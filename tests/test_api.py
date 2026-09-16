import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    # TestClient must be used as a context manager for startup/shutdown
    # lifespan events to fire — without it, the sample-doc ingest in
    # app.main's startup handler never runs, and every /query 400s.
    with TestClient(app) as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_query_returns_source_doc(client):
    resp = client.post("/query", json={"question": "How long are call recordings retained?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["source_doc_id"] == "doc_recording_retention"


def test_query_rejects_empty_question(client):
    resp = client.post("/query", json={"question": "   "})
    assert resp.status_code == 400


def test_ingest_custom_docs(client):
    resp = client.post(
        "/ingest",
        json={"docs": [{"id": "custom_doc", "text": "This is a custom test document about widgets."}]},
    )
    assert resp.status_code == 200
    assert resp.json()["chunks_indexed"] >= 1
