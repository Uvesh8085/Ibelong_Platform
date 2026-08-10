"""
Rebuild the "Your ISM Appointments" section on the client profile page
(client_profile_v3, Web Page 'v3-progle-page') as newest-first expandable
cards, covering every requirement in the NISC-managed-ISM spec:

  - Meeting Date, Meeting Time, ISM Officer, Current ISM Status (card header)
  - Support Requested, Outcome, Personal Integration Plan and Expected
    Outcomes, Follow-Up Notes, Referral Details/Status/Comments, OTP
    Confirmation Status (expanded card body)
  - additional_notes is NEVER shown (the backend never returns it)
  - newest booking first (Jinja |reverse over the child table)

Reuses the same widened ism_review.get_ism_review_summary() for BOTH the
"Review & Confirm" (Pending Client Review) and "View Details" (any other
status) expand actions - one API, one renderer, no duplicated logic.

This REPLACES the previous table-based ismBookingHistory block and its
associated <script>, wherever they currently are on the page (their exact
byte offsets may have shifted from earlier manual edits).

Run: bench --site ibelong.test execute ibelong_system.ism_v3_client_cards.run
"""

import frappe

PROFILE_PAGE = "v3-progle-page"

HISTORY_BLOCK_START = '<div class="mb-4" id="ismBookingHistory">'

NEW_HISTORY_BLOCK = """<div class="mb-4" id="ismBookingHistory">
                           <h6 class="mb-3"><i class="fas fa-history me-2"></i>Your ISM Appointments</h6>
                           {% if doc_data and doc_data.ism_bookings %}
                           {% for b in doc_data.ism_bookings|reverse %}
                           <div class="card mb-3 ism-card">
                              <div class="card-body">
                                 <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
                                    <div>
                                       <strong>{{ frappe.format_value(b.slot_date, {"fieldtype": "Date"}) if b.slot_date else "-" }}</strong>
                                       at {{ frappe.format_value(b.slot_time, {"fieldtype": "Time"}) if b.slot_time else "-" }}
                                       <span class="text-muted">&middot; Officer: {{ b.officer_name or "-" }}</span>
                                    </div>
                                    <div>
                                       {% if b.booking_status == "ISM Cancelled" %}<span class="badge bg-danger">{{ b.booking_status }}</span>
                                       {% elif b.booking_status == "Pending Client Review" %}<span class="badge bg-warning text-dark">{{ b.booking_status }}</span>
                                       {% elif b.booking_status == "Case Open" %}<span class="badge bg-info text-dark">{{ b.booking_status }}</span>
                                       {% elif b.booking_status == "Case Referred" %}<span class="badge" style="background-color:#6f42c1;color:#fff;">{{ b.booking_status }}</span>
                                       {% elif b.booking_status == "Case Closed" %}<span class="badge bg-secondary">{{ b.booking_status }}</span>
                                       {% else %}<span class="badge bg-primary">{{ b.booking_status or "ISM Scheduled" }}</span>{% endif %}
                                    </div>
                                 </div>
                                 <div class="mt-2">
                                    {% if b.booking_status == "Pending Client Review" %}
                                    <button type="button" class="btn btn-sm btn-outline-primary ism-expand" data-booking="{{ b.name }}" data-target="ismCardBody{{ loop.index }}">Review &amp; Confirm</button>
                                    {% elif b.booking_status in ("Case Open", "Case Referred", "Case Closed") %}
                                    <button type="button" class="btn btn-sm btn-outline-secondary ism-expand" data-booking="{{ b.name }}" data-target="ismCardBody{{ loop.index }}">View Details</button>
                                    {% endif %}
                                 </div>
                                 <div id="ismCardBody{{ loop.index }}" class="ism-card-body mt-3" style="display:none">
                                    <div class="ism-loading text-muted"><i class="fas fa-spinner fa-spin me-1"></i>Loading&hellip;</div>
                                    <div class="ism-content" style="display:none"></div>
                                 </div>
                              </div>
                           </div>
                           {% endfor %}
                           <p class="text-muted mb-0"><small>You may book more than one Integration Support Meeting. Each appointment and its outcome is listed here, newest first.</small></p>
                           {% else %}
                           <p class="text-muted mb-0">You have not booked an Integration Support Meeting yet.</p>
                           {% endif %}
                        </div>
                        """

NEW_JS = """
<script>
document.addEventListener("DOMContentLoaded", function(){
  function esc(s){ var d=document.createElement("div"); d.innerText=(s||""); return d.innerHTML; }

  function renderIsmDetail(d){
    var itemsHtml = "";
    (d.items || []).forEach(function(i){
      itemsHtml += "<li><strong>" + esc(i.label) + "</strong>" +
        (i.notes ? " - " + esc(i.notes) : "") +
        (i.referral_category ? " (Referral: " + esc(i.referral_category) + ")" : "") +
        "</li>";
    });
    if (!itemsHtml) itemsHtml = "<li>No specific support items recorded.</li>";

    var html = "";
    html += '<p class="mb-1"><strong>Outcome:</strong> ' + esc(d.booking_status) + '</p>';
    html += '<p class="mb-1"><strong>Support Requested</strong></p>';
    html += '<ul class="mb-3">' + itemsHtml + '</ul>';
    if (d.personal_integration_plan) {
      html += '<p class="mb-1"><strong>Personal Integration Plan and Expected Outcomes</strong></p><p class="mb-3">' + esc(d.personal_integration_plan) + '</p>';
    }
    if (d.follow_up) {
      html += '<p class="mb-1"><strong>Follow-Up Notes</strong></p><p class="mb-3">' + esc(d.follow_up) + '</p>';
    }
    if (d.referred_to_provider) {
      html += '<hr><p class="mb-1"><strong>Referral Details</strong></p>';
      html += '<p class="mb-1">Referred to: ' + esc(d.referred_to_provider) + '</p>';
      if (d.referral_status) html += '<p class="mb-1">Referral Status: <span class="badge bg-secondary">' + esc(d.referral_status) + '</span></p>';
      if (d.referral_comments) html += '<p class="mb-1">Referral Comments: ' + esc(d.referral_comments) + '</p>';
    }
    html += '<hr><p class="mb-0"><strong>OTP Confirmation:</strong> ' +
      (d.client_confirmed ? ('Confirmed' + (d.client_confirmed_on ? ' on ' + esc(d.client_confirmed_on) : '')) : 'Not yet confirmed') +
      '</p>';

    if (d.booking_status === "Pending Client Review") {
      html += '<hr><p class="mb-2">Enter the confirmation code we sent you by email to confirm this summary is correct.</p>';
      html += '<div class="row g-2 align-items-center">' +
        '<div class="col-auto"><input type="text" class="form-control form-control-sm ism-otp-input" placeholder="6-digit code" maxlength="6" style="width:140px"></div>' +
        '<div class="col-auto"><button type="button" class="btn btn-success btn-sm ism-otp-confirm">Confirm</button></div>' +
        '</div><div class="ism-otp-msg mt-2"></div>';
    }
    return html;
  }

  document.querySelectorAll(".ism-expand").forEach(function(btn){
    btn.addEventListener("click", function(){
      var target = document.getElementById(btn.getAttribute("data-target"));
      if (!target) return;
      var showing = target.style.display !== "none";
      if (showing) { target.style.display = "none"; return; }
      target.style.display = "block";
      if (target.getAttribute("data-loaded") === "1") return;

      var booking = btn.getAttribute("data-booking");
      var loading = target.querySelector(".ism-loading");
      var content = target.querySelector(".ism-content");

      frappe.call({
        method: "ibelong_system.ism_review.get_ism_review_summary",
        args: { booking: booking },
        callback: function(r){
          if (loading) loading.style.display = "none";
          if (!r.message || r.message.error) {
            content.innerHTML = '<p class="text-danger mb-0">' + ((r.message && r.message.error) || "Could not load this meeting.") + '</p>';
            content.style.display = "block";
            return;
          }
          var d = r.message;
          content.innerHTML = renderIsmDetail(d);
          content.style.display = "block";
          target.setAttribute("data-loaded", "1");

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
        }
      });
    });
  });
});
</script>
"""


def _find_div_end(html, start):
    depth = 0
    i = start
    while i < len(html):
        if html.startswith("<div", i):
            depth += 1
            i += 4
            continue
        if html.startswith("</div>", i):
            depth -= 1
            i += 6
            if depth == 0:
                return i
            continue
        i += 1
    raise RuntimeError("could not find matching </div>")


def _strip_old_scripts(html):
    """Remove any previously-appended ISM history <script> blocks (old
    table-based versions used '.ism-review-toggle' / '.ism-detail-toggle'
    listeners) so we don't end up with duplicate/dead event bindings."""
    markers = ['document.querySelectorAll(".ism-review-toggle")', 'document.querySelectorAll(".ism-detail-toggle")']
    changed = True
    while changed:
        changed = False
        for marker in markers:
            idx = html.find(marker)
            if idx == -1:
                continue
            script_start = html.rfind("<script>", 0, idx)
            script_end = html.find("</script>", idx)
            if script_start == -1 or script_end == -1:
                continue
            script_end += len("</script>")
            html = html[:script_start] + html[script_end:]
            changed = True
    return html


def run():
    print("=== Rebuild ISM history as newest-first cards ===")
    html = (frappe.db.get_value("Web Page", PROFILE_PAGE, "main_section_html") or "").replace("\r\n", "\n")

    if HISTORY_BLOCK_START not in html:
        raise RuntimeError("[FAIL] ismBookingHistory block not found - page structure changed")

    start = html.index(HISTORY_BLOCK_START)
    end = _find_div_end(html, start)
    html = html[:start] + NEW_HISTORY_BLOCK + html[end:]
    print("  [ok] history block replaced with card layout")

    html = _strip_old_scripts(html)
    print("  [ok] old ISM history <script> block(s) removed")

    html = html + NEW_JS
    print("  [ok] new unified detail/expand script appended")

    frappe.db.set_value("Web Page", PROFILE_PAGE, "main_section_html", html, update_modified=True)
    frappe.db.commit()
    frappe.clear_cache()
    print("\nDone.")
