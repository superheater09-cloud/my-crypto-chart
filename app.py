import streamlit as st
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import numpy as np
import requests

# 페이지 설정
st.set_page_config(layout="wide", page_title="Upbit Crypto Chart")

# 데이터 로드 함수 (업비트 API 사용)
def get_upbit_data(ticker, interval, count=200):
    try:
        # 업비트 분봉/일봉 API URL 설정
        if interval == '1d':
            url = f"https://api.upbit.com/v1/candles/days?market=KRW-{ticker}&count={count}"
        else:
            # 1h -> 60, 4h -> 240
            min_map = {'1h': 60, '4h': 240}
            minutes = min_map.get(interval, 60)
            url = f"https://api.upbit.com/v1/candles/minutes/{minutes}?market=KRW-{ticker}&count={count}"
        
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            st.error(f"업비트 API 호출 실패: {response.status_code}")
            return pd.DataFrame()
            
        data = response.json()
        df = pd.DataFrame(data)
        
        # 컬럼명 정리 및 시간축 설정
        df = df[['candle_date_time_kst', 'opening_price', 'high_price', 'low_price', 'trade_price', 'candle_acc_trade_volume']]
        df.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
        df['Time'] = pd.to_datetime(df['Time'])
        df = df.set_index('Time').sort_index().apply(pd.to_numeric)
        
        # 지표 계산
        df['MA10'] = ta.sma(df.Close, length=10)
        df['RSI'] = ta.rsi(df.Close, length=14)
        
        # 매도 시그널 (RSI 과매수 + 음봉)
        cond_sell = (df['RSI'] >= 65) & (df['Close'] < df['Open'])
        df['Sell_Signal'] = np.where(cond_sell, df['High'] * 1.01, np.nan)
        
        return df
    except Exception as e:
        st.error(f"데이터 처리 오류: {e}")
        return pd.DataFrame()

# UI 구성
st.sidebar.title("차트 설정 (업비트)")
# 업비트에서 지원하는 티커로 변경
sel_sym = st.sidebar.selectbox("코인 선택", ('BTC', 'ETH', 'XRP', 'BCH', 'ZRO'))
sel_int = st.sidebar.selectbox("시간 단위", ('1h', '4h', '1d'), index=0)

with st.spinner('업비트 데이터를 불러오는 중...'):
    df = get_upbit_data(sel_sym, sel_int)

if not df.empty:
    st.title(f"📈 업비트 {sel_sym}/KRW 실시간 차트")
    
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index, open=df.Open, high=df.High, low=df.Low, close=df.Close, name="가격"
    ))
    
    fig.add_trace(go.Scatter(x=df.index, y=df.MA10, line=dict(color='orange', width=1.5), name="MA10"))
    
    s_df = df[df.Sell_Signal.notna()]
    if not s_df.empty:
        fig.add_trace(go.Scatter(
            x=s_df.index, y=s_df.Sell_Signal, mode='markers', 
            marker=dict(symbol='triangle-down', size=15, color='blue'), name="매도 신호"
        ))

    fig.update_layout(height=700, template="plotly_white", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.")
