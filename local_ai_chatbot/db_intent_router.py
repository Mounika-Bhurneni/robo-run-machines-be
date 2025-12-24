from db_query_registry import DB_QUERY_REGISTRY

def detect_db_intent(question: str):
    question = question.lower()
    matched = []

    for name, meta in DB_QUERY_REGISTRY.items():
        for kw in meta["keywords"]:
            if kw in question:
                matched.append(name)
                break

    return matched[:1]  # 🔒 Only ONE DB query max
