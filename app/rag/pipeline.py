"""Ties a chunking strategy and a retrieval strategy into one pipeline.

The "generation" step here is deliberately extractive (it returns the
best-matching chunk verbatim, with its source) rather than calling an
LLM — this keeps the whole project runnable with no API key and no
network dependency, which matters for a CI pipeline and for a judge
who just wants to clone and run it.
"""
from __future__ import annotations

from .chunking import CHUNKERS, Chunk
from .retrieval import RETRIEVERS


class RAGPipeline:
    def __init__(self, chunker_name: str = "sentence", retriever_name: str = "bm25"):
        if chunker_name not in CHUNKERS:
            raise ValueError(f"Unknown chunker '{chunker_name}'. Options: {list(CHUNKERS)}")
        if retriever_name not in RETRIEVERS:
            raise ValueError(f"Unknown retriever '{retriever_name}'. Options: {list(RETRIEVERS)}")
        self.chunker_name = chunker_name
        self.retriever_name = retriever_name
        self._chunk_fn = CHUNKERS[chunker_name]
        self._retriever_cls = RETRIEVERS[retriever_name]
        self._retriever = None
        self._all_chunks: list[Chunk] = []

    def ingest(self, docs: list[dict]) -> int:
        """docs: [{"id": "doc1", "text": "..."}, ...]. Returns chunk count."""
        self._all_chunks = []
        for doc in docs:
            self._all_chunks.extend(self._chunk_fn(doc["id"], doc["text"]))
        if not self._all_chunks:
            raise ValueError("No chunks produced — check input documents.")
        self._retriever = self._retriever_cls(self._all_chunks)
        return len(self._all_chunks)

    def answer(self, question: str, top_k: int = 1) -> dict:
        if self._retriever is None:
            raise RuntimeError("Call ingest() before answer().")
        results = self._retriever.query(question, top_k=top_k)
        top_chunk, score = results[0]
        return {
            "question": question,
            "answer": top_chunk.text,
            "source_doc_id": top_chunk.doc_id,
            "score": float(score),
            "chunker": self.chunker_name,
            "retriever": self.retriever_name,
        }
