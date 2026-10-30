# -*- coding: utf-8 -*-
"""Stock Market Client KYC & Consent Compliance APIs (v1)

Implements TRK-061 - TRK-065:
- Client Profile management & KYC lifecycle
- Immutable cryptographic consent audit logs
- Affirmative paper-only disclaimer verification
- Mandate pre-activation compliance checks
"""

import hashlib
import json
import frappe
from frappe import _
from frappe.utils import now_datetime, getdate, add_years, nowdate


PAPER_MODE_DISCLAIMER_TEXT = (
    "I explicitly acknowledge and agree that this platform is operating strictly in "
    "RESEARCH & PAPER TRADING mode. Live order submission to exchange matching engines "
    "is disabled. No real financial obligations or market executions will take place. "
    "All simulations, PnL, and executions are synthetic."
)


def compute_text_hash(text: str) -> str:
    """Generate SHA-256 hash of consent terms."""
    return hashlib.sha256((text or "").strip().encode("utf-8")).hexdigest()


@frappe.whitelist(allow_guest=True)
def get_clients(tenant=None):
    """Retrieve list of client profiles."""
    filters = {}
    if tenant:
        filters["tenant"] = tenant

    clients = frappe.get_all(
        "Client Profile",
        fields=[
            "name",
            "tenant",
            "client_code",
            "client_name",
            "email",
            "phone",
            "pan_masked",
            "kyc_status",
            "kyc_verified_at",
            "risk_profile",
            "investment_objective",
            "is_accredited_investor",
            "annual_income_slab",
            "status",
            "notes",
            "creation"
        ],
        filters=filters,
        order_by="creation desc"
    )
    return clients


@frappe.whitelist(allow_guest=True)
def create_client(
    tenant,
    client_code,
    client_name,
    email,
    phone=None,
    pan_masked=None,
    risk_profile="Moderate",
    investment_objective="Capital Growth",
    annual_income_slab="10L - 25L",
    is_accredited_investor=0,
    notes=""
):
    """Register a new client profile under a tenant."""
    if not tenant:
        frappe.throw(_("Tenant is required."))
    if not client_code:
        frappe.throw(_("Client code is required."))
    if not client_name:
        frappe.throw(_("Client name is required."))
    if not email:
        frappe.throw(_("Email address is required."))

    doc = frappe.get_doc({
        "doctype": "Client Profile",
        "tenant": tenant,
        "client_code": client_code.upper().strip(),
        "client_name": client_name.strip(),
        "email": email.strip().lower(),
        "phone": (phone or "").strip(),
        "pan_masked": (pan_masked or "").strip().upper(),
        "kyc_status": "Pending",
        "risk_profile": risk_profile,
        "investment_objective": investment_objective,
        "annual_income_slab": annual_income_slab,
        "is_accredited_investor": int(is_accredited_investor),
        "status": "Active",
        "notes": notes
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()


@frappe.whitelist(allow_guest=True)
def update_client_kyc(client_name, kyc_status, pan_masked=None):
    """Update KYC verification status for a client."""
    if not client_name or not frappe.db.exists("Client Profile", client_name):
        frappe.throw(_(f"Client '{client_name}' not found."))

    doc = frappe.get_doc("Client Profile", client_name)
    doc.kyc_status = kyc_status
    if pan_masked:
        doc.pan_masked = pan_masked.strip().upper()
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()


@frappe.whitelist(allow_guest=True)
def get_consent_records(tenant=None, client=None):
    """Retrieve consent audit records."""
    filters = {}
    if tenant:
        filters["tenant"] = tenant
    if client:
        filters["client"] = client

    records = frappe.get_all(
        "Client Consent Record",
        fields=[
            "name",
            "tenant",
            "client",
            "mandate",
            "consent_type",
            "status",
            "acknowledged_paper_only",
            "signed_at",
            "valid_until",
            "consent_text_hash",
            "ip_address",
            "user_agent",
            "revoked_at",
            "revocation_reason",
            "creation"
        ],
        filters=filters,
        order_by="signed_at desc"
    )
    return records


@frappe.whitelist(allow_guest=True)
def submit_consent(
    tenant,
    client,
    consent_type="Paper Mode Disclaimer",
    acknowledged_paper_only=1,
    mandate=None,
    consent_text=None
):
    """Submit affirmative client consent with audit trail."""
    if not tenant:
        frappe.throw(_("Tenant is required."))
    if not client:
        frappe.throw(_("Client profile identifier is required."))
    if not int(acknowledged_paper_only):
        frappe.throw(_("Affirmative acknowledgment of Paper-Only Execution is mandatory."))

    if not frappe.db.exists("Client Profile", client):
        frappe.throw(_(f"Client profile '{client}' not found."))

    full_text = consent_text or PAPER_MODE_DISCLAIMER_TEXT
    text_hash = compute_text_hash(full_text)

    # Capture IP and User-Agent if available from request context
    ip_addr = getattr(frappe.local, "request_ip", "127.0.0.1") or "127.0.0.1"
    user_agent = getattr(getattr(frappe.local, "request", None), "user_agent", "Antigravity/Frappe Client") or "Antigravity/Frappe Client"
    if hasattr(user_agent, "string"):
        user_agent = user_agent.string

    signed_time = now_datetime()
    valid_date = add_years(getdate(nowdate()), 1)

    record = frappe.get_doc({
        "doctype": "Client Consent Record",
        "tenant": tenant,
        "client": client,
        "mandate": mandate or None,
        "consent_type": consent_type,
        "status": "Valid",
        "acknowledged_paper_only": 1,
        "signed_at": signed_time,
        "valid_until": valid_date,
        "consent_text_hash": text_hash,
        "ip_address": ip_addr,
        "user_agent": str(user_agent)[:140]
    })
    record.insert(ignore_permissions=True)
    frappe.db.commit()

    return record.as_dict()


@frappe.whitelist(allow_guest=True)
def get_client_compliance_status(tenant, client):
    """Return full compliance overview for a client."""
    if not client or not frappe.db.exists("Client Profile", client):
        frappe.throw(_(f"Client '{client}' does not exist."))

    c_doc = frappe.get_doc("Client Profile", client)
    today = getdate(nowdate())

    active_consents = frappe.get_all(
        "Client Consent Record",
        filters={
            "tenant": tenant,
            "client": client,
            "status": "Valid",
            "acknowledged_paper_only": 1,
            "valid_until": [">=", today]
        },
        fields=["name", "consent_type", "signed_at", "valid_until", "consent_text_hash"]
    )

    has_paper_disclaimer = any(c.consent_type == "Paper Mode Disclaimer" for c in active_consents)
    has_mandate_agreement = any(c.consent_type == "Mandate Agreement" for c in active_consents)

    is_compliant = (c_doc.kyc_status == "Verified") and has_paper_disclaimer

    return {
        "client": c_doc.as_dict(),
        "is_compliant": is_compliant,
        "kyc_verified": c_doc.kyc_status == "Verified",
        "has_paper_disclaimer": has_paper_disclaimer,
        "has_mandate_agreement": has_mandate_agreement,
        "active_consent_count": len(active_consents),
        "consents": active_consents
    }

