"""Text cleaning, normalisation and quality checks (empty / short / repeated / spam)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

STOPWORDS = frozenset(
    """a an the and or but if of to in on at for with from by about as is are was were be been being
    i me my we our you your he she it they them his her their this that these those not no have has had
    do does did will would can could should may might am so than then too very just also into out up
    down over under again still more most some any all when what which who whom how why there here""".split()
)
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPAM = re.compile(r"\b(viagra|casino|lottery|crypto giveaway|click here|free money|buy now|work from home)\b", re.I)


def clean_text(value: str) -> str:
    value = _CTRL.sub("", value.replace("\r\n", "\n").replace("\r", "\n"))
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def keyword_set(text: str) -> set[str]:
    return {w for w in normalize(text).split() if len(w) > 2 and w not in STOPWORDS}


def truncate(text: str | None, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def first_sentence(text: str, limit: int = 220) -> str:
    text = " ".join(text.split())
    match = re.match(r"(.+?[.!?])(\s|$)", text)
    return truncate(match.group(1) if match else text, limit)


@dataclass
class TextQuality:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def assess_text_quality(text: str) -> TextQuality:
    q = TextQuality()
    stripped = (text or "").strip()
    words = re.findall(r"\w{2,}", stripped)
    if not stripped:
        q.errors.append("The complaint description is empty.")
        return q
    if len(stripped) < 15 or len(words) < 4:
        q.errors.append(
            "The complaint description is too short. Please describe what happened, when, and who is affected."
        )
        return q
    if re.search(r"(.)\1{9,}", stripped):
        q.warnings.append("repeated characters")
    lowered = [w.lower() for w in words]
    if len(lowered) >= 8 and len(set(lowered)) / len(lowered) < 0.3:
        q.warnings.append("repeated words")
    sentences = [normalize(s) for s in re.split(r"[.!?\n]+", stripped) if normalize(s)]
    if len(sentences) >= 3 and len(set(sentences)) <= len(sentences) / 2:
        q.warnings.append("duplicated sentences")
    if len(re.findall(r"https?://|www\.", stripped, re.I)) >= 3 or _SPAM.search(stripped):
        q.warnings.append("spam-like content")
    return q
