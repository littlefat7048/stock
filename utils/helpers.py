"""
工具函式庫
包含：台股中文名稱查詢、價格格式化、概念股與同業查詢、自選股存取
"""
import json
import os
import re
import streamlit as st

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
WATCHLIST_FILE = os.path.join(DATA_DIR, 'watchlist.json')
CONCEPT_FILE = os.path.join(DATA_DIR, 'concept_stocks.json')
TW_STOCKS_FILE = os.path.join(DATA_DIR, 'tw_stocks_info.json')

# 快取台股基本資料字典
_TW_STOCKS_CACHE = None

def _load_tw_stocks_dict():
    global _TW_STOCKS_CACHE
    if _TW_STOCKS_CACHE is not None:
        return _TW_STOCKS_CACHE
    if os.path.exists(TW_STOCKS_FILE):
        try:
            with open(TW_STOCKS_FILE, 'r', encoding='utf-8') as f:
                _TW_STOCKS_CACHE = json.load(f)
                return _TW_STOCKS_CACHE
        except Exception:
            pass
    _TW_STOCKS_CACHE = {'stocks': {}, 'name_to_code': {}}
    return _TW_STOCKS_CACHE


def resolve_stock_query(query: str) -> str:
    """
    將使用者輸入的「股票代號」或「中文股票名稱」轉換為標準代號
    例如：輸入 '慧友' -> 回傳 '5484'；輸入 '2330' -> 回傳 '2330'
    若傳入完整標籤如 '2327 國巨 ｜ 上市...'，自動解析出 '2327'
    """
    q = str(query).strip()
    if not q:
        return '2330'

    # 若格式包含空格（如 "2327 國巨 ｜ 上市" 或 "2330 台積電"），直接提取開頭的股票代號
    parts = q.split()
    if parts:
        first = parts[0]
        if first.isdigit() or (len(first) >= 4 and first[:4].isdigit()):
            return first

    db = _load_tw_stocks_dict()
    stocks = db.get('stocks', {})
    name_to_code = db.get('name_to_code', {})

    # 1. 若直接是代號
    if q in stocks:
        return q

    # 2. 若是完整中文名稱
    if q in name_to_code:
        return name_to_code[q]

    # 3. 模糊比對中文名稱
    for name, code in name_to_code.items():
        if q in name or name in q:
            return code

    # 4. 從概念股資料庫找
    concept_data = load_concept_data()
    for _, sub_cats in concept_data.get('概念分類', {}).items():
        for _, cinfo in sub_cats.items():
            for s in cinfo.get('stocks', []):
                if q == s.get('code') or q in s.get('name', ''):
                    return s.get('code')

    return q


@st.cache_data
def get_searchable_stock_options():
    """
    提供快速即時搜尋使用的全台股清單：
    - 精選台股上市櫃普通股與熱門原型 ETF（排除冷門債券型ETF與權證，確保搜尋精準度）
    - 依「權值熱門龍頭股」與「標準 4 碼個股」排序，讓輸入「國」即跳出國巨、國泰金；輸入「23」即跳出台積電、鴻海、國巨
    - 格式：'2327 國巨 ｜ 上市 · 電子工業'
    - 回傳：(options_list, code_to_label, label_to_code)
    """
    db = _load_tw_stocks_dict()
    stocks = db.get('stocks', {})

    POPULAR_STOCKS = [
        '2330', '2317', '2454', '2382', '2308', '2881', '2882', '2327', '2603',
        '3008', '2303', '2412', '2886', '2891', '2357', '3711', '2884', '2892',
        '1301', '1303', '2002', '3231', '6505', '5484', '2221', '6515',
        '0050', '0056', '00878', '00919', '00929', '00940'
    ]

    clean_stocks = []
    for code, info in stocks.items():
        # 排除債券型 ETF (結尾為 B)、權證 (6 碼以上或特定字母)
        if code.endswith('B') or code.endswith('T') or code.endswith('P') or code.endswith('F'):
            continue
        if len(code) >= 6:
            continue
        name = info.get('name', '').replace('*', '').strip()
        market = info.get('market', '').strip()
        inds = info.get('industries', [])
        ind = inds[0].strip() if inds and inds[0] else ''
        clean_stocks.append({
            'code': code,
            'name': name,
            'market': market,
            'ind': ind
        })

    def sort_key(s):
        c = s['code']
        if c in POPULAR_STOCKS:
            return (0, POPULAR_STOCKS.index(c))
        if re.match(r'^\d{4}$', c):
            return (1, int(c))
        if re.match(r'^00\d{3}$', c):
            return (2, int(c))
        return (3, c)

    clean_stocks.sort(key=sort_key)

    options_list = []
    code_to_label = {}
    label_to_code = {}

    for s in clean_stocks:
        code = s['code']
        # 精簡標籤：移除長贅字，只保留「代號 股名」，方便使用者在手機輸入與退格刪除！
        label = f"{code} {s['name']}"
        options_list.append(label)
        code_to_label[code] = label
        label_to_code[label] = code

    return options_list, code_to_label, label_to_code


def get_tw_stock_chinese_info(code: str) -> dict:
    """
    取得台股中文名稱、市場別（上市/上櫃）、中文產業分類
    """
    code = str(code).strip()
    db = _load_tw_stocks_dict()
    stocks = db.get('stocks', {})

    if code in stocks:
        return stocks[code]

    # 備用：從概念股找名稱
    concept_data = load_concept_data()
    for _, sub_cats in concept_data.get('概念分類', {}).items():
        for cname, cinfo in sub_cats.items():
            for s in cinfo.get('stocks', []):
                if s.get('code') == code:
                    return {
                        'code': code,
                        'name': s.get('name', code),
                        'industries': [cname],
                        'market': '台股',
                        'type': 'twse'
                    }

    return {
        'code': code,
        'name': code,
        'industries': ['台股上市櫃'],
        'market': '台股',
        'type': 'twse'
    }


def get_peer_stocks(code: str, limit: int = 12) -> list:
    """
    尋找同產業競爭/相關公司（用於產業生態比較）
    """
    info = get_tw_stock_chinese_info(code)
    industries = info.get('industries', [])
    db = _load_tw_stocks_dict()
    stocks = db.get('stocks', {})

    peers = []
    target_ind = [i for i in industries if i not in ('電子工業', '其他', '綜合')]
    if not target_ind and industries:
        target_ind = industries

    for scode, sdata in stocks.items():
        if scode == code or len(scode) != 4 or not scode.isdigit():
            continue
        s_inds = sdata.get('industries', [])
        if any(ind in s_inds for ind in target_ind):
            peers.append({
                'code': scode,
                'name': sdata.get('name', scode),
                'market': sdata.get('market', '上市'),
                'industry': ' / '.join(s_inds)
            })
            if len(peers) >= limit:
                break
    return peers


def format_price(price, currency='NT$'):
    try:
        return f"{currency} {float(price):,.2f}"
    except (ValueError, TypeError):
        return f"{currency} 0.00"


def format_change(change, pct_change):
    try:
        c = float(change)
        p = float(pct_change)
        arrow = "▲" if c > 0 else "▼" if c < 0 else "➖"
        return f"{arrow} {abs(c):,.2f} ({abs(p):.2f}%)"
    except (ValueError, TypeError):
        return "- 0.00 (0.00%)"


def color_for_change(value):
    """台股慣例：紅漲 (#e53935)、綠跌 (#43a047)"""
    try:
        v = float(value)
        return '#e53935' if v > 0 else '#43a047' if v < 0 else '#FAFAFA'
    except (ValueError, TypeError):
        return '#FAFAFA'


def load_concept_data():
    if os.path.exists(CONCEPT_FILE):
        try:
            with open(CONCEPT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def get_concept_tags_for_stock(code: str, concept_data: dict = None) -> list:
    """
    給定股票代號，回傳其所屬的所有概念股細項名稱清單
    支援三層結構：concept_data['概念分類'][大分類][細項概念]['stocks']
    """
    if concept_data is None:
        concept_data = load_concept_data()

    code = str(code).strip()
    tags = []

    categories = concept_data.get('概念分類', {})
    for big_cat, sub_cats in categories.items():
        if not isinstance(sub_cats, dict):
            continue
        for concept_name, cinfo in sub_cats.items():
            if not isinstance(cinfo, dict):
                continue
            for s in cinfo.get('stocks', []):
                scode = s.get('code') if isinstance(s, dict) else str(s)
                if str(scode).strip() == code:
                    if concept_name not in tags:
                        tags.append(concept_name)

    return tags


def get_concept_details_for_stock(code: str, concept_data: dict = None) -> list:
    """
    回傳該股票在各概念中的詳細定位與同概念夥伴（自動去重，防止同概念在不同大分類重複出現）
    """
    if concept_data is None:
        concept_data = load_concept_data()

    code = str(code).strip()
    details = []
    seen_concepts = set()
    categories = concept_data.get('概念分類', {})
    for big_cat, sub_cats in categories.items():
        if not isinstance(sub_cats, dict):
            continue
        for concept_name, cinfo in sub_cats.items():
            if not isinstance(cinfo, dict):
                continue
            if concept_name in seen_concepts:
                continue
            stocks_list = cinfo.get('stocks', [])
            for s in stocks_list:
                if isinstance(s, dict) and str(s.get('code')).strip() == code:
                    seen_concepts.add(concept_name)
                    details.append({
                        'big_category': big_cat,
                        'concept_name': concept_name,
                        'desc': cinfo.get('desc', ''),
                        'role': s.get('role', '概念成員'),
                        'related_stocks': stocks_list
                    })
                    break
    return details


def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 確保每個項目都有中文名稱
                normalized = []
                for item in data:
                    if isinstance(item, str):
                        cinfo = get_tw_stock_chinese_info(item)
                        normalized.append({'code': item, 'name': cinfo['name']})
                    elif isinstance(item, dict):
                        c = item.get('code', '')
                        n = item.get('name', '')
                        if not n or n == '未知' or n == c:
                            n = get_tw_stock_chinese_info(c)['name']
                        normalized.append({'code': c, 'name': n, 'note': item.get('note', '')})
                return normalized
        except Exception:
            return []
    return []


def save_watchlist(codes):
    os.makedirs(os.path.dirname(WATCHLIST_FILE), exist_ok=True)
    with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(codes, f, ensure_ascii=False, indent=2)


def get_common_css() -> str:
    """
    全站響應式行動版與桌機深色樣式（超大字體・防遮擋高清晰版）
    1. 全面放大字體（內文 18px、次要 16px、標題 22~28px、大數字 26~34px）
    2. 頂部工具列改為不透明實心黑底並預留安全上邊距，防止滑動時遮蓋上方文字
    3. 嚴格鎖定水平溢出，杜絕手機版左右滑動導致版面滑掉走位
    """
    return """
    <style>
    /* ── 嚴格禁止全頁面橫向滑動（防止資料被滑掉/畫面左右位移） ── */
    html, body {
        overflow-x: hidden !important;
        max-width: 100vw !important;
        width: 100% !important;
        box-sizing: border-box !important;
        touch-action: pan-y !important;
    }
    [data-testid="stAppViewContainer"] {
        overflow-x: hidden !important;
        overflow-y: auto !important;
        max-width: 100vw !important;
        width: 100% !important;
    }
    .main, section.main, [data-testid="stMainBlockContainer"], .block-container {
        overflow-x: hidden !important;
        max-width: 100vw !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }
    /* ── 全站基礎字體再放大 ── */
    html, body, [class*="css"], .stMarkdown, p, li, span, div {
        font-size: 18px;
    }
    /* ── 頂部工具列不透明實心背景（防止 >> Share ☆ 遮蓋下方文字） ── */
    header[data-testid="stHeader"] {
        background: #0E1117 !important;
        border-bottom: 1px solid #1E293B !important;
        z-index: 999 !important;
    }
    /* ── 全站通用深色系與卡片樣式 ── */
    .metric-card {
        background: #1C2333; border-radius: 10px; padding: 15px 17px;
        border-left: 4px solid #00D4AA; margin-bottom: 10px;
        font-size: 18px;
    }
    .up-text { color: #e53935; font-weight: bold; }
    .down-text { color: #43a047; font-weight: bold; }
    .rating-buy   { background: linear-gradient(135deg, #d32f2f, #e53935); color:white; padding:10px 22px; border-radius:10px; font-size:25px; font-weight:bold; display:inline-block; box-shadow: 0 4px 10px rgba(229,57,53,0.3); }
    .rating-watch { background: linear-gradient(135deg, #f57c00, #ff9800); color:white; padding:10px 22px; border-radius:10px; font-size:25px; font-weight:bold; display:inline-block; box-shadow: 0 4px 10px rgba(255,152,0,0.3); }
    .rating-sell  { background: linear-gradient(135deg, #2e7d32, #43a047); color:white; padding:10px 22px; border-radius:10px; font-size:25px; font-weight:bold; display:inline-block; box-shadow: 0 4px 10px rgba(67,160,71,0.3); }
    
    .market-badge { background:#00D4AA1C; border:1px solid #00D4AA; color:#00D4AA; padding:4px 11px; border-radius:6px; font-size:16.5px; font-weight:bold; }
    .sector-badge { background:#38BDF81C; border:1px solid #38BDF8; color:#38BDF8; padding:4px 11px; border-radius:6px; font-size:16.5px; font-weight:bold; }
    .concept-tag  { display:inline-block; background:#1C2333; border:1px solid #FFB30066; color:#FFD54F; padding:5px 13px; border-radius:14px; font-size:16px; font-weight:600; margin:3px 5px 3px 0; }
    
    .info-card    { background:#1C2333; border:1px solid #2A324B; border-radius:10px; padding:14px 16px; margin-bottom:10px; font-size:18px; line-height:1.7; }
    .price-box    { background:#161C28; border-left:4px solid #00D4AA; border-radius:8px; padding:12px 12px; font-size:18px; }
    .pro-box      { background:#1C2826; border-left:4px solid #e53935; border-radius:8px; padding:14px 16px; margin-bottom:10px; font-size:18px; line-height:1.7; }
    .con-box      { background:#1E241E; border-left:4px solid #43a047; border-radius:8px; padding:14px 16px; margin-bottom:10px; font-size:18px; line-height:1.7; }

    /* ── 表單控制項、下拉選單、分頁標籤與表格字體再放大 ── */
    label[data-testid="stWidgetLabel"] p {
        font-size: 17.5px !important;
        font-weight: bold !important;
        color: #F8FAFC !important;
        line-height: 1.45 !important;
    }
    input[type="text"] {
        font-size: 18.5px !important;
    }
    div[data-baseweb="select"] * {
        font-size: 17.5px !important;
    }
    button[data-baseweb="tab"] p, button[data-baseweb="tab"] {
        font-size: 17.5px !important;
        font-weight: bold !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 27px !important;
        font-weight: bold !important;
    }
    div[data-testid="stMetricLabel"] p {
        font-size: 17px !important;
        font-weight: bold !important;
        color: #CBD5E1 !important;
    }
    div[data-testid="stMetricDelta"] div {
        font-size: 15.5px !important;
    }
    div[data-testid="stExpander"] summary p {
        font-size: 17.5px !important;
        font-weight: bold !important;
    }

    /* ── 橫向滑動晶片區（限定在自己的容器內滾動，禁止撐大外層頁面） ── */
    .chips-scroll-bar {
        display: flex;
        overflow-x: auto;
        white-space: nowrap;
        gap: 8px;
        padding: 6px 2px 10px 2px;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: none;
        max-width: 100% !important;
        width: 100% !important;
        min-width: 0 !important;
        flex: 1 1 auto;
        touch-action: pan-x !important;
    }
    .chips-scroll-bar::-webkit-scrollbar {
        display: none;
    }
    .stock-chip-link {
        display: inline-flex;
        align-items: center;
        background: #1C2333;
        border: 1px solid #2E3A59;
        border-radius: 18px;
        padding: 7px 14px;
        color: #E2E8F0 !important;
        font-size: 17px !important;
        font-weight: 600;
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
        margin-right: 5px;
        font-size: 16.5px !important;
    }

    /* ── 手機版專屬佈局與超大字體 (螢幕寬度 <= 768px) ── */
    @media (max-width: 768px) {
        .main .block-container {
            padding-top: 2.8rem !important;
            padding-bottom: 2.5rem !important;
            padding-left: 0.6rem !important;
            padding-right: 0.6rem !important;
            max-width: 100% !important;
        }
        header[data-testid="stHeader"] {
            height: 2.5rem !important;
            background: #0E1117 !important;
            border-bottom: 1px solid #1E293B !important;
        }
        div[data-testid="stVerticalBlock"] > div {
            gap: 0.5rem !important;
        }
        h1 {
            font-size: 1.7rem !important;
            margin: 0.3rem 0 !important;
            line-height: 1.35 !important;
        }
        h2 {
            font-size: 1.5rem !important;
            margin: 0.35rem 0 !important;
            line-height: 1.35 !important;
        }
        h3 {
            font-size: 1.35rem !important;
            margin: 0.3rem 0 !important;
            line-height: 1.35 !important;
        }
        h4, h5, h6 {
            font-size: 1.2rem !important;
            margin: 0.25rem 0 !important;
            line-height: 1.35 !important;
        }
        hr {
            margin: 0.5rem 0 !important;
        }
        .stButton > button {
            padding: 0.45rem 0.85rem !important;
            font-size: 17.5px !important;
            font-weight: bold !important;
            min-height: 2.6rem !important;
            border-radius: 8px !important;
        }
        button[data-baseweb="tab"], button[data-baseweb="tab"] p {
            padding: 7px 11px !important;
            font-size: 17px !important;
            font-weight: bold !important;
        }
        .js-plotly-plot {
            margin-bottom: 0.35rem !important;
        }
    }
    .modebar, .modebar-container, button[title="View fullscreen"], [data-testid="StyledFullScreenButton"] {
        display: none !important;
    }

    /* ── 頂部 5 大功能快速導覽列（手機/電腦皆固定單行並排） ── */
    .top-nav-bar {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 4px;
        margin-bottom: 10px;
        background: #141923;
        padding: 5px 3px;
        border-radius: 10px;
        border: 1px solid #263044;
    }
    .top-nav-item {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 7px 1px;
        border-radius: 6px;
        font-size: 14.5px;
        font-weight: bold;
        color: #94A3B8 !important;
        text-decoration: none !important;
        text-align: center;
        transition: all 0.15s ease;
        white-space: nowrap;
    }
    .top-nav-item:hover {
        background: #1C2536;
        color: #FAFAFA !important;
    }
    .top-nav-item.active {
        background: #00D4AA22;
        border: 1px solid #00D4AA;
        color: #00D4AA !important;
    }
    @media (max-width: 600px) {
        .nav-full { display: none !important; }
        .nav-mobile { display: inline !important; }
        .top-nav-item { padding: 7px 2px !important; font-size: 15px !important; }
    }
    @media (min-width: 601px) {
        .nav-full { display: inline !important; }
        .nav-mobile { display: none !important; }
    }
    .quote-row-link, .quote-row-link * {
        text-decoration: none !important;
    }
    .quote-row-link:hover {
        background: #111726 !important;
    }
    </style>
    """


def inject_pwa_and_ux_enhancements():
    """
    注入 PWA 全螢幕模式 (Standalone App) 與手機端點擊輸入框自動全選 JS
    1. 注入 PWA manifest, service worker 與 meta 標籤（支援 Android/iOS 獨立全螢幕 App，無網址列）
    2. 點擊/聚焦輸入框時自動 select() 全選，支援一秒取代或單次退格清空
    3. 全域鎖定 documentElement, body, container 之 overflowX = 'hidden'，徹底禁止手機頁面被滑掉
    """
    import streamlit.components.v1 as components
    components.html("""
    <script>
    (function() {
        try {
            var p = window.parent || window.top;
            if (!p || !p.document) return;
            var doc = p.document;

            // 1. 嚴格鎖定父視窗頁面禁止水平位移滑掉（動態注入高優先級樣式）
            if (doc.head && !p._pwaOverflowLocked) {
                p._pwaOverflowLocked = true;
                var styleEl = doc.createElement('style');
                styleEl.id = '_ux_overflow_lock';
                styleEl.textContent = 'html, body { overflow-x: hidden !important; max-width: 100vw !important; touch-action: pan-y !important; } [data-testid="stAppViewContainer"] { overflow-x: hidden !important; overflow-y: auto !important; max-width: 100vw !important; } .main, .block-container { overflow-x: hidden !important; max-width: 100vw !important; }';
                doc.head.appendChild(styleEl);
            }
            if (doc.documentElement) {
                doc.documentElement.style.overflowX = 'hidden';
                doc.documentElement.style.maxWidth = '100vw';
            }
            if (doc.body) {
                doc.body.style.overflowX = 'hidden';
                doc.body.style.maxWidth = '100vw';
            }

            // 2. 注入 PWA Web App Manifest 與全螢幕 Meta 標籤
            if (doc.head && !p._pwaStandaloneInjected) {
                p._pwaStandaloneInjected = true;
                
                var metas = [
                    { name: 'mobile-web-app-capable', content: 'yes' },
                    { name: 'apple-mobile-web-app-capable', content: 'yes' },
                    { name: 'apple-mobile-web-app-status-bar-style', content: 'black-translucent' },
                    { name: 'theme-color', content: '#0E1117' }
                ];
                metas.forEach(function(m) {
                    var el = doc.querySelector('meta[name="' + m.name + '"]');
                    if (!el) {
                        el = doc.createElement('meta');
                        el.name = m.name;
                        doc.head.appendChild(el);
                    }
                    el.content = m.content;
                });

                // Manifest link
                var link = doc.querySelector('link[rel="manifest"]');
                if (link) {
                    link.href = '/app/static/manifest.json';
                } else {
                    link = doc.createElement('link');
                    link.rel = 'manifest';
                    link.href = '/app/static/manifest.json';
                    doc.head.appendChild(link);
                }

                // Apple touch icon
                var appleIcon = doc.querySelector('link[rel="apple-touch-icon"]');
                if (!appleIcon) {
                    appleIcon = doc.createElement('link');
                    appleIcon.rel = 'apple-touch-icon';
                    appleIcon.href = 'https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f4ca.png';
                    doc.head.appendChild(appleIcon);
                }
            }

            // 3. 註冊 Service Worker 滿足 Chrome PWA 安裝條件
            if (window.navigator && window.navigator.serviceWorker && !p._pwaSwRegistered) {
                p._pwaSwRegistered = true;
                try {
                    window.navigator.serviceWorker.register('/app/static/sw.js').catch(function(){});
                } catch(e){}
            }

            // 4. 點擊/聚焦輸入框自動全選文字（一秒替換，無需從結尾逐字刪除）
            if (!p._autoSelectInjected) {
                p._autoSelectInjected = true;
                function doSelect(target) {
                    if (target && (target.tagName === 'INPUT' || target.getAttribute('role') === 'combobox')) {
                        setTimeout(function() {
                            try { target.select(); } catch(err){}
                        }, 50);
                    }
                }
                doc.addEventListener('focusin', function(e) { doSelect(e.target); });
                doc.addEventListener('click', function(e) {
                    if (e.target && e.target.tagName === 'INPUT') {
                        // 延遲選取避免手機游標事件覆蓋
                        setTimeout(function() {
                            try { e.target.select(); } catch(err){}
                        }, 80);
                    }
                });
            }
        } catch(err) {
            console.error('UX script error:', err);
        }
    })();
    </script>
    """, height=0, width=0)


def get_top_nav_html(active: str = 'home') -> str:
    """產生手機與電腦皆可一鍵切換的頂部 5 格導覽列 HTML（手機響應式自動縮字）"""
    items = [
        ('home', '📊 盤後日報', '📊 日報'),
        ('radar', '🚀 策略推薦', '🚀 推薦'),
        ('stock', '🔍 股票分析', '🔍 分析'),
        ('concept', '🏷️ 概念股', '🏷️ 概念'),
        ('watch', '⭐ 自選股', '⭐ 自選'),
    ]
    links = []
    for key, label_full, label_mob in items:
        cls = "top-nav-item active" if key == active else "top-nav-item"
        links.append(
            f'<a href="/?nav={key}" target="_self" class="{cls}">'
            f'<span class="nav-full">{label_full}</span>'
            f'<span class="nav-mobile">{label_mob}</span>'
            f'</a>'
        )
    return f'<div class="top-nav-bar">{"".join(links)}</div>'


def _make_kbar_svg(open_p: float, high_p: float, low_p: float, close_p: float, prev_close: float) -> str:
    """繪製左側迷你紅綠 K 棒 SVG（含上下影線與實體）"""
    if close_p > open_p:
        color = "#ff3b5c"
    elif close_p < open_p:
        color = "#00e676"
    else:
        color = "#ff3b5c" if close_p >= prev_close else "#00e676"

    hi = max(high_p, open_p, close_p)
    lo = min(low_p, open_p, close_p)
    span = hi - lo

    if span <= 1e-6:
        return (
            f'<svg width="14" height="32" viewBox="0 0 14 32" style="flex-shrink:0;margin-right:6px;">'
            f'<line x1="7" y1="10" x2="7" y2="22" stroke="{color}" stroke-width="1.8"/>'
            f'<rect x="2" y="14.5" width="10" height="3" rx="1" fill="{color}"/>'
            f'</svg>'
        )

    def to_y(val):
        return 28.0 - ((val - lo) / span) * 24.0

    y_open = to_y(open_p)
    y_close = to_y(close_p)
    y_top = min(y_open, y_close)
    body_h = max(2.8, abs(y_close - y_open))

    return (
        f'<svg width="14" height="32" viewBox="0 0 14 32" style="flex-shrink:0;margin-right:6px;">'
        f'<line x1="7" y1="3" x2="7" y2="29" stroke="{color}" stroke-width="1.8" stroke-linecap="round"/>'
        f'<rect x="2.5" y="{y_top:.1f}" width="9" height="{body_h:.1f}" rx="1.2" fill="{color}"/>'
        f'</svg>'
    )


def _make_sparkline_svg(uid: str, prices: list, prev_close: float, close_p: float) -> str:
    """繪製右側迷你盤中走勢圖 SVG（平盤虛線 + 平盤以上紅、平盤以下綠雙色漸層）"""
    pts = [float(x) for x in prices if x is not None and float(x) > 0]
    if len(pts) < 2:
        base = close_p if close_p > 0 else 100.0
        pts = [base, base]

    ref = prev_close if prev_close > 0 else pts[0]
    min_v = min(min(pts), ref)
    max_v = max(max(pts), ref)
    pad = max((max_v - min_v) * 0.08, ref * 0.003, 0.01)
    lo = min_v - pad
    hi = max_v + pad
    span = max(hi - lo, 0.01)

    w, h = 104.0, 40.0

    def to_y(val):
        y = 36.0 - ((val - lo) / span) * 32.0
        return max(3.0, min(37.0, y))

    y_ref = to_y(ref)
    n = len(pts)
    coords = []
    for i, p in enumerate(pts):
        x = 2.0 + (i / (n - 1)) * 100.0
        y = to_y(p)
        coords.append((x, y))

    poly_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    area_str = f"2.0,{y_ref:.1f} {poly_str} 102.0,{y_ref:.1f}"

    return (
        f'<svg width="104" height="40" viewBox="0 0 104 40" style="display:block;background:#090D14;border:1px solid #1E293B;border-radius:4px;">'
        f'<defs>'
        f'<clipPath id="ca_{uid}"><rect x="0" y="0" width="104" height="{y_ref:.1f}"/></clipPath>'
        f'<clipPath id="cb_{uid}"><rect x="0" y="{y_ref:.1f}" width="104" height="{40.0 - y_ref:.1f}"/></clipPath>'
        f'<linearGradient id="gr_{uid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="#ff3b5c" stop-opacity="0.48"/>'
        f'<stop offset="100%" stop-color="#ff3b5c" stop-opacity="0.06"/>'
        f'</linearGradient>'
        f'<linearGradient id="gg_{uid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="#00e676" stop-opacity="0.06"/>'
        f'<stop offset="100%" stop-color="#00e676" stop-opacity="0.48"/>'
        f'</linearGradient>'
        f'</defs>'
        f'<line x1="0" y1="{y_ref:.1f}" x2="104" y2="{y_ref:.1f}" stroke="#64748B" stroke-width="1" stroke-dasharray="2.5,2.5"/>'
        f'<g clip-path="url(#ca_{uid})">'
        f'<polygon points="{area_str}" fill="url(#gr_{uid})"/>'
        f'<polyline points="{poly_str}" fill="none" stroke="#ff3b5c" stroke-width="1.5" stroke-linejoin="round"/>'
        f'</g>'
        f'<g clip-path="url(#cb_{uid})">'
        f'<polygon points="{area_str}" fill="url(#gg_{uid})"/>'
        f'<polyline points="{poly_str}" fill="none" stroke="#00e676" stroke-width="1.5" stroke-linejoin="round"/>'
        f'</g>'
        f'</svg>'
    )


def render_quote_table_html(rows: list) -> str:
    """
    將多檔股票報價渲染為仿專業看盤 App 的深色列表 HTML
    rows 每個元素包含: code, name, market_short, role, open, high, low, close, prev_close, change, pct_change, sparkline
    """
    html_parts = [
        '<div style="background:#070A10;border:1px solid #1E2638;border-radius:12px;overflow:hidden;margin-top:4px;">',
        '<div style="display:grid;grid-template-columns:1.35fr 1.15fr 108px;align-items:center;padding:8px 10px;background:#0F1420;border-bottom:1px solid #1E2638;color:#94A3B8;font-size:12px;font-weight:bold;">',
        '<div>股名</div>',
        '<div style="text-align:right;padding-right:8px;">成交價 ｜ 漲跌幅</div>',
        '<div style="text-align:center;">走勢圖</div>',
        '</div>'
    ]

    for idx, r in enumerate(rows):
        code = str(r.get('code', ''))
        name = str(r.get('name', code))
        m_short = str(r.get('market_short', '市'))
        role = str(r.get('role', '')).strip()
        open_p = float(r.get('open', 0.0))
        high_p = float(r.get('high', 0.0))
        low_p = float(r.get('low', 0.0))
        close_p = float(r.get('close', 0.0))
        prev_c = float(r.get('prev_close', 0.0))
        chg = float(r.get('change', 0.0))
        pct = float(r.get('pct_change', 0.0))
        spark = r.get('sparkline', [])

        if chg > 0:
            p_color = "#ff3b5c"
            chg_str = f"+{chg:.2f} ▲{abs(pct):.2f}%"
        elif chg < 0:
            p_color = "#00e676"
            chg_str = f"{chg:.2f} ▼{abs(pct):.2f}%"
        else:
            p_color = "#E2E8F0"
            chg_str = f"0.00 0.00%"

        price_str = f"{close_p:.2f}" if close_p > 0 else "--"
        kbar_svg = _make_kbar_svg(open_p, high_p, low_p, close_p, prev_c)
        spark_svg = _make_sparkline_svg(f"{code}_{idx}", spark, prev_c, close_p)

        role_badge = ""
        if role:
            short_role = role[:9] + ("…" if len(role) > 9 else "")
            role_badge = f'<span style="display:inline-block;background:#1E293B;color:#CBD5E1;font-size:10px;padding:1px 5px;border-radius:4px;margin-left:5px;vertical-align:middle;">{short_role}</span>'

        row_html = (
            f'<a href="/?stock={code}" target="_self" class="quote-row-link" style="display:grid;grid-template-columns:1.35fr 1.15fr 108px;align-items:center;padding:10px 10px;border-bottom:1px solid #161D2B;text-decoration:none !important;background:#070A10;transition:background 0.12s;">'
            f'<div style="display:flex;align-items:center;min-width:0;">'
            f'{kbar_svg}'
            f'<div style="min-width:0;overflow:hidden;">'
            f'<div style="color:#FFFFFF;font-size:17px;font-weight:bold;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{name}</div>'
            f'<div style="color:#94A3B8;font-size:12px;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
            f'<span style="background:#1E293B;color:#94A3B8;border-radius:50%;padding:0px 4px;font-size:10px;margin-right:3px;">⏳</span>'
            f'{code} {m_short}{role_badge}'
            f'</div>'
            f'</div>'
            f'</div>'
            f'<div style="text-align:right;padding-right:10px;">'
            f'<div style="color:{p_color};font-size:19px;font-weight:800;line-height:1.15;font-family:\'Segoe UI\',Roboto,sans-serif;">{price_str}</div>'
            f'<div style="color:{p_color};font-size:12px;font-weight:600;margin-top:3px;">{chg_str}</div>'
            f'</div>'
            f'<div style="display:flex;justify-content:center;">{spark_svg}</div>'
            f'</a>'
        )
        html_parts.append(row_html)

    html_parts.append('</div>')
    return "".join(html_parts)


