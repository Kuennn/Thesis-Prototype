# main.py
# Entry point for the ExamCheck AI backend

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database.database import engine, Base
from routers import exams, papers, results, ocr, analytics, omr
import os

# ─── Create all database tables on startup ────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ─── App setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ExamCheck AI — Backend API",
    description="""
    Backend for the Hybrid Automated Examination Checking System.

    ## Features
    - **Exams**     — Create exams with answer keys and rubrics
    - **Papers**    — Upload student answer sheet images
    - **Results**   — View scores, breakdowns, and summaries
    - **Analytics** — Charts, distributions, AI exam analysis
    - **OCR**       — Hybrid EasyOCR + TrOCR pipeline
    - **OMR**       — Printable answer sheets, bubble detection, QR scanning
    """,
    version="3.0.0",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Serve uploaded images as static files ────────────────────────────────────
os.makedirs("uploaded_papers", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploaded_papers"), name="uploads")

# ─── Serve generated answer sheets as static files ────────────────────────────
os.makedirs("generated_sheets", exist_ok=True)
app.mount("/sheets", StaticFiles(directory="generated_sheets"), name="sheets")

# ─── Register routers ─────────────────────────────────────────────────────────
app.include_router(exams.router)
app.include_router(papers.router)
app.include_router(results.router)
app.include_router(ocr.router)
app.include_router(analytics.router)
app.include_router(omr.router)

# ─── Root health check ────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {
        "status":  "running",
        "message": "ExamCheck AI backend is live",
        "version": "3.0.0",
        "docs":    "Visit /docs to explore the API",
    }
