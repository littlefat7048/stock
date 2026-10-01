"""
台股強勢股雷達與多頭特徵篩選模組
包含：
1. 今日爆量長紅（成交量 > 5日均量 1.8~3.0倍 且股價收紅）
2. 多頭連攻（連續 2~5 日收紅盤，沿均線上攻）
3. 創 20 日波段新高（突破整理平台）
4. 王者共振股（暴量 ＋ 連漲 ＋ 突破三合一）
5. 概念族群資金輪動統計（族群平均漲幅與領頭羊排行）
"""
import os
import json
import time
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from utils.helpers import get_tw_stock_chinese_info, load_concept_data, load_watchlist

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)
SCREENER_CACHE_FILE = os.path.join(CACHE_DIR, 'screener_results_v1.json')
SCREENER_EXPIRY_SECONDS = 3600  # 1 小時快取


def get_screener_universe() -> list:
    """
    整合台股最具流動性與市場焦點的股票池（約 250~350 檔）：
    - 每日盤後報告收錄的個股
    - 核心概念股資料庫收錄之題材股
    - 使用者個人自選股
    """
    codes = set()

    # 1. 概念股清單
    cdata = load_concept_data()
    for _, sub_cats in cdata.get('概念分類', {}).items():
        if isinstance(sub_cats, dict):
            for _, cinfo in sub_cats.items():
                if isinstance(cinfo, dict):
                    for s in cinfo.get('stocks', []):
                        code = s.get('code') if isinstance(s, dict) else str(s)
                        if code and len(str(code).strip()) == 4:
                            codes.add(str(code).strip())

    # 2. 每日盤後報告收錄之個股 (最近 3 期報告)
    report_files = sorted(
        [f for f in os.listdir(CACHE_DIR) if f.startswith('report_') and f.endswith('.json')],
        reverse=True
    )
    for rf in report_files[:3]:
        try:
            with open(os.path.join(CACHE_DIR, rf), 'r', encoding='utf-8') as f:
                rdata = json.load(f)
            for s in rdata.get('stocks', []):
                c = s.get('code', '').strip()
                if c and len(c) == 4:
                    codes.add(c)
        except Exception:
            continue

    # 3. 使用者自選股
    for item in load_watchlist():
        c = item.get('code', '').strip() if isinstance(item, dict) else str(item).strip()
        if c and len(c) == 4:
            codes.add(c)

    return sorted(list(codes))


def scan_market_signals(force_refresh: bool = False) -> dict:
    """
    批次掃描股票池的多頭攻擊特徵，回傳結構化雷達清單與統計數據。
    支援 1 小時本地快取，避免重複請求 yfinance。
    """
    if not force_refresh and os.path.exists(SCREENER_CACHE_FILE):
        try:
            mtime = os.path.getmtime(SCREENER_CACHE_FILE)
            if time.time() - mtime < SCREENER_EXPIRY_SECONDS:
                with open(SCREENER_CACHE_FILE, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    if cached_data and cached_data.get('total_scanned', 0) > 0:
                        return cached_data
        except Exception:
            pass

    universe = get_screener_universe()
    if not universe:
        return {'total_scanned': 0, 'items': {}, 'volume_surge': [], 'consecutive_up': [], 'breakout': [], 'all_star': []}

    # 建立 ticker 映射
    ticker_map = {}
    for c in universe:
        cinfo = get_tw_stock_chinese_info(c)
        mtype = cinfo.get('type', 'twse')
        suffix = '.TWO' if mtype == 'tpex' else '.TW'
        ticker_map[c] = f"{c}{suffix}"

    tickers = list(ticker_map.values())

    try:
        # 下載近 25 日日線資料以精確計算均量、連漲天數與 20 日高點
        df_all = yf.download(tickers, period='25d', interval='1d', group_by='ticker', progress=False, threads=True)
    except Exception as e:
        print(f"Screener yf.download error: {e}")
        df_all = pd.DataFrame()

    cdata = load_concept_data()
    items = {}
    vol_surge_list = []
    consec_up_list = []
    breakout_list = []
    all_star_list = []

    single_mode = (len(tickers) == 1)

    for code in universe:
        tk = ticker_map[code]
        cinfo = get_tw_stock_chinese_info(code)
        market_raw = cinfo.get('market', '上市')
        market_short = '櫃' if '櫃' in market_raw else '市'

        try:
            sub_d = df_all if single_mode else df_all[tk]
            sub_d = sub_d.dropna(how='all')
            if len(sub_d) < 5:
                continue

            closes = sub_d['Close'].dropna().tolist()
            volumes = sub_d['Volume'].dropna().tolist()
            highs = sub_d['High'].dropna().tolist()
            opens = sub_d['Open'].dropna().tolist()
            lows = sub_d['Low'].dropna().tolist()

            if len(closes) < 5:
                continue

            latest_close = float(closes[-1])
            prev_close = float(closes[-2])
            change = round(latest_close - prev_close, 2)
            pct_change = round((change / prev_close) * 100.0, 2) if prev_close else 0.0

            # 成交量（轉為張數：除以 1000）
            latest_vol_lots = int(round(float(volumes[-1]) / 1000.0))
            prev_5d_vols = [float(v) / 1000.0 for v in volumes[-6:-1]] if len(volumes) >= 6 else [latest_vol_lots]
            vol_ma5 = round(sum(prev_5d_vols) / max(len(prev_5d_vols), 1), 1)
            vol_ratio = round(latest_vol_lots / vol_ma5, 2) if vol_ma5 > 0 else 1.0

            # 連續上漲天數計算 (從最後一天往前數收盤價 > 前一日收盤價)
            consec_up = 0
            for i in range(len(closes) - 1, 0, -1):
                if closes[i] > closes[i - 1]:
                    consec_up += 1
                else:
                    break

            # 創 20 日波段收盤新高
            lookback_20 = closes[-20:-1] if len(closes) >= 20 else closes[:-1]
            max_20d = max(lookback_20) if lookback_20 else latest_close
            is_breakout_20d = (latest_close >= max_20d) and (change > 0)

            # 均線判定 (MA5, MA10, MA20)
            ma5 = sum(closes[-5:]) / 5.0 if len(closes) >= 5 else latest_close
            ma10 = sum(closes[-10:]) / 10.0 if len(closes) >= 10 else latest_close
            ma20 = sum(closes[-20:]) / 20.0 if len(closes) >= 20 else latest_close
            is_ma_bull = (latest_close > ma5 > ma10 > ma20)

            # 所屬概念標籤
            tags = []
            for _, sub_cats in cdata.get('概念分類', {}).items():
                if isinstance(sub_cats, dict):
                    for cname, ci in sub_cats.items():
                        if isinstance(ci, dict):
                            for st_item in ci.get('stocks', []):
                                sc = st_item.get('code') if isinstance(st_item, dict) else str(st_item)
                                if str(sc).strip() == code and cname not in tags:
                                    tags.append(cname)

            role_tag = tags[0] if tags else cinfo.get('industry', '焦點股')

            sparkline = [round(float(x), 2) for x in closes[-10:]]

            entry = {
                'code': code,
                'name': cinfo.get('name', code),
                'market_short': market_short,
                'role': role_tag,
                'tags': tags,
                'open': round(float(opens[-1]), 2),
                'high': round(float(highs[-1]), 2),
                'low': round(float(lows[-1]), 2),
                'close': latest_close,
                'prev_close': prev_close,
                'change': change,
                'pct_change': pct_change,
                'volume_lots': latest_vol_lots,
                'vol_ma5': vol_ma5,
                'vol_ratio': vol_ratio,
                'consec_up': consec_up,
                'is_breakout_20d': is_breakout_20d,
                'is_ma_bull': is_ma_bull,
                'sparkline': sparkline
            }

            items[code] = entry

            # 1. 今日暴量攻擊股：成交量暴增 >= 1.8 倍 且 今日收紅 (漲幅 >= 1.5%) 且 成交量 >= 300 張
            if vol_ratio >= 1.8 and pct_change >= 1.5 and latest_vol_lots >= 300:
                vol_surge_list.append(entry)

            # 2. 多頭連攻股：連續上漲 >= 3 天 且 今日仍收紅
            if consec_up >= 3 and pct_change > 0:
                consec_up_list.append(entry)

            # 3. 創 20 日新高股：收盤創 20 日新高 且 漲幅 > 0 且 成交量 >= 300 張
            if is_breakout_20d and pct_change > 0 and latest_vol_lots >= 300:
                breakout_list.append(entry)

            # 4. 王者共振股：暴量 ＋ 連漲 >= 2天 或 創高突破
            if (vol_ratio >= 1.8 and pct_change >= 2.0 and latest_vol_lots >= 500) and (consec_up >= 2 or is_breakout_20d):
                all_star_list.append(entry)

        except Exception:
            continue

    # 排序邏輯
    vol_surge_list.sort(key=lambda x: (x['vol_ratio'], x['pct_change']), reverse=True)
    consec_up_list.sort(key=lambda x: (x['consec_up'], x['pct_change']), reverse=True)
    breakout_list.sort(key=lambda x: (x['pct_change'], x['vol_ratio']), reverse=True)
    all_star_list.sort(key=lambda x: (x['pct_change'], x['vol_ratio']), reverse=True)

    result = {
        'timestamp': datetime.now().isoformat(),
        'scan_date': datetime.now().strftime('%Y-%m-%d'),
        'total_scanned': len(items),
        'items': items,
        'volume_surge': vol_surge_list,
        'consecutive_up': consec_up_list,
        'breakout': breakout_list,
        'all_star': all_star_list
    }

    try:
        with open(SCREENER_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return result


def get_concept_rotation_rankings(screener_data: dict = None) -> list:
    """
    計算今日各概念族群的資金輪動強度與平均漲幅排行
    回傳：[{'concept': '光通訊CPO', 'avg_pct': 3.82, 'up_count': 8, 'total': 10, 'leader': {'code': '3081', 'name': '聯亞', 'pct': 6.2}}, ...]
    """
    if screener_data is None:
        screener_data = scan_market_signals()

    items = screener_data.get('items', {})
    if not items:
        return []

    cdata = load_concept_data()
    rankings = []

    for big_cat, sub_cats in cdata.get('概念分類', {}).items():
        if not isinstance(sub_cats, dict):
            continue
        for sub_name, cinfo in sub_cats.items():
            if not isinstance(cinfo, dict):
                continue
            stocks = cinfo.get('stocks', [])
            if not stocks or len(stocks) < 2:
                continue

            pcts = []
            leader_stock = None
            max_pct = -999.0
            up_count = 0

            for s in stocks:
                code = s.get('code') if isinstance(s, dict) else str(s)
                code = str(code).strip()
                if code in items:
                    info = items[code]
                    pct = float(info.get('pct_change', 0.0))
                    pcts.append(pct)
                    if pct > 0:
                        up_count += 1
                    if pct > max_pct:
                        max_pct = pct
                        leader_stock = {
                            'code': code,
                            'name': info.get('name', code),
                            'pct_change': pct
                        }

            if pcts:
                avg_pct = round(sum(pcts) / len(pcts), 2)
                rankings.append({
                    'big_category': big_cat,
                    'concept_name': sub_name,
                    'desc': cinfo.get('desc', ''),
                    'avg_pct_change': avg_pct,
                    'up_count': up_count,
                    'total_count': len(pcts),
                    'up_ratio': round(up_count / len(pcts) * 100.0, 1),
                    'leader': leader_stock
                })

    # 依平均漲幅由高到低排序
    rankings.sort(key=lambda x: x['avg_pct_change'], reverse=True)
    return rankings
