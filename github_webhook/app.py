import json
import hmac
import hashlib
import os
import base64
import uuid
from datetime import datetime

# ==========================================================
# 1. MySQL Connection (pymysql)
# ==========================================================
import pymysql

def get_connection():
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        port=3306,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )


# ==========================================================
# 2. GitHub Signature Validation
# ==========================================================
def verify_signature(event_body, headers):
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    signature = headers.get("x-hub-signature-256", "")

    if not signature:
        print("❌ Missing signature header x-hub-signature-256")
        return False

    mac = hmac.new(
        secret.encode(),
        msg=event_body.encode(),
        digestmod=hashlib.sha256
    )

    expected = f"sha256={mac.hexdigest()}"

    return hmac.compare_digest(expected, signature)


# ==========================================================
# 3. Lambda Handler
# ==========================================================
def lambda_handler(event, context):

    # Normalize headers to lowercase
    headers = {k.lower(): v for k, v in event.get("headers", {}).items()}

    # Handle body (base64 or plain)
    body = event.get("body", "")
    if event.get("isBase64Encoded", False):
        body = base64.b64decode(body).decode("utf-8")

    print("Body:", body[:200])

    # Verify GitHub Signature
    if not verify_signature(body, headers):
        return {
            "statusCode": 401,
            "body": json.dumps({"error": "Invalid GitHub signature"})
        }

    github_event = headers.get("x-github-event", "unknown")
    print("GitHub Event:", github_event)

    payload = json.loads(body)

    # ======================================================
    # 🔥 HANDLE PUSH EVENT
    # ======================================================
    if github_event == "push":
        repo = payload["repository"]["full_name"]
        commits = payload.get("commits", [])

        print(f"Push event received → {len(commits)} commits")

        if commits:
            conn = get_connection()
            cur = conn.cursor()

            for c in commits:

                commit_id = str(uuid.uuid4())  # MySQL → UUID stored as string
                commit_sha = c["id"]
                author_email = c["author"]["email"]
                message = c["message"]

                files = c.get("modified", []) + c.get("added", []) + c.get("removed", [])

                timestamp = datetime.utcnow()

                sql = """
                    INSERT INTO github_events 
                    (id, repo, commit_sha, author_email, message, files, timestamp, raw)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """

                cur.execute(sql, (
                    commit_id,
                    repo,
                    commit_sha,
                    author_email,
                    message,
                    json.dumps(files),     # store list as JSON
                    timestamp,
                    json.dumps(c)          # raw commit JSON
                ))

            cur.close()
            conn.close()
            print("Commits inserted into MySQL successfully.")

    # ======================================================
    # Other GitHub Events (log only)
    # ======================================================
    elif github_event == "pull_request":
        print(f"Pull Request #{payload['number']} → {payload['action']}")

    elif github_event == "workflow_job":
        print("Workflow Job Status:", payload["workflow_job"]["status"])

    elif github_event == "workflow_run":
        print("Workflow Run Status:", payload["workflow_run"]["status"])

    else:
        print("Unhandled GitHub Event:", github_event)

    return {
        "statusCode": 200,
        "body": json.dumps({"message": f"Received {github_event}"})
    }
