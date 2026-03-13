# services/ocr.py
# Handles image preprocessing and OCR text extraction
# Pipeline: Load image → Preprocess with OpenCV → Extract text with EasyOCR

import cv2
import numpy as np
import easyocr
import os
from PIL import Image

# ─── EasyOCR Reader ───────────────────────────────────────────────────────────
# Initialized once and reused — loading the model is slow (~5 seconds first time)
# gpu=False means it runs on CPU, which works fine without a graphics card
_reader = None

def get_reader():
    global _reader
    if _reader is None:
        print("Loading EasyOCR model... (this takes a moment on first run)")
        _reader = easyocr.Reader(['en'], gpu=False)
        print("EasyOCR model loaded.")
    return _reader


# ─── Image Preprocessing ──────────────────────────────────────────────────────

def preprocess_image(image_path: str) -> np.ndarray:
    """
    Cleans up a scanned exam paper image before OCR:
    1. Convert to grayscale        — removes color noise
    2. Resize if too small         — ensures OCR reads small text
    3. Deskew                      — straightens tilted scans
    4. Denoise                     — removes scan artifacts
    5. Adaptive threshold          — makes text stand out sharply
    """
    # Load image
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not load image: {image_path}")

    # Step 1: Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Step 2: Upscale if image is too small (OCR works best at 300+ DPI equivalent)
    h, w = gray.shape
    if w < 1000:
        scale = 1000 / w
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # Step 3: Deskew — detect and correct tilt up to ±15 degrees
    gray = deskew(gray)

    # Step 4: Denoise — removes salt-and-pepper noise from scans
    gray = cv2.fastNlMeansDenoising(gray, h=10)

    # Step 5: Adaptive threshold — makes handwriting/text black on white background
    # This handles uneven lighting across the page
    processed = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31,
        C=15
    )

    return processed


def deskew(image: np.ndarray) -> np.ndarray:
    """
    Detects the angle of text lines and rotates the image to straighten them.
    Works by finding the dominant angle of dark pixel runs in the image.
    Only corrects angles within ±15 degrees to avoid over-rotating badly scanned pages.
    """
    # Find all non-white pixel coordinates
    coords = np.column_stack(np.where(image < 128))
    if len(coords) < 100:
        return image  # Not enough content to detect angle

    # Use minAreaRect to find the angle of the text block
    angle = cv2.minAreaRect(coords)[-1]

    # Normalize angle to -15..+15 range
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    # Only deskew if tilt is significant (> 0.5 degrees) but not extreme (> 15 degrees)
    if abs(angle) < 0.5 or abs(angle) > 15:
        return image

    # Rotate image around its center
    h, w = image.shape
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        image, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE
    )
    return rotated


# ─── Text Extraction ──────────────────────────────────────────────────────────

def extract_text_from_image(image_path: str) -> dict:
    """
    Main function: takes an image path, preprocesses it, runs EasyOCR,
    and returns the extracted text along with confidence scores.

    Returns:
        {
            "full_text": "...",           # All extracted text joined
            "lines": [...],              # Individual text lines with confidence
            "average_confidence": 0.85,  # How confident OCR is (0.0 - 1.0)
            "word_count": 42,
        }
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    # Preprocess the image
    processed = preprocess_image(image_path)

    # Save preprocessed image to a temp file for EasyOCR
    # (EasyOCR accepts numpy arrays directly too, but file path is more stable)
    temp_path = image_path + "_preprocessed.png"
    cv2.imwrite(temp_path, processed)

    try:
        reader = get_reader()

        # Run OCR — returns list of [bounding_box, text, confidence]
        results = reader.readtext(temp_path, detail=1, paragraph=False)

        # Parse results
        lines = []
        confidences = []

        for (bbox, text, confidence) in results:
            text = text.strip()
            if text and confidence > 0.1:  # Filter out very low confidence noise
                lines.append({
                    "text":       text,
                    "confidence": round(confidence, 3),
                    "bbox":       bbox,  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                })
                confidences.append(confidence)

        full_text = " ".join([l["text"] for l in lines])
        avg_confidence = round(sum(confidences) / len(confidences), 3) if confidences else 0.0

        return {
            "full_text":          full_text,
            "lines":              lines,
            "average_confidence": avg_confidence,
            "word_count":         len(full_text.split()),
        }

    finally:
        # Always clean up the temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)


def extract_text_simple(image_path: str) -> str:
    """
    Simplified version — just returns the extracted text string.
    Used internally when we only need the text, not the full metadata.
    """
    result = extract_text_from_image(image_path)
    return result["full_text"]
