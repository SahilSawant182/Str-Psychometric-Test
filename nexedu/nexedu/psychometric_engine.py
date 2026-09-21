import frappe
import random
import json

# 15 Master Dimensions Configuration
DIMENSIONS_CONFIG = [
    # Level 1 – Core Discriminators (7 dimensions)
    {"name": "Career Security & Stability", "level": "Level 1 - Core Discriminators", "desc": "Focus on stability, predictable career path, and job security."},
    {"name": "Autonomy & Independence", "level": "Level 1 - Core Discriminators", "desc": "Desire for freedom, self-direction, and decision-making authority."},
    {"name": "Risk & Ambiguity Tolerance", "level": "Level 1 - Core Discriminators", "desc": "Ability to operate comfortably in uncertain or high-risk environments."},
    {"name": "Innovation & Creativity", "level": "Level 1 - Core Discriminators", "desc": "Drive to invent new products, services, or solutions."},
    {"name": "Opportunity Recognition", "level": "Level 1 - Core Discriminators", "desc": "Ability to spot market needs, business gaps, and value creation chances."},
    {"name": "Intellectual Curiosity", "level": "Level 1 - Core Discriminators", "desc": "Deep desire for research, conceptual knowledge, and academic exploration."},
    {"name": "Learning Orientation", "level": "Level 1 - Core Discriminators", "desc": "Commitment to continuous skill acquisition and lifelong education."},
    
    # Level 2 – Supporting Discriminators (6 dimensions)
    {"name": "Achievement Motivation", "level": "Level 2 - Supporting Discriminators", "desc": "Inner drive to reach high standards and accomplish difficult goals."},
    {"name": "Leadership Orientation", "level": "Level 2 - Supporting Discriminators", "desc": "Propensity to guide, inspire, and manage teams or organizations."},
    {"name": "Problem Solving Orientation", "level": "Level 2 - Supporting Discriminators", "desc": "Analytical approach to dissecting and solving complex challenges."},
    {"name": "Persistence & Resilience", "level": "Level 2 - Supporting Discriminators", "desc": "Perseverance in the face of obstacles, failures, or setbacks."},
    {"name": "Long Term Orientation", "level": "Level 2 - Supporting Discriminators", "desc": "Focus on long-term strategy and delayed gratification over quick wins."},
    {"name": "Adaptability & Career Exploration", "level": "Level 2 - Supporting Discriminators", "desc": "Flexibility to pivot, explore diverse roles, and embrace change."},

    # Level 3 – Context Dimensions (2 dimensions)
    {"name": "Structure Preference", "level": "Level 3 - Context Dimensions", "desc": "Preference for established processes, hierarchy, and clear guidelines."},
    {"name": "Social & Professional Orientation", "level": "Level 3 - Context Dimensions", "desc": "Preference for team collaboration, networking, and professional status."}
]

OPTION_SCORE_MAP = {
    "Strongly Agree": 2,
    "Agree": 1,
    "Neutral": 0,
    "Disagree": -1,
    "Strongly Disagree": -2
}

STANDARD_OPTIONS = [
    "Strongly Agree",
    "Agree",
    "Neutral",
    "Disagree",
    "Strongly Disagree"
]

def ensure_master_dimensions():
    """Seeds or verifies the 15 master dimensions in DocTypes."""
    for cfg in DIMENSIONS_CONFIG:
        # 1. Psychometric Dimension
        if frappe.db.exists("Psychometric Dimension", cfg["name"]):
            frappe.db.set_value("Psychometric Dimension", cfg["name"], {
                "importance_level": cfg["level"],
                "description": cfg["desc"]
            })
        else:
            doc = frappe.new_doc("Psychometric Dimension")
            doc.dimension_name = cfg["name"]
            doc.importance_level = cfg["level"]
            doc.description = cfg["desc"]
            doc.insert(ignore_permissions=True)

        # 2. Str Psychometric Subject
        if frappe.db.exists("Str Psychometric Subject", cfg["name"]):
            frappe.db.set_value("Str Psychometric Subject", cfg["name"], {
                "description": cfg["desc"],
                "is_active": 1
            })
        else:
            doc = frappe.new_doc("Str Psychometric Subject")
            doc.subject_name = cfg["name"]
            doc.description = cfg["desc"]
            doc.is_active = 1
            doc.insert(ignore_permissions=True)


def seed_master_questions():
    """Ensures a rich question bank exists for all 15 dimensions across Job, Entrepreneurship, and Higher Ed."""
    ensure_master_dimensions()

    # Pre-defined high-quality question bank templates covering all 15 dimensions
    templates = [
        # Level 1: Career Security & Stability (Job heavy)
        {"text": "I value job security and fixed working hours over high-risk opportunities.", "dim": "Career Security & Stability", "dir": "Normal", "j": 9, "e": 1, "h": 4},
        {"text": "I prefer working for a well-established company with clear career progression.", "dim": "Career Security & Stability", "dir": "Normal", "j": 10, "e": 1, "h": 3},
        {"text": "I dislike financial unpredictability in my career path.", "dim": "Career Security & Stability", "dir": "Normal", "j": 8, "e": 0, "h": 4},
        {"text": "I am willing to take large personal financial risks to build something new.", "dim": "Career Security & Stability", "dir": "Reverse", "j": 2, "e": 9, "h": 3},

        # Level 1: Autonomy & Independence (Entrepreneurship heavy)
        {"text": "I thrive when I have total control over my work schedule and decisions.", "dim": "Autonomy & Independence", "dir": "Normal", "j": 3, "e": 10, "h": 5},
        {"text": "I prefer following established organizational rules rather than making my own rules.", "dim": "Autonomy & Independence", "dir": "Reverse", "j": 8, "e": 1, "h": 3},
        {"text": "I enjoy taking initiative without waiting for instructions or manager approval.", "dim": "Autonomy & Independence", "dir": "Normal", "j": 5, "e": 10, "h": 4},
        {"text": "I work best when a supervisor clearly outlines my daily responsibilities.", "dim": "Autonomy & Independence", "dir": "Reverse", "j": 9, "e": 1, "h": 3},

        # Level 1: Risk & Ambiguity Tolerance (Entrepreneurship heavy)
        {"text": "I am comfortable making important decisions with incomplete information.", "dim": "Risk & Ambiguity Tolerance", "dir": "Normal", "j": 4, "e": 10, "h": 5},
        {"text": "Uncertain outcomes cause me significant stress and anxiety.", "dim": "Risk & Ambiguity Tolerance", "dir": "Reverse", "j": 8, "e": 1, "h": 3},
        {"text": "I view failure as a necessary stepping stone toward innovation.", "dim": "Risk & Ambiguity Tolerance", "dir": "Normal", "j": 4, "e": 9, "h": 6},
        {"text": "I prefer safe choices even if the potential rewards are smaller.", "dim": "Risk & Ambiguity Tolerance", "dir": "Reverse", "j": 9, "e": 1, "h": 4},

        # Level 1: Innovation & Creativity (Entrepreneurship / Higher Ed heavy)
        {"text": "I frequently brainstorm new product ideas or novel business concepts.", "dim": "Innovation & Creativity", "dir": "Normal", "j": 3, "e": 10, "h": 5},
        {"text": "I prefer executing proven solutions over designing untested concepts.", "dim": "Innovation & Creativity", "dir": "Reverse", "j": 9, "e": 2, "h": 3},
        {"text": "I enjoy solving problems by coming up with original, unconventional ideas.", "dim": "Innovation & Creativity", "dir": "Normal", "j": 4, "e": 9, "h": 7},
        {"text": "Routine operational tasks appeal to me more than creative problem solving.", "dim": "Innovation & Creativity", "dir": "Reverse", "j": 9, "e": 1, "h": 2},

        # Level 1: Opportunity Recognition (Entrepreneurship heavy)
        {"text": "I notice unmet customer needs or market gaps in everyday situations.", "dim": "Opportunity Recognition", "dir": "Normal", "j": 3, "e": 10, "h": 4},
        {"text": "I constantly look for ways to turn ideas into commercial value.", "dim": "Opportunity Recognition", "dir": "Normal", "j": 2, "e": 10, "h": 3},
        {"text": "I rarely think about starting my own venture or business service.", "dim": "Opportunity Recognition", "dir": "Reverse", "j": 8, "e": 1, "h": 5},
        {"text": "I am quick to evaluate the economic feasibility of new ideas.", "dim": "Opportunity Recognition", "dir": "Normal", "j": 5, "e": 9, "h": 4},

        # Level 1: Intellectual Curiosity (Higher Ed heavy)
        {"text": "I am fascinated by deep theoretical concepts and academic research.", "dim": "Intellectual Curiosity", "dir": "Normal", "j": 3, "e": 3, "h": 10},
        {"text": "I enjoy reading scholarly articles or literature beyond mandatory coursework.", "dim": "Intellectual Curiosity", "dir": "Normal", "j": 2, "e": 2, "h": 10},
        {"text": "I prefer practical work tasks over theoretical or academic study.", "dim": "Intellectual Curiosity", "dir": "Reverse", "j": 8, "e": 7, "h": 1},
        {"text": "I love exploring underlying principles and root causes behind phenomena.", "dim": "Intellectual Curiosity", "dir": "Normal", "j": 4, "e": 4, "h": 9},

        # Level 1: Learning Orientation (Higher Ed heavy)
        {"text": "Mastering advanced specialized knowledge is more important to me than immediate income.", "dim": "Learning Orientation", "dir": "Normal", "j": 2, "e": 3, "h": 10},
        {"text": "I plan to pursue a Master's or Doctorate degree after graduation.", "dim": "Learning Orientation", "dir": "Normal", "j": 2, "e": 2, "h": 10},
        {"text": "I want to start earning a steady income right after completing my Bachelor's degree.", "dim": "Learning Orientation", "dir": "Reverse", "j": 9, "e": 5, "h": 1},
        {"text": "I actively seek out academic mentorship and specialized research projects.", "dim": "Learning Orientation", "dir": "Normal", "j": 3, "e": 2, "h": 9},

        # Level 2: Achievement Motivation
        {"text": "I set extremely challenging goals for myself and work relentlessly to reach them.", "dim": "Achievement Motivation", "dir": "Normal", "j": 6, "e": 9, "h": 7},
        {"text": "I am satisfied with meeting basic expectations rather than exceeding them.", "dim": "Achievement Motivation", "dir": "Reverse", "j": 4, "e": 1, "h": 3},

        # Level 2: Leadership Orientation
        {"text": "I naturally step forward to lead and coordinate group projects.", "dim": "Leadership Orientation", "dir": "Normal", "j": 7, "e": 9, "h": 5},
        {"text": "I prefer being an individual contributor rather than managing people.", "dim": "Leadership Orientation", "dir": "Reverse", "j": 6, "e": 2, "h": 6},

        # Level 2: Problem Solving Orientation
        {"text": "I approach complex problems in a systematic, step-by-step analytical manner.", "dim": "Problem Solving Orientation", "dir": "Normal", "j": 8, "e": 7, "h": 8},
        {"text": "I tend to rely on intuition rather than detailed analysis when solving issues.", "dim": "Problem Solving Orientation", "dir": "Reverse", "j": 4, "e": 6, "h": 3},

        # Level 2: Persistence & Resilience
        {"text": "When my project encounters severe roadblocks, I double down until it succeeds.", "dim": "Persistence & Resilience", "dir": "Normal", "j": 6, "e": 10, "h": 7},
        {"text": "If a goal becomes too difficult, I am willing to abandon it quickly.", "dim": "Persistence & Resilience", "dir": "Reverse", "j": 4, "e": 1, "h": 3},

        # Level 2: Long Term Orientation
        {"text": "I am willing to sacrifice immediate short-term financial gains for long-term growth.", "dim": "Long Term Orientation", "dir": "Normal", "j": 4, "e": 8, "h": 9},
        {"text": "I prioritize quick short-term earnings over long-term potential.", "dim": "Long Term Orientation", "dir": "Reverse", "j": 8, "e": 4, "h": 2},

        # Level 2: Adaptability & Career Exploration
        {"text": "I enjoy exploring diverse industries and role opportunities before committing.", "dim": "Adaptability & Career Exploration", "dir": "Normal", "j": 6, "e": 8, "h": 6},
        {"text": "I prefer staying on a single, fixed career track without changing paths.", "dim": "Adaptability & Career Exploration", "dir": "Reverse", "j": 8, "e": 2, "h": 5},

        # Level 3: Structure Preference
        {"text": "Clear organizational hierarchies and defined procedures help me perform best.", "dim": "Structure Preference", "dir": "Normal", "j": 9, "e": 1, "h": 5},
        {"text": "Rigid workplace structures make me feel restricted and unmotivated.", "dim": "Structure Preference", "dir": "Reverse", "j": 2, "e": 9, "h": 4},

        # Level 3: Social & Professional Orientation
        {"text": "Building a strong professional network and gaining industry recognition is a top priority.", "dim": "Social & Professional Orientation", "dir": "Normal", "j": 8, "e": 8, "h": 6},
        {"text": "I prefer working independently without needing external validation or networking.", "dim": "Social & Professional Orientation", "dir": "Reverse", "j": 4, "e": 4, "h": 6}
    ]

    # Create/update master questions in Psychometric Question & Str Question
    for idx, t in enumerate(templates, 1):
        level = frappe.db.get_value("Psychometric Dimension", t["dim"], "importance_level") or "Level 1 - Core Discriminators"
        
        # 1. Psychometric Question
        existing_pq = frappe.db.get_value("Psychometric Question", {"question_text": t["text"]})
        if not existing_pq:
            doc = frappe.new_doc("Psychometric Question")
            doc.question_text = t["text"]
            doc.dimension = t["dim"]
            doc.importance_level = level
            doc.direction = t["dir"]
            doc.job_weight = t["j"]
            doc.entrepreneurship_weight = t["e"]
            doc.higher_education_weight = t["h"]
            doc.active = 1
            doc.validation_status = "Approved"
            doc.language = "English"
            doc.exposure_count = 0
            doc.version = 1
            doc.insert(ignore_permissions=True)
        else:
            frappe.db.set_value("Psychometric Question", existing_pq, {
                "dimension": t["dim"],
                "importance_level": level,
                "direction": t["dir"],
                "job_weight": t["j"],
                "entrepreneurship_weight": t["e"],
                "higher_education_weight": t["h"],
                "active": 1,
                "validation_status": "Approved"
            })

        # 2. Str Question
        existing_sq = frappe.db.get_value("Str Question", {"question": t["text"]})
        if not existing_sq:
            doc = frappe.new_doc("Str Question")
            doc.name = f"Psychometric Q - {t['text'][:30]} ({idx})"
            doc.question = t["text"]
            doc.type = "Choices"
            doc.test_subject = t["dim"]
            doc.dimension = t["dim"]
            doc.importance_level = level
            doc.direction = t["dir"]
            doc.job_weight = t["j"]
            doc.entrepreneurship_weight = t["e"]
            doc.higher_education_weight = t["h"]
            doc.is_active = 1
            doc.validation_status = "Approved"
            doc.language = "English"
            doc.no_of_options = "5"
            doc.option_1 = "Strongly Agree"
            doc.option_2 = "Agree"
            doc.option_3 = "Neutral"
            doc.option_4 = "Disagree"
            doc.option_5 = "Strongly Disagree"
            doc.insert(ignore_permissions=True)
        else:
            frappe.db.set_value("Str Question", existing_sq, {
                "test_subject": t["dim"],
                "dimension": t["dim"],
                "importance_level": level,
                "direction": t["dir"],
                "job_weight": t["j"],
                "entrepreneurship_weight": t["e"],
                "higher_education_weight": t["h"],
                "is_active": 1,
                "validation_status": "Approved"
            })


def generate_controlled_test(student_email=None, language="English", test_type=None):
    """
    Controlled Test Generator Engine:
    Selects N questions based on 15 Psychometric Dimensions.
    N is read from Psychometric Settings (total_questions field, default 30).
    """
    ensure_master_dimensions()

    # Get settings FIRST so tot_target_q is available for the seed check below
    settings = frappe.get_single("Psychometric Settings") if frappe.db.exists("DocType", "Psychometric Settings") else None

    outcome_balance_tolerance = getattr(settings, "outcome_balance_tolerance", 35.0) or 35.0
    tot_target_q = int(getattr(settings, "total_questions", 30) or 30)
    l1_k = int(getattr(settings, "level_1_questions_per_dim", 3) or 3)
    l2_k = int(getattr(settings, "level_2_questions_per_dim", 1) or 1)
    l3_total = int(getattr(settings, "level_3_total_questions", 3) or 3)

    # Check if questions exist, seed if missing
    q_count = frappe.db.count("Psychometric Question", {"active": 1, "validation_status": "Approved"})
    if q_count < tot_target_q:
        seed_master_questions()

    attempts = 0
    max_attempts = 10

    while attempts < max_attempts:
        attempts += 1
        selected_questions = []

        # Step 1: Level 1 Dimensions
        l1_dims = frappe.get_all("Psychometric Dimension", filters={"importance_level": "Level 1 - Core Discriminators"}, fields=["name"])
        if len(l1_dims) > 7:
            l1_dims = random.sample(l1_dims, 7)
        for dim in l1_dims:
            d_name = dim["name"]
            qs = frappe.get_all("Psychometric Question", filters={"dimension": d_name, "active": 1, "validation_status": "Approved"}, fields=["*"])
            if not qs:
                qs = frappe.get_all("Str Question", filters={"dimension": d_name, "is_active": 1}, fields=["*"])
            
            if qs:
                k = min(l1_k, len(qs))
                selected_questions.extend(random.sample(qs, k))

        # Step 2: Level 2 Dimensions
        l2_dims = frappe.get_all("Psychometric Dimension", filters={"importance_level": "Level 2 - Supporting Discriminators"}, fields=["name"])
        if len(l2_dims) > 6:
            l2_dims = random.sample(l2_dims, 6)
        for dim in l2_dims:
            d_name = dim["name"]
            qs = frappe.get_all("Psychometric Question", filters={"dimension": d_name, "active": 1, "validation_status": "Approved"}, fields=["*"])
            if not qs:
                qs = frappe.get_all("Str Question", filters={"dimension": d_name, "is_active": 1}, fields=["*"])
            
            if qs:
                k = min(l2_k, len(qs))
                selected_questions.extend(random.sample(qs, k))

        # Step 3: Level 3 Dimensions
        l3_dims = frappe.get_all("Psychometric Dimension", filters={"importance_level": "Level 3 - Context Dimensions"}, fields=["name"])
        if len(l3_dims) > 2:
            l3_dims = random.sample(l3_dims, 2)
        if len(l3_dims) >= 2:
            dim1, dim2 = l3_dims[0]["name"], l3_dims[1]["name"]
            # Dynamically split l3_total across 2 dims (e.g. l3_total=3 → (1,2)/(2,1), l3_total=2 → (1,1))
            half = l3_total // 2
            remainder = l3_total % 2
            split = random.choice([(half + remainder, half), (half, half + remainder)])

            qs1 = frappe.get_all("Psychometric Question", filters={"dimension": dim1, "active": 1, "validation_status": "Approved"}, fields=["*"])
            if not qs1:
                qs1 = frappe.get_all("Str Question", filters={"dimension": dim1, "is_active": 1}, fields=["*"])
            if qs1:
                selected_questions.extend(random.sample(qs1, min(split[0], len(qs1))))

            qs2 = frappe.get_all("Psychometric Question", filters={"dimension": dim2, "active": 1, "validation_status": "Approved"}, fields=["*"])
            if not qs2:
                qs2 = frappe.get_all("Str Question", filters={"dimension": dim2, "is_active": 1}, fields=["*"])
            if qs2:
                selected_questions.extend(random.sample(qs2, min(split[1], len(qs2))))

        # Step 4: Ensure target questions count (tot_target_q)
        if len(selected_questions) > tot_target_q:
            selected_questions = random.sample(selected_questions, tot_target_q)
        elif len(selected_questions) < tot_target_q:
            existing_ids = {q.get("name") for q in selected_questions}
            all_qs = frappe.get_all("Psychometric Question", filters={"active": 1, "validation_status": "Approved"}, fields=["*"])
            if not all_qs:
                all_qs = frappe.get_all("Str Question", filters={"is_active": 1}, fields=["*"])
            available = [q for q in all_qs if q.get("name") not in existing_ids]
            needed = tot_target_q - len(selected_questions)
            if available:
                selected_questions.extend(random.sample(available, min(needed, len(available))))



        # Step 5: Validate Outcome Balance
        total_j = sum(float(q.get("job_weight") or 0) for q in selected_questions)
        total_e = sum(float(q.get("entrepreneurship_weight") or 0) for q in selected_questions)
        total_h = sum(float(q.get("higher_education_weight") or 0) for q in selected_questions)

        max_w = max(total_j, total_e, total_h)
        min_w = min(total_j, total_e, total_h)

        if max_w > 0:
            diff_pct = ((max_w - min_w) / max_w) * 100
        else:
            diff_pct = 0

        if diff_pct <= outcome_balance_tolerance or attempts >= max_attempts:
            break

    # Step 6: Shuffle final question order
    random.shuffle(selected_questions)

    # Calculate final weights
    total_j_weight = sum(float(q.get("job_weight") or 0) for q in selected_questions)
    total_e_weight = sum(float(q.get("entrepreneurship_weight") or 0) for q in selected_questions)
    total_h_weight = sum(float(q.get("higher_education_weight") or 0) for q in selected_questions)

    # Increment exposure_count
    for q in selected_questions:
        q_name = q.get("name")
        if q_name and frappe.db.exists("Psychometric Question", q_name):
            frappe.db.set_value("Psychometric Question", q_name, "exposure_count", (q.get("exposure_count") or 0) + 1)
        elif q_name and frappe.db.exists("Str Question", q_name):
            frappe.db.set_value("Str Question", q_name, "exposure_count", (q.get("exposure_count") or 0) + 1)

    return {
        "questions": selected_questions,
        "total_job_weight": total_j_weight,
        "total_entrepreneurship_weight": total_e_weight,
        "total_higher_education_weight": total_h_weight,
        "random_seed": str(random.randint(100000, 999999))
    }


def calculate_effective_score_and_contributions(question_doc, selected_option):
    """
    Computes effective score (Reverse/Normal) and contributions for Job, Entrepreneurship, and Higher Ed.
    """
    raw_score = OPTION_SCORE_MAP.get(selected_option, 0)
    
    direction = question_doc.get("direction") or "Normal"
    if str(direction).strip().upper() in ["REVERSE", "R"]:
        effective_score = -1 * raw_score
    else:
        effective_score = raw_score

    job_weight = float(question_doc.get("job_weight") or 0)
    entrepreneurship_weight = float(question_doc.get("entrepreneurship_weight") or 0)
    higher_education_weight = float(question_doc.get("higher_education_weight") or 0)

    job_contrib = effective_score * job_weight
    e_contrib = effective_score * entrepreneurship_weight
    h_contrib = effective_score * higher_education_weight

    return {
        "raw_score": raw_score,
        "effective_score": effective_score,
        "job_weight": job_weight,
        "entrepreneurship_weight": entrepreneurship_weight,
        "higher_education_weight": higher_education_weight,
        "job_contribution": job_contrib,
        "entrepreneurship_contribution": e_contrib,
        "higher_education_contribution": h_contrib
    }


def normalize_score(raw_score, total_weight):
    """
    Formula:
    Normalized Score = ((raw_score + 2 * total_weight) / (4 * total_weight)) * 100
    0 = min, 50 = neutral midpoint, 100 = max
    """
    if not total_weight or total_weight <= 0:
        return 50.0
    
    normalized = ((raw_score + 2.0 * total_weight) / (4.0 * total_weight)) * 100.0
    return max(0.0, min(100.0, round(normalized, 2)))


def classify_career_profile(job_score, e_score, h_score):
    """
    Classifies student career inclination into profile types based on normalized scores.
    """
    settings = frappe.get_single("Psychometric Settings") if frappe.db.exists("DocType", "Psychometric Settings") else None
    dominant_threshold = getattr(settings, "dominant_threshold", 10.0) or 10.0
    diff_threshold = getattr(settings, "differentiation_threshold", 5.0) or 5.0

    scores = [
        {"type": "Job", "score": job_score, "label": "Job Dominant"},
        {"type": "Entrepreneurship", "score": e_score, "label": "Entrepreneurship Dominant"},
        {"type": "Higher Education", "score": h_score, "label": "Higher Education Dominant"}
    ]

    scores.sort(key=lambda x: x["score"], reverse=True)

    first = scores[0]
    second = scores[1]
    third = scores[2]

    # Check for low differentiation
    if (first["score"] - third["score"]) <= diff_threshold:
        return "Balanced / Multi-path"

    # Check for single dominant profile
    if (first["score"] - second["score"]) >= dominant_threshold:
        return first["label"]

    # Top two pathways are close -> Dual Profile
    top_types = {first["type"], second["type"]}
    if top_types == {"Job", "Entrepreneurship"}:
        return "Job + Entrepreneurship"
    elif top_types == {"Job", "Higher Education"}:
        return "Job + Higher Education"
    elif top_types == {"Entrepreneurship", "Higher Education"}:
        return "Entrepreneurship + Higher Education"

    return "Balanced / Multi-path"


def import_psychometric_questions_from_file(file_path):
    """
    Imports questions, dimensions, direction, and weights from an Excel (.xlsx/.xls) or CSV (.csv) file.
    Flexible column detection for:
    - Dimension / Subject
    - Direction (N / R / Normal / Reverse)
    - Question / Question Text
    - Job Weight
    - Entrepreneurship Weight
    - Higher Education Weight
    """
    import os
    import pandas as pd

    if not os.path.exists(file_path):
        frappe.throw(f"File not found: {file_path}")

    if file_path.endswith(".csv"):
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)

    # Normalize column headers
    col_map = {}
    for col in df.columns:
        c_str = str(col).strip().lower()
        if "dim" in c_str or "subject" in c_str:
            col_map[col] = "dimension"
        elif "dir" in c_str or c_str in ["n/r", "direction"]:
            col_map[col] = "direction"
        elif "question" in c_str or "text" in c_str:
            col_map[col] = "question"
        elif "job" in c_str:
            col_map[col] = "job_weight"
        elif "entrepreneur" in c_str or "startup" in c_str or "business" in c_str:
            col_map[col] = "entrepreneurship_weight"
        elif "higher" in c_str or "ed" in c_str or "study" in c_str:
            col_map[col] = "higher_education_weight"

    df = df.rename(columns=col_map)

    count = 0
    for idx, row in df.iterrows():
        q_text = str(row.get("question") or "").strip()
        if not q_text or q_text == "nan":
            continue

        dim = str(row.get("dimension") or "General").strip()
        direction_val = str(row.get("direction") or "N").strip().upper()
        direction = "Reverse" if direction_val in ["R", "REVERSE", "-1"] else "Normal"

        try:
            j_weight = float(row.get("job_weight") or 0)
        except Exception:
            j_weight = 0.0

        try:
            e_weight = float(row.get("entrepreneurship_weight") or 0)
        except Exception:
            e_weight = 0.0

        try:
            h_weight = float(row.get("higher_education_weight") or 0)
        except Exception:
            h_weight = 0.0

        # Ensure Dimension exists
        if dim and not frappe.db.exists("Psychometric Dimension", dim):
            d_doc = frappe.new_doc("Psychometric Dimension")
            d_doc.dimension_name = dim
            d_doc.importance_level = "Level 1 - Core Discriminators"
            d_doc.description = f"Master dimension for {dim}"
            d_doc.insert(ignore_permissions=True)

        level = frappe.db.get_value("Psychometric Dimension", dim, "importance_level") or "Level 1 - Core Discriminators"

        # 1. Update/Create Psychometric Question
        existing_pq = frappe.db.get_value("Psychometric Question", {"question_text": q_text})
        if not existing_pq:
            pq = frappe.new_doc("Psychometric Question")
            pq.question_text = q_text
            pq.dimension = dim
            pq.importance_level = level
            pq.direction = direction
            pq.job_weight = j_weight
            pq.entrepreneurship_weight = e_weight
            pq.higher_education_weight = h_weight
            pq.active = 1
            pq.validation_status = "Approved"
            pq.language = "English"
            pq.insert(ignore_permissions=True)
        else:
            frappe.db.set_value("Psychometric Question", existing_pq, {
                "dimension": dim,
                "importance_level": level,
                "direction": direction,
                "job_weight": j_weight,
                "entrepreneurship_weight": e_weight,
                "higher_education_weight": h_weight,
                "active": 1,
                "validation_status": "Approved"
            })

        # 2. Update/Create Str Question
        existing_sq = frappe.db.get_value("Str Question", {"question": q_text})
        if not existing_sq:
            sq = frappe.new_doc("Str Question")
            sq.name = f"Psychometric Q - {q_text[:30]} ({idx+1})"
            sq.question = q_text
            sq.type = "Choices"
            sq.test_subject = dim
            sq.dimension = dim
            sq.importance_level = level
            sq.direction = direction
            sq.job_weight = j_weight
            sq.entrepreneurship_weight = e_weight
            sq.higher_education_weight = h_weight
            sq.is_active = 1
            sq.validation_status = "Approved"
            sq.language = "English"
            sq.no_of_options = "5"
            sq.option_1 = "Strongly Agree"
            sq.option_2 = "Agree"
            sq.option_3 = "Neutral"
            sq.option_4 = "Disagree"
            sq.option_5 = "Strongly Disagree"
            sq.insert(ignore_permissions=True)
        else:
            frappe.db.set_value("Str Question", existing_sq, {
                "test_subject": dim,
                "dimension": dim,
                "importance_level": level,
                "direction": direction,
                "job_weight": j_weight,
                "entrepreneurship_weight": e_weight,
                "higher_education_weight": h_weight,
                "is_active": 1,
                "validation_status": "Approved"
            })

        count += 1

    return count

