"""
台股資料擷取模組
整合：
1. 本地台股中文名稱與產業資料庫 (data/tw_stocks_info.json)
2. FinMind 免費公開 API（PER/PBR/殖利率、月營收、季財報 EPS/三率）
3. Yahoo Finance (yfinance) 歷史 K 線、52週高低點、市值
4. 台灣證交所 (TWSE) 大盤與法人統計
"""
import os
import re
import json
import time
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from utils.helpers import get_tw_stock_chinese_info

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_EXPIRY_SECONDS = 3600  # 1 小時快取

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"


def _get_cache(key):
    path = os.path.join(CACHE_DIR, f"{key}.json")
    if os.path.exists(path):
        mtime = os.path.getmtime(path)
        if time.time() - mtime < CACHE_EXPIRY_SECONDS:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return None
    return None


def _set_cache(key, data):
    path = os.path.join(CACHE_DIR, f"{key}.json")
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def normalize_ticker(code: str) -> str:
    """
    自動判斷台股是上市 (.TW) 或上櫃 (.TWO)
    優先依據 tw_stocks_info.json 的 market type 決定
    """
    code = str(code).strip().upper()
    if code.endswith('.TW') or code.endswith('.TWO'):
        return code

    cinfo = get_tw_stock_chinese_info(code)
    mtype = cinfo.get('type', 'twse')

    if mtype == 'tpex':
        primary, secondary = f"{code}.TWO", f"{code}.TW"
    else:
        primary, secondary = f"{code}.TW", f"{code}.TWO"

    try:
        tk = yf.Ticker(primary)
        hist = tk.history(period='5d')
        if not hist.empty:
            return primary
    except Exception:
        pass

    return secondary


def _parse_float(val_str):
    if not val_str:
        return None
    s = str(val_str).replace(',', '').replace('%', '').replace('元', '').replace('　', '').strip()
    m = re.search(r'[-+]?\d+(?:\.\d+)?', s)
    if m:
        try:
            return float(m.group(0))
        except Exception:
            return None
    return None


def _parse_revenue_mix(raw_str: str) -> list:
    """
    將 MoneyDJ 營收比重字串（如：'潔淨級管配件39.21%、廠務服務34.23%、不銹鋼焊接管配件25.41%、其他1.15% (2025年)'）
    解析為 [{'name': '潔淨級管配件', 'pct': 39.21}, ...]
    """
    if not raw_str:
        return []
    clean = re.sub(r'\(\d{4}年?\)', '', str(raw_str)).strip()
    items = []
    parts = re.split(r'[、,，;；]', clean)
    for p in parts:
        p = p.strip()
        if not p:
            continue
        m = re.match(r'^(.+?)\s*([-+]?\d+(?:\.\d+)?)\s*%$', p)
        if m:
            name = m.group(1).strip()
            try:
                pct = float(m.group(2))
                if name and pct > 0:
                    items.append({'name': name, 'pct': pct})
            except Exception:
                pass
    items.sort(key=lambda x: x['pct'], reverse=True)
    return items


def _infer_related_industries(main_business: list, revenue_mix_raw: str, moneydj_inds: list, official_inds: list) -> list:
    """
    根據主要經營業務、產品營收比重、MoneyDJ細分產業與官方分類，自動推論具體的「相關產業與應用領域」標籤
    解決許多台股（如 2221 大甲）官方分類僅顯示「其他」而看不出實際產業的問題
    """
    combined_text = " ".join(main_business or []) + " " + (revenue_mix_raw or "") + " " + " ".join(moneydj_inds or [])
    tags = []

    keyword_rules = [
        (['半導體廠務', '廠務工程', '廠務服務', '無塵室'], '半導體廠務工程'),
        (['潔淨級', '超純', '高潔淨'], '超純潔淨級管配件/耗材'),
        (['特殊氣體', '特殊化學', '特用化學', '氣體供應', '化學品供應'], '特殊氣體與化學品供應系統'),
        (['不鏽鋼', '不銹鋼', '焊接管', '焊管'], '不鏽鋼管件與金屬製品'),
        (['CoWoS', '先進封裝', 'SoIC', 'FOPLP', '玻璃基板'], '先進封裝 / CoWoS 供應鏈'),
        (['探針卡', '測試座', 'Socket', '老化測試', '晶圓測試', 'IC測試'], '半導體測試介面與設備'),
        (['晶圓代工', '晶圓製造'], '晶圓代工與製造'),
        (['IC設計', '特殊應用積體電路', 'ASIC', 'IP', '矽智財'], 'IC設計與ASIC矽智財'),
        (['伺服器', 'AI伺服器', '雲端資料中心'], 'AI 伺服器與資料中心'),
        (['散熱', '水冷', '液冷', '均熱片', '導熱'], '散熱模組與液冷方案'),
        (['光通訊', '光纖', '矽光子', 'CPO', '光收發', '磊晶'], '光通訊與矽光子 CPO'),
        (['印刷電路板', 'PCB', '銅箔基板', 'CCL', 'ABF', '載板', 'HDI'], 'PCB 與 IC 載板'),
        (['被動元件', '電容', '電阻', '電感', 'MLCC'], '被動元件'),
        (['連接器', '連接線', '線束'], '高速連接器與線束'),
        (['機器人', '機械手臂', '減速機', '自動化設備', '視覺感測'], '機器人與智慧自動化'),
        (['監控', '攝影機', '安控', '影像處理', '車載鏡頭'], '智慧安控與邊緣視覺 AI'),
        (['車用', '電動車', '汽車', '車載', '充電樁'], '車用電子與汽車零組件'),
        (['重電', '變壓器', '配電盤', '電網', '電纜'], '重電設備與強韌電網'),
        (['太陽能', '風電', '儲能', '綠能', '再生能源'], '綠能與儲能系統'),
        (['航太', '無人機', '衛星', '低軌衛星', '軍工'], '航太、低軌衛星與軍工'),
        (['新藥', '生技', '醫療器材', '醫材', '保健', '製藥'], '生技醫療與製藥'),
    ]

    for kw_list, label in keyword_rules:
        if any(kw in combined_text for kw in kw_list):
            if label not in tags:
                tags.append(label)

    for ind in (moneydj_inds or []):
        ind_clean = ind.strip()
        if ind_clean and ind_clean not in ('其他', '台股') and ind_clean not in tags:
            tags.append(ind_clean)

    for oind in (official_inds or []):
        o_clean = oind.strip()
        if o_clean and o_clean not in ('其他', '台股', '台股產業') and o_clean not in tags:
            tags.append(o_clean)

    # 若仍無特定標籤，從營收比重前兩大產品提取
    if not tags and revenue_mix_raw:
        for item in _parse_revenue_mix(revenue_mix_raw)[:3]:
            if item['name'] != '其他' and item['name'] not in tags:
                tags.append(item['name'])

    return tags[:8]


def _fetch_extended_company_profile(code: str, ticker: str, chinese_name: str) -> dict:
    """
    平行抓取 MoneyDJ (基本資料 zca、所屬產業 zcs、個股動態新聞 zcv)
    與 Yahoo奇摩股市 (公司基本資料 /profile、個股新聞公告 /news)
    """
    from bs4 import BeautifulSoup
    from concurrent.futures import ThreadPoolExecutor

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    }
    ext = {
        'main_business': [],
        'revenue_mix_raw': '',
        'revenue_mix_items': [],
        'moneydj_industries': [],
        'pe': None,
        'industry_avg_pe': None,
        'pb': None,
        'dividend_yield': None,
        'net_worth_per_share': None,
        'gross_margin_pct': None,
        'operating_margin_pct': None,
        'pretax_margin_pct': None,
        'roe_pct': None,
        'roa_pct': None,
        'debt_ratio_pct': None,
        'director_holding_pct': None,
        'cash_dividend': None,
        'capital_yi': None,
        'market_cap': None,
        'recent_news': [],
    }

    urls = {
        'zca': (f"https://justdata.moneydj.com/z/zc/zca/zca_{code}.djhtm", 'cp950'),
        'zcs': (f"https://justdata.moneydj.com/z/zc/zcs/zcs_{code}.djhtm", 'cp950'),
        'zcv': (f"https://justdata.moneydj.com/z/zc/zcv/zcv_{code}.djhtm", 'cp950'),
        'y_prof': (f"https://tw.stock.yahoo.com/quote/{ticker}/profile", 'utf-8'),
        'y_news': (f"https://tw.stock.yahoo.com/quote/{ticker}/news", 'utf-8'),
    }

    def _get_html(item):
        k, (u, enc) = item
        try:
            r = requests.get(u, headers=headers, timeout=6)
            if r.status_code == 200:
                if enc == 'cp950':
                    txt = r.content.decode('cp950', errors='replace').replace('合恲', '合併')
                    return k, txt
                r.encoding = enc
                return k, r.text
        except Exception:
            pass
        return k, ''

    pages = {}
    try:
        with ThreadPoolExecutor(max_workers=5) as ex:
            for k, html in ex.map(_get_html, urls.items()):
                pages[k] = html
    except Exception:
        pass

    # 1. 解析 MoneyDJ zca (基本面指標與營收比重)
    if pages.get('zca'):
        try:
            soup = BeautifulSoup(pages['zca'], 'html.parser')
            tds = soup.find_all('td')
            for i in range(len(tds) - 1):
                lbl = tds[i].get_text(strip=True).replace('　', '').replace(' ', '')
                val = tds[i + 1].get_text(' ', strip=True).replace('　', ' ').strip()
                if not lbl or len(lbl) > 15:
                    continue
                if lbl == '營收比重' and val and len(val) < 250:
                    ext['revenue_mix_raw'] = val
                    ext['revenue_mix_items'] = _parse_revenue_mix(val)
                elif lbl == '本益比':
                    v = _parse_float(val)
                    if v and v > 0:
                        ext['pe'] = v
                elif lbl == '同業平均本益比':
                    v = _parse_float(val)
                    if v and v > 0:
                        ext['industry_avg_pe'] = v
                elif lbl == '股價淨值比':
                    v = _parse_float(val)
                    if v and v > 0:
                        ext['pb'] = v
                elif lbl == '殖利率':
                    v = _parse_float(val)
                    if v is not None and v >= 0:
                        ext['dividend_yield'] = v / 100.0
                elif lbl == '每股淨值(元)':
                    v = _parse_float(val)
                    if v is not None:
                        ext['net_worth_per_share'] = v
                elif lbl == '營業毛利率':
                    ext['gross_margin_pct'] = _parse_float(val)
                elif lbl == '營業利益率':
                    ext['operating_margin_pct'] = _parse_float(val)
                elif lbl == '稅前淨利率':
                    ext['pretax_margin_pct'] = _parse_float(val)
                elif lbl == '股東權益報酬率':
                    ext['roe_pct'] = _parse_float(val)
                elif lbl == '資產報酬率':
                    ext['roa_pct'] = _parse_float(val)
                elif lbl == '負債比例':
                    ext['debt_ratio_pct'] = _parse_float(val)
                elif lbl == '現金股利':
                    v = _parse_float(val)
                    if v is not None:
                        ext['cash_dividend'] = v
                elif lbl in ('股本(億,台幣)', '股本(億)'):
                    v = _parse_float(val)
                    if v is not None:
                        ext['capital_yi'] = v
        except Exception:
            pass

    # 2. 解析 MoneyDJ zcs (所屬細分產業)
    if pages.get('zcs'):
        try:
            soup = BeautifulSoup(pages['zcs'], 'html.parser')
            tds = soup.find_all('td')
            for i in range(len(tds) - 1):
                lbl = tds[i].get_text(strip=True).replace('　', '').replace(' ', '')
                if lbl == '所屬產業':
                    val = tds[i + 1].get_text(' ', strip=True)
                    inds = [x.strip() for x in re.split(r'[、,，\s]+', val) if x.strip()]
                    ext['moneydj_industries'] = inds
                    break
        except Exception:
            pass

    # 3. 解析 Yahoo奇摩股市 /profile (主要經營業務、董監持股、同業本益比備援)
    if pages.get('y_prof'):
        try:
            soup = BeautifulSoup(pages['y_prof'], 'html.parser')
            items = [t.strip() for t in soup.stripped_strings if t.strip()]
            for idx, text in enumerate(items):
                if text == '主要經營業務' and idx + 1 < len(items):
                    biz_raw = items[idx + 1]
                    if biz_raw not in ('配股資訊', '財務資訊', '-'):
                        biz_lines = [b.strip() for b in re.split(r'[\r\n;；]+', biz_raw) if b.strip()]
                        ext['main_business'] = biz_lines
                elif text == '董監持股比例(%)' and idx + 1 < len(items):
                    v = _parse_float(items[idx + 1])
                    if v is not None:
                        ext['director_holding_pct'] = v
                elif text == '市值 (百萬)' and idx + 1 < len(items):
                    v = _parse_float(items[idx + 1])
                    if v and v > 0:
                        ext['market_cap'] = v * 1e6
                elif text == '本益比 (同業平均)' and idx >= 1:
                    prev_t = items[idx - 1]
                    m = re.search(r'([\d.]+)\s*\(\s*([\d.]+)\s*\)', prev_t)
                    if m:
                        if ext['pe'] is None:
                            ext['pe'] = float(m.group(1))
                        if ext['industry_avg_pe'] is None:
                            ext['industry_avg_pe'] = float(m.group(2))
                elif text == '營業毛利率' and ext['gross_margin_pct'] is None and idx + 1 < len(items):
                    ext['gross_margin_pct'] = _parse_float(items[idx + 1])
                elif text == '營業利益率' and ext['operating_margin_pct'] is None and idx + 1 < len(items):
                    ext['operating_margin_pct'] = _parse_float(items[idx + 1])
                elif text == '稅前淨利率' and ext['pretax_margin_pct'] is None and idx + 1 < len(items):
                    ext['pretax_margin_pct'] = _parse_float(items[idx + 1])
                elif text == '股東權益報酬率' and ext['roe_pct'] is None and idx + 1 < len(items):
                    ext['roe_pct'] = _parse_float(items[idx + 1])
                elif text == '每股淨值' and ext['net_worth_per_share'] is None and idx + 1 < len(items):
                    ext['net_worth_per_share'] = _parse_float(items[idx + 1])
                elif text == '現金股利' and ext['cash_dividend'] is None and idx + 1 < len(items):
                    ext['cash_dividend'] = _parse_float(items[idx + 1])
        except Exception:
            pass

    # 4. 解析個股近期重要新聞與獲利/營收公告 (結合 MoneyDJ zcv 與 Yahoo /news)
    news_list = []
    seen_titles = set()
    ignore_patterns = [
        '注意有價證券名單', '處置有價證券名單', '注意證券名單', '處置證券名單',
        '當日融券賣出', '標借證券', '融資比率、融券保證金', '零股交易成交股數',
        '盤後零股交易', '融資融券暫停與恢復', '得為融資融券'
    ]
    if pages.get('zcv'):
        try:
            soup = BeautifulSoup(pages['zcv'], 'html.parser')
            for tr in soup.find_all('tr'):
                row_tds = tr.find_all('td', recursive=False)
                if len(row_tds) == 2:
                    d_str = row_tds[0].get_text(strip=True)
                    title = row_tds[1].get_text(' ', strip=True)
                    if re.match(r'^\d{2,3}/\d{2}/\d{2}$', d_str) and len(title) > 6:
                        if any(ig in title for ig in ignore_patterns):
                            continue
                        clean_t = re.sub(rf'^{code}\s*', '', title).strip()
                        if clean_t not in seen_titles:
                            seen_titles.add(clean_t)
                            news_list.append(f"[{d_str}] {clean_t}")
        except Exception:
            pass

    if pages.get('y_news'):
        try:
            soup = BeautifulSoup(pages['y_news'], 'html.parser')
            for h3 in soup.find_all('h3'):
                t = h3.get_text(strip=True)
                if len(t) > 10 and (chinese_name in t or '【公告】' in t or '營收' in t or '獲利' in t or 'EPS' in t):
                    if '注意交易資訊標準' in t and any('注意交易資訊標準' in x for x in seen_titles):
                        continue
                    if t not in seen_titles:
                        seen_titles.add(t)
                        news_list.append(t)
        except Exception:
            pass

    ext['recent_news'] = news_list[:8]
    return ext


def get_stock_info(code: str) -> dict:
    """
    取得台股完整基本面資訊（全中文名稱、上市櫃別、主要經營業務、產品營收比重、細分相關產業、PE、同業平均PE、PB、殖利率、三率、ROE、近期新聞等）
    """
    code = str(code).strip()
    cache_key = f"stock_info_v4_{code}"
    cached = _get_cache(cache_key)
    if cached:
        return cached

    # 1. 先從本地台股字典取得正確中文名稱與產業
    tw_info = get_tw_stock_chinese_info(code)
    chinese_name = tw_info.get('name', code)
    market_label = tw_info.get('market', '上市')
    industries = tw_info.get('industries', ['台股'])
    sector_zh = ' / '.join(industries) if industries else '台股產業'
    ticker = normalize_ticker(code)

    result = {
        'code': code,
        'name': chinese_name,
        'english_name': '',
        'market': market_label,
        'sector': sector_zh,
        'official_sector': sector_zh,
        'industries': industries,
        'related_industries': [],
        'main_business': [],
        'revenue_mix_raw': '',
        'revenue_mix_items': [],
        'recent_news': [],
        'pe': None,
        'industry_avg_pe': None,
        'pb': None,
        'dividend_yield': None,  # 以小數儲存，例如 0.045 代表 4.5%
        'net_worth_per_share': None,
        'cash_dividend': None,
        'capital_yi': None,
        'director_holding_pct': None,
        'debt_ratio_pct': None,
        'market_cap': None,
        '52w_high': None,
        '52w_low': None,
        'roe': None,
        'roa': None,
        'gross_margin': None,
        'operating_margin': None,
        'profit_margin': None,
        'revenue_growth': None,
        'earnings_growth': None,
        'summary_zh': ''
    }

    # 2. 從 FinMind 取得最新官方 PER / PBR / 殖利率
    try:
        start_d = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        r = requests.get(
            FINMIND_URL,
            params={'dataset': 'TaiwanStockPER', 'data_id': code, 'start_date': start_d},
            timeout=6
        )
        rows = r.json().get('data', [])
        if rows:
            latest_per = rows[-1]
            if latest_per.get('PER') and float(latest_per['PER']) > 0:
                result['pe'] = float(latest_per['PER'])
            if latest_per.get('PBR') and float(latest_per['PBR']) > 0:
                result['pb'] = float(latest_per['PBR'])
            if latest_per.get('dividend_yield') is not None:
                result['dividend_yield'] = float(latest_per['dividend_yield']) / 100.0
    except Exception:
        pass

    # 3. 平行抓取 MoneyDJ 與 Yahoo奇摩股市 公司業務、營收比重、細分產業與獲利指標
    ext = _fetch_extended_company_profile(code, ticker, chinese_name)
    result['main_business'] = ext.get('main_business') or []
    result['revenue_mix_raw'] = ext.get('revenue_mix_raw') or ''
    result['revenue_mix_items'] = ext.get('revenue_mix_items') or []
    result['recent_news'] = ext.get('recent_news') or []
    result['industry_avg_pe'] = ext.get('industry_avg_pe')
    result['net_worth_per_share'] = ext.get('net_worth_per_share')
    result['cash_dividend'] = ext.get('cash_dividend')
    result['capital_yi'] = ext.get('capital_yi')
    result['director_holding_pct'] = ext.get('director_holding_pct')
    result['debt_ratio_pct'] = ext.get('debt_ratio_pct')

    if result['pe'] is None and ext.get('pe'):
        result['pe'] = ext['pe']
    if result['pb'] is None and ext.get('pb'):
        result['pb'] = ext['pb']
    if result['dividend_yield'] is None and ext.get('dividend_yield') is not None:
        result['dividend_yield'] = ext['dividend_yield']
    if ext.get('gross_margin_pct') is not None:
        result['gross_margin'] = ext['gross_margin_pct'] / 100.0
    if ext.get('operating_margin_pct') is not None:
        result['operating_margin'] = ext['operating_margin_pct'] / 100.0
    if ext.get('pretax_margin_pct') is not None:
        result['profit_margin'] = ext['pretax_margin_pct'] / 100.0
    if ext.get('roe_pct') is not None:
        result['roe'] = ext['roe_pct'] / 100.0
    if ext.get('roa_pct') is not None:
        result['roa'] = ext['roa_pct'] / 100.0
    if ext.get('market_cap'):
        result['market_cap'] = ext['market_cap']

    # 自動推論相關細分產業與應用標籤
    rel_inds = _infer_related_industries(
        result['main_business'],
        result['revenue_mix_raw'],
        ext.get('moneydj_industries', []),
        industries
    )
    result['related_industries'] = rel_inds
    if sector_zh in ('其他', '台股', '台股產業') and rel_inds:
        result['sector'] = f"{sector_zh}（{' / '.join(rel_inds[:2])}）"

    # 4. 從 yfinance 補充 52週高低點、市值與缺漏比率
    try:
        tk = yf.Ticker(ticker)
        info = tk.info or {}

        result['english_name'] = info.get('shortName', '')
        if result['pe'] is None and info.get('trailingPE'):
            result['pe'] = float(info['trailingPE'])
        if result['pb'] is None and info.get('priceToBook'):
            result['pb'] = float(info['priceToBook'])
        if result['dividend_yield'] is None and info.get('dividendYield'):
            dy = float(info['dividendYield'])
            result['dividend_yield'] = dy / 100.0 if dy > 1 else dy

        if not result['market_cap'] and info.get('marketCap'):
            result['market_cap'] = info.get('marketCap')
        result['52w_high'] = info.get('fiftyTwoWeekHigh')
        result['52w_low'] = info.get('fiftyTwoWeekLow')
        if result['roe'] is None and info.get('returnOnEquity') is not None:
            result['roe'] = info.get('returnOnEquity')
        if result['gross_margin'] is None and info.get('grossMargins') is not None:
            result['gross_margin'] = info.get('grossMargins')
        if result['operating_margin'] is None and info.get('operatingMargins') is not None:
            result['operating_margin'] = info.get('operatingMargins')
        if result['profit_margin'] is None and info.get('profitMargins') is not None:
            result['profit_margin'] = info.get('profitMargins')
        result['revenue_growth'] = info.get('revenueGrowth')
        result['earnings_growth'] = info.get('earningsGrowth')
    except Exception as e:
        print(f"yfinance info warning for {code}: {e}")

    _set_cache(cache_key, result)
    return result


def build_business_and_profit_analysis(
    info: dict,
    financials: dict = None,
    report_cmt: dict = None,
    concept_details: list = None
) -> dict:
    """
    針對任何一檔台股，自動彙整出白話易懂的：
    1. 公司是做什麼的？（核心業務與白話一句話總結）
    2. 相關產業與應用領域是什麼？
    3. 靠什麼產品賺錢？（營收比重結構）
    4. 為什麼會賺錢？近期獲利與股價動能來源（結合產品組合、獲利三率、月營收YoY、季EPS、自結獲利公告）
    """
    code = info.get('code', '')
    name = info.get('name', code)
    main_biz = info.get('main_business') or []
    rev_mix_raw = info.get('revenue_mix_raw') or ''
    rev_mix_items = info.get('revenue_mix_items') or []
    rel_inds = list(info.get('related_industries') or [])
    recent_news = info.get('recent_news') or []

    # 整合概念股供應鏈角色
    concept_roles = []
    if concept_details:
        for cd in concept_details:
            cname = cd.get('concept_name', '')
            crole = cd.get('role', '')
            if cname and cname not in rel_inds:
                rel_inds.append(cname)
            if crole:
                concept_roles.append(f"【{cname}】{crole}")

    # 1. 白話一句話看懂公司做什麼
    biz_desc = "、".join(main_biz) if main_biz else ""
    top_products = "、".join([f"{it['name']}({it['pct']:.1f}%)" for it in rev_mix_items[:3] if it['name'] != '其他'])
    ind_desc = "、".join(rel_inds[:4]) if rel_inds else info.get('sector', '台股產業')

    if biz_desc and top_products:
        one_liner = (
            f"<b>{name} ({code})</b> 主要從事<b>「{biz_desc}」</b>，"
            f"主力營收來源為<b>{top_products}</b>，切入<b>{ind_desc}</b>等關鍵應用領域。"
        )
    elif biz_desc:
        one_liner = f"<b>{name} ({code})</b> 主要從事<b>「{biz_desc}」</b>，屬於<b>{ind_desc}</b>相關供應鏈。"
    elif top_products:
        one_liner = f"<b>{name} ({code})</b> 主力產品與服務為<b>{top_products}</b>，深耕<b>{ind_desc}</b>領域。"
    else:
        one_liner = f"<b>{name} ({code})</b> 為台灣<b>{info.get('market', '')} — {ind_desc}</b>代表性廠商。"

    # 2. 為什麼會賺錢？（自動生成 4~5 點具體數據支撐的白話解析）
    why_profit = []

    # (A) 主力產品與高毛利營收結構
    if rev_mix_items:
        non_other = [it for it in rev_mix_items if it['name'] != '其他']
        if len(non_other) >= 2:
            top2_pct = non_other[0]['pct'] + non_other[1]['pct']
            why_profit.append(
                f"<b>主力產品獲利結構清晰：</b>公司前兩大核心業務為「<b>{non_other[0]['name']} ({non_other[0]['pct']:.2f}%)</b>」與"
                f"「<b>{non_other[1]['name']} ({non_other[1]['pct']:.2f}%)</b>」，合計佔總營收達 <b>{top2_pct:.1f}%</b>；"
                + (f"受惠於<b>{'、'.join(rel_inds[:2])}</b>需求帶動，高附加價值產品拉升整體獲利表現。" if rel_inds else "核心產品訂單穩定貢獻現金流。")
            )
        elif len(non_other) == 1:
            why_profit.append(
                f"<b>核心業務高度集中：</b>主力營收來自「<b>{non_other[0]['name']} ({non_other[0]['pct']:.2f}%)</b>」，"
                f"專注於<b>{'、'.join(rel_inds[:2]) if rel_inds else ind_desc}</b>市場。"
            )
    elif main_biz:
        why_profit.append(
            f"<b>核心業務定位明確：</b>專注於「<b>{'、'.join(main_biz)}</b>」，受惠於<b>{ind_desc}</b>產業需求。"
        )

    # (B) 本業賺錢效率（毛利率 / 營業利益率 / 淨利率 / ROE）
    gm = info.get('gross_margin')
    om = info.get('operating_margin')
    pm = info.get('profit_margin')
    roe = info.get('roe')
    q_eps_list = (financials or {}).get('quarterly_eps', [])
    if q_eps_list:
        latest_q = q_eps_list[-1]
        q_gm = latest_q.get('毛利率(%)')
        q_om = latest_q.get('營益率(%)')
        q_nm = latest_q.get('淨利率(%)')
        if gm is None and q_gm:
            gm = q_gm / 100.0
        if om is None and q_om:
            om = q_om / 100.0
        if pm is None and q_nm:
            pm = q_nm / 100.0

    if gm is not None and om is not None:
        gm_p = gm * 100
        om_p = om * 100
        pm_p = (pm * 100) if pm is not None else om_p
        margin_comment = "屬於高毛利、強定價權體質" if gm_p >= 35 else ("產品毛利與本業控管穩健" if gm_p >= 20 else "屬規模經濟與製造加工型態")
        # 檢查三率是否較前幾季提升
        trend_note = ""
        if len(q_eps_list) >= 2:
            prev_q = q_eps_list[-2]
            if latest_q.get('營益率(%)', 0) > prev_q.get('營益率(%)', 0) + 1.5:
                trend_note = f"（且營業利益率由上季 {prev_q['營益率(%)']:.2f}% 躍升至 {latest_q['營益率(%)']:.2f}%，代表高毛利產品比重提高、規模經濟顯現！）"
        why_profit.append(
            f"<b>本業賺錢效率（獲利三率）：</b>最新營業毛利率達 <b>{gm_p:.2f}%</b>、營業利益率 <b>{om_p:.2f}%</b>、淨利率 <b>{pm_p:.2f}%</b>"
            f"——白話來說，公司每做 100 元生意，扣除直接生產成本後毛利賺 <b>{gm_p:.1f} 元</b>，再扣除管銷研發費用後本業實賺 <b>{om_p:.1f} 元</b>，{margin_comment}{trend_note}"
        )

    # (C) 近期月營收爆發動能 (YoY / MoM)
    m_rev_list = (financials or {}).get('monthly_revenue', [])
    if m_rev_list:
        lm = m_rev_list[-1]
        m_name = lm.get('Month', '')
        m_val = lm.get('Revenue', 0)
        yoy = lm.get('YoY', 0)
        mom = lm.get('MoM', 0)
        if yoy >= 30:
            why_profit.append(
                f"<b>近期營收爆發成長：</b>最新（{m_name}）單月合併營收達 <b>{m_val:,.3f} 億元</b>，"
                f"<b>較去年同期大幅成長 (YoY) +{yoy:.2f}%、月增 (MoM) {mom:+.2f}%</b>，顯示下游客戶拉貨或工程訂單認列進入高速成長期！"
            )
        elif yoy > 0:
            why_profit.append(
                f"<b>近期營收穩步成長：</b>最新（{m_name}）單月合併營收為 <b>{m_val:,.3f} 億元</b>，"
                f"<b>年增率 (YoY) +{yoy:.2f}%、月增率 (MoM) {mom:+.2f}%</b>，維持正向營收成長動能。"
            )
        else:
            why_profit.append(
                f"<b>近期營收表現：</b>最新（{m_name}）單月合併營收為 <b>{m_val:,.3f} 億元</b>（年增率 {yoy:+.2f}%、月增率 {mom:+.2f}%），"
                f"需持續追蹤後續訂單回溫狀況。"
            )

    # (D) 季度 EPS 與最新自結獲利催化劑
    self_profit_news = [n for n in recent_news if ('自結' in n or '獲利' in n or '每股' in n or 'EPS' in n)]
    if q_eps_list or self_profit_news:
        eps_parts = []
        if q_eps_list:
            lq = q_eps_list[-1]
            eps_parts.append(f"最新財報（{lq['Quarter']}）單季 EPS 達 <b>{lq['EPS']:.2f} 元</b>")
            if len(q_eps_list) >= 2 and lq['EPS'] > q_eps_list[-2]['EPS'] and q_eps_list[-2]['EPS'] > 0:
                qoq_growth = (lq['EPS'] - q_eps_list[-2]['EPS']) / abs(q_eps_list[-2]['EPS']) * 100
                eps_parts.append(f"較前一季（{q_eps_list[-2]['Quarter']} 的 {q_eps_list[-2]['EPS']:.2f} 元）季增 <b>+{qoq_growth:.1f}%</b>")
        if self_profit_news:
            eps_parts.append(f"最新重大催化劑：<b>「{self_profit_news[0]}」</b>，單月獲利能力顯著跳升")
        if eps_parts:
            why_profit.append("<b>實質獲利與 EPS 成長催化劑：</b>" + "；".join(eps_parts) + "。")

    # (E) 大股東籌碼與同業估值比較
    dh = info.get('director_holding_pct')
    pe = info.get('pe')
    ind_pe = info.get('industry_avg_pe')
    extra_parts = []
    if dh and dh >= 25:
        extra_parts.append(f"董監事持股比例高達 <b>{dh:.2f}%</b>（大股東與經營團隊股權高度集中，與股東利益一致、在外流通籌碼穩定）")
    elif dh:
        extra_parts.append(f"董監事持股比例為 <b>{dh:.2f}%</b>")
    if pe and ind_pe:
        if pe > ind_pe * 1.15:
            extra_parts.append(f"目前本益比 <b>{pe:.1f} 倍</b>（同業平均 <b>{ind_pe:.1f} 倍</b>），市場因近期營收與獲利高成長而給予高成長溢價")
        elif pe < ind_pe * 0.9:
            extra_parts.append(f"目前本益比 <b>{pe:.1f} 倍</b>，低於同業平均（<b>{ind_pe:.1f} 倍</b>），具備估值優勢")
        else:
            extra_parts.append(f"目前本益比 <b>{pe:.1f} 倍</b>，與同業平均（<b>{ind_pe:.1f} 倍</b>）相當")
    if extra_parts:
        why_profit.append("<b>股權結構與同業估值定位：</b>" + "；".join(extra_parts) + "。")

    return {
        'one_liner': one_liner,
        'main_business': main_biz,
        'concept_roles': concept_roles,
        'related_industries': rel_inds,
        'revenue_mix_raw': rev_mix_raw,
        'revenue_mix_items': rev_mix_items,
        'why_profitable': why_profit,
        'recent_news': recent_news,
    }



def get_price_history(code: str, period: str = '1y', interval: str = '1d') -> pd.DataFrame:
    """取得歷史 K 線 OHLCV DataFrame（含自動修復 yfinance 缺漏或 NaN 當日 K 棒之雙保險機制）"""
    ticker = normalize_ticker(code)
    df = None
    try:
        tk = yf.Ticker(ticker)
        df = tk.history(period=period, interval=interval)
    except Exception as e:
        print(f"Error fetching price history for {code}: {e}")

    # 雙保險機制：若 yfinance 抓到的資料有 NaN（常見於當日剛收盤未結算完畢），或延遲尚未抓到最新交易日，自動由 FinMind 補齊正確價格
    if df is not None and not df.empty:
        try:
            start_d = (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d')
            r = requests.get(
                FINMIND_URL,
                params={'dataset': 'TaiwanStockPrice', 'data_id': str(code).strip(), 'start_date': start_d},
                timeout=6
            )
            f_rows = r.json().get('data', [])
            if f_rows:
                f_map = {r['date']: r for r in f_rows}
                nan_mask = df[['Open', 'High', 'Low', 'Close']].isna().any(axis=1)
                if nan_mask.any():
                    for dt, row in df[nan_mask].iterrows():
                        d_str = dt.strftime('%Y-%m-%d')
                        if d_str in f_map:
                            f = f_map[d_str]
                            df.loc[dt, 'Open'] = float(f['open'])
                            df.loc[dt, 'High'] = float(f['max'])
                            df.loc[dt, 'Low'] = float(f['min'])
                            df.loc[dt, 'Close'] = float(f['close'])
                            if float(f.get('Trading_Volume', 0)) > 0:
                                df.loc[dt, 'Volume'] = float(f['Trading_Volume'])

                # 若 FinMind 有比 yfinance 更即時的最新交易日資料，自動追加
                latest_f = f_rows[-1]
                latest_f_date = str(latest_f.get('date', ''))
                max_df_date = df.index.max().strftime('%Y-%m-%d')
                if latest_f_date > max_df_date and float(latest_f.get('close', 0)) > 0:
                    tz_info = getattr(df.index, 'tz', None)
                    new_idx = pd.to_datetime(latest_f_date).tz_localize(tz_info) if tz_info is not None else pd.to_datetime(latest_f_date)
                    new_row = pd.DataFrame([{
                        'Open': float(latest_f['open']),
                        'High': float(latest_f['max']),
                        'Low': float(latest_f['min']),
                        'Close': float(latest_f['close']),
                        'Volume': float(latest_f.get('Trading_Volume', 0))
                    }], index=[new_idx])
                    df = pd.concat([df, new_row])
        except Exception as e:
            print(f"FinMind patch error for {code}: {e}")

        # 徹底清除仍為空值或無效價值的列，確保量價絕對齊全
        df = df.dropna(subset=['Open', 'High', 'Low', 'Close'])
        df = df[df['Close'] > 0]
        if not df.empty:
            return df

    # 備用：若 yfinance 完全無資料，直接從 FinMind 抓歷史日 K
    try:
        start_d = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        r = requests.get(
            FINMIND_URL,
            params={'dataset': 'TaiwanStockPrice', 'data_id': str(code).strip(), 'start_date': start_d},
            timeout=10
        )
        rows = r.json().get('data', [])
        if rows:
            df = pd.DataFrame(rows)
            df['Date'] = pd.to_datetime(df['date'])
            df.set_index('Date', inplace=True)
            df.rename(columns={
                'open': 'Open', 'max': 'High', 'min': 'Low',
                'close': 'Close', 'Trading_Volume': 'Volume'
            }, inplace=True)
            df = df.dropna(subset=['Open', 'High', 'Low', 'Close'])
            df = df[df['Close'] > 0]
            return df[['Open', 'High', 'Low', 'Close', 'Volume']]
    except Exception:
        pass

    return pd.DataFrame()


def get_financials(code: str) -> dict:
    """
    從 FinMind 取得台股季度財報（EPS、毛利率、營益率、淨利率）與月營收（含年增率 YoY、月增率 MoM）
    """
    code = str(code).strip()
    cache_key = f"financials_v2_{code}"
    cached = _get_cache(cache_key)
    if cached:
        return cached

    result = {
        'quarterly_eps': [],      # [{'Quarter': '2025Q1', 'EPS': 1.5, '毛利率': 35.2, '營益率': 18.1, '淨利率': 15.0, '營收(億)': 12.3}]
        'monthly_revenue': [],    # [{'Month': '2026/08', 'Revenue': 0.48, 'YoY': 153.2, 'MoM': 12.1}]
    }

    # 1. 取得季度損益表 (TaiwanStockFinancialStatements)
    try:
        start_q = (datetime.now() - timedelta(days=900)).strftime('%Y-%m-%d')
        r = requests.get(
            FINMIND_URL,
            params={'dataset': 'TaiwanStockFinancialStatements', 'data_id': code, 'start_date': start_q},
            timeout=10
        )
        rows = r.json().get('data', [])
        if rows:
            by_date = {}
            for row in rows:
                d = row.get('date', '')
                t = row.get('type', '')
                v = float(row.get('value', 0) or 0)
                if d not in by_date:
                    by_date[d] = {}
                by_date[d][t] = v

            q_list = []
            for d in sorted(by_date.keys()):
                metrics = by_date[d]
                # 轉換日期為季度標籤，例如 2026-06-30 -> 26Q2
                dt = datetime.strptime(d, '%Y-%m-%d')
                q_num = (dt.month - 1) // 3 + 1
                q_label = f"{str(dt.year)[2:]}Q{q_num}"

                rev = metrics.get('Revenue', 0)
                gp = metrics.get('GrossProfit', 0)
                op = metrics.get('OperatingIncome', 0)
                ni = metrics.get('IncomeAfterTaxes', metrics.get('IncomeFromContinuingOperations', 0))
                eps = metrics.get('EPS', 0)

                gm = round(gp / rev * 100, 2) if rev > 0 else 0.0
                om = round(op / rev * 100, 2) if rev > 0 else 0.0
                nm = round(ni / rev * 100, 2) if rev > 0 else 0.0

                q_list.append({
                    'Quarter': q_label,
                    'Date': d,
                    'EPS': round(eps, 2),
                    '營收(億)': round(rev / 1e8, 2),
                    '毛利率(%)': gm,
                    '營益率(%)': om,
                    '淨利率(%)': nm
                })
            result['quarterly_eps'] = q_list[-8:]  # 最近 8 季
    except Exception as e:
        print(f"FinMind quarterly financials error for {code}: {e}")

    # 2. 取得月營收 (TaiwanStockMonthRevenue)
    try:
        start_m = (datetime.now() - timedelta(days=800)).strftime('%Y-%m-%d')
        r = requests.get(
            FINMIND_URL,
            params={'dataset': 'TaiwanStockMonthRevenue', 'data_id': code, 'start_date': start_m},
            timeout=10
        )
        rows = r.json().get('data', [])
        if rows:
            # 建立 (year, month) -> revenue 索引以計算 YoY 與 MoM
            rev_map = {}
            for row in rows:
                y = int(row.get('revenue_year', 0))
                m = int(row.get('revenue_month', 0))
                rev = float(row.get('revenue', 0) or 0)
                if y and m:
                    rev_map[(y, m)] = rev

            m_list = []
            sorted_keys = sorted(rev_map.keys())
            for (y, m) in sorted_keys:
                curr_rev = rev_map[(y, m)]
                prev_y_rev = rev_map.get((y - 1, m), 0)
                prev_m_key = (y, m - 1) if m > 1 else (y - 1, 12)
                prev_m_rev = rev_map.get(prev_m_key, 0)

                yoy = round((curr_rev - prev_y_rev) / prev_y_rev * 100, 2) if prev_y_rev > 0 else 0.0
                mom = round((curr_rev - prev_m_rev) / prev_m_rev * 100, 2) if prev_m_rev > 0 else 0.0

                m_list.append({
                    'Month': f"{y}/{m:02d}",
                    'Revenue': round(curr_rev / 1e8, 3),  # 單位：億元
                    '營收(千元)': round(curr_rev / 1e3, 0),
                    'YoY': yoy,
                    'MoM': mom
                })
            result['monthly_revenue'] = m_list[-12:]  # 最近 12 個月
    except Exception as e:
        print(f"FinMind monthly revenue error for {code}: {e}")

    _set_cache(cache_key, result)
    return result


def get_daily_report_commentary_for_stock(code: str) -> dict:
    """
    若今日或近期盤後報告中有收錄此股票（如 5484 慧友），直接擷取報告中的 AI 評析與新聞亮點！
    """
    code = str(code).strip()
    if not os.path.exists(CACHE_DIR):
        return {}

    report_files = sorted(
        [f for f in os.listdir(CACHE_DIR) if f.startswith('report_') and f.endswith('.json')],
        reverse=True
    )
    for rf in report_files[:3]:
        try:
            with open(os.path.join(CACHE_DIR, rf), 'r', encoding='utf-8') as f:
                rdata = json.load(f)
            html = rdata.get('html', '')
            if f">{code} " in html:
                # 擷取該個股區塊文字
                pos = html.find(f">{code} ")
                block = html[max(0, pos - 100):pos + 1800]
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(block, 'html.parser')
                texts = [t.strip() for t in soup.stripped_strings if t.strip()]
                return {
                    'report_date': rdata.get('date', ''),
                    'lines': texts[:12]
                }
        except Exception:
            continue
    return {}


def get_twse_institutional_summary():
    """取得證交所三大法人買賣超彙總"""
    cache_key = "twse_institutional_summary"
    cached = _get_cache(cache_key)
    if cached:
        return cached

    url = "https://www.twse.com.tw/rwd/zh/fund/T86?response=json&selectType=ALL"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        _set_cache(cache_key, data)
        return data
    except Exception:
        return {}


def get_batch_quotes_with_intraday(codes: list) -> dict:
    """
    批次取得多檔台股的最新報價、日K四價（開高低收）、昨收平盤價與當日 5 分 K 走勢序列
    用於繪製仿看盤 App 的「紅綠K棒 + 報價漲跌 + 平盤雙色走勢圖」列表
    """
    clean_codes = []
    for c in codes:
        sc = str(c).strip()
        if sc and sc not in clean_codes:
            clean_codes.append(sc)
    if not clean_codes:
        return {}

    import hashlib
    key_hash = hashlib.md5(",".join(sorted(clean_codes)).encode('utf-8')).hexdigest()[:12]
    cache_key = f"batch_intraday_{key_hash}"
    cached = _get_cache(cache_key)
    if cached:
        return cached

    ticker_map = {c: normalize_ticker(c) for c in clean_codes}
    tickers = list(ticker_map.values())

    result = {}
    try:
        # 1. 批次下載近 10 日日線（取得精確昨收、今日開高低收）
        df_daily = yf.download(tickers, period='10d', interval='1d', group_by='ticker', progress=False, threads=True)
        # 2. 批次下載近 5 日 5 分 K（取得當日盤中走勢圖點位）
        df_5m = yf.download(tickers, period='5d', interval='5m', group_by='ticker', progress=False, threads=True)
    except Exception:
        df_daily = pd.DataFrame()
        df_5m = pd.DataFrame()

    single_mode = (len(tickers) == 1)

    for c in clean_codes:
        tk = ticker_map[c]
        cinfo = get_tw_stock_chinese_info(c)
        market_raw = cinfo.get('market', '上市')
        market_short = '櫃' if '櫃' in market_raw else '市'
        info_item = {
            'code': c,
            'name': cinfo.get('name', c),
            'market_short': market_short,
            'open': 0.0,
            'high': 0.0,
            'low': 0.0,
            'close': 0.0,
            'prev_close': 0.0,
            'change': 0.0,
            'pct_change': 0.0,
            'sparkline': []
        }

        try:
            sub_d = df_daily if single_mode else df_daily[tk]
            sub_d = sub_d.dropna(how='all')
            if not sub_d.empty:
                last_row = sub_d.iloc[-1]
                close_v = float(last_row['Close'])
                open_v = float(last_row['Open']) if pd.notna(last_row['Open']) else close_v
                high_v = float(last_row['High']) if pd.notna(last_row['High']) else max(open_v, close_v)
                low_v = float(last_row['Low']) if pd.notna(last_row['Low']) else min(open_v, close_v)
                prev_v = float(sub_d['Close'].iloc[-2]) if len(sub_d) > 1 else open_v
                chg_v = close_v - prev_v
                pct_v = (chg_v / prev_v * 100.0) if prev_v else 0.0

                info_item.update({
                    'open': round(open_v, 2),
                    'high': round(high_v, 2),
                    'low': round(low_v, 2),
                    'close': round(close_v, 2),
                    'prev_close': round(prev_v, 2),
                    'change': round(chg_v, 2),
                    'pct_change': round(pct_v, 2),
                })

                # 先以近 10 日收盤價作為預設走勢備援
                info_item['sparkline'] = [round(float(x), 2) for x in sub_d['Close'].dropna().tolist()]
        except Exception:
            pass

        try:
            sub_m = df_5m if single_mode else df_5m[tk]
            sub_m = sub_m.dropna(how='all')
            if not sub_m.empty:
                last_date = sub_m.index[-1].date()
                day_m = sub_m[sub_m.index.date == last_date]
                closes_m = [round(float(x), 2) for x in day_m['Close'].dropna().tolist()]
                if len(closes_m) >= 5:
                    info_item['sparkline'] = closes_m
        except Exception:
            pass

        result[c] = info_item

    _set_cache(cache_key, result)
    return result

