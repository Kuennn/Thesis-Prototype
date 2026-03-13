import React, { useState, useRef, useCallback } from 'react';
import './UploadZone.css';

export default function UploadZone({ onFilesSelected, hasFiles }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);
  const dragCounter = useRef(0);

  const handleDragEnter = useCallback((e) => {
    e.preventDefault();
    dragCounter.current += 1;
    setDragging(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    dragCounter.current -= 1;
    if (dragCounter.current === 0) setDragging(false);
  }, []);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    dragCounter.current = 0;
    setDragging(false);
    const dropped = Array.from(e.dataTransfer.files);
    onFilesSelected(dropped);
  }, [onFilesSelected]);

  const handleFileInput = useCallback((e) => {
    const selected = Array.from(e.target.files);
    onFilesSelected(selected);
    e.target.value = '';
  }, [onFilesSelected]);

  const handleClick = () => inputRef.current?.click();

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      inputRef.current?.click();
    }
  };

  return (
    <div
      className={`upload-zone ${dragging ? 'dragging' : ''} ${hasFiles ? 'compact' : ''}`}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
      aria-label="Upload exam paper images"
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        className="upload-input"
        onChange={handleFileInput}
        aria-hidden="true"
        tabIndex={-1}
      />

      {/* Animated border corners */}
      <span className="corner tl" aria-hidden="true" />
      <span className="corner tr" aria-hidden="true" />
      <span className="corner bl" aria-hidden="true" />
      <span className="corner br" aria-hidden="true" />

      <div className="upload-zone-content">
        {dragging ? (
          <>
            <div className="drop-icon" aria-hidden="true">
              <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                <path d="M20 8v18M12 18l8 8 8-8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M8 30h24" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            </div>
            <p className="zone-drop-hint">Release to add papers</p>
          </>
        ) : (
          <>
            <div className="upload-icon" aria-hidden="true">
              <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
                <rect x="4" y="4" width="28" height="28" rx="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3"/>
                <path d="M18 23V13M13 17l5-5 5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <div className="zone-text">
              <p className="zone-title">
                {hasFiles ? 'Drop more papers here' : 'Drop exam papers here'}
              </p>
              <p className="zone-sub">
                or <span className="zone-link">browse files</span> — JPG, PNG, WEBP supported
              </p>
            </div>
            <div className="zone-tips">
              <span>✓ Multiple files at once</span>
              <span>✓ Handwritten &amp; printed</span>
              <span>✓ Up to 20MB per file</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
