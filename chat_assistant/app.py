import os
import json
import requests
from typing import Dict, Any

# ============================================================
# Environment Variables
# ============================================================

HF_API_TOKEN = os.environ.get("HF_API_TOKEN")
HF_MODEL_ID = os.environ.get("HF_MODEL_ID")

WORKLOAD_API_URL = os.environ.get("WORKLOAD_API_URL")
RISK_API_URL = os.environ.get("RISK_API_URL")

if not HF_API_TOKEN or not HF_MODEL_ID:
    raise RuntimeError("HF_API_TOKEN and HF_MODEL_ID must be set")

HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL_ID}"

HEADERS = {
    "Authorization": f"Bearer {HF_API_TOKEN}",
    "Content-Type": "application/json"
}

# ============================================================
# HuggingFace LLM Call
# ============================================================

def call_huggingface_llm(user_query: str) -> Dict[str, Any]:
    """
    Uses an open-source LLM (Phi-3 Mini) to decide
    which internal analytics APIs should be called.
    """

    prompt = f"""
You are an AI planning system.

Your job is to decide which analytics APIs are required
to answer the user's question.

Available tools:
1. WORKLOAD_ANALYTICS - capacity, utilization, workload distribution
2. RISK_STATS - delivery risks, blocked work, delays, incidents

Rules:
- Return ONLY valid JSON
- Do NOT explain anything
- Do NOT add extra text

Required JSON format:
{{
  "required_tools": [],
  "merge_strategy": "",
  "response_style": ""
}}

User question:
"{user_query}"
"""

    payload = {
        "inputs": prompt,
        "parameters": {
            "temperature": 0.2,
            "max_new_tokens": 300
        }
    }

    response = requests.post(
        HF_API_URL,
        headers=HEADERS,
        json=payload,
        timeout=20
    )

    response.raise_for_status()
    result = response.json()

    # ---------------- SAFETY CHECKS ----------------

    if isinstance(result, dict) and "error" in result:
        raise Exception(f"HuggingFace error: {result['error']}")

    if not isinstance(result, list) or not result:
        raise Exception("Unexpected HuggingFace response format")

    item = result[0]
    generated_text = item.get("generated_text") or item.get("text")

    if not generated_text:
        raise Exception("No generated text returned from HuggingFace")

    # ---------------- JSON EXTRACTION ----------------

    json_start = generated_text.find("{")
    json_end = generated_text.rfind("}") + 1

    if json_start == -1 or json_end == -1:
        raise Exception("LLM did not return valid JSON")

    json_text = generated_text[json_start:json_end]

    return json.loads(json_text)

# ============================================================
# Internal API Call
# ============================================================

def call_internal_api(url: str) -> Dict[str, Any]:
    """
    Calls internal deterministic analytics APIs
    """
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()

# ============================================================
# Lambda Handler
# ============================================================

def lambda_handler(event, context):
    try:
        # ---------------- Request Parsing ----------------
        body = json.loads(event.get("body", "{}"))
        user_query = body.get("query")

        if not user_query:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "query is required"})
            }

        # ---------------- Step 1: LLM Planning ----------------
        plan = call_huggingface_llm(user_query)

        required_tools = plan.get("required_tools", [])

        # Fallback safety
        if not required_tools:
            required_tools = ["WORKLOAD_ANALYTICS"]

        # ---------------- Step 2: Execute Tools ----------------
        results = {}

        if "WORKLOAD_ANALYTICS" in required_tools and WORKLOAD_API_URL:
            results["workload"] = call_internal_api(WORKLOAD_API_URL)

        if "RISK_STATS" in required_tools and RISK_API_URL:
            results["risk"] = call_internal_api(RISK_API_URL)

        # ---------------- Step 3: Deterministic Response ----------------
        final_response = {
            "question": user_query,
            "used_tools": required_tools,
            "data": results
        }

        return {
            "statusCode": 200,
            "body": json.dumps(final_response)
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
