"""
台股熱門概念股與題材分類看盤頁面（專業看盤 App 報價走勢列表版）
支援：
- 橫向滑動題材膠囊標籤（玻璃基板、光通訊、InP、封測、高價股、CoWoS、機器人等）
- 即時批次報價、迷你紅綠 K 棒、成交價/漲跌幅排序、平盤雙色漸層迷你走勢圖
- 點擊任一股票列直接進入個股深度分析
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
    load_concept_data, get_common_css, get_top_nav_html,
    render_quote_table_html
)
from modules.data_fetcher import get_batch_quotes_with_intraday

st.set_page_config(page_title='台股概念股看盤', page_icon='🏷️', layout='wide')
st.markdown(get_common_css(), unsafe_allow_html=True)
st.markdown(get_top_nav_html('concept'), unsafe_allow_html=True)

# ── 專屬概念膠囊列樣式（仿看盤 App 頂部圓角膠囊標籤） ──────────
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
    font-size:19px;
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
</style>
""", unsafe_allow_html=True)

concept_data = load_concept_data()
categories = concept_data.get('概念分類', {})

# 攤平所有子概念並建立索引
all_sub_concepts = {}  # sub_name -> {big_cat, desc, stocks}
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

# 優先排序熱門概念（將圖片中的「玻璃基板、光通訊、InP、封測、高價股」排在最前面）
PRIORITY_CONCEPTS = [
    ('玻璃基板', '玻璃基板'),
    ('光通訊CPO', '光通訊'),
    ('InP磷化銦', 'InP'),
    ('封裝測試', '封測'),
    ('高價千金股', '高價股'),
    ('CoWoS先進封裝', 'CoWoS'),
    ('AI伺服器', 'AI伺服器'),
    ('散熱模組', '散熱模組'),
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

# 讀取目前選中的概念（預設為「光通訊CPO」）
default_sub = '光通訊CPO' if '光通訊CPO' in all_sub_concepts else ordered_sub_keys[0]
if 'c_sub' in st.query_params and st.query_params['c_sub'] in all_sub_concepts:
    st.session_state['selected_concept_sub'] = st.query_params['c_sub']

current_sub = st.session_state.get('selected_concept_sub', default_sub)
if current_sub not in all_sub_concepts:
    current_sub = default_sub

# ── 🏆 今日最強資金輪動族群 TOP 5 ─────────────────────────────
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

# ── 橫向滑動概念膠囊列（仿圖片 [玻璃基板] [光通訊] [InP] [封測] [高價股]） ──
pills_html = []
for k in ordered_sub_keys:
    cls = "concept-pill-item active" if k == current_sub else "concept-pill-item"
    lbl = short_label_map.get(k, k)
    encoded_k = urllib.parse.quote(k)
    pills_html.append(f'<a href="/?c_sub={encoded_k}" target="_self" class="{cls}">{lbl}</a>')

st.markdown(f'<div class="concept-pill-bar">{"".join(pills_html)}</div>', unsafe_allow_html=True)

# ── 收合式進階篩選與排序列（不佔手機首屏空間） ────────────────
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

# ── 準備當前概念（或關鍵字搜尋）的股票清單 ────────────────────
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

    # 依選擇模式排序
    if sort_mode == "漲跌幅 ▼ (強勢)":
        rows_data.sort(key=lambda x: x['pct_change'], reverse=True)
    elif sort_mode == "漲跌幅 ▲ (弱勢)":
        rows_data.sort(key=lambda x: x['pct_change'], reverse=False)
    elif sort_mode == "成交價 ▼ (高價)":
        rows_data.sort(key=lambda x: x['close'], reverse=True)
    elif sort_mode == "成交價 ▲ (低價)":
        rows_data.sort(key=lambda x: x['close'], reverse=False)

    # 計算族群漲跌統計
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

    # 渲染專業看盤報價走勢表
    table_html = render_quote_table_html(rows_data)
    st.markdown(table_html, unsafe_allow_html=True)
    st.caption("💡 點擊上方任一檔股票列，即可直接開啟該股「技術面 K 線、籌碼面、基本面、財報與 AI 深度評語」！")
