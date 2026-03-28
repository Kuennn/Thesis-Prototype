import React, { useState, useEffect } from 'react';
import { getAllClasses, getAllExams, createExam, deleteExam } from '../api/api';
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
  const [classes,        setClasses]       = useState([]);
  const [selectedClass,  setSelectedClass] = useState('');
  const [exams,          setExams]         = useState([]);
  const [loading,        setLoading]       = useState(false);
  const [loadingClasses, setLoadingClasses] = useState(true);
  const [showForm,       setShowForm]      = useState(false);
  const [saving,         setSaving]        = useState(false);
  const [error,          setError]         = useState(null);
  const [success,        setSuccess]       = useState(null);

  // Form state
  const [examName,   setExamName]   = useState('');
  const [subject,    setSubject]    = useState('');
  const [questions,  setQuestions]  = useState([emptyQuestion(1)]);

  // Load classes on mount
  useEffect(() => {
    getAllClasses()
      .then(data => {
        setClasses(data);
        if (data.length > 0) setSelectedClass(String(data[0].id));
      })
      .catch(() => setError('Could not load classes. Is the backend running?'))
      .finally(() => setLoadingClasses(false));
  }, []);

  // Load exams when class changes
  useEffect(() => {
    if (!selectedClass) return;
    setLoading(true);
    setExams([]);
    getAllExams(selectedClass)
      .then(setExams)
      .catch(() => setError('Could not load exams.'))
      .finally(() => setLoading(false));
  }, [selectedClass]);

  // Auto-fill subject from selected class
  useEffect(() => {
    if (!selectedClass) return;
    const cls = classes.find(c => String(c.id) === selectedClass);
    if (cls) setSubject(cls.subject);
  }, [selectedClass, classes]);

  function addQuestion() {
    setQuestions(prev => [...prev, emptyQuestion(prev.length + 1)]);
  }

  function removeQuestion(index) {
    setQuestions(prev =>
      prev.filter((_, i) => i !== index).map((q, i) => ({ ...q, question_no: i + 1 }))
    );
  }

  function updateQuestion(index, field, value) {
    setQuestions(prev => prev.map((q, i) => i === index ? { ...q, [field]: value } : q));
  }

  async function handleSave() {
    if (!selectedClass)         { setError('Please select a class first.');                          return; }
    if (!examName.trim())       { setError('Please enter an exam name.');                            return; }
    if (!subject.trim())        { setError('Please enter a subject.');                               return; }
    if (questions.some(q => !q.answer_key.trim())) {
      setError('All questions must have an answer key.'); return;
    }

    setSaving(true); setError(null);
    try {
      await createExam({
        name:      examName.trim(),
        subject:   subject.trim(),
        class_id:  parseInt(selectedClass),
        questions: questions.map(q => ({
          ...q,
          max_score: parseFloat(q.max_score) || 1,
          rubric:    q.rubric || null,
        })),
      });
      setSuccess(`Exam "${examName}" created successfully!`);
      setExamName('');
      setQuestions([emptyQuestion(1)]);
      setShowForm(false);
      // Reload exams for this class
      getAllExams(selectedClass).then(setExams);
    } catch (err) {
      setError(err.message || 'Failed to save exam.');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(exam) {
    if (!window.confirm(`Delete "${exam.name}"? This cannot be undone.`)) return;
    setError(null);
    try {
      await deleteExam(exam.id);
      setSuccess(`Exam "${exam.name}" deleted.`);
      setExams(prev => prev.filter(e => e.id !== exam.id));
    } catch (err) {
      setError(err.message || 'Failed to delete exam.');
    }
  }

  function resetForm() {
    setShowForm(false);
    setExamName('');
    setQuestions([emptyQuestion(1)]);
    setError(null);
  }

  const selectedClassData = classes.find(c => String(c.id) === selectedClass);

  return (
    <div className="exams-page">

      {/* Header */}
      <div className="exams-header fade-up">
        <div>
          <h1>Answer Keys</h1>
          <p>Select a class then create exams with answer keys and rubrics.</p>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => { setShowForm(true); setSuccess(null); }}
          disabled={!selectedClass || loadingClasses}
          title={!selectedClass ? 'Select a class first' : ''}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
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

      {/* Class selector */}
      <div className="class-selector-row fade-up">
        <div className="field-group">
          <label className="field-label">Viewing Exams For Class</label>
          {loadingClasses ? (
            <div className="field-loading">Loading classes...</div>
          ) : classes.length === 0 ? (
            <div className="field-empty">
              No classes found. Go to <strong>Classes</strong> and create one first.
            </div>
          ) : (
            <select
              className="field-input field-select"
              value={selectedClass}
              onChange={e => { setSelectedClass(e.target.value); setShowForm(false); }}
            >
              {classes.map(c => (
                <option key={c.id} value={c.id}>
                  {c.name} — {c.subject}
                  {c.school_year ? ` (${c.school_year})` : ''}
                </option>
              ))}
            </select>
          )}
        </div>
        {selectedClassData && (
          <div className="class-info-chip">
            <span className="class-info-label">Students</span>
            <span className="class-info-val">{selectedClassData.student_count}</span>
            <span className="class-info-sep" />
            <span className="class-info-label">Exams</span>
            <span className="class-info-val">{exams.length}</span>
          </div>
        )}
      </div>

      {/* No class warning */}
      {!loadingClasses && classes.length === 0 && (
        <div className="no-class-banner fade-up">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M10 6v4M10 13v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <div>
            <strong>No classes yet.</strong> You need to create a class and enroll students
            before you can create exams.
          </div>
        </div>
      )}

      {/* Create exam form */}
      {showForm && selectedClass && (
        <div className="exam-form fade-up">
          <div className="exam-form-header">
            <div>
              <h2>New Exam</h2>
              <span className="exam-form-class">
                {selectedClassData?.name} — {selectedClassData?.subject}
              </span>
            </div>
            <button className="btn-icon" onClick={resetForm}>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
          </div>

          {/* Class picker inside form */}
          <div className="form-row">
            <div className="field-group">
              <label className="field-label">Assign to Class *</label>
              <select
                className="field-input field-select"
                value={selectedClass}
                onChange={e => setSelectedClass(e.target.value)}
              >
                {classes.map(c => (
                  <option key={c.id} value={c.id}>
                    {c.name} — {c.subject}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-row">
            <div className="field-group">
              <label className="field-label">Exam Name *</label>
              <input
                type="text"
                className="field-input"
                placeholder="e.g. Midterm Exam — Chapter 4"
                value={examName}
                onChange={e => setExamName(e.target.value)}
              />
            </div>
            <div className="field-group">
              <label className="field-label">Subject *</label>
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
              <span className="questions-count">
                {questions.length} question{questions.length !== 1 ? 's' : ''}
              </span>
            </div>
            <div className="questions-list">
              {questions.map((q, idx) => (
                <div key={idx} className="question-card">
                  <div className="question-number">Q{q.question_no}</div>
                  <div className="question-fields">
                    <div className="question-row-top">
                      <div className="field-group" style={{ flex: 2 }}>
                        <label className="field-label">Question Text (optional)</label>
                        <input type="text" className="field-input"
                          placeholder="e.g. What is the capital of France?"
                          value={q.question_text}
                          onChange={e => updateQuestion(idx, 'question_text', e.target.value)} />
                      </div>
                      <div className="field-group">
                        <label className="field-label">Type</label>
                        <select className="field-input field-select"
                          value={q.question_type}
                          onChange={e => updateQuestion(idx, 'question_type', e.target.value)}>
                          {QUESTION_TYPES.map(t => (
                            <option key={t.value} value={t.value}>{t.label}</option>
                          ))}
                        </select>
                      </div>
                      <div className="field-group" style={{ maxWidth: 80 }}>
                        <label className="field-label">Points</label>
                        <input type="number" className="field-input"
                          min="0.5" step="0.5" value={q.max_score}
                          onChange={e => updateQuestion(idx, 'max_score', e.target.value)} />
                      </div>
                    </div>
                    <div className="question-row-bottom">
                      <div className="field-group" style={{ flex: 2 }}>
                        <label className="field-label">
                          {q.question_type === 'essay' ? 'Model Answer / Key Points' : 'Correct Answer'} *
                        </label>
                        {q.question_type === 'essay' ? (
                          <textarea className="field-input field-textarea"
                            placeholder="Enter the model answer or key points to look for..."
                            value={q.answer_key}
                            onChange={e => updateQuestion(idx, 'answer_key', e.target.value)} />
                        ) : (
                          <input type="text" className="field-input"
                            placeholder={
                              q.question_type === 'true_or_false'  ? 'True or False' :
                              q.question_type === 'multiple_choice' ? 'e.g. A, B, C, or D' :
                              'Enter the correct answer'
                            }
                            value={q.answer_key}
                            onChange={e => updateQuestion(idx, 'answer_key', e.target.value)} />
                        )}
                      </div>
                      {q.question_type === 'essay' && (
                        <div className="field-group" style={{ flex: 1 }}>
                          <label className="field-label">Rubric (optional)</label>
                          <textarea className="field-input field-textarea"
                            placeholder="Grading criteria for the AI..."
                            value={q.rubric}
                            onChange={e => updateQuestion(idx, 'rubric', e.target.value)} />
                        </div>
                      )}
                    </div>
                  </div>
                  {questions.length > 1 && (
                    <button className="question-remove" onClick={() => removeQuestion(idx)}>
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

          <div className="form-actions">
            <button className="btn btn-ghost" onClick={resetForm} disabled={saving}>Cancel</button>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving...' : 'Save Exam'}
            </button>
          </div>
        </div>
      )}

      {/* Exams list */}
      {selectedClass && (
        <div className="exams-list fade-up">
          {loading ? (
            <p className="exams-loading">Loading exams...</p>
          ) : exams.length === 0 ? (
            <div className="exams-empty">
              <p>No exams yet for this class. Click <strong>New Exam</strong> to create one.</p>
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
                  <button
                    className="btn btn-danger btn-sm"
                    onClick={() => handleDelete(exam)}
                    title="Delete exam"
                  >
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M2 2l8 8M10 2L2 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                    Delete
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
