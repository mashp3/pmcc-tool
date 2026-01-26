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
# 0. キャッシュ付きデータ取得関数 (これが重要！)
# ==========================================
@st.cache_data(ttl=600) # 10分間データを保存して再利用する（Rate Limit対策）
def fetch_ticker_info(ticker):
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period='1d')
        if hist.empty:
            return None, None, "データなし"
        price = hist['Close'].iloc[-1]
        exps = tk.options
        if not exps:
            return None, None, "オプションなし"
        return price, exps, None
    except Exception as e:
        return None, None, str(e)

@st.cache_data(ttl=600) # オプションチェーンもキャッシュ
def fetch_option_chain_data(ticker, date):
    try:
        tk = yf.Ticker(ticker)
        chain = tk.option_chain(date).calls
        return chain, None
    except Exception as e:
        return None, str(e)

# ==========================================
# 1. デザイン修正 (CSS注入)
# ==========================================
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* 固定ヘッダー (最前面に表示) */
        .fixed-header {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 45px;
            background-color: #0E1117;
            border-bottom: 1px solid #333;
            z-index: 999999;
            display: flex;
            align-items: center;
            padding-left: 15px;
        }
        .header-text {
            color: #00e676;
            font-size: 16px;
            font-weight: bold;
            margin: 0;
            line-height: 45px;
        }
        .block-container {
            padding-top: 60px !important;
        }
    </style>
    <div class="fixed-header">
        <span class="header-text">🇯🇵 PMCC 分析ツール (Ver 3.3 Stable)</span>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 2. ポートフォリオ機能
# ==========================================
if 'portfolios' not in st.session_state:
    st.session_state['portfolios'] = {f"Slot {i+1}": None for i in range(5)}
# セッション変数の初期化
for key in ['ticker_data', 'strikes_data', 'load_trigger']:
    if key not in st.session_state:
        st.session_state[key] = None

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
            else:
                st.error("データなし")
    with c2:
        if st.button("読込", use_container_width=True):
            if saved:
                st.session_state['load_trigger'] = saved
                st.rerun()
            else:
                st.warning("空です")

# ==========================================
# 3. メイン処理
# ==========================================
default_ticker = "NVDA"
if st.session_state['load_trigger']:
    default_ticker = st.session_state['load_trigger']['ticker']

col1, col2 = st.columns([3, 1])
with col1:
    ticker_input = st.text_input("銘柄", value=default_ticker, label_visibility="collapsed", placeholder="銘柄コード").upper()
with col2:
    fetch_pressed = st.button("データ取得", type="primary", use_container_width=True)

# データ取得ロジック (キャッシュ利用)
if fetch_pressed or st.session_state['load_trigger']:
    with st.spinner("データ取得中..."):
        price, exps, err = fetch_ticker_info(ticker_input) # ここでキャッシュ関数を呼ぶ
        
        if err:
            st.error(f"Error: {err}")
            st.session_state['load_trigger'] = None
        else:
            st.session_state['ticker_data'] = {'price': price, 'exps': exps, 'ticker': ticker_input}
            st.session_state['strikes_data'] = None
            if fetch_pressed:
                st.session_state['load_trigger'] = None

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

    # 自動ロード判定
    auto_load = False
    if loaded:
        auto_load = True
        st.session_state['load_trigger'] = None

    if st.button("ストライク読込", use_container_width=True) or auto_load:
        with st.spinner("チェーン取得中..."):
            # キャッシュ関数を利用
            l_chain, err1 = fetch_option_chain_data(data['ticker'], long_exp)
            s_chain, err2 = fetch_option_chain_data(data['ticker'], short_exp)
            
            if err1 or err2:
                st.error("取得エラー")
            else:
                strikes_l = sorted(l_chain['strike'].unique())
                strikes_s = sorted(s_chain['strike'].unique())
                
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
    else: st.success(f"✅ 期間OK: 残{days}日")

    if st.button("分析実行", type="primary", use_container_width=True):
        try:
            # ここでもキャッシュデータを使いたいが、行データ取得のため再利用
            # ただしチェーン自体は軽量なのでここは直接呼ぶか、キャッシュから引く
            # 整合性のため、ここではキャッシュ関数を再コール（高速）
            l_chain, _ = fetch_option_chain_data(ticker, s_data['long_exp'])
            s_chain, _ = fetch_option_chain_data(ticker, s_data['short_exp'])
            
            l_row = l_chain[l_chain['strike'] == long_strike].iloc[0]
            s_row = s_chain[s_chain['strike'] == short_strike].iloc[0]
            
            # === 【最重要】価格取得の修正ロジック ($0対策) ===
            def get_valid_price(row, col_name):
                # まず指定されたカラム(ask/bid)を見る
                val = row.get(col_name, 0)
                # もし値がない、または0以下なら
                if pd.isna(val) or val <= 0:
                    # lastPrice (最終取引値) を使う
                    return row.get('lastPrice', 0)
                return val

            prem_l = get_valid_price(l_row, 'ask')
            prem_s = get_valid_price(s_row, 'bid')
            # ==============================================

            net_debit = prem_l - prem_s
            total_cost = net_debit * 100
            breakeven = long_strike + net_debit
            
            st.markdown("### 📊 分析レポート")
            m1, m2, m3 = st.columns(3)
            m1.metric("実質コスト", f"${net_debit:.2f}")
            m2.metric("初期投資", f"${total_cost:.0f}")
            m3.metric("分岐点", f"${breakeven:.2f}")
            
            st.caption(f"Long: ${long_strike} (${prem_l:.2f}) / Short: ${short_strike} (${prem_s:.2f})")

            # グラフ
            fig, ax = plt.subplots(figsize=(10, 4))
            prices = np.linspace(price * 0.7, price * 1.3, 100)
            val_l = np.maximum(0, prices - long_strike)
            val_s = np.maximum(0, prices - short_strike)
            profit = (val_l - val_s) - net_debit
            
            ax.plot(prices, profit*100, color='#00e676')
            ax.axhline(0, color='gray', linestyle='--')
            ax.axvline(price, color='blue', linestyle=':', label='Current')
            ax.axvline(breakeven, color='orange', linestyle=':', label='BE')
            ax.fill_between(prices, profit*100, 0, where=(profit>0), color='#00e676', alpha=0.3)
            ax.fill_between(prices, profit*100, 0, where=(profit<0), color='#ff5252', alpha=0.3)
            ax.grid(True, alpha=0.3)
            ax.legend()
            st.pyplot(fig)

            # テーブル
            with st.expander("詳細テーブル"):
                sim_prices = np.linspace(price * 0.7, price * 1.3, 11)
                data_list = []
                for p in sim_prices:
                    vl = max(0, p - long_strike)
                    vs = max(0, p - short_strike)
                    pf = (vl - vs) - net_debit
                    # ROI計算（ゼロ除算対策）
                    roi = (pf/net_debit)*100 if net_debit > 0 else 0
                    data_list.append({"Price": p, "P&L": pf * 100, "ROI": roi})
                df = pd.DataFrame(data_list)
                st.dataframe(df.style.format({"Price": "${:.2f}", "P&L": "${:.0f}", "ROI": "{:.1f}%"}))

        except Exception as e:
            st.error(f"分析エラー: {e}")
