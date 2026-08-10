"""
NISC enhancement (30/07/2026 doc) - move the ISM meeting form from single
Client Details fields to PER-BOOKING fields on the ISM Booking child table,
since a client can now have multiple ISM meetings and things like "Follow-Up"
only make sense per meeting.

Adds to ISM Booking:
  - support checkboxes (9) + notes + referral category, each opens on tick
  - vulnerability checkboxes (8) + notes + referral category, each opens on tick
  - personal_integration_plan  ("Personal Integration Plan and Expected Outcomes")
  - follow_up                  (free text, not filled at the first meeting)
  - referred_to_provider       (Link -> External Service Provider; setting this
                                 + submitting for review is what makes a case
                                 "Case Referred")
  - additional_notes           (internal only - staff + referred provider)
  - client_confirmed / client_confirmed_on (OTP confirmation audit)
  - linked_referral            (Link -> Client Referral, set once created)

Also updates booking_status options to the new lifecycle:
  ISM Scheduled -> ISM Cancelled | Pending Client Review
  Pending Client Review -> Case Open | Case Referred   (client OTP-confirms)
  Case Open | Case Referred -> Case Closed             (NISC staff only)

The old Client Details Phase-3 fields (employment_assistance_notes etc.,
case_status) are left in place but are no longer the active data path -
superseded by these per-booking fields.

Run: bench --site ibelong.test execute ibelong_system.ism_v2_booking_fields.run
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

REFERRAL_CATEGORIES = (
    "\nEducational Support\nEmployment Assistance\nDocumentation Assistance\n"
    "Family Support\nAccommodation Support\nHealth Services\n"
    "Well-being / Mental Health Support\nSocial Integration Activities\n"
    "Legal Assistance\nOther"
)

NEW_BOOKING_STATUS_OPTIONS = (
    "\nISM Scheduled\nISM Cancelled\nPending Client Review\n"
    "Case Open\nCase Referred\nCase Closed"
)

SUPPORT_CHECKS = [
    "employment_assistance", "educational_support", "documentation_assistance",
    "family_support", "accommodation_support", "health_services",
    "wellbeing_mental_health_support", "social_integration_activities", "other_support",
]

VULNERABILITY_CHECKS = [
    "pregnant_women", "single_parents_with_minor_children", "victims_of_human_trafficking",
    "persons_with_serious_illnesses", "person_with_disabilities", "persons_with_mental_disorders",
    "victim", "ps_v",
]

# Human labels for the checkboxes (ISM Booking is a fresh child table, so these
# don't exist yet as fields anywhere - unlike Phase 3 on Client Details).
LABELS = {
    "employment_assistance": "Employment Assistance",
    "educational_support": "Educational Support",
    "documentation_assistance": "Documentation Assistance",
    "family_support": "Family Support",
    "accommodation_support": "Accommodation Support",
    "health_services": "Health Services",
    "wellbeing_mental_health_support": "Well-being / Mental Health Support",
    "social_integration_activities": "Social Integration Activities",
    "other_support": "Other Support",
    "pregnant_women": "Pregnant Women",
    "single_parents_with_minor_children": "Single Parents with Minor Children",
    "victims_of_human_trafficking": "Victims of Human Trafficking",
    "persons_with_serious_illnesses": "Persons with Serious Illnesses",
    "person_with_disabilities": "Person with Disabilities",
    "persons_with_mental_disorders": "Persons with Mental Disorders",
    "victim": "Victims of Torture, Rape, or Severe Psychological Violence",
    "ps_v": "Physical or Sexual Violence (incl. domestic)",
}


def _pair(fn):
    label = LABELS[fn]
    dep = f"eval:doc.{fn}==1"
    return [
        {"fieldname": fn, "label": label, "fieldtype": "Check"},
        {"fieldname": f"{fn}_notes", "label": f"{label} - Notes", "fieldtype": "Small Text",
         "insert_after": fn, "depends_on": dep, "translatable": 0},
        {"fieldname": f"{fn}_referral_category", "label": f"{label} - Referral Category", "fieldtype": "Select",
         "options": REFERRAL_CATEGORIES, "insert_after": f"{fn}_notes", "depends_on": dep, "translatable": 0},
    ]


def run():
    print("=== Extend ISM Booking: per-meeting form fields ===")

    fields = []
    fields.append({"fieldname": "support_section", "fieldtype": "Section Break", "label": "Support Needed"})
    for fn in SUPPORT_CHECKS:
        fields.extend(_pair(fn))

    fields.append({"fieldname": "vulnerability_section", "fieldtype": "Section Break", "label": "Vulnerable Groups"})
    for fn in VULNERABILITY_CHECKS:
        fields.extend(_pair(fn))

    fields.append({"fieldname": "outcome_section", "fieldtype": "Section Break", "label": "Meeting Outcome"})
    fields.append({"fieldname": "personal_integration_plan", "fieldtype": "Small Text",
                    "label": "Personal Integration Plan and Expected Outcomes"})
    fields.append({"fieldname": "follow_up", "fieldtype": "Small Text",
                    "label": "Follow-Up",
                    "description": "Not filled in at the first meeting - used if the client returns for a further meeting."})
    fields.append({"fieldname": "referred_to_provider", "fieldtype": "Link", "options": "External Service Provider",
                    "label": "Refer to Service Provider",
                    "description": "Setting this and submitting for client review marks the case as Case Referred."})
    fields.append({"fieldname": "linked_referral", "fieldtype": "Link", "options": "Client Referral",
                    "label": "Linked Referral", "read_only": 1})

    fields.append({"fieldname": "internal_section", "fieldtype": "Section Break", "label": "Internal Only"})
    fields.append({"fieldname": "additional_notes", "fieldtype": "Small Text",
                    "label": "Additional Notes",
                    "description": "Never shown to the client. Visible to NISC staff and, if referred, to the receiving service provider."})

    fields.append({"fieldname": "confirmation_section", "fieldtype": "Section Break", "label": "Client Confirmation"})
    fields.append({"fieldname": "client_confirmed", "fieldtype": "Check", "label": "Client Confirmed via OTP", "read_only": 1})
    fields.append({"fieldname": "client_confirmed_on", "fieldtype": "Datetime", "label": "Confirmed On", "read_only": 1})

    print(f"  creating/ensuring {len(fields)} fields on ISM Booking ...")
    create_custom_fields({"ISM Booking": fields}, update=True)

    # booking_status: widen options (native field on a fully custom doctype ->
    # edit the DocType doc directly rather than via Custom Field)
    dt = frappe.get_doc("DocType", "ISM Booking")
    for f in dt.fields:
        if f.fieldname == "booking_status":
            f.options = NEW_BOOKING_STATUS_OPTIONS
            break
    dt.save(ignore_permissions=True)
    print("  [ok] booking_status options updated to new lifecycle vocabulary")

    frappe.db.commit()
    frappe.clear_cache()

    meta = frappe.get_meta("ISM Booking")
    missing = [f["fieldname"] for f in fields if not meta.get_field(f["fieldname"])]
    print("  missing fields:", missing or "none")
    print("\nDone.")
