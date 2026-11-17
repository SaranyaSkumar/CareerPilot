"""Shared HTTP client and the spacing between calls to one provider."""

from __future__ import annotations

import os
import threading
import time

import httpx

_client: httpx.Client | None = None
_gates: dict[str, threading.Lock] = {}
_last_call: dict[str, float] = {}
_gate_guard = threading.Lock()


def min_interval_seconds() -> float:
    raw = os.getenv("JOB_DISCOVERY_MIN_INTERVAL_SECONDS", "2.5").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 2.5


def get_http_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=httpx.Timeout(8.0, connect=3.0), follow_redirects=False)
    return _client


def set_http_client(client: httpx.Client | None) -> None:
    """Tests replace the client so provider calls never leave the machine."""

    global _client
    _client = client


def wait_turn(provider_key: str) -> None:
    """Keep repeat calls to one provider inside a small gap. The first call does not wait."""

    interval = min_interval_seconds()
    if interval <= 0:
        return
    with _gate_guard:
        lock = _gates.setdefault(provider_key, threading.Lock())
    with lock:
        now = time.monotonic()
        delay = interval - (now - _last_call.get(provider_key, 0.0))
        if delay > 0:
            time.sleep(delay)
        _last_call[provider_key] = time.monotonic()
