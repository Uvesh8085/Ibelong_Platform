"""
Map existing ISM Booking.booking_status values (old vocabulary) onto the new
NISC-enhancement vocabulary so migrated rows don't show as invalid/blank.

  Scheduled      -> ISM Scheduled
  Rescheduled    -> ISM Scheduled       (still just a booked meeting)
  Cancelled      -> ISM Cancelled
  Pending Review -> Pending Client Review
  Attended       -> Case Open           (best-effort: no case data exists for
                                          these old rows, so default to Open
                                          rather than guessing Referred)
  Not Attended   -> ISM Cancelled

Run: bench --site ibelong.test execute ibelong_system.ism_v2_status_migrate.run
"""

import frappe

MAPPING = {
    "Scheduled": "ISM Scheduled",
    "Rescheduled": "ISM Scheduled",
    "Cancelled": "ISM Cancelled",
    "Pending Review": "Pending Client Review",
    "Attended": "Case Open",
    "Not Attended": "ISM Cancelled",
}


def run():
    print("=== Migrating ISM Booking.booking_status to new vocabulary ===")
    total = 0
    for old_val, new_val in MAPPING.items():
        names = frappe.get_all("ISM Booking", filters={"booking_status": old_val}, pluck="name")
        if not names:
            print(f"  {old_val!r:16} -> {new_val!r:24} : 0 rows")
            continue
        for chunk_start in range(0, len(names), 500):
            chunk = names[chunk_start:chunk_start + 500]
            frappe.db.set_value("ISM Booking", {"name": ["in", chunk]}, "booking_status", new_val, update_modified=False)
        print(f"  {old_val!r:16} -> {new_val!r:24} : {len(names)} rows")
        total += len(names)
    frappe.db.commit()

    remaining = frappe.get_all(
        "ISM Booking",
        filters={"booking_status": ["not in", list(MAPPING.values())]},
        fields=["booking_status"],
        group_by="booking_status",
    )
    print(f"\n  total remapped: {total}")
    print("  any values outside the new vocabulary now:", remaining or "none")
