"""Thin LLM client interface. Only Gemini is implemented; callers depend on the Protocol."""

from typing import Protocol, TypeVar

from pydantic import BaseModel

from app.config import get_settings
from app.llm.retry import call_with_429_backoff

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    def generate_structured(self, prompt: str, schema: type[T], *, system: str | None = None) -> T:
        """One LLM call returning a validated Pydantic object."""
        ...


class GeminiClient:
    def __init__(self) -> None:
        from google import genai

        s = get_settings()
        self._client = genai.Client(api_key=s.gemini_api_key.get_secret_value())
        self._model = s.llm_model

    def generate_structured(self, prompt: str, schema: type[T], *, system: str | None = None) -> T:
        from google.genai import types

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            system_instruction=system,
            temperature=0,
        )
        resp = call_with_429_backoff(
            lambda: self._client.models.generate_content(
                model=self._model, contents=prompt, config=config
            )
        )
        return schema.model_validate_json(resp.text)
