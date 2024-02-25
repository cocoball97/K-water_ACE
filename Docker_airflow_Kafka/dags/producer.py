import pandas as pd
import psycopg2
from datetime import datetime
from airflow import DAG
from airflow.models.variable import Variable
from airflow.operators.python import PythonOperator
from airflow.operators.python import BranchPythonOperator
from joblib import load
import numpy as np
import logging
import random
from sklearn.preprocessing import MinMaxScaler
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient

# kafka 설정
kafka_conf = {
    "bootstrap.servers": "daa-kafka1:9092, daa-kafka2:9093, daa-kafka3:9094",  # Kafka 브로커의 주소
    "client.id": "water"
}
kafka_topic = 'water'

# 센서데이터 대체 > 랜덤데이터 생성
def generate_random_data(**kwargs):
    conn = psycopg2.connect(
        host="172.30.1.87",
        user="airflow",
        password="airflow"
    )
    query = "SELECT * FROM kwater"
    df = pd.read_sql(query, conn)
    conn.close()
    
    index_list = list(df.index)
    rand_index = random.sample(index_list, k=1)
    new_data = df.iloc[rand_index, [1, 2, 3, 4, 5, 8]].values * 0.9

    return new_data.tolist()



def produce(**kwargs):
    # Kafka 프로듀서 생성
    producer = Producer(kafka_conf)
    ti = kwargs['ti']
    new_data = ti.xcom_pull(task_ids='generate_random_data_task')
    message = str(new_data).encode('utf-8')
    producer.produce(kafka_topic, message)
    # poll 메서드 호출: 콜백을 처리하고, 전송 상태를 관리합니다.
    producer.poll(0)
    # Kafka Producer를 닫습니다. (################### 전송완료역할  존나 이것때문이래)
    producer.flush()
    print(f'전송메시지: {message}')



default_args = {
    'start_date': datetime(2021, 1, 1),
}


with DAG(dag_id='producer_dag',
         schedule_interval="* * * * *", #"* * * * *",  
         default_args=default_args,
         catchup=False) as dag:
    
    generate_data_task = PythonOperator(
        task_id='generate_random_data_task',
        python_callable=generate_random_data
    )
    
    produce_task = PythonOperator(
        task_id='produce_task',
        python_callable=produce,
        provide_context=True
    )

    generate_data_task >> produce_task
