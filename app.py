import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from urllib.parse import quote

# --- フォント設定 ---
plt.rcParams['font.family'] = 'IPAGothic'

# ページ設定
st.set_page_config(page_title="PMCC Analyzer", layout="wide")

# ==========================================
# 0. データ取得関数
# ==========================================
@st.cache_data(ttl=600)
def fetch_ticker_info(ticker):
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period='1d')
        if hist.empty: return None, None, "データなし"
        price = hist['Close'].iloc[-1]
        exps = tk.options
        if not exps: return None, None, "オプションなし"
        return price, exps, None
    except Exception as e: return None, None, str(e)

@st.cache_data(ttl=600)
def fetch_option_chain_data(ticker, date):
    try:
        tk = yf.Ticker(ticker)
        chain = tk.option_chain(date).calls
        return chain, None
    except Exception as e: return None, str(e)

# ==========================================
# 1. 共通関数 (カレンダーURL生成)
# ==========================================
def create_gcal_url(title, date_obj, description=""):
    """Googleカレンダー登録用のURLを生成する"""
    if not date_obj: return "#"
    
    # 日付フォーマット YYYYMMDD (終日は翌日を指定する必要があるため+1日)
    start_str = date_obj.strftime('%Y%m%d')
    end_date = date_obj + timedelta(days=1)
    end_str = end_date.strftime('%Y%m%d')
    
    base_url = "https://www.google.com/calendar/render?action=TEMPLATE"
    params = f"&text={quote(title)}&dates={start_str}/{end_str}&details={quote(description)}"
    return base_url + params

# ==========================================
# 2. デザイン修正
# ==========================================
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .fixed-header {
            position: fixed; top: 0; left: 60px; width: calc(100% - 60px); height: 45px;
            background-color: #0E1117; border-bottom: 1px solid #333; z-index: 999999;
            display: flex; align-items: center; padding-left: 10px;
        }
        .header-text {
            color: #00e676; font-size: 16px; font-weight: bold; margin: 0;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .block-container { padding-top: 60px !important; }
        .stTable { font-size: 14px; }
        /* リンクボタンのスタイル調整 */
        .gcal-btn {
            text-decoration: none; display: inline-block; padding: 5px 10px;
            background-color: #333; color: white !important; border-radius: 4px;
            border: 1px solid #555; font-size: 0.8rem; margin-right: 5px;
        }
        .gcal-btn:hover { background-color: #444; border-color: #00e676; }
    </style>
    <div class="fixed-header">
        <span class="header-text">🇯🇵 PMCC 分析ツール (Ver 7.1)</span>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 3. ポートフォリオ & 手動モード切替
# ==========================================
if 'portfolios' not in st.session_state:
    st.session_state['portfolios'] = {f"Slot {i+1}": None for i in range(5)}
for key in ['ticker_data', 'strikes_data', 'load_trigger']:
    if key not in st.session_state: st.session_state[key] = None

if 'manual_mode' not in st.session_state:
    st.session_state['manual_mode'] = False

with st.sidebar:
    st.header("⚙️ 設定")
    st.session_state['manual_mode'] = st.toggle("手動入力モード (APIエラー時用)", value=st.session_state['manual_mode'])
    
    st.divider()
    st.header("📂 ポートフォリオ")
    selected_slot = st.selectbox("保存スロット", [f"Slot {i+1}" for i in range(5)])
    
    saved = st.session_state['portfolios'][selected_slot]
    if saved:
        st.caption(f"保存済: {saved.get('ticker', 'Manual')} ({saved.get('save_date','')})")
    
    c1, c2 = st.
