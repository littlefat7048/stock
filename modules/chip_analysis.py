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


def get_institutional_trend(code: str, days: int = 25) -> pd.DataFrame:
    """
    取得個股近 N 個交易日三大法人買賣超（單位：張）
    回傳欄位：['Foreign', 'Trust', 'Dealer', 'Total', '外資', '投信', '自營商', '三大法人合計']
    """
    code = str(code).strip()
    cache_path = os.path.join(CACHE_DIR, f"chip_inst_{code}.json")

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


def get_chip_score(data: pd.DataFrame) -> tuple:
    """
    計算籌碼面分數 0-100 與中文評級標籤
    回傳：(score: int, label: str)
    """
    if data is None or data.empty or '三大法人合計' not in data.columns:
        return 50, '⚪ 中性（無近期法人重大異動）'

    score = 50
    recent5 = data.tail(5)
    recent20 = data.tail(20)

    sum5_total = recent5['三大法人合計'].sum()
    sum5_foreign = recent5['外資'].sum()
    sum5_trust = recent5['投信'].sum()

    # 近5日三大法人合計買賣超
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
        score += 12
    elif sum5_trust > 0:
        score += 6
    elif sum5_trust < -100:
        score -= 10

    # 外資連買連賣天數
    f_streak = _calc_streak(data['外資'])
    if f_streak >= 3:
        score += 12
    elif f_streak <= -3:
        score -= 12

    # 近20日趨勢
    if recent20['三大法人合計'].sum() > 0:
        score += 5
    else:
        score -= 5

    score = max(10, min(95, score))

    if score >= 75:
        label = '🔴 法人大舉買進（籌碼極強）'
    elif score >= 60:
        label = '🟠 法人偏多操作（籌碼正向）'
    elif score >= 45:
        label = '⚪ 法人多空分歧（籌碼中性）'
    elif score >= 30:
        label = '🟢 法人調節賣出（籌碼偏弱）'
    else:
        label = '🟢 法人連續提款（籌碼弱勢）'

    return int(score), label


def get_chip_summary(inst_df: pd.DataFrame, margin_df: pd.DataFrame = None) -> dict:
    """
    產生完整的中文籌碼統計摘要（最新日、近5日、近20日、連買連賣天數）
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
