import os
import json
import requests
from openai import OpenAI

from api_registry import API_REGISTRY
from intent_router import detect_relevant_apis
from db_intent_router import detect_db_intent
from db_query_registry import DB_QUERY_REGISTRY
from db_client import run_safe_query

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
GLOBAL_TIMEOUT = 35


def calculate_confidence(collected_data, timeout_occurred):
    score = 100

    if timeout_occurred:
        score -= 20

    if all(k.startswith("db::") for k in collected_data.keys()):
        score -= 15

    if len(json.dumps(collected_data)) < 300:
        score -= 10

    return max(score, 60)


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        question = body.get("question", "").strip()

        if not question:
            return _response(400, {"error": "Question is required"})

        collected_data = {}
        timeout_occurred = False

        # -------------------------
        # API DATA (PRIMARY)
        # -------------------------
        api_names = detect_relevant_apis(question)

        for api_name in api_names:
            url = API_REGISTRY[api_name]["url"]
            try:
                resp = requests.get(url, timeout=GLOBAL_TIMEOUT)
                resp.raise_for_status()
                data = resp.json()

                if isinstance(data, list):
                    data = data[:20]
                elif isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, list):
                            data[k] = v[:20]

                collected_data[api_name] = data

            except requests.exceptions.Timeout:
                timeout_occurred = True
            except Exception:
                continue

        # -------------------------
        # DB DATA (ALWAYS-ON)
        # -------------------------
        db_intents = detect_db_intent(question)

        for intent in db_intents:
            try:
                rows = run_safe_query(DB_QUERY_REGISTRY[intent]["sql"])
                if rows:
                    collected_data[f"db::{intent}"] = rows
            except Exception:
                continue

        if not collected_data:
            return _response(200, {
                "facts": "No relevant factual data was found.",
                "sources": [],
                "confidence": 60
            })

        # -------------------------
        # FACTS PROMPT
        # -------------------------
        prompt = f"""
You are a factual analytics assistant.

Answer the user's question using ONLY the provided data.

STRICT RULES:
- Include ONLY facts relevant to the question
- Do NOT summarize
- Do NOT interpret
- Do NOT include unrelated information
- Use exact names, IDs, counts, statuses, dates
- If the question is about a person, include ONLY that person
- If the question is about recent activity, include ONLY recent events
- Remove duplicate facts

If data is insufficient, say:
"No relevant factual data was found."

Question:
{question}

Data:
{json.dumps(collected_data, indent=2)}

Return factual sentences only.
"""

        ai_resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=600
        )

        confidence = calculate_confidence(collected_data, timeout_occurred)

        return _response(200, {
            "facts": ai_resp.choices[0].message.content.strip(),
            "sources": list(collected_data.keys()),
            "confidence": confidence
        })

    except Exception as e:
        return _response(500, {"error": str(e)})


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body)
    }
