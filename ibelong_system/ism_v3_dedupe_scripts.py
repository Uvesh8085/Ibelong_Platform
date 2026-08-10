"""
Real bug found via live testing: the client profile page has exact-duplicate
inline <script> blocks - at least the ISM card detail script (renderIsmDetail
/ .ism-expand) appears twice. This is a side effect of ism_v3_client_cards.py
(and similar scripts) appending their trailing <script> to main_section_html
unconditionally, with no guard against being run twice against the same
content - which evidently happened at some point before this page's current
content was put in place.

With TWO identical listeners bound to the same .ism-expand button, a single
real click fires both synchronously: the first opens the detail box and
kicks off the API call, the second immediately sees the box is now
"showing" and closes it again - all within the same click event, so nothing
is ever visibly rendered, no errors, no way to tell anything ran at all.
(Manually pasting a single copy of the same code into DevTools worked
perfectly, which is what proved this.)

This removes exact-duplicate <script>...</script> blocks anywhere on the
page, keeping only the LAST copy of each - safe because a truly
byte-identical duplicate is by definition redundant (each block is
self-contained/IIFE-scoped, so there's no cross-block state to lose).

Run: bench --site ibelong.test execute ibelong_system.ism_v3_dedupe_scripts.run

On a different environment where the profile page has a different Web Page
docname, override before calling run():
    import ibelong_system.ism_v3_dedupe_scripts as m
    m.PROFILE_PAGE = "client-profile-page-v3"
    m.run()
"""

import frappe

PROFILE_PAGE = "v3-progle-page"


def _find_all_script_blocks(html):
    """List of (start, end) spans for every <script>...</script> block."""
    blocks = []
    i = 0
    while True:
        start = html.find("<script>", i)
        if start == -1:
            break
        end = html.find("</script>", start)
        if end == -1:
            break
        end += len("</script>")
        blocks.append((start, end))
        i = end
    return blocks


def run():
    print("=== Remove exact-duplicate <script> blocks on profile page ===")
    print(f"    target page: {PROFILE_PAGE}")
    html = (frappe.db.get_value("Web Page", PROFILE_PAGE, "main_section_html") or "").replace("\r\n", "\n")
    if not html:
        raise RuntimeError(f"[FAIL] Web Page '{PROFILE_PAGE}' not found or empty")

    blocks = _find_all_script_blocks(html)
    print(f"  total <script> blocks found: {len(blocks)}")

    seen = set()
    keep = [True] * len(blocks)
    # Walk backwards so the LAST occurrence of each duplicate is the one kept.
    for idx in range(len(blocks) - 1, -1, -1):
        s, e = blocks[idx]
        content = html[s:e]
        if content in seen:
            keep[idx] = False
        else:
            seen.add(content)

    removed = sum(1 for k in keep if not k)
    if removed == 0:
        print("  [skip] no exact-duplicate script blocks found")
        print("\nDone.")
        return

    for idx in range(len(blocks) - 1, -1, -1):
        if not keep[idx]:
            s, e = blocks[idx]
            html = html[:s] + html[e:]

    frappe.db.set_value("Web Page", PROFILE_PAGE, "main_section_html", html, update_modified=True)
    frappe.db.commit()
    frappe.clear_cache()
    print(f"  [ok] removed {removed} duplicate script block(s), kept one copy of each")
    print("\nDone. Hard-refresh and retest 'View Details'.")
