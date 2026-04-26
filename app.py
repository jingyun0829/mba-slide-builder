"""SlideGen — AI course decks for business school instructors."""
import json, os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
import streamlit as st

# ── Bridge st.secrets → os.environ ─────────────────────────────────────
# All pipeline modules read API keys from os.environ, so on Streamlit Cloud
# we copy the secrets into env vars at startup. Local .env still works
# (load_dotenv ran above). Streamlit Cloud secrets take precedence.
def _bridge_secrets_to_env():
    keys = ("ANTHROPIC_API_KEY", "TAVILY_API_KEY", "ELEVENLABS_API_KEY",
            "ANTHROPIC_MODEL", "INVITE_CODE", "MAX_DECKS_PER_USER", "ADMIN_PASS")
    try:
        for k in keys:
            if k in st.secrets:
                v = st.secrets[k]
                if v:
                    os.environ[k] = str(v)
    except Exception:
        pass  # no secrets.toml — local dev mode, .env is enough
_bridge_secrets_to_env()

st.set_page_config(page_title="SlideGen", layout="wide", page_icon="📚")

# ── Authentication gate ───────────────────────────────────────────────
# Show the invite-code login screen FIRST. Nothing else loads until the
# user types a valid code. This protects API keys + caps deck generation.
from pipeline import auth as _auth
if not _auth.render_login_gate():
    st.stop()

# Now safe to do heavy imports (auth passed)
from pipeline.syllabus import generate_syllabus, save_syllabus, load_syllabus
from pipeline.style_analyzer import extract_style_profile, save_style_profile, load_style_profile, compute_dimensions
from pipeline.outline import generate_outline
from pipeline.slides_html import build_html, THEMES
from pipeline.examples import fetch_recent_examples
from pipeline.dataset_generator import generate_dataset
from pipeline.slides_pptx_export import export_pptx
from pipeline.activity_generator import generate_activity_xlsx
from pipeline.pdf_export import export_html_to_pdf
from pipeline.study_guide import generate_study_guide
from pipeline.evaluator import evaluate_outline
from pipeline.outline import VERSION_ANGLES, AUDIENCE_LEVELS
from pipeline.course_memory import (
    extract_session_memory, save_session_memory, load_prior_memory,
    load_prior_memory_with_syllabus, list_all_memory, clear_memory,
)
from concurrent.futures import ThreadPoolExecutor

MODULE_AREAS = ["analytics","information_systems","statistics","strategy","finance","marketing","operations"]

# ---------- Custom CSS for a more polished look ----------
st.markdown("""
<style>
/* Import a clean serif/sans pair */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Serif+Pro:wght@600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, "Helvetica Neue", sans-serif !important;
}

/* Trim the default top padding */
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 4rem !important;
    max-width: 1200px;
}

/* Hero header */
.hero {
    background: linear-gradient(135deg, #1A1A1A 0%, #042f2e 60%, #0d9488 100%);
    color: white;
    padding: 36px 44px;
    border-radius: 18px;
    margin-bottom: 24px;
    box-shadow: 0 10px 30px rgba(13,148,136,0.15);
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: "";
    position: absolute;
    top: -50%; right: -20%;
    width: 400px; height: 400px;
    background: radial-gradient(circle, rgba(255,255,255,0.06) 0%, transparent 70%);
    pointer-events: none;
}
.hero h1 {
    font-family: 'Source Serif Pro', 'Georgia', serif;
    font-size: 40pt;
    font-weight: 700;
    margin: 0;
    line-height: 1.1;
}
.hero .hero-sub {
    font-size: 13pt;
    opacity: 0.85;
    margin-top: 10px;
    letter-spacing: 0.3px;
}
.hero .hero-flow {
    margin-top: 14px;
    font-size: 11pt;
    opacity: 0.7;
    font-family: ui-monospace, "SF Mono", Consolas, monospace;
}

/* Status pills row */
.status-row {
    display: flex;
    gap: 10px;
    margin: -8px 0 22px 0;
    flex-wrap: wrap;
}
.status-pill {
    background: #fff;
    border: 1px solid #e5e5e5;
    border-radius: 999px;
    padding: 6px 14px;
    font-size: 11pt;
    color: #888;
    transition: all 0.15s;
}
.status-pill.active {
    background: #ECFDF5;
    border-color: #0d9488;
    color: #0d9488;
    font-weight: 500;
}

/* Tabs — premium SaaS look */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #f3f3f3;
    padding: 6px;
    border-radius: 12px;
    margin-bottom: 18px;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    border-radius: 8px;
    padding: 10px 18px;
    font-weight: 500;
    color: #555;
    border: none;
    transition: all 0.15s;
}
.stTabs [data-baseweb="tab"]:hover {
    background: rgba(255,255,255,0.5);
}
.stTabs [aria-selected="true"] {
    background: white !important;
    color: #0d9488 !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    font-weight: 600;
}

/* Subheaders */
.stMarkdown h3 {
    font-family: 'Source Serif Pro', Georgia, serif;
    font-weight: 700;
    color: #1A1A1A;
}

/* Buttons */
.stButton > button {
    border-radius: 8px;
    border: 1px solid #e0e0e0;
    font-weight: 500;
    padding: 8px 18px;
    transition: all 0.15s;
}
.stButton > button:hover {
    border-color: #0d9488;
    color: #0d9488;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(13,148,136,0.10);
}
.stButton > button[kind="primary"] {
    background: #0d9488;
    border-color: #0d9488;
    color: white;
}
.stButton > button[kind="primary"]:hover {
    background: #0f766e;
    border-color: #0f766e;
    color: white;
    box-shadow: 0 6px 16px rgba(13,148,136,0.30);
}

/* Download buttons */
.stDownloadButton > button {
    border-radius: 8px;
    background: #fff;
    border: 1px solid #1A1A1A;
    color: #1A1A1A;
    font-weight: 500;
    padding: 8px 18px;
}
.stDownloadButton > button:hover {
    background: #1A1A1A;
    color: white;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

/* Inputs */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stNumberInput > div > div > input {
    border-radius: 8px;
    border: 1px solid #e0e0e0;
    font-family: 'Inter', sans-serif;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus,
.stNumberInput > div > div > input:focus {
    border-color: #0d9488 !important;
    box-shadow: 0 0 0 3px rgba(13,148,136,0.1) !important;
}

/* Selectbox */
.stSelectbox > div > div {
    border-radius: 8px;
}

/* Expanders — card-like */
[data-testid="stExpander"] {
    border: 1px solid #ececec !important;
    border-radius: 12px !important;
    background: white;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    margin-bottom: 8px;
    transition: all 0.15s;
}
[data-testid="stExpander"]:hover {
    border-color: #0d9488 !important;
    box-shadow: 0 4px 12px rgba(13,148,136,0.06);
}
[data-testid="stExpander"] summary {
    font-weight: 500;
    padding: 12px 16px;
    border-radius: 12px;
}

/* File uploader */
[data-testid="stFileUploaderDropzone"] {
    border-radius: 12px;
    border: 2px dashed #ccc;
    background: #FAFAFA;
}
[data-testid="stFileUploaderDropzone"]:hover {
    border-color: #0d9488;
    background: #F0FDFA;
}

/* Success/info/warning boxes — softer */
.stAlert {
    border-radius: 10px;
    border: 1px solid;
}

/* Metric / caption */
.stCaption {
    color: #888;
    font-size: 11pt;
}

/* Spinner color */
.stSpinner > div > div {
    border-top-color: #0d9488 !important;
}

/* Section spacing inside tabs */
[data-baseweb="tab-panel"] {
    padding-top: 8px;
}

/* Footer hint at the bottom */
.app-footer {
    margin-top: 40px;
    padding-top: 16px;
    border-top: 1px solid #eee;
    color: #999;
    font-size: 10pt;
    text-align: center;
    font-family: ui-monospace, "SF Mono", Consolas, monospace;
}

/* =========================================================
   Welcome / Landing page — fullscreen + dynamic
   ========================================================= */
/* Hide scrollbar artifacts on welcome */
body:has(.welcome-wrap) { overflow-x: hidden; }

.welcome-wrap {
    position: relative;
    width: 100vw;
    margin-left: calc(-50vw + 50%);
    min-height: 100vh;
    padding: 80px 40px 100px;
    text-align: center;
    color: white;
    overflow: hidden;
    isolation: isolate;
    background:
        radial-gradient(ellipse 80% 60% at 20% 20%, rgba(13,148,136,0.35) 0%, transparent 60%),
        radial-gradient(ellipse 70% 80% at 80% 30%, rgba(20,120,90,0.30) 0%, transparent 55%),
        radial-gradient(ellipse 60% 50% at 50% 90%, rgba(0,80,70,0.45) 0%, transparent 60%),
        linear-gradient(180deg, #060606 0%, #062b29 50%, #050505 100%);
    background-size: 100% 100%;
    animation: meshShift 18s ease-in-out infinite;
}
@keyframes meshShift {
    0%, 100% { background-position: 0% 0%, 100% 0%, 50% 100%, 0 0; }
    33% { background-position: 30% 20%, 70% 50%, 60% 80%, 0 0; }
    66% { background-position: 60% 10%, 40% 30%, 40% 90%, 0 0; }
}

/* Drifting blobs */
.welcome-wrap .blob {
    position: absolute;
    border-radius: 50%;
    filter: blur(80px);
    opacity: 0.55;
    z-index: 0;
    pointer-events: none;
}
.welcome-wrap .blob-1 { width: 480px; height: 480px; background: #0d9488; top: -100px; left: -120px;  animation: drift1 22s ease-in-out infinite; }
.welcome-wrap .blob-2 { width: 380px; height: 380px; background: #115e59; top: 30%;    right: -100px; animation: drift2 28s ease-in-out infinite; }
.welcome-wrap .blob-3 { width: 520px; height: 520px; background: #042f2e; bottom: -180px; left: 25%;  animation: drift3 32s ease-in-out infinite; }
.welcome-wrap .blob-4 { width: 320px; height: 320px; background: #34d399; opacity: 0.30; top: 50%; left: 50%; animation: drift4 26s ease-in-out infinite; }
@keyframes drift1 { 0%,100%{transform:translate(0,0) scale(1);} 50%{transform:translate(120px, 80px) scale(1.1);} }
@keyframes drift2 { 0%,100%{transform:translate(0,0) scale(1);} 50%{transform:translate(-100px, 120px) scale(0.9);} }
@keyframes drift3 { 0%,100%{transform:translate(0,0) scale(1);} 50%{transform:translate(60px, -80px) scale(1.05);} }
@keyframes drift4 { 0%,100%{transform:translate(-50%,-50%) scale(1);} 50%{transform:translate(-30%,-70%) scale(1.2);} }

/* Particle / sparkle field */
.welcome-wrap .stars {
    position: absolute; inset: 0; pointer-events: none; z-index: 1;
}
.welcome-wrap .stars span {
    position: absolute;
    width: 2px; height: 2px;
    background: white;
    border-radius: 50%;
    box-shadow: 0 0 8px rgba(255,255,255,0.8);
    animation: twinkle 3s ease-in-out infinite;
}
@keyframes twinkle {
    0%, 100% { opacity: 0.2; transform: scale(0.5); }
    50%     { opacity: 1;   transform: scale(1.4); }
}

/* AI orb — bigger + animated rings */
.welcome-content { position: relative; z-index: 5; max-width: 900px; margin: 0 auto; }
.ai-orb {
    width: 220px; height: 220px;
    margin: 30px auto 36px;
    position: relative;
}
.ai-orb .ring {
    position: absolute; inset: 0;
    border-radius: 50%;
    border: 1px solid rgba(167,243,208,0.25);
}
.ai-orb .ring-1 { animation: spin 14s linear infinite; }
.ai-orb .ring-2 { inset: -22px; border-color: rgba(94,234,212,0.20); animation: spin 22s linear infinite reverse; }
.ai-orb .ring-3 { inset: -50px; border-color: rgba(52,211,153,0.12); animation: spin 30s linear infinite; }
@keyframes spin { from{transform:rotate(0);} to{transform:rotate(360deg);} }
.ai-orb svg { width: 100%; height: 100%; animation: orbFloat 6s ease-in-out infinite; position: relative; z-index: 2; }
@keyframes orbFloat {
    0%,100% { transform: translateY(0) rotate(0); }
    50%     { transform: translateY(-12px) rotate(3deg); }
}
.ai-orb::before {
    content: "";
    position: absolute;
    inset: -40px;
    background: radial-gradient(circle, rgba(13,148,136,0.65) 0%, rgba(13,148,136,0) 65%);
    border-radius: 50%;
    animation: pulse 3s ease-in-out infinite;
    z-index: 1;
}
@keyframes pulse {
    0%,100% { transform: scale(1);    opacity: 0.5; }
    50%     { transform: scale(1.25); opacity: 1; }
}

/* Greeting + title */
.welcome-greeting {
    font-family: 'Source Serif Pro', Georgia, serif;
    font-style: italic;
    font-size: 26pt;
    color: #99f6e4;
    margin-bottom: 8px;
    opacity: 0;
    animation: fadeDown 0.8s ease-out 0.3s forwards;
}
.welcome-title {
    font-family: 'Source Serif Pro', Georgia, serif;
    font-size: 110pt;
    font-weight: 700;
    line-height: 1.0;
    letter-spacing: -3px;
    margin: 0 0 8px 0;
    background: linear-gradient(120deg, #fff 0%, #99f6e4 25%, #10b981 50%, #99f6e4 75%, #fff 100%);
    background-size: 200% 100%;
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: shimmer 6s linear infinite, fadeUp 1s ease-out 0.5s backwards;
}
.welcome-subtitle {
    font-family: ui-monospace, "SF Mono", Consolas, monospace;
    font-size: 14pt;
    color: #5eead4;
    letter-spacing: 6px;
    text-transform: uppercase;
    margin: 0 0 36px 0;
    opacity: 0;
    animation: fadeUp 1s ease-out 0.8s forwards;
}
@keyframes shimmer {
    0%   { background-position: 200% 0%; }
    100% { background-position: -200% 0%; }
}
.welcome-tagline {
    /* Force-center & highlight as a glassy card */
    display: block;
    width: 100%;
    max-width: 760px;
    margin: 0 auto 48px !important;
    padding: 24px 36px;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(167,243,208,0.25);
    border-radius: 18px;
    box-shadow:
        0 0 50px rgba(13,148,136,0.25) inset,
        0 12px 36px rgba(0,0,0,0.45);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    font-size: 17pt;
    color: rgba(255,255,255,0.92);
    line-height: 1.7;
    text-align: center !important;
    text-wrap: balance;
    opacity: 0;
    animation: fadeUp 0.9s ease-out 0.9s forwards, taglineGlow 4s ease-in-out 2s infinite;
    position: relative;
    z-index: 6;
}
.welcome-tagline em {
    color: #34d399;
    font-style: italic;
    font-weight: 700;
    text-shadow: 0 0 12px rgba(94,234,212,0.5);
}
@keyframes taglineGlow {
    0%, 100% { box-shadow: 0 0 50px rgba(13,148,136,0.25) inset, 0 12px 36px rgba(0,0,0,0.45); }
    50%      { box-shadow: 0 0 70px rgba(13,148,136,0.45) inset, 0 12px 36px rgba(0,0,0,0.45); }
}

@keyframes fadeUp   { from { opacity:0; transform: translateY(20px); } to { opacity:1; transform: translateY(0); } }
@keyframes fadeDown { from { opacity:0; transform: translateY(-15px);} to { opacity:1; transform: translateY(0); } }

/* Feature cards — stagger entrance */
.welcome-features {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 12px;
    max-width: 1240px;
    margin: 0 auto 40px;
}
@media (max-width: 1100px) {
    .welcome-features { grid-template-columns: repeat(3, 1fr); max-width: 720px; }
}
@media (max-width: 640px) {
    .welcome-features { grid-template-columns: repeat(2, 1fr); }
}
.welcome-feature {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 16px;
    padding: 18px 14px 16px;
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    transition: all 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
    opacity: 0;
    animation: fadeUp 0.7s ease-out forwards;
    min-height: 200px;
}
.welcome-feature:nth-child(1) { animation-delay: 1.1s; }
.welcome-feature:nth-child(2) { animation-delay: 1.25s; }
.welcome-feature:nth-child(3) { animation-delay: 1.4s; }
.welcome-feature:nth-child(4) { animation-delay: 1.55s; }
.welcome-feature:nth-child(5) { animation-delay: 1.7s; }
.welcome-feature:nth-child(6) { animation-delay: 1.85s; }
.welcome-feature:hover {
    background: rgba(13,148,136,0.20);
    border-color: rgba(94,234,212,0.55);
    transform: translateY(-6px);
    box-shadow: 0 20px 40px rgba(13,148,136,0.25);
}
.welcome-feature .feat-icon {
    font-size: 24pt;
    margin-bottom: 8px;
    display: block;
}
.welcome-feature .feat-title {
    font-weight: 700;
    font-size: 12pt;
    margin-bottom: 6px;
    color: white;
    line-height: 1.2;
}
.welcome-feature .feat-desc {
    font-size: 10pt;
    color: rgba(255,255,255,0.65);
    line-height: 1.45;
}

/* Path picker cards (3 starting points) */
.path-card {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(167,243,208,0.25);
    border-radius: 18px;
    padding: 22px 18px 16px;
    margin: 12px 4px 12px;
    backdrop-filter: blur(14px);
    transition: all 0.25s cubic-bezier(0.2, 0.8, 0.2, 1);
    color: white;
    min-height: 220px;
}
.path-card:hover {
    background: rgba(13,148,136,0.20);
    border-color: rgba(94,234,212,0.65);
    transform: translateY(-4px);
    box-shadow: 0 16px 40px rgba(13,148,136,0.30);
}
.path-card-featured {
    border-color: rgba(94,234,212,0.55);
    background: rgba(13,148,136,0.12);
    box-shadow: 0 0 30px rgba(13,148,136,0.20) inset;
}
.path-card .path-icon {
    font-size: 32pt;
    line-height: 1;
    margin-bottom: 10px;
}
.path-card .path-title {
    font-family: 'Source Serif Pro', Georgia, serif;
    font-size: 20pt;
    font-weight: 700;
    color: white;
    margin-bottom: 4px;
}
.path-card .path-time {
    font-family: ui-monospace, monospace;
    font-size: 10pt;
    color: #5eead4;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 12px;
}
.path-card .path-desc {
    font-size: 11pt;
    color: rgba(255,255,255,0.78);
    line-height: 1.5;
}
.path-card .path-desc strong {
    color: #a7f3d0;
    font-weight: 600;
}

/* CTA hint with bounce */
.welcome-cta-hint {
    margin-top: 36px;
    font-size: 11pt;
    color: rgba(255,255,255,0.55);
    font-family: ui-monospace, "SF Mono", Consolas, monospace;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    opacity: 0;
    animation: fadeUp 0.6s ease-out 1.7s forwards, bob 2s ease-in-out 2.5s infinite;
}
@keyframes bob {
    0%,100% { transform: translateY(0); }
    50%     { transform: translateY(6px); }
}
</style>
""", unsafe_allow_html=True)

for k in ("syllabus","style_profile","outline","outline_inputs","examples","html_path","dataset_path","activity_path","pdf_path","last_eval","alternatives","alt_html_paths","intro_video_path","intro_video_meta","study_guide_path","study_guide_meta"):
    st.session_state.setdefault(k, None)
if st.session_state["syllabus"] is None:
    st.session_state["syllabus"] = load_syllabus()
if st.session_state["style_profile"] is None:
    st.session_state["style_profile"] = load_style_profile()
st.session_state.setdefault("welcomed", False)

# ---------- Welcome / landing page (shown until user clicks "Get started") ----------
if not st.session_state["welcomed"]:
    # Generate scattered star positions for the particle field
    import random as _random
    _random.seed(42)
    _star_html = "".join(
        f'<span style="top:{_random.randint(2, 96)}%; left:{_random.randint(2, 98)}%; '
        f'animation-delay:{_random.uniform(0, 3):.1f}s; '
        f'opacity:{_random.uniform(0.3, 1):.2f}; '
        f'transform:scale({_random.uniform(0.5, 1.6):.2f});"></span>'
        for _ in range(70)
    )

    # NOTE: keep this HTML on a single block with NO blank lines.
    # Streamlit's markdown parser breaks out of "raw HTML mode" on blank lines
    # and starts treating subsequent indented lines as code blocks.
    _welcome_html = (
        '<div class="welcome-wrap">'
        '<div class="blob blob-1"></div>'
        '<div class="blob blob-2"></div>'
        '<div class="blob blob-3"></div>'
        '<div class="blob blob-4"></div>'
        f'<div class="stars">{_star_html}</div>'
        '<div class="welcome-content">'
          '<div class="ai-orb">'
            '<div class="ring ring-1"></div>'
            '<div class="ring ring-2"></div>'
            '<div class="ring ring-3"></div>'
            '<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">'
              '<defs>'
                '<radialGradient id="headBody" cx="50%" cy="35%" r="65%">'
                  '<stop offset="0%" stop-color="#0a4a47"/>'
                  '<stop offset="55%" stop-color="#062b29"/>'
                  '<stop offset="100%" stop-color="#021614"/>'
                '</radialGradient>'
                '<linearGradient id="edgeGlow" x1="0%" y1="0%" x2="100%" y2="100%">'
                  '<stop offset="0%" stop-color="#5eead4"/>'
                  '<stop offset="100%" stop-color="#0d9488"/>'
                '</linearGradient>'
                '<linearGradient id="eyeGlow" x1="0%" x2="0%" y1="0%" y2="100%">'
                  '<stop offset="0%" stop-color="#d1fae5"/>'
                  '<stop offset="100%" stop-color="#34d399"/>'
                '</linearGradient>'
                '<filter id="softGlow"><feGaussianBlur stdDeviation="2.5"/></filter>'
              '</defs>'
              # ----- Top antenna with pulsing tip -----
              '<line x1="100" y1="12" x2="100" y2="40" stroke="#5eead4" stroke-width="1.5" stroke-linecap="round"/>'
              '<circle cx="100" cy="9" r="4" fill="#34d399" filter="url(#softGlow)">'
                '<animate attributeName="r" values="3;5;3" dur="1.6s" repeatCount="indefinite"/>'
              '</circle>'
              # ----- Side mini-antennas -----
              '<line x1="65" y1="50" x2="58" y2="40" stroke="#5eead4" stroke-width="1" stroke-linecap="round"/>'
              '<circle cx="58" cy="40" r="2" fill="#5eead4"/>'
              '<line x1="135" y1="50" x2="142" y2="40" stroke="#5eead4" stroke-width="1" stroke-linecap="round"/>'
              '<circle cx="142" cy="40" r="2" fill="#5eead4"/>'
              # ----- Main robot head (rounded hexagon) -----
              '<path d="M 60 50 L 140 50 Q 156 50 159 67 L 163 88 Q 163 102 159 117 L 153 144 Q 146 162 130 162 L 70 162 Q 54 162 47 144 L 41 117 Q 37 102 37 88 L 41 67 Q 44 50 60 50 Z" '
                  'fill="url(#headBody)" stroke="url(#edgeGlow)" stroke-width="2"/>'
              # ----- Inner frame outline -----
              '<path d="M 72 62 L 128 62 Q 139 62 142 76 L 145 95 Q 145 105 142 115 L 139 134 Q 134 148 122 148 L 78 148 Q 66 148 61 134 L 58 115 Q 55 105 55 95 L 58 76 Q 61 62 72 62 Z" '
                  'fill="none" stroke="rgba(94,234,212,0.25)" stroke-width="1"/>'
              # ----- Brow accent line -----
              '<path d="M 58 88 L 142 88" stroke="rgba(94,234,212,0.35)" stroke-width="0.8" stroke-dasharray="2,2"/>'
              # ----- Forehead processor / "third eye" -----
              '<circle cx="100" cy="76" r="4" fill="#34d399" filter="url(#softGlow)">'
                '<animate attributeName="opacity" values="0.5;1;0.5" dur="2s" repeatCount="indefinite"/>'
              '</circle>'
              '<circle cx="100" cy="76" r="2" fill="#d1fae5"/>'
              # ----- Eyes (glowing slits) -----
              '<rect x="58" y="100" width="28" height="8" rx="4" fill="url(#eyeGlow)" filter="url(#softGlow)">'
                '<animate attributeName="opacity" values="0.7;1;0.7" dur="2.4s" repeatCount="indefinite"/>'
              '</rect>'
              '<rect x="58" y="100" width="28" height="8" rx="4" fill="url(#eyeGlow)" opacity="0.95"/>'
              '<rect x="114" y="100" width="28" height="8" rx="4" fill="url(#eyeGlow)" filter="url(#softGlow)">'
                '<animate attributeName="opacity" values="0.7;1;0.7" dur="2.4s" begin="0.3s" repeatCount="indefinite"/>'
              '</rect>'
              '<rect x="114" y="100" width="28" height="8" rx="4" fill="url(#eyeGlow)" opacity="0.95"/>'
              # ----- Brain / neural network nodes (lower face) -----
              '<g fill="#a7f3d0">'
                '<circle cx="80" cy="125" r="1.6">'
                  '<animate attributeName="opacity" values="0.4;1;0.4" dur="2s" repeatCount="indefinite"/></circle>'
                '<circle cx="100" cy="120" r="1.6">'
                  '<animate attributeName="opacity" values="0.4;1;0.4" dur="2s" begin="0.4s" repeatCount="indefinite"/></circle>'
                '<circle cx="120" cy="125" r="1.6">'
                  '<animate attributeName="opacity" values="0.4;1;0.4" dur="2s" begin="0.8s" repeatCount="indefinite"/></circle>'
                '<circle cx="92" cy="135" r="1.6">'
                  '<animate attributeName="opacity" values="0.4;1;0.4" dur="2s" begin="0.2s" repeatCount="indefinite"/></circle>'
                '<circle cx="108" cy="135" r="1.6">'
                  '<animate attributeName="opacity" values="0.4;1;0.4" dur="2s" begin="0.6s" repeatCount="indefinite"/></circle>'
                '<circle cx="100" cy="142" r="1.6">'
                  '<animate attributeName="opacity" values="0.4;1;0.4" dur="2s" begin="1s" repeatCount="indefinite"/></circle>'
              '</g>'
              # ----- Neural connection lines -----
              '<g stroke="rgba(94,234,212,0.45)" stroke-width="0.8" fill="none">'
                '<line x1="80" y1="125" x2="100" y2="120"/>'
                '<line x1="100" y1="120" x2="120" y2="125"/>'
                '<line x1="80" y1="125" x2="92" y2="135"/>'
                '<line x1="120" y1="125" x2="108" y2="135"/>'
                '<line x1="92" y1="135" x2="108" y2="135"/>'
                '<line x1="100" y1="120" x2="100" y2="142"/>'
                '<line x1="92" y1="135" x2="100" y2="142"/>'
                '<line x1="108" y1="135" x2="100" y2="142"/>'
              '</g>'
              # ----- Side sensor pods (ears) -----
              '<rect x="32" y="100" width="10" height="22" rx="3" fill="#062b29" stroke="#5eead4" stroke-width="1"/>'
              '<circle cx="37" cy="111" r="1.5" fill="#34d399">'
                '<animate attributeName="opacity" values="0.5;1;0.5" dur="1.8s" repeatCount="indefinite"/></circle>'
              '<rect x="158" y="100" width="10" height="22" rx="3" fill="#062b29" stroke="#5eead4" stroke-width="1"/>'
              '<circle cx="163" cy="111" r="1.5" fill="#34d399">'
                '<animate attributeName="opacity" values="0.5;1;0.5" dur="1.8s" begin="0.5s" repeatCount="indefinite"/></circle>'
              # ----- Speaker grille (mouth/voice) -----
              '<g stroke="#5eead4" stroke-width="1.2" opacity="0.7" stroke-linecap="round">'
                '<line x1="86" y1="155" x2="86" y2="158"/>'
                '<line x1="93" y1="153" x2="93" y2="159"/>'
                '<line x1="100" y1="152" x2="100" y2="160"/>'
                '<line x1="107" y1="153" x2="107" y2="159"/>'
                '<line x1="114" y1="155" x2="114" y2="158"/>'
              '</g>'
              # ----- Scan line sweeping top→bottom -----
              '<rect x="42" y="60" width="116" height="1.5" fill="rgba(167,243,208,0.7)">'
                '<animate attributeName="opacity" values="0;0.8;0" dur="3.5s" repeatCount="indefinite"/>'
                '<animate attributeName="y" from="60" to="155" dur="3.5s" repeatCount="indefinite"/>'
              '</rect>'
            '</svg>'
          '</div>'
          '<div class="welcome-greeting">Hey, Professor! 👋</div>'
          '<h1 class="welcome-title">SlideGen</h1>'
          '<div class="welcome-subtitle">Your AI course assistant</div>'
          '<p class="welcome-tagline">'
            'Turn a course description into a full <em>semester syllabus</em>, '
            'then craft <em>style-matched lectures</em> in your <em>own voice</em> — slide by slide. '
            '<br>Code walkthroughs, classroom games, homework, datasets — '
            '<em>all generated on demand</em>.'
          '</p>'
          '<div class="welcome-features">'
            '<div class="welcome-feature">'
              '<span class="feat-icon">📐</span>'
              '<div class="feat-title">Style-aware</div>'
              '<div class="feat-desc">Learns from your past decks — bullet rhythm, question titles, red key terms.</div>'
            '</div>'
            '<div class="welcome-feature">'
              '<span class="feat-icon">💻</span>'
              '<div class="feat-title">Code &amp; datasets</div>'
              '<div class="feat-desc">Step-by-step Python with explanations. Excel datasets for hands-on practice.</div>'
            '</div>'
            '<div class="welcome-feature">'
              '<span class="feat-icon">🎮</span>'
              '<div class="feat-title">Classroom games</div>'
              '<div class="feat-desc">10-minute warm-ups: Excel simulations or curated web tools.</div>'
            '</div>'
            '<div class="welcome-feature">'
              '<span class="feat-icon">📤</span>'
              '<div class="feat-title">Export anywhere</div>'
              '<div class="feat-desc">HTML to present, PPTX to edit, PDF for handouts. One click each.</div>'
            '</div>'
            '<div class="welcome-feature">'
              '<span class="feat-icon">🎬</span>'
              '<div class="feat-title">Class intro video</div>'
              '<div class="feat-desc">60-90 sec narrated teaser — get students excited before class. Share on Canvas or email.</div>'
            '</div>'
            '<div class="welcome-feature">'
              '<span class="feat-icon">🎓</span>'
              '<div class="feat-title">Student self-study</div>'
              '<div class="feat-desc">Flash cards + self-quiz. Send the link — students review at their own pace.</div>'
            '</div>'
          '</div>'
          '<div class="welcome-cta-hint">↓ Pick how you want to start ↓</div>'
        '</div>'
        '</div>'
    )
    st.markdown(_welcome_html, unsafe_allow_html=True)

    # ── Path picker — 3 starting points ─────────────────────
    pc1, pc2, pc3 = st.columns(3, gap="small")
    with pc1:
        st.markdown(
            '<div class="path-card">'
            '<div class="path-icon">📝</div>'
            '<div class="path-title">One-off lecture</div>'
            '<div class="path-time">~5 minutes</div>'
            '<div class="path-desc">A guest talk, workshop, or single class. Type a topic, optionally upload past slides for style match, get a deck. <strong>No course setup needed.</strong></div>'
            '</div>',
            unsafe_allow_html=True,
        )
        if st.button("Start →", key="start_quick", use_container_width=True, type="primary"):
            st.session_state["welcomed"] = True
            st.session_state["start_mode"] = "quick"
            st.rerun()
    with pc2:
        st.markdown(
            '<div class="path-card path-card-featured">'
            '<div class="path-icon">📚</div>'
            '<div class="path-title">Full course</div>'
            '<div class="path-time">~30 minutes setup</div>'
            '<div class="path-desc">A semester-long course. Generate a syllabus, analyze your style from past decks, then build week-by-week with memory across sessions. <strong>The full SlideGen experience.</strong></div>'
            '</div>',
            unsafe_allow_html=True,
        )
        if st.button("Start →", key="start_full", use_container_width=True, type="primary"):
            st.session_state["welcomed"] = True
            st.session_state["start_mode"] = "full"
            st.rerun()
    with pc3:
        st.markdown(
            '<div class="path-card">'
            '<div class="path-icon">🎯</div>'
            '<div class="path-title">Outline only</div>'
            '<div class="path-time">~2 minutes</div>'
            '<div class="path-desc">Just want a structured outline to write yourself? Type a topic, get a slide-by-slide plan as text. <strong>No deck — just the skeleton.</strong></div>'
            '</div>',
            unsafe_allow_html=True,
        )
        if st.button("Start →", key="start_outline", use_container_width=True, type="primary"):
            st.session_state["welcomed"] = True
            st.session_state["start_mode"] = "outline"
            st.rerun()

    st.markdown(
        '<div class="app-footer" style="margin-top:32px;">Made for business school instructors</div>',
        unsafe_allow_html=True
    )
    st.stop()

# ---------- Hero header ----------
hero_col, back_col = st.columns([5, 1])
with hero_col:
    st.markdown("""
<div class="hero">
  <h1>📚 SlideGen</h1>
  <div class="hero-sub">AI course decks for business school instructors — style-matched, in your voice.</div>
  <div class="hero-flow">Course → Style → Session → Deck → Video → Study guide</div>
</div>
""", unsafe_allow_html=True)
with back_col:
    st.markdown("<div style='height: 30px'></div>", unsafe_allow_html=True)
    if st.button("↻ Welcome screen", key="show_welcome"):
        st.session_state["welcomed"] = False
        st.rerun()

# ---------- Status pills ----------
def _pill(label, active):
    cls = "status-pill active" if active else "status-pill"
    icon = "✓" if active else "○"
    return f'<span class="{cls}">{icon} {label}</span>'

_pills_html = '<div class="status-row">' + "".join([
    _pill("Syllabus", bool(st.session_state.get("syllabus"))),
    _pill("Style profile", bool(st.session_state.get("style_profile"))),
    _pill("Outline", bool(st.session_state.get("outline"))),
    _pill("HTML deck", bool(st.session_state.get("html_path") and Path(st.session_state.get("html_path") or "").exists())),
    _pill("Intro video", bool(st.session_state.get("intro_video_path") and Path(st.session_state.get("intro_video_path") or "").exists())),
    _pill("Study guide", bool(st.session_state.get("study_guide_path") and Path(st.session_state.get("study_guide_path") or "").exists())),
]) + '</div>'
st.markdown(_pills_html, unsafe_allow_html=True)

# ── Path-mode guidance banner (only shown if user picked one on welcome) ──
_mode = st.session_state.get("start_mode")
if _mode:
    _mode_msg = {
        "quick":   ("⚡ **Quick deck mode** — go to the **⚡ Quick deck** tab (first one). "
                    "Type a topic + optional pptx, get a deck in ~5 min."),
        "full":    ("📚 **Full course mode** — work through the numbered tabs in order: "
                    "**1. Course** → **2. Style** → **3. Outline** → **4. Deck** → (optional 5/6)."),
        "outline": ("🎯 **Outline only mode** — go to the **⚡ Quick deck** tab and check "
                    "**'Outline only — skip deck build'** at the bottom. Get a text outline you can paste anywhere."),
    }.get(_mode)
    if _mode_msg:
        gc1, gc2 = st.columns([6, 1])
        with gc1:
            st.info(_mode_msg)
        with gc2:
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            if st.button("↻ Change mode", key="change_mode_btn"):
                st.session_state["welcomed"] = False
                st.session_state["start_mode"] = None
                st.rerun()

# ── Per-user quota badge (beta-mode only) ──
_auth.render_usage_badge()
# Admin panel — wrapped defensively so any bug here doesn't crash the whole app
try:
    _auth.render_admin_panel()
except AttributeError:
    # Older deployed auth.py without render_admin_panel — silently skip
    pass
except Exception as _e:
    if _auth.is_admin():
        st.warning(f"⚠️ Admin panel unavailable: `{_e}`. Reboot the app from "
                   "Manage app → ⋮ → Reboot.")

tabs = st.tabs(["⚡ Quick deck","1. Course","2. Teaching style","3. Session outline","4. Deck","5. 🎬 Intro video","6. 🎓 Study guide"])

# ═══════════════════════════════════════════════════════════════
#  ⚡ QUICK DECK — single-topic, no-syllabus express path
#  Skips Stage 1-3. One topic in, one deck out. Optional pptx upload
#  for instant style match. Counts as 1 toward the user's quota.
# ═══════════════════════════════════════════════════════════════
with tabs[0]:
    st.subheader("⚡ Quick deck — one topic, no setup")
    st.markdown(
        "Just want a deck on a single topic? Skip the syllabus / course-memory flow. "
        "Type your topic, optionally upload past slides for style matching, and click build. "
        "**Best for**: guest lectures, workshops, one-off sessions, or just testing the tool."
    )

    qc1, qc2 = st.columns([2, 1])
    with qc1:
        q_topic = st.text_input(
            "Topic *",
            placeholder="e.g., Probability for Business Uncertainty",
            key="q_topic",
        )
        q_objectives = st.text_area(
            "Learning objectives (one per line) *",
            height=120,
            placeholder="Students will be able to:\n• Apply Bayes' rule to business decisions\n• Distinguish frequentist vs Bayesian thinking\n• Use probability trees for sequential decisions",
            key="q_objectives",
        )
        q_notes = st.text_area(
            "Rough notes (optional)",
            height=80,
            placeholder="Anything specific you want covered: a case, a story, a particular angle…",
            key="q_notes",
        )
    with qc2:
        q_module = st.selectbox("Subject area", MODULE_AREAS, key="q_module")
        q_audience = st.selectbox(
            "Audience level",
            options=list(AUDIENCE_LEVELS.keys()),
            format_func=lambda k: f"{k.title()} — {AUDIENCE_LEVELS[k][:40]}…",
            index=1, key="q_audience",
        )
        q_duration = st.slider("Class duration (min)", 30, 180, 75, 15, key="q_duration")
        q_target_slides = st.number_input("Target slides", 8, 40, 18, key="q_target_slides")
        q_include_code = st.checkbox("Include Python code", value=False, key="q_include_code")
        q_include_homework = st.checkbox("Include homework", value=False, key="q_include_homework")
        q_include_activity = st.checkbox("Include in-class activity", value=False, key="q_include_activity")

    st.markdown("---")
    st.markdown("**🎨 Style match (optional)** — upload 1-3 of your past slides to make the deck look like *yours*.")
    q_pptx_files = st.file_uploader(
        "Past .pptx files",
        type=["pptx"],
        accept_multiple_files=True,
        help="If skipped, the deck uses a generic clean style.",
        key="q_pptx_uploader",
    )

    # If user picked "outline only" path on welcome, default the checkbox to True
    _outline_only_default = (st.session_state.get("start_mode") == "outline")
    q_outline_only = st.checkbox(
        "🎯 Outline only — skip deck build, just give me the structured text outline",
        value=_outline_only_default, key="q_outline_only",
        help="Gets you a slide-by-slide plan as text/markdown you can edit or paste anywhere. ~30 sec faster, no images, no deck.",
    )

    if not q_outline_only:
        q_image_mode = st.radio(
            "Images for image-type slides:",
            options=["search", "svg", "skip"],
            format_func=lambda x: {
                "search": "🔍 Web search (real photos)",
                "svg":    "🎨 AI-generated diagrams",
                "skip":   "⏭ Skip — placeholders only (fastest)",
            }[x],
            index=0, horizontal=True, key="q_image_mode",
        )
        q_theme = st.selectbox(
            "Background theme",
            options=list(THEMES.keys()),
            format_func=lambda k: THEMES[k]["label"],
            index=0, key="q_theme",
        )
    else:
        # Set defaults so downstream code doesn't crash
        q_image_mode = "skip"
        q_theme = "light_gray"

    st.markdown("---")
    _q_can_build = _auth.can_build()
    if q_outline_only:
        _q_btn_label = "📝 Generate outline" if _q_can_build else "📝 Generate outline (quota reached)"
    else:
        _q_btn_label = "🚀 Build deck" if _q_can_build else "🚀 Build deck (quota reached)"
    if st.button(_q_btn_label, type="primary", key="q_build", disabled=not _q_can_build,
                 use_container_width=True):
        if not q_topic.strip():
            st.error("Topic is required.")
        elif not q_objectives.strip():
            st.error("At least one learning objective required.")
        elif not _auth.can_build():
            st.error("⚠️ Quota reached. Email dvora5018@gmail.com for more.")
        else:
            obj_list = [o.strip().lstrip("•·-* ").strip()
                        for o in q_objectives.splitlines() if o.strip()]

            # Step 1: optional style profile from uploaded pptx
            q_style_profile = None
            if q_pptx_files:
                with st.spinner(f"Analyzing your style from {len(q_pptx_files)} pptx file(s)..."):
                    try:
                        # Save uploaded files to a temp folder so style_analyzer can read them
                        import tempfile, os as _os
                        with tempfile.TemporaryDirectory() as _td:
                            paths = []
                            for f in q_pptx_files:
                                p = _os.path.join(_td, f.name)
                                with open(p, "wb") as _w:
                                    _w.write(f.read())
                                paths.append(p)
                            q_style_profile = extract_style_profile(paths)
                        st.success(f"✓ Style profile extracted from {len(q_pptx_files)} file(s).")
                    except Exception as e:
                        st.warning(f"Style extraction failed ({e}). Building with default style.")

            # Step 2: generate outline (no syllabus, no course memory)
            with st.spinner("Drafting outline..."):
                try:
                    outline_json = generate_outline(
                        topic=q_topic.strip(),
                        objectives=obj_list,
                        rough_notes=q_notes.strip(),
                        module=q_module,
                        duration_minutes=int(q_duration),
                        recent_examples=[],
                        style_profile=q_style_profile,
                        target_slides=int(q_target_slides),
                        include_code=bool(q_include_code),
                        include_homework=bool(q_include_homework),
                        include_activity=bool(q_include_activity),
                        prior_memory=None,
                        include_recap=False,
                        audience_level=q_audience,
                    )
                    st.session_state["outline"] = outline_json
                except Exception as e:
                    st.error(f"Outline generation failed: {e}")
                    st.stop()

            # Step 3: build HTML deck (skipped if outline-only mode)
            if q_outline_only:
                # Just count usage; the outline display happens in the section below
                _auth.consume_deck()
                st.session_state["html_path"] = None
                st.session_state["pdf_path"] = None
                st.success(f"🎉 Outline ready below! {_auth.remaining_decks()} build(s) remaining.")
            else:
                with st.spinner("Building deck..."):
                    try:
                        safe_name = "".join(c if c.isalnum() else "_" for c in q_topic[:40]).strip("_")
                        out_html = f"output/quick_{safe_name}.html"
                        path = build_html(outline_json, out_html,
                                          image_mode=q_image_mode, theme=q_theme)
                        st.session_state["html_path"] = path
                        st.session_state["pdf_path"] = None
                        _auth.consume_deck()
                        st.success(f"🎉 Deck ready! {_auth.remaining_decks()} build(s) remaining.")
                    except Exception as e:
                        st.error(f"Deck build failed: {e}")
                        st.stop()

    # ── Outline-only output: render as markdown text ──
    if q_outline_only and st.session_state.get("outline"):
        try:
            _outline_dict = json.loads(st.session_state["outline"])
        except Exception:
            _outline_dict = None
        if _outline_dict:
            st.markdown("---")
            st.markdown("### 📝 Your outline")
            # Build markdown from the outline JSON
            md_lines = [f"# {_outline_dict.get('session_title', q_topic)}",
                        f"_{_outline_dict.get('duration_minutes', q_duration)} min · {q_module} · {q_audience} level_",
                        ""]
            if _outline_dict.get("learning_objectives"):
                md_lines.append("## Learning objectives")
                for lo in _outline_dict["learning_objectives"]:
                    md_lines.append(f"- {lo}")
                md_lines.append("")
            md_lines.append("## Slides")
            for i, slide in enumerate(_outline_dict.get("slides") or [], 1):
                title = slide.get("title", "(untitled)")
                stype = (slide.get("type") or "concept").title()
                md_lines.append(f"\n### Slide {i}: {title}  *({stype})*")
                for line in slide.get("lines") or []:
                    if isinstance(line, dict):
                        text = line.get("text", "")
                        if line.get("bold"): text = f"**{text}**"
                        if line.get("red"): text = f"**🔴 {text}**"
                        md_lines.append(f"- {text}")
                    else:
                        md_lines.append(f"- {line}")
                if slide.get("key_takeaway"):
                    md_lines.append(f"\n  > 💡 **Key insight:** {slide['key_takeaway']}")
            if _outline_dict.get("homework"):
                hw = _outline_dict["homework"]
                md_lines.append(f"\n## Homework: {hw.get('title', '')}")
                if hw.get("problem_statement"):
                    md_lines.append(hw["problem_statement"])
            if _outline_dict.get("activity"):
                act = _outline_dict["activity"]
                md_lines.append(f"\n## In-class activity: {act.get('title', '')}")
                if act.get("instructions"):
                    md_lines.append(act["instructions"])
            md_text = "\n".join(md_lines)

            # Tabs: rendered preview + raw markdown for copy
            ot1, ot2 = st.tabs(["📖 Preview", "📋 Markdown (copy/paste)"])
            with ot1:
                st.markdown(md_text)
            with ot2:
                st.code(md_text, language="markdown")

            # Download as .md file
            safe_name = "".join(c if c.isalnum() else "_" for c in q_topic[:40]).strip("_")
            st.download_button(
                "⬇ Download outline (.md)",
                md_text,
                file_name=f"outline_{safe_name}.md",
                mime="text/markdown",
                use_container_width=True,
            )
            st.caption(
                "Want to turn this into actual slides later? Uncheck 'Outline only' above and click again — "
                "or switch to **Stage 4** and click Build (your outline is already loaded)."
            )

    # Download buttons (re-uses the same html_path session state as Stage 4).
    # Naturally skipped in outline-only mode because html_path is None.
    if not q_outline_only and st.session_state.get("html_path") and Path(st.session_state["html_path"]).exists():
        st.markdown("---")
        st.markdown("**📥 Download your deck:**")
        dc1, dc2, dc3 = st.columns(3)
        with dc1:
            with open(st.session_state["html_path"], "rb") as f:
                st.download_button("⬇ HTML (live deck)", f,
                                   file_name=Path(st.session_state["html_path"]).name,
                                   mime="text/html", use_container_width=True)
        with dc2:
            if st.button("📊 Export PPTX", key="q_export_pptx", use_container_width=True):
                with st.spinner("Building PPTX..."):
                    base = Path(st.session_state["html_path"]).stem
                    pptx_path = export_pptx(st.session_state["outline"], f"output/{base}.pptx")
                    st.session_state["pptx_path"] = pptx_path
                    st.success("PPTX ready below.")
        with dc3:
            if st.button("📄 Export PDF", key="q_export_pdf", use_container_width=True):
                with st.spinner("Rendering PDF..."):
                    try:
                        pdf_path = str(Path(st.session_state["html_path"]).with_suffix(".pdf"))
                        export_html_to_pdf(st.session_state["html_path"], pdf_path)
                        st.session_state["pdf_path"] = pdf_path
                        st.success("PDF ready below.")
                    except Exception as e:
                        st.error(f"PDF export failed: {e}")

        if st.session_state.get("pptx_path") and Path(st.session_state["pptx_path"]).exists():
            with open(st.session_state["pptx_path"], "rb") as f:
                st.download_button("⬇ PPTX (editable)", f,
                                   file_name=Path(st.session_state["pptx_path"]).name,
                                   mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")
        if st.session_state.get("pdf_path") and Path(st.session_state["pdf_path"]).exists():
            with open(st.session_state["pdf_path"], "rb") as f:
                st.download_button("⬇ PDF (handouts)", f,
                                   file_name=Path(st.session_state["pdf_path"]).name,
                                   mime="application/pdf")

        st.caption(
            "Want to edit slides before exporting? Switch to **Stage 3** — your outline is already loaded there."
        )


with tabs[1]:
    st.subheader("Stage 1 — Course → Syllabus")
    c1, c2 = st.columns([2, 1])
    with c1:
        course_description = st.text_area("Course description", height=180)
        recommended_textbook = st.text_input(
            "📖 Recommended textbook (optional)",
            placeholder="e.g., Anderson — Statistics for Business & Economics, 13th ed.",
            help="If specified, weekly readings will lead with chapters from this book, then add 1 supplemental article each week.",
        )
        extra_notes = st.text_area("Other instructor notes (optional)", height=80)
    with c2:
        course_level = st.selectbox("Course level", ["undergraduate","mba","executive"])
        module_area = st.selectbox("Primary module area", MODULE_AREAS)
        total_weeks = st.number_input("Total weeks", min_value=4, max_value=16, value=14, step=1)
    if st.button("Generate syllabus", type="primary", key="gen_syllabus"):
        if not course_description.strip(): st.error("Course description required.")
        else:
            with st.spinner("Drafting syllabus..."):
                syl = generate_syllabus(
                    course_description=course_description,
                    total_weeks=int(total_weeks),
                    course_level=course_level,
                    module_area=module_area,
                    extra_notes=extra_notes,
                    recommended_textbook=recommended_textbook,
                )
                st.session_state["syllabus"] = syl; save_syllabus(syl); st.success("Saved.")
    if st.session_state["syllabus"]:
        try: syl_obj = json.loads(st.session_state["syllabus"])
        except: syl_obj = None
        if syl_obj:
            st.markdown(f"### {syl_obj.get('course_title','(untitled)')}")
            st.caption(f"{syl_obj.get('course_level','')} · {syl_obj.get('total_weeks','')} weeks · {syl_obj.get('module_area','')}")
            # Show primary textbook if specified
            tb = syl_obj.get("primary_textbook") or ""
            if tb.strip():
                st.markdown(
                    f"<div style='margin:12px 0; padding:12px 16px; background:#ecfdf5; "
                    f"border-left:4px solid #0d9488; border-radius:8px;'>"
                    f"<span style='color:#0d9488; font-weight:600; font-size:10pt; text-transform:uppercase; letter-spacing:1px;'>📖 Primary textbook</span><br>"
                    f"<span style='font-size:12pt; color:#0f172a;'>{tb}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with st.expander("Weekly sessions", expanded=True):
                for s in syl_obj.get("sessions", []):
                    readings = s.get("suggested_readings", [])
                    readings_str = "; ".join(readings) if readings else ""
                    st.markdown(
                        f"**Week {s.get('week')} — {s.get('session_title')}**  \n"
                        f"_Module: {s.get('module','')}_  \n"
                        f"Topics: {', '.join(s.get('topics', []))}  \n"
                        f"📚 Readings: {readings_str}"
                    )
        with st.expander("⚙️ Advanced — edit raw syllabus JSON", expanded=False):
            st.caption("For power users. Edit the structured fields directly if the rendered view above isn't enough.")
            edited = st.text_area("Syllabus JSON", value=st.session_state["syllabus"], height=400, label_visibility="collapsed")
            if st.button("Save edits", key="save_syl"):
                st.session_state["syllabus"] = edited; save_syllabus(edited); st.success("Saved.")

with tabs[2]:
    st.subheader("Stage 2 — Teaching style")
    uploads = st.file_uploader("Upload previous .pptx lectures", type=["pptx"], accept_multiple_files=True)
    if st.button("Extract teaching style", type="primary", key="gen_style"):
        if not uploads: st.error("Upload at least one past .pptx.")
        else:
            sd = Path("style_profiles/sources"); sd.mkdir(parents=True, exist_ok=True)
            paths = []
            for u in uploads:
                p = sd / u.name; p.write_bytes(u.read()); paths.append(str(p))
            with st.spinner(f"Analyzing {len(paths)} deck(s)..."):
                prof = extract_style_profile(paths); save_style_profile(prof)
                st.session_state["style_profile"] = prof; st.success("Saved.")
    profile = st.session_state["style_profile"]
    if profile:
        q = profile.get("quantitative", {}) or {}
        qual = profile.get("qualitative", {}) or {}
        dims = compute_dimensions(profile)

        # ---------- Radar chart + key stats side-by-side ----------
        col_radar, col_stats = st.columns([3, 2])

        with col_radar:
            # Pure-SVG radar — no external chart library needed.
            import math as _math
            _size = 460
            _cx = _cy = _size / 2
            _r_max = _size * 0.32  # max plotted radius
            _items = list(dims.items())
            _n = len(_items)
            _angles = [(-_math.pi/2) + (2*_math.pi*i/_n) for i in range(_n)]

            # Background concentric rings + tick percent labels
            _rings = ""
            for frac in (0.25, 0.5, 0.75, 1.0):
                _rings += (
                    f'<circle cx="{_cx}" cy="{_cy}" r="{_r_max*frac:.1f}" '
                    f'fill="none" stroke="#e5e7eb" stroke-width="1" '
                    f'stroke-dasharray="{"" if frac == 1.0 else "3,4"}"/>'
                )

            # Radial axis lines
            _axes = ""
            for a in _angles:
                x = _cx + _r_max*_math.cos(a)
                y = _cy + _r_max*_math.sin(a)
                _axes += (f'<line x1="{_cx}" y1="{_cy}" x2="{x:.1f}" y2="{y:.1f}" '
                         f'stroke="#e5e7eb" stroke-width="1"/>')

            # Tick percent labels (25, 50, 75, 100) on top axis
            _ticks = ""
            for frac in (0.25, 0.5, 0.75, 1.0):
                ty = _cy - _r_max*frac
                _ticks += (
                    f'<text x="{_cx+4}" y="{ty+3:.1f}" font-size="9" fill="#9ca3af" '
                    f'font-family="Inter, sans-serif">{int(frac*100)}</text>'
                )

            # Data polygon points
            _pts = []
            for (label, val), a in zip(_items, _angles):
                r = _r_max * (val/100)
                x = _cx + r*_math.cos(a)
                y = _cy + r*_math.sin(a)
                _pts.append((x, y, label, val))
            _poly_pts = " ".join(f"{x:.1f},{y:.1f}" for x, y, _, _ in _pts)

            # Polygon fill + outline
            _poly = (
                f'<polygon points="{_poly_pts}" '
                f'fill="rgba(13,148,136,0.28)" stroke="#0d9488" stroke-width="2.5" '
                f'stroke-linejoin="round"/>'
            )
            # Data dots
            _dots = "".join(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#0d9488" stroke="white" stroke-width="2"/>'
                for x, y, _, _ in _pts
            )

            # Axis labels + score
            _labels_svg = ""
            for (x, y, label, val), a in zip(_pts, _angles):
                lr = _r_max + 36
                lx = _cx + lr*_math.cos(a)
                ly = _cy + lr*_math.sin(a)
                cos_a = _math.cos(a)
                anchor = "middle" if abs(cos_a) <= 0.3 else ("start" if cos_a > 0 else "end")
                _labels_svg += (
                    f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
                    f'font-family="Inter, sans-serif" font-size="12" font-weight="600" fill="#0f172a">'
                    f'{label}</text>'
                    f'<text x="{lx:.1f}" y="{ly+15:.1f}" text-anchor="{anchor}" '
                    f'font-family="Inter, sans-serif" font-size="11" font-weight="500" fill="#0d9488">'
                    f'{val}/100</text>'
                )

            radar_svg = (
                f'<div style="display:flex;justify-content:center;">'
                f'<svg viewBox="0 0 {_size} {_size}" '
                f'xmlns="http://www.w3.org/2000/svg" style="max-width:480px;width:100%;height:auto;">'
                f'{_rings}{_axes}{_ticks}{_poly}{_dots}{_labels_svg}'
                f'</svg></div>'
            )
            st.markdown(radar_svg, unsafe_allow_html=True)

        with col_stats:
            st.markdown("##### 📊 Key numbers")
            st.markdown(
                f"<div style='line-height:2;font-size:11pt;'>"
                f"📚 <b>{q.get('decks_analyzed','?')}</b> decks · "
                f"<b>{q.get('total_slides_analyzed','?')}</b> slides<br>"
                f"📊 <b>{q.get('avg_slides_per_lecture','?')}</b> slides / lecture<br>"
                f"📝 <b>{q.get('avg_lines_per_slide','?')}</b> lines / slide "
                f"<span style='color:#888;font-size:10pt;'>(median {q.get('median_lines_per_slide','?')})</span><br>"
                f"💬 <b>{q.get('avg_words_per_body_line','?')}</b> words / body line<br>"
                f"❓ <b>{int(q.get('question_title_ratio',0)*100)}%</b> question titles<br>"
                f"🖼 <b>{int(q.get('image_slide_ratio',0)*100)}%</b> image slides"
                f"</div>",
                unsafe_allow_html=True,
            )

        # ---------- Style summary card ----------
        summary = qual.get("teaching_style_summary") or qual.get("tone") or ""
        if summary:
            st.markdown(
                f"<div style='margin-top:18px;padding:18px 22px;border-radius:14px;"
                f"border-left:4px solid #0d9488;background:#f0fdfa;'>"
                f"<div style='font-size:10pt;color:#0d9488;font-weight:700;letter-spacing:1px;text-transform:uppercase;'>Style summary</div>"
                f"<div style='margin-top:6px;font-size:13pt;color:#0f172a;line-height:1.55;'>{summary}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        # ---------- Recurring phrases as pill tags ----------
        phrases = qual.get("recurring_phrases_or_patterns") or []
        if phrases:
            st.markdown("<div style='margin-top:18px;'><b>Your recurring phrases</b></div>", unsafe_allow_html=True)
            pill_html = "<div style='display:flex;flex-wrap:wrap;gap:8px;margin-top:8px;'>"
            for p in phrases[:8]:
                pill_html += (
                    f"<span style='background:#ecfdf5;color:#0f766e;border:1px solid #a7f3d0;"
                    f"border-radius:999px;padding:6px 14px;font-size:11pt;'>“{p}”</span>"
                )
            pill_html += "</div>"
            st.markdown(pill_html, unsafe_allow_html=True)

        # ---------- Other qualitative dimensions in compact grid ----------
        with st.expander("More qualitative detail"):
            for key in ("opening_pattern","closing_pattern","framework_usage",
                        "bullet_style","questioning_style","content_to_text_balance",
                        "structural_habits"):
                val = qual.get(key)
                if not val: continue
                if isinstance(val, list):
                    val = "; ".join(str(v) for v in val)
                st.markdown(f"**{key.replace('_',' ').title()}**: {val}")

        # ---------- Sources + Clear ----------
        srcs = profile.get("sources") or []
        c_left, c_right = st.columns([3, 1])
        with c_left:
            if srcs:
                st.caption(f"Source decks: {', '.join(srcs)}")
        with c_right:
            if st.button("🗑 Clear profile", key="clear_style"):
                p = Path("style_profiles/current.json")
                if p.exists(): p.unlink()
                st.session_state["style_profile"] = None
                st.rerun()

        with st.expander("⚙️ Raw profile JSON (advanced)"):
            st.code(json.dumps(profile, indent=2, ensure_ascii=False), language="json")
    else:
        st.info("Upload past decks to extract your style.")

with tabs[3]:
    st.subheader("Stage 3 — Session outline")
    if st.session_state["style_profile"]: st.success("Style profile active.")
    syl_obj = None
    if st.session_state["syllabus"]:
        try: syl_obj = json.loads(st.session_state["syllabus"])
        except: syl_obj = None
    selected_session = None
    if syl_obj and syl_obj.get("sessions"):
        labels = [f"Week {s['week']}: {s['session_title']}" for s in syl_obj["sessions"]]
        pick = st.selectbox("Pick a syllabus session", ["custom"] + labels)
        if pick != "custom": selected_session = syl_obj["sessions"][labels.index(pick)]
    dt = selected_session.get("session_title","") if selected_session else ""
    do = "\n".join(selected_session.get("topics",[])) if selected_session else ""
    dm = syl_obj.get("module_area","analytics") if syl_obj else "analytics"

    # Default slide count from style profile
    default_slides = 25
    if st.session_state["style_profile"]:
        avg = (st.session_state["style_profile"].get("quantitative") or {}).get("avg_slides_per_lecture")
        if avg: default_slides = int(round(float(avg)))

    c1, c2 = st.columns([2, 1])
    with c1:
        topic = st.text_input("Session topic", value=dt)
        objectives = st.text_area("Learning objectives (one per line)", value=do, height=140)
        rough_notes = st.text_area("Rough notes (optional)", height=120)
    with c2:
        module = st.selectbox("Module area", MODULE_AREAS, index=MODULE_AREAS.index(dm) if dm in MODULE_AREAS else 0)
        duration = st.number_input("Duration (min)", min_value=30, max_value=180, value=90, step=15)
        # Audience level — controls technical depth, analogies, math, citations
        _audience_keys = list(AUDIENCE_LEVELS.keys())
        _audience_labels = {k: AUDIENCE_LEVELS[k][0] for k in _audience_keys}
        audience_level = st.selectbox(
            "🎚 Audience level",
            options=_audience_keys,
            format_func=lambda k: _audience_labels[k],
            index=_audience_keys.index("standard"),
            help="Intro = analogies + simple lines + no math. Standard = MBA default. Advanced = research citations + math + framework critique.",
        )
        use_examples = st.checkbox("Fetch recent real-world examples", value=True)
        latest_only = st.checkbox("📰 Latest cases only (last 6 mo.)", value=False,
            help="When on, searches the last 6 months only — best for fast-moving topics like AI, tech, current macro. Default is 18 months.")
        st.markdown("**Deck content**")
        target_slides = st.number_input("Target slide count", min_value=10, max_value=80, value=default_slides, step=1)
        include_code = st.checkbox("Include code (Step 1/2/3)", value=False)
        include_homework = st.checkbox("Include homework", value=False)
        include_activity = st.checkbox("Include in-class activity (10-min warm-up)", value=False,
            help="AI picks an Excel simulation (for stats/data tasks) or a real web tool (for visual exploration). You'll get an .xlsx to hand out when Excel is chosen.")

    # ----- 🧠 Course memory section -----
    _all_mem_detailed = list_all_memory()  # only on-disk detailed entries
    _current_week = (selected_session or {}).get("week") if selected_session else None
    _prior_mem = []
    if _current_week:
        # Use the syllabus-aware loader: every prior week gets memory,
        # detailed if outline was generated, otherwise from syllabus topics.
        _prior_mem = load_prior_memory_with_syllabus(int(_current_week), syl_obj)

    n_detailed_in_prior = sum(1 for m in _prior_mem if not m.get("from_syllabus_only"))
    n_syllabus_in_prior = sum(1 for m in _prior_mem if m.get("from_syllabus_only"))

    # Show memory summary
    if _prior_mem:
        mem_col1, mem_col2 = st.columns([4, 1])
        with mem_col1:
            chips = []
            for m in _prior_mem:
                wk = m.get("week", "?")
                title = (m.get("session_title", "") or "")[:24]
                if m.get("from_syllabus_only"):
                    chips.append(
                        f"<span style='background:#fef3c7;color:#92400e;border-radius:6px;padding:2px 8px;font-size:10pt;margin:0 2px;'>"
                        f"📋 W{wk} {title}</span>"
                    )
                else:
                    chips.append(
                        f"<span style='background:#d1fae5;color:#065f46;border-radius:6px;padding:2px 8px;font-size:10pt;margin:0 2px;'>"
                        f"✅ W{wk} {title}</span>"
                    )
            chips_html = " ".join(chips)
            st.markdown(
                f"<div style='background:#f0fdfa;border-left:3px solid #0d9488;border-radius:8px;"
                f"padding:10px 14px;margin:8px 0;font-size:11pt;'>"
                f"🧠 <b>Course memory for Week {_current_week}</b>: "
                f"{n_detailed_in_prior} detailed · {n_syllabus_in_prior} from syllabus<br>"
                f"<div style='margin-top:6px;'>{chips_html}</div>"
                f"</div>", unsafe_allow_html=True
            )
        with mem_col2:
            if _all_mem_detailed and st.button("🗑 Clear detailed", key="clear_memory_btn",
                                                help="Remove all saved per-week detailed memory. Syllabus-based memory is unaffected (it always comes from Stage 1)."):
                n = clear_memory()
                st.success(f"Cleared {n} detailed memory file(s).")
                st.rerun()

    include_recap = st.checkbox(
        "🔁 Insert recap slides at start",
        value=bool(_prior_mem),
        disabled=not _prior_mem,
        help="When on, AI inserts 2-3 'Quick Recap of Last Week' slides at the start of this session. Uses any prior memory (✅ detailed or 📋 from syllabus).",
    )
    if not _prior_mem and _current_week == 1:
        st.caption("ℹ️ This is Week 1 — no prior content to recap.")
    elif not _prior_mem and _current_week and _current_week > 1:
        st.caption("⚠️ No syllabus loaded — generate one in Stage 1 to unlock memory for prior weeks.")

    _can_build = _auth.can_build()
    _gen_label = "Generate outline" if _can_build else "Generate outline (quota reached)"
    if st.button(_gen_label, type="primary", key="gen_outline", disabled=not _can_build):
        if not topic or not objectives.strip(): st.error("Topic and objectives required.")
        elif not _auth.can_build():
            st.error("⚠️ You've used all your decks for this beta. Email **dvora5018@gmail.com** to request more.")
        else:
            with st.spinner("Fetching examples..."):
                examples = fetch_recent_examples(topic, days=(180 if latest_only else 540)) if use_examples else []
                st.session_state["examples"] = examples
            with st.spinner("Drafting outline (style-aware, memory-aware)..."):
                obj_list = [o.strip() for o in objectives.splitlines() if o.strip()]
                outline_json = generate_outline(
                    topic=topic, objectives=obj_list, rough_notes=rough_notes,
                    module=module, duration_minutes=duration,
                    recent_examples=examples,
                    style_profile=st.session_state["style_profile"],
                    target_slides=int(target_slides),
                    include_code=bool(include_code),
                    include_homework=bool(include_homework),
                    include_activity=bool(include_activity),
                    prior_memory=_prior_mem,
                    include_recap=bool(include_recap),
                    audience_level=audience_level,
                )
                st.session_state["outline"] = outline_json
                # Auto-save memory for THIS session (only if we know which week it is)
                if _current_week:
                    try:
                        with st.spinner("Saving session to course memory..."):
                            mem = extract_session_memory(outline_json)
                            save_session_memory(int(_current_week), topic, mem)
                            st.toast(f"🧠 Saved Week {_current_week} to course memory", icon="💾")
                    except Exception as e:
                        st.warning(f"Memory save skipped: {e}")
                st.session_state["outline_inputs"] = {
                    "topic":topic,"objectives":obj_list,"rough_notes":rough_notes,
                    "module":module,"duration":duration,"examples":examples,
                    "target_slides":int(target_slides),
                    "include_code":bool(include_code),
                    "include_homework":bool(include_homework),
                    "include_activity":bool(include_activity),
                    "audience_level":audience_level,
                }
                # Count this toward the user's quota (one outline = one deck)
                _new_total = _auth.consume_deck()
                _rem = _auth.remaining_decks()
                if _rem == 0:
                    st.warning(f"⚠️ This was your final deck ({_new_total}/{_auth.get_max_decks()}). "
                               f"Email dvora5018@gmail.com to extend your quota.")
    if st.session_state["outline"]:
        # ---------- Helpers for line marker <-> object conversion ----------
        def _line_to_marker(line):
            if isinstance(line, str): return line
            if not isinstance(line, dict): return str(line)
            text = line.get("text", "")
            if line.get("red"): return f"!!{text}!!"
            if line.get("bold"): return f"**{text}**"
            if line.get("small"): return f"_{text}_"
            return text

        def _marker_to_line(s):
            s = s.strip()
            if not s: return None
            if s.startswith("!!") and s.endswith("!!") and len(s) > 4:
                return {"text": s[2:-2], "red": True}
            if s.startswith("**") and s.endswith("**") and len(s) > 4:
                return {"text": s[2:-2], "bold": True}
            if s.startswith("_") and s.endswith("_") and len(s) > 2:
                return {"text": s[1:-1], "small": True}
            return s

        def _save_outline_dict(d):
            st.session_state["outline"] = json.dumps(d, indent=2, ensure_ascii=False)

        # --- Parse outline ---
        try:
            _outline_dict = json.loads(st.session_state["outline"])
        except Exception:
            _outline_dict = None

        if _outline_dict:
            _slides = _outline_dict.get("slides", [])
            st.markdown(f"### {_outline_dict.get('session_title', '(untitled)')} "
                        f"· {_outline_dict.get('duration_minutes', 90)} min "
                        f"· {len(_slides)} slides")

            _icons = {"title":"🏷️","question":"❓","concept":"📝","example":"🏢",
                      "image":"🖼️","code":"💻","exercise":"🔧","discussion":"💬","summary":"✨"}
            SLIDE_TYPES = ["concept","question","example","image","code","exercise","discussion","summary"]

            # ---------- Session-level fields (editable) ----------
            with st.expander("🏷️ Session title · duration · learning objectives", expanded=False):
                new_sess_title = st.text_input("Session title", value=_outline_dict.get("session_title",""), key="sess_title")
                new_duration = st.number_input("Duration (min)", value=int(_outline_dict.get("duration_minutes", 90)), min_value=15, max_value=240, step=15, key="sess_dur")
                objs_text = "\n".join(_outline_dict.get("learning_objectives", []))
                new_objs = st.text_area("Learning objectives (one per line)", value=objs_text, height=140, key="sess_objs")
                if st.button("Save session fields", key="save_session_fields"):
                    _outline_dict["session_title"] = new_sess_title
                    _outline_dict["duration_minutes"] = int(new_duration)
                    _outline_dict["learning_objectives"] = [o.strip() for o in new_objs.splitlines() if o.strip()]
                    _save_outline_dict(_outline_dict)
                    st.success("Session fields saved.")
                    st.rerun()

            # ---------- Per-slide cards (preview + edit toggle) ----------
            st.caption("💡 Each slide card can be switched to Edit mode. Use markers in the Lines box: `**bold**`, `_small_`, `!!red!!`.")

            for i, s in enumerate(_slides):
                stype = (s.get("type") or "concept").lower()
                icon = _icons.get(stype, "•")
                title = s.get("title", "(untitled)")
                edit_key = f"edit_slide_{i}"
                st.session_state.setdefault(edit_key, False)

                with st.expander(f"{icon} Slide {i+1}: {title}  — _{stype}_", expanded=False):
                    if st.session_state[edit_key]:
                        # ========== EDIT MODE ==========
                        new_title = st.text_input("Title", value=s.get("title",""), key=f"t_{i}")
                        new_type = st.selectbox("Type", SLIDE_TYPES,
                                                index=SLIDE_TYPES.index(stype) if stype in SLIDE_TYPES else 0,
                                                key=f"ty_{i}")

                        lines_text = "\n".join(_line_to_marker(l) for l in (s.get("lines") or []))
                        new_lines_text = st.text_area(
                            "Lines (one per row — use `**bold**`, `_small_`, `!!red!!`)",
                            value=lines_text, height=160, key=f"lines_{i}",
                        )

                        new_kt = st.text_input("Key takeaway (red 30pt) — optional",
                                               value=s.get("key_takeaway",""), key=f"kt_{i}")

                        new_hint = None
                        new_code_obj = None
                        if new_type == "image":
                            new_hint = st.text_input("Image hint (what to draw)",
                                                    value=s.get("image_hint",""), key=f"ih_{i}")
                        elif new_type == "code":
                            code_obj = s.get("code") or {}
                            new_lang = st.text_input("Language", value=code_obj.get("language","python"), key=f"cl_{i}")
                            new_caption = st.text_input("Caption (optional)", value=code_obj.get("caption",""), key=f"cc_{i}")
                            st.markdown("**Code steps** (each step becomes its own slide):")
                            steps = code_obj.get("steps") or []
                            new_steps = []
                            for j, step in enumerate(steps):
                                st.markdown(f"— *Step {j+1}* —")
                                sd = st.text_input("Description", value=step.get("description",""), key=f"sd_{i}_{j}")
                                sc = st.text_area("Code", value=step.get("code",""), height=140, key=f"sc_{i}_{j}")
                                se = st.text_area("Explanation", value=step.get("explanation",""), height=80, key=f"se_{i}_{j}")
                                new_steps.append({"description": sd, "code": sc, "explanation": se})
                            new_code_obj = {"language": new_lang, "caption": new_caption, "steps": new_steps}

                        c_save, c_cancel, c_delete = st.columns([1,1,1])
                        if c_save.button("💾 Save", type="primary", key=f"save_{i}"):
                            updated = {"type": new_type, "title": new_title}
                            parsed = [_marker_to_line(l) for l in new_lines_text.split("\n")]
                            updated["lines"] = [l for l in parsed if l is not None]
                            if new_kt.strip():
                                updated["key_takeaway"] = new_kt.strip()
                            if new_type == "image" and new_hint is not None:
                                updated["image_hint"] = new_hint
                            if new_type == "code" and new_code_obj is not None:
                                updated["code"] = new_code_obj
                            _slides[i] = updated
                            _outline_dict["slides"] = _slides
                            _save_outline_dict(_outline_dict)
                            st.session_state[edit_key] = False
                            st.success(f"Slide {i+1} saved.")
                            st.rerun()
                        if c_cancel.button("Cancel", key=f"cancel_{i}"):
                            st.session_state[edit_key] = False
                            st.rerun()
                        if c_delete.button("🗑️ Delete slide", key=f"del_{i}"):
                            del _slides[i]
                            _outline_dict["slides"] = _slides
                            _save_outline_dict(_outline_dict)
                            st.session_state[edit_key] = False
                            st.warning(f"Slide {i+1} deleted.")
                            st.rerun()

                    else:
                        # ========== PREVIEW MODE ==========
                        for line in (s.get("lines") or []):
                            if isinstance(line, dict):
                                text = line.get("text","")
                                if line.get("red"):
                                    st.markdown(f"<span style='color:#0d9488; font-weight:bold;'>{text}</span>", unsafe_allow_html=True)
                                elif line.get("bold"):
                                    st.markdown(f"**{text}**")
                                elif line.get("small"):
                                    st.markdown(f"<span style='color:#666; font-size:0.9em;'>{text}</span>", unsafe_allow_html=True)
                                else:
                                    st.markdown(text)
                            else:
                                st.markdown(str(line))
                        if s.get("key_takeaway"):
                            st.markdown(
                                f"<div style='margin-top:10px; padding:10px; border-left:4px solid #0d9488; "
                                f"color:#0d9488; font-weight:bold; font-size:1.1em;'>{s['key_takeaway']}</div>",
                                unsafe_allow_html=True,
                            )
                        if s.get("image_hint"):
                            st.markdown(f"*🖼️ Diagram hint: {s['image_hint']}*")
                        if stype == "code":
                            code_obj = s.get("code") or {}
                            lang = code_obj.get("language","python")
                            if code_obj.get("caption"):
                                st.caption(code_obj["caption"])
                            for step_idx, step in enumerate(code_obj.get("steps") or [], 1):
                                st.markdown(f"**{step.get('description', f'Step {step_idx}')}**")
                                if step.get("code"):
                                    st.code(step["code"], language=lang)
                                if step.get("explanation"):
                                    st.markdown(f"*{step['explanation']}*")

                        if st.button("✏️ Edit this slide", key=f"btn_edit_{i}"):
                            st.session_state[edit_key] = True
                            st.rerun()

            # ---------- Homework preview ----------
            if _outline_dict.get("homework"):
                hw = _outline_dict["homework"]
                with st.expander(f"📚 Homework: {hw.get('title', 'Assignment')}", expanded=False):
                    if hw.get("problem_statement"):
                        st.markdown(f"**Problem:** {hw['problem_statement']}")
                    ds = hw.get("dataset") or {}
                    if ds:
                        st.markdown(f"**Dataset:** {ds.get('description','')}")
                        if ds.get("source"): st.caption(f"Source: {ds['source']}")
                        if ds.get("columns"): st.caption(f"Columns: {', '.join(ds['columns'])}")
                    if hw.get("deliverables"):
                        st.markdown("**Deliverables:**")
                        for d in hw["deliverables"]: st.markdown(f"- {d}")
                    if hw.get("hints"):
                        st.markdown("**Hints:**")
                        for h in hw["hints"]: st.markdown(f"- {h}")
                    if hw.get("grading_rubric"):
                        st.markdown(f"**Grading:** {hw['grading_rubric']}")

        # --- AI evaluation: single-outline review ---
        st.markdown("---")
        st.markdown("### 🔬 AI evaluation")
        eval_col1, eval_col2 = st.columns([3, 2])
        with eval_col1:
            st.caption("Grade this outline on 6 dimensions: structure, style match, depth, engagement, specificity, code quality.")
        with eval_col2:
            if st.button("🔬 Evaluate this outline", key="eval_outline", use_container_width=True):
                with st.spinner("Grading outline..."):
                    try:
                        st.session_state["last_eval"] = evaluate_outline(
                            st.session_state["outline"],
                            st.session_state.get("style_profile"),
                        )
                    except Exception as e:
                        st.error(f"Evaluation failed: {e}")
                        st.session_state["last_eval"] = None

        if st.session_state.get("last_eval"):
            e = st.session_state["last_eval"]
            score = e.get("overall_score", 0)
            score_color = "#0d9488" if score >= 8 else ("#d97706" if score >= 6 else "#dc2626")
            st.markdown(
                f"<div style='background:#f0fdfa;border:1px solid #99f6e4;border-radius:14px;"
                f"padding:20px 24px;margin:16px 0;'>"
                f"<div style='display:flex;align-items:baseline;gap:14px;'>"
                f"<div style='font-size:40pt;font-weight:700;color:{score_color};line-height:1;'>{score}</div>"
                f"<div style='font-size:14pt;color:#888;'>/10</div>"
                f"</div>"
                f"<div style='margin-top:8px;font-size:12pt;color:#0f172a;'>{e.get('verdict','')}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

            sc1, sc2 = st.columns(2)
            with sc1:
                st.markdown("**Dimensional scores**")
                for dim, val in (e.get("scores") or {}).items():
                    if val is None:
                        continue
                    st.progress(int(val) / 10, text=f"{dim.replace('_',' ').title()}: {val}/10")
            with sc2:
                if e.get("strengths"):
                    st.markdown("**✓ Strengths**")
                    for s in e["strengths"]:
                        st.markdown(f"- {s}")
                if e.get("weaknesses"):
                    st.markdown("**△ Weaknesses**")
                    for w in e["weaknesses"]:
                        st.markdown(f"- {w}")

        # --- Multi-version generation: compare alternatives ---
        st.markdown("---")
        st.markdown("### 🎯 Compare alternative versions")
        st.caption(
            "Generate 3 alternative outlines from different angles, evaluate each, "
            "and pick the highest-scoring one. Takes about 30 seconds."
        )
        # Alternatives = 3 outlines, costs 3 toward the quota
        _alt_remaining = _auth.remaining_decks()
        _alt_can = _auth.is_admin() or _alt_remaining >= 3
        _alt_label = ("🎯 Generate 3 alternatives & evaluate" if _alt_can
                      else f"🎯 Generate 3 alternatives (needs 3 quota, you have {_alt_remaining})")
        if st.button(_alt_label, key="gen_alts", disabled=not _alt_can):
            ins = st.session_state.get("outline_inputs")
            if not ins:
                st.error("Generate an initial outline first (we need topic + objectives).")
            elif not _alt_can:
                st.error("⚠️ Not enough quota for 3 alternatives. Email dvora5018@gmail.com for more.")
            else:
                # Pick the first 3 angles deterministically
                angle_items = list(VERSION_ANGLES.items())[:3]
                with st.spinner("Generating 3 outlines + 3 evaluations in parallel..."):
                    try:
                        # Stage 1: generate 3 outlines in parallel
                        with ThreadPoolExecutor(max_workers=3) as ex:
                            out_futures = {
                                ex.submit(
                                    generate_outline,
                                    topic=ins["topic"], objectives=ins["objectives"],
                                    rough_notes=ins["rough_notes"], module=ins["module"],
                                    duration_minutes=ins["duration"],
                                    recent_examples=ins.get("examples", []),
                                    style_profile=st.session_state["style_profile"],
                                    target_slides=ins.get("target_slides"),
                                    include_code=ins.get("include_code", False),
                                    include_homework=ins.get("include_homework", False),
                                    include_activity=ins.get("include_activity", False),
                                    audience_level=ins.get("audience_level", "standard"),
                                    version_angle=desc,
                                ): name
                                for name, desc in angle_items
                            }
                            outlines = {}
                            for fut in out_futures:
                                outlines[out_futures[fut]] = fut.result()

                        # Stage 2: evaluate each in parallel
                        with ThreadPoolExecutor(max_workers=3) as ex:
                            eval_futures = {
                                ex.submit(evaluate_outline, outlines[name], st.session_state["style_profile"]): name
                                for name in outlines
                            }
                            evaluations = {}
                            for fut in eval_futures:
                                evaluations[eval_futures[fut]] = fut.result()

                        st.session_state["alternatives"] = [
                            {"name": name, "outline": outlines[name], "eval": evaluations[name]}
                            for name, _ in angle_items
                        ]
                        # Count 3 toward the quota
                        for _ in range(3):
                            _auth.consume_deck()
                    except Exception as e:
                        st.error(f"Alternative generation failed: {e}")
                        st.session_state["alternatives"] = None

        if st.session_state.get("alternatives"):
            alts = st.session_state["alternatives"]
            best_idx = max(range(len(alts)), key=lambda i: alts[i]["eval"].get("overall_score", 0))

            cols = st.columns(len(alts))
            for i, (col, alt) in enumerate(zip(cols, alts)):
                with col:
                    name = alt["name"]
                    eval_ = alt["eval"]
                    score = eval_.get("overall_score", 0)
                    is_best = (i == best_idx)
                    badge = "🏆 Recommended" if is_best else ""
                    score_color = "#0d9488" if score >= 8 else ("#d97706" if score >= 6 else "#dc2626")
                    border = "border:2px solid #0d9488;" if is_best else "border:1px solid #e5e5e5;"

                    st.markdown(
                        f"<div style='{border}border-radius:14px;padding:18px;background:white;'>"
                        f"<div style='font-size:13pt;color:#888;font-weight:500;'>{name}</div>"
                        f"<div style='font-size:11pt;color:#0d9488;font-weight:600;'>{badge}&nbsp;</div>"
                        f"<div style='font-size:36pt;font-weight:700;color:{score_color};line-height:1;margin-top:8px;'>{score}<span style='font-size:14pt;color:#888;'>/10</span></div>"
                        f"<div style='font-size:10.5pt;color:#475569;margin-top:10px;line-height:1.5;'>{eval_.get('verdict','')}</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    with st.expander("Detail scores"):
                        for dim, val in (eval_.get("scores") or {}).items():
                            if val is None: continue
                            st.progress(int(val) / 10, text=f"{dim.replace('_',' ')}: {val}")
                    with st.expander("Strengths / Weaknesses"):
                        if eval_.get("strengths"):
                            st.markdown("**✓ Strengths**")
                            for s in eval_["strengths"]:
                                st.markdown(f"- {s}")
                        if eval_.get("weaknesses"):
                            st.markdown("**△ Weaknesses**")
                            for w in eval_["weaknesses"]:
                                st.markdown(f"- {w}")
                    if st.button(f"Use this version", key=f"use_alt_{i}",
                                 type="primary" if is_best else "secondary",
                                 use_container_width=True):
                        st.session_state["outline"] = alt["outline"]
                        st.session_state["last_eval"] = alt["eval"]
                        st.session_state["alternatives"] = None
                        st.success(f"Switched to '{name}' version.")
                        st.rerun()

        # --- Raw JSON (power users only) ---
        st.markdown("---")
        with st.expander("⚙️ Advanced — edit raw outline JSON", expanded=False):
            st.caption("For cases the visual editor can't handle (reordering slides, adding slides, etc.).")
            edited = st.text_area("Outline JSON", value=st.session_state["outline"], height=480, label_visibility="collapsed")
            if st.button("Save raw edits", key="save_outline"):
                st.session_state["outline"] = edited; st.success("Saved.")

with tabs[4]:
    st.subheader("Stage 4 — Deck (render only)")
    st.caption("Render the outline from Stage 3 as a deck. Pick image style and background, then build.")
    if not st.session_state["outline"]:
        st.info("Generate an outline in Stage 3 first.")
    else:
        cm, cc = st.columns([2, 1])
        with cm:
            out_name = st.text_input("Output filename (base)", value="deck",
                                     help="Extensions added automatically: .html, .pptx, .xlsx")
            st.caption("Tip: open the .html in Chrome. Press F for fullscreen, S for speaker notes.")
        with cc:
            st.markdown("**Options**")
            image_mode = st.radio(
                "Images for image-type slides:",
                options=["search", "svg", "skip"],
                format_func=lambda x: {
                    "search": "🔍 Web search (real photos)",
                    "svg":    "🎨 AI-generated SVG diagrams",
                    "skip":   "⏭ Skip — placeholders only (fastest)",
                }[x],
                index=0,
                help=("Web search — best for company logos, real charts, news photos. "
                      "AI-generated diagrams — best for abstract concepts (flow charts, models). "
                      "Skip — no images, fastest build."),
            )
            theme = st.selectbox(
                "Background theme:",
                options=list(THEMES.keys()),
                format_func=lambda k: THEMES[k]["label"],
                index=0,
                help=("Sets the deck's slide background. Per-type tints "
                      "(question / discussion / summary) layer on top automatically."),
            )
            gen_dataset = st.checkbox("Generate Excel dataset", value=False,
                help="Only runs if the outline has a homework field.")
            dataset_rows = st.number_input("Dataset rows", min_value=30, max_value=1000, value=150, step=10)

        # Preview: how many slides and whether homework/code are present
        try:
            _preview = json.loads(st.session_state["outline"])
            _slide_count = len(_preview.get("slides", []))
            _has_hw = bool(_preview.get("homework"))
            _has_code = any((s.get("type") or "").lower() == "code" for s in _preview.get("slides", []))
            st.caption(f"Outline contains **{_slide_count}** narrative slides · "
                       f"code: {'✓' if _has_code else '—'} · homework: {'✓' if _has_hw else '—'}")
        except Exception:
            pass

        col_html, col_pptx, col_pdf = st.columns(3)
        with col_html:
            if st.button("Build HTML deck", type="primary", key="build_html"):
                _spinner_label = {
                    "search": "Building deck (searching real images)...",
                    "svg":    "Building deck (generating diagrams)...",
                    "skip":   "Building deck...",
                }[image_mode]
                with st.spinner(_spinner_label):
                    path = build_html(st.session_state["outline"], f"output/{out_name}.html",
                                       image_mode=image_mode, theme=theme)
                    st.session_state["html_path"] = path
                    st.session_state["pdf_path"] = None
                    st.success(f"HTML saved → {path}")
                    # Quick image hit-rate diagnostic
                    if image_mode in ("search", "svg"):
                        try:
                            _outline_d = json.loads(st.session_state["outline"])
                            _img_slides = [s for s in (_outline_d.get("slides") or [])
                                           if (s.get("type") or "").lower() == "image"]
                            _n_total = len(_img_slides)
                            if _n_total:
                                _html_text = Path(path).read_text(encoding="utf-8")
                                if image_mode == "search":
                                    _n_hit = _html_text.count('class="img-wrapper"')
                                    label = "real images"
                                else:
                                    _n_hit = _html_text.count('class="svg-wrapper"')
                                    label = "AI diagrams"
                                _n_miss = _n_total - _n_hit
                                if _n_miss > 0:
                                    st.warning(
                                        f"⚠️ Got {_n_hit}/{_n_total} {label}. "
                                        f"{_n_miss} slide(s) fell back to a placeholder. "
                                        f"Try shorter / more specific image titles in Stage 3 to improve search hit rate."
                                    )
                                else:
                                    st.info(f"✓ All {_n_total} image slide(s) got {label}.")
                        except Exception:
                            pass
        with col_pptx:
            if st.button("Export as .pptx", key="export_pptx"):
                with st.spinner("Building .pptx from current outline..."):
                    path = export_pptx(st.session_state["outline"], f"output/{out_name}.pptx")
                    st.session_state["pptx_path"] = path
                    st.success(f"PPTX saved → {path}")
        with col_pdf:
            if st.button("Export as .pdf", key="export_pdf",
                         help="Renders the HTML via headless Chrome — exact visual match, 16:9 per page."):
                if not st.session_state.get("html_path") or not Path(st.session_state["html_path"]).exists():
                    st.error("Build HTML deck first (left button).")
                else:
                    with st.spinner("Rendering PDF via headless Chrome..."):
                        try:
                            pdf_out = str(Path(st.session_state["html_path"]).with_suffix(".pdf"))
                            path = export_html_to_pdf(st.session_state["html_path"], pdf_out)
                            st.session_state["pdf_path"] = path
                            st.success(f"PDF saved → {path}")
                        except Exception as e:
                            st.error(f"PDF export failed: {e}")

        # Dataset generation (always available if homework present)
        if gen_dataset:
            if st.button("Generate Excel dataset", key="gen_ds"):
                try:
                    outline_dict = json.loads(st.session_state["outline"])
                    hw = outline_dict.get("homework")
                    if not hw:
                        st.warning("No homework in the outline. Re-generate outline in Stage 3 with 'Include homework' on.")
                    else:
                        with st.spinner("Generating Excel dataset..."):
                            ds_path = generate_dataset(hw, f"output/{out_name}_dataset.xlsx", rows=int(dataset_rows))
                            st.session_state["dataset_path"] = ds_path
                            st.success(f"Dataset saved → {ds_path}")
                except Exception as e:
                    st.error(f"Dataset failed: {e}")

        # --- Activity Excel generation (if outline has an excel_simulation activity) ---
        try:
            _outline_dict = json.loads(st.session_state["outline"])
        except Exception:
            _outline_dict = None
        _activity = (_outline_dict or {}).get("activity") or {}
        if _activity.get("type") == "excel_simulation" and _activity.get("excel_spec"):
            st.markdown("---")
            st.markdown(f"**🎮 In-class activity:** {_activity.get('title', 'Warm-up')} "
                        f"· {_activity.get('duration_minutes', 10)} min · Excel simulation")
            if st.button("Generate activity Excel", key="gen_activity_xlsx"):
                try:
                    with st.spinner("Building activity .xlsx..."):
                        xlsx_path = f"output/{out_name}_activity.xlsx"
                        generate_activity_xlsx(_activity["excel_spec"], xlsx_path)
                        st.session_state["activity_path"] = xlsx_path
                        st.success(f"Activity saved → {xlsx_path}")
                except Exception as e:
                    st.error(f"Activity Excel failed: {e}")
        elif _activity.get("type") == "web_link":
            st.markdown("---")
            st.markdown(f"**🌐 In-class activity (web link):** {_activity.get('title', '')}")
            url = _activity.get("url", "")
            if url:
                st.markdown(f"[{_activity.get('source_name', url)}]({url})")
            st.caption(f"Duration: {_activity.get('duration_minutes', 10)} min · "
                       f"No Excel needed — students visit the link above.")

        # Download buttons
        st.markdown("---")
        if st.session_state["html_path"] and Path(st.session_state["html_path"]).exists():
            with open(st.session_state["html_path"], "rb") as f:
                st.download_button("⬇ Download deck (.html)", f, file_name=Path(st.session_state["html_path"]).name, mime="text/html")
        if st.session_state.get("pptx_path") and Path(st.session_state["pptx_path"]).exists():
            with open(st.session_state["pptx_path"], "rb") as f:
                st.download_button("⬇ Download deck (.pptx)", f, file_name=Path(st.session_state["pptx_path"]).name,
                                   mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")
        if st.session_state["dataset_path"] and Path(st.session_state["dataset_path"]).exists():
            with open(st.session_state["dataset_path"], "rb") as f:
                st.download_button("⬇ Download dataset (.xlsx)", f, file_name=Path(st.session_state["dataset_path"]).name)
        if st.session_state.get("activity_path") and Path(st.session_state["activity_path"]).exists():
            with open(st.session_state["activity_path"], "rb") as f:
                st.download_button("⬇ Download activity (.xlsx)", f, file_name=Path(st.session_state["activity_path"]).name)
        if st.session_state.get("pdf_path") and Path(st.session_state["pdf_path"]).exists():
            with open(st.session_state["pdf_path"], "rb") as f:
                st.download_button("⬇ Download deck (.pdf)", f, file_name=Path(st.session_state["pdf_path"]).name, mime="application/pdf")

        # ---------- Multi-version HTML build (uses Stage 3 alternatives) ----------
        if st.session_state.get("alternatives"):
            st.markdown("---")
            st.markdown("### 🎬 Build alternative versions as HTML")
            st.caption(
                "You generated 3 alternative outlines in Stage 3. Build all 3 as HTML in parallel, "
                "open each in a browser to compare visually, then promote your favorite to the main outline "
                "(so you can export it as PPTX/PDF above)."
            )
            if st.button("Build all alternatives as HTML", key="build_alt_htmls"):
                alts = st.session_state["alternatives"]
                base = Path(out_name).stem
                _spinner_label = {
                    "search": "Building 3 HTMLs (searching real images)...",
                    "svg":    "Building 3 HTMLs (generating SVG diagrams)...",
                    "skip":   "Building 3 HTMLs (no image fetch)...",
                }[image_mode]
                with st.spinner(_spinner_label):
                    out_paths = {}
                    safe_names = []
                    with ThreadPoolExecutor(max_workers=3) as ex:
                        future_to_name = {}
                        for alt in alts:
                            safe = alt["name"].lower().replace(" ", "_").replace("-", "_").replace("/", "_")
                            safe_names.append(safe)
                            path_target = f"output/{base}_{safe}.html"
                            fut = ex.submit(build_html, alt["outline"], path_target, image_mode, theme)
                            future_to_name[fut] = alt["name"]
                        for fut in future_to_name:
                            try:
                                out_paths[future_to_name[fut]] = fut.result()
                            except Exception as e:
                                st.error(f"{future_to_name[fut]} failed: {e}")
                    st.session_state["alt_html_paths"] = out_paths
                    st.success(f"Built {len(out_paths)} HTML files.")

            # Show 3 alternative HTML cards side-by-side
            if st.session_state.get("alt_html_paths"):
                paths = st.session_state["alt_html_paths"]
                alts = st.session_state["alternatives"]
                cols = st.columns(len(paths))
                for i, (col, alt) in enumerate(zip(cols, alts)):
                    name = alt["name"]
                    score = alt["eval"].get("overall_score", 0)
                    path = paths.get(name)
                    if not path or not Path(path).exists():
                        continue
                    with col:
                        st.markdown(f"**{name}**")
                        st.markdown(
                            f"<div style='font-size:24pt;font-weight:700;color:#0d9488;line-height:1;'>{score}<span style='font-size:11pt;color:#888;'>/10</span></div>",
                            unsafe_allow_html=True,
                        )
                        with open(path, "rb") as f:
                            st.download_button(
                                "⬇ Download HTML",
                                f,
                                file_name=Path(path).name,
                                mime="text/html",
                                key=f"dl_alt_html_{i}",
                                use_container_width=True,
                            )
                        if st.button("👉 Promote to main outline",
                                     key=f"promote_alt_{i}",
                                     use_container_width=True,
                                     help="Set this version as the active outline so you can export it as PPTX/PDF above."):
                            st.session_state["outline"] = alt["outline"]
                            st.session_state["html_path"] = path
                            st.session_state["last_eval"] = alt["eval"]
                            st.session_state["pdf_path"] = None  # invalidate
                            st.session_state["pptx_path"] = None
                            st.success(f"Promoted '{name}' → it's now the active outline.")
                            st.rerun()

# ---------- Stage 5: Session preview video ----------
with tabs[5]:
    st.subheader("Stage 5 — 🎬 Session preview video")
    st.caption(
        "Generate a 60-90 second teaser video for the session you built in Stage 4. "
        "The script references the actual cases, frameworks, and homework from your outline — "
        "students see a real preview, not a generic course pitch. "
        "Use the video to introduce the session to your students before class — on Canvas, in an email, or on your course homepage."
    )

    if not st.session_state.get("outline"):
        st.info("⚠️ Generate an outline in Stage 3 (and ideally build the deck in Stage 4) first — the video previews this specific session.")
    else:
        try:
            _outline_obj = json.loads(st.session_state["outline"])
        except Exception:
            _outline_obj = {}

        _slides = _outline_obj.get("slides") or []
        _has_code = any((s.get("type") or "").lower() == "code" for s in _slides)
        _has_hw = bool(_outline_obj.get("homework"))

        # Show what the video will draw on
        st.markdown(
            f"<div style='background:#f0fdfa;border-left:4px solid #0d9488;border-radius:8px;"
            f"padding:14px 18px;margin:12px 0;'>"
            f"<div style='font-size:10pt;color:#0d9488;font-weight:700;letter-spacing:1px;text-transform:uppercase;'>Source — this session's outline</div>"
            f"<div style='margin-top:6px;font-size:14pt;color:#0f172a;font-weight:600;'>🎓 {_outline_obj.get('session_title', '(no title)')}</div>"
            f"<div style='font-size:11pt;color:#475569;margin-top:4px;'>"
            f"{_outline_obj.get('duration_minutes', '?')} min class · "
            f"{len(_slides)} slides · "
            f"{len(_outline_obj.get('learning_objectives', []))} learning objectives · "
            f"code: {'✓' if _has_code else '—'} · "
            f"homework: {'✓' if _has_hw else '—'}"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        v_col1, v_col2 = st.columns([1, 1])
        with v_col1:
            video_duration = st.select_slider(
                "Target duration",
                options=[60, 75, 90, 120],
                value=90,
                format_func=lambda x: f"{x}s",
                key="video_duration",
            )
        with v_col2:
            st.markdown(
                "<div style='font-size:11pt;color:#666;margin-top:24px;'>"
                "Voice: <b>Alice</b> · Engaging Educator"
                "</div>",
                unsafe_allow_html=True,
            )


        if st.button("🎬 Generate preview video", type="primary", key="gen_intro_video"):
            sess_title = _outline_obj.get("session_title", "Session")
            with st.spinner(
                f"Building {video_duration}s preview video — this takes 1-2 minutes... "
                "(this takes ~60-90 seconds total)"
            ):
                try:
                    from pipeline.video_generator import generate_intro_video
                    safe_name = sess_title.lower().replace(" ", "_").replace("/", "_").replace(":", "")[:40]
                    out_path = f"output/preview_{safe_name}.mp4"
                    meta = generate_intro_video(
                        outline_json=st.session_state["outline"],
                        output_path=out_path,
                        duration_seconds=int(video_duration),
                    )
                    st.session_state["intro_video_path"] = meta["path"]
                    st.session_state["intro_video_meta"] = meta
                    st.success(
                        f"✓ Video saved → {meta['path']} · "
                        f"{meta['duration_seconds']:.0f}s · {meta['scene_count']} scenes · "
                        f"{meta['image_hits']}/{meta['scene_count']} real images"
                    )
                except Exception as e:
                    st.error(f"Video generation failed: {e}")

        # Inline preview + download
        if (st.session_state.get("intro_video_path")
                and Path(st.session_state["intro_video_path"]).exists()):
            st.markdown("---")
            v_path = st.session_state["intro_video_path"]
            meta = st.session_state.get("intro_video_meta") or {}
            if meta.get("title"):
                st.markdown(f"### 🎬 {meta['title']}")
            if meta.get("narration_preview"):
                st.markdown(
                    f"<div style='font-style:italic;color:#475569;background:#f8fafc;"
                    f"padding:12px 18px;border-radius:8px;border-left:3px solid #cbd5e1;"
                    f"margin:8px 0;'>“{meta['narration_preview']}”</div>",
                    unsafe_allow_html=True,
                )
            st.video(v_path)
            with open(v_path, "rb") as f:
                st.download_button(
                    "⬇ Download intro video (.mp4)",
                    f,
                    file_name=Path(v_path).name,
                    mime="video/mp4",
                )

# ---------- Stage 6: Student Study Guide ----------
with tabs[6]:
    st.subheader("Stage 6 — 🎓 Student Study Guide")
    st.caption(
        "A separate student-facing .html — interactive flash cards + multiple-choice quiz + key summary. "
        "Mobile-friendly, score saved locally per-device. Distribute to students via Canvas / email — "
        "they don't see your instructor deck or speaker notes."
    )

    if not st.session_state.get("outline"):
        st.info("⚠️ Generate an outline in Stage 3 first — the study guide draws on this session's actual content.")
    else:
        try:
            _outline_d = json.loads(st.session_state["outline"])
        except Exception:
            _outline_d = {}
        try:
            _syl_obj = json.loads(st.session_state.get("syllabus") or "{}")
        except Exception:
            _syl_obj = {}

        _slides = _outline_d.get("slides") or []

        # Show what the study guide will draw on
        st.markdown(
            f"<div style='background:#f0fdfa;border-left:4px solid #0d9488;border-radius:8px;"
            f"padding:14px 18px;margin:12px 0;'>"
            f"<div style='font-size:10pt;color:#0d9488;font-weight:700;letter-spacing:1px;text-transform:uppercase;'>Source — this session</div>"
            f"<div style='margin-top:6px;font-size:14pt;color:#0f172a;font-weight:600;'>🎓 {_outline_d.get('session_title', '(no title)')}</div>"
            f"<div style='font-size:11pt;color:#475569;margin-top:4px;'>"
            f"{_syl_obj.get('course_title', '(course unset)')} · "
            f"{len(_slides)} slides · "
            f"{len(_outline_d.get('learning_objectives', []))} learning objectives"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        sg_col1, sg_col2 = st.columns(2)
        with sg_col1:
            sg_n_cards = st.number_input(
                "🎴 Flash cards", min_value=4, max_value=20, value=8, step=1,
                key="sg_n_cards",
                help="Concept-definition or question-answer pairs. Students click to flip.",
            )
        with sg_col2:
            sg_n_quiz = st.number_input(
                "❓ Quiz questions", min_value=3, max_value=15, value=5, step=1,
                key="sg_n_quiz",
                help="Multiple-choice with instant feedback + explanation. Score saved in browser localStorage.",
            )


        if st.button("🎓 Generate Student Study Guide", type="primary", key="gen_study_guide"):
            sess_title = _outline_d.get("session_title", "Session")
            course_title = _syl_obj.get("course_title", "Course")
            safe_name = sess_title.lower().replace(" ", "_").replace(":", "").replace("/", "")[:40]
            sg_path = f"output/study_guide_{safe_name}.html"
            with st.spinner("Generating flash cards + quiz... about 10 seconds"):
                try:
                    meta = generate_study_guide(
                        outline_json=st.session_state["outline"],
                        course_title=course_title,
                        session_title=sess_title,
                        output_path=sg_path,
                        n_cards=int(sg_n_cards),
                        n_quiz=int(sg_n_quiz),
                    )
                    st.session_state["study_guide_path"] = meta["path"]
                    st.session_state["study_guide_meta"] = meta
                    st.success(
                        f"✓ Study guide saved → {meta['path']} · "
                        f"{meta['n_flash_cards']} cards · "
                        f"{meta['n_quiz_questions']} quiz Qs · "
                        f"{meta['n_summary_points']} summary points"
                    )
                except Exception as e:
                    st.error(f"Study guide failed: {e}")

        # Inline preview + download
        if (st.session_state.get("study_guide_path")
                and Path(st.session_state["study_guide_path"]).exists()):
            st.markdown("---")
            sg_path = st.session_state["study_guide_path"]
            meta = st.session_state.get("study_guide_meta") or {}
            st.markdown(
                f"<div style='display:flex;gap:18px;flex-wrap:wrap;margin:8px 0 16px 0;'>"
                f"<span style='background:#ecfdf5;color:#0f766e;border:1px solid #a7f3d0;border-radius:999px;padding:6px 14px;font-size:11pt;'>🎴 {meta.get('n_flash_cards','?')} cards</span>"
                f"<span style='background:#ecfdf5;color:#0f766e;border:1px solid #a7f3d0;border-radius:999px;padding:6px 14px;font-size:11pt;'>❓ {meta.get('n_quiz_questions','?')} quiz Qs</span>"
                f"<span style='background:#ecfdf5;color:#0f766e;border:1px solid #a7f3d0;border-radius:999px;padding:6px 14px;font-size:11pt;'>📝 {meta.get('n_summary_points','?')} summary points</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            with open(sg_path, "rb") as f:
                st.download_button(
                    "⬇ Download Student Study Guide (.html)",
                    f,
                    file_name=Path(sg_path).name,
                    mime="text/html",
                )
            st.caption(
                f"📁 Saved to `{sg_path}` — open in a browser to preview before sending to students. "
                "Upload to Canvas / Blackboard, or attach to your weekly email."
            )

# ---------- Footer ----------
st.markdown(
    '<div class="app-footer">SlideGen · AI course decks for business school instructors</div>',
    unsafe_allow_html=True
)

# ============================================================
#  💬 Floating AI Help Assistant (bottom-right corner)
#  Always available; uses Haiku 4.5 with a system prompt that
#  knows the app structure. ~$0.0002 per question.
# ============================================================
st.markdown("""
<style>
/* Pin the LAST popover on the page to the bottom-right corner.
   Using :last-of-type so the help button floats while other popovers
   on the page (if any) remain inline. */
section.main div[data-testid="stPopover"]:last-of-type,
[data-testid="stMain"] div[data-testid="stPopover"]:last-of-type {
  position: fixed !important;
  bottom: 22px;
  right: 22px;
  z-index: 999999;
  width: auto !important;
}
section.main div[data-testid="stPopover"]:last-of-type button,
[data-testid="stMain"] div[data-testid="stPopover"]:last-of-type button {
  border-radius: 999px !important;
  padding: 10px 22px !important;
  box-shadow: 0 8px 24px rgba(13,148,136,0.40) !important;
  background: #0d9488 !important;
  color: white !important;
  border: none !important;
  font-weight: 600 !important;
  font-size: 14px !important;
}
section.main div[data-testid="stPopover"]:last-of-type button:hover,
[data-testid="stMain"] div[data-testid="stPopover"]:last-of-type button:hover {
  background: #0f766e !important;
  transform: translateY(-1px);
  box-shadow: 0 12px 28px rgba(13,148,136,0.50) !important;
}
</style>
""", unsafe_allow_html=True)

if "help_chat" not in st.session_state:
    st.session_state["help_chat"] = []

with st.popover("💬 Help", use_container_width=False):
    st.markdown("**Ask me anything about how to use the app.**  \n"
                "_Quick guidance · 1-3 sentence answers._")

    # Chat history (scrollable container)
    chat_box = st.container(height=300, border=False)
    with chat_box:
        if not st.session_state["help_chat"]:
            st.caption("👋 Try: *How do I change the background?* · "
                       "*What's the difference between SVG and web search?* · "
                       "*How do students access the study guide?*")
        for msg in st.session_state["help_chat"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Input form (Enter submits, auto-clears)
    with st.form("help_form", clear_on_submit=True, border=False):
        col_q, col_btn = st.columns([5, 1])
        with col_q:
            q = st.text_input(
                "Question", placeholder="Ask a question...",
                label_visibility="collapsed", key="help_q",
            )
        with col_btn:
            submitted = st.form_submit_button("Ask")
        if submitted and q and q.strip():
            st.session_state["help_chat"].append({"role": "user", "content": q.strip()})
            try:
                from pipeline.help_assistant import ask as _help_ask
                with st.spinner("Thinking..."):
                    answer = _help_ask(st.session_state["help_chat"])
                st.session_state["help_chat"].append({"role": "assistant", "content": answer})
            except Exception as e:
                st.session_state["help_chat"].append(
                    {"role": "assistant",
                     "content": f"Sorry, I hit an error: `{e}`. Make sure ANTHROPIC_API_KEY is set in .env."}
                )
            st.rerun()

    if st.session_state["help_chat"]:
        if st.button("🗑 Clear conversation", key="clear_help_chat", type="tertiary"):
            st.session_state["help_chat"] = []
            st.rerun()
