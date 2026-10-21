from app.ai.schemas import CoverLetterDraft
from tests.conftest import JD, fill_profile, make_user


def setup(client):
    make_user(client)
    fill_profile(client)
    aid = client.post("/api/v1/analyses", json={"jd_text": JD}).json()["id"]
    rid = client.post(f"/api/v1/analyses/{aid}/resumes", json={"template_key": "modern"}).json()["id"]
    return aid, rid


def test_generate_cover_letter_linked_to_resume(client):
    aid, rid = setup(client)
    r = client.post(f"/api/v1/analyses/{aid}/cover-letters", json={"resume_id": rid})
    assert r.status_code == 201, r.text
    letter = r.json()
    assert letter["resume_id"] == rid and letter["status"] == "draft"
    assert letter["content"].startswith("Dear Hiring Manager,") and letter["content"].endswith("Sincerely,\nAsha Kumar")
    assert "Backend Developer" in letter["title"]


def test_cover_letter_cannot_link_someone_elses_resume(client):
    aid, rid = setup(client)
    client.post("/api/v1/auth/logout")
    make_user(client, "other@example.com")
    aid2 = client.post("/api/v1/analyses", json={"jd_text": JD}).json()["id"]
    assert client.post(f"/api/v1/analyses/{aid2}/cover-letters", json={"resume_id": rid}).status_code == 404


def test_fabricated_sentences_removed_from_letter(client, llm):
    aid, _ = setup(client)
    llm.overrides[CoverLetterDraft] = lambda s, p: CoverLetterDraft(paragraphs=[
        "I am excited to apply. I led a team of 12 engineers.", "I built REST APIs with FastAPI.", "I know Kubernetes well.",
    ])
    text = client.post(f"/api/v1/analyses/{aid}/cover-letters", json={}).json()["content"]
    assert "12 engineers" not in text and "Kubernetes" not in text
    assert "I am excited to apply." in text and "FastAPI" in text


def test_letter_fully_unsupported_is_an_error_not_a_made_up_letter(client, llm):
    aid, _ = setup(client)
    llm.overrides[CoverLetterDraft] = lambda s, p: CoverLetterDraft(paragraphs=["I managed 50 engineers on Kubernetes."])
    r = client.post(f"/api/v1/analyses/{aid}/cover-letters", json={})
    assert r.status_code == 502


def test_edit_regenerate_download_delete_letter(client):
    aid, rid = setup(client)
    lid = client.post(f"/api/v1/analyses/{aid}/cover-letters", json={"resume_id": rid}).json()["id"]
    r = client.patch(f"/api/v1/cover-letters/{lid}", json={"content": "Edited body.\n\nSecond paragraph.", "status": "saved"})
    assert r.json()["content"].startswith("Edited") and r.json()["status"] == "saved"
    assert client.post(f"/api/v1/cover-letters/{lid}/regenerate").json()["version"] == 2
    assert client.get(f"/api/v1/cover-letters/{lid}/download?format=pdf").content[:5] == b"%PDF-"
    assert client.get(f"/api/v1/cover-letters/{lid}/download?format=docx").content[:2] == b"PK"
    assert client.delete(f"/api/v1/cover-letters/{lid}").status_code == 204
    assert client.get(f"/api/v1/cover-letters/{lid}").status_code == 404


def test_history_filter_search_paginate(client):
    aid, rid = setup(client)
    client.post(f"/api/v1/analyses/{aid}/cover-letters", json={"resume_id": rid})
    client.post(f"/api/v1/analyses/{aid}/cover-letters", json={"resume_id": rid})
    allp = client.get("/api/v1/documents").json()
    assert allp["total"] == 3 and {d["type"] for d in allp["items"]} == {"resume", "cover_letter"}
    assert client.get("/api/v1/documents?type=resume").json()["total"] == 1
    assert client.get("/api/v1/documents?type=cover_letter").json()["total"] == 2
    assert client.get("/api/v1/documents?q=cover").json()["total"] == 2
    assert client.get("/api/v1/documents?q=100%25").json()["total"] == 0  # % is not a wildcard
    p1 = client.get("/api/v1/documents?page=1&page_size=2").json()
    p2 = client.get("/api/v1/documents?page=2&page_size=2").json()
    assert len(p1["items"]) == 2 and len(p2["items"]) == 1
    assert client.get("/api/v1/documents?type=bogus").status_code == 422


def test_history_is_private(client):
    setup(client)
    client.post("/api/v1/auth/logout")
    make_user(client, "other@example.com")
    assert client.get("/api/v1/documents").json()["total"] == 0


def test_dashboard_and_templates(client):
    setup(client)
    d = client.get("/api/v1/dashboard/stats").json()
    assert d["counts"] == {"resumes": 1, "cover_letters": 0, "analyses": 1}
    assert d["profile_completeness"] == 100 and d["average_keyword_score"] is not None and len(d["recent"]) == 1
    assert [t["key"] for t in client.get("/api/v1/templates").json()] == ["classic", "modern", "compact"]


def test_analysis_lists_its_documents(client):
    aid, rid = setup(client)
    a = client.get(f"/api/v1/analyses/{aid}").json()
    assert [d["id"] for d in a["documents"]["resumes"]] == [rid]


def test_error_format_and_unknown_route(client):
    assert client.get("/api/v1/nope").json()["error"]["code"] == "NOT_FOUND"
    assert client.get("/api/v1/health").json() == {"status": "ok"}
