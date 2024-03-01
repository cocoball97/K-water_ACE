FROM jupyter/pyspark-notebook

# 필요한 패키지 및 라이브러리 설치
RUN pip install pyspark

USER root
RUN apt-get update && \
    apt-get install -y wget && \
    apt-get clean

# PostgreSQL JDBC 드라이버 다운로드 및 Spark의 jars 디렉터리에 배포
RUN mkdir -p /opt/spark/jars && \
    wget -O /opt/spark/jars/postgresql.jar https://jdbc.postgresql.org/download/postgresql-42.2.20.jar
USER jovyan

# Spark 세션의 클래스패스에 PostgreSQL JDBC 드라이버 추가
ENV SPARK_DIST_CLASSPATH="/opt/spark/jars/*"
