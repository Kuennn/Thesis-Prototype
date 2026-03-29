// components/CameraCapture.js
// Inline camera capture — live feed shown directly on the page (no modal)
// Handles browser permission errors and shows quality check after capture

import React, { useState, useRef, useEffect, useCallback } from 'react';
import './CameraCapture.css';

export default function CameraCapture({ onCapture, onClose }) {
  const videoRef  = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);

  const [phase,      setPhase]      = useState('idle');    // idle | requesting | live | captured | error
  const [captured,   setCaptured]   = useState(null);      // base64 dataURL
  const [quality,    setQuality]    = useState(null);
  const [errorMsg,   setErrorMsg]   = useState('');
  const [facingMode, setFacingMode] = useState('environment');

  // ── Start camera ────────────────────────────────────────────────────────────
  const startCamera = useCallback(async (facing = facingMode) => {
    setPhase('requesting');
    setErrorMsg('');

    // Stop any previous stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: facing,
          width:  { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      });

      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.onloadedmetadata = () => {
          videoRef.current.play()
            .then(() => setPhase('live'))
            .catch(() => setPhase('live')); // play() rejection is harmless
        };
      }
    } catch (err) {
      console.error('Camera error:', err.name, err.message);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setErrorMsg(
          'Camera access was denied. Click the camera icon in your browser address bar ' +
          'and set it to "Allow", then try again.'
        );
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        setErrorMsg('No camera was found on this device.');
      } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
        setErrorMsg(
          'Camera is already in use by another app (e.g. Zoom, Teams). ' +
          'Close that app and try again.'
        );
      } else if (!window.isSecureContext) {
        setErrorMsg(
          'Camera requires a secure connection (HTTPS or localhost). ' +
          'Make sure you are opening the app at http://localhost:3000'
        );
      } else {
        setErrorMsg(`Camera error: ${err.message || err.name}`);
      }
      setPhase('error');
    }
  }, [facingMode]);

  // ── Stop camera on unmount ──────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
      }
    };
  }, []);

  // ── Flip camera ─────────────────────────────────────────────────────────────
  const flipCamera = () => {
    const next = facingMode === 'environment' ? 'user' : 'environment';
    setFacingMode(next);
    startCamera(next);
  };

  // ── Quality check ────────────────────────────────────────────────────────────
  const checkQuality = (ctx, w, h) => {
    const data = ctx.getImageData(0, 0, w, h).data;

    // Sample for speed — every 8th pixel
    let totalBrightness = 0;
    let lapValues = [];
    const step = 8;
    const imgW  = w;

    for (let y = step; y < h - step; y += step) {
      for (let x = step; x < imgW - step; x += step) {
        const i    = (y * imgW + x) * 4;
        const gray = 0.299 * data[i] + 0.587 * data[i+1] + 0.114 * data[i+2];
        totalBrightness += gray;

        // Laplacian
        const top    = 0.299 * data[((y-step)*imgW+x)*4] + 0.587 * data[((y-step)*imgW+x)*4+1] + 0.114 * data[((y-step)*imgW+x)*4+2];
        const bottom = 0.299 * data[((y+step)*imgW+x)*4] + 0.587 * data[((y+step)*imgW+x)*4+1] + 0.114 * data[((y+step)*imgW+x)*4+2];
        const left   = 0.299 * data[(y*imgW+(x-step))*4] + 0.587 * data[(y*imgW+(x-step))*4+1] + 0.114 * data[(y*imgW+(x-step))*4+2];
        const right  = 0.299 * data[(y*imgW+(x+step))*4] + 0.587 * data[(y*imgW+(x+step))*4+1] + 0.114 * data[(y*imgW+(x+step))*4+2];
        lapValues.push(Math.abs(-4 * gray + top + bottom + left + right));
      }
    }

    const n          = lapValues.length || 1;
    const mean       = lapValues.reduce((a, b) => a + b, 0) / n;
    const variance   = lapValues.reduce((a, b) => a + (b - mean) ** 2, 0) / n;
    const brightness = totalBrightness / (n || 1);

    const isBlurry = variance < 80;
    const isDark   = brightness < 55;
    const isBright = brightness > 220;
    const isGood   = !isBlurry && !isDark && !isBright;

    return {
      isGood, isBlurry, isDark, isBright,
      sharpness:  Math.min(100, Math.round(variance / 4)),
      brightness: Math.round(brightness),
    };
  };

  // ── Capture photo ────────────────────────────────────────────────────────────
  const capturePhoto = () => {
    if (!videoRef.current || !canvasRef.current) return;
    const video  = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width  = video.videoWidth  || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const q = checkQuality(ctx, canvas.width, canvas.height);
    setQuality(q);
    setCaptured(canvas.toDataURL('image/jpeg', 0.92));
    setPhase('captured');

    // Stop live stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
  };

  // ── Use / Retake ─────────────────────────────────────────────────────────────
  const usePhoto = () => {
    if (!canvasRef.current) return;
    canvasRef.current.toBlob(blob => {
      const file = new File([blob], `capture_${Date.now()}.jpg`, { type: 'image/jpeg' });
      onCapture(file);
    }, 'image/jpeg', 0.92);
  };

  const retake = () => {
    setCaptured(null);
    setQuality(null);
    startCamera();
  };

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <div className="camera-inline fade-up">

      {/* Header */}
      <div className="camera-inline-header">
        <div>
          <span className="camera-inline-title">Camera Capture</span>
          <span className="camera-inline-sub">
            {phase === 'live'     && 'Position the paper and press Capture'}
            {phase === 'captured' && 'Review the photo before using it'}
            {phase === 'idle'     && 'Click Open Camera to start'}
            {phase === 'error'    && 'Camera unavailable'}
            {phase === 'requesting' && 'Requesting camera access...'}
          </span>
        </div>
        <button className="camera-inline-close" onClick={onClose} title="Close camera">
          ✕ Close
        </button>
      </div>

      {/* ── IDLE ── */}
      {phase === 'idle' && (
        <div className="camera-idle">
          <div className="camera-idle-icon">
            <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
              <rect x="4" y="10" width="32" height="22" rx="3"
                fill="var(--accent-glow)" stroke="var(--accent)" strokeWidth="1.5"/>
              <circle cx="20" cy="21" r="7" stroke="var(--accent)" strokeWidth="1.5"/>
              <circle cx="20" cy="21" r="3.5" fill="var(--accent)"/>
              <path d="M13 10l2-4h10l2 4" stroke="var(--accent)"
                strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <p>Use your device camera to capture a student answer sheet directly.</p>
          <button className="btn btn-primary" onClick={() => startCamera()}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <rect x="1" y="3" width="12" height="9" rx="2"
                stroke="currentColor" strokeWidth="1.3"/>
              <circle cx="7" cy="7.5" r="2" fill="currentColor"/>
              <path d="M4.5 3l1-2h3l1 2" stroke="currentColor"
                strokeWidth="1.3" strokeLinecap="round"/>
            </svg>
            Open Camera
          </button>
        </div>
      )}

      {/* ── REQUESTING ── */}
      {phase === 'requesting' && (
        <div className="camera-idle">
          <div className="camera-spinner">
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
              <circle cx="16" cy="16" r="12" stroke="var(--accent-glow)" strokeWidth="3"/>
              <circle cx="16" cy="16" r="12" stroke="var(--accent)" strokeWidth="3"
                strokeDasharray="40" strokeDashoffset="30" strokeLinecap="round"/>
            </svg>
          </div>
          <p>Waiting for camera permission...</p>
        </div>
      )}

      {/* ── ERROR ── */}
      {phase === 'error' && (
        <div className="camera-error-inline">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M10 6v5M10 14v.5" stroke="currentColor"
              strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <div>
            <strong>Camera not available</strong>
            <p>{errorMsg}</p>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={() => startCamera()}>
            Try Again
          </button>
        </div>
      )}

      {/* ── LIVE FEED ── */}
      {(phase === 'live' || phase === 'requesting') && (
        <div className="camera-live-wrap">
          <div className="camera-viewfinder">
            <video
              ref={videoRef}
              className="camera-video"
              autoPlay
              playsInline
              muted
            />
            {/* Corner guides */}
            {phase === 'live' && (
              <div className="camera-guides">
                <span className="cg tl"/><span className="cg tr"/>
                <span className="cg bl"/><span className="cg br"/>
                <span className="cg-label">Align paper within guides</span>
              </div>
            )}
          </div>

          {phase === 'live' && (
            <div className="camera-controls">
              <button className="btn-flip" onClick={flipCamera} title="Flip camera">
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                  <path d="M3 9a6 6 0 0 1 11-3M15 9a6 6 0 0 1-11 3"
                    stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                  <path d="M14 4l1.5 2-2 1M4 14l-1.5-2 2-1"
                    stroke="currentColor" strokeWidth="1.5"
                    strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
              <button className="btn-shutter" onClick={capturePhoto} title="Capture">
                <div className="shutter-ring">
                  <div className="shutter-dot"/>
                </div>
              </button>
              <div style={{ width: 44 }}/>
            </div>
          )}
        </div>
      )}

      {/* ── CAPTURED PREVIEW ── */}
      {phase === 'captured' && captured && (
        <div className="camera-preview-wrap">
          <div className="camera-preview-img-wrap">
            <img src={captured} alt="Captured answer sheet" className="camera-preview-img"/>
            {quality && (
              <div className={`quality-pill ${quality.isGood ? 'qp-good' : 'qp-warn'}`}>
                {quality.isGood   ? '✓ Good quality' :
                 quality.isBlurry ? '⚠ Image is blurry' :
                 quality.isDark   ? '⚠ Too dark' : '⚠ Overexposed'}
              </div>
            )}
          </div>

          {/* Quality bars */}
          {quality && (
            <div className="quality-bars">
              <div className="qb-row">
                <span className="qb-label">Sharpness</span>
                <div className="qb-track">
                  <div className="qb-fill"
                    style={{
                      width: `${quality.sharpness}%`,
                      background: quality.isBlurry ? 'var(--danger)' : 'var(--accent)',
                    }}/>
                </div>
                <span className="qb-val">{quality.sharpness}/100</span>
              </div>
              <div className="qb-row">
                <span className="qb-label">Brightness</span>
                <div className="qb-track">
                  <div className="qb-fill"
                    style={{
                      width: `${(quality.brightness / 255) * 100}%`,
                      background: (quality.isDark || quality.isBright)
                        ? 'var(--danger)' : 'var(--accent)',
                    }}/>
                </div>
                <span className="qb-val">{quality.brightness}/255</span>
              </div>
            </div>
          )}

          <div className="camera-preview-actions">
            <button className="btn btn-ghost" onClick={retake}>
              ↩ Retake
            </button>
            <button className="btn btn-primary" onClick={usePhoto}>
              ✓ Use This Photo
            </button>
          </div>
        </div>
      )}

      {/* Hidden canvas */}
      <canvas ref={canvasRef} style={{ display: 'none' }}/>
    </div>
  );
}
