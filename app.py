import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from urllib.parse import quote
import gspread
from google.oauth2.service_account import Credentials
import json
import os
from scipy.stats import norm

# --- フォント設定 ---
plt.rcParams['font.family'] = 'IPAGothic'

# ページ設定
st.set_page_config(page_title="PMCC Analyzer", layout="wide")

# ==========================================
# 0. Google Sheets & 共通設定
# ==========================================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

def get_sheet_connection():
    try:
        json_str = os.environ.get("GCP_KEY_JSON")
        if not json_str: return None, "環境変数 GCP_KEY_JSON が未設定"
        key_dict = json.loads(json_str)
        creds = Credentials.from_service_account_info(key_dict, scopes=SCOPES)
        client = gspread.authorize(creds)
        sheet_url = os.environ.get("SHEET_URL")
        if not sheet_url: return None, "環境変数 SHEET_URL が未設定"
        sheet = client.open_by_url(sheet_url).sheet1
        return sheet, None
    except Exception as e: return None, str(e)

# ==========================================
# 1. 計算ロジック (BSモデル & コーチ判定)
# ==========================================
def calculate_greeks(S, K, T, r, sigma, option_type='call'):
    try:
        if T <= 0 or sigma <= 0: return None, None
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        if option_type == 'call':
            delta = norm.cdf(d1)
            theta_annual = -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * norm.cdf(d2)
            theta = theta_annual / 365.0
        else:
            delta = -norm.cdf(-d1); theta = 0
        return delta, theta
    except: return None, None

def generate_coach_comments(delta_l, days_l, delta_s, days_s):
    """グリークスに基づいたコメントを生成する"""
    comments = {"long": [], "short": [], "score": "B"}
    
    # --- Long判定 ---
    if delta_l >= 0.90:
        comments["long"].append(f"✅ 【Long】デルタ {delta_l:.2f}: 極めて深いDeep ITMです。現物株同様の動きが期待できます。")
    elif delta_l >= 0.80:
        comments["long"].append(f"✅ 【Long】デルタ {delta_l:.2f}: 十分なDeep ITMです。PMCCの土台として理想的です。")
    elif delta_l >= 0.70:
        comments["long"].append(f"⚠️ 【Long】デルタ {delta_l:.2f}: 少し浅いです。急落時のクッション性が弱まる可能性があります。")
    else:
        comments["long"].append(f"❌ 【Long】デルタ {delta_l:.2f}: 不適切です（OTM寄り）。カレンダー・スプレッドになっています。")

    if days_l > 365:
        comments["long"].append(f"✅ 【Long】残存 {int(days_l)}日: 1年以上あり、満期まで十分な余裕があります。")
    elif days_l > 180:
        comments["long"].append(f"✅ 【Long】残存 {int(days_l)}日: 半年以上あり、問題ありません。")
    else:
        comments["long"].append(f"⚠️ 【Long】残存 {int(days_l)}日: 期間が短めです。")

    # --- Short判定 ---
    if delta_s > 0.60:
        comments["short"].append(f"❌ 【Short】デルタ {delta_s:.2f}: ITMです。権利行使されるリスクが非常に高いです。")
    elif delta_s > 0.50:
        comments["short"].append(f"⚠️ 【Short】デルタ {delta_s:.2f}: 現在値に近すぎます（ATM）。上昇益が限定的です。")
    elif 0.20 <= delta_s <= 0.45:
        comments["short"].append(f"✅ 【Short】デルタ {delta_s:.2f}: 理想的なOTMです。確率と利益のバランスが良いです。")
    else:
        comments["short"].append(f"⚪ 【Short】デルタ {delta_s:.2f}: かなり遠くのOTMです。安全ですが受取額は少なめです。")

    # 総合評価
    if delta_l >= 0.80 and (0.20 <= delta_s <= 0.50): comments["score"] = "S"
    elif delta_l >= 0.75: comments["score"] = "A"
    else: comments["score"] = "C"

    return comments

# ==========================================
# 2. データ取得関数
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

def create_gcal_url(title, date_obj, description=""):
    if not date_obj: return "#"
    start_str = date_obj.strftime('%Y%m%d')
    end_date = date_obj + timedelta(days=1)
    end_str = end_date.strftime('%Y%m%d')
    base_url = "https://www.google.com/calendar/render?action=TEMPLATE"
    params = f"&text={quote(title)}&dates={start_str}/{end_str}&details={quote(description)}"
    return base_url + params

# ==========================================
# 3. デザイン & 状態管理
# ==========================================
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;} footer {visibility: hidden;}
        .fixed-header {
            position: fixed; top: 0; left: 60px; width: calc(100% - 60px); height: 45px;
            background-color: #0E1117; border-bottom: 1px solid #333; z-index: 999999;
            display: flex; align-items: center; padding-left: 10px;
        }
        .header-text { color: #00e676; font-size: 16px; font-weight: bold; margin: 0; }
        .block-container { padding-top: 60px !important; }
        .gcal-btn {
            text-decoration: none; display: inline-block; padding: 5px 10px;
            background-color: #333; color: white !important; border-radius: 4px;
            border: 1px solid #555; font-size: 0.8rem; margin-right: 5px;
        }
        .gcal-btn:hover { background-color: #444; border-color: #00e676; }
        /* コメント用 */
        .coach-box {
            background-color: #262730; border: 1px solid #444; border-radius: 8px;
            padding: 15px; margin-bottom: 20px;
        }
        .coach-title { font-weight: bold; color: #00e676; margin-bottom: 5px; }
        .coach-item { margin-bottom: 3px; font-size: 0.95rem; }
    </style>
    <div class="fixed-header"><span class="header-text">🇯🇵 PMCC 分析ツール (Ver 9.2)</span></div>
    """, unsafe_allow_html=True)

for key in ['ticker_data', 'strikes_data', 'load_trigger']:
    if key not in st.session_state: st.session_state[key] = None
if 'manual_mode' not in st.session_state: st.session_state['manual_mode'] = False
if 'ticker_input_val' not in st.session_state: st.session_state['ticker_input_val'] = "NVDA"

# ==========================================
# 4. サイドバー
# ==========================================
with st.sidebar:
    st.header("⚙️ 設定")
    st.session_state['manual_mode'] = st.toggle("手動入力モード", value=st.session_state['manual_mode'])
    st.divider()
    st.header("☁️ クラウド保存")
    slot_idx = st.selectbox("スロット選択", range(1, 6), format_func=lambda x: f"Slot {x}")
    row_num = slot_idx + 1

    c1, c2 = st.columns(2)
    with c1:
        if st.button("クラウド保存", use_container_width=True):
            with st.spinner("送信中..."):
                sheet, err = get_sheet_connection()
                if err: st.error(f"Error: {err}")
                else:
                    ts = datetime.now().strftime('%Y/%m/%d %H:%M')
                    save_list = [""] * 11
                    if st.session_state['manual_mode'] and 'm_ticker' in st.session_state:
                        save_list = [f"Slot {slot_idx}", ts, "manual", st.session_state.m_ticker, st.session_state.m_price, st.session_state.m_l_strike, st.session_state.m_l_prem, st.session_state.m_s_strike, st.session_state.m_s_prem, str(st.session_state.get('m_l_exp', '')), str(st.session_state.get('m_s_exp', ''))]
                    elif st.session_state.get('ticker_data'):
                        save_list = [f"Slot {slot_idx}", ts, "auto", st.session_state['ticker_data']['ticker'], st.session_state['ticker_data']['price'], st.session_state.get('long_strike_val', 0), st.session_state.get('prem_l_val', 0), st.session_state.get('short_strike_val', 0), st.session_state.get('prem_s_val', 0), st.session_state['strikes_data']['long_exp'], st.session_state['strikes_data']['short_exp']]
                    if save_list[0]:
                        try:
                            sheet.update(range_name=f"A{row_num}:K{row_num}", values=[save_list])
                            st.success("保存完了!")
                        except Exception as e: st.error(f"Error: {e}")
                    else: st.warning("データなし")
    with c2:
        if st.button("クラウド読込", use_container_width=True):
            with st.spinner("受信中..."):
                sheet, err = get_sheet_connection()
                if err: st.error(f"Error: {err}")
                else:
                    try:
                        vals = sheet.row_values(row_num)
                        if not vals or len(vals) < 4: st.warning("データ空")
                        else:
                            d_type, ticker, price = vals[2], vals[3], float(vals[4])
                            if d_type == 'manual':
                                st.session_state['manual_mode'] = True
                                st.session_state['m_ticker'] = ticker; st.session_state['m_price'] = price
                                st.session_state['m_l_strike'] = float(vals[5]); st.session_state['m_l_prem'] = float(vals[6])
                                st.session_state['m_s_strike'] = float(vals[7]); st.session_state['m_s_prem'] = float(vals[8])
                                try: st.session_state['m_l_exp'] = datetime.strptime(vals[9], '%Y-%m-%d').date()
                                except: pass
                                try: st.session_state['m_s_exp'] = datetime.strptime(vals[10], '%Y-%m-%d').date()
                                except: pass
                                st.rerun()
                            else:
                                st.session_state['manual_mode'] = False
                                st.session_state['ticker_input_val'] = ticker
                                st.session_state['load_trigger'] = {'ticker': ticker, 'long_exp': vals[9], 'short_exp': vals[10], 'long_strike': float(vals[5]), 'short_strike': float(vals[7])}
                                st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

# ==========================================
# 5. メイン処理
# ==========================================
price = 0.0
long_strike = 0.0
short_strike = 0.0
prem_l = 0.0
prem_s = 0.0
exp_l_obj = None
exp_s_obj = None
is_ready = False
ticker_name = "MANUAL"
delta_l, theta_l = None, None
delta_s, theta_s = None, None
T_l_days, T_s_days = 0, 0

if st.session_state['manual_mode']:
    st.info("📝 **手動モード** (Greeks計算不可)")
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        ticker_name = st.text_input("銘柄", value="NVDA", key="m_ticker").upper()
        price = st.number_input("株価 ($)", value=100.0, step=0.1, key="m_price")
    st.divider()
    c_l, c_s = st.columns(2)
    with c_l:
        st.subheader("Long (LEAPS)")
        exp_l_obj = st.date_input("Long満期", value=datetime.today()+timedelta(days=365), key="m_l_exp")
        long_strike = st.number_input("行使価格 (L)", value=80.0, step=1.0, key="m_l_strike")
        prem_l = st.number_input("支払 (Ask)", value=25.0, step=0.1, key="m_l_prem")
    with c_s:
        st.subheader("Short (Call)")
        exp_s_obj = st.date_input("Short満期", value=datetime.today()+timedelta(days=30), key="m_s_exp")
        short_strike = st.number_input("行使価格 (S)", value=130.0, step=1.0, key="m_s_strike")
        prem_s = st.number_input("受取 (Bid)", value=5.0, step=0.1, key="m_s_prem")
    if st.button("分析実行", type="primary"): is_ready = True

else:
    col1, col2 = st.columns([3, 1])
    with col1: ticker_input = st.text_input("銘柄", key="ticker_input_val", placeholder="NVDA").upper()
    with col2: fetch_pressed = st.button("データ取得", type="primary", use_container_width=True)

    if fetch_pressed or st.session_state['load_trigger']:
        with st.spinner("取得中..."):
            p_val, exps, err = fetch_ticker_info(ticker_input)
            if err:
                st.error(f"Error: {err}"); st.warning("👉 手動モード推奨")
                st.session_state['load_trigger'] = None
            else:
                st.session_state['ticker_data'] = {'price': p_val, 'exps': exps, 'ticker': ticker_input}
                st.session_state['strikes_data'] = None
                if fetch_pressed: st.session_state['load_trigger'] = None

    if st.session_state['ticker_data']:
        data = st.session_state['ticker_data']
        loaded = st.session_state.get('load_trigger')
        price = data['price']
        ticker_name = data['ticker']
        st.markdown(f"**現在株価: ${price:.2f}**")
        
        c1, c2 = st.columns(2)
        l_idx = len(data['exps']) - 1
        s_idx = 1 if len(data['exps']) > 1 else 0
        if loaded:
            if loaded['long_exp'] in data['exps']: l_idx = data['exps'].index(loaded['long_exp'])
            if loaded['short_exp'] in data['exps']: s_idx = data['exps'].index(loaded['short_exp'])

        with c1: long_exp = st.selectbox("Long満期", data['exps'], index=l_idx)
        with c2: short_exp = st.selectbox("Short満期", data['exps'], index=s_idx)
        
        try:
            exp_l_obj = datetime.strptime(long_exp, '%Y-%m-%d').date()
            exp_s_obj = datetime.strptime(short_exp, '%Y-%m-%d').date()
        except: pass

        auto_load = False
        if loaded: auto_load = True

        if 'chain_cache' not in st.session_state: st.session_state['chain_cache'] = {}
        if st.button("ストライク読込", use_container_width=True) or auto_load:
            with st.spinner("チェーン取得中..."):
                l_chain, err1 = fetch_option_chain_data(data['ticker'], long_exp)
                s_chain, err2 = fetch_option_chain_data(data['ticker'], short_exp)
                if err1 or err2: st.error("取得エラー")
                else:
                    st.session_state['chain_cache']['l'] = l_chain
                    st.session_state['chain_cache']['s'] = s_chain
                    strikes_l = sorted(l_chain['strike'].unique())
                    strikes_s = sorted(s_chain['strike'].unique())
                    if loaded and 'long_strike' in loaded:
                        def_l = min(strikes_l, key=lambda x:abs(x-loaded['long_strike']))
                        def_s = min(strikes_s, key=lambda x:abs(x-loaded['short_strike']))
                    else:
                        def_l = min(strikes_l, key=lambda x:abs(x-(data['price']*0.60)))
                        def_s = min(strikes_s, key=lambda x:abs(x-(data['price']*1.15)))
                    st.session_state['strikes_data'] = {'long_exp': long_exp, 'short_exp': short_exp, 'strikes_l': strikes_l, 'strikes_s': strikes_s, 'def_l': def_l, 'def_s': def_s}
        
        if loaded: st.session_state['load_trigger'] = None

        if st.session_state['strikes_data']:
            s_data = st.session_state['strikes_data']
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
            
            if st.button("分析実行", type="primary", use_container_width=True):
                l_chain = st.session_state['chain_cache'].get('l')
                s_chain = st.session_state['chain_cache'].get('s')
                if l_chain is not None and s_chain is not None:
                    l_row = l_chain[l_chain['strike'] == long_strike].iloc[0]
                    s_row = s_chain[s_chain['strike'] == short_strike].iloc[0]
                    
                    def get_price(row):
                        val = row.get('ask', 0) if 'ask' in row else 0
                        if pd.isna(val) or val <= 0: return row.get('lastPrice', 0)
                        return val
                    def get_bid(row):
                        val = row.get('bid', 0) if 'bid' in row else 0
                        if pd.isna(val) or val <= 0: return row.get('lastPrice', 0)
                        return val

                    prem_l = get_price(l_row)
                    prem_s = get_bid(s_row)
                    
                    today = datetime.today()
                    T_l = (datetime.strptime(long_exp, '%Y-%m-%d') - today).days / 365.0
                    T_s = (datetime.strptime(short_exp, '%Y-%m-%d') - today).days / 365.0
                    T_l_days = (datetime.strptime(long_exp, '%Y-%m-%d') - today).days
                    T_s_days = (datetime.strptime(short_exp, '%Y-%m-%d') - today).days
                    
                    iv_l = l_row.get('impliedVolatility', 0)
                    iv_s = s_row.get('impliedVolatility', 0)
                    r = 0.045
                    delta_l, theta_l = calculate_greeks(price, long_strike, T_l, r, iv_l, 'call')
                    delta_s, theta_s = calculate_greeks(price, short_strike, T_s, r, iv_s, 'call')
                    is_ready = True
                    
            st.session_state['long_strike_val'] = long_strike
            st.session_state['short_strike_val'] = short_strike
            st.session_state['prem_l_val'] = prem_l
            st.session_state['prem_s_val'] = prem_s

# ==========================================
# 6. 分析レポート
# ==========================================
if is_ready:
    if st.session_state['manual_mode']:
        ticker_name = st.session_state.m_ticker
        price = st.session_state.m_price
        long_strike = st.session_state.m_l_strike
        prem_l = st.session_state.m_l_prem
        short_strike = st.session_state.m_s_strike
        prem_s = st.session_state.m_s_prem
        exp_l_obj = st.session_state.m_l_exp
        exp_s_obj = st.session_state.m_s_exp

    try:
        net_debit = prem_l - prem_s
        total_cost = net_debit * 100
        breakeven = long_strike + net_debit
        
        st.markdown(f"### 📊 分析レポート ({ticker_name})")
        
        # --- コーチコメント ---
        if not st.session_state['manual_mode'] and delta_l is not None:
            comments = generate_coach_comments(delta_l, T_l_days, delta_s, T_s_days)
            score = comments['score']
            if score == 'S': score_icon = "💎 Sランク (完璧)"
            elif score == 'A': score_icon = "✅ Aランク (優秀)"
            else: score_icon = "⚠️ Bランク (要調整)"

            st.markdown(f"""
            <div class="coach-box">
                <div class="coach-title">👨‍🏫 AIコーチ判定: {score_icon}</div>
                {''.join([f'<div class="coach-item">{c}</div>' for c in comments['long']])}
                {''.join([f'<div class="coach-item">{c}</div>' for c in comments['short']])}
            </div>
            """, unsafe_allow_html=True)

        st.markdown("##### 📋 シナリオ別 損益内訳")
        scenarios = [
            {"name": f"現在値 (${price:.2f})", "p": price},
            {"name": f"損益分岐 (${breakeven:.2f})", "p": breakeven},
            {"name": f"Short行使 (${short_strike:.2f})", "p": short_strike},
        ]
        table_data = []
        for sc in scenarios:
            p = sc["p"]
            val_l = max(0, p - long_strike)
            val_s = max(0, p - short_strike)
            cost = -net_debit
            total = val_l - val_s + cost
            # ROI計算
            if total_cost > 0:
                roi = (total / total_cost) * 100
            else: roi = 0
            
            table_data.append({
                "シナリオ": sc["name"],
                "LEAPS価値": f"${val_l:.2f}",
                "Short損益": f"-${val_s:.2f}",
                "合計損益": f"${total:.2f}",
                "ROI": f"{roi:+.1f}%"
            })
        st.table(pd.DataFrame(table_data))

        m1, m2, m3 = st.columns(3)
        m1.metric("実質コスト", f"${net_debit:.2f}")
        m2.metric("初期投資", f"${total_cost:,.2f}") # カンマ追加
        m3.metric("分岐点", f"${breakeven:.2f}")
        st.caption(f"Long: ${long_strike} (支払 ${prem_l:.2f}) / Short: ${short_strike} (受取 ${prem_s:.2f})")

        fig, ax = plt.subplots(figsize=(10, 4))
        prices = np.linspace(price * 0.7, price * 1.3, 100)
        val_l_arr = np.maximum(0, prices - long_strike)
        val_s_arr = np.maximum(0, prices - short_strike)
        profit = (val_l_arr - val_s_arr) - net_debit
        
        ax.plot(prices, profit*100, color='#00e676')
        ax.axhline(0, color='gray', linestyle='--')
        ax.axvline(price, color='blue', linestyle=':', label='Current')
        ax.axvline(breakeven, color='orange', linestyle=':', label='BE')
        ax.fill_between(prices, profit*100, 0, where=(profit>0), color='#00e676', alpha=0.3)
        ax.fill_between(prices, profit*100, 0, where=(profit<0), color='#ff5252', alpha=0.3)
        ax.grid(True, alpha=0.3)
        ax.legend(['P&L', 'Zero Line', 'Current', 'Breakeven'])
        st.pyplot(fig)

        if exp_l_obj and exp_s_obj:
            st.divider()
            st.markdown("##### 📅 スケジュール管理")
            roll_date = exp_l_obj - timedelta(days=20)
            settle_date = exp_s_obj - timedelta(days=10)
            desc_common = f"銘柄: {ticker_name}\nLong: ${long_strike}\nShort: ${short_strike}"
            
            url_s_exp = create_gcal_url(f"【PMCC】Short満期 ({ticker_name})", exp_s_obj, desc_common)
            url_l_exp = create_gcal_url(f"【PMCC】LEAPS満期 ({ticker_name})", exp_l_obj, desc_common)
            url_roll = create_gcal_url(f"【PMCC】LEAPSロール ({ticker_name})", roll_date, f"{desc_common}\n満期20日前")
            url_settle = create_gcal_url(f"【PMCC】Short決済 ({ticker_name})", settle_date, f"{desc_common}\n満期10日前")

            gc1, gc2, gc3, gc4 = st.columns(4)
            with gc1: st.markdown(f"**Short満期**<br>{exp_s_obj}<br><a href='{url_s_exp}' target='_blank' class='gcal-btn'>＋カレンダー登録</a>", unsafe_allow_html=True)
            with gc2: st.markdown(f"**Short決済目安**<br>{settle_date}<br><a href='{url_settle}' target='_blank' class='gcal-btn'>＋カレンダー登録</a>", unsafe_allow_html=True)
            with gc3: st.markdown(f"**LEAPS満期**<br>{exp_l_obj}<br><a href='{url_l_exp}' target='_blank' class='gcal-btn'>＋カレンダー登録</a>", unsafe_allow_html=True)
            with gc4: st.markdown(f"**LEAPSロール目安**<br>{roll_date}<br><a href='{url_roll}' target='_blank' class='gcal-btn'>＋カレンダー登録</a>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"計算エラー: {e}")
