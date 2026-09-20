# Banking Fraud RAG Evaluation System

A small, self-contained retrieval-augmented pipeline with a real evaluation harness comparing chunking and retrieval strategies head-to-head. Built to demonstrate engineering practice — chunking strategy design, retrieval benchmarking, a tested FastAPI service, Docker packaging, and CI — not to claim state-of-the-art retrieval quality.

**What this is (and isn't):** retrieval is TF-IDF / BM25 (classic sparse methods), and "generation" is extractive — it returns the best-matching source chunk verbatim rather than calling an LLM. That's a deliberate choice: the whole thing runs offline, with no API key, so a CI pipeline (or anyone cloning this) can run it end to end with nothing but `pip install`.

## Also in this repository

[`fraud-agent-mock-backend/`](./fraud-agent-mock-backend) is a separate, self-contained FastAPI project: mocked verification, policy-evaluation and action services for a voice-agent fraud-intervention demo (Ignyte x ElevenLabs hackathon, Banking & Insurance track). It has its own README, tests and Dockerfile. Everything below describes the RAG evaluation project at the repository root.

## Results

Evaluated against 14 questions over a 5-document sample corpus (policy-style documents on card freezes, fraud escalation, authentication requirements, multilingual servicing, and call recording — see `app/data/`). Full run: `python -m eval.run_eval`.

| Chunker | Retriever | Chunks | Hit-rate@1 | Avg query (ms) |
|---|---|---|---|---|
| fixed_size | bm25 | 8 | 14/14 (100%) | 0.06 |
| sentence | bm25 | 10 | 14/14 (100%) | 0.09 |
| fixed_size | tfidf | 8 | 14/14 (100%) | 0.50 |
| sentence | tfidf | 10 | 14/14 (100%) | 0.62 |

**Honest read of this result:** all four combinations tie on accuracy at this corpus size — the real, reportable finding is speed, not accuracy. BM25 answers roughly 8–9x faster than TF-IDF cosine similarity here, which is the kind of gap that matters at production query volume even when both methods get the right answer. A corpus this small doesn't stress-test retrieval *quality* differences; it does honestly surface a *latency* difference. Re-run `python -m eval.run_eval` any time — it regenerates this table from scratch, including after you swap in a larger or harder document set.

One real bug this harness caught during development, left in the code as a comment where it was fixed (`app/rag/retrieval.py`): naive whitespace tokenization left punctuation glued to words (`"processed?"` never matched `"processed"`), silently zeroing out BM25 scores. Also worth knowing: BM25's IDF term is mathematically degenerate on very small (2-document) corpora — `log((N-df+0.5)/(df+0.5))` hits exactly zero for any term in exactly one of two documents — documented in `tests/test_pipeline.py`.

## Architecture

```
app/
  main.py          FastAPI app: /health, /ingest, /query
  rag/
    chunking.py     fixed_size and sentence-based chunking strategies
    retrieval.py     TF-IDF (cosine) and BM25 retrievers
    pipeline.py      ties a chunker + retriever together
  data/              5 sample source documents (.txt)
eval/
  eval_dataset.json  14 question -> expected-source-document pairs
  run_eval.py        runs every (chunker x retriever) combo, writes results.md
tests/
  test_pipeline.py   unit tests on the RAG pipeline directly
  test_api.py        tests the FastAPI endpoints via TestClient
.github/workflows/ci.yml   installs deps, runs pytest, runs the eval harness, uploads results.md as a build artifact
Dockerfile
```

## Running it

**Locally:**
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
# then: POST http://localhost:8000/query {"question": "How long are call recordings retained?"}
```

**Tests:**
```bash
pytest -v
```

**Evaluation harness:**
```bash
python -m eval.run_eval
```

**Docker:**
```bash
docker build -t banking-fraud-rag-eval-system .
docker run -p 8000:8000 banking-fraud-rag-eval-system
```
*(Dockerfile follows a standard `python:3.11-slim` + pip-install pattern; not build-verified in the environment this repo was authored in — verify locally before relying on it.)*

## CI

`.github/workflows/ci.yml` runs on every push/PR to `main`: installs dependencies, runs the full test suite, runs the evaluation harness, and uploads `eval/results.md` as a downloadable build artifact — so the benchmark table above is always reproducible from a clean checkout, not just a claim in this README.
