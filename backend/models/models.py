# models/models.py
# Defines all database tables as Python classes
# Phase 5 update: Added Class, Student, ClassEnrollment tables
# Exam now belongs to a Class, StudentPaper now links to an enrolled Student

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.database import Base
import enum


# ─── Enums ────────────────────────────────────────────────────────────────────

class QuestionType(str, enum.Enum):
    essay           = "essay"
    multiple_choice = "multiple_choice"
    true_or_false   = "true_or_false"
    identification  = "identification"

class PaperStatus(str, enum.Enum):
    uploaded   = "uploaded"
    processing = "processing"
    graded     = "graded"
    error      = "error"


# ─── Phase 5: Class Management Tables ─────────────────────────────────────────

class Class(Base):
    """A class/section created by the teacher (e.g. BSCS 2A — Programming 1)"""
    __tablename__ = "classes"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(200), nullable=False)   # e.g. "BSCS 2A"
    subject     = Column(String(200), nullable=False)   # e.g. "Introduction to Programming"
    section     = Column(String(100), nullable=True)    # e.g. "Section A"
    school_year = Column(String(50),  nullable=True)    # e.g. "2025-2026"
    semester    = Column(String(50),  nullable=True)    # e.g. "1st Semester"
    description = Column(Text,        nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    enrollments = relationship("ClassEnrollment", back_populates="class_", cascade="all, delete-orphan")
    exams       = relationship("Exam", back_populates="class_", cascade="all, delete-orphan")


class Student(Base):
    """A student that can be enrolled in one or more classes"""
    __tablename__ = "students"

    id         = Column(Integer, primary_key=True, index=True)
    student_no = Column(String(50), unique=True, nullable=False)  # e.g. "2021-00123"
    first_name = Column(String(100), nullable=False)
    last_name  = Column(String(100), nullable=False)
    email      = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    enrollments = relationship("ClassEnrollment", back_populates="student", cascade="all, delete-orphan")
    papers      = relationship("StudentPaper", back_populates="student")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class ClassEnrollment(Base):
    """Links a student to a class — many students per class, one student in many classes"""
    __tablename__ = "class_enrollments"

    id          = Column(Integer, primary_key=True, index=True)
    class_id    = Column(Integer, ForeignKey("classes.id"), nullable=False)
    student_id  = Column(Integer, ForeignKey("students.id"), nullable=False)
    enrolled_at = Column(DateTime(timezone=True), server_default=func.now())

    # A student can only be enrolled once per class
    __table_args__ = (
        UniqueConstraint("class_id", "student_id", name="uq_class_student"),
    )

    class_   = relationship("Class",   back_populates="enrollments")
    student  = relationship("Student", back_populates="enrollments")


# ─── Existing Tables (updated for Phase 5) ────────────────────────────────────

class Exam(Base):
    """An exam created by a teacher — now belongs to a Class"""
    __tablename__ = "exams"

    id         = Column(Integer, primary_key=True, index=True)
    class_id   = Column(Integer, ForeignKey("classes.id"), nullable=True)  # nullable for backward compat
    name       = Column(String(200), nullable=False)
    subject    = Column(String(200), nullable=False)
    qr_token   = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    class_    = relationship("Class",    back_populates="exams")
    questions = relationship("Question", back_populates="exam", cascade="all, delete-orphan")
    papers    = relationship("StudentPaper", back_populates="exam", cascade="all, delete-orphan")


class Question(Base):
    """A single question inside an exam with its answer key"""
    __tablename__ = "questions"

    id            = Column(Integer, primary_key=True, index=True)
    exam_id       = Column(Integer, ForeignKey("exams.id"), nullable=False)
    question_no   = Column(Integer, nullable=False)
    question_text = Column(Text,    nullable=True)
    question_type = Column(Enum(QuestionType), nullable=False)
    answer_key    = Column(Text,  nullable=False)
    max_score     = Column(Float, default=1.0)
    rubric        = Column(Text,  nullable=True)

    exam    = relationship("Exam",          back_populates="questions")
    answers = relationship("StudentAnswer", back_populates="question", cascade="all, delete-orphan")


class StudentPaper(Base):
    """An uploaded answer sheet — now links to an enrolled Student"""
    __tablename__ = "student_papers"

    id         = Column(Integer, primary_key=True, index=True)
    exam_id    = Column(Integer, ForeignKey("exams.id"),    nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)  # nullable for backward compat

    # Kept for backward compatibility and fallback when student not matched
    student_name = Column(String(200), nullable=True)

    image_path   = Column(String(500), nullable=False)
    status       = Column(Enum(PaperStatus), default=PaperStatus.uploaded)
    total_score  = Column(Float, nullable=True)
    max_score    = Column(Float, nullable=True)
    qr_scanned   = Column(String(100), nullable=True)
    uploaded_at  = Column(DateTime(timezone=True), server_default=func.now())
    graded_at    = Column(DateTime(timezone=True), nullable=True)

    exam    = relationship("Exam",          back_populates="papers")
    student = relationship("Student",       back_populates="papers")
    answers = relationship("StudentAnswer", back_populates="paper", cascade="all, delete-orphan")


class StudentAnswer(Base):
    """One student's answer to one question with AI-generated score"""
    __tablename__ = "student_answers"

    id             = Column(Integer, primary_key=True, index=True)
    paper_id       = Column(Integer, ForeignKey("student_papers.id"), nullable=False)
    question_id    = Column(Integer, ForeignKey("questions.id"),      nullable=False)
    extracted_text = Column(Text,  nullable=True)
    score          = Column(Float, nullable=True)
    feedback       = Column(Text,  nullable=True)
    teacher_score  = Column(Float, nullable=True)
    teacher_note   = Column(Text,  nullable=True)

    paper    = relationship("StudentPaper", back_populates="answers")
    question = relationship("Question",     back_populates="answers")
