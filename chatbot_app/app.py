import os
import json
import requests

# ===============================
# Config
# ===============================
BASE_API_URL = os.environ.get(
    "BASE_API_URL",
    "http://host.docker.internal:3000"
)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

# ===============================
# Fetch Risk Insights (WORKING API)
# ===============================
def fetch_risk_insights():
    resp = requests.get(
        f"{BASE_API_URL}/analytics/risk",
        timeout=5
    )
    resp.raise_for_status()
    return resp.json()

# ===============================
# AI Summarization (ONLY THIS IS AI)
# ===============================
def summarize_with_ai(risk_data):
    if not OPENAI_API_KEY:
        return "AI summarization is not configured."

    prompt = f"""
You are an engineering manager assistant.

Summarize the sprint health based ONLY on the data below.
Be concise (2–4 sentences).
Do not invent anything.

Data:
{json.dumps(risk_data, indent=2)}
"""

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 120,
        "temperature": 0.2
    }

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        OPENAI_URL,
        headers=headers,
        json=payload,
        timeout=8   # 🔴 HARD STOP — prevents hangs
    )

    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()

# ===============================
# Lambda Handler
# ===============================
def lambda_handler(event, context):
    try:
        risk_data = fetch_risk_insights()
        summary = summarize_with_ai(risk_data)

        return {
            "statusCode": 200,
            "body": json.dumps({
                "summary": summary,
                "source": "risk_insights"
            })
        }

    except requests.exceptions.Timeout:
        return {
            "statusCode": 200,
            "body": json.dumps({
                "summary": "Sprint data retrieved, but AI summarization timed out.",
                "source": "risk_insights"
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e)
            })
        }
