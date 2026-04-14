import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="XAUUSD AI Analyzer", layout="wide")
st.title("🤖 XAUUSD Automated AI Analysis System")

@st.cache_data(ttl=300)
def get_live_data():
    gold = yf.download("GC=F", period="5d", interval="15m", progress=False)
    return gold

with st.spinner("Fetching live XAUUSD data..."):
    df = get_live_data()

# Convert to scalar values properly
current_price = float(df['Close'].iloc[-1])
prev_price = float(df['Close'].iloc[-2]) if len(df) > 1 else current_price
high_price = float(df['High'].iloc[-1])
low_price = float(df['Low'].iloc[-1])
change = current_price - prev_price
change_pct = (change / prev_price) * 100

col1, col2, col3, col4 = st.columns(4)
col1.metric("XAUUSD", f"${current_price:.2f}", f"{change:+.2f} ({change_pct:+.2f}%)")
col2.metric("High", f"${high_price:.2f}")
col3.metric("Low", f"${low_price:.2f}")
col4.metric("Data Points", f"{len(df)}")

st.header("📊 Live Price Chart")
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df.index, df['Close'], color='gold', linewidth=2, label='XAUUSD')
ax.set_title('XAUUSD Price - Last 5 Days')
ax.set_ylabel('Price (USD)')
ax.set_xlabel('Date')
ax.legend()
ax.grid(True, alpha=0.3)
plt.xticks(rotation=45)
st.pyplot(fig)

st.header("📈 Technical Summary")
col1, col2 = st.columns(2)

with col1:
    # Simple moving averages
    sma20 = float(df['Close'].rolling(20).mean().iloc[-1]) if len(df) >= 20 else current_price
    sma50 = float(df['Close'].rolling(50).mean().iloc[-1]) if len(df) >= 50 else current_price
    
    st.metric("SMA 20", f"${sma20:.2f}")
    st.metric("SMA 50", f"${sma50:.2f}")
    
    if current_price > sma20:
        st.success("✅ Price above SMA 20 (Bullish)")
    else:
        st.error("❌ Price below SMA 20 (Bearish)")

with col2:
    # Calculate RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    current_rsi = float(rsi.iloc[-1]) if len(rsi) > 0 else 50
    
    st.metric("RSI (14)", f"{current_rsi:.1f}")
    
    if current_rsi > 70:
        st.warning("⚠️ Overbought - Possible pullback")
    elif current_rsi < 30:
        st.success("✅ Oversold - Possible bounce")
    else:
        st.info("📊 Neutral zone")

st.header("🤖 AI Quick Analysis")
st.info("""
**Market Summary:**
- Gold is currently trading at **${:.2f}**
- {} from previous session
- RSI at **{:.1f}** indicates {}
""".format(
    current_price,
    f"UP ${change:.2f}" if change > 0 else f"DOWN ${abs(change):.2f}",
    current_rsi,
    "overbought conditions" if current_rsi > 70 else "oversold conditions" if current_rsi < 30 else "neutral momentum"
))

st.sidebar.markdown("---")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.sidebar.warning("⚠️ Educational only - Not financial advice")

# Auto-refresh option
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
