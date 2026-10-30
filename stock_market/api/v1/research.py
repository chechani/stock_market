# -*- coding: utf-8 -*-
"""Stock Market Research & Strategy Campaigns Engine (v1)

Implements TRK-101 - TRK-105:
- Research Campaign and Campaign Trade lifecycle management
- Moving Average Crossover & Momentum Backtesting Engine
- Multi-timeframe historical/synthetic candle simulation
- Performance analytics: Win Rate, Sharpe Ratio, Max Drawdown, Profit Factor
- Equity curve series generation
- Invariant: Live trading strictly disabled, execution_mode='paper_only'
"""

import math
import random
from datetime import datetime, timedelta
import frappe
from frappe import _
from frappe.utils import now_datetime, getdate, nowdate, flt, cint

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


def _generate_synthetic_series(symbol: str, count: int = 120, base_price: float = None):
    """Generate a realistic sequence of OHLCV candles for backtesting."""
    if not base_price:
        base_price = BASE_PRICES.get(symbol.upper(), 1500.0)

    candles = []
    current_time = datetime.now() - timedelta(minutes=count * 15)
    price = base_price

    # Use deterministic drift with realistic volatility
    trend = random.choice([0.0003, 0.0005, -0.0002, 0.0008, 0.0001])
    volatility = 0.008

    for _ in range(count):
        change = price * (trend + random.gauss(0, volatility))
        open_p = price
        close_p = round(max(10.0, open_p + change), 2)
        high_p = round(max(open_p, close_p) + abs(random.gauss(0, volatility * price * 0.7)), 2)
        low_p = round(min(open_p, close_p) - abs(random.gauss(0, volatility * price * 0.7)), 2)
        volume = int(random.randint(25000, 350000))

        candles.append({
            "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "volume": volume
        })

        price = close_p
        current_time += timedelta(minutes=15)

    return candles


def _calculate_sma(prices, period):
    """Calculate Simple Moving Average."""
    smas = []
    for i in range(len(prices)):
        if i + 1 < period:
            smas.append(None)
        else:
            window = prices[i + 1 - period: i + 1]
            smas.append(sum(window) / float(period))
    return smas


@frappe.whitelist(allow_guest=True)
def get_campaigns(tenant=None):
    """TRK-102: List all research campaigns for the given tenant."""
    tenant = tenant or "pandey"
    campaigns = frappe.get_all(
        "Research Campaign",
        filters={"tenant": tenant},
        fields=[
            "name",
            "campaign_name",
            "tenant",
            "strategy",
            "universe",
            "timeframe",
            "status",
            "start_date",
            "end_date",
            "initial_capital_inr",
            "ending_capital_inr",
            "total_trades",
            "winning_trades",
            "losing_trades",
            "win_rate_pct",
            "pnl_inr",
            "return_pct",
            "max_drawdown_pct",
            "sharpe_ratio",
            "profit_factor",
            "fast_ma",
            "slow_ma",
            "stop_loss_pct",
            "take_profit_pct",
            "execution_mode",
            "creation"
        ],
        order_by="creation desc",
        limit=50
    )

    return {
        "tenant": tenant,
        "count": len(campaigns),
        "campaigns": campaigns
    }


@frappe.whitelist(allow_guest=True)
def get_campaign_detail(campaign_id):
    """TRK-103: Fetch comprehensive campaign details including trades and equity curve."""
    if not campaign_id:
        frappe.throw(_("campaign_id parameter is required"))

    if not frappe.db.exists("Research Campaign", campaign_id):
        frappe.throw(_("Campaign {0} not found").format(campaign_id))

    campaign = frappe.get_doc("Research Campaign", campaign_id).as_dict()

    trades = frappe.get_all(
        "Campaign Trade",
        filters={"campaign": campaign_id},
        fields=[
            "name",
            "campaign",
            "symbol",
            "direction",
            "quantity",
            "status",
            "entry_time",
            "entry_price",
            "exit_time",
            "exit_price",
            "pnl_inr",
            "return_pct",
            "exit_reason",
            "notes"
        ],
        order_by="entry_time asc"
    )

    # Compute Equity Curve Progression
    initial_cap = flt(campaign.get("initial_capital_inr", 500000.0))
    equity_curve = []

    running_cap = initial_cap
    peak_cap = initial_cap

    start_ts = str(campaign.get("start_date") or campaign.get("creation"))[:19]
    equity_curve.append({
        "time": start_ts,
        "equity": round(running_cap, 2),
        "drawdown_pct": 0.0,
        "pnl": 0.0,
        "trade_no": 0
    })

    for idx, tr in enumerate(trades, start=1):
        pnl = flt(tr.get("pnl_inr", 0.0))
        running_cap += pnl
        if running_cap > peak_cap:
            peak_cap = running_cap

        drawdown = round(((peak_cap - running_cap) / peak_cap) * 100.0, 2) if peak_cap > 0 else 0.0
        exit_ts = str(tr.get("exit_time") or tr.get("entry_time"))[:19]

        equity_curve.append({
            "time": exit_ts,
            "equity": round(running_cap, 2),
            "drawdown_pct": max(0.0, drawdown),
            "pnl": round(pnl, 2),
            "trade_no": idx
        })

    return {
        "campaign": campaign,
        "trades": trades,
        "equity_curve": equity_curve
    }


@frappe.whitelist(allow_guest=True)
def run_backtest(
    campaign_name=None,
    tenant=None,
    strategy=None,
    symbol="RELIANCE",
    timeframe="15m",
    start_date=None,
    end_date=None,
    initial_capital=500000.0,
    fast_ma=9,
    slow_ma=21,
    stop_loss_pct=2.0,
    take_profit_pct=4.0,
    notes=None
):
    """TRK-102 & TRK-103: Execute paper strategy backtest and persist campaign & trades."""
    tenant = tenant or "pandey"
    symbol = (symbol or "RELIANCE").upper().strip()
    fast_ma = max(2, cint(fast_ma or 9))
    slow_ma = max(fast_ma + 1, cint(slow_ma or 21))
    initial_capital = max(10000.0, flt(initial_capital or 500000.0))
    stop_loss_pct = max(0.5, flt(stop_loss_pct or 2.0))
    take_profit_pct = max(1.0, flt(take_profit_pct or 4.0))

    if not campaign_name:
        campaign_name = f"{symbol} MA({fast_ma}/{slow_ma}) Research"

    # Fetch candles from Market Candle if available, or generate synthetic series
    existing_candles = frappe.get_all(
        "Market Candle",
        filters={"symbol": symbol, "timeframe": timeframe},
        fields=["timestamp", "open", "high", "low", "close", "volume"],
        order_by="timestamp asc",
        limit=200
    )

    if len(existing_candles) >= slow_ma + 20:
        candles = existing_candles
    else:
        candles = _generate_synthetic_series(symbol, count=120)

    closes = [flt(c["close"]) for c in candles]
    fast_smas = _calculate_sma(closes, fast_ma)
    slow_smas = _calculate_sma(closes, slow_ma)

    trades = []
    in_position = False
    entry_price = 0.0
    entry_time = None
    entry_idx = 0
    trade_qty = max(1, int((initial_capital * 0.15) / closes[0])) if closes[0] > 0 else 25

    # Simulation loop
    for i in range(slow_ma, len(candles)):
        c = candles[i]
        curr_close = flt(c["close"])
        curr_high = flt(c["high"])
        curr_low = flt(c["low"])
        ts = str(c["timestamp"])

        prev_fast = fast_smas[i - 1]
        prev_slow = slow_smas[i - 1]
        curr_fast = fast_smas[i]
        curr_slow = slow_smas[i]

        if not in_position:
            # Bullish Crossover: Fast MA crosses above Slow MA
            if prev_fast is not None and prev_slow is not None:
                if prev_fast <= prev_slow and curr_fast > curr_slow:
                    in_position = True
                    entry_price = curr_close
                    entry_time = ts
                    entry_idx = i
        else:
            # Position is active: check Stop Loss or Take Profit or Bearish Crossover
            sl_price = entry_price * (1.0 - (stop_loss_pct / 100.0))
            tp_price = entry_price * (1.0 + (take_profit_pct / 100.0))

            exit_reason = None
            exit_price = curr_close

            if curr_low <= sl_price:
                exit_reason = "Stop Loss"
                exit_price = round(sl_price, 2)
            elif curr_high >= tp_price:
                exit_reason = "Take Profit"
                exit_price = round(tp_price, 2)
            elif prev_fast is not None and prev_slow is not None and prev_fast >= prev_slow and curr_fast < curr_slow:
                exit_reason = "Signal Reversal"
                exit_price = curr_close
            elif i == len(candles) - 1:
                exit_reason = "Time Exit"
                exit_price = curr_close

            if exit_reason:
                pnl = round((exit_price - entry_price) * trade_qty, 2)
                ret_pct = round(((exit_price - entry_price) / entry_price) * 100.0, 2)
                trades.append({
                    "symbol": symbol,
                    "direction": "BUY",
                    "quantity": trade_qty,
                    "status": "CLOSED",
                    "entry_time": entry_time,
                    "entry_price": round(entry_price, 2),
                    "exit_time": ts,
                    "exit_price": exit_price,
                    "pnl_inr": pnl,
                    "return_pct": ret_pct,
                    "exit_reason": exit_reason,
                    "notes": f"Simulated paper trade. Fast MA: {fast_ma}, Slow MA: {slow_ma}."
                })
                in_position = False

    # Aggregate performance metrics
    total_trades = len(trades)
    winning_trades = sum(1 for t in trades if t["pnl_inr"] > 0)
    losing_trades = sum(1 for t in trades if t["pnl_inr"] <= 0)
    win_rate_pct = round((winning_trades / total_trades * 100.0), 2) if total_trades > 0 else 0.0

    total_pnl = round(sum(t["pnl_inr"] for t in trades), 2)
    ending_capital = round(initial_capital + total_pnl, 2)
    return_pct = round((total_pnl / initial_capital) * 100.0, 2)

    gross_profit = sum(t["pnl_inr"] for t in trades if t["pnl_inr"] > 0)
    gross_loss = abs(sum(t["pnl_inr"] for t in trades if t["pnl_inr"] < 0))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (round(gross_profit, 2) if gross_profit > 0 else 1.0)

    # Compute Drawdown & Sharpe
    peak = initial_capital
    running_eq = initial_capital
    drawdowns = [0.0]
    returns_series = []

    for t in trades:
        running_eq += t["pnl_inr"]
        if running_eq > peak:
            peak = running_eq
        dd = ((peak - running_eq) / peak) * 100.0
        drawdowns.append(dd)
        returns_series.append(t["return_pct"])

    max_drawdown_pct = round(max(drawdowns), 2) if drawdowns else 0.0

    # Annualized Sharpe approximation
    if len(returns_series) > 1:
        mean_ret = sum(returns_series) / len(returns_series)
        var = sum((r - mean_ret) ** 2 for r in returns_series) / (len(returns_series) - 1)
        std_ret = math.sqrt(var) if var > 0 else 0.0
        sharpe = round((mean_ret / std_ret) * math.sqrt(252), 2) if std_ret > 0 else 0.0
    else:
        sharpe = 0.0

    # Ensure strategy exists or default to STR-GAR_WEEKLY_LONG-2026
    if not strategy or not frappe.db.exists("Strategy Definition", strategy):
        first_strat = frappe.db.get_value("Strategy Definition", {}, "name")
        strategy = first_strat

    # Create Research Campaign Doc
    campaign_doc = frappe.get_doc({
        "doctype": "Research Campaign",
        "campaign_name": campaign_name,
        "tenant": tenant,
        "strategy": strategy,
        "universe": symbol,
        "timeframe": timeframe,
        "status": "Completed",
        "start_date": str(candles[0]["timestamp"])[:10],
        "end_date": str(candles[-1]["timestamp"])[:10],
        "initial_capital_inr": initial_capital,
        "ending_capital_inr": ending_capital,
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate_pct": win_rate_pct,
        "pnl_inr": total_pnl,
        "return_pct": return_pct,
        "max_drawdown_pct": max_drawdown_pct,
        "sharpe_ratio": sharpe,
        "profit_factor": profit_factor,
        "fast_ma": fast_ma,
        "slow_ma": slow_ma,
        "stop_loss_pct": stop_loss_pct,
        "take_profit_pct": take_profit_pct,
        "execution_mode": "paper_only",
        "notes": notes or f"Backtest simulated across {len(candles)} {timeframe} candles. Live trading disabled."
    })
    campaign_doc.insert(ignore_permissions=True)

    # Insert trades linked to campaign
    persisted_trades = []
    for tr in trades:
        trade_doc = frappe.get_doc({
            "doctype": "Campaign Trade",
            "campaign": campaign_doc.name,
            "symbol": tr["symbol"],
            "direction": tr["direction"],
            "quantity": tr["quantity"],
            "status": tr["status"],
            "entry_time": tr["entry_time"],
            "entry_price": tr["entry_price"],
            "exit_time": tr["exit_time"],
            "exit_price": tr["exit_price"],
            "pnl_inr": tr["pnl_inr"],
            "return_pct": tr["return_pct"],
            "exit_reason": tr["exit_reason"],
            "notes": tr["notes"]
        })
        trade_doc.insert(ignore_permissions=True)
        persisted_trades.append(trade_doc.as_dict())

    frappe.db.commit()

    # Generate Equity Curve response
    equity_curve = []
    eq_val = initial_capital
    peak_val = initial_capital
    equity_curve.append({
        "time": str(candles[0]["timestamp"])[:19],
        "equity": round(eq_val, 2),
        "drawdown_pct": 0.0,
        "pnl": 0.0,
        "trade_no": 0
    })

    for idx, tr in enumerate(persisted_trades, start=1):
        pnl = flt(tr.get("pnl_inr", 0.0))
        eq_val += pnl
        if eq_val > peak_val:
            peak_val = eq_val
        dd = round(((peak_val - eq_val) / peak_val) * 100.0, 2) if peak_val > 0 else 0.0

        equity_curve.append({
            "time": str(tr.get("exit_time"))[:19],
            "equity": round(eq_val, 2),
            "drawdown_pct": max(0.0, dd),
            "pnl": round(pnl, 2),
            "trade_no": idx
        })

    return {
        "success": True,
        "message": f"Research campaign {campaign_doc.name} backtest completed with {total_trades} trades.",
        "campaign": campaign_doc.as_dict(),
        "trades": persisted_trades,
        "equity_curve": equity_curve
    }

