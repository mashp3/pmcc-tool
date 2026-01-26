import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# --- フォント設定 (OSインストール済みフォントを使用) ---
plt.rcParams['font.family'] = 'IPAGothic'

# ページ設定
st.set_page_config(page_title="PMCC Analyzer", layout="wide")

# ==========================================
# 1. デザイン修正 (CSS注入) - 強制表示版
# ==========================================
st.markdown("""
    <style>
        /* デフォルトのヘッダー・フッターを隠す */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* 固定ヘッダーのスタイル (Z-indexを爆上げ) */
        .fixed-header {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 45px;
            background-color: #0E1117; /* ダーク背景 */
            border-bottom: 1px solid #333;
            z-index: 999999; /* 最前面に */
            display: flex;
            align-items: center;
            padding-left: 15px;
        }
        
        /* タイトル文字 */
        .header-text {
            color: #00e676; /* 緑色 */
            font-size: 16px;
            font-weight: bold;
            margin: 0;
            padding: 0;
            line-height: 45px;
        }

        /* 本文がヘッダーに隠れないように余白を確保 */
        .block-container {
            padding-top: 60px !important;
        }
    </style>
    
    <div class="fixed-header">
        <span class="header-text">🇯🇵 PMCC 分析ツール (Ver 3.2)</span>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 2. ポートフォリオ機能
# ==========================================
if 'portfolios' not in st.session_state:
    st.session_state['portfolios'] = {f"Slot {i+1}": None for i in range(5)}
if 'ticker_data' not in st.session_state:
    st.session_state['ticker_data'] = None
if 'strikes_data' not in st.session_state:
    st.session_state['strikes_data'] = None
if 'load_trigger' not in st.session_state:
    st.session_state['load_trigger'] = None

with st.sidebar:
    st.header("📂 ポートフォリオ")
    selected_slot = st.selectbox("保存スロット", [f"Slot {i+1}" for i in range(5)])
    
    saved_data = st.session_state['portfolios'][selected_slot]
    if saved_data:
        st.caption(f"保存済: {saved_data['ticker']} ({saved_data['save_date']})")
    else:
        st.caption("データなし")
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
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
            else:
                st.error("データなし")
    with col_p2:
        if st.button("読込", use_container_width=True):
            if saved_data:
                st.session_state['load_trigger'] = saved_data
                st.rerun()
            else:
                st.warning("空です")

# ==========================================
# 3. データ取得 & 分析ロジック
# ==========================================
default_ticker = "NVDA"
if st.session_state['load_trigger']:
    default_ticker = st.session_state['load_trigger']['ticker']

st.caption(" ") # ヘッダー下の微調整用スペーサー

col1, col2 = st.columns([3, 1])
with col1:
    ticker_input = st.text_input("銘柄コード", value=default_ticker, label_visibility="collapsed", placeholder="銘柄コード").upper()
with col2:
    fetch_pressed = st.button("データ取得", type="primary", use_container_width=True)

if fetch_pressed or st.session_state['load_trigger']:
    with st.spinner("データ取得中..."):
        try:
            tk = yf.Ticker(ticker_input)
            hist = tk.history(period='1d')
            if hist.empty:
                st.error("データが見つかりません")
                st.session_state['load_trigger'] = None
            else:
                price = hist['Close'].iloc[-1]
                exps = tk.options
                if not exps:
                    st.error("オプションなし")
                    st.session_state['load_trigger'] = None
                else:
                    st.session_state['ticker_data'] = {'price': price, 'exps': exps, 'ticker': ticker_input}
                    st.session_state['strikes_data'] = None
                    if fetch_pressed:
                        st.session_state['load_trigger'] = None
        except Exception as e:
            st.error(f"Error: {e}")
            st.session_state['load_trigger'] = None

# --- 満期日 ---
if st.session_state['ticker_data']:
    data = st.session_state['ticker_data']
    loaded_data = st.session_state.get('load_trigger')
    
    st.markdown(f"**現在株価: ${data['price']:.2f}**")
    
    c1, c2 = st.columns(2)
    long_def_idx = len(data['exps']) - 1
    short_def_idx = 1 if len(data['exps']) > 1 else 0

    if loaded_data:
        if loaded_data['long_exp'] in data['exps']: long_def_idx = data['exps'].index(loaded_data['long_exp'])
        if loaded_data['short_exp'] in data['exps']: short_def_idx = data['exps'].index(loaded_data['short_exp'])

    with c1:
        long_exp = st.selectbox("Long満期", data['exps'], index=long_def_idx)
    with c2:
        short_exp = st.selectbox("Short満期", data['exps'], index=short_def_idx)

    # ロード時は自動実行
    auto_load = False
    if loaded_data:
        auto_load = True
        st.session_state['load_trigger'] = None # フラグ消費

    if st.button("ストライク読込", use_container_width=True) or auto_load:
        with st.spinner("チェーン取得中..."):
            try:
                tk = yf.Ticker(data['ticker'])
                l_c = tk.option_chain(long_exp).calls
                s_c = tk.option_chain(short_exp).calls
                strikes_l = sorted(l_c['strike'].unique())
                strikes_s = sorted(s_c['strike'].unique())
                
                # 推奨値
                tgt_l = data['price'] * 0.60
                def_l = min(strikes_l, key=lambda x:abs(x-tgt_l))
                tgt_s = data['price'] * 1.15
                def_s = min(strikes_s, key=lambda x:abs(x-tgt_s))

                st.session_state['strikes_data'] = {
                    'long_exp': long_exp, 'short_exp': short_exp,
                    'strikes_l': strikes_l, 'strikes_s': strikes_s,
                    'def_l': def_l, 'def_s': def_s
                }
            except:
                st.error("取得エラー")

# --- 分析 ---
if st.session_state['strikes_data']:
    s_data = st.session_state['strikes_data']
    price = st.session_state['ticker_data']['price']
    ticker = st.session_state['ticker_data']['ticker']
    
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        try: d_idx = s_data['strikes_l'].index(s_data['def_l'])
        except: d_idx = 0
        long_strike = st.selectbox("Long Strike", s_data['strikes_l'], index=d_idx)
    with c2:
        try: d_idx = s_data['strikes_s'].index(s_data['def_s'])
        except: d_idx = 0
        short_strike = st.selectbox("Short Strike", s_data['strikes_s'], index=d_idx)

    # 簡易判定
    today = datetime.today()
    days = (datetime.strptime(s_data['long_exp'], '%Y-%m-%d') - today).days
    moneyness = long_strike / price
    
    if days < 180: st.warning(f"⚠️ 期間不足: 残{days}日")
    elif days < 365: st.info(f"ℹ️ 期間注意: 残{days}日")
    else: st.success(f"✅ 期間十分: 残{days}日")
    
    if moneyness > 0.85: st.warning(f"⚠️ 浅い: 現在値の{moneyness:.0%}")
    else: st.success(f"✅ 深さOK: 現在値の{moneyness:.0%}")

    if st.button("分析実行", type="primary", use_container_width=True):
        try:
            tk = yf.Ticker(ticker)
            l_opt = tk.option_chain(s_data['long_exp']).calls
            l_row = l_opt[l_opt['strike'] == long_strike].iloc[0]
            s_opt = tk.option_chain(s_data['short_exp']).calls
            s_row = s_opt[s_opt['strike'] == short_strike].iloc[0]
            
            # === 【重要】価格取得の修正ロジック ===
            # Ask/Bidが0の場合は、LastPrice(最終取引値)を使う
            def get_valid_price(row, col_name):
                val = row[col_name]
                if pd.isna(val) or val <= 0:
                    return row['lastPrice'] # 代替値
                return val

            prem_l = get_valid_price(l_row, 'ask')
            prem_s = get_valid_price(s_row, 'bid')
            # ===================================

            net_debit = prem_l - prem_s
            total_cost = net_debit * 100
            breakeven = long_strike + net_debit
            
            st.markdown("### 📊 分析レポート")
            m1, m2, m3 = st.columns(3)
            m1.metric("実質コスト", f"${net_debit:.2f}")
            m2.metric("初期投資", f"${total_cost:.0f}")
            m3.metric("分岐点", f"${breakeven:.2f}")
            
            st.caption(f"Long(${long_strike}): ${prem_l:.2f} / Short(${short_strike}): ${prem_s:.2f}")

            # グラフ
            fig, ax = plt.subplots(figsize=(10, 4))
            prices = np.linspace(price * 0.7, price * 1.3, 100)
            val_l = np.maximum(0, prices - long_strike)
            val_s = np.maximum(0, prices - short_strike)
            profit = (val_l - val_s) - net_debit
            
            ax.plot(prices, profit*100, color='#00e676', label='P&L')
            ax.axhline(0, color='gray', linestyle='--')
            ax.axvline(price, color='blue', linestyle=':', label='Current')
            ax.axvline(breakeven, color='orange', linestyle=':', label='BE')
            ax.fill_between(prices, profit*100, 0, where=(profit>0), color='#00e676', alpha=0.3)
            ax.fill_between(prices, profit*100, 0, where=(profit<0), color='#ff5252', alpha=0.3)
            ax.grid(True, alpha=0.3)
            st.pyplot(fig)

            # テーブル
            with st.expander("詳細テーブル"):
                sim_prices = np.linspace(price * 0.7, price * 1.3, 11)
                data_list = []
                for p in sim_prices:
                    vl = max(0, p - long_strike)
                    vs = max(0, p - short_strike)
                    pf = (vl - vs) - net_debit
                    data_list.append({"Price": p, "P&L": pf * 100, "ROI": (pf/net_debit)*100})
                df = pd.DataFrame(data_list)
                st.dataframe(df.style.format({"Price": "${:.2f}", "P&L": "${:.0f}", "ROI": "{:.1f}%"}))

        except Exception as e:
            st.error(f"Error: {e}")
