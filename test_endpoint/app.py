import os
import json
import datetime
import pymysql
import requests
from collections import deque

def lambda_handler(event, context):
    # Access environment variables
    db_host = os.environ.get("DB_HOST")
    db_user = os.environ.get("DB_USER")
    db_password = os.environ.get("DB_PASSWORD")
    db_name = os.environ.get("DB_NAME")
    db_port = os.environ.get("DB_PORT")

    # Print them (these will appear in CloudWatch logs)
    print("DB_HOST:", db_host)
    print("DB_USER:", db_user)
    print("DB_PASSWORD:", "[HIDDEN]")  # avoid printing sensitive info
    print("DB_NAME:", db_name)
    print("DB_PORT:", db_port)

    # Return them in response if needed (optional, avoid sending passwords in response)
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "hello there",
            "DB_HOST": db_host,
            "DB_USER": db_user,
            "DB_NAME": db_name,
            "DB_PORT": db_port
        }),
    }
