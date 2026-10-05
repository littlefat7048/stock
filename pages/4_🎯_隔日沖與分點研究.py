"""
台股隔日沖手法研究與主力分點分時足跡專頁 (4_🎯_隔日沖與分點研究.py)
功能特點：
1. 還原專業主力籌碼看盤軟體之「分點進出成本 vs. 盤中 1 分鐘走勢還原」
2. 支援全自動抓取主力分點，亦支援手動上傳看盤軟體（XQ、三竹、富邦等）匯出之 700+ 家分點 Excel / CSV
3. 走勢圖支援 VWAP（市場均價線）、主力分點買賣均價水平線、以及進出場可能時段色帶（▲▼ 足跡）
4. 盤中特大單爆量點火高亮警示（比照 Tick 逐筆撮合特大單流水帳）
5. 雙圖黃金十字查價線貫穿上下
6. 內建 24 小時嚴格本地快取，杜絕重複外部請求，符合網路禮儀與法規安全
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from modules.data_fetcher import get_stock_info
from modules.broker_analysis import (
    get_intraday_minute_data,
    get_broker_trading_auto,
    parse_broker_excel,
    match_broker_footprint
)
from utils.charts import create_intraday_footprint_chart
from utils.helpers import get_searchable_stock_options, color_for_change

st.set_page_config(page_title="隔日沖手法研究 - 台股分點足跡", page_icon="🎯", layout="wide")

# 自訂深色現代風格 CSS
st.markdown("""
<style>
.metric-card {
    background: #161F30;
    border: 1px solid #263044;
    border-radius: 8px;
    padding: 10px 14px;
}
.broker-pill-buy {
    background: rgba(229, 57, 53, 0.12);
    border: 1px solid #e53935;
    color: #FF8A80;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 14.5px;
    font-weight: bold;
}
.broker-pill-sell {
    background: rgba(67, 160, 71, 0.12);
    border: 1px solid #43a047;
    color: #81C784;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 14.5px;
    font-weight: bold;
}
.stock-chip-link {
    display: inline-flex;
    align-items: center;
    background: #1E293B;
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 4px 12px;
    margin: 2px 4px 2px 0;
    font-size: 15.5px;
    color: #E2E8F0;
    text-decoration: none;
    white-space: nowrap;
    transition: all 0.15s ease-in-out;
}
.stock-chip-link:hover {
    background: #0F172A;
    border-color: #38BDF8;
    color: #38BDF8;
}
.chip-code {
    background: #0F172A;
    color: #38BDF8;
    padding: 1px 6px;
    border-radius: 10px;
    margin-right: 6px;
    font-size: 14px;
    font-weight: bold;
}
.footprint-legend {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-top: 6px;
    font-size: 14.5px;
    color: #94A3B8;
}
</style>
""", unsafe_allow_html=True)

# 頂部導航
nav_html = (
    "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px; border-bottom:1px solid #2A324B; padding-bottom:10px;'>"
    "<div style='display:flex; align-items:center; gap:8px;'>"
    "<span style='font-size:24px; font-weight:bold; color:#FFD700;'>📊 隔日沖手法研究</span>"
    "<span style='font-size:14px; color:#94A3B8; background:#1E293B; padding:2px 8px; border-radius:12px;'>v1.3.0 專業版</span>"
    "</div>"
    "<div style='display:flex; gap:6px; flex-wrap:wrap;'>"
    "<a href='/' target='_self' class='stock-chip-link'>📰 盤後日報</a>"
    "<a href='/強勢雷達' target='_self' class='stock-chip-link'>🚀 強勢雷達</a>"
    "<a href='/股票分析' target='_self' class='stock-chip-link'>📊 股票分析</a>"
    "<a href='/概念股' target='_self' class='stock-chip-link'>🏷️ 概念股</a>"
    "<a href='/自選股' target='_self' class='stock-chip-link'>⭐ 自選股</a>"
    "<span class='stock-chip-link' style='border-color:#FFD700; color:#FFD700; font-weight:bold;'>🎯 隔日沖研究</span>"
    "</div>"
    "</div>"
)
st.markdown(nav_html, unsafe_allow_html=True)

# 讀取 URL 參數中的股票代號
url_stock = st.query_params.get('stock', '')
default_code = url_stock if url_stock else '6672'

# 頂部控制列
c_inp, c_date, c_upload = st.columns([2.5, 1.3, 1.2])

with c_inp:
    options, c2l, l2c = get_searchable_stock_options()
    def_idx = 0
    if default_code in c2l:
        target_lbl = c2l[default_code]
        if target_lbl in options:
            def_idx = options.index(target_lbl)

    selected_option = st.selectbox(
        "🔍 輸入股票代號或中文名稱（支援即時聯想）",
        options=options,
        index=def_idx,
        key="broker_stock_select"
    )
    stock_code = l2c.get(selected_option, default_code)

with c_date:
    # 預設為最新交易日（若為週日或週一早上，取上週五）
    today = datetime.now()
    default_d = today.date()
    if today.weekday() == 6:  # 週日
        default_d = (today - timedelta(days=2)).date()
    elif today.weekday() == 5:  # 週六
        default_d = (today - timedelta(days=1)).date()
    elif today.weekday() == 0 and today.hour < 16:  # 週一盤中取上週五
        default_d = (today - timedelta(days=3)).date()
    elif today.hour < 16:  # 平日收盤前取前一天
        default_d = (today - timedelta(days=1)).date()

    query_date = st.date_input("📅 研究日期", value=default_d, key="broker_date_picker")
    date_str = query_date.strftime('%Y-%m-%d')

with c_upload:
    st.write("")
    st.write("")
    with st.popover("📁 Excel 分點匯入", use_container_width=True):
        st.markdown("**匯入看盤軟體匯出之分點檔**")
        st.caption("支援 XQ、三竹、富邦、元大等匯出之 .xlsx 或 .csv，一秒載入 700+ 家完整分點！")
        uploaded_file = st.file_uploader("選擇分點明細檔案", type=['xlsx', 'xls', 'csv'], key="broker_file_uploader")

# 熱門速選標籤
quick_samples = [
    ('6672', '騰輝電子-KY'), ('2327', '國巨'), ('2330', '台積電'),
    ('2317', '鴻海'), ('2454', '聯發科'), ('2382', '廣達'), ('2882', '國泰金')
]
sample_chips = "".join([
    f'<a href="/隔日沖與分點研究?stock={qcode}" target="_self" class="stock-chip-link">'
    f'<span class="chip-code">{qcode}</span>{qname}</a>'
    for qcode, qname in quick_samples
])
st.markdown(
    f'<div style="display:flex; align-items:center; margin-bottom:10px;">'
    f'<span style="color:#94A3B8; font-size:16.5px; margin-right:6px; flex-shrink:0;">🔥 熱門分點焦點：</span>'
    f'<div style="display:flex; overflow-x:auto; padding:2px 0;">{sample_chips}</div>'
    f'</div>',
    unsafe_allow_html=True
)

# ══════════════════════════════════════════════════════════
# 資料載入核心
# ══════════════════════════════════════════════════════════
with st.spinner(f"正在載入 {stock_code} 盤中分時走勢與主力分點進出資料..."):
    # 1. 抓取盤中分時 1 分鐘線
    df_m = get_intraday_minute_data(stock_code, date_str)
    # 2. 取得股票基本資料
    info = get_stock_info(stock_code)
    stock_name = info.get('name', stock_code)

    # 3. 取得分點資料（若有上傳 Excel 優先解析，否則全自動從公開平台抓取）
    if uploaded_file is not None:
        broker_data = parse_broker_excel(uploaded_file, uploaded_file.name)
        if not broker_data.get('available'):
            st.warning(f"⚠️ Excel 檔案解析異常: {broker_data.get('error')}，已自動切換回全自動網路抓取。")
            broker_data = get_broker_trading_auto(stock_code, date_str)
    else:
        broker_data = get_broker_trading_auto(stock_code, date_str)

if df_m.empty:
    st.error(f"❌ 查無台股 {stock_name} ({stock_code}) 於 {date_str} 的盤中 1 分鐘分時資料。可能是非交易日（週末、國定假日）或查詢日期過久。")
    st.stop()

# ══════════════════════════════════════════════════════════
# 頂部資訊列：股票名稱、現價、開高低量（完全還原圖一）
# ══════════════════════════════════════════════════════════
first_p = float(df_m['Open'].iloc[0])
last_p  = float(df_m['Close'].iloc[-1])
high_p  = float(df_m['High'].max())
low_p   = float(df_m['Low'].min())
tot_lot = int(round(df_m['Vol_Lots'].sum()))
price_chg = last_p - first_p
pct_chg = (price_chg / first_p * 100) if first_p else 0.0
p_color = color_for_change(price_chg)
arrow = "▲" if price_chg > 0 else "▼" if price_chg < 0 else "➖"

col_head_l, col_head_r = st.columns([1.5, 2.5])
with col_head_l:
    st.markdown(
        f"<div style='display:flex; align-items:baseline; gap:10px; flex-wrap:wrap;'>"
        f"<span style='font-size:26px; font-weight:bold; color:#FAFAFA;'>{stock_name}</span>"
        f"<span style='font-size:20px; color:#94A3B8; font-weight:bold;'>({stock_code})</span>"
        f"<span style='font-size:30px; font-weight:bold; color:{p_color};'>NT$ {last_p:,.2f}</span>"
        f"<span style='font-size:19px; font-weight:bold; color:{p_color};'>{arrow} {abs(price_chg):,.2f} ({pct_chg:+.2f}%)</span>"
        f"</div>",
        unsafe_allow_html=True
    )
with col_head_r:
    st.markdown(
        f"<div style='display:flex; justify-content:flex-end; align-items:center; gap:16px; margin-top:6px; font-size:17px;'>"
        f"<span>開 <b style='color:#FAFAFA;'>{first_p:,.2f}</b></span>"
        f"<span>高 <b style='color:#e53935;'>{high_p:,.2f}</b></span>"
        f"<span>低 <b style='color:#43a047;'>{low_p:,.2f}</b></span>"
        f"<span>量 <b style='color:#FFD700;'>{tot_lot:,} 張</b></span>"
        f"<span style='font-size:14.5px; color:#94A3B8; background:#1E293B; padding:2px 8px; border-radius:6px;'>{broker_data.get('source', '自動同步')}</span>"
        f"</div>",
        unsafe_allow_html=True
    )

st.divider()

# ══════════════════════════════════════════════════════════
# 主畫面雙欄版面（左側 68% 走勢足跡大圖，右側 32% 分點排行榜）
# ══════════════════════════════════════════════════════════
col_chart, col_brokers = st.columns([2.2, 1.0])

# 右側：當日分點排行榜與搜尋過濾
with col_brokers:
    st.subheader("🏛 當日分點（點選看足跡）")

    # 搜尋分點輸入框
    search_broker = st.text_input("🔍 搜尋分點（例：凱基、城中、元大）", value="", placeholder="輸入關鍵字過濾分點...", key="broker_filter_input")

    buyers = broker_data.get('buyers', [])
    sellers = broker_data.get('sellers', [])

    if search_broker.strip():
        k_word = search_broker.strip()
        buyers = [b for b in buyers if k_word in b['name']]
        sellers = [s for s in sellers if k_word in s['name']]

    # 建立分點下拉選單選項
    all_broker_names = list(dict.fromkeys([b['name'] for b in buyers] + [s['name'] for s in sellers]))
    if not all_broker_names:
        all_broker_names = ["無符合分點"]

    # 預設選中第一個買方或第一個賣方主力
    def_broker = all_broker_names[0]
    # 若有凱基-城中優先示範（貼近圖一）
    for b_n in all_broker_names:
        if '凱基' in b_n or '城中' in b_n:
            def_broker = b_n
            break

    selected_broker = st.selectbox(
        "🎯 選擇要追蹤足跡的分點：",
        options=all_broker_names,
        index=all_broker_names.index(def_broker) if def_broker in all_broker_names else 0,
        key="active_broker_picker"
    )

    # 取得目前選取分點的買均價與賣均價
    active_buy_info = next((b for b in broker_data.get('buyers', []) if b['name'] == selected_broker), None)
    active_sell_info = next((s for s in broker_data.get('sellers', []) if s['name'] == selected_broker), None)

    cur_buy_p = active_buy_info['buy_price'] if active_buy_info else 0.0
    cur_sell_p = active_sell_info['sell_price'] if active_sell_info else 0.0
    cur_buy_vol = active_buy_info['buy_lots'] if active_buy_info else 0
    cur_sell_vol = active_sell_info['sell_lots'] if active_sell_info else 0

    st.markdown(
        f"<div class='metric-card' style='margin-bottom:10px; border-left:4px solid #FFD700;'>"
        f"<div style='font-size:17.5px; font-weight:bold; color:#FFD700; margin-bottom:4px;'>📌 目前追蹤：{selected_broker}</div>"
        f"<div style='display:flex; justify-content:space-between; font-size:15.5px;'>"
        f"<span>買進: <b style='color:#e53935;'>{cur_buy_vol:,} 張</b> (均價: {cur_buy_p:,.2f})</span>"
        f"<span>賣出: <b style='color:#43a047;'>{cur_sell_vol:,} 張</b> (均價: {cur_sell_p:,.2f})</span>"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True
    )

    tab_b, tab_s = st.tabs([f"🔴 買方分點 ({len(buyers)})", f"🟢 賣方分點 ({len(sellers)})"])

    with tab_b:
        if buyers:
            b_rows = []
            for b in buyers[:25]:
                is_active = (b['name'] == selected_broker)
                active_style = "background:rgba(255,215,0,0.15); font-weight:bold;" if is_active else ""
                b_rows.append(
                    f"<tr style='border-bottom:1px solid #263044; {active_style}'>"
                    f"<td style='padding:6px 4px; color:#94A3B8;'>{b.get('rank', '-')}</td>"
                    f"<td style='padding:6px 4px; font-weight:bold;'>{b['name']}</td>"
                    f"<td style='padding:6px 4px; text-align:right; color:#e53935; font-weight:bold;'>{b['buy_lots']:,}</td>"
                    f"<td style='padding:6px 4px; text-align:right;'>{b['buy_price']:,.2f}</td>"
                    f"</tr>"
                )
            st.markdown(
                f"<div style='max-height:360px; overflow-y:auto; border:1px solid #263044; border-radius:6px;'>"
                f"<table style='width:100%; border-collapse:collapse; font-size:15px;'>"
                f"<thead style='background:#1E293B; color:#94A3B8; position:sticky; top:0;'>"
                f"<tr><th style='padding:6px 4px; text-align:left;'>#</th><th style='padding:6px 4px; text-align:left;'>分點名稱</th>"
                f"<th style='padding:6px 4px; text-align:right;'>買進張數↓</th><th style='padding:6px 4px; text-align:right;'>買均價</th></tr>"
                f"</thead><tbody>{''.join(b_rows)}</tbody></table></div>",
                unsafe_allow_html=True
            )
        else:
            st.info("無買方分點資料")

    with tab_s:
        if sellers:
            s_rows = []
            for s in sellers[:25]:
                is_active = (s['name'] == selected_broker)
                active_style = "background:rgba(255,215,0,0.15); font-weight:bold;" if is_active else ""
                s_rows.append(
                    f"<tr style='border-bottom:1px solid #263044; {active_style}'>"
                    f"<td style='padding:6px 4px; color:#94A3B8;'>{s.get('rank', '-')}</td>"
                    f"<td style='padding:6px 4px; font-weight:bold;'>{s['name']}</td>"
                    f"<td style='padding:6px 4px; text-align:right; color:#43a047; font-weight:bold;'>{s['sell_lots']:,}</td>"
                    f"<td style='padding:6px 4px; text-align:right;'>{s['sell_price']:,.2f}</td>"
                    f"</tr>"
                )
            st.markdown(
                f"<div style='max-height:360px; overflow-y:auto; border:1px solid #263044; border-radius:6px;'>"
                f"<table style='width:100%; border-collapse:collapse; font-size:15px;'>"
                f"<thead style='background:#1E293B; color:#94A3B8; position:sticky; top:0;'>"
                f"<tr><th style='padding:6px 4px; text-align:left;'>#</th><th style='padding:6px 4px; text-align:left;'>分點名稱</th>"
                f"<th style='padding:6px 4px; text-align:right;'>賣出張數↓</th><th style='padding:6px 4px; text-align:right;'>賣均價</th></tr>"
                f"</thead><tbody>{''.join(s_rows)}</tbody></table></div>",
                unsafe_allow_html=True
            )
        else:
            st.info("無賣方分點資料")

# 左側：分時走勢與主力足跡大圖
with col_chart:
    c_ctrl1, c_ctrl2, c_ctrl3 = st.columns([1.5, 1.2, 1.3])
    with c_ctrl1:
        st.markdown(f"<div style='font-size:20px; font-weight:bold; color:#FFD54F; padding-top:6px;'>📈 單日走勢 ── 追蹤【{selected_broker}】足跡</div>", unsafe_allow_html=True)
    with c_ctrl2:
        chk_vwap = st.checkbox("顯示市場均價線 (VWAP)", value=True)
    with c_ctrl3:
        chk_footprint = st.checkbox("顯示主力進出場足跡色帶", value=True)

    # 計算分點分時推估足跡
    footprint = match_broker_footprint(
        df_intraday=df_m,
        buy_price=cur_buy_p,
        sell_price=cur_sell_p,
        buy_lots=cur_buy_vol,
        sell_lots=cur_sell_vol
    )

    fig_fp = create_intraday_footprint_chart(
        df_m=df_m,
        broker_name=selected_broker if selected_broker != "無符合分點" else None,
        buy_price=cur_buy_p,
        sell_price=cur_sell_p,
        footprint=footprint,
        show_vwap=chk_vwap,
        show_footprint=chk_footprint
    )

    st.plotly_chart(
        fig_fp,
        use_container_width=True,
        config={'displayModeBar': False, 'scrollZoom': False, 'doubleClick': False}
    )

    st.markdown(
        f"<div class='footprint-legend'>"
        f"<span><b style='color:#FF5252;'>▲ 紅色階梯帶</b>：{selected_broker} 可能買進吃貨時段</span>"
        f"<span><b style='color:#69F0AE;'>▼ 綠色階梯帶</b>：{selected_broker} 可能逢高倒貨時段</span>"
        f"<span><b style='color:#CBD5E1;'>--- 白色虛線</b>：全市場成交量加權平均價 (VWAP)</span>"
        f"<span><b style='color:#FFD700;'>🔥 金色柱狀</b>：盤中特大單爆量點火時段</span>"
        f"</div>",
        unsafe_allow_html=True
    )

st.divider()

# ══════════════════════════════════════════════════════════
# 白話教學卡片：如何看懂隔日沖手法？
# ══════════════════════════════════════════════════════════
with st.expander("📖 30 秒看懂「隔日沖大戶手法與分點足跡」實戰教學", expanded=False):
    st.markdown("""
    ### 🎯 隔日沖主力大戶（如凱基台北、凱基城中、元大總公司）常見手法解密：
    1. **早盤急拉點火（買在均價線之上）**：
       - 主力通常在 **09:00 ~ 09:30** 使用大單連敲（如圖中的特大單 🔥），快速把股價拉過市場均價（VWAP）甚至攻上漲停。
       - **走勢特徵**：早盤出現密集 **▲ 紅色階梯帶**，且下方成交量柱爆出大單。
    2. **盤中鎖碼鎖漲停**：
       - 主力在漲停價附近掛出巨量買單排隊，吸引市場散戶追單。
    3. **隔日早盤倒貨（賣在均價線之上）**：
       - 隔天開盤，主力趁著散戶激情追價時，在開盤前 15 分鐘將昨日買進的籌碼全數市價倒出獲利了結。
       - **走勢特徵**：若某天某分點同時有大量賣出，且賣均價高於買均價，走勢圖上會呈現 **▼ 綠色階梯帶**。
    4. **成本防守線（金色買均價線）**：
       - 只要當前股價維持在該主力分點的「買均價」之上，代表主力目前處於獲利狀態；若跌破買均價，則主力可能被套牢或面臨停損賣壓。
    """)
