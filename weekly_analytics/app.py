import os
import json
import psycopg2
from datetime import datetime, timedelta

ALLOWED_ROLES = ["DEV", "QA", "MANAGER", "DEV_MANAGER"]

#Weekly Commit & PR Analytics 

def get_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dbname=os.environ["DB_NAME"],
    )

def lambda_handler(event, context):
    try:
        # ------------------------------------------------------------
        # Auth Validation (Cognito JWT already validated by API Gateway)
        # ------------------------------------------------------------
        claims = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {})
        role = claims.get("custom:role")
        if role not in ALLOWED_ROLES:
            return {
                "statusCode": 403,
                "body": json.dumps({"error": "Unauthorized role"})
            }

        # ------------------------------------------------------------
        # Time Window: Last 7 days
        # ------------------------------------------------------------
        now = datetime.utcnow()
        start_date = now - timedelta(days=7)

        conn = get_connection()
        cur = conn.cursor()

        # ------------------------------------------------------------
        # Commits Analytics
        # ------------------------------------------------------------
        commit_query = """
            SELECT 
                author_email,
                repo,
                COUNT(*) AS commit_count
            FROM github_events
            WHERE timestamp >= %s AND timestamp <= %s
              AND commit_sha IS NOT NULL
            GROUP BY author_email, repo
            ORDER BY commit_count DESC;
        """
        cur.execute(commit_query, (start_date, now))
        commit_rows = cur.fetchall()
        commits = [
            {"author_email": r[0], "repo": r[1], "commit_count": r[2]}
            for r in commit_rows
        ]

        # ------------------------------------------------------------
        # PR Analytics
        # ------------------------------------------------------------
        pr_query = """
            SELECT
                author_email,
                repo,
                COUNT(*) FILTER (WHERE message ILIKE '%pull request%open%') AS open_prs,
                COUNT(*) FILTER (WHERE message ILIKE '%pull request%closed%') AS closed_prs,
                COUNT(*) FILTER (WHERE message ILIKE '%pull request%merged%') AS merged_prs
            FROM github_events
            WHERE timestamp >= %s AND timestamp <= %s
              AND message ILIKE '%pull request%'
            GROUP BY author_email, repo
            ORDER BY merged_prs DESC;
        """
        cur.execute(pr_query, (start_date, now))
        pr_rows = cur.fetchall()
        pull_requests = [
            {"author_email": r[0], "repo": r[1], "open_prs": r[2], "closed_prs": r[3], "merged_prs": r[4]}
            for r in pr_rows
        ]

        cur.close()
        conn.close()

        # ------------------------------------------------------------
        # Response
        # ------------------------------------------------------------
        return {
            "statusCode": 200,
            "body": json.dumps({
                "range": {"from": start_date.isoformat(), "to": now.isoformat()},
                "commits": commits,
                "pull_requests": pull_requests
            })
        }

    except Exception as e:
        print("ERROR:", str(e))
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
