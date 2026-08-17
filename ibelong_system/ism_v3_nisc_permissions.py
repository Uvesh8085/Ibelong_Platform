"""
Fix for two bugs reported from live testing on the test server, both
traced to the same root cause: the "NISC User" role has ZERO permission
entries on "Client Details" there (confirmed: querying its permissions
returned nothing, vs full read/write/create locally). Without write access,
a NISC user can't save any change to Client Details - including changing an
ISM Booking row's booking_status - and the whole ism_bookings grid likely
renders read-only for them, which is also why ticking "Other Support" never
reveals its dependent notes/referral-category fields (the grid row can't be
interacted with at all).

Client Details is a database-only doctype (no JSON fixture on disk) - its
permissions were set up locally via the desk UI (Role Permissions Manager)
and were never captured in any deployable script, unlike Client Referral/
External Service Provider, whose NISC User permissions are baked into their
doctype JSON and synced automatically via frappe.reload_doc(). This script
closes that specific gap, matching local's exact permission set, and
double-checks the other two doctypes as a safety net.

Run: bench --site ibelong.test execute ibelong_system.ism_v3_nisc_permissions.run
"""

import frappe

ROLE = "NISC User"

PERMISSIONS = {
    "Client Details": dict(read=1, write=1, create=1, report=1, export=1),
    "Client Referral": dict(read=1, write=1, create=1, report=1, export=1, share=1, print=1, email=1),
    "External Service Provider": dict(read=1, report=1),
}

DEFAULTS = dict(
    read=0, write=0, create=0, delete=0, submit=0, cancel=0, amend=0,
    report=0, export=0, select=0, share=0, print=0, email=0, if_owner=0,
)


def _ensure_perm(doctype, role, **overrides):
    existing = frappe.db.get_value(
        "Custom DocPerm",
        {"parent": doctype, "role": role, "permlevel": 0},
        "name",
    )
    values = dict(DEFAULTS)
    values.update(overrides)

    if existing:
        doc = frappe.get_doc("Custom DocPerm", existing)
        doc.update(values)
        doc.save(ignore_permissions=True)
        print(f"  [ok] updated existing permission: {doctype} / {role}")
    else:
        doc = frappe.get_doc(dict(
            doctype="Custom DocPerm",
            parent=doctype,
            parenttype="DocType",
            parentfield="permissions",
            role=role,
            permlevel=0,
            **values,
        ))
        doc.insert(ignore_permissions=True)
        print(f"  [ok] created permission: {doctype} / {role}")


def run():
    print(f"=== Ensure '{ROLE}' permissions match local ===")
    for doctype, perms in PERMISSIONS.items():
        _ensure_perm(doctype, ROLE, **perms)

    frappe.db.commit()
    frappe.clear_cache()

    print("\n=== Verifying ===")
    for doctype in PERMISSIONS:
        meta = frappe.get_meta(doctype, cached=False)
        found = None
        for p in meta.permissions:
            if p.role == ROLE:
                found = p
        if found:
            print(f"  {doctype}: read={found.read} write={found.write} create={found.create}")
        else:
            print(f"  {doctype}: [FAIL] still no permission entry")

    print("\nDone.")
