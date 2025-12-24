# sprint_insights/app.py

import os
import json
import psycopg2
import psycopg2.extras


def get_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dbname=os.environ["DB_NAME"],
        port=int(os.environ.get("DB_PORT", 5432))
    )


def response_ok(data):
    return {
        "statusCode": 200,
        "body": json.dumps({"status": 200, "data": data}, default=str)
    }


def percent_change(current, previous):
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100, 1)


def lambda_handler(event, context):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        # ------------------------------------------------
        # 1. Current Sprint
        # ------------------------------------------------
        cur.execute("""
            SELECT sprint_id, start_date, end_date, name
            FROM jira_sprints
            WHERE state = 'active'
            ORDER BY start_date DESC
            LIMIT 1
        """)
        current = cur.fetchone()

        if not current:
            return response_ok({"message": "No active sprint found"})

        # ------------------------------------------------
        # 2. Previous Sprint
        # ------------------------------------------------
        cur.execute("""
            SELECT sprint_id, start_date, end_date
            FROM jira_sprints
            WHERE state = 'closed'
            ORDER BY end_date DESC
            LIMIT 1
        """)
        previous = cur.fetchone()

        # Prepare sprint JSON once (KEY FIX)
        current_sprint_json = f'[{{"id": {current["sprint_id"]}}}]'
        previous_sprint_json = (
            f'[{{"id": {previous["sprint_id"]}}}]' if previous else None
        )

        # ------------------------------------------------
        # 3. Jira Ticket Counts
        # ------------------------------------------------
        cur.execute("""
            SELECT COUNT(*) AS cnt
            FROM jira_issues
            WHERE raw->'fields'->'customfield_10020' @> %s::jsonb
        """, (current_sprint_json,))
        current_jira = cur.fetchone()["cnt"]

        if previous:
            cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM jira_issues
                WHERE raw->'fields'->'customfield_10020' @> %s::jsonb
            """, (previous_sprint_json,))
            previous_jira = cur.fetchone()["cnt"]
        else:
            previous_jira = 0

        # ------------------------------------------------
        # 4. High Priority – No Recent Activity (3 days)
        # ------------------------------------------------
        cur.execute("""
            SELECT COUNT(*) AS cnt
            FROM jira_issues
            WHERE priority ILIKE 'high%'
              AND updated_at < NOW() - INTERVAL '3 days'
              AND raw->'fields'->'customfield_10020' @> %s::jsonb
        """, (current_sprint_json,))
        high_priority_stale = cur.fetchone()["cnt"]

        # ------------------------------------------------
        # 5. Commits
        # ------------------------------------------------
        cur.execute("""
            SELECT COUNT(*) AS cnt
            FROM github_events
            WHERE commit_sha IS NOT NULL
              AND timestamp BETWEEN %s AND %s
        """, (current["start_date"], current["end_date"]))
        current_commits = cur.fetchone()["cnt"]

        if previous:
            cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM github_events
                WHERE commit_sha IS NOT NULL
                  AND timestamp BETWEEN %s AND %s
            """, (previous["start_date"], previous["end_date"]))
            previous_commits = cur.fetchone()["cnt"]
        else:
            previous_commits = 0

        # ------------------------------------------------
        # 6. Pull Requests
        # ------------------------------------------------
        cur.execute("""
            SELECT COUNT(*) AS cnt
            FROM pull_requests
            WHERE timestamp BETWEEN %s AND %s
        """, (current["start_date"], current["end_date"]))
        current_prs = cur.fetchone()["cnt"]

        if previous:
            cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM pull_requests
                WHERE timestamp BETWEEN %s AND %s
            """, (previous["start_date"], previous["end_date"]))
            previous_prs = cur.fetchone()["cnt"]
        else:
            previous_prs = 0

        # ------------------------------------------------
        # 7. Incidents (not implemented yet)
        # ------------------------------------------------
        current_incidents = 0
        previous_incidents = 0

        # ------------------------------------------------
        # Final Response
        # ------------------------------------------------
        data = {
            "sprint": {
                "id": current["sprint_id"],
                "name": current["name"],
                "start_date": current["start_date"],
                "end_date": current["end_date"]
            },
            "metrics": {
                "jira_tickets": {
                    "count": current_jira,
                    "percent_change": percent_change(current_jira, previous_jira)
                },
                "high_priority_no_activity": {
                    "count": high_priority_stale
                },
                "commits": {
                    "count": current_commits,
                    "percent_change": percent_change(current_commits, previous_commits)
                },
                "pull_requests": {
                    "count": current_prs,
                    "percent_change": percent_change(current_prs, previous_prs)
                },
                "incidents": {
                    "count": current_incidents,
                    "percent_change": percent_change(
                        current_incidents, previous_incidents
                    )
                }
            }
        }

        return response_ok(data)

    finally:
        cur.close()
        conn.close()
