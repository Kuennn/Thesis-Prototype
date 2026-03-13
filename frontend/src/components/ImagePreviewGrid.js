import React from 'react';
import './ImagePreviewGrid.css';

const STATUS_ICONS = {
  ready: null,
  uploading: (
    <span className="status-spinner" aria-label="Uploading">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="20" strokeDashoffset="10" strokeLinecap="round"/>
      </svg>
    </span>
  ),
  done: (
    <span className="status-done" aria-label="Done">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="8" r="6" fill="var(--accent)"/>
        <path d="M5.5 8l2 2 3-3" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    </span>
  ),
  error: (
    <span className="status-error" aria-label="Error">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="8" r="6" fill="var(--danger)"/>
        <path d="M6 6l4 4M10 6l-4 4" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    </span>
  ),
};

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ImagePreviewGrid({ files, onRemove }) {
  return (
    <div className="preview-section">
      <div className="preview-header">
        <span className="preview-count">{files.length} paper{files.length !== 1 ? 's' : ''} queued</span>
      </div>
      <div className="preview-grid">
        {files.map((entry, idx) => (
          <div
            key={entry.id}
            className={`preview-card ${entry.status}`}
            style={{ animationDelay: `${idx * 0.05}s` }}
          >
            {/* Thumbnail */}
            <div className="preview-thumb">
              <img
                src={entry.preview}
                alt={entry.file.name}
                loading="lazy"
              />
              {/* Overlay shimmer while uploading */}
              {entry.status === 'uploading' && (
                <div className="thumb-shimmer" aria-hidden="true" />
              )}
            </div>

            {/* Info row */}
            <div className="preview-info">
              <span className="preview-name" title={entry.file.name}>
                {entry.file.name.replace(/\.[^.]+$/, '')}
              </span>
              <span className="preview-size">{formatBytes(entry.file.size)}</span>
            </div>

            {/* Status badge */}
            <div className="preview-status">
              {STATUS_ICONS[entry.status]}
              <span className="status-label">
                {entry.status === 'ready'     && 'Ready'}
                {entry.status === 'uploading' && 'Processing…'}
                {entry.status === 'done'      && 'Graded'}
                {entry.status === 'error'     && 'Failed'}
              </span>
            </div>

            {/* Remove button (only when not uploading) */}
            {entry.status !== 'uploading' && (
              <button
                className="preview-remove"
                onClick={() => onRemove(entry.id)}
                aria-label={`Remove ${entry.file.name}`}
                title="Remove"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M2 2l8 8M10 2L2 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
