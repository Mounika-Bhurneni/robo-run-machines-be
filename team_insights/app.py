import json
import os
import psycopg2
from datetime import datetime, timedelta
import re


def normalize_email_for_login(email: str) -> str:
    """
    krishna.mayekar@aithinkers.com → krishnamayekar
    """
    local = email.split("@")[0]
    return re.sub(r"[^a-z0-9]", "", local.lower())


# ==========================================================
# HELPERS
# ==========================================================
def percent_change(current, previous):
    if previous == 0:
        value = 100 if current > 0 else 0
    else:
        value = round(((current - previous) / previous) * 100, 2)
    return f"{value:+.2f}%"


# ==========================================================
# PostgreSQL Connection
# ==========================================================
def get_connection():
    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dbname=os.environ["DB_NAME"],
        port=5432
    )
    conn.autocommit = True
    return conn


# ==========================================================
# Lambda Handler
# ==========================================================
def lambda_handler(event, context):
    params = event.get("queryStringParameters") or {}

    org_id = params.get("org_id")
    user_id = params.get("user_id")
    email = params.get("email")

    insights = get_team_insights(
        org_id=org_id,
        user_id=user_id,
        email=email
    )

    return {
        "statusCode": 200,
        "body": json.dumps(insights, indent=2)
    }


# ==========================================================
# TEAM INSIGHTS LOGIC
# ==========================================================
def get_team_insights(org_id=None, user_id=None, email=None):
    conn = get_connection()
    cur = conn.cursor()

    filters = []
    values = []

    login_key = normalize_email_for_login(email) if email else None

    if org_id:
        filters.append("org_id = %s")
        values.append(org_id)

    if user_id:
        filters.append("assignee_user_id = %s")
        values.append(user_id)

    if email:
        filters.append("assignee_email = %s")
        values.append(email)

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
        ORDER BY COUNT(*) DESC
    """, values)

    insights["issues_per_user"] = [
        {"user": r[0], "total_issues": r[1]} for r in cur.fetchall()
    ]

    # ==========================================================
    # 2. COMPLETED TODAY
    # ==========================================================
    today = datetime.utcnow().date()

    cur.execute(f"""
        SELECT assignee_name, COUNT(*)
        FROM jira_issues
        {where_clause + (" AND" if where_clause else "WHERE")}
        status IN ('Done','Closed','Resolved')
        AND DATE(updated_at) = %s
        GROUP BY assignee_name
    """, values + [today])

    insights["completed_today"] = [
        {"user": r[0], "completed": r[1]} for r in cur.fetchall()
    ]

    # ==========================================================
    # 3. COMPLETED THIS WEEK
    # ==========================================================
    start_week = today - timedelta(days=today.weekday())

    cur.execute(f"""
        SELECT assignee_name, COUNT(*)
        FROM jira_issues
        {where_clause + (" AND" if where_clause else "WHERE")}
        status IN ('Done','Closed','Resolved')
        AND DATE(updated_at) >= %s
        GROUP BY assignee_name
    """, values + [start_week])

    insights["completed_week"] = [
        {"user": r[0], "completed": r[1]} for r in cur.fetchall()
    ]

    # ==========================================================
    # 4. PENDING VS COMPLETED
    # ==========================================================
    cur.execute(f"""
        SELECT
            SUM(CASE WHEN status IN ('Done','Closed','Resolved') THEN 1 ELSE 0 END),
            SUM(CASE WHEN status NOT IN ('Done','Closed','Resolved') THEN 1 ELSE 0 END)
        FROM jira_issues
        {where_clause}
    """, values)

    completed, pending = cur.fetchone()
    insights["pending_vs_completed"] = {
        "completed": completed or 0,
        "pending": pending or 0
    }

    # ==========================================================
    # 5. ACTIVE USERS (COMMENTS)
    # ==========================================================
    if email:
        cur.execute("""
            SELECT author_login, COUNT(*)
            FROM jira_issue_comments
            WHERE lower(author_login) LIKE %s
            GROUP BY author_login
            ORDER BY COUNT(*) DESC
        """, [f"%{login_key}%"])
    else:
        cur.execute("""
            SELECT author_login, COUNT(*)
            FROM jira_issue_comments
            GROUP BY author_login
            ORDER BY COUNT(*) DESC
            LIMIT 10
        """)

    insights["top_active_users"] = [
        {"user": r[0], "comments": r[1]} for r in cur.fetchall()
    ]

    # ==========================================================
    # 6. TEAM METRICS SUMMARY
    # ==========================================================
    now = datetime.utcnow()
    curr_start = now - timedelta(days=14)
    prev_start = now - timedelta(days=28)

    # Jira counts
    if email:
        cur.execute("""
            SELECT COUNT(*) FROM jira_issues
            WHERE updated_at >= %s AND assignee_email = %s
        """, [curr_start, email])
    else:
        cur.execute("""
            SELECT COUNT(*) FROM jira_issues
            WHERE updated_at >= %s
        """, [curr_start])
    curr_tickets = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM jira_issues
        WHERE updated_at BETWEEN %s AND %s
    """, [prev_start, curr_start])
    prev_tickets = cur.fetchone()[0]

    # Commits
    if email:
        cur.execute("""
            SELECT COUNT(*) FROM git_commits
            WHERE timestamp >= %s
            AND author_email = %s
        """, [curr_start, email])
    else:
        cur.execute("""
            SELECT COUNT(*) FROM git_commits
            WHERE timestamp >= %s
        """, [curr_start])

    curr_commits = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM git_commits
        WHERE timestamp BETWEEN %s AND %s
    """, [prev_start, curr_start])
    prev_commits = cur.fetchone()[0]

    insights["team_metrics_summary"] = {
        "total_jira_tickets": {
            "count": curr_tickets,
            "delta_percent": percent_change(curr_tickets, prev_tickets)
        },
        "commits_prs": {
            "count": curr_commits,
            "delta_percent": percent_change(curr_commits, prev_commits)
        }
    }

    cur.close()
    conn.close()
    return insights
