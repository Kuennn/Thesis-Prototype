# services/ocr.py
# Hybrid OCR Pipeline — EasyOCR + TrOCR
#
# How it works:
#   Step 1: OpenCV  — preprocesses image (deskew, denoise, threshold)
#   Step 2: EasyOCR — detects WHERE text regions are on the page
#   Step 3: TrOCR   — reads WHAT each text region says (better handwriting)
#   Step 4: Combine — joins all regions into full extracted text

import cv2
import numpy as np
import easyocr
import os
import torch
from PIL import Image
from transformers import TrOCRProcessor, VisionEncoderDecoderModel

# ── Model Singletons ──────────────────────────────────────────────────────────
_easyocr_reader  = None
_trocr_processor = None
_trocr_model     = None

def get_easyocr():
    global _easyocr_reader
    if _easyocr_reader is None:
        print("Loading EasyOCR model...")
        _easyocr_reader = easyocr.Reader(['en'], gpu=False)
        print("EasyOCR loaded.")
    return _easyocr_reader

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


# ── Image Preprocessing ───────────────────────────────────────────────────────

def preprocess_image(image_path: str) -> np.ndarray:
    """
    Cleans up a scanned exam paper image before OCR:
    1. Convert to grayscale
    2. Resize if too small
    3. Deskew
    4. Denoise
    5. Adaptive threshold
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not load image: {image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    h, w = gray.shape
    if w < 1000:
        scale = 1000 / w
        gray  = cv2.resize(gray, None, fx=scale, fy=scale,
                           interpolation=cv2.INTER_CUBIC)

    gray = deskew(gray)
    gray = cv2.fastNlMeansDenoising(gray, h=10)

    processed = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31,
        C=15
    )

    return processed


def deskew(image: np.ndarray) -> np.ndarray:
    """Detects and corrects tilt angle of scanned pages."""
    coords = np.column_stack(np.where(image < 128))
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


# ── TrOCR Region Reader ───────────────────────────────────────────────────────

def read_region_with_trocr(image: np.ndarray, bbox: list) -> str:
    """
    Crops a detected text region and reads it with TrOCR.
    bbox format from EasyOCR: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
    """
    try:
        pts   = np.array(bbox, dtype=np.int32)
        x_min = max(0, pts[:, 0].min() - 4)
        y_min = max(0, pts[:, 1].min() - 4)
        x_max = min(image.shape[1], pts[:, 0].max() + 4)
        y_max = min(image.shape[0], pts[:, 1].max() + 4)

        if (x_max - x_min) < 5 or (y_max - y_min) < 5:
            return ""

        cropped = image[y_min:y_max, x_min:x_max]

        if len(cropped.shape) == 2:
            cropped_rgb = cv2.cvtColor(cropped, cv2.COLOR_GRAY2RGB)
        else:
            cropped_rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)

        pil_image = Image.fromarray(cropped_rgb)

        if pil_image.height < 32:
            scale     = 32 / pil_image.height
            new_w     = int(pil_image.width * scale)
            pil_image = pil_image.resize((new_w, 32), Image.LANCZOS)

        processor, model = get_trocr()
        pixel_values     = processor(pil_image, return_tensors="pt").pixel_values

        with torch.no_grad():
            generated = model.generate(pixel_values, max_new_tokens=128)

        text = processor.batch_decode(generated, skip_special_tokens=True)[0]
        return text.strip()

    except Exception as e:
        print(f"TrOCR region read failed: {e}")
        return ""


# ── Main Hybrid Extraction ────────────────────────────────────────────────────

def extract_text_from_image(image_path: str) -> dict:
    """
    Main function: Hybrid OCR pipeline.
    EasyOCR finds text regions, TrOCR reads each region.

    Returns:
        {
            "full_text":          str,
            "lines":              list,
            "average_confidence": float,
            "word_count":         int,
            "ocr_method":         str,
        }
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    # Preprocess — returns numpy array, no temp file needed
    processed = preprocess_image(image_path)

    # EasyOCR can accept a numpy array directly — no disk write needed
    # This avoids Windows file locking errors with temp files
    reader       = get_easyocr()
    easy_results = reader.readtext(processed, detail=1, paragraph=False)

    if not easy_results:
        return {
            "full_text":          "",
            "lines":              [],
            "average_confidence": 0.0,
            "word_count":         0,
            "ocr_method":         "hybrid",
        }

    lines       = []
    confidences = []

    for (bbox, easy_text, confidence) in easy_results:
        if confidence < 0.1:
            continue

        trocr_text = read_region_with_trocr(processed, bbox)
        final_text = trocr_text if trocr_text else easy_text

        if final_text:
            lines.append({
                "text":       final_text,
                "easy_text":  easy_text,
                "trocr_text": trocr_text,
                "confidence": round(confidence, 3),
                "bbox":       bbox,
            })
            confidences.append(confidence)

    lines.sort(key=lambda x: (
        min(pt[1] for pt in x["bbox"]),
        min(pt[0] for pt in x["bbox"]),
    ))

    full_text      = " ".join([l["text"] for l in lines])
    avg_confidence = round(
        sum(confidences) / len(confidences), 3
    ) if confidences else 0.0

    return {
        "full_text":          full_text,
        "lines":              lines,
        "average_confidence": avg_confidence,
        "word_count":         len(full_text.split()),
        "ocr_method":         "hybrid (EasyOCR + TrOCR)",
    }


def extract_text_simple(image_path: str) -> str:
    """Simplified version — just returns the extracted text string."""
    result = extract_text_from_image(image_path)
    return result["full_text"]
