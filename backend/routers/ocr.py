# routers/ocr.py
# Endpoints for triggering OCR + automatic grading on uploaded student papers

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database.database import get_db
from models.models import StudentPaper, StudentAnswer, Question, PaperStatus
from services.ocr import extract_text_from_image, preprocess_image
from services.grader import grade_answers, compute_total_score
import cv2, os, tempfile
from datetime import datetime, timezone

router = APIRouter(prefix="/api/ocr", tags=["OCR"])


@router.post("/process/{paper_id}", summary="Run OCR + auto-grade on a single paper")
def process_paper(paper_id: int, db: Session = Depends(get_db)):
    paper = db.query(StudentPaper).filter(StudentPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    if not os.path.exists(paper.image_path):
        raise HTTPException(status_code=404, detail="Image file not found on disk")

    paper.status = PaperStatus.processing
    db.commit()

    try:
        # Step 1: OCR
        ocr_result = extract_text_from_image(paper.image_path)
        full_text  = ocr_result["full_text"]

        # Step 2: Load questions
        questions = db.query(Question).filter(
            Question.exam_id == paper.exam_id
        ).order_by(Question.question_no).all()

        if not questions:
            raise HTTPException(status_code=400, detail="This exam has no questions defined.")

        # Step 3: Grade all objective questions
        grading_results = grade_answers(full_text, questions)

        # Step 4: Save results to database
        answers    = db.query(StudentAnswer).filter(StudentAnswer.paper_id == paper_id).all()
        answer_map = {a.question_id: a for a in answers}

        for result in grading_results:
            answer = answer_map.get(result["question_id"])
            if answer:
                answer.extracted_text = result["extracted_answer"]
                answer.score          = result["score"]
                answer.feedback       = result["feedback"]
                # Append essay details to feedback if present
                if result.get("essay_details"):
                    details = result["essay_details"]
                    hit     = ", ".join(details.get("key_points_hit",    []))
                    missed  = ", ".join(details.get("key_points_missed", []))
                    extra   = f"\n\nKey points covered: {hit}" if hit else ""
                    extra  += f"\nKey points missed: {missed}"  if missed else ""
                    extra  += f"\nRubric: {details.get('rubric_notes', '')}" if details.get('rubric_notes') else ""
                    answer.feedback = (answer.feedback or "") + extra
        summary           = compute_total_score(grading_results)
        paper.total_score = summary["total_score"]
        paper.max_score   = summary["max_score"]

        if summary["pending_essays"] == 0:
            paper.status    = PaperStatus.graded
            paper.graded_at = datetime.now(timezone.utc)
        else:
            paper.status = PaperStatus.processing

        db.commit()

        return {
            "paper_id":     paper_id,
            "student_name": paper.student_name,
            "ocr": {
                "full_text":          full_text,
                "word_count":         ocr_result["word_count"],
                "average_confidence": ocr_result["average_confidence"],
            },
            "grading": {
                "results":        grading_results,
                "total_score":    summary["total_score"],
                "max_score":      summary["max_score"],
                "percentage":     summary["percentage"],
                "pending_essays": summary["pending_essays"],
            },
            "status":  paper.status,
            "message": (
                "Grading complete!" if summary["pending_essays"] == 0
                else f"Objective questions graded. {summary['pending_essays']} essay(s) pending AI grading."
            )
        }

    except HTTPException:
        raise
    except Exception as e:
        paper.status = PaperStatus.error
        db.commit()
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.post("/process-exam/{exam_id}", summary="Run OCR + grade all papers in an exam")
def process_exam_papers(
    exam_id:          int,
    background_tasks: BackgroundTasks,
    db:               Session = Depends(get_db),
):
    papers = db.query(StudentPaper).filter(
        StudentPaper.exam_id == exam_id,
        StudentPaper.status  == PaperStatus.uploaded,
    ).all()

    if not papers:
        return {"message": "No unprocessed papers found for this exam.", "queued": 0}

    paper_ids = [p.id for p in papers]
    for pid in paper_ids:
        background_tasks.add_task(run_pipeline_background, pid)

    return {
        "message":   f"Processing queued for {len(paper_ids)} paper(s).",
        "exam_id":   exam_id,
        "queued":    len(paper_ids),
        "paper_ids": paper_ids,
    }


def run_pipeline_background(paper_id: int):
    from database.database import SessionLocal
    db = SessionLocal()
    try:
        paper = db.query(StudentPaper).filter(StudentPaper.id == paper_id).first()
        if not paper or not os.path.exists(paper.image_path):
            return

        paper.status = PaperStatus.processing
        db.commit()

        ocr_result = extract_text_from_image(paper.image_path)
        full_text  = ocr_result["full_text"]

        questions = db.query(Question).filter(
            Question.exam_id == paper.exam_id
        ).order_by(Question.question_no).all()

        grading_results = grade_answers(full_text, questions)
        answer_map = {
            a.question_id: a
            for a in db.query(StudentAnswer).filter(StudentAnswer.paper_id == paper_id).all()
        }

        for result in grading_results:
            answer = answer_map.get(result["question_id"])
            if answer:
                answer.extracted_text = result["extracted_answer"]
                answer.score          = result["score"]
                answer.feedback       = result["feedback"]

        summary           = compute_total_score(grading_results)
        paper.total_score = summary["total_score"]
        paper.max_score   = summary["max_score"]

        if summary["pending_essays"] == 0:
            paper.status    = PaperStatus.graded
            paper.graded_at = datetime.now(timezone.utc)
        else:
            paper.status = PaperStatus.processing

        db.commit()
        print(f"Paper {paper_id} done: {summary['total_score']}/{summary['max_score']} pts")

    except Exception as e:
        paper = db.query(StudentPaper).filter(StudentPaper.id == paper_id).first()
        if paper:
            paper.status = PaperStatus.error
            db.commit()
        print(f"Pipeline failed for paper {paper_id}: {e}")
    finally:
        db.close()


@router.get("/preview/{paper_id}", summary="Get the preprocessed version of an image")
def get_preprocessed_preview(paper_id: int, db: Session = Depends(get_db)):
    paper = db.query(StudentPaper).filter(StudentPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    if not os.path.exists(paper.image_path):
        raise HTTPException(status_code=404, detail="Image file not found")

    try:
        processed = preprocess_image(paper.image_path)
        tmp       = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        cv2.imwrite(tmp.name, processed)
        return FileResponse(tmp.name, media_type="image/png",
                            filename=f"preview_paper_{paper_id}.png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")


@router.get("/status/{paper_id}", summary="Get OCR status and grading results for a paper")
def get_ocr_status(paper_id: int, db: Session = Depends(get_db)):
    paper = db.query(StudentPaper).filter(StudentPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    answers   = db.query(StudentAnswer).filter(StudentAnswer.paper_id == paper_id).all()
    questions = {
        q.id: q for q in db.query(Question).filter(Question.exam_id == paper.exam_id).all()
    }

    breakdown = []
    for a in answers:
        q = questions.get(a.question_id)
        breakdown.append({
            "answer_id":      a.id,
            "question_no":    q.question_no if q else None,
            "question_type":  q.question_type if q else None,
            "answer_key":     q.answer_key if q else None,
            "extracted_text": a.extracted_text,
            "score":          a.score,
            "max_score":      q.max_score if q else None,
            "feedback":       a.feedback,
        })

    return {
        "paper_id":     paper_id,
        "student_name": paper.student_name,
        "status":       paper.status,
        "total_score":  paper.total_score,
        "max_score":    paper.max_score,
        "answers":      breakdown,
    }
