"""
技術指標與綜合診斷模組
使用純 Pandas + NumPy 計算，無需額外 C 擴充套件
所有訊號皆以「繁體中文」直白說明，並提供即時綜合買賣評價與建議價位
"""
import pandas as pd
import numpy as np


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    計算所有技術指標：MA5/10/20/60/120/240、MACD、RSI、KD、布林通道
    """
    if df is None or df.empty:
        return df

    close = df['Close']
    high  = df['High']
    low   = df['Low']

    for period in [5, 10, 20, 60, 120, 240]:
        df[f'MA{period}'] = _sma(close, period)

    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)
    df['MACD']        = ema12 - ema26
    df['MACD_signal'] = _ema(df['MACD'], 9)
    df['MACD_hist']   = df['MACD'] - df['MACD_signal']
    df['Signal']      = df['MACD_signal']
    df['Hist']        = df['MACD_hist']

    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_g = gain.ewm(com=13, adjust=False).mean()
    avg_l = loss.ewm(com=13, adjust=False).mean()
    rs    = avg_g / avg_l.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))

    low14  = low.rolling(14).min()
    high14 = high.rolling(14).max()
    rsv    = (close - low14) / (high14 - low14 + 1e-9) * 100
    df['KD_K'] = rsv.ewm(com=2, adjust=False).mean()
    df['KD_D'] = df['KD_K'].ewm(com=2, adjust=False).mean()
    df['K']    = df['KD_K']
    df['D']    = df['KD_D']

    df['BB_middle'] = _sma(close, 20)
    bb_std          = close.rolling(20).std()
    df['BB_upper']  = df['BB_middle'] + 2 * bb_std
    df['BB_lower']  = df['BB_middle'] - 2 * bb_std

    return df


# ── 全中文技術訊號判斷 ──────────────────────────────────────

def get_ma_trend(df: pd.DataFrame) -> str:
    """均線多/空排列判斷（全中文）"""
    if df is None or df.empty:
        return '⚪ 資料不足'
    last = df.iloc[-1]
    try:
        c = last['Close']
        m5, m10, m20, m60 = last['MA5'], last['MA10'], last['MA20'], last['MA60']
        if m5 > m10 > m20 > m60:
            return '🔴 多頭排列（短中長期均線全面向上）'
        if c > m20 and m5 > m20:
            return '🟠 短多格局（站穩月線 MA20 之上）'
        if m5 < m10 < m20 < m60:
            return '🟢 空頭排列（均線層層反壓向下）'
        if c < m20 and m5 < m20:
            return '🟢 短線偏弱（跌破月線 MA20）'
        return '⚖️ 均線糾結（區間盤整震盪）'
    except Exception:
        return '⚖️ 盤整震盪'


def get_macd_signal(df: pd.DataFrame) -> str:
    """MACD 訊號（全中文）"""
    if df is None or len(df) < 2:
        return '⚪ 中性'
    try:
        prev_hist = df['MACD_hist'].iloc[-2]
        curr_hist = df['MACD_hist'].iloc[-1]

        if prev_hist < 0 and curr_hist >= 0:
            return '🔴 黃金交叉（紅柱翻正，買訊浮現）'
        if prev_hist > 0 and curr_hist <= 0:
            return '🟢 死亡交叉（綠柱翻負，賣訊浮現）'
        if curr_hist > 0 and curr_hist >= prev_hist:
            return '🔴 多頭強勁（紅柱持續放大）'
        if curr_hist > 0:
            return '🟠 多方收斂（紅柱縮短，動能放緩）'
        if curr_hist < 0 and curr_hist <= prev_hist:
            return '🟢 空方增強（綠柱持續放大）'
        return '⚖️ 空方收斂（綠柱縮短，跌勢趨緩）'
    except Exception:
        return '⚪ 中性'


def get_rsi_signal(df: pd.DataFrame) -> str:
    """RSI 訊號（全中文）"""
    if df is None or df.empty or 'RSI' not in df.columns:
        return '⚪ 中性'
    try:
        rsi = float(df['RSI'].iloc[-1])
        if np.isnan(rsi):
            return '⚪ 中性'
        if rsi >= 75:
            return f'🔥 超買過熱（RSI={rsi:.1f}，短線留意拉回）'
        if rsi >= 55:
            return f'🔴 多方強勢（RSI={rsi:.1f}，買盤佔優）'
        if rsi >= 45:
            return f'⚖️ 多空均衡（RSI={rsi:.1f}，中性整理）'
        if rsi >= 25:
            return f'🟢 偏弱整理（RSI={rsi:.1f}，買氣較弱）'
        return f'❄️ 超賣低檔（RSI={rsi:.1f}，隨時醞釀反彈）'
    except Exception:
        return '⚪ 中性'


def get_kd_signal(df: pd.DataFrame) -> str:
    """KD 隨機指標訊號（全中文）"""
    if df is None or len(df) < 2:
        return '⚪ 中性'
    try:
        prev_k = float(df['KD_K'].iloc[-2])
        prev_d = float(df['KD_D'].iloc[-2])
        curr_k = float(df['KD_K'].iloc[-1])
        curr_d = float(df['KD_D'].iloc[-1])

        if prev_k < prev_d and curr_k >= curr_d:
            return f'🔴 黃金交叉（K={curr_k:.0f} 向上突破 D={curr_d:.0f}）'
        if prev_k > prev_d and curr_k <= curr_d:
            return f'🟢 死亡交叉（K={curr_k:.0f} 向下跌破 D={curr_d:.0f}）'
        if curr_k >= 80:
            return f'🔥 高檔鈍化/超買（K={curr_k:.0f}, D={curr_d:.0f}）'
        if curr_k <= 20:
            return f'❄️ 低檔超賣區（K={curr_k:.0f}, D={curr_d:.0f}）'
        if curr_k > curr_d:
            return f'🟠 KD 偏多向上（K={curr_k:.0f} > D={curr_d:.0f}）'
        return f'🟢 KD 偏空向下（K={curr_k:.0f} < D={curr_d:.0f}）'
    except Exception:
        return '⚪ 中性'


def get_technical_score(df: pd.DataFrame) -> tuple:
    """
    綜合技術評分 0-100，回傳 (score, label)
    台股慣例：紅色代表多頭強勢，綠色代表空頭弱勢
    """
    if df is None or df.empty:
        return 50, '⚪ 資料不足'

    score = 50
    last = df.iloc[-1]

    try:
        c = float(last['Close'])
        m5 = float(last['MA5'])
        m10 = float(last['MA10'])
        m20 = float(last['MA20'])
        m60 = float(last['MA60'])

        if c > m5:
            score += 6
        else:
            score -= 6
        if c > m20:
            score += 10
        else:
            score -= 10
        if c > m60:
            score += 8
        else:
            score -= 8
        if m5 > m10 > m20:
            score += 8
        elif m5 < m10 < m20:
            score -= 8
    except Exception:
        pass

    macd_sig = get_macd_signal(df)
    if '黃金交叉' in macd_sig or '多頭強勁' in macd_sig:
        score += 10
    elif '死亡交叉' in macd_sig or '空方增強' in macd_sig:
        score -= 10

    kd_sig = get_kd_signal(df)
    if '黃金交叉' in kd_sig or '偏多' in kd_sig or '高檔鈍化' in kd_sig:
        score += 8
    elif '死亡交叉' in kd_sig or '偏空' in kd_sig:
        score -= 8

    score = max(10, min(95, score))

    if score >= 75:
        label = '🔴 強勢多頭（技術面極強）'
    elif score >= 60:
        label = '🟠 偏多格局（多方佔優）'
    elif score >= 45:
        label = '⚪ 區間震盪（多空拉鋸）'
    elif score >= 30:
        label = '🟢 偏空格局（賣壓較重）'
    else:
        label = '🟢 弱勢空頭（跌勢未止）'

    return int(score), label


def find_support_resistance(df: pd.DataFrame, window: int = 20) -> dict:
    """
    計算支撐價位與壓力價位（結合近 20 日高低點、月線 MA20、季線 MA60 與布林通道）
    """
    if df is None or df.empty:
        return {'support': 0.0, 'resistance': 0.0}
    try:
        recent = df.tail(window)
        close = float(df['Close'].iloc[-1])
        low20 = float(recent['Low'].min())
        high20 = float(recent['High'].max())
        ma20 = float(df['MA20'].iloc[-1]) if 'MA20' in df.columns and not np.isnan(df['MA20'].iloc[-1]) else low20

        # 支撐取月線與近20日低點較合理者
        support = round(min(close * 0.96, max(low20, min(ma20, close * 0.97))), 2)
        resistance = round(max(high20, close * 1.05), 2)
        stop_loss = round(min(low20 * 0.98, support * 0.96), 2)

        return {
            'support': support,
            'buy_low': round(support * 0.99, 2),
            'buy_high': round(min(close, support * 1.02), 2),
            'resistance': resistance,
            'target_price': round(max(resistance, close * 1.10), 2),
            'stop_loss': stop_loss
        }
    except Exception:
        return {'support': 0.0, 'resistance': 0.0}


def generate_instant_diagnosis(
    df_price: pd.DataFrame,
    info: dict,
    chip_score: int,
    chip_summary: dict,
    financials: dict
) -> dict:
    """
    產生「秒開即看」的全中文綜合投資診斷（包含：買進/觀望/賣出、建議價位、優缺點分析）
    """
    tech_score, tech_label = get_technical_score(df_price)
    sr = find_support_resistance(df_price)
    close = float(df_price['Close'].iloc[-1]) if df_price is not None and not df_price.empty else 0.0

    # 綜合總分 = 技術面 45% + 籌碼面 35% + 基本面/財報 20%
    fund_score = 50
    strengths = []
    risks = []

    # 1. 技術面優缺點
    ma_txt = get_ma_trend(df_price)
    macd_txt = get_macd_signal(df_price)
    kd_txt = get_kd_signal(df_price)

    if '多頭排列' in ma_txt or '短多' in ma_txt:
        strengths.append(f"【技術面】{ma_txt}")
    elif '空頭' in ma_txt or '偏弱' in ma_txt:
        risks.append(f"【技術面】{ma_txt}")

    if '黃金交叉' in macd_txt or '多頭強勁' in macd_txt:
        strengths.append(f"【動能指標】MACD {macd_txt}")
    elif '死亡交叉' in macd_txt or '空方增強' in macd_txt:
        risks.append(f"【動能指標】MACD {macd_txt}")

    if '黃金交叉' in kd_txt:
        strengths.append(f"【短線轉折】KD {kd_txt}")
    elif '死亡交叉' in kd_txt:
        risks.append(f"【短線轉折】KD {kd_txt}")

    # 2. 籌碼面優缺點
    if chip_summary and chip_summary.get('available'):
        tot_5d = chip_summary.get('total_5d', 0)
        f_5d = chip_summary.get('foreign_5d', 0)
        t_5d = chip_summary.get('trust_5d', 0)
        if tot_5d > 0:
            strengths.append(f"【法人籌碼】近 5 日三大法人合計買超 {tot_5d:+,.0f} 張（外資 {f_5d:+,.0f} 張、投信 {t_5d:+,.0f} 張）")
        elif tot_5d < 0:
            risks.append(f"【法人籌碼】近 5 日三大法人合計賣超 {tot_5d:,.0f} 張（外資 {f_5d:+,.0f} 張、投信 {t_5d:+,.0f} 張）")

    # 3. 營收與財報優缺點
    if financials:
        m_rev = financials.get('monthly_revenue', [])
        if m_rev:
            latest_m = m_rev[-1]
            yoy = latest_m.get('YoY', 0)
            m_str = latest_m.get('Month', '')
            if yoy >= 20:
                fund_score += 20
                strengths.append(f"【營收爆發】最新 {m_str} 月營收年增率高達 +{yoy:.1f}%，成長動能強勁")
            elif yoy > 0:
                fund_score += 8
                strengths.append(f"【營收穩健】最新 {m_str} 月營收年增 +{yoy:.1f}%，維持正成長")
            elif yoy <= -15:
                fund_score -= 15
                risks.append(f"【營收衰退】最新 {m_str} 月營收年減 {yoy:.1f}%，基本面動能轉弱")

        q_eps = financials.get('quarterly_eps', [])
        if q_eps:
            latest_q = q_eps[-1]
            eps_val = latest_q.get('EPS', 0)
            gm_val = latest_q.get('毛利率(%)', 0)
            q_str = latest_q.get('Quarter', '')
            if eps_val > 0:
                fund_score += 10
                strengths.append(f"【獲利能力】{q_str} 單季 EPS {eps_val:.2f} 元（毛利率 {gm_val:.1f}%），具備實質獲利支撐")
            elif eps_val < 0:
                fund_score -= 15
                risks.append(f"【虧損警訊】{q_str} 單季 EPS 為 {eps_val:.2f} 元，尚處虧損階段")

    # 4. 估值優缺點
    pe = info.get('pe')
    div = info.get('dividend_yield')
    if pe:
        if 0 < pe <= 16:
            fund_score += 10
            strengths.append(f"【估值合理】目前本益比 {pe:.1f} 倍，處於相對低估安全區間")
        elif pe >= 50:
            risks.append(f"【估值偏高】目前本益比高達 {pe:.1f} 倍，股價已反映高成長預期，追價需謹慎")
    if div and div >= 0.04:
        strengths.append(f"【高殖利率】現金殖利率達 {div*100:.2f}%，具下檔防禦保護")

    if not strengths:
        strengths.append("【區間支撐】股價接近波段支撐位置，可觀察量能是否放大回穩")
    if not risks:
        risks.append("【大盤連動】留意台股大盤與國際科技股波動對個股短線的影響")

    total_score = int(round(tech_score * 0.45 + chip_score * 0.35 + max(10, min(95, fund_score)) * 0.20))

    if total_score >= 65:
        action = "買進 / 偏多佈局"
        badge_type = "buy"
        advice = f"目前綜合評分 {total_score} 分（偏多）。建議於支撐區 NT$ {sr.get('buy_low', 0):,.1f} ~ {sr.get('buy_high', 0):,.1f} 分批佈局，波段目標看 NT$ {sr.get('target_price', 0):,.1f}，跌破 NT$ {sr.get('stop_loss', 0):,.1f} 嚴設停損。"
    elif total_score >= 45:
        action = "等待 / 區間觀望"
        badge_type = "watch"
        advice = f"目前綜合評分 {total_score} 分（中性震盪）。短線不建議追高，宜等待回測支撐 NT$ {sr.get('support', 0):,.1f} 附近量縮止穩，或帶量突破壓力 NT$ {sr.get('resistance', 0):,.1f} 後再行進場。"
    else:
        action = "避開 / 逢高減碼"
        badge_type = "sell"
        advice = f"目前綜合評分 {total_score} 分（偏空弱勢）。均線或籌碼面仍有賣壓，建議暫時觀望避開，持有者若跌破支撐 NT$ {sr.get('support', 0):,.1f} 宜執行停損或減碼。"

    return {
        'total_score': total_score,
        'tech_score': tech_score,
        'chip_score': chip_score,
        'fund_score': max(10, min(95, fund_score)),
        'action': action,
        'badge_type': badge_type,
        'advice': advice,
        'buy_zone': f"NT$ {sr.get('buy_low', 0):,.1f} ~ {sr.get('buy_high', 0):,.1f}",
        'target_price': f"NT$ {sr.get('target_price', 0):,.1f}",
        'stop_loss': f"NT$ {sr.get('stop_loss', 0):,.1f}",
        'support': sr.get('support', 0),
        'resistance': sr.get('resistance', 0),
        'strengths': strengths,
        'risks': risks
    }
