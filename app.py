"""
KYC Document Verifier — Streamlit App
========================================
Run:
    streamlit run app.py

Requires a free Google Gemini API key. Get one at:
    https://aistudio.google.com/app/apikey
"""

import os
import re
import datetime
import streamlit as st
from dotenv import load_dotenv
import verifier_gemini
import verifier_offline
import db

SUPPORTED_DOC_TYPES = verifier_offline.SUPPORTED_DOC_TYPES

load_dotenv()
db.init_db()

st.set_page_config(
    page_title="KYC Document Verifier",
    page_icon="🪪",
    layout="wide",
    initial_sidebar_state="expanded",
)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def render_html(text: str):
    """Render raw HTML safely via st.markdown.

    Streamlit's markdown parser treats a blank line (which happens
    whenever an optional f-string field like phone/business_name is
    empty) as the end of an HTML block, and any indented line after
    that gets misread as a Markdown code block instead of real HTML.
    Stripping indentation and blank lines here prevents that.
    """
    lines = [ln.strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln]
    st.markdown("\n".join(lines), unsafe_allow_html=True)

# ── Session defaults ─────────────────────────────────────────────────────
defaults = {
    "theme": "dark",
    "entered": False,
    "verifier_mode": "gemini",   # "gemini" | "offline"
    "auth_tab": "signin",        # "signin" | "register"
    "merchant_name": "",
    "business_name": "",
    "merchant_email": "",
    "merchant_phone": "",
    "merchant_age": None,
    "merchant_address": "",
    "verification_log": [],
    "doc_type": None,
    "doc_result": None,
    "doc_image": None,
    "face_result": None,
    "selfie_image": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

DARK = {
    "bg1": "#0a0f24", "bg2": "#060a18", "bg3": "#03050d",
    "text": "#E8EBF7", "muted": "#8B93B8",
    "card_bg": "rgba(76,141,255,0.05)", "card_border": "rgba(76,141,255,0.22)",
    "sidebar1": "#0a0f24", "sidebar2": "#03050d", "sidebar_border": "rgba(76,141,255,0.15)",
    "input_bg": "rgba(76,141,255,0.07)", "chip_bg": "rgba(76,141,255,0.06)",
}
LIGHT = {
    "bg1": "#F3F6FF", "bg2": "#FAFBFF", "bg3": "#EEF2FF",
    "text": "#101426", "muted": "#5B6485",
    "card_bg": "rgba(255,255,255,0.9)", "card_border": "rgba(59,130,246,0.22)",
    "sidebar1": "#EEF2FF", "sidebar2": "#F3F6FF", "sidebar_border": "rgba(59,130,246,0.2)",
    "input_bg": "rgba(59,130,246,0.06)", "chip_bg": "rgba(59,130,246,0.05)",
}
T = DARK if st.session_state.theme == "dark" else LIGHT

DOC_ICONS = {"Aadhaar Card": "🪪", "PAN Card": "💳", "Passport": "📘"}
DOC_DESCRIPTIONS = {
    "Aadhaar Card": "Verify a 12-digit Indian identity card with photo and address.",
    "PAN Card": "Verify a 10-character Permanent Account Number tax card.",
    "Passport": "Verify an international travel document with photo page.",
}
DOC_COLORS = {
    "Aadhaar Card": ("#4C8DFF", "#8B5CF6"),
    "PAN Card": ("#22D3EE", "#3B82F6"),
    "Passport": ("#A78BFA", "#4C8DFF"),
}

# ── Global styling ───────────────────────────────────────────────────────
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800;900&family=Inter:wght@400;500;600;700;800;900&display=swap');
    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; font-size: 16px; }}
    .stApp {{
        background: radial-gradient(circle at top left, {T['bg1']} 0%, {T['bg2']} 45%, {T['bg3']} 100%);
        color: {T['text']};
    }}
    h1, h2, h3, h4, p, span, label, div {{ color: {T['text']}; }}

    .hero {{
        position: relative; overflow: hidden;
        background:
            radial-gradient(circle at 15% 30%, rgba(76,141,255,0.35) 0%, transparent 45%),
            radial-gradient(circle at 85% 70%, rgba(139,92,246,0.30) 0%, transparent 50%),
            linear-gradient(135deg, #060a18 0%, #0a0f24 100%);
        border: 1px solid rgba(76,141,255,0.25);
        border-radius: 26px; padding: 56px 48px; margin-bottom: 28px;
        box-shadow: 0 30px 70px -25px rgba(76,141,255,0.35);
    }}
    .hero h1 {{ margin: 0; font-weight: 900; font-size: 2.9rem; color: white !important; letter-spacing: -0.02em; line-height: 1.1; }}
    .hero .hero-accent {{ background: linear-gradient(90deg, #4C8DFF, #A78BFA); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
    .hero p {{ margin: 16px 0 0 0; color: #B8C0E0 !important; font-size: 1.15rem; max-width: 640px; line-height: 1.5; }}

    .step-badge {{
        display: inline-flex; align-items: center; gap: 8px;
        background: {T['input_bg']}; border: 1px solid {T['card_border']};
        border-radius: 999px; padding: 7px 18px; font-size: 0.9rem; font-weight: 800;
        letter-spacing: 0.04em; color: #4C8DFF !important; margin-bottom: 16px;
    }}

    .card {{
        background: {T['card_bg']}; border: 1px solid {T['card_border']};
        border-radius: 18px; padding: 28px 32px; margin-bottom: 22px; backdrop-filter: blur(8px);
    }}
    .card-title {{
        font-size: 1.35rem; font-weight: 800; margin-bottom: 6px;
        background: linear-gradient(90deg, #4C8DFF, #8B5CF6);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }}
    .card-subtitle {{ color: {T['muted']} !important; font-size: 0.98rem; margin-bottom: 18px; }}

    .merchant-chip-row {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 6px; }}
    .merchant-chip {{
        color: {T['text']} !important; padding: 7px 16px; border-radius: 10px; font-size: 0.95rem; font-weight: 500;
    }}
    .merchant-chip b {{ color: #4C8DFF !important; }}
    .chip-gold {{ background: rgba(76,141,255,0.14); border: 1px solid rgba(76,141,255,0.4); }}
    .chip-teal {{ background: rgba(23,195,178,0.14); border: 1px solid rgba(23,195,178,0.45); }}
    .chip-coral {{ background: rgba(255,107,107,0.14); border: 1px solid rgba(255,107,107,0.45); }}
    .chip-emerald {{ background: rgba(46,204,113,0.14); border: 1px solid rgba(46,204,113,0.45); }}
    .chip-violet {{ background: rgba(155,89,182,0.14); border: 1px solid rgba(155,89,182,0.45); }}

    /* Document type cards */
    .doctype-card {{
        border-radius: 18px; padding: 30px 26px; text-align: left;
        border: 1px solid {T['card_border']}; background: {T['chip_bg']};
        transition: all 0.15s ease; height: 100%; min-height: 190px;
        display: flex; flex-direction: column;
    }}
    .doctype-card .icon {{ font-size: 2.1rem; margin-bottom: 14px; }}
    .doctype-card .label {{ font-weight: 800; font-size: 1.2rem; margin-bottom: 8px; }}
    .doctype-card .desc {{ color: {T['muted']} !important; font-size: 0.92rem; line-height: 1.5; flex-grow: 1; }}
    .doctype-card.selected {{
        border: 1px solid transparent;
        background: linear-gradient({T['card_bg']}, {T['card_bg']}) padding-box,
                    linear-gradient(135deg, var(--c1), var(--c2)) border-box;
        box-shadow: 0 16px 36px -16px rgba(76,141,255,0.5);
    }}

    .banner {{
        border-radius: 14px; padding: 16px 22px; font-weight: 800; font-size: 1.05rem;
        margin-bottom: 16px; display: flex; align-items: center; gap: 10px;
    }}
    .banner-flag {{ background: linear-gradient(90deg, rgba(239,68,68,0.20), rgba(239,68,68,0.05)); border: 1px solid rgba(239,68,68,0.5); color: #FCA5A5 !important; }}
    .banner-mismatch {{ background: linear-gradient(90deg, rgba(245,158,11,0.20), rgba(245,158,11,0.05)); border: 1px solid rgba(245,158,11,0.5); color: #D97706 !important; }}
    .banner-verified {{ background: linear-gradient(90deg, rgba(34,197,94,0.20), rgba(34,197,94,0.05)); border: 1px solid rgba(34,197,94,0.5); color: #15803D !important; }}

    .verdict-box {{
        border-radius: 22px; padding: 40px; text-align: center; margin-bottom: 20px;
    }}
    .verdict-pass {{
        background: linear-gradient(135deg, rgba(34,197,94,0.18), rgba(16,185,129,0.08));
        border: 2px solid rgba(34,197,94,0.5);
    }}
    .verdict-fail {{
        background: linear-gradient(135deg, rgba(239,68,68,0.18), rgba(245,158,11,0.08));
        border: 2px solid rgba(239,68,68,0.5);
    }}
    .verdict-icon {{ font-size: 3.2rem; margin-bottom: 10px; }}
    .verdict-title {{ font-size: 1.6rem; font-weight: 900; margin-bottom: 8px; }}
    .verdict-sub {{ color: {T['muted']} !important; font-size: 0.95rem; max-width: 500px; margin: 0 auto; }}

    .info-row {{ display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid {T['card_border']}; font-size: 1.02rem; }}
    .info-row:last-child {{ border-bottom: none; }}
    .info-label {{ color: {T['muted']} !important; }}
    .info-value {{ color: {T['text']} !important; font-weight: 700; }}

    .pill {{ display: inline-block; padding: 3px 13px; border-radius: 999px; font-size: 0.8rem; font-weight: 800; }}
    .pill-high {{ background: rgba(34,197,94,0.18); color: #16A34A !important; }}
    .pill-medium {{ background: rgba(245,158,11,0.18); color: #D97706 !important; }}
    .pill-low {{ background: rgba(239,68,68,0.18); color: #DC2626 !important; }}

    .issue-chip {{ display: inline-block; background: rgba(239,68,68,0.12); border: 1px solid rgba(239,68,68,0.3); color: #DC2626 !important; padding: 4px 12px; border-radius: 999px; font-size: 0.82rem; margin: 3px 6px 3px 0; }}
    .tamper-chip {{ display: inline-block; background: rgba(245,158,11,0.12); border: 1px solid rgba(245,158,11,0.35); color: #D97706 !important; padding: 4px 12px; border-radius: 999px; font-size: 0.82rem; margin: 3px 6px 3px 0; }}

    .reasoning-box {{ background: rgba(76,141,255,0.10); border-left: 3px solid #4C8DFF; border-radius: 8px; padding: 16px 20px; color: {T['text']} !important; font-size: 1rem; margin-top: 10px; }}

    section[data-testid="stSidebar"] {{ background: linear-gradient(180deg, {T['sidebar1']} 0%, {T['sidebar2']} 100%); border-right: 1px solid {T['sidebar_border']}; }}

    .stButton>button {{ background: linear-gradient(135deg, #4C8DFF, #3B82F6); color: #FFFFFF !important; border: none; border-radius: 10px; padding: 11px 26px; font-weight: 800; font-size: 1.05rem; box-shadow: 0 10px 25px -10px rgba(76, 141, 255, 0.6); transition: all 0.15s ease; }}
    .stButton>button:hover {{ filter: brightness(1.12); transform: translateY(-1px); }}
    .stButton>button p {{ color: #FFFFFF !important; font-weight: 800; }}
    .stButton>button[kind="secondary"] {{ background: transparent !important; color: #8B93B8 !important; box-shadow: none; border: 1px solid rgba(76,141,255,0.2); }}
    .stButton>button[kind="secondary"] p {{ color: #8B93B8 !important; }}
    .stButton>button[kind="secondary"]:hover {{ background: rgba(76,141,255,0.08) !important; }}
    .stButton>button[kind="secondary"]:hover p {{ color: #4C8DFF !important; }}
    .stButton>button[kind="primary"] {{ background: linear-gradient(135deg, #4C8DFF, #8B5CF6) !important; box-shadow: 0 10px 25px -10px rgba(76,141,255,0.7) !important; }}

    .stTextInput input,
    .stTextArea textarea,
    .stNumberInput input {{
        background-color: {T['input_bg']} !important;
        color: {T['text']} !important;
        border: 1px solid {T['card_border']} !important;
        border-radius: 10px !important;
        caret-color: {T['text']} !important;
    }}
    .stTextInput input::placeholder,
    .stTextArea textarea::placeholder {{
        color: {T['muted']} !important;
        opacity: 0.7;
    }}

    .landing-wrap {{ display: flex; justify-content: center; padding-top: 30px; }}
    .landing-card {{ max-width: 460px; width: 100%; background: {T['card_bg']}; border: 1px solid {T['card_border']}; border-radius: 26px; padding: 48px 40px; text-align: center; box-shadow: 0 30px 80px -30px rgba(139,92,246,0.4); backdrop-filter: blur(10px); }}
    .landing-icon {{ width: 84px; height: 84px; border-radius: 22px; margin: 0 auto 22px auto; background: linear-gradient(135deg, #6366F1, #DB2777); display: flex; align-items: center; justify-content: center; font-size: 2.4rem; box-shadow: 0 15px 35px -10px rgba(219,39,119,0.6); }}
    .landing-title {{ font-size: 1.7rem; font-weight: 900; margin-bottom: 8px; letter-spacing: -0.01em; }}
    .landing-sub {{ color: {T['muted']} !important; font-size: 0.98rem; margin-bottom: 30px; line-height: 1.5; }}
    .landing-feature {{ display: flex; align-items: center; gap: 12px; text-align: left; background: {T['input_bg']}; border-radius: 12px; padding: 12px 16px; margin-bottom: 10px; font-size: 0.9rem; font-weight: 600; }}

    /* Native bordered container (st.container(border=True)) — used for the
       Sign In / Register card. Targeting Streamlit's real container avoids
       the rendering bugs that a hand-rolled unclosed <div> wrapper causes. */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(div[data-testid="stForm"]) {{
        background: linear-gradient(160deg, rgba(20,15,0,0.97), rgba(10,8,0,0.99));
        border: 1px solid rgba(76,141,255,0.35) !important;
        border-radius: 24px !important;
        box-shadow: 0 0 0 1px rgba(76,141,255,0.15), 0 25px 70px -20px rgba(76,141,255,0.4), 0 0 60px -15px rgba(139,92,246,0.35);
        padding: 8px;
    }}
    .auth-title {{
        font-family: 'Poppins', sans-serif; font-weight: 800; font-size: 2rem;
        text-align: center; color: #FFFFFF !important;
        text-shadow: 0 0 18px rgba(76,141,255,0.6), 0 0 40px rgba(139,92,246,0.4);
        margin-bottom: 6px; letter-spacing: -0.01em;
    }}
    .auth-sub {{ text-align: center; color: #B8C0E0 !important; font-size: 0.92rem; margin-bottom: 26px; }}
    .auth-switch {{ text-align: center; color: #8B93B8 !important; font-size: 0.88rem; margin-top: 16px; }}
    .login-error {{ color: #FF6B6B !important; font-size: 0.85rem; margin: 2px 0 6px 0; text-align: left; }}

    footer, #MainMenu {{ visibility: hidden; }}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎨 Appearance")
    theme_choice = st.radio("Theme", ["🌙 Dark", "☀️ Light"], horizontal=True,
                             index=0 if st.session_state.theme == "dark" else 1,
                             label_visibility="collapsed")
    new_theme = "dark" if "Dark" in theme_choice else "light"
    if new_theme != st.session_state.theme:
        st.session_state.theme = new_theme
        st.rerun()

    st.markdown("---")
    st.markdown("### 🧠 Verification Engine")
    mode_choice = st.radio(
        "Engine",
        ["🌐 Cloud AI (Gemini)", "🔒 Offline (Local)"],
        index=0 if st.session_state.verifier_mode == "gemini" else 1,
        label_visibility="collapsed",
    )
    new_mode = "gemini" if "Cloud" in mode_choice else "offline"
    if new_mode != st.session_state.verifier_mode:
        st.session_state.verifier_mode = new_mode
        st.session_state.doc_result = None
        st.session_state.doc_image = None
        st.session_state.face_result = None
        st.session_state.selfie_image = None
        st.rerun()

    st.markdown("---")
    st.markdown("### ⚙️ Setup")
    if st.session_state.verifier_mode == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            api_key_input = st.text_input("Google Gemini API Key", type="password",
                                           help="Get a free key at https://aistudio.google.com/app/apikey")
            if api_key_input:
                api_key = api_key_input
        else:
            st.success("API key loaded from .env ✅")
        st.caption("This mode sends the document image to Google's Gemini API for analysis.")
    else:
        api_key = None
        st.success("Running 100% locally — no API key needed ✅")
        st.caption("Documents are processed on this machine only, using OCR + rule-based checks. Nothing leaves this computer.")

    st.markdown("---")
    st.markdown("### 🧭 How it works")
    st.markdown(
        "**1.** Login with your merchant details\n\n"
        "**2.** Select the document type\n\n"
        "**3.** Upload & verify the document\n\n"
        "**4.** Optionally verify a selfie face-match\n\n"
        "**5.** Get the final verdict 🎯"
    )
    if st.session_state.verification_log:
        st.markdown("---")
        st.markdown("### 📊 This session")
        total = len(st.session_state.verification_log)
        flagged = sum(1 for r in st.session_state.verification_log if r["flagged"])
        st.caption(f"{total} verification(s) run · {flagged} flagged")

    if st.session_state.entered:
        st.markdown("---")
        st.markdown(f"### 👤 Logged in as\n**{st.session_state.merchant_name}**")
        if st.button("🚪 Logout", use_container_width=True):
            for k, v in defaults.items():
                st.session_state[k] = v
            st.rerun()

    st.markdown("---")
    st.markdown("### 🗄️ Saved History")
    recent = db.get_recent_records(10)
    if recent:
        st.caption(f"{len(recent)} record(s) on file (permanent)")
        for r in recent:
            badge = "✅" if r["verdict"] == "Pass" else "🚩"
            st.caption(f"{badge} {r['merchant_name']} · {r['doc_type']} · {r['created_at'][:10]}")
    else:
        st.caption("No records yet.")

    st.markdown("---")
    st.caption("Built with Streamlit + Google Gemini Vision")

# ── Merchant login screen ────────────────────────────────────────────────
if not st.session_state.entered:

    _, mid_col, _ = st.columns([1, 1.3, 1])
    with mid_col:
      with st.container(border=True):

        tcol1, tcol2 = st.columns(2)
        with tcol1:
            if st.button("Sign In", key="tab_signin", use_container_width=True,
                         type="primary" if st.session_state.auth_tab == "signin" else "secondary"):
                st.session_state.auth_tab = "signin"
                st.rerun()
        with tcol2:
            if st.button("Register", key="tab_register", use_container_width=True,
                         type="primary" if st.session_state.auth_tab == "register" else "secondary"):
                st.session_state.auth_tab = "register"
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Sign In ──────────────────────────────────────────────────────────
        if st.session_state.auth_tab == "signin":
            st.markdown('<div class="auth-title">Welcome Back</div>', unsafe_allow_html=True)
            st.markdown('<div class="auth-sub">Sign in to continue to KYC document verification.</div>', unsafe_allow_html=True)

            with st.form("signin_form", clear_on_submit=False):
                email_in = st.text_input("Email")
                password_in = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign In →", type="primary", use_container_width=True)

            if submitted:
                if not email_in.strip() or not password_in:
                    st.markdown('<div class="login-error">⚠ Please enter both email and password.</div>', unsafe_allow_html=True)
                else:
                    merchant = db.authenticate_merchant(email_in.strip(), password_in)
                    if not merchant:
                        st.markdown('<div class="login-error">⚠ Incorrect email or password, or no account found. Try Register instead.</div>', unsafe_allow_html=True)
                    else:
                        st.session_state.merchant_name = merchant["name"]
                        st.session_state.merchant_email = merchant["email"]
                        st.session_state.merchant_age = merchant["age"]
                        st.session_state.merchant_address = merchant["address"]
                        st.session_state.business_name = merchant["business_name"] or ""
                        st.session_state.merchant_phone = merchant["phone"] or ""
                        st.session_state.entered = True
                        st.rerun()

            st.markdown('<div class="auth-switch">New here? Click <b>Register</b> above to create your account.</div>', unsafe_allow_html=True)

        # ── Register ─────────────────────────────────────────────────────────
        else:
            st.markdown('<div class="auth-title">Create Account</div>', unsafe_allow_html=True)
            st.markdown('<div class="auth-sub">Register once — after this you\'ll only need to Sign In.</div>', unsafe_allow_html=True)

            with st.form("register_form", clear_on_submit=False):
                name_in = st.text_input("Full Name")
                email_in = st.text_input("Email")
                password_in = st.text_input("Password", type="password")
                confirm_in = st.text_input("Confirm Password", type="password")
                age_in = st.text_input("Age")
                address_in = st.text_area("Address", height=80)
                business_in = st.text_input("Business name (optional)")
                phone_in = st.text_input("Phone number (optional)")
                submitted = st.form_submit_button("Register →", type="primary", use_container_width=True)

            if submitted:
                errors = []
                if not name_in.strip():
                    errors.append("Please enter your full name.")
                if not email_in.strip() or not EMAIL_REGEX.match(email_in.strip()):
                    errors.append("Please enter a valid email address (e.g. name@example.com).")
                if len(password_in) < 6:
                    errors.append("Password should be at least 6 characters.")
                if password_in != confirm_in:
                    errors.append("Passwords do not match.")
                if not age_in.strip().isdigit() or not (18 <= int(age_in.strip()) <= 120):
                    errors.append("Please enter a valid age (18–120).")
                if not address_in.strip():
                    errors.append("Please enter your address.")
                if phone_in.strip() and (not phone_in.strip().isdigit() or len(phone_in.strip()) != 10):
                    errors.append("Phone number should be exactly 10 digits, or left blank.")

                if errors:
                    for e in errors:
                        st.markdown(f'<div class="login-error">⚠ {e}</div>', unsafe_allow_html=True)
                else:
                    ok, err = db.register_merchant(
                        name=name_in.strip(),
                        email=email_in.strip(),
                        password=password_in,
                        age=int(age_in.strip()),
                        address=address_in.strip(),
                        business_name=business_in.strip(),
                        phone=phone_in.strip(),
                    )
                    if not ok:
                        st.markdown(f'<div class="login-error">⚠ {err}</div>', unsafe_allow_html=True)
                    else:
                        st.session_state.merchant_name = name_in.strip()
                        st.session_state.merchant_email = email_in.strip()
                        st.session_state.merchant_age = int(age_in.strip())
                        st.session_state.merchant_address = address_in.strip()
                        st.session_state.business_name = business_in.strip()
                        st.session_state.merchant_phone = phone_in.strip()
                        st.session_state.entered = True
                        st.rerun()

            st.markdown('<div class="auth-switch">Already have an account? Click <b>Sign In</b> above.</div>', unsafe_allow_html=True)

        st.stop()

# ── Pull merchant details from session (set during login) ─────────────────
merchant_name = st.session_state.merchant_name
business_name = st.session_state.business_name
merchant_email = st.session_state.merchant_email
merchant_phone = st.session_state.merchant_phone
merchant_age = st.session_state.merchant_age
merchant_address = st.session_state.merchant_address

# ── Main app ──────────────────────────────────────────────────────────────
active_verifier = verifier_gemini if st.session_state.verifier_mode == "gemini" else verifier_offline
mode_label = "Cloud AI (Gemini)" if st.session_state.verifier_mode == "gemini" else "Offline / Local"

render_html(f"""
<div class="hero">
    <h1>Verify identity documents<br>with <span class="hero-accent">KYC Verifier</span></h1>
    <p>{mode_label} document check for banks, fintechs and merchant onboarding. Detects type mismatches, quality issues, and face mismatches in seconds.</p>
</div>
""")

if st.session_state.verifier_mode == "gemini":
    if not api_key:
        st.warning("👈 Please enter your Gemini API key in the sidebar to continue, or switch to Offline mode.")
        st.stop()
    active_verifier.configure_api(api_key)
else:
    active_verifier.configure_api()

# ── Merchant summary chip row ──────────────────────────────────────────────
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">🏪 Merchant</div>', unsafe_allow_html=True)
render_html(f"""
<div class="merchant-chip-row">
    <span class="merchant-chip chip-gold">👤 <b>{merchant_name}</b></span>
    {f'<span class="merchant-chip chip-violet">🏢 {business_name}</span>' if business_name else ''}
    <span class="merchant-chip chip-teal">✉️ {merchant_email}</span>
    {f'<span class="merchant-chip chip-coral">📞 {merchant_phone}</span>' if merchant_phone else ''}
    <span class="merchant-chip chip-emerald">🎂 Age {merchant_age}</span>
    <span class="merchant-chip chip-gold">🏠 {merchant_address}</span>
</div>
""")
st.markdown('</div>', unsafe_allow_html=True)

# ── Step 1: Please select your document type (colorful cards) ─────────────
st.markdown('<div class="step-badge">STEP 1 · DOCUMENT TYPE</div>', unsafe_allow_html=True)
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">📋 Please select your document type</div>', unsafe_allow_html=True)
st.markdown('<div class="card-subtitle">Which document are you about to upload?</div>', unsafe_allow_html=True)

dcols = st.columns(len(SUPPORTED_DOC_TYPES))
for i, doc in enumerate(SUPPORTED_DOC_TYPES):
    c1, c2 = DOC_COLORS[doc]
    selected = st.session_state.doc_type == doc
    with dcols[i]:
        render_html(f"""
        <div class="doctype-card {'selected' if selected else ''}" style="--c1:{c1};--c2:{c2};">
            <div class="icon">{DOC_ICONS[doc]}</div>
            <div class="label">{doc}</div>
            <div class="desc">{DOC_DESCRIPTIONS[doc]}</div>
        </div>
        """)
        btn_label = "✓ Selected" if selected else "Select"
        if st.button(btn_label, key=f"select_{doc}", use_container_width=True):
            st.session_state.doc_type = doc
            st.session_state.doc_result = None
            st.session_state.face_result = None
            st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

if not st.session_state.doc_type:
    st.info("👆 Select a document type above to continue.")
    st.stop()

expected_type = st.session_state.doc_type

# ── Step 2: Upload + Start Verification ─────────────────────────────────────
st.markdown('<div class="step-badge">STEP 2 · UPLOAD & VERIFY</div>', unsafe_allow_html=True)
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown(f'<div class="card-title">{DOC_ICONS[expected_type]} Upload your {expected_type}</div>', unsafe_allow_html=True)
st.markdown('<div class="card-subtitle">Upload a clear photo or PDF of the document.</div>', unsafe_allow_html=True)

uploaded_file = st.file_uploader("📤 Document file", type=["jpg", "jpeg", "png", "pdf"], label_visibility="collapsed")
start_verify = st.button("🚀 Start Verification", type="primary", disabled=not uploaded_file)
st.markdown('</div>', unsafe_allow_html=True)

if start_verify and uploaded_file:
    with st.spinner("🔬 Analyzing document with AI..."):
        result = active_verifier.verify_document(uploaded_file, expected_type)
    if "error" in result:
        st.error(result["error"])
        if "raw_response" in result:
            with st.expander("Raw AI response (for debugging)"):
                st.code(result["raw_response"])
    else:
        st.session_state.doc_image = result.pop("_image", None)
        st.session_state.doc_result = result
        st.session_state.face_result = None
        st.session_state.verification_log.append({
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
            "merchant": merchant_name,
            "expected": expected_type,
            "detected": result["document_type"],
            "flagged": bool(result["flag_for_review"]),
        })
        doc_verdict = "Review" if (result["flag_for_review"] or not result["matches_expected"]) else "Pass"
        db.insert_record(
            merchant_name=merchant_name,
            business_name=business_name,
            email=merchant_email,
            phone=merchant_phone,
            age=merchant_age,
            address=merchant_address,
            doc_type=expected_type,
            detected_type=result["document_type"],
            confidence=result["confidence"],
            matches_expected=result["matches_expected"],
            flagged=result["flag_for_review"],
            verdict=doc_verdict,
        )
        st.rerun()

if not st.session_state.doc_result:
    st.stop()

result = st.session_state.doc_result
image = st.session_state.doc_image

# ── Document result card ────────────────────────────────────────────────────
st.markdown('<div class="step-badge">DOCUMENT RESULT</div>', unsafe_allow_html=True)
col1, col2 = st.columns([1, 1.3])
with col1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    if image:
        st.image(image, caption="Uploaded document", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
with col2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    if result["flag_for_review"]:
        st.markdown('<div class="banner banner-flag">🚩 FLAGGED FOR MANUAL REVIEW</div>', unsafe_allow_html=True)
    elif result["matches_expected"]:
        st.markdown('<div class="banner banner-verified">✅ VERIFIED — MATCHES EXPECTED TYPE</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="banner banner-mismatch">⚠️ MISMATCH DETECTED</div>', unsafe_allow_html=True)

    confidence = result["confidence"].lower()
    pill_class = {"high": "pill-high", "medium": "pill-medium", "low": "pill-low"}.get(confidence, "pill-medium")
    render_html(f"""
        <div class="info-row"><span class="info-label">Merchant</span><span class="info-value">{merchant_name}</span></div>
        <div class="info-row"><span class="info-label">Detected type</span><span class="info-value">{result['document_type']}</span></div>
        <div class="info-row"><span class="info-label">Expected type</span><span class="info-value">{expected_type}</span></div>
        <div class="info-row"><span class="info-label">Confidence</span><span class="pill {pill_class}">{result['confidence'].upper()}</span></div>
    """)

    if result["quality_issues"]:
        st.markdown("<br><b>Quality issues detected:</b><br>", unsafe_allow_html=True)
        st.markdown("".join(f'<span class="issue-chip">⚠ {i}</span>' for i in result["quality_issues"]), unsafe_allow_html=True)
    if result["tampering_signs"]:
        st.markdown("<br><b>Possible tampering signs:</b><br>", unsafe_allow_html=True)
        st.markdown("".join(f'<span class="tamper-chip">🔍 {s}</span>' for s in result["tampering_signs"]), unsafe_allow_html=True)

    st.markdown(f'<div class="reasoning-box">🧠 <b>AI reasoning:</b><br>{result["reasoning"]}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ── Step 3: Optional Face Match ─────────────────────────────────────────────
st.markdown('<div class="step-badge">STEP 3 · FACE MATCH (OPTIONAL)</div>', unsafe_allow_html=True)
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">🤳 Verify it\'s the same person</div>', unsafe_allow_html=True)
st.markdown('<div class="card-subtitle">Upload a live selfie to compare against the document photo.</div>', unsafe_allow_html=True)

selfie_file = st.file_uploader("Selfie", type=["jpg", "jpeg", "png"], key="selfie_uploader", label_visibility="collapsed")
run_face_match = st.button("🤳 Verify Face Match", disabled=not selfie_file)
st.markdown('</div>', unsafe_allow_html=True)

if run_face_match and selfie_file:
    with st.spinner("🤳 Comparing selfie to document photo..."):
        face_result = active_verifier.verify_face_match(selfie_file, image)
    if "error" in face_result:
        st.error(face_result["error"])
    else:
        st.session_state.selfie_image = face_result.pop("_selfie_image", None)
        st.session_state.face_result = face_result
        st.rerun()

if st.session_state.face_result:
    face_result = st.session_state.face_result
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">🤳 Face Match Result</div>', unsafe_allow_html=True)
    fcol1, fcol2 = st.columns([1, 1.3])
    with fcol1:
        if st.session_state.selfie_image:
            st.image(st.session_state.selfie_image, caption="Uploaded selfie", use_container_width=True)
    with fcol2:
        if face_result["faces_match"]:
            st.markdown('<div class="banner banner-verified">✅ FACES APPEAR TO MATCH</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="banner banner-flag">🚩 FACES DO NOT APPEAR TO MATCH</div>', unsafe_allow_html=True)
        fconfidence = face_result["confidence"].lower()
        fpill_class = {"high": "pill-high", "medium": "pill-medium", "low": "pill-low"}.get(fconfidence, "pill-medium")
        st.markdown(f'<div class="info-row"><span class="info-label">Confidence</span><span class="pill {fpill_class}">{face_result["confidence"].upper()}</span></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="reasoning-box">🧠 <b>AI reasoning:</b><br>{face_result["reasoning"]}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ── Step 4: Final Verdict ────────────────────────────────────────────────────
st.markdown('<div class="step-badge">STEP 4 · FINAL VERDICT</div>', unsafe_allow_html=True)

doc_ok = result["matches_expected"] and not result["flag_for_review"]
face_ok = (st.session_state.face_result["faces_match"]) if st.session_state.face_result else True
overall_pass = doc_ok and face_ok

if overall_pass:
    render_html(f"""
    <div class="verdict-box verdict-pass">
        <div class="verdict-icon">✅</div>
        <div class="verdict-title">Yes — this looks like a genuine, matching {expected_type}</div>
        <div class="verdict-sub">The document type matches what was expected, no serious quality or tampering issues were found{'  , and the selfie face matches the document photo' if st.session_state.face_result else ''}. This is an AI-based plausibility check, not a certified legal verification.</div>
    </div>
    """)
else:
    reasons = []
    if not result["matches_expected"]:
        reasons.append(f"detected type ({result['document_type']}) doesn't match expected ({expected_type})")
    if result["flag_for_review"]:
        reasons.append("quality/tampering concerns were found")
    if st.session_state.face_result and not st.session_state.face_result["faces_match"]:
        reasons.append("the selfie does not appear to match the document photo")
    reason_text = "; ".join(reasons) if reasons else "the AI flagged this for review"
    render_html(f"""
    <div class="verdict-box verdict-fail">
        <div class="verdict-icon">🚩</div>
        <div class="verdict-title">Not verified — needs manual review</div>
        <div class="verdict-sub">Reason: {reason_text}. Please have a human reviewer double-check this before proceeding.</div>
    </div>
    """)

if st.button("🔄 Start a new verification"):
    st.session_state.doc_type = None
    st.session_state.doc_result = None
    st.session_state.doc_image = None
    st.session_state.face_result = None
    st.session_state.selfie_image = None
    st.rerun()

with st.expander("🔧 Full raw result (JSON)"):
    st.json({"document": result, "face_match": st.session_state.face_result})

if st.session_state.verification_log:
    st.markdown('<div class="step-badge">SESSION LOG</div>', unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📋 Verifications This Session</div>', unsafe_allow_html=True)
    st.markdown('<div class="card-subtitle">In-memory only — clears when the app restarts. Not saved to a database yet.</div>', unsafe_allow_html=True)
    st.dataframe(st.session_state.verification_log, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")
st.caption(
    "⚠️ This is a prototype for learning purposes. All processing happens locally on this machine "
    "using OCR + rule-based checks — no document image is sent to any third-party server. Quality and "
    "format checks here are pattern-based, not forensic-grade or biometric-grade authentication. Merchant "
    "details are held only in this browser session (no database yet). Real KYC systems need "
    "additional checks (liveness detection, database verification, certified document forensics, "
    "persistent audit logging, and compliance with local data protection law) before production use."
)