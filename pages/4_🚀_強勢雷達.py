"""
台股智慧策略選股與推薦清單頁面 (v2.0)
包含：
1. 🏆 今日精選推薦總榜（綜合評分 Top Picks：籌碼 ＋ 技術 ＋ 族群全面共振）
2. 🏛️ 籌碼面策略推薦（投信作帳認養、外資大戶鎖碼、土洋同步合買）
3. 🔥 技術面突破策略（爆量長紅攻擊、創 20 日新高、多頭連續上漲、王者共振）
4. 🏭 熱門族群領頭羊（題材資金輪動排行 ＋ 各族群指標龍頭股）
5. 💎 穩健多頭起漲股（均線多頭排列 MA5>MA10>MA20 ＋ 接近支撐低接）
6. ⚠️ 隔日沖避雷指南（識別隔日沖主力，防追高遭倒貨）
"""
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.helpers import get_common_css, get_top_nav_html, render_quote_table_html, inject_pwa_and_ux_enhancements
from modules.screener import (
    scan_market_signals, get_concept_rotation_rankings, get_concept_consecutive_rankings
)

st.set_page_config(page_title='台股智慧策略推薦清單', page_icon='🚀', layout='wide')
st.markdown(get_common_css(), unsafe_allow_html=True)
inject_pwa_and_ux_enhancements()
st.markdown(get_top_nav_html('radar'), unsafe_allow_html=True)

# ── 自訂卡片與推薦清單專屬樣式 ─────────────────────────────
st.markdown("""
<style>
.rec-card {
    background: #141722;
    border: 1px solid #232A3B;
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 12px;
    transition: all 0.15s ease-in-out;
}
.rec-card:hover {
    border-color: #00D4AA;
    background: #171B28;
}
.rec-badge-star {
    background: rgba(245, 158, 11, 0.15);
    border: 1px solid #F59E0B;
    color: #F59E0B;
    font-size: 13px;
    font-weight: bold;
    padding: 2px 8px;
    border-radius: 4px;
}
.rec-tag-chip {
    display: inline-block;
    background: #1E2433;
    border: 1px solid #333F54;
    color: #E2E8F0;
    font-size: 12px;
    padding: 2px 7px;
    border-radius: 4px;
    margin-right: 5px;
    margin-top: 2px;
}
.rec-tag-chip-bull {
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid #EF4444;
    color: #EF4444;
}
.rec-tag-chip-trust {
    background: rgba(245, 158, 11, 0.15);
    border: 1px solid #F59E0B;
    color: #F59E0B;
}
.rec-tag-chip-foreign {
    background: rgba(59, 130, 246, 0.15);
    border: 1px solid #3B82F6;
    color: #60A5FA;
}
.rec-btn-link {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: #1A2234;
    border: 1px solid #2D3B55;
    color: #00D4AA !important;
    text-decoration: none !important;
    font-size: 13px;
    font-weight: bold;
    padding: 5px 12px;
    border-radius: 6px;
    margin-right: 6px;
    transition: all 0.15s;
}
.rec-btn-link:hover {
    background: #00D4AA;
    color: #0B0E14 !important;
    border-color: #00D4AA;
}
.concept-rank-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #141722;
    border: 1px solid #232A3B;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 8px;
}
</style>
""", unsafe_allow_html=True)

# ── 標題與說明 ────────────────────────────────────────────
st.markdown(
    "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; margin-bottom:4px;'>"
    "<div>"
    "<h1 style='margin:0; font-size:26px;'>🚀 台股智慧策略選股與推薦清單</h1>"
    "<div style='color:#94A3B8; font-size:15px; margin-top:3px;'>"
    "⚡ 結合「三大法人籌碼鎖碼」×「技術均線爆量」×「熱門概念族群輪動」×「隔日沖風險避坑」多維度大數據精選"
    "</div>"
    "</div>"
    "</div>",
    unsafe_allow_html=True
)

c_refresh, c_tip = st.columns([1.3, 3.7])
with c_refresh:
    force_btn = st.button("🔄 重新掃描市場數據", use_container_width=True)
with c_tip:
    st.caption("💡 每日盤後定時自動演算，點擊任一檔股票即可一鍵進入「個股完整分析」或「隔日沖分點研究」！")

with st.spinner("正在演算全市場多頭特徵、法人買賣超與族群輪動強度..."):
    screener_data = scan_market_signals(force_refresh=force_btn)

top_recs = screener_data.get('top_recommendations', [])
trust_picks = screener_data.get('trust_picks', [])
foreign_picks = screener_data.get('foreign_picks', [])
dual_bull_picks = screener_data.get('dual_bull_picks', [])
vol_surge_list = screener_data.get('volume_surge', [])
consec_up_list = screener_data.get('consecutive_up', [])
breakout_list  = screener_data.get('breakout', [])
steady_ma_picks = screener_data.get('steady_ma_picks', [])
all_star_list = screener_data.get('all_star', [])
concept_rankings = screener_data.get('concept_rankings', [])
if not concept_rankings:
    concept_rankings = get_concept_rotation_rankings(screener_data)

strong_breakouts = screener_data.get('strong_breakouts', [])
strong_continuing = screener_data.get('strong_continuing', [])
strong_initial = screener_data.get('strong_initial', [])
concept_consec_rankings = screener_data.get('concept_consecutive_rankings', [])
if not concept_consec_rankings:
    concept_consec_rankings = get_concept_consecutive_rankings(screener_data)

total_scanned  = screener_data.get('total_scanned', 0)

# 冠軍族群資訊
top_consec_name = concept_consec_rankings[0]['concept_name'] if concept_consec_rankings else "運算中"
top_consec_days = concept_consec_rankings[0]['consec_days'] if concept_consec_rankings else 0
top_consec_pct  = concept_consec_rankings[0]['cum_pct'] if concept_consec_rankings else 0.0

# ── 頂部 5 大核心數據指標卡 ────────────────────────────────
st.markdown(
    f"<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(130px, 1fr)); gap:8px; margin:10px 0 14px 0;'>"
    f"<div style='background:#181A26; border-left:4px solid #FF4444; border-radius:8px; padding:10px 12px;'>"
    f"<div style='color:#94A3B8; font-size:13px;'>🔥 族群連漲冠軍</div>"
    f"<div style='font-size:18px; font-weight:800; color:#FF5252; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{top_consec_name}</div>"
    f"<div style='color:#888; font-size:12px;'>連漲 {top_consec_days} 天 ({top_consec_pct:+}%)</div>"
    f"</div>"
    f"<div style='background:#181A26; border-left:4px solid #00D4AA; border-radius:8px; padding:10px 12px;'>"
    f"<div style='color:#94A3B8; font-size:13px;'>⚡ 真強勢突破</div>"
    f"<div style='font-size:22px; font-weight:800; color:#00D4AA;'>{len(strong_breakouts)} <span style='font-size:13px; font-weight:normal;'>檔</span></div>"
    f"<div style='color:#888; font-size:12px;'>主升 {len(strong_continuing)} ｜ 初升 {len(strong_initial)}</div>"
    f"</div>"
    f"<div style='background:#181A26; border-left:4px solid #F59E0B; border-radius:8px; padding:10px 12px;'>"
    f"<div style='color:#94A3B8; font-size:13px;'>👑 投信作帳認養</div>"
    f"<div style='font-size:22px; font-weight:800; color:#F59E0B;'>{len(trust_picks)} <span style='font-size:13px; font-weight:normal;'>檔</span></div>"
    f"<div style='color:#888; font-size:12px;'>投信重兵鎖碼</div>"
    f"</div>"
    f"<div style='background:#181A26; border-left:4px solid #3B82F6; border-radius:8px; padding:10px 12px;'>"
    f"<div style='color:#94A3B8; font-size:13px;'>🤝 土洋同步合買</div>"
    f"<div style='font-size:22px; font-weight:800; color:#60A5FA;'>{len(dual_bull_picks)} <span style='font-size:13px; font-weight:normal;'>檔</span></div>"
    f"<div style='color:#888; font-size:12px;'>外資投信聯手</div>"
    f"</div>"
    f"<div style='background:#181A26; border-left:4px solid #FFD700; border-radius:8px; padding:10px 12px;'>"
    f"<div style='color:#94A3B8; font-size:13px;'>🏆 今日精選推薦</div>"
    f"<div style='font-size:22px; font-weight:800; color:#FFD700;'>{len(top_recs)} <span style='font-size:13px; font-weight:normal;'>檔</span></div>"
    f"<div style='color:#888; font-size:12px;'>籌碼技術雙共振</div>"
    f"</div>"
    f"</div>",
    unsafe_allow_html=True
)

# ── 7 大核心策略頁籤 ──────────────────────────────────────────
t_consec, t_strong, t_rec, t_chip, t_tech, t_steady, t_guide = st.tabs([
    f"🔥 族群連漲總榜 ({len(concept_consec_rankings)})",
    f"⚡ 真強勢突破 ({len(strong_breakouts)})",
    f"🏆 今日精選推薦 ({len(top_recs)})",
    f"🏛️ 籌碼面策略 ({len(trust_picks) + len(foreign_picks)})",
    f"📈 技術面策略 ({len(vol_surge_list)})",
    f"💎 穩健多頭起漲 ({len(steady_ma_picks)})",
    f"⚠️ 隔日沖避雷指南"
])

def _render_screener_table_common(items_list, badge_gen_func, key_suffix=""):
    if not items_list:
        st.info("今日暫無完全符合此策略條件的股票。")
        return

    s_col1, s_col2 = st.columns([3.5, 1.5])
    with s_col1:
        kw = st.text_input("🔍 在結果中搜尋股票或概念", placeholder="輸入股名、代號或概念（如 聯亞、CoWoS、光通訊）", key=f"kw_{key_suffix}_{id(items_list)}")
    with s_col2:
        min_v = st.selectbox("最小成交量", [300, 500, 1000, 3000], index=0, key=f"min_v_{key_suffix}_{id(items_list)}", format_func=lambda x: f"成交量 ≥ {x:,} 張")

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


# ══════════════════════════════════════════════════════════
# Tab 1: 🔥 熱門族群連漲總榜 (由多到少排序)
# ══════════════════════════════════════════════════════════
with t_consec:
    st.markdown(
        "<div style='background:#181A26; border-left:4px solid #FF4444; border-radius:8px; padding:12px 16px; margin-bottom:12px; font-size:15px; color:#F5F5F4;'>"
        "🔥 <b>全市場熱門族群連漲動能總榜：</b>"
        "大數據自動追蹤全台股 75 個概念族群目前<b>【連續上漲天數（由多到少排序）】</b>與<b>【累積總漲幅】</b>！"
        "一眼揪出當前市場大資金連續抱團的主流題材。點擊任一族群卡片即可<b>展開查看全體成分股</b>（包含 👑 領頭羊、🏛️ 法人中軍、💎 穩健起漲股）！"
        "</div>",
        unsafe_allow_html=True
    )

    c_c1, c_c2, c_c3 = st.columns([2.5, 1.8, 1.5])
    with c_c1:
        c_kw = st.text_input("🔍 搜尋族群或股票", placeholder="輸入族群（如 CoWoS、PCB、散熱）或股名/代號", key="consec_kw")
    with c_c2:
        c_sort = st.selectbox("排序方式", ["🔥 連漲天數由多到少", "📈 累積總漲幅由大到小", "⚡ 今日漲幅由大到小"], key="consec_sort")
    with c_c3:
        c_min_days = st.selectbox("連漲門檻", [0, 1, 3, 5], format_func=lambda x: "全部族群" if x == 0 else f"連漲 ≥ {x} 天", key="consec_min_days")

    cur_consec = list(concept_consec_rankings)
    if c_min_days > 0:
        cur_consec = [x for x in cur_consec if x.get('consec_days', 0) >= c_min_days]

    if c_kw and c_kw.strip():
        ck_clean = c_kw.strip().lower()
        cur_consec = [
            x for x in cur_consec
            if ck_clean in str(x.get('concept_name', '')).lower()
            or ck_clean in str(x.get('big_category', '')).lower()
            or any(ck_clean in str(s.get('name', '')).lower() or ck_clean in str(s.get('code', '')) for s in x.get('stocks', []))
        ]

    if c_sort == "📈 累積總漲幅由大到小":
        cur_consec.sort(key=lambda x: x.get('cum_pct', 0), reverse=True)
    elif c_sort == "⚡ 今日漲幅由大到小":
        cur_consec.sort(key=lambda x: x.get('today_avg_pct', 0), reverse=True)
    else:
        cur_consec.sort(key=lambda x: (x.get('consec_days', 0), x.get('cum_pct', 0), x.get('today_avg_pct', 0)), reverse=True)

    st.caption(f"共符合 **{len(cur_consec)}** 個概念族群")

    if not cur_consec:
        st.info("暫無符合條件的族群。")
    else:
        for idx, citem in enumerate(cur_consec):
            cdays = citem['consec_days']
            c_pct = citem['cum_pct']
            t_pct = citem['today_avg_pct']
            t_cnt = citem['total_count']
            u_cnt = citem['up_count']
            u_ratio = citem['up_ratio']
            leader = citem.get('leader')
            inst_l = citem.get('inst_leader')
            cname = citem['concept_name']
            bcat = citem['big_category']

            if cdays >= 5:
                badge_style = "background:rgba(239,68,68,0.2); border:1px solid #EF4444; color:#FF5252;"
                icon_tag = "🔥"
            elif cdays >= 3:
                badge_style = "background:rgba(245,158,11,0.2); border:1px solid #F59E0B; color:#FBBF24;"
                icon_tag = "⚡"
            elif cdays >= 1:
                badge_style = "background:rgba(16,185,129,0.2); border:1px solid #10B981; color:#34D399;"
                icon_tag = "🌱"
            else:
                badge_style = "background:#1E2433; border:1px solid #333F54; color:#94A3B8;"
                icon_tag = "⚪"

            flame_badge = f"<span style='{badge_style} padding:3px 10px; border-radius:12px; font-weight:800; font-size:14px;'>{icon_tag} 連漲 {cdays} 天</span>"
            t_color = "#EF4444" if t_pct > 0 else ("#10B981" if t_pct < 0 else "#CBD5E1")
            c_color = "#EF4444" if c_pct > 0 else ("#10B981" if c_pct < 0 else "#CBD5E1")

            leader_chip = ""
            if leader:
                l_code = leader['code']
                l_name = leader['name']
                l_pct = leader['pct_change']
                l_col = "#EF4444" if l_pct > 0 else "#10B981"
                leader_chip = f"👑 領頭羊：<b style='color:#FFFFFF;'>{l_code} {l_name}</b> <span style='color:{l_col}; font-weight:bold;'>{l_pct:+.2f}%</span>"

            inst_chip = ""
            if inst_l and inst_l.get('inst_total_lots', 0) > 0:
                inst_chip = f"🏛️ 主力中軍：<b style='color:#FFFFFF;'>{inst_l['code']} {inst_l['name']}</b> <span style='color:#60A5FA; font-weight:bold;'>+{inst_l['inst_total_lots']:,.0f}張</span>"

            summary_chips = " ｜ ".join([x for x in [leader_chip, inst_chip] if x])

            exp_label = f"No.{idx+1}  {cname}  ({bcat})  ｜  連漲 {cdays} 天  ｜  累計 {c_pct:+}%  ｜  今日 {t_pct:+}%  ({u_cnt}/{t_cnt} 檔上漲)"

            with st.expander(exp_label, expanded=(idx < 2)):
                st.markdown(
                    f"<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:8px; padding:8px 12px; background:#1C2333; border-radius:6px;'>"
                    f"<div>{flame_badge} <span style='margin-left:10px; font-size:14px; color:#E2E8F0;'>累計漲幅 <b style='color:{c_color};'>{c_pct:+}%</b> ｜ 今日平均 <b style='color:{t_color};'>{t_pct:+}%</b> ｜ 上漲比例 <b style='color:#FFD700;'>{u_ratio}%</b></span></div>"
                    f"<div style='font-size:13px; color:#94A3B8;'>{summary_chips}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

                # Render stock rows
                stocks_list = citem.get('stocks', [])
                s_rows = []
                for s in stocks_list:
                    s_code = s['code']
                    s_name = s['name']
                    s_role = s.get('role', '')

                    if leader and s_code == leader['code']:
                        role_badge = "👑 族群領頭羊"
                    elif inst_l and s_code == inst_l['code'] and s.get('inst_total_lots', 0) > 0:
                        role_badge = "🏛️ 主力中軍"
                    elif s.get('is_steady_ma'):
                        role_badge = "💎 穩健起漲"
                    elif s.get('is_breakout_20d'):
                        role_badge = "🚀 創20日新高"
                    elif s_role:
                        role_badge = s_role[:8]
                    else:
                        role_badge = "概念成分股"

                    s_rows.append({
                        'code': s_code,
                        'name': s_name,
                        'market_short': s.get('market_short', '市'),
                        'role': role_badge,
                        'open': s.get('close', 0.0),
                        'high': s.get('close', 0.0),
                        'low': s.get('close', 0.0),
                        'close': s.get('close', 0.0),
                        'prev_close': s.get('close', 0.0),
                        'change': round(s.get('close', 0.0) * s.get('pct_change', 0.0) / 100.0, 2),
                        'pct_change': s.get('pct_change', 0.0),
                        'sparkline': s.get('sparkline', [])
                    })

                st.markdown(render_quote_table_html(s_rows), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# Tab 2: ⚡ 全市場真強勢突破榜 (初升發動 vs. 主升續噴)
# ══════════════════════════════════════════════════════════
with t_strong:
    st.markdown(
        "<div style='background:#181A26; border-left:4px solid #00D4AA; border-radius:8px; padding:12px 16px; margin-bottom:12px; font-size:15px; color:#F5F5F4;'>"
        "⚡ <b>全市場真強勢突破說明：</b>"
        "突破 20 日整理新高 ＋ 成交量放大 1.8x 以上 ＋ 漲幅 ≥ 4.0% 實體大長紅（收盤逼近最高點，無長上影線）＋ 三大法人買超鎖碼！"
        "<b>不限題材庫、不限連漲天數</b>，精準鎖定全市場多頭火力最強的飆股！"
        "</div>",
        unsafe_allow_html=True
    )

    st_col1, st_col2, st_col3 = st.columns([3.2, 1.4, 1.4])
    with st_col1:
        phase_choice = st.radio(
            "篩選分類",
            [
                f"全部強勢股 ({len(strong_breakouts)})",
                f"🔥 主升續噴 ({len(strong_continuing)})",
                f"🌱 初升發動 ({len(strong_initial)})"
            ],
            horizontal=True,
            key="strong_phase_choice"
        )
    with st_col2:
        st_sort = st.selectbox("排序依據", ["依今日漲幅最高", "依爆量倍數最大", "依法人買超最多"], key="st_sort")
    with st_col3:
        st_min_v = st.selectbox("最低成交量", [800, 1500, 3000], format_func=lambda x: f"成交量 ≥ {x:,} 張", key="st_min_v")

    if "主升續噴" in phase_choice:
        cur_strong = list(strong_continuing)
    elif "初升發動" in phase_choice:
        cur_strong = list(strong_initial)
    else:
        cur_strong = list(strong_breakouts)

    cur_strong = [x for x in cur_strong if x.get('volume_lots', 0) >= st_min_v]

    if st_sort == "依爆量倍數最大":
        cur_strong.sort(key=lambda x: x.get('vol_ratio', 0), reverse=True)
    elif st_sort == "依法人買超最多":
        cur_strong.sort(key=lambda x: x.get('inst_total_lots', 0), reverse=True)
    else:
        cur_strong.sort(key=lambda x: x.get('pct_change', 0), reverse=True)

    st.caption(f"共篩選出 **{len(cur_strong)}** 檔真強勢標的")
    if not cur_strong:
        st.info("目前無符合條件的強勢股。")
    else:
        _render_screener_table_common(
            cur_strong,
            lambda x: f"{x.get('breakout_phase_label', '強勢突破')} ｜ 爆量{x.get('vol_ratio', 1.0)}x",
            key_suffix="strong_table"
        )


# ══════════════════════════════════════════════════════════
# Tab 3: 🏆 今日精選推薦總榜 (Top Picks)
# ══════════════════════════════════════════════════════════
with t_rec:
    st.markdown(
        "<div style='background:#181A26; border-left:4px solid #FFD700; border-radius:8px; padding:12px 16px; margin-bottom:12px; font-size:15px; color:#F5F5F4;'>"
        "🏆 <b>今日智慧綜合推薦榜說明：</b>"
        "系統運用量化多因子評分模型，綜合加權<b>【三大法人籌碼力度 40%】</b>＋<b>【技術面均線與爆量突破 30%】</b>＋<b>【熱門概念族群共振 20%】</b>＋<b>【量能流動性 10%】</b>，"
        "自動挑選今日全市場表現最剽悍、多頭結構最扎實的領先指標標的！"
        "</div>",
        unsafe_allow_html=True
    )

    if not top_recs:
        st.info("今日暫無足夠多頭共振標的，建議參考其他單一策略頁籤。")
    else:
        for idx, item in enumerate(top_recs[:12]):
            code = item['code']
            name = item['name']
            close_p = item['close']
            pct = item['pct_change']
            c_color = "#EF4444" if pct > 0 else ("#10B981" if pct < 0 else "#CBD5E1")
            c_sign = "+" if pct > 0 else ""

            # 標籤
            tag_badges = "".join([f"<span class='rec-tag-chip rec-tag-chip-bull'>{t}</span>" for t in item.get('rec_tags', [])])
            concept_badges = "".join([f"<span class='rec-tag-chip'>{t}</span>" for t in item.get('tags', [])[:2]])

            f_str = f"外資 <b style='color:{'#EF4444' if item['foreign_lots'] > 0 else '#10B981'};'>{item['foreign_lots']:+,.0f}</b> 張"
            t_str = f"投信 <b style='color:{'#EF4444' if item['trust_lots'] > 0 else '#10B981'};'>{item['trust_lots']:+,.0f}</b> 張"
            tot_str = f"三大法人合計 <b style='color:#FFD700;'>{item['inst_total_lots']:+,.0f}</b> 張"

            card_html = (
                f"<div class='rec-card'>"
                f"<div style='display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:8px;'>"
                f"<div>"
                f"<div style='display:flex; align-items:center; gap:8px; flex-wrap:wrap;'>"
                f"<span style='font-size:18px; font-weight:bold; color:#FFFFFF;'>{idx+1}. {code} {name}</span>"
                f"<span style='font-size:12px; color:#94A3B8; background:#1C202C; padding:1px 6px; border-radius:4px;'>{item['market_short']}</span>"
                f"<span class='rec-badge-star'>{item['stars']} {item['composite_score']}分 · {item['star_label']}</span>"
                f"</div>"
                f"<div style='margin-top:6px;'>"
                f"{tag_badges} {concept_badges}"
                f"</div>"
                f"</div>"
                f"<div style='text-align:right;'>"
                f"<div style='font-size:22px; font-weight:bold; color:{c_color};'>{close_p:,.2f} <span style='font-size:15px;'>({c_sign}{pct:.2f}%)</span></div>"
                f"<div style='font-size:12px; color:#94A3B8; margin-top:2px;'>成交量 {item['volume_lots']:,} 張 (量比 {item['vol_ratio']}x)</div>"
                f"</div>"
                f"</div>"
                f"<div style='margin-top:10px; background:#10131C; border-radius:6px; padding:8px 12px; font-size:13.5px; color:#E2E8F0; line-height:1.6;'>"
                f"💡 <b>核心邏輯：</b>{item['recommend_reason']}"
                f"</div>"
                f"<div style='margin-top:8px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; font-size:12.5px; color:#94A3B8;'>"
                f"<div>{f_str} ｜ {t_str} ｜ {tot_str}</div>"
                f"<div>建議觀察區間：<b style='color:#E2E8F0;'>{item['watch_price']}</b> 元 ｜ 參考防守停損：<b style='color:#EF4444;'>{item['support_price']}</b> 元</div>"
                f"</div>"
                f"<div style='margin-top:10px; display:flex; gap:8px;'>"
                f"<a href='/?stock={code}' target='_blank' class='rec-btn-link'>📊 個股完整分析</a>"
                f"<a href='/隔日沖與分點研究?stock={code}' target='_blank' class='rec-btn-link'>🎯 查分點與隔日沖</a>"
                f"</div>"
                f"</div>"
            )
            st.markdown(card_html, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# Tab 2: 🏛️ 籌碼面策略推薦
# ══════════════════════════════════════════════════════════
with t_chip:
    st.markdown(
        "<div style='background:#181A26; border-left:4px solid #3B82F6; border-radius:8px; padding:10px 14px; margin-bottom:10px; font-size:15px; color:#F5F5F4;'>"
        "🏛️ <b>籌碼面策略說明：</b>"
        "在台股市場，「跟著聰明錢走」是波段勝率最高的法則。投信往往擅長挖掘中小型潛力飆股，外資則掌控權值與大波段行情，土洋同步合買更是市場最強的多方共識！"
        "</div>",
        unsafe_allow_html=True
    )

    t_cp_sync, t_cp_trust, t_cp_foreign = st.tabs([
        f"🤝 土洋同步合買 ({len(dual_bull_picks)})",
        f"👑 投信作帳認養 ({len(trust_picks)})",
        f"🏛️ 外資主力鎖碼 ({len(foreign_picks)})"
    ])

    with t_cp_sync:
        st.caption("外資與投信當日雙雙站買方，籌碼高度集中，多方力道最強！")
        _render_screener_table_common(
            dual_bull_picks,
            lambda x: f"🤝外資+{x['foreign_lots']:,}｜投信+{x['trust_lots']:,}",
            key_suffix="dual"
        )

    with t_cp_trust:
        st.caption("投信買超佔比顯著（投本比高），中小型股季底作帳、法人認養行情指標！")
        _render_screener_table_common(
            trust_picks,
            lambda x: f"👑投信買{x['trust_lots']:,}張 (佔量{x['trust_ratio']}%)",
            key_suffix="trust"
        )

    with t_cp_foreign:
        st.caption("外資大舉掃貨敲進，主力資金大部位回補鎖碼！")
        _render_screener_table_common(
            foreign_picks,
            lambda x: f"🏛️外資買{x['foreign_lots']:,}張 (佔量{x['foreign_ratio']}%)",
            key_suffix="foreign"
        )


# ══════════════════════════════════════════════════════════
# Tab 3: 🔥 技術面策略推薦
# ══════════════════════════════════════════════════════════
with t_tech:
    st.markdown(
        "<div style='background:#181A26; border-left:4px solid #FF3B5C; border-radius:8px; padding:10px 14px; margin-bottom:10px; font-size:15px; color:#F5F5F4;'>"
        "🔥 <b>技術面策略說明：</b>"
        "「量是價的先行指標，突破是趨勢的起跑信號」。結合量能倍增、連紅推升與創 20 日波段新高，精準掌握起漲發動點！"
        "</div>",
        unsafe_allow_html=True
    )

    t_tc_all, t_tc_vol, t_tc_brk, t_tc_up = st.tabs([
        f"👑 王者共振飆股 ({len(all_star_list)})",
        f"🔥 今日量增暴量 ({len(vol_surge_list)})",
        f"🚀 創 20 日新高 ({len(breakout_list)})",
        f"📈 多頭連續上漲 ({len(consec_up_list)})"
    ])

    with t_tc_all:
        st.caption("同時滿足【爆量 1.8x 以上】＋【多頭連漲或創高突破】，短線攻擊力道最強！")
        _render_screener_table_common(
            all_star_list,
            lambda x: f"👑爆量{x['vol_ratio']}x｜連{x['consec_up']}紅" if x['consec_up'] >= 2 else f"👑爆量{x['vol_ratio']}x｜創新高",
            key_suffix="allstar"
        )

    with t_tc_vol:
        st.caption("今日成交量達過去 5 日均量的 1.8 倍以上且收紅，大單主力點火起跑！")
        _render_screener_table_common(
            vol_surge_list,
            lambda x: f"🔥爆量{x['vol_ratio']}x (量{x['volume_lots']:,}張)",
            key_suffix="vol"
        )

    with t_tc_brk:
        st.caption("突破過去 20 個交易日最高點，克服盤整壓力，上方無沉重套牢賣壓！")
        _render_screener_table_common(
            breakout_list,
            lambda x: f"🚀突破20日新高｜量{x['vol_ratio']}x",
            key_suffix="breakout"
        )

    with t_tc_up:
        st.caption("連續 3 天以上收紅推升，沿均線穩定上攻，籌碼沉澱穩定！")
        _render_screener_table_common(
            consec_up_list,
            lambda x: f"📈連續上漲 {x['consec_up']} 天",
            key_suffix="consec"
        )





# ══════════════════════════════════════════════════════════
# Tab 5: 💎 穩健多頭起漲
# ══════════════════════════════════════════════════════════
with t_steady:
    st.markdown(
        "<div style='background:#181A26; border-left:4px solid #10B981; border-radius:8px; padding:10px 14px; margin-bottom:10px; font-size:15px; color:#F5F5F4;'>"
        "💎 <b>穩健多頭起漲說明：</b>"
        "不想追高飆股？此策略專門篩選<b>【短中長期均線呈多頭排列（MA5 > MA10 > MA20）】</b>，"
        "且今日漲幅溫和收斂（0% ~ 4.2%）、股價貼近 5 日或 10 日均線回測有守的標的，具備優異的風險報酬比與防守停損點！"
        "</div>",
        unsafe_allow_html=True
    )
    _render_screener_table_common(
        steady_ma_picks,
        lambda x: f"💎均線多頭｜守MA10 {x['support_price']}元",
        key_suffix="steady"
    )


# ══════════════════════════════════════════════════════════
# Tab 6: ⚠️ 隔日沖避雷指南
# ══════════════════════════════════════════════════════════
with t_guide:
    st.markdown(
        "<div style='background:#181A26; border-left:4px solid #F59E0B; border-radius:8px; padding:12px 16px; margin-bottom:12px; font-size:15px; color:#F5F5F4;'>"
        "⚠️ <b>台股散戶必讀：隔日沖主力陷阱與自保心法</b>"
        "</div>",
        unsafe_allow_html=True
    )

    st.markdown("""
    ### 🎯 什麼是隔日沖？為什麼常讓散戶被套？
    在台股中，有特定超大型主力分點（如：**凱基台北、美林證券、元大土城永寧、富邦建國、虎尾幫** 等），他們的操盤模式為：
    1. **盤中點火鎖漲停**：利用數千甚至上萬張大單，在盤中暴力拉抬敲進，將熱門強勢股直接鎖在漲停板，吸引散戶在尾盤與盤後排隊搶買。
    2. **隔天開盤全倒出**：次日開盤利用散戶昨夜追價的興奮情緒，在 **09:00 ~ 09:15** 早盤撮合開高之際，以市價或大單全數倒光獲利了結。
    3. **散戶受害型態**：股票開高後迅速急殺翻黑，留下一根長長的上影線，盲目追高的投資人直接當天套牢 5%~10%！

    ---

    ### 🛡️ 實戰 3 大自保原則：
    1. **追強勢股前，先查「分點研究」**：
       - 進入系統的 **【🎯 隔日沖與分點研究】** 頁面，輸入欲操作之股票。
       - 若買方第一名赫然出現「凱基台北」或「美林」且佔比超過當日量 20% 以上，即高度暗示此為隔日沖點火！
    2. **隔日早盤切勿開盤直接市價追高**：
       - 若前一日為隔日沖鎖漲停，次日開盤 **09:00 ~ 09:20 嚴禁盲目追多**！
       - 應觀察開盤 15~20 分鐘後，隔日沖籌碼是否已洗淨出清，且股價是否有守在市場均價線 (VWAP) 之上。
    3. **波段操作優先挑選「投信認養」或「土洋同步」**：
       - 投信基金有持股法定閉鎖與季底結算壓力，買進通常是連買數天甚至數週，跟隨投信坐轎的波段穩定度遠高於隔日沖短線游資！
    """)
