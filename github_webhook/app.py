import json
import hmac
import hashlib
import os
import base64

# Handles all GitHub events:
# push
# pull_request
# issues
# issue_comment
# workflow_run
# release
# stars
# forks

def verify_signature(event_body, headers):
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "my_super_secret_key")
    signature = headers.get("X-Hub-Signature-256", "")

    if not signature:
        return False

    mac = hmac.new(secret.encode(), msg=event_body.encode(), digestmod=hashlib.sha256)
    expected = f"sha256={mac.hexdigest()}"

    return hmac.compare_digest(expected, signature)


def lambda_handler(event, context):
    headers = event.get("headers", {})
    body = event.get("body", "")

    if event.get("isBase64Encoded", False):
        body = base64.b64decode(body).decode("utf-8")

    # Validate GitHub signature
    if not verify_signature(body, headers):
        return {
            "statusCode": 401,
            "body": json.dumps({"error": "Invalid GitHub signature"})
        }

    github_event = headers.get("X-GitHub-Event", "unknown")

    print(f"Received GitHub event: {github_event}")

    payload = json.loads(body)

    # ---------------------------------------------------------------------
    # Event handling
    # ---------------------------------------------------------------------
    if github_event == "push":
        print("Push event received:")
        print(f"Repo: {payload['repository']['full_name']}")
        print(f"Commits: {len(payload['commits'])}")

    elif github_event == "pull_request":
        action = payload["action"]
        number = payload["number"]
        print(f"Pull Request #{number} {action}")

    elif github_event == "issues":
        print(f"Issue #{payload['issue']['number']} {payload['action']}")

    elif github_event == "issue_comment":
        print(f"Comment on Issue #{payload['issue']['number']}: {payload['comment']['body']}")

    elif github_event == "workflow_run":
        print(f"Workflow run status: {payload['workflow_run']['conclusion']}")

    elif github_event == "release":
        print(f"Release published: {payload['release']['tag_name']}")

    elif github_event == "star":
        print("Repo starred")

    elif github_event == "fork":
        print("Repo forked")

    else:
        print("Unhandled GitHub event:", github_event)

    # 🚀 You can now INSERT into DB here exactly like your Jira webhook
    # db.save_github_event(...)

    return {
        "statusCode": 200,
        "body": json.dumps({"message": f"Received event {github_event}"})
    }
