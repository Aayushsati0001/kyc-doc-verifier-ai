"""
KYC Document Verifier — Streamlit App
========================================
Run:
    streamlit run app.py

Requires a free Google Gemini API key. Get one at:
    https://aistudio.google.com/app/apikey
"""

import os
import streamlit as st
from dotenv import load_dotenv
from verifier import configure_api, verify_document, verify_face_match, SUPPORTED_DOC_TYPES

load_dotenv()

st.set_page_config(
    page_title="KYC Document Verifier",
    page_icon="🪪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom styling ──────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .stApp {
        background: radial-gradient(circle at top left, #1a1f3c 0%, #0b0e1a 55%, #05070d 100%);
        color: #E6E8F0;
    }

    /* Hero header */
    .hero {
        background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 45%, #EC4899 100%);
        border-radius: 20px;
        padding: 34px 40px;
        margin-bottom: 28px;
        box-shadow: 0 20px 50px -20px rgba(139, 92, 246, 0.55);
    }
    .hero h1 {
        margin: 0;
        font-weight: 800;
        font-size: 2.1rem;
        color: white;
    }
    .hero p {
        margin: 6px 0 0 0;
        color: rgba(255,255,255,0.9);
        font-size: 1rem;
    }

    /* Section card */
    .card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px;
        padding: 24px 28px;
        margin-bottom: 20px;
        backdrop-filter: blur(6px);
    }

    /* Result banners */
    .banner {
        border-radius: 14px;
        padding: 16px 22px;
        font-weight: 700;
        font-size: 1.05rem;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .banner-flag {
        background: linear-gradient(90deg, rgba(239,68,68,0.18), rgba(239,68,68,0.05));
        border: 1px solid rgba(239,68,68,0.45);
        color: #FCA5A5;
    }
    .banner-mismatch {
        background: linear-gradient(90deg, rgba(245,158,11,0.18), rgba(245,158,11,0.05));
        border: 1px solid rgba(245,158,11,0.45);
        color: #FCD34D;
    }
    .banner-verified {
        background: linear-gradient(90deg, rgba(34,197,94,0.18), rgba(34,197,94,0.05));
        border: 1px solid rgba(34,197,94,0.45);
        color: #86EFAC;
    }

    /* Info rows */
    .info-row {
        display: flex;
        justify-content: space-between;
        padding: 10px 0;
        border-bottom: 1px solid rgba(255,255,255,0.07);
        font-size: 0.95rem;
    }
    .info-row:last-child { border-bottom: none; }
    .info-label { color: #9CA3AF; }
    .info-value { color: #F3F4F6; font-weight: 600; }

    .pill {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 700;
    }
    .pill-high { background: rgba(34,197,94,0.18); color: #86EFAC; }
    .pill-medium { background: rgba(245,158,11,0.18); color: #FCD34D; }
    .pill-low { background: rgba(239,68,68,0.18); color: #FCA5A5; }

    .issue-chip {
        display: inline-block;
        background: rgba(239,68,68,0.12);
        border: 1px solid rgba(239,68,68,0.3);
        color: #FCA5A5;
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 0.82rem;
        margin: 3px 6px 3px 0;
    }

    .tamper-chip {
        display: inline-block;
        background: rgba(245,158,11,0.12);
        border: 1px solid rgba(245,158,11,0.35);
        color: #FCD34D;
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 0.82rem;
        margin: 3px 6px 3px 0;
    }

    .reasoning-box {
        background: rgba(99,102,241,0.1);
        border-left: 3px solid #818CF8;
        border-radius: 8px;
        padding: 14px 18px;
        color: #E0E7FF;
        font-size: 0.95rem;
        margin-top: 10px;
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #12162b 0%, #0b0e1a 100%);
        border-right: 1px solid rgba(255,255,255,0.06);
    }

    .stButton>button {
        background: linear-gradient(135deg, #6366F1, #EC4899);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 10px 26px;
        font-weight: 700;
        font-size: 1rem;
        box-shadow: 0 10px 25px -10px rgba(236, 72, 153, 0.6);
    }
    .stButton>button:hover {
        filter: brightness(1.1);
    }

    footer, #MainMenu { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Hero header ──────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <h1>🪪 KYC Document Verifier</h1>
    <p>AI-powered document check for Aadhaar, PAN & Passport — flags mismatches, tampering signs & face mismatches instantly.</p>
</div>
""", unsafe_allow_html=True)

# ── API Key handling ────────────────────────────────────────────────────────
api_key = os.getenv("GEMINI_API_KEY")

with st.sidebar:
    st.markdown("### ⚙️ Setup")
    if not api_key:
        api_key_input = st.text_input(
            "Google Gemini API Key",
            type="password",
            help="Get a free key at https://aistudio.google.com/app/apikey",
        )
        if api_key_input:
            api_key = api_key_input
    else:
        st.success("API key loaded from .env ✅")

    st.markdown("---")
    st.markdown("### 🧭 How it works")
    st.markdown(
        "**1.** Pick the document type you expect\n\n"
        "**2.** Upload the file (image or PDF)\n\n"
        "**3.** Optionally upload a selfie for face-match\n\n"
        "**4.** AI checks type match, quality & tampering signs\n\n"
        "**5.** Mismatches or issues get flagged 🚩"
    )
    st.markdown("---")
    st.caption("Built with Streamlit + Google Gemini Vision")

if not api_key:
    st.warning("👈 Please enter your Gemini API key in the sidebar to continue.")
    st.stop()

configure_api(api_key)

# ── Main form ────────────────────────────────────────────────────────────
st.markdown('<div class="card">', unsafe_allow_html=True)
col_a, col_b = st.columns([1, 1.6])
with col_a:
    expected_type = st.selectbox("📋 Expected document type", SUPPORTED_DOC_TYPES)
with col_b:
    uploaded_file = st.file_uploader(
        "📤 Upload the document (image or PDF)",
        type=["jpg", "jpeg", "png", "pdf"],
    )

selfie_file = st.file_uploader(
    "🤳 (Optional) Upload a selfie to check it's the same person as the document photo",
    type=["jpg", "jpeg", "png"],
    key="selfie_uploader",
)

verify_clicked = st.button("🔍  Verify Document", type="primary")
st.markdown('</div>', unsafe_allow_html=True)

if uploaded_file and verify_clicked:
    with st.spinner("🔬 Analyzing document with AI..."):
        result = verify_document(uploaded_file, expected_type)

    if "error" in result:
        st.error(result["error"])
        if "raw_response" in result:
            with st.expander("Raw AI response (for debugging)"):
                st.code(result["raw_response"])
    else:
        image = result.pop("_image", None)

        col1, col2 = st.columns([1, 1.3])

        with col1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            if image:
                st.image(image, caption="Uploaded document", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="card">', unsafe_allow_html=True)

            if result["flag_for_review"]:
                st.markdown(
                    '<div class="banner banner-flag">🚩 FLAGGED FOR MANUAL REVIEW</div>',
                    unsafe_allow_html=True)
            elif result["matches_expected"]:
                st.markdown(
                    '<div class="banner banner-verified">✅ VERIFIED — MATCHES EXPECTED TYPE</div>',
                    unsafe_allow_html=True)
            else:
                st.markdown(
                    '<div class="banner banner-mismatch">⚠️ MISMATCH DETECTED</div>',
                    unsafe_allow_html=True)

            confidence = result["confidence"].lower()
            pill_class = {"high": "pill-high", "medium": "pill-medium", "low": "pill-low"}.get(confidence, "pill-medium")

            st.markdown(f"""
                <div class="info-row"><span class="info-label">Detected type</span>
                    <span class="info-value">{result['document_type']}</span></div>
                <div class="info-row"><span class="info-label">Expected type</span>
                    <span class="info-value">{expected_type}</span></div>
                <div class="info-row"><span class="info-label">Confidence</span>
                    <span class="pill {pill_class}">{result['confidence'].upper()}</span></div>
            """, unsafe_allow_html=True)

            if result["quality_issues"]:
                st.markdown("<br><b>Quality issues detected:</b><br>", unsafe_allow_html=True)
                chips = "".join(f'<span class="issue-chip">⚠ {issue}</span>' for issue in result["quality_issues"])
                st.markdown(chips, unsafe_allow_html=True)

            if result["tampering_signs"]:
                st.markdown("<br><b>Possible tampering signs:</b><br>", unsafe_allow_html=True)
                chips = "".join(f'<span class="tamper-chip">🔍 {sign}</span>' for sign in result["tampering_signs"])
                st.markdown(chips, unsafe_allow_html=True)

            st.markdown(
                f'<div class="reasoning-box">🧠 <b>AI reasoning:</b><br>{result["reasoning"]}</div>',
                unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)

        # ── Face match (only runs if a selfie was uploaded) ────────────────
        if selfie_file:
            with st.spinner("🤳 Comparing selfie to document photo..."):
                face_result = verify_face_match(selfie_file, image)

            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### 🤳 Face Match")

            if "error" in face_result:
                st.error(face_result["error"])
            else:
                selfie_image = face_result.pop("_selfie_image", None)
                fcol1, fcol2 = st.columns([1, 1.3])
                with fcol1:
                    if selfie_image:
                        st.image(selfie_image, caption="Uploaded selfie", use_container_width=True)
                with fcol2:
                    if face_result["faces_match"]:
                        st.markdown(
                            '<div class="banner banner-verified">✅ FACES APPEAR TO MATCH</div>',
                            unsafe_allow_html=True)
                    else:
                        st.markdown(
                            '<div class="banner banner-flag">🚩 FACES DO NOT APPEAR TO MATCH</div>',
                            unsafe_allow_html=True)

                    fconfidence = face_result["confidence"].lower()
                    fpill_class = {"high": "pill-high", "medium": "pill-medium", "low": "pill-low"}.get(fconfidence, "pill-medium")
                    st.markdown(f"""
                        <div class="info-row"><span class="info-label">Confidence</span>
                            <span class="pill {fpill_class}">{face_result['confidence'].upper()}</span></div>
                    """, unsafe_allow_html=True)

                    st.markdown(
                        f'<div class="reasoning-box">🧠 <b>AI reasoning:</b><br>{face_result["reasoning"]}</div>',
                        unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with st.expander("🔧 Full raw result (JSON)"):
            st.json(result)

elif verify_clicked and not uploaded_file:
    st.warning("Please upload a document first.")

st.markdown("---")
st.caption(
    "⚠️ This is a prototype for learning purposes. Tampering and face-match checks here are "
    "AI visual plausibility checks, not forensic-grade or biometric-grade authentication. Real "
    "KYC systems need additional checks (liveness detection, database verification, certified "
    "document forensics, audit logging, and compliance with local data protection law) before "
    "production use."
)
