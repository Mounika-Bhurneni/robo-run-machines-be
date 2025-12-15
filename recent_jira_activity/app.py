import os
import json
import psycopg2
from datetime import datetime, timezone

ALLOWED_ROLES = ["DEV", "QA", "MANAGER", "DEV_MANAGER"]

# ==========================================================
# PostgreSQL Connection
# ==========================================================
def get_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dbname=os.environ["DB_NAME"],
        port=5432
    )

# ==========================================================
# Time Ago Helper
# ==========================================================
from datetime import datetime, timezone

def time_ago(ts):
    # Make DB timestamp timezone-aware (UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    diff = now - ts

    seconds = int(diff.total_seconds())
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24

    if seconds < 60:
        return "just now"
    elif minutes < 60:
        return f"{minutes} min ago"
    elif hours < 24:
        return f"{hours} h ago"
    else:
        return f"{days} d ago"


# ==========================================================
# Lambda Handler
# ==========================================================
def lambda_handler(event, context):
    try:
        claims = (
            event.get("requestContext", {})
            .get("authorizer", {})
            .get("jwt", {})
            .get("claims", {})
        )

        user_role = claims.get("custom:role")

        if not user_role or user_role not in ALLOWED_ROLES:
            return {
                "statusCode": 403,
                "body": json.dumps({"error": "Access denied"})
            }

        conn = get_connection()
        cur = conn.cursor()

        # ================================================================
        # RECENT JIRA TICKETS (Ticket-centric)
        # ================================================================
        cur.execute("""
            SELECT
                issue_key,
                assignee_name,
                updated_at,
                status,
                priority,
                LEFT(raw->'fields'->>'summary', 120) AS summary
            FROM jira_issues
            ORDER BY updated_at DESC
            LIMIT 20
        """)

        rows = cur.fetchall()

        jira_tickets = []
        for row in rows:
            jira_tickets.append({
                "jira_ticket_id": row[0],
                "assignee_name": row[1],
                "timestamp": row[2],
                "time_ago": time_ago(row[2]),
                "status": row[3],
                "priority": row[4],
                "summary": row[5]
            })

        cur.close()
        conn.close()

        return {
            "statusCode": 200,
            "body": json.dumps(
                {"jira_recent_tickets": jira_tickets},
                default=str,
                indent=2
            )
        }

    except Exception as e:
        print("Error:", str(e))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
