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


def get_stock_info(code: str) -> dict:
    """
    取得台股完整基本面資訊（全中文名稱、上市櫃別、中文產業別、PE、PB、殖利率、市值、ROE等）
    """
    code = str(code).strip()
    cache_key = f"stock_info_v2_{code}"
    cached = _get_cache(cache_key)
    if cached:
        return cached

    # 1. 先從本地台股字典取得正確中文名稱與產業
    tw_info = get_tw_stock_chinese_info(code)
    chinese_name = tw_info.get('name', code)
    market_label = tw_info.get('market', '上市')
    industries = tw_info.get('industries', ['台股'])
    sector_zh = ' / '.join(industries) if industries else '台股產業'

    result = {
        'code': code,
        'name': chinese_name,
        'english_name': '',
        'market': market_label,
        'sector': sector_zh,
        'industries': industries,
        'pe': None,
        'pb': None,
        'dividend_yield': None,  # 以小數儲存，例如 0.045 代表 4.5%
        'market_cap': None,
        '52w_high': None,
        '52w_low': None,
        'roe': None,
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
            timeout=8
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

    # 3. 從 yfinance 補充市值、52週高低點、ROE 與財務比率
    try:
        ticker = normalize_ticker(code)
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

        result['market_cap'] = info.get('marketCap')
        result['52w_high'] = info.get('fiftyTwoWeekHigh')
        result['52w_low'] = info.get('fiftyTwoWeekLow')
        result['roe'] = info.get('returnOnEquity')
        result['gross_margin'] = info.get('grossMargins')
        result['operating_margin'] = info.get('operatingMargins')
        result['profit_margin'] = info.get('profitMargins')
        result['revenue_growth'] = info.get('revenueGrowth')
        result['earnings_growth'] = info.get('earningsGrowth')
    except Exception as e:
        print(f"yfinance info warning for {code}: {e}")

    _set_cache(cache_key, result)
    return result


def get_price_history(code: str, period: str = '1y', interval: str = '1d') -> pd.DataFrame:
    """取得歷史 K 線 OHLCV DataFrame"""
    ticker = normalize_ticker(code)
    try:
        tk = yf.Ticker(ticker)
        df = tk.history(period=period, interval=interval)
        if df is not None and not df.empty:
            return df
    except Exception as e:
        print(f"Error fetching price history for {code}: {e}")

    # 備用：若 yfinance 失敗，從 FinMind 抓日 K
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

