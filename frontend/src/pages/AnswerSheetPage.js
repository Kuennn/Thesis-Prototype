import React, { useState, useEffect } from 'react';
import { getAllClasses, getAllExams, generateAnswerSheet, downloadAnswerSheet } from '../api/api';
import './AnswerSheetPage.css';

// ─── Step Indicator ───────────────────────────────────────────────────────────
function StepIndicator({ current }) {
  const steps = ['Select Exam', 'Generate Sheet', 'Print & Distribute'];
  return (
    <div className="step-indicator">
      {steps.map((label, i) => (
        <React.Fragment key={i}>
          <div className={`step ${i < current ? 'done' : i === current ? 'active' : ''}`}>
            <div className="step-circle">
              {i < current ? (
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M2 6l3 3 5-5" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              ) : (
                <span>{i + 1}</span>
              )}
            </div>
            <span className="step-label">{label}</span>
          </div>
          {i < steps.length - 1 && <div className={`step-line ${i < current ? 'done' : ''}`} />}
        </React.Fragment>
      ))}
    </div>
  );
}

// ─── Exam Card ────────────────────────────────────────────────────────────────
function ExamCard({ exam, selected, onClick }) {
  const mcCount    = exam.questions?.filter(q => q.question_type === 'multiple_choice').length || 0;
  const tfCount    = exam.questions?.filter(q => q.question_type === 'true_or_false').length   || 0;
  const idCount    = exam.questions?.filter(q => q.question_type === 'identification').length   || 0;
  const essayCount = exam.questions?.filter(q => q.question_type === 'essay').length            || 0;

  return (
    <div className={`exam-select-card ${selected ? 'selected' : ''}`} onClick={onClick}>
      <div className="exam-select-indicator">
        {selected && (
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="7" cy="7" r="6" fill="var(--accent)"/>
            <path d="M4 7l2.5 2.5L10 4.5" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        )}
      </div>
      <div className="exam-select-info">
        <div className="exam-select-name">{exam.name}</div>
        <div className="exam-select-subject">{exam.subject}</div>
      </div>
      <div className="exam-select-types">
        {mcCount    > 0 && <span className="type-chip chip-mc">MC ×{mcCount}</span>}
        {tfCount    > 0 && <span className="type-chip chip-tf">T/F ×{tfCount}</span>}
        {idCount    > 0 && <span className="type-chip chip-id">ID ×{idCount}</span>}
        {essayCount > 0 && <span className="type-chip chip-essay">Essay ×{essayCount}</span>}
      </div>
    </div>
  );
}

// ─── Question Preview ─────────────────────────────────────────────────────────
function QuestionPreview({ questions }) {
  const typeLabel = {
    multiple_choice: 'MC',
    true_or_false:   'T/F',
    identification:  'ID',
    essay:           'Essay',
  };
  return (
    <div className="question-preview">
      <div className="qp-header">
        <span className="field-label">Question Breakdown</span>
        <span className="qp-count">{questions.length} total</span>
      </div>
      <div className="qp-list">
        {questions.map((q, i) => (
          <div key={i} className={`qp-row qp-${q.question_type}`}>
            <span className="qp-no">Q{q.question_no}</span>
            <span className="qp-type">{typeLabel[q.question_type] || q.question_type}</span>
            <span className="qp-pts">{q.max_score} pt{q.max_score !== 1 ? 's' : ''}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Generated Sheet Card ─────────────────────────────────────────────────────
function GeneratedCard({ exam, result, onDownload, downloading }) {
  return (
    <div className="generated-card fade-up">
      <div className="generated-card-icon">
        <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
          <rect x="4" y="2" width="20" height="26" rx="2" fill="var(--accent-glow)" stroke="var(--accent)" strokeWidth="1.2"/>
          <path d="M8 9h12M8 13h12M8 17h8" stroke="var(--accent)" strokeWidth="1.2" strokeLinecap="round"/>
          <rect x="18" y="20" width="10" height="10" rx="1.5" fill="var(--accent)"/>
          <path d="M21 25l1.5 1.5L25 23" stroke="white" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
      <div className="generated-card-info">
        <div className="generated-card-title">{exam.name}</div>
        <div className="generated-card-meta">
          <span>{exam.subject}</span>
          <span className="dot">·</span>
          <span>{result.total_bubbles} bubble{result.total_bubbles !== 1 ? 's' : ''}</span>
          <span className="dot">·</span>
          <span className="qr-token">QR: {result.qr_token?.slice(0, 8)}…</span>
        </div>
      </div>
      <div className="generated-card-actions">
        <button className="btn btn-primary" onClick={onDownload} disabled={downloading}>
          {downloading ? (
            <>
              <span className="btn-spinner">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <circle cx="6" cy="6" r="4" stroke="currentColor" strokeWidth="1.5"
                    strokeDasharray="16" strokeDashoffset="8" strokeLinecap="round"/>
                </svg>
              </span>
              Preparing…
            </>
          ) : (
            <>
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                <path d="M6.5 1v8M3 6l3.5 3.5L10 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M1 11h11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              Download PDF
            </>
          )}
        </button>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function AnswerSheetPage() {
  const [classes,        setClasses]        = useState([]);
  const [selectedClass,  setSelectedClass]  = useState('');
  const [exams,          setExams]          = useState([]);
  const [selectedExam,   setSelectedExam]   = useState(null);
  const [loadingClasses, setLoadingClasses] = useState(true);
  const [loadingExams,   setLoadingExams]   = useState(false);
  const [generating,     setGenerating]     = useState(false);
  const [downloading,    setDownloading]    = useState(false);
  const [result,         setResult]         = useState(null);
  const [error,          setError]          = useState(null);

  // Load classes on mount
  useEffect(() => {
    getAllClasses()
      .then(data => {
        setClasses(data);
        if (data.length > 0) setSelectedClass(String(data[0].id));
      })
      .catch(() => setError('Could not load classes. Is the backend running?'))
      .finally(() => setLoadingClasses(false));
  }, []);

  // Load exams when class changes
  useEffect(() => {
    if (!selectedClass) return;
    setLoadingExams(true);
    setExams([]);
    setSelectedExam(null);
    setResult(null);
    getAllExams(selectedClass)
      .then(setExams)
      .catch(() => setError('Could not load exams.'))
      .finally(() => setLoadingExams(false));
  }, [selectedClass]);

  const handleSelectExam = (exam) => {
    setSelectedExam(exam);
    setResult(null);
    setError(null);
  };

  const handleGenerate = async () => {
    if (!selectedExam) return;
    setGenerating(true);
    setError(null);
    try {
      const data = await generateAnswerSheet(selectedExam.id);
      setResult(data);
    } catch (err) {
      setError(err.message || 'Failed to generate answer sheet.');
    } finally {
      setGenerating(false);
    }
  };

  const handleDownload = async () => {
    if (!selectedExam) return;
    setDownloading(true);
    try {
      await downloadAnswerSheet(selectedExam.id, selectedExam.name);
    } catch (err) {
      setError(err.message || 'Failed to download PDF.');
    } finally {
      setDownloading(false);
    }
  };

  const currentStep = result ? 2 : selectedExam ? 1 : 0;
  const selectedClassData = classes.find(c => String(c.id) === selectedClass);

  return (
    <div className="answer-sheet-page">

      {/* Header */}
      <div className="as-header fade-up">
        <div>
          <h1>Answer Sheets</h1>
          <p>Generate printable OMR answer sheets with QR codes for automatic identification.</p>
        </div>
      </div>

      {/* Step indicator */}
      <div className="fade-up fade-up-delay-1">
        <StepIndicator current={currentStep} />
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

      {/* Class selector */}
      <div className="as-class-selector fade-up">
        <div className="field-group">
          <label className="field-label">Class</label>
          {loadingClasses ? (
            <div className="field-loading">Loading classes...</div>
          ) : classes.length === 0 ? (
            <div className="field-empty">
              No classes found. Create a class in <strong>Classes</strong> first.
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
                  {c.school_year ? ` (${c.school_year})` : ''}
                </option>
              ))}
            </select>
          )}
        </div>
        {selectedClassData && (
          <div className="as-class-chip">
            <strong>{selectedClassData.student_count}</strong> students ·{' '}
            <strong>{exams.length}</strong> exams
          </div>
        )}
      </div>

      <div className="as-body">

        {/* Left — Exam selector */}
        <div className="as-panel fade-up fade-up-delay-1">
          <div className="as-panel-header">
            <span className="field-label">Select Exam</span>
            {selectedExam && (
              <button className="btn-clear" onClick={() => { setSelectedExam(null); setResult(null); }}>
                Clear
              </button>
            )}
          </div>

          {loadingExams ? (
            <p className="as-loading">Loading exams…</p>
          ) : exams.length === 0 ? (
            <div className="as-empty">
              <p>No exams for this class yet. Create one in <strong>Answer Keys</strong> first.</p>
            </div>
          ) : (
            <div className="exam-select-list">
              {exams.map(exam => (
                <ExamCard
                  key={exam.id}
                  exam={exam}
                  selected={selectedExam?.id === exam.id}
                  onClick={() => handleSelectExam(exam)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Right — Preview + Generate */}
        <div className="as-panel fade-up fade-up-delay-2">
          {!selectedExam ? (
            <div className="as-placeholder">
              <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
                <rect x="8" y="4" width="28" height="36" rx="3" stroke="var(--ink-faint)" strokeWidth="1.5"/>
                <path d="M14 14h20M14 20h20M14 26h12" stroke="var(--ink-faint)" strokeWidth="1.5" strokeLinecap="round"/>
                <circle cx="36" cy="36" r="8" fill="var(--accent-glow)" stroke="var(--accent)" strokeWidth="1.2"/>
                <path d="M33 36l2 2 4-4" stroke="var(--accent)" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              <p>Select an exam on the left to preview and generate its answer sheet.</p>
            </div>
          ) : (
            <>
              <div className="as-panel-header">
                <span className="field-label">Sheet Preview</span>
                <span className="exam-badge">{selectedExam.name}</span>
              </div>

              {selectedExam.questions?.length > 0 && (
                <QuestionPreview questions={selectedExam.questions} />
              )}

              <div className="sheet-info">
                <div className="sheet-info-row">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <rect x="1" y="1" width="12" height="12" rx="1.5" stroke="var(--accent)" strokeWidth="1.2"/>
                    <circle cx="4" cy="4.5" r="1" fill="var(--accent)"/>
                    <circle cx="7" cy="4.5" r="1" fill="var(--accent)"/>
                    <circle cx="10" cy="4.5" r="1" fill="var(--accent)"/>
                    <path d="M3 8h8" stroke="var(--accent)" strokeWidth="1" strokeLinecap="round"/>
                  </svg>
                  <span>QR code embedded for auto-identification on upload</span>
                </div>
                <div className="sheet-info-row">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <circle cx="7" cy="7" r="5" stroke="var(--accent)" strokeWidth="1.2"/>
                    <circle cx="7" cy="7" r="2" fill="var(--accent)"/>
                  </svg>
                  <span>MC and T/F questions use fillable bubble circles</span>
                </div>
                <div className="sheet-info-row">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M2 4h10M2 7h10M2 10h6" stroke="var(--accent)" strokeWidth="1.2" strokeLinecap="round"/>
                  </svg>
                  <span>Identification and essay questions use write-in lines</span>
                </div>
              </div>

              {result && (
                <GeneratedCard
                  exam={selectedExam}
                  result={result}
                  onDownload={handleDownload}
                  downloading={downloading}
                />
              )}

              {!result && (
                <button
                  className="btn btn-primary btn-generate"
                  onClick={handleGenerate}
                  disabled={generating}
                >
                  {generating ? (
                    <>
                      <span className="btn-spinner">
                        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                          <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="1.5"
                            strokeDasharray="20" strokeDashoffset="10" strokeLinecap="round"/>
                        </svg>
                      </span>
                      Generating PDF…
                    </>
                  ) : (
                    <>
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <rect x="1" y="1" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.3"/>
                        <path d="M4 7h6M7 4v6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                      </svg>
                      Generate Answer Sheet
                    </>
                  )}
                </button>
              )}

              {result && (
                <button className="btn btn-ghost btn-regenerate" onClick={handleGenerate} disabled={generating}>
                  Regenerate
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Instructions */}
      <div className="as-instructions fade-up fade-up-delay-2">
        <div className="instructions-header">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="6" stroke="var(--accent)" strokeWidth="1.3"/>
            <path d="M8 7v4M8 5v.5" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <span className="field-label">How It Works</span>
        </div>
        <div className="instructions-grid">
          <div className="instruction-step">
            <span className="instruction-no">01</span>
            <div>
              <strong>Generate</strong>
              <p>Select a class and exam then click Generate. A PDF answer sheet is created with bubbles for MC/T/F and write-in lines for ID/Essay.</p>
            </div>
          </div>
          <div className="instruction-step">
            <span className="instruction-no">02</span>
            <div>
              <strong>Print & Distribute</strong>
              <p>Download the PDF and print one copy per student. Each sheet has a unique QR code that identifies the exam.</p>
            </div>
          </div>
          <div className="instruction-step">
            <span className="instruction-no">03</span>
            <div>
              <strong>Upload & Grade</strong>
              <p>After students complete the sheet, photograph or scan it and upload via Upload Papers. The system auto-detects the exam via QR and grades MC/T/F bubbles automatically.</p>
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
