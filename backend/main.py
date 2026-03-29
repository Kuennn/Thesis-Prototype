# main.py
# Entry point for the ExamCheck AI backend — Phase 5: Class Management

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database.database import engine, Base
from routers import exams, papers, results, ocr, analytics, classes, students, omr
import os

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ExamCheck AI — Backend API",
    description="""
    Backend for the Hybrid Automated Examination Checking System.

    ## Features
    - **Classes** — Create and manage classes, enroll students
    - **Students** — Student profiles and performance tracking
    - **Exams** — Create exams with answer keys and rubrics
    - **Papers** — Upload and grade student answer sheets
    - **Results** — Scores, breakdowns, teacher overrides
    - **Analytics** — Charts, distributions, AI exam analysis
    - **OCR** — Hybrid EasyOCR + TrOCR pipeline
    - **OMR** — Bubble sheet detection + QR codes
    """,
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:3000",
    "https://pound-puzzles-garmin-reporter.trycloudflare.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploaded_papers", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploaded_papers"), name="uploads")

app.include_router(classes.router)
app.include_router(students.router)
app.include_router(exams.router)
app.include_router(papers.router)
app.include_router(results.router)
app.include_router(ocr.router)
app.include_router(omr.router)
app.include_router(analytics.router)

@app.get("/", tags=["Health"])
def root():
    return {
        "status":  "running",
        "message": "ExamCheck AI backend is live",
        "version": "3.0.0 — Phase 5 Class Management",
        "docs":    "Visit /docs to explore the API",
    }
