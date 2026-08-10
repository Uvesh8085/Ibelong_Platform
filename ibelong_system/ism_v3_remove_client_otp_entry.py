"""
Remove the client-side OTP entry from the profile page. Per the confirmed
real-world flow, the client reads the code back to the NISC officer verbally
- they never type it into their own portal. Staff verify it via the desk
"Verify OTP" button (ism_review.py + Course Assigned Client Script), which
was already built and is unaffected by this change.

Two edits to v3-progle-page:
  1. renderIsmDetail(): drop the OTP input + Confirm button block that only
     rendered for "Pending Client Review".
  2. The expand-click handler's dead .ism-otp-confirm wiring is removed too,
     since renderIsmDetail() will never emit that markup anymore.
  3. Jinja: "Pending Client Review" now gets the same "View Details" button
     as Case Open/Referred/Closed, instead of a distinct "Review & Confirm"
     label implying a client action that no longer exists.

Run: bench --site ibelong.test execute ibelong_system.ism_v3_remove_client_otp_entry.run
"""

import frappe

PROFILE_PAGE = "v3-progle-page"

OLD_JINJA = (
    '{% if b.booking_status == "Pending Client Review" %}\n'
    '                                    <button type="button" class="btn btn-sm btn-outline-primary ism-expand" data-booking="{{ b.name }}" data-target="ismCardBody{{ loop.index }}">Review &amp; Confirm</button>\n'
    '                                    {% elif b.booking_status in ("Case Open", "Case Referred", "Case Closed") %}\n'
    '                                    <button type="button" class="btn btn-sm btn-outline-secondary ism-expand" data-booking="{{ b.name }}" data-target="ismCardBody{{ loop.index }}">View Details</button>\n'
    '                                    {% endif %}'
)
NEW_JINJA = (
    '{% if b.booking_status in ("Pending Client Review", "Case Open", "Case Referred", "Case Closed") %}\n'
    '                                    <button type="button" class="btn btn-sm btn-outline-secondary ism-expand" data-booking="{{ b.name }}" data-target="ismCardBody{{ loop.index }}">View Details</button>\n'
    '                                    {% endif %}'
)

OLD_JS_OTP_BLOCK = """
    if (d.booking_status === "Pending Client Review") {
      html += '<hr><p class="mb-2">Enter the confirmation code we sent you by email to confirm this summary is correct.</p>';
      html += '<div class="row g-2 align-items-center">' +
        '<div class="col-auto"><input type="text" class="form-control form-control-sm ism-otp-input" placeholder="6-digit code" maxlength="6" style="width:140px"></div>' +
        '<div class="col-auto"><button type="button" class="btn btn-success btn-sm ism-otp-confirm">Confirm</button></div>' +
        '</div><div class="ism-otp-msg mt-2"></div>';
    }
    return html;
  }"""
NEW_JS_NO_OTP_BLOCK = """
    return html;
  }"""

OLD_JS_CONFIRM_WIRING = """
          var confirmBtn = content.querySelector(".ism-otp-confirm");
          if (confirmBtn) {
            confirmBtn.addEventListener("click", function(){
              var otpVal = content.querySelector(".ism-otp-input").value.trim();
              var msgEl = content.querySelector(".ism-otp-msg");
              if (!otpVal) { msgEl.innerHTML = '<span class="text-danger">Please enter the code.</span>'; return; }
              frappe.call({
                method: "ibelong_system.ism_review.confirm_ism_review",
                args: { booking: booking, otp: otpVal },
                callback: function(cr){
                  if (!cr.message || cr.message.error) {
                    msgEl.innerHTML = '<span class="text-danger">' + ((cr.message && cr.message.error) || "Could not confirm.") + '</span>';
                    return;
                  }
                  msgEl.innerHTML = '<span class="text-success">Confirmed! Refreshing&hellip;</span>';
                  setTimeout(function(){ location.reload(); }, 1200);
                }
              });
            });
          }
        }"""
NEW_JS_NO_CONFIRM_WIRING = """
        }"""


def run():
    print("=== Remove client-side OTP entry from profile page ===")
    html = (frappe.db.get_value("Web Page", PROFILE_PAGE, "main_section_html") or "").replace("\r\n", "\n")

    changed = []

    if OLD_JINJA in html:
        html = html.replace(OLD_JINJA, NEW_JINJA, 1)
        changed.append("Jinja button unified to 'View Details'")
    elif NEW_JINJA in html:
        print("  [skip] Jinja button already unified")
    else:
        raise RuntimeError("[FAIL] expected Jinja button markup not found - page structure changed")

    if OLD_JS_OTP_BLOCK in html:
        html = html.replace(OLD_JS_OTP_BLOCK, NEW_JS_NO_OTP_BLOCK, 1)
        changed.append("renderIsmDetail() OTP block removed")
    elif NEW_JS_NO_OTP_BLOCK in html and "ism-otp-input" not in html:
        print("  [skip] renderIsmDetail() OTP block already removed")
    else:
        raise RuntimeError("[FAIL] expected JS OTP block not found - page structure changed")

    if OLD_JS_CONFIRM_WIRING in html:
        html = html.replace(OLD_JS_CONFIRM_WIRING, NEW_JS_NO_CONFIRM_WIRING, 1)
        changed.append("dead .ism-otp-confirm wiring removed")
    elif "ism-otp-confirm" not in html:
        print("  [skip] confirm-wiring already removed")
    else:
        raise RuntimeError("[FAIL] expected JS confirm-wiring block not found - page structure changed")

    if changed:
        frappe.db.set_value("Web Page", PROFILE_PAGE, "main_section_html", html, update_modified=True)
        frappe.db.commit()
        frappe.clear_cache()
        print("  [ok]", "; ".join(changed))
    print("\nDone.")
