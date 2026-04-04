# services/grader.py
# Phase 9 — OCR Accuracy Rework
#
# Changes from Phase 8:
#   - grade_essay_with_ai() now calls extract_essay_region() directly
#     instead of relying on the flat full_text string.
#     This gives the essay grader a clean, position-aware crop of the
#     answer box rather than the whole-page OCR dump.
#   - Essay extraction strategies updated to use structured OCR output
#     (lines list with bbox positions) when available.
#   - All other question types (MC, TF, ID) unchanged from Phase 8.

import re
from difflib import SequenceMatcher
from models.models import QuestionType


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def grade_answers(
    extracted_text: str,
    questions:      list,
    ocr_result:     dict  = None,   # Phase 9: full OCR result dict (optional)
    image_path:     str   = None,   # Phase 9: original image path for essay re-crop
    region_map_path: str  = None,   # Phase 9: region map for homography crop
) -> list:
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
                text             = extracted_text,
                q_no             = q_no,
                model_answer     = key,
                question_text    = question.question_text or "",
                rubric           = question.rubric or "",
                max_score        = max_s,
                questions        = questions,
                image_path       = image_path,
                region_map_path  = region_map_path,
                ocr_result       = ocr_result,
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

    pattern = rf'\b{q_no}\s*[.):\-]?\s*([A-Da-d])\b'
    match   = re.search(pattern, normalized)

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
    normalized = normalize_ocr_text(text)
    next_q_no  = _next_question_no(q_no, questions)
    candidates = []

    if next_q_no:
        pattern = rf'\b{q_no}\s*[.):\-]?\s*(.+?)(?=\b{next_q_no}\s*[.):\-]|\Z)'
    else:
        pattern = rf'\b{q_no}\s*[.):\-]?\s*(.+?)(?=\Z)'

    match = re.search(pattern, normalized, re.DOTALL)
    if match:
        raw        = match.group(1).strip()
        first_line = raw.split('\n')[0].strip()
        first_line = re.sub(r'[.\-,;:]+$', '', first_line).strip()
        words      = first_line.split()[:3]
        candidate  = ' '.join(words).strip()
        if candidate:
            candidates.append(candidate)

    key_words = answer_key.lower().split()
    if len(key_words) <= 3:
        q_pos = re.search(rf'\b{q_no}\b', normalized)
        if q_pos:
            vicinity = normalized[q_pos.start():q_pos.start() + 80]
            for word in key_words:
                word_match = re.search(rf'\b{re.escape(word)}\b', vicinity, re.IGNORECASE)
                if word_match:
                    start = max(0, word_match.start() - 5)
                    end   = min(len(vicinity), word_match.end() + 20)
                    candidates.append(vicinity[start:end].strip())

    if len(key_words) <= 3:
        for i in range(len(normalized) - len(answer_key)):
            chunk = normalized[i:i + len(answer_key) + 10]
            if fuzzy_match(chunk[:len(answer_key)].lower(), answer_key.lower()) > 0.7:
                candidates.append(chunk[:len(answer_key) + 5].strip())

    if not candidates:
        return ("", 0.0, f"Could not find answer for question {q_no} in the paper.")

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


# ─── Essay Grader ─────────────────────────────────────────────────────────────

def grade_essay_with_ai(
    text:             str,
    q_no:             int,
    model_answer:     str,
    question_text:    str,
    rubric:           str,
    max_score:        float,
    questions:        list = None,
    image_path:       str  = None,   # Phase 9: direct image path for re-crop
    region_map_path:  str  = None,   # Phase 9: region map path
    ocr_result:       dict = None,   # Phase 9: full OCR result with line positions
):
    """
    Phase 9 essay extraction — 3-tier strategy:

    Tier 1 (best): extract_essay_region() — crops the physical essay box
        from the answer sheet image using region_map coordinates or the
        bottom-half heuristic, then stitches lines before TrOCR reads them.
        This bypasses the flat full_text entirely for essays.

    Tier 2: structured OCR output — uses the lines list with bbox positions
        to find text in the bottom portion of the page by y-coordinate,
        rather than relying on question number patterns in flat text.

    Tier 3: flat text fallback — original regex-based extraction from
        Phase 8, used when image_path is unavailable.
    """
    from services.essay_grader import grade_essay

    extracted     = ""
    ocr_confidence = 1.0

    # ── Tier 1: direct image re-crop (Phase 9) ────────────────────────────────
    if image_path and os.path.exists(image_path):
        try:
            from services.ocr import extract_essay_region
            essay_text = extract_essay_region(image_path, region_map_path)
            if essay_text and len(essay_text.split()) >= 2:
                extracted      = essay_text
                ocr_confidence = _estimate_ocr_confidence(ocr_result)
                print(f"  Essay Q{q_no}: Tier 1 extraction — {len(extracted.split())} words")
        except Exception as e:
            print(f"  Essay Q{q_no}: Tier 1 failed ({e}), trying Tier 2.")

    # ── Tier 2: structured OCR line positions ────────────────────────────────
    if (not extracted or len(extracted.split()) < 2) and ocr_result:
        try:
            lines    = ocr_result.get("lines", [])
            page_h   = _estimate_page_height(lines)
            # Take lines from the bottom 55% of the page (essay section)
            threshold_y = page_h * 0.45
            essay_lines = [
                l for l in lines
                if l.get("y_center", 0) > threshold_y
            ]
            if essay_lines:
                extracted      = " ".join(l["text"] for l in essay_lines)
                ocr_confidence = _estimate_ocr_confidence(ocr_result)
                print(f"  Essay Q{q_no}: Tier 2 extraction — {len(extracted.split())} words")
        except Exception as e:
            print(f"  Essay Q{q_no}: Tier 2 failed ({e}), trying Tier 3.")

    # ── Tier 3: flat text regex fallback (Phase 8 behavior) ──────────────────
    if not extracted or len(extracted.split()) < 2:
        next_q_no = _next_question_no(q_no, questions)

        if next_q_no:
            pattern = rf'\b{q_no}\s*[.):\-]?\s*(.+?)(?=\b{next_q_no}\s*[.):\-]|\Z)'
        else:
            pattern = rf'\b{q_no}\s*[.):\-]?\s*(.+?)(?=\Z)'

        match = re.search(pattern, text, re.DOTALL)
        if match:
            extracted = match.group(1).strip()[:1500]

        if not extracted or len(extracted.split()) < 5:
            answer_match = re.search(r'[Aa]nswer\s*[:\-]?\s*(.+)', text, re.DOTALL)
            if answer_match:
                extracted = answer_match.group(1).strip()[:1500]

        if not extracted or len(extracted.split()) < 5:
            lines_list = text.split(' ')
            filtered   = [
                w for w in lines_list
                if not re.match(r'^\d+[.):\-]?$', w.strip())
            ]
            extracted = ' '.join(filtered).strip()[:1500]

        print(f"  Essay Q{q_no}: Tier 3 fallback — {len(extracted.split())} words")

    # ── Clean TrOCR artifacts ─────────────────────────────────────────────────
    extracted = re.sub(r'\s+\.\s+', ' ', extracted)
    extracted = re.sub(r'\s{2,}',   ' ', extracted)
    extracted = extracted.strip()

    # ── Send to Groq ──────────────────────────────────────────────────────────
    result = grade_essay(
        student_answer  = extracted,
        model_answer    = model_answer,
        question_text   = question_text,
        rubric          = rubric,
        max_score       = max_score,
        ocr_confidence  = ocr_confidence,
    )

    essay_details = {
        "key_points_hit":    result["key_points_hit"],
        "key_points_missed": result["key_points_missed"],
        "relevance":         result["relevance"],
        "rubric_notes":      result["rubric_notes"],
        "extraction_tier":   result.get("extraction_tier", "unknown"),
        "ocr_confidence":    round(ocr_confidence, 3),
    }

    return (extracted, result["score"], result["feedback"], essay_details)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _next_question_no(q_no: int, questions: list) -> int:
    if not questions:
        return q_no + 1
    q_nos = sorted([q.question_no for q in questions])
    idx   = q_nos.index(q_no) if q_no in q_nos else -1
    if idx >= 0 and idx < len(q_nos) - 1:
        return q_nos[idx + 1]
    return None


def _estimate_ocr_confidence(ocr_result: dict) -> float:
    if not ocr_result:
        return 0.5
    return ocr_result.get("average_confidence", 0.5)


def _estimate_page_height(lines: list) -> int:
    if not lines:
        return 2000
    return max((l.get("y_center", 0) for l in lines), default=2000) + 200


def normalize_ocr_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def fuzzy_match(a: str, b: str) -> float:
    return SequenceMatcher(None, a.strip(), b.strip()).ratio()


# ─── Score Summary ────────────────────────────────────────────────────────────

def compute_total_score(grading_results: list) -> dict:
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


import os
