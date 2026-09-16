import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.pipeline import RAGPipeline


SAMPLE_DOCS = [
    {"id": "doc_a", "text": "The office is open from nine in the morning until six in the evening on weekdays."},
    {"id": "doc_b", "text": "Refunds are processed within five business days of an approved return."},
    {"id": "doc_c", "text": "Support tickets are answered within one hour during business hours."},
    # Note: BM25's IDF term is log((N - df + 0.5) / (df + 0.5)). With only
    # two documents, any term appearing in exactly one of them scores
    # idf = log(1.0) = 0 — every discriminating term is zeroed out and BM25
    # degenerates to a tie. A third document avoids that edge case; the same
    # effect is visible (and documented) at the full-corpus scale in
    # eval/results.md, where 5 documents make it a non-issue.
]


def test_ingest_returns_chunk_count():
    pipeline = RAGPipeline(chunker_name="sentence", retriever_name="bm25")
    count = pipeline.ingest(SAMPLE_DOCS)
    assert count >= 2


def test_answer_returns_correct_source_doc():
    pipeline = RAGPipeline(chunker_name="sentence", retriever_name="bm25")
    pipeline.ingest(SAMPLE_DOCS)
    result = pipeline.answer("When are refunds processed?")
    assert result["source_doc_id"] == "doc_b"


def test_answer_before_ingest_raises():
    pipeline = RAGPipeline(chunker_name="sentence", retriever_name="tfidf")
    try:
        pipeline.answer("anything")
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass


def test_all_chunker_retriever_combinations_run():
    from app.rag.chunking import CHUNKERS
    from app.rag.retrieval import RETRIEVERS

    for chunker_name in CHUNKERS:
        for retriever_name in RETRIEVERS:
            pipeline = RAGPipeline(chunker_name=chunker_name, retriever_name=retriever_name)
            pipeline.ingest(SAMPLE_DOCS)
            result = pipeline.answer("office hours")
            assert result["source_doc_id"] in {"doc_a", "doc_b", "doc_c"}
