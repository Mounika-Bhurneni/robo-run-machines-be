from db_query_registry import DB_QUERY_REGISTRY

MAX_DB_QUERIES = 2

def detect_db_intent(question: str):
    question = question.lower()
    matched = []

    for name, meta in DB_QUERY_REGISTRY.items():
        if any(kw in question for kw in meta["keywords"]):
            matched.append(name)

    return matched[:MAX_DB_QUERIES]
