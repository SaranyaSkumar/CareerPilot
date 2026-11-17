"""Find jobs for one user and remember which sources they want.

Discovery runs when the user clicks Find jobs, or when they call the daily
refresh route. There is no background worker. Provider responses are cached,
and each app-level API key has a daily call ceiling.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user_id
from app.database import get_db
from app.job_providers.adzuna import ADZUNA_COUNTRIES
from app.job_providers.page_fetch import (
    PASTE_INSTEAD,
    PASTE_REQUIRED,
    PUBLIC_LINK,
    FetchError,
    fetch_public_job_page,
    host_is_blocked,
)
from app.job_providers.registry import get_provider, providers
from app.job_providers.types import (
    LinkOut,
    NormalizedJob,
    ProviderError,
    ProviderRun,
    SearchEcho,
    SearchQuery,
    canonical_url,
    dedupe_jobs,
    dedupe_key,
    one_line,
)
from app.jobs import JobResponse
from app.models import (
    CareerProfile,
    JobDiscoverySettings,
    JobListing,
    JobProviderCache,
    JobProviderQuota,
    JobProviderSetting,
)
from app.ownership import get_or_create_for_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jobs", tags=["job discovery"])


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def cache_ttl_seconds() -> int:
    return _int_env("JOB_DISCOVERY_CACHE_SECONDS", 12 * 60 * 60)


def _user_window_seconds(mode: str) -> int:
    if mode == "daily":
        return _int_env("JOB_DISCOVERY_DAILY_SECONDS", 20 * 60 * 60)
    return _int_env("JOB_DISCOVERY_INTERACTIVE_SECONDS", 15 * 60)


def _daily_limit(provider_key: str) -> int:
    if provider_key == "jooble":
        return _int_env("JOOBLE_DAILY_LIMIT", 90)
    if provider_key == "adzuna":
        return _int_env("ADZUNA_DAILY_LIMIT", 250)
    return 0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class ProviderToggle(BaseModel):
    provider_key: str = Field(min_length=1, max_length=40)
    enabled: bool


class SettingsWrite(BaseModel):
    country: str = "nz"
    location: str = Field(default="New Zealand", max_length=200)
    keywords: str = Field(default="", max_length=300)
    remote_preference: Literal["any", "remote", "onsite"] = "any"
    providers: list[ProviderToggle] = Field(default_factory=list)

    @field_validator("country")
    @classmethod
    def supported_country(cls, value: str) -> str:
        code = value.strip().lower()
        if code not in ADZUNA_COUNTRIES:
            raise ValueError("Choose a supported country code.")
        return code

    @field_validator("location", "keywords")
    @classmethod
    def trimmed(cls, value: str) -> str:
        return value.strip()


class ProviderView(BaseModel):
    provider_key: str
    label: str
    kind: str
    description: str
    enabled: bool
    configured: bool
    status: str
    attribution_label: str = ""
    attribution_url: str = ""


class Attribution(BaseModel):
    label: str
    url: str


class SettingsResponse(BaseModel):
    country: str
    location: str
    keywords: str
    remote_preference: str
    last_discovered_at: datetime | None
    search: SearchEcho
    providers: list[ProviderView]
    link_outs: list[LinkOut]
    attributions: list[Attribution]


class DiscoverResponse(BaseModel):
    cached: bool
    discovered_at: datetime | None
    created: int
    updated: int
    duplicates: int
    removed: int
    search: SearchEcho
    providers: list[ProviderRun]
    link_outs: list[LinkOut]
    attributions: list[Attribution]


class FromLinkRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    title: str = Field(default="", max_length=200)
    company: str = Field(default="", max_length=200)
    location: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=20000)


def _keywords(profile: CareerProfile | None, override: str) -> tuple[str, bool]:
    custom = override.strip()
    if custom:
        return custom[:300], False
    if profile is None:
        return "", True
    skills = [part.strip() for part in re.split(r"[,;\n|]+", profile.skills or "") if part.strip()]
    parts: list[str] = []
    headline = (profile.headline or "").strip()
    if headline:
        parts.append(headline)
    parts.extend(skills[:6])
    return " ".join(parts)[:300], True


def _search(settings: JobDiscoverySettings, profile: CareerProfile | None) -> tuple[SearchQuery, bool]:
    keywords, from_profile = _keywords(profile, settings.keywords or "")
    location = (settings.location or "").strip()
    if not location and profile is not None:
        location = (profile.location or "").strip()
    location = location or "New Zealand"
    country = (settings.country or "nz").strip().lower()
    if country not in ADZUNA_COUNTRIES:
        country = "nz"
    remote = settings.remote_preference if settings.remote_preference in {"any", "remote", "onsite"} else "any"
    return SearchQuery(keywords=keywords, location=location[:200], country=country, remote=remote), from_profile


def _echo(query: SearchQuery, from_profile: bool) -> SearchEcho:
    return SearchEcho(
        keywords=query.provider_keywords(),
        location=query.location,
        country=query.country,
        remote_preference=query.remote,
        keywords_from_profile=from_profile,
    )


def _enabled_map(db: Session, user_id: uuid.UUID) -> dict[str, bool]:
    rows = db.query(JobProviderSetting).filter(JobProviderSetting.user_id == user_id).all()
    stored = {row.provider_key: bool(row.enabled) for row in rows}
    return {provider.key: stored.get(provider.key, provider.default_enabled) for provider in providers()}


def _fingerprint(query: SearchQuery, enabled: dict[str, bool]) -> str:
    api_keys = [provider.key for provider in providers() if provider.kind == "api" and enabled.get(provider.key, True)]
    raw = query.fingerprint() + "|" + ",".join(api_keys)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _link_outs(query: SearchQuery, enabled: dict[str, bool]) -> list[LinkOut]:
    items: list[LinkOut] = []
    for provider in providers():
        if provider.kind != "link" or not enabled.get(provider.key, True) or provider.search_url is None:
            continue
        items.append(LinkOut(provider_key=provider.key, label=provider.label, url=provider.search_url(query)))
    return items


def _provider_views(enabled: dict[str, bool]) -> list[ProviderView]:
    views: list[ProviderView] = []
    for provider in providers():
        turned_on = enabled.get(provider.key, True)
        configured = provider.is_configured
        if not turned_on:
            status = "disabled"
        elif not configured:
            status = "not_configured"
        else:
            status = "ready"
        views.append(ProviderView(
            provider_key=provider.key,
            label=provider.label,
            kind=provider.kind,
            description=provider.description,
            enabled=turned_on,
            configured=configured,
            status=status,
            attribution_label=provider.attribution_label,
            attribution_url=provider.attribution_url,
        ))
    return views


def _attributions(db: Session, user_id: uuid.UUID) -> list[Attribution]:
    sources = {
        source
        for (source,) in db.query(JobListing.source).filter(JobListing.user_id == user_id).distinct()
    }
    items: list[Attribution] = []
    for provider in providers():
        if provider.attribution_label and provider.label in sources:
            items.append(Attribution(label=provider.attribution_label, url=provider.attribution_url))
    return items


def _within_window(settings: JobDiscoverySettings, fingerprint: str, mode: str) -> bool:
    window = _user_window_seconds(mode)
    last = _aware(settings.last_discovered_at)
    if window <= 0 or not last or settings.query_fingerprint != fingerprint:
        return False
    return (_now() - last).total_seconds() < window


def _take_quota(db: Session, provider_key: str) -> bool:
    limit = _daily_limit(provider_key)
    if limit <= 0:
        return False
    today = _now().date()
    row = (
        db.query(JobProviderQuota)
        .filter(JobProviderQuota.provider_key == provider_key, JobProviderQuota.quota_day == today)
        .one_or_none()
    )
    if row is None:
        row = JobProviderQuota(provider_key=provider_key, quota_day=today, request_count=0)
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            row = (
                db.query(JobProviderQuota)
                .filter(JobProviderQuota.provider_key == provider_key, JobProviderQuota.quota_day == today)
                .one()
            )
    if row.request_count >= limit:
        return False
    row.request_count += 1
    db.commit()
    return True


def _read_cache(db: Session, provider_key: str, fingerprint: str) -> tuple[list[NormalizedJob] | None, bool]:
    row = (
        db.query(JobProviderCache)
        .filter(
            JobProviderCache.provider_key == provider_key,
            JobProviderCache.query_fingerprint == fingerprint,
        )
        .one_or_none()
    )
    if row is None or not isinstance(row.payload, list):
        return None, False
    jobs: list[NormalizedJob] = []
    for item in row.payload:
        if isinstance(item, dict):
            try:
                jobs.append(NormalizedJob.model_validate(item))
            except ValueError:
                continue
    fetched = _aware(row.fetched_at)
    fresh = fetched is not None and (_now() - fetched).total_seconds() < cache_ttl_seconds()
    return jobs, fresh


def _write_cache(db: Session, provider_key: str, fingerprint: str, jobs: list[NormalizedJob]) -> None:
    payload = [job.model_dump(mode="json") for job in jobs]
    row = (
        db.query(JobProviderCache)
        .filter(
            JobProviderCache.provider_key == provider_key,
            JobProviderCache.query_fingerprint == fingerprint,
        )
        .one_or_none()
    )
    if row is None:
        db.add(JobProviderCache(
            provider_key=provider_key,
            query_fingerprint=fingerprint,
            payload=payload,
            fetched_at=_now(),
        ))
    else:
        row.payload = payload
        row.fetched_at = _now()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def _load_provider(
    db: Session,
    provider_key: str,
    query: SearchQuery,
) -> tuple[list[NormalizedJob], ProviderRun, bool]:
    provider = get_provider(provider_key)
    if provider is None or provider.fetch is None:
        raise ProviderError("That job source is not available.")
    cached, fresh = _read_cache(db, provider.key, query.fingerprint())
    if fresh and cached is not None:
        return cached, ProviderRun(
            provider_key=provider.key,
            label=provider.label,
            status="cached",
            message="Using listings saved from the last request to this provider.",
            fetched=len(cached),
        ), True
    if not _take_quota(db, provider.key):
        if cached:
            return cached, ProviderRun(
                provider_key=provider.key,
                label=provider.label,
                status="rate_limited",
                message="Daily request limit reached. Showing the last saved listings.",
                fetched=len(cached),
            ), False
        return [], ProviderRun(
            provider_key=provider.key,
            label=provider.label,
            status="rate_limited",
            message="Daily request limit reached.",
            fetched=0,
        ), False
    try:
        jobs = provider.fetch(query)
    except ProviderError as exc:
        logger.info(
            "job_provider_failed provider=%s error_type=%s rate_limited=%s",
            provider.key,
            type(exc).__name__,
            exc.rate_limited,
        )
        if cached:
            return cached, ProviderRun(
                provider_key=provider.key,
                label=provider.label,
                status="rate_limited" if exc.rate_limited else "stale",
                message="Showing the last saved listings.",
                fetched=len(cached),
            ), False
        return [], ProviderRun(
            provider_key=provider.key,
            label=provider.label,
            status="rate_limited" if exc.rate_limited else "error",
            message=str(exc),
            fetched=0,
        ), False
    _write_cache(db, provider.key, query.fingerprint(), jobs)
    noun = "listing" if len(jobs) == 1 else "listings"
    return jobs, ProviderRun(
        provider_key=provider.key,
        label=provider.label,
        status="ok",
        message=f"{len(jobs)} {noun} fetched.",
        fetched=len(jobs),
    ), True


def _apply_discovered(row: JobListing, job: NormalizedJob, key: str) -> None:
    row.title = job.title
    row.company = job.company
    row.location = job.location or "New Zealand"
    if job.description:
        row.description = job.description
    row.salary = job.salary
    row.posted_at = job.posted_at
    if job.url:
        row.url = canonical_url(job.url)
    row.source = job.source
    row.dedupe_key = key
    row.updated_at = _now()


def _store(
    db: Session,
    user_id: uuid.UUID,
    batches: list[tuple[str, list[NormalizedJob], bool]],
    disabled_sources: list[str],
) -> tuple[int, int, int, int]:
    existing = db.query(JobListing).filter(JobListing.user_id == user_id).all()
    by_url: dict[str, JobListing] = {}
    by_key: dict[str, JobListing] = {}
    for row in existing:
        url = canonical_url(row.url)
        if url:
            by_url.setdefault(url, row)
        key = row.dedupe_key or dedupe_key(row.title, row.company, row.location)
        if key:
            by_key.setdefault(key, row)

    kept = dedupe_jobs([job for _, jobs, _ in batches for job in jobs])
    replace_sources = {label for label, _, replace in batches if replace}
    seen: set[int] = set()
    created = updated = duplicates = 0
    for job in kept:
        url = canonical_url(job.url)
        key = dedupe_key(job.title, job.company, job.location)
        if not key:
            continue
        match = by_url.get(url) if url else None
        if match is None:
            match = by_key.get(key)
        if match is not None:
            if match.id is not None:
                seen.add(match.id)
            if match.status == "discovered":
                try:
                    with db.begin_nested():
                        _apply_discovered(match, job, key)
                        db.flush()
                except IntegrityError:
                    duplicates += 1
                    continue
                updated += 1
            else:
                duplicates += 1
            continue
        row = JobListing(
            user_id=user_id,
            title=job.title,
            company=job.company,
            location=job.location or "New Zealand",
            description=job.description,
            url=url,
            source=job.source,
            salary=job.salary,
            posted_at=job.posted_at,
            dedupe_key=key,
            status="discovered",
        )
        try:
            with db.begin_nested():
                db.add(row)
                db.flush()
        except IntegrityError:
            duplicates += 1
            continue
        seen.add(row.id)
        if url:
            by_url[url] = row
        by_key[key] = row
        created += 1

    removed = 0
    for row in existing:
        if row.status != "discovered":
            continue
        drop = row.source in disabled_sources or (row.source in replace_sources and row.id not in seen)
        if drop:
            db.delete(row)
            removed += 1
    return created, updated, duplicates, removed


def _settings_payload(db: Session, user_id: uuid.UUID, settings: JobDiscoverySettings) -> SettingsResponse:
    profile = db.query(CareerProfile).filter(CareerProfile.user_id == user_id).one_or_none()
    enabled = _enabled_map(db, user_id)
    query, from_profile = _search(settings, profile)
    return SettingsResponse(
        country=settings.country,
        location=settings.location,
        keywords=settings.keywords,
        remote_preference=settings.remote_preference,
        last_discovered_at=settings.last_discovered_at,
        search=_echo(query, from_profile),
        providers=_provider_views(enabled),
        link_outs=_link_outs(query, enabled),
        attributions=_attributions(db, user_id),
    )


def run_discovery(db: Session, user_id: uuid.UUID, *, mode: Literal["interactive", "daily"]) -> DiscoverResponse:
    settings = get_or_create_for_user(db, JobDiscoverySettings, user_id)
    profile = db.query(CareerProfile).filter(CareerProfile.user_id == user_id).one_or_none()
    enabled = _enabled_map(db, user_id)
    query, from_profile = _search(settings, profile)
    fingerprint = _fingerprint(query, enabled)
    echo = _echo(query, from_profile)
    links = _link_outs(query, enabled)
    if _within_window(settings, fingerprint, mode):
        logger.info("job_discovery user_id=%s mode=%s cached=true", user_id, mode)
        return DiscoverResponse(
            cached=True,
            discovered_at=settings.last_discovered_at,
            created=0,
            updated=0,
            duplicates=0,
            removed=0,
            search=echo,
            providers=[
                ProviderRun(
                    provider_key=provider.key,
                    label=provider.label,
                    status="cached",
                    message="Saved results are still fresh.",
                    fetched=0,
                )
                for provider in providers()
                if provider.kind == "api" and enabled.get(provider.key, True)
            ],
            link_outs=links,
            attributions=_attributions(db, user_id),
        )

    batches: list[tuple[str, list[NormalizedJob], bool]] = []
    runs: list[ProviderRun] = []
    disabled_sources: list[str] = []
    touched_provider = False
    for provider in providers():
        if provider.kind != "api":
            continue
        if not enabled.get(provider.key, True):
            disabled_sources.append(provider.label)
            runs.append(ProviderRun(
                provider_key=provider.key,
                label=provider.label,
                status="disabled",
                message="Turned off in your job sources.",
                fetched=0,
            ))
            continue
        if not provider.is_configured:
            runs.append(ProviderRun(
                provider_key=provider.key,
                label=provider.label,
                status="not_configured",
                message="Not configured.",
                fetched=0,
            ))
            continue
        jobs, run, replace = _load_provider(db, provider.key, query)
        batches.append((provider.label, jobs, replace))
        runs.append(run)
        touched_provider = True
        logger.info(
            "job_provider user_id=%s provider=%s status=%s fetched=%s",
            user_id,
            provider.key,
            run.status,
            run.fetched,
        )

    created, updated, duplicates, removed = _store(db, user_id, batches, disabled_sources)
    if touched_provider:
        settings.query_fingerprint = fingerprint
        settings.last_discovered_at = _now()
        settings.updated_at = _now()
    db.commit()
    db.refresh(settings)
    logger.info(
        "job_discovery user_id=%s mode=%s cached=false created=%s updated=%s duplicates=%s removed=%s",
        user_id,
        mode,
        created,
        updated,
        duplicates,
        removed,
    )
    return DiscoverResponse(
        cached=False,
        discovered_at=settings.last_discovered_at,
        created=created,
        updated=updated,
        duplicates=duplicates,
        removed=removed,
        search=echo,
        providers=runs,
        link_outs=links,
        attributions=_attributions(db, user_id),
    )


def _http_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise HTTPException(status_code=422, detail=PUBLIC_LINK)
    return url.strip()


def _source_for_url(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    if host == "seek.co.nz" or host.endswith(".seek.co.nz") or host.endswith(".seek.com") or host == "seek.com":
        return "SEEK"
    if "linkedin." in host or host.endswith("lnkd.in") or host == "lnkd.in":
        return "LinkedIn"
    if "indeed." in host:
        return "Indeed"
    if "trademe." in host:
        return "Trade Me Jobs"
    return "Added from link"


def _first_line(value: str) -> str:
    for line in value.splitlines():
        title = one_line(line, 200)
        if title:
            return title
    return ""


@router.get("/discovery/settings", response_model=SettingsResponse)
def get_discovery_settings(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> SettingsResponse:
    settings = get_or_create_for_user(db, JobDiscoverySettings, user_id)
    return _settings_payload(db, user_id, settings)


@router.put("/discovery/settings", response_model=SettingsResponse)
def save_discovery_settings(
    payload: SettingsWrite,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> SettingsResponse:
    known = {provider.key for provider in providers()}
    unknown = [item.provider_key for item in payload.providers if item.provider_key not in known]
    if unknown:
        raise HTTPException(status_code=422, detail="Unknown job source.")
    settings = get_or_create_for_user(db, JobDiscoverySettings, user_id)
    settings.country = payload.country
    settings.location = payload.location or "New Zealand"
    settings.keywords = payload.keywords
    settings.remote_preference = payload.remote_preference
    settings.updated_at = _now()
    for item in payload.providers:
        row = (
            db.query(JobProviderSetting)
            .filter(JobProviderSetting.user_id == user_id, JobProviderSetting.provider_key == item.provider_key)
            .one_or_none()
        )
        if row is None:
            db.add(JobProviderSetting(
                user_id=user_id,
                provider_key=item.provider_key,
                enabled=item.enabled,
                updated_at=_now(),
            ))
        else:
            row.enabled = item.enabled
            row.updated_at = _now()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Those job source settings could not be saved.") from None
    db.refresh(settings)
    return _settings_payload(db, user_id, settings)


@router.post("/discovery", response_model=DiscoverResponse)
def discover_jobs(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> DiscoverResponse:
    return run_discovery(db, user_id, mode="interactive")


@router.post("/discovery/refresh", response_model=DiscoverResponse)
def refresh_jobs_daily(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> DiscoverResponse:
    """Refresh one signed-in user's jobs when the last run is older than the daily window.

    Call this from a scheduler that already has that user's access token.
    It does not run for anyone else, and it does nothing when the last run is still fresh.
    """

    return run_discovery(db, user_id, mode="daily")


@router.post("/from-link", response_model=JobResponse, status_code=201)
def add_job_from_link(
    payload: FromLinkRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> JobListing:
    url = canonical_url(_http_url(payload.url))
    description = payload.description.strip()
    title = one_line(payload.title, 200)
    company = one_line(payload.company, 200)
    location = one_line(payload.location, 200)
    salary = ""
    posted_at = None
    host = (urlsplit(url).hostname or "").lower()
    if not description and host_is_blocked(host):
        raise HTTPException(status_code=422, detail=PASTE_REQUIRED)
    if not description or not title:
        if not description:
            try:
                parsed = fetch_public_job_page(url)
            except FetchError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from None
            title = title or one_line(parsed.get("title"), 200)
            company = company or one_line(parsed.get("company"), 200)
            location = location or one_line(parsed.get("location"), 200)
            description = description or str(parsed.get("description") or "").strip()
            salary = one_line(parsed.get("salary"), 200)
            posted_at = parsed.get("posted_at") if isinstance(parsed.get("posted_at"), datetime) else None
            if not description:
                raise HTTPException(status_code=422, detail=PASTE_INSTEAD)
    title = title or _first_line(description) or "Job listing"
    location = location or "New Zealand"
    key = dedupe_key(title, company, location)
    existing_rows = db.query(JobListing).filter(JobListing.user_id == user_id).all()
    for row in existing_rows:
        same_url = url and canonical_url(row.url) == url
        same_key = key and (row.dedupe_key or dedupe_key(row.title, row.company, row.location)) == key
        if same_url or same_key:
            raise HTTPException(status_code=409, detail="This job link is already in your list.")
    job = JobListing(
        user_id=user_id,
        title=title[:200],
        company=company,
        location=location,
        description=description[:20000],
        url=url,
        source=_source_for_url(url),
        salary=salary,
        posted_at=posted_at,
        dedupe_key=key,
        status="saved",
    )
    try:
        db.add(job)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This job link is already in your list.") from None
    db.refresh(job)
    return job
