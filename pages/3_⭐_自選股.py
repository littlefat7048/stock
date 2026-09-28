"""
台股自選股追蹤與備註管理頁面
支援以代號或中文股名新增、編輯投資備註、一鍵跳轉個股完整分析
"""
import importlib
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import utils.helpers
importlib.reload(utils.helpers)
from utils.helpers import (
    load_watchlist, save_watchlist,
    resolve_stock_query, get_tw_stock_chinese_info,
    get_concept_tags_for_stock, load_concept_data, get_common_css, get_top_nav_html
)

st.set_page_config(page_title='自選股清單', page_icon='⭐', layout='wide')
st.markdown(get_common_css(), unsafe_allow_html=True)
st.markdown(get_top_nav_html('watch'), unsafe_allow_html=True)

st.title("⭐ 我的台股自選股清單")
st.caption("輸入股票代號（如 5484）或中文名稱（如 慧友、台積電）加入追蹤，並記錄買進理由或目標價。")

watchlist = load_watchlist()

col1, col2 = st.columns([1.5, 2.5])
with col1:
    new_input = st.text_input("➕ 股票代號或中文股名", placeholder="例如：5484 或 慧友")
with col2:
    new_note = st.text_input("📝 投資備註（選填）", placeholder="例如：等待拉回 38 元支撐買進")

if st.button("➕ 加入自選股", use_container_width=True):
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

st.divider()

if not watchlist:
    st.info("目前尚未加入任何自選股。您可以在上方輸入代號/股名新增，或在「股票分析」頁面點擊加入！")
else:
    concept_data = load_concept_data()
    for idx, stock in enumerate(watchlist):
        scode = stock['code']
        cinfo = get_tw_stock_chinese_info(scode)
        sname = cinfo.get('name', stock.get('name', scode))
        smarket = cinfo.get('market', '台股')
        sinds = ' / '.join(cinfo.get('industries', []))
        tags = get_concept_tags_for_stock(scode, concept_data)

        c1, c2, c3, c4 = st.columns([1.5, 2.2, 2.5, 1.4])
        with c1:
            st.markdown(f"### 🇹🇼 {sname} `({scode})`")
            st.caption(f"{smarket} ｜ {sinds}")
        with c2:
            st.markdown("**🏷️ 所屬題材概念**")
            st.write(", ".join(tags) if tags else f"{sinds or '一般台股'}")
        with c3:
            updated_note = st.text_input(
                "📌 投資備註",
                value=stock.get('note', ''),
                key=f"note_{scode}",
                placeholder="輸入買進價位或觀察重點..."
            )
            if updated_note != stock.get('note', ''):
                watchlist[idx]['note'] = updated_note
                save_watchlist(watchlist)
                st.toast("💾 備註已自動儲存")
        with c4:
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            if st.button("📊 深度分析", key=f"view_{scode}", use_container_width=True):
                st.session_state['target_stock'] = scode
                st.switch_page("pages/1_📊_股票分析.py")
            if st.button("🗑️ 移除", key=f"del_{scode}", use_container_width=True):
                watchlist = [s for s in watchlist if s['code'] != scode]
                save_watchlist(watchlist)
                st.rerun()
        st.divider()
