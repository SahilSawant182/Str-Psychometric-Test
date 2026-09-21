import frappe


@frappe.whitelist(allow_guest=True)
def load_question(screen_name):
    doc = frappe.get_doc("Student Test Screen", screen_name)
    return doc.load_question()


@frappe.whitelist(allow_guest=True)
def next_question(screen_name, selected_option=None, user_input=None, open_ended=None):
    doc = frappe.get_doc("Student Test Screen", screen_name)
    return doc.next_question(selected_option, user_input, open_ended)


@frappe.whitelist(allow_guest=True)
def previous_question(screen_name):
    doc = frappe.get_doc("Student Test Screen", screen_name)
    return doc.previous_question()


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




    doc = frappe.new_doc("Student Test Screen")
    doc.test_type = test_type
    doc.test = test_type
    doc.question_index = 0
    user_email = email or (frappe.session.user if frappe.session.user != "Guest" else None)
    if user_email:
        doc.owner = user_email
        doc.student = user_email
    doc.insert(ignore_permissions=True)
    doc.init_test_instance()
    return doc.name


@frappe.whitelist(allow_guest=True)
def start_new_test(test_type=None, email=None):
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


