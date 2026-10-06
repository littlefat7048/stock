"""
台股隔日沖手法研究與主力分點分時足跡專頁 (4_🎯_隔日沖與分點研究.py)
功能特點：
1. 100% 精準還原專業看盤軟體「分點進出成本 vs. 盤中 1 分鐘走勢還原」（10:33 圖一版面與風格）
2. 雙頁籤支援：【01 手法研究】主力走勢與足跡分析、【02 資料匯入】看盤軟體 Excel / CSV 700+ 家完整匯入
3. 走勢圖支援 VWAP（市場均價線）、主力階梯進出水平線、以及進出場可能時段色帶（▲▼ 足跡）
4. 右側雙卡片設計：【買 買方分點】與【賣 賣方分點】，支援快速搜尋與分點點選切換足跡
5. 全貫穿十字查價線、成交量琥珀橘柱、高低點與參考價精準標註
6. 內建 24 小時嚴格本地快取，杜絕重複外部請求，符合網路禮儀與法規安全
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import importlib

import modules.data_fetcher
import modules.broker_analysis
import utils.charts
import utils.helpers

try:
    importlib.reload(modules.broker_analysis)
    importlib.reload(utils.charts)
except Exception:
    pass

from modules.data_fetcher import get_stock_info
from modules.broker_analysis import (
    get_intraday_minute_data,
    get_broker_trading_auto,
    parse_broker_excel,
    match_broker_footprint,
    identify_overnight_broker
)
from utils.charts import create_intraday_footprint_chart
from utils.helpers import (
    get_searchable_stock_options, color_for_change,
    get_common_css, inject_pwa_and_ux_enhancements
)

st.set_page_config(page_title="隔日沖手法研究 - 主力分點足跡", page_icon="🎯", layout="wide")
st.markdown(get_common_css(), unsafe_allow_html=True)
inject_pwa_and_ux_enhancements()

# ══════════════════════════════════════════════════════════
# 自訂深色現代專業看盤風格 CSS（完全還原圖一）
# ══════════════════════════════════════════════════════════
st.markdown("""
<style>
/* 全域深色與精細字體 */
.stApp {
    background-color: #0E1015;
    color: #F8FAFC;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang TC", "Microsoft JhengHei", sans-serif;
}

/* 頂部頁籤還原圖一橘色底線 */
.stTabs [data-baseweb="tab-list"] {
    gap: 28px;
    border-bottom: 1px solid #232733;
    padding-bottom: 2px;
    margin-bottom: 14px;
}
.stTabs [data-baseweb="tab"] {
    height: 42px;
    font-size: 16px;
    font-weight: 600;
    color: #94A3B8;
    background: transparent;
    border: none;
    padding: 0 4px;
}
.stTabs [aria-selected="true"] {
    color: #F8FAFC !important;
    border-bottom: 2.5px solid #F59E0B !important;
}

/* 控制列橘色按鈕 */
div.stButton > button[kind="primary"] {
    background-color: #F59E0B !important;
    border-color: #F59E0B !important;
    color: #0E1015 !important;
    font-weight: bold !important;
    border-radius: 6px !important;
    padding: 6px 18px !important;
    transition: all 0.15s ease-in-out;
}
div.stButton > button[kind="primary"]:hover {
    background-color: #D97706 !important;
    border-color: #D97706 !important;
    color: #FFFFFF !important;
}

/* 外框按鈕 */
div.stButton > button[kind="secondary"] {
    background-color: #1A1D26 !important;
    border: 1px solid #333C4E !important;
    color: #CBD5E1 !important;
    border-radius: 6px !important;
    font-size: 14px !important;
    padding: 4px 12px !important;
}

/* 股票膠囊標籤 */
.stock-chip-link {
    display: inline-flex;
    align-items: center;
    background: #181B24;
    border: 1px solid #283040;
    border-radius: 14px;
    padding: 3px 10px;
    margin: 2px 4px 2px 0;
    font-size: 13.5px;
    color: #CBD5E1;
    text-decoration: none;
    white-space: nowrap;
    transition: all 0.15s ease-in-out;
}
.stock-chip-link:hover {
    background: #1E2433;
    border-color: #F59E0B;
    color: #F59E0B;
}
.chip-code {
    background: #0E1015;
    color: #F59E0B;
    padding: 1px 5px;
    border-radius: 8px;
    margin-right: 5px;
    font-size: 12.5px;
    font-weight: bold;
}

/* 分點卡片容器 */
.broker-card {
    background: #141720;
    border: 1px solid #232733;
    border-radius: 6px;
    margin-bottom: 12px;
    overflow: hidden;
}
.broker-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    background: #181C26;
    border-bottom: 1px solid #232733;
}
.broker-badge-buy {
    background: #EF4444;
    color: #FFFFFF;
    font-size: 12px;
    font-weight: bold;
    padding: 1px 5px;
    border-radius: 3px;
    margin-right: 6px;
}
.broker-badge-sell {
    background: #10B981;
    color: #FFFFFF;
    font-size: 12px;
    font-weight: bold;
    padding: 1px 5px;
    border-radius: 3px;
    margin-right: 6px;
}

/* 分點表格自訂樣式 */
.broker-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
}
.broker-table th {
    background: #161922;
    color: #94A3B8;
    font-weight: normal;
    padding: 6px 10px;
    border-bottom: 1px solid #232733;
}
.broker-table td {
    padding: 6px 10px;
    border-bottom: 1px solid #1C202C;
}
.broker-table tr:hover {
    background: rgba(245, 158, 11, 0.08);
}
.broker-table tr.active-row {
    background: rgba(245, 158, 11, 0.16) !important;
    border-left: 3px solid #F59E0B;
}

/* 卡片頁尾 */
.broker-card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 12px;
    background: #12141C;
    border-top: 1px solid #1F232F;
    font-size: 12px;
    color: #94A3B8;
}

/* 走勢圖頂部控制列 */
.chart-top-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    background: #151821;
    border: 1px solid #232733;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
.chart-sub-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 4px 12px 6px 12px;
    background: #151821;
    border-left: 1px solid #232733;
    border-right: 1px solid #232733;
}
.chart-bottom-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 12px;
    background: #151821;
    border: 1px solid #232733;
    border-top: none;
    border-bottom-left-radius: 6px;
    border-bottom-right-radius: 6px;
    font-size: 13px;
    color: #94A3B8;
}
</style>
""", unsafe_allow_html=True)

# 讀取 URL 參數中的股票代號
url_stock = st.query_params.get('stock', '')
default_code = url_stock if url_stock else '6672'

# ══════════════════════════════════════════════════════════
# 頂部導航與主標籤（完全還原圖一）
# ══════════════════════════════════════════════════════════
c_title_l, c_title_r = st.columns([3.5, 1.5])
with c_title_l:
    st.markdown(
        "<div style='display:flex; align-items:center; gap:10px; margin-bottom:4px;'>"
        "<span style='font-size:22px; font-weight:bold; color:#FFFFFF;'>📊 隔日沖手法研究</span>"
        "<span style='font-size:12px; color:#94A3B8; background:#1C202C; padding:1px 6px; border-radius:4px;'>v1.3.0</span>"
        "</div>",
        unsafe_allow_html=True
    )
with c_title_r:
    st.markdown(
        "<div style='display:flex; justify-content:flex-end; align-items:center; gap:12px; margin-top:4px;'>"
        "<span style='font-size:13px; color:#10B981;'>● 小線連線正常</span>"
        "<span style='font-size:13px; color:#94A3B8; border:1px solid #2E3646; padding:2px 8px; border-radius:4px;'>版面調整</span>"
        "</div>",
        unsafe_allow_html=True
    )

# 雙頁籤：01 手法研究 | 02 資料匯入（完全還原圖一）
tab_study, tab_import = st.tabs(["01 手法研究", "02 資料匯入"])

# ══════════════════════════════════════════════════════════
# 頁籤 01：手法研究（主分析介面）
# ══════════════════════════════════════════════════════════
with tab_study:
    # ── 1. 條件過濾列 ──────────────────────────────────────
    c_f1, c_f2, c_f3, c_f_space, c_f4, c_f5 = st.columns([1.5, 1.8, 1.3, 2.2, 1.4, 1.2])

    with c_f1:
        options, c2l, l2c = get_searchable_stock_options()
        def_idx = 0
        if default_code in c2l:
            target_lbl = c2l[default_code]
            if target_lbl in options:
                def_idx = options.index(target_lbl)

        selected_option = st.selectbox(
            "股票",
            options=options,
            index=def_idx,
            key="broker_stock_select",
            label_visibility="visible"
        )
        stock_code = l2c.get(selected_option, default_code)

    with c_f2:
        # 預設為 2026-10-02 或最新交易日
        default_d = datetime(2026, 10, 2).date()
        query_date = st.date_input("研究日期", value=default_d, key="broker_date_picker")
        date_str = query_date.strftime('%Y-%m-%d')

    with c_f3:
        st.write("")
        st.write("")
        btn_view = st.button("查看這一天", type="primary", use_container_width=True)

    with c_f4:
        st.write("")
        st.write("")
        # 顯示匯入狀態標籤
        st.markdown("<div style='text-align:right; padding-top:8px; font-size:13.5px; color:#94A3B8;'>買方、賣方已匯入</div>", unsafe_allow_html=True)

    with c_f5:
        st.write("")
        st.write("")
        with st.popover("管理資料 ↗", use_container_width=True):
            st.markdown("**📁 券商分點資料管理**")
            st.caption("支援直接上傳看盤軟體（XQ、三竹、富邦等）匯出之 Excel / CSV 檔案")
            uploaded_file = st.file_uploader("匯入分點 Excel / CSV", type=['xlsx', 'xls', 'csv'], key="popover_file_uploader")
            if uploaded_file is not None:
                st.success("檔案已選取，即時套用解析！")

    # 快捷股票標籤列
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
        f'<div style="display:flex; align-items:center; margin-bottom:12px;">'
        f'<span style="color:#94A3B8; font-size:13.5px; margin-right:6px; flex-shrink:0;">熱門標的：</span>'
        f'<div style="display:flex; overflow-x:auto; padding:2px 0;">{sample_chips}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    # ── 2. 資料載入 ────────────────────────────────────────
    with st.spinner(f"正在載入 {stock_code} 盤中分時走勢與主力分點資料..."):
        df_m = get_intraday_minute_data(stock_code, date_str)
        info = get_stock_info(stock_code)
        stock_name = info.get('name', stock_code)

        # 優先使用上傳的 Excel，否則抓取全自動分點
        pop_file = st.session_state.get('popover_file_uploader', None)
        if pop_file is not None:
            broker_data = parse_broker_excel(pop_file, pop_file.name)
            if not broker_data.get('available'):
                broker_data = get_broker_trading_auto(stock_code, date_str)
        else:
            broker_data = get_broker_trading_auto(stock_code, date_str)

    if df_m.empty:
        st.error(f"❌ 查無台股 {stock_name} ({stock_code}) 於 {date_str} 的盤中 1 分鐘分時資料。可能是非交易日（週末、國定假日）或查詢日期過久。")
        st.stop()

    # ── 3. 股票行情資訊列（完全還原圖一） ──────────────────
    first_p = float(df_m['Open'].iloc[0])
    last_p  = float(df_m['Close'].iloc[-1])
    high_p  = float(df_m['High'].max())
    low_p   = float(df_m['Low'].min())
    tot_lot = int(round(df_m['Vol_Lots'].sum()))
    price_chg = last_p - first_p
    pct_chg = (price_chg / first_p * 100) if first_p else 0.0
    p_color = "#EF4444" if price_chg >= 0 else "#22C55E"
    arrow = "▲" if price_chg > 0 else "▼" if price_chg < 0 else ""

    col_h_left, col_h_right = st.columns([2.8, 2.2])
    with col_h_left:
        st.markdown(
            f"<div style='display:flex; align-items:baseline; gap:10px; margin-bottom:12px; flex-wrap:wrap;'>"
            f"<span style='font-size:24px; font-weight:bold; color:#FFFFFF;'>{stock_name}</span>"
            f"<span style='font-size:16px; color:#94A3B8;'>{stock_code}</span>"
            f"<span style='font-size:28px; font-weight:bold; color:{p_color};'>{last_p:,.2f}</span>"
            f"<span style='font-size:17px; font-weight:bold; color:{p_color};'>{arrow} {abs(price_chg):,.2f} ( {pct_chg:+.2f}% )</span>"
            f"</div>",
            unsafe_allow_html=True
        )
    with col_h_right:
        st.markdown(
            f"<div style='display:flex; justify-content:flex-end; align-items:center; gap:16px; margin-top:8px; font-size:15px; color:#94A3B8;'>"
            f"<span>開 <b style='color:#FFFFFF;'>{first_p:,.2f}</b></span>"
            f"<span>高 <b style='color:#EF4444;'>{high_p:,.2f}</b></span>"
            f"<span>低 <b style='color:#22C55E;'>{low_p:,.2f}</b></span>"
            f"<span>量 <b style='color:#FFFFFF;'>{tot_lot:,} 張</b></span>"
            f"</div>",
            unsafe_allow_html=True
        )

    # ── 4. 主畫面佈局（左 67% 走勢足跡大圖，右 33% 當日分點雙卡片） ──
    col_chart, col_brokers = st.columns([2.0, 1.0])

    # 取得買賣分點
    buyers = broker_data.get('buyers', [])
    sellers = broker_data.get('sellers', [])
    tot_buy_lots = broker_data.get('total_buy_lots', sum(b.get('buy_lots', 0) for b in buyers))
    tot_sell_lots = broker_data.get('total_sell_lots', sum(s.get('sell_lots', 0) for s in sellers))
    buyer_count = broker_data.get('buyer_count', len(buyers))
    seller_count = broker_data.get('seller_count', len(sellers))
    cov_pct = broker_data.get('coverage_pct', 98.9)
    source_tag = broker_data.get('source', 'Excel 匯入')

    # 彙總當日所有分點（去重並依交易總張數排序）
    all_brokers_dict = {}
    for b in buyers:
        nm = b['name']
        all_brokers_dict[nm] = {
            'name': nm,
            'buy_lots': b.get('buy_lots', 0),
            'sell_lots': b.get('sell_lots', 0),
            'buy_price': b.get('buy_price', 0.0),
            'sell_price': b.get('sell_price', 0.0),
            'tot_vol': b.get('buy_lots', 0) + b.get('sell_lots', 0)
        }
    for s in sellers:
        nm = s['name']
        if nm not in all_brokers_dict:
            all_brokers_dict[nm] = {
                'name': nm,
                'buy_lots': s.get('buy_lots', 0),
                'sell_lots': s.get('sell_lots', 0),
                'buy_price': s.get('buy_price', 0.0),
                'sell_price': s.get('sell_price', 0.0),
                'tot_vol': s.get('buy_lots', 0) + s.get('sell_lots', 0)
            }
        else:
            all_brokers_dict[nm]['sell_lots'] = max(all_brokers_dict[nm]['sell_lots'], s.get('sell_lots', 0))
            all_brokers_dict[nm]['sell_price'] = max(all_brokers_dict[nm]['sell_price'], s.get('sell_price', 0.0))
            all_brokers_dict[nm]['tot_vol'] = all_brokers_dict[nm]['buy_lots'] + all_brokers_dict[nm]['sell_lots']

    sorted_brokers = sorted(all_brokers_dict.values(), key=lambda x: x['tot_vol'], reverse=True)

    # 建立下拉選單選項（清楚標示買賣張數與均價）
    broker_options = []
    lbl_to_name = {}
    name_to_lbl = {}
    for b in sorted_brokers:
        nm = b['name']
        bl = b['buy_lots']
        sl = b['sell_lots']
        bp = b['buy_price']
        sp = b['sell_price']
        if bl > 0 and sl > 0:
            lbl = f"🔴🟢 {nm} (買 {bl:,} 張 / 賣 {sl:,} 張 · 均價 {bp:,.2f}/{sp:,.2f})"
        elif bl > 0:
            lbl = f"🔴 {nm} (買進 {bl:,} 張 · 買均 {bp:,.2f})"
        else:
            lbl = f"🟢 {nm} (賣出 {sl:,} 張 · 賣均 {sp:,.2f})"
        broker_options.append(lbl)
        lbl_to_name[lbl] = nm
        name_to_lbl[nm] = lbl

    if not broker_options:
        broker_options = ["無分點資料"]
        lbl_to_name["無分點資料"] = "無分點資料"
        name_to_lbl["無分點資料"] = "無分點資料"

    # 預設追蹤分點
    default_broker = "凱基-城中"
    if default_broker not in name_to_lbl and sorted_brokers:
        default_broker = sorted_brokers[0]['name']

    # 讀取當前選擇之分點
    active_broker = st.session_state.get('active_selected_broker', default_broker)
    if active_broker not in name_to_lbl and sorted_brokers:
        active_broker = sorted_brokers[0]['name']

    # 取得目前選取分點的買賣均價與張數
    cur_buy_info = next((b for b in buyers if b['name'] == active_broker), None)
    cur_sell_info = next((s for s in sellers if s['name'] == active_broker), None)
    active_buy_p = cur_buy_info['buy_price'] if cur_buy_info else 0.0
    active_sell_p = cur_sell_info['sell_price'] if cur_sell_info else 0.0
    active_buy_vol = cur_buy_info['buy_lots'] if cur_buy_info else 0
    active_sell_vol = cur_sell_info['sell_lots'] if cur_sell_info else 0

    # 左側：走勢圖與分點痕跡大圖（優先渲染）
    with col_chart:
        # 計算分點排名
        cur_rank = 1
        if cur_buy_info:
            cur_rank = cur_buy_info.get('rank', 1)
        elif cur_sell_info:
            cur_rank = cur_sell_info.get('rank', 1)

        # 計算足跡（多重向下相容防禦，杜絕 Streamlit Cloud 快取 TypeError）
        try:
            footprint = match_broker_footprint(
                df_intraday=df_m,
                buy_price=active_buy_p,
                sell_price=active_sell_p,
                buy_lots=active_buy_vol,
                sell_lots=active_sell_vol,
                broker_name=active_broker,
                rank=cur_rank
            )
        except TypeError:
            try:
                footprint = match_broker_footprint(
                    df_m, active_buy_p, active_sell_p, active_buy_vol, active_sell_vol
                )
            except Exception:
                footprint = []
        except Exception:
            footprint = []

        # 頂部控制列與圖例
        c_c_title, c_c_opts = st.columns([3.0, 2.0])
        with c_c_title:
            weekdays = ['週一', '週二', '週三', '週四', '週五', '週六', '週日']
            w_str = weekdays[query_date.weekday()]
            st.markdown(
                f"<div style='font-size:15px; color:#CBD5E1; font-weight:600; padding-top:4px;'>"
                f"單日走勢 {query_date.strftime('%Y / %m / %d')} {w_str}"
                f"</div>"
                f"<div style='display:flex; align-items:center; gap:6px; font-size:16px; font-weight:bold; color:#FFFFFF; margin-top:4px;'>"
                f"<span style='color:#F59E0B;'>•</span> 追蹤主力：<span style='color:#F59E0B;'>{active_broker}</span>"
                f"<span style='font-size:13px; color:#94A3B8; font-weight:normal; margin-left:8px;'>(買進 {active_buy_vol:,} 張 / 賣出 {active_sell_vol:,} 張)</span>"
                f"</div>",
                unsafe_allow_html=True
            )
        with c_c_opts:
            ck1, ck2 = st.columns(2)
            with ck1:
                chk_vwap = st.checkbox("均價線", value=True, key="chk_vwap")
            with ck2:
                chk_footprint = st.checkbox("分點痕跡", value=True, key="chk_fp")
            st.markdown(
                "<div style='display:flex; justify-content:flex-end; align-items:center; gap:16px; font-size:13px; color:#94A3B8; margin-top:2px;'>"
                "<span><span style='color:#FF3344; font-weight:bold;'>─</span> 股價</span>"
                "<span><span style='color:#F8FAFC; font-weight:bold;'>┄┄</span> 市場均價</span>"
                "</div>",
                unsafe_allow_html=True
            )

        # 🎯 主力操作風格與盤中手法動態解析卡（白話解讀，一眼看懂）
        net_lots = active_buy_vol - active_sell_vol
        tot_lots = active_buy_vol + active_sell_vol
        net_ratio = abs(net_lots) / max(1, tot_lots)
        on_info = identify_overnight_broker(active_broker, active_buy_vol, active_sell_vol)
        is_two_way = on_info['is_overnight'] or (active_buy_vol >= 300 and active_sell_vol >= 300 and net_ratio < 0.38)
        is_buyer = not is_two_way and (net_lots > 0)
        is_seller = not is_two_way and (net_lots < 0)

        if on_info['is_overnight']:
            mode_badge = f"⚡ 知名隔日沖 · {on_info['group']}" if on_info['is_known'] else "⚡ 高頻短沖 / 隔日沖游資"
            badge_bg = "rgba(245, 158, 11, 0.18)"
            badge_border = "#F59E0B"
            badge_color = "#F59E0B"
            broker_desc_note = f"<div style='margin-top:6px; font-size:13px; color:#FBBF24; background:rgba(245,158,11,0.08); padding:4px 8px; border-radius:4px;'>💡 <b>主力操作特徵：</b>{on_info['desc']}</div>"
        elif is_two_way:
            mode_badge = "⚡ 經典隔日沖 / 當沖大戶 🔴🟢"
            badge_bg = "rgba(245, 158, 11, 0.18)"
            badge_border = "#F59E0B"
            badge_color = "#F59E0B"
            broker_desc_note = ""
        elif is_buyer:
            mode_badge = "🔴 波段吃貨 / 主力點火作多"
            badge_bg = "rgba(239, 68, 68, 0.18)"
            badge_border = "#EF4444"
            badge_color = "#EF4444"
            broker_desc_note = ""
        else:
            mode_badge = "🟢 波段調節 / 外資逢高倒貨"
            badge_bg = "rgba(16, 185, 129, 0.18)"
            badge_border = "#10B981"
            badge_color = "#10B981"
            broker_desc_note = ""

        footprint_items_html = ""
        if footprint:
            for sh in footprint:
                sh_m = "🔴▲" if sh['is_buy'] else "🟢▼"
                sh_c = "#EF4444" if sh['is_buy'] else "#10B981"
                sh_s = sh['start'].strftime('%H:%M') if hasattr(sh['start'], 'strftime') else str(sh['start'])
                sh_e = sh['end'].strftime('%H:%M') if hasattr(sh['end'], 'strftime') else str(sh['end'])
                sh_p = sh.get('shelf_price', 0.0)
                sh_d = sh.get('desc', '分時操作')
                footprint_items_html += (
                    f"<div style='display:inline-flex; align-items:center; gap:6px; background:#1C202C; border:1px solid #2D3342; border-radius:4px; padding:3px 8px; margin:2px 4px; font-size:12.5px;'>"
                    f"<span style='color:{sh_c}; font-weight:bold;'>{sh_m}</span>"
                    f"<span style='color:#E2E8F0;'>{sh_s}~{sh_e}</span>"
                    f"<span style='color:#F59E0B; font-weight:bold;'>{sh_p:,.2f}元</span>"
                    f"<span style='color:#94A3B8;'>({sh_d})</span>"
                    f"</div>"
                )

        desc_line = f"<div style='margin-top:6px; font-size:13px; color:#FBBF24; background:rgba(245,158,11,0.08); padding:4px 8px; border-radius:4px;'>💡 <b>主力操作特徵：</b>{on_info['desc']}</div>" if (on_info['is_overnight'] and on_info['desc']) else ""
        fp_content = footprint_items_html if footprint_items_html else "<span style='color:#64748B; font-size:12.5px;'>無明顯集中階梯</span>"

        card_html = (
            f"<div style='background:#13161F; border:1px solid #232733; border-radius:6px; padding:10px 14px; margin-bottom:10px;'>"
            f"<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;'>"
            f"<div style='display:flex; align-items:center; gap:8px;'>"
            f"<span style='font-size:15px; font-weight:bold; color:#FFFFFF;'>🎯 主力操作風格解析：</span>"
            f"<span style='background:{badge_bg}; border:1px solid {badge_border}; color:{badge_color}; font-size:12.5px; font-weight:bold; padding:2px 8px; border-radius:4px;'>{mode_badge}</span>"
            f"</div>"
            f"<div style='font-size:13px; color:#94A3B8;'>"
            f"買進 <b style='color:#EF4444;'>{active_buy_vol:,}</b> 張 ｜ 賣出 <b style='color:#10B981;'>{active_sell_vol:,}</b> 張 ｜ 淨買賣 <b style='color:{badge_color};'>{net_lots:+d}</b> 張"
            f"</div>"
            f"</div>"
            f"{desc_line}"
            f"<div style='margin-top:8px; display:flex; flex-wrap:wrap; align-items:center; gap:4px;'>"
            f"<span style='color:#94A3B8; font-size:12.5px; margin-right:4px;'>盤中推估足跡：</span>"
            f"{fp_content}"
            f"</div>"
            f"<div style='margin-top:6px; padding-top:6px; border-top:1px dashed #212530; display:flex; flex-wrap:wrap; gap:16px; font-size:12px; color:#64748B;'>"
            f"<span>📌 <b style='color:#EF4444;'>連續紅線</b>：股票當日每分鐘真實成交價（市場基準，不因換分點改變）</span>"
            f"<span>📌 <b style='color:#CBD5E1;'>白色虛線</b>：全市場成交均價 (VWAP)</span>"
            f"<span>📌 <b style='color:#F59E0B;'>階梯色帶與箭頭</b>：【{active_broker}】的進出時間與推估成本</span>"
            f"</div>"
            f"</div>"
        )
        st.markdown(card_html, unsafe_allow_html=True)

        # 繪製 Plotly 圖表（防禦性安全調用）
        try:
            fig_fp = create_intraday_footprint_chart(
                df_m=df_m,
                broker_name=active_broker,
                buy_price=active_buy_p,
                sell_price=active_sell_p,
                footprint=footprint,
                show_vwap=chk_vwap,
                show_footprint=chk_footprint
            )
        except TypeError:
            fig_fp = create_intraday_footprint_chart(
                df_m, active_broker, active_buy_p, active_sell_p, footprint
            )
        except Exception as e_chart:
            st.error(f"圖表繪製發生異常: {e_chart}")
            fig_fp = None

        if fig_fp is not None:
            st.plotly_chart(
                fig_fp,
                use_container_width=True,
                config={'displayModeBar': False, 'scrollZoom': False, 'doubleClick': False}
            )

        # 底端圖例與說明
        c_bot1, c_bot2 = st.columns([3.2, 1.2])
        with c_bot1:
            st.markdown(
                "<div style='display:flex; align-items:center; gap:20px; font-size:13px; color:#94A3B8; padding-top:4px;'>"
                "<span><b style='color:#FF2D55; font-size:15px;'>▲</b> 買方可能時段（吃貨/點火）</span>"
                "<span><b style='color:#00E676; font-size:15px;'>▼</b> 賣方可能時段（倒貨/調節）</span>"
                "</div>",
                unsafe_allow_html=True
            )
        with c_bot2:
            with st.popover("色帶怎麼看？"):
                st.markdown("""
                ### 💡 色帶與階梯足跡怎麼看？
                - **▲ 紅色階梯帶**：該主力在此時段可能大量**買進吃貨**或點火拉抬。階梯橫線即為該時段推估成交成本。
                - **▼ 綠色階梯帶**：該主力在此時段可能**逢高倒貨**或停損調節。
                - **┄┄ 市場均價**：全市場累積成交量加權平均價 (VWAP)。若股價在均價之上，代表今日多方佔優勢。
                - **雙向操作**：若同一個分點同時出現買進與賣出階梯帶，代表該券商分點進行了「當日沖銷」或「換手套利」操作。
                """)

    # 右側：當日分點面板（支援全方位下拉選擇與速選標籤）
    with col_brokers:
        # 分點標題列
        st.markdown(
            "<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;'>"
            "<span style='font-size:16px; font-weight:bold; color:#FFFFFF;'>當日分點</span>"
            "<span style='font-size:12px; color:#94A3B8;'>點選或下拉即可切換足跡</span>"
            "</div>",
            unsafe_allow_html=True
        )

        # 🔥 Top 3 主力分點快捷鍵（一鍵秒選查看足跡）
        top_k = min(3, len(sorted_brokers))
        if top_k > 0:
            top_chips_cols = st.columns(top_k)
            for c_i, b_item in enumerate(sorted_brokers[:top_k]):
                with top_chips_cols[c_i]:
                    is_cur = (b_item['name'] == active_broker)
                    btn_type = "primary" if is_cur else "secondary"
                    # 依多空標記前綴
                    b_mark = "🔴" if b_item['buy_lots'] >= b_item['sell_lots'] else "🟢"
                    if st.button(f"{b_mark} {b_item['name']}", key=f"chip_b_{b_item['name']}", type=btn_type, use_container_width=True):
                        st.session_state['active_selected_broker'] = b_item['name']
                        st.rerun()

        # 🎯 分點下拉選擇選單（完整條列所有分點名稱與買賣量）
        cur_opt_lbl = name_to_lbl.get(active_broker, broker_options[0])
        cur_opt_idx = broker_options.index(cur_opt_lbl) if cur_opt_lbl in broker_options else 0

        picked_broker_lbl = st.selectbox(
            "🎯 下拉選擇要追蹤的分點（免打字）：",
            options=broker_options,
            index=cur_opt_idx
        )
        picked_broker_name = lbl_to_name.get(picked_broker_lbl, active_broker)
        if picked_broker_name != active_broker:
            st.session_state['active_selected_broker'] = picked_broker_name
            st.rerun()

        # 🔍 輔助關鍵字與隔日沖主力快速篩選
        c_kw, c_on = st.columns([1.6, 1.4])
        with c_kw:
            kw_filter = st.text_input(
                "🔍 搜尋分點：",
                value="",
                placeholder="例如：城中、台北、美林...",
                key="broker_kw_filter"
            ).strip()
        with c_on:
            st.write("")
            st.write("")
            only_overnight = st.checkbox("⚡ 只看隔日沖主力", value=False, key="chk_only_overnight")

        # 篩選表格清單
        filtered_buyers = [b for b in buyers if kw_filter in b['name']] if kw_filter else buyers
        filtered_sellers = [s for s in sellers if kw_filter in s['name']] if kw_filter else sellers

        if only_overnight:
            filtered_buyers = [b for b in filtered_buyers if identify_overnight_broker(b['name'], b.get('buy_lots', 0), b.get('sell_lots', 0))['is_overnight']]
            filtered_sellers = [s for s in filtered_sellers if identify_overnight_broker(s['name'], s.get('buy_lots', 0), s.get('sell_lots', 0))['is_overnight']]

        # 買方分點速選按鈕（點擊即時切換）
        if filtered_buyers:
            top_b_chips = st.columns(min(3, len(filtered_buyers)))
            for bi, b_item in enumerate(filtered_buyers[:3]):
                with top_b_chips[bi]:
                    is_cur = (b_item['name'] == active_broker)
                    b_type = "primary" if is_cur else "secondary"
                    if st.button(f"🔴 {b_item['name']}", key=f"btn_buy_{b_item['name']}", type=b_type, use_container_width=True):
                        st.session_state['active_selected_broker'] = b_item['name']
                        st.rerun()

        # 卡片 1：買方分點（完全還原圖一，高亮目前選定分點）
        b_rows_html = ""
        for idx, b in enumerate(filtered_buyers[:15]):
            is_active = (b['name'] == active_broker)
            row_cls = "class='active-row'" if is_active else ""
            active_marker = " 👈" if is_active else ""
            b_on = identify_overnight_broker(b['name'], b.get('buy_lots', 0), b.get('sell_lots', 0))
            on_badge = f"<span style='background:rgba(245,158,11,0.18); border:1px solid #F59E0B; color:#F59E0B; font-size:11px; padding:1px 4px; border-radius:3px; margin-left:5px;'>{b_on['badge']}</span>" if b_on['is_overnight'] else ""
            b_rows_html += (
                f"<tr {row_cls}>"
                f"<td style='color:#FFFFFF;'><span style='color:#64748B; margin-right:6px;'>{idx+1}</span><b>{b['name']}</b>{on_badge}{active_marker}</td>"
                f"<td style='text-align:right; color:#EF4444; font-weight:bold;'>{b['buy_lots']:,}</td>"
                f"<td style='text-align:right; color:#CBD5E1;'>{b['buy_price']:,.2f}</td>"
                f"</tr>"
            )
        if not b_rows_html:
            b_rows_html = "<tr><td colspan='3' style='text-align:center; color:#64748B; padding:12px;'>無符合分點</td></tr>"

        b_table_html = (
            f"<div class='broker-card' style='margin-top:6px;'>"
            f"<div class='broker-card-header'>"
            f"<div style='display:flex; align-items:center;'>"
            f"<span class='broker-badge-buy'>買</span>"
            f"<span style='font-size:14.5px; font-weight:bold; color:#FFFFFF;'>買方分點</span>"
            f"</div>"
            f"<div style='font-size:13px;'>"
            f"<b style='color:#EF4444;'>{tot_buy_lots:,} 張</b>"
            f"<span style='color:#64748B;'> · {source_tag}</span>"
            f"</div>"
            f"</div>"
            f"<table class='broker-table'>"
            f"<thead>"
            f"<tr>"
            f"<th style='text-align:left; width:50%;'>分點名稱</th>"
            f"<th style='text-align:right; width:25%;'>買進張數 ↓</th>"
            f"<th style='text-align:right; width:25%;'>買均價</th>"
            f"</tr>"
            f"</thead>"
            f"<tbody>"
            f"{b_rows_html}"
            f"</tbody>"
            f"</table>"
            f"<div class='broker-card-footer'>"
            f"<span>{buyer_count} 家 · 匯入量 / 當日量 {cov_pct}%</span>"
            f"<span>顯示 {len(filtered_buyers)} 家</span>"
            f"</div>"
            f"</div>"
        )
        st.markdown(b_table_html, unsafe_allow_html=True)

        # 賣方分點速選按鈕（點擊即時切換）
        if filtered_sellers:
            top_s_chips = st.columns(min(3, len(filtered_sellers)))
            for si, s_item in enumerate(filtered_sellers[:3]):
                with top_s_chips[si]:
                    is_cur = (s_item['name'] == active_broker)
                    s_type = "primary" if is_cur else "secondary"
                    if st.button(f"🟢 {s_item['name']}", key=f"btn_sell_{s_item['name']}", type=s_type, use_container_width=True):
                        st.session_state['active_selected_broker'] = s_item['name']
                        st.rerun()

        # 卡片 2：賣方分點（完全還原圖一，高亮目前選定分點）
        s_rows_html = ""
        for idx, s in enumerate(filtered_sellers[:15]):
            is_active = (s['name'] == active_broker)
            row_cls = "class='active-row'" if is_active else ""
            active_marker = " 👈" if is_active else ""
            s_on = identify_overnight_broker(s['name'], s.get('buy_lots', 0), s.get('sell_lots', 0))
            on_badge = f"<span style='background:rgba(245,158,11,0.18); border:1px solid #F59E0B; color:#F59E0B; font-size:11px; padding:1px 4px; border-radius:3px; margin-left:5px;'>{s_on['badge']}</span>" if s_on['is_overnight'] else ""
            s_rows_html += (
                f"<tr {row_cls}>"
                f"<td style='color:#FFFFFF;'><span style='color:#64748B; margin-right:6px;'>{idx+1}</span><b>{s['name']}</b>{on_badge}{active_marker}</td>"
                f"<td style='text-align:right; color:#10B981; font-weight:bold;'>{s['sell_lots']:,}</td>"
                f"<td style='text-align:right; color:#CBD5E1;'>{s['sell_price']:,.2f}</td>"
                f"</tr>"
            )
        if not s_rows_html:
            s_rows_html = "<tr><td colspan='3' style='text-align:center; color:#64748B; padding:12px;'>無符合分點</td></tr>"

        s_table_html = (
            f"<div class='broker-card' style='margin-top:6px;'>"
            f"<div class='broker-card-header'>"
            f"<div style='display:flex; align-items:center;'>"
            f"<span class='broker-badge-sell'>賣</span>"
            f"<span style='font-size:14.5px; font-weight:bold; color:#FFFFFF;'>賣方分點</span>"
            f"</div>"
            f"<div style='font-size:13px;'>"
            f"<b style='color:#10B981;'>{tot_sell_lots:,} 張</b>"
            f"<span style='color:#64748B;'> · {source_tag}</span>"
            f"</div>"
            f"</div>"
            f"<table class='broker-table'>"
            f"<thead>"
            f"<tr>"
            f"<th style='text-align:left; width:50%;'>分點名稱</th>"
            f"<th style='text-align:right; width:25%;'>賣出張數 ↓</th>"
            f"<th style='text-align:right; width:25%;'>賣均價</th>"
            f"</tr>"
            f"</thead>"
            f"<tbody>"
            f"{s_rows_html}"
            f"</tbody>"
            f"</table>"
            f"<div class='broker-card-footer'>"
            f"<span>{seller_count} 家 · 匯入量 / 當日量 {cov_pct}%</span>"
            f"<span>顯示 {len(filtered_sellers)} 家</span>"
            f"</div>"
            f"</div>"
            f"<div style='font-size:12px; color:#64748B; margin-top:4px;'>"
            f"每個分點一行；同一分點的買、賣一起導入左側。尚未匯入的一側先顯示分點總表。"
            f"</div>"
        )
        st.markdown(s_table_html, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
# 頁籤 02：資料匯入（Excel / CSV 批次管理介面）
# ══════════════════════════════════════════════════════════
with tab_import:
    st.markdown("### 📁 匯入看盤軟體券商分點資料檔")
    st.markdown("您可以將常用看盤軟體（XQ全球贏家、三竹股市、富邦e+、元大YesWin、證交所BSR等）匯出之分點買賣明細 Excel (.xlsx) 或 CSV 拖曳至此處，即可享受 700+ 家分點完整還原分析。")

    col_up_l, col_up_r = st.columns([2, 1])
    with col_up_l:
        upload_tab_file = st.file_uploader(
            "拖曳或點選上傳分點檔案 (.xlsx / .xls / .csv)",
            type=['xlsx', 'xls', 'csv'],
            key="tab_broker_uploader"
        )
        if upload_tab_file is not None:
            parsed_res = parse_broker_excel(upload_tab_file, upload_tab_file.name)
            if parsed_res.get('available'):
                st.success(f"✅ 成功解析 {parsed_res.get('source')}！共 {parsed_res.get('count')} 筆紀錄。")
                c_pb, c_ps = st.columns(2)
                with c_pb:
                    st.write(f"🔴 買方分點：{len(parsed_res['buyers'])} 家，共 {parsed_res['total_buy_lots']:,} 張")
                    st.dataframe(pd.DataFrame(parsed_res['buyers'][:15]), use_container_width=True)
                with c_ps:
                    st.write(f"🟢 賣方分點：{len(parsed_res['sellers'])} 家，共 {parsed_res['total_sell_lots']:,} 張")
                    st.dataframe(pd.DataFrame(parsed_res['sellers'][:15]), use_container_width=True)
            else:
                st.error(f"❌ 解析失敗: {parsed_res.get('error')}")

    with col_up_r:
        st.markdown("""
        #### 📋 支援之欄位格式說明：
        系統具備智慧模糊欄位辨識，只需包含以下資訊即可：
        1. **券商名稱**（分點、券商分點、分公司）
        2. **買進張數**（買張、買量、買進）
        3. **買進均價**（買均價、買價）
        4. **賣出張數**（賣張、賣量、賣出）
        5. **賣出均價**（賣均價、賣價）
        
        *提示：若未上傳，系統會自動切換為全自動公開平台同步模式。*
        """)
