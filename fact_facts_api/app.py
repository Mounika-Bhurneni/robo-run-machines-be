import os
import json
import requests
from fastapi import FastAPI
from dotenv import load_dotenv
from openai import OpenAI

from api_router import detect_relevant_apis
from api_registry import API_REGISTRY
from db_router import detect_db_queries
from db_query_registry import DB_QUERY_REGISTRY
from db_client import run_query
from prompt import FACTS_PROMPT
from settings import API_TIMEOUT, OPENAI_MODEL

load_dotenv()
app = FastAPI()
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

@app.post("/facts")
def get_facts(payload: dict):
    question = payload.get("question", "")
    collected = {}
    sources = []

    # APIs
    for api in detect_relevant_apis(question):
        try:
            resp = requests.get(API_REGISTRY[api]["url"], timeout=API_TIMEOUT)
            resp.raise_for_status()
            collected[api] = resp.json()
            sources.append(api)
        except Exception:
            continue

    # DB
    for q in detect_db_queries(question):
        try:
            sql = DB_QUERY_REGISTRY[q]["sql"]
            params = {"name": f"%{question.split()[-1]}%"}
            rows = run_query(sql, params)
            collected[q] = rows
            sources.append(q)
        except Exception:
            continue

    prompt = FACTS_PROMPT.format(data=json.dumps(collected, indent=2))

    ai_resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=800
    )

    return {
        "facts": ai_resp.choices[0].message.content.strip(),
        "sources": sources
    }
