"""
Cosmetic fix from live testing: the OTP Confirmation timestamp on the ISM
detail card showed the raw stored value including seconds and microseconds
(e.g. "2026-08-10 12:23:21.721964"). Trims display to "YYYY-MM-DD HH:MM".

client_confirmed_on is always set via frappe.utils.now(), which is always
"YYYY-MM-DD HH:MM:SS.ffffff" - the first 16 characters are always exactly
"YYYY-MM-DD HH:MM", so a plain slice is safe and needs no date parsing.

Patches the EXISTING ISM card script in place - does NOT re-run
ism_v3_client_cards.py, which appends its trailing <script> unconditionally
and would duplicate it if run again.

Run: bench --site ibelong.test execute ibelong_system.ism_v3_trim_confirmed_on.run

On a different environment where the profile page has a different Web Page
docname, override before calling run():
    import ibelong_system.ism_v3_trim_confirmed_on as m
    m.PROFILE_PAGE = "client-profile-page-v3"
    m.run()
"""

import frappe

PROFILE_PAGE = "v3-progle-page"

OLD = "esc(d.client_confirmed_on)"
NEW = "esc((d.client_confirmed_on || '').slice(0,16))"


def run():
    print("=== Trim seconds/microseconds from OTP Confirmation timestamp ===")
    print(f"    target page: {PROFILE_PAGE}")
    html = (frappe.db.get_value("Web Page", PROFILE_PAGE, "main_section_html") or "").replace("\r\n", "\n")
    if not html:
        raise RuntimeError(f"[FAIL] Web Page '{PROFILE_PAGE}' not found or empty")

    if OLD not in html:
        if NEW in html:
            print("  [skip] already trimmed")
        else:
            raise RuntimeError("[FAIL] anchor not found - page structure changed")
    else:
        count = html.count(OLD)
        html = html.replace(OLD, NEW)
        frappe.db.set_value("Web Page", PROFILE_PAGE, "main_section_html", html, update_modified=True)
        frappe.db.commit()
        frappe.clear_cache()
        print(f"  [ok] replaced {count} occurrence(s)")

    print("\nDone. Hard-refresh and re-check a confirmed ISM's detail card.")
