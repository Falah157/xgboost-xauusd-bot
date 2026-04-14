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
    gold = yf.download("GC=F", period="5d", interval="15m", progress=False, auto_adjust=False)
    return gold

with st.spinner("Fetching live XAUUSD data..."):
    df = get_live_data()

# Ensure we have a flat DataFrame
if isinstance(df.columns, pd.MultiIndex):
    df.columns = ['_'.join(col).strip() for col in df.columns.values]

# Get values using .values[0] to ensure scalar
current_price = df['Close'].values[-1]
if isinstance(current_price, (list, np.ndarray)):
    current_price = current_price[0] if len(current_price) > 0 else 0
current_price = float(current_price)

prev_price = df['Close'].values[-2] if len(df) > 1 else current_price
if isinstance(prev_price, (list, np.ndarray)):
    prev_price = prev_price[0] if len(prev_price) > 0 else current_price
prev_price = float(prev_price)

high_price = df['High'].values[-1]
if isinstance(high_price, (list, np.ndarray)):
    high_price = high_price[0] if len(high_price) > 0 else current_price
high_price = float(high_price)

low_price = df['Low'].values[-1]
if isinstance(low_price, (list, np.ndarray)):
    low_price = low_price[0] if len(low_price) > 0 else current_price
low_price = float(low_price)

change = current_price - prev_price
change_pct = (change / prev_price) * 100 if prev_price != 0 else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("XAUUSD", f"${current_price:.2f}", f"{change:+.2f} ({change_pct:+.2f}%)")
col2.metric("High", f"${high_price:.2f}")
col3.metric("Low", f"${low_price:.2f}")
col4.metric("Data Points", f"{len(df)}")

st.header("📊 Live Price Chart")
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df.index, df['Close'].values, color='gold', linewidth=2)
ax.set_title('XAUUSD Price - Last 5 Days')
ax.set_ylabel('Price (USD)')
ax.set_xlabel('Date')
ax.grid(True, alpha=0.3)
plt.xticks(rotation=45)
st.pyplot(fig)

# Calculate RSI
close_values = df['Close'].values
delta = np.diff(close_values)
gain = np.where(delta > 0, delta, 0)
loss = np.where(delta < 0, -delta, 0)

window = 14
avg_gain = np.convolve(gain, np.ones(window)/window, mode='valid')
avg_loss = np.convolve(loss, np.ones(window)/window, mode='valid')
rs = avg_gain / (avg_loss + 1e-10)
rsi = 100 - (100 / (1 + rs))
current_rsi = float(rsi[-1]) if len(rsi) > 0 else 50

st.header("📈 Technical Summary")
col1, col2 = st.columns(2)

with col1:
    st.metric("Current Price", f"${current_price:.2f}")
    st.metric("24h Change", f"{change:+.2f}")

with col2:
    st.metric("RSI (14)", f"{current_rsi:.1f}")
    if current_rsi > 70:
        st.warning("⚠️ Overbought")
    elif current_rsi < 30:
        st.success("✅ Oversold")
    else:
        st.info("📊 Neutral")

st.sidebar.markdown("---")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.sidebar.warning("⚠️ Educational only - Not financial advice")

if st.sidebar.button("🔄 Refresh"):
    st.cache_data.clear()
    st.rerun()
