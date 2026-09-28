"""
台股分析系統 — 全站響應式行動版與桌機樣式模組
針對手機螢幕（寬度 <= 768px）進行深度緊湊化排版優化，消除過度鬆散的空白間距
"""

def get_common_css():
    return """
    <style>
    /* ── 全站通用深色系與卡片樣式 ── */
    .metric-card {
        background: #1C2333; border-radius: 10px; padding: 12px 14px;
        border-left: 4px solid #00D4AA; margin-bottom: 6px;
    }
    .up-text { color: #e53935; font-weight: bold; }
    .down-text { color: #43a047; font-weight: bold; }
    .rating-buy   { background: linear-gradient(135deg, #d32f2f, #e53935); color:white; padding:8px 18px; border-radius:10px; font-size:20px; font-weight:bold; display:inline-block; box-shadow: 0 4px 10px rgba(229,57,53,0.3); }
    .rating-watch { background: linear-gradient(135deg, #f57c00, #ff9800); color:white; padding:8px 18px; border-radius:10px; font-size:20px; font-weight:bold; display:inline-block; box-shadow: 0 4px 10px rgba(255,152,0,0.3); }
    .rating-sell  { background: linear-gradient(135deg, #2e7d32, #43a047); color:white; padding:8px 18px; border-radius:10px; font-size:20px; font-weight:bold; display:inline-block; box-shadow: 0 4px 10px rgba(67,160,71,0.3); }
    
    .market-badge { background:#00D4AA1C; border:1px solid #00D4AA; color:#00D4AA; padding:2px 8px; border-radius:6px; font-size:12px; font-weight:bold; }
    .sector-badge { background:#38BDF81C; border:1px solid #38BDF8; color:#38BDF8; padding:2px 8px; border-radius:6px; font-size:12px; }
    .concept-tag  { display:inline-block; background:#1C2333; border:1px solid #FFB30066; color:#FFD54F; padding:2px 10px; border-radius:12px; font-size:11px; margin:2px 4px 2px 0; }
    
    .info-card    { background:#1C2333; border:1px solid #2A324B; border-radius:8px; padding:10px 14px; margin-bottom:8px; }
    .price-box    { background:#161C28; border-left:3px solid #00D4AA; border-radius:8px; padding:10px 12px; }
    .pro-box      { background:#1C2826; border-left:3px solid #e53935; border-radius:8px; padding:10px 12px; margin-bottom:6px; }
    .con-box      { background:#1E241E; border-left:3px solid #43a047; border-radius:8px; padding:10px 12px; margin-bottom:6px; }

    /* ── 橫向滑動晶片區（手機友善極簡設計） ── */
    .chips-scroll-bar {
        display: flex;
        overflow-x: auto;
        white-space: nowrap;
        gap: 6px;
        padding: 4px 2px 8px 2px;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: none;
    }
    .chips-scroll-bar::-webkit-scrollbar {
        display: none;
    }
    .stock-chip-link {
        display: inline-flex;
        align-items: center;
        background: #1C2333;
        border: 1px solid #2E3A59;
        border-radius: 16px;
        padding: 4px 11px;
        color: #E2E8F0 !important;
        font-size: 13px;
        text-decoration: none !important;
        cursor: pointer;
        flex-shrink: 0;
        transition: all 0.15s ease;
    }
    .stock-chip-link:hover, .stock-chip-link:active {
        background: #00D4AA22;
        border-color: #00D4AA;
        color: #00D4AA !important;
    }
    .chip-code {
        color: #00D4AA;
        font-weight: bold;
        margin-right: 4px;
        font-size: 12px;
    }

    /* ── 手機版專屬緊湊佈局 (螢幕寬度 <= 768px) ── */
    @media (max-width: 768px) {
        /* 大幅減少 Streamlit 預設多達 6rem 的頂部與邊緣留白 */
        .main .block-container {
            padding-top: 0.6rem !important;
            padding-bottom: 2rem !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
            max-width: 100% !important;
        }
        /* 縮小 Header 佔用高度 */
        header[data-testid="stHeader"] {
            height: 2.2rem !important;
            background: rgba(14, 17, 23, 0.8) !important;
        }
        /* 元件之間的垂直空隙由預設的 1rem 降為 0.35rem */
        div[data-testid="stVerticalBlock"] > div {
            gap: 0.35rem !important;
        }
        /* 標題與字體適當縮放 */
        h1 {
            font-size: 1.35rem !important;
            margin: 0.2rem 0 !important;
            line-height: 1.25 !important;
        }
        h2 {
            font-size: 1.2rem !important;
            margin: 0.3rem 0 !important;
        }
        h3 {
            font-size: 1.05rem !important;
            margin: 0.25rem 0 !important;
        }
        h4, h5, h6 {
            font-size: 0.95rem !important;
            margin: 0.2rem 0 !important;
        }
        hr {
            margin: 0.4rem 0 !important;
        }
        /* 按鈕小巧緊湊化 */
        .stButton > button {
            padding: 0.3rem 0.6rem !important;
            font-size: 0.85rem !important;
            min-height: 2rem !important;
            border-radius: 8px !important;
        }
        /* 分頁標籤縮小邊距 */
        button[data-baseweb="tab"] {
            padding: 5px 8px !important;
            font-size: 12px !important;
        }
        /* 表格與圖表緊湊化 */
        .js-plotly-plot {
            margin-bottom: 0.2rem !important;
        }
    }
    </style>
    """
