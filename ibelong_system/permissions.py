import frappe

def is_admin_user(user):
    """Helper to check if user has admin-level privileges."""
    roles = frappe.get_roles(user)
    return "System Manager" in roles or "HRD-Admin" in roles

def get_service_provider_conditions(user=None):
    if not user:
        user = frappe.session.user
    
    # If the user is Admin or HRD, they see all records
    if is_admin_user(user):
        return ""

    # Filter by user email
    return f"`tabService Provider`.email = '{user}'"

def get_client_progression_conditions(user=None):
    if not user:
        user = frappe.session.user

    if is_admin_user(user):
        return ""

    # Get Service Provider linked to user email
    sp_name = frappe.db.get_value(
        "Service Provider",
        {"email": user},
        "name"
    )

    # Fallback to User Permission
    if not sp_name:
        sp_name = frappe.db.get_value(
            "User Permission",
            {"user": user, "allow": "Service Provider"},
            "for_value"
        )

    if sp_name:
        return f"`tabClient Progression Details`.service_provider = '{sp_name}'"

    return "1=0"

def get_client_attendance_conditions(user=None):
    if not user:
        user = frappe.session.user

    if is_admin_user(user):
        return ""

    # Get the Service Provider linked to this user
    sp_name = frappe.db.get_value("Service Provider", {"email": user}, "name")

    if sp_name:
        return f"`tabClient Attendance`.service_provider = '{sp_name}'"
    
    return "1=0"
