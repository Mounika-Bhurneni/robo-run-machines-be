import json
import os
import requests

COMPOSIO_API_KEY = os.environ.get("COMPOSIO_API_KEY")
BASE_URL = os.environ.get("COMPOSIO_BASE_URL", "https://api.composio.dev")

HEADERS = {
    "Authorization": f"Bearer {COMPOSIO_API_KEY}",
    "Content-Type": "application/json"
}

def fetch_user_profile():
    url = f"{BASE_URL}/v1/user/profile"
    res = requests.get(url, headers=HEADERS)
    res.raise_for_status()
    return res.json()

def fetch_user_projects():
    url = f"{BASE_URL}/v1/projects"
    res = requests.get(url, headers=HEADERS)
    res.raise_for_status()
    return res.json()

def fetch_user_prs():
    url = f"{BASE_URL}/v1/integrations/github/prs"
    res = requests.get(url, headers=HEADERS)
    res.raise_for_status()
    return res.json()

def fetch_user_issues():
    url = f"{BASE_URL}/v1/integrations/jira/issues"
    res = requests.get(url, headers=HEADERS)
    res.raise_for_status()
    return res.json()

def lambda_handler(event, context):
    try:
        profile = fetch_user_profile()
        projects = fetch_user_projects()
        prs = fetch_user_prs()
        issues = fetch_user_issues()

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "User Composio data fetched successfully",
                "profile": profile,
                "projects": projects,
                "prs": prs,
                "issues": issues
            }, indent=2)
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
