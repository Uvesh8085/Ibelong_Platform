import frappe
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
