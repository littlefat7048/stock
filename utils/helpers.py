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
