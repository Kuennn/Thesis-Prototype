# services/grader.py
# Handles answer checking for all objective question types.
# Uses pattern matching on OCR text — no AI needed for MC, T/F, and Identification.
#
# Grading logic per type:
#   multiple_choice  → find "1. A", "1) A", "1 A" patterns → compare letter to answer key
#   true_or_false    → find "1. True", "1. T", "1. False", "1. F" patterns
#   identification   → fuzzy text match against answer key (handles OCR typos)
#   essay            → handled by Groq AI grader

import re
from difflib import SequenceMatcher
from models.models import QuestionType


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def grade_answers(extracted_text: str, questions: list) -> list:
    """
    Takes the full OCR text from a paper and a list of Question objects.
    Returns a list of grading results, one per question.
    """
    results = []

    for question in questions:
        q_no          = question.question_no
        q_type        = question.question_type
        key           = question.answer_key.strip()
        max_s         = question.max_score
        essay_details = None

        if q_type == QuestionType.multiple_choice:
            extracted, score, feedback = grade_multiple_choice(
                extracted_text, q_no, key, max_s
            )

        elif q_type == QuestionType.true_or_false:
            extracted, score, feedback = grade_true_or_false(
                extracted_text, q_no, key, max_s
            )

        elif q_type == QuestionType.identification:
            extracted, score, feedback = grade_identification(
                extracted_text, q_no, key, max_s
            )

        elif q_type == QuestionType.essay:
            extracted, score, feedback, essay_details = grade_essay_with_ai(
                text          = extracted_text,
                q_no          = q_no,
                model_answer  = key,
                question_text = question.question_text or "",
                rubric        = question.rubric or "",
                max_score     = max_s,
            )

        else:
            extracted, score, feedback = ("", 0.0, "Unknown question type.")

        results.append({
            "question_id":      question.id,
            "question_no":      q_no,
            "question_type":    q_type,
            "extracted_answer": extracted,
            "answer_key":       key,
            "score":            score,
            "max_score":        max_s,
            "feedback":         feedback,
            "is_essay":         q_type == QuestionType.essay,
            "essay_details":    essay_details,
        })

    return results


# ─── Multiple Choice ──────────────────────────────────────────────────────────

def grade_multiple_choice(text: str, q_no: int, answer_key: str, max_score: float):
    """
    Finds patterns like: "1. A", "1) A", "1 - A", "1: A", "1.A"
    TrOCR sometimes separates number and letter so we have a fallback pattern.
    """
    normalized = normalize_ocr_text(text)

    # Primary pattern — number immediately followed by letter
    pattern = rf'\b{q_no}\s*[.):\-]?\s*([A-Da-d])\b'
    match   = re.search(pattern, normalized)

    # Fallback — number then up to 5 non-letter chars then a letter
    # Handles TrOCR separating "1" and "A" into different tokens
    if not match:
        pattern = rf'\b{q_no}\b[^A-Da-d\n]{{0,5}}([A-Da-d])\b'
        match   = re.search(pattern, normalized)

    if not match:
        return ("", 0.0, f"Could not find answer for question {q_no} in the paper.")

    student_answer = match.group(1).upper()
    correct_answer = answer_key.upper().strip()

    if student_answer == correct_answer:
        return (student_answer, max_score, f"Correct! Answer: {student_answer}")
    else:
        return (
            student_answer, 0.0,
            f"Incorrect. You answered {student_answer}, correct answer is {correct_answer}."
        )


# ─── True or False ────────────────────────────────────────────────────────────

def grade_true_or_false(text: str, q_no: int, answer_key: str, max_score: float):
    """
    Finds patterns like: "1. True", "1. False", "1. T", "1. F"
    Fuzzy matches to handle OCR misreads like "Irue" for "True".
    """
    normalized = normalize_ocr_text(text)

    pattern = rf'\b{q_no}\s*[.):\-]?\s*([A-Za-z]+)\b'
    match   = re.search(pattern, normalized)

    if not match:
        return ("", 0.0, f"Could not find answer for question {q_no} in the paper.")

    raw            = match.group(1).strip().lower()
    correct_answer = answer_key.strip().lower()

    student_answer = normalize_true_false(raw)
    correct_norm   = normalize_true_false(correct_answer)

    if student_answer is None:
        return (raw, 0.0,
                f"Could not read True/False answer for question {q_no}. Found: '{raw}'")

    if student_answer == correct_norm:
        return (student_answer.capitalize(), max_score,
                f"Correct! Answer: {student_answer.capitalize()}")
    else:
        return (
            student_answer.capitalize(), 0.0,
            f"Incorrect. You answered {student_answer.capitalize()}, "
            f"correct answer is {correct_norm.capitalize()}."
        )


def normalize_true_false(raw: str):
    """Maps various OCR outputs to 'true' or 'false'."""
    true_variants  = {'true', 't', 'yes', 'y', '1', 'irue', 'trve', 'troe', 'tue', 'ture'}
    false_variants = {'false', 'f', 'no', 'n', '0', 'talse', 'faise', 'fase', 'flase'}

    raw = raw.lower().strip()
    if raw in true_variants:
        return 'true'
    if raw in false_variants:
        return 'false'

    # Fuzzy match as last resort
    if fuzzy_match(raw, 'true') > 0.75:
        return 'true'
    if fuzzy_match(raw, 'false') > 0.75:
        return 'false'

    return None


# ─── Identification ───────────────────────────────────────────────────────────

def grade_identification(text: str, q_no: int, answer_key: str, max_score: float):
    """
    Extracts the answer for a question number and fuzzy matches against the key.
    Updated to handle TrOCR output which may include punctuation artifacts.

    Scoring:
      >= 90% match → full marks
      >= 70% match → half marks
      <  70% match → no marks
    """
    normalized = normalize_ocr_text(text)

    # Extract text after the question number until the next number or end
    pattern = rf'\b{q_no}\s*[.):\-]?\s*(.+?)(?=\b{q_no + 1}\s*[.):\-]|\Z)'
    match   = re.search(pattern, normalized, re.DOTALL)

    if not match:
        return ("", 0.0, f"Could not find answer for question {q_no} in the paper.")

    student_answer = match.group(1).strip()

    # Take first line only — avoids grabbing next question's content
    student_answer = student_answer.split('\n')[0].strip()

    # Clean up TrOCR punctuation artifacts (dots, dashes, commas at end)
    student_answer = re.sub(r'[.\-,;]+$', '', student_answer).strip()

    # Cap at 60 chars — identification answers should be short
    student_answer = student_answer[:60].strip()

    if not student_answer:
        return ("", 0.0, f"No answer found for question {q_no}.")

    similarity = fuzzy_match(student_answer.lower(), answer_key.lower())

    if similarity >= 0.90:
        return (student_answer, max_score,
                f"Correct! ({int(similarity * 100)}% match)")
    elif similarity >= 0.70:
        half = round(max_score / 2, 1)
        return (student_answer, half,
                f"Partially correct ({int(similarity * 100)}% match). "
                f"Expected: {answer_key}")
    else:
        return (student_answer, 0.0,
                f"Incorrect ({int(similarity * 100)}% match). "
                f"Expected: {answer_key}")


# ─── Essay Grader (AI) ────────────────────────────────────────────────────────

def grade_essay_with_ai(
    text:          str,
    q_no:          int,
    model_answer:  str,
    question_text: str,
    rubric:        str,
    max_score:     float,
):
    """
    Extracts the student's essay answer from OCR text,
    then sends it to Groq for rubric-based grading.
    Returns: (extracted_text, score, feedback, essay_details)
    """
    from services.essay_grader import grade_essay

    # Try to extract text near this question number
    pattern   = rf'\b{q_no}\s*[.):\-]?\s*(.+?)(?=\b{q_no + 1}\s*[.):\-]|\Z)'
    match     = re.search(pattern, text, re.DOTALL)
    extracted = ""

    if match:
        extracted = match.group(1).strip()[:1000]

    # Fallback — check for "Answer:" label
    if not extracted:
        answer_match = re.search(r'[Aa]nswer\s*:\s*(.+)', text, re.DOTALL)
        if answer_match:
            extracted = answer_match.group(1).strip()[:1000]
        else:
            extracted = text.strip()[:1000]

    result = grade_essay(
        student_answer = extracted,
        model_answer   = model_answer,
        question_text  = question_text,
        rubric         = rubric,
        max_score      = max_score,
    )

    essay_details = {
        "key_points_hit":    result["key_points_hit"],
        "key_points_missed": result["key_points_missed"],
        "relevance":         result["relevance"],
        "rubric_notes":      result["rubric_notes"],
    }

    return (extracted, result["score"], result["feedback"], essay_details)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def normalize_ocr_text(text: str) -> str:
    """Normalizes whitespace and collapses multiple spaces."""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def fuzzy_match(a: str, b: str) -> float:
    """Returns similarity ratio between two strings (0.0 to 1.0)."""
    return SequenceMatcher(None, a.strip(), b.strip()).ratio()


# ─── Score Summary ────────────────────────────────────────────────────────────

def compute_total_score(grading_results: list) -> dict:
    """Computes total and max scores from all grading results including essays."""
    total          = 0.0
    maximum        = 0.0
    pending_essays = 0

    for r in grading_results:
        maximum += r["max_score"]
        if r["score"] is not None:
            total += r["score"]
        elif r["is_essay"]:
            pending_essays += 1

    return {
        "total_score":    round(total, 2),
        "max_score":      round(maximum, 2),
        "pending_essays": pending_essays,
        "percentage":     round((total / maximum * 100), 1) if maximum > 0 else 0.0,
    }
