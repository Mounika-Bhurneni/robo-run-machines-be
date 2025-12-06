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
# 1. PostgreSQL Connection
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
# 3. Lambda Handler
# ==========================================================
def lambda_handler(event, context):
    # Normalize headers
    headers = {k.lower(): v for k, v in event.get("headers", {}).items()}

    # Decode body
    body = event.get("body", "")
    if event.get("isBase64Encoded", False):
        body = base64.b64decode(body).decode("utf-8")

    print("Body preview:", body[:300])

    # Verify GitHub signature
    if not verify_signature(body, headers):
        return {"statusCode": 401, "body": json.dumps({"error": "Invalid GitHub signature"})}

    github_event = headers.get("x-github-event", "unknown")
    print("GitHub Event:", github_event)

    payload = json.loads(body)

    try:
        conn = get_connection()
        cur = conn.cursor()

        try:
            # Handle each GitHub event type safely
            if github_event == "push":
                repo = payload["repository"]["full_name"]
                commits = payload.get("commits", [])
                print(f"Push event → {len(commits)} commits. ")

                for c in commits:
                    commit_id = str(uuid.uuid4())
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
                        json.dumps(files),
                        timestamp,
                        json.dumps(c)
                    ))
                print("Push commits inserted successfully.")

            elif github_event == "pull_request":
                pr = payload
                event_id = str(uuid.uuid4())
                repo = pr["repository"]["full_name"]
                commit_sha = pr["pull_request"]["head"]["sha"]
                author_email = pr["pull_request"]["user"]["login"]
                message = pr["pull_request"]["title"]
                files = []
                timestamp = datetime.utcnow()

                sql = """
                    INSERT INTO github_events 
                    (id, repo, commit_sha, author_email, message, files, timestamp, raw)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                cur.execute(sql, (
                    event_id,
                    repo,
                    commit_sha,
                    author_email,
                    f"PR {pr['action']}: {message}",
                    json.dumps(files),
                    timestamp,
                    json.dumps(pr)
                ))
                print(f"Pull Request event inserted: #{pr['number']} → {pr['action']}")

        # ======================================================
        # ISSUES
        # ======================================================
            elif github_event == "issues":
                issue = payload
                event_id = str(uuid.uuid4())
                repo = issue["repository"]["full_name"]
                commit_sha = None
                author_email = issue["issue"]["user"]["login"]
                message = issue["issue"]["title"]
                files = []
                timestamp = datetime.utcnow()

                sql = """
                    INSERT INTO github_events 
                    (id, repo, commit_sha, author_email, message, files, timestamp, raw)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                cur.execute(sql, (
                    event_id,
                    repo,
                    commit_sha,
                    author_email,
                    f"Issue {issue['action']}: {message}",
                    json.dumps(files),
                    timestamp,
                    json.dumps(issue)
                ))
                print(f"Issue event inserted: #{issue['issue']['number']} → {issue['action']}")

            # ======================================================
            # ISSUE COMMENT
            # ======================================================
            elif github_event == "issue_comment":
                comment = payload
                event_id = str(uuid.uuid4())
                repo = comment["repository"]["full_name"]
                commit_sha = None
                author_email = comment["comment"]["user"]["login"]
                message = comment["comment"]["body"]
                files = []
                timestamp = datetime.utcnow()

                sql = """
                    INSERT INTO github_events 
                    (id, repo, commit_sha, author_email, message, files, timestamp, raw)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                cur.execute(sql, (
                    event_id,
                    repo,
                    commit_sha,
                    author_email,
                    f"Comment {comment['action']}: {message}",
                    json.dumps(files),
                    timestamp,
                    json.dumps(comment)
                ))
                print(f"Issue comment inserted: Issue #{comment['issue']['number']}")

            # ======================================================
            # WORKFLOW RUN
            # ======================================================
            elif github_event == "workflow_run":
                run = payload["workflow_run"]
                event_id = str(uuid.uuid4())
                repo = payload["repository"]["full_name"]
                commit_sha = run.get("head_sha")
                author_email = run["head_repository"]["owner"]["login"]
                message = f"Workflow run {run['name']} → {run['status']} / {run.get('conclusion')}"
                files = []
                timestamp = datetime.utcnow()

                sql = """
                    INSERT INTO github_events 
                    (id, repo, commit_sha, author_email, message, files, timestamp, raw)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                cur.execute(sql, (
                    event_id,
                    repo,
                    commit_sha,
                    author_email,
                    message,
                    json.dumps(files),
                    timestamp,
                    json.dumps(payload)
                ))
                print(f"Workflow run event inserted: {run['name']}")

            # ======================================================
            # WORKFLOW JOB
            # ======================================================
            elif github_event == "workflow_job":
                job = payload["workflow_job"]
                event_id = str(uuid.uuid4())
                repo = payload["repository"]["full_name"]
                commit_sha = job.get("head_sha")
                author_email = job["run_url"]
                message = f"Workflow job {job['name']} → {job['status']} / {job.get('conclusion')}"
                files = []
                timestamp = datetime.utcnow()

                sql = """
                    INSERT INTO github_events 
                    (id, repo, commit_sha, author_email, message, files, timestamp, raw)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                cur.execute(sql, (
                    event_id,
                    repo,
                    commit_sha,
                    author_email,
                    message,
                    json.dumps(files),
                    timestamp,
                    json.dumps(payload)
                ))
                print(f"Workflow job event inserted: {job['name']}")

            # ======================================================
            # RELEASE
            # ======================================================
            elif github_event == "release":
                release = payload["release"]
                event_id = str(uuid.uuid4())
                repo = payload["repository"]["full_name"]
                commit_sha = None
                author_email = release["author"]["login"]
                message = f"Release {release['tag_name']} → {payload['action']}"
                files = []
                timestamp = datetime.utcnow()

                sql = """
                    INSERT INTO github_events 
                    (id, repo, commit_sha, author_email, message, files, timestamp, raw)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                cur.execute(sql, (
                    event_id,
                    repo,
                    commit_sha,
                    author_email,
                    message,
                    json.dumps(files),
                    timestamp,
                    json.dumps(payload)
                ))
                print(f"Release event inserted: {release['tag_name']}")

            # ======================================================
            # STAR
            # ======================================================
            elif github_event == "star":
                star = payload
                event_id = str(uuid.uuid4())
                repo = payload["repository"]["full_name"]
                commit_sha = None
                author_email = star["sender"]["login"]
                message = f"Repo starred → {payload['action']}"
                files = []
                timestamp = datetime.utcnow()

                sql = """
                    INSERT INTO github_events 
                    (id, repo, commit_sha, author_email, message, files, timestamp, raw)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                cur.execute(sql, (
                    event_id,
                    repo,
                    commit_sha,
                    author_email,
                    message,
                    json.dumps(files),
                    timestamp,
                    json.dumps(payload)
                ))
                print(f"Star event inserted by {author_email}")

            # ======================================================
            # FORK
            # ======================================================
            elif github_event == "fork":
                fork = payload
                event_id = str(uuid.uuid4())
                repo = payload["repository"]["full_name"]
                commit_sha = None
                author_email = fork["forkee"]["owner"]["login"]
                message = f"Repo forked → {payload['action']}"
                files = []
                timestamp = datetime.utcnow()

                sql = """
                    INSERT INTO github_events 
                    (id, repo, commit_sha, author_email, message, files, timestamp, raw)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                cur.execute(sql, (
                    event_id,
                    repo,
                    commit_sha,
                    author_email,
                    message,
                    json.dumps(files),
                    timestamp,
                    json.dumps(payload)
                ))
                print(f"Fork event inserted by {author_email}")

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
