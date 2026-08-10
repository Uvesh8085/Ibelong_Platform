"""
Batch 2 - portal/profile page ISM tab (enhancement 2).

Adds, as the FIRST thing on the v3 profile page ISM tab:
  - the "Integration Support Meeting (OPTIONAL)" intro,
  - a "What kind of support do you need?" dropdown (full ISM support list),
  - an "Other Support -> Please Specify" free-text field,
  - a Save button that persists to Client Details (ism_support_need / ism_support_other)
    via the existing update_client_and_sync_email API, so it reaches NISC staff.

Also: expands the ism_support_need Select options to the full ISM list and adds
the ism_support_other custom field.

Run: bench --site ibelong.test execute ibelong_system.ism_portal_support.run
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

PROFILE_PAGE = "v3-progle-page"

SUPPORT_OPTIONS = (
    "\nEmployment Assistance\nEducational Support\nDocumentation Assistance\n"
    "Family Support\nAccommodation Support\nHealth Services\n"
    "Well-being / Mental Health Support\nSocial Integration Activities\n"
    "Legal Assistance\nOther Support"
)

ANCHOR = (
    '<div class="calendar-container">\n'
    '                        <h5 class="section-title">Select Date and Time for ISM Session</h5>'
)

SUPPORT_BLOCK = """<div class="calendar-container">
                        <div class="mb-4" id="ismSupportBlock">
                           <h5 class="section-title">Integration Support Meeting (OPTIONAL)</h5>
                           <p>The Integration Support Meeting (ISM) is optional and can be booked if integration assistance is required.</p>
                           <p>The one-to-one meeting with a member of the National Integration Support Centre team is designed to help you understand and access the services, opportunities, and support available as you settle and build your life in Malta.</p>
                           <p>The meeting is free of charge and aims to help you identify the integration support best suited to your individual needs.</p>
                           <h6 class="mt-4 fw-bold">What kind of support do you need?</h6>
                           <p class="text-muted">Please tell us what type of support you are seeking. This information will help us prepare for your meeting and identify any services that may be relevant to your situation.</p>
                           <div class="row g-3 align-items-end">
                              <div class="col-md-6">
                                 <label for="ismSupportNeedPortal" class="form-label">Support needed</label>
                                 <select class="form-select" id="ismSupportNeedPortal">
                                    <option value="">Select support type&hellip;</option>
                                    {% for opt in ["Employment Assistance","Educational Support","Documentation Assistance","Family Support","Accommodation Support","Health Services","Well-being / Mental Health Support","Social Integration Activities","Legal Assistance","Other Support"] %}
                                    <option {% if doc_data and doc_data.ism_support_need == opt %}selected{% endif %}>{{ opt }}</option>
                                    {% endfor %}
                                 </select>
                              </div>
                              <div class="col-md-6" id="ismSupportOtherWrap" style="display:none">
                                 <label for="ismSupportOther" class="form-label">Please Specify</label>
                                 <input type="text" class="form-control" id="ismSupportOther" value="{% if doc_data and doc_data.ism_support_other %}{{ doc_data.ism_support_other }}{% endif %}">
                              </div>
                           </div>
                           <div class="mt-2">
                              <button type="button" class="btn btn-outline-primary btn-sm" id="saveIsmSupport"><i class="fas fa-save me-1"></i>Save support need</button>
                              <span id="ismSupportSaved" class="text-success ms-2" style="display:none">Saved &#10003;</span>
                           </div>
                           <hr class="my-4">
                        </div>
                        <h5 class="section-title">Select Date and Time for ISM Session</h5>"""

SUPPORT_JS = """
<script>
document.addEventListener("DOMContentLoaded", function(){
  var sel=document.getElementById("ismSupportNeedPortal");
  if(!sel) return;
  var otherWrap=document.getElementById("ismSupportOtherWrap");
  var otherInp=document.getElementById("ismSupportOther");
  var saveBtn=document.getElementById("saveIsmSupport");
  var savedMsg=document.getElementById("ismSupportSaved");
  function toggleOther(){ if(otherWrap) otherWrap.style.display=(sel.value==="Other Support")?"block":"none"; }
  toggleOther(); sel.addEventListener("change", toggleOther);
  if(saveBtn) saveBtn.addEventListener("click", function(){
    var fnEl=document.getElementById("fileNumber");
    var fn=fnEl?(fnEl.value||fnEl.getAttribute("value")||""):"";
    if(!fn){ alert("File number missing - cannot save support need."); return; }
    var fields={ ism_support_need: sel.value||"", ism_support_other:(sel.value==="Other Support"&&otherInp)?(otherInp.value||""):"" };
    frappe.call({ method:"ibelong_system.update_user.update_client_and_sync_email",
      args:{ doctype:"Client Details", name:fn, fieldname:fields },
      callback:function(r){ if(savedMsg){ savedMsg.style.display="inline"; setTimeout(function(){savedMsg.style.display="none";},2500);} },
      error:function(e){ alert("Could not save support need. Please try again."); }
    });
  });
});
</script>
"""


def run():
    print("=== Batch 2: portal ISM support dropdown ===")

    # 1. field schema
    cf = "Client Details-ism_support_need"
    if frappe.db.exists("Custom Field", cf):
        frappe.db.set_value("Custom Field", cf, "options", SUPPORT_OPTIONS)
        print("  [ok] expanded ism_support_need options to full ISM list")
    create_custom_fields(
        {"Client Details": [
            {"fieldname": "ism_support_other", "label": "Support Needed - Please Specify",
             "fieldtype": "Data", "insert_after": "ism_support_need", "translatable": 0,
             "depends_on": "eval:doc.ism_support_need=='Other Support'"},
        ]},
        update=True,
    )
    print("  [ok] ism_support_other field ensured")

    # 2. profile page injection
    html = (frappe.db.get_value("Web Page", PROFILE_PAGE, "main_section_html") or "").replace("\r\n", "\n")
    if "ismSupportNeedPortal" in html:
        print("  [skip] support block already present")
    else:
        if ANCHOR not in html:
            raise RuntimeError("[FAIL] ISM tab anchor not found on profile page")
        html = html.replace(ANCHOR, SUPPORT_BLOCK, 1)
        # append the JS once, before the last </div> of the page body is risky; append at end
        html = html + SUPPORT_JS
        frappe.db.set_value("Web Page", PROFILE_PAGE, "main_section_html", html, update_modified=True)
        print("  [ok] injected support block + JS into ISM tab")

    frappe.db.commit()
    frappe.clear_cache()
    print("\nDone. Portal ISM tab now leads with the support question; selection saves to Client Details.")
