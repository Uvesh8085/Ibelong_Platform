# ibelong_system/otp_verify.py

import random
import frappe
from frappe import _
from ibelong_system.mail_api import email_api  # your SMS sender


def get_client_by_mobile(full_mobile):
    """full_mobile example: +35699112233 or +919876543210"""

    # Normalise: remove spaces/dashes
    number = (full_mobile or "").replace(" ", "").replace("-", "")

    # Accept + or 00, but internally we work with +
    if number.startswith("00"):
        number = "+" + number[2:]
    elif not number.startswith("+"):
        frappe.throw(_("Mobile number must start with country code (e.g. +35699112233 or 0035699112233)."))

    # Special-case Malta if you really need it
    if number.startswith("+356"):
        cc = "+356"
        mob = number[4:]
    else:
        # default: +91..., +44..., +49..., etc.
        cc = number[:3]
        mob = number[3:]

    if not mob.isdigit():
        frappe.throw(_("Invalid mobile number format."))

    client = frappe.db.get_value(
        "Client Details",
        {"country_code": cc, "mobile_number": mob},
        ["first_name", "email", "country_code", "mobile_number"],
        as_dict=True,
    )

    if not client:
        frappe.throw(_("No client found with mobile number {0}").format(full_mobile))

    return client

@frappe.whitelist(allow_guest=True)
def send_mobile_login_otp(mobile):
    """
    mobile: what user typed, e.g. "+918085037259" or "0035680..."
    """

    # 1️⃣ Normalise for lookup & SMS – always keep + (gateway wants + or 00)
    raw = (mobile or "").strip().replace(" ", "").replace("-", "")

    if raw.startswith("00"):
        normalized = "+" + raw[2:]
    else:
        normalized = raw

    if not normalized.startswith("+"):
        frappe.throw(_("Provide an international mobile number starting with + or 00 (e.g., +9180...)."))

    # 2️⃣ Find client in Client Details
    client = get_client_by_mobile(normalized)
    client_name = client.first_name

    # 3️⃣ Generate & cache OTP (key based on normalized +number)
    otp = random.randint(100000, 999999)
    cache_key = f"mobile_login_otp:{normalized}"

    frappe.cache().set_value(
        cache_key,
        {"otp": str(otp), "mobile": normalized},
        expires_in_sec=300,
    )

    # 4️⃣ SMS body (EN + MT)
    sms_body_en = (
        f"Dear {client_name}, your login OTP is {otp}. "
        f"It is valid for 5 minutes."
    )

    sms_body_mt = (
        f"Għażiż {client_name}, il-kodiċi OTP tiegħek biex tidħol fis-sistema huwa {otp}. "
        f"Jidvalidu għal 5 minuti."
    )

    mobile_for_sms = normalized  # e.g. "+918085037259"

    sms_params = {
        "type": "sms",
        "displayname": "Ibelong System",
        "firstname": client_name,
        "lastname": "",
        "mobile": mobile_for_sms,
        "subjectEN": "Login OTP",
        "bodyEN": sms_body_en,
        "subjectMT": "Login OTP",
        "bodyMT": sms_body_mt,
    }

    frappe.log_error(
        "LOGIN OTP - SMS PARAMS",
        frappe.as_json({
            "input_mobile": mobile,
            "normalized": normalized,
            "mobile_for_sms": mobile_for_sms,
            "sms_params": sms_params
        })
    )

    old_form_dict = getattr(frappe.local, "form_dict", None)
    try:
        frappe.local.form_dict = frappe._dict()
        frappe.local.form_dict.params = sms_params
        sms_response = email_api.send_email_notification()
    finally:
        if old_form_dict is not None:
            frappe.local.form_dict = old_form_dict
        elif hasattr(frappe.local, "form_dict"):
            del frappe.local.form_dict

    frappe.log_error("LOGIN OTP - SMS RESPONSE", frappe.as_json(sms_response))

    # ✅ SUCCESS CHECK: any status_code < 400 is OK
    status_code = None
    status = None
    if isinstance(sms_response, dict):
        status_code = sms_response.get("status_code")
        status = sms_response.get("status")

    # if provider explicitly says error or status_code >= 400 → treat as failure
    if (status_code is not None and int(status_code) >= 400) or status == "error":
        msg = sms_response if isinstance(sms_response, str) else frappe.as_json(sms_response)
        frappe.throw(_("Failed to send OTP. Provider response: {0}").format(msg))

    # 👉 If we reach here, OTP is sent successfully
    return {
        "status": "success",
        "message": "OTP sent to your registered mobile number"
    }


@frappe.whitelist(allow_guest=True)
def verify_mobile_login_otp(mobile, otp):
    # Same normalization as send_mobile_login_otp
    raw = (mobile or "").strip().replace(" ", "").replace("-", "")

    if raw.startswith("00"):
        normalized = "+" + raw[2:]
    else:
        normalized = raw

    if not normalized.startswith("+"):
        frappe.throw(_("Provide an international mobile number starting with + or 00 (e.g., +9180...)."))

    cache_key = f"mobile_login_otp:{normalized}"
    data = frappe.cache().get_value(cache_key)

    if not data:
        frappe.throw(_("OTP expired or not found. Please request a new one."))

    if str(data.get("otp")) != str(otp):
        frappe.throw(_("Invalid OTP. Please try again."))

    # OTP valid → find client → login using email
    client = get_client_by_mobile(normalized)
    user_email = client.email

    frappe.cache().delete_value(cache_key)

    login_manager = frappe.auth.LoginManager()
    login_manager.login_as(user_email)

    return {
        "status": "success",
        "message": "Logged in successfully",
        "user": user_email,
        "sid": frappe.session.sid,
    }
