# routers/exams.py
# Endpoints for creating and retrieving exams
# Phase 5 update: Exams now belong to a Class

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from database.database import get_db
from models.models import Exam, Question, QuestionType, Class, ClassEnrollment

router = APIRouter(prefix="/api/exams", tags=["Exams"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class QuestionIn(BaseModel):
    question_no:   int
    question_text: Optional[str] = None
    question_type: QuestionType
    answer_key:    str
    max_score:     float = 1.0
    rubric:        Optional[str] = None

class ExamIn(BaseModel):
    name:      str
    subject:   str
    class_id:  Optional[int] = None   # Required for new exams, optional for backward compat
    questions: List[QuestionIn] = []

class QuestionOut(QuestionIn):
    id:      int
    exam_id: int
    class Config:
        from_attributes = True

class ExamOut(BaseModel):
    id:        int
    name:      str
    subject:   str
    class_id:  Optional[int]
    questions: List[QuestionOut] = []
    class Config:
        from_attributes = True


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/", response_model=ExamOut, summary="Create a new exam with answer key")
def create_exam(payload: ExamIn, db: Session = Depends(get_db)):
    # Validate class exists if class_id provided
    if payload.class_id:
        class_ = db.query(Class).filter(Class.id == payload.class_id).first()
        if not class_:
            raise HTTPException(status_code=404, detail="Class not found")

    exam = Exam(
        name     = payload.name,
        subject  = payload.subject,
        class_id = payload.class_id,
    )
    db.add(exam)
    db.flush()

    for q in payload.questions:
        question = Question(
            exam_id       = exam.id,
            question_no   = q.question_no,
            question_text = q.question_text,
            question_type = q.question_type,
            answer_key    = q.answer_key,
            max_score     = q.max_score,
            rubric        = q.rubric,
        )
        db.add(question)

    db.commit()
    db.refresh(exam)
    return exam


@router.get("/", response_model=List[ExamOut], summary="Get all exams")
def get_all_exams(class_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Get all exams. Optionally filter by class_id."""
    query = db.query(Exam)
    if class_id:
        query = query.filter(Exam.class_id == class_id)
    return query.order_by(Exam.created_at.desc()).all()


@router.get("/{exam_id}", response_model=ExamOut, summary="Get one exam by ID")
def get_exam(exam_id: int, db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


@router.delete("/{exam_id}", summary="Delete an exam")
def delete_exam(exam_id: int, db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    db.delete(exam)
    db.commit()
    return {"message": f"Exam '{exam.name}' deleted successfully"}
