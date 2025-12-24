import os
import psycopg2
from datetime import datetime, timedelta


def get_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dbname=os.environ["DB_NAME"],
        port=int(os.environ.get("DB_PORT", 5432))
    )


def fetch_metrics():
    conn = get_connection()
    cur = conn.cursor()

    # -------------------------
    # Sprint velocity (example)
    # -------------------------
    cur.execute("""
        SELECT COUNT(*) FROM jira_issues
        WHERE status = 'Done'
          AND updated_at >= NOW() - INTERVAL '7 days'
    """)
    velocity = cur.fetchone()[0]

    # -------------------------
    # Risk metrics
    # -------------------------
    cur.execute("""
        SELECT COUNT(*) FROM jira_issues
        WHERE status NOT IN ('Done','Closed','Resolved')
          AND updated_at < NOW() - INTERVAL '7 days'
    """)
    at_risk = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM pull_requests
        WHERE state = 'open'
          AND timestamp < NOW() - INTERVAL '72 hours'
    """)
    prs_stuck = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM servicenow_incidents
        WHERE severity IN ('High','Critical')
          AND state NOT IN ('Resolved','Closed')
    """)
    incidents = cur.fetchone()[0]

    cur.close()
    conn.close()

    return {
        "velocity": velocity,
        "at_risk_jira": at_risk,
        "prs_stuck": prs_stuck,
        "critical_incidents": incidents
    }
