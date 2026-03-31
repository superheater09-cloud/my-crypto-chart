import streamlit as st
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import numpy as np
import requests

# 페이지 설정
st.set_page_config(layout="wide", page_title="Crypto Web Chart")

# 보안 설정 (Secrets)
try:
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    ID = st.secrets["CHAT_ID"]
except:
    st.warning("Secrets 설정이 필요합니다.")
    TOKEN, ID = "", ""

# 데이터 로드 함수
@st.cache_data(ttl=300)
def get_data(symbol, interval):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval={interval}&limit=500"
        res = requests.get(url, timeout=10).json()
        df = pd.DataFrame(res).iloc[:, :6]
        df.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
        df['Time'] = pd.to_datetime(df['Time'], unit='ms') + pd.Timedelta(hours=9)
        df = df.set_index('Time').apply(pd.to_numeric)
        
        # 지표 계산
        df['MA10'] = ta.sma(df.Close, length=10)
        df['MA120'] = ta.sma(df.Close, length=120)
        df['MAC_Upper'] = ta.ema(df.High, length=300)
        df['RSI'] = ta.rsi(df.Close, length=14)
        macd = ta.macd(df.Close)
        if macd is not None:
            df['MH'] = macd.iloc[:, 2]
            
        # 매도 시그널 로직
        overbought = (df['RSI'] >= 65) | (df['RSI'].shift(1) >= 70)
        disparity = (df['Close'] / df['MAC_Upper']) > 1.10
        breakdown = (df['Close'] < df['MA10']) & (df['Close'] < df['Open'])
        cond_sell = (overbought | disparity) & breakdown
        df['Sell_Signal'] = np.where(cond_sell, df['High'] * 1.02, np.nan)
        
        return df
    except:
        return pd.DataFrame()

# UI
st.sidebar.title("설정")
sel_sym = st.sidebar.selectbox("코인", ('BTC', 'ETH', 'XRP', 'BCH', 'ZRO'))
sel_int = st.sidebar.selectbox("시간", ('1h', '4h', '1d'), index=2)

df = get_data(sel_sym, sel_int)

if not df.empty:
    st.title(f"📈 {sel_sym} 실시간 차트")
    
    # Plotly 차트
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df.index, open=df.Open, high=df.High, low=df.Low, close=df.Close, name="Price"))
    fig.add_trace(go.Scatter(x=df.index, y=df.MA10, line=dict(color='orange', width=1), name="MA10"))
    
    # 매도 시그널 표시
    s_df = df[df.Sell_Signal.notna()]
    fig.add_trace(go.Scatter(x=s_df.index, y=s_df.Sell_Signal, mode='markers', 
                             marker=dict(symbol='triangle-down', size=12, color='blue'), name="SELL"))

    fig.update_layout(height=600, template="plotly_white", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
