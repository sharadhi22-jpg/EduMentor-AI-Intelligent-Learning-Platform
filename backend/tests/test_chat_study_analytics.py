import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app

SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(name="db_session")
def fixture_db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(name="client")
def fixture_client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(name="auth_headers")
def fixture_auth_headers(client):
    client.post(
        "/api/v1/auth/register",
        json={"name": "Eve Adams", "email": "eve@example.com", "password": "supersecurepass"},
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "eve@example.com", "password": "supersecurepass"},
    )
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(name="subject_id")
def fixture_subject_id(client, auth_headers):
    res = client.post(
        "/api/v1/subjects/",
        json={"name": "Machine Learning", "code": "CS-701", "semester": 7},
        headers=auth_headers,
    )
    return res.json()["id"]


def test_chat_session_lifecycle(client, auth_headers, subject_id, monkeypatch):
    from app.core import gemini as gemini_module
    monkeypatch.setattr(gemini_module, "is_configured", lambda: False)

    # Create a session
    create_res = client.post(
        "/api/v1/chat/sessions",
        json={"subject_id": subject_id, "title": "Doubt session"},
        headers=auth_headers,
    )
    assert create_res.status_code == 201
    session_id = create_res.json()["id"]
    assert create_res.json()["title"] == "Doubt session"

    # List sessions
    list_res = client.get(f"/api/v1/chat/sessions?subject_id={subject_id}", headers=auth_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    # Messages list should start empty
    msgs_res = client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=auth_headers)
    assert msgs_res.status_code == 200
    assert msgs_res.json() == []

    # Sending a message without GEMINI_API_KEY configured should fail gracefully (503),
    # not crash, since no key is set in the test environment.
    send_res = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "What is gradient descent?"},
        headers=auth_headers,
    )
    assert send_res.status_code == 503

    # Delete session
    delete_res = client.delete(f"/api/v1/chat/sessions/{session_id}", headers=auth_headers)
    assert delete_res.status_code == 200


def test_chat_session_requires_owned_subject(client, auth_headers):
    res = client.post(
        "/api/v1/chat/sessions",
        json={"subject_id": 9999, "title": "Ghost subject"},
        headers=auth_headers,
    )
    assert res.status_code == 404


def test_flashcard_and_quiz_generation_without_gemini_key(client, auth_headers, subject_id):
    # No documents uploaded yet -> should 400 (no source content), never a raw 500
    flash_res = client.post(
        "/api/v1/study-tools/flashcards/generate",
        json={"subject_id": subject_id, "count": 3},
        headers=auth_headers,
    )
    assert flash_res.status_code in (400, 503)

    quiz_res = client.post(
        "/api/v1/study-tools/quizzes/generate",
        json={"subject_id": subject_id, "count": 3},
        headers=auth_headers,
    )
    assert quiz_res.status_code in (400, 503)


def test_flashcard_list_empty(client, auth_headers, subject_id):
    res = client.get(f"/api/v1/study-tools/flashcards?subject_id={subject_id}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json() == []


def test_analytics_progress_and_dashboard(client, auth_headers, subject_id):
    # Progress record is lazily created on first read
    progress_res = client.get(f"/api/v1/analytics/progress/{subject_id}", headers=auth_headers)
    assert progress_res.status_code == 200
    assert progress_res.json()["study_hours"] == 0.0
    assert progress_res.json()["completed_quizzes"] == 0

    # Log some study time
    log_res = client.post(
        "/api/v1/analytics/progress/study-time",
        json={"subject_id": subject_id, "hours": 2.5},
        headers=auth_headers,
    )
    assert log_res.status_code == 200
    assert log_res.json()["study_hours"] == 2.5

    # Dashboard aggregates across subjects
    dash_res = client.get("/api/v1/analytics/dashboard", headers=auth_headers)
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert dash_data["total_subjects"] == 1
    assert dash_data["total_study_hours"] == 2.5
    assert dash_data["subjects"][0]["name"] == "Machine Learning"


def test_analytics_requires_owned_subject(client, auth_headers):
    res = client.get("/api/v1/analytics/progress/9999", headers=auth_headers)
    assert res.status_code == 404


def test_full_rag_chat_flow_with_mocked_gemini(client, auth_headers, subject_id, monkeypatch):
    """
    Simulates a real end-to-end RAG cycle (upload -> embed -> chat -> retrieve ->
    generate -> citations) with Gemini calls mocked out, so the wiring between
    documents.py, embeddings.py, vector_store.py, and chat.py is verified without
    needing a live API key.
    """
    import io
    from app.core import gemini as gemini_module
    from app.core import embeddings as embeddings_module

    # Fake deterministic embeddings: identical text -> identical vector
    def fake_embed_documents(texts):
        return [[1.0, 0.0, 0.0] if "gradient" in t.lower() else [0.0, 1.0, 0.0] for t in texts]

    def fake_embed_query(text):
        return [1.0, 0.0, 0.0] if "gradient" in text.lower() else [0.0, 1.0, 0.0]

    monkeypatch.setattr(embeddings_module, "embed_documents", fake_embed_documents)
    monkeypatch.setattr(embeddings_module, "embed_query", fake_embed_query)
    monkeypatch.setattr(gemini_module, "is_configured", lambda: True)
    monkeypatch.setattr(
        gemini_module,
        "generate_text",
        lambda prompt, system_instruction=None, temperature=0.4: "Gradient descent minimizes loss iteratively.",
    )

    # Upload a document containing the phrase our fake embedder keys off of
    mock_file = io.BytesIO(b"Gradient descent is an optimization algorithm used to minimize a loss function.")
    upload_res = client.post(
        "/api/v1/documents/upload",
        data={"subject_id": subject_id},
        files=[("files", ("ml_notes.txt", mock_file, "text/plain"))],
        headers=auth_headers,
    )
    assert upload_res.status_code == 201
    assert upload_res.json()[0]["upload_status"] == "completed"

    # Create a chat session and ask a question that should retrieve that chunk
    session_res = client.post(
        "/api/v1/chat/sessions",
        json={"subject_id": subject_id},
        headers=auth_headers,
    )
    session_id = session_res.json()["id"]

    msg_res = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "What is gradient descent?"},
        headers=auth_headers,
    )
    assert msg_res.status_code == 201
    data = msg_res.json()
    assert data["role"] == "assistant"
    assert "Gradient descent minimizes loss" in data["content"]
    assert data["citations"] is not None
    assert data["citations"][0]["filename"] == "ml_notes.txt"

    # Both user and assistant messages should now be stored
    all_msgs = client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=auth_headers)
    assert len(all_msgs.json()) == 2
