import os
import json
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

from api_registry import API_REGISTRY
from intent_router import detect_relevant_apis

from db_query_registry import DB_QUERY_REGISTRY
from db_intent_router import detect_db_intent
from db_client import run_safe_query

load_dotenv()

app = FastAPI()

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

GLOBAL_TIMEOUT = 35  # seconds

class ChatRequest(BaseModel):
    question: str


def calculate_confidence(collected_data, timeout_occurred):
    score = 100

    data_size = len(json.dumps(collected_data))

    if timeout_occurred:
        score -= 20

    if all(k.startswith("db::") for k in collected_data.keys()):
        score -= 15

    if data_size < 300:
        score -= 15
    elif data_size < 800:
        score -= 5

    return max(score, 60)


@app.post("/chatbot")
def chatbot(req: ChatRequest):
    try:
        collected_data = {}
        timeout_occurred = False

        # -------------------------
        # API-based data
        # -------------------------
        api_names = detect_relevant_apis(req.question)

        for api_name in api_names:
            url = API_REGISTRY[api_name]["url"]
            try:
                resp = requests.get(url, timeout=GLOBAL_TIMEOUT)
                resp.raise_for_status()
                data = resp.json()

                if isinstance(data, list):
                    data = data[:10]
                elif isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, list):
                            data[k] = v[:10]

                collected_data[api_name] = data

            except requests.exceptions.Timeout:
                timeout_occurred = True
                continue

            except requests.exceptions.RequestException:
                continue

        # -------------------------
        # DB fallback
        # -------------------------
        if not collected_data or len(json.dumps(collected_data)) < 300:
            db_intents = detect_db_intent(req.question)
            for intent in db_intents:
                sql = DB_QUERY_REGISTRY[intent]["sql"]
                rows = run_safe_query(sql)
                collected_data[f"db::{intent}"] = rows

        # -------------------------
        # Timeout notice
        # -------------------------
        if timeout_occurred:
            collected_data["system_notice"] = (
                "Some data sources took longer than expected and were not included."
            )

        # -------------------------
        # AI Summarization
        # -------------------------
        prompt = f"""
You are an engineering manager assistant.

User question:
"{req.question}"

Answer using ONLY the data below.
Be factual and concise (2–4 sentences).
Do not invent information.

If some insights are missing due to limited data availability or any errors, mention this briefly in a non-technical way.

Data:
{json.dumps(collected_data, indent=2)}
"""

        ai_resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.2
        )

        confidence = calculate_confidence(collected_data, timeout_occurred)

        return {
            "answer": ai_resp.choices[0].message.content.strip(),
            "confidence": confidence,
            "sources": list(collected_data.keys())
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
