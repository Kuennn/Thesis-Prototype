import React, { useState, useEffect, useRef, useCallback } from 'react';
import { getAllExams, getExamAnalytics, getAIAnalysis } from '../api/api';
import './AnalyticsPage.css';

// ─── Simple bar chart using SVG ───────────────────────────────────────────────
function BarChart({ data, title, valueKey, labelKey, color = 'var(--accent)' }) {
  if (!data || data.length === 0) return null;
  const max = Math.max(...data.map(d => d[valueKey]), 1);

  return (
    <div className="chart-card">
      <h3 className="chart-title">{title}</h3>
      <div className="bar-chart">
        {data.map((item, i) => {
          const pct = (item[valueKey] / max) * 100;
          return (
            <div key={i} className="bar-group">
              <div className="bar-wrap">
                <span className="bar-value">{item[valueKey]}</span>
                <div
                  className="bar-fill"
                  style={{ height: `${Math.max(pct, 2)}%`, background: color }}
                />
              </div>
              <span className="bar-label">{item[labelKey]}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Horizontal accuracy bar ──────────────────────────────────────────────────
function AccuracyBar({ pct, color }) {
  const bg = pct >= 75 ? 'var(--accent-light)'
           : pct >= 50 ? '#f4a623'
           : 'var(--danger)';
  return (
    <div className="acc-bar-track">
      <div
        className="acc-bar-fill"
        style={{ width: `${Math.min(pct, 100)}%`, background: color || bg }}
      />
    </div>
  );
}

// ─── Stat card ────────────────────────────────────────────────────────────────
function StatCard({ label, value, sub, highlight }) {
  return (
    <div className={`stat-card ${highlight ? 'stat-card-highlight' : ''}`}>
      <span className="stat-value">{value}</span>
      {sub && <span className="stat-sub">{sub}</span>}
      <span className="stat-label">{label}</span>
    </div>
  );
}

// ─── Main Analytics Page ──────────────────────────────────────────────────────
export default function AnalyticsPage() {
  const [exams,          setExams]          = useState([]);
  const [selectedExamId, setSelectedExamId] = useState('');
  const [analytics,      setAnalytics]      = useState(null);
  const [aiAnalysis,     setAiAnalysis]     = useState('');
  const [loadingExams,   setLoadingExams]   = useState(true);
  const [loadingData,    setLoadingData]    = useState(false);
  const [loadingAI,      setLoadingAI]      = useState(false);
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

  // Load analytics when exam changes
  useEffect(() => {
    if (!selectedExamId) return;
    setLoadingData(true);
    setAnalytics(null);
    setAiAnalysis('');
    setError(null);

    getExamAnalytics(selectedExamId)
      .then(setAnalytics)
      .catch(e => setError(e.message))
      .finally(() => setLoadingData(false));
  }, [selectedExamId]);

  const handleAIAnalysis = async () => {
    if (!selectedExamId || loadingAI) return;
    setLoadingAI(true);
    setAiAnalysis('');
    try {
      const data = await getAIAnalysis(selectedExamId);
      setAiAnalysis(data.analysis);
    } catch (e) {
      setAiAnalysis(`Error: ${e.message}`);
    } finally {
      setLoadingAI(false);
    }
  };

  const stats = analytics?.statistics;

  return (
    <div className="analytics-page">

      {/* Header */}
      <div className="analytics-header fade-up">
        <div>
          <h1>Analytics</h1>
          <p>Score distributions, per-question accuracy, and AI-generated insights.</p>
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
      <div className="analytics-controls fade-up fade-up-delay-1">
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
      </div>

      {loadingData && (
        <p className="analytics-loading fade-up">Loading analytics...</p>
      )}

      {analytics && analytics.total_graded === 0 && (
        <div className="analytics-empty fade-up">
          <p>No graded papers yet for this exam.</p>
          <p>Upload and process papers first, then come back here.</p>
        </div>
      )}

      {analytics && analytics.total_graded > 0 && (
        <>
          {/* Stat cards */}
          <div className="stats-grid fade-up fade-up-delay-1">
            <StatCard
              label="Students Graded"
              value={analytics.total_graded}
            />
            <StatCard
              label="Class Average"
              value={`${stats.average_score}/${analytics.max_score}`}
              sub={`${stats.average_percent}%`}
              highlight
            />
            <StatCard
              label="Highest Score"
              value={`${stats.highest_score}/${analytics.max_score}`}
            />
            <StatCard
              label="Lowest Score"
              value={`${stats.lowest_score}/${analytics.max_score}`}
            />
            <StatCard
              label="Passed (≥75%)"
              value={stats.passed}
              sub={`${stats.pass_rate}% pass rate`}
              highlight={stats.pass_rate >= 75}
            />
            <StatCard
              label="Failed (<75%)"
              value={stats.failed}
            />
          </div>

          {/* Charts row */}
          <div className="charts-row fade-up fade-up-delay-2">
            {/* Score distribution */}
            <BarChart
              data={analytics.distribution}
              title="Score Distribution"
              valueKey="count"
              labelKey="label"
              color="var(--accent)"
            />

            {/* Per-question accuracy */}
            <div className="chart-card">
              <h3 className="chart-title">Per-Question Accuracy</h3>
              <div className="question-accuracy-list">
                {analytics.per_question.map((q, i) => (
                  <div key={i} className="qa-row">
                    <div className="qa-left">
                      <span className="qa-number">Q{q.question_no}</span>
                      <span className="qa-type">{q.question_type?.replace('_', ' ')}</span>
                    </div>
                    <div className="qa-mid">
                      <span className="qa-text" title={q.question_text}>
                        {q.question_text?.length > 40
                          ? q.question_text.slice(0, 40) + '…'
                          : q.question_text || `Question ${q.question_no}`}
                      </span>
                      <AccuracyBar pct={q.accuracy_pct} />
                    </div>
                    <div className="qa-right">
                      <span
                        className={`qa-pct ${
                          q.accuracy_pct >= 75 ? 'pct-pass'
                          : q.accuracy_pct >= 50 ? 'pct-mid'
                          : 'pct-fail'
                        }`}
                      >
                        {q.accuracy_pct}%
                      </span>
                      <span className="qa-count">
                        {q.correct_count}/{q.total_count}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Student ranking */}
          <div className="chart-card fade-up fade-up-delay-2">
            <h3 className="chart-title">Student Rankings</h3>
            <div className="ranking-table">
              <div className="ranking-header">
                <span>#</span>
                <span>Student</span>
                <span>Score</span>
                <span>Percentage</span>
                <span>Status</span>
              </div>
              {analytics.students.map((s, i) => (
                <div key={i} className={`ranking-row ${s.passed ? 'rank-pass' : 'rank-fail'}`}>
                  <span className="rank-no">{i + 1}</span>
                  <span className="rank-name">{s.student_name}</span>
                  <span className="rank-score">{s.total_score}/{s.max_score}</span>
                  <span className="rank-pct">{s.percentage}%</span>
                  <span className={`rank-status ${s.passed ? 'status-pass' : 'status-fail'}`}>
                    {s.passed ? 'Passed' : 'Failed'}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* AI Analysis */}
          <div className="ai-analysis-card fade-up fade-up-delay-3">
            <div className="ai-analysis-header">
              <div>
                <h3 className="chart-title">AI Exam Analysis</h3>
                <p className="ai-analysis-sub">
                  Groq (LLaMA 3) generates a summary of class performance and teaching recommendations.
                </p>
              </div>
              <button
                className="btn btn-primary"
                onClick={handleAIAnalysis}
                disabled={loadingAI}
              >
                {loadingAI ? (
                  <>
                    <span className="btn-spinner">
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="1.5"
                          strokeDasharray="20" strokeDashoffset="10" strokeLinecap="round"/>
                      </svg>
                    </span>
                    Analyzing...
                  </>
                ) : (
                  <>
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                      <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1"/>
                      <path d="M5 7l2 2 3-3" stroke="currentColor" strokeWidth="1.2"
                        strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    Generate Analysis
                  </>
                )}
              </button>
            </div>

            {aiAnalysis ? (
              <div className="ai-analysis-result">
                <div className="ai-badge">
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <circle cx="6" cy="6" r="5" fill="var(--accent)"/>
                    <path d="M4 6l1.5 1.5 3-3" stroke="white" strokeWidth="1.2"
                      strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  AI Generated
                </div>
                <p className="ai-analysis-text">{aiAnalysis}</p>
              </div>
            ) : (
              <div className="ai-analysis-empty">
                Click "Generate Analysis" to get an AI-powered summary of this exam's results.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
