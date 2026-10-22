# RateDay — currency conversion (Angular + Django)

Convert amounts in INR (or another local currency) to USD, AED, SAR, and more.

**Default in POC now: [Frankfurter v2](https://api.frankfurter.dev/v2/rates)** (free, no key — includes USD/AED/SAR + date).  
**Paid alternates:** Open Exchange Rates or ExchangeRate-API via `FX_PROVIDER`.

See `docs/Currency_Conversion_Service_Recommendation.pdf` for the plain-language decision note for leads/PMs.

## Source code

| Path | What |
| --- | --- |
| `currency/` + `config/` + `manage.py` | Django API |
| `frontend/` | Angular UI |
| `.env.example` | Env template (copy to `.env`, never commit secrets) |
| `docs/` | Provider recommendation PDF |

## Run locally

### 1. Backend — Django (`43125`)

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env             # Windows CMD
# edit .env → OPEN_EXCHANGE_RATES_APP_ID=... and FX_PROVIDER=openexchangerates
python manage.py migrate
python manage.py runserver 127.0.0.1:43125
```

### 2. Frontend — Angular (`43126`)

```bash
cd frontend
npm install
npm start
```

Open [http://127.0.0.1:43126](http://127.0.0.1:43126).

## Switch providers

```bash
# Production default
FX_PROVIDER=openexchangerates
OPEN_EXCHANGE_RATES_APP_ID=...

# Price-sensitive alternate
FX_PROVIDER=exchangerateapi
EXCHANGE_RATE_API_KEY=...
```

## Vercel demo (frontend)

Deploy `frontend/` to Vercel; host Django separately; set `apiBaseUrl` in `frontend/src/environments/environment.prod.ts`.
