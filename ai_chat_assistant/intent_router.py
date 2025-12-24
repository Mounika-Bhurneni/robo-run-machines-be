from api_registry import API_REGISTRY

MAX_APIS = 3

def detect_relevant_apis(question: str):
    question = question.lower()
    scores = {}

    for api, meta in API_REGISTRY.items():
        score = sum(1 for kw in meta["keywords"] if kw.lower() in question)
        if score > 0:
            scores[api] = score

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    selected = [name for name, _ in ranked[:MAX_APIS]]

    return selected or ["recent_activity"]
