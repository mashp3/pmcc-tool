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
# 1. デザイン修正 (CSS注入)
# ==========================================
st.markdown("""
    <style>
        /* デフォルトのヘッダー・フッター・メニューを隠す */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* 固定ヘッダーのスタイル */
        .fixed-header {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 50px;
            background-color: #0E1117; /* ダークモード背景色 */
            border-bottom: 1px solid #262730;
            z-index: 99999;
            display: flex;
            align-items: center;
            padding-left: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.5);
        }
        
        /* ヘッダー内のタイトル文字 */
        .header-text {
            color: #00e676; /* アクセントカラー */
            font-size: 1.2rem;
            font-weight: bold;
            margin: 0;
        }

        /* 本文がヘッダーに隠れないように余白を確保 */
        .block-container {
            padding-top: 70px !important;
        }
    </style>
    
    <div class="fixed-header">
        <p class="header-text">🇯🇵 PMCC 分析ツール (Webアプリ版)</p>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 2. ポートフォリオ機能 (サイドバー)
# ==========================================
# セッション初期化
if 'portfolios' not in st.session_state:
    st.session_state['portfolios'] = {f"Slot {i+1}": None for i in range(5)}
if 'ticker_data' not in st.session_state:
    st.session_state['ticker_data'] = None
if 'strikes_data' not in st.session_state:
    st.session_state['strikes_data'] = None

# ロード用のフラグ管理
if 'load_trigger' not in st.session_state:
    st.session_state['load_trigger'] = None

with st.sidebar:
    st.header("📂 ポートフォリオ (5枠)")
    selected_slot = st.selectbox("保存スロット", [f"Slot {i+1}" for i in range(5)])
    
    # 現在の保存状況表示
    saved_data = st.session_state['portfolios'][selected_slot]
    if saved_data:
        st.caption(f"保存済み: {saved_data['ticker']} ({saved_data['save_date']})")
    else:
        st.caption("データなし")
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        if st.button("保存", use_container_width=True):
            # 現在の入力状態を保存
            if st.session_state.get('ticker_data') and st.session_state.get('strikes_data'):
                # ユーザーが現在選択している値をウィジェットから取得したいが、
                # ここでは安全のため session_state のデータを参照して保存
                # ※注意: 再現性を高めるため、現在の選択状態(index)ではなく値を保存します
                current_ticker = st.session_state['ticker_data']['ticker']
                current_long_exp = st.session_state['strikes_data']['long_exp']
                current_short_exp = st.session_state['strikes_data']['short_exp']
                
                # 詳細分析まで進んでいれば、選択したストライク価格を保存したい
                # しかし、ストライクは動的に変わるため、ここでは「銘柄と満期日」を保存します
                st.session_state['portfolios'][selected_slot] = {
                    'ticker': current_ticker,
                    'long_exp': current_long_exp,
                    'short_exp': current_short_exp,
                    'save_date': datetime.now().strftime('%Y-%m-%d %H:%M')
                }
                st.success("保存完了")
                st.rerun()
            else:
                st.error("保存するデータがありません")
    
    with col_p2:
        if st.button("読込", use_container_width=True):
            if saved_data:
                st.session_state['load_trigger'] = saved_data
                st.rerun() # リロードしてメイン画面に反映
            else:
                st.warning("データがありません")


# ==========================================
# 3. メイン処理 (データ取得ロジック)
# ==========================================

# ロード処理がトリガーされていた場合の初期値設定
default_ticker = "NVDA"
if st.session_state['load_trigger']:
    default_ticker = st.session_state['load_trigger']['ticker']

st.header("1. 銘柄選択")
col1, col2 = st.columns([3, 1])
with col1:
    ticker_input = st.text_input("銘柄コード (例: NVDA, LEU)", value=default_ticker).upper()
with col2:
    st.write("") # スペース調整
    st.write("") 
    # ロード直後なら自動でボタンを押したことにする、または通常通りボタンを表示
    fetch_pressed = st.button("データ取得", type="primary")

# ロードトリガーがある、またはボタンが押された場合に実行
if fetch_pressed or st.session_state['load_trigger']:
    with st.spinner("株価データを取得中..."):
        try:
            tk = yf.Ticker(ticker_input)
            hist = tk.history(period='1d')
            if hist.empty:
                st.error("データが見つかりません。")
                st.session_state['load_trigger'] = None # エラーならロード解除
            else:
                price = hist['Close'].iloc[-1]
                exps = tk.options
                if not exps:
                    st.error("オプションデータがありません。")
                    st.session_state['load_trigger'] = None
                else:
                    st.session_state['ticker_data'] = {
                        'price': price,
                        'exps': exps,
                        'ticker': ticker_input
                    }
                    st.session_state['strikes_data'] = None # リセット
                    
                    # ボタン押下時は成功メッセージ
                    if fetch_pressed:
                        st.success(f"取得成功: ${price:.2f}")
                        st.session_state['load_trigger'] = None # 手動取得ならロード解除
        except Exception as e:
            st.error(f"エラー: {e}")
            st.session_state['load_trigger'] = None

# --- Step 2: 満期日選択 ---
if st.session_state['ticker_data']:
    data = st.session_state['ticker_data']
    # ロード用データがあればそれを参照
    loaded_data = st.session_state.get('load_trigger')
    
    st.markdown(f"**現在株価: ${data['price']:.2f}**")
    
    st.header("2. 満期日設定")
    c1, c2 = st.columns(2)
    
    # デフォルト値の計算
    long_def_idx = len(data['exps']) - 1
    short_def_idx = 1 if len(data['exps']) > 1 else 0

    # ロード時は保存された満期日を選択しようとする
    if loaded_data:
        if loaded_data['long_exp'] in data['exps']:
            long_def_idx = data['exps'].index(loaded_data['long_exp'])
        if loaded_data['short_exp'] in data['exps']:
            short_def_idx = data['exps'].index(loaded_data['short_exp'])

    with c1:
        long_exp = st.selectbox("Long満期 (土台/LEAPS)", data['exps'], index=long_def_idx)
    with c2:
        short_exp = st.selectbox("Short満期 (収益)", data['exps'], index=short_def_idx)

    # ロード時、またはボタン押下時にストライク読み込み
    load_strikes_pressed = st.button("ストライク価格を読み込む")
    
    # ロード直後は自動でストライク読み込みまで進める
    if load_strikes_pressed or loaded_data:
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
                # ロード完了につきフラグを下ろす
                st.session_state['load_trigger'] = None
                
            except Exception as e:
                st.error(f"データ取得エラー: {e}")
                st.session_state['load_trigger'] = None

# --- Step 3: ストライク選択と分析 ---
if st.session_state['strikes_data']:
    s_data = st.session_state['strikes_data']
    price = st.session_state['ticker_data']['price']
    ticker = st.session_state['ticker_data']['ticker']
    
    st.header("3. ポジション構築 & 分析")
    
    c1, c2 = st.columns(2)
    with c1:
        # indexメソッドの安全策（万が一推奨値が変わっていた場合）
        try:
            def_l_idx = s_data['strikes_l'].index(s_data['def_l'])
        except:
            def_l_idx = 0
        long_strike = st.selectbox("Long権利行使価格", s_data['strikes_l'], index=def_l_idx)
        
    with c2:
        try:
            def_s_idx = s_data['strikes_s'].index(s_data['def_s'])
        except:
            def_s_idx = 0
        short_strike = st.selectbox("Short権利行使価格", s_data['strikes_s'], index=def_s_idx)

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
                
                # ==== ユーザー指定の計算ロジック (変更なし) ====
                prem_l = l_row['ask']
                prem_s = s_row['bid']
                net_debit = prem_l - prem_s
                total_cost = net_debit * 100
                breakeven = long_strike + net_debit
                # ==========================================
                
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
                
                # ==== ユーザー指定の計算ロジック (変更なし) ====
                val_l = np.maximum(0, prices - long_strike)
                val_s = np.maximum(0, prices - short_strike)
                profit = (val_l - val_s) - net_debit
                profit_total = profit * 100
                # ==========================================

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
                    # ==== ユーザー指定の計算ロジック (変更なし) ====
                    vl = max(0, p - long_strike)
                    vs = max(0, p - short_strike)
                    pf = (vl - vs) - net_debit
                    # ==========================================
                    data_list.append({
                        "株価": p,
                        "総損益": pf * 100,
                        "ROI": (pf / net_debit) * 100
                    })
                df = pd.DataFrame(data_list)
                st.dataframe(df.style.format({"株価": "${:.2f}", "総損益": "${:.0f}", "ROI": "{:.1f}%"}))

            except Exception as e:
                st.error(f"分析エラー: {e}")
