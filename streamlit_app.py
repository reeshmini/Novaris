import html
import re
import time
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from dotenv import dotenv_values


# =========================================================
# CONFIG
# =========================================================
env_path = Path(__file__).resolve().parent / ".env"
env_vars = dict(dotenv_values(env_path))

# Deployment-friendly secrets handling:
# - Local development can continue using .env
# - Streamlit Community Cloud can use its built-in Secrets panel
# Cloud secrets override local .env values when both are present.
try:
    for _key in st.secrets.keys():
        _value = st.secrets[_key]
        if isinstance(_value, (str, int, float, bool)):
            env_vars[_key] = str(_value)
except Exception:
    pass

ETHERSCAN_API_KEY = (env_vars.get("ETHERSCAN_API_KEY") or "").strip()
GNEWS_API_KEY = (env_vars.get("GNEWS_API_KEY") or "").strip()

DEFAULT_ETH_WATCH = (env_vars.get("DEFAULT_ETH_WATCH") or "").strip()
DEFAULT_BTC_WATCH = (env_vars.get("DEFAULT_BTC_WATCH") or "").strip()

WHALE_THRESHOLD_USD = float((env_vars.get("WHALE_THRESHOLD_USD") or "1000000").strip())
NETWORK_ETH_BLOCKS = int((env_vars.get("NETWORK_ETH_BLOCKS") or "1").strip())
NETWORK_BTC_BLOCKS = int((env_vars.get("NETWORK_BTC_BLOCKS") or "4").strip())
BTC_NETWORK_TXS_PER_BLOCK = int((env_vars.get("BTC_NETWORK_TXS_PER_BLOCK") or "20").strip())
WATCH_TX_LIMIT = int((env_vars.get("WATCH_TX_LIMIT") or "15").strip())

# Controlled refresh intervals for expensive external data.
# Navigation reruns reuse st.session_state and do not call these APIs again
# until the corresponding interval has elapsed.
NETWORK_REFRESH_SECONDS = int((env_vars.get("NETWORK_REFRESH_SECONDS") or "120").strip())
MARKET_REFRESH_SECONDS = int((env_vars.get("MARKET_REFRESH_SECONDS") or "120").strip())
NEWS_REFRESH_SECONDS = int((env_vars.get("NEWS_REFRESH_SECONDS") or "300").strip())

ETH_RPC_URLS = [x.strip() for x in (env_vars.get("ETH_RPC_URLS") or "").split(",") if x.strip()]
DEFAULT_NEWS_QUERY = (
    env_vars.get("DEFAULT_NEWS_QUERY")
    or "Bitcoin OR Ethereum OR cryptocurrency OR blockchain OR crypto market"
).strip()

CHAIN_ETH = "Ethereum"
CHAIN_BTC = "Bitcoin"

STABLECOINS = {"USDT", "USDC", "DAI", "FDUSD", "PYUSD", "USDP", "TUSD", "GUSD", "LUSD", "FRAX"}

ASSET_META = {
    "BTC": {"icon": "🟠", "label": "Bitcoin", "chain_label": "Bitcoin"},
    "ETH": {"icon": "💠", "label": "Ethereum", "chain_label": "Ethereum"},
    "USDT": {"icon": "🟢", "label": "Tether", "chain_label": "Ethereum"},
    "USDC": {"icon": "🔵", "label": "USD Coin", "chain_label": "Ethereum"},
    "DAI": {"icon": "🟡", "label": "DAI", "chain_label": "Ethereum"},
    "WBTC": {"icon": "🟠", "label": "Wrapped Bitcoin", "chain_label": "Ethereum"},
}

TOKEN_PRICE_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "USDT": "tether",
    "USDC": "usd-coin",
    "DAI": "dai",
    "WBTC": "wrapped-bitcoin",
}

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

REQUIRED_COLUMNS = [
    "chain",
    "asset_symbol",
    "asset_name",
    "timestamp",
    "tx_hash",
    "from",
    "to",
    "direction",
    "amount_native",
    "amount_usd",
    "source_type",
    "watch_address",
    "event_note",
]


# =========================================================
# PAGE
# =========================================================
st.set_page_config(
    page_title="Novaris ✦",
    page_icon="✦",
    layout="wide",
)

st.markdown("""
<style>
header[data-testid="stHeader"] {
    display: none !important;
}

.stApp {
    background:
      radial-gradient(circle at 24% 16%, rgba(211,139,25,0.10), transparent 28%),
      radial-gradient(circle at 78% 20%, rgba(31,183,104,0.05), transparent 24%),
      linear-gradient(180deg, #050505 0%, #080808 42%, #0b0b0b 100%);
    color: #f7f3eb;
}

.block-container {
    padding-top: 0 !important;
    padding-bottom: 1rem !important;
    padding-left: 1.25rem !important;
    padding-right: 1.25rem !important;
    max-width: 100% !important;
}

h1, h2, h3, h4, h5, h6, p, label {
    color: #ffffff !important;
    font-family: Inter, Segoe UI, Arial, sans-serif !important;
}

.brand-title {
    font-size: 3.45rem;
    font-weight: 950;
    color: #ffffff !important;
    -webkit-text-stroke: 0.18px rgba(255,255,255,0.92);
    text-shadow:
        0 0 3px rgba(255,255,255,0.78),
        0 0 7px rgba(255,255,255,0.52),
        0 0 14px rgba(235,242,255,0.34),
        0 0 24px rgba(210,226,255,0.20),
        0 0 34px rgba(180,210,255,0.10);
    filter:
        drop-shadow(0 0 4px rgba(255,255,255,0.18));
    margin-bottom: 0.35rem;
    line-height: 1.02;
    letter-spacing: -0.7px;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    animation: none;
}

.brand-sub {
    font-size: 0.98rem;
    color: #f2ede4 !important;
    margin-bottom: 0.15rem;
}

.brand-mini {
    font-size: 0.87rem;
    color: #b9b3a8 !important;
    opacity: 1;
}


.sidebar-note {
    font-size: 0.88rem;
    color: #ffffff !important;
    opacity: 0.9;
    margin-bottom: 1rem;
    line-height: 1.4;
}

.stTextInput input, .stTextArea textarea, .stNumberInput input {
    background: rgba(18,18,18,0.98) !important;
    color: #ffffff !important;
    border: 1px solid rgba(255,255,255,0.14) !important;
    border-radius: 12px !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
}

.stButton > button {
    background: linear-gradient(90deg, #9d5d00, #d48612 58%, #f0a72a) !important;
    color: #fff7e8 !important;
    font-weight: 850 !important;
    border: 1px solid rgba(255,190,85,0.35) !important;
    border-radius: 12px !important;
    box-shadow:
        0 0 16px rgba(211,139,25,0.20),
        0 8px 22px rgba(0,0,0,0.28);
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow:
        0 0 22px rgba(211,139,25,0.30),
        0 10px 26px rgba(0,0,0,0.32);
}

div[data-testid="stMetric"] {
    background: rgba(8, 22, 44, 0.92);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 18px;
    padding: 10px 12px;
    min-height: 104px;
}

div[data-testid="stMetricValue"] {
    color: #ffffff !important;
}

div[data-testid="stMetricLabel"] {
    color: #ffffff !important;
}

.section-title {
    font-size: 2.15rem;
    font-weight: 800;
    color: #ffffff !important;
    text-shadow: 0 0 8px rgba(255,255,255,0.08);
    margin-bottom: 0.95rem;
    line-height: 1.1;
    letter-spacing: -0.3px;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
}

.subtle-title {
    font-size: 1.15rem;
    font-weight: 700;
    color: #ffffff !important;
    opacity: 0.95;
    margin-bottom: 0.6rem;
}




/* =========================
   STICKY NOVARIS HEADER
   ========================= */

/* The keyed header container itself */
.st-key-brand_header {
    position: sticky !important;
    top: 0 !important;
    z-index: 9999 !important;
    background:
        linear-gradient(
            180deg,
            rgba(5,5,5,0.99) 0%,
            rgba(7,7,7,0.98) 82%,
            rgba(7,7,7,0.94) 100%
        ) !important;
    backdrop-filter: blur(14px) !important;
    -webkit-backdrop-filter: blur(14px) !important;
    border-bottom: 1px solid rgba(212,134,18,0.22) !important;
    box-shadow:
        0 10px 28px rgba(0,0,0,0.34),
        0 1px 0 rgba(255,255,255,0.025) !important;
    padding: 0.55rem 0 0.65rem 0 !important;
    margin-bottom: 0.85rem !important;
}

/* Streamlit sometimes places the key on a nested wrapper.
   This selector makes the actual element containing the title sticky too. */
div[data-testid="stVerticalBlock"] > div:has(.brand-title),
div[data-testid="stElementContainer"]:has(.brand-title) {
    position: sticky !important;
    top: 0 !important;
    z-index: 9999 !important;
    background:
        linear-gradient(
            180deg,
            rgba(5,5,5,0.99) 0%,
            rgba(7,7,7,0.98) 82%,
            rgba(7,7,7,0.94) 100%
        ) !important;
    backdrop-filter: blur(14px) !important;
    -webkit-backdrop-filter: blur(14px) !important;
    border-bottom: 1px solid rgba(212,134,18,0.22) !important;
    box-shadow:
        0 10px 28px rgba(0,0,0,0.34),
        0 1px 0 rgba(255,255,255,0.025) !important;
}

/* Remove any visible inner shell */
.st-key-brand_header [data-testid="stVerticalBlockBorderWrapper"] {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    padding: 0 !important;
}

/* Compact the pinned header slightly */
.st-key-brand_header .brand-title,
div[data-testid="stVerticalBlock"] > div:has(.brand-title) .brand-title {
    margin-bottom: 0.18rem !important;
}

.st-key-brand_header .brand-sub,
div[data-testid="stVerticalBlock"] > div:has(.brand-title) .brand-sub {
    margin-bottom: 0.06rem !important;
}

.st-key-brand_header .brand-mini,
div[data-testid="stVerticalBlock"] > div:has(.brand-title) .brand-mini {
    margin-bottom: 0 !important;
}

/* =========================
   CONTROL PANEL CARDS
   ========================= */
/* Align the right control rail with the top KPI-card row */
.control-rail-top-spacer {
    height: 138px;
    width: 100%;
    pointer-events: none;
    margin: 0 !important;
    padding: 0 !important;
}

/* At laptop / narrower desktop widths the header wraps slightly less,
   so use a slightly smaller but still aligned offset. */
@media (max-width: 1400px) {
    .control-rail-top-spacer {
        height: 130px;
    }
}

.sidebar-section-title {
    font-size: 1.50rem !important;
    font-weight: 900 !important;
    line-height: 1.08 !important;
    letter-spacing: -0.35px !important;
    color: #ffffff !important;
    margin: 0.10rem 0 0.85rem 0 !important;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    text-shadow:
        0 0 8px rgba(255,255,255,0.22),
        0 0 16px rgba(124,248,255,0.14),
        0 0 26px rgba(200,162,255,0.22);
}

.sidebar-card-title-outside {
    font-size: 2.55rem !important;
    font-weight: 800 !important;
    line-height: 1.1 !important;
    letter-spacing: -0.02em !important;
    color: #F4F8FF !important;
    margin: 8px 0 14px 0 !important;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    text-shadow: 0 0 8px rgba(255,255,255,0.08) !important;
}

.sidebar-card-title-gap {
    margin-top: 0.30rem !important;
}

.sidebar-card-kicker {
    font-size: 0.70rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #C8A2FF !important;
    margin-bottom: 0.35rem;
    opacity: 0.95;
}

/* Two distinct right-side control cards */
.st-key-monitoring_controls_card,
.st-key-watchlist_controls_card {
    position: relative;
    overflow: hidden;
    background: linear-gradient(180deg, rgba(10,24,46,0.97), rgba(7,18,35,0.99)) !important;
    border: 1px solid rgba(124,248,255,0.17) !important;
    border-radius: 20px !important;
    padding: 14px 14px 14px 14px !important;
    margin-bottom: 16px !important;
    box-shadow:
        0 10px 26px rgba(0,0,0,0.23),
        inset 0 1px 0 rgba(255,255,255,0.04);
    transition: transform 0.22s ease, border-color 0.22s ease, box-shadow 0.22s ease;
}

.st-key-monitoring_controls_card::before,
.st-key-watchlist_controls_card::before {
    content: "";
    position: absolute;
    top: 0;
    left: 14px;
    right: 14px;
    height: 3px;
    border-radius: 999px;
}

/* Purple accent: monitoring controls */
.st-key-monitoring_controls_card::before {
    background: linear-gradient(90deg, rgba(200,162,255,0), #C8A2FF, rgba(200,162,255,0));
    box-shadow: 0 0 16px rgba(200,162,255,0.45);
}

/* Green-cyan accent: watchlist */
.st-key-watchlist_controls_card::before {
    background: linear-gradient(90deg, rgba(109,255,157,0), #6DFF9D, rgba(109,255,157,0));
    box-shadow: 0 0 16px rgba(109,255,157,0.38);
}

.st-key-monitoring_controls_card:hover,
.st-key-watchlist_controls_card:hover {
    transform: translateY(-2px);
    border-color: rgba(255,255,255,0.27) !important;
    box-shadow:
        0 14px 32px rgba(0,0,0,0.28),
        0 0 20px rgba(124,248,255,0.08),
        inset 0 1px 0 rgba(255,255,255,0.05);
}

.st-key-monitoring_controls_card label,
.st-key-watchlist_controls_card label {
    color: #D8E6F5 !important;
    font-weight: 700 !important;
}

/* Remove Streamlit's inner border so only the custom card border is visible */
.st-key-monitoring_controls_card [data-testid="stVerticalBlockBorderWrapper"],
.st-key-watchlist_controls_card [data-testid="stVerticalBlockBorderWrapper"] {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    padding: 0 !important;
}


.sidebar-card-heading {
    font-size: 1.55rem !important;
    font-weight: 900 !important;
    line-height: 1.08 !important;
    letter-spacing: -0.4px !important;
    color: #ffffff !important;
    margin: 0.15rem 0 0.95rem 0 !important;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    text-shadow:
        0 0 8px rgba(255,255,255,0.18),
        0 0 16px rgba(211,139,25,0.16),
        0 0 26px rgba(211,139,25,0.12);
}

.st-key-monitoring_controls_card,
.st-key-watchlist_controls_card {
    background:
        radial-gradient(circle at top left, rgba(255,178,30,0.09), transparent 38%),
        linear-gradient(180deg, rgba(10,10,10,0.99), rgba(3,3,3,1)) !important;
    border: 1px solid rgba(255,178,30,0.28) !important;
    border-radius: 20px !important;
    box-shadow:
        0 0 0 1px rgba(255,178,30,0.05),
        0 0 14px rgba(255,178,30,0.12),
        0 10px 28px rgba(0,0,0,0.38) !important;
    transition:
        transform 0.25s ease,
        border-color 0.25s ease,
        box-shadow 0.25s ease !important;
}

/* Same amber top accent used by the KPI cards */
.st-key-monitoring_controls_card::before,
.st-key-watchlist_controls_card::before {
    background:
        linear-gradient(
            90deg,
            rgba(255,178,30,0),
            rgba(255,178,30,1),
            rgba(255,178,30,0)
        ) !important;
    box-shadow:
        0 0 18px rgba(255,178,30,0.38),
        0 0 34px rgba(255,145,0,0.14) !important;
}

/* Match KPI-card hover glow */
.st-key-monitoring_controls_card:hover,
.st-key-watchlist_controls_card:hover {
    transform: translateY(-3px);
    border-color: rgba(255,199,92,0.58) !important;
    box-shadow:
        0 0 0 1px rgba(255,199,92,0.12),
        0 0 20px rgba(255,178,30,0.24),
        0 0 38px rgba(255,145,0,0.14),
        0 14px 34px rgba(0,0,0,0.46) !important;
}

/* =========================
   LATEST ALERTS - 3D CARDS
   ========================= */

.latest-alerts-title {
    color: #F8E6BC !important;
    font-size: 1.82rem !important;
    font-weight: 820 !important;
    line-height: 1.08 !important;
    letter-spacing: 0.7px !important;
    text-transform: uppercase !important;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    text-shadow:
        0 0 12px rgba(255,178,30,0.12),
        0 0 18px rgba(255,178,30,0.06);
    margin: 10px 0 18px 0;
}

.alert-card {
    position: relative;
    background: linear-gradient(180deg, rgba(20,20,20,0.98) 0%, rgba(10,10,10,0.99) 100%);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 20px;
    padding: 16px 18px;
    box-shadow:
        0 10px 26px rgba(0,0,0,0.24),
        inset 0 1px 0 rgba(255,255,255,0.05);
    overflow: hidden;
    transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;
    margin-bottom: 14px;
}

.alert-card::before {
    content: "";
    position: absolute;
    left: 14px;
    right: 14px;
    top: 0;
    height: 3px;
    border-radius: 999px;
    background: linear-gradient(90deg, rgba(212,134,18,0.0), rgba(212,134,18,0.95), rgba(212,134,18,0.0));
    box-shadow: 0 0 14px rgba(212,134,18,0.38);
}

.alert-card:hover {
    transform: translateY(-3px);
    border-color: rgba(255,255,255,0.62);
    box-shadow:
        0 16px 34px rgba(0,0,0,0.34),
        0 0 10px rgba(255,255,255,0.22),
        0 0 24px rgba(255,255,255,0.16),
        0 0 42px rgba(255,255,255,0.08),
        inset 0 1px 0 rgba(255,255,255,0.10);
}

.alert-card.whale-card {
    border-color: rgba(124,248,255,0.30);
    box-shadow:
        0 16px 36px rgba(0,0,0,0.28),
        0 0 26px rgba(124,248,255,0.14),
        inset 0 1px 0 rgba(255,255,255,0.06);
}

.alert-card.whale-card::before {
    background: linear-gradient(90deg, rgba(124,248,255,0.0), rgba(124,248,255,1), rgba(124,248,255,0.0));
    box-shadow: 0 0 18px rgba(124,248,255,0.62);
}


.alert-card.whale-card:hover {
    border-color: rgba(255,255,255,0.62);
    box-shadow:
        0 16px 34px rgba(0,0,0,0.34),
        0 0 10px rgba(255,255,255,0.22),
        0 0 24px rgba(255,255,255,0.16),
        0 0 42px rgba(255,255,255,0.08),
        inset 0 1px 0 rgba(255,255,255,0.10);
}

.alert-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 14px;
}

.alert-left {
    display: flex;
    align-items: center;
    gap: 17px;
    min-width: 0;
    flex: 1;
}

.asset-circle {
    width: 58px;
    height: 58px;
    min-width: 58px;
    border-radius: 50%;
    background: radial-gradient(circle at 30% 25%, rgba(255,188,92,0.22), rgba(26,18,10,0.96) 58%), linear-gradient(180deg, rgba(28,20,10,0.98), rgba(10,10,10,0.99));
    border: 1px solid rgba(255,184,64,0.34);
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.10),
        0 0 16px rgba(255,170,34,0.18),
        0 8px 20px rgba(0,0,0,0.28);
    display: flex;
    align-items: center;
    justify-content: center;
    align-self: center;
    font-size: 1.72rem;
    line-height: 1;
    color: #82C9FF;
    flex-shrink: 0;
}


/* Latest Alerts crypto icons — same visual language as Spot Price cards */
.asset-circle .alert-eth-icon {
    width: 32px;
    height: 32px;
    display: block;
    overflow: visible;
    filter:
        drop-shadow(0 0 5px rgba(175,200,255,0.34))
        drop-shadow(0 0 10px rgba(112,146,255,0.18));
}

.asset-circle .alert-btc-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: #FFCF5A !important;
    font-family: Georgia, "Times New Roman", serif !important;
    font-size: 2.10rem !important;
    font-weight: 900 !important;
    line-height: 1 !important;
    transform: translateY(-1px);
    text-shadow:
        0 0 5px rgba(255,207,90,0.66),
        0 0 11px rgba(255,178,30,0.30);
}

/* Keep the homepage's smaller alert circles proportional */
.st-key-home_alerts_panel .asset-circle .alert-eth-icon {
    width: 26px;
    height: 26px;
}

.st-key-home_alerts_panel .asset-circle .alert-btc-icon {
    font-size: 1.72rem !important;
}

.alert-content {
    min-width: 0;
    flex: 1 1 auto;
    padding-right: 18px;
}

.alert-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 9px;
    margin-bottom: 8px;
}

.left-alerts-wrap {
    width: 100%;
    max-width: 100%;
}

.alert-card {
    width: 100%;
    max-width: 100%;
    box-sizing: border-box;
}

.alert-row,
.alert-left,
.alert-content {
    width: 100%;
    max-width: 100%;
}

.alert-sub,
.alert-title {
    overflow-wrap: anywhere;
    word-break: break-word;
}

.badge {
    display: inline-block;
    padding: 6px 13px;
    border-radius: 999px;
    font-size: 0.98rem;
    font-weight: 800;
    line-height: 1;
    letter-spacing: 0.01em;
    margin: 0;
}

.badge-eth {
    background: rgba(61,139,255,0.14);
    border: 1px solid rgba(91,169,255,0.40);
    color: #DDEEFF !important;
    box-shadow:
        0 0 10px rgba(70,145,255,0.14),
        0 0 18px rgba(70,145,255,0.07),
        inset 0 1px 0 rgba(255,255,255,0.05);
}

.badge-btc {
    background: rgba(255,136,60,0.13);
    border: 1px solid rgba(255,136,60,0.32);
    color: #FFE0C7 !important;
    box-shadow:
        0 0 10px rgba(255,136,60,0.10),
        inset 0 1px 0 rgba(255,255,255,0.04);
}

.badge-net {
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.20);
    color: #F4F4F4 !important;
    box-shadow:
        0 0 8px rgba(255,255,255,0.06),
        inset 0 1px 0 rgba(255,255,255,0.04);
}

.badge-watch {
    background: rgba(255,178,30,0.10);
    border: 1px solid rgba(255,178,30,0.28);
    color: #FFE7AE !important;
    box-shadow:
        0 0 9px rgba(255,178,30,0.08),
        inset 0 1px 0 rgba(255,255,255,0.04);
}

.badge-high {
    background: rgba(255,84,84,0.14);
    border: 1px solid rgba(255,84,84,0.30);
    color: #FFD7D7 !important;
    box-shadow: 0 0 9px rgba(255,84,84,0.08);
}

.badge-medium {
    background: rgba(255,178,30,0.13);
    border: 1px solid rgba(255,178,30,0.32);
    color: #FFE2A0 !important;
    box-shadow: 0 0 9px rgba(255,178,30,0.08);
}

.badge-low {
    background: rgba(72,196,125,0.12);
    border: 1px solid rgba(72,196,125,0.28);
    color: #DDF7E8 !important;
    box-shadow: 0 0 9px rgba(72,196,125,0.08);
}

.flag-row {
    margin-bottom: 8px;
    font-size: 0.95rem;
    letter-spacing: 0.08em;
    color: #FF7E73;
    text-shadow: 0 0 10px rgba(255,126,115,0.30);
}

.alert-title {
    display: grid;
    grid-template-columns: max-content max-content;
    align-items: baseline;
    justify-content: start;
    column-gap: 20px;
    row-gap: 4px;
    width: max-content;
    max-width: 100%;
    font-size: 1.46rem;
    font-weight: 850;
    color: #FFFFFF !important;
    line-height: 1.18;
    margin-bottom: 7px;
    letter-spacing: -0.02em;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
}

.alert-amount {
    display: inline-block;
    font-size: 1.50rem;
    font-weight: 900;
    color: #FFB21E !important;
    letter-spacing: -0.025em;
    white-space: nowrap;
    text-shadow: 0 0 14px rgba(255,178,30,0.18);
}

.alert-usd {
    display: inline-block;
    margin-left: 2px;
    font-size: 1.28rem;
    font-weight: 800;
    color: #F0F4FA !important;
    letter-spacing: -0.015em;
    white-space: nowrap;
    opacity: 0.96;
}

.alert-sub {
    font-size: 1.10rem;
    color: #C6D6E8 !important;
    line-height: 1.35;
    word-break: break-word;
}

.alert-time {
    align-self: flex-start;
    font-size: 1.02rem;
    font-weight: 800;
    color: #E7EEF8 !important;
    white-space: nowrap;
    opacity: 0.98;
    padding-top: 5px;
    text-shadow: 0 0 8px rgba(255,255,255,0.10);
}

.stTabs [data-baseweb="tab-list"] {
    gap: 12px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    padding-bottom: 6px;
}

.stTabs [data-baseweb="tab"] {
    background: linear-gradient(180deg, rgba(22,22,22,0.98), rgba(10,10,10,0.99)) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 12px 12px 0 0 !important;
    padding: 14px 34px !important;
    min-height: 58px !important;
    min-width: 150px !important;
    justify-content: center !important;
    box-shadow: 0 0 0 rgba(255,255,255,0) !important;
    transition: all 0.25s ease !important;
}

/* inner label */
.stTabs [data-baseweb="tab"] p,
.stTabs [data-baseweb="tab"] span,
.stTabs [data-baseweb="tab"] div {
    color: #f8fbff !important;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    font-size: 19.5px !important;
    font-weight: 850 !important;
    letter-spacing: 0 !important;
    text-shadow:
        0 0 7px rgba(255,255,255,0.12),
        0 0 12px rgba(255,178,30,0.06) !important;
    margin: 0 !important;
}

/* hover */
.stTabs [data-baseweb="tab"]:hover {
    border-color: rgba(255,255,255,0.28) !important;
    box-shadow:
        0 0 10px rgba(255,255,255,0.10),
        0 0 18px rgba(255,255,255,0.08) !important;
    transform: translateY(-1px);
}

.stTabs [data-baseweb="tab"]:hover p,
.stTabs [data-baseweb="tab"]:hover span,
.stTabs [data-baseweb="tab"]:hover div {
    color: #ffffff !important;
    text-shadow: 0 0 10px rgba(255,255,255,0.20) !important;
}

/* selected tab */
.stTabs [aria-selected="true"] {
    background: linear-gradient(180deg, rgba(41,28,11,0.98), rgba(18,14,8,1)) !important;
    border-color: rgba(255,255,255,0.35) !important;
    border-bottom: 2px solid #f0a72a !important;
    box-shadow:
        0 0 12px rgba(255,255,255,0.16),
        0 0 24px rgba(255,255,255,0.12),
        inset 0 -2px 0 rgba(255,255,255,0.75) !important;
}

.stTabs [aria-selected="true"] p,
.stTabs [aria-selected="true"] span,
.stTabs [aria-selected="true"] div {
    color: #ffffff !important;
    font-weight: 800 !important;
    text-shadow: 0 0 12px rgba(255,255,255,0.25) !important;
}

.small-note {
    font-size: 0.85rem;
    color: #ffffff !important;
    opacity: 0.82;
}

hr {
    border: none;
    border-top: 1px solid rgba(255,255,255,0.08);
}

/* Premium stat cards — unified neon amber */
.metric-card {
    position: relative;
    background:
        radial-gradient(circle at top left, rgba(255,178,30,0.09), transparent 38%),
        linear-gradient(180deg, rgba(10,10,10,0.99), rgba(3,3,3,1));
    border: 1px solid rgba(255,178,30,0.28);
    border-radius: 20px;
    padding: 14px 16px 12px 16px;
    min-height: 96px;
    box-shadow:
        0 0 0 1px rgba(255,178,30,0.05),
        0 0 14px rgba(255,178,30,0.12),
        0 10px 28px rgba(0,0,0,0.38);
    transition:
        transform 0.25s ease,
        border-color 0.25s ease,
        box-shadow 0.25s ease;
    overflow: hidden;
}

.metric-card:hover {
    transform: translateY(-3px);
    border-color: rgba(255,199,92,0.58);
    box-shadow:
        0 0 0 1px rgba(255,199,92,0.12),
        0 0 20px rgba(255,178,30,0.24),
        0 0 38px rgba(255,145,0,0.14),
        0 14px 34px rgba(0,0,0,0.46);
}

.metric-card.secondary-card {
    min-height: 82px;
    padding: 12px 16px 10px 16px;
    background:
        radial-gradient(circle at top left, rgba(255,178,30,0.07), transparent 36%),
        linear-gradient(180deg, rgba(9,9,9,0.99), rgba(3,3,3,1));
    border-color: rgba(255,178,30,0.24);
    box-shadow:
        0 0 12px rgba(255,178,30,0.10),
        0 9px 26px rgba(0,0,0,0.34);
}

.metric-card.glow-card {
    border-color: rgba(255,199,92,0.56);
    box-shadow:
        0 0 0 1px rgba(255,199,92,0.10),
        0 0 22px rgba(255,178,30,0.24),
        0 0 42px rgba(255,145,0,0.14),
        0 14px 34px rgba(0,0,0,0.44);
}

.metric-accent {
    position: absolute;
    top: 0;
    left: 14px;
    right: 14px;
    height: 3px;
    border-radius: 999px;
    opacity: 1;
}

.metric-main {
    min-width: 0;
    margin-top: 6px;
}

.metric-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    min-height: 1.45rem;
    margin: 0 0 6px 0;
}

.metric-head-left {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
}

.metric-icon {
    width: 1.55rem;
    min-width: 1.55rem;
    height: 1.55rem;
    font-size: 1.42rem !important;
    line-height: 1 !important;
    opacity: 1;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    filter:
        drop-shadow(0 0 7px rgba(255,178,30,0.34))
        drop-shadow(0 0 12px rgba(255,178,30,0.16));
}

.big-transfer-icon {
    color: #FFD97C !important;
    font-size: 1.68rem !important;
    font-weight: 700 !important;
    line-height: 1 !important;
    letter-spacing: -0.03em;
    transform: translateY(-1px);
    text-shadow:
        0 0 4px rgba(255,221,142,0.65),
        0 0 10px rgba(255,178,30,0.38),
        0 0 18px rgba(255,145,0,0.18);
    filter:
        drop-shadow(0 0 5px rgba(255,205,72,0.26))
        drop-shadow(0 0 12px rgba(255,145,0,0.12));
}


/* Ethereum logo styling for the KPI card */
.eth-price-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    line-height: 1 !important;
}

.metric-card.compact-kpi .metric-icon svg {
    width: 46px;
    height: 46px;
    display: block;
    overflow: visible;
}

.eth-price-svg {
    filter:
        drop-shadow(0 0 6px rgba(175, 200, 255, 0.36))
        drop-shadow(0 0 13px rgba(112, 146, 255, 0.20))
        drop-shadow(0 0 22px rgba(102, 120, 255, 0.10));
}

.big-transfer-svg {
    filter:
        drop-shadow(0 0 6px rgba(255, 221, 142, 0.36))
        drop-shadow(0 0 14px rgba(255, 178, 30, 0.20))
        drop-shadow(0 0 24px rgba(255, 145, 0, 0.10));
}


/* Glowing icon used only for the Fear & Greed card */
.fear-greed-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 1.62rem !important;
    line-height: 1 !important;
    color: #FFFFFF !important;
    transform: translateY(-1px);
    text-shadow:
        0 0 3px rgba(255,255,255,0.95),
        0 0 7px rgba(255,255,255,0.72),
        0 0 13px rgba(235,245,255,0.46),
        0 0 21px rgba(215,232,255,0.24);
    filter:
        drop-shadow(0 0 5px rgba(255,255,255,0.34))
        drop-shadow(0 0 11px rgba(220,238,255,0.18));
}

.metric-label {
    font-size: 1.72rem !important;
    font-weight: 850 !important;
    line-height: 1.15 !important;
    letter-spacing: 0 !important;
    color: #F8E6BC !important;
    text-transform: none !important;
    white-space: nowrap;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    text-shadow:
        0 0 8px rgba(255,178,30,0.12),
        0 0 14px rgba(255,178,30,0.06);
}

.metric-value {
    font-size: 2.80rem;
    line-height: 1.02;
    font-weight: 900;
    color: #ffffff !important;
    letter-spacing: -0.6px;
    margin: 18px 0 0 0 !important;
    padding: 0 !important;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    text-shadow:
        0 0 8px rgba(255,255,255,0.10),
        0 0 14px rgba(255,178,30,0.08);
}

.secondary-card .metric-value {
    font-size: 2.50rem;
}

.metric-badge {
    font-size: 1.00rem !important;
    font-weight: 850 !important;
    line-height: 1 !important;
    padding: 6px 12px !important;
    border-radius: 999px;
    white-space: nowrap;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    letter-spacing: 0.1px;
    text-shadow: 0 0 8px rgba(255,178,30,0.16);
    box-shadow:
        0 0 10px rgba(255,178,30,0.10),
        inset 0 1px 0 rgba(255,255,255,0.04);
}


/* Keep the primary cards aligned with the refined gauge card */
.metric-card:not(.secondary-card) {
    min-height: 154px;
}

/* Refined Fear & Greed Index gauge card */
.st-key-fear_greed_index_card {
    position: relative;
    overflow: hidden;
    min-height: 252px !important;
    height: auto !important;
    padding: 16px 20px 18px 20px !important;
    box-sizing: border-box !important;
    background:
        radial-gradient(circle at 50% 82%, rgba(255,178,30,0.08), transparent 42%),
        radial-gradient(circle at top left, rgba(255,178,30,0.09), transparent 40%),
        linear-gradient(180deg, rgba(10,10,10,0.99), rgba(3,3,3,1)) !important;
    border: 1px solid rgba(255,178,30,0.30) !important;
    border-radius: 20px !important;
    box-shadow:
        0 0 0 1px rgba(255,178,30,0.05),
        0 0 16px rgba(255,178,30,0.13),
        0 10px 28px rgba(0,0,0,0.38) !important;
    transition:
        transform 0.25s ease,
        border-color 0.25s ease,
        box-shadow 0.25s ease;
}

.st-key-fear_greed_index_card::before {
    content: "";
    position: absolute;
    top: 0;
    left: 14px;
    right: 14px;
    height: 3px;
    border-radius: 999px;
    background:
        linear-gradient(
            90deg,
            rgba(255,178,30,0),
            rgba(255,178,30,1),
            rgba(255,178,30,0)
        );
    box-shadow:
        0 0 18px rgba(255,178,30,0.40),
        0 0 34px rgba(255,145,0,0.15);
}

.st-key-fear_greed_index_card:hover {
    transform: translateY(-3px);
    border-color: rgba(255,199,92,0.58) !important;
    box-shadow:
        0 0 0 1px rgba(255,199,92,0.12),
        0 0 20px rgba(255,178,30,0.24),
        0 0 38px rgba(255,145,0,0.14),
        0 14px 34px rgba(0,0,0,0.46) !important;
}

.st-key-fear_greed_index_card [data-testid="stVerticalBlockBorderWrapper"] {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    padding: 0 !important;
}


.fg-index-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin: 0 0 4px 0;
    min-height: 82px;
}

.fg-index-title-wrap {
    display: inline-flex;
    align-items: center;
    gap: 18px;
    min-width: 0;
}

/* Same circle dimensions as the three KPI cards */
.fg-index-icon-ring {
    width: 82px;
    min-width: 82px;
    height: 82px;
    border-radius: 999px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background:
        radial-gradient(circle at 35% 30%, rgba(255,194,85,0.18), rgba(255,154,0,0.06) 48%, rgba(255,154,0,0.02) 70%),
        linear-gradient(180deg, rgba(28,20,9,0.95), rgba(12,10,7,0.98));
    border: 1px solid rgba(255,178,30,0.46);
    box-shadow:
        inset 0 0 18px rgba(255,178,30,0.10),
        0 0 18px rgba(255,178,30,0.16),
        0 0 34px rgba(255,145,0,0.08);
}

/* Coloured icon only — no white/neon glow */
.fg-index-icon {
    width: auto;
    height: auto;
    min-width: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 2.55rem !important;
    line-height: 1 !important;
    transform: translateY(-1px);

    background: linear-gradient(
        90deg,
        #D94D39 0%,
        #F0A34A 34%,
        #E4CF52 55%,
        #80D058 75%,
        #24B768 100%
    );
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent !important;
    -webkit-text-fill-color: transparent !important;

    text-shadow: none !important;
    filter: none !important;
}

/* Match the top KPI card header typography exactly */
.fg-index-title {
    font-size: 1.02rem !important;
    font-weight: 740 !important;
    line-height: 1.14 !important;
    letter-spacing: 0.42px !important;
    color: #F8E6BC !important;
    white-space: normal !important;
    text-transform: uppercase !important;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    text-shadow:
        0 0 8px rgba(255,178,30,0.10),
        0 0 14px rgba(255,178,30,0.04);
    margin: 0 !important;
}

.fg-index-badge {
    flex-shrink: 0;
    padding: 7px 13px;
    border-radius: 999px;
    border: 1px solid rgba(255,178,30,0.34);
    background: rgba(255,178,30,0.11);
    color: #FFB21E !important;
    font-size: 0.84rem;
    font-weight: 850;
    line-height: 1;
    text-shadow: 0 0 8px rgba(255,178,30,0.16);
    box-shadow:
        0 0 10px rgba(255,178,30,0.08),
        inset 0 1px 0 rgba(255,255,255,0.04);
}

/* Gauge region */
.st-key-fear_greed_index_card [data-testid="stPlotlyChart"] {
    margin-top: 10px !important;
    margin-bottom: -2px !important;
    transform: translateX(-26px);
}

.fg-index-scale {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    align-items: center;
    width: 88%;
    max-width: 660px;
    min-width: 320px;
    padding: 0;
    margin: 4px auto 2px auto;
    transform: translateX(-26px);
    font-size: 1.02rem;
    font-weight: 950;
    letter-spacing: 0.10em;
}

.fg-index-scale .fear-side {
    color: #E87458 !important;
    text-align: left;
}

.fg-index-scale .neutral-side {
    color: #E9D15B !important;
    text-align: center;
}

.fg-index-scale .greed-side {
    color: #54D177 !important;
    text-align: right;
}

/* Right-side sentiment insight — open layout, no nested card */
.fg-insight-panel {
    min-height: 188px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 12px 18px 10px 4px;
    margin-top: 4px;
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    overflow: visible;
}

.fg-insight-content {
    width: 92%;
    margin: 0;
    transform: translateX(-8px);
    text-align: left;
}

.fg-insight-kicker {
    color: #BDB6AA !important;
    font-size: 1.05rem;
    font-weight: 900;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin-bottom: 13px;
    text-align: left;
}

.fg-insight-status-row {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 10px;
    margin-bottom: 13px;
}

.fg-live-dot {
    width: 9px;
    height: 9px;
    min-width: 9px;
    border-radius: 50%;
    background: #FFB21E;
    box-shadow:
        0 0 8px rgba(255,178,30,0.72),
        0 0 16px rgba(255,178,30,0.32);
}

.fg-insight-status {
    font-size: 1.78rem;
    font-weight: 950;
    letter-spacing: -0.25px;
    line-height: 1.05;
}

.fg-insight-description {
    color: #DDD6C9 !important;
    font-size: 1.16rem;
    line-height: 1.48;
    margin-bottom: 15px;
    max-width: 520px;
    text-align: left;
}

.fg-score-row,
.fg-source-row {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 26px;
    max-width: 520px;
}

.fg-score-row {
    padding-top: 11px;
    margin-top: 6px;
    border-top: 1px solid rgba(255,255,255,0.08);
}

.fg-source-row {
    padding-top: 9px;
}

.fg-score-label,
.fg-source-label {
    color: #989188 !important;
    font-size: 0.95rem;
    font-weight: 850;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    min-width: 132px;
    flex: 0 0 132px;
}

.fg-score-value {
    color: #F8E6BC !important;
    font-size: 1.16rem;
    font-weight: 950;
    display: inline-flex;
    align-items: baseline;
    gap: 4px;
}

.fg-score-value-main {
    color: #F3B33E !important;
}

.fg-score-value-total {
    color: #F4F1EB !important;
}

.fg-source-value {
    color: #F4F1EB !important;
    font-size: 1.02rem;
    font-weight: 800;
    text-transform: lowercase;
}

/* Full-width card refinements */
.st-key-fear_greed_index_card {
    min-height: 268px !important;
    padding: 16px 20px 18px 20px !important;
}

@media (max-width: 1100px) {
    .fg-insight-panel {
        margin-top: 10px;
        min-height: auto;
    }

    .fg-index-scale {
        min-width: 240px;
        width: 90%;
    }
}

/* =========================
   OVERVIEW CONTENT CARDS
   ========================= */
.st-key-overview_timeline_card,
.st-key-overview_summary_card,
.st-key-overview_transactions_card,
.st-key-watchlist_results_card,
.st-key-market_indicators_card,
.st-key-market_news_card,
.st-key-raw_eth_native_card,
.st-key-raw_eth_erc20_card,
.st-key-raw_btc_network_card,
.st-key-raw_eth_watchlist_card,
.st-key-raw_btc_watchlist_card {
    position: relative;
    overflow: hidden;
    background:
        radial-gradient(circle at top left, rgba(255,178,30,0.06), transparent 38%),
        linear-gradient(180deg, rgba(14,14,14,0.98), rgba(6,6,6,0.99)) !important;
    border: 1px solid rgba(255,178,30,0.20) !important;
    border-radius: 22px !important;
    padding: 18px 18px 14px 18px !important;
    margin-bottom: 18px !important;
    box-shadow:
        0 12px 30px rgba(0,0,0,0.34),
        0 0 14px rgba(255,178,30,0.06),
        inset 0 1px 0 rgba(255,255,255,0.035) !important;
    transition:
        transform 0.24s ease,
        border-color 0.24s ease,
        box-shadow 0.24s ease;
}

.st-key-overview_timeline_card::before,
.st-key-overview_summary_card::before,
.st-key-overview_transactions_card::before,
.st-key-watchlist_results_card::before,
.st-key-market_indicators_card::before,
.st-key-market_news_card::before,
.st-key-raw_eth_native_card::before,
.st-key-raw_eth_erc20_card::before,
.st-key-raw_btc_network_card::before,
.st-key-raw_eth_watchlist_card::before,
.st-key-raw_btc_watchlist_card::before {
    content: "";
    position: absolute;
    top: 0;
    left: 18px;
    right: 18px;
    height: 3px;
    border-radius: 999px;
    background:
        linear-gradient(
            90deg,
            rgba(255,178,30,0),
            rgba(255,178,30,0.98),
            rgba(255,178,30,0)
        );
    box-shadow:
        0 0 14px rgba(255,178,30,0.34),
        0 0 28px rgba(255,145,0,0.12);
}

.st-key-overview_timeline_card:hover,
.st-key-overview_summary_card:hover,
.st-key-overview_transactions_card:hover,
.st-key-watchlist_results_card:hover,
.st-key-market_indicators_card:hover,
.st-key-market_news_card:hover,
.st-key-raw_eth_native_card:hover,
.st-key-raw_eth_erc20_card:hover,
.st-key-raw_btc_network_card:hover,
.st-key-raw_eth_watchlist_card:hover,
.st-key-raw_btc_watchlist_card:hover {
    transform: translateY(-2px);
    border-color: rgba(255,255,255,0.42) !important;
    box-shadow:
        0 16px 36px rgba(0,0,0,0.40),
        0 0 12px rgba(255,255,255,0.12),
        0 0 26px rgba(255,178,30,0.09),
        inset 0 1px 0 rgba(255,255,255,0.05) !important;
}

/* Remove Streamlit's default bordered-container shell */
.st-key-overview_timeline_card [data-testid="stVerticalBlockBorderWrapper"],
.st-key-overview_summary_card [data-testid="stVerticalBlockBorderWrapper"],
.st-key-overview_transactions_card [data-testid="stVerticalBlockBorderWrapper"],
.st-key-watchlist_results_card [data-testid="stVerticalBlockBorderWrapper"],
.st-key-market_indicators_card [data-testid="stVerticalBlockBorderWrapper"],
.st-key-market_news_card [data-testid="stVerticalBlockBorderWrapper"],
.st-key-raw_eth_native_card [data-testid="stVerticalBlockBorderWrapper"],
.st-key-raw_eth_erc20_card [data-testid="stVerticalBlockBorderWrapper"],
.st-key-raw_btc_network_card [data-testid="stVerticalBlockBorderWrapper"],
.st-key-raw_eth_watchlist_card [data-testid="stVerticalBlockBorderWrapper"],
.st-key-raw_btc_watchlist_card [data-testid="stVerticalBlockBorderWrapper"] {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    padding: 0 !important;
}

/* Card heading used above the dataframe */
.overview-card-heading {
    font-size: 1.70rem !important;
    font-weight: 900 !important;
    line-height: 1.08 !important;
    letter-spacing: -0.35px !important;
    color: #ffffff !important;
    margin: 0.10rem 0 1rem 0 !important;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    text-shadow:
        0 0 8px rgba(255,255,255,0.16),
        0 0 16px rgba(255,178,30,0.10);
}

/* Make the dataframe itself look cleaner inside its card */
.st-key-overview_transactions_card [data-testid="stDataFrame"] {
    border: 1px solid rgba(255,178,30,0.12) !important;
    border-radius: 14px !important;
    overflow: hidden !important;
    box-shadow: 0 8px 24px rgba(0,0,0,0.22);
}


/* =========================
   MARKET / WATCHLIST / RAW DATA CARDS
   ========================= */

/* Dataframes inside the themed cards */
.st-key-watchlist_results_card [data-testid="stDataFrame"],
.st-key-market_news_card [data-testid="stDataFrame"],
.st-key-raw_eth_native_card [data-testid="stDataFrame"],
.st-key-raw_eth_erc20_card [data-testid="stDataFrame"],
.st-key-raw_btc_network_card [data-testid="stDataFrame"],
.st-key-raw_eth_watchlist_card [data-testid="stDataFrame"],
.st-key-raw_btc_watchlist_card [data-testid="stDataFrame"] {
    border: 1px solid rgba(255,178,30,0.14) !important;
    border-radius: 14px !important;
    overflow: hidden !important;
    box-shadow:
        0 8px 24px rgba(0,0,0,0.24),
        0 0 12px rgba(255,178,30,0.04);
}

/* Market indicator mini-cards */
.st-key-market_indicators_card div[data-testid="stMetric"] {
    background:
        radial-gradient(circle at top left, rgba(255,178,30,0.07), transparent 42%),
        linear-gradient(180deg, rgba(17,17,17,0.98), rgba(8,8,8,0.99)) !important;
    border: 1px solid rgba(255,178,30,0.20) !important;
    border-radius: 18px !important;
    min-height: 112px !important;
    padding: 14px 16px !important;
    box-shadow:
        0 8px 24px rgba(0,0,0,0.28),
        inset 0 1px 0 rgba(255,255,255,0.03);
}

.st-key-market_indicators_card div[data-testid="stMetricLabel"],
.st-key-market_indicators_card div[data-testid="stMetricLabel"] p,
.st-key-market_indicators_card div[data-testid="stMetricLabel"] span,
.st-key-market_indicators_card div[data-testid="stMetricLabel"] div {
    color: #F8E6BC !important;
    font-size: 1.22rem !important;
    font-weight: 850 !important;
    line-height: 1.2 !important;
    letter-spacing: 0 !important;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    text-shadow:
        0 0 7px rgba(255,255,255,0.10),
        0 0 12px rgba(255,178,30,0.08) !important;
}

/* Force Streamlit's inner label paragraph to inherit the larger size */
.st-key-market_indicators_card [data-testid="stMetricLabel"] > div,
.st-key-market_indicators_card [data-testid="stMetricLabel"] > div > p {
    font-size: 1.22rem !important;
    font-weight: 850 !important;
}

.st-key-market_indicators_card div[data-testid="stMetricValue"] {
    color: #ffffff !important;
    font-size: 2rem !important;
    font-weight: 900 !important;
}

/* Empty-state / info boxes */
.st-key-watchlist_results_card [data-testid="stAlert"],
.st-key-market_news_card [data-testid="stAlert"] {
    background: rgba(255,178,30,0.06) !important;
    border: 1px solid rgba(255,178,30,0.16) !important;
    border-radius: 14px !important;
    color: #F6E8C8 !important;
}


/* Uniform typography for primary KPI/dashboard card headers */
.metric-label {
    font-size: 1.72rem !important;
    font-weight: 900 !important;
    line-height: 1.15 !important;
    letter-spacing: -0.1px !important;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
}

/* Keep FEAR & GREED INDEX title at the same compact size as BIG TRANSFERS header */
.fg-index-title {
    font-size: 1.02rem !important;
    line-height: 1.14 !important;
    font-weight: 740 !important;
    letter-spacing: 0.42px !important;
    text-transform: uppercase !important;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
}


/* =========================
   CLICKABLE ALERTS
   ========================= */
.alert-card-link,
.alert-card-link:visited,
.alert-card-link:hover,
.alert-card-link:active {
    display: block;
    color: inherit !important;
    text-decoration: none !important;
    cursor: pointer;
}

.alert-card-link .alert-card {
    cursor: pointer;
}

.alert-card-link .alert-card:hover {
    transform: translateY(-3px) scale(1.003);
}

/* =========================
   TRANSACTION DETAIL VIEW
   ========================= */
.tx-detail-shell {
    margin-top: 4px;
}

.tx-back-row {
    display: flex;
    align-items: center;
    margin-bottom: 18px;
}

.tx-back-link {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: #F8E6BC !important;
    text-decoration: none !important;
    font-size: 1rem;
    font-weight: 850;
    padding: 8px 12px;
    border: 1px solid rgba(255,178,30,0.22);
    border-radius: 999px;
    background: rgba(255,178,30,0.055);
    transition: all 0.22s ease;
}

.tx-back-link:hover {
    border-color: rgba(255,199,92,0.55);
    box-shadow:
        0 0 12px rgba(255,178,30,0.15),
        0 0 24px rgba(255,178,30,0.08);
    transform: translateX(-2px);
}

.tx-page-title {
    font-size: 2.65rem !important;
    line-height: 1.04 !important;
    font-weight: 900 !important;
    letter-spacing: -0.7px !important;
    color: #FFFFFF !important;
    margin: 0 0 18px 0 !important;
    text-shadow:
        0 0 10px rgba(255,255,255,0.10),
        0 0 18px rgba(255,178,30,0.08);
}

.tx-summary-card,
.tx-info-card,
.tx-transfer-card {
    position: relative;
    overflow: hidden;
    background:
        radial-gradient(circle at top left, rgba(255,178,30,0.075), transparent 38%),
        linear-gradient(180deg, rgba(12,12,12,0.99), rgba(5,5,5,1));
    border: 1px solid rgba(255,178,30,0.27);
    border-radius: 22px;
    box-shadow:
        0 0 0 1px rgba(255,178,30,0.04),
        0 0 16px rgba(255,178,30,0.09),
        0 12px 32px rgba(0,0,0,0.34);
}

.tx-summary-card::before,
.tx-info-card::before,
.tx-transfer-card::before {
    content: "";
    position: absolute;
    top: 0;
    left: 18px;
    right: 18px;
    height: 2px;
    border-radius: 999px;
    background:
        linear-gradient(
            90deg,
            rgba(255,178,30,0),
            rgba(255,178,30,0.96),
            rgba(255,178,30,0)
        );
    box-shadow: 0 0 16px rgba(255,178,30,0.28);
}

.tx-summary-card {
    padding: 20px 22px;
    margin-bottom: 18px;
}

.tx-summary-main {
    display: flex;
    justify-content: space-between;
    gap: 24px;
    align-items: flex-start;
}

.tx-summary-left {
    display: flex;
    align-items: flex-start;
    gap: 16px;
    min-width: 0;
}

.tx-asset-icon {
    width: 58px;
    height: 58px;
    min-width: 58px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 1.75rem;
    background:
        radial-gradient(circle at 35% 30%, rgba(255,255,255,0.10), transparent 42%),
        rgba(255,178,30,0.08);
    border: 1px solid rgba(255,178,30,0.38);
    box-shadow:
        0 0 14px rgba(255,178,30,0.20),
        0 8px 20px rgba(0,0,0,0.25);
}

.tx-summary-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    margin-bottom: 8px;
}

.tx-summary-amount {
    color: #FFFFFF !important;
    font-size: 1.75rem;
    font-weight: 950;
    line-height: 1.12;
    letter-spacing: -0.4px;
    margin-bottom: 6px;
}

.tx-summary-route {
    color: #C8D0D8 !important;
    font-size: 1rem;
    line-height: 1.42;
    word-break: break-word;
}

.tx-summary-time {
    color: #E9E1D2 !important;
    font-size: 0.95rem;
    font-weight: 800;
    white-space: nowrap;
    padding-top: 3px;
}

.tx-section-title {
    font-size: 1.65rem !important;
    font-weight: 900 !important;
    color: #FFFFFF !important;
    letter-spacing: -0.35px;
    margin: 0 0 14px 0;
}

.tx-info-card {
    padding: 20px 22px;
    margin-bottom: 18px;
}

.tx-detail-grid {
    display: grid;
    grid-template-columns: 150px minmax(0, 1fr);
    column-gap: 22px;
    row-gap: 13px;
    align-items: start;
}

.tx-detail-label {
    color: #A99F90 !important;
    font-size: 0.88rem;
    font-weight: 850;
    letter-spacing: 0.02em;
}

.tx-detail-value {
    color: #F5F5F5 !important;
    font-size: 1rem;
    font-weight: 750;
    line-height: 1.42;
    word-break: break-all;
}

.tx-hash-value {
    color: #E7C473 !important;
}

.tx-transfer-card {
    padding: 20px 22px 22px 22px;
    margin-bottom: 18px;
}

.tx-transfer-grid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 110px minmax(0, 1fr);
    gap: 18px;
    align-items: center;
}

.tx-wallet-label {
    color: #A99F90 !important;
    font-size: 0.82rem;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: 0.11em;
    margin-bottom: 7px;
}

.tx-wallet-address {
    color: #F4F4F4 !important;
    font-size: 1rem;
    font-weight: 760;
    word-break: break-all;
    line-height: 1.42;
}

.tx-wallet-meta {
    color: #A9A39A !important;
    font-size: 0.80rem;
    font-weight: 700;
    margin-top: 6px;
}

.tx-arrow-wrap {
    text-align: center;
}

.tx-arrow {
    width: 52px;
    height: 52px;
    margin: 0 auto 7px auto;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    color: #FFFFFF !important;
    font-size: 1.45rem;
    border: 1px solid rgba(255,178,30,0.34);
    background: rgba(255,178,30,0.08);
    box-shadow:
        0 0 12px rgba(255,178,30,0.13),
        inset 0 1px 0 rgba(255,255,255,0.04);
}

.tx-transfer-amount {
    color: #F8E6BC !important;
    font-size: 0.82rem;
    font-weight: 900;
    white-space: nowrap;
}

.tx-explorer-link {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    margin-top: 2px;
    color: #F8E6BC !important;
    font-size: 0.93rem;
    font-weight: 850;
    text-decoration: none !important;
    border-bottom: 1px solid rgba(255,178,30,0.30);
}

.tx-explorer-link:hover {
    color: #FFFFFF !important;
    border-bottom-color: rgba(255,255,255,0.55);
}

.tx-not-found {
    padding: 26px;
    border: 1px solid rgba(255,178,30,0.22);
    border-radius: 20px;
    background: rgba(255,178,30,0.04);
    color: #E9E1D2 !important;
    font-size: 1rem;
    line-height: 1.5;
}

@media (max-width: 1100px) {
    .tx-summary-main {
        flex-direction: column;
    }

    .tx-summary-time {
        white-space: normal;
    }

    .tx-transfer-grid {
        grid-template-columns: 1fr;
        text-align: left;
    }

    .tx-arrow-wrap {
        text-align: left;
    }

    .tx-arrow {
        margin-left: 0;
    }
}


/* =========================
   NEWS TAB
   ========================= */
.news-hero {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 20px;
    margin: 18px 4px 20px 4px;
}

.news-page-title {
    color: #FFFFFF !important;
    font-size: 2.25rem;
    font-weight: 900;
    line-height: 1.04;
    letter-spacing: -0.55px;
    text-shadow:
        0 0 9px rgba(255,255,255,0.09),
        0 0 18px rgba(255,178,30,0.07);
}

.news-page-subtitle {
    margin-top: 7px;
    color: #AFA79A !important;
    font-size: 0.98rem;
    font-weight: 650;
}

.news-summary-card {
    position: relative;
    overflow: hidden;
    padding: 20px 22px;
    margin-bottom: 20px;
    background:
        radial-gradient(circle at top left, rgba(255,178,30,0.08), transparent 35%),
        linear-gradient(180deg, rgba(16,16,16,0.99), rgba(6,6,6,1));
    border: 1px solid rgba(255,178,30,0.25);
    border-radius: 20px;
    box-shadow:
        0 0 0 1px rgba(255,178,30,0.04),
        0 0 14px rgba(255,178,30,0.10),
        0 12px 30px rgba(0,0,0,0.30);
}

.news-summary-card::before {
    content: "";
    position: absolute;
    top: 0;
    left: 18px;
    right: 18px;
    height: 2px;
    border-radius: 999px;
    background:
        linear-gradient(
            90deg,
            rgba(255,178,30,0),
            rgba(255,178,30,0.96),
            rgba(255,178,30,0)
        );
    box-shadow: 0 0 15px rgba(255,178,30,0.25);
}

.news-summary-top {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 10px;
}

.news-summary-label {
    color: #B9B1A4 !important;
    font-size: 0.78rem;
    font-weight: 900;
    letter-spacing: 0.14em;
}

.news-summary-value {
    font-size: 1.03rem;
    font-weight: 900;
}

.news-summary-icon {
    font-size: 1.12rem;
}

.news-sentiment-positive,
.news-positive {
    color: #46D17A !important;
}

.news-sentiment-negative,
.news-negative {
    color: #FF735D !important;
}

.news-sentiment-neutral,
.news-neutral {
    color: #E8C955 !important;
}

.news-feature-title {
    display: inline-block;
    color: #FFFFFF !important;
    text-decoration: none !important;
    font-size: 1.40rem;
    font-weight: 900;
    line-height: 1.35;
    letter-spacing: -0.20px;
    margin-bottom: 8px;
}

.news-feature-title:hover {
    color: #F8E6BC !important;
    text-shadow: 0 0 10px rgba(255,178,30,0.14);
}

.news-feature-description {
    color: #DDD7CD !important;
    font-size: 1rem;
    line-height: 1.50;
    max-width: 950px;
}

.news-feature-meta {
    display: flex;
    gap: 14px;
    margin-top: 12px;
    color: #8F897F !important;
    font-size: 0.82rem;
    font-weight: 750;
}

.news-feed-heading {
    color: #F4F8FF !important;
    font-size: 2.20rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    line-height: 1.1;
    margin: 22px 0 14px 0;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
}


.news-story-card-wrap {
    position: relative;
    display: block;
    margin-bottom: 14px;
}

.news-story-hitbox {
    position: absolute;
    inset: 0;
    z-index: 10;
    border-radius: 20px;
    text-decoration: none !important;
    cursor: pointer;
}

.news-story-hitbox:focus-visible {
    outline: 2px solid rgba(255,255,255,0.78);
    outline-offset: 2px;
}

.news-story-card {
    position: relative;
    overflow: hidden;
    padding: 16px 18px;
    background:
        linear-gradient(
            180deg,
            rgba(20,20,20,0.98) 0%,
            rgba(10,10,10,0.99) 100%
        );
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 20px;
    box-shadow:
        0 10px 26px rgba(0,0,0,0.24),
        inset 0 1px 0 rgba(255,255,255,0.05);
    transition:
        transform 0.22s ease,
        box-shadow 0.22s ease,
        border-color 0.22s ease;
}

.news-story-card::before {
    content: "";
    position: absolute;
    left: 14px;
    right: 14px;
    top: 0;
    height: 3px;
    border-radius: 999px;
    background:
        linear-gradient(
            90deg,
            rgba(212,134,18,0),
            rgba(212,134,18,0.95),
            rgba(212,134,18,0)
        );
    box-shadow: 0 0 14px rgba(212,134,18,0.38);
}

.news-story-card-wrap:hover .news-story-card {
    transform: translateY(-3px);
    border-color: rgba(255,255,255,0.62);
    box-shadow:
        0 16px 34px rgba(0,0,0,0.34),
        0 0 10px rgba(255,255,255,0.22),
        0 0 24px rgba(255,255,255,0.16),
        0 0 42px rgba(255,255,255,0.08),
        inset 0 1px 0 rgba(255,255,255,0.10);
}

.news-story-main {
    position: relative;
    z-index: 2;
    display: grid;
    grid-template-columns: 54px minmax(0, 1fr) 118px;
    gap: 14px;
    align-items: center;
}

.news-story-icon {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 1.40rem;
    font-weight: 950;
    background:
        radial-gradient(
            circle at 35% 30%,
            rgba(255,255,255,0.08),
            transparent 42%
        ),
        rgba(255,178,30,0.055);
    border: 1px solid rgba(255,178,30,0.42);
    box-shadow:
        0 0 12px rgba(255,178,30,0.15),
        0 7px 18px rgba(0,0,0,0.24),
        inset 0 1px 0 rgba(255,255,255,0.04);
}

.news-story-content {
    min-width: 0;
}

.news-story-title {
    color: #FFFFFF !important;
    font-size: 1.34rem;
    font-weight: 900;
    line-height: 1.28;
    letter-spacing: -0.20px;
    margin-bottom: 5px;
}

.news-story-source {
    color: #D39A2E !important;
    font-size: 0.90rem;
    font-weight: 800;
    margin-top: 2px;
}

.news-story-description {
    color: #C6D0DA !important;
    font-size: 1.00rem;
    line-height: 1.42;
    margin-top: 7px;
}

.news-story-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    margin-top: 10px;
}

.news-tag {
    display: inline-flex;
    align-items: center;
    padding: 5px 10px;
    border-radius: 999px;
    background: rgba(255,178,30,0.07);
    border: 1px solid rgba(255,178,30,0.18);
    color: #F1D9A5 !important;
    font-size: 0.75rem;
    font-weight: 850;
    line-height: 1;
}

.news-story-side {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    justify-content: center;
    gap: 12px;
    text-align: right;
}

.news-story-time {
    color: #D7DEE7 !important;
    font-size: 0.88rem;
    font-weight: 850;
    white-space: nowrap;
}

.news-story-sentiment {
    font-size: 0.85rem;
    font-weight: 900;
    white-space: nowrap;
}

.news-positive {
    color: #47D17A !important;
}

.news-negative {
    color: #FF755F !important;
}

.news-neutral {
    color: #E8C955 !important;
}

@media (max-width: 980px) {
    .news-story-main {
        grid-template-columns: 52px minmax(0, 1fr);
        align-items: start;
    }

    .news-story-side {
        grid-column: 2;
        flex-direction: row;
        justify-content: flex-start;
        align-items: center;
        gap: 16px;
        text-align: left;
        margin-top: 3px;
    }
}

.news-empty {
    padding: 28px;
    border-radius: 18px;
    border: 1px solid rgba(255,178,30,0.18);
    background: rgba(255,178,30,0.035);
}

.news-empty-title {
    color: #FFFFFF !important;
    font-size: 1.25rem;
    font-weight: 900;
}

.news-empty-copy {
    color: #AAA397 !important;
    margin-top: 7px;
    font-size: 0.92rem;
}

@media (max-width: 980px) {
    .news-story-main {
        grid-template-columns: 46px minmax(0, 1fr);
    }

    .news-story-side {
        grid-column: 2;
        text-align: left;
        display: flex;
        gap: 16px;
        align-items: center;
    }

    .news-story-sentiment {
        margin-top: 0;
    }
}


/* =========================
   TOP NAVIGATION BAR
   ========================= */
.brand-top-nav {
    position: absolute;
    top: 0.62rem;
    left: 50% !important;
    right: auto !important;
    transform: translateX(-50%) !important;
    z-index: 10020;

    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 2px;

    padding: 5px 8px;
    border-radius: 999px;

    background:
        radial-gradient(circle at 50% 0%, rgba(255,178,30,0.06), transparent 60%),
        linear-gradient(180deg, rgba(24,24,24,0.98), rgba(10,10,10,0.99));

    border: 1px solid rgba(255,255,255,0.09);

    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.045),
        0 0 0 1px rgba(255,178,30,0.025),
        0 10px 26px rgba(0,0,0,0.34);

    white-space: nowrap;
}

.brand-top-nav a,
.brand-top-nav a:visited,
.brand-top-nav a:hover,
.brand-top-nav a:active {
    min-width: 96px;
    padding: 12px 18px;

    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;

    border-radius: 999px;
    border: 1px solid transparent;

    color: #E8DFC9 !important;

    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    font-size: 1.02rem !important;
    font-weight: 740 !important;
    line-height: 1 !important;
    letter-spacing: 0.42px !important;
    text-transform: uppercase !important;

    text-align: center;
    text-decoration: none !important;

    transition:
        color 0.20s ease,
        background 0.20s ease,
        border-color 0.20s ease,
        box-shadow 0.20s ease,
        transform 0.20s ease;

    text-shadow:
        0 0 8px rgba(255,178,30,0.09),
        0 0 14px rgba(255,178,30,0.03);
}

.brand-top-nav a .nav-item-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    flex: 0 0 18px;
    color: #F3E6BE;
    opacity: 1;
    filter:
        drop-shadow(0 0 4px rgba(255, 178, 30, 0.18))
        drop-shadow(0 0 8px rgba(255, 178, 30, 0.10));
}

.brand-top-nav a .nav-item-icon svg {
    width: 18px;
    height: 18px;
    display: block;
    stroke: currentColor;
    fill: none;
    stroke-width: 2.25;
    stroke-linecap: round;
    stroke-linejoin: round;
}

.brand-top-nav a:hover .nav-item-icon,
.brand-top-nav a.active .nav-item-icon {
    color: #FFF6DE;
    filter:
        drop-shadow(0 0 5px rgba(255, 178, 30, 0.24))
        drop-shadow(0 0 10px rgba(255, 178, 30, 0.14));
}

.brand-top-nav a .nav-item-label {
    display: inline-block;
    transform: translateY(0.5px);
}

.brand-top-nav a:hover {
    color: #FFFFFF !important;

    background:
        linear-gradient(
            180deg,
            rgba(255,255,255,0.07),
            rgba(255,255,255,0.025)
        );

    border-color: rgba(255,255,255,0.14);

    box-shadow:
        0 0 10px rgba(255,255,255,0.06),
        inset 0 1px 0 rgba(255,255,255,0.035);

    transform: translateY(-1px);
}

.brand-top-nav a.active {
    color: #FFF5DF !important;

    background:
        radial-gradient(circle at 50% 0%, rgba(255,190,70,0.20), transparent 72%),
        linear-gradient(
            180deg,
            rgba(255,178,30,0.20),
            rgba(255,178,30,0.08)
        );

    border-color: rgba(255,178,30,0.40);

    box-shadow:
        0 0 0 1px rgba(255,178,30,0.04),
        0 0 12px rgba(255,178,30,0.14),
        inset 0 1px 0 rgba(255,255,255,0.05);

    text-shadow:
        0 0 7px rgba(255,255,255,0.12),
        0 0 10px rgba(255,178,30,0.08);
}

/* Anchor target for Controls */
#monitoring-controls {
    scroll-margin-top: 94px;
}

/* Slightly tighter at laptop widths */
@media (max-width: 1400px) {
    .brand-top-nav {
        gap: 2px;
    }

    .brand-top-nav a,
    .brand-top-nav a:visited,
    .brand-top-nav a:hover,
    .brand-top-nav a:active {
        min-width: 90px;
        padding: 11px 14px;
        font-size: 0.94rem !important;
        gap: 7px;
    }

    .brand-top-nav a .nav-item-icon,
    .brand-top-nav a .nav-item-icon svg {
        width: 16px;
        height: 16px;
        flex-basis: 16px;
    }
}

@media (max-width: 1050px) {
    .brand-top-nav {
        left: 50% !important;
        right: auto !important;
        transform: translateX(-50%) !important;
    }

    .brand-top-nav a,
    .brand-top-nav a:visited,
    .brand-top-nav a:hover,
    .brand-top-nav a:active {
        min-width: 74px;
        padding-left: 10px;
        padding-right: 10px;
        font-size: 0.86rem !important;
        gap: 6px;
    }

    .brand-top-nav a .nav-item-icon,
    .brand-top-nav a .nav-item-icon svg {
        width: 15px;
        height: 15px;
        flex-basis: 15px;
    }
}


@media (max-width: 1400px) {
    .st-key-session_nav_shell [data-testid="stColumn"] {
        min-width: 118px !important;
    }
}

@media (max-width: 1050px) {
    .st-key-session_nav_shell [data-testid="stColumn"] {
        min-width: 100px !important;
    }
}

@media (max-width: 900px) {
    .brand-top-nav {
        position: relative;
        top: auto;
        left: auto;
        right: auto;
        transform: none;

        margin-top: 0.60rem;

        width: 100%;
        max-width: 100%;

        overflow-x: auto;
        justify-content: flex-start;

        scrollbar-width: none;
    }

    .brand-top-nav::-webkit-scrollbar {
        display: none;
    }

    .brand-top-nav a,
    .brand-top-nav a:visited,
    .brand-top-nav a:hover,
    .brand-top-nav a:active {
        min-width: 96px;
        flex: 0 0 auto;
    }
}


/* =========================================================
   NOVARIS REFINED HOMEPAGE — REFERENCE LAYOUT
   ========================================================= */

/* Brand treatment */
.brand-title {
    color: #F6C45F !important;
    font-size: 3.05rem !important;
    letter-spacing: 0.7px !important;
    text-shadow:
        0 0 4px rgba(255,216,128,0.70),
        0 0 11px rgba(255,178,30,0.32),
        0 0 24px rgba(255,145,0,0.16) !important;
}

.brand-sub {
    max-width: 420px;
    line-height: 1.35;
}

.brand-live-status {
    position: absolute;
    top: 0.95rem;
    right: 1.05rem;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: #DAD6CF !important;
    font-size: 0.82rem;
    font-weight: 800;
    white-space: nowrap;
}

.brand-live-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #55D66B;
    box-shadow:
        0 0 7px rgba(85,214,107,0.72),
        0 0 14px rgba(85,214,107,0.28);
}

/* Compact KPI cards for the home top row */
.metric-card.compact-kpi {
    min-height: 132px !important;
    padding: 15px 18px 14px 18px !important;
}

.metric-card.compact-kpi .metric-main {
    margin-top: 0 !important;
}

.metric-card.compact-kpi .metric-kpi-layout {
    display: flex;
    align-items: center;
    gap: 18px;
    min-height: 102px;
}

.metric-card.compact-kpi .metric-kpi-icon-ring {
    width: 82px;
    min-width: 82px;
    height: 82px;
    border-radius: 999px;
    display: flex;
    align-items: center;
    justify-content: center;
    background:
        radial-gradient(circle at 35% 30%, rgba(255,194,85,0.18), rgba(255,154,0,0.06) 48%, rgba(255,154,0,0.02) 70%),
        linear-gradient(180deg, rgba(28,20,9,0.95), rgba(12,10,7,0.98));
    border: 1px solid rgba(255,178,30,0.46);
    box-shadow:
        inset 0 0 18px rgba(255,178,30,0.10),
        0 0 18px rgba(255,178,30,0.16),
        0 0 34px rgba(255,145,0,0.08);
}

.metric-card.compact-kpi .metric-icon {
    width: auto;
    min-width: 0;
    height: auto;
    font-size: 2.55rem !important;
    line-height: 1 !important;
    filter: none;
}

.metric-card.compact-kpi .metric-kpi-copy {
    display: flex;
    flex-direction: column;
    justify-content: center;
    min-width: 0;
    gap: 7px;
}

.metric-card.compact-kpi .metric-label {
    font-size: 1.02rem !important;
    line-height: 1.14 !important;
    font-weight: 740 !important;
    letter-spacing: 0.42px !important;
    white-space: normal !important;
    text-transform: uppercase !important;
    color: #F8E6BC !important;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    text-shadow:
        0 0 8px rgba(255,178,30,0.10),
        0 0 14px rgba(255,178,30,0.04);
    margin: 0 !important;
}

.metric-card.compact-kpi .metric-value {
    font-size: 2.66rem !important;
    line-height: 1 !important;
    margin: 0 !important;
    letter-spacing: -0.9px;
    color: #ffffff !important;
    text-shadow:
        0 0 8px rgba(255,255,255,0.10),
        0 0 14px rgba(255,178,30,0.06);
}

.metric-card.compact-kpi .metric-subtext {
    margin-top: 2px;
    color: #AFA99E !important;
    font-size: 0.84rem;
    font-weight: 700;
}

.metric-subtext {
    margin-top: 6px;
    color: #AFA99E !important;
    font-size: 0.78rem;
    font-weight: 700;
}

.btc-price-icon {
    color: #FFCF5A !important;
    font-size: 2.75rem !important;
    font-weight: 900 !important;
    text-shadow:
        0 0 6px rgba(255,207,90,0.78),
        0 0 14px rgba(255,178,30,0.38),
        0 0 26px rgba(255,145,0,0.20);
    filter:
        drop-shadow(0 0 4px rgba(255,207,90,0.38))
        drop-shadow(0 0 12px rgba(255,145,0,0.16));
}

/* Mini Fear & Greed KPI */
.mini-fg-card {
    position: relative;
    min-height: 116px;
    box-sizing: border-box;
    overflow: hidden;
    padding: 13px 15px 12px 15px;
    border: 1px solid rgba(255,178,30,0.28);
    border-radius: 20px;
    background:
        radial-gradient(circle at top left, rgba(255,178,30,0.09), transparent 38%),
        linear-gradient(180deg, rgba(10,10,10,0.99), rgba(3,3,3,1));
    box-shadow:
        0 0 0 1px rgba(255,178,30,0.04),
        0 0 14px rgba(255,178,30,0.11),
        0 10px 28px rgba(0,0,0,0.38);
}

.mini-fg-card::before {
    content: "";
    position: absolute;
    left: 14px;
    right: 14px;
    top: 0;
    height: 3px;
    border-radius: 999px;
    background: linear-gradient(90deg, transparent, #FFB21E, transparent);
    box-shadow: 0 0 15px rgba(255,178,30,0.32);
}

.mini-fg-head {
    display: flex;
    align-items: center;
    gap: 10px;
    color: #F8E6BC !important;
    font-size: 1.02rem;
    font-weight: 900;
}

.mini-fg-body {
    margin-top: 10px;
    display: flex;
    align-items: center;
    gap: 14px;
}

.mini-fg-gauge {
    position: relative;
    width: 74px;
    height: 38px;
    overflow: hidden;
    flex: 0 0 auto;
}

.mini-fg-gauge::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0;
    width: 74px;
    height: 74px;
    border-radius: 50%;
    background:
        conic-gradient(
            from 270deg,
            #D94D39 0deg 35deg,
            #F09A38 35deg 70deg,
            #E4D24E 70deg 105deg,
            #87CF53 105deg 140deg,
            #34BE68 140deg 180deg,
            transparent 180deg 360deg
        );
    -webkit-mask: radial-gradient(circle at center, transparent 0 50%, #000 52% 100%);
    mask: radial-gradient(circle at center, transparent 0 50%, #000 52% 100%);
    filter: drop-shadow(0 0 6px rgba(255,178,30,0.12));
}

.mini-fg-value {
    color: #FFFFFF !important;
    font-size: 2.02rem;
    font-weight: 950;
    line-height: 1;
}

.mini-fg-status {
    color: #FFB21E !important;
    font-size: 0.88rem;
    font-weight: 900;
    margin-top: 3px;
}

/* Large market sentiment card */
.fg-index-kicker {
    color: #E7C77E !important;
    font-size: 0.78rem;
    font-weight: 900;
    letter-spacing: 0.13em;
    text-transform: uppercase;
    margin-bottom: 5px;
}

.st-key-fear_greed_index_card {
    min-height: 286px !important;
}

/* Shared home panel shell */
.home-panel-heading-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 14px;
    margin-bottom: 12px;
}

.home-panel-title {
    color: #F8E6BC !important;
    font-size: 1.65rem;
    font-weight: 900;
    line-height: 1.12;
    letter-spacing: 0.01em;
}

.home-alerts-title {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    color: #F8E6BC !important;
    font-size: 1.02rem !important;
    line-height: 1.14 !important;
    font-weight: 740 !important;
    letter-spacing: 0.42px !important;
    text-transform: uppercase !important;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    text-shadow:
        0 0 8px rgba(255,178,30,0.10),
        0 0 14px rgba(255,178,30,0.04);
}


.home-compact-title {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    color: #F8E6BC !important;
    font-size: 1.02rem !important;
    line-height: 1.14 !important;
    font-weight: 740 !important;
    letter-spacing: 0.42px !important;
    text-transform: uppercase !important;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    text-shadow:
        0 0 8px rgba(255,178,30,0.10),
        0 0 14px rgba(255,178,30,0.04);
}

.home-news-title-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    flex: 0 0 30px;
}

.home-news-title-icon svg {
    width: 24px;
    height: 24px;
    display: block;
    stroke: #F3B33E;
    fill: none;
    stroke-width: 2.20;
    stroke-linecap: round;
    stroke-linejoin: round;
    filter: drop-shadow(0 0 5px rgba(255,178,30,0.16));
}

.home-alerts-bell {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    flex: 0 0 30px;
}

.home-alerts-bell svg {
    width: 24px;
    height: 24px;
    stroke: #F3B33E;
    fill: none;
    stroke-width: 2.15;
    stroke-linecap: round;
    stroke-linejoin: round;
    filter: drop-shadow(0 0 5px rgba(255,178,30,0.16));
}

.home-panel-action,
.home-panel-action:visited {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 7px 12px;
    border-radius: 8px;
    color: #E9E1D2 !important;
    text-decoration: none !important;
    font-size: 0.80rem;
    font-weight: 800;
    border: 1px solid rgba(255,255,255,0.12);
    background: rgba(255,255,255,0.025);
}

.home-panel-action:hover {
    color: #FFFFFF !important;
    border-color: rgba(255,178,30,0.35);
    box-shadow: 0 0 12px rgba(255,178,30,0.09);
}


/* Native in-app VIEW ALL buttons — identical styling */
.st-key-home_alerts_view_all button,
.st-key-home_news_view_all button {
    min-height: 0 !important;
    height: 34px !important;
    padding: 0 13px !important;
    border-radius: 8px !important;

    color: #E9E1D2 !important;
    background: rgba(255,255,255,0.025) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;

    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    font-size: 0.80rem !important;
    font-weight: 800 !important;
    line-height: 1 !important;

    box-shadow: none !important;
}

.st-key-home_alerts_view_all button:hover,
.st-key-home_news_view_all button:hover {
    color: #FFFFFF !important;
    background: rgba(255,178,30,0.055) !important;
    border-color: rgba(255,178,30,0.35) !important;
    box-shadow: 0 0 12px rgba(255,178,30,0.09) !important;
    transform: none !important;
}

.st-key-home_alerts_view_all button p,
.st-key-home_news_view_all button p {
    color: inherit !important;
    font: inherit !important;
}

/* Outer shells for home content */
.st-key-home_alerts_panel,
.st-key-home_timeline_card,
.st-key-home_news_preview_card {
    position: relative;
    overflow: hidden;
    background:
        radial-gradient(circle at top left, rgba(255,178,30,0.055), transparent 35%),
        linear-gradient(180deg, rgba(12,12,12,0.99), rgba(5,5,5,1)) !important;
    border: 1px solid rgba(255,178,30,0.24) !important;
    border-radius: 20px !important;
    box-shadow:
        0 0 12px rgba(255,178,30,0.08),
        0 12px 30px rgba(0,0,0,0.30) !important;
    padding: 14px 14px 12px 14px !important;
}

.st-key-home_alerts_panel::before,
.st-key-home_timeline_card::before,
.st-key-home_news_preview_card::before {
    content: "";
    position: absolute;
    left: 16px;
    right: 16px;
    top: 0;
    height: 2px;
    border-radius: 999px;
    background: linear-gradient(90deg, transparent, rgba(255,178,30,0.92), transparent);
    box-shadow: 0 0 15px rgba(255,178,30,0.24);
}

.st-key-home_alerts_panel [data-testid="stVerticalBlockBorderWrapper"],
.st-key-home_timeline_card [data-testid="stVerticalBlockBorderWrapper"],
.st-key-home_news_preview_card [data-testid="stVerticalBlockBorderWrapper"] {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    padding: 0 !important;
}


.st-key-home_alerts_panel:hover,
.st-key-home_timeline_card:hover,
.st-key-home_news_preview_card:hover {
    transform: translateY(-3px);
    border-color: rgba(255,199,92,0.58) !important;
    box-shadow:
        0 0 0 1px rgba(255,199,92,0.12),
        0 0 20px rgba(255,178,30,0.24),
        0 0 38px rgba(255,145,0,0.14),
        0 14px 34px rgba(0,0,0,0.46) !important;
}

/* Home alert rows: smaller inside one parent card */
.st-key-home_alerts_panel .alert-card {
    border-radius: 14px;
    padding: 17px 16px;
    margin-bottom: 14px;
    min-height: 104px;
    box-shadow:
        0 7px 18px rgba(0,0,0,0.22),
        inset 0 1px 0 rgba(255,255,255,0.04);
}

.st-key-home_alerts_panel .alert-card::before {
    height: 2px;
}

.st-key-home_alerts_panel .asset-circle {
    width: 46px;
    height: 46px;
    min-width: 46px;
    font-size: 1.34rem;
}

.st-key-home_alerts_panel .badge {
    padding: 4px 9px;
    font-size: 0.76rem;
}

.st-key-home_alerts_panel .alert-badges {
    gap: 6px;
    margin-top: 8px;
    margin-bottom: 0;
}

.st-key-home_alerts_panel .alert-title {
    display: flex !important;
    align-items: baseline !important;
    justify-content: flex-start !important;
    flex-wrap: nowrap !important;
    width: auto !important;
    max-width: 100% !important;
    margin-bottom: 8px !important;
    font-size: 1.18rem !important;
    line-height: 1.18 !important;
    white-space: nowrap !important;
}

.st-key-home_alerts_panel .alert-amount {
    display: inline-block !important;
    flex: 0 0 auto !important;
    margin: 0 24px 0 0 !important;
    padding: 0 !important;
    font-size: 1.24rem !important;
    line-height: 1.15 !important;
    white-space: nowrap !important;
}

.st-key-home_alerts_panel .alert-usd {
    display: inline-block !important;
    flex: 0 0 auto !important;
    margin: 0 !important;
    padding: 0 !important;
    font-size: 1.06rem !important;
    line-height: 1.15 !important;
    white-space: nowrap !important;
}

.st-key-home_alerts_panel .alert-sub {
    margin-top: 1px !important;
    margin-bottom: 8px !important;
    font-size: 0.86rem !important;
    line-height: 1.38 !important;
}

.st-key-home_alerts_panel .alert-time {
    font-size: 0.82rem !important;
}

/* Timeline controls */
.home-timeframe-pills {
    display: inline-flex;
    align-items: center;
    gap: 5px;
}

.home-timeframe-pill {
    min-width: 38px;
    padding: 5px 9px;
    border-radius: 999px;
    border: 1px solid rgba(255,255,255,0.10);
    color: #BDB7AD !important;
    font-size: 0.72rem;
    font-weight: 800;
    text-align: center;
    background: rgba(255,255,255,0.02);
}

.home-timeframe-pill.active {
    color: #F8E6BC !important;
    border-color: rgba(255,178,30,0.30);
    background: rgba(255,178,30,0.10);
    box-shadow: 0 0 9px rgba(255,178,30,0.08);
}

/* News preview */
.home-news-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
}

.home-news-item {
    display: grid;
    grid-template-columns: 106px minmax(0, 1fr);
    gap: 13px;
    align-items: stretch;
    min-width: 0;
}

.home-news-thumb {
    width: 106px;
    height: 78px;
    border-radius: 12px;
    object-fit: cover;
    border: 1px solid rgba(255,178,30,0.18);
    background:
        radial-gradient(circle at 35% 25%, rgba(255,178,30,0.16), transparent 42%),
        linear-gradient(145deg, #16100A, #070707);
}

.home-news-fallback {
    width: 106px;
    height: 78px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #FFB21E !important;
    font-size: 2rem;
    border: 1px solid rgba(255,178,30,0.18);
    background:
        radial-gradient(circle at 35% 25%, rgba(255,178,30,0.16), transparent 42%),
        linear-gradient(145deg, #16100A, #070707);
}

.home-news-copy {
    min-width: 0;
}

.home-news-title,
.home-news-title:visited {
    color: #FFFFFF !important;
    text-decoration: none !important;
    font-size: 1.06rem;
    font-weight: 900;
    line-height: 1.30;
}

.home-news-title:hover {
    color: #F8E6BC !important;
}

.home-news-desc {
    margin-top: 7px;
    color: #AAA399 !important;
    font-size: 0.84rem;
    line-height: 1.42;
}

.home-news-meta {
    margin-top: 9px;
    color: #8A847B !important;
    font-size: 0.76rem;
    font-weight: 750;
}

/* Right sidebar: titles live inside the cards */
.side-card-heading {
    color: #F8E6BC !important;
    font-size: 1.16rem;
    font-weight: 900;
    letter-spacing: 0.04em;
    margin: 0 0 12px 0;
}

.sidebar-card-title-outside {
    display: none !important;
}

.st-key-monitoring_controls_card,
.st-key-watchlist_controls_card {
    padding: 16px 15px 15px 15px !important;
}

.st-key-monitoring_controls_card label,
.st-key-watchlist_controls_card label {
    font-size: 0.78rem !important;
}

.st-key-monitoring_controls_card .sidebar-note {
    font-size: 0.78rem !important;
}

.st-key-monitoring_controls_card .stButton > button,
.st-key-watchlist_controls_card .stButton > button {
    min-height: 42px;
}

/* Footer */
.novaris-footer {
    margin-top: 18px;
    padding: 16px 4px 6px 4px;
    border-top: 1px solid rgba(255,178,30,0.14);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    color: #7F796F !important;
    font-size: 0.72rem;
}

.novaris-footer-links {
    display: inline-flex;
    gap: 24px;
}

.novaris-footer-links span {
    color: #8E887F !important;
}

/* Keep the right control rail aligned with the KPI row */
.control-rail-top-spacer {
    height: 132px !important;
}

@media (max-width: 1400px) {
    .control-rail-top-spacer {
        height: 124px !important;
    }
}

@media (max-width: 1050px) {
    .brand-live-status {
        display: none;
    }
    .home-news-grid {
        grid-template-columns: 1fr;
    }
}


/* Exact lower-home alignment.
   380px timeline + 12px gap + 248px news = 640px,
   matching the 640px Latest Alerts panel. */
.st-key-home_alerts_panel {
    height: 640px !important;
    min-height: 640px !important;
    box-sizing: border-box !important;
    overflow: hidden !important;
}

.st-key-home_timeline_card {
    height: 380px !important;
    min-height: 380px !important;
    box-sizing: border-box !important;
    overflow: hidden !important;
}

.st-key-home_news_preview_card {
    height: 248px !important;
    min-height: 248px !important;
    box-sizing: border-box !important;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    overflow: hidden !important;
}

.st-key-home_news_preview_card > div,
.st-key-home_news_preview_card [data-testid="stVerticalBlock"] {
    width: 100%;
}

.st-key-home_news_preview_card .home-news-grid {
    min-height: 160px;
    height: 160px;
    align-items: stretch;
}

.st-key-home_news_preview_card .home-news-item {
    min-height: 136px;
    height: 136px;
    align-items: center;
}

.st-key-home_news_preview_card .home-news-thumb,
.st-key-home_news_preview_card .home-news-fallback {
    width: 116px;
    height: 88px;
}

.st-key-home_news_preview_card .home-news-item {
    grid-template-columns: 116px minmax(0, 1fr);
}


/* =========================================================
   REFINED NOVARIS WORDMARK
   ========================================================= */

/* Move the brand further upward inside the sticky header */
.st-key-brand_header {
    padding-top: 0.06rem !important;
    padding-bottom: 0.42rem !important;
}

/* Elegant gold NOVARIS wordmark */
.brand-title {
    display: inline-flex !important;
    align-items: center !important;
    gap: 9px !important;

    margin-top: -0.62rem !important;
    margin-bottom: 0.08rem !important;

    line-height: 1 !important;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;

    /* neutralise the older chunky styling */
    -webkit-text-stroke: 0 !important;
    filter: none !important;
    text-shadow: none !important;
}

.brand-word {
    color: #F0B846 !important;
    font-size: 2.42rem !important;
    font-weight: 520 !important;
    letter-spacing: 0.115em !important;
    line-height: 1 !important;

    text-shadow:
        0 0 4px rgba(255,198,84,0.28),
        0 0 11px rgba(255,178,30,0.13) !important;
}

.brand-spark {
    color: #FFD36A !important;
    font-size: 2.10rem !important;
    font-weight: 400 !important;
    line-height: 1 !important;
    transform: translateY(-1px);

    text-shadow:
        0 0 4px rgba(255,223,150,0.62),
        0 0 10px rgba(255,178,30,0.26),
        0 0 18px rgba(255,145,0,0.11) !important;
}

/* Keep subtitle tucked neatly under the higher wordmark */
.st-key-brand_header .brand-sub,
div[data-testid="stVerticalBlock"] > div:has(.brand-title) .brand-sub {
    margin-top: -0.02rem !important;
    margin-bottom: 0.02rem !important;
}

.st-key-brand_header .brand-mini,
div[data-testid="stVerticalBlock"] > div:has(.brand-title) .brand-mini {
    margin-top: -0.02rem !important;
    margin-bottom: 0 !important;
}

/* Responsive wordmark sizing */
@media (max-width: 1200px) {
    .brand-word {
        font-size: 2.18rem !important;
        letter-spacing: 0.10em !important;
    }

    .brand-spark {
        font-size: 1.92rem !important;
    }
}


/* Final nudge so the whole brand block sits visually higher */
.st-key-brand_header [data-testid="stVerticalBlock"] {
    gap: 0 !important;
}

.st-key-brand_header .brand-title,
div[data-testid="stVerticalBlock"] > div:has(.brand-title) .brand-title {
    transform: translateY(-2px) !important;
}


/* =========================================================
   NAVBAR — MATCH SUPPLIED REFERENCE
   ========================================================= */
.brand-top-nav {
    position: absolute !important;
    top: 0.64rem !important;
    left: 50% !important;
    right: auto !important;
    transform: translateX(-50%) !important;
    z-index: 10020 !important;

    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 0 !important;

    width: auto !important;
    max-width: none !important;
    padding: 5px 9px !important;

    border-radius: 999px !important;
    border: 1px solid rgba(255,255,255,0.085) !important;

    background:
        linear-gradient(
            180deg,
            rgba(18,19,21,0.985) 0%,
            rgba(7,8,10,0.995) 100%
        ) !important;

    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.035),
        0 8px 24px rgba(0,0,0,0.38) !important;

    white-space: nowrap !important;
    overflow: visible !important;
}

.brand-top-nav a,
.brand-top-nav a:visited,
.brand-top-nav a:hover,
.brand-top-nav a:active {
    min-width: 0 !important;
    height: 46px !important;
    box-sizing: border-box !important;

    padding: 0 20px !important;
    margin: 0 !important;

    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 10px !important;

    border-radius: 999px !important;
    border: 1px solid transparent !important;

    color: #D7D8DB !important;
    background: transparent !important;

    font-family:
        Inter,
        "Segoe UI",
        "Helvetica Neue",
        Arial,
        sans-serif !important;

    font-size: 0.84rem !important;
    font-weight: 520 !important;
    line-height: 1 !important;
    letter-spacing: 0 !important;
    text-transform: none !important;

    text-decoration: none !important;
    text-align: center !important;
    text-shadow: none !important;

    box-shadow: none !important;

    transition:
        background-color 0.16s ease,
        color 0.16s ease,
        border-color 0.16s ease,
        box-shadow 0.16s ease !important;
}

.brand-top-nav a .nav-item-label {
    display: inline-block !important;
    transform: none !important;
    color: inherit !important;
    font: inherit !important;
    letter-spacing: inherit !important;
    text-transform: inherit !important;
}

/* Clear, fine-line icons like the reference */
.brand-top-nav a .nav-item-icon {
    width: 18px !important;
    height: 18px !important;
    flex: 0 0 18px !important;

    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;

    color: #DCDDDF !important;
    opacity: 1 !important;
    filter: none !important;
}

.brand-top-nav a .nav-item-icon svg {
    width: 18px !important;
    height: 18px !important;

    display: block !important;
    overflow: visible !important;

    stroke: currentColor !important;
    fill: none !important;
    stroke-width: 1.95 !important;
    stroke-linecap: round !important;
    stroke-linejoin: round !important;

    filter: none !important;
}

/* Active Home pill — warm amber, subtle rather than chunky */
.brand-top-nav a.active {
    color: #FFFFFF !important;

    border-color: rgba(210,143,25,0.62) !important;

    background:
        radial-gradient(
            circle at 48% -20%,
            rgba(255,190,67,0.20),
            transparent 72%
        ),
        linear-gradient(
            180deg,
            rgba(91,60,16,0.72),
            rgba(44,29,8,0.82)
        ) !important;

    box-shadow:
        inset 0 1px 0 rgba(255,220,145,0.12),
        0 0 9px rgba(210,143,25,0.18),
        0 4px 13px rgba(0,0,0,0.30) !important;

    text-shadow: none !important;
}

.brand-top-nav a.active .nav-item-icon {
    color: #FFF5D8 !important;
    filter: none !important;
}

/* Very restrained hover, matching the clean sample */
.brand-top-nav a:not(.active):hover {
    color: #FFFFFF !important;
    background: rgba(255,255,255,0.035) !important;
    border-color: rgba(255,255,255,0.055) !important;
    transform: none !important;
    box-shadow: none !important;
}

.brand-top-nav a:not(.active):hover .nav-item-icon {
    color: #FFFFFF !important;
    filter: none !important;
}

/* Keep the desktop reference appearance through normal laptop widths */
@media (max-width: 1400px) {
    .brand-top-nav {
        gap: 0 !important;
        padding: 5px 8px !important;
    }

    .brand-top-nav a,
    .brand-top-nav a:visited,
    .brand-top-nav a:hover,
    .brand-top-nav a:active {
        min-width: 0 !important;
        height: 44px !important;
        padding: 0 17px !important;
        gap: 9px !important;
        font-size: 0.94rem !important;
        font-weight: 520 !important;
    }

    .brand-top-nav a .nav-item-icon,
    .brand-top-nav a .nav-item-icon svg {
        width: 17px !important;
        height: 17px !important;
        flex-basis: 17px !important;
    }
}

@media (max-width: 1050px) {
    .brand-top-nav {
        left: 50% !important;
        right: auto !important;
        transform: translateX(-50%) !important;
    }

    .brand-top-nav a,
    .brand-top-nav a:visited,
    .brand-top-nav a:hover,
    .brand-top-nav a:active {
        min-width: 0 !important;
        height: 40px !important;
        padding: 0 12px !important;
        gap: 7px !important;
        font-size: 0.84rem !important;
    }

    .brand-top-nav a .nav-item-icon,
    .brand-top-nav a .nav-item-icon svg {
        width: 15px !important;
        height: 15px !important;
        flex-basis: 15px !important;
    }
}

@media (max-width: 900px) {
    .brand-top-nav {
        position: relative !important;
        top: auto !important;
        left: auto !important;
        right: auto !important;
        transform: none !important;

        width: max-content !important;
        max-width: 100% !important;

        margin-top: 0.48rem !important;

        overflow-x: auto !important;
        justify-content: flex-start !important;

        scrollbar-width: none !important;
    }

    .brand-top-nav::-webkit-scrollbar {
        display: none !important;
    }
}


/* =========================================================
   SESSION-STATE NAVIGATION — PREMIUM LARGE IN-APP NAVBAR
   ========================================================= */
.st-key-session_nav_shell {
    position: absolute !important;
    top: 0.48rem !important;
    left: 50% !important;
    transform: translateX(-50%) !important;
    z-index: 10030 !important;

    width: 930px !important;
    max-width: 88% !important;
}

/* One premium outer pill around all six navigation buttons */
.st-key-session_nav_shell [data-testid="stHorizontalBlock"] {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;

    gap: 4px !important;

    width: 100% !important;
    padding: 7px 9px !important;
    box-sizing: border-box !important;

    border-radius: 999px !important;

    background:
        radial-gradient(
            circle at 50% -35%,
            rgba(255, 178, 30, 0.11),
            transparent 58%
        ),
        linear-gradient(
            180deg,
            rgba(21,22,24,0.99) 0%,
            rgba(8,9,11,0.995) 100%
        ) !important;

    border: 1px solid rgba(255,255,255,0.11) !important;

    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.055),
        inset 0 -1px 0 rgba(255,178,30,0.025),
        0 0 0 1px rgba(255,178,30,0.018),
        0 10px 28px rgba(0,0,0,0.42),
        0 0 24px rgba(255,178,30,0.035) !important;

    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
}

/* Remove Streamlit column spacing inside the nav shell */
.st-key-session_nav_shell [data-testid="stColumn"] {
    min-width: 118px !important;
    flex: 1 1 0 !important;
    padding: 0 !important;
}

/* All six buttons */
.st-key-session_nav_shell .stButton {
    width: 100% !important;
}

.st-key-session_nav_shell .stButton > button {
    width: 100% !important;
    min-width: 0 !important;
    height: 52px !important;

    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 10px !important;

    padding: 0 15px !important;

    border-radius: 999px !important;
    border: 1px solid transparent !important;

    background: transparent !important;
    color: #DCD9D2 !important;

    font-family:
        Inter,
        "Segoe UI",
        "Helvetica Neue",
        Arial,
        sans-serif !important;

    font-size: 1.02rem !important;
    font-weight: 560 !important;
    line-height: 1 !important;
    letter-spacing: 0.02em !important;

    text-shadow: none !important;
    box-shadow: none !important;
    white-space: nowrap !important;

    transition:
        color 0.18s ease,
        background 0.18s ease,
        border-color 0.18s ease,
        box-shadow 0.18s ease,
        transform 0.18s ease !important;
}

/* Keep text refined rather than chunky */
.st-key-session_nav_shell .stButton > button p {
    color: inherit !important;
    font-family:
        Inter,
        "Segoe UI",
        "Helvetica Neue",
        Arial,
        sans-serif !important;
    font-size: 1.02rem !important;
    font-weight: 560 !important;
    letter-spacing: 0.02em !important;
    line-height: 1 !important;
    margin: 0 !important;
    white-space: nowrap !important;
}

/* Material icons — deliberately larger and brighter */
.st-key-session_nav_shell .stButton > button [data-testid="stIconMaterial"],
.st-key-session_nav_shell .stButton > button .material-symbols-rounded,
.st-key-session_nav_shell .stButton > button .material-symbols-outlined,
.st-key-session_nav_shell .stButton > button span[translate="no"] {
    font-size: 1.42rem !important;
    width: 1.42rem !important;
    height: 1.42rem !important;
    line-height: 1.42rem !important;

    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;

    color: #EDE6D8 !important;
    opacity: 1 !important;

    text-shadow:
        0 0 5px rgba(255,255,255,0.08),
        0 0 8px rgba(255,178,30,0.07) !important;
}

/* Hover: subtle premium lift */
.st-key-session_nav_shell .stButton > button:hover {
    color: #FFFFFF !important;

    background:
        linear-gradient(
            180deg,
            rgba(255,255,255,0.055),
            rgba(255,255,255,0.018)
        ) !important;

    border-color: rgba(255,255,255,0.09) !important;

    transform: translateY(-1px) !important;

    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.035),
        0 5px 14px rgba(0,0,0,0.22) !important;
}

/* Active navigation item uses Streamlit's primary button type */
.st-key-session_nav_shell .stButton > button[kind="primary"],
.st-key-session_nav_shell .stButton > button[data-testid="stBaseButton-primary"] {
    color: #FFF7E8 !important;

    border-color: rgba(223,151,27,0.58) !important;

    background:
        radial-gradient(
            circle at 50% -25%,
            rgba(255,198,82,0.22),
            transparent 68%
        ),
        linear-gradient(
            180deg,
            rgba(93,62,17,0.84),
            rgba(43,28,8,0.91)
        ) !important;

    box-shadow:
        inset 0 1px 0 rgba(255,226,158,0.14),
        0 0 0 1px rgba(255,178,30,0.035),
        0 0 13px rgba(255,178,30,0.17),
        0 5px 15px rgba(0,0,0,0.30) !important;
}

.st-key-session_nav_shell .stButton > button[kind="primary"] p,
.st-key-session_nav_shell .stButton > button[data-testid="stBaseButton-primary"] p {
    color: #FFF7E8 !important;
    font-weight: 620 !important;
}

.st-key-session_nav_shell .stButton > button[kind="primary"] [data-testid="stIconMaterial"],
.st-key-session_nav_shell .stButton > button[data-testid="stBaseButton-primary"] [data-testid="stIconMaterial"],
.st-key-session_nav_shell .stButton > button[kind="primary"] .material-symbols-rounded,
.st-key-session_nav_shell .stButton > button[data-testid="stBaseButton-primary"] .material-symbols-rounded,
.st-key-session_nav_shell .stButton > button[kind="primary"] span[translate="no"],
.st-key-session_nav_shell .stButton > button[data-testid="stBaseButton-primary"] span[translate="no"] {
    color: #FFE3A0 !important;
    text-shadow:
        0 0 5px rgba(255,220,140,0.22),
        0 0 10px rgba(255,178,30,0.13) !important;
}

/* Laptop sizing — still visibly premium */
@media (max-width: 1400px) {
    .st-key-session_nav_shell {
        width: 850px !important;
        max-width: 90% !important;
    }

    .st-key-session_nav_shell [data-testid="stHorizontalBlock"] {
        padding: 6px 8px !important;
    }

    .st-key-session_nav_shell .stButton > button {
        height: 48px !important;
        padding: 0 12px !important;
        gap: 8px !important;
    }

    .st-key-session_nav_shell .stButton > button,
    .st-key-session_nav_shell .stButton > button p {
        font-size: 0.94rem !important;
    }

    .st-key-session_nav_shell .stButton > button [data-testid="stIconMaterial"],
    .st-key-session_nav_shell .stButton > button .material-symbols-rounded,
    .st-key-session_nav_shell .stButton > button .material-symbols-outlined,
    .st-key-session_nav_shell .stButton > button span[translate="no"] {
        font-size: 1.30rem !important;
        width: 1.30rem !important;
        height: 1.30rem !important;
        line-height: 1.30rem !important;
    }
}

@media (max-width: 1050px) {
    .st-key-session_nav_shell {
        width: 760px !important;
        max-width: 94% !important;
    }

    .st-key-session_nav_shell .stButton > button {
        height: 44px !important;
        padding: 0 9px !important;
        gap: 6px !important;
    }

    .st-key-session_nav_shell .stButton > button,
    .st-key-session_nav_shell .stButton > button p {
        font-size: 0.84rem !important;
    }

    .st-key-session_nav_shell .stButton > button [data-testid="stIconMaterial"],
    .st-key-session_nav_shell .stButton > button .material-symbols-rounded,
    .st-key-session_nav_shell .stButton > button .material-symbols-outlined,
    .st-key-session_nav_shell .stButton > button span[translate="no"] {
        font-size: 1.15rem !important;
        width: 1.15rem !important;
        height: 1.15rem !important;
        line-height: 1.15rem !important;
    }
}

@media (max-width: 900px) {
    .st-key-session_nav_shell {
        position: relative !important;
        top: auto !important;
        left: auto !important;
        transform: none !important;

        width: 100% !important;
        max-width: 100% !important;

        margin: 0.55rem 0 0.30rem 0 !important;
        overflow-x: auto !important;
        scrollbar-width: none !important;
    }

    .st-key-session_nav_shell::-webkit-scrollbar {
        display: none !important;
    }

    .st-key-session_nav_shell [data-testid="stHorizontalBlock"] {
        width: max-content !important;
        min-width: 520px !important;
    }

    .st-key-session_nav_shell [data-testid="stColumn"] {
        min-width: 110px !important;
    }
}


/* Remove form shells so existing card styling remains unchanged. */
.st-key-monitoring_controls_card [data-testid="stForm"],
.st-key-watchlist_controls_card [data-testid="stForm"] {
    border: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
    background: transparent !important;
}

@media (max-width: 1400px) {
    .st-key-session_nav_shell [data-testid="stButtonGroup"] button,
    .st-key-session_nav_shell button[kind="segmented_control"],
    .st-key-session_nav_shell button {
        height: 44px !important;
        padding: 0 16px !important;
        font-size: 0.92rem !important;
    }
}

@media (max-width: 1050px) {
    .st-key-session_nav_shell {
        max-width: 78% !important;
    }

    .st-key-session_nav_shell [data-testid="stButtonGroup"] button,
    .st-key-session_nav_shell button[kind="segmented_control"],
    .st-key-session_nav_shell button {
        height: 40px !important;
        padding: 0 10px !important;
        font-size: 0.82rem !important;
    }
}

@media (max-width: 900px) {
    .st-key-session_nav_shell {
        position: relative !important;
        top: auto !important;
        left: auto !important;
        transform: none !important;
        width: 100% !important;
        max-width: 100% !important;
        margin: 0.45rem 0 0.25rem 0 !important;
        overflow-x: auto !important;
        scrollbar-width: none !important;
    }

    .st-key-session_nav_shell::-webkit-scrollbar {
        display: none !important;
    }
}


/* =========================================================
   DEDICATED CONTROLS PAGE
   ========================================================= */
.st-key-monitoring_controls_card {
    width: 100% !important;
    min-height: 330px !important;
    box-sizing: border-box !important;
    padding: 24px 26px 24px 26px !important;
    margin-top: 8px !important;
    margin-bottom: 18px !important;
    background:
        radial-gradient(circle at 12% 0%, rgba(255,178,30,0.085), transparent 32%),
        linear-gradient(180deg, rgba(10,10,10,0.995), rgba(3,3,3,1)) !important;
    border: 1px solid rgba(255,178,30,0.30) !important;
    border-radius: 20px !important;
    box-shadow:
        0 0 0 1px rgba(255,178,30,0.045),
        0 0 16px rgba(255,178,30,0.12),
        0 12px 30px rgba(0,0,0,0.40) !important;
}

.st-key-monitoring_controls_card .side-card-heading {
    color: #F8E6BC !important;
    font-size: 1.22rem !important;
    font-weight: 760 !important;
    letter-spacing: 0.42px !important;
    line-height: 1.1 !important;
    margin: 0 0 8px 0 !important;
    text-transform: uppercase !important;
    text-shadow:
        0 0 8px rgba(255,178,30,0.10),
        0 0 14px rgba(255,178,30,0.04) !important;
}

.st-key-monitoring_controls_card .controls-page-note {
    max-width: 850px !important;
    margin-bottom: 20px !important;
    color: #AFA99E !important;
    font-size: 0.86rem !important;
    line-height: 1.45 !important;
}

.st-key-monitoring_controls_card label {
    color: #E6E0D5 !important;
    font-size: 0.86rem !important;
    font-weight: 650 !important;
}

.st-key-monitoring_controls_card [data-testid="stForm"] {
    margin-top: 2px !important;
}

.st-key-monitoring_controls_card [data-testid="stHorizontalBlock"] {
    align-items: flex-start !important;
}

.st-key-monitoring_controls_card .stTextInput input,
.st-key-monitoring_controls_card .stNumberInput input {
    min-height: 44px !important;
}

.st-key-monitoring_controls_card .stButton > button {
    min-height: 44px !important;
    font-size: 0.88rem !important;
    font-weight: 760 !important;
}


/* =========================================================
   WATCHLIST-ONLY WALLET LOOKUP RAIL
   ========================================================= */
.watchlist-rail-top-spacer {
    height: 122px !important;
}

@media (max-width: 1400px) {
    .watchlist-rail-top-spacer {
        height: 114px !important;
    }
}

@media (max-width: 1050px) {
    .watchlist-rail-top-spacer {
        height: 104px !important;
    }
}


/* =========================================================
   WATCHLIST — MAIN-CANVAS WALLET LOOKUP
   ========================================================= */
.st-key-watchlist_controls_card {
    width: 100% !important;
    min-height: 320px !important;
    box-sizing: border-box !important;

    margin-top: 14px !important;
    margin-bottom: 18px !important;
    padding: 24px 26px 24px 26px !important;

    background:
        radial-gradient(circle at 10% 0%, rgba(255,178,30,0.085), transparent 34%),
        linear-gradient(180deg, rgba(10,10,10,0.995), rgba(3,3,3,1)) !important;

    border: 1px solid rgba(255,178,30,0.30) !important;
    border-radius: 20px !important;

    box-shadow:
        0 0 0 1px rgba(255,178,30,0.045),
        0 0 16px rgba(255,178,30,0.12),
        0 12px 30px rgba(0,0,0,0.40) !important;
}

.st-key-watchlist_controls_card::before {
    content: "" !important;
    position: absolute !important;
    top: 0 !important;
    left: 16px !important;
    right: 16px !important;
    height: 3px !important;
    border-radius: 999px !important;
    background:
        linear-gradient(
            90deg,
            rgba(255,178,30,0),
            rgba(255,178,30,1),
            rgba(255,178,30,0)
        ) !important;
    box-shadow:
        0 0 18px rgba(255,178,30,0.38),
        0 0 34px rgba(255,145,0,0.14) !important;
}

.st-key-watchlist_controls_card:hover {
    transform: translateY(-3px) !important;
    border-color: rgba(255,199,92,0.58) !important;
    box-shadow:
        0 0 0 1px rgba(255,199,92,0.12),
        0 0 20px rgba(255,178,30,0.24),
        0 0 38px rgba(255,145,0,0.14),
        0 14px 34px rgba(0,0,0,0.46) !important;
}

.st-key-watchlist_controls_card [data-testid="stVerticalBlockBorderWrapper"] {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    padding: 0 !important;
}

.watchlist-main-heading {
    color: #F8E6BC !important;
    font-size: 1.22rem !important;
    font-weight: 760 !important;
    line-height: 1.1 !important;
    letter-spacing: 0.42px !important;
    text-transform: uppercase !important;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    margin: 0 0 7px 0 !important;
}

.watchlist-main-note {
    color: #AAA399 !important;
    font-size: 0.86rem !important;
    line-height: 1.42 !important;
    margin-bottom: 18px !important;
    max-width: 920px !important;
}

.st-key-watchlist_controls_card label {
    color: #E7E0D5 !important;
    font-size: 0.86rem !important;
    font-weight: 650 !important;
}

.st-key-watchlist_controls_card textarea {
    min-height: 118px !important;
}

.wallet-action-spacer {
    height: 25px !important;
}

.st-key-watchlist_controls_card [data-testid="stFormSubmitButton"] button {
    min-height: 44px !important;
    margin-top: 0 !important;
    font-size: 0.88rem !important;
    font-weight: 760 !important;
}

.watchlist-empty-note {
    margin-top: 2px !important;
    padding: 14px 16px !important;
    border-radius: 12px !important;

    color: #9D978E !important;
    font-size: 0.84rem !important;

    background: rgba(255,178,30,0.035) !important;
    border: 1px solid rgba(255,178,30,0.09) !important;
}

.st-key-topnav_watchlist_results_card {
    margin-top: 4px !important;
}


/* =========================================================
   BRANDING — FLUSH TO TOP OF PAGE
   ========================================================= */

/* Remove Streamlit's remaining top spacing around the main canvas */
[data-testid="stAppViewContainer"] > .main,
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
.block-container {
    padding-top: 0 !important;
    margin-top: 0 !important;
}

/* Pin the NOVARIS header directly against the top edge */
.st-key-brand_header {
    top: 0 !important;
    margin-top: 0 !important;
    padding-top: 0 !important;
}

/* Move the complete branding group upward as one unit */
.st-key-brand_header .brand-title,
div[data-testid="stVerticalBlock"] > div:has(.brand-title) .brand-title {
    margin-top: 0 !important;
    transform: translateY(-1px) !important;
}

/* Keep subtitle and data note tight beneath the wordmark */
.st-key-brand_header .brand-sub,
div[data-testid="stVerticalBlock"] > div:has(.brand-title) .brand-sub {
    margin-top: 0 !important;
    margin-bottom: 0.02rem !important;
}

.st-key-brand_header .brand-mini,
div[data-testid="stVerticalBlock"] > div:has(.brand-title) .brand-mini {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}

/* Remove any hidden wrapper spacing above the brand */
.st-key-brand_header > div,
.st-key-brand_header [data-testid="stVerticalBlock"],
.st-key-brand_header [data-testid="stElementContainer"]:first-child {
    margin-top: 0 !important;
    padding-top: 0 !important;
}


.st-key-home_alerts_panel .alert-time {
    flex: 0 0 auto !important;
    min-width: 54px !important;
    margin-left: 16px !important;
    text-align: right !important;
}

.st-key-home_alerts_panel .alert-row {
    align-items: flex-start !important;
}

.st-key-home_alerts_panel .alert-left {
    min-width: 0 !important;
    flex: 1 1 auto !important;
}


/* =========================================================
   FULL ALERTS + NEWS PAGES — UNIFORM COMPACT CONTENT WIDTH
   ========================================================= */
:root {
    --novaris-detail-page-width: min(78vw, 1280px);
}

/* Alerts page heading lines up exactly with alert cards */
.latest-alerts-title {
    width: var(--novaris-detail-page-width) !important;
    max-width: 1280px !important;
    margin-left: auto !important;
    margin-right: auto !important;
}

/* Full Alerts page only — do not affect Home dashboard alert cards */
.alert-card-link.full-alert-link,
.alert-card-link.full-alert-link:visited,
.alert-card-link.full-alert-link:hover,
.alert-card-link.full-alert-link:active {
    width: var(--novaris-detail-page-width) !important;
    max-width: 1280px !important;
    margin: 0 auto 14px auto !important;
}

.alert-card-link.full-alert-link .alert-card {
    width: 100% !important;
    box-sizing: border-box !important;
    margin-bottom: 0 !important;
}

/* News page uses the exact same content width as Alerts */
.news-hero,
.news-summary-card,
.news-story-card-wrap {
    width: var(--novaris-detail-page-width) !important;
    max-width: 1280px !important;
    margin-left: auto !important;
    margin-right: auto !important;
    box-sizing: border-box !important;
}

.news-summary-card {
    margin-bottom: 20px !important;
}

.news-story-card-wrap {
    margin-bottom: 14px !important;
}

/* Keep long article titles/descriptions readable in the shorter cards */
.news-story-main {
    grid-template-columns: 54px minmax(0, 1fr) 105px !important;
}

.news-feature-description,
.news-story-description {
    max-width: 100% !important;
}

@media (max-width: 1400px) {
    :root {
        --novaris-detail-page-width: 90vw;
    }

    .latest-alerts-title,
    .alert-card-link.full-alert-link,
    .news-hero,
    .news-summary-card,
    .news-story-card-wrap {
        max-width: 1180px !important;
    }
}

@media (max-width: 900px) {
    :root {
        --novaris-detail-page-width: calc(100vw - 28px);
    }

    .latest-alerts-title,
    .alert-card-link.full-alert-link,
    .news-hero,
    .news-summary-card,
    .news-story-card-wrap {
        max-width: none !important;
    }
}


/* =========================================================
   TRANSACTION DETAIL PAGE — CENTERED LIKE ALERTS PAGE
   ========================================================= */

/* Use the same centred content width as the full Alerts page */
.tx-back-row,
.tx-page-title,
.tx-summary-card,
.tx-whale-alert-summary,
.tx-info-card,
.tx-transfer-card,
.tx-not-found {
    width: var(--novaris-detail-page-width) !important;
    max-width: 1280px !important;
    box-sizing: border-box !important;
    margin-left: auto !important;
    margin-right: auto !important;
}

/* Preserve the intended vertical spacing after centering */
.tx-back-row {
    margin-top: 8px !important;
    margin-bottom: 18px !important;
}

.tx-page-title {
    margin-top: 0 !important;
    margin-bottom: 18px !important;
}

.tx-summary-card,
.tx-whale-alert-summary,
.tx-info-card {
    margin-bottom: 18px !important;
}

.tx-transfer-card {
    margin-bottom: 24px !important;
}

/* Keep the back button and titles aligned to the same left edge as the cards */
.tx-back-row {
    justify-content: flex-start !important;
}

@media (max-width: 1400px) {
    .tx-back-row,
    .tx-page-title,
    .tx-summary-card,
    .tx-whale-alert-summary,
    .tx-info-card,
    .tx-transfer-card,
    .tx-not-found {
        max-width: 1180px !important;
    }
}

@media (max-width: 900px) {
    .tx-back-row,
    .tx-page-title,
    .tx-summary-card,
    .tx-whale-alert-summary,
    .tx-info-card,
    .tx-transfer-card,
    .tx-not-found {
        width: calc(100vw - 28px) !important;
        max-width: none !important;
    }
}


/* =========================================================
   WATCHLIST + CONTROLS PAGES — CENTERED LIKE ALERTS PAGE
   ========================================================= */

/* Main Watchlist lookup card */
.st-key-watchlist_controls_card {
    width: var(--novaris-detail-page-width) !important;
    max-width: 1280px !important;
    margin-left: auto !important;
    margin-right: auto !important;
}

/* Watchlist empty-state / results also align to the same centred width */
.watchlist-empty-note,
.st-key-topnav_watchlist_results_card {
    width: var(--novaris-detail-page-width) !important;
    max-width: 1280px !important;
    box-sizing: border-box !important;
    margin-left: auto !important;
    margin-right: auto !important;
}

/* Dedicated Controls page card */
.st-key-monitoring_controls_card {
    width: var(--novaris-detail-page-width) !important;
    max-width: 1280px !important;
    margin-left: auto !important;
    margin-right: auto !important;
}

/* Keep both pages aligned with the Alerts page at smaller widths */
@media (max-width: 1400px) {
    .st-key-watchlist_controls_card,
    .watchlist-empty-note,
    .st-key-topnav_watchlist_results_card,
    .st-key-monitoring_controls_card {
        max-width: 1180px !important;
    }
}

@media (max-width: 900px) {
    .st-key-watchlist_controls_card,
    .watchlist-empty-note,
    .st-key-topnav_watchlist_results_card,
    .st-key-monitoring_controls_card {
        width: calc(100vw - 28px) !important;
        max-width: none !important;
    }
}


/* =========================================================
   FINAL BRAND HEADER BEHAVIOUR
   - NOVARIS is no longer sticky/fixed
   - branding begins at the very top of the page
   ========================================================= */

/* Remove Streamlit's remaining top canvas spacing */
html,
body,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > .main,
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
.block-container {
    margin-top: 0 !important;
    padding-top: 0 !important;
}

/* The complete header now scrolls normally with the page */
.st-key-brand_header {
    position: relative !important;
    top: auto !important;
    left: auto !important;
    right: auto !important;
    z-index: 100 !important;

    margin-top: 0 !important;
    padding-top: 0 !important;

    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
}

/* Neutralise the older fallback sticky selectors as well */
div[data-testid="stVerticalBlock"] > div:has(.brand-title),
div[data-testid="stElementContainer"]:has(.brand-title) {
    position: relative !important;
    top: auto !important;
    left: auto !important;
    right: auto !important;
    z-index: auto !important;

    margin-top: 0 !important;
    padding-top: 0 !important;

    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
}

/* Remove hidden wrapper space above NOVARIS */
.st-key-brand_header,
.st-key-brand_header > div,
.st-key-brand_header [data-testid="stVerticalBlock"],
.st-key-brand_header [data-testid="stElementContainer"],
div[data-testid="stVerticalBlock"] > div:has(.brand-title),
div[data-testid="stElementContainer"]:has(.brand-title) {
    margin-top: 0 !important;
    padding-top: 0 !important;
}

/* Place the wordmark directly at the top edge */
.st-key-brand_header .brand-title,
div[data-testid="stVerticalBlock"] > div:has(.brand-title) .brand-title {
    margin-top: 0 !important;
    padding-top: 0 !important;
    transform: none !important;
}

/* Keep the subtitle and refresh note tucked underneath */
.st-key-brand_header .brand-sub,
.st-key-brand_header .brand-mini,
div[data-testid="stVerticalBlock"] > div:has(.brand-title) .brand-sub,
div[data-testid="stVerticalBlock"] > div:has(.brand-title) .brand-mini {
    margin-top: 0 !important;
}


/* =========================================================
   FINAL NOVARIS TOP POSITIONING
   ========================================================= */

/* Eliminate all top-page spacing */
html,
body,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > .main,
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
.block-container {
    margin-top: 0 !important;
    padding-top: 0 !important;
}

/* Header is normal page content, never sticky/fixed */
.st-key-brand_header {
    position: relative !important;
    top: auto !important;
    left: auto !important;
    right: auto !important;

    min-height: 108px !important;
    height: 108px !important;

    margin: 0 0 10px 0 !important;
    padding: 0 !important;

    overflow: visible !important;
    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
}

/* Remove Streamlit's internal vertical gaps in this header */
.st-key-brand_header [data-testid="stVerticalBlock"] {
    gap: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}

.st-key-brand_header [data-testid="stElementContainer"] {
    margin: 0 !important;
    padding: 0 !important;
}

/* One absolute brand block means Streamlit cannot push it downward */
.st-key-brand_header .brand-copy {
    position: absolute !important;
    top: 0 !important;
    left: 0 !important;
    z-index: 10010 !important;

    display: block !important;
    width: max-content !important;
    max-width: none !important;

    margin: 0 !important;
    padding: 0 !important;
}

/* Wordmark directly against the top edge */
.st-key-brand_header .brand-copy .brand-title {
    display: inline-flex !important;
    align-items: center !important;

    margin: 0 0 4px 0 !important;
    padding: 0 !important;
    transform: none !important;

    line-height: 1 !important;
}

/* Subtitle stays on one line */
.st-key-brand_header .brand-copy .brand-sub {
    display: block !important;
    width: max-content !important;
    max-width: none !important;

    margin: 0 0 2px 0 !important;
    padding: 0 !important;

    white-space: nowrap !important;
    overflow: visible !important;
    text-overflow: clip !important;

    font-size: 0.84rem !important;
    line-height: 1.18 !important;
}

/* Refresh note also kept compact */
.st-key-brand_header .brand-copy .brand-mini {
    display: block !important;
    width: max-content !important;
    max-width: none !important;

    margin: 0 !important;
    padding: 0 !important;

    white-space: nowrap !important;
    font-size: 0.76rem !important;
    line-height: 1.16 !important;
}

/* Keep the navbar centred at the top without affecting brand placement */
.st-key-session_nav_shell {
    top: 0 !important;
}

/* Neutralise any older fallback sticky rules */
div[data-testid="stVerticalBlock"] > div:has(.brand-copy),
div[data-testid="stElementContainer"]:has(.brand-copy),
div[data-testid="stVerticalBlock"] > div:has(.brand-title),
div[data-testid="stElementContainer"]:has(.brand-title) {
    position: static !important;
    top: auto !important;
    margin-top: 0 !important;
    padding-top: 0 !important;

    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
}

/* Slightly smaller subtitle on narrow screens while preserving one line */
@media (max-width: 1200px) {
    .st-key-brand_header .brand-copy .brand-sub {
        font-size: 0.78rem !important;
    }

    .st-key-brand_header .brand-copy .brand-mini {
        font-size: 0.70rem !important;
    }
}


/* WHALE ALERTS bell icon — uses the existing KPI circle styling */
.whale-alert-svg {
    width: 36px !important;
    height: 36px !important;
    display: block !important;
    overflow: visible !important;
    filter:
        drop-shadow(0 0 5px rgba(255,215,106,0.26))
        drop-shadow(0 0 10px rgba(255,178,30,0.12));
}


/* =========================================================
   WHALE ALERTS KPI — RELIABLE FULL-CARD CLICK TARGET
   ========================================================= */

/*
Streamlit inserts extra wrapper elements around st.button().
Target the button's own key directly instead of relying on
`.stButton { height:100% }`, which can resolve against the wrong wrapper.
*/
.st-key-whale_alerts_kpi_clickable {
    position: relative !important;
    cursor: pointer !important;
}

/* Keep the visual KPI below the click layer. */
.st-key-whale_alerts_kpi_clickable .metric-card {
    position: relative !important;
    z-index: 1 !important;
}

/* The keyed Streamlit button becomes an invisible overlay. */
.st-key-whale_alerts_kpi_clickable .st-key-open_whale_alerts_page {
    position: absolute !important;
    inset: 0 !important;
    z-index: 100 !important;

    width: 100% !important;
    height: 100% !important;
    min-height: 100% !important;

    margin: 0 !important;
    padding: 0 !important;

    pointer-events: auto !important;
}

/* Cover the complete KPI card with the native Streamlit button. */
.st-key-whale_alerts_kpi_clickable .st-key-open_whale_alerts_page button,
.st-key-whale_alerts_kpi_clickable .st-key-open_whale_alerts_page [data-testid="stBaseButton-secondary"],
.st-key-whale_alerts_kpi_clickable .st-key-open_whale_alerts_page [data-testid="stBaseButton-primary"] {
    position: absolute !important;
    inset: 0 !important;

    width: 100% !important;
    height: 100% !important;
    min-height: 100% !important;

    margin: 0 !important;
    padding: 0 !important;

    border: 0 !important;
    border-radius: 20px !important;

    background: transparent !important;
    box-shadow: none !important;

    color: transparent !important;
    opacity: 0 !important;

    cursor: pointer !important;
    pointer-events: auto !important;
}

/* Hide the button text without disabling the actual click target. */
.st-key-whale_alerts_kpi_clickable .st-key-open_whale_alerts_page button p {
    opacity: 0 !important;
}

/* Premium hover remains on the visible KPI card. */
.st-key-whale_alerts_kpi_clickable:hover .metric-card {
    transform: translateY(-3px) !important;
    border-color: rgba(255,199,92,0.58) !important;
    box-shadow:
        0 0 0 1px rgba(255,199,92,0.12),
        0 0 20px rgba(255,178,30,0.24),
        0 0 38px rgba(255,145,0,0.14),
        0 14px 34px rgba(0,0,0,0.46) !important;
}

/* Whale Alerts page uses the same centred width as Transfers. */
.latest-alerts-title,
.alert-card-link.full-alert-link {
    box-sizing: border-box !important;
}



/* =========================================================
   WHALE ALERT DETAILS — MATCH WHALE ALERT LIST CARD
   ========================================================= */
.tx-whale-alert-summary {
    /* Align the Whale Alert summary card to the exact same content column
       as the page title, Transaction Information and Transfer cards. */
    width: var(--novaris-detail-page-width) !important;
    max-width: 1280px !important;
    box-sizing: border-box !important;

    margin: 0 auto 18px auto !important;
    padding: 0 !important;
}

.tx-whale-alert-summary .alert-card {
    width: 100% !important;
    box-sizing: border-box !important;
    margin: 0 !important;
    border: 1px solid rgba(255,178,30,0.42) !important;
    background:
        linear-gradient(
            180deg,
            rgba(18,18,18,0.96) 0%,
            rgba(7,7,7,0.985) 100%
        ) !important;
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.025),
        0 0 18px rgba(255,178,30,0.05) !important;
}

.tx-whale-alert-summary .asset-circle {
    flex: 0 0 auto !important;
}

.tx-whale-alert-summary .alert-title {
    display: flex !important;
    align-items: baseline !important;
    gap: 24px !important;
    flex-wrap: wrap !important;
}

.tx-whale-alert-summary .alert-amount {
    color: #FFB21E !important;
}

.tx-whale-alert-summary .alert-usd {
    color: #F5F3EE !important;
}

.tx-whale-alert-summary .alert-sub {
    margin-top: 4px !important;
}

.tx-whale-alert-summary .alert-badges {
    margin-top: 7px !important;
    margin-bottom: 0 !important;
}

.tx-whale-alert-summary .alert-card:hover {
    transform: none !important;
}


/* =========================================================
   HEADER STATUS + SETTINGS ICON
   ========================================================= */

/* Shift Live Feed slightly left to create space for the gear icon. */
.brand-live-status {
    top: 0.83rem !important;
    right: 4.55rem !important;
}

/* Streamlit keyed Settings button placed beside Live Feed. */
.st-key-header_settings_button {
    position: absolute !important;
    top: 0.43rem !important;
    right: 1.05rem !important;
    z-index: 10040 !important;

    width: 44px !important;
    height: 44px !important;

    margin: 0 !important;
    padding: 0 !important;
}

/* Remove extra Streamlit wrapper spacing. */
.st-key-header_settings_button .stButton,
.st-key-header_settings_button [data-testid="stButton"] {
    width: 44px !important;
    height: 44px !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* True icon-only circular Settings control. */
.st-key-header_settings_button button {
    width: 44px !important;
    min-width: 44px !important;
    height: 44px !important;
    min-height: 44px !important;

    padding: 0 !important;
    margin: 0 !important;

    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;

    border-radius: 999px !important;
    border: 1px solid rgba(255,255,255,0.12) !important;

    background:
        linear-gradient(
            180deg,
            rgba(20,21,23,0.98),
            rgba(8,9,11,0.99)
        ) !important;

    color: #EDE6D8 !important;

    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.05),
        0 7px 18px rgba(0,0,0,0.30) !important;
}

/* Hide the word "Settings"; retain it as the accessible button label. */
.st-key-header_settings_button button p {
    display: none !important;
}

/* Actual Material Settings gear icon. */
.st-key-header_settings_button button [data-testid="stIconMaterial"],
.st-key-header_settings_button button .material-symbols-rounded,
.st-key-header_settings_button button .material-symbols-outlined,
.st-key-header_settings_button button span[translate="no"] {
    margin: 0 !important;

    font-size: 1.48rem !important;
    width: 1.48rem !important;
    height: 1.48rem !important;
    line-height: 1.48rem !important;

    color: #EDE6D8 !important;
}

/* Premium hover treatment. */
.st-key-header_settings_button button:hover {
    border-color: rgba(255,178,30,0.40) !important;
    color: #FFE4A3 !important;

    background:
        radial-gradient(
            circle at 50% 0%,
            rgba(255,178,30,0.12),
            transparent 70%
        ),
        linear-gradient(
            180deg,
            rgba(27,23,15,0.99),
            rgba(9,9,9,0.99)
        ) !important;

    box-shadow:
        inset 0 1px 0 rgba(255,226,158,0.08),
        0 0 14px rgba(255,178,30,0.12),
        0 7px 18px rgba(0,0,0,0.32) !important;
}

/* Active state when Settings page is open. */
.st-key-header_settings_button button[kind="primary"],
.st-key-header_settings_button button[data-testid="stBaseButton-primary"] {
    border-color: rgba(223,151,27,0.58) !important;

    background:
        radial-gradient(
            circle at 50% -20%,
            rgba(255,198,82,0.22),
            transparent 68%
        ),
        linear-gradient(
            180deg,
            rgba(93,62,17,0.84),
            rgba(43,28,8,0.91)
        ) !important;

    box-shadow:
        inset 0 1px 0 rgba(255,226,158,0.14),
        0 0 13px rgba(255,178,30,0.17),
        0 5px 15px rgba(0,0,0,0.30) !important;
}

.st-key-header_settings_button button[kind="primary"] [data-testid="stIconMaterial"],
.st-key-header_settings_button button[data-testid="stBaseButton-primary"] [data-testid="stIconMaterial"],
.st-key-header_settings_button button[kind="primary"] .material-symbols-rounded,
.st-key-header_settings_button button[data-testid="stBaseButton-primary"] .material-symbols-rounded,
.st-key-header_settings_button button[kind="primary"] span[translate="no"],
.st-key-header_settings_button button[data-testid="stBaseButton-primary"] span[translate="no"] {
    color: #FFE3A0 !important;
}

/* On narrower screens, keep the status compact and prevent overlap. */
@media (max-width: 1050px) {
    .st-key-header_settings_button {
        right: 0.75rem !important;
    }

    .brand-live-status {
        display: none !important;
    }
}

@media (max-width: 900px) {
    .st-key-header_settings_button {
        top: 0.35rem !important;
        right: 0.45rem !important;
        width: 40px !important;
        height: 40px !important;
    }

    .st-key-header_settings_button button {
        width: 40px !important;
        min-width: 40px !important;
        height: 40px !important;
        min-height: 40px !important;
    }
}


/* =========================================================
   CLICKABLE ETH / BTC SPOT PRICE CARDS
   ========================================================= */
.st-key-eth_market_kpi_clickable,
.st-key-btc_market_kpi_clickable {
    position: relative !important;
    cursor: pointer !important;
}

.st-key-eth_market_kpi_clickable .metric-card,
.st-key-btc_market_kpi_clickable .metric-card {
    position: relative !important;
    z-index: 1 !important;
}

.st-key-eth_market_kpi_clickable .st-key-open_eth_market_page,
.st-key-btc_market_kpi_clickable .st-key-open_btc_market_page {
    position: absolute !important;
    inset: 0 !important;
    z-index: 100 !important;
    width: 100% !important;
    height: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
}

.st-key-eth_market_kpi_clickable .st-key-open_eth_market_page button,
.st-key-btc_market_kpi_clickable .st-key-open_btc_market_page button {
    position: absolute !important;
    inset: 0 !important;
    width: 100% !important;
    height: 100% !important;
    min-height: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
    border: 0 !important;
    border-radius: 18px !important;
    background: transparent !important;
    box-shadow: none !important;
    color: transparent !important;
    opacity: 0 !important;
    cursor: pointer !important;
}

.st-key-eth_market_kpi_clickable:hover .metric-card,
.st-key-btc_market_kpi_clickable:hover .metric-card {
    transform: translateY(-3px) !important;
    border-color: rgba(255,199,92,0.58) !important;
    box-shadow:
        0 0 0 1px rgba(255,199,92,0.12),
        0 0 20px rgba(255,178,30,0.22),
        0 0 38px rgba(255,145,0,0.12),
        0 14px 34px rgba(0,0,0,0.46) !important;
}

/* =========================================================
   MARKET PAGE
   ========================================================= */
.market-page-hero,
.market-table-shell {
    width: var(--novaris-detail-page-width) !important;
    max-width: 1280px !important;
    margin-left: auto !important;
    margin-right: auto !important;
    box-sizing: border-box !important;
}

.market-page-hero {
    margin-top: 8px !important;
    margin-bottom: 18px !important;
}

.market-page-title {
    color: #FFFFFF !important;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    font-size: 2.05rem !important;
    font-weight: 850 !important;
    letter-spacing: -0.035em !important;
    line-height: 1.08 !important;
}

.market-page-subtitle {
    margin-top: 7px !important;
    color: #AFA99F !important;
    font-size: 1rem !important;
    font-weight: 550 !important;
}

.market-table-shell {
    overflow: hidden !important;
    border: 1px solid rgba(255,178,30,0.36) !important;
    border-radius: 22px !important;
    background:
        radial-gradient(
            circle at 16% 0%,
            rgba(255,178,30,0.055),
            transparent 34%
        ),
        linear-gradient(
            180deg,
            rgba(15,15,15,0.985),
            rgba(5,5,5,0.995)
        ) !important;
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.035),
        0 0 24px rgba(255,178,30,0.055),
        0 18px 42px rgba(0,0,0,0.30) !important;
}

.market-table-header,
.market-table-row {
    display: grid !important;
    grid-template-columns: 1.55fr 1.05fr 1.35fr 0.9fr !important;
    align-items: center !important;
    column-gap: 24px !important;
}

.market-table-header {
    min-height: 58px !important;
    padding: 0 28px !important;
    border-bottom: 1px solid rgba(255,255,255,0.075) !important;
    color: #938C80 !important;
    font-size: 0.76rem !important;
    font-weight: 850 !important;
    letter-spacing: 0.12em !important;
}

.market-table-row {
    min-height: 126px !important;
    padding: 14px 28px !important;
    border-bottom: 1px solid rgba(255,255,255,0.065) !important;
    transition:
        background 0.22s ease,
        box-shadow 0.22s ease !important;
}

.market-table-row:hover {
    background:
        linear-gradient(
            90deg,
            rgba(255,178,30,0.045),
            rgba(255,255,255,0.012) 42%,
            transparent
        ) !important;
    box-shadow: inset 3px 0 0 rgba(255,178,30,0.70) !important;
}

.market-asset-cell {
    display: flex !important;
    align-items: center !important;
    gap: 16px !important;
    min-width: 0 !important;
}

.market-asset-icon {
    width: 56px !important;
    height: 56px !important;
    flex: 0 0 56px !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    border-radius: 999px !important;
    border: 1px solid rgba(255,178,30,0.42) !important;
    background:
        radial-gradient(
            circle at 45% 40%,
            rgba(255,190,73,0.18),
            rgba(16,16,16,0.94) 66%
        ) !important;
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.05),
        0 0 17px rgba(255,178,30,0.10) !important;
}

.market-btc-icon {
    color: #FFD263 !important;
    font-size: 2rem !important;
    font-weight: 900 !important;
    line-height: 1 !important;
    text-shadow:
        0 0 8px rgba(255,203,86,0.56),
        0 0 18px rgba(255,178,30,0.22) !important;
}

.market-asset-icon .alert-eth-icon {
    width: 31px !important;
    height: 38px !important;
}

.market-asset-name {
    color: #F7F3EB !important;
    font-size: 1.08rem !important;
    font-weight: 800 !important;
    line-height: 1.12 !important;
}

.market-asset-symbol {
    margin-top: 5px !important;
    color: #827C73 !important;
    font-size: 0.86rem !important;
    font-weight: 700 !important;
}

.market-price-cell {
    color: #FFFFFF !important;
    font-size: 1.26rem !important;
    font-weight: 820 !important;
    letter-spacing: -0.02em !important;
}

.market-chart-cell {
    height: 72px !important;
    display: flex !important;
    align-items: center !important;
}

.market-sparkline {
    width: 100% !important;
    max-width: 210px !important;
    height: 62px !important;
    overflow: visible !important;
}

.market-chart-empty {
    width: 180px !important;
    height: 42px !important;
    display: flex !important;
    align-items: center !important;
    gap: 5px !important;
    opacity: 0.45 !important;
}

.market-chart-empty span {
    width: 5px !important;
    height: 5px !important;
    border-radius: 999px !important;
    background: #8B857B !important;
}

.market-change-cell {
    justify-self: end !important;
    font-size: 1.03rem !important;
    font-weight: 850 !important;
    white-space: nowrap !important;
}

.market-change-cell span {
    display: inline-block !important;
    margin-right: 5px !important;
}

.market-change-positive {
    color: #65D98A !important;
}

.market-change-negative {
    color: #FF7474 !important;
}

.market-change-neutral {
    color: #B4AEA4 !important;
}

.market-source-row {
    min-height: 54px !important;
    display: flex !important;
    align-items: center !important;
    gap: 9px !important;
    padding: 0 28px !important;
    color: #777169 !important;
    font-size: 0.76rem !important;
    font-weight: 650 !important;
}

.market-source-row > span:first-child {
    color: #9A9388 !important;
    font-weight: 850 !important;
    letter-spacing: 0.10em !important;
}

.market-source-row strong {
    color: #D7B76B !important;
    font-weight: 800 !important;
}

.market-source-dot {
    color: rgba(255,178,30,0.58) !important;
}

@media (max-width: 900px) {
    .market-page-hero,
    .market-table-shell {
        width: calc(100vw - 28px) !important;
        max-width: none !important;
    }

    .market-table-header {
        display: none !important;
    }

    .market-table-row {
        grid-template-columns: 1fr 1fr !important;
        row-gap: 14px !important;
        padding: 20px !important;
    }

    .market-chart-cell {
        grid-column: 1 / 2 !important;
    }

    .market-change-cell {
        grid-column: 2 / 3 !important;
        justify-self: end !important;
    }

    .market-source-row {
        flex-wrap: wrap !important;
        padding: 14px 20px !important;
    }
}


/* =========================================================
   MARKET PAGE — ALIGN WITH OTHER DETAIL PAGES
   ========================================================= */
.market-page-hero,
.market-table-shell {
    width: var(--novaris-detail-page-width) !important;
    max-width: 1280px !important;
    box-sizing: border-box !important;
    margin-left: auto !important;
    margin-right: auto !important;
}

.market-table-shell .market-table-header,
.market-table-shell .market-table-row,
.market-table-shell .market-source-row {
    width: 100% !important;
    box-sizing: border-box !important;
    margin-left: 0 !important;
    margin-right: 0 !important;
}

.market-table-shell .market-table-row:last-of-type {
    border-bottom: 1px solid rgba(255,255,255,0.065) !important;
}

@media (max-width: 1400px) {
    .market-page-hero,
    .market-table-shell {
        max-width: 1180px !important;
    }
}

@media (max-width: 900px) {
    .market-page-hero,
    .market-table-shell {
        width: calc(100vw - 28px) !important;
        max-width: none !important;
    }
}


/* =========================================================
   CLICKABLE KPI OVERLAYS — REMOVE WHITE HOVER / FOCUS BOXES
   ========================================================= */

/* Whale Alerts */
.st-key-whale_alerts_kpi_clickable .st-key-open_whale_alerts_page,
.st-key-eth_market_kpi_clickable .st-key-open_eth_market_page,
.st-key-btc_market_kpi_clickable .st-key-open_btc_market_page {
    position: absolute !important;
    inset: 0 !important;
    z-index: 100 !important;
    width: 100% !important;
    height: 100% !important;
    min-height: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
    overflow: hidden !important;
    pointer-events: auto !important;
}

/* Streamlit wrapper */
.st-key-whale_alerts_kpi_clickable .st-key-open_whale_alerts_page .stButton,
.st-key-eth_market_kpi_clickable .st-key-open_eth_market_page .stButton,
.st-key-btc_market_kpi_clickable .st-key-open_btc_market_page .stButton,
.st-key-whale_alerts_kpi_clickable .st-key-open_whale_alerts_page [data-testid="stButton"],
.st-key-eth_market_kpi_clickable .st-key-open_eth_market_page [data-testid="stButton"],
.st-key-btc_market_kpi_clickable .st-key-open_btc_market_page [data-testid="stButton"] {
    position: absolute !important;
    inset: 0 !important;
    width: 100% !important;
    height: 100% !important;
    min-height: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
}

/* Actual native Streamlit buttons:
   keep fully transparent in normal, hover, focus, focus-visible and active states. */
.st-key-whale_alerts_kpi_clickable .st-key-open_whale_alerts_page button,
.st-key-eth_market_kpi_clickable .st-key-open_eth_market_page button,
.st-key-btc_market_kpi_clickable .st-key-open_btc_market_page button,
.st-key-whale_alerts_kpi_clickable .st-key-open_whale_alerts_page button:hover,
.st-key-eth_market_kpi_clickable .st-key-open_eth_market_page button:hover,
.st-key-btc_market_kpi_clickable .st-key-open_btc_market_page button:hover,
.st-key-whale_alerts_kpi_clickable .st-key-open_whale_alerts_page button:focus,
.st-key-eth_market_kpi_clickable .st-key-open_eth_market_page button:focus,
.st-key-btc_market_kpi_clickable .st-key-open_btc_market_page button:focus,
.st-key-whale_alerts_kpi_clickable .st-key-open_whale_alerts_page button:focus-visible,
.st-key-eth_market_kpi_clickable .st-key-open_eth_market_page button:focus-visible,
.st-key-btc_market_kpi_clickable .st-key-open_btc_market_page button:focus-visible,
.st-key-whale_alerts_kpi_clickable .st-key-open_whale_alerts_page button:active,
.st-key-eth_market_kpi_clickable .st-key-open_eth_market_page button:active,
.st-key-btc_market_kpi_clickable .st-key-open_btc_market_page button:active {
    position: absolute !important;
    inset: 0 !important;
    width: 100% !important;
    height: 100% !important;
    min-height: 100% !important;

    margin: 0 !important;
    padding: 0 !important;

    border: 0 !important;
    outline: 0 !important;
    border-radius: 18px !important;

    background: transparent !important;
    background-color: transparent !important;
    background-image: none !important;

    box-shadow: none !important;
    filter: none !important;

    color: transparent !important;
    opacity: 0 !important;

    cursor: pointer !important;
    pointer-events: auto !important;
}

/* Hide every visual child belonging to the invisible overlay button. */
.st-key-whale_alerts_kpi_clickable .st-key-open_whale_alerts_page button *,
.st-key-eth_market_kpi_clickable .st-key-open_eth_market_page button *,
.st-key-btc_market_kpi_clickable .st-key-open_btc_market_page button * {
    opacity: 0 !important;
    color: transparent !important;
    background: transparent !important;
    box-shadow: none !important;
}

/* Some Streamlit/baseweb versions apply hover styling through the test-id element. */
.st-key-whale_alerts_kpi_clickable [data-testid^="stBaseButton"],
.st-key-eth_market_kpi_clickable [data-testid^="stBaseButton"],
.st-key-btc_market_kpi_clickable [data-testid^="stBaseButton"],
.st-key-whale_alerts_kpi_clickable [data-testid^="stBaseButton"]:hover,
.st-key-eth_market_kpi_clickable [data-testid^="stBaseButton"]:hover,
.st-key-btc_market_kpi_clickable [data-testid^="stBaseButton"]:hover,
.st-key-whale_alerts_kpi_clickable [data-testid^="stBaseButton"]:focus,
.st-key-eth_market_kpi_clickable [data-testid^="stBaseButton"]:focus,
.st-key-btc_market_kpi_clickable [data-testid^="stBaseButton"]:focus,
.st-key-whale_alerts_kpi_clickable [data-testid^="stBaseButton"]:active,
.st-key-eth_market_kpi_clickable [data-testid^="stBaseButton"]:active,
.st-key-btc_market_kpi_clickable [data-testid^="stBaseButton"]:active {
    background: transparent !important;
    background-color: transparent !important;
    background-image: none !important;
    border: 0 !important;
    outline: 0 !important;
    box-shadow: none !important;
    opacity: 0 !important;
}

/* Keep only the visible KPI card hover glow. */
.st-key-whale_alerts_kpi_clickable:hover .metric-card,
.st-key-eth_market_kpi_clickable:hover .metric-card,
.st-key-btc_market_kpi_clickable:hover .metric-card {
    transform: translateY(-3px) !important;
    border-color: rgba(255,199,92,0.58) !important;
    box-shadow:
        0 0 0 1px rgba(255,199,92,0.12),
        0 0 20px rgba(255,178,30,0.22),
        0 0 38px rgba(255,145,0,0.12),
        0 14px 34px rgba(0,0,0,0.46) !important;
}


/* =========================================================
   KPI CLICK OVERLAYS — NO HOVER TOOLTIP / WHITE POPUP
   ========================================================= */
.st-key-whale_alerts_kpi_clickable [data-testid="stTooltipIcon"],
.st-key-eth_market_kpi_clickable [data-testid="stTooltipIcon"],
.st-key-btc_market_kpi_clickable [data-testid="stTooltipIcon"] {
    display: none !important;
}

/* The overlay buttons are interaction layers only. They must never create
   a visible white surface above the real KPI cards. */
.st-key-whale_alerts_kpi_clickable .st-key-open_whale_alerts_page,
.st-key-eth_market_kpi_clickable .st-key-open_eth_market_page,
.st-key-btc_market_kpi_clickable .st-key-open_btc_market_page {
    background: transparent !important;
    box-shadow: none !important;
}


/* =========================================================
   MARKET TABLE — ALIGN VALUES DIRECTLY UNDER HEADERS
   ========================================================= */

/* Keep all four columns using the same grid structure. */
.market-table-header,
.market-table-row {
    grid-template-columns: 1.55fr 1.05fr 1.35fr 0.90fr !important;
}

/* PRICE: align header and values consistently. */
.market-table-header > div:nth-child(2),
.market-price-cell {
    justify-self: start !important;
    text-align: left !important;
}

/* CHART: align header and sparkline consistently. */
.market-table-header > div:nth-child(3),
.market-chart-cell {
    justify-self: start !important;
    text-align: left !important;
}

/* 24H CHANGE: centre both the heading and values in the same column.
   Previously the values used justify-self:end, which pushed them to
   the far-right edge while the heading stayed at the left of the column. */
.market-table-header > div:nth-child(4),
.market-change-cell {
    width: 100% !important;
    justify-self: stretch !important;
    text-align: center !important;
}

.market-change-cell {
    display: block !important;
}

@media (max-width: 900px) {
    .market-change-cell {
        width: auto !important;
        justify-self: end !important;
        text-align: right !important;
    }
}


/* =========================================================
   ALERTS / TRANSFERS PAGE HEADERS — MATCH MARKET HEADER
   ========================================================= */
.latest-alerts-title {
    /* Same typography as "Crypto Market Prices" */
    color: #FFFFFF !important;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    font-size: 2.05rem !important;
    font-weight: 850 !important;
    letter-spacing: -0.035em !important;
    line-height: 1.08 !important;

    /* Remove the older all-caps / gold-glow treatment */
    text-transform: none !important;
    text-shadow: none !important;

    /* Same page spacing/alignment as the Market hero */
    margin-top: 8px !important;
    margin-bottom: 18px !important;
    margin-left: auto !important;
    margin-right: auto !important;
}


/* =========================================================
   WALLET LOOKUP — MATCH CRYPTO MARKET PRICES HEADER
   ========================================================= */
.wallet-page-hero {
    width: var(--novaris-detail-page-width) !important;
    max-width: 1280px !important;
    margin-left: auto !important;
    margin-right: auto !important;
    margin-top: 8px !important;
    margin-bottom: 18px !important;
    box-sizing: border-box !important;
}

/* Exact same typography as Crypto Market Prices */
.wallet-page-hero .market-page-title {
    color: #FFFFFF !important;
    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    font-size: 2.05rem !important;
    font-weight: 850 !important;
    letter-spacing: -0.035em !important;
    line-height: 1.08 !important;
    text-transform: none !important;
    text-shadow: none !important;
}

.wallet-page-hero .market-page-subtitle {
    margin-top: 7px !important;
    color: #AFA99F !important;
    font-size: 1rem !important;
    font-weight: 550 !important;
    line-height: 1.4 !important;
}

/* Since the title is now outside the card, tighten the card top spacing. */
.st-key-watchlist_controls_card {
    margin-top: 0 !important;
}

/* =========================================================
   RUN WALLET SEARCH BUTTON — VISIBLE NOVARIS STYLE
   ========================================================= */
.st-key-watchlist_controls_card [data-testid="stFormSubmitButton"] {
    width: 100% !important;
    margin: 0 !important;
}

.st-key-watchlist_controls_card [data-testid="stFormSubmitButton"] button,
.st-key-watchlist_controls_card [data-testid="stFormSubmitButton"] button:hover,
.st-key-watchlist_controls_card [data-testid="stFormSubmitButton"] button:focus,
.st-key-watchlist_controls_card [data-testid="stFormSubmitButton"] button:focus-visible,
.st-key-watchlist_controls_card [data-testid="stFormSubmitButton"] button:active {
    min-height: 44px !important;
    width: 100% !important;

    border-radius: 11px !important;
    border: 1px solid rgba(255,178,30,0.42) !important;

    background:
        linear-gradient(
            180deg,
            rgba(32,24,11,0.98),
            rgba(10,9,7,0.99)
        ) !important;
    background-color: #11100D !important;
    background-image:
        linear-gradient(
            180deg,
            rgba(32,24,11,0.98),
            rgba(10,9,7,0.99)
        ) !important;

    color: #FFE6A8 !important;

    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    font-size: 0.88rem !important;
    font-weight: 800 !important;

    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.055),
        0 0 12px rgba(255,178,30,0.08),
        0 7px 16px rgba(0,0,0,0.28) !important;

    opacity: 1 !important;
    cursor: pointer !important;
}

/* Force the actual text to remain visible even if generic Streamlit
   button rules elsewhere in the app attempt to recolour it. */
.st-key-watchlist_controls_card [data-testid="stFormSubmitButton"] button p,
.st-key-watchlist_controls_card [data-testid="stFormSubmitButton"] button span {
    color: #FFE6A8 !important;
    opacity: 1 !important;
    visibility: visible !important;
    font-weight: 800 !important;
}

.st-key-watchlist_controls_card [data-testid="stFormSubmitButton"] button:hover {
    border-color: rgba(255,198,82,0.72) !important;
    background:
        linear-gradient(
            180deg,
            rgba(73,48,13,0.98),
            rgba(23,16,7,0.99)
        ) !important;

    color: #FFFFFF !important;

    box-shadow:
        inset 0 1px 0 rgba(255,235,187,0.10),
        0 0 17px rgba(255,178,30,0.18),
        0 8px 18px rgba(0,0,0,0.30) !important;
}

.st-key-watchlist_controls_card [data-testid="stFormSubmitButton"] button:hover p,
.st-key-watchlist_controls_card [data-testid="stFormSubmitButton"] button:hover span {
    color: #FFFFFF !important;
}

/* Keep Wallet page aligned at the same responsive widths as Market. */
@media (max-width: 1400px) {
    .wallet-page-hero {
        max-width: 1180px !important;
    }
}

@media (max-width: 900px) {
    .wallet-page-hero {
        width: calc(100vw - 28px) !important;
        max-width: none !important;
    }
}


/* =========================================================
   WALLET LOOKUP — PREMIUM NOVARIS REDESIGN
   ========================================================= */

.wallet-page-hero {
    margin-bottom: 20px !important;
}

.wallet-page-hero .market-page-subtitle {
    max-width: 920px !important;
    line-height: 1.48 !important;
}

/* Main search card */
.st-key-watchlist_controls_card {
    padding: 22px 24px 24px 24px !important;
    min-height: 0 !important;
    overflow: visible !important;
    background:
        radial-gradient(circle at 11% 0%, rgba(255,178,30,0.075), transparent 33%),
        linear-gradient(180deg, rgba(11,11,11,0.995), rgba(4,4,4,1)) !important;
}

/* Do not lift the entire form card on hover; keep it stable and professional. */
.st-key-watchlist_controls_card:hover {
    transform: none !important;
}

/* Top explainer strip */
.wallet-intro-strip {
    display: flex !important;
    align-items: center !important;
    gap: 14px !important;

    margin-bottom: 20px !important;
    padding: 13px 15px !important;

    border: 1px solid rgba(255,178,30,0.13) !important;
    border-radius: 14px !important;
    background:
        linear-gradient(
            90deg,
            rgba(255,178,30,0.055),
            rgba(255,178,30,0.016) 55%,
            rgba(255,255,255,0.008)
        ) !important;
}

.wallet-intro-icon {
    width: 40px !important;
    height: 40px !important;
    flex: 0 0 40px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;

    border-radius: 11px !important;
    border: 1px solid rgba(255,178,30,0.30) !important;
    background: rgba(255,178,30,0.055) !important;
}

.wallet-intro-icon svg {
    width: 24px !important;
    height: 24px !important;
    fill: none !important;
    stroke: #FFD36D !important;
    stroke-width: 2.2 !important;
    stroke-linecap: round !important;
}

.wallet-intro-copy {
    min-width: 0 !important;
    flex: 1 1 auto !important;
}

.wallet-intro-title {
    color: #F6F1E8 !important;
    font-size: 0.94rem !important;
    font-weight: 800 !important;
}

.wallet-intro-note {
    margin-top: 3px !important;
    color: #918B82 !important;
    font-size: 0.78rem !important;
    line-height: 1.42 !important;
}

.wallet-intro-badge {
    flex: 0 0 auto !important;
    padding: 6px 9px !important;

    border: 1px solid rgba(255,178,30,0.20) !important;
    border-radius: 999px !important;

    background: rgba(255,178,30,0.045) !important;
    color: #DDBB69 !important;

    font-size: 0.68rem !important;
    font-weight: 850 !important;
    letter-spacing: 0.08em !important;
}

/* Individual network input panels */
.st-key-wallet_eth_panel,
.st-key-wallet_btc_panel {
    box-sizing: border-box !important;
    height: 100% !important;

    padding: 15px 16px 14px 16px !important;

    border: 1px solid rgba(255,255,255,0.085) !important;
    border-radius: 16px !important;

    background:
        linear-gradient(
            180deg,
            rgba(255,255,255,0.027),
            rgba(255,255,255,0.009)
        ) !important;

    transition:
        border-color 0.2s ease,
        background 0.2s ease,
        box-shadow 0.2s ease !important;
}

.st-key-wallet_eth_panel:hover,
.st-key-wallet_btc_panel:hover {
    border-color: rgba(255,178,30,0.23) !important;
    background:
        linear-gradient(
            180deg,
            rgba(255,178,30,0.035),
            rgba(255,255,255,0.008)
        ) !important;
}

.wallet-network-heading {
    display: flex !important;
    align-items: center !important;
    gap: 11px !important;
    margin-bottom: 12px !important;
}

.wallet-network-icon {
    width: 36px !important;
    height: 36px !important;
    flex: 0 0 36px !important;

    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;

    border-radius: 999px !important;
    border: 1px solid rgba(255,178,30,0.30) !important;
    background:
        radial-gradient(circle at 45% 38%, rgba(255,190,73,0.15), rgba(9,9,9,0.96) 68%) !important;

    box-shadow: 0 0 13px rgba(255,178,30,0.07) !important;
}

.wallet-network-icon-eth svg {
    width: 20px !important;
    height: 26px !important;
    fill: #A9BCFF !important;
}

.wallet-network-icon-btc {
    color: #FFD263 !important;
    font-size: 1.45rem !important;
    font-weight: 900 !important;
}

.wallet-network-title {
    color: #F6F2EA !important;
    font-size: 0.91rem !important;
    font-weight: 820 !important;
}

.wallet-network-hint {
    margin-top: 2px !important;
    color: #817B72 !important;
    font-size: 0.72rem !important;
    font-weight: 560 !important;
}

/* Address inputs */
.st-key-wallet_eth_panel textarea,
.st-key-wallet_btc_panel textarea {
    min-height: 112px !important;
    padding: 13px 14px !important;

    border: 1px solid rgba(255,255,255,0.13) !important;
    border-radius: 12px !important;

    background: rgba(255,255,255,0.035) !important;
    color: #F1EEE8 !important;

    font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace !important;
    font-size: 0.80rem !important;
    line-height: 1.55 !important;

    box-shadow: inset 0 1px 0 rgba(255,255,255,0.018) !important;
}

.st-key-wallet_eth_panel textarea:focus,
.st-key-wallet_btc_panel textarea:focus {
    border-color: rgba(255,178,30,0.58) !important;
    box-shadow:
        0 0 0 1px rgba(255,178,30,0.12),
        0 0 14px rgba(255,178,30,0.08) !important;
}

.st-key-wallet_eth_panel textarea::placeholder,
.st-key-wallet_btc_panel textarea::placeholder {
    color: #615D57 !important;
}

/* Search depth */
.wallet-search-divider {
    height: 1px !important;
    margin: 20px 0 16px 0 !important;
    background:
        linear-gradient(
            90deg,
            transparent,
            rgba(255,178,30,0.14) 18%,
            rgba(255,178,30,0.14) 82%,
            transparent
        ) !important;
}

.wallet-search-heading {
    margin-bottom: 7px !important;
}

.wallet-search-title {
    color: #F5F0E7 !important;
    font-size: 0.91rem !important;
    font-weight: 820 !important;
}

.wallet-search-note {
    margin-top: 3px !important;
    color: #847E75 !important;
    font-size: 0.75rem !important;
}

/* Slider label becomes secondary because Search Depth is now the main heading. */
.st-key-watchlist_controls_card [data-testid="stSlider"] label {
    color: #9D968B !important;
    font-size: 0.72rem !important;
    font-weight: 650 !important;
}

/* Gold slider thumb to match NOVARIS. */
.st-key-watchlist_controls_card [data-baseweb="slider"] [role="slider"] {
    background: #FFB21E !important;
    border-color: #FFB21E !important;
    box-shadow: 0 0 9px rgba(255,178,30,0.26) !important;
}

/* Button alignment */
.wallet-action-spacer {
    height: 23px !important;
}

.st-key-watchlist_controls_card [data-testid="stFormSubmitButton"] button {
    min-height: 46px !important;
    border-radius: 12px !important;
    border-color: rgba(255,178,30,0.46) !important;

    background:
        linear-gradient(
            180deg,
            rgba(66,44,13,0.98),
            rgba(24,17,7,0.99)
        ) !important;

    color: #FFE7AC !important;
    font-size: 0.84rem !important;
    font-weight: 820 !important;

    box-shadow:
        inset 0 1px 0 rgba(255,231,169,0.08),
        0 0 13px rgba(255,178,30,0.10),
        0 8px 17px rgba(0,0,0,0.27) !important;
}

.st-key-watchlist_controls_card [data-testid="stFormSubmitButton"] button p,
.st-key-watchlist_controls_card [data-testid="stFormSubmitButton"] button span {
    color: #FFE7AC !important;
    opacity: 1 !important;
}

.st-key-watchlist_controls_card [data-testid="stFormSubmitButton"] button:hover {
    border-color: rgba(255,200,95,0.76) !important;
    background:
        linear-gradient(
            180deg,
            rgba(91,59,13,0.99),
            rgba(35,23,7,0.99)
        ) !important;

    color: #FFFFFF !important;

    box-shadow:
        inset 0 1px 0 rgba(255,240,202,0.11),
        0 0 20px rgba(255,178,30,0.17),
        0 9px 19px rgba(0,0,0,0.30) !important;
}

.st-key-watchlist_controls_card [data-testid="stFormSubmitButton"] button:hover p,
.st-key-watchlist_controls_card [data-testid="stFormSubmitButton"] button:hover span {
    color: #FFFFFF !important;
}

/* Empty-state panel */
.wallet-empty-state {
    display: flex !important;
    align-items: flex-start !important;
    gap: 12px !important;

    margin-top: 10px !important;
    padding: 15px 17px !important;

    background:
        linear-gradient(
            90deg,
            rgba(255,178,30,0.040),
            rgba(255,255,255,0.008)
        ) !important;

    border-color: rgba(255,178,30,0.12) !important;
}

.wallet-empty-dot {
    width: 8px !important;
    height: 8px !important;
    flex: 0 0 8px !important;
    margin-top: 5px !important;

    border-radius: 999px !important;
    background: #FFB21E !important;
    box-shadow: 0 0 9px rgba(255,178,30,0.45) !important;
}

.wallet-empty-title {
    color: #D9D3C8 !important;
    font-size: 0.81rem !important;
    font-weight: 780 !important;
}

.wallet-empty-copy {
    margin-top: 3px !important;
    color: #817B73 !important;
    font-size: 0.74rem !important;
    line-height: 1.42 !important;
}

/* Responsive */
@media (max-width: 900px) {
    .wallet-intro-badge {
        display: none !important;
    }

    .st-key-watchlist_controls_card {
        padding: 18px !important;
    }
}


/* =========================================================
   SETTINGS PAGE — MATCH LATEST BLOCKCHAIN NEWS HEADER
   ========================================================= */

/* Exact same centred content width as News. */
.settings-page-hero {
    width: var(--novaris-detail-page-width) !important;
    max-width: 1280px !important;
    margin-left: auto !important;
    margin-right: auto !important;
    box-sizing: border-box !important;
}

/*
The page title/subtitle deliberately inherit .news-page-title and
.news-page-subtitle so Settings stays visually identical to
Latest Blockchain News.
*/
.settings-page-hero.news-hero {
    margin-top: 18px !important;
    margin-bottom: 20px !important;
}

/* Settings card aligns directly beneath the header. */
.st-key-monitoring_controls_card {
    margin-top: 0 !important;
    padding: 22px 24px 24px 24px !important;
}

/* Small internal section intro — not a competing page heading. */
.settings-card-intro {
    margin-bottom: 19px !important;
    padding-bottom: 15px !important;
    border-bottom: 1px solid rgba(255,178,30,0.12) !important;
}

.settings-card-kicker {
    color: #D8B76B !important;
    font-size: 0.73rem !important;
    font-weight: 900 !important;
    letter-spacing: 0.13em !important;
}

.settings-card-copy {
    margin-top: 6px !important;
    max-width: 880px !important;
    color: #918A80 !important;
    font-size: 0.80rem !important;
    font-weight: 560 !important;
    line-height: 1.48 !important;
}

/* =========================================================
   SAVE PREFERENCES BUTTON — NOVARIS BLACK/GOLD
   ========================================================= */
.st-key-monitoring_controls_card [data-testid="stFormSubmitButton"] {
    width: 100% !important;
}

.st-key-monitoring_controls_card [data-testid="stFormSubmitButton"] button,
.st-key-monitoring_controls_card [data-testid="stFormSubmitButton"] button:hover,
.st-key-monitoring_controls_card [data-testid="stFormSubmitButton"] button:focus,
.st-key-monitoring_controls_card [data-testid="stFormSubmitButton"] button:focus-visible,
.st-key-monitoring_controls_card [data-testid="stFormSubmitButton"] button:active {
    width: 100% !important;
    min-height: 44px !important;

    border-radius: 11px !important;
    border: 1px solid rgba(255,178,30,0.44) !important;

    background:
        linear-gradient(
            180deg,
            rgba(54,37,12,0.99),
            rgba(18,13,6,0.99)
        ) !important;
    background-color: #151008 !important;

    color: #FFE5A4 !important;

    font-family: Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important;
    font-size: 0.86rem !important;
    font-weight: 820 !important;

    box-shadow:
        inset 0 1px 0 rgba(255,236,188,0.08),
        0 0 14px rgba(255,178,30,0.10),
        0 8px 17px rgba(0,0,0,0.28) !important;

    opacity: 1 !important;
}

.st-key-monitoring_controls_card [data-testid="stFormSubmitButton"] button p,
.st-key-monitoring_controls_card [data-testid="stFormSubmitButton"] button span {
    color: #FFE5A4 !important;
    opacity: 1 !important;
    visibility: visible !important;
    font-weight: 820 !important;
}

.st-key-monitoring_controls_card [data-testid="stFormSubmitButton"] button:hover {
    border-color: rgba(255,201,95,0.74) !important;

    background:
        linear-gradient(
            180deg,
            rgba(82,54,12,0.99),
            rgba(29,20,6,0.99)
        ) !important;

    box-shadow:
        inset 0 1px 0 rgba(255,240,202,0.11),
        0 0 20px rgba(255,178,30,0.17),
        0 9px 19px rgba(0,0,0,0.30) !important;
}

.st-key-monitoring_controls_card [data-testid="stFormSubmitButton"] button:hover p,
.st-key-monitoring_controls_card [data-testid="stFormSubmitButton"] button:hover span {
    color: #FFFFFF !important;
}

/* Keep Settings responsive exactly like News. */
@media (max-width: 1400px) {
    .settings-page-hero {
        max-width: 1180px !important;
    }
}

@media (max-width: 900px) {
    .settings-page-hero {
        width: calc(100vw - 28px) !important;
        max-width: none !important;
    }

    .st-key-monitoring_controls_card {
        padding: 18px !important;
    }
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# HELPERS
# =========================================================
def empty_alert_df():
    return pd.DataFrame(columns=REQUIRED_COLUMNS)


def safe_get_json(url, params=None, headers=None, timeout=25):
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()


def safe_get_text(url, params=None, headers=None, timeout=25):
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text


def safe_post_json(url, payload, headers=None, timeout=20):
    r = requests.post(url, json=payload, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()


def parse_lines(text):
    values = []
    for line in str(text).replace(",", "\n").splitlines():
        line = line.strip()
        if line:
            values.append(line)
    return values


def short_addr(addr, front=8, back=6):
    if not addr:
        return "unknown wallet"
    addr = str(addr)
    if len(addr) <= front + back + 3:
        return addr
    return f"{addr[:front]}...{addr[-back:]}"


def format_amount(value):
    if pd.isna(value):
        return "N/A"
    value = float(value)
    if value >= 1_000_000:
        return f"{value:,.0f}"
    if value >= 1:
        return f"{value:,.4f}".rstrip("0").rstrip(".")
    return f"{value:.8f}".rstrip("0").rstrip(".")


def human_age(ts):
    if pd.isna(ts):
        return "unknown time"
    diff = datetime.now(timezone.utc) - ts
    sec = int(diff.total_seconds())
    if sec < 60:
        return f"{sec}s ago"
    mins = sec // 60
    if mins < 60:
        return f"{mins}m ago"
    hrs = mins // 60
    if hrs < 24:
        return f"{hrs}h ago"
    return f"{hrs // 24}d ago"


def whale_marker(amount_usd):
    if pd.isna(amount_usd) or amount_usd is None:
        return ""
    if amount_usd >= 100_000_000:
        return "🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨"
    if amount_usd >= 10_000_000:
        return "🚨🚨🚨🚨🚨🚨🚨"
    if amount_usd >= 1_000_000:
        return "🚨🚨🚨🚨"
    return ""


def get_asset_meta(symbol, chain):
    symbol = (symbol or "").upper()
    if symbol in ASSET_META:
        return ASSET_META[symbol]
    return {"icon": "🪙", "label": symbol or "Unknown Asset", "chain_label": chain}



def get_alert_asset_icon(symbol, chain):
    """Return alert-card crypto artwork matching the top spot-price cards."""
    symbol = (symbol or "").upper()
    chain = str(chain or "")

    if symbol == "BTC" or chain == CHAIN_BTC:
        return "<span class='alert-btc-icon'>₿</span>"

    if symbol == "ETH" or chain == CHAIN_ETH:
        return (
            "<svg class='alert-eth-icon' viewBox='0 0 64 64' aria-hidden='true'>"
            "<defs>"
            "<linearGradient id='alertEthTop' x1='0%' y1='0%' x2='100%' y2='100%'>"
            "<stop offset='0%' stop-color='#EAF0FF'/>"
            "<stop offset='45%' stop-color='#C2D1FF'/>"
            "<stop offset='100%' stop-color='#8FAAFF'/>"
            "</linearGradient>"
            "<linearGradient id='alertEthBottom' x1='0%' y1='0%' x2='100%' y2='100%'>"
            "<stop offset='0%' stop-color='#B2C4FF'/>"
            "<stop offset='50%' stop-color='#92AAFF'/>"
            "<stop offset='100%' stop-color='#718EFF'/>"
            "</linearGradient>"
            "<linearGradient id='alertEthCore' x1='0%' y1='0%' x2='100%' y2='100%'>"
            "<stop offset='0%' stop-color='#D4DEFF'/>"
            "<stop offset='100%' stop-color='#9EB4FF'/>"
            "</linearGradient>"
            "</defs>"
            "<polygon points='32,4 16,31 32,23 48,31' fill='url(#alertEthTop)'/>"
            "<polygon points='32,23 16,31 32,40 48,31' fill='url(#alertEthCore)' opacity='0.95'/>"
            "<polygon points='32,60 16,34 32,43 48,34' fill='url(#alertEthBottom)'/>"
            "</svg>"
        )

    # Preserve existing icons for stablecoins / other assets.
    return get_asset_meta(symbol, chain).get("icon", "🪙")


def simple_sentiment_score(text):
    text = (text or "").lower()
    pos = ["surge", "gain", "bullish", "positive", "approval", "adoption", "strong", "rally"]
    neg = ["drop", "hack", "lawsuit", "bearish", "negative", "selloff", "crash", "fear", "fraud"]
    score = 0
    for w in pos:
        if w in text:
            score += 1
    for w in neg:
        if w in text:
            score -= 1
    if score > 0:
        return min(score / 5, 1.0)
    if score < 0:
        return max(score / 5, -1.0)
    return 0.0


def hex_to_address(topic_hex):
    if not topic_hex:
        return ""
    return "0x" + topic_hex[-40:]

def fear_greed_style(classification):
    text = (classification or "").lower()
    if "extreme fear" in text:
        return "#ff7a59", "rgba(255,122,89,0.14)", "rgba(255,122,89,0.30)"
    if text == "fear":
        return "#ffbe5c", "rgba(255,190,92,0.14)", "rgba(255,190,92,0.28)"
    if text == "neutral":
        return "#7cf8ff", "rgba(124,248,255,0.14)", "rgba(124,248,255,0.28)"
    if "greed" in text:
        return "#6dff9d", "rgba(109,255,157,0.14)", "rgba(109,255,157,0.28)"
    return "#7cf8ff", "rgba(124,248,255,0.14)", "rgba(124,248,255,0.28)"


def render_stat_card(label, value, icon="", accent="#FFB21E", glow=False, badge_text=None, badge_colors=None, secondary=False, compact=False, subtext=None):
    glow_class = " glow-card" if glow else ""
    secondary_class = " secondary-card" if secondary else ""
    compact_class = " compact-kpi" if compact else ""
    icon_html = f"<div class='metric-icon'>{icon}</div>" if icon else ""
    accent_bar = f"<div class='metric-accent' style='background:linear-gradient(90deg, transparent, {accent}, transparent); box-shadow:0 0 18px {accent}, 0 0 34px {accent}55;'></div>"
    badge_html = ""

    if badge_text:
        bg = badge_colors[0] if badge_colors else "rgba(124,248,255,0.14)"
        border = badge_colors[1] if badge_colors else "rgba(124,248,255,0.28)"
        badge_html = f"<div class='metric-badge' style='color:{accent}; background:{bg}; border:1px solid {border};'>{badge_text}</div>"

    subtext_html = (
        f"<div class='metric-subtext'>{subtext}</div>"
        if subtext
        else ""
    )

    if compact:
        html = (
            f"<div class='metric-card{glow_class}{secondary_class}{compact_class}'>"
            f"{accent_bar}"
            f"<div class='metric-main'>"
            f"<div class='metric-kpi-layout'>"
            f"<div class='metric-kpi-icon-ring'>{icon_html}</div>"
            f"<div class='metric-kpi-copy'>"
            f"<div class='metric-label'>{label}</div>"
            f"<div class='metric-value'>{str(value)}</div>"
            f"{subtext_html}"
            f"</div>"
            f"</div>"
            f"</div>"
            f"</div>"
        )
    else:
        html = (
            f"<div class='metric-card{glow_class}{secondary_class}{compact_class}'>"
            f"{accent_bar}"
            f"<div class='metric-main'>"
            f"<div class='metric-head'>"
            f"<div class='metric-head-left'>{icon_html}<div class='metric-label'>{label}</div></div>"
            f"{badge_html}"
            f"</div>"
            f"<div class='metric-value'>{str(value)}</div>"
            f"{subtext_html}"
            f"</div>"
            f"</div>"
        )

    st.markdown(html, unsafe_allow_html=True)




def render_fear_greed_mini_card(fg):
    raw_value = fg.get("value")
    value = float(raw_value) if raw_value is not None else 0.0
    value = max(0.0, min(100.0, value))
    classification = fg.get("classification") or "Unavailable"
    classification_color, _, _ = fear_greed_style(classification)

    html_card = (
        f'<div class="mini-fg-card">'
        f'<div class="mini-fg-head"><span class="fear-greed-icon">◐</span>'
        f'<span>Fear &amp; Greed Index</span></div>'
        f'<div class="mini-fg-body">'
        f'<div class="mini-fg-gauge"></div>'
        f'<div><div class="mini-fg-value">{value:.0f}</div>'
        f'<div class="mini-fg-status" style="color:{classification_color} !important;">'
        f'{_safe_html(classification)}</div></div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(html_card, unsafe_allow_html=True)


def render_home_news_preview(news_df: pd.DataFrame):
    """Render two compact latest-news items for the homepage."""
    with st.container(border=True, key="home_news_preview_card"):
        news_heading_col, news_action_col = st.columns([5.3, 1.0], gap="small")

        with news_heading_col:
            st.markdown(
                '<div class="home-panel-title home-compact-title">'
                '<span class="home-news-title-icon">'
                '<svg viewBox="0 0 24 24" aria-hidden="true">'
                '<rect x="4" y="3.5" width="16" height="17" rx="2.5"></rect>'
                '<rect x="7" y="7" width="3.2" height="3.2" rx="0.45"></rect>'
                '<line x1="12.4" y1="8.6" x2="17" y2="8.6"></line>'
                '<line x1="7" y1="13" x2="17" y2="13"></line>'
                '<line x1="7" y1="16.6" x2="17" y2="16.6"></line>'
                '</svg>'
                '</span>'
                '<span>MARKET NEWS</span>'
                '</div>',
                unsafe_allow_html=True,
            )

        with news_action_col:
            st.button(
                "VIEW ALL",
                key="home_news_view_all",
                use_container_width=True,
                on_click=set_nav_view,
                args=("news",),
            )

        if news_df.empty:
            st.markdown(
                '<div style="color:#AAA399;font-size:0.85rem;padding:8px 2px 12px 2px;">'
                'No market news available right now.'
                '</div>',
                unsafe_allow_html=True,
            )
            return

        items = []
        for idx, (_, row) in enumerate(news_df.head(2).iterrows()):
            title = _safe_html(row.get("title") or "Latest blockchain update")
            description = _safe_html(row.get("description") or "")
            source = _safe_html(row.get("source") or "Unknown source")
            url = _safe_html(row.get("url") or "#")
            image_url = str(row.get("image") or "").strip()
            age = _safe_html(news_time_ago(row.get("published_at")))

            if image_url:
                media = (
                    f'<img class="home-news-thumb" src="{_safe_html(image_url)}" '
                    f'alt="News thumbnail">'
                )
            else:
                fallback = "◈" if idx == 0 else "₿"
                media = f'<div class="home-news-fallback">{fallback}</div>'

            items.append(
                f'<div class="home-news-item">'
                f'{media}'
                f'<div class="home-news-copy">'
                f'<a class="home-news-title" href="{url}" target="_blank" '
                f'rel="noopener noreferrer">{title}</a>'
                f'<div class="home-news-desc">{description[:155]}</div>'
                f'<div class="home-news-meta">{age} &nbsp; • &nbsp; {source}</div>'
                f'</div>'
                f'</div>'
            )

        st.markdown(
            '<div class="home-news-grid">' + "".join(items) + '</div>',
            unsafe_allow_html=True,
        )


def render_fear_greed_index_card(fg):
    """Render a premium full-width Fear & Greed Index card."""
    raw_value = fg.get("value")
    is_available = raw_value is not None

    value = float(raw_value) if is_available else 0.0
    value = max(0.0, min(100.0, value))
    classification = fg.get("classification") or "Unavailable"

    classification_color, _, _ = fear_greed_style(classification)

    if not is_available or classification == "Unavailable":
        description = "The latest Fear & Greed reading is currently unavailable."
        gauge_value_text = "N/A"
    elif value < 25:
        description = "Market sentiment shows extreme caution and elevated risk aversion."
        gauge_value_text = f"{value:.0f}"
    elif value < 45:
        description = "Market sentiment is cautious, with fear currently outweighing confidence."
        gauge_value_text = f"{value:.0f}"
    elif value < 56:
        description = "Market sentiment is broadly balanced between fear and greed."
        gauge_value_text = f"{value:.0f}"
    elif value < 75:
        description = "Market confidence is improving, with greed beginning to dominate."
        gauge_value_text = f"{value:.0f}"
    else:
        description = "Market sentiment reflects strong optimism and elevated risk appetite."
        gauge_value_text = f"{value:.0f}"

    fig = go.Figure(
        go.Indicator(
            mode="gauge",
            value=value,
            gauge={
                "shape": "angular",
                "axis": {
                    "range": [0, 100],
                    "visible": False,
                },
                "bar": {
                    "color": "rgba(255,255,255,0)",
                    "thickness": 0.25,
                },
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 12], "color": "#B83B38"},
                    {"range": [12, 25], "color": "#D65740"},
                    {"range": [25, 37], "color": "#E78143"},
                    {"range": [37, 45], "color": "#F0A34A"},
                    {"range": [45, 55], "color": "#E4CF52"},
                    {"range": [55, 67], "color": "#B4D653"},
                    {"range": [67, 75], "color": "#80D058"},
                    {"range": [75, 88], "color": "#49C868"},
                    {"range": [88, 100], "color": "#24B768"},
                ],
                "threshold": {
                    "line": {
                        "color": "#FFFFFF",
                        "width": 7,
                    },
                    "thickness": 0.86,
                    "value": value,
                },
            },
            domain={"x": [0.07, 0.93], "y": [0.02, 0.90]},
        )
    )

    # Large centre reading
    fig.add_annotation(
        x=0.50,
        y=0.25,
        xref="paper",
        yref="paper",
        text=f"<b>{gauge_value_text}</b>",
        showarrow=False,
        font={
            "size": 32,
            "color": "#FFFFFF",
            "family": "Inter, Segoe UI, Arial, sans-serif",
        },
    )

    # Classification below the number
    fig.add_annotation(
        x=0.50,
        y=0.12,
        xref="paper",
        yref="paper",
        text=f"<b>{classification}</b>",
        showarrow=False,
        font={
            "size": 18,
            "color": classification_color,
            "family": "Inter, Segoe UI, Arial, sans-serif",
        },
    )

    fig.update_layout(
        height=220,
        margin=dict(l=4, r=4, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family="Inter, Segoe UI, Arial, sans-serif",
            color="#FFFFFF",
        ),
    )

    with st.container(key="fear_greed_index_card"):
        st.markdown(
            """
            <div class="fg-index-header">
                <div class="fg-index-title-wrap">
                    <span class="fg-index-icon-ring"><span class="fg-index-icon">◐</span></span>
                    <div class="fg-index-title">FEAR &amp; GREED INDEX</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        gauge_col, insight_col = st.columns([1.72, 0.88], gap="large")

        with gauge_col:
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={
                    "displayModeBar": False,
                    "responsive": True,
                    "staticPlot": True,
                },
                key="top_fear_greed_gauge",
            )

            st.markdown(
                """
                <div class="fg-index-scale">
                    <span class="fear-side">EXTREME FEAR</span>
                    <span class="neutral-side">NEUTRAL</span>
                    <span class="greed-side">EXTREME GREED</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with insight_col:
            # Build the HTML without leading indentation.
            # Streamlit Markdown can interpret indented HTML after blank lines
            # as a Markdown code block, which is why the raw <div> tags were
            # appearing in a white box.
            insight_html = (
                f'<div class="fg-insight-panel">'
                f'<div class="fg-insight-content">'
                f'<div class="fg-insight-kicker">Sentiment Insight</div>'
                f'<div class="fg-insight-status-row">'
                f'<span class="fg-live-dot"></span>'
                f'<span class="fg-insight-status" style="color:{classification_color};">'
                f'{classification}'
                f'</span>'
                f'</div>'
                f'<div class="fg-insight-description">{description}</div>'
                f'<div class="fg-score-row">'
                f'<span class="fg-score-label">INDEX SCORE</span>'
                f'<span class="fg-score-value"><span class="fg-score-value-main">{gauge_value_text}</span><span class="fg-score-value-total">/ 100</span></span>'
                f'</div>'
                f'<div class="fg-source-row">'
                f'<span class="fg-source-label">DATA SOURCE</span>'
                f'<span class="fg-source-value">alternative.me</span>'
                f'</div>'
                f'</div>'
                f'</div>'
            )
            st.markdown(insight_html, unsafe_allow_html=True)



def _safe_html(value) -> str:
    """Escape values before inserting them into custom HTML."""
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return html.escape(str(value))


def render_transaction_detail_page(tx_hash: str, alerts_df: pd.DataFrame):
    """Render a Whale Alert Details page using the same alert-card design as Whale Alerts."""
    tx_hash = str(tx_hash or "").strip()

    st.markdown("<div class='tx-detail-shell'>", unsafe_allow_html=True)
    st.markdown(
        "<div class='tx-back-row'>"
        "<a class='tx-back-link' href='?' target='_self'>← Back to Dashboard</a>"
        "</div>",
        unsafe_allow_html=True,
    )

    if not tx_hash or alerts_df.empty or "tx_hash" not in alerts_df.columns:
        st.markdown(
            "<div class='tx-not-found'>"
            "Transaction details are not available in the current scan window."
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    matched = alerts_df[
        alerts_df["tx_hash"].astype(str).str.lower() == tx_hash.lower()
    ]

    if matched.empty:
        st.markdown("<div class='tx-page-title'>Whale Alert Details</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='tx-not-found'>"
            "This transaction is no longer present in the current Novaris scan window. "
            "Return to the dashboard and select a recent alert."
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    row = matched.iloc[0]
    chain = str(row.get("chain") or "")
    asset_symbol = str(row.get("asset_symbol") or "")
    meta = get_asset_meta(asset_symbol, chain)

    amount_native = row.get("amount_native")
    amount_usd = row.get("amount_usd")

    amount_text = (
        f"{format_amount(amount_native)} {asset_symbol}"
        if pd.notna(amount_native)
        else asset_symbol
    )
    usd_text = (
        f"${float(amount_usd):,.0f}"
        if pd.notna(amount_usd)
        else "USD unavailable"
    )

    from_addr = str(row.get("from") or "Unknown")
    to_addr = str(row.get("to") or "Unknown")
    direction = str(row.get("direction") or "")
    source_type = str(row.get("source_type") or "network")
    watch_address = str(row.get("watch_address") or "")
    final_risk = str(row.get("final_risk") or "Low")
    event_note = str(row.get("event_note") or "")

    timestamp = pd.to_datetime(row.get("timestamp"), utc=True, errors="coerce")
    if pd.isna(timestamp):
        timestamp_text = "Timestamp unavailable"
        age_text = ""
    else:
        timestamp_text = timestamp.strftime("%a, %d %b %Y %H:%M:%S UTC")
        age_text = human_age(timestamp)

    if source_type == "watchlist":
        route_text = (
            f"{direction} involving watchlist wallet "
            f"{short_addr(watch_address) if watch_address else '—'}"
        )
        source_label = "Watchlist"
        source_badge = "badge-watch"
    else:
        route_text = f"transferred from {short_addr(from_addr)} to {short_addr(to_addr)}"
        source_label = "Network"
        source_badge = "badge-net"

    chain_badge = "badge-eth" if chain == CHAIN_ETH else "badge-btc"
    if final_risk == "High":
        risk_badge = "badge-high"
    elif final_risk == "Medium":
        risk_badge = "badge-medium"
    else:
        risk_badge = "badge-low"

    explorer_url = (
        f"https://etherscan.io/tx/{tx_hash}"
        if chain == CHAIN_ETH
        else f"https://www.blockchain.com/explorer/transactions/btc/{tx_hash}"
    )

    st.markdown("<div class='tx-page-title'>Whale Alert Details</div>", unsafe_allow_html=True)

    # Use the exact same card composition as the Whale Alerts list:
    # matching asset icon, amount/USD typography, route text, badges and age.
    whale_summary_html = (
        f'<div class="tx-whale-alert-summary">'
        f'<div class="alert-card whale-card">'
        f'<div class="alert-row">'
        f'<div class="alert-left">'
        f'<div class="asset-circle">'
        f'{get_alert_asset_icon(asset_symbol, chain)}'
        f'</div>'
        f'<div class="alert-content">'
        f'<div class="alert-title">'
        f'<span class="alert-amount">{_safe_html(amount_text)}</span>'
        f'<span class="alert-usd">{_safe_html(usd_text)}</span>'
        f'</div>'
        f'<div class="alert-sub">{_safe_html(route_text)}</div>'
        f'<div class="alert-badges">'
        f'<span class="badge {chain_badge}">{_safe_html(chain)}</span>'
        f'<span class="badge {risk_badge}">{_safe_html(final_risk)}</span>'
        f'<span class="badge {source_badge}">{_safe_html(source_label)}</span>'
        f'</div>'
        f'</div>'
        f'</div>'
        f'<div class="alert-time">{_safe_html(age_text)}</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(whale_summary_html, unsafe_allow_html=True)

    info_html = (
        f'<div class="tx-info-card">'
        f'<div class="tx-section-title">Transaction Information</div>'
        f'<div class="tx-detail-grid">'
        f'<div class="tx-detail-label">Blockchain</div>'
        f'<div class="tx-detail-value">{_safe_html(chain)}</div>'
        f'<div class="tx-detail-label">Asset</div>'
        f'<div class="tx-detail-value">{_safe_html(meta["label"])} ({_safe_html(asset_symbol)})</div>'
        f'<div class="tx-detail-label">Timestamp</div>'
        f'<div class="tx-detail-value">{_safe_html(timestamp_text)}</div>'
        f'<div class="tx-detail-label">Transaction Hash</div>'
        f'<div class="tx-detail-value tx-hash-value">{_safe_html(tx_hash)}</div>'
        f'<div class="tx-detail-label">Source</div>'
        f'<div class="tx-detail-value">{_safe_html(source_label)}</div>'
        f'<div class="tx-detail-label">Risk Level</div>'
        f'<div class="tx-detail-value">{_safe_html(final_risk)}</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(info_html, unsafe_allow_html=True)

    from_meta = "Sender wallet"
    to_meta = "Receiver wallet"
    if watch_address:
        if from_addr.lower() == watch_address.lower():
            from_meta = "Watchlist wallet"
        if to_addr.lower() == watch_address.lower():
            to_meta = "Watchlist wallet"

    transfer_html = (
        f'<div class="tx-transfer-card">'
        f'<div class="tx-section-title">Transfer</div>'
        f'<div class="tx-transfer-grid">'
        f'<div>'
        f'<div class="tx-wallet-label">Sender</div>'
        f'<div class="tx-wallet-address">{_safe_html(from_addr)}</div>'
        f'<div class="tx-wallet-meta">{_safe_html(from_meta)}</div>'
        f'</div>'
        f'<div class="tx-arrow-wrap">'
        f'<div class="tx-arrow">→</div>'
        f'<div class="tx-transfer-amount">{_safe_html(amount_text)}</div>'
        f'</div>'
        f'<div>'
        f'<div class="tx-wallet-label">Receiver</div>'
        f'<div class="tx-wallet-address">{_safe_html(to_addr)}</div>'
        f'<div class="tx-wallet-meta">{_safe_html(to_meta)}</div>'
        f'</div>'
        f'</div>'
    )

    if event_note:
        transfer_html += (
            f'<div style="margin-top:18px; padding-top:14px; '
            f'border-top:1px solid rgba(255,255,255,0.07);">'
            f'<div class="tx-detail-label">Event Note</div>'
            f'<div class="tx-detail-value" style="margin-top:6px;">'
            f'{_safe_html(event_note)}</div>'
            f'</div>'
        )

    transfer_html += (
        f'<div style="margin-top:18px;">'
        f'<a class="tx-explorer-link" href="{_safe_html(explorer_url)}" '
        f'target="_blank" rel="noopener noreferrer">'
        f'Open in blockchain explorer ↗'
        f'</a>'
        f'</div>'
        f'</div>'
    )
    st.markdown(transfer_html, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# CACHED DATA SOURCES
# =========================================================
@st.cache_data(ttl=300)
def fetch_price_map():
    ids = list(set(TOKEN_PRICE_IDS.values()))
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": ",".join(ids), "vs_currencies": "usd"}
    try:
        data = safe_get_json(url, params=params)
        out = {"BTC": None, "ETH": None, "USDT": 1.0, "USDC": 1.0, "DAI": 1.0, "WBTC": None}
        for sym, cg_id in TOKEN_PRICE_IDS.items():
            if cg_id in data and "usd" in data[cg_id]:
                out[sym] = float(data[cg_id]["usd"])
        return out
    except Exception:
        return {"BTC": None, "ETH": None, "USDT": 1.0, "USDC": 1.0, "DAI": 1.0, "WBTC": None}


@st.cache_data(ttl=120)
def fetch_market_overview():
    """Fetch BTC/ETH price, 24H change and sparkline data from CoinGecko."""
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": "bitcoin,ethereum",
        "order": "market_cap_desc",
        "sparkline": "true",
        "price_change_percentage": "24h",
    }

    columns = [
        "id",
        "symbol",
        "name",
        "current_price",
        "price_change_percentage_24h",
        "sparkline",
    ]

    try:
        rows = safe_get_json(url, params=params)
        output = []

        for row in rows or []:
            sparkline = (
                (row.get("sparkline_in_7d") or {}).get("price")
                or []
            )

            output.append(
                {
                    "id": str(row.get("id") or ""),
                    "symbol": str(row.get("symbol") or "").upper(),
                    "name": str(row.get("name") or ""),
                    "current_price": pd.to_numeric(
                        row.get("current_price"),
                        errors="coerce",
                    ),
                    "price_change_percentage_24h": pd.to_numeric(
                        row.get("price_change_percentage_24h"),
                        errors="coerce",
                    ),
                    "sparkline": sparkline,
                }
            )

        return pd.DataFrame(output, columns=columns)
    except Exception:
        return pd.DataFrame(columns=columns)


@st.cache_data(ttl=300)
def fetch_fear_greed():
    try:
        data = safe_get_json("https://api.alternative.me/fng/", params={"limit": 1})
        row = data.get("data", [{}])[0]
        value = float(row.get("value", 50))
        return {
            "value": value,
            "classification": row.get("value_classification", "Unknown"),
            "normalized_score": (value - 50.0) / 50.0
        }
    except Exception:
        return {"value": None, "classification": "Unavailable", "normalized_score": 0.0}


@st.cache_data(ttl=300)
def fetch_news_articles(query, api_key):
    """
    Fetch crypto/blockchain news.

    Priority:
    1. GNews API when GNEWS_API_KEY is available.
    2. Google News RSS fallback when there is no API key or GNews fails.
    3. If the custom query returns nothing, retry with a broader crypto query.
    """
    columns = [
        "published_at",
        "source",
        "title",
        "description",
        "url",
        "image",
        "sentiment_score",
        "sentiment_label",
    ]

    def finalize_rows(rows):
        if not rows:
            return pd.DataFrame(columns=columns)

        out = pd.DataFrame(rows)

        for col in columns:
            if col not in out.columns:
                out[col] = None

        out["published_at"] = pd.to_datetime(
            out["published_at"],
            utc=True,
            errors="coerce",
        )

        out = (
            out.dropna(subset=["title", "url"])
            .drop_duplicates(subset=["title"], keep="first")
            .sort_values("published_at", ascending=False, na_position="last")
            .reset_index(drop=True)
        )

        return out[columns]

    def add_sentiment(row):
        article_text = f"{row.get('title', '')}. {row.get('description', '')}"
        score = simple_sentiment_score(article_text)

        if score > 0.12:
            label = "Positive"
        elif score < -0.12:
            label = "Negative"
        else:
            label = "Neutral"

        row["sentiment_score"] = score
        row["sentiment_label"] = label
        return row

    def fetch_from_gnews(search_query):
        if not api_key:
            return []

        try:
            data = safe_get_json(
                "https://gnews.io/api/v4/search",
                params={
                    "q": search_query,
                    "lang": "en",
                    "max": 10,
                    "sortby": "publishedAt",
                    "apikey": api_key,
                },
            )

            rows = []
            for article in data.get("articles", []):
                rows.append(
                    add_sentiment(
                        {
                            "published_at": article.get("publishedAt"),
                            "source": (article.get("source") or {}).get("name"),
                            "title": article.get("title"),
                            "description": article.get("description"),
                            "url": article.get("url"),
                            "image": article.get("image"),
                        }
                    )
                )
            return rows

        except Exception:
            return []

    def clean_rss_description(raw_html):
        if not raw_html:
            return ""

        cleaned = html.unescape(str(raw_html))
        cleaned = re.sub(r"<br\s*/?>", " ", cleaned, flags=re.I)
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # Google News RSS descriptions can repeat publisher/link information.
        # Keep the preview concise for the dashboard.
        if len(cleaned) > 420:
            cleaned = cleaned[:417].rstrip() + "..."

        return cleaned

    def fetch_from_google_rss(search_query):
        try:
            response = requests.get(
                "https://news.google.com/rss/search",
                params={
                    "q": search_query,
                    "hl": "en-US",
                    "gl": "US",
                    "ceid": "US:en",
                },
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 Chrome/120 Safari/537.36"
                    )
                },
                timeout=20,
            )
            response.raise_for_status()

            root = ET.fromstring(response.content)
            rows = []

            for item in root.findall(".//item")[:12]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                raw_description = item.findtext("description") or ""
                description = clean_rss_description(raw_description)

                source_el = item.find("source")
                source = (
                    (source_el.text or "").strip()
                    if source_el is not None
                    else "Google News"
                )

                pub_date_raw = (item.findtext("pubDate") or "").strip()
                try:
                    published_at = parsedate_to_datetime(pub_date_raw)
                    if published_at.tzinfo is None:
                        published_at = published_at.replace(tzinfo=timezone.utc)
                except Exception:
                    published_at = None

                if title and link:
                    rows.append(
                        add_sentiment(
                            {
                                "published_at": published_at,
                                "source": source,
                                "title": title,
                                "description": description,
                                "url": link,
                                "image": None,
                            }
                        )
                    )

            return rows

        except Exception:
            return []

    search_query = (query or "").strip()
    if not search_query:
        search_query = "Bitcoin OR Ethereum OR cryptocurrency OR blockchain"

    # 1. Use GNews when configured.
    rows = fetch_from_gnews(search_query)

    # 2. No API key / GNews error / zero results -> free RSS fallback.
    if not rows:
        rows = fetch_from_google_rss(search_query)

    # 3. A very restrictive custom query can still produce no articles.
    #    Retry automatically with a broad blockchain-news query.
    if not rows:
        broad_query = (
            "Bitcoin OR Ethereum OR cryptocurrency OR blockchain "
            "OR crypto market"
        )
        rows = fetch_from_google_rss(broad_query)

    return finalize_rows(rows)



def classify_news_tags(title: str, description: str):
    """Return simple display tags from article text."""
    combined = f"{title or ''} {description or ''}".lower()
    tags = []

    tag_rules = [
        ("Bitcoin", ["bitcoin", "btc"]),
        ("Ethereum", ["ethereum", "eth"]),
        ("Whale", ["whale", "large transfer", "large transaction"]),
        ("Regulation", ["sec", "regulation", "regulator", "law", "government"]),
        ("Security", ["hack", "exploit", "security", "scam", "breach"]),
        ("ETF", ["etf"]),
        ("Trading", ["trading", "liquidation", "futures", "derivative"]),
        ("Market", ["market", "price", "rally", "sell-off", "selloff"]),
    ]

    for label, keywords in tag_rules:
        if any(keyword in combined for keyword in keywords):
            tags.append(label)

    return tags[:3] or ["Blockchain"]


def news_time_ago(value):
    """Compact age label for the news feed."""
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return ""

    now = pd.Timestamp.now(tz="UTC")
    delta = now - ts

    seconds = max(0, int(delta.total_seconds()))
    if seconds < 60:
        return "Just now"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"

    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"

    days = hours // 24
    if days == 1:
        return "1d ago"
    return f"{days}d ago"


def _market_sparkline_svg(values, asset_symbol):
    """Build a lightweight NOVARIS-themed SVG sparkline."""
    clean_values = [
        float(v)
        for v in (values or [])
        if pd.notna(v)
    ]

    # CoinGecko's 7D sparkline normally contains many points.
    # Use the latest portion so the mini chart reads as a recent trend.
    if len(clean_values) > 48:
        clean_values = clean_values[-48:]

    if len(clean_values) < 2:
        return (
            '<div class="market-chart-empty">'
            '<span></span><span></span><span></span>'
            '</div>'
        )

    width = 210.0
    height = 62.0
    pad_x = 5.0
    pad_y = 7.0

    min_v = min(clean_values)
    max_v = max(clean_values)
    spread = max(max_v - min_v, 1e-9)

    points = []
    count = len(clean_values)

    for idx, value in enumerate(clean_values):
        x = pad_x + ((width - 2 * pad_x) * idx / max(count - 1, 1))
        y = (
            height
            - pad_y
            - ((height - 2 * pad_y) * (value - min_v) / spread)
        )
        points.append(f"{x:.1f},{y:.1f}")

    if str(asset_symbol).upper() == "BTC":
        stroke = "#FFB21E"
        glow = "rgba(255,178,30,0.22)"
    else:
        stroke = "#8FAAFF"
        glow = "rgba(143,170,255,0.22)"

    return (
        f'<svg class="market-sparkline" viewBox="0 0 {int(width)} {int(height)}" '
        f'role="img" aria-label="{html.escape(str(asset_symbol))} recent price trend">'
        f'<defs>'
        f'<filter id="marketGlow{html.escape(str(asset_symbol))}" x="-20%" y="-40%" width="140%" height="180%">'
        f'<feDropShadow dx="0" dy="0" stdDeviation="2.4" flood-color="{stroke}" flood-opacity="0.36"/>'
        f'</filter>'
        f'</defs>'
        f'<polyline points="{" ".join(points)}" fill="none" stroke="{stroke}" '
        f'stroke-width="3" stroke-linecap="round" stroke-linejoin="round" '
        f'filter="url(#marketGlow{html.escape(str(asset_symbol))})"/>'
        f'</svg>'
    )


def render_market_page(prices, market_df: pd.DataFrame):
    """Render NOVARIS Crypto Market Prices using the CoinGecko market snapshot."""
    st.markdown(
        """
        <div class="market-page-hero">
            <div class="market-page-title">Crypto Market Prices</div>
            <div class="market-page-subtitle">
                Bitcoin and Ethereum spot prices with recent market movement.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    market_lookup = {}
    if market_df is not None and not market_df.empty:
        for _, row in market_df.iterrows():
            market_lookup[str(row.get("symbol") or "").upper()] = row

    assets = [
        {
            "symbol": "BTC",
            "name": "Bitcoin",
            "icon": "<span class='market-btc-icon'>₿</span>",
        },
        {
            "symbol": "ETH",
            "name": "Ethereum",
            "icon": get_alert_asset_icon("ETH", CHAIN_ETH),
        },
    ]

    # Build the COMPLETE table in one HTML block.
    # Streamlit creates a separate DOM wrapper for every st.markdown call,
    # so opening the shell in one call and adding rows in later calls caused
    # the rows to escape the centred container and stretch across the page.
    market_html = [
        '<div class="market-table-shell">',
        '<div class="market-table-header">',
        '<div>ASSET</div>',
        '<div>PRICE</div>',
        '<div>CHART</div>',
        '<div>24H CHANGE</div>',
        '</div>',
    ]

    for asset in assets:
        symbol = asset["symbol"]
        row = market_lookup.get(symbol)

        current_price = prices.get(symbol)
        change = None
        sparkline = []

        if row is not None:
            row_price = pd.to_numeric(
                row.get("current_price"),
                errors="coerce",
            )
            if pd.notna(row_price):
                current_price = float(row_price)

            row_change = pd.to_numeric(
                row.get("price_change_percentage_24h"),
                errors="coerce",
            )
            if pd.notna(row_change):
                change = float(row_change)

            sparkline = row.get("sparkline") or []

        price_text = (
            f"${float(current_price):,.2f}"
            if current_price is not None and pd.notna(current_price)
            else "N/A"
        )

        if change is None or pd.isna(change):
            change_text = "—"
            change_class = "market-change-neutral"
            change_arrow = ""
        elif change > 0:
            change_text = f"{abs(change):.2f}%"
            change_class = "market-change-positive"
            change_arrow = "↗"
        elif change < 0:
            change_text = f"{abs(change):.2f}%"
            change_class = "market-change-negative"
            change_arrow = "↘"
        else:
            change_text = "0.00%"
            change_class = "market-change-neutral"
            change_arrow = "→"

        spark_svg = _market_sparkline_svg(sparkline, symbol)

        market_html.extend(
            [
                '<div class="market-table-row">',
                '<div class="market-asset-cell">',
                f'<div class="market-asset-icon">{asset["icon"]}</div>',
                '<div class="market-asset-copy">',
                f'<div class="market-asset-name">{html.escape(asset["name"])}</div>',
                f'<div class="market-asset-symbol">{symbol}</div>',
                '</div>',
                '</div>',
                f'<div class="market-price-cell">{price_text}</div>',
                f'<div class="market-chart-cell">{spark_svg}</div>',
                (
                    f'<div class="market-change-cell {change_class}">'
                    f'<span>{change_arrow}</span> {change_text}'
                    f'</div>'
                ),
                '</div>',
            ]
        )

    market_html.extend(
        [
            '<div class="market-source-row">',
            '<span>DATA SOURCE</span>',
            '<strong>CoinGecko</strong>',
            '<span class="market-source-dot">•</span>',
            '<span>24H change and recent sparkline are market-data estimates.</span>',
            '</div>',
            '</div>',
        ]
    )

    st.markdown("".join(market_html), unsafe_allow_html=True)


def render_news_feed(news_df: pd.DataFrame):
    """Render a premium Whale-Alert-inspired blockchain news feed."""
    st.markdown(
        """
        <div class="news-hero">
            <div>
                <div class="news-page-title">Latest Blockchain News</div>
                <div class="news-page-subtitle">
                    Live crypto-market headlines with lightweight sentiment analysis.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if news_df.empty:
        st.markdown(
            """
            <div class="news-empty">
                <div class="news-empty-title">News feed temporarily unavailable</div>
                <div class="news-empty-copy">
                    Novaris tried both GNews and the Google News RSS fallback.
                    Check your internet connection or try a broader News Query.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    valid_scores = pd.to_numeric(
        news_df.get("sentiment_score"),
        errors="coerce",
    ).dropna()

    avg_score = float(valid_scores.mean()) if not valid_scores.empty else 0.0

    if avg_score > 0.12:
        overall_label = "Positive"
        overall_class = "news-sentiment-positive"
        overall_icon = "↗"
    elif avg_score < -0.12:
        overall_label = "Negative"
        overall_class = "news-sentiment-negative"
        overall_icon = "↘"
    else:
        overall_label = "Neutral"
        overall_class = "news-sentiment-neutral"
        overall_icon = "◐"

    top_row = news_df.iloc[0]
    top_title = _safe_html(top_row.get("title") or "Latest blockchain update")
    top_description = _safe_html(top_row.get("description") or "")
    top_source = _safe_html(top_row.get("source") or "Unknown source")
    top_url = _safe_html(top_row.get("url") or "#")
    top_age = _safe_html(news_time_ago(top_row.get("published_at")))

    st.markdown(
        (
            f'<div class="news-summary-card">'
            f'<div class="news-summary-top">'
            f'<div class="news-summary-label">24H MARKET SENTIMENT</div>'
            f'<div class="news-summary-value {overall_class}">'
            f'<span class="news-summary-icon">{overall_icon}</span> {overall_label}'
            f'</div>'
            f'</div>'
            f'<a class="news-feature-title" href="{top_url}" target="_blank" '
            f'rel="noopener noreferrer">{top_title} ↗</a>'
            f'<div class="news-feature-description">{top_description}</div>'
            f'<div class="news-feature-meta">'
            f'<span>{top_source}</span>'
            f'<span>{top_age}</span>'
            f'</div>'
            f'</div>'
        ),
        unsafe_allow_html=True,
    )

    for _, article in news_df.iterrows():
        title = _safe_html(article.get("title") or "Untitled story")
        description = _safe_html(article.get("description") or "")
        source = _safe_html(article.get("source") or "Unknown source")
        url = _safe_html(article.get("url") or "#")
        age = _safe_html(news_time_ago(article.get("published_at")))
        sentiment = str(article.get("sentiment_label") or "Neutral")

        if sentiment == "Positive":
            sentiment_class = "news-positive"
            sentiment_icon = "↗"
        elif sentiment == "Negative":
            sentiment_class = "news-negative"
            sentiment_icon = "↘"
        else:
            sentiment_class = "news-neutral"
            sentiment_icon = "◐"

        tags = classify_news_tags(
            str(article.get("title") or ""),
            str(article.get("description") or ""),
        )
        tag_html = "".join(
            f'<span class="news-tag">{_safe_html(tag)}</span>'
            for tag in tags
        )

        card_html = (
            f'<div class="news-story-card-wrap">'
            f'<div class="news-story-card">'
            f'<a class="news-story-hitbox" href="{url}" target="_blank" '
            f'rel="noopener noreferrer" aria-label="Open news article"></a>'
            f'<div class="news-story-main">'
            f'<div class="news-story-icon {sentiment_class}">{sentiment_icon}</div>'
            f'<div class="news-story-content">'
            f'<div class="news-story-title">{title} ↗</div>'
            f'<div class="news-story-source">via {source}</div>'
            f'<div class="news-story-description">{description}</div>'
            f'<div class="news-story-tags">{tag_html}</div>'
            f'</div>'
            f'<div class="news-story-side">'
            f'<div class="news-story-time">{age}</div>'
            f'<div class="news-story-sentiment {sentiment_class}">'
            f'{sentiment_icon} {sentiment}'
            f'</div>'
            f'</div>'
            f'</div>'
            f'</div>'
            f'</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)



def render_full_alerts_page(
    all_alerts_df: pd.DataFrame,
    whale_threshold: float,
    page_title: str = "Latest Transfers",
    max_items: int | None = 30,
):
    """Render transfers using the standard NOVARIS transaction alert cards."""
    st.markdown(
        f"<div class='latest-alerts-title'>{html.escape(page_title)}</div>",
        unsafe_allow_html=True,
    )

    if all_alerts_df.empty:
        st.info("No transactions found in the current scan window.")
        return

    display_df = (
        all_alerts_df
        if max_items is None
        else all_alerts_df.head(max_items)
    )

    for _, row in display_df.iterrows():
        meta = get_asset_meta(row["asset_symbol"], row["chain"])
        amount_txt = f"{format_amount(row['amount_native'])} {row['asset_symbol']}"
        usd_txt = (
            f"${row['amount_usd']:,.0f}"
            if pd.notna(row["amount_usd"])
            else "USD unavailable"
        )

        if row["source_type"] == "watchlist":
            line2 = (
                f"{row['direction']} involving watchlist wallet "
                f"{short_addr(row['watch_address'])}"
            )
            source_text = "Watchlist"
            source_badge = "badge-watch"
        else:
            line2 = (
                f"transferred from {short_addr(row['from'])} "
                f"to {short_addr(row['to'])}"
            )
            source_text = "Network"
            source_badge = "badge-net"

        chain_badge = "badge-eth" if row["chain"] == CHAIN_ETH else "badge-btc"

        if row["final_risk"] == "High":
            risk_badge = "badge-high"
        elif row["final_risk"] == "Medium":
            risk_badge = "badge-medium"
        else:
            risk_badge = "badge-low"

        marker = whale_marker(row["amount_usd"])
        whale_class = (
            "whale-card"
            if pd.notna(row["amount_usd"])
            and row["amount_usd"] >= whale_threshold
            else ""
        )

        tx_hash_value = str(row.get("tx_hash") or "").strip()
        alert_href = f"?tx={tx_hash_value}" if tx_hash_value else "#"

        st.markdown(
            f"""
            <a class="alert-card-link full-alert-link" href="{alert_href}" target="_self">
                <div class="alert-card {whale_class}">
                    <div class="alert-row">
                        <div class="alert-left">
                            <div class="asset-circle">{get_alert_asset_icon(row['asset_symbol'], row['chain'])}</div>
                            <div class="alert-content">
                                <div class="alert-title"><span class="alert-amount">{amount_txt}</span><span class="alert-usd">{usd_txt}</span></div>
                                <div class="alert-sub">{line2}</div>
                                <div class="alert-badges">
                                    <span class="badge {chain_badge}">{row['chain']}</span>
                                    <span class="badge {risk_badge}">{row['final_risk']}</span>
                                    <span class="badge {source_badge}">{source_text}</span>
                                </div>
                            </div>
                        </div>
                        <div class="alert-time">{human_age(row["timestamp"])}</div>
                    </div>
                </div>
            </a>
            """,
            unsafe_allow_html=True,
        )


# =========================================================
# ETH RPC
# =========================================================
def eth_rpc(method, params=None):
    payload = {"jsonrpc": "2.0", "method": method, "params": params or [], "id": 1}
    last_error = None

    for rpc_url in ETH_RPC_URLS:
        for _ in range(2):
            try:
                data = safe_post_json(rpc_url, payload)
                if data.get("error"):
                    last_error = RuntimeError(data["error"])
                    continue
                return data.get("result")
            except Exception as e:
                last_error = e
                time.sleep(0.4)

    raise RuntimeError(f"All Ethereum RPC endpoints failed. Last error: {last_error}")


# =========================================================
# BLOCKCHAIN CRAWLER AGENT
# =========================================================
@st.cache_data(ttl=120)
def fetch_eth_network_native(num_blocks, eth_price):
    rows = []
    warnings = []

    try:
        latest_hex = eth_rpc("eth_blockNumber")
        latest_block = int(latest_hex, 16)

        for bn in range(latest_block, latest_block - num_blocks, -1):
            block = eth_rpc("eth_getBlockByNumber", [hex(bn), True])
            if not block:
                continue

            block_time = datetime.fromtimestamp(int(block["timestamp"], 16), tz=timezone.utc)
            txs = block.get("transactions", [])[:80]

            for tx in txs:
                value_wei = int(tx.get("value", "0x0"), 16)
                if value_wei <= 0:
                    continue

                amount_eth = value_wei / 10**18
                amount_usd = amount_eth * eth_price if eth_price else None

                rows.append({
                    "chain": CHAIN_ETH,
                    "asset_symbol": "ETH",
                    "asset_name": "Ethereum",
                    "timestamp": block_time,
                    "tx_hash": tx.get("hash"),
                    "from": tx.get("from", ""),
                    "to": tx.get("to", ""),
                    "direction": "network",
                    "amount_native": amount_eth,
                    "amount_usd": amount_usd,
                    "source_type": "network",
                    "watch_address": None,
                    "event_note": "Network-wide ETH transfer."
                })
    except Exception as e:
        warnings.append(f"Ethereum network fetch failed: {e}")

    return (pd.DataFrame(rows) if rows else empty_alert_df(), warnings)


@st.cache_data(ttl=180)
def fetch_eth_token_metadata(contract_address):
    if not ETHERSCAN_API_KEY or not contract_address:
        return {"symbol": "ERC20", "name": "ERC20 Token", "decimals": 18}

    try:
        data = safe_get_json(
            "https://api.etherscan.io/v2/api",
            params={
                "chainid": 1,
                "module": "token",
                "action": "tokeninfo",
                "contractaddress": contract_address,
                "apikey": ETHERSCAN_API_KEY
            }
        )
        result = data.get("result", [])
        if isinstance(result, list) and result:
            row = result[0]
            return {
                "symbol": (row.get("symbol") or "ERC20").upper(),
                "name": row.get("tokenName") or row.get("symbol") or "ERC20 Token",
                "decimals": int(row.get("divisor", 18))
            }
    except Exception:
        pass

    return {"symbol": "ERC20", "name": "ERC20 Token", "decimals": 18}


@st.cache_data(ttl=120)
def fetch_eth_network_erc20(num_blocks, prices, enabled=False):
    if not enabled:
        return empty_alert_df(), []

    rows = []
    warnings = []

    try:
        latest_hex = eth_rpc("eth_blockNumber")
        latest_block = int(latest_hex, 16)
        start_block = max(0, latest_block - num_blocks + 1)

        logs = eth_rpc("eth_getLogs", [{
            "fromBlock": hex(start_block),
            "toBlock": hex(latest_block),
            "topics": [TRANSFER_TOPIC]
        }])

        logs = logs[:60]
        block_time_cache = {}

        for log in logs:
            topics = log.get("topics", [])
            if len(topics) < 3:
                continue

            contract = log.get("address", "")
            tx_hash = log.get("transactionHash", "")
            block_number = int(log.get("blockNumber", "0x0"), 16)
            raw_amount = int(log.get("data", "0x0"), 16)

            meta = fetch_eth_token_metadata(contract)
            symbol = meta["symbol"]
            decimals = meta["decimals"]
            name = meta["name"]

            amount_native = raw_amount / (10 ** decimals) if decimals >= 0 else float(raw_amount)

            if symbol in STABLECOINS:
                proxy_price = 1.0
            elif symbol == "WBTC":
                proxy_price = prices.get("BTC")
            elif symbol in ["WETH", "ETH"]:
                proxy_price = prices.get("ETH")
            else:
                proxy_price = prices.get(symbol)

            amount_usd = amount_native * proxy_price if proxy_price is not None else None

            if block_number not in block_time_cache:
                try:
                    block = eth_rpc("eth_getBlockByNumber", [hex(block_number), False])
                    block_time_cache[block_number] = datetime.fromtimestamp(int(block["timestamp"], 16), tz=timezone.utc)
                except Exception:
                    block_time_cache[block_number] = datetime.now(timezone.utc)

            rows.append({
                "chain": CHAIN_ETH,
                "asset_symbol": symbol,
                "asset_name": name,
                "timestamp": block_time_cache[block_number],
                "tx_hash": tx_hash,
                "from": hex_to_address(topics[1]),
                "to": hex_to_address(topics[2]),
                "direction": "network",
                "amount_native": amount_native,
                "amount_usd": amount_usd,
                "source_type": "network",
                "watch_address": None,
                "event_note": "Network-wide ERC-20 transfer."
            })
    except Exception as e:
        warnings.append(f"Ethereum ERC-20 network fetch failed: {e}")

    return (pd.DataFrame(rows) if rows else empty_alert_df(), warnings)


@st.cache_data(ttl=180)
def fetch_btc_network_whales(num_blocks, btc_price, tx_per_block):
    rows = []
    warnings = []

    bases = [
        "https://blockstream.info/api",
        "https://mempool.space/api",
    ]

    last_error = None

    for base in bases:
        try:
            tip_height = int(safe_get_text(f"{base}/blocks/tip/height").strip())

            for height in range(tip_height, tip_height - num_blocks, -1):
                block_hash = safe_get_text(f"{base}/block-height/{height}").strip()
                txids = safe_get_json(f"{base}/block/{block_hash}/txids")[:tx_per_block]

                for txid in txids:
                    try:
                        tx = safe_get_json(f"{base}/tx/{txid}")
                    except Exception:
                        continue

                    vins = tx.get("vin", [])
                    vouts = tx.get("vout", [])
                    if not vouts:
                        continue

                    largest_vout = max(vouts, key=lambda x: x.get("value", 0))
                    amount_btc = largest_vout.get("value", 0) / 10**8
                    amount_usd = amount_btc * btc_price if btc_price else None

                    first_from = ""
                    if vins:
                        first_from = (vins[0].get("prevout") or {}).get("scriptpubkey_address", "")

                    first_to = largest_vout.get("scriptpubkey_address", "")
                    block_time_raw = tx.get("status", {}).get("block_time")
                    ts = datetime.fromtimestamp(block_time_raw, tz=timezone.utc) if block_time_raw else datetime.now(timezone.utc)

                    rows.append({
                        "chain": CHAIN_BTC,
                        "asset_symbol": "BTC",
                        "asset_name": "Bitcoin",
                        "timestamp": ts,
                        "tx_hash": tx.get("txid"),
                        "from": first_from,
                        "to": first_to,
                        "direction": "network",
                        "amount_native": amount_btc,
                        "amount_usd": amount_usd,
                        "source_type": "network",
                        "watch_address": None,
                        "event_note": f"Network-wide BTC transfer via {base}."
                    })

            return (pd.DataFrame(rows) if rows else empty_alert_df(), warnings)

        except Exception as e:
            last_error = e
            time.sleep(0.5)

    warnings.append(f"Bitcoin network fetch failed: {last_error}")
    return empty_alert_df(), warnings


def etherscan_account_endpoint(action, address, offset=25):
    return safe_get_json(
        "https://api.etherscan.io/v2/api",
        params={
            "chainid": 1,
            "module": "account",
            "action": action,
            "address": address,
            "startblock": 0,
            "endblock": 999999999,
            "page": 1,
            "offset": offset,
            "sort": "desc",
            "apikey": ETHERSCAN_API_KEY
        }
    )


def token_proxy_usd(symbol, prices):
    symbol = (symbol or "").upper()
    if symbol in STABLECOINS:
        return 1.0
    if symbol in ["WBTC", "TBTC"]:
        return prices.get("BTC")
    if symbol == "WETH":
        return prices.get("ETH")
    return prices.get(symbol)


@st.cache_data(ttl=180)
def fetch_eth_watchlist(addresses, offset, prices):
    if not addresses:
        return empty_alert_df()

    rows = []

    for addr in addresses:
        addr_lower = addr.lower()

        try:
            data = etherscan_account_endpoint("txlist", addr, offset=offset)
            if data.get("status") == "1":
                for tx in data.get("result", []):
                    from_addr = (tx.get("from") or "").lower()
                    to_addr = (tx.get("to") or "").lower()
                    amount_eth = int(tx.get("value", "0")) / 10**18
                    amount_usd = amount_eth * prices.get("ETH") if prices.get("ETH") else None

                    if from_addr == addr_lower and to_addr == addr_lower:
                        direction = "self"
                    elif to_addr == addr_lower:
                        direction = "inflow"
                    elif from_addr == addr_lower:
                        direction = "outflow"
                    else:
                        direction = "other"

                    rows.append({
                        "chain": CHAIN_ETH,
                        "asset_symbol": "ETH",
                        "asset_name": "Ethereum",
                        "timestamp": datetime.fromtimestamp(int(tx.get("timeStamp")), tz=timezone.utc),
                        "tx_hash": tx.get("hash"),
                        "from": from_addr,
                        "to": to_addr,
                        "direction": direction,
                        "amount_native": amount_eth,
                        "amount_usd": amount_usd,
                        "source_type": "watchlist",
                        "watch_address": addr_lower,
                        "event_note": "ETH watchlist transaction."
                    })
        except Exception:
            pass

        try:
            data = etherscan_account_endpoint("tokentx", addr, offset=offset)
            if data.get("status") == "1":
                for tx in data.get("result", []):
                    from_addr = (tx.get("from") or "").lower()
                    to_addr = (tx.get("to") or "").lower()
                    decimals = int(tx.get("tokenDecimal", "0") or 0)
                    raw_value = int(tx.get("value", "0") or 0)
                    amount_token = raw_value / (10 ** decimals) if decimals > 0 else float(raw_value)
                    symbol = (tx.get("tokenSymbol") or "").upper()
                    proxy_price = token_proxy_usd(symbol, prices)
                    amount_usd = amount_token * proxy_price if proxy_price is not None else None

                    if from_addr == addr_lower and to_addr == addr_lower:
                        direction = "self"
                    elif to_addr == addr_lower:
                        direction = "inflow"
                    elif from_addr == addr_lower:
                        direction = "outflow"
                    else:
                        direction = "other"

                    rows.append({
                        "chain": CHAIN_ETH,
                        "asset_symbol": symbol or "ERC20",
                        "asset_name": tx.get("tokenName") or symbol or "ERC20 Token",
                        "timestamp": datetime.fromtimestamp(int(tx.get("timeStamp")), tz=timezone.utc),
                        "tx_hash": tx.get("hash"),
                        "from": from_addr,
                        "to": to_addr,
                        "direction": direction,
                        "amount_native": amount_token,
                        "amount_usd": amount_usd,
                        "source_type": "watchlist",
                        "watch_address": addr_lower,
                        "event_note": "ERC-20 watchlist transaction."
                    })
        except Exception:
            pass

    return pd.DataFrame(rows).sort_values("timestamp", ascending=False).reset_index(drop=True) if rows else empty_alert_df()


@st.cache_data(ttl=180)
def fetch_btc_watchlist(addresses, offset, prices):
    if not addresses:
        return empty_alert_df()

    bases = [
        "https://blockstream.info/api",
        "https://mempool.space/api",
    ]

    rows = []
    for base in bases:
        try:
            for addr in addresses:
                txs = safe_get_json(f"{base}/address/{addr}/txs")[:offset]

                for tx in txs:
                    vin = tx.get("vin", [])
                    vout = tx.get("vout", [])

                    sent_sats = sum(
                        (i.get("prevout") or {}).get("value", 0)
                        for i in vin
                        if (i.get("prevout") or {}).get("scriptpubkey_address", "") == addr
                    )

                    recv_sats = sum(
                        o.get("value", 0)
                        for o in vout
                        if o.get("scriptpubkey_address", "") == addr
                    )

                    net_sats = recv_sats - sent_sats
                    if net_sats == 0:
                        continue

                    amount_btc = abs(net_sats) / 10**8
                    amount_usd = amount_btc * prices.get("BTC") if prices.get("BTC") else None
                    direction = "inflow" if net_sats > 0 else "outflow"

                    first_from = ""
                    for i in vin:
                        first_from = (i.get("prevout") or {}).get("scriptpubkey_address", "")
                        if first_from:
                            break

                    first_to = ""
                    for o in vout:
                        first_to = o.get("scriptpubkey_address", "")
                        if first_to:
                            break

                    block_time_raw = tx.get("status", {}).get("block_time")
                    ts = datetime.fromtimestamp(block_time_raw, tz=timezone.utc) if block_time_raw else datetime.now(timezone.utc)

                    rows.append({
                        "chain": CHAIN_BTC,
                        "asset_symbol": "BTC",
                        "asset_name": "Bitcoin",
                        "timestamp": ts,
                        "tx_hash": tx.get("txid"),
                        "from": first_from,
                        "to": first_to,
                        "direction": direction,
                        "amount_native": amount_btc,
                        "amount_usd": amount_usd,
                        "source_type": "watchlist",
                        "watch_address": addr,
                        "event_note": f"BTC watchlist transaction via {base}."
                    })

            return pd.DataFrame(rows).sort_values("timestamp", ascending=False).reset_index(drop=True) if rows else empty_alert_df()

        except Exception:
            continue

    return empty_alert_df()


# =========================================================
# ANOMALY DETECTION AGENT
# =========================================================
def score_alerts(df, whale_threshold_usd):
    if df.empty:
        out = df.copy()
        for col in ["base_score", "risk_level", "alert_flag", "anomaly_reason"]:
            out[col] = []
        return out

    out = df.copy()

    def compute_score(row):
        usd = row.get("amount_usd")
        if pd.isna(usd) or usd is None:
            score = 0.30
        else:
            ratio = usd / whale_threshold_usd
            if ratio >= 5:
                score = 0.90
            elif ratio >= 2:
                score = 0.78
            elif ratio >= 1:
                score = 0.62
            elif ratio >= 0.5:
                score = 0.45
            else:
                score = 0.22

        if row["source_type"] == "watchlist":
            score += 0.08
        if row["direction"] in ["inflow", "outflow"]:
            score += 0.04
        return min(score, 1.0)

    def bucket(score):
        if score >= 0.78:
            return "High"
        if score >= 0.48:
            return "Medium"
        return "Low"

    def explain(row):
        parts = []
        if pd.notna(row["amount_usd"]):
            parts.append(f"valued at approximately ${row['amount_usd']:,.0f}")
            if row["amount_usd"] >= whale_threshold_usd:
                parts.append("meets whale threshold")
        else:
            parts.append("USD valuation unavailable")
        parts.append(f"source={row['source_type']}")
        return "; ".join(parts) + "."

    out["base_score"] = out.apply(compute_score, axis=1)
    out["risk_level"] = out["base_score"].apply(bucket)
    out["alert_flag"] = True
    out["anomaly_reason"] = out.apply(explain, axis=1)
    return out


# =========================================================
# SENTIMENT FUSION AGENT
# =========================================================
def fuse_sentiment(df, news_df, fear_greed):
    if df.empty:
        out = df.copy()
        for col in [
            "news_sentiment_score", "fear_greed_score", "combined_sentiment_score",
            "combined_sentiment_label", "final_score", "final_risk", "final_explanation"
        ]:
            out[col] = []
        return out

    out = df.copy()
    news_score = news_df["sentiment_score"].mean() if not news_df.empty else 0.0
    fg_score = fear_greed.get("normalized_score", 0.0)
    combined = 0.6 * news_score + 0.4 * fg_score

    def label(score):
        if score <= -0.15:
            return "Negative"
        elif score >= 0.15:
            return "Positive"
        return "Neutral"

    def final_score(row):
        score = row["base_score"]
        if row["direction"] == "outflow" and combined <= -0.2:
            score += 0.06
        elif row["direction"] == "inflow" and combined >= 0.2:
            score += 0.05
        elif row["source_type"] == "network" and abs(combined) >= 0.3:
            score += 0.03
        return min(score, 1.0)

    def risk(score):
        if score >= 0.78:
            return "High"
        elif score >= 0.48:
            return "Medium"
        return "Low"

    out["news_sentiment_score"] = news_score
    out["fear_greed_score"] = fg_score
    out["combined_sentiment_score"] = combined
    out["combined_sentiment_label"] = label(combined)
    out["final_score"] = out.apply(final_score, axis=1)
    out["final_risk"] = out["final_score"].apply(risk)
    out["final_explanation"] = out.apply(
        lambda row: f"{row['anomaly_reason'].rstrip('.')} ; combined sentiment={row['combined_sentiment_label']} ({row['combined_sentiment_score']:.2f}) ; final risk={row['final_risk']}.",
        axis=1
    )
    return out


def render_monitoring_controls_page(prefs):
    """Render the NOVARIS Settings page."""
    # Match the exact page-header treatment used by Latest Blockchain News.
    st.markdown(
        """
        <div class="news-hero settings-page-hero">
            <div>
                <div class="news-page-title">Settings</div>
                <div class="news-page-subtitle">
                    Configure how NOVARIS monitors blockchain activity, identifies
                    whale transfers and retrieves market-related news.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True, key="monitoring_controls_card"):
        st.markdown(
            """
            <div class="settings-card-intro">
                <div>
                    <div class="settings-card-kicker">MONITORING PREFERENCES</div>
                    <div class="settings-card-copy">
                        Changes are applied only after you select Save Preferences.
                        Network-related changes will be used on the next monitoring refresh.
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("monitoring_preferences_form", clear_on_submit=False):
            left_controls, right_controls = st.columns(2, gap="large")

            with left_controls:
                auto_erc20_input = st.checkbox(
                    "Include ERC-20 network scan",
                    value=bool(prefs["auto_erc20"]),
                )
                news_query_input = st.text_input(
                    "News Query",
                    value=str(prefs["news_query"]),
                )
                whale_threshold_input = st.number_input(
                    "Whale Threshold (USD)",
                    min_value=1000.0,
                    value=float(prefs["whale_threshold"]),
                    step=100000.0,
                )

            with right_controls:
                eth_blocks_input = st.slider(
                    "Number of Ethereum Network Blocks",
                    1,
                    3,
                    int(prefs["eth_blocks"]),
                    1,
                )
                btc_blocks_input = st.slider(
                    "Number of Bitcoin Network Blocks",
                    1,
                    10,
                    int(prefs["btc_blocks"]),
                    1,
                )
                btc_txs_per_block_input = st.slider(
                    "Number of Bitcoin Transactions Per Block",
                    10,
                    50,
                    int(prefs["btc_txs_per_block"]),
                    5,
                )

            save_space, save_col = st.columns([3.4, 1.0], gap="large")
            with save_col:
                prefs_saved = st.form_submit_button(
                    "Save Preferences",
                    use_container_width=True,
                )

        if prefs_saved:
            old_prefs = dict(st.session_state.monitoring_prefs)
            new_prefs = {
                "auto_erc20": bool(auto_erc20_input),
                "news_query": str(news_query_input).strip() or DEFAULT_NEWS_QUERY,
                "whale_threshold": float(whale_threshold_input),
                "eth_blocks": int(eth_blocks_input),
                "btc_blocks": int(btc_blocks_input),
                "btc_txs_per_block": int(btc_txs_per_block_input),
            }

            st.session_state.monitoring_prefs = new_prefs

            fetch_keys = {
                "auto_erc20",
                "eth_blocks",
                "btc_blocks",
                "btc_txs_per_block",
            }

            if any(old_prefs.get(k) != new_prefs.get(k) for k in fetch_keys):
                st.session_state.force_network_refresh = True

            if old_prefs.get("news_query") != new_prefs.get("news_query"):
                st.session_state.force_news_refresh = True

            st.success("Settings saved successfully.")



# =========================================================
# SESSION RUNTIME STATE
# =========================================================
# Navigation is kept in Streamlit session state instead of query-string links.
# Clicking the in-app navigation still causes Streamlit's normal lightweight
# script rerun, but it no longer causes a browser URL/page reload and expensive
# API calls are skipped while the stored snapshots are still fresh.
if "nav_view" not in st.session_state:
    st.session_state.nav_view = "home"

if "monitoring_prefs" not in st.session_state:
    st.session_state.monitoring_prefs = {
        "auto_erc20": False,
        "news_query": DEFAULT_NEWS_QUERY,
        "whale_threshold": float(WHALE_THRESHOLD_USD),
        "eth_blocks": min(max(NETWORK_ETH_BLOCKS, 1), 3),
        "btc_blocks": min(max(NETWORK_BTC_BLOCKS, 1), 10),
        "btc_txs_per_block": min(max(BTC_NETWORK_TXS_PER_BLOCK, 10), 50),
    }

# Persistent market/news/network snapshots.
if "prices_data" not in st.session_state:
    st.session_state.prices_data = {
        "BTC": None,
        "ETH": None,
        "USDT": 1.0,
        "USDC": 1.0,
        "DAI": 1.0,
        "WBTC": None,
    }
if "prices_loaded_at" not in st.session_state:
    st.session_state.prices_loaded_at = 0.0

if "market_overview_data" not in st.session_state:
    st.session_state.market_overview_data = pd.DataFrame()
if "market_overview_loaded_at" not in st.session_state:
    st.session_state.market_overview_loaded_at = 0.0

if "fear_greed_data" not in st.session_state:
    st.session_state.fear_greed_data = {
        "value": None,
        "classification": "Unavailable",
        "normalized_score": 0.0,
    }
if "fear_greed_loaded_at" not in st.session_state:
    st.session_state.fear_greed_loaded_at = 0.0

if "news_data" not in st.session_state:
    st.session_state.news_data = pd.DataFrame()
if "news_loaded_at" not in st.session_state:
    st.session_state.news_loaded_at = 0.0
if "news_loaded_query" not in st.session_state:
    st.session_state.news_loaded_query = ""

if "network_raw_df" not in st.session_state:
    st.session_state.network_raw_df = empty_alert_df()
if "network_scored_df" not in st.session_state:
    st.session_state.network_scored_df = empty_alert_df()
if "network_final_df" not in st.session_state:
    st.session_state.network_final_df = empty_alert_df()
if "network_loaded_at" not in st.session_state:
    st.session_state.network_loaded_at = 0.0
if "network_fetch_signature" not in st.session_state:
    st.session_state.network_fetch_signature = None
if "network_score_threshold" not in st.session_state:
    st.session_state.network_score_threshold = None
if "network_fusion_signature" not in st.session_state:
    st.session_state.network_fusion_signature = None
if "network_warnings" not in st.session_state:
    st.session_state.network_warnings = []
if "force_network_refresh" not in st.session_state:
    st.session_state.force_network_refresh = False
if "force_news_refresh" not in st.session_state:
    st.session_state.force_news_refresh = False

if "watchlist_final_df" not in st.session_state:
    st.session_state.watchlist_final_df = empty_alert_df()
if "eth_watch_df" not in st.session_state:
    st.session_state.eth_watch_df = empty_alert_df()
if "btc_watch_df" not in st.session_state:
    st.session_state.btc_watch_df = empty_alert_df()

prefs = dict(st.session_state.monitoring_prefs)


# =========================================================
# PAGE LAYOUT / CONTROLS
# =========================================================
# All top-level views now use the full main canvas.
# Wallet Lookup is rendered inside the Watchlist page itself.
layout_view = str(st.session_state.nav_view or "home").lower()

run_watchlist_btn = False
eth_watch_input = DEFAULT_ETH_WATCH
btc_watch_input = DEFAULT_BTC_WATCH
watch_limit = min(max(WATCH_TX_LIMIT, 5), 30)

main_col = st.container()
control_col = None

# Always derive runtime values from the last saved preferences.
prefs = dict(st.session_state.monitoring_prefs)
auto_erc20 = bool(prefs["auto_erc20"])
news_query = str(prefs["news_query"])
whale_threshold = float(prefs["whale_threshold"])
eth_blocks = int(prefs["eth_blocks"])
btc_blocks = int(prefs["btc_blocks"])
btc_txs_per_block = int(prefs["btc_txs_per_block"])


# =========================================================
# IN-APP SESSION NAVIGATION
# =========================================================
NAV_OPTIONS = [
    "⌂  Home",
    "◉  Alerts",
    "♧  Transfers",
    "◫  Market",
    "☆  Watchlist",
    "▣  News",
    "≛  Settings",
]
NAV_TO_VIEW = {
    NAV_OPTIONS[0]: "home",
    NAV_OPTIONS[1]: "whales",
    NAV_OPTIONS[2]: "alerts",
    NAV_OPTIONS[3]: "market",
    NAV_OPTIONS[4]: "watchlist",
    NAV_OPTIONS[5]: "news",
    NAV_OPTIONS[6]: "controls",
}
VIEW_TO_NAV = {value: key for key, value in NAV_TO_VIEW.items()}


def set_nav_view(view_name: str):
    """Switch NOVARIS views without browser URL navigation."""
    view_name = str(view_name or "home").lower()

    if view_name not in {"home", "alerts", "whales", "market", "watchlist", "news", "controls"}:
        view_name = "home"

    st.session_state.nav_view = view_name
    nav_label = VIEW_TO_NAV.get(view_name, NAV_OPTIONS[0])

    # Keep whichever navigation widget is being used synchronized.
    st.session_state["novaris_session_navigation"] = nav_label
    st.session_state["novaris_session_navigation_fallback"] = nav_label


current_view = str(st.session_state.nav_view or "home").lower()
if current_view not in {"home", "alerts", "whales", "market", "watchlist", "news", "controls"}:
    current_view = "home"
    st.session_state.nav_view = "home"

with main_col:
    with st.container(key="brand_header"):
        with st.container(key="session_nav_shell"):
            nav_items = [
                ("home", "Home", ":material/home:"),
                ("whales", "Alerts", ":material/notifications:"),
                ("alerts", "Transfers", ":material/swap_horiz:"),
                ("market", "Market", ":material/show_chart:"),
                ("watchlist", "Watchlist", ":material/star_outline:"),
                ("news", "News", ":material/article:"),
            ]

            nav_cols = st.columns(6, gap="small")

            for nav_col, (view_name, label, icon_name) in zip(nav_cols, nav_items):
                with nav_col:
                    st.button(
                        label,
                        key=f"session_nav_{view_name}",
                        icon=icon_name,
                        type="primary"
                        if current_view == view_name
                        else "secondary",
                        use_container_width=True,
                        on_click=set_nav_view,
                        args=(view_name,),
                    )

        nav_view = str(st.session_state.nav_view or "home").lower()

        # Settings is intentionally kept outside the main navigation pill.
        # The gear icon sits beside the Live Feed session indicator.
        st.button(
            "Settings",
            key="header_settings_button",
            icon=":material/settings:",
            help="Open Settings",
            type="primary" if current_view == "controls" else "secondary",
            on_click=set_nav_view,
            args=("controls",),
        )

        st.markdown(
            "<div class='brand-live-status'>"
            "<span class='brand-live-dot'></span>"
            "<span>Live Feed</span><span style='color:#777169;'>session</span>"
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            "<div class='brand-copy'>"
            "<div class='brand-title'>"
            "<span class='brand-word'>NOVARIS</span>"
            "<span class='brand-spark'>✦</span>"
            "</div>"
            "<div class='brand-sub'>An intelligence console for live Bitcoin and Ethereum monitoring and signal detection.</div>"
            "<div class='brand-mini'>Network data is reused between views; Alerts opens the current Home snapshot without refetching blockchain data.</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    # -----------------------------------------------------
    # WATCHLIST — WALLET LOOKUP IN MAIN CONTENT AREA
    # -----------------------------------------------------
    if nav_view == "watchlist":
        # Same page-header treatment as Crypto Market Prices.
        st.markdown(
            """
            <div class="market-page-hero wallet-page-hero">
                <div class="market-page-title">Wallet Lookup</div>
                <div class="market-page-subtitle">
                    Inspect recent on-chain activity for any Bitcoin or Ethereum wallet.
                    Enter one or both public addresses and NOVARIS will surface recent
                    transfers, direction, USD value and risk signals.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container(border=True, key="watchlist_controls_card"):
            st.markdown(
                """
                <div class="wallet-intro-strip">
                    <div class="wallet-intro-icon">
                        <svg viewBox="0 0 48 48" aria-hidden="true">
                            <circle cx="20" cy="20" r="10"></circle>
                            <path d="M27.5 27.5 38 38"></path>
                            <circle cx="20" cy="20" r="3"></circle>
                        </svg>
                    </div>
                    <div class="wallet-intro-copy">
                        <div class="wallet-intro-title">Search blockchain activity</div>
                        <div class="wallet-intro-note">
                            Only public wallet addresses are queried. No wallet connection,
                            seed phrase or private key is required.
                        </div>
                    </div>
                    <div class="wallet-intro-badge">BTC + ETH</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            with st.form("wallet_lookup_form", clear_on_submit=False):
                wallet_left, wallet_right = st.columns(2, gap="large")

                with wallet_left:
                    with st.container(key="wallet_eth_panel"):
                        st.markdown(
                            """
                            <div class="wallet-network-heading">
                                <div class="wallet-network-icon wallet-network-icon-eth">
                                    <svg viewBox="0 0 40 52" aria-hidden="true">
                                        <polygon points="20,2 5,26 20,18 35,26"></polygon>
                                        <polygon points="20,50 5,29 20,37 35,29"></polygon>
                                    </svg>
                                </div>
                                <div>
                                    <div class="wallet-network-title">Ethereum Wallet</div>
                                    <div class="wallet-network-hint">Public address beginning with 0x</div>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        eth_watch_input = st.text_area(
                            "Ethereum Wallet Address",
                            value=DEFAULT_ETH_WATCH,
                            height=112,
                            placeholder="0x...",
                            label_visibility="collapsed",
                        )

                with wallet_right:
                    with st.container(key="wallet_btc_panel"):
                        st.markdown(
                            """
                            <div class="wallet-network-heading">
                                <div class="wallet-network-icon wallet-network-icon-btc">₿</div>
                                <div>
                                    <div class="wallet-network-title">Bitcoin Wallet</div>
                                    <div class="wallet-network-hint">Public address beginning with bc1, 1 or 3</div>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        btc_watch_input = st.text_area(
                            "Bitcoin Wallet Address",
                            value=DEFAULT_BTC_WATCH,
                            height=112,
                            placeholder="bc1... / 1... / 3...",
                            label_visibility="collapsed",
                        )

                st.markdown(
                    """
                    <div class="wallet-search-divider"></div>
                    <div class="wallet-search-heading">
                        <div>
                            <div class="wallet-search-title">Search Depth</div>
                            <div class="wallet-search-note">
                                Choose how many recent transactions to retrieve for each address.
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                slider_col, action_col = st.columns([3.25, 1.0], gap="large")

                with slider_col:
                    watch_limit = st.slider(
                        "Recent Transactions Per Address",
                        5,
                        30,
                        min(max(WATCH_TX_LIMIT, 5), 30),
                        5,
                    )

                with action_col:
                    st.markdown(
                        "<div class='wallet-action-spacer'></div>",
                        unsafe_allow_html=True,
                    )
                    run_watchlist_btn = st.form_submit_button(
                        "Search Wallet Activity",
                        use_container_width=True,
                    )


# =========================================================
# SELECTIVE DATA LOADING / SESSION SNAPSHOTS
# =========================================================
# Transaction links still use ?tx=... because they represent a drill-down view,
# but top-level navigation no longer uses query parameters.
selected_tx_hash = st.query_params.get("tx", "")
if isinstance(selected_tx_hash, list):
    selected_tx_hash = selected_tx_hash[0] if selected_tx_hash else ""
selected_tx_hash = str(selected_tx_hash or "").strip()

now_ts = time.time()
# Home and Transfers are the views allowed to refresh the live network snapshot.
#
# Alerts deliberately reuses the exact same already-loaded transaction snapshot
# that produced the WHALE ALERTS KPI on Home. This makes Home -> Alerts a display
# change only, rather than another Ethereum/Bitcoin API refresh.
#
# A direct first visit to Alerts / a transaction deep-link can still perform one
# initial load if there is no network snapshot in this Streamlit session yet.
network_snapshot_missing = (
    st.session_state.network_loaded_at <= 0
    or st.session_state.network_final_df is None
)

need_network = (
    nav_view in {"home", "alerts"}
    or (
        nav_view == "whales"
        and network_snapshot_missing
    )
    or (
        bool(selected_tx_hash)
        and network_snapshot_missing
    )
)

need_news = nav_view in {"home", "news"}
need_prices = need_network or run_watchlist_btn or nav_view == "market"
need_fear_greed = need_network or run_watchlist_btn

prices_updated = False
fear_greed_updated = False
news_updated = False

# Prices are fetched for blockchain valuation and the dedicated Market page.
if need_prices:
    prices_stale = (
        st.session_state.prices_loaded_at <= 0
        or (now_ts - st.session_state.prices_loaded_at) >= MARKET_REFRESH_SECONDS
    )
    if prices_stale:
        st.session_state.prices_data = fetch_price_map()
        st.session_state.prices_loaded_at = now_ts
        prices_updated = True

# Fear & Greed is refreshed only where risk/sentiment calculations need it.
if need_fear_greed:
    fg_stale = (
        st.session_state.fear_greed_loaded_at <= 0
        or (now_ts - st.session_state.fear_greed_loaded_at) >= MARKET_REFRESH_SECONDS
    )
    if fg_stale:
        st.session_state.fear_greed_data = fetch_fear_greed()
        st.session_state.fear_greed_loaded_at = now_ts
        fear_greed_updated = True

# News is loaded only on Home (for the preview) and News pages.
# Other views simply reuse the most recent news snapshot if one exists.
if need_news:
    news_stale = (
        st.session_state.news_loaded_at <= 0
        or (now_ts - st.session_state.news_loaded_at) >= NEWS_REFRESH_SECONDS
        or st.session_state.news_loaded_query != news_query
        or st.session_state.force_news_refresh
    )
    if news_stale:
        with st.spinner("Refreshing market news..."):
            st.session_state.news_data = fetch_news_articles(news_query, GNEWS_API_KEY)
        st.session_state.news_loaded_at = now_ts
        st.session_state.news_loaded_query = news_query
        st.session_state.force_news_refresh = False
        news_updated = True

# Dedicated market overview is fetched only on the Market page.
# It is independent of the blockchain scan, so opening Market never causes
# Ethereum/Bitcoin transaction APIs to refresh.
if nav_view == "market":
    market_overview_stale = (
        st.session_state.market_overview_loaded_at <= 0
        or (
            now_ts - st.session_state.market_overview_loaded_at
        ) >= MARKET_REFRESH_SECONDS
    )

    if market_overview_stale:
        st.session_state.market_overview_data = fetch_market_overview()
        st.session_state.market_overview_loaded_at = now_ts

prices = st.session_state.prices_data
fg = st.session_state.fear_greed_data
news_df = st.session_state.news_data
market_overview_df = st.session_state.market_overview_data

# ---------------------------------------------------------
# MARKET PAGE
# ---------------------------------------------------------
# At this point the CoinGecko price variables exist.
# Render Market here and stop immediately so:
#   1. no NameError can occur,
#   2. Market never appears underneath Home,
#   3. opening Market never continues into blockchain ingestion.
if nav_view == "market":
    render_market_page(prices, market_overview_df)
    st.stop()

# Network fetch signature contains only settings that actually change which
# blockchain transactions are requested. Whale Threshold is deliberately not
# included because threshold-only changes can rescore stored raw transactions.
network_fetch_signature = (
    auto_erc20,
    eth_blocks,
    btc_blocks,
    btc_txs_per_block,
)

network_refreshed = False
network_rescored = False

if need_network:
    network_stale = (
        st.session_state.network_loaded_at <= 0
        or (now_ts - st.session_state.network_loaded_at) >= NETWORK_REFRESH_SECONDS
        or st.session_state.network_fetch_signature != network_fetch_signature
        or st.session_state.force_network_refresh
    )

    if network_stale:
        with st.spinner("Refreshing blockchain transactions..."):
            eth_native_df, eth_native_warn = fetch_eth_network_native(
                eth_blocks,
                prices.get("ETH"),
            )
            eth_erc20_df, eth_erc20_warn = fetch_eth_network_erc20(
                eth_blocks,
                prices,
                enabled=auto_erc20,
            )
            btc_network_df, btc_warn = fetch_btc_network_whales(
                btc_blocks,
                prices.get("BTC"),
                btc_txs_per_block,
            )

            network_raw = pd.concat(
                [eth_native_df, eth_erc20_df, btc_network_df],
                ignore_index=True,
            ) if any(
                not df.empty
                for df in [eth_native_df, eth_erc20_df, btc_network_df]
            ) else empty_alert_df()

        st.session_state.network_raw_df = network_raw
        st.session_state.network_loaded_at = now_ts
        st.session_state.network_fetch_signature = network_fetch_signature
        st.session_state.network_warnings = (
            eth_native_warn + eth_erc20_warn + btc_warn
        )
        st.session_state.force_network_refresh = False
        network_refreshed = True

    # Score stored raw transactions only if the raw snapshot or threshold changed.
    if (
        network_refreshed
        or st.session_state.network_score_threshold != whale_threshold
        or st.session_state.network_scored_df is None
    ):
        st.session_state.network_scored_df = score_alerts(
            st.session_state.network_raw_df,
            whale_threshold,
        )
        st.session_state.network_score_threshold = whale_threshold
        network_rescored = True

    # Re-fuse sentiment when the underlying transactions/scores or market/news
    # context changed. This does NOT query the blockchains again.
    fusion_signature = (
        st.session_state.network_loaded_at,
        st.session_state.network_score_threshold,
        st.session_state.news_loaded_at,
        st.session_state.fear_greed_loaded_at,
    )

    if (
        network_refreshed
        or network_rescored
        or news_updated
        or fear_greed_updated
        or st.session_state.network_fusion_signature != fusion_signature
    ):
        network_final = fuse_sentiment(
            st.session_state.network_scored_df,
            news_df,
            fg,
        )
        network_final = (
            network_final.sort_values(
                ["timestamp", "amount_usd"],
                ascending=[False, False],
            ).reset_index(drop=True)
            if not network_final.empty
            else empty_alert_df()
        )
        st.session_state.network_final_df = network_final
        st.session_state.network_fusion_signature = fusion_signature

network_final = st.session_state.network_final_df
network_warnings = list(st.session_state.network_warnings)


# =========================================================
# WATCHLIST — RUN ONLY ON EXPLICIT SUBMIT
# =========================================================
if run_watchlist_btn:
    eth_watch = parse_lines(eth_watch_input)
    btc_watch = parse_lines(btc_watch_input)

    with st.spinner("Running watchlist search..."):
        eth_watch_df = (
            fetch_eth_watchlist(eth_watch, watch_limit, prices)
            if eth_watch
            else empty_alert_df()
        )
        btc_watch_df = (
            fetch_btc_watchlist(btc_watch, watch_limit, prices)
            if btc_watch
            else empty_alert_df()
        )

        watch_df = pd.concat(
            [eth_watch_df, btc_watch_df],
            ignore_index=True,
        ) if any(
            not df.empty for df in [eth_watch_df, btc_watch_df]
        ) else empty_alert_df()

        watch_scored = score_alerts(watch_df, whale_threshold)
        watch_final = fuse_sentiment(watch_scored, news_df, fg)
        watch_final = (
            watch_final.sort_values(
                ["timestamp", "amount_usd"],
                ascending=[False, False],
            ).reset_index(drop=True)
            if not watch_final.empty
            else empty_alert_df()
        )

        st.session_state.eth_watch_df = eth_watch_df
        st.session_state.btc_watch_df = btc_watch_df
        st.session_state.watchlist_final_df = watch_final

watchlist_final_df = st.session_state.watchlist_final_df
eth_watch_df = st.session_state.eth_watch_df
btc_watch_df = st.session_state.btc_watch_df

all_alerts_df = pd.concat(
    [network_final, watchlist_final_df],
    ignore_index=True,
) if any(
    not df.empty for df in [network_final, watchlist_final_df]
) else empty_alert_df()

all_alerts_df = (
    all_alerts_df.sort_values(
        ["timestamp", "amount_usd"],
        ascending=[False, False],
    ).reset_index(drop=True)
    if not all_alerts_df.empty
    else empty_alert_df()
)

big_alerts_df = (
    all_alerts_df[
        all_alerts_df["amount_usd"].fillna(0) >= whale_threshold
    ].copy()
    if not all_alerts_df.empty
    else empty_alert_df()
)

# Only surface network warnings on views that actually use the network feed.
if need_network:
    for w in network_warnings:
        st.warning(w)


# =========================================================
# MAIN DASHBOARD / TRANSACTION DETAIL ROUTING
# =========================================================
with main_col:
    if selected_tx_hash:
        render_transaction_detail_page(selected_tx_hash, all_alerts_df)
        st.stop()

    if nav_view == "alerts":
        render_full_alerts_page(
            all_alerts_df,
            whale_threshold,
            page_title="Latest Transfers",
            max_items=30,
        )
        st.stop()

    if nav_view == "whales":
        # No blockchain/API call is triggered merely by opening this page.
        # `big_alerts_df` is derived from the same stored transaction snapshot
        # used for the WHALE ALERTS count on Home, and all matching alerts are shown.
        render_full_alerts_page(
            big_alerts_df,
            whale_threshold,
            page_title="Whale Alerts",
            max_items=None,
        )
        st.stop()

    if nav_view == "watchlist":
        if watchlist_final_df.empty:
            st.markdown(
                """
                <div class="watchlist-empty-note wallet-empty-state">
                    <div class="wallet-empty-dot"></div>
                    <div>
                        <div class="wallet-empty-title">Ready to inspect wallet activity</div>
                        <div class="wallet-empty-copy">
                            Enter a Bitcoin or Ethereum address above and run a search.
                            Matching transfers and NOVARIS risk signals will appear here.
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            with st.container(border=True, key="topnav_watchlist_results_card"):
                st.markdown(
                    "<div class='overview-card-heading'>WALLET ACTIVITY RESULTS</div>",
                    unsafe_allow_html=True,
                )

                st.dataframe(
                    watchlist_final_df[[
                        "timestamp",
                        "chain",
                        "asset_symbol",
                        "watch_address",
                        "direction",
                        "amount_native",
                        "amount_usd",
                        "final_risk",
                        "tx_hash",
                    ]],
                    use_container_width=True,
                )
        st.stop()

    if nav_view == "news":
        render_news_feed(news_df)
        st.stop()

    if nav_view == "controls":
        render_monitoring_controls_page(
            dict(st.session_state.monitoring_prefs)
        )
        st.stop()

    # Every non-Home route above must stop before this point.
    # This guard prevents any future page from accidentally being appended
    # below the Home footer if a new route is introduced or moved.
    if nav_view != "home":
        st.stop()

    fear_color, fear_bg, fear_border = fear_greed_style(fg["classification"])

    # -----------------------------------------------------
    # TOP KPI ROW — four compact cards
    # -----------------------------------------------------
    p1, p2, p3 = st.columns(3, gap="medium")

    with p1:
        with st.container(key="whale_alerts_kpi_clickable"):
            render_stat_card(
                label="WHALE ALERTS",
                value=f"{len(big_alerts_df)}",
                icon="<svg class='whale-alert-svg' viewBox='0 0 64 64' aria-hidden='true'><defs><linearGradient id='waGrad' x1='0%' y1='0%' x2='100%' y2='100%'><stop offset='0%' stop-color='#FFF0B8'/><stop offset='55%' stop-color='#FFD76A'/><stop offset='100%' stop-color='#FFB21E'/></linearGradient></defs><path d='M32 8c-8.2 0-14.5 6.7-14.5 15.2v5.2c0 5.1-1.7 9.7-4.8 13.2-1.3 1.5-.3 3.9 1.7 3.9h35.2c2 0 3-2.4 1.7-3.9-3.1-3.5-4.8-8.1-4.8-13.2v-5.2C46.5 14.7 40.2 8 32 8Z' fill='none' stroke='url(#waGrad)' stroke-width='4.8' stroke-linecap='round' stroke-linejoin='round'/><path d='M25.5 50.5c1.4 3.3 3.5 5.2 6.5 5.2s5.1-1.9 6.5-5.2' fill='none' stroke='url(#waGrad)' stroke-width='4.8' stroke-linecap='round'/></svg>",
                accent="#FFB21E",
                glow=True,
                compact=True,
                subtext=None,
            )

            st.button(
                "WHALE ALERTS",
                key="open_whale_alerts_page",
                on_click=set_nav_view,
                args=("whales",),
            )

    with p2:
        with st.container(key="eth_market_kpi_clickable"):
            render_stat_card(
                label="ETHEREUM SPOT PRICE (USD)",
                value=f"${prices['ETH']:,.2f}" if prices.get("ETH") else "N/A",
                icon="<svg class='eth-price-svg' viewBox='0 0 64 64' aria-hidden='true'><defs><linearGradient id='ethTop' x1='0%' y1='0%' x2='100%' y2='100%'><stop offset='0%' stop-color='#EAF0FF'/><stop offset='45%' stop-color='#C2D1FF'/><stop offset='100%' stop-color='#8FAAFF'/></linearGradient><linearGradient id='ethBottom' x1='0%' y1='0%' x2='100%' y2='100%'><stop offset='0%' stop-color='#B2C4FF'/><stop offset='50%' stop-color='#92AAFF'/><stop offset='100%' stop-color='#718EFF'/></linearGradient><linearGradient id='ethCore' x1='0%' y1='0%' x2='100%' y2='100%'><stop offset='0%' stop-color='#D4DEFF'/><stop offset='100%' stop-color='#9EB4FF'/></linearGradient></defs><polygon points='32,4 16,31 32,23 48,31' fill='url(#ethTop)'/><polygon points='32,23 16,31 32,40 48,31' fill='url(#ethCore)' opacity='0.95'/><polygon points='32,60 16,34 32,43 48,34' fill='url(#ethBottom)'/></svg>",
                accent="#FFB21E",
                compact=True,
                subtext=None,
            )

            st.button(
                "Open Ethereum Market",
                key="open_eth_market_page",
                on_click=set_nav_view,
                args=("market",),
            )

    with p3:
        with st.container(key="btc_market_kpi_clickable"):
            render_stat_card(
                label="BITCOIN SPOT PRICE (USD)",
                value=f"${prices['BTC']:,.2f}" if prices.get("BTC") else "N/A",
                icon="<span class='btc-price-icon'>₿</span>",
                accent="#FFB21E",
                compact=True,
                subtext=None,
            )

            st.button(
                "Open Bitcoin Market",
                key="open_btc_market_page",
                on_click=set_nav_view,
                args=("market",),
            )

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

    # -----------------------------------------------------
    # FEATURED MARKET SENTIMENT PANEL
    # -----------------------------------------------------
    render_fear_greed_index_card(fg)

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    # -----------------------------------------------------
    # LOWER HOME — alerts left, timeline/news right
    # -----------------------------------------------------
    left_col, right_col = st.columns([0.92, 1.48], gap="medium")

    with left_col:
        with st.container(border=True, key="home_alerts_panel"):
            alerts_heading_col, alerts_action_col = st.columns([5.3, 1.0], gap="small")

            with alerts_heading_col:
                st.markdown(
                    '<div class="home-panel-title home-alerts-title">'
                    '<span class="home-alerts-bell">'
                    '<svg viewBox="0 0 24 24" aria-hidden="true">'
                    '<path d="M4 8h12"></path>'
                    '<path d="m13 5 3 3-3 3"></path>'
                    '<path d="M20 16H8"></path>'
                    '<path d="m11 13-3 3 3 3"></path>'
                    '</svg>'
                    '</span>'
                    '<span>LATEST TRANSFERS</span>'
                    '</div>',
                    unsafe_allow_html=True,
                )

            with alerts_action_col:
                st.button(
                    "VIEW ALL",
                    key="home_alerts_view_all",
                    use_container_width=True,
                    on_click=set_nav_view,
                    args=("alerts",),
                )

            if all_alerts_df.empty:
                st.info("No transactions found in the current scan window.")
            else:
                for _, row in all_alerts_df.head(4).iterrows():
                    meta = get_asset_meta(row["asset_symbol"], row["chain"])
                    amount_txt = f"{format_amount(row['amount_native'])} {row['asset_symbol']}"
                    usd_txt = (
                        f"${row['amount_usd']:,.0f}"
                        if pd.notna(row["amount_usd"])
                        else "USD unavailable"
                    )

                    if row["source_type"] == "watchlist":
                        line2 = (
                            f"{row['direction']} involving watchlist wallet "
                            f"{short_addr(row['watch_address'])}"
                        )
                        source_text = "Watchlist"
                        source_badge = "badge-watch"
                    else:
                        line2 = (
                            f"transferred from {short_addr(row['from'])} "
                            f"to {short_addr(row['to'])}"
                        )
                        source_text = "Network"
                        source_badge = "badge-net"

                    chain_badge = (
                        "badge-eth"
                        if row["chain"] == CHAIN_ETH
                        else "badge-btc"
                    )

                    if row["final_risk"] == "High":
                        risk_badge = "badge-high"
                    elif row["final_risk"] == "Medium":
                        risk_badge = "badge-medium"
                    else:
                        risk_badge = "badge-low"

                    whale_class = (
                        "whale-card"
                        if pd.notna(row["amount_usd"])
                        and row["amount_usd"] >= whale_threshold
                        else ""
                    )

                    tx_hash_value = str(row.get("tx_hash") or "").strip()
                    alert_href = (
                        f"?tx={tx_hash_value}"
                        if tx_hash_value
                        else "#"
                    )

                    st.markdown(
                        (
                            f'<a class="alert-card-link" href="{alert_href}" target="_self">'
                            f'<div class="alert-card {whale_class}">'
                            f'<div class="alert-row">'
                            f'<div class="alert-left">'
                            f'<div class="asset-circle">{get_alert_asset_icon(row["asset_symbol"], row["chain"])}</div>'
                            f'<div class="alert-content">'
                            f'<div class="alert-title"><span class="alert-amount">{amount_txt}</span><span class="alert-usd">{usd_txt}</span></div>'
                            f'<div class="alert-sub">{line2}</div>'
                            f'<div class="alert-badges" style="margin-top:7px;margin-bottom:0;">'
                            f'<span class="badge {chain_badge}">{row["chain"]}</span>'
                            f'<span class="badge {risk_badge}">{row["final_risk"]}</span>'
                            f'<span class="badge {source_badge}">{source_text}</span>'
                            f'</div>'
                            f'</div>'
                            f'</div>'
                            f'<div class="alert-time">{human_age(row["timestamp"])}</div>'
                            f'</div>'
                            f'</div>'
                            f'</a>'
                        ),
                        unsafe_allow_html=True,
                    )

    with right_col:
        # Transaction Timeline
        with st.container(border=True, key="home_timeline_card"):
            st.markdown(
                '<div class="home-panel-title home-compact-title">'
                'TRANSACTION TIMELINE (USD VALUE)'
                '</div>',
                unsafe_allow_html=True,
            )

            if all_alerts_df.empty:
                st.info("No transaction data to display.")
            else:
                timeline_df = all_alerts_df.copy()

                # Normalize timestamps before applying the selected time window.
                timeline_df["timestamp"] = pd.to_datetime(
                    timeline_df["timestamp"],
                    utc=True,
                    errors="coerce",
                )
                timeline_df = timeline_df.dropna(subset=["timestamp"])

                # Keep all currently available transaction history in the
                # Plotly figure. The timeframe controls below operate entirely
                # in the browser, so clicking them does not rerun Streamlit or
                # refetch any blockchain/API data.
                timeline_end = (
                    timeline_df["timestamp"].max()
                    if not timeline_df.empty
                    else pd.Timestamp.now(tz="UTC")
                )
                default_timeline_start = timeline_end - pd.Timedelta(hours=24)

                timeline_df["chain_source_type"] = (
                    timeline_df["chain"] + "_" + timeline_df["source_type"]
                )

                timeline_color_map = {
                    "Ethereum_network": "#F5A623",
                    "Bitcoin_network": "#E7E5E0",
                    "Ethereum_watchlist": "#FFB21E",
                    "Bitcoin_watchlist": "#BDB8AE",
                }

                fig1 = px.scatter(
                    timeline_df,
                    x="timestamp",
                    y="amount_usd",
                    color="chain_source_type",
                    color_discrete_map=timeline_color_map,
                    hover_data=["asset_symbol", "tx_hash", "final_risk"],
                )

                fig1.update_traces(
                    marker=dict(size=8, opacity=0.92, line=dict(width=0))
                )

                fig1.update_layout(
                    height=320,
                    template="plotly_dark",
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#DCD8D0", size=14),
                    hoverlabel=dict(
                        font=dict(size=13),
                    ),
                    xaxis=dict(
                        title="",
                        type="date",
                        range=[default_timeline_start, timeline_end],
                        tickfont=dict(color="#C9C3B9", size=14),
                        gridcolor="rgba(255,255,255,0.065)",
                        zeroline=False,
                        automargin=True,
                        nticks=9,
                        hoverformat="%b %d, %Y %H:%M:%S",
                        tickformatstops=[
                            dict(
                                dtickrange=[None, 60 * 60 * 1000],
                                value="%H:%M",
                            ),
                            dict(
                                dtickrange=[
                                    60 * 60 * 1000,
                                    24 * 60 * 60 * 1000,
                                ],
                                value="%H:%M<br>%b %d",
                            ),
                            dict(
                                dtickrange=[
                                    24 * 60 * 60 * 1000,
                                    None,
                                ],
                                value="%b %d<br>%Y",
                            ),
                        ],
                        rangeselector=dict(
                            buttons=[
                                dict(
                                    count=1,
                                    label="1H",
                                    step="hour",
                                    stepmode="backward",
                                ),
                                dict(
                                    count=6,
                                    label="6H",
                                    step="hour",
                                    stepmode="backward",
                                ),
                                dict(
                                    count=24,
                                    label="24H",
                                    step="hour",
                                    stepmode="backward",
                                ),
                                dict(
                                    count=7,
                                    label="7D",
                                    step="day",
                                    stepmode="backward",
                                ),
                            ],
                            x=1.0,
                            y=1.18,
                            xanchor="right",
                            yanchor="top",
                            bgcolor="rgba(12,12,12,0.96)",
                            activecolor="rgba(96,62,12,0.98)",
                            bordercolor="rgba(255,255,255,0.14)",
                            borderwidth=1,
                            font=dict(
                                color="#F4E8CB",
                                size=12,
                                family='Inter, "Segoe UI", Arial, sans-serif',
                            ),
                        ),
                    ),
                    yaxis=dict(
                        title="USD VALUE",
                        title_font=dict(color="#C9C3B9", size=13),
                        tickfont=dict(color="#C9C3B9", size=14),
                        gridcolor="rgba(255,255,255,0.065)",
                        zeroline=False,
                        automargin=True,
                    ),
                    legend=dict(
                        title="",
                        orientation="v",
                        x=1.0,
                        y=0.98,
                        xanchor="right",
                        yanchor="top",
                        font=dict(color="#D2CCC1", size=12),
                        bgcolor="rgba(0,0,0,0)",
                    ),
                    margin=dict(l=58, r=12, t=42, b=42),
                )

                st.plotly_chart(
                    fig1,
                    use_container_width=True,
                    config={"displayModeBar": False},
                    key="home_transaction_timeline",
                )

        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
        render_home_news_preview(news_df)

    # -----------------------------------------------------
    # FOOTER
    # -----------------------------------------------------
    st.markdown(
        '<div class="novaris-footer">'
        '<div>✦ &nbsp; © 2026 NOVARIS. All rights reserved.</div>'
        '<div class="novaris-footer-links">'
        '<span>Privacy Policy</span>'
        '<span>Terms of Service</span>'
        '<span>Contact</span>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )
