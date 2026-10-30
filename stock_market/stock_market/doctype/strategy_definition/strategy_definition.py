# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document


class StrategyDefinition(Document):
    def validate(self):
        if self.execution_mode not in ("paper_only", "shadow_only", "live_disabled"):
            frappe.throw("execution_mode must be paper_only, shadow_only, or live_disabled.")
        if self.stop_loss_pct and self.stop_loss_pct > 30:
            frappe.throw("Stop Loss % cannot exceed 30%. Adjust risk parameters.")
        if self.max_open_positions and self.max_open_positions > 50:
            frappe.throw("Max Open Positions cannot exceed 50.")

