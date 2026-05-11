import json

import frappe
import frappe.utils
from frappe.utils.oauth import login_via_oauth2, login_via_oauth2_id_token
def corp_id_token_decoder(raw):
    # raw is bytes from the HTTP response body
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")

    data = json.loads(raw)

    # Provider only returns id_token, but rauth expects access_token
    if "access_token" not in data and "id_token" in data:
        data["access_token"] = data["id_token"]

    return data


@frappe.whitelist(allow_guest=True)
def integration_corp():
    frappe.log_error("login in login_via .py with aouth.py")
    request_data = frappe.form_dict

    try:
        provider = "eid_or_corp_login"
        frappe.log_error("provider -->>>in login_via .py", provider)
        frappe.log_error("request_data in login_via .py", request_data)

        code = request_data.get("code")
        state = request_data.get("state")

        frappe.log_error("code in login_via .py", code)
        frappe.log_error("state in login_via .py", state)

        # 🔴 IMPORTANT: pass the custom decoder here
        login_via_oauth2_id_token(provider, code, state, decoder=corp_id_token_decoder)

        frappe.log_error("login_via_oauth2_id_token in login_via .py", "success")

    except Exception as e:
        frappe.log_error("error occured in login via", frappe.get_traceback())
        # returning raw exception object is not ideal, but keeping your behaviour
        return str(e)


# test eid login ->

# @frappe.whitelist(allow_guest=True)
# def login():
#     request_data=frappe.form_dict
#     try:
#         provider="eid_or_corp"
#         frappe.log_error("provider in login_via .py", provider)
#         code = request_data.get("code")
#         state = request_data.get("state")
#         login_via_oauth2_id_token(provider,code ,state )
#         frappe.log_error("login_via_oauth2_id_token in login_via .py", login_via_oauth2_id_token)

#     except Exception as e:
#         return e


# /home/frappe-user/whistleblower_frappe2/apps/frappe/frappe/utils/oauth.py

# In [2]:
