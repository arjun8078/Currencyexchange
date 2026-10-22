# RateDay — historical currency conversion (Angular + Django)

Users enter an amount in INR (or another local currency) and a **date**. Django fetches the FX rate **for that date** and returns USD, AED, or any other supported currency.

## Which FX service should you use?

| Need | Best choice | Why |
| --- | --- | --- |
| **Production app (INR → USD/AED, historical)** | **[Open Exchange Rates](https://openexchangerates.org/)** | Reliable historical endpoint (`/historical/YYYY-MM-DD.json`), wide coverage including **AED**, clear commercial license. Also strong: **Fixer.io** (APILayer). |
| **Bank / accounting / India compliance** | **RBI reference rate** (or your bank’s mid-rate feed) | Display APIs are fine for UX; statutory books often need RBI / contracted bank rates. |
| **Free demo / ECB majors (no AED)** | **[Frankfurter](https://www.frankfurter.app/)** | ECB rates, historical by date, no API key. No AED. |
| **Free demo with AED + date** | **CurrencyAPI CDN** (`@fawazahmed0/currency-api`) | Historical JSON by date, includes AED. Fine for prototypes; prefer OXR/Fixer for money movement. |

**Recommendation for your Angular + Django stack**

1. Call FX **only from Django** (keep keys off the client).
2. Pass `amount`, `from`, `to`, and `date` (the user-entered date).
3. **Persist** `rate`, `rate_date`, and `provider` on the transaction row so invoices stay stable if rates change later.
4. Cache same-day lookups server-side (this demo uses Django’s local memory cache).

This repo defaults to **CurrencyAPI** (free, supports AED + historical). Set `OPEN_EXCHANGE_RATES_APP_ID` to switch to Open Exchange Rates automatically (`FX_PROVIDER=auto`).

## Run locally

### Backend (Django) — port `43125`

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional: add OPEN_EXCHANGE_RATES_APP_ID
python manage.py migrate
python manage.py runserver 127.0.0.1:43125
```

### Frontend (Angular) — port `43126`

```bash
cd frontend
npm install
npm start -- --host 127.0.0.1 --port 43126
```

Open [http://127.0.0.1:43126](http://127.0.0.1:43126).

### API example

```bash
curl "http://127.0.0.1:43125/api/convert/?amount=10000&from=INR&to=AED&date=2024-06-15"
```

```json
{
  "amount": "10000",
  "from": "INR",
  "to": "AED",
  "date_requested": "2024-06-15",
  "rate_date": "2024-06-15",
  "rate": "0.04395552",
  "converted_amount": "439.56",
  "provider": "currencyapi"
}
```

## Provider env vars

See `.env.example`:

- `FX_PROVIDER=auto|openexchangerates|frankfurter|currencyapi`
- `OPEN_EXCHANGE_RATES_APP_ID=...` (recommended for production)
