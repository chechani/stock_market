# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class PaperOrderTicket(Document):
    def validate(self):
        # TRK-095: Hard safety guard preventing live broker routing
        if self.execution_mode not in ("paper_only", "shadow_only", "live_disabled"):
            frappe.throw(
                "Execution safety violation: Live trading is strictly disabled. "
                "Order cannot be routed to exchange matching engine."
            )

        if not self.submitted_at:
            self.submitted_at = now_datetime()

        if self.quantity <= 0:
            frappe.throw("Order quantity must be greater than zero.")

