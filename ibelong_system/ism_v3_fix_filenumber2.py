"""
Second instance of the File Number empty-value bug: the small "client-id"
badge under the client's name (id="clientIdDisplay") shows doc_data.file_number
with NO fallback at all, so it renders as an empty badge/dot when file_number
is unset - which is what showed up as an empty purple dot on the profile page.

Same fix as ism_v3_fix_filenumber.py: fall back to doc_data.name (the real
client docname) so the badge always shows something meaningful.

Run: bench --site ibelong.test execute ibelong_system.ism_v3_fix_filenumber2.run
"""

import frappe

PROFILE_PAGE = "v3-progle-page"

OLD = '<span class="client-id" id="clientIdDisplay">{% if doc_data and doc_data.file_number %}{{ doc_data.file_number }}{% endif %}</span>'
NEW = '<span class="client-id" id="clientIdDisplay">{% if doc_data and doc_data.file_number %}{{ doc_data.file_number }}{% elif doc_data %}{{ doc_data.name }}{% endif %}</span>'


def run():
    print("=== Fix second File Number empty-badge bug (clientIdDisplay) ===")
    html = (frappe.db.get_value("Web Page", PROFILE_PAGE, "main_section_html") or "").replace("\r\n", "\n")

    if OLD not in html:
        if NEW in html:
            print("  [skip] already fixed")
            return
        raise RuntimeError("[FAIL] expected pattern not found - page structure changed")

    html = html.replace(OLD, NEW, 1)
    frappe.db.set_value("Web Page", PROFILE_PAGE, "main_section_html", html, update_modified=True)
    frappe.db.commit()
    frappe.clear_cache()
    print("  [ok] clientIdDisplay now falls back to the client's real docname")
    print("\nDone.")
