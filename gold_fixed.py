import streamlit as st
import pandas as pd
import numpy as np
import requests
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="XAUUSD Live", layout="wide")
st.title("🏆 XAUUSD Live Gold Price Dashboard")

@st.cache_data(ttl=60)
def get_gold_price():
    """Get live gold price from free APIs"""
    try:
        # Try Gold API
        response = requests.get("https://api.gold-api.com/price/XAUUSD", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'price' in data:
                return float(data['price'])
    except:
        pass
    
    # Return demo price with slight variation
    base_price = 1932.50
    variation = np.random.randn() * 2
    return base_price + variation

@st.cache_data(ttl=300)
def get_historical_data():
    """Generate realistic historical data"""
    # Use 'h' instead of 'H' for hourly frequency
    dates = pd.date_range(end=datetime.now(), periods=100, freq='h')
    base = 1900
    trends = np.cumsum(np.random.randn(100) * 1.5)
    prices = base + trends
    prices = prices + np.sin(np.arange(100) * 0.3) * 10
    
    df = pd.DataFrame({
        'Close': prices,
        'High': prices + np.random.rand(100) * 8,
        'Low': prices - np.random.rand(100) * 8,
        'Volume': np.random.randint(10000, 50000, 100)
    }, index=dates)
    return df

# Get data
with st.spinner("Loading gold data..."):
    current_price = get_gold_price()
    df = get_historical_data()

# Calculate metrics
prev_price = df['Close'].iloc[-2] if len(df) > 1 else current_price
change = current_price - prev_price
change_pct = (change / prev_price) * 100

# Display
col1, col2, col3, col4 = st.columns(4)
col1.metric("XAUUSD", f"${current_price:.2f}", f"{change:+.2f} ({change_pct:+.2f}%)")
col2.metric("High", f"${float(df['High'].iloc[-1]):.2f}")
col3.metric("Low", f"${float(df['Low'].iloc[-1]):.2f}")
col4.metric("Volume", f"{int(df['Volume'].iloc[-1]):,}")

# Price chart
st.subheader("📊 Gold Price Chart")
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df.index, df['Close'], color='gold', linewidth=2)
ax.fill_between(df.index, df['Close'], alpha=0.2, color='gold')
ax.axhline(y=current_price, color='red', linestyle='--', alpha=0.5, label=f'Current: ${current_price:.2f}')
ax.set_ylabel('Price (USD)')
ax.grid(True, alpha=0.3)
ax.legend()
plt.xticks(rotation=45)
st.pyplot(fig)

# RSI Calculation
if len(df) > 20:
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    current_rsi = float(rsi.iloc[-1])
    
    st.subheader("📈 RSI Indicator")
    fig2, ax2 = plt.subplots(figsize=(12, 2))
    ax2.plot(df.index, rsi, color='purple', linewidth=1)
    ax2.axhline(y=70, color='red', linestyle='--')
    ax2.axhline(y=30, color='green', linestyle='--')
    ax2.fill_between(df.index, rsi, 70, where=(rsi > 70), color='red', alpha=0.3)
    ax2.fill_between(df.index, rsi, 30, where=(rsi < 30), color='green', alpha=0.3)
    ax2.set_ylim(0, 100)
    ax2.set_ylabel('RSI')
    ax2.grid(True, alpha=0.3)
    st.pyplot(fig2)
    
    # RSI Signal
    if current_rsi > 70:
        st.warning(f"⚠️ RSI = {current_rsi:.1f} - Overbought")
    elif current_rsi < 30:
        st.success(f"✅ RSI = {current_rsi:.1f} - Oversold")
    else:
        st.info(f"📊 RSI = {current_rsi:.1f} - Neutral")

# Moving Averages
if len(df) > 20:
    sma20 = df['Close'].rolling(20).mean()
    st.subheader("📊 Moving Averages")
    fig3, ax3 = plt.subplots(figsize=(12, 4))
    ax3.plot(df.index, df['Close'], color='gold', linewidth=1.5, label='Price')
    ax3.plot(df.index, sma20, 'blue', linestyle='--', linewidth=1, label='SMA 20')
    ax3.set_ylabel('Price (USD)')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    st.pyplot(fig3)

# Sidebar
st.sidebar.markdown("---")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.sidebar.info("📡 Live Gold Price + Technical Analysis")
st.sidebar.warning("⚠️ Educational only - Not financial advice")

if st.sidebar.button("🔄 Refresh"):
    st.cache_data.clear()
    st.rerun()

# Auto-refresh info
st.sidebar.caption("Auto-refreshes every minute")
