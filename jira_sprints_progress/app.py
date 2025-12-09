import os
import json
import psycopg2
from datetime import datetime, date

ALLOWED_ROLES = ["DEV", "QA", "MANAGER", "DEV_MANAGER"]


def get_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dbname=os.environ["DB_NAME"],
        port=5432
    )


def lambda_handler(event, context):
    try:
        # Extract JWT claims
        claims = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {})
        user_email = claims.get("email")
        user_role = claims.get("custom:role")
        sub = claims.get("sub")

        print("User Email:", user_email)
        print("User Role:", user_role)
        print("sub:", sub)

        # Role check
        if not user_role or user_role not in ALLOWED_ROLES:
            return {
                "statusCode": 403,
                "body": json.dumps({"error": "Access denied. Insufficient permissions."})
            }

        conn = get_connection()
        cur = conn.cursor()

        # ==========================================================
        # Fetch ALL Sprints (Latest Record Per Sprint)
        # ==========================================================
        cur.execute("""
            SELECT DISTINCT ON (sprint_id)
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
            ORDER BY sprint_id, timestamp DESC
        """)

        sprints = cur.fetchall()
        cur.close()
        conn.close()

        if not sprints:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "No sprints found"})
            }

        today = date.today()
        sprint_list = []

        # ==========================================================
        # Process Each Sprint
        # ==========================================================
        for sprint in sprints:
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

            # Compute progress
            if not start_date or not end_date:
                progress = None
                remaining_days = None
                total_days = None
                status = "Incomplete sprint data"
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

            sprint_list.append({
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
            })

        # ==========================================================
        # Final Response
        # ==========================================================
        return {
            "statusCode": 200,
            "body": json.dumps({
                "count": len(sprint_list),
                "sprints": sprint_list
            }, default=str)
        }

    except Exception as e:
        print("Error:", str(e))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
