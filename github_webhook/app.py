import json
import hmac
import hashlib
import os
import base64
import uuid
from datetime import datetime
import psycopg2
import psycopg2.extras

# ==========================================================
# 1. PostgreSQL Connection.   
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
# 2. GitHub Signature Validation
# ==========================================================
def verify_signature(event_body, headers):
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    signature = headers.get("x-hub-signature-256", "")

    if not signature:
        print("❌ Missing signature header x-hub-signature-256")
        return False

    mac = hmac.new(secret.encode(), msg=event_body.encode(), digestmod=hashlib.sha256)
    expected = f"sha256={mac.hexdigest()}"
    print("Expected signature:", expected)
    print("Received signature:", signature)
    return hmac.compare_digest(expected, signature)

# ==========================================================
# 3. Lambda Handler with Upserts
# ==========================================================
def lambda_handler(event, context):
    headers = {k.lower(): v for k, v in event.get("headers", {}).items()}
    body = event.get("body", "")
    if event.get("isBase64Encoded", False):
        body = base64.b64decode(body).decode("utf-8")

    print("Body preview:", body[:300])
    if not verify_signature(body, headers):
        return {"statusCode": 401, "body": json.dumps({"error": "Invalid GitHub signature"})}

    github_event = headers.get("x-github-event", "unknown")
    print("GitHub Event:", github_event)
    payload = json.loads(body)

    try:
        conn = get_connection()
        cur = conn.cursor()

        try:
            repo = payload["repository"]["full_name"]
            timestamp = datetime.utcnow()

            # Helper function to upsert
            def upsert_record(github_id, author_email, message, commit_sha=None, files=[]):
                event_uuid = str(uuid.uuid4())
                sql = """
                    INSERT INTO github_events
                    (id, github_id, repo, commit_sha, author_email, message, files, timestamp, raw)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (github_id, repo)
                    DO UPDATE SET
                        commit_sha = EXCLUDED.commit_sha,
                        author_email = EXCLUDED.author_email,
                        message = EXCLUDED.message,
                        files = EXCLUDED.files,
                        timestamp = EXCLUDED.timestamp,
                        raw = EXCLUDED.raw
                """
                cur.execute(sql, (
                    event_uuid,
                    github_id,
                    repo,
                    commit_sha,
                    author_email,
                    message,
                    json.dumps(files),
                    timestamp,
                    json.dumps(payload)
                ))

            if github_event == "push":
                for c in payload.get("commits", []):
                    github_id = c["id"]
                    author_email = c["author"]["email"]
                    message = c["message"]
                    files = c.get("modified", []) + c.get("added", []) + c.get("removed", [])
                    upsert_record(github_id, author_email, message, commit_sha=github_id, files=files)
                print("Push commits upserted successfully.")

            elif github_event == "pull_request":
                pr = payload
                github_id = pr["pull_request"]["id"]
                author_email = pr["pull_request"]["user"]["login"]
                message = f"PR {pr['action']}: {pr['pull_request']['title']}"
                upsert_record(github_id, author_email, message, commit_sha=pr["pull_request"]["head"]["sha"])

            elif github_event == "issues":
                issue = payload["issue"]
                github_id = issue["id"]
                author_email = issue["user"]["login"]
                message = f"Issue {payload['action']}: {issue['title']}"
                upsert_record(github_id, author_email, message)

            elif github_event == "issue_comment":
                comment = payload["comment"]
                github_id = comment["id"]
                author_email = comment["user"]["login"]
                message = f"Comment {payload['action']}: {comment['body']}"
                upsert_record(github_id, author_email, message)

            elif github_event == "workflow_run":
                run = payload["workflow_run"]
                github_id = run["id"]
                author_email = run["head_repository"]["owner"]["login"]
                message = f"Workflow run {run['name']} → {run['status']} / {run.get('conclusion')}"
                upsert_record(github_id, author_email, message, commit_sha=run.get("head_sha"))

            elif github_event == "workflow_job":
                job = payload["workflow_job"]
                github_id = job["id"]
                author_email = job["run_url"]
                message = f"Workflow job {job['name']} → {job['status']} / {job.get('conclusion')}"
                upsert_record(github_id, author_email, message, commit_sha=job.get("head_sha"))

            elif github_event == "release":
                release = payload["release"]
                github_id = release["id"]
                author_email = release["author"]["login"]
                message = f"Release {release['tag_name']} → {payload['action']}"
                upsert_record(github_id, author_email, message)

            elif github_event == "star":
                star = payload
                github_id = star["sender"]["id"]
                author_email = star["sender"]["login"]
                message = f"Repo starred → {payload['action']}"
                upsert_record(github_id, author_email, message)

            elif github_event == "fork":
                fork = payload["forkee"]
                github_id = fork["id"]
                author_email = fork["owner"]["login"]
                message = f"Repo forked → {payload['action']}"
                upsert_record(github_id, author_email, message)

            else:
                print("Unhandled GitHub event:", github_event)

        except Exception as event_error:
            print(f"Error processing {github_event} event:", str(event_error))

        finally:
            conn.commit()
            cur.close()
            conn.close()

    except Exception as e:
        print("Error handling event:", str(e))
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

    return {"statusCode": 200, "body": json.dumps({"message": f"Received {github_event}"})}
