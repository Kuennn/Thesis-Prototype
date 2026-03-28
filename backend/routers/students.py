# routers/students.py
# CRUD endpoints for Student management

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from database.database import get_db
from models.models import Student, ClassEnrollment, StudentPaper, Exam, PaperStatus, Class

router = APIRouter(prefix="/api/students", tags=["Students"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class StudentIn(BaseModel):
    student_no: str
    first_name: str
    last_name:  str
    email:      Optional[str] = None

class StudentOut(BaseModel):
    id:         int
    student_no: str
    first_name: str
    last_name:  str
    email:      Optional[str]
    class Config:
        from_attributes = True

class StudentDetailOut(BaseModel):
    id:         int
    student_no: str
    first_name: str
    last_name:  str
    email:      Optional[str]
    classes:    List[dict] = []
    performance: List[dict] = []
    class Config:
        from_attributes = True


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/", response_model=StudentOut, summary="Create a new student")
def create_student(payload: StudentIn, db: Session = Depends(get_db)):
    existing = db.query(Student).filter(
        Student.student_no == payload.student_no
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Student with ID '{payload.student_no}' already exists"
        )
    student = Student(**payload.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.get("/", response_model=List[StudentOut], summary="Get all students")
def get_all_students(db: Session = Depends(get_db)):
    return db.query(Student).order_by(Student.last_name).all()


@router.get("/{student_id}", summary="Get one student with full performance data")
def get_student(student_id: int, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Classes enrolled in
    enrollments = db.query(ClassEnrollment).filter(
        ClassEnrollment.student_id == student_id
    ).all()

    classes = [
        {
            "class_id":   e.class_id,
            "class_name": e.class_.name,
            "subject":    e.class_.subject,
            "section":    e.class_.section,
        }
        for e in enrollments
    ]

    # Performance per exam
    papers = db.query(StudentPaper).filter(
        StudentPaper.student_id == student_id,
        StudentPaper.status     == PaperStatus.graded,
    ).all()

    performance = []
    for paper in papers:
        exam = db.query(Exam).filter(Exam.id == paper.exam_id).first()
        pct  = None
        if paper.total_score is not None and paper.max_score:
            pct = round(paper.total_score / paper.max_score * 100, 1)
        performance.append({
            "paper_id":    paper.id,
            "exam_id":     paper.exam_id,
            "exam_name":   exam.name if exam else "Unknown",
            "subject":     exam.subject if exam else "",
            "total_score": paper.total_score,
            "max_score":   paper.max_score,
            "percentage":  pct,
            "passed":      pct >= 75 if pct is not None else False,
            "graded_at":   paper.graded_at,
        })

    # Sort by most recent
    performance.sort(key=lambda x: x["graded_at"] or "", reverse=True)

    # Overall average
    scores = [p["percentage"] for p in performance if p["percentage"] is not None]
    overall_avg = round(sum(scores) / len(scores), 1) if scores else None

    return {
        "id":           student.id,
        "student_no":   student.student_no,
        "first_name":   student.first_name,
        "last_name":    student.last_name,
        "email":        student.email,
        "classes":      classes,
        "performance":  performance,
        "overall_average": overall_avg,
        "total_exams_taken": len(performance),
    }


@router.put("/{student_id}", response_model=StudentOut, summary="Update student info")
def update_student(student_id: int, payload: StudentIn, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Check student_no uniqueness if changed
    if payload.student_no != student.student_no:
        existing = db.query(Student).filter(
            Student.student_no == payload.student_no
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Student ID '{payload.student_no}' already taken"
            )

    for k, v in payload.model_dump().items():
        setattr(student, k, v)
    db.commit()
    db.refresh(student)
    return student


@router.delete("/{student_id}", summary="Delete a student")
def delete_student(student_id: int, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    db.delete(student)
    db.commit()
    return {"message": f"Student '{student.full_name}' deleted"}


@router.get("/search/{query}", summary="Search students by name or student number")
def search_students(query: str, db: Session = Depends(get_db)):
    q = f"%{query}%"
    students = db.query(Student).filter(
        (Student.student_no.ilike(q)) |
        (Student.first_name.ilike(q)) |
        (Student.last_name.ilike(q))
    ).limit(20).all()
    return students
