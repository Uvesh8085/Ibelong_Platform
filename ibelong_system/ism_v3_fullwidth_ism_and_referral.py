"""
Layout fix requested from live testing: the ISM Bookings table and the
Referral summary table on the Client Details desk form should each span the
full page width, ISM Bookings first, then Referrals directly below it, with
"Show Employment & Social Participation Fields" (and the Employment/
Participation sections it gates) pushed below both.

Two problems, two fixes:

1. ism_bookings currently has no Section Break directly before it, so it's
   still inside the two-column layout started earlier by column_break_pmym
   (the column containing ISM Time Slot / ISM Officer Name / etc.) - it
   renders squeezed into that narrow column instead of full width. Adding a
   plain Section Break custom field immediately before it resets the layout
   to a fresh full-width row for the table.

2. The Referral summary section (see client_details_referral.js) is
   appended to the END of the whole "Integration Support" section body -
   which also contains "Show Employment & Social Participation Fields" and
   the Employment/Participation fields below it - so it currently renders
   AFTER all of that, not right after ISM Bookings. That's a separate JS fix
   (see ism_v3_referral_after_ism.py), not something this script touches.

Run: bench --site ibelong.test execute ibelong_system.ism_v3_fullwidth_ism_and_referral.run
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

FIELDS = {
    "Client Details": [
        {
            "fieldname": "section_break_ism_bookings_full_width",
            "label": "",
            "fieldtype": "Section Break",
            "insert_after": "selected_time",
        },
    ]
}


SECTION_BREAK_FIELDNAME = "section_break_ism_bookings_full_width"


def run():
    print("=== Give ISM Bookings table its own full-width section ===")
    create_custom_fields(FIELDS, ignore_validate=True)

    # Both the new Section Break and ism_bookings are Custom Fields sharing
    # the same insert_after anchor ("selected_time") - Frappe's tie-break for
    # two custom fields on the same anchor is not reliably idx-based, and in
    # testing it put the new section break AFTER ism_bookings instead of
    # before it. Re-anchoring ism_bookings itself to follow the new section
    # break removes the ambiguity entirely - selected_time -> section break
    # -> ism_bookings is then the only possible order.
    frappe.db.set_value(
        "Custom Field", "Client Details-ism_bookings",
        "insert_after", SECTION_BREAK_FIELDNAME,
    )

    frappe.db.commit()
    frappe.clear_cache()

    meta = frappe.get_meta("Client Details", cached=False)
    fo = [f.fieldname for f in meta.fields]
    idx = fo.index("ism_bookings") if "ism_bookings" in fo else -1
    print("  fields around ism_bookings now:", fo[idx - 2:idx + 2] if idx >= 0 else "not found")
    print("\nDone.")
