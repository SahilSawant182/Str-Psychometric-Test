import frappe

import json

def _extract_screen_name(screen_name):
    if isinstance(screen_name, dict):
        if screen_name.get("status") == "quota_exceeded":
            return None, {"completed": True, "error": "quota_exceeded", "message": screen_name.get("message")}
        return screen_name.get("screen_name") or screen_name.get("name"), None
        
    if isinstance(screen_name, str) and screen_name.strip().startswith("{"):
        try:
            parsed = json.loads(screen_name)
            if parsed.get("status") == "quota_exceeded":
                return None, {"completed": True, "error": "quota_exceeded", "message": parsed.get("message")}
            return parsed.get("screen_name") or parsed.get("name") or screen_name, None
        except Exception:
            pass
            
    return screen_name, None

@frappe.whitelist(allow_guest=True)
def load_question(screen_name=None):
    try:
        if not screen_name:
            return {"completed": True, "error": "missing_screen_name"}
            
        s_name, err = _extract_screen_name(screen_name)
        if err: return err
        
        doc = frappe.get_doc("Student Test Screen", s_name)
        return doc.load_question()
    except Exception as e:
        import traceback
        frappe.log_error(title=f"load_question crash: {str(screen_name)[:50]}", message=traceback.format_exc())
        frappe.local.response['http_status_code'] = 500
        return {"completed": True, "error": "server_error", "message": str(e)}


@frappe.whitelist(allow_guest=True)
def next_question(screen_name=None, selected_option=None, user_input=None, open_ended=None):
    try:
        if not screen_name:
            return {"completed": True, "error": "missing_screen_name"}
            
        s_name, err = _extract_screen_name(screen_name)
        if err: return err
        
        doc = frappe.get_doc("Student Test Screen", s_name)
        return doc.next_question(selected_option, user_input, open_ended)
    except Exception as e:
        import traceback
        frappe.log_error(title=f"next_question crash: {str(screen_name)[:50]}", message=traceback.format_exc())
        frappe.local.response['http_status_code'] = 500
        return {"completed": True, "error": "server_error", "message": str(e)}


@frappe.whitelist(allow_guest=True)
def previous_question(screen_name=None):
    try:
        if not screen_name:
            return {"completed": True, "error": "missing_screen_name"}
            
        s_name, err = _extract_screen_name(screen_name)
        if err: return err
        
        doc = frappe.get_doc("Student Test Screen", s_name)
        return doc.previous_question()
    except Exception as e:
        import traceback
        frappe.log_error(title=f"previous_question crash: {str(screen_name)[:50]}", message=traceback.format_exc())
        frappe.local.response['http_status_code'] = 500
        return {"completed": True, "error": "server_error", "message": str(e)}


@frappe.whitelist(allow_guest=True)
def create_student_test_screen(test_type=None, email=None):
    if not test_type or test_type in ["Demo psy 1", "undefined", "null"]:
        test_type = "Psychometric Career Assessment"

    if not frappe.db.exists("Str Psychometric Test", test_type):
        test_doc = frappe.new_doc("Str Psychometric Test")
        test_doc.name = test_type
        test_doc.title = test_type
        test_doc.is_active = 1
        test_doc.passing_percentage = 50
        sub = frappe.db.get_value("Str Psychometric Subject", {}, "name")
        if sub:
            test_doc.append("psychometric_test_subject", {"subject": sub})
        test_doc.flags.ignore_validate = True
        test_doc.insert(ignore_permissions=True)

    user_email = email or (frappe.session.user if frappe.session.user != "Guest" else None)
    
    # ── QUOTA GATE ────────────────────────────────────────────────────────────
    session_user = frappe.session.user
    is_admin = session_user in ("Administrator",) or "System Manager" in frappe.get_roles(session_user)
    
    if not is_admin:
        quota_check = _enforce_psychometric_quota(session_user, user_email)
        if quota_check and quota_check.get("status") == "quota_exceeded":
            return quota_check
    # ─────────────────────────────────────────────────────────────────────────

    doc = frappe.new_doc("Student Test Screen")
    doc.test_type = test_type
    doc.test = test_type
    doc.question_index = 0
    if user_email:
        doc.owner = user_email
        doc.student = user_email
    doc.insert(ignore_permissions=True)
    doc.init_test_instance()
    
    # Consume quota atomically after successful insert
    if not is_admin:
        _consume_psychometric_quota(session_user, user_email)
        
    return {"status": "success", "screen_name": doc.name}

@frappe.whitelist(allow_guest=True)
def start_new_test(test_type=None, email=None):
    # Delegate to create_student_test_screen which now handles quota and returns a dictionary
    return create_student_test_screen(test_type, email)


@frappe.whitelist(allow_guest=True)
def submit_test(name, email=None):
    doc = frappe.get_doc("Student Test Screen", name)

    if doc.docstatus == 0:
        doc.flags.ignore_permissions = True
        doc.submit()

    user_email = email or (frappe.session.user if frappe.session.user != "Guest" else None) or doc.owner or doc.student
    if user_email and user_email != "Guest":
        sub_name = frappe.db.get_value("Str Psychometric Test Submission", {"student_test_screen": doc.name})
        if sub_name:
            frappe.db.set_value("Str Psychometric Test Submission", sub_name, "member", user_email)

        student_name = frappe.db.get_value("Student", {"email_id": user_email})
        if not student_name and frappe.db.exists("Student", user_email):
            student_name = user_email
        if student_name:
            frappe.db.set_value("Student", student_name, "is_first_login", 0)

    return {
        "status": "Submitted",
        "result": doc.profile_result,
        "job_score": doc.job_score,
        "startup_score": doc.entrepreneurship_score,
        "entrepreneurship_score": doc.entrepreneurship_score,
        "higher_ed_score": doc.higher_education_score,
        "raw_job_score": doc.raw_job_score,
        "raw_entrepreneurship_score": doc.raw_entrepreneurship_score,
        "raw_higher_education_score": doc.raw_higher_education_score,
        "ai_result": getattr(doc, "ai_result", None)
    }


@frappe.whitelist(allow_guest=True)
def get_tests():
    if not frappe.db.exists("Str Psychometric Test", "Psychometric Career Assessment"):
        test_doc = frappe.new_doc("Str Psychometric Test")
        test_doc.name = "Psychometric Career Assessment"
        test_doc.title = "Psychometric Career Assessment"
        test_doc.is_active = 1
        test_doc.insert(ignore_permissions=True)

    return [{"name": "Psychometric Career Assessment"}]



@frappe.whitelist(allow_guest=True)
def check_test_status(email=None):
    user = email or (frappe.session.user if frappe.session.user != "Guest" else None)
    if not user or user == "Guest":
        return {
            "has_completed_test": False,
            "submission": None
        }

    submission = frappe.db.get_value(
        "Str Psychometric Test Submission",
        {"member": user},
        ["name", "psychometric_test", "creation", "profile_type", "job_score", "entrepreneurship_score", "higher_education_score"],
        as_dict=True
    )
    if not submission:
        submission = frappe.db.get_value(
            "Str Psychometric Test Submission",
            {"owner": user},
            ["name", "psychometric_test", "creation", "profile_type", "job_score", "entrepreneurship_score", "higher_education_score"],
            as_dict=True
        )

    return {
        "has_completed_test": bool(submission),
        "submission": submission
    }


@frappe.whitelist(allow_guest=True)
def check_onboarding_status(email=None):
    user = email or (frappe.session.user if frappe.session.user != "Guest" else None)
    
    if not user or user == "Guest":
        return {
            "is_first_login": False,
            "is_onboarded": False,
            "test_completed": False,
            "has_completed_test": False,
            "requires_test": False,
            "submission": None,
            "test_screen": None
        }

    student_name = frappe.db.get_value("Student", {"email_id": user})
    if not student_name and frappe.db.exists("Student", user):
        student_name = user

    student_is_first_login = None
    if student_name:
        student_is_first_login = frappe.db.get_value("Student", student_name, "is_first_login")

    submission = frappe.db.get_value(
        "Str Psychometric Test Submission",
        {"member": user},
        ["name", "psychometric_test", "creation", "score", "percentage", "profile_type", "job_score", "entrepreneurship_score", "higher_education_score"],
        as_dict=True
    )
    if not submission:
        submission = frappe.db.get_value(
            "Str Psychometric Test Submission",
            {"owner": user},
            ["name", "psychometric_test", "creation", "score", "percentage", "profile_type", "job_score", "entrepreneurship_score", "higher_education_score"],
            as_dict=True
        )
    
    test_screen = frappe.db.get_value(
        "Student Test Screen",
        {"owner": user, "docstatus": 1},
        ["name", "creation", "docstatus"],
        as_dict=True
    )
    
    has_completed = bool(submission or test_screen)

    if student_is_first_login is not None:
        is_first_login = bool(student_is_first_login)
    else:
        is_first_login = not has_completed

    requires_test = is_first_login
    is_onboarded = has_completed and not is_first_login
    
    return {
        "is_first_login": is_first_login,
        "is_onboarded": is_onboarded,
        "test_completed": has_completed,
        "has_completed_test": has_completed,
        "requires_test": requires_test,
        "submission": submission,
        "test_screen": test_screen
    }


@frappe.whitelist()
def import_questions_file(file_path):
    from nexedu.nexedu.psychometric_engine import import_psychometric_questions_from_file
    count = import_psychometric_questions_from_file(file_path)
    return {
        "status": "Success",
        "message": f"Successfully imported/updated {count} psychometric questions from {file_path}",
        "imported_count": count
    }



# ── Internal helper: psychometric test quota handlers ───────────────────────────

_PSYCHOMETRIC_FEATURE_CODE = "take_psychometric_test"

def _resolve_user_email(session_user, student=None):
    user_email = session_user
    if not user_email or user_email == "Guest":
        if student:
            user_email = frappe.db.get_value("Student", student, "email_id") or student
        else:
            frappe.throw("Authentication required.", frappe.AuthenticationError)
    return user_email

def _get_psychometric_quota_row(user_email: str):
    feature_name = frappe.db.get_value(
        "Application Features",
        {"feature_code": _PSYCHOMETRIC_FEATURE_CODE},
        "name"
    )
    if not feature_name:
        return None

    rows = frappe.db.get_all(
        "User Quota Tracker",
        filters={
            "parent": user_email,
            "parenttype": "Billing Account Master",
            "feature": feature_name
        },
        fields=["name", "total_limit", "used_count", "reset_frequency", "last_reset_date"],
        limit=1
    )
    return rows[0] if rows else None

def _days_until_reset(last_reset_date) -> int:
    from frappe.utils import getdate, date_diff, today as frappe_today
    if not last_reset_date:
        return 7
    days_since = date_diff(getdate(frappe_today()), getdate(last_reset_date))
    remaining = 7 - int(days_since)
    return max(remaining, 0)

def _enforce_psychometric_quota(session_user: str, student: str = None):
    """
    Checks if the student has remaining psychometric test quota.
    FAIL-OPEN: If no billing configured, allow freely.
    """
    user_email = _resolve_user_email(session_user, student)

    try:
        from quantbit_billing_platform.quantbit_billing_platform.api import evaluate_and_reset_cycles
        evaluate_and_reset_cycles(user_email)
    except Exception:
        frappe.log_error(title="Psychometric Quota – evaluate_and_reset_cycles failed", message=frappe.get_traceback())
        return {"status": "success"}

    row = _get_psychometric_quota_row(user_email)
    if not row:
        return {"status": "success"}

    if row.total_limit == 0:
        return {"status": "success"}

    if row.used_count >= row.total_limit:
        days_left = _days_until_reset(row.last_reset_date)
        renewal_hint = f" Your quota resets in {days_left} day(s)." if days_left > 0 else " Please upgrade your plan for more tests."
        return {
            "status": "quota_exceeded",
            "quota_remaining": 0,
            "message": f"You have used all {row.total_limit} psychometric test(s) allowed by your plan.{renewal_hint}"
        }

    return {"status": "success"}

def _consume_psychometric_quota(session_user: str, student: str = None):
    user_email = _resolve_user_email(session_user, student)
    feature_name = frappe.db.get_value(
        "Application Features",
        {"feature_code": _PSYCHOMETRIC_FEATURE_CODE},
        "name"
    )
    if not feature_name:
        return

    frappe.db.sql("""
        UPDATE `tabUser Quota Tracker`
        SET used_count = used_count + 1
        WHERE parent = %s
          AND parenttype = 'Billing Account Master'
          AND feature = %s
          AND (total_limit = 0 OR used_count < total_limit)
    """, (user_email, feature_name))

# ══════════════════════════════════════════════════════════════════════════════
# QUOTA STATUS API
# ══════════════════════════════════════════════════════════════════════════════

@frappe.whitelist(allow_guest=True)
def get_psychometric_test_quota_status(student: str = None):
    """
    Returns the student's current quota status for the 'take_psychometric_test' feature.
    """
    user_email = frappe.session.user
    if not user_email or user_email == "Guest":
        if student:
            user_email = frappe.db.get_value("Student", student, "email_id") or student
        else:
            return {
                "feature_code"   : _PSYCHOMETRIC_FEATURE_CODE,
                "total_limit"    : 0,
                "used_count"     : 0,
                "remaining"      : 0,
                "reset_frequency": "Weekly",
                "has_quota"      : False,
                "is_gated"       : True,
                "message"        : "Authentication required.",
                "can_add"        : False
            }

    try:
        from quantbit_billing_platform.quantbit_billing_platform.api import evaluate_and_reset_cycles
        evaluate_and_reset_cycles(user_email)
    except Exception:
        pass

    row = _get_psychometric_quota_row(user_email)

    if not row:
        return {
            "feature_code"   : _PSYCHOMETRIC_FEATURE_CODE,
            "total_limit"    : "Unlimited",
            "used_count"     : 0,
            "remaining"      : "Unlimited",
            "reset_frequency": "Weekly",
            "has_quota"      : True,
            "is_gated"       : False,
            "message"        : "Psychometric test is currently unrestricted.",
            "can_add"        : True,
            "days_until_reset": 0
        }

    if row.total_limit == 0:
        return {
            "feature_code"   : _PSYCHOMETRIC_FEATURE_CODE,
            "total_limit"    : "Unlimited",
            "used_count"     : row.used_count,
            "remaining"      : "Unlimited",
            "reset_frequency": row.reset_frequency or "Weekly",
            "has_quota"      : True,
            "is_gated"       : True,
            "message"        : "You have unlimited psychometric tests.",
            "can_add"        : True,
            "days_until_reset": 0
        }

    remaining = max(0, row.total_limit - row.used_count)
    has_quota = remaining > 0

    if has_quota:
        message = f"You can take {remaining} more test(s) in this billing cycle."
    else:
        freq = row.reset_frequency or "Weekly"
        renewal_hint = f" Your quota resets {freq.lower()}." if freq != "None" else " Please upgrade your plan."
        message = f"You have used all {row.total_limit} test(s) in your plan.{renewal_hint}"

    return {
        "feature_code"   : _PSYCHOMETRIC_FEATURE_CODE,
        "total_limit"    : row.total_limit,
        "used_count"     : row.used_count,
        "remaining"      : remaining,
        "reset_frequency": row.reset_frequency or "Weekly",
        "has_quota"      : has_quota,
        "is_gated"       : True,
        "message"        : message,
        "can_add"        : has_quota,
        "days_until_reset": _days_until_reset(row.last_reset_date)
    }

