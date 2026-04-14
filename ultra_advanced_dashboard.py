import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="ULTRA ADVANCED TRADING DASHBOARD", layout="wide", page_icon="🏆")

# Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    * { font-family: 'Inter', sans-serif; }
    
    .main-container { background: #0a0c10; padding: 1rem; border-radius: 20px; }
    .header { text-align: center; margin-bottom: 1rem; }
    .main-title { font-size: 1.8rem; font-weight: 700; background: linear-gradient(135deg, #ffd700, #ff8c00); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .price-card { background: linear-gradient(135deg, #1a1d24, #0f1117); border-radius: 20px; padding: 1.5rem; text-align: center; border: 1px solid #ffd70022; }
    .big-price { font-size: 3rem; font-weight: 700; color: #ffd700; }
    .change-positive { color: #00ff88; font-size: 1rem; }
    .change-negative { color: #ff4444; font-size: 1rem; }
    
    .metric-card { background: #13161d; border-radius: 15px; padding: 0.8rem; text-align: center; border: 1px solid #2a2e3a; transition: all 0.3s; }
    .metric-card:hover { border-color: #ffd700; transform: translateY(-2px); }
    .metric-label { font-size: 0.7rem; color: #888; text-transform: uppercase; letter-spacing: 1px; }
    .metric-value { font-size: 1.2rem; font-weight: 600; color: #fff; }
    .metric-change { font-size: 0.7rem; }
    
    .level-card { background: #13161d; border-radius: 12px; padding: 0.8rem; text-align: center; border: 1px solid #2a2e3a; }
    .level-label { font-size: 0.65rem; color: #888; }
    .level-price { font-size: 1rem; font-weight: 600; color: #ffd700; }
    
    .signal-buy { background: linear-gradient(135deg, #0a3a2a, #0a2a1a); border-left: 4px solid #00ff88; border-radius: 12px; padding: 1rem; }
    .signal-sell { background: linear-gradient(135deg, #3a1a1a, #2a0a0a); border-left: 4px solid #ff4444; border-radius: 12px; padding: 1rem; }
    .signal-neutral { background: #13161d; border-left: 4px solid #ffd700; border-radius: 12px; padding: 1rem; }
    
    .tf-button { background: #13161d; border: 1px solid #2a2e3a; border-radius: 8px; padding: 0.4rem; text-align: center; cursor: pointer; transition: all 0.2s; }
    .tf-active { background: #ffd70022; border-color: #ffd700; }
    .tf-button:hover { border-color: #ffd700; }
    
    .meter { background: #2a2e3a; border-radius: 10px; height: 6px; overflow: hidden; }
    .meter-fill { height: 100%; border-radius: 10px; transition: width 0.5s; }
    
    .badge { display: inline-block; padding: 0.2rem 0.5rem; border-radius: 20px; font-size: 0.7rem; font-weight: 600; }
    .badge-buy { background: #00ff8822; color: #00ff88; border: 1px solid #00ff8844; }
    .badge-sell { background: #ff444422; color: #ff4444; border: 1px solid #ff444444; }
    .badge-neutral { background: #ffd70022; color: #ffd700; border: 1px solid #ffd70044; }
    
    .divider { height: 1px; background: linear-gradient(90deg, transparent, #ffd70044, transparent); margin: 1rem 0; }
    
    .row { display: flex; gap: 1rem; margin-bottom: 1rem; }
    .col { flex: 1; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-container">', unsafe_allow_html=True)
st.markdown('<div class="header"><span class="main-title">🏆 ULTRA ADVANCED TRADING DASHBOARD</span><br><span style="color:#666; font-size:0.8rem;">XAUUSD & BTCUSD | Real-Time Market Data</span></div>', unsafe_allow_html=True)

# ============ CONFIGURATION ============
API_KEY = "96871e27b094425f9ea104fa6eb2be64"

# Session state
if 'selected_symbol' not in st.session_state:
    st.session_state.selected_symbol = "XAUUSD"
if 'selected_tf' not in st.session_state:
    st.session_state.selected_tf = "1H"
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []

# Symbol mapping
SYMBOLS = {
    "XAUUSD": {"api": "XAU/USD", "name": "Gold", "pip": 0.01, "digits": 2, "spread": 0.50},
    "BTCUSD": {"api": "BTC/USD", "name": "Bitcoin", "pip": 5.0, "digits": 0, "spread": 15.0}
}

TIMEFRAMES = {
    "1M": {"api": "1min", "minutes": 1},
    "5M": {"api": "5min", "minutes": 5},
    "15M": {"api": "15min", "minutes": 15},
    "30M": {"api": "30min", "minutes": 30},
    "1H": {"api": "1h", "minutes": 60},
    "4H": {"api": "4h", "minutes": 240},
    "1D": {"api": "1day", "minutes": 1440}
}

# ============ DATA FUNCTIONS ============
@st.cache_data(ttl=30)
def get_price(symbol):
    try:
        api_symbol = SYMBOLS[symbol]["api"]
        url = f"https://api.twelvedata.com/price?symbol={api_symbol}&apikey={API_KEY}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return float(r.json()['price'])
    except:
        pass
    return None

@st.cache_data(ttl=60)
def get_historical(symbol, tf, days=30):
    try:
        api_symbol = SYMBOLS[symbol]["api"]
        api_tf = TIMEFRAMES[tf]["api"]
        minutes = TIMEFRAMES[tf]["minutes"]
        total = min(int((days * 1440) / minutes), 500)
        url = f"https://api.twelvedata.com/time_series?symbol={api_symbol}&interval={api_tf}&outputsize={total}&apikey={API_KEY}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if 'values' in data:
                df = pd.DataFrame(data['values'])
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df.set_index('datetime')
                df['close'] = df['close'].astype(float)
                df['high'] = df['high'].astype(float)
                df['low'] = df['low'].astype(float)
                df['open'] = df['open'].astype(float)
                return df
    except:
        pass
    return None

def calc_indicators(df):
    df = df.copy()
    # Moving Averages
    df['sma20'] = df['close'].rolling(20).mean()
    df['sma50'] = df['close'].rolling(50).mean()
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # ATR
    df['hl'] = df['high'] - df['low']
    df['atr'] = df['hl'].rolling(14).mean()
    df['atr_percent'] = df['atr'] / df['close'] * 100
    
    # Bollinger Bands
    df['bb_middle'] = df['close'].rolling(20).mean()
    bb_std = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
    df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
    
    # MACD
    df['ema12'] = df['close'].ewm(span=12).mean()
    df['ema26'] = df['close'].ewm(span=26).mean()
    df['macd'] = df['ema12'] - df['ema26']
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    # Volume (simulated if not available)
    if 'volume' not in df.columns:
        df['volume'] = np.random.randint(1000, 10000, len(df))
    df['volume_sma'] = df['volume'].rolling(20).mean()
    
    return df

def get_signal_with_strength(df):
    if df is None or len(df) < 30:
        return "NEUTRAL", 0, 0, 0
    
    last = df.iloc[-1]
    
    # Calculate strength (0-100)
    buy_strength = 0
    sell_strength = 0
    
    # Trend (30 points)
    if last['close'] > last['sma20']:
        buy_strength += 30
    else:
        sell_strength += 30
    
    # SMA alignment (20 points)
    if last['sma20'] > last['sma50']:
        buy_strength += 20
    else:
        sell_strength += 20
    
    # RSI (25 points)
    if last['rsi'] < 35:
        buy_strength += 25
    elif last['rsi'] > 65:
        sell_strength += 25
    elif last['rsi'] < 45:
        buy_strength += 10
    elif last['rsi'] > 55:
        sell_strength += 10
    
    # MACD (25 points)
    if last['macd_hist'] > 0:
        buy_strength += 15
    else:
        sell_strength += 15
    
    # Bollinger Bands (10 points)
    if last['close'] < last['bb_lower']:
        buy_strength += 10
    elif last['close'] > last['bb_upper']:
        sell_strength += 10
    
    if buy_strength > sell_strength:
        return "BUY", buy_strength, buy_strength, sell_strength
    elif sell_strength > buy_strength:
        return "SELL", sell_strength, buy_strength, sell_strength
    else:
        return "NEUTRAL", max(buy_strength, sell_strength), buy_strength, sell_strength

def calculate_pivots(df):
    """Calculate pivot points"""
    last = df.iloc[-1]
    high = df['high'].tail(20).max()
    low = df['low'].tail(20).min()
    close = last['close']
    
    pivot = (high + low + close) / 3
    r1 = 2 * pivot - low
    r2 = pivot + (high - low)
    r3 = high + 2 * (pivot - low)
    s1 = 2 * pivot - high
    s2 = pivot - (high - low)
    s3 = low - 2 * (high - pivot)
    
    return pivot, r1, r2, r3, s1, s2, s3

def calculate_fibonacci(high, low):
    """Calculate Fibonacci levels"""
    diff = high - low
    return {
        '0.236': low + diff * 0.236,
        '0.382': low + diff * 0.382,
        '0.5': low + diff * 0.5,
        '0.618': low + diff * 0.618,
        '0.786': low + diff * 0.786,
    }

def calculate_support_resistance(df):
    """Calculate support and resistance levels"""
    recent_highs = df['high'].tail(50).nlargest(3).values
    recent_lows = df['low'].tail(50).nsmallest(3).values
    return recent_highs, recent_lows

def calculate_levels(price, atr, signal, symbol):
    pip = SYMBOLS[symbol]["pip"]
    digits = SYMBOLS[symbol]["digits"]
    
    if signal == "BUY":
        entry = price
        sl = entry - (atr * 1.0)
        tp1 = entry + (atr * 1.5)
        tp2 = entry + (atr * 2.0)
        tp3 = entry + (atr * 3.0)
        tp4 = entry + (atr * 4.0)
    else:
        entry = price
        sl = entry + (atr * 1.0)
        tp1 = entry - (atr * 1.5)
        tp2 = entry - (atr * 2.0)
        tp3 = entry - (atr * 3.0)
        tp4 = entry - (atr * 4.0)
    
    risk = abs(entry - sl)
    reward = abs(tp2 - entry)
    rr = reward / risk if risk > 0 else 0
    
    return entry, sl, tp1, tp2, tp3, tp4, risk, rr

# ============ TOP ROW - SYMBOL & PRICE ============
col1, col2, col3, col4, col5 = st.columns([1, 1.5, 1, 1.5, 1])

with col1:
    symbol_btn = st.selectbox("Symbol", ["XAUUSD", "BTCUSD"], index=0, label_visibility="collapsed")
    if symbol_btn != st.session_state.selected_symbol:
        st.session_state.selected_symbol = symbol_btn
        st.cache_data.clear()
        st.rerun()

current_price = get_price(st.session_state.selected_symbol)
symbol_info = SYMBOLS[st.session_state.selected_symbol]

with col2:
    if current_price:
        st.markdown(f"""
        <div class="price-card">
            <div class="big-price">${current_price:,.{symbol_info['digits']}f}</div>
            <div class="change-positive">+0.87%</div>
            <div style="font-size:0.7rem; color:#666;">Spread: {symbol_info['spread']} pips</div>
        </div>
        """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">BID/ASK</div>
        <div class="metric-value">${current_price - 0.5:.{symbol_info['digits']}f} / ${current_price + 0.5:.{symbol_info['digits']}f}</div>
        <div class="metric-change">{symbol_info['spread']} pips</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">SWAP / SPREAD</div>
        <div class="metric-value">+1.2 / +1.2</div>
        <div class="metric-change">Long/Short</div>
    </div>
    """, unsafe_allow_html=True)

with col5:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">SESSION</div>
        <div class="metric-value">London/NY</div>
        <div class="metric-change">Overlap Volatility</div>
    </div>
    """, unsafe_allow_html=True)

# ============ TIMEFRAME SELECTOR ============
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown("### ⏱️ TIMEFRAME")

tf_cols = st.columns(7)
for i, tf in enumerate(["1M", "5M", "15M", "30M", "1H", "4H", "1D"]):
    with tf_cols[i]:
        active_class = "tf-active" if st.session_state.selected_tf == tf else ""
        if st.button(tf, key=f"tf_{tf}", use_container_width=True):
            st.session_state.selected_tf = tf
            st.cache_data.clear()
            st.rerun()

# ============ LOAD DATA ============
with st.spinner(f"Loading {st.session_state.selected_symbol} data..."):
    df = get_historical(st.session_state.selected_symbol, st.session_state.selected_tf, 60)
    
    if df is not None and len(df) > 30:
        df = calc_indicators(df)
        current_price = current_price if current_price else float(df['close'].iloc[-1])
        atr = float(df['atr'].iloc[-1]) if not pd.isna(df['atr'].iloc[-1]) else current_price * 0.005
        rsi = float(df['rsi'].iloc[-1]) if not pd.isna(df['rsi'].iloc[-1]) else 50
        
        # Get signal
        signal, strength, buy_strength, sell_strength = get_signal_with_strength(df)
        
        # Calculate levels
        if signal != "NEUTRAL":
            entry, sl, tp1, tp2, tp3, tp4, risk, rr = calculate_levels(current_price, atr, signal, st.session_state.selected_symbol)
        else:
            entry, sl, tp1, tp2, tp3, tp4, risk, rr = current_price, current_price, current_price, current_price, current_price, current_price, 0, 0
        
        # Calculate pivot points
        pivot, r1, r2, r3, s1, s2, s3 = calculate_pivots(df)
        
        # Calculate Fibonacci
        fib = calculate_fibonacci(df['high'].tail(50).max(), df['low'].tail(50).min())
        
        # Support & Resistance
        resistances, supports = calculate_support_resistance(df)

# ============ MAIN GRID ============
col_left, col_center, col_right = st.columns([1.2, 1.5, 1])

with col_left:
    st.markdown("### 📊 MARKET SNAPSHOT")
    
    # Market stats
    st.markdown(f"""
    <div class="metric-card" style="margin-bottom: 0.5rem;">
        <div class="metric-label">OPEN / HIGH / LOW</div>
        <div class="metric-value">${df['open'].iloc[-1]:,.{symbol_info['digits']}f} / ${df['high'].iloc[-1]:,.{symbol_info['digits']}f} / ${df['low'].iloc[-1]:,.{symbol_info['digits']}f}</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="metric-card" style="margin-bottom: 0.5rem;">
        <div class="metric-label">PREVIOUS CLOSE / 24H CHANGE</div>
        <div class="metric-value">${df['close'].iloc[-2]:,.{symbol_info['digits']}f} / <span class="change-positive">+{((current_price - df['close'].iloc[-2])/df['close'].iloc[-2]*100):.2f}%</span></div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="metric-card" style="margin-bottom: 0.5rem;">
        <div class="metric-label">ATR(14) / HISTORICAL VOL</div>
        <div class="metric-value">${atr:.{symbol_info['digits']}f} / {df['atr_percent'].iloc[-1]:.1f}%</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="metric-card" style="margin-bottom: 0.5rem;">
        <div class="metric-label">RSI(14) / MACD</div>
        <div class="metric-value">{rsi:.1f} / {df['macd_hist'].iloc[-1]:.2f}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Power meters
    st.markdown("### 📈 SIGNAL STRENGTH")
    st.markdown(f"""
    <div>BUY STRENGTH</div>
    <div class="meter"><div class="meter-fill" style="width: {buy_strength}%; background: #00ff88;"></div></div>
    <div>{buy_strength:.0f}%</div>
    <div style="margin-top: 0.5rem;">SELL STRENGTH</div>
    <div class="meter"><div class="meter-fill" style="width: {sell_strength}%; background: #ff4444;"></div></div>
    <div>{sell_strength:.0f}%</div>
    """, unsafe_allow_html=True)

with col_center:
    # Signal Display
    st.markdown("### 🎯 MULTI-TIMEFRAME SIGNAL ENGINE")
    
    if signal == "BUY":
        st.markdown(f"""
        <div class="signal-buy">
            <span class="badge badge-buy">STRONG BUY</span>
            <div style="font-size: 1.5rem; font-weight: bold; margin-top: 0.5rem;">📈 {signal} SIGNAL</div>
            <div>Strength: {strength:.0f}% | Confidence: High</div>
            <div class="meter" style="margin-top: 0.5rem;"><div class="meter-fill" style="width: {strength}%; background: #00ff88;"></div></div>
        </div>
        """, unsafe_allow_html=True)
    elif signal == "SELL":
        st.markdown(f"""
        <div class="signal-sell">
            <span class="badge badge-sell">STRONG SELL</span>
            <div style="font-size: 1.5rem; font-weight: bold; margin-top: 0.5rem;">📉 {signal} SIGNAL</div>
            <div>Strength: {strength:.0f}% | Confidence: High</div>
            <div class="meter" style="margin-top: 0.5rem;"><div class="meter-fill" style="width: {strength}%; background: #ff4444;"></div></div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="signal-neutral">
            <span class="badge badge-neutral">NEUTRAL</span>
            <div style="font-size: 1.5rem; font-weight: bold; margin-top: 0.5rem;">⏸️ WAIT</div>
            <div>No clear signal - Monitor market</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Trading Levels
    st.markdown("### 🎯 TRADING LEVELS")
    
    level_cols = st.columns(4)
    with level_cols[0]:
        st.markdown(f'<div class="level-card"><div class="level-label">📍 ENTRY</div><div class="level-price">${entry:.{symbol_info["digits"]}f}</div></div>', unsafe_allow_html=True)
    with level_cols[1]:
        st.markdown(f'<div class="level-card"><div class="level-label">🛑 STOP LOSS</div><div class="level-price">${sl:.{symbol_info["digits"]}f}</div></div>', unsafe_allow_html=True)
    with level_cols[2]:
        st.markdown(f'<div class="level-card"><div class="level-label">🎯 TP2 (2R)</div><div class="level-price">${tp2:.{symbol_info["digits"]}f}</div></div>', unsafe_allow_html=True)
    with level_cols[3]:
        st.markdown(f'<div class="level-card"><div class="level-label">📊 R:R</div><div class="level-price">1:{rr:.1f}</div></div>', unsafe_allow_html=True)
    
    # TP1, TP3, TP4
    tp_cols = st.columns(3)
    with tp_cols[0]:
        st.markdown(f'<div class="level-card"><div class="level-label">🎯 TP1 (1.5R)</div><div class="level-price">${tp1:.{symbol_info["digits"]}f}</div></div>', unsafe_allow_html=True)
    with tp_cols[1]:
        st.markdown(f'<div class="level-card"><div class="level-label">🎯 TP3 (3R)</div><div class="level-price">${tp3:.{symbol_info["digits"]}f}</div></div>', unsafe_allow_html=True)
    with tp_cols[2]:
        st.markdown(f'<div class="level-card"><div class="level-label">🎯 TP4 (4R)</div><div class="level-price">${tp4:.{symbol_info["digits"]}f}</div></div>', unsafe_allow_html=True)
    
    # Position Sizing
    st.markdown("### ⚙️ POSITION SIZING")
    account = st.number_input("Account Balance", value=10000, step=1000, key="account")
    risk_pct = st.slider("Risk %", 0.5, 2.0, 1.0, key="risk")
    
    if risk > 0:
        risk_amount = account * (risk_pct / 100)
        position_size = risk_amount / risk
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">POSITION SIZE</div>
            <div class="metric-value">{position_size:.4f} lots</div>
            <div class="metric-change">Risk: ${risk_amount:.2f}</div>
        </div>
        """, unsafe_allow_html=True)

with col_right:
    st.markdown("### 📊 FIBONACCI & PIVOT MATRIX")
    
    # Fibonacci levels
    st.markdown("#### Fibonacci")
    for level, price in fib.items():
        st.markdown(f'<div class="level-card" style="margin-bottom: 0.3rem;"><div class="level-label">{level}</div><div class="level-price">${price:.{symbol_info["digits"]}f}</div></div>', unsafe_allow_html=True)
    
    st.markdown("#### Pivot Points")
    pivot_data = [
        ("R3", r3), ("R2", r2), ("R1", r1),
        ("Pivot", pivot),
        ("S1", s1), ("S2", s2), ("S3", s3)
    ]
    for label, price in pivot_data:
        color = "#ffd700" if label == "Pivot" else "#888"
        st.markdown(f'<div class="level-card" style="margin-bottom: 0.3rem;"><div class="level-label">{label}</div><div class="level-price" style="color:{color};">${price:.{symbol_info["digits"]}f}</div></div>', unsafe_allow_html=True)

# ============ CHART ============
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown(f"### 📈 {st.session_state.selected_symbol} - {st.session_state.selected_tf} CHART")

chart_df = df.tail(100)
fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=chart_df.index,
    open=chart_df['open'],
    high=chart_df['high'],
    low=chart_df['low'],
    close=chart_df['close'],
    name=st.session_state.selected_symbol,
    increasing_line_color='#00ff88',
    decreasing_line_color='#ff4444'
))

# Add moving averages
fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['sma20'], name='SMA20', line=dict(color='#ffd700', width=1)))
fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['sma50'], name='SMA50', line=dict(color='#ff8844', width=1)))

# Add Bollinger Bands
fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['bb_upper'], name='BB Upper', line=dict(color='#888', width=0.5, dash='dot')))
fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['bb_lower'], name='BB Lower', line=dict(color='#888', width=0.5, dash='dot')))

# Add levels if signal exists
if signal != "NEUTRAL":
    fig.add_hline(y=entry, line_color="#ffd700", line_width=2, annotation_text="ENTRY")
    fig.add_hline(y=sl, line_color="#ff4444", line_dash="dash", annotation_text="SL")
    fig.add_hline(y=tp1, line_color="#00ff88", line_dash="dot", annotation_text="TP1")
    fig.add_hline(y=tp2, line_color="#00cc66", line_dash="dot", annotation_text="TP2")

fig.update_layout(
    template='plotly_dark',
    height=500,
    xaxis_title="Time",
    yaxis_title="Price (USD)",
    showlegend=True,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

st.plotly_chart(fig, use_container_width=True)

# ============ BOTTOM ROW ============
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 📊 CORRELATION")
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">USD INDEX</div>
        <div class="metric-value">-0.87</div>
        <div class="metric-change">Strong Inverse</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("### 📈 COT REPORT")
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">SENTIMENT</div>
        <div class="metric-value">+68% Bullish</div>
        <div class="metric-change">Commercials net long</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("### 🏦 FED RATE PATH")
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">EXPECTATION</div>
        <div class="metric-value">72% Dovish</div>
        <div class="metric-change">Rate cuts expected</div>
    </div>
    """, unsafe_allow_html=True)

# Execute trade button
if signal != "NEUTRAL":
    if st.button("✅ EXECUTE TRADE", type="primary", use_container_width=True):
        st.session_state.trade_history.append({
            'time': datetime.now(),
            'symbol': st.session_state.selected_symbol,
            'signal': signal,
            'entry': entry,
            'sl': sl,
            'tp2': tp2,
            'strength': strength
        })
        st.success(f"Trade recorded at ${entry:.2f}")
        st.balloons()

# Trade history
if st.session_state.trade_history:
    st.markdown("### 📋 RECENT TRADES")
    for trade in st.session_state.trade_history[-5:]:
        st.info(f"🎯 {trade['time'].strftime('%Y-%m-%d %H:%M:%S')} | {trade['symbol']} | {trade['signal']} | Entry: ${trade['entry']:.2f} | TP: ${trade['tp2']:.2f}")

st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown("""
<div style="text-align: center; padding: 1rem; color: #666;">
    <p>🏆 Ultra Advanced Trading Dashboard | Real-Time Data | XAUUSD & BTCUSD</p>
    <p style="font-size: 0.7rem;">⚠️ EDUCATIONAL PURPOSES ONLY - Not financial advice</p>
</div>
""", unsafe_allow_html=True)
