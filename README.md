# 🪪 KYC Document Verifier

AI-powered KYC (Know Your Customer) document verification tool built for banks, fintechs, and merchant onboarding platforms. It checks Aadhaar Card / PAN Card / Passport uploads for type mismatches, image quality issues, and optionally verifies a live selfie against the document photo — with **two interchangeable verification engines**: a cloud AI mode (Google Gemini) and a fully offline/local mode.

---

## 🎥 What It Does

1. **Sign In / Register** — merchant accounts are created once (name, email, password, age, address) and persisted; returning users just sign in with email + password.
2. **Select document type** — Aadhaar Card, PAN Card, or Passport.
3. **Upload & verify** — the document is checked for:
   - Detected document type vs. expected type
   - Confidence level
   - Image quality issues (blur, poor lighting, cropping)
   - Possible tampering signs
4. **Optional face match** — compare a live selfie against the document photo.
5. **Final verdict** — Pass / Flagged for manual review, with reasoning.
6. Every verification is **permanently logged** to a local SQLite database, with duplicate-merchant history visible in the sidebar.

---

## 🧱 Tech Stack

### Frontend
- **[Streamlit](https://streamlit.io/)** — the entire UI (forms, cards, file uploads, theming) is built in pure Python using Streamlit, styled with custom CSS injected via `st.markdown` (dark/light themes, glowing cards, gradient hero section).

### Backend / AI
Two interchangeable verification engines, selectable at runtime from the sidebar:

| Engine | File | How it works |
|---|---|---|
| **Cloud AI** | `verifier_gemini.py` | Sends the document image to **Google Gemini** (`gemini-flash-latest`, multimodal vision model) with a structured prompt, and parses the JSON response for the verdict. |
| **Offline / Local** | `verifier_offline.py` | Runs entirely on-device: **Tesseract OCR** extracts text, regex + keyword rules classify the document type and validate number formats (Aadhaar/PAN/Passport patterns), **OpenCV** checks blur/brightness, and an **LBPH face recognizer** (with CLAHE contrast preprocessing) handles the selfie-to-document face match. No data ever leaves the machine in this mode. |

### Data & Persistence
- **SQLite** (`db.py`) — two tables:
  - `merchants` — registered accounts (passwords stored as SHA-256 hashes)
  - `verifications` — permanent log of every document check (merchant, document type, result, timestamp)
- **PyMuPDF (fitz)** — converts PDF uploads to images before processing.

---

## 🔌 How the API Was Used

- The Gemini engine uses the official **`google-genai`** Python SDK, calling `client.models.generate_content()` with the document image (as inline JPEG bytes) plus a structured text prompt instructing the model to return a raw JSON object with fixed keys (`document_type`, `matches_expected`, `confidence`, `quality_issues`, `tampering_signs`, `flag_for_review`, `reasoning`).
- The JSON response is parsed manually (stripping markdown code fences defensively) rather than using a schema-enforcing library like LangChain's structured output — a deliberate simplicity trade-off for a small, single-provider project.
- **Model name is not hardcoded to a dated version** — it uses the `gemini-flash-latest` alias so it keeps working as Google rotates model versions, instead of breaking when a specific dated model is deprecated.

---

## ⚙️ What Was Optimized / Reduced

Several rounds of hardening were added after initial testing surfaced real-world failure modes:

- **Retry with exponential backoff + automatic model fallback** — if the primary Gemini model returns a transient error (503 overloaded, 429 rate-limited), the app retries a few times with increasing delay, then automatically falls back to a second, separately-quota'd model (`gemini-flash-lite-latest`) instead of failing outright.
- **Removed hard dependency on a paid/cloud API** — added a complete offline verification path (OCR + rule-based checks + local face recognition) so the tool can run with zero external API calls and zero cost when privacy or connectivity is a concern.
- **Fixed a Markdown/HTML rendering bug** — Streamlit's markdown parser silently broke into a "code block" (tiny monospace, literal tags visible) whenever an optional field (like phone number) was blank, because the blank line prematurely closed the HTML block. Fixed with a small `render_html()` helper that strips blank lines/indentation before rendering.
- **Removed non-ASCII characters** from strings that get sent over the network or could be printed in a traceback, after a `UnicodeEncodeError` surfaced on Windows consoles with non-UTF-8 default encoding.
- **Image handling** — uploaded documents/selfies are normalized to JPEG before being sent to the API, keeping payloads small and consistent regardless of the original upload format (PNG, PDF page, etc.).

---

## 🖥️ Running It Locally

```bash
# 1. Clone and enter the project
git clone <this-repo-url>
cd kyc-doc-verifier

# 2. Create and activate a virtual environment
python -m venv venv312
venv312\Scripts\Activate.ps1        # Windows PowerShell
# source venv312/bin/activate       # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional, for Cloud AI mode) Install Tesseract OCR for Offline mode
#    https://github.com/UB-Mannheim/tesseract/wiki

# 5. (Optional, for Cloud AI mode) Add your free Gemini API key
#    Get one at https://aistudio.google.com/app/apikey
#    Either paste it into the sidebar at runtime, or create a .env file:
echo GEMINI_API_KEY=your_key_here > .env

# 6. Run the app
python -m streamlit run app.py
```

The app opens at `http://localhost:8501`. No API key is required at all if you select **Offline (Local)** mode from the sidebar.

---

## ⚠️ Disclaimer

This is a learning/prototype project. Quality, tampering, and face-match checks here are AI/heuristic **plausibility checks**, not forensic-grade or biometric-grade authentication. A production KYC system would additionally need liveness detection, official database cross-verification, certified document forensics, encrypted storage, and compliance with local data-protection law (e.g. India's DPDP Act).
