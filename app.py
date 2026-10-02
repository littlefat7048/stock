"""
台股每日盤後分析報告 — 首頁
每日 19:00 自動抓取報告，股票名稱點擊後立即跳轉至個股分析頁
"""
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timedelta
import sys, os, re

sys.path.insert(0, os.path.dirname(__file__))

# ── 1. Page Config 必須為第一個 Streamlit 指令 ────────────
st.set_page_config(page_title='台股每日分析', page_icon='📊', layout='wide')

# ── 2. 攔截跳轉參數（點擊日報內的股票或頂部導覽列時切換頁面）───
if 'stock' in st.query_params and st.query_params['stock']:
    stock_code = str(st.query_params['stock']).strip()
    st.session_state['target_stock'] = stock_code
    del st.query_params['stock']
    st.switch_page("pages/1_📊_股票分析.py")

if 'c_sub' in st.query_params and st.query_params['c_sub']:
    st.session_state['selected_concept_sub'] = str(st.query_params['c_sub']).strip()
    del st.query_params['c_sub']
    st.switch_page("pages/2_🏷️_概念股.py")

if 'nav' in st.query_params and st.query_params['nav']:
    nav_target = str(st.query_params['nav']).strip()
    del st.query_params['nav']
    if nav_target == 'radar':
        st.switch_page("pages/4_🚀_強勢雷達.py")
    elif nav_target == 'stock':
        st.switch_page("pages/1_📊_股票分析.py")
    elif nav_target == 'concept':
        st.switch_page("pages/2_🏷️_概念股.py")
    elif nav_target == 'watch':
        st.switch_page("pages/3_⭐_自選股.py")

# ── 3. 注入父視窗跨 iframe 通訊監聽器 ─────────────────────
components.html("""
<script>
(function() {
    try {
        var p = window.parent || window.top;
        if (p && !p._stockBridgeReady) {
            p._stockBridgeReady = true;
            p.addEventListener('message', function(e) {
                if (e.data && (e.data.type === 'navigate_stock' || e.data.stock)) {
                    var code = e.data.stock;
                    if (code) {
                        var origin = p.location.origin || '';
                        p.location.href = origin + '/?stock=' + code;
                    }
                }
            });
        }
    } catch(err) {
        console.error('Stock bridge init error:', err);
    }
})();
</script>
""", height=0, width=0)

import importlib
importlib.invalidate_caches()
import utils.helpers
importlib.reload(utils.helpers)

from modules.daily_report import (
    scrape_report, load_report_cache, save_report_cache,
    parse_stock_codes, get_available_dates
)
from modules.data_fetcher import get_twse_institutional_summary
from utils.helpers import get_common_css, get_top_nav_html

# ── 注入自訂響應式 CSS 與頂部導覽列 ──────────────────────
st.markdown(get_common_css(), unsafe_allow_html=True)
st.markdown(get_top_nav_html('home'), unsafe_allow_html=True)

# ── 側邊欄：日期選擇 ──────────────────────────────────────
with st.sidebar:
    st.title("📅 報告日期")

    available = get_available_dates()
    # 產生最近 10 個工作日選項
    date_options = []
    d = datetime.now()
    for _ in range(20):
        if d.weekday() < 5:  # 非週末
            date_options.append(d.strftime('%Y%m%d'))
            if len(date_options) == 10:
                break
        d -= timedelta(days=1)

    # 智慧自動同步：若最新工作日尚未快取，主動向線上探測是否有新報告發布
    latest_workday = date_options[0] if date_options else None
    if latest_workday and latest_workday not in available:
        try:
            latest_res = scrape_report(latest_workday)
            if latest_res.get('status') == 'success':
                available = get_available_dates()
        except Exception:
            pass

    # 確保已快取的日期在選項內
    for av in available:
        if av not in date_options:
            date_options.append(av)
    date_options = sorted(date_options, reverse=True)

    # 預設選最新有快取的日期
    default_idx = 0
    for i, opt in enumerate(date_options):
        if opt in available:
            default_idx = i
            break

    def label_date(ds):
        try:
            dt = datetime.strptime(ds, '%Y%m%d')
            label = dt.strftime('%Y/%m/%d (%a)')
        except Exception:
            label = ds
        if ds in available:
            label += " ✅ 已快取"
        return label

    selected_date = st.selectbox(
        "選擇日期",
        date_options,
        index=default_idx,
        format_func=label_date
    )

    st.divider()
    if st.button("🔄 立即檢查與重新抓取", use_container_width=True):
        with st.spinner(f"正在檢查與抓取盤後分析報告..."):
            # 優先嘗試當前選取的日期，若未抓到再嘗試最新工作日
            result = scrape_report(selected_date)
            if result.get('status') != 'success' and latest_workday and latest_workday != selected_date:
                result = scrape_report(latest_workday)
            if result.get('status') == 'success':
                st.success(f"✅ 抓取成功！日期 {result.get('date')} 包含 {len(result.get('stocks_found', []))} 檔個股分析")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ 該日報告尚未發布或抓取失敗，請確認上游是否已出刊")

    st.caption("💡 週末休市不開盤，最新交易日為週五。平日每日 19:00 起自動多梯次同步！")
    st.divider()
    st.caption("💡 每日 19:00 自動抓取最新報告\n\n點擊報告中任何股票代碼即可跳至「個股分析」！")

# ── 主頁面標題與快速查股框 ────────────────────────────────
st.title("📊 台股每日盤後分析報告")
st.caption(f"選取報告日期：{selected_date[:4]}/{selected_date[4:6]}/{selected_date[6:]} ｜ 每日盤後定時自動同步")

st.markdown("<div style='font-size:18px; font-weight:bold; color:#00D4AA; margin-top:4px; margin-bottom:2px;'>🔍 直接輸入台股代號或中文股名查詢：</div>", unsafe_allow_html=True)
hc1, hc2 = st.columns([3.6, 1.4])
with hc1:
    home_stock_q = st.text_input(
        "輸入台股代號或中文股名",
        placeholder="點此輸入：例如 5484、慧友、2330、台積電...",
        key="home_direct_search",
        label_visibility="collapsed"
    )
with hc2:
    home_search_btn = st.button("🚀 立即分析", key="home_search_btn", use_container_width=True)

if (home_search_btn or home_stock_q) and home_stock_q.strip():
    st.session_state['target_stock'] = home_stock_q.strip()
    st.switch_page("pages/1_📊_股票分析.py")

st.markdown(
    '<a href="/?nav=radar" target="_self" style="text-decoration:none !important;">'
    '<div style="background:linear-gradient(90deg, #1E1B4B 0%, #311042 100%); border:1.5px solid #A855F7; border-radius:10px; padding:10px 14px; margin:8px 0 10px 0; display:flex; justify-content:space-between; align-items:center; cursor:pointer;">'
    '<div>'
    '<span style="font-size:18px; font-weight:bold; color:#F472B6;">🚀 今日強勢飆股雷達已上線！</span>'
    '<div style="color:#CBD5E1; font-size:14px; margin-top:2px;">🔥 爆量長紅 ｜ 📈 多頭連續上漲 ｜ 👑 王者共振股點此查看 ➔</div>'
    '</div>'
    '<span style="background:#7C3AED; color:#FFF; font-weight:bold; font-size:14px; padding:5px 12px; border-radius:6px; flex-shrink:0;">立即看盤 ➔</span>'
    '</div>'
    '</a>',
    unsafe_allow_html=True
)

st.divider()

# ── 載入報告 ──────────────────────────────────────────────
cached = load_report_cache(selected_date)

if cached and cached.get('html'):
    report_html = cached['html']
    stocks_in_report = cached.get('stocks', [])
    st.success(f"✅ 已載入完整盤後報告 | 共收錄 {len(stocks_in_report)} 檔個股深度分析")
else:
    with st.spinner(f"⏳ 正在抓取 {selected_date} 盤後報告..."):
        result = scrape_report(selected_date)

    if result['status'] == 'success':
        report_html = result['html']
        stocks_in_report = result['stocks_found']
        st.success(f"✅ 抓取成功！共收錄 {len(stocks_in_report)} 檔個股深度分析")
    else:
        report_html = None
        stocks_in_report = []
        st.warning(f"⚠️ 尚無 {selected_date} 的完整報告（可能尚未發布，或非交易日）")

# ── 今日焦點股快速捷徑（手機滑動晶片）───────────────────
if stocks_in_report:
    st.markdown("<div style='font-size:19px; font-weight:bold; margin-bottom:4px;'>🚀 今日熱門焦點股（左右滑動點擊直達）：</div>", unsafe_allow_html=True)
    focus_stocks = stocks_in_report[:15]
    chips_html = "".join([
        f'<a href="/?stock={s["code"]}" target="_self" class="stock-chip-link">'
        f'<span class="chip-code">{s["code"]}</span>{s["name"]}</a>'
        for s in focus_stocks
    ])
    st.markdown(f'<div class="chips-scroll-bar">{chips_html}</div>', unsafe_allow_html=True)

    with st.expander(f"🔍 展開查看全部收錄的 {len(stocks_in_report)} 檔個股清單（支援搜尋）", expanded=False):
        search_kw = st.text_input("輸入代碼或名稱搜尋", placeholder="例如：2330 或 穎崴", key="quick_filter", label_visibility="collapsed")
        filtered_stocks = stocks_in_report
        if search_kw:
            filtered_stocks = [s for s in stocks_in_report if search_kw in s['code'] or search_kw in s['name']]

        chips_all = "".join([
            f'<a href="/?stock={s["code"]}" target="_self" class="stock-chip-link" style="margin:2px 2px;">'
            f'<span class="chip-code">{s["code"]}</span>{s["name"]}</a>'
            for s in filtered_stocks[:90]
        ])
        st.markdown(
            f'<div style="display:flex; flex-wrap:wrap; gap:4px; max-height:260px; overflow-y:auto; padding:6px 0;">{chips_all}</div>',
            unsafe_allow_html=True
        )

        if len(filtered_stocks) > 90:
            st.caption(f"（已顯示前 90 檔，其餘請使用上方搜尋過濾）")

    st.divider()

# ── 嵌入報告 HTML（帶跨層級點擊事件綁定）──────────────────
if report_html:
    def inject_stock_links(html):
        """
        將報告 HTML 中的股票名稱/代碼包裝為呼叫 handleStockClick(code) 的互動元素。
        1. 個股卡片標題：<span style="font-weight:bold;font-size:20px">6515 穎崴</span>
        2. 段落文字中的「股名（代碼）」
        """
        # 1. 替換個股卡片標題
        card_pattern = r'<span style="font-weight:bold;font-size:20px">(\d{4})\s*([^<]+)</span>'
        def replace_card(m):
            code = m.group(1)
            name = m.group(2).strip()
            return (
                f'<span onclick="handleStockClick(\'{code}\')" style="cursor:pointer; display:inline-block; '
                f'background:#00D4AA20; border:2px solid #00D4AA; border-radius:8px; '
                f'padding:3px 12px; margin-right:6px; font-weight:bold; font-size:20px; color:#00D4AA; '
                f'box-shadow: 0 2px 5px rgba(0,212,170,0.2); transition: transform 0.1s;" '
                f'onmouseover="this.style.background=\'#00D4AA40\'" onmouseout="this.style.background=\'#00D4AA20\'" '
                f'title="點擊前往 {code} {name} 完整深度分析">📊 {code} {name} ↗</span>'
            )
        html = re.sub(card_pattern, replace_card, html)

        # 2. 替換文字段落中的「股名（代號）」
        text_pattern = r'([\u4e00-\u9fa5A-Za-z0-9\-]{2,8})[（\(](\d{4})([，,][^）\)]*)?[）\)]'
        def replace_text(m):
            name = m.group(1)
            code = m.group(2)
            extra = m.group(3) or ''
            return (
                f'<span onclick="handleStockClick(\'{code}\')" style="cursor:pointer; color:#00D4AA; '
                f'font-weight:bold; text-decoration:underline; padding:1px 4px; border-radius:4px;" '
                f'onmouseover="this.style.background=\'#00D4AA20\'" onmouseout="this.style.background=\'transparent\'" '
                f'title="點擊查看 {code} 分析">{name}（{code}{extra}）</span>'
            )
        html = re.sub(text_pattern, replace_text, html)

        # 3. 在 HTML 開頭注入通訊 JavaScript 函數
        js_bridge = """
<script>
function handleStockClick(code) {
    if (!code) return;
    
    // 1. 優先透過 postMessage 通知父視窗跳轉（同分頁無縫切換）
    try {
        var p = window.parent || window.top;
        if (p) {
            p.postMessage({type: 'navigate_stock', stock: code}, '*');
        }
    } catch(e) {}

    // 2. 嘗試直接操作父視窗 URL
    try {
        var p = window.parent || window.top;
        if (p && p.location) {
            var origin = p.location.origin || '';
            p.location.href = origin + '/?stock=' + code;
            return;
        }
    } catch(e) {}

    // 3. 兜底保障：開新分頁跳轉
    try {
        var base = '';
        try { base = (window.parent && window.parent.location) ? window.parent.location.origin : ''; } catch(e) {}
        if (!base) base = window.location.origin || '';
        window.open(base + '/?stock=' + code, '_blank');
    } catch(e) {}
}
</script>
"""
        return js_bridge + html

    display_html = inject_stock_links(report_html)

    st.subheader("📄 每日盤後報告全文")
    st.caption("💡 提示：點擊報告中任何**綠色股票標籤 📊** 或**有底線的股票名稱**，即可立即跳轉至個股完整分析！")
    components.html(display_html, height=12000, scrolling=True)

else:
    st.subheader("📊 今日大盤概況（官方備用資料）")
    st.info("今日尚未有完整盤後報告，以下顯示台灣證交所官方即時資料")

    with st.spinner("載入證交所資料..."):
        inst_data = get_twse_institutional_summary()

    if inst_data and inst_data.get('data'):
        st.subheader("🏛 三大法人買賣超（上市）")
        rows_data = inst_data.get('data', [])
        if rows_data:
            import pandas as pd
            fields = inst_data.get('fields', [])
            df = pd.DataFrame(rows_data, columns=fields) if fields else pd.DataFrame(rows_data)
            st.dataframe(df, use_container_width=True)
    else:
        st.info("暫無即時資料。請確認每日 19:00 後報告已產生。")
