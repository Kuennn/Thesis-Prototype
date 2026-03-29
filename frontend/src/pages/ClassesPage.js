import React, { useState, useEffect, useCallback } from 'react';
import {
  getAllClasses, createClass, updateClass, deleteClass,
  getClassStudents, getAllStudents, createStudent,
  enrollStudent, unenrollStudent, searchStudents,
  getClassPerformance, getAllExams,
  downloadCSVTemplate, importStudentsCSV,
} from '../api/api';
import './ClassesPage.css';

// ─── Small helpers ────────────────────────────────────────────────────────────
function Alert({ type, msg, onClose }) {
  if (!msg) return null;
  return (
    <div className={`alert alert-${type}`}>
      <span>{msg}</span>
      <button className="alert-close" onClick={onClose}>✕</button>
    </div>
  );
}

function ScorePill({ pct }) {
  if (pct == null) return <span className="pill pill-gray">No data</span>;
  const cls = pct >= 75 ? 'pill-pass' : pct >= 50 ? 'pill-mid' : 'pill-fail';
  return <span className={`pill ${cls}`}>{pct}%</span>;
}

// ─── Create / Edit Class Modal ────────────────────────────────────────────────
function ClassFormModal({ initial, onSave, onClose }) {
  const [form, setForm] = useState(initial || {
    name: '', subject: '', school_year: '', semester: '', description: '',
  });
  const [saving, setSaving] = useState(false);
  const [error,  setError]  = useState('');

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSave = async () => {
    if (!form.name.trim())    { setError('Class name is required.');  return; }
    if (!form.subject.trim()) { setError('Subject is required.');     return; }
    setSaving(true); setError('');
    try { await onSave(form); }
    catch (e) { setError(e.message); setSaving(false); }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{initial ? 'Edit Class' : 'New Class'}</h2>
          <button className="btn-icon" onClick={onClose}>✕</button>
        </div>
        {error && <div className="alert alert-error"><span>{error}</span></div>}
        <div className="modal-body">
          <div className="form-row">
            <div className="field-group">
              <label className="field-label">Class Name *</label>
              <input className="field-input" placeholder="e.g. BSCS 2A"
                value={form.name} onChange={e => set('name', e.target.value)} />
            </div>
            <div className="field-group">
              <label className="field-label">Subject *</label>
              <input className="field-input" placeholder="e.g. Introduction to Programming"
                value={form.subject} onChange={e => set('subject', e.target.value)} />
            </div>
          </div>
          <div className="form-row">
            <div className="field-group">
              <label className="field-label">School Year</label>
              <input className="field-input" placeholder="e.g. 2025-2026"
                value={form.school_year} onChange={e => set('school_year', e.target.value)} />
            </div>
            <div className="field-group">
              <label className="field-label">Semester</label>
              <input className="field-input" placeholder="e.g. 1st Semester"
                value={form.semester} onChange={e => set('semester', e.target.value)} />
            </div>
          </div>
          <div className="field-group">
            <label className="field-label">Description</label>
            <textarea className="field-input field-textarea" placeholder="Optional notes..."
              value={form.description} onChange={e => set('description', e.target.value)} />
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving...' : (initial ? 'Save Changes' : 'Create Class')}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Add Student Modal ────────────────────────────────────────────────────────
function AddStudentModal({ classId, onDone, onClose }) {
  const [tab,      setTab]      = useState('search'); // 'search' | 'new'
  const [query,    setQuery]    = useState('');
  const [results,  setResults]  = useState([]);
  const [form,     setForm]     = useState({ student_no: '', first_name: '', last_name: '', email: '' });
  const [saving,   setSaving]   = useState(false);
  const [error,    setError]    = useState('');
  const [enrolled, setEnrolled] = useState([]);

  useEffect(() => {
    getClassStudents(classId).then(s => setEnrolled(s.map(x => x.student_id)));
  }, [classId]);

  const handleSearch = async (q) => {
    setQuery(q);
    if (q.length < 2) { setResults([]); return; }
    try { setResults(await searchStudents(q)); } catch { setResults([]); }
  };

  const handleEnroll = async (studentId) => {
    setSaving(true); setError('');
    try {
      await enrollStudent(classId, studentId);
      setEnrolled(prev => [...prev, studentId]);
      onDone();
    } catch (e) { setError(e.message); }
    finally { setSaving(false); }
  };

  const handleCreate = async () => {
    if (!form.student_no.trim() || !form.first_name.trim() || !form.last_name.trim()) {
      setError('Student ID, first name, and last name are required.'); return;
    }
    setSaving(true); setError('');
    try {
      const student = await createStudent(form);
      await enrollStudent(classId, student.id);
      onDone(); onClose();
    } catch (e) { setError(e.message); setSaving(false); }
  };

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Add Student</h2>
          <button className="btn-icon" onClick={onClose}>✕</button>
        </div>
        {error && <div className="alert alert-error"><span>{error}</span></div>}

        <div className="modal-tabs">
          <button className={`tab-btn ${tab === 'search' ? 'active' : ''}`} onClick={() => setTab('search')}>
            Search Existing
          </button>
          <button className={`tab-btn ${tab === 'new' ? 'active' : ''}`} onClick={() => setTab('new')}>
            Create New
          </button>
        </div>

        <div className="modal-body">
          {tab === 'search' ? (
            <>
              <input
                className="field-input"
                placeholder="Search by name or student ID..."
                value={query}
                onChange={e => handleSearch(e.target.value)}
              />
              <div className="search-results">
                {results.length === 0 && query.length >= 2 && (
                  <p className="search-empty">No students found. Try creating a new one.</p>
                )}
                {results.map(s => {
                  const isEnrolled = enrolled.includes(s.id);
                  return (
                    <div key={s.id} className="search-result-row">
                      <div>
                        <span className="sr-name">{s.first_name} {s.last_name}</span>
                        <span className="sr-no">{s.student_no}</span>
                      </div>
                      <button
                        className={`btn ${isEnrolled ? 'btn-ghost' : 'btn-primary'} btn-sm`}
                        onClick={() => !isEnrolled && handleEnroll(s.id)}
                        disabled={isEnrolled || saving}
                      >
                        {isEnrolled ? 'Enrolled' : 'Enroll'}
                      </button>
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            <div className="form-stack">
              <div className="form-row">
                <div className="field-group">
                  <label className="field-label">Student ID *</label>
                  <input className="field-input" placeholder="e.g. 2021-00123"
                    value={form.student_no} onChange={e => set('student_no', e.target.value)} />
                </div>
              </div>
              <div className="form-row">
                <div className="field-group">
                  <label className="field-label">First Name *</label>
                  <input className="field-input" value={form.first_name}
                    onChange={e => set('first_name', e.target.value)} />
                </div>
                <div className="field-group">
                  <label className="field-label">Last Name *</label>
                  <input className="field-input" value={form.last_name}
                    onChange={e => set('last_name', e.target.value)} />
                </div>
              </div>
              <div className="field-group">
                <label className="field-label">Email</label>
                <input className="field-input" type="email" value={form.email}
                  onChange={e => set('email', e.target.value)} />
              </div>
            </div>
          )}
        </div>

        {tab === 'new' && (
          <div className="modal-footer">
            <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button className="btn btn-primary" onClick={handleCreate} disabled={saving}>
              {saving ? 'Creating...' : 'Create & Enroll'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Class Detail Panel ───────────────────────────────────────────────────────
function ClassDetail({ class_, onBack, onEdit }) {
  const [students,    setStudents]    = useState([]);
  const [exams,       setExams]       = useState([]);
  const [performance, setPerformance] = useState(null);
  const [showAdd,     setShowAdd]     = useState(false);
  const [removing,    setRemoving]    = useState(null);
  const [error,       setError]       = useState('');
  const [activeTab,   setActiveTab]   = useState('students');

  const load = useCallback(async () => {
    try {
      const [s, e, p] = await Promise.all([
        getClassStudents(class_.id),
        getAllExams(class_.id),
        getClassPerformance(class_.id),
      ]);
      setStudents(s);
      setExams(e);
      setPerformance(p);
    } catch (e) { setError(e.message); }
  }, [class_.id]);

  useEffect(() => { load(); }, [load]);

  const handleRemove = async (studentId, studentName) => {
    if (!window.confirm(`Remove ${studentName} from this class?`)) return;
    setRemoving(studentId);
    try { await unenrollStudent(class_.id, studentId); await load(); }
    catch (e) { setError(e.message); }
    finally { setRemoving(null); }
  };

  return (
    <div className="class-detail fade-up">
      {/* Header */}
      <div className="detail-header">
        <div className="detail-header-left">
          <button className="btn-back" onClick={onBack}>
            ← Back
          </button>
          <div>
            <h1>{class_.name}</h1>
            <p className="detail-sub">
              {class_.subject}
              {class_.school_year && ` · ${class_.school_year}`}
              {class_.semester   && ` · ${class_.semester}`}
            </p>
          </div>
        </div>
        <button className="btn btn-ghost" onClick={onEdit}>Edit Class</button>
      </div>

      {error && <div className="alert alert-error"><span>{error}</span></div>}

      {/* Stats row */}
      <div className="detail-stats">
        <div className="dstat">
          <span className="dstat-val">{students.length}</span>
          <span className="dstat-label">Students</span>
        </div>
        <div className="dstat">
          <span className="dstat-val">{exams.length}</span>
          <span className="dstat-label">Exams</span>
        </div>
        <div className="dstat">
          <span className="dstat-val">
            {performance?.summary?.overall_average != null
              ? `${performance.summary.overall_average}%` : '—'}
          </span>
          <span className="dstat-label">Class Average</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="detail-tabs">
        <button className={`tab-btn ${activeTab === 'students' ? 'active' : ''}`}
          onClick={() => { setActiveTab('students'); load(); }}>Students</button>
        <button className={`tab-btn ${activeTab === 'exams' ? 'active' : ''}`}
          onClick={() => setActiveTab('exams')}>Exams</button>
        <button className={`tab-btn ${activeTab === 'performance' ? 'active' : ''}`}
          onClick={() => { setActiveTab('performance'); load(); }}>Performance</button>
      </div>

      {/* Students tab */}
      {activeTab === 'students' && (
        <div className="tab-content">
          <div className="tab-actions">
            <span className="field-label">{students.length} enrolled</span>
            <div className="tab-actions-right">
              <button className="btn btn-ghost btn-sm"
                onClick={() => downloadCSVTemplate(class_.id, class_.name)}
                title="Download CSV template">
                ↓ CSV Template
              </button>
              <label className="btn btn-ghost btn-sm btn-csv-upload" title="Import from CSV">
                ↑ Import CSV
                <input
                  type="file"
                  accept=".csv"
                  style={{ display: 'none' }}
                  onChange={async e => {
                    const file = e.target.files[0];
                    if (!file) return;
                    try {
                      const result = await importStudentsCSV(class_.id, file);
                      setError('');
                      await load();
                      alert(
                        `Import complete!\n` +
                        `✓ Imported: ${result.total_imported}\n` +
                        `⊘ Skipped: ${result.total_skipped}\n` +
                        `✕ Errors: ${result.total_errors}` +
                        (result.errors.length ? `\n\n${result.errors.join('\n')}` : '')
                      );
                    } catch (e) {
                      setError(e.message);
                    }
                    e.target.value = '';
                  }}
                />
              </label>
              <button className="btn btn-primary btn-sm" onClick={() => setShowAdd(true)}>
                + Add Student
              </button>
            </div>
          </div>
          {students.length === 0 ? (
            <div className="tab-empty">
              <p>No students enrolled yet.</p>
              <button className="btn btn-primary" onClick={() => setShowAdd(true)}>
                Add First Student
              </button>
            </div>
          ) : (
            <div className="student-table">
              <div className="student-table-header">
                <span>Student ID</span>
                <span>Name</span>
                <span>Email</span>
                <span>Exams</span>
                <span>Average</span>
                <span></span>
              </div>
              {students.map(s => (
                <div key={s.student_id} className="student-table-row">
                  <span className="student-no">{s.student_no}</span>
                  <span className="student-name">{s.first_name} {s.last_name}</span>
                  <span className="student-email">{s.email || '—'}</span>
                  <span>{s.total_exams}</span>
                  <span><ScorePill pct={s.average_score} /></span>
                  <button
                    className="btn btn-danger btn-sm"
                    disabled={removing === s.student_id}
                    onClick={() => handleRemove(s.student_id, `${s.first_name} ${s.last_name}`)}
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Exams tab */}
      {activeTab === 'exams' && (
        <div className="tab-content">
          <div className="tab-actions">
            <span className="field-label">{exams.length} exam{exams.length !== 1 ? 's' : ''}</span>
          </div>
          {exams.length === 0 ? (
            <div className="tab-empty">
              <p>No exams created for this class yet.</p>
              <p>Go to <strong>Answer Keys</strong> and select this class to create one.</p>
            </div>
          ) : (
            <div className="exam-list">
              {exams.map(exam => (
                <div key={exam.id} className="exam-list-row">
                  <div>
                    <div className="exam-list-name">{exam.name}</div>
                    <div className="exam-list-sub">{exam.subject} · {exam.questions?.length || 0} questions</div>
                  </div>
                  <span className="exam-list-id">ID: {exam.id}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Performance tab */}
      {activeTab === 'performance' && (
        <div className="tab-content">
          {!performance || performance.exams.length === 0 ? (
            <div className="tab-empty">
              <p>No graded exams yet. Process some papers first.</p>
            </div>
          ) : (
            <div className="perf-table">
              <div className="perf-header">
                <span>Exam</span>
                <span>Papers</span>
                <span>Average</span>
                <span>Highest</span>
                <span>Lowest</span>
                <span>Passed</span>
                <span>Failed</span>
              </div>
              {performance.exams.map(e => (
                <div key={e.exam_id} className="perf-row">
                  <span className="perf-name">{e.exam_name}</span>
                  <span>{e.total_papers}</span>
                  <span><ScorePill pct={e.average_pct} /></span>
                  <span className="perf-high">{e.highest_pct}%</span>
                  <span className="perf-low">{e.lowest_pct}%</span>
                  <span className="perf-pass">{e.passed}</span>
                  <span className="perf-fail">{e.failed}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {showAdd && (
        <AddStudentModal
          classId={class_.id}
          onDone={load}
          onClose={() => setShowAdd(false)}
        />
      )}
    </div>
  );
}

// ─── Main Classes Page ────────────────────────────────────────────────────────
export default function ClassesPage() {
  const [classes,      setClasses]     = useState([]);
  const [loading,      setLoading]     = useState(true);
  const [selectedClass, setSelected]   = useState(null);
  const [showForm,     setShowForm]    = useState(false);
  const [editTarget,   setEditTarget]  = useState(null);
  const [error,        setError]       = useState('');
  const [success,      setSuccess]     = useState('');

  const load = useCallback(() => {
    setLoading(true);
    getAllClasses()
      .then(setClasses)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (form) => {
    await createClass(form);
    setSuccess('Class created!');
    setShowForm(false);
    load();
  };

  const handleEdit = async (form) => {
    await updateClass(editTarget.id, form);
    setSuccess('Class updated!');
    setEditTarget(null);
    setShowForm(false);
    load();
    if (selectedClass?.id === editTarget.id) setSelected(prev => ({ ...prev, ...form }));
  };

  const handleDelete = async (class_) => {
    if (!window.confirm(`Delete "${class_.name}"? This will also delete all its exams and papers.`)) return;
    try {
      await deleteClass(class_.id);
      setSuccess('Class deleted.');
      if (selectedClass?.id === class_.id) setSelected(null);
      load();
    } catch (e) { setError(e.message); }
  };

  if (selectedClass) {
    return (
      <ClassDetail
        class_={selectedClass}
        onBack={() => setSelected(null)}
        onEdit={() => { setEditTarget(selectedClass); setShowForm(true); }}
      />
    );
  }

  return (
    <div className="classes-page">
      <div className="classes-header fade-up">
        <div>
          <h1>Classes</h1>
          <p>Create and manage your classes. Enroll students before creating exams.</p>
        </div>
        <button className="btn btn-primary" onClick={() => { setShowForm(true); setEditTarget(null); }}>
          + New Class
        </button>
      </div>

      <Alert type="error"   msg={error}   onClose={() => setError('')}   />
      <Alert type="success" msg={success} onClose={() => setSuccess('')} />

      {loading ? (
        <p className="classes-loading">Loading classes...</p>
      ) : classes.length === 0 ? (
        <div className="classes-empty fade-up">
          <p>No classes yet. Create your first class to get started.</p>
          <button className="btn btn-primary" onClick={() => setShowForm(true)}>
            Create First Class
          </button>
        </div>
      ) : (
        <div className="classes-grid fade-up">
          {classes.map(c => (
            <div key={c.id} className="class-card" onClick={() => setSelected(c)}>
              <div className="class-card-top">
                <div className="class-avatar">
                  {c.name.charAt(0).toUpperCase()}
                </div>
                <div className="class-card-actions" onClick={e => e.stopPropagation()}>
                  <button className="btn-icon-sm" title="Edit"
                    onClick={() => { setEditTarget(c); setShowForm(true); }}>✎</button>
                  <button className="btn-icon-sm btn-icon-danger" title="Delete"
                    onClick={() => handleDelete(c)}>✕</button>
                </div>
              </div>
              <div className="class-card-body">
                <h3 className="class-card-name">{c.name}</h3>
                <p className="class-card-subject">{c.subject}</p>
                {c.school_year && <p className="class-card-meta">{c.school_year} {c.semester && `· ${c.semester}`}</p>}
              </div>
              <div className="class-card-footer">
                <span className="class-stat">
                  <strong>{c.student_count}</strong> student{c.student_count !== 1 ? 's' : ''}
                </span>
                <span className="class-stat">
                  <strong>{c.exam_count}</strong> exam{c.exam_count !== 1 ? 's' : ''}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <ClassFormModal
          initial={editTarget}
          onSave={editTarget ? handleEdit : handleCreate}
          onClose={() => { setShowForm(false); setEditTarget(null); }}
        />
      )}
    </div>
  );
}
