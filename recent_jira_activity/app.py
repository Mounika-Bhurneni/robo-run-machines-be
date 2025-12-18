import os
import json
import psycopg2
from datetime import datetime, timezone


def time_ago(ts):
    if not ts:
        return None

    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts)
        except ValueError:
            return None  # 👈 prevents crashes

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
                type,
                title,
                description,
                author,
                project_name,
                timestamp
            FROM (
                SELECT
                    'ISSUE' AS type,
                    issue_key AS title,
                    LEFT(raw->'fields'->>'summary', 120) AS description,
                    assignee_name AS author,
                    raw->'fields'->'project'->>'name' AS project_name,
                    updated_at::timestamptz AS timestamp
                FROM jira_issues

                UNION ALL

                SELECT
                    'SPRINT',
                    name,
                    state,
                    author_login,
                    raw->'project'->>'name',
                    timestamp::timestamptz
                FROM jira_sprints

                UNION ALL

                SELECT
                    'SUBTASK',
                    summary,
                    status,
                    author_login,
                    raw->'fields'->'project'->>'name',
                    timestamp::timestamptz
                FROM jira_subtasks

                UNION ALL

                SELECT
                    'COMMENT',
                    CONCAT('Comment on Issue ', issue_id),
                    LEFT(comment_body, 120),
                    author_login,
                    raw->'fields'->'project'->>'name',
                    timestamp::timestamptz
                FROM jira_issue_comments
            ) activities
            ORDER BY timestamp DESC
            LIMIT 30;


        """)

       
        rows = cur.fetchall()
        activities = []
        for row in rows:
            ts = row[5]   # 👈 THIS is the timestamp column

            activities.append({
                "type": row[0],
                "title": row[1],
                "description": row[2],
                "author": row[3],
                "project_name": row[4],
                "timestamp": ts,
                "time_ago": time_ago(ts) if ts else None
            })


        cur.close()
        conn.close()

        return {
            "statusCode": 200,
            "body": json.dumps(
                {"jira_recent_activities": activities},
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
