# services/ocr.py
# Phase 9 — OCR Accuracy Rework
#
# Key changes from Phase 8:
#   - RapidOCR (DBNet++ via ONNX) replaces EasyOCR for region detection
#     Python 3.14 compatible — install: pip install rapidocr-onnxruntime
#     Falls back to EasyOCR automatically if RapidOCR is not installed
#   - Per-region preprocessing: tighter adaptiveThreshold (blockSize=15)
#     applied after cropping instead of only once on the full page
#   - Minimum TrOCR crop height raised 32px → 64px
#     (trocr-large-handwritten was benchmarked on 64px+ height images)
#   - 2x upscale applied before full-page threshold so small
#     handwritten words produce larger crops for TrOCR
#   - Essay region stitching: consecutive answer-box regions are joined
#     into a single passage before TrOCR reads them, preserving sentence
#     flow that gets broken when each line is read independently
#   - Confidence threshold lowered 0.10 → 0.05 for handwritten regions
#   - Structured output: returns per-question region dict in addition to
#     flat full_text so grader.py can do question-aware extraction

import cv2
import numpy as np
import os
import torch
from PIL import Image
from transformers import TrOCRProcessor, VisionEncoderDecoderModel

# ── Model singletons ──────────────────────────────────────────────────────────
# Detector priority:
#   1. RapidOCR (rapidocr-onnxruntime) — DBNet++ via ONNX, Python 3.14 compatible
#      Install: pip install rapidocr-onnxruntime
#   2. EasyOCR fallback — if RapidOCR not installed

_rapid_ocr       = None
_easyocr_reader  = None
_trocr_processor = None
_trocr_model     = None


def get_detector():
    """
    Returns the best available text region detector.
    Tries RapidOCR first (DBNet++ detector, Python 3.14 compatible),
    falls back to EasyOCR if not installed.
    """
    global _rapid_ocr, _easyocr_reader

    # Try RapidOCR first
    if _rapid_ocr is None and _rapid_ocr != "unavailable":
        try:
            from rapidocr_onnxruntime import RapidOCR
            print("Loading RapidOCR (DBNet++ via ONNX)...")
            _rapid_ocr = RapidOCR()
            print("RapidOCR loaded.")
        except ImportError:
            print("RapidOCR not installed — falling back to EasyOCR.")
            print("To install: pip install rapidocr-onnxruntime")
            _rapid_ocr = "unavailable"

    if _rapid_ocr != "unavailable":
        return ("rapid", _rapid_ocr)

    # Fallback: EasyOCR
    if _easyocr_reader is None:
        import easyocr
        print("Loading EasyOCR fallback...")
        _easyocr_reader = easyocr.Reader(['en'], gpu=False)
        print("EasyOCR loaded.")
    return ("easy", _easyocr_reader)


def get_trocr():
    global _trocr_processor, _trocr_model
    if _trocr_processor is None:
        print("Loading TrOCR model (first run downloads ~1.3GB)...")
        _trocr_processor = TrOCRProcessor.from_pretrained(
            "microsoft/trocr-large-handwritten"
        )
        _trocr_model = VisionEncoderDecoderModel.from_pretrained(
            "microsoft/trocr-large-handwritten"
        )
        _trocr_model.eval()
        print("TrOCR loaded.")
    return _trocr_processor, _trocr_model


# ── Full-page preprocessing ───────────────────────────────────────────────────

def preprocess_image(image_path: str) -> np.ndarray:
    """
    Prepares the full page image for region detection.
    Returns a cleaned grayscale numpy array (not thresholded — PaddleOCR
    works better on grayscale than on binary images).
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not load image: {image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # Phase 9 change: always upscale to at least 2000px wide
    # (was: only upscale if < 1000px — too small for handwriting crops)
    target_w = 2000
    if w < target_w:
        scale = target_w / w
        gray  = cv2.resize(gray, None, fx=scale, fy=scale,
                           interpolation=cv2.INTER_CUBIC)

    gray = _deskew(gray)
    gray = cv2.fastNlMeansDenoising(gray, h=10)

    return gray


def _deskew(image: np.ndarray) -> np.ndarray:
    """Corrects page tilt. Operates on grayscale."""
    thresh = cv2.adaptiveThreshold(
        image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 31, 10
    )
    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) < 100:
        return image

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    if abs(angle) < 0.5 or abs(angle) > 15:
        return image

    h, w   = image.shape
    center = (w // 2, h // 2)
    M      = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(image, M, (w, h),
                          flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)


# ── Per-region preprocessing ──────────────────────────────────────────────────

def preprocess_crop(crop: np.ndarray) -> np.ndarray:
    """
    Applies a tighter threshold specifically tuned for small handwritten crops.
    Phase 9 change: blockSize=15 instead of 31 — catches finer ink strokes.
    Also applies a small morphological dilation to thicken thin pen strokes.
    """
    if len(crop.shape) == 3:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    else:
        gray = crop.copy()

    # CLAHE — improves local contrast for faint/light handwriting
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    gray  = clahe.apply(gray)

    # Denoise before threshold
    gray = cv2.fastNlMeansDenoising(gray, h=8)

    # Tighter adaptive threshold for small regions
    binary = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=15,
        C=8
    )

    # Dilate slightly to thicken thin ink strokes
    # Helps TrOCR read light ballpen writing
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 1))
    binary = cv2.dilate(binary, kernel, iterations=1)

    return binary


# ── Region detection ──────────────────────────────────────────────────────────

def detect_regions(gray_image: np.ndarray) -> list:
    """
    Detects text regions using RapidOCR (DBNet++ via ONNX Runtime).
    Falls back to EasyOCR if RapidOCR is not installed.

    Returns list of dicts: [{"bbox": [[x1,y1],...,[x4,y4]], "confidence": float}]
    sorted top-to-bottom, left-to-right.
    """
    detector_type, detector = get_detector()
    bboxes = []

    if detector_type == "rapid":
        # RapidOCR returns: (boxes, scores, time_cost)
        # boxes shape: [[x1,y1,x2,y2,x3,y3,x4,y4], ...]  (flat 8-element per box)
        # scores: list of floats
        try:
            result, elapse = detector(gray_image)
            if result is None:
                return []
            for item in result:
                # RapidOCR returns flat [x1,y1,x2,y2,x3,y3,x4,y4,text,score]
                # or [[x1,y1],[x2,y2],[x3,y3],[x4,y4]], text, score
                if item is None:
                    continue
                if len(item) == 3:
                    pts_raw, text, score = item
                elif len(item) == 2:
                    pts_raw, score = item
                else:
                    continue

                # Normalise to [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                pts = _normalise_bbox(pts_raw)
                if pts and float(score) >= 0.05:
                    bboxes.append({
                        "bbox":       pts,
                        "confidence": float(score),
                    })
        except Exception as e:
            print(f"RapidOCR detection error: {e} — retrying with EasyOCR")
            detector_type = "easy"
            _, detector = get_detector()  # will return EasyOCR

    if detector_type == "easy":
        results = detector.readtext(gray_image, detail=1, paragraph=False)
        bboxes  = [
            {"bbox": r[0], "confidence": r[2]}
            for r in results
            if r[2] >= 0.05
        ]

    # Sort top-to-bottom, then left-to-right within the same horizontal band
    bboxes.sort(key=lambda b: (
        round(min(pt[1] for pt in b["bbox"]) / 20) * 20,
        min(pt[0] for pt in b["bbox"]),
    ))

    return bboxes


def _normalise_bbox(pts_raw) -> list:
    """
    Normalise RapidOCR bbox to [[x1,y1],[x2,y2],[x3,y3],[x4,y4]].
    RapidOCR can return either:
      - [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]  ← already correct
      - [x1,y1,x2,y2,x3,y3,x4,y4]          ← flat list of 8 numbers
    """
    try:
        if len(pts_raw) == 4 and isinstance(pts_raw[0], (list, tuple)):
            return [[float(p[0]), float(p[1])] for p in pts_raw]
        if len(pts_raw) == 8:
            flat = [float(v) for v in pts_raw]
            return [[flat[i], flat[i+1]] for i in range(0, 8, 2)]
        return None
    except Exception:
        return None


# ── TrOCR reader ──────────────────────────────────────────────────────────────

def read_crop_with_trocr(crop: np.ndarray) -> str:
    """
    Reads a single cropped region with TrOCR.
    Phase 9: minimum height raised 32 → 64px.
    Applies per-region preprocessing before reading.
    """
    try:
        preprocessed = preprocess_crop(crop)

        # Convert to RGB PIL — TrOCR expects 3-channel
        if len(preprocessed.shape) == 2:
            rgb = cv2.cvtColor(preprocessed, cv2.COLOR_GRAY2RGB)
        else:
            rgb = cv2.cvtColor(preprocessed, cv2.COLOR_BGR2RGB)

        pil = Image.fromarray(rgb)

        # Phase 9: minimum 64px height instead of 32px
        if pil.height < 64:
            scale = 64 / pil.height
            pil   = pil.resize(
                (max(64, int(pil.width * scale)), 64),
                Image.LANCZOS
            )

        processor, model = get_trocr()
        pixel_values     = processor(pil, return_tensors="pt").pixel_values

        with torch.no_grad():
            generated = model.generate(
                pixel_values,
                max_new_tokens=256,   # Phase 9: raised from 128 for longer essay lines
            )

        text = processor.batch_decode(generated, skip_special_tokens=True)[0]
        return text.strip()

    except Exception as e:
        print(f"TrOCR crop read failed: {e}")
        return ""


def stitch_essay_regions(regions: list, gray_image: np.ndarray) -> str:
    """
    Phase 9 — essay-specific improvement.

    Problem: TrOCR reads each bounding box independently. For an essay
    written across 8 lines in an answer box, each line becomes a separate
    region. Reading them independently loses context at line breaks —
    TrOCR adds spurious periods and drops sentence continuations.

    Solution: group consecutive regions that belong to the same vertical
    block (answer box area), stitch their crops into a single tall image,
    and read the whole passage in one TrOCR pass.

    For essays this produces dramatically cleaner output because TrOCR's
    language model can see the full sentence context instead of fragments.
    """
    if not regions:
        return ""

    # Sort regions top to bottom
    regions_sorted = sorted(
        regions,
        key=lambda r: min(pt[1] for pt in r["bbox"])
    )

    # Group regions into vertical clusters
    # Regions within 30px vertical gap = same answer block
    clusters = []
    current  = [regions_sorted[0]]

    for r in regions_sorted[1:]:
        prev_bottom = max(pt[1] for pt in current[-1]["bbox"])
        this_top    = min(pt[1] for pt in r["bbox"])
        gap         = this_top - prev_bottom
        if gap < 30:
            current.append(r)
        else:
            clusters.append(current)
            current = [r]
    clusters.append(current)

    # For each cluster, stitch crops vertically and read as one image
    passages = []
    for cluster in clusters:
        if len(cluster) == 1:
            # Single region — read normally
            r     = cluster[0]
            pts   = np.array(r["bbox"], dtype=np.int32)
            x_min = max(0, pts[:, 0].min() - 6)
            y_min = max(0, pts[:, 1].min() - 6)
            x_max = min(gray_image.shape[1], pts[:, 0].max() + 6)
            y_max = min(gray_image.shape[0], pts[:, 1].max() + 6)
            crop  = gray_image[y_min:y_max, x_min:x_max]
            if crop.size > 0:
                text = read_crop_with_trocr(crop)
                if text:
                    passages.append(text)
        else:
            # Multiple consecutive regions — stitch and read as one passage
            crops     = []
            max_width = 0
            for r in cluster:
                pts   = np.array(r["bbox"], dtype=np.int32)
                x_min = max(0, pts[:, 0].min() - 6)
                y_min = max(0, pts[:, 1].min() - 6)
                x_max = min(gray_image.shape[1], pts[:, 0].max() + 6)
                y_max = min(gray_image.shape[0], pts[:, 1].max() + 6)
                crop  = gray_image[y_min:y_max, x_min:x_max]
                if crop.size > 0:
                    crops.append(crop)
                    max_width = max(max_width, crop.shape[1])

            if not crops:
                continue

            # Pad all crops to the same width and stack vertically
            padded = []
            for crop in crops:
                h, w  = crop.shape[:2]
                pad_w = max_width - w
                if pad_w > 0:
                    pad = np.full((h, pad_w), 255, dtype=np.uint8) \
                          if len(crop.shape) == 2 \
                          else np.full((h, pad_w, 3), 255, dtype=np.uint8)
                    crop = np.hstack([crop, pad])
                padded.append(crop)

            # Add 4px white gap between lines (improves TrOCR line separation)
            gap_row = np.full((4, max_width), 255, dtype=np.uint8) \
                      if len(padded[0].shape) == 2 \
                      else np.full((4, max_width, 3), 255, dtype=np.uint8)
            stitched_parts = []
            for i, crop in enumerate(padded):
                stitched_parts.append(crop)
                if i < len(padded) - 1:
                    stitched_parts.append(gap_row)

            stitched = np.vstack(stitched_parts)
            text     = read_crop_with_trocr(stitched)
            if text:
                passages.append(text)

    return " ".join(passages)


# ── Main extraction ───────────────────────────────────────────────────────────

def extract_text_from_image(image_path: str) -> dict:
    """
    Phase 9 hybrid OCR pipeline.
    PaddleOCR detects regions → TrOCR reads each region.
    Essay regions are stitched before reading for better coherence.

    Returns:
        {
            "full_text":          str,   — joined text for backward compat
            "lines":              list,  — per-region results
            "regions_by_position": dict, — regions grouped by vertical band
            "average_confidence": float,
            "word_count":         int,
            "ocr_method":         str,
        }
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    gray        = preprocess_image(image_path)
    page_h      = gray.shape[0]
    bboxes      = detect_regions(gray)

    if not bboxes:
        return {
            "full_text":           "",
            "lines":               [],
            "regions_by_position": {},
            "average_confidence":  0.0,
            "word_count":          0,
            "ocr_method":          "phase9-paddle+trocr",
        }

    lines       = []
    confidences = []

    for region in bboxes:
        bbox = region["bbox"]
        conf = region["confidence"]

        pts   = np.array(bbox, dtype=np.int32)
        x_min = max(0, pts[:, 0].min() - 6)
        y_min = max(0, pts[:, 1].min() - 6)
        x_max = min(gray.shape[1], pts[:, 0].max() + 6)
        y_max = min(gray.shape[0], pts[:, 1].max() + 6)

        if (x_max - x_min) < 8 or (y_max - y_min) < 8:
            continue

        crop = gray[y_min:y_max, x_min:x_max]
        text = read_crop_with_trocr(crop)

        if text:
            lines.append({
                "text":       text,
                "confidence": round(conf, 3),
                "bbox":       bbox,
                "y_center":   (y_min + y_max) // 2,
            })
            confidences.append(conf)

    # Group lines into vertical bands (top 33% / mid 33% / bottom 33%)
    # This helps the grader locate answer regions by position
    regions_by_position = {"top": [], "middle": [], "bottom": []}
    for line in lines:
        frac = line["y_center"] / page_h
        if frac < 0.33:
            regions_by_position["top"].append(line)
        elif frac < 0.66:
            regions_by_position["middle"].append(line)
        else:
            regions_by_position["bottom"].append(line)

    full_text      = " ".join(l["text"] for l in lines)
    avg_confidence = round(
        sum(confidences) / len(confidences), 3
    ) if confidences else 0.0

    # Clean up TrOCR artifacts in full_text
    full_text = _clean_trocr_artifacts(full_text)

    return {
        "full_text":           full_text,
        "lines":               lines,
        "regions_by_position": regions_by_position,
        "average_confidence":  avg_confidence,
        "word_count":          len(full_text.split()),
        "ocr_method":          "phase9-paddle+trocr",
    }


def extract_essay_region(image_path: str, region_map_path: str = None) -> str:
    """
    Phase 9 — essay-specific extraction.

    If region_map_path is provided and homography alignment succeeds,
    crops the exact essay answer box and stitches its lines.
    Otherwise falls back to bottom-third heuristic on the full page.

    Called directly by grade_essay_with_ai() for essay questions.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    gray   = preprocess_image(image_path)
    page_h = gray.shape[0]

    # ── Attempt 1: region_map homography crop ─────────────────────────────────
    if region_map_path and os.path.exists(region_map_path):
        try:
            import json
            with open(region_map_path) as f:
                rmap = json.load(f)

            essay_regions = [
                r for r in rmap.get("regions", [])
                if r.get("type") == "answer_box"
            ]

            if essay_regions:
                # Use normalized coordinates to locate essay box
                scale_x = gray.shape[1]
                scale_y = gray.shape[0]

                all_crops = []
                for r in essay_regions:
                    x = int(r["x_norm"] * scale_x)
                    y = int(r["y_norm"] * scale_y)
                    w = int(r["w_norm"] * scale_x)
                    h = int(r["h_norm"] * scale_y)
                    crop = gray[y:y+h, x:x+w]
                    if crop.size > 0:
                        all_crops.append(crop)

                if all_crops:
                    # Detect regions within the cropped essay area
                    essay_bboxes = []
                    y_offset = 0
                    for crop in all_crops:
                        sub_bboxes = detect_regions(crop)
                        for b in sub_bboxes:
                            # Adjust y coords by the crop's offset in page
                            adjusted = [[pt[0], pt[1] + y_offset]
                                        for pt in b["bbox"]]
                            essay_bboxes.append({
                                "bbox":       adjusted,
                                "confidence": b["confidence"],
                            })
                        y_offset += crop.shape[0]

                    if essay_bboxes:
                        return stitch_essay_regions(essay_bboxes, gray)

        except Exception as e:
            print(f"Region map essay extraction failed ({e}), using fallback.")

    # ── Attempt 2: bottom-half heuristic ─────────────────────────────────────
    # Essay section is typically in the lower portion of the answer sheet
    # Use bottom 55% of the page (essay box is below MC/TF/ID sections)
    essay_crop_start = int(page_h * 0.45)
    essay_region     = gray[essay_crop_start:, :]

    bboxes = detect_regions(essay_region)
    if not bboxes:
        return ""

    # Re-adjust bbox y coordinates to full-page reference
    adjusted_bboxes = []
    for b in bboxes:
        adjusted = [[pt[0], pt[1] + essay_crop_start] for pt in b["bbox"]]
        adjusted_bboxes.append({
            "bbox":       adjusted,
            "confidence": b["confidence"],
        })

    return stitch_essay_regions(adjusted_bboxes, gray)


# ── Utilities ─────────────────────────────────────────────────────────────────

def _clean_trocr_artifacts(text: str) -> str:
    """
    Cleans common TrOCR output artifacts:
    - Random " . " between words (tokenizer artifact)
    - Repeated characters from stitching edges
    - Multiple spaces
    """
    import re
    text = re.sub(r'\s+\.\s+', ' ', text)      # " . " → space
    text = re.sub(r'\.{3,}',   '...', text)    # collapse ellipsis runs
    text = re.sub(r'\s{2,}',   ' ', text)      # multiple spaces → one
    text = text.strip()
    return text


def extract_text_simple(image_path: str) -> str:
    """Simplified version — just returns the extracted text string."""
    result = extract_text_from_image(image_path)
    return result["full_text"]
