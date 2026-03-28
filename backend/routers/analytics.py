# routers/analytics.py
# Analytics endpoints — per-question stats, score distribution, AI exam analysis

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.database import get_db
from models.models import StudentPaper, StudentAnswer, Question, Exam, PaperStatus

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/exam/{exam_id}", summary="Get full analytics for an exam")
def get_exam_analytics(exam_id: int, db: Session = Depends(get_db)):
    """
    Returns detailed analytics:
    - Class statistics (avg, high, low, pass rate)
    - Score distribution by percentage buckets
    - Per-question accuracy
    - Student ranking list
    """
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    papers = db.query(StudentPaper).filter(
        StudentPaper.exam_id == exam_id,
        StudentPaper.status  == PaperStatus.graded,
    ).all()

    questions = db.query(Question).filter(
        Question.exam_id == exam_id
    ).order_by(Question.question_no).all()

    max_score = sum(q.max_score for q in questions)

    if not papers:
        return {
            "exam_id":      exam_id,
            "exam_name":    exam.name,
            "subject":      exam.subject,
            "total_graded": 0,
            "max_score":    max_score,
            "statistics":   None,
            "distribution": [],
            "per_question": [],
            "students":     [],
        }

    # ── Class statistics ──────────────────────────────────────────────────────
    scores  = [p.total_score for p in papers if p.total_score is not None]
    avg     = round(sum(scores) / len(scores), 2) if scores else 0
    high    = max(scores) if scores else 0
    low     = min(scores) if scores else 0
    avg_pct = round((avg / max_score * 100), 1) if max_score > 0 else 0
    passed  = sum(1 for s in scores if max_score > 0 and (s / max_score) >= 0.75)

    statistics = {
        "average_score":   avg,
        "average_percent": avg_pct,
        "highest_score":   high,
        "lowest_score":    low,
        "passed":          passed,
        "failed":          len(scores) - passed,
        "pass_rate":       round(passed / len(scores) * 100, 1) if scores else 0,
    }

    # ── Score distribution ────────────────────────────────────────────────────
    buckets = [
        {"label": "0–24%",   "min": 0,    "max": 0.25, "count": 0},
        {"label": "25–49%",  "min": 0.25, "max": 0.50, "count": 0},
        {"label": "50–74%",  "min": 0.50, "max": 0.75, "count": 0},
        {"label": "75–89%",  "min": 0.75, "max": 0.90, "count": 0},
        {"label": "90–100%", "min": 0.90, "max": 1.01, "count": 0},
    ]

    for score in scores:
        pct = score / max_score if max_score > 0 else 0
        for b in buckets:
            if b["min"] <= pct < b["max"]:
                b["count"] += 1
                break

    distribution = [{"label": b["label"], "count": b["count"]} for b in buckets]

    # ── Per-question accuracy ─────────────────────────────────────────────────
    paper_ids    = [p.id for p in papers]
    per_question = []

    for q in questions:
        answers = db.query(StudentAnswer).filter(
            StudentAnswer.question_id == q.id,
            StudentAnswer.paper_id.in_(paper_ids),
        ).all()

        if not answers:
            per_question.append({
                "question_no":   q.question_no,
                "question_type": q.question_type,
                "question_text": q.question_text or f"Question {q.question_no}",
                "max_score":     q.max_score,
                "avg_score":     0,
                "accuracy_pct":  0,
                "correct_count": 0,
                "total_count":   0,
            })
            continue

        final_scores = [
            (a.teacher_score if a.teacher_score is not None else a.score) or 0
            for a in answers
        ]

        avg_q   = round(sum(final_scores) / len(final_scores), 2)
        correct = sum(1 for s in final_scores if s >= q.max_score)
        acc_pct = round(correct / len(final_scores) * 100, 1)

        per_question.append({
            "question_no":   q.question_no,
            "question_type": q.question_type,
            "question_text": q.question_text or f"Question {q.question_no}",
            "max_score":     q.max_score,
            "avg_score":     avg_q,
            "accuracy_pct":  acc_pct,
            "correct_count": correct,
            "total_count":   len(final_scores),
        })

    # ── Student ranking ───────────────────────────────────────────────────────
    students = sorted([
        {
            "paper_id":     p.id,
            "student_name": p.student_name,
            "total_score":  p.total_score,
            "max_score":    max_score,
            "percentage":   round(p.total_score / max_score * 100, 1)
                            if max_score > 0 and p.total_score is not None else 0,
            "passed":       (p.total_score / max_score >= 0.75)
                            if max_score > 0 and p.total_score is not None else False,
        }
        for p in papers if p.total_score is not None
    ], key=lambda x: x["total_score"], reverse=True)

    return {
        "exam_id":      exam_id,
        "exam_name":    exam.name,
        "subject":      exam.subject,
        "total_graded": len(papers),
        "max_score":    max_score,
        "statistics":   statistics,
        "distribution": distribution,
        "per_question": per_question,
        "students":     students,
    }


@router.post("/exam/{exam_id}/ai-analysis", summary="Generate AI summary of exam results")
def get_ai_analysis(exam_id: int, db: Session = Depends(get_db)):
    """
    Uses Groq (LLaMA 3) to generate a human-readable analysis of the exam results.
    Identifies hardest questions, common mistakes, and teaching recommendations.
    """
    from services.essay_grader import get_client

    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    papers = db.query(StudentPaper).filter(
        StudentPaper.exam_id == exam_id,
        StudentPaper.status  == PaperStatus.graded,
    ).all()

    if not papers:
        return {"analysis": "No graded papers found for this exam yet."}

    questions = db.query(Question).filter(
        Question.exam_id == exam_id
    ).order_by(Question.question_no).all()

    scores    = [p.total_score for p in papers if p.total_score is not None]
    max_score = sum(q.max_score for q in questions)
    avg       = round(sum(scores) / len(scores), 2) if scores else 0
    avg_pct   = round(avg / max_score * 100, 1) if max_score > 0 else 0
    passed    = sum(1 for s in scores if max_score > 0 and s / max_score >= 0.75)

    paper_ids = [p.id for p in papers]
    q_lines   = []
    for q in questions:
        answers = db.query(StudentAnswer).filter(
            StudentAnswer.question_id == q.id,
            StudentAnswer.paper_id.in_(paper_ids),
        ).all()
        if not answers:
            continue
        final   = [(a.teacher_score if a.teacher_score is not None else a.score) or 0
                   for a in answers]
        correct = sum(1 for s in final if s >= q.max_score)
        acc     = round(correct / len(final) * 100, 1)
        q_lines.append(
            f"Q{q.question_no} ({q.question_type}, {q.max_score}pts): "
            f"{acc}% accuracy, avg {round(sum(final)/len(final),1)}/{q.max_score}"
        )

    prompt = f"""
You are an academic performance analyst reviewing exam results for a teacher.

Exam: {exam.name} — {exam.subject}
Students graded: {len(papers)}
Class average: {avg}/{max_score} ({avg_pct}%)
Students passed (≥75%): {passed}/{len(papers)}

Per-question performance:
{chr(10).join(q_lines)}

Write a 3-4 sentence analysis that:
1. States the overall class performance clearly
2. Identifies the hardest question (lowest accuracy) and easiest question
3. Suggests what the teacher might want to review or re-teach
4. Ends with one positive observation about the class

Be direct and professional. Write in paragraph form, no bullet points.
""".strip()

    try:
        client   = get_client()
        response = client.chat.completions.create(
            model       = "llama-3.1-8b-instant",
            messages    = [{"role": "user", "content": prompt}],
            temperature = 0.4,
        )
        return {"analysis": response.choices[0].message.content.strip()}

    except Exception as e:
        return {
            "analysis": f"AI analysis unavailable: {str(e)}. "
                        "Check your GROQ_API_KEY and try again."
        }
