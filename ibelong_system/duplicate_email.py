import frappe
from frappe.utils import getdate, get_time

@frappe.whitelist(allow_guest=True)
def check_email(email):
    exists = frappe.db.exists("Client Details", {"email": email.lower()})
    return {"exists": bool(exists)}