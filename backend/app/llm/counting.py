"""LLM wrapper that counts calls per chat turn (budget: <= 2 in the normal path) and
records each one as a generation span in the trace. Also enforces the global daily
LLM-call budget (raises QuotaExceeded before calling Gemini when it is used up)."""

from typing import TypeVar

from pydantic import BaseModel

from app.llm.gemini import LLMClient
from app.observability.tracing import NOOP, Tracer
from app.quota import QuotaGuard

T = TypeVar("T", bound=BaseModel)


class CountingLLM:
    def __init__(
        self, llm: LLMClient, tracer: Tracer = NOOP, quota: QuotaGuard | None = None
    ) -> None:
        self._llm, self._tracer, self._quota = llm, tracer, quota
        self.calls = 0

    def generate_structured(self, prompt: str, schema: type[T], *, system: str | None = None) -> T:
        if self._quota is not None:
            self._quota.consume()  # raises QuotaExceeded once the day's budget is spent
        self.calls += 1
        with self._tracer.span(
            f"llm:{schema.__name__}", as_type="generation", input=prompt[:1500]
        ) as span:
            out = self._llm.generate_structured(prompt, schema, system=system)
            span.update(output=out.model_dump())
            return out
