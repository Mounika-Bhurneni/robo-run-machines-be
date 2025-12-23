import os
import json
import psycopg2
from datetime import datetime, timezone, timedelta

DB_HOST = os.environ.get("DB_HOST")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_NAME = os.environ.get("DB_NAME")

DONE_STATUSES = ("done", "closed", "resolved")
STORY_POINTS_FIELD = "customfield_10016"  # update if different

SPRINT_DAYS = 14
HISTORICAL_SPRINTS = 3

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME
    )

def calculate_load_label(assigned, avg):
    if avg == 0:
        return "🟢 Balanced"

    ratio = assigned / avg

    if ratio <= 1.10:
        return "🟢 Balanced"
    elif ratio <= 1.30:
        return "🟡 High"
    else:
        return "🔴 Overloaded"

def lambda_handler(event, context):
    conn = get_connection()
    cur = conn.cursor()

    now = datetime.now(timezone.utc)

    current_sprint_start = now - timedelta(days=SPRINT_DAYS)
    historical_start = now - timedelta(days=SPRINT_DAYS * HISTORICAL_SPRINTS)

    # Historical average (last 3 sprints)
    cur.execute(f"""
        SELECT
            assignee_user_id,
            assignee_name,
            MAX(raw->'fields'->'assignee'->>'emailAddress') AS assignee_email,
            COALESCE(
                AVG(
                    NULLIF((raw->'fields'->>'{STORY_POINTS_FIELD}'), '')::int
                ),
                0
            ) AS avg_points
        FROM jira_issues
        WHERE updated_at >= %s
        AND updated_at < %s
        GROUP BY assignee_user_id, assignee_name
    """, (historical_start, current_sprint_start))



    avg_map = {
    row[0]: {
            "name": row[1],
            "email": row[2],
            "avg_points": float(row[3])
        }
        for row in cur.fetchall()
    }



    # Current sprint assignment
    cur.execute(f"""
        SELECT
            assignee_user_id,
            assignee_name,
            MAX(assignee_email) AS assignee_email,
            COALESCE(
                SUM(
                    NULLIF((raw->'fields'->>'{STORY_POINTS_FIELD}'), '')::int
                ),
                0
            ) AS assigned_points,
            COUNT(*) FILTER (WHERE status NOT IN %s) AS open_issues,
            COUNT(*) FILTER (WHERE priority IN ('High', 'Critical')) AS high_priority,
            COUNT(*) FILTER (WHERE status = 'IN_REVIEW') AS prs_review
        FROM jira_issues
        WHERE updated_at >= %s
        GROUP BY assignee_user_id, assignee_name
    """, (DONE_STATUSES, current_sprint_start))



    sprint_data = cur.fetchall()

    # Subtasks
    cur.execute("""
        SELECT author_login, COUNT(*)
        FROM jira_subtasks
        WHERE status NOT IN %s
        GROUP BY author_login
    """, (DONE_STATUSES,))
    subtasks = dict(cur.fetchall())

    cur.close()
    conn.close()

    people = []
    overloaded_count = 0

    for user_id, name,email, assigned, open_issues, high_priority, prs_review in sprint_data:
        avg_points = avg_map.get(user_id, {}).get("avg_points", 0)
        load_label = calculate_load_label(assigned, avg_points)

        if load_label == "🔴 Overloaded":
            overloaded_count += 1

        people.append({
            "name": name,
            "email": email,
            "role": "Developer",
            "assigned_story_points": assigned,
            "avg_story_points_last_3_sprints": round(avg_points, 1),
            "load_label": load_label,
            "tooltip": "Load is based on assigned story points compared to historical sprint averages.",
            "focus_today": {
                "active_jira_tickets": open_issues,
                "high_priority_tickets": high_priority,
                "prs_awaiting_review": prs_review,
                "subtasks": subtasks.get(user_id, 0)
            }
        })

    response = {
        "sprint_load_overview": people,
        "summary": {
            "overloaded_count": f"{overloaded_count} overloaded" if overloaded_count > 0 else None
        },
        "ai_suggestion": "Consider redistributing 2 tasks from Mike to Emily to balance the team workload."
    }

    return {
        "statusCode": 200,
        "body": json.dumps(response, indent=2)
    }
