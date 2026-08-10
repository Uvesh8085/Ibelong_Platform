"""
Verification script - run on the test env after deploy_ism.sh completes.
bench --site <SITE> execute ibelong_system.verify_deployment.run
"""
import frappe

def run():
    print("=== ISM deployment verification ===\n")

    checks = []

    checks.append(("ISM Booking doctype exists", frappe.db.exists("DocType", "ISM Booking")))
    checks.append(("Client Details has ism_bookings field", bool(frappe.get_meta("Client Details").get_field("ism_bookings"))))
    checks.append(("ISM Booking has booking_status field", bool(frappe.get_meta("ISM Booking").get_field("booking_status"))))

    bs = frappe.get_meta("ISM Booking").get_field("booking_status")
    expected_statuses = {"ISM Scheduled", "ISM Cancelled", "Pending Client Review", "Case Open", "Case Referred", "Case Closed"}
    actual_statuses = set((bs.options or "").split("\n")) if bs else set()
    checks.append(("booking_status has correct new vocabulary", expected_statuses.issubset(actual_statuses)))

    checks.append(("ism_review module importable", True))
    try:
        from ibelong_system import ism_review
        checks.append(("ism_review.submit_for_client_review exists", hasattr(ism_review, "submit_for_client_review")))
        checks.append(("ism_review.confirm_ism_review exists", hasattr(ism_review, "confirm_ism_review")))
        checks.append(("ism_review.validate_client_details exists", hasattr(ism_review, "validate_client_details")))
    except ImportError as e:
        checks.append((f"ism_review module import FAILED: {e}", False))

    import ibelong_system.hooks as hooks
    doc_events = getattr(hooks, "doc_events", {})
    checks.append(("hooks.py doc_events has Client Details validate hook",
        doc_events.get("Client Details", {}).get("validate") == "ibelong_system.ism_review.validate_client_details"))

    cs = frappe.db.get_value("Client Script", "Course Assigned", ["enabled", "script"], as_dict=True)
    checks.append(("Course Assigned script has Send OTP button", bool(cs and "Send OTP" in (cs.script or ""))))
    checks.append(("Course Assigned script has Verify OTP button", bool(cs and "Verify OTP" in (cs.script or ""))))

    lf = frappe.db.get_value("Client Script", "Language Fluency", "enabled")
    checks.append(("Legacy 'Language Fluency' script disabled (or absent)", lf in (0, None)))

    html = frappe.db.get_value("Web Page", "v3-progle-page", "main_section_html") or ""
    checks.append(("Profile page has hasActiveIsm gating field", "hasActiveIsm" in html))
    checks.append(("Profile page has ISM appointment cards", "ism-card" in html))
    checks.append(("Profile page has no client-side OTP entry (removed)", "ism-otp-input" not in html))
    checks.append(("File Number fallback fix applied (input)", "FN-12345" not in html))

    from ibelong_system import get_booking_data
    import inspect
    src = inspect.getsource(get_booking_data.create_client)
    checks.append(("create_client has duplicate-booking guard", "existing_active" in src))
    checks.append(("create_client does NOT set doc.status", "doc.status =" not in src))

    print("RESULTS:")
    passed = 0
    for label, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'} - {label}")
        if ok:
            passed += 1
    print(f"\n{passed}/{len(checks)} checks passed")
