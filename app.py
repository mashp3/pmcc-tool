import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import json

# --- フォント設定 ---
plt.rcParams['font.family'] = 'IPAGothic'

# ページ設定
st.set_page_config(page_title="PMCC Analyzer", layout="wide")

# --- CSS設定 (デザイン調整) ---
# 1. ヘッダーを固定・コンパクト化
# 2. 余計なメニューを隠す
# 3. コンテンツがヘッダーに隠れないように余白調整
st.markdown("""
    <style>
        /* メニューとフッターを隠す */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        /* 固定ヘッダーのデザイン */
        .fixed-header {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            background-color: #0E1117; /* 背景色 */
            z-index: 9999;
            padding: 10px 20px;
            border-bottom: 1px solid #333;
            display: flex;
            align-items: center;
            justify-content: space-between;
            height: 50px;
        }
        .header-title {
            color: #00e676;
            font-weight: bold;
            font-size: 18px;
            margin: 0;
        }
        .header-sub {
            color: #888;
            font-size: 12px;
            margin-left: 10px;
        }
        
        /* 本文がヘッダーに隠れないように上部余白を追加 */
        .block-container {
            padding-top: 60px !important;
        }
    </style>
    
    <div class="fixed-header">
        <div style="display:flex; align-items:baseline;">
            <p class="header-title">🇯🇵 PMCC Analyzer</p>
            <p class="header-sub">Ver 3.0 (Portfolio Edition)</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

# --- セッション状態の初期化 ---
if 'ticker_data' not in st.session_state:
    st.session_state['ticker_data'] = None
if 'strikes_data' not in st.session_state:
    st.session_state['strikes_data'] = None
# ポートフォリオ用 (5枠)
if 'portfolios' not in st.session_state:
    st.session_state['portfolios'] = {
        "Slot 1": {}, "Slot 2": {}, "Slot 3": {}, "Slot 4": {}, "Slot 5": {}
    }

# --- サイドバー: ポートフォリオ管理 ---
with st.sidebar:
    st.header("📂 ポートフォリオ")
    selected_slot = st.selectbox("スロット選択", ["Slot 1", "Slot 2", "Slot 3", "Slot 4", "Slot 5"])
    
    # 現在のスロットの状態を表示
    current_data = st.session_state['portfolios'][selected_slot]
    if current_data:
        st.caption(f"保存済み: {current_data.get('ticker', 'Unknown')}")
    else:
        st.caption("データなし")

    col_p1, col_p2 = st.columns(2)
    
    # 保存ボタン
    with col_p1:
        if st.button("現在の状態を保存"):
            # 現在の入力状態を取得して保存
            if st.session_state.get('ticker_data') and st.session_state.get('strikes_data'):
                save_data = {
                    'ticker': st.session_state['ticker_data']['ticker'],
                    'long_exp': st.session_state['strikes_data']['long_exp'],
                    'short_exp': st.session_state['strikes_data']['short_exp'],
                    # 注意: ストライク価格そのものはUIで選択するため、再計算が必要
                    # ここでは銘柄と満期日セットを保存します
                }
                st.session_state['portfolios'][selected_slot] = save_data
                st.success("保存しました")
                st.rerun() # リロードして表示更新
            else:
                st.error("データがありません")

    # 読込ボタン
    with col_p2:
        if st.button("読込"):
            loaded = st.session_state['portfolios'][selected_slot]
            if loaded:
                # 読み込みロジック (疑似的に入力欄を上書きしたいが、Streamlitの仕様上
                # session_stateを直接書き換えるアプローチをとる)
                # ※簡易実装として、銘柄コードをセットして自動実行を促す形にします
                st.session_state['manual_ticker'] = loaded['ticker']
                st.info(f"{loaded['ticker']} をロード。データ取得を押してください。")
            else:
                st.warning("空のスロットです")

    st.divider()
    # バックアップ機能
    st.caption("PCへのバックアップ")
    json_str = json.dumps(st.session_state['portfolios'], ensure_ascii=False)
    st.download_button(
        label="設定ファイル(.json)をDL",
        data=json_str,
        file_name="pmcc_portfolio.json",
        mime="application/json"
    )

# --- メインコンテンツ ---

# ポートフォリオ読込時の初期値
default_ticker = "NVDA"
if 'manual_ticker' in st.session_state:
    default_ticker = st.session_state['manual_ticker']
    # 一度使ったら消す
    del st.session_state['manual_ticker']

# --- Step 1: データ取得 ---
st.subheader("1. 銘柄選択")
col1, col2 = st.columns([3, 1])
with col1:
    ticker_input = st.text_input("銘柄コード", value=default_ticker).upper()
with col2:
    st.write("") 
    st.write("") 
    fetch_btn = st.button("データ取得", type="primary", use_container_width=True)

if fetch_btn:
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
                    st.session_state['strikes_data'] = None
                    st.success(f"取得成功: ${price:.2f}")
        except Exception as e:
            st.error(f"エラー: {e}")

# --- Step 2: 満期日選択 ---
if st.session_state['ticker_data']:
    data = st.session_state['ticker_data']
    st.markdown(f"**現在株価: ${data['price']:.2f}**")
    
    st.subheader("2. 満期日設定")
    c1, c2 = st.columns(2)
    
    # ポートフォリオからのロードがあればそれを優先、なければデフォルト
    long_def_idx = len(data['exps']) - 1
    short_def_idx = 1 if len(data['exps']) > 1 else 0

    # 選択済みスロットから満期情報を探す
    # (ロード直後かつ銘柄が一致する場合のみ適用)
    current_slot = st.session_state['portfolios'][selected_slot]
    if current_slot and current_slot.get('ticker') == data['ticker']:
         if current_slot.get('long_exp') in data['exps']:
             long_def_idx = data['exps'].index(current_slot['long_exp'])
         if current_slot.get('short_exp') in data['exps']:
             short_def_idx = data['exps'].index(current_slot['short_exp'])

    with c1:
        long_exp = st.selectbox("Long満期 (土台/LEAPS)", data['exps'], index=long_def_idx)
    with c2:
        short_exp = st.selectbox("Short満期 (収益)", data['exps'], index=short_def_idx)

    if st.button("ストライク価格を読み込む"):
        with st.spinner("オプションチェーンを取得中..."):
            try:
                tk = yf.Ticker(data['ticker'])
                chain_l = tk.option_chain(long_exp).calls
                strikes_l = sorted(chain_l['strike'].unique())
                chain_s = tk.option_chain(short_exp).calls
                strikes_s = sorted(chain_s['strike'].unique())
                
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
    
    st.subheader("3. ポジション構築 & 分析")
    
    c1, c2 = st.columns(2)
    with c1:
        long_strike = st.selectbox("Long権利行使価格", s_data['strikes_l'], index=s_data['strikes_l'].index(s_data['def_l']))
    with c2:
        short_strike = st.selectbox("Short権利行使価格", s_data['strikes_s'], index=s_data['strikes_s'].index(s_data['def_s']))

    # 鬼教官チェック
    def check_quality(price, l_date, l_strike):
        today = datetime.today()
        d_obj = datetime.strptime(l_date, '%Y-%m-%d')
        days = (d_obj - today).days
        moneyness = l_strike / price
        msgs = []
        
        if days < 180: msgs.append(f"❌ 期間不足: 残り{days}日 (推奨1年以上)")
        elif days < 365: msgs.append(f"⚠️ 期間注意: 残り{days}日 (半年〜1年は短期戦)")
        else: msgs.append(f"✅ 期間十分: 残り{days}日")
            
        if moneyness > 0.9: msgs.append(f"❌ 深さ不足: Strikeが現在値の{moneyness:.0%} (浅すぎる)")
        elif moneyness > 0.8: msgs.append(f"⚠️ 深さ注意: Strikeが現在値の{moneyness:.0%} (Delta不足の懸念)")
        else: msgs.append(f"✅ 深さ十分: Strikeが現在値の{moneyness:.0%} (Deep ITM)")
        return msgs

    msgs = check_quality(price, s_data['long_exp'], long_strike)
    st.info("  \n".join(msgs)) # 改行して表示

    if st.button("詳細分析を実行", type="primary", use_container_width=True):
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
                
                # --- レポート表示 ---
                st.markdown("---")
                st.markdown("#### 📊 分析レポート")
                
                m1, m2, m3 = st.columns(3)
                m1.metric("実質コスト", f"${net_debit:.2f}")
                m2.metric("初期投資(100株)", f"${total_cost:.0f}")
                m3.metric("損益分岐点", f"${breakeven:.2f}")
                
                st.caption(f"Long: ${long_strike} (払: ${prem_l:.2f}) / Short: ${short_strike} (受: ${prem_s:.2f})")

                # グラフ
                fig, ax = plt.subplots(figsize=(10, 4)) # 高さを少し縮小
                prices = np.linspace(price * 0.7, price * 1.3, 100)
                val_l = np.maximum(0, prices - long_strike)
                val_s = np.maximum(0, prices - short_strike)
                profit = (val_l - val_s) - net_debit
                profit_total = profit * 100

                ax.plot(prices, profit_total, color='#00e676', label='P&L')
                ax.axhline(0, color='gray', linestyle='--')
                ax.axvline(price, color='blue', linestyle=':', label='Current')
                ax.axvline(breakeven, color='orange', linestyle=':', label='BE')
                ax.fill_between(prices, profit_total, 0, where=(profit_total>0), color='#00e676', alpha=0.3)
                ax.fill_between(prices, profit_total, 0, where=(profit_total<0), color='#ff5252', alpha=0.3)
                ax.grid(True, alpha=0.3)
                st.pyplot(fig)

                # テーブル (折りたたみ式に)
                with st.expander("詳細な価格別損益表を見る"):
                    sim_prices = np.linspace(price * 0.7, price * 1.3, 11)
                    data_list = []
                    for p in sim_prices:
                        vl = max(0, p - long_strike)
                        vs = max(0, p - short_strike)
                        pf = (vl - vs) - net_debit
                        data_list.append({"株価": p, "総損益": pf * 100, "ROI": (pf / net_debit) * 100})
                    df = pd.DataFrame(data_list)
                    st.dataframe(df.style.format({"株価": "${:.2f}", "総損益": "${:.0f}", "ROI": "{:.1f}%"}))

            except Exception as e:
                st.error(f"分析エラー: {e}")
