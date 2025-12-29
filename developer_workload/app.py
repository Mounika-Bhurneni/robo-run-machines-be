import os
import json
import psycopg2
from datetime import datetime, timezone

# DB Config
DB_HOST = os.environ.get("DB_HOST")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_NAME = os.environ.get("DB_NAME")

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME
    )

def lambda_handler(event, context):
    conn = get_connection()
    cur = conn.cursor()

    # -------------------------
    # Get email from query params (optional)
    # -------------------------
    email = (
        event.get("queryStringParameters") or {}
    ).get("email")

    # -------------------------
    # Fetch Jira Issues
    # -------------------------
    if email:
        cur.execute("""
            SELECT assignee_user_id, assignee_name, status, priority, updated_at
            FROM jira_issues
            WHERE assignee_user_id IS NOT NULL
              AND assignee_email = %s
        """, (email,))
    else:
        cur.execute("""
            SELECT assignee_user_id, assignee_name, status, priority, updated_at
            FROM jira_issues
            WHERE assignee_user_id IS NOT NULL
        """)

    issues = cur.fetchall()

    # -------------------------
    # Fetch Jira Subtasks
    # -------------------------
    if email:
        cur.execute("""
            SELECT author_login, status, timestamp
            FROM jira_subtasks
            WHERE author_login = %s
        """, (email,))
    else:
        cur.execute("""
            SELECT author_login, status, timestamp
            FROM jira_subtasks
        """)

    subtasks = cur.fetchall()

    cur.close()
    conn.close()

    now = datetime.now(timezone.utc)
    workload = {}

    # -------------------------
    # Process Issues
    # -------------------------
    for assignee_id, name, status, priority, updated_at in issues:
        if assignee_id not in workload:
            workload[assignee_id] = {
                "name": name,
                "open_issues": 0,
                "high_priority_issues": 0,
                "idle_days_max": 0,
                "subtasks": 0
            }

        if status.lower() not in ("done", "closed", "resolved"):
            workload[assignee_id]["open_issues"] += 1

        if priority and priority.lower() in ("high", "critical"):
            workload[assignee_id]["high_priority_issues"] += 1

        if updated_at:
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            idle_days = (now - updated_at).days
            workload[assignee_id]["idle_days_max"] = max(
                workload[assignee_id]["idle_days_max"],
                idle_days
            )

    # -------------------------
    # Process Subtasks
    # -------------------------
    for author_login, status, timestamp in subtasks:
        if author_login not in workload:
            workload[author_login] = {
                "name": author_login,
                "open_issues": 0,
                "high_priority_issues": 0,
                "idle_days_max": 0,
                "subtasks": 0
            }

        if status.lower() not in ("done", "closed", "resolved"):
            workload[author_login]["subtasks"] += 1

    # -------------------------
    # Prepare Response
    # -------------------------
    response = []
    for user_id, metrics in workload.items():
        response.append({
            "user_id": user_id,
            "name": metrics["name"],
            "open_issues": metrics["open_issues"],
            "high_priority_issues": metrics["high_priority_issues"],
            "subtasks": metrics["subtasks"],
            "max_idle_days": metrics["idle_days_max"]
        })

    return {
        "statusCode": 200,
        "body": json.dumps(response, indent=2)
    }
