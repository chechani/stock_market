# -*- coding: utf-8 -*-
import json
import frappe
from frappe.model.document import Document


class SaaSPlan(Document):
    def validate(self):
        if self.price_inr is not None and self.price_inr < 0:
            frappe.throw("Plan price cannot be negative.")

        if self.features_json:
            try:
                parsed = json.loads(self.features_json)
                if not isinstance(parsed, list):
                    frappe.throw("features_json must be a valid JSON array of feature strings.")
            except json.JSONDecodeError:
                frappe.throw("features_json contains invalid JSON syntax.")

        if self.limits_json:
            try:
                parsed = json.loads(self.limits_json)
                if not isinstance(parsed, dict):
                    frappe.throw("limits_json must be a valid JSON object of limits.")
            except json.JSONDecodeError:
                frappe.throw("limits_json contains invalid JSON syntax.")

