"""
台股互動式圖表繪製模組 (Plotly 深色主題・手機零遮擋超大字版)
台股慣例：紅漲 (#e53935)、綠跌 (#43a047)
"""
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd

BG_COLOR = '#0E1117'
PLOT_BG_COLOR = '#1C2333'
FONT_COLOR = '#FAFAFA'
PRIMARY_COLOR = '#00D4AA'
UP_COLOR = '#e53935'
DOWN_COLOR = '#43a047'
GRID_COLOR = '#2A324B'


def _get_dt_rangebreaks(df_index):
    """
    計算所有非交易日（週末、國定假日、颱風休市），將其從 X 軸剔除，
    讓 K 線完全連續接續，絕不留下空白非交易日！
    """
    if df_index is None or len(df_index) < 2:
        return [dict(bounds=["sat", "mon"])]
    try:
        ts = pd.to_datetime(df_index)
        if getattr(ts, 'tz', None) is not None:
            ts = ts.tz_convert('Asia/Taipei').tz_localize(None)
        trading_days = set(ts.strftime('%Y-%m-%d'))
        full_range = pd.date_range(start=ts.min(), end=ts.max(), freq='D')
        missing = [d.strftime('%Y-%m-%d') for d in full_range if d.strftime('%Y-%m-%d') not in trading_days]
        if missing:
            return [dict(values=missing)]
        return [dict(bounds=["sat", "mon"])]
    except Exception:
        return [dict(bounds=["sat", "mon"])]


def _apply_dark_layout(fig, bottom_margin=100, top_margin=54, legend_y=-0.24, is_date_x=True, df_index=None):
    """
    統一深色主題佈局：
    1. 隱藏右上角懸浮工具列 (displayModeBar=False)，避免遮住右上角標題與K線（雙指縮放與連點還原仍完全保留）。
    2. 日期橫軸統一改為單行『MM/DD』(例如 09/06、09/20)，消除原本兩行英文『Sep 6 \\n 2026』向下撞到圖例的問題！
    3. 加大底部留白與圖例距離 (legend_y)，確保圖例在任何螢幕高度下都絕不與橫軸文字重疊。
    4. 自動剔除非交易日（週末與休市），K 線緊密相連無空白斷層！
    """
    layout_kwargs = dict(
        template='plotly_dark',
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=PLOT_BG_COLOR,
        font=dict(size=14.5, color=FONT_COLOR),
        margin=dict(l=10, r=14, t=top_margin, b=bottom_margin),
        dragmode=False,
        hovermode='closest',
        hoverlabel=dict(
            bgcolor='rgba(14, 17, 23, 0.92)',
            bordercolor='#38BDF8',
            font=dict(size=13.5, color='#FAFAFA'),
            namelength=0
        ),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=legend_y,
            xanchor="center",
            x=0.5,
            font=dict(size=13.5, color='#E2E8F0')
        )
    )
    if fig.layout.title and fig.layout.title.text:
        layout_kwargs['title'] = dict(
            text=fig.layout.title.text,
            y=0.96, x=0.01,
            xanchor='left', yanchor='top',
            font=dict(size=16.5, color='#FFD54F')
        )
    fig.update_layout(**layout_kwargs)
    xaxis_kwargs = dict(
        showgrid=True, gridwidth=1, gridcolor=GRID_COLOR,
        fixedrange=True,
        tickfont=dict(size=13),
        automargin=True
    )
    if is_date_x:
        xaxis_kwargs['tickformat'] = '%m/%d'
        if df_index is not None:
            xaxis_kwargs['rangebreaks'] = _get_dt_rangebreaks(df_index)

    fig.update_xaxes(**xaxis_kwargs)
    fig.update_yaxes(
        showgrid=True, gridwidth=1, gridcolor=GRID_COLOR,
        fixedrange=True,
        tickfont=dict(size=13),
        automargin=True
    )
    # 子圖標題 (subplot_titles) 靠左對齊並放大，避免置中偏右被擋
    if fig.layout.annotations:
        for ann in fig.layout.annotations:
            ann.font = dict(size=16, color='#FFD54F')
    return fig


def create_candlestick_chart(df, selected_mas=['MA5', 'MA20', 'MA60'], day_trading_df=None):
    """
    專業 K 線與成交量全連動圖表（還原專業看盤軟體十字查價線功能）：
    1. 上下全連動：點擊或懸停 K 線或成交量任一處，即刻同步顯示當日完整四價、漲跌、振幅、成交張數、5MA/20MA均量、當沖數據與各期均線數值。
    2. 十字查價線 (Crosshair)：金色虛線貫穿上下雙圖表，精準對齊同一交易日。
    3. 成交量附帶 5日均量線 (黃色) 與 20日均量線 (青色)。
    4. 支援當沖率 (Day Trading Ratio) 與當沖張數整合顯示。
    5. 自動剔除非交易日，K 線緊密相連。
    """
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=('📈 股價 K 線與均線走勢（紅漲綠跌・十字查價上下連動）', '📊 成交量（張）與 5MA / 20MA 均量走勢'),
        row_width=[0.28, 0.72]
    )

    # 成交量轉換為「張」（每張 = 1,000 股）
    vol_lots = [round(float(v) / 1000.0, 1) for v in df['Volume']]
    s_vol = pd.Series(vol_lots, index=df.index)
    vol_ma5 = s_vol.rolling(5).mean()
    vol_ma20 = s_vol.rolling(20).mean()

    # 建立當沖數據快速索引
    dt_map = {}
    if day_trading_df is not None and not day_trading_df.empty:
        for idx, r in day_trading_df.iterrows():
            d_key = r.get('DateStr') or (idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)[:10])
            dt_map[d_key] = (float(r.get('DayTradingLots', 0)), float(r.get('DayTradingRatio', 0.0)))

    # 1. 產生 K 線圖「上下全連動」懸浮卡片（涵蓋：四價、漲跌幅、振幅、成交張數、均量、均線、當沖）
    k_tooltips = []
    prev_close = None
    for idx_val, row in df.iterrows():
        o = float(row.get('Open', 0))
        h = float(row.get('High', 0))
        l = float(row.get('Low', 0))
        c = float(row.get('Close', 0))
        v = s_vol.loc[idx_val]
        v5 = vol_ma5.loc[idx_val]
        v20 = vol_ma20.loc[idx_val]

        base_p = prev_close if prev_close else o
        chg = c - base_p
        pct = (chg / base_p * 100) if base_p else 0.0
        c_color = UP_COLOR if chg >= 0 else DOWN_COLOR
        amp = ((h - l) / base_p * 100) if base_p else 0.0

        d_str = idx_val.strftime('%Y/%m/%d') if hasattr(idx_val, 'strftime') else str(idx_val)[:10]
        d_key = idx_val.strftime('%Y-%m-%d') if hasattr(idx_val, 'strftime') else str(idx_val)[:10]

        v5_str = f"{v5:,.0f} 張" if pd.notnull(v5) else "-"
        v20_str = f"{v20:,.0f} 張" if pd.notnull(v20) else "-"

        # 當沖資訊
        dt_line = ""
        if d_key in dt_map:
            dt_l, dt_r = dt_map[d_key]
            dt_color = '#FF5252' if dt_r >= 60 else '#FFA726' if dt_r >= 40 else '#38BDF8'
            dt_line = f"• 當沖量: <b>{dt_l:,.0f} 張</b> ｜ 當沖率: <b style='color:{dt_color};'>{dt_r:.1f}%</b><br>"

        # 均線資訊
        ma_parts = []
        ma_color_map = {'MA5': '#FFD700', 'MA10': '#FF80AB', 'MA20': '#00E5FF', 'MA60': '#FF9100', 'MA120': '#B388FF', 'MA240': '#69F0AE'}
        for ma in selected_mas:
            if ma in row and pd.notnull(row[ma]):
                m_color = ma_color_map.get(ma, '#FAFAFA')
                ma_parts.append(f"{ma}: <b style='color:{m_color};'>{row[ma]:,.2f}</b>")
        ma_line = " ｜ ".join(ma_parts) if ma_parts else "無"

        card = (
            f"📅 <b>{d_str}</b><br>"
            f"━━━━━━━━━━━━━━━━━━<br>"
            f"📈 <b>【股價四價與漲跌】</b><br>"
            f"• 開: <b>{o:,.2f}</b> ｜ 高: <b style='color:{UP_COLOR};'>{h:,.2f}</b><br>"
            f"• 低: <b style='color:{DOWN_COLOR};'>{l:,.2f}</b> ｜ 收: <b style='color:{c_color};'>{c:,.2f}</b><br>"
            f"• 漲跌: <b style='color:{c_color};'>{chg:+,.2f} ({pct:+.2f}%)</b> ｜ 振幅: <b>{amp:.2f}%</b><br>"
            f"━━━━━━━━━━━━━━━━━━<br>"
            f"📊 <b>【成交量能（上下連動）】</b><br>"
            f"• 成交量: <b style='color:#FFD700;'>{v:,.0f} 張</b><br>"
            f"• 5日均量: <b>{v5_str}</b> ｜ 20日均量: <b>{v20_str}</b><br>"
            f"{dt_line}"
            f"━━━━━━━━━━━━━━━━━━<br>"
            f"📏 <b>【均線位置】</b><br>"
            f"{ma_line}"
        )
        k_tooltips.append(card)
        prev_close = c

    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        increasing_line_color=UP_COLOR, increasing_fillcolor=UP_COLOR,
        decreasing_line_color=DOWN_COLOR, decreasing_fillcolor=DOWN_COLOR,
        name='K線',
        text=k_tooltips,
        hoverinfo='text'
    ), row=1, col=1)

    ma_colors = {
        'MA5': '#FFD700',
        'MA10': '#FF80AB',
        'MA20': '#00E5FF',
        'MA60': '#FF9100',
        'MA120': '#B388FF',
        'MA240': '#69F0AE'
    }
    for ma in selected_mas:
        if ma in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[ma],
                line=dict(color=ma_colors.get(ma, '#FFFFFF'), width=1.8),
                name=ma,
                hoverinfo='skip'
            ), row=1, col=1)

    # 2. 產生成交量「上下全連動」懸浮卡片（點成交量也同樣完整呈現股價與量能）
    vol_tooltips = []
    prev_close = None
    for idx_val, row in df.iterrows():
        o = float(row.get('Open', 0))
        h = float(row.get('High', 0))
        l = float(row.get('Low', 0))
        c = float(row.get('Close', 0))
        v = s_vol.loc[idx_val]
        v5 = vol_ma5.loc[idx_val]
        v20 = vol_ma20.loc[idx_val]

        base_p = prev_close if prev_close else o
        chg = c - base_p
        pct = (chg / base_p * 100) if base_p else 0.0
        c_color = UP_COLOR if chg >= 0 else DOWN_COLOR
        amp = ((h - l) / base_p * 100) if base_p else 0.0

        d_str = idx_val.strftime('%Y/%m/%d') if hasattr(idx_val, 'strftime') else str(idx_val)[:10]
        d_key = idx_val.strftime('%Y-%m-%d') if hasattr(idx_val, 'strftime') else str(idx_val)[:10]

        v5_str = f"{v5:,.0f} 張" if pd.notnull(v5) else "-"
        v20_str = f"{v20:,.0f} 張" if pd.notnull(v20) else "-"

        dt_line = ""
        if d_key in dt_map:
            dt_l, dt_r = dt_map[d_key]
            dt_color = '#FF5252' if dt_r >= 60 else '#FFA726' if dt_r >= 40 else '#38BDF8'
            dt_line = f"• 當沖量: <b>{dt_l:,.0f} 張</b> ｜ 當沖率: <b style='color:{dt_color};'>{dt_r:.1f}%</b><br>"

        ma_parts = []
        ma_color_map = {'MA5': '#FFD700', 'MA10': '#FF80AB', 'MA20': '#00E5FF', 'MA60': '#FF9100', 'MA120': '#B388FF', 'MA240': '#69F0AE'}
        for ma in selected_mas:
            if ma in row and pd.notnull(row[ma]):
                m_color = ma_color_map.get(ma, '#FAFAFA')
                ma_parts.append(f"{ma}: <b style='color:{m_color};'>{row[ma]:,.2f}</b>")
        ma_line = " ｜ ".join(ma_parts) if ma_parts else "無"

        card = (
            f"📅 <b>{d_str}</b><br>"
            f"━━━━━━━━━━━━━━━━━━<br>"
            f"📊 <b>【成交量能明細】</b><br>"
            f"• 成交量: <b style='color:#FFD700;'>{v:,.0f} 張</b><br>"
            f"• 5日均量: <b>{v5_str}</b> ｜ 20日均量: <b>{v20_str}</b><br>"
            f"{dt_line}"
            f"━━━━━━━━━━━━━━━━━━<br>"
            f"📈 <b>【對應股價（上下連動）】</b><br>"
            f"• 收盤價: <b style='color:{c_color};'>{c:,.2f} ({chg:+,.2f} / {pct:+.2f}%)</b><br>"
            f"• 開: {o:,.2f} ｜ 高: {h:,.2f} ｜ 低: {l:,.2f} ｜ 振幅: {amp:.2f}%<br>"
            f"━━━━━━━━━━━━━━━━━━<br>"
            f"📏 <b>【均線位置】</b><br>"
            f"{ma_line}"
        )
        vol_tooltips.append(card)
        prev_close = c

    volume_colors = [UP_COLOR if row['Close'] >= row['Open'] else DOWN_COLOR for _, row in df.iterrows()]
    fig.add_trace(go.Bar(
        x=df.index, y=vol_lots,
        marker_color=volume_colors,
        name='成交量(張)',
        text=vol_tooltips,
        hoverinfo='text'
    ), row=2, col=1)

    # 5日與20日均量線
    fig.add_trace(go.Scatter(
        x=df.index, y=vol_ma5,
        line=dict(color='#FFD700', width=1.6),
        name='5日均量',
        hoverinfo='skip'
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=df.index, y=vol_ma20,
        line=dict(color='#00E5FF', width=1.6),
        name='20日均量',
        hoverinfo='skip'
    ), row=2, col=1)

    fig.update_layout(xaxis_rangeslider_visible=False, height=660)
    fig = _apply_dark_layout(fig, bottom_margin=96, top_margin=44, legend_y=-0.16, is_date_x=True, df_index=df.index)

    # 覆蓋深色主題的 hoverlabel 與 十字查價線 (Spikelines)
    fig.update_layout(
        hovermode='x',
        hoverlabel=dict(
            bgcolor='rgba(15, 23, 42, 0.96)',
            bordercolor='#FFD700',
            font=dict(size=14, color='#F8FAFC'),
            align='left'
        )
    )
    fig.update_xaxes(
        showspikes=True,
        spikemode='across',
        spikesnap='cursor',
        spikethickness=1.4,
        spikecolor='#FFD700',
        spikedash='dash'
    )
    fig.update_yaxes(
        showspikes=True,
        spikemode='across',
        spikesnap='cursor',
        spikethickness=1.0,
        spikecolor='rgba(255, 215, 0, 0.45)',
        spikedash='dot'
    )
    return fig


def create_macd_chart(df):
    fig = go.Figure()
    if 'MACD' in df.columns and 'Signal' in df.columns and 'Hist' in df.columns:
        colors = [UP_COLOR if h >= 0 else DOWN_COLOR for h in df['Hist']]
        fig.add_trace(go.Bar(
            x=df.index, y=df['Hist'], marker_color=colors, name='柱狀(OSC)',
            hovertemplate="%{x|%m/%d}｜柱狀(OSC): <b>%{y:+.2f}</b><extra></extra>"
        ))
        fig.add_trace(go.Scatter(
            x=df.index, y=df['MACD'], line=dict(color='#00E5FF', width=2.0), name='DIF快線',
            hovertemplate="%{x|%m/%d}｜DIF: <b>%{y:.2f}</b><extra></extra>"
        ))
        fig.add_trace(go.Scatter(
            x=df.index, y=df['Signal'], line=dict(color='#FF80AB', width=2.0), name='MACD慢線',
            hovertemplate="%{x|%m/%d}｜MACD: <b>%{y:.2f}</b><extra></extra>"
        ))
    fig.update_layout(height=350, title_text='MACD 動能指標')
    return _apply_dark_layout(fig, bottom_margin=98, top_margin=50, legend_y=-0.28, is_date_x=True, df_index=df.index)


def create_kd_chart(df):
    fig = go.Figure()
    if 'K' in df.columns and 'D' in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df['K'], line=dict(color='#FFD700', width=2.0), name='K值(快線)',
            hovertemplate="%{x|%m/%d}｜K值: <b>%{y:.1f}</b><extra></extra>"
        ))
        fig.add_trace(go.Scatter(
            x=df.index, y=df['D'], line=dict(color='#00E5FF', width=2.0), name='D值(慢線)',
            hovertemplate="%{x|%m/%d}｜D值: <b>%{y:.1f}</b><extra></extra>"
        ))
        fig.add_hline(y=80, line_dash="dash", line_color=UP_COLOR)
        fig.add_hline(y=20, line_dash="dash", line_color=DOWN_COLOR)
    fig.update_layout(height=350, title_text='KD 隨機指標（80超買 / 20超賣）')
    return _apply_dark_layout(fig, bottom_margin=98, top_margin=50, legend_y=-0.28, is_date_x=True, df_index=df.index)


def create_rsi_chart(df):
    fig = go.Figure()
    if 'RSI' in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df['RSI'], line=dict(color=PRIMARY_COLOR, width=2.2), name='RSI(14)',
            hovertemplate="%{x|%m/%d}｜RSI: <b>%{y:.1f}</b><extra></extra>"
        ))
        fig.add_hline(y=70, line_dash="dash", line_color=UP_COLOR)
        fig.add_hline(y=50, line_dash="dot", line_color="#888888")
        fig.add_hline(y=30, line_dash="dash", line_color=DOWN_COLOR)
    fig.update_layout(height=350, title_text='RSI 相對強弱指標（70超買 / 30超賣）')
    return _apply_dark_layout(fig, bottom_margin=98, top_margin=50, legend_y=-0.28, is_date_x=True, df_index=df.index)


def create_institutional_chart(data, days=25):
    """三大法人每日買賣超柱狀圖（單位：張）"""
    fig = go.Figure()
    if data is None or data.empty:
        return _apply_dark_layout(fig)

    series_cfg = [
        ('外資', '#38BDF8'),
        ('投信', '#FBBF24'),
        ('自營商', '#C084FC')
    ]
    for col, color in series_cfg:
        if col in data.columns:
            fig.add_trace(go.Bar(
                x=data.index, y=data[col],
                name=col, marker_color=color,
                hovertemplate=f"%{{x|%m/%d}}｜{col}: <b>%{{y:+,.0f}} 張</b><extra></extra>"
            ))

    if '三大法人合計' in data.columns:
        fig.add_trace(go.Scatter(
            x=data.index, y=data['三大法人合計'],
            mode='lines+markers',
            line=dict(color='#FF5252', width=2.2),
            name='合計(張)',
            hovertemplate="%{x|%m/%d}｜三大法人合計: <b>%{y:+,.0f} 張</b><extra></extra>"
        ))

    fig.add_hline(y=0, line_color='#FFFFFF', line_width=1)
    fig.update_layout(barmode='relative', height=430, title_text='三大法人每日買賣超明細（單位：張）')
    return _apply_dark_layout(fig, bottom_margin=102, top_margin=52, legend_y=-0.25, is_date_x=True, df_index=data.index)


def create_mofi_institutional_force_chart(mofi_df, investor_type='三大法人', denom_mode='佔股本比', sensitivity=2.0):
    """
    繪製仿 @MOFI「法人力度 (2026 版)」專業副圖：
    - 縱軸直接顯示百分比 (%)（例如 +2.0% 代表單日買超佔總股本 2%），直覺好懂！
    - 橫軸日期單行顯示 (MM/DD)，圖例與橫軸留有充足間距，絕不重疊遮字！
    """
    fig = go.Figure()
    if mofi_df is None or mofi_df.empty or 'Force_Pct' not in mofi_df.columns:
        return _apply_dark_layout(fig)

    bar_colors = []
    for _, r in mofi_df.iterrows():
        v = float(r['Force_Pct'])
        if r.get('Extreme_Buy'):
            bar_colors.append('#FF2A2A')  # 極端顯著買超：高亮紅
        elif v > 0:
            bar_colors.append('#B71C1C')  # 一般買超：暗紅
        elif r.get('Extreme_Sell'):
            bar_colors.append('#00E676')  # 極端賣超：亮綠
        else:
            bar_colors.append('#2E7D32')  # 一般賣超：暗綠

    sub_label = "（投本比）" if (investor_type == '投信' and denom_mode == '佔股本比') else ""
    fig.add_trace(go.Bar(
        x=mofi_df.index,
        y=mofi_df['Force_Pct'],
        marker_color=bar_colors,
        name=f'{investor_type}(%)',
        customdata=mofi_df[['Target_Lots', 'Force_Pct', 'Z_Score']],
        hovertemplate=(
            "<b>%{x|%m/%d}</b>｜"
            f"{investor_type} <b>%{{customdata[0]:+,.0f}}張</b><br>"
            f"{denom_mode} <b>%{{customdata[1]:+.2f}}%</b> (Z=<b>%{{customdata[2]:+.2f}}σ</b>)<extra></extra>"
        )
    ))

    # 白色虛線：長期法人基準 (Slow_MA 轉百分比)
    if 'Slow_MA' in mofi_df.columns:
        fig.add_trace(go.Scatter(
            x=mofi_df.index,
            y=mofi_df['Slow_MA'] * 100.0,
            mode='lines',
            line=dict(color='#CBD5E1', width=1.6, dash='dash'),
            name='40MA基準',
            hoverinfo='skip'
        ))

    # 白色實線：近期法人動向 (Fast_MA 轉百分比)
    if 'Fast_MA' in mofi_df.columns:
        fig.add_trace(go.Scatter(
            x=mofi_df.index,
            y=mofi_df['Fast_MA'] * 100.0,
            mode='lines',
            line=dict(color='#FFFFFF', width=2.4),
            name='10MA動向',
            hoverinfo='skip'
        ))

    # 零軸上的買方轉強色塊（對應圖一零軸上的橄欖金/綠色橫條）
    bull_strong_df = mofi_df[mofi_df['Zero_State'] == 'bull_strong']
    bull_turn_df = mofi_df[mofi_df['Zero_State'] == 'bull_turn']
    if not bull_turn_df.empty:
        fig.add_trace(go.Scatter(
            x=bull_turn_df.index,
            y=[0.0] * len(bull_turn_df),
            mode='markers',
            marker=dict(symbol='square', size=7, color='#9E9D24'),
            name='翻多',
            hoverinfo='skip'
        ))
    if not bull_strong_df.empty:
        fig.add_trace(go.Scatter(
            x=bull_strong_df.index,
            y=[0.0] * len(bull_strong_df),
            mode='markers',
            marker=dict(symbol='square', size=7, color='#00C853'),
            name='買強',
            hoverinfo='skip'
        ))

    # 🟡 大黃球：顯著買超（極端訊號）
    eb_df = mofi_df[mofi_df['Extreme_Buy'] == True]
    if not eb_df.empty:
        fig.add_trace(go.Scatter(
            x=eb_df.index,
            y=eb_df['Force_Pct'] * 0.85,
            mode='markers',
            marker=dict(
                symbol='circle',
                size=16,
                color='#FFEA00',
                line=dict(color='#FFF9C4', width=2)
            ),
            name='顯著買超',
            customdata=eb_df[['Target_Lots', 'Force_Pct', 'Z_Score']],
            hovertemplate=(
                "🟡 <b>%{x|%m/%d} 顯著買超！</b><br>"
                "買超 <b>%{customdata[0]:+,.0f}張</b>｜"
                f"{denom_mode} <b>%{{customdata[1]:+.2f}}%</b> (<b>%{{customdata[2]:+.2f}}σ</b>)<extra></extra>"
            )
        ))

    fig.add_hline(y=0, line_color='#64748B', line_width=1, line_dash='dot')
    title_str = f"法人力度 (2026 版)｜{investor_type} × {denom_mode}{sub_label}"
    fig.update_layout(height=410, title_text=title_str)
    fig = _apply_dark_layout(fig, bottom_margin=100, top_margin=52, legend_y=-0.22, is_date_x=True, df_index=mofi_df.index)
    fig.update_layout(
        yaxis=dict(side='right', ticksuffix='%', fixedrange=True, gridcolor=GRID_COLOR, tickfont=dict(size=13)),
        plot_bgcolor='#080B10',
        paper_bgcolor='#0E1117'
    )
    return fig


def create_margin_chart(data):
    """融資餘額與融券餘額雙軸走勢圖"""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if data is not None and not data.empty:
        if 'MarginLong' in data.columns:
            fig.add_trace(go.Scatter(
                x=data.index, y=data['MarginLong'],
                name='融資餘額(左軸:張)',
                line=dict(color='#FF80AB', width=2.4),
                fill='tozeroy', fillcolor='rgba(255,128,171,0.1)',
                hovertemplate="%{x|%m/%d}｜融資餘額: <b>%{y:,.0f} 張</b><extra></extra>"
            ), secondary_y=False)
        if 'MarginShort' in data.columns:
            fig.add_trace(go.Scatter(
                x=data.index, y=data['MarginShort'],
                name='融券餘額(右軸:張)',
                line=dict(color='#00E5FF', width=2.4),
                hovertemplate="%{x|%m/%d}｜融券餘額: <b>%{y:,.0f} 張</b><extra></extra>"
            ), secondary_y=True)

    fig.update_layout(height=420, title_text='融資與融券餘額趨勢（單位：張）')
    return _apply_dark_layout(fig, bottom_margin=102, top_margin=52, legend_y=-0.25, is_date_x=True, df_index=data.index)


def create_eps_chart(quarterly_df):
    """單季 EPS 與三率（毛利率/營益率/淨利率）雙圖表（防遮字優化版）"""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if quarterly_df is not None and not quarterly_df.empty:
        colors = [UP_COLOR if v >= 0 else DOWN_COLOR for v in quarterly_df['EPS']]
        fig.add_trace(go.Bar(
            x=quarterly_df['Quarter'], y=quarterly_df['EPS'],
            marker_color=colors, name='單季EPS(元)',
            hovertemplate="<b>%{x}</b>｜單季EPS: <b>%{y:.2f} 元</b><extra></extra>"
        ), secondary_y=False)

        for rate_col, short_name, color in [
            ('毛利率(%)', '毛利率(%)', '#FFD700'),
            ('營益率(%)', '營益率(%)', '#00E5FF'),
            ('淨利率(%)', '淨利率(%)', '#C084FC')
        ]:
            if rate_col in quarterly_df.columns:
                fig.add_trace(go.Scatter(
                    x=quarterly_df['Quarter'], y=quarterly_df[rate_col],
                    mode='lines+markers',
                    line=dict(color=color, width=2.4),
                    marker=dict(size=7),
                    name=short_name,
                    hovertemplate=f"<b>%{{x}}</b>｜{short_name}: <b>%{{y:.2f}}%</b><extra></extra>"
                ), secondary_y=True)

    fig.update_xaxes(tickangle=-25, tickfont=dict(size=13.5))
    fig.update_yaxes(secondary_y=False, tickfont=dict(size=13))
    fig.update_yaxes(secondary_y=True, ticksuffix="%", tickfont=dict(size=13))
    fig.update_layout(height=440, title_text='季度 EPS(柱) 與 獲利三率(線) 走勢')
    return _apply_dark_layout(fig, bottom_margin=106, top_margin=52, legend_y=-0.26, is_date_x=False)


def create_revenue_chart(monthly_revenue):
    """月營收與年增率 YoY 走勢圖（防遮字與防X軸截斷優化版）"""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if monthly_revenue is not None and not monthly_revenue.empty:
        short_months = [str(m)[2:] if len(str(m)) >= 7 and str(m).startswith('20') else str(m) for m in monthly_revenue['Month']]
        fig.add_trace(go.Bar(
            x=short_months, y=monthly_revenue['Revenue'],
            marker_color=PRIMARY_COLOR, name='月營收(億)',
            hovertemplate="<b>%{x}</b>｜月營收: <b>%{y:.2f} 億元</b><extra></extra>"
        ), secondary_y=False)

        if 'YoY' in monthly_revenue.columns:
            fig.add_trace(go.Scatter(
                x=short_months, y=monthly_revenue['YoY'],
                mode='lines+markers',
                line=dict(color='#FFD700', width=2.4),
                marker=dict(size=7),
                name='年增YoY(%)',
                hovertemplate="<b>%{x}</b>｜年增率YoY: <b>%{y:+.2f}%</b><extra></extra>"
            ), secondary_y=True)
        if 'MoM' in monthly_revenue.columns:
            fig.add_trace(go.Scatter(
                x=short_months, y=monthly_revenue['MoM'],
                mode='lines+markers',
                line=dict(color='#FF80AB', width=1.8, dash='dot'),
                marker=dict(size=6),
                name='月增MoM(%)',
                hovertemplate="<b>%{x}</b>｜月增率MoM: <b>%{y:+.2f}%</b><extra></extra>"
            ), secondary_y=True)

    fig.update_xaxes(tickangle=-35, tickfont=dict(size=13))
    fig.update_yaxes(secondary_y=False, tickfont=dict(size=13))
    fig.update_yaxes(secondary_y=True, ticksuffix="%", tickfont=dict(size=13))
    fig.update_layout(height=440, title_text='近 12 個月營收(柱) 與 年增率 YoY(線)')
    return _apply_dark_layout(fig, bottom_margin=106, top_margin=52, legend_y=-0.27, is_date_x=False)


def create_day_trading_chart(day_trading_df):
    """
    當日沖銷（當沖）雙軸走勢圖：
    - 主軸（左軸/柱狀）：總成交量(張) 與 當沖成交量(張)
    - 副軸（右軸/折線）：當沖率 (%)，含 50% 警戒虛線
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if day_trading_df is None or day_trading_df.empty:
        return _apply_dark_layout(fig)

    x_vals = day_trading_df.index
    tot_lots = day_trading_df['TotalLots']
    dt_lots = day_trading_df['DayTradingLots']
    dt_ratios = day_trading_df['DayTradingRatio']

    # 1. 總成交量柱狀圖（暗灰藍底柱）
    fig.add_trace(go.Bar(
        x=x_vals, y=tot_lots,
        name='總成交量(張)',
        marker_color='#334155',
        hovertemplate="%{x|%m/%d}｜總成交量: <b>%{y:,.0f} 張</b><extra></extra>"
    ), secondary_y=False)

    # 2. 當沖成交量柱狀圖（亮橘色疊加柱）
    fig.add_trace(go.Bar(
        x=x_vals, y=dt_lots,
        name='當沖成交量(張)',
        marker_color='#FB923C',
        hovertemplate="%{x|%m/%d}｜當沖量: <b>%{y:,.0f} 張</b><extra></extra>"
    ), secondary_y=False)

    # 3. 當沖率折線圖（霓虹青色折線帶金黃點）
    fig.add_trace(go.Scatter(
        x=x_vals, y=dt_ratios,
        mode='lines+markers',
        line=dict(color='#00E5FF', width=2.6),
        marker=dict(size=7, color='#FFD700'),
        name='當沖率(%)',
        hovertemplate="%{x|%m/%d}｜當沖率: <b>%{y:.2f}%</b><extra></extra>"
    ), secondary_y=True)

    # 50% 當沖警戒虛線
    fig.add_hline(y=50, line_dash="dash", line_color="#FF5252", line_width=1.5,
                  annotation_text="50% 當沖熱度警戒線", annotation_position="top left",
                  annotation_font=dict(color="#FF5252", size=12),
                  secondary_y=True)

    fig.update_layout(
        barmode='overlay',
        height=420,
        title_text='當日沖銷成交量(張) 與 當沖率(%) 歷史走勢'
    )
    fig.update_yaxes(title_text='成交量(張)', secondary_y=False, tickfont=dict(size=13))
    fig.update_yaxes(title_text='當沖率(%)', ticksuffix='%', secondary_y=True, tickfont=dict(size=13))
    return _apply_dark_layout(fig, bottom_margin=102, top_margin=52, legend_y=-0.25, is_date_x=True, df_index=day_trading_df.index)


def create_intraday_footprint_chart(df_m: pd.DataFrame, broker_name: str = None, buy_price: float = 0.0, sell_price: float = 0.0, footprint: list = None, show_vwap: bool = True, show_footprint: bool = True, *args, **kwargs):
    """
    隔日沖手法研究：分時走勢與主力分點足跡圖（精準還原 10:33 圖一）
    1. 上方子圖：
       - 股價分時折線（紅色 #EF4444）
       - 市場均價線 VWAP（白色虛線 #CBD5E1）
       - 分點階梯帶（Stepped Shelves）與 ▲▼ 三角形標記
       - 參考價格標籤（如 參考 405.50）與高低點數值標記
    2. 下方子圖：
       - 盤中 1 分鐘成交量琥珀橘柱（張）
    3. 全貫穿十字查價線
    """
    if df_m is None or df_m.empty:
        fig = go.Figure()
        fig.update_layout(title="無分時資料", template='plotly_dark')
        return fig

    BG_COLOR = '#111215'
    PLOT_BG = '#15161A'
    GRID_COLOR = '#21232B'

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.06,
        row_width=[0.24, 0.76]
    )

    # 1. 市場均價線 (VWAP)
    if show_vwap and 'VWAP' in df_m.columns:
        fig.add_trace(go.Scatter(
            x=df_m.index, y=df_m['VWAP'],
            mode='lines',
            line=dict(color='#CBD5E1', width=1.5, dash='dash'),
            name='市場均價',
            hoverinfo='skip'
        ), row=1, col=1)

    # 2. 股價分時折線
    price_tooltips = []
    first_p = df_m['Open'].iloc[0]
    for dt, row in df_m.iterrows():
        c = row['Close']
        v = row['Vol_Lots']
        vw = row['VWAP']
        chg = c - first_p
        pct = (chg / first_p * 100) if first_p else 0.0
        time_str = dt.strftime('%H:%M')
        txt = (
            f"⏰ <b>{time_str}</b><br>"
            f"━━━━━━━━━━━━━━━━━━<br>"
            f"• 股價: <b style='color:#EF4444;'>{c:,.2f}</b> ({chg:+,.2f} / {pct:+.2f}%)<br>"
            f"• 市場均價(VWAP): <b>{vw:,.2f}</b><br>"
            f"• 分時量: <b>{v:,.0f} 張</b>"
        )
        price_tooltips.append(txt)

    fig.add_trace(go.Scatter(
        x=df_m.index, y=df_m['Close'],
        mode='lines',
        line=dict(color='#FF3344', width=2.5),
        name='股價',
        text=price_tooltips,
        hoverinfo='text'
    ), row=1, col=1)

    # 3. 主力進出場階梯色帶與 ▲▼ 三角形（還原圖一）
    if show_footprint and footprint:
        # 若傳入的是 list (shelves)，逐一繪製
        shelves_list = footprint if isinstance(footprint, list) else (footprint.get('buy_segments', []) + footprint.get('sell_segments', []))
        for sh in shelves_list:
            t_s = sh.get('start')
            t_e = sh.get('end')
            p_sh = sh.get('shelf_price') or sh.get('price', 0.0)
            is_buy = sh.get('is_buy', True)
            n_arrows = sh.get('arrow_count', 3)
            min_p = sh.get('min_p', p_sh * 0.99)
            max_p = sh.get('max_p', p_sh * 1.01)

            fill_col = 'rgba(239, 68, 68, 0.36)' if is_buy else 'rgba(0, 230, 118, 0.35)'
            line_col = '#FF2D55' if is_buy else '#00E676'
            arrow_sym = '▲' if is_buy else '▼'

            # 階梯水平線（加粗高對比）
            fig.add_shape(
                type='line',
                x0=t_s, x1=t_e, y0=p_sh, y1=p_sh,
                line=dict(color=line_col, width=2.8),
                row=1, col=1
            )
            # 填色塊（鮮明緊湊）
            fig.add_shape(
                type='rect',
                x0=t_s, x1=t_e, y0=min_p, y1=max_p,
                fillcolor=fill_col,
                line=dict(width=0),
                layer='below',
                row=1, col=1
            )

            # 三角形標籤（清晰大尺寸）
            sub_slice = df_m.loc[t_s:t_e]
            if len(sub_slice) > 0:
                step_idx = max(1, len(sub_slice) // (n_arrows + 1))
                for a_i in range(1, n_arrows + 1):
                    idx_pt = min(len(sub_slice) - 1, a_i * step_idx)
                    pt_x = sub_slice.index[idx_pt]
                    fig.add_annotation(
                        x=pt_x, y=p_sh,
                        text=arrow_sym,
                        showarrow=False,
                        font=dict(color=line_col, size=15),
                        yshift=10 if is_buy else -10,
                        row=1, col=1
                    )

    # 4. 參考價格與高低點標記（還原圖一）
    ref_p = round(float(df_m['Open'].iloc[0]) * 0.982, 2)
    fig.add_annotation(
        x=df_m.index[-1], y=ref_p,
        text=f"參考 {ref_p:,.2f}",
        showarrow=False,
        font=dict(color="#64748B", size=11),
        xshift=-35, yshift=-8,
        row=1, col=1
    )

    lo_val = float(df_m['Low'].min())
    lo_idx = df_m['Low'].idxmin()
    fig.add_annotation(
        x=lo_idx, y=lo_val,
        text=f"{lo_val:,.2f}",
        showarrow=False,
        font=dict(color="#94A3B8", size=11),
        yshift=-12,
        row=1, col=1
    )

    hi_val = float(df_m['High'].max())
    hi_idx = df_m['High'].idxmax()
    fig.add_annotation(
        x=hi_idx, y=hi_val,
        text=f"{hi_val:,.2f}",
        showarrow=False,
        font=dict(color="#22C55E", size=11),
        yshift=12,
        row=1, col=1
    )

    last_c = float(df_m['Close'].iloc[-1])
    fig.add_annotation(
        x=df_m.index[-1], y=last_c,
        text=f"{last_c:,.2f}",
        showarrow=False,
        font=dict(color="#EF4444", size=11),
        xshift=-25, yshift=12,
        row=1, col=1
    )

    # 5. 下方分時成交量柱狀圖（琥珀橘柱）
    fig.add_trace(go.Bar(
        x=df_m.index, y=df_m['Vol_Lots'],
        marker_color='#F59E0B',
        name='市場分時量',
        hovertemplate="%{x|%H:%M}｜量: <b>%{y:,.0f} 張</b><extra></extra>"
    ), row=2, col=1)

    # 下方子圖左上方成交量註解（完全還原圖一）
    vol_sum = df_m['Vol_Lots'].sum()
    fig.add_annotation(
        x=df_m.index[2], y=1.0,
        xref='x2', yref='y2 domain',
        text=f"成交量 {vol_sum:,.0f} 張 · 市場分時量",
        showarrow=False,
        font=dict(color="#94A3B8", size=11),
        xanchor='left', yanchor='top',
        row=2, col=1
    )

    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=PLOT_BG,
        height=580,
        margin=dict(l=10, r=16, t=20, b=30),
        dragmode=False,
        hovermode='x',
        showlegend=False
    )

    fig.update_xaxes(
        showgrid=True, gridwidth=1, gridcolor=GRID_COLOR,
        fixedrange=True,
        showspikes=True, spikemode='across', spikesnap='cursor',
        spikethickness=1.2, spikecolor='#F59E0B', spikedash='dash',
        tickformat='%H:%M',
        automargin=True
    )
    fig.update_yaxes(
        showgrid=True, gridwidth=1, gridcolor=GRID_COLOR,
        fixedrange=True,
        automargin=True,
        title=dict(text="元", font=dict(color="#94A3B8", size=12)),
        row=1, col=1
    )
    fig.update_yaxes(
        showgrid=True, gridwidth=1, gridcolor=GRID_COLOR,
        showticklabels=False,
        fixedrange=True,
        automargin=True,
        row=2, col=1
    )
    return fig

