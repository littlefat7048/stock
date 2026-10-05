import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. Fetch 6672 on 2026-10-02
ticker = yf.Ticker('6672.TW')
df = ticker.history(period='7d', interval='1m')
df.index = df.index.tz_convert('Asia/Taipei')
d2 = df[df.index.strftime('%Y-%m-%d') == '2026-10-02'].copy()

d2['Vol_Lots'] = d2['Volume'] / 1000.0
d2['Cum_Vol'] = d2['Volume'].cumsum()
d2['Cum_VP'] = (d2['Close'] * d2['Volume']).cumsum()
d2['VWAP'] = np.where(d2['Cum_Vol'] > 0, d2['Cum_VP'] / d2['Cum_Vol'], d2['Close'])

# Create figure matching 图一
fig = make_subplots(
    rows=2, cols=1, shared_xaxes=True,
    vertical_spacing=0.06,
    row_width=[0.24, 0.76]
)

BG_COLOR = '#111215'
PLOT_BG = '#15161A'
GRID_COLOR = '#21232B'

# 1. Market VWAP (white dotted line)
fig.add_trace(go.Scatter(
    x=d2.index, y=d2['VWAP'],
    mode='lines',
    line=dict(color='#CBD5E1', width=1.5, dash='dash'),
    name='市場均價',
    hoverinfo='skip'
), row=1, col=1)

# 2. Main Price Line (red polyline)
fig.add_trace(go.Scatter(
    x=d2.index, y=d2['Close'],
    mode='lines',
    line=dict(color='#EF4444', width=2.2),
    name='股價',
    hovertemplate="%{x|%H:%M}｜股價: <b>%{y:.2f}</b><extra></extra>"
), row=1, col=1)

# 3. Add Stepped Footprint Shelves (還原圖一的綠色/紅色階梯帶與三角形)
t_0902 = d2.index[2]
t_0908 = d2.index[8]
t_0925 = d2.index[25]
t_1015 = d2.index[75]
t_1045 = d2.index[105]
t_1245 = d2.index[225]
t_1300 = d2.index[240]
t_1315 = d2.index[255]

shelves = [
    (t_0902, t_0908, 418.0, False, 3),
    (t_0908, t_0925, 426.0, False, 4),
    (t_0925, t_1015, 431.5, True, 3),
    (t_1045, t_1245, 427.0, False, 2),
    (t_1300, t_1315, 437.0, False, 3)
]

for t_s, t_e, p_sh, is_buy, n_arrows in shelves:
    sub_slice = d2.loc[t_s:t_e]
    if sub_slice.empty: continue
    
    fill_col = 'rgba(239, 68, 68, 0.40)' if is_buy else 'rgba(34, 197, 94, 0.40)'
    line_col = '#EF4444' if is_buy else '#22C55E'
    arrow_sym = '▲' if is_buy else '▼'

    # Stepped shelf line
    fig.add_shape(
        type='line',
        x0=t_s, x1=t_e, y0=p_sh, y1=p_sh,
        line=dict(color=line_col, width=2.5),
        row=1, col=1
    )
    
    min_p = min(sub_slice['Low'].min(), p_sh)
    max_p = max(sub_slice['High'].max(), p_sh)
    fig.add_shape(
        type='rect',
        x0=t_s, x1=t_e, y0=min_p, y1=max_p,
        fillcolor=fill_col,
        line=dict(width=0),
        layer='below',
        row=1, col=1
    )

    step_idx = max(1, len(sub_slice) // (n_arrows + 1))
    for a_i in range(1, n_arrows + 1):
        idx_pt = min(len(sub_slice) - 1, a_i * step_idx)
        pt_x = sub_slice.index[idx_pt]
        fig.add_annotation(
            x=pt_x, y=p_sh,
            text=arrow_sym,
            showarrow=False,
            font=dict(color=line_col, size=13),
            yshift=10 if is_buy else -10,
            row=1, col=1
        )

# Reference annotations
fig.add_annotation(x=d2.index[-1], y=405.50, text="參考 405.50", showarrow=False, font=dict(color="#64748B", size=11), xshift=-30, yshift=-10, row=1, col=1)
fig.add_annotation(x=t_0902, y=404.0, text="404.00", showarrow=False, font=dict(color="#94A3B8", size=11), yshift=-14, row=1, col=1)
fig.add_annotation(x=t_1315, y=439.0, text="439.00", showarrow=False, font=dict(color="#22C55E", size=11), yshift=14, row=1, col=1)
fig.add_annotation(x=d2.index[-1], y=439.0, text="439.00", showarrow=False, font=dict(color="#EF4444", size=11), xshift=-25, yshift=14, row=1, col=1)

# Lower Volume chart
fig.add_trace(go.Bar(
    x=d2.index, y=d2['Vol_Lots'],
    marker_color='#F59E0B',
    name='市場分時量',
    hovertemplate="%{x|%H:%M}｜量: <b>%{y:,.0f} 張</b><extra></extra>"
), row=2, col=1)

fig.update_layout(
    template='plotly_dark',
    paper_bgcolor=BG_COLOR,
    plot_bgcolor=PLOT_BG,
    height=600,
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
    automargin=True
)

fig.write_html("scripts/fig1_preview.html")
print("Saved scripts/fig1_preview.html!")

from playwright.sync_api import sync_playwright
import os
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 980, 'height': 650})
    file_uri = "file:///" + os.path.abspath("scripts/fig1_preview.html").replace('\\', '/')
    page.goto(file_uri)
    page.wait_for_timeout(1500)
    page.screenshot(path="C:/Users/SOHO/.gemini/antigravity/brain/4f0ffc20-d7fe-4309-9493-c334bd868b71/verify_exact_fig1_chart.png")
    browser.close()
print("Captured verify_exact_fig1_chart.png!")
