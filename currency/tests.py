from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from currency.services import (
    ExchangeRateApiProvider,
    FxQuote,
    RateResult,
    convert_amount,
)
from currency.views import convert


class ConvertServiceTests(SimpleTestCase):
    @override_settings(FX_PROVIDER="exchangerateapi", EXCHANGE_RATE_API_KEY="test-key")
    @patch.object(ExchangeRateApiProvider, "get_rate")
    def test_convert_uses_rate(self, mock_rate):
        mock_rate.return_value = RateResult(Decimal("0.012"), date(2026, 10, 22))
        quote = convert_amount(Decimal("10000"), "INR", "USD", date.today())
        self.assertIsInstance(quote, FxQuote)
        self.assertEqual(quote.converted_amount, Decimal("120.00"))
        self.assertEqual(quote.provider, "exchangerateapi")
        mock_rate.assert_called_once()


class ConvertApiTests(SimpleTestCase):
    @override_settings(FX_PROVIDER="exchangerateapi", EXCHANGE_RATE_API_KEY="test-key")
    @patch("currency.views.convert_amount")
    def test_convert_endpoint(self, mock_convert):
        mock_convert.return_value = FxQuote(
            amount=Decimal("10000"),
            from_currency="INR",
            to_currency="AED",
            rate_date=date(2026, 10, 22),
            rate=Decimal("0.043"),
            converted_amount=Decimal("430.00"),
            provider="exchangerateapi",
            warning=None,
        )
        factory = APIRequestFactory()
        request = factory.get(
            "/api/convert/",
            {"amount": "10000", "from": "INR", "to": "AED", "date": date.today().isoformat()},
        )
        response = convert(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["converted_amount"], "430.00")
        self.assertEqual(response.data["provider"], "exchangerateapi")
        self.assertNotIn("warning", response.data)

    @override_settings(FX_PROVIDER="exchangerateapi", EXCHANGE_RATE_API_KEY="test-key")
    @patch("currency.views.convert_amount")
    def test_convert_endpoint_includes_warning(self, mock_convert):
        mock_convert.return_value = FxQuote(
            amount=Decimal("10000"),
            from_currency="INR",
            to_currency="USD",
            rate_date=date.today(),
            rate=Decimal("0.012"),
            converted_amount=Decimal("120.00"),
            provider="exchangerateapi",
            warning="Free tier latest only",
        )
        factory = APIRequestFactory()
        request = factory.get(
            "/api/convert/",
            {"amount": "10000", "from": "INR", "to": "USD", "date": "2024-06-15"},
        )
        response = convert(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["warning"], "Free tier latest only")
