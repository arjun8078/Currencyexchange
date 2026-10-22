"""
Historical FX conversion providers.

Call FX APIs from Django only — never put provider keys in Angular.
Always persist the rate + date used on the transaction for auditability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol

import httpx
from django.conf import settings
from django.core.cache import cache


COMMON_CURRENCIES = [
    "INR",
    "USD",
    "AED",
    "EUR",
    "GBP",
    "SAR",
    "SGD",
    "JPY",
    "AUD",
    "CAD",
    "CHF",
    "CNY",
]


@dataclass(frozen=True)
class FxQuote:
    amount: Decimal
    from_currency: str
    to_currency: str
    rate_date: date
    rate: Decimal
    converted_amount: Decimal
    provider: str


class FxProvider(Protocol):
    name: str

    def get_rate(self, from_currency: str, to_currency: str, on: date) -> tuple[Decimal, date]:
        ...


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _quantize_rate(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


class FrankfurterProvider:
    """
    ECB reference rates via Frankfurter (free, no API key).
    Strong for EUR majors + INR/USD. Does NOT publish AED.
    """

    name = "frankfurter"
    base_url = "https://api.frankfurter.app"

    def get_rate(self, from_currency: str, to_currency: str, on: date) -> tuple[Decimal, date]:
        if from_currency == to_currency:
            return Decimal("1"), on

        url = f"{self.base_url}/{on.isoformat()}"
        params = {"from": from_currency, "to": to_currency}
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        rate = Decimal(str(payload["rates"][to_currency]))
        rate_date = date.fromisoformat(payload["date"])
        return _quantize_rate(rate), rate_date


class CurrencyApiProvider:
    """
    Free community CDN (@fawazahmed0/currency-api) with historical dates and AED.
    Good for demos and non-regulated display rates. Prefer OXR/Fixer for finance.
    """

    name = "currencyapi"
    cdn = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{day}/v1/currencies/{base}.min.json"
    fallback = "https://{day}.currency-api.pages.dev/v1/currencies/{base}.min.json"

    def get_rate(self, from_currency: str, to_currency: str, on: date) -> tuple[Decimal, date]:
        if from_currency == to_currency:
            return Decimal("1"), on

        base = from_currency.lower()
        target = to_currency.lower()
        day = on.isoformat()

        urls = [
            self.cdn.format(day=day, base=base),
            self.fallback.format(day=day, base=base),
        ]
        last_error: Exception | None = None
        payload = None
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            for url in urls:
                try:
                    response = client.get(url)
                    response.raise_for_status()
                    payload = response.json()
                    break
                except Exception as exc:  # noqa: BLE001 — try next mirror
                    last_error = exc

        if payload is None:
            raise RuntimeError(f"CurrencyAPI unavailable for {on}: {last_error}")

        rates = payload.get(base) or {}
        if target not in rates:
            raise ValueError(f"No rate {from_currency}->{to_currency} on {on}")

        rate = _quantize_rate(Decimal(str(rates[target])))
        rate_date = date.fromisoformat(payload.get("date", day))
        return rate, rate_date


class OpenExchangeRatesProvider:
    """
    Open Exchange Rates historical endpoint — recommended for production apps.
    Requires OPEN_EXCHANGE_RATES_APP_ID. Covers USD, INR, AED, and 160+ others.
    """

    name = "openexchangerates"
    base_url = "https://openexchangerates.org/api"

    def __init__(self, app_id: str) -> None:
        self.app_id = app_id

    def get_rate(self, from_currency: str, to_currency: str, on: date) -> tuple[Decimal, date]:
        if from_currency == to_currency:
            return Decimal("1"), on

        url = f"{self.base_url}/historical/{on.isoformat()}.json"
        params = {"app_id": self.app_id, "base": "USD", "symbols": f"{from_currency},{to_currency}"}
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        rates = payload["rates"]
        # OXR free plans are USD-based; cross via USD.
        usd_from = Decimal("1") if from_currency == "USD" else Decimal(str(rates[from_currency]))
        usd_to = Decimal("1") if to_currency == "USD" else Decimal(str(rates[to_currency]))
        rate = _quantize_rate(usd_to / usd_from)
        rate_date = datetime.fromtimestamp(payload["timestamp"], tz=timezone.utc).date()
        return rate, rate_date


def get_provider() -> FxProvider:
    configured = getattr(settings, "FX_PROVIDER", "auto").lower()
    app_id = getattr(settings, "OPEN_EXCHANGE_RATES_APP_ID", "") or ""

    if configured == "openexchangerates":
        if not app_id:
            raise RuntimeError("OPEN_EXCHANGE_RATES_APP_ID is required for openexchangerates provider")
        return OpenExchangeRatesProvider(app_id)
    if configured == "frankfurter":
        return FrankfurterProvider()
    if configured == "currencyapi":
        return CurrencyApiProvider()

    # auto
    if app_id:
        return OpenExchangeRatesProvider(app_id)
    return CurrencyApiProvider()


def convert_amount(
    amount: Decimal,
    from_currency: str,
    to_currency: str,
    on: date | None = None,
) -> FxQuote:
    from_currency = from_currency.upper().strip()
    to_currency = to_currency.upper().strip()
    on = on or date.today()

    if amount < 0:
        raise ValueError("Amount must be non-negative")
    if on > date.today():
        raise ValueError("Rate date cannot be in the future")

    provider = get_provider()
    cache_key = f"fx:{provider.name}:{from_currency}:{to_currency}:{on.isoformat()}"
    cached = cache.get(cache_key)
    if cached:
        rate = Decimal(cached["rate"])
        rate_date = date.fromisoformat(cached["rate_date"])
    else:
        rate, rate_date = provider.get_rate(from_currency, to_currency, on)
        # Rates rarely move intraday for accounting; cache until next day.
        ttl = int(timedelta(hours=12).total_seconds())
        cache.set(
            cache_key,
            {"rate": str(rate), "rate_date": rate_date.isoformat()},
            timeout=ttl,
        )

    converted = _quantize_money(amount * rate)
    return FxQuote(
        amount=amount,
        from_currency=from_currency,
        to_currency=to_currency,
        rate_date=rate_date,
        rate=rate,
        converted_amount=converted,
        provider=provider.name,
    )
