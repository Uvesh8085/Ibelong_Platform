import secrets
import frappe
from frappe.utils import now_datetime


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_provider(api_key):
    """Return the External Service Provider name for a valid, active API key.
    Raises AuthenticationError on failure so callers don't need to check."""
    if not api_key:
        frappe.throw("API key is required.", frappe.AuthenticationError)

    provider = frappe.db.get_value(
        "External Service Provider",
        {"api_key": api_key, "is_active": 1},
        "name"
    )
    if not provider:
        frappe.throw("Invalid or inactive API key.", frappe.AuthenticationError)

    return provider


def _assert_referral_owner(referral_doc, provider):
    """Ensure the referral belongs to the requesting provider."""
    if referral_doc.referred_to != provider:
        frappe.throw("You do not have access to this referral.", frappe.PermissionError)


# ---------------------------------------------------------------------------
# External API — callable by external systems using their API key
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def get_referrals(api_key, **kwargs):
    """Return all referrals assigned to the calling external provider.

    Response includes limited client fields only (no ID/passport numbers).

    Example call:
        GET /api/method/ibelong_system.referral_api.get_referrals?api_key=<key>
    """
    provider = _resolve_provider(api_key)

    referrals = frappe.db.get_all(
        "Client Referral",
        filters={"referred_to": provider},
        fields=[
            "name", "client", "client_name_display", "file_number",
            "referral_status", "referral_date", "referral_reason",
            "reason_for_closure", "status_changed_on", "referred_by"
        ],
        order_by="referral_date desc"
    )

    for ref in referrals:
        ref["notes"] = frappe.db.get_all(
            "Referral Note",
            filters={"parent": ref["name"], "parenttype": "Client Referral"},
            fields=["note", "added_by", "added_on", "source"],
            order_by="added_on asc"
        )

    return {"status": "success", "provider": provider, "referrals": referrals}


@frappe.whitelist(allow_guest=True)
def update_referral_status(api_key, referral_id, status, note=None, **kwargs):
    """Update the status of a referral and optionally add a note.

    Allowed statuses for external providers:
        Accepted | In Progress | Completed | Closed | Declined

    Example call (POST):
        /api/method/ibelong_system.referral_api.update_referral_status
        Body: api_key=<key>&referral_id=IBREF-0001&status=Accepted&note=We have received this referral.
    """
    provider = _resolve_provider(api_key)

    allowed = {"Accepted", "In Progress", "Completed", "Closed", "Declined"}
    if status not in allowed:
        frappe.throw(
            f"Invalid status '{status}'. Allowed values: {', '.join(sorted(allowed))}."
        )

    referral = frappe.get_doc("Client Referral", referral_id)
    _assert_referral_owner(referral, provider)

    if referral.referral_status in ("Closed", "Declined"):
        frappe.throw("This referral is already closed and cannot be updated.")

    old_status = referral.referral_status
    referral.referral_status = status
    referral.status_changed_on = now_datetime()

    if note and note.strip():
        referral.add_note(
            note_text=note.strip(),
            source="External",
            added_by=f"External: {provider}"
        )
    else:
        # Always log the status change even with no custom note
        referral.add_note(
            note_text=f"Status changed from '{old_status}' to '{status}'.",
            source="External",
            added_by=f"External: {provider}"
        )

    referral.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "referral": referral_id,
        "previous_status": old_status,
        "new_status": status
    }


@frappe.whitelist(allow_guest=True)
def add_referral_note(api_key, referral_id, note, **kwargs):
    """Add a note to a referral without changing its status.

    Example call (POST):
        /api/method/ibelong_system.referral_api.add_referral_note
        Body: api_key=<key>&referral_id=IBREF-0001&note=Client attended first session.
    """
    provider = _resolve_provider(api_key)

    if not note or not note.strip():
        frappe.throw("Note text cannot be empty.")

    referral = frappe.get_doc("Client Referral", referral_id)
    _assert_referral_owner(referral, provider)

    referral.add_note(
        note_text=note.strip(),
        source="External",
        added_by=f"External: {provider}"
    )
    referral.save(ignore_permissions=True)
    frappe.db.commit()

    return {"status": "success", "referral": referral_id}


@frappe.whitelist()
def get_client_referrals(client):
    """Return all referrals for a client. Used by the Client Details form dashboard."""
    referrals = frappe.db.get_all(
        "Client Referral",
        filters={"client": client},
        fields=["name", "referred_to", "referral_status", "referral_date", "referral_reason"],
        order_by="referral_date desc"
    )
    return referrals


# ---------------------------------------------------------------------------
# Internal API — only for logged-in iBelong staff (admin)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def generate_api_key(provider_name):
    """Generate (or rotate) the API key for an External Service Provider.

    Called from the External Service Provider form via the JS button.
    Only System Managers and HRD-Admins can call this.
    """
    if not frappe.has_permission("External Service Provider", "write", provider_name):
        frappe.throw("You do not have permission to manage API keys.", frappe.PermissionError)

    new_key = secrets.token_hex(32)  # 64-character hex string

    frappe.db.set_value(
        "External Service Provider",
        provider_name,
        "api_key",
        new_key,
        update_modified=True
    )
    frappe.db.commit()

    return {"status": "success", "api_key": new_key}
