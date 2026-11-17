"""Search links for boards that do not offer a listing API we can call.

These URLs open the board's own search. CareerPilot does not download the pages.
"""

from __future__ import annotations

from urllib.parse import urlencode

from app.job_providers.types import SearchQuery


def _keywords(query: SearchQuery) -> str:
    return query.provider_keywords()


def _place(query: SearchQuery) -> str:
    return query.location.strip() or "New Zealand"


def seek_url(query: SearchQuery) -> str:
    return "https://www.seek.co.nz/jobs?" + urlencode({
        "keywords": _keywords(query),
        "where": _place(query),
    })


def linkedin_url(query: SearchQuery) -> str:
    location = _place(query)
    if "new zealand" not in location.casefold() and query.country == "nz":
        location = f"{location}, New Zealand"
    params = {"keywords": _keywords(query), "location": location}
    if query.remote == "remote":
        params["f_WT"] = "2"
    elif query.remote == "onsite":
        params["f_WT"] = "1"
    return "https://www.linkedin.com/jobs/search/?" + urlencode(params)


def indeed_url(query: SearchQuery) -> str:
    return "https://nz.indeed.com/jobs?" + urlencode({
        "q": _keywords(query),
        "l": _place(query),
    })


def trademe_url(query: SearchQuery) -> str:
    text = _keywords(query)
    place = query.location.strip()
    if place and place.casefold() not in {"new zealand", "nz", "aotearoa"}:
        text = f"{text} {place}".strip()
    return "https://www.trademe.co.nz/a/jobs/search?" + urlencode({"search_string": text})
