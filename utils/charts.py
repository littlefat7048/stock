"""
台股互動式圖表繪製模組 (Plotly 深色主題)
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


def _apply_dark_layout(fig):
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=PLOT_BG_COLOR,
        font=dict(size=11, color=FONT_COLOR),
        margin=dict(l=15, r=15, t=32, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#2A324B')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#2A324B')
    return fig


def create_candlestick_chart(df, selected_mas=['MA5', 'MA20', 'MA60']):
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.04,
        subplot_titles=('股價 K 線與均線走勢（紅漲綠跌）', '成交量（股）'),
        row_width=[0.25, 0.75]
    )

    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        increasing_line_color=UP_COLOR, increasing_fillcolor=UP_COLOR,
        decreasing_line_color=DOWN_COLOR, decreasing_fillcolor=DOWN_COLOR,
        name='K線'
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
                line=dict(color=ma_colors.get(ma, '#FFFFFF'), width=1.6),
                name=ma
            ), row=1, col=1)

    volume_colors = [UP_COLOR if row['Close'] >= row['Open'] else DOWN_COLOR for _, row in df.iterrows()]
    fig.add_trace(go.Bar(
        x=df.index, y=df['Volume'],
        marker_color=volume_colors,
        name='成交量'
    ), row=2, col=1)

    fig.update_layout(xaxis_rangeslider_visible=False, height=560)
    return _apply_dark_layout(fig)


def create_macd_chart(df):
    fig = go.Figure()
    if 'MACD' in df.columns and 'Signal' in df.columns and 'Hist' in df.columns:
        colors = [UP_COLOR if h >= 0 else DOWN_COLOR for h in df['Hist']]
        fig.add_trace(go.Bar(x=df.index, y=df['Hist'], marker_color=colors, name='MACD柱狀體(DIF-MACD)'))
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='#00E5FF', width=1.8), name='DIF快線'))
        fig.add_trace(go.Scatter(x=df.index, y=df['Signal'], line=dict(color='#FF80AB', width=1.8), name='MACD慢線'))
    fig.update_layout(height=280, title='MACD 動能指標')
    return _apply_dark_layout(fig)


def create_kd_chart(df):
    fig = go.Figure()
    if 'K' in df.columns and 'D' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='#FFD700', width=1.8), name='K值(快線)'))
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], line=dict(color='#00E5FF', width=1.8), name='D值(慢線)'))
        fig.add_hline(y=80, line_dash="dash", line_color=UP_COLOR, annotation_text="80 超買線")
        fig.add_hline(y=20, line_dash="dash", line_color=DOWN_COLOR, annotation_text="20 超賣線")
    fig.update_layout(height=280, title='KD 隨機指標')
    return _apply_dark_layout(fig)


def create_rsi_chart(df):
    fig = go.Figure()
    if 'RSI' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color=PRIMARY_COLOR, width=2), name='RSI(14)'))
        fig.add_hline(y=70, line_dash="dash", line_color=UP_COLOR, annotation_text="70 超買區")
        fig.add_hline(y=50, line_dash="dot", line_color="#888888", annotation_text="50 多空分界")
        fig.add_hline(y=30, line_dash="dash", line_color=DOWN_COLOR, annotation_text="30 超賣區")
    fig.update_layout(height=280, title='RSI 相對強弱指標')
    return _apply_dark_layout(fig)


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
                name=col, marker_color=color
            ))

    if '三大法人合計' in data.columns:
        fig.add_trace(go.Scatter(
            x=data.index, y=data['三大法人合計'],
            mode='lines+markers',
            line=dict(color='#FF5252', width=2.2),
            name='三大法人合計(張)'
        ))

    fig.add_hline(y=0, line_color='#FFFFFF', line_width=1)
    fig.update_layout(barmode='relative', height=400, title='三大法人每日買賣超明細（單位：張）')
    return _apply_dark_layout(fig)


def create_margin_chart(data):
    """融資餘額與融券餘額雙軸走勢圖"""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if data is not None and not data.empty:
        if 'MarginLong' in data.columns:
            fig.add_trace(go.Scatter(
                x=data.index, y=data['MarginLong'],
                name='融資餘額(張)',
                line=dict(color='#FF80AB', width=2.2),
                fill='tozeroy', fillcolor='rgba(255,128,171,0.1)'
            ), secondary_y=False)
        if 'MarginShort' in data.columns:
            fig.add_trace(go.Scatter(
                x=data.index, y=data['MarginShort'],
                name='融券餘額(張)',
                line=dict(color='#00E5FF', width=2.2)
            ), secondary_y=True)

    fig.update_yaxes(title_text="融資餘額 (張)", secondary_y=False)
    fig.update_yaxes(title_text="融券餘額 (張)", secondary_y=True)
    fig.update_layout(height=380, title='融資與融券餘額趨勢（單位：張）')
    return _apply_dark_layout(fig)


def create_eps_chart(quarterly_df):
    """單季 EPS 與三率（毛利率/營益率/淨利率）雙圖表"""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if quarterly_df is not None and not quarterly_df.empty:
        colors = [UP_COLOR if v >= 0 else DOWN_COLOR for v in quarterly_df['EPS']]
        fig.add_trace(go.Bar(
            x=quarterly_df['Quarter'], y=quarterly_df['EPS'],
            marker_color=colors, name='單季 EPS (元)',
            text=quarterly_df['EPS'], textposition='outside'
        ), secondary_y=False)

        for rate_col, color in [('毛利率(%)', '#FFD700'), ('營益率(%)', '#00E5FF'), ('淨利率(%)', '#C084FC')]:
            if rate_col in quarterly_df.columns:
                fig.add_trace(go.Scatter(
                    x=quarterly_df['Quarter'], y=quarterly_df[rate_col],
                    mode='lines+markers',
                    line=dict(color=color, width=2),
                    name=rate_col
                ), secondary_y=True)

    fig.update_yaxes(title_text="單季 EPS (元)", secondary_y=False)
    fig.update_yaxes(title_text="獲利三率 (%)", secondary_y=True)
    fig.update_layout(height=400, title='季度 EPS 與獲利三率（毛利率 / 營益率 / 淨利率）走勢')
    return _apply_dark_layout(fig)


def create_revenue_chart(monthly_revenue):
    """月營收與年增率 YoY 走勢圖"""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if monthly_revenue is not None and not monthly_revenue.empty:
        fig.add_trace(go.Bar(
            x=monthly_revenue['Month'], y=monthly_revenue['Revenue'],
            marker_color=PRIMARY_COLOR, name='月營收 (億元)'
        ), secondary_y=False)

        if 'YoY' in monthly_revenue.columns:
            fig.add_trace(go.Scatter(
                x=monthly_revenue['Month'], y=monthly_revenue['YoY'],
                mode='lines+markers',
                line=dict(color='#FFD700', width=2.2),
                name='年增率 YoY (%)'
            ), secondary_y=True)
        if 'MoM' in monthly_revenue.columns:
            fig.add_trace(go.Scatter(
                x=monthly_revenue['Month'], y=monthly_revenue['MoM'],
                mode='lines+markers',
                line=dict(color='#FF80AB', width=1.6, dash='dot'),
                name='月增率 MoM (%)'
            ), secondary_y=True)

    fig.update_yaxes(title_text="月營收 (億元)", secondary_y=False)
    fig.update_yaxes(title_text="增減率 (%)", secondary_y=True)
    fig.update_layout(height=400, title='近 12 個月營收與年增率 (YoY) 趨勢')
    return _apply_dark_layout(fig)
