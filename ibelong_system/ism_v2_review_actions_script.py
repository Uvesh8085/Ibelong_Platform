"""
Load public/js/ism_review_actions.js as an enabled Client Script on Client
Details, same pattern as ism_phase2.py did for the referral buttons - so NISC
staff have "Submit ISM for Client Review" / "Close ISM Case" buttons in the
desk without needing bench execute.

Run: bench --site ibelong.test execute ibelong_system.ism_v2_review_actions_script.run
"""

import os
import frappe

CS_NAME = "ISM Review Actions"
JS_PATH = os.path.join(os.path.dirname(__file__), "public", "js", "ism_review_actions.js")


def run():
    print("=== Load ISM Review Actions Client Script ===")
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
        doc = frappe.get_doc({
            "doctype": "Client Script",
            "name": CS_NAME,
            "dt": "Client Details",
            "view": "Form",
            "enabled": 1,
            "script": code,
        })
        doc.insert(ignore_permissions=True)
        print(f"  [ok] created Client Script '{CS_NAME}'")

    frappe.db.commit()
    frappe.clear_cache()
    print("\nDone. Open a Client Details record with ISM bookings - the")
    print("'Submit ISM for Client Review' / 'Close ISM Case' buttons appear under 'ISM'.")
