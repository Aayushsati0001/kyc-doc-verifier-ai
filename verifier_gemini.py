"""
verifier_gemini.py - Cloud AI (Google Gemini) KYC document verification.

Uses Gemini's multimodal vision model to inspect the document image and
return a structured verdict (type match, quality issues, tampering
signs, reasoning). Requires a Gemini API key and an internet connection
- the document image is sent to Google's servers for processing.

Requires a free Google Gemini API key. Get one at:
    https://aistudio.google.com/app/apikey
"""

import io
import json
import re
import time

import fitz  # PyMuPDF
from PIL import Image
from google import genai
from google.genai import types

SUPPORTED_DOC_TYPES = ["Aadhaar Card", "PAN Card", "Passport"]

# Try the main Flash model first; if it's overloaded (503) or rate-limited
# (429) even after retries, automatically fall back to the Lite model,
# which runs on a separate, often less congested quota pool.
PRIMARY_MODEL = "gemini-flash-latest"
FALLBACK_MODEL = "gemini-flash-lite-latest"

MAX_RETRIES = 3
BASE_DELAY_SECONDS = 2  # doubles each retry: 2s, 4s, 8s

_client = None


def configure_api(api_key: str):
    global _client
    _client = genai.Client(api_key=api_key)


def _is_transient_error(exc: Exception) -> bool:
    """True for errors worth retrying/falling back on (server overloaded,
    rate limited, temporary network hiccups) - not for things like a bad
    API key, which retrying won't fix."""
    status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if status in (429, 500, 502, 503, 504):
        return True
    msg = str(exc).lower()
    return any(s in msg for s in ["unavailable", "overloaded", "high demand", "rate limit", "timeout"])


def _generate_with_resilience(contents):
    """Calls Gemini with retry + exponential backoff on the primary model,
    then falls back to a second (usually less busy) model if the primary
    still fails after all retries. Raises the last error if everything fails."""
    last_error = None
    for model in (PRIMARY_MODEL, FALLBACK_MODEL):
        for attempt in range(MAX_RETRIES):
            try:
                return _client.models.generate_content(model=model, contents=contents)
            except Exception as e:
                last_error = e
                if not _is_transient_error(e):
                    raise  # not worth retrying (e.g. bad API key) - fail fast
                if attempt < MAX_RETRIES - 1:
                    time.sleep(BASE_DELAY_SECONDS * (2 ** attempt))
        # all retries on this model exhausted - try the next model in the loop
    raise last_error


# -- Helpers --------------------------------------------------------------

def _load_image(uploaded_file) -> Image.Image:
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


def _image_to_jpeg_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```json\s*|\s*```$", "", cleaned, flags=re.MULTILINE).strip("`").strip()
    return json.loads(cleaned)


DOC_PROMPT_TEMPLATE = """You are a KYC document verification assistant. Look at this ID document image
and determine:
1. What type of document this is: one of "Aadhaar Card", "PAN Card", "Passport", or "Unknown".
2. Whether it matches the expected type: "{expected_type}" (true/false).
3. Your confidence: "high", "medium", or "low".
4. Any image quality issues (blur, glare, cropping, poor lighting) as a list of short strings. Empty list if none.
5. Any signs the document might be tampered with (mismatched fonts, inconsistent alignment, obvious digital
   editing artifacts) as a list of short strings. Leave empty if none found - do not guess.
6. Whether this should be flagged for manual human review (true if quality issues, tampering signs,
   type mismatch, or low confidence).
7. A short 1-3 sentence reasoning explaining your findings.

Respond with ONLY a raw JSON object (no markdown, no code fences) with exactly these keys:
document_type, matches_expected, confidence, quality_issues, tampering_signs, flag_for_review, reasoning
"""

FACE_PROMPT = """You are comparing two face photos: a live selfie and a photo from an ID document.
Determine if they appear to show the same person.

Respond with ONLY a raw JSON object (no markdown, no code fences) with exactly these keys:
faces_match (true or false), confidence ("high"/"medium"/"low"), reasoning (1-3 sentences).
"""


# -- Public: verify_document ---------------------------------------------

def verify_document(uploaded_file, expected_type: str) -> dict:
    if _client is None:
        return {"error": "Gemini API is not configured. Please provide an API key in the sidebar."}
    try:
        img = _load_image(uploaded_file)
    except Exception as e:
        return {"error": f"Could not read the uploaded file: {e}"}

    raw_text = ""
    try:
        response = _generate_with_resilience([
            types.Part.from_bytes(data=_image_to_jpeg_bytes(img), mime_type="image/jpeg"),
            DOC_PROMPT_TEMPLATE.format(expected_type=expected_type),
        ])
        raw_text = response.text
        result = _extract_json(raw_text)
    except json.JSONDecodeError:
        return {"error": "The AI returned an unexpected format. Please try again.", "raw_response": raw_text}
    except Exception as e:
        return {"error": f"AI request failed after retries: {e}"}

    result.setdefault("quality_issues", [])
    result.setdefault("tampering_signs", [])
    result["_image"] = img
    return result


# -- Public: verify_face_match -------------------------------------------

def verify_face_match(selfie_file, doc_image: Image.Image) -> dict:
    if _client is None:
        return {"error": "Gemini API is not configured. Please provide an API key in the sidebar."}
    try:
        selfie_img = _load_image(selfie_file)
    except Exception as e:
        return {"error": f"Could not read the selfie file: {e}"}

    raw_text = ""
    try:
        response = _generate_with_resilience([
            types.Part.from_bytes(data=_image_to_jpeg_bytes(selfie_img), mime_type="image/jpeg"),
            types.Part.from_bytes(data=_image_to_jpeg_bytes(doc_image), mime_type="image/jpeg"),
            FACE_PROMPT,
        ])
        raw_text = response.text
        result = _extract_json(raw_text)
    except json.JSONDecodeError:
        return {"error": "The AI returned an unexpected format. Please try again.", "raw_response": raw_text}
    except Exception as e:
        return {"error": f"AI request failed after retries: {e}"}

    result["_selfie_image"] = selfie_img
    return result