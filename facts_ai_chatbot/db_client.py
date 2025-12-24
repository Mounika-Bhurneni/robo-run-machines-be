import os
import psycopg2
import psycopg2.extras

def get_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dbname=os.environ["DB_NAME"],
        port=int(os.environ.get("DB_PORT", 5432))
    )

def run_safe_query(sql: str):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        cur.execute(sql)
        rows = cur.fetchall()
        return rows[:10]   # 🔒 Hard safety limit
    finally:
        cur.close()
        conn.close()
