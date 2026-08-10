"""
Batch 3 (schema + backfill) - allow MULTIPLE ISM bookings per client.

  1. Create child DocType "ISM Booking" (one row per appointment).
  2. Add Table field `ism_bookings` to Client Details (in the ISM slot section).
  3. Backfill: every client that already has a single-field ISM booking
     (migrated data) gets one row created from those fields, so nothing is lost
     and existing bookings show up in the new list. Existing single fields are
     kept untouched.

The MS Bookings webhook change (append a row per booking) is applied separately
in get_booking_data.py.

Run: bench --site ibelong.test execute ibelong_system.ism_multi.run
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CHILD = "ISM Booking"

STATUS_MAP = {
    "ISM Meeting Scheduled": "Scheduled",
    "ISM Meeting Rescheduled": "Rescheduled",
    "Meeting Attended": "Attended",
    "Meeting Not Attended": "Not Attended",
    "Meeting Cancelled": "Cancelled",
    "Pending Client Review": "Pending Review",
}


def ensure_child_doctype():
    if frappe.db.exists("DocType", CHILD):
        print(f"  [skip] DocType '{CHILD}' already exists")
        return
    module = frappe.db.get_value("DocType", "Client Referral", "module") or "Ibelong"
    dt = frappe.get_doc({
        "doctype": "DocType",
        "name": CHILD,
        "module": module,
        "custom": 1,
        "istable": 1,
        "editable_grid": 1,
        "fields": [
            {"fieldname": "slot_date", "fieldtype": "Date", "label": "ISM Date", "in_list_view": 1, "columns": 2},
            {"fieldname": "slot_time", "fieldtype": "Time", "label": "ISM Time", "in_list_view": 1, "columns": 2},
            {"fieldname": "officer_name", "fieldtype": "Data", "label": "Officer", "in_list_view": 1, "columns": 2},
            {"fieldname": "booking_status", "fieldtype": "Select", "label": "Status",
             "options": "Scheduled\nRescheduled\nAttended\nNot Attended\nCancelled\nPending Review",
             "in_list_view": 1, "columns": 2},
            {"fieldname": "support_need", "fieldtype": "Data", "label": "Support Need", "in_list_view": 1, "columns": 2},
            {"fieldname": "remarks", "fieldtype": "Small Text", "label": "Remarks"},
        ],
        "permissions": [],
    })
    dt.insert(ignore_permissions=True)
    print(f"  [ok] created child DocType '{CHILD}' (module={module})")


def ensure_table_field():
    create_custom_fields({
        "Client Details": [
            {"fieldname": "ism_bookings", "label": "ISM Bookings", "fieldtype": "Table",
             "options": CHILD, "insert_after": "selected_time"},
        ]
    }, update=True)
    print("  [ok] Client Details.ism_bookings table field ensured")


def backfill():
    names = frappe.get_all("Client Details", filters={"ism_slot": ["is", "set"]}, pluck="name")
    print(f"  clients with an existing ISM slot: {len(names)}")
    created = 0
    for name in names:
        # skip if this client already has any ism_bookings rows
        if frappe.db.exists("ISM Booking", {"parent": name, "parenttype": "Client Details", "parentfield": "ism_bookings"}):
            continue
        d = frappe.db.get_value(
            "Client Details", name,
            ["ism_slot", "selected_time", "ism_slot_time", "isr_officer_name", "isr_status", "ism_support_need"],
            as_dict=True,
        )
        # insert child row directly (no parent re-save -> no parent hooks/side effects)
        frappe.get_doc({
            "doctype": "ISM Booking",
            "parenttype": "Client Details",
            "parent": name,
            "parentfield": "ism_bookings",
            "idx": 1,
            "slot_date": d.ism_slot,
            "slot_time": d.selected_time or d.ism_slot_time,
            "officer_name": d.isr_officer_name,
            "booking_status": STATUS_MAP.get(d.isr_status, "Scheduled"),
            "support_need": d.ism_support_need,
            "remarks": "Migrated from existing single-field booking.",
        }).insert(ignore_permissions=True)
        created += 1
    print(f"  [ok] backfilled {created} migrated booking row(s)")


def run():
    print("=== Batch 3 schema + backfill: multiple ISM bookings ===")
    ensure_child_doctype()
    ensure_table_field()
    frappe.db.commit()
    frappe.clear_cache()
    backfill()
    frappe.db.commit()
    print("\nDone. Child table + field ready; migrated bookings preserved.")
