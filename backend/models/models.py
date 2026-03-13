# models/models.py
# Defines all database tables as Python classes

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.database import Base
import enum

# ─── Enums ────────────────────────────────────────────────────────────────────

class QuestionType(str, enum.Enum):
    essay          = "essay"
    multiple_choice = "multiple_choice"
    true_or_false  = "true_or_false"
    identification = "identification"

class PaperStatus(str, enum.Enum):
    uploaded   = "uploaded"    # Image saved, not yet processed
    processing = "processing"  # OCR / AI grading in progress
    graded     = "graded"      # Fully checked and scored
    error      = "error"       # Something went wrong

# ─── Tables ───────────────────────────────────────────────────────────────────

class Exam(Base):
    """An exam created by a teacher (e.g. Midterm Exam — Chapter 4)"""
    __tablename__ = "exams"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String(200), nullable=False)
    subject    = Column(String(200), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    questions = relationship("Question", back_populates="exam", cascade="all, delete-orphan")
    papers    = relationship("StudentPaper", back_populates="exam", cascade="all, delete-orphan")


class Question(Base):
    """A single question inside an exam with its answer key"""
    __tablename__ = "questions"

    id            = Column(Integer, primary_key=True, index=True)
    exam_id       = Column(Integer, ForeignKey("exams.id"), nullable=False)
    question_no   = Column(Integer, nullable=False)               # e.g. 1, 2, 3
    question_text = Column(Text, nullable=True)                   # Optional text of the question
    question_type = Column(Enum(QuestionType), nullable=False)
    answer_key    = Column(Text, nullable=False)                  # Correct answer or model answer
    max_score     = Column(Float, default=1.0)                    # Points for this question
    rubric        = Column(Text, nullable=True)                   # For essays: grading rubric

    exam    = relationship("Exam", back_populates="questions")
    answers = relationship("StudentAnswer", back_populates="question", cascade="all, delete-orphan")


class StudentPaper(Base):
    """An uploaded answer sheet image from one student"""
    __tablename__ = "student_papers"

    id           = Column(Integer, primary_key=True, index=True)
    exam_id      = Column(Integer, ForeignKey("exams.id"), nullable=False)
    student_name = Column(String(200), nullable=True)             # Optional: fill in after OCR
    image_path   = Column(String(500), nullable=False)            # Path to saved image file
    status       = Column(Enum(PaperStatus), default=PaperStatus.uploaded)
    total_score  = Column(Float, nullable=True)                   # Filled after grading
    max_score    = Column(Float, nullable=True)                   # Total possible score
    uploaded_at  = Column(DateTime(timezone=True), server_default=func.now())
    graded_at    = Column(DateTime(timezone=True), nullable=True)

    exam    = relationship("Exam", back_populates="papers")
    answers = relationship("StudentAnswer", back_populates="paper", cascade="all, delete-orphan")


class StudentAnswer(Base):
    """One student's answer to one question, with the AI-generated score"""
    __tablename__ = "student_answers"

    id              = Column(Integer, primary_key=True, index=True)
    paper_id        = Column(Integer, ForeignKey("student_papers.id"), nullable=False)
    question_id     = Column(Integer, ForeignKey("questions.id"), nullable=False)
    extracted_text  = Column(Text, nullable=True)    # Text from OCR (added later)
    score           = Column(Float, nullable=True)   # AI-assigned score (added later)
    feedback        = Column(Text, nullable=True)    # AI feedback for the student
    teacher_score   = Column(Float, nullable=True)   # Teacher override score
    teacher_note    = Column(Text, nullable=True)    # Teacher's comment

    paper    = relationship("StudentPaper", back_populates="answers")
    question = relationship("Question", back_populates="answers")
