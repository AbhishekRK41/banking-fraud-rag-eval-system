"""Chunking strategies for splitting documents before retrieval.

Two strategies are provided deliberately, so the evaluation harness
(see eval/run_eval.py) can compare them head to head rather than
assuming one is better.
"""
from dataclasses import dataclass


@dataclass
class Chunk:
    doc_id: str
    text: str


def fixed_size_chunks(doc_id: str, text: str, chunk_size_words: int = 60) -> list[Chunk]:
    """Split text into fixed-size windows of `chunk_size_words` words.

    Simple and predictable, but can split a sentence (and its meaning)
    across two chunks.
    """
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size_words):
        window = words[i : i + chunk_size_words]
        if window:
            chunks.append(Chunk(doc_id=doc_id, text=" ".join(window)))
    return chunks


def sentence_chunks(doc_id: str, text: str, sentences_per_chunk: int = 3) -> list[Chunk]:
    """Split text on sentence boundaries, grouping N sentences per chunk.

    Keeps sentences intact, at the cost of variable chunk length.
    """
    raw_sentences = [s.strip() for s in text.replace("\n", " ").split(". ") if s.strip()]
    chunks = []
    for i in range(0, len(raw_sentences), sentences_per_chunk):
        group = raw_sentences[i : i + sentences_per_chunk]
        if group:
            chunks.append(Chunk(doc_id=doc_id, text=". ".join(group)))
    return chunks


CHUNKERS = {
    "fixed_size": fixed_size_chunks,
    "sentence": sentence_chunks,
}
