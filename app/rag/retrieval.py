from __future__ import annotations

import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi

from .chunking import Chunk

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    """Lowercase + strip punctuation. Naive BM25 splitting on whitespace
    alone leaves punctuation glued to words ('processed?' != 'processed'),
    which silently degrades every score to a tie — this bit us in testing,
    so it's handled explicitly rather than left as a footgun."""
    return _TOKEN_RE.findall(text.lower())


class TfidfRetriever:
    name = "tfidf"

    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.vectorizer = TfidfVectorizer()
        self.matrix = self.vectorizer.fit_transform([c.text for c in chunks])

    def query(self, question: str, top_k: int = 1) -> list[tuple[Chunk, float]]:
        q_vec = self.vectorizer.transform([question])
        scores = cosine_similarity(q_vec, self.matrix)[0]
        ranked = sorted(zip(self.chunks, scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]


class BM25Retriever:
    name = "bm25"

    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        tokenized = [_tokenize(c.text) for c in chunks]
        self.bm25 = BM25Okapi(tokenized)

    def query(self, question: str, top_k: int = 1) -> list[tuple[Chunk, float]]:
        scores = self.bm25.get_scores(_tokenize(question))
        ranked = sorted(zip(self.chunks, scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]


RETRIEVERS = {
    "tfidf": TfidfRetriever,
    "bm25": BM25Retriever,
}
