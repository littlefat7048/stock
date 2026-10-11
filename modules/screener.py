"""
台股強勢股雷達與智慧策略推薦模組 (v2.0)
結合：
1. 籌碼面核心策略（投信作帳認養、外資大戶鎖碼、土洋同步合買、三大法人佔比）
2. 技術面核心策略（今日爆量長紅、創 20 日波段新高突破、多頭連攻、均線多頭排列起漲）
3. 熱門概念族群輪動領頭羊（大數據統計各族群平均漲幅與指標龍頭股）
4. 隔日沖主力快篩與避坑提醒（標記知名隔日沖大戶鎖碼風險，防隔日開高走低出貨）
5. 全市場綜合量化推薦榜（綜合評分 0~100 分，提供 ⭐⭐⭐⭐⭐ 推薦星級與操盤指南）
"""
import os
import json
import time
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from utils.helpers import get_tw_stock_chinese_info, load_concept_data, load_watchlist

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)
SCREENER_CACHE_FILE = os.path.join(CACHE_DIR, 'screener_results_v2.json')
MARKET_INST_CACHE_FILE = os.path.join(CACHE_DIR, 'market_inst_today.json')
MARKET_VALUATION_CACHE_FILE = os.path.join(CACHE_DIR, 'market_valuation_today.json')
SCREENER_EXPIRY_SECONDS = 3600  # 1 小時快取


def _parse_num(v) -> float:
    if v is None:
        return 0.0
    s = str(v).replace(',', '').strip()
    if s in ('-', 'N/A', '', 'None'):
        return 0.0
    try:
        return float(s)
    except Exception:
        return 0.0


def get_market_daily_institution_data(force_refresh: bool = False) -> dict:
    """
    抓取全台股（上市 TWSE ＋ 上櫃 TPEx）當日三大法人買賣超數據字典
    回傳：{
        '2330': {'foreign': 9770.5, 'trust': 589.1, 'dealer': 491.7, 'total': 10851.3},
        ...
    }
    單位：張。快取 1 小時，0 API 消耗，全自動官方公開數據。
    """
    if not force_refresh and os.path.exists(MARKET_INST_CACHE_FILE):
        try:
            mtime = os.path.getmtime(MARKET_INST_CACHE_FILE)
            if time.time() - mtime < SCREENER_EXPIRY_SECONDS:
                with open(MARKET_INST_CACHE_FILE, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                    if cached and len(cached) > 500:
                        return cached
        except Exception:
            pass

    inst_map = {}

    # 1. 證交所 (TWSE) 上市三大法人
    try:
        url_tw = "https://www.twse.com.tw/rwd/zh/fund/T86?response=json&selectType=ALL"
        r_tw = requests.get(url_tw, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        tw_data = r_tw.json().get('data', [])
        for row in tw_data:
            code = str(row[0]).strip()
            if len(code) == 4 and code.isdigit():
                # row[4]: 外陸資買賣超(不含外資自營), row[10]: 投信, row[11]: 自營商合計, row[18]: 三大法人
                foreign = round(_parse_num(row[4]) / 1000.0, 1)
                trust = round(_parse_num(row[10]) / 1000.0, 1)
                dealer = round(_parse_num(row[11]) / 1000.0, 1)
                total = round(_parse_num(row[18]) / 1000.0, 1)
                inst_map[code] = {
                    'foreign': foreign,
                    'trust': trust,
                    'dealer': dealer,
                    'total': total
                }
    except Exception as e:
        print(f"Screener TWSE institutional fetch error: {e}")

    # 2. 櫃買中心 (TPEx) 上櫃三大法人
    try:
        url_otc = "https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php?l=zh-tw&o=json"
        r_otc = requests.get(url_otc, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        tables = r_otc.json().get('tables', [])
        if tables and tables[0].get('data'):
            for row in tables[0]['data']:
                code = str(row[0]).strip()
                if len(code) == 4 and code.isdigit():
                    # col 10: 外資合計, col 13: 投信淨買賣超, col 22: 自營商合計, col 23: 三大法人合計
                    foreign = round(_parse_num(row[10]) / 1000.0, 1)
                    trust = round(_parse_num(row[13]) / 1000.0, 1)
                    dealer = round(_parse_num(row[22]) / 1000.0, 1)
                    total = round(_parse_num(row[23]) / 1000.0, 1)
                    inst_map[code] = {
                        'foreign': foreign,
                        'trust': trust,
                        'dealer': dealer,
                        'total': total
                    }
    except Exception as e:
        print(f"Screener TPEx institutional fetch error: {e}")

    if inst_map:
        try:
            with open(MARKET_INST_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(inst_map, f, ensure_ascii=False)
        except Exception:
            pass

    return inst_map


def get_market_daily_valuation_data(force_refresh: bool = False) -> dict:
    """
    抓取全台股（上市 TWSE ＋ 上櫃 TPEx）每日官方最新本益比、殖利率、股價淨值比
    回傳：{
        '2330': {'pe': 29.56, 'pb': 10.28, 'yield': 0.86},
        ...
    }
    快取 1 天，0 API 消耗，官方公開數據涵蓋近 2,000 檔。
    """
    if not force_refresh and os.path.exists(MARKET_VALUATION_CACHE_FILE):
        try:
            mtime = os.path.getmtime(MARKET_VALUATION_CACHE_FILE)
            if time.time() - mtime < 86400:
                with open(MARKET_VALUATION_CACHE_FILE, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                    if cached and len(cached) > 800:
                        return cached
        except Exception:
            pass

    val_map = {}

    # 1. 證交所 (TWSE) 上市本益比、殖利率、淨值比 (BWIBBU_d)
    try:
        url_tw = "https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?response=json&selectType=ALL"
        r_tw = requests.get(url_tw, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        data_tw = r_tw.json().get('data', [])
        for row in data_tw:
            c = str(row[0]).strip()
            if len(c) == 4 and c.isdigit():
                val_map[c] = {
                    'yield': _parse_num(row[3]),
                    'pe': _parse_num(row[5]),
                    'pb': _parse_num(row[6])
                }
    except Exception as e:
        print(f"TWSE Valuation API error: {e}")

    # 2. 櫃買中心 (TPEx) 上櫃本益比、殖利率、淨值比
    try:
        url_otc = "https://www.tpex.org.tw/web/stock/aftertrading/peratio_analysis/pera_result.php?l=zh-tw&o=json"
        r_otc = requests.get(url_otc, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        tables = r_otc.json().get('tables', [])
        if tables:
            data_otc = tables[0].get('data', [])
            for row in data_otc:
                c = str(row[0]).strip()
                if len(c) == 4 and c.isdigit():
                    val_map[c] = {
                        'yield': _parse_num(row[5]),
                        'pe': _parse_num(row[2]),
                        'pb': _parse_num(row[6])
                    }
    except Exception as e:
        print(f"TPEx Valuation API error: {e}")

    if val_map:
        try:
            with open(MARKET_VALUATION_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(val_map, f, ensure_ascii=False)
        except Exception:
            pass

    return val_map


def get_screener_universe() -> list:
    """
    整合台股最具流動性與市場焦點的股票池（約 300~450 檔）：
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
    批次掃描股票池的多頭攻擊特徵、籌碼面動向與綜合推薦清單。
    支援 1 小時本地快取，避免重複請求 yfinance 與證交所。
    """
    if not force_refresh and os.path.exists(SCREENER_CACHE_FILE):
        try:
            mtime = os.path.getmtime(SCREENER_CACHE_FILE)
            if time.time() - mtime < SCREENER_EXPIRY_SECONDS:
                with open(SCREENER_CACHE_FILE, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    if cached_data and cached_data.get('total_scanned', 0) > 0 and 'top_recommendations' in cached_data:
                        return cached_data
        except Exception:
            pass

    universe = get_screener_universe()
    if not universe:
        return {
            'total_scanned': 0,
            'items': {},
            'top_recommendations': [],
            'trust_picks': [],
            'foreign_picks': [],
            'dual_bull_picks': [],
            'volume_surge': [],
            'consecutive_up': [],
            'breakout': [],
            'steady_ma_picks': [],
            'all_star': []
        }

    # 獲取全市場三大法人當日買賣超與官方估值數據 (PE, PB, 殖利率)
    inst_map = get_market_daily_institution_data(force_refresh=force_refresh)
    val_map = get_market_daily_valuation_data(force_refresh=force_refresh)

    # 建立 ticker 映射
    ticker_map = {}
    for c in universe:
        cinfo = get_tw_stock_chinese_info(c)
        mtype = cinfo.get('type', 'twse')
        suffix = '.TWO' if mtype == 'tpex' else '.TW'
        ticker_map[c] = f"{c}{suffix}"

    tickers = list(ticker_map.values())

    try:
        # 下載近 65 日日線資料以精確計算季均線、60日波段回檔、短線急跌跌幅與落底轉折
        df_all = yf.download(tickers, period='65d', interval='1d', group_by='ticker', progress=False, threads=True)
    except Exception as e:
        print(f"Screener yf.download error: {e}")
        df_all = pd.DataFrame()

    cdata = load_concept_data()
    items = {}

    top_recommendations = []
    trust_picks = []
    foreign_picks = []
    dual_bull_picks = []
    vol_surge_list = []
    consec_up_list = []
    breakout_list = []
    steady_ma_picks = []
    all_star_list = []
    strong_breakouts_list = []

    oversold_all = []
    oversold_flash_crash = []
    oversold_turnaround = []
    oversold_deep_value = []

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

            # 連續上漲天數計算
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

            # 均線判定 (MA5, MA10, MA20, MA60)
            ma5 = round(sum(closes[-5:]) / 5.0, 2) if len(closes) >= 5 else latest_close
            ma10 = round(sum(closes[-10:]) / 10.0, 2) if len(closes) >= 10 else latest_close
            ma20 = round(sum(closes[-20:]) / 20.0, 2) if len(closes) >= 20 else latest_close
            ma60 = round(sum(closes[-60:]) / 60.0, 2) if len(closes) >= 60 else ma20
            is_ma_bull = (latest_close > ma5 > ma10 > ma20)

            # 乖離率 (BIAS)
            bias_5 = round((latest_close - ma5) / ma5 * 100.0, 2) if ma5 > 0 else 0.0
            bias_20 = round((latest_close - ma20) / ma20 * 100.0, 2) if ma20 > 0 else 0.0
            bias_60 = round((latest_close - ma60) / ma60 * 100.0, 2) if ma60 > 0 else 0.0

            # 60 日波段最高價與回檔幅度
            lookback_60 = closes[-60:] if len(closes) >= 60 else closes
            max_60d = max(lookback_60) if lookback_60 else latest_close
            drawdown_60d = round((latest_close - max_60d) / max_60d * 100.0, 2) if max_60d > 0 else 0.0

            # 短期 3 日與 5 日累計漲跌幅
            ret_3d = round((latest_close - closes[-4]) / closes[-4] * 100.0, 2) if len(closes) >= 4 and closes[-4] > 0 else 0.0
            ret_5d = round((latest_close - closes[-6]) / closes[-6] * 100.0, 2) if len(closes) >= 6 and closes[-6] > 0 else 0.0

            # 近 5 個交易日是否有跌停板（單日跌幅 <= -8.8%）
            limit_down_count = 0
            for i in range(max(1, len(closes) - 5), len(closes)):
                p_c = closes[i - 1]
                c_c = closes[i]
                l_c = lows[i] if i < len(lows) else c_c
                if p_c > 0:
                    if (c_c - p_c) / p_c <= -0.088 or (l_c - p_c) / p_c <= -0.088:
                        limit_down_count += 1
            has_limit_down = (limit_down_count >= 1)

            # KD (9, 3, 3) 快速指標運算
            kd_k, kd_d, prev_k, prev_d = 50.0, 50.0, 50.0, 50.0
            if len(closes) >= 12:
                k_val, d_val = 50.0, 50.0
                for i in range(max(9, len(closes) - 20), len(closes)):
                    sub_h = highs[max(0, i - 8):i + 1]
                    sub_l = lows[max(0, i - 8):i + 1]
                    hh = max(sub_h) if sub_h else closes[i]
                    ll = min(sub_l) if sub_l else closes[i]
                    rsv = ((closes[i] - ll) / (hh - ll) * 100.0) if (hh > ll) else 50.0
                    prev_k, prev_d = k_val, d_val
                    k_val = round((2.0 / 3.0) * k_val + (1.0 / 3.0) * rsv, 2)
                    d_val = round((2.0 / 3.0) * d_val + (1.0 / 3.0) * k_val, 2)
                kd_k, kd_d = k_val, d_val

            # 止跌與打底轉折特徵
            is_stand_ma5 = (latest_close > ma5 and change > 0)
            is_kd_gold = (kd_k <= 35 and kd_k > kd_d and prev_k <= prev_d)
            is_hammer = (min(opens[-1], latest_close) - lows[-1]) >= 1.2 * max(0.01, abs(latest_close - opens[-1]))

            # 官方估值數據
            val = val_map.get(code, {'yield': 0.0, 'pe': 0.0, 'pb': 0.0})
            pe_val = val.get('pe', 0.0)
            yield_val = val.get('yield', 0.0)
            pb_val = val.get('pb', 0.0)

            is_good_fund = (0.0 < pe_val <= 20.0) or (yield_val >= 3.8)
            is_deep_pe = (0.0 < pe_val <= 14.0)
            is_high_yield = (yield_val >= 4.5)

            # 支撐與防守建議價
            support_price = round(max(ma10, latest_close * 0.94), 2)
            watch_price = f"{min(ma5, latest_close):.2f} ~ {max(ma5, latest_close):.2f}"

            # 法人買賣超（單位：張）
            inst = inst_map.get(code, {'foreign': 0.0, 'trust': 0.0, 'dealer': 0.0, 'total': 0.0})
            f_lots = float(inst.get('foreign', 0.0))
            t_lots = float(inst.get('trust', 0.0))
            d_lots = float(inst.get('dealer', 0.0))
            tot_lots = float(inst.get('total', 0.0))

            v_base = max(1, latest_vol_lots)
            trust_ratio = round((t_lots / v_base) * 100.0, 1)
            foreign_ratio = round((f_lots / v_base) * 100.0, 1)
            total_ratio = round((tot_lots / v_base) * 100.0, 1)

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

            # ── 策略核心特徵判斷 ─────────────────────────────
            # 1. 投信作帳認養：投信買超顯著 且 收紅
            is_trust_pick = (t_lots >= 80 or (t_lots >= 30 and trust_ratio >= 4.0)) and (pct_change > 0)

            # 2. 外資大戶鎖碼：外資買超顯著 且 收紅
            is_foreign_pick = (f_lots >= 350 or (f_lots >= 150 and foreign_ratio >= 12.0)) and (pct_change > 0)

            # 3. 土洋同步合買：外資 > 0 且 投信 > 0 且 收紅
            is_dual_bull = (f_lots > 0 and t_lots > 0) and (pct_change > 0)

            # 4. 穩健多頭起漲：均線多頭排列 且 漲幅溫和 (0 < pct <= 4.2%) 且 未遠離 MA5 均線 (未過熱追高)
            is_steady_ma = is_ma_bull and (0.0 < pct_change <= 4.2) and (latest_close <= ma5 * 1.035)

            # 5. 爆量長紅攻擊
            is_vol_surge = (vol_ratio >= 1.8 and pct_change >= 1.5 and latest_vol_lots >= 300)

            # 6. 王者共振
            is_all_star = (vol_ratio >= 1.8 and pct_change >= 2.0 and latest_vol_lots >= 500) and (consec_up >= 2 or is_breakout_20d)

            # ── 綜合推薦量化評分 (0 ~ 100) ────────────────────
            score = 50.0

            # 技術面加分
            if is_vol_surge:
                score += 14.0
            if is_breakout_20d:
                score += 12.0
            if consec_up >= 2:
                score += min(10.0, consec_up * 3.0)
            if is_ma_bull:
                score += 8.0

            # 籌碼面加分（極度關鍵指標）
            if is_dual_bull:
                score += 16.0
            elif is_trust_pick:
                score += 13.0
            elif is_foreign_pick:
                score += 10.0

            if tot_lots > 500:
                score += 6.0
            elif tot_lots > 0:
                score += 3.0

            if trust_ratio >= 5.0:
                score += 5.0
            if foreign_ratio >= 15.0:
                score += 4.0

            # 族群與成交量流動性加分
            if len(tags) >= 1:
                score += 4.0
            if latest_vol_lots >= 1000:
                score += 3.0

            score = min(99.0, max(25.0, score))
            composite_score = int(round(score))

            # 推薦星級
            if composite_score >= 88:
                stars = "⭐⭐⭐⭐⭐"
                star_label = "強力推薦"
            elif composite_score >= 78:
                stars = "⭐⭐⭐⭐"
                star_label = "優選推薦"
            else:
                stars = "⭐⭐⭐"
                star_label = "潛力觀察"

            # 產生推薦標籤清單
            rec_tags = []
            if is_dual_bull:
                rec_tags.append("🤝 土洋合買")
            elif is_trust_pick:
                rec_tags.append("👑 投信作帳")
            elif is_foreign_pick:
                rec_tags.append("🏛️ 外資鎖碼")

            if is_vol_surge:
                rec_tags.append(f"🔥 爆量{vol_ratio:.1f}x")
            if is_breakout_20d:
                rec_tags.append("🚀 創20日新高")
            if is_steady_ma:
                rec_tags.append("💎 穩健起漲")
            if consec_up >= 3:
                rec_tags.append(f"📈 連{consec_up}紅")

            # 生成白話操盤解讀理由
            reasons = []
            if is_dual_bull:
                reasons.append(f"外資加碼 {f_lots:+,.0f} 張、投信買超 {t_lots:+,.0f} 張，土洋聯手籌碼極度安定")
            elif is_trust_pick:
                reasons.append(f"投信大買 {t_lots:+,.0f} 張（佔量 {trust_ratio:.1f}%），具法人作帳認養動能")
            elif is_foreign_pick:
                reasons.append(f"外資主力單日買超 {f_lots:+,.0f} 張（佔量 {foreign_ratio:.1f}%），鎖碼拉抬明顯")

            if is_vol_surge:
                reasons.append(f"成交量放大至 {vol_ratio:.1f} 倍帶量長紅")
            if is_breakout_20d:
                reasons.append("收盤價強勢突破 20 日整理平台新高，上方無沉重套牢賣壓")
            if is_steady_ma:
                reasons.append("短中均線呈多頭排列，股價守穩均線支撐具低接價值")

            if not reasons:
                recommend_reason = f"均線多頭格局，量能維持活絡，短線技術指標維持多方控盤。"
            else:
                recommend_reason = "，".join(reasons) + "。"

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
                'ma5': ma5,
                'ma10': ma10,
                'ma20': ma20,
                'support_price': support_price,
                'watch_price': watch_price,
                'foreign_lots': f_lots,
                'trust_lots': t_lots,
                'dealer_lots': d_lots,
                'inst_total_lots': tot_lots,
                'trust_ratio': trust_ratio,
                'foreign_ratio': foreign_ratio,
                'is_trust_pick': is_trust_pick,
                'is_foreign_pick': is_foreign_pick,
                'is_dual_bull': is_dual_bull,
                'is_steady_ma': is_steady_ma,
                'composite_score': composite_score,
                'stars': stars,
                'star_label': star_label,
                'rec_tags': rec_tags,
                'recommend_reason': recommend_reason,
                'sparkline': sparkline,
                'pe': pe_val,
                'dividend_yield': yield_val,
                'pb': pb_val,
                'drawdown_60d': drawdown_60d,
                'ret_3d': ret_3d,
                'ret_5d': ret_5d,
                'has_limit_down': has_limit_down,
                'limit_down_count': limit_down_count,
                'bias_5': bias_5,
                'bias_20': bias_20,
                'bias_60': bias_60,
                'kd_k': kd_k,
                'kd_d': kd_d,
                'is_stand_ma5': is_stand_ma5,
                'is_kd_gold': is_kd_gold,
                'is_hammer': is_hammer
            }

            items[code] = entry

            # 各策略清單歸類
            if is_vol_surge:
                vol_surge_list.append(entry)

            if consec_up >= 3 and pct_change > 0:
                consec_up_list.append(entry)

            if is_breakout_20d and pct_change > 0 and latest_vol_lots >= 300:
                breakout_list.append(entry)

            if is_all_star:
                all_star_list.append(entry)

            if is_trust_pick:
                trust_picks.append(entry)

            if is_foreign_pick:
                foreign_picks.append(entry)

            if is_dual_bull:
                dual_bull_picks.append(entry)

            if is_steady_ma:
                steady_ma_picks.append(entry)

            # 7. 全市場真強勢突破（整理長紅突破，不限題材庫、不限連漲天數，由實體大長紅與大法人鎖碼驅動）
            high_latest = highs[-1] if len(highs) > 0 else 0
            body_ratio = (latest_close / high_latest) if high_latest > 0 else 0.0
            if (is_breakout_20d and pct_change >= 4.0 and body_ratio >= 0.965 and
                vol_ratio >= 1.8 and latest_vol_lots >= 800 and tot_lots > 0):
                entry['is_strong_breakout'] = True
                entry['breakout_phase'] = 'initial' if consec_up <= 2 else 'continuing'
                entry['breakout_phase_label'] = '🌱 初升發動' if consec_up <= 2 else f'🔥 主升續噴 (連{consec_up}紅)'
                strong_breakouts_list.append(entry)

            # 8. 跌深價值與轉折潛力股判定 (急跌錯殺 / 打底轉折 / 價值超跌)
            is_flash_crash = (
                is_good_fund and latest_vol_lots >= 200 and
                (has_limit_down or ret_3d <= -8.0 or ret_5d <= -12.0 or bias_5 <= -6.0 or bias_20 <= -12.0)
            )

            is_turnaround = (
                is_good_fund and latest_vol_lots >= 250 and
                (drawdown_60d <= -10.0 or bias_20 <= -4.5 or ret_5d <= -4.5) and
                (is_stand_ma5 or is_kd_gold or is_hammer)
            )

            is_deep_value = (
                is_good_fund and latest_vol_lots >= 200 and
                (is_deep_pe or is_high_yield) and
                (drawdown_60d <= -12.0 or bias_60 <= -6.0 or bias_20 <= -4.5)
            )

            if is_flash_crash or is_turnaround or is_deep_value:
                os_entry = dict(entry)
                os_entry['is_flash_crash'] = is_flash_crash
                os_entry['is_turnaround'] = is_turnaround
                os_entry['is_deep_value'] = is_deep_value

                # 專屬標籤
                os_tags = []
                if is_flash_crash:
                    os_tags.append("⚡ 急跌錯殺")
                if has_limit_down:
                    os_tags.append("🩸 曾連碰跌停" if limit_down_count >= 2 else "🩸 曾碰跌停")
                if is_turnaround:
                    os_tags.append("🔄 打底轉折")
                if is_stand_ma5:
                    os_tags.append("📈 站上5MA")
                if is_kd_gold:
                    os_tags.append("🌟 KD低檔金叉")
                if is_hammer:
                    os_tags.append("💥 爆量長下影線")
                if tot_lots > 100:
                    os_tags.append("🤝 法人低檔回補")
                if is_deep_pe:
                    os_tags.append(f"PE {pe_val:.1f}x")
                if yield_val >= 4.0:
                    os_tags.append(f"🛡️ 殖利率 {yield_val:.1f}%")

                os_entry['oversold_tags'] = os_tags

                # 操盤解讀理由
                os_reasons = []
                if pe_val > 0:
                    os_reasons.append(f"本益比僅 {pe_val:.1f} 倍")
                if yield_val > 0:
                    os_reasons.append(f"殖利率達 {yield_val:.1f}%")
                if is_flash_crash:
                    os_reasons.append(f"近5日急跌 {ret_5d:.1f}% 觸發恐慌清洗，短線具備急跌錯殺報復性反彈契機")
                elif is_turnaround:
                    os_reasons.append(f"自波段高點回檔 {drawdown_60d:.1f}% 後，今日出現轉折止跌訊號")
                elif is_deep_value:
                    os_reasons.append(f"波段修正 {drawdown_60d:.1f}% 進入深幅折價區，具長線安全邊際")

                os_entry['oversold_reason'] = "，".join(os_reasons) + "。"

                oversold_all.append(os_entry)
                if is_flash_crash:
                    oversold_flash_crash.append(os_entry)
                if is_turnaround:
                    oversold_turnaround.append(os_entry)
                if is_deep_value:
                    oversold_deep_value.append(os_entry)

            # 納入綜合評分候選
            if pct_change > 0 and latest_vol_lots >= 300:
                top_recommendations.append(entry)

        except Exception:
            continue

    # 排序邏輯
    top_recommendations.sort(key=lambda x: (x['composite_score'], x['pct_change']), reverse=True)
    trust_picks.sort(key=lambda x: (x['trust_lots'], x['pct_change']), reverse=True)
    foreign_picks.sort(key=lambda x: (x['foreign_lots'], x['pct_change']), reverse=True)
    dual_bull_picks.sort(key=lambda x: (x['inst_total_lots'], x['pct_change']), reverse=True)
    vol_surge_list.sort(key=lambda x: (x['vol_ratio'], x['pct_change']), reverse=True)
    consec_up_list.sort(key=lambda x: (x['consec_up'], x['pct_change']), reverse=True)
    breakout_list.sort(key=lambda x: (x['pct_change'], x['vol_ratio']), reverse=True)
    steady_ma_picks.sort(key=lambda x: (x['composite_score'], -abs(x['pct_change'] - 2.0)), reverse=True)
    all_star_list.sort(key=lambda x: (x['pct_change'], x['vol_ratio']), reverse=True)

    strong_breakouts_list.sort(key=lambda x: (x['pct_change'], x['vol_ratio']), reverse=True)
    strong_continuing = [x for x in strong_breakouts_list if x['consec_up'] >= 3]
    strong_initial = [x for x in strong_breakouts_list if x['consec_up'] <= 2]

    oversold_all.sort(key=lambda x: (x['drawdown_60d'], -x['dividend_yield']))
    oversold_flash_crash.sort(key=lambda x: (x['ret_5d'], x['drawdown_60d']))
    oversold_turnaround.sort(key=lambda x: (-x['pct_change'], x['drawdown_60d']))
    oversold_deep_value.sort(key=lambda x: (-x['dividend_yield'], x['pe'] if x['pe'] > 0 else 999))

    result = {
        'timestamp': datetime.now().isoformat(),
        'scan_date': datetime.now().strftime('%Y-%m-%d'),
        'total_scanned': len(items),
        'items': items,
        'top_recommendations': top_recommendations[:15],
        'trust_picks': trust_picks,
        'foreign_picks': foreign_picks,
        'dual_bull_picks': dual_bull_picks,
        'volume_surge': vol_surge_list,
        'consecutive_up': consec_up_list,
        'breakout': breakout_list,
        'steady_ma_picks': steady_ma_picks,
        'all_star': all_star_list,
        'strong_breakouts': strong_breakouts_list,
        'strong_continuing': strong_continuing,
        'strong_initial': strong_initial,
        'oversold_all': oversold_all,
        'oversold_flash_crash': oversold_flash_crash,
        'oversold_turnaround': oversold_turnaround,
        'oversold_deep_value': oversold_deep_value
    }

    try:
        concept_rankings = get_concept_rotation_rankings(screener_data={'items': items})
        result['concept_rankings'] = concept_rankings
    except Exception:
        result['concept_rankings'] = []

    try:
        concept_consec = get_concept_consecutive_rankings(screener_data={'items': items})
        result['concept_consecutive_rankings'] = concept_consec
    except Exception:
        result['concept_consecutive_rankings'] = []

    try:
        with open(SCREENER_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return result


def get_concept_rotation_rankings(screener_data: dict = None) -> list:
    """
    計算今日各概念族群的資金輪動強度與平均漲幅排行，並找出族群指標領頭羊
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
                            'pct_change': pct,
                            'close': info.get('close', 0.0),
                            'volume_lots': info.get('volume_lots', 0),
                            'sparkline': info.get('sparkline', [])
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


def get_concept_consecutive_rankings(screener_data: dict = None) -> list:
    """
    全市場大數據動態計算：所有概念族群的【連續上漲天數】、【累積總漲幅】與【今日表現】
    由連續上漲天數由多到少排序（連漲9天 -> 6天 -> 5天...），
    同時整理該族群內的所有成分股（領頭羊、法人中軍、穩健起漲），供使用者一鍵展開查看。
    """
    if screener_data is None:
        screener_data = scan_market_signals()

    items = screener_data.get('items', {})
    if not items:
        return []

    cdata = load_concept_data()
    consec_rankings = []

    for big_cat, sub_cats in cdata.get('概念分類', {}).items():
        if not isinstance(sub_cats, dict):
            continue
        for cname, cinfo in sub_cats.items():
            if not isinstance(cinfo, dict):
                continue
            stocks = cinfo.get('stocks', [])
            valid_stocks = []
            for s in stocks:
                code = str(s.get('code') if isinstance(s, dict) else s).strip()
                if code in items:
                    it = items[code]
                    role = s.get('role', '') if isinstance(s, dict) else ''
                    valid_stocks.append({
                        'code': code,
                        'name': it.get('name', code),
                        'role': role,
                        'market_short': it.get('market_short', '市'),
                        'close': it.get('close', 0.0),
                        'pct_change': it.get('pct_change', 0.0),
                        'volume_lots': it.get('volume_lots', 0),
                        'vol_ratio': it.get('vol_ratio', 1.0),
                        'consec_up': it.get('consec_up', 0),
                        'inst_total_lots': it.get('inst_total_lots', 0.0),
                        'trust_lots': it.get('trust_lots', 0.0),
                        'foreign_lots': it.get('foreign_lots', 0.0),
                        'composite_score': it.get('composite_score', 50),
                        'stars': it.get('stars', '⭐⭐⭐'),
                        'rec_tags': it.get('rec_tags', []),
                        'recommend_reason': it.get('recommend_reason', ''),
                        'is_steady_ma': it.get('is_steady_ma', False),
                        'is_breakout_20d': it.get('is_breakout_20d', False),
                        'sparkline': it.get('sparkline', [])
                    })

            if len(valid_stocks) < 2:
                continue

            # 依據近 10 日 sparkline 計算每日族群平均漲跌幅
            spark_lens = [len(s['sparkline']) for s in valid_stocks if len(s['sparkline']) >= 5]
            if not spark_lens:
                continue
            min_len = min(spark_lens)

            daily_returns = []
            for d in range(1, min_len):
                day_rets = []
                for s in valid_stocks:
                    sp = s['sparkline']
                    if len(sp) >= min_len and sp[d - 1] > 0:
                        day_rets.append((sp[d] - sp[d - 1]) / sp[d - 1] * 100.0)
                if day_rets:
                    daily_returns.append(sum(day_rets) / len(day_rets))

            consec_days = 0
            cum_pct = 0.0
            for r in reversed(daily_returns):
                if r > 0:
                    consec_days += 1
                    cum_pct += r
                else:
                    break

            # 族群內成分股依今日漲幅排序
            by_pct = sorted(valid_stocks, key=lambda x: x['pct_change'], reverse=True)
            by_inst = sorted(valid_stocks, key=lambda x: x['inst_total_lots'], reverse=True)

            up_count = sum(1 for s in valid_stocks if s['pct_change'] > 0)

            consec_rankings.append({
                'big_category': big_cat,
                'concept_name': cname,
                'desc': cinfo.get('desc', ''),
                'consec_days': consec_days,
                'cum_pct': round(cum_pct, 2),
                'today_avg_pct': round(daily_returns[-1], 2) if daily_returns else 0.0,
                'total_count': len(valid_stocks),
                'up_count': up_count,
                'up_ratio': round(up_count / len(valid_stocks) * 100.0, 1),
                'leader': by_pct[0] if by_pct else None,
                'inst_leader': by_inst[0] if by_inst else None,
                'stocks': by_pct
            })

    # 預設由「連續上漲天數」由多到少排序，天數相同則依「累計漲幅」由高到低
    consec_rankings.sort(key=lambda x: (x['consec_days'], x['cum_pct'], x['today_avg_pct']), reverse=True)
    return consec_rankings

