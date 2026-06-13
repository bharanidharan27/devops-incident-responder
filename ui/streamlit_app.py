import json

import pandas as pd
import streamlit as st

from app.config import API_BASE_URL
from ui.api_client import IncidentApiClient, IncidentApiError


def api_client() -> IncidentApiClient:
    return IncidentApiClient(API_BASE_URL)


def stop_on_api_error(exc: IncidentApiError) -> None:
    st.error(f"API error: {exc}")
    st.stop()


NAV_ITEMS = [
    ("Dashboard", "dashboard", "space_dashboard"),
    ("Create Incident", "create", "bolt"),
    ("AI Providers", "providers", "memory"),
]

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap');

:root {
    --bg-base: #0a0b0e;
    --bg-elevated: #111317;
    --bg-elevated-2: #16191f;
    --bg-elevated-3: #1c2027;
    --border: #23272f;
    --border-bright: #353a44;
    --border-accent: #ff5a3c33;
    --text-primary: #e8eaed;
    --text-secondary: #9097a3;
    --text-muted: #5b6068;
    --accent: #ff5a3c;
    --accent-dim: rgba(255, 90, 60, 0.12);
    --accent-glow: rgba(255, 90, 60, 0.25);
    --sev-critical: #ff3344;
    --sev-high: #ff8a00;
    --sev-medium: #f5c518;
    --sev-low: #4cc9f0;
    --status-open: #ff8a00;
    --status-running: #4cc9f0;
    --status-resolved: #3ddc97;
    --status-failed: #ff3344;
}

/* ---------- Global canvas ---------- */
html, body, [class*="css"], .stApp {
    font-family: 'Geist', -apple-system, BlinkMacSystemFont, sans-serif;
    color: var(--text-primary);
}

.stApp {
    background:
        radial-gradient(1200px 600px at 100% -10%, rgba(255, 90, 60, 0.07), transparent 60%),
        radial-gradient(900px 500px at -10% 110%, rgba(76, 201, 240, 0.04), transparent 60%),
        var(--bg-base);
}

/* hide streamlit default chrome, but KEEP the header so sidebar toggle stays clickable */
#MainMenu, footer {visibility: hidden; height: 0;}
header[data-testid="stHeader"] {
    background: transparent;
    height: 2.6rem;
}
header[data-testid="stHeader"] [data-testid="stToolbar"],
header[data-testid="stHeader"] [data-testid="stDecoration"],
header[data-testid="stHeader"] [data-testid="stStatusWidget"] {
    visibility: hidden;
}
/* re-expose only the sidebar collapse/expand buttons */
header[data-testid="stHeader"] [data-testid="stSidebarCollapseButton"],
header[data-testid="stHeader"] [data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"],
button[kind="headerNoPadding"] {
    visibility: visible !important;
    color: var(--text-secondary) !important;
}
.block-container {padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1600px;}

/* ---------- Typography ---------- */
h1, h2, h3, h4, h5 {
    font-family: 'Geist', sans-serif;
    font-weight: 600;
    letter-spacing: -0.02em;
    color: var(--text-primary);
}
h1 {font-size: 1.9rem; line-height: 1.1;}
h2 {font-size: 1.35rem;}
h3 {font-size: 1.1rem;}

p, span, label, div {color: var(--text-primary);}
.stCaption, [data-testid="stCaptionContainer"], .stMarkdown small {
    color: var(--text-muted);
    font-size: 0.78rem;
    letter-spacing: 0.01em;
}

code, pre, .stCode, [data-testid="stCodeBlock"], .mono {
    font-family: 'Geist Mono', ui-monospace, monospace !important;
}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0c0d11 0%, #08090c 100%);
    border-right: 1px solid var(--border);
}
section[data-testid="stSidebar"][aria-expanded="true"] {min-width: 250px;}
section[data-testid="stSidebar"] {position: relative;}
section[data-testid="stSidebar"] > div {padding-top: 0;}
section[data-testid="stSidebar"] .block-container {padding: 0.4rem 1rem 1.4rem 1rem;}
/* Collapse the native sidebar header — we'll float the toggle ourselves */
section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {
    height: 0 !important;
    min-height: 0 !important;
    padding: 0 !important;
    overflow: visible !important;
}
section[data-testid="stSidebar"] [data-testid="stLogoSpacer"] {display: none !important;}
/* Pin the collapse arrow to the top-right of the sidebar so it sits next to the brand */
section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] {
    position: absolute !important;
    top: 29px !important;
    right: 14px !important;
    left: auto !important;
    margin: 0 !important;
    z-index: 50;
    display: flex !important;
    align-items: center !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button {
    height: 30px !important; width: 30px !important;
    border-radius: 8px !important;
    background: transparent !important;
    color: var(--text-secondary) !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button:hover {
    background: var(--bg-elevated-2) !important;
    color: var(--text-primary) !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
    padding-top: 0.8rem !important;
}

.sidebar-brand {
    display: flex; align-items: center; gap: 0.65rem;
    padding: 0 2.4rem 1rem 0.4rem; /* right padding leaves room for the « toggle */
    border-bottom: 1px solid var(--border);
    margin-bottom: 1rem;
}
.sidebar-brand .logo-mark {
    width: 30px; height: 30px;
    border-radius: 7px;
    background: linear-gradient(135deg, #ff5a3c, #ff8a00);
    box-shadow: 0 0 0 1px rgba(255,138,0,0.3), 0 6px 20px rgba(255,90,60,0.25);
    display: flex; align-items: center; justify-content: center;
    font-family: 'Geist Mono', monospace; font-weight: 700; color: #0a0b0e;
    font-size: 0.8rem;
}
.sidebar-brand .brand-text {display: flex; flex-direction: column; line-height: 1.05;}
.sidebar-brand .brand-name {
    font-size: 0.85rem; font-weight: 600; letter-spacing: 0.02em;
    color: var(--text-primary);
}
.sidebar-brand .brand-sub {
    font-family: 'Geist Mono', monospace;
    font-size: 0.62rem; color: var(--text-muted);
    text-transform: uppercase; letter-spacing: 0.14em;
}

/* Sidebar nav buttons */
section[data-testid="stSidebar"] .stButton > button {
    background: transparent;
    color: var(--text-secondary);
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 0.55rem 0.75rem;
    font-weight: 500;
    font-size: 0.88rem;
    text-align: left;
    justify-content: flex-start;
    height: auto;
    transition: all 120ms ease;
    box-shadow: none;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: var(--bg-elevated-2);
    color: var(--text-primary);
    border-color: var(--border);
}
section[data-testid="stSidebar"] .stButton > button p {
    font-weight: 500; font-size: 0.88rem; margin: 0;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"],
section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
    background: var(--accent-dim) !important;
    color: #ffd5cc !important;
    border: 1px solid var(--border-accent) !important;
    box-shadow: inset 3px 0 0 var(--accent) !important;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"] p,
section[data-testid="stSidebar"] .stButton > button[kind="primary"] span {
    color: #ffd5cc !important;
    font-weight: 600;
}

/* ---------- Top bar / page header ---------- */
.page-header {
    display: flex; align-items: flex-end; justify-content: space-between;
    padding: 0 0 1.3rem 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 1.5rem;
}
.page-header .title-block {display: flex; flex-direction: column; gap: 0.25rem;}
.page-header h1 {margin: 0; font-size: 1.7rem;}
.page-header .eyebrow {
    font-family: 'Geist Mono', monospace;
    font-size: 0.68rem; color: var(--text-muted);
    text-transform: uppercase; letter-spacing: 0.18em;
}
.page-header .meta {
    font-family: 'Geist Mono', monospace;
    font-size: 0.72rem; color: var(--text-muted);
}
.page-header .meta .live-dot {
    display: inline-block; width: 6px; height: 6px; border-radius: 50%;
    background: var(--status-resolved); margin-right: 0.4rem;
    animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
    0%, 100% {opacity: 1;}
    50% {opacity: 0.4;}
}

/* ---------- Stat cards ---------- */
.stat-grid {display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.85rem; margin-bottom: 1.5rem;}
.stat-card {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 0.95rem 1.05rem;
    position: relative; overflow: hidden;
    transition: border-color 150ms ease;
}
.stat-card:hover {border-color: var(--border-bright);}
.stat-card .label {
    font-family: 'Geist Mono', monospace;
    font-size: 0.65rem; color: var(--text-muted);
    text-transform: uppercase; letter-spacing: 0.16em;
    margin-bottom: 0.45rem;
}
.stat-card .value {
    font-family: 'Geist', sans-serif;
    font-size: 1.7rem; font-weight: 600;
    color: var(--text-primary); letter-spacing: -0.02em;
    line-height: 1;
}
.stat-card .sub {
    font-family: 'Geist Mono', monospace;
    font-size: 0.7rem; color: var(--text-muted);
    margin-top: 0.4rem;
}
.stat-card.accent {border-color: var(--border-accent);}
.stat-card.accent .value {color: var(--accent);}
.stat-card .corner-dot {
    position: absolute; top: 12px; right: 12px;
    width: 6px; height: 6px; border-radius: 50%;
}
.stat-card.critical .corner-dot {background: var(--sev-critical); box-shadow: 0 0 8px var(--sev-critical);}
.stat-card.high .corner-dot {background: var(--sev-high);}
.stat-card.medium .corner-dot {background: var(--sev-medium);}
.stat-card.low .corner-dot {background: var(--sev-low);}

/* ---------- Section header (with accent rule) ---------- */
.section-head {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 0.7rem;
}
.section-head h2 {
    margin: 0; font-size: 0.95rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.14em;
    color: var(--text-secondary);
    display: flex; align-items: center; gap: 0.55rem;
}
.section-head h2::before {
    content: ""; display: inline-block;
    width: 3px; height: 14px; background: var(--accent); border-radius: 2px;
}
.section-head .right {
    font-family: 'Geist Mono', monospace; font-size: 0.7rem;
    color: var(--text-muted);
}

/* ---------- Incident HTML grid table ---------- */
.incident-table {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
}
.incident-row-head {
    display: grid;
    gap: 1rem;
    align-items: center;
    padding: 0.7rem 1.1rem;
    background: #0e1014;
    border-bottom: 1px solid var(--border);
    font-family: 'Geist Mono', monospace;
    font-size: 0.65rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.16em;
}
.incident-row-head > div {white-space: nowrap;}

.incident-row {
    display: grid;
    gap: 1rem;
    align-items: center;
    padding: 0.7rem 1.1rem;
    border-bottom: 1px solid var(--border);
    color: var(--text-secondary);
    font-size: 0.85rem;
    text-decoration: none !important;
    cursor: pointer;
    transition: background 120ms ease, color 120ms ease;
}
.incident-row:last-child {border-bottom: none;}
.incident-row:hover {
    background: var(--bg-elevated-2);
    color: var(--text-primary);
}
.incident-row.selected {
    background: var(--accent-dim);
    color: var(--text-primary);
    box-shadow: inset 3px 0 0 var(--accent);
}

.incident-row > div {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.incident-row .mono,
.incident-row-head .mono,
.incident-row .c-id,
.incident-row .c-created,
.incident-row .c-service {
    font-family: 'Geist Mono', monospace;
    font-size: 0.78rem;
}
.incident-row .c-id {color: var(--text-primary); font-weight: 600;}
.incident-row .muted {color: var(--text-muted);}
.incident-row .c-title {
    color: var(--text-primary);
    font-weight: 500;
}
.incident-row .c-sev {
    display: flex; align-items: center; gap: 0.45rem;
    font-family: 'Geist Mono', monospace;
    font-size: 0.74rem;
    font-weight: 600;
    letter-spacing: 0.06em;
}
.incident-row .sev-dot {font-size: 0.65rem; line-height: 1;}
.incident-row .c-sev.sev-critical {color: var(--sev-critical);}
.incident-row .c-sev.sev-high     {color: var(--sev-high);}
.incident-row .c-sev.sev-medium   {color: var(--sev-medium);}
.incident-row .c-sev.sev-low      {color: var(--sev-low);}

.row-pill {
    display: inline-flex; align-items: center;
    padding: 0.15rem 0.55rem;
    border-radius: 5px;
    font-family: 'Geist Mono', monospace;
    font-size: 0.66rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    border: 1px solid transparent;
}
.row-pill.open     {color: var(--status-open);     background: rgba(255,138,0,0.10); border-color: rgba(255,138,0,0.25);}
.row-pill.running  {color: var(--status-running);  background: rgba(76,201,240,0.10); border-color: rgba(76,201,240,0.25);}
.row-pill.resolved {color: var(--status-resolved); background: rgba(61,220,151,0.10); border-color: rgba(61,220,151,0.25);}
.row-pill.failed   {color: var(--status-failed);   background: rgba(255,51,68,0.10); border-color: rgba(255,51,68,0.25);}
.row-pill.neutral  {color: var(--text-secondary);  background: var(--bg-elevated-2); border-color: var(--border);}

/* ---------- Data table (legacy, kept for tab-internal tables) ---------- */
[data-testid="stDataFrame"] {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
}
[data-testid="stDataFrame"] [data-testid="stTable"] {background: transparent;}
[data-testid="stDataFrame"] .glideDataEditor {
    --gdg-bg-cell: var(--bg-elevated);
    --gdg-bg-cell-medium: var(--bg-elevated-2);
    --gdg-bg-header: #0e1014;
    --gdg-bg-header-has-focus: #14171c;
    --gdg-bg-header-hovered: #14171c;
    --gdg-text-header: var(--text-muted);
    --gdg-text-dark: var(--text-primary);
    --gdg-text-medium: var(--text-secondary);
    --gdg-text-light: var(--text-muted);
    --gdg-border-color: var(--border);
    --gdg-horizontal-border-color: var(--border);
    --gdg-accent-color: var(--accent);
    --gdg-accent-fg: #ffffff;
    --gdg-accent-light: rgba(255, 90, 60, 0.14);
    --gdg-cell-horizontal-padding: 12px;
    --gdg-cell-vertical-padding: 8px;
    --gdg-header-icon-size: 14px;
    --gdg-font-family: 'Geist', sans-serif;
    --gdg-base-font-style: 500 13px;
    --gdg-header-font-style: 600 11px;
    font-family: 'Geist', sans-serif;
}

/* ---------- Pills / badges ---------- */
.pill {
    display: inline-flex; align-items: center; gap: 0.4rem;
    padding: 0.25rem 0.65rem;
    border-radius: 999px;
    font-family: 'Geist Mono', monospace;
    font-size: 0.68rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.1em;
    border: 1px solid transparent;
}
.pill::before {content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor;}
.pill.critical {color: var(--sev-critical); background: rgba(255,51,68,0.08); border-color: rgba(255,51,68,0.25);}
.pill.high     {color: var(--sev-high);     background: rgba(255,138,0,0.08); border-color: rgba(255,138,0,0.25);}
.pill.medium   {color: var(--sev-medium);   background: rgba(245,197,24,0.08); border-color: rgba(245,197,24,0.25);}
.pill.low      {color: var(--sev-low);      background: rgba(76,201,240,0.08); border-color: rgba(76,201,240,0.25);}
.pill.open     {color: var(--status-open);     background: rgba(255,138,0,0.08); border-color: rgba(255,138,0,0.25);}
.pill.running  {color: var(--status-running);  background: rgba(76,201,240,0.08); border-color: rgba(76,201,240,0.25);}
.pill.resolved {color: var(--status-resolved); background: rgba(61,220,151,0.08); border-color: rgba(61,220,151,0.25);}
.pill.failed   {color: var(--status-failed);   background: rgba(255,51,68,0.08); border-color: rgba(255,51,68,0.25);}
.pill.neutral  {color: var(--text-secondary);  background: var(--bg-elevated-2); border-color: var(--border);}

/* ---------- Detail panel ---------- */
.detail-card {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.3rem 1.4rem;
    margin-bottom: 1rem;
    position: relative;
}
.detail-card::before {
    content: ""; position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, var(--accent), transparent);
    opacity: 0.4;
}
.detail-head {display: flex; flex-direction: column; gap: 0.7rem;}
.detail-id {
    font-family: 'Geist Mono', monospace;
    font-size: 0.7rem; color: var(--text-muted);
    text-transform: uppercase; letter-spacing: 0.16em;
}
.detail-title {
    font-size: 1.35rem; font-weight: 600; letter-spacing: -0.02em;
    color: var(--text-primary); line-height: 1.2;
}
.detail-meta-row {
    display: flex; flex-wrap: wrap; gap: 0.45rem; margin-top: 0.6rem;
}
.detail-info-grid {
    display: grid; grid-template-columns: repeat(2, 1fr);
    gap: 0.4rem 1.2rem;
    margin-top: 1rem;
    padding-top: 0.9rem;
    border-top: 1px dashed var(--border);
}
.detail-info-grid .k {
    font-family: 'Geist Mono', monospace; font-size: 0.65rem;
    color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.14em;
}
.detail-info-grid .v {
    font-family: 'Geist Mono', monospace; font-size: 0.8rem;
    color: var(--text-primary);
}

/* ---------- Tabs ---------- */
.stTabs [data-baseweb="tab-list"] {
    background: transparent;
    border-bottom: 1px solid var(--border);
    gap: 0.2rem;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--text-muted) !important;
    border: none !important;
    border-radius: 0;
    padding: 0.55rem 0.9rem;
    font-family: 'Geist Mono', monospace;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-weight: 600;
}
.stTabs [data-baseweb="tab"]:hover {color: var(--text-secondary) !important;}
.stTabs [aria-selected="true"] {
    color: var(--accent) !important;
    box-shadow: inset 0 -2px 0 var(--accent);
}

/* ---------- Generic buttons (outside sidebar) ---------- */
.stApp .stButton > button {
    background: var(--bg-elevated-2);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.5rem 0.95rem;
    font-weight: 500;
    font-size: 0.85rem;
    transition: all 120ms ease;
    box-shadow: none;
}
.stApp .stButton > button:hover {
    background: var(--bg-elevated-3);
    border-color: var(--border-bright);
}
.stApp .stButton > button[kind="primary"] {
    background: var(--accent);
    color: #0a0b0e;
    border-color: var(--accent);
    font-weight: 600;
}
.stApp .stButton > button[kind="primary"]:hover {
    background: #ff7355;
    box-shadow: 0 4px 18px rgba(255, 90, 60, 0.3);
}

/* Download buttons */
[data-testid="stDownloadButton"] > button {
    background: var(--bg-elevated-2);
    color: var(--text-secondary);
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: 0.78rem;
    font-family: 'Geist Mono', monospace;
}
[data-testid="stDownloadButton"] > button:hover {
    color: var(--text-primary);
    border-color: var(--border-bright);
}

/* ---------- Inputs ---------- */
.stTextInput input, .stTextArea textarea, .stSelectbox > div > div, .stNumberInput input {
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-primary) !important;
    border-radius: 8px !important;
    font-family: 'Geist', sans-serif;
    font-size: 0.88rem;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(255, 90, 60, 0.12) !important;
}
.stTextArea textarea {font-family: 'Geist Mono', monospace; font-size: 0.82rem;}
label, .stTextInput label, .stTextArea label, .stSelectbox label {
    color: var(--text-secondary) !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
}

/* ---------- Alerts / info boxes ---------- */
[data-testid="stAlert"] {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 10px;
    color: var(--text-secondary);
}

/* ---------- Markdown body ---------- */
.stMarkdown p {color: var(--text-secondary); line-height: 1.65;}
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {
    color: var(--text-primary);
}
.stMarkdown code {
    background: var(--bg-elevated-2);
    border: 1px solid var(--border);
    padding: 0.05rem 0.4rem;
    border-radius: 5px;
    font-size: 0.82em;
    color: var(--accent);
}
.stMarkdown pre {
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border);
    border-radius: 10px;
}

/* ---------- JSON viewer ---------- */
[data-testid="stJson"] {
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 0.6rem 0.9rem;
}

/* ---------- Spinner ---------- */
.stSpinner > div {border-top-color: var(--accent) !important;}

/* ---------- Form container ---------- */
[data-testid="stForm"] {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.4rem 1.5rem;
}

/* ---------- Scrollbar ---------- */
::-webkit-scrollbar {width: 10px; height: 10px;}
::-webkit-scrollbar-track {background: transparent;}
::-webkit-scrollbar-thumb {background: var(--border-bright); border-radius: 5px; border: 2px solid var(--bg-base);}
::-webkit-scrollbar-thumb:hover {background: #4a4f5a;}
</style>
"""


def inject_theme() -> None:
    st.markdown(THEME_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_payload(raw: str) -> dict:
    if not raw.strip():
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {"value": value}
    except json.JSONDecodeError as exc:
        st.error(f"Payload JSON is invalid: {exc}")
        st.stop()


def selected_rows(selection_event) -> list[int]:
    if selection_event is None:
        return []
    selection = getattr(selection_event, "selection", None)
    if selection is None and isinstance(selection_event, dict):
        selection = selection_event.get("selection")
    rows = getattr(selection, "rows", None)
    if rows is None and isinstance(selection, dict):
        rows = selection.get("rows")
    return list(rows or [])


def pill(text: str, kind: str) -> str:
    cls = kind.lower() if kind else "neutral"
    safe = (text or "").upper()
    return f'<span class="pill {cls}">{safe}</span>'


def severity_class(sev: str) -> str:
    return (sev or "").lower() if sev in {"CRITICAL", "HIGH", "MEDIUM", "LOW"} else "neutral"


def status_class(status: str) -> str:
    s = (status or "").upper()
    if s == "OPEN":
        return "open"
    if s == "RUNNING":
        return "running"
    if s in {"RESOLVED", "DONE", "CLOSED"}:
        return "resolved"
    if s == "FAILED":
        return "failed"
    return "neutral"


def page_header(eyebrow: str, title: str, meta: str | None = None) -> None:
    meta_html = ""
    if meta:
        meta_html = f'<div class="meta"><span class="live-dot"></span>{meta}</div>'
    st.markdown(
        f"""
        <div class="page-header">
            <div class="title-block">
                <div class="eyebrow">{eyebrow}</div>
                <h1>{title}</h1>
            </div>
            {meta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_head(title: str, right: str = "") -> None:
    right_html = f'<div class="right">{right}</div>' if right else ""
    st.markdown(
        f'<div class="section-head"><h2>{title}</h2>{right_html}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar() -> str:
    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-brand">
                <div class="logo-mark">IR</div>
                <div class="brand-text">
                    <span class="brand-name">Incident Responder</span>
                    <span class="brand-sub">OPS · CONSOLE</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        current = st.session_state.get("nav_key", "dashboard")
        for label, key, icon in NAV_ITEMS:
            btn_type = "primary" if current == key else "tertiary"
            if st.button(
                f":material/{icon}: {label}",
                key=f"nav_btn_{key}",
                type=btn_type,
                use_container_width=True,
            ):
                st.session_state["nav_key"] = key
                st.session_state["selected_incident_id"] = None
                if "incident_id" in st.query_params:
                    del st.query_params["incident_id"]
                st.rerun()

    return st.session_state.get("nav_key", "dashboard")


# ---------------------------------------------------------------------------
# Dashboard – stat cards
# ---------------------------------------------------------------------------

def render_stat_cards(incidents: list[dict]) -> None:
    total = len(incidents)
    open_count = sum(1 for i in incidents if (i.get("status") or "").upper() == "OPEN")
    critical = sum(1 for i in incidents if (i.get("severity") or "").upper() == "CRITICAL")
    high = sum(1 for i in incidents if (i.get("severity") or "").upper() == "HIGH")

    st.markdown(
        f"""
        <div class="stat-grid">
            <div class="stat-card">
                <div class="corner-dot" style="background: var(--text-muted);"></div>
                <div class="label">Total Incidents</div>
                <div class="value">{total}</div>
                <div class="sub">all time</div>
            </div>
            <div class="stat-card accent">
                <div class="corner-dot" style="background: var(--accent); box-shadow: 0 0 10px var(--accent-glow);"></div>
                <div class="label">Open</div>
                <div class="value">{open_count}</div>
                <div class="sub">awaiting triage</div>
            </div>
            <div class="stat-card critical">
                <div class="corner-dot"></div>
                <div class="label">Critical</div>
                <div class="value">{critical}</div>
                <div class="sub">P0 severity</div>
            </div>
            <div class="stat-card high">
                <div class="corner-dot"></div>
                <div class="label">High</div>
                <div class="value">{high}</div>
                <div class="sub">P1 severity</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Incident table
# ---------------------------------------------------------------------------

SEV_DOT = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}


def _format_created(value) -> str:
    try:
        ts = pd.to_datetime(value, errors="coerce")
        if pd.isna(ts):
            return ""
        return ts.strftime("%b %d · %H:%M")
    except Exception:
        return str(value or "")


def _html_escape(value) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


def render_incident_table(incidents: list[dict], *, compact: bool) -> None:
    """Render the incidents list as an HTML grid table. Click sets ?incident_id."""
    if not incidents:
        st.markdown(
            """
            <div class="detail-card" style="text-align:center; padding: 3rem 1rem;">
                <div style="font-family:'Geist Mono',monospace; color:var(--text-muted);
                            text-transform:uppercase; letter-spacing:0.16em; font-size:0.75rem;">
                    No incidents yet
                </div>
                <div style="margin-top:0.6rem; color:var(--text-secondary); font-size:0.9rem;">
                    Create an incident from the sidebar or send an Alertmanager webhook.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    selected_id = st.session_state.get("selected_incident_id")
    try:
        selected_id = int(selected_id) if selected_id is not None else None
    except (TypeError, ValueError):
        selected_id = None

    grid_template = (
        "56px 26px 1fr"
        if compact
        else "70px 150px 110px 160px 1fr 150px"
    )

    if compact:
        header_cells = '<div>ID</div><div></div><div>Title</div>'
    else:
        header_cells = (
            '<div>ID</div><div>Severity</div><div>Status</div><div>Service</div>'
            '<div>Title</div><div>Created</div>'
        )

    rows_html: list[str] = []
    for inc in incidents:
        inc_id = int(inc["id"])
        sev = (inc.get("severity") or "").upper()
        status = (inc.get("status") or "").upper()
        dot = SEV_DOT.get(sev, "⚪")
        title = _html_escape(inc.get("title") or "")
        service = _html_escape(inc.get("service") or "")
        created = _html_escape(_format_created(inc.get("created_at")))

        sev_cls = severity_class(sev)
        status_cls = status_class(status)
        is_selected = selected_id == inc_id

        if compact:
            cells = (
                f'<div class="c-id mono">#{inc_id}</div>'
                f'<div class="c-sev sev-{sev_cls}" title="{sev}"><span class="sev-dot">{dot}</span></div>'
                f'<div class="c-title">{title}</div>'
            )
        else:
            cells = (
                f'<div class="c-id mono">#{inc_id}</div>'
                f'<div class="c-sev sev-{sev_cls}"><span class="sev-dot">{dot}</span>{sev}</div>'
                f'<div class="c-status"><span class="row-pill {status_cls}">{status}</span></div>'
                f'<div class="c-service mono">{service}</div>'
                f'<div class="c-title">{title}</div>'
                f'<div class="c-created mono muted">{created}</div>'
            )

        sel_cls = " selected" if is_selected else ""
        rows_html.append(
            f'<a class="incident-row{sel_cls}" target="_self" '
            f'href="?incident_id={inc_id}" '
            f'style="grid-template-columns:{grid_template};">{cells}</a>'
        )

    st.markdown(
        f'<div class="incident-table">'
        f'<div class="incident-row-head" style="grid-template-columns:{grid_template};">'
        f'{header_cells}</div>'
        f'{"".join(rows_html)}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Incident detail
# ---------------------------------------------------------------------------

def render_report_panel(incident_id: int, key_prefix: str) -> bool:
    try:
        report = api_client().get_report(incident_id)
    except IncidentApiError as exc:
        if exc.status_code == 404:
            report = None
        else:
            stop_on_api_error(exc)
    if not report:
        st.markdown(
            """
            <div style="color:var(--text-muted); font-family:'Geist Mono',monospace;
                        font-size:0.78rem; padding:0.8rem 0;">
                No report generated yet. Click <b style="color:var(--accent);">Run now</b> to trigger analysis.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return False

    st.markdown(report["report_md"])
    left, right = st.columns(2)
    left.download_button(
        ":material/download: report.json",
        data=json.dumps(report["report"], indent=2),
        file_name=f"incident_{incident_id}_report.json",
        mime="application/json",
        use_container_width=True,
        key=f"{key_prefix}_report_json_{incident_id}",
    )
    right.download_button(
        ":material/download: report.md",
        data=report["report_md"],
        file_name=f"incident_{incident_id}_report.md",
        mime="text/markdown",
        use_container_width=True,
        key=f"{key_prefix}_report_md_{incident_id}",
    )
    return True


def render_incident_detail(incident_id: int) -> None:
    client = api_client()
    try:
        incident = client.get_incident(incident_id)
    except IncidentApiError as exc:
        if exc.status_code == 404:
            incident = None
        else:
            stop_on_api_error(exc)
    if not incident:
        st.warning("Incident not found")
        return

    sev = (incident.get("severity") or "").upper()
    status = (incident.get("status") or "").upper()

    # Header card
    top_cols = st.columns([4, 1])
    with top_cols[1]:
        if st.button(":material/close: Close", key=f"close_{incident_id}", use_container_width=True):
            st.session_state["selected_incident_id"] = None
            if "incident_id" in st.query_params:
                del st.query_params["incident_id"]
            st.rerun()

    st.markdown(
        f"""
        <div class="detail-card">
            <div class="detail-head">
                <div class="detail-id">Incident · #{incident['id']}</div>
                <div class="detail-title">{incident.get('title') or incident['service']}</div>
                <div class="detail-meta-row">
                    {pill(status, status_class(status))}
                    {pill(sev, severity_class(sev))}
                    {pill(incident.get('service') or '—', 'neutral')}
                    {pill(incident.get('environment') or '—', 'neutral')}
                </div>
            </div>
            <div class="detail-info-grid">
                <div><span class="k">Source</span></div>
                <div><span class="v">{incident.get('source') or '—'}</span></div>
                <div><span class="k">Alert Type</span></div>
                <div><span class="v">{incident.get('alert_type') or '—'}</span></div>
                <div><span class="k">Created</span></div>
                <div><span class="v">{incident.get('created_at') or '—'}</span></div>
                <div><span class="k">Updated</span></div>
                <div><span class="v">{incident.get('updated_at') or '—'}</span></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if incident.get("description"):
        st.markdown(
            f"""
            <div style="color:var(--text-secondary); font-size:0.92rem; line-height:1.65;
                        padding: 0 0.25rem 1rem 0.25rem;">
                {incident['description']}
            </div>
            """,
            unsafe_allow_html=True,
        )

    actions = st.columns([1, 1, 3])
    if actions[0].button(":material/play_arrow: Run now", type="primary", use_container_width=True, key=f"run_{incident_id}"):
        with st.spinner("Processing incident…"):
            try:
                client.run_incident(incident_id)
            except IncidentApiError as exc:
                st.error(f"Incident processing failed: {exc}")
                return
        st.rerun()
    if actions[1].button(":material/refresh: Refresh", use_container_width=True, key=f"refresh_{incident_id}"):
        st.rerun()

    section_head("Incident Report")
    render_report_panel(incident_id, key_prefix="detail")

    detail_tabs = st.tabs(["Timeline", "Evidence", "Payload"])
    try:
        steps = client.list_steps(incident_id)
    except IncidentApiError as exc:
        stop_on_api_error(exc)

    with detail_tabs[0]:
        if steps:
            steps_df = pd.DataFrame(
                [
                    {
                        "ID": step["id"],
                        "Agent": step["agent"],
                        "Phase": step["phase"],
                        "Status": (step.get("status") or "").upper(),
                        "Message": step["message"],
                        "Timestamp": step["ts"],
                    }
                    for step in steps
                ]
            )
            st.dataframe(steps_df, use_container_width=True, hide_index=True, height=360)
        else:
            st.info("No agent steps yet.")

    with detail_tabs[1]:
        collector_steps = [s for s in steps if s["agent"] == "collector" and s["phase"] == "done"]
        analyst_retrieval = [s for s in steps if s["agent"] == "analyst" and s["phase"] == "retrieve"]
        if collector_steps:
            section_head("Retrieved Logs")
            logs = collector_steps[-1].get("data", {}).get("logs", [])
            if logs:
                st.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True)
            else:
                st.info("No logs in collector output.")
        if analyst_retrieval:
            section_head("Knowledge Snippets")
            snippets = analyst_retrieval[-1].get("data", {}).get("snippets", [])
            if snippets:
                st.dataframe(pd.DataFrame(snippets), use_container_width=True, hide_index=True)
            else:
                st.info("No knowledge snippets retrieved.")
        if not collector_steps and not analyst_retrieval:
            st.info("No evidence collected yet.")

    with detail_tabs[2]:
        st.json(incident.get("payload", {}))


# ---------------------------------------------------------------------------
# Dashboard composition
# ---------------------------------------------------------------------------

def render_dashboard() -> None:
    try:
        incidents = api_client().list_incidents(limit=200)
    except IncidentApiError as exc:
        page_header(
            eyebrow="Operations Â· Live",
            title="Dashboard",
            meta="api unavailable",
        )
        st.error(f"API unavailable: {exc}")
        return

    # Pick up row clicks from anchor links (?incident_id=<id>)
    if "incident_id" in st.query_params:
        try:
            st.session_state["selected_incident_id"] = int(st.query_params["incident_id"])
        except (TypeError, ValueError):
            pass

    page_header(
        eyebrow="Operations · Live",
        title="Dashboard",
        meta=f"{len(incidents)} incidents tracked",
    )

    render_stat_cards(incidents)

    valid_ids = {int(i["id"]) for i in incidents}
    selected_id = st.session_state.get("selected_incident_id")
    try:
        selected_id = int(selected_id) if selected_id is not None else None
    except (TypeError, ValueError):
        selected_id = None
    if selected_id is not None and selected_id not in valid_ids:
        selected_id = None
        st.session_state["selected_incident_id"] = None
        if "incident_id" in st.query_params:
            del st.query_params["incident_id"]

    if selected_id:
        section_head("Incidents", right=f"selected · #{selected_id}")
        table_col, detail_col = st.columns([1, 1.55], gap="large")
        with table_col:
            render_incident_table(incidents, compact=True)
        with detail_col:
            render_incident_detail(selected_id)
    else:
        section_head("Incidents", right="click a row to inspect")
        render_incident_table(incidents, compact=False)


# ---------------------------------------------------------------------------
# Create Incident
# ---------------------------------------------------------------------------

def create_incident_form() -> None:
    page_header(
        eyebrow="New Record",
        title="Create Incident",
        meta="manual entry",
    )

    with st.form("incident_form"):
        section_head("Routing")
        cols = st.columns(3)
        service = cols[0].text_input("Service", value="payment-service")
        environment = cols[1].text_input("Environment", value="prod")
        severity = cols[2].selectbox("Severity", ["CRITICAL", "HIGH", "MEDIUM", "LOW"], index=0)

        section_head("Description")
        title = st.text_input("Title", value="Checkout requests are failing")
        description = st.text_area("Description", value="HTTP 500 spike on checkout flow", height=100)

        section_head("Source")
        src_cols = st.columns(3)
        alert_type = src_cols[0].text_input("Alert type", value="HTTP 500")
        source = src_cols[1].text_input("Source", value="manual")
        external_id = src_cols[2].text_input("External ID", value="")

        section_head("Payload")
        payload_raw = st.text_area(
            "Payload JSON",
            value='{"details": "synthetic cloudwatch-like alert", "service": "payment-service"}',
            height=160,
            label_visibility="collapsed",
        )

        submitted = st.form_submit_button("Create incident", type="primary", use_container_width=True)

    if submitted:
        try:
            incident = api_client().create_incident(
                {
                    "service": service,
                    "environment": environment,
                    "severity": severity,
                    "title": title,
                    "description": description,
                    "alert_type": alert_type,
                    "source": source or "manual",
                    "external_id": external_id or None,
                    "payload": parse_payload(payload_raw),
                }
            )
        except IncidentApiError as exc:
            st.error(f"Incident was not created: {exc}")
            return

        incident_id = int(incident["id"])
        st.session_state["selected_incident_id"] = incident_id
        st.session_state["nav_key"] = "dashboard"
        st.success(f"Incident #{incident_id} created")
        st.rerun()


# ---------------------------------------------------------------------------
# AI Providers
# ---------------------------------------------------------------------------

def render_provider_panel() -> None:
    try:
        health = api_client().provider_status()
    except IncidentApiError as exc:
        page_header(
            eyebrow="Inference",
            title="AI Providers",
            meta="api unavailable",
        )
        st.error(f"API unavailable: {exc}")
        return

    status = health.get("ai", {})
    page_header(
        eyebrow="Inference",
        title="AI Providers",
        meta=f"api · {health.get('status', 'unknown')} · default · {status.get('default_model', 'unknown')}",
    )

    cards = []
    for item in status.get("models", []):
        configured = item["configured"]
        dot_color = "var(--status-resolved)" if configured else "var(--text-muted)"
        glow = "0 0 8px rgba(61,220,151,0.45)" if configured else "none"
        cls = "resolved" if configured else "neutral"
        cards.append(
            f'<div class="stat-card">'
            f'<div class="corner-dot" style="background:{dot_color}; box-shadow:{glow};"></div>'
            f'<div class="label">{item["provider"]}</div>'
            f'<div class="value" style="font-size:1.05rem; font-family:\'Geist Mono\',monospace;">{item["model"]}</div>'
            f'<div class="sub">{pill("configured" if configured else "not set", cls)}</div>'
            f'</div>'
        )
    st.markdown(
        f'<div class="stat-grid" style="grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));">{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )

    section_head("Knowledge Base")
    st.markdown(
        """
        <div style="color:var(--text-secondary); font-size:0.88rem; line-height:1.6; max-width:680px;">
            Rebuild the RAG index over runbooks and post-mortems. Trigger this after adding new
            documents to <code>knowledge/</code>.
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button(":material/refresh: Rebuild knowledge base", type="primary"):
        with st.spinner("Reindexing knowledge base…"):
            try:
                result = api_client().reindex_rag()
            except IncidentApiError as exc:
                st.error(f"Reindex failed: {exc}")
                return
        st.success(f"Indexed {result['documents']} chunks via {result['backend']}")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="Incident Responder",
        layout="wide",
        initial_sidebar_state="expanded",
        page_icon="🛰️",
    )
    inject_theme()

    if "nav_key" not in st.session_state:
        st.session_state["nav_key"] = "dashboard"
    if "selected_incident_id" not in st.session_state:
        st.session_state["selected_incident_id"] = None

    nav = render_sidebar()

    if nav == "dashboard":
        render_dashboard()
    elif nav == "create":
        create_incident_form()
    elif nav == "providers":
        render_provider_panel()


if __name__ == "__main__":
    main()
