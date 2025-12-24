import os
import json
import requests
from openai import OpenAI
from datetime import datetime, date

from api_registry import API_REGISTRY
from db_query_registry import DB_QUERY_REGISTRY
from db_client import run_safe_query

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
GLOBAL_TIMEOUT = 35


def safe_json(obj):
    def default(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return str(o)

    return json.dumps(obj, indent=2, default=default)


def generate_summary_logic():
    snapshot = {}
    failures = 0

    # -------------------------
    # API DATA SOURCES
    # -------------------------
    for api_name, api_url in API_REGISTRY.items():
        try:
            resp = requests.get(api_url, timeout=GLOBAL_TIMEOUT)
            resp.raise_for_status()
            snapshot[api_name] = resp.json()
        except Exception:
            failures += 1
            continue

    # -------------------------
    # DB DATA SOURCES
    # -------------------------
    for query_name, sql in DB_QUERY_REGISTRY.items():
        try:
            snapshot[f"db::{query_name}"] = run_safe_query(sql)
        except Exception:
            failures += 1
            continue

    # -------------------------
    # CONFIDENCE
    # -------------------------
    total_sources = len(API_REGISTRY) + len(DB_QUERY_REGISTRY)
    confidence = max(60, int((1 - failures / total_sources) * 100))

    # -------------------------
    # PROMPT
    # -------------------------
    prompt = f"""
You are generating an engineering summary for leadership.

GOAL:
Highlight only the most important sprint and team risks.
Focus on patterns and concentrations, not individual repetition.

Use ONLY the provided data.
Do NOT invent information.

====================
SUMMARY
====================
Write 4–5 bullet points total.

Rules:
- Each bullet must start with a dot (.)
- Combine similar findings into ONE point
- Do NOT create separate bullets for the same type of issue
- Mention multiple names in a single point if they belong to the same pattern
- Focus on:
  - workload concentration
  - sprint delivery risk
  - backlog size
  - blocked or stale work
- Omit low-impact or normal conditions

====================
RECOMMENDATIONS
====================
Write exactly 3 recommendations.

Rules:
- Each recommendation must address a DIFFERENT problem
- Do NOT repeat recommendations that solve the same issue
- Each recommendation must include:
  - title
  - text
  - impact (High / Medium / Low)
- Mention names ONLY when they are part of the problem being solved
- Keep recommendations specific and outcome-focused

====================
DATA
====================
{safe_json(snapshot)}

====================
OUTPUT FORMAT (STRICT JSON)
====================

{{
  "summary": [
    ".Summary point 1",
    ".Summary point 2"
  ],
  "recommendations": [
    {{
      "title": "Title",
      "text": "Recommendation text",
      "impact": "High"
    }}
  ],
  "confidence": {confidence}
}}

If multiple data points describe the same issue, merge them into one insight.
"""

    ai_resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=500
    )

    return json.loads(ai_resp.choices[0].message.content)


# ==================================================
# Lambda Handler
# ==================================================
def lambda_handler(event, context):
    try:
        result = generate_summary_logic()

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps(result)
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
