# routers/classes.py
# CRUD endpoints for Class management

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Optional
from database.database import get_db
from models.models import Class, ClassEnrollment, Student, Exam, StudentPaper, PaperStatus

router = APIRouter(prefix="/api/classes", tags=["Classes"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class ClassIn(BaseModel):
    name:        str
    subject:     str
    section:     Optional[str] = None
    school_year: Optional[str] = None
    semester:    Optional[str] = None
    description: Optional[str] = None

class ClassOut(BaseModel):
    id:             int
    name:           str
    subject:        str
    section:        Optional[str]
    school_year:    Optional[str]
    semester:       Optional[str]
    description:    Optional[str]
    student_count:  int = 0
    exam_count:     int = 0
    class Config:
        from_attributes = True

class StudentOut(BaseModel):
    id:         int
    student_no: str
    first_name: str
    last_name:  str
    email:      Optional[str]
    class Config:
        from_attributes = True

class EnrolledStudentOut(BaseModel):
    enrollment_id:  int
    student_id:     int
    student_no:     str
    first_name:     str
    last_name:      str
    email:          Optional[str]
    total_exams:    int = 0
    average_score:  Optional[float] = None
    class Config:
        from_attributes = True


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/", response_model=ClassOut, summary="Create a new class")
def create_class(payload: ClassIn, db: Session = Depends(get_db)):
    class_ = Class(**payload.model_dump())
    db.add(class_)
    db.commit()
    db.refresh(class_)
    return _enrich_class(class_, db)


@router.get("/", response_model=List[ClassOut], summary="Get all classes")
def get_all_classes(db: Session = Depends(get_db)):
    classes = db.query(Class).order_by(Class.created_at.desc()).all()
    return [_enrich_class(c, db) for c in classes]


@router.get("/{class_id}", response_model=ClassOut, summary="Get one class")
def get_class(class_id: int, db: Session = Depends(get_db)):
    class_ = db.query(Class).filter(Class.id == class_id).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Class not found")
    return _enrich_class(class_, db)


@router.put("/{class_id}", response_model=ClassOut, summary="Update a class")
def update_class(class_id: int, payload: ClassIn, db: Session = Depends(get_db)):
    class_ = db.query(Class).filter(Class.id == class_id).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Class not found")
    for k, v in payload.model_dump().items():
        setattr(class_, k, v)
    db.commit()
    db.refresh(class_)
    return _enrich_class(class_, db)


@router.delete("/{class_id}", summary="Delete a class")
def delete_class(class_id: int, db: Session = Depends(get_db)):
    class_ = db.query(Class).filter(Class.id == class_id).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Class not found")
    db.delete(class_)
    db.commit()
    return {"message": f"Class '{class_.name}' deleted successfully"}


# ─── Enrollment ───────────────────────────────────────────────────────────────

@router.get("/{class_id}/students", summary="Get all enrolled students with performance")
def get_class_students(class_id: int, db: Session = Depends(get_db)):
    class_ = db.query(Class).filter(Class.id == class_id).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Class not found")

    enrollments = db.query(ClassEnrollment).filter(
        ClassEnrollment.class_id == class_id
    ).all()

    result = []
    for enr in enrollments:
        student = enr.student

        # Get all papers for this student in this class's exams
        class_exam_ids = [e.id for e in class_.exams]
        papers = db.query(StudentPaper).filter(
            StudentPaper.student_id == student.id,
            StudentPaper.exam_id.in_(class_exam_ids),
            StudentPaper.status == PaperStatus.graded,
        ).all() if class_exam_ids else []

        scores  = [p.total_score for p in papers if p.total_score is not None]
        max_scores = [p.max_score for p in papers if p.max_score is not None]

        avg = None
        if scores and max_scores:
            total_earned  = sum(scores)
            total_possible = sum(max_scores)
            avg = round((total_earned / total_possible * 100), 1) if total_possible > 0 else None

        result.append({
            "enrollment_id": enr.id,
            "student_id":    student.id,
            "student_no":    student.student_no,
            "first_name":    student.first_name,
            "last_name":     student.last_name,
            "email":         student.email,
            "total_exams":   len(papers),
            "average_score": avg,
        })

    return result


@router.post("/{class_id}/enroll/{student_id}", summary="Enroll a student in a class")
def enroll_student(class_id: int, student_id: int, db: Session = Depends(get_db)):
    class_ = db.query(Class).filter(Class.id == class_id).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Class not found")

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    existing = db.query(ClassEnrollment).filter(
        ClassEnrollment.class_id   == class_id,
        ClassEnrollment.student_id == student_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Student already enrolled in this class")

    enrollment = ClassEnrollment(class_id=class_id, student_id=student_id)
    db.add(enrollment)
    db.commit()
    return {"message": f"{student.full_name} enrolled in {class_.name}"}


@router.delete("/{class_id}/enroll/{student_id}", summary="Remove a student from a class")
def unenroll_student(class_id: int, student_id: int, db: Session = Depends(get_db)):
    enrollment = db.query(ClassEnrollment).filter(
        ClassEnrollment.class_id   == class_id,
        ClassEnrollment.student_id == student_id,
    ).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    db.delete(enrollment)
    db.commit()
    return {"message": "Student removed from class"}


# ─── Class Performance Summary ────────────────────────────────────────────────

@router.get("/{class_id}/performance", summary="Get class performance overview")
def get_class_performance(class_id: int, db: Session = Depends(get_db)):
    """
    Returns overall class performance across all exams:
    - Class average per exam
    - Top and bottom performers
    - Overall class average
    """
    class_ = db.query(Class).filter(Class.id == class_id).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Class not found")

    exams = db.query(Exam).filter(Exam.class_id == class_id).all()
    if not exams:
        return {
            "class_id":   class_id,
            "class_name": class_.name,
            "exams":      [],
            "summary":    None,
        }

    exam_summaries = []
    all_percentages = []

    for exam in exams:
        papers = db.query(StudentPaper).filter(
            StudentPaper.exam_id == exam.id,
            StudentPaper.status  == PaperStatus.graded,
        ).all()

        if not papers:
            continue

        scores = [
            (p.total_score / p.max_score * 100) if p.max_score and p.total_score else 0
            for p in papers
        ]
        all_percentages.extend(scores)

        exam_summaries.append({
            "exam_id":       exam.id,
            "exam_name":     exam.name,
            "total_papers":  len(papers),
            "average_pct":   round(sum(scores) / len(scores), 1) if scores else 0,
            "highest_pct":   round(max(scores), 1) if scores else 0,
            "lowest_pct":    round(min(scores), 1) if scores else 0,
            "passed":        sum(1 for s in scores if s >= 75),
            "failed":        sum(1 for s in scores if s < 75),
        })

    overall_avg = round(sum(all_percentages) / len(all_percentages), 1) if all_percentages else None

    return {
        "class_id":      class_id,
        "class_name":    class_.name,
        "subject":       class_.subject,
        "total_exams":   len(exams),
        "exams":         exam_summaries,
        "summary": {
            "overall_average": overall_avg,
            "total_students":  len(class_.enrollments),
        }
    }


# ─── Helper ───────────────────────────────────────────────────────────────────

def _enrich_class(class_: Class, db: Session) -> dict:
    """Adds student_count and exam_count to a class object."""
    student_count = db.query(ClassEnrollment).filter(
        ClassEnrollment.class_id == class_.id
    ).count()
    exam_count = db.query(Exam).filter(Exam.class_id == class_.id).count()
    return {
        "id":            class_.id,
        "name":          class_.name,
        "subject":       class_.subject,
        "section":       class_.section,
        "school_year":   class_.school_year,
        "semester":      class_.semester,
        "description":   class_.description,
        "student_count": student_count,
        "exam_count":    exam_count,
    }


# ─── CSV Import ───────────────────────────────────────────────────────────────

@router.get("/{class_id}/csv-template", summary="Download CSV template for student import")
def download_csv_template(class_id: int, db: Session = Depends(get_db)):
    """Returns a CSV template file the teacher fills in and uploads."""
    from fastapi.responses import StreamingResponse
    import io

    class_ = db.query(Class).filter(Class.id == class_id).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Class not found")

    # Build template with header + 3 example rows
    lines = [
        "student_no,first_name,last_name,email",
        "2021-00001,Juan,dela Cruz,juan.delacruz@school.edu",
        "2021-00002,Maria,Santos,maria.santos@school.edu",
        "2021-00003,Jose,Reyes,jose.reyes@school.edu",
    ]
    content  = "\n".join(lines)
    filename = f"student_import_{class_.name.replace(' ', '_')}.csv"

    return StreamingResponse(
        io.StringIO(content),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/{class_id}/import-csv", summary="Import students from CSV file")
async def import_students_csv(
    class_id: int,
    file:     UploadFile = File(...),
    db:       Session    = Depends(get_db),
):
    """
    Reads a CSV file with columns: student_no, first_name, last_name, email
    Creates new students and enrolls them in the class.
    Skips duplicates — students already enrolled are not re-added.
    Returns a summary: imported, skipped, errors.
    """
    import csv
    import io

    class_ = db.query(Class).filter(Class.id == class_id).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Class not found")

    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")  # utf-8-sig handles Excel BOM
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader  = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []

    # Normalize headers — lowercase, strip spaces
    norm = [h.lower().strip() for h in headers]
    required = {"student_no", "first_name", "last_name"}
    if not required.issubset(set(norm)):
        raise HTTPException(
            status_code=400,
            detail=f"CSV must have columns: student_no, first_name, last_name (and optionally email). "
                   f"Found: {', '.join(headers)}"
        )

    imported = []
    skipped  = []
    errors   = []

    for i, row in enumerate(reader, start=2):  # start=2 because row 1 is header
        # Normalize row keys
        row = {k.lower().strip(): v.strip() for k, v in row.items() if k}

        student_no = row.get("student_no", "").strip()
        first_name = row.get("first_name", "").strip()
        last_name  = row.get("last_name",  "").strip()
        email      = row.get("email",      "").strip() or None

        if not student_no or not first_name or not last_name:
            errors.append(f"Row {i}: missing required field (student_no, first_name, or last_name)")
            continue

        # Check if student already exists by student_no
        student = db.query(Student).filter(Student.student_no == student_no).first()

        if not student:
            # Create new student
            student = Student(
                student_no = student_no,
                first_name = first_name,
                last_name  = last_name,
                email      = email,
            )
            db.add(student)
            db.flush()

        # Check if already enrolled
        existing_enrollment = db.query(ClassEnrollment).filter(
            ClassEnrollment.class_id   == class_id,
            ClassEnrollment.student_id == student.id,
        ).first()

        if existing_enrollment:
            skipped.append(f"{first_name} {last_name} ({student_no}) — already enrolled")
            continue

        # Enroll
        enrollment = ClassEnrollment(class_id=class_id, student_id=student.id)
        db.add(enrollment)
        imported.append(f"{first_name} {last_name} ({student_no})")

    db.commit()

    return {
        "message":        f"Import complete for class '{class_.name}'",
        "total_imported": len(imported),
        "total_skipped":  len(skipped),
        "total_errors":   len(errors),
        "imported":       imported,
        "skipped":        skipped,
        "errors":         errors,
    }
