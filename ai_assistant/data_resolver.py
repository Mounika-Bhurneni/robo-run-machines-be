import psycopg2
import os
from datetime import datetime, timedelta


def get_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dbname=os.environ["DB_NAME"],
        port=int(os.environ.get("DB_PORT", 5432)),
    )


def resolve_data(question: str):
    """
    Fetch only the minimum data needed.
    No AI logic here.
    """

    conn = get_connection()
    cur = conn.cursor()

    data = {}

    # -------- COMMITS --------
    if "commit" in question.lower():
        cur.execute("""
            SELECT author_login, COUNT(*) AS commits
            FROM pull_requests
            WHERE created_at >= NOW() - INTERVAL '30 days'
            GROUP BY author_login
        """)
        data["commits"] = cur.fetchall()

    # -------- RISK --------
    if "risk" in question.lower():
        cur.execute("""
            SELECT COUNT(*)
            FROM jira_issues
            WHERE status NOT IN ('Done','Closed','Resolved')
              AND updated_at < NOW() - INTERVAL '7 days'
        """)
        data["at_risk_jira"] = cur.fetchone()[0]

    # -------- PR STUCK --------
    if "pr" in question.lower():
        cur.execute("""
            SELECT COUNT(*)
            FROM pull_requests
            WHERE state = 'open'
              AND merged = false
              AND timestamp < NOW() - INTERVAL '72 hours'
        """)
        data["prs_stuck"] = cur.fetchone()[0]

    cur.close()
    conn.close()

    return data
