# -*- coding: utf-8 -*-
import re
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class ClientProfile(Document):
    def validate(self):
        # Email format check
        if self.email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", self.email):
            frappe.throw(f"Invalid email address: {self.email}")

        # Client code formatting
        if self.client_code:
            self.client_code = re.sub(r"[^A-Za-z0-9_-]", "", self.client_code).upper()

        # Update verification timestamp if KYC is verified
        if self.kyc_status == "Verified" and not self.kyc_verified_at:
            self.kyc_verified_at = now_datetime()
        elif self.kyc_status != "Verified":
            self.kyc_verified_at = None

