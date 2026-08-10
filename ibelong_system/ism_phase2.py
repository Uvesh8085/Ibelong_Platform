"""
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
