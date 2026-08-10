import frappe
from frappe.model.document import Document
from frappe.utils import today, now_datetime


class ClientReferral(Document):
    def before_insert(self):
        self.referred_by = frappe.session.user
        self.referral_date = today()
        if not self.referral_status:
            self.referral_status = "Pending"
        self.status_changed_on = now_datetime()

    def validate(self):
        self._check_duplicate_referral()

        if self.referral_status in ("Closed", "Declined") and not self.reason_for_closure:
            frappe.throw(
                frappe._("Please provide a reason when closing or declining a referral.")
            )

        # Update timestamp whenever status changes (avoid has_value_changed which can fail on new docs)
        try:
            before = self._doc_before_save
            if before and before.get("referral_status") != self.referral_status:
                self.status_changed_on = now_datetime()
        except Exception:
            pass

    def _check_duplicate_referral(self):
        """Prevent a second active referral to the same provider for the same client."""
        existing = frappe.db.get_value(
            "Client Referral",
            {
                "client": self.client,
                "referred_to": self.referred_to,
                "referral_status": ["not in", ["Closed", "Declined"]],
                "name": ["!=", self.name or ""],
            },
            "name",
        )
        if existing:
            frappe.throw(
                frappe._(
                    "An active referral to {0} already exists for this client ({1}). "
                    "Close or decline that referral before creating a new one."
                ).format(self.referred_to, existing)
            )

    def add_note(self, note_text, source="Internal", added_by=None):
        """Append a timestamped note. Used by both the form and the external API."""
        self.append("notes", {
            "note": note_text,
            "added_by": added_by or frappe.session.user,
            "added_on": now_datetime(),
            "source": source
        })
