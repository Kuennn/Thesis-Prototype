// src/api/api.js
// Central place for all backend API calls
// If your backend URL changes, you only need to update it here

const BASE_URL = 'http://localhost:8000';

// ─── Exams ────────────────────────────────────────────────────────────────────

export async function createExam(examData) {
  const res = await fetch(`${BASE_URL}/api/exams/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(examData),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to create exam');
  }
  return res.json();
}

export async function getAllExams() {
  const res = await fetch(`${BASE_URL}/api/exams/`);
  if (!res.ok) throw new Error('Failed to fetch exams');
  return res.json();
}

export async function getExam(examId) {
  const res = await fetch(`${BASE_URL}/api/exams/${examId}`);
  if (!res.ok) throw new Error('Exam not found');
  return res.json();
}

export async function deleteExam(examId) {
  const res = await fetch(`${BASE_URL}/api/exams/${examId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to delete exam');
  }
  return res.json();
}

// ─── Papers ───────────────────────────────────────────────────────────────────

export async function uploadPapers(examId, files, onFileProgress) {
  const results = [];

  for (let i = 0; i < files.length; i++) {
    const entry = files[i];
    onFileProgress(entry.id, 'uploading');

    const formData = new FormData();
    formData.append('exam_id', examId);
    formData.append('student_name', entry.file.name.replace(/\.[^.]+$/, ''));
    formData.append('papers', entry.file);

    try {
      const res = await fetch(`${BASE_URL}/api/papers/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Upload failed');
      }

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
  const res = await fetch(`${BASE_URL}/api/papers/${paperId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to delete paper');
  }
  return res.json();
}

// ─── Teacher Override ─────────────────────────────────────────────────────────

export async function overrideScore(paperId, answerId, teacherScore, teacherNote) {
  const res = await fetch(`${BASE_URL}/api/papers/${paperId}/override/${answerId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      teacher_score: teacherScore,
      teacher_note:  teacherNote || null,
    }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Override failed');
  }
  return res.json();
}

// ─── OCR ──────────────────────────────────────────────────────────────────────

export async function processPaper(paperId) {
  const res = await fetch(`${BASE_URL}/api/ocr/process/${paperId}`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'OCR processing failed');
  }
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
  const res = await fetch(`${BASE_URL}/api/analytics/exam/${examId}/ai-analysis`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to get AI analysis');
  return res.json();
}

// ─── OMR / Answer Sheets ──────────────────────────────────────────────────────

export async function generateAnswerSheet(examId) {
  const res = await fetch(`${BASE_URL}/api/omr/generate/${examId}`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to generate answer sheet');
  }
  return res.json();
}

export async function downloadAnswerSheet(examId, examName) {
  const res = await fetch(`${BASE_URL}/api/omr/sheet/${examId}`);
  if (!res.ok) throw new Error('Failed to download answer sheet');

  // Trigger browser download
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
  const res = await fetch(`${BASE_URL}/api/omr/scan-qr/${paperId}`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'QR scan failed');
  }
  return res.json();
}

export async function detectBubbles(paperId) {
  const res = await fetch(`${BASE_URL}/api/omr/detect-bubbles/${paperId}`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Bubble detection failed');
  }
  return res.json();
}
