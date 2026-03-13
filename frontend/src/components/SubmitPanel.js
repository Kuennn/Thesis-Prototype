import React from 'react';
import './SubmitPanel.css';

export default function SubmitPanel({ fileCount, submitting, submitted, examName, onSubmit, onClear }) {
  if (fileCount === 0 && !submitted) {
    return (
      <div className="submit-empty">
        <p>Add exam papers above to get started.</p>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="submit-success fade-up">
        <div className="success-icon" aria-hidden="true">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <circle cx="14" cy="14" r="12" fill="var(--accent)"/>
            <path d="M9 14l3.5 3.5 6.5-7" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        <div>
          <p className="success-title">All papers processed!</p>
          <p className="success-sub">
            {fileCount} paper{fileCount !== 1 ? 's' : ''} graded{examName ? ` for "${examName}"` : ''}.
            Navigate to <strong>Results</strong> to review scores.
          </p>
        </div>
        <button className="btn btn-ghost" onClick={onClear}>
          Upload more
        </button>
      </div>
    );
  }

  return (
    <div className="submit-panel">
      <div className="submit-summary">
        <span className="summary-count">{fileCount} paper{fileCount !== 1 ? 's' : ''} ready</span>
        {examName && <span className="summary-exam">{examName}</span>}
      </div>
      <div className="submit-actions">
        <button className="btn btn-ghost" onClick={onClear} disabled={submitting}>
          Clear all
        </button>
        <button
          className="btn btn-primary"
          onClick={onSubmit}
          disabled={submitting || fileCount === 0}
          aria-busy={submitting}
        >
          {submitting ? (
            <>
              <span className="btn-spinner" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <circle cx="8" cy="8" r="5.5" stroke="currentColor" strokeWidth="1.5" strokeDasharray="20" strokeDashoffset="10" strokeLinecap="round"/>
                </svg>
              </span>
              Processing papers…
            </>
          ) : (
            <>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M8 2v8M5 7l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M3 12h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              Submit for Grading
            </>
          )}
        </button>
      </div>
    </div>
  );
}
