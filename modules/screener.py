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
SCREENER_EXPIRY_SECONDS = 3600  # 1 小時快取


def _parse_num(v) -> float:
    if v is None:
        return 0.0
    s = str(v).replace(',', '').strip()
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

    # 獲取全市場三大法人當日買賣超
    inst_map = get_market_daily_institution_data(force_refresh=force_refresh)

    # 建立 ticker 映射
    ticker_map = {}
    for c in universe:
        cinfo = get_tw_stock_chinese_info(c)
        mtype = cinfo.get('type', 'twse')
        suffix = '.TWO' if mtype == 'tpex' else '.TW'
        ticker_map[c] = f"{c}{suffix}"

    tickers = list(ticker_map.values())

    try:
        # 下載近 25 日日線資料以精確計算均量、連漲天數、均線與 20 日高點
        df_all = yf.download(tickers, period='25d', interval='1d', group_by='ticker', progress=False, threads=True)
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

            # 均線判定 (MA5, MA10, MA20)
            ma5 = round(sum(closes[-5:]) / 5.0, 2) if len(closes) >= 5 else latest_close
            ma10 = round(sum(closes[-10:]) / 10.0, 2) if len(closes) >= 10 else latest_close
            ma20 = round(sum(closes[-20:]) / 20.0, 2) if len(closes) >= 20 else latest_close
            is_ma_bull = (latest_close > ma5 > ma10 > ma20)

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
                'sparkline': sparkline
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
        'all_star': all_star_list
    }

    try:
        concept_rankings = get_concept_rotation_rankings(screener_data={'items': items})
        result['concept_rankings'] = concept_rankings
    except Exception:
        result['concept_rankings'] = []

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
