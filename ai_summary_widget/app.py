import os
import json
import requests
from fastapi import FastAPI
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime, date

from api_registry import API_REGISTRY
from db_query_registry import DB_QUERY_REGISTRY
from db_client import run_safe_query

load_dotenv()
app = FastAPI()

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
GLOBAL_TIMEOUT = 35


# -------------------------
# SAFE JSON SERIALIZER
# -------------------------
def safe_json(obj):
    def default(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return str(o)
    return json.dumps(obj, indent=2, default=default)


@app.get("/summary")
def ai_summary():
    snapshot = {}
    failures = 0

    # -------------------------
    # API SNAPSHOT
    # -------------------------
    for name, url in API_REGISTRY.items():
        try:
            resp = requests.get(url, timeout=GLOBAL_TIMEOUT)
            resp.raise_for_status()
            snapshot[name] = resp.json()
        except Exception:
            failures += 1

    # -------------------------
    # DB SNAPSHOT
    # -------------------------
    for name, sql in DB_QUERY_REGISTRY.items():
        try:
            snapshot[f"db::{name}"] = run_safe_query(sql)
        except Exception:
            failures += 1

    # -------------------------
    # OWNERSHIP ATTRIBUTION LAYER  ✅ NEW
    # -------------------------
    attribution = {
        "at_risk_jira": [],
        "stale_jira": [],
        "workload": [],
        "open_prs": []
    }

    # Jira: stale / risky tickets
    for row in snapshot.get("db::stale_jira", []):
        attribution["stale_jira"].append({
            "issue_key": row.get("issue_key"),
            "assignee": row.get("assignee_name"),
            "priority": row.get("priority"),
            "last_updated": row.get("updated_at")
        })

    # Jira: workload per assignee
    assignee_counts = {}
    for row in snapshot.get("db::jira_assignee_breakdown", []):
        name = row.get("assignee_name")
        assignee_counts.setdefault(name, 0)
        assignee_counts[name] += row.get("count", 0)

    for name, count in assignee_counts.items():
        attribution["workload"].append({
            "assignee": name,
            "open_issues": count
        })

    # Git: open PRs by owner
    for row in snapshot.get("db::open_prs", []):
        attribution["open_prs"].append({
            "owner": row.get("author_login"),
            "open_pr_count": row.get("count")
        })

    # -------------------------
    # CONFIDENCE
    # -------------------------
    total_sources = len(API_REGISTRY) + len(DB_QUERY_REGISTRY)
    confidence = max(60, int((1 - failures / total_sources) * 100))

    # -------------------------
    # AI PROMPT (UNCHANGED LOGIC, BETTER DATA)
    # -------------------------
    prompt = f"""
You are an AI system generating a team-level summary.

PURPOSE:
- Explain what is happening and why, using the provided data
- Provide advisory recommendations based on observed signals
- Do NOT invent or assume information

RULES:
- Generate 5–7 neutral insight sentences
- Then generate 3–4 recommendations
- Each summary point MUST start with a dot (.)
- Each recommendation point MUST start with a dot (.)
- No action verbs in summary
- Recommendations should be advisory
- Do not invent data
- Keep sentences short, factual, and UI-friendly

DATA SNAPSHOT:
{safe_json(snapshot)}

OWNERSHIP ATTRIBUTION (IMPORTANT):
{safe_json(attribution)}

SUMMARY ATTRIBUTION RULES:
- Mention ticket IDs and assignees when available
- Mention PR owners when available
- Mention overloaded and underloaded developers with counts
- Mention sprint name if visible
- Prefer precise facts over general statements

RECOMMENDATION RULES:
- Mention overloaded and underloaded names explicitly
- Mention ticket IDs or PR numbers when relevant
- Avoid generic terms if names exist

OUTPUT FORMAT:
Return STRICT JSON ONLY:

{{
  "summary": [
    ".Summary point 1",
    ".Summary point 2"
  ],
  "recommendations": [
    ".Recommendation point 1",
    ".Recommendation point 2"
  ],
  "confidence": {confidence}
}}

Use ONLY the provided data.
If data is missing, omit that insight silently.
"""

    ai_resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=450
    )

    return json.loads(ai_resp.choices[0].message.content)
