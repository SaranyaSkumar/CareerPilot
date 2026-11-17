"""Jooble job search.

Documented request: POST https://jooble.org/api/{api_key} with a JSON body.
A New Zealand key is requested at https://nz.jooble.org/api/about. A key from
jooble.org returns US listings only. JOOBLE_API_BASE can point at another
official Jooble host such as https://nz.jooble.org/api.
"""

from __future__ import annotations

import os
from urllib.parse import quote, urlsplit

import httpx

from app.job_providers.http import get_http_client, wait_turn
from app.job_providers.types import (
    NormalizedJob,
    ProviderError,
    SearchQuery,
    html_to_text,
    one_line,
    parse_datetime,
)

COUNTRY_NAMES = {
    "nz": "New Zealand",
    "au": "Australia",
    "gb": "United Kingdom",
    "us": "United States",
    "ca": "Canada",
}


def jooble_api_key() -> str:
    return os.getenv("JOOBLE_API_KEY", "").strip()


def jooble_configured() -> bool:
    key = jooble_api_key()
    return bool(key) and not any(character in key for character in "/?#% \n\r\t")


def jooble_endpoint() -> str:
    key = jooble_api_key()
    if not jooble_configured():
        raise ProviderError("Jooble is not configured.")
    base = os.getenv("JOOBLE_API_BASE", "https://jooble.org/api").strip()
    parts = urlsplit(base)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not (host == "jooble.org" or host.endswith(".jooble.org")):
        raise ProviderError("Jooble is not configured.")
    path = parts.path.rstrip("/")
    return f"https://{host}{path}/{quote(key, safe='')}"


def jooble_location(query: SearchQuery) -> str:
    location = query.location.strip()
    if location:
        return location[:200]
    return COUNTRY_NAMES.get(query.country, "New Zealand")


def parse_jooble_results(payload: object, *, fallback_location: str) -> list[NormalizedJob]:
    if not isinstance(payload, dict):
        raise ProviderError("Jooble did not return listings.")
    results = payload.get("jobs")
    if not isinstance(results, list):
        raise ProviderError("Jooble did not return listings.")
    jobs: list[NormalizedJob] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        title = one_line(item.get("title"), 200)
        url = one_line(item.get("link"), 2000)
        if not title or not url:
            continue
        description = html_to_text(item.get("snippet") or "")
        employment = one_line(item.get("type"), 80)
        if employment and employment.casefold() not in description.casefold():
            description = f"{employment}\n{description}".strip()
        jobs.append(NormalizedJob(
            title=title,
            company=one_line(item.get("company"), 200),
            location=one_line(item.get("location"), 200) or one_line(fallback_location, 200) or "New Zealand",
            salary=one_line(item.get("salary"), 200),
            description=description[:8000],
            source="Jooble",
            url=url,
            posted_at=parse_datetime(item.get("updated")),
        ))
    return jobs


def fetch_jooble(query: SearchQuery) -> list[NormalizedJob]:
    endpoint = jooble_endpoint()
    body = {
        "keywords": query.provider_keywords(),
        "location": jooble_location(query),
        "page": "1",
        "ResultOnPage": 20,
        "companysearch": False,
    }
    wait_turn("jooble")
    try:
        response = get_http_client().post(
            endpoint,
            json=body,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=8.0,
        )
    except httpx.TimeoutException:
        raise ProviderError("Jooble took too long to respond.") from None
    except httpx.HTTPError:
        raise ProviderError("Jooble could not be reached.") from None
    if response.status_code == 429:
        raise ProviderError("Jooble's daily request limit was reached.", rate_limited=True)
    if response.status_code in {401, 403}:
        raise ProviderError("Jooble rejected the API key.")
    if response.status_code != 200:
        raise ProviderError("Jooble did not return listings.")
    try:
        payload = response.json()
    except ValueError:
        raise ProviderError("Jooble did not return listings.") from None
    return parse_jooble_results(payload, fallback_location=query.location)
