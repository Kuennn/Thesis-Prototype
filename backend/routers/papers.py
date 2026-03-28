# routers/papers.py
# Endpoints for uploading and managing student answer sheet images
# Phase 5 update: Upload now accepts student_id to link paper to enrolled student

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from database.database import get_db
from models.models import StudentPaper, StudentAnswer, Exam, Question, Student, PaperStatus
from PIL import Image
import shutil, os, uuid
from datetime import datetime

router = APIRouter(prefix="/api/papers", tags=["Student Papers"])

UPLOAD_DIR = "uploaded_papers"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

# ─── Schemas ──────────────────────────────────────────────────────────────────

class AnswerOut(BaseModel):
    id:             int
    question_id:    int
    extracted_text: Optional[str]
    score:          Optional[float]
    feedback:       Optional[str]
    teacher_score:  Optional[float]
    teacher_note:   Optional[str]
    class Config:
        from_attributes = True

class PaperOut(BaseModel):
    id:           int
    exam_id:      int
    student_id:   Optional[int]
    student_name: Optional[str]
    image_path:   str
    status:       str
    total_score:  Optional[float]
    max_score:    Optional[float]
    uploaded_at:  datetime
    graded_at:    Optional[datetime]
    answers:      List[AnswerOut] = []
    class Config:
        from_attributes = True

class TeacherOverride(BaseModel):
    teacher_score: float
    teacher_note:  Optional[str] = None


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/upload", summary="Upload student answer sheet images")
async def upload_papers(
    exam_id:      int              = Form(...),
    student_name: Optional[str]    = Form(None),
    student_id:   Optional[int]    = Form(None),
    papers:       List[UploadFile] = File(...),
    db:           Session          = Depends(get_db),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    # Resolve student name from student_id if provided
    resolved_name = student_name
    if student_id:
        student = db.query(Student).filter(Student.id == student_id).first()
        if student:
            resolved_name = f"{student.first_name} {student.last_name}"

    saved_papers = []

    for upload in papers:
        if upload.content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"File '{upload.filename}' is not a supported image type. Use JPG, PNG, or WEBP."
            )

        content = await upload.read()

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File '{upload.filename}' exceeds the 20MB size limit."
            )

        ext         = os.path.splitext(upload.filename)[1].lower() or ".jpg"
        unique_name = f"{uuid.uuid4().hex}{ext}"
        save_path   = os.path.join(UPLOAD_DIR, unique_name)

        with open(save_path, "wb") as f:
            f.write(content)

        try:
            with Image.open(save_path) as img:
                img.verify()
        except Exception:
            os.remove(save_path)
            raise HTTPException(
                status_code=400,
                detail=f"File '{upload.filename}' could not be read as an image."
            )

        paper = StudentPaper(
            exam_id      = exam_id,
            student_id   = student_id,
            student_name = resolved_name or upload.filename,
            image_path   = save_path,
            status       = PaperStatus.uploaded,
        )
        db.add(paper)
        db.flush()

        questions = db.query(Question).filter(Question.exam_id == exam_id).all()
        for q in questions:
            answer = StudentAnswer(paper_id=paper.id, question_id=q.id)
            db.add(answer)

        saved_papers.append({
            "id":           paper.id,
            "filename":     upload.filename,
            "saved_as":     unique_name,
            "student_name": paper.student_name,
            "student_id":   student_id,
            "status":       paper.status,
        })

    db.commit()

    return {
        "message": f"{len(saved_papers)} paper(s) uploaded for exam '{exam.name}'",
        "exam_id": exam_id,
        "papers":  saved_papers,
    }


@router.get("/exam/{exam_id}", summary="Get all papers for an exam")
def get_papers_by_exam(exam_id: int, db: Session = Depends(get_db)):
    papers = db.query(StudentPaper).filter(StudentPaper.exam_id == exam_id).all()
    result = []
    for p in papers:
        student_name = p.student_name
        if p.student_id and not student_name:
            student = db.query(Student).filter(Student.id == p.student_id).first()
            if student:
                student_name = f"{student.first_name} {student.last_name}"
        result.append({
            "id":           p.id,
            "exam_id":      p.exam_id,
            "student_id":   p.student_id,
            "student_name": student_name,
            "image_path":   p.image_path,
            "status":       p.status,
            "total_score":  p.total_score,
            "max_score":    p.max_score,
            "uploaded_at":  p.uploaded_at,
            "graded_at":    p.graded_at,
        })
    return result


@router.get("/{paper_id}", summary="Get one paper by ID")
def get_paper(paper_id: int, db: Session = Depends(get_db)):
    paper = db.query(StudentPaper).filter(StudentPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


@router.patch("/{paper_id}/override/{answer_id}", summary="Teacher overrides an AI score")
def override_score(
    paper_id:  int,
    answer_id: int,
    payload:   TeacherOverride,
    db:        Session = Depends(get_db),
):
    answer = db.query(StudentAnswer).filter(
        StudentAnswer.id       == answer_id,
        StudentAnswer.paper_id == paper_id,
    ).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")

    answer.teacher_score = payload.teacher_score
    answer.teacher_note  = payload.teacher_note

    # Recalculate total score
    all_answers = db.query(StudentAnswer).filter(
        StudentAnswer.paper_id == paper_id
    ).all()
    total = sum(
        (a.teacher_score if a.teacher_score is not None else a.score or 0)
        for a in all_answers
    )
    paper = db.query(StudentPaper).filter(StudentPaper.id == paper_id).first()
    if paper:
        paper.total_score = round(total, 2)

    db.commit()
    db.refresh(answer)
    return {"message": "Score overridden", "answer_id": answer_id, "new_total": round(total, 2)}


@router.delete("/{paper_id}", summary="Delete a paper and its image")
def delete_paper(paper_id: int, db: Session = Depends(get_db)):
    paper = db.query(StudentPaper).filter(StudentPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    if os.path.exists(paper.image_path):
        os.remove(paper.image_path)
    db.delete(paper)
    db.commit()
    return {"message": "Paper deleted successfully"}
