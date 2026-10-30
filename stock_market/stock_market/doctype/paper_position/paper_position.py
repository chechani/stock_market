# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class PaperPosition(Document):
    def validate(self):
        if not self.opened_at:
            self.opened_at = now_datetime()

        # Recalculate unrealized PnL based on direction
        if self.avg_entry_price and self.current_price and self.quantity:
            if self.direction == "LONG":
                self.unrealized_pnl = round((self.current_price - self.avg_entry_price) * self.quantity, 2)
                self.unrealized_pnl_pct = round(((self.current_price - self.avg_entry_price) / self.avg_entry_price) * 100, 2)
            else:
                self.unrealized_pnl = round((self.avg_entry_price - self.current_price) * self.quantity, 2)
                self.unrealized_pnl_pct = round(((self.avg_entry_price - self.current_price) / self.avg_entry_price) * 100, 2)

