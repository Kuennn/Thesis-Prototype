# routers/exams.py
# Endpoints for creating and retrieving exams

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from database.database import get_db
from models.models import Exam, Question, QuestionType

router = APIRouter(prefix="/api/exams", tags=["Exams"])

# ─── Pydantic Schemas (request/response shapes) ───────────────────────────────

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
    questions: List[QuestionIn] = []

class QuestionOut(QuestionIn):
    id: int
    exam_id: int
    class Config:
        from_attributes = True

class ExamOut(BaseModel):
    id:         int
    name:       str
    subject:    str
    questions:  List[QuestionOut] = []
    class Config:
        from_attributes = True

# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/", response_model=ExamOut, summary="Create a new exam with its answer key")
def create_exam(payload: ExamIn, db: Session = Depends(get_db)):
    """
    Creates an exam and saves all its questions + answer keys to the database.
    Call this before uploading student papers.
    """
    exam = Exam(name=payload.name, subject=payload.subject)
    db.add(exam)
    db.flush()  # Get the exam ID before committing

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
def get_all_exams(db: Session = Depends(get_db)):
    return db.query(Exam).order_by(Exam.created_at.desc()).all()


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
