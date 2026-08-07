"""
KYC Document Verifier — Core Logic
====================================
Uses Google Gemini Vision (free tier) to look at an uploaded document
image and determine:
  1. What type of document it actually is (Aadhaar / PAN / Passport / Other)
  2. Whether it matches the type the user claims to be uploading
  3. Whether anything looks suspicious (blurry, cropped, edited, wrong doc)
  4. Whether the document shows visible signs of digital tampering/editing
  5. (Optional) Whether a selfie photo matches the face on the document

No document data is stored anywhere — everything happens in memory.
"""

import os
import io
import json
import re
from PIL import Image
import fitz  # PyMuPDF, used only to render PDF pages to images
from google import genai

# ── Configuration ───────────────────────────────────────────────────────────
MODEL_NAME = "gemini-3.1-flash-lite"  # fast + free-tier friendly, supports vision

SUPPORTED_DOC_TYPES = ["Aadhaar Card", "PAN Card", "Passport"]

_client = None


def configure_api(api_key: str):
    """Set up the Gemini client with the user's API key."""
    global _client
    _client = genai.Client(api_key=api_key)


# ── File handling ─────────────────────────────────────────────────────────
def load_as_image(uploaded_file) -> Image.Image:
    """
    Accepts a Streamlit UploadedFile (image or PDF) and returns a PIL Image.
    For PDFs, only the first page is used (KYC docs are almost always
    single-page).
    """
    filename = uploaded_file.name.lower()
    file_bytes = uploaded_file.read()

    if filename.endswith(".pdf"):
        pdf = fitz.open(stream=file_bytes, filetype="pdf")
        page = pdf[0]
        # Render at higher resolution for better AI readability
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        pdf.close()
        return img
    else:
        return Image.open(io.BytesIO(file_bytes)).convert("RGB")


# ── Prompt: document type + tampering check ────────────────────────────────
def build_prompt(expected_type: str) -> str:
    return f"""You are a KYC (Know Your Customer) document verification assistant
used by a bank/merchant onboarding team.

You are shown ONE image of a document that a user uploaded, claiming it is
their **{expected_type}**.

Carefully examine the image and determine:

1. document_type: What kind of official document is this, actually?
   Choose one of: "Aadhaar Card", "PAN Card", "Passport", "Other/Unrecognized"

2. matches_expected: true if document_type equals "{expected_type}", else false

3. confidence: "high", "medium", or "low" — how confident are you in the
   document_type classification?

4. quality_issues: a list of any problems you notice, such as:
   - "blurry" / "low resolution"
   - "partially cropped or cut off"
   - "glare or shadow obscuring text"
   - "appears to be a photo of a screen, not the physical document"
   - "no clear identifying text/number visible"
   (Return an empty list if none apply.)

5. tampering_signs: a list of any visible signs that the document image may
   have been digitally edited or tampered with, such as:
   - "font or text style looks inconsistent with the rest of the document"
   - "text alignment or spacing looks unnatural around the ID number"
   - "sharp edges or pixelation inconsistency around the photo, suggesting a
     pasted-in image"
   - "colors or resolution mismatch between sections of the document"
   - "visible copy-paste artifacts or cloned regions"
   - "layout does not match the standard official template for this
     document type"
   (Return an empty list if nothing looks suspicious. This is a visual
   plausibility check only, not forensic-grade authentication — only flag
   things you can actually see, don't guess.)

6. flag_for_review: true if this document should be manually reviewed by a
   human because it does NOT match the expected type, OR because of serious
   quality issues, OR because of tampering signs that make it unreliable.
   Otherwise false.

7. reasoning: 1-2 short sentences explaining your decision in plain English.

Respond with ONLY valid JSON, no markdown formatting, no code fences, in
exactly this shape:

{{
  "document_type": "...",
  "matches_expected": true,
  "confidence": "...",
  "quality_issues": [],
  "tampering_signs": [],
  "flag_for_review": false,
  "reasoning": "..."
}}
"""


# ── Prompt: face match ──────────────────────────────────────────────────────
def build_face_match_prompt() -> str:
    return """You are a KYC verification assistant. You are shown TWO images:
  IMAGE 1: a live selfie photo of a person
  IMAGE 2: an identity document containing a photo of a person

Compare the face in the selfie (IMAGE 1) to the face in the document photo
(IMAGE 2) and determine whether they appear to be the same person.

Consider that document photos are often older, lower resolution, or taken
under different lighting than a live selfie — focus on stable facial
features (face shape, eyes, nose, eyebrows) rather than lighting, angle, or
hairstyle differences.

Respond with ONLY valid JSON, no markdown formatting, no code fences, in
exactly this shape:

{
  "faces_match": true,
  "confidence": "high",
  "reasoning": "..."
}

Where:
- faces_match: true if you believe it's plausibly the same person, false if
  they clearly look like different people
- confidence: "high", "medium", or "low"
- reasoning: 1-2 short sentences explaining your decision in plain English
"""


# ── Main document verification call ─────────────────────────────────────────
def verify_document(uploaded_file, expected_type: str) -> dict:
    """
    Runs the full pipeline: load file -> send to Gemini -> parse response.
    Returns a dict with the parsed result, or an 'error' key on failure.
    """
    try:
        image = load_as_image(uploaded_file)
    except Exception as e:
        return {"error": f"Could not read the file: {e}"}

    if _client is None:
        return {"error": "API not configured. Call configure_api(api_key) first."}

    prompt = build_prompt(expected_type)

    try:
        response = _client.models.generate_content(
            model=MODEL_NAME,
            contents=[prompt, image],
        )
        raw_text = response.text.strip()
    except Exception as e:
        return {"error": f"AI request failed: {e}"}

    raw_text = re.sub(r"^```(json)?|```$", "", raw_text.strip(), flags=re.MULTILINE).strip()

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        return {"error": "Could not parse AI response.", "raw_response": raw_text}

    # Backward-safety: make sure keys always exist even if the model skips one
    result.setdefault("quality_issues", [])
    result.setdefault("tampering_signs", [])

    result["_image"] = image  # attach for display in the UI
    return result


# ── Face-match verification call ────────────────────────────────────────────
def verify_face_match(selfie_file, document_image: Image.Image) -> dict:
    """
    Compares a selfie upload against the photo on the already-loaded
    document image. Returns a dict with the parsed result, or an 'error' key.
    """
    try:
        selfie_image = load_as_image(selfie_file)
    except Exception as e:
        return {"error": f"Could not read the selfie file: {e}"}

    if _client is None:
        return {"error": "API not configured. Call configure_api(api_key) first."}

    prompt = build_face_match_prompt()

    try:
        response = _client.models.generate_content(
            model=MODEL_NAME,
            contents=[prompt, selfie_image, document_image],
        )
        raw_text = response.text.strip()
    except Exception as e:
        return {"error": f"AI request failed: {e}"}

    raw_text = re.sub(r"^```(json)?|```$", "", raw_text.strip(), flags=re.MULTILINE).strip()

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        return {"error": "Could not parse AI response.", "raw_response": raw_text}

    result["_selfie_image"] = selfie_image
    return result
