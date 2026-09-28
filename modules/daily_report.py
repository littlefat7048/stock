"""
每日盤後分析報告爬蟲模組
資料來源：https://7388chichi.pages.dev
包含：自動尋找最新完整報告、解析個股代號名稱、快取管理
"""
import os
import re
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
}

def get_today_date_str():
    """取得今天的日期字串 (YYYYMMDD)"""
    return datetime.now().strftime('%Y%m%d')

def _is_real_report(html: str) -> bool:
    """
    嚴格驗證抓到的是真實個股分析報告頁，而非首頁/目錄頁。
    真實報告大小通常 > 200KB，且含有個股分析特徵文字。
    """
    if not html or len(html) < 150000:
        return False
    # 首頁會有「閱讀完整報告」按鈕，真實報告頁沒有
    if '閱讀完整報告' in html and '專欄' in html and len(html) < 200000:
        return False
    # 真實報告的特徵
    return ('台股收盤分析' in html or '重點個股分析' in html or '本益比' in html)

def get_latest_report_info_from_home():
    """
    從 7388chichi 首頁解析最新報告的日期與網址
    回傳 (date_str, url) 或 (None, None)
    """
    try:
        r = requests.get('https://7388chichi.pages.dev/', headers=HEADERS, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # 尋找「閱讀完整報告」按鈕連結
            for a in soup.find_all('a'):
                if '閱讀完整報告' in a.get_text():
                    href = a.get('href', '').strip()
                    m = re.search(r'twse_(\d{8})', href)
                    if m:
                        date_str = m.group(1)
                        full_url = f"https://7388chichi.pages.dev/{href.lstrip('/')}"
                        return date_str, full_url

            # 若無按鈕文字，找所有 reports/twse_ 連結中日期最新者
            dates_links = []
            for a in soup.find_all('a'):
                href = a.get('href', '')
                m = re.search(r'reports/twse_(\d{8})', href)
                if m:
                    dates_links.append((m.group(1), href))
            if dates_links:
                dates_links.sort(key=lambda x: x[0], reverse=True)
                latest_date, href = dates_links[0]
                full_url = f"https://7388chichi.pages.dev/{href.lstrip('/')}"
                return latest_date, full_url
    except Exception as e:
        print(f"取得首頁最新報告連結失敗: {e}")
    return None, None

def scrape_report(date_str=None):
    """
    爬取報告網頁 HTML。
    若未指定日期或指定日期失敗，會自動從首頁偵測最新發布的完整報告。
    回傳字典：{html, date, status, stocks_found}
    """
    # 1. 優先嘗試指定的日期
    dates_to_try = []
    if date_str:
        dates_to_try.append(date_str)
    else:
        # 自動向首頁詢問最新日期
        latest_date, _ = get_latest_report_info_from_home()
        if latest_date:
            dates_to_try.append(latest_date)
        today = datetime.now()
        for i in range(7):
            d = today - timedelta(days=i)
            if d.weekday() < 5:
                ds = d.strftime('%Y%m%d')
                if ds not in dates_to_try:
                    dates_to_try.append(ds)

    for d_str in dates_to_try:
        # 報告網址可能帶 .html 或不帶，兩者皆試
        url_candidates = [
            f"https://7388chichi.pages.dev/reports/twse_{d_str}.html",
            f"https://7388chichi.pages.dev/reports/twse_{d_str}",
        ]
        for url in url_candidates:
            try:
                response = requests.get(url, headers=HEADERS, timeout=15)
                if response.status_code == 200:
                    html = response.text
                    if _is_real_report(html):
                        stocks = parse_stock_codes(html)
                        save_report_cache(d_str, html, stocks)
                        return {
                            'html': html,
                            'date': d_str,
                            'status': 'success',
                            'stocks_found': stocks
                        }
            except requests.RequestException:
                continue

    return {
        'html': '',
        'date': date_str or get_today_date_str(),
        'status': 'failed',
        'stocks_found': []
    }

def parse_stock_codes(html):
    """
    從 HTML 中精準解析出個股分析卡片的代號 (4碼) 和名稱。
    格式通常為：<span style="...font-size:15px...">6515 穎崴</span>
    """
    stocks = []
    seen = set()

    # 1. 優先從卡片標題精準擷取
    card_pattern = r'font-size:\s*15px[^>]*>(\d{4})\s*([^<]+)</span>'
    for code, raw_name in re.findall(card_pattern, html):
        name = raw_name.strip()
        if code not in seen and len(name) >= 2:
            stocks.append({'code': code, 'name': name})
            seen.add(code)

    # 2. 備用：若卡片正則沒抓到，使用中文括號格式「股名（代號）」
    if not stocks:
        bracket_pattern = r'([\u4e00-\u9fa5A-Za-z0-9\-]{2,8})[（\(](\d{4})[）\)]'
        for name, code in re.findall(bracket_pattern, html):
            if code not in seen:
                stocks.append({'code': code, 'name': name.strip()})
                seen.add(code)

    return stocks

def inject_links(html, app_base_url=""):
    """
    將 HTML 中的股票代號和名稱加上可點擊的連結或跳轉事件。
    """
    stocks = parse_stock_codes(html)
    for stock in stocks:
        code = stock['code']
        name = stock['name']
        # 替換 "代號 名稱"
        pattern = f"({code}\\s+{re.escape(name)})"
        replacement = (
            f'<a href="/?stock={code}" target="_top" '
            f'style="color:#00D4AA; font-weight:bold; text-decoration:underline;">\\1</a>'
        )
        html = re.sub(pattern, replacement, html)
    return html

def save_report_cache(date_str, html, stocks):
    """將報告存入快取"""
    cache_path = os.path.join(CACHE_DIR, f'report_{date_str}.json')
    data = {
        'date': date_str,
        'html': html,
        'stocks': stocks,
        'timestamp': datetime.now().isoformat()
    }
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_report_cache(date_str):
    """從快取載入報告，並確認內容是真實報告"""
    cache_path = os.path.join(CACHE_DIR, f'report_{date_str}.json')
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 驗證快取內容是否為真實報告
                if _is_real_report(data.get('html', '')):
                    return data
                else:
                    # 快取到首頁等無效內容，自動移除
                    os.remove(cache_path)
        except Exception:
            pass
    return None

def get_available_dates():
    """取得所有已快取真實報告的日期清單"""
    dates = []
    if os.path.exists(CACHE_DIR):
        for filename in os.listdir(CACHE_DIR):
            if filename.startswith('report_') and filename.endswith('.json'):
                date_str = filename.replace('report_', '').replace('.json', '')
                dates.append(date_str)
    return sorted(dates, reverse=True)
