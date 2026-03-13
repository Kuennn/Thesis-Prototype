# main.py
# Entry point for the ExamCheck AI backend

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database.database import engine, Base
from routers import exams, papers, results, ocr
import os

# ─── Create all database tables on startup ────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ─── App setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ExamCheck AI — Backend API",
    description="""
    Backend for the Hybrid Automated Examination Checking System.

    ## Features
    - **Exams** — Create exams with answer keys and rubrics
    - **Papers** — Upload student answer sheet images
    - **Results** — View scores, breakdowns, and summaries

    ## Coming Soon
    - OCR text extraction from uploaded images
    - AI essay grading via OpenAI / Gemini
    """,
    version="1.0.0",
)

# ─── CORS — allows the React frontend to talk to this backend ─────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Serve uploaded images as static files ────────────────────────────────────
os.makedirs("uploaded_papers", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploaded_papers"), name="uploads")

# ─── Register routers ─────────────────────────────────────────────────────────
app.include_router(exams.router)
app.include_router(papers.router)
app.include_router(results.router)
app.include_router(ocr.router)

# ─── Root health check ────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {
        "status":  "running",
        "message": "ExamCheck AI backend is live",
        "docs":    "Visit /docs to explore the API",
    }
