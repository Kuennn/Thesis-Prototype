# services/essay_grader.py
# Phase 9 — OCR Accuracy Rework
#
# Changes from Phase 8:
#   - Prompt now receives ocr_confidence so LLaMA knows how reliable
#     the extracted text is. Low-confidence extractions get a note
#     telling the model to be lenient with OCR errors.
#   - Model upgraded to llama-3.1-8b-instant (was llama3-8b-8192)
#   - Stronger JSON enforcement in the prompt and parser
#   - extraction_tier passed back in result for grader.py logging

from groq import Groq
import json
import re
import os
import time
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

_client = None


def get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY not found. "
                "Make sure your .env file has GROQ_API_KEY=your_key_here"
            )
        _client = Groq(api_key=api_key)
        print("Groq client loaded.")
    return _client


def grade_essay(
    student_answer:  str,
    model_answer:    str,
    question_text:   str,
    rubric:          str,
    max_score:       float,
    ocr_confidence:  float = 1.0,   # Phase 9: passed from grader.py
) -> dict:
    """
    Grades a student essay using Groq LLaMA 3.1.
    Phase 9: ocr_confidence adjusts the prompt's leniency instruction.
    """
    if not student_answer or not student_answer.strip():
        return {
            "score":             0.0,
            "feedback":          "No answer was detected for this essay question.",
            "key_points_hit":    [],
            "key_points_missed": [],
            "relevance":         "low",
            "rubric_notes":      "No answer provided.",
            "extraction_tier":   "none",
        }

    prompt = build_prompt(
        student_answer, model_answer, question_text,
        rubric, max_score, ocr_confidence
    )

    try:
        client = get_client()
        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model       = "llama-3.1-8b-instant",
                    messages    = [{"role": "user", "content": prompt}],
                    temperature = 0.2,   # Phase 9: lowered from 0.3 for consistency
                    max_tokens  = 512,
                )
                result = parse_groq_response(
                    response.choices[0].message.content, max_score
                )
                return result

            except Exception as retry_err:
                if "429" in str(retry_err) and attempt < 2:
                    wait = (attempt + 1) * 10
                    print(f"Rate limited, retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    raise retry_err

    except ValueError as e:
        raise e

    except Exception as e:
        print(f"Groq API error: {e}")
        return {
            "score":             None,
            "feedback":          f"AI grading temporarily unavailable. Error: {str(e)}",
            "key_points_hit":    [],
            "key_points_missed": [],
            "relevance":         "unknown",
            "rubric_notes":      "Could not grade — please try again or grade manually.",
            "extraction_tier":   "error",
        }


def build_prompt(
    student_answer:  str,
    model_answer:    str,
    question_text:   str,
    rubric:          str,
    max_score:       float,
    ocr_confidence:  float = 1.0,
) -> str:
    rubric_section = (
        f"Rubric / Grading Criteria:\n{rubric}"
        if rubric
        else "No specific rubric provided — use the model answer as the standard."
    )

    # Phase 9: OCR quality note — warn LLaMA if text extraction was uncertain
    if ocr_confidence < 0.5:
        ocr_note = (
            "IMPORTANT: The student's answer was extracted via handwriting OCR "
            f"with low confidence ({ocr_confidence:.0%}). There may be spelling "
            "errors, missing words, or garbled characters due to OCR limitations "
            "— not the student's fault. Grade based on the meaning and concepts "
            "present, not exact wording. Be generous with OCR artifacts."
        )
    elif ocr_confidence < 0.75:
        ocr_note = (
            "Note: The student's answer was extracted via handwriting OCR "
            f"(confidence: {ocr_confidence:.0%}). Minor OCR errors in spelling "
            "or punctuation may be present — grade based on demonstrated understanding."
        )
    else:
        ocr_note = (
            "The student's answer was extracted via handwriting OCR "
            f"(confidence: {ocr_confidence:.0%})."
        )

    return f"""You are a teacher grading a student's handwritten essay answer.
Award partial credit fairly — a student who demonstrates understanding of key concepts
deserves credit even if their wording differs from the model answer.

{ocr_note}

===== QUESTION =====
{question_text or "Open-ended essay question"}

===== MODEL ANSWER =====
{model_answer}

===== {rubric_section} =====

===== STUDENT ANSWER =====
{student_answer}

===== INSTRUCTIONS =====
Maximum score: {max_score} points

Evaluate on:
1. Key concepts covered (vs model answer)
2. Relevance to the question
3. Rubric alignment

Scoring guide:
- {max_score} pts   : Covers all key concepts, fully relevant, meets rubric
- {max_score*0.75:.1f} pts : Covers most concepts, minor gaps
- {max_score*0.5:.1f} pts  : Covers some concepts, partially relevant
- {max_score*0.25:.1f} pts : Minimal concepts, mostly off-topic
- 0 pts   : No relevant content

Respond with ONLY a raw JSON object. No markdown, no backticks, no extra text.
The response must start with {{ and end with }}:

{{
  "score": <number 0 to {max_score}>,
  "feedback": "<2-3 sentences of constructive feedback>",
  "key_points_hit": ["<concept 1>", "<concept 2>"],
  "key_points_missed": ["<missed concept 1>"],
  "relevance": "<high|medium|low>",
  "rubric_notes": "<one sentence on rubric alignment>"
}}""".strip()


def parse_groq_response(response_text: str, max_score: float) -> dict:
    cleaned = response_text.strip()

    # Strip markdown code fences if present
    cleaned = re.sub(r'^```json\s*', '', cleaned)
    cleaned = re.sub(r'^```\s*',     '', cleaned)
    cleaned = re.sub(r'```\s*$',     '', cleaned)
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                raise ValueError(f"Could not parse Groq response: {cleaned[:200]}")
        else:
            raise ValueError(f"No JSON found in Groq response: {cleaned[:200]}")

    score = float(data.get("score", 0))
    score = max(0.0, min(score, max_score))
    score = round(score * 2) / 2   # Round to nearest 0.5

    return {
        "score":             score,
        "feedback":          str(data.get("feedback",          "No feedback provided.")),
        "key_points_hit":    list(data.get("key_points_hit",    [])),
        "key_points_missed": list(data.get("key_points_missed", [])),
        "relevance":         str(data.get("relevance",         "unknown")),
        "rubric_notes":      str(data.get("rubric_notes",      "")),
        "extraction_tier":   "groq",
    }


def grade_all_essays(essay_questions: list) -> list:
    results = []
    for q in essay_questions:
        result = grade_essay(
            student_answer  = q.get("student_answer",  ""),
            model_answer    = q.get("model_answer",    ""),
            question_text   = q.get("question_text",   ""),
            rubric          = q.get("rubric",          ""),
            max_score       = q.get("max_score",       1.0),
            ocr_confidence  = q.get("ocr_confidence",  1.0),
        )
        results.append({
            "question_id": q["question_id"],
            **result
        })
    return results
