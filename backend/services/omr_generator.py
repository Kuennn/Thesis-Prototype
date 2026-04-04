# services/omr_generator.py
# Phase 9 — Fixed Answer Sheet Generator
#
# Fixes applied:
#   1. ROW_H increased 18 → 26pt (was cutting off bubble+label which needs 25pt)
#   2. Bubble spacing tightened: BUBBLE_R*2 + 9 instead of BUBBLE_R*2 + 11
#   3. Corner markers now drawn DYNAMICALLY below last content + beside QR
#      instead of fixed to page corners — adapts to actual sheet length
#   4. QR code + BL/BR markers grouped together below last question
#   5. Section header bottom padding increased 14 → 18pt for label clearance
#   6. Two-column layout: col_w computed from available width with explicit
#      max per column so bubbles never overflow
#   7. Bubble label y-position corrected: above bubble top, not clipping header

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import json, os, tempfile
from datetime import datetime
from PIL import Image as PILImage
import qrcode

PAGE_W, PAGE_H = A4   # 595.28 x 841.89 pt
ML = 18 * mm           # 51.0 pt — left margin
MR = PAGE_W - 18*mm   # 544.3 pt — right margin
MT = PAGE_H - 15*mm   # 799.4 pt — top margin
MB = 18 * mm           # 51.0 pt — bottom margin

CONTENT_W = MR - ML   # 493.2 pt usable width

BLACK  = colors.HexColor("#000000")
GRAY   = colors.HexColor("#555555")
INK    = colors.HexColor("#000000")
LINE_C = colors.HexColor("#BBBBBB")
WHITE  = colors.white

# ── Bubble parameters ─────────────────────────────────────────────────────────
BUBBLE_R     = 6.5     # pt radius — slightly smaller for cleaner spacing
BUBBLE_GAP   = 9       # pt between bubble edges (was 11, tightened)
LABEL_ABOVE  = 9       # pt from bubble top center to label baseline
ROW_H        = 26      # pt per question row — was 18, must be ≥ BUBBLE_R*2 + LABEL_ABOVE + 2

# Per-bubble column width: label(6pt) + BUBBLE_R + BUBBLE_GAP + BUBBLE_R
BUBBLE_COL_W = BUBBLE_R * 2 + BUBBLE_GAP   # 22pt per bubble slot

# Row prefix width (question number + gap)
ROW_PREFIX   = 22      # pt before first bubble

# ── Marker parameters ─────────────────────────────────────────────────────────
MARKER_SIZE  = 12      # pt — solid black square with white inner


def _draw_marker(c, x, y):
    """Draw one alignment marker at (x, y) = bottom-left corner of marker."""
    c.setFillColor(INK)
    c.rect(x, y, MARKER_SIZE, MARKER_SIZE, stroke=0, fill=1)
    inner = MARKER_SIZE * 0.3
    c.setFillColor(WHITE)
    c.rect(x + inner, y + inner,
           MARKER_SIZE - 2*inner, MARKER_SIZE - 2*inner, stroke=0, fill=1)
    c.setFillColor(INK)


def draw_corner_markers(c):
    """Draw fixed TL and TR markers only — BL and BR are drawn dynamically."""
    _draw_marker(c, ML - 3,               MT + 3)                   # TL
    _draw_marker(c, MR - MARKER_SIZE + 3, MT + 3)                   # TR


def draw_bottom_markers(c, bottom_y):
    """
    Draw BL and BR markers at a dynamic y position (below last content).
    Called after all content is drawn so markers adapt to sheet length.
    bottom_y = the y coordinate of the bottom of the last content element.
    """
    marker_y = bottom_y - MARKER_SIZE - 6   # 6pt gap below content
    _draw_marker(c, ML - 3,               marker_y)    # BL
    _draw_marker(c, MR - MARKER_SIZE + 3, marker_y)    # BR
    return marker_y  # return actual y for region_map


def draw_section_header(c, title, y):
    bar_h = 13
    c.setFillColor(BLACK)
    c.rect(ML, y - bar_h, CONTENT_W, bar_h, stroke=0, fill=1)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(WHITE)
    c.drawString(ML + 5, y - bar_h + 3.5, title.upper())
    return y - bar_h - 18   # 18pt padding: was 5pt, now leaves room for labels


def draw_bubble_row(c, q_no, choices, x_start, y, region_map):
    """
    Draw one question row with bubbles.
    Fixed: ROW_H=26 so labels never overlap the section header or adjacent rows.
    Layout per row (from top):
      y                   ← row top
      y - LABEL_ABOVE     ← bubble label baseline (e.g. "A")
      y - BUBBLE_R - ...  ← bubble center (cy)
      y - ROW_H           ← row bottom (next row starts here)
    """
    # Bubble center sits LABEL_ABOVE pt below the top of the row area
    cy = y - LABEL_ABOVE - BUBBLE_R

    # Question number — right-aligned before first bubble
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(INK)
    c.drawRightString(x_start + ROW_PREFIX - 2, cy - 2.5, f"{q_no}.")

    x = x_start + ROW_PREFIX
    for choice in choices:
        label = choice[0] if len(choice) > 1 else choice
        bubble_cx = x + BUBBLE_R

        # Label above bubble
        c.setFont("Helvetica", 6.5)
        c.setFillColor(GRAY)
        c.drawCentredString(bubble_cx, cy + BUBBLE_R + 2, label)

        # Bubble circle
        c.setStrokeColor(INK)
        c.setFillColor(WHITE)
        c.setLineWidth(0.8)
        c.circle(bubble_cx, cy, BUBBLE_R, stroke=1, fill=1)

        region_map.append({
            "type":       "bubble",
            "question_no": q_no,
            "choice":      choice,
            "x":           bubble_cx,
            "y":           cy,
            "r":           BUBBLE_R,
            "x_norm":      round(bubble_cx / PAGE_W, 6),
            "y_norm":      round(cy / PAGE_H, 6),
            "r_norm":      round(BUBBLE_R / PAGE_W, 6),
        })

        x += BUBBLE_R * 2 + BUBBLE_GAP

    return y - ROW_H


def draw_two_column_section(c, questions, choices, region_map, y):
    """
    Render a list of questions in two balanced columns.
    Each column is exactly half the content width.
    Bubbles are guaranteed to stay within their column.
    """
    col_w = CONTENT_W / 2   # 246.6 pt per column

    # Verify a row fits in one column
    row_needed = ROW_PREFIX + len(choices) * (BUBBLE_R * 2 + BUBBLE_GAP)
    if row_needed > col_w:
        # Fallback: single column if somehow too wide
        for q in questions:
            y = draw_bubble_row(c, q.question_no, choices, ML, y, region_map)
        return y

    half    = (len(questions) + 1) // 2
    col1_qs = questions[:half]
    col2_qs = questions[half:]

    col1_x = ML
    col2_x = ML + col_w

    y1 = y
    y2 = y

    for q in col1_qs:
        y1 = draw_bubble_row(c, q.question_no, choices, col1_x, y1, region_map)

    for q in col2_qs:
        y2 = draw_bubble_row(c, q.question_no, choices, col2_x, y2, region_map)

    return min(y1, y2) - 8


def draw_answer_box(c, q_no, y, label="", lines=1, region_map=None):
    """Bounded write-in answer box for Identification and Essay questions."""
    box_h = lines * 15 + 8
    box_w = CONTENT_W
    box_y = y - box_h - 18

    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(INK)
    c.drawString(ML, y - 10, f"{q_no}.  {label}")

    c.setFillColor(WHITE)
    c.setStrokeColor(colors.HexColor("#888888"))
    c.setLineWidth(1.0)
    c.roundRect(ML, box_y, box_w, box_h, 3, stroke=1, fill=1)

    line_y = box_y + box_h - 15
    for _ in range(lines):
        c.setStrokeColor(LINE_C)
        c.setLineWidth(0.4)
        c.line(ML + 8, line_y, ML + box_w - 8, line_y)
        line_y -= 15

    if region_map is not None:
        region_map.append({
            "type":        "answer_box",
            "question_no": q_no,
            "box_x":       ML,   "box_y": box_y,
            "box_w":       box_w, "box_h": box_h,
            "x_norm":      round(ML / PAGE_W, 6),
            "y_norm":      round(box_y / PAGE_H, 6),
            "w_norm":      round(box_w / PAGE_W, 6),
            "h_norm":      round(box_h / PAGE_H, 6),
        })

    return box_y - 8


def generate_qr_image(data, size_px=100):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=4, border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img = img.resize((size_px, size_px), PILImage.LANCZOS)
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    img.save(tmp.name)
    return tmp.name


def generate_answer_sheet(exam=None, questions=None, output_dir=None,
                           exam_id=None, exam_name=None, subject=None,
                           qr_token=None, output_path=None, db=None, **kwargs):
    """
    Generate PDF answer sheet + region_map JSON.
    Compatible with both direct call and legacy omr.py kwargs.
    """
    legacy_mode = exam is None and exam_id is not None

    if legacy_mode:
        class _S: pass
        s = _S()
        s.id       = exam_id
        s.name     = exam_name or f"Exam {exam_id}"
        s.subject  = subject   or ""
        s.qr_token = qr_token  or str(exam_id)
        exam       = s

        if questions and isinstance(questions[0], dict):
            class _Q: pass
            qs = []
            for qd in questions:
                q              = _Q()
                q.question_no  = qd["question_no"]
                q.question_type = qd["question_type"]
                q.question_text = qd.get("question_text", "")
                q.answer_key   = qd["answer_key"]
                q.max_score    = qd["max_score"]
                qs.append(q)
            questions = qs

        output_dir = os.path.dirname(output_path) if output_path else "generated_sheets"

    if exam is None:      raise ValueError("exam is required")
    if questions is None: questions = []
    if output_dir is None: output_dir = "generated_sheets"
    os.makedirs(output_dir, exist_ok=True)

    def qtype(q):
        t = q.question_type
        return t.value if hasattr(t, 'value') else str(t)

    mc_qs  = [q for q in questions if qtype(q) == "multiple_choice"]
    tf_qs  = [q for q in questions if qtype(q) == "true_or_false"]
    id_qs  = [q for q in questions if qtype(q) == "identification"]
    ess_qs = [q for q in questions if qtype(q) == "essay"]

    pdf_path   = os.path.join(output_dir, f"exam_{exam.id}_sheet.pdf")
    map_path   = os.path.join(output_dir, f"exam_{exam.id}_region_map.json")
    region_map = []

    c = canvas.Canvas(pdf_path, pagesize=A4)
    c.setAuthor("GrAid")
    c.setTitle(f"Answer Sheet — {exam.name}")

    # TL + TR fixed markers
    draw_corner_markers(c)

    # ── Header ────────────────────────────────────────────────────────────────
    y = MT
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(BLACK)
    c.drawString(ML, y, "GrAid — Answer Sheet")
    c.setFont("Helvetica", 9)
    c.setFillColor(GRAY)
    c.drawString(ML, y - 14, f"{exam.name}  ·  {exam.subject}")
    y -= 30

    # ── Student info box ──────────────────────────────────────────────────────
    bh = 38
    c.setStrokeColor(LINE_C); c.setLineWidth(0.5); c.setFillColor(WHITE)
    c.roundRect(ML, y - bh, CONTENT_W, bh, 4, stroke=1, fill=1)
    fields = [
        ("Student Name:", ML + 4,   y - bh * 0.38, 160),
        ("Student No:",   ML + 200, y - bh * 0.38, 100),
        ("Section:",      ML + 340, y - bh * 0.38, 80),
        ("Date:",         ML + 4,   y - bh * 0.80, 80),
        ("Score:",        ML + 160, y - bh * 0.80, 80),
        ("Checked by:",   ML + 300, y - bh * 0.80, 120),
    ]
    c.setFont("Helvetica-Bold", 7); c.setFillColor(GRAY)
    for label, lx, ly, lw in fields:
        c.drawString(lx, ly + 8, label)
        c.setStrokeColor(LINE_C); c.setLineWidth(0.4)
        c.line(lx, ly, lx + lw, ly)
    y -= bh + 8

    # ── Multiple Choice ───────────────────────────────────────────────────────
    if mc_qs:
        y = draw_section_header(c, "Multiple Choice", y)
        y = draw_two_column_section(c, mc_qs, ["A", "B", "C", "D"], region_map, y)

    # ── True or False ─────────────────────────────────────────────────────────
    if tf_qs:
        y = draw_section_header(c, "True or False", y)
        y = draw_two_column_section(c, tf_qs, ["True", "False"], region_map, y)

    # ── Identification ────────────────────────────────────────────────────────
    if id_qs:
        y = draw_section_header(c, "Identification", y)
        for q in id_qs:
            if y < MB + 60:
                c.showPage()
                draw_corner_markers(c)
                y = MT
            y = draw_answer_box(c, q.question_no, y, lines=1, region_map=region_map)

    # ── Essay ─────────────────────────────────────────────────────────────────
    if ess_qs:
        if y > MB + 80:
            y = draw_section_header(c, "Essay", y)
        for q in ess_qs:
            if y < MB + 120:
                c.showPage()
                draw_corner_markers(c)
                y = MT
            y = draw_answer_box(c, q.question_no, y,
                                label=f"({int(q.max_score)} pts)",
                                lines=8, region_map=region_map)

    # ── QR + dynamic BL/BR markers ────────────────────────────────────────────
    # Place BL/BR markers and QR code together below the last content element.
    # This keeps all four markers at the same vertical level as the content —
    # not floating at the bottom of the page when content is short.
    qr_size  = 22 * mm   # 62.4 pt
    bottom_y = y - 8     # 8pt gap from last content

    # QR code — right-aligned
    qr_data  = json.dumps({
        "exam_id": exam.id,
        "token":   getattr(exam, "qr_token", str(exam.id)),
    })
    qr_img = generate_qr_image(qr_data)
    qr_x   = MR - qr_size
    qr_y   = bottom_y - qr_size

    c.drawImage(qr_img, qr_x, qr_y, width=qr_size, height=qr_size)
    c.setFont("Helvetica", 6); c.setFillColor(GRAY)
    c.drawCentredString(qr_x + qr_size / 2, qr_y - 8, f"Exam ID: {exam.id}")
    os.unlink(qr_img)

    # BL marker — left-aligned at same y as QR
    bl_y = qr_y + (qr_size - MARKER_SIZE) / 2   # vertically centered with QR
    _draw_marker(c, ML - 3, bl_y)

    # BR marker — to the left of QR code
    br_x = qr_x - MARKER_SIZE - 6
    _draw_marker(c, br_x, bl_y)

    # Actual bottom marker y for region_map
    actual_marker_y = bl_y

    # ── Footer ────────────────────────────────────────────────────────────────
    footer_y = qr_y - 16
    c.setFont("Helvetica", 7); c.setFillColor(GRAY)
    c.drawString(ML, footer_y,
                 f"GrAid  ·  {exam.name}  ·  {datetime.now().strftime('%B %d, %Y')}")

    c.save()

    # ── Region map ────────────────────────────────────────────────────────────
    map_data = {
        "exam_id":    exam.id,
        "exam_name":  exam.name,
        "page_w_pt":  PAGE_W,
        "page_h_pt":  PAGE_H,
        "generated":  datetime.now().isoformat(),
        "corner_markers": {
            "TL": {"x": ML - 3,               "y": MT + 3,
                   "x_norm": round((ML-3)/PAGE_W, 6),
                   "y_norm": round((MT+3)/PAGE_H, 6)},
            "TR": {"x": MR - MARKER_SIZE + 3,  "y": MT + 3,
                   "x_norm": round((MR-MARKER_SIZE+3)/PAGE_W, 6),
                   "y_norm": round((MT+3)/PAGE_H, 6)},
            "BL": {"x": ML - 3,               "y": actual_marker_y,
                   "x_norm": round((ML-3)/PAGE_W, 6),
                   "y_norm": round(actual_marker_y/PAGE_H, 6)},
            "BR": {"x": br_x,                  "y": actual_marker_y,
                   "x_norm": round(br_x/PAGE_W, 6),
                   "y_norm": round(actual_marker_y/PAGE_H, 6)},
        },
        "regions": region_map,
        "bubbles":  [r for r in region_map if r["type"] == "bubble"],
    }
    with open(map_path, "w") as f:
        json.dump(map_data, f, indent=2)

    if legacy_mode:
        return map_data
    return pdf_path, map_path
