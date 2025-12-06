import json
import os
import psycopg2
from datetime import datetime

# ==========================================================
# PostgreSQL Connection
# ==========================================================
def get_connection():
    try:
        conn = psycopg2.connect(
            host=os.environ["DB_HOST"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            dbname=os.environ["DB_NAME"],
            port=5432
        )
        return conn
    except Exception as e:
        print("DB Connection Error:", str(e))
        raise

# ==========================================================
# Lambda Handler
# ==========================================================
def lambda_handler(event, context):
    print("Raw Event:", json.dumps(event))
    try:
        body = json.loads(event.get("body", "{}"))
        webhook_event = body.get("webhookEvent")
        issue = body.get("issue")
        comment = body.get("comment")
        changelog = body.get("changelog")
        sprint = body.get("sprint")
        worklog = body.get("worklog")

        print("Webhook Event:", webhook_event)

        # ---- ISSUE EVENTS ---- #
        if webhook_event == "jira:issue_created":
            handle_issue_created(issue)
        elif webhook_event == "jira:issue_updated":
            handle_issue_updated(issue, changelog)
        elif webhook_event == "jira:issue_deleted":
            handle_issue_deleted(issue)

        # ---- SPRINT EVENTS ---- #
        elif webhook_event in ["sprint_created", "sprint_updated", "sprint_deleted", "sprint_started", "sprint_closed"]:
            handle_sprint_events(webhook_event, sprint)

        # ---- COMMENT EVENTS ---- #
        elif webhook_event in ["comment_created", "comment_updated", "comment_deleted"]:
            handle_comment_events(webhook_event, issue, comment)

        # ---- VOTING/WATCHING ---- #
        elif webhook_event in ["issue_vote_changed", "issue_watch_changed"]:
            handle_vote_watch_events(webhook_event, issue)

        # ---- ISSUE LINKS ---- #
        elif webhook_event in ["issue_link_created", "issue_link_deleted"]:
            handle_issue_links(webhook_event, body)

        # ---- SUBTASKS ---- #
        elif webhook_event in ["subtask_created", "subtask_updated", "subtask_deleted"]:
            handle_subtask_events(webhook_event, issue)

        # ---- WORKLOG ---- #
        elif webhook_event in ["worklog_created", "worklog_updated", "worklog_deleted"]:
            handle_worklog_events(webhook_event, issue, worklog)

        # ---- TIMETRACKING PROVIDER ---- #
        elif webhook_event == "timetrackingprovider_update":
            handle_timetracking_provider(body)

        # ---- FEATURE TOGGLE ---- #
        elif webhook_event in ["feature_flag_enabled", "feature_flag_disabled"]:
            handle_feature_toggle(webhook_event, body)

        else:
            print("Unhandled event:", webhook_event)

        return {"statusCode": 200, "body": json.dumps({"message": "Webhook received"})}

    except Exception as e:
        print("Error:", str(e))
        return {"statusCode": 500, "body": json.dumps({"error": "Internal server error"})}


# ==========================================================
# ISSUE HANDLERS
# ==========================================================

def handle_issue_created(issue):
    import json
    from datetime import datetime

    print("Issue created:", json.dumps(issue))
    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        fields = issue.get("fields", {})

        # --- Fetch org_id ---
        org = fields.get("organization")
        if org and org.get("id"):
            org_id = str(org.get("id"))
        else:
            project = fields.get("project")
            org_id = str(project.get("id")) if project and project.get("id") else None

        # --- Fetch assignee ---
        assignee = fields.get("assignee")
        assignee_id = assignee.get("id") or assignee.get("accountId") if assignee else None
        assignee_name = assignee.get("displayName") if assignee else None

        # --- Fetch reporter ---
        reporter = fields.get("reporter")
        reporter_id = reporter.get("id") or reporter.get("accountId") if reporter else None
        reporter_name = reporter.get("displayName") if reporter else None

        # --- Other fields ---
        status = fields.get("status", {}).get("name") if fields.get("status") else None
        priority = fields.get("priority", {}).get("name") if fields.get("priority") else None
        components = json.dumps(fields.get("components") or [])

        sql = """
            INSERT INTO jira_issues (
                id, issue_key, org_id, assignee_user_id, reporter_user_id,
                assignee_name, reporter_name,
                status, priority, component, updated_at, raw
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (issue_key) DO UPDATE
            SET status = EXCLUDED.status,
                priority = EXCLUDED.priority,
                assignee_user_id = EXCLUDED.assignee_user_id,
                reporter_user_id = EXCLUDED.reporter_user_id,
                assignee_name = EXCLUDED.assignee_name,
                reporter_name = EXCLUDED.reporter_name,
                component = EXCLUDED.component,
                updated_at = EXCLUDED.updated_at,
                raw = EXCLUDED.raw
        """

        cur.execute(sql, (
            str(issue.get("id")),
            issue.get("key"),
            org_id,
            assignee_id,
            reporter_id,
            assignee_name,
            reporter_name,
            status,
            priority,
            components,
            datetime.utcnow(),
            json.dumps(issue)
        ))

        conn.commit()
        print(f"Issue {issue.get('key')} inserted/updated.")

    except Exception as e:
        print("Error in handle_issue_created:", str(e))
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def handle_issue_updated(issue, changelog):
    print("Issue updated:", json.dumps(issue))
    handle_issue_created(issue)  # same logic as create


def handle_issue_deleted(issue):
    print("Issue deleted:", json.dumps(issue))
    try:
        conn = get_connection()
        cur = conn.cursor()
        sql = "DELETE FROM jira_issues WHERE issue_key = %s"
        cur.execute(sql, (issue.get("key"),))
        conn.commit()
        cur.close()
        conn.close()
        print(f"Issue {issue.get('key')} deleted.")
    except Exception as e:
        print("Error in handle_issue_deleted:", str(e))


# ==========================================================
# SPRINT HANDLER
# ==========================================================
def handle_sprint_events(event, sprint):
    print(f"Sprint event: {event}", json.dumps(sprint))
    # TODO: Insert/update sprint info into separate sprint table


# ==========================================================
# COMMENT HANDLER
# ==========================================================
def handle_comment_events(event, issue, comment):
    print(f"Comment event: {event}", json.dumps(comment))
    try:
        conn = get_connection()
        cur = conn.cursor()
        sql = """
            INSERT INTO jira_comments (
                id, issue_key, author_user_id, body, updated_at, raw
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET body = EXCLUDED.body,
                updated_at = EXCLUDED.updated_at,
                raw = EXCLUDED.raw
        """
        cur.execute(sql, (
            comment.get("id"),
            issue.get("key"),
            comment.get("author", {}).get("id"),
            comment.get("body"),
            datetime.utcnow(),
            json.dumps(comment)
        ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("Error in handle_comment_events:", str(e))


# ==========================================================
# VOTING / WATCH HANDLER
# ==========================================================
def handle_vote_watch_events(event, issue):
    print(f"Vote/Watch event: {event}", json.dumps(issue))
    # TODO: Update votes/watchers table


# ==========================================================
# ISSUE LINKS HANDLER
# ==========================================================
def handle_issue_links(event, body):
    print(f"Issue link event: {event}", json.dumps(body))
    # TODO: Insert/update issue_links table


# ==========================================================
# SUBTASK HANDLER
# ==========================================================
def handle_subtask_events(event, issue):
    print(f"Subtask event: {event}", json.dumps(issue))
    # TODO: Insert/update subtasks table


# ==========================================================
# WORKLOG HANDLER
# ==========================================================
def handle_worklog_events(event, issue, worklog):
    print(f"Worklog event: {event}", json.dumps(worklog))
    # TODO: Insert/update worklogs table


# ==========================================================
# TIMETRACKING PROVIDER
# ==========================================================
def handle_timetracking_provider(body):
    print("Timetracking provider update:", json.dumps(body))
    # TODO: Update timetracking provider info


# ==========================================================
# FEATURE TOGGLE
# ==========================================================
def handle_feature_toggle(event, body):
    print("Feature toggle event:", event, json.dumps(body))
    # TODO: Track feature toggle changes
