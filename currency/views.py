from datetime import date
from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .services import COMMON_CURRENCIES, convert_amount, get_provider


@api_view(["GET"])
def health(request):
    provider = get_provider()
    return Response(
        {
            "status": "ok",
            "provider": provider.name,
            "currencies": COMMON_CURRENCIES,
        }
    )


@api_view(["GET"])
def currencies(request):
    return Response({"currencies": COMMON_CURRENCIES, "provider": get_provider().name})


@api_view(["GET", "POST"])
def convert(request):
    """
    Convert an amount using the FX rate for a specific calendar date.

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
    except Exception as exc:  # noqa: BLE001
        return Response(
            {"detail": f"FX provider error: {exc}"},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response(
        {
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
    )
