from datetime import date
from decimal import Decimal, InvalidOperation

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .services import COMMON_CURRENCIES, convert_amount, get_provider


@api_view(["GET"])
def health(request):
    er_key = bool(getattr(settings, "EXCHANGE_RATE_API_KEY", ""))
    try:
        provider = get_provider()
        provider_name = provider.name
        provider_error = None
    except Exception as exc:  # noqa: BLE001
        provider_name = None
        provider_error = str(exc)

    return Response(
        {
            "status": "ok" if provider_name else "needs_key",
            "provider": provider_name,
            "provider_error": provider_error,
            "exchange_rate_api_key_configured": er_key,
            "currencies": COMMON_CURRENCIES,
            "free_tier_note": (
                "ExchangeRate-API free tier returns latest mid-market rates. "
                "Historical rates for a past date need a paid plan (or OXR/Fixer next)."
            ),
        }
    )


@api_view(["GET"])
def currencies(request):
    try:
        provider_name = get_provider().name
    except Exception as exc:  # noqa: BLE001
        return Response(
            {"detail": str(exc), "currencies": COMMON_CURRENCIES},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response({"currencies": COMMON_CURRENCIES, "provider": provider_name})


@api_view(["GET", "POST"])
def convert(request):
    """
    Convert an amount using FX rates.

    With ExchangeRate-API free tier this is latest mid-market.
    Past dates: tries /history (paid); otherwise falls back to latest + warning.

    Query/body params:
      amount, from, to, date (YYYY-MM-DD, optional — defaults to today)
    """
    data = request.data if request.method == "POST" else request.query_params

    try:
        amount = Decimal(str(data.get("amount", "")).replace(",", "").strip())
    except (InvalidOperation, TypeError):
        return Response({"detail": "Valid amount is required."}, status=status.HTTP_400_BAD_REQUEST)

    from_currency = (data.get("from") or data.get("from_currency") or "").strip()
    to_currency = (data.get("to") or data.get("to_currency") or "").strip()
    raw_date = (data.get("date") or data.get("rate_date") or "").strip()

    if not from_currency or not to_currency:
        return Response(
            {"detail": "Both from and to currency codes are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    rate_on: date | None = None
    if raw_date:
        try:
            rate_on = date.fromisoformat(raw_date)
        except ValueError:
            return Response(
                {"detail": "date must be YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    try:
        quote = convert_amount(amount, from_currency, to_currency, rate_on)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except RuntimeError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as exc:  # noqa: BLE001
        return Response(
            {"detail": f"FX provider error: {exc}"},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    payload = {
        "amount": str(quote.amount),
        "from": quote.from_currency,
        "to": quote.to_currency,
        "date_requested": (rate_on or date.today()).isoformat(),
        "rate_date": quote.rate_date.isoformat(),
        "rate": str(quote.rate),
        "converted_amount": str(quote.converted_amount),
        "provider": quote.provider,
        "note": (
            "Persist rate + rate_date on your transaction row so later "
            "recalculations stay consistent."
        ),
    }
    if quote.warning:
        payload["warning"] = quote.warning
    return Response(payload)
