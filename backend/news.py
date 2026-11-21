"""Market news aggregation.

Free sources, no API keys required:

- CNBC RSS            (US top/market news)
- Yahoo Finance RSS   (S&P 500 market news + per-symbol headlines)
- MarketWatch RSS     (Dow Jones top-stories feed)
- Seeking Alpha RSS   (breaking market news)
- yfinance Search     (per-symbol news fallback/supplement)

Benzinga, Reuters, Bloomberg, The Fly, FinancialJuice and StockTitan
either have no public feed or are paywalled, so they are not included.
"""

from __future__ import annotations

import html
import re
import time
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import requests
import yfinance as yf

MARKET_FEEDS = [
    ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    (
        "Yahoo Finance",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC&region=US&lang=en-US",
    ),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("Seeking Alpha", "https://seekingalpha.com/market_currents.xml"),
]

YAHOO_SYMBOL_RSS = (
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
)

NEWS_TTL_SECONDS = 60
_market_cache: tuple[float, list] | None = None
_symbol_cache: dict[str, tuple[float, list]] = {}

_TAG_RE = re.compile(r"<[^>]+>")
_TITLE_KEY_RE = re.compile(r"[^a-z0-9]+")

DRIVER_CATEGORIES = [
    (
        "earnings / results",
        [
            "earnings",
            "revenue",
            "profit",
            "eps",
            "beat estimates",
            "misses estimates",
            "quarterly results",
            "q1",
            "q2",
            "q3",
            "q4",
        ],
    ),
    (
        "analyst action",
        [
            "upgrade",
            "downgrade",
            "price target",
            "initiated",
            "overweight",
            "underweight",
            "buy rating",
            "sell rating",
            "analyst",
        ],
    ),
    (
        "guidance / outlook",
        ["guidance", "outlook", "forecast", "raises", "lowers", "cuts forecast"],
    ),
    (
        "m&a / deals",
        [
            "acquisition",
            "acquire",
            "merger",
            "takeover",
            "deal",
            "stake",
            "buyout",
            "bid",
        ],
    ),
    (
        "regulatory / legal",
        [
            "sec",
            "fda",
            "lawsuit",
            "sues",
            "sued",
            "probe",
            "investigation",
            "antitrust",
            "regulator",
            "fine",
            "approval",
            "ban",
            "tariff",
        ],
    ),
    (
        "macro / fed",
        [
            "fed",
            "federal reserve",
            "interest rate",
            "inflation",
            "cpi",
            "jobs report",
            "treasury",
            "recession",
            "powell",
        ],
    ),
    (
        "buybacks / insider",
        ["buyback", "repurchase", "dividend", "insider", "stock split", "split"],
    ),
    (
        "product / ai",
        [
            "ai",
            "artificial intelligence",
            "launch",
            "unveils",
            "product",
            "chip",
            "iphone",
            "model",
        ],
    ),
    (
        "restructuring / layoffs",
        ["layoff", "layoffs", "job cuts", "restructuring", "ceo", "resigns", "cfo"],
    ),
    (
        "short seller / bearish report",
        ["short seller", "short-seller", "hindenburg", "fraud", "accounting"],
    ),
]


# Compiled once: whole-word matching so "sec" doesn't hit "sector" and
# "ai" doesn't hit "millionaire".
_DRIVER_PATTERNS = [
    (cat, re.compile(r"\b(?:" + "|".join(re.escape(k) for k in kws) + r")\b", re.I))
    for cat, kws in DRIVER_CATEGORIES
]


def _parse_date(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw.strip()).timestamp()
    except Exception:
        return None


def _clean(text: str | None) -> str:
    if not text:
        return ""
    return html.unescape(_TAG_RE.sub("", text)).strip()


def _title_key(title: str) -> str:
    return _TITLE_KEY_RE.sub(" ", title.lower()).strip()[:80]


def fetch_rss(name: str, url: str, limit: int = 25) -> list[dict]:
    """Fetch one RSS feed and normalize its items. Never raises."""
    try:
        res = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8,
        )
        res.raise_for_status()
        root = ElementTree.fromstring(res.content)
    except Exception:
        return []

    items = []
    for item in root.iter("item"):
        title = _clean(item.findtext("title"))
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        items.append(
            {
                "title": title,
                "link": link,
                "summary": _clean(item.findtext("description")),
                "published": _parse_date(item.findtext("pubDate")),
                "source": name,
            }
        )
        if len(items) >= limit:
            break
    return items


def _yf_search_news(symbol: str, limit: int = 10) -> list[dict]:
    """News from Yahoo's search API for a ticker/company query."""
    try:
        results = yf.Search(symbol, news_count=limit, enable_fuzzy_query=False)
    except Exception:
        return []
    items = []
    for n in results.news or []:
        title = _clean(n.get("title"))
        link = (n.get("link") or "").strip()
        if not title or not link:
            continue
        items.append(
            {
                "title": title,
                "link": link,
                "summary": _clean(n.get("summary")),
                "published": n.get("providerPublishTime"),
                "source": n.get("publisher") or "Yahoo Finance",
            }
        )
    return items


def _dedupe_sort(items: list[dict], limit: int) -> list[dict]:
    seen, out = set(), []
    for it in sorted(items, key=lambda i: i.get("published") or 0, reverse=True):
        key = _title_key(it["title"])
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
        if len(out) >= limit:
            break
    return out


def get_market_news(limit: int = 40) -> list[dict]:
    """Aggregated US market headlines, cached briefly."""
    global _market_cache
    now = time.time()
    if _market_cache and now - _market_cache[0] < NEWS_TTL_SECONDS:
        return _market_cache[1]

    with ThreadPoolExecutor(max_workers=len(MARKET_FEEDS)) as pool:
        per_feed = pool.map(lambda f: fetch_rss(*f), MARKET_FEEDS)
    items = [it for feed in per_feed for it in feed]
    if items:
        _market_cache = (now, _dedupe_sort(items, limit))
    return _market_cache[1] if _market_cache else []


def get_symbol_news(symbol: str, limit: int = 25) -> list[dict]:
    """Headlines for one ticker: Yahoo symbol RSS + Yahoo search news."""
    now = time.time()
    cached = _symbol_cache.get(symbol)
    if cached and now - cached[0] < NEWS_TTL_SECONDS:
        return cached[1]

    rss = fetch_rss("Yahoo Finance", YAHOO_SYMBOL_RSS.format(symbol=symbol), limit)
    search = _yf_search_news(symbol)
    items = _dedupe_sort(rss + search, limit)
    _symbol_cache[symbol] = (now, items)
    return items


def _categorize(title: str) -> list[str]:
    return [cat for cat, pat in _DRIVER_PATTERNS if pat.search(title)]


def explain_move(symbol: str, quote: dict) -> dict:
    """Heuristic 'why is it up/down' explanation built from recent headlines.

    Returns direction + magnitude, a written answer, the categorized driver
    headlines, and the raw recent news list.
    """
    news = get_symbol_news(symbol)
    price = quote.get("price")
    prev = quote.get("previous_close")
    change_pct = (
        round(100 * (price - prev) / prev, 2) if price is not None and prev else None
    )
    direction = "up" if (change_pct or 0) > 0 else "down" if (change_pct or 0) < 0 else "flat"

    # Keep the most recent headline per category.
    drivers: dict[str, dict] = {}
    for item in news:
        for cat in _categorize(item["title"]):
            if cat not in drivers:
                drivers[cat] = {
                    "category": cat,
                    "title": item["title"],
                    "link": item["link"],
                    "source": item["source"],
                    "published": item["published"],
                }

    name = quote.get("name") or symbol
    driver_list = list(drivers.values())
    if direction == "flat" or change_pct is None:
        answer = f"{symbol} is essentially flat today."
    else:
        mag = (
            "sharply" if abs(change_pct) >= 4 else "noticeably" if abs(change_pct) >= 2 else "slightly"
        )
        lead = f"{name} ({symbol}) is {direction} {mag}, {change_pct:+.2f}% versus the previous close."
        if driver_list:
            reasons = "; ".join(f"{d['category']}: \"{d['title']}\" ({d['source']})" for d in driver_list[:4])
            answer = f"{lead} Likely drivers from recent headlines — {reasons}."
        else:
            answer = (
                f"{lead} No single headline catalyst stands out in the last few "
                "days; the move may reflect broader market sentiment. See the "
                "latest headlines below."
            )

    return {
        "symbol": symbol,
        "name": name,
        "price": price,
        "currency": quote.get("currency"),
        "change_pct": change_pct,
        "direction": direction,
        "answer": answer,
        "drivers": driver_list,
        "news": news,
    }
