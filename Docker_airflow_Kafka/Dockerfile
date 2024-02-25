FROM apache/airflow:2.6.3

# pip 업그레이드 명령을 추가합니다.
RUN python -m pip install --upgrade pip

# root 권한으로 패키지 설치
USER root
RUN apt-get update && apt-get install -y libgomp1
USER airflow

# 여기에 필요한 추가적인 패키지 설치 명령을 넣습니다.
RUN pip install lightgbm
RUN pip install joblib
RUN pip install scikit-learn
RUN pip install tensorflow
RUN pip install xgboost
RUN pip install confluent_kafka
RUN pip install --upgrade kafka-python

