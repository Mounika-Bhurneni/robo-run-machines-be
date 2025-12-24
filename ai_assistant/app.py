import json
import os
from openai import OpenAI
from data_resolver import resolve_data
from prompt_templates import SYSTEM_PROMPT, build_prompt


client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
        question = body.get("question")

        if not question:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Question is required"})
            }

        # 1️⃣ Fetch real data (NO AI here)
        data = resolve_data(question)

        # 2️⃣ Build AI prompt
        prompt = build_prompt(question, data)

        # 3️⃣ AI interpretation
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0
        )

        answer = response.choices[0].message.content.strip()

        return {
            "statusCode": 200,
            "body": json.dumps({
                "question": question,
                "answer": answer
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
