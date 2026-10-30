# -*- coding: utf-8 -*-
"""Stock Market System & Context APIs (v1)

Provides system health, tenancy context, installed app metadata,
and enforces safety policies (e.g. live trading disabled).
"""

import frappe
from frappe import _
from frappe.utils import now_datetime


def get_site_mode() -> str:
    """Determine site mode ('control' or 'tenant') from site_config.json or site name."""
    conf = frappe.conf or {}
    site_mode = conf.get("site_mode")
    if site_mode in ("control", "tenant"):
        return site_mode
    # Convention fallback
    site_name = getattr(frappe.local, "site", "") or ""
    if "control" in site_name.lower():
        return "control"
    return "tenant"


@frappe.whitelist(allow_guest=True)
def ping():
    """Simple ping endpoint to verify Frappe + stock_market API connectivity."""
    return {
        "status": "ok",
        "message": "pong",
        "app": "stock_market",
        "timestamp": now_datetime().isoformat(),
    }


@frappe.whitelist(allow_guest=True)
def get_system_context():
    """Returns the verified runtime context for the current tenant or control site.
    
    Includes site mode, versions, installed apps, database state,
    and enforces that live trading is explicitly disabled.
    """
    import stock_market

    site_name = getattr(frappe.local, "site", "unknown")
    site_mode = get_site_mode()
    installed_apps = frappe.get_installed_apps() if hasattr(frappe, "get_installed_apps") else []

    # Check database connectivity
    db_connected = False
    try:
        frappe.db.sql("SELECT 1")
        db_connected = True
    except Exception:
        db_connected = False

    return {
        "site": site_name,
        "site_mode": site_mode,
        "app_name": "stock_market",
        "app_version": getattr(stock_market, "__version__", "0.0.1"),
        "frappe_version": getattr(frappe, "__version__", "unknown"),
        "installed_apps": installed_apps,
        "database_connected": db_connected,
        "live_trading_enabled": False,  # Hard invariant: disabled absent separate explicit clearance
        "execution_mode": "paper_only",
        "timestamp": now_datetime().isoformat(),
        "user": frappe.session.user if hasattr(frappe, "session") else "Guest",
    }


@frappe.whitelist(allow_guest=True)
def get_reference_market_overview():
    """Returns baseline reference market indicators for Phase 01 demo.
    
    Note: Labelled clearly as reference/paper data until Phase 08 feed integration.
    """
    return {
        "source": "reference_paper_feed",
        "status": "active",
        "indices": [
            {
                "symbol": "NIFTY 50",
                "exchange": "NSE",
                "last_price": 24340.60,
                "change": 85.20,
                "change_percent": 0.35,
                "status": "open",
            },
            {
                "symbol": "NIFTY BANK",
                "exchange": "NSE",
                "last_price": 51980.15,
                "change": -110.40,
                "change_percent": -0.21,
                "status": "open",
            },
            {
                "symbol": "SENSEX",
                "exchange": "BSE",
                "last_price": 79942.10,
                "change": 235.80,
                "change_percent": 0.30,
                "status": "open",
            },
            {
                "symbol": "INDIA VIX",
                "exchange": "NSE",
                "last_price": 14.25,
                "change": -0.45,
                "change_percent": -3.06,
                "status": "open",
            },
        ],
        "timestamp": now_datetime().isoformat(),
    }

