"""
Real-world ISM confirmation flow, per live testing feedback: the client does
NOT type the OTP into their own portal. Instead, the officer sends the OTP,
the client reads it back to the officer (in person / over the phone) as their
way of agreeing to the ISM form, and the OFFICER types it into the desk to
verify it. On a correct OTP, the booking goes straight to Case Open / Case
Referred (per the referral logic already built) - "Meeting Attended" is not
reintroduced, matching the original written spec.

Updates the "Course Assigned" Client Script (Client Details) to show, per
ism_bookings row:
  - "Send OTP"   - rows in "ISM Scheduled" (first send) or
                   "Pending Client Review" (resend, e.g. code expired) -
                   calls the already-widened ism_review.submit_for_client_review
  - "Verify OTP" - rows in "Pending Client Review" - opens a small dialog for
                   the officer to enter the code the client relayed, calls
                   ism_review.confirm_ism_review (already permits staff, not
                   just the owning client - no backend change needed there)

Client Details.status is still never touched - only booking_status on the
relevant ISM Booking row changes, exactly as before.

Run: bench --site ibelong.test execute ibelong_system.ism_v3_send_verify_otp.run
"""

import frappe

CS_NAME = "Course Assigned"

NEW_SCRIPT = """frappe.ui.form.on("Client Details", {
    refresh(frm) {
        // Disable renaming when form loads
        //disable_title_click();

        _add_ism_action_buttons(frm);
    },

    // refresh(frm) {
    //     // Title might get re-rendered on refresh — disable rename again
    //     setTimeout(disable_title_click, 50);
    // },
});

// ISM actions - never touch Client Details.status, only the relevant
// ism_bookings row's booking_status.
//
// "Send OTP"   shown for a row in "ISM Scheduled" (first send) or
//              "Pending Client Review" (resend).
// "Verify OTP" shown for a row in "Pending Client Review" - the client reads
//              the code back to the officer, who enters it here to confirm.
//              A correct code moves the row straight to Case Open / Case
//              Referred (never "Meeting Attended").
function _add_ism_action_buttons(frm) {
    if (frm.is_new()) return;

    (frm.doc.ism_bookings || []).forEach(function(row) {
        var tag = row.slot_date ? ' (' + row.slot_date + ')' : '';

        if (row.booking_status === "ISM Scheduled" || row.booking_status === "Pending Client Review") {
            frm.add_custom_button(__('Send OTP{0}', [tag]), function () {
                frappe.confirm(
                    __('Send the confirmation code to the client for this ISM meeting?'),
                    () => {
                        frappe.call({
                            method: "ibelong_system.ism_review.submit_for_client_review",
                            args: { booking: row.name },
                            freeze: true,
                            callback: function (r) {
                                if (r.exc) return;
                                frappe.show_alert({
                                    message: __("Confirmation code sent to the client"),
                                    indicator: "green",
                                });
                                frm.reload_doc();
                            },
                        });
                    }
                );
            }, __('Actions'));
        }

        if (row.booking_status === "Pending Client Review") {
            frm.add_custom_button(__('Verify OTP{0}', [tag]), function () {
                var d = new frappe.ui.Dialog({
                    title: __('Verify OTP'),
                    fields: [
                        {
                            fieldname: 'otp',
                            fieldtype: 'Data',
                            label: __('Code the client read back to you'),
                            reqd: 1,
                        },
                    ],
                    primary_action_label: __('Verify'),
                    primary_action(values) {
                        frappe.call({
                            method: "ibelong_system.ism_review.confirm_ism_review",
                            args: { booking: row.name, otp: values.otp },
                            freeze: true,
                            callback: function (r) {
                                if (!r.message || r.message.error) {
                                    frappe.msgprint(__((r.message && r.message.error) || 'Could not verify this code.'));
                                    return;
                                }
                                d.hide();
                                frappe.show_alert({
                                    message: __('Verified - status updated to {0}', [r.message.new_status]),
                                    indicator: 'green',
                                });
                                frm.reload_doc();
                            },
                        });
                    },
                });
                d.show();
            }, __('Actions'));
        }
    });
}

// 🚫 Prevent renaming from the form title
// function disable_title_click() {
//     const $titleArea = $(".page-title .title-area.editable-title");
//     if (!$titleArea.length) return;

//     $titleArea.off("click");
//     $titleArea.find(".title-text").off("click dblclick");

//     $titleArea.on("click", function (e) {
//         e.stopImmediatePropagation();
//         e.preventDefault();
//     });

//     $titleArea.find(".title-text")
//         .css("cursor", "default")
//         .attr("title", "Renaming disabled");
// }
"""


def run():
    print("=== Add Send OTP + Verify OTP buttons (Course Assigned script) ===")
    if not frappe.db.exists("Client Script", CS_NAME):
        raise RuntimeError(f"[FAIL] Client Script '{CS_NAME}' not found")

    doc = frappe.get_doc("Client Script", CS_NAME)
    doc.script = NEW_SCRIPT
    doc.enabled = 1
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    frappe.clear_cache()
    print(f"  [ok] '{CS_NAME}' updated with Send OTP / Verify OTP buttons")
    print("\nDone.")
