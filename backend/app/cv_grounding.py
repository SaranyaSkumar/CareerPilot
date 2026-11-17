"""Turn a structured model draft into suggestions grounded in the saved CV.

The model is instructed not to invent facts. These checks do not trust that
claim: a suggestion is flagged when it introduces a number, month, or
organisation that is absent from the saved CV, or when too little of its
wording appears there. The job description is not part of the corpus, so a
requirement copied from the listing is not treated as the candidate's fact.
"""

from __future__ import annotations

import re

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?%?")
_LIST_MARKER = re.compile(r"(?m)^\s*(?:[-*•]|\d+[.)])\s+")
_ORG_INTRO = re.compile(
    r"\b(?:at|for|with|via|joining|joined|join)\s+"
    r"([A-Z][\w.&'-]*(?:\s+[A-Z][\w.&'-]*){0,3})"
)
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9+.#/-]{3,}")
_MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)
_OVERLAP_STOP = {
    "with",
    "from",
    "that",
    "this",
    "their",
    "them",
    "they",
    "have",
    "been",
    "were",
    "into",
    "using",
    "used",
    "across",
    "within",
    "while",
    "where",
    "which",
    "about",
    "after",
    "before",
    "through",
    "under",
    "over",
    "your",
    "role",
    "work",
    "team",
    "also",
    "than",
    "then",
    "such",
    "including",
    "include",
    "more",
    "most",
    "some",
    "other",
    "only",
    "able",
    "make",
    "made",
    "help",
    "helped",
}


def indexed_lines(text: str) -> list[tuple[int, str]]:
    """Non-empty lines with their index in `text.split("\\n")`."""

    return [(index, line) for index, line in enumerate(text.split("\n")) if line.strip()]


def cv_corpus(facts: dict[str, str]) -> str:
    return "\n".join(facts.get(field, "") for field in ("name", "headline", "summary", "experience", "skills", "education"))


def _without_list_markers(text: str) -> str:
    return _LIST_MARKER.sub("", text)


def _numbers(text: str) -> set[str]:
    return {match.group(0) for match in _NUMBER.finditer(text)}


def _novel_organisations(suggestion: str, corpus: str) -> list[str]:
    corpus_cf = corpus.casefold()
    found: list[str] = []
    for match in _ORG_INTRO.finditer(suggestion):
        phrase = match.group(1).strip(" .")
        if phrase and phrase.casefold() not in corpus_cf:
            found.append(phrase)
    return found


def _month_note(suggestion: str, corpus: str) -> str:
    corpus_cf = corpus.casefold()
    for month in _MONTHS:
        if month in corpus_cf:
            continue
        if re.search(rf"\b{month}\b", suggestion, re.IGNORECASE):
            return f"Introduces the month {month}, which is not in your saved CV."
    if re.search(r"\bMay\b", suggestion) and "may" not in corpus_cf:
        return "Introduces the month May, which is not in your saved CV."
    return ""


def _overlap_note(suggestion: str, corpus: str) -> str:
    words = [
        word.casefold()
        for word in _WORD.findall(_without_list_markers(suggestion))
        if word.casefold() not in _OVERLAP_STOP
    ]
    if len(words) < 4:
        return ""
    corpus_cf = corpus.casefold()
    hits = sum(1 for word in words if word in corpus_cf)
    if hits / len(words) < 0.5:
        return "Too little of this wording is supported by your saved CV."
    return ""


def grounding_note(suggestion: str, corpus: str) -> str:
    """Empty when the wording stays within the saved CV; otherwise the reason."""

    notes: list[str] = []
    novel_numbers = sorted(_numbers(_without_list_markers(suggestion)) - _numbers(corpus))
    if novel_numbers:
        notes.append(
            "Introduces a number or date that is not in your saved CV: " + ", ".join(novel_numbers) + "."
        )
    month = _month_note(suggestion, corpus)
    if month:
        notes.append(month)
    organisations = _novel_organisations(suggestion, corpus)
    if organisations:
        notes.append(
            "Introduces an organisation that is not in your saved CV: " + ", ".join(organisations) + "."
        )
    overlap = _overlap_note(suggestion, corpus)
    if overlap:
        notes.append(overlap)
    return " ".join(notes)


def preserve_marker(original: str, suggested: str) -> str:
    match = re.match(r"^(\s*(?:[-*•]|\d+[.)])\s+)", original)
    cleaned = suggested.strip()
    if match and not re.match(r"^(?:[-*•]|\d+[.)])\s+", cleaned):
        return f"{match.group(1)}{cleaned}"
    return cleaned


# A missing job keyword may be surfaced only when the saved CV already uses
# that term or an obvious equivalent. Frameworks and products are not inferred
# from a language or a nearby tool.
_KEYWORD_ALIASES: dict[str, tuple[str, ...]] = {
    "postgresql": ("postgresql", "postgres"),
    "postgres": ("postgresql", "postgres"),
    "ci/cd": ("ci/cd", "cicd", "continuous integration", "continuous delivery"),
    "gcp": ("gcp", "google cloud"),
    "aws": ("aws", "amazon web services"),
    "azure": ("azure", "microsoft azure"),
    "node.js": ("node.js", "nodejs"),
    "kubernetes": ("kubernetes", "k8s"),
    "golang": ("golang",),
    "go": ("golang", "go"),
}


def term_supported(term: str, corpus: str) -> str | None:
    """Return the phrase already in the CV when it supports `term`.

    The result is empty when the keyword would be a new skill. Callers must
    not add it unless the user explicitly confirms it.
    """

    needle = " ".join(term.casefold().split())
    if len(needle) < 2 or len(needle) > 80:
        return None
    candidates = list(_KEYWORD_ALIASES.get(needle, (needle,)))
    if re.fullmatch(r"[a-z]{4,}", needle):
        candidates.extend((f"{needle}ed", f"{needle}ing", f"{needle}s"))
        if needle.endswith("e"):
            candidates.append(f"{needle[:-1]}ing")
    for candidate in dict.fromkeys(candidates):
        if re.search(r"(?<!\w)" + re.escape(candidate) + r"(?!\w)", corpus.casefold()):
            return candidate
    return None


def find_skill_phrase(skill: str, facts: dict[str, str]) -> str | None:
    needle = " ".join(skill.split())
    if len(needle) < 2 or len(needle) > 80:
        return None
    skills_field = facts.get("skills", "")
    for part in re.split(r"[\n,]", skills_field):
        if part.strip().casefold() == needle.casefold():
            return part.strip()
    corpus = cv_corpus(facts)
    if re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", corpus, re.IGNORECASE):
        return needle
    return None


def match_saved_bullets(experience: str, requested: list[str]) -> list[tuple[int, str]] | None:
    """Pair each requested bullet with one saved experience line.

    Returns None when any requested bullet is missing or repeated more times
    than it appears in the saved CV. Matching is on the stripped line.
    """

    pools: dict[str, list[tuple[int, str]]] = {}
    for index, line in enumerate(experience.split("\n")):
        key = line.strip()
        if key:
            pools.setdefault(key, []).append((index, line))
    matched: list[tuple[int, str]] = []
    for bullet in requested:
        pool = pools.get(bullet.strip())
        if not pool:
            return None
        matched.append(pool.pop(0))
    return matched


def _clip(text: str, limit: int = 400) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def assess_rewrite(
    *,
    original: str,
    suggested: str,
    corpus: str,
    model_supported: bool,
    model_note: str,
) -> tuple[str, bool, str]:
    """Return `(after, unsupported, note)` for one rewritten block."""

    after = preserve_marker(original, suggested)
    notes: list[str] = []
    if not model_supported:
        notes.append(_clip(model_note) or "The model could not ground this wording in your saved CV.")
    grounding = grounding_note(after, corpus)
    if grounding:
        notes.append(grounding)
    note = _clip(" ".join(notes), 500)
    return after, bool(note), note
