# services/grader.py
# Handles answer checking for all objective question types.
# Updated for hybrid TrOCR output — handles fragmented text regions.
#
# Grading logic per type:
#   multiple_choice  → regex pattern matching for "1. A" style answers
#   true_or_false    → regex + fuzzy match for True/False variants
#   identification   → improved extraction + multi-strategy fuzzy matching
#   essay            → Groq AI grader with improved text extraction

import re
from difflib import SequenceMatcher
from models.models import QuestionType


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def grade_answers(extracted_text: str, questions: list) -> list:
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
                extracted_text, q_no, key, max_s, questions
            )

        elif q_type == QuestionType.essay:
            extracted, score, feedback, essay_details = grade_essay_with_ai(
                text          = extracted_text,
                q_no          = q_no,
                model_answer  = key,
                question_text = question.question_text or "",
                rubric        = question.rubric or "",
                max_score     = max_s,
                questions     = questions,
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
    normalized = normalize_ocr_text(text)

    # Primary — number immediately followed by letter
    pattern = rf'\b{q_no}\s*[.):\-]?\s*([A-Da-d])\b'
    match   = re.search(pattern, normalized)

    # Fallback — number then up to 5 non-letter chars then a letter
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
    normalized = normalize_ocr_text(text)

    pattern = rf'\b{q_no}\s*[.):\-]?\s*([A-Za-z]+)\b'
    match   = re.search(pattern, normalized)

    if not match:
        return ("", 0.0, f"Could not find answer for question {q_no} in the paper.")

    raw          = match.group(1).strip().lower()
    correct_norm = normalize_true_false(answer_key.strip().lower())
    student_ans  = normalize_true_false(raw)

    if student_ans is None:
        return (raw, 0.0,
                f"Could not read True/False answer for question {q_no}. Found: '{raw}'")

    if student_ans == correct_norm:
        return (student_ans.capitalize(), max_score,
                f"Correct! Answer: {student_ans.capitalize()}")
    else:
        return (
            student_ans.capitalize(), 0.0,
            f"Incorrect. You answered {student_ans.capitalize()}, "
            f"correct answer is {correct_norm.capitalize()}."
        )


def normalize_true_false(raw: str):
    true_variants  = {'true', 't', 'yes', 'y', '1', 'irue', 'trve', 'troe', 'tue', 'ture'}
    false_variants = {'false', 'f', 'no', 'n', '0', 'talse', 'faise', 'fase', 'flase'}

    raw = raw.lower().strip()
    if raw in true_variants:  return 'true'
    if raw in false_variants: return 'false'

    if fuzzy_match(raw, 'true')  > 0.75: return 'true'
    if fuzzy_match(raw, 'false') > 0.75: return 'false'
    return None


# ─── Identification ───────────────────────────────────────────────────────────

def grade_identification(text: str, q_no: int, answer_key: str,
                         max_score: float, questions: list = None):
    """
    Multi-strategy extraction for identification answers.
    TrOCR fragments text into regions, so we try several approaches
    and pick the best match against the answer key.
    """
    normalized = normalize_ocr_text(text)

    # Determine what the next question number is
    next_q_no = _next_question_no(q_no, questions)

    candidates = []

    # ── Strategy 1: Standard pattern with boundary ────────────────────────────
    if next_q_no:
        pattern = rf'\b{q_no}\s*[.):\-]?\s*(.+?)(?=\b{next_q_no}\s*[.):\-]|\Z)'
    else:
        pattern = rf'\b{q_no}\s*[.):\-]?\s*(.+?)(?=\Z)'

    match = re.search(pattern, normalized, re.DOTALL)
    if match:
        raw = match.group(1).strip()
        # Take first line only and clean up
        first_line = raw.split('\n')[0].strip()
        first_line = re.sub(r'[.\-,;:]+$', '', first_line).strip()
        # Take only first 3 words — identification answers are short
        words = first_line.split()[:3]
        candidate = ' '.join(words).strip()
        if candidate:
            candidates.append(candidate)

    # ── Strategy 2: Look for answer key words anywhere near the question ───────
    # Search for words from the answer key in the vicinity of the question number
    key_words = answer_key.lower().split()
    if len(key_words) <= 3:
        # Build pattern that looks for key words near the question number
        q_pos = re.search(rf'\b{q_no}\b', normalized)
        if q_pos:
            # Look at 80 chars after the question number
            vicinity = normalized[q_pos.start():q_pos.start() + 80]
            # Try to find the answer key words in the vicinity
            for word in key_words:
                word_match = re.search(rf'\b{re.escape(word)}\b', vicinity, re.IGNORECASE)
                if word_match:
                    # Extract surrounding context
                    start = max(0, word_match.start() - 5)
                    end   = min(len(vicinity), word_match.end() + 20)
                    candidates.append(vicinity[start:end].strip())

    # ── Strategy 3: Whole text fuzzy search for answer key ────────────────────
    # If answer key is short (≤3 words), search the entire text for it
    if len(key_words) <= 3:
        # Look for partial matches of the answer key anywhere in text
        for i in range(len(normalized) - len(answer_key)):
            chunk = normalized[i:i + len(answer_key) + 10]
            if fuzzy_match(chunk[:len(answer_key)].lower(), answer_key.lower()) > 0.7:
                candidates.append(chunk[:len(answer_key) + 5].strip())

    # ── Pick best candidate ────────────────────────────────────────────────────
    if not candidates:
        return ("", 0.0, f"Could not find answer for question {q_no} in the paper.")

    # Score each candidate against the answer key
    best_text  = ""
    best_score = 0.0
    for c in candidates:
        c_clean = re.sub(r'[.\-,;:]+$', '', c).strip()[:80]
        sim     = fuzzy_match(c_clean.lower(), answer_key.lower())
        if sim > best_score:
            best_score = sim
            best_text  = c_clean

    if not best_text:
        return ("", 0.0, f"No answer found for question {q_no}.")

    if best_score >= 0.90:
        return (best_text, max_score,
                f"Correct! ({int(best_score * 100)}% match)")
    elif best_score >= 0.65:
        half = round(max_score / 2, 1)
        return (best_text, half,
                f"Partially correct ({int(best_score * 100)}% match). "
                f"Expected: {answer_key}")
    else:
        return (best_text, 0.0,
                f"Incorrect ({int(best_score * 100)}% match). "
                f"Expected: {answer_key}")


# ─── Essay Grader (AI) ────────────────────────────────────────────────────────

def grade_essay_with_ai(
    text:          str,
    q_no:          int,
    model_answer:  str,
    question_text: str,
    rubric:        str,
    max_score:     float,
    questions:     list = None,
):
    """
    Improved essay extraction for TrOCR fragmented output.
    Uses multiple strategies to get the best essay text before sending to Groq.
    """
    from services.essay_grader import grade_essay

    next_q_no = _next_question_no(q_no, questions)
    extracted = ""

    # ── Strategy 1: Question number boundary ──────────────────────────────────
    if next_q_no:
        pattern = rf'\b{q_no}\s*[.):\-]?\s*(.+?)(?=\b{next_q_no}\s*[.):\-]|\Z)'
    else:
        pattern = rf'\b{q_no}\s*[.):\-]?\s*(.+?)(?=\Z)'

    match = re.search(pattern, text, re.DOTALL)
    if match:
        extracted = match.group(1).strip()[:1500]

    # ── Strategy 2: "Answer:" label ───────────────────────────────────────────
    if not extracted or len(extracted.split()) < 5:
        answer_match = re.search(r'[Aa]nswer\s*[:\-]?\s*(.+)', text, re.DOTALL)
        if answer_match:
            extracted = answer_match.group(1).strip()[:1500]

    # ── Strategy 3: Use full text minus question numbers ──────────────────────
    # For single-essay exams or when other strategies fail
    if not extracted or len(extracted.split()) < 5:
        # Remove lines that look like question numbers (e.g. "1.", "2.")
        lines    = text.split(' ')
        filtered = [
            w for w in lines
            if not re.match(r'^\d+[.):\-]?$', w.strip())
        ]
        extracted = ' '.join(filtered).strip()[:1500]

    # ── Clean up TrOCR artifacts ──────────────────────────────────────────────
    # TrOCR adds random periods and spaces between words
    extracted = re.sub(r'\s+\.\s+', ' ', extracted)   # " . " → " "
    extracted = re.sub(r'\s{2,}',   ' ', extracted)   # multiple spaces → single
    extracted = extracted.strip()

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

def _next_question_no(q_no: int, questions: list) -> int:
    """Returns the next question number after q_no, or None if last."""
    if not questions:
        return q_no + 1
    q_nos = sorted([q.question_no for q in questions])
    idx   = q_nos.index(q_no) if q_no in q_nos else -1
    if idx >= 0 and idx < len(q_nos) - 1:
        return q_nos[idx + 1]
    return None


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
