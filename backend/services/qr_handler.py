# services/qr_handler.py
# Handles QR code generation and scanning for answer sheets
#
# How it works:
#   Generation: Creates a QR code image encoding exam info as JSON
#   Scanning:   Reads a QR code from an uploaded answer sheet image
#
# QR payload format:
#   { "exam_id": 1, "token": "abc123...", "exam_name": "Midterm" }

import qrcode
import json
import secrets
import cv2
import numpy as np
from PIL import Image
from pyzbar.pyzbar import decode as pyzbar_decode


# ─── Token Generation ─────────────────────────────────────────────────────────

def generate_qr_token() -> str:
    """
    Generates a unique 16-character token for an exam.
    Used to identify which exam an answer sheet belongs to.
    """
    return secrets.token_hex(8)  # 16 hex characters


# ─── QR Code Generation ───────────────────────────────────────────────────────

def generate_qr_code(exam_id: int, token: str, exam_name: str) -> Image.Image:
    """
    Creates a QR code image encoding exam identification data.

    Args:
        exam_id:   Database ID of the exam
        token:     Unique token for this exam (from generate_qr_token)
        exam_name: Human-readable exam name (included for debugging)

    Returns:
        PIL Image of the QR code (can be embedded into the PDF)
    """
    payload = json.dumps({
        "exam_id":   exam_id,
        "token":     token,
        "exam_name": exam_name,
    })

    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction
        box_size=6,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    return img.convert("RGB")


# ─── QR Code Scanning ─────────────────────────────────────────────────────────

def scan_qr_from_image(image_path: str) -> dict | None:
    """
    Scans an uploaded answer sheet image for a QR code.

    Tries multiple preprocessing strategies to maximize detection rate:
    1. Raw image
    2. Grayscale
    3. Thresholded

    Args:
        image_path: Path to the uploaded student answer sheet image

    Returns:
        Decoded payload dict if QR found, None if not found
    """
    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        return None

    # Strategy 1: Try raw image first
    result = _try_decode(img_bgr)
    if result:
        return result

    # Strategy 2: Grayscale
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    result = _try_decode(gray)
    if result:
        return result

    # Strategy 3: Adaptive threshold (helps with low contrast / shadows)
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=11,
        C=2,
    )
    result = _try_decode(thresh)
    if result:
        return result

    # Strategy 4: Upscale — helps if image is low resolution
    scale   = 2.0
    upscale = cv2.resize(img_bgr, None, fx=scale, fy=scale,
                         interpolation=cv2.INTER_CUBIC)
    result  = _try_decode(upscale)
    if result:
        return result

    return None


def _try_decode(image: np.ndarray) -> dict | None:
    """
    Attempts to decode a QR code from a numpy image array.
    Returns parsed payload dict or None.
    """
    try:
        # Convert to PIL for pyzbar
        if len(image.shape) == 2:
            pil_img = Image.fromarray(image)
        else:
            pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

        decoded = pyzbar_decode(pil_img)
        if not decoded:
            return None

        for item in decoded:
            if item.type == "QRCODE":
                raw = item.data.decode("utf-8")
                payload = json.loads(raw)
                # Validate expected keys are present
                if "exam_id" in payload and "token" in payload:
                    return payload

    except Exception as e:
        print(f"QR decode attempt failed: {e}")

    return None
