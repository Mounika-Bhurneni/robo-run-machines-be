import json
import os
import psycopg2
from datetime import datetime, timedelta

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
    print("Incoming Event:", json.dumps(event))

    try:
        params = event.get("queryStringParameters") or {}
        org_id = params.get("org_id")
        user_id = params.get("user_id")  # optional filter

        insights = get_team_insights(org_id=org_id, user_id=user_id)

        return {
            "statusCode": 200,
            "body": json.dumps(insights)
        }

    except Exception as e:
        print("Error:", str(e))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"})
        }


# ==========================================================
# TEAM INSIGHTS LOGIC
# ==========================================================
def get_team_insights(org_id=None, user_id=None):
    conn = get_connection()
    cur = conn.cursor()

    filters = []
    values = []

    if org_id:
        filters.append("org_id = %s")
        values.append(org_id)

    if user_id:
        filters.append("assignee_user_id = %s")
        values.append(user_id)

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    insights = {}

    # ==========================================================
    # 1. TOTAL ISSUES PER USER
    # ==========================================================
    cur.execute(f"""
        SELECT assignee_name, COUNT(*)
        FROM jira_issues
        {where_clause}
        GROUP BY assignee_name
        ORDER BY COUNT(*) DESC;
    """, values)

    insights["issues_per_user"] = [
        {"user": row[0], "total_issues": row[1]} for row in cur.fetchall()
    ]

    # ==========================================================
    # 2. ISSUES COMPLETED TODAY
    # ==========================================================
    today = datetime.utcnow().date()

    cur.execute(f"""
        SELECT assignee_name, COUNT(*)
        FROM jira_issues
        {where_clause + (" AND" if where_clause else "WHERE")}
            status IN ('Done', 'Closed', 'Resolved')
            AND DATE(updated_at) = %s
        GROUP BY assignee_name;
    """, values + [today])

    insights["completed_today"] = [
        {"user": row[0], "completed": row[1]} for row in cur.fetchall()
    ]

    # ==========================================================
    # 3. ISSUES COMPLETED THIS WEEK
    # ==========================================================
    start_week = today - timedelta(days=today.weekday())

    cur.execute(f"""
        SELECT assignee_name, COUNT(*)
        FROM jira_issues
        {where_clause + (" AND" if where_clause else "WHERE")}
            status IN ('Done', 'Closed', 'Resolved')
            AND DATE(updated_at) >= %s
        GROUP BY assignee_name;
    """, values + [start_week])

    insights["completed_week"] = [
        {"user": row[0], "completed": row[1]} for row in cur.fetchall()
    ]

    # ==========================================================
    # 4. PENDING VS COMPLETED
    # ==========================================================
    cur.execute(f"""
        SELECT
            SUM(CASE WHEN status IN ('Done','Closed','Resolved') THEN 1 ELSE 0 END) AS completed,
            SUM(CASE WHEN status NOT IN ('Done','Closed','Resolved') THEN 1 ELSE 0 END) AS pending
        FROM jira_issues
        {where_clause};
    """, values)

    row = cur.fetchone()
    insights["pending_vs_completed"] = {
        "completed": row[0] or 0,
        "pending": row[1] or 0
    }

    # ==========================================================
    # 5. ACTIVE USERS BASED ON COMMENTS
    # ==========================================================
    cur.execute("""
        SELECT author_login, COUNT(*)
        FROM jira_issue_comments
        GROUP BY author_login
        ORDER BY COUNT(*) DESC
        LIMIT 10;
    """)

    insights["top_active_users"] = [
        {"user": row[0], "comments": row[1]} for row in cur.fetchall()
    ]

    # ==========================================================
    # 6. SPRINT LOAD (issues assigned per sprint)
    # ==========================================================
    cur.execute("""
        SELECT sprint_id, COUNT(*)
        FROM jira_sprints
        GROUP BY sprint_id
        ORDER BY COUNT(*) DESC;
    """)

    insights["sprint_load"] = [
        {"sprint_id": row[0], "total_events": row[1]} for row in cur.fetchall()
    ]

    # ==========================================================
    # 7. AVERAGE RESOLUTION TIME (if you store created/resolved)
    # ==========================================================
    try:
        cur.execute(f"""
            SELECT AVG(EXTRACT(EPOCH FROM (updated_at - TO_TIMESTAMP((raw::json->'fields'->>'created'), 'YYYY-MM-DD"T"HH24:MI:SS"Z"'))))
            FROM jira_issues
            {where_clause}
            AND status IN ('Done', 'Closed', 'Resolved');
        """, values)

        avg_secs = cur.fetchone()[0]
        insights["avg_resolution_time_hours"] = round(avg_secs / 3600, 2) if avg_secs else 0
    except:
        insights["avg_resolution_time_hours"] = "created_at not parsable"

    # ==========================================================
    # Cleanup
    # ==========================================================
    cur.close()
    conn.close()

    return insights
