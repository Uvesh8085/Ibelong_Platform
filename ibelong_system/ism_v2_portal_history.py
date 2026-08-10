"""
NISC enhancement (30/07/2026 doc) - refresh the ISM booking history table on
the portal profile page for the new lifecycle vocabulary, and add the
"Review & Confirm" panel (OTP) for bookings sitting in Pending Client Review.

Replaces the #ismBookingHistory block built earlier (which used the old
Scheduled/Cancelled/Attended/... vocabulary) with one that:
  - colour-codes the new statuses (ISM Scheduled / ISM Cancelled /
    Pending Client Review / Case Open / Case Referred / Case Closed)
  - for a row in "Pending Client Review", shows a "Review & Confirm" button
    that expands an inline panel: fetches the summary via
    ism_review.get_ism_review_summary, lets the client enter the OTP they
    were emailed/texted, and confirms via ism_review.confirm_ism_review.

additional_notes is never requested or shown here - the backend endpoint
itself omits it, so there's nothing to leak even if this markup changes.

Run: bench --site ibelong.test execute ibelong_system.ism_v2_portal_history.run
"""

import frappe

PROFILE_PAGE = "v3-progle-page"

OLD_HISTORY_BLOCK_MARKER = '<div class="mb-4" id="ismBookingHistory">'

NEW_HISTORY_BLOCK = """<div class="mb-4" id="ismBookingHistory">
                           <h6 class="mb-2"><i class="fas fa-history me-2"></i>Your ISM Appointments</h6>
                           {% if doc_data and doc_data.ism_bookings %}
                           <div class="table-responsive">
                              <table class="table table-sm align-middle">
                                 <thead class="table-light">
                                    <tr>
                                       <th scope="col">#</th>
                                       <th scope="col">Date</th>
                                       <th scope="col">Time</th>
                                       <th scope="col">Officer</th>
                                       <th scope="col">Status</th>
                                       <th scope="col"></th>
                                    </tr>
                                 </thead>
                                 <tbody>
                                    {% for b in doc_data.ism_bookings %}
                                    <tr>
                                       <td>{{ loop.index }}</td>
                                       <td>{{ frappe.format_value(b.slot_date, {"fieldtype": "Date"}) if b.slot_date else "-" }}</td>
                                       <td>{{ frappe.format_value(b.slot_time, {"fieldtype": "Time"}) if b.slot_time else "-" }}</td>
                                       <td>{{ b.officer_name or "-" }}</td>
                                       <td>
                                          {% if b.booking_status == "ISM Cancelled" %}<span class="badge bg-danger">{{ b.booking_status }}</span>
                                          {% elif b.booking_status == "Pending Client Review" %}<span class="badge bg-warning text-dark">{{ b.booking_status }}</span>
                                          {% elif b.booking_status == "Case Open" %}<span class="badge bg-info text-dark">{{ b.booking_status }}</span>
                                          {% elif b.booking_status == "Case Referred" %}<span class="badge" style="background-color:#6f42c1;color:#fff;">{{ b.booking_status }}</span>
                                          {% elif b.booking_status == "Case Closed" %}<span class="badge bg-secondary">{{ b.booking_status }}</span>
                                          {% else %}<span class="badge bg-primary">{{ b.booking_status or "ISM Scheduled" }}</span>{% endif %}
                                       </td>
                                       <td>
                                          {% if b.booking_status == "Pending Client Review" %}
                                          <button type="button" class="btn btn-outline-primary btn-sm ism-review-toggle" data-booking="{{ b.name }}" data-row="ismReviewPanel{{ loop.index }}">
                                             Review &amp; Confirm
                                          </button>
                                          {% endif %}
                                       </td>
                                    </tr>
                                    {% if b.booking_status == "Pending Client Review" %}
                                    <tr id="ismReviewPanel{{ loop.index }}" style="display:none">
                                       <td colspan="6">
                                          <div class="p-3 bg-light rounded ism-review-body" data-booking="{{ b.name }}">
                                             <div class="ism-review-loading text-muted"><i class="fas fa-spinner fa-spin me-1"></i>Loading your meeting summary&hellip;</div>
                                             <div class="ism-review-content" style="display:none"></div>
                                          </div>
                                       </td>
                                    </tr>
                                    {% endif %}
                                    {% endfor %}
                                 </tbody>
                              </table>
                           </div>
                           <p class="text-muted mb-0"><small>You may book more than one Integration Support Meeting. Each appointment you book is listed here.</small></p>
                           {% else %}
                           <p class="text-muted mb-0">You have not booked an Integration Support Meeting yet.</p>
                           {% endif %}
                        </div>"""

REVIEW_JS = """
<script>
document.addEventListener("DOMContentLoaded", function(){
  document.querySelectorAll(".ism-review-toggle").forEach(function(btn){
    btn.addEventListener("click", function(){
      var rowId = btn.getAttribute("data-row");
      var row = document.getElementById(rowId);
      if (!row) return;
      var showing = row.style.display !== "none";
      if (showing) { row.style.display = "none"; return; }
      row.style.display = "table-row";
      var body = row.querySelector(".ism-review-body");
      if (body.getAttribute("data-loaded") === "1") return;

      var booking = body.getAttribute("data-booking");
      frappe.call({
        method: "ibelong_system.ism_review.get_ism_review_summary",
        args: { booking: booking },
        callback: function(r){
          var loading = body.querySelector(".ism-review-loading");
          var content = body.querySelector(".ism-review-content");
          if (loading) loading.style.display = "none";
          if (!r.message || r.message.error) {
            content.innerHTML = '<p class="text-danger mb-0">' + ((r.message && r.message.error) || "Could not load this meeting summary.") + '</p>';
            content.style.display = "block";
            return;
          }
          var d = r.message;
          var itemsHtml = "";
          (d.items || []).forEach(function(i){
            itemsHtml += "<li><strong>" + i.label + "</strong>" +
              (i.notes ? " - " + i.notes : "") +
              (i.referral_category ? " (Referral: " + i.referral_category + ")" : "") +
              "</li>";
          });
          if (!itemsHtml) itemsHtml = "<li>No specific support items recorded.</li>";

          content.innerHTML =
            '<p class="mb-2"><strong>Summary of your meeting</strong></p>' +
            '<ul class="mb-3">' + itemsHtml + '</ul>' +
            (d.personal_integration_plan ? '<p class="mb-2"><strong>Personal Integration Plan and Expected Outcomes:</strong><br>' + d.personal_integration_plan + '</p>' : '') +
            (d.follow_up ? '<p class="mb-2"><strong>Follow-Up:</strong><br>' + d.follow_up + '</p>' : '') +
            (d.referred_to_provider ? '<p class="mb-2"><strong>Referred to:</strong> ' + d.referred_to_provider + '</p>' : '') +
            '<hr>' +
            '<p class="mb-2">Enter the confirmation code we sent you by email' + (d.officer_name ? '' : '') + ' to confirm this summary is correct.</p>' +
            '<div class="row g-2 align-items-center">' +
              '<div class="col-auto"><input type="text" class="form-control form-control-sm ism-otp-input" placeholder="6-digit code" maxlength="6" style="width:140px"></div>' +
              '<div class="col-auto"><button type="button" class="btn btn-success btn-sm ism-otp-confirm">Confirm</button></div>' +
            '</div>' +
            '<div class="ism-otp-msg mt-2"></div>';
          content.style.display = "block";
          body.setAttribute("data-loaded", "1");

          content.querySelector(".ism-otp-confirm").addEventListener("click", function(){
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
      });
    });
  });
});
</script>
"""


def run():
    print("=== Portal: ISM history v2 (new vocab + Review & Confirm) ===")
    html = (frappe.db.get_value("Web Page", PROFILE_PAGE, "main_section_html") or "").replace("\r\n", "\n")

    if OLD_HISTORY_BLOCK_MARKER not in html:
        raise RuntimeError("[FAIL] ismBookingHistory block not found on profile page")

    start = html.index(OLD_HISTORY_BLOCK_MARKER)
    # The block is a single top-level <div id="ismBookingHistory">...</div>.
    # Find its matching close by counting div depth from `start`.
    depth = 0
    i = start
    end = None
    while i < len(html):
        if html.startswith("<div", i):
            depth += 1
            i += 4
            continue
        if html.startswith("</div>", i):
            depth -= 1
            i += 6
            if depth == 0:
                end = i
                break
            continue
        i += 1

    if end is None:
        raise RuntimeError("[FAIL] could not find the end of the ismBookingHistory block")

    html = html[:start] + NEW_HISTORY_BLOCK + html[end:]

    if REVIEW_JS not in html:
        html = html + REVIEW_JS

    frappe.db.set_value("Web Page", PROFILE_PAGE, "main_section_html", html, update_modified=True)
    frappe.db.commit()
    frappe.clear_cache()
    print("  [ok] history block replaced with new-vocab version + Review & Confirm panel")
    print("\nDone.")
