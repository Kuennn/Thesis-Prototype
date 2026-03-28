# routers/omr.py
import os
import json
import tempfile

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database.database import get_db
from models.models import Exam, Question, StudentPaper, StudentAnswer, PaperStatus
from services.qr_handler import generate_qr_token, scan_qr_from_image
from services.omr_generator import generate_answer_sheet
from services.bubble_detector import detect_bubbles, annotate_detection, extract_student_name

import cv2

router = APIRouter(prefix="/api/omr", tags=["OMR"])

SHEETS_DIR = "generated_sheets"
os.makedirs(SHEETS_DIR, exist_ok=True)


# ─── Generate Answer Sheet ────────────────────────────────────────────────────

@router.post("/generate/{exam_id}")
def generate_sheet(exam_id: int, db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    questions = db.query(Question).filter(
        Question.exam_id == exam_id
    ).order_by(Question.question_no).all()

    if not questions:
        raise HTTPException(status_code=400, detail="Exam has no questions defined")

    if not exam.qr_token:
        exam.qr_token = generate_qr_token()
        db.commit()
        db.refresh(exam)

    question_dicts = [
        {
            "question_no":   q.question_no,
            "question_type": q.question_type,
            "question_text": q.question_text or "",
            "answer_key":    q.answer_key,
            "max_score":     q.max_score,
        }
        for q in questions
    ]

    pdf_path = os.path.join(SHEETS_DIR, f"exam_{exam_id}_sheet.pdf")
    map_path = os.path.join(SHEETS_DIR, f"exam_{exam_id}_bubble_map.json")

    bubble_map = generate_answer_sheet(
        exam_id=exam_id,
        exam_name=exam.name,
        subject=exam.subject,
        questions=question_dicts,
        qr_token=exam.qr_token,
        output_path=pdf_path,
    )

    with open(map_path, "w") as f:
        json.dump(bubble_map, f, indent=2)

    return {
        "message":       f"Answer sheet generated for '{exam.name}'",
        "exam_id":       exam_id,
        "qr_token":      exam.qr_token,
        "pdf_path":      pdf_path,
        "bubble_map":    bubble_map,
        "total_bubbles": len(bubble_map["bubbles"]),
    }


# ─── Download PDF ─────────────────────────────────────────────────────────────

@router.get("/sheet/{exam_id}")
def download_sheet(exam_id: int):
    pdf_path = os.path.join(SHEETS_DIR, f"exam_{exam_id}_sheet.pdf")
    if not os.path.exists(pdf_path):
        raise HTTPException(
            status_code=404,
            detail="Answer sheet not generated yet. Call POST /api/omr/generate/{exam_id} first."
        )
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"answer_sheet_exam_{exam_id}.pdf",
    )


# ─── Get Bubble Map ───────────────────────────────────────────────────────────

@router.get("/bubble-map/{exam_id}")
def get_bubble_map(exam_id: int):
    map_path = os.path.join(SHEETS_DIR, f"exam_{exam_id}_bubble_map.json")
    if not os.path.exists(map_path):
        raise HTTPException(status_code=404, detail="Bubble map not found. Generate the answer sheet first.")
    with open(map_path) as f:
        bubble_map = json.load(f)
    return bubble_map


# ─── Scan QR Code ─────────────────────────────────────────────────────────────

@router.post("/scan-qr/{paper_id}")
def scan_qr(paper_id: int, db: Session = Depends(get_db)):
    paper = db.query(StudentPaper).filter(StudentPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    if not os.path.exists(paper.image_path):
        raise HTTPException(status_code=404, detail="Image file not found")

    payload = scan_qr_from_image(paper.image_path)

    if not payload:
        return {
            "found":    False,
            "paper_id": paper_id,
            "message":  "No QR code detected on this sheet",
        }

    token = payload.get("token")
    exam  = db.query(Exam).filter(Exam.qr_token == token).first()

    if not exam:
        return {
            "found":    False,
            "paper_id": paper_id,
            "message":  f"QR code found but token '{token}' does not match any exam",
        }

    if paper.exam_id != exam.id:
        paper.exam_id = exam.id

    paper.qr_scanned = token
    db.commit()

    return {
        "found":     True,
        "paper_id":  paper_id,
        "exam_id":   exam.id,
        "exam_name": exam.name,
        "qr_token":  token,
        "message":   f"QR matched — paper linked to exam '{exam.name}'",
    }


# ─── Detect Bubbles ───────────────────────────────────────────────────────────

@router.post("/detect-bubbles/{paper_id}")
def detect_paper_bubbles(paper_id: int, db: Session = Depends(get_db)):
    paper = db.query(StudentPaper).filter(StudentPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    if not os.path.exists(paper.image_path):
        raise HTTPException(status_code=404, detail="Image file not found")

    map_path = os.path.join(SHEETS_DIR, f"exam_{paper.exam_id}_bubble_map.json")
    if not os.path.exists(map_path):
        raise HTTPException(
            status_code=400,
            detail="Bubble map not found. Generate the answer sheet first."
        )

    with open(map_path) as f:
        bubble_map = json.load(f)

    # Run bubble detection
    try:
        detection = detect_bubbles(paper.image_path, bubble_map)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bubble detection failed: {str(e)}")

    detected_answers = detection["answers"]

    # Extract student name
    try:
        name = extract_student_name(paper.image_path)
        if name and not paper.student_name:
            paper.student_name = name
    except Exception as e:
        print(f"Name extraction failed for paper {paper_id}: {e}")

    # Load questions
    questions = db.query(Question).filter(
        Question.exam_id == paper.exam_id
    ).order_by(Question.question_no).all()

    q_map = {q.question_no: q for q in questions}

    existing_answers = {
        a.question_id: a
        for a in db.query(StudentAnswer).filter(StudentAnswer.paper_id == paper_id).all()
    }

    omr_types = {"multiple_choice", "true_or_false"}
    saved     = []
    not_found = []

    for q_no_str, choice in detected_answers.items():
        q_no = int(q_no_str)
        q    = q_map.get(q_no)
        if not q:
            not_found.append(q_no)
            continue

        if q.question_type not in omr_types:
            continue

        detected = choice.strip().upper()
        key      = q.answer_key.strip().upper()

        if q.question_type == "true_or_false":
            detected = "TRUE"  if detected in ("T", "TRUE")  else "FALSE"
            key      = "TRUE"  if key      in ("T", "TRUE")  else "FALSE"

        is_correct = detected == key
        score      = q.max_score if is_correct else 0.0
        feedback   = (
            f"Correct! Bubble detected: {choice}."
            if is_correct else
            f"Bubble detected: {choice}. Correct answer: {q.answer_key}."
        )

        answer = existing_answers.get(q.id)
        if answer:
            answer.extracted_text = choice
            answer.score          = score
            answer.feedback       = feedback
        else:
            answer = StudentAnswer(
                paper_id=paper_id,
                question_id=q.id,
                extracted_text=choice,
                score=score,
                feedback=feedback,
            )
            db.add(answer)

        saved.append({
            "question_no": q_no,
            "detected":    choice,
            "correct":     q.answer_key,
            "is_correct":  is_correct,
            "score":       score,
        })

    # Roll up total score onto the paper
    all_answers = db.query(StudentAnswer).filter(StudentAnswer.paper_id == paper_id).all()
    paper.total_score = sum(
        (a.teacher_score if a.teacher_score is not None else a.score or 0)
        for a in all_answers
    )
    paper.max_score = sum(q.max_score for q in questions)
    paper.status    = PaperStatus.graded

    db.commit()

    return {
        "paper_id":         paper_id,
        "student_name":     paper.student_name,
        "detected_answers": detected_answers,
        "saved":            saved,
        "not_found":        not_found,
        "raw_fill_ratios":  detection["raw"],
        "message":          f"Bubble detection complete. {len(saved)} answer(s) saved.",
    }


# ─── Annotated Debug Preview ──────────────────────────────────────────────────

@router.get("/annotated/{paper_id}")
def get_annotated(paper_id: int, db: Session = Depends(get_db)):
    paper = db.query(StudentPaper).filter(StudentPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    map_path = os.path.join(SHEETS_DIR, f"exam_{paper.exam_id}_bubble_map.json")
    if not os.path.exists(map_path):
        raise HTTPException(status_code=400, detail="Bubble map not found")

    with open(map_path) as f:
        bubble_map = json.load(f)

    answers_db = db.query(StudentAnswer).filter(StudentAnswer.paper_id == paper_id).all()
    questions  = {
        q.id: q for q in db.query(Question).filter(Question.exam_id == paper.exam_id).all()
    }
    answers_dict = {
        questions[a.question_id].question_no: a.extracted_text
        for a in answers_db if a.question_id in questions
    }

    annotated = annotate_detection(
        paper.image_path,
        bubble_map,
        {"answers": answers_dict},
    )

    if annotated is None:
        raise HTTPException(status_code=500, detail="Could not annotate image")

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    cv2.imwrite(tmp.name, annotated)

    return FileResponse(tmp.name, media_type="image/png",
                        filename=f"annotated_paper_{paper_id}.png")