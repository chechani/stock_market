# -*- coding: utf-8 -*-
"""Stock Market SaaS Plans & Subscription APIs (v1)

Implements TRK-051 - TRK-055:
- SaaS Plan catalog (Starter, Pro, Enterprise)
- Tenant subscription management & lifecycle
- ERPNext-compatible sales invoice referencing without modifying ERPNext core
- Quota limits & feature entitlement resolution
"""

import json
import frappe
from frappe import _
from frappe.utils import now_datetime, getdate, add_days, add_months, add_years, random_string


DEFAULT_PLANS = [
    {
        "plan_code": "STARTER",
        "plan_name": "Starter Paper",
        "tier": "Starter",
        "price_inr": 0,
        "billing_interval": "Monthly",
        "is_active": 1,
        "max_strategies": 2,
        "max_watchlists": 2,
        "max_broker_connections": 1,
        "max_mandates": 2,
        "description": "Ideal for students and individual traders practicing systematic trading in paper mode.",
        "features_json": json.dumps([
            "Paper Trading Simulation",
            "EOD Market Data",
            "Up to 2 Watchlists (10 symbols each)",
            "Standard Daily Timeframe",
            "Single Broker Sandbox"
        ]),
        "limits_json": json.dumps({
            "daily_api_calls": 500,
            "backtest_lookback_days": 90,
            "allow_custom_indicators": False
        })
    },
    {
        "plan_code": "PRO",
        "plan_name": "Pro Research",
        "tier": "Pro",
        "price_inr": 4999,
        "billing_interval": "Monthly",
        "is_active": 1,
        "max_strategies": 10,
        "max_watchlists": 10,
        "max_broker_connections": 3,
        "max_mandates": 10,
        "description": "For quantitative analysts and serious traders seeking multi-timeframe research tools.",
        "features_json": json.dumps([
            "Advanced Paper & Research Engine",
            "Real-time Paper Feeds (XTS / RMoney Mock)",
            "Intraday, Daily & Weekly Timeframes",
            "GAR Weekly Long Strategy Suite",
            "Up to 3 Broker Sandboxes",
            "Audit Trail & CSV Export"
        ]),
        "limits_json": json.dumps({
            "daily_api_calls": 5000,
            "backtest_lookback_days": 730,
            "allow_custom_indicators": True
        })
    },
    {
        "plan_code": "ENTERPRISE",
        "plan_name": "Enterprise Multi-Strategy",
        "tier": "Enterprise",
        "price_inr": 14999,
        "billing_interval": "Monthly",
        "is_active": 1,
        "max_strategies": 50,
        "max_watchlists": 50,
        "max_broker_connections": 10,
        "max_mandates": 50,
        "description": "Full-stack multi-tenant platform for wealth managers, advisory firms, and prop desks.",
        "features_json": json.dumps([
            "All Pro Research Features",
            "Dedicated Isolated Tenant Database",
            "High-Frequency Candle Builder",
            "Custom Client Mandates & Risk Profiles",
            "Automated Paper Rebalancing",
            "Priority SLA & Dedicated Audit Run Persist"
        ]),
        "limits_json": json.dumps({
            "daily_api_calls": 50000,
            "backtest_lookback_days": 3650,
            "allow_custom_indicators": True
        })
    }
]


def ensure_default_plans_exist():
    """Seed the default SaaS plans if database is empty."""
    for plan_data in DEFAULT_PLANS:
        if not frappe.db.exists("SaaS Plan", plan_data["plan_code"]):
            doc = frappe.get_doc({
                "doctype": "SaaS Plan",
                **plan_data
            })
            doc.insert(ignore_permissions=True)
    frappe.db.commit()


@frappe.whitelist(allow_guest=True)
def get_plans():
    """Retrieve all available SaaS plans."""
    ensure_default_plans_exist()
    plans = frappe.get_all(
        "SaaS Plan",
        fields=[
            "name",
            "plan_code",
            "plan_name",
            "tier",
            "price_inr",
            "billing_interval",
            "is_active",
            "max_strategies",
            "max_watchlists",
            "max_broker_connections",
            "max_mandates",
            "description",
            "features_json",
            "limits_json",
            "creation"
        ],
        filters={"is_active": 1},
        order_by="price_inr asc"
    )
    for p in plans:
        try:
            p["features"] = json.loads(p.get("features_json") or "[]")
        except Exception:
            p["features"] = []
        try:
            p["limits"] = json.loads(p.get("limits_json") or "{}")
        except Exception:
            p["limits"] = {}
    return plans


@frappe.whitelist(allow_guest=True)
def get_subscriptions(tenant=None):
    """List subscriptions, optionally filtered by tenant."""
    filters = {}
    if tenant:
        filters["tenant"] = tenant

    subs = frappe.get_all(
        "Tenant Subscription",
        fields=[
            "name",
            "tenant",
            "plan",
            "status",
            "billing_start",
            "billing_end",
            "price_paid_inr",
            "auto_renew",
            "invoice_reference",
            "erpnext_invoice_id",
            "notes",
            "creation"
        ],
        filters=filters,
        order_by="creation desc"
    )

    # Attach plan name
    for s in subs:
        plan_doc = frappe.db.get_value("SaaS Plan", s.get("plan"), ["plan_name", "tier", "price_inr"], as_dict=True)
        if plan_doc:
            s["plan_name"] = plan_doc.plan_name
            s["tier"] = plan_doc.tier
            s["catalog_price"] = plan_doc.price_inr

    return subs


@frappe.whitelist(allow_guest=True)
def create_subscription(tenant, plan_code, billing_interval="Monthly", auto_renew=1, notes=""):
    """Create or renew a tenant subscription."""
    if not tenant:
        frappe.throw(_("Tenant is required."))
    if not plan_code:
        frappe.throw(_("Plan code is required."))

    ensure_default_plans_exist()

    if not frappe.db.exists("SaaS Plan", plan_code):
        frappe.throw(_(f"Plan '{plan_code}' does not exist."))

    plan = frappe.get_doc("SaaS Plan", plan_code)
    start_date = getdate()
    if billing_interval == "Yearly":
        end_date = add_years(start_date, 1)
        price = plan.price_inr * 10  # 2 months free discount
    else:
        end_date = add_months(start_date, 1)
        price = plan.price_inr

    # Mock / standard invoice reference (ERPNext-compatible without modifying core)
    inv_ref = f"INV-{tenant.upper()}-{start_date.strftime('%Y%m')}-{random_string(4).upper()}"

    sub = frappe.get_doc({
        "doctype": "Tenant Subscription",
        "tenant": tenant,
        "plan": plan.name,
        "status": "Active",
        "billing_start": start_date,
        "billing_end": end_date,
        "price_paid_inr": price,
        "auto_renew": int(auto_renew),
        "invoice_reference": inv_ref,
        "erpnext_invoice_id": f"ACC-SINV-{random_string(6).upper()}",
        "notes": notes or f"Provisioned via SaaS Plan API. Interval: {billing_interval}."
    })
    sub.insert(ignore_permissions=True)
    frappe.db.commit()

    # Also update Tenant record's plan field if tenant exists
    if frappe.db.exists("Stock Market Tenant", tenant):
        frappe.db.set_value("Stock Market Tenant", tenant, "plan", plan.plan_name)
        frappe.db.commit()

    return sub.as_dict()


@frappe.whitelist(allow_guest=True)
def get_tenant_entitlements(tenant):
    """Return effective plan, feature flags, quotas, and current consumption for a tenant."""
    if not tenant:
        frappe.throw(_("Tenant identifier required."))

    ensure_default_plans_exist()

    # Find active subscription
    active_sub = frappe.db.get_value(
        "Tenant Subscription",
        {"tenant": tenant, "status": "Active"},
        ["name", "plan", "billing_start", "billing_end", "invoice_reference"],
        as_dict=True
    )

    plan_code = "STARTER"
    sub_data = None
    if active_sub:
        plan_code = active_sub.plan
        sub_data = active_sub
    else:
        # Check tenant table fallback
        tenant_plan = frappe.db.get_value("Stock Market Tenant", tenant, "plan")
        if tenant_plan:
            for p in DEFAULT_PLANS:
                if p["plan_name"].lower() == tenant_plan.lower():
                    plan_code = p["plan_code"]
                    break

    plan_doc = frappe.get_doc("SaaS Plan", plan_code) if frappe.db.exists("SaaS Plan", plan_code) else None

    # Count current resource usage
    strategies_count = frappe.db.count("Strategy Definition")
    watchlists_count = frappe.db.count("Watchlist", {"tenant": tenant}) if frappe.db.has_column("Watchlist", "tenant") else 0
    broker_conns_count = frappe.db.count("Broker Connection", {"tenant": tenant}) if frappe.db.has_column("Broker Connection", "tenant") else 0
    mandates_count = frappe.db.count("Client Mandate", {"tenant": tenant}) if frappe.db.has_column("Client Mandate", "tenant") else 0

    max_strategies = plan_doc.max_strategies if plan_doc else 2
    max_watchlists = plan_doc.max_watchlists if plan_doc else 3
    max_broker_connections = plan_doc.max_broker_connections if plan_doc else 1
    max_mandates = plan_doc.max_mandates if plan_doc else 5

    return {
        "tenant": tenant,
        "subscription": sub_data,
        "plan": plan_doc.as_dict() if plan_doc else None,
        "quotas": {
            "strategies": {
                "used": strategies_count,
                "max": max_strategies,
                "remaining": max(0, max_strategies - strategies_count),
                "is_exceeded": strategies_count >= max_strategies
            },
            "watchlists": {
                "used": watchlists_count,
                "max": max_watchlists,
                "remaining": max(0, max_watchlists - watchlists_count),
                "is_exceeded": watchlists_count >= max_watchlists
            },
            "broker_connections": {
                "used": broker_conns_count,
                "max": max_broker_connections,
                "remaining": max(0, max_broker_connections - broker_conns_count),
                "is_exceeded": broker_conns_count >= max_broker_connections
            },
            "mandates": {
                "used": mandates_count,
                "max": max_mandates,
                "remaining": max(0, max_mandates - mandates_count),
                "is_exceeded": mandates_count >= max_mandates
            }
        }
    }

