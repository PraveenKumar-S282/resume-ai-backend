from tests.conftest import JD, fill_profile, make_user


def test_analysis_matches_against_real_profile(client):
    make_user(client)
    fill_profile(client)
    r = client.post("/api/v1/analyses", json={"jd_text": JD})
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["job_title"] == "Backend Developer" and a["company"] == "Acme Labs"
    m = a["match_result"]
    assert set(m["matched_skills"]) >= {"Python", "FastAPI", "REST APIs", "React"}
    assert set(m["missing_skills"]) == {"Docker", "Kubernetes"}
    assert 0 < m["keyword_score"] < 100 and m["extraction"] == "llm"
    assert any("Docker" in s["message"] for s in m["suggestions"])


def test_jd_is_sent_to_llm_as_delimited_data(client, llm):
    make_user(client)
    client.post("/api/v1/analyses", json={"jd_text": JD})
    prompt = llm.calls[0][1]
    assert "<job_description>" in prompt and JD.splitlines()[0] in prompt


def test_lexicon_fallback_when_ai_is_down(client, llm):
    make_user(client)
    fill_profile(client)
    llm.fail = True
    r = client.post("/api/v1/analyses", json={"jd_text": JD})
    assert r.status_code == 201
    a = r.json()
    assert a["match_result"]["extraction"] == "lexicon"
    assert "python" in a["required_skills"]


def test_short_jd_rejected(client):
    make_user(client)
    r = client.post("/api/v1/analyses", json={"jd_text": "too short"})
    assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == "jd_text"


def test_list_get_delete_and_isolation(client):
    make_user(client, "a@example.com")
    aid = client.post("/api/v1/analyses", json={"jd_text": JD}).json()["id"]
    page = client.get("/api/v1/analyses").json()
    assert page["total"] == 1 and page["items"][0]["id"] == aid
    client.post("/api/v1/auth/logout")
    make_user(client, "b@example.com")
    assert client.get(f"/api/v1/analyses/{aid}").status_code == 404
    assert client.delete(f"/api/v1/analyses/{aid}").status_code == 404
    assert client.get("/api/v1/analyses").json()["total"] == 0
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "Passw0rd123"})
    assert client.delete(f"/api/v1/analyses/{aid}").status_code == 204
