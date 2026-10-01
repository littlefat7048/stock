"""
台股強勢飆股雷達頁面
包含：
1. 王者共振飆股（暴量 ＋ 連漲 ＋ 創 20 日新高三合一）
2. 今日量增暴量（成交量爆增 1.8~3 倍以上之攻擊股）
3. 多頭連續上漲（連續 3~5 日收紅盤，強勢沿均線上攻）
4. 創 20 日新高突破股（帶量突破波段整理平台）
"""
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.helpers import get_common_css, get_top_nav_html, render_quote_table_html
from modules.screener import scan_market_signals

st.set_page_config(page_title='台股強勢飆股雷達', page_icon='🚀', layout='wide')
st.markdown(get_common_css(), unsafe_allow_html=True)
st.markdown(get_top_nav_html('radar'), unsafe_allow_html=True)

# ── 標題與說明 ────────────────────────────────────────────
st.markdown(
    "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; margin-bottom:4px;'>"
    "<div>"
    "<h1 style='margin:0; font-size:26px;'>🚀 台股今日強勢飆股雷達</h1>"
    "<div style='color:#94A3B8; font-size:16px; margin-top:2px;'>⚡ 0 API 消耗・全自動統計：今日量增暴量 ｜ 多頭連續上漲 ｜ 創波段新高 ｜ 主力共振</div>"
    "</div>"
    "</div>",
    unsafe_allow_html=True
)

c_refresh, c_tip = st.columns([1.2, 3.8])
with c_refresh:
    force_btn = st.button("🔄 重新掃描市場數據", use_container_width=True)
with c_tip:
    st.caption("💡 每日盤後定時自動演算，點擊任一檔股票即可一鍵進入「個股完整分析」！")

with st.spinner("正在演算全市場多頭特徵與成交量能..."):
    screener_data = scan_market_signals(force_refresh=force_btn)

all_star_list = screener_data.get('all_star', [])
vol_surge_list = screener_data.get('volume_surge', [])
consec_up_list = screener_data.get('consecutive_up', [])
breakout_list  = screener_data.get('breakout', [])
total_scanned  = screener_data.get('total_scanned', 0)

# ── 頂部 4 大核心數據指標卡 ────────────────────────────────
st.markdown(
    f"<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(140px, 1fr)); gap:8px; margin:10px 0 14px 0;'>"
    f"<div style='background:#181A26; border-left:4px solid #FFD700; border-radius:8px; padding:10px 12px;'>"
    f"<div style='color:#94A3B8; font-size:14px;'>👑 王者共振飆股</div>"
    f"<div style='font-size:24px; font-weight:800; color:#FFD700;'>{len(all_star_list)} <span style='font-size:14px; font-weight:normal;'>檔</span></div>"
    f"<div style='color:#888; font-size:12px;'>暴量 ＋ 連漲 ＋ 創高</div>"
    f"</div>"
    f"<div style='background:#181A26; border-left:4px solid #FF3B5C; border-radius:8px; padding:10px 12px;'>"
    f"<div style='color:#94A3B8; font-size:14px;'>🔥 今日暴量長紅</div>"
    f"<div style='font-size:24px; font-weight:800; color:#FF3B5C;'>{len(vol_surge_list)} <span style='font-size:14px; font-weight:normal;'>檔</span></div>"
    f"<div style='color:#888; font-size:12px;'>量增 1.8 倍 且收紅</div>"
    f"</div>"
    f"<div style='background:#181A26; border-left:4px solid #00E5FF; border-radius:8px; padding:10px 12px;'>"
    f"<div style='color:#94A3B8; font-size:14px;'>📈 多頭連續上漲</div>"
    f"<div style='font-size:24px; font-weight:800; color:#00E5FF;'>{len(consec_up_list)} <span style='font-size:14px; font-weight:normal;'>檔</span></div>"
    f"<div style='color:#888; font-size:12px;'>連漲 3 天以上強攻</div>"
    f"</div>"
    f"<div style='background:#181A26; border-left:4px solid #B388FF; border-radius:8px; padding:10px 12px;'>"
    f"<div style='color:#94A3B8; font-size:14px;'>🚀 創 20 日新高</div>"
    f"<div style='font-size:24px; font-weight:800; color:#B388FF;'>{len(breakout_list)} <span style='font-size:14px; font-weight:normal;'>檔</span></div>"
    f"<div style='color:#888; font-size:12px;'>突破波段整理平台</div>"
    f"</div>"
    f"</div>",
    unsafe_allow_html=True
)

# ── 4 大策略分頁 ──────────────────────────────────────────
t_all, t_vol, t_up, t_brk = st.tabs([
    f"👑 王者共振飆股 ({len(all_star_list)})",
    f"🔥 今日量增暴量 ({len(vol_surge_list)})",
    f"📈 多頭連續上漲 ({len(consec_up_list)})",
    f"🚀 創20日新高 ({len(breakout_list)})"
])

def _render_screener_table(items_list, badge_gen_func):
    if not items_list:
        st.info("今日暫無完全符合此策略條件的股票。")
        return

    # 搜尋過濾框
    s_col1, s_col2 = st.columns([3.5, 1.5])
    with s_col1:
        kw = st.text_input("🔍 在結果中搜尋股票或概念", placeholder="輸入股名、代號或概念（如 聯亞、CoWoS、光通訊）", key=f"kw_{id(items_list)}")
    with s_col2:
        min_v = st.selectbox("最小成交量", [300, 500, 1000, 3000], index=0, key=f"min_v_{id(items_list)}", format_func=lambda x: f"成交量 ≥ {x:,} 張")

    filtered = [x for x in items_list if x.get('volume_lots', 0) >= min_v]
    if kw and kw.strip():
        k_clean = kw.strip().lower()
        filtered = [
            x for x in filtered
            if k_clean in str(x.get('code', '')).lower()
            or k_clean in str(x.get('name', '')).lower()
            or any(k_clean in str(t).lower() for t in x.get('tags', []))
        ]

    st.caption(f"共篩選出 **{len(filtered)}** 檔標的")
    if not filtered:
        st.warning("沒有符合過濾條件的股票。")
        return

    rows = []
    for item in filtered:
        badge_text = badge_gen_func(item)
        rows.append({
            'code': item['code'],
            'name': item['name'],
            'market_short': item['market_short'],
            'role': badge_text,
            'open': item['open'],
            'high': item['high'],
            'low': item['low'],
            'close': item['close'],
            'prev_close': item['prev_close'],
            'change': item['change'],
            'pct_change': item['pct_change'],
            'sparkline': item.get('sparkline', [])
        })

    st.markdown(render_quote_table_html(rows), unsafe_allow_html=True)


with t_all:
    st.markdown(
        "<div style='background:#1C1917; border-left:4px solid #FFD700; border-radius:8px; padding:10px 14px; margin-bottom:10px; font-size:16px; color:#F5F5F4;'>"
        "👑 <b>王者共振策略說明：</b>同時滿足<b>「今日量增爆量 1.8x 以上」</b>且<b>「多頭連漲 2 天以上 或 創 20 日波段新高」</b>！"
        "代表主力買盤積極攻擊推進，多頭氣勢最強、勝率最高！"
        "</div>",
        unsafe_allow_html=True
    )
    _render_screener_table(
        all_star_list,
        lambda x: f"👑爆量{x['vol_ratio']}x｜連{x['consec_up']}紅" if x['consec_up'] >= 2 else f"👑爆量{x['vol_ratio']}x｜創新高"
    )

with t_vol:
    st.markdown(
        "<div style='background:#1C1917; border-left:4px solid #FF3B5C; border-radius:8px; padding:10px 14px; margin-bottom:10px; font-size:16px; color:#F5F5F4;'>"
        "🔥 <b>今日量增暴量說明：</b>今日成交量達到過去 5 天平均的 <b>1.8 倍至數倍以上</b>，且當日收紅（漲幅 > 1.5%）。"
        "量是價的先行指標，爆量長紅通常是法人或大戶點火起跑的關鍵攻擊信號！"
        "</div>",
        unsafe_allow_html=True
    )
    _render_screener_table(
        vol_surge_list,
        lambda x: f"🔥爆量{x['vol_ratio']}x (量{x['volume_lots']:,}張)"
    )

with t_up:
    st.markdown(
        "<div style='background:#1C1917; border-left:4px solid #00E5FF; border-radius:8px; padding:10px 14px; margin-bottom:10px; font-size:16px; color:#F5F5F4;'>"
        "📈 <b>多頭連續上漲說明：</b>連續 <b>3 天、4 天甚至 5 天以上</b>收盤價持續推升。"
        "通常沿著 5 日或 10 日均線穩定推升，代表盤面籌碼極度安定、主力不輕易拋售！"
        "</div>",
        unsafe_allow_html=True
    )
    _render_screener_table(
        consec_up_list,
        lambda x: f"📈連續上漲 {x['consec_up']} 天"
    )

with t_brk:
    st.markdown(
        "<div style='background:#1C1917; border-left:4px solid #B388FF; border-radius:8px; padding:10px 14px; margin-bottom:10px; font-size:16px; color:#F5F5F4;'>"
        "🚀 <b>創 20 日新高說明：</b>今日收盤價突破過去 20 個交易日的最高點，突破整理平台，上方無近期套牢壓力！"
        "</div>",
        unsafe_allow_html=True
    )
    _render_screener_table(
        breakout_list,
        lambda x: f"🚀突破20日新高｜量{x['vol_ratio']}x"
    )
