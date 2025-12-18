import json
import os
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# ==========================================================
# PostgreSQL Connection
# ==========================================================
def get_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dbname=os.environ["DB_NAME"],
        port=5432
    )

# ==========================================================
# Lambda Handler
# ==========================================================
def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        question = body.get("question")

        if not question:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "question is required"})
            }

        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # --------------------------------------------------
        # 1️⃣ Resolve User (name/email fuzzy match)
        # --------------------------------------------------
        cur.execute("""
            SELECT id, email, display_name
            FROM users
            WHERE
                LOWER(display_name) LIKE %s
                OR LOWER(email) LIKE %s
            LIMIT 1
        """, (f"%{question.lower()}%", f"%{question.lower()}%"))

        user = cur.fetchone()
        if not user:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "User not found"})
            }

        user_id = user["id"]

        since = datetime.utcnow() - timedelta(days=7)

        # --------------------------------------------------
        # 2️⃣ Git Commits
        # --------------------------------------------------
        cur.execute("""
            SELECT repo, commit_sha, message, files, timestamp
            FROM git_commits
            WHERE author_user_id = %s
              AND timestamp >= %s
            ORDER BY timestamp DESC
            LIMIT 20
        """, (user_id, since))
        commits = cur.fetchall()

        # --------------------------------------------------
        # 3️⃣ Jira Issues
        # --------------------------------------------------
        cur.execute("""
            SELECT issue_key, status, priority, updated_at
            FROM jira_issues
            WHERE assignee_user_id = %s
            ORDER BY updated_at DESC
            LIMIT 20
        """, (str(user_id),))
        issues = cur.fetchall()

        # --------------------------------------------------
        # 4️⃣ Jira Subtasks
        # --------------------------------------------------
        cur.execute("""
            SELECT summary, status, timestamp
            FROM jira_subtasks
            WHERE author_login = %s
            ORDER BY timestamp DESC
            LIMIT 20
        """, (user["email"],))
        subtasks = cur.fetchall()

        cur.close()
        conn.close()

        # --------------------------------------------------
        # 5️⃣ Send to OpenAI
        # --------------------------------------------------
        prompt = f"""
            You are an engineering manager assistant.

            User: {user['display_name']} ({user['email']})

            Git commits (last 7 days):
            {json.dumps(commits, indent=2, default=str)}

            Jira issues:
            {json.dumps(issues, indent=2, default=str)}

            Jira subtasks:
            {json.dumps(subtasks, indent=2, default=str)}

            Question:
            {question}

            Answer in clear, concise bullet points.
            """

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Summarize developer activity clearly."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )

        answer = response.choices[0].message.content

        return {
            "statusCode": 200,
            "body": json.dumps({
                "user": user,
                "answer": answer
            })
        }

    except Exception as e:
        print("ERROR:", str(e))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
