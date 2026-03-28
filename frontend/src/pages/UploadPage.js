import React, { useState, useEffect, useCallback } from 'react';
import UploadZone from '../components/UploadZone';
import ImagePreviewGrid from '../components/ImagePreviewGrid';
import SubmitPanel from '../components/SubmitPanel';
import {
  getAllClasses, getAllExams, getClassStudents, uploadPapers,
} from '../api/api';
import './UploadPage.css';

export default function UploadPage() {
  // ── Class / Exam / Student selectors ──────────────────────────────────────
  const [classes,       setClasses]       = useState([]);
  const [selectedClass, setSelectedClass] = useState('');
  const [exams,         setExams]         = useState([]);
  const [selectedExam,  setSelectedExam]  = useState('');
  const [students,      setStudents]      = useState([]);
  const [selectedStudent, setSelectedStudent] = useState('');

  const [loadingClasses,  setLoadingClasses]  = useState(true);
  const [loadingExams,    setLoadingExams]    = useState(false);
  const [loadingStudents, setLoadingStudents] = useState(false);

  // ── Upload state ───────────────────────────────────────────────────────────
  const [files,      setFiles]      = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitted,  setSubmitted]  = useState(false);
  const [error,      setError]      = useState(null);

  // Load classes on mount
  useEffect(() => {
    getAllClasses()
      .then(data => {
        setClasses(data);
        if (data.length > 0) setSelectedClass(String(data[0].id));
      })
      .catch(() => setError('Could not connect to backend.'))
      .finally(() => setLoadingClasses(false));
  }, []);

  // Load exams when class changes
  useEffect(() => {
    if (!selectedClass) return;
    setLoadingExams(true);
    setExams([]);
    setSelectedExam('');
    setStudents([]);
    setSelectedStudent('');
    getAllExams(selectedClass)
      .then(data => {
        setExams(data);
        if (data.length > 0) setSelectedExam(String(data[0].id));
      })
      .catch(() => setError('Could not load exams.'))
      .finally(() => setLoadingExams(false));
  }, [selectedClass]);

  // Load students when class changes
  useEffect(() => {
    if (!selectedClass) return;
    setLoadingStudents(true);
    setSelectedStudent('');
    getClassStudents(selectedClass)
      .then(data => {
        setStudents(data);
        if (data.length > 0) setSelectedStudent(String(data[0].student_id));
      })
      .catch(() => setError('Could not load students.'))
      .finally(() => setLoadingStudents(false));
  }, [selectedClass]);

  // ── File handling ──────────────────────────────────────────────────────────
  const addFiles = useCallback((incoming) => {
    const newEntries = incoming
      .filter(f => f.type.startsWith('image/'))
      .map(f => ({
        id:      `${f.name}-${f.size}-${Date.now()}-${Math.random()}`,
        file:    f,
        preview: URL.createObjectURL(f),
        status:  'ready',
      }))
      .filter(entry => !files.some(ex =>
        ex.file.name === entry.file.name && ex.file.size === entry.file.size
      ));

    if (newEntries.length > 0) {
      setFiles(prev => [...prev, ...newEntries]);
      setSubmitted(false);
      setError(null);
    }
  }, [files]);

  const removeFile = useCallback((id) => {
    setFiles(prev => {
      const target = prev.find(f => f.id === id);
      if (target) URL.revokeObjectURL(target.preview);
      return prev.filter(f => f.id !== id);
    });
  }, []);

  const clearAll = useCallback(() => {
    files.forEach(f => URL.revokeObjectURL(f.preview));
    setFiles([]);
    setSubmitted(false);
    setError(null);
  }, [files]);

  const updateFileStatus = useCallback((fileId, status) => {
    setFiles(prev => prev.map(f => f.id === fileId ? { ...f, status } : f));
  }, []);

  // ── Submit ─────────────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!files.length || submitting) return;

    if (!selectedClass) {
      setError('Please select a class first.'); return;
    }
    if (!selectedExam) {
      setError('Please select an exam. Create one in Answer Keys first.'); return;
    }
    if (!selectedStudent) {
      setError('Please select a student from the class roster.'); return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await uploadPapers(
        parseInt(selectedExam),
        files,
        updateFileStatus,
        parseInt(selectedStudent),
      );
      setSubmitted(true);
    } catch (err) {
      setError('Something went wrong during upload. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const selectedExamData    = exams.find(e => String(e.id) === selectedExam);
  const selectedStudentData = students.find(s => String(s.student_id) === selectedStudent);
  const selectedClassData   = classes.find(c => String(c.id) === selectedClass);

  return (
    <div className="upload-page">

      {/* Header */}
      <div className="upload-header fade-up">
        <div className="upload-header-text">
          <h1>Upload Answer Sheets</h1>
          <p>Select a class, exam, and student — then upload the scanned answer sheet.</p>
        </div>
        <div className="upload-header-meta">
          <span className="meta-chip">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M7 1v6M7 10v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1"/>
            </svg>
            AI-powered grading
          </span>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="alert alert-error fade-up">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M8 5v3M8 10v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          {error}
        </div>
      )}

      {/* Selectors */}
      <div className="upload-selectors fade-up fade-up-delay-1">

        {/* Class */}
        <div className="field-group">
          <label className="field-label">Class</label>
          {loadingClasses ? (
            <div className="field-loading">Loading classes...</div>
          ) : classes.length === 0 ? (
            <div className="field-empty">
              No classes yet. Go to <strong>Classes</strong> to create one.
            </div>
          ) : (
            <select
              className="field-input field-select"
              value={selectedClass}
              onChange={e => setSelectedClass(e.target.value)}
            >
              {classes.map(c => (
                <option key={c.id} value={c.id}>
                  {c.name} — {c.subject}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Exam */}
        <div className="field-group">
          <label className="field-label">Exam</label>
          {loadingExams ? (
            <div className="field-loading">Loading exams...</div>
          ) : exams.length === 0 && selectedClass ? (
            <div className="field-empty">
              No exams for this class. Go to <strong>Answer Keys</strong> to create one.
            </div>
          ) : (
            <select
              className="field-input field-select"
              value={selectedExam}
              onChange={e => setSelectedExam(e.target.value)}
              disabled={!selectedClass || loadingExams}
            >
              {exams.map(exam => (
                <option key={exam.id} value={exam.id}>
                  {exam.name}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Student */}
        <div className="field-group">
          <label className="field-label">Student</label>
          {loadingStudents ? (
            <div className="field-loading">Loading students...</div>
          ) : students.length === 0 && selectedClass ? (
            <div className="field-empty">
              No students enrolled. Go to <strong>Classes</strong> to enroll students.
            </div>
          ) : (
            <select
              className="field-input field-select"
              value={selectedStudent}
              onChange={e => setSelectedStudent(e.target.value)}
              disabled={!selectedClass || loadingStudents}
            >
              {students.map(s => (
                <option key={s.student_id} value={s.student_id}>
                  {s.last_name}, {s.first_name} — {s.student_no}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Selection summary chip */}
      {selectedExamData && selectedStudentData && (
        <div className="upload-summary-chip fade-up">
          <div className="summary-chip-item">
            <span className="summary-chip-label">Class</span>
            <span className="summary-chip-val">{selectedClassData?.name}</span>
          </div>
          <div className="summary-chip-sep" />
          <div className="summary-chip-item">
            <span className="summary-chip-label">Exam</span>
            <span className="summary-chip-val">{selectedExamData.name}</span>
          </div>
          <div className="summary-chip-sep" />
          <div className="summary-chip-item">
            <span className="summary-chip-label">Student</span>
            <span className="summary-chip-val">
              {selectedStudentData.first_name} {selectedStudentData.last_name}
            </span>
          </div>
          <div className="summary-chip-sep" />
          <div className="summary-chip-item">
            <span className="summary-chip-label">Questions</span>
            <span className="summary-chip-val">{selectedExamData.questions?.length || 0}</span>
          </div>
        </div>
      )}

      {/* Upload zone */}
      <div className="fade-up fade-up-delay-2">
        <UploadZone onFilesSelected={addFiles} hasFiles={files.length > 0} />
      </div>

      {/* Preview grid */}
      {files.length > 0 && (
        <div className="fade-up">
          <ImagePreviewGrid files={files} onRemove={removeFile} />
        </div>
      )}

      {/* Submit panel */}
      <div className="fade-up fade-up-delay-3">
        <SubmitPanel
          fileCount={files.length}
          submitting={submitting}
          submitted={submitted}
          examName={selectedExamData?.name || ''}
          onSubmit={handleSubmit}
          onClear={clearAll}
        />
      </div>

    </div>
  );
}
