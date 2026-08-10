"""
Fix "Client Details FN-12345 not found" on the v3 profile page's Course
Selection tab.

Root cause: the readonly #fileNumber input defaults its VALUE (not just
placeholder text) to the literal string "FN-12345" whenever
doc_data.file_number is empty. JS then reads that fake value and submits it
to submit_stage1_certificate / submit_stage2_culture_only as `fileno`, which
fails both of the server's lookups (file_number match, or fileno-as-docname).

Fix: fall back to doc_data.name (the client's real docname) instead of a
fake placeholder. The server-side handlers already support using the docname
directly as `fileno` (frappe.db.exists("Client Details", fileno)), so this
resolves cleanly - and Stage 2's handler even self-heals by writing that
value back as the client's file_number.

Unrelated to ISM/registration - this only touches the Course Selection tab's
File Number field.

Run: bench --site ibelong.test execute ibelong_system.ism_v3_fix_filenumber.run
"""

import frappe

PROFILE_PAGE = "v3-progle-page"

OLD = '{% if doc_data and doc_data.file_number %}{{ doc_data.file_number }}{% else %}FN-12345{% endif %}" readonly /></div>'
NEW = '{% if doc_data and doc_data.file_number %}{{ doc_data.file_number }}{% else %}{{ doc_data.name }}{% endif %}" readonly /></div>'


def run():
    print("=== Fix File Number fake-placeholder bug ===")
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
    print("  [ok] File Number now falls back to the client's real docname instead of a fake placeholder")
    print("\nDone.")
