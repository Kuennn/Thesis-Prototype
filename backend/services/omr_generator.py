# services/omr_generator.py
# Enhanced Answer Sheet Generator — Phase 8
#
# Improvements over original:
#  - Smaller bubbles (radius 7pt vs old ~12pt) — still detectable at 0.20 fill threshold
#  - More questions fit per page (up to 60 MC/TF questions)
#  - Cleaner two-column layout for MC/TF sections
#  - Dedicated essay/identification write-in lines
#  - Student info box at top (name, student number, date)
#  - Exam info header with institution name
#  - Bubble labels clearly printed (A B C D / T F)
#  - Registration marks at corners for alignment correction
#  - QR code positioned consistently bottom-right
#  - Bubble map JSON records exact pixel coordinates for detector

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import qrcode
import json
import os
import io
import tempfile
from datetime import datetime
from PIL import Image as PILImage

# ── Page constants ─────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4          # 595.28 x 841.89 pts
MARGIN_L = 18 * mm
MARGIN_R = PAGE_W - 18 * mm
MARGIN_T = PAGE_H - 15 * mm
MARGIN_B = 18 * mm

# ── Bubble parameters ──────────────────────────────────────────────────────────
BUBBLE_R      = 7.0    # pt — smaller than old 12pt, still reliable at 300 DPI
BUBBLE_STROKE = 0.8    # pt line weight
BUBBLE_GAP    = 5.5    # pt between bubble centers horizontally
CHOICE_GAP    = 42     # pt between choice groups (space for label + bubble)
ROW_H         = 16     # pt row height per question

# ── Colors ─────────────────────────────────────────────────────────────────────
INK      = colors.HexColor("#1A1A18")
ACCENT   = colors.HexColor("#2D6A4F")
LIGHT    = colors.HexColor("#52B788")
CREAM    = colors.HexColor("#F5F0E8")
GRAY     = colors.HexColor("#9A9A8E")
LINE_CLR = colors.HexColor("#CCCCCC")


def generate_qr_image(data: str, size_px: int = 120) -> str:
    """Generate QR code and save to temp file, return path."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=4,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img = img.resize((size_px, size_px), PILImage.LANCZOS)
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img.save(tmp.name)
    return tmp.name


def draw_registration_marks(c: canvas.Canvas):
    """Draw corner registration marks for alignment detection."""
    mark_size = 8
    marks = [
        (MARGIN_L - 10, MARGIN_B - 10),         # bottom-left
        (MARGIN_R + 10, MARGIN_B - 10),          # bottom-right
        (MARGIN_L - 10, MARGIN_T + 10),          # top-left
        (MARGIN_R + 10, MARGIN_T + 10),          # top-right
    ]
    c.setStrokeColor(INK)
    c.setLineWidth(1.5)
    for mx, my in marks:
        # Cross mark
        c.line(mx - mark_size, my, mx + mark_size, my)
        c.line(mx, my - mark_size, mx, my + mark_size)
        # Small circle
        c.circle(mx, my, 3, stroke=1, fill=0)


def draw_student_info_box(c: canvas.Canvas, exam_name: str, subject: str, y_start: float) -> float:
    """Draw student information section at top. Returns y position after box."""
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(ACCENT)
    c.drawString(MARGIN_L, y_start, "GrAid — Answer Sheet")

    c.setFont("Helvetica", 9)
    c.setFillColor(GRAY)
    c.drawString(MARGIN_L, y_start - 14, f"{exam_name}  ·  {subject}")

    y = y_start - 30

    # Box outline
    box_h = 36
    c.setStrokeColor(LINE_CLR)
    c.setLineWidth(0.5)
    c.roundRect(MARGIN_L, y - box_h, PAGE_W - MARGIN_L * 2, box_h, 4, stroke=1, fill=0)

    # Labels + lines inside box
    fields = [
        ("Student Name:", MARGIN_L + 4,    y - box_h * 0.42, 160),
        ("Student No:",   MARGIN_L + 200,  y - box_h * 0.42, 100),
        ("Section:",      MARGIN_L + 340,  y - box_h * 0.42, 80),
        ("Date:",         MARGIN_L + 4,    y - box_h * 0.85, 80),
        ("Score:",        MARGIN_L + 160,  y - box_h * 0.85, 80),
        ("Checked by:",   MARGIN_L + 300,  y - box_h * 0.85, 120),
    ]

    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(GRAY)
    for label, lx, ly, line_w in fields:
        c.drawString(lx, ly + 8, label)
        c.setStrokeColor(LINE_CLR)
        c.setLineWidth(0.5)
        c.line(lx, ly, lx + line_w, ly)

    return y - box_h - 8


def draw_section_header(c: canvas.Canvas, title: str, y: float) -> float:
    """Draw a section header bar."""
    bar_h = 12
    c.setFillColor(ACCENT)
    c.setStrokeColor(ACCENT)
    c.rect(MARGIN_L, y - bar_h, PAGE_W - MARGIN_L * 2, bar_h, stroke=0, fill=1)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.white)
    c.drawString(MARGIN_L + 4, y - bar_h + 3, title.upper())
    return y - bar_h - 4


def draw_bubble_row(
    c: canvas.Canvas,
    q_no: int,
    choices: list,
    x_start: float,
    y: float,
    bubble_map: list,
) -> float:
    """Draw one question row. Label sits to left of bubbles, choices inline."""
    cy = y - BUBBLE_R  # vertical center of bubbles

    # Question number
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(INK)
    c.drawRightString(x_start + 18, cy - 3, f"{q_no}.")

    x = x_start + 24
    for choice in choices:
        label = choice[0] if len(choice) > 1 else choice

        # Choice label above bubble
        c.setFont("Helvetica", 6.5)
        c.setFillColor(GRAY)
        c.drawCentredString(x + BUBBLE_R, cy + BUBBLE_R + 2, label)

        # Bubble circle
        c.setStrokeColor(INK)
        c.setFillColor(colors.white)
        c.setLineWidth(BUBBLE_STROKE)
        c.circle(x + BUBBLE_R, cy, BUBBLE_R, stroke=1, fill=1)

        bubble_map.append({
            "question_no": q_no,
            "choice":      choice,
            "x":           x + BUBBLE_R,
            "y":           cy,
            "r":           BUBBLE_R,
        })

        x += BUBBLE_R * 2 + BUBBLE_GAP + 5

    return y - ROW_H


def draw_write_in_lines(c: canvas.Canvas, q_no: int, y: float, lines: int = 1, label: str = "") -> float:
    """Draw write-in lines for identification and essay questions."""
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(INK)
    c.drawString(MARGIN_L, y, f"{q_no}. {label}")
    y -= 4

    line_w = PAGE_W - MARGIN_L * 2
    for _ in range(lines):
        c.setStrokeColor(LINE_CLR)
        c.setLineWidth(0.4)
        y -= 11
        c.line(MARGIN_L, y, MARGIN_L + line_w, y)

    return y - 4


def generate_answer_sheet(exam=None, questions: list = None, output_dir: str = None,
                          # Legacy kwargs from omr.py
                          exam_id=None, exam_name=None, subject=None,
                          qr_token=None, output_path=None, db=None, **kwargs):
    """
    Generate a PDF answer sheet and bubble map for an exam.
    Returns (pdf_path, bubble_map_path).

    Accepts either:
      - generate_answer_sheet(exam, questions, output_dir)   ← new style
      - generate_answer_sheet(exam_id=1, questions=..., output_path=..., db=...)  ← legacy omr.py style
    """
    # ── Resolve legacy calling convention ─────────────────────────────────────
    # omr.py calls: generate_answer_sheet(exam_id=, exam_name=, subject=,
    #                questions=<list of dicts>, qr_token=, output_path=)
    # and expects a bubble_map DICT returned (not a tuple)
    legacy_mode = exam is None and exam_id is not None

    if legacy_mode:
        # Build a minimal exam stub from the kwargs
        class _ExamStub:
            pass
        stub           = _ExamStub()
        stub.id        = exam_id
        stub.name      = exam_name or f"Exam {exam_id}"
        stub.subject   = subject   or ""
        stub.qr_token  = qr_token  or str(exam_id)
        exam           = stub

        # questions is already a list of dicts — convert to stubs
        if questions and isinstance(questions[0], dict):
            class _QStub:
                pass
            q_stubs = []
            for qd in questions:
                qs = _QStub()
                qs.question_no   = qd["question_no"]
                qs.question_type = qd["question_type"]  # already an enum or string
                qs.question_text = qd.get("question_text", "")
                qs.answer_key    = qd["answer_key"]
                qs.max_score     = qd["max_score"]
                q_stubs.append(qs)
            questions = q_stubs

        output_dir = os.path.dirname(output_path) if output_path else "generated_sheets"

    if exam is None:
        raise ValueError("generate_answer_sheet: exam is required")
    if questions is None:
        questions = []
    if output_dir is None:
        output_dir = "generated_sheets"


    os.makedirs(output_dir, exist_ok=True)

    pdf_path      = os.path.join(output_dir, f"exam_{exam.id}_sheet.pdf")
    map_path      = os.path.join(output_dir, f"exam_{exam.id}_bubble_map.json")
    qr_token      = getattr(exam, "qr_token", str(exam.id))

    # Helper to get question type as string regardless of enum or string
    def qtype(q):
        t = q.question_type
        return t.value if hasattr(t, 'value') else str(t)

    # Separate questions by type
    mc_qs   = [q for q in questions if qtype(q) == "multiple_choice"]
    tf_qs   = [q for q in questions if qtype(q) == "true_or_false"]
    id_qs   = [q for q in questions if qtype(q) == "identification"]
    ess_qs  = [q for q in questions if qtype(q) == "essay"]

    bubble_map = []

    # ── Build PDF ──────────────────────────────────────────────────────────────
    c = canvas.Canvas(pdf_path, pagesize=A4)
    c.setAuthor("GrAid")
    c.setTitle(f"Answer Sheet — {exam.name}")

    draw_registration_marks(c)

    # Header
    y = MARGIN_T
    y = draw_student_info_box(c, exam.name, exam.subject, y)
    y -= 6

    # ── Multiple Choice ────────────────────────────────────────────────────────
    if mc_qs:
        y = draw_section_header(c, "Multiple Choice", y)
        y -= 14  # padding: space for choice labels above first row
        choices_mc = ["A", "B", "C", "D"]

        col_w   = (PAGE_W - MARGIN_L * 2) / 2
        col1_x  = MARGIN_L
        col2_x  = MARGIN_L + col_w
        half    = (len(mc_qs) + 1) // 2
        col1_qs = mc_qs[:half]
        col2_qs = mc_qs[half:]

        y_col1 = y
        y_col2 = y

        for q in col1_qs:
            y_col1 = draw_bubble_row(c, q.question_no, choices_mc, col1_x, y_col1, bubble_map)

        for q in col2_qs:
            y_col2 = draw_bubble_row(c, q.question_no, choices_mc, col2_x, y_col2, bubble_map)

        y = min(y_col1, y_col2) - 8

    # ── True / False ───────────────────────────────────────────────────────────
    if tf_qs:
        y = draw_section_header(c, "True or False", y)
        y -= 14  # padding for labels
        choices_tf = ["True", "False"]

        col_w   = (PAGE_W - MARGIN_L * 2) / 2
        half    = (len(tf_qs) + 1) // 2
        col1_qs = tf_qs[:half]
        col2_qs = tf_qs[half:]

        y_col1 = y
        y_col2 = y

        for q in col1_qs:
            y_col1 = draw_bubble_row(c, q.question_no, choices_tf, MARGIN_L, y_col1, bubble_map)

        for q in col2_qs:
            y_col2 = draw_bubble_row(c, q.question_no, choices_tf, MARGIN_L + col_w, y_col2, bubble_map)

        y = min(y_col1, y_col2) - 8

    # ── Identification ─────────────────────────────────────────────────────────
    if id_qs:
        y = draw_section_header(c, "Identification", y)
        for q in id_qs:
            y = draw_write_in_lines(c, q.question_no, y, lines=1)
            if y < MARGIN_B + 60:
                c.showPage()
                draw_registration_marks(c)
                y = MARGIN_T

    # ── Essay ──────────────────────────────────────────────────────────────────
    if ess_qs:
        y = draw_section_header(c, "Essay", y) if y > MARGIN_B + 80 else y
        for q in ess_qs:
            pts = int(q.max_score)
            label = f"({pts} pts)"
            if y < MARGIN_B + 120:
                c.showPage()
                draw_registration_marks(c)
                y = MARGIN_T
            y = draw_write_in_lines(c, q.question_no, y, lines=8, label=label)
            y -= 6

    # ── QR Code ────────────────────────────────────────────────────────────────
    qr_data   = json.dumps({"exam_id": exam.id, "token": getattr(exam, 'qr_token', str(exam.id))})
    qr_path   = generate_qr_image(qr_data, size_px=90)
    qr_size   = 22 * mm
    qr_x      = MARGIN_R - qr_size
    qr_y      = MARGIN_B

    c.drawImage(qr_path, qr_x, qr_y, width=qr_size, height=qr_size)

    c.setFont("Helvetica", 6)
    c.setFillColor(GRAY)
    c.drawCentredString(qr_x + qr_size / 2, qr_y - 8, f"Exam ID: {exam.id}")

    os.unlink(qr_path)

    # ── Footer ─────────────────────────────────────────────────────────────────
    c.setFont("Helvetica", 7)
    c.setFillColor(GRAY)
    c.drawString(MARGIN_L, MARGIN_B, f"GrAid  ·  {exam.name}  ·  Generated {datetime.now().strftime('%B %d, %Y')}")

    c.save()

    # ── Save bubble map ────────────────────────────────────────────────────────
    # Convert pt coordinates to normalized (0-1) for resolution-independence
    for b in bubble_map:
        b["x_norm"] = round(b["x"] / PAGE_W, 6)
        b["y_norm"] = round(b["y"] / PAGE_H, 6)
        b["r_norm"] = round(b["r"] / PAGE_W, 6)

    map_data = {
        "exam_id":    exam.id,
        "exam_name":  exam.name,
        "page_w_pt":  PAGE_W,
        "page_h_pt":  PAGE_H,
        "bubble_r":   BUBBLE_R,
        "generated":  datetime.now().isoformat(),
        "bubbles":    bubble_map,
    }

    with open(map_path, "w") as f:
        json.dump(map_data, f, indent=2)

    # Legacy callers (omr.py) expect just the bubble_map dict returned
    # New callers expect (pdf_path, map_path) tuple
    if legacy_mode:
        return map_data
    return pdf_path, map_path
