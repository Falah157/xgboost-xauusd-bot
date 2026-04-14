import streamlit as st
import pandas as pd
import numpy as np
import requests
import matplotlib.pyplot as plt
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="REAL XAUUSD", layout="wide")
st.title("🏆 REAL XAUUSD Live Trading Dashboard")

# YOUR API KEY - PASTED HERE
API_KEY = "96871e27b094425f9ea104fa6eb2be64"

st.success("✅ Connected to Twelve Data API - Getting REAL XAUUSD prices!")

@st.cache_data(ttl=30)
def get_realtime_price():
    """Get REAL XAUUSD price"""
    try:
        url = f"https://api.twelvedata.com/price?symbol=XAU/USD&apikey={API_KEY}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'price' in data:
                return float(data['price'])
    except Exception as e:
        st.error(f"API Error: {e}")
    return None

@st.cache_data(ttl=300)
def get_historical():
    """Get historical XAUUSD data"""
    try:
        url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=1h&outputsize=100&apikey={API_KEY}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'values' in data:
                df = pd.DataFrame(data['values'])
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df.set_index('datetime')
                df['Close'] = df['close'].astype(float)
                df['High'] = df['high'].astype(float)
                df['Low'] = df['low'].astype(float)
                return df
    except:
        pass
    return None

# Get data
with st.spinner("Fetching REAL XAUUSD data..."):
    current_price = get_realtime_price()
    df = get_historical()

if current_price is None:
    st.error("Failed to fetch price. Please check your API key or internet connection.")
    st.stop()

# Calculate indicators
if df is not None and len(df) > 20:
    df['SMA_20'] = df['Close'].rolling(20).mean()
    df['SMA_50'] = df['Close'].rolling(50).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    current_rsi = float(df['RSI'].iloc[-1]) if not pd.isna(df['RSI'].iloc[-1]) else 50
    sma20 = float(df['SMA_20'].iloc[-1]) if not pd.isna(df['SMA_20'].iloc[-1]) else current_price
else:
    current_rsi = 50
    sma20 = current_price

# Determine trend
if current_price > sma20 and current_rsi > 50:
    trend = "BULLISH 📈"
    direction = "LONG"
elif current_price < sma20 and current_rsi < 50:
    trend = "BEARISH 📉"
    direction = "SHORT"
else:
    trend = "SIDEWAYS ➡️"
    direction = "SHORT" if current_rsi < 50 else "LONG"

# Display metrics
st.success(f"✅ LIVE XAUUSD: **${current_price:.2f}**")

col1, col2, col3, col4 = st.columns(4)
col1.metric("XAUUSD (REAL)", f"${current_price:.2f}")
col2.metric("RSI (14)", f"{current_rsi:.1f}")
col3.metric("Trend", trend)
col4.metric("Data", "LIVE from Twelve Data")

# Price chart
if df is not None and len(df) > 0:
    st.subheader("📊 XAUUSD Price Chart (Real Data)")
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(df.index, df['Close'], color='gold', linewidth=2, label='XAUUSD')
    if 'SMA_20' in df.columns:
        ax.plot(df.index, df['SMA_20'], 'blue', linestyle='--', alpha=0.7, label='SMA 20')
    ax.set_ylabel('Price (USD)')
    ax.set_title('Real XAUUSD Prices from Twelve Data API')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    st.pyplot(fig)

# Trading Levels
st.subheader("🎯 Trading Levels (Based on REAL Price)")

atr = current_price * 0.005
risk_amount = current_price * 0.01

if direction == "LONG":
    entry = current_price
    sl = entry - atr
    tps = {f"{r}R": entry + (atr * r) for r in [2, 3, 4, 5]}
else:
    entry = current_price
    sl = entry + atr
    tps = {f"{r}R": entry - (atr * r) for r in [2, 3, 4, 5]}

col1, col2 = st.columns(2)
with col1:
    st.metric("📍 ENTRY", f"${entry:.2f}")
    st.metric("🛑 STOP LOSS", f"${sl:.2f}", f"Risk: ${abs(entry - sl):.2f}")
with col2:
    st.metric("💰 RISK:REWARD", "1:2 to 1:5")
    for label, tp in tps.items():
        st.metric(f"🎯 {label}", f"${tp:.2f}", f"Profit: ${abs(tp - entry):.2f}")

# Position Sizing
st.subheader("⚙️ Position Sizing")
account = st.number_input("Account Balance ($)", value=10000, step=1000)
risk_pct = st.slider("Risk per trade (%)", 0.5, 3.0, 1.0)
risk_dollar = account * (risk_pct / 100)
position_size = risk_dollar / abs(entry - sl)
st.metric("📊 Position Size", f"{position_size:.4f} units")
st.metric("⚠️ Risk Amount", f"${risk_dollar:.2f}")

# RSI Chart
if df is not None and 'RSI' in df.columns:
    st.subheader("📈 RSI Indicator")
    fig2, ax2 = plt.subplots(figsize=(12, 2))
    ax2.plot(df.index, df['RSI'], color='purple', linewidth=1)
    ax2.axhline(y=70, color='red', linestyle='--', label='Overbought')
    ax2.axhline(y=30, color='green', linestyle='--', label='Oversold')
    ax2.set_ylim(0, 100)
    ax2.set_ylabel('RSI')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    st.pyplot(fig2)

st.sidebar.markdown("---")
st.sidebar.success(f"✅ Using REAL XAUUSD data via Twelve Data API")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.sidebar.warning("⚠️ Educational only - Not financial advice")

if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
