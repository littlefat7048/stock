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
from utils.helpers import get_common_css, get_top_nav_html, render_quote_table_html
from modules.screener import scan_market_signals, get_concept_rotation_rankings

st.set_page_config(page_title='台股智慧策略推薦清單', page_icon='🚀', layout='wide')
st.markdown(get_common_css(), unsafe_allow_html=True)
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

total_scanned  = screener_data.get('total_scanned', 0)

# ── 頂部 5 大核心數據指標卡 ────────────────────────────────
st.markdown(
    f"<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(130px, 1fr)); gap:8px; margin:10px 0 14px 0;'>"
    f"<div style='background:#181A26; border-left:4px solid #FFD700; border-radius:8px; padding:10px 12px;'>"
    f"<div style='color:#94A3B8; font-size:13px;'>🏆 今日精選推薦</div>"
    f"<div style='font-size:22px; font-weight:800; color:#FFD700;'>{len(top_recs)} <span style='font-size:13px; font-weight:normal;'>檔</span></div>"
    f"<div style='color:#888; font-size:12px;'>籌碼技術雙共振</div>"
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
    f"<div style='background:#181A26; border-left:4px solid #FF3B5C; border-radius:8px; padding:10px 12px;'>"
    f"<div style='color:#94A3B8; font-size:13px;'>🔥 爆量突破長紅</div>"
    f"<div style='font-size:22px; font-weight:800; color:#FF3B5C;'>{len(vol_surge_list)} <span style='font-size:13px; font-weight:normal;'>檔</span></div>"
    f"<div style='color:#888; font-size:12px;'>量增 1.8x 以上</div>"
    f"</div>"
    f"<div style='background:#181A26; border-left:4px solid #10B981; border-radius:8px; padding:10px 12px;'>"
    f"<div style='color:#94A3B8; font-size:13px;'>🏭 熱門強勢族群</div>"
    f"<div style='font-size:22px; font-weight:800; color:#34D399;'>{len(concept_rankings)} <span style='font-size:13px; font-weight:normal;'>群</span></div>"
    f"<div style='color:#888; font-size:12px;'>資金輪動領頭羊</div>"
    f"</div>"
    f"</div>",
    unsafe_allow_html=True
)

# ── 6 大核心策略頁籤 ──────────────────────────────────────────
t_rec, t_chip, t_tech, t_concept, t_steady, t_guide = st.tabs([
    f"🏆 今日精選推薦 ({len(top_recs)})",
    f"🏛️ 籌碼面策略 ({len(trust_picks) + len(foreign_picks)})",
    f"🔥 技術面策略 ({len(vol_surge_list)})",
    f"🏭 熱門族群領頭羊 ({len(concept_rankings)})",
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
# Tab 1: 🏆 今日精選推薦總榜 (Top Picks)
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
# Tab 4: 🏭 熱門族群領頭羊
# ══════════════════════════════════════════════════════════
with t_concept:
    st.markdown(
        "<div style='background:#181A26; border-left:4px solid #10B981; border-radius:8px; padding:10px 14px; margin-bottom:10px; font-size:15px; color:#F5F5F4;'>"
        "🏭 <b>熱門族群輪動說明：</b>"
        "「做股票要買主流，買主流要買龍頭」。大數據即時統計全台股 50+ 個核心概念族群之<b>【平均漲跌幅】</b>與<b>【上漲家數比例】</b>，"
        "自動找出今日資金最聚集的最強族群，並標記族群內的第 1 指標領頭羊！"
        "</div>",
        unsafe_allow_html=True
    )

    if not concept_rankings:
        st.info("正在統計概念族群數據...")
    else:
        for cr in concept_rankings[:15]:
            cname = cr['concept_name']
            bname = cr['big_category']
            avg_p = cr['avg_pct_change']
            u_ratio = cr['up_ratio']
            u_cnt = cr['up_count']
            t_cnt = cr['total_count']
            leader = cr.get('leader')

            p_color = "#EF4444" if avg_p > 0 else ("#10B981" if avg_p < 0 else "#CBD5E1")
            p_sign = "+" if avg_p > 0 else ""

            leader_info_html = ""
            if leader:
                l_code = leader['code']
                l_name = leader['name']
                l_pct = leader['pct_change']
                l_color = "#EF4444" if l_pct > 0 else "#10B981"
                leader_info_html = (
                    f"<div style='display:flex; align-items:center; gap:8px;'>"
                    f"<span style='color:#94A3B8; font-size:13px;'>族群領頭羊：</span>"
                    f"<a href='/?stock={l_code}' target='_blank' style='color:#FFFFFF; font-weight:bold; text-decoration:none; background:#1C202C; padding:3px 8px; border-radius:4px; border:1px solid #2D3342;'>"
                    f"🏆 {l_code} {l_name} <span style='color:{l_color}; font-weight:bold;'>+{l_pct:.2f}%</span>"
                    f"</a>"
                    f"</div>"
                )

            row_html = (
                f"<div class='concept-rank-row'>"
                f"<div style='display:flex; align-items:center; gap:12px; flex-wrap:wrap;'>"
                f"<div>"
                f"<span style='font-size:16px; font-weight:bold; color:#FFFFFF;'>{cname}</span>"
                f"<span style='font-size:12px; color:#94A3B8; background:#181A26; padding:1px 6px; border-radius:4px; margin-left:6px;'>{bname}</span>"
                f"</div>"
                f"<div style='font-size:13px; color:#94A3B8;'>"
                f"上漲比例 <b style='color:#FFD700;'>{u_ratio}%</b> ({u_cnt}/{t_cnt} 家收紅)"
                f"</div>"
                f"</div>"
                f"<div style='display:flex; align-items:center; gap:16px; flex-wrap:wrap;'>"
                f"{leader_info_html}"
                f"<div style='font-size:17px; font-weight:bold; color:{p_color}; min-width:80px; text-align:right;'>"
                f"均 {p_sign}{avg_p:.2f}%"
                f"</div>"
                f"</div>"
                f"</div>"
            )
            st.markdown(row_html, unsafe_allow_html=True)


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
