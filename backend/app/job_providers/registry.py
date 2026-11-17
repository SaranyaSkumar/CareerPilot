"""The job providers CareerPilot knows how to use."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.job_providers.adzuna import adzuna_configured, fetch_adzuna
from app.job_providers.jooble import fetch_jooble, jooble_configured
from app.job_providers.linkouts import indeed_url, linkedin_url, seek_url, trademe_url
from app.job_providers.types import NormalizedJob, SearchQuery

Fetch = Callable[[SearchQuery], list[NormalizedJob]]
LinkBuilder = Callable[[SearchQuery], str]


@dataclass(frozen=True)
class JobProvider:
    key: str
    label: str
    kind: str
    description: str
    configured: Callable[[], bool]
    default_enabled: bool = True
    fetch: Fetch | None = None
    search_url: LinkBuilder | None = None
    attribution_label: str = ""
    attribution_url: str = ""

    @property
    def is_configured(self) -> bool:
        return self.configured()


def _always_ready() -> bool:
    return True


PROVIDERS: tuple[JobProvider, ...] = (
    JobProvider(
        key="adzuna",
        label="Adzuna",
        kind="api",
        description="Pulls New Zealand listings from the Adzuna API when ADZUNA_APP_ID and ADZUNA_APP_KEY are set.",
        configured=adzuna_configured,
        fetch=fetch_adzuna,
        attribution_label="Jobs by Adzuna",
        attribution_url="https://www.adzuna.co.nz/",
    ),
    JobProvider(
        key="jooble",
        label="Jooble",
        kind="api",
        description="Pulls listings from the Jooble API when JOOBLE_API_KEY is set. Use a key from the New Zealand Jooble API page.",
        configured=jooble_configured,
        fetch=fetch_jooble,
        attribution_label="Jobs by Jooble",
        attribution_url="https://nz.jooble.org/",
    ),
    JobProvider(
        key="seek",
        label="SEEK",
        kind="link",
        description="Opens a SEEK New Zealand search filled in from your headline, skills, and location. CareerPilot does not download SEEK pages.",
        configured=_always_ready,
        search_url=seek_url,
    ),
    JobProvider(
        key="linkedin",
        label="LinkedIn",
        kind="link",
        description="Opens LinkedIn Jobs with your search filled in. CareerPilot does not download LinkedIn pages.",
        configured=_always_ready,
        search_url=linkedin_url,
    ),
    JobProvider(
        key="indeed",
        label="Indeed",
        kind="link",
        description="Opens Indeed New Zealand with your search filled in. CareerPilot does not download Indeed pages.",
        configured=_always_ready,
        search_url=indeed_url,
    ),
    JobProvider(
        key="trademe",
        label="Trade Me Jobs",
        kind="link",
        description="Opens Trade Me Jobs with your search filled in. CareerPilot does not download Trade Me pages.",
        configured=_always_ready,
        search_url=trademe_url,
    ),
)


def providers() -> tuple[JobProvider, ...]:
    return PROVIDERS


def get_provider(key: str) -> JobProvider | None:
    for provider in PROVIDERS:
        if provider.key == key:
            return provider
    return None
