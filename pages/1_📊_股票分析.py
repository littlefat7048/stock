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
    get_daily_report_commentary_for_stock
)
from modules.technical_analysis import (
    calculate_indicators, get_technical_score,
    get_ma_trend, get_macd_signal, get_kd_signal, get_rsi_signal,
    find_support_resistance, generate_instant_diagnosis
)
from modules.chip_analysis import (
    get_institutional_trend, get_margin_trading,
    get_chip_score, get_chip_summary
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
    create_eps_chart, create_revenue_chart
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

st.markdown("<div style='font-size:13px; font-weight:bold; color:#00D4AA; margin-bottom:2px;'>🔍 輸入台股代號或中文股名查詢：</div>", unsafe_allow_html=True)
col_input, col_btn = st.columns([3.6, 1.4])
with col_input:
    raw_input = st.text_input(
        "🔍 輸入台股代號或中文股名",
        value=default_query,
        placeholder="點此輸入：例如 5484、慧友、2330、台積電、穎崴",
        label_visibility="collapsed"
    )
with col_btn:
    search_btn = st.button("🚀 立即分析", use_container_width=True)

# 熱門速選晶片（手機左右滑動，點擊直達）
quick_samples = [('2330', '台積電'), ('5484', '慧友'), ('6515', '穎崴'), ('2317', '鴻海'), ('2454', '聯發科'), ('2382', '廣達')]
sample_chips = "".join([
    f'<a href="/?stock={qcode}" target="_self" class="stock-chip-link">'
    f'<span class="chip-code">{qcode}</span>{qname}</a>'
    for qcode, qname in quick_samples
])
st.markdown(
    f'<div style="display:flex; align-items:center; margin-bottom:6px;">'
    f'<span style="color:#94A3B8; font-size:12px; margin-right:6px; flex-shrink:0;">熱門：</span>'
    f'<div class="chips-scroll-bar" style="margin:0; padding:2px 0;">{sample_chips}</div>'
    f'</div>',
    unsafe_allow_html=True
)

if search_btn or raw_input:
    # 將中文名稱或代號統一轉為標準台股代號
    stock_code = resolve_stock_query(raw_input)
    st.query_params['stock'] = stock_code

    with st.spinner(f"正在載入台股 {stock_code} 完整基本面、技術面、籌碼面與財報資料..."):
        info       = get_stock_info(stock_code)
        df_price   = get_price_history(stock_code, period='1y')
        chip_df    = get_institutional_trend(stock_code, days=25)
        margin_df  = get_margin_trading(stock_code, days=25)
        financials = get_financials(stock_code)
        concepts   = load_concept_data()
        report_cmt = get_daily_report_commentary_for_stock(stock_code)

    if df_price is None or df_price.empty:
        st.error(f"❌ 找不到台股代號「{raw_input}」（解析為 {stock_code}）的股價資料，請確認輸入的台股代號或中文名稱是否正確。")
        st.stop()

    # 計算技術指標與籌碼分數
    df_price = calculate_indicators(df_price)
    tech_score, tech_label = get_technical_score(df_price)
    support_resistance = find_support_resistance(df_price)
    chip_score, chip_label = get_chip_score(chip_df)
    chip_summary = get_chip_summary(chip_df, margin_df)

    # 計算即時綜合診斷（買進/觀望/賣出 + 建議價位 + 優缺點）
    diagnosis = generate_instant_diagnosis(df_price, info, chip_score, chip_summary, financials)

    # 取得最新價格與漲跌
    latest_close = float(df_price['Close'].iloc[-1])
    prev_close   = float(df_price['Close'].iloc[-2]) if len(df_price) > 1 else latest_close
    price_change = latest_close - prev_close
    pct_change   = (price_change / prev_close * 100) if prev_close else 0.0
    latest_date_str = df_price.index[-1].strftime('%Y/%m/%d') if hasattr(df_price.index[-1], 'strftime') else str(df_price.index[-1])[:10]

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
            f"<span style='font-size:22px; font-weight:bold; color:#FAFAFA;'>🇹🇼 {stock_name}</span>"
            f"<span style='color:#94A3B8; font-size:18px; font-weight:bold;'>({stock_code})</span>"
            f"<span class='market-badge'>{market_str}</span>"
            f"<span class='sector-badge'>{sector_str}</span>"
            f"</div>"
            f"<div style='margin-bottom:4px; display:flex; align-items:baseline; flex-wrap:wrap; gap:8px;'>"
            f"<span style='font-size:26px; font-weight:bold; color:{price_color}'>NT$ {latest_close:,.2f}</span>"
            f"<span style='font-size:16px; font-weight:bold; color:{price_color}'>{arrow} {abs(price_change):,.2f} ({pct_change:+.2f}%)</span>"
            f"<span style='color:#888; font-size:11px;'>基準：{latest_date_str}</span>"
            f"</div>",
            unsafe_allow_html=True
        )

        stock_concepts = get_concept_tags_for_stock(stock_code, concepts)
        if stock_concepts:
            tags_html = "".join([f"<span class='concept-tag'>🏷️ {t}</span>" for t in stock_concepts])
            st.markdown(f"<div style='margin-bottom:2px;'>{tags_html}</div>", unsafe_allow_html=True)

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
    # 2. 最前方：綜合評價（買進/賣出/等待）、建議價位、優缺點速覽
    # ══════════════════════════════════════════════════════════
    st.subheader("🎯 綜合評價與操作建議")

    btype = diagnosis['badge_type']
    css_cls = 'rating-buy' if btype == 'buy' else ('rating-watch' if btype == 'watch' else 'rating-sell')

    col_eval, col_prices = st.columns([1.2, 2.8])
    with col_eval:
        st.markdown(
            f"<div class='info-card' style='text-align:center; padding:12px 10px; margin-bottom:6px;'>"
            f"<div style='color:#94A3B8;font-size:12px;margin-bottom:4px;'>目前綜合評價</div>"
            f"<div class='{css_cls}'>{diagnosis['action']}</div>"
            f"<div style='margin-top:10px;font-size:14px;'>"
            f"評分：<b style='color:#00D4AA;font-size:18px;'>{diagnosis['total_score']}</b> / 100"
            f"</div>"
            f"<div style='color:#94A3B8;font-size:11px;margin-top:4px;'>"
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
            f"<div style='color:#94A3B8;font-size:11px;'>💰 建議買進</div>"
            f"<div style='color:#00D4AA;font-size:15px;font-weight:bold;margin-top:2px;'>{diagnosis['buy_zone']}</div>"
            f"<div style='color:#888;font-size:10px;margin-top:2px;'>支撐：{diagnosis['support']:,.1f}</div>"
            f"</div>"
            f"<div class='price-box' style='border-left-color:#e53935; padding:8px 6px; text-align:center;'>"
            f"<div style='color:#94A3B8;font-size:11px;'>🚀 目標價</div>"
            f"<div style='color:#e53935;font-size:15px;font-weight:bold;margin-top:2px;'>{diagnosis['target_price']}</div>"
            f"<div style='color:#888;font-size:10px;margin-top:2px;'>壓力：{diagnosis['resistance']:,.1f}</div>"
            f"</div>"
            f"<div class='price-box' style='border-left-color:#43a047; padding:8px 6px; text-align:center;'>"
            f"<div style='color:#94A3B8;font-size:11px;'>🛑 停損價</div>"
            f"<div style='color:#43a047;font-size:15px;font-weight:bold;margin-top:2px;'>{diagnosis['stop_loss']}</div>"
            f"<div style='color:#888;font-size:10px;margin-top:2px;'>防守線</div>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True
        )

        st.markdown(
            f"<div class='info-card' style='padding:8px 12px; margin-bottom:6px; font-size:13px;'>"
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
            f"<div style='color:#FF8A80;font-weight:bold;font-size:13px;margin-bottom:4px;'>👍 多方優勢與亮點</div>"
            f"<ul style='margin:0;padding-left:18px;font-size:13px;'>{pros_items}</ul>"
            f"</div>",
            unsafe_allow_html=True
        )
    with col_cons:
        st.markdown(
            f"<div class='con-box'>"
            f"<div style='color:#81C784;font-weight:bold;font-size:13px;margin-bottom:4px;'>⚠️ 潛在風險與注意事項</div>"
            f"<ul style='margin:0;padding-left:18px;font-size:13px;'>{cons_items}</ul>"
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

    # ── Tab 1：📊 技術面分析 ───────────────────────────────
    with tab1:
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
                    f"<div style='color:#94A3B8;font-size:12px'>{label}</div>"
                    f"<div style='font-weight:bold;font-size:14px;margin-top:4px'>{sig_text}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            # 各均線目前精確數值
            last_row = df_price.iloc[-1]
            st.markdown(
                f"<div class='info-card'>"
                f"<div style='color:#94A3B8;font-size:12px;margin-bottom:6px;'>📏 各期均線目前位置</div>"
                f"<div style='font-size:13px;line-height:1.8;'>"
                f"• 5日線 (週線)：<b>{last_row.get('MA5', 0):,.2f}</b> 元<br>"
                f"• 10日線 (雙週)：<b>{last_row.get('MA10', 0):,.2f}</b> 元<br>"
                f"• 20日線 (月線)：<b>{last_row.get('MA20', 0):,.2f}</b> 元<br>"
                f"• 60日線 (季線)：<b>{last_row.get('MA60', 0):,.2f}</b> 元"
                f"</div></div>",
                unsafe_allow_html=True
            )

        with col_chart:
            ma_options = st.multiselect(
                "選擇顯示均線",
                ['MA5', 'MA10', 'MA20', 'MA60', 'MA120', 'MA240'],
                default=['MA5', 'MA20', 'MA60']
            )
            st.plotly_chart(
                create_candlestick_chart(df_price.tail(150), ma_options),
                use_container_width=True
            )

            sub_col1, sub_col2 = st.columns(2)
            with sub_col1:
                st.plotly_chart(create_macd_chart(df_price.tail(120)), use_container_width=True)
            with sub_col2:
                st.plotly_chart(create_kd_chart(df_price.tail(120)), use_container_width=True)

            st.plotly_chart(create_rsi_chart(df_price.tail(120)), use_container_width=True)

    # ── Tab 2：🏛 籌碼面分析 ───────────────────────────────
    with tab2:
        st.subheader(f"🏛 {stock_name} ({stock_code}) 三大法人與資券籌碼分析")

        if chip_summary.get('available'):
            # 頂部籌碼統計卡片
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(
                    f"<div class='info-card'>"
                    f"<div style='color:#94A3B8;font-size:13px;'>籌碼綜合評分</div>"
                    f"<div style='font-size:24px;font-weight:bold;color:#00D4AA;margin:4px 0;'>{chip_score} / 100</div>"
                    f"<div style='font-size:13px;'>{chip_label}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            with c2:
                f5 = chip_summary['foreign_5d']
                f_col = '#e53935' if f5 >= 0 else '#43a047'
                st.markdown(
                    f"<div class='info-card'>"
                    f"<div style='color:#94A3B8;font-size:13px;'>🌍 外資動向（{chip_summary['foreign_streak']}）</div>"
                    f"<div style='font-size:20px;font-weight:bold;color:{f_col};margin:4px 0;'>近5日 {f5:+,.1f} 張</div>"
                    f"<div style='font-size:12px;color:#AAA;'>最新單日：{chip_summary['foreign_1d']:+,.1f} 張 ｜ 近20日：{chip_summary['foreign_20d']:+,.1f} 張</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            with c3:
                t5 = chip_summary['trust_5d']
                t_col = '#e53935' if t5 >= 0 else '#43a047'
                st.markdown(
                    f"<div class='info-card'>"
                    f"<div style='color:#94A3B8;font-size:13px;'>🏦 投信動向（{chip_summary['trust_streak']}）</div>"
                    f"<div style='font-size:20px;font-weight:bold;color:{t_col};margin:4px 0;'>近5日 {t5:+,.1f} 張</div>"
                    f"<div style='font-size:12px;color:#AAA;'>最新單日：{chip_summary['trust_1d']:+,.1f} 張 ｜ 近20日：{chip_summary['trust_20d']:+,.1f} 張</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            with c4:
                tot5 = chip_summary['total_5d']
                tot_col = '#e53935' if tot5 >= 0 else '#43a047'
                st.markdown(
                    f"<div class='info-card'>"
                    f"<div style='color:#94A3B8;font-size:13px;'>📊 三大法人合計（{chip_summary['total_streak']}）</div>"
                    f"<div style='font-size:20px;font-weight:bold;color:{tot_col};margin:4px 0;'>近5日 {tot5:+,.1f} 張</div>"
                    f"<div style='font-size:12px;color:#AAA;'>最新單日：{chip_summary['total_1d']:+,.1f} 張 ｜ 近20日：{chip_summary['total_20d']:+,.1f} 張</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            # 三大法人買賣超圖表
            st.plotly_chart(create_institutional_chart(chip_df), use_container_width=True)

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

                st.plotly_chart(create_margin_chart(margin_df), use_container_width=True)

            # 近期法人買賣超明細表
            with st.expander("📋 查看近 15 個交易日三大法人買賣超明細表（單位：張）", expanded=True):
                display_chip_df = chip_df[['外資', '投信', '自營商', '三大法人合計']].tail(15).iloc[::-1]
                st.dataframe(display_chip_df, use_container_width=True)
        else:
            st.info("此股票目前無近期三大法人買賣超明細資料。")

    # ── Tab 3：💹 基本面與估值 ─────────────────────────────
    with tab3:
        st.subheader(f"💹 {stock_name} ({stock_code}) 基本面與估值分析")

        pe  = info.get('pe')
        pb  = info.get('pb')
        div = info.get('dividend_yield')
        mc  = info.get('market_cap')
        h52 = info.get('52w_high')
        l52 = info.get('52w_low')

        # 估值指標卡片
        v1, v2, v3, v4 = st.columns(4)
        with v1:
            pe_status = "合理區間"
            if pe:
                pe_status = "估值偏低（便宜）" if pe < 15 else ("估值偏高（成長預期）" if pe > 35 else "歷史合理區間")
            st.markdown(
                f"<div class='info-card'>"
                f"<div style='color:#94A3B8;font-size:13px;'>本益比 (PE Ratio)</div>"
                f"<div style='font-size:24px;font-weight:bold;color:#00D4AA;margin:4px 0;'>{f'{pe:.2f} 倍' if pe else '無資料 (虧損或未公布)'}</div>"
                f"<div style='font-size:12px;color:#AAA;'>判讀：{pe_status}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        with v2:
            pb_status = "股價低於淨值" if (pb and pb < 1) else ("正常水準" if (pb and pb < 3) else "高溢價倍數")
            st.markdown(
                f"<div class='info-card'>"
                f"<div style='color:#94A3B8;font-size:13px;'>股價淨值比 (PB Ratio)</div>"
                f"<div style='font-size:24px;font-weight:bold;color:#38BDF8;margin:4px 0;'>{f'{pb:.2f} 倍' if pb else 'N/A'}</div>"
                f"<div style='font-size:12px;color:#AAA;'>判讀：{pb_status if pb else '—'}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        with v3:
            div_pct = div * 100 if div is not None else 0.0
            div_status = "高殖利率防禦股 🔥" if div_pct >= 4.5 else ("具配息能力" if div_pct > 0 else "以資本利得為主")
            st.markdown(
                f"<div class='info-card'>"
                f"<div style='color:#94A3B8;font-size:13px;'>現金殖利率 (Yield)</div>"
                f"<div style='font-size:24px;font-weight:bold;color:#FFD54F;margin:4px 0;'>{f'{div_pct:.2f}%' if div is not None else 'N/A'}</div>"
                f"<div style='font-size:12px;color:#AAA;'>判讀：{div_status}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        with v4:
            mc_str = f"NT$ {mc/1e8:,.1f} 億" if mc else "N/A"
            st.markdown(
                f"<div class='info-card'>"
                f"<div style='color:#94A3B8;font-size:13px;'>公司總市值</div>"
                f"<div style='font-size:24px;font-weight:bold;color:#FAFAFA;margin:4px 0;'>{mc_str}</div>"
                f"<div style='font-size:12px;color:#AAA;'>一年高低：{f'{l52:,.1f} ~ {h52:,.1f} 元' if (h52 and l52) else '—'}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

        # 52週股價位階進度條
        if h52 and l52 and h52 > l52:
            pos_pct = max(0.0, min(1.0, (latest_close - l52) / (h52 - l52)))
            st.markdown(f"**📏 近一年（52週）股價位階：{pos_pct*100:.1f}%**（最低 `NT$ {l52:,.2f}` ── 目前 `NT$ {latest_close:,.2f}` ── 最高 `NT$ {h52:,.2f}`）")
            st.progress(pos_pct)

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

            st.plotly_chart(create_revenue_chart(rev_df), use_container_width=True)
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

            st.plotly_chart(create_eps_chart(eps_df), use_container_width=True)
            with st.expander("📄 查看近 8 季損益與三率完整數據表"):
                st.dataframe(eps_df.iloc[::-1], use_container_width=True, hide_index=True)
        else:
            st.info("暫無季度損益與 EPS 明細資料。")

    # ── Tab 5：🤖 AI 深度評語 ──────────────────────────────
    with tab5:
        st.subheader(f"🤖 Gemini 3.8 Flash — {stock_name} ({stock_code}) 深度操盤報告")
        st.caption("結合即時技術指標、三大法人籌碼、月營收 YoY 與季度 EPS，由 Google Gemini 3.8 Flash 進行專業研判")

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

            with st.spinner(f"🤖 Gemini 3.8 Flash 正在深入分析 {stock_name} ({stock_code}) 的技術、籌碼與財報數據..."):
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
                    '本益比PE': info.get('pe'),
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
                    st.markdown(f"<div style='margin-bottom:6px;color:#AAA;font-size:13px;'>AI 投資評級</div><span class='{badge_cls}'>{rating}</span>", unsafe_allow_html=True)
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

        st.markdown(
            f"<div class='info-card'>"
            f"<b>📌 官方產業分類：</b> <span style='color:#00D4AA;font-weight:bold;'>{market_str} — {sector_str}</span>"
            f"</div>",
            unsafe_allow_html=True
        )

        # 1. 概念股供應鏈角色與夥伴
        concept_details = get_concept_details_for_stock(stock_code, concepts)
        if concept_details:
            st.markdown("#### 🔗 所屬熱門題材與供應鏈角色")
            for citem in concept_details:
                st.markdown(
                    f"<div class='info-card' style='border-left:4px solid #FFB300;'>"
                    f"<div style='font-size:16px;font-weight:bold;color:#FFD54F;'>"
                    f"🏷️ {citem['big_category']} ▸ {citem['concept_name']}"
                    f"</div>"
                    f"<div style='color:#AAA;font-size:13px;margin:4px 0;'>題材說明：{citem['desc']}</div>"
                    f"<div style='color:#00D4AA;font-size:14px;font-weight:bold;'>"
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
            st.markdown(f"#### 🏢 同產業（{sector_str}）相關與競爭公司")
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
請以台灣股市產業研究員的角度，用繁體中文詳細整理台股「{stock_code} {stock_name}」（所屬產業：{sector_str}）的產業生態系：
1. **公司核心業務與主力產品**：用白話文介紹這家公司主要靠什麼賺錢？
2. **上游供應商**：主要原料、晶片或零組件來源有哪些（請列出代表性台股或國際廠商）？
3. **中游製造/核心技術**：公司在產業鏈中的位置與優勢？
4. **下游客戶與應用領域**：產品賣給誰？主要應用在哪些終端產業（如 AI、車用、安控、半導體等）？
5. **主要競爭對手（台股與國際）**：有哪些直接競爭的同業公司（請附上台股代號）？
"""
                    resp = model.generate_content(chain_prompt)
                    st.markdown(
                        f"<div class='info-card' style='line-height:1.8;'>{resp.text}</div>",
                        unsafe_allow_html=True
                    )
                except Exception as e:
                    st.error(f"產業鏈分析產生失敗：{e}")
