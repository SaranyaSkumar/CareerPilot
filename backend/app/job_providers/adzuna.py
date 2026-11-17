"""Adzuna job search.

Documented endpoint:
https://api.adzuna.com/v1/api/jobs/{country}/search/{page}
Credentials are the app_id and app_key query parameters from
https://developer.adzuna.com/.
"""

from __future__ import annotations

import os

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

ADZUNA_COUNTRIES = {
    "nz", "au", "gb", "us", "ca", "de", "fr", "at", "nl", "pl", "it", "es",
    "br", "in", "mx", "sg", "za",
}
COUNTRY_WIDE = {
    "nz": {"new zealand", "nz", "aotearoa"},
    "au": {"australia", "au"},
    "gb": {"united kingdom", "uk", "gb", "great britain"},
    "us": {"united states", "usa", "us", "united states of america"},
    "ca": {"canada", "ca"},
}
CURRENCY = {
    "nz": "NZD",
    "au": "AUD",
    "gb": "GBP",
    "us": "USD",
    "ca": "CAD",
    "sg": "SGD",
    "za": "ZAR",
    "in": "INR",
    "br": "BRL",
    "mx": "MXN",
}


def adzuna_app_id() -> str:
    return os.getenv("ADZUNA_APP_ID", "").strip()


def adzuna_app_key() -> str:
    return os.getenv("ADZUNA_APP_KEY", "").strip()


def adzuna_configured() -> bool:
    return bool(adzuna_app_id() and adzuna_app_key())


def _where(query: SearchQuery) -> str:
    location = query.location.strip()
    if not location:
        return ""
    if location.casefold() in COUNTRY_WIDE.get(query.country, set()):
        return ""
    return location


def _salary(item: dict, country: str) -> str:
    low = item.get("salary_min")
    high = item.get("salary_max")
    try:
        low_value = int(float(low)) if low not in (None, "") else None
        high_value = int(float(high)) if high not in (None, "") else None
    except (TypeError, ValueError):
        return ""
    if not low_value and not high_value:
        return ""
    currency = CURRENCY.get(country, "")
    prefix = f"{currency} " if currency else ""

    def money(amount: int) -> str:
        return f"{amount:,}"

    if low_value and high_value and low_value != high_value:
        text = f"{prefix}{money(low_value)}–{money(high_value)}".strip()
    else:
        text = f"{prefix}{money(low_value or high_value or 0)}".strip()
    if item.get("salary_is_predicted") in {1, True, "1"}:
        text += " (estimated)"
    return one_line(text, 200)


def parse_adzuna_results(payload: object, *, fallback_location: str, country: str) -> list[NormalizedJob]:
    if not isinstance(payload, dict):
        raise ProviderError("Adzuna did not return listings.")
    results = payload.get("results")
    if not isinstance(results, list):
        raise ProviderError("Adzuna did not return listings.")
    jobs: list[NormalizedJob] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        title = one_line(item.get("title"), 200)
        url = one_line(item.get("redirect_url"), 2000)
        if not title or not url:
            continue
        company_node = item.get("company")
        if isinstance(company_node, dict):
            company = one_line(company_node.get("display_name"), 200)
        else:
            company = one_line(company_node, 200)
        location_node = item.get("location")
        if isinstance(location_node, dict):
            location = one_line(location_node.get("display_name"), 200)
        else:
            location = one_line(location_node, 200)
        description = html_to_text(item.get("description") or "")[:8000]
        jobs.append(NormalizedJob(
            title=title,
            company=company,
            location=location or one_line(fallback_location, 200) or "New Zealand",
            salary=_salary(item, country),
            description=description,
            source="Adzuna",
            url=url,
            posted_at=parse_datetime(item.get("created")),
        ))
    return jobs


def fetch_adzuna(query: SearchQuery) -> list[NormalizedJob]:
    if query.country not in ADZUNA_COUNTRIES:
        raise ProviderError("Adzuna does not cover that country in this workspace.")
    app_id = adzuna_app_id()
    app_key = adzuna_app_key()
    if not app_id or not app_key:
        raise ProviderError("Adzuna is not configured.")
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": "20",
        "content-type": "application/json",
        "sort_by": "date",
    }
    keywords = query.provider_keywords()
    if keywords and keywords != "jobs":
        params["what"] = keywords
    where = _where(query)
    if where:
        params["where"] = where
    wait_turn("adzuna")
    try:
        response = get_http_client().get(
            f"https://api.adzuna.com/v1/api/jobs/{query.country}/search/1",
            params=params,
            headers={"Accept": "application/json"},
            timeout=8.0,
        )
    except httpx.TimeoutException:
        raise ProviderError("Adzuna took too long to respond.") from None
    except httpx.HTTPError:
        raise ProviderError("Adzuna could not be reached.") from None
    if response.status_code == 429:
        raise ProviderError("Adzuna's rate limit was reached.", rate_limited=True)
    if response.status_code in {401, 403}:
        raise ProviderError("Adzuna rejected the API key.")
    if response.status_code != 200:
        raise ProviderError("Adzuna did not return listings.")
    try:
        payload = response.json()
    except ValueError:
        raise ProviderError("Adzuna did not return listings.") from None
    return parse_adzuna_results(payload, fallback_location=query.location, country=query.country)
