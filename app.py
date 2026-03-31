import streamlit as st
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import numpy as np
import requests

# 페이지 설정
st.set_page_config(layout="wide", page_title="Crypto Web Chart")

# 보안 설정 (Secrets)
TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
ID = st.secrets.get("CHAT_ID", "")

# 데이터 로드 함수 (에러 메시지 출력 추가)
def get_data(symbol, interval):
    try:
        # 데이터 개수를 200개로 줄여 로딩 속도 개선
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval={interval}&limit=200"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            st.error(f"API 호출 실패: 상태 코드 {response.status_code}")
            return pd.DataFrame()
            
        res = response.json()
        if not res or not isinstance(res, list):
            st.warning("데이터가 비어 있습니다.")
            return pd.DataFrame()

        df = pd.DataFrame(res).iloc[:, :6]
        df.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
        df['Time'] = pd.to_datetime(df['Time'], unit='ms') + pd.Timedelta(hours=9)
        df = df.set_index('Time').apply(pd.to_numeric)
        
        # 지표 계산
        df['MA10'] = ta.sma(df.Close, length=10)
        df['MAC_Upper'] = ta.ema(df.High, length=120) # EMA 기간을 짧게 조정하여 빠른 로딩
        df['RSI'] = ta.rsi(df.Close, length=14)
        
        # 매도 시그널 로직
        cond_sell = (df['RSI'] >= 65) & (df['Close'] < df['MA10'])
        df['Sell_Signal'] = np.where(cond_sell, df['High'] * 1.02, np.nan)
        
        return df
    except Exception as e:
        st.error(f"데이터 처리 중 오류 발생: {e}")
        return pd.DataFrame()

# UI 구성
st.sidebar.title("차트 설정")
sel_sym = st.sidebar.selectbox("코인 선택", ('BTC', 'ETH', 'XRP', 'BCH', 'ZRO'))
sel_int = st.sidebar.selectbox("시간 단위", ('1h', '4h', '1d'), index=0)

# 실행 및 출력
with st.spinner('데이터를 불러오는 중...'):
    df = get_data(sel_sym, sel_int)

if not df.empty:
    st.title(f"📈 {sel_sym}/USDT 실시간 차트")
    
    fig = go.Figure()
    # 캔들스틱 추가
    fig.add_trace(go.Candlestick(
        x=df.index, open=df.Open, high=df.High, low=df.Low, close=df.Close, name="가격"
    ))
    
    # 이동평균선 추가
    fig.add_trace(go.Scatter(x=df.index, y=df.MA10, line=dict(color='orange', width=1.5), name="MA10"))
    
    # 매도 시그널 표시
    s_df = df[df.Sell_Signal.notna()]
    if not s_df.empty:
        fig.add_trace(go.Scatter(
            x=s_df.index, y=s_df.Sell_Signal, mode='markers', 
            marker=dict(symbol='triangle-down', size=15, color='blue'), name="매도 신호"
        ))

    fig.update_layout(
        height=700, 
        template="plotly_white", 
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=50, b=10)
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("차트를 표시할 데이터가 없습니다. 설정을 변경해 보세요.")
