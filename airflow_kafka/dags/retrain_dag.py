import pandas as pd
import psycopg2
from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from joblib import dump
from sklearn.ensemble import ExtraTreesRegressor
from pytz import timezone 




from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split


def train_and_save_model():
    conn = psycopg2.connect(
        host="172.30.1.87",
        user="airflow",
        password="airflow"
    )
    
    query = "SELECT * FROM kwater"
    df = pd.read_sql(query, conn)

    clusters = df['cluster'].unique()
    model1=ExtraTreesRegressor(max_depth=15, n_estimators=200, random_state=6666)
    model_list=[model1]
    features = ['탁도', 'pH', '수온', '전기전도도', '알칼리도']
    target = 'PACS투입률'

    for cluster in clusters:
        condition = df['cluster'] == cluster
        X = df.loc[condition, features]
        y = df.loc[condition, target]
        
        # 데이터 분할
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=6666)

        best_model = None
        best_score = float('inf')
        
        for model in model_list:
            model.fit(X_train, y_train)
            predictions = model.predict(X_val)
            score = mean_squared_error(y_val, predictions)
            
            if score < best_score:
                best_score = score
                best_model = model
        best_model.fit(X,y)
        
        dump(best_model, f'./models/reg_clust_{int(cluster)}.pkl')

        
    # 모델 학습이 모두 끝난 후에 현재 시간을 가져옵니다.
    seoul_timezone = timezone("Asia/Seoul")
    current_time = datetime.now(seoul_timezone).strftime('%Y/%m/%d %H:%M')
    # 현재 시간을 kwater_copy 테이블의 update 칼럼에 저장합니다.
    update_query = """
        UPDATE kwater
        SET update_time = %s;
        """
    # WHERE update_time IS NULL OR update_time = ''
    with conn.cursor() as cursor:
        cursor.execute(update_query, (current_time,))
        conn.commit()

    conn.close()




default_args = {
    'start_date': datetime(2021, 1, 1),
}

with DAG(dag_id='retrain_dag',
         schedule_interval="*/2 * * * *",#*/2 * * * *
         default_args=default_args, 
         catchup=False) as dag:

    train_and_save_model_task = PythonOperator(
        task_id='train_and_save_model',
        python_callable=train_and_save_model
    )
    

train_and_save_model_task
