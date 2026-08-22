import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app

# Create an in-memory SQLite database for testing, isolated from production MySQL
SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(name="db_session")
def fixture_db_session():
    """Create a clean in-memory database schema for each test session."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(name="client")
def fixture_client(db_session):
    """Override get_db dependency with testing database session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_register_and_login(client):
    # Register user
    reg_response = client.post(
        "/api/v1/auth/register",
        json={"name": "Alice Smith", "email": "alice@example.com", "password": "securepassword123"},
    )
    assert reg_response.status_code == 201
    reg_data = reg_response.json()
    assert reg_data["email"] == "alice@example.com"
    assert "password_hash" not in reg_data

    # Attempt registration with duplicate email
    duplicate_response = client.post(
        "/api/v1/auth/register",
        json={"name": "Alice Clone", "email": "alice@example.com", "password": "anotherpassword"},
    )
    assert duplicate_response.status_code == 400
    assert duplicate_response.json()["detail"] == "Email already registered"

    # Login user
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "securepassword123"},
    )
    assert login_response.status_code == 200
    login_data = login_response.json()
    assert "access_token" in login_data
    assert login_data["token_type"] == "bearer"
    assert login_data["user"]["email"] == "alice@example.com"

    # Try invalid login
    bad_login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "wrongpassword"},
    )
    assert bad_login_response.status_code == 401


def test_auth_me_protected_route(client):
    # Register & Login to get token
    client.post(
        "/api/v1/auth/register",
        json={"name": "Bob Jones", "email": "bob@example.com", "password": "secretpassword"},
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "secretpassword"},
    )
    token = login_res.json()["access_token"]

    # Request /me with no token
    unauthorized_res = client.get("/api/v1/auth/me")
    assert unauthorized_res.status_code == 401

    # Request /me with valid token
    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["name"] == "Bob Jones"
    assert me_data["email"] == "bob@example.com"


def test_subject_management(client):
    # Register & Login
    client.post(
        "/api/v1/auth/register",
        json={"name": "Carol Danvers", "email": "carol@example.com", "password": "capmarvelpass"},
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "carol@example.com", "password": "capmarvelpass"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create first subject (Semester 6)
    sub1_res = client.post(
        "/api/v1/subjects/",
        json={"name": "Software Engineering", "code": "CS-602", "semester": 6},
        headers=headers,
    )
    assert sub1_res.status_code == 201
    sub1_data = sub1_res.json()
    assert sub1_data["name"] == "Software Engineering"
    assert sub1_data["semester"] == 6

    # Attempt to create duplicate subject in same semester
    sub1_dup_res = client.post(
        "/api/v1/subjects/",
        json={"name": "Software Engineering", "code": "CS-602", "semester": 6},
        headers=headers,
    )
    assert sub1_dup_res.status_code == 400

    # Create second subject (Semester 5)
    client.post(
        "/api/v1/subjects/",
        json={"name": "Database Management Systems", "code": "CS-501", "semester": 5},
        headers=headers,
    )

    # List all subjects
    list_all_res = client.get("/api/v1/subjects/", headers=headers)
    assert list_all_res.status_code == 200
    assert len(list_all_res.json()) == 2

    # List filtered by semester
    list_filtered_res = client.get("/api/v1/subjects/?semester=5", headers=headers)
    assert list_filtered_res.status_code == 200
    filtered_data = list_filtered_res.json()
    assert len(filtered_data) == 1
    assert filtered_data[0]["name"] == "Database Management Systems"
