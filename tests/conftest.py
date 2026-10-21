import os

# Must be set before the app is imported.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["BCRYPT_ROUNDS"] = "4"
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest-only-0123456789"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.ai.llm_client import get_llm
from app.db.base import Base
from app.db.seed import seed_templates
from app.db.session import get_db, make_engine
import app.models  # noqa: F401  (register tables)
from app.main import app as fastapi_app
from tests.fakes import FakeLLM


TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite://")  # set to a MySQL URL to run the suite against MySQL


@pytest.fixture()
def db_session():
    kwargs = {"poolclass": StaticPool} if TEST_DB_URL.startswith("sqlite") else {}
    engine = make_engine(TEST_DB_URL, **kwargs)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as s:
        seed_templates(s)
    yield Session
    engine.dispose()


@pytest.fixture()
def llm():
    return FakeLLM()


@pytest.fixture()
def client(db_session, llm):
    def _db():
        with db_session() as s:
            yield s

    fastapi_app.dependency_overrides[get_db] = _db
    fastapi_app.dependency_overrides[get_llm] = lambda: llm
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


PASSWORD = "Passw0rd123"


def make_user(client: TestClient, email="asha@example.com", name="Asha Kumar") -> TestClient:
    r = client.post("/api/v1/auth/register", json={"full_name": name, "email": email, "password": PASSWORD})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return client


def fill_profile(c: TestClient) -> None:
    """A realistic, fully populated profile."""
    c.put("/api/v1/profile", json={
        "headline": "Full stack developer", "phone": "9876543210", "location": "Chennai, India",
        "summary": "Final-year CSE student who builds web apps with Python and React.",
        "github_url": "https://github.com/asha", "achievements": ["Won college hackathon 2025"],
    })
    c.post("/api/v1/profile/education", json={"institution": "Jayalakshmi Institute of Technology", "degree": "B.E.", "field": "Computer Science", "start_date": "2023-08-01", "end_date": "2027-05-01", "grade": "8.4 CGPA"})
    for name, cat in [("Python", "language"), ("JavaScript", "language"), ("React", "framework"), ("FastAPI", "framework"), ("MySQL", "database"), ("Git", "tool"), ("REST APIs", "framework")]:
        assert c.post("/api/v1/profile/skills", json={"name": name, "category": cat}).status_code == 201
    c.post("/api/v1/profile/experience", json={
        "role": "Full Stack Developer Intern", "company": "AngamTech", "start_date": "2025-06-01", "end_date": "2025-08-01",
        "bullets": ["Built REST APIs with FastAPI and MySQL", "Developed React dashboards for internal teams"],
    })
    c.post("/api/v1/profile/projects", json={
        "title": "Smart Village Portal", "description": "Complaint registration portal built with React, Flask and MySQL.",
        "tech_stack": ["React", "Flask", "MySQL"],
    })


JD = """Backend Developer
Acme Labs is hiring a Backend Developer.
Required: Python, FastAPI, REST APIs, Docker, Kubernetes. 2+ years of experience.
Preferred: React, AWS. You will build and maintain microservices and APIs used by thousands of customers."""
