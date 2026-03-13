import React, { useState, useEffect, useCallback } from 'react';
import UploadZone from '../components/UploadZone';
import ImagePreviewGrid from '../components/ImagePreviewGrid';
import SubmitPanel from '../components/SubmitPanel';
import { getAllExams, uploadPapers } from '../api/api';
import './UploadPage.css';

export default function UploadPage() {
  const [files, setFiles]               = useState([]);
  const [exams, setExams]               = useState([]);
  const [selectedExam, setSelectedExam] = useState('');
  const [submitting, setSubmitting]     = useState(false);
  const [submitted, setSubmitted]       = useState(false);
  const [error, setError]               = useState(null);
  const [loadingExams, setLoadingExams] = useState(true);

  // Load existing exams from backend on page load
  useEffect(() => {
    getAllExams()
      .then(data => {
        setExams(data);
        if (data.length > 0) setSelectedExam(String(data[0].id));
      })
      .catch(() => setError('Could not connect to backend. Make sure it is running on port 8000.'))
      .finally(() => setLoadingExams(false));
  }, []);

  const addFiles = useCallback((incoming) => {
    const newEntries = incoming
      .filter(f => f.type.startsWith('image/'))
      .map(f => ({
        id: `${f.name}-${f.size}-${Date.now()}-${Math.random()}`,
        file: f,
        preview: URL.createObjectURL(f),
        status: 'ready',
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

  const handleSubmit = async () => {
    if (!files.length || submitting) return;

    if (!selectedExam) {
      setError('Please select an exam before uploading. Create one in the Answer Keys page first.');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await uploadPapers(parseInt(selectedExam), files, updateFileStatus);
      setSubmitted(true);
    } catch (err) {
      setError('Something went wrong during upload. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const selectedExamData = exams.find(e => String(e.id) === selectedExam);

  return (
    <div className="upload-page">

      {/* Page header */}
      <div className="upload-header fade-up">
        <div className="upload-header-text">
          <h1>Upload Answer Sheets</h1>
          <p>Drag and drop scanned exam papers. Supports JPG, PNG, and WEBP.</p>
        </div>
        <div className="upload-header-meta">
          <span className="meta-chip">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <path d="M7 1v6M7 10v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1"/>
            </svg>
            AI-powered grading
          </span>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="alert alert-error fade-up">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M8 5v3M8 10v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          {error}
        </div>
      )}

      {/* Exam selector */}
      <div className="exam-select-row fade-up fade-up-delay-1">
        <div className="field-group">
          <label htmlFor="exam-select" className="field-label">Select Exam</label>
          {loadingExams ? (
            <div className="field-loading">Connecting to backend...</div>
          ) : exams.length === 0 ? (
            <div className="field-empty">
              No exams found. Go to <strong>Answer Keys</strong> to create one first.
            </div>
          ) : (
            <select
              id="exam-select"
              className="field-input field-select"
              value={selectedExam}
              onChange={e => setSelectedExam(e.target.value)}
            >
              {exams.map(exam => (
                <option key={exam.id} value={exam.id}>
                  {exam.name} — {exam.subject}
                </option>
              ))}
            </select>
          )}
        </div>

        {selectedExamData && (
          <div className="exam-info-chip">
            <span className="exam-info-label">Subject</span>
            <span className="exam-info-value">{selectedExamData.subject}</span>
            <span className="exam-info-sep" />
            <span className="exam-info-label">Questions</span>
            <span className="exam-info-value">{selectedExamData.questions?.length || 0}</span>
          </div>
        )}
      </div>

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
