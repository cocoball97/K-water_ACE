import pandas as pd
import psycopg2
from datetime import datetime
from airflow.operators.python import PythonOperator
from joblib import load
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import load_model
from confluent_kafka import Consumer, KafkaException, KafkaError
from pytz import timezone 
from airflow import DAG
import json
import time
import numpy as np
import random

# Kafka 컨슈머 설정
kafka_consumer_conf = {
    'bootstrap.servers': "daa-kafka1:9092, daa-kafka2:9093, daa-kafka3:9094",
    'group.id': 'my_consumer_group',
    'auto.offset.reset': 'latest'
}
kafka_topic = 'water'


def consume(**kwargs):
    consumer = Consumer(kafka_consumer_conf)
    consumer.subscribe([kafka_topic])
    try:
        msg = consumer.poll(timeout=20)
        if msg is not None:
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    print(msg.error())
                    raise KafkaException(msg.error())
            else:
                # 메시지 처리
                new_data = json.loads(msg.value().decode('utf-8'))
                print(f'받은 메시지',new_data)
                return new_data
        else:
            print('메시지 없음')

    except KafkaException as e:
        # 에러 처리 로직
        print('예외')
    finally:
        consumer.close()

    
def predict_ntu(**kwargs):
    conn = psycopg2.connect(
        host="172.30.1.87",
        user="airflow",
        password="airflow"
    )
    query = "SELECT * FROM kwater"
    df = pd.read_sql(query, conn)
    conn.close()
    lstm_df=df[['탁도']]
    cutoff = {'탁도' : 0.1}
    cols = ['탁도']
    for col in cols:
        # 푸리에 변환
        frequencies = np.fft.fftfreq(len(lstm_df[col]))
        fft_values = np.fft.fft(lstm_df[col])

        # 컷오프 주파수 설정 및 필터 적용
        cutoff_frequency = cutoff.get(col, 0.1)
        fft_values[np.abs(frequencies) > cutoff_frequency] = 0

        # 역 푸리에 변환
        low_val = np.fft.ifft(fft_values).real
        lstm_df[col] = low_val

    scaler=MinMaxScaler(feature_range=(0,1)).fit(lstm_df[['탁도']].astype(float))
    index_list = list(df.index)
    rand_index = random.sample(index_list, k=1)

    # 2시간, 1시간 이전 값
    if rand_index[0]>=2:
        previous_data=[[df.iloc[[rand_index[0]-2], 1].values[0]*0.99],[df.iloc[[rand_index[0]-1], 1].values[0]*1.01],[df.iloc[rand_index, 1].values[0]*0.98]]

    # LSTM 모델 적용
    ntu_model=load_model('./models/lstm_ntu.h5')
    ss_ntu_data=scaler.transform(previous_data)
    seq_len=3
    input_ntu_data=[ss_ntu_data[-seq_len:]]
    input_ntu_data=np.array(input_ntu_data)
    ntu_pred_scaled=ntu_model.predict(input_ntu_data)
    ntu_pred=scaler.inverse_transform(ntu_pred_scaled)[0]
    print('new data :', previous_data)
    print('t+1 ntu :', ntu_pred)
    print(type(ntu_pred))
    return ntu_pred



def load_modeling(**kwargs):
    ti = kwargs['ti']
    new_data = ti.xcom_pull(task_ids='consume_task')
    cl_model = load('./models/classify_model.pkl')
    new_pred_cluster = cl_model.predict([new_data[0][0:5]])
    reg_model = load(f'./models/reg_clust_{new_pred_cluster[0]}.pkl')
    new_pred_pacs = reg_model.predict([new_data[0][0:5]])
    return new_pred_pacs, new_pred_cluster





def insert_to_db(**kwargs):
    ti = kwargs['ti']
    new_data = ti.xcom_pull(task_ids='consume_task')[0]
    ntu_pred = ti.xcom_pull(task_ids='predict_ntu_task')[0]
    new_pred_pacs = ti.xcom_pull(task_ids='load_modeling')[0]
    new_pred_cluster = ti.xcom_pull(task_ids='load_modeling')[1]
    print(new_data)

    conn = psycopg2.connect(
        host="172.30.1.87",
        user="airflow",
        password="airflow"
    )
    cursor = conn.cursor()
    insert_query = """
    INSERT INTO kwater ("logTime", 탁도, "pH", 수온, 전기전도도, 알칼리도, "PACS투입률", cluster, 원수유입유량, 예측탁도)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
    """
    seoul_timezone = timezone("Asia/Seoul")
    current_time = datetime.now(seoul_timezone).strftime('%Y/%m/%d %H:%M')
    cursor.execute(insert_query, (current_time, new_data[0], new_data[1], new_data[2], new_data[3], new_data[4], float(new_pred_pacs[0]), int(new_pred_cluster[0]), new_data[5], float(ntu_pred)))

    conn.commit()
    conn.close()







default_args = {
    'start_date': datetime(2021, 1, 1),
}

with DAG(dag_id='modeling_dag',
         schedule_interval="* * * * *",#"* * * * *"
         default_args=default_args,
         catchup=False) as dag:

    consume_task = PythonOperator(
        task_id='consume_task',
        python_callable=consume
    )

    predict_ntu_task = PythonOperator(
        task_id='predict_ntu_task',
        python_callable=predict_ntu,
        provide_context=True
    )

    modeling_task = PythonOperator(
        task_id='load_modeling',
        python_callable=load_modeling,
        provide_context=True
    )

    insert_task = PythonOperator(
        task_id='insert_task',
        python_callable=insert_to_db,
        provide_context=True
    )


    consume_task >> [predict_ntu_task, modeling_task] >> insert_task
