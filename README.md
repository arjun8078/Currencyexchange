# RateDay — historical currency conversion (Angular + Django)

Users enter an amount in INR (or another local currency) and a date. Django calls an FX provider and returns USD, AED, or another currency.

## Provider we’re trying now: ExchangeRate-API

Sign up (free): [exchangerate-api.com](https://www.exchangerate-api.com/)

1. Copy your API key  
2. Put it in `/workspace/.env`:

```bash
cp .env.example .env
# edit .env:
EXCHANGE_RATE_API_KEY=your_key_here
FX_PROVIDER=exchangerateapi
```

3. Restart Django.

**Free tier note:** latest mid-market rates only (good accuracy vs the old community CDN).  
True **historical** rates for a past date need their paid plan — or we switch to **Open Exchange Rates / Fixer.io** next.

| Need | Service |
| --- | --- |
| **Now (free, better accuracy)** | **ExchangeRate-API** |
| **Next (historical by date)** | Open Exchange Rates or Fixer.io |
| **India statutory books** | RBI / bank mid-rate |
| **Old demo fallback** | Community CDN (`currencyapi`) — weaker accuracy |

## Run locally

### Backend (Django) — port `43125`

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add EXCHANGE_RATE_API_KEY
python manage.py migrate
python manage.py runserver 127.0.0.1:43125
```

### Frontend (Angular) — port `43126`

```bash
cd frontend
npm install
npm start
```

Open [http://127.0.0.1:43126](http://127.0.0.1:43126).

### API example

```bash
curl "http://127.0.0.1:43125/api/convert/?amount=10000&from=INR&to=AED&date=$(date -u +%F)"
curl "http://127.0.0.1:43125/api/health/"
```

## Env vars

See `.env.example`:

- `EXCHANGE_RATE_API_KEY` — required for ExchangeRate-API  
- `FX_PROVIDER=exchangerateapi|openexchangerates|frankfurter|currencyapi|auto`  
- `OPEN_EXCHANGE_RATES_APP_ID` — for the next trial (historical)
