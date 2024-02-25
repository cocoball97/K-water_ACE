from flask import Flask, render_template, jsonify
import psycopg2

app = Flask(__name__)

# PostgreSQL 데이터베이스 연결 정보 설정
db_host = "172.30.1.87"
db_user = "airflow"
db_name = "airflow"
db_password = "airflow"
db_port = "5432"

def get_data_from_db1():
    try:
        connection = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password
        )

        cursor = connection.cursor()

        cursor.execute('SELECT * FROM public.kwater ORDER BY "logTime" DESC LIMIT 10;')
        data = cursor.fetchall()  # 가장 최근 레코드 가져오기

        cursor.close()
        connection.close()

        return data

    except psycopg2.Error as e:
        print("PostgreSQL 연결 오류:", e)
        return []

@app.route('/')
def index():
    selected_data_1  = get_data_from_db1()

    data1 = [
        [
            float("{:.2f}".format(value)) if isinstance(value, (float, int)) else value
            for value in row
        ]
        for row in selected_data_1
    ]

    return render_template("Homepage.html", data1 = data1)

@app.route('/get_latest_data', methods=['GET'])
def get_latest_data():
    data = get_data_from_db1()
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)

