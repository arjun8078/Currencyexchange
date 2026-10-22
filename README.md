# RateDay — currency conversion (Angular + Django)

Convert amounts in INR (or another local currency) to USD, AED, SAR, and more.

**Default provider: [ExchangeRate-API](https://www.exchangerate-api.com/)** (free tier = latest mid-market rates).  
Open Exchange Rates is still wired in if you set `OPEN_EXCHANGE_RATES_APP_ID` and `FX_PROVIDER=openexchangerates`.

## Source code

This repo is the full app:

| Path | What |
| --- | --- |
| `currency/` + `config/` + `manage.py` | Django API |
| `frontend/` | Angular UI |
| `.env.example` | Env template (copy to `.env`, never commit secrets) |

Keys stay in local `.env` (gitignored). Safe to clone and run anywhere.

## Run locally

### 1. Backend — Django (`43125`)

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# edit .env → set EXCHANGE_RATE_API_KEY=... and FX_PROVIDER=exchangerateapi
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

API smoke test:

```bash
curl "http://127.0.0.1:43125/api/health/"
curl "http://127.0.0.1:43125/api/convert/?amount=10000&from=INR&to=AED&date=$(date -u +%F)"
```

## Demo on Vercel (frontend)

Vercel is a great fit for the **Angular** demo UI. Django is a separate API process — host it on Render / Railway / Fly.io / a VPS, then point the UI at it.

1. Deploy Django somewhere public and set env vars there (`EXCHANGE_RATE_API_KEY`, `FX_PROVIDER`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, CORS for your Vercel domain).
2. In `frontend/src/environments/environment.prod.ts`, set:

```ts
apiBaseUrl: 'https://your-django-host.example.com/api'
```

3. Deploy the `frontend/` folder to Vercel (Root Directory = `frontend`).  
   `frontend/vercel.json` already points the build output at `dist/frontend/browser`.

Local-only demos can skip Vercel and just run both servers on your machine.

## Providers

| Provider | Env | Notes |
| --- | --- | --- |
| **ExchangeRate-API** (default) | `EXCHANGE_RATE_API_KEY` | Free = latest; historical needs paid |
| Open Exchange Rates | `OPEN_EXCHANGE_RATES_APP_ID` | Often better historical on their plans |
| Frankfurter | none | ECB; no AED |
| Community CDN | none | Prototype only |

```bash
FX_PROVIDER=exchangerateapi   # or openexchangerates | frankfurter | currencyapi | auto
```

## Free-tier note

ExchangeRate-API free tier returns **latest** rates. Choosing a past date falls back to today and shows a warning in the UI.
