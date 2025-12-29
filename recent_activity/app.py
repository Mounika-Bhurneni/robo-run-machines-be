import os
import json
import psycopg2
import psycopg2.extras
from datetime import datetime
import pytz  # make sure this is installed
import re

JIRA_REGEX = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")

def extract_jira_ticket(message):
    if not message:
        return None
    match = JIRA_REGEX.search(message)
    return match.group(0) if match else None


def infer_commit_type(message):
    if not message:
        return "Other"

    msg = message.lower()

    if any(k in msg for k in ["fix", "bug", "hotfix", "patch"]):
        return "Bugfix"
    if any(k in msg for k in ["feat", "feature", "add", "implement"]):
        return "Feature"
    if any(k in msg for k in ["refactor", "cleanup", "optimize"]):
        return "Refactor"
    if any(k in msg for k in ["test", "spec", "coverage"]):
        return "Test"

    return "Other"


def commit_message_quality(message):
    if not message:
        return "Needs Improvement"

    words = message.strip().split()

    if len(words) < 4:
        return "Needs Improvement"

    if message[0].islower():
        return "Needs Improvement"

    return "Clear"


def is_pr_linked(commit_sha, pull_requests):
    return any(pr.get("raw", {}).get("head", {}).get("sha") == commit_sha
               for pr in pull_requests)


def get_ci_status(raw):
    return raw.get("ci_status", "unknown")

def get_cd_status(raw):
    return raw.get("cd_status", "unknown")


def build_commit_cards(commits, pull_requests):
    cards = []

    for c in commits:
        msg = c.get("message")

        cards.append({
            "commit_id": c.get("commit_sha"),
            "timestamp": c.get("timestamp"),
            "author": c.get("author_email"),
            "commit_message": msg,
            "jira_ticket_id": extract_jira_ticket(msg),
            "branch_name": c.get("raw", {}).get("ref"),
            "pr_linked": is_pr_linked(c.get("commit_sha"), pull_requests),
            "ci_status": get_ci_status(c.get("raw", {})),
            "cd_status": get_cd_status(c.get("raw", {})),
            "derived_intelligence": {
                "commit_type": infer_commit_type(msg),
                "commit_message_quality": commit_message_quality(msg)
            }
        })

    return cards


from datetime import datetime, date, timezone

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


def make_aware(dt):
    """Convert naive datetime to UTC-aware."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ==========================
# Helper to parse query params
# ==========================
def parse_date(date_str):
    """Convert date string to UTC timezone-aware datetime."""
    dt = datetime.fromisoformat(date_str)
    return dt.astimezone(pytz.UTC)


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
        "body": json.dumps({"status": 200, "message": message, "data": data}, cls=DateTimeEncoder,indent=2),
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
        SELECT 
            id,
            issue_key AS issue_id,
            assignee_name AS assignee,
            reporter_name AS reporter,
            status,
            priority,
            updated_at AS timestamp,
            raw
        FROM jira_issues
        WHERE updated_at BETWEEN %s AND %s
        ORDER BY updated_at DESC;
        """,
        (from_date, to_date),
    )
    return [
        {**dict(r), "source": "jira_issue", "timestamp": make_aware(r["timestamp"])}
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
        {**dict(r), "source": "jira_subtask", "timestamp": make_aware(r["timestamp"])}
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
        {**dict(r), "source": "jira_sprint", "timestamp": make_aware(r["timestamp"])}
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
        {**dict(r), "source": "github_event", "timestamp": make_aware(r["timestamp"])}
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
        
        {**dict(r), "source": "pull_request", "timestamp": make_aware(r["timestamp"])}
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
        {**dict(r), "source": "github_issue", "timestamp": make_aware(r["timestamp"])}
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
        
        {**dict(r), "source": "issue_comment", "timestamp": make_aware(r["timestamp"])}
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
        {**dict(r), "source": "activity_log", "timestamp": make_aware(r["timestamp"])}
        for r in cursor.fetchall()
    ]


# ==========================================================
# 12. Main Lambda Handler
# ==========================================================
def lambda_handler(event, context):
    print("EVENT:", json.dumps(event))

    try:
        query = event.get("queryStringParameters") or {}
        from_date_str = query.get("from_date")
        to_date_str = query.get("to_date")

        from_date = parse_date(from_date_str)
        to_date = parse_date(to_date_str)

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
        # all_events += fetch_activity_logs(cursor, from_date, to_date)

        # Sort all events DESC by timestamp
        all_events = sorted(all_events, key=lambda x: x.get("timestamp"), reverse=True)

        commit_cards = build_commit_cards(
            fetch_github_events(cursor, from_date, to_date),
            fetch_pull_requests(cursor, from_date, to_date)
        )


        cursor.close()
        conn.close()
        return success("Current work snapshot", commit_cards)

        # return success("Recent activity fetched successfully", all_events)

    except Exception as e:
        print("ERROR:", str(e))
        return error(500, f"Internal server error: {str(e)}")
