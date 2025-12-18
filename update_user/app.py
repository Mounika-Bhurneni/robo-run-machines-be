import json
import boto3
import os
from datetime import datetime, date
import psycopg2

cognito = boto3.client("cognito-idp")
USER_POOL_ID = os.environ["USER_POOL_ID"]

ALLOWED_ROLES = ["DEV", "QA", "MANAGER", "DEV_MANAGER"]
ADMIN_ROLES = ["MANAGER", "DEV_MANAGER"]

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

# -------------------------------
# Custom Serializer
# -------------------------------
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

# ==========================================================
# Lambda Handler
# ==========================================================
def lambda_handler(event, context):
    try:
        # ------------------------------
        # Auth / RBAC
        # ------------------------------
        claims = event.get("requestContext", {}) \
                      .get("authorizer", {}) \
                      .get("jwt", {}) \
                      .get("claims", {})

        requester_role = claims.get("custom:role")

        if requester_role not in ADMIN_ROLES:
            return {
                "statusCode": 403,
                "body": json.dumps({"error": "Only managers can update users"})
            }

        # ------------------------------
        # Parse Input
        # ------------------------------
        body = json.loads(event.get("body", "{}"))

        email = body.get("email")
        role = body.get("role")
        org_id = body.get("org_id")
        skills = body.get("skills", [])

        if not email:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "email is required"})
            }

        if role and role not in ALLOWED_ROLES:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Invalid role: {role}"})
            }

        conn = get_connection()
        cur = conn.cursor()

        # ------------------------------
        # Fetch Existing User
        # ------------------------------
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        row = cur.fetchone()

        if not row:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "User not found"})
            }

        user_id = row[0]

        # ------------------------------
        # Validate Organization
        # ------------------------------
        if org_id:
            cur.execute("SELECT id FROM organizations WHERE id = %s", (org_id,))
            if not cur.fetchone():
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Invalid organization"})
                }

        # ------------------------------
        # Update User Table
        # ------------------------------
        cur.execute("""
            UPDATE users
            SET
                org_id = COALESCE(%s, org_id),
                role = COALESCE(%s, role)
            WHERE id = %s
        """, (org_id, role, user_id))

        # ------------------------------
        # Update Cognito Role (if changed)
        # ------------------------------
        if role:
            cognito.admin_update_user_attributes(
                UserPoolId=USER_POOL_ID,
                Username=email,
                UserAttributes=[
                    {"Name": "custom:role", "Value": role}
                ]
            )

            # Remove from all role groups
            for r in ALLOWED_ROLES:
                try:
                    cognito.admin_remove_user_from_group(
                        UserPoolId=USER_POOL_ID,
                        Username=email,
                        GroupName=r
                    )
                except Exception:
                    pass

            # Add to new role group
            cognito.admin_add_user_to_group(
                UserPoolId=USER_POOL_ID,
                Username=email,
                GroupName=role
            )

        # ------------------------------
        # Update Skills (Replace)
        # ------------------------------
        if skills:
            # Delete existing skills
            cur.execute("DELETE FROM user_skills WHERE user_id = %s", (user_id,))

            for skill in skills:
                name = skill.get("name")
                proficiency = skill.get("proficiency", 3)

                # Upsert skill
                cur.execute("""
                    INSERT INTO skills (name)
                    VALUES (%s)
                    ON CONFLICT (name) DO NOTHING
                    RETURNING id
                """, (name,))

                row = cur.fetchone()
                if row:
                    skill_id = row[0]
                else:
                    cur.execute("SELECT id FROM skills WHERE name = %s", (name,))
                    skill_id = cur.fetchone()[0]

                cur.execute("""
                    INSERT INTO user_skills (user_id, skill_id, proficiency)
                    VALUES (%s, %s, %s)
                """, (user_id, skill_id, proficiency))

        conn.commit()
        cur.close()
        conn.close()

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "User updated successfully",
                "user_id": str(user_id)
            }, cls=DateTimeEncoder)
        }

    except Exception as e:
        print("ERROR:", str(e))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}, cls=DateTimeEncoder)
        }
