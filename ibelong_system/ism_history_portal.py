"""
Show the client's FULL ISM booking history on the portal profile page.

Clients can now book more than one ISM, so the ISM tab lists every appointment
from the ism_bookings child table (date, time, officer, status) instead of only
the current slot. Migrated single-field bookings appear too, because they were
backfilled into the same table.

Run: bench --site ibelong.test execute ibelong_system.ism_history_portal.run
"""

import frappe

PROFILE_PAGE = "v3-progle-page"

# Unique element that directly follows the "current slot" block, so the history
# table is inserted between them without disturbing the surrounding markup.
ANCHOR = '                        <div class="alert alert-warning d-flex align-items-start gap-2 mt-3">'

HISTORY_BLOCK = """                        <div class="mb-4" id="ismBookingHistory">
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
                                          {% if b.booking_status == "Cancelled" %}<span class="badge bg-danger">{{ b.booking_status }}</span>
                                          {% elif b.booking_status == "Attended" %}<span class="badge bg-success">{{ b.booking_status }}</span>
                                          {% elif b.booking_status == "Not Attended" %}<span class="badge bg-secondary">{{ b.booking_status }}</span>
                                          {% elif b.booking_status == "Rescheduled" %}<span class="badge bg-warning text-dark">{{ b.booking_status }}</span>
                                          {% else %}<span class="badge bg-primary">{{ b.booking_status or "Scheduled" }}</span>{% endif %}
                                       </td>
                                    </tr>
                                    {% endfor %}
                                 </tbody>
                              </table>
                           </div>
                           <p class="text-muted mb-0"><small>You may book more than one Integration Support Meeting. Each appointment you book is listed here.</small></p>
                           {% else %}
                           <p class="text-muted mb-0">You have not booked an Integration Support Meeting yet.</p>
                           {% endif %}
                        </div>
"""


def run():
    print("=== Portal: ISM booking history list ===")
    html = (frappe.db.get_value("Web Page", PROFILE_PAGE, "main_section_html") or "").replace("\r\n", "\n")

    if "ismBookingHistory" in html:
        print("  [skip] history block already present")
        return

    if ANCHOR not in html:
        raise RuntimeError("[FAIL] ISM current-slot anchor not found on profile page")

    html = html.replace(ANCHOR, HISTORY_BLOCK + ANCHOR, 1)
    frappe.db.set_value("Web Page", PROFILE_PAGE, "main_section_html", html, update_modified=True)
    frappe.db.commit()
    frappe.clear_cache()
    print("  [ok] booking history table injected into ISM tab")
