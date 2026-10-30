# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document


class BrokerConnection(Document):
    def validate(self):
        # Safety invariant: live execution forbidden without explicit authority
        if self.is_live_enabled:
            frappe.throw(
                "Live execution cannot be enabled without separate explicit written authorisation. "
                "Set is_live_enabled=0 to save."
            )

