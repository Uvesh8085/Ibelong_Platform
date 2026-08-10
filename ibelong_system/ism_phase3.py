"""
Phase 3 - NISC operational changes on the Client Details ISM tab (backend/doctype).

For every support-service checkbox and every vulnerability checkbox, add two
fields that appear (depends_on) only when the box is ticked:
    <field>_notes      Small Text  "<Label> - Notes"
    <field>_referral   Select      "<Label> - Referral Service"  (categories incl. Legal Assistance)

Plus a Case Status Select (Active / Referred / Closed).

All additive custom fields. Run:
    bench --site ibelong.test execute ibelong_system.ism_phase3.run
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

# Referral categories offered per ticked box (item 2: add Legal Assistance)
REFERRAL_CATEGORIES = (
    "\nEducational Support\nEmployment Assistance\nDocumentation Assistance\n"
    "Family Support\nAccommodation Support\nHealth Services\n"
    "Well-being / Mental Health Support\nSocial Integration Activities\n"
    "Legal Assistance\nOther"
)

SUPPORT_CHECKS = [
    "employment_assistance",
    "educational_support",
    "documentation_assistance",
    "family_support",
    "accommodation_support",
    "health_services",
    "wellbeing_mental_health_support",
    "social_integration_activities",
    "other_support",
]

VULNERABILITY_CHECKS = [
    "pregnant_women",
    "single_parents_with_minor_children",
    "victims_of_human_trafficking",
    "persons_with_serious_illnesses",
    "person_with_disabilities",
    "persons_with_mental_disorders",
    "victim",
    "ps_v",
]


def _pair(meta, fn):
    """Return the notes + referral custom-field defs for checkbox `fn`."""
    field = meta.get_field(fn)
    if not field:
        raise RuntimeError(f"checkbox not found on Client Details: {fn}")
    label = field.label or fn
    dep = f"eval:doc.{fn}==1"
    return [
        {
            "fieldname": f"{fn}_notes",
            "label": f"{label} - Notes",
            "fieldtype": "Small Text",
            "insert_after": fn,
            "depends_on": dep,
            "translatable": 0,
        },
        {
            "fieldname": f"{fn}_referral",
            "label": f"{label} - Referral Service",
            "fieldtype": "Select",
            "options": REFERRAL_CATEGORIES,
            "insert_after": f"{fn}_notes",
            "depends_on": dep,
            "translatable": 0,
        },
    ]


def run():
    print("=== ISM Phase 3: per-checkbox Notes + Referral, Case Status ===")
    meta = frappe.get_meta("Client Details")

    fields = []
    # Case Status near the ISM status info
    fields.append(
        {
            "fieldname": "case_status",
            "label": "Case Status",
            "fieldtype": "Select",
            "options": "\nActive\nReferred\nClosed",
            "insert_after": "isr_status",
            "translatable": 0,
        }
    )

    for fn in SUPPORT_CHECKS:
        fields.extend(_pair(meta, fn))
    for fn in VULNERABILITY_CHECKS:
        fields.extend(_pair(meta, fn))

    print(f"  creating/ensuring {len(fields)} custom fields …")
    create_custom_fields({"Client Details": fields}, update=True)

    frappe.db.commit()
    frappe.clear_cache()

    # verify
    meta2 = frappe.get_meta("Client Details")
    missing = [f["fieldname"] for f in fields if not meta2.get_field(f["fieldname"])]
    print("  case_status present:", bool(meta2.get_field("case_status")),
          "| opts:", (meta2.get_field("case_status").options or "").replace("\n", "|"))
    print(f"  support pairs: {len(SUPPORT_CHECKS)} | vulnerability pairs: {len(VULNERABILITY_CHECKS)}")
    print("  missing:", missing or "none")
    print("\nDone.")
