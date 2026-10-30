# -*- coding: utf-8 -*-
"""Stock Market Phase 04 — Schema & Core DocType APIs (v1)

Provides CRUD + listing APIs for:
  - Broker Connection  (TRK-041)
  - Watchlist & Watchlist Items (TRK-042)
  - Client Mandate (TRK-043)
  - Strategy Definition (TRK-044)
"""

import frappe
from frappe import _
from frappe.utils import now_datetime


# ────────────────────────────────────────────────────────────────────────────
# Broker Connection
# ────────────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def get_broker_connections(tenant: str = None):
    filters = {}
    if tenant:
        filters["tenant"] = tenant
    return frappe.get_all(
        "Broker Connection",
        filters=filters,
        fields=["name", "tenant", "broker_code", "broker_name", "status",
                "api_endpoint", "client_id", "is_live_enabled",
                "connected_at", "last_healthcheck_at", "healthcheck_status"],
        order_by="creation desc",
    )


@frappe.whitelist(allow_guest=True)
def create_broker_connection():
    data = frappe.request.get_json() if hasattr(frappe.request, "get_json") else {}
    if not data:
        data = frappe.form_dict

    required = ["tenant", "broker_code", "broker_name"]
    for f in required:
        if not data.get(f):
            frappe.throw(_("{0} is required.").format(f))

    # Hard safety: never allow live execution to be enabled via API
    if data.get("is_live_enabled"):
        frappe.throw(_("Live execution cannot be enabled via API. Set is_live_enabled=0."))

    doc = frappe.get_doc({
        "doctype": "Broker Connection",
        "tenant": data["tenant"],
        "broker_code": data["broker_code"],
        "broker_name": data["broker_name"],
        "status": "Inactive",
        "api_endpoint": data.get("api_endpoint", ""),
        "client_id": data.get("client_id", ""),
        "is_live_enabled": 0,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()


# ────────────────────────────────────────────────────────────────────────────
# Watchlist
# ────────────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def get_watchlists(tenant: str = None):
    filters = {}
    if tenant:
        filters["tenant"] = tenant
    return frappe.get_all(
        "Watchlist",
        filters=filters,
        fields=["name", "tenant", "watchlist_name", "description",
                "is_default", "exchange_filter", "instrument_type_filter"],
        order_by="is_default desc, creation desc",
    )


@frappe.whitelist(allow_guest=True)
def create_watchlist():
    data = frappe.request.get_json() if hasattr(frappe.request, "get_json") else {}
    if not data:
        data = frappe.form_dict

    if not data.get("tenant") or not data.get("watchlist_name"):
        frappe.throw(_("tenant and watchlist_name are required."))

    doc = frappe.get_doc({
        "doctype": "Watchlist",
        "tenant": data["tenant"],
        "watchlist_name": data["watchlist_name"],
        "description": data.get("description", ""),
        "is_default": data.get("is_default", 0),
        "exchange_filter": data.get("exchange_filter", "All"),
        "instrument_type_filter": data.get("instrument_type_filter", "All"),
        "items": [],
    })
    # Seed with provided symbols
    for item in (data.get("items") or []):
        doc.append("items", {
            "exchange": item.get("exchange", "NSE"),
            "symbol": item.get("symbol", ""),
            "instrument_type": item.get("instrument_type", "EQ"),
            "lot_size": item.get("lot_size", 1),
            "added_at": now_datetime(),
        })

    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()


@frappe.whitelist(allow_guest=True)
def get_watchlist_detail(watchlist_name: str):
    doc = frappe.get_doc("Watchlist", watchlist_name)
    return doc.as_dict()


@frappe.whitelist(allow_guest=True)
def add_watchlist_item(watchlist_name: str, exchange: str, symbol: str,
                       instrument_type: str = "EQ", lot_size: int = 1):
    doc = frappe.get_doc("Watchlist", watchlist_name)
    # Deduplicate
    for row in doc.items:
        if row.exchange == exchange and row.symbol == symbol:
            return {"status": "already_exists", "symbol": symbol}
    doc.append("items", {
        "exchange": exchange,
        "symbol": symbol.upper(),
        "instrument_type": instrument_type,
        "lot_size": lot_size,
        "added_at": now_datetime(),
    })
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "added", "symbol": symbol}


# ────────────────────────────────────────────────────────────────────────────
# Client Mandate
# ────────────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def get_mandates(tenant: str = None):
    filters = {}
    if tenant:
        filters["tenant"] = tenant
    return frappe.get_all(
        "Client Mandate",
        filters=filters,
        fields=["name", "tenant", "client_user", "mandate_type", "status",
                "risk_profile", "max_capital_inr", "execution_mode",
                "strategy", "broker_connection", "consent_given_at"],
        order_by="creation desc",
    )


@frappe.whitelist(allow_guest=True)
def create_mandate():
    data = frappe.request.get_json() if hasattr(frappe.request, "get_json") else {}
    if not data:
        data = frappe.form_dict

    required = ["tenant", "client_user", "owner_email"]
    for f in ["tenant", "client_user"]:
        if not data.get(f):
            frappe.throw(_("{0} is required.").format(f))

    doc = frappe.get_doc({
        "doctype": "Client Mandate",
        "tenant": data["tenant"],
        "client_user": data["client_user"],
        "mandate_type": data.get("mandate_type", "Research Only"),
        "status": "Draft",
        "risk_profile": data.get("risk_profile", "Conservative"),
        "max_capital_inr": data.get("max_capital_inr", 0),
        "max_single_trade_inr": data.get("max_single_trade_inr", 0),
        "execution_mode": "paper_only",   # always starts paper; live blocked
        "strategy": data.get("strategy"),
        "broker_connection": data.get("broker_connection"),
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()


# ────────────────────────────────────────────────────────────────────────────
# Strategy Definition
# ────────────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def get_strategies():
    return frappe.get_all(
        "Strategy Definition",
        fields=["name", "strategy_code", "strategy_name", "status",
                "direction", "universe", "timeframe", "execution_mode",
                "max_open_positions", "stop_loss_pct", "trailing_stop_pct",
                "last_backtest_at", "last_backtest_result"],
        order_by="creation desc",
    )


@frappe.whitelist(allow_guest=True)
def create_strategy():
    data = frappe.request.get_json() if hasattr(frappe.request, "get_json") else {}
    if not data:
        data = frappe.form_dict

    if not data.get("strategy_code") or not data.get("strategy_name"):
        frappe.throw(_("strategy_code and strategy_name are required."))

    doc = frappe.get_doc({
        "doctype": "Strategy Definition",
        "strategy_code": data["strategy_code"].upper().replace(" ", "_"),
        "strategy_name": data["strategy_name"],
        "status": "Draft",
        "direction": data.get("direction", "Long Only"),
        "universe": data.get("universe", "NIFTY 50"),
        "timeframe": data.get("timeframe", "Daily"),
        "execution_mode": "paper_only",
        "description": data.get("description", ""),
        "parameters_json": data.get("parameters_json", "{}"),
        "max_open_positions": data.get("max_open_positions", 5),
        "stop_loss_pct": data.get("stop_loss_pct", 5.0),
        "trailing_stop_pct": data.get("trailing_stop_pct", 0),
        "created_by_user": frappe.session.user,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()


@frappe.whitelist(allow_guest=True)
def get_schema_overview():
    """Returns a summary count of all Phase 04 DocType records for the dashboard."""
    def safe_count(dt, filters=None):
        try:
            return frappe.db.count(dt, filters or {})
        except Exception:
            return 0

    return {
        "broker_connections": safe_count("Broker Connection"),
        "watchlists":         safe_count("Watchlist"),
        "mandates":           safe_count("Client Mandate"),
        "strategies":         safe_count("Strategy Definition"),
        "tenants":            safe_count("Stock Market Tenant"),
        "timestamp":          now_datetime().isoformat(),
    }

