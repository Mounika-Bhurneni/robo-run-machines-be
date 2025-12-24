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

    if timeout_occurred:
        score -= 20

    if all(k.startswith("db::") for k in collected_data.keys()):
        score -= 15

    data_size = len(json.dumps(collected_data))
    if data_size < 300:
        score -= 10

    return max(score, 60)


@app.post("/facts")
def facts_chatbot(req: ChatRequest):
    try:
        collected_data = {}
        timeout_occurred = False

        # -------------------------
        # API-based data (PRIMARY)
        # -------------------------
        api_names = detect_relevant_apis(req.question)
        print("Selected APIs:", api_names)

        for api_name in api_names:
            url = API_REGISTRY[api_name]["url"]
            try:
                resp = requests.get(url, timeout=GLOBAL_TIMEOUT)
                resp.raise_for_status()
                data = resp.json()

                # Safety trimming
                if isinstance(data, list):
                    data = data[:20]
                elif isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, list):
                            data[k] = v[:20]

                collected_data[api_name] = data

            except requests.exceptions.Timeout:
                timeout_occurred = True
                continue
            except requests.exceptions.RequestException:
                continue

        # -------------------------
        # DB data (SUPPLEMENTARY ONLY)
        # -------------------------
        #if not collected_data:
         #   db_intents = detect_db_intent(req.question)
          #  for intent in db_intents:
           #     sql = DB_QUERY_REGISTRY[intent]["sql"]
            #    rows = run_safe_query(sql)
             #   collected_data[f"db::{intent}"] = rows

        # -------------------------
        # DB-based data (ALWAYS-ON)
        # -------------------------
        db_intents = detect_db_intent(req.question)

        for intent in db_intents:
            try:
                sql = DB_QUERY_REGISTRY[intent]["sql"]
                rows = run_safe_query(sql)
                if rows:
                    collected_data[f"db::{intent}"] = rows
            except Exception:
                continue


        if not collected_data:
            return {
                "facts": "No relevant factual data was found for the given question.",
                "sources": [],
                "confidence": 60
            }

        # -------------------------
        # FACTS PROMPT (NO SUMMARY)
        # -------------------------
        prompt = f"""
You are a factual analytics assistant.

Your task is to answer the user's question using ONLY the data provided.

CORE PRINCIPLE:
- Relevance is determined strictly by the user's question.
- Include ONLY facts that directly answer the question.
- Exclude any data that is not relevant to the question.

DO NOT:
- Summarize
- Interpret
- Explain causes, risks, or impact
- Add opinions or recommendations
- Include unrelated facts

FACT RULES:
- Use clear, direct sentences.
- Always include exact names, IDs, counts, statuses, priorities, and dates when available.
- If the question asks about a specific person, include ONLY facts about that person.
- If the question asks about recent activity, include ONLY recent events.
- If the question asks for counts, provide counts (lists only if needed).
- If multiple sources contain overlapping facts, remove duplicates.

If the data does not contain enough information to answer the question, say:
"No relevant factual data was found."

User question:
"{req.question}"

Available data:
{json.dumps(collected_data, indent=2)}

Return factual statements only.
"""


        ai_resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0
        )

        confidence = calculate_confidence(collected_data, timeout_occurred)

        return {
            "facts": ai_resp.choices[0].message.content.strip(),
            "sources": list(collected_data.keys()),
            "confidence": confidence
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
