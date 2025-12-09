import os
import json
import psycopg2
from datetime import datetime, date


# ==========================================================
# 1. DB Connection
# ==========================================================
def get_connection():
    try:
        return psycopg2.connect(
            host=os.environ["DB_HOST"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            dbname=os.environ["DB_NAME"],
            port=5432
        )
    except Exception as e:
        print("DB Connection Error:", str(e))
        raise


# ==========================================================
# 2. JSON Encoder
# ==========================================================
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


# ==========================================================
# 3. Response Helpers
# ==========================================================
def success(message, data):
    return {
        "statusCode": 200,
        "body": json.dumps({"status": 200, "message": message, "data": data}, cls=DateTimeEncoder),
    }


def error(status, message):
    return {
        "statusCode": status,
        "body": json.dumps({"status": status, "message": message}),
    }


# ==========================================================
# 4. Fetch Recent Jira Issues
# ==========================================================
def fetch_jira_issues(cursor, from_date, to_date):
    cursor.execute(
        """
        SELECT id, issue_id, title, status, assignee, created_at AS timestamp, raw
        FROM jira_issues
        WHERE created_at BETWEEN %s AND %s
        ORDER BY created_at DESC;
        """,
        (from_date, to_date),
    )
    return [
        {**dict(r), "source": "jira_issue"}
        for r in cursor.fetchall()
    ]


# ==========================================================
# 5. Recent Jira Subtasks
# ==========================================================
def fetch_jira_subtasks(cursor, from_date, to_date):
    cursor.execute(
        """
        SELECT id, subtask_id, parent_issue_id, summary, status,
               timestamp, raw
        FROM jira_subtasks
        WHERE timestamp BETWEEN %s AND %s
        ORDER BY timestamp DESC;
        """,
        (from_date, to_date),
    )
    return [
        {**dict(r), "source": "jira_subtask"}
        for r in cursor.fetchall()
    ]


# ==========================================================
# 6. Recent Sprint Events
# ==========================================================
def fetch_jira_sprints(cursor, from_date, to_date):
    cursor.execute(
        """
        SELECT id, sprint_id, name, state, event_type,
               timestamp, raw
        FROM jira_sprints
        WHERE timestamp BETWEEN %s AND %s
        ORDER BY timestamp DESC;
        """,
        (from_date, to_date),
    )
    return [
        {**dict(r), "source": "jira_sprint"}
        for r in cursor.fetchall()
    ]


# ==========================================================
# 7. Recent GitHub Events (Commits)
# ==========================================================
def fetch_github_events(cursor, from_date, to_date):
    cursor.execute(
        """
        SELECT id, github_id, repo, commit_sha, author_email,
               message, timestamp, raw
        FROM github_events
        WHERE timestamp BETWEEN %s AND %s
        ORDER BY timestamp DESC;
        """,
        (from_date, to_date),
    )
    return [
        {**dict(r), "source": "github_event"}
        for r in cursor.fetchall()
    ]


# ==========================================================
# 8. Recent GitHub Pull Requests
# ==========================================================
def fetch_pull_requests(cursor, from_date, to_date):
    cursor.execute(
        """
        SELECT id, github_id, repo, pr_number, title,
               action, state, author_login,
               timestamp, raw
        FROM pull_requests
        WHERE timestamp BETWEEN %s AND %s
        ORDER BY timestamp DESC;
        """,
        (from_date, to_date),
    )
    return [
        {**dict(r), "source": "pull_request"}
        for r in cursor.fetchall()
    ]


# ==========================================================
# 9. Recent GitHub Issues
# ==========================================================
def fetch_github_issues(cursor, from_date, to_date):
    cursor.execute(
        """
        SELECT id, github_id, repo, issue_number,
               title, body, action, author_login,
               timestamp, raw
        FROM issues
        WHERE timestamp BETWEEN %s AND %s
        ORDER BY timestamp DESC;
        """,
        (from_date, to_date),
    )
    return [
        {**dict(r), "source": "github_issue"}
        for r in cursor.fetchall()
    ]


# ==========================================================
# 10. Recent GitHub Issue Comments
# ==========================================================
def fetch_issue_comments(cursor, from_date, to_date):
    cursor.execute(
        """
        SELECT id, github_id, repo, issue_number,
               comment_body, action, author_login,
               timestamp, raw
        FROM issue_comments
        WHERE timestamp BETWEEN %s AND %s
        ORDER BY timestamp DESC;
        """,
        (from_date, to_date),
    )
    return [
        {**dict(r), "source": "issue_comment"}
        for r in cursor.fetchall()
    ]


# ==========================================================
# 11. Recent Activity Logs
# ==========================================================
def fetch_activity_logs(cursor, from_date, to_date):
    cursor.execute(
        """
        SELECT log_id AS id, event_type, description,
               user_id, created_at AS timestamp
        FROM activity_logs
        WHERE created_at BETWEEN %s AND %s
        ORDER BY created_at DESC;
        """,
        (from_date, to_date),
    )
    return [
        {**dict(r), "source": "activity_log"}
        for r in cursor.fetchall()
    ]


# ==========================================================
# 12. Main Lambda Handler
# ==========================================================
def lambda_handler(event, context):
    print("EVENT:", json.dumps(event))

    try:
        query = event.get("queryStringParameters") or {}

        from_date = query.get("from_date")
        to_date = query.get("to_date")

        if not from_date or not to_date:
            return error(400, "from_date and to_date are required")

        conn = get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        all_events = []

        all_events += fetch_jira_issues(cursor, from_date, to_date)
        all_events += fetch_jira_subtasks(cursor, from_date, to_date)
        all_events += fetch_jira_sprints(cursor, from_date, to_date)
        all_events += fetch_github_events(cursor, from_date, to_date)
        all_events += fetch_pull_requests(cursor, from_date, to_date)
        all_events += fetch_github_issues(cursor, from_date, to_date)
        all_events += fetch_issue_comments(cursor, from_date, to_date)
        all_events += fetch_activity_logs(cursor, from_date, to_date)

        # Sort all events DESC by timestamp
        all_events = sorted(all_events, key=lambda x: x.get("timestamp"), reverse=True)

        cursor.close()
        conn.close()

        return success("Recent activity fetched successfully", all_events)

    except Exception as e:
        print("ERROR:", str(e))
        return error(500, f"Internal server error: {str(e)}")
