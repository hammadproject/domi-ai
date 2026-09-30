"""Input guard: rules first; the LLM classifier runs ONLY for ambiguous messages."""

import json
import logging
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.guardrails import rules
from app.llm.gemini import GeminiClient, LLMClient

log = logging.getLogger(__name__)

# Guardrail trigger counter (exported to tracing / metrics later). Keyed by category.
guardrail_counter: Counter[str] = Counter()

CACHE_PATH = Path(__file__).resolve().parents[3] / "data" / "cache" / "guard_llm.json"


class InputGuardResult(BaseModel):
    action: Literal["allow", "refuse"]
    category: str | None = None
    decided_by: Literal["rules", "llm", "fallback"] = "rules"
    reason: str = ""
    reply: str | None = None  # canned refusal text when action == "refuse"


class Classification(BaseModel):
    steering: bool
    category: Literal["steering", "demographic", "familial_status", "neighborhood_quality", "none"]
    reason: str


CLASSIFIER_SYSTEM = """You are a Fair Housing compliance classifier for a home-search assistant.
Decide if the user message asks the assistant to recommend, filter, rank or avoid areas or
homes based on protected characteristics or their proxies: race, color, religion, sex,
disability, familial status, national origin, age, or who lives in an area (demographics,
"type of people", safety/crime characterisations of neighborhoods).
steering=true examples: "best area for Muslims", "is this neighborhood good for kids",
"find a Spanish-speaking neighborhood".
steering=false examples: requests about the home itself or objective location features,
e.g. "homes within walking distance of a church", "near a mosque", "wheelchair accessible
single-story", "I have 3 kids and need 4 bedrooms". A user mentioning their own religion or
family only to state a need is fine as long as they are not asking to be steered by who lives
somewhere. Return JSON only."""


def normalise(message: str) -> str:
    text = message.lower().replace("’", "'")
    return rules.ALLOW_PHRASES.sub(" ", text)


def _cache_get(key: str) -> Classification | None:
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return Classification.model_validate(data[key]) if key in data else None
    except (OSError, ValueError, KeyError):
        return None


def _cache_put(key: str, value: Classification) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        data[key] = value.model_dump()
        CACHE_PATH.write_text(json.dumps(data, indent=1), encoding="utf-8")
    except OSError:
        log.warning("could not write guard classifier cache")


def _refuse(category: str, decided_by: str, reason: str) -> InputGuardResult:
    guardrail_counter[f"input:{category}"] += 1
    log.warning(
        "guardrail input refused: category=%s by=%s reason=%s", category, decided_by, reason
    )
    return InputGuardResult(
        action="refuse",
        category=category,
        decided_by=decided_by,  # type: ignore[arg-type]
        reason=reason,
        reply=rules.REFUSALS[category],
    )


def classify_with_llm(message: str, llm: LLMClient | None = None) -> Classification:
    """One small LLM call, cached on disk by message hash."""
    key = sha256(message.strip().lower().encode()).hexdigest()
    cached = _cache_get(key)
    if cached is not None:
        return cached
    llm = llm or GeminiClient()
    result = llm.generate_structured(
        f"User message: {message}", Classification, system=CLASSIFIER_SYSTEM
    )
    _cache_put(key, result)
    return result


def check_input(
    message: str, *, llm: LLMClient | None = None, use_llm: bool = True
) -> InputGuardResult:
    """Clear steering -> refuse (rules). Clearly fine -> allow. Ambiguous -> LLM classifier.

    If the classifier is needed but unavailable or fails, FAIL CLOSED with a gentle
    'rephrase' reply rather than risk a steering answer. With use_llm=False, ambiguous
    messages are allowed but reported via reason='ambiguous-unresolved' (used by evals).
    """
    text = normalise(message)
    hard = rules.hard_category(text)
    if hard:
        return _refuse(hard[0], "rules", hard[1])

    if not rules.is_ambiguous(text):
        return InputGuardResult(action="allow", reason="no rule matched")

    if not use_llm:
        return InputGuardResult(
            action="allow", decided_by="fallback", reason="ambiguous-unresolved"
        )
    try:
        verdict = classify_with_llm(message, llm)
    except Exception as exc:  # quota, network, malformed output
        log.warning("guard classifier failed (%s); failing closed", type(exc).__name__)
        return _refuse("unverified", "fallback", f"classifier unavailable: {type(exc).__name__}")
    if verdict.steering:
        category = verdict.category if verdict.category != "none" else "steering"
        return _refuse(category, "llm", verdict.reason)
    return InputGuardResult(action="allow", decided_by="llm", reason=verdict.reason)
