"""Pluggable job sources.

API providers pull listings through each vendor's documented API. Link-out
providers only build a search URL. Nothing in this package downloads SEEK,
LinkedIn, Indeed, or Trade Me pages.
"""

from app.job_providers.registry import get_provider, providers

__all__ = ["get_provider", "providers"]
