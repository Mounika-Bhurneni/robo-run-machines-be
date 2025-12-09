import os
import json
import psycopg2
from datetime import datetime, date

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
        # Extract JWT claims
        claims = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {})
        user_role = claims.get("custom:role")
        user_email = claims.get("email")

        print("User:", user_email)
        print("Role:", user_role)

        # Role check
        if not user_role or user_role not in ALLOWED_ROLES:
            return {
                "statusCode": 403,
                "body": json.dumps({"error": "Access denied. Insufficient permissions."})
            }

        # Get sprint_id from query params
        sprint_id = event.get("queryStringParameters", {}).get("sprint_id")
        if not sprint_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing sprint_id"})
            }

        conn = get_connection()
        cur = conn.cursor()

        # ==========================================================
        # Fetch Sprint Info
        # ==========================================================
        cur.execute("""
            SELECT
                sprint_id,
                repo_or_board_id,
                name,
                state,
                start_date,
                end_date,
                goal,
                event_type,
                author_login,
                timestamp
            FROM jira_sprints
            WHERE sprint_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """, (sprint_id,))

        sprint = cur.fetchone()
        cur.close()
        conn.close()

        if not sprint:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Sprint not found"})
            }

        (
            sprint_id,
            board_id,
            name,
            state,
            start_date,
            end_date,
            goal,
            event_type,
            author_login,
            updated_at
        ) = sprint

        # ==========================================================
        # Calculate Sprint Progress
        # ==========================================================
        today = date.today()

        # Handle missing dates
        if start_date is None or end_date is None:
            progress = None
            status = "Incomplete sprint data"
            remaining_days = None
            total_days = None
        else:
            total_days = (end_date.date() - start_date.date()).days
            elapsed_days = (today - start_date.date()).days

            if today < start_date.date():
                progress = 0
                status = "Not Started"
                remaining_days = total_days
            elif start_date.date() <= today <= end_date.date():
                progress = round((elapsed_days / total_days) * 100, 2)
                status = "In Progress"
                remaining_days = (end_date.date() - today).days
            else:
                progress = 100
                status = "Completed / Past End Date"
                remaining_days = 0

        # ==========================================================
        # Response
        # ==========================================================
        return {
            "statusCode": 200,
            "body": json.dumps({
                "sprint_id": sprint_id,
                "board_id": board_id,
                "name": name,
                "state": state,
                "goal": goal,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "status": status,
                "progress_percent": progress,
                "days_total": total_days,
                "days_remaining": remaining_days,
                "last_update": str(updated_at)
            }, default=str)
        }

    except Exception as e:
        print("Error:", str(e))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
