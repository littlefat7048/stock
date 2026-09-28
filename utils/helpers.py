"""
工具函式庫
包含：台股中文名稱查詢、價格格式化、概念股與同業查詢、自選股存取
"""
import json
import os

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
    """
    q = str(query).strip()
    if not q:
        return '2330'

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
    回傳該股票在各概念中的詳細定位與同概念夥伴
    """
    if concept_data is None:
        concept_data = load_concept_data()

    code = str(code).strip()
    details = []
    categories = concept_data.get('概念分類', {})
    for big_cat, sub_cats in categories.items():
        if not isinstance(sub_cats, dict):
            continue
        for concept_name, cinfo in sub_cats.items():
            if not isinstance(cinfo, dict):
                continue
            stocks_list = cinfo.get('stocks', [])
            for s in stocks_list:
                if isinstance(s, dict) and str(s.get('code')).strip() == code:
                    details.append({
                        'big_category': big_cat,
                        'concept_name': concept_name,
                        'desc': cinfo.get('desc', ''),
                        'role': s.get('role', '概念成員'),
                        'related_stocks': stocks_list
                    })
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
    全站響應式行動版與桌機深色樣式
    針對手機螢幕（寬度 <= 768px）進行深度緊湊化排版優化，消除過度鬆散的空白間距
    """
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
        .main .block-container {
            padding-top: 0.6rem !important;
            padding-bottom: 2rem !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
            max-width: 100% !important;
        }
        header[data-testid="stHeader"] {
            height: 2.2rem !important;
            background: rgba(14, 17, 23, 0.8) !important;
        }
        div[data-testid="stVerticalBlock"] > div {
            gap: 0.35rem !important;
        }
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
        .stButton > button {
            padding: 0.3rem 0.6rem !important;
            font-size: 0.85rem !important;
            min-height: 2rem !important;
            border-radius: 8px !important;
        }
        button[data-baseweb="tab"] {
            padding: 5px 8px !important;
            font-size: 12px !important;
        }
        .js-plotly-plot {
            margin-bottom: 0.2rem !important;
        }
    }

    /* ── 頂部 4 大功能快速導覽列（手機/電腦皆固定單行並排） ── */
    .top-nav-bar {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 6px;
        margin-bottom: 8px;
        background: #141923;
        padding: 5px;
        border-radius: 10px;
        border: 1px solid #263044;
    }
    .top-nav-item {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 6px 2px;
        border-radius: 7px;
        font-size: 13px;
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
    .quote-row-link, .quote-row-link * {
        text-decoration: none !important;
    }
    .quote-row-link:hover {
        background: #111726 !important;
    }
    </style>
    """


def get_top_nav_html(active: str = 'home') -> str:
    """產生手機與電腦皆可一鍵切換的頂部 4 格導覽列 HTML"""
    items = [
        ('home', '📊 盤後日報'),
        ('stock', '🔍 股票分析'),
        ('concept', '🏷️ 概念股'),
        ('watch', '⭐ 自選股'),
    ]
    links = []
    for key, label in items:
        cls = "top-nav-item active" if key == active else "top-nav-item"
        links.append(f'<a href="/?nav={key}" target="_self" class="{cls}">{label}</a>')
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


