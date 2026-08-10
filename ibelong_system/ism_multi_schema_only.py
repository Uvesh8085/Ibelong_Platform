"""
DEPLOYMENT VARIANT for environments where migrated data must not be touched.

Same as ism_multi.py but WITHOUT the backfill() step - creates the ISM
Booking child doctype and the ism_bookings Table field on Client Details,
but does not create rows from clients' existing single-field ISM data.

Consequence: clients with historical (pre-existing) ISM activity will show
"no ISM bookings yet" in the new UI until they book again. New bookings from
this point forward work identically to an environment where the backfill ran.

Run: bench --site <site> execute ibelong_system.ism_multi_schema_only.run
"""

import frappe
from ibelong_system.ism_multi import ensure_child_doctype, ensure_table_field


def run():
    print("=== ISM Booking: schema only (no backfill - migrated data untouched) ===")
    ensure_child_doctype()
    ensure_table_field()
    frappe.db.commit()
    frappe.clear_cache()
    print("\nDone. Child table + field ready. Migrated data NOT touched (backfill skipped).")
