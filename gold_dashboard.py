import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="XAUUSD Live", layout="wide")
st.title("🏆 XAUUSD Live Analysis Dashboard")

@st.cache_data(ttl=300)
def get_gold_data():
    # Try different symbols for gold
    symbols = ['GLD', 'IAU', 'GC=F']
    
    for symbol in symbols:
        try:
            df = yf.download(symbol, period="5d", interval="15m", progress=False)
            if not df.empty and len(df) > 5:
                return df, symbol
        except:
            continue
    
    # If all fail, generate sample data
    st.warning("Using sample data - Live feed unavailable")
    dates = pd.date_range(end=datetime.now(), periods=100, freq='15min')
    prices = 1900 + np.cumsum(np.random.randn(100) * 1.5)
    df = pd.DataFrame({
        'Open': prices,
        'High': prices + np.random.rand(100) * 5,
        'Low': prices - np.random.rand(100) * 5,
        'Close': prices,
        'Volume': np.random.randint(1000, 10000, 100)
    }, index=dates)
    return df, "Sample"

# Load data
with st.spinner("Loading XAUUSD data..."):
    df, source = get_gold_data()

# Get current price safely
if len(df) > 0:
    current_price = float(df['Close'].iloc[-1])
    prev_price = float(df['Close'].iloc[-2]) if len(df) > 1 else current_price
    change = current_price - prev_price
    change_pct = (change / prev_price) * 100 if prev_price != 0 else 0
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("XAUUSD", f"${current_price:.2f}", f"{change:+.2f} ({change_pct:+.2f}%)")
    col2.metric("High", f"${float(df['High'].iloc[-1]):.2f}")
    col3.metric("Low", f"${float(df['Low'].iloc[-1]):.2f}")
    col4.metric("Data Source", source)
    
    # Price chart
    st.subheader("📊 Price Chart")
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(df.index, df['Close'], color='gold', linewidth=2)
    ax.fill_between(df.index, df['Close'], alpha=0.3, color='gold')
    ax.set_title(f'XAUUSD Price - Last {len(df)} periods')
    ax.set_ylabel('Price (USD)')
    ax.set_xlabel('Time')
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    st.pyplot(fig)
    
    # Simple indicators
    st.subheader("📈 Quick Analysis")
    
    # Calculate simple moving averages
    if len(df) > 20:
        sma20 = df['Close'].rolling(20).mean().iloc[-1]
        sma50 = df['Close'].rolling(50).mean().iloc[-1] if len(df) > 50 else sma20
        
        col1, col2 = st.columns(2)
        col1.metric("SMA 20", f"${float(sma20):.2f}")
        col2.metric("SMA 50", f"${float(sma50):.2f}")
        
        if current_price > sma20:
            st.success("✅ Price above SMA20 - Bullish signal")
        else:
            st.warning("⚠️ Price below SMA20 - Bearish signal")
    
    # Volume info
    st.subheader("📊 Volume")
    fig2, ax2 = plt.subplots(figsize=(12, 2))
    ax2.bar(df.index, df['Volume'], color='gold', alpha=0.5)
    ax2.set_title('Trading Volume')
    ax2.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    st.pyplot(fig2)
    
else:
    st.error("Unable to fetch data. Please check your internet connection.")

st.sidebar.markdown("---")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.sidebar.info("💡 Tip: Data refreshes every 5 minutes")
st.sidebar.warning("⚠️ Educational purposes only - Not financial advice")

if st.sidebar.button("🔄 Manual Refresh"):
    st.cache_data.clear()
    st.rerun()
