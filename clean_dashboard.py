import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="XAUUSD Trader", layout="wide")
st.title("🏆 XAUUSD Trading Dashboard")

API_KEY = "96871e27b094425f9ea104fa6eb2be64"

@st.cache_data(ttl=30)
def get_price():
    try:
        url = f"https://api.twelvedata.com/price?symbol=XAU/USD&apikey={API_KEY}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return float(r.json()['price'])
    except:
        pass
    return 1932.50

@st.cache_data(ttl=300)
def get_data():
    try:
        url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=15min&outputsize=200&apikey={API_KEY}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if 'values' in data:
                df = pd.DataFrame(data['values'])
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df.set_index('datetime')
                df['Close'] = df['close'].astype(float)
                df['High'] = df['high'].astype(float)
                df['Low'] = df['low'].astype(float)
                df['Open'] = df['open'].astype(float)
                return df
    except Exception as e:
        st.error(f"Error: {e}")
    return None

# Load data
current_price = get_price()
df = get_data()

# Display metrics
col1, col2, col3, col4 = st.columns(4)
col1.metric("XAUUSD", f"${current_price:.2f}")
if df is not None:
    col2.metric("High (24h)", f"${df['High'].max():.2f}")
    col3.metric("Low (24h)", f"${df['Low'].min():.2f}")
    col4.metric("Data Points", len(df))

# Chart
if df is not None:
    st.subheader("📈 Price Chart")
    fig = go.Figure(data=[go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name='XAUUSD'
    )])
    fig.update_layout(
        title="XAUUSD - 15 Minute Chart",
        yaxis_title="Price (USD)",
        xaxis_title="Time",
        height=500,
        template='plotly_dark'
    )
    st.plotly_chart(fig, use_container_width=True)

# Simple RSI
if df is not None and len(df) > 20:
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    current_rsi = rsi.iloc[-1]
    
    st.subheader("📊 RSI Indicator")
    col1, col2 = st.columns(2)
    col1.metric("RSI (14)", f"{current_rsi:.1f}")
    
    if current_rsi > 70:
        col2.warning("⚠️ Overbought Zone")
    elif current_rsi < 30:
        col2.success("✅ Oversold Zone")
    else:
        col2.info("📊 Neutral Zone")

# Footer
st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.caption("⚠️ Educational purposes only - Not financial advice")
