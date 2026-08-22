import os
import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.services.chunker import RecursiveCharacterChunker
from app.services.parser import extract_text_from_file

# Create in-memory test DB
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


def test_recursive_character_chunker():
    text = (
        "This is paragraph one. It contains some basic introductory material.\n\n"
        "This is paragraph two. It is a bit longer and has more detailed sentences in it to test the recursive splitting boundaries."
    )
    chunker = RecursiveCharacterChunker(chunk_size=50, chunk_overlap=10)
    chunks = chunker.chunk_text(text)
    
    assert len(chunks) > 0
    # Every chunk should be <= chunk_size (50)
    for chunk in chunks:
        assert len(chunk) <= 50


def test_txt_parser(tmp_path):
    # Create temp text file
    txt_file = tmp_path / "lecture.txt"
    txt_file.write_text("Hello, this is a network design lecture notes file.", encoding="utf-8")
    
    parsed_text = extract_text_from_file(str(txt_file), "txt")
    assert "network design" in parsed_text


def test_document_upload_list_delete(client):
    # 1. Register and Login to get headers
    client.post(
        "/api/v1/auth/register",
        json={"name": "Diana Prince", "email": "diana@example.com", "password": "wonderwomanpass"},
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "diana@example.com", "password": "wonderwomanpass"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create a subject
    sub_res = client.post(
        "/api/v1/subjects/",
        json={"name": "Artificial Intelligence", "code": "AI-701", "semester": 7},
        headers=headers,
    )
    subject_id = sub_res.json()["id"]

    # 3. Upload a mock text file
    mock_file_content = b"This is module 1 notes about heuristic search algorithms. A* Search uses f(n) = g(n) + h(n)."
    mock_file = io.BytesIO(mock_file_content)
    
    # Form data: subject_id and files (using multipart upload format)
    response = client.post(
        "/api/v1/documents/upload",
        data={"subject_id": subject_id},
        files=[("files", ("heuristic_search.txt", mock_file, "text/plain"))],
        headers=headers,
    )
    
    assert response.status_code == 201
    res_data = response.json()
    assert len(res_data) == 1
    doc_id = res_data[0]["id"]
    assert res_data[0]["filename"] == "heuristic_search.txt"
    assert res_data[0]["upload_status"] == "completed"

    # 4. List documents for subject
    list_res = client.get(f"/api/v1/documents/subject/{subject_id}", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1
    assert list_res.json()[0]["filename"] == "heuristic_search.txt"

    # 5. Delete document
    delete_res = client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
    assert delete_res.status_code == 200
    assert "deleted successfully" in delete_res.json()["detail"]

    # Verify document list is empty now
    list_empty_res = client.get(f"/api/v1/documents/subject/{subject_id}", headers=headers)
    assert len(list_empty_res.json()) == 0
