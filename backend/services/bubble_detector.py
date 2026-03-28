# services/bubble_detector.py
import cv2
import numpy as np
import easyocr
from typing import Optional

# ─── Constants ────────────────────────────────────────────────────────────────

PDF_W = 595.28
PDF_H = 841.89

FILL_THRESHOLD = 0.20
SAMPLE_PADDING = 1.2

_ocr_reader = None

def _get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        _ocr_reader = easyocr.Reader(['en'], gpu=False)
    return _ocr_reader


# ─── Main Detector ────────────────────────────────────────────────────────────

def detect_bubbles(image_path: str, bubble_map: dict) -> dict:
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not load image: {image_path}")

    processed    = _preprocess(img)
    img_h, img_w = processed.shape[:2]
    questions    = _group_by_question(bubble_map["bubbles"])

    answers = {}
    raw     = {}

    for q_no, bubbles in questions.items():
        fill_ratios = {}
        for bubble in bubbles:
            px, py = _pdf_to_pixel(bubble["x"], bubble["y"], img_w, img_h)
            pr     = _pdf_to_pixel_radius(bubble["r"], img_w, img_h)
            ratio  = _measure_fill(processed, px, py, pr)
            fill_ratios[bubble["choice"]] = round(ratio, 4)

        raw[q_no] = fill_ratios
        best_choice = _pick_answer(fill_ratios)
        if best_choice:
            answers[q_no] = best_choice

    return {
        "answers": answers,
        "raw":     raw,
        "method":  "omr_bubble_detection",
    }


# ─── Student Name Extraction ──────────────────────────────────────────────────

def extract_student_name(image_path: str) -> str:
    img = cv2.imread(image_path)
    if img is None:
        return ""

    img_h, img_w = img.shape[:2]

    mm_pt      = 2.8346
    name_x1_pt = (18 + 13) * mm_pt
    name_x2_pt = (18 + 90) * mm_pt
    name_y_pt  = PDF_H - (18 + 38) * mm_pt

    x1 = int((name_x1_pt / PDF_W) * img_w)
    x2 = int((name_x2_pt / PDF_W) * img_w)
    cy = int(((PDF_H - name_y_pt) / PDF_H) * img_h)

    pad = max(8, int(0.018 * img_h))
    y1  = max(0, cy - pad)
    y2  = min(img_h, cy + pad * 2)

    crop = img[y1:y2, x1:x2]
    if crop.size == 0:
        return ""

    scale = 3.0
    crop  = cv2.resize(crop, None, fx=scale, fy=scale,
                       interpolation=cv2.INTER_CUBIC)

    reader  = _get_ocr_reader()
    results = reader.readtext(crop, detail=0, paragraph=True)
    return " ".join(results).strip()


# ─── Preprocessing ────────────────────────────────────────────────────────────

def _preprocess(img: np.ndarray) -> np.ndarray:
    gray    = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(
        blurred, 0, 255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    return binary


# ─── Coordinate Mapping ───────────────────────────────────────────────────────

def _pdf_to_pixel(pdf_x: float, pdf_y: float, img_w: int, img_h: int) -> tuple:
    px = int((pdf_x / PDF_W) * img_w)
    py = int(((PDF_H - pdf_y) / PDF_H) * img_h)
    return px, py


def _pdf_to_pixel_radius(pdf_r: float, img_w: int, img_h: int) -> int:
    scale = (img_w / PDF_W + img_h / PDF_H) / 2
    return max(4, int(pdf_r * scale * SAMPLE_PADDING))


# ─── Fill Measurement ─────────────────────────────────────────────────────────

def _measure_fill(binary: np.ndarray, cx: int, cy: int, r: int) -> float:
    h, w = binary.shape
    x1 = max(0, cx - r)
    y1 = max(0, cy - r)
    x2 = min(w, cx + r)
    y2 = min(h, cy + r)

    if x2 <= x1 or y2 <= y1:
        return 0.0

    mask     = np.zeros((y2 - y1, x2 - x1), dtype=np.uint8)
    local_cx = cx - x1
    local_cy = cy - y1
    cv2.circle(mask, (local_cx, local_cy), r, 255, -1)

    region = binary[y1:y2, x1:x2]
    total  = np.count_nonzero(mask)
    filled = np.count_nonzero(cv2.bitwise_and(region, region, mask=mask))

    return 0.0 if total == 0 else filled / total


# ─── Answer Selection ─────────────────────────────────────────────────────────

def _pick_answer(fill_ratios: dict) -> Optional[str]:
    candidates = {
        choice: ratio
        for choice, ratio in fill_ratios.items()
        if ratio >= FILL_THRESHOLD
    }
    if not candidates:
        return None
    return max(candidates, key=candidates.get)


# ─── Grouping Helper ──────────────────────────────────────────────────────────

def _group_by_question(bubbles: list) -> dict:
    groups = {}
    for bubble in bubbles:
        q_no = bubble["question_no"]
        if q_no not in groups:
            groups[q_no] = []
        groups[q_no].append(bubble)
    return groups


# ─── Debug Annotator ──────────────────────────────────────────────────────────

def annotate_detection(image_path: str, bubble_map: dict, answers: dict) -> np.ndarray:
    img = cv2.imread(image_path)
    if img is None:
        return None

    img_h, img_w = img.shape[:2]
    questions    = _group_by_question(bubble_map["bubbles"])
    processed    = _preprocess(img)

    for q_no, bubbles in questions.items():
        selected = answers.get("answers", {}).get(q_no)

        for bubble in bubbles:
            px, py = _pdf_to_pixel(bubble["x"], bubble["y"], img_w, img_h)
            pr     = _pdf_to_pixel_radius(bubble["r"], img_w, img_h)
            ratio  = _measure_fill(processed, px, py, pr)

            if bubble["choice"] == selected:
                color = (0, 200, 0)
            elif ratio >= FILL_THRESHOLD:
                color = (0, 165, 255)
            else:
                color = (0, 0, 200)

            cv2.circle(img, (px, py), pr, color, 2)

    return img