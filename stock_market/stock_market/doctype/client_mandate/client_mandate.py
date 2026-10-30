# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document
from frappe.utils import getdate, nowdate


class ClientMandate(Document):
    def validate(self):
        # Enforce live trading policy
        if self.execution_mode not in ("paper_only", "shadow_only", "live_disabled"):
            frappe.throw("Invalid execution_mode. Must be paper_only, shadow_only, or live_disabled.")
        
        # Managed Execution type requires operator review
        if self.mandate_type == "Managed Execution (Gated)" and not self.reviewed_by:
            frappe.throw(
                "Managed Execution mandates require explicit operator review before activation."
            )

        # TRK-065: Validation hook preventing mandate activation if client consent is missing or expired
        if self.status == "Active":
            today = getdate(nowdate())
            # Find an active, valid consent record linked to this mandate or tenant/client
            has_consent = frappe.db.sql("""
                SELECT name FROM `tabClient Consent Record`
                WHERE tenant = %(tenant)s
                  AND status = 'Valid'
                  AND acknowledged_paper_only = 1
                  AND valid_until >= %(today)s
                LIMIT 1
            """, {"tenant": self.tenant, "today": today})

            if not has_consent:
                frappe.throw(
                    f"Mandate '{self.name or 'New'}' cannot be marked 'Active' without a valid, "
                    f"unexpired Client Consent Record acknowledging Paper-Only execution."
                )
