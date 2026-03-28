import React from 'react';
import './Navbar.css';

const NAV_ITEMS = [
  { id: 'upload',    label: 'Upload Papers' },
  { id: 'keys',      label: 'Answer Keys'   },
  { id: 'results',   label: 'Results'       },
  { id: 'analytics', label: 'Analytics'     },
];

export default function Navbar({ activePage, setActivePage }) {
  return (
    <header className="navbar">
      <div className="navbar-inner">
        {/* Logo / Brand */}
        <button className="navbar-brand" onClick={() => setActivePage('upload')}>
          <span className="brand-icon" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
              <rect x="2" y="2" width="18" height="18" rx="4" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M6 8h10M6 11h7M6 14h5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              <circle cx="17" cy="15" r="3.5" fill="var(--accent)" stroke="var(--cream)" strokeWidth="1"/>
              <path d="M15.8 15l.8.8 1.4-1.4" stroke="white" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </span>
          <span className="brand-name">ExamCheck <em>AI</em></span>
        </button>

        {/* Nav links */}
        <nav className="navbar-nav" aria-label="Main navigation">
          {NAV_ITEMS.map(item => (
            <button
              key={item.id}
              className={`nav-link ${activePage === item.id ? 'active' : ''}`}
              onClick={() => setActivePage(item.id)}
              aria-current={activePage === item.id ? 'page' : undefined}
            >
              {item.label}
            </button>
          ))}
        </nav>

        {/* Right side badge */}
        <div className="navbar-badge">
          <span className="status-dot" aria-hidden="true" />
          Teacher Mode
        </div>
      </div>
    </header>
  );
}
