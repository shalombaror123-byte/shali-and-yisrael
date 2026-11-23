# Portfolio Tracker

A finance web app that tracks a stock/ETF portfolio with live prices from
Yahoo Finance.

- **Backend** (`backend/`): FastAPI + yfinance. Positions are stored in
  `backend/portfolio.json`. Prices are fetched live and cached for 15s.
  Market news is aggregated from free RSS feeds (CNBC, Yahoo Finance,
  MarketWatch, Seeking Alpha) plus Yahoo Finance search, cached for 60s.
- **Frontend** (`frontend/`): React (Vite). Auto-refreshes every 15s.
  Two tabs: **Portfolio** and **News** — the News tab shows the latest US
  market headlines and can explain why a given stock is up/down by
  matching recent headlines to likely catalyst categories.

## Run it

### Backend (port 8000)

```bash
cd backend
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/uvicorn main:app --port 8000
```

### Frontend (port 5173)

```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173

## Versioning

The app is versioned with semver in `version.json` (repo root). A GitHub
Actions workflow bumps the patch version on every push to `main`, so each
deployment ships a new version. The running version is shown in the app's
footer and at `GET /api/version` (which also reports the git commit SHA on
Vercel).

To bump manually: `python3 scripts/bump_version.py [patch|minor|major]`.

## API

| Method | Endpoint                | Description                          |
| ------ | ----------------------- | ------------------------------------ |
| GET    | `/api/version`          | App version, git SHA, deploy env     |
| GET    | `/api/portfolio`        | Positions + live prices + totals     |
| POST   | `/api/portfolio`        | Add position `{symbol, shares, avg_cost}` |
| PUT    | `/api/portfolio/{sym}`  | Update shares / avg cost             |
| DELETE | `/api/portfolio/{sym}`  | Remove position                      |
| GET    | `/api/quote/{sym}`      | Live quote for one symbol            |
| GET    | `/api/search?q=`        | Symbol search                        |
| GET    | `/api/news`             | Aggregated US market headlines       |
| GET    | `/api/news/{sym}`       | Headlines for one ticker             |
| GET    | `/api/why/{sym}`        | Heuristic explanation of the day's move |

API docs: http://localhost:8000/docs while the backend is running.
