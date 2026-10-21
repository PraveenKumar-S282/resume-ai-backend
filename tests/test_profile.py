import pytest

from tests.conftest import fill_profile, make_user

SECTIONS = {
    "education": ({"institution": "JIT", "degree": "B.E."}, {"grade": "9.0"}),
    "experience": ({"role": "Intern", "company": "AngamTech", "bullets": ["Built APIs", " "]}, {"is_current": True}),
    "skills": ({"name": "Python", "category": "language"}, {"proficiency": "advanced"}),
    "projects": ({"title": "Portal", "tech_stack": ["React", " "]}, {"description": "A portal"}),
    "certifications": ({"name": "AWS Cloud Practitioner"}, {"issuer": "AWS"}),
}


@pytest.mark.parametrize("section", SECTIONS)
def test_section_crud(client, section):
    make_user(client)
    create, patch = SECTIONS[section]
    r = client.post(f"/api/v1/profile/{section}", json=create)
    assert r.status_code == 201, r.text
    item = r.json()
    assert client.get(f"/api/v1/profile/{section}").json()[0]["id"] == item["id"]
    r = client.patch(f"/api/v1/profile/{section}/{item['id']}", json=patch)
    assert r.status_code == 200 and all(r.json()[k] == v for k, v in patch.items())
    assert client.delete(f"/api/v1/profile/{section}/{item['id']}").status_code == 204
    assert client.get(f"/api/v1/profile/{section}").json() == []


def test_blank_list_entries_are_cleaned(client):
    make_user(client)
    r = client.post("/api/v1/profile/experience", json=SECTIONS["experience"][0]).json()
    assert r["bullets"] == ["Built APIs"]


@pytest.mark.parametrize("section", SECTIONS)
def test_users_cannot_touch_each_others_items(client, section):
    make_user(client, "a@example.com")
    item = client.post(f"/api/v1/profile/{section}", json=SECTIONS[section][0]).json()
    client.post("/api/v1/auth/logout")
    make_user(client, "b@example.com")
    assert client.get(f"/api/v1/profile/{section}").json() == []
    assert client.patch(f"/api/v1/profile/{section}/{item['id']}", json=SECTIONS[section][1]).status_code == 404
    assert client.delete(f"/api/v1/profile/{section}/{item['id']}").status_code == 404


def test_duplicate_skill_is_409_ignoring_case(client):
    make_user(client)
    client.post("/api/v1/profile/skills", json={"name": "Python", "category": "language"})
    r = client.post("/api/v1/profile/skills", json={"name": "python", "category": "language"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "DUPLICATE_SKILL"


def test_required_field_cannot_be_nulled(client):
    make_user(client)
    item = client.post("/api/v1/profile/education", json=SECTIONS["education"][0]).json()
    r = client.patch(f"/api/v1/profile/education/{item['id']}", json={"institution": None})
    assert r.status_code == 422


def test_profile_put_and_completeness(client):
    make_user(client)
    assert client.get("/api/v1/profile/completeness").json()["percentage"] == 0
    fill_profile(client)
    c = client.get("/api/v1/profile/completeness").json()
    assert c["percentage"] == 100 and c["missing"] == []
    p = client.get("/api/v1/profile").json()
    assert p["headline"] == "Full stack developer" and p["achievements"] == ["Won college hackathon 2025"]


def test_invalid_skill_category_rejected(client):
    make_user(client)
    assert client.post("/api/v1/profile/skills", json={"name": "X", "category": "magic"}).status_code == 422
