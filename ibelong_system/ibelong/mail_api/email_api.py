import frappe
import requests
import uuid
import hashlib
import hmac
import urllib.parse
import datetime
import pytz
import json
import base64


key = "D7B69EFA56BB4C8683612DCBB94A2B90"
secret = "EjHivEIA5r84f3VmNvbnxYVoH11Gsj+XT9e2oo3Ipcg="
email_sender_id = "4be06987-df99-4820-be56-a74545b26788"
request_uri = "https://notifications-api.gov.mt/api/v1/messages"


data_new = frappe.form_dict
frappe.log_error("working -->>data",data_new)

@frappe.whitelist(allow_guest=True)
def send_email_notification():
    args = frappe.request.args
    form_data = frappe.form_dict
    frappe.log_error("Incoming Data", form_data)

    # Extract params (email info)
    params = form_data.get("params", {})

    # Extract payload if needed
    payload_raw = form_data.get("payload")
    if payload_raw:
        try:
            payload_data = json.loads(payload_raw.replace("'", '"'))  # safe load
            frappe.log_error("Parsed Payload", payload_data)
        except Exception as e:
            frappe.log_error("Payload Parse Error", str(e))
            payload_data = {}

    # Build email data from params
    data = {
        "type": params.get("type", "email"),
        "displayname": params.get("displayname", ""),
        "firstname": params.get("firstname", ""),
        "lastname": params.get("lastname", ""),
        "email": params.get("email", ""),
        "mobile": params.get("mobile", ""),
        "subjectEN": params.get("subjectEN", ""),
        "bodyEN": params.get("bodyEN", ""),
        "subjectMT": params.get("subjectMT", ""),
        "bodyMT": params.get("bodyMT", ""),
        "FileName": params.get("FileName"),
        "ContentStream": params.get("ContentStream"),
        "ContentType": params.get("ContentType"),
    }

    mobile = data["mobile"]
    if mobile and not mobile.startswith("00356"):
        mobile = "00356" + mobile

    emails = params.get("emails") or [params.get("email")]  # list of emails


# Build contacts (multiple emails, same mobile)
    contacts = []
    for email in emails:
        contacts.append({
        "DisplayName": data["displayname"],
        "Title": None,
        "FirstName": data["firstname"],
        "LastName": data["lastname"],
        "Email": email,
        "MobileNo": mobile    # always same mobile
    })


    sender_id = sms_sender_id if data["type"] == "sms" else email_sender_id



    attachments = None
    if data["type"] == "email" and data["FileName"] and data["FileName"] != "null":
        attachments = [{
            "ContentStream": data["ContentStream"],
            "FileName": data["FileName"],
            "ContentType": data["ContentType"]
        }]

    scheduled_delivery = datetime.datetime.now(pytz.timezone("Europe/Malta")).isoformat()
    client_reference = str(uuid.uuid4())
    nonce = str(uuid.uuid4())
    timestamp = str(int(datetime.datetime.now().timestamp()))
    encoded_request_uri = urllib.parse.quote(request_uri, safe="").lower()


    if data["type"] == "sms":

        payload = {
            "Contacts": [{
                "DisplayName": data["displayname"],
                "Title": None,
                "FirstName": data["firstname"],
                "LastName": data["lastname"],
                "Email": data["email"],
                "MobileNo": mobile
            }],
            "MessageContent": [
                {
                    "Language": 1,
                    "MessageBody": data["bodyEN"]
                },
                {
                    "Language": 6,
                    "MessageBody": data["bodyMT"]
                }
            ],
            "ClientReference": client_reference,
            "MessageType": data["type"],
            "MessagePriority": "100",
            "SenderId": sender_id,
            "CallbackUrl": None,
            "ScheduledDeliveryDate": scheduled_delivery
        }
    else:

        payload = {
            "Contacts": contacts,
            "MessageContent": [
                {
                    "Language": 1,
                    "Subject": data["subjectEN"],
                    "MessageBody": data["bodyEN"],
                    "Attachments": attachments
                },
                {
                    "Language": 6,
                    "Subject": data["subjectMT"],
                    "MessageBody": data["bodyMT"],
                    "Attachments": None
                }
            ],
            "ClientReference": client_reference,
            "MessageType": data["type"],
            "MessagePriority": "100",
            "SenderId": sender_id,
            "CallbackUrl": None,
            "ScheduledDeliveryDate": scheduled_delivery
        }

    json_payload = json.dumps(payload, separators=(",", ":"))
    sha256_hash = hashlib.sha256(json_payload.encode("utf-8")).digest()
    base64_request_content = base64.b64encode(sha256_hash).decode("utf-8")

    signature_raw = f"{key}\nPOST\n{encoded_request_uri}\n{timestamp}\n{nonce}\n{base64_request_content}"
    hmac_signature = base64.b64encode(
        hmac.new(secret.encode("utf-8"), signature_raw.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f'SMG-V1-HMAC-SHA256 id="{key}",ts="{timestamp}",nonce="{nonce}",mac="{hmac_signature}"'
    }

    try:
        response = requests.post(request_uri, data=json_payload, headers=headers)
        return {
            "status": "success",
            "status_code": response.status_code,
            "response": response.json()
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": str(e)
        }
