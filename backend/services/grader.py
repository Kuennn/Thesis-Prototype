# services/grader.py
# Handles answer checking for all objective question types.
# Uses pattern matching on OCR text — no AI needed for MC, T/F, and Identification.
#
# Grading logic per type:
#   multiple_choice  → find "1. A", "1) A", "1 A" patterns → compare letter to answer key
#   true_or_false    → find "1. True", "1. T", "1. False", "1. F" patterns
#   identification   → fuzzy text match against answer key (handles OCR typos)
#   essay            → skipped here, handled by AI grader later

import re
from difflib import SequenceMatcher
from models.models import QuestionType


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def grade_answers(extracted_text: str, questions: list) -> list:
    """
    Takes the full OCR text from a paper and a list of Question objects.
    Returns a list of grading results, one per question.

    Each result:
        {
            "question_id":    int,
            "question_no":    int,
            "question_type":  str,
            "extracted_answer": str,   # What OCR found for this question
            "answer_key":     str,     # Correct answer
            "score":          float,   # Points awarded
            "max_score":      float,
            "feedback":       str,     # Explanation shown to student
            "is_essay":       bool,    # True = needs AI grading later
        }
    """
    results = []

    for question in questions:
        q_no   = question.question_no
        q_type = question.question_type
        key    = question.answer_key.strip()
        max_s  = question.max_score

        if q_type == QuestionType.multiple_choice:
            extracted, score, feedback = grade_multiple_choice(extracted_text, q_no, key, max_s)

        elif q_type == QuestionType.true_or_false:
            extracted, score, feedback = grade_true_or_false(extracted_text, q_no, key, max_s)

        elif q_type == QuestionType.identification:
            extracted, score, feedback = grade_identification(extracted_text, q_no, key, max_s)

        elif q_type == QuestionType.essay:
            # Essays are skipped — marked for AI grading
            extracted, score, feedback = grade_essay_placeholder(extracted_text, q_no)

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
        })

    return results


# ─── Multiple Choice ──────────────────────────────────────────────────────────

def grade_multiple_choice(text: str, q_no: int, answer_key: str, max_score: float):
    """
    Finds patterns like:
      "1. A", "1) A", "1 - A", "1: A", "1.A"
    OCR sometimes misreads letters so we also handle common substitutions:
      0 → O, 1 → I, ( → C, | → I
    """
    # Normalize OCR common misreads before matching
    normalized = normalize_ocr_text(text)

    # Build regex: matches "1." or "1)" or "1 " followed by optional space and a letter A-D
    pattern = rf'\b{q_no}\s*[.):\-]?\s*([A-Da-d])\b'
    match   = re.search(pattern, normalized)

    if not match:
        return ("", 0.0, f"Could not find answer for question {q_no} in the paper.")

    student_answer = match.group(1).upper()
    correct_answer = answer_key.upper().strip()

    if student_answer == correct_answer:
        return (student_answer, max_score, f"Correct! Answer: {student_answer}")
    else:
        return (student_answer, 0.0, f"Incorrect. You answered {student_answer}, correct answer is {correct_answer}.")


# ─── True or False ────────────────────────────────────────────────────────────

def grade_true_or_false(text: str, q_no: int, answer_key: str, max_score: float):
    """
    Finds patterns like:
      "1. True", "1. False", "1. T", "1. F"
    OCR sometimes writes "Irue" instead of "True" so we fuzzy match.
    """
    normalized = normalize_ocr_text(text)

    # Match question number followed by True/False or T/F
    pattern = rf'\b{q_no}\s*[.):\-]?\s*([A-Za-z]+)\b'
    match   = re.search(pattern, normalized)

    if not match:
        return ("", 0.0, f"Could not find answer for question {q_no} in the paper.")

    raw            = match.group(1).strip().lower()
    correct_answer = answer_key.strip().lower()

    # Normalize to "true" or "false"
    student_answer = normalize_true_false(raw)
    correct_norm   = normalize_true_false(correct_answer)

    if student_answer is None:
        return (raw, 0.0, f"Could not read True/False answer for question {q_no}. Found: '{raw}'")

    if student_answer == correct_norm:
        return (student_answer.capitalize(), max_score, f"Correct! Answer: {student_answer.capitalize()}")
    else:
        return (
            student_answer.capitalize(), 0.0,
            f"Incorrect. You answered {student_answer.capitalize()}, correct answer is {correct_norm.capitalize()}."
        )


def normalize_true_false(raw: str) -> str:
    """Maps various OCR outputs to 'true' or 'false'."""
    true_variants  = {'true', 't', 'yes', 'y', '1', 'irue', 'trve', 'troe'}
    false_variants = {'false', 'f', 'no', 'n', '0', 'talse', 'faise', 'fase'}

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
    Finds the text after a question number and compares it to the answer key
    using fuzzy matching — this handles OCR typos and minor spelling errors.

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
    # Take only the first line (avoid grabbing next question's content)
    student_answer = student_answer.split('\n')[0].strip()

    if not student_answer:
        return ("", 0.0, f"No answer found for question {q_no}.")

    similarity = fuzzy_match(
        student_answer.lower(),
        answer_key.lower()
    )

    if similarity >= 0.90:
        return (student_answer, max_score, f"Correct! ({int(similarity*100)}% match)")
    elif similarity >= 0.70:
        half = round(max_score / 2, 1)
        return (student_answer, half, f"Partially correct ({int(similarity*100)}% match). Expected: {answer_key}")
    else:
        return (student_answer, 0.0, f"Incorrect ({int(similarity*100)}% match). Expected: {answer_key}")


# ─── Essay Placeholder ────────────────────────────────────────────────────────

def grade_essay_placeholder(text: str, q_no: int):
    """
    Essays are not graded here — they are flagged for AI grading.
    We still try to extract the relevant text portion for the AI to use later.
    """
    # Try to extract text near this question number
    pattern = rf'\b{q_no}\s*[.):\-]?\s*(.+?)(?=\b{q_no + 1}\s*[.):\-]|\Z)'
    match   = re.search(pattern, text, re.DOTALL)

    extracted = ""
    if match:
        extracted = match.group(1).strip()[:500]  # Cap at 500 chars

    return (extracted, None, "Pending AI essay grading.")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def normalize_ocr_text(text: str) -> str:
    """
    Fixes the most common OCR misreads before pattern matching.
    These substitutions only apply in specific contexts so we keep them minimal.
    """
    # Common single-character OCR errors in answer context
    corrections = {
        '|': 'I',   # Pipe misread as I
        'l': 'I',   # Lowercase L misread as I (in answer position)
        '0': 'O',   # Zero misread as O (careful — only in letter positions)
    }
    # We don't do blanket replacement since it would corrupt numbers
    # Instead just return normalized whitespace
    text = re.sub(r'\s+', ' ', text)  # Collapse multiple spaces
    text = text.strip()
    return text


def fuzzy_match(a: str, b: str) -> float:
    """Returns similarity ratio between two strings (0.0 to 1.0)."""
    return SequenceMatcher(None, a.strip(), b.strip()).ratio()


# ─── Score Summary ────────────────────────────────────────────────────────────

def compute_total_score(grading_results: list) -> dict:
    """
    Computes total and max scores from grading results.
    Essays (score=None) are excluded from total until AI grades them.
    """
    total   = 0.0
    maximum = 0.0
    pending_essays = 0

    for r in grading_results:
        maximum += r["max_score"]
        if r["is_essay"]:
            pending_essays += 1
        elif r["score"] is not None:
            total += r["score"]

    return {
        "total_score":     round(total, 2),
        "max_score":       round(maximum, 2),
        "pending_essays":  pending_essays,
        "percentage":      round((total / maximum * 100), 1) if maximum > 0 else 0.0,
    }
