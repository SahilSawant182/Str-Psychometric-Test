import frappe
from frappe.model.document import Document
from nexedu.nexedu.psychometric_engine import (
    generate_controlled_test,
    calculate_effective_score_and_contributions,
    normalize_score,
    classify_career_profile,
    STANDARD_OPTIONS
)


class StudentTestScreen(Document):

    def init_test_instance(self):
        """Generates a test instance if not already initialized. Question count is read from Psychometric Settings."""
        # Read the configured question count from settings (default 30)
        settings = frappe.get_single("Psychometric Settings") if frappe.db.exists("DocType", "Psychometric Settings") else None
        configured_total = int(getattr(settings, "total_questions", 30) or 30)

        if self.str_test_response and len(self.str_test_response) >= configured_total:
            return

        test_data = generate_controlled_test(
            student_email=self.student or self.owner,
            language="English",
            test_type=self.test
        )

        self.total_job_weight = test_data["total_job_weight"]
        self.total_entrepreneurship_weight = test_data["total_entrepreneurship_weight"]
        self.total_higher_education_weight = test_data["total_higher_education_weight"]
        self.question_index = 0
        self.status = "In Progress"

        self.set("str_test_response", [])
        for q in test_data["questions"]:
            q_name = q.get("name")
            q_text = q.get("question_text") or q.get("question")
            q_dim = q.get("dimension") or q.get("test_subject") or "General"
            q_dir = q.get("direction") or "Normal"

            self.append("str_test_response", {
                "question": q_text,
                "question_link": str(q_name),
                "type": "Choices",
                "subject": q_dim,
                "dimension": q_dim,
                "direction": q_dir,
                "job_weight": float(q.get("job_weight") or 0),
                "entrepreneurship_weight": float(q.get("entrepreneurship_weight") or 0),
                "higher_education_weight": float(q.get("higher_education_weight") or 0)
            })

        self.save(ignore_permissions=True)

        # Create Psychometric Test Instance record
        inst_name = frappe.db.get_value("Psychometric Test Instance", {"student_test_screen": self.name})
        if not inst_name:
            inst_doc = frappe.new_doc("Psychometric Test Instance")
            inst_doc.student_test_screen = self.name
            inst_doc.student = self.student or self.owner or frappe.session.user
            inst_doc.random_seed = str(test_data.get("seed") or "")
            inst_doc.total_questions = len(test_data["questions"])
            inst_doc.question_index = 0
            inst_doc.status = "In Progress"
            inst_doc.total_job_weight = self.total_job_weight
            inst_doc.total_entrepreneurship_weight = self.total_entrepreneurship_weight
            inst_doc.total_higher_education_weight = self.total_higher_education_weight
            inst_doc.insert(ignore_permissions=True)


    @frappe.whitelist()
    def load_question(self):
        self.init_test_instance()

        index = self.question_index or 0
        responses = self.str_test_response

        if index >= len(responses):
            return {"completed": True}

        row = responses[index]

        # Secure Payload: Do NOT reveal weights, direction, or dimensions to frontend
        return {
            "question": row.question,
            "question_id": row.question_link,
            "question_type": "Choices",
            "subject": "Psychometric Career Assessment",
            "options": STANDARD_OPTIONS,
            "multiple_correct": False,
            "is_last": (index == len(responses) - 1),
            "no_of_options": "5",
            "saved_response": getattr(row, "response", None) or getattr(row, "selected_option", None),
            "completed": False,
            "total_questions": len(responses),
            "current_index": index
        }

    @frappe.whitelist()
    def next_question(self, selected_option=None, user_input=None, open_ended=None):
        self.init_test_instance()

        index = self.question_index or 0
        responses = self.str_test_response

        if index >= len(responses):
            return {"completed": True}

        row = responses[index]
        option_chosen = selected_option or user_input or open_ended

        if option_chosen:
            if isinstance(option_chosen, list):
                option_chosen = option_chosen[0] if option_chosen else ""

            # Fetch question doc for weights & direction
            q_doc = None
            if row.question_link and frappe.db.exists("Psychometric Question", row.question_link):
                q_doc = frappe.get_doc("Psychometric Question", row.question_link)
            elif row.question_link and frappe.db.exists("Str Question", row.question_link):
                q_doc = frappe.get_doc("Str Question", row.question_link)

            if q_doc:
                calc = calculate_effective_score_and_contributions(q_doc, option_chosen)
            else:
                # Fallback calculation using row values
                q_fake = {
                    "direction": row.direction or "Normal",
                    "job_weight": row.job_weight or 0,
                    "entrepreneurship_weight": row.entrepreneurship_weight or 0,
                    "higher_education_weight": row.higher_education_weight or 0
                }
                calc = calculate_effective_score_and_contributions(q_fake, option_chosen)

            row.response = option_chosen
            if hasattr(row, "selected_option"):
                row.selected_option = option_chosen
            row.effective_score = calc["effective_score"]
            row.mark = int(calc["effective_score"] or 0)
            row.maximum_marks = 2
            row.job_weight = calc["job_weight"]
            row.entrepreneurship_weight = calc["entrepreneurship_weight"]
            row.higher_education_weight = calc["higher_education_weight"]
            row.job_contribution = calc["job_contribution"]
            row.entrepreneurship_contribution = calc["entrepreneurship_contribution"]
            row.higher_education_contribution = calc["higher_education_contribution"]


        self.question_index += 1

        if self.question_index >= len(responses):
            self.status = "Completed"
            self.save(ignore_permissions=True)
            if self.docstatus == 0:
                self.flags.ignore_permissions = True
                self.submit()
            return {"completed": True}


        self.save(ignore_permissions=True)

        next_row = responses[self.question_index]
        return {
            "question": next_row.question,
            "question_id": next_row.question_link,
            "question_type": "Choices",
            "subject": "Psychometric Career Assessment",
            "options": STANDARD_OPTIONS,
            "multiple_correct": False,
            "is_last": (self.question_index == len(responses) - 1),
            "saved_response": getattr(next_row, "response", None) or getattr(next_row, "selected_option", None),
            "completed": False,
            "total_questions": len(responses),
            "current_index": self.question_index
        }

    @frappe.whitelist()
    def previous_question(self):
        if not self.question_index or self.question_index <= 0:
            return self.load_question()

        self.question_index -= 1
        self.save(ignore_permissions=True)

        row = self.str_test_response[self.question_index]
        return {
            "question": row.question,
            "question_id": row.question_link,
            "question_type": "Choices",
            "subject": "Psychometric Career Assessment",
            "options": STANDARD_OPTIONS,
            "saved_response": getattr(row, "response", None) or getattr(row, "selected_option", None),
            "multiple_correct": False,
            "no_of_options": "5",
            "is_last": False,
            "completed": False
        }

    def calculate_scores(self):
        raw_j = sum(float(r.job_contribution or 0) for r in self.str_test_response)
        raw_e = sum(float(r.entrepreneurship_contribution or 0) for r in self.str_test_response)
        raw_h = sum(float(r.higher_education_contribution or 0) for r in self.str_test_response)

        self.raw_job_score = raw_j
        self.raw_entrepreneurship_score = raw_e
        self.raw_higher_education_score = raw_h

        norm_j = normalize_score(raw_j, self.total_job_weight)
        norm_e = normalize_score(raw_e, self.total_entrepreneurship_weight)
        norm_h = normalize_score(raw_h, self.total_higher_education_weight)

        self.job_score = norm_j
        self.entrepreneurship_score = norm_e
        self.higher_education_score = norm_h

        profile = classify_career_profile(norm_j, norm_e, norm_h)
        self.profile_result = profile
        self.status = "Submitted"
        return norm_j, norm_e, norm_h, profile

    def before_submit(self):
        self.calculate_scores()

    def on_submit(self):
        norm_j, norm_e, norm_h, profile = self.calculate_scores()
        raw_j, raw_e, raw_h = self.raw_job_score, self.raw_entrepreneurship_score, self.raw_higher_education_score

        frappe.db.set_value("Student Test Screen", self.name, {
            "raw_job_score": raw_j,
            "raw_entrepreneurship_score": raw_e,
            "raw_higher_education_score": raw_h,
            "job_score": norm_j,
            "entrepreneurship_score": norm_e,
            "higher_education_score": norm_h,
            "profile_result": profile,
            "status": "Submitted"
        })

        # Create/Update Submissions & Results
        member_email = self.student or self.owner or frappe.session.user
        valid_user = member_email if frappe.db.exists("User", member_email) else (frappe.session.user if frappe.db.exists("User", frappe.session.user) else "Administrator")

        # 1. Str Psychometric Test Submission
        sub_name = frappe.db.get_value("Str Psychometric Test Submission", {"student_test_screen": self.name})
        if not sub_name:
            sub_doc = frappe.new_doc("Str Psychometric Test Submission")
            sub_doc.student_test_screen = self.name
            sub_doc.psychometric_test = self.test or "Psychometric Career Assessment"
            sub_doc.member = valid_user
        else:
            sub_doc = frappe.get_doc("Str Psychometric Test Submission", sub_name)
            sub_doc.member = valid_user

        sub_doc.score = int(norm_j)
        sub_doc.score_out_of = 100
        sub_doc.percentage = int(norm_j)
        sub_doc.passing_percentage = 50
        sub_doc.total_job_weight = self.total_job_weight
        sub_doc.total_entrepreneurship_weight = self.total_entrepreneurship_weight
        sub_doc.total_higher_education_weight = self.total_higher_education_weight
        sub_doc.raw_job_score = raw_j
        sub_doc.raw_entrepreneurship_score = raw_e
        sub_doc.raw_higher_education_score = raw_h
        sub_doc.job_score = norm_j
        sub_doc.entrepreneurship_score = norm_e
        sub_doc.higher_education_score = norm_h
        sub_doc.profile_type = profile

        sub_doc.set("str_test_response", [])
        for r in self.str_test_response:
            eff_score = float(getattr(r, "effective_score", 0) or 0)
            dim_val = getattr(r, "dimension", None) or getattr(r, "subject", None)
            sub_doc.append("str_test_response", {
                "question": r.question,
                "question_link": r.question_link,
                "response": r.response,
                "mark": int(eff_score),
                "maximum_marks": 2,
                "dimension": dim_val,
                "direction": getattr(r, "direction", "Normal"),
                "effective_score": eff_score,
                "job_weight": float(getattr(r, "job_weight", 0) or 0),
                "entrepreneurship_weight": float(getattr(r, "entrepreneurship_weight", 0) or 0),
                "higher_education_weight": float(getattr(r, "higher_education_weight", 0) or 0),
                "job_contribution": float(getattr(r, "job_contribution", 0) or 0),
                "entrepreneurship_contribution": float(getattr(r, "entrepreneurship_contribution", 0) or 0),
                "higher_education_contribution": float(getattr(r, "higher_education_contribution", 0) or 0),
                "subject": getattr(r, "subject", None)
            })
        sub_doc.save(ignore_permissions=True)


        # 2. Psychometric Result
        res_name = frappe.db.get_value("Psychometric Result", {"student_test_screen": self.name})
        if not res_name:
            res_doc = frappe.new_doc("Psychometric Result")
            res_doc.student_test_screen = self.name
            res_doc.student = valid_user
        else:
            res_doc = frappe.get_doc("Psychometric Result", res_name)
            res_doc.student = valid_user


        res_doc.raw_job_score = raw_j
        res_doc.raw_entrepreneurship_score = raw_e
        res_doc.raw_higher_education_score = raw_h
        res_doc.total_job_weight = self.total_job_weight
        res_doc.total_entrepreneurship_weight = self.total_entrepreneurship_weight
        res_doc.total_higher_education_weight = self.total_higher_education_weight
        res_doc.job_score = norm_j
        res_doc.entrepreneurship_score = norm_e
        res_doc.higher_education_score = norm_h
        res_doc.profile_type = profile
        res_doc.save(ignore_permissions=True)

        # 3. Psychometric Test Instance
        inst_name = frappe.db.get_value("Psychometric Test Instance", {"student_test_screen": self.name})
        if not inst_name:
            inst_doc = frappe.new_doc("Psychometric Test Instance")
            inst_doc.student_test_screen = self.name
            inst_doc.student = valid_user
            inst_doc.total_questions = len(self.str_test_response)
        else:
            inst_doc = frappe.get_doc("Psychometric Test Instance", inst_name)

        inst_doc.question_index = len(self.str_test_response)
        inst_doc.total_job_weight = self.total_job_weight
        inst_doc.total_entrepreneurship_weight = self.total_entrepreneurship_weight
        inst_doc.total_higher_education_weight = self.total_higher_education_weight
        inst_doc.raw_job_score = raw_j
        inst_doc.raw_entrepreneurship_score = raw_e
        inst_doc.raw_higher_education_score = raw_h
        inst_doc.job_score = norm_j
        inst_doc.entrepreneurship_score = norm_e
        inst_doc.higher_education_score = norm_h
        inst_doc.profile_result = profile
        inst_doc.status = "Submitted"
        inst_doc.save(ignore_permissions=True)
        if inst_doc.docstatus == 0:
            inst_doc.flags.ignore_permissions = True
            inst_doc.submit()


        # Update Student DocType is_first_login
        student_name = frappe.db.get_value("Student", {"email_id": member_email})
        if not student_name and frappe.db.exists("Student", member_email):
            student_name = member_email
        if student_name:
            frappe.db.set_value("Student", student_name, "is_first_login", 0)

        frappe.msgprint(f"""
            <b>Psychometric Career Assessment Result</b><br><br>
            💼 <b>Job Inclination Score:</b> {round(norm_j, 1)}/100<br>
            🚀 <b>Entrepreneurship Score:</b> {round(norm_e, 1)}/100<br>
            🎓 <b>Higher Education Score:</b> {round(norm_h, 1)}/100<br><br>
            🌟 <b>Career Inclination Profile:</b> {profile}
        """)
