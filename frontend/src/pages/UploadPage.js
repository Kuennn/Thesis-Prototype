import React, { useState, useEffect, useCallback } from 'react';
import UploadZone from '../components/UploadZone';
import ImagePreviewGrid from '../components/ImagePreviewGrid';
import SubmitPanel from '../components/SubmitPanel';
import CameraCapture from '../components/CameraCapture';
import { getAllClasses, getAllExams, getClassStudents, uploadPapers } from '../api/api';
import './UploadPage.css';

import BASE_URL, { apiFetch } from '../config';

export default function UploadPage() {
  // ── Selectors ─────────────────────────────────────────────────────────────
  const [classes,         setClasses]         = useState([]);
  const [selectedClass,   setSelectedClass]   = useState('');
  const [exams,           setExams]           = useState([]);
  const [selectedExam,    setSelectedExam]    = useState('');
  const [students,        setStudents]        = useState([]);
  const [selectedStudent, setSelectedStudent] = useState('');

  const [loadingClasses,  setLoadingClasses]  = useState(true);
  const [loadingExams,    setLoadingExams]    = useState(false);
  const [loadingStudents, setLoadingStudents] = useState(false);

  // ── Mode: 'single' or 'batch' ─────────────────────────────────────────────
  const [uploadMode, setUploadMode] = useState('single');

  // ── Upload state ───────────────────────────────────────────────────────────
  const [files,      setFiles]      = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitted,  setSubmitted]  = useState(false);
  const [batchResult, setBatchResult] = useState(null);
  const [error,      setError]      = useState(null);
  const [showCamera, setShowCamera] = useState(false);

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
    setExams([]); setSelectedExam('');
    setStudents([]); setSelectedStudent('');
    getAllExams(selectedClass)
      .then(data => { setExams(data); if (data.length > 0) setSelectedExam(String(data[0].id)); })
      .catch(() => setError('Could not load exams.'))
      .finally(() => setLoadingExams(false));
  }, [selectedClass]);

  // Load students when class changes
  useEffect(() => {
    if (!selectedClass) return;
    setLoadingStudents(true); setSelectedStudent('');
    getClassStudents(selectedClass)
      .then(data => { setStudents(data); if (data.length > 0) setSelectedStudent(String(data[0].student_id)); })
      .catch(() => setError('Could not load students.'))
      .finally(() => setLoadingStudents(false));
  }, [selectedClass]);

  // ── File handling ──────────────────────────────────────────────────────────
  const addFiles = useCallback((incoming) => {
    const newEntries = incoming
      .filter(f => f.type.startsWith('image/'))
      .map(f => ({
        id: `${f.name}-${f.size}-${Date.now()}-${Math.random()}`,
        file: f, preview: URL.createObjectURL(f), status: 'ready',
      }))
      .filter(entry => !files.some(ex =>
        ex.file.name === entry.file.name && ex.file.size === entry.file.size
      ));
    if (newEntries.length > 0) {
      setFiles(prev => [...prev, ...newEntries]);
      setSubmitted(false); setBatchResult(null); setError(null);
    }
  }, [files]);

  const removeFile = useCallback((id) => {
    setFiles(prev => {
      const t = prev.find(f => f.id === id);
      if (t) URL.revokeObjectURL(t.preview);
      return prev.filter(f => f.id !== id);
    });
  }, []);

  const clearAll = useCallback(() => {
    files.forEach(f => URL.revokeObjectURL(f.preview));
    setFiles([]); setSubmitted(false); setBatchResult(null); setError(null);
  }, [files]);

  const updateFileStatus = useCallback((fileId, status) => {
    setFiles(prev => prev.map(f => f.id === fileId ? { ...f, status } : f));
  }, []);

  // ── Submit ─────────────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!files.length || submitting) return;
    if (!selectedClass) { setError('Please select a class.'); return; }
    if (!selectedExam)  { setError('Please select an exam.'); return; }

    if (uploadMode === 'single') {
      if (!selectedStudent) { setError('Please select a student.'); return; }
      setSubmitting(true); setError(null);
      try {
        await uploadPapers(parseInt(selectedExam), files, updateFileStatus, parseInt(selectedStudent));
        setSubmitted(true);
      } catch {
        setError('Upload failed. Please try again.');
      } finally { setSubmitting(false); }

    } else {
      // Batch mode — send to upload-batch endpoint
      setSubmitting(true); setError(null); setBatchResult(null);
      try {
        const formData = new FormData();
        formData.append('exam_id', selectedExam);
        files.forEach(entry => formData.append('papers', entry.file));
        files.forEach(entry => updateFileStatus(entry.id, 'uploading'));

        const res  = await apiFetch(`${BASE_URL}/api/papers/upload-batch`, {
          method: 'POST', body: formData,
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Batch upload failed');

        files.forEach(entry => updateFileStatus(entry.id, 'done'));
        setBatchResult(data);
        setSubmitted(true);
      } catch (err) {
        setError(err.message);
        files.forEach(entry => updateFileStatus(entry.id, 'error'));
      } finally { setSubmitting(false); }
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
          <p>Select class and exam, then upload scanned papers.</p>
        </div>
        <div className="upload-header-meta">
          <button
            className={`btn-camera ${showCamera ? 'btn-camera-active' : ''}`}
            onClick={() => setShowCamera(s => !s)}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="1" y="4" width="14" height="10" rx="2"
                stroke="currentColor" strokeWidth="1.3"/>
              <circle cx="8" cy="9" r="2.5" stroke="currentColor" strokeWidth="1.3"/>
              <path d="M5.5 4l1-2h3l1 2" stroke="currentColor"
                strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            {showCamera ? 'Hide Camera' : 'Use Camera'}
          </button>
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

      {/* Upload mode toggle */}
      <div className="upload-mode-toggle fade-up">
        <button
          className={`mode-btn ${uploadMode === 'single' ? 'mode-active' : ''}`}
          onClick={() => { setUploadMode('single'); clearAll(); }}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="7" cy="5" r="3" stroke="currentColor" strokeWidth="1.3"/>
            <path d="M2 13c0-2.76 2.24-5 5-5s5 2.24 5 5"
              stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
          </svg>
          Single Student
        </button>
        <button
          className={`mode-btn ${uploadMode === 'batch' ? 'mode-active' : ''}`}
          onClick={() => { setUploadMode('batch'); clearAll(); }}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <rect x="1" y="1" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.3"/>
            <rect x="8" y="1" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.3"/>
            <rect x="1" y="8" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.3"/>
            <rect x="8" y="8" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.3"/>
          </svg>
          Batch Auto-Match
        </button>
      </div>

      {/* Batch mode info */}
      {uploadMode === 'batch' && (
        <div className="batch-info fade-up">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.3"/>
            <path d="M8 7v4M8 5.5v.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
          </svg>
          <div>
            <strong>Batch Auto-Match</strong> — Upload multiple papers at once.
            Name your files by student number or name (e.g. <code>2023-00001.jpg</code> or <code>dela_cruz.jpg</code>)
            and the system will automatically match each paper to the right student.
            Unmatched files are still saved and can be assigned later in Results.
          </div>
        </div>
      )}

      {/* Selectors */}
      <div className="upload-selectors fade-up fade-up-delay-1">
        {/* Class */}
        <div className="field-group">
          <label className="field-label">Class</label>
          {loadingClasses ? <div className="field-loading">Loading...</div> : (
            <select className="field-input field-select" value={selectedClass}
              onChange={e => setSelectedClass(e.target.value)}>
              {classes.map(c => (
                <option key={c.id} value={c.id}>{c.name} — {c.subject}</option>
              ))}
            </select>
          )}
        </div>

        {/* Exam */}
        <div className="field-group">
          <label className="field-label">Exam</label>
          {loadingExams ? <div className="field-loading">Loading...</div> :
           exams.length === 0 ? <div className="field-empty">No exams yet — create one in Answer Keys.</div> : (
            <select className="field-input field-select" value={selectedExam}
              onChange={e => setSelectedExam(e.target.value)}
              disabled={!selectedClass || loadingExams}>
              {exams.map(exam => (
                <option key={exam.id} value={exam.id}>{exam.name}</option>
              ))}
            </select>
          )}
        </div>

        {/* Student — only in single mode */}
        {uploadMode === 'single' && (
          <div className="field-group">
            <label className="field-label">Student</label>
            {loadingStudents ? <div className="field-loading">Loading...</div> :
             students.length === 0 ? <div className="field-empty">No students enrolled.</div> : (
              <select className="field-input field-select" value={selectedStudent}
                onChange={e => setSelectedStudent(e.target.value)}
                disabled={!selectedClass || loadingStudents}>
                {students.map(s => (
                  <option key={s.student_id} value={s.student_id}>
                    {s.last_name}, {s.first_name} — {s.student_no}
                  </option>
                ))}
              </select>
            )}
          </div>
        )}
      </div>

      {/* Summary chip */}
      {selectedExamData && (uploadMode === 'batch' || selectedStudentData) && (
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
          {uploadMode === 'single' && selectedStudentData && (
            <>
              <div className="summary-chip-sep" />
              <div className="summary-chip-item">
                <span className="summary-chip-label">Student</span>
                <span className="summary-chip-val">
                  {selectedStudentData.first_name} {selectedStudentData.last_name}
                </span>
              </div>
            </>
          )}
          {uploadMode === 'batch' && (
            <>
              <div className="summary-chip-sep" />
              <div className="summary-chip-item">
                <span className="summary-chip-label">Mode</span>
                <span className="summary-chip-val" style={{ color: 'var(--accent)' }}>
                  Auto-Match
                </span>
              </div>
            </>
          )}
          <div className="summary-chip-sep" />
          <div className="summary-chip-item">
            <span className="summary-chip-label">Questions</span>
            <span className="summary-chip-val">{selectedExamData.questions?.length || 0}</span>
          </div>
        </div>
      )}

      {/* Camera */}
      {showCamera && (
        <div className="fade-up">
          <CameraCapture
            onCapture={file => { addFiles([file]); setShowCamera(false); }}
            onClose={() => setShowCamera(false)}
          />
        </div>
      )}

      {/* Upload zone */}
      {!showCamera && (
        <div className="fade-up fade-up-delay-2">
          <UploadZone onFilesSelected={addFiles} hasFiles={files.length > 0} />
        </div>
      )}

      {/* Preview grid */}
      {files.length > 0 && (
        <div className="fade-up">
          <ImagePreviewGrid files={files} onRemove={removeFile} />
        </div>
      )}

      {/* Batch result summary */}
      {batchResult && (
        <div className="batch-result fade-up">
          <div className="batch-result-title">
            ✓ Batch Upload Complete
          </div>
          <div className="batch-result-stats">
            <span className="br-stat">
              <strong>{batchResult.papers?.length || 0}</strong> uploaded
            </span>
            <span className="br-stat br-warn">
              <strong>{batchResult.unmatched_count || 0}</strong> unmatched
            </span>
            {batchResult.errors?.length > 0 && (
              <span className="br-stat br-error">
                <strong>{batchResult.errors.length}</strong> errors
              </span>
            )}
          </div>
          {batchResult.papers?.length > 0 && (
            <div className="batch-match-list">
              {batchResult.papers.map((p, i) => (
                <div key={i} className={`bm-row ${p.auto_matched ? '' : 'bm-unmatched'}`}>
                  <span className="bm-icon">{p.auto_matched ? '✓' : '?'}</span>
                  <span className="bm-file">{p.filename}</span>
                  <span className="bm-arrow">→</span>
                  <span className="bm-student">{p.matched_to}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Submit */}
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
