"""
Fix the pre-existing "Start ISM" button (Client Script "Course Assigned" on
Client Details). It currently:
  - shows based on Client Details.status == "ISM Meeting Scheduled" (wrong -
    that's the course-progress field, and doesn't work per-booking)
  - on click, sets Client Details.status = "Pending Client Review" directly
    (wrong - must never touch Client Details.status; only the specific ISM
    Booking row's booking_status should change)

Fixed behaviour: one "Start ISM" button per ism_bookings row currently in
"ISM Scheduled" status (normally just one - the current appointment). Clicking
it calls the existing, already-tested ism_review.submit_for_client_review()
for that specific row, which validates, generates + sends the OTP, and sets
that row's booking_status to "Pending Client Review". Client Details.status
is never touched.

Everything else in the script (the commented-out title-disabling code) is
left untouched.

Run: bench --site ibelong.test execute ibelong_system.ism_v3_fix_start_button.run
"""

import frappe

CS_NAME = "Course Assigned"

NEW_SCRIPT = """frappe.ui.form.on("Client Details", {
    refresh(frm) {
        // Disable renaming when form loads
        //disable_title_click();

        _add_start_ism_buttons(frm);
    },

    // refresh(frm) {
    //     // Title might get re-rendered on refresh — disable rename again
    //     setTimeout(disable_title_click, 50);
    // },
});

// Start ISM: one button per booking row currently "ISM Scheduled" - never
// touches Client Details.status, only that row's booking_status (via the
// existing OTP submit-for-review flow).
function _add_start_ism_buttons(frm) {
    if (frm.is_new()) return;

    var rows = (frm.doc.ism_bookings || []).filter(function(r) {
        return r.booking_status === "ISM Scheduled";
    });
    if (!rows.length) return;

    rows.forEach(function(row) {
        var label = rows.length > 1
            ? __('Start ISM ({0})', [row.slot_date || 'no date'])
            : __('Start ISM');

        frm.add_custom_button(label, function () {
            frappe.confirm(
                __('Are you sure you want to start this ISM meeting? Once started, the client will be sent a confirmation code and the meeting status will move to "Pending Client Review".'),
                () => {
                    frappe.call({
                        method: "ibelong_system.ism_review.submit_for_client_review",
                        args: { booking: row.name },
                        freeze: true,
                        callback: function (r) {
                            if (r.exc) return;
                            frappe.show_alert({
                                message: __("Status updated to Pending Client Review - confirmation code sent to the client"),
                                indicator: "green",
                            });
                            frm.reload_doc();
                        },
                    });
                }
            );
        }, __('Actions'));
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
    print("=== Fix Start ISM button (Course Assigned script) ===")
    if not frappe.db.exists("Client Script", CS_NAME):
        raise RuntimeError(f"[FAIL] Client Script '{CS_NAME}' not found")

    doc = frappe.get_doc("Client Script", CS_NAME)
    doc.script = NEW_SCRIPT
    doc.enabled = 1
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    frappe.clear_cache()
    print(f"  [ok] '{CS_NAME}' updated - Start ISM now targets the ISM Booking row, not Client Details.status")
    print("\nDone.")
