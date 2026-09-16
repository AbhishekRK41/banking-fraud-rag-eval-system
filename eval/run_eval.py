"""Evaluation harness: runs every (chunker x retriever) combination
against eval_dataset.json and reports hit-rate@1 — whether the
top-retrieved chunk actually comes from the document the question was
written against.

Usage:
    python -m eval.run_eval
Writes eval/results.md and prints a summary table to stdout.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.chunking import CHUNKERS
from app.rag.retrieval import RETRIEVERS
from app.rag.pipeline import RAGPipeline

DATA_DIR = Path(__file__).parent.parent / "app" / "data"
EVAL_SET_PATH = Path(__file__).parent / "eval_dataset.json"
RESULTS_PATH = Path(__file__).parent / "results.md"


def load_docs() -> list[dict]:
    return [
        {"id": p.stem, "text": p.read_text(encoding="utf-8")}
        for p in sorted(DATA_DIR.glob("*.txt"))
    ]


def load_eval_set() -> list[dict]:
    return json.loads(EVAL_SET_PATH.read_text(encoding="utf-8"))


def run_combination(chunker_name: str, retriever_name: str, docs: list[dict], eval_set: list[dict]) -> dict:
    pipeline = RAGPipeline(chunker_name=chunker_name, retriever_name=retriever_name)
    t0 = time.perf_counter()
    chunk_count = pipeline.ingest(docs)
    ingest_ms = (time.perf_counter() - t0) * 1000

    hits = 0
    t0 = time.perf_counter()
    for item in eval_set:
        result = pipeline.answer(item["question"])
        if result["source_doc_id"] == item["expected_doc_id"]:
            hits += 1
    query_ms = (time.perf_counter() - t0) * 1000 / len(eval_set)

    return {
        "chunker": chunker_name,
        "retriever": retriever_name,
        "chunk_count": chunk_count,
        "hit_rate": hits / len(eval_set),
        "hits": hits,
        "total": len(eval_set),
        "avg_query_ms": round(query_ms, 2),
        "ingest_ms": round(ingest_ms, 2),
    }


def main() -> None:
    docs = load_docs()
    eval_set = load_eval_set()

    results = []
    for chunker_name in CHUNKERS:
        for retriever_name in RETRIEVERS:
            results.append(run_combination(chunker_name, retriever_name, docs, eval_set))

    # Rank by accuracy first; break ties by query speed rather than
    # insertion order — on a small corpus, hit-rate alone often ties,
    # and speed is the honest differentiator at that point.
    results.sort(key=lambda r: (-r["hit_rate"], r["avg_query_ms"]))

    header = f"| {'Chunker':<12} | {'Retriever':<9} | {'Chunks':<7} | {'Hit-rate@1':<11} | {'Avg query (ms)':<15} |"
    sep = "|" + "-" * 14 + "|" + "-" * 11 + "|" + "-" * 9 + "|" + "-" * 13 + "|" + "-" * 17 + "|"
    lines = [header, sep]
    for r in results:
        lines.append(
            f"| {r['chunker']:<12} | {r['retriever']:<9} | {r['chunk_count']:<7} "
            f"| {r['hits']}/{r['total']} ({r['hit_rate']:.0%})".ljust(23)
            + f"| {r['avg_query_ms']:<15} |"
        )

    table = "\n".join(lines)
    print(table)

    best = results[0]
    md = [
        "# Evaluation Results",
        "",
        f"Run against {len(eval_set)} questions over {len(docs)} source documents.",
        "",
        table,
        "",
        f"**Best combination:** `{best['chunker']}` chunking + `{best['retriever']}` retrieval "
        f"— {best['hits']}/{best['total']} ({best['hit_rate']:.0%}) hit-rate@1, "
        f"{best['avg_query_ms']}ms average query time. "
        + (
            "All four combinations tied on accuracy at this corpus size; "
            "ranked first here for query speed, not retrieval quality."
            if len({r["hit_rate"] for r in results}) == 1
            else "Selected for the highest hit-rate@1; ties broken by query speed."
        ),
        "",
        "Hit-rate@1 = the top-retrieved chunk came from the document the question",
        "was actually written against. Regenerate with `python -m eval.run_eval`.",
    ]
    RESULTS_PATH.write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()
