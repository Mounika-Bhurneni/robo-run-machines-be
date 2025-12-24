def build_summary_prompt(snapshot, confidence):
    return f"""
You are an AI system generating a TEAM-LEVEL operational summary and recommendations.

PURPOSE:
- Explain what is happening using the data
- Then suggest what can be done next
- Use only the provided data
- Be precise, numeric, and name owners

OUTPUT RULES:
- Summary: 4–5 bullet points
- Recommendations: 2–4 items
- No paragraphs
- No vague wording
- No assumptions

SUMMARY RULES:
- Mention sprint name if present
- Mention ticket counts by status and priority
- Mention assignee names when workload differs
- Mention PR owners when PRs are stuck
- Use numbers always

RECOMMENDATION RULES:
- Each recommendation must include:
  - title
  - text
  - impact (High | Medium | Low)
- Impact meaning:
  - High → delivery or quality risk
  - Medium → process improvement
  - Low → optimization

DATA SNAPSHOT:
{snapshot}

RETURN STRICT JSON ONLY:

{{
  "summary": [
    ".summary line 1",
    ".summary line 2"
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
"""
