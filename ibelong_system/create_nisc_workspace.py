import json
import frappe

def create():
    # Create NISC User role if it doesn't exist
    if not frappe.db.exists("Role", "NISC User"):
        role = frappe.new_doc("Role")
        role.role_name = "NISC User"
        role.desk_access = 1
        role.is_custom = 1
        role.insert(ignore_permissions=True)
        print("Created role: NISC User")
    else:
        print("Role NISC User already exists")

    # Delete existing workspace to recreate cleanly
    if frappe.db.exists("Workspace", "NISC Dashboard"):
        frappe.delete_doc("Workspace", "NISC Dashboard", ignore_permissions=True)
        print("Deleted old NISC Dashboard workspace")

    # Build the content JSON matching Frappe's block format
    content = [
        {
            "id": frappe.generate_hash(length=10),
            "type": "header",
            "data": {
                "text": "<span class=\"h4\">NISC Dashboard</span>",
                "col": 12
            }
        },
        {
            "id": frappe.generate_hash(length=10),
            "type": "shortcut",
            "data": {"shortcut_name": "Clients", "col": 3}
        },
        {
            "id": frappe.generate_hash(length=10),
            "type": "shortcut",
            "data": {"shortcut_name": "Referrals", "col": 3}
        },
        {
            "id": frappe.generate_hash(length=10),
            "type": "shortcut",
            "data": {"shortcut_name": "Ext. Service Providers", "col": 3}
        }
    ]

    # Create workspace
    ws = frappe.new_doc("Workspace")
    ws.name = "NISC Dashboard"
    ws.title = "NISC Dashboard"
    ws.label = "NISC Dashboard"
    ws.module = "iBelong"
    ws.icon = "🤝"
    ws.is_hidden = 0
    ws.public = 1
    ws.sequence_id = 5.0
    ws.content = json.dumps(content)

    # Restrict to NISC User role
    ws.append("roles", {"role": "NISC User"})

    # Shortcuts (must match shortcut_name values used in content above)
    ws.append("shortcuts", {
        "type": "DocType",
        "label": "Clients",
        "link_to": "Client Details",
        "color": "Blue",
        "doc_view": "List"
    })
    ws.append("shortcuts", {
        "type": "DocType",
        "label": "Referrals",
        "link_to": "Client Referral",
        "color": "Purple",
        "doc_view": "List"
    })
    ws.append("shortcuts", {
        "type": "DocType",
        "label": "Ext. Service Providers",
        "link_to": "External Service Provider",
        "color": "Green",
        "doc_view": "List"
    })

    # Links (type must be "Link" in this Frappe version)
    ws.append("links", {
        "type": "Link",
        "label": "Clients",
        "link_to": "Client Details",
        "link_type": "DocType",
        "onboard": 1
    })
    ws.append("links", {
        "type": "Link",
        "label": "Client Referrals",
        "link_to": "Client Referral",
        "link_type": "DocType",
        "onboard": 1
    })
    ws.append("links", {
        "type": "Link",
        "label": "External Service Providers",
        "link_to": "External Service Provider",
        "link_type": "DocType",
        "onboard": 0
    })

    ws.insert(ignore_permissions=True)
    frappe.db.commit()
    print("Created workspace: NISC Dashboard")
    print("Done!")
