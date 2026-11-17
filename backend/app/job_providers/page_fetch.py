"""Read a public job page the user pasted, when the site allows it.

SEEK, LinkedIn, Indeed, and Trade Me are never downloaded. Other http(s)
pages may be fetched with a short timeout. Private and link-local addresses
are refused. JSON-LD JobPosting is preferred, then the page title and description.
"""

from __future__ import annotations

import ipaddress
import json
import re
import socket
from collections.abc import Callable
from urllib.parse import urljoin, urlsplit

import httpx

from app.job_providers.http import get_http_client
from app.job_providers.types import html_to_text, one_line, parse_datetime

PASTE_REQUIRED = (
    "Paste the job description for SEEK, LinkedIn, Indeed, and Trade Me links. "
    "CareerPilot does not download those pages."
)
PASTE_INSTEAD = "That link could not be read. Paste the job title and description instead."
PUBLIC_LINK = "Enter a public http or https link."

BLOCKED_HOST_SUFFIXES = (
    "seek.co.nz",
    "seek.com.au",
    "seek.com",
    "linkedin.com",
    "lnkd.in",
    "indeed.com",
    "indeed.co.nz",
    "indeed.co.uk",
    "trademe.co.nz",
    "trademe.com",
)

USER_AGENT = "CareerPilot/1.0 (+https://careerpilot-eight-iota.vercel.app)"
MAX_BYTES = 500_000
Resolver = Callable[[str], list[ipaddress.IPv4Address | ipaddress.IPv6Address]]

_resolver: Resolver | None = None


class FetchError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


def set_resolver(resolver: Resolver | None) -> None:
    global _resolver
    _resolver = resolver


def host_is_blocked(host: str) -> bool:
    name = host.lower().rstrip(".")
    return any(name == suffix or name.endswith("." + suffix) for suffix in BLOCKED_HOST_SUFFIXES)


def _default_resolver(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise FetchError(PASTE_INSTEAD) from exc
    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        try:
            addresses.append(ipaddress.ip_address(info[4][0]))
        except ValueError:
            continue
    return addresses


def assert_public_http_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise FetchError(PUBLIC_LINK)
    if parts.username or parts.password:
        raise FetchError(PUBLIC_LINK)
    host = parts.hostname.lower().rstrip(".")
    if host_is_blocked(host):
        raise FetchError(PASTE_REQUIRED)
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        addresses = (_resolver or _default_resolver)(host)
    if not addresses or any(not address.is_global for address in addresses):
        raise FetchError(PASTE_INSTEAD)
    return url.strip()


def _meta_content(page: str, *names: str) -> str:
    for name in names:
        pattern = (
            rf'<meta[^>]+(?:name|property)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']'
            rf'|<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:name|property)=["\']{re.escape(name)}["\']'
        )
        match = re.search(pattern, page, flags=re.I)
        if match:
            return html_to_text(next(group for group in match.groups() if group))
    return ""


def _page_title(page: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", page, flags=re.I | re.S)
    if not match:
        return ""
    title = html_to_text(match.group(1))
    return one_line(re.split(r"\s+[|\-–—]\s+", title, maxsplit=1)[0], 200)


def find_job_posting(node: object) -> dict | None:
    if isinstance(node, list):
        for item in node:
            found = find_job_posting(item)
            if found:
                return found
        return None
    if not isinstance(node, dict):
        return None
    kinds = node.get("@type")
    if isinstance(kinds, str):
        kinds = [kinds]
    if isinstance(kinds, list) and any(str(kind).lower() == "jobposting" for kind in kinds):
        return node
    for key in ("@graph", "mainEntity"):
        if key in node:
            found = find_job_posting(node[key])
            if found:
                return found
    return None


def _organisation_name(value: object) -> str:
    if isinstance(value, str):
        return one_line(value, 200)
    if isinstance(value, dict):
        return one_line(value.get("name"), 200)
    return ""


def _location_name(value: object) -> str:
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, str):
        return one_line(value, 200)
    if not isinstance(value, dict):
        return ""
    address = value.get("address")
    if isinstance(address, str):
        return one_line(address, 200)
    if isinstance(address, dict):
        locality = one_line(address.get("addressLocality"), 80)
        region = one_line(address.get("addressRegion"), 80)
        country = one_line(address.get("addressCountry"), 80)
        return one_line(", ".join(part for part in (locality, region, country) if part), 200)
    return one_line(value.get("name"), 200)


def _salary_text(value: object) -> str:
    if isinstance(value, str):
        return one_line(value, 200)
    if isinstance(value, list):
        value = value[0] if value else None
    if not isinstance(value, dict):
        return ""
    currency = one_line(value.get("currency"), 12)
    amount = value.get("value")
    low = high = unit = ""
    if isinstance(amount, dict):
        low = one_line(amount.get("minValue") or amount.get("value"), 20)
        high = one_line(amount.get("maxValue"), 20)
        unit = one_line(amount.get("unitText"), 20)
    elif amount not in (None, ""):
        low = one_line(amount, 20)
    if low and high and low != high:
        numbers = f"{low}–{high}"
    else:
        numbers = low or high
    return one_line(" ".join(part for part in (currency, numbers, unit) if part), 200)


def parse_public_job_page(page: str) -> dict[str, object]:
    posting: dict | None = None
    for match in re.finditer(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        page,
        flags=re.I | re.S,
    ):
        try:
            payload = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            continue
        posting = find_job_posting(payload)
        if posting:
            break
    if posting:
        title = one_line(posting.get("title"), 200)
        description = html_to_text(posting.get("description") or "")[:20000]
        return {
            "title": title,
            "company": _organisation_name(posting.get("hiringOrganization")),
            "location": _location_name(posting.get("jobLocation")),
            "description": description,
            "salary": _salary_text(posting.get("baseSalary")),
            "posted_at": parse_datetime(posting.get("datePosted")),
        }
    title = one_line(_meta_content(page, "og:title", "twitter:title"), 200) or _page_title(page)
    description = html_to_text(
        _meta_content(page, "og:description", "description", "twitter:description")
    )[:20000]
    return {
        "title": title,
        "company": "",
        "location": "",
        "description": description,
        "salary": "",
        "posted_at": None,
    }


def _read_limited(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > MAX_BYTES:
            raise FetchError(PASTE_INSTEAD)
        chunks.append(chunk)
    return b"".join(chunks)


def fetch_public_job_page(url: str) -> dict[str, object]:
    current = url.strip()
    client = get_http_client()
    for _ in range(3):
        current = assert_public_http_url(current)
        try:
            with client.stream(
                "GET",
                current,
                headers={"Accept": "text/html,application/xhtml+xml", "User-Agent": USER_AGENT},
                timeout=httpx.Timeout(5.0, connect=3.0),
                follow_redirects=False,
            ) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise FetchError(PASTE_INSTEAD)
                    current = urljoin(current, location)
                    continue
                if response.status_code != 200:
                    raise FetchError(PASTE_INSTEAD)
                content_type = response.headers.get("content-type", "").lower()
                if not any(kind in content_type for kind in ("html", "text/plain", "json")):
                    raise FetchError(PASTE_INSTEAD)
                body = _read_limited(response)
        except FetchError:
            raise
        except httpx.TimeoutException:
            raise FetchError(PASTE_INSTEAD) from None
        except httpx.HTTPError:
            raise FetchError(PASTE_INSTEAD) from None
        page = body.decode("utf-8", errors="replace")
        parsed = parse_public_job_page(page)
        if not parsed["title"] and not parsed["description"]:
            raise FetchError(PASTE_INSTEAD)
        return parsed
    raise FetchError(PASTE_INSTEAD)
