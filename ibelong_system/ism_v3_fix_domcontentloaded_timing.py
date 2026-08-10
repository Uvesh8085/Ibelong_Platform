"""
Real bug found via live browser testing on the test server: the client
profile page is one large document with many inline <script> blocks appended
over the course of this feature's development. Several of them wrap their
logic in:

    document.addEventListener("DOMContentLoaded", function(){ ... });

That's wrong for a <script> tag that is itself part of the initial HTML
document - DOMContentLoaded fires once, after the whole document is parsed.
By the time a LATER inline script (deep in a large page) executes, that
event may already have fired (order/timing dependent, so it can look like it
"works" locally and silently fails elsewhere). The listener then waits for
an event that will never come again - no errors, nothing happens, exactly
what broke the "View Details" / "Review & Confirm" buttons on the ISM
appointment cards (confirmed live: the button and DOM were fine - manually
re-binding the same click listener in DevTools worked immediately).

Fix: rewrite every such block to run immediately if the document is already
past "loading", and only fall back to the DOMContentLoaded listener if it's
still actually loading - the standard safe pattern for inline scripts.

Run: bench --site ibelong.test execute ibelong_system.ism_v3_fix_domcontentloaded_timing.run

On a different environment where the profile page has a different Web Page
docname, override before calling run():
    import ibelong_system.ism_v3_fix_domcontentloaded_timing as m
    m.PROFILE_PAGE = "client-profile-page-v3"
    m.run()
"""

import frappe

PROFILE_PAGE = "v3-progle-page"

MARKER = 'document.addEventListener("DOMContentLoaded", function(){'


def _find_function_end(html, start):
    """Index just past the matching closing brace for the function(){ that
    begins at/after `start`."""
    open_brace = html.index("{", start)
    depth = 0
    i = open_brace
    while i < len(html):
        c = html[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise RuntimeError("Could not find matching closing brace")


def run():
    print("=== Fix DOMContentLoaded timing bug on profile page ===")
    print(f"    target page: {PROFILE_PAGE}")
    html = (frappe.db.get_value("Web Page", PROFILE_PAGE, "main_section_html") or "").replace("\r\n", "\n")
    if not html:
        raise RuntimeError(f"[FAIL] Web Page '{PROFILE_PAGE}' not found or empty")

    count = 0
    search_from = 0
    while True:
        idx = html.find(MARKER, search_from)
        if idx == -1:
            break

        func_kw = html.index("function(){", idx)
        body_start = func_kw + len("function(){")
        end = _find_function_end(html, func_kw)  # just past the function's closing '}'
        tail = html[end:end + 2]
        if tail != ");":
            raise RuntimeError(f"[FAIL] unexpected trailing characters after DOMContentLoaded block: {tail!r}")
        full_end = end + 2

        body = html[body_start:end - 1]  # inner body only, excluding function(){ ... }

        replacement = (
            "(function(){function _ibelongReady(){" + body + "}"
            'if(document.readyState==="loading"){'
            'document.addEventListener("DOMContentLoaded",_ibelongReady);'
            "}else{_ibelongReady();}})();"
        )

        html = html[:idx] + replacement + html[full_end:]
        count += 1
        search_from = idx + len(replacement)

    if count == 0:
        print("  [skip] no DOMContentLoaded-wrapped blocks found (already fixed, or none present)")
    else:
        frappe.db.set_value("Web Page", PROFILE_PAGE, "main_section_html", html, update_modified=True)
        frappe.db.commit()
        frappe.clear_cache()
        print(f"  [ok] rewrote {count} DOMContentLoaded block(s) to run immediately once the DOM is ready")

    print("\nDone. Hard-refresh the profile page and retest.")
