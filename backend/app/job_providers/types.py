"""Normalised listings and the search built from a user's settings."""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel

TRACKING_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
}


class ProviderError(Exception):
    """A provider call failed in a way that is safe to show to the user."""

    def __init__(self, message: str, *, rate_limited: bool = False) -> None:
        super().__init__(message)
        self.rate_limited = rate_limited


class NormalizedJob(BaseModel):
    title: str
    company: str = ""
    location: str = "New Zealand"
    salary: str = ""
    description: str = ""
    source: str
    url: str = ""
    posted_at: datetime | None = None


@dataclass(frozen=True)
class SearchQuery:
    keywords: str
    location: str
    country: str
    remote: str

    def provider_keywords(self) -> str:
        keywords = self.keywords.strip()
        if self.remote == "remote" and "remote" not in keywords.casefold():
            keywords = f"{keywords} remote".strip()
        return keywords or "jobs"

    def fingerprint(self) -> str:
        raw = "|".join(
            [
                self.country,
                self.remote,
                normalise(self.location),
                normalise(self.provider_keywords()),
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class LinkOut(BaseModel):
    provider_key: str
    label: str
    url: str


def normalise(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def dedupe_key(title: str, company: str, location: str) -> str:
    parts = [normalise(part)[:120] for part in (title, company, location)]
    if not parts[0]:
        return ""
    return "|".join(parts)[:400]


def canonical_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return raw[:2000]
    host = parts.hostname.lower()
    netloc = host
    if parts.port and not (
        (parts.scheme.lower() == "http" and parts.port == 80)
        or (parts.scheme.lower() == "https" and parts.port == 443)
    ):
        netloc = f"{host}:{parts.port}"
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_KEYS and not key.lower().startswith("utm_")
    ]
    return urlunsplit((parts.scheme.lower(), netloc, path, urlencode(sorted(query_pairs)), ""))[:2000]


def one_line(value: object, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).replace("\x00", "").strip()
    return text[:limit]


def clean_text(value: object, limit: int) -> str:
    return str(value or "").replace("\x00", "").strip()[:limit]


def html_to_text(value: object) -> str:
    raw = str(value or "").replace("\x00", "")
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"(?i)</li>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "• ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    text = re.sub(r"(\.\d{6})\d+", r"\1", text)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class ProviderRun(BaseModel):
    provider_key: str
    label: str
    status: str
    message: str
    fetched: int = 0


class SearchEcho(BaseModel):
    keywords: str
    location: str
    country: str
    remote_preference: str
    keywords_from_profile: bool = False


def dedupe_jobs(jobs: list[NormalizedJob]) -> list[NormalizedJob]:
    """Drop later listings that repeat a URL or a title, company, and location."""

    kept: list[NormalizedJob] = []
    seen_urls: set[str] = set()
    seen_keys: set[str] = set()
    for job in jobs:
        url = canonical_url(job.url)
        key = dedupe_key(job.title, job.company, job.location)
        if url and url in seen_urls:
            continue
        if key and key in seen_keys:
            continue
        if url:
            seen_urls.add(url)
        if key:
            seen_keys.add(key)
        if url and url != job.url:
            job = job.model_copy(update={"url": url})
        kept.append(job)
    return kept
