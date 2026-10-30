# -*- coding: utf-8 -*-
"""Stock Market Authentication, Session Management & Role APIs (v1)

Provides secure login, session verification, current user metadata,
CSRF token extraction, and custom domain roles.
"""

import frappe
from frappe import _
from frappe.auth import LoginManager
from stock_market.api.v1.system import get_site_mode

STOCK_MARKET_ROLES = [
    {"role_name": "Stock Market Provider Admin", "desk_access": 1},
    {"role_name": "Stock Market Operator", "desk_access": 1},
    {"role_name": "Stock Market Analyst", "desk_access": 1},
    {"role_name": "Stock Market Client", "desk_access": 0},
    {"role_name": "Stock Market Viewer", "desk_access": 0},
]


@frappe.whitelist(allow_guest=True)
def get_current_user():
    """Returns the authenticated user's profile, roles, and CSRF token for the session."""
    user = frappe.session.user if hasattr(frappe, "session") else "Guest"
    is_authenticated = user != "Guest"
    
    full_name = frappe.utils.get_fullname(user) if is_authenticated else "Guest User"
    roles = frappe.get_roles(user) if is_authenticated else ["Guest"]
    
    # Extract CSRF token if session exists
    csrf_token = None
    if hasattr(frappe, "sessions") and hasattr(frappe.sessions, "get_csrf_token"):
        try:
            csrf_token = frappe.sessions.get_csrf_token()
        except Exception:
            csrf_token = None

    return {
        "user": user,
        "full_name": full_name,
        "is_authenticated": is_authenticated,
        "roles": roles,
        "site": getattr(frappe.local, "site", ""),
        "site_mode": get_site_mode(),
        "csrf_token": csrf_token,
    }


@frappe.whitelist(allow_guest=True)
def login(usr=None, pwd=None):
    """Securely authenticates user credentials and initiates a Frappe session.
    
    Sets the standard Frappe HTTP-only sid cookie in the response.
    """
    if not usr or not pwd:
        # Check if JSON payload was passed
        data = frappe.request.get_json() if hasattr(frappe.request, "get_json") else None
        if data and isinstance(data, dict):
            usr = usr or data.get("usr")
            pwd = pwd or data.get("pwd")

    if not usr or not pwd:
        frappe.throw(_("Username and password are required."), frappe.AuthenticationError)

    login_manager = LoginManager()
    login_manager.authenticate(user=usr, pwd=pwd)
    login_manager.post_login()

    user = frappe.session.user
    return {
        "message": "Logged In",
        "user": user,
        "full_name": frappe.utils.get_fullname(user),
        "roles": frappe.get_roles(user),
        "site": getattr(frappe.local, "site", ""),
        "site_mode": get_site_mode(),
    }


@frappe.whitelist(allow_guest=False)
def logout():
    """Logs out the current session and clears cookies."""
    if hasattr(frappe.local, "login_manager"):
        frappe.local.login_manager.logout()
    return {"message": "Logged Out"}


@frappe.whitelist()
def ensure_custom_roles():
    """Ensures domain roles for Stock Market SaaS exist in the database."""
    created = []
    for r in STOCK_MARKET_ROLES:
        if not frappe.db.exists("Role", r["role_name"]):
            role_doc = frappe.get_doc({
                "doctype": "Role",
                "role_name": r["role_name"],
                "desk_access": r["desk_access"],
            })
            role_doc.insert(ignore_permissions=True)
            created.append(r["role_name"])
    
    frappe.db.commit()
    return {"status": "ok", "created_roles": created}

