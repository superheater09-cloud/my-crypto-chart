import streamlit as st
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import numpy as np
import requests
import time
from datetime import datetime

# 1. 페이지 기본 설정 (스마트폰 최적화)
st.set_page_config(layout="wide", page_title="Crypto Signal Web")

# 2. 보안 설정 (Secrets에서 가져오기)
try:
    TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
    CHAT_ID = st.secrets["CHAT_ID"]
except:
    st.warning("⚠️ Streamlit Secrets에 TELEGRAM_TOKEN과 CHAT_ID를 설정해주세요.")
    TELEGRAM_TOKEN = ""
    CHAT_ID = ""

# 3. 데이터 로딩 함수 (바이낸스 API 활용)
@st.cache_data(ttl=300) # 5분간 캐시 유지
def fetch_data(symbol, interval):
    try:
        target_symbol = f"{symbol}USDT"
        # 월봉은 2017년부터, 나머지는 2023년부터 가져오기 (기존 로직 반영)
        if interval == '1M':
            start_ts = int(pd.Timestamp("2017-01-01").timestamp() * 1000)
        else:
            start_ts = int(pd.Timestamp("2023-01-01").timestamp() * 1000)
            
        url = f"https://api.binance.com/api/v3/klines?symbol={target_symbol}&interval={interval}&limit=1000&startTime={start_ts}"
        res = requests.get(url, timeout=10).json()
        
        df = pd.DataFrame(res).iloc[:, :6]
        df.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
        df['Time'] = pd.to_datetime(df['Time'], unit='ms') + pd.Timedelta(hours=9)
        df = df.set_index('Time').apply(pd.to_numeric)
        
        # 지표 계산 로직 (보내주신 코드와 동일하게 구현)
        df['MA10'] = ta.sma(df.Close, length=10)
        df['MA120'] = ta.sma(df.Close, length=120)
        df['MA240'] = ta.sma(df.Close, length=240)
        df['MAC_Upper'] = ta.ema(df.High, length=300)
        df['RSI'] = ta.rsi(df.Close, length=14)
        
        # MACD
        macd = ta.macd(df.Close)
        if macd is not None:
            df['M'], df['MS'], df['MH'] = macd.iloc[:, 0], macd.iloc[:, 1], macd.iloc[:, 2]
            
        # Bollinger Bands
        bb = ta.bbands(df.Close, length=20, std=2)
        df['BBU'], df['BBL'] = bb.iloc[:, 2], bb.iloc[:, 0]
        
        # Ichimoku
        ichimoku, _ = ta.ichimoku(df.High, df.Low, df.Close)
        df['ISA'], df['ISB'] = ichimoku.iloc[:, 0], ichimoku.iloc[:, 1]

        # [매수 신호]
        cond_b1 = (df['RSI'] >= 40)
        cond_b2 = (df['M'] > df['MS']) & (df['M'].shift(1) <= df['MS'].shift(1))
        cond_b3 = (df['Close'] >= df['MA10'])
        df['Buy_Signal'] = np.where(cond_b1 & cond_b2 & cond_b3, df['Low'] * 0.98, np.nan)

        # [매도 신호 - 보내주신 수정 로직 적용]
        overbought = (df['RSI'] >= 65) | (df['RSI'].shift(1) >= 70)
        disparity = (df['Close'] / df['MAC_Upper']) > 1.10
        breakdown = (df['Close'] < df['MA10']) & (df['Close'] < df['Open'])
        momentum_fade = (df['MH'] < df['MH'].shift(1))
        
        cond_sell = (overbought | disparity) & breakdown & momentum_fade
        df['Sell_Signal'] = np.where(cond_sell, df['High'] * 1.02, np.nan)
        
        return df.dropna(subset=['MA10'])
    except Exception as e:
        st.error(f"데이터 로드 에러: {e}")
        return pd.DataFrame()

# 4. 사이드바 UI 구성 (라디오 버튼 대체)
st.sidebar.title("🛠️ Control Panel")
symbol = st.sidebar.selectbox("코인 선택", ('BTC', 'ETH', 'XRP', 'BCH', 'ZRO'), index=0)
interval = st.sidebar.selectbox("시간 단위", ('1m', '1h', '4h', '1d', '1w', '1M'), index=3)
show_bb = st.sidebar.checkbox("Bollinger Bands (BB)")
show_cloud = st.sidebar.checkbox("Ichimoku Cloud")
view_count = st.sidebar.slider("캔들 표시 개수", 50, 500, 200)

# 5. 메인 화면 차트 구현
st.title(f"🚀 {symbol} 실시간 시그널 차트 ({interval})")

df = fetch_data(symbol, interval)

if not df.empty:
    plot_df = df.tail(view_count)
    
    # Plotly 차트 생성 (멀티 차트 레이아웃)
    from plotly.subplots import make_subplots
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.03, row_heights=[0.5, 0.1, 0.2, 0.2])

    # 1. 메인 캔들스틱 차트
    fig.add_trace(go.Candlestick(
        x=plot_df.index, open=plot_df['Open'], high=plot_df['High'],
        low=plot_df['Low'], close=plot_df['Close'], name="Price"
    ), row=1, col=1)

    # 이동평균선 및 EMA300
    fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MA10'], line=dict(color='#1f77b4', width=1), name="MA10"), row=1, col=1)
    fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MA120'], line=dict(color='#ff7f0e', width=1), name="MA120"), row=1, col=1)
    fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MAC_Upper'], line=dict(color='#ff00ff', width=1.5), name="EMA300"), row=1, col=1)

    # 지표 On/Off (BB, Cloud)
    if show_bb:
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['BBU'], line=dict(color='gold', dash='dot'), name="BB Upper"), row=1, col=1)
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['BBL'], line=dict(color='gold', dash='dot'), name="BB Lower"), row=1, col=1)
    
    if show_cloud:
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['ISA'], line=dict(width=0), showlegend=False), row=1, col=1)
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['ISB'], line=dict(width=0), fill='tonexty', name="Cloud"), row=1, col=1)

    # 신호 표시 (화살표 대체)
    buy_signals = plot_df[plot_df['Buy_Signal'].notna()]
    fig.add_trace(go.Scatter(x=buy_signals.index, y=buy_signals['Buy_Signal'], mode='markers', 
                             marker=dict(symbol='triangle-up', size=12, color='red'), name="BUY"), row=1, col=1)
    
    sell_signals = plot_df[plot_df['Sell_Signal'].notna()]
    fig.add_trace(go.Scatter(x=sell_signals.index, y=sell_signals['Sell_Signal'], mode='markers', 
                             marker=dict(symbol='triangle-down', size=12, color='blue'), name="SELL"), row=1, col=1)

    # 2. 거래량 차트
    fig.add_trace(go.Bar(x=plot_df.index, y=plot_df['Volume'], name="Volume", marker_color='gray', opacity=0.5), row=2, col=1)

    # 3. MACD 차트
    fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['M'], line=dict(color='blue'), name="MACD"), row=3, col=1)
    fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MS'], line=dict(color='red'), name="Signal"), row=3, col=1)
    fig.add_trace(go.Bar(x=plot_df.index, y=plot_df['MH'], name="Hist", marker_color='silver'), row=3, col=1)

    # 4. RSI 차트
    fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['RSI'], line=dict(color='#8a2be2'), name="RSI"), row=4, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=4, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="blue", row=4, col=1)

    # 레이아웃 업데이트 (모바일 터치 최적화)
    fig.update_layout(height=900, template="plotly_white", margin=dict(l=10, r=10, t=50, b=10),
                      xaxis_rangeslider_visible=False, showlegend=False)
    
    st.plotly_chart(fig, use_container_width=True)

    # 최신봉 시그널 발생 시 텔레그램 발송 (웹 접속 시 체크)
    last_row = df.iloc[-1]
    if not np.isnan(last_row['Sell_Signal']):
        st.error(f"🚨 매도 시그널 발생! 가격: {last_row['Close']:,.2f}")
        # 참고: 웹 환경에서는 새로고침 시마다 메시지가 갈 수 있으므로 
        # 실제 서버(VPS)에서 백그라운드로 돌리는 코드와 병행하는 것이 좋습니다.

else:
    st.warning("데이터를 불러올 수 없습니다. API 연결을 확인하세요.")