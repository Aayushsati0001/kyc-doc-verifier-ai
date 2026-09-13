"""
verifier.py — Fully OFFLINE / local KYC document verification.

No third-party AI API (Gemini/OpenAI/etc.) is used here. Your document
images never leave this computer. Instead of an AI vision model, this
uses:

    - Tesseract OCR  (extracts text from the document image)
    - Regex + keyword rules  (checks if it "looks like" an Aadhaar /
      PAN / Passport, and validates the number format)
    - OpenCV  (checks image blur/brightness, and does a very basic
      face-region comparison for the selfie step)

⚠️ Trade-off (be upfront about this in an interview): this is NOT as
"smart" as an AI vision model. It checks patterns and formats, not
true visual authenticity — and the face-match step is a lightweight
similarity check, not biometric-grade face recognition.

Setup required (one-time):
    pip install pytesseract opencv-python pillow pymupdf numpy
    Install the Tesseract OCR engine itself (separate from the
    Python package):
        Windows -> https://github.com/UB-Mannheim/tesseract/wiki
    After installing on Windows, if `tesseract` isn't on PATH,
    uncomment and set TESSERACT_CMD below to the install path.
"""

import io
import re

import cv2
import numpy as np
import pytesseract
import fitz  # PyMuPDF
from PIL import Image

SUPPORTED_DOC_TYPES = ["Aadhaar Card", "PAN Card", "Passport"]

# If Tesseract isn't found automatically on Windows, set the path here:
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def configure_api(api_key=None):
    """
    Kept only so app.py's existing call signature still works.
    No external API is used anymore — this is a no-op.
    """
    return True


# ── Helpers ──────────────────────────────────────────────────────────────

def _load_image(uploaded_file) -> Image.Image:
    """Load a Streamlit-uploaded image or PDF as a PIL Image."""
    raw = uploaded_file.getvalue()
    name = getattr(uploaded_file, "name", "").lower()
    if name.endswith(".pdf"):
        doc = fitz.open(stream=raw, filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        doc.close()
        return img
    return Image.open(io.BytesIO(raw)).convert("RGB")


def _pil_to_cv2(img: Image.Image):
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def _ocr_text(img: Image.Image) -> str:
    try:
        return pytesseract.image_to_string(img)
    except Exception:
        return ""


def _blur_score(cv_img) -> float:
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def _brightness_score(cv_img) -> float:
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    return float(np.mean(gray))


_FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def _detect_faces(cv_img):
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    return _FACE_CASCADE.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))


# ── Document type detection (keyword + number-format rules) ───────────────

AADHAAR_NUM_RE = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
PASSPORT_RE = re.compile(r"\b[A-PR-WYa-pr-wy][1-9]\d\d[A-Z]{2}\d{7}\b")

AADHAAR_KEYWORDS = ["government of india", "unique identification", "aadhaar", "uidai"]
PAN_KEYWORDS = ["income tax department", "permanent account number", "income tax", "pan"]
PASSPORT_KEYWORDS = ["republic of india", "passport", "given name", "nationality", "type p"]


def _detect_document_type(text: str):
    t = text.lower()
    scores = {
        "Aadhaar Card": sum(1 for k in AADHAAR_KEYWORDS if k in t) + (2 if AADHAAR_NUM_RE.search(text) else 0),
        "PAN Card": sum(1 for k in PAN_KEYWORDS if k in t) + (2 if PAN_RE.search(text) else 0),
        "Passport": sum(1 for k in PASSPORT_KEYWORDS if k in t) + (2 if PASSPORT_RE.search(text) else 0),
    }
    best = max(scores, key=scores.get)
    return best, scores[best], scores


# ── Public: verify_document ─────────────────────────────────────────────

def verify_document(uploaded_file, expected_type: str) -> dict:
    try:
        img = _load_image(uploaded_file)
    except Exception as e:
        return {"error": f"Could not read the uploaded file: {e}"}

    cv_img = _pil_to_cv2(img)
    text = _ocr_text(img)

    detected_type, score, all_scores = _detect_document_type(text)

    quality_issues = []
    tampering_signs = []

    blur = _blur_score(cv_img)
    if blur < 60:
        quality_issues.append("Image looks blurry / low sharpness")

    brightness = _brightness_score(cv_img)
    if brightness < 60:
        quality_issues.append("Image is too dark")
    elif brightness > 220:
        quality_issues.append("Image is overexposed / too bright")

    if len(text.strip()) < 20:
        quality_issues.append("Very little readable text detected — check photo clarity/cropping")

    # Format sanity checks (NOT forensic tampering detection — pattern-based only)
    if expected_type == "Aadhaar Card" and detected_type == "Aadhaar Card" and not AADHAAR_NUM_RE.search(text):
        tampering_signs.append("Aadhaar number pattern not clearly found")
    if expected_type == "PAN Card" and detected_type == "PAN Card" and not PAN_RE.search(text):
        tampering_signs.append("PAN number format not clearly found")
    if expected_type == "Passport" and detected_type == "Passport" and not PASSPORT_RE.search(text):
        tampering_signs.append("Passport number format not clearly found")

    matches_expected = (detected_type == expected_type) and score > 0
    confidence = "high" if score >= 3 else ("medium" if score >= 1 else "low")
    flag_for_review = (not matches_expected) or bool(quality_issues) or bool(tampering_signs) or confidence == "low"

    reasoning = (
        f"Offline OCR extracted {len(text.strip())} characters of text from the image. "
        f"Keyword/number-format match scores: {all_scores}. Best match: '{detected_type}'. "
        f"This is a rule-based, fully local check (no AI vision model or external API is used) — "
        f"it validates text patterns, keywords, and image quality rather than deep visual authenticity."
    )

    return {
        "document_type": detected_type,
        "matches_expected": matches_expected,
        "confidence": confidence,
        "quality_issues": quality_issues,
        "tampering_signs": tampering_signs,
        "flag_for_review": flag_for_review,
        "reasoning": reasoning,
        "_image": img,
    }


# ── Public: verify_face_match ───────────────────────────────────────────

def _preprocess_face(face_bgr):
    """Grayscale + resize + CLAHE (adaptive contrast) so lighting differences
    between the selfie and the document photo matter less."""
    gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (200, 200))
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def verify_face_match(selfie_file, doc_image: Image.Image) -> dict:
    try:
        selfie_img = _load_image(selfie_file)
    except Exception as e:
        return {"error": f"Could not read the selfie file: {e}"}

    cv_selfie = _pil_to_cv2(selfie_img)
    cv_doc = _pil_to_cv2(doc_image)

    selfie_faces = _detect_faces(cv_selfie)
    doc_faces = _detect_faces(cv_doc)

    if len(selfie_faces) == 0:
        return {"error": "No face detected in the selfie. Please retake it in good lighting, facing the camera."}
    if len(doc_faces) == 0:
        return {"error": "No face detected on the document photo. Try a clearer, well-lit document image."}

    def crop_largest_face(cv_img, faces):
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        return cv_img[y:y + h, x:x + w]

    selfie_face = crop_largest_face(cv_selfie, selfie_faces)
    doc_face = crop_largest_face(cv_doc, doc_faces)

    selfie_proc = _preprocess_face(selfie_face)
    doc_proc = _preprocess_face(doc_face)

    # Primary signal: LBPH face recognizer (a real, lightweight local-features
    # face-recognition algorithm — much more robust than a plain histogram
    # of the whole face). Requires opencv-contrib-python.
    if not hasattr(cv2, "face"):
        return {
            "error": (
                "Face matching needs the 'opencv-contrib-python' package "
                "(it includes the face-recognition module). Run:\n"
                "pip uninstall opencv-python -y\n"
                "pip install opencv-contrib-python==4.10.0.84"
            )
        }

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train([selfie_proc], np.array([0]))
    _, lbph_distance = recognizer.predict(doc_proc)  # lower = more similar

    # Secondary signal: histogram correlation, as a sanity cross-check
    hist1 = cv2.calcHist([selfie_proc], [0], None, [256], [0, 256])
    hist2 = cv2.calcHist([doc_proc], [0], None, [256], [0, 256])
    cv2.normalize(hist1, hist1)
    cv2.normalize(hist2, hist2)
    hist_similarity = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)

    faces_match = lbph_distance < 75 and hist_similarity > 0.45

    if lbph_distance < 50 and hist_similarity > 0.65:
        confidence = "high"
    elif faces_match:
        confidence = "medium"
    else:
        confidence = "low"

    reasoning = (
        f"Detected one face in each image (fully offline, via OpenCV) and compared them using an "
        f"LBPH face-recognition model (distance {lbph_distance:.1f}, lower = more similar; match "
        f"threshold < 75) plus a histogram similarity cross-check ({hist_similarity:.2f}). "
        f"This is a lightweight, local comparison — NOT biometric-grade or as accurate as a deep-learning "
        f"face model — meant as a reasonable local sanity check rather than a certified identity match."
    )

    return {
        "faces_match": faces_match,
        "confidence": confidence,
        "reasoning": reasoning,
        "_selfie_image": selfie_img,
    }
