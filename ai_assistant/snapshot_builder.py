import psycopg2
import os
from datetime import datetime, timedelta

def get_conn():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dbname=os.environ["DB_NAME"],
        port=os.environ.get("DB_PORT", "5432")
    )


def build_snapshot():
    conn = get_conn()
    cur = conn.cursor()

    snapshot = {}

    # -----------------------
    # Sprint Progress
    # -----------------------
    cur.execute("""
        SELECT COUNT(*) FILTER (WHERE status IN ('Done','Closed','Resolved')) AS completed,
               COUNT(*) AS total
        FROM jira_issues
    """)
    completed, total = cur.fetchone()
    progress_pct = round((completed / total) * 100, 2) if total else 0

    snapshot["sprint_progress"] = {
        "completed": completed,
        "total": total,
        "progress_pct": progress_pct
    }

    # -----------------------
    # Risks (same as risk_insights)
    # -----------------------
    now = datetime.utcnow()

    cur.execute("""
        SELECT COUNT(*) FROM jira_issues
        WHERE status NOT IN ('Done','Closed','Resolved')
          AND updated_at < %s
    """, (now - timedelta(days=7),))
    at_risk = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM pull_requests
        WHERE state = 'open'
          AND merged = false
          AND timestamp < %s
    """, (now - timedelta(hours=72),))
    prs_stuck = cur.fetchone()[0]

    snapshot["risks"] = {
        "at_risk_jira": at_risk,
        "prs_stuck": prs_stuck
    }

    # -----------------------
    # Workload Summary (simple, safe)
    # -----------------------
    cur.execute("""
        SELECT assignee_name, COUNT(*) AS issue_count
        FROM jira_issues
        WHERE status NOT IN ('Done','Closed','Resolved')
        GROUP BY assignee_name
    """)

    workloads = [{"name": r[0], "open_items": r[1]} for r in cur.fetchall()]
    snapshot["workload"] = workloads

    cur.close()
    conn.close()

    return snapshot
