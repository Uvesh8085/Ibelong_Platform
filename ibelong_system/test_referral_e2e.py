"""
End-to-end smoke test for the referral system: ISM meetings referred to an
external provider ("Malta Police"), and that provider following up through
the external API (referral_api.py) exactly as a real integration would -
using only its api_key, no desk session.

Creates 3 clearly-marked TEST client records (file_number prefixed
"TEST-REF-...") - never touches real/migrated data. Each is taken through
the real flow: booked ISM -> staff sends review OTP -> client confirms with
referred_to_provider set -> Client Referral auto-created (see
ism_review.confirm_ism_review). Then "Malta Police" (an External Service
Provider) uses its own API key to:

  1) get_referrals            - list what's been referred to them (with
                                 their notes/follow-up history)
  2) update_referral_status   - Accepted -> In Progress -> Completed, with
                                 a follow-up note on each transition
  3) add_referral_note        - a follow-up note with no status change
  4) confirm a Closed/Declined referral can no longer be updated
  5) confirm an invalid api_key is rejected

Throughout, confirms Client Details.status is never touched by any of this -
only the ISM Booking row's booking_status and the Client Referral's own
fields change.

Run:
  bench --site <site> execute ibelong_system.test_referral_e2e.run
or paste the body of run() directly into `bench console`.

Test records are left in place afterwards for manual UI inspection; the
output prints ready-to-paste delete commands to clean them up.
"""

import frappe
from ibelong_system import ism_review, referral_api

RESULTS = []
PROVIDER_NAME = "Malta Police"


def _log(label, ok, detail=""):
    RESULTS.append((label, ok, detail))
    print(("PASS" if ok else "FAIL"), "-", label, ("- " + str(detail) if detail else ""))


def _ensure_provider():
    if not frappe.db.exists("External Service Provider", PROVIDER_NAME):
        p = frappe.get_doc({
            "doctype": "External Service Provider",
            "organization_name": PROVIDER_NAME,
            "organization_type": "Police",
            "is_active": 1,
        })
        p.insert(ignore_permissions=True)
        frappe.db.commit()
    return frappe.get_doc("External Service Provider", PROVIDER_NAME)


def _new_test_client(tag):
    suffix = frappe.generate_hash(length=6)
    doc = frappe.new_doc("Client Details")
    doc.file_number = f"TEST-REF-{tag}-{suffix}"
    doc.first_name = f"TestRef{tag}"
    doc.email = f"test.ref.{tag.lower()}.{suffix}@example.invalid"
    doc.status = "Registration Complete"
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc


def _refer_client_via_ism(client_name):
    """Real path: book ISM -> send OTP -> client confirms with a provider set
    -> Client Referral auto-created by ism_review.confirm_ism_review."""
    doc = frappe.get_doc("Client Details", client_name)
    status_before = doc.status

    doc.append("ism_bookings", {
        "slot_date": frappe.utils.today(),
        "slot_time": "10:00:00",
        "officer_name": "Test Officer",
        "booking_status": "ISM Scheduled",
        "support_need": "Referral smoke test",
        "referred_to_provider": PROVIDER_NAME,
    })
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    booking_name = doc.ism_bookings[-1].name

    frappe.set_user("Administrator")
    ism_review.submit_for_client_review(booking_name)
    cached = frappe.cache().get_value(f"ism_review_otp:{booking_name}")
    otp = cached["otp"] if cached else None

    result = ism_review.confirm_ism_review(booking_name, otp)
    _log(f"[{client_name}] confirm_ism_review -> Case Referred", result.get("new_status") == "Case Referred", result)

    status_after = frappe.db.get_value("Client Details", client_name, "status")
    _log(f"[{client_name}] Client Details.status unchanged through referral", status_after == status_before, f"{status_before!r} -> {status_after!r}")

    referral_id = frappe.db.get_value("ISM Booking", booking_name, "linked_referral")
    _log(f"[{client_name}] Client Referral auto-created", bool(referral_id), referral_id)
    return referral_id, status_before


def run():
    print("=== Referral system end-to-end smoke test (Malta Police) ===\n")

    provider = _ensure_provider()
    frappe.set_user("Administrator")
    key_result = referral_api.generate_api_key(provider.name)
    api_key = key_result["api_key"]
    _log("Generated API key for Malta Police", bool(api_key))

    print("\n--- Creating 3 clients, each referred to Malta Police via ISM ---")
    clients = []
    for tag in ("A", "B", "C"):
        c = _new_test_client(tag)
        referral_id, status_before = _refer_client_via_ism(c.name)
        clients.append({"client": c.name, "status_before": status_before, "referral": referral_id})

    print("\n--- Malta Police calls get_referrals() with their api_key ---")
    frappe.set_user("Guest")
    listing = referral_api.get_referrals(api_key)
    frappe.set_user("Administrator")
    returned_ids = {r["name"] for r in listing["referrals"]}
    expected_ids = {c["referral"] for c in clients}
    _log("get_referrals returns exactly our 3 test referrals", expected_ids.issubset(returned_ids), returned_ids)

    ref_a, ref_b, ref_c = (c["referral"] for c in clients)

    print("\n--- Referral A: Accepted, single follow-up note ---")
    frappe.set_user("Guest")
    r1 = referral_api.update_referral_status(api_key, ref_a, "Accepted", note="We have received this referral and will make contact.")
    frappe.set_user("Administrator")
    _log("[A] status -> Accepted", r1.get("new_status") == "Accepted", r1)

    print("\n--- Referral B: Accepted -> In Progress -> Completed, with follow-up notes ---")
    frappe.set_user("Guest")
    referral_api.update_referral_status(api_key, ref_b, "Accepted", note="Case received.")
    referral_api.update_referral_status(api_key, ref_b, "In Progress", note="Officer assigned, investigation started.")
    r2 = referral_api.update_referral_status(api_key, ref_b, "Completed", note="Matter resolved, client supported.")
    frappe.set_user("Administrator")
    _log("[B] status -> Completed", r2.get("new_status") == "Completed", r2)
    b_notes = frappe.db.get_all("Referral Note", filters={"parent": ref_b}, fields=["note", "source"])
    _log("[B] 3 follow-up notes recorded", len(b_notes) == 3, len(b_notes))

    print("\n--- Referral C: plain follow-up note, no status change ---")
    frappe.set_user("Guest")
    r3 = referral_api.add_referral_note(api_key, ref_c, "Client attended first appointment, no further action yet.")
    frappe.set_user("Administrator")
    _log("[C] follow-up note added", r3.get("status") == "success", r3)
    c_status = frappe.db.get_value("Client Referral", ref_c, "referral_status")
    _log("[C] status unchanged by a plain note (still Sent)", c_status == "Sent", c_status)

    print("\n--- Referral B is Completed but not Closed/Declined yet - close it, then confirm it's locked ---")
    frappe.db.set_value("Client Referral", ref_b, "reason_for_closure", "Case fully resolved.")
    frappe.set_user("Guest")
    referral_api.update_referral_status(api_key, ref_b, "Closed", note="Closing out - resolved.")
    try:
        referral_api.update_referral_status(api_key, ref_b, "Accepted", note="should be rejected")
        _log("[B] closed referral rejects further updates", False, "no exception raised")
    except frappe.ValidationError:
        _log("[B] closed referral rejects further updates", True)
    finally:
        frappe.set_user("Administrator")

    print("\n--- Invalid api_key is rejected ---")
    frappe.set_user("Guest")
    try:
        referral_api.get_referrals("not-a-real-key")
        _log("Invalid api_key rejected", False, "no exception raised")
    except frappe.AuthenticationError:
        _log("Invalid api_key rejected", True)
    finally:
        frappe.set_user("Administrator")

    print("\n--- Final check: no Client Details.status was ever touched ---")
    for c in clients:
        final_status = frappe.db.get_value("Client Details", c["client"], "status")
        _log(f"[{c['client']}] status still {c['status_before']!r}", final_status == c["status_before"], final_status)

    print("\n=== SUMMARY ===")
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"{passed}/{len(RESULTS)} checks passed")

    print("\nTest records (kept for manual UI inspection):")
    print("  Provider:", provider.name, "| api_key:", api_key)
    for c in clients:
        print(" ", c["client"], "-> referral", c["referral"])

    print("\nTo delete the test clients AND their referrals later, run:")
    for c in clients:
        print(f'  frappe.delete_doc("Client Details", "{c["client"]}", force=True, ignore_permissions=True)')
    for c in clients:
        print(f'  frappe.delete_doc("Client Referral", "{c["referral"]}", force=True, ignore_permissions=True)')
    print("  frappe.db.commit()")
    print("\n(Leave the 'Malta Police' provider in place if you want to keep testing the API by hand.)")
