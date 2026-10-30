import frappe
from frappe.model.document import Document

class ResearchCampaign(Document):
	def validate(self):
		if not self.execution_mode:
			self.execution_mode = "paper_only"
		if self.execution_mode != "paper_only":
			frappe.throw("Live execution is strictly disabled. Execution mode must be 'paper_only'.")

