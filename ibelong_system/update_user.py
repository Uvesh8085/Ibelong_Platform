import frappe
import traceback
import json

# ==========================================================
# 1. Custom Background Wrapper for Renaming User
# ==========================================================
@frappe.whitelist()   # <-- ADD THIS DECORATOR
def background_rename_user(old_email, new_email):
    log_title = f"---> Rename User Job: {old_email} to {new_email}"
    frappe.log_error(message="Rename started in background worker.", title=log_title)
    
    try:
        # Execute the rename WITHOUT the ignore_permissions flag
        # It will now rely on the Role Permissions you set in the UI
        frappe.rename_doc("User", old_email, new_email)
        
        # Background jobs must commit their own database transactions
        frappe.db.commit() 
        frappe.log_error(message="Rename done successfully.", title=log_title)
    except Exception as e:
        frappe.log_error(message=f"Failed with error:\n{traceback.format_exc()}", title=f"---> Rename FAILED: {old_email}")

# ==========================================================
# 2. Main API Endpoint
# ==========================================================
@frappe.whitelist()
def update_client_and_sync_email(name, fieldname, doctype="Client Details"):
    # Explicitly defining message= and title= fixes the TypeError in newer Frappe versions
    frappe.log_error(message=f"Name: {name} | Data: {fieldname}", title="---> API Hit: update_client_and_sync_email")

    if isinstance(fieldname, str):
        try:
            fieldname = json.loads(fieldname)
        except Exception:
            frappe.throw("Invalid data format provided.")
            
    # Capture the OLD and NEW emails
    old_email = frappe.db.get_value(doctype, name, "email")
    new_email = fieldname.get("email")
    
    frappe.log_error(message=f"Old Email: {old_email} | New Email: {new_email}", title="---> Email Values Extracted")

    # Update the main Client Details document
    try:
        doc = frappe.get_doc(doctype, name)
        doc.update(fieldname)
        doc.save(ignore_permissions=True)
    except Exception as e:
        frappe.log_error(message=f"Failed to save main Client Details {name}:\n{traceback.format_exc()}", title="---> Client Update Error")
        frappe.throw("Failed to update Client Details. Please contact support.")

    # Sync email ONLY if it actually changed
    if old_email and new_email and old_email != new_email:
        log_title = f"---> Email Sync Process: {old_email} to {new_email}"
        frappe.log_error(message="Emails are different. Starting sync process...", title=log_title)
        
        # --- ENQUEUE CUSTOM RENAME JOB ---
        if frappe.db.exists("User", old_email):
            if frappe.db.exists("User", new_email):
                frappe.throw(f"The email {new_email} is already registered to another account.")
            
            try:
                frappe.log_error(message="Enqueuing background job now...", title=log_title)
                frappe.enqueue(
                    'ibelong_system.update_user.background_rename_user', 
                    old_email=old_email,
                    new_email=new_email,
                    queue='long',
                    timeout=1500
                )
            except Exception:
                frappe.log_error(message=f"Failed to enqueue:\n{traceback.format_exc()}", title=f"---> Enqueue Failed: {old_email}")
        else:
            frappe.log_error(message=f"User {old_email} not found in User doctype.", title="---> User Sync Notice")

        # Update 'Client Progression Details'
        try:
            progression_details = frappe.get_all("Client Progression Details", filters={"email": old_email}, pluck="name")
            for doc_name in progression_details:
                try:
                    frappe.db.set_value("Client Progression Details", doc_name, "email", new_email)
                except Exception:
                    frappe.log_error(message=f"Failed Progression '{doc_name}':\n{traceback.format_exc()}", title=f"---> Sync Failed")
        except Exception:
            pass 

        # Update 'Client Details Child Table'
        try:
            child_records = frappe.get_all("Client Details Child Table", filters={"email": old_email}, pluck="name")
            for child_name in child_records:
                try:
                    frappe.db.set_value("Client Details Child Table", child_name, "email", new_email)
                except Exception:
                    frappe.log_error(message=f"Failed Child Table '{child_name}':\n{traceback.format_exc()}", title=f"---> Sync Failed")
        except Exception:
            pass 
            # --- THE FIX: LOG THEM OUT ON THE SERVER ---
        if frappe.session.user != "Guest":
            # This safely destroys the session and clears the HttpOnly cookie
            frappe.local.login_manager.logout()
    # Commit all successful database changes
    frappe.db.commit()
    
    return {"status": "success", "message": "Records updated successfully. Background sync started."}


