# ExamCheck AI — Backend

FastAPI backend for the Hybrid Automated Examination Checking System thesis.

## Project Structure

```
backend/
├── main.py                  ← App entry point, starts the server
├── requirements.txt         ← Python dependencies
├── database/
│   └── database.py          ← SQLite connection + session setup
├── models/
│   └── models.py            ← All database tables (Exam, Question, Paper, Answer)
├── routers/
│   ├── exams.py             ← POST/GET /api/exams
│   ├── papers.py            ← POST /api/papers/upload, GET /api/papers
│   └── results.py           ← GET /api/results
└── uploaded_papers/         ← Saved student answer sheet images (auto-created)
```

## Setup & Running

```bash
# 1. Create a virtual environment
python -m venv venv

# 2. Activate it
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the server
uvicorn main:app --reload
```

Server runs at: `http://localhost:8000`  
Interactive API docs: `http://localhost:8000/docs`

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/` | Health check |
| POST   | `/api/exams/` | Create exam + answer key |
| GET    | `/api/exams/` | List all exams |
| GET    | `/api/exams/{id}` | Get one exam |
| POST   | `/api/papers/upload` | Upload student paper images |
| GET    | `/api/papers/exam/{exam_id}` | Get all papers for an exam |
| GET    | `/api/papers/{id}` | Get one paper |
| PATCH  | `/api/papers/{id}/override/{answer_id}` | Teacher score override |
| GET    | `/api/results/exam/{exam_id}/summary` | Exam results summary |
| GET    | `/api/results/paper/{paper_id}` | Per-student result breakdown |

## Database Tables

- **exams** — Exam name, subject, date created
- **questions** — Questions per exam with answer keys and rubrics
- **student_papers** — Uploaded image path, student name, grading status
- **student_answers** — Per-question: extracted text, AI score, teacher override

## Coming Next

- OCR with EasyOCR / Tesseract to extract text from uploaded images
- AI essay grading via OpenAI or Gemini API
- Authentication (teacher login)
