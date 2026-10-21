"""Test-only stand-in for the AI provider. Never used outside tests."""
import json
import re
from typing import Callable

from pydantic import BaseModel

from app.ai.llm_client import LLMError
from app.ai.schemas import CoverLetterDraft, JDExtraction, ResumeDraft


def _candidate(prompt: str) -> dict:
    m = re.search(r"<candidate_profile>\n(.*?)\n</candidate_profile>", prompt, re.S)
    return json.loads(m.group(1))


class FakeLLM:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.overrides: dict[type, Callable[[str, str], BaseModel]] = {}
        self.fail = False

    def generate_json(self, system: str, prompt: str, schema):
        self.calls.append((schema.__name__, prompt))
        if self.fail:
            raise LLMError("fake provider down")
        if schema in self.overrides:
            return self.overrides[schema](system, prompt)
        if schema is JDExtraction:
            return JDExtraction(
                job_title="Backend Developer", company="Acme Labs",
                required_skills=["Python", "FastAPI", "REST APIs", "Docker", "Kubernetes"],
                preferred_skills=["React", "AWS"], experience_requirement="2+ years",
                keywords=["microservices", "APIs"],
            )
        if schema is ResumeDraft:
            c = _candidate(prompt)
            return ResumeDraft(
                summary="Developer who builds web applications with Python and React.",
                experience=[{"id": e["id"], "bullets": list(e["bullets"])} for e in c["experience"]],
                projects=[{"id": p["id"], "bullets": [p["description"]] if p["description"] else []} for p in c["projects"]],
            )
        if schema is CoverLetterDraft:
            return CoverLetterDraft(paragraphs=[
                "I am excited to apply for the Backend Developer role.",
                "My internship involved building REST APIs with FastAPI and MySQL.",
                "I would welcome the chance to discuss how I can contribute.",
            ])
        raise AssertionError(f"unexpected schema {schema}")
