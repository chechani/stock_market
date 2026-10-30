# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class TenantSubscription(Document):
    def validate(self):
        if self.billing_start and self.billing_end:
            if getdate(self.billing_end) < getdate(self.billing_start):
                frappe.throw("Billing end date cannot be earlier than billing start date.")

        if self.price_paid_inr is not None and self.price_paid_inr < 0:
            frappe.throw("Price paid cannot be negative.")

