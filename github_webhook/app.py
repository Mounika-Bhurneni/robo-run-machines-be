import json
import hmac
import hashlib
import os
import base64

# -----------------------------------
# Validate Signature
# -----------------------------------
def verify_signature(event_body, headers):
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "my_super_secret_key")

    # API Gateway lowercases header names
    signature = headers.get("x-hub-signature-256", "")

    if not signature:
        print("❌ Missing signature header")
        return False

    mac = hmac.new(secret.encode(), msg=event_body.encode(), digestmod=hashlib.sha256)
    expected = f"sha256={mac.hexdigest()}"

    print("Expected signature:", expected)
    print("Received signature:", signature)

    return hmac.compare_digest(expected, signature)


# -----------------------------------
# Lambda Entry
# -----------------------------------
def lambda_handler(event, context):

    headers = event.get("headers", {})
    # Convert header keys to lowercase (API Gateway inconsistent sometimes)
    headers = {k.lower(): v for k, v in headers.items()}

    body = event.get("body", "")

    # Base64 decode if needed
    if event.get("isBase64Encoded", False):
        body = base64.b64decode(body).decode("utf-8")

    print("Body preview:", body[:300])

    # Validate GitHub Signature
    if not verify_signature(body, headers):
        return {
            "statusCode": 401,
            "body": json.dumps({"error": "Invalid GitHub signature"})
        }

    # Correct GitHub event header
    github_event = headers.get("x-github-event", "unknown")
    print("GitHub event received:", github_event)

    payload = json.loads(body)

    # -----------------------------------
    # Handle Events
    # -----------------------------------
    if github_event == "push":
        print("Push event:")
        print("Repo:", payload["repository"]["full_name"])
        print("Commits:", len(payload.get("commits", [])))

    elif github_event == "pull_request":
        print(f"PR #{payload['number']} {payload['action']}")

    elif github_event == "workflow_job":
        print("Workflow job event")
        print("Status:", payload["workflow_job"]["status"])
        print("Conclusion:", payload["workflow_job"]["conclusion"])

    elif github_event == "workflow_run":
        print("Workflow run:")
        print("Status:", payload["workflow_run"]["status"])
        print("Conclusion:", payload["workflow_run"]["conclusion"])

    else:
        print("Unhandled event:", github_event)

    # you can save to DB here...

    return {
        "statusCode": 200,
        "body": json.dumps({"message": f"Received {github_event}"})
    }
