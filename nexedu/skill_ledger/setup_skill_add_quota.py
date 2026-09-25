"""
setup_skill_add_quota.py
========================
One-time setup script: registers the SKILL_ADD feature in Application Features
and adds the weekly limit rows to every Billing Package.

Run via bench console:
    bench --site devstridenex.quantcloud.in console
    >>> exec(open('apps/nexedu/nexedu/skill_ledger/setup_skill_add_quota.py').read())

Or as a bench execute:
    bench --site devstridenex.quantcloud.in execute \
        nexedu.skill_ledger.setup_skill_add_quota.run
"""

import frappe

# ---------------------------------------------------------------------------
# Config — adjust these as needed before running
# ---------------------------------------------------------------------------

FEATURE_CODE  = "SKILL_ADD"
FEATURE_TITLE = "Skill Add"          # human-readable name shown in the UI
FEATURE_APP   = "stridenex_app"      # must match an option in the App select field

# Per-package limits  { package_name: (usage_limit, reset_frequency) }
# usage_limit = 0  →  Unlimited
PACKAGE_LIMITS = {
    "Student Trial":           (2, "Weekly"),
    "Student Pro Package":     (2, "Weekly"),
    "Student Advance Package": (0, "Weekly"),   # 0 = Unlimited
    "Student Max Package":     (0, "Weekly"),   # 0 = Unlimited
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _upsert_app_feature_details(package_doc, feature_name: str, usage_limit: int, freq: str):
    """
    Adds or updates an App Feature Details row on the Billing Package doc
    for the given feature_name.
    """
    for row in package_doc.get("app_feature_details", []):
        if row.feature_list == feature_name:
            row.usage_limit      = usage_limit
            row.reset_frequency  = freq
            print(f"  [UPDATE] {package_doc.name}: {feature_name} → {usage_limit} / {freq}")
            return

    # Row not found — append a new one
    package_doc.append("app_feature_details", {
        "feature_list":    feature_name,
        "usage_limit":     usage_limit,
        "reset_frequency": freq,
    })
    print(f"  [ADD]    {package_doc.name}: {feature_name} → {usage_limit} / {freq}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run():
    # ── Step 1: Register the Application Feature ────────────────────────────
    if frappe.db.exists("Application Features", FEATURE_TITLE):
        print(f"[OK] Application Feature '{FEATURE_TITLE}' already exists — skipping creation.")
        feature_name = FEATURE_TITLE
    else:
        feat = frappe.get_doc({
            "doctype":      "Application Features",
            "title":        FEATURE_TITLE,
            "feature_code": FEATURE_CODE,
            "app":          FEATURE_APP,
        })
        feat.insert(ignore_permissions=True)
        frappe.db.commit()
        feature_name = feat.name
        print(f"[CREATED] Application Feature: {feature_name} (code={FEATURE_CODE})")

    # ── Step 2: Add the limit rows to every Billing Package ─────────────────
    for pkg_name, (limit, freq) in PACKAGE_LIMITS.items():
        if not frappe.db.exists("Billing Package", pkg_name):
            print(f"[SKIP] Billing Package '{pkg_name}' not found — skipping.")
            continue

        pkg_doc = frappe.get_doc("Billing Package", pkg_name)
        _upsert_app_feature_details(pkg_doc, feature_name, limit, freq)
        pkg_doc.flags.ignore_validate = True
        pkg_doc.save(ignore_permissions=True)
        frappe.db.commit()
        print(f"[SAVED] {pkg_name}")

    # ── Step 3: Re-allocate quotas for all affected Billing Account Masters ──
    print("\n[STEP 3] Re-allocating quotas for all Billing Account Masters …")
    accounts = frappe.get_all(
        "Billing Account Master",
        fields=["name"],
        filters={"docstatus": ["!=", 2]}
    )

    from quantbit_billing_platform.quantbit_billing_platform.api import allocate_package_quotas

    for acc in accounts:
        try:
            doc = frappe.get_doc("Billing Account Master", acc.name)
            allocate_package_quotas(doc)
            doc.save(ignore_permissions=True)
            frappe.db.commit()
            print(f"  [OK] {acc.name}")
        except Exception as e:
            print(f"  [ERROR] {acc.name}: {e}")
            frappe.log_error(
                title=f"setup_skill_add_quota – BAM re-allocate error: {acc.name}",
                message=frappe.get_traceback()
            )

    print("\n✅  Setup complete. SKILL_ADD quota is now active.")


if __name__ == "__main__":
    run()
