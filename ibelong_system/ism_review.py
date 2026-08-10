"""
NISC enhancement (30/07/2026 doc) - ISM meeting review + OTP confirmation.

Lifecycle of a single ISM Booking row (see ism_v2_booking_fields.py):
    ISM Scheduled
        -> ISM Cancelled                                  (client/staff cancels)
        -> Pending Client Review   [submit_for_client_review, staff-only]
               -> Case Open        [confirm_ism_review, client OTP]
               -> Case Referred    [confirm_ism_review, client OTP, provider set]
                      -> Case Closed  [close_ism_case, staff-only]

The OTP itself is never written to the database - it lives in the Redis cache
for a short window, the same pattern already used for mobile-login OTPs in
otp_verify.py, so a client's session (or anyone with desk access) can never
read it back out.
"""

import random
from datetime import datetime

import frappe
from frappe import _

OTP_CACHE_PREFIX = "ism_review_otp:"
OTP_TTL_SECONDS = 30 * 60  # 30 minutes

STAFF_ROLES = ("System Manager", "NISC User")

SUPPORT_FIELDS = [
    "employment_assistance", "educational_support", "documentation_assistance",
    "family_support", "accommodation_support", "health_services",
    "wellbeing_mental_health_support", "social_integration_activities", "other_support",
]
VULNERABILITY_FIELDS = [
    "pregnant_women", "single_parents_with_minor_children", "victims_of_human_trafficking",
    "persons_with_serious_illnesses", "person_with_disabilities", "persons_with_mental_disorders",
    "victim", "ps_v",
]


def _is_staff():
    return bool(set(frappe.get_roles(frappe.session.user)) & set(STAFF_ROLES))


def _require_staff():
    if not _is_staff():
        frappe.throw(_("Only NISC staff can do this."), frappe.PermissionError)


def _get_booking_row(booking_name):
    """Return (client_doc, booking_row). Raises if the booking doesn't exist."""
    parent = frappe.db.get_value("ISM Booking", booking_name, "parent")
    if not parent:
        frappe.throw(_("ISM booking not found."))
    client_doc = frappe.get_doc("Client Details", parent)
    row = next((r for r in client_doc.ism_bookings if r.name == booking_name), None)
    if not row:
        frappe.throw(_("ISM booking not found."))
    return client_doc, row


def _require_owning_client(client_doc):
    """The logged-in Website User must be the client this booking belongs to."""
    if _is_staff():
        return
    if frappe.session.user != client_doc.email:
        frappe.throw(_("You do not have access to this ISM booking."), frappe.PermissionError)


def _checked_items(row):
    """[(label, notes, referral_category), ...] for every ticked box on the row."""
    meta = frappe.get_meta("ISM Booking")
    items = []
    for fn in SUPPORT_FIELDS + VULNERABILITY_FIELDS:
        if row.get(fn):
            label = meta.get_label(fn)
            items.append({
                "label": label,
                "notes": row.get(f"{fn}_notes") or "",
                "referral_category": row.get(f"{fn}_referral_category") or "",
            })
    return items


# ---------------------------------------------------------------------------
# 1. Staff submits the completed ISM form for client review
# ---------------------------------------------------------------------------
@frappe.whitelist()
def submit_for_client_review(booking):
    _require_staff()
    client_doc, row = _get_booking_row(booking)

    # "ISM Scheduled" -> first submission. "Pending Client Review" -> the
    # client hasn't confirmed yet (e.g. the OTP expired or the email was
    # missed) and staff are resending a fresh code. Any other status means
    # the case has already moved on and must not be re-triggered.
    if row.booking_status not in ("ISM Scheduled", "Pending Client Review"):
        frappe.throw(_("Only a booking in 'ISM Scheduled' or 'Pending Client Review' status can be (re)submitted for review. Current status: {0}").format(row.booking_status))

    if not client_doc.email:
        frappe.throw(_("This client has no email on file - cannot send the review OTP."))

    otp = str(random.randint(100000, 999999))
    frappe.cache().set_value(
        f"{OTP_CACHE_PREFIX}{row.name}",
        {"otp": otp, "generated_at": str(datetime.now())},
        expires_in_sec=OTP_TTL_SECONDS,
    )

    items = _checked_items(row)
    items_html = "".join(
        f"<li><strong>{i['label']}</strong>"
        + (f" - {i['notes']}" if i["notes"] else "")
        + (f" (Referral: {i['referral_category']})" if i["referral_category"] else "")
        + "</li>"
        for i in items
    ) or "<li>No specific support items recorded.</li>"

    plan = row.personal_integration_plan or "-"
    provider = row.referred_to_provider or ""

    email_body = f"""
    <div style="font-family: Arial, sans-serif; font-size: 14px; color: #333;">
        <p>Dear {client_doc.first_name or "Client"},</p>
        <p>Your Integration Support Meeting has been recorded. Please review the summary below and confirm it using the OTP code.</p>
        <p><strong>Summary of your meeting:</strong></p>
        <ul>{items_html}</ul>
        <p><strong>Personal Integration Plan and Expected Outcomes:</strong><br>{plan}</p>
        {f"<p><strong>Referred to:</strong> {provider}</p>" if provider else ""}
        <p style="font-size: 22px; font-weight: bold; letter-spacing: 3px;">{otp}</p>
        <p>Enter this code on your profile page to confirm. This code expires in 30 minutes.</p>
        <p>If you did not attend this meeting or believe this is a mistake, please contact NISC.</p>
    </div>
    """

    email_params = {
        "type": "email",
        "displayname": "I Belong System",
        "firstname": client_doc.first_name or "Applicant",
        "lastname": "",
        "emails": [client_doc.email],
        "mobile": "",
        "subjectEN": "Please Confirm Your Integration Support Meeting",
        "bodyEN": email_body,
        "subjectMT": "Please Confirm Your Integration Support Meeting",
        "bodyMT": email_body,
    }
    try:
        frappe.call("ibelong_system.mail_api.email_api.send_email_notification", params=email_params)
    except Exception:
        frappe.log_error("ISM review OTP email failed", frappe.get_traceback())

    if client_doc.country_code and client_doc.mobile_number:
        sms_text = f"Your ISM review confirmation code is {otp}. Enter it on your profile page. Valid for 30 minutes."
        sms_params = {
            "type": "sms",
            "displayname": "I Belong System",
            "firstname": client_doc.first_name or "Applicant",
            "lastname": "",
            "mobile": f"{client_doc.country_code}{client_doc.mobile_number}",
            "subjectEN": "ISM Confirmation Code",
            "bodyEN": sms_text,
            "subjectMT": "ISM Confirmation Code",
            "bodyMT": sms_text,
        }
        try:
            frappe.call("ibelong_system.mail_api.email_api.send_email_notification", params=sms_params)
        except Exception:
            frappe.log_error("ISM review OTP sms failed", frappe.get_traceback())

    row.booking_status = "Pending Client Review"
    client_doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"status": "success", "message": "Review OTP sent to the client."}


# ---------------------------------------------------------------------------
# 2. Client-facing: fetch the meeting summary - works for ANY status, so the
# client can review a pending confirmation as well as look back at any past
# ISM. additional_notes is intentionally NEVER returned - staff/provider only.
# ---------------------------------------------------------------------------
@frappe.whitelist()
def get_ism_review_summary(booking):
    client_doc, row = _get_booking_row(booking)
    _require_owning_client(client_doc)

    referral_status = None
    referral_comments = None
    if row.linked_referral:
        ref = frappe.db.get_value(
            "Client Referral", row.linked_referral,
            ["referral_status", "referral_reason"], as_dict=True,
        )
        if ref:
            referral_status = ref.referral_status
            referral_comments = ref.referral_reason

            # Surface the service provider's latest follow-up note too, not
            # just the static reason captured when the referral was created.
            latest_note = frappe.db.get_value(
                "Referral Note",
                {"parent": row.linked_referral, "parenttype": "Client Referral"},
                "note",
                order_by="added_on desc",
            )
            if latest_note:
                referral_comments = (
                    f"{referral_comments} Latest update: {latest_note}"
                    if referral_comments else latest_note
                )

    return {
        "status": "success",
        "booking_status": row.booking_status,
        "slot_date": row.slot_date,
        "slot_time": row.slot_time,
        "officer_name": row.officer_name,
        "items": _checked_items(row),
        "personal_integration_plan": row.personal_integration_plan or "",
        "follow_up": row.follow_up or "",
        "referred_to_provider": row.referred_to_provider or "",
        "referral_status": referral_status or "",
        "referral_comments": referral_comments or "",
        "client_confirmed": bool(row.client_confirmed),
        "client_confirmed_on": row.client_confirmed_on or "",
        # additional_notes is intentionally NEVER returned here - staff/provider only.
    }


# ---------------------------------------------------------------------------
# 3. Client-facing: confirm with OTP
# ---------------------------------------------------------------------------
@frappe.whitelist()
def confirm_ism_review(booking, otp):
    client_doc, row = _get_booking_row(booking)
    _require_owning_client(client_doc)

    if row.booking_status != "Pending Client Review":
        return {"error": "This booking is not awaiting your review."}

    cache_key = f"{OTP_CACHE_PREFIX}{row.name}"
    cached = frappe.cache().get_value(cache_key)
    if not cached or str(cached.get("otp")) != str(otp).strip():
        return {"error": "Incorrect or expired code. Please request a new one."}

    frappe.cache().delete_value(cache_key)

    new_status = "Case Referred" if row.referred_to_provider else "Case Open"
    row.booking_status = new_status
    row.client_confirmed = 1
    row.client_confirmed_on = frappe.utils.now()

    if row.referred_to_provider and not row.linked_referral:
        items = _checked_items(row)
        categories = ", ".join(sorted({i["referral_category"] for i in items if i["referral_category"]}))
        referral = frappe.get_doc({
            "doctype": "Client Referral",
            "client": client_doc.name,
            "referred_to": row.referred_to_provider,
            "referral_status": "Sent",
            "referral_date": frappe.utils.today(),
            "referred_by": row.officer_name or "",
            "referral_reason": (
                (f"Referral categories: {categories}. " if categories else "")
                + (row.personal_integration_plan or "")
            ) or "ISM meeting referral.",
        })
        referral.insert(ignore_permissions=True)
        row.linked_referral = referral.name

    client_doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"status": "success", "new_status": new_status}


# ---------------------------------------------------------------------------
# 4. Staff-only: close a case
# ---------------------------------------------------------------------------
@frappe.whitelist()
def close_ism_case(booking):
    _require_staff()
    client_doc, row = _get_booking_row(booking)

    if row.booking_status not in ("Case Open", "Case Referred"):
        frappe.throw(_("Only a case in 'Case Open' or 'Case Referred' status can be closed. Current status: {0}").format(row.booking_status))

    row.booking_status = "Case Closed"
    client_doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"status": "success"}


# ---------------------------------------------------------------------------
# 5. Client Details validate hook: no separate "Close Case" action exists in
# the UI - NISC staff close a case by editing the ISM Booking row's
# booking_status field directly (in the existing ism_bookings grid) and using
# the normal Save button. This hook is what actually enforces that only NISC
# staff can make that specific transition, and only from a valid prior state.
# ---------------------------------------------------------------------------
def validate_client_details(doc, method=None):
    is_staff = bool(set(frappe.get_roles(frappe.session.user)) & set(STAFF_ROLES))

    for row in (doc.get("ism_bookings") or []):
        row_name = row.get("name") or ""
        if not row_name or row_name.startswith("new-"):
            continue  # not yet saved - nothing to compare against

        prev_status = frappe.db.get_value("ISM Booking", row_name, "booking_status")
        if prev_status is None or prev_status == row.booking_status:
            continue  # unchanged, or a stale reference - nothing to enforce

        if row.booking_status == "Case Closed":
            if not is_staff:
                frappe.throw(_("Only NISC staff can close an ISM case."), frappe.PermissionError)
            if prev_status not in ("Case Open", "Case Referred"):
                frappe.throw(_(
                    "An ISM case can only be closed from 'Case Open' or 'Case Referred' (current: {0})."
                ).format(prev_status))
