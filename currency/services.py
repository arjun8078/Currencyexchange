"""
Historical FX conversion providers.

Call FX APIs from Django only — never put provider keys in Angular.
Always persist the rate + date used on the transaction for auditability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from email.utils import parsedate_to_datetime
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
    warning: str | None = None


@dataclass(frozen=True)
class RateResult:
    rate: Decimal
    rate_date: date
    warning: str | None = None


class FxProvider(Protocol):
    name: str

    def get_rate(self, from_currency: str, to_currency: str, on: date) -> RateResult:
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

    def get_rate(self, from_currency: str, to_currency: str, on: date) -> RateResult:
        if from_currency == to_currency:
            return RateResult(Decimal("1"), on)

        url = f"{self.base_url}/{on.isoformat()}"
        params = {"from": from_currency, "to": to_currency}
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        rate = Decimal(str(payload["rates"][to_currency]))
        rate_date = date.fromisoformat(payload["date"])
        return RateResult(_quantize_rate(rate), rate_date)


class CurrencyApiProvider:
    """
    Free community CDN (@fawazahmed0/currency-api) with historical dates and AED.
    Prototype only — accuracy can drift vs bank/mid-market feeds.
    """

    name = "currencyapi"
    cdn = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{day}/v1/currencies/{base}.min.json"
    fallback = "https://{day}.currency-api.pages.dev/v1/currencies/{base}.min.json"

    def get_rate(self, from_currency: str, to_currency: str, on: date) -> RateResult:
        if from_currency == to_currency:
            return RateResult(Decimal("1"), on)

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
        return RateResult(rate, rate_date)


class ExchangeRateApiProvider:
    """
    ExchangeRate-API (exchangerate-api.com).

    Free tier: latest mid-market rates via /pair and /latest (no true historical).
    Paid plans add /history/{BASE}/{YYYY}/{MM}/{DD}.
    """

    name = "exchangerateapi"
    base_url = "https://v6.exchangerate-api.com/v6"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def get_rate(self, from_currency: str, to_currency: str, on: date) -> RateResult:
        if from_currency == to_currency:
            return RateResult(Decimal("1"), on)

        warning: str | None = None
        today = date.today()

        # Free tier has no historical; paid history endpoint is attempted first
        # for past dates, then we fall back to latest with an explicit warning.
        if on < today:
            try:
                return self._historical(from_currency, to_currency, on)
            except Exception:
                warning = (
                    "ExchangeRate-API free tier only includes latest rates. "
                    "Returned today's mid-market rate, not the selected date. "
                    "Upgrade their plan (or use Open Exchange Rates / Fixer) for historical FX."
                )

        return self._latest_pair(from_currency, to_currency, warning=warning)

    def _historical(self, from_currency: str, to_currency: str, on: date) -> RateResult:
        url = (
            f"{self.base_url}/{self.api_key}/history/"
            f"{from_currency}/{on.year}/{on.month}/{on.day}"
        )
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()

        if payload.get("result") != "success":
            raise RuntimeError(payload.get("error-type") or "history request failed")

        rates = payload.get("conversion_rates") or {}
        if to_currency not in rates:
            raise ValueError(f"No rate {from_currency}->{to_currency} on {on}")

        rate = _quantize_rate(Decimal(str(rates[to_currency])))
        return RateResult(rate, on)

    def _latest_pair(
        self,
        from_currency: str,
        to_currency: str,
        warning: str | None = None,
    ) -> RateResult:
        url = f"{self.base_url}/{self.api_key}/pair/{from_currency}/{to_currency}"
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()

        if payload.get("result") != "success":
            error = payload.get("error-type") or "pair request failed"
            if error == "invalid-key":
                raise RuntimeError("Invalid EXCHANGE_RATE_API_KEY")
            raise RuntimeError(error)

        rate = _quantize_rate(Decimal(str(payload["conversion_rate"])))
        rate_date = today = date.today()
        raw_updated = payload.get("time_last_update_utc")
        if raw_updated:
            try:
                rate_date = parsedate_to_datetime(raw_updated).date()
            except (TypeError, ValueError, IndexError):
                rate_date = today

        return RateResult(rate, rate_date, warning=warning)


class OpenExchangeRatesProvider:
    """
    Open Exchange Rates — App ID required.
    Free plan: USD base + latest. Historical endpoint usually needs a paid plan.
    """

    name = "openexchangerates"
    base_url = "https://openexchangerates.org/api"

    def __init__(self, app_id: str) -> None:
        self.app_id = app_id

    def get_rate(self, from_currency: str, to_currency: str, on: date) -> RateResult:
        if from_currency == to_currency:
            return RateResult(Decimal("1"), on)

        warning: str | None = None
        today = date.today()
        symbols = ",".join(sorted({from_currency, to_currency} - {"USD"})) or "EUR"

        if on < today:
            try:
                return self._from_payload(
                    self._fetch(f"/historical/{on.isoformat()}.json", symbols),
                    from_currency,
                    to_currency,
                )
            except Exception:
                warning = (
                    "Open Exchange Rates free plan may not include historical rates. "
                    "Returned latest mid-market rate, not the selected date."
                )

        return self._from_payload(
            self._fetch("/latest.json", symbols),
            from_currency,
            to_currency,
            warning=warning,
        )

    def _fetch(self, path: str, symbols: str) -> dict:
        params = {"app_id": self.app_id, "base": "USD", "symbols": symbols}
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.get(f"{self.base_url}{path}", params=params)
            if response.status_code >= 400:
                try:
                    detail = response.json()
                    message = detail.get("description") or detail.get("message") or response.text
                except Exception:  # noqa: BLE001
                    message = response.text
                raise RuntimeError(f"OXR {response.status_code}: {message}")
            return response.json()

    def _from_payload(
        self,
        payload: dict,
        from_currency: str,
        to_currency: str,
        warning: str | None = None,
    ) -> RateResult:
        rates = payload["rates"]
        # Free plans are USD-based; cross-convert via USD.
        usd_from = Decimal("1") if from_currency == "USD" else Decimal(str(rates[from_currency]))
        usd_to = Decimal("1") if to_currency == "USD" else Decimal(str(rates[to_currency]))
        rate = _quantize_rate(usd_to / usd_from)
        rate_date = datetime.fromtimestamp(payload["timestamp"], tz=timezone.utc).date()
        return RateResult(rate, rate_date, warning=warning)


def get_provider() -> FxProvider:
    configured = getattr(settings, "FX_PROVIDER", "auto").lower()
    er_key = getattr(settings, "EXCHANGE_RATE_API_KEY", "") or ""
    oxr_id = getattr(settings, "OPEN_EXCHANGE_RATES_APP_ID", "") or ""

    if configured == "exchangerateapi":
        if not er_key:
            raise RuntimeError(
                "EXCHANGE_RATE_API_KEY is required. "
                "Get a free key at https://www.exchangerate-api.com/"
            )
        return ExchangeRateApiProvider(er_key)
    if configured == "openexchangerates":
        if not oxr_id:
            raise RuntimeError("OPEN_EXCHANGE_RATES_APP_ID is required for openexchangerates provider")
        return OpenExchangeRatesProvider(oxr_id)
    if configured == "frankfurter":
        return FrankfurterProvider()
    if configured == "currencyapi":
        return CurrencyApiProvider()

    # auto: prefer ExchangeRate-API, then Open Exchange Rates, else CDN fallback
    if er_key:
        return ExchangeRateApiProvider(er_key)
    if oxr_id:
        return OpenExchangeRatesProvider(oxr_id)
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
        warning = cached.get("warning")
    else:
        result = provider.get_rate(from_currency, to_currency, on)
        rate = result.rate
        rate_date = result.rate_date
        warning = result.warning
        # Latest rates: short TTL. Dated historical: longer.
        ttl = int(timedelta(minutes=30).total_seconds()) if warning else int(timedelta(hours=12).total_seconds())
        cache.set(
            cache_key,
            {"rate": str(rate), "rate_date": rate_date.isoformat(), "warning": warning},
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
        warning=warning,
    )
