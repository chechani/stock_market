# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime


class ClientConsentRecord(Document):
    def validate(self):
        # Mandatory policy check: live trading is disabled, paper execution acknowledgment required
        if not self.acknowledged_paper_only:
            frappe.throw(
                "Consent cannot be recorded without affirmative acknowledgment of the "
                "Paper-Only Execution Policy (Live trading disabled)."
            )

        # Ensure valid_until is in the future relative to signed_at
        if self.signed_at and self.valid_until:
            if getdate(self.valid_until) < getdate(self.signed_at):
                frappe.throw("Consent expiration date cannot be before signature date.")

        if self.status == "Revoked" and not self.revoked_at:
            self.revoked_at = now_datetime()

