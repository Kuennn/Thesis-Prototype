import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import Navbar from './components/Navbar';
import LoginPage from './pages/LoginPage';
import ClassesPage from './pages/ClassesPage';
import UploadPage from './pages/UploadPage';
import ExamsPage from './pages/ExamsPage';
import ResultsPage from './pages/ResultsPage';
import AnalyticsPage from './pages/AnalyticsPage';
import AnswerSheetPage from './pages/AnswerSheetPage';
import './App.css';

function AppInner() {
  const { isAuthenticated, loading } = useAuth();
  const [activePage, setActivePage]  = useState('classes');

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex',
        alignItems: 'center', justifyContent: 'center',
        background: 'var(--cream)',
      }}>
        <svg width="32" height="32" viewBox="0 0 32 32" fill="none"
          style={{ animation: 'spin 1s linear infinite' }}>
          <circle cx="16" cy="16" r="12"
            stroke="var(--accent-glow)" strokeWidth="3"/>
          <circle cx="16" cy="16" r="12"
            stroke="var(--accent)" strokeWidth="3"
            strokeDasharray="40" strokeDashoffset="30" strokeLinecap="round"/>
        </svg>
      </div>
    );
  }

  if (!isAuthenticated) return <LoginPage />;

  return (
    <div className="app-shell">
      <Navbar activePage={activePage} setActivePage={setActivePage} />
      <main className="app-main">
        {activePage === 'classes'     && <ClassesPage />}
        {activePage === 'upload'      && <UploadPage />}
        {activePage === 'results'     && <ResultsPage />}
        {activePage === 'keys'        && <ExamsPage />}
        {activePage === 'analytics'   && <AnalyticsPage />}
        {activePage === 'answersheet' && <AnswerSheetPage />}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppInner />
    </AuthProvider>
  );
}
