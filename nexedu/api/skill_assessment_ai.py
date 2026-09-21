import json
from pathlib import Path
from urllib import error, request

import frappe
from frappe.utils import cint, now_datetime

from nexedu.api.skill_assessment_config import (
    BANK_SIZE,
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GROQ_MODEL_NAME,
    LLM_PROVIDER,
    MODEL_NAME,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL_NAME,
    PASS_SCORE,
    QUESTION_COUNT,
    QUESTION_GENERATION_ATTEMPTS,
    QUESTION_MAX_TOKENS,
    REQUEST_TIMEOUT_SECONDS,
    TEST_QUESTION_COUNT,
    TEST_QUESTION_MIX,
)


PROMPTS_FILE = Path(__file__).with_name("skill_assessment_skills.md")
VALID_LEVELS = {"Beginner", "Intermediate", "Advanced", "Expert"}
ANSWER_KEYS = {"A": 0, "B": 1, "C": 2, "D": 3}
QUESTION_TYPES = {"mcq", "short_answer", "long_answer", "problem_solving"}
QUESTION_TYPE_ALIASES = {
    "multiple_choice": "mcq",
    "multiple_choice_question": "mcq",
    "short": "short_answer",
    "written_answer": "short_answer",
    "open_ended": "long_answer",
    "essay": "long_answer",
    "coding": "problem_solving",
    "coding_problem": "problem_solving",
    "practical": "problem_solving",
}


def _get_cache_fieldname(level):
    mapping = {
        "Beginner": "beginner_questions",
        "Intermediate": "intermediate_questions",
        "Advanced": "advanced_questions",
        "Expert": "expert_questions"
    }
    return mapping.get(level, "beginner_questions")


def _prompt_section(name):
    text = PROMPTS_FILE.read_text(encoding="utf-8")
    marker = "## {0}\n\n```text\n".format(name)
    return text.split(marker, 1)[1].split("\n```", 1)[0].strip()


def _fill_prompt(template, **values):
    for name, value in values.items():
        template = template.replace("{" + name + "}", str(value))
    return template


def _parse_json(raw):
    raw = (raw or "").replace("```json", "").replace("```", "").strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Model did not return JSON")
    return json.loads(raw[start : end + 1], strict=False)


def _get_active_provider():
    try:
        from job_search_ai.services.settings_service import SettingsService
        settings = SettingsService.get()
        if settings and settings.llm_provider:
            return str(settings.llm_provider).lower().strip()
    except Exception:
        pass

    import os
    provider = os.getenv("LLM_PROVIDER")

    if not provider:
        try:
            from nexedu.api.skill_assessment_config import LLM_PROVIDER as CONFIG_LLM_PROVIDER
            provider = CONFIG_LLM_PROVIDER
        except ImportError:
            provider = "ollama"

    return str(provider or "ollama").lower().strip()


def _get_active_model(provider):
    import os
    try:
        from job_search_ai.services.settings_service import SettingsService
        settings = SettingsService.get()
    except Exception:
        settings = None

    if provider == "omniroute":
        model_name = None
        if settings:
            model_name = settings.omniroute_model
        if not model_name:
            model_name = os.getenv("OMNIROUTE_MODEL")
        if not model_name:
            try:
                from nexedu.api.skill_assessment_config import OMNIROUTE_MODEL_NAME
                model_name = OMNIROUTE_MODEL_NAME
            except ImportError:
                model_name = "career-agent"
        return model_name
    elif provider == "groq":
        try:
            from nexedu.api.skill_assessment_config import GROQ_MODEL_NAME
            return GROQ_MODEL_NAME
        except ImportError:
            return "groq/compound"
    else:
        model_name = None
        if settings:
            model_name = settings.default_llm_model
        if not model_name:
            model_name = os.getenv("OLLAMA_MODEL")
        if not model_name:
            try:
                from nexedu.api.skill_assessment_config import OLLAMA_MODEL_NAME
                model_name = OLLAMA_MODEL_NAME
            except ImportError:
                model_name = "qwen3:8b"
        return model_name


def _ollama_chat(prompt, system="JSON only.", max_tokens=1200):
    from nexedu.api.skill_assessment_config import (
        OLLAMA_BASE_URL,
        OLLAMA_MODEL_NAME,
        REQUEST_TIMEOUT_SECONDS,
    )
    import os

    base_url = OLLAMA_BASE_URL
    model_name = OLLAMA_MODEL_NAME

    try:
        from job_search_ai.services.settings_service import SettingsService
        settings = SettingsService.get()
        if settings:
            base_url = settings.ollama_base_url
            model_name = settings.default_llm_model
    except Exception:
        pass

    if os.getenv("OLLAMA_BASE_URL"):
        base_url = os.getenv("OLLAMA_BASE_URL")
    if os.getenv("OLLAMA_MODEL"):
        model_name = os.getenv("OLLAMA_MODEL")

    base_url = base_url.rstrip("/")
    payload = json.dumps(
        {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "think": False,
            "format": "json",
            "options": {"temperature": 0.1, "num_predict": max_tokens},
        }
    ).encode("utf-8")
    api_request = request.Request(
        "{0}/api/chat".format(base_url),
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(api_request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:300]
        raise RuntimeError("Ollama API error ({0}): {1}".format(exc.code, detail))
    except error.URLError as exc:
        raise RuntimeError("Could not connect to Ollama at {0}: {1}".format(base_url, exc.reason))
    except TimeoutError:
        raise RuntimeError("Ollama took too long to respond. Please try again.")

    content = (data.get("message") or {}).get("content")
    if not content:
        raise RuntimeError("Ollama returned an empty response.")
    return content.strip()


def _groq_chat(prompt, system="JSON only.", max_tokens=1200):
    """Call Groq API (OpenAI-compatible endpoint)."""
    payload = json.dumps({
        "model": GROQ_MODEL_NAME,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "stream": False,
    }).encode("utf-8")

    api_request = request.Request(
        "{0}/chat/completions".format(GROQ_BASE_URL.rstrip("/")),
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {0}".format(GROQ_API_KEY),
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
        method="POST",
    )

    try:
        with request.urlopen(api_request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:300]
        raise RuntimeError("Groq API error ({0}): {1}".format(exc.code, detail))
    except error.URLError as exc:
        raise RuntimeError("Could not connect to Groq: {0}".format(exc.reason))
    except TimeoutError:
        raise RuntimeError("Groq took too long to respond. Please try again.")

    choices = data.get("choices") or []
    content = (choices[0].get("message") or {}).get("content") if choices else None
    if not content:
        raise RuntimeError("Groq returned an empty response.")
    return content.strip()


def _omniroute_chat(prompt, system="JSON only.", max_tokens=1200):
    """Call OmniRoute API (OpenAI-compatible endpoint)."""
    from nexedu.api.skill_assessment_config import (
        OMNIROUTE_BASE_URL,
        OMNIROUTE_API_KEY,
        OMNIROUTE_MODEL_NAME,
        REQUEST_TIMEOUT_SECONDS,
    )
    import os

    # Resolve dynamically with fallbacks
    base_url = OMNIROUTE_BASE_URL
    model_name = OMNIROUTE_MODEL_NAME
    api_key = OMNIROUTE_API_KEY

    try:
        from job_search_ai.services.settings_service import SettingsService
        settings = SettingsService.get()
        if settings:
            base_url = settings.omniroute_base_url
            model_name = settings.omniroute_model
    except Exception:
        pass

    # 1. Environment variables
    if os.getenv("OMNIROUTE_BASE_URL"):
        base_url = os.getenv("OMNIROUTE_BASE_URL")
    if os.getenv("OMNIROUTE_API_KEY"):
        api_key = os.getenv("OMNIROUTE_API_KEY")
    if os.getenv("OMNIROUTE_MODEL"):
        model_name = os.getenv("OMNIROUTE_MODEL")

    # 2. Frappe config / settings / site_config.json fallback for key
    if not api_key:
        try:
            if frappe.local and getattr(frappe.local, "initialised", False):
                api_key = frappe.conf.get("omniroute_api_key")
        except Exception:
            pass

    payload = json.dumps({
        "model": model_name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "stream": False,
    }).encode("utf-8")

    api_request = request.Request(
        "{0}/chat/completions".format(base_url.rstrip("/")),
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {0}".format(api_key),
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
        method="POST",
    )

    try:
        with request.urlopen(api_request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:300]
        raise RuntimeError("OmniRoute API error ({0}): {1}".format(exc.code, detail))
    except error.URLError as exc:
        raise RuntimeError("Could not connect to OmniRoute: {0}".format(exc.reason))
    except TimeoutError:
        raise RuntimeError("OmniRoute took too long to respond. Please try again.")

    choices = data.get("choices") or []
    content = (choices[0].get("message") or {}).get("content") if choices else None
    if not content:
        raise RuntimeError("OmniRoute returned an empty response.")
    return content.strip()


def _llm_chat(prompt, system="JSON only.", max_tokens=1200):
    """Route to the active LLM provider resolved dynamically (falling back to config)."""
    provider = _get_active_provider()
    if provider == "omniroute":
        return _omniroute_chat(prompt, system=system, max_tokens=max_tokens)
    if provider == "groq":
        return _groq_chat(prompt, system=system, max_tokens=max_tokens)
    return _ollama_chat(prompt, system=system, max_tokens=max_tokens)


def _normalise_level(level):
    level = (level or "").strip()
    if level.lower() == "exper":
        level = "Expert"
    if level not in VALID_LEVELS:
        frappe.throw("Level must be one of: Beginner, Intermediate, Advanced, Expert")
    return level


def _load_json_value(value, default):
    if value is None:
        return default
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return default
        return json.loads(value)
    return value


def _safe_questions(questions):
    hidden_keys = {"answer", "rubric"}
    return [{key: value for key, value in question.items() if key not in hidden_keys} for question in questions]


def _skill_prompt_name(skill, level):
    return "{0} level {1}".format(level, skill)


def _normalise_answer(answer, options, correct_answer=None):
    answer = str(answer or "").strip()
    if not answer:
        return ""

    # 1. Check if the answer matches A, B, C, D directly
    upper_answer = answer.upper()
    if upper_answer in ANSWER_KEYS:
        return upper_answer

    # 2. Check for formats like "A.", "A)", "A -", "A: ", etc.
    if len(upper_answer) > 1 and upper_answer[0] in ANSWER_KEYS:
        if upper_answer[1] in {".", ")", " ", "-", ":"}:
            return upper_answer[0]

    # 3. Check if correct_answer is provided and the answer text matches the correct option text
    if correct_answer and correct_answer in ANSWER_KEYS:
        correct_index = ANSWER_KEYS[correct_answer]
        if correct_index < len(options):
            correct_opt = str(options[correct_index]).strip().lower()
            if answer.lower() == correct_opt:
                return correct_answer
            if len(correct_opt) > 1 and correct_opt[0].upper() in ANSWER_KEYS and correct_opt[1] in {".", ")", " ", "-", ":"}:
                sub_opt = correct_opt[2:].strip()
                if answer.lower() == sub_opt:
                    return correct_answer

    # 4. Check for case-insensitive matching against option texts
    for index, option in enumerate(options):
        opt_str = str(option).strip().lower()
        if answer.lower() == opt_str:
            return "ABCD"[index]
        
        # Strip option prefixes from options if present (e.g. "A. Option content")
        if len(opt_str) > 1 and opt_str[0].upper() in ANSWER_KEYS and opt_str[1] in {".", ")", " ", "-", ":"}:
            sub_opt = opt_str[2:].strip()
            if answer.lower() == sub_opt:
                return "ABCD"[index]

    return ""


def _normalise_questions(data, level=None):
    if not isinstance(data, dict):
        raise ValueError("Model response must be a JSON object")
    questions = data.get("questions")
    if not isinstance(questions, list) or len(questions) != QUESTION_COUNT:
        count = len(questions) if isinstance(questions, list) else 0
        raise ValueError("Model returned {0} questions; expected {1}".format(count, QUESTION_COUNT))

    normalised = []
    for index, item in enumerate(questions, 1):
        if not isinstance(item, dict):
            raise ValueError("Model returned an invalid question at index {0}".format(index))
        question_text = item.get("q") or item.get("question") or item.get("text")
        options = item.get("o") or item.get("options") or item.get("choices")
        question_type = str(item.get("type") or item.get("question_type") or "mcq").strip().lower()
        question_type = question_type.replace(" ", "_").replace("-", "_")
        question_type = QUESTION_TYPE_ALIASES.get(question_type, question_type)
        if question_type not in QUESTION_TYPES:
            question_type = "mcq" if options else "short_answer"
        if options is None:
            options = []
        raw_answer = item.get("a") or item.get("answer") or item.get("correct_answer") or ""
        answer = _normalise_answer(raw_answer, options or []) if question_type == "mcq" else ""
        rubric = item.get("rubric") or item.get("expected_answer") or item.get("answer_key") or ""
        difficulty = item.get("d") or item.get("difficulty") or "medium"
        if not isinstance(question_text, str) or not isinstance(options, list):
            raise ValueError("Model returned an invalid question at index {0}".format(index))
        if question_type == "mcq" and (len(options) != 4 or not answer):
            raise ValueError("Model returned an invalid MCQ at index {0}".format(index))
        if question_type == "mcq":
            cleaned_opts = []
            for opt in options:
                opt_str = str(opt).strip().lower()
                if len(opt_str) > 1 and opt_str[0] in "abcd" and opt_str[1] in {".", ")", " ", "-", ":"}:
                    opt_str = opt_str[2:].strip()
                cleaned_opts.append(opt_str)
            if len(set(cleaned_opts)) < len(options):
                raise ValueError("Model returned duplicate MCQ options at index {0}".format(index))
        if question_type != "mcq" and not str(rubric).strip():
            rubric = str(raw_answer).strip() or (
                "Evaluate technical correctness, completeness, reasoning, and practical relevance "
                "for the question. Accept equivalent valid approaches."
            )
        normalised.append(
            {
                "index": index,
                "type": question_type,
                "question": question_text.strip(),
                "options": [str(option).strip() for option in options],
                "answer": answer,
                "rubric": str(rubric).strip(),
                "difficulty": str(difficulty).strip().lower(),
                "source": "ollama",
            }
        )

    if level:
        mcq_count = sum(1 for q in normalised if q["type"] == "mcq")
        desc_count = len(normalised) - mcq_count
        if level == "Beginner" and (mcq_count != 5 or desc_count != 0):
            raise ValueError("Beginner level must have exactly 5 MCQs.")
        elif level == "Intermediate" and (mcq_count != 4 or desc_count != 1):
            raise ValueError("Intermediate level must have exactly 4 MCQs and 1 descriptive question.")
        elif level == "Advanced" and (mcq_count != 3 or desc_count != 2):
            raise ValueError("Advanced level must have exactly 3 MCQs and 2 descriptive questions.")

    return normalised


def _generate_questions(skill, level):
    """Generate a batch of QUESTION_COUNT questions for the given skill/level."""
    # Batch mix: how many MCQs vs descriptive per QUESTION_COUNT=5 batch
    batch_mix = {
        "Beginner":     "Generate exactly 5 'mcq' questions and 0 descriptive questions.",
        "Intermediate": "Generate exactly 4 'mcq' questions and exactly 1 descriptive question (use 'short_answer' or 'problem_solving' type).",
        "Advanced":     "Generate exactly 3 'mcq' questions and exactly 2 descriptive questions (use 'long_answer' or 'problem_solving' type).",
        "Expert":       "Generate exactly 1 'mcq' question and exactly 4 descriptive questions (use 'long_answer' or 'problem_solving' type).",
    }
    mix_instruction = batch_mix.get(level, batch_mix["Beginner"])

    prompt = _fill_prompt(
        _prompt_section("Quiz prompt"),
        skill=skill,
        level=level,
        question_count=QUESTION_COUNT,
        mix_instruction=mix_instruction
    )
    last_error = None
    fallback_questions = None
    for attempt in range(QUESTION_GENERATION_ATTEMPTS):
        try:
            response = _llm_chat(prompt, max_tokens=QUESTION_MAX_TOKENS)
            raw_parsed = _normalise_questions(_parse_json(response))
            fallback_questions = raw_parsed
            normalised = _normalise_questions(_parse_json(response), level)
            return normalised
        except Exception as exc:
            last_error = exc
            continue

    if fallback_questions:
        return fallback_questions
    frappe.throw("Model failed to return valid questions after {0} attempts: {1}".format(QUESTION_GENERATION_ATTEMPTS, last_error))


def _get_skill_syllabus_topics(skill, level):
    """Read the learning_points_json field from the Skill master and return a flat list of topic strings for the given level."""
    try:
        skill_doc = frappe.get_doc("Skill", skill)
        raw = getattr(skill_doc, "learning_points_json", None) or ""
        if not raw:
            return []
        data = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(data, dict):
            # Structure: {"Beginner": [...], "Intermediate": [...], "Advanced": [...]}
            return [str(t) for t in (data.get(level) or [])]
        if isinstance(data, list):
            return [str(t) for t in data]
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Skill Syllabus Topics Load Error")
    return []


def _build_bank_prompt(skill, level, topics, batch_num):
    """Build a generation prompt that anchors question generation to a specific set of syllabus topics."""
    batch_mix = {
        "Beginner":     "Generate exactly 5 'mcq' questions and 0 descriptive questions.",
        "Intermediate": "Generate exactly 4 'mcq' questions and exactly 1 descriptive question (use 'short_answer' or 'problem_solving' type).",
        "Advanced":     "Generate exactly 3 'mcq' questions and exactly 2 descriptive questions (use 'long_answer' or 'problem_solving' type).",
        "Expert":       "Generate exactly 1 'mcq' question and exactly 4 descriptive questions (use 'long_answer' or 'problem_solving' type).",
    }
    mix_instruction = batch_mix.get(level, batch_mix["Beginner"])

    if topics:
        topic_hint = " Focus questions ONLY on these specific topics: {0}.".format(", ".join(topics[:6]))
    else:
        topic_hint = ""

    base_prompt = _prompt_section("Quiz prompt")
    return _fill_prompt(
        base_prompt,
        skill=skill,
        level=level,
        question_count=QUESTION_COUNT,
        mix_instruction=mix_instruction + topic_hint,
    )


def _safe_db_reconnect():
    """Reconnect to MySQL if the connection was lost (OperationalError 2013)."""
    try:
        frappe.db.connect()
    except Exception:
        pass


def _bank_count(skill, level):
    """Return the number of active questions currently in the bank for this skill+level."""
    try:
        return frappe.db.count("Skill Question Bank", {
            "skill": skill,
            "level": level,
            "is_active": 1,
        })
    except Exception as e:
        if "2013" in str(e) or "Lost connection" in str(e):
            _safe_db_reconnect()
            return frappe.db.count("Skill Question Bank", {
                "skill": skill,
                "level": level,
                "is_active": 1,
            })
        raise


def _save_batch_to_bank(skill, level, questions, batch_label):
    """Persist a list of normalised question dicts to the Skill Question Bank doctype."""
    for q in questions:
        doc = frappe.get_doc({
            "doctype": "Skill Question Bank",
            "skill": skill,
            "level": level,
            "question_type": q["type"],
            "difficulty": q.get("difficulty") or "medium",
            "topic": "",
            "is_active": 1,
            "generation_batch": batch_label,
            "question_text": q["question"],
            "options": json.dumps(q.get("options") or []),
            "correct_answer": q.get("answer") or "",
            "rubric": q.get("rubric") or "",
        })
        doc.insert(ignore_permissions=True)
    frappe.db.commit()


@frappe.whitelist()
def generate_question_bank(skill=None, level=None):
    """
    Background-safe function that fills the Skill Question Bank with BANK_SIZE questions
    for the given skill and level. Uses learning_points as topic anchors for diversity.
    Can be called via API or via bench execute for a single skill/level.
    """
    import time
    skill = (skill or "").strip()
    level = _normalise_level(level)
    if not skill:
        frappe.throw("Skill is required.")

    target = BANK_SIZE  # 50
    current = _bank_count(skill, level)
    if current >= target:
        return {"message": "Bank already full ({0}/{1}).".format(current, target)}

    # Load syllabus topics
    all_topics = _get_skill_syllabus_topics(skill, level)
    topic_groups = []
    if all_topics:
        # Spread topics evenly across batches to ensure diversity
        num_batches = (target - current + QUESTION_COUNT - 1) // QUESTION_COUNT
        chunk_size = max(1, len(all_topics) // max(1, num_batches))
        for i in range(0, len(all_topics), chunk_size):
            topic_groups.append(all_topics[i:i + chunk_size])

    batch_num = 0
    while _bank_count(skill, level) < target:
        batch_num += 1
        topics = topic_groups[batch_num % len(topic_groups)] if topic_groups else []
        batch_label = "batch-{0}".format(batch_num)

        try:
            prompt = _build_bank_prompt(skill, level, topics, batch_num)
            response = _llm_chat(prompt, max_tokens=QUESTION_MAX_TOKENS)
            questions = _normalise_questions(_parse_json(response))
            _save_batch_to_bank(skill, level, questions, batch_label)
        except Exception as exc:
            # Reconnect if MySQL dropped the connection (memory pressure / long-running job)
            if "2013" in str(exc) or "Lost connection" in str(exc):
                _safe_db_reconnect()
            # Safely log the error — frappe_whatsapp hook can also fail if DB is down,
            # so we must not let log_error propagate and crash the RQ worker.
            try:
                frappe.log_error(
                    frappe.get_traceback(),
                    "Question Bank Generation Error ({0} {1} batch {2})".format(skill, level, batch_num)
                )
            except Exception:
                pass  # Never let log_error crash the worker
            if batch_num > (target // QUESTION_COUNT) * 3:
                break  # Safety: give up after 3x the expected batches

        time.sleep(1)

    final_count = _bank_count(skill, level)
    return {"message": "Bank for {0} ({1}) now has {2} questions.".format(skill, level, final_count)}


def _get_bank_questions(skill, level):
    """
    Randomly select TEST_QUESTION_COUNT questions from the Skill Question Bank,
    maintaining the correct MCQ/descriptive mix for the given level.
    Returns a list of normalised question dicts, or None if the bank is too small.
    """
    import random

    mix = TEST_QUESTION_MIX.get(level, {"mcq": TEST_QUESTION_COUNT, "descriptive": 0})
    n_mcq = mix["mcq"]
    n_desc = mix["descriptive"]

    # Fetch all active MCQ and descriptive questions separately
    mcq_rows = frappe.get_all(
        "Skill Question Bank",
        filters={"skill": skill, "level": level, "is_active": 1, "question_type": "mcq"},
        fields=["name", "question_type", "question_text", "options", "correct_answer", "rubric", "difficulty"],
    )
    desc_rows = frappe.get_all(
        "Skill Question Bank",
        filters={"skill": skill, "level": level, "is_active": 1, "question_type": ["not in", ["mcq"]]},
        fields=["name", "question_type", "question_text", "options", "correct_answer", "rubric", "difficulty"],
    )

    if len(mcq_rows) < n_mcq or (n_desc > 0 and len(desc_rows) < n_desc):
        return None  # Bank too small — fall back to live generation

    selected_mcq = random.sample(mcq_rows, n_mcq)
    selected_desc = random.sample(desc_rows, n_desc) if n_desc > 0 else []
    combined = selected_mcq + selected_desc
    random.shuffle(combined)

    # Convert to the normalised question dict format
    result = []
    for idx, row in enumerate(combined, 1):
        try:
            opts = json.loads(row.get("options") or "[]")
        except Exception:
            opts = []
        result.append({
            "index": idx,
            "type": row["question_type"],
            "question": row["question_text"],
            "options": opts,
            "answer": row.get("correct_answer") or "",
            "rubric": row.get("rubric") or "",
            "difficulty": row.get("difficulty") or "medium",
            "source": "bank",
        })
    return result



def _answers_to_list(answers, questions):
    answers = _load_json_value(answers, [])
    if isinstance(answers, dict):
        values = []
        for index, question in enumerate(questions, 1):
            question_text = question.get("question") or ""
            if question_text in answers:
                values.append(answers[question_text])
            else:
                values.append(answers.get(str(index), answers.get(index, "")))
        return values
    if isinstance(answers, list):
        return answers
    frappe.throw("Answers must be a list or dict.")


def _question_type_from_text(question):
    first_word = question.strip().split(" ", 1)[0].lower()
    if first_word in {"build", "create", "design", "develop", "implement", "solve", "write"}:
        return "problem_solving"
    return "long_answer"


def _build_submission(student, skill, level, answers):
    try:
        answers = _load_json_value(answers, {})
    except json.JSONDecodeError:
        frappe.throw("Answers must be a complete, valid JSON question-to-answer dict.")
    if not isinstance(answers, dict) or not answers:
        frappe.throw("Answers must be a non-empty question-to-answer dict.")

    questions = []
    answer_map = {}
    for index, (question_text, submitted) in enumerate(answers.items(), 1):
        question_text = str(question_text or "").strip()
        if not question_text:
            frappe.throw("Every submitted answer must include its question text.")

        question_type = _question_type_from_text(question_text)
        options = []
        if isinstance(submitted, dict):
            selected = submitted.get("answer", submitted.get("student_answer", ""))
            requested_type = str(submitted.get("type") or "").strip().lower().replace("-", "_").replace(" ", "_")
            requested_type = QUESTION_TYPE_ALIASES.get(requested_type, requested_type)
            if requested_type in QUESTION_TYPES:
                question_type = requested_type
            if isinstance(submitted.get("options"), list):
                options = [str(option).strip() for option in submitted["options"]]
        else:
            selected = submitted

        questions.append(
            {
                "index": index,
                "type": question_type,
                "question": question_text,
                "options": options,
                "answer": "",
                "rubric": (
                    "Evaluate technical correctness, completeness, reasoning, and practical relevance. "
                    "Accept equivalent valid approaches."
                ),
                "difficulty": "hard" if level in {"Advanced", "Expert"} else "medium",
                "source": "submitted",
            }
        )
        answer_map[question_text] = selected

    return {
        "student": student,
        "skill": skill,
        "level": level,
        "questions": questions,
        "model": _get_active_model(_get_active_provider()),
    }, answer_map


def _evaluate_written_answers(assessment, descriptive_items):
    if not descriptive_items:
        return {}

    input_list = []
    for item in descriptive_items:
        question_text = item["question"]
        if item.get("options"):
            question_text = "{0} Options: {1}".format(question_text, "; ".join(item["options"]))
        input_list.append({
            "index": item["index"],
            "question_type": item["type"],
            "question": question_text,
            "rubric": item.get("rubric") or "",
            "student_answer": item["selected"]
        })

    prompt = _fill_prompt(
        _prompt_section("Evaluation prompt"),
        skill=assessment["skill"],
        level=assessment["level"],
        input_data=json.dumps(input_list),
        pass_score=PASS_SCORE,
    )

    try:
        raw = _llm_chat(prompt, max_tokens=1500)
        data = _parse_json(raw)
        evals = data.get("evaluations") or []

        results = {}
        for ev in evals:
            idx = ev.get("index")
            score = float(ev.get("score", 0) or 0)
            score = max(0, min(100, score))

            # Use ONLY the numeric score as the source of truth.
            # The LLM often contradicts itself by giving a low score but setting
            # is_correct=true. We ignore is_correct entirely and trust the score.
            if score >= PASS_SCORE:
                final_score = 100.0
                final_is_correct = True
            else:
                final_score = score
                final_is_correct = False

            results[idx] = {
                "answer_score": final_score,
                "is_correct": final_is_correct,
                "evaluation_comment": str(ev.get("comment") or "").strip(),
            }
        return results
    except Exception as exc:
        frappe.log_error(frappe.get_traceback(), "Skill Assessment Batch Evaluation Error")
        results = {}
        for item in descriptive_items:
            results[item["index"]] = {
                "answer_score": 0.0,
                "is_correct": False,
                "evaluation_comment": "Evaluation failed: {0}".format(exc),
            }
        return results




def _score_questions(assessment, answers):
    questions = assessment["questions"]
    answers = _answers_to_list(answers, questions)
    if len(answers) != len(questions):
        frappe.throw("Expected {0} answers.".format(len(questions)))

    descriptive_items = []
    for question, answer in zip(questions, answers):
        selected = str(answer or "").strip()
        if not (question.get("type") == "mcq" and question.get("answer")):
            descriptive_items.append({
                "index": question["index"],
                "type": question["type"],
                "question": question["question"],
                "options": question.get("options") or [],
                "rubric": question.get("rubric") or "",
                "selected": selected
            })

    batch_results = {}
    if descriptive_items:
        batch_results = _evaluate_written_answers(assessment, descriptive_items)

    breakdown = []
    for question, answer in zip(questions, answers):
        selected = str(answer or "").strip()
        if question.get("type") == "mcq" and question.get("answer"):
            selected = _normalise_answer(selected, question.get("options") or [], question.get("answer"))
            answer_score = 100 if selected == question["answer"] else 0
            correct = answer_score == 100
            evaluation_comment = ""
        else:
            res = batch_results.get(question["index"]) or {
                "answer_score": 0.0,
                "is_correct": False,
                "evaluation_comment": "Evaluation missing"
            }
            answer_score = res["answer_score"]
            correct = res["is_correct"]
            evaluation_comment = res["evaluation_comment"]

        breakdown.append(
            {
                "index": question.get("index"),
                "type": question.get("type"),
                "question": question["question"],
                "selected_answer": selected,
                "correct_answer": question["answer"] if question.get("type") == "mcq" else "",
                "answer_score": answer_score,
                "is_correct": correct,
                "evaluation_comment": evaluation_comment,
                "difficulty": question.get("difficulty"),
            }
        )

    total_correct = sum(1 for item in breakdown if item["is_correct"])
    score = round(sum(item["answer_score"] for item in breakdown) / len(questions), 2) if questions else 0
    passed = score >= PASS_SCORE
    return {
        "score": score,
        "passed": passed,
        "verification_status": "Pass" if passed else "Fail",
        "total_correct": total_correct,
        "total_questions": len(questions),
        "pass_score": PASS_SCORE,
        "breakdown": breakdown,
    }


def _result_feedback(assessment, scores):
    questions = assessment["questions"]
    correct_topics = "; ".join(
        question["question"] for question, result in zip(questions, scores["breakdown"]) if result["is_correct"]
    ) or "none"
    missed_topics = "; ".join(
        question["question"] for question, result in zip(questions, scores["breakdown"]) if not result["is_correct"]
    ) or "none"

    # Fully deterministic programmatic feedback — ZERO LLM CALLS
    # This cuts verification time in half.
    skill = _skill_prompt_name(assessment["skill"], assessment["level"])
    passed = scores["passed"]
    feedback = {
        "summary": "You scored {score}% on the {skill} quiz.".format(
            score=scores["score"], skill=skill
        ),
        "strengths": [correct_topics] if correct_topics != "none" else [],
        "gaps": [missed_topics] if missed_topics != "none" else [],
        "next_step": (
            "Well done! Move on to the next level."
            if passed
            else "Review the missed topics and try again."
        ),
        "status": "verified" if passed else "not_verified",
    }
    return feedback



def _student_exists(student):
    if not frappe.db.exists("Student", student):
        frappe.throw("Student not found: {0}".format(student))


def _store_skill_test(assessment, scores, feedback, answers):
    answer_list = _answers_to_list(answers, assessment["questions"])
    question_type_counts = {}
    for question in assessment["questions"]:
        question_type = question.get("type") or "question"
        question_type_counts[question_type] = question_type_counts.get(question_type, 0) + 1

    test_result = {
        "attempt": {
            "submitted_at": str(now_datetime()),
            "model": _get_active_model(_get_active_provider()),
            "student": assessment["student"],
            "skill": assessment["skill"],
            "level": assessment["level"],
            "question_count": len(assessment["questions"]),
            "question_type_counts": question_type_counts,
        },
        "result": {
            "score": scores["score"],
            "status": scores["verification_status"],
            "passed": scores["passed"],
            "pass_score": PASS_SCORE,
            "total_correct": scores["total_correct"],
            "total_questions": scores["total_questions"],
        },
        "ai_response": feedback,
        "student_answers": answer_list,
        "questions": assessment["questions"],
        "evaluation_breakdown": scores["breakdown"],
    }
    attempts = frappe.db.count(
        "Skill Test",
        filters={
            "student": assessment["student"],
            "skill_name": assessment["skill"],
            "level": assessment["level"],
        },
    )
    doc = frappe.get_doc(
        {
            "doctype": "Skill Test",
            "naming_series": "ST-.YYYY.-",
            "student": assessment["student"],
            "skill_name": assessment["skill"],
            "level": assessment["level"],
            "score": scores["score"],
            "status": scores["verification_status"],
            "attempts": cint(attempts) + 1,
            "test_result": json.dumps(test_result, indent=2),
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def get_skill_test_questions(student=None, skill=None, level=None):
    student = (student or "").strip()
    skill = (skill or "").strip()
    level = _normalise_level(level)
    if not student:
        frappe.throw("Student is required.")
    if not skill:
        frappe.throw("Skill is required.")
    _student_exists(student)

    # -----------------------------------------------------------------------
    # Priority 1: Pull TEST_QUESTION_COUNT random questions from the Question Bank.
    # This ensures every student gets a unique, randomised set.
    # -----------------------------------------------------------------------
    questions = _get_bank_questions(skill, level)

    # -----------------------------------------------------------------------
    # Priority 2 (Fallback): Old Skill Assessment Cache — 5 fixed questions.
    # Used when the bank is not yet populated for this skill+level.
    # -----------------------------------------------------------------------
    if not questions:
        cache_name = skill.strip().lower()
        fieldname = _get_cache_fieldname(level)
        cached_questions_json = None
        if frappe.db.exists("Skill Assessment Cache", cache_name):
            cached_questions_json = frappe.db.get_value("Skill Assessment Cache", cache_name, fieldname)
        if cached_questions_json:
            try:
                questions = json.loads(cached_questions_json)
            except Exception:
                frappe.log_error(frappe.get_traceback(), "Skill Assessment Cache Parse Error")

    # -----------------------------------------------------------------------
    # Priority 3: Generate live (triggers bank fill in background).
    # -----------------------------------------------------------------------
    if not questions:
        try:
            questions = _generate_questions(skill, level)
            # Also kick off background bank population so next time we serve from bank
            frappe.enqueue(
                "nexedu.api.skill_assessment_ai.generate_question_bank",
                queue="long",
                timeout=43200,
                skill=skill,
                level=level,
                now=frappe.flags.in_test,
            )
            # Also save to legacy cache for immediate subsequent requests
            cache_name = skill.strip().lower()
            fieldname = _get_cache_fieldname(level)
            if frappe.db.exists("Skill Assessment Cache", cache_name):
                cache_doc = frappe.get_doc("Skill Assessment Cache", cache_name)
                cache_doc.set(fieldname, json.dumps(questions))
                cache_doc.save(ignore_permissions=True)
            else:
                cache_doc = frappe.get_doc({
                    "doctype": "Skill Assessment Cache",
                    "skill": skill,
                    fieldname: json.dumps(questions)
                })
                cache_doc.insert(ignore_permissions=True)
            frappe.db.commit()
        except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
            frappe.log_error(frappe.get_traceback(), "Skill Assessment Question Error")
            frappe.throw("Could not generate skill test questions: {0}".format(exc))

    safe_questions = _safe_questions(questions)
    return {
        "name": student,
        "skill": skill,
        "level": level,
        "no_of_questions": len(safe_questions),
        "questions": safe_questions,
    }




@frappe.whitelist()
def submit_skill_test_answers(student=None, skill=None, level=None, answers=None):
    student = (student or "").strip()
    skill = (skill or "").strip()
    level = _normalise_level(level)
    if not student:
        frappe.throw("Student is required.")
    if not skill:
        frappe.throw("Skill is required.")
    _student_exists(student)
    assessment, answers = _build_submission(student, skill, level, answers)

    # Enrich submitted questions with metadata (correct answer keys, rubrics, types, options).
    # Priority 1: Question Bank (new architecture)
    # Priority 2: Legacy Skill Assessment Cache
    bank_map = {}
    try:
        bank_rows = frappe.get_all(
            "Skill Question Bank",
            filters={"skill": skill, "level": level, "is_active": 1},
            fields=["question_text", "question_type", "options", "correct_answer", "rubric", "difficulty"],
        )
        for row in bank_rows:
            try:
                opts = json.loads(row.get("options") or "[]")
            except Exception:
                opts = []
            bank_map[row["question_text"].strip().lower()] = {
                "type": row["question_type"],
                "options": opts,
                "answer": row.get("correct_answer") or "",
                "rubric": row.get("rubric") or "",
                "difficulty": row.get("difficulty") or "medium",
            }
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Question Bank Load in Submission Error")

    # Legacy cache fallback
    cache_map = {}
    cache_name = skill.strip().lower()
    fieldname = _get_cache_fieldname(level)
    if frappe.db.exists("Skill Assessment Cache", cache_name):
        cached_questions_json = frappe.db.get_value("Skill Assessment Cache", cache_name, fieldname)
        if cached_questions_json:
            try:
                cached_questions = json.loads(cached_questions_json)
                cache_map = {q["question"].strip().lower(): q for q in cached_questions}
            except Exception:
                frappe.log_error(frappe.get_traceback(), "Skill Assessment Cache Load in Submission Error")

    for q in assessment.get("questions", []):
        q_text = q["question"].strip().lower()
        source = bank_map.get(q_text) or cache_map.get(q_text)
        if source:
            q["answer"] = source.get("answer") or ""
            q["rubric"] = source.get("rubric") or q["rubric"]
            q["difficulty"] = source.get("difficulty") or q["difficulty"]
            q["type"] = source.get("type") or q["type"]
            if source.get("options"):
                q["options"] = [str(opt).strip() for opt in source["options"]]



    # -----------------------------------------------------------------------
    # Phase 1: Instant MCQ scoring (pure Python, zero LLM calls).
    # Descriptive answers get a placeholder score — background job evaluates them.
    # -----------------------------------------------------------------------
    questions = assessment["questions"]
    answers_list = _answers_to_list(answers, questions)

    breakdown = []
    descriptive_items = []

    for question, answer in zip(questions, answers_list):
        selected = str(answer or "").strip()
        correct_answer_key = question.get("answer") or ""
        q_type = question.get("type") or ""

        # Treat as MCQ when the cache gave us an answer key AND
        # the type is "mcq" OR the student submitted a letter choice (A/B/C/D).
        is_mcq = bool(correct_answer_key) and (
            q_type == "mcq" or _is_mcq_answer(selected)
        )

        if is_mcq:
            selected_norm = _normalise_answer(selected, question.get("options") or [], correct_answer_key)
            answer_score = 100.0 if selected_norm == correct_answer_key else 0.0
            breakdown.append({
                "index": question.get("index"),
                "type": "mcq",
                "question": question["question"],
                "selected_answer": selected_norm,
                "correct_answer": correct_answer_key,
                "answer_score": answer_score,
                "is_correct": answer_score == 100.0,
                "evaluation_comment": "",
                "difficulty": question.get("difficulty"),
            })
        else:
            # Descriptive — placeholder score until background job runs
            breakdown.append({
                "index": question.get("index"),
                "type": q_type or "long_answer",
                "question": question["question"],
                "selected_answer": selected,
                "correct_answer": "",
                "answer_score": 0.0,
                "is_correct": False,
                "evaluation_comment": "Pending AI evaluation.",
                "difficulty": question.get("difficulty"),
            })
            descriptive_items.append({
                "index": question.get("index"),
                "type": q_type or "long_answer",
                "question": question["question"],
                "options": question.get("options") or [],
                "rubric": question.get("rubric") or "",
                "selected": selected,
            })

    mcq_correct = sum(1 for item in breakdown if item["is_correct"])
    preliminary_score = round(
        sum(item["answer_score"] for item in breakdown) / len(questions), 2
    ) if questions else 0.0
    preliminary_passed = preliminary_score >= PASS_SCORE

    scores = {
        "score": preliminary_score,
        "passed": preliminary_passed,
        "verification_status": "Pass" if preliminary_passed else "Fail",
        "total_correct": mcq_correct,
        "total_questions": len(questions),
        "pass_score": PASS_SCORE,
        "breakdown": breakdown,
    }

    feedback = {
        "summary": "Your answers have been submitted. AI evaluation is in progress.",
        "strengths": [],
        "gaps": [],
        "next_step": "Check back shortly for your final score and personalised feedback.",
        "status": "pending",
        "feedback_status": "pending",
    }

    skill_test = _store_skill_test(assessment, scores, feedback, answers)

    # -----------------------------------------------------------------------
    # Phase 2: Run evaluation and finalization synchronously in the request.
    # This blocks the response until the LLM responds, but guarantees
    # that the user gets the finalized results immediately.
    # -----------------------------------------------------------------------
    evaluate_and_finalise_skill_test(
        skill_test_name=skill_test,
        assessment=assessment,
        answers=answers,
        descriptive_items=descriptive_items,
        breakdown=breakdown,
        student=student,
        skill=skill,
        level=level,
    )

    # Fetch the finalized Skill Test record to return the correct score, status, and feedback.
    doc = frappe.get_doc("Skill Test", skill_test)
    result_data = json.loads(doc.test_result or "{}")
    ai_response = result_data.get("ai_response") or {}
    result = result_data.get("result") or {}
    final_breakdown = result_data.get("evaluation_breakdown") or []

    return {
        "skill_test": skill_test,
        "name": doc.student,
        "student": doc.student,
        "skill": doc.skill_name,
        "level": doc.level,
        "score": doc.score,
        "status": doc.status,
        "verification_status": doc.status,
        "passed": result.get("passed", False),
        "pass_score": PASS_SCORE,
        "total_correct": result.get("total_correct", 0),
        "total_questions": len(questions),
        "feedback": ai_response,
        "feedback_status": ai_response.get("feedback_status", "ready"),
        "question_answers": [
            {
                "question": item["question"],
                "answer": item["selected_answer"],
                "type": item["type"],
            }
            for item in final_breakdown
        ],
        "breakdown": final_breakdown,
    }


@frappe.whitelist()
def start_skill_test(student=None, skill=None, level=None):
    return get_skill_test_questions(student=student, skill=skill, level=level)


@frappe.whitelist()
def submit_skill_test(student=None, skill=None, level=None, answers=None):
    return submit_skill_test_answers(
        student=student,
        skill=skill,
        level=level,
        answers=answers,
    )


def evaluate_and_finalise_skill_test(
    skill_test_name, assessment, answers, descriptive_items, breakdown, student, skill, level
):
    """
    Background job:
    1. Evaluates descriptive answers via a single batched LLM call.
    2. Recomputes final score merging MCQ + descriptive results.
    3. Generates LLM feedback summary.
    4. Updates Student Skill if the student passed.
    5. Saves everything back to the Skill Test doc.
    """
    # Step 1 — evaluate descriptive answers with a single batched LLM call
    if descriptive_items:
        try:
            batch_results = _evaluate_written_answers(assessment, descriptive_items)
            for item in breakdown:
                if item.get("evaluation_comment") == "Pending AI evaluation.":
                    res = batch_results.get(item["index"]) or {}
                    item["answer_score"] = float(res.get("answer_score", 0) or 0)
                    item["is_correct"] = bool(res.get("is_correct", False))
                    item["evaluation_comment"] = str(res.get("evaluation_comment", "")).strip()
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Skill Assessment BG Evaluation Error")

    # Step 2 — recompute final score with descriptive results included
    questions = assessment["questions"]
    total_correct = sum(1 for item in breakdown if item["is_correct"])
    final_score = round(
        sum(item["answer_score"] for item in breakdown) / len(questions), 2
    ) if questions else 0.0
    final_passed = final_score >= PASS_SCORE

    scores = {
        "score": final_score,
        "passed": final_passed,
        "verification_status": "Pass" if final_passed else "Fail",
        "total_correct": total_correct,
        "total_questions": len(questions),
        "pass_score": PASS_SCORE,
        "breakdown": breakdown,
    }

    # Step 3 — generate LLM feedback summary
    try:
        feedback = _result_feedback(assessment, scores)
        feedback["feedback_status"] = "ready"
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Skill Assessment BG Feedback Error")
        feedback = {
            "summary": "Quiz completed. See your score above.",
            "strengths": [],
            "gaps": [],
            "next_step": "Review the missed concepts and retry.",
            "status": "verified" if final_passed else "not_verified",
            "feedback_status": "ready",
        }

    # Step 4 — update Student Skill record if the student passed
    if final_passed:
        try:
            student_skill_name = frappe.db.get_value(
                "Student Skill", {"student": student, "skill": skill}, "name"
            )
            if student_skill_name:
                ss_doc = frappe.get_doc("Student Skill", student_skill_name)
            else:
                ss_doc = frappe.get_doc({
                    "doctype": "Student Skill",
                    "student": student,
                    "skill": skill,
                    "current_level": level,
                    "self_declared": 0,
                    "is_public": 1,
                })
                ss_doc.insert(ignore_permissions=True)
                ss_doc = frappe.get_doc("Student Skill", ss_doc.name)

            level_weights = {"Beginner": 1, "Intermediate": 2, "Advanced": 3, "Expert": 4}
            if level_weights.get(level, 1) > level_weights.get(ss_doc.current_level, 0):
                ss_doc.update_skill_level(level)
                ss_doc = frappe.get_doc("Student Skill", ss_doc.name)

            ss_doc.mark_ai_verified()

            # Milestone completion logic: check if this skill test completion completes a milestone in the student's enrollment
            try:
                enrollments = frappe.get_all(
                    "Student Path Enrollment",
                    filters={"student": student, "status": "Active"},
                    fields=["name"]
                )
                for enr in enrollments:
                    enr_doc = frappe.get_doc("Student Path Enrollment", enr.name)
                    from nexedu.path_finder.utils.milestone_engine import recalculate_all_milestones
                    recalculate_all_milestones(enr_doc)
                    current_order = enr_doc.current_milestone_order or 1
                    active_milestone = next(
                        (r for r in enr_doc.milestone_progress if r.idx == current_order), None
                    )
                    if active_milestone and active_milestone.skill:
                        try:
                            from job_search_ai.services.skill_gap.normalizer import normalize_skill
                            norm_active_skill = normalize_skill(active_milestone.skill).lower().strip()
                            norm_tested_skill = normalize_skill(skill).lower().strip()
                        except Exception:
                            norm_active_skill = active_milestone.skill.lower().strip()
                            norm_tested_skill = skill.lower().strip()

                        if norm_active_skill == norm_tested_skill:
                            # Check if all checklist points for this milestone are completed
                            siblings = [r for r in enr_doc.milestone_points if r.milestone_title == active_milestone.milestone_title]
                            all_completed = len(siblings) == 0 or all(r.status == "Completed" for r in siblings)
                            
                            if all_completed:
                                if not frappe.db.exists("Path Progress Log", {"enrollment": enr_doc.name, "milestone": active_milestone.name}):
                                    log = frappe.get_doc({
                                        "doctype": "Path Progress Log",
                                        "student": student,
                                        "enrollment": enr_doc.name,
                                        "career_path": enr_doc.career_path,
                                        "milestone": active_milestone.name,
                                        "status": "Completed",
                                        "score": final_score,
                                        "feedback": feedback.get("summary") or "Completed via skill assessment test."
                                    })
                                    log.insert(ignore_permissions=True)
                                    frappe.db.commit()
            except Exception:
                frappe.log_error(frappe.get_traceback(), "Skill Assessment BG Milestone Completion Error")
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Skill Assessment BG Student Skill Error")

    # Step 5 — save final score + feedback + breakdown back to the Skill Test doc
    try:
        doc = frappe.get_doc("Skill Test", skill_test_name)
        result_data = json.loads(doc.test_result or "{}")
        result_data["ai_response"] = feedback
        result_data.setdefault("result", {})
        result_data["result"]["score"] = final_score
        result_data["result"]["status"] = scores["verification_status"]
        result_data["result"]["passed"] = final_passed
        result_data["result"]["total_correct"] = total_correct
        result_data["result"]["total_questions"] = len(questions)
        result_data["evaluation_breakdown"] = breakdown
        doc.score = final_score
        doc.status = scores["verification_status"]
        doc.test_result = json.dumps(result_data, indent=2)
        doc.save(ignore_permissions=True)
        if not frappe.flags.in_test:
            frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Skill Assessment BG Save Error")


@frappe.whitelist()
def get_skill_test_result(skill_test_name, **kwargs):
    """
    Poll this endpoint after submit_skill_test to get the final score + feedback.
    Returns feedback_status='pending' while the background job is still running,
    and 'ready' once evaluation and feedback are complete.
    """
    if not skill_test_name:
        frappe.throw("skill_test_name is required.")
    doc = frappe.get_doc("Skill Test", skill_test_name)
    result_data = json.loads(doc.test_result or "{}")
    ai_response = result_data.get("ai_response") or {}
    result = result_data.get("result") or {}
    return {
        "skill_test": skill_test_name,
        "score": doc.score,
        "status": doc.status,
        "passed": result.get("passed", False),
        "total_correct": result.get("total_correct", 0),
        "total_questions": result.get("total_questions", 0),
        "feedback": ai_response,
        "feedback_status": ai_response.get("feedback_status", "pending"),
        "breakdown": result_data.get("evaluation_breakdown") or [],
    }


@frappe.whitelist()
def enqueue_generate_question_banks():
    """
    Enqueues the question bank generation task to run in the background.
    """
    import frappe.utils.background_jobs
    
    # Check if job is enqueued (not started yet)
    is_active = frappe.utils.background_jobs.is_job_enqueued("nexedu.api.skill_assessment_ai.prepopulate_question_banks")
    
    # Check if job is currently started/executing
    if not is_active:
        for q_name in ["long", "default", "short"]:
            q = frappe.utils.background_jobs.get_queue(q_name)
            started_ids = q.started_job_registry.get_job_ids()
            for j_id in started_ids:
                job = q.fetch_job(j_id)
                if job and job.kwargs.get("method") == "nexedu.api.skill_assessment_ai.prepopulate_question_banks":
                    is_active = True
                    break
            if is_active:
                break
                
    if is_active:
        return {"message": "Question bank generation task is already enqueued or running."}

    frappe.enqueue(
        "nexedu.api.skill_assessment_ai.prepopulate_question_banks",
        queue="long",
        timeout=43200,
        now=frappe.flags.in_test
    )
    return {"message": "Question bank generation task enqueued successfully in the background queue."}


def prepopulate_question_banks():
    """
    Iterates over all skills and generates questions for Beginner, Intermediate, and Advanced levels
    if their Question Bank does not have enough questions.
    """
    import time
    from nexedu.api.skill_assessment_config import BANK_SIZE
    
    skills = frappe.get_all("Skill", fields=["skill_name"])
    levels = ["Beginner", "Intermediate", "Advanced", "Expert"]

    total_generated = 0
    total_skipped = 0

    for s_item in skills:
        skill = s_item.get("skill_name")
        if not skill:
            continue

        for level in levels:
            # Check if this level is already populated
            count = frappe.db.count("Skill Question Bank", filters={"skill": skill, "level": level})
            if count >= BANK_SIZE:
                total_skipped += 1
                continue

            # Level is missing or partially filled, let's generate it
            try:
                generate_question_bank(skill, level)
                total_generated += 1
                
                # Commit after each level to ensure progress is saved immediately
                frappe.db.commit()
                
                # Sleep a short while to cool down Ollama and avoid server overload
                time.sleep(3)
            except Exception as e:
                # Reconnect if MySQL dropped the connection (long-running job)
                if "2013" in str(e) or "Lost connection" in str(e):
                    _safe_db_reconnect()
                # Safely log
                try:
                    frappe.log_error(
                        message=f"Failed to generate bank for {skill} ({level}): {str(e)}",
                        title="Skill Question Bank Generation Failed"
                    )
                except Exception:
                    pass
                # Still commit whatever succeeded
                try:
                    frappe.db.commit()
                except Exception:
                    pass

    return {
        "status": "Completed",
        "generated": total_generated,
        "skipped": total_skipped
    }
