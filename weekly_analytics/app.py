import os
import json
import psycopg2
from datetime import datetime, timedelta

ALLOWED_ROLES = ["DEV", "QA", "MANAGER", "DEV_MANAGER"]

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
        # Auth Validation
        # ------------------------------------------------------------
        claims = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {})
        role = claims.get("custom:role")
        if role not in ALLOWED_ROLES:
            return {"statusCode": 403, "body": json.dumps({"error": "Unauthorized role"})}

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
        # Pull Requests Analytics (from pull_requests table)
        # ------------------------------------------------------------
        pr_query = """
            SELECT 
                author_login,
                repo,
                COUNT(*) FILTER (WHERE state='open') AS open_prs,
                COUNT(*) FILTER (WHERE state='closed') AS closed_prs,
                COUNT(*) FILTER (WHERE merged=true) AS merged_prs
            FROM pull_requests
            WHERE timestamp >= %s AND timestamp <= %s
            GROUP BY author_login, repo
            ORDER BY merged_prs DESC;
        """
        cur.execute(pr_query, (start_date, now))
        pr_rows = cur.fetchall()

        pull_requests = [
            {
                "author_email": r[0],   # using author_login as "email" for display
                "repo": r[1],
                "open_prs": r[2] or 0,
                "closed_prs": r[3] or 0,
                "merged_prs": r[4] or 0
            }
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
            },indent=2)
        }

    except Exception as e:
        print("ERROR:", str(e))
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
