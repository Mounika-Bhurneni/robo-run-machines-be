from db_query_registry import DB_QUERY_REGISTRY

MIN_DB_QUERIES = 3
MAX_DB_QUERIES = 5

def detect_db_intent(question: str):
    question = question.lower()
    matched = []

    # Match by keyword relevance
    for name, meta in DB_QUERY_REGISTRY.items():
        if any(kw in question for kw in meta["keywords"]):
            matched.append(name)

    # If fewer than MIN_DB_QUERIES matched, top up generically
    if len(matched) < MIN_DB_QUERIES:
        for name in DB_QUERY_REGISTRY.keys():
            if name not in matched:
                matched.append(name)
            if len(matched) >= MIN_DB_QUERIES:
                break

    return matched[:MAX_DB_QUERIES]
