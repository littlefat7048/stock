"""
台股自選股追蹤與看盤管理頁面
支援：
- 仿專業看盤 App 的「紅綠K棒 + 報價漲跌 + 平盤雙色走勢圖」自選股看盤面板
- 代號或中文股名快速新增、投資備註編輯、一鍵跳轉個股完整分析
"""
import importlib
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import utils.helpers
import modules.data_fetcher
importlib.reload(utils.helpers)
importlib.reload(modules.data_fetcher)

from utils.helpers import (
    load_watchlist, save_watchlist,
    resolve_stock_query, get_tw_stock_chinese_info,
    get_concept_tags_for_stock, load_concept_data,
    get_common_css, get_top_nav_html, render_quote_table_html
)
from modules.data_fetcher import get_batch_quotes_with_intraday
from modules.screener import scan_market_signals

st.set_page_config(page_title='自選股看盤清單', page_icon='⭐', layout='wide')
st.markdown(get_common_css(), unsafe_allow_html=True)
st.markdown(get_top_nav_html('watch'), unsafe_allow_html=True)

st.title("⭐ 我的台股自選股看盤清單")

watchlist = load_watchlist()

col1, col2, col3 = st.columns([1.8, 2.0, 1.2])
with col1:
    new_input = st.text_input("➕ 輸入股票代號或中文股名", placeholder="例如：5484、慧友、3081、聯亞", label_visibility="collapsed")
with col2:
    new_note = st.text_input("📝 投資備註（選填）", placeholder="備註（選填）：如 38元支撐買進", label_visibility="collapsed")
with col3:
    if st.button("➕ 加入自選", use_container_width=True):
        if new_input:
            code = resolve_stock_query(new_input)
            cinfo = get_tw_stock_chinese_info(code)
            if code not in [s['code'] for s in watchlist]:
                watchlist.append({
                    'code': code,
                    'name': cinfo.get('name', code),
                    'note': new_note.strip()
                })
                save_watchlist(watchlist)
                st.toast(f"✅ 已新增 {cinfo.get('name', code)} ({code})")
                st.rerun()
            else:
                st.warning(f"{cinfo.get('name', code)} ({code}) 已經在自選股清單中！")

if not watchlist:
    st.info("目前尚未加入任何自選股。您可以在上方輸入代號/股名新增，或在「股票分析」頁面點擊加入！")
else:
    codes = [s['code'] for s in watchlist]
    with st.spinner("正在載入自選股即時報價與訊號雷達..."):
        quotes_map = get_batch_quotes_with_intraday(codes)
        screener_data = scan_market_signals()
        screener_items = screener_data.get('items', {})

    # ── ⭐ 自選股多頭訊號即時警報雷達 ──────────────────────────
    alerts = []
    for c in codes:
        if c in screener_items:
            s_info = screener_items[c]
            sig_parts = []
            vr = s_info.get('vol_ratio', 1.0)
            cup = s_info.get('consec_up', 0)
            brk = s_info.get('is_breakout_20d', False)
            pct = s_info.get('pct_change', 0.0)

            if vr >= 1.8 and pct > 0:
                sig_parts.append(f"🔥爆量{vr}x")
            if cup >= 2:
                sig_parts.append(f"📈連{cup}紅")
            if brk:
                sig_parts.append("🚀創20日高")

            if sig_parts:
                p_col = "#ff3b5c" if pct >= 0 else "#00e676"
                alerts.append(
                    f'<a href="/?stock={c}" target="_self" style="text-decoration:none !important; display:inline-block; background:#1C2436; border:1px solid #38BDF8; border-radius:8px; padding:6px 12px; margin:3px 2px;">'
                    f'<span style="color:#FFF; font-weight:bold; font-size:16px;">{s_info.get("name", c)} ({c})</span> '
                    f'<span style="color:{p_col}; font-weight:bold; font-size:15px; margin-left:4px;">{pct:+.2f}%</span> '
                    f'<span style="color:#FFD600; font-size:14px; margin-left:6px;">{" ｜ ".join(sig_parts)}</span>'
                    f'</a>'
                )

    if alerts:
        st.markdown(
            f"<div style='background:#101826; border-left:4px solid #38BDF8; border-radius:8px; padding:10px 14px; margin:10px 0 14px 0;'>"
            f"<div style='color:#38BDF8; font-weight:bold; font-size:17.5px; margin-bottom:6px;'>🚨 今日自選股強勢訊號雷達（{len(alerts)} 檔觸發）</div>"
            f"<div style='display:flex; flex-wrap:wrap; gap:4px;'>{''.join(alerts)}</div>"
            f"</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            "<div style='background:#0B1320; border-left:4px solid #10B981; border-radius:6px; padding:8px 12px; margin:10px 0 12px 0; font-size:15px; color:#A7F3D0;'>"
            "🛡️ <b>今日自選股訊號雷達：</b>持股走勢平穩，目前暫無短線暴量過熱或異動訊號。"
            "</div>",
            unsafe_allow_html=True
        )

    concept_data = load_concept_data()
    rows_data = []
    for s in watchlist:
        c = s['code']
        q = quotes_map.get(c, {})
        tags = get_concept_tags_for_stock(c, concept_data)
        note_str = s.get('note', '').strip()
        role_display = note_str if note_str else (tags[0] if tags else '')
        rows_data.append({
            'code': c,
            'name': q.get('name') or s.get('name', c),
            'market_short': q.get('market_short', '市'),
            'role': role_display,
            'open': q.get('open', 0.0),
            'high': q.get('high', 0.0),
            'low': q.get('low', 0.0),
            'close': q.get('close', 0.0),
            'prev_close': q.get('prev_close', 0.0),
            'change': q.get('change', 0.0),
            'pct_change': q.get('pct_change', 0.0),
            'sparkline': q.get('sparkline', []),
        })

    table_html = render_quote_table_html(rows_data)
    st.markdown(table_html, unsafe_allow_html=True)
    st.caption("💡 點擊任一列股票即可直接進入完整深度分析！")

    with st.expander("📝 編輯自選股備註與移除管理", expanded=False):
        for idx, stock in enumerate(watchlist):
            scode = stock['code']
            cinfo = get_tw_stock_chinese_info(scode)
            sname = cinfo.get('name', stock.get('name', scode))
            mc1, mc2, mc3 = st.columns([1.5, 2.5, 1.0])
            with mc1:
                st.markdown(f"**{sname} ({scode})**")
            with mc2:
                updated_note = st.text_input(
                    "備註",
                    value=stock.get('note', ''),
                    key=f"note_{scode}",
                    placeholder="輸入買進價位或觀察重點...",
                    label_visibility="collapsed"
                )
                if updated_note != stock.get('note', ''):
                    watchlist[idx]['note'] = updated_note
                    save_watchlist(watchlist)
                    st.toast("💾 備註已儲存")
            with mc3:
                if st.button("🗑️ 移除", key=f"del_{scode}", use_container_width=True):
                    watchlist = [s for s in watchlist if s['code'] != scode]
                    save_watchlist(watchlist)
                    st.rerun()
