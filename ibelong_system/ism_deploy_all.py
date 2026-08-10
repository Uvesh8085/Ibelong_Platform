"""
ONE-FILE deployer for the ISM workflow feature - creates all needed files
and runs the migrations, in one go. Paste this whole file as
ism_deploy_all.py, then run:
  bench --site ibelong.in execute ibelong_system.ism_deploy_all.run

Does NOT touch the Registration page/workflow. Does NOT run any data
backfill/remap on migrated data - only schema + new-file changes.
"""

import os
import importlib
import frappe

APP_DIR = os.path.dirname(__file__)

FILES = {}

FILES['get_booking_data.py'] = r'''import frappe
from frappe.utils import getdate, get_time
from datetime import datetime
import pytz


def _add_booking_row(doc, slot_date, slot_time, officer_name, status):
    """Append a new appointment to the ism_bookings child table.

    Clients may book more than one ISM, so every booking gets its own row.
    The single ism_slot / selected_time fields are still maintained above so
    existing pages and migrated data keep working.

    A row is only added when we actually know the appointment date - otherwise
    an empty Time value is coerced to "now" and we end up storing a blank
    booking.
    """
    if not slot_date:
        return

    doc.append("ism_bookings", {
        "slot_date": slot_date,
        "slot_time": slot_time,
        "officer_name": officer_name,
        "booking_status": status,
        "support_need": doc.get("ism_support_need"),
    })


def _update_latest_booking(doc, status, slot_date=None, slot_time=None, officer_name=None):
    """Update the most recent booking row (used for reschedule / cancel).

    Falls back to appending a row when the client has no rows yet, so a
    reschedule or cancellation is never silently lost.
    """
    rows = doc.get("ism_bookings") or []
    if not rows:
        _add_booking_row(doc, slot_date, slot_time, officer_name, status)
        return

    row = rows[-1]
    row.booking_status = status
    if slot_date:
        row.slot_date = slot_date
    if slot_time:
        row.slot_time = slot_time
    if officer_name:
        row.officer_name = officer_name


@frappe.whitelist(allow_guest=True)
def create_client():
    try:
        data = frappe.local.form_dict or {}
        frappe.log_error("BOOKING PAYLOAD", data)

        # -----------------------------
        # BASIC DETAILS
        # -----------------------------
        email = (data.get("CustomerEmail") or "").strip().lower()
        phone = (data.get("CustomerPhone") or "").strip()
        customer_name = (data.get("CustomerName") or "").strip()

        frappe.log_error("BOOKING IDENTIFIERS", {
            "email": email,
            "phone": phone,
            "name": customer_name
        })

        if not email and not phone:
            frappe.log_error("CREATE_CLIENT_ERROR", "Missing email & phone")
            return {"error": "Email or phone is required to identify client"}

        # -----------------------------
        # STAFF / OFFICER NAME
        # -----------------------------
        staff = data.get("StaffMembers") or []
        officer_name = staff[0].get("DisplayName") if staff else ""

        # -----------------------------
        # SERVICE / STATUS
        # -----------------------------


        # -----------------------------
        # DATE & TIME HANDLING
        # -----------------------------
        # -----------------------------
        # DATE & TIME HANDLING (STORE MALTA TIME AS-IS)
        # -----------------------------
        # DATE & TIME HANDLING (CONVERT UTC TO MALTA TIME)
        # -----------------------------
        start_time_raw = data.get("StartTime")

        ism_slot_date = None
        ism_slot_time = None

        if start_time_raw:
            try:
                # 1. Parse the Microsoft Bookings format: "04/15/2026 06:00:00" (MM/DD/YYYY HH:MM:SS)
                utc_dt = datetime.strptime(start_time_raw, "%m/%d/%Y %H:%M:%S")
                
                # 2. Tell Python this time is in UTC
                utc_dt = pytz.utc.localize(utc_dt)
                
                # 3. Convert it to Malta local time
                malta_tz = pytz.timezone("Europe/Malta")
                malta_dt = utc_dt.astimezone(malta_tz)

                # 4. Extract the correct date and time
                ism_slot_date = malta_dt.date()
                ism_slot_time = malta_dt.time()

            except Exception as e:
                frappe.log_error(
                    "DATE PARSE ERROR",
                    f"Raw value: {start_time_raw} | Error: {str(e)}"
                )

        # -----------------------------
        # FIND CLIENT (EMAIL → PHONE)
        # -----------------------------
        client_name = frappe.db.get_value(
            "Client Details",
            {"email": email},
            "name"
        )

        if not client_name and phone:
            client_name = frappe.db.get_value(
                "Client Details",
                {"mobile_number": phone},
                "name"
            )

        if not client_name:
            frappe.log_error(
                "CLIENT NOT FOUND",
                {"email": email, "phone": phone}
            )
            return {
                "error": "Client not found",
                "email": email,
                "phone": phone
            }

        # -----------------------------
        # LOAD DOC USING get_doc
        # -----------------------------
        doc = frappe.get_doc("Client Details", client_name)

        # Client clarification (07/08/2026): a client may book multiple ISMs
        # over time, but never more than one ACTIVE case at once. The ISM tab
        # is hidden on the profile while a case is active (see v3-progle-page),
        # but the client could still reach an old MS Bookings link (e.g. from
        # a saved email) and book again - so this is enforced here too. If an
        # active booking already exists, skip the update entirely: nothing on
        # Client Details changes and no new row is appended.
        existing_active = next(
            (r for r in doc.ism_bookings if r.booking_status not in ("Case Closed", "ISM Cancelled")),
            None,
        )
        if existing_active:
            frappe.log_error(
                "BOOKING SKIPPED - ACTIVE ISM ALREADY EXISTS",
                {"client": doc.name, "active_booking": existing_active.name, "status": existing_active.booking_status},
            )
            return {
                "status": "skipped",
                "message": "Client already has an active ISM booking. Please complete the current active ISM meeting first.",
                "client": doc.name,
            }

        # NISC enhancement (30/07/2026): ISM booking must NEVER change the
        # client's course-progress status (doc.status). A client can book an
        # ISM at any point - right after registration, mid-course, or after
        # graduating - and their status must keep reflecting their course
        # progress only. ISM state lives entirely in the ism_bookings child
        # table (booking_status) instead.
        doc.isr_officer_name = officer_name
        doc.ism_slot = ism_slot_date
        doc.selected_time = ism_slot_time
        doc.isr_status = "ISM Meeting Scheduled"

        # Marks that this client has engaged with ISM at least once. Distinct
        # from doc.status (course progress), which is never touched here.
        doc.integration_support = 1

        # Each booking is kept as its own row so a client can book several ISMs
        _add_booking_row(doc, ism_slot_date, ism_slot_time, officer_name, "ISM Scheduled")

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        # -----------------------------
        # SUCCESS LOG
        # -----------------------------
        frappe.log_error(
            "BOOKING UPDATE SUCCESS",
            {
                "client": doc.name,
                "officer": officer_name,
                "date": ism_slot_date,
                "time": ism_slot_time,
                "status": "ISM Meeting Scheduled"
            }
        )

        return {
            "status": "success",
            "client": doc.name
        }

    except Exception:
        frappe.log_error(
            title="CREATE_CLIENT_FATAL_ERROR",
            message=frappe.get_traceback()
        )
        return {"error": "Internal error. Check error logs."}


import frappe
from frappe.utils import getdate, get_time

 
@frappe.whitelist(allow_guest=True)
def reschedule_meeting():
    try:
        data = frappe.local.form_dict or {}
        frappe.log_error("BOOKING PAYLOAD", data)

        # -----------------------------
        # BASIC DETAILS
        # -----------------------------
        email = (data.get("CustomerEmail") or "").strip().lower()
        phone = (data.get("CustomerPhone") or "").strip()
        customer_name = (data.get("CustomerName") or "").strip()

        frappe.log_error("BOOKING IDENTIFIERS", {
            "email": email,
            "phone": phone,
            "name": customer_name
        })

        if not email and not phone:
            frappe.log_error("CREATE_CLIENT_ERROR", "Missing email & phone")
            return {"error": "Email or phone is required to identify client"}

        # -----------------------------
        # STAFF / OFFICER NAME
        # -----------------------------
        staff = data.get("StaffMembers") or []
        officer_name = staff[0].get("DisplayName") if staff else ""

        # -----------------------------
        # SERVICE / STATUS
        # -----------------------------


        # -----------------------------
        # DATE & TIME HANDLING
        # -----------------------------
        # DATE & TIME HANDLING (CONVERT UTC TO MALTA TIME)
        # -----------------------------
        start_time_raw = data.get("StartTime")

        ism_slot_date = None
        ism_slot_time = None

        if start_time_raw:
            try:
                # 1. Parse the Microsoft Bookings format: "04/15/2026 06:00:00" (MM/DD/YYYY HH:MM:SS)
                utc_dt = datetime.strptime(start_time_raw, "%m/%d/%Y %H:%M:%S")
                
                # 2. Tell Python this time is in UTC
                utc_dt = pytz.utc.localize(utc_dt)
                
                # 3. Convert it to Malta local time
                malta_tz = pytz.timezone("Europe/Malta")
                malta_dt = utc_dt.astimezone(malta_tz)

                # 4. Extract the correct date and time
                ism_slot_date = malta_dt.date()
                ism_slot_time = malta_dt.time()

            except Exception as e:
                frappe.log_error(
                    "DATE PARSE ERROR",
                    f"Raw value: {start_time_raw} | Error: {str(e)}"
                )
        # -----------------------------
        # FIND CLIENT (EMAIL → PHONE)
        # -----------------------------
        client_name = frappe.db.get_value(
            "Client Details",
            {"email": email},
            "name"
        )

        if not client_name and phone:
            client_name = frappe.db.get_value(
                "Client Details",
                {"mobile_number": phone},
                "name"
            )

        if not client_name:
            frappe.log_error(
                "CLIENT NOT FOUND",
                {"email": email, "phone": phone}
            )
            return {
                "error": "Client not found",
                "email": email,
                "phone": phone
            }

        # -----------------------------
        # LOAD DOC USING get_doc
        # -----------------------------
        doc = frappe.get_doc("Client Details", client_name)

        # See create_client(): ISM booking never touches doc.status.
        doc.isr_officer_name = officer_name
        doc.ism_slot = ism_slot_date
        doc.ism_slot_time = ism_slot_time
        doc.isr_status = "ISM Meeting Rescheduled"

        # A reschedule moves the latest appointment rather than adding a new one
        _update_latest_booking(doc, "ISM Scheduled", ism_slot_date, ism_slot_time, officer_name)

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        # -----------------------------
        # SUCCESS LOG
        # -----------------------------
        frappe.log_error(
            "BOOKING UPDATE SUCCESS",
            {
                "client": doc.name,
                "officer": officer_name,
                "date": ism_slot_date,
                "time": ism_slot_time,
                "status": "ISM Meeting Rescheduled"
            }
        )

        return {
            "status": "success",
            "client": doc.name
        }

    except Exception:
        frappe.log_error(
            title="CREATE_CLIENT_FATAL_ERROR",
            message=frappe.get_traceback()
        )
        return {"error": "Internal error. Check error logs."}


@frappe.whitelist(allow_guest=True)
def cancel_meeting():
    try:
        data = frappe.local.form_dict or {}
        frappe.log_error("BOOKING PAYLOAD", data)

        # -----------------------------
        # BASIC DETAILS
        # -----------------------------
        email = (data.get("CustomerEmail") or "").strip().lower()
        phone = (data.get("CustomerPhone") or "").strip()

        if not email and not phone:
            return {"error": "Email or phone is required"}

        # -----------------------------
        # FIND CLIENT
        # -----------------------------
        client_name = frappe.db.get_value(
            "Client Details", {"email": email}, "name"
        )

        if not client_name and phone:
            client_name = frappe.db.get_value(
                "Client Details", {"mobile_number": phone}, "name"
            )

        if not client_name:
            return {"error": "Client not found"}

        doc = frappe.get_doc("Client Details", client_name)

        # -----------------------------
        # STAFF / OFFICER
        # -----------------------------
        staff = data.get("StaffMembers") or []
        if staff and staff[0].get("DisplayName"):
            doc.isr_officer_name = staff[0]["DisplayName"]

        # -----------------------------
        # SERVICE / STATUS
        # -----------------------------


        # -----------------------------
        # DATE & TIME (ONLY IF PRESENT)
        # -----------------------------
        start_time_raw = data.get("StartTime")
        if start_time_raw:
            try:
                date_part, time_part = start_time_raw.split(" ", 1)
                doc.ism_slot = getdate(date_part)
                doc.ism_slot_time = get_time(time_part)
            except Exception:
                frappe.log_error("DATE PARSE ERROR", start_time_raw)

        # -----------------------------
        # CANCEL STATUS (ALWAYS SET) - see create_client(): never touches doc.status
        # -----------------------------
        doc.isr_status = "Meeting Cancelled"

        _update_latest_booking(doc, "ISM Cancelled")

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": "success",
            "client": doc.name
        }

    except Exception:
        frappe.log_error(
            "CANCEL_MEETING_FATAL",
            frappe.get_traceback()
        )
        return {"error": "Internal error"}
'''

FILES['ism_review.py'] = r'''"""
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
'''

FILES['ism_phase2.py'] = r'''"""
Phase 2 - load the existing referral system on the Client Details desk form by
registering apps/ibelong_system/ibelong_system/public/js/client_details_referral.js
as an enabled Client Script (Form view). No bench restart needed.

Run: bench --site ibelong.test execute ibelong_system.ism_phase2.run
"""

import os
import frappe

CS_NAME = "Client Details Referral Section"
JS_PATH = os.path.join(os.path.dirname(__file__), "public", "js", "client_details_referral.js")


def run():
    print("=== ISM Phase 2: enable referral Client Script ===")
    with open(JS_PATH) as fh:
        code = fh.read()
    print(f"  loaded {JS_PATH} ({len(code)} chars)")

    if frappe.db.exists("Client Script", CS_NAME):
        doc = frappe.get_doc("Client Script", CS_NAME)
        doc.dt = "Client Details"
        doc.view = "Form"
        doc.enabled = 1
        doc.script = code
        doc.save(ignore_permissions=True)
        print(f"  [ok] updated Client Script '{CS_NAME}'")
    else:
        doc = frappe.get_doc(
            {
                "doctype": "Client Script",
                "name": CS_NAME,
                "dt": "Client Details",
                "view": "Form",
                "enabled": 1,
                "script": code,
            }
        )
        doc.insert(ignore_permissions=True)
        print(f"  [ok] created Client Script '{CS_NAME}'")

    frappe.db.commit()
    frappe.clear_cache()
    print("\nDone. Open any Client Details record in the desk — the 'New Referral' /")
    print("'View All Referrals' buttons and the referral section should now appear.")
'''

FILES['ism_multi_schema_only.py'] = r'''"""
DEPLOYMENT VARIANT for environments where migrated data must not be touched.

Same as ism_multi.py but WITHOUT the backfill() step - creates the ISM
Booking child doctype and the ism_bookings Table field on Client Details,
but does not create rows from clients' existing single-field ISM data.

Consequence: clients with historical (pre-existing) ISM activity will show
"no ISM bookings yet" in the new UI until they book again. New bookings from
this point forward work identically to an environment where the backfill ran.

Run: bench --site <site> execute ibelong_system.ism_multi_schema_only.run
"""

import frappe
from ibelong_system.ism_multi import ensure_child_doctype, ensure_table_field


def run():
    print("=== ISM Booking: schema only (no backfill - migrated data untouched) ===")
    ensure_child_doctype()
    ensure_table_field()
    frappe.db.commit()
    frappe.clear_cache()
    print("\nDone. Child table + field ready. Migrated data NOT touched (backfill skipped).")
'''

FILES['ism_v2_booking_fields.py'] = r'''"""
NISC enhancement (30/07/2026 doc) - move the ISM meeting form from single
Client Details fields to PER-BOOKING fields on the ISM Booking child table,
since a client can now have multiple ISM meetings and things like "Follow-Up"
only make sense per meeting.

Adds to ISM Booking:
  - support checkboxes (9) + notes + referral category, each opens on tick
  - vulnerability checkboxes (8) + notes + referral category, each opens on tick
  - personal_integration_plan  ("Personal Integration Plan and Expected Outcomes")
  - follow_up                  (free text, not filled at the first meeting)
  - referred_to_provider       (Link -> External Service Provider; setting this
                                 + submitting for review is what makes a case
                                 "Case Referred")
  - additional_notes           (internal only - staff + referred provider)
  - client_confirmed / client_confirmed_on (OTP confirmation audit)
  - linked_referral            (Link -> Client Referral, set once created)

Also updates booking_status options to the new lifecycle:
  ISM Scheduled -> ISM Cancelled | Pending Client Review
  Pending Client Review -> Case Open | Case Referred   (client OTP-confirms)
  Case Open | Case Referred -> Case Closed             (NISC staff only)

The old Client Details Phase-3 fields (employment_assistance_notes etc.,
case_status) are left in place but are no longer the active data path -
superseded by these per-booking fields.

Run: bench --site ibelong.test execute ibelong_system.ism_v2_booking_fields.run
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

REFERRAL_CATEGORIES = (
    "\nEducational Support\nEmployment Assistance\nDocumentation Assistance\n"
    "Family Support\nAccommodation Support\nHealth Services\n"
    "Well-being / Mental Health Support\nSocial Integration Activities\n"
    "Legal Assistance\nOther"
)

NEW_BOOKING_STATUS_OPTIONS = (
    "\nISM Scheduled\nISM Cancelled\nPending Client Review\n"
    "Case Open\nCase Referred\nCase Closed"
)

SUPPORT_CHECKS = [
    "employment_assistance", "educational_support", "documentation_assistance",
    "family_support", "accommodation_support", "health_services",
    "wellbeing_mental_health_support", "social_integration_activities", "other_support",
]

VULNERABILITY_CHECKS = [
    "pregnant_women", "single_parents_with_minor_children", "victims_of_human_trafficking",
    "persons_with_serious_illnesses", "person_with_disabilities", "persons_with_mental_disorders",
    "victim", "ps_v",
]

# Human labels for the checkboxes (ISM Booking is a fresh child table, so these
# don't exist yet as fields anywhere - unlike Phase 3 on Client Details).
LABELS = {
    "employment_assistance": "Employment Assistance",
    "educational_support": "Educational Support",
    "documentation_assistance": "Documentation Assistance",
    "family_support": "Family Support",
    "accommodation_support": "Accommodation Support",
    "health_services": "Health Services",
    "wellbeing_mental_health_support": "Well-being / Mental Health Support",
    "social_integration_activities": "Social Integration Activities",
    "other_support": "Other Support",
    "pregnant_women": "Pregnant Women",
    "single_parents_with_minor_children": "Single Parents with Minor Children",
    "victims_of_human_trafficking": "Victims of Human Trafficking",
    "persons_with_serious_illnesses": "Persons with Serious Illnesses",
    "person_with_disabilities": "Person with Disabilities",
    "persons_with_mental_disorders": "Persons with Mental Disorders",
    "victim": "Victims of Torture, Rape, or Severe Psychological Violence",
    "ps_v": "Physical or Sexual Violence (incl. domestic)",
}


def _pair(fn):
    label = LABELS[fn]
    dep = f"eval:doc.{fn}==1"
    return [
        {"fieldname": fn, "label": label, "fieldtype": "Check"},
        {"fieldname": f"{fn}_notes", "label": f"{label} - Notes", "fieldtype": "Small Text",
         "insert_after": fn, "depends_on": dep, "translatable": 0},
        {"fieldname": f"{fn}_referral_category", "label": f"{label} - Referral Category", "fieldtype": "Select",
         "options": REFERRAL_CATEGORIES, "insert_after": f"{fn}_notes", "depends_on": dep, "translatable": 0},
    ]


def run():
    print("=== Extend ISM Booking: per-meeting form fields ===")

    fields = []
    fields.append({"fieldname": "support_section", "fieldtype": "Section Break", "label": "Support Needed"})
    for fn in SUPPORT_CHECKS:
        fields.extend(_pair(fn))

    fields.append({"fieldname": "vulnerability_section", "fieldtype": "Section Break", "label": "Vulnerable Groups"})
    for fn in VULNERABILITY_CHECKS:
        fields.extend(_pair(fn))

    fields.append({"fieldname": "outcome_section", "fieldtype": "Section Break", "label": "Meeting Outcome"})
    fields.append({"fieldname": "personal_integration_plan", "fieldtype": "Small Text",
                    "label": "Personal Integration Plan and Expected Outcomes"})
    fields.append({"fieldname": "follow_up", "fieldtype": "Small Text",
                    "label": "Follow-Up",
                    "description": "Not filled in at the first meeting - used if the client returns for a further meeting."})
    fields.append({"fieldname": "referred_to_provider", "fieldtype": "Link", "options": "External Service Provider",
                    "label": "Refer to Service Provider",
                    "description": "Setting this and submitting for client review marks the case as Case Referred."})
    fields.append({"fieldname": "linked_referral", "fieldtype": "Link", "options": "Client Referral",
                    "label": "Linked Referral", "read_only": 1})

    fields.append({"fieldname": "internal_section", "fieldtype": "Section Break", "label": "Internal Only"})
    fields.append({"fieldname": "additional_notes", "fieldtype": "Small Text",
                    "label": "Additional Notes",
                    "description": "Never shown to the client. Visible to NISC staff and, if referred, to the receiving service provider."})

    fields.append({"fieldname": "confirmation_section", "fieldtype": "Section Break", "label": "Client Confirmation"})
    fields.append({"fieldname": "client_confirmed", "fieldtype": "Check", "label": "Client Confirmed via OTP", "read_only": 1})
    fields.append({"fieldname": "client_confirmed_on", "fieldtype": "Datetime", "label": "Confirmed On", "read_only": 1})

    print(f"  creating/ensuring {len(fields)} fields on ISM Booking ...")
    create_custom_fields({"ISM Booking": fields}, update=True)

    # booking_status: widen options (native field on a fully custom doctype ->
    # edit the DocType doc directly rather than via Custom Field)
    dt = frappe.get_doc("DocType", "ISM Booking")
    for f in dt.fields:
        if f.fieldname == "booking_status":
            f.options = NEW_BOOKING_STATUS_OPTIONS
            break
    dt.save(ignore_permissions=True)
    print("  [ok] booking_status options updated to new lifecycle vocabulary")

    frappe.db.commit()
    frappe.clear_cache()

    meta = frappe.get_meta("ISM Booking")
    missing = [f["fieldname"] for f in fields if not meta.get_field(f["fieldname"])]
    print("  missing fields:", missing or "none")
    print("\nDone.")
'''

FILES['ism_portal_support.py'] = r'''"""
Batch 2 - portal/profile page ISM tab (enhancement 2).

Adds, as the FIRST thing on the v3 profile page ISM tab:
  - the "Integration Support Meeting (OPTIONAL)" intro,
  - a "What kind of support do you need?" dropdown (full ISM support list),
  - an "Other Support -> Please Specify" free-text field,
  - a Save button that persists to Client Details (ism_support_need / ism_support_other)
    via the existing update_client_and_sync_email API, so it reaches NISC staff.

Also: expands the ism_support_need Select options to the full ISM list and adds
the ism_support_other custom field.

Run: bench --site ibelong.test execute ibelong_system.ism_portal_support.run
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

PROFILE_PAGE = "v3-progle-page"

SUPPORT_OPTIONS = (
    "\nEmployment Assistance\nEducational Support\nDocumentation Assistance\n"
    "Family Support\nAccommodation Support\nHealth Services\n"
    "Well-being / Mental Health Support\nSocial Integration Activities\n"
    "Legal Assistance\nOther Support"
)

ANCHOR = (
    '<div class="calendar-container">\n'
    '                        <h5 class="section-title">Select Date and Time for ISM Session</h5>'
)

SUPPORT_BLOCK = """<div class="calendar-container">
                        <div class="mb-4" id="ismSupportBlock">
                           <h5 class="section-title">Integration Support Meeting (OPTIONAL)</h5>
                           <p>The Integration Support Meeting (ISM) is optional and can be booked if integration assistance is required.</p>
                           <p>The one-to-one meeting with a member of the National Integration Support Centre team is designed to help you understand and access the services, opportunities, and support available as you settle and build your life in Malta.</p>
                           <p>The meeting is free of charge and aims to help you identify the integration support best suited to your individual needs.</p>
                           <h6 class="mt-4 fw-bold">What kind of support do you need?</h6>
                           <p class="text-muted">Please tell us what type of support you are seeking. This information will help us prepare for your meeting and identify any services that may be relevant to your situation.</p>
                           <div class="row g-3 align-items-end">
                              <div class="col-md-6">
                                 <label for="ismSupportNeedPortal" class="form-label">Support needed</label>
                                 <select class="form-select" id="ismSupportNeedPortal">
                                    <option value="">Select support type&hellip;</option>
                                    {% for opt in ["Employment Assistance","Educational Support","Documentation Assistance","Family Support","Accommodation Support","Health Services","Well-being / Mental Health Support","Social Integration Activities","Legal Assistance","Other Support"] %}
                                    <option {% if doc_data and doc_data.ism_support_need == opt %}selected{% endif %}>{{ opt }}</option>
                                    {% endfor %}
                                 </select>
                              </div>
                              <div class="col-md-6" id="ismSupportOtherWrap" style="display:none">
                                 <label for="ismSupportOther" class="form-label">Please Specify</label>
                                 <input type="text" class="form-control" id="ismSupportOther" value="{% if doc_data and doc_data.ism_support_other %}{{ doc_data.ism_support_other }}{% endif %}">
                              </div>
                           </div>
                           <div class="mt-2">
                              <button type="button" class="btn btn-outline-primary btn-sm" id="saveIsmSupport"><i class="fas fa-save me-1"></i>Save support need</button>
                              <span id="ismSupportSaved" class="text-success ms-2" style="display:none">Saved &#10003;</span>
                           </div>
                           <hr class="my-4">
                        </div>
                        <h5 class="section-title">Select Date and Time for ISM Session</h5>"""

SUPPORT_JS = """
<script>
document.addEventListener("DOMContentLoaded", function(){
  var sel=document.getElementById("ismSupportNeedPortal");
  if(!sel) return;
  var otherWrap=document.getElementById("ismSupportOtherWrap");
  var otherInp=document.getElementById("ismSupportOther");
  var saveBtn=document.getElementById("saveIsmSupport");
  var savedMsg=document.getElementById("ismSupportSaved");
  function toggleOther(){ if(otherWrap) otherWrap.style.display=(sel.value==="Other Support")?"block":"none"; }
  toggleOther(); sel.addEventListener("change", toggleOther);
  if(saveBtn) saveBtn.addEventListener("click", function(){
    var fnEl=document.getElementById("fileNumber");
    var fn=fnEl?(fnEl.value||fnEl.getAttribute("value")||""):"";
    if(!fn){ alert("File number missing - cannot save support need."); return; }
    var fields={ ism_support_need: sel.value||"", ism_support_other:(sel.value==="Other Support"&&otherInp)?(otherInp.value||""):"" };
    frappe.call({ method:"ibelong_system.update_user.update_client_and_sync_email",
      args:{ doctype:"Client Details", name:fn, fieldname:fields },
      callback:function(r){ if(savedMsg){ savedMsg.style.display="inline"; setTimeout(function(){savedMsg.style.display="none";},2500);} },
      error:function(e){ alert("Could not save support need. Please try again."); }
    });
  });
});
</script>
"""


def run():
    print("=== Batch 2: portal ISM support dropdown ===")

    # 1. field schema
    cf = "Client Details-ism_support_need"
    if frappe.db.exists("Custom Field", cf):
        frappe.db.set_value("Custom Field", cf, "options", SUPPORT_OPTIONS)
        print("  [ok] expanded ism_support_need options to full ISM list")
    create_custom_fields(
        {"Client Details": [
            {"fieldname": "ism_support_other", "label": "Support Needed - Please Specify",
             "fieldtype": "Data", "insert_after": "ism_support_need", "translatable": 0,
             "depends_on": "eval:doc.ism_support_need=='Other Support'"},
        ]},
        update=True,
    )
    print("  [ok] ism_support_other field ensured")

    # 2. profile page injection
    html = (frappe.db.get_value("Web Page", PROFILE_PAGE, "main_section_html") or "").replace("\r\n", "\n")
    if "ismSupportNeedPortal" in html:
        print("  [skip] support block already present")
    else:
        if ANCHOR not in html:
            raise RuntimeError("[FAIL] ISM tab anchor not found on profile page")
        html = html.replace(ANCHOR, SUPPORT_BLOCK, 1)
        # append the JS once, before the last </div> of the page body is risky; append at end
        html = html + SUPPORT_JS
        frappe.db.set_value("Web Page", PROFILE_PAGE, "main_section_html", html, update_modified=True)
        print("  [ok] injected support block + JS into ISM tab")

    frappe.db.commit()
    frappe.clear_cache()
    print("\nDone. Portal ISM tab now leads with the support question; selection saves to Client Details.")
'''

FILES['ism_v2_insert_history.py'] = r'''"""
Insert the "Your ISM Appointments" history section into the ISM tab-pane on
the portal profile page (client_profile_v3). The section that existed here
before is gone (the pane currently ends right after the "Book ISM Session"
CTA + a note + Back/Submit buttons, per a live screenshot), so this INSERTS
rather than replaces.

For every past ISM booking, shows to the client:
  - date / time / officer / status
  - for "Pending Client Review": the Review & Confirm (OTP) panel
  - for "Case Open" / "Case Referred" / "Case Closed": a "View Details" panel
    with Personal Integration Plan, Follow-Up notes, and - if referred - the
    provider and referral status/comments.
additional_notes is never fetched/shown here - ism_review.get_ism_review_summary
never returns it, so there's nothing to leak.

Run: bench --site ibelong.test execute ibelong_system.ism_v2_insert_history.run
"""

import frappe

PROFILE_PAGE = "v3-progle-page"

ANCHOR = '<div class="action-buttons mt-4">\n                           <button type="button" class="btn-back" id="backToPersonal">'

HISTORY_BLOCK = """<div class="mb-4" id="ismBookingHistory">
                           <h6 class="mb-2"><i class="fas fa-history me-2"></i>Your ISM Appointments</h6>
                           {% if doc_data and doc_data.ism_bookings %}
                           <div class="table-responsive">
                              <table class="table table-sm align-middle">
                                 <thead class="table-light">
                                    <tr>
                                       <th scope="col">#</th>
                                       <th scope="col">Date</th>
                                       <th scope="col">Time</th>
                                       <th scope="col">Officer</th>
                                       <th scope="col">Status</th>
                                       <th scope="col"></th>
                                    </tr>
                                 </thead>
                                 <tbody>
                                    {% for b in doc_data.ism_bookings %}
                                    <tr>
                                       <td>{{ loop.index }}</td>
                                       <td>{{ frappe.format_value(b.slot_date, {"fieldtype": "Date"}) if b.slot_date else "-" }}</td>
                                       <td>{{ frappe.format_value(b.slot_time, {"fieldtype": "Time"}) if b.slot_time else "-" }}</td>
                                       <td>{{ b.officer_name or "-" }}</td>
                                       <td>
                                          {% if b.booking_status == "ISM Cancelled" %}<span class="badge bg-danger">{{ b.booking_status }}</span>
                                          {% elif b.booking_status == "Pending Client Review" %}<span class="badge bg-warning text-dark">{{ b.booking_status }}</span>
                                          {% elif b.booking_status == "Case Open" %}<span class="badge bg-info text-dark">{{ b.booking_status }}</span>
                                          {% elif b.booking_status == "Case Referred" %}<span class="badge" style="background-color:#6f42c1;color:#fff;">{{ b.booking_status }}</span>
                                          {% elif b.booking_status == "Case Closed" %}<span class="badge bg-secondary">{{ b.booking_status }}</span>
                                          {% else %}<span class="badge bg-primary">{{ b.booking_status or "ISM Scheduled" }}</span>{% endif %}
                                       </td>
                                       <td>
                                          {% if b.booking_status == "Pending Client Review" %}
                                          <button type="button" class="btn btn-outline-primary btn-sm ism-review-toggle" data-booking="{{ b.name }}" data-row="ismReviewPanel{{ loop.index }}">Review &amp; Confirm</button>
                                          {% elif b.booking_status in ("Case Open", "Case Referred", "Case Closed") %}
                                          <button type="button" class="btn btn-outline-secondary btn-sm ism-detail-toggle" data-row="ismDetailPanel{{ loop.index }}">View Details</button>
                                          {% endif %}
                                       </td>
                                    </tr>
                                    {% if b.booking_status == "Pending Client Review" %}
                                    <tr id="ismReviewPanel{{ loop.index }}" style="display:none">
                                       <td colspan="6">
                                          <div class="p-3 bg-light rounded ism-review-body" data-booking="{{ b.name }}">
                                             <div class="ism-review-loading text-muted"><i class="fas fa-spinner fa-spin me-1"></i>Loading your meeting summary&hellip;</div>
                                             <div class="ism-review-content" style="display:none"></div>
                                          </div>
                                       </td>
                                    </tr>
                                    {% elif b.booking_status in ("Case Open", "Case Referred", "Case Closed") %}
                                    <tr id="ismDetailPanel{{ loop.index }}" style="display:none" class="ism-detail-row">
                                       <td colspan="6">
                                          <div class="p-3 bg-light rounded">
                                             {% if b.personal_integration_plan %}
                                             <p class="mb-1"><strong>Personal Integration Plan and Expected Outcomes:</strong></p>
                                             <p class="mb-3">{{ b.personal_integration_plan }}</p>
                                             {% endif %}
                                             {% if b.follow_up %}
                                             <p class="mb-1"><strong>Follow-Up Notes:</strong></p>
                                             <p class="mb-3">{{ b.follow_up }}</p>
                                             {% endif %}
                                             {% if b.linked_referral %}
                                             <hr>
                                             <p class="mb-1"><strong>Referral Information</strong></p>
                                             <p class="mb-1"><strong>Referred to:</strong> {{ b.referred_to_provider or "-" }}</p>
                                             <p class="mb-0"><strong>Referral Status:</strong>
                                                {% if b.booking_status == "Case Closed" %}<span class="badge bg-secondary">Closed</span>
                                                {% else %}<span class="badge" style="background-color:#6f42c1;color:#fff;">Referred</span>{% endif %}
                                             </p>
                                             {% endif %}
                                             {% if not b.personal_integration_plan and not b.follow_up and not b.linked_referral %}
                                             <p class="text-muted mb-0">No additional details recorded for this meeting yet.</p>
                                             {% endif %}
                                          </div>
                                       </td>
                                    </tr>
                                    {% endif %}
                                    {% endfor %}
                                 </tbody>
                              </table>
                           </div>
                           <p class="text-muted mb-0"><small>You may book more than one Integration Support Meeting. Each appointment and its outcome is listed here.</small></p>
                           {% else %}
                           <p class="text-muted mb-0">You have not booked an Integration Support Meeting yet.</p>
                           {% endif %}
                        </div>
                        """

DETAIL_JS = """
<script>
document.addEventListener("DOMContentLoaded", function(){
  document.querySelectorAll(".ism-review-toggle").forEach(function(btn){
    btn.addEventListener("click", function(){
      var rowId = btn.getAttribute("data-row");
      var row = document.getElementById(rowId);
      if (!row) return;
      var showing = row.style.display !== "none";
      if (showing) { row.style.display = "none"; return; }
      row.style.display = "table-row";
      var body = row.querySelector(".ism-review-body");
      if (body.getAttribute("data-loaded") === "1") return;

      var booking = body.getAttribute("data-booking");
      frappe.call({
        method: "ibelong_system.ism_review.get_ism_review_summary",
        args: { booking: booking },
        callback: function(r){
          var loading = body.querySelector(".ism-review-loading");
          var content = body.querySelector(".ism-review-content");
          if (loading) loading.style.display = "none";
          if (!r.message || r.message.error) {
            content.innerHTML = '<p class="text-danger mb-0">' + ((r.message && r.message.error) || "Could not load this meeting summary.") + '</p>';
            content.style.display = "block";
            return;
          }
          var d = r.message;
          var itemsHtml = "";
          (d.items || []).forEach(function(i){
            itemsHtml += "<li><strong>" + i.label + "</strong>" +
              (i.notes ? " - " + i.notes : "") +
              (i.referral_category ? " (Referral: " + i.referral_category + ")" : "") +
              "</li>";
          });
          if (!itemsHtml) itemsHtml = "<li>No specific support items recorded.</li>";

          content.innerHTML =
            '<p class="mb-2"><strong>Summary of your meeting</strong></p>' +
            '<ul class="mb-3">' + itemsHtml + '</ul>' +
            (d.personal_integration_plan ? '<p class="mb-2"><strong>Personal Integration Plan and Expected Outcomes:</strong><br>' + d.personal_integration_plan + '</p>' : '') +
            (d.follow_up ? '<p class="mb-2"><strong>Follow-Up:</strong><br>' + d.follow_up + '</p>' : '') +
            (d.referred_to_provider ? '<p class="mb-2"><strong>Referred to:</strong> ' + d.referred_to_provider + '</p>' : '') +
            '<hr>' +
            '<p class="mb-2">Enter the confirmation code we sent you by email to confirm this summary is correct.</p>' +
            '<div class="row g-2 align-items-center">' +
              '<div class="col-auto"><input type="text" class="form-control form-control-sm ism-otp-input" placeholder="6-digit code" maxlength="6" style="width:140px"></div>' +
              '<div class="col-auto"><button type="button" class="btn btn-success btn-sm ism-otp-confirm">Confirm</button></div>' +
            '</div>' +
            '<div class="ism-otp-msg mt-2"></div>';
          content.style.display = "block";
          body.setAttribute("data-loaded", "1");

          content.querySelector(".ism-otp-confirm").addEventListener("click", function(){
            var otpVal = content.querySelector(".ism-otp-input").value.trim();
            var msgEl = content.querySelector(".ism-otp-msg");
            if (!otpVal) { msgEl.innerHTML = '<span class="text-danger">Please enter the code.</span>'; return; }
            frappe.call({
              method: "ibelong_system.ism_review.confirm_ism_review",
              args: { booking: booking, otp: otpVal },
              callback: function(cr){
                if (!cr.message || cr.message.error) {
                  msgEl.innerHTML = '<span class="text-danger">' + ((cr.message && cr.message.error) || "Could not confirm.") + '</span>';
                  return;
                }
                msgEl.innerHTML = '<span class="text-success">Confirmed! Refreshing&hellip;</span>';
                setTimeout(function(){ location.reload(); }, 1200);
              }
            });
          });
        }
      });
    });
  });

  document.querySelectorAll(".ism-detail-toggle").forEach(function(btn){
    btn.addEventListener("click", function(){
      var row = document.getElementById(btn.getAttribute("data-row"));
      if (!row) return;
      row.style.display = (row.style.display !== "none") ? "none" : "table-row";
    });
  });
});
</script>
"""


def run():
    print("=== Insert ISM appointment history (with outcomes/referrals) into profile ISM tab ===")
    html = (frappe.db.get_value("Web Page", PROFILE_PAGE, "main_section_html") or "").replace("\r\n", "\n")

    if "ismBookingHistory" in html:
        print("  [skip] ismBookingHistory block already present - not inserting a duplicate")
        return

    if ANCHOR not in html:
        raise RuntimeError("[FAIL] anchor (action-buttons / backToPersonal) not found - page structure changed")

    html = html.replace(ANCHOR, HISTORY_BLOCK + ANCHOR, 1)

    if DETAIL_JS not in html:
        html = html + DETAIL_JS

    frappe.db.set_value("Web Page", PROFILE_PAGE, "main_section_html", html, update_modified=True)
    frappe.db.commit()
    frappe.clear_cache()
    print("  [ok] history block inserted with outcome + referral detail, before the Back/Submit buttons")
    print("\nDone.")
'''

FILES['ism_v2_fix_tab_visibility.py'] = r'''"""
The ISM tab on the client profile page (client_profile_v3) must be visible at
ALL times for ALL registered service users (NISC enhancement doc, 30/07/2026).

The page's toggleTabsBasedOnStatusAndIntegration() JS function currently hides
the ISM nav item unless integration_support=="Yes" AND the client's course
status is in an old allowlist. Since registration no longer sets
integration_support, and course status has nothing to do with ISM eligibility,
this made the tab invisible for effectively everyone.

This patch replaces that function in place (operating on whatever is
currently stored, since it may have been hand-edited) so the ISM nav item is
always shown, while leaving the Course Selection tab's own status-driven
display logic untouched.

Run: bench --site ibelong.test execute ibelong_system.ism_v2_fix_tab_visibility.run
"""

import re

import frappe

PROFILE_PAGE = "v3-progle-page"

FUNC_START_MARKER = "function toggleTabsBasedOnStatusAndIntegration(){"

NEW_FUNCTION = """function toggleTabsBasedOnStatusAndIntegration(){
    var sf=getEl("clientStatus"),isf=getEl("integrationSupport");
    var ism=getEl("ism-tab"),crs=getEl("course-tab");
    var ismNI=ism&&ism.closest("li"),crsNI=crs&&crs.closest("li");
    var nxtBtn=getEl("nextToIsm"),bakBtn=getEl("backToIsm");
    if(!sf||!isf||!ismNI||!crsNI)return;
    var status=sf.value.trim();

    /* NISC enhancement (30/07/2026): the ISM tab must be visible at ALL times
       for ALL registered service users - ISM booking is fully independent of
       I Belong course status. Never hide it. */
    ismNI.style.display="block";

    /* Course Selection tab keeps its previous status-driven behaviour. */
    var ismPausedUntil=new Date('2026-07-27T00:00:00');
    var newFlowStatuses=["Registration Complete","Pending Eligibility Verification","Stage 1 Requirement Completed","Stage 1 Not Eligible"];
    crsNI.style.display="block";
    if(new Date()<ismPausedUntil || newFlowStatuses.includes(status)){
        if(bakBtn)bakBtn.style.display="none";
        if(nxtBtn)nxtBtn.style.display="none";
        return;
    }
    if(bakBtn)bakBtn.style.display="none";
    if(nxtBtn){nxtBtn.onclick=function(){new bootstrap.Tab(crs).show();};nxtBtn.style.display="inline-block";}
}"""


def _find_function_end(html, start):
    """Find the index just past the matching closing brace for the function
    starting at `start` (which points at 'function ...(){')."""
    open_brace = html.index("{", start)
    depth = 0
    i = open_brace
    while i < len(html):
        c = html[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise RuntimeError("Could not find matching closing brace")


def run():
    print("=== Fix ISM tab visibility on profile page ===")
    html = (frappe.db.get_value("Web Page", PROFILE_PAGE, "main_section_html") or "").replace("\r\n", "\n")

    if FUNC_START_MARKER not in html:
        raise RuntimeError("[FAIL] toggleTabsBasedOnStatusAndIntegration() not found - page structure changed")

    start = html.index(FUNC_START_MARKER)
    end = _find_function_end(html, start)
    old_func = html[start:end]

    if old_func.strip() == NEW_FUNCTION.strip():
        print("  [skip] function already matches the fixed version")
    else:
        html = html[:start] + NEW_FUNCTION + html[end:]
        frappe.db.set_value("Web Page", PROFILE_PAGE, "main_section_html", html, update_modified=True)
        print("  [ok] toggleTabsBasedOnStatusAndIntegration() replaced - ISM tab always visible now")

    frappe.db.commit()
    frappe.clear_cache()
    print("\nDone.")
'''

FILES['ism_v3_client_cards.py'] = r'''"""
Rebuild the "Your ISM Appointments" section on the client profile page
(client_profile_v3, Web Page 'v3-progle-page') as newest-first expandable
cards, covering every requirement in the NISC-managed-ISM spec:

  - Meeting Date, Meeting Time, ISM Officer, Current ISM Status (card header)
  - Support Requested, Outcome, Personal Integration Plan and Expected
    Outcomes, Follow-Up Notes, Referral Details/Status/Comments, OTP
    Confirmation Status (expanded card body)
  - additional_notes is NEVER shown (the backend never returns it)
  - newest booking first (Jinja |reverse over the child table)

Reuses the same widened ism_review.get_ism_review_summary() for BOTH the
"Review & Confirm" (Pending Client Review) and "View Details" (any other
status) expand actions - one API, one renderer, no duplicated logic.

This REPLACES the previous table-based ismBookingHistory block and its
associated <script>, wherever they currently are on the page (their exact
byte offsets may have shifted from earlier manual edits).

Run: bench --site ibelong.test execute ibelong_system.ism_v3_client_cards.run
"""

import frappe

PROFILE_PAGE = "v3-progle-page"

HISTORY_BLOCK_START = '<div class="mb-4" id="ismBookingHistory">'

NEW_HISTORY_BLOCK = """<div class="mb-4" id="ismBookingHistory">
                           <h6 class="mb-3"><i class="fas fa-history me-2"></i>Your ISM Appointments</h6>
                           {% if doc_data and doc_data.ism_bookings %}
                           {% for b in doc_data.ism_bookings|reverse %}
                           <div class="card mb-3 ism-card">
                              <div class="card-body">
                                 <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
                                    <div>
                                       <strong>{{ frappe.format_value(b.slot_date, {"fieldtype": "Date"}) if b.slot_date else "-" }}</strong>
                                       at {{ frappe.format_value(b.slot_time, {"fieldtype": "Time"}) if b.slot_time else "-" }}
                                       <span class="text-muted">&middot; Officer: {{ b.officer_name or "-" }}</span>
                                    </div>
                                    <div>
                                       {% if b.booking_status == "ISM Cancelled" %}<span class="badge bg-danger">{{ b.booking_status }}</span>
                                       {% elif b.booking_status == "Pending Client Review" %}<span class="badge bg-warning text-dark">{{ b.booking_status }}</span>
                                       {% elif b.booking_status == "Case Open" %}<span class="badge bg-info text-dark">{{ b.booking_status }}</span>
                                       {% elif b.booking_status == "Case Referred" %}<span class="badge" style="background-color:#6f42c1;color:#fff;">{{ b.booking_status }}</span>
                                       {% elif b.booking_status == "Case Closed" %}<span class="badge bg-secondary">{{ b.booking_status }}</span>
                                       {% else %}<span class="badge bg-primary">{{ b.booking_status or "ISM Scheduled" }}</span>{% endif %}
                                    </div>
                                 </div>
                                 <div class="mt-2">
                                    {% if b.booking_status == "Pending Client Review" %}
                                    <button type="button" class="btn btn-sm btn-outline-primary ism-expand" data-booking="{{ b.name }}" data-target="ismCardBody{{ loop.index }}">Review &amp; Confirm</button>
                                    {% elif b.booking_status in ("Case Open", "Case Referred", "Case Closed") %}
                                    <button type="button" class="btn btn-sm btn-outline-secondary ism-expand" data-booking="{{ b.name }}" data-target="ismCardBody{{ loop.index }}">View Details</button>
                                    {% endif %}
                                 </div>
                                 <div id="ismCardBody{{ loop.index }}" class="ism-card-body mt-3" style="display:none">
                                    <div class="ism-loading text-muted"><i class="fas fa-spinner fa-spin me-1"></i>Loading&hellip;</div>
                                    <div class="ism-content" style="display:none"></div>
                                 </div>
                              </div>
                           </div>
                           {% endfor %}
                           <p class="text-muted mb-0"><small>You may book more than one Integration Support Meeting. Each appointment and its outcome is listed here, newest first.</small></p>
                           {% else %}
                           <p class="text-muted mb-0">You have not booked an Integration Support Meeting yet.</p>
                           {% endif %}
                        </div>
                        """

NEW_JS = """
<script>
document.addEventListener("DOMContentLoaded", function(){
  function esc(s){ var d=document.createElement("div"); d.innerText=(s||""); return d.innerHTML; }

  function renderIsmDetail(d){
    var itemsHtml = "";
    (d.items || []).forEach(function(i){
      itemsHtml += "<li><strong>" + esc(i.label) + "</strong>" +
        (i.notes ? " - " + esc(i.notes) : "") +
        (i.referral_category ? " (Referral: " + esc(i.referral_category) + ")" : "") +
        "</li>";
    });
    if (!itemsHtml) itemsHtml = "<li>No specific support items recorded.</li>";

    var html = "";
    html += '<p class="mb-1"><strong>Outcome:</strong> ' + esc(d.booking_status) + '</p>';
    html += '<p class="mb-1"><strong>Support Requested</strong></p>';
    html += '<ul class="mb-3">' + itemsHtml + '</ul>';
    if (d.personal_integration_plan) {
      html += '<p class="mb-1"><strong>Personal Integration Plan and Expected Outcomes</strong></p><p class="mb-3">' + esc(d.personal_integration_plan) + '</p>';
    }
    if (d.follow_up) {
      html += '<p class="mb-1"><strong>Follow-Up Notes</strong></p><p class="mb-3">' + esc(d.follow_up) + '</p>';
    }
    if (d.referred_to_provider) {
      html += '<hr><p class="mb-1"><strong>Referral Details</strong></p>';
      html += '<p class="mb-1">Referred to: ' + esc(d.referred_to_provider) + '</p>';
      if (d.referral_status) html += '<p class="mb-1">Referral Status: <span class="badge bg-secondary">' + esc(d.referral_status) + '</span></p>';
      if (d.referral_comments) html += '<p class="mb-1">Referral Comments: ' + esc(d.referral_comments) + '</p>';
    }
    html += '<hr><p class="mb-0"><strong>OTP Confirmation:</strong> ' +
      (d.client_confirmed ? ('Confirmed' + (d.client_confirmed_on ? ' on ' + esc(d.client_confirmed_on) : '')) : 'Not yet confirmed') +
      '</p>';

    if (d.booking_status === "Pending Client Review") {
      html += '<hr><p class="mb-2">Enter the confirmation code we sent you by email to confirm this summary is correct.</p>';
      html += '<div class="row g-2 align-items-center">' +
        '<div class="col-auto"><input type="text" class="form-control form-control-sm ism-otp-input" placeholder="6-digit code" maxlength="6" style="width:140px"></div>' +
        '<div class="col-auto"><button type="button" class="btn btn-success btn-sm ism-otp-confirm">Confirm</button></div>' +
        '</div><div class="ism-otp-msg mt-2"></div>';
    }
    return html;
  }

  document.querySelectorAll(".ism-expand").forEach(function(btn){
    btn.addEventListener("click", function(){
      var target = document.getElementById(btn.getAttribute("data-target"));
      if (!target) return;
      var showing = target.style.display !== "none";
      if (showing) { target.style.display = "none"; return; }
      target.style.display = "block";
      if (target.getAttribute("data-loaded") === "1") return;

      var booking = btn.getAttribute("data-booking");
      var loading = target.querySelector(".ism-loading");
      var content = target.querySelector(".ism-content");

      frappe.call({
        method: "ibelong_system.ism_review.get_ism_review_summary",
        args: { booking: booking },
        callback: function(r){
          if (loading) loading.style.display = "none";
          if (!r.message || r.message.error) {
            content.innerHTML = '<p class="text-danger mb-0">' + ((r.message && r.message.error) || "Could not load this meeting.") + '</p>';
            content.style.display = "block";
            return;
          }
          var d = r.message;
          content.innerHTML = renderIsmDetail(d);
          content.style.display = "block";
          target.setAttribute("data-loaded", "1");

          var confirmBtn = content.querySelector(".ism-otp-confirm");
          if (confirmBtn) {
            confirmBtn.addEventListener("click", function(){
              var otpVal = content.querySelector(".ism-otp-input").value.trim();
              var msgEl = content.querySelector(".ism-otp-msg");
              if (!otpVal) { msgEl.innerHTML = '<span class="text-danger">Please enter the code.</span>'; return; }
              frappe.call({
                method: "ibelong_system.ism_review.confirm_ism_review",
                args: { booking: booking, otp: otpVal },
                callback: function(cr){
                  if (!cr.message || cr.message.error) {
                    msgEl.innerHTML = '<span class="text-danger">' + ((cr.message && cr.message.error) || "Could not confirm.") + '</span>';
                    return;
                  }
                  msgEl.innerHTML = '<span class="text-success">Confirmed! Refreshing&hellip;</span>';
                  setTimeout(function(){ location.reload(); }, 1200);
                }
              });
            });
          }
        }
      });
    });
  });
});
</script>
"""


def _find_div_end(html, start):
    depth = 0
    i = start
    while i < len(html):
        if html.startswith("<div", i):
            depth += 1
            i += 4
            continue
        if html.startswith("</div>", i):
            depth -= 1
            i += 6
            if depth == 0:
                return i
            continue
        i += 1
    raise RuntimeError("could not find matching </div>")


def _strip_old_scripts(html):
    """Remove any previously-appended ISM history <script> blocks (old
    table-based versions used '.ism-review-toggle' / '.ism-detail-toggle'
    listeners) so we don't end up with duplicate/dead event bindings."""
    markers = ['document.querySelectorAll(".ism-review-toggle")', 'document.querySelectorAll(".ism-detail-toggle")']
    changed = True
    while changed:
        changed = False
        for marker in markers:
            idx = html.find(marker)
            if idx == -1:
                continue
            script_start = html.rfind("<script>", 0, idx)
            script_end = html.find("</script>", idx)
            if script_start == -1 or script_end == -1:
                continue
            script_end += len("</script>")
            html = html[:script_start] + html[script_end:]
            changed = True
    return html


def run():
    print("=== Rebuild ISM history as newest-first cards ===")
    html = (frappe.db.get_value("Web Page", PROFILE_PAGE, "main_section_html") or "").replace("\r\n", "\n")

    if HISTORY_BLOCK_START not in html:
        raise RuntimeError("[FAIL] ismBookingHistory block not found - page structure changed")

    start = html.index(HISTORY_BLOCK_START)
    end = _find_div_end(html, start)
    html = html[:start] + NEW_HISTORY_BLOCK + html[end:]
    print("  [ok] history block replaced with card layout")

    html = _strip_old_scripts(html)
    print("  [ok] old ISM history <script> block(s) removed")

    html = html + NEW_JS
    print("  [ok] new unified detail/expand script appended")

    frappe.db.set_value("Web Page", PROFILE_PAGE, "main_section_html", html, update_modified=True)
    frappe.db.commit()
    frappe.clear_cache()
    print("\nDone.")
'''

FILES['ism_v3_remove_client_otp_entry.py'] = r'''"""
Remove the client-side OTP entry from the profile page. Per the confirmed
real-world flow, the client reads the code back to the NISC officer verbally
- they never type it into their own portal. Staff verify it via the desk
"Verify OTP" button (ism_review.py + Course Assigned Client Script), which
was already built and is unaffected by this change.

Two edits to v3-progle-page:
  1. renderIsmDetail(): drop the OTP input + Confirm button block that only
     rendered for "Pending Client Review".
  2. The expand-click handler's dead .ism-otp-confirm wiring is removed too,
     since renderIsmDetail() will never emit that markup anymore.
  3. Jinja: "Pending Client Review" now gets the same "View Details" button
     as Case Open/Referred/Closed, instead of a distinct "Review & Confirm"
     label implying a client action that no longer exists.

Run: bench --site ibelong.test execute ibelong_system.ism_v3_remove_client_otp_entry.run
"""

import frappe

PROFILE_PAGE = "v3-progle-page"

OLD_JINJA = (
    '{% if b.booking_status == "Pending Client Review" %}\n'
    '                                    <button type="button" class="btn btn-sm btn-outline-primary ism-expand" data-booking="{{ b.name }}" data-target="ismCardBody{{ loop.index }}">Review &amp; Confirm</button>\n'
    '                                    {% elif b.booking_status in ("Case Open", "Case Referred", "Case Closed") %}\n'
    '                                    <button type="button" class="btn btn-sm btn-outline-secondary ism-expand" data-booking="{{ b.name }}" data-target="ismCardBody{{ loop.index }}">View Details</button>\n'
    '                                    {% endif %}'
)
NEW_JINJA = (
    '{% if b.booking_status in ("Pending Client Review", "Case Open", "Case Referred", "Case Closed") %}\n'
    '                                    <button type="button" class="btn btn-sm btn-outline-secondary ism-expand" data-booking="{{ b.name }}" data-target="ismCardBody{{ loop.index }}">View Details</button>\n'
    '                                    {% endif %}'
)

OLD_JS_OTP_BLOCK = """
    if (d.booking_status === "Pending Client Review") {
      html += '<hr><p class="mb-2">Enter the confirmation code we sent you by email to confirm this summary is correct.</p>';
      html += '<div class="row g-2 align-items-center">' +
        '<div class="col-auto"><input type="text" class="form-control form-control-sm ism-otp-input" placeholder="6-digit code" maxlength="6" style="width:140px"></div>' +
        '<div class="col-auto"><button type="button" class="btn btn-success btn-sm ism-otp-confirm">Confirm</button></div>' +
        '</div><div class="ism-otp-msg mt-2"></div>';
    }
    return html;
  }"""
NEW_JS_NO_OTP_BLOCK = """
    return html;
  }"""

OLD_JS_CONFIRM_WIRING = """
          var confirmBtn = content.querySelector(".ism-otp-confirm");
          if (confirmBtn) {
            confirmBtn.addEventListener("click", function(){
              var otpVal = content.querySelector(".ism-otp-input").value.trim();
              var msgEl = content.querySelector(".ism-otp-msg");
              if (!otpVal) { msgEl.innerHTML = '<span class="text-danger">Please enter the code.</span>'; return; }
              frappe.call({
                method: "ibelong_system.ism_review.confirm_ism_review",
                args: { booking: booking, otp: otpVal },
                callback: function(cr){
                  if (!cr.message || cr.message.error) {
                    msgEl.innerHTML = '<span class="text-danger">' + ((cr.message && cr.message.error) || "Could not confirm.") + '</span>';
                    return;
                  }
                  msgEl.innerHTML = '<span class="text-success">Confirmed! Refreshing&hellip;</span>';
                  setTimeout(function(){ location.reload(); }, 1200);
                }
              });
            });
          }
        }"""
NEW_JS_NO_CONFIRM_WIRING = """
        }"""


def run():
    print("=== Remove client-side OTP entry from profile page ===")
    html = (frappe.db.get_value("Web Page", PROFILE_PAGE, "main_section_html") or "").replace("\r\n", "\n")

    changed = []

    if OLD_JINJA in html:
        html = html.replace(OLD_JINJA, NEW_JINJA, 1)
        changed.append("Jinja button unified to 'View Details'")
    elif NEW_JINJA in html:
        print("  [skip] Jinja button already unified")
    else:
        raise RuntimeError("[FAIL] expected Jinja button markup not found - page structure changed")

    if OLD_JS_OTP_BLOCK in html:
        html = html.replace(OLD_JS_OTP_BLOCK, NEW_JS_NO_OTP_BLOCK, 1)
        changed.append("renderIsmDetail() OTP block removed")
    elif NEW_JS_NO_OTP_BLOCK in html and "ism-otp-input" not in html:
        print("  [skip] renderIsmDetail() OTP block already removed")
    else:
        raise RuntimeError("[FAIL] expected JS OTP block not found - page structure changed")

    if OLD_JS_CONFIRM_WIRING in html:
        html = html.replace(OLD_JS_CONFIRM_WIRING, NEW_JS_NO_CONFIRM_WIRING, 1)
        changed.append("dead .ism-otp-confirm wiring removed")
    elif "ism-otp-confirm" not in html:
        print("  [skip] confirm-wiring already removed")
    else:
        raise RuntimeError("[FAIL] expected JS confirm-wiring block not found - page structure changed")

    if changed:
        frappe.db.set_value("Web Page", PROFILE_PAGE, "main_section_html", html, update_modified=True)
        frappe.db.commit()
        frappe.clear_cache()
        print("  [ok]", "; ".join(changed))
    print("\nDone.")
'''

FILES['ism_v3_fix_filenumber.py'] = r'''"""
Fix "Client Details FN-12345 not found" on the v3 profile page's Course
Selection tab.

Root cause: the readonly #fileNumber input defaults its VALUE (not just
placeholder text) to the literal string "FN-12345" whenever
doc_data.file_number is empty. JS then reads that fake value and submits it
to submit_stage1_certificate / submit_stage2_culture_only as `fileno`, which
fails both of the server's lookups (file_number match, or fileno-as-docname).

Fix: fall back to doc_data.name (the client's real docname) instead of a
fake placeholder. The server-side handlers already support using the docname
directly as `fileno` (frappe.db.exists("Client Details", fileno)), so this
resolves cleanly - and Stage 2's handler even self-heals by writing that
value back as the client's file_number.

Unrelated to ISM/registration - this only touches the Course Selection tab's
File Number field.

Run: bench --site ibelong.test execute ibelong_system.ism_v3_fix_filenumber.run
"""

import frappe

PROFILE_PAGE = "v3-progle-page"

OLD = '{% if doc_data and doc_data.file_number %}{{ doc_data.file_number }}{% else %}FN-12345{% endif %}" readonly /></div>'
NEW = '{% if doc_data and doc_data.file_number %}{{ doc_data.file_number }}{% else %}{{ doc_data.name }}{% endif %}" readonly /></div>'


def run():
    print("=== Fix File Number fake-placeholder bug ===")
    html = (frappe.db.get_value("Web Page", PROFILE_PAGE, "main_section_html") or "").replace("\r\n", "\n")

    if OLD not in html:
        if NEW in html:
            print("  [skip] already fixed")
            return
        raise RuntimeError("[FAIL] expected pattern not found - page structure changed")

    html = html.replace(OLD, NEW, 1)
    frappe.db.set_value("Web Page", PROFILE_PAGE, "main_section_html", html, update_modified=True)
    frappe.db.commit()
    frappe.clear_cache()
    print("  [ok] File Number now falls back to the client's real docname instead of a fake placeholder")
    print("\nDone.")
'''

FILES['ism_v3_fix_filenumber2.py'] = r'''"""
Second instance of the File Number empty-value bug: the small "client-id"
badge under the client's name (id="clientIdDisplay") shows doc_data.file_number
with NO fallback at all, so it renders as an empty badge/dot when file_number
is unset - which is what showed up as an empty purple dot on the profile page.

Same fix as ism_v3_fix_filenumber.py: fall back to doc_data.name (the real
client docname) so the badge always shows something meaningful.

Run: bench --site ibelong.test execute ibelong_system.ism_v3_fix_filenumber2.run
"""

import frappe

PROFILE_PAGE = "v3-progle-page"

OLD = '<span class="client-id" id="clientIdDisplay">{% if doc_data and doc_data.file_number %}{{ doc_data.file_number }}{% endif %}</span>'
NEW = '<span class="client-id" id="clientIdDisplay">{% if doc_data and doc_data.file_number %}{{ doc_data.file_number }}{% elif doc_data %}{{ doc_data.name }}{% endif %}</span>'


def run():
    print("=== Fix second File Number empty-badge bug (clientIdDisplay) ===")
    html = (frappe.db.get_value("Web Page", PROFILE_PAGE, "main_section_html") or "").replace("\r\n", "\n")

    if OLD not in html:
        if NEW in html:
            print("  [skip] already fixed")
            return
        raise RuntimeError("[FAIL] expected pattern not found - page structure changed")

    html = html.replace(OLD, NEW, 1)
    frappe.db.set_value("Web Page", PROFILE_PAGE, "main_section_html", html, update_modified=True)
    frappe.db.commit()
    frappe.clear_cache()
    print("  [ok] clientIdDisplay now falls back to the client's real docname")
    print("\nDone.")
'''

FILES['ism_v3_hide_legacy_otp_fields.py'] = r'''"""
Hide the last remnants of the old, pre-restructure single-ISM OTP mechanism
on the Client Details "Declaration and Client Acceptance" tab:
  - one_time_password_for_confirmation (visible input)
  - verify_otp_button (visible button)

Their handler lived in the "Language Fluency" Client Script, which has just
been disabled - so this button is now dead (clicking it does nothing), which
is more confusing than helpful sitting there. This mechanism operated on
Client Details.status directly and isn't per-booking, so it's fully
superseded by the "Send OTP" / "Verify OTP" buttons in the Actions menu
(ism_review.py + the "Course Assigned" Client Script).

declarations_per_tender_document ("Declarations accepted by client") is left
untouched - unrelated general declaration field, not part of the OTP flow.

Both fields are core DocField entries on Client Details (not Custom Fields),
so this edits the DocType directly.

Run: bench --site ibelong.test execute ibelong_system.ism_v3_hide_legacy_otp_fields.run
"""

import frappe

FIELDS_TO_HIDE = ["one_time_password_for_confirmation", "verify_otp_button"]


def run():
    print("=== Hide legacy single-ISM OTP fields on Client Details ===")
    dt = frappe.get_doc("DocType", "Client Details")
    changed = []
    for f in dt.fields:
        if f.fieldname in FIELDS_TO_HIDE and not f.hidden:
            f.hidden = 1
            changed.append(f.fieldname)

    if changed:
        dt.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.clear_cache()
        print(f"  [ok] hidden: {changed}")
    else:
        print("  [skip] already hidden")

    print("\nDone.")
'''

FILES['ism_v3_send_verify_otp.py'] = r'''"""
Real-world ISM confirmation flow, per live testing feedback: the client does
NOT type the OTP into their own portal. Instead, the officer sends the OTP,
the client reads it back to the officer (in person / over the phone) as their
way of agreeing to the ISM form, and the OFFICER types it into the desk to
verify it. On a correct OTP, the booking goes straight to Case Open / Case
Referred (per the referral logic already built) - "Meeting Attended" is not
reintroduced, matching the original written spec.

Updates the "Course Assigned" Client Script (Client Details) to show, per
ism_bookings row:
  - "Send OTP"   - rows in "ISM Scheduled" (first send) or
                   "Pending Client Review" (resend, e.g. code expired) -
                   calls the already-widened ism_review.submit_for_client_review
  - "Verify OTP" - rows in "Pending Client Review" - opens a small dialog for
                   the officer to enter the code the client relayed, calls
                   ism_review.confirm_ism_review (already permits staff, not
                   just the owning client - no backend change needed there)

Client Details.status is still never touched - only booking_status on the
relevant ISM Booking row changes, exactly as before.

Run: bench --site ibelong.test execute ibelong_system.ism_v3_send_verify_otp.run
"""

import frappe

CS_NAME = "Course Assigned"

NEW_SCRIPT = """frappe.ui.form.on("Client Details", {
    refresh(frm) {
        // Disable renaming when form loads
        //disable_title_click();

        _add_ism_action_buttons(frm);
    },

    // refresh(frm) {
    //     // Title might get re-rendered on refresh — disable rename again
    //     setTimeout(disable_title_click, 50);
    // },
});

// ISM actions - never touch Client Details.status, only the relevant
// ism_bookings row's booking_status.
//
// "Send OTP"   shown for a row in "ISM Scheduled" (first send) or
//              "Pending Client Review" (resend).
// "Verify OTP" shown for a row in "Pending Client Review" - the client reads
//              the code back to the officer, who enters it here to confirm.
//              A correct code moves the row straight to Case Open / Case
//              Referred (never "Meeting Attended").
function _add_ism_action_buttons(frm) {
    if (frm.is_new()) return;

    (frm.doc.ism_bookings || []).forEach(function(row) {
        var tag = row.slot_date ? ' (' + row.slot_date + ')' : '';

        if (row.booking_status === "ISM Scheduled" || row.booking_status === "Pending Client Review") {
            frm.add_custom_button(__('Send OTP{0}', [tag]), function () {
                frappe.confirm(
                    __('Send the confirmation code to the client for this ISM meeting?'),
                    () => {
                        frappe.call({
                            method: "ibelong_system.ism_review.submit_for_client_review",
                            args: { booking: row.name },
                            freeze: true,
                            callback: function (r) {
                                if (r.exc) return;
                                frappe.show_alert({
                                    message: __("Confirmation code sent to the client"),
                                    indicator: "green",
                                });
                                frm.reload_doc();
                            },
                        });
                    }
                );
            }, __('Actions'));
        }

        if (row.booking_status === "Pending Client Review") {
            frm.add_custom_button(__('Verify OTP{0}', [tag]), function () {
                var d = new frappe.ui.Dialog({
                    title: __('Verify OTP'),
                    fields: [
                        {
                            fieldname: 'otp',
                            fieldtype: 'Data',
                            label: __('Code the client read back to you'),
                            reqd: 1,
                        },
                    ],
                    primary_action_label: __('Verify'),
                    primary_action(values) {
                        frappe.call({
                            method: "ibelong_system.ism_review.confirm_ism_review",
                            args: { booking: row.name, otp: values.otp },
                            freeze: true,
                            callback: function (r) {
                                if (!r.message || r.message.error) {
                                    frappe.msgprint(__((r.message && r.message.error) || 'Could not verify this code.'));
                                    return;
                                }
                                d.hide();
                                frappe.show_alert({
                                    message: __('Verified - status updated to {0}', [r.message.new_status]),
                                    indicator: 'green',
                                });
                                frm.reload_doc();
                            },
                        });
                    },
                });
                d.show();
            }, __('Actions'));
        }
    });
}

// 🚫 Prevent renaming from the form title
// function disable_title_click() {
//     const $titleArea = $(".page-title .title-area.editable-title");
//     if (!$titleArea.length) return;

//     $titleArea.off("click");
//     $titleArea.find(".title-text").off("click dblclick");

//     $titleArea.on("click", function (e) {
//         e.stopImmediatePropagation();
//         e.preventDefault();
//     });

//     $titleArea.find(".title-text")
//         .css("cursor", "default")
//         .attr("title", "Renaming disabled");
// }
"""


def run():
    print("=== Add Send OTP + Verify OTP buttons (Course Assigned script) ===")
    if not frappe.db.exists("Client Script", CS_NAME):
        raise RuntimeError(f"[FAIL] Client Script '{CS_NAME}' not found")

    doc = frappe.get_doc("Client Script", CS_NAME)
    doc.script = NEW_SCRIPT
    doc.enabled = 1
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    frappe.clear_cache()
    print(f"  [ok] '{CS_NAME}' updated with Send OTP / Verify OTP buttons")
    print("\nDone.")
'''

FILES['ism_v3_one_active_case.py'] = r'''"""
Client clarification (07/08/2026): only one ACTIVE ISM case at a time.
A client may book multiple ISMs over time, but the ISM tab must be hidden
on their profile while a case is active (anything except Case Closed or
ISM Cancelled), and reappear once the active case is closed - allowing a
new booking. The client profile itself always stays accessible; only the
ISM tab is gated.

Two edits to v3-progle-page:
  1. Compute has_active_ism server-side (Jinja) and expose it via a hidden
     input, matching the existing #clientStatus / #integrationSupport
     pattern already read by toggleTabsBasedOnStatusAndIntegration().
  2. That JS function now hides the ISM nav tab when has_active_ism is true,
     instead of always showing it.
  3. Defensive click-guard on the "Book ISM Session" link: if somehow
     reached with an active case (stale cache, direct URL, etc.), show an
     alert instead of navigating to the external MS Bookings page.

Run: bench --site ibelong.test execute ibelong_system.ism_v3_one_active_case.run
"""

import frappe

PROFILE_PAGE = "v3-progle-page"

# --- 1. hidden field with the server-computed flag ---------------------------
ANCHOR_HIDDEN_FIELD = (
    'id="integrationSupport" value="{% if doc_data and doc_data.integration_support %}'
    'Yes{% else %}No{% endif %}" readonly /></div>'
)
NEW_HIDDEN_FIELD = ANCHOR_HIDDEN_FIELD + (
    '\n{% set ns = namespace(has_active_ism=false) %}'
    '{% if doc_data and doc_data.ism_bookings %}{% for b in doc_data.ism_bookings %}'
    '{% if b.booking_status not in ("Case Closed", "ISM Cancelled") %}{% set ns.has_active_ism = true %}{% endif %}'
    '{% endfor %}{% endif %}'
    '<input type="hidden" id="hasActiveIsm" value="{% if ns.has_active_ism %}Yes{% else %}No{% endif %}" />'
)

# --- 2. tab-visibility JS -----------------------------------------------------
OLD_JS_TAB_LINE = (
    '    /* NISC enhancement (30/07/2026): the ISM tab must be visible at ALL times\n'
    '       for ALL registered service users - ISM booking is fully independent of\n'
    '       I Belong course status. Never hide it. */\n'
    '    ismNI.style.display="block";'
)
NEW_JS_TAB_LINE = (
    '    /* NISC enhancement (30/07/2026): the ISM tab is visible at ALL times\n'
    '       for ALL registered service users - ISM booking is fully independent of\n'
    '       I Belong course status - EXCEPT while the client has an active ISM case\n'
    '       (client clarification 07/08/2026: only one active case at a time). */\n'
    '    var hasActiveIsmEl=getEl("hasActiveIsm");\n'
    '    var hasActiveIsm=hasActiveIsmEl&&hasActiveIsmEl.value.trim()==="Yes";\n'
    '    ismNI.style.display=hasActiveIsm?"none":"block";'
)

# --- 3. defensive popup on the Book ISM Session link --------------------------
BOOK_BTN_MARKER = 'class="btn btn-primary btn-lg" style="background-color: #6f42c1; border-color: #6f42c1; padding: 12px 30px; font-size: 1.1rem;"><i class="fas fa-external-link-alt me-2"></i>Book ISM Session</a>'

GUARD_SCRIPT = """
<script>
document.addEventListener("DOMContentLoaded", function(){
  document.querySelectorAll('a.btn-primary').forEach(function(a){
    if (a.textContent.indexOf("Book ISM Session") === -1) return;
    a.addEventListener("click", function(e){
      var flag = document.getElementById("hasActiveIsm");
      if (flag && flag.value.trim() === "Yes") {
        e.preventDefault();
        alert("Please complete your current active ISM meeting first.");
      }
    });
  });
});
</script>
"""


def run():
    print("=== One active ISM case at a time: tab gating ===")
    html = (frappe.db.get_value("Web Page", PROFILE_PAGE, "main_section_html") or "").replace("\r\n", "\n")

    if ANCHOR_HIDDEN_FIELD in html:
        html = html.replace(ANCHOR_HIDDEN_FIELD, NEW_HIDDEN_FIELD, 1)
        print("  [ok] hasActiveIsm hidden field added")
    elif 'id="hasActiveIsm"' in html:
        print("  [skip] hasActiveIsm field already present")
    else:
        raise RuntimeError("[FAIL] integrationSupport field anchor not found")

    if OLD_JS_TAB_LINE in html:
        html = html.replace(OLD_JS_TAB_LINE, NEW_JS_TAB_LINE, 1)
        print("  [ok] toggleTabsBasedOnStatusAndIntegration() now gates on has_active_ism")
    elif "hasActiveIsm" in html and 'ismNI.style.display=hasActiveIsm' in html:
        print("  [skip] tab-gating JS already updated")
    else:
        raise RuntimeError("[FAIL] expected JS tab-visibility block not found")

    if BOOK_BTN_MARKER in html and GUARD_SCRIPT not in html:
        html = html + GUARD_SCRIPT
        print("  [ok] defensive popup script added to Book ISM Session button")
    elif GUARD_SCRIPT in html:
        print("  [skip] defensive popup script already present")
    else:
        raise RuntimeError("[FAIL] Book ISM Session button marker not found")

    frappe.db.set_value("Web Page", PROFILE_PAGE, "main_section_html", html, update_modified=True)
    frappe.db.commit()
    frappe.clear_cache()
    print("\nDone.")
'''

FILES['verify_deployment.py'] = r'''"""
Verification script - run on the test env after deploy_ism.sh completes.
bench --site <SITE> execute ibelong_system.verify_deployment.run
"""
import frappe

def run():
    print("=== ISM deployment verification ===\n")

    checks = []

    checks.append(("ISM Booking doctype exists", frappe.db.exists("DocType", "ISM Booking")))
    checks.append(("Client Details has ism_bookings field", bool(frappe.get_meta("Client Details").get_field("ism_bookings"))))
    checks.append(("ISM Booking has booking_status field", bool(frappe.get_meta("ISM Booking").get_field("booking_status"))))

    bs = frappe.get_meta("ISM Booking").get_field("booking_status")
    expected_statuses = {"ISM Scheduled", "ISM Cancelled", "Pending Client Review", "Case Open", "Case Referred", "Case Closed"}
    actual_statuses = set((bs.options or "").split("\n")) if bs else set()
    checks.append(("booking_status has correct new vocabulary", expected_statuses.issubset(actual_statuses)))

    checks.append(("ism_review module importable", True))
    try:
        from ibelong_system import ism_review
        checks.append(("ism_review.submit_for_client_review exists", hasattr(ism_review, "submit_for_client_review")))
        checks.append(("ism_review.confirm_ism_review exists", hasattr(ism_review, "confirm_ism_review")))
        checks.append(("ism_review.validate_client_details exists", hasattr(ism_review, "validate_client_details")))
    except ImportError as e:
        checks.append((f"ism_review module import FAILED: {e}", False))

    import ibelong_system.hooks as hooks
    doc_events = getattr(hooks, "doc_events", {})
    checks.append(("hooks.py doc_events has Client Details validate hook",
        doc_events.get("Client Details", {}).get("validate") == "ibelong_system.ism_review.validate_client_details"))

    cs = frappe.db.get_value("Client Script", "Course Assigned", ["enabled", "script"], as_dict=True)
    checks.append(("Course Assigned script has Send OTP button", bool(cs and "Send OTP" in (cs.script or ""))))
    checks.append(("Course Assigned script has Verify OTP button", bool(cs and "Verify OTP" in (cs.script or ""))))

    lf = frappe.db.get_value("Client Script", "Language Fluency", "enabled")
    checks.append(("Legacy 'Language Fluency' script disabled (or absent)", lf in (0, None)))

    html = frappe.db.get_value("Web Page", "v3-progle-page", "main_section_html") or ""
    checks.append(("Profile page has hasActiveIsm gating field", "hasActiveIsm" in html))
    checks.append(("Profile page has ISM appointment cards", "ism-card" in html))
    checks.append(("Profile page has no client-side OTP entry (removed)", "ism-otp-input" not in html))
    checks.append(("File Number fallback fix applied (input)", "FN-12345" not in html))

    from ibelong_system import get_booking_data
    import inspect
    src = inspect.getsource(get_booking_data.create_client)
    checks.append(("create_client has duplicate-booking guard", "existing_active" in src))
    checks.append(("create_client does NOT set doc.status", "doc.status =" not in src))

    print("RESULTS:")
    passed = 0
    for label, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'} - {label}")
        if ok:
            passed += 1
    print(f"\n{passed}/{len(checks)} checks passed")
'''


HOOKS_ENTRY_MARKER = "ibelong_system.ism_review.validate_client_details"
HOOKS_ANCHOR = 'doc_events = {'


def _patch_hooks():
    hooks_path = os.path.join(APP_DIR, "hooks.py")
    with open(hooks_path) as fh:
        content = fh.read()

    if HOOKS_ENTRY_MARKER in content:
        print("  [skip] hooks.py already has the Client Details validate hook")
        return

    entry = (
        '    "Client Details": {\n'
        '        "validate": "ibelong_system.ism_review.validate_client_details"\n'
        '    },\n'
    )

    if HOOKS_ANCHOR in content:
        content = content.replace(HOOKS_ANCHOR, HOOKS_ANCHOR + "\n" + entry, 1)
        print("  [ok] added Client Details validate hook to existing doc_events dict")
    else:
        content = content.rstrip() + (
            "\n\ndoc_events = {\n" + entry + "}\n"
        )
        print("  [ok] doc_events dict did not exist - created it with the validate hook")

    with open(hooks_path, "w") as fh:
        fh.write(content)


def run():
    print("=== ISM deploy-all: writing files ===")
    for fname, content in FILES.items():
        path = os.path.join(APP_DIR, fname)
        with open(path, "w") as fh:
            fh.write(content)
        print(f"  wrote {fname} ({len(content)} chars)")

    print("\n=== Patching hooks.py ===")
    _patch_hooks()

    print("\n=== Running migrations in order ===")

    print("--- ism_phase2 ---")
    importlib.import_module("ibelong_system.ism_phase2").run()

    print("--- ism_multi_schema_only ---")
    importlib.import_module("ibelong_system.ism_multi_schema_only").run()

    print("--- ism_v2_booking_fields ---")
    importlib.import_module("ibelong_system.ism_v2_booking_fields").run()

    print("--- ism_portal_support ---")
    importlib.import_module("ibelong_system.ism_portal_support").run()

    print("--- ism_v2_insert_history ---")
    importlib.import_module("ibelong_system.ism_v2_insert_history").run()

    print("--- ism_v2_fix_tab_visibility ---")
    importlib.import_module("ibelong_system.ism_v2_fix_tab_visibility").run()

    print("--- ism_v3_client_cards ---")
    importlib.import_module("ibelong_system.ism_v3_client_cards").run()

    print("--- ism_v3_remove_client_otp_entry ---")
    importlib.import_module("ibelong_system.ism_v3_remove_client_otp_entry").run()

    print("--- ism_v3_fix_filenumber ---")
    importlib.import_module("ibelong_system.ism_v3_fix_filenumber").run()

    print("--- ism_v3_fix_filenumber2 ---")
    importlib.import_module("ibelong_system.ism_v3_fix_filenumber2").run()

    print("--- ism_v3_hide_legacy_otp_fields ---")
    importlib.import_module("ibelong_system.ism_v3_hide_legacy_otp_fields").run()

    print("--- ism_v3_send_verify_otp ---")
    importlib.import_module("ibelong_system.ism_v3_send_verify_otp").run()

    print("--- ism_v3_one_active_case ---")
    importlib.import_module("ibelong_system.ism_v3_one_active_case").run()


    print("\n=== Disabling legacy 'Language Fluency' script if present ===")
    if frappe.db.exists("Client Script", "Language Fluency"):
        frappe.db.set_value("Client Script", "Language Fluency", "enabled", 0)
        frappe.db.commit()
        print("  [ok] disabled")
    else:
        print("  [skip] not found")

    frappe.clear_cache()

    print("\n=== Running verification ===")
    importlib.import_module("ibelong_system.verify_deployment").run()

    print("\nAll done.")
