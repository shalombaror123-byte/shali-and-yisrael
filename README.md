# Portfolio Tracker

A finance web app that tracks a stock/ETF portfolio with live prices from
Yahoo Finance.

- **Backend** (`backend/`): FastAPI + yfinance. Positions are stored in
  `backend/portfolio.json`. Prices are fetched live and cached for 15s.
- **Frontend** (`frontend/`): React (Vite). Auto-refreshes every 15s.

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

## API

| Method | Endpoint                | Description                          |
| ------ | ----------------------- | ------------------------------------ |
| GET    | `/api/portfolio`        | Positions + live prices + totals     |
| POST   | `/api/portfolio`        | Add position `{symbol, shares, avg_cost}` |
| PUT    | `/api/portfolio/{sym}`  | Update shares / avg cost             |
| DELETE | `/api/portfolio/{sym}`  | Remove position                      |
| GET    | `/api/quote/{sym}`      | Live quote for one symbol            |
| GET    | `/api/search?q=`        | Symbol search                        |

API docs: http://localhost:8000/docs while the backend is running.
