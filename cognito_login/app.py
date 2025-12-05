import json
import boto3
import os
import base64
import hmac
import hashlib

cognito = boto3.client("cognito-idp")

USER_POOL_ID = os.environ["USER_POOL_ID"]
CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")  # optional


# Helper to compute SECRET_HASH
def calculate_secret_hash(username):
    if not CLIENT_SECRET:
        return None

    message = bytes(username + CLIENT_ID, "utf-8")
    key = bytes(CLIENT_SECRET, "utf-8")

    secret_hash = base64.b64encode(
        hmac.new(key, message, digestmod=hashlib.sha256).digest()
    ).decode()

    return secret_hash


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        email = body.get("email")
        password = body.get("password")

        if not email or not password:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Email and password required"})
            }

        params = {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": CLIENT_ID,
            "AuthParameters": {
                "USERNAME": email,
                "PASSWORD": password,
            }
        }

        # If app client has a secret → add SECRET_HASH
        if CLIENT_SECRET:
            params["AuthParameters"]["SECRET_HASH"] = calculate_secret_hash(email)

        response = cognito.initiate_auth(**params)

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Login successful",
                "auth_result": response["AuthenticationResult"]
            },indent=2)
        }

    except cognito.exceptions.NotAuthorizedException:
        return {
            "statusCode": 401,
            "body": json.dumps({"error": "Invalid username/password"})
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
