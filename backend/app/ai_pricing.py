"""Token estimates and Anthropic list prices for the CV-writing cap.

Prices are USD per million tokens from Anthropic's published rates. An unknown
model name uses the Sonnet 4.6 rate, which is higher than the default Sonnet
5.5 rate, so a custom model id is not priced below the default. Opus and Fable
names use their own higher rates. Haiku 5.5 has a higher long-context tier;
that higher tier is used so a short prompt is never under-estimated.
"""

from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation

DEFAULT_MODEL = "claude-sonnet-5-5"
REQUEST_CAP_USD = Decimal("0.50")
DEFAULT_DAILY_CAP_USD = Decimal("2")
DEFAULT_MONTHLY_CAP_USD = Decimal("50")

# (input USD per million, output USD per million)
_RATES: dict[str, tuple[Decimal, Decimal]] = {
    "claude-sonnet-5-5": (Decimal("2"), Decimal("10")),
    "claude-sonnet-5": (Decimal("2"), Decimal("10")),
    "claude-sonnet-4-6": (Decimal("3"), Decimal("15")),
    "claude-sonnet-4-5": (Decimal("3"), Decimal("15")),
    "claude-sonnet-4-5-20250929": (Decimal("3"), Decimal("15")),
    "claude-haiku-5-5": (Decimal("0.50"), Decimal("2.50")),
    "claude-haiku-4-5": (Decimal("1"), Decimal("5")),
    "claude-opus-5-5": (Decimal("4"), Decimal("20")),
    "claude-opus-5": (Decimal("5"), Decimal("25")),
    "claude-opus-4-8": (Decimal("5"), Decimal("25")),
    "claude-fable-5-2": (Decimal("8"), Decimal("40")),
    "claude-fable-5": (Decimal("10"), Decimal("50")),
}


class CapMisconfigured(Exception):
    """A spending-cap environment variable is not a non-negative amount."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(name)


def anthropic_api_key() -> str:
    return os.environ.get("ANTHROPIC_API_KEY", "").strip()


def anthropic_model() -> str:
    return os.environ.get("ANTHROPIC_MODEL", "").strip() or DEFAULT_MODEL


def rates_for(model: str) -> tuple[Decimal, Decimal]:
    known = _RATES.get(model)
    if known is not None:
        return known
    lowered = model.lower()
    if "fable" in lowered or "mythos" in lowered:
        return _RATES["claude-fable-5-2"]
    if "opus" in lowered:
        return _RATES["claude-opus-5-5"]
    if "haiku" in lowered:
        return _RATES["claude-haiku-4-5"]
    return _RATES["claude-sonnet-4-6"]


def estimate_input_tokens(*parts: str) -> int:
    """Conservative input-token estimate. English is about 4 characters per token.

    Dividing by 3, plus a fixed allowance for message framing and the JSON
    schema, keeps the estimate above the likely true count.
    """

    characters = sum(len(part) for part in parts)
    return characters // 3 + 64


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    input_rate, output_rate = rates_for(model)
    cost = (
        Decimal(input_tokens) * input_rate + Decimal(output_tokens) * output_rate
    ) / Decimal(1_000_000)
    return cost.quantize(Decimal("0.000001"))


def _money_env(name: str, default: Decimal) -> Decimal:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise CapMisconfigured(name) from exc
    if value < 0:
        raise CapMisconfigured(name)
    return value


def daily_user_cap_usd() -> Decimal:
    return _money_env("ANTHROPIC_DAILY_USER_CAP_USD", DEFAULT_DAILY_CAP_USD)


def monthly_cap_usd() -> Decimal:
    return _money_env("ANTHROPIC_MONTHLY_CAP_USD", DEFAULT_MONTHLY_CAP_USD)


def format_usd(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"


def tailor_max_tokens(line_count: int) -> int:
    return min(4096, max(600, 350 + 90 * max(line_count, 1)))


def improve_max_tokens(bullet_count: int) -> int:
    return min(2048, max(400, 180 + 140 * max(bullet_count, 1)))
