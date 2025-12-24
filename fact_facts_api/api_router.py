from api_registry import API_REGISTRY
from settings import MAX_SOURCES

def detect_relevant_apis(question: str):
    q = question.lower()
    selected = []

    for name, meta in API_REGISTRY.items():
        if any(k in q for k in meta["keywords"]):
            selected.append(name)

    return selected[:MAX_SOURCES]