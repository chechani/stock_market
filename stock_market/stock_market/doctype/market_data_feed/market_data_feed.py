# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class MarketDataFeed(Document):
    def validate(self):
        # Invariant: Live broker feeds strictly disallowed without explicit gated authority
        if not self.is_paper_only:
            frappe.throw("Live feed connection cannot be enabled. Must remain paper_only simulation.")

        if not self.last_heartbeat_at:
            self.last_heartbeat_at = now_datetime()

