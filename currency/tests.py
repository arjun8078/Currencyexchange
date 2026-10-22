from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from currency.services import CurrencyApiProvider, FxQuote, convert_amount
from currency.views import convert


class ConvertServiceTests(SimpleTestCase):
    @override_settings(FX_PROVIDER="currencyapi", OPEN_EXCHANGE_RATES_APP_ID="")
    @patch.object(CurrencyApiProvider, "get_rate")
    def test_convert_uses_rate_for_date(self, mock_rate):
        mock_rate.return_value = (Decimal("0.012"), date(2024, 6, 14))
        quote = convert_amount(Decimal("10000"), "INR", "USD", date(2024, 6, 15))
        self.assertIsInstance(quote, FxQuote)
        self.assertEqual(quote.converted_amount, Decimal("120.00"))
        self.assertEqual(quote.rate_date, date(2024, 6, 14))
        mock_rate.assert_called_once()


class ConvertApiTests(SimpleTestCase):
    @override_settings(FX_PROVIDER="currencyapi", OPEN_EXCHANGE_RATES_APP_ID="")
    @patch("currency.views.convert_amount")
    def test_convert_endpoint(self, mock_convert):
        mock_convert.return_value = FxQuote(
            amount=Decimal("10000"),
            from_currency="INR",
            to_currency="AED",
            rate_date=date(2024, 6, 15),
            rate=Decimal("0.04395552"),
            converted_amount=Decimal("439.56"),
            provider="currencyapi",
        )
        factory = APIRequestFactory()
        request = factory.get(
            "/api/convert/",
            {"amount": "10000", "from": "INR", "to": "AED", "date": "2024-06-15"},
        )
        response = convert(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["converted_amount"], "439.56")
        self.assertEqual(response.data["to"], "AED")
