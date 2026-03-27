# routers/results.py
# Endpoints for viewing grading results and summaries

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from database.database import get_db
from models.models import StudentPaper, StudentAnswer, Question, Exam, PaperStatus

router = APIRouter(prefix="/api/results", tags=["Results"])


@router.get("/exam/{exam_id}/summary", summary="Get a summary of results for an exam")
def get_exam_summary(exam_id: int, db: Session = Depends(get_db)):
    """
    Returns overall statistics for an exam:
    total papers, how many graded, average score, highest, lowest.
    """
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    papers = db.query(StudentPaper).filter(StudentPaper.exam_id == exam_id).all()

    total      = len(papers)
    graded     = [p for p in papers if p.status == PaperStatus.graded]
    scores     = [p.total_score for p in graded if p.total_score is not None]

    return {
        "exam_id":       exam_id,
        "exam_name":     exam.name,
        "subject":       exam.subject,
        "total_papers":  total,
        "graded_papers": len(graded),
        "pending":       total - len(graded),
        "average_score": round(sum(scores) / len(scores), 2) if scores else None,
        "highest_score": max(scores) if scores else None,
        "lowest_score":  min(scores) if scores else None,
    }


@router.get("/paper/{paper_id}", summary="Get detailed results for one student paper")
def get_paper_results(paper_id: int, db: Session = Depends(get_db)):
    """
    Returns the full breakdown of one student's paper:
    each question, extracted answer, AI score, and teacher override if any.
    """
    paper = db.query(StudentPaper).filter(StudentPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    answers = db.query(StudentAnswer).filter(StudentAnswer.paper_id == paper_id).all()

    breakdown = []
    for ans in answers:
        question = db.query(Question).filter(Question.id == ans.question_id).first()
        # Use teacher override if available, otherwise use AI score
        final_score = ans.teacher_score if ans.teacher_score is not None else ans.score
        breakdown.append({
            "answer_id":        ans.id,
            "question_no":      question.question_no if question else None,
            "question_type":    question.question_type if question else None,
            "question_text":    question.question_text if question else None,
            "answer_key":       question.answer_key if question else None,
            "max_score":        question.max_score if question else None,
            "extracted_text":   ans.extracted_text,
            "ai_score":         ans.score,
            "ai_feedback":      ans.feedback,
            "teacher_score":    ans.teacher_score,
            "teacher_note":     ans.teacher_note,
            "final_score":      final_score,
            "overridden":       ans.teacher_score is not None,
        })

    return {
        "paper_id":     paper.id,
        "student_name": paper.student_name,
        "status":       paper.status,
        "total_score":  paper.total_score,
        "max_score":    paper.max_score,
        "graded_at":    paper.graded_at,
        "breakdown":    breakdown,
    }
