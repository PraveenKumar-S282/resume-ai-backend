from app.ai.schemas import ResumeDraft
from tests.conftest import JD, fill_profile, make_user


def setup_analysis(client):
    make_user(client)
    fill_profile(client)
    return client.post("/api/v1/analyses", json={"jd_text": JD}).json()["id"]


def test_missing_profile_data_is_reported_not_invented(client):
    make_user(client)
    aid = client.post("/api/v1/analyses", json={"jd_text": JD}).json()["id"]
    r = client.post(f"/api/v1/analyses/{aid}/resumes", json={"template_key": "classic"})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "MISSING_PROFILE_DATA"
    assert {d["field"] for d in err["details"]} == {"education", "skills", "experience"}


def test_generate_resume_uses_only_profile_data(client):
    aid = setup_analysis(client)
    r = client.post(f"/api/v1/analyses/{aid}/resumes", json={"template_key": "modern", "preferences": {"tone": "confident", "length": "one_page"}})
    assert r.status_code == 201, r.text
    res = r.json()
    c = res["content"]
    assert res["template_key"] == "modern" and res["status"] == "draft" and res["version"] == 1
    assert c["header"]["name"] == "Asha Kumar" and c["header"]["email"] == "asha@example.com"
    assert c["education"][0]["dates"] == "2023 to 2027" and c["education"][0]["grade"] == "8.4 CGPA"
    assert c["experience"][0]["company"] == "AngamTech" and c["experience"][0]["start"] == "Jun 2025"
    skills = {s for g in c["skills"] for s in g["items"]}
    assert skills == {"Python", "JavaScript", "React", "FastAPI", "MySQL", "Git", "REST APIs"}  # nothing added from the JD
    assert "Docker" not in str(c) and "Kubernetes" not in str(c)
    assert set(res["scores"]) >= {"keyword", "completeness", "relevance", "verification"}


def test_job_relevant_skills_are_listed_first(client):
    aid = setup_analysis(client)
    c = client.post(f"/api/v1/analyses/{aid}/resumes", json={}).json()["content"]
    langs = next(g for g in c["skills"] if g["category"] == "Languages")["items"]
    assert langs[0] == "Python"  # required by the job, ahead of JavaScript


def test_fabricated_ai_content_is_stripped(client, llm):
    aid = setup_analysis(client)

    def bad(system, prompt):
        import json, re
        cand = json.loads(re.search(r"<candidate_profile>\n(.*?)\n</candidate_profile>", prompt, re.S).group(1))
        e = cand["experience"][0]
        return ResumeDraft(
            summary="Expert in Kubernetes. Builds web apps with Python.",
            experience=[{"id": e["id"], "bullets": ["Cut latency by 70% using Docker", "Built REST APIs with FastAPI and MySQL"]}],
            projects=[],
        )

    llm.overrides[ResumeDraft] = bad
    res = client.post(f"/api/v1/analyses/{aid}/resumes", json={}).json()
    c = res["content"]
    text = str(c)
    assert "Kubernetes" not in text and "70%" not in text and "Docker" not in text
    assert c["summary"] == "Builds web apps with Python."
    assert c["experience"][0]["bullets"] == ["Built REST APIs with FastAPI and MySQL"]
    assert res["scores"]["verification"]["removed"]
    assert sum(1 for n, _ in llm.calls if n == "ResumeDraft") == 2  # one corrective retry


def test_item_without_source_text_gets_no_invented_bullets(client, llm):
    make_user(client)
    fill_profile(client)
    client.post("/api/v1/profile/experience", json={"role": "Volunteer", "company": "NGO"})
    aid = client.post("/api/v1/analyses", json={"jd_text": JD}).json()["id"]

    def inventive(system, prompt):
        import json, re
        cand = json.loads(re.search(r"<candidate_profile>\n(.*?)\n</candidate_profile>", prompt, re.S).group(1))
        return ResumeDraft(summary="", experience=[{"id": e["id"], "bullets": ["Did great work"]} for e in cand["experience"]], projects=[])

    llm.overrides[ResumeDraft] = inventive
    c = client.post(f"/api/v1/analyses/{aid}/resumes", json={}).json()["content"]
    vol = next(e for e in c["experience"] if e["company"] == "NGO")
    assert vol["bullets"] == []


def test_ai_failure_is_502_with_message(client, llm):
    aid = setup_analysis(client)
    llm.fail = True
    r = client.post(f"/api/v1/analyses/{aid}/resumes", json={})
    assert r.status_code == 502 and r.json()["error"]["code"] == "AI_UNAVAILABLE"


def test_invalid_template_and_preferences(client):
    aid = setup_analysis(client)
    assert client.post(f"/api/v1/analyses/{aid}/resumes", json={"template_key": "neon"}).status_code == 422
    assert client.post(f"/api/v1/analyses/{aid}/resumes", json={"preferences": {"tone": "sarcastic"}}).status_code == 422


def test_edit_save_regenerate_delete(client):
    aid = setup_analysis(client)
    rid = client.post(f"/api/v1/analyses/{aid}/resumes", json={}).json()["id"]
    res = client.get(f"/api/v1/resumes/{rid}").json()
    content = res["content"]
    content["summary"] = "My edited summary."
    r = client.patch(f"/api/v1/resumes/{rid}", json={"title": "Final", "template_key": "compact", "content": content, "status": "saved"})
    assert r.status_code == 200
    out = r.json()
    assert out["title"] == "Final" and out["template_key"] == "compact" and out["status"] == "saved" and out["content"]["summary"] == "My edited summary."
    r = client.post(f"/api/v1/resumes/{rid}/regenerate")
    assert r.status_code == 200 and r.json()["version"] == 2 and r.json()["status"] == "draft"
    assert client.delete(f"/api/v1/resumes/{rid}").status_code == 204
    assert client.get(f"/api/v1/resumes/{rid}").status_code == 404


def test_improve_returns_scores_keywords_and_honest_suggestions(client):
    aid = setup_analysis(client)
    rid = client.post(f"/api/v1/analyses/{aid}/resumes", json={}).json()["id"]
    r = client.post(f"/api/v1/resumes/{rid}/improve")
    assert r.status_code == 200
    out = r.json()
    assert set(out["scores"]) == {"keyword", "completeness", "relevance"}
    assert "python" in [k.lower() for k in out["matched_keywords"]]
    assert {"Docker", "Kubernetes"} <= set(out["missing_keywords"])
    msgs = " ".join(s["message"] for s in out["suggestions"])
    assert "only if" in msgs and "truthfully" in msgs  # never tells the user to claim missing skills


def test_resume_needs_its_analysis_to_regenerate_or_improve(client):
    aid = setup_analysis(client)
    rid = client.post(f"/api/v1/analyses/{aid}/resumes", json={}).json()["id"]
    client.delete(f"/api/v1/analyses/{aid}")
    assert client.get(f"/api/v1/resumes/{rid}").json()["analysis_id"] is None  # document is kept
    for path in (f"/api/v1/resumes/{rid}/improve", f"/api/v1/resumes/{rid}/regenerate"):
        r = client.post(path)
        assert r.status_code == 422 and r.json()["error"]["code"] == "ANALYSIS_MISSING"


def test_downloads_are_real_pdf_and_docx(client):
    aid = setup_analysis(client)
    for template in ("classic", "modern", "compact"):
        rid = client.post(f"/api/v1/analyses/{aid}/resumes", json={"template_key": template}).json()["id"]
        pdf = client.get(f"/api/v1/resumes/{rid}/download?format=pdf")
        assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-" and "attachment" in pdf.headers["content-disposition"]
        docx = client.get(f"/api/v1/resumes/{rid}/download?format=docx")
        assert docx.status_code == 200 and docx.content[:2] == b"PK"
    assert client.get(f"/api/v1/resumes/{rid}/download?format=exe").status_code == 422


def test_docx_contains_the_resume_text(client):
    import io
    from docx import Document

    aid = setup_analysis(client)
    rid = client.post(f"/api/v1/analyses/{aid}/resumes", json={}).json()["id"]
    doc = Document(io.BytesIO(client.get(f"/api/v1/resumes/{rid}/download?format=docx").content))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Asha Kumar" in text and "AngamTech" in text and "Smart Village Portal" in text


def test_special_characters_do_not_break_pdf(client):
    aid = setup_analysis(client)
    rid = client.post(f"/api/v1/analyses/{aid}/resumes", json={}).json()["id"]
    content = client.get(f"/api/v1/resumes/{rid}").json()["content"]
    content["summary"] = "R&D <b>engineer</b> with C++ & café skills – “quoted” தமிழ்"
    client.patch(f"/api/v1/resumes/{rid}", json={"content": content})
    assert client.get(f"/api/v1/resumes/{rid}/download?format=pdf").content[:5] == b"%PDF-"


def test_resumes_are_private(client):
    aid = setup_analysis(client)
    rid = client.post(f"/api/v1/analyses/{aid}/resumes", json={}).json()["id"]
    client.post("/api/v1/auth/logout")
    make_user(client, "other@example.com")
    for method, path in [("get", f"/api/v1/resumes/{rid}"), ("patch", f"/api/v1/resumes/{rid}"), ("delete", f"/api/v1/resumes/{rid}"),
                         ("get", f"/api/v1/resumes/{rid}/download?format=pdf"), ("post", f"/api/v1/resumes/{rid}/improve"),
                         ("post", f"/api/v1/analyses/{aid}/resumes")]:
        kwargs = {"json": {}} if method in ("patch", "post") else {}
        assert getattr(client, method)(path, **kwargs).status_code == 404, (method, path)
