// src/api/api.js
// Central place for all backend API calls

const BASE_URL = 'http://localhost:8000';

// ─── Classes ──────────────────────────────────────────────────────────────────

export async function getAllClasses() {
  const res = await fetch(`${BASE_URL}/api/classes/`);
  if (!res.ok) throw new Error('Failed to fetch classes');
  return res.json();
}

export async function getClass(classId) {
  const res = await fetch(`${BASE_URL}/api/classes/${classId}`);
  if (!res.ok) throw new Error('Class not found');
  return res.json();
}

export async function createClass(data) {
  const res = await fetch(`${BASE_URL}/api/classes/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Failed to create class'); }
  return res.json();
}

export async function updateClass(classId, data) {
  const res = await fetch(`${BASE_URL}/api/classes/${classId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Failed to update class'); }
  return res.json();
}

export async function deleteClass(classId) {
  const res = await fetch(`${BASE_URL}/api/classes/${classId}`, { method: 'DELETE' });
  if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Failed to delete class'); }
  return res.json();
}

export async function getClassStudents(classId) {
  const res = await fetch(`${BASE_URL}/api/classes/${classId}/students`);
  if (!res.ok) throw new Error('Failed to fetch students');
  return res.json();
}

export async function enrollStudent(classId, studentId) {
  const res = await fetch(`${BASE_URL}/api/classes/${classId}/enroll/${studentId}`, { method: 'POST' });
  if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Failed to enroll student'); }
  return res.json();
}

export async function unenrollStudent(classId, studentId) {
  const res = await fetch(`${BASE_URL}/api/classes/${classId}/enroll/${studentId}`, { method: 'DELETE' });
  if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Failed to remove student'); }
  return res.json();
}

export async function getClassPerformance(classId) {
  const res = await fetch(`${BASE_URL}/api/classes/${classId}/performance`);
  if (!res.ok) throw new Error('Failed to fetch performance');
  return res.json();
}

// ─── Students ─────────────────────────────────────────────────────────────────

export async function getAllStudents() {
  const res = await fetch(`${BASE_URL}/api/students/`);
  if (!res.ok) throw new Error('Failed to fetch students');
  return res.json();
}

export async function getStudent(studentId) {
  const res = await fetch(`${BASE_URL}/api/students/${studentId}`);
  if (!res.ok) throw new Error('Student not found');
  return res.json();
}

export async function createStudent(data) {
  const res = await fetch(`${BASE_URL}/api/students/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Failed to create student'); }
  return res.json();
}

export async function updateStudent(studentId, data) {
  const res = await fetch(`${BASE_URL}/api/students/${studentId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Failed to update student'); }
  return res.json();
}

export async function deleteStudent(studentId) {
  const res = await fetch(`${BASE_URL}/api/students/${studentId}`, { method: 'DELETE' });
  if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Failed to delete student'); }
  return res.json();
}

export async function searchStudents(query) {
  const res = await fetch(`${BASE_URL}/api/students/search/${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error('Search failed');
  return res.json();
}

// ─── Exams ────────────────────────────────────────────────────────────────────

export async function createExam(examData) {
  const res = await fetch(`${BASE_URL}/api/exams/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(examData),
  });
  if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Failed to create exam'); }
  return res.json();
}

export async function getAllExams(classId) {
  const url = classId
    ? `${BASE_URL}/api/exams/?class_id=${classId}`
    : `${BASE_URL}/api/exams/`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch exams');
  return res.json();
}

export async function getExam(examId) {
  const res = await fetch(`${BASE_URL}/api/exams/${examId}`);
  if (!res.ok) throw new Error('Exam not found');
  return res.json();
}

export async function deleteExam(examId) {
  const res = await fetch(`${BASE_URL}/api/exams/${examId}`, { method: 'DELETE' });
  if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Failed to delete exam'); }
  return res.json();
}

// ─── Papers ───────────────────────────────────────────────────────────────────

export async function uploadPapers(examId, files, onFileProgress, studentId) {
  const results = [];
  for (let i = 0; i < files.length; i++) {
    const entry = files[i];
    onFileProgress(entry.id, 'uploading');
    const formData = new FormData();
    formData.append('exam_id', examId);
    formData.append('student_name', entry.file.name.replace(/\.[^.]+$/, ''));
    if (studentId) formData.append('student_id', studentId);
    formData.append('papers', entry.file);
    try {
      const res = await fetch(`${BASE_URL}/api/papers/upload`, { method: 'POST', body: formData });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Upload failed'); }
      const data = await res.json();
      onFileProgress(entry.id, 'done');
      results.push({ ...data, fileId: entry.id });
    } catch (err) {
      onFileProgress(entry.id, 'error');
      results.push({ error: err.message, fileId: entry.id });
    }
  }
  return results;
}

export async function getPapersByExam(examId) {
  const res = await fetch(`${BASE_URL}/api/papers/exam/${examId}`);
  if (!res.ok) throw new Error('Failed to fetch papers');
  return res.json();
}

export async function deletePaper(paperId) {
  const res = await fetch(`${BASE_URL}/api/papers/${paperId}`, { method: 'DELETE' });
  if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Failed to delete paper'); }
  return res.json();
}

// ─── Teacher Override ─────────────────────────────────────────────────────────

export async function overrideScore(paperId, answerId, teacherScore, teacherNote) {
  const res = await fetch(`${BASE_URL}/api/papers/${paperId}/override/${answerId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ teacher_score: teacherScore, teacher_note: teacherNote || null }),
  });
  if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Override failed'); }
  return res.json();
}

// ─── OCR ──────────────────────────────────────────────────────────────────────

export async function processPaper(paperId) {
  const res = await fetch(`${BASE_URL}/api/ocr/process/${paperId}`, { method: 'POST' });
  if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'OCR processing failed'); }
  return res.json();
}

// ─── Results ──────────────────────────────────────────────────────────────────

export async function getExamSummary(examId) {
  const res = await fetch(`${BASE_URL}/api/results/exam/${examId}/summary`);
  if (!res.ok) throw new Error('Failed to fetch results');
  return res.json();
}

export async function getPaperResults(paperId) {
  const res = await fetch(`${BASE_URL}/api/results/paper/${paperId}`);
  if (!res.ok) throw new Error('Failed to fetch paper results');
  return res.json();
}

// ─── Analytics ────────────────────────────────────────────────────────────────

export async function getExamAnalytics(examId) {
  const res = await fetch(`${BASE_URL}/api/analytics/exam/${examId}`);
  if (!res.ok) throw new Error('Failed to fetch analytics');
  return res.json();
}

export async function getAIAnalysis(examId) {
  const res = await fetch(`${BASE_URL}/api/analytics/exam/${examId}/ai-analysis`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to get AI analysis');
  return res.json();
}

// ─── OMR / Answer Sheets ──────────────────────────────────────────────────────

export async function generateAnswerSheet(examId) {
  const res = await fetch(`${BASE_URL}/api/omr/generate/${examId}`, { method: 'POST' });
  if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Failed to generate answer sheet'); }
  return res.json();
}

export async function downloadAnswerSheet(examId, examName) {
  const res = await fetch(`${BASE_URL}/api/omr/sheet/${examId}`);
  if (!res.ok) throw new Error('Failed to download answer sheet');
  const blob = await res.blob();
  const url  = window.URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `answer_sheet_${examName.replace(/\s+/g, '_')}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export async function scanQRCode(paperId) {
  const res = await fetch(`${BASE_URL}/api/omr/scan-qr/${paperId}`, { method: 'POST' });
  if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'QR scan failed'); }
  return res.json();
}

export async function detectBubbles(paperId) {
  const res = await fetch(`${BASE_URL}/api/omr/detect-bubbles/${paperId}`, { method: 'POST' });
  if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Bubble detection failed'); }
  return res.json();
}
