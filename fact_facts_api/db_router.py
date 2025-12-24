from db_query_registry import DB_QUERY_REGISTRY
from settings import MAX_SOURCES

def detect_db_queries(question: str):
    q = question.lower()
    selected = []

    for name, meta in DB_QUERY_REGISTRY.items():
        if any(k in q for k in meta["keywords"]):
            selected.append(name)

    return selected[:MAX_SOURCES]
