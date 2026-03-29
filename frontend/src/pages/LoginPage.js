// src/pages/LoginPage.js
import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import './LoginPage.css';

export default function LoginPage() {
  const { login }   = useAuth();
  const [username,  setUsername]  = useState('');
  const [password,  setPassword]  = useState('');
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState('');
  const [showPass,  setShowPass]  = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError('Please enter both username and password.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await login(username.trim(), password);
    } catch (err) {
      setError(err.message || 'Login failed. Check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card fade-up">

        {/* Brand */}
        <div className="login-brand">
          <div className="login-brand-icon">
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
              <rect x="3" y="3" width="26" height="26" rx="6"
                stroke="var(--accent)" strokeWidth="1.8" fill="var(--accent-glow)"/>
              <path d="M9 11h14M9 16h10M9 21h7"
                stroke="var(--accent)" strokeWidth="1.8" strokeLinecap="round"/>
              <circle cx="24" cy="22" r="5" fill="var(--accent)"/>
              <path d="M22 22l1.5 1.5L26 20.5" stroke="white"
                strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <div>
            <h1 className="login-brand-name">Gr<em>Aid</em></h1>
            <p className="login-brand-sub">AI-Powered Examination Checker</p>
          </div>
        </div>

        <div className="login-divider" />

        <h2 className="login-title">Teacher Login</h2>
        <p className="login-sub">Sign in to access your classes and exam results.</p>

        {error && (
          <div className="login-error">
            <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
              <circle cx="7.5" cy="7.5" r="6" stroke="currentColor" strokeWidth="1.4"/>
              <path d="M7.5 5v3M7.5 10v.4" stroke="currentColor"
                strokeWidth="1.4" strokeLinecap="round"/>
            </svg>
            {error}
          </div>
        )}

        <form className="login-form" onSubmit={handleLogin}>
          <div className="login-field">
            <label className="login-label">Username</label>
            <input
              className="login-input"
              type="text"
              placeholder="Enter username"
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
            />
          </div>

          <div className="login-field">
            <label className="login-label">Password</label>
            <div className="login-input-wrap">
              <input
                className="login-input"
                type={showPass ? 'text' : 'password'}
                placeholder="Enter password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                autoComplete="current-password"
              />
              <button
                type="button"
                className="login-show-pass"
                onClick={() => setShowPass(s => !s)}
                tabIndex={-1}
              >
                {showPass ? (
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M2 8s2.5-4 6-4 6 4 6 4-2.5 4-6 4-6-4-6-4z"
                      stroke="currentColor" strokeWidth="1.3"/>
                    <circle cx="8" cy="8" r="1.8" stroke="currentColor" strokeWidth="1.3"/>
                    <path d="M3 3l10 10" stroke="currentColor"
                      strokeWidth="1.3" strokeLinecap="round"/>
                  </svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M2 8s2.5-4 6-4 6 4 6 4-2.5 4-6 4-6-4-6-4z"
                      stroke="currentColor" strokeWidth="1.3"/>
                    <circle cx="8" cy="8" r="1.8" stroke="currentColor" strokeWidth="1.3"/>
                  </svg>
                )}
              </button>
            </div>
          </div>

          <button className="login-btn" type="submit" disabled={loading}>
            {loading ? (
              <span className="login-spinner">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <circle cx="8" cy="8" r="6" stroke="rgba(255,255,255,0.3)" strokeWidth="2"/>
                  <circle cx="8" cy="8" r="6" stroke="white" strokeWidth="2"
                    strokeDasharray="20" strokeDashoffset="15" strokeLinecap="round"/>
                </svg>
                Signing in...
              </span>
            ) : 'Sign In'}
          </button>
        </form>

        <p className="login-hint">
          Default credentials: <code>admin</code> / <code>examcheck2024</code>
        </p>
      </div>
    </div>
  );
}
