import React, { useState, useEffect } from 'react';
import { getAllExams, createExam } from '../api/api';
import './ExamsPage.css';

const QUESTION_TYPES = [
  { value: 'multiple_choice', label: 'Multiple Choice' },
  { value: 'true_or_false',   label: 'True or False'   },
  { value: 'identification',  label: 'Identification'  },
  { value: 'essay',           label: 'Essay'           },
];

function emptyQuestion(no) {
  return {
    question_no:   no,
    question_text: '',
    question_type: 'multiple_choice',
    answer_key:    '',
    max_score:     1,
    rubric:        '',
  };
}

export default function ExamsPage() {
  const [exams, setExams]         = useState([]);
  const [loading, setLoading]     = useState(true);
  const [showForm, setShowForm]   = useState(false);
  const [saving, setSaving]       = useState(false);
  const [error, setError]         = useState(null);
  const [success, setSuccess]     = useState(null);

  // Form state
  const [examName, setExamName]   = useState('');
  const [subject, setSubject]     = useState('');
  const [questions, setQuestions] = useState([emptyQuestion(1)]);

  useEffect(() => {
    loadExams();
  }, []);

  function loadExams() {
    setLoading(true);
    getAllExams()
      .then(setExams)
      .catch(() => setError('Could not load exams. Is the backend running?'))
      .finally(() => setLoading(false));
  }

  function addQuestion() {
    setQuestions(prev => [...prev, emptyQuestion(prev.length + 1)]);
  }

  function removeQuestion(index) {
    setQuestions(prev =>
      prev
        .filter((_, i) => i !== index)
        .map((q, i) => ({ ...q, question_no: i + 1 }))
    );
  }

  function updateQuestion(index, field, value) {
    setQuestions(prev => prev.map((q, i) =>
      i === index ? { ...q, [field]: value } : q
    ));
  }

  async function handleSave() {
    if (!examName.trim()) { setError('Please enter an exam name.'); return; }
    if (!subject.trim())  { setError('Please enter a subject.');    return; }
    if (questions.some(q => !q.answer_key.trim())) {
      setError('All questions must have an answer key filled in.');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      await createExam({
        name:      examName.trim(),
        subject:   subject.trim(),
        questions: questions.map(q => ({
          ...q,
          max_score: parseFloat(q.max_score) || 1,
          rubric:    q.rubric || null,
        })),
      });

      setSuccess(`Exam "${examName}" created successfully!`);
      setExamName('');
      setSubject('');
      setQuestions([emptyQuestion(1)]);
      setShowForm(false);
      loadExams();
    } catch (err) {
      setError(err.message || 'Failed to save exam.');
    } finally {
      setSaving(false);
    }
  }

  function resetForm() {
    setShowForm(false);
    setExamName('');
    setSubject('');
    setQuestions([emptyQuestion(1)]);
    setError(null);
  }

  return (
    <div className="exams-page">

      {/* Header */}
      <div className="exams-header fade-up">
        <div>
          <h1>Answer Keys</h1>
          <p>Create exams and define the correct answers before uploading student papers.</p>
        </div>
        <button className="btn btn-primary" onClick={() => { setShowForm(true); setSuccess(null); }}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
            <path d="M7 1v12M1 7h12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
          </svg>
          New Exam
        </button>
      </div>

      {/* Alerts */}
      {error && (
        <div className="alert alert-error fade-up">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M8 5v3M8 10v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          {error}
        </div>
      )}
      {success && (
        <div className="alert alert-success fade-up">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="6" fill="var(--accent)"/>
            <path d="M5.5 8l2 2 3-3" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          {success}
        </div>
      )}

      {/* Create exam form */}
      {showForm && (
        <div className="exam-form fade-up">
          <div className="exam-form-header">
            <h2>Create New Exam</h2>
            <button className="btn-icon" onClick={resetForm} aria-label="Close form">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
          </div>

          {/* Exam details */}
          <div className="form-row">
            <div className="field-group">
              <label className="field-label">Exam Name</label>
              <input
                type="text"
                className="field-input"
                placeholder="e.g. Midterm Exam — Chapter 4"
                value={examName}
                onChange={e => setExamName(e.target.value)}
              />
            </div>
            <div className="field-group">
              <label className="field-label">Subject</label>
              <input
                type="text"
                className="field-input"
                placeholder="e.g. Introduction to Programming"
                value={subject}
                onChange={e => setSubject(e.target.value)}
              />
            </div>
          </div>

          {/* Questions */}
          <div className="questions-section">
            <div className="questions-header">
              <span className="field-label">Questions & Answer Keys</span>
              <span className="questions-count">{questions.length} question{questions.length !== 1 ? 's' : ''}</span>
            </div>

            <div className="questions-list">
              {questions.map((q, idx) => (
                <div key={idx} className="question-card">
                  <div className="question-number">Q{q.question_no}</div>

                  <div className="question-fields">
                    <div className="question-row-top">
                      <div className="field-group" style={{ flex: 2 }}>
                        <label className="field-label">Question Text (optional)</label>
                        <input
                          type="text"
                          className="field-input"
                          placeholder="e.g. What is the capital of France?"
                          value={q.question_text}
                          onChange={e => updateQuestion(idx, 'question_text', e.target.value)}
                        />
                      </div>
                      <div className="field-group">
                        <label className="field-label">Type</label>
                        <select
                          className="field-input field-select"
                          value={q.question_type}
                          onChange={e => updateQuestion(idx, 'question_type', e.target.value)}
                        >
                          {QUESTION_TYPES.map(t => (
                            <option key={t.value} value={t.value}>{t.label}</option>
                          ))}
                        </select>
                      </div>
                      <div className="field-group" style={{ maxWidth: 80 }}>
                        <label className="field-label">Points</label>
                        <input
                          type="number"
                          className="field-input"
                          min="0.5"
                          step="0.5"
                          value={q.max_score}
                          onChange={e => updateQuestion(idx, 'max_score', e.target.value)}
                        />
                      </div>
                    </div>

                    <div className="question-row-bottom">
                      <div className="field-group" style={{ flex: 2 }}>
                        <label className="field-label">
                          {q.question_type === 'essay' ? 'Model Answer / Key Points' : 'Correct Answer'} *
                        </label>
                        {q.question_type === 'essay' ? (
                          <textarea
                            className="field-input field-textarea"
                            placeholder="Enter the model answer or key points to look for..."
                            value={q.answer_key}
                            onChange={e => updateQuestion(idx, 'answer_key', e.target.value)}
                          />
                        ) : (
                          <input
                            type="text"
                            className="field-input"
                            placeholder={
                              q.question_type === 'true_or_false'   ? 'True or False' :
                              q.question_type === 'multiple_choice'  ? 'e.g. A, B, C, or D' :
                              'Enter the correct answer'
                            }
                            value={q.answer_key}
                            onChange={e => updateQuestion(idx, 'answer_key', e.target.value)}
                          />
                        )}
                      </div>
                      {q.question_type === 'essay' && (
                        <div className="field-group" style={{ flex: 1 }}>
                          <label className="field-label">Rubric (optional)</label>
                          <textarea
                            className="field-input field-textarea"
                            placeholder="Grading criteria for the AI..."
                            value={q.rubric}
                            onChange={e => updateQuestion(idx, 'rubric', e.target.value)}
                          />
                        </div>
                      )}
                    </div>
                  </div>

                  {questions.length > 1 && (
                    <button
                      className="question-remove"
                      onClick={() => removeQuestion(idx)}
                      aria-label={`Remove question ${q.question_no}`}
                    >
                      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                        <path d="M2 2l8 8M10 2L2 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      </svg>
                    </button>
                  )}
                </div>
              ))}
            </div>

            <button className="btn btn-ghost btn-add-question" onClick={addQuestion}>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M7 1v12M1 7h12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
              </svg>
              Add Question
            </button>
          </div>

          {/* Form actions */}
          <div className="form-actions">
            <button className="btn btn-ghost" onClick={resetForm} disabled={saving}>Cancel</button>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving...' : 'Save Exam'}
            </button>
          </div>
        </div>
      )}

      {/* Existing exams list */}
      <div className="exams-list fade-up">
        {loading ? (
          <p className="exams-loading">Loading exams...</p>
        ) : exams.length === 0 ? (
          <div className="exams-empty">
            <p>No exams yet. Click <strong>New Exam</strong> to create your first one.</p>
          </div>
        ) : (
          exams.map(exam => (
            <div key={exam.id} className="exam-card">
              <div className="exam-card-main">
                <div className="exam-card-title">{exam.name}</div>
                <div className="exam-card-subject">{exam.subject}</div>
              </div>
              <div className="exam-card-meta">
                <span className="exam-card-badge">
                  {exam.questions?.length || 0} question{exam.questions?.length !== 1 ? 's' : ''}
                </span>
                <span className="exam-card-id">ID: {exam.id}</span>
              </div>
            </div>
          ))
        )}
      </div>

    </div>
  );
}
