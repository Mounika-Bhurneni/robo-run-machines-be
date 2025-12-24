SYSTEM_PROMPT = """
You are an engineering analytics assistant.

Rules:
- Use ONLY the provided data
- Do NOT guess or assume missing values
- Keep answers short (2–4 sentences)
- No recommendations
- No exaggeration
"""

def build_prompt(question: str, data: dict) -> str:
    return f"""
User question:
{question}

Available data:
{data}

Answer clearly and factually.
"""
