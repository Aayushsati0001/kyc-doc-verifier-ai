# KYC Document Verifier

AI-powered document verification — upload an Aadhaar, PAN, or Passport, and the app checks whether the document genuinely matches what you claim it is. It also looks for visual signs of tampering, and can optionally verify that a selfie matches the photo on the document. Anything suspicious gets flagged for manual review.

## How It Works

1. You select the expected document type: "I'm expecting an Aadhaar"
2. You upload the document (image or PDF)
3. Google Gemini (a free, vision-capable AI model) examines the document and determines:
   - What the document actually is
   - Whether it matches the expected type
   - Any quality issues (blurry, cropped, glare, etc.)
   - Any visible signs of digital tampering or editing
   - Whether it should be flagged for manual review
4. (Optional) You can also upload a selfie — the app checks whether the face in the selfie matches the photo on the document

## Setup — Step by Step

### 1. Get a free Gemini API key

- Go to: https://aistudio.google.com/app/apikey
- Sign in with your Google account
- Click "Create API Key"
- Copy the key (it will look something like `AIzaSy...`)

This is free — no credit card required, and the free tier allows a generous number of requests per day.

### 2. Install dependencies

From inside the project folder:

```bash
pip install -r requirements.txt
```

### 3. Configure your API key

Copy `.env.example` to `.env` and paste your key in:

```
GEMINI_API_KEY=AIzaSy...your_actual_key_here
```

(Alternatively, the app will show an API key input box in the sidebar if no `.env` is set — you can paste it there instead.)

### 4. Run the app

```bash
streamlit run app.py
```

This opens the app in your browser at `http://localhost:8501`.

## How to Use

1. Select the document type from the dropdown (Aadhaar / PAN / Passport)
2. Upload the document file
3. (Optional) Upload a selfie to check it matches the document photo
4. Click "Verify Document"
5. Review the result:
   - 🟢 Green — verified, matches expected type
   - 🟡 Yellow — mismatch detected
   - 🔴 Red — flagged for manual review
   - Any tampering signs or quality issues are shown as tags
   - If a selfie was uploaded, a separate Face Match card shows whether the faces appear to match

## Project Structure

```
kyc-doc-verifier/
├── app.py              # Streamlit UI
├── verifier.py         # Core AI verification logic (document check + face match)
├── requirements.txt    # Dependencies
├── .env.example         # API key template
└── README.md
```

## Possible Future Enhancements

- Support more document types (Voter ID, Driving License, etc.)
- Save results to a database for an audit trail
- Batch processing — verify multiple documents at once
- OCR to extract actual field data (name, number, DOB) and cross-validate it
- Liveness detection for the selfie step (to catch a photo-of-a-photo)

## ⚠️ Important Disclaimer

This is a learning/prototype project. A production KYC system would need significantly more, including:

- **Liveness detection** — distinguishing a live selfie from a photo of a photo
- **Forensic-grade tamper/forgery detection** — the tampering check here is a visual plausibility check by an AI model, not certified document forensics
- **Government database verification** — e.g. actual UIDAI eKYC/Authentication API integration, which requires official licensing
- **Biometric-grade face matching** — the face-match feature here is an AI visual comparison, not a certified biometric match
- **Data privacy compliance** — KYC data is sensitive; encryption, secure storage, and compliance with applicable data protection laws are essential
- **Proper audit logging**

Do not use this on real users' actual documents in production without adding the above.
