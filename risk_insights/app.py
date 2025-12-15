import os
import json
import psycopg2
from datetime import datetime, timedelta

# ==========================
# DB Connection
# ==========================
def get_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dbname=os.environ["DB_NAME"],
        port=int(os.environ.get("DB_PORT", 5432))
    )

# ==========================
# Helpers
# ==========================
def trend_arrow(current, previous):
    if current > previous:
        return "up"
    elif current < previous:
        return "down"
    return "stable"

# ==========================
# Main Lambda
# ==========================
def lambda_handler(event, context):
    params = event.get("queryStringParameters") or {}
    window_days = int(params.get("window_days", 7))

    now = datetime.utcnow()
    start_current = now - timedelta(days=window_days)
    start_previous = start_current - timedelta(days=window_days)

    conn = get_connection()
    cur = conn.cursor()

    # --------------------------
    # CURRENT WINDOW
    # --------------------------

    # w: stale jira issues
    cur.execute("""
        SELECT COUNT(*)
        FROM jira_issues
        WHERE status NOT IN ('Done','Closed','Resolved')
          AND updated_at < %s
    """, (start_current,))
    w = cur.fetchone()[0]

    # x: high priority delayed
    cur.execute("""
        SELECT COUNT(*)
        FROM jira_issues
        WHERE priority IN ('High','Critical')
          AND status NOT IN ('Done','Closed','Resolved')
    """)
    x = cur.fetchone()[0]

    # y: stuck PRs
    cur.execute("""
        SELECT COUNT(*)
        FROM pull_requests
        WHERE state = 'open'
          AND merged = false
          AND timestamp < %s
    """, (start_current,))
    y = cur.fetchone()[0]

    # z: critical incidents
    cur.execute("""
        SELECT COUNT(*)
        FROM servicenow_incidents
        WHERE severity IN ('High','Critical')
          AND state NOT IN ('Resolved','Closed')
    """)
    z = cur.fetchone()[0]

    # --------------------------
    # PREVIOUS WINDOW
    # --------------------------

    cur.execute("""
        SELECT COUNT(*)
        FROM jira_issues
        WHERE status NOT IN ('Done','Closed','Resolved')
          AND updated_at < %s
    """, (start_previous,))
    w_prev = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM pull_requests
        WHERE state = 'open'
          AND merged = false
          AND timestamp < %s
    """, (start_previous,))
    y_prev = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM servicenow_incidents
        WHERE severity IN ('High','Critical')
          AND state NOT IN ('Resolved','Closed')
    """)
    z_prev = cur.fetchone()[0]

    cur.close()
    conn.close()

    # --------------------------
    # Severity Scores
    # --------------------------
    jira_severity = (w * 1) + (x * 2)
    pr_severity = y * 1.5
    incident_severity = z * 3

    # --------------------------
    # Final Response
    # --------------------------
    response = {
        "at_risk_jira": {
            "count": w + x,
            "severity": jira_severity,
            "trend": trend_arrow(w + x, w_prev)
        },
        "high_priority_delayed": {
            "count": x,
            "severity": x * 2,
            "trend": trend_arrow(x, x)  # same window
        },
        "critical_incidents": {
            "count": z,
            "severity": incident_severity,
            "trend": trend_arrow(z, z_prev)
        },
        "prs_stuck": {
            "count": y,
            "severity": pr_severity,
            "trend": trend_arrow(y, y_prev)
        }
    }

    return {
        "statusCode": 200,
        "body": json.dumps(response, indent=2)
    }
