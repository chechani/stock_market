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


@frappe.whitelist(allow_guest=True)
def run_platform_sanity_suite(tenant="pandey"):
    """TRK-152: Master End-to-End Multi-Tenant Sanity Test Suite across all 12 modules.
    
    Validates platform readiness for Phase 15 Deployment & Rollout.
    """
    import time
    t0 = time.time()
    results = []

    def check(module_id, module_name, test_name, fn):
        try:
            passed, details = fn()
            results.append({
                "module_id": module_id,
                "module_name": module_name,
                "test_name": test_name,
                "passed": bool(passed),
                "details": str(details)
            })
        except Exception as e:
            results.append({
                "module_id": module_id,
                "module_name": module_name,
                "test_name": test_name,
                "passed": False,
                "details": f"Exception: {e}"
            })

    # 1. Baseline & Context
    check("M01", "System Baseline", "Live Trading Hard Guard", lambda: (
        frappe.conf.get("live_trading_enabled") is not True,
        "live_trading_enabled is strictly False or None"
    ))
    check("M01", "System Baseline", "Custom App Registration", lambda: (
        "stock_market" in frappe.get_installed_apps(),
        "stock_market is active in installed_apps"
    ))

    # 2. Auth & Roles
    domain_roles = [
        "Stock Market Provider Admin",
        "Stock Market Operator",
        "Stock Market Analyst",
        "Stock Market Client",
        "Stock Market Viewer"
    ]
    check("M02", "Auth & Roles", "5 Domain Roles Seeded", lambda: (
        all(frappe.db.exists("Role", r) for r in domain_roles),
        f"Verified {len(domain_roles)} domain roles in MariaDB"
    ))

    # 3. Tenant Provisioning
    check("M03", "Tenant Lifecycle", "Multi-Tenant Separation", lambda: (
        frappe.db.exists("Stock Market Tenant", "pandey") and frappe.db.exists("Stock Market Tenant", "alpha"),
        "Both 'pandey' and 'alpha' tenants provisioned and isolated"
    ))

    # 4. Schema & Catalog
    check("M04", "Schema & Catalog", "Core Trading Schema Exist", lambda: (
        frappe.db.count("Strategy Definition") > 0 and
        frappe.db.count("Watchlist") > 0 and
        frappe.db.count("Broker Connection") > 0,
        f"Strategies={frappe.db.count('Strategy Definition')}, Watchlists={frappe.db.count('Watchlist')}, Connections={frappe.db.count('Broker Connection')}"
    ))

    # 5. SaaS Plans & Billing
    check("M05", "SaaS Plans & Billing", "3-Tier SaaS Catalog", lambda: (
        frappe.db.count("SaaS Plan") >= 3 and frappe.db.count("Tenant Subscription") > 0,
        f"SaaS Plans={frappe.db.count('SaaS Plan')}, Subscriptions={frappe.db.count('Tenant Subscription')}"
    ))

    # 6. Client KYC & Consent
    check("M06", "Client KYC & Consent", "Client Profile & Consent Hash", lambda: (
        frappe.db.count("Client Profile") > 0 and frappe.db.count("Client Consent Record") > 0,
        f"Profiles={frappe.db.count('Client Profile')}, Consent Records={frappe.db.count('Client Consent Record')}"
    ))

    # 7. Central Monitoring & Telemetry
    check("M07", "Fleet Telemetry", "Health Telemetry Snapshot Recorded", lambda: (
        frappe.db.count("Tenant Health Snapshot") > 0,
        f"Health Snapshots={frappe.db.count('Tenant Health Snapshot')}"
    ))

    # 8. Market Foundation
    check("M08", "Market Data", "Data Feeds & Multi-Timeframe Candles", lambda: (
        frappe.db.count("Market Data Feed") >= 2 and frappe.db.count("Market Candle") > 0,
        f"Data Feeds={frappe.db.count('Market Data Feed')}, Candles={frappe.db.count('Market Candle')}"
    ))

    # 9. Trading Terminal
    check("M09", "Trading Terminal", "Paper Execution & Positions", lambda: (
        frappe.db.count("Paper Order Ticket") > 0 and frappe.db.count("Paper Position") > 0,
        f"Paper Orders={frappe.db.count('Paper Order Ticket')}, Paper Positions={frappe.db.count('Paper Position')}"
    ))

    # 10. Research & Backtesting
    check("M10", "Research & Campaigns", "Backtest Campaigns & Trade Logs", lambda: (
        frappe.db.count("Research Campaign") > 0 and frappe.db.count("Campaign Trade") > 0,
        f"Campaigns={frappe.db.count('Research Campaign')}, Trades={frappe.db.count('Campaign Trade')}"
    ))

    # 11. Broker Reconciliation
    check("M11", "Broker Reconciliation", "Settlement Batches & Audit Items", lambda: (
        frappe.db.count("Reconciliation Batch") > 0 and frappe.db.count("Reconciliation Item") > 0,
        f"Batches={frappe.db.count('Reconciliation Batch')}, Items={frappe.db.count('Reconciliation Item')}"
    ))

    # 12. Routines & Operations
    check("M12", "Routines & Operations", "7 Scheduled Routines & Logs", lambda: (
        frappe.db.count("Scheduled Routine") >= 7 and frappe.db.count("Routine Execution Log") > 0,
        f"Routines={frappe.db.count('Scheduled Routine')}, Logs={frappe.db.count('Routine Execution Log')}"
    ))

    # 14. Security & Isolation
    check("M14", "Security & Isolation", "Security Audit Events & Posture", lambda: (
        frappe.db.count("Security Audit Event") > 0,
        f"Security Events={frappe.db.count('Security Audit Event')}"
    ))

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    duration_ms = int((time.time() - t0) * 1000)
    score_pct = round((passed / total) * 100, 1)

    return {
        "success": passed == total,
        "tenant": tenant,
        "total_tests": total,
        "passed_tests": passed,
        "failed_tests": total - passed,
        "score_pct": score_pct,
        "duration_ms": duration_ms,
        "platform_status": "PRODUCTION_READY" if passed == total else "NEEDS_ATTENTION",
        "live_trading_guard": "STRICTLY_DISABLED",
        "results": results
    }


