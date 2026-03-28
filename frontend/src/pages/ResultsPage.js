import React, { useState, useEffect, useCallback } from 'react';
import {
  getAllExams, getPapersByExam, getExamSummary, getPaperResults,
  processPaper, overrideScore, deletePaper, detectBubbles, scanQRCode
} from '../api/api';
import './ResultsPage.css';

// ─── Score Badge ──────────────────────────────────────────────────────────────
function ScoreBadge({ score, maxScore }) {
  if (score == null || maxScore == null) return <span className="badge badge-pending">Pending</span>;
  const pct = maxScore > 0 ? (score / maxScore) * 100 : 0;
  const cls  = pct >= 75 ? 'badge-pass' : pct >= 50 ? 'badge-mid' : 'badge-fail';
  return (
    <span className={`badge ${cls}`}>
      {score}/{maxScore} <em>({Math.round(pct)}%)</em>
    </span>
  );
}

// ─── Status Pill ──────────────────────────────────────────────────────────────
function StatusPill({ status }) {
  const map = {
    uploaded:   { label: 'Uploaded',   cls: 'pill-uploaded'   },
    processing: { label: 'Processing', cls: 'pill-processing' },
    graded:     { label: 'Graded',     cls: 'pill-graded'     },
    error:      { label: 'Error',      cls: 'pill-error'      },
  };
  const { label, cls } = map[status] || { label: status, cls: '' };
  return <span className={`status-pill ${cls}`}>{label}</span>;
}

// ─── Summary Cards ────────────────────────────────────────────────────────────
function SummaryCards({ summary }) {
  const cards = [
    { label: 'Total Papers',  value: summary.total_papers  },
    { label: 'Graded',        value: summary.graded_papers },
    { label: 'Pending',       value: summary.pending       },
    {
      label: 'Average Score',
      value: summary.average_score != null
        ? `${summary.average_score}/${summary.max_score || '?'}`
        : '—'
    },
    { label: 'Highest', value: summary.highest_score ?? '—' },
    { label: 'Lowest',  value: summary.lowest_score  ?? '—' },
  ];

  return (
    <div className="summary-grid">
      {cards.map(c => (
        <div key={c.label} className="summary-card">
          <span className="summary-value">{c.value}</span>
          <span className="summary-label">{c.label}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Question Breakdown Row ───────────────────────────────────────────────────
function QuestionRow({ item, paperId, onOverrideSuccess }) {
  const [showForm,  setShowForm]  = useState(false);
  const [newScore,  setNewScore]  = useState('');
  const [newNote,   setNewNote]   = useState('');
  const [saving,    setSaving]    = useState(false);
  const [saveError, setSaveError] = useState(null);

  const finalScore = item.teacher_score ?? item.ai_score;
  const pct        = item.max_score > 0 && finalScore != null
    ? (finalScore / item.max_score) * 100 : 0;
  const correct    = finalScore != null && finalScore >= item.max_score;

  // Determine label based on question type
  const isOMR    = item.question_type === 'multiple_choice' || item.question_type === 'true_or_false';
  const readLabel = isOMR ? 'Bubble detected' : 'OCR read';

  const handleOverride = async () => {
    const score = parseFloat(newScore);
    if (isNaN(score) || score < 0 || score > item.max_score) {
      setSaveError(`Score must be between 0 and ${item.max_score}`);
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      const answerId = item.answer_id ?? item.id;
      await overrideScore(paperId, answerId, score, newNote);
      setShowForm(false);
      setNewScore('');
      setNewNote('');
      onOverrideSuccess();
    } catch (e) {
      setSaveError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={`question-row ${correct ? 'correct' : finalScore == null ? 'pending' : 'incorrect'}`}>
      <div className="qrow-left">
        <span className="qrow-number">Q{item.question_no}</span>
        <span className="qrow-type">{item.question_type?.replace('_', ' ')}</span>
      </div>

      <div className="qrow-middle">
        <div className="qrow-answers">
          <span className="qrow-label">{readLabel}</span>
          <span className="qrow-value extracted">
            {item.extracted_text || <em>nothing detected</em>}
          </span>
        </div>
        <div className="qrow-answers">
          <span className="qrow-label">Answer key</span>
          <span className="qrow-value key">{item.answer_key}</span>
        </div>
        {item.ai_feedback && (
          <p className="qrow-feedback">{item.ai_feedback}</p>
        )}
        {item.teacher_score != null && (
          <p className="qrow-override">
            ✎ Teacher override: {item.teacher_score}/{item.max_score}
            {item.teacher_note && ` — "${item.teacher_note}"`}
          </p>
        )}

        {showForm && (
          <div className="override-form">
            <div className="override-form-row">
              <div className="override-field">
                <label className="override-label">
                  New score (0 – {item.max_score})
                </label>
                <input
                  type="number"
                  className="override-input"
                  min="0"
                  max={item.max_score}
                  step="0.5"
                  value={newScore}
                  onChange={e => setNewScore(e.target.value)}
                  placeholder={`0 – ${item.max_score}`}
                  autoFocus
                />
              </div>
              <div className="override-field override-field-note">
                <label className="override-label">Note (optional)</label>
                <input
                  type="text"
                  className="override-input"
                  value={newNote}
                  onChange={e => setNewNote(e.target.value)}
                  placeholder="Reason for override..."
                />
              </div>
            </div>
            {saveError && <p className="override-error">{saveError}</p>}
            <div className="override-actions">
              <button
                className="btn btn-ghost override-btn-sm"
                onClick={() => { setShowForm(false); setSaveError(null); }}
                disabled={saving}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary override-btn-sm"
                onClick={handleOverride}
                disabled={saving}
              >
                {saving ? 'Saving...' : 'Save Override'}
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="qrow-right">
        {finalScore != null ? (
          <>
            <span className="qrow-score">{finalScore}/{item.max_score}</span>
            <div className="qrow-bar">
              <div className="qrow-bar-fill" style={{ width: `${Math.min(pct, 100)}%` }} />
            </div>
          </>
        ) : (
          <span className="qrow-pending">Pending</span>
        )}
        <button
          className="btn-override-toggle"
          onClick={() => setShowForm(f => !f)}
          title={showForm ? 'Cancel override' : 'Override score'}
        >
          ✎
        </button>
      </div>
    </div>
  );
}

// ─── Paper Detail Modal ───────────────────────────────────────────────────────
function PaperDetailPanel({ paperId, onClose, onOverrideSuccess }) {
  const [detail,  setDetail]  = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  const loadDetail = useCallback(() => {
    setLoading(true);
    getPaperResults(paperId)
      .then(setDetail)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [paperId]);

  useEffect(() => { loadDetail(); }, [loadDetail]);

  const handleOverrideSuccess = () => {
    loadDetail();
    onOverrideSuccess();
  };

  return (
    <div className="detail-panel fade-up">
      <div className="detail-header">
        <div>
          <h3>{detail?.student_name || 'Student Paper'}</h3>
          {detail && (
            <ScoreBadge score={detail.total_score} maxScore={detail.max_score} />
          )}
        </div>
        <button className="btn-icon" onClick={onClose} aria-label="Close">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </button>
      </div>

      {loading && <p className="detail-loading">Loading results...</p>}
      {error   && <p className="detail-error">{error}</p>}

      {detail && (
        <div className="detail-body">
          {detail.breakdown.length === 0 ? (
            <p className="detail-empty">No answers recorded yet.</p>
          ) : (
            detail.breakdown.map((item, i) => (
              <QuestionRow
                key={i}
                item={item}
                paperId={paperId}
                onOverrideSuccess={handleOverrideSuccess}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Results Page ────────────────────────────────────────────────────────
export default function ResultsPage() {
  const [exams,          setExams]          = useState([]);
  const [selectedExamId, setSelectedExamId] = useState('');
  const [summary,        setSummary]        = useState(null);
  const [papers,         setPapers]         = useState([]);
  const [selectedPaper,  setSelectedPaper]  = useState(null);
  const [loadingExams,   setLoadingExams]   = useState(true);
  const [loadingPapers,  setLoadingPapers]  = useState(false);
  const [processing,     setProcessing]     = useState({});
  const [error,          setError]          = useState(null);

  // Load exams on mount
  useEffect(() => {
    getAllExams()
      .then(data => {
        setExams(data);
        if (data.length > 0) setSelectedExamId(String(data[0].id));
      })
      .catch(() => setError('Could not connect to backend.'))
      .finally(() => setLoadingExams(false));
  }, []);

  // Load papers + summary when exam changes
  useEffect(() => {
    if (!selectedExamId) return;
    setLoadingPapers(true);
    setSelectedPaper(null);
    setError(null);

    Promise.all([
      getPapersByExam(selectedExamId),
      getExamSummary(selectedExamId),
    ])
      .then(([papersData, summaryData]) => {
        setPapers(papersData);
        setSummary(summaryData);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoadingPapers(false));
  }, [selectedExamId]);

  // Refresh papers list and summary
  const refreshPapers = useCallback(() => {
    if (!selectedExamId) return;
    Promise.all([
      getPapersByExam(selectedExamId),
      getExamSummary(selectedExamId),
    ]).then(([papersData, summaryData]) => {
      setPapers([...papersData]);
      setSummary({ ...summaryData });
    });
  }, [selectedExamId]);

  // Run OCR pipeline
  const handleProcessOCR = async (paperId) => {
    setProcessing(prev => ({ ...prev, [paperId]: 'ocr' }));
    setError(null);
    try {
      await processPaper(paperId);
      refreshPapers();
      if (selectedPaper === paperId) setSelectedPaper(null);
    } catch (e) {
      setError(`OCR failed: ${e.message}`);
    } finally {
      setProcessing(prev => ({ ...prev, [paperId]: null }));
    }
  };

  // Run OMR bubble detection pipeline
  const handleProcessOMR = async (paperId) => {
    setProcessing(prev => ({ ...prev, [paperId]: 'omr' }));
    setError(null);
    try {
      // Step 1: Scan QR to auto-link exam (non-fatal if it fails)
      try { await scanQRCode(paperId); } catch (_) {}
      // Step 2: Detect bubbles
      await detectBubbles(paperId);
      refreshPapers();
      if (selectedPaper === paperId) setSelectedPaper(null);
    } catch (e) {
      setError(`OMR detection failed: ${e.message}`);
    } finally {
      setProcessing(prev => ({ ...prev, [paperId]: null }));
    }
  };

  // Delete a paper
  const handleDeletePaper = async (paper, e) => {
    e.stopPropagation();
    if (!window.confirm(`Delete "${paper.student_name}"? This cannot be undone.`)) return;
    setError(null);
    try {
      await deletePaper(paper.id);
      if (selectedPaper === paper.id) setSelectedPaper(null);
      refreshPapers();
    } catch (err) {
      setError(`Delete failed: ${err.message}`);
    }
  };

  return (
    <div className="results-page">

      {/* Header */}
      <div className="results-header fade-up">
        <div>
          <h1>Results</h1>
          <p>View graded papers, scores, and per-question breakdowns.</p>
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

      {/* Exam selector */}
      <div className="results-controls fade-up fade-up-delay-1">
        <div className="field-group">
          <label className="field-label">Select Exam</label>
          {loadingExams ? (
            <div className="field-loading">Loading exams...</div>
          ) : (
            <select
              className="field-input field-select"
              value={selectedExamId}
              onChange={e => setSelectedExamId(e.target.value)}
            >
              {exams.map(exam => (
                <option key={exam.id} value={exam.id}>
                  {exam.name} — {exam.subject}
                </option>
              ))}
            </select>
          )}
        </div>
        <button
          className="btn btn-ghost"
          onClick={refreshPapers}
          disabled={!selectedExamId}
          title="Refresh"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M12 7A5 5 0 1 1 7 2c1.5 0 2.8.6 3.8 1.6L13 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            <path d="M13 2v4H9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Refresh
        </button>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="fade-up fade-up-delay-2">
          <SummaryCards summary={summary} />
        </div>
      )}

      {/* Papers list + detail panel */}
      <div className="results-body fade-up fade-up-delay-2">

        {/* Papers list */}
        <div className="papers-list">
          <div className="papers-list-header">
            <span className="field-label">
              {papers.length} paper{papers.length !== 1 ? 's' : ''}
            </span>
          </div>

          {loadingPapers ? (
            <p className="papers-loading">Loading papers...</p>
          ) : papers.length === 0 ? (
            <div className="papers-empty">
              <p>No papers uploaded for this exam yet.</p>
            </div>
          ) : (
            papers.map(paper => (
              <div
                key={paper.id}
                className={`paper-row ${selectedPaper === paper.id ? 'selected' : ''}`}
                onClick={() => setSelectedPaper(
                  selectedPaper === paper.id ? null : paper.id
                )}
              >
                <div className="paper-row-main">
                  <span className="paper-name">{paper.student_name}</span>
                  <StatusPill status={paper.status} />
                </div>
                <div className="paper-row-meta">
                  <ScoreBadge score={paper.total_score} maxScore={paper.max_score} />

                  {/* Action buttons — shown for uploaded, error, or processing */}
                  {(paper.status === 'uploaded' || paper.status === 'error' || paper.status === 'processing') && (
                    <>
                      {/* Run OCR — for handwritten identification/essay papers */}
                      <button
                        className="btn btn-process"
                        disabled={!!processing[paper.id]}
                        onClick={e => { e.stopPropagation(); handleProcessOCR(paper.id); }}
                      >
                        {processing[paper.id] === 'ocr' ? (
                          <>
                            <span className="btn-spinner">
                              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                                <circle cx="6" cy="6" r="4" stroke="currentColor" strokeWidth="1.5" strokeDasharray="16" strokeDashoffset="8" strokeLinecap="round"/>
                              </svg>
                            </span>
                            Running OCR...
                          </>
                        ) : (
                          <>
                            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                              <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1"/>
                              <path d="M4 6l2 2 3-3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                            Run OCR
                          </>
                        )}
                      </button>

                      {/* Run OMR — for bubble answer sheets */}
                      <button
                        className="btn btn-process"
                        disabled={!!processing[paper.id]}
                        onClick={e => { e.stopPropagation(); handleProcessOMR(paper.id); }}
                      >
                        {processing[paper.id] === 'omr' ? (
                          <>
                            <span className="btn-spinner">
                              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                                <circle cx="6" cy="6" r="4" stroke="currentColor" strokeWidth="1.5" strokeDasharray="16" strokeDashoffset="8" strokeLinecap="round"/>
                              </svg>
                            </span>
                            Scanning OMR...
                          </>
                        ) : (
                          <>
                            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                              <circle cx="6" cy="6" r="4" stroke="currentColor" strokeWidth="1"/>
                              <circle cx="6" cy="6" r="1.5" fill="currentColor"/>
                            </svg>
                            Run OMR
                          </>
                        )}
                      </button>
                    </>
                  )}

                  {/* Re-run buttons for already graded papers */}
                  {paper.status === 'graded' && (
                    <>
                      <button
                        className="btn btn-ghost btn-sm"
                        disabled={!!processing[paper.id]}
                        onClick={e => { e.stopPropagation(); handleProcessOCR(paper.id); }}
                        title="Re-run OCR grading"
                      >
                        Re-OCR
                      </button>
                      <button
                        className="btn btn-ghost btn-sm"
                        disabled={!!processing[paper.id]}
                        onClick={e => { e.stopPropagation(); handleProcessOMR(paper.id); }}
                        title="Re-run OMR bubble detection"
                      >
                        Re-OMR
                      </button>
                    </>
                  )}

                  {/* Delete button */}
                  <button
                    className="btn btn-danger btn-sm"
                    onClick={e => handleDeletePaper(paper, e)}
                    title="Delete paper"
                  >
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M2 2l8 8M10 2L2 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                    Delete
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Detail panel */}
        {selectedPaper && (
          <PaperDetailPanel
            key={selectedPaper}
            paperId={selectedPaper}
            onClose={() => setSelectedPaper(null)}
            onOverrideSuccess={refreshPapers}
          />
        )}
      </div>

    </div>
  );
}