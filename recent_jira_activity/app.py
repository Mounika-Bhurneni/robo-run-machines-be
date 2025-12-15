import os
import json
import psycopg2

ALLOWED_ROLES = ["DEV", "QA", "MANAGER", "DEV_MANAGER"]

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
        claims = (
            event.get("requestContext", {})
            .get("authorizer", {})
            .get("jwt", {})
            .get("claims", {})
        )

        user_email = claims.get("email")
        user_role = claims.get("custom:role")

        if not user_role or user_role not in ALLOWED_ROLES:
            return {
                "statusCode": 403,
                "body": json.dumps({"error": "Access denied"})
            }

        conn = get_connection()
        cur = conn.cursor()

        # ================================================================
        # RECENT JIRA ACTIVITIES (Unified Feed)
        # ================================================================
        cur.execute("""
            SELECT
                'ISSUE' AS activity_type,
                issue_key AS reference_id,
                NULL AS issue_id,
                COALESCE(assignee_name, reporter_name) AS author,
                status AS summary,
                'ISSUE_UPDATED' AS event_type,
                updated_at AS timestamp
            FROM jira_issues

            UNION ALL

            SELECT
                'COMMENT' AS activity_type,
                comment_id::text AS reference_id,
                issue_id::text AS issue_id,
                author_login AS author,
                comment_body AS summary,
                event_type,
                timestamp
            FROM jira_issue_comments

            UNION ALL

            SELECT
                'LINK' AS activity_type,
                link_id::text AS reference_id,
                source_issue_id::text AS issue_id,
                author_login AS author,
                link_type AS summary,
                event_type,
                timestamp
            FROM jira_issue_links

            UNION ALL

            SELECT
                'SPRINT' AS activity_type,
                sprint_id::text AS reference_id,
                NULL AS issue_id,
                author_login AS author,
                name AS summary,
                event_type,
                timestamp
            FROM jira_sprints

            UNION ALL

            SELECT
                'SUBTASK' AS activity_type,
                subtask_id::text AS reference_id,
                parent_issue_id::text AS issue_id,
                author_login AS author,
                summary,
                event_type,
                timestamp
            FROM jira_subtasks

            ORDER BY timestamp DESC
            LIMIT 20
        """)

        jira_recent_activities = cur.fetchall()

        cur.close()
        conn.close()

        return {
            "statusCode": 200,
            "body": json.dumps({
                "jira_recent_activities": jira_recent_activities
            }, default=str)
        }

    except Exception as e:
        print("Error:", str(e))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
