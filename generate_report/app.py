import os
import json
import psycopg2
from datetime import datetime, date

ALLOWED_ROLES = ["DEV", "QA", "MANAGER", "DEV_MANAGER"]

# ==========================================================
# DB Connection
# ==========================================================
def get_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dbname=os.environ["DB_NAME"]
    )


# ==========================================================
# JSON Encoder
# ==========================================================
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


# ==========================================================
# Response Helpers
# ==========================================================
def success(status, message, data=None):
    return {
        "statusCode": status,
        "body": json.dumps(
            {"status": status, "message": message, "data": data},
            cls=DateTimeEncoder
        )
    }


def error(status, message):
    return {
        "statusCode": status,
        "body": json.dumps({"status": status, "message": message})
    }


# ==========================================================
# Fetch Jira Issues
# ==========================================================
def fetch_jira_issues(cursor, team, from_date, to_date):
    cursor.execute(
        """
        SELECT issue_id, title, status, assignee, created_at, updated_at
        FROM jira_issues
        WHERE team = %s
          AND created_at >= %s
          AND created_at <= %s
        ORDER BY created_at DESC;
        """,
        (team, from_date, to_date),
    )
    return cursor.fetchall()


# ==========================================================
# Fetch GitHub PRs (including merges)
# ==========================================================
def fetch_github_prs(cursor, team, from_date, to_date):
    cursor.execute(
        """
        SELECT pr_id, title, state, author, created_at, merged_at
        FROM github_pull_requests
        WHERE team = %s
          AND created_at >= %s
          AND created_at <= %s
        ORDER BY created_at DESC;
        """,
        (team, from_date, to_date),
    )
    return cursor.fetchall()


# ==========================================================
# Fetch Sprint Progress from jira_sprints
# ==========================================================
def fetch_sprint_progress(cursor, team, from_date, to_date):
    cursor.execute(
        """
        SELECT id, sprint_id, repo_or_board_id, name, state,
               start_date, end_date, goal, event_type,
               author_login, timestamp, raw
        FROM jira_sprints
        WHERE timestamp >= %s
          AND timestamp <= %s
        ORDER BY timestamp DESC;
        """,
        (from_date, to_date),
    )
    return cursor.fetchall()


# ==========================================================
# Fetch Jira Subtasks from jira_subtasks
# ==========================================================
def fetch_jira_subtasks(cursor, team, from_date, to_date):
    cursor.execute(
        """
        SELECT id, subtask_id, parent_issue_id, board_id,
               summary, status, event_type, author_login,
               timestamp, raw
        FROM jira_subtasks
        WHERE timestamp >= %s
          AND timestamp <= %s
        ORDER BY timestamp DESC;
        """,
        (from_date, to_date),
    )
    return cursor.fetchall()


# ==========================================================
# Fetch Activity Logs
# ==========================================================
def fetch_activity_logs(cursor, team, from_date, to_date):
    cursor.execute(
        """
        SELECT log_id, event_type, description, created_at, user_id
        FROM activity_logs
        WHERE team = %s
          AND created_at >= %s
          AND created_at <= %s
        ORDER BY created_at DESC;
        """,
        (team, from_date, to_date),
    )
    return cursor.fetchall()


# ==========================================================
# Main Lambda
# ==========================================================
def lambda_handler(event, context):
    print("EVENT:", json.dumps(event))

    try:
        query = event.get("queryStringParameters") or {}

        team = query.get("team")
        from_date = query.get("from_date")
        to_date = query.get("to_date")
        report_type = query.get("type", "full")  # jira|github|sprints|subtasks|logs|full

        if not team or not from_date or not to_date:
            return error(400, "team, from_date, to_date are required")

        conn = get_connection()
        cursor = conn.cursor()

        response_data = {}

        # -----------------------------
        # JIRA Issues
        # -----------------------------
        if report_type in ["jira", "full"]:
            response_data["jira_issues"] = fetch_jira_issues(cursor, team, from_date, to_date)

        # -----------------------------
        # GitHub PRs + merges
        # -----------------------------
        if report_type in ["github", "full"]:
            response_data["github_pull_requests"] = fetch_github_prs(cursor, team, from_date, to_date)

        # -----------------------------
        # Sprint Progress
        # -----------------------------
        if report_type in ["sprints", "full"]:
            response_data["jira_sprint_progress"] = fetch_sprint_progress(cursor, team, from_date, to_date)

        # -----------------------------
        # Jira Subtasks
        # -----------------------------
        if report_type in ["subtasks", "full"]:
            response_data["jira_subtasks"] = fetch_jira_subtasks(cursor, team, from_date, to_date)

        # -----------------------------
        # Activity Logs
        # -----------------------------
        if report_type in ["logs", "full"]:
            response_data["activity_logs"] = fetch_activity_logs(cursor, team, from_date, to_date)

        cursor.close()
        conn.close()

        return success(200, "Report generated successfully", response_data)

    except Exception as e:
        print("ERROR:", str(e))
        return error(500, f"Internal error: {str(e)}")
