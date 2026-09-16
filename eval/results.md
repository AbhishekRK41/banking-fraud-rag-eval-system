# Evaluation Results

Run against 14 questions over 5 source documents.

| Chunker      | Retriever | Chunks  | Hit-rate@1  | Avg query (ms)  |
|--------------|-----------|---------|-------------|-----------------|
| fixed_size   | bm25      | 8       | 14/14 (100%)| 0.06            |
| sentence     | bm25      | 10      | 14/14 (100%)| 0.09            |
| fixed_size   | tfidf     | 8       | 14/14 (100%)| 0.50            |
| sentence     | tfidf     | 10      | 14/14 (100%)| 0.62            |

**Best combination:** `fixed_size` chunking + `bm25` retrieval — 14/14 (100%) hit-rate@1, 0.06ms average query time. All four combinations tied on accuracy at this corpus size; ranked first here for query speed, not retrieval quality.

Hit-rate@1 = the top-retrieved chunk came from the document the question
was actually written against. Regenerate with `python -m eval.run_eval`.
