# services/omr_generator.py — Phase 9 Improved Answer Sheet Generator
# Key changes:
#   1. Bold corner markers for homography alignment
#   2. Fixed answer BOXES (not just lines) for ID and essay
#   3. All region coordinates stored in region_map for precise cropping
#   4. Backward compatible with existing omr.py

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import json, os, tempfile
from datetime import datetime
from PIL import Image as PILImage
import qrcode

PAGE_W, PAGE_H = A4
ML = 18 * mm
MR = PAGE_W - 18*mm
MT = PAGE_H - 15*mm
MB = 18 * mm

BLACK  = colors.HexColor("#000000")
GRAY   = colors.HexColor("#555555")
INK    = colors.HexColor("#000000")
LINE_C = colors.HexColor("#BBBBBB")

BUBBLE_R    = 7.0
ROW_H       = 18
MARKER_SIZE = 12  # larger = more reliably detected by OpenCV

MARKER_POSITIONS = {
    'TL': (ML - 3,               MT + 3),
    'TR': (MR - MARKER_SIZE + 3, MT + 3),
    'BL': (ML - 3,               MB - MARKER_SIZE - 3),
    'BR': (MR - MARKER_SIZE + 3, MB - MARKER_SIZE - 3),
}


def draw_corner_markers(c):
    c.setFillColor(INK)
    for name, (x, y) in MARKER_POSITIONS.items():
        c.rect(x, y, MARKER_SIZE, MARKER_SIZE, stroke=0, fill=1)
        inner = MARKER_SIZE * 0.3
        c.setFillColor(colors.white)
        c.rect(x+inner, y+inner, MARKER_SIZE-2*inner, MARKER_SIZE-2*inner, stroke=0, fill=1)
        c.setFillColor(INK)


def draw_section_header(c, title, y):
    bar_h = 13
    c.setFillColor(BLACK)
    c.rect(ML, y-bar_h, PAGE_W-ML*2, bar_h, stroke=0, fill=1)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.white)
    c.drawString(ML+5, y-bar_h+3.5, title.upper())
    return y - bar_h - 5


def draw_bubble_row(c, q_no, choices, x_start, y, region_map):
    cy = y - BUBBLE_R
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(INK)
    c.drawRightString(x_start+18, cy-3, f"{q_no}.")
    x = x_start + 24
    for choice in choices:
        label = choice[0] if len(choice) > 1 else choice
        c.setFont("Helvetica", 6.5)
        c.setFillColor(GRAY)
        c.drawCentredString(x+BUBBLE_R, cy+BUBBLE_R+2, label)
        c.setStrokeColor(INK)
        c.setFillColor(colors.white)
        c.setLineWidth(0.8)
        c.circle(x+BUBBLE_R, cy, BUBBLE_R, stroke=1, fill=1)
        region_map.append({
            "type": "bubble", "question_no": q_no, "choice": choice,
            "x": x+BUBBLE_R, "y": cy, "r": BUBBLE_R,
            "x_norm": round((x+BUBBLE_R)/PAGE_W, 6),
            "y_norm": round(cy/PAGE_H, 6),
            "r_norm": round(BUBBLE_R/PAGE_W, 6),
        })
        x += BUBBLE_R*2 + 11
    return y - ROW_H


def draw_answer_box(c, q_no, y, label="", lines=1, region_map=None):
    """
    Bounded answer box — key innovation.
    The exact box coordinates are stored so the OCR extractor can
    crop this region precisely from the aligned photo.
    """
    box_h = lines * 14 + 8
    box_w = PAGE_W - ML*2
    box_y = y - box_h - 18

    # Question label
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(INK)
    c.drawString(ML, y-10, f"{q_no}.  {label}")

    # Answer box with light fill
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#888888"))
    c.setLineWidth(1.0)
    c.roundRect(ML, box_y, box_w, box_h, 3, stroke=1, fill=1)

    # Ruled lines inside box
    line_y = box_y + box_h - 14
    for _ in range(lines):
        c.setStrokeColor(LINE_C)
        c.setLineWidth(0.4)
        c.line(ML+8, line_y, ML+box_w-8, line_y)
        line_y -= 14

    if region_map is not None:
        region_map.append({
            "type": "answer_box", "question_no": q_no,
            "box_x": ML, "box_y": box_y,
            "box_w": box_w, "box_h": box_h,
            "x_norm": round(ML/PAGE_W, 6),
            "y_norm": round(box_y/PAGE_H, 6),
            "w_norm": round(box_w/PAGE_W, 6),
            "h_norm": round(box_h/PAGE_H, 6),
        })
    return box_y - 8


def generate_qr_image(data, size_px=100):
    qr = qrcode.QRCode(version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=4, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img = img.resize((size_px, size_px), PILImage.LANCZOS)
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img.save(tmp.name)
    return tmp.name


def generate_answer_sheet(exam=None, questions=None, output_dir=None,
                          exam_id=None, exam_name=None, subject=None,
                          qr_token=None, output_path=None, db=None, **kwargs):
    legacy_mode = exam is None and exam_id is not None

    if legacy_mode:
        class _S: pass
        s = _S()
        s.id = exam_id; s.name = exam_name or f"Exam {exam_id}"
        s.subject = subject or ""; s.qr_token = qr_token or str(exam_id)
        exam = s

        if questions and isinstance(questions[0], dict):
            class _Q: pass
            qs = []
            for qd in questions:
                q = _Q()
                q.question_no = qd["question_no"]
                q.question_type = qd["question_type"]
                q.question_text = qd.get("question_text", "")
                q.answer_key = qd["answer_key"]
                q.max_score = qd["max_score"]
                qs.append(q)
            questions = qs

        output_dir = os.path.dirname(output_path) if output_path else "generated_sheets"

    if exam is None: raise ValueError("exam required")
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

    pdf_path = os.path.join(output_dir, f"exam_{exam.id}_sheet.pdf")
    map_path = os.path.join(output_dir, f"exam_{exam.id}_region_map.json")
    region_map = []

    c = canvas.Canvas(pdf_path, pagesize=A4)
    c.setAuthor("GrAid")
    c.setTitle(f"Answer Sheet — {exam.name}")

    draw_corner_markers(c)

    y = MT
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(BLACK)
    c.drawString(ML, y, "GrAid — Answer Sheet")
    c.setFont("Helvetica", 9)
    c.setFillColor(GRAY)
    c.drawString(ML, y-14, f"{exam.name}  ·  {exam.subject}")
    y -= 30

    # Student info box
    bh = 38
    c.setStrokeColor(LINE_C); c.setLineWidth(0.5); c.setFillColor(colors.white)
    c.roundRect(ML, y-bh, PAGE_W-ML*2, bh, 4, stroke=1, fill=1)
    fields = [
        ("Student Name:", ML+4,   y-bh*0.38, 160),
        ("Student No:",   ML+200, y-bh*0.38, 100),
        ("Section:",      ML+340, y-bh*0.38, 80),
        ("Date:",         ML+4,   y-bh*0.80, 80),
        ("Score:",        ML+160, y-bh*0.80, 80),
        ("Checked by:",   ML+300, y-bh*0.80, 120),
    ]
    c.setFont("Helvetica-Bold", 7); c.setFillColor(GRAY)
    for label, lx, ly, lw in fields:
        c.drawString(lx, ly+8, label)
        c.setStrokeColor(LINE_C); c.setLineWidth(0.4)
        c.line(lx, ly, lx+lw, ly)
    y -= bh + 8

    if mc_qs:
        y = draw_section_header(c, "Multiple Choice", y)
        y -= 14
        col_w = (PAGE_W-ML*2)/2
        half  = (len(mc_qs)+1)//2
        y1, y2 = y, y
        for q in mc_qs[:half]:
            y1 = draw_bubble_row(c, q.question_no, ["A","B","C","D"], ML, y1, region_map)
        for q in mc_qs[half:]:
            y2 = draw_bubble_row(c, q.question_no, ["A","B","C","D"], ML+col_w, y2, region_map)
        y = min(y1, y2) - 8

    if tf_qs:
        y = draw_section_header(c, "True or False", y)
        y -= 14
        col_w = (PAGE_W-ML*2)/2
        half  = (len(tf_qs)+1)//2
        y1, y2 = y, y
        for q in tf_qs[:half]:
            y1 = draw_bubble_row(c, q.question_no, ["True","False"], ML, y1, region_map)
        for q in tf_qs[half:]:
            y2 = draw_bubble_row(c, q.question_no, ["True","False"], ML+col_w, y2, region_map)
        y = min(y1, y2) - 8

    if id_qs:
        y = draw_section_header(c, "Identification", y)
        y -= 4
        for q in id_qs:
            if y < MB+60:
                c.showPage(); draw_corner_markers(c); y = MT
            y = draw_answer_box(c, q.question_no, y, lines=1, region_map=region_map)

    if ess_qs:
        y = draw_section_header(c, "Essay", y) if y > MB+80 else y
        y -= 4
        for q in ess_qs:
            if y < MB+120:
                c.showPage(); draw_corner_markers(c); y = MT
            y = draw_answer_box(c, q.question_no, y,
                                label=f"({int(q.max_score)} pts)",
                                lines=8, region_map=region_map)

    qr_data = json.dumps({"exam_id": exam.id,
                           "token": getattr(exam, 'qr_token', str(exam.id))})
    qr_img  = generate_qr_image(qr_data)
    qr_size = 22*mm
    c.drawImage(qr_img, MR-qr_size, MB, width=qr_size, height=qr_size)
    c.setFont("Helvetica", 6); c.setFillColor(GRAY)
    c.drawCentredString(MR-qr_size/2, MB-8, f"Exam ID: {exam.id}")
    os.unlink(qr_img)

    c.setFont("Helvetica", 7); c.setFillColor(GRAY)
    c.drawString(ML, MB, f"GrAid  ·  {exam.name}  ·  {datetime.now().strftime('%B %d, %Y')}")
    c.save()

    map_data = {
        "exam_id":   exam.id,
        "exam_name": exam.name,
        "page_w_pt": PAGE_W,
        "page_h_pt": PAGE_H,
        "generated": datetime.now().isoformat(),
        "corner_markers": {
            name: {"x": x, "y": y,
                   "x_norm": round(x/PAGE_W, 6),
                   "y_norm": round(y/PAGE_H, 6)}
            for name, (x, y) in MARKER_POSITIONS.items()
        },
        "regions": region_map,
        # backward-compat for old bubble_detector.py
        "bubbles": [r for r in region_map if r["type"] == "bubble"],
    }
    with open(map_path, "w") as f:
        json.dump(map_data, f, indent=2)

    if legacy_mode:
        return map_data
    return pdf_path, map_path
