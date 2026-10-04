"""
台股個股全方位深度分析頁面
包含：
- 頂部：中文股名、即時報價、買賣/觀望評價、建議買進價位/目標價/停損價、優缺點速覽
- 分頁 1：📊 技術面（全中文訊號 + 互動式 K 線、均線、MACD、KD、RSI）
- 分頁 2：🏛 籌碼面（外資/投信/自營商買賣超、連買連賣、融資融券、券資比）
- 分頁 3：💹 基本面（PE/PB/殖利率估值判讀、獲利三率、盤後報告亮點）
- 分頁 4：📋 財報分析（近12月營收 YoY/MoM 圖表、近8季 EPS 與毛利/營益/淨利率圖表）
- 分頁 5：🤖 AI 深度評語（Gemini 3.8 Flash 操盤策略與目標價分析）
- 分頁 6：🏭 產業生態（概念股定位、同概念夥伴、同產業競爭公司比較）
"""
import importlib
import streamlit as st
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import utils.helpers
import utils.charts
import modules.data_fetcher
import modules.technical_analysis
import modules.chip_analysis
import modules.ai_analysis

importlib.reload(utils.helpers)
importlib.reload(utils.charts)
importlib.reload(modules.data_fetcher)
importlib.reload(modules.technical_analysis)
importlib.reload(modules.chip_analysis)
importlib.reload(modules.ai_analysis)

from modules.data_fetcher import (
    get_stock_info, get_price_history, get_financials,
    get_daily_report_commentary_for_stock, build_business_and_profit_analysis
)
from modules.technical_analysis import (
    calculate_indicators, get_technical_score,
    get_ma_trend, get_macd_signal, get_kd_signal, get_rsi_signal,
    find_support_resistance, generate_instant_diagnosis
)
from modules.chip_analysis import (
    get_institutional_trend, get_margin_trading,
    get_chip_score, get_chip_summary,
    calculate_chip_intensity, calculate_mofi_institutional_series,
    get_day_trading_analysis
)
from modules.ai_analysis import generate_stock_analysis, get_gemini_model
from utils.helpers import (
    resolve_stock_query, get_tw_stock_chinese_info, get_peer_stocks,
    format_price, color_for_change, load_concept_data,
    get_concept_tags_for_stock, get_concept_details_for_stock,
    load_watchlist, save_watchlist
)
from utils.charts import (
    create_candlestick_chart, create_macd_chart, create_kd_chart,
    create_rsi_chart, create_institutional_chart, create_margin_chart,
    create_eps_chart, create_revenue_chart, create_mofi_institutional_force_chart,
    create_day_trading_chart
)

from utils.helpers import get_common_css, get_top_nav_html

st.set_page_config(page_title='台股個股深度分析', page_icon='📊', layout='wide')

# ── 注入自訂繁體中文與手機響應式樣式及頂部導覽列 ──────────
st.markdown(get_common_css(), unsafe_allow_html=True)
st.markdown(get_top_nav_html('stock'), unsafe_allow_html=True)

# ── 股票代號或中文名稱輸入區 ──────────────────────────────
if 'target_stock' in st.session_state and st.session_state['target_stock']:
    default_query = str(st.session_state['target_stock']).strip()
    st.session_state['target_stock'] = ''
else:
    default_query = st.query_params.get('stock', '2330')

st.markdown("<div style='font-size:18px; font-weight:bold; color:#00D4AA; margin-bottom:2px;'>🔍 輸入台股代號或中文股名查詢：</div>", unsafe_allow_html=True)
col_input, col_btn = st.columns([3.6, 1.4])
with col_input:
    raw_input = st.text_input(
        "🔍 輸入台股代號或中文股名",
        value=default_query,
        placeholder="點此輸入：例如 2221、大甲、5484、慧友、2330、台積電",
        label_visibility="collapsed"
    )
with col_btn:
    search_btn = st.button("🚀 立即分析", use_container_width=True)

# 熱門速選晶片（手機左右滑動，點擊直達）
quick_samples = [('2330', '台積電'), ('2221', '大甲'), ('5484', '慧友'), ('6515', '穎崴'), ('2317', '鴻海'), ('2454', '聯發科'), ('2382', '廣達')]
sample_chips = "".join([
    f'<a href="/?stock={qcode}" target="_self" class="stock-chip-link">'
    f'<span class="chip-code">{qcode}</span>{qname}</a>'
    for qcode, qname in quick_samples
])
st.markdown(
    f'<div style="display:flex; align-items:center; margin-bottom:6px;">'
    f'<span style="color:#94A3B8; font-size:17px; margin-right:6px; flex-shrink:0;">熱門：</span>'
    f'<div class="chips-scroll-bar" style="margin:0; padding:2px 0;">{sample_chips}</div>'
    f'</div>',
    unsafe_allow_html=True
)

if search_btn or raw_input:
    # 將中文名稱或代號統一轉為標準台股代號
    stock_code = resolve_stock_query(raw_input)
    st.query_params['stock'] = stock_code

    with st.spinner(f"正在載入台股 {stock_code} 完整基本面、公司業務、技術面、法人力度、當沖率與財報資料..."):
        info       = get_stock_info(stock_code)
        df_price   = get_price_history(stock_code, period='1y')
        chip_df    = get_institutional_trend(stock_code, days=65)
        margin_df  = get_margin_trading(stock_code, days=25)
        financials = get_financials(stock_code)
        concepts   = load_concept_data()
        report_cmt = get_daily_report_commentary_for_stock(stock_code)
        concept_details = get_concept_details_for_stock(stock_code, concepts)
        biz_analysis = build_business_and_profit_analysis(info, financials, report_cmt, concept_details)
        day_trading  = get_day_trading_analysis(stock_code, df_price=df_price, days=40)

    if df_price is None or df_price.empty:
        st.error(f"❌ 找不到台股代號「{raw_input}」（解析為 {stock_code}）的股價資料，請確認輸入的台股代號或中文名稱是否正確。")
        st.stop()

    # 取得最新價格與漲跌
    latest_close = float(df_price['Close'].iloc[-1])
    prev_close   = float(df_price['Close'].iloc[-2]) if len(df_price) > 1 else latest_close
    price_change = latest_close - prev_close
    pct_change   = (price_change / prev_close * 100) if prev_close else 0.0
    latest_date_str = df_price.index[-1].strftime('%Y/%m/%d') if hasattr(df_price.index[-1], 'strftime') else str(df_price.index[-1])[:10]

    # 計算技術指標與籌碼分數（含雙層過濾「法人力度 / 顯著買超」）
    df_price = calculate_indicators(df_price)
    tech_score, tech_label = get_technical_score(df_price)
    support_resistance = find_support_resistance(df_price)
    chip_score, chip_label = get_chip_score(chip_df, info=info, latest_close=latest_close)
    chip_summary = get_chip_summary(chip_df, margin_df, info=info, latest_close=latest_close)

    # 計算即時綜合診斷（買進/觀望/賣出 + 建議價位 + 優缺點）
    diagnosis = generate_instant_diagnosis(df_price, info, chip_score, chip_summary, financials)

    # 確保中文名稱顯示
    stock_name = info.get('name', stock_code)
    market_str = info.get('market', '上市')
    sector_str = info.get('sector', '台股產業')

    # ══════════════════════════════════════════════════════════
    # 1. 頂部標題列：中文名稱 + 市場別 + 產業別 + 即時股價
    # ══════════════════════════════════════════════════════════
    col_title, col_watch = st.columns([3.6, 1.4])
    with col_title:
        price_color = color_for_change(price_change)
        arrow = "▲" if price_change > 0 else "▼" if price_change < 0 else "➖"
        st.markdown(
            f"<div style='margin-bottom:2px; display:flex; align-items:center; flex-wrap:wrap; gap:6px;'>"
            f"<span style='font-size:28px; font-weight:bold; color:#FAFAFA;'>🇹🇼 {stock_name}</span>"
            f"<span style='color:#94A3B8; font-size:23px; font-weight:bold;'>({stock_code})</span>"
            f"<span class='market-badge'>{market_str}</span>"
            f"<span class='sector-badge'>{sector_str}</span>"
            f"</div>"
            f"<div style='margin-bottom:4px; display:flex; align-items:baseline; flex-wrap:wrap; gap:8px;'>"
            f"<span style='font-size:32px; font-weight:bold; color:{price_color}'>NT$ {latest_close:,.2f}</span>"
            f"<span style='font-size:21px; font-weight:bold; color:{price_color}'>{arrow} {abs(price_change):,.2f} ({pct_change:+.2f}%)</span>"
            f"<span style='color:#888; font-size:16.5px;'>基準：{latest_date_str}</span>"
            f"</div>",
            unsafe_allow_html=True
        )

        stock_concepts = get_concept_tags_for_stock(stock_code, concepts)
        rel_ind_tags = [t for t in (biz_analysis.get('related_industries') or []) if t not in stock_concepts]
        combined_badges = (
            [f"<span class='concept-tag'>🏷️ {t}</span>" for t in stock_concepts] +
            [f"<span class='concept-tag' style='background:rgba(56,189,248,0.14);border-color:#38BDF8;color:#7DD3FC;'>🏭 {t}</span>" for t in rel_ind_tags[:5]]
        )
        if combined_badges:
            st.markdown(f"<div style='margin-bottom:2px; display:flex; flex-wrap:wrap; gap:4px;'>{''.join(combined_badges)}</div>", unsafe_allow_html=True)

    with col_watch:
        watchlist = load_watchlist()
        in_watch = any(s.get('code') == stock_code for s in watchlist)
        btn_label = "⭐ 已在自選" if in_watch else "☆ 加入自選"
        if st.button(btn_label, use_container_width=True):
            if not in_watch:
                watchlist.append({'code': stock_code, 'name': stock_name, 'note': ''})
                save_watchlist(watchlist)
                st.toast(f"✅ 已將 {stock_name} 加入自選股！")
            else:
                watchlist = [s for s in watchlist if s.get('code') != stock_code]
                save_watchlist(watchlist)
                st.toast(f"已將 {stock_name} 從自選股移除")
            st.rerun()

    st.divider()

    # ══════════════════════════════════════════════════════════
    # 1.5 公司做什麼的？靠什麼賺錢？（一分鐘白話看懂卡片）
    # ══════════════════════════════════════════════════════════
    st.subheader(f"🏢 {stock_name} ({stock_code}) 是做什麼的？為什麼會賺錢？")

    # 產品營收比重水平視覺條
    rev_mix_items = biz_analysis.get('revenue_mix_items') or []
    bar_colors = ['#00D4AA', '#38BDF8', '#F59E0B', '#EC4899', '#A855F7', '#94A3B8']
    if rev_mix_items:
        stacked_seg_html = "".join([
            f"<div style='width:{max(2.0, it['pct'])}%; background:{bar_colors[i % len(bar_colors)]}; height:10px;' title='{it['name']} {it['pct']}%'></div>"
            for i, it in enumerate(rev_mix_items)
        ])
        legend_pills_html = "".join([
            f"<span style='display:inline-flex;align-items:center;gap:4px;font-size:17px;color:#E2E8F0;margin-right:10px;'>"
            f"<span style='width:8px;height:8px;border-radius:50%;background:{bar_colors[i % len(bar_colors)]};display:inline-block;'></span>"
            f"<b>{it['name']}</b> <span style='color:{bar_colors[i % len(bar_colors)]};font-weight:bold;'>{it['pct']:.2f}%</span></span>"
            for i, it in enumerate(rev_mix_items)
        ])
        rev_mix_block = (
            f"<div style='margin-top:8px; padding-top:8px; border-top:1px solid #263044;'>"
            f"<div style='color:#94A3B8; font-size:17px; margin-bottom:4px;'>🥧 <b>靠什麼產品賺錢（主力營收比重結構）：</b></div>"
            f"<div style='display:flex; width:100%; border-radius:6px; overflow:hidden; margin-bottom:6px; background:#1E293B;'>{stacked_seg_html}</div>"
            f"<div style='display:flex; flex-wrap:wrap; gap:4px;'>{legend_pills_html}</div>"
            f"</div>"
        )
    elif biz_analysis.get('revenue_mix_raw'):
        rev_mix_block = (
            f"<div style='margin-top:8px; padding-top:8px; border-top:1px solid #263044; font-size:18px;'>"
            f"🥧 <b>主力營收比重：</b>{biz_analysis['revenue_mix_raw']}"
            f"</div>"
        )
    else:
        rev_mix_block = ""

    why_profit_items_html = "".join([
        f"<li style='margin:5px 0; line-height:1.55;'>{pt}</li>"
        for pt in (biz_analysis.get('why_profitable') or [])
    ])

    st.markdown(
        f"<div class='info-card' style='border-left:4px solid #00D4AA; padding:12px 14px; margin-bottom:8px;'>"
        f"<div style='font-size:19px; line-height:1.6; color:#F8FAFC;'>"
        f"🛠️ <b>公司核心業務（做什麼的）：</b>{biz_analysis.get('one_liner', '')}"
        f"</div>"
        f"{rev_mix_block}"
        f"<div style='margin-top:8px; padding-top:8px; border-top:1px solid #263044;'>"
        f"<div style='color:#FFD54F; font-weight:bold; font-size:18px; margin-bottom:4px;'>💰 為什麼會賺錢？近期獲利與成長動能白話解析：</div>"
        f"<ul style='margin:0; padding-left:18px; font-size:18px; color:#E2E8F0;'>{why_profit_items_html}</ul>"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True
    )

    st.divider()

    # ══════════════════════════════════════════════════════════
    # 2. 綜合評價（買進/賣出/等待）、建議價位、優缺點速覽
    # ══════════════════════════════════════════════════════════
    st.subheader("🎯 綜合評價與操作建議")

    btype = diagnosis['badge_type']
    css_cls = 'rating-buy' if btype == 'buy' else ('rating-watch' if btype == 'watch' else 'rating-sell')

    col_eval, col_prices = st.columns([1.2, 2.8])
    with col_eval:
        st.markdown(
            f"<div class='info-card' style='text-align:center; padding:12px 10px; margin-bottom:6px;'>"
            f"<div style='color:#94A3B8;font-size:17px;margin-bottom:4px;'>目前綜合評價</div>"
            f"<div class='{css_cls}'>{diagnosis['action']}</div>"
            f"<div style='margin-top:10px;font-size:19px;'>"
            f"評分：<b style='color:#00D4AA;font-size:23px;'>{diagnosis['total_score']}</b> / 100"
            f"</div>"
            f"<div style='color:#94A3B8;font-size:16.5px;margin-top:4px;'>"
            f"技術 {diagnosis['tech_score']}分 ｜ 籌碼 {diagnosis['chip_score']}分 ｜ 基本 {diagnosis['fund_score']}分"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True
        )

    with col_prices:
        # 手機並排 3 欄關鍵價位區
        st.markdown(
            f"<div style='display:grid; grid-template-columns: repeat(3, 1fr); gap:6px; margin-bottom:6px;'>"
            f"<div class='price-box' style='padding:8px 6px; text-align:center;'>"
            f"<div style='color:#94A3B8;font-size:16.5px;'>💰 建議買進</div>"
            f"<div style='color:#00D4AA;font-size:20px;font-weight:bold;margin-top:2px;'>{diagnosis['buy_zone']}</div>"
            f"<div style='color:#888;font-size:15.5px;margin-top:2px;'>支撐：{diagnosis['support']:,.1f}</div>"
            f"</div>"
            f"<div class='price-box' style='border-left-color:#e53935; padding:8px 6px; text-align:center;'>"
            f"<div style='color:#94A3B8;font-size:16.5px;'>🚀 目標價</div>"
            f"<div style='color:#e53935;font-size:20px;font-weight:bold;margin-top:2px;'>{diagnosis['target_price']}</div>"
            f"<div style='color:#888;font-size:15.5px;margin-top:2px;'>壓力：{diagnosis['resistance']:,.1f}</div>"
            f"</div>"
            f"<div class='price-box' style='border-left-color:#43a047; padding:8px 6px; text-align:center;'>"
            f"<div style='color:#94A3B8;font-size:16.5px;'>🛑 停損價</div>"
            f"<div style='color:#43a047;font-size:20px;font-weight:bold;margin-top:2px;'>{diagnosis['stop_loss']}</div>"
            f"<div style='color:#888;font-size:15.5px;margin-top:2px;'>防守線</div>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True
        )

        st.markdown(
            f"<div class='info-card' style='padding:8px 12px; margin-bottom:6px; font-size:18px;'>"
            f"💡 <b>操作建議：</b>{diagnosis['advice']}"
            f"</div>",
            unsafe_allow_html=True
        )

    # 優缺點雙欄速覽
    pros_items = "".join([f"<li style='margin:3px 0;'>{s}</li>" for s in diagnosis['strengths']])
    cons_items = "".join([f"<li style='margin:3px 0;'>{r}</li>" for r in diagnosis['risks']])
    col_pros, col_cons = st.columns(2)
    with col_pros:
        st.markdown(
            f"<div class='pro-box'>"
            f"<div style='color:#FF8A80;font-weight:bold;font-size:18px;margin-bottom:4px;'>👍 多方優勢與亮點</div>"
            f"<ul style='margin:0;padding-left:18px;font-size:18px;'>{pros_items}</ul>"
            f"</div>",
            unsafe_allow_html=True
        )
    with col_cons:
        st.markdown(
            f"<div class='con-box'>"
            f"<div style='color:#81C784;font-weight:bold;font-size:18px;margin-bottom:4px;'>⚠️ 潛在風險與注意事項</div>"
            f"<ul style='margin:0;padding-left:18px;font-size:18px;'>{cons_items}</ul>"
            f"</div>",
            unsafe_allow_html=True
        )

    st.divider()

    # ══════════════════════════════════════════════════════════
    # 3. 六大深度分析分頁
    # ══════════════════════════════════════════════════════════
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 技術面分析",
        "🏛 籌碼面分析",
        "💹 基本面與估值",
        "📋 財報與營收",
        "🤖 AI 深度評語",
        "🏭 產業生態與同業"
    ])

    PLOTLY_CFG = {
        'displayModeBar': False,
        'scrollZoom': False,
        'doubleClick': False,
        'displaylogo': False
    }

    MOFI_TUTORIAL_HTML = (
        "<div style='background:#141E30; border:1px solid #38BDF8; border-radius:10px; padding:12px 15px; margin:6px 0 10px 0; font-size:17.5px; line-height:1.7;'>"
        "<div style='color:#FFD600; font-weight:bold; font-size:19px; margin-bottom:6px;'>📖 30 秒看懂「法人力度 (2026 版)」圖表 5 大符號教學：</div>"
        "<ul style='margin:0; padding-left:20px; color:#F8FAFC;'>"
        "<li><b>🔴 紅柱 / 🟢 綠柱（三大法人力度 %）</b>：代表當天法人買賣超<b>「佔整間公司總股本的百分比」</b>（右側座標軸）。"
        "紅柱往上＝法人買超（例如 <code>+2.0%</code> 代表一天買走公司 2% 股本！）；綠柱往下＝法人賣超。</li>"
        "<li><b>🟡 亮黃色大圓球（顯著買超 ── 最重要的進場信號！）</b>：當某天紅柱突然衝高，系統算出來<b>比過去 20 天平均高出 1.5~2 個標準差（Z-Score）</b>，就會在紅柱頂端打上一顆 <b>🟡 大黃球</b>！"
        "代表這天不是散戶小買，而是<b>「法人主力真正在點火大買、鎖碼拉抬」</b>！</li>"
        "<li><b>⚪ 白色實線（近期動向 10MA） vs ⚪ 白色虛線（長期基準 40MA）</b>："
        "白色實線是「近 10 天平均買超力道」，白色虛線是「過去 40 天長期平均基準」。"
        "當<b>白色實線向上穿過白色虛線</b>，代表近期法人買盤比過去兩個月都還要強！</li>"
        "<li><b>🟩 中間零軸上的「亮綠 / 橄欖黃小方塊」</b>："
        "只要看到中間 `0.0%` 虛線上出現<b>一排綠色或黃色小方塊</b>，就代表目前正處於<b>「短線買盤 ＞ 長線基準」的法人偏多吸籌期</b>！</li>"
        "<li><b>🔍 想要放大看最近幾天？</b>畫面已鎖定防滑動誤觸，點擊 K 線任一根可查看當日數據，您可直接點選上方的<b>「近2週(極大) / 近1月(放大)」</b>按鈕一鍵切換！</li>"
        "</ul></div>"
    )

    # ── Tab 1：📊 技術面分析 ───────────────────────────────
    with tab1:
        # 1. 頂部：免點圖表直接看！「最新交易日完整四價、成交量、均線與技術指標數值看板」
        last_row = df_price.iloc[-1]
        open_p  = float(last_row.get('Open', latest_close))
        high_p  = float(last_row.get('High', latest_close))
        low_p   = float(last_row.get('Low', latest_close))
        vol_lot = int(round(float(last_row.get('Volume', 0)) / 1000.0))
        ma5_v   = float(last_row.get('MA5', 0) or 0)
        ma10_v  = float(last_row.get('MA10', 0) or 0)
        ma20_v  = float(last_row.get('MA20', 0) or 0)
        ma60_v  = float(last_row.get('MA60', 0) or 0)
        k_v     = float(last_row.get('K', 0) or 0)
        d_v     = float(last_row.get('D', 0) or 0)
        dif_v   = float(last_row.get('MACD', 0) or 0)
        macd_v  = float(last_row.get('Signal', 0) or 0)
        osc_v   = float(last_row.get('Hist', 0) or 0)
        rsi_v   = float(last_row.get('RSI', 0) or 0)

        dt_ratio = day_trading.get('latest_ratio', 0.0) if day_trading else 0.0
        dt_lots = day_trading.get('latest_dt_lots', 0) if day_trading else 0
        dt_color = day_trading.get('heat_color', '#FFD700') if day_trading else '#FFD700'

        st.markdown(
            f"<div class='info-card' style='border-left:4px solid #38BDF8; padding:10px 12px; margin-bottom:8px;'>"
            f"<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; margin-bottom:6px;'>"
            f"<span style='color:#38BDF8; font-weight:bold; font-size:18.5px;'>📌 最新交易日（{latest_date_str}）詳細數據一覽（免點圖表直接看）</span>"
            f"<span style='color:#94A3B8; font-size:16.5px;'>🔒 畫面已固定防誤觸滑動（點擊 K 棒可看詳細數值）</span>"
            f"</div>"
            f"<div style='display:grid; grid-template-columns: repeat(auto-fit, minmax(115px, 1fr)); gap:6px; font-size:17.5px;'>"
            f"<div style='background:#161F30; padding:6px 8px; border-radius:6px;'>"
            f"<div style='color:#94A3B8; font-size:16.5px;'>📊 當日四價</div>"
            f"<div>開 <b>{open_p:,.2f}</b> ｜ 高 <b style='color:#e53935;'>{high_p:,.2f}</b><br>低 <b style='color:#43a047;'>{low_p:,.2f}</b> ｜ 收 <b style='color:{price_color};'>{latest_close:,.2f}</b></div>"
            f"</div>"
            f"<div style='background:#161F30; padding:6px 8px; border-radius:6px;'>"
            f"<div style='color:#94A3B8; font-size:16.5px;'>📏 均線位置 (MA)</div>"
            f"<div>5日 <b style='color:#FFD700;'>{ma5_v:,.2f}</b> ｜ 10日 <b style='color:#FF80AB;'>{ma10_v:,.2f}</b><br>20日 <b style='color:#00E5FF;'>{ma20_v:,.2f}</b> ｜ 60日 <b style='color:#FF9100;'>{ma60_v:,.2f}</b></div>"
            f"</div>"
            f"<div style='background:#161F30; padding:6px 8px; border-radius:6px;'>"
            f"<div style='color:#94A3B8; font-size:16.5px;'>⚡ KD / RSI / 量</div>"
            f"<div>K <b style='color:#FFD700;'>{k_v:.1f}</b> / D <b style='color:#00E5FF;'>{d_v:.1f}</b> ｜ RSI <b>{rsi_v:.1f}</b><br>成交量：<b>{vol_lot:,} 張</b></div>"
            f"</div>"
            f"<div style='background:#161F30; padding:6px 8px; border-radius:6px;'>"
            f"<div style='color:#94A3B8; font-size:16.5px;'>🌊 MACD 指標</div>"
            f"<div>DIF <b style='color:#00E5FF;'>{dif_v:.2f}</b> ｜ MACD <b style='color:#FF80AB;'>{macd_v:.2f}</b><br>柱狀(OSC)：<b style='color:{'#e53935' if osc_v>=0 else '#43a047'};'>{osc_v:+.2f}</b></div>"
            f"</div>"
            f"<div style='background:#161F30; padding:6px 8px; border-radius:6px;'>"
            f"<div style='color:#94A3B8; font-size:16.5px;'>⚡ 當沖交易指標</div>"
            f"<div>當沖率：<b style='color:{dt_color};'>{dt_ratio:.1f}%</b><br>當沖量：<b>{dt_lots:,} 張</b></div>"
            f"</div>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True
        )

        # 2. 外部專業看盤一鍵跳轉列（Yahoo股市 / 玩股網 / Goodinfo / HiStock）
        st.markdown(
            f"<div style='display:flex; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:8px;'>"
            f"<span style='color:#94A3B8; font-size:17px;'>🔗 外部專業看盤線圖：</span>"
            f"<a href='https://tw.stock.yahoo.com/quote/{stock_code}/technical-analysis' target='_blank' class='stock-chip-link' style='font-size:17px; padding:3px 9px;'>📈 Yahoo奇摩技術線圖 ↗</a>"
            f"<a href='https://www.wantgoo.com/stock/{stock_code}/technical-chart' target='_blank' class='stock-chip-link' style='font-size:17px; padding:3px 9px;'>📊 玩股網動態K線 ↗</a>"
            f"<a href='https://goodinfo.tw/tw/ShowK_Chart.asp?STOCK_ID={stock_code}&CHT_CAT=DATE' target='_blank' class='stock-chip-link' style='font-size:17px; padding:3px 9px;'>📋 Goodinfo K線圖 ↗</a>"
            f"<a href='https://histock.tw/stock/{stock_code}/%E6%8A%80%E8%A1%93%E5%88%86%E6%9E%90' target='_blank' class='stock-chip-link' style='font-size:17px; padding:3px 9px;'>📉 HiStock 技術分析 ↗</a>"
            f"</div>",
            unsafe_allow_html=True
        )

        col_sig, col_chart = st.columns([1.1, 2.9])

        with col_sig:
            st.subheader("📌 技術指標全中文判讀")
            ma_trend = get_ma_trend(df_price)
            macd_sig = get_macd_signal(df_price)
            kd_sig   = get_kd_signal(df_price)
            rsi_sig  = get_rsi_signal(df_price)

            signals_display = [
                ("均線排列 (MA)", ma_trend),
                ("MACD 趨勢動能", macd_sig),
                ("KD 隨機指標", kd_sig),
                ("RSI 強弱指標", rsi_sig),
            ]
            for label, sig_text in signals_display:
                st.markdown(
                    f"<div class='info-card'>"
                    f"<div style='color:#94A3B8;font-size:17px'>{label}</div>"
                    f"<div style='font-weight:bold;font-size:19px;margin-top:4px'>{sig_text}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            st.markdown(
                f"<div class='info-card'>"
                f"<div style='color:#94A3B8;font-size:17px;margin-bottom:6px;'>📏 各期均線目前位置</div>"
                f"<div style='font-size:18px;line-height:1.8;'>"
                f"• 5日線 (週線)：<b>{ma5_v:,.2f}</b> 元<br>"
                f"• 10日線 (雙週)：<b>{ma10_v:,.2f}</b> 元<br>"
                f"• 20日線 (月線)：<b>{ma20_v:,.2f}</b> 元<br>"
                f"• 60日線 (季線)：<b>{ma60_v:,.2f}</b> 元"
                f"</div></div>",
                unsafe_allow_html=True
            )

        with col_chart:
            c_opt1, c_opt2 = st.columns([1.4, 1.6])
            with c_opt1:
                k_range_label = st.radio(
                    "🔍 選擇 K 線顯示週期（畫面鎖定防誤觸・點擊可看數值）",
                    ["近2週(極大)", "近1月(放大)", "近3月(適中)", "近半年"],
                    index=1,
                    horizontal=True
                )
            with c_opt2:
                ma_options = st.multiselect(
                    "選擇顯示均線",
                    ['MA5', 'MA10', 'MA20', 'MA60', 'MA120', 'MA240'],
                    default=['MA5', 'MA20', 'MA60']
                )

            if "近2週" in k_range_label:
                k_bars = 12
            elif "近1月" in k_range_label:
                k_bars = 25
            elif "近3月" in k_range_label:
                k_bars = 65
            else:
                k_bars = 140

            st.plotly_chart(
                create_candlestick_chart(df_price.tail(k_bars), ma_options),
                use_container_width=True,
                config=PLOTLY_CFG
            )

            # ── 緊接在 K 線與成交量下方：@MOFI「法人力度 (2026 版)」顯著買超副圖（還原圖一配置！）──
            if chip_df is not None and not chip_df.empty:
                st.markdown(
                    "<div style='background:#131C2E; border:1px solid #263044; border-left:4px solid #FFD600; "
                    "border-radius:8px; padding:8px 12px; margin:4px 0 6px 0;'>"
                    "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:4px;'>"
                    "<span style='color:#FFD600; font-weight:bold; font-size:18.5px;'>🔥 法人力度 (2026 版) ── 雙層過濾「顯著買超(🟡)」副圖</span>"
                    "<span style='color:#94A3B8; font-size:16.5px;'>🟡 亮黃圓點＝Z-Score 突破門檻＋佔股本比顯著（法人真正在拉）｜白實線(10MA)＞白虛線(40MA)＝中期吸籌</span>"
                    "</div></div>",
                    unsafe_allow_html=True
                )
                with st.expander("📖 看不懂這張圖嗎？點此展開「30 秒看懂法人力度圖表」白話教學", expanded=False):
                    st.markdown(MOFI_TUTORIAL_HTML, unsafe_allow_html=True)

                mc_1, mc_2, mc_3 = st.columns(3)
                with mc_1:
                    t1_inv = st.selectbox(
                        "🏛 看哪個法人",
                        ["三大法人", "外資", "投信", "自營商"],
                        index=0,
                        key="t1_mofi_inv"
                    )
                with mc_2:
                    t1_denom_lbl = st.selectbox(
                        "⚖️ 標準化分母（第二層）",
                        ["佔股本比（佈局深度）", "成交力道（當日力道）"],
                        index=0,
                        key="t1_mofi_denom"
                    )
                    t1_denom = "佔股本比" if "佔股本比" in t1_denom_lbl else "成交力道"
                with mc_3:
                    t1_sens_lbl = st.selectbox(
                        "🎯 極端靈敏度（Z-Score）",
                        ["1.5σ（靈敏・提早發現）", "2.0σ（適中・標準顯著）", "2.5σ（嚴格・極端爆量）"],
                        index=1,
                        key="t1_mofi_sens"
                    )
                    t1_sens = 1.5 if "1.5" in t1_sens_lbl else (2.5 if "2.5" in t1_sens_lbl else 2.0)

                mofi_t1_df = calculate_mofi_institutional_series(
                    chip_df,
                    df_price=df_price,
                    info=info,
                    investor_type=t1_inv,
                    denom_mode=t1_denom,
                    sensitivity=t1_sens
                )
                if mofi_t1_df is not None and not mofi_t1_df.empty:
                    st.plotly_chart(
                        create_mofi_institutional_force_chart(
                            mofi_t1_df.tail(min(len(mofi_t1_df), k_bars)),
                            investor_type=t1_inv,
                            denom_mode=t1_denom,
                            sensitivity=t1_sens
                        ),
                        use_container_width=True,
                        config=PLOTLY_CFG,
                        key="t1_mofi_chart"
                    )

            sub_col1, sub_col2 = st.columns(2)
            with sub_col1:
                st.plotly_chart(create_macd_chart(df_price.tail(k_bars)), use_container_width=True, config=PLOTLY_CFG)
            with sub_col2:
                st.plotly_chart(create_kd_chart(df_price.tail(k_bars)), use_container_width=True, config=PLOTLY_CFG)

            st.plotly_chart(create_rsi_chart(df_price.tail(k_bars)), use_container_width=True, config=PLOTLY_CFG)

            # 近 10 個交易日完整價量與技術指標明細表（不用點圖表也能查每天精確數字！）
            with st.expander("📋 查看近 10 個交易日每日「開高低收、均線、KD、MACD、RSI」詳細數據表", expanded=True):
                recent_10 = df_price.tail(10).iloc[::-1].copy()
                table_rows = []
                for idx_dt, r_row in recent_10.iterrows():
                    d_label = idx_dt.strftime('%m/%d') if hasattr(idx_dt, 'strftime') else str(idx_dt)[:10]
                    table_rows.append({
                        '日期': d_label,
                        '收盤': round(float(r_row.get('Close', 0)), 2),
                        '開盤': round(float(r_row.get('Open', 0)), 2),
                        '最高': round(float(r_row.get('High', 0)), 2),
                        '最低': round(float(r_row.get('Low', 0)), 2),
                        '量(張)': int(round(float(r_row.get('Volume', 0)) / 1000.0)),
                        '5日線': round(float(r_row.get('MA5', 0) or 0), 2),
                        '20日線': round(float(r_row.get('MA20', 0) or 0), 2),
                        'K值': round(float(r_row.get('K', 0) or 0), 1),
                        'D值': round(float(r_row.get('D', 0) or 0), 1),
                        'DIF': round(float(r_row.get('MACD', 0) or 0), 2),
                        'RSI': round(float(r_row.get('RSI', 0) or 0), 1),
                    })
                st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

    # ── Tab 2：🏛 籌碼面分析 ───────────────────────────────
    with tab2:
        st.subheader(f"🏛 {stock_name} ({stock_code}) 法人力度（顯著買超）與資券籌碼分析")

        if chip_summary.get('available'):
            # ══════════════════════════════════════════════════════
            # 1. 核心亮點：「法人力度 (2026 版)」雙層過濾（標準化 Z-Score ＋ 佔股本比）
            # ══════════════════════════════════════════════════════
            imeta = chip_summary.get('intensity_meta') or {}
            if imeta.get('available'):
                sig_dates_str = "、".join(imeta.get('sig_buy_dates_20d') or []) or "近20日尚無極端買超亮燈"
                border_col = "#FFD600" if (imeta.get('is_latest_sig_buy') or imeta.get('sig_buy_count_5d', 0) >= 1) else "#00D4AA"
                st.markdown(
                    f"<div class='info-card' style='border-left:4px solid {border_col}; padding:12px 14px; margin-bottom:10px;'>"
                    f"<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px;'>"
                    f"<span style='color:#FFD600; font-weight:bold; font-size:20px;'>🔥 法人力度（顯著買超）雙層過濾診斷：{imeta.get('headline', '')}</span>"
                    f"<span style='background:#1E293B; color:#94A3B8; font-size:16.5px; padding:2px 8px; border-radius:12px;'>"
                    f"公司總股本約 {imeta.get('total_lots', 0):,} 張</span>"
                    f"</div>"
                    f"<div style='font-size:18.5px; color:#F8FAFC; line-height:1.6; margin-bottom:8px;'>"
                    f"💡 <b>為什麼不直接看買賣超張數？</b>同樣買超 1,000 張，放在大型權值股只是零頭，放在中小型股卻是重倉掃貨！"
                    f"本指標先做<b>第一層「標準化 Z-Score（跟自己過去20天比是否異常放大）」</b>，再做<b>第二層「佔股本比（相對整間公司股本份量）」</b>：<br>"
                    f"👉 <b>目前判讀：</b>{imeta.get('verdict', '')}"
                    f"</div>"
                    f"<div style='display:grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap:6px; font-size:17.5px;'>"
                    f"<div style='background:#161F30; padding:7px 9px; border-radius:6px;'>"
                    f"<div style='color:#94A3B8; font-size:16.5px;'>📏 第一層：最新標準化 Z 值</div>"
                    f"<div style='font-size:21px; font-weight:bold; color:{'#FFD600' if imeta.get('latest_z_score',0)>=1.5 else ('#e53935' if imeta.get('latest_z_score',0)>0 else '#43a047')};'>"
                    f"{imeta.get('latest_z_score', 0.0):+.2f} σ</div>"
                    f"<div style='color:#888; font-size:16px;'>≥ +1.5σ 代表異常大買</div>"
                    f"</div>"
                    f"<div style='background:#161F30; padding:7px 9px; border-radius:6px;'>"
                    f"<div style='color:#94A3B8; font-size:16.5px;'>⚖️ 第二層：單日佔股本比</div>"
                    f"<div style='font-size:21px; font-weight:bold; color:{'#e53935' if imeta.get('latest_cap_pct',0)>=0 else '#43a047'};'>"
                    f"{imeta.get('latest_cap_pct', 0.0):+.3f}%</div>"
                    f"<div style='color:#888; font-size:16px;'>外資 {imeta.get('latest_f_cap_pct',0):+.3f}%｜投本比 {imeta.get('latest_t_cap_pct',0):+.3f}%</div>"
                    f"</div>"
                    f"<div style='background:#161F30; padding:7px 9px; border-radius:6px;'>"
                    f"<div style='color:#94A3B8; font-size:16.5px;'>📦 近 5 日累計佔股本比</div>"
                    f"<div style='font-size:21px; font-weight:bold; color:{'#e53935' if imeta.get('sum5_cap_pct',0)>=0 else '#43a047'};'>"
                    f"{imeta.get('sum5_cap_pct', 0.0):+.3f}%</div>"
                    f"<div style='color:#888; font-size:16px;'>近20日累計：{imeta.get('sum20_cap_pct', 0.0):+.3f}%</div>"
                    f"</div>"
                    f"<div style='background:#161F30; padding:7px 9px; border-radius:6px;'>"
                    f"<div style='color:#94A3B8; font-size:16.5px;'>🟡 顯著買超亮燈統計</div>"
                    f"<div style='font-size:20px; font-weight:bold; color:#FFD600;'>"
                    f"近5日 {imeta.get('sig_buy_count_5d', 0)} 次 / 近20日 {imeta.get('sig_buy_count_20d', 0)} 次</div>"
                    f"<div style='color:#888; font-size:16px;'>亮燈日：{sig_dates_str}</div>"
                    f"</div>"
                    f"</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

                # 展開式白話圖表教學
                with st.expander("📖 看不懂下方「法人力度」圖表嗎？點此查看 5 大符號白話教學", expanded=True):
                    st.markdown(MOFI_TUTORIAL_HTML, unsafe_allow_html=True)

                t2_range_lbl = st.radio(
                    "🔍 選擇籌碼圖表顯示範圍（亦可直接在圖上用雙指左右放大）",
                    ["近2週(12日・極大)", "近1月(25日・放大)", "近3月(65日・完整)"],
                    index=1,
                    horizontal=True,
                    key="t2_range_radio"
                )
                t2_bars = 12 if "近2週" in t2_range_lbl else (25 if "近1月" in t2_range_lbl else 65)

                # 互動式 @MOFI 法人力度圖表控制器（Tab 2 專屬）
                c_m1, c_m2, c_m3 = st.columns(3)
                with c_m1:
                    t2_inv = st.selectbox(
                        "🏛 選擇觀察法人（投信×佔股本比＝投本比）",
                        ["三大法人", "外資", "投信", "自營商"],
                        index=0,
                        key="t2_mofi_inv"
                    )
                with c_m2:
                    t2_denom_lbl = st.selectbox(
                        "⚖️ 選擇標準化分母",
                        ["佔股本比（佈局深度）", "成交力道（當日力道）"],
                        index=0,
                        key="t2_mofi_denom"
                    )
                    t2_denom = "佔股本比" if "佔股本比" in t2_denom_lbl else "成交力道"
                with c_m3:
                    t2_sens_lbl = st.selectbox(
                        "🎯 極端買超(🟡)靈敏度門檻",
                        ["1.5σ（靈敏・提早發現）", "2.0σ（適中・標準顯著）", "2.5σ（嚴格・極端爆量）"],
                        index=1,
                        key="t2_mofi_sens"
                    )
                    t2_sens = 1.5 if "1.5" in t2_sens_lbl else (2.5 if "2.5" in t2_sens_lbl else 2.0)

                mofi_t2_df = calculate_mofi_institutional_series(
                    chip_df,
                    df_price=df_price,
                    info=info,
                    investor_type=t2_inv,
                    denom_mode=t2_denom,
                    sensitivity=t2_sens
                )
                if mofi_t2_df is not None and not mofi_t2_df.empty:
                    st.plotly_chart(
                        create_mofi_institutional_force_chart(
                            mofi_t2_df.tail(min(len(mofi_t2_df), t2_bars)),
                            investor_type=t2_inv,
                            denom_mode=t2_denom,
                            sensitivity=t2_sens
                        ),
                        use_container_width=True,
                        config=PLOTLY_CFG,
                        key="t2_mofi_chart"
                    )

            # 2. 頂部傳統籌碼統計卡片
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(
                    f"<div class='info-card'>"
                    f"<div style='color:#94A3B8;font-size:18px;'>籌碼綜合評分（含力度加成）</div>"
                    f"<div style='font-size:30px;font-weight:bold;color:#00D4AA;margin:4px 0;'>{chip_score} / 100</div>"
                    f"<div style='font-size:18px;'>{chip_label}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            with c2:
                f5 = chip_summary['foreign_5d']
                f_col = '#e53935' if f5 >= 0 else '#43a047'
                st.markdown(
                    f"<div class='info-card'>"
                    f"<div style='color:#94A3B8;font-size:18px;'>🌍 外資動向（{chip_summary['foreign_streak']}）</div>"
                    f"<div style='font-size:26px;font-weight:bold;color:{f_col};margin:4px 0;'>近5日 {f5:+,.1f} 張</div>"
                    f"<div style='font-size:17px;color:#AAA;'>最新單日：{chip_summary['foreign_1d']:+,.1f} 張 ｜ 近20日：{chip_summary['foreign_20d']:+,.1f} 張</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            with c3:
                t5 = chip_summary['trust_5d']
                t_col = '#e53935' if t5 >= 0 else '#43a047'
                st.markdown(
                    f"<div class='info-card'>"
                    f"<div style='color:#94A3B8;font-size:18px;'>🏦 投信動向（{chip_summary['trust_streak']}）</div>"
                    f"<div style='font-size:26px;font-weight:bold;color:{t_col};margin:4px 0;'>近5日 {t5:+,.1f} 張</div>"
                    f"<div style='font-size:17px;color:#AAA;'>最新單日：{chip_summary['trust_1d']:+,.1f} 張 ｜ 近20日：{chip_summary['trust_20d']:+,.1f} 張</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            with c4:
                tot5 = chip_summary['total_5d']
                tot_col = '#e53935' if tot5 >= 0 else '#43a047'
                st.markdown(
                    f"<div class='info-card'>"
                    f"<div style='color:#94A3B8;font-size:18px;'>📊 三大法人合計（{chip_summary['total_streak']}）</div>"
                    f"<div style='font-size:26px;font-weight:bold;color:{tot_col};margin:4px 0;'>近5日 {tot5:+,.1f} 張</div>"
                    f"<div style='font-size:17px;color:#AAA;'>最新單日：{chip_summary['total_1d']:+,.1f} 張 ｜ 近20日：{chip_summary['total_20d']:+,.1f} 張</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            # 三大法人買賣超張數堆疊圖表
            st.plotly_chart(
                create_institutional_chart(chip_df.tail(min(len(chip_df), t2_bars if 't2_bars' in locals() else 25))),
                use_container_width=True,
                config=PLOTLY_CFG
            )

            # 融資融券分析區
            if margin_df is not None and not margin_df.empty:
                st.markdown("#### 💳 融資融券與散戶籌碼變化")
                mc1, mc2, mc3 = st.columns(3)
                with mc1:
                    st.metric(
                        "融資餘額（散戶指標）",
                        f"{chip_summary.get('margin_balance', 0):,} 張",
                        f"最新增減 {chip_summary.get('margin_change_1d', 0):+,} 張（近5日 {chip_summary.get('margin_change_5d', 0):+,} 張）",
                        delta_color="inverse"
                    )
                with mc2:
                    st.metric(
                        "融券餘額（空單指標）",
                        f"{chip_summary.get('short_balance', 0):,} 張",
                        f"最新增減 {chip_summary.get('short_change_1d', 0):+,} 張"
                    )
                with mc3:
                    st.metric(
                        "券資比（軋空動能）",
                        f"{chip_summary.get('short_ratio', 0):.2f}%",
                        "券資比 > 30% 易有軋空行情" if chip_summary.get('short_ratio', 0) >= 30 else "正常水位"
                    )

                st.plotly_chart(create_margin_chart(margin_df), use_container_width=True, config=PLOTLY_CFG)

            # 3. ⚡ 當日沖銷（當沖）籌碼與短線熱度深度分析
            if day_trading and day_trading.get('available'):
                st.markdown("#### ⚡ 當日沖銷（當沖）籌碼與短線熱度分析")
                dt_col1, dt_col2, dt_col3, dt_col4 = st.columns(4)
                dt_r = day_trading.get('latest_ratio', 0.0)
                dt_lots = day_trading.get('latest_dt_lots', 0)
                tot_lots = day_trading.get('latest_tot_lots', 0)
                avg_5d = day_trading.get('avg_5d_ratio', 0.0)
                b_yi = day_trading.get('buy_amt_yi', 0.0)
                s_yi = day_trading.get('sell_amt_yi', 0.0)
                h_col = day_trading.get('heat_color', '#00D4AA')
                h_lvl = day_trading.get('heat_level', '')

                with dt_col1:
                    st.markdown(
                        f"<div class='info-card'>"
                        f"<div style='color:#94A3B8;font-size:17px;'>最新當沖率 (當沖比)</div>"
                        f"<div style='font-size:28px;font-weight:bold;color:{h_col};margin:3px 0;'>{dt_r:.2f}%</div>"
                        f"<div style='font-size:16px;font-weight:bold;color:{h_col};'>{h_lvl}</div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                with dt_col2:
                    st.markdown(
                        f"<div class='info-card'>"
                        f"<div style='color:#94A3B8;font-size:17px;'>當沖成交張數</div>"
                        f"<div style='font-size:26px;font-weight:bold;color:#FB923C;margin:3px 0;'>{dt_lots:,} 張</div>"
                        f"<div style='font-size:16px;color:#94A3B8;'>佔總量 {tot_lots:,} 張之 {dt_r:.1f}%</div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                with dt_col3:
                    st.markdown(
                        f"<div class='info-card'>"
                        f"<div style='color:#94A3B8;font-size:17px;'>近 5 日平均當沖率</div>"
                        f"<div style='font-size:26px;font-weight:bold;color:#38BDF8;margin:3px 0;'>{avg_5d:.2f}%</div>"
                        f"<div style='font-size:16px;color:#94A3B8;'>5日均值水準</div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                with dt_col4:
                    st.markdown(
                        f"<div class='info-card'>"
                        f"<div style='color:#94A3B8;font-size:17px;'>當日當沖金額規模</div>"
                        f"<div style='font-size:22px;font-weight:bold;color:#FAFAFA;margin:3px 0;'>買 {b_yi:.1f}億 / 賣 {s_yi:.1f}億</div>"
                        f"<div style='font-size:16px;color:#94A3B8;'>當沖資金進出總額</div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )

                st.markdown(
                    f"<div class='info-card' style='border-left:4px solid {h_col}; padding:10px 12px; margin-bottom:8px;'>"
                    f"💡 <b>當沖籌碼解讀：</b>{day_trading.get('heat_desc', '')}"
                    f"</div>",
                    unsafe_allow_html=True
                )

                dt_df = day_trading.get('df')
                if dt_df is not None and not dt_df.empty:
                    st.plotly_chart(create_day_trading_chart(dt_df), use_container_width=True, config=PLOTLY_CFG)

                    with st.expander("📋 查看近 15 日當沖成交量、當沖率與金額明細表", expanded=False):
                        show_dt = dt_df[['DateStr', 'Close', 'TotalLots', 'DayTradingLots', 'DayTradingRatio', 'BuyAmtYi', 'SellAmtYi']].tail(15).iloc[::-1].copy()
                        show_dt.columns = ['日期', '收盤價', '總量(張)', '當沖量(張)', '當沖率(%)', '當沖買額(億)', '當沖賣額(億)']
                        st.dataframe(show_dt, use_container_width=True, hide_index=True)

            # 近期法人買賣超與「法人力度（佔股本比 + Z-Score）」明細表
            with st.expander("📋 查看近 15 個交易日三大法人買賣超與「法人力度（佔股本比 / Z值）」明細表", expanded=True):
                enriched_chip_df, _ = calculate_chip_intensity(chip_df, info=info, latest_close=latest_close)
                if enriched_chip_df is not None and not enriched_chip_df.empty and '佔股本比(%)' in enriched_chip_df.columns:
                    cols_show = ['外資', '投信', '自營商', '三大法人合計', '佔股本比(%)', '投信佔股本比(%)', '標準化Z值', '力度信號']
                    cols_exist = [c for c in cols_show if c in enriched_chip_df.columns]
                    display_chip_df = enriched_chip_df[cols_exist].tail(15).iloc[::-1]
                else:
                    display_chip_df = chip_df[['外資', '投信', '自營商', '三大法人合計']].tail(15).iloc[::-1]
                st.dataframe(display_chip_df, use_container_width=True)
        else:
            st.info("此股票目前無近期三大法人買賣超明細資料。")

    # ── Tab 3：💹 基本面與估值 ─────────────────────────────
    with tab3:
        st.subheader(f"💹 {stock_name} ({stock_code}) 基本面、核心業務與獲利原因分析")

        # 1. 公司核心業務、相關產業與產品營收比重詳解
        main_biz_list = biz_analysis.get('main_business') or []
        rel_inds_list = biz_analysis.get('related_industries') or []
        rev_items = biz_analysis.get('revenue_mix_items') or []

        col_biz, col_rev = st.columns([1.3, 1.7])
        with col_biz:
            biz_bullets = "".join([f"<li style='margin:4px 0;'>{b}</li>" for b in main_biz_list]) if main_biz_list else f"<li>{biz_analysis.get('one_liner', '')}</li>"
            ind_badges = "".join([
                f"<span class='concept-tag' style='background:rgba(0,212,170,0.14);border-color:#00D4AA;color:#00D4AA;margin:2px 4px 2px 0;display:inline-block;'>🏭 {ind}</span>"
                for ind in rel_inds_list
            ])
            st.markdown(
                f"<div class='info-card' style='height:100%;'>"
                f"<div style='color:#00D4AA;font-weight:bold;font-size:19px;margin-bottom:6px;'>🛠️ 公司是做什麼的？（主要經營業務）</div>"
                f"<ul style='margin:0 0 10px 0;padding-left:18px;font-size:18px;line-height:1.6;color:#F8FAFC;'>{biz_bullets}</ul>"
                f"<div style='color:#38BDF8;font-weight:bold;font-size:18px;margin-bottom:4px;'>🔗 相關細分產業與終端應用領域：</div>"
                f"<div>{ind_badges if ind_badges else sector_str}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

        with col_rev:
            if rev_items:
                bar_colors = ['#00D4AA', '#38BDF8', '#F59E0B', '#EC4899', '#A855F7', '#94A3B8']
                rows_html = ""
                for idx_r, it in enumerate(rev_items):
                    c_hex = bar_colors[idx_r % len(bar_colors)]
                    pct_v = max(0.0, min(100.0, float(it['pct'])))
                    rows_html += (
                        f"<div style='margin-bottom:8px;'>"
                        f"<div style='display:flex;justify-content:space-between;font-size:18px;margin-bottom:2px;'>"
                        f"<span style='color:#F8FAFC;font-weight:bold;'>{it['name']}</span>"
                        f"<span style='color:{c_hex};font-weight:bold;'>{pct_v:.2f}%</span>"
                        f"</div>"
                        f"<div style='width:100%;background:#1E293B;height:8px;border-radius:4px;overflow:hidden;'>"
                        f"<div style='width:{pct_v}%;background:{c_hex};height:8px;border-radius:4px;'></div>"
                        f"</div>"
                        f"</div>"
                    )
                st.markdown(
                    f"<div class='info-card' style='height:100%;'>"
                    f"<div style='color:#FFD54F;font-weight:bold;font-size:19px;margin-bottom:8px;'>🥧 靠什麼賺錢？（主力產品營收比重結構）</div>"
                    f"{rows_html}"
                    f"<div style='color:#94A3B8;font-size:16.5px;margin-top:4px;'>原始比重：{biz_analysis.get('revenue_mix_raw', '')}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f"<div class='info-card'>"
                    f"<div style='color:#FFD54F;font-weight:bold;font-size:19px;margin-bottom:6px;'>🥧 靠什麼賺錢？（業務結構）</div>"
                    f"<div style='font-size:18px;line-height:1.6;'>{biz_analysis.get('one_liner', '')}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

        # 2. 為什麼會賺錢？近期獲利動能與重要財報/自結公告
        why_html = "".join([f"<li style='margin:6px 0;line-height:1.6;'>{w}</li>" for w in (biz_analysis.get('why_profitable') or [])])
        st.markdown(
            f"<div class='info-card' style='border-left:4px solid #FFD54F; margin-top:6px;'>"
            f"<div style='color:#FFD54F;font-weight:bold;font-size:20px;margin-bottom:6px;'>💰 為什麼會賺錢？本業獲利模式與近期成長動能深度白話解析</div>"
            f"<ul style='margin:0;padding-left:18px;font-size:18.5px;color:#F8FAFC;'>{why_html}</ul>"
            f"</div>",
            unsafe_allow_html=True
        )

        # 3. 估值與財務體質八大核心指標卡片
        st.markdown("#### 📊 估值水準與本業獲利體質指標（含同業比較）")
        pe  = info.get('pe')
        ind_pe = info.get('industry_avg_pe')
        pb  = info.get('pb')
        nav = info.get('net_worth_per_share')
        div = info.get('dividend_yield')
        cdiv = info.get('cash_dividend')
        mc  = info.get('market_cap')
        cap_yi = info.get('capital_yi')
        h52 = info.get('52w_high')
        l52 = info.get('52w_low')

        # 第一排：四大估值指標
        v1, v2, v3, v4 = st.columns(4)
        with v1:
            pe_status = "合理區間"
            if pe:
                pe_status = "估值偏低（便宜）" if pe < 15 else ("高成長預期溢價" if pe > 35 else "歷史合理區間")
            ind_pe_txt = f"同業平均：{ind_pe:.1f} 倍" if ind_pe else f"判讀：{pe_status}"
            st.markdown(
                f"<div class='info-card'>"
                f"<div style='color:#94A3B8;font-size:17px;'>本益比 (PE Ratio)</div>"
                f"<div style='font-size:28px;font-weight:bold;color:#00D4AA;margin:4px 0;'>{f'{pe:.2f} 倍' if pe else '無資料 (虧損或未公布)'}</div>"
                f"<div style='font-size:17px;color:#AAA;'>{ind_pe_txt}（{pe_status}）</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        with v2:
            pb_status = "股價低於淨值" if (pb and pb < 1) else ("正常水準" if (pb and pb < 3) else "高獲利溢價倍數")
            nav_txt = f"每股淨值：{nav:.2f} 元" if nav else f"判讀：{pb_status if pb else '—'}"
            st.markdown(
                f"<div class='info-card'>"
                f"<div style='color:#94A3B8;font-size:17px;'>股價淨值比 (PB Ratio)</div>"
                f"<div style='font-size:28px;font-weight:bold;color:#38BDF8;margin:4px 0;'>{f'{pb:.2f} 倍' if pb else 'N/A'}</div>"
                f"<div style='font-size:17px;color:#AAA;'>{nav_txt}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        with v3:
            div_pct = div * 100 if div is not None else 0.0
            div_status = "高殖利率防禦股 🔥" if div_pct >= 4.5 else ("具穩定配息能力" if div_pct > 0 else "以資本利得為主")
            cdiv_txt = f"現金股利：{cdiv:.2f} 元" if cdiv else f"判讀：{div_status}"
            st.markdown(
                f"<div class='info-card'>"
                f"<div style='color:#94A3B8;font-size:17px;'>現金殖利率 (Yield)</div>"
                f"<div style='font-size:28px;font-weight:bold;color:#FFD54F;margin:4px 0;'>{f'{div_pct:.2f}%' if div is not None else 'N/A'}</div>"
                f"<div style='font-size:17px;color:#AAA;'>{cdiv_txt}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        with v4:
            mc_str = f"NT$ {mc/1e8:,.1f} 億" if mc else "N/A"
            cap_txt = f"股本：{cap_yi:.2f} 億 ｜ " if cap_yi else ""
            st.markdown(
                f"<div class='info-card'>"
                f"<div style='color:#94A3B8;font-size:17px;'>公司總市值與股本</div>"
                f"<div style='font-size:28px;font-weight:bold;color:#FAFAFA;margin:4px 0;'>{mc_str}</div>"
                f"<div style='font-size:17px;color:#AAA;'>{cap_txt}一年高低：{f'{l52:,.1f}~{h52:,.1f}' if (h52 and l52) else '—'}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

        # 第二排：四大獲利能力與股權體質指標
        gm_v = info.get('gross_margin')
        om_v = info.get('operating_margin')
        roe_v = info.get('roe')
        dh_v = info.get('director_holding_pct')
        debt_v = info.get('debt_ratio_pct')

        p1, p2, p3, p4 = st.columns(4)
        with p1:
            gm_str = f"{gm_v*100:.2f}%" if gm_v is not None else "N/A"
            st.markdown(
                f"<div class='info-card'>"
                f"<div style='color:#94A3B8;font-size:17px;'>營業毛利率（產品競爭力）</div>"
                f"<div style='font-size:26px;font-weight:bold;color:#FF8A80;margin:4px 0;'>{gm_str}</div>"
                f"<div style='font-size:16.5px;color:#AAA;'>毛利率越高代表產品附加價值與定價權越強</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        with p2:
            om_str = f"{om_v*100:.2f}%" if om_v is not None else "N/A"
            st.markdown(
                f"<div class='info-card'>"
                f"<div style='color:#94A3B8;font-size:17px;'>營業利益率（本業實賺率）</div>"
                f"<div style='font-size:26px;font-weight:bold;color:#FF8A80;margin:4px 0;'>{om_str}</div>"
                f"<div style='font-size:16.5px;color:#AAA;'>扣除管銷研發費用後，本業每百元營收實賺比例</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        with p3:
            roe_str = f"{roe_v*100:.2f}%" if roe_v is not None else "N/A"
            st.markdown(
                f"<div class='info-card'>"
                f"<div style='color:#94A3B8;font-size:17px;'>股東權益報酬率 (ROE)</div>"
                f"<div style='font-size:26px;font-weight:bold;color:#A78BFA;margin:4px 0;'>{roe_str}</div>"
                f"<div style='font-size:16.5px;color:#AAA;'>衡量公司替股東資金創造獲利的效率</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        with p4:
            dh_str = f"{dh_v:.2f}%" if dh_v is not None else "N/A"
            debt_txt = f"負債比例：{debt_v:.1f}%" if debt_v is not None else "大股東籌碼集中度指標"
            st.markdown(
                f"<div class='info-card'>"
                f"<div style='color:#94A3B8;font-size:17px;'>董監事持股比例（大股東信心）</div>"
                f"<div style='font-size:26px;font-weight:bold;color:#34D399;margin:4px 0;'>{dh_str}</div>"
                f"<div style='font-size:16.5px;color:#AAA;'>{debt_txt}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

        # 52週股價位階進度條
        if h52 and l52 and h52 > l52:
            pos_pct = max(0.0, min(1.0, (latest_close - l52) / (h52 - l52)))
            st.markdown(f"**📏 近一年（52週）股價位階：{pos_pct*100:.1f}%**（最低 `NT$ {l52:,.2f}` ── 目前 `NT$ {latest_close:,.2f}` ── 最高 `NT$ {h52:,.2f}`）")
            st.progress(pos_pct)

        # 近期公司重要獲利/營收/動態新聞公告
        recent_news_list = biz_analysis.get('recent_news') or []
        if recent_news_list:
            st.markdown("#### 📢 近期公司重要營收、自結獲利與重大公告")
            news_items_html = "".join([f"<li style='margin:4px 0;'>{n}</li>" for n in recent_news_list])
            st.markdown(
                f"<div class='info-card' style='border-left:4px solid #38BDF8;'>"
                f"<ul style='margin:0;padding-left:18px;font-size:18px;line-height:1.65;color:#E2E8F0;'>{news_items_html}</ul>"
                f"</div>",
                unsafe_allow_html=True
            )

        # 若盤後報告有收錄此股，顯示報告中的深度評語
        if report_cmt and report_cmt.get('lines'):
            st.markdown(f"#### 📰 盤後報告焦點解析（報告日期：{report_cmt.get('report_date')}）")
            cmt_text = "<br>".join(report_cmt['lines'])
            st.markdown(
                f"<div class='info-card' style='border-left:4px solid #e53935;line-height:1.8;'>{cmt_text}</div>",
                unsafe_allow_html=True
            )

    # ── Tab 4：📋 財報與營收 ───────────────────────────────
    with tab4:
        st.subheader(f"📋 {stock_name} ({stock_code}) 營收動能與季度財報分析")

        m_rev_list = financials.get('monthly_revenue', []) if financials else []
        q_eps_list = financials.get('quarterly_eps', []) if financials else []

        # 1. 月營收區塊
        st.markdown("#### 📈 近 12 個月營收與年增率 (YoY) 表現")
        if m_rev_list:
            rev_df = pd.DataFrame(m_rev_list)
            latest_m = m_rev_list[-1]
            rm1, rm2, rm3 = st.columns(3)
            rm1.metric("最新月份營收", f"{latest_m['Revenue']:,.3f} 億元", f"({latest_m['Month']})")
            rm2.metric("營收年增率 (YoY)", f"{latest_m['YoY']:+.2f}%", "正成長" if latest_m['YoY'] >= 0 else "年減")
            rm3.metric("營收月增率 (MoM)", f"{latest_m['MoM']:+.2f}%", "月增" if latest_m['MoM'] >= 0 else "月減")

            st.plotly_chart(create_revenue_chart(rev_df), use_container_width=True, config=PLOTLY_CFG)
            with st.expander("📄 查看近 12 個月營收完整數據表"):
                st.dataframe(rev_df.iloc[::-1], use_container_width=True, hide_index=True)
        else:
            st.info("暫無月營收資料。")

        st.divider()

        # 2. 季度 EPS 與三率區塊
        st.markdown("#### 💰 近 8 季每股盈餘 (EPS) 與獲利三率（毛利率 / 營益率 / 淨利率）")
        if q_eps_list:
            eps_df = pd.DataFrame(q_eps_list)
            latest_q = q_eps_list[-1]
            rq1, rq2, rq3, rq4 = st.columns(4)
            rq1.metric(f"最新季度 EPS ({latest_q['Quarter']})", f"{latest_q['EPS']:.2f} 元")
            rq2.metric("單季毛利率", f"{latest_q['毛利率(%)']:.2f}%")
            rq3.metric("單季營業利益率", f"{latest_q['營益率(%)']:.2f}%")
            rq4.metric("單季稅後淨利率", f"{latest_q['淨利率(%)']:.2f}%")

            st.plotly_chart(create_eps_chart(eps_df), use_container_width=True, config=PLOTLY_CFG)
            with st.expander("📄 查看近 8 季損益與三率完整數據表"):
                st.dataframe(eps_df.iloc[::-1], use_container_width=True, hide_index=True)
        else:
            st.info("暫無季度損益與 EPS 明細資料。")

    # ── Tab 5：🤖 AI 深度評語 ──────────────────────────────
    with tab5:
        st.subheader(f"🤖 Gemini 3.8 Flash — {stock_name} ({stock_code}) 深度操盤報告")
        st.caption("結合即時技術指標、三大法人籌碼、公司主要業務、營收比重、月營收 YoY 與季度 EPS，由 Google Gemini 3.8 Flash 進行專業研判")

        # 檢查是否已有快取的 AI 分析報告
        cache_ai_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'cache', f"ai_analysis_{stock_code}.json")
        has_cached_ai = os.path.exists(cache_ai_file)

        run_ai = st.button("🔮 立即產生 / 更新 AI 深度分析報告（Gemini 3.8 Flash）", use_container_width=True)

        if run_ai or has_cached_ai:
            if run_ai and has_cached_ai:
                try:
                    os.remove(cache_ai_file)
                except Exception:
                    pass

            with st.spinner(f"🤖 Gemini 3.8 Flash 正在深入分析 {stock_name} ({stock_code}) 的業務、技術、籌碼與財報數據..."):
                tech_summary_payload = {
                    '最新收盤價': latest_close,
                    '漲跌幅': f"{pct_change:+.2f}%",
                    '技術評分': f"{tech_score}/100 ({tech_label})",
                    '均線趨勢': get_ma_trend(df_price),
                    'MACD訊號': get_macd_signal(df_price),
                    'KD訊號': get_kd_signal(df_price),
                    'RSI訊號': get_rsi_signal(df_price),
                    '支撐價位': support_resistance.get('support'),
                    '壓力價位': support_resistance.get('resistance'),
                }
                fundamental_payload = {
                    '中文股名': stock_name,
                    '市場與產業': f"{market_str} - {sector_str}",
                    '主要經營業務': biz_analysis.get('main_business'),
                    '產品營收比重': biz_analysis.get('revenue_mix_raw'),
                    '相關細分產業與應用': biz_analysis.get('related_industries'),
                    '近期重要新聞與自結公告': (biz_analysis.get('recent_news') or [])[:4],
                    '本益比PE': info.get('pe'),
                    '同業平均本益比': info.get('industry_avg_pe'),
                    '淨值比PB': info.get('pb'),
                    '殖利率': f"{info.get('dividend_yield')*100:.2f}%" if info.get('dividend_yield') else '無',
                    '52週高點': info.get('52w_high'),
                    '52週低點': info.get('52w_low'),
                }
                financial_payload = {
                    '近3季EPS与三率': financials.get('quarterly_eps', [])[-3:] if financials else [],
                    '近3月營收與YoY': financials.get('monthly_revenue', [])[-3:] if financials else [],
                }
                ai_result = generate_stock_analysis(
                    stock_code, stock_name,
                    tech_summary_payload, chip_summary,
                    fundamental_payload, financial_payload
                )

            if ai_result and 'error' not in ai_result and ai_result.get('rating'):
                rating = ai_result.get('rating', '觀望')
                badge_cls = 'rating-buy' if rating == '買進' else ('rating-watch' if rating == '觀望' else 'rating-sell')

                ac1, ac2, ac3, ac4 = st.columns(4)
                with ac1:
                    st.markdown(f"<div style='margin-bottom:6px;color:#AAA;font-size:18px;'>AI 投資評級</div><span class='{badge_cls}'>{rating}</span>", unsafe_allow_html=True)
                    st.caption(f"AI 信心指數：{ai_result.get('confidence', 7)} / 10")
                with ac2:
                    st.metric("🎯 AI 建議買進區間", f"NT$ {ai_result.get('buy_zone_low', 0)} ~ {ai_result.get('buy_zone_high', 0)}")
                with ac3:
                    st.metric("🚀 AI 目標價", f"NT$ {ai_result.get('target_price', 0)}")
                with ac4:
                    st.metric("🛑 AI 嚴格停損價", f"NT$ {ai_result.get('stop_loss', 0)}")

                st.markdown(
                    f"<div class='info-card' style='margin-top:12px;border-left:4px solid #00D4AA;'>"
                    f"<b>📝 AI 綜合評語：</b><br>{ai_result.get('summary', '')}"
                    f"</div>",
                    unsafe_allow_html=True
                )

                acol1, acol2 = st.columns(2)
                with acol1:
                    st.markdown("**✅ AI 歸納核心優勢**")
                    for s in ai_result.get('strengths', []):
                        st.markdown(f"- 🟢 {s}")
                with acol2:
                    st.markdown("**⚠️ AI 提醒潛在風險**")
                    for r in ai_result.get('risks', []):
                        st.markdown(f"- 🔴 {r}")

                st.markdown(
                    f"<div class='info-card'>"
                    f"<b>🎯 具體進出場操作策略：</b><br>{ai_result.get('strategy', '')}"
                    f"</div>",
                    unsafe_allow_html=True
                )
                st.markdown(
                    f"<div class='info-card'>"
                    f"<b>🔭 產業前景展望：</b><br>{ai_result.get('industry_outlook', '')}"
                    f"</div>",
                    unsafe_allow_html=True
                )
            elif ai_result and 'error' in ai_result:
                st.error(f"⚠️ {ai_result['error']}")
        else:
            st.info("👆 點擊上方「🔮 立即產生 / 更新 AI 深度分析報告」按鈕，即可由 Gemini 3.8 Flash 針對此股生成完整操盤建議！（頂部已先為您提供即時系統綜合評價）")

    # ── Tab 6：🏭 產業生態與同業比較 ───────────────────────
    with tab6:
        st.subheader(f"🏭 {stock_name} ({stock_code}) 產業鏈定位與同業競爭公司")

        rel_inds_str = " / ".join(biz_analysis.get('related_industries') or []) or sector_str
        st.markdown(
            f"<div class='info-card'>"
            f"<div style='margin-bottom:4px;'><b>📌 官方掛牌分類：</b> <span style='color:#00D4AA;font-weight:bold;'>{market_str} — {info.get('official_sector', sector_str)}</span></div>"
            f"<div style='margin-bottom:4px;'><b>🔍 實際細分產業與應用領域：</b> <span style='color:#38BDF8;font-weight:bold;'>{rel_inds_str}</span></div>"
            f"<div><b>🛠️ 主要經營業務：</b> <span style='color:#E2E8F0;'>{'；'.join(biz_analysis.get('main_business') or []) or biz_analysis.get('one_liner', '')}</span></div>"
            f"</div>",
            unsafe_allow_html=True
        )

        # 1. 概念股供應鏈角色與夥伴
        if concept_details:
            st.markdown("#### 🔗 所屬熱門題材與供應鏈角色")
            for citem in concept_details:
                st.markdown(
                    f"<div class='info-card' style='border-left:4px solid #FFB300;'>"
                    f"<div style='font-size:21px;font-weight:bold;color:#FFD54F;'>"
                    f"🏷️ {citem['big_category']} ▸ {citem['concept_name']}"
                    f"</div>"
                    f"<div style='color:#AAA;font-size:18px;margin:4px 0;'>題材說明：{citem['desc']}</div>"
                    f"<div style='color:#00D4AA;font-size:19px;font-weight:bold;'>"
                    f"📍 {stock_name} ({stock_code}) 在供應鏈中的定位：{citem['role']}"
                    f"</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
                st.caption(f"👇 點擊同屬「{citem['concept_name']}」的關聯公司可直接切換分析：")
                rel_stocks = [s for s in citem['related_stocks'] if str(s.get('code')) != stock_code]
                if rel_stocks:
                    rcols = st.columns(min(6, len(rel_stocks)))
                    for idx, rs in enumerate(rel_stocks[:12]):
                        with rcols[idx % len(rcols)]:
                            if st.button(
                                f"{rs['code']} {rs['name']}\n({rs.get('role', '')[:8]})",
                                key=f"rel_{citem['concept_name']}_{rs['code']}_{idx}",
                                use_container_width=True
                            ):
                                st.session_state['target_stock'] = rs['code']
                                st.rerun()

        # 2. 同產業競爭/相關公司（自動從台股 3,149 檔資料庫比對）
        peers = get_peer_stocks(stock_code, limit=12)
        if peers:
            st.markdown(f"#### 🏢 同分類（{info.get('official_sector', sector_str)}）其他上市櫃公司")
            st.caption("點擊任一同業公司按鈕，即可跳轉比較基本面與技術面：")
            p_cols = st.columns(6)
            for idx, peer in enumerate(peers):
                with p_cols[idx % 6]:
                    if st.button(
                        f"{peer['code']} {peer['name']}\n[{peer['market']}]",
                        key=f"peer_{peer['code']}",
                        use_container_width=True
                    ):
                        st.session_state['target_stock'] = peer['code']
                        st.rerun()

        st.divider()
        # 3. AI 產生上下游與競爭對手報告
        if st.button(f"🤖 請 Gemini 3.8 Flash 深度梳理「{stock_name} ({stock_code})」的上下游供應鏈與競爭對手", use_container_width=True):
            with st.spinner(f"正在分析 {stock_name} 的上下游產業鏈..."):
                try:
                    model = get_gemini_model()
                    chain_prompt = f"""
請以台灣股市產業研究員的角度，用繁體中文詳細整理台股「{stock_code} {stock_name}」（所屬細分產業：{rel_inds_str}；主要業務：{'、'.join(biz_analysis.get('main_business') or [])}；產品營收比重：{biz_analysis.get('revenue_mix_raw', '')}）的產業生態系：
1. **公司核心業務與主力產品**：用白話文介紹這家公司主要靠什麼賺錢？為什麼它的產品具有競爭力？
2. **上游供應商**：主要原料、晶片或零組件來源有哪些（請列出代表性台股或國際廠商）？
3. **中游製造/核心技術**：公司在產業鏈中的位置與優勢？
4. **下游客戶與應用領域**：產品賣給誰？主要應用在哪些終端產業（如半導體擴廠、AI、車用、安控等）？
5. **主要競爭對手（台股與國際）**：有哪些直接競爭的同業公司（請附上台股代號）？
"""
                    resp = model.generate_content(chain_prompt)
                    st.markdown(
                        f"<div class='info-card' style='line-height:1.8;'>{resp.text}</div>",
                        unsafe_allow_html=True
                    )
                except Exception as e:
                    st.error(f"產業鏈分析產生失敗：{e}")

