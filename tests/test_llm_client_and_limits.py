"""GeminiClient logic tested with a stubbed SDK client (no network, no API key)."""
from types import SimpleNamespace

import pytest

from app.ai.llm_client import GeminiClient, LLMError, UnconfiguredClient
from app.ai.schemas import CoverLetterDraft, JDExtraction
from app.core.rate_limit import limiter
from tests.conftest import make_user


def make_client(responses):
    """responses: list of str (response text) or Exception, consumed one call at a time."""
    from google.genai import types

    queue = list(responses)
    calls = []

    def generate_content(model, contents, config):
        calls.append((model, config))
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(text=item)

    c = GeminiClient.__new__(GeminiClient)
    c._types, c._model = types, "test-model"
    c._client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    return c, calls


def test_valid_json_is_parsed_and_request_is_structured():
    c, calls = make_client(['{"job_title": "Dev", "required_skills": ["Python"]}'])
    out = c.generate_json("sys", "prompt", JDExtraction)
    assert out.job_title == "Dev" and out.required_skills == ["Python"]
    model, config = calls[0]
    assert model == "test-model" and config.response_mime_type == "application/json" and config.system_instruction == "sys"


def test_malformed_json_is_retried_once():
    c, calls = make_client(["not json at all", '{"paragraphs": ["Hello."]}'])
    assert c.generate_json("s", "p", CoverLetterDraft).paragraphs == ["Hello."]
    assert len(calls) == 2


def test_two_bad_responses_become_llm_error():
    c, _ = make_client(["nope", "still nope"])
    with pytest.raises(LLMError):
        c.generate_json("s", "p", JDExtraction)


def test_provider_failure_becomes_friendly_llm_error():
    c, _ = make_client([TimeoutError("boom")])
    with pytest.raises(LLMError) as e:
        c.generate_json("s", "p", JDExtraction)
    assert "boom" not in str(e.value)  # internal details are not shown to users


def test_unconfigured_client_explains_itself():
    with pytest.raises(LLMError, match="GEMINI_API_KEY"):
        UnconfiguredClient().generate_json("s", "p", JDExtraction)


def test_login_is_rate_limited(client):
    make_user(client)
    limiter.enabled = True
    limiter.reset()
    try:
        codes = [client.post("/api/v1/auth/login", json={"email": "asha@example.com", "password": "wrong-pass1"}).status_code for _ in range(12)]
    finally:
        limiter.enabled = False
        limiter.reset()
    assert codes[0] == 401 and 429 in codes
    assert client.post("/api/v1/auth/login", json={"email": "asha@example.com", "password": "wrong-pass1"}).status_code == 401
