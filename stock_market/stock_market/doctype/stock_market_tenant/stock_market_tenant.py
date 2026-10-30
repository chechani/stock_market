# -*- coding: utf-8 -*-
"""Stock Market Tenant Document Controller"""

import frappe
from frappe.model.document import Document


class StockMarketTenant(Document):
    def validate(self):
        if self.domain:
            self.domain = self.domain.strip().lower()
        if self.tenant_id:
            self.tenant_id = self.tenant_id.strip().lower()

