import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import './Navbar.css';

// Ordered by teacher workflow
const NAV_ITEMS = [
  { id: 'classes',     label: 'Classes'       },
  { id: 'keys',        label: 'Answer Keys'   },
  { id: 'answersheet', label: 'Answer Sheets' },
  { id: 'upload',      label: 'Upload Papers' },
  { id: 'results',     label: 'Results'       },
  { id: 'analytics',   label: 'Analytics'     },
];

const BASE_URL = 'http://localhost:8000';

// ─── Change Password Modal ────────────────────────────────────────────────────
function ChangePasswordModal({ onClose }) {
  const { token } = useAuth();
  const [cur,  setCur]  = useState('');
  const [next, setNext] = useState('');
  const [msg,  setMsg]  = useState('');
  const [err,  setErr]  = useState('');
  const [busy, setBusy] = useState(false);

  const handleSave = async () => {
    if (!cur || !next) { setErr('Please fill in both fields.'); return; }
    if (next.length < 6) { setErr('New password must be at least 6 characters.'); return; }
    setBusy(true); setErr(''); setMsg('');
    try {
      const res = await fetch(`${BASE_URL}/api/auth/change-password`, {
        method:  'POST',
        headers: {
          'Content-Type':  'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ current_password: cur, new_password: next }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed');
      setMsg('Password changed successfully!');
      setCur(''); setNext('');
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  // Close on Escape
  React.useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div className="cp-overlay" onClick={onClose}>
      <div className="cp-modal" onClick={e => e.stopPropagation()}>

        <div className="cp-header">
          <h2 className="cp-title">Change Password</h2>
          <button className="cp-close" onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div className="cp-body">
          {err && (
            <div className="cp-alert cp-alert-error">{err}</div>
          )}
          {msg && (
            <div className="cp-alert cp-alert-success">{msg}</div>
          )}

          <div className="cp-field">
            <label className="cp-label">Current Password</label>
            <input
              className="cp-input"
              type="password"
              value={cur}
              onChange={e => setCur(e.target.value)}
              autoFocus
            />
          </div>

          <div className="cp-field">
            <label className="cp-label">New Password</label>
            <input
              className="cp-input"
              type="password"
              placeholder="At least 6 characters"
              value={next}
              onChange={e => setNext(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleSave(); }}
            />
          </div>
        </div>

        <div className="cp-footer">
          <button className="cp-btn cp-btn-ghost" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button className="cp-btn cp-btn-primary" onClick={handleSave} disabled={busy}>
            {busy ? 'Saving...' : 'Save Password'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Navbar ───────────────────────────────────────────────────────────────────
export default function Navbar({ activePage, setActivePage }) {
  const [menuOpen,    setMenuOpen]    = useState(false);
  const [showChgPass, setShowChgPass] = useState(false);
  const { teacherName, logout }       = useAuth();

  const handleNav = (id) => {
    setActivePage(id);
    setMenuOpen(false);
  };

  return (
    <>
      <header className="navbar">
        <div className="navbar-inner">

          {/* Brand */}
          <button className="navbar-brand" onClick={() => handleNav('classes')}>
            <span className="brand-icon">
              <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
                <rect x="2" y="2" width="18" height="18" rx="4"
                  stroke="currentColor" strokeWidth="1.5"/>
                <path d="M6 8h10M6 11h7M6 14h5"
                  stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                <circle cx="17" cy="15" r="3.5" fill="var(--accent)"
                  stroke="var(--cream)" strokeWidth="1"/>
                <path d="M15.8 15l.8.8 1.4-1.4" stroke="white"
                  strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </span>
            <span className="brand-name">Gr<em>Aid</em></span>
          </button>

          {/* Desktop nav */}
          <nav className="navbar-nav">
            {NAV_ITEMS.map(item => (
              <button
                key={item.id}
                className={`nav-link ${activePage === item.id ? 'active' : ''}`}
                onClick={() => handleNav(item.id)}
              >
                {item.label}
              </button>
            ))}
          </nav>

          {/* Right side */}
          <div className="navbar-right">
            <div className="navbar-badge">
              <span className="status-dot" />
              {teacherName || 'Teacher'}
            </div>

            {/* Account button */}
            <button
              className="btn-account"
              onClick={() => setShowChgPass(true)}
              title="Account settings"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <circle cx="7" cy="4.5" r="2.5"
                  stroke="currentColor" strokeWidth="1.3"/>
                <path d="M2 13c0-2.76 2.24-5 5-5s5 2.24 5 5"
                  stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
              </svg>
              <span className="account-label">Account</span>
            </button>

            {/* Sign out */}
            <button className="btn-signout" onClick={logout} title="Sign out">
              <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
                <path d="M6 2H3a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h3"
                  stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                <path d="M10 10l3-2.5L10 5M13 7.5H6"
                  stroke="currentColor" strokeWidth="1.3"
                  strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              <span className="signout-label">Sign Out</span>
            </button>

            {/* Hamburger */}
            <button
              className="hamburger"
              onClick={() => setMenuOpen(o => !o)}
              aria-label="Toggle menu"
            >
              <span className={`ham-line ${menuOpen ? 'open' : ''}`} />
              <span className={`ham-line ${menuOpen ? 'open' : ''}`} />
              <span className={`ham-line ${menuOpen ? 'open' : ''}`} />
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {menuOpen && (
          <div className="mobile-menu">
            {NAV_ITEMS.map(item => (
              <button
                key={item.id}
                className={`mobile-nav-link ${activePage === item.id ? 'active' : ''}`}
                onClick={() => handleNav(item.id)}
              >
                {item.label}
              </button>
            ))}
            <div className="mobile-menu-sep" />
            <button className="mobile-nav-link"
              onClick={() => { setShowChgPass(true); setMenuOpen(false); }}>
              Account Settings
            </button>
            <button className="mobile-nav-link mobile-signout" onClick={logout}>
              Sign Out
            </button>
          </div>
        )}
      </header>

      {/* Change password modal — rendered outside navbar so it's always on top */}
      {showChgPass && (
        <ChangePasswordModal onClose={() => setShowChgPass(false)} />
      )}
    </>
  );
}
