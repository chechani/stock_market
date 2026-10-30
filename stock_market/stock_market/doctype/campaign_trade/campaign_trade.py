# -*- coding: utf-8 -*-
# Copyright (c) 2026, Antigravity and contributors

import frappe
from frappe.model.document import Document

class CampaignTrade(Document):
	def validate(self):
		if self.entry_price and self.exit_price and self.quantity:
			if self.direction == "BUY":
				self.pnl_inr = (self.exit_price - self.entry_price) * self.quantity
				self.return_pct = round(((self.exit_price - self.entry_price) / self.entry_price) * 100, 2)
			else:
				self.pnl_inr = (self.entry_price - self.exit_price) * self.quantity
				self.return_pct = round(((self.entry_price - self.exit_price) / self.entry_price) * 100, 2)

