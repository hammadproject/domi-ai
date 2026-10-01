"""Output guard: rule-based check of a drafted answer for steering and subjective
neighborhood claims. Offending sentences are removed deterministically (no LLM call);
if nothing usable is left the answer is replaced with a safe fallback."""

import logging
import re

from pydantic import BaseModel

from app.guardrails.input_guard import guardrail_counter

log = logging.getLogger(__name__)

_NOUN = (
    r"(?:neighbou?rhoods?|areas?|communit(?:y|ies)|parts? of town|sides? of town|streets?|"
    r"locations?|districts?|suburbs?|enclaves?|addresses|address|blocks?)"
)
_GROUPS = (
    r"(?:young |first[- ]time )?(?:families|family|kids|children|professionals|couples|singles|"
    r"retirees|seniors|students|bachelors|empty[- ]nesters|singles|women|men)"
)
_ETHNIC = (
    r"(?:white|black|hispanic|latino|latina|asian|indian|mexican|chinese|korean|muslim|jewish|"
    r"christian|catholic|hindu|immigrant|minority)"
)

OUTPUT_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "subjective_quality",
        re.compile(
            rf"\b(?:desirable|prestigious|upscale|exclusive|up[- ]and[- ]coming|trendy|charming|"
            rf"vibrant|sought[- ]after|quiet|peaceful|friendly|nice|great|good|bad|rough|sketchy|"
            rf"high[- ]end|high[- ]class|low[- ]class|affluent|wealthy|poor|run[- ]down|"
            rf"welcoming|lovely|wonderful|best)\s+(?:and\s+\w+\s+)?{_NOUN}\b|"
            rf"\b{_NOUN}\s+(?:is|are|feels?|seems?)\s+(?:a\s+)?(?:very\s+|really\s+)?"
            rf"(?:quiet|great|nice|desirable|friendly|vibrant|peaceful|prestigious|welcoming|"
            rf"lovely|diverse)\b|"
            rf"\b(?:prestigious|exclusive|upscale|desirable|up[- ]and[- ]coming)\b",
            re.I,
        ),
    ),
    (
        "safety",
        re.compile(
            rf"\bcrime\b|\b(?:low|high|no)[- ]crime\b|\bunsafe\b|\bdangerous\b|\bsketchy\b|"
            rf"\bsafe(?:r|st)?\s+(?:and\s+\w+\s+)?{_NOUN}\b|"
            rf"\b{_NOUN}\s+(?:is|are|feels?|seems?)\s+(?:very\s+|really\s+)?safe\b|"
            rf"\bsafe,",
            re.I,
        ),
    ),
    (
        "steering_group",
        re.compile(
            rf"\b(?:family|kid|child|senior|student|lgbt|lgbtq)[- ]friendly\b|"
            rf"\b(?:good|great|perfect|ideal|best|suited|suitable|excellent|right|made)\s+(?:for|to)\s+"
            rf"(?:a\s+|the\s+)?{_GROUPS}\b|"
            rf"^ideal for {_GROUPS}|\bperfect for {_GROUPS}",
            re.I,
        ),
    ),
    (
        "demographic",
        re.compile(
            rf"\bdemographics?\b|\bracial(?:ly)?\b|\bethnic(?:ally|ity)?\b|\bdivers(?:e|ity)\b|"
            rf"\b(?:predominantly|mostly|majority|mainly|heavily)\s+{_ETHNIC}\b|"
            rf"\b{_ETHNIC}\s+{_NOUN}\b",
            re.I,
        ),
    ),
    (
        "school_quality",
        re.compile(
            r"\b(?:good|great|top|excellent|best|highly[- ]rated|top[- ]rated)\s+schools?\b", re.I
        ),
    ),
]

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_LINE_SENTENCES = re.compile(r"(?<=[.!?])\s+")
_MARKER = re.compile(r"^\s*(?:[-+•]|\d+\.)\s+")  # bullet / numbered-list prefix
FALLBACK_TEXT = (
    "I can only describe listings using their objective details (price, size, bedrooms, "
    "year built, HOA and similar). I can't characterise neighborhoods or who they suit."
)


class Violation(BaseModel):
    category: str
    text: str


class OutputGuardResult(BaseModel):
    text: str
    modified: bool
    blocked: bool
    violations: list[Violation]


def find_violations(text: str) -> list[Violation]:
    found: list[Violation] = []
    for raw in _SENTENCE_SPLIT.split(text):
        sentence = _MARKER.sub("", raw)  # judge the words, not the list marker
        for category, pattern in OUTPUT_RULES:
            if pattern.search(sentence):
                found.append(Violation(category=category, text=sentence.strip()))
                break
    return found


def check_output(text: str) -> OutputGuardResult:
    """Drop sentences that steer or make subjective neighborhood claims."""
    violations = find_violations(text)
    if not violations:
        return OutputGuardResult(text=text, modified=False, blocked=False, violations=[])

    for v in violations:
        guardrail_counter[f"output:{v.category}"] += 1
        log.warning("guardrail output flagged: category=%s", v.category)

    bad = {v.text for v in violations}
    lines: list[str] = []
    for line in text.split("\n"):
        m = _MARKER.match(line)
        marker = m.group(0) if m else ""
        sentences = _LINE_SENTENCES.split(line[len(marker) :])
        kept = [x for x in sentences if x.strip() and x.strip() not in bad]
        if kept:  # keep the bullet / numbering and any untouched sentences on this line
            lines.append(marker + " ".join(kept))
        elif not line.strip() and lines and lines[-1] != "":
            lines.append("")  # preserve paragraph breaks
    cleaned = "\n".join(lines).strip()
    if not cleaned:
        return OutputGuardResult(
            text=FALLBACK_TEXT, modified=True, blocked=True, violations=violations
        )
    return OutputGuardResult(text=cleaned, modified=True, blocked=False, violations=violations)
