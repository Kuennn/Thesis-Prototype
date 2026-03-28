import React, { useState } from 'react';
import Navbar from './components/Navbar';
import UploadPage from './pages/UploadPage';
import ExamsPage from './pages/ExamsPage';
import ResultsPage from './pages/ResultsPage';
import AnalyticsPage from './pages/AnalyticsPage';
import './App.css';

export default function App() {
  const [activePage, setActivePage] = useState('upload');

  return (
    <div className="app-shell">
      <Navbar activePage={activePage} setActivePage={setActivePage} />
      <main className="app-main">
        {activePage === 'upload'    && <UploadPage />}
        {activePage === 'results'   && <ResultsPage />}
        {activePage === 'keys'      && <ExamsPage />}
        {activePage === 'analytics' && <AnalyticsPage />}
      </main>
    </div>
  );
}
