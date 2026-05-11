import frappe
from frappe.utils import getdate, get_time
from datetime import datetime
import pytz


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

        doc.isr_officer_name = officer_name
        doc.ism_slot = ism_slot_date
        doc.selected_time = ism_slot_time
        doc.isr_status = "ISM Meeting Scheduled"
        doc.status = "ISM Meeting Scheduled"

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

        doc.isr_officer_name = officer_name
        doc.ism_slot = ism_slot_date
        doc.ism_slot_time = ism_slot_time
        doc.isr_status = "ISM Meeting Rescheduled"
        doc.status = "ISM Meeting Rescheduled"

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
        # CANCEL STATUS (ALWAYS SET)
        # -----------------------------
        doc.status = "Meeting Cancelled"
        doc.isr_status = "Meeting Cancelled"

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
