"""
Client clarification (07/08/2026): only one ACTIVE ISM case at a time.
A client may book multiple ISMs over time, but the ISM tab must be hidden
on their profile while a case is active (anything except Case Closed or
ISM Cancelled), and reappear once the active case is closed - allowing a
new booking. The client profile itself always stays accessible; only the
ISM tab is gated.

Two edits to v3-progle-page:
  1. Compute has_active_ism server-side (Jinja) and expose it via a hidden
     input, matching the existing #clientStatus / #integrationSupport
     pattern already read by toggleTabsBasedOnStatusAndIntegration().
  2. That JS function now hides the ISM nav tab when has_active_ism is true,
     instead of always showing it.
  3. Defensive click-guard on the "Book ISM Session" link: if somehow
     reached with an active case (stale cache, direct URL, etc.), show an
     alert instead of navigating to the external MS Bookings page.

Run: bench --site ibelong.test execute ibelong_system.ism_v3_one_active_case.run
"""

import frappe

PROFILE_PAGE = "v3-progle-page"

# --- 1. hidden field with the server-computed flag ---------------------------
ANCHOR_HIDDEN_FIELD = (
    'id="integrationSupport" value="{% if doc_data and doc_data.integration_support %}'
    'Yes{% else %}No{% endif %}" readonly /></div>'
)
NEW_HIDDEN_FIELD = ANCHOR_HIDDEN_FIELD + (
    '\n{% set ns = namespace(has_active_ism=false) %}'
    '{% if doc_data and doc_data.ism_bookings %}{% for b in doc_data.ism_bookings %}'
    '{% if b.booking_status not in ("Case Closed", "ISM Cancelled") %}{% set ns.has_active_ism = true %}{% endif %}'
    '{% endfor %}{% endif %}'
    '<input type="hidden" id="hasActiveIsm" value="{% if ns.has_active_ism %}Yes{% else %}No{% endif %}" />'
)

# --- 2. tab-visibility JS -----------------------------------------------------
OLD_JS_TAB_LINE = (
    '    /* NISC enhancement (30/07/2026): the ISM tab must be visible at ALL times\n'
    '       for ALL registered service users - ISM booking is fully independent of\n'
    '       I Belong course status. Never hide it. */\n'
    '    ismNI.style.display="block";'
)
NEW_JS_TAB_LINE = (
    '    /* NISC enhancement (30/07/2026): the ISM tab is visible at ALL times\n'
    '       for ALL registered service users - ISM booking is fully independent of\n'
    '       I Belong course status - EXCEPT while the client has an active ISM case\n'
    '       (client clarification 07/08/2026: only one active case at a time). */\n'
    '    var hasActiveIsmEl=getEl("hasActiveIsm");\n'
    '    var hasActiveIsm=hasActiveIsmEl&&hasActiveIsmEl.value.trim()==="Yes";\n'
    '    ismNI.style.display=hasActiveIsm?"none":"block";'
)

# --- 3. defensive popup on the Book ISM Session link --------------------------
BOOK_BTN_MARKER = 'class="btn btn-primary btn-lg" style="background-color: #6f42c1; border-color: #6f42c1; padding: 12px 30px; font-size: 1.1rem;"><i class="fas fa-external-link-alt me-2"></i>Book ISM Session</a>'

GUARD_SCRIPT = """
<script>
document.addEventListener("DOMContentLoaded", function(){
  document.querySelectorAll('a.btn-primary').forEach(function(a){
    if (a.textContent.indexOf("Book ISM Session") === -1) return;
    a.addEventListener("click", function(e){
      var flag = document.getElementById("hasActiveIsm");
      if (flag && flag.value.trim() === "Yes") {
        e.preventDefault();
        alert("Please complete your current active ISM meeting first.");
      }
    });
  });
});
</script>
"""


def run():
    print("=== One active ISM case at a time: tab gating ===")
    html = (frappe.db.get_value("Web Page", PROFILE_PAGE, "main_section_html") or "").replace("\r\n", "\n")

    if ANCHOR_HIDDEN_FIELD in html:
        html = html.replace(ANCHOR_HIDDEN_FIELD, NEW_HIDDEN_FIELD, 1)
        print("  [ok] hasActiveIsm hidden field added")
    elif 'id="hasActiveIsm"' in html:
        print("  [skip] hasActiveIsm field already present")
    else:
        raise RuntimeError("[FAIL] integrationSupport field anchor not found")

    if OLD_JS_TAB_LINE in html:
        html = html.replace(OLD_JS_TAB_LINE, NEW_JS_TAB_LINE, 1)
        print("  [ok] toggleTabsBasedOnStatusAndIntegration() now gates on has_active_ism")
    elif "hasActiveIsm" in html and 'ismNI.style.display=hasActiveIsm' in html:
        print("  [skip] tab-gating JS already updated")
    else:
        raise RuntimeError("[FAIL] expected JS tab-visibility block not found")

    if BOOK_BTN_MARKER in html and GUARD_SCRIPT not in html:
        html = html + GUARD_SCRIPT
        print("  [ok] defensive popup script added to Book ISM Session button")
    elif GUARD_SCRIPT in html:
        print("  [skip] defensive popup script already present")
    else:
        raise RuntimeError("[FAIL] Book ISM Session button marker not found")

    frappe.db.set_value("Web Page", PROFILE_PAGE, "main_section_html", html, update_modified=True)
    frappe.db.commit()
    frappe.clear_cache()
    print("\nDone.")
