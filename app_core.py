from fastapi import FastAPI
import sqlite3

app = FastAPI()


def get_db_connection():
    conn = sqlite3.connect('database/api.db')
    conn.row_factory = sqlite3.Row
    return conn

def execute_test_query(db_type, host, port, db_name, username, password, sql_query, query_params=None):
    import datetime

    def serialize_row(row, columns):
        return {
            col: val.isoformat() if isinstance(val, (datetime.datetime, datetime.date)) else val
            for col, val in zip(columns, row)
        }

    query_params = query_params or {}

    if db_type in ("oracle_cx", "oracle_legacy"):
        import cx_Oracle
        dsn = f"{host}:{port}/{db_name}"
        conn = cx_Oracle.connect(user=username, password=password, dsn=dsn)
        cursor = conn.cursor()
        final_query = f"SELECT * FROM ({sql_query}) WHERE ROWNUM <= 10"
        cursor.execute(final_query, query_params)
        columns = [col[0].lower() for col in cursor.description]
        rows = [serialize_row(row, columns) for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return rows

    elif db_type == "oracle":
        import oracledb
        dsn = f"{host}:{port}/{db_name}"
        conn = oracledb.connect(user=username, password=password, dsn=dsn)
        cursor = conn.cursor()
        final_query = sql_query + " FETCH FIRST 10 ROWS ONLY"
        cursor.execute(final_query, query_params)
        columns = [col[0].lower() for col in cursor.description]
        rows = [serialize_row(row, columns) for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return rows

    elif db_type == "postgresql":
        import psycopg2
        import re
        conn = psycopg2.connect(host=host, port=port, dbname=db_name, user=username, password=password)
        cursor = conn.cursor()
        pattern = re.compile(r":(\w+)")
        final_query = pattern.sub(r"%(\1)s", sql_query) + " LIMIT 10"
        cursor.execute(final_query, query_params)
        columns = [desc[0].lower() for desc in cursor.description]
        rows = [serialize_row(row, columns) for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return rows

    elif db_type == "clickhouse":
        import clickhouse_connect
        final_query = sql_query.format(**query_params) + " LIMIT 10"
        client = clickhouse_connect.get_client(host=host, port=port, username=username, password=password)
        result = client.query(final_query)
        columns = result.column_names
        rows = [serialize_row(row, columns) for row in result.result_rows]
        return rows

    else:
        raise Exception(f"Неподдерживаемый тип БД: {db_type}")

