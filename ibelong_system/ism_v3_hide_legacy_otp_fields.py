"""
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
