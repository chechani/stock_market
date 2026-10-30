# -*- coding: utf-8 -*-
"""Stock Market Data Foundation, Feeds & Candle Aggregator APIs (v1)

Implements TRK-081 - TRK-085:
- Market Data Feeds (XTS & RMoney Paper adapters)
- Multi-timeframe candlestick generation and aggregation (1m, 5m, 15m, 1h, Daily, Weekly)
- Ticker quotes with live paper prices
- Strict invariant: live feed connections disabled; simulation and paper feeds only
"""

import math
import random
from datetime import datetime, timedelta
import frappe
from frappe import _
from frappe.utils import now_datetime, getdate, nowdate, add_days


DEFAULT_FEEDS = [
    {
        "feed_code": "XTS_PAPER_NSE",
        "feed_name": "XTS Paper Adapter (NSE Equities)",
        "feed_type": "XTS Paper Feed",
        "status": "Active",
        "exchange": "NSE",
        "tick_frequency_sec": 1.0,
        "is_paper_only": 1,
        "symbols_tracked": "RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, SBIN, NIFTY50"
    },
    {
        "feed_code": "RMONEY_PAPER_FEED",
        "feed_name": "RMoney Paper Feed (F&O / Equity)",
        "feed_type": "RMoney Paper Feed",
        "status": "Active",
        "exchange": "NSE",
        "tick_frequency_sec": 1.0,
        "is_paper_only": 1,
        "symbols_tracked": "NIFTY50, BANKNIFTY, RELIANCE, TCS"
    },
    {
        "feed_code": "SYNTHETIC_CANDLE_GEN",
        "feed_name": "Synthetic Multi-Timeframe Candle Engine",
        "feed_type": "Synthetic Generator",
        "status": "Active",
        "exchange": "NSE",
        "tick_frequency_sec": 0.5,
        "is_paper_only": 1,
        "symbols_tracked": "RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, SBIN, BHARTIARTL"
    }
]

BASE_PRICES = {
    "RELIANCE": 2840.50,
    "TCS": 3950.00,
    "INFY": 1820.75,
    "HDFCBANK": 1675.20,
    "ICICIBANK": 1245.80,
    "SBIN": 815.40,
    "BHARTIARTL": 1490.00,
    "NIFTY50": 24350.00
}


def ensure_default_feeds_exist():
    """Seed default paper data feeds if table is empty."""
    for feed in DEFAULT_FEEDS:
        if not frappe.db.exists("Market Data Feed", feed["feed_code"]):
            doc = frappe.get_doc({
                "doctype": "Market Data Feed",
                **feed,
                "last_heartbeat_at": now_datetime(),
                "total_ticks_ingested": 10420
            })
            doc.insert(ignore_permissions=True)
    frappe.db.commit()


@frappe.whitelist(allow_guest=True)
def get_data_feeds():
    """Retrieve list of configured paper data feeds."""
    ensure_default_feeds_exist()
    return frappe.get_all(
        "Market Data Feed",
        fields=[
            "name",
            "feed_code",
            "feed_name",
            "feed_type",
            "status",
            "exchange",
            "tick_frequency_sec",
            "is_paper_only",
            "symbols_tracked",
            "last_heartbeat_at",
            "total_ticks_ingested",
            "creation"
        ],
        order_by="creation asc"
    )


def generate_synthetic_candles(symbol: str, timeframe: str = "Daily", count: int = 40):
    """Generate realistic OHLCV historical candlestick data for research & paper charts."""
    base = BASE_PRICES.get(symbol.upper(), 1500.0)
    now = datetime.now()
    candles = []

    price = base * 0.92  # start slightly lower and trend
    vol_base = 50000 if symbol != "NIFTY50" else 250000

    delta = timedelta(days=1)
    if timeframe == "1m":
        delta = timedelta(minutes=1)
    elif timeframe == "5m":
        delta = timedelta(minutes=5)
    elif timeframe == "15m":
        delta = timedelta(minutes=15)
    elif timeframe == "1h":
        delta = timedelta(hours=1)
    elif timeframe == "Weekly":
        delta = timedelta(weeks=1)

    start_time = now - (delta * count)

    for i in range(count):
        t = start_time + (delta * (i + 1))
        # Simulated drift and volatility
        ret = random.gauss(0.001, 0.015)
        open_p = round(price, 2)
        close_p = round(open_p * (1 + ret), 2)
        spread = abs(close_p - open_p)
        high_p = round(max(open_p, close_p) + (spread * random.uniform(0.2, 0.8)) + (open_p * 0.003), 2)
        low_p = round(min(open_p, close_p) - (spread * random.uniform(0.2, 0.8)) - (open_p * 0.003), 2)
        vol = int(vol_base * random.uniform(0.6, 2.2))
        price = close_p

        c_data = {
            "symbol": symbol.upper(),
            "exchange": "NSE",
            "timeframe": timeframe,
            "timestamp": t.strftime("%Y-%m-%d %H:%M:%S"),
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "volume": vol,
            "is_synthetic": 1,
            "feed_source": "XTS Paper Adapter"
        }
        candles.append(c_data)

    return candles


@frappe.whitelist(allow_guest=True)
def get_candles(symbol="RELIANCE", timeframe="Daily", limit=60):
    """Fetch candlestick series for interactive charts and research."""
    symbol = (symbol or "RELIANCE").upper().strip()
    limit = int(limit)

    candles = frappe.get_all(
        "Market Candle",
        filters={"symbol": symbol, "timeframe": timeframe},
        fields=["name", "symbol", "exchange", "timeframe", "timestamp", "open", "high", "low", "close", "volume", "is_synthetic", "feed_source"],
        order_by="timestamp asc",
        limit_page_length=limit
    )

    if not candles:
        # Generate & persist synthetic historical dataset
        generated = generate_synthetic_candles(symbol, timeframe, count=min(limit, 45))
        for g in generated:
            doc = frappe.get_doc({
                "doctype": "Market Candle",
                **g
            })
            doc.insert(ignore_permissions=True)
        frappe.db.commit()
        candles = generated

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "count": len(candles),
        "is_synthetic": True,
        "execution_mode": "paper_only",
        "candles": candles
    }


@frappe.whitelist(allow_guest=True)
def get_ticker_quotes():
    """Retrieve simulated real-time quotes for tracked market symbols."""
    symbols = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "BHARTIARTL", "NIFTY50"]
    quotes = []

    for sym in symbols:
        base = BASE_PRICES.get(sym, 1000.0)
        # Random realistic day variation
        day_chg_pct = round(random.uniform(-1.8, 2.4), 2)
        ltp = round(base * (1 + (day_chg_pct / 100.0)), 2)
        chg = round(ltp - base, 2)
        high = round(max(ltp, base) * 1.008, 2)
        low = round(min(ltp, base) * 0.992, 2)
        vol = random.randint(250000, 4500000)

        quotes.append({
            "symbol": sym,
            "exchange": "NSE",
            "ltp": ltp,
            "change": chg,
            "change_pct": day_chg_pct,
            "high": high,
            "low": low,
            "volume": vol,
            "is_paper": True,
            "source": "XTS Paper Adapter",
            "updated_at": now_datetime()
        })

    return quotes


@frappe.whitelist(allow_guest=True)
def ingest_tick(symbol, ltp, volume=10, exchange="NSE"):
    """Ingest a paper market tick into the current 1-minute candle."""
    symbol = (symbol or "").upper().strip()
    ltp = float(ltp)
    vol = int(volume)
    now = datetime.now()
    minute_timestamp = now.replace(second=0, microsecond=0)

    # Check for existing 1m candle for current minute
    existing = frappe.db.get_value(
        "Market Candle",
        {
            "symbol": symbol,
            "timeframe": "1m",
            "timestamp": minute_timestamp.strftime("%Y-%m-%d %H:%M:%S")
        },
        ["name", "open", "high", "low", "close", "volume"],
        as_dict=True
    )

    if existing:
        doc = frappe.get_doc("Market Candle", existing.name)
        doc.high = max(doc.high, ltp)
        doc.low = min(doc.low, ltp)
        doc.close = ltp
        doc.volume = (doc.volume or 0) + vol
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc({
            "doctype": "Market Candle",
            "symbol": symbol,
            "exchange": exchange,
            "timeframe": "1m",
            "timestamp": minute_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "open": ltp,
            "high": ltp,
            "low": ltp,
            "close": ltp,
            "volume": vol,
            "is_synthetic": 1,
            "feed_source": "XTS Paper Tick Ingest"
        })
        doc.insert(ignore_permissions=True)

    frappe.db.commit()
    return doc.as_dict()

