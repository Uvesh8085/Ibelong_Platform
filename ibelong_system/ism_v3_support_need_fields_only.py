"""
Fix for a bug found via live testing on the test server: the portal profile
page's "What kind of support do you need?" dropdown (client-profile-page-v3,
injected by ism_portal_support.py) calls
ibelong_system.update_user.update_client_and_sync_email to save
ism_support_need / ism_support_other onto Client Details. That call succeeds
silently either way - but if those two fields don't actually exist as real
fields on Client Details, Frappe just drops the values on save, so nothing
is ever persisted (looks like it saved - the button shows "Saved" - but
reloading the page shows nothing selected).

This creates ONLY the two underlying custom fields, with the full support
option list already used by the portal dropdown. It deliberately does NOT
touch anything else - specifically NOT the Registration page
(client-registration-i-belong-platform-v3) or its "Save Client Registration
Data" Server Script, both of which ism_phase1.py (the field's original
source) also patches. Per this project's standing instruction, the
Registration page and workflow must never be modified again - this script
is scoped to exclude that entirely.

Run: bench --site ibelong.test execute ibelong_system.ism_v3_support_need_fields_only.run
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

SUPPORT_OPTIONS = (
    "\nEmployment Assistance\nEducational Support\nDocumentation Assistance\n"
    "Family Support\nAccommodation Support\nHealth Services\n"
    "Well-being / Mental Health Support\nSocial Integration Activities\n"
    "Legal Assistance\nOther Support"
)


def run():
    print("=== Ensure ism_support_need / ism_support_other fields exist (schema only) ===")
    create_custom_fields(
        {
            "Client Details": [
                {
                    "fieldname": "ism_support_need",
                    "label": "Support Needed (selected at registration)",
                    "fieldtype": "Select",
                    "options": SUPPORT_OPTIONS,
                    "insert_after": "support_requested_section",
                    "translatable": 0,
                },
                {
                    "fieldname": "ism_support_other",
                    "label": "Support Needed - Please Specify",
                    "fieldtype": "Data",
                    "insert_after": "ism_support_need",
                    "translatable": 0,
                    "depends_on": "eval:doc.ism_support_need=='Other Support'",
                },
            ]
        },
        update=True,
    )

    # If ism_support_need already existed with an older/shorter option list,
    # make sure it matches the full list the portal dropdown actually offers.
    cf = "Client Details-ism_support_need"
    if frappe.db.exists("Custom Field", cf):
        frappe.db.set_value("Custom Field", cf, "options", SUPPORT_OPTIONS)

    frappe.db.commit()
    frappe.clear_cache()

    meta = frappe.get_meta("Client Details", cached=False)
    print("  ism_support_need exists:", bool(meta.get_field("ism_support_need")))
    print("  ism_support_other exists:", bool(meta.get_field("ism_support_other")))
    print("\nDone. Registration page and its save script were NOT touched.")
