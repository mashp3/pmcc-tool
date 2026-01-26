import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# --- フォント設定 ---
plt.rcParams['font.family'] = 'IPAGothic'

# ページ設定
st.set_page_config(page_title="PMCC Analyzer", layout="wide")

# ==========================================
# 0. キャッシュ付きデータ取得関数
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
# 1. デザイン修正 (スマホ対応)
# ==========================================
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        .fixed-header {
            position: fixed;
            top: 0;
            left: 60px; 
            width: calc(100% - 60px);
            height: 45px;
            background-color: #0E1117;
            border-bottom: 1px solid #333;
            z-index: 999999;
            display: flex;
            align-items: center;
            padding-left: 10px;
        }
        .header-text {
            color: #00e676;
            font-size: 16px;
            font-weight: bold;
            margin: 0;
            line-height: 45px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .block-container {
            padding-top: 60px !important;
        }
    </style>
    <div class="fixed-header">
        <span class="header-text">🇯🇵 PMCC 分析ツール (Ver 3.6)</span>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 2. ポートフォリオ機能
# ==========================================
if 'portfolios' not in st.session_state:
    st.session_state['portfolios'] = {f"Slot {i+1}": None for i in range(5)}
for key in ['ticker_data', 'strikes_data', 'load_trigger']:
    if key not in st.session_state: st.session_state[key] = None

with st.sidebar:
    st.header("📂 ポートフォリオ")
    selected_slot = st.selectbox("保存スロット", [f"Slot {i+1}" for i in range(5)])
    
    saved = st.session_state['portfolios'][selected_slot]
    if saved:
        st.caption(f"保存済: {saved['ticker']} ({saved['save_date']})")
    else:
        st.caption("データなし")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("保存", use_container_width=True):
            if st.session_state.get('ticker_data') and st.session_state.get('strikes_data'):
                st.session_state['portfolios'][selected_slot] = {
                    'ticker': st.session_state['ticker_data']['ticker'],
                    'long_exp': st.session_state['strikes_data']['long_exp'],
                    'short_exp': st.session_state['strikes_data']['short_exp'],
                    'save_date': datetime.now().strftime('%m/%d %H:%M')
                }
                st.success("保存!")
                st.rerun()
            else: st.error("データなし")
    with c2:
        if st.button("読込", use_container_width=True):
            if saved:
                st.session_state['load_trigger'] = saved
                st.rerun()
            else: st.warning("空です")

# ==========================================
# 3. メイン処理
# ==========================================
# 【重要】変数の定義（ここが消えていた可能性があります）
default_ticker = "NVDA"
if st.session_state['load_trigger']:
    default_ticker = st.session_state['load_trigger']['ticker']

col1, col2 = st.columns([3, 1])
with col1:
    ticker_input = st.text_input("銘柄", value=default_ticker, label_visibility="collapsed", placeholder="銘柄コード").upper()
with col2:
    fetch_pressed = st.button("データ取得", type="primary", use_container_width=True)

if fetch_pressed or st.session_state['load_trigger']:
    with st.spinner("データ取得中..."):
        price, exps, err = fetch_ticker_info(ticker_input)
        if err:
            st.error(f"Error: {err}")
            st.session_state['load_trigger'] = None
        else:
            st.session_state['ticker_data'] = {'price': price, 'exps': exps, 'ticker': ticker_input}
            st.session_state['strikes_data'] = None
            if fetch_pressed: st.session_state['load_trigger'] = None

# --- 満期日選択 ---
if st.session_state['ticker_data']:
    data = st.session_state['ticker_data']
    loaded = st.session_state.get('load_trigger')
    
    st.markdown(f"**現在株価: ${data['price']:.2f}**")
    
    c1, c2 = st.columns(2)
    l_idx = len(data['exps']) - 1
    s_idx = 1 if len(data['exps']) > 1 else 0

    if loaded:
        if loaded['long_exp'] in data['exps']: l_idx = data['exps'].index(loaded['long_exp'])
        if loaded['short_exp'] in data['exps']: s_idx = data['exps'].index(loaded['short_exp'])

    with c1: long_exp = st.selectbox("Long満期", data['exps'], index=l_idx)
    with c2: short_exp = st.selectbox("Short満期", data['exps'], index=s_idx)

    auto_load = False
    if loaded:
        auto_load = True
        st.session_state['load_trigger'] = None

    if st.button("ストライク読込", use_container_width=True) or auto_load:
        with st.spinner("チェーン取得中..."):
            l_chain, err1 = fetch_option_chain_data(data['ticker'], long_exp)
            s_chain, err2 = fetch_option_chain_data(data['ticker'], short_exp)
            
            if err1 or err2:
                st.error("取得エラー")
            else:
                strikes_l = sorted(l
