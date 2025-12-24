from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from intents import INTENTS

# Prepare training data
sentences = []
intent_map = []

for intent, data in INTENTS.items():
    for example in data["examples"]:
        sentences.append(example)
        intent_map.append(intent)

vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(sentences)


def detect_intents(user_query, threshold=0.25):
    query_vec = vectorizer.transform([user_query])
    similarities = cosine_similarity(query_vec, X)[0]

    detected = set()

    for score, intent in zip(similarities, intent_map):
        if score >= threshold:
            detected.add(intent)

    return list(detected)
