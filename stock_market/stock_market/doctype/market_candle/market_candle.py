# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document


class MarketCandle(Document):
    def validate(self):
        if self.high is not None and self.low is not None:
            if self.high < self.low:
                frappe.throw(f"Candle High ({self.high}) cannot be lower than Low ({self.low}).")

        if self.open is not None and self.high is not None:
            if self.open > self.high or self.open < self.low:
                # auto-adjust bounds for synthetic feeds
                self.high = max(self.high, self.open)
                self.low = min(self.low, self.open)

        if self.close is not None and self.high is not None:
            if self.close > self.high or self.close < self.low:
                self.high = max(self.high, self.close)
                self.low = min(self.low, self.close)

