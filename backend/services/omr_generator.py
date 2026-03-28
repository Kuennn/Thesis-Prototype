# services/omr_generator.py
import io
import os
import json
import tempfile
from PIL import Image as PILImage
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from services.qr_handler import generate_qr_code

# ─── Page Constants (forced A4 — do NOT use reportlab A4 import) ──────────────
PAGE_W = 595.28   # A4 width in points
PAGE_H = 841.89   # A4 height in points
MARGIN       = 18 * mm
CONTENT_W    = PAGE_W - 2 * MARGIN

# Typography
FONT_BOLD    = "Helvetica-Bold"
FONT_REGULAR = "Helvetica"
FONT_SIZE_H1   = 14
FONT_SIZE_H2   = 11
FONT_SIZE_BODY = 9
FONT_SIZE_TINY = 7

# Bubble dimensions
BUBBLE_R       = 4.5 * mm
BUBBLE_SPACING = 12 * mm
ROW_HEIGHT     = 11 * mm

# Colors
COLOR_BLACK  = colors.black
COLOR_GRAY   = colors.HexColor("#888888")
COLOR_LIGHT  = colors.HexColor("#dddddd")
COLOR_ACCENT = colors.HexColor("#2d6a4f")


# ─── Main Generator ───────────────────────────────────────────────────────────

def generate_answer_sheet(
    exam_id:     int,
    exam_name:   str,
    subject:     str,
    questions:   list,
    qr_token:    str,
    output_path: str,
) -> dict:
    # Force A4 explicitly as a tuple — never rely on reportlab's A4 constant
    c = canvas.Canvas(output_path, pagesize=(PAGE_W, PAGE_H))
    c.setPageSize((PAGE_W, PAGE_H))

    bubble_map = {"exam_id": exam_id, "token": qr_token, "bubbles": []}

    y = PAGE_H - MARGIN

    y = _draw_header(c, exam_name, subject, qr_token, exam_id, y)
    y = _draw_instructions(c, y)

    for q in questions:
        q_no   = q["question_no"]
        q_type = q["question_type"]

        if y < MARGIN + 30 * mm:
            c.showPage()
            c.setPageSize((PAGE_W, PAGE_H))
            y = PAGE_H - MARGIN

        if q_type == "multiple_choice":
            choices = _get_mc_choices(q)
            y, bubbles = _draw_mc_row(c, q_no, choices, y)
            bubble_map["bubbles"].extend(bubbles)

        elif q_type == "true_or_false":
            y, bubbles = _draw_tf_row(c, q_no, y)
            bubble_map["bubbles"].extend(bubbles)

        elif q_type == "identification":
            y = _draw_identification_row(c, q_no, y)

        elif q_type == "essay":
            y = _draw_essay_box(c, q_no, q.get("max_score", 1), y)

    _draw_footer(c, exam_id)
    c.save()
    return bubble_map


# ─── Header ───────────────────────────────────────────────────────────────────

def _draw_header(c, exam_name, subject, qr_token, exam_id, y) -> float:
    qr_img  = generate_qr_code(exam_id, qr_token, exam_name)
    qr_size = 28 * mm
    qr_x    = PAGE_W - MARGIN - qr_size
    qr_y    = y - qr_size

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        qr_img.save(tmp.name)
        tmp_path = tmp.name

    try:
        c.drawImage(tmp_path, qr_x, qr_y, width=qr_size, height=qr_size)
    finally:
        os.unlink(tmp_path)

    c.setFont(FONT_BOLD, FONT_SIZE_H1)
    c.setFillColor(COLOR_ACCENT)
    c.drawString(MARGIN, y - 6 * mm, exam_name)

    c.setFont(FONT_REGULAR, FONT_SIZE_H2)
    c.setFillColor(COLOR_GRAY)
    c.drawString(MARGIN, y - 12 * mm, subject)

    y -= 16 * mm
    c.setStrokeColor(COLOR_LIGHT)
    c.setLineWidth(0.5)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 6 * mm

    c.setFont(FONT_REGULAR, FONT_SIZE_BODY)
    c.setFillColor(COLOR_BLACK)
    c.drawString(MARGIN, y, "Name:")
    c.setStrokeColor(COLOR_BLACK)
    c.setLineWidth(0.5)
    c.line(MARGIN + 13 * mm, y - 1, MARGIN + 90 * mm, y - 1)

    date_x = MARGIN + 100 * mm
    c.drawString(date_x, y, "Date:")
    c.line(date_x + 11 * mm, y - 1, PAGE_W - MARGIN - qr_size - 4 * mm, y - 1)

    y -= 4 * mm
    c.setStrokeColor(COLOR_LIGHT)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 6 * mm

    return y


# ─── Instructions ─────────────────────────────────────────────────────────────

def _draw_instructions(c, y) -> float:
    c.setFont(FONT_REGULAR, FONT_SIZE_TINY)
    c.setFillColor(COLOR_GRAY)
    c.drawString(
        MARGIN, y,
        "INSTRUCTIONS: Fill bubbles completely for MC/T/F. Write clearly in lined areas."
    )
    y -= 7 * mm
    return y


# ─── Multiple Choice Row ──────────────────────────────────────────────────────

def _draw_mc_row(c, q_no: int, choices: list, y: float) -> tuple:
    row_y   = y - ROW_HEIGHT / 2
    bubbles = []

    c.setFont(FONT_BOLD, FONT_SIZE_BODY)
    c.setFillColor(COLOR_BLACK)
    c.drawRightString(MARGIN + 8 * mm, row_y - 2, str(q_no) + ".")

    bubble_x = MARGIN + 14 * mm
    for i, choice in enumerate(choices):
        cx = bubble_x + i * BUBBLE_SPACING

        c.setStrokeColor(COLOR_BLACK)
        c.setFillColor(colors.white)
        c.setLineWidth(0.8)
        c.circle(cx, row_y, BUBBLE_R, stroke=1, fill=1)

        c.setFont(FONT_REGULAR, FONT_SIZE_TINY)
        c.setFillColor(COLOR_BLACK)
        c.drawCentredString(cx, row_y - 2, choice)

        bubbles.append({
            "question_no":   q_no,
            "question_type": "multiple_choice",
            "choice":        choice,
            "x":             round(cx, 2),
            "y":             round(row_y, 2),
            "r":             round(BUBBLE_R, 2),
        })

    c.setStrokeColor(COLOR_LIGHT)
    c.setLineWidth(0.3)
    c.line(MARGIN, y - ROW_HEIGHT, PAGE_W - MARGIN, y - ROW_HEIGHT)

    return y - ROW_HEIGHT, bubbles


# ─── True / False Row ─────────────────────────────────────────────────────────

def _draw_tf_row(c, q_no: int, y: float) -> tuple:
    row_y   = y - ROW_HEIGHT / 2
    bubbles = []

    c.setFont(FONT_BOLD, FONT_SIZE_BODY)
    c.setFillColor(COLOR_BLACK)
    c.drawRightString(MARGIN + 8 * mm, row_y - 2, str(q_no) + ".")

    bubble_x = MARGIN + 14 * mm
    for i, (choice, label) in enumerate([("T", "True"), ("F", "False")]):
        cx = bubble_x + i * (BUBBLE_SPACING * 1.8)

        c.setStrokeColor(COLOR_BLACK)
        c.setFillColor(colors.white)
        c.setLineWidth(0.8)
        c.circle(cx, row_y, BUBBLE_R, stroke=1, fill=1)

        c.setFont(FONT_REGULAR, FONT_SIZE_TINY)
        c.setFillColor(COLOR_BLACK)
        c.drawCentredString(cx, row_y - 2, choice)
        c.drawString(cx + BUBBLE_R + 1 * mm, row_y - 2, label)

        bubbles.append({
            "question_no":   q_no,
            "question_type": "true_or_false",
            "choice":        label,
            "x":             round(cx, 2),
            "y":             round(row_y, 2),
            "r":             round(BUBBLE_R, 2),
        })

    c.setStrokeColor(COLOR_LIGHT)
    c.setLineWidth(0.3)
    c.line(MARGIN, y - ROW_HEIGHT, PAGE_W - MARGIN, y - ROW_HEIGHT)

    return y - ROW_HEIGHT, bubbles


# ─── Identification Row ───────────────────────────────────────────────────────

def _draw_identification_row(c, q_no: int, y: float) -> float:
    row_y = y - ROW_HEIGHT / 2

    c.setFont(FONT_BOLD, FONT_SIZE_BODY)
    c.setFillColor(COLOR_BLACK)
    c.drawRightString(MARGIN + 8 * mm, row_y - 2, str(q_no) + ".")

    c.setStrokeColor(COLOR_BLACK)
    c.setLineWidth(0.5)
    c.line(MARGIN + 10 * mm, row_y - 2, PAGE_W - MARGIN, row_y - 2)

    c.setFont(FONT_REGULAR, FONT_SIZE_TINY)
    c.setFillColor(COLOR_GRAY)
    c.drawString(MARGIN + 10 * mm, row_y + 2, "Answer:")

    c.setStrokeColor(COLOR_LIGHT)
    c.setLineWidth(0.3)
    c.line(MARGIN, y - ROW_HEIGHT, PAGE_W - MARGIN, y - ROW_HEIGHT)

    return y - ROW_HEIGHT


# ─── Essay Box ────────────────────────────────────────────────────────────────

def _draw_essay_box(c, q_no: int, max_score: float, y: float) -> float:
    num_lines  = max(6, int(max_score * 3))
    line_gap   = 7 * mm
    box_height = num_lines * line_gap + 8 * mm

    if y - box_height < MARGIN + 10 * mm:
        c.showPage()
        c.setPageSize((PAGE_W, PAGE_H))
        y = PAGE_H - MARGIN

    box_top = y - 6 * mm
    box_bot = box_top - box_height

    c.setFont(FONT_BOLD, FONT_SIZE_BODY)
    c.setFillColor(COLOR_BLACK)
    c.drawString(MARGIN, y, f"{q_no}.  Essay  ({max_score} pts)")

    c.setStrokeColor(COLOR_LIGHT)
    c.setLineWidth(0.6)
    c.rect(MARGIN, box_bot, CONTENT_W, box_height, stroke=1, fill=0)

    c.setStrokeColor(COLOR_LIGHT)
    c.setLineWidth(0.3)
    line_y = box_top - line_gap
    while line_y > box_bot + 3 * mm:
        c.line(MARGIN + 3 * mm, line_y, MARGIN + CONTENT_W - 3 * mm, line_y)
        line_y -= line_gap

    score_box_w = 18 * mm
    score_box_h = 7 * mm
    c.setStrokeColor(COLOR_ACCENT)
    c.setLineWidth(0.5)
    c.rect(
        MARGIN + CONTENT_W - score_box_w,
        box_bot, score_box_w, score_box_h,
        stroke=1, fill=0,
    )
    c.setFont(FONT_REGULAR, FONT_SIZE_TINY)
    c.setFillColor(COLOR_GRAY)
    c.drawCentredString(
        MARGIN + CONTENT_W - score_box_w / 2,
        box_bot + 2 * mm,
        f"Score: __ / {max_score}",
    )

    return box_bot - 6 * mm


# ─── Footer ───────────────────────────────────────────────────────────────────

def _draw_footer(c, exam_id: int):
    c.setFont(FONT_REGULAR, FONT_SIZE_TINY)
    c.setFillColor(COLOR_GRAY)
    c.drawString(MARGIN, MARGIN - 5 * mm, f"Exam ID: {exam_id}")
    c.drawRightString(
        PAGE_W - MARGIN, MARGIN - 5 * mm,
        "ExamCheck AI — Automated Examination System"
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_mc_choices(q: dict) -> list:
    all_choices = ["A", "B", "C", "D", "E", "F"]
    text = (q.get("question_text") or "").upper()
    for n in range(6, 1, -1):
        last = all_choices[n - 1]
        if f"(A-{last})" in text or f"A-{last}" in text:
            return all_choices[:n]
    return all_choices[:4]