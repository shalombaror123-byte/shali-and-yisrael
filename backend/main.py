"""Portfolio tracker backend.

Serves the user's portfolio enriched with live market data from Yahoo
Finance (via yfinance). Positions are persisted to portfolio.json.
"""

import json
import threading
import time
from pathlib import Path

import yfinance as yf
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from news import explain_move, get_market_news, get_symbol_news

DATA_FILE = Path(__file__).parent / "portfolio.json"
_lock = threading.Lock()

# Simple in-memory quote cache so the frontend can poll frequently
# without hammering Yahoo.
QUOTE_TTL_SECONDS = 15
_quote_cache: dict[str, tuple[float, dict]] = {}

app = FastAPI(title="Portfolio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- persistence ----------

def load_positions() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    return json.loads(DATA_FILE.read_text())


def save_positions(positions: list[dict]) -> None:
    DATA_FILE.write_text(json.dumps(positions, indent=2))


# ---------- models ----------

class PositionIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    shares: float = Field(gt=0)
    avg_cost: float = Field(ge=0)


# ---------- market data ----------

def _extract_quote(symbol: str, ticker: yf.Ticker) -> dict:
    """Pull a quote out of a yfinance Ticker, tolerating schema changes."""
    quote = {"symbol": symbol}
    try:
        fi = ticker.fast_info
        quote["price"] = _first(fi, "last_price", "lastPrice")
        quote["previous_close"] = _first(fi, "previous_close", "previousClose")
        quote["currency"] = _first(fi, "currency") or "USD"
        quote["day_high"] = _first(fi, "day_high", "dayHigh")
        quote["day_low"] = _first(fi, "day_low", "dayLow")
    except Exception:
        pass
    try:
        info = ticker.info
        quote.setdefault("price", info.get("regularMarketPrice"))
        quote["price"] = quote.get("price") or info.get("regularMarketPrice")
        quote["name"] = info.get("shortName") or info.get("longName") or symbol
        quote["currency"] = quote.get("currency") or info.get("currency") or "USD"
    except Exception:
        quote.setdefault("name", symbol)
    if quote.get("price") is None:
        raise HTTPException(status_code=404, detail=f"No price data for {symbol}")
    return quote


def _first(mapping, *keys):
    for k in keys:
        try:
            v = mapping[k]
        except (KeyError, TypeError):
            v = getattr(mapping, k, None)
        if v is not None:
            return v
    return None


def get_quotes(symbols: list[str]) -> dict[str, dict]:
    """Return {symbol: quote} using a short-lived cache."""
    now = time.time()
    result, missing = {}, []
    for s in symbols:
        cached = _quote_cache.get(s)
        if cached and now - cached[0] < QUOTE_TTL_SECONDS:
            result[s] = cached[1]
        else:
            missing.append(s)

    if missing:
        tickers = yf.Tickers(" ".join(missing)).tickers
        for s in missing:
            t = tickers.get(s) or tickers.get(s.upper())
            if t is None:
                result[s] = {"symbol": s, "error": "unknown symbol"}
                continue
            try:
                q = _extract_quote(s, t)
                _quote_cache[s] = (now, q)
                result[s] = q
            except HTTPException as e:
                result[s] = {"symbol": s, "error": e.detail}
    return result


def enrich(position: dict, quote: dict) -> dict:
    shares, avg_cost = position["shares"], position["avg_cost"]
    row = {**position, **{k: v for k, v in quote.items() if k != "symbol"}}
    row["cost_basis"] = round(shares * avg_cost, 2)
    if quote.get("price") is not None:
        row["market_value"] = round(shares * quote["price"], 2)
        row["unrealized_pl"] = round(row["market_value"] - row["cost_basis"], 2)
        row["unrealized_pl_pct"] = (
            round(100 * (quote["price"] - avg_cost) / avg_cost, 2)
            if avg_cost else None
        )
        prev = quote.get("previous_close")
        if prev:
            row["day_change_pct"] = round(100 * (quote["price"] - prev) / prev, 2)
    else:
        row.update(market_value=None, unrealized_pl=None, unrealized_pl_pct=None)
    return row


# ---------- routes ----------

@app.get("/api/portfolio")
def portfolio():
    positions = load_positions()
    quotes = get_quotes([p["symbol"] for p in positions]) if positions else {}
    rows = [enrich(p, quotes.get(p["symbol"], {})) for p in positions]
    total_mv = sum(r["market_value"] or 0 for r in rows)
    total_cost = sum(r["cost_basis"] for r in rows)
    return {
        "positions": rows,
        "summary": {
            "market_value": round(total_mv, 2),
            "cost_basis": round(total_cost, 2),
            "unrealized_pl": round(total_mv - total_cost, 2),
            "unrealized_pl_pct": round(100 * (total_mv - total_cost) / total_cost, 2)
            if total_cost else None,
            "updated_at": int(time.time()),
        },
    }


@app.post("/api/portfolio", status_code=201)
def add_position(pos: PositionIn):
    symbol = pos.symbol.upper().strip()
    # Validate the symbol against Yahoo before saving.
    quote = get_quotes([symbol])[symbol]
    if "error" in quote:
        raise HTTPException(status_code=400, detail=f"Unknown symbol: {symbol}")
    with _lock:
        positions = load_positions()
        for p in positions:
            if p["symbol"] == symbol:
                raise HTTPException(
                    status_code=409,
                    detail=f"{symbol} already in portfolio; use PUT to update",
                )
        positions.append(
            {"symbol": symbol, "shares": pos.shares, "avg_cost": pos.avg_cost}
        )
        save_positions(positions)
    return enrich(positions[-1], quote)


@app.put("/api/portfolio/{symbol}")
def update_position(symbol: str, pos: PositionIn):
    symbol = symbol.upper().strip()
    with _lock:
        positions = load_positions()
        for i, p in enumerate(positions):
            if p["symbol"] == symbol:
                positions[i] = {
                    "symbol": symbol,
                    "shares": pos.shares,
                    "avg_cost": pos.avg_cost,
                }
                save_positions(positions)
                return positions[i]
    raise HTTPException(status_code=404, detail=f"{symbol} not in portfolio")


@app.delete("/api/portfolio/{symbol}", status_code=204)
def delete_position(symbol: str):
    symbol = symbol.upper().strip()
    with _lock:
        positions = load_positions()
        remaining = [p for p in positions if p["symbol"] != symbol]
        if len(remaining) == len(positions):
            raise HTTPException(status_code=404, detail=f"{symbol} not in portfolio")
        save_positions(remaining)


@app.get("/api/quote/{symbol}")
def quote(symbol: str):
    symbol = symbol.upper().strip()
    q = get_quotes([symbol])[symbol]
    if "error" in q:
        raise HTTPException(status_code=404, detail=q["error"])
    return q


@app.get("/api/search")
def search(q: str):
    try:
        results = yf.Search(q, max_results=8).quotes
        return [
            {
                "symbol": r.get("symbol"),
                "name": r.get("shortname") or r.get("longname"),
                "type": r.get("quoteType"),
                "exchange": r.get("exchange"),
            }
            for r in results
            if r.get("symbol")
        ]
    except Exception:
        return []


# ---------- news routes ----------


@app.get("/api/news")
def market_news():
    return {"news": get_market_news(), "updated_at": int(time.time())}


@app.get("/api/news/{symbol}")
def symbol_news(symbol: str):
    symbol = symbol.upper().strip()
    return {"symbol": symbol, "news": get_symbol_news(symbol)}


@app.get("/api/why/{symbol}")
def why(symbol: str):
    symbol = symbol.upper().strip()
    q = get_quotes([symbol])[symbol]
    if "error" in q:
        raise HTTPException(status_code=404, detail=q["error"])
    return explain_move(symbol, q)
