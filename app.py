import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# --- フォント設定 (OSインストール済みフォントを使用) ---
# packages.txt で 'fonts-ipafont-gothic' をインストールしている前提
plt.rcParams['font.family'] = 'IPAGothic'

# ページ設定
st.set_page_config(page_title="PMCC Analyzer", layout="wide")

st.title("🇯🇵 PMCC 分析ツール (Webアプリ版)")
st.markdown("LEAPSを使ったカバードコール戦略（PMCC）の損益シミュレーター")

# --- セッション状態の初期化 ---
if 'ticker_data' not in st.session_state:
    st.session_state['ticker_data'] = None
if 'strikes_data' not in st.session_state:
    st.session_state['strikes_data'] = None

# --- Step 1: データ取得 ---
st.header("1. 銘柄選択")
col1, col2 = st.columns([3, 1])
with col1:
    ticker_input = st.text_input("銘柄コード (例: NVDA, LEU)", value="NVDA").upper()
with col2:
    st.write("") # スペース調整
    st.write("") 
    if st.button("データ取得", type="primary"):
        with st.spinner("株価データを取得中..."):
            try:
                tk = yf.Ticker(ticker_input)
                hist = tk.history(period='1d')
                if hist.empty:
                    st.error("データが見つかりません。")
                else:
                    price = hist['Close'].iloc[-1]
                    exps = tk.options
                    if not exps:
                        st.error("オプションデータがありません。")
                    else:
                        st.session_state['ticker_data'] = {
                            'price': price,
                            'exps': exps,
                            'ticker': ticker_input
                        }
                        st.session_state['strikes_data'] = None # リセット
                        st.success(f"取得成功: ${price:.2f}")
            except Exception as e:
                st.error(f"エラー: {e}")

# --- Step 2: 満期日選択 ---
if st.session_state['ticker_data']:
    data = st.session_state['ticker_data']
    st.markdown(f"**現在株価: ${data['price']:.2f}**")
    
    st.header("2. 満期日設定")
    c1, c2 = st.columns(2)
    
    # デフォルト値の計算
    long_def_idx = len(data['exps']) - 1
    short_def_idx = 1 if len(data['exps']) > 1 else 0

    with c1:
        long_exp = st.selectbox("Long満期 (土台/LEAPS)", data['exps'], index=long_def_idx)
    with c2:
        short_exp = st.selectbox("Short満期 (収益)", data['exps'], index=short_def_idx)

    if st.button("ストライク価格を読み込む"):
        with st.spinner("オプションチェーンを取得中..."):
            try:
                tk = yf.Ticker(data['ticker'])
                # Long
                chain_l = tk.option_chain(long_exp).calls
                strikes_l = sorted(chain_l['strike'].unique())
                # Short
                chain_s = tk.option_chain(short_exp).calls
                strikes_s = sorted(chain_s['strike'].unique())
                
                # 推奨値の計算
                target_l = data['price'] * 0.60
                def_l = min(strikes_l, key=lambda x:abs(x-target_l))
                
                target_s = data['price'] * 1.15
                def_s = min(strikes_s, key=lambda x:abs(x-target_s))

                st.session_state['strikes_data'] = {
                    'long_exp': long_exp,
                    'short_exp': short_exp,
                    'strikes_l': strikes_l,
                    'strikes_s': strikes_s,
                    'def_l': def_l,
                    'def_s': def_s
                }
            except Exception as e:
                st.error(f"データ取得エラー: {e}")

# --- Step 3: ストライク選択と分析 ---
if st.session_state['strikes_data']:
    s_data = st.session_state['strikes_data']
    price = st.session_state['ticker_data']['price']
    ticker = st.session_state['ticker_data']['ticker']
    
    st.header("3. ポジション構築 & 分析")
    
    c1, c2 = st.columns(2)
    with c1:
        long_strike = st.selectbox("Long権利行使価格", s_data['strikes_l'], index=s_data['strikes_l'].index(s_data['def_l']))
    with c2:
        short_strike = st.selectbox("Short権利行使価格", s_data['strikes_s'], index=s_data['strikes_s'].index(s_data['def_s']))

    # --- リアルタイム判定ロジック ---
    def check_quality(price, l_date, l_strike):
        today = datetime.today()
        d_obj = datetime.strptime(l_date, '%Y-%m-%d')
        days = (d_obj - today).days
        moneyness = l_strike / price
        
        msgs = []
        is_safe = True
        
        if days < 180:
            msgs.append(f"❌ 期間不足: 残り{days}日 (推奨1年以上)")
            is_safe = False
        elif days < 365:
            msgs.append(f"⚠️ 期間注意: 残り{days}日 (半年〜1年は短期戦)")
        else:
            msgs.append(f"✅ 期間十分: 残り{days}日")
            
        if moneyness > 0.9:
            msgs.append(f"❌ 深さ不足: Strikeが現在値の{moneyness:.0%} (浅すぎる)")
            is_safe = False
        elif moneyness > 0.8:
            msgs.append(f"⚠️ 深さ注意: Strikeが現在値の{moneyness:.0%} (Delta不足の懸念)")
        else:
            msgs.append(f"✅ 深さ十分: Strikeが現在値の{moneyness:.0%} (Deep ITM)")
            
        return msgs, is_safe

    msgs, is_safe = check_quality(price, s_data['long_exp'], long_strike)
    
    st.info("🕵️‍♂️ **鬼教官の診断結果**")
    for msg in msgs:
        st.write(msg)

    if st.button("詳細分析を実行", type="primary"):
        with st.spinner("計算中..."):
            try:
                tk = yf.Ticker(ticker)
                l_opt = tk.option_chain(s_data['long_exp']).calls
                l_row = l_opt[l_opt['strike'] == long_strike].iloc[0]
                
                s_opt = tk.option_chain(s_data['short_exp']).calls
                s_row = s_opt[s_opt['strike'] == short_strike].iloc[0]
                
                prem_l = l_row['ask']
                prem_s = s_row['bid']
                net_debit = prem_l - prem_s
                total_cost = net_debit * 100
                breakeven = long_strike + net_debit
                
                # 結果表示
                st.subheader("📊 分析レポート")
                res_col1, res_col2, res_col3 = st.columns(3)
                res_col1.metric("実質コスト (単価)", f"${net_debit:.2f}")
                res_col2.metric("初期投資額 (1セット)", f"${total_cost:.0f}")
                res_col3.metric("損益分岐点", f"${breakeven:.2f}")
                
                st.write(f"🔹 **Long**: ${long_strike} (支払: ${prem_l:.2f})")
                st.write(f"🔸 **Short**: ${short_strike} (受取: ${prem_s:.2f})")

                # グラフ描画
                fig, ax = plt.subplots(figsize=(10, 5))
                prices = np.linspace(price * 0.7, price * 1.3, 100)
                val_l = np.maximum(0, prices - long_strike)
                val_s = np.maximum(0, prices - short_strike)
                profit = (val_l - val_s) - net_debit
                profit_total = profit * 100

                ax.plot(prices, profit_total, color='#00e676', label='P&L')
                ax.axhline(0, color='gray', linestyle='--')
                ax.axvline(price, color='blue', linestyle=':', label='Current Price')
                ax.axvline(breakeven, color='orange', linestyle=':', label='Breakeven')
                ax.fill_between(prices, profit_total, 0, where=(profit_total>0), color='#00e676', alpha=0.3)
                ax.fill_between(prices, profit_total, 0, where=(profit_total<0), color='#ff5252', alpha=0.3)
                ax.set_title(f"PMCC P&L Simulation ({ticker})")
                ax.set_xlabel("Stock Price ($)")
                ax.set_ylabel("Total Profit/Loss ($)")
                ax.legend()
                ax.grid(True, alpha=0.3)
                
                st.pyplot(fig)

                # テーブル表示
                st.write("📋 **価格別損益表**")
                sim_prices = np.linspace(price * 0.7, price * 1.3, 11)
                data_list = []
                for p in sim_prices:
                    vl = max(0, p - long_strike)
                    vs = max(0, p - short_strike)
                    pf = (vl - vs) - net_debit
                    data_list.append({
                        "株価": p,
                        "総損益": pf * 100,
                        "ROI": (pf / net_debit) * 100
                    })
                df = pd.DataFrame(data_list)
                st.dataframe(df.style.format({"株価": "${:.2f}", "総損益": "${:.0f}", "ROI": "{:.1f}%"}))

            except Exception as e:
                st.error(f"分析エラー: {e}")
