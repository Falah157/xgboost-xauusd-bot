import streamlit as st
import pandas as pd
import numpy as np
import requests
import matplotlib.pyplot as plt
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="XAUUSD Trading Dashboard", layout="wide")
st.title("🏆 XAUUSD Professional Trading Dashboard")

# Get live price
@st.cache_data(ttl=30)
def get_live_price():
    try:
        response = requests.get("https://api.gold-api.com/price/XAUUSD", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return float(data.get('price', 1932.50))
    except:
        pass
    # Demo price with small random movement
    base = 1932.50
    return base + np.random.randn() * 1.5

@st.cache_data(ttl=300)
def generate_data():
    dates = pd.date_range(end=datetime.now(), periods=100, freq='h')
    base = 1900
    trends = np.cumsum(np.random.randn(100) * 1.2)
    prices = base + trends + np.sin(np.arange(100) * 0.3) * 8
    return pd.DataFrame({'Close': prices}, index=dates)

# Calculate technical indicators
def calculate_indicators(df):
    df = df.copy()
    df['SMA_20'] = df['Close'].rolling(20).mean()
    df['SMA_50'] = df['Close'].rolling(50).mean()
    df['EMA_9'] = df['Close'].ewm(span=9).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    df['EMA_12'] = df['Close'].ewm(span=12).mean()
    df['EMA_26'] = df['Close'].ewm(span=26).mean()
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['Signal'] = df['MACD'].ewm(span=9).mean()
    
    # Bollinger Bands
    df['BB_Middle'] = df['Close'].rolling(20).mean()
    bb_std = df['Close'].rolling(20).std()
    df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
    df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
    
    return df

def determine_trend(df):
    """Determine market trend"""
    current = df['Close'].iloc[-1]
    sma20 = df['SMA_20'].iloc[-1]
    sma50 = df['SMA_50'].iloc[-1]
    rsi = df['RSI'].iloc[-1]
    
    if current > sma20 and current > sma50 and rsi > 50:
        return "📈 BULLISH", "green"
    elif current < sma20 and current < sma50 and rsi < 50:
        return "📉 BEARISH", "red"
    else:
        return "➡️ SIDEWAYS", "orange"

def calculate_levels(price, trend, risk_reward_ratios=[2, 3, 4, 5]):
    """Calculate Entry, SL, and TP levels"""
    atr = price * 0.005  # 0.5% ATR approximation
    
    if "BULLISH" in trend:
        entry = price
        sl = price - atr
        tps = {f"{r}R": price + (atr * r) for r in risk_reward_ratios}
        direction = "LONG"
    else:
        entry = price
        sl = price + atr
        tps = {f"{r}R": price - (atr * r) for r in risk_reward_ratios}
        direction = "SHORT"
    
    return entry, sl, tps, direction

# Load data
with st.spinner("Analyzing XAUUSD..."):
    current_price = get_live_price()
    df = generate_data()
    df = calculate_indicators(df)
    trend, trend_color = determine_trend(df)

# Main metrics
st.metric("LIVE XAUUSD", f"${current_price:.2f}", 
          f"{current_price - df['Close'].iloc[-2]:+.2f}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("RSI (14)", f"{df['RSI'].iloc[-1]:.1f}")
col2.metric("SMA 20", f"${df['SMA_20'].iloc[-1]:.2f}")
col3.metric("SMA 50", f"${df['SMA_50'].iloc[-1]:.2f}")
col4.metric("Trend", trend)

# Trading Levels
st.header("🎯 TRADING SETUP")

entry, sl, tp_levels, direction = calculate_levels(current_price, trend)

# Display levels in a nice table
st.subheader(f"📍 {direction} Setup")

col1, col2 = st.columns(2)
with col1:
    st.metric("ENTRY", f"${entry:.2f}", "Suggested Entry")
    st.metric("STOP LOSS", f"${sl:.2f}", f"Risk: ${abs(entry - sl):.2f}")

with col2:
    st.metric("RISK:REWARD", "1:2 to 1:5", "Multiple Targets")

st.subheader("🎯 TAKE PROFIT LEVELS")
tp_cols = st.columns(len(tp_levels))
for idx, (label, tp) in enumerate(tp_levels.items()):
    with tp_cols[idx]:
        profit = abs(tp - entry)
        st.metric(label, f"${tp:.2f}", f"+${profit:.2f}")

# Visual representation
st.subheader("📊 Price Levels Visualization")
fig, ax = plt.subplots(figsize=(12, 3))
ax.axhline(y=entry, color='blue', linestyle='-', linewidth=2, label=f'Entry: ${entry:.2f}')
ax.axhline(y=sl, color='red', linestyle='--', linewidth=2, label=f'SL: ${sl:.2f}')
colors = ['green', 'lightgreen', 'darkgreen', 'olive']
for idx, (label, tp) in enumerate(tp_levels.items()):
    ax.axhline(y=tp, color=colors[idx % len(colors)], linestyle=':', linewidth=1.5, label=f'{label}: ${tp:.2f}')
ax.axhline(y=current_price, color='gold', linewidth=3, alpha=0.7, label=f'Current: ${current_price:.2f}')
ax.set_ylabel('Price (USD)')
ax.set_title('Trading Levels')
ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))
ax.grid(True, alpha=0.3)
st.pyplot(fig)

# Price Chart
st.header("📈 Technical Analysis Chart")
fig2, ax2 = plt.subplots(figsize=(12, 5))
ax2.plot(df.index, df['Close'], color='gold', linewidth=2, label='XAUUSD')
ax2.plot(df.index, df['SMA_20'], 'blue', linestyle='--', linewidth=1, label='SMA 20')
ax2.plot(df.index, df['SMA_50'], 'red', linestyle='--', linewidth=1, label='SMA 50')
ax2.fill_between(df.index, df['BB_Upper'], df['BB_Lower'], alpha=0.1, color='gray')
ax2.set_ylabel('Price (USD)')
ax2.legend()
ax2.grid(True, alpha=0.3)
plt.xticks(rotation=45)
st.pyplot(fig2)

# Trade Recommendations
st.header("📋 TRADE RECOMMENDATION")

if trend == "📈 BULLISH":
    st.success("""
    ✅ **BUY (LONG) Setup**
    - Entry: Market price or limit at support
    - Stop Loss: Below recent low or ${:.2f}
    - Target 1 (2R): ${:.2f}
    - Target 2 (3R): ${:.2f}
    - Target 3 (4R): ${:.2f}
    - Target 4 (5R): ${:.2f}
    """.format(sl, tp_levels.get('2R', 0), tp_levels.get('3R', 0), 
               tp_levels.get('4R', 0), tp_levels.get('5R', 0)))
elif trend == "📉 BEARISH":
    st.error("""
    ❌ **SELL (SHORT) Setup**
    - Entry: Market price or limit at resistance
    - Stop Loss: Above recent high or ${:.2f}
    - Target 1 (2R): ${:.2f}
    - Target 2 (3R): ${:.2f}
    - Target 3 (4R): ${:.2f}
    - Target 4 (5R): ${:.2f}
    """.format(sl, tp_levels.get('2R', 0), tp_levels.get('3R', 0),
               tp_levels.get('4R', 0), tp_levels.get('5R', 0)))
else:
    st.warning("⚠️ Market is sideways - Wait for clear breakout")

# Sidebar
st.sidebar.header("⚙️ Settings")
risk_percent = st.sidebar.slider("Risk per trade (%)", 0.5, 3.0, 1.0)
account_size = st.sidebar.number_input("Account Size ($)", value=10000)

risk_amount = account_size * (risk_percent / 100)
position_size = risk_amount / abs(entry - sl)

st.sidebar.metric("Position Size", f"{position_size:.2f} units")
st.sidebar.metric("Risk Amount", f"${risk_amount:.2f}")

st.sidebar.markdown("---")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.sidebar.warning("⚠️ Educational only - Not financial advice")

if st.sidebar.button("🔄 Refresh Analysis"):
    st.cache_data.clear()
    st.rerun()
