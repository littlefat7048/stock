"""
台股熱門概念股與題材分類瀏覽器
收錄 13 大領域、47 個細項概念股分類，點擊個股直接跳轉深度分析
"""
import importlib
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import utils.helpers
importlib.reload(utils.helpers)
from utils.helpers import load_concept_data, get_common_css, get_top_nav_html

st.set_page_config(page_title='台股概念股分類', page_icon='🏷️', layout='wide')
st.markdown(get_common_css(), unsafe_allow_html=True)
st.markdown(get_top_nav_html('concept'), unsafe_allow_html=True)

st.title("🏷️ 台股熱門概念股與題材細項分類")
st.caption("仿照籌碼 K 線細分題材，涵蓋 AI 算力、CoWoS、機器人、矽光子、散熱等 47 個細項。點擊任一股票即可開啟完整分析！")

concept_data = load_concept_data()
categories = concept_data.get('概念分類', {})

if not categories:
    st.warning("目前沒有概念股資料。")
else:
    col_cat, col_search = st.columns([1.5, 2.5])
    with col_cat:
        big_cat_list = ["全部領域"] + list(categories.keys())
        selected_big = st.selectbox("📂 選擇主產業領域", big_cat_list)
    with col_search:
        kw = st.text_input("🔍 搜尋概念名稱、股票代號或中文股名", placeholder="例如：機器人、CoWoS、慧友、2330", label_visibility="collapsed")

    st.divider()

    for big_cat, sub_cats in categories.items():
        if selected_big != "全部領域" and big_cat != selected_big:
            continue
        if not isinstance(sub_cats, dict):
            continue

        # 過濾符合關鍵字的子概念
        matched_subs = {}
        for sub_name, cinfo in sub_cats.items():
            if not isinstance(cinfo, dict):
                continue
            stocks = cinfo.get('stocks', [])
            if kw:
                kw_lower = kw.strip().lower()
                in_title = kw_lower in sub_name.lower() or kw_lower in cinfo.get('desc', '').lower()
                in_stocks = any(
                    kw_lower in str(s.get('code', '')).lower() or
                    kw_lower in str(s.get('name', '')).lower() or
                    kw_lower in str(s.get('role', '')).lower()
                    for s in stocks
                )
                if not (in_title or in_stocks):
                    continue
            matched_subs[sub_name] = cinfo

        if not matched_subs:
            continue

        st.subheader(f"📌 {big_cat}")
        for sub_name, cinfo in matched_subs.items():
            stocks = cinfo.get('stocks', [])
            desc = cinfo.get('desc', '')
            with st.expander(f"🏷️ {sub_name}（{len(stocks)} 檔） — {desc}", expanded=bool(kw)):
                chips_html = "".join([
                    f'<a href="/?stock={s.get("code","")}" target="_self" class="stock-chip-link" style="margin:2px 2px;">'
                    f'<span class="chip-code">{s.get("code","")}</span>{s.get("name","")}'
                    f'<span style="color:#94A3B8; font-size:11px; margin-left:4px;">({s.get("role","")})</span></a>'
                    for s in stocks
                ])
                st.markdown(f'<div style="display:flex; flex-wrap:wrap; gap:4px; padding:4px 0;">{chips_html}</div>', unsafe_allow_html=True)
