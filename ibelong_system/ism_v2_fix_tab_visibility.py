"""
The ISM tab on the client profile page (client_profile_v3) must be visible at
ALL times for ALL registered service users (NISC enhancement doc, 30/07/2026).

The page's toggleTabsBasedOnStatusAndIntegration() JS function currently hides
the ISM nav item unless integration_support=="Yes" AND the client's course
status is in an old allowlist. Since registration no longer sets
integration_support, and course status has nothing to do with ISM eligibility,
this made the tab invisible for effectively everyone.

This patch replaces that function in place (operating on whatever is
currently stored, since it may have been hand-edited) so the ISM nav item is
always shown, while leaving the Course Selection tab's own status-driven
display logic untouched.

Run: bench --site ibelong.test execute ibelong_system.ism_v2_fix_tab_visibility.run
"""

import re

import frappe

PROFILE_PAGE = "v3-progle-page"

FUNC_START_MARKER = "function toggleTabsBasedOnStatusAndIntegration(){"

NEW_FUNCTION = """function toggleTabsBasedOnStatusAndIntegration(){
    var sf=getEl("clientStatus"),isf=getEl("integrationSupport");
    var ism=getEl("ism-tab"),crs=getEl("course-tab");
    var ismNI=ism&&ism.closest("li"),crsNI=crs&&crs.closest("li");
    var nxtBtn=getEl("nextToIsm"),bakBtn=getEl("backToIsm");
    if(!sf||!isf||!ismNI||!crsNI)return;
    var status=sf.value.trim();

    /* NISC enhancement (30/07/2026): the ISM tab must be visible at ALL times
       for ALL registered service users - ISM booking is fully independent of
       I Belong course status. Never hide it. */
    ismNI.style.display="block";

    /* Course Selection tab keeps its previous status-driven behaviour. */
    var ismPausedUntil=new Date('2026-07-27T00:00:00');
    var newFlowStatuses=["Registration Complete","Pending Eligibility Verification","Stage 1 Requirement Completed","Stage 1 Not Eligible"];
    crsNI.style.display="block";
    if(new Date()<ismPausedUntil || newFlowStatuses.includes(status)){
        if(bakBtn)bakBtn.style.display="none";
        if(nxtBtn)nxtBtn.style.display="none";
        return;
    }
    if(bakBtn)bakBtn.style.display="none";
    if(nxtBtn){nxtBtn.onclick=function(){new bootstrap.Tab(crs).show();};nxtBtn.style.display="inline-block";}
}"""


def _find_function_end(html, start):
    """Find the index just past the matching closing brace for the function
    starting at `start` (which points at 'function ...(){')."""
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
    print("=== Fix ISM tab visibility on profile page ===")
    html = (frappe.db.get_value("Web Page", PROFILE_PAGE, "main_section_html") or "").replace("\r\n", "\n")

    if FUNC_START_MARKER not in html:
        raise RuntimeError("[FAIL] toggleTabsBasedOnStatusAndIntegration() not found - page structure changed")

    start = html.index(FUNC_START_MARKER)
    end = _find_function_end(html, start)
    old_func = html[start:end]

    if old_func.strip() == NEW_FUNCTION.strip():
        print("  [skip] function already matches the fixed version")
    else:
        html = html[:start] + NEW_FUNCTION + html[end:]
        frappe.db.set_value("Web Page", PROFILE_PAGE, "main_section_html", html, update_modified=True)
        print("  [ok] toggleTabsBasedOnStatusAndIntegration() replaced - ISM tab always visible now")

    frappe.db.commit()
    frappe.clear_cache()
    print("\nDone.")
