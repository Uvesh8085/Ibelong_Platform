"""
End-to-end smoke test for the NISC-managed ISM case-management flow, run
directly against a live environment (local or test server).

Creates 3 clearly-marked TEST client records (file_number prefixed
"TEST-...") - never touches real/migrated data:

  A) ISM only            - books an ISM, staff sends + verifies OTP
                            -> Case Open -> Case Closed
  B) ISM + Course         - same ISM flow but referred to a provider
                            -> Case Referred, PLUS an independent course
                            status change, to prove the two never interfere
  C) Course only, no ISM  - normal course status progression with an empty
                            ism_bookings table throughout

Confirms throughout: Client Details.status is NEVER modified by any ISM
action - only the relevant ISM Booking row's booking_status changes.

Run:
  bench --site <site> execute ibelong_system.test_ism_e2e.run
or paste the body of run() directly into `bench console`.

Test records are left in place afterwards for manual UI inspection; the
output prints ready-to-paste delete commands to clean them up.
"""

import frappe
from ibelong_system import ism_review

RESULTS = []


def _log(label, ok, detail=""):
    RESULTS.append((label, ok, detail))
    print(("PASS" if ok else "FAIL"), "-", label, ("- " + str(detail) if detail else ""))


def _new_test_client(tag):
    suffix = frappe.generate_hash(length=6)
    doc = frappe.new_doc("Client Details")
    doc.file_number = f"TEST-{tag}-{suffix}"
    doc.first_name = f"Test{tag}"
    doc.email = f"test.{tag.lower()}.{suffix}@example.invalid"
    doc.status = "Registration Complete"
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc


def _run_ism_flow(client_name, want_referral, close_after=False):
    doc = frappe.get_doc("Client Details", client_name)
    status_before = doc.status

    doc.append("ism_bookings", {
        "slot_date": frappe.utils.today(),
        "slot_time": "10:00:00",
        "officer_name": "Test Officer",
        "booking_status": "ISM Scheduled",
        "support_need": "Smoke test booking",
    })
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    booking_name = doc.ism_bookings[-1].name

    if want_referral:
        provider = frappe.db.get_value("External Service Provider", {}, "name")
        if not provider:
            p = frappe.get_doc({
                "doctype": "External Service Provider",
                "organization_name": f"Test Provider {frappe.generate_hash(length=4)}",
                "organization_type": "Other",
                "is_active": 1,
            })
            p.insert(ignore_permissions=True)
            frappe.db.commit()
            provider = p.name
        frappe.db.set_value("ISM Booking", booking_name, "referred_to_provider", provider)

    frappe.set_user("Administrator")

    ism_review.submit_for_client_review(booking_name)
    cached = frappe.cache().get_value(f"ism_review_otp:{booking_name}")
    otp = cached["otp"] if cached else None
    _log(f"[{client_name}] OTP generated on Send", bool(otp))

    bstat = frappe.db.get_value("ISM Booking", booking_name, "booking_status")
    _log(f"[{client_name}] booking_status -> Pending Client Review", bstat == "Pending Client Review", bstat)

    cstat = frappe.db.get_value("Client Details", client_name, "status")
    _log(f"[{client_name}] Client Details.status unchanged after Send OTP", cstat == status_before, f"{status_before!r} -> {cstat!r}")

    result = ism_review.confirm_ism_review(booking_name, otp)
    expected = "Case Referred" if want_referral else "Case Open"
    _log(f"[{client_name}] confirm_ism_review -> {expected}", result.get("new_status") == expected, result)

    cstat2 = frappe.db.get_value("Client Details", client_name, "status")
    _log(f"[{client_name}] Client Details.status STILL unchanged after Verify OTP", cstat2 == status_before, f"{status_before!r} -> {cstat2!r}")

    if want_referral:
        linked = frappe.db.get_value("ISM Booking", booking_name, "linked_referral")
        _log(f"[{client_name}] Client Referral auto-created on confirm", bool(linked), linked)

    if close_after:
        ism_review.close_ism_case(booking_name)
        bstat_closed = frappe.db.get_value("ISM Booking", booking_name, "booking_status")
        _log(f"[{client_name}] close_ism_case -> Case Closed", bstat_closed == "Case Closed", bstat_closed)
        cstat3 = frappe.db.get_value("Client Details", client_name, "status")
        _log(f"[{client_name}] Client Details.status STILL unchanged after Close Case", cstat3 == status_before, f"{status_before!r} -> {cstat3!r}")

    return booking_name


def run():
    print("=== ISM end-to-end smoke test ===\n")

    print("--- A) ISM only ---")
    client_a = _new_test_client("ISM-ONLY")
    _run_ism_flow(client_a.name, want_referral=False, close_after=True)

    print("\n--- B) ISM + Course (referred) ---")
    client_b = _new_test_client("ISM-PLUS-COURSE")
    _run_ism_flow(client_b.name, want_referral=True, close_after=False)
    frappe.db.set_value("Client Details", client_b.name, "status", "Stage 1 - Course Assigned")
    frappe.db.commit()
    ism_status_b = frappe.db.get_value("ISM Booking", {"parent": client_b.name}, "booking_status")
    _log("[B] course status change did not affect ISM booking_status", ism_status_b == "Case Referred", ism_status_b)

    print("\n--- C) Course only, no ISM ---")
    client_c = _new_test_client("COURSE-ONLY")
    frappe.db.set_value("Client Details", client_c.name, "status", "Stage 1 - Course Assigned")
    frappe.db.commit()
    frappe.db.set_value("Client Details", client_c.name, "status", "Stage 1 - In Progress")
    frappe.db.commit()
    final_status_c = frappe.db.get_value("Client Details", client_c.name, "status")
    bookings_c = frappe.db.count("ISM Booking", {"parent": client_c.name})
    _log("[C] course-only client progressed normally", final_status_c == "Stage 1 - In Progress", final_status_c)
    _log("[C] course-only client has zero ISM bookings", bookings_c == 0, bookings_c)

    print("\n=== SUMMARY ===")
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"{passed}/{len(RESULTS)} checks passed")

    print("\nTest client records (kept for manual UI inspection):")
    for c in (client_a, client_b, client_c):
        print(" ", c.name, "-", c.file_number)

    print("\nTo delete them later, run:")
    for c in (client_a, client_b, client_c):
        print(f'  frappe.delete_doc("Client Details", "{c.name}", force=True, ignore_permissions=True)')
    print("  frappe.db.commit()")
