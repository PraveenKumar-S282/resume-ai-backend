"""LLM provider abstraction. Credentials are read from the backend environment only."""
import logging
from functools import lru_cache
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import settings

log = logging.getLogger("app.llm")
T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """The AI provider failed or returned unusable output."""


class LLMClient(Protocol):
    def generate_json(self, system: str, prompt: str, schema: type[T]) -> T: ...


class GeminiClient:
    def __init__(self, api_key: str, model: str, timeout_seconds: int):
        from google import genai
        from google.genai import types

        self._types = types
        self._model = model
        self._client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=timeout_seconds * 1000))

    def generate_json(self, system: str, prompt: str, schema: type[T]) -> T:
        from google.genai import errors

        config = self._types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.3,
            max_output_tokens=4096,
        )
        last_error: Exception | None = None
        for attempt in range(2):  # one retry on malformed output
            try:
                resp = self._client.models.generate_content(model=self._model, contents=prompt, config=config)
                return schema.model_validate_json(resp.text or "")
            except (ValidationError, ValueError) as exc:
                last_error = exc
                log.warning("LLM returned invalid JSON (attempt %s): %s", attempt + 1, exc)
            except errors.APIError as exc:
                log.error("Gemini API error: %s", exc)
                raise LLMError("The AI service returned an error. Please try again shortly.") from exc
            except Exception as exc:  # network, timeout, etc.
                log.error("Gemini call failed: %s", exc)
                raise LLMError("The AI service could not be reached. Please try again shortly.") from exc
        raise LLMError("The AI service returned an unreadable response. Please try again.") from last_error


class UnconfiguredClient:
    def generate_json(self, system: str, prompt: str, schema: type[T]) -> T:
        raise LLMError("The AI service is not configured. Set GEMINI_API_KEY on the server.")


@lru_cache
def _build() -> LLMClient:
    if not settings.GEMINI_API_KEY:
        return UnconfiguredClient()
    return GeminiClient(settings.GEMINI_API_KEY, settings.GEMINI_MODEL, settings.LLM_TIMEOUT_SECONDS)


def get_llm() -> LLMClient:
    """FastAPI dependency. Tests override this with a fake."""
    return _build()
