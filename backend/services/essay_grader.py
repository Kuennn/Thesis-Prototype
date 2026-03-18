# services/essay_grader.py
# Grades essay/open-ended answers using Groq API (LLaMA 3)
#
# Evaluation criteria:
#   1. Key points covered   — did the student mention the important concepts?
#   2. Relevance            — is the answer actually about the question asked?
#   3. Rubric alignment     — does it meet the teacher's grading criteria?
#
# Scoring: Balanced — partial credit for partially correct answers

from groq import Groq
import json
import re
import os
import time
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
print("Groq essay grader loaded.")

# ─── Groq Setup ───────────────────────────────────────────────────────────────

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


# ─── Main Essay Grader ────────────────────────────────────────────────────────

def grade_essay(
    student_answer:  str,
    model_answer:    str,
    question_text:   str,
    rubric:          str,
    max_score:       float,
) -> dict:
    """
    Sends the student's essay to Groq (LLaMA 3) for grading.

    Returns:
        {
            "score":             float,
            "feedback":          str,
            "key_points_hit":    list,
            "key_points_missed": list,
            "relevance":         str,
            "rubric_notes":      str,
        }
    """
    if not student_answer or not student_answer.strip():
        return {
            "score":             0.0,
            "feedback":          "No answer was detected for this essay question.",
            "key_points_hit":    [],
            "key_points_missed": [],
            "relevance":         "low",
            "rubric_notes":      "No answer provided.",
        }

    prompt = build_prompt(
        student_answer, model_answer, question_text, rubric, max_score
    )

    try:
        client = get_client()
        for attempt in range(3):  # Retry up to 3 times
            try:
                response = client.chat.completions.create(
                    model = "llama-3.1-8b-instant",
                    messages = [{"role": "user", "content": prompt}],
                    temperature = 0.3,  # Lower = more consistent grading
                )
                result = parse_groq_response(
                    response.choices[0].message.content, max_score
                )
                return result

            except Exception as retry_err:
                if "429" in str(retry_err) and attempt < 2:
                    wait = (attempt + 1) * 10  # Wait 10s, then 20s
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
        }


# ─── Prompt Builder ───────────────────────────────────────────────────────────

def build_prompt(
    student_answer: str,
    model_answer:   str,
    question_text:  str,
    rubric:         str,
    max_score:      float,
) -> str:
    rubric_section = f"Rubric / Grading Criteria:\n{rubric}" if rubric else \
                     "No specific rubric provided — use the model answer as the standard."

    return f"""
You are an expert teacher grading a student's essay answer.
Be fair and balanced — award partial credit for partially correct answers.
Do NOT be overly strict. If the student demonstrates understanding of the key concepts,
even if not perfectly worded, give appropriate credit.

===== QUESTION =====
{question_text or "Open-ended essay question"}

===== MODEL ANSWER (what a perfect answer looks like) =====
{model_answer}

===== {rubric_section} =====

===== STUDENT'S ANSWER =====
{student_answer}

===== SCORING =====
Maximum score: {max_score} points

Evaluate the student's answer based on:
1. KEY POINTS COVERED — which important concepts from the model answer did the student mention?
2. RELEVANCE — is the answer actually addressing the question? (high/medium/low)
3. RUBRIC ALIGNMENT — how well does it meet the grading criteria?

SCORING GUIDE (balanced):
- Full marks ({max_score}):      Covers all key points, highly relevant, meets rubric fully
- 75% ({max_score * 0.75:.1f}):  Covers most key points with minor gaps
- 50% ({max_score * 0.5:.1f}):   Covers some key points, partially relevant
- 25% ({max_score * 0.25:.1f}):  Minimal key points, mostly off-topic
- 0:                             No relevant content or blank

Respond ONLY with a valid JSON object — no extra text, no markdown, no backticks:
{{
  "score": <number between 0 and {max_score}>,
  "feedback": "<2-3 sentences of constructive feedback for the student>",
  "key_points_hit": ["<point 1>", "<point 2>"],
  "key_points_missed": ["<missed point 1>", "<missed point 2>"],
  "relevance": "<high|medium|low>",
  "rubric_notes": "<brief note on rubric alignment>"
}}
""".strip()


# ─── Response Parser ──────────────────────────────────────────────────────────

def parse_groq_response(response_text: str, max_score: float) -> dict:
    """
    Parses Groq's JSON response safely.
    Handles cases where the model adds extra text around the JSON.
    """
    cleaned = response_text.strip()
    cleaned = re.sub(r'^```json\s*', '', cleaned)
    cleaned = re.sub(r'^```\s*',     '', cleaned)
    cleaned = re.sub(r'```\s*$',     '', cleaned)
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to extract JSON object from response using regex
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise ValueError(f"Could not parse Groq response: {cleaned[:200]}")

    score = float(data.get("score", 0))
    score = max(0.0, min(score, max_score))  # Clamp between 0 and max_score
    score = round(score * 2) / 2             # Round to nearest 0.5

    return {
        "score":             score,
        "feedback":          str(data.get("feedback",          "No feedback provided.")),
        "key_points_hit":    list(data.get("key_points_hit",    [])),
        "key_points_missed": list(data.get("key_points_missed", [])),
        "relevance":         str(data.get("relevance",         "unknown")),
        "rubric_notes":      str(data.get("rubric_notes",      "")),
    }


# ─── Batch Essay Grader ───────────────────────────────────────────────────────

def grade_all_essays(essay_questions: list) -> list:
    """
    Grades multiple essay questions for one paper.
    Each item in essay_questions should be a dict with:
        question_id, student_answer, model_answer,
        question_text, rubric, max_score
    """
    results = []
    for q in essay_questions:
        result = grade_essay(
            student_answer = q.get("student_answer", ""),
            model_answer   = q.get("model_answer",   ""),
            question_text  = q.get("question_text",  ""),
            rubric         = q.get("rubric",         ""),
            max_score      = q.get("max_score",      1.0),
        )
        results.append({
            "question_id": q["question_id"],
            **result
        })
    return results