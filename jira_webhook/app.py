import json
import os
import psycopg2
from datetime import datetime
import uuid


import requests
from requests.auth import HTTPBasicAuth

def get_jira_user_email(account_id):
    url = f"https://praveenreddygopidi.atlassian.net/rest/api/3/user?accountId={account_id}"
    auth = HTTPBasicAuth(os.environ["JIRA_USER"], os.environ["JIRA_API_TOKEN"])

    headers = {"Accept": "application/json"}
    response = requests.get(url, headers=headers, auth=auth)
    if response.status_code == 200:
        return response.json().get("emailAddress")
    else:
        print("Failed to fetch email for", account_id)
        return None

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
            author_login = body.get("user", {}).get("displayName")
            handle_issue_links(webhook_event, body, author_login=author_login)


        # ---- SUBTASKS ---- #
        elif webhook_event in ["subtask_created", "subtask_updated", "subtask_deleted"]:
            board_id = body.get("issue", {}).get("originBoardId")  # optional
            issue_data = body.get("issue")
            author_login = body.get("user", {}).get("displayName")
            handle_subtask_events(webhook_event, issue_data, board_id=board_id, author_login=author_login)



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
        assignee_email =  get_jira_user_email(assignee_id)


        # --- Fetch reporter ---
        reporter = fields.get("reporter")
        reporter_id = reporter.get("id") or reporter.get("accountId") if reporter else None
        reporter_name = reporter.get("displayName") if reporter else None
        reporter_email =  get_jira_user_email(reporter_id)


        # --- Other fields ---
        status = fields.get("status", {}).get("name") if fields.get("status") else None
        priority = fields.get("priority", {}).get("name") if fields.get("priority") else None
        components = json.dumps(fields.get("components") or [])

        print("Assignee email:===>", assignee_email)
        print("Reporter email:====>", reporter_email)


        sql = """
            INSERT INTO jira_issues (
                id, issue_key, org_id, 
                assignee_user_id, assignee_name, assignee_email,
                reporter_user_id, reporter_name, reporter_email,
                status, priority, component, updated_at, raw
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (issue_key)
            DO UPDATE SET
                assignee_user_id = EXCLUDED.assignee_user_id,
                assignee_name = EXCLUDED.assignee_name,
                assignee_email = EXCLUDED.assignee_email,
                reporter_user_id = EXCLUDED.reporter_user_id,
                reporter_name = EXCLUDED.reporter_name,
                reporter_email = EXCLUDED.reporter_email,
                status = EXCLUDED.status,
                priority = EXCLUDED.priority,
                component = EXCLUDED.component,
                updated_at = EXCLUDED.updated_at,
                raw = EXCLUDED.raw
        """

        cur.execute(sql, (
            str(issue.get("id")),
            issue.get("key"),
            org_id,

            assignee_id,
            assignee_name,
            assignee_email,

            reporter_id,
            reporter_name,
            reporter_email,

            status,
            priority,
            components,
            datetime.utcnow(),
            json.dumps(issue)
        ))

        conn.commit()
        print(f"Issue {issue.get('key')} created/updated with email addresses.")

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
def handle_sprint_events(event_type, sprint, repo_or_board_id=None, author_login=None):
    try:
        conn = get_connection()
        cur = conn.cursor()
        event_uuid = str(uuid.uuid4())
        timestamp = datetime.utcnow()

        sql = """
            INSERT INTO jira_sprints
            (id, sprint_id, repo_or_board_id, name, state, start_date, end_date, goal, event_type, author_login, timestamp, raw)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (sprint_id, event_type)
            DO UPDATE SET
                name = EXCLUDED.name,
                state = EXCLUDED.state,
                start_date = EXCLUDED.start_date,
                end_date = EXCLUDED.end_date,
                goal = EXCLUDED.goal,
                author_login = EXCLUDED.author_login,
                timestamp = EXCLUDED.timestamp,
                raw = EXCLUDED.raw
        """

        cur.execute(sql, (
            event_uuid,
            sprint["id"],
            repo_or_board_id,
            sprint.get("name"),
            sprint.get("state"),
            sprint.get("startDate"),
            sprint.get("endDate"),
            sprint.get("goal"),
            event_type,
            author_login,
            timestamp,
            json.dumps(sprint)
        ))

        conn.commit()
        cur.close()
        conn.close()
        print(f"Sprint event '{event_type}' recorded successfully.")

    except Exception as e:
        print(f"Error recording sprint event '{event_type}':", str(e))


# ==========================================================
# COMMENT HANDLER
# ==========================================================
def handle_comment_events(event_type, issue, comment, board_id=None, author_login=None):
    try:
        conn = get_connection()
        cur = conn.cursor()
        event_uuid = str(uuid.uuid4())
        timestamp = datetime.utcnow()

        sql = """
            INSERT INTO jira_issue_comments
            (id, comment_id, issue_id, board_id, comment_body, event_type, author_login, timestamp, raw)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (comment_id, event_type)
            DO UPDATE SET
                comment_body = EXCLUDED.comment_body,
                author_login = EXCLUDED.author_login,
                timestamp = EXCLUDED.timestamp,
                raw = EXCLUDED.raw
        """

        cur.execute(sql, (
            event_uuid,
            comment["id"],
            issue["id"],
            board_id,
            comment.get("body"),
            event_type,
            author_login,
            timestamp,
            json.dumps(comment)
        ))

        conn.commit()
        cur.close()
        conn.close()
        print(f"Comment event '{event_type}' recorded successfully.")

    except Exception as e:
        print(f"Error recording comment event '{event_type}':", str(e))


# ==========================================================
# VOTING / WATCH HANDLER
# ==========================================================
def handle_vote_watch_events(event_type, issue, board_id=None, author_login=None):
    try:
        conn = get_connection()
        cur = conn.cursor()
        event_uuid = str(uuid.uuid4())
        timestamp = datetime.utcnow()

        total_votes = issue.get("votes", {}).get("votes", 0)
        total_watchers = issue.get("watches", {}).get("watchCount", 0)

        sql = """
            INSERT INTO jira_issue_votes_watches
            (id, issue_id, board_id, event_type, total_votes, total_watchers, author_login, timestamp, raw)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (issue_id, event_type)
            DO UPDATE SET
                total_votes = EXCLUDED.total_votes,
                total_watchers = EXCLUDED.total_watchers,
                author_login = EXCLUDED.author_login,
                timestamp = EXCLUDED.timestamp,
                raw = EXCLUDED.raw
        """

        cur.execute(sql, (
            event_uuid,
            issue["id"],
            board_id,
            event_type,
            total_votes,
            total_watchers,
            author_login,
            timestamp,
            json.dumps(issue)
        ))

        conn.commit()
        cur.close()
        conn.close()
        print(f"Vote/Watch event '{event_type}' recorded successfully.")

    except Exception as e:
        print(f"Error recording Vote/Watch event '{event_type}':", str(e))



# ==========================================================
# ISSUE LINKS HANDLER
# ==========================================================
def handle_issue_links(event_type, payload, author_login=None):
    try:
        conn = get_connection()
        cur = conn.cursor()
        event_uuid = str(uuid.uuid4())
        timestamp = datetime.utcnow()

        link = payload["issueLink"]
        source_issue_id = link["source"]["id"]
        target_issue_id = link["destination"]["id"]
        link_type = link["type"]["name"]
        link_id = link["id"]

        sql = """
            INSERT INTO jira_issue_links
            (id, link_id, source_issue_id, target_issue_id, link_type, event_type, author_login, timestamp, raw)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (link_id, event_type)
            DO UPDATE SET
                source_issue_id = EXCLUDED.source_issue_id,
                target_issue_id = EXCLUDED.target_issue_id,
                link_type = EXCLUDED.link_type,
                author_login = EXCLUDED.author_login,
                timestamp = EXCLUDED.timestamp,
                raw = EXCLUDED.raw
        """

        cur.execute(sql, (
            event_uuid,
            link_id,
            source_issue_id,
            target_issue_id,
            link_type,
            event_type,
            author_login,
            timestamp,
            json.dumps(link)
        ))

        conn.commit()
        cur.close()
        conn.close()
        print(f"Issue link event '{event_type}' recorded successfully.")

    except Exception as e:
        print(f"Error recording issue link event '{event_type}':", str(e))



# ==========================================================
# SUBTASK HANDLER
# ==========================================================
def handle_subtask_events(event_type, issue, board_id=None, author_login=None):
    try:
        conn = get_connection()
        cur = conn.cursor()
        event_uuid = str(uuid.uuid4())
        timestamp = datetime.utcnow()

        subtask_id = issue["id"]
        parent_issue_id = issue.get("parent", {}).get("id")
        summary = issue.get("fields", {}).get("summary")
        status = issue.get("fields", {}).get("status", {}).get("name")

        sql = """
            INSERT INTO jira_subtasks
            (id, subtask_id, parent_issue_id, board_id, summary, status, event_type, author_login, timestamp, raw)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (subtask_id, event_type)
            DO UPDATE SET
                summary = EXCLUDED.summary,
                status = EXCLUDED.status,
                author_login = EXCLUDED.author_login,
                timestamp = EXCLUDED.timestamp,
                raw = EXCLUDED.raw
        """

        cur.execute(sql, (
            event_uuid,
            subtask_id,
            parent_issue_id,
            board_id,
            summary,
            status,
            event_type,
            author_login,
            timestamp,
            json.dumps(issue)
        ))

        conn.commit()
        cur.close()
        conn.close()
        print(f"Subtask event '{event_type}' recorded successfully.")

    except Exception as e:
        print(f"Error recording subtask event '{event_type}':", str(e))



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
