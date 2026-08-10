app_name = "ibelong_system"
app_title = "Ibelong System"
app_publisher = " "
app_description = " "
app_email = "test@test.com"
app_license = "mit"

fixtures = [
    {"dt": "Role", "filters": [["role_name", "in", ["NISC User"]]]},
    {"dt": "Workspace", "filters": [["name", "in", ["NISC Dashboard"]]]},
    {"dt": "Server Script", "filters": [["name", "in", [
        "Submit Stage2 Culture Only",
        "Repeater Post",
        "Status change on save"
    ]]]},
    {"dt": "Web Page", "filters": [["name", "in", ["demo-clinet-profile"]]]}
]

role_home_page = {
    "NISC User": "/app/nisc-dashboard"
}

# Apps
# ------------------
# hooks.py
# ... existing content ...
app_include_js = [
    "/assets/ibelong_system/js/model_fix.js"
]


permission_query_conditions = {
    "Service Provider": "ibelong_system.permissions.get_service_provider_conditions",
    "Client Progression Details": "ibelong_system.permissions.get_client_progression_conditions",
    "Client Attendance": "ibelong_system.permissions.get_client_attendance_conditions",
    "Batch Details": "ibelong_system.permissions.get_batch_details_conditions"
}

doc_events = {
    # Silently remove User Permissions for doctypes whose visibility
    # is already controlled by permission_query_conditions (see permissions.py).
    "User Permission": {
        "after_insert": "ibelong_system.permissions.block_managed_doctype_user_permissions"
    },
    # Only NISC staff may close an ISM case, and only from a valid prior status.
    "Client Details": {
        "validate": "ibelong_system.ism_review.validate_client_details"
    }
}

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "ibelong_system",
# 		"logo": "/assets/ibelong_system/logo.png",
# 		"title": "Ibelong System",
# 		"route": "/ibelong_system",
# 		"has_permission": "ibelong_system.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/ibelong_system/css/ibelong_system.css"
# app_include_js = "/assets/ibelong_system/js/ibelong_system.js"

# include js, css files in header of web template
# web_include_css = "/assets/ibelong_system/css/ibelong_system.css"
# web_include_js = "/assets/ibelong_system/js/ibelong_system.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "ibelong_system/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "ibelong_system/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "ibelong_system.utils.jinja_methods",
# 	"filters": "ibelong_system.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "ibelong_system.install.before_install"
# after_install = "ibelong_system.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "ibelong_system.uninstall.before_uninstall"
# after_uninstall = "ibelong_system.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "ibelong_system.utils.before_app_install"
# after_app_install = "ibelong_system.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "ibelong_system.utils.before_app_uninstall"
# after_app_uninstall = "ibelong_system.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "ibelong_system.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }


# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"ibelong_system.tasks.all"
# 	],
# 	"daily": [
# 		"ibelong_system.tasks.daily"
# 	],
# 	"hourly": [
# 		"ibelong_system.tasks.hourly"
# 	],
# 	"weekly": [
# 		"ibelong_system.tasks.weekly"
# 	],
# 	"monthly": [
# 		"ibelong_system.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "ibelong_system.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "ibelong_system.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "ibelong_system.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["ibelong_system.utils.before_request"]
# after_request = ["ibelong_system.utils.after_request"]

# Job Events
# ----------
# before_job = ["ibelong_system.utils.before_job"]
# after_job = ["ibelong_system.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"ibelong_system.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

