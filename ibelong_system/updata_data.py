import frappe
import json
from frappe.utils import cint
from datetime import datetime


@frappe.whitelist(allow_guest=True)
def test_api():
    frappe.log_error("started job")
    frappe.enqueue(
       "ibelong_system.updata_data.update_integration_com_from_json2502",
       queue='long',
       timeout=19000
    )

    return "The API is Running..."




import frappe
import json
import re

@frappe.whitelist()
def update_integration_com_from_json2502():
    file_path = "/home/frappe-user/ibelong-frappe/apps/ibelong_system/ibelong_system/comm26.json"

    # ---------------- CLEAN ----------------
    def clean_text(text):
        if not text:
            return ""

        text = str(text)

        # remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)

        # replace new lines with space
        text = text.replace("\n", " ")

        # normalize multiple spaces
        text = re.sub(r'\s{2,}', ' ', text)

        # remove trailing dots like ...
        text = re.sub(r'\.{2,}$', '', text.strip())

        return text.strip()

    # ---------------- LOAD JSON ----------------
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except Exception as e:
        return {"status": "error", "message": str(e)}

    # normalize structure
    if isinstance(data, dict):
        if "data" in data:
            data = data["data"]
        elif "response" in data:
            data = data["response"]
        elif not isinstance(data, list):
            data = [data]

    updated_count = 0

    # ---------------- MAIN LOOP ----------------
    for row in data:
        file_no = row.get("File_Number") or row.get("FileNo")
        raw_comment = row.get("Comments")

        if not file_no or not raw_comment:
            continue

        if not frappe.db.exists("Client Details", file_no):
            continue

        try:
            cleaned = clean_text(raw_comment)

            doc = frappe.get_doc("Client Details", file_no)

            # ✅ CLEAR OLD COMMENTS FIRST
            doc.comment_box = ""
            doc.more_comments = ""

            # ✅ PUT FULL COMMENT IN ONE BOX
            doc.comment_box = cleaned

            doc.flags.ignore_permissions = True
            doc.flags.ignore_mandatory = True
            doc.save()

            updated_count += 1

        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Comment Update Error: {file_no}"
            )

    frappe.db.commit()

    return {
        "status": "success",
        "updated_count": updated_count
    }



import frappe
import json
import traceback

@frappe.whitelist(allow_guest=False)
def update_languages_from_json25():

    DEBUG_TITLE = "ClientDetails_Update_Language_From_JSON"
    file_path = "/home/frappe-user/ibelong-frappe/apps/ibelong_system/ibelong_system/CDlang25a.json"

    try:
        # ---------------- LOAD JSON ----------------
        with open(file_path, "r") as f:
            data = json.load(f)

        if isinstance(data, dict):
            data = [data]

        updated_count = 0
        errors = []

        # ---------------- MAIN LOOP ----------------
        for row in data:
            file_no = row.get("FileNo")

            try:
                if not file_no:
                    continue

                # 🔍 find client by file_number field
                client_name = frappe.db.get_value(
                    "Client Details",
                    {"file_number": file_no},
                    "name"
                )

                if not client_name:
                    continue

                doc = frappe.get_doc("Client Details", client_name)

                # ===============================
                # ✅ CLEAR CHILD TABLE
                # ===============================
                doc.set("language_fluency", [])

                # ===============================
                # READ ARRAYS FROM JSON
                # ===============================
                languages = row.get("Language_Language_Fluency)", [])
                reading = row.get("Reading_Language_Fluency)", [])
                writing = row.get("Writing_Language_Fluency)", [])
                speaking = row.get("Speaking_Language_Fluency)", [])
                understanding = row.get("Understanding_Language_Fluency)", [])

                inserted_count = 0

                # ===============================
                # APPEND CHILD ROWS
                # ===============================
                for i, lang in enumerate(languages):
                    if not lang:
                        continue

                    doc.append("language_fluency", {
                        "language": lang,
                        "reading": reading[i] if i < len(reading) else None,
                        "writing": writing[i] if i < len(writing) else None,
                        "speaking": speaking[i] if i < len(speaking) else None,
                        "understanding": understanding[i] if i < len(understanding) else None,
                    })

                    inserted_count += 1

                # ===============================
                # SAVE
                # ===============================
                doc.flags.ignore_permissions = True
                doc.flags.ignore_mandatory = True
                doc.flags.ignore_links = True
                doc.flags.ignore_server_script = True
                doc.flags.mute_emails = True

                doc.save()

                updated_count += 1

                if updated_count % 100 == 0:
                    frappe.db.commit()

            except Exception:
                frappe.db.rollback()
                err_msg = f"File {file_no}: {traceback.format_exc()}"
                errors.append(err_msg)
                frappe.log_error(err_msg, f"{DEBUG_TITLE} - ROW ERROR")

        frappe.db.commit()

        return {
            "status": "success",
            "updated_count": updated_count,
            "error_count": len(errors),
            "errors": errors[:20]
        }

    except Exception:
        frappe.log_error(traceback.format_exc(), DEBUG_TITLE)
        return {"status": "error", "message": "Failed to process JSON"}


import frappe
import json
import re
import traceback

def parse_house(house_name, house_no):
    hn = (house_name or "").strip()
    hno = (house_no or "").strip()

    # If house_name is purely numeric → move
    if re.fullmatch(r"\d+", hn):
        return "", hn

    return hn, hno


def fix_house_from_json():
    file_path = "/home/frappe-user/ibelong-frappe/apps/ibelong_system/ibelong_system/update_HCB.json"
    updated = 0
    frappe.log_error("HCB job started")

    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except Exception:
        frappe.log_error(traceback.format_exc(), "HOUSE FIX JSON LOAD ERROR")
        return

    if isinstance(data, dict):
        if "data" in data:
            data = data["data"]
        elif "response" in data:
            data = data["response"]
        elif not isinstance(data, list):
            data = [data]

    frappe.log_error(f"Total rows: {len(data)}")

    for idx, row in enumerate(data, start=1):
        try:
            file_no = (row.get("File_Number") or "").strip()
            if not file_no:
                continue

            if not frappe.db.exists("Client Details", file_no):
                continue

            # 🔥 take values from JSON (NULL → "")
            house_no = (row.get("House_Number") or "").strip()
            house_name = (row.get("House_Name") or "").strip()
            country = (row.get("Country_of_Birth") or "").strip()

            # 🔥 apply your parse rule when needed
            has_digit_no = bool(re.search(r"\d", house_no))
            has_digit_name = bool(re.search(r"\d", house_name))

            if (not has_digit_no) and has_digit_name:
                new_name, new_no = parse_house(house_name, house_no)

                if new_no == house_no:
                    house_no, house_name = house_name, house_no
                else:
                    house_name, house_no = new_name, new_no

            # ✅ ALWAYS overwrite (your requirement)
            frappe.db.set_value(
                "Client Details",
                file_no,
                {
                    "house_name": house_name,
                    "house_number": house_no,
                    "country_of_birth": country,
                },
                update_modified=False
            )

            updated += 1

            # ✅ periodic commit
            if idx % 200 == 0:
                frappe.db.commit()
                frappe.log_error(f"Processed {idx} | Updated {updated}")

        except Exception:
            frappe.log_error(traceback.format_exc(), f"HOUSE FIX ERROR {file_no}")

    frappe.db.commit()
    frappe.clear_cache()  # ⭐ VERY IMPORTANT
    frappe.log_error(f"✅ FINAL Updated: {updated}")
# ▶ RUN

import frappe
import json
import traceback

@frappe.whitelist(allow_guest=False)
def replace_languages_with_fluency():
    try:
        data = frappe.request.get_json()

        if not data:
            return {"status": "error", "message": "No JSON payload received"}

        file_no = data.get("FileNo")
        if not file_no:
            return {"status": "error", "message": "FileNo is required"}

        # -------------------------------
        # DELETE OLD RECORDS
        # -------------------------------
        old_records = frappe.get_all(
            "Language Fluency",
            filters={"file_number": file_no},
            pluck="name"
        )

        for name in old_records:
            frappe.delete_doc("Language Fluency", name, force=1)

        # -------------------------------
        # PREPARE ARRAYS
        # -------------------------------
        ids = data.get("ID_Language_Fluency)", [])
        languages = data.get("Language_Language_Fluency)", [])
        reading = data.get("Reading_Language_Fluency)", [])
        writing = data.get("Writing_Language_Fluency)", [])
        speaking = data.get("Speaking_Language_Fluency)", [])
        understanding = data.get("Understanding_Language_Fluency)", [])

        max_len = len(languages)

        inserted = []

        # -------------------------------
        # INSERT NEW RECORDS
        # -------------------------------
        for i in range(max_len):
            lang = languages[i]

            # Skip empty language rows
            if not lang:
                continue

            doc = frappe.get_doc({
                "doctype": "Language Fluency",
                "file_number": file_no,
                "language": lang,
                "reading": reading[i] if i < len(reading) else None,
                "writing": writing[i] if i < len(writing) else None,
                "speaking": speaking[i] if i < len(speaking) else None,
                "understanding": understanding[i] if i < len(understanding) else None,
            })

            doc.insert(ignore_permissions=True)
            inserted.append(doc.name)

        frappe.db.commit()

        return {
            "status": "success",
            "message": f"{len(inserted)} language records replaced",
            "inserted": inserted
        }

    except Exception as e:
        frappe.log_error(
            title="replace_languages_with_fluency Error",
            message=traceback.format_exc()
        )
        return {"status": "error", "message": str(e)}

import frappe
import json
import traceback
from datetime import datetime

@frappe.whitelist(allow_guest=False)
def update_ism_and_location_only():
    DEBUG_TITLE = "ClientDetails_Update_ISM_Location"
    file_path = "/home/frappe-user/ibelong-frappe/apps/ibelong_system/ibelong_system/CD19a.json"

    frappe.log_error("Function started", DEBUG_TITLE)

    # ---------------- HELPERS ----------------

    def safe_date(val):
        """Convert datetime string to date"""
        if not val:
            return None
        try:
            return datetime.strptime(str(val), "%Y-%m-%d %H:%M:%S").date()
        except Exception:
            return None

    def clean(v):
        if v is None:
            return None
        return str(v).strip()

    # ---------------- LOAD JSON ----------------

    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except Exception:
        frappe.log_error(traceback.format_exc(), f"{DEBUG_TITLE} - JSON LOAD FAILED")
        return {"status": "error", "message": "Failed to load JSON"}

    if isinstance(data, dict):
        if "data" in data:
            data = data["data"]
        elif "response" in data:
            data = data["response"]
        elif not isinstance(data, list):
            data = [data]

    updated = 0
    errors = []

    # ---------------- MAIN LOOP ----------------

    for row in data:
        try:
            file_no = clean(row.get("File_Number"))
            if not file_no:
                continue

            if not frappe.db.exists("Client Details", file_no):
                frappe.log_error(f"SKIP: Client not found {file_no}", DEBUG_TITLE)
                continue

            doc = frappe.get_doc("Client Details", file_no)

            # ✅ UPDATE ONLY REQUIRED FIELDS
            ism_date = safe_date(row.get("ISR_Slot_Date"))
            location_val = clean(row.get("Location"))

            doc.ism_slot = ism_date
            doc.please_select_preferred_location = location_val

            doc.flags.ignore_permissions = True
            doc.flags.ignore_mandatory = True
            doc.flags.ignore_links = True
            doc.flags.ignore_server_script = True
            doc.flags.mute_emails = True

            doc.save()
            updated += 1

            if updated % 100 == 0:
                frappe.db.commit()

        except Exception:
            frappe.db.rollback()
            err = f"File {file_no}: {traceback.format_exc()}"
            errors.append(err)
            frappe.log_error(err, f"{DEBUG_TITLE} - ROW ERROR")

    frappe.db.commit()

    frappe.log_error(
        f"FINISHED | Updated: {updated} | Errors: {len(errors)}",
        DEBUG_TITLE
    )

    return {
        "status": "success",
        "updated_count": updated,
        "error_count": len(errors),
        "errors": errors[:20],
    }

import frappe
import json
import traceback

@frappe.whitelist(allow_guest=False)
def replace_languages_with_fluency():
    DEBUG_TITLE = "langlog"
    file_path = "/home/frappe-user/ibelong-frappe/apps/ibelong_system/ibelong_system/CDlang20.json"

    frappe.log_error("Function started", DEBUG_TITLE)

    # ---------------- HELPERS ----------------

    def clean(v):
        if v is None:
            return ""
        return str(v).strip()

    # ---------------- LOAD JSON ----------------

    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        frappe.log_error(f"JSON loaded. Rows: {len(data) if isinstance(data, list) else 'unknown'}", DEBUG_TITLE)
    except Exception:
        frappe.log_error(traceback.format_exc(), f"{DEBUG_TITLE} - JSON LOAD FAILED")
        return {"status": "error", "message": "Failed to load JSON"}

    if isinstance(data, dict):
        if "data" in data:
            data = data["data"]
        elif "response" in data:
            data = data["response"]
        elif not isinstance(data, list):
            data = [data]

    # ---------------- GROUP BY FILE ----------------

    grouped = {}

    for row in data:
        file_no = clean(row.get("FileNo"))
        if not file_no:
            continue
        grouped.setdefault(file_no, []).append(row)

    frappe.log_error(f"Grouped files count: {len(grouped)}", DEBUG_TITLE)

    updated_count = 0
    errors = []

    # ---------------- MAIN LOOP ----------------

    for file_no, rows in grouped.items():
        try:
            if not frappe.db.exists("Client Details", file_no):
                frappe.log_error(f"SKIP: Client not found {file_no}", DEBUG_TITLE)
                continue

            doc = frappe.get_doc("Client Details", file_no)

            # ✅ DELETE OLD LANGUAGES (FULL REPLACE)
            old_count = len(doc.get("language_fluency") or [])
            if old_count:
                doc.set("language_fluency", [])
                frappe.log_error(f"CLEARED old languages for {file_no} (removed {old_count})", DEBUG_TITLE)

            seen = set()
            inserted_rows = 0

            # ✅ INSERT NEW FROM JSON
            for row in rows:
                language = clean(row.get("Language_Language_Fluency)"))
                reading = clean(row.get("Reading_Language_Fluency)"))
                writing = clean(row.get("Writing_Language_Fluency)"))
                speaking = clean(row.get("Speaking_Language_Fluency)"))
                understanding = clean(row.get("Understanding_Language_Fluency)"))

                if not language:
                    continue

                unique_key = f"{language}|{reading}|{writing}|{speaking}|{understanding}"
                if unique_key in seen:
                    continue
                seen.add(unique_key)

                doc.append("language_fluency", {
                    "language": language,
                    "reading": reading,
                    "writing": writing,
                    "speaking": speaking,
                    "understanding": understanding
                })

                inserted_rows += 1

            # ✅ SAVE ONLY IF WE INSERTED SOMETHING
            if inserted_rows:
                doc.flags.ignore_permissions = True
                doc.flags.ignore_mandatory = True
                doc.flags.ignore_links = True
                doc.flags.ignore_server_script = True
                doc.flags.mute_emails = True

                doc.save()
                updated_count += 1

                frappe.log_error(
                    f"UPDATED: {file_no} | inserted: {inserted_rows}",
                    DEBUG_TITLE
                )
            else:
                frappe.log_error(f"SKIP: No valid language rows for {file_no}", DEBUG_TITLE)

            if updated_count % 100 == 0:
                frappe.db.commit()

        except Exception:
            frappe.db.rollback()
            err = f"File {file_no}: {traceback.format_exc()}"
            errors.append(err)
            frappe.log_error(err, f"{DEBUG_TITLE} - ROW ERROR")

    frappe.db.commit()

    frappe.log_error(
        f"FINISHED | Updated: {updated_count} | Errors: {len(errors)}",
        DEBUG_TITLE
    )

    return {
        "status": "success",
        "updated_count": updated_count,
        "error_count": len(errors),
        "errors": errors[:20]
    }




import frappe
import json
import traceback

@frappe.whitelist()
def update_client_progresssion_sp():
    frappe.log_error("Update Job", "Started job testy4")

    FILE_PATH = "/home/frappe-user/ibelong-frappe/apps/ibelong_system/ibelong_system/CPD19.json"

    try:
        with open(FILE_PATH, "r") as f:
            client_data = json.load(f)

        frappe.log_error("Update Job", f"File loaded. Records found: {len(client_data)}")

    except Exception as e:
        frappe.log_error("Update Job Error", f"Failed to load/parse file: {str(e)}")
        return {"error": f"Failed to load file: {str(e)}"}

    updated, skipped, errors = [], [], {}

    for i, row in enumerate(client_data):
        enrolment_no = None
        try:
            # ✅ Use File_Number directly (already IBP formatted)
            file_no = (row.get("File_Number") or "").strip()
            course_id = (row.get("CourseId") or "").strip()

            if not file_no:
                errors[f"Row_{i}"] = "Missing File Number"
                continue

            enrolment_no = f"{file_no}_{course_id}" if course_id else file_no

            # ✅ Check and Update
            if frappe.db.exists("Client Progression Details", enrolment_no):

                update_fields = {
                    "status": row.get("ClientStatus_New_database"),
                    "service_provider": row.get("Service_Provider"),
                }

                frappe.db.set_value(
                    "Client Progression Details",
                    enrolment_no,
                    update_fields,
                    update_modified=True
                )

                updated.append(enrolment_no)
            else:
                skipped.append(enrolment_no)

        except Exception as e:
            err_msg = f"Row {i} error: {str(e)}"
            frappe.log_error("Update Job Row Error", err_msg)
            errors[enrolment_no or f"Row_{i}"] = str(e)

    frappe.db.commit()

    summary = {
        "status": "Completed",
        "updated_count": len(updated),
        "not_found_count": len(skipped),
        "errors": errors
    }

    frappe.log_error("Update Job Summary", json.dumps(summary, indent=2))
    return summary



# def execute_pr_api():
#     frappe.log_error("API started To Update PR Data in IBelong System")

#     file_name = "iBelongdata022026.txt"
#     today = frappe.utils.nowdate()

#     files = frappe.get_all("File", filters={"file_name": file_name}, fields=["name"])
#     if not files:
#         frappe.log_error("File Not Found", file_name)
#         return

#     file_doc = frappe.get_doc("File", files[0].name)
#     content = file_doc.get_content()

#     if isinstance(content, bytes):
#         content = content.decode('utf-8', errors='ignore')

#     lines = content.splitlines()

#     processed_count = 0
#     update_count = 0
    
#     unique_localities = set()
#     unique_nationalities = set()
#     unique_countries = set()

#     # ✅ helper to convert API date → frappe date
#     def to_frappe_date(date_str):
#         if not date_str:
#             return None
#         try:
#             return datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
#         except Exception:
#             return date_str  # safe fallback

#     # --- PROGRESS LOGGING SETUP ---
#     total_lines = len(lines)

#     # Use enumerate to track the current line number (index)
#     for index, line in enumerate(lines, start=1):
        
#         # --- LOG PERCENTAGE EVERY 500 LINES ---
#         if index % 500 == 0 or index == total_lines:
#             percent_complete = round((index / total_lines) * 100, 2)
#             log_msg = f"Progress: {percent_complete}% | Checked {index} out of {total_lines} lines."
#             frappe.log_error("PR Sync Progress", log_msg)

#         parts = line.split("|")
#         if len(parts) <= 15:
#             continue

#         uri = parts[0].strip()
#         id_card_number = parts[15].strip()
#         frappe.log_error("URI", uri)
#         try: 
#             client_name = frappe.db.get_value(
#                 "Client Details",
#                 {
#                     "id_card_number": id_card_number,
#                     # Only fetch if the last modified date is strictly before today
#                     "modified": ["<", today] 
#                 },
#                 "name"
#             )
            
#             if not client_name:
#                 frappe.log_error("SKIPPED PR UPDATE", id_card_number)
#                 # This will now skip both missing IDs AND IDs already updated today
#                 continue
#         except Exception as e:
#             frappe.log_error("Client Detail Fetch", str(e))
#             continue # Added continue here so it doesn't try to fetch a missing doc below

#         try:
#             doc = frappe.get_doc("Client Details", client_name)

#             api_response = frappe.call(
#                 "ibelong_system.mail_api.pr_api.get_person_data",
#                 identification_document_number=id_card_number
#             ) or {}
#             frappe.log_error("ID Card: 1", id_card_number)
#             person_data_list = api_response.get("data") or []
#             frappe.log_error("person_data_list: 2", api_response)
            
#             if person_data_list:
#                 api_data = person_data_list[0]
#                 state = {"has_changes": False}
#                 frappe.log_error("API Resp: 3", api_data)

#                 # ✅ FIXED sync function
#                 def sync_field(target_field, value):
#                     if target_field in ["last_name_1"]:
#                         new_val = value
#                     else:
#                         new_val = str(value or "").strip().title()
                    
#                     old_val = str(doc.get(target_field) or "").strip()
                    
#                     if old_val != new_val:
#                         log_msg = f"Field: {target_field} | New: {new_val} | Old: {old_val}"
#                         frappe.log_error("Data Mismatch Detected : 6", log_msg)
#                         state["has_changes"] = True
#                         doc.set(target_field, new_val) # uncomment when ready
                
#                 # URL mapping
#                 sync_field("pr_url", uri)
                
#                 # mapping
#                 sync_field("first_name", api_data.get("name"))
#                 sync_field("last_name_1", api_data.get("surname"))
#                 sync_field("gender", (api_data.get("sex") or "").title())
#                 sync_field("nationality", api_data.get("nationalityCitizenship"))
#                 sync_field("country_of_birth", api_data.get("countryOfBirth"))

#                 addr = api_data.get("address") or {}
#                 parts_address = [
#                     str(addr.get("streetPrefix") or "").strip(),
#                     str(addr.get("streetName") or "").strip()
#                 ]
                
#                 # 2. Join only non-empty strings with a space
#                 full_street = " ".join([p for p in parts_address if p])
#                 sync_field("street_name", full_street)
#                 sync_field("house_number", addr.get("propertyNumber"))
#                 sync_field("house_name", addr.get("propertyName"))
#                 sync_field("locality", addr.get("streetCouncil"))
#                 sync_field("post_code", addr.get("postalCode"))
#                 sync_field("island", addr.get("island"))

#                 # ---------------- DOB ----------------
#                 api_dob = api_data.get("dateOfBirth")
#                 formatted_dob = to_frappe_date(api_dob)
#                 sync_field("date_of_birth", formatted_dob)
                
#                 # ---------------- ID CARD ----------------
#                 idCard = api_data.get("idCard") or {}

#                 issue_date = to_frappe_date(idCard.get("idCardValidFrom"))
#                 expiry_date = to_frappe_date(idCard.get("idCardValidTo"))

#                 sync_field("date_of_issue", issue_date)
#                 sync_field("date_of_expiry", expiry_date)
                
#                 if api_data.get("nationalityCitizenship"):
#                     unique_nationalities.add(str(api_data.get("nationalityCitizenship")).strip().title())
                
#                 if api_data.get("countryOfBirth"):
#                     unique_countries.add(str(api_data.get("countryOfBirth")).strip().title())
                
#                 if addr.get("streetCouncil"):
#                     unique_localities.add(str(addr.get("streetCouncil")).strip().title())
                
#                 frappe.log_error("state has change : 7", state["has_changes"])
                
#                 if state["has_changes"]:
#                     doc.save(ignore_permissions=True) # enable when ready
#                     update_count += 1

#             processed_count += 1

#             if processed_count % 2000 == 0:
#                 frappe.db.commit()
#                 # ✅ 3. Save the lists to your Single DocType
                
#             try:
#                 master_data = frappe.get_doc("PR Sync Master Data")
                
#                 # 'json' is globally available in the sandbox by default!
#                 master_data.locality_list = json.dumps(sorted(list(unique_localities)))
#                 master_data.nationality_list = json.dumps(sorted(list(unique_nationalities)))
#                 master_data.country_list = json.dumps(sorted(list(unique_countries)))
                
#                 master_data.save(ignore_permissions=True)
#                 frappe.db.commit()
                
#                 frappe.log_error("Master Data Lists Updated Successfully")
#             except Exception as e:
#                 frappe.log_error("Failed to save Master Data lists", str(e))

#         except Exception as e:
#             frappe.log_error(f"Sync Error for ID {id_card_number}", str(e))

#     frappe.db.commit()

#     frappe.log_error(
#         "PR Sync Complete",
#         f"Processed: {processed_count}, Updated: {update_count}"
#     )

import json

# def execute_pr_api():
#     frappe.log_error("API started To Update Nationality Data in IBelong System")

#     # ✅ 1. THE MALTESE TO ENGLISH MAPPING DICTIONARY
#     NATIONALITY_MAP = {
#         "AFGHANA": "Afghan", "AFRIKA T'ISFEL": "South African", "AFRIKANA": "African",
#         "ALBANIZA": "Albanian", "ALGERINA": "Algerian", "AMERIKANA": "American",
#         "ANDORRA": "Andorran", "ANGOLA": "Angolan", "ANGUILLA": "Anguillian",
#         "ANTIGUA": "Antiguan", "ARGENTINA": "Argentinian", "ARMENA": "Armenian",
#         "AWSTRALJANA": "Australian", "AWSTRIJAKA": "Austrian", "AZERBAJGAN": "Azerbaijani",
#         "BAHAMAS": "Bahamian", "BAHRAIN": "Bahraini", "BANGLADESH": "Bangladeshi",
#         "BARBADOS": "Barbadian", "BELGJANA": "Belgian", "BELIZE": "Belizean",
#         "BELORUSSA": "Belarusian", "BELT TAL-VATIKAN": "Vatican", "BENIN": "Beninese",
#         "BERMUDA": "Bermudian", "BHUTAN": "Bhutanese", "BOLIVJANA": "Bolivian",
#         "BOTSWANA": "Batswana", "BOZNIJA HERZEGOVINA": "Bosnian / Herzegovinian",
#         "BR. SOLOMON ISLANDS": "Solomon Islander", "BR. VIRGIN ISLANDS": "British Virgin Islander",
#         "BRAZILJANA": "Brazilian", "BRITISH NATIONAL (OVERSEAS)": "British National (Overseas)",
#         "BRITISH OVERSEAS CITIZEN": "British Overseas Citizen", 
#         "BRITISH OVERSEAS TERRITORIES CITIZEN": "British Overseas Territories Citizen",
#         "BRITISH PROTECTED PERSON": "British Protected Person", "BRITISH SUBJECT": "British Subject",
#         "BRITTANIKA": "British", "BRUNEI": "Bruneian", "BULGARA": "Bulgarian",
#         "BURKINA FASO": "Burkinabè", "BURMA": "Burmese", "BURUNDI": "Burundian",
#         "CAMBODIA": "Cambodian", "CAPE VERDE": "Cape Verdean", "CAYMAN ISLAND": "Caymanian",
#         "CENT. AFRICAN REPUBLIC": "Central African", "CHAD": "Chadian", 
#         "CHRISTMAS ISLAND": "Christmas Islander", "CILENA": "Chilean", "CINIZA": "Chinese",
#         "CIPRIJOTTA": "Cypriot", "COMORO ISLAND": "Comorian", "CONGO": "Congolese",
#         "CONGO, THE DEMOCRATIC REPUBLIC OF THE": "Congolese", "DANIZA": "Danish",
#         "DJIBOUTI": "Djiboutian", "DOMINICA": "Dominican", "EGIZZJANA": "Egyptian",
#         "EKWADORJANA": "Ecuadorian", "EL SALVADORENA": "Salvadoran", "EMIRATI GHARAB MAGHQUDA": "Emirati",
#         "EQUATORIAL GUINEA": "Equatorial Guinean", "ERITREA": "Eritrean", "ESTONJA": "Estonian",
#         "ETJOPJA": "Ethiopian", "FAROE ISLANDS": "Faroese", "FIJI": "Fijian",
#         "FILIPPINA": "Filipino / Filipina", "FINLANDIZA": "Finnish", "FRANCIZA": "French",
#         "FRENCH GUIANA": "French Guianese", "GABON": "Gabonese", "GAMAJKANA": "Jamaican",
#         "GAMBIA": "Gambian", "GAPPUNIZA": "Japanese", "GEORGJANA": "Georgian",
#         "GERMANIZA": "German", "GHANA": "Ghanaian", "GIBILTA'": "Gibraltarian",
#         "GORDANIZA": "Jordanian", "GREENLAND": "Greenlandic", "GRENADA": "Grenadian",
#         "GRIEGA": "Greek", "GUAM": "Guamanian", "GUATEMALA": "Guatemalan",
#         "GUINEA": "Guinean", "GUINEA-BISSAU": "Bissau-Guinean", "GUYANA": "Guyanese",
#         "GZEJJER FALKLAND": "Falkland Islander", "HAITI": "Haitian", "HONDURAS": "Honduran",
#         "HONG KONG": "Hong Konger", "INDJANA": "Indian", "INDONEZJANA": "Indonesian",
#         "IRANJANA": "Iranian", "IRAQQINA": "Iraqi", "IRLANDIZA": "Irish",
#         "ISLANDIZA": "Icelandic", "IVORY COAST": "Ivorian", "IZRAELITA": "Israeli",
#         "JUGOSLAVA": "Yugoslav", "KAMERUN": "Cameroonian", "KANADIZA": "Canadian",
#         "KAZAKHSTAN": "Kazakhstani", "KENJANA": "Kenyan", "KIRIBATI": "I-Kiribati",
#         "KOLOMBJANA": "Colombian", "KOREA TA' FUQ": "North Korean", "KOREANA": "South Korean",
#         "KOSOVO": "Kosovar", "KOSTARIKANA": "Costa Rican", "KROATA": "Croatian",
#         "KUBANA": "Cuban", "KUWAJT": "Kuwaiti", "KYRGYZ": "Kyrgyzstani",
#         "LAOS": "Lao", "LATVJA": "Latvian", "LEBANIZA": "Lebanese",
#         "LESOTHO": "Basotho", "LIBERJANA": "Liberian", "LIBJANA": "Libyan",
#         "LIECHTENSTEIN": "Liechtensteiner", "LITWANJA": "Lithuanian", "LUSSEMBURGU": "Luxembourgish",
#         "MACAU": "Macanese", "MACEDONA": "Macedonian", "MADAGASCAR": "Malagasy",
#         "MALAWI": "Malawian", "MALAZJANA": "Malaysian", "MALDIVES": "Maldivian",
#         "MALI": "Malian", "MALTA/NEW ZEALAND": "Maltese / New Zealander", "MALTIJA": "Maltese",
#         "MALTIJA/AMER./KANAD.": "Maltese / American / Canadian", "MALTIJA/AMERIKANA": "Maltese / American",
#         "MALTIJA/AWSTRALJANA": "Maltese / Australian", "MALTIJA/BRITTANIKA": "Maltese / British",
#         "MALTIJA/DANIZA": "Maltese / Danish", "MALTIJA/GERMANIZA": "Maltese / German",
#         "MALTIJA/GRIEGA": "Maltese / Greek", "MALTIJA/KANADIZA": "Maltese / Canadian",
#         "MALTIJA/NORVEGIZA": "Maltese / Norwegian", "MALTIJA/OHRAJN": "Maltese / Other",
#         "MALTIJA/OLANDIZA": "Maltese / Dutch", "MALTIJA/SVIZZERA": "Maltese / Swiss",
#         "MALTIJA/TALJANA": "Maltese / Italian", "MAROKKINA": "Moroccan", "MARSHALL ISLANDS": "Marshallese",
#         "MAURITANIA": "Mauritanian", "MAURITIUS": "Mauritian", "MESSIKANA": "Mexican",
#         "MHUX INDIKAT": "Not Indicated", "MICRONESIA": "Micronesian", "MOLDAVJA": "Moldovan",
#         "MONACO": "Monégasque", "MONGOLJA": "Mongolian", "MONSERRAT": "Montserratian",
#         "MONTENEGRO": "Montenegrin", "MOZAMBIQUE": "Mozambican", "MYANMAR": "Burmese",
#         "NAMIBJA": "Namibian", "NAURU": "Nauruan", "NEPAL": "Nepalese / Nepali",
#         "NEW ZEALAND": "New Zealander", "NIGER": "Nigerien", "NIGERJANA": "Nigerian",
#         "NIKARAGWENA": "Nicaraguan", "NIUE": "Niuean", "NORFOLK ISLAND": "Norfolk Islander",
#         "NORVEGIZA": "Norwegian", "NOT AVAILABLE": "Not Available", "OLANDIZA": "Dutch",
#         "OMAN": "Omani", "PAKISTANA": "Pakistani", "PALAU": "Palauan",
#         "PALESTINJANA": "Palestinian", "PANAMA": "Panamanian", "PAPUA NEW GUINEA": "Papua New Guinean",
#         "PARAGWAJANA": "Paraguayan", "PERUVJANA": "Peruvian", "POLLAKKA": "Polish",
#         "PORTUGIZA": "Portuguese", "QATAR": "Qatari", "REFUGEE": "Refugee",
#         "REP. DOMINIKANA": "Dominican", "REPUBBLIKA CEKA": "Czech", "RUMENA": "Romanian",
#         "RUSSA": "Russian", "RWANDA": "Rwandan", "SAMOA": "Samoan",
#         "SAN MARINO": "Sammarinese", "SAO TOME & PRINCIPE": "São Toméan", "SAWDI ARABJA": "Saudi / Saudi Arabian",
#         "SENEGAL": "Senegalese", "SERBA": "Serbian", "SEYCHELLES": "Seychellois",
#         "SIERRA LEONE": "Sierra Leonean", "SINGAPORE": "Singaporean", "SIRJANA": "Syrian",
#         "SLOVAKKJA": "Slovak", "SLOVENA": "Slovenian", "SOMALJA": "Somali",
#         "SOUTH SUDAN": "South Sudanese", "SPANJOLA": "Spanish", "SRI LANKA": "Sri Lankan",
#         "ST. HELEN": "Saint Helenian", "ST. KITTS-NEVIS": "Kittitian / Nevisian", "ST. LUCIA": "Saint Lucian",
#         "ST. VINCENT": "Vincentian", "STATELESS": "Stateless", "SUDAN": "Sudanese",
#         "SURINAM": "Surinamese", "SVEDIZA": "Swedish", "SVIZZERA": "Swiss",
#         "SWAZILAND": "Swazi", "TADZHIKISTAN": "Tajik / Tajikistani", "TAIWAN": "Taiwanese",
#         "TAJLANDJA": "Thai", "TALJANA": "Italian", "TANZANIJA": "Tanzanian",
#         "TIMOR-LESTE": "Timorese", "TOGO": "Togolese", "TONGA": "Tongan",
#         "TORKA": "Turkish", "TRINIDAD & TOBAGO": "Trinidadian / Tobagonian", "TUNEZINA": "Tunisian",
#         "TURKMENISTAN": "Turkmen", "TUVALU": "Tuvaluan", "UGANDA": "Ugandan",
#         "UKRANJA": "Ukrainian", "UNGERIZA": "Hungarian", "URUGWAJANA": "Uruguayan",
#         "UZBEKISTAN": "Uzbek / Uzbekistani", "VANUATU": "Ni-Vanuatu", "VENEZWELA": "Venezuelan",
#         "VIRGIN ISLAND": "Virgin Islander", "VJETNAMITA": "Vietnamese", "YEMEN": "Yemeni",
#         "ZAIRE": "Congolese", "ZAMBJA": "Zambian", "ZIMBABWE": "Zimbabwean"
#     }

#     file_name = "iBelongdata022026.txt"

#     files = frappe.get_all("File", filters={"file_name": file_name}, fields=["name"], limit=1)
#     if not files:
#         frappe.log_error("File Not Found", file_name)
#         return

#     file_doc = frappe.get_doc("File", files[0].name)
#     content = file_doc.get_content()
#     if isinstance(content, bytes):
#         content = content.decode('utf-8', errors='ignore')

#     lines = content.splitlines()

#     # 2. FETCH ALL CLIENTS (Removed pr_url filter so it checks EVERYONE)
#     eligible_clients = frappe.get_all(
#         "Client Details",
#         fields=["name", "id_card_number"]
#     )
#     client_map = {str(c.id_card_number).strip(): c.name for c in eligible_clients}

#     processed_count = 0
#     update_count = 0
#     unique_nationalities = set()
#     skipped_ids = []
#     no_change_ids = []

#     try:
#         master_data = frappe.get_doc("PR Sync Master Data")
#         if master_data.nationality_list:
#             unique_nationalities = set(json.loads(master_data.nationality_list))
#     except Exception as e:
#         frappe.log_error("Master Data Pre-load Warning", str(e))

#     total_lines = len(lines)

#     for index, line in enumerate(lines, start=1):
        
#         if index % 1000 == 0 or index == total_lines:
#             percent_complete = round((index / total_lines) * 100, 2)
#             frappe.log_error(
#                 "PR Sync Progress", 
#                 f"Progress: {percent_complete}% | Checked {index} out of {total_lines} lines."
#             )

#         parts = line.split("|")
#         if len(parts) <= 15:
#             continue

#         original_id_card = parts[15].strip()
#         system_id = original_id_card.lstrip('0')
        
#         client_name = client_map.get(original_id_card) or client_map.get(system_id)
        
#         if not client_name:
#             skipped_ids.append(original_id_card)
#             continue

#         try:
#             doc = frappe.get_doc("Client Details", client_name)

#             api_response = frappe.call(
#                 "ibelong_system.mail_api.pr_api.get_person_data",
#                 identification_document_number=original_id_card 
#             ) or {}
            
#             person_data_list = api_response.get("data") or []
            
#             if person_data_list:
#                 api_data = person_data_list[0]
                
#                 # ✅ MAPPING LOGIC
#                 raw_nationality = str(api_data.get("nationalityCitizenship") or "").strip().upper()
                
#                 # If found in map, use English. If not found, use Title Case of whatever the API sent
#                 english_nationality = NATIONALITY_MAP.get(raw_nationality, raw_nationality.title())
                
#                 old_val = str(doc.get("nationality") or "").strip()
                
#                 if english_nationality and old_val != english_nationality:
#                     doc.set("nationality", english_nationality)
#                     doc.save(ignore_permissions=True)
#                     update_count += 1
#                 else:
#                     no_change_ids.append(original_id_card)

#                 # Track for Master Data
#                 if english_nationality:
#                     unique_nationalities.add(english_nationality)

#             else:
#                 no_change_ids.append(original_id_card)

#             processed_count += 1

#             if processed_count % 500 == 0:
#                 frappe.db.commit()
            
#         except Exception as e:
#             frappe.log_error(f"Sync Error for ID {original_id_card}", str(e))
#             no_change_ids.append(original_id_card)

#     frappe.db.commit()

#     # 6. SAVE MASTER DATA (Only updating Nationality)
#     try:
#         master_data = frappe.get_doc("PR Sync Master Data")
#         master_data.nationality_list = json.dumps(sorted(list(unique_nationalities)))
#         master_data.save(ignore_permissions=True)
#         frappe.db.commit()
#     except Exception as e:
#         frappe.log_error("Failed to save Master Data list", str(e))

#     # 7. LOG SKIPPED IDS IN CHUNKS
#     if skipped_ids:
#         chunk_size = 500
#         for i in range(0, len(skipped_ids), chunk_size):
#             chunk = skipped_ids[i:i + chunk_size]
#             frappe.log_error(
#                 f"Skipped Nationality Updates (Part {int((i/chunk_size)+1)})", 
#                 ", ".join(chunk)
#             )

#     # 8. LOG NO-CHANGE IDS IN CHUNKS
#     if no_change_ids:
#         chunk_size = 500
#         for i in range(0, len(no_change_ids), chunk_size):
#             chunk = no_change_ids[i:i + chunk_size]
#             frappe.log_error(
#                 f"Processed But Not Updated (Part {int((i/chunk_size)+1)})", 
#                 ", ".join(chunk)
#             )

#     frappe.log_error(
#         "Nationality Sync Complete",
#         f"Processed: {processed_count} | Updated: {update_count} | No Change: {len(no_change_ids)} | Skipped: {len(skipped_ids)}"
#     )

import json

def execute_pr_error_fix():
    frappe.log_error("API started to Fix Pieta/Ghawdex Errors in IBelong System")

    # ✅ 1. THE EXACT LIST OF FAILED IDS
    ERROR_IDS = [
    "0036585A", "0037966A", "0040905A", "0041187A", "0044716A", "0047506A", "0048137A", "0052956A", "0056718A", "0061903A", 
    "0062909A", "0100671A", "0104388A", "0118189A", "0115601A", "0122240A", "0116295A", "0122804A", "0125533A", "0133543A", 
    "0136923A", "0137467A", "0139888A", "0142426A", "0142424A", "0140611A", "0139203A", "0149907A", "0148213A", "0152761A", 
    "0153031A", "0153047A", "0151687A", "0162238A", "0161188A", "0162046A", "0163279A", "0160578A", "0147255A", "0161847A", 
    "0164054A", "0162450A", "0169490A", "0171136A", "0170152A", "0173235A", "0147084A", "0173143A", "0174771A", "0163825A", 
    "0177043A", "0177330A", "0177283A", "0177818A", "0177823A", "0177828A", "0182274A", "0182436A", "0187865A", "0185545A", 
    "0187733A", "0188480A", "0181624A", "0187274A", "0189215A", "0189305A", "0189324A", "0188058A", "0185501A", "0193154A", 
    "0191862A", "0194078A", "0195716A", "0195078A", "0198498A", "0198257A", "0198256A", "0199843A", "0198669A", "0199224A", 
    "0195659A", "0199066A", "0199064A", "0193732A", "0198821A", "0204736A", "0202224A", "0202255A", "0205332A", "0202294A", 
    "0199316A", "0207309A", "0208867A", "0208987A", "0215158A", "0216021A", "0213745A", "0217506A", "0217408A", "0223931A", 
    "0208482A", "0208100A", "0226643A", "0225140A", "0223461A", "0220456A", "0223463A", "0231654A", "0227809A", "0218642A", 
    "0226443A", "0224162A", "0220157A", "0216302A", "0215775A", "0232955A", "0220375A", "0233810A", "0233410A", "0233094A", 
    "0234131A", "0235605A", "0239657A", "0250716A", "0256590A", "0242362A", "0242153A", "0258926A", "0258224A", "0258622A", 
    "0265347A", "0267576A", "0274988A", "0258687A", "0270517A", "0274075A", "0263568A", "0279585A", "0269263A", "0280928A", 
    "0283261A", "0036340A", "0036341A", "0036449A", "0036514A", "0036591A", "0036823A", "0036824A", "0036910A", "0037272A", 
    "0037360A", "0037372A", "0037591A", "0037616A", "0037688A", "0037832A", "0037895A", "0037904A", "0037924A", "0037969A", 
    "0037976A", "0037978A", "0038135A", "0038374A", "0038375A", "0038376A", "0038380A", "0038508A", "0038602A", "0038655A", 
    "0038666A", "0038672A", "0038674A", "0038732A", "0038897A", "0038902A", "0038905A", "0038908A", "0038911A", "0038980A", 
    "0038986A", "0038993A", "0039069A", "0039071A", "0039147A", "0039148A", "0039224A", "0039239A", "0039262A", "0039320A", 
    "0039442A", "0039505A", "0039508A", "0039509A", "0039513A", "0039514A", "0039516A", "0039536A", "0039548A", "0039622A", 
    "0039628A", "0039629A", "0039840A", "0039880A", "0039919A", "0039939A", "0039942A", "0040228A", "0040229A", "0040230A", 
    "0194074A", "0197920A", "0196892A", "0199635A", "0191385A", "0199832A", "0199260A", "0202960A", "0200754A", "0202762A", 
    "0200867A", "0205580A", "0201559A", "0186951A", "0206133A", "0208197A", "0211477A", "0209722A", "0211831A", "0205886A", 
    "0216977A", "0203163A", "0204431A", "0218299A", "0219959A", "0219134A", "0219299A", "0208126A", "0207946A", "0221608A", 
    "0224696A", "0227379A", "0217770A", "0217767A", "0232679A", "0231357A", "0235097A", "0226159A", "0201907A", "0212711A", 
    "0237165A", "0230873A", "0228877A", "0230032A", "0240001A", "0239265A", "0243983A", "0197853A", "0232950A", "0233446A", 
    "0240888A", "0255615A", "0256779A", "0264238A", "0265926A", "0259701A", "0294272A", "0293926A", "0294559A", "0297904A", 
    "0333079A", "0324323A", "0299505A", "0308032A", "0352822A", "0356211A", "0384596A", "0381629A", "0392375A", "0405980A", 
    "0042442A", "0042590A", "0042594A", "0043041A", "0043420A", "0043435A", "0043440A", "0043448A", "0043459A", "0043726A", 
    "0043756A", "0043864A", "0043872A", "0043882A", "0043888A", "0043898A", "0044112A", "0044371A", "0044377A", "0044415A", 
    "0044428A", "0044431A", "0044441A", "0044444A", "0044496A", "0044538A", "0044547A", "0044548A", "0044642A", "0044665A", 
    "0044681A", "0044687A", "0044692A", "0044793A", "0044916A", "0044971A", "0044980A", "0044982A", "0044989A", "0045018A", 
    "0045022A", "0045102A", "0045305A", "0045307A", "0045372A", "0045423A", "0045431A", "0045443A", "0045497A", "0045498A", 
    "0045500A", "0045624A", "0045635A", "0045669A", "0045675A", "0045708A", "0045709A", "0045716A", "0045718A", "0045722A", 
    "0045727A", "0045745A", "0045760A", "0045847A", "0045858A", "0045862A", "0045863A", "0045864A", "0045960A", "0046028A", 
    "0046082A", "0046169A", "0046174A", "0046278A", "0046280A", "0046290A", "0046293A", "0046317A", "0046373A", "0046375A", 
    "0046389A", "0046444A", "0046545A", "0046705A", "0046709A", "0046809A", "9000816A", "9001032A", "0014635A", "0027959A", 
    "0036304A", "0039441A", "0044081A", "0045174A", "0045957A", "0059511A", "0062922A", "0063275A", "0065436A", "0067255A", 
    "0069252A", "0074663A", "0078794A", "0081570A", "0112817A", "0115602A", "0117147A", "0118260A", "0119907A", "0116283A", 
    "0121347A", "0122513A", "0123332A", "0129204A", "0125963A", "0129447A", "0130440A", "0136164A", "0133113A", "0129694A", 
    "0126468A", "0142832A", "0143136A", "0136889A", "0144180A", "0141912A", "0155493A", "0153609A", "0154998A", "0155486A", 
    "0156300A", "0145643A", "0157044A", "0164393A", "0165090A", "0165125A", "0158930A", "0163974A", "0165657A", "0165686A", 
    "0163359A", "0171573A", "0171556A", "0171565A", "0172318A", "0172527A", "0140875A", "0173017A", "0173213A", "0169283A", 
    "0175468A", "0177922A", "0175185A", "0178841A", "0178839A", "0179125A", "0179389A", "0183407A", "0183357A", "0181645A", 
    "0183988A", "0184189A", "0180419A", "0184454A", "0184376A", "0179716A", "0184753A", "0179941A", "0181881A", "0180147A", 
    "0188271A", "0189980A", "0190017A", "0190019A", "0191117A", "0188946A", "0189869A", "0192073A", "0193032A", "0196584A", 
    "0190751A", "0196834A", "0196782A", "0200811A", "0200798A", "0199766A", "0201483A", "0199146A", "0202074A", "0187254A", 
    "0203916A", "0202458A", "0201654A", "0190238A", "0208397A", "0208099A", "0209381A", "0211290A", "0211600A", "0208568A", 
    "0207345A", "0209706A", "0209983A", "0213467A", "0210959A", "0220167A", "0211404A", "0218987A", "0218991A", "0219894A", 
    "0225091A", "0212720A", "0210182A", "0226568A", "0210394A", "0219826A", "0215236A", "0213413A", "0212475A", "0211722A", 
    "0215550A", "0225399A", "0218627A", "0225093A", "0207022A", "0218472A", "0230940A", "0216801A", "0215637A", "0218678A", 
    "0221491A", "0221494A", "0215626A", "0229263A", "0224125A", "0227621A", "0210540A", "0229982A", "0218384A", "0227950A", 
    "0229951A", "0232527A", "0235378A", "0238547A", "0238556A", "0239346A", "0237839A", "0239974A", "0239385A", "0241255A", 
    "0238427A", "0238488A", "0242614A", "0238429A", "0234275A", "0233134A", "0236447A", "0252339A", "0251562A", "0244790A", 
    "0255426A", "0261575A", "0257417A", "0282322A", "0272620A", "0262974A", "0288208A", "0290213A", "0101514A", "0103167A", 
    "0102831A", "0102834A", "0100433A", "0101931A", "0102477A", "0102123A", "0104156A", "0104354A", "0101127A", "0102986A", 
    "0105272A", "0105763A", "0105384A", "0107180A", "0105965A", "0107394A", "0108350A", "0105551A", "0105392A", "0105843A", 
    "0108562A", "0104876A", "0110310A", "0105541A", "0111344A", "0108160A", "0112464A", "0112411A", "0112642A", "0112357A", 
    "0105273A", "0110967A", "0114531A", "0114430A", "0114523A", "0113957A", "0110721A", "0114978A", "0108618A", "0111296A", 
    "0114707A", "0115345A", "0112506A", "0115856A", "0116239A", "0115604A", "0114289A", "0114290A", "0117541A", "0117685A", 
    "0118228A", "0118158A", "0115084A", "0118088A", "0103980A", "0119659A", "0120374A", "0119793A", "0119586A", "0119916A", 
    "0121703A", "0122648A", "0118196A", "0121891A", "0124137A", "0124258A", "0119862A", "0122199A", "0121496A", "0121987A", 
    "0126966A", "0123427A", "0287006A", "0299387A", "0311434A", "0308536A", "0306918A", "0305568A", "0303056A", "0303757A", 
    "0308453A", "0295493A", "0271770A", "0304075A", "0301097A", "0344773A", "0305103A", "0367070A", "0369951A", "0244369A", 
    "0350271A", "0372419A", "0344186A", "0363368A", "0410578A", "0310072A", "0046868A", "0046966A", "0047098A", "0047128A", 
    "0047319A", "0047469A", "0047485A", "0047487A", "0047488A", "0047490A", "0047507A", "0047514A", "0047628A", "0047639A", 
    "0047760A", "0047794A", "0047795A", "0047796A", "0047949A", "0047967A", "0048003A", "0048007A", "0048014A", "0048027A", 
    "0048313A", "0048318A", "0048661A", "0049035A", "0049114A", "0049263A", "0049295A", "0049520A", "0049995A", "0050568A", 
    "0051274A", "0051276A", "0051402A", "0052312A", "0052425A", "0052511A", "0052549A", "0052582A", "0052588A", "0052782A", 
    "0052790A", "0052808A", "0052874A", "0052950A", "0052951A", "0053038A", "0053057A", "0053084A", "0053197A", "0053226A", 
    "0053232A", "0053276A", "0053369A", "0053385A", "0053514A", "0053515A", "0053518A", "0053692A", "0053716A", "0053857A", 
    "0053860A", "0053880A", "0053890A", "0053984A", "0053989A", "0053995A", "0054011A", "0054391A", "0054396A", "0054398A", 
    "0054406A", "0054411A", "0054745A", "0055155A", "0055750A", "0055760A", "0055886A", "0055914A", "0055995A", "0056142A", 
    "0056268A", "0056273A", "0056282A", "0056302A", "0056410A", "9001306A", "9001380A", "9001341A", "9001558A", "9001830A", 
    "9001860A", "9001966A", "0022939A", "0031952A", "0032091A", "0038244A", "0038350A", "0045421A", "0046700A", "0046801A", 
    "0052586A", "0053265A", "0054405A", "0054640A", "0061151A", "0065317A", "0068231A", "0074581A", "0077397A", "0082265A", 
    "0083511A", "0106019A", "0111336A", "0113264A", "0109124A", "0105021A", "0115383A", "0117209A", "0123708A", "0110271A", 
    "0120360A", "0129349A", "0126040A", "0136005A", "0135387A", "0144044A", "0138181A", "0138711A", "0146600A", "0142351A", 
    "0159491A", "0164175A", "0165813A", "0165884A", "0163722A", "0179371A", "0178474A", "0176874A", "0177299A", "0173998A", 
    "0178160A", "0178099A", "0178016A", "0178101A", "0184799A", "0181418A", "0181426A", "0184888A", "0182866A", "0181580A", 
    "0183454A", "0180891A", "0184864A", "0186116A", "0186303A", "0187845A", "0190212A", "0192413A", "0190519A", "0196800A", 
    "0184517A", "0191149A", "0197260A", "0196811A", "0201940A", "0201941A", "0203507A", "0197538A", "0199038A", "0205263A", 
    "0201683A", "0205299A", "0205233A", "0210703A", "0210702A", "0209967A", "0209491A", "0209850A", "0213456A", "0208103A", 
    "0220009A", "0210806A", "0214881A", "0210844A", "0208314A", "0212197A", "0224615A", "0212693A", "0221882A", "0206860A", 
    "0206847A", "0230556A", "0219187A", "0225017A", "0220413A", "0231641A", "0223076A", "0217108A", "0215492A", "0227212A", 
    "0230251A", "0228802A", "0211430A", "0223330A", "0228513A", "0232221A", "0226384A", "0229921A", "0226274A", "0229780A", 
    "0238215A", "0241263A", "0234776A", "0237602A", "0242325A", "0244016A", "0236463A", "0236449A", "0240609A", "0250256A", 
    "0265421A", "0260063A", "0246000A", "0285113A", "0277509A", "0286651A", "0287053A", "0287479A", "0281244A", "0285049A", 
    "0265006A", "0263814A", "0290192A", "0252283A", "0127882A", "0123996A", "0128014A", "0123372A", "0125778A", "0124124A", 
    "0128986A", "0128983A", "0127207A", "0129604A", "0129360A", "0129636A", "0126442A", "0130333A", "0129415A", "0133652A", 
    "0132362A", "0132080A", "0129637A", "0134370A", "0135318A", "0124581A", "0131906A", "0130346A", "0132527A", "0136008A", 
    "0133233A", "0131065A", "0135764A", "0133772A", "0138010A", "0137061A", "0135138A", "0126440A", "0134578A", "0134848A", 
    "0137671A", "0136987A", "0141408A", "0137239A", "0137613A", "0139733A", "0139409A", "0136720A", "0140886A", "0141877A", 
    "0129698A", "0143245A", "0142801A", "0143634A", "0143230A", "0143876A", "0143275A", "0135940A", "0129410A", "0141837A", 
    "0146181A", "0145048A", "0143614A", "0144728A", "0140083A", "0127730A", "0146298A", "0145387A", "0144524A", "0145856A", 
    "0145631A", "0147856A", "0147956A", "0144052A", "0132199A", "0150206A", "0147733A", "0149077A", "0151679A", "0150132A", 
    "0153043A", "0152489A", "0154258A", "0154136A", "0154735A", "0154686A", "0142943A", "0154828A", "0154662A", "0155675A", 
    "0154497A", "0155822A", "0154361A", "0128844A", "0155416A", "0152986A", "0137918A", "0293726A", "0316934A", "0314559A", 
    "0340883A", "0347534A", "0331047A", "0324412A", "0311482A", "0360101A", "0366803A", "0372385A", "0346672A", "0426550A", 
    "0369122A", "0431298A", "0434274A", "0056621A", "0056677A", "0056911A", "0056922A", "0056924A", "0056996A", "0057095A", 
    "0057151A", "0057522A", "0057893A", "0057894A", "0057907A", "0057913A", "0058191A", "0058198A", "0058323A", "0059391A", 
    "0059394A", "0059509A", "0060189A", "0060816A", "0061168A", "0061174A", "0062716A", "0063241A", "0063484A", "0063635A", 
    "0063886A", "0063900A", "0063901A", "0064010A", "0064217A", "0064800A", "0064901A", "0065340A", "0065341A", "0065477A", 
    "0065561A", "0065566A", "0065569A", "0066002A", "0066246A", "0067532A", "0067550A", "0067758A", "0068547A", "0069143A", 
    "0069627A", "0069655A", "0070172A", "0070480A", "0070575A", "0070714A", "0070883A", "0070943A", "0071371A", "0071442A", 
    "0071633A", "0071715A", "0071809A", "0072616A", "0072628A", "0072731A", "0072990A", "0073363A", "0073818A", "0074515A", 
    "0074518A", "0074523A", "0074587A", "0074604A", "0074653A", "0074658A", "0074672A", "0074708A", "0074932A", "0075074A", 
    "0075113A", "0075200A", "0075223A", "0075264A", "0075288A", "0075296A", "0075514A", "0076086A", "0076382A", "0076580A", 
    "0076708A", "0076761A", "0076968A", "0077060A", "0077098A", "0077102A", "0077159A", "0077315A", "0077424A", "0077679A", 
    "0078637A", "9004823A", "0079178A", "0064058A", "0031697A", "0036825A", "0038903A", "0040894A", "0041339A", "0045940A", 
    "0046573A", "0046956A", "0047502A", "0074582A", "0076001A", "0103137A", "0105796A", "0108508A", "0112170A", "0117283A", 
    "0119919A", "0120209A", "0123206A", "0133580A", "0146963A", "0147967A", "0149676A", "0149399A", "0149108A", "0151142A", 
    "0158981A", "0168791A", "0167015A", "0174616A", "0175960A", "0175992A", "0173419A", "0174082A", "0136409A", "0179899A", 
    "0179996A", "0180098A", "0186601A", "0186514A", "0183544A", "0187000A", "0184947A", "0192300A", "0193204A", "0188751A", 
    "0190892A", "0193906A", "0196690A", "0196692A", "0186296A", "0199025A", "0203261A", "0198870A", "0200471A", "0201845A", 
    "0204737A", "0204958A", "0207109A", "0206519A", "0207555A", "0212911A", "0209709A", "0213410A", "0216621A", "0210252A", 
    "0215610A", "0224987A", "0229854A", "0216094A", "0226505A", "0219098A", "0219181A", "0226065A", "0226990A", "0229587A", 
    "0217566A", "0216761A", "0232642A", "0223704A", "0223926A", "0215910A", "0223524A", "0224433A", "0223903A", "0218562A", 
    "0223702A", "0220342A", "0224595A", "0229496A", "0232567A", "0219089A", "0224374A", "0233091A", "0235589A", "0237120A", 
    "0243726A", "0244912A", "0254859A", "0254921A", "0255455A", "0255831A", "0255540A", "0256230A", "0259308A", "0261647A", 
    "0269601A", "0263125A", "0271824A", "0272022A", "0284491A", "0286861A", "0286150A", "0280082A", "0285075A", "0261280A", 
    "0291289A", "0241445A", "0021766A", "0024815A", "0025241A", "0026037A", "0026536A", "0027130A", "0028424A", "0028809A", 
    "0028935A", "0028940A", "0029209A", "0029439A", "0030304A", "0030400A", "0031943A", "0033211A", "0034060A", "0034164A", 
    "0035003A", "0035157A", "0036067A", "0036073A", "0036197A", "0036306A", "0156989A", "0157558A", "0147627A", "0158137A", 
    "0158032A", "0159107A", "0159705A", "0157399A", "0160086A", "0158145A", "0158458A", "0161974A", "0161979A", "0162025A", 
    "0160821A", "0161312A", "0160648A", "0162307A", "0162263A", "0162172A", "0161007A", "0165572A", "0166704A", "0167245A", 
    "0163337A", "0165887A", "0166787A", "0168353A", "0167604A", "0167866A", "0169478A", "0168410A", "0169847A", "0168111A", 
    "0167329A", "0164165A", "0167323A", "0171594A", "0169897A", "0171781A", "0171847A", "0171107A", "0172293A", "0172918A", 
    "0173378A", "0174063A", "0172110A", "0175872A", "0172949A", "0175997A", "0173854A", "0173882A", "0174053A", "0172633A", 
    "0176460A", "0175123A", "0174422A", "0172329A", "0177651A", "0178029A", "0177478A", "0178920A", "0176349A", "0179576A", 
    "0181505A", "0177781A", "0179231A", "0149333A", "0182997A", "0182994A", "0183702A", "0175008A", "0185633A", "0183909A", 
    "0185681A", "0183807A", "0182986A", "0185581A", "0185580A", "0190102A", "0189308A", "0181825A", "0188849A", "0189186A", 
    "0190395A", "0190444A", "0190523A", "0191936A", "0195555A", "0196274A", "0191095A", "0197669A", "0190515A", "0198305A", 
    "0196579A", "0313608A", "0314391A", "0292678A", "0296292A", "0294673A", "0330590A", "0302880A", "0302884A", "0354480A", 
    "0350013A", "0294703A", "0376745A", "0386587A", "0356518A", "0354859A", "0367281A", "0447235A", "0040231A", "0040288A", 
    "0040318A", "0040432A", "0040435A", "0040515A", "0040664A", "0040786A", "0040795A", "0040892A", "0040895A", "0040909A", 
    "0040910A", "0040912A", "0040917A", "0041169A", "0041196A", "0041207A", "0041209A", "0041279A", "0041280A", "0041315A", 
    "0041325A", "0041326A", "0041357A", "0041363A", "0041379A", "0041568A", "0041570A", "0041572A", "0041783A", "0041784A", 
    "0041835A", "0042067A", "0042071A", "0042075A", "0042221A", "0042322A", "0078746A", "0078969A", "0079795A", "0080145A", 
    "0080685A", "0081373A", "0081379A", "0081539A", "0081567A", "0081759A", "0081789A", "0081795A", "0081798A", "0081801A", 
    "0081818A", "0082036A", "0082598A", "0082810A", "0082813A", "0082819A", "0082859A", "0082934A", "0083041A", "0083074A", 
    "0083081A", "0083755A", "0084106A", "0084141A", "0084230A", "9000055A", "9000421A", "9000524A"
]

    # ✅ 2. MALTESE TO ENGLISH DICTIONARY
    NATIONALITY_MAP = {
        "AFGHANA": "Afghan", "AFRIKA T'ISFEL": "South African", "AFRIKANA": "African",
        "ALBANIZA": "Albanian", "ALGERINA": "Algerian", "AMERIKANA": "American",
        "ANDORRA": "Andorran", "ANGOLA": "Angolan", "ANGUILLA": "Anguillian",
        "ANTIGUA": "Antiguan", "ARGENTINA": "Argentinian", "ARMENA": "Armenian",
        "AWSTRALJANA": "Australian", "AWSTRIJAKA": "Austrian", "AZERBAJGAN": "Azerbaijani",
        "BAHAMAS": "Bahamian", "BAHRAIN": "Bahraini", "BANGLADESH": "Bangladeshi",
        "BARBADOS": "Barbadian", "BELGJANA": "Belgian", "BELIZE": "Belizean",
        "BELORUSSA": "Belarusian", "BELT TAL-VATIKAN": "Vatican", "BENIN": "Beninese",
        "BERMUDA": "Bermudian", "BHUTAN": "Bhutanese", "BOLIVJANA": "Bolivian",
        "BOTSWANA": "Batswana", "BOZNIJA HERZEGOVINA": "Bosnian / Herzegovinian",
        "BR. SOLOMON ISLANDS": "Solomon Islander", "BR. VIRGIN ISLANDS": "British Virgin Islander",
        "BRAZILJANA": "Brazilian", "BRITISH NATIONAL (OVERSEAS)": "British National (Overseas)",
        "BRITISH OVERSEAS CITIZEN": "British Overseas Citizen", 
        "BRITISH OVERSEAS TERRITORIES CITIZEN": "British Overseas Territories Citizen",
        "BRITISH PROTECTED PERSON": "British Protected Person", "BRITISH SUBJECT": "British Subject",
        "BRITTANIKA": "British", "BRUNEI": "Bruneian", "BULGARA": "Bulgarian",
        "BURKINA FASO": "Burkinabè", "BURMA": "Burmese", "BURUNDI": "Burundian",
        "CAMBODIA": "Cambodian", "CAPE VERDE": "Cape Verdean", "CAYMAN ISLAND": "Caymanian",
        "CENT. AFRICAN REPUBLIC": "Central African", "CHAD": "Chadian", 
        "CHRISTMAS ISLAND": "Christmas Islander", "CILENA": "Chilean", "CINIZA": "Chinese",
        "CIPRIJOTTA": "Cypriot", "COMORO ISLAND": "Comorian", "CONGO": "Congolese",
        "CONGO, THE DEMOCRATIC REPUBLIC OF THE": "Congolese", "DANIZA": "Danish",
        "DJIBOUTI": "Djiboutian", "DOMINICA": "Dominican", "EGIZZJANA": "Egyptian",
        "EKWADORJANA": "Ecuadorian", "EL SALVADORENA": "Salvadoran", "EMIRATI GHARAB MAGHQUDA": "Emirati",
        "EQUATORIAL GUINEA": "Equatorial Guinean", "ERITREA": "Eritrean", "ESTONJA": "Estonian",
        "ETJOPJA": "Ethiopian", "FAROE ISLANDS": "Faroese", "FIJI": "Fijian",
        "FILIPPINA": "Filipino / Filipina", "FINLANDIZA": "Finnish", "FRANCIZA": "French",
        "FRENCH GUIANA": "French Guianese", "GABON": "Gabonese", "GAMAJKANA": "Jamaican",
        "GAMBIA": "Gambian", "GAPPUNIZA": "Japanese", "GEORGJANA": "Georgian",
        "GERMANIZA": "German", "GHANA": "Ghanaian", "GIBILTA'": "Gibraltarian",
        "GORDANIZA": "Jordanian", "GREENLAND": "Greenlandic", "GRENADA": "Grenadian",
        "GRIEGA": "Greek", "GUAM": "Guamanian", "GUATEMALA": "Guatemalan",
        "GUINEA": "Guinean", "GUINEA-BISSAU": "Bissau-Guinean", "GUYANA": "Guyanese",
        "GZEJJER FALKLAND": "Falkland Islander", "HAITI": "Haitian", "HONDURAS": "Honduran",
        "HONG KONG": "Hong Konger", "INDJANA": "Indian", "INDONEZJANA": "Indonesian",
        "IRANJANA": "Iranian", "IRAQQINA": "Iraqi", "IRLANDIZA": "Irish",
        "ISLANDIZA": "Icelandic", "IVORY COAST": "Ivorian", "IZRAELITA": "Israeli",
        "JUGOSLAVA": "Yugoslav", "KAMERUN": "Cameroonian", "KANADIZA": "Canadian",
        "KAZAKHSTAN": "Kazakhstani", "KENJANA": "Kenyan", "KIRIBATI": "I-Kiribati",
        "KOLOMBJANA": "Colombian", "KOREA TA' FUQ": "North Korean", "KOREANA": "South Korean",
        "KOSOVO": "Kosovar", "KOSTARIKANA": "Costa Rican", "KROATA": "Croatian",
        "KUBANA": "Cuban", "KUWAJT": "Kuwaiti", "KYRGYZ": "Kyrgyzstani",
        "LAOS": "Lao", "LATVJA": "Latvian", "LEBANIZA": "Lebanese",
        "LESOTHO": "Basotho", "LIBERJANA": "Liberian", "LIBJANA": "Libyan",
        "LIECHTENSTEIN": "Liechtensteiner", "LITWANJA": "Lithuanian", "LUSSEMBURGU": "Luxembourgish",
        "MACAU": "Macanese", "MACEDONA": "Macedonian", "MADAGASCAR": "Malagasy",
        "MALAWI": "Malawian", "MALAZJANA": "Malaysian", "MALDIVES": "Maldivian",
        "MALI": "Malian", "MALTA/NEW ZEALAND": "Maltese / New Zealander", "MALTIJA": "Maltese",
        "MALTIJA/AMER./KANAD.": "Maltese / American / Canadian", "MALTIJA/AMERIKANA": "Maltese / American",
        "MALTIJA/AWSTRALJANA": "Maltese / Australian", "MALTIJA/BRITTANIKA": "Maltese / British",
        "MALTIJA/DANIZA": "Maltese / Danish", "MALTIJA/GERMANIZA": "Maltese / German",
        "MALTIJA/GRIEGA": "Maltese / Greek", "MALTIJA/KANADIZA": "Maltese / Canadian",
        "MALTIJA/NORVEGIZA": "Maltese / Norwegian", "MALTIJA/OHRAJN": "Maltese / Other",
        "MALTIJA/OLANDIZA": "Maltese / Dutch", "MALTIJA/SVIZZERA": "Maltese / Swiss",
        "MALTIJA/TALJANA": "Maltese / Italian", "MAROKKINA": "Moroccan", "MARSHALL ISLANDS": "Marshallese",
        "MAURITANIA": "Mauritanian", "MAURITIUS": "Mauritian", "MESSIKANA": "Mexican",
        "MHUX INDIKAT": "Not Indicated", "MICRONESIA": "Micronesian", "MOLDAVJA": "Moldovan",
        "MONACO": "Monégasque", "MONGOLJA": "Mongolian", "MONSERRAT": "Montserratian",
        "MONTENEGRO": "Montenegrin", "MOZAMBIQUE": "Mozambican", "MYANMAR": "Burmese",
        "NAMIBJA": "Namibian", "NAURU": "Nauruan", "NEPAL": "Nepalese / Nepali",
        "NEW ZEALAND": "New Zealander", "NIGER": "Nigerien", "NIGERJANA": "Nigerian",
        "NIKARAGWENA": "Nicaraguan", "NIUE": "Niuean", "NORFOLK ISLAND": "Norfolk Islander",
        "NORVEGIZA": "Norwegian", "NOT AVAILABLE": "Not Available", "OLANDIZA": "Dutch",
        "OMAN": "Omani", "PAKISTANA": "Pakistani", "PALAU": "Palauan",
        "PALESTINJANA": "Palestinian", "PANAMA": "Panamanian", "PAPUA NEW GUINEA": "Papua New Guinean",
        "PARAGWAJANA": "Paraguayan", "PERUVJANA": "Peruvian", "POLLAKKA": "Polish",
        "PORTUGIZA": "Portuguese", "QATAR": "Qatari", "REFUGEE": "Refugee",
        "REP. DOMINIKANA": "Dominican", "REPUBBLIKA CEKA": "Czech", "RUMENA": "Romanian",
        "RUSSA": "Russian", "RWANDA": "Rwandan", "SAMOA": "Samoan",
        "SAN MARINO": "Sammarinese", "SAO TOME & PRINCIPE": "São Toméan", "SAWDI ARABJA": "Saudi / Saudi Arabian",
        "SENEGAL": "Senegalese", "SERBA": "Serbian", "SEYCHELLES": "Seychellois",
        "SIERRA LEONE": "Sierra Leonean", "SINGAPORE": "Singaporean", "SIRJANA": "Syrian",
        "SLOVAKKJA": "Slovak", "SLOVENA": "Slovenian", "SOMALJA": "Somali",
        "SOUTH SUDAN": "South Sudanese", "SPANJOLA": "Spanish", "SRI LANKA": "Sri Lankan",
        "ST. HELEN": "Saint Helenian", "ST. KITTS-NEVIS": "Kittitian / Nevisian", "ST. LUCIA": "Saint Lucian",
        "ST. VINCENT": "Vincentian", "STATELESS": "Stateless", "SUDAN": "Sudanese",
        "SURINAM": "Surinamese", "SVEDIZA": "Swedish", "SVIZZERA": "Swiss",
        "SWAZILAND": "Swazi", "TADZHIKISTAN": "Tajik / Tajikistani", "TAIWAN": "Taiwanese",
        "TAJLANDJA": "Thai", "TALJANA": "Italian", "TANZANIJA": "Tanzanian",
        "TIMOR-LESTE": "Timorese", "TOGO": "Togolese", "TONGA": "Tongan",
        "TORKA": "Turkish", "TRINIDAD & TOBAGO": "Trinidadian / Tobagonian", "TUNEZINA": "Tunisian",
        "TURKMENISTAN": "Turkmen", "TUVALU": "Tuvaluan", "UGANDA": "Ugandan",
        "UKRANJA": "Ukrainian", "UNGERIZA": "Hungarian", "URUGWAJANA": "Uruguayan",
        "UZBEKISTAN": "Uzbek / Uzbekistani", "VANUATU": "Ni-Vanuatu", "VENEZWELA": "Venezuelan",
        "VIRGIN ISLAND": "Virgin Islander", "VJETNAMITA": "Vietnamese", "YEMEN": "Yemeni",
        "ZAIRE": "Congolese", "ZAMBJA": "Zambian", "ZIMBABWE": "Zimbabwean"
    }

    # Generate a list that includes the IDs with and without leading zeros for safe DB lookup
    search_ids = ERROR_IDS + [i.lstrip('0') for i in ERROR_IDS]

    # Pre-fetch only these specific clients to save massive memory overhead
    eligible_clients = frappe.get_all(
        "Client Details",
        filters={"id_card_number": ["in", search_ids]},
        fields=["name", "id_card_number"]
    )
    client_map = {str(c.id_card_number).strip(): c.name for c in eligible_clients}

    processed_count = 0
    update_count = 0
    skipped_ids = []

    # 3. LOOP ONLY THROUGH THE FAILED IDS
    for original_id_card in ERROR_IDS:
        original_id_card = original_id_card.strip()
        system_id = original_id_card.lstrip('0')
        
        client_name = client_map.get(original_id_card) or client_map.get(system_id)
        
        if not client_name:
            skipped_ids.append(original_id_card)
            continue

        try:
            doc = frappe.get_doc("Client Details", client_name)

            api_response = frappe.call(
                "ibelong_system.mail_api.pr_api.get_person_data",
                identification_document_number=original_id_card 
            ) or {}
            
            person_data_list = api_response.get("data") or []
            
            if person_data_list:
                api_data = person_data_list[0]
                has_changes = False
                
                # --- A. NATIONALITY ---
                raw_nationality = str(api_data.get("nationalityCitizenship") or "").strip().upper()
                english_nationality = NATIONALITY_MAP.get(raw_nationality, raw_nationality.title())
                
                old_nat = str(doc.get("nationality") or "").strip()
                if english_nationality and old_nat != english_nationality:
                    doc.set("nationality", english_nationality)
                    has_changes = True

                # --- B. LOCALITY AND ISLAND (Targeted Check & Fix) ---
                old_locality = str(doc.get("locality") or "").strip()
                old_island = str(doc.get("island") or "").strip()
                
                # 1. Check if the document CURRENTLY has the bad values and fix them
                if old_locality == "Pieta`":
                    doc.set("locality", "Pieta")
                    has_changes = True
                    
                if old_island == "Ghawdex":
                    doc.set("island", "Gozo")
                    has_changes = True

                
                # --- SAVE IF ANY OF THE 3 FIELDS CHANGED ---
                if has_changes:
                    doc.save(ignore_permissions=True)
                    update_count += 1    
            processed_count += 1
            
        except Exception as e:
            frappe.log_error(f"Error fixing ID {original_id_card}", str(e))

    frappe.db.commit()

    frappe.log_error(
        "Targeted Error Fix Complete", 
        f"Processed: {processed_count} | Updated: {update_count} | Skipped: {len(skipped_ids)}"
    )

import frappe
import json
import re

@frappe.whitelist()
def update_integration_com_from_json():
    file_path = "/home/frappe-user/ibelong-frappe/apps/ibelong_system/ibelong_system/CDcom.json"

    # ---------------- CLEAN ----------------
    def clean_text(text):
        if not text:
            return ""

        text = str(text)

        # remove HTML tags if present
        text = re.sub(r'<[^>]+>', '', text)

        # replace new lines with space
        text = text.replace("\n", " ")

        # normalize multiple spaces
        text = re.sub(r'\s{2,}', ' ', text)

        # remove trailing ... or ..
        text = re.sub(r'\.{2,}$', '', text.strip())

        return text.strip()

    # ---------------- LOAD JSON ----------------
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except Exception as e:
        return {"status": "error", "message": str(e)}

    if isinstance(data, dict):
        if "data" in data:
            data = data["data"]
        elif "response" in data:
            data = data["response"]
        elif not isinstance(data, list):
            data = [data]

    updated_count = 0

    # ---------------- MAIN LOOP ----------------
    for row in data:
        file_no = row.get("File_Number") or row.get("file_no")
        raw_comment = row.get("Comments")

        if not file_no or not raw_comment:
            continue

        if not frappe.db.exists("Client Details", file_no):
            continue

        try:
            cleaned = clean_text(raw_comment)

            doc = frappe.get_doc("Client Details", file_no)

            # ✅ FULL COMMENT — no limit now
            doc.comment_box = cleaned

            # optional: clear more_comments if you want
            # doc.more_comments = ""

            doc.flags.ignore_permissions = True
            doc.flags.ignore_mandatory = True
            doc.save()

            updated_count += 1

        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Comment Update Error: {file_no}"
            )

    frappe.db.commit()

    return {
        "status": "success",
        "updated_count": updated_count
    }


import frappe
import json
import traceback

@frappe.whitelist(allow_guest=False)
def update_integration_officer_from_json():
    DEBUG_TITLE = "CD comm and status"
    # Update this path to your current JSON file location
    file_path = "/home/frappe-user/ibelong-frappe/apps/ibelong_system/ibelong_system/Location_To_repeat_16_02_2026.json"

    # ---------------- LOAD JSON ----------------
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except Exception:
        return {"status": "error", "message": f"Failed to load JSON from {file_path}"}

    # Handle different JSON wrapper formats
    if isinstance(data, dict):
        if "data" in data: data = data["data"]
        elif "response" in data: data = data["response"]
        elif not isinstance(data, list): data = [data]

    updated_count = 0
    errors = []
    processed_files = set()

    # ---------------- MAIN LOOP ----------------
    for row in data:
        file_no = row.get("FileNo") or row.get("file_no")
        comment_box = row.get("Integration_officer")
        more_comments = row.get("New_Location")

        if not file_no or not comment_box:
            continue

        try:
            # Prevent double processing in the same loop
            if file_no in processed_files: 
                continue
            
            if not frappe.db.exists("Client Details", file_no):
                continue

            processed_files.add(file_no)
            
            # Use db_set for a faster update if no other logic needs to fire
            # Or use get_doc if you need to bypass specific server scripts
            doc = frappe.get_doc("Client Details", file_no)
            
            # Set the field (ensure 'integration_officer' is the correct fieldname in your DocType)

            # ---------------- SAVE ----------------
            doc.flags.ignore_permissions = True
            doc.flags.ignore_mandatory = True
            doc.flags.ignore_links = True
            doc.flags.ignore_server_script = True 
            doc.flags.mute_emails = True
            
            doc.save()

            updated_count += 1
            
            # Commit every 100 rows to keep memory/logs clean
            if updated_count % 100 == 0:
                frappe.db.commit()

        except Exception:
            frappe.db.rollback()
            err_msg = f"File {file_no}: {traceback.format_exc()}"
            errors.append(err_msg)
            frappe.log_error(err_msg, f"{DEBUG_TITLE} - ROW ERROR")

    frappe.db.commit()

    return {
        "status": "success",
        "updated_count": updated_count,
        "error_count": len(errors),
        "errors": errors[:20]
    }

import frappe
import json
import traceback

@frappe.whitelist(allow_guest=False)
def update_house_and_cleanup_languages():
    DEBUG_TITLE = "ClientDetails_Fix_House_Lang_Cleanup"
    file_path = "/home/frappe-user/ibelong-frappe/apps/ibelong_system/ibelong_system/Location_To_repeat_16_02_2026.json"

    # ---------------- HELPERS ----------------

    def normalize_file_number(raw_val):
        if not raw_val: return ""
        val_str = str(raw_val)
        if "," in val_str:
            parts = [p.strip() for p in val_str.split(',') if p.strip()]
            val_str = parts[-1] if parts else ""
        
        val_str = val_str.strip()
        val_str = val_str.replace("/", "-").replace("\\/", "-")
        
        if "LEI" in val_str:
            val_str = val_str.replace("LEI", "IBP")
            
        return val_str[:140]

    def clean_house_number(value):
        """
        Smart deduplication for repeating addresses.
        Examples:
        "74, GF, 74, GF" -> "74, GF"
        "13, 13, 13" -> "13"
        "Leone, Flat 3, 192, Leone, Flat 3, 192" -> "Leone, Flat 3, 192"
        """
        if not value: return ""
        s = str(value).strip()
        
        # 1. Simple Split Check (e.g. "13, 13, 13")
        parts = [p.strip() for p in s.split(',')]
        if len(parts) > 1 and all(p == parts[0] for p in parts):
            return parts[0]

        # 2. Pattern Check (e.g. "74, GF, 74, GF")
        # Check if the string is exactly two identical halves separated by comma
        mid = len(parts) // 2
        if len(parts) > 1 and len(parts) % 2 == 0:
            first_half = parts[:mid]
            second_half = parts[mid:]
            # Join them back to string to compare content equality
            if ", ".join(first_half) == ", ".join(second_half):
                return ", ".join(first_half)

        # 3. Fallback: Standard cleanup (Remove distinct duplicates but keep order)
        seen = set()
        cleaned = []
        for p in parts:
            if p and p not in seen:
                seen.add(p)
                cleaned.append(p)
        
        return ", ".join(cleaned)

    def get_json_value(row, *keys):
        for k in keys:
            val = row.get(k)
            if val: return val
        return None

    # ---------------- LOAD JSON ----------------

    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except Exception:
        return {"status": "error", "message": "Failed to load JSON"}

    if isinstance(data, dict):
        if "data" in data: data = data["data"]
        elif "response" in data: data = data["response"]
        elif not isinstance(data, list): data = [data]

    updated_count = 0
    errors = []
    processed_files = set()

    # ---------------- MAIN LOOP ----------------

    for row in data:
        file_no = None
        try:
            # 1. Get File Number
            raw_fn = get_json_value(row, "File_Number", "FileNumber", "file_number")
            file_no = normalize_file_number(raw_fn)

            if not file_no:
                continue

            # 2. Update Only Check
            if file_no in processed_files: continue
            
            if not frappe.db.exists("Client Details", file_no):
                continue

            processed_files.add(file_no)
            
            # Load Existing Doc
            doc = frappe.get_doc("Client Details", file_no)

            # ---------------- UPDATE 1: HOUSE NUMBER ----------------
            # Using JSON data to fix the address
            # raw_house = row.get("House_Number")
            # if raw_house:
                # doc.house_number = clean_house_number(raw_house)

            # ---------------- UPDATE 2: CLEANUP DUPLICATE LANGUAGES ----------------
            # Logic: Look at CURRENT rows in DB. Keep only 1 unique combination.
            
            existing_languages = doc.get("language_fluency")
            unique_rows = []
            seen_combinations = set()

            if existing_languages:
                for lang_row in existing_languages:
                    # Create a unique key based on Language + Proficiency
                    # We strip just in case there are hidden spaces causing "duplicates"
                    lang_name = str(lang_row.language).strip() if lang_row.language else ""
                    read = str(lang_row.reading).strip() if lang_row.reading else ""
                    write = str(lang_row.writing).strip() if lang_row.writing else ""
                    speak = str(lang_row.speaking).strip() if lang_row.speaking else ""
                    under = str(lang_row.understanding).strip() if lang_row.understanding else ""

                    # The unique signature of this row
                    unique_key = f"{lang_name}|{read}|{write}|{speak}|{under}"

                    if unique_key not in seen_combinations:
                        # This is a new unique row, keep it
                        unique_rows.append(lang_row)
                        seen_combinations.add(unique_key)
                    else:
                        # This is a duplicate! We skip appending it to unique_rows.
                        # This effectively deletes it when we save.
                        pass
                
                # Replace the child table with the filtered unique list
                doc.set("language_fluency", unique_rows)

            # ---------------- SAVE ----------------
            
            doc.flags.ignore_permissions = True
            doc.flags.ignore_mandatory = True
            doc.flags.ignore_links = True
            doc.flags.ignore_server_script = True  # Stop the email error
            doc.flags.mute_emails = True
            
            doc.save()

            updated_count += 1
            if updated_count % 100 == 0:
                frappe.db.commit()

        except Exception:
            frappe.db.rollback()
            err_msg = f"File {file_no}: {traceback.format_exc()}"
            errors.append(err_msg)
            frappe.log_error(err_msg, f"{DEBUG_TITLE} - ROW ERROR")

    frappe.db.commit()

    return {
        "status": "success",
        "updated_count": updated_count,
        "error_count": len(errors),
        "errors": errors[:20]
    }

import frappe
import json
import traceback

@frappe.whitelist()  # <--- MUST HAVE THIS FOR THE API TO BE CALLABLE
def update_client_results_and_certificates():
    frappe.log_error("Update Job", "Started job testy4")

    # Path to your JSON file
    FILE_PATH = "/home/frappe-user/ibelong-frappe/apps/ibelong_system/ibelong_system/CPD3.json"
    
    def normalize_file_number(val):
        if not val: return ""
        val = str(val).strip()
        val = val.replace("LEI", "IBP").replace("/", "-")
        return val

    try:
        with open(FILE_PATH, "r") as f:
            client_data = json.load(f)
        
        # Log count to see if file actually loaded
        frappe.log_error("Update Job", f"File loaded. Records found: {len(client_data)}")
        
    except Exception as e:
        frappe.log_error("Update Job Error", f"Failed to load/parse file: {str(e)}")
        return {"error": f"Failed to load file: {str(e)}"}

    updated, skipped, errors = [], [], {}

    for i, row in enumerate(client_data):
        enrolment_no = None
        try:
            # 1. Reconstruct the enrolment_number
            # Check if key "File_Number CPD3" actually exists in your JSON
            raw_file_no = row.get("File_Number CPD3") 
            course_id = row.get("CourseId")
            
            if not raw_file_no:
                # Fallback if the key name changed in the JSON
                raw_file_no = row.get("File_Number") 

            file_no = normalize_file_number(raw_file_no)
            
            if not file_no:
                # Log if a specific row is missing the key
                errors[f"Row_{i}"] = "Missing File Number key"
                continue
                
            enrolment_no = f"{file_no}_{course_id}" if course_id else file_no

            # 2. Check and Update
            if frappe.db.exists("Client Progression Details", enrolment_no):
                res_val = str(row.get("Result") or "").strip()
                cert_val = str(row.get("Certificate_Number") or "").strip()

                frappe.db.set_value("Client Progression Details", enrolment_no, {
                    "result": res_val,
                    "certificate_number": cert_val
                }, update_modified=True) # Ensure modified date changes
                
                updated.append(enrolment_no)
            else:
                skipped.append(enrolment_no)

        except Exception as e:
            err_msg = f"Row {i} error: {str(e)}"
            frappe.log_error("Update Job Row Error", err_msg)
            errors[enrolment_no or f"Row_{i}"] = str(e)

    # Final Commit
    frappe.db.commit()

    summary = {
        "status": "Completed",
        "updated_count": len(updated),
        "not_found_count": len(skipped),
        "errors": errors
    }
    
    frappe.log_error("Update Job Summary", json.dumps(summary, indent=2))
    return summary
@frappe.whitelist(allow_guest=False)
def update_client_details_final_migration_1202():
    DEBUG_TITLE = "ClientDetailsMigration_FINAL"
    file_path = "/home/frappe-user/ibelong-frappe/apps/ibelong_system/ibelong_system/CD2a.json"

    # ---------------- HELPERS ----------------

    def normalize_file_number(raw_val):
        """
        1. Takes the LAST value if multiple exist.
        2. Replaces LEI with IBP.
        3. Replaces / with -.
        4. Truncates to 140 chars max to prevent 'Data too long for column name'.
        """
        if not raw_val:
            return ""
        
        # Get the last entry if comma separated
        val_str = str(raw_val)
        if "," in val_str:
            parts = [p.strip() for p in val_str.split(',') if p.strip()]
            val_str = parts[-1] if parts else ""

        val_str = val_str.strip()
        
        # Replacement Logic
        val_str = val_str.replace("/", "-").replace("\\/", "-")
        
        if "LEI" in val_str:
            val_str = val_str.replace("LEI", "IBP")
        
        # SAFETY: Ensure it fits in the primary key column
        return val_str[:140]

    def get_list_clean(value):
        if not value:
            return []
        parts = [str(p).strip() for p in str(value).split(',')]
        seen = set()
        cleaned = []
        for p in parts:
            if p and p not in seen:
                seen.add(p)
                cleaned.append(p)
        return cleaned

    def get_last_unique(value):
        """
        Splits by comma and returns the LAST valid value.
        Used for Single Fields to avoid 'Data too long'.
        """
        items = get_list_clean(value)
        return items[-1] if items else None

    def get_all_as_str_unique(value):
        """Returns unique values joined by comma."""
        items = get_list_clean(value)
        return ", ".join(items)

    def get_raw_list(value):
        if not value: return []
        return [str(p).strip() for p in str(value).split(',')]

    def get_json_value(row, *keys):
        for k in keys:
            val = row.get(k)
            if val:
                return val
        return None

    def clean_spaces(text):
        if not text: return ""
        return " ".join(str(text).split())
    
    def safe_date(date_val):
        if not date_val: return None
        try:
            d_str = get_last_unique(date_val)
            if not d_str or d_str == "None" or "0000" in str(d_str):
                return None
            return getdate(d_str)
        except Exception:
            return None

    # ---------------- LOAD JSON ----------------

    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except Exception:
        frappe.log_error(traceback.format_exc(), f"{DEBUG_TITLE} - JSON LOAD ERROR")
        return {"status": "error", "message": "Failed to load JSON"}

    if isinstance(data, dict):
        if "data" in data: data = data["data"]
        elif "response" in data: data = data["response"]
        elif not isinstance(data, list): data = [data]

    updated_count = 0
    errors = []
    
    # Track processed files in this run to handle duplicates within the JSON itself
    processed_files = set()

    meta = frappe.get_meta("Client Details")
    comment_field = meta.get_field("comment_box")
    COMMENT_LIMIT = int(comment_field.length) if comment_field and comment_field.length else 140

    # ---------------- MAIN LOOP ----------------

    for row in data:
        file_no = None
        try:
            # 1. Get File Number
            raw_fn = get_json_value(row, "File_Number", "FileNumber", "file_number")
            file_no = normalize_file_number(raw_fn)

            if not file_no:
                continue

            # 2. Setup Doc
            # Check DB existence OR if we already processed it in this loop (to prevent Duplicate Entry error)
            doc_exists = frappe.db.exists("Client Details", file_no)
            
            if doc_exists or (file_no in processed_files):
                # If we just processed it, it might be in local cache, get_doc handles that
                doc = frappe.get_doc("Client Details", file_no)
                
                # Clear child tables
                doc.set("preferred_location", [])
                doc.set("select_course_required", [])
                doc.set("select_preferred_day_time", [])
                doc.set("availability_for_attend_program", [])
                doc.set("language_fluency", [])
            else:
                doc = frappe.new_doc("Client Details")
                doc.file_number = file_no

            # Mark as processed
            processed_files.add(file_no)

            # ---------------- MAPPING ----------------
            
            doc.first_name = get_last_unique(row.get("First_Name"))
            doc.last_name_1 = get_last_unique(row.get("Last_Name"))
            doc.gender = get_last_unique(row.get("Gender"))
            doc.nationality = get_last_unique(row.get("Nationality"))
            doc.mobile_number = get_last_unique(row.get("Mobile_Number"))
            doc.email = get_last_unique(row.get("Email_ID"))
            doc.education_level = get_last_unique(row.get("Education_Level"))
            
            doc.national_status = get_last_unique(get_json_value(row, "National_Status_New_database", "National_Status"))
            
            # Dates
            doc.date_of_birth = safe_date(row.get("Date_of_Birth"))
            doc.country_of_birth = get_last_unique(row.get("Country_Of_Birth"))
            doc.date_of_expiry = safe_date(row.get("Date_of_Expiry"))
            doc.registration_date = safe_date(row.get("Registration Date"))
            doc.date_of_arrival_in_malta = safe_date(row.get("Date_of_Arrival_in_Malta"))

            # Status & Stage
            doc.status = get_last_unique(get_json_value(row, "ClientStatus_New_database"))
            doc.old_status = get_last_unique(row.get("ClientStatus_Current_database"))
            doc.assigned_course = get_last_unique(row.get("StageId"))

            # Address - CHANGED TO get_last_unique TO FIX "DATA TOO LONG"
            doc.house_number = get_last_unique(row.get("House_Number"))
            doc.house_name = get_last_unique(row.get("House_Name"))
            doc.street_name = get_last_unique(row.get("Street_Name"))
            doc.locality = get_last_unique(row.get("Locality"))
            
            doc.post_code = get_last_unique(row.get("Post_Code"))
            doc.id_card_number = get_last_unique(row.get("ID_Card_Number"))
            doc.id_card_number_2 = get_last_unique(row.get("Alternative_ID_Card_Number"))

            # Integration Info
            doc.isr_slot_date = safe_date(row.get("ISR_Slot_Date"))
            doc.ism_slot = safe_date(row.get("ISR_Slot_Date"))
            doc.isr_slot_time = get_last_unique(row.get("ISR_Slot_Time"))
            doc.selected_time = get_last_unique(row.get("ISR_Slot_Time"))
            doc.isr_status = get_last_unique(row.get("ISR_Status"))
            doc.isr_officer_name = get_last_unique(get_json_value(row, "Integration_Officer", "Integration_officer", "Integration_officer_name"))
            
            doc.integration_support = 1 
            doc.declarations_per_tender_document = 1
            doc.verify_otp = 1  

            # ---------------- COMMENTS ----------------
            
            raw_comments = get_all_as_str_unique(row.get("Comments"))
            clean_comment_text = clean_spaces(raw_comments)

            if len(clean_comment_text) > COMMENT_LIMIT:
                doc.comment_box = clean_comment_text[:COMMENT_LIMIT]
                doc.more_comments = clean_comment_text[COMMENT_LIMIT:]
            else:
                doc.comment_box = clean_comment_text
                doc.more_comments = ""

            # ---------------- OTHER TEXT FIELDS ----------------

            vulnerabilities = get_all_as_str_unique(row.get("Vulnerability"))
            if vulnerabilities:
                doc.other_vg = vulnerabilities
                doc.other_support = 1

            special_needs = get_all_as_str_unique(get_json_value(row, "Need_of_specific_assistance", "Special_Needs"))
            doc.if_yes_please_specify = get_all_as_str_unique(row.get("If_yes_Please_Specify"))
            doc.for_others_please_specify = get_all_as_str_unique(row.get("For_others_please_specify"))
            
            if special_needs:
                doc.need_of_specific_assistance = special_needs

            # ---------------- CHILD TABLES ----------------
            
            loc_list = get_list_clean(row.get("Location"))
            for loc in loc_list:
                doc.append("preferred_location", {"location": loc})

            course_list = get_list_clean(get_json_value(row, "Personal_Integration_Plan"))
            for course in course_list:
                doc.append("select_course_required", {"course_name": course})

            day_list = get_list_clean(row.get("DayAvailability"))
            for day in day_list:
                doc.append("select_preferred_day_time", {"day": day})

            time_list = get_list_clean(row.get("TimeAvailability"))
            for t in time_list:
                doc.append("availability_for_attend_program", {"available_time": t})

            l_names = get_raw_list(get_json_value(row, "Language_Language_Fluency)", "Language_Language_Fluency"))
            l_ids   = get_raw_list(get_json_value(row, "ID_Language_Fluency)", "ID_Language_Fluency"))
            l_read  = get_raw_list(get_json_value(row, "Reading_Language_Fluency)", "Reading_Language_Fluency"))
            l_speak = get_raw_list(get_json_value(row, "Speaking_Language_Fluency)", "Speaking_Language_Fluency"))
            l_write = get_raw_list(get_json_value(row, "Writing_Language_Fluency)", "Writing_Language_Fluency"))
            l_under = get_raw_list(get_json_value(row, "Understanding_Language_Fluency)", "Understanding_Language_Fluency"))

            if l_names:
                added_langs = set()
                for i in range(len(l_names)):
                    lang_name = l_names[i].strip()
                    if not lang_name: continue

                    val_id = l_ids[i] if i < len(l_ids) else ""
                    val_read = l_read[i] if i < len(l_read) else ""
                    val_speak = l_speak[i] if i < len(l_speak) else ""
                    val_write = l_write[i] if i < len(l_write) else ""
                    val_under = l_under[i] if i < len(l_under) else ""

                    unique_key = f"{lang_name}-{val_read}-{val_write}"
                    
                    if unique_key not in added_langs:
                        doc.append("language_fluency", {
                            "language": lang_name,
                            "language_id": val_id,
                            "reading": val_read,
                            "speaking": val_speak,
                            "writing": val_write,
                            "understanding": val_under
                        })
                        added_langs.add(unique_key)

            # ---------------- SAVE ----------------
            
            # Flags to bypass unnecessary validation/errors during migration
            doc.flags.ignore_permissions = True
            doc.flags.ignore_mandatory = True
            doc.flags.ignore_links = True 
            
            if doc.is_new():
                doc.insert()
            else:
                doc.save()

            updated_count += 1
            if updated_count % 100 == 0:
                frappe.db.commit()

        except Exception:
            # Only rollback if we haven't committed recently
            frappe.db.rollback()
            err_msg = f"File {file_no}: {traceback.format_exc()}"
            errors.append(err_msg)
            frappe.log_error(err_msg, f"{DEBUG_TITLE} - ROW ERROR")

    frappe.db.commit()

    return {
        "status": "success",
        "updated_count": updated_count,
        "error_count": len(errors),
        "errors": errors[:20]
    }

import frappe
import json
import traceback
import re
from frappe.utils import getdate

# Removed fields that need special logic from the map to handle them manually
FIELD_MAP = {
    # ---- IDENTIFIERS ----
    "ClientId": "client_id",
    # "File_Number": Handled manually
    "CourseId": "which_courses_are_assigned_to_the_client",

    # ---- PERSONAL ----
    "First_Name": "first_name",
    "Last_Name": "last_name_1",
    "Gender": "gender",
    "Date_of_Birth": "date_of_birth",
    "Nationality": "nationality",
    "ID_Card_Number": "id_card_number",
    "Alternative_ID_Card_Number": "passport_number",
    "Country_Of_Birth": "country_of_birth",

    # ---- CONTACT ----
    "Mobile_Number": "mobile_number",
    "Email_ID": "email",
    "Street_Name": "street_name",
    "Locality": "locality",
    "Post_Code": "post_code",
    "Correspondence_Address": "correspondence_address",

    # ---- COURSE / PROGRESSION ----
    "Course_Level": "course_level",
    "Service_Provider": "service_provider",
    "Assigned_Batch": "approved_by_sp",
    "Certificate_Number": "certificate_number",
    "Result": "result",
    "Selected_Course_Type": "selected_course_type",

    # ---- STATUS ----
    "ClientStatus_New_database": "status",
    "ClientStatus_Current_database": "status_current",

    # ---- ADMIN / META ----
    "Name": "cohort",

    # ---- INSTITUTE / IRM ----
    # Handled manually below for special logic
    # "Exempted": "exemption", 
    # "InstituteRegistered": "institute_registered",
    "InstituteRegistrationDate": "institute_registered_date",
}

def create_client_progression_info1002():
    import json, re, traceback
    import frappe

    FILE_PATH = (
        "/home/frappe-user/ibelong-frappe/apps/"
        "ibelong_system/ibelong_system/CPD3a.json"
    )

    def normalize_date(val):
        return val.split(" ")[0] if val else ""

    def normalize_file_number(val):
        """
        Converts 'LEI/23/000001' -> 'IBP-23-000001'
        """
        val = (val or "").strip()
        # Replace LEI with IBP
        val = val.replace("LEI", "IBP")
        # Replace slashes with dashes
        val = val.replace("/", "-")
        return val

    def parse_house(house_name, house_no):
        hn = (house_name or "").strip()
        hno = (house_no or "").strip()

        if re.fullmatch(r"\d+", hn):
            return "", hn

        if "," in hno and not hn:
            parts = [p.strip() for p in hno.split(",", 1)]
            if re.search(r"\d", parts[0]):
                return parts[1], parts[0]

        return hn, hno

    with open(FILE_PATH, "r") as f:
        client_data = json.load(f)

    created, skipped, errors = [], [], {}

    for row in client_data:
        try:
            # ---- Normalize NULLs ----
            for k in row:
                row[k] = row.get(k) or ""

            # 1. Process File Number
            raw_file_no = row.get("File_Number") 
            file_no = normalize_file_number(raw_file_no)
            
            if not file_no:
                skipped.append("Missing file number")
                continue

            course_id = row.get("CourseId")
            enrolment_no = f"{file_no}_{course_id}" if course_id else file_no

            # Create the document
            doc = frappe.get_doc({
                "doctype": "Client Progression Details",
                "file_number": file_no,
                "enrolment_number": enrolment_no,
            })

            extra_json = {}

            # ---- FIELD MAPPING ----
            for json_key, doc_field in FIELD_MAP.items():
                val = row.get(json_key)

                # Special cleaning for Result/Certificate
                if doc_field in ["result", "certificate_number"] and val:
                    val = str(val).strip()

                if doc_field in (
                    "date_of_birth",
                    "registration_date",
                    "application_date",
                    "institute_registration_date",
                ):
                    val = normalize_date(val)

                if doc.meta.has_field(doc_field):
                    setattr(doc, doc_field, val)
                else:
                    # DEBUG: This prints if the field name is wrong in the DocType
                    if doc_field in ["result", "certificate_number"]:
                        print(f"⚠️ Warning: Field '{doc_field}' not found in DocType for {enrolment_no}")
                    extra_json[json_key] = val

            # ---- SPECIAL LOGIC: EXEMPTION ----
            # If Exempted is "Exempted", set exemption="Yes" and verify=1
            exempted_val = row.get("Exempted")
            if exempted_val == "Exempted":
                doc.exemption = "Yes"
                doc.verify = 1
            else:
                # Optional: Set defaults if not exempted?
                pass

            # ---- SPECIAL LOGIC: INSTITUTE ----
            # If InstituteRegistered is True/"True", set institute_registered=1
            inst_reg_val = row.get("InstituteRegistered")
            # Handle boolean True or string "True"
            if inst_reg_val is True or str(inst_reg_val).lower() == "true":
                doc.institute_registered = 1
            else:
                doc.institute_registered = 0

            # ---- HOUSE PARSING ----
            house_name, house_no = parse_house(
                row.get("House_Name"),
                row.get("House_Number")
            )
            doc.house_name = house_name
            doc.house_number = house_no

            # ---- DATE RULES ----
            course_level = (row.get("Course_Level") or "").lower()
            if "stage 1" in course_level or "foundation" in course_level:
                doc.registration_date = normalize_date(row.get("Registration Date"))

            if "stage 2" in course_level:
                doc.registration_date = normalize_date(row.get("Registration Date"))
                doc.application_date = normalize_date(row.get("Application_Date"))

            # ---- STORE FULL RAW JSON ----
            doc.raw_json_data = json.dumps(row, indent=2)

            # Insert
            doc.flags.ignore_mails = True
            doc.insert(ignore_permissions=True, ignore_mandatory=True)
            frappe.db.commit()

            created.append(enrolment_no)
            
            # DEBUG PRINT: Verify result/cert saved
            if row.get("Result") or row.get("Certificate_Number"):
                print(f"✅ {enrolment_no} -> Result: {doc.result}, Cert: {doc.certificate_number}")
            else:
                print(f"✅ Created: {enrolment_no}")

        except Exception as e:
            frappe.db.rollback()
            errors.setdefault(enrolment_no, []).append(str(e))
            skipped.append(enrolment_no)
            frappe.log_error(
                title=f"Import error {enrolment_no}",
                message=traceback.format_exc(),
            )

    frappe.log_error(
        "Client Progression Import Summary",
        f"Created={len(created)}, Skipped={len(skipped)}"
    )

    return {
        "message": "Client Progression Import Completed",
        "created": len(created),
        "skipped": len(skipped),
        "errors": errors,
    }









FIELD_MAP = {
    # ---- IDENTIFIERS ----
    "ClientId": "client_id",
    "File_Number": "file_number",
    "CourseId": "which_courses_are_assigned_to_the_client",

    # ---- PERSONAL ----
    "First_Name": "first_name",
    "Last_Name": "last_name_1",
    "Gender": "gender",
    "Date_of_Birth": "date_of_birth",
    "Nationality": "nationality",
    "ID_Card_Number": "id_card_number",
    "Alternative_ID_Card_Number": "passport_number",
    "Country_Of_Birth": "country_of_birth",

    # ---- CONTACT ----
    "Mobile_Number": "mobile_number",
    "Email_ID": "email",
    "Street_Name": "street_name",
    "Locality": "locality",
    "Post_Code": "post_code",
    "Correspondence_Address": "correspondence_address",

    # ---- COURSE / PROGRESSION ----
    "Course_Level": "course_level",
    "Service_Provider": "service_provider",
    "Assigned_Batch": "approved_by_sp",
    "Certificate_Number": "certificate_number",
    "Result": "result",
    "Selected_Course_Type": "selected_course_type",

    # ---- STATUS ----
    "ClientStatus_New_database": "status",
    "ClientStatus_Current_database": "status_current",

    # ---- ADMIN / META ----
    "Name": "cohort",

    # ---- INSTITUTE / IRM ----
    "Exempted": "exempted",
    "InstituteRegistered": "institute_registered",
    "InstituteRegistrationDate": "institute_registered_date",
}

def create_client_progression_info0902():
    import json, re, traceback
    import frappe

    FILE_PATH = (
        "/home/frappe-user/ibelong-frappe/apps/"
        "ibelong_system/ibelong_system/CPD10-02-26.json"
    )

    def normalize_date(val):
        return val.split(" ")[0] if val else ""

    def normalize_file_number(val):
        return (val or "").strip()

    def parse_house(house_name, house_no):
        hn = (house_name or "").strip()
        hno = (house_no or "").strip()

        if re.fullmatch(r"\d+", hn):
            return "", hn

        if "," in hno and not hn:
            parts = [p.strip() for p in hno.split(",", 1)]
            if re.search(r"\d", parts[0]):
                return parts[1], parts[0]

        return hn, hno

    with open(FILE_PATH, "r") as f:
        client_data = json.load(f)

    created, skipped, errors = [], [], {}

    for row in client_data:
        try:
            # ---- Normalize NULLs ----
            for k in row:
                row[k] = row.get(k) or ""

            file_no = normalize_file_number(
                row.get("File_Number") or row.get("ClientId")
            )
            if not file_no:
                skipped.append("Missing file number")
                continue

            course_id = row.get("CourseId")
            enrolment_no = f"{file_no}_{course_id}" if course_id else file_no

            doc = frappe.get_doc({
                "doctype": "Client Progression Details",
                "file_number": file_no,
                "enrolment_number": enrolment_no,
            })

            extra_json = {}

            # ---- FIELD MAPPING ----
            for json_key, doc_field in FIELD_MAP.items():
                val = row.get(json_key)

                if doc_field in (
                    "date_of_birth",
                    "registration_date",
                    "application_date",
                    "institute_registration_date",
                ):
                    val = normalize_date(val)

                if doc.meta.has_field(doc_field):
                    setattr(doc, doc_field, val)
                else:
                    extra_json[json_key] = val

            # ---- HOUSE PARSING ----
            house_name, house_no = parse_house(
                row.get("House_Name"),
                row.get("House_Number")
            )
            doc.house_name = house_name
            doc.house_number = house_no

            # ---- DATE RULES ----
            course_level = (row.get("Course_Level") or "").lower()
            if "stage 1" in course_level or "foundation" in course_level:
                doc.registration_date = normalize_date(row.get("Registration Date"))

            if "stage 2" in course_level:
                doc.application_date = normalize_date(row.get("Application_Date"))

            # ---- STORE FULL RAW JSON ----
            doc.raw_json_data = json.dumps(row, indent=2)

            doc.flags.ignore_mails = True
            doc.insert(ignore_permissions=True, ignore_mandatory=True)
            frappe.db.commit()

            created.append(enrolment_no)
            print(f"✅ Created: {enrolment_no}")

        except Exception as e:
            frappe.db.rollback()
            errors.setdefault(enrolment_no, []).append(str(e))
            skipped.append(enrolment_no)
            frappe.log_error(
                title=f"Import error {enrolment_no}",
                message=traceback.format_exc(),
            )

    frappe.log_error(
        "Client Progression Import Summary",
        f"Created={len(created)}, Skipped={len(skipped)}"
    )

    return {
        "message": "Client Progression Import Completed",
        "created": len(created),
        "skipped": len(skipped),
        "errors": errors,
    }


@frappe.whitelist(allow_guest=False)
def update_client_details_final_migration_0902():
    DEBUG_TITLE = "ClientDetailsMigration_FINAL"
    file_path = "/home/frappe-user/ibelong-frappe/apps/ibelong_system/ibelong_system/output.json"

    # ---------------- HELPERS ----------------

    def normalize_file_number(file_no):
        if not file_no:
            return ""
        file_no = str(file_no).strip().replace("/", "-")
        if file_no.startswith("LEI-"):
            file_no = file_no.replace("LEI-", "IBP-", 1)
        return file_no

    def split_and_clean(value):
        """
        Splits by comma, removes duplicates, removes empty strings.
        Input: "Barbara, Flat 7, Barbara, Flat 7" -> Output: ["Barbara", "Flat 7"]
        """
        if not value:
            return []
        parts = [str(p).strip() for p in str(value).split(',')]
        seen = set()
        cleaned = []
        for p in parts:
            if p and p not in seen:
                seen.add(p)
                cleaned.append(p)
        return cleaned

    def get_first(value):
        """Returns the first unique value found."""
        items = split_and_clean(value)
        return items[0] if items else None

    def get_all_as_str(value):
        """Returns unique values joined by comma."""
        items = split_and_clean(value)
        return ", ".join(items)

    def get_json_value(row, *keys):
        """Checks multiple keys and returns the first non-empty value."""
        for k in keys:
            val = row.get(k)
            if val:
                return val
        return None

    def clean_spaces(text):
        """Removes newlines, tabs, and double spaces."""
        if not text: 
            return ""
        return " ".join(str(text).split())
    
    def safe_date(date_val):
        """Safely parses dates. Returns None if invalid or empty."""
        if not date_val:
            return None
        try:
            # Clean string first
            d = str(date_val).strip()
            if not d or d == "None" or d == "0000-00-00":
                return None
            return getdate(d)
        except Exception:
            # If parsing fails, return None to prevent script crash
            return None

    # ---------------- LOAD JSON ----------------

    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except Exception:
        frappe.log_error(traceback.format_exc(), f"{DEBUG_TITLE} - JSON LOAD ERROR")
        return {"status": "error", "message": "Failed to load JSON"}

    if isinstance(data, dict):
        data = data.get("data", [])

    updated_count = 0
    errors = []

    # Get max length for comment box dynamically
    meta = frappe.get_meta("Client Details")
    comment_field = meta.get_field("comment_box")
    COMMENT_LIMIT = int(comment_field.length) if comment_field and comment_field.length else 140

    # ---------------- MAIN LOOP ----------------

    for row in data:
        file_no = None
        try:
            # 1. Get File Number
            raw_fn = get_json_value(row, "File_Number", "FileNumber", "file_number")
            file_no = normalize_file_number(raw_fn)

            if not file_no:
                continue

            # 2. Setup Doc
            if frappe.db.exists("Client Details", file_no):
                doc = frappe.get_doc("Client Details", file_no)
                # Clear child tables to ensure clean slate
                doc.set("preferred_location", [])
                doc.set("select_course_required", [])
                doc.set("select_preferred_day_time", [])
                doc.set("availability_for_attend_program", [])
                doc.set("language_fluency", [])
            else:
                doc = frappe.new_doc("Client Details")
                doc.file_number = file_no

            # ---------------- MAPPING ----------------
            
            doc.first_name = get_first(row.get("First_Name"))
            doc.last_name_1 = get_first(row.get("Last_Name"))
            doc.gender = get_first(row.get("Gender"))
            doc.national_status = get_first(get_json_value(row, "National_Status_New_database", "National_Status"))
            doc.nationality = get_first(row.get("Nationality"))
            doc.mobile_number = get_first(row.get("Mobile_Number"))
            doc.email = get_first(row.get("Email_ID"))
            doc.education_level = get_first(row.get("Education_Level"))
            
            # Dates (Using safe_date to prevent crashes)
            doc.date_of_birth = safe_date(get_first(row.get("Date_of_Birth")))
            doc.country_of_birth = get_first(row.get("Country_Of_Birth"))
            doc.date_of_expiry = safe_date(get_first(row.get("Date_of_Expiry")))
            doc.registration_date = safe_date(get_first(row.get("Registration Date")))
            doc.date_of_arrival_in_malta = safe_date(get_first(row.get("Date_of_Arrival_in_Malta")))

            # Status & Stage
            doc.status = get_first(get_json_value(row, "ClientStatus_New_database", "ClientStatus"))
            doc.old_status = get_first(row.get("ClientStatus_Current_database"))
            doc.assigned_course = get_first(row.get("StageId"))

            # Address
            doc.house_number = get_all_as_str(row.get("House_Number"))
            doc.house_name = get_all_as_str(row.get("House_Name"))
            doc.street_name = get_all_as_str(row.get("Street_Name"))
            doc.locality = get_all_as_str(row.get("Locality"))
            doc.post_code = get_first(row.get("Post_Code"))
            doc.id_card_number = get_first(row.get("ID_Card_Number"))
            doc.id_card_number_2 = get_first(row.get("Alternative_ID_Card_Number"))

            # Integration Info
            doc.isr_slot_date = safe_date(get_first(row.get("ISR_Slot_Date")))
            doc.ism_slot = safe_date(get_first(row.get("ISR_Slot_Date")))
            doc.isr_slot_time = get_first(row.get("ISR_Slot_Time"))
            doc.selected_time = get_first(row.get("ISR_Slot_Time"))
            doc.isr_status = get_first(row.get("ISR_Status"))
            doc.isr_officer_name = get_first(get_json_value(row, "Integration_officer", "Integration_officer_name"))
            
            req_support = get_first(row.get("Integration_support_Required"))
            doc.integration_support = 1 if req_support and req_support.lower() == "yes" else 0

            # ---------------- COMMENTS LOGIC ----------------
            
            raw_comments = get_all_as_str(row.get("Comments"))
            clean_comment_text = clean_spaces(raw_comments)

            if len(clean_comment_text) > COMMENT_LIMIT:
                doc.comment_box = clean_comment_text[:COMMENT_LIMIT]
                doc.more_comments = clean_comment_text[COMMENT_LIMIT:]
            else:
                doc.comment_box = clean_comment_text
                doc.more_comments = ""

            # ---------------- OTHER TEXT FIELDS ----------------

            vulnerabilities = get_all_as_str(row.get("Vulnerability"))
            if vulnerabilities:
                doc.other_vg = vulnerabilities
                doc.other_support = 1

            # Fallback for Special Needs (checks both key variations)
            special_needs = get_all_as_str(get_json_value(row, "Need_of_specific_assistance", "Special_Needs"))
            
            doc.if_yes_please_specify = get_all_as_str(row.get("If_yes_Please_Specify"))
            doc.for_others_please_specify = get_all_as_str(row.get("For_others_please_specify"))
            
            if special_needs:
                doc.need_of_specific_assistance = special_needs

            # ---------------- CHILD TABLES ----------------
            
            # Location
            loc_list = split_and_clean(row.get("Location"))
            for loc in loc_list:
                doc.append("preferred_location", {"location": loc})

            # Courses
            course_list = split_and_clean(get_json_value(row, "Personal_Integration_Plan", "Personalintegrationplan"))
            for course in course_list:
                doc.append("select_course_required", {"course_name": course})

            # Days
            day_list = split_and_clean(row.get("DayAvailability"))
            for day in day_list:
                doc.append("select_preferred_day_time", {"day": day})

            # Times
            time_list = split_and_clean(row.get("TimeAvailability"))
            for t in time_list:
                doc.append("availability_for_attend_program", {"available_time": t})

            # Languages
            l_names = split_and_clean(get_json_value(row, "Language_Language_Fluency)", "Language_Language_Fluency"))
            l_ids   = split_and_clean(get_json_value(row, "ID_Language_Fluency)", "ID_Language_Fluency"))
            l_read  = split_and_clean(get_json_value(row, "Reading_Language_Fluency)", "Reading_Language_Fluency"))
            l_speak = split_and_clean(get_json_value(row, "Speaking_Language_Fluency)", "Speaking_Language_Fluency"))
            l_write = split_and_clean(get_json_value(row, "Writing_Language_Fluency)", "Writing_Language_Fluency"))
            l_under = split_and_clean(get_json_value(row, "Understanding_Language_Fluency)", "Understanding_Language_Fluency"))

            if l_names:
                for i in range(len(l_names)):
                    doc.append("language_fluency", {
                        "language": l_names[i],
                        "language_id": l_ids[i] if i < len(l_ids) else "",
                        "reading": l_read[i] if i < len(l_read) else "",
                        "speaking": l_speak[i] if i < len(l_speak) else "",
                        "writing": l_write[i] if i < len(l_write) else "",
                        "understanding": l_under[i] if i < len(l_under) else ""
                    })

            # ---------------- SAVE ----------------
            
            doc.flags.ignore_permissions = True
            doc.flags.ignore_mandatory = True
            
            if doc.is_new():
                doc.insert()
            else:
                doc.save()

            updated_count += 1
            if updated_count % 100 == 0:
                frappe.db.commit()

        except Exception:
            frappe.db.rollback()
            err_msg = f"File {file_no}: {traceback.format_exc()}"
            errors.append(err_msg)
            frappe.log_error(err_msg, f"{DEBUG_TITLE} - ROW ERROR")

    frappe.db.commit()

    return {
        "status": "success",
        "updated_count": updated_count,
        "error_count": len(errors),
        "errors": errors[:20]
    }

import frappe
import json
import traceback
import re

@frappe.whitelist(allow_guest=False)
def update_client_details_final_migration_v2():
    DEBUG_TITLE = "ClientDetailsMigration_FINAL"
    file_path = "/home/frappe-user/ibelong-frappe/apps/ibelong_system/ibelong_system/output.json"

    # ---------------- HELPERS ----------------

    def normalize_file_number(file_no):
        if not file_no:
            return ""
        file_no = str(file_no).strip().replace("/", "-")
        if file_no.startswith("LEI-"):
            file_no = file_no.replace("LEI-", "IBP-", 1)
        return file_no

    def split_and_clean(value):
        """
        Splits by comma, removes duplicates, removes empty strings.
        Input: "Barbara, Flat 7, Barbara, Flat 7" -> Output: ["Barbara", "Flat 7"]
        """
        if not value:
            return []
        parts = [str(p).strip() for p in str(value).split(',')]
        seen = set()
        cleaned = []
        for p in parts:
            if p and p not in seen:
                seen.add(p)
                cleaned.append(p)
        return cleaned

    def get_first(value):
        """Returns the first unique value found."""
        items = split_and_clean(value)
        return items[0] if items else None

    def get_all_as_str(value):
        """Returns unique values joined by comma."""
        items = split_and_clean(value)
        return ", ".join(items)

    def get_json_value(row, *keys):
        """Checks multiple keys."""
        for k in keys:
            if row.get(k):
                return row.get(k)
        return None

    def clean_spaces(text):
        """Removes newlines, tabs, and double spaces."""
        if not text: 
            return ""
        # join(split()) removes all extra whitespace between words
        return " ".join(str(text).split())

    # ---------------- LOAD JSON ----------------

    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except Exception:
        frappe.log_error(traceback.format_exc(), f"{DEBUG_TITLE} - JSON LOAD ERROR")
        return {"status": "error", "message": "Failed to load JSON"}

    if isinstance(data, dict):
        data = data.get("data", [])

    updated_count = 0
    errors = []

    # Get max length for comment box dynamically
    meta = frappe.get_meta("Client Details")
    comment_field = meta.get_field("comment_box")
    # Default to 140 if field not found or length not set
    COMMENT_LIMIT = int(comment_field.length) if comment_field and comment_field.length else 140

    # ---------------- MAIN LOOP ----------------

    for row in data:
        file_no = None
        try:
            # 1. Get File Number
            raw_fn = get_json_value(row, "File_Number", "FileNumber", "file_number")
            file_no = normalize_file_number(raw_fn)

            if not file_no:
                continue

            # 2. Setup Doc (Wipe old data logic implied by 'doc.insert')
            if frappe.db.exists("Client Details", file_no):
                doc = frappe.get_doc("Client Details", file_no)
                # Clear child tables
                doc.set("preferred_location", [])
                doc.set("select_course_required", [])
                doc.set("select_preferred_day_time", [])
                doc.set("availability_for_attend_program", [])
                doc.set("language_fluency", [])
            else:
                doc = frappe.new_doc("Client Details")
                doc.file_number = file_no

            # ---------------- MAPPING ----------------
            
            doc.first_name = get_first(row.get("First_Name"))
            doc.last_name_1 = get_first(row.get("Last_Name"))
            doc.gender = get_first(row.get("Gender"))
            doc.national_status = get_first(row.get("National_Status_New_database"))
            doc.nationality = get_first(row.get("Nationality"))
            doc.mobile_number = get_first(row.get("Mobile_Number"))
            doc.email = get_first(row.get("Email_ID"))
            doc.education_level = get_first(row.get("Education_Level"))
            
            # Dates
            doc.date_of_birth = get_first(row.get("Date_of_Birth"))
            doc.country_of_birth = get_first(row.get("Country_Of_Birth"))
            doc.date_of_expiry = get_first(row.get("Date_of_Expiry"))
            doc.registration_date = get_first(row.get("Registration Date"))
            doc.date_of_arrival_in_malta = get_first(row.get("Date_of_Arrival_in_Malta"))

            # Status & Stage
            doc.status = get_first(get_json_value(row, "ClientStatus_New_database", "ClientStatus"))
            doc.old_status = get_first(row.get("ClientStatus_Current_database"))
            doc.assigned_course = get_first(row.get("StageId"))

            # Address
            doc.house_number = get_all_as_str(row.get("House_Number"))
            doc.house_name = get_all_as_str(row.get("House_Name"))
            doc.street_name = get_all_as_str(row.get("Street_Name"))
            doc.locality = get_all_as_str(row.get("Locality"))
            doc.post_code = get_first(row.get("Post_Code"))
            doc.id_card_number = get_first(row.get("ID_Card_Number"))
            doc.id_card_number_2 = get_first(row.get("Alternative_ID_Card_Number"))

            # Integration Info
            doc.isr_slot_date = get_first(row.get("ISR_Slot_Date"))
            doc.ism_slot = get_first(row.get("ISR_Slot_Date")) 
            doc.isr_slot_time = get_first(row.get("ISR_Slot_Time"))
            doc.isr_status = get_first(row.get("ISR_Status"))
            doc.isr_officer_name = get_first(get_json_value(row, "Integration_officer", "Integration_officer_name"))
            
            req_support = get_first(row.get("Integration_support_Required"))
            doc.integration_support = 1 if req_support and req_support.lower() == "yes" else 0

            # ---------------- COMMENTS LOGIC ----------------
            
            raw_comments = get_all_as_str(row.get("Comments"))
            # Clean unwanted spaces/newlines
            clean_comment_text = clean_spaces(raw_comments)

            if len(clean_comment_text) > COMMENT_LIMIT:
                # Split text
                doc.comment_box = clean_comment_text[:COMMENT_LIMIT]
                doc.more_comments = clean_comment_text[COMMENT_LIMIT:]
            else:
                doc.comment_box = clean_comment_text
                doc.more_comments = ""

            # ---------------- OTHER TEXT FIELDS ----------------

            vulnerabilities = get_all_as_str(row.get("Vulnerability"))
            if vulnerabilities:
                doc.other_vg = vulnerabilities
                doc.other_support = 1

            special_needs = get_all_as_str(row.get("Need_of_specific_assistance"))
            doc.if_yes_please_specify = get_all_as_str(row.get("If_yes_Please_Specify"))
            # doc.need_of_specific_assistance = get_all_as_str(row.get("Need_of_specific_assistance"))
            doc.for_others_please_specify = get_all_as_str(row.get("For_others_please_specify"))
            if special_needs:
                doc.need_of_specific_assistance = special_needs

            # ---------------- CHILD TABLES ----------------
            
            # Location
            loc_list = split_and_clean(row.get("Location"))
            for loc in loc_list:
                doc.append("preferred_location", {"location": loc})

            # Courses
            course_list = split_and_clean(get_json_value(row, "Personal_Integration_Plan", "Personalintegrationplan"))
            for course in course_list:
                doc.append("select_course_required", {"course_name": course})

            # Days
            day_list = split_and_clean(row.get("DayAvailability"))
            for day in day_list:
                doc.append("select_preferred_day_time", {"day": day})

            # Times
            time_list = split_and_clean(row.get("TimeAvailability"))
            for t in time_list:
                doc.append("availability_for_attend_program", {"available_time": t})

            # Languages
            l_names = split_and_clean(get_json_value(row, "Language_Language_Fluency)", "Language_Language_Fluency"))
            l_ids   = split_and_clean(get_json_value(row, "ID_Language_Fluency)", "ID_Language_Fluency"))
            l_read  = split_and_clean(get_json_value(row, "Reading_Language_Fluency)", "Reading_Language_Fluency"))
            l_speak = split_and_clean(get_json_value(row, "Speaking_Language_Fluency)", "Speaking_Language_Fluency"))
            l_write = split_and_clean(get_json_value(row, "Writing_Language_Fluency)", "Writing_Language_Fluency"))
            l_under = split_and_clean(get_json_value(row, "Understanding_Language_Fluency)", "Understanding_Language_Fluency"))

            if l_names:
                for i in range(len(l_names)):
                    doc.append("language_fluency", {
                        "language": l_names[i],
                        "language_id": l_ids[i] if i < len(l_ids) else "",
                        "reading": l_read[i] if i < len(l_read) else "",
                        "speaking": l_speak[i] if i < len(l_speak) else "",
                        "writing": l_write[i] if i < len(l_write) else "",
                        "understanding": l_under[i] if i < len(l_under) else ""
                    })

            # ---------------- SAVE ----------------
            
            doc.flags.ignore_permissions = True
            doc.flags.ignore_mandatory = True
            
            if doc.is_new():
                doc.insert()
            else:
                doc.save()

            updated_count += 1
            if updated_count % 100 == 0:
                frappe.db.commit()

        except Exception:
            frappe.db.rollback()
            err_msg = f"File {file_no}: {traceback.format_exc()}"
            errors.append(err_msg)
            frappe.log_error(err_msg, f"{DEBUG_TITLE} - ROW ERROR")

    frappe.db.commit()

    return {
        "status": "success",
        "updated_count": updated_count,
        "error_count": len(errors),
        "errors": errors[:20]
    }

import json
import re
import traceback
import frappe


# --------------------------------------------------
# Dummy request binding (prevents hook crashes)
# --------------------------------------------------
def _bind_dummy_request():
    prev = getattr(frappe.local, "request", None)

    class DummyRequest:
        args = {}
        form = {}

    frappe.local.request = DummyRequest()
    return prev


def _restore_request(prev):
    if prev is None:
        frappe.local.__dict__.pop("request", None)
    else:
        frappe.local.request = prev


# --------------------------------------------------
# FILE NUMBER NORMALIZER
# LEI/25/000222 -> IBP-25-000222
# --------------------------------------------------
def normalize_file_number(file_no):
    if not file_no:
        return file_no

    file_no = file_no.strip()

    if file_no.upper().startswith("LEI/"):
        parts = file_no.split("/")
        if len(parts) == 3:
            return f"IBP-{parts[1]}-{parts[2]}"

    return file_no


# --------------------------------------------------
# FIELD COMPARISON
# --------------------------------------------------
def has_diff(doc, incoming_data, ignore_fields):
    for field, new_val in incoming_data.items():
        if field in ignore_fields or field in ("doctype", "name"):
            continue

        if not hasattr(doc, field):
            continue

        old_val = getattr(doc, field)

        if (old_val or "") != (new_val or ""):
            return True

    return False


# --------------------------------------------------
# MAIN IMPORT FUNCTION
# --------------------------------------------------
def create_client_progression_info2():
    DEBUG_TITLE = "CPD-->"

    FILE_PATH = (
        "/home/frappe-user/ibelong-frappe/apps/"
        "ibelong_system/ibelong_system/Client_Progression_full_data_04_01_2026.json"
    )

    IGNORE_COMPARE_FIELDS = {
        "passport_number",   # Alternative_ID_Card_Number
        "cohort_id",         # CohortId
        "code",
        "description",
    }

    try:
        with open(FILE_PATH, "r") as f:
            client_data = json.load(f)

        created, updated, skipped = [], [], []
        errors_per_doc = {}

        for client in client_data:

            # -----------------------------
            # Normalize JSON values
            # -----------------------------
            for k in client:
                client[k] = client.get(k) or ""

            raw_file_no = client.get("File_Number") or client.get("ClientId")
            file_no = normalize_file_number(raw_file_no)

            if not file_no:
                skipped.append({"reason": "Missing File Number", "client": client})
                continue

            course_id = client.get("CourseId", "")
            enrolment_no = f"{file_no}_{course_id}" if course_id else file_no

            status = client.get("ClientStatus", "").lower()

            # -----------------------------
            # Date of Birth
            # -----------------------------
            dob = ""
            try:
                dob_raw = client.get("Date_of_Birth", "")
                dob = dob_raw.split(" ")[0] if dob_raw else ""
            except Exception as e:
                errors_per_doc.setdefault(file_no, []).append({"dob": str(e)})

            # -----------------------------
            # Base Doc Data
            # -----------------------------
            doc_data = {
                "doctype": "Client Progression Details",
                "file_number": file_no,
                "enrolment_number": enrolment_no,

                # Course
                "course_level": client.get("Course_Level"),
                "which_courses_are_assigned_to_the_client": course_id,
                "service_provider": client.get("Service_Provider"),
                "approved_by_sp": client.get("Assigned_Batch"),
                "certificate_number": client.get("Certificate_Number"),
                "result": client.get("Result"),
                "status": client.get("ClientStatus"),

                # Personal
                "first_name": client.get("First_Name"),
                "last_name_1": client.get("Last_Name"),
                "gender": client.get("Gender"),
                "date_of_birth": dob,
                "nationality": client.get("Nationality"),
                "id_card_number": client.get("ID_Card_Number"),
                "passport_number": client.get("Alternative_ID_Card_Number"),
                "country_of_birth": client.get("Country_Of_Birth"),

                # Contact
                "mobile_number": client.get("Mobile_Number"),
                "email": client.get("Email_ID"),
                "street_name": client.get("Street_Name"),
                "locality": client.get("Locality"),
                "post_code": client.get("Post_Code"),
                "correspondence_address": client.get("Correspondence_Address"),

                # Static
                "selected_course_type": client.get("Selected_Course_Type") or "Free",
            }

            # -----------------------------
            # SMART HOUSE PARSING
            # -----------------------------
            raw_house_name = (client.get("House_Name") or "").strip()
            raw_house_no = (client.get("House_Number") or "").strip()

            def has_digits(s):
                return bool(re.search(r"\d", s))

            def is_digits_only(s):
                return bool(re.fullmatch(r"\d+", s))

            final_house_name = raw_house_name
            final_house_no = raw_house_no

            try:
                if is_digits_only(raw_house_name):
                    final_house_no = raw_house_name
                    final_house_name = raw_house_no
                elif has_digits(raw_house_name) and "," in raw_house_name and not raw_house_no:
                    left, right = [p.strip() for p in raw_house_name.split(",", 1)]
                    if has_digits(left):
                        final_house_no = left
                        final_house_name = right
                elif has_digits(raw_house_name) and raw_house_no and not has_digits(raw_house_no):
                    final_house_no = raw_house_name
                    final_house_name = raw_house_no
            except Exception as e:
                errors_per_doc.setdefault(file_no, []).append({"house_parse": str(e)})

            doc_data["house_name"] = final_house_name
            doc_data["house_number"] = final_house_no

            # -----------------------------
            # EXISTING RECORD CHECK
            # -----------------------------
            existing_name = frappe.db.get_value(
                "Client Progression Details",
                {"enrolment_number": enrolment_no},
                "name",
            )

            prev_req = None

            try:
                prev_req = _bind_dummy_request()

                if existing_name:
                    doc = frappe.get_doc("Client Progression Details", existing_name)

                    if not has_diff(doc, doc_data, IGNORE_COMPARE_FIELDS):
                        skipped.append(f"{enrolment_no} (no changes)")
                        continue

                    for k, v in doc_data.items():
                        if k in IGNORE_COMPARE_FIELDS:
                            continue
                        if hasattr(doc, k):
                            setattr(doc, k, v)

                    # ---- DATE RULES ----
                    if "stage 1" in status or "foundation" in status:
                        doc.registration_date = client.get("Registration Date")

                    if "stage 2" in status:
                        doc.application_date = client.get("Application_Date")

                    doc.flags.ignore_mails = True
                    doc.save(ignore_permissions=True)
                    frappe.db.commit()

                    updated.append(enrolment_no)
                    print(f"🔄 Updated: {enrolment_no}")

                else:
                    doc = frappe.get_doc(doc_data)

                    if "stage 1" in status or "foundation" in status:
                        doc.registration_date = client.get("Registration Date")

                    if "stage 2" in status:
                        doc.application_date = client.get("Application_Date")

                    doc.flags.ignore_mails = True
                    doc.insert(ignore_permissions=True, ignore_mandatory=True)
                    frappe.db.commit()

                    created.append(enrolment_no)
                    print(f"✅ Created: {enrolment_no}")

            except Exception as e:
                frappe.log_error(
                    title=f"Save error {enrolment_no}",
                    message=traceback.format_exc(),
                )
                errors_per_doc.setdefault(file_no, []).append({"save": str(e)})
                skipped.append(enrolment_no)

            finally:
                _restore_request(prev_req)

        frappe.log_error(
            "Client Progression Import Summary",
            f"Created={len(created)}, Updated={len(updated)}, Skipped={len(skipped)}",
        )

        return {
            "message": "Client Progression Import Completed Successfully",
            "created": len(created),
            "updated": len(updated),
            "skipped": len(skipped),
            "errors_per_doc": errors_per_doc,
        }

    except Exception as e:
        frappe.log_error(
            "Fatal Client Progression Import Error",
            traceback.format_exc(),
        )
        return {"error": str(e)}




import frappe
import json
import traceback
import re


@frappe.whitelist(allow_guest=False)
def update_client_details_from_grouped_json28():
    DEBUG_TITLE = "ClientDetailsMigration_FINAL"

    file_path = "/home/frappe-user/ibelong-frappe/apps/ibelong_system/ibelong_system/CD2a.json"

    # ---------------- HELPERS ----------------

    def normalize_file_number(file_no: str) -> str:
        if not file_no:
            return ""
        file_no = file_no.replace("/", "-").strip()
        if file_no.startswith("LEI-"):
            file_no = file_no.replace("LEI-", "IBP-", 1)
        return file_no

    def last_value(v):
        if v is None:
            return ""
        parts = [p.strip() for p in str(v).split(",") if p and str(p).strip()]
        return parts[-1] if parts else ""

    def split_multi(v):
        if not v:
            return []
        seen, out = set(), []
        for p in str(v).split(","):
            p = p.strip()
            if p and p not in seen:
                seen.add(p)
                out.append(p)
        return out
    def all_values_as_text(v):
        """Return comma-separated string of ALL values"""
        parts = split_multi(v)
        return ", ".join(parts)


    def safe_set(doc, fieldname, value):
        """Set only if JSON has value AND DB field is empty"""
        if not value:
            return
        if getattr(doc, fieldname, None):
            return
        setattr(doc, fieldname, value)
    def get_max_length(doctype, fieldname):
        meta = frappe.get_meta(doctype)
        field = meta.get_field(fieldname)
        return int(field.length) if field and field.length else 140  # fallback

    # ---------------- LOAD JSON ----------------

    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except Exception:
        frappe.log_error(traceback.format_exc(), f"{DEBUG_TITLE} - JSON LOAD ERROR")
        return {"status": "error", "message": "Failed to load JSON"}

    if isinstance(data, dict):
        data = data.get("data", [])

    client_meta = frappe.get_meta("Client Details")

    updated, errors = [], []

    # ---------------- MAIN LOOP ----------------

    for idx, row in enumerate(data):
        try:
            raw_file_no = (
                row.get("File_Number")
                or row.get("FileNumber")
                or row.get("file_number")
            )
            file_no = normalize_file_number(raw_file_no)

            if not file_no:
                continue

            # -------- FIND OR CREATE DOC --------

            is_new = False

            if frappe.db.exists("Client Details", file_no):
                doc = frappe.get_doc("Client Details", file_no)
            else:
                names = frappe.get_all(
                    "Client Details",
                    filters={"file_number": file_no},
                    pluck="name",
                )
                if names:
                    doc = frappe.get_doc("Client Details", names[0])
                else:
                    doc = frappe.new_doc("Client Details")
                    doc.file_number = file_no
                    is_new = True

            # -------- SAFE FIELD UPDATES --------

            safe_set(doc, "file_number", file_no)
            safe_set(doc, "first_name", last_value(row.get("First_Name")))
            safe_set(doc, "last_name_1", last_value(row.get("Last_Name")))
            safe_set(doc, "gender", last_value(row.get("Gender")))
            safe_set(doc, "nationality", last_value(row.get("Nationality")))
            safe_set(doc, "mobile_number", last_value(row.get("Mobile_Number")))
            safe_set(doc, "email", last_value(row.get("Email_ID")))

            safe_set(doc, "date_of_birth", last_value(row.get("Date_of_Birth")))
            safe_set(doc, "date_of_expiry", last_value(row.get("Date_of_Expiry")))
            safe_set(doc, "registration_date", last_value(row.get("Registration Date")))
            safe_set(
                doc,
                "date_of_arrival_in_malta",
                last_value(row.get("Date_of_Arrival_in_Malta")),
            )
            # ---------------- VULNERABILITY (ALL VALUES) ----------------

            vulnerabilities = split_multi(row.get("Vulnerability"))

            if vulnerabilities:
                safe_set(doc, "other_vg", ", ".join(vulnerabilities))
                doc.other_support = 1  # checkbox ON

            # ---------------- SPECIAL NEEDS (ALL VALUES) ----------------

            special_needs = split_multi(row.get("Special_Needs"))

            if special_needs:
                safe_set(
                    doc,
                    "need_of_specific_assistance",
                    ", ".join(special_needs),
                )

            # ---------------- COMMENTS (APPEND ALL VALUES) ----------------

            json_comments = split_multi(row.get("Comments"))

            if json_comments:
                existing = doc.comment_box or ""
                new_text = ", ".join(json_comments)

                full_text = existing + "\n" + new_text if existing else new_text

                COMMENT_MAX = get_max_length(doc.doctype, "comment_box")
                MORE_MAX = get_max_length(doc.doctype, "more_comments")

                # 1️⃣ Hard trim for comment_box
                comment_part = full_text[:COMMENT_MAX]
                remaining_part = full_text[COMMENT_MAX:]

                doc.comment_box = comment_part

                # 2️⃣ Save overflow safely
                if remaining_part:
                    doc.more_comments = (doc.more_comments or "") + remaining_part[:MORE_MAX]

            # ---------------- COURSE REQUIRED (ALL VALUES) ----------------

            json_courses = split_multi(row.get("Personalintegrationplan"))

            if json_courses and not doc.get("select_course_required"):
                doc.set("select_course_required", [])
                for course in json_courses:
                    doc.append("select_course_required", {
                        "course_name": course
                    })


            # -------- ISR / ISM DATE FIX --------

            isr_date = last_value(row.get("ISR_Slot_Date"))

            # Save only if DB field is empty (NO data loss)
            if client_meta.get_field("isr_slot_date"):
                safe_set(doc, "isr_slot_date", isr_date)

            if client_meta.get_field("ism_slot"):
                safe_set(doc, "ism_slot", isr_date)


            safe_set(doc, "isr_slot_time", last_value(row.get("ISR_Slot_Time")))
            # ---------------- ISM STATUS (ALWAYS UPDATE) ----------------
            isr_status = last_value(row.get("ISR_Status"))
            if isr_status:
                doc.isr_status = isr_status
            
            # ---------------- STATUS & STAGE (ALWAYS UPDATE) ----------------

            client_status = last_value(row.get("ClientStatus"))
            if client_status:
                doc.status = client_status   # overwrite allowed

            stage_id = last_value(row.get("StageId"))
            if stage_id:
                doc.assigned_course = stage_id  # overwrite allowed


            safe_set(
                doc,
                "integration_support",
                1
                if last_value(row.get("Integration_Support_required")).lower()
                == "yes"
                else 0,
            )

            safe_set(
                doc,
                "isr_officer_name",
                row.get("Integration_officer")
                or row.get("Integration_officer_name"),
            )

            # -------- HOUSE PARSING --------

            raw_house_name = (row.get("House_Name") or "").strip()
            raw_house_number = (row.get("House_Number") or "").strip()

            def has_digits(s):
                return bool(re.search(r"\d", s))

            final_house_name = raw_house_name
            final_house_number = raw_house_number

            if raw_house_name.isdigit():
                final_house_number = raw_house_name
                final_house_name = raw_house_number
            elif has_digits(raw_house_name) and "," in raw_house_name and not raw_house_number:
                left, right = [p.strip() for p in raw_house_name.split(",", 1)]
                final_house_number = left
                final_house_name = right

            safe_set(doc, "house_name", final_house_name)
            safe_set(doc, "house_number", final_house_number)

            safe_set(doc, "street_name", last_value(row.get("Street_Name")))
            safe_set(doc, "locality", last_value(row.get("Locality")))
            safe_set(doc, "post_code", last_value(row.get("Post_Code")))
            safe_set(
                doc,
                "correspondence_address",
                last_value(row.get("Correspondence_Address")),
            )

            # ---------------- DAY AVAILABILITY ----------------

            json_days = split_multi(row.get("DayAvailability"))

            if json_days and not doc.get("select_preferred_day_time"):
                doc.set("select_preferred_day_time", [])
                for d in json_days:
                    doc.append("select_preferred_day_time", {
                        "day": d
                    })

            # ---------------- TIME AVAILABILITY ----------------

            json_times = split_multi(row.get("TimeAvailability"))

            if json_times and not doc.get("availability_for_attend_program"):
                doc.set("availability_for_attend_program", [])
                for t in json_times:
                    doc.append("availability_for_attend_program", {
                        "available_time": t
                    })
            # ---------------- LOCATION ----------------

            json_locations = split_multi(row.get("Location"))

            if json_locations and not doc.get("preferred_location"):
                doc.set("preferred_location", [])
                for loc in json_locations:
                    doc.append("preferred_location", {
                        "location": loc
                    })
       
        
        
        
        

            # -------- LANGUAGE FLUENCY (REBUILD ONLY IF EMPTY) --------
            # ---------------- LANGUAGE FLUENCY (AUTHORITATIVE FROM JSON) ----------------

            json_languages = split_multi(row.get("Language_Language_Fluency"))
            language_ids = split_multi(row.get("ID_Language_Fluency"))
            readings = split_multi(row.get("Reading_Language_Fluency"))
            speakings = split_multi(row.get("Speaking_Language_Fluency"))
            understandings = split_multi(row.get("Understanding_Language_Fluency"))
            writings = split_multi(row.get("Writing_Language_Fluency"))

            if json_languages:
                # JSON is authoritative → rebuild table
                doc.set("language_fluency", [])

                max_len = max(
                    len(json_languages),
                    len(language_ids),
                    len(readings),
                    len(speakings),
                    len(understandings),
                    len(writings),
                )

                for i in range(max_len):
                    doc.append("language_fluency", {
                        "language": json_languages[i] if i < len(json_languages) else "",
                        "language_id": language_ids[i] if i < len(language_ids) else "",
                        "reading": readings[i] if i < len(readings) else "",
                        "speaking": speakings[i] if i < len(speakings) else "",
                        "understanding": understandings[i] if i < len(understandings) else "",
                        "writing": writings[i] if i < len(writings) else "",
                    })




            # -------- INSERT / UPDATE --------

            doc.flags.ignore_permissions = True
            doc.flags.ignore_mandatory = True

            if is_new or getattr(doc, "__islocal", 0):
                doc.db_insert()
            else:
                doc.save()

            frappe.db.commit()
            updated.append(file_no)

        except Exception:
            frappe.db.rollback()
            errors.append(f"{file_no}: {traceback.format_exc()}")
            frappe.log_error(traceback.format_exc(), f"{DEBUG_TITLE} - ROW ERROR")

    # ---------------- SUMMARY ----------------

    frappe.log_error(
        f"UPDATED={len(updated)}, ERRORS={len(errors)}",
        f"{DEBUG_TITLE} - SUMMARY",
    )

    return {
        "status": "success",
        "updated_count": len(updated),
        "error_count": len(errors),
        "errors": errors[:20],
    }


import frappe
import json

def update_institute_registration_from_json():
    file_path = (
        "/home/frappe-user/ibelong-frappe/apps/"
        "ibelong_system/ibelong_system/"
        "institution_reg_data.json"
    )

    with open(file_path, "r") as f:
        data = json.load(f)

    updated = 0
    skipped = 0

    for row in data:
        enrollment_no = row.get("Enrollment Number")
        reg_date = row.get("Institute Registered Date")
        reg_flag = row.get("Institute Registered")

        if not enrollment_no:
            skipped += 1
            continue

        if not frappe.db.exists("Client Progression Details", enrollment_no):
            print(f"❌ Not found: {enrollment_no}")
            skipped += 1
            continue

        # Prepare values
        values = {
            "institute_registered": int(reg_flag) if reg_flag is not None else 0,
            "institute_registered_date": (
                frappe.utils.getdate(reg_date) if reg_date else None
            )
        }

        # ✅ Direct DB update (no validation, no link checks)
        frappe.db.set_value(
            "Client Progression Details",
            enrollment_no,
            values,
            update_modified=False
        )

        updated += 1

    frappe.db.commit()

    print("✅ Update completed successfully")
    print(f"   Updated: {updated}")
    print(f"   Skipped: {skipped}")



import frappe
import time

@frappe.whitelist()
def fix_progression_file_numbers():
    """
    Safest possible scheduler job:
    - Uses get_doc() only
    - Updates ONE document at a time
    - Logs errors
    - Zero lock timeout risk
    """

    BATCH_SIZE = 5          # very small = very safe
    SLEEP = 0.1             # reduce DB pressure
    updated = 0
    failed = 0

    names = frappe.get_all(
        "Client Progression Details",
        filters={},
        fields=["name"],
        limit=BATCH_SIZE
    )

    for row in names:
        docname = row.name
        clean_file = docname.split("_")[0]

        try:
            doc = frappe.get_doc("Client Progression Details", docname)

            # skip if already correct
            if doc.file_number == clean_file:
                continue

            doc.file_number = clean_file
            doc.save(ignore_permissions=True)
            frappe.db.commit()

            updated += 1

        except Exception:
            failed += 1
            frappe.log_error(
                title="Fix Progression File Number Failed",
                message=frappe.get_traceback()
            )

        time.sleep(SLEEP)

    return {
        "updated": updated,
        "failed": failed
    }

import frappe
import json

@frappe.whitelist()
def update_batch_details_from_json2():

    DEBUG_TITLE = "BatchDetailsMigration"

    def safe(row, key, default=""):
        try:
            val = row.get(key, default)
            return val if val is not None else default
        except Exception:
            return default

    try:
        file_path = (
            "/home/frappe-user/ibelong-frappe/apps/"
            "ibelong_system/ibelong_system/"
            "Batch_Details_Full_Data_23_12_2025.json"
        )

        # 1️⃣ LOAD JSON
        with open(file_path, "r") as f:
            client_data = json.load(f)

        if not isinstance(client_data, list) or not client_data:
            return "❌ JSON empty or invalid"

        # 2️⃣ UNIQUE BATCHES
        batch_names = list({
            safe(row, "Batch")
            for row in client_data
            if safe(row, "Batch")
        })

        results = []

        for batch_name in batch_names:

            is_new = False

            # 3️⃣ GET / CREATE BATCH
            try:
                batch_doc = frappe.get_doc("Batch Details", batch_name)
            except frappe.DoesNotExistError:
                batch_doc = frappe.new_doc("Batch Details")
                batch_doc.name = batch_name
                batch_doc.select_batch = batch_name
                batch_doc.insert(ignore_permissions=True)
                is_new = True

            # 4️⃣ METADATA FROM FIRST ROW
            first_row = next(
                (r for r in client_data if safe(r, "Batch") == batch_name),
                None
            )

            if first_row:
                # Cohort
                cohort_name = safe(first_row, "Cohort_Name")
                if cohort_name and batch_doc.meta.has_field("cohort"):
                    batch_doc.set("cohort", cohort_name)

                # Course Name
                course_name = safe(first_row, "Course_Name")
                if course_name and batch_doc.meta.has_field("course_name"):
                    batch_doc.set("course_name", course_name)

                assessment = safe(first_row, "AssessmentId").strip().lower()
                institute = safe(first_row, "Institute")

                # ✅ PASS + SERVICE PROVIDER
                if assessment == "pass":
                    if batch_doc.meta.has_field("pass"):
                        batch_doc.set("pass", 1)
                    if institute and batch_doc.meta.has_field("service_provider"):
                        batch_doc.set("service_provider", institute)
                else:
                    if batch_doc.meta.has_field("pass"):
                        batch_doc.set("pass", 0)

            # 5️⃣ CLEAR CHILD TABLE
            batch_doc.client_attendance_child = []

            rows = [
                r for r in client_data
                if safe(r, "Batch") == batch_name
            ]

            inserted = 0
            skipped = 0

            # 6️⃣ CHILD ROWS
            for idx, row in enumerate(rows, start=1):
                try:
                    file_number = safe(row, "File_Number").replace("\\/", "/")

                    batch_doc.append("client_attendance_child", {
                        "no": idx,
                        "first_name": safe(row, "First_Name"),
                        "last_name": safe(row, "Last_Name"),
                        "file_number": file_number,
                        "email": safe(row, "Email_ID"),
                        "pass": 1 if safe(row, "AssessmentId").lower() == "pass" else 0
                    })

                    inserted += 1

                except Exception:
                    skipped += 1
                    frappe.log_error(
                        title=f"{DEBUG_TITLE} - Row Error",
                        message=frappe.get_traceback()
                    )

            # 7️⃣ SAVE
            batch_doc.save(ignore_permissions=True)
            frappe.db.commit()

            action = "Created" if is_new else "Updated"
            results.append(
                f"{action} Batch '{batch_name}' → {inserted} rows (skipped {skipped})"
            )

        frappe.log_error(
            title=f"{DEBUG_TITLE} - Completed",
            message="\n".join(results)
        )

        return results

    except Exception:
        frappe.log_error(
            title=f"{DEBUG_TITLE} - Fatal Error",
            message=frappe.get_traceback()
        )
        return "❌ Fatal error"


import frappe
import traceback
from collections import defaultdict

@frappe.whitelist()
def update_batch_details_from_client_progression():
    """
    Build Batch Details from Client Progression Details
    (NO JSON)

    Grouping logic:
    - Client Progression Details.approved_by_sp == Batch Details.name

    Child table populated:
    - client_attendance_child
    """

    DEBUG_TITLE = "BatchDetailsFromClientProgression"

    try:
        # 1️⃣ Fetch Client Progression records
        clients = frappe.get_all(
            "Client Progression Details",
            filters={
                "approved_by_sp": ["is", "set"],
                "file_number": ["is", "set"],
            },
            fields=[
                "name",
                "file_number",
                "first_name",
                "last_name_1",
                "email",
                "approved_by_sp",   # Batch name
                "cohort",
            ],
        )

        if not clients:
            return "No Client Progression records found"

        # 2️⃣ Group clients by Batch
        batches = defaultdict(list)
        for c in clients:
            batches[c.approved_by_sp].append(c)

        results = []

        # 3️⃣ Process each Batch
        for batch_name, batch_clients in batches.items():

            is_new = False

            # Fetch or create Batch Details
            try:
                batch_doc = frappe.get_doc("Batch Details", batch_name)
            except frappe.DoesNotExistError:
                batch_doc = frappe.new_doc("Batch Details")
                batch_doc.name = batch_name
                batch_doc.select_batch = batch_name
                batch_doc.insert(ignore_permissions=True)
                is_new = True

            # Clear old child rows
            batch_doc.client_attendance_child = []

            inserted = 0
            skipped = 0

            # 4️⃣ Insert child rows
            for idx, c in enumerate(batch_clients, start=1):
                try:
                    batch_doc.append("client_attendance_child", {
                        "no": idx,
                        "first_name": c.first_name,
                        "last_name": c.last_name_1,
                        "file_number": c.file_number,
                        "email": c.email,
                        "cohort": c.cohort,
                        "pass": 0,
                    })
                    inserted += 1

                except Exception:
                    skipped += 1
                    frappe.log_error(
                        title=f"{DEBUG_TITLE} - Child Row Error",
                        message=f"""
Batch: {batch_name}
Client: {c.name}
File: {c.file_number}

{frappe.get_traceback()}
"""
                    )

            # 5️⃣ Save batch
            batch_doc.save(ignore_permissions=True)
            frappe.db.commit()

            action = "Created" if is_new else "Updated"
            results.append(
                f"{action} Batch {batch_name}: {inserted} added, {skipped} skipped"
            )

        frappe.log_error(
            title=f"{DEBUG_TITLE} - Completed",
            message="\n".join(results)
        )

        return results

    except Exception:
        frappe.log_error(
            title=f"{DEBUG_TITLE} - Fatal Error",
            message=frappe.get_traceback()
        )
        return "Fatal error occurred. Check Error Log."

def live_test():
    frappe.log_error("Hi live testing working")
    return

import json
import os
import frappe


@frappe.whitelist()
def update_batch_cohort_from_json_bg():
    """
    Background job:
    - Reads Batch_Cohort JSON
    - Uses Enrollment Number as doc.name
    - Updates cohort field
    """

    FILE_PATH = (
        "/home/frappe-user/ibelong-frappe/apps/"
        "ibelong_system/ibelong_system/Progresssion_cohort.json"
    )

    TITLE = "BATCH_COHORT_BG_JOB"

    try:
        if not os.path.exists(FILE_PATH):
            frappe.log_error(
                title=TITLE,
                message=f"File not found: {FILE_PATH}"
            )
            return

        with open(FILE_PATH, "r") as f:
            rows = json.load(f)

        updated = 0
        missing = 0
        errors = 0

        for row in rows:
            try:
                enrollment_no = (row.get("Enrollment Number") or "").strip()
                cohort = (row.get("Cohort") or "").strip()

                if not enrollment_no or not cohort:
                    continue

                if not frappe.db.exists("Client Progression Details", enrollment_no):
                    missing += 1
                    continue

                # ⚡ FAST UPDATE (no validation)
                frappe.db.set_value(
                    "Client Progression Details",
                    enrollment_no,
                    "cohort",
                    cohort
                )

                updated += 1

            except Exception:
                errors += 1
                frappe.log_error(
                    title=f"{TITLE} - ROW ERROR",
                    message=frappe.get_traceback()
                )

        frappe.db.commit()

        frappe.log_error(
            title=TITLE,
            message=(
                f"Completed\n"
                f"Updated: {updated}\n"
                f"Missing: {missing}\n"
                f"Errors: {errors}"
            )
        )

    except Exception:
        frappe.log_error(
            title=f"{TITLE} - FATAL",
            message=frappe.get_traceback()
        )



@frappe.whitelist()
def update_batch_cohort_from_json():
    """
    Update cohort name/number in Batch Details
    based on Batch (doc.name) + Course_Name match
    """

    DEBUG_TITLE = "BATCH_COHORT_UPDATE"

    file_path = (
        "/home/frappe-user/ibelong-frappe/apps/ibelong_system/"
        "ibelong_system/Batch_Cohort_19_12_2.json"
    )

    try:
        # 1️⃣ Load JSON
        with open(file_path, "r") as f:
            data = json.load(f)

        if not data:
            return "JSON file is empty"

        updated = 0
        skipped = 0
        results = []

        # 2️⃣ Process each mapping
        for row in data:
            batch = (row.get("Batch") or "").strip()
            course = (row.get("Course_Name") or "").strip()
            cohort = (row.get("Cohort_Name") or "").strip()

            if not batch or not course or not cohort:
                skipped += 1
                continue

            try:
                # 3️⃣ Fetch Batch Details by name
                doc = frappe.get_doc("Batch Details", batch)

                # 4️⃣ Validate course match
                if (doc.course_name or "").strip() != course:
                    skipped += 1
                    frappe.log_error(
                        title=f"{DEBUG_TITLE} - Course Mismatch",
                        message=(
                            f"Batch: {batch}\n"
                            f"Expected course: {course}\n"
                            f"Found course: {doc.course_name}"
                        )
                    )
                    continue

                # 5️⃣ Update cohort field
                # 🔁 Change fieldname if required (cohort_number / cohort_name)
                doc.cohorts = cohort

                doc.save(ignore_permissions=True)
                updated += 1

            except frappe.DoesNotExistError:
                skipped += 1
                frappe.log_error(
                    title=f"{DEBUG_TITLE} - Batch Not Found",
                    message=f"Batch Details not found: {batch}"
                )

            except Exception:
                skipped += 1
                frappe.log_error(
                    title=f"{DEBUG_TITLE} - Update Error",
                    message=f"Batch: {batch}\n{frappe.get_traceback()}"
                )

        frappe.db.commit()

        summary = (
            f"Batch Cohort Update Completed\n"
            f"Updated: {updated}\n"
            f"Skipped: {skipped}"
        )

        frappe.log_error(title=f"{DEBUG_TITLE} - DONE", message=summary)
        return summary

    except Exception:
        frappe.log_error(
            title=f"{DEBUG_TITLE} - FATAL",
            message=frappe.get_traceback()
        )
        return "Fatal error occurred. Check Error Log."


import frappe
import json
import traceback

@frappe.whitelist()
def repair_language_fluency_from_json():
    DEBUG_TITLE = "LANGUAGE_FLUENCY_REPAIR"
    file_path = "/home/frappe-user/ibelong-frappe/apps/ibelong_system/ibelong_system/newClient_Details_Full_data_06_12_2024.json"

    def split_multi(v):
        if not v:
            return []
        return [x.strip() for x in str(v).split(",") if x.strip()]

    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        frappe.log_error(message=f"JSON loaded, rows={len(data)}", title=DEBUG_TITLE)
    except Exception:
        frappe.log_error(traceback.format_exc(), f"{DEBUG_TITLE}-JSON-ERROR")
        return

    for row in data:
        try:
            file_no = row.get("File_Number")
            if not file_no:
                continue

            parent = frappe.db.get_value("Client Details", {"file_number": file_no}, "name")
            if not parent:
                continue

            languages = split_multi(row.get("Language_Language_Fluency"))
            if not languages:
                continue

            readings = split_multi(row.get("Reading_Language_Fluency"))
            speakings = split_multi(row.get("Speaking_Language_Fluency"))
            understandings = split_multi(row.get("Understanding_Language_Fluency"))
            writings = split_multi(row.get("Writing_Language_Fluency"))

            # 🔥 fallback: single proficiency → apply to all languages
            def pick(arr, idx):
                if len(arr) == 1:
                    return arr[0]
                if idx < len(arr):
                    return arr[idx]
                return ""

            existing_rows = frappe.db.sql(
                """
                SELECT name, language, reading, speaking, understanding, writing
                FROM `tabLanguage Proficiency`
                WHERE parent=%s AND parenttype='Client Details'
                """,
                parent,
                as_dict=True
            )

            existing = {r.language.lower(): r for r in existing_rows if r.language}

            total_langs = len(languages)

            def pick(arr, idx, total_langs):
                if len(arr) == total_langs and idx < len(arr):
                    return arr[idx]
                if len(arr) == 1 and idx == 0:
                    return arr[0]
                return ""

            for i, lang in enumerate(languages):
                key = lang.lower()

                payload = {
                    "reading": pick(readings, i, total_langs),
                    "speaking": pick(speakings, i, total_langs),
                    "understanding": pick(understandings, i, total_langs),
                    "writing": pick(writings, i, total_langs),
                }

                if key in existing:
                    for f, v in payload.items():
                        if v and not existing[key][f]:
                            frappe.db.set_value(
                                "Language Proficiency",
                                existing[key]["name"],
                                f,
                                v,
                                update_modified=False
                            )
                else:
                    doc = frappe.new_doc("Language Proficiency")
                    doc.parent = parent
                    doc.parenttype = "Client Details"
                    doc.parentfield = "language_fluency"
                    doc.language = lang
                    doc.update(payload)
                    doc.flags.ignore_permissions = True
                    doc.insert()


            frappe.db.commit()

        except Exception:
            frappe.db.rollback()
            frappe.log_error(traceback.format_exc(), f"LANG-ERROR {file_no}")


import frappe
import json
import traceback

@frappe.whitelist(allow_guest=False)
def update_client_details_from_grouped_json():
    """
    Reads grouped JSON (one record per File_Number) and updates Client Details.
    - Existing records: updated via .save()
    - New records: inserted via .db_insert() to SKIP after_insert hooks (e.g. email scripts)
    """
    DEBUG_TITLE = "ClientDetailsMigrationV22"

    # file_path = "/home/frappe-user/ibelog-frappe/apps/ibelong_system/ibelong_system/newClient_Details_Full_data_06_12_2024.json"
    file_path = "/home/frappe-user/ibelong-frappe/apps/ibelong_system/ibelong_system/newClient_Details_Full_data_06_12_2024.json"

    # START
    frappe.log_error(
        message=f"ENTERED function. file_path={file_path}",
        title=f"{DEBUG_TITLE} - START",
    )

    updated, not_found, errors = [], [], []

    def last_value(v: str) -> str:
        if v is None:
            return ""
        parts = [p.strip() for p in str(v).split(",") if p and str(p).strip()]
        return parts[-1] if parts else ""

    def split_multi(v: str):
        if not v:
            return []
        vals = [p.strip() for p in str(v).split(",") if p and str(p).strip()]
        seen = set()
        out = []
        for val in vals:
            if val not in seen:
                seen.add(val)
                out.append(val)
        return out

    # LOAD JSON
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except Exception:
        frappe.log_error(
            message="Error loading grouped JSON:\n" + traceback.format_exc(),
            title=f"{DEBUG_TITLE} - JSON LOAD ERROR",
        )
        return {"status": "error", "message": "Failed to load JSON, check error log."}

    try:
        data_len = len(data) if hasattr(data, "__len__") else "no-len"
        frappe.log_error(
            message=f"JSON loaded. type={type(data)}, len={data_len}",
            title=f"{DEBUG_TITLE} - JSON INFO",
        )
    except Exception:
        frappe.log_error(
            message="Error while inspecting loaded JSON:\n" + traceback.format_exc(),
            title=f"{DEBUG_TITLE} - JSON INFO ERROR",
        )

    # If data is dict, try unwrap
    if isinstance(data, dict):
        if "data" in data and isinstance(data["data"], list):
            frappe.log_error(
                message="Top level is dict, using data['data'] as list",
                title=f"{DEBUG_TITLE} - JSON UNWRAP",
            )
            data = data["data"]
        else:
            frappe.log_error(
                message="Top level JSON is dict, not list. Aborting.",
                title=f"{DEBUG_TITLE} - JSON STRUCT ERROR",
            )
            return {"status": "error", "message": "Top level JSON is dict, expected list"}

    # PRELOAD meta for existence checks
    try:
        client_meta = frappe.get_meta("Client Details")
    except Exception:
        client_meta = None

    # MAIN LOOP
    for idx, row in enumerate(data):
        if not isinstance(row, dict):
            frappe.log_error(
                message=f"Row {idx} is NOT dict: {repr(row)}",
                title=f"{DEBUG_TITLE} - ROW TYPE ERROR",
            )
            continue

        file_no = row.get("File_Number") or row.get("FileNumber") or row.get("file_number")
        if not file_no:
            frappe.log_error(
                message=f"Row {idx} missing 'File_Number'. Row={row}",
                title=f"{DEBUG_TITLE} - MISSING File_Number",
            )
            continue

        frappe.log_error(
            message=f"Processing row {idx}, File_Number={file_no}",
            title=f"{DEBUG_TITLE} - PROCESS ROW",
        )

        # -------- Find or create doc --------
        try:
            is_new_doc = False

            if frappe.db.exists("Client Details", file_no):
                # Case 1: doc name == File_Number
                doc = frappe.get_doc("Client Details", file_no)
                frappe.log_error(
                    message=f"Found existing Client Details by name for {file_no}",
                    title=f"{DEBUG_TITLE} - FOUND BY NAME",
                )
            else:
                # Case 2: search by file_number field
                names = frappe.get_all(
                    "Client Details",
                    filters={"file_number": file_no},
                    pluck="name",
                )

                if names:
                    doc = frappe.get_doc("Client Details", names[0])
                    frappe.log_error(
                        message=f"Found existing Client Details by file_number for {file_no}, docname={names[0]}",
                        title=f"{DEBUG_TITLE} - FOUND BY FIELD",
                    )
                else:
                    # Case 3: NOT FOUND → create NEW document (will use db_insert)
                    frappe.log_error(
                        message=f"No Client Details found for {file_no}, creating NEW document.",
                        title=f"{DEBUG_TITLE} - CREATE NEW",
                    )
                    doc = frappe.new_doc("Client Details")
                    doc.file_number = file_no
                    is_new_doc = True

        except Exception:
            errors.append(f"{file_no}: {traceback.format_exc()}")
            frappe.log_error(
                message=f"Error while locating/creating doc for {file_no}:\n{traceback.format_exc()}",
                title=f"{DEBUG_TITLE} - LOCATE ERROR",
            )
            frappe.db.rollback()
            continue

        # -------- Map fields & save/insert --------
        try:
            # basic fields (existing mapping - keep)
            doc.first_name = last_value(row.get("First_Name"))
            doc.file_number = file_no
            doc.last_name_1 = last_value(row.get("Last_Name"))
            doc.gender = last_value(row.get("Gender"))
            doc.nationality = last_value(row.get("Nationality"))
            doc.mobile_number = last_value(row.get("Mobile_Number"))

            # CHANGED: Email key now uses underscore
            doc.email = last_value(row.get("Email_ID"))

            doc.id_card_number = last_value(row.get("ID_Card_Number"))
            doc.id_card_number_2 = last_value(row.get("Alternative_ID_Card_Number"))

            doc.country_of_birth = last_value(row.get("Country_Of_Birth"))
            doc.registration_date = last_value(row.get("ApplicationDate"))
            doc.date_of_birth = last_value(row.get("Date_of_Birth"))
            doc.date_of_arrival_in_malta = last_value(row.get("Date_of_Arrival_in_Malta"))
            doc.integration_support = 1 if last_value(row.get("Integration_Support_required")).lower() == "yes" else 0

            # doc.house_name = last_value(row.get("House_Name"))
            doc.locality = last_value(row.get("Locality"))
            # doc.house_number = last_value(row.get("House_Number"))
            doc.street_name = last_value(row.get("Street_Name"))
            doc.post_code = last_value(row.get("Post_Code"))
            doc.correspondence_address = last_value(row.get("Correspondence_Address"))

            doc.national_status = last_value(row.get("National_Status"))
            doc.education_level = last_value(row.get("Education_Level"))
            doc.isr_officer_name = row.get("Integration_officer") or row.get("Integration_officer_name") or ""
            doc.ism_slot_time = row.get("ISR_Slot_Time") or row.get("ISR_Slot_Time") or "00:00"

            doc.status = last_value(row.get("ClientStatus"))
            doc.assigned_course = last_value(row.get("StageId"))
            # --------------------------------------------
            # SMART HOUSE NAME + HOUSE NUMBER PROCESSING (swap & comma-split rules)
            # --------------------------------------------

            raw_house_name = (row.get("House_Name") or "").strip()
            raw_house_number = (row.get("House_Number") or "").strip()

            import re

            def has_digits(s):
                return bool(re.search(r"\d", s)) if s else False

            def is_digits_only(s):
                return bool(s) and re.fullmatch(r"\s*\d+\s*", s) is not None

            final_house_name = raw_house_name
            final_house_number = raw_house_number

            try:
                # 1) If house_name is digits-only -> move it to house_number and put house_number into house_name (swap)
                if is_digits_only(raw_house_name):
                    final_house_number = raw_house_name
                    final_house_name = raw_house_number or ""
                # 2) If house_name contains digits and a comma, and house_number empty -> split at first comma
                elif has_digits(raw_house_name) and ("," in raw_house_name) and not raw_house_number:
                    left, right = [p.strip() for p in raw_house_name.split(",", 1)]
                    # prefer left as number if left contains any digits
                    if has_digits(left):
                        final_house_number = left
                        final_house_name = right or ""
                    else:
                        # fallback: keep original when left has no digits
                        final_house_name = raw_house_name
                        final_house_number = raw_house_number
                # 3) If house_name contains digits AND house_number is text-only -> swap (house_number <- house_name; house_name <- house_number)
                elif has_digits(raw_house_name) and raw_house_number and not has_digits(raw_house_number):
                    final_house_number = raw_house_name
                    final_house_name = raw_house_number
                # 4) If house_number contains digits -> trust house_number and keep house_name as-is (already default)
                elif has_digits(raw_house_number):
                    final_house_number = raw_house_number
                    final_house_name = raw_house_name
                # 5) else: keep originals (already assigned)
            except Exception:
                # On any unexpected error, fallback to originals but log the issue
                frappe.log_error(
                    message=f"HOUSE PARSE EXCEPTION for {file_no}: raw_house_name={raw_house_name!r}, raw_house_number={raw_house_number!r}\n{traceback.format_exc()}",
                    title=f"{DEBUG_TITLE} - HOUSE_PARSE_ERR",
                )

            # Final assignment
            try:
                if hasattr(doc, "house_name") or (client_meta and client_meta.get_field("house_name")):
                    doc.house_name = final_house_name
                if hasattr(doc, "house_number") or (client_meta and client_meta.get_field("house_number")):
                    doc.house_number = final_house_number
            except Exception:
                frappe.log_error(
                    message=f"Error assigning house fields for {file_no}: {traceback.format_exc()}",
                    title=f"{DEBUG_TITLE} - HOUSE_ASSIGN_ERR",
                )

            frappe.log_error(
                message=(
                    f"SMART HOUSE PARSE: raw_house_name={raw_house_name!r} "
                    f"raw_house_number={raw_house_number!r} -> "
                    f"final_house_name={final_house_name!r} final_house_number={final_house_number!r}"
                ),
                title=f"{DEBUG_TITLE} - HOUSE PARSE",
            )
            

            # Accept ClientId from JSON and set on common field names if present on DocType
            client_id_value = last_value(row.get("ClientId") or row.get("Client_ID") or row.get("client_id"))
            if client_id_value:
                # try several common field names; set if attribute exists on doc or on meta
                for attr in ("client_id", "clientid", "client"):
                    try:
                        # only set attribute if field exists on DocType or doc already has attribute
                        if hasattr(doc, attr) or (client_meta and client_meta.get_field(attr)):
                            setattr(doc, attr, client_id_value)
                    except Exception:
                        # ignore errors setting optional fields
                        pass

            # ------------- LANGUAGE FLUENCY (child table) -------------
            # JSON keys changed to use underscores:
            #   ID_Language_Fluency
            #   Language_Language_Fluency
            #   Reading_Language_Fluency
            #   Speaking_Language_Fluency
            #   Understanding_Language_Fluency (or "Understanding_Language Fluency")
            #   Writing_Language_Fluency

            # ------------- LANGUAGE FLUENCY (child table) -------------
            # Handle possibly multiple languages and matching proficiency columns.
            # Accept different key names and be tolerant of missing data.

            # best-effort sources for language + id
            raw_language = row.get("Language_Language_Fluency") or row.get("Language") or ""
            raw_language_ids = row.get("ID_Language_Fluency") or row.get("ID_Language Fluency") or ""

            # proficiency columns (may be comma-separated lists that correspond by position)
            raw_reading = row.get("Reading_Language_Fluency") or row.get("Reading") or ""
            raw_speaking = row.get("Speaking_Language_Fluency") or row.get("Speaking") or ""
            raw_understanding = (
                row.get("Understanding_Language_Fluency")
                or row.get("Understanding_Language Fluency")
                or row.get("Understanding")
                or ""
            )
            raw_writing = row.get("Writing_Language_Fluency") or row.get("Writing") or ""

            # split into lists using your existing helper (preserves order, removes duplicates)
            languages = split_multi(raw_language)
            language_ids = split_multi(raw_language_ids)
            readings = split_multi(raw_reading)
            speakings = split_multi(raw_speaking)
            understandings = split_multi(raw_understanding)
            writings = split_multi(raw_writing)

            frappe.log_error(
                message=(
                    f"{file_no} - LANG PARSE: languages={languages}, ids={language_ids}, "
                    f"R={readings}, S={speakings}, U={understandings}, W={writings}"
                ),
                title=f"{DEBUG_TITLE} - LANG PARSE",
            )

            # clear existing rows and re-add fresh
            doc.set("language_fluency", [])

            # If there are no languages but some proficiencies exist, attempt to create a single row
            if not languages and (readings or speakings or understandings or writings or language_ids):
                # create single "unknown" language row with available proficiencies
                doc.append("language_fluency", {
                    "language_id": language_ids[0] if language_ids else "",
                    "language": "",
                    "reading": readings[0] if readings else "",
                    "speaking": speakings[0] if speakings else "",
                    "understanding": understandings[0] if understandings else "",
                    "writing": writings[0] if writings else "",
                })
            else:
                # For N languages, create up to max_len rows aligning proficiency by index
                max_len = max(len(languages), len(language_ids), len(readings), len(speakings), len(understandings), len(writings))
                for i in range(max_len):
                    lang = languages[i] if i < len(languages) else ""
                    lid = language_ids[i] if i < len(language_ids) else ""
                    rd = readings[i] if i < len(readings) else ""
                    sp = speakings[i] if i < len(speakings) else ""
                    un = understandings[i] if i < len(understandings) else ""
                    wr = writings[i] if i < len(writings) else ""

                    # skip completely empty rows
                    if not (lang or lid or rd or sp or un or wr):
                        continue

                    doc.append("language_fluency", {
                        "language_id": lid,
                        "language": lang,
                        "reading": rd,
                        "speaking": sp,
                        "understanding": un,
                        "writing": wr,
                    })


            # ------------- DAY AVAILABILITY (child table) -------------
            raw_days = row.get("DayAvailability")
            days = split_multi(raw_days)

            frappe.log_error(
                message=f"{file_no} - DayAvailability raw={raw_days} -> {days}",
                title=f"{DEBUG_TITLE} - DAY PARSE",
            )

            doc.set("select_preferred_day_time", [])
            for d in days:
                doc.append("select_preferred_day_time", {"day": d})

            # ------------- TIME AVAILABILITY (child table) -------------
            raw_times = row.get("TimeAvailability")
            times = split_multi(raw_times)

            frappe.log_error(
                message=f"{file_no} - TimeAvailability raw={raw_times} -> {times}",
                title=f"{DEBUG_TITLE} - TIME PARSE",
            )

            doc.set("availability_for_attend_program", [])
            for t in times:
                doc.append("availability_for_attend_program", {"available_time": t})

            # ------------- LOCATION (child table / multiselect) -------------
            raw_locations = row.get("Location")
            locations = split_multi(raw_locations)

            frappe.log_error(
                message=f"{file_no} - Location raw={raw_locations} -> {locations}",
                title=f"{DEBUG_TITLE} - LOC PARSE",
            )

            doc.set("preferred_location", [])
            for loc in locations:
                doc.append("preferred_location", {"location": loc})

            # -------- Map additional fields explicitly present in sample JSON --------
            # safe explicit settings for fields present in your sample
            doc.date_of_expiry = last_value(row.get("Date_of_Expiry"))
            doc.isr_status = last_value(row.get("ISR_Status") or row.get("ISR Status"))
            doc.isr_slot_date = last_value(row.get("ISR_Slot_Date"))
            doc.isr_slot_time = last_value(row.get("ISR_Slot_Time"))
            doc.if_yes_please_specify = last_value(row.get("If_yes_Please_Specify"))
            doc.need_of_specific_assistance = last_value(row.get("Need_of_specific_assistance"))
            doc.for_others_please_specify = last_value(row.get("For_others_please_specify"))
            doc.application_date = last_value(row.get("Registration_Date"))

            # -------- Generic: copy any remaining JSON keys into DocType fields if they exist --------
            handled_keys = {
                # keys handled above (case-insensitive normalized)
                "file_number", "first_name", "last_name", "last_name_1", "last_name_2",
                "gender", "nationality", "mobile_number", "email_id", "email",
                "id_card_number", "alternative_id_card_number", "country_of_birth",
                "registration_date", "date_of_birth", "date_of_arrival_in_malta",
                "integration_support_required", "house_name", "locality", "house_number",
                "street_name", "post_code", "correspondence_address", "national_status",
                "education_level", "integration_officer", "integration_officer_name",
                "isr_slot_time", "status", "clientstatus", "stageid", "clientid",
                "client_id", "language_language_fluency", "id_language_fluency",
                "reading_language_fluency", "speaking_language_fluency",
                "understanding_language_fluency", "writing_language_fluency",
                "dayavailability", "timeavailability", "location",
                "date_of_expiry", "isr_status", "isr_slot_date", "isr_slot_time",
                "if_yes_please_specify", "need_of_specific_assistance",
                "for_others_please_specify", "applicationdate"
            }

            # iterate JSON keys and set onto doc if normalized field exists on DocType and not already handled
            for k, v in row.items():
                norm = str(k).strip().lower().replace(" ", "_")
                if norm in handled_keys:
                    continue
                # skip file number variants already done
                if norm in ("file_number", "filenumber"):
                    continue
                if client_meta and client_meta.get_field(norm):
                    try:
                        # choose scalar last value if it's comma-separated
                        setattr(doc, norm, last_value(v))
                    except Exception:
                        # ignore failed sets
                        pass

            # -------- Insert / Update --------
            if is_new_doc or getattr(doc, "__islocal", 0):
                doc.flags.ignore_mandatory = True
                doc.db_insert()
                frappe.log_error(
                    message=f"db_insert() done for NEW Client Details, File_Number={file_no}",
                    title=f"{DEBUG_TITLE} - INSERT OK",
                )
            else:
                doc.save(ignore_permissions=True)
                frappe.log_error(
                    message=f"save() done for EXISTING Client Details, File_Number={file_no}",
                    title=f"{DEBUG_TITLE} - UPDATE OK",
                )

            frappe.db.commit()
            updated.append(file_no)

        except Exception:
            frappe.db.rollback()
            errors.append(f"{file_no}: {traceback.format_exc()}")
            frappe.log_error(
                message=f"Error updating {file_no}:\n{traceback.format_exc()}",
                title=f"{DEBUG_TITLE} - UPDATE ERROR",
            )

    # SUMMARY
    frappe.log_error(
        message=f"FINISHED. updated={len(updated)}, not_found={len(not_found)}, errors={len(errors)}",
        title=f"{DEBUG_TITLE} - SUMMARY",
    )

    return {
        "status": "success",
        "message": "Client Details update from grouped JSON completed",
        "updated_count": len(updated),
        "not_found": not_found,
        "error_count": len(errors),
        "errors": errors[:20],
    }

# import frappe
# import json
# import traceback

# @frappe.whitelist(allow_guest=False)
# def update_client_details_from_grouped_json():
#     """
#     Reads grouped JSON (one record per File_Number) and updates Client Details.
#     - Existing records: updated via .save()
#     - New records: inserted via .db_insert() to SKIP after_insert hooks (e.g. email scripts)
#     """
#     DEBUG_TITLE = "ClientDetailsMigrationV22"

#     file_path = "/home/frappe-user/ibelog-frappe/apps/ibelong_system/ibelong_system/Client_Details_Full_data_04_12_2024.json"

#     # START
#     frappe.log_error(
#         message=f"ENTERED function. file_path={file_path}",
#         title=f"{DEBUG_TITLE} - START",
#     )

#     updated, not_found, errors = [], [], []

#     def last_value(v: str) -> str:
#         if not v:
#             return ""
#         parts = [p.strip() for p in str(v).split(",") if p and str(p).strip()]
#         return parts[-1] if parts else ""

#     def split_multi(v: str):
#         if not v:
#             return []
#         vals = [p.strip() for p in str(v).split(",") if p and str(p).strip()]
#         seen = set()
#         out = []
#         for val in vals:
#             if val not in seen:
#                 seen.add(val)
#                 out.append(val)
#         return out

#     # LOAD JSON
#     try:
#         with open(file_path, "r") as f:
#             data = json.load(f)
#     except Exception:
#         frappe.log_error(
#             message="Error loading grouped JSON:\n" + traceback.format_exc(),
#             title=f"{DEBUG_TITLE} - JSON LOAD ERROR",
#         )
#         return {"status": "error", "message": "Failed to load JSON, check error log."}

#     try:
#         data_len = len(data) if hasattr(data, "__len__") else "no-len"
#         frappe.log_error(
#             message=f"JSON loaded. type={type(data)}, len={data_len}",
#             title=f"{DEBUG_TITLE} - JSON INFO",
#         )
#     except Exception:
#         frappe.log_error(
#             message="Error while inspecting loaded JSON:\n" + traceback.format_exc(),
#             title=f"{DEBUG_TITLE} - JSON INFO ERROR",
#         )

#     # If data is dict, try unwrap
#     if isinstance(data, dict):
#         if "data" in data and isinstance(data["data"], list):
#             frappe.log_error(
#                 message="Top level is dict, using data['data'] as list",
#                 title=f"{DEBUG_TITLE} - JSON UNWRAP",
#             )
#             data = data["data"]
#         else:
#             frappe.log_error(
#                 message="Top level JSON is dict, not list. Aborting.",
#                 title=f"{DEBUG_TITLE} - JSON STRUCT ERROR",
#             )
#             return {"status": "error", "message": "Top level JSON is dict, expected list"}

#     # MAIN LOOP
#     for idx, row in enumerate(data):
#         if not isinstance(row, dict):
#             frappe.log_error(
#                 message=f"Row {idx} is NOT dict: {repr(row)}",
#                 title=f"{DEBUG_TITLE} - ROW TYPE ERROR",
#             )
#             continue

#         file_no = row.get("File_Number")
#         if not file_no:
#             frappe.log_error(
#                 message=f"Row {idx} missing 'File_Number'. Row={row}",
#                 title=f"{DEBUG_TITLE} - MISSING File_Number",
#             )
#             continue

#         frappe.log_error(
#             message=f"Processing row {idx}, File_Number={file_no}",
#             title=f"{DEBUG_TITLE} - PROCESS ROW",
#         )

#         # -------- Find or create doc --------
#         try:
#             is_new_doc = False

#             if frappe.db.exists("Client Details", file_no):
#                 # Case 1: doc name == File_Number
#                 doc = frappe.get_doc("Client Details", file_no)
#                 frappe.log_error(
#                     message=f"Found existing Client Details by name for {file_no}",
#                     title=f"{DEBUG_TITLE} - FOUND BY NAME",
#                 )
#             else:
#                 # Case 2: search by file_number field
#                 names = frappe.get_all(
#                     "Client Details",
#                     filters={"file_number": file_no},
#                     pluck="name",
#                 )

#                 if names:
#                     doc = frappe.get_doc("Client Details", names[0])
#                     frappe.log_error(
#                         message=f"Found existing Client Details by file_number for {file_no}, docname={names[0]}",
#                         title=f"{DEBUG_TITLE} - FOUND BY FIELD",
#                     )
#                 else:
#                     # Case 3: NOT FOUND → create NEW document (will use db_insert)
#                     frappe.log_error(
#                         message=f"No Client Details found for {file_no}, creating NEW document.",
#                         title=f"{DEBUG_TITLE} - CREATE NEW",
#                     )
#                     doc = frappe.new_doc("Client Details")
#                     doc.file_number = file_no
#                     is_new_doc = True

#         except Exception:
#             errors.append(f"{file_no}: {traceback.format_exc()}")
#             frappe.log_error(
#                 message=f"Error while locating/creating doc for {file_no}:\n{traceback.format_exc()}",
#                 title=f"{DEBUG_TITLE} - LOCATE ERROR",
#             )
#             frappe.db.rollback()
#             continue

#         # -------- Map fields & save/insert --------
#         # -------- Map fields & save/insert --------
#         try:
#             # basic fields
#             doc.first_name = last_value(row.get("First_Name"))
#             doc.file_number = file_no
#             doc.last_name_1 = last_value(row.get("Last_Name"))
#             doc.gender = last_value(row.get("Gender"))
#             doc.nationality = last_value(row.get("Nationality"))
#             doc.mobile_number = last_value(row.get("Mobile_Number"))
#             doc.email = last_value(row.get("Email ID"))

#             doc.id_card_number = last_value(row.get("ID_Card_Number"))
#             doc.id_card_number_2 = last_value(row.get("Alternative_ID_Card_Number"))

#             doc.country_of_birth = last_value(row.get("Country_Of_Birth"))
#             doc.registration_date = last_value(row.get("Registration_Date"))
#             doc.date_of_birth = last_value(row.get("Date_of_Birth"))
#             doc.date_of_arrival_in_malta = last_value(row.get("Date_of_Arrival_in_Malta"))

#             doc.house_name = last_value(row.get("House_Name"))
#             doc.locality = last_value(row.get("Locality"))
#             doc.house_number = last_value(row.get("House_Number"))
#             doc.street_name = last_value(row.get("Street_Name"))
#             doc.post_code = last_value(row.get("Post_Code"))
#             doc.correspondence_address = last_value(row.get("Correspondence_Address"))

#             doc.national_status = last_value(row.get("National_Status"))
#             doc.education_level = last_value(row.get("Education_Level"))

#             # 🔁 adjust if your status / course fieldnames differ
#             doc.status = last_value(row.get("ClientStatus"))
#             doc.assigned_course = last_value(row.get("StageId"))

#             # ------------- LANGUAGE FLUENCY (child table) -------------
#             # IMPORTANT: check the child table fieldnames:
#             #   Parent field: "language_fluency"   (table field in Client Details)
#             #   Child doctype: open it and check actual fieldnames:
#             #       e.g. language_id, language, reading, speaking, understanding, writing

#             raw_language = row.get("Language (Language Fluency)")
#             language_id = last_value(row.get("ID (Language Fluency)"))

#             frappe.log_error(
#                 message=f"{file_no} - Language raw={raw_language}, ID={language_id}",
#                 title=f"{DEBUG_TITLE} - LANG RAW",
#             )

#             # clear existing rows and re-add fresh
#             doc.set("language_fluency", [])

#             if raw_language:
#                 doc.append(
#                     "language_fluency",
#                     {
#                         "language_id": language_id or "",
#                         "language": raw_language,
#                         "reading": row.get("Reading (Language Fluency)") or "",
#                         "speaking": row.get("Speaking (Language Fluency)") or "",
#                         "understanding": row.get("Understanding (Language Fluency)") or "",
#                         "writing": row.get("Writing (Language Fluency)") or "",
#                     },
#                 )

#             # ------------- DAY AVAILABILITY (child table) -------------

#             raw_days = row.get("DayAvailability")
#             days = split_multi(raw_days)

#             frappe.log_error(
#                 message=f"{file_no} - DayAvailability raw={raw_days} -> {days}",
#                 title=f"{DEBUG_TITLE} - DAY PARSE",
#             )

#             # Always reset the child table
#             doc.set("select_preferred_day_time", [])
#             for d in days:
#                 # 🔁 'day' must match the fieldname in your child doctype
#                 doc.append("select_preferred_day_time", {"day": d})

#             # ------------- TIME AVAILABILITY (child table) -------------

#             raw_times = row.get("TimeAvailability")
#             times = split_multi(raw_times)

#             frappe.log_error(
#                 message=f"{file_no} - TimeAvailability raw={raw_times} -> {times}",
#                 title=f"{DEBUG_TITLE} - TIME PARSE",
#             )

#             doc.set("availability_for_attend_program", [])
#             for t in times:
#                 # 🔁 'available_time' must match fieldname in child doctype
#                 doc.append("availability_for_attend_program", {"available_time": t})

#             # ------------- LOCATION (child table / multiselect) -------------

#             raw_locations = row.get("Location")
#             locations = split_multi(raw_locations)

#             frappe.log_error(
#                 message=f"{file_no} - Location raw={raw_locations} -> {locations}",
#                 title=f"{DEBUG_TITLE} - LOC PARSE",
#             )

#             doc.set("preferred_location", [])
#             for loc in locations:
#                 # 🔁 'location' must match fieldname in child doctype
#                 doc.append("preferred_location", {"location": loc})

#             # -------- Insert / Update --------
#             if is_new_doc or getattr(doc, "__islocal", 0):
#                 # NEW DOC → direct db_insert (no after_insert, no server scripts)
#                 doc.flags.ignore_mandatory = True
#                 doc.db_insert()
#                 frappe.log_error(
#                     message=f"db_insert() done for NEW Client Details, File_Number={file_no}",
#                     title=f"{DEBUG_TITLE} - INSERT OK",
#                 )
#             else:
#                 doc.save(ignore_permissions=True)
#                 frappe.log_error(
#                     message=f"save() done for EXISTING Client Details, File_Number={file_no}",
#                     title=f"{DEBUG_TITLE} - UPDATE OK",
#                 )

#             frappe.db.commit()
#             updated.append(file_no)

#         except Exception:
#             frappe.db.rollback()
#             errors.append(f"{file_no}: {traceback.format_exc()}")
#             frappe.log_error(
#                 message=f"Error updating {file_no}:\n{traceback.format_exc()}",
#                 title=f"{DEBUG_TITLE} - UPDATE ERROR",
#             )

#     # SUMMARY
#     frappe.log_error(
#         message=f"FINISHED. updated={len(updated)}, not_found={len(not_found)}, errors={len(errors)}",
#         title=f"{DEBUG_TITLE} - SUMMARY",
#     )

#     return {
#         "status": "success",
#         "message": "Client Details update from grouped JSON completed",
#         "updated_count": len(updated),
#         "not_found": not_found,
#         "error_count": len(errors),
#         "errors": errors[:20],
#     }


import frappe
import json
import frappe, json
import frappe, json





@frappe.whitelist(allow_guest=True)
def update_institute_registered_from_json():
    try:
        file_path = "/home/frappe-user/ibelog-frappe/apps/ibelong_system/ibelong_system/Updated National Status.json"

        with open(file_path, "r") as f:
            data = json.load(f)

        updated, skipped = [], []

        for record in data:
            try:
                file_no = record.get("File_Number")
                raw_value = record.get("National Status")

                if not file_no:
                    skipped.append({"error": "Missing File_Number", "data": record})
                    continue

                # Normalize boolean
                institute_registered = str(raw_value)

                # Check document existence
                if not frappe.db.exists("Client Details", file_no):
                    skipped.append({"file_no": file_no, "error": "Client not found"})
                    continue

                # Update both fields together
                frappe.db.set_value(
                    "Client Details",
                    file_no,
                    {
                        "national_status": institute_registered,
                    },
                    # update_modified=False
                )
                frappe.log_error(f"Updated {file_no}: national_status={institute_registered}")
                # frappe.logger().info(f"✅ Updated {file_no}: declarations_per_tender_document={institute_registered}, verify_otp=1")
                updated.append(file_no)

            except Exception as e:
                frappe.log_error(f"Error updating {file_no}: {str(e)}", "InstituteRegistered Update Error")
                skipped.append({"file_no": file_no, "error": str(e)})
                continue

        frappe.db.commit()

        return {
            "status": "Completed",
            "updated": updated,
            "skipped": skipped
        }

    except Exception as e:
        frappe.log_error(str(e), "InstituteRegistered JSON Processing Error")
        return {"status": "Failed", "error": str(e)}


@frappe.whitelist(allow_guest=True)
def update_client_details_from_json():
    """
    Updates Client Details records from JSON.
    Adds language entries only if not already present.
    Skips errored docs and continues processing all.
    """
    try:
        file_path = "/home/frappe-user/ibelog-frappe/apps/ibelong_system/ibelong_system/clinet_details29-102.json"

        with open(file_path, "r") as f:
            client_data = json.load(f)

        updated, skipped, failed = [], [], []

        for client in client_data:
            file_no = client.get("File_Number")

            # Skip if File_Number missing
            if not file_no:
                continue

            try:
                existing_docs = frappe.get_all("Client Details", filters={"file_number": file_no}, pluck="name")
                if not existing_docs:
                    frappe.log_error(f"No Client Details found for File_Number: {file_no}")
                    failed.append(file_no)
                    continue

                doc = frappe.get_doc("Client Details", existing_docs[0])

                # ✅ Update only required fields
                doc.email = client.get("Email ID") or ""
                doc.id_card_number = client.get("ID Card Number") or ""
                doc.id_card_number_2 = client.get("Alternative ID Card Number") or ""
                doc.country_of_birth = client.get("Country Of Birth") or ""
                doc.registration_date = client.get("Registration Date") or ""
                doc.post_code = client.get("Post Code") or ""
                doc.correspondence_address = client.get("Correspondence Address") or ""
                doc.ism_slot_time = client.get("ISM Slot Time") or ""
                doc.assigned_course = client.get("Stage") or ""
                doc.isr_officer_name = client.get("Integration officer") or ""
                doc.language_fluency_id = client.get("ID (Language Fluency)") or ""

                # ✅ Handle Language Fluency
                language = client.get("Language (Language Fluency)")
                if language:
                    # Collect existing languages
                    existing_languages = [
                        d.language.strip().lower()
                        for d in doc.get("language_fluency")
                        if getattr(d, "language", None)
                    ]

                    # Skip if already exists
                    if language.strip().lower() in existing_languages:
                        skipped.append(f"{file_no} - {language}")
                        frappe.log_error(f"Skipped: Language '{language}' already exists for {file_no}.")
                    else:
                        # Add new language entry
                        doc.append("language_fluency", {
                            "language_id": client.get("ID (Language Fluency)") or "",
                            "language": language,
                            "reading": client.get("Reading (Language Fluency)") or "",
                            "speaking": client.get("Speaking (Language Fluency)") or "",
                            "understanding": client.get("Understanding (Language Fluency)") or "",
                            "writing": client.get("Writing (Language Fluency)") or ""
                        })
                        updated.append(f"{file_no} - {language}")
                        frappe.log_error(f"Added: Language '{language}' for {file_no}.")

                # ✅ Save changes for this doc
                doc.save(ignore_permissions=True)
                frappe.db.commit()

            except Exception as single_doc_error:
                # If one doc fails, log error and move on
                frappe.db.rollback()
                failed.append(file_no)
                frappe.log_error(
                    title=f"Error Updating {file_no}",
                    message=f"Error: {str(single_doc_error)}"
                )
                continue  # move to next client

        # ✅ Return summary
        return {
            "status": "success",
            "message": f"Processed {len(client_data)} records | Updated: {len(updated)} | Skipped: {len(skipped)} | Failed: {len(failed)}",
            "updated": updated,
            "skipped": skipped,
            "failed": failed
        }

    except Exception as e:
        frappe.log_error(f"Error running update_client_details_from_json: {str(e)}")
        return {"status": "error", "message": str(e)}


import frappe
import json
from collections import defaultdict

@frappe.whitelist(allow_guest=False)
def update_client_available_days():
    try:
        # Path to your JSON file
        file_path = "/home/frappe-user/ibelog-frappe/apps/ibelong_system/ibelong_system/Client_Day2.json"

        # Load JSON data
        with open(file_path, "r") as f:
            client_data = json.load(f)

        # Group days by FileNo
        grouped_days = defaultdict(list)
        for entry in client_data:
            file_no = entry.get("FileNo")
            day_name = entry.get("DayAvailabilityName")
            if file_no and day_name:
                grouped_days[file_no].append(day_name)

        updated, not_found, errors = [], [], []

        # Iterate grouped records
        for file_no, days in grouped_days.items():
            try:
                # Check if client exists
                if not frappe.db.exists("Client Details", file_no):
                    not_found.append(file_no)
                    continue

                # Load client
                doc = frappe.get_doc("Client Details", file_no)

                # Clear existing rows
                doc.set("available_days_table", [])

                # Add each day to child table
                # frappe.log_error("data ->",doc)
                for day in days:
                    doc.append("select_preferred_day_time", {
                        "day": day
                    })
                frappe.log_error("done")

                # Save changes
                doc.save(ignore_permissions=True)
                frappe.db.commit()
                updated.append(file_no)

            except Exception as e:
                frappe.db.rollback()
                errors.append(f"{file_no}: {str(e)}")
                continue

        return {
            "message": "Available days update complete",
            "updated_count": len(updated),
            "not_found": not_found,
            "errors": errors
        }

    except Exception as e:
        frappe.log_error(f"Error in update_client_available_days: {str(e)}")
        return {"error": str(e)}

import frappe
import json

@frappe.whitelist(allow_guest=False)
def update_client_details_with_file_number():
    try:
        file_path = "/home/frappe-user/ibelog-frappe/apps/ibelong_system/ibelong_system/Client 27-10-2025.json"

        with open(file_path, "r") as f:
            client_data = json.load(f)

        updated, skipped, not_found, deleted, errors = [], [], [], [], []

        for entry in client_data:
            try:
                file_no = entry.get("File_Number")
                status = entry.get("ClientStatus")

                if not file_no:
                    continue

                # Find Client Details by file_number
                existing_docs = frappe.get_all("Client Details", filters={"file_number": file_no}, pluck="name")

                if not existing_docs:
                    not_found.append(file_no)
                    continue

                old_name = existing_docs[0]

                # Fetch the document safely
                try:
                    doc = frappe.get_doc("Client Details", old_name)
                except frappe.DoesNotExistError:
                    errors.append(f"Doc {old_name} not found while fetching")
                    continue

                # ✅ If already same name, just update and save
                if doc.name == file_no:
                    doc.application_status = status
                    doc.save(ignore_permissions=True)
                    frappe.db.commit()
                    skipped.append(file_no)
                    continue

                # ✅ If another record already exists with same name, delete it
                if frappe.db.exists("Client Details", file_no):
                    frappe.delete_doc("Client Details", file_no, ignore_permissions=True)
                    frappe.db.commit()
                    deleted.append(file_no)

                # ✅ Rename safely
                frappe.rename_doc("Client Details", old_name, file_no, force=True, merge=False)
                frappe.db.commit()

                # ✅ Re-fetch after rename and update
                try:
                    renamed_doc = frappe.get_doc("Client Details", file_no)
                    renamed_doc.application_status = status
                    renamed_doc.save(ignore_permissions=True)
                    frappe.db.commit()
                    updated.append(file_no)
                except frappe.DoesNotExistError:
                    errors.append(f"Renamed doc {file_no} not found after rename")
                    continue

            except Exception as inner_e:
                # Catch any error for this one document and skip it
                frappe.db.rollback()
                errors.append(f"{file_no}: {str(inner_e)}")
                continue

        # Final logs
        frappe.log_error(f"Renamed {len(updated)} docs: {updated}")
        frappe.log_error(f"Skipped (same name): {skipped}")
        frappe.log_error(f"Deleted duplicates: {deleted}")
        frappe.log_error(f"Not found: {not_found}")
        frappe.log_error(f"Errors: {errors}")

        return {
            "message": "Update completed (skipping errored docs)",
            "renamed_count": len(updated),
            "skipped_same_name": len(skipped),
            "deleted_duplicates": len(deleted),
            "not_found": not_found,
            "error_count": len(errors),
            "errors": errors,
        }

    except Exception as e:
        frappe.log_error(f"Error in update_client_details_with_file_number (outer): {str(e)}")
        return {"error": str(e)}


#12-12-25
import json
import re
import traceback
import frappe
from types import SimpleNamespace

# Assumes safe_get is available in the module. If not, uncomment the helper below:
def safe_get(d, key, default=""):
    try:
        return d.get(key, default) or default
    except Exception:
        return default

DEBUG_TITLE = "CLIENT_PROGRESSION_IMPORT"

def _bind_dummy_request():
    """
    Helper to temporarily bind a dummy request object to frappe.local.request.
    Returns the previous request object (or None). Caller must restore it.
    """
    prev_req = getattr(frappe.local, "request", None)
    # set a minimal request object with args attribute so server scripts can access .args safely
    frappe.local.request = SimpleNamespace(args={})
    return prev_req

def _restore_request(prev_req):
    """
    Restore previous frappe.local.request. If prev_req is None, remove the attribute.
    """
    if prev_req is None:
        # delete attribute if it was not present originally
        try:
            delattr(frappe.local, "request")
        except Exception:
            # fallback: set to None (some environments may not allow delattr)
            try:
                frappe.local.request = None
            except Exception:
                pass
    else:
        frappe.local.request = prev_req

def create_client_progression_info():
    """
    Improved importer for `Client Progression Details`.

    Main changes made:
    - Fixed house-name/house-number parsing (removed undefined `row`).
    - If a matching record already exists, update it (merge JSON fields) instead of skipping.
    - Per-document, per-field errors are collected and returned in the summary.
    - All assignments are defensive (wrapped in try/except) so a bad field won't break the whole run.
    - Added `errors_per_doc` structure to summarize field-level problems for each doc.
    - Temporarily binds a dummy `frappe.local.request` during insert/save to avoid RuntimeError
      when server scripts try to access `frappe.request.args` outside of an HTTP request.
    """

    try:
        file_path = "/home/frappe-user/ibelong-frappe/apps/ibelong_system/ibelong_system/newClient_Progression3.json"


        with open(file_path, "r") as f:
            client_data = json.load(f)

        created = []
        updated = []
        skipped = []
        errors_per_doc = {}  # file_no -> list of {field: error_message}

        for client in client_data:
            # Defensive normalisation
            for key in [
                "ClientId",
                "File_Number",
                "Course_Level",
                "CourseId",
                "Certificate_Number",
                "Service_Provider",
                "First_Name",
                "Last_Name",
                "Gender",
                "Date_of_Birth",
                "Nationality",
                "ID_Card_Number",
                "Country_Of_Birth",
                "Mobile_Number",
                "Email_ID",
                "House_Name",
                "House_Number",
                "Street_Name",
                "Locality",
                "Post_Code",
                "Correspondence_Address",
                "ClientStatus",
                "Selected_Course_Type",
                "Assigned_Batch",
                "Result",
                "Alternative_ID_Card_Number",
            ]:
                try:
                    client[key] = client.get(key, "") or ""
                except Exception as e:
                    # record the error but keep going
                    fname = client.get("File_Number") or client.get("ClientId") or "<unknown>"
                    errors_per_doc.setdefault(fname, []).append(
                        {f"normalise_{key}": str(e)}
                    )
                    client[key] = ""

            file_no = client.get("File_Number", "") or client.get("ClientId", "")
            course_id = client.get("CourseId", "")

            if not file_no:
                skipped.append({"reason": "Missing File_Number/ClientId", "client": client})
                continue

            enrollment_no = f"{file_no}_{course_id}" if course_id else file_no

            # Check existing doc (match on file_number + course)
            existing_name = frappe.db.get_value(
                "Client Progression Details",
                {
                    "file_number": file_no,
                    "which_courses_are_assigned_to_the_client": course_id,
                },
                "name",
            )

            # --- Date of birth: defensive trim ---
            dob_raw = client.get("Date_of_Birth", "")
            try:
                dob = dob_raw.split(" ")[0] if " " in dob_raw else dob_raw
            except Exception as e:
                errors_per_doc.setdefault(file_no, []).append({"Date_of_Birth": str(e)})
                dob = ""

            # Build doc data using safe per-field extraction
            doc_data = {
                "doctype": "Client Progression Details",
                "file_number": file_no,
                "enrolment_number": enrollment_no,

                # Course Information
                "course_level": client.get("Course_Level", ""),
                "result": client.get("Result", ""),
                "status": client.get("ClientStatus", ""),
                "which_courses_are_assigned_to_the_client": course_id,
                "approved_by_sp": client.get("Assigned_Batch", ""),
                "certificate_number": client.get("Certificate_Number", ""),
                # "class_location": "",
                "service_provider": client.get("Service_Provider", ""),

                # Personal Details
                "first_name": client.get("First_Name", ""),
                "last_name_1": client.get("Last_Name", ""),
                "gender": client.get("Gender", ""),
                "date_of_birth": dob,
                "nationality": client.get("Nationality", ""),
                "id_card_number": client.get("ID_Card_Number", ""),
                "passport_number": client.get("Alternative_ID_Card_Number", ""),
                "country_of_birth": client.get("Country_Of_Birth", ""),

                # Contact Details
                "mobile_number": client.get("Mobile_Number", ""),
                "email": client.get("Email_ID", ""),
                "street_name": client.get("Street_Name", ""),
                "locality": client.get("Locality", ""),
                "post_code": client.get("Post_Code", ""),
                "correspondence_address": client.get("Correspondence_Address", ""),

                # Static / default
                "selected_course_type": client.get("Selected_Course_Type", "") or "Free",
                "certificate_for_skip_maltese_course": "",
                "completed_course_certificates": "",
                "foundation": "",
                "certificate_of_completion": "",
            }

            # --------------------------------------------
            # SMART HOUSE NAME + HOUSE NUMBER PROCESSING (swap & comma-split rules)
            # --------------------------------------------
            raw_house_name = (client.get("House_Name") or "").strip()
            raw_house_number = (client.get("House_Number") or "").strip()

            def has_digits(s):
                return bool(re.search(r"\d", s)) if s else False

            def is_digits_only(s):
                return bool(s) and re.fullmatch(r"\s*\d+\s*", s) is not None

            final_house_name = raw_house_name
            final_house_number = raw_house_number

            try:
                # 1) If house_name is digits-only -> move it to house_number and put house_number into house_name (swap)
                if is_digits_only(raw_house_name):
                    final_house_number = raw_house_name
                    final_house_name = raw_house_number or ""
                # 2) If house_name contains digits and a comma, and house_number empty -> split at first comma
                elif has_digits(raw_house_name) and ("," in raw_house_name) and not raw_house_number:
                    left, right = [p.strip() for p in raw_house_name.split(",", 1)]
                    if has_digits(left):
                        final_house_number = left
                        final_house_name = right or ""
                    else:
                        final_house_name = raw_house_name
                        final_house_number = raw_house_number
                # 3) If house_name contains digits AND house_number is text-only -> swap
                elif has_digits(raw_house_name) and raw_house_number and not has_digits(raw_house_number):
                    final_house_number = raw_house_name
                    final_house_name = raw_house_number
                # 4) If house_number contains digits -> trust house_number and keep house_name as-is
                elif has_digits(raw_house_number):
                    final_house_number = raw_house_number
                    final_house_name = raw_house_name
                # else: keep originals

            except Exception as e:
                errors_per_doc.setdefault(file_no, []).append({"house_parse": str(e)})
                # fallback to originals (already set)

            # Put final house values into doc_data so they are saved/updated
            doc_data["house_name"] = final_house_name
            doc_data["house_number"] = final_house_number

            # LOG smart parse
            frappe.log_error(
                message=(
                    f"SMART HOUSE PARSE: raw_house_name={raw_house_name!r} raw_house_number={raw_house_number!r} -> "
                    f"final_house_name={final_house_name!r} final_house_number={final_house_number!r}"
                ),
                title=f"{DEBUG_TITLE} - HOUSE PARSE",
            )

            # Now either create or update the doc
            try:
                # Temporarily bind dummy request so server-scripts/hooks that expect frappe.request.args don't crash
                prev_req = None
                try:
                    prev_req = _bind_dummy_request()
                    if existing_name:
                        # Update existing doc - merge fields (overwrite with json values where present)
                        doc = frappe.get_doc("Client Progression Details", existing_name)
                        # For safety, set only keys that exist in doc fields (so we don't set arbitrary keys)
                        for k, v in doc_data.items():
                            # skip doctype and name
                            if k in ("doctype", "name"):
                                continue
                            try:
                                # assign only if field exists on the DocType or is an allowed custom field
                                setattr(doc, k, v)
                            except Exception as e:
                                errors_per_doc.setdefault(file_no, []).append({f"assign_{k}": str(e)})
                        # Avoid emails / notifications
                        doc.flags.ignore_mails = True
                        doc.save(ignore_permissions=True)
                        frappe.db.commit()
                        updated.append(f"{file_no}_{course_id}")
                        print(f"🔄 Updated: {file_no}_{course_id}")
                    else:
                        # Create new doc
                        doc = frappe.get_doc(doc_data)
                        doc.flags.ignore_mails = True
                        doc.insert(ignore_permissions=True, ignore_mandatory=True)
                        frappe.db.commit()
                        created.append(f"{file_no}_{course_id}")
                        print(f"✅ Created: {file_no}_{course_id}")
                finally:
                    # restore previous request object (or remove dummy)
                    _restore_request(prev_req)

            except Exception as insert_e:
                # Log and record the error. We'll include the exception message in the per-doc error list.
                frappe.log_error(
                    title=f"Error saving Client Progression for {file_no}",
                    message=traceback.format_exc(),
                )
                errors_per_doc.setdefault(file_no, []).append({"save_error": str(insert_e)})
                skipped.append({
                    "reason": str(insert_e),
                    "file_number": file_no,
                    "course_id": course_id,
                })

        # Final summary logging
        frappe.log_error(
            "Client Progression Info Import Summary",
            f"Created: {len(created)}, Updated: {len(updated)}, Skipped: {len(skipped)}",
        )

        return {
            "message": "Client Progression Info import completed",
            "created_count": len(created),
            "updated_count": len(updated),
            "skipped_count": len(skipped),
            "created": created[:50],
            "updated": updated[:50],
            "skipped": skipped[:50],
            "errors_per_doc": errors_per_doc,
        }

    except json.JSONDecodeError as e:
        frappe.log_error("JSON Decode Error", str(e))
        return {"error": f"Invalid JSON file at line {e.lineno}, column {e.colno}"}

    except Exception as e:
        frappe.log_error("Unexpected Error in create_client_progression_info", traceback.format_exc())
        return {"error": str(e)}




# added on 11-12-25

# import json
# import re
# import traceback
# import frappe

# # Assumes safe_get is available in the module. If not, uncomment the helper below:
# def safe_get(d, key, default=""):
#     try:
#         return d.get(key, default) or default
#     except Exception:
#         return default

# DEBUG_TITLE = "CLIENT_PROGRESSION_IMPORT"


# def create_client_progression_info():
#     """
#     Improved importer for `Client Progression Details`.

#     Main changes made:
#     - Fixed house-name/house-number parsing (removed undefined `row`).
#     - If a matching record already exists, update it (merge JSON fields) instead of skipping.
#     - Per-document, per-field errors are collected and returned in the summary.
#     - All assignments are defensive (wrapped in try/except) so a bad field won't break the whole run.
#     - Added `errors_per_doc` structure to summarize field-level problems for each doc.
#     """

#     try:
#         file_path = (
#             "/home/frappe-user/ibelog-frappe/apps/ibelong_system/ibelong_system/Client_Progression_full_data_11-12-25.json"
#         )

#         with open(file_path, "r") as f:
#             client_data = json.load(f)

#         created = []
#         updated = []
#         skipped = []
#         errors_per_doc = {}  # file_no -> list of {field: error_message}

#         for client in client_data:
#             # Defensive normalisation
#             for key in [
#                 "ClientId",
#                 "File_Number",
#                 "Course_Level",
#                 "CourseId",
#                 "Certificate_Number",
#                 "Service_Provider",
#                 "First_Name",
#                 "Last_Name",
#                 "Gender",
#                 "Date_of_Birth",
#                 "Nationality",
#                 "ID_Card_Number",
#                 "Country_Of_Birth",
#                 "Mobile_Number",
#                 "Email_ID",
#                 "House_Name",
#                 "House_Number",
#                 "Street_Name",
#                 "Locality",
#                 "Post_Code",
#                 "Correspondence_Address",
#                 "ClientStatus",
#                 "Selected_Course_Type",
#                 "Assigned_Batch",
#                 "Result",
#                 "Alternative_ID_Card_Number",
#             ]:
#                 try:
#                     client[key] = client.get(key, "") or ""
#                 except Exception as e:
#                     # record the error but keep going
#                     fname = client.get("File_Number") or client.get("ClientId") or "<unknown>"
#                     errors_per_doc.setdefault(fname, []).append(
#                         {f"normalise_{key}": str(e)}
#                     )
#                     client[key] = ""

#             file_no = client.get("File_Number", "") or client.get("ClientId", "")
#             course_id = client.get("CourseId", "")

#             if not file_no:
#                 skipped.append({"reason": "Missing File_Number/ClientId", "client": client})
#                 continue

#             enrollment_no = f"{file_no}_{course_id}" if course_id else file_no

#             # Check existing doc (match on file_number + course)
#             existing_name = frappe.db.get_value(
#                 "Client Progression Details",
#                 {
#                     "file_number": file_no,
#                     "which_courses_are_assigned_to_the_client": course_id,
#                 },
#                 "name",
#             )

#             # --- Date of birth: defensive trim ---
#             dob_raw = client.get("Date_of_Birth", "")
#             try:
#                 dob = dob_raw.split(" ")[0] if " " in dob_raw else dob_raw
#             except Exception as e:
#                 errors_per_doc.setdefault(file_no, []).append({"Date_of_Birth": str(e)})
#                 dob = ""

#             # Build doc data using safe per-field extraction
#             doc_data = {
#                 "doctype": "Client Progression Details",
#                 "file_number": file_no,
#                 "enrolment_number": enrollment_no,

#                 # Course Information
#                 "course_level": client.get("Course_Level", ""),
#                 "result": client.get("Result", ""),
#                 "status": client.get("ClientStatus", ""),
#                 "which_courses_are_assigned_to_the_client": course_id,
#                 "approved_by_sp": client.get("Assigned_Batch", ""),
#                 "certificate_no": client.get("Certificate_Number", ""),
#                 "class_location": "",
#                 "service_provider": client.get("Service_Provider", ""),

#                 # Personal Details
#                 "first_name": client.get("First_Name", ""),
#                 "last_name": client.get("Last_Name", ""),
#                 "gender": client.get("Gender", ""),
#                 "date_of_birth": dob,
#                 "nationality": client.get("Nationality", ""),
#                 "id_card_number": client.get("ID_Card_Number", ""),
#                 "passport_number": client.get("Alternative_ID_Card_Number", ""),
#                 "country_of_birth": client.get("Country_Of_Birth", ""),

#                 # Contact Details
#                 "mobile_number": client.get("Mobile_Number", ""),
#                 "email": client.get("Email_ID", ""),
#                 "street_name": client.get("Street_Name", ""),
#                 "locality": client.get("Locality", ""),
#                 "post_code": client.get("Post_Code", ""),
#                 "correspondence_address": client.get("Correspondence_Address", ""),

#                 # Static / default
#                 "selected_course_type": client.get("Selected_Course_Type", "") or "Free",
#                 "certificate_for_skip_maltese_course": "",
#                 "completed_course_certificates": "",
#                 "foundation": "",
#                 "certificate_of_completion": "",
#             }

#             # --------------------------------------------
#             # SMART HOUSE NAME + HOUSE NUMBER PROCESSING (swap & comma-split rules)
#             # --------------------------------------------
#             raw_house_name = (client.get("House_Name") or "").strip()
#             raw_house_number = (client.get("House_Number") or "").strip()

#             def has_digits(s):
#                 return bool(re.search(r"\d", s)) if s else False

#             def is_digits_only(s):
#                 return bool(s) and re.fullmatch(r"\s*\d+\s*", s) is not None

#             final_house_name = raw_house_name
#             final_house_number = raw_house_number

#             try:
#                 # 1) If house_name is digits-only -> move it to house_number and put house_number into house_name (swap)
#                 if is_digits_only(raw_house_name):
#                     final_house_number = raw_house_name
#                     final_house_name = raw_house_number or ""
#                 # 2) If house_name contains digits and a comma, and house_number empty -> split at first comma
#                 elif has_digits(raw_house_name) and ("," in raw_house_name) and not raw_house_number:
#                     left, right = [p.strip() for p in raw_house_name.split(",", 1)]
#                     if has_digits(left):
#                         final_house_number = left
#                         final_house_name = right or ""
#                     else:
#                         final_house_name = raw_house_name
#                         final_house_number = raw_house_number
#                 # 3) If house_name contains digits AND house_number is text-only -> swap
#                 elif has_digits(raw_house_name) and raw_house_number and not has_digits(raw_house_number):
#                     final_house_number = raw_house_name
#                     final_house_name = raw_house_number
#                 # 4) If house_number contains digits -> trust house_number and keep house_name as-is
#                 elif has_digits(raw_house_number):
#                     final_house_number = raw_house_number
#                     final_house_name = raw_house_name
#                 # else: keep originals

#             except Exception as e:
#                 errors_per_doc.setdefault(file_no, []).append({"house_parse": str(e)})
#                 # fallback to originals (already set)

#             # Put final house values into doc_data so they are saved/updated
#             doc_data["house_name"] = final_house_name
#             doc_data["house_number"] = final_house_number

#             # LOG smart parse
#             frappe.log_error(
#                 message=(
#                     f"SMART HOUSE PARSE: raw_house_name={raw_house_name!r} raw_house_number={raw_house_number!r} -> "
#                     f"final_house_name={final_house_name!r} final_house_number={final_house_number!r}"
#                 ),
#                 title=f"{DEBUG_TITLE} - HOUSE PARSE",
#             )

#             # Now either create or update the doc
#             try:
#                 if existing_name:
#                     # Update existing doc - merge fields (overwrite with json values where present)
#                     doc = frappe.get_doc("Client Progression Details", existing_name)
#                     # For safety, set only keys that exist in doc fields (so we don't set arbitrary keys)
#                     for k, v in doc_data.items():
#                         # skip doctype and name
#                         if k in ("doctype", "name"):
#                             continue
#                         try:
#                             # assign only if field exists on the DocType or is an allowed custom field
#                             # We try setting; if field not present, getattr will raise when saving -> catch below
#                             setattr(doc, k, v)
#                         except Exception as e:
#                             errors_per_doc.setdefault(file_no, []).append({f"assign_{k}": str(e)})
#                     # Avoid emails / notifications
#                     doc.flags.ignore_mails = True
#                     doc.save(ignore_permissions=True)
#                     frappe.db.commit()
#                     updated.append(f"{file_no}_{course_id}")
#                     print(f"🔄 Updated: {file_no}_{course_id}")
#                 else:
#                     # Create new doc
#                     doc = frappe.get_doc(doc_data)
#                     doc.flags.ignore_mails = True
#                     doc.insert(ignore_permissions=True, ignore_mandatory=True)
#                     frappe.db.commit()
#                     created.append(f"{file_no}_{course_id}")
#                     print(f"✅ Created: {file_no}_{course_id}")

#             except Exception as insert_e:
#                 # Log and record the error. We'll include the exception message in the per-doc error list.
#                 frappe.log_error(
#                     title=f"Error saving Client Progression for {file_no}",
#                     message=traceback.format_exc(),
#                 )
#                 errors_per_doc.setdefault(file_no, []).append({"save_error": str(insert_e)})
#                 skipped.append({
#                     "reason": str(insert_e),
#                     "file_number": file_no,
#                     "course_id": course_id,
#                 })

#         # Final summary logging
#         frappe.log_error(
#             "Client Progression Info Import Summary",
#             f"Created: {len(created)}, Updated: {len(updated)}, Skipped: {len(skipped)}",
#         )

#         return {
#             "message": "Client Progression Info import completed",
#             "created_count": len(created),
#             "updated_count": len(updated),
#             "skipped_count": len(skipped),
#             "created": created[:50],
#             "updated": updated[:50],
#             "skipped": skipped[:50],
#             "errors_per_doc": errors_per_doc,
#         }

#     except json.JSONDecodeError as e:
#         frappe.log_error("JSON Decode Error", str(e))
#         return {"error": f"Invalid JSON file at line {e.lineno}, column {e.colno}"}

#     except Exception as e:
#         frappe.log_error("Unexpected Error in create_client_progression_info", traceback.format_exc())
#         return {"error": str(e)}






# import frappe
# import json
# import traceback
# # 3commneted on 11-12-25 50 habdle address other ishue 
# def safe_get(d, key, default=""):
#     """Safe dictionary access: never raises, always returns something."""
#     try:
#         value = d.get(key, default)
#         return value if value is not None else default
#     except Exception:
#         # If something weird happens, just log & return default
#         frappe.log_error(
#             title=f"safe_get error for key {key}",
#             message=traceback.format_exc()
#         )
#         return default

# @frappe.whitelist(allow_guest=True)
# def create_client_progression_info():
#     try:
#         file_path = "/home/frappe-user/ibelog-frappe/apps/ibelong_system/ibelong_system/Client_Progression_full_data2.json"

#         with open(file_path, "r") as f:
#             client_data = json.load(f)

#         created, skipped = [], []

#         for client in client_data:
#             # --- Normalize keys: if missing, set to "" (but never fail) ---
#             for key in [
#                 "File_Number",
#                 "Course_Level",
#                 "CourseId",
#                 "Certificate_Number",
#                 "Service_Provider",
#                 "First_Name",
#                 "Last_Name",
#                 "Gender",
#                 "Date_of_Birth",
#                 "Nationality",
#                 "ID_Card_Number",
#                 "Country_Of_Birth",
#                 "Mobile_Number",
#                 "Email_ID",
#                 "House_Name",
#                 "House_Number",
#                 "Street_Name",
#                 "Locality",
#                 "Post_Code",
#                 "Correspondence_Address",
#                 "ClientStatus",
#                 "Selected_Course_Type",
#                 "Assigned_Batch",
#                 "Result",
#                 "Alternative_ID_Card_Number",
#             ]:
#                 try:
#                     client[key] = client.get(key, "") or ""
#                 except Exception:
#                     # Even this should not break the loop
#                     frappe.log_error(
#                         title=f"Error normalizing key {key}",
#                         message=traceback.format_exc(),
#                     )
#                     client[key] = ""

#             file_no = safe_get(client, "File_Number", "")
#             course_id = safe_get(client, "CourseId", "")

#             if not file_no:
#                 skipped.append({"reason": "Missing File_Number", "client": client})
#                 continue

#             # Unique enrolment number = FileNo + CourseId
#             enrollment_no = f"{file_no}_{course_id}" if course_id else file_no

#             # Skip if same file_number + course already exists
#             if frappe.db.exists(
#                 "Client Progression Details",
#                 {
#                     "file_number": file_no,
#                     "which_courses_are_assigned_to_the_client": course_id,
#                 },
#             ):
#                 skipped.append({
#                     "reason": "Duplicate File_Number + CourseId combination",
#                     "file_number": file_no,
#                     "course_id": course_id,
#                 })
#                 continue

#             # --- Date of birth: be defensive, never raise ---
#             dob_raw = safe_get(client, "Date_of_Birth", "")
#             try:
#                 if " " in dob_raw:
#                     dob = dob_raw.split(" ")[0]
#                 else:
#                     dob = dob_raw
#             except Exception:
#                 frappe.log_error(
#                     title=f"Error parsing DOB for {file_no}",
#                     message=traceback.format_exc(),
#                 )
#                 dob = ""  # skip invalid DOB

#             # --- Build doc_data: every field via safe_get so any bad value is replaced ---
#             doc_data = {
#                 "doctype": "Client Progression Details",
#                 "file_number": file_no,
#                 "enrolment_number": enrollment_no,

#                 # Course Information
#                 "course_level": safe_get(client, "Course_Level", ""),
#                 "course_status": safe_get(client, "Result", ""),
#                 "status": safe_get(client, "ClientStatus", ""),
#                 "which_courses_are_assigned_to_the_client": course_id,
#                 "approved_by_sp": safe_get(client, "Assigned_Batch", ""),
#                 "certificate_no": safe_get(client, "Certificate_Number", ""),
#                 "class_location": "",
#                 "service_provider": safe_get(client, "Service_Provider", ""),

#                 # Personal Details
#                 "first_name": safe_get(client, "First_Name", ""),
#                 "last_name": safe_get(client, "Last_Name", ""),
#                 "gender": safe_get(client, "Gender", ""),
#                 "date_of_birth": dob,
#                 "nationality": safe_get(client, "Nationality", ""),
#                 "id_card_number": safe_get(client, "ID_Card_Number", ""),
#                 "passport_number": safe_get(client, "Alternative_ID_Card_Number", ""),
#                 "country_of_birth": safe_get(client, "Country_Of_Birth", ""),

#                 # Contact Details
#                 "mobile_number": safe_get(client, "Mobile_Number", ""),
#                 "email": safe_get(client, "Email_ID", ""),
#                 "house_name": safe_get(client, "House_Name", ""),
#                 "house_number": safe_get(client, "House_Number", ""),
#                 "street_name": safe_get(client, "Street_Name", ""),
#                 "locality": safe_get(client, "Locality", ""),
#                 "post_code": safe_get(client, "Post_Code", ""),
#                 "correspondence_address": safe_get(client, "Correspondence_Address", ""),

#                 # Static / default
#                 "selected_course_type": safe_get(client, "Selected_Course_Type", "") or "Free",
#                 "certificate_for_skip_maltese_course": "",
#                 "completed_course_certificates": "",
#                 "foundation": "",
#                 "certificate_of_completion": "",
#             }

#             try:
#                 doc = frappe.get_doc(doc_data)

#                 # Avoid emails / notifications
#                 doc.flags.ignore_mails = True

#                 # Try inserting with all fields
#                 doc.insert(ignore_permissions=True, ignore_mandatory=True)
#                 frappe.db.commit()

#                 created.append(f"{file_no}_{course_id}")
#                 print(f"✅ Created: {file_no}_{course_id}")

#             except Exception as insert_e:
#                 # At this point, we already tried to be safe per-field.
#                 # If Frappe still refuses, we log it and mark as skipped.
#                 frappe.log_error(
#                     title=f"Error inserting Client Progression for {file_no}",
#                     message=traceback.format_exc(),
#                 )
#                 skipped.append({
#                     "reason": str(insert_e),
#                     "file_number": file_no,
#                     "course_id": course_id,
#                 })

#         frappe.log_error(
#             "Client Progression Info Import Summary",
#             f"Created: {len(created)}, Skipped: {len(skipped)}",
#         )

#         return {
#             "message": "Client Progression Info import completed",
#             "created_count": len(created),
#             "skipped_count": len(skipped),
#             "created": created[:10],
#             "skipped": skipped[:10],
#         }

#     except json.JSONDecodeError as e:
#         frappe.log_error("JSON Decode Error", str(e))
#         return {"error": f"Invalid JSON file at line {e.lineno}, column {e.colno}"}

#     except Exception as e:
#         frappe.log_error(
#             "Unexpected Error in create_client_progression_info",
#             traceback.format_exc(),
#         )
#         return {"error": str(e)}

import frappe
import json
import traceback

@frappe.whitelist()
def update_batch_details_from_json():
    """
    Auto-load batch name from JSON and update/create the Batch Details document.
    Populates child table: client_attendance_child.
    - If batch exists: update it.
    - If batch does not exist: create new Batch Details doc.
    - If a row causes an error, it is skipped but the rest continue.
    """

    DEBUG_TITLE = "BatchDetailsMigration"

    try:
        file_path = "/home/frappe-user/ibelog-frappe/apps/ibelong_system/ibelong_system/Batch_Details_Full_Data_06_12_2025.json"

        # 1) LOAD JSON FILE
        try:
            with open(file_path, "r") as f:
                client_data = json.load(f)
        except Exception:
            frappe.log_error(
                title=f"{DEBUG_TITLE} - JSON Load Error",
                message=f"Failed to load JSON from path: {file_path}\n{frappe.get_traceback()}"
            )
            return "Error: Could not load JSON file. Check Error Log."

        if not client_data:
            frappe.log_error(
                title=f"{DEBUG_TITLE} - Empty JSON",
                message=f"JSON file at {file_path} is empty."
            )
            return "JSON is empty"

        # 2) COLLECT UNIQUE BATCH NAMES
        batch_names = list({row.get("Batch") for row in client_data if row.get("Batch")})

        if not batch_names:
            frappe.log_error(
                title=f"{DEBUG_TITLE} - No Batch Field",
                message="No 'Batch' field found in JSON records."
            )
            return "No Batch field found in JSON"

        results = []

        # 3) PROCESS EACH BATCH SEPARATELY
        for batch_name in batch_names:

            # Try to fetch batch document, else create new
            is_new = False
            try:
                batch_doc = frappe.get_doc("Batch Details", batch_name)
            except frappe.DoesNotExistError:
                # CREATE NEW BATCH
                try:
                    batch_doc = frappe.new_doc("Batch Details")
                    # Force the name to be the Batch code (e.g. "OC2336")
                    batch_doc.name = batch_name
                    batch_doc.select_batch = batch_name

                    # If you know field names (e.g. batch_code, course_name),
                    # you can set them here using one of the JSON rows.
                    # Example (COMMENTED OUT – only enable if field names are correct):
                    #
                    # first_row = next((r for r in client_data if r.get("Batch") == batch_name), None)
                    # if first_row:
                    #     if "Course_Name" in first_row and hasattr(batch_doc, "course_name"):
                    #         batch_doc.course_name = first_row.get("Course_Name")
                    #
                    batch_doc.insert(ignore_permissions=True)
                    is_new = True

                    frappe.log_error(
                        title=f"{DEBUG_TITLE} - Created New Batch",
                        message=f"Batch '{batch_name}' not found, created new Batch Details doc with name '{batch_doc.name}'."
                    )
                except Exception:
                    frappe.log_error(
                        title=f"{DEBUG_TITLE} - Error Creating Batch",
                        message=f"Error while creating new Batch Details: {batch_name}\n{frappe.get_traceback()}"
                    )
                    results.append(f"Error creating batch {batch_name}")
                    continue

            except Exception:
                frappe.log_error(
                    title=f"{DEBUG_TITLE} - Error Fetching Batch",
                    message=f"Error while fetching Batch Details: {batch_name}\n{frappe.get_traceback()}"
                )
                results.append(f"Error fetching batch {batch_name}")
                continue

            # Clear old rows (for both existing and newly created batch)
            batch_doc.client_attendance_child = []

            # Filter clients belonging to this batch
            clients_for_batch = [row for row in client_data if row.get("Batch") == batch_name]

            inserted_count = 0
            skipped_count = 0

            for idx, row in enumerate(clients_for_batch, start=1):

                # Default values
                file_number_raw = row.get("File_Number") or ""
                try:
                    file_number = file_number_raw.replace("\\/", "/")
                except Exception:
                    # If even replace fails, log and keep raw value
                    file_number = file_number_raw
                    frappe.log_error(
                        title=f"{DEBUG_TITLE} - File Number Clean Error",
                        message=f"Batch: {batch_name}, idx: {idx}, raw file number: {file_number_raw}\n{frappe.get_traceback()}"
                    )

                # Try inserting this single row
                try:
                    batch_doc.append("client_attendance_child", {
                        "no": idx,
                        "first_name": row.get("First_Name"),
                        "last_name": row.get("Last_Name"),
                        "file_number": file_number,
                        "email": row.get("Email_ID"),
                        "pass": 0
                    })
                    inserted_count += 1

                except Exception as e:
                    skipped_count += 1
                    # Log detailed info about the failing row, but continue
                    frappe.log_error(
                        title=f"{DEBUG_TITLE} - Row Insert Error",
                        message=(
                            f"Error inserting child row for Batch: {batch_name}\n"
                            f"idx: {idx}, File_Number: {file_number}, Email: {row.get('Email_ID')}\n"
                            f"Row Data: {row}\n\n"
                            f"Exception: {e}\n\n"
                            f"{frappe.get_traceback()}"
                        )
                    )
                    continue

            # Save the batch document
            try:
                batch_doc.save(ignore_permissions=True)
                frappe.db.commit()

                action = "Created" if is_new else "Updated"
                results.append(
                    f"{action} Batch: {batch_name} with {inserted_count} clients (skipped {skipped_count})"
                )
            except Exception as e:
                frappe.log_error(
                    title=f"{DEBUG_TITLE} - Batch Save Error",
                    message=(
                        f"Error saving Batch Details doc: {batch_name}\n"
                        f"Exception: {e}\n\n"
                        f"{frappe.get_traceback()}"
                    )
                )
                results.append(f"Error saving batch {batch_name}")

        # Final summary
        frappe.log_error(
            title=f"{DEBUG_TITLE} - Completed",
            message=f"Migration finished.\nResults:\n" + "\n".join(results)
        )

        return results

    except Exception:
        # Catch any unexpected top-level error
        frappe.log_error(
            title=f"{DEBUG_TITLE} - Fatal Error",
            message=f"Unexpected error in update_batch_details_from_json\n{frappe.get_traceback()}"
        )
        return "Fatal error occurred. Check Error Log."


# import frappe
# import json
# import traceback

# @frappe.whitelist(allow_guest=True)
# def create_client_progression_info():
#     try:
#         # frappe.log_error("create_client_progression_info started ->")

#         file_path = "/home/frappe-user/ibelog-frappe/apps/ibelong_system/ibelong_system/Client_Progression_full_data2.json"

#         with open(file_path, "r") as f:
#             client_data = json.load(f)

#         created, skipped = [], []

#         for client in client_data:
#             try:
#                 # Ensure all expected keys exist (using ACTUAL JSON keys)
#                 for key in [
#                     "File_Number",
#                     "Course_Level",
#                     "CourseId",
#                     "Certificate_Number",
#                     "Service_Provider",
#                     "First_Name",
#                     "Last_Name",
#                     "Gender",
#                     "Date_of_Birth",
#                     "Nationality",
#                     "ID_Card_Number",
#                     "Country_Of_Birth",
#                     "Mobile_Number",
#                     "Email_ID",
#                     "House_Name",
#                     "House_Number",
#                     "Street_Name",
#                     "Locality",
#                     "Post_Code",
#                     "Correspondence_Address",
#                     "ClientStatus",
#                     "Selected_Course_Type",
#                     "Assigned_Batch",
#                     "Result",
#                 ]:
#                     client[key] = client.get(key, "") or ""

#                 file_no = client["File_Number"]
#                 course_id = client.get("CourseId", "")

#                 if not file_no:
#                     skipped.append({"reason": "Missing File_Number", "client": client})
#                     continue

#                 # Unique enrolment number = FileNo + CourseId
#                 enrollment_no = f"{file_no}_{course_id}" if course_id else file_no

#                 # Skip if same file_number + course already exists
#                 if frappe.db.exists(
#                     "Client Progression Details",
#                     {
#                         "file_number": file_no,
#                         "which_courses_are_assigned_to_the_client": course_id,
#                     },
#                 ):
#                     skipped.append({
#                         "reason": "Duplicate File_Number + CourseId combination",
#                         "file_number": file_no,
#                         "course_id": course_id,
#                     })
#                     continue

#                 # Optional: clean date format (YYYY-MM-DD from 'YYYY-MM-DD 00:00:00')
#                 dob_raw = client.get("Date_of_Birth") or ""
#                 if " " in dob_raw:
#                     dob = dob_raw.split(" ")[0]
#                 else:
#                     dob = dob_raw

#                 # Build doc data mapping JSON -> DocType fields
#                 doc_data = {
#                     "doctype": "Client Progression Details",
#                     "file_number": file_no,
#                     "enrolment_number": enrollment_no,

#                     # Course Information
#                     # From JSON: "Course_Level": "Stage 1"
#                     "course_level": client.get("Course_Level", ""),
#                     # You can map "Result" here if that's your course status
#                     # "course_status": client.get("Result", ""),
#                     # From JSON: "ClientStatus": "Stage 1 - Allocated"
#                     "status": client.get("ClientStatus", ""),
#                     "which_courses_are_assigned_to_the_client": course_id,
#                     # There is "Assigned_Batch" in JSON, no "ClassId"
#                     "approved_by_sp": client.get("Assigned_Batch", ""),
#                     "certificate_no": client.get("Certificate_Number", ""),
#                     # No "Class Location" in sample JSON, keep empty or map if you add it later
#                     "class_location": "",
#                     "service_provider": client.get("Service_Provider", ""),

#                     # Personal Details
#                     "first_name": client.get("First_Name", ""),
#                     "last_name": client.get("Last_Name", ""),
#                     "gender": client.get("Gender", ""),
#                     "date_of_birth": dob,
#                     "nationality": client.get("Nationality", ""),
#                     "id_card_number": client.get("ID_Card_Number", ""),
#                     "passport_number": client.get("Alternative_ID_Card_Number", "") or "",
#                     "country_of_birth": client.get("Country_Of_Birth", ""),

#                     # Contact Details
#                     "mobile_number": client.get("Mobile_Number", ""),
#                     "email": client.get("Email_ID", ""),
#                     "house_name": client.get("House_Name", ""),
#                     "house_number": client.get("House_Number", ""),
#                     "street_name": client.get("Street_Name", ""),
#                     "locality": client.get("Locality", ""),
#                     "post_code": client.get("Post_Code", ""),
#                     "correspondence_address": client.get("Correspondence_Address", ""),

#                     # Static or from JSON
#                     "selected_course_type": client.get("Selected_Course_Type", "") or "Free",
#                     "certificate_for_skip_maltese_course": "",
#                     "completed_course_certificates": "",
#                     "foundation": "",
#                     "certificate_of_completion": "",
#                 }

#                 doc = frappe.get_doc(doc_data)

#                 # If you don't want notifications / emails during migration:
#                 doc.flags.ignore_mails = True

#                 doc.insert(ignore_permissions=True, ignore_mandatory=True)
#                 frappe.db.commit()

#                 created.append(f"{file_no}_{course_id}")
#                 print(f"✅ Created: {file_no}_{course_id}")

#             except Exception as inner_e:
#                 frappe.log_error(
#                     title=f"Error processing {client.get('File_Number', 'Unknown File')}",
#                     message=traceback.format_exc(),
#                 )
#                 skipped.append({
#                     "reason": str(inner_e),
#                     "file_number": client.get("File_Number", ""),
#                     "course_id": client.get("CourseId", ""),
#                 })

#         frappe.log_error(
#             "Client Progression Info Import Summary",
#             f"Created: {len(created)}, Skipped: {len(skipped)}",
#         )

#         return {
#             "message": "Client Progression Info import completed",
#             "created_count": len(created),
#             "skipped_count": len(skipped),
#             "created": created[:10],
#             "skipped": skipped[:10],
#         }

#     except json.JSONDecodeError as e:
#         frappe.log_error("JSON Decode Error", str(e))
#         return {"error": f"Invalid JSON file at line {e.lineno}, column {e.colno}"}

#     except Exception as e:
#         frappe.log_error(
#             "Unexpected Error in create_client_progression_info",
#             traceback.format_exc(),
#         )
#         return {"error": str(e)}

# import frappe
# import json
# import traceback

# @frappe.whitelist(allow_guest=True)
# def create_client_progression_info():
#     try:
#         frappe.log_error("create_client_progression_info started->")

#         file_path = "/home/frappe-user/ibelog-frappe/apps/ibelong_system/ibelong_system/Client_Progression_full_data2.json"

#         with open(file_path, "r") as f:
#             client_data = json.load(f)

#         created, skipped = [], []

#         for client in client_data:
#             try:
#                 # Ensure all expected keys exist
#                 for key in [
#                     "File_Number", "Course_Level", "IntegrationApplicationStatusId", "CourseId", "ClassId",
#                     "CertificateNo", "Class Location", "Service Provicer", "First Name", "Last Name",
#                     "Gender", "Date of Birth", "Nationality", "ID Card Number", "Country Of Birth",
#                     "Mobile Number", "Email", "House Name", "House Number", "Street Name", "Locality",
#                     "Post Code", "Correspondence Address"
#                 ]:
#                     client[key] = client.get(key, "") or ""

#                 file_no = client["File_Number"]
#                 course_id = client.get("CourseId", "")

#                 if not file_no:
#                     skipped.append({"reason": "Missing File_Number", "client": client})
#                     continue

#                 # Unique enrolment number = FileNo + CourseId
#                 enrollment_no = f"{file_no}_{course_id}" if course_id else file_no

#                 # Skip only if both file_number and CourseId already exist
#                 if frappe.db.exists(
#                     "Client Progression Details",
#                     {"file_number": file_no, "which_courses_are_assigned_to_the_client": course_id}
#                 ):
#                     skipped.append({
#                         "reason": "Duplicate File_Number + CourseId combination",
#                         "file_number": file_no,
#                         "course_id": course_id
#                     })
#                     continue

#                 doc_data = {
#                     "doctype": "Client Progression Details",
#                     "file_number": file_no,
#                     "enrolment_number": enrollment_no,

#                     # Course Information
#                     "course_level": client.get("StageId", ""),
#                     "course_status": client.get("IntegrationApplicationStatusId", ""),
#                     "status": client.get("ClientStatus", ""),
#                     "which_courses_are_assigned_to_the_client": course_id,
#                     "approved_by_sp": client.get("ClassId", ""),
#                     "certificate_no": client.get("CertificateNo", ""),
#                     "class_location": client.get("Class Location", ""),
#                     "service_provider": client.get("Service Provicer", ""),

#                     # Personal Details
#                     "first_name": client.get("First Name", ""),
#                     "last_name": client.get("Last Name", ""),
#                     "gender": client.get("Gender", ""),
#                     "date_of_birth": client.get("Date of Birth", ""),
#                     "nationality": client.get("Nationality", ""),
#                     "id_card_number": client.get("ID Card Number", ""),
#                     "passport_number": "",
#                     "country_of_birth": client.get("Country Of Birth", ""),

#                     # Contact Details
#                     "mobile_number": client.get("Mobile Number", ""),
#                     "email": client.get("Email", ""),
#                     "house_name": client.get("House Name", ""),
#                     "house_number": client.get("House Number", ""),
#                     "street_name": client.get("Street Name", ""),
#                     "locality": client.get("Locality", ""),
#                     "post_code": client.get("Post Code", ""),
#                     "correspondence_address": client.get("Correspondence Address", ""),

#                     # Static or empty fields
#                     "selected_course_type": "Free",
#                     "certificate_for_skip_maltese_course": "",
#                     "completed_course_certificates": "",
#                     "foundation": "",
#                     "certificate_of_completion": ""
#                 }

#                 doc = frappe.get_doc(doc_data)
#                 doc.insert(ignore_permissions=True, ignore_mandatory=True)
#                 frappe.db.commit()

#                 created.append(f"{file_no}_{course_id}")
#                 print(f"✅ Created: {file_no}_{course_id}")

#             except Exception as inner_e:
#                 frappe.log_error(
#                     title=f"Error processing {client.get('File_Number', 'Unknown File')}",
#                     message=traceback.format_exc()
#                 )
#                 skipped.append({
#                     "reason": str(inner_e),
#                     "file_number": client.get("File_Number", ""),
#                     "course_id": client.get("CourseId", "")
#                 })

#         frappe.log_error(
#             "Client Progression Info Import Summary",
#             f"Created: {len(created)}, Skipped: {len(skipped)}"
#         )

#         return {
#             "message": "Client Progression Info import completed",
#             "created_count": len(created),
#             "skipped_count": len(skipped),
#             "created": created[:10],
#             "skipped": skipped[:10]
#         }

#     except json.JSONDecodeError as e:
#         frappe.log_error("JSON Decode Error", str(e))
#         return {"error": f"Invalid JSON file at line {e.lineno}, column {e.colno}"}

#     except Exception as e:
#         frappe.log_error("Unexpected Error in create_client_progression_info", traceback.format_exc())
#         return {"error": str(e)}


import frappe
import json
from collections import defaultdict

@frappe.whitelist(allow_guest=False)
def update_client_available_location():
    try:
        # Path to your JSON file
        file_path = "/home/frappe-user/ibelog-frappe/apps/ibelong_system/ibelong_system/time.json"

        # Load JSON data
        with open(file_path, "r") as f:
            client_data = json.load(f)

        # Group days by FileNo
        grouped_days = defaultdict(list)
        for entry in client_data:
            file_no = entry.get("FileNo")
            day_name = entry.get("TimeAvailabilityName")
            if file_no and day_name:
                grouped_days[file_no].append(day_name)

        updated, not_found, errors = [], [], []

        # Iterate grouped records
        for file_no, days in grouped_days.items():
            try:
                # Check if client exists
                if not frappe.db.exists("Client Details", file_no):
                    not_found.append(file_no)
                    continue

                # Load client
                doc = frappe.get_doc("Client Details", file_no)

                # Clear existing rows
                # doc.set("available_days_table", [])

                # Add each day to child table
                # frappe.log_error("data ->",doc)
                for day in days:
                    doc.append("availability_for_attend_program", {
                        "available_time": day
                    })
                # frappe.log_error("done")

                # Save changes
                doc.save(ignore_permissions=True)
                frappe.db.commit()
                updated.append(file_no)

            except Exception as e:
                frappe.db.rollback()
                errors.append(f"{file_no}: {str(e)}")
                continue

        return {
            "message": "Available days update complete",
            "updated_count": len(updated),
            "not_found": not_found,
            "errors": errors
        }

    except Exception as e:
        frappe.log_error(f"Error in update_client_available_days: {str(e)}")
        return {"error": str(e)}
@frappe.whitelist()
def check_integration_support_for_lei_clients():
    # get all Client Details where name starts with 'LEI'
    records = frappe.get_all(
        "Client Details",
        filters={"name": ["like", "LEI%"]},
        fields=["name", "integration_support"]
    )

    if not records:
        return {"status": "error", "message": "No Client Details found starting with 'LEI'."}

    updated = []
    skipped = []

    for r in records:
        try:
            doc = frappe.get_doc("Client Details", r.name)
            # Only check if not already checked
            if not doc.integration_support:
                doc.integration_support = 1
                doc.verify_otp = 1
                doc.save(ignore_permissions=True)
                frappe.db.commit()
                updated.append(r.name)
            else:
                skipped.append(r.name)
        except Exception as e:
            frappe.log_error(f"Error updating {r.name}: {str(e)}", "Integration Support Update Error")

    return {
        "status": "success",
        "message": "Integration support checkbox updated successfully.",
        "total_found": len(records),
        "updated_count": len(updated),
        "skipped_count": len(skipped),
        "updated_records": updated,
        "skipped_records": skipped
    }
