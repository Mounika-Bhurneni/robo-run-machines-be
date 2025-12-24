FACTS_PROMPT = """
You are generating FACTUAL statements only.

Rules:
- Do NOT summarize
- Do NOT infer
- Do NOT explain
- Convert data into clear factual sentences
- Include all names, IDs, counts, dates present
- Do NOT hide information

Data:
{data}

Return plain text facts.
"""
