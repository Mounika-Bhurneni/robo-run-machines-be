import json
import flask
from flask import jsonify, request
from flask_restx import Api, Namespace, Resource, fields
from aws_lambda_wsgi import response as wsgi_response
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import ClientError
import requests

# -----------------------------
# Flask app & RESTX API setup
# -----------------------------
app = flask.Flask(__name__)

authorizations = {
    "BearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Enter your Bearer token here"
    }
}

api = Api(
    app,
    version="1.0",
    title="LMS API Endpoints ",
    description="Swagger for AWS Lambda function",
    authorizations=authorizations,
    security="apikey"
)

swagger_ns = Namespace("", description="Cognito Proxy Namespace")
api.add_namespace(swagger_ns)

# -----------------------------
# API Keys
# -----------------------------
API_KEYS = ["my-secret-api-key"]

def require_api_key(func):
    def wrapper(*args, **kwargs):
        api_key = request.headers.get("X-API-KEY")
        if not api_key or api_key not in API_KEYS:
            return jsonify({"message": "Unauthorized"}), 401
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

def require_bearer_auth(func):
    """
    Accepts only Authorization: Bearer <token>
    """
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            if token:  # optionally validate token here
                return func(*args, **kwargs)
        return jsonify({"message": "Unauthorized"}), 401
    wrapper.__name__ = func.__name__
    return wrapper



# -----------------------------
# Swagger model for Cognito request
# -----------------------------
@swagger_ns.route("/auth/login")
class AuthLogin(Resource):
    @swagger_ns.expect(
        swagger_ns.model(
            "AuthLoginModel",
            {
                "email": fields.String(required=True, description="User email"),
                "password": fields.String(required=True, description="User password")
            }
        )
    )
    def post(self):
        body = request.json

        # Required fields
        required_fields = ["email", "password"]
        for field in required_fields:
            if field not in body:
                return jsonify({"message": f"{field} is required"}), 400

        email = body["email"]
        password = body["password"]

        # ===== No middleware, no auth, no token checks =====
        # Add real DB check here if required
        # For now return a fixed success response

        response = {
            "message": "Login successful",
            "user": {
                "email": email,
                "role": "agent"
            },
            "access_token": "mock-jwt-token-123456",
            "token_type": "Bearer",
            "expires_in": 3600
        }

        return jsonify(response), 200



forgot_password_model = swagger_ns.model(
    "ForgotPasswordRequest",
    {
        "email": fields.String(
            required=True,
            example="swaroop.s@aithinkers.com",
            description="Email of the user requesting password reset"
        ),
    }
)

@swagger_ns.route("/forgotPassword")
class ForgotPassword(Resource):

    @swagger_ns.expect(forgot_password_model)
    def post(self):
        body = request.json

        email = body.get("email")
        if not email:
            return jsonify({"message": "email is required"}), 400

        # ===== Mocked Response =====
        response = {
            "email": email,
            "status": "Reset link sent successfully",
            "timestamp": "2025-12-11T16:45:00Z"
        }

        return jsonify(response), 200


confirm_forgot_password_model = swagger_ns.model(
    "ConfirmForgotPasswordRequest",
    {
        "email": fields.String(
            required=True,
            example="krishna.aithinkers@gmail.com",
            description="Email of the user"
        ),
        "otp": fields.String(
            required=True,
            example="048120",
            description="OTP received by the user"
        ),
        "new_password": fields.String(
            required=True,
            example="1NewSecurePassword456@",
            description="New password to set"
        ),
    }
)

@swagger_ns.route("/confirmForgotPassword")
class ConfirmForgotPassword(Resource):

    @swagger_ns.expect(confirm_forgot_password_model)
    def post(self):
        body = request.json

        email = body.get("email")
        otp = body.get("otp")
        new_password = body.get("new_password")

        # ===== Validation =====
        missing_fields = [f for f in ["email", "otp", "new_password"] if not body.get(f)]
        if missing_fields:
            return jsonify({"message": f"Missing fields: {', '.join(missing_fields)}"}), 400

        # ===== Mocked Response =====
        response = {
            "email": email,
            "status": "Password updated successfully",
            "timestamp": "2025-12-11T16:55:00Z"
        }

        return jsonify(response), 200


# -----------------------------
# Swagger JSON & UI
# -----------------------------
@app.route("/swagger/openapi.json")
def openapi():
    return jsonify(api.__schema__)

@app.route("/swagger/docs")
def docs():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Swagger UI</title>
        <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist/swagger-ui.css">
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://unpkg.com/swagger-ui-dist/swagger-ui-bundle.js"></script>
        <script src="https://unpkg.com/swagger-ui-dist/swagger-ui-standalone-preset.js"></script>
        <script>
            window.onload = () => {
                SwaggerUIBundle({
                    url: "/swagger/openapi.json",
                    dom_id: "#swagger-ui",
                    presets: [
                        SwaggerUIBundle.presets.apis,
                        SwaggerUIStandalonePreset
                    ],
                    requestInterceptor: (req) => {
                        req.headers['X-API-KEY'] = 'my-secret-api-key';

                        // Read from UI "Authorize" section or custom inputs
                        const accessKey = document.getElementById('x-aws-access-key')?.value;
                        const secretKey = document.getElementById('x-aws-secret-key')?.value;
                        const region = document.getElementById('x-aws-region')?.value;

                        if (accessKey) req.headers['x-aws-access-key'] = accessKey;
                        if (secretKey) req.headers['x-aws-secret-key'] = secretKey;
                        if (region) req.headers['x-aws-region'] = region;

                        return req;
                    }
                });
            };
        </script>

    </body>
    </html>
    """
    return html, 200, {"Content-Type": "text/html"}

# -----------------------------
# Lambda adapter
# -----------------------------
def convert_http_api_event(event):
    http = event["requestContext"]["http"]
    return {
        "httpMethod": http["method"],
        "path": event.get("rawPath", http.get("path", "/")),
        "headers": event.get("headers", {}),
        "multiValueHeaders": {},
        "queryStringParameters": event.get("queryStringParameters", {}),
        "body": event.get("body", None),
        "isBase64Encoded": event.get("isBase64Encoded", False)
    }

def lambda_handler(event, context):
    if isinstance(event, dict) and event.get("version") == "2.0":
        event = convert_http_api_event(event)
    return wsgi_response(app, event, context)
