from api_registry import API_REGISTRY

MIN_APIS = 3
MAX_APIS = 5   # safe upper bound

def detect_relevant_apis(question: str):
    question = question.lower()
    scores = {}

    # Score APIs by keyword relevance
    for api_name, meta in API_REGISTRY.items():
        score = 0
        for kw in meta["keywords"]:
            if kw.lower() in question:
                score += 1
        if score > 0:
            scores[api_name] = score

    # Sort by relevance
    ranked = [name for name, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]

    # If fewer than MIN_APIS matched, top up with generic APIs
    if len(ranked) < MIN_APIS:
        for api_name in API_REGISTRY.keys():
            if api_name not in ranked:
                ranked.append(api_name)
            if len(ranked) >= MIN_APIS:
                break

    return ranked[:MAX_APIS]
