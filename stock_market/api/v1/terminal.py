# -*- coding: utf-8 -*-
"""Stock Market Read-Only Trading Terminal & Paper Order Execution APIs (v1)

Implements TRK-091 - TRK-095:
- Level 2 Market Depth (5-depth bids & asks)
- Paper order ticket submission & instantaneous simulation fills
- Position management & unrealized/realized PnL tracking
- Hard safety invariant: live execution strictly rejected
"""

import random
import frappe
from frappe import _
from frappe.utils import now_datetime, getdate, nowdate


BASE_SYMBOL_PRICES = {
    "RELIANCE": 2840.50,
    "TCS": 3950.00,
    "INFY": 1820.75,
    "HDFCBANK": 1675.20,
    "ICICIBANK": 1245.80,
    "SBIN": 815.40,
    "BHARTIARTL": 1490.00,
    "NIFTY50": 24350.00
}


def get_current_paper_price(symbol: str) -> float:
    """Retrieve latest price from market candles or base map."""
    symbol = (symbol or "RELIANCE").upper()
    latest_candle = frappe.db.get_value(
        "Market Candle",
        {"symbol": symbol},
        "close",
        order_by="timestamp desc"
    )
    if latest_candle:
        return float(latest_candle)
    return BASE_SYMBOL_PRICES.get(symbol, 1500.0)


@frappe.whitelist(allow_guest=True)
def get_order_book_depth(symbol="RELIANCE"):
    """TRK-092: Generate Level 2 (5-depth) order book for paper simulation."""
    symbol = (symbol or "RELIANCE").upper().strip()
    ltp = get_current_paper_price(symbol)

    tick = 0.05
    spread = tick * random.choice([1, 2, 3])

    bids = []
    asks = []

    best_bid = round(ltp - (spread / 2.0), 2)
    best_ask = round(ltp + (spread / 2.0), 2)

    total_bid_qty = 0
    total_ask_qty = 0

    for i in range(5):
        bid_price = round(best_bid - (i * tick), 2)
        bid_qty = random.randint(150, 3200) * (5 - i)
        bid_orders = random.randint(3, 28)
        total_bid_qty += bid_qty
        bids.append({
            "price": bid_price,
            "quantity": bid_qty,
            "orders": bid_orders
        })

        ask_price = round(best_ask + (i * tick), 2)
        ask_qty = random.randint(150, 3200) * (5 - i)
        ask_orders = random.randint(3, 28)
        total_ask_qty += ask_qty
        asks.append({
            "price": ask_price,
            "quantity": ask_qty,
            "orders": ask_orders
        })

    return {
        "symbol": symbol,
        "ltp": ltp,
        "exchange": "NSE",
        "spread": round(best_ask - best_bid, 2),
        "total_bid_quantity": total_bid_qty,
        "total_ask_quantity": total_ask_qty,
        "bids": bids,
        "asks": asks,
        "is_paper": True,
        "timestamp": now_datetime()
    }


@frappe.whitelist(allow_guest=True)
def get_paper_orders(tenant=None, symbol=None):
    """Retrieve submitted paper order tickets."""
    filters = {}
    if tenant:
        filters["tenant"] = tenant
    if symbol:
        filters["symbol"] = symbol.upper()

    return frappe.get_all(
        "Paper Order Ticket",
        fields=[
            "name",
            "tenant",
            "symbol",
            "exchange",
            "transaction_type",
            "order_type",
            "quantity",
            "price",
            "trigger_price",
            "status",
            "execution_price",
            "execution_mode",
            "submitted_at",
            "executed_at",
            "notes"
        ],
        filters=filters,
        order_by="submitted_at desc",
        limit_page_length=50
    )


@frappe.whitelist(allow_guest=True)
def get_paper_positions(tenant=None, status="OPEN"):
    """Retrieve paper positions with live mark-to-market valuations."""
    filters = {}
    if tenant:
        filters["tenant"] = tenant
    if status and status != "ALL":
        filters["status"] = status

    positions = frappe.get_all(
        "Paper Position",
        fields=[
            "name",
            "tenant",
            "symbol",
            "exchange",
            "direction",
            "status",
            "quantity",
            "avg_entry_price",
            "current_price",
            "unrealized_pnl",
            "unrealized_pnl_pct",
            "realized_pnl",
            "execution_mode",
            "opened_at",
            "closed_at"
        ],
        filters=filters,
        order_by="opened_at desc"
    )

    # Recalculate live mark-to-market for OPEN positions
    for pos in positions:
        if pos.status == "OPEN":
            live_price = get_current_paper_price(pos.symbol)
            pos["current_price"] = live_price
            if pos.direction == "LONG":
                pos["unrealized_pnl"] = round((live_price - pos.avg_entry_price) * pos.quantity, 2)
                pos["unrealized_pnl_pct"] = round(((live_price - pos.avg_entry_price) / pos.avg_entry_price) * 100, 2)
            else:
                pos["unrealized_pnl"] = round((pos.avg_entry_price - live_price) * pos.quantity, 2)
                pos["unrealized_pnl_pct"] = round(((pos.avg_entry_price - live_price) / pos.avg_entry_price) * 100, 2)

    return positions


@frappe.whitelist(allow_guest=True)
def submit_paper_order(
    tenant,
    symbol,
    transaction_type,
    order_type="MARKET",
    quantity=1,
    price=0.0,
    trigger_price=0.0,
    mandate=None,
    strategy=None
):
    """TRK-093 / TRK-095: Submit simulated order and update positions safely."""
    if not tenant:
        frappe.throw(_("Tenant is required."))
    if not symbol:
        frappe.throw(_("Symbol is required."))

    quantity = int(quantity)
    if quantity <= 0:
        frappe.throw(_("Quantity must be positive."))

    transaction_type = transaction_type.upper().strip()
    if transaction_type not in ("BUY", "SELL"):
        frappe.throw(_("Transaction type must be BUY or SELL."))

    order_type = order_type.upper().strip()

    current_price = get_current_paper_price(symbol)
    fill_price = current_price if order_type == "MARKET" else float(price or current_price)

    # Create Paper Order Ticket
    order_doc = frappe.get_doc({
        "doctype": "Paper Order Ticket",
        "tenant": tenant,
        "symbol": symbol.upper(),
        "exchange": "NSE",
        "transaction_type": transaction_type,
        "order_type": order_type,
        "quantity": quantity,
        "price": float(price or current_price),
        "trigger_price": float(trigger_price or 0.0),
        "status": "EXECUTED",
        "execution_price": fill_price,
        "execution_mode": "paper_only",
        "mandate": mandate,
        "strategy": strategy,
        "submitted_at": now_datetime(),
        "executed_at": now_datetime(),
        "notes": f"Simulated paper fill at ₹{fill_price:.2f} via Terminal Engine."
    })
    order_doc.insert(ignore_permissions=True)

    # Update or Create Paper Position
    direction = "LONG" if transaction_type == "BUY" else "SHORT"
    existing_pos = frappe.db.get_value(
        "Paper Position",
        {"tenant": tenant, "symbol": symbol.upper(), "status": "OPEN"},
        ["name", "direction", "quantity", "avg_entry_price"],
        as_dict=True
    )

    if existing_pos:
        if existing_pos.direction == direction:
            # Add to position
            new_qty = existing_pos.quantity + quantity
            new_avg = round(((existing_pos.avg_entry_price * existing_pos.quantity) + (fill_price * quantity)) / new_qty, 2)
            pos_doc = frappe.get_doc("Paper Position", existing_pos.name)
            pos_doc.quantity = new_qty
            pos_doc.avg_entry_price = new_avg
            pos_doc.current_price = fill_price
            pos_doc.save(ignore_permissions=True)
        else:
            # Reversing or reducing position
            pos_doc = frappe.get_doc("Paper Position", existing_pos.name)
            if quantity >= existing_pos.quantity:
                # Close existing position
                pnl = (fill_price - existing_pos.avg_entry_price) * existing_pos.quantity if existing_pos.direction == "LONG" else (existing_pos.avg_entry_price - fill_price) * existing_pos.quantity
                pos_doc.status = "CLOSED"
                pos_doc.closed_at = now_datetime()
                pos_doc.realized_pnl = round(pnl, 2)
                pos_doc.current_price = fill_price
                pos_doc.unrealized_pnl = 0
                pos_doc.unrealized_pnl_pct = 0
                pos_doc.save(ignore_permissions=True)

                remaining = quantity - existing_pos.quantity
                if remaining > 0:
                    # Open new reverse position
                    new_pos = frappe.get_doc({
                        "doctype": "Paper Position",
                        "tenant": tenant,
                        "symbol": symbol.upper(),
                        "exchange": "NSE",
                        "direction": direction,
                        "status": "OPEN",
                        "quantity": remaining,
                        "avg_entry_price": fill_price,
                        "current_price": fill_price,
                        "execution_mode": "paper_only",
                        "opened_at": now_datetime()
                    })
                    new_pos.insert(ignore_permissions=True)
            else:
                # Partial reduce
                pos_doc.quantity -= quantity
                pos_doc.current_price = fill_price
                pos_doc.save(ignore_permissions=True)
    else:
        # Create brand new position
        pos_doc = frappe.get_doc({
            "doctype": "Paper Position",
            "tenant": tenant,
            "symbol": symbol.upper(),
            "exchange": "NSE",
            "direction": direction,
            "status": "OPEN",
            "quantity": quantity,
            "avg_entry_price": fill_price,
            "current_price": fill_price,
            "execution_mode": "paper_only",
            "opened_at": now_datetime()
        })
        pos_doc.insert(ignore_permissions=True)

    frappe.db.commit()

    return {
        "order": order_doc.as_dict(),
        "position": pos_doc.as_dict(),
        "fill_price": fill_price
    }


@frappe.whitelist(allow_guest=True)
def close_paper_position(position_name):
    """Close an open paper position and realize profit/loss."""
    if not position_name or not frappe.db.exists("Paper Position", position_name):
        frappe.throw(_(f"Position '{position_name}' not found."))

    pos = frappe.get_doc("Paper Position", position_name)
    if pos.status == "CLOSED":
        frappe.throw(_("Position is already closed."))

    live_price = get_current_paper_price(pos.symbol)
    if pos.direction == "LONG":
        pnl = (live_price - pos.avg_entry_price) * pos.quantity
    else:
        pnl = (pos.avg_entry_price - live_price) * pos.quantity

    pos.status = "CLOSED"
    pos.closed_at = now_datetime()
    pos.current_price = live_price
    pos.realized_pnl = round(pnl, 2)
    pos.unrealized_pnl = 0.0
    pos.unrealized_pnl_pct = 0.0
    pos.save(ignore_permissions=True)

    # Log closing paper ticket
    close_order = frappe.get_doc({
        "doctype": "Paper Order Ticket",
        "tenant": pos.tenant,
        "symbol": pos.symbol,
        "exchange": pos.exchange,
        "transaction_type": "SELL" if pos.direction == "LONG" else "BUY",
        "order_type": "MARKET",
        "quantity": pos.quantity,
        "price": live_price,
        "status": "EXECUTED",
        "execution_price": live_price,
        "execution_mode": "paper_only",
        "submitted_at": now_datetime(),
        "executed_at": now_datetime(),
        "notes": f"Position closing order for {pos.name}. Realized PnL: ₹{pnl:.2f}."
    })
    close_order.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "position": pos.as_dict(),
        "close_order": close_order.as_dict(),
        "realized_pnl": round(pnl, 2)
    }

