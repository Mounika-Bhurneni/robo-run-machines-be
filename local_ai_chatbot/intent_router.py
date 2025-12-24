from api_registry import API_REGISTRY

def detect_relevant_apis(question: str):
    question = question.lower()
    matched = []

    for name, meta in API_REGISTRY.items():
        for kw in meta["keywords"]:
            if kw in question:
                matched.append(name)
                break

    # Safety fallback
    if not matched:
        matched.append("risk_insights")

    return matched[:3]  # calling 3 APIs only
