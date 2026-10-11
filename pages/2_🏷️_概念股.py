"""
台股熱門概念股與產業鏈看盤頁面
包含：
1. 🏷️ 熱門題材即時看盤（專業看盤 App 報價走勢列表、資金輪動 TOP 5、快速搜尋）
2. 🌐 上中下游產業鏈地圖（光通訊 CPO、CoWoS 先進封裝、AI 伺服器水冷 流程圖）
3. 🇺🇸 美股巨頭對標台股供應鏈（Lumentum、Nvidia、Broadcom、Apple、Tesla 對標台廠與即時報價）
"""
import importlib
import urllib.parse
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import utils.helpers
import modules.data_fetcher
importlib.reload(utils.helpers)
importlib.reload(modules.data_fetcher)

from utils.helpers import (
    load_concept_data, load_supply_chain_data, get_common_css, get_top_nav_html,
    render_quote_table_html, render_supply_chain_stock_card, inject_pwa_and_ux_enhancements
)
from modules.data_fetcher import get_batch_quotes_with_intraday

st.set_page_config(page_title='台股概念與產業鏈', page_icon='🏷️', layout='wide')
st.markdown(get_common_css(), unsafe_allow_html=True)
inject_pwa_and_ux_enhancements()
st.markdown(get_top_nav_html('concept'), unsafe_allow_html=True)

# ── 專屬樣式（概念膠囊列 ＆ 產業鏈卡片） ──────────
st.markdown("""
<style>
.concept-pill-bar {
    display: flex;
    overflow-x: auto;
    white-space: nowrap;
    gap: 8px;
    padding: 6px 2px 10px 2px;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
}
.concept-pill-bar::-webkit-scrollbar {
    display: none;
}
.concept-pill-item {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 6px 15px;
    border-radius: 20px;
    background: #1B202B;
    border: 1px solid #2E3646;
    color: #D1D5DB !important;
    font-size:18px;
    font-weight: 600;
    text-decoration: none !important;
    flex-shrink: 0;
    transition: all 0.15s ease;
}
.concept-pill-item:hover {
    background: #262D3D;
    color: #FFFFFF !important;
}
.concept-pill-item.active {
    background: rgba(255, 92, 124, 0.22);
    border: 1.5px solid #FF758F;
    color: #FFD6DF !important;
    font-weight: 700;
    box-shadow: 0 0 10px rgba(255, 117, 143, 0.3);
}

.giant-pill-item {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 8px 16px;
    border-radius: 12px;
    background: #131826;
    border: 1px solid #25334D;
    color: #CBD5E1 !important;
    font-size: 17px;
    font-weight: 600;
    text-decoration: none !important;
    flex-shrink: 0;
    transition: all 0.15s ease;
}
.giant-pill-item:hover {
    background: #1E293B;
    border-color: #38BDF8;
    color: #FFF !important;
}
.giant-pill-item.active {
    background: rgba(56, 189, 248, 0.18);
    border: 1.5px solid #38BDF8;
    color: #38BDF8 !important;
    font-weight: 700;
    box-shadow: 0 0 10px rgba(56, 189, 248, 0.25);
}

/* 產業鏈流程箭頭 */
.chain-arrow-right {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    color: #38BDF8;
    padding: 0 4px;
}
.tier-header-box {
    background: #141A26;
    border: 1px solid #253046;
    border-radius: 8px;
    padding: 10px 12px;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

# ── 檢查外部跳轉模組模式（c_tab 或 giant） ──────────────────────
tab_options = ["🏷️ 熱門題材即時看盤", "🌐 上中下游產業鏈地圖", "🇺🇸 美股巨頭對標台股供應鏈"]

active_mode = st.session_state.get('selected_concept_tab', '')
if 'c_tab' in st.query_params:
    active_mode = str(st.query_params['c_tab']).strip()
elif 'giant' in st.query_params:
    active_mode = 'giants'

def_tab_idx = 0
if active_mode in ('chains', 'chain', 'map'):
    def_tab_idx = 1
elif active_mode in ('giants', 'giant', 'lumentum', 'nvidia', 'broadcom', 'lite', 'nvda'):
    def_tab_idx = 2

# 頂部模式切換單選鈕
view_mode = st.radio(
    "選擇概念股分析模式",
    tab_options,
    index=def_tab_idx,
    horizontal=True,
    label_visibility="collapsed"
)

# ==============================================================================
# 模式 1：🏷️ 熱門題材即時看盤
# ==============================================================================
if view_mode == "🏷️ 熱門題材即時看盤":
    concept_data = load_concept_data()
    categories = concept_data.get('概念分類', {})

    # 攤平所有子概念並建立索引
    all_sub_concepts = {}
    for big_cat, sub_cats in categories.items():
        if not isinstance(sub_cats, dict):
            continue
        for sub_name, cinfo in sub_cats.items():
            if isinstance(cinfo, dict) and cinfo.get('stocks'):
                all_sub_concepts[sub_name] = {
                    'big_cat': big_cat,
                    'desc': cinfo.get('desc', ''),
                    'stocks': cinfo.get('stocks', [])
                }

    PRIORITY_CONCEPTS = [
        ('FOPLP面板級封裝', 'FOPLP封裝'),
        ('玻璃基板', '玻璃基板'),
        ('光通訊CPO', '光通訊'),
        ('BBU備援電池', 'BBU電池'),
        ('半導體特用化學', '半導體特化'),
        ('CoWoS先進封裝', 'CoWoS'),
        ('AI伺服器', 'AI伺服器'),
        ('散熱模組', '散熱模組'),
        ('CCL高速銅箔基板', 'CCL銅箔基板'),
        ('伺服器連接與線材', '連接器/線材'),
        ('ASIC設計服務', 'ASIC設計'),
        ('InP磷化銦', 'InP'),
        ('封裝測試', '封測'),
        ('高價千金股', '高價股'),
        ('AI機器人與視覺', '機器人'),
        ('HBM高頻寬記憶體', 'HBM'),
        ('IC設計', 'IC設計'),
        ('ABF載板', 'ABF載板'),
        ('重電設備', '重電'),
        ('低軌衛星', '低軌衛星'),
    ]

    ordered_sub_keys = []
    short_label_map = {}
    for key, label in PRIORITY_CONCEPTS:
        if key in all_sub_concepts:
            ordered_sub_keys.append(key)
            short_label_map[key] = label

    for key in all_sub_concepts.keys():
        if key not in ordered_sub_keys:
            ordered_sub_keys.append(key)
            short_label_map[key] = key

    if not ordered_sub_keys:
        st.warning("目前沒有概念股資料。")
        st.stop()

    default_sub = '光通訊CPO' if '光通訊CPO' in all_sub_concepts else ordered_sub_keys[0]
    if 'c_sub' in st.query_params and st.query_params['c_sub'] in all_sub_concepts:
        st.session_state['selected_concept_sub'] = st.query_params['c_sub']

    current_sub = st.session_state.get('selected_concept_sub', default_sub)
    if current_sub not in all_sub_concepts:
        current_sub = default_sub

    # 🏆 今日最強資金輪動族群 TOP 5
    try:
        from modules.screener import get_concept_rotation_rankings
        rankings = get_concept_rotation_rankings()
    except Exception:
        rankings = []

    if rankings:
        top5 = rankings[:5]
        rank_items_html = []
        for idx, r in enumerate(top5):
            cname = r['concept_name']
            avg_pct = r['avg_pct_change']
            leader = r.get('leader') or {}
            l_name = leader.get('name', '')
            l_pct = leader.get('pct_change', 0.0)
            p_col = "#ff3b5c" if avg_pct >= 0 else "#00e676"
            enc_c = urllib.parse.quote(cname)
            active_cls = "border:2px solid #FFD700; background:#2A1B28;" if cname == current_sub else "border:1px solid #334155; background:#111622;"

            leader_str = f"領頭: {l_name} ({l_pct:+.1f}%)" if l_name else f"共 {r['total_count']} 檔"
            rank_items_html.append(
                f'<a href="/?c_sub={enc_c}" target="_self" style="text-decoration:none !important; flex-shrink:0;">'
                f'<div style="{active_cls} border-radius:8px; padding:6px 12px; min-width:145px; cursor:pointer;">'
                f'<div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">'
                f'<span style="color:#FFD700; font-weight:bold; font-size:14.5px;">NO.{idx+1} {short_label_map.get(cname, cname)}</span>'
                f'<span style="color:{p_col}; font-weight:bold; font-size:16px;">{avg_pct:+.2f}%</span>'
                f'</div>'
                f'<div style="color:#94A3B8; font-size:12px; margin-top:2px;">{leader_str}</div>'
                f'</div>'
                f'</a>'
            )

        st.markdown(
            f'<div style="margin-bottom:8px;">'
            f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">'
            f'<span style="color:#F472B6; font-weight:bold; font-size:16.5px;">🏆 今日最強資金輪動族群 TOP 5（點擊直達該族群）：</span>'
            f'<span style="color:#64748B; font-size:13px;">依族群平均漲幅排行</span>'
            f'</div>'
            f'<div style="display:flex; overflow-x:auto; gap:8px; padding-bottom:6px; scrollbar-width:none;">{"".join(rank_items_html)}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    # 橫向滑動概念膠囊列
    pills_html = []
    for k in ordered_sub_keys:
        cls = "concept-pill-item active" if k == current_sub else "concept-pill-item"
        lbl = short_label_map.get(k, k)
        encoded_k = urllib.parse.quote(k)
        pills_html.append(f'<a href="/?c_sub={encoded_k}" target="_self" class="{cls}">{lbl}</a>')

    st.markdown(f'<div class="concept-pill-bar">{"".join(pills_html)}</div>', unsafe_allow_html=True)

    # 收合式進階篩選與排序列
    with st.expander(f"📂 全部 {len(ordered_sub_keys)} 個分類選單 ／ 漲跌幅排序 ／ 搜尋股名", expanded=False):
        c_sel, c_sort, c_kw = st.columns([1.8, 1.4, 1.8])
        with c_sel:
            selected_from_box = st.selectbox(
                "選擇題材分類",
                ordered_sub_keys,
                index=ordered_sub_keys.index(current_sub),
                format_func=lambda k: f"🏷️ {short_label_map.get(k, k)}（{len(all_sub_concepts[k]['stocks'])}檔）",
                label_visibility="collapsed"
            )
            if selected_from_box != current_sub:
                st.session_state['selected_concept_sub'] = selected_from_box
                current_sub = selected_from_box
                st.rerun()

        with c_sort:
            sort_mode = st.selectbox(
                "排序方式",
                ["預設排序", "漲跌幅 ▼ (強勢)", "漲跌幅 ▲ (弱勢)", "成交價 ▼ (高價)", "成交價 ▲ (低價)"],
                label_visibility="collapsed"
            )

        with c_kw:
            kw = st.text_input(
                "搜尋股票或概念",
                placeholder="🔍 搜尋股名/代號（如 聯亞、3081）",
                label_visibility="collapsed"
            )

    if kw and kw.strip():
        kw_clean = kw.strip().lower()
        target_stocks = []
        seen_codes = set()
        for s_name, s_info in all_sub_concepts.items():
            for st_item in s_info['stocks']:
                c = str(st_item.get('code', ''))
                n = str(st_item.get('name', ''))
                r = str(st_item.get('role', ''))
                if (kw_clean in c.lower() or kw_clean in n.lower() or kw_clean in r.lower() or kw_clean in s_name.lower()):
                    if c not in seen_codes:
                        seen_codes.add(c)
                        target_stocks.append({
                            'code': c,
                            'name': n,
                            'role': f"{short_label_map.get(s_name, s_name)}｜{r}"
                        })
        header_title = f"🔍 搜尋「{kw.strip()}」結果（共 {len(target_stocks)} 檔）"
        header_desc = "點擊任一列即可進入個股全方位分析"
    else:
        sub_info = all_sub_concepts[current_sub]
        target_stocks = sub_info['stocks']
        header_title = f"📌 {short_label_map.get(current_sub, current_sub)}"
        header_desc = sub_info.get('desc', '')

    if not target_stocks:
        st.info("找不到符合條件的概念股，請嘗試其他關鍵字。")
    else:
        codes_to_fetch = [s['code'] for s in target_stocks[:30]]
        with st.spinner(f"正在載入 {header_title} 即時報價與走勢圖..."):
            quotes_map = get_batch_quotes_with_intraday(codes_to_fetch)

        rows_data = []
        for s in target_stocks[:30]:
            c = s['code']
            q = quotes_map.get(c, {})
            rows_data.append({
                'code': c,
                'name': q.get('name') or s.get('name', c),
                'market_short': q.get('market_short', '市'),
                'role': s.get('role', ''),
                'open': q.get('open', 0.0),
                'high': q.get('high', 0.0),
                'low': q.get('low', 0.0),
                'close': q.get('close', 0.0),
                'prev_close': q.get('prev_close', 0.0),
                'change': q.get('change', 0.0),
                'pct_change': q.get('pct_change', 0.0),
                'sparkline': q.get('sparkline', []),
            })

        if sort_mode == "漲跌幅 ▼ (強勢)":
            rows_data.sort(key=lambda x: x['pct_change'], reverse=True)
        elif sort_mode == "漲跌幅 ▲ (弱勢)":
            rows_data.sort(key=lambda x: x['pct_change'], reverse=False)
        elif sort_mode == "成交價 ▼ (高價)":
            rows_data.sort(key=lambda x: x['close'], reverse=True)
        elif sort_mode == "成交價 ▲ (低價)":
            rows_data.sort(key=lambda x: x['close'], reverse=False)

        valid_pcts = [r['pct_change'] for r in rows_data if r['close'] > 0]
        up_cnt = sum(1 for r in rows_data if r['change'] > 0)
        dn_cnt = sum(1 for r in rows_data if r['change'] < 0)
        avg_pct = (sum(valid_pcts) / len(valid_pcts)) if valid_pcts else 0.0
        avg_color = "#ff3b5c" if avg_pct > 0 else ("#00e676" if avg_pct < 0 else "#94A3B8")

        st.markdown(
            f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;padding:2px 4px;margin-bottom:2px;">'
            f'<div style="font-size:18px;color:#94A3B8;"><b style="color:#FAFAFA;">{header_title}</b>：{header_desc}</div>'
            f'<div style="font-size:17px;color:#94A3B8;">'
            f'平均 <b style="color:{avg_color};">{avg_pct:+.2f}%</b> ｜ '
            f'<span style="color:#ff3b5c;">▲{up_cnt}</span> / <span style="color:#00e676;">▼{dn_cnt}</span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True
        )

        table_html = render_quote_table_html(rows_data)
        st.markdown(table_html, unsafe_allow_html=True)
        st.caption("💡 點擊上方任一檔股票列，即可直接開啟該股「技術面 K 線、籌碼面、基本面、財報與 AI 深度評語」！")


# ==============================================================================
# 模式 2：🌐 上中下游產業鏈地圖
# ==============================================================================
elif view_mode == "🌐 上中下游產業鏈地圖":
    sc_data = load_supply_chain_data()
    concept_chains = sc_data.get('concept_chains', {})

    chain_options = {
        'cpo_optical': '⚡ 光通訊 ＆ CPO 共同封裝光學產業鏈',
        'foplp_packaging': '📦 FOPLP 扇出型面板級封裝 ＆ 玻璃基板鏈',
        'semiconductor_chemicals': '🧪 半導體特用化學 ＆ 先進材料產業鏈',
        'cowos_packaging': '🔬 CoWoS 先進封裝 ＆ 半導體製程設備鏈',
        'ai_server_cooling': '🖥️ AI 伺服器整機 ＆ 水冷供電機構鏈'
    }

    c_choice = st.selectbox(
        "選擇產業鏈圖譜",
        list(chain_options.keys()),
        format_func=lambda k: chain_options[k]
    )

    cur_chain = concept_chains.get(c_choice, {})
    if cur_chain:
        # 標題與簡介卡
        st.markdown(
            f"<div style='background:#111726; border:1px solid #1E293B; border-left:5px solid #00D4AA; border-radius:10px; padding:14px 16px; margin:6px 0 14px 0;'>"
            f"<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;'>"
            f"<span style='color:#FFF; font-size:22px; font-weight:800;'>{cur_chain.get('title', '')}</span>"
            f"<span style='background:rgba(0,212,170,0.15); border:1px solid #00D4AA; color:#00D4AA; font-size:14px; font-weight:bold; padding:3px 10px; border-radius:12px;'>{cur_chain.get('badge', '')}</span>"
            f"</div>"
            f"<div style='color:#CBD5E1; font-size:16px; margin-top:8px; line-height:1.6;'>{cur_chain.get('desc', '')}</div>"
            f"</div>",
            unsafe_allow_html=True
        )

        up_obj = cur_chain.get('upstream', {})
        mid_obj = cur_chain.get('midstream', {})
        dn_obj = cur_chain.get('downstream', {})

        # 收集該鏈的所有股票批次抓取報價
        all_codes = [s['code'] for s in up_obj.get('stocks', []) + mid_obj.get('stocks', []) + dn_obj.get('stocks', [])]
        with st.spinner("正在更新產業鏈成分股即時報價..."):
            quotes_map = get_batch_quotes_with_intraday(all_codes)

        # 響應式 3 欄上中下游流程圖
        col1, col2, col3 = st.columns([1, 1, 1])

        # 【上游】
        with col1:
            st.markdown(
                f"<div class='tier-header-box' style='border-left:4px solid #38BDF8;'>"
                f"<div style='color:#38BDF8; font-size:18px; font-weight:800;'>⬅️ 上游材料與核心組件</div>"
                f"<div style='color:#94A3B8; font-size:13px; margin-top:2px;'>{up_obj.get('desc', '')}</div>"
                f"<div style='color:#38BDF8; font-size:12px; margin-top:4px; font-weight:600;'>➔ 供貨至中游製造代工</div>"
                f"</div>",
                unsafe_allow_html=True
            )
            for s in up_obj.get('stocks', []):
                q = quotes_map.get(s['code'], {})
                card_html = render_supply_chain_stock_card(
                    s['code'], s['name'], s['role'], details="", quote=q
                )
                st.markdown(card_html, unsafe_allow_html=True)

        # 【中游】
        with col2:
            st.markdown(
                f"<div class='tier-header-box' style='border-left:4px solid #F59E0B;'>"
                f"<div style='color:#F59E0B; font-size:18px; font-weight:800;'>🎯 中游製造與製程設備</div>"
                f"<div style='color:#94A3B8; font-size:13px; margin-top:2px;'>{mid_obj.get('desc', '')}</div>"
                f"<div style='color:#F59E0B; font-size:12px; margin-top:4px; font-weight:600;'>➔ 交付下游模組與整合</div>"
                f"</div>",
                unsafe_allow_html=True
            )
            for s in mid_obj.get('stocks', []):
                q = quotes_map.get(s['code'], {})
                card_html = render_supply_chain_stock_card(
                    s['code'], s['name'], s['role'], details="", quote=q
                )
                st.markdown(card_html, unsafe_allow_html=True)

        # 【下游】
        with col3:
            st.markdown(
                f"<div class='tier-header-box' style='border-left:4px solid #10B981;'>"
                f"<div style='color:#10B981; font-size:18px; font-weight:800;'>➡️ 下游模組封裝與出海口</div>"
                f"<div style='color:#94A3B8; font-size:13px; margin-top:2px;'>{dn_obj.get('desc', '')}</div>"
                f"<div style='color:#10B981; font-size:12px; margin-top:4px; font-weight:600;'>🏁 全球資料中心與終端</div>"
                f"</div>",
                unsafe_allow_html=True
            )
            for s in dn_obj.get('stocks', []):
                q = quotes_map.get(s['code'], {})
                card_html = render_supply_chain_stock_card(
                    s['code'], s['name'], s['role'], details="", quote=q
                )
                st.markdown(card_html, unsafe_allow_html=True)

        st.caption("💡 點擊上方任何一檔成分股卡片，即可一秒切換進入該股「技術分析 K 線、籌碼買賣超與 AI 投資評級」！")


# ==============================================================================
# 模式 3：🇺🇸 美股巨頭對標台股供應鏈
# ==============================================================================
elif view_mode == "🇺🇸 美股巨頭對標台股供應鏈":
    sc_data = load_supply_chain_data()
    global_giants = sc_data.get('global_giants', {})

    giant_keys = list(global_giants.keys())
    giant_labels = {
        'lumentum': '🌟 Lumentum (LITE) ｜ 全球光通訊與雷射巨頭',
        'nvidia': '🚀 NVIDIA (NVDA) ｜ AI 算力 GPU / Blackwell 霸主',
        'broadcom': '⚡ Broadcom (AVGO) ｜ 網通交換器晶片 / ASIC / CPO',
        'apple': '🍎 Apple (AAPL) ｜ iPhone 16 / Apple Intelligence',
        'tesla': '🚗 Tesla (TSLA) ｜ 電動車 / FSD / 人形機器人'
    }

    # 檢查預設選取
    def_g_idx = 0
    if 'giant' in st.query_params and st.query_params['giant'] in global_giants:
        def_g_idx = giant_keys.index(st.query_params['giant'])

    selected_giant_key = st.selectbox(
        "選擇美股科技巨頭",
        giant_keys,
        index=def_g_idx,
        format_func=lambda k: giant_labels.get(k, k)
    )

    giant = global_giants.get(selected_giant_key, {})
    if giant:
        # 美股巨頭背景與暴漲催化劑 Banner
        cat_items_html = "".join([
            f"<div style='color:#E2E8F0; font-size:15px; margin:4px 0;'><span style='color:#F59E0B; font-weight:bold;'>🔥 催化亮點：</span>{cat}</div>"
            for cat in giant.get('catalysts', [])
        ])

        st.markdown(
            f"<div style='background:linear-gradient(135deg, #101626 0%, #0B101D 100%); border:1px solid #23314E; border-left:5px solid #38BDF8; border-radius:12px; padding:16px; margin:6px 0 14px 0;'>"
            f"<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;'>"
            f"<div>"
            f"<span style='color:#FFF; font-size:23px; font-weight:900;'>{giant.get('name')}</span> "
            f"<span style='color:#38BDF8; font-size:17px; font-weight:bold;'>({giant.get('market')}: {giant.get('ticker')})</span>"
            f"</div>"
            f"<span style='background:#0369A1; color:#FFF; font-size:13.5px; font-weight:bold; padding:3px 10px; border-radius:12px;'>{giant.get('sector')}</span>"
            f"</div>"
            f"<div style='color:#CBD5E1; font-size:15.5px; margin-top:8px; line-height:1.6;'>{giant.get('description')}</div>"
            f"<div style='margin-top:10px; padding-top:10px; border-top:1px dashed #243048;'>"
            f"{cat_items_html}"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True
        )

        chain = giant.get('supply_chain', {})
        up_list = chain.get('upstream', [])
        mid_list = chain.get('midstream', [])
        dn_list = chain.get('downstream', [])

        all_giant_codes = [s['code'] for s in up_list + mid_list + dn_list]
        with st.spinner(f"正在載入 {giant.get('ticker')} 對標台股供應鏈即時報價..."):
            quotes_map = get_batch_quotes_with_intraday(all_giant_codes)

        # 3 欄展示供應鏈關係
        col_g1, col_g2, col_g3 = st.columns([1, 1, 1])

        with col_g1:
            st.markdown(
                f"<div class='tier-header-box' style='border-left:4px solid #38BDF8;'>"
                f"<div style='color:#38BDF8; font-size:18px; font-weight:800;'>⬅️ 上游材料與晶圓製造</div>"
                f"<div style='color:#94A3B8; font-size:13px; margin-top:2px;'>核心半導體材料、特化與先進製程代工</div>"
                f"<div style='color:#38BDF8; font-size:12px; margin-top:4px; font-weight:600;'>➔ 供貨至中游零組件</div>"
                f"</div>",
                unsafe_allow_html=True
            )
            for s in up_list:
                q = quotes_map.get(s['code'], {})
                card_html = render_supply_chain_stock_card(
                    s['code'], s['name'], s['role'], details=s.get('details', ''), quote=q
                )
                st.markdown(card_html, unsafe_allow_html=True)

        with col_g2:
            st.markdown(
                f"<div class='tier-header-box' style='border-left:4px solid #F59E0B;'>"
                f"<div style='color:#F59E0B; font-size:18px; font-weight:800;'>🎯 中游模組與製程代工</div>"
                f"<div style='color:#94A3B8; font-size:13px; margin-top:2px;'>關鍵零組件代工、散熱模組與高階電源</div>"
                f"<div style='color:#F59E0B; font-size:12px; margin-top:4px; font-weight:600;'>➔ 交付終端組裝或封裝</div>"
                f"</div>",
                unsafe_allow_html=True
            )
            for s in mid_list:
                q = quotes_map.get(s['code'], {})
                card_html = render_supply_chain_stock_card(
                    s['code'], s['name'], s['role'], details=s.get('details', ''), quote=q
                )
                st.markdown(card_html, unsafe_allow_html=True)

        with col_g3:
            st.markdown(
                f"<div class='tier-header-box' style='border-left:4px solid #10B981;'>"
                f"<div style='color:#10B981; font-size:18px; font-weight:800;'>➡️ 下游先進封裝與整機 ODM</div>"
                f"<div style='color:#94A3B8; font-size:13px; margin-top:2px;'>光收發模組、共同封裝、伺服器整機出海口</div>"
                f"<div style='color:#10B981; font-size:12px; margin-top:4px; font-weight:600;'>🏁 直接出貨美股巨頭</div>"
                f"</div>",
                unsafe_allow_html=True
            )
            for s in dn_list:
                q = quotes_map.get(s['code'], {})
                card_html = render_supply_chain_stock_card(
                    s['code'], s['name'], s['role'], details=s.get('details', ''), quote=q
                )
                st.markdown(card_html, unsafe_allow_html=True)

        st.caption(f"💡 透過美股 {giant.get('ticker')} 股價連動與供應鏈地圖，可精準捕捉台股外溢受惠概念股！點擊任一卡片可直達個股深度診斷。")
