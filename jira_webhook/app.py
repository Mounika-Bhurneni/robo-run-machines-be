import json

def lambda_handler(event, context):
    print("Raw Event:", json.dumps(event))

    try:
        body = json.loads(event.get("body", "{}"))
        webhook_event = body.get("webhookEvent")
        issue = body.get("issue")
        comment = body.get("comment")
        changelog = body.get("changelog")
        sprint = body.get("sprint")

        print("Webhook Event:", webhook_event)

        # ---- EVENT DISPATCHER ---- #
        if webhook_event in ["jira:issue_created"]:
            handle_issue_created(issue)

        elif webhook_event in ["jira:issue_updated"]:
            handle_issue_updated(issue, changelog)

        elif webhook_event in ["jira:issue_deleted"]:
            handle_issue_deleted(issue)

        # ---------------- Sprint Events ---------------- #
        elif webhook_event in [
            "sprint_created",
            "sprint_deleted",
            "sprint_updated",
            "sprint_started",
            "sprint_closed"
        ]:
            handle_sprint_events(webhook_event, sprint)

        # ---------------- Comment Events ---------------- #
        elif webhook_event in ["comment_created"]:
            handle_comment_created(issue, comment)

        elif webhook_event in ["comment_updated"]:
            handle_comment_updated(issue, comment)

        elif webhook_event in ["comment_deleted"]:
            handle_comment_deleted(issue, comment)

        # ---------------- Voting / Watching ---------------- #
        elif webhook_event in ["issue_vote_changed"]:
            handle_issue_vote_changed(issue)

        elif webhook_event in ["issue_watch_changed"]:
            handle_issue_watch_changed(issue)

        # ---------------- Issue Links ---------------- #
        elif webhook_event in ["issue_link_created", "issue_link_deleted"]:
            handle_issue_links(webhook_event, body)

        # ---------------- Subtasks ---------------- #
        elif webhook_event in ["subtask_created", "subtask_updated", "subtask_deleted"]:
            handle_subtask_events(webhook_event, issue)

        # ---------------- Time Tracking ---------------- #
        elif webhook_event in ["worklog_created", "worklog_updated", "worklog_deleted"]:
            handle_time_tracking(webhook_event, issue, body.get("worklog"))

        elif webhook_event in ["timetrackingprovider_update"]:
            handle_timetracking_provider(body)

        # ---------------- Feature status change ---------------- #
        elif webhook_event in ["feature_flag_enabled", "feature_flag_disabled"]:
            handle_feature_toggle(webhook_event, body)

        else:
            print("Unhandled event:", webhook_event)

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Webhook received"})
        }

    except Exception as e:
        print("Error:", str(e))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"})
        }



# ======================================================
# HANDLERS FOR ALL EVENTS
# ======================================================

def handle_issue_created(issue):
    print("Issue created:", json.dumps(issue))
    # TODO: Insert into DB


def handle_issue_updated(issue, changelog):
    print("Issue updated:", json.dumps(issue))
    print("Changelog:", json.dumps(changelog))
    # TODO: Update DB record


def handle_issue_deleted(issue):
    print("Issue deleted:", json.dumps(issue))
    # TODO: Delete from DB



# ---------- Sprint Events ---------- #

def handle_sprint_events(event, sprint):
    print(f"Sprint event: {event}", json.dumps(sprint))
    # TODO: Store sprint changes in DB



# ---------- Comments ---------- #

def handle_comment_created(issue, comment):
    print("Comment created:", json.dumps(comment))
    # TODO: Insert comment into DB

def handle_comment_updated(issue, comment):
    print("Comment updated:", json.dumps(comment))
    # TODO: Update comment in DB

def handle_comment_deleted(issue, comment):
    print("Comment deleted:", json.dumps(comment))
    # TODO: Delete comment from DB



# ---------- Votes / Watches ---------- #

def handle_issue_vote_changed(issue):
    print("Vote changed:", issue["id"])
    # TODO: Update vote counter

def handle_issue_watch_changed(issue):
    print("Watch changed:", issue["id"])
    # TODO: Update watchers list



# ---------- Issue Links ---------- #
def handle_issue_links(event, body):
    print("Issue link event:", event)
    print("Body:", json.dumps(body))
    # TODO: Store link relation



# ---------- Subtasks ---------- #
def handle_subtask_events(event, issue):
    print("Subtask event:", event)
    print("Issue:", json.dumps(issue))
    # TODO: Update/insert subtask info



# ---------- Time Tracking ---------- #

def handle_time_tracking(event, issue, worklog):
    print("Time tracking event:", event)
    print("Worklog:", json.dumps(worklog))
    # TODO: Insert/update time log


def handle_timetracking_provider(body):
    print("Provider updated:", json.dumps(body))
    # TODO: Update provider info



# ---------- Feature toggles ---------- #

def handle_feature_toggle(event, body):
    print("Feature toggle:", event)
    print("Body:", json.dumps(body))
    # TODO: Track feature toggle
