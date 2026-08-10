"""
The referral UI on the Client Details desk form (summary table + New
Referral / View All buttons) is delivered as a "Client Script" DB record
named "Client Details Referral Section" - the SAME pattern already used for
"Course Assigned" (Send/Verify OTP buttons). The static file at
public/js/client_details_referral.js that was committed earlier is never
actually loaded by Frappe (no doctype_js hook wires it in) - it was only
ever a reference copy. This script creates/updates the real Client Script
record from that file's content, exactly as it exists locally.

Run: bench --site ibelong.test execute ibelong_system.ism_v3_deploy_referral_client_script.run
"""

import os

import frappe

APP_DIR = os.path.dirname(__file__)
SCRIPT_NAME = "Client Details Referral Section"
SOURCE_FILE = os.path.join(APP_DIR, "public", "js", "client_details_referral.js")


def run():
    print("=== Deploy Client Details Referral Section (Client Script) ===")
    with open(SOURCE_FILE) as f:
        script_content = f.read()

    if frappe.db.exists("Client Script", SCRIPT_NAME):
        doc = frappe.get_doc("Client Script", SCRIPT_NAME)
        doc.script = script_content
        doc.dt = "Client Details"
        doc.view = "Form"
        doc.enabled = 1
        doc.save(ignore_permissions=True)
        print(f"  [ok] updated existing '{SCRIPT_NAME}'")
    else:
        doc = frappe.get_doc({
            "doctype": "Client Script",
            "name": SCRIPT_NAME,
            "dt": "Client Details",
            "view": "Form",
            "script": script_content,
            "enabled": 1,
        })
        doc.insert(ignore_permissions=True)
        print(f"  [ok] created '{SCRIPT_NAME}'")

    frappe.db.commit()
    frappe.clear_cache()
    print("\nDone. Refresh the Client Details form - the Referrals section")
    print("should now appear inside the 'Integration Support' area.")
