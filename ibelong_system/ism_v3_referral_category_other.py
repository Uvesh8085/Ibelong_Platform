"""
Missing feature found via live testing: every support/vulnerability
category on an ISM Booking row has its own "Referral Category" Select
field, and every one of them includes "Other" as a valid option - but there
was never a "please specify" field for it, on local or the test server.

Adds one dedicated "<Category> - Referral Category - Please Specify" field
per category (17 total, matching ism_review.SUPPORT_FIELDS +
VULNERABILITY_FIELDS), shown only when that specific category's own
referral_category is set to "Other" - each category's note stays separate,
so a row with multiple "Other" selections doesn't share one ambiguous box.

Run: bench --site ibelong.test execute ibelong_system.ism_v3_referral_category_other.run
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

SUPPORT_FIELDS = [
    "employment_assistance", "educational_support", "documentation_assistance",
    "family_support", "accommodation_support", "health_services",
    "wellbeing_mental_health_support", "social_integration_activities", "other_support",
]
VULNERABILITY_FIELDS = [
    "pregnant_women", "single_parents_with_minor_children", "victims_of_human_trafficking",
    "persons_with_serious_illnesses", "person_with_disabilities", "persons_with_mental_disorders",
    "victim", "ps_v",
]
ALL_CATEGORIES = SUPPORT_FIELDS + VULNERABILITY_FIELDS


def run():
    print("=== Add 'please specify' field for each Referral Category's Other option ===")

    fields = []
    for category in ALL_CATEGORIES:
        rc_fieldname = f"{category}_referral_category"
        meta = frappe.get_meta("ISM Booking")
        rc_field = meta.get_field(rc_fieldname)
        if not rc_field:
            print(f"  [skip] {rc_fieldname} not found on ISM Booking - skipping")
            continue

        label_base = (rc_field.label or category).replace(" - Referral Category", "")
        fields.append({
            "fieldname": f"{category}_referral_category_other",
            "label": f"{label_base} - Referral Category - Please Specify",
            "fieldtype": "Data",
            "insert_after": rc_fieldname,
            "translatable": 0,
            "depends_on": f'eval:doc.{rc_fieldname}=="Other"',
        })

    create_custom_fields({"ISM Booking": fields}, update=True)
    frappe.db.commit()
    frappe.clear_cache()

    print(f"  [ok] ensured {len(fields)} 'please specify' fields")

    meta = frappe.get_meta("ISM Booking", cached=False)
    missing = [f["fieldname"] for f in fields if not meta.get_field(f["fieldname"])]
    if missing:
        print("  [FAIL] still missing:", missing)
    else:
        print("  [ok] all fields verified present")

    print("\nDone.")
