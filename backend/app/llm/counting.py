"""LLM wrapper that counts calls per chat turn (budget: <= 2 in the normal path) and
records each one as a generation span in the trace."""

from typing import TypeVar

from pydantic import BaseModel

from app.llm.gemini import LLMClient
from app.observability.tracing import NOOP, Tracer

T = TypeVar("T", bound=BaseModel)


class CountingLLM:
    def __init__(self, llm: LLMClient, tracer: Tracer = NOOP) -> None:
        self._llm, self._tracer = llm, tracer
        self.calls = 0

    def generate_structured(self, prompt: str, schema: type[T], *, system: str | None = None) -> T:
        self.calls += 1
        with self._tracer.span(
            f"llm:{schema.__name__}", as_type="generation", input=prompt[:1500]
        ) as span:
            out = self._llm.generate_structured(prompt, schema, system=system)
            span.update(output=out.model_dump())
            return out
