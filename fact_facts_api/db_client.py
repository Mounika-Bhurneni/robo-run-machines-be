import os
import psycopg2
import psycopg2.extras

def run_query(sql, params=None):
    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dbname=os.environ["DB_NAME"],
        port=int(os.environ.get("DB_PORT", 5432))
    )

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(sql, params or {})
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows[:MAX_DB_ROWS]

