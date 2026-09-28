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
from utils.helpers import load_concept_data

st.set_page_config(page_title='台股概念股分類', page_icon='🏷️', layout='wide')

st.title("🏷️ 台股熱門概念股與題材細項分類")
st.caption("仿照籌碼 K 線細分題材，涵蓋 AI 算力、CoWoS、機器人、矽光子、散熱、重電、軍工等 47 個細項分類。點擊任一股票即可開啟完整分析！")

concept_data = load_concept_data()
categories = concept_data.get('概念分類', {})

if not categories:
    st.warning("目前沒有概念股資料。")
else:
    col_cat, col_search = st.columns([2, 2])
    with col_cat:
        big_cat_list = ["全部領域"] + list(categories.keys())
        selected_big = st.selectbox("📂 選擇主產業領域", big_cat_list)
    with col_search:
        kw = st.text_input("🔍 搜尋概念名稱、股票代號或中文股名", placeholder="例如：機器人、CoWoS、慧友、2330")

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
            with st.expander(f"🏷️ {sub_name}（共 {len(stocks)} 檔） — {desc}", expanded=bool(kw)):
                cols = st.columns(5)
                for idx, s in enumerate(stocks):
                    scode = s.get('code', '')
                    sname = s.get('name', '')
                    srole = s.get('role', '')
                    with cols[idx % 5]:
                        if st.button(
                            f"📊 {scode} {sname}\n[{srole}]",
                            key=f"c_{big_cat}_{sub_name}_{scode}_{idx}",
                            use_container_width=True
                        ):
                            st.session_state['target_stock'] = scode
                            st.switch_page("pages/1_📊_股票分析.py")
