"""
台股籌碼面分析模組
資料來源：FinMind 免費公開 API
包含：
1. 個股三大法人買賣超（外資、投信、自營商，單位：張）
2. 個股融資融券變化與券資比
3. 籌碼集中度評分與連買連賣天數計算
"""
import os
import json
import time
import requests
import pandas as pd
from datetime import datetime, timedelta

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)
FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"


def get_institutional_trend(code: str, days: int = 65) -> pd.DataFrame:
    """
    取得個股近 N 個交易日三大法人買賣超（單位：張）
    回傳欄位：['Foreign', 'Trust', 'Dealer', 'Total', '外資', '投信', '自營商', '三大法人合計']
    """
    code = str(code).strip()
    cache_path = os.path.join(CACHE_DIR, f"chip_inst_v2_{code}.json")

    rows = None
    if os.path.exists(cache_path) and (time.time() - os.path.getmtime(cache_path) < 3600):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                rows = json.load(f)
        except Exception:
            rows = None

    if rows is None:
        try:
            start_d = (datetime.now() - timedelta(days=max(200, days * 2 + 40))).strftime('%Y-%m-%d')
            r = requests.get(
                FINMIND_URL,
                params={
                    'dataset': 'TaiwanStockInstitutionalInvestorsBuySell',
                    'data_id': code,
                    'start_date': start_d
                },
                timeout=10
            )
            rows = r.json().get('data', [])
            if rows:
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(rows, f, ensure_ascii=False)
        except Exception as e:
            print(f"FinMind institutional error for {code}: {e}")
            rows = []

    if not rows:
        return pd.DataFrame()

    # 依日期彙整外資、投信、自營商買賣超（股數轉張數：除以 1000）
    daily = {}
    for row in rows:
        d = row.get('date')
        name = row.get('name', '')
        net_shares = float(row.get('buy', 0) or 0) - float(row.get('sell', 0) or 0)
        net_lots = round(net_shares / 1000.0, 1)  # 轉為「張」

        if d not in daily:
            daily[d] = {'外資': 0.0, '投信': 0.0, '自營商': 0.0}

        if 'Foreign' in name:
            daily[d]['外資'] = round(daily[d]['外資'] + net_lots, 1)
        elif 'Investment_Trust' in name:
            daily[d]['投信'] = round(daily[d]['投信'] + net_lots, 1)
        elif 'Dealer' in name:
            daily[d]['自營商'] = round(daily[d]['自營商'] + net_lots, 1)

    records = []
    for d in sorted(daily.keys())[-days:]:
        f_val = daily[d]['外資']
        t_val = daily[d]['投信']
        d_val = daily[d]['自營商']
        tot_val = round(f_val + t_val + d_val, 1)
        records.append({
            'Date': d,
            '外資': f_val,
            '投信': t_val,
            '自營商': d_val,
            '三大法人合計': tot_val,
            # 相容 charts.py 欄位名稱
            'Foreign': f_val,
            'Trust': t_val,
            'Dealer': d_val,
            'Total': tot_val
        })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df.set_index('Date', inplace=True)
    return df


def get_margin_trading(code: str, days: int = 25) -> pd.DataFrame:
    """
    取得個股近 N 個交易日融資融券餘額與變化（單位：張）
    """
    code = str(code).strip()
    cache_path = os.path.join(CACHE_DIR, f"chip_margin_{code}.json")

    rows = None
    if os.path.exists(cache_path) and (time.time() - os.path.getmtime(cache_path) < 3600):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                rows = json.load(f)
        except Exception:
            rows = None

    if rows is None:
        try:
            start_d = (datetime.now() - timedelta(days=days * 2 + 20)).strftime('%Y-%m-%d')
            r = requests.get(
                FINMIND_URL,
                params={
                    'dataset': 'TaiwanStockMarginPurchaseShortSale',
                    'data_id': code,
                    'start_date': start_d
                },
                timeout=10
            )
            rows = r.json().get('data', [])
            if rows:
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(rows, f, ensure_ascii=False)
        except Exception as e:
            print(f"FinMind margin error for {code}: {e}")
            rows = []

    if not rows:
        return pd.DataFrame()

    records = []
    for row in rows[-days:]:
        d = row.get('date')
        m_today = float(row.get('MarginPurchaseTodayBalance', 0) or 0)
        m_yest = float(row.get('MarginPurchaseYesterdayBalance', 0) or 0)
        s_today = float(row.get('ShortSaleTodayBalance', 0) or 0)
        s_yest = float(row.get('ShortSaleYesterdayBalance', 0) or 0)

        ratio = round(s_today / m_today * 100, 2) if m_today > 0 else 0.0

        records.append({
            'Date': d,
            '融資餘額(張)': int(m_today),
            '融資增減(張)': int(m_today - m_yest),
            '融券餘額(張)': int(s_today),
            '融券增減(張)': int(s_today - s_yest),
            '券資比(%)': ratio,
            # 相容 charts.py
            'MarginLong': int(m_today),
            'MarginShort': int(s_today)
        })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df.set_index('Date', inplace=True)
    return df


def _calc_streak(series: pd.Series) -> int:
    """計算連續買超(>0)或連續賣超(<0)天數"""
    if series is None or series.empty:
        return 0
    vals = list(series.values)[::-1]
    if not vals or vals[0] == 0:
        return 0
    direction = 1 if vals[0] > 0 else -1
    count = 0
    for v in vals:
        if (v > 0 and direction > 0) or (v < 0 and direction < 0):
            count += 1
        else:
            break
    return count * direction


def calculate_chip_intensity(inst_df: pd.DataFrame, info: dict = None, latest_close: float = None) -> tuple:
    """
    計算「法人籌碼力度（顯著買超）」雙層量化指標：
    - 第一層（縱向標準化 Z-Score）：將每日法人買賣超與近 20 日均值/標準差比較，量化「相對於個股平日習性的異常倍數 (σ)」
    - 第二層（橫向佔股本比 %）：將每日與近 5 日法人買賣超張數除以「公司總發行張數（股本）」，量化「吃掉整間公司多少比例籌碼」
    - 綜合過濾：只有同時具備「標準化異常放大」與「實質股本份量」的買超才標記為『🔥 顯著買超（法人在拉）』，其餘列為『⚪ 一般雜訊』
    """
    if inst_df is None or inst_df.empty or '三大法人合計' not in inst_df.columns:
        return pd.DataFrame(), {'available': False}

    df = inst_df.copy()
    info = info or {}

    # 1. 推算公司總股本張數（台股預設面額 10 元 -> 1 億元股本 = 10,000 張）
    cap_yi = info.get('capital_yi')
    mcap = info.get('market_cap')
    total_lots = None
    if cap_yi and float(cap_yi) > 0:
        total_lots = float(cap_yi) * 10000.0
    elif mcap and latest_close and float(latest_close) > 0:
        total_lots = float(mcap) / float(latest_close) / 1000.0

    # 若仍無股本資料，以預設中型股 100,000 張（10億股本）估算
    if not total_lots or total_lots <= 0:
        total_lots = 100000.0

    # 2. 第一層：計算三大法人合計買賣超之標準化 Z-Score
    s_tot = df['三大法人合計'].astype(float)
    mean_v = float(s_tot.mean())
    std_v = float(s_tot.std(ddof=0)) if len(s_tot) > 1 else 1.0
    if std_v < 1.0:
        std_v = max(1.0, abs(mean_v) * 0.5 + 1.0)

    df['Z_Score'] = ((s_tot - mean_v) / std_v).round(2)

    # 3. 第二層：計算單日與近5日累積「買賣超佔股本比 (%)」
    df['佔股本比(%)'] = (s_tot / total_lots * 100.0).round(3)
    if '外資' in df.columns:
        df['外資佔股本比(%)'] = (df['外資'].astype(float) / total_lots * 100.0).round(3)
    if '投信' in df.columns:
        df['投信佔股本比(%)'] = (df['投信'].astype(float) / total_lots * 100.0).round(3)
    df['近5日佔股本比(%)'] = (s_tot.rolling(5, min_periods=1).sum() / total_lots * 100.0).round(3)

    # 4. 合成「法人籌碼力度指數」與信號分類（過濾雜訊，抓出真正『顯著買超』）
    signals = []
    intensity_scores = []
    for _, row in df.iterrows():
        net_lots = float(row['三大法人合計'])
        z = float(row['Z_Score'])
        cap_pct = float(row['佔股本比(%)'])

        # 綜合力度值：結合 Z-Score 與 佔股本比（佔股本 0.2% 約等於 1 個標準差權重）
        raw_intensity = round(z * 0.55 + (cap_pct / 0.20) * 0.45, 2)
        intensity_scores.append(raw_intensity)

        # 判定是否為「顯著買超」（必須買超 > 0，且具備高 Z-Score 或高佔股本比）
        if net_lots > 0 and (
            (z >= 1.2 and cap_pct >= 0.08) or
            cap_pct >= 0.25 or
            (z >= 1.6 and cap_pct >= 0.03)
        ):
            signals.append('🔥 顯著買超')
        elif net_lots > 0 and (z >= 0.75 or cap_pct >= 0.10):
            signals.append('🟠 有效買入')
        elif net_lots < 0 and (
            (z <= -1.2 and cap_pct <= -0.08) or
            cap_pct <= -0.25 or
            (z <= -1.6 and cap_pct <= -0.03)
        ):
            signals.append('🟢 顯著賣超')
        elif net_lots < 0 and (z <= -0.75 or cap_pct <= -0.10):
            signals.append('🟢 偏空調節')
        else:
            signals.append('⚪ 一般雜訊')

    df['籌碼力度'] = intensity_scores
    df['標準化Z值'] = df['Z_Score']
    df['力度信號'] = signals

    # 5. 彙整最新日與近 5 日「籌碼力度」結論
    last_r = df.iloc[-1]
    last_z = float(last_r['Z_Score'])
    last_cap_pct = float(last_r['佔股本比(%)'])
    last_f_cap_pct = float(last_r.get('外資佔股本比(%)', 0.0))
    last_t_cap_pct = float(last_r.get('投信佔股本比(%)', 0.0))
    last_5d_cap_pct = float(last_r['近5日佔股本比(%)'])
    sum20_cap_pct = round(float(df['佔股本比(%)'].tail(20).sum()), 3)
    last_sig = str(last_r['力度信號'])
    last_intensity = float(last_r['籌碼力度'])

    # 統計近 20 日與近 5 日出現過幾次「🔥 顯著買超」與「🟢 顯著賣超」
    sig_buy_days_20 = [str(idx)[-5:] for idx, r in df.tail(20).iterrows() if r['力度信號'] == '🔥 顯著買超']
    sig_buy_days_5 = [str(idx)[-5:] for idx, r in df.tail(5).iterrows() if r['力度信號'] in ('🔥 顯著買超', '🟠 有效買入')]
    sig_sell_days_5 = [str(idx)[-5:] for idx, r in df.tail(5).iterrows() if r['力度信號'] == '🟢 顯著賣超']

    # 綜合狀態標題與白話解讀
    if last_sig == '🔥 顯著買超' or (last_5d_cap_pct >= 0.50 and len(sig_buy_days_5) >= 2):
        headline = "🔥 顯著買超（法人強拉信號！）"
        badge_color = "#e53935"
        verdict = (
            f"通過雙層過濾！最新單日買超標準化力度達 <b>{last_z:+.2f} σ</b>（單日吃掉股本 <b>{last_cap_pct:+.3f}%</b>），"
            f"近 5 日累計買超佔總股本達 <b>{last_5d_cap_pct:+.2f}%</b>（公司總股本約 {int(total_lots):,} 張）。"
            f"這不是一般散亂小買，而是<b>相對於公司股本極具份量的「法人有效鎖碼／正在拉抬」信號</b>！"
        )
    elif last_5d_cap_pct >= 0.20 or last_sig == '🟠 有效買入':
        headline = "🟠 有效買入（法人溫和吃貨）"
        badge_color = "#FB8C00"
        verdict = (
            f"最新單日標準化力度 <b>{last_z:+.2f} σ</b>（佔股本 <b>{last_cap_pct:+.3f}%</b>），"
            f"近 5 日累計買超佔公司總股本 <b>{last_5d_cap_pct:+.2f}%</b>，屬於具實質份量的正向買盤。"
        )
    elif last_sig == '🟢 顯著賣超' or last_5d_cap_pct <= -0.50:
        headline = "🟢 顯著賣超（法人實質倒貨）"
        badge_color = "#43a047"
        verdict = (
            f"最新單日標準化力度 <b>{last_z:+.2f} σ</b>（單日調節佔股本 <b>{last_cap_pct:+.3f}%</b>），"
            f"近 5 日累計賣超佔總股本 <b>{last_5d_cap_pct:+.2f}%</b>，屬於有份量的法人減碼，短線宜避開賣壓。"
        )
    else:
        headline = "⚪ 一般雜訊（無顯著大動作，已過濾）"
        badge_color = "#64748B"
        verdict = (
            f"雖然帳面上三大法人單日買賣超 {float(last_r['三大法人合計']):+,.1f} 張，但經標準化後僅 <b>{last_z:+.2f} σ</b>、"
            f"佔總股本（{int(total_lots):,} 張）僅 <b>{last_cap_pct:+.3f}%</b>（近5日累計 {last_5d_cap_pct:+.2f}%）。"
            f"<b>相對於整間公司股本份量極小，屬於日常交易雜訊，還不到「法人主力狂拉」的顯著門檻。</b>"
        )

    meta = {
        'available': True,
        'total_issued_lots': int(round(total_lots)),
        'total_lots': int(round(total_lots)),
        'latest_z_score': last_z,
        'latest_cap_pct': last_cap_pct,
        'latest_f_cap_pct': last_f_cap_pct,
        'latest_t_cap_pct': last_t_cap_pct,
        'sum5_cap_pct': last_5d_cap_pct,
        'sum20_cap_pct': sum20_cap_pct,
        'latest_intensity': last_intensity,
        'latest_signal': last_sig,
        'is_latest_sig_buy': (last_sig == '🔥 顯著買超'),
        'is_latest_sig_sell': (last_sig == '🟢 顯著賣超'),
        'headline': headline,
        'badge_color': badge_color,
        'verdict': verdict,
        'sig_buy_days_20': sig_buy_days_20,
        'sig_buy_dates_20d': sig_buy_days_20,
        'sig_buy_count_20': len(sig_buy_days_20),
        'sig_buy_count_20d': len(sig_buy_days_20),
        'sig_buy_count_5d': len(sig_buy_days_5),
        'sig_sell_count_5d': len(sig_sell_days_5),
    }
    return df, meta


def get_chip_score(data: pd.DataFrame, info: dict = None, latest_close: float = None) -> tuple:
    """
    計算籌碼面分數 0-100 與中文評級標籤（升級整合「標準化 Z-Score」與「買賣超佔股本比」）
    回傳：(score: int, label: str)
    """
    if data is None or data.empty or '三大法人合計' not in data.columns:
        return 50, '⚪ 中性（無近期法人重大異動）'

    score = 50
    recent5 = data.tail(5)
    recent20 = data.tail(20)

    sum5_total = recent5['三大法人合計'].sum()
    sum5_trust = recent5['投信'].sum()

    # 結合兩層「籌碼力度」加減分
    _, intensity_meta = calculate_chip_intensity(data, info=info, latest_close=latest_close)
    if intensity_meta.get('available'):
        sum5_cap = intensity_meta.get('sum5_cap_pct', 0)
        last_z = intensity_meta.get('latest_z_score', 0)
        # 第二層：近5日佔股本比權重
        if sum5_cap >= 0.8:
            score += 22
        elif sum5_cap >= 0.25:
            score += 14
        elif sum5_cap > 0.05:
            score += 7
        elif sum5_cap <= -0.8:
            score -= 22
        elif sum5_cap <= -0.25:
            score -= 14
        elif sum5_cap < -0.05:
            score -= 7

        # 第一層：最新單日標準化爆發力 Z-Score
        if last_z >= 1.5:
            score += 10
        elif last_z <= -1.5:
            score -= 10
    else:
        if sum5_total > 500:
            score += 15
        elif sum5_total > 0:
            score += 8
        elif sum5_total < -500:
            score -= 15
        elif sum5_total < 0:
            score -= 8

    # 投信（內資作帳重要指標）
    if sum5_trust > 100:
        score += 10
    elif sum5_trust > 0:
        score += 5
    elif sum5_trust < -100:
        score -= 8

    # 外資連買連賣天數
    f_streak = _calc_streak(data['外資'])
    if f_streak >= 3:
        score += 10
    elif f_streak <= -3:
        score -= 10

    # 近20日趨勢
    if recent20['三大法人合計'].sum() > 0:
        score += 5
    else:
        score -= 5

    score = max(10, min(95, score))

    if score >= 75:
        label = '🔥 顯著買超鎖碼（法人強拉）'
    elif score >= 60:
        label = '🟠 法人有效買入（籌碼偏多）'
    elif score >= 45:
        label = '⚪ 一般雜訊區間（籌碼中性）'
    elif score >= 30:
        label = '🟢 法人調節賣出（籌碼偏弱）'
    else:
        label = '🟢 法人顯著提款（籌碼弱勢）'

    return int(score), label


def get_chip_summary(inst_df: pd.DataFrame, margin_df: pd.DataFrame = None, info: dict = None, latest_close: float = None) -> dict:
    """
    產生完整的中文籌碼統計摘要（含最新日、近5日、近20日、連買連賣天數、以及『法人籌碼力度』雙層指標）
    """
    if inst_df is None or inst_df.empty:
        return {
            'available': False,
            'message': '此股票暫無三大法人買賣超明細'
        }

    r1 = inst_df.tail(1)
    r5 = inst_df.tail(5)
    r20 = inst_df.tail(20)

    f_streak = _calc_streak(inst_df['外資'])
    t_streak = _calc_streak(inst_df['投信'])
    tot_streak = _calc_streak(inst_df['三大法人合計'])

    def streak_str(s):
        if s > 0:
            return f"連 {s} 日買超 🔴"
        if s < 0:
            return f"連 {abs(s)} 日賣超 🟢"
        return "持平 ⚪"

    df_with_intensity, intensity_meta = calculate_chip_intensity(inst_df, info=info, latest_close=latest_close)

    summary = {
        'available': True,
        'latest_date': str(inst_df.index[-1]),
        'foreign_1d': float(r1['外資'].iloc[0]),
        'trust_1d': float(r1['投信'].iloc[0]),
        'dealer_1d': float(r1['自營商'].iloc[0]),
        'total_1d': float(r1['三大法人合計'].iloc[0]),
        'foreign_5d': round(float(r5['外資'].sum()), 1),
        'trust_5d': round(float(r5['投信'].sum()), 1),
        'dealer_5d': round(float(r5['自營商'].sum()), 1),
        'total_5d': round(float(r5['三大法人合計'].sum()), 1),
        'foreign_20d': round(float(r20['外資'].sum()), 1),
        'trust_20d': round(float(r20['投信'].sum()), 1),
        'dealer_20d': round(float(r20['自營商'].sum()), 1),
        'total_20d': round(float(r20['三大法人合計'].sum()), 1),
        'foreign_streak': streak_str(f_streak),
        'trust_streak': streak_str(t_streak),
        'total_streak': streak_str(tot_streak),
        'intensity_meta': intensity_meta,
    }

    if margin_df is not None and not margin_df.empty:
        m1 = margin_df.tail(1)
        m5 = margin_df.tail(5)
        summary['margin_balance'] = int(m1['融資餘額(張)'].iloc[0])
        summary['margin_change_1d'] = int(m1['融資增減(張)'].iloc[0])
        summary['margin_change_5d'] = int(m5['融資增減(張)'].sum())
        summary['short_balance'] = int(m1['融券餘額(張)'].iloc[0])
        summary['short_change_1d'] = int(m1['融券增減(張)'].iloc[0])
        summary['short_ratio'] = float(m1['券資比(%)'].iloc[0])

    return summary


def calculate_mofi_institutional_series(
    inst_df: pd.DataFrame,
    df_price: pd.DataFrame = None,
    info: dict = None,
    investor_type: str = '三大法人',
    denom_mode: str = '佔股本比',
    sensitivity: float = 2.0,
    fast_len: int = 10,
    slow_len: int = 40,
    z_win: int = 20
) -> pd.DataFrame:
    """
    復刻 @MOFI「法人力度 (2026 版)」核心演算法：
    - 支援 4 種法人選擇：'三大法人' / '外資' / '投信' / '自營商'
    - 支援 2 種標準化分母：'佔股本比'（買賣超張數 ÷ 總股本張數） / '成交力道'（買賣超張數 ÷ 當日總成交張數）
      （當選『投信』×『佔股本比』時，即為市場經典『投本比』）
    - 計算近期法人動向（快線 10MA，白色實線）與長期法人基準（慢線 40MA，白色虛線）
    - 計算極端值統計視窗（20日 Z-Score），當正向力道突破 sensitivity (1.5 / 2.0 / 2.5) 個標準差時，標記『🟡 顯著買超（極端訊號）』
    """
    if inst_df is None or inst_df.empty:
        return pd.DataFrame()

    df = inst_df.copy()
    col_map = {
        '三大法人': '三大法人合計',
        '外資': '外資',
        '投信': '投信',
        '自營商': '自營商'
    }
    target_col = col_map.get(investor_type, '三大法人合計')
    if target_col not in df.columns:
        target_col = '三大法人合計'

    # 1. 取得總股本張數
    info = info or {}
    cap_yi = info.get('capital_yi')
    mcap = info.get('market_cap')
    latest_close = float(df_price['Close'].iloc[-1]) if (df_price is not None and not df_price.empty) else None
    total_lots = None
    if cap_yi and float(cap_yi) > 0:
        total_lots = float(cap_yi) * 10000.0
    elif mcap and latest_close and latest_close > 0:
        total_lots = float(mcap) / latest_close / 1000.0
    if not total_lots or total_lots <= 0:
        total_lots = 100000.0

    # 2. 對齊每日成交量（張）以供「成交力道」分母使用
    vol_map = {}
    if df_price is not None and not df_price.empty and 'Volume' in df_price.columns:
        for idx_dt, r in df_price.iterrows():
            d_str = idx_dt.strftime('%Y-%m-%d') if hasattr(idx_dt, 'strftime') else str(idx_dt)[:10]
            vol_map[d_str] = max(1.0, float(r['Volume']) / 1000.0)

    net_series = df[target_col].astype(float)
    ratios = []
    for idx_d, val in net_series.items():
        d_key = str(idx_d)[:10]
        if denom_mode == '成交力道':
            v_lots = vol_map.get(d_key, max(100.0, abs(val) * 3.0))
            r_val = max(-1.0, min(1.0, val / v_lots))
        else:
            # 佔股本比（與圖一相同，以小數比率表示，例如 0.01 代表佔股本 1%）
            r_val = val / total_lots
        ratios.append(r_val)

    df['Force_Ratio'] = pd.Series(ratios, index=df.index)
    df['Force_Pct'] = (df['Force_Ratio'] * 100.0).round(3)
    df['Target_Lots'] = net_series

    # 3. 近期法人動向（白實線 Fast_MA）與 長期法人基準（白虛線 Slow_MA）
    df['Fast_MA'] = df['Force_Ratio'].rolling(fast_len, min_periods=2).mean()
    df['Slow_MA'] = df['Force_Ratio'].rolling(slow_len, min_periods=5).mean()

    # 4. 計算滾動 Z-Score 與「🟡 顯著買超（極端訊號）」
    roll_mean = df['Force_Ratio'].rolling(z_win, min_periods=5).mean()
    roll_std = df['Force_Ratio'].rolling(z_win, min_periods=5).std(ddof=0)
    overall_std = float(df['Force_Ratio'].std(ddof=0)) if len(df) > 1 else 0.001
    if overall_std <= 0:
        overall_std = 0.001
    roll_std = roll_std.replace(0, overall_std).fillna(overall_std)
    roll_mean = roll_mean.fillna(float(df['Force_Ratio'].mean()))

    df['Z_Score'] = ((df['Force_Ratio'] - roll_mean) / roll_std).round(2)

    # 判定極端訊號（🟡 大黃球：站買方 > 0，且 Z_Score >= sensitivity，且高於近期正值平均）
    pos_vals = df['Force_Ratio'][df['Force_Ratio'] > 0]
    min_pos_thresh = float(pos_vals.mean() * 0.8) if len(pos_vals) > 0 else 0.0005

    extreme_buy = []
    extreme_sell = []
    zero_state = []
    for _, r in df.iterrows():
        fr = float(r['Force_Ratio'])
        zs = float(r['Z_Score'])
        fma = float(r['Fast_MA']) if pd.notna(r['Fast_MA']) else 0.0
        sma = float(r['Slow_MA']) if pd.notna(r['Slow_MA']) else 0.0

        is_eb = (fr > max(0.0, min_pos_thresh)) and (zs >= sensitivity)
        is_es = (fr < 0.0) and (zs <= -sensitivity)
        extreme_buy.append(is_eb)
        extreme_sell.append(is_es)

        # 零軸轉強橫條狀態（如同圖一零軸上的橄欖黃/綠色小橫條）
        if fma > sma and fma > 0:
            zero_state.append('bull_strong')
        elif fma > sma:
            zero_state.append('bull_turn')
        else:
            zero_state.append('neutral')

    df['Extreme_Buy'] = extreme_buy
    df['Extreme_Sell'] = extreme_sell
    df['Zero_State'] = zero_state
    return df


def get_day_trading_analysis(code: str, df_price: pd.DataFrame = None, days: int = 40) -> dict:
    """
    取得個股當日沖銷（當沖）歷史數據與最新指標：
    - 當沖成交股數、當沖買進金額、當沖賣出金額
    - 與當日總成交量對比計算「當沖率 (Day Trading Ratio %)」
    - 近 5 日平均當沖率
    - 當沖籌碼熱度評級與操作解讀
    - 支援 1 小時本地快取
    """
    code = str(code).strip()
    cache_path = os.path.join(CACHE_DIR, f"day_trading_{code}.json")
    rows = None
    if os.path.exists(cache_path) and (time.time() - os.path.getmtime(cache_path) < 3600):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                rows = json.load(f)
        except Exception:
            rows = None

    if rows is None:
        try:
            start_d = (datetime.now() - timedelta(days=max(120, days * 2 + 30))).strftime('%Y-%m-%d')
            r = requests.get(FINMIND_URL, params={
                'dataset': 'TaiwanStockDayTrading',
                'data_id': code,
                'start_date': start_d
            }, timeout=8)
            rows = r.json().get('data', [])
            if rows:
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(rows, f, ensure_ascii=False)
        except Exception as e:
            print(f"FinMind day trading error for {code}: {e}")
            rows = []

    if not rows:
        return {'available': False, 'df': pd.DataFrame()}

    # 建立以日期字串為 key 的當沖字典
    dt_map = {r['date']: r for r in rows if 'date' in r}

    # 若沒有傳入 df_price，自行從 data_fetcher 抓
    if df_price is None or df_price.empty:
        try:
            from modules.data_fetcher import get_price_history
            df_price = get_price_history(code, period='6mo')
        except Exception:
            df_price = pd.DataFrame()

    if df_price is None or df_price.empty:
        return {'available': False, 'df': pd.DataFrame()}

    records = []
    for dt, row in df_price.iterrows():
        d_str = dt.strftime('%Y-%m-%d') if hasattr(dt, 'strftime') else str(dt)[:10]
        tot_vol = float(row.get('Volume', 0))
        tot_lots = round(tot_vol / 1000.0)
        dt_record = dt_map.get(d_str, {})
        dt_vol = float(dt_record.get('Volume', 0) or 0)
        dt_lots = round(dt_vol / 1000.0)
        buy_amt = float(dt_record.get('BuyAmount', 0) or 0)
        sell_amt = float(dt_record.get('SellAmount', 0) or 0)

        ratio = round((dt_vol / tot_vol * 100), 2) if tot_vol > 0 else 0.0

        records.append({
            'Date': dt,
            'DateStr': d_str,
            'Close': float(row.get('Close', 0)),
            'TotalLots': tot_lots,
            'DayTradingLots': dt_lots,
            'DayTradingRatio': ratio,
            'BuyAmtYi': round(buy_amt / 1e8, 2),
            'SellAmtYi': round(sell_amt / 1e8, 2),
        })

    res_df = pd.DataFrame(records)
    if res_df.empty:
        return {'available': False, 'df': pd.DataFrame()}

    res_df.set_index('Date', inplace=True)
    res_df = res_df.tail(days)

    latest_r = res_df.iloc[-1]
    latest_ratio = float(latest_r['DayTradingRatio'])
    latest_dt_lots = int(latest_r['DayTradingLots'])
    latest_tot_lots = int(latest_r['TotalLots'])
    latest_date = str(latest_r['DateStr'])
    buy_amt_yi = float(latest_r['BuyAmtYi'])
    sell_amt_yi = float(latest_r['SellAmtYi'])

    avg_5d = round(float(res_df['DayTradingRatio'].tail(5).mean()), 2)

    if latest_ratio >= 60.0:
        heat_level = '🚨 極高當沖 (警戒)'
        heat_color = '#FF5252'
        heat_desc = f'最新當沖率達 {latest_ratio:.1f}%，已超越 60% 警戒門檻！市場短線熱度爆表，大量隔日沖游資主力頻繁進出，盤中容易出現劇烈急拉或急殺，留倉風險偏高，操作需嚴格設定停損點。'
    elif latest_ratio >= 40.0:
        heat_level = '⚡ 當沖活躍 (熱門)'
        heat_color = '#FFA726'
        heat_desc = f'最新當沖率為 {latest_ratio:.1f}%，屬於熱門焦點股常態，交投熱絡且流動性極佳，但需留意早盤衝高後尾盤當沖籌碼調節的震盪洗盤。'
    elif latest_ratio >= 20.0:
        heat_level = '🌿 溫和健康 (常態)'
        heat_color = '#38BDF8'
        heat_desc = f'最新當沖率為 {latest_ratio:.1f}%，處於健康常態區間，兼具市場流動性且有實質波段買盤進駐，籌碼結構相對穩健。'
    elif latest_ratio > 0.0:
        heat_level = '🛡️ 低當沖 (安定)'
        heat_color = '#4ADE80'
        heat_desc = f'最新當沖率僅 {latest_ratio:.1f}%，短線當沖客極少參與，多為法人、大戶或長線實質投資人進駐，籌碼沉穩安定，不易受當沖雜音干擾。'
    else:
        heat_level = '⚪ 無當沖交易'
        heat_color = '#94A3B8'
        heat_desc = '當日無當沖交易紀錄或非現股當沖標的。'

    return {
        'available': True,
        'latest_date': latest_date,
        'latest_ratio': latest_ratio,
        'latest_dt_lots': latest_dt_lots,
        'latest_tot_lots': latest_tot_lots,
        'buy_amt_yi': buy_amt_yi,
        'sell_amt_yi': sell_amt_yi,
        'avg_5d_ratio': avg_5d,
        'heat_level': heat_level,
        'heat_color': heat_color,
        'heat_desc': heat_desc,
        'df': res_df
    }


