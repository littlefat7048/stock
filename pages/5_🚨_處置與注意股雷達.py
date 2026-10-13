"""
pages/5_🚨_處置與注意股雷達.py
台股處置股預測、當沖券差借券軋空、注意股自結損益速報
資料來源：Chengwaye 與證交所 / 櫃買中心公開數據
"""

import streamlit as st
import pandas as pd
import html
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.disposal_radar import (
    get_disposal_forecast,
    get_borrowed_short_squeeze,
    get_attention_self_reported_eps
)
from utils.helpers import get_common_css, get_top_nav_html, inject_pwa_and_ux_enhancements

# 頁面基本設定
st.set_page_config(
    page_title="處置與注意股雷達",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入導覽列與通用樣式
st.markdown(get_common_css(), unsafe_allow_html=True)
st.markdown(get_top_nav_html('disposal'), unsafe_allow_html=True)
inject_pwa_and_ux_enhancements()

# 注入自訂 Dark CSS 樣式
st.markdown("""
<style>
    /* 全域暗色系卡片與文字微調 */
    .metric-card {
        background: #161B22;
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 12px;
    }
    .metric-title {
        color: #8B949E;
        font-size: 13px;
        font-weight: 500;
        margin-bottom: 4px;
    }
    .metric-val {
        font-size: 26px;
        font-weight: 700;
        color: #F0F6FC;
        font-variant-numeric: tabular-nums;
    }
    .metric-sub {
        font-size: 12px;
        margin-top: 4px;
    }
    .badge-danger {
        background: rgba(231, 76, 60, 0.2);
        color: #FF6B6B;
        border: 1px solid rgba(231, 76, 60, 0.4);
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-warning {
        background: rgba(241, 196, 15, 0.2);
        color: #F1C40F;
        border: 1px solid rgba(241, 196, 15, 0.4);
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-success {
        background: rgba(46, 204, 113, 0.2);
        color: #2ECC71;
        border: 1px solid rgba(46, 204, 113, 0.4);
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-info {
        background: rgba(52, 152, 219, 0.2);
        color: #3498DB;
        border: 1px solid rgba(52, 152, 219, 0.4);
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }
    .stock-card {
        background: #161B22;
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 14px 16px;
        margin-bottom: 10px;
        transition: border-color 0.2s;
    }
    .stock-card:hover {
        border-color: #58A6FF;
    }
    .clause-box {
        background: #0D1117;
        border: 1px solid #21262D;
        border-radius: 6px;
        padding: 10px 14px;
        font-size: 13px;
        line-height: 1.6;
        color: #C9D1D9;
        margin-top: 8px;
    }
</style>
""", unsafe_allow_html=True)

# 頂部標題與說明
st.title("🚨 處置與注意股雷達")
st.markdown("盤後即時追蹤**處置預測、分盤撮合、出關倒數**，以及**當沖券差軋空指標**與**注意股自結損益速報**。")

# 側邊欄控制
with st.sidebar:
    st.header("⚙️ 雷達控制台")
    force_reload = st.button("🔄 強制重新整理最新資料", use_container_width=True)
    st.markdown("---")
    st.markdown("""
    **💡 什麼是處置股？**
    - 台灣證交所對過熱飆股的處置措施（俗稱關禁閉）。
    - 採每 **5 分鐘** 或 **20 分鐘** 人工分盤撮合，並**預收款券（全額交割，禁止當沖）**。
    - **出關日**前夕常迎來流動性解禁行情！
    """)

# 載入核心資料
with st.spinner("正在連線抓取盤後處置與券差資料..."):
    disp_data = get_disposal_forecast(force_refresh=force_reload)
    squeeze_data = get_borrowed_short_squeeze(force_refresh=force_reload)
    att_data = get_attention_self_reported_eps(force_refresh=force_reload)

# 頂部 4 大 KPI 統計指標卡片
high_cnt = len(disp_data.get('high_risk', [])) if disp_data.get('status') == 'success' else 0
med_cnt = len(disp_data.get('med_risk', [])) if disp_data.get('status') == 'success' else 0
active_cnt = len(disp_data.get('active_disposal', [])) if disp_data.get('status') == 'success' else 0
exit_soon_cnt = len(disp_data.get('exit_soon', [])) if disp_data.get('status') == 'success' else 0
squeeze_cnt = squeeze_data.get('high_squeeze_count', 0) if squeeze_data.get('status') == 'success' else 0

kpi_cols = st.columns(4)
with kpi_cols[0]:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">🔴 差 1 次就處置 (高危)</div>
        <div class="metric-val" style="color:#FF6B6B;">{high_cnt} <span style="font-size:15px;color:#8B949E;">檔</span></div>
        <div class="metric-sub" style="color:#FF6B6B;">明日達觸發價即送處置</div>
    </div>
    """, unsafe_allow_html=True)

with kpi_cols[1]:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">🟡 差 2 次處置 (中度觀察)</div>
        <div class="metric-val" style="color:#F1C40F;">{med_cnt} <span style="font-size:15px;color:#8B949E;">檔</span></div>
        <div class="metric-sub" style="color:#F1C40F;">已累積多次注意條款</div>
    </div>
    """, unsafe_allow_html=True)

with kpi_cols[2]:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">⚪ 目前處置中 (關禁閉)</div>
        <div class="metric-val" style="color:#58A6FF;">{active_cnt} <span style="font-size:15px;color:#8B949E;">檔</span></div>
        <div class="metric-sub" style="color:#2ECC71;">其中 {exit_soon_cnt} 檔即將出關</div>
    </div>
    """, unsafe_allow_html=True)

with kpi_cols[3]:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">⚡ 當沖券差軋空高危</div>
        <div class="metric-val" style="color:#E056FD;">{squeeze_cnt} <span style="font-size:15px;color:#8B949E;">檔</span></div>
        <div class="metric-sub" style="color:#E056FD;">空單遭鎖死，明早市價回補</div>
    </div>
    """, unsafe_allow_html=True)

# 4 大主要功能頁籤
tabs = st.tabs([
    "🔴 處置預測與出關雷達",
    "⚡ 當沖券差軋空雷達",
    "📑 注意股自結損益照妖鏡",
    "📘 實戰指南與處置攻略"
])

# ==========================================
# TAB 1: 處置預測與出關雷達
# ==========================================
with tabs[0]:
    if disp_data.get('status') != 'success':
        st.error(f"無法取得處置預測資料：{disp_data.get('message', '未知錯誤')}")
    else:
        st.caption(f"📅 資料狀態：{disp_data.get('subtitle')} ｜ 更新時間：{disp_data.get('fetched_at')}")

        # 1. 差 1 次就處置 (高危警戒區)
        st.subheader("🔴 差 1 次就處置 (最快明日收盤觸發)")
        high_list = disp_data.get('high_risk', [])
        if not high_list:
            st.info("✅ 目前無「差 1 次就處置」的高危個股。")
        else:
            for s in high_list:
                with st.container():
                    st.markdown(f"""
                    <div class="stock-card" style="border-left: 4px solid #FF6B6B;">
                        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                            <div>
                                <span class="badge-danger">{s['market']}</span>
                                <strong style="font-size:18px; margin-left:6px; color:#F0F6FC;">{s['code']} {s['name']}</strong>
                                <span style="color:#8B949E; margin-left:10px;">目前收盤：<strong>{s['close']} 元</strong></span>
                            </div>
                            <div>
                                <span class="badge-danger">最快處置：{s['soonest_disposal']}</span>
                            </div>
                        </div>
                        <div style="margin-top:10px; font-size:14px; color:#E6EDF3;">
                            🎯 <strong>觸發條件：</strong> <span style="color:#FF6B6B; font-weight:700;">{s['trigger_cond']}</span>
                        </div>
                        <div style="display:flex; gap:12px; margin-top:8px; font-size:12px; color:#8B949E; flex-wrap:wrap;">
                            <span>3①(連續3日第1款): <strong style="color:#F0F6FC;">{s.get('c_3_1', '—')}</strong></span>
                            <span>5(連續5日): <strong style="color:#F0F6FC;">{s.get('c_5', '—')}</strong></span>
                            <span>6(10日內6次): <strong style="color:#F0F6FC;">{s.get('c_6', '—')}</strong></span>
                            <span>12(30日內12次): <strong style="color:#F0F6FC;">{s.get('c_12', '—')}</strong></span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    with st.expander(f"🔍 展開 {s['code']} {s['name']} 條款詳細計算與歷史紀錄", expanded=False):
                        st.markdown(f"<div class='clause-box'>{s.get('detail', '無明細')}</div>", unsafe_allow_html=True)
                        st.page_link("pages/1_📊_股票分析.py", label=f"👉 前往 {s['code']} {s['name']} 個股完整分析", icon="📈")

        st.markdown("---")

        # 2. 差 2 次處置 (中度觀察區)
        st.subheader("🟡 差 2 次處置 (已進入警戒觀察名單)")
        med_list = disp_data.get('med_risk', [])
        if not med_list:
            st.info("✅ 目前無差 2 次處置的個股。")
        else:
            med_rows = []
            for m in med_list:
                med_rows.append({
                    "市場": m['market'],
                    "代號": m['code'],
                    "名稱": m['name'],
                    "收盤價": m['close'],
                    "觸發條件估算": m['trigger_cond'][:45] + ("..." if len(m['trigger_cond']) > 45 else ""),
                    "最快處置日": m['soonest_disposal'],
                    "條款累積": f"3①:{m.get('c_3_1','')} | 6次:{m.get('c_6','')}"
                })
            df_med = pd.DataFrame(med_rows)
            st.dataframe(df_med, use_container_width=True, hide_index=True)

        st.markdown("---")

        # 3. 處置中股票與出關倒數日曆
        st.subheader("⚪ 目前處置中股票（分盤撮合中）")
        active_list = disp_data.get('active_disposal', [])
        
        # 篩選按鈕
        filter_col1, filter_col2 = st.columns([2, 1])
        with filter_col1:
            disp_filter = st.radio(
                "篩選處置股票：",
                ["全部處置股", "🟢 即將出關 (剩餘 2 天以內)", "🔴 20 分盤 (嚴重處置)", "🟡 5 分盤 (一般處置)"],
                horizontal=True
            )
        
        filtered_disp = active_list
        if disp_filter == "🟢 即將出關 (剩餘 2 天以內)":
            filtered_disp = [s for s in active_list if s['remaining_days'] in ['出關', '1天', '2天']]
        elif disp_filter == "🔴 20 分盤 (嚴重處置)":
            filtered_disp = [s for s in active_list if '20' in s.get('interval', '') or '25' in s.get('interval', '')]
        elif disp_filter == "🟡 5 分盤 (一般處置)":
            filtered_disp = [s for s in active_list if '5' in s.get('interval', '') or '2' in s.get('interval', '')]
            
        if not filtered_disp:
            st.info("無符合條件的處置股票。")
        else:
            disp_rows = []
            for s in filtered_disp:
                is_exit_soon = s['remaining_days'] in ['出關', '1天', '2天']
                status_icon = "🟢 即將出關" if is_exit_soon else "⏳ 關禁閉中"
                disp_rows.append({
                    "狀態": status_icon,
                    "市場": s['market'],
                    "代號": s['code'],
                    "名稱": s['name'],
                    "撮合分盤": s['interval'],
                    "處置起始": s['start_date'],
                    "處置結束": s['end_date'],
                    "出關日": s['exit_date'],
                    "剩餘交易日": s['remaining_days'],
                    "處置原因": s['reason']
                })
            df_disp = pd.DataFrame(disp_rows)
            st.dataframe(df_disp, use_container_width=True, hide_index=True)

        st.markdown("---")

        # 4. LINE 轉貼純文字版
        st.subheader("📋 盤前 LINE / 筆記轉貼文字版")
        line_txt = disp_data.get('line_share_text', '')
        if line_txt:
            st.code(line_txt, language="text")
        else:
            st.info("暫無文字版格式")

# ==========================================
# TAB 2: 當沖券差軋空雷達
# ==========================================
with tabs[1]:
    st.subheader("⚡ 當沖券差借券費率排行榜（核彈級隔日軋空指標）")
    
    st.info("""
    **🔥 為什麼券差是短線必看的「隔日軋空指標」？**
    - 現股當沖放空者在盤中未能買回（例如個股強勢拉漲停鎖死），收盤後券商必須向市場投資人「標借」股票來交割（每日費率最高可達 **7%**！）。
    - **隔天早盤 9:00 開盤，券商會以「市價單」直接強制買回還券！**
    - 巨量借券 + 漲停鎖死，往往引發隔日開盤**直接跳空漲停或極度開高軋空**！
    """)
    
    if squeeze_data.get('status') != 'success':
        st.error(f"無法載入券差借券資料：{squeeze_data.get('message', '未知錯誤')}")
    else:
        sq_entries = squeeze_data.get('entries', [])
        
        # 篩選器
        sq_filter_cols = st.columns([2, 1, 1])
        with sq_filter_cols[0]:
            sq_filter = st.radio(
                "篩選軋空標的：",
                ["全部有借券股", "🚨 漲停鎖死軋空股 (極高危)", "⚡ 費率 ≥ 3.0% (高成本急迫回補)", "📈 借券 ≥ 50 張"],
                horizontal=True
            )
        
        filtered_sq = sq_entries
        if sq_filter == "🚨 漲停鎖死軋空股 (極高危)":
            filtered_sq = [x for x in sq_entries if x['is_locked_up']]
        elif sq_filter == "⚡ 費率 ≥ 3.0% (高成本急迫回補)":
            filtered_sq = [x for x in sq_entries if x['avg_rate'] >= 3.0]
        elif sq_filter == "📈 借券 ≥ 50 張":
            filtered_sq = [x for x in sq_entries if x['total_lots'] >= 50]
            
        st.caption(f"共找到 {len(filtered_sq)} 檔標的 ｜ 基準日期：{squeeze_data.get('date')}")
        
        if not filtered_sq:
            st.info("無符合篩選條件的標的。")
        else:
            sq_rows = []
            for item in filtered_sq[:60]: # 取前 60 檔
                sq_rows.append({
                    "軋空評級": item['squeeze_rank'],
                    "市場": item['market'],
                    "代號": item['code'],
                    "名稱": item['name'],
                    "收盤價": item['close'],
                    "當日漲幅%": f"{item['daily_pct']}%",
                    "總借券張數": f"{item['total_lots']} 張",
                    "加權均費率%": f"{item['avg_rate']}%",
                    "最高費率%": f"{item['max_rate']}%",
                    "筆數": item['records_count']
                })
            df_sq = pd.DataFrame(sq_rows)
            st.dataframe(df_sq, use_container_width=True, hide_index=True)

# ==========================================
# TAB 3: 注意股自結損益照妖鏡
# ==========================================
with tabs[2]:
    st.subheader("📑 注意股自結損益速報（飆股開箱照妖鏡）")
    
    st.info("""
    **💡 自結損益的實戰價值：**
    - 股票因股價異常飆漲被列為「注意股」後，交易所會強制要求公司公布「單月自結獲利」。
    - **真妖股 (AI +5)**：單月自結 EPS 暴賺超越過去全季，開箱確認業績爆發，隔日往往跳空鎖漲停！
    - **假題材 (AI -5)**：飆漲一倍但自結公布竟是虧損，假面具被拆穿，隔日往往跌停倒貨！
    """)
    
    if att_data.get('status') != 'success':
        st.error(f"無法載入自結損益資料：{att_data.get('message', '未知錯誤')}")
    else:
        att_entries = att_data.get('entries', [])
        
        att_choice = st.radio(
            "篩選自結評分：",
            ["全部最新公告", "🟢 AI 看多暴賺 (分數 ≥ 1)", "🔴 AI 看空轉虧/衰退 (分數 ≤ -1)"],
            horizontal=True
        )
        
        filtered_att = att_entries
        if att_choice == "🟢 AI 看多暴賺 (分數 ≥ 1)":
            filtered_att = [x for x in att_entries if x.get('ai_score', 0) >= 1]
        elif att_choice == "🔴 AI 看空轉虧/衰退 (分數 ≤ -1)":
            filtered_att = [x for x in att_entries if x.get('ai_score', 0) <= -1]
            
        st.caption(f"共顯示 {len(filtered_att)} 筆自結公告 ｜ 更新時間：{att_data.get('fetched_at')}")
        
        for item in filtered_att[:30]:
            score = item.get('ai_score', 0)
            if score >= 2:
                badge_html = f"<span class='badge-success'>AI 評分: +{score} (大幅成長)</span>"
            elif score >= 1:
                badge_html = f"<span class='badge-success'>AI 評分: +{score} (正面)</span>"
            elif score == 0:
                badge_html = f"<span class='badge-info'>AI 評分: 0 (持平/中性)</span>"
            else:
                badge_html = f"<span class='badge-danger'>AI 評分: {score} (衰退/轉虧)</span>"
                
            eps_val = item.get('eps')
            eps_display = f"{eps_val} 元" if eps_val is not None else "未揭露/待查"
            
            with st.container():
                st.markdown(f"""
                <div class="stock-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                        <div>
                            <strong style="font-size:17px; color:#F0F6FC;">{item['code']} {item['name']}</strong>
                            <span style="color:#8B949E; margin-left:8px;">公告日：{item['date']} {item['time']}</span>
                        </div>
                        <div>
                            {badge_html}
                        </div>
                    </div>
                    <div style="margin-top:8px; font-size:14px; color:#C9D1D9;">
                        📌 <strong>期間：</strong>{item.get('period', '單月')} ｜ 
                        💰 <strong>自結 EPS：</strong><span style="font-weight:700; color:#58A6FF;">{eps_display}</span> ｜ 
                        📊 <strong>上季月均 EPS：</strong>{item.get('prev_quarter_avg', '—')} 元
                    </div>
                    <div style="margin-top:6px; font-size:13px; color:#FFA500;">
                        💡 <strong>AI 評語：</strong>{item.get('ai_reason', '無特殊評語')}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                with st.expander(f"📜 查看 {item['code']} {item['name']} 公開資訊觀測站公告原文", expanded=False):
                    st.text(item.get('raw', '無詳細公告內容'))
                    st.page_link("pages/1_📊_股票分析.py", label=f"👉 前往 {item['code']} {item['name']} 個股分析", icon="📈")

# ==========================================
# TAB 4: 實戰指南與處置攻略
# ==========================================
with tabs[3]:
    st.subheader("📘 處置股與券差實戰攻略手冊")
    
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        st.markdown("""
        ### 1. 處置四大條款公式圖解
        - **`3①`（連續 3 天第 1 款）**：
          - 第 1 款為「6 個營業日累積漲跌幅 > 32%」。
          - 只要連續 3 個營業日符合第 1 款，**第 4 天立刻進處置**！此條款最容易出現觸發價拉扯。
        - **`5`（連續 5 天公布注意）**：
          - 連續 5 個營業日經第 1~7 款公布注意即進處置。
        - **`6`（10 日內 6 次公布注意）**：
          - 最近 10 個營業日內累積達 6 次公布注意。
        - **`12`（30 日內 12 次公布注意）**：
          - 最近 30 個營業日內累積達 12 次公布注意。
          
        ---
        
        ### 2. 主力控盤生死線（觸發價）
        - **壓盤控盤型**：若主力貨還沒出完，不想進去關禁閉，盤中往往會在觸發價下方刻意壓盤。
        - **故意關禁閉（軋空型）**：主力籌碼極度集中時，乾脆故意拉漲停達標送進去關禁閉。進處置後無當沖客攪局，主力天天量縮跳空乾拔漲停！
        """)
        
    with col_g2:
        st.markdown("""
        ### 3. 處置出關戰法（解禁獵鷹）
        - 處置期間通常為 10 個營業日。
        - **倒數 1~2 天（出關日前夕）**：
          - 預收款券即將解除，恢復 5 秒撮合與信用交易當沖。
          - 被壓抑的市場買盤與流動性會瞬間解鎖。
          - 專職短線客常在倒數 1~2 天提前卡位，迎接「出關噴發大行情」！
          
        ---
        
        ### 4. 當沖券差隔日軋空 SOP
        1. **收盤檢查**：當天是否出現「漲停鎖死」且「借券張數 > 50 張」？
        2. **費率檢視**：平均借券費率是否高於 2%~5%？
        3. **隔日早盤預期**：9:00 開盤券商將強制市價買回，開盤極高機率跳空開高或直奔漲停！
        """)

st.caption("Chengwaye 處置預測由證交所公開公式估算，實際處置結果以證交所與櫃買中心官方最終公告為準。")
