from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.rag.pipeline import RAGPipeline

DATA_DIR = Path(__file__).parent / "data"

app = FastAPI(
    title="RAG Evaluation System",
    description=(
        "A small, self-contained retrieval-augmented pipeline with an "
        "evaluation harness comparing chunking and retrieval strategies. "
        "Runs fully offline — no API key required."
    ),
    version="1.0.0",
)

pipeline = RAGPipeline(chunker_name="sentence", retriever_name="bm25")


def _load_sample_docs() -> list[dict]:
    docs = []
    for path in sorted(DATA_DIR.glob("*.txt")):
        docs.append({"id": path.stem, "text": path.read_text(encoding="utf-8")})
    return docs


@app.on_event("startup")
def startup() -> None:
    docs = _load_sample_docs()
    if docs:
        pipeline.ingest(docs)


class IngestDoc(BaseModel):
    id: str
    text: str


class IngestRequest(BaseModel):
    docs: list[IngestDoc]


class QueryRequest(BaseModel):
    question: str
    top_k: int = 1


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ingest")
def ingest(payload: IngestRequest) -> dict:
    docs = [d.model_dump() for d in payload.docs]
    if not docs:
        raise HTTPException(status_code=400, detail="No documents provided.")
    count = pipeline.ingest(docs)
    return {"chunks_indexed": count}


@app.post("/query")
def query(payload: QueryRequest) -> dict:
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    try:
        return pipeline.answer(payload.question, top_k=payload.top_k)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
