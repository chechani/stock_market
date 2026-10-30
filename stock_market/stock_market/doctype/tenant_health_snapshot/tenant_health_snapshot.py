# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class TenantHealthSnapshot(Document):
    def validate(self):
        if not self.captured_at:
            self.captured_at = now_datetime()
        if self.latency_ms is not None and self.latency_ms < 0:
            frappe.throw("Latency cannot be negative.")

