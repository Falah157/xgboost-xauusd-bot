import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="ADVANCED REAL INDICATORS DASHBOARD", layout="wide", page_icon="📊")

st.markdown("""
<style>
    .main-title { font-size: 1.8rem; font-weight: bold; background: linear-gradient(90deg, #ffd700, #ff8c00); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; }
    .indicator-card { background: #1e1e2e; border-radius: 12px; padding: 0.8rem; margin: 0.3rem 0; border-left: 3px solid; }
    .signal-buy { border-left-color: #00ff88; background: #0a3a2a22; }
    .signal-sell { border-left-color: #ff4444; background: #3a1a1a22; }
    .signal-neutral { border-left-color: #ffd700; }
    .level-card { background: #13161d; border-radius: 10px; padding: 0.5rem; text-align: center; }
    .level-price { font-size: 1rem; font-weight: bold; color: #ffd700; }
    .meter { background: #2a2e3a; border-radius: 10px; height: 6px; overflow: hidden; }
    .meter-fill { height: 100%; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📊 ADVANCED REAL INDICATORS DASHBOARD</div>', unsafe_allow_html=True)

# ============ CONFIGURATION ============
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
    return None

@st.cache_data(ttl=60)
def get_data(days=60):
    try:
        url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=1h&outputsize={days*24}&apikey={API_KEY}"
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

def calculate_all_real_indicators(df):
    """Calculate ALL REAL indicators from price data"""
    df = df.copy()
    
    # ============ 1. BASIC MOVING AVERAGES ============
    df['sma20'] = df['close'].rolling(20).mean()
    df['sma50'] = df['close'].rolling(50).mean()
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()
    df['ema50'] = df['close'].ewm(span=50).mean()
    
    # ============ 2. RSI ============
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # ============ 3. STOCHASTIC RSI (More accurate than regular RSI) ============
    # First get RSI, then apply stochastic formula
    rsi_min = df['rsi'].rolling(14).min()
    rsi_max = df['rsi'].rolling(14).max()
    df['stoch_rsi_k'] = 100 * ((df['rsi'] - rsi_min) / (rsi_max - rsi_min))
    df['stoch_rsi_d'] = df['stoch_rsi_k'].rolling(3).mean()
    
    # ============ 4. WILLIAMS %R ============
    high_14 = df['high'].rolling(14).max()
    low_14 = df['low'].rolling(14).min()
    df['williams_r'] = -100 * ((high_14 - df['close']) / (high_14 - low_14))
    
    # ============ 5. CCI (Commodity Channel Index) ============
    tp = (df['high'] + df['low'] + df['close']) / 3
    sma_tp = tp.rolling(20).mean()
    mad = tp.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean())
    df['cci'] = (tp - sma_tp) / (0.015 * mad)
    
    # ============ 6. MACD ============
    df['ema12'] = df['close'].ewm(span=12).mean()
    df['ema26'] = df['close'].ewm(span=26).mean()
    df['macd'] = df['ema12'] - df['ema26']
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    # ============ 7. BOLLINGER BANDS ============
    df['bb_middle'] = df['close'].rolling(20).mean()
    bb_std = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
    df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
    df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    
    # ============ 8. ATR ============
    df['hl'] = df['high'] - df['low']
    df['atr'] = df['hl'].rolling(14).mean()
    df['atr_percent'] = df['atr'] / df['close'] * 100
    
    # ============ 9. ICHIMOKU CLOUD (Simplified) ============
    df['tenkan_sen'] = (df['high'].rolling(9).max() + df['low'].rolling(9).min()) / 2
    df['kijun_sen'] = (df['high'].rolling(26).max() + df['low'].rolling(26).min()) / 2
    df['senkou_span_a'] = ((df['tenkan_sen'] + df['kijun_sen']) / 2).shift(26)
    df['senkou_span_b'] = ((df['high'].rolling(52).max() + df['low'].rolling(52).min()) / 2).shift(26)
    
    # ============ 10. ADX (Trend Strength) ============
    plus_dm = df['high'].diff()
    minus_dm = df['low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    atr = df['atr']
    df['plus_di'] = 100 * (plus_dm.rolling(14).mean() / atr)
    df['minus_di'] = 100 * (abs(minus_dm).rolling(14).mean() / atr)
    dx = (abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])) * 100
    df['adx'] = dx.rolling(14).mean()
    
    return df

def get_advanced_signal(df):
    """Generate signal using ALL real indicators"""
    if df is None or len(df) < 50:
        return "WAIT", 0, {}
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    buy_score = 0
    sell_score = 0
    details = {}
    
    # 1. Trend (SMA/EMA) - 20 points
    if last['close'] > last['sma20'] and last['sma20'] > last['sma50']:
        buy_score += 20
        details['trend'] = "BULLISH"
    elif last['close'] < last['sma20'] and last['sma20'] < last['sma50']:
        sell_score += 20
        details['trend'] = "BEARISH"
    else:
        details['trend'] = "NEUTRAL"
    
    # 2. RSI - 15 points
    if last['rsi'] < 30:
        buy_score += 15
        details['rsi'] = f"OVERSOLD ({last['rsi']:.1f})"
    elif last['rsi'] > 70:
        sell_score += 15
        details['rsi'] = f"OVERBOUGHT ({last['rsi']:.1f})"
    else:
        details['rsi'] = f"NEUTRAL ({last['rsi']:.1f})"
    
    # 3. Stochastic RSI - 15 points
    if last['stoch_rsi_k'] < 20:
        buy_score += 15
        details['stoch_rsi'] = f"OVERSOLD ({last['stoch_rsi_k']:.1f})"
    elif last['stoch_rsi_k'] > 80:
        sell_score += 15
        details['stoch_rsi'] = f"OVERBOUGHT ({last['stoch_rsi_k']:.1f})"
    else:
        details['stoch_rsi'] = f"NEUTRAL ({last['stoch_rsi_k']:.1f})"
    
    # 4. Williams %R - 10 points
    if last['williams_r'] < -80:
        buy_score += 10
        details['williams'] = f"OVERSOLD ({last['williams_r']:.1f})"
    elif last['williams_r'] > -20:
        sell_score += 10
        details['williams'] = f"OVERBOUGHT ({last['williams_r']:.1f})"
    else:
        details['williams'] = f"NEUTRAL ({last['williams_r']:.1f})"
    
    # 5. CCI - 10 points
    if last['cci'] < -100:
        buy_score += 10
        details['cci'] = f"OVERSOLD ({last['cci']:.1f})"
    elif last['cci'] > 100:
        sell_score += 10
        details['cci'] = f"OVERBOUGHT ({last['cci']:.1f})"
    else:
        details['cci'] = f"NEUTRAL ({last['cci']:.1f})"
    
    # 6. MACD - 10 points
    if last['macd'] > last['macd_signal'] and last['macd_hist'] > 0:
        buy_score += 10
        details['macd'] = "BULLISH"
    elif last['macd'] < last['macd_signal'] and last['macd_hist'] < 0:
        sell_score += 10
        details['macd'] = "BEARISH"
    else:
        details['macd'] = "NEUTRAL"
    
    # 7. Bollinger Bands - 10 points
    if last['close'] < last['bb_lower']:
        buy_score += 10
        details['bb'] = "BELOW LOWER (BUY)"
    elif last['close'] > last['bb_upper']:
        sell_score += 10
        details['bb'] = "ABOVE UPPER (SELL)"
    else:
        details['bb'] = "INSIDE BANDS"
    
    # 8. Ichimoku - 10 points
    if last['close'] > last['senkou_span_a'] and last['close'] > last['senkou_span_b']:
        buy_score += 10
        details['ichimoku'] = "ABOVE CLOUD"
    elif last['close'] < last['senkou_span_a'] and last['close'] < last['senkou_span_b']:
        sell_score += 10
        details['ichimoku'] = "BELOW CLOUD"
    else:
        details['ichimoku'] = "INSIDE CLOUD"
    
    # 9. ADX (Trend Strength) - 10 points (for confirmation)
    if last['adx'] > 25:
        details['adx'] = f"STRONG TREND ({last['adx']:.1f})"
        if buy_score > sell_score:
            buy_score += 5
        else:
            sell_score += 5
    else:
        details['adx'] = f"WEAK TREND ({last['adx']:.1f})"
    
    # 10. Momentum - 10 points
    if last['close'] > prev['close']:
        buy_score += 10
        details['momentum'] = "UP"
    else:
        sell_score += 10
        details['momentum'] = "DOWN"
    
    total_score = buy_score + sell_score
    confidence = max(buy_score, sell_score)
    
    if buy_score > sell_score and confidence >= 50:
        return "BUY", confidence, details
    elif sell_score > buy_score and confidence >= 50:
        return "SELL", confidence, details
    else:
        return "WAIT", confidence, details

def calculate_levels(price, atr, signal):
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
    rr = abs(tp2 - entry) / risk if risk > 0 else 0
    return entry, sl, tp1, tp2, tp3, tp4, risk, rr

# ============ MAIN APP ============
with st.spinner("Loading market data & calculating 10+ real indicators..."):
    df = get_data(60)
    current_price = get_price()
    
    if df is not None and len(df) > 50:
        df = calculate_all_real_indicators(df)
        current_price = current_price if current_price else float(df['close'].iloc[-1])
        atr = float(df['atr'].iloc[-1]) if not pd.isna(df['atr'].iloc[-1]) else current_price * 0.005
        
        # Get signal from all indicators
        signal, confidence, details = get_advanced_signal(df)
        
        # Calculate levels
        if signal != "WAIT":
            entry, sl, tp1, tp2, tp3, tp4, risk, rr = calculate_levels(current_price, atr, signal)
        else:
            entry, sl, tp1, tp2, tp3, tp4, risk, rr = current_price, current_price, current_price, current_price, current_price, current_price, 0, 0

# ============ DISPLAY ============
col1, col2, col3 = st.columns([1, 1.5, 1])

with col1:
    st.metric("XAUUSD", f"${current_price:.2f}")
    st.metric("ATR (14)", f"${atr:.2f}", f"{atr/current_price*100:.2f}%")
    
    st.markdown("### 📊 INDICATORS SUMMARY")
    
    # Indicator cards
    indicators = [
        ("RSI (14)", df['rsi'].iloc[-1], 30, 70),
        ("Stoch RSI", df['stoch_rsi_k'].iloc[-1], 20, 80),
        ("Williams %R", df['williams_r'].iloc[-1], -80, -20),
        ("CCI", df['cci'].iloc[-1], -100, 100),
        ("ADX", df['adx'].iloc[-1], 25, 25),
    ]
    
    for name, value, lower, upper in indicators:
        if value < lower:
            status = "🟢 OVERSOLD"
            color = "#00ff88"
        elif value > upper:
            status = "🔴 OVERBOUGHT"
            color = "#ff4444"
        else:
            status = "⚪ NEUTRAL"
            color = "#ffd700"
        
        st.markdown(f"""
        <div class="indicator-card" style="border-left-color: {color};">
            <b>{name}</b><br>
            <span style="font-size: 1.2rem;">{value:.1f}</span>
            <span style="float: right; color: {color};">{status}</span>
        </div>
        """, unsafe_allow_html=True)

with col2:
    # Signal Display
    st.markdown("### 🎯 SIGNAL")
    
    if signal == "BUY":
        st.markdown(f"""
        <div class="indicator-card signal-buy" style="text-align: center; padding: 1rem;">
            <div style="font-size: 2rem; font-weight: bold; color: #00ff88;">📈 BUY</div>
            <div>Confidence: {confidence:.0f}%</div>
            <div class="meter" style="margin-top: 0.5rem;"><div class="meter-fill" style="width: {confidence}%; background: #00ff88;"></div></div>
        </div>
        """, unsafe_allow_html=True)
    elif signal == "SELL":
        st.markdown(f"""
        <div class="indicator-card signal-sell" style="text-align: center; padding: 1rem;">
            <div style="font-size: 2rem; font-weight: bold; color: #ff4444;">📉 SELL</div>
            <div>Confidence: {confidence:.0f}%</div>
            <div class="meter" style="margin-top: 0.5rem;"><div class="meter-fill" style="width: {confidence}%; background: #ff4444;"></div></div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="indicator-card signal-neutral" style="text-align: center; padding: 1rem;">
            <div style="font-size: 2rem; font-weight: bold; color: #ffd700;">⏸️ WAIT</div>
            <div>Confidence: {confidence:.0f}%</div>
            <div class="meter" style="margin-top: 0.5rem;"><div class="meter-fill" style="width: {confidence}%; background: #ffd700;"></div></div>
        </div>
        """, unsafe_allow_html=True)
    
    # Trading Levels
    st.markdown("### 🎯 TRADING LEVELS")
    level_cols = st.columns(4)
    with level_cols[0]:
        st.markdown(f'<div class="level-card"><div class="level-price">📍 ENTRY<br>${entry:.2f}</div></div>', unsafe_allow_html=True)
    with level_cols[1]:
        st.markdown(f'<div class="level-card"><div class="level-price">🛑 SL<br>${sl:.2f}</div></div>', unsafe_allow_html=True)
    with level_cols[2]:
        st.markdown(f'<div class="level-card"><div class="level-price">🎯 TP2<br>${tp2:.2f}</div></div>', unsafe_allow_html=True)
    with level_cols[3]:
        st.markdown(f'<div class="level-card"><div class="level-price">📊 R:R<br>1:{rr:.1f}</div></div>', unsafe_allow_html=True)
    
    tp_cols = st.columns(4)
    with tp_cols[0]:
        st.markdown(f'<div class="level-card"><div class="level-price">TP1<br>${tp1:.2f}</div></div>', unsafe_allow_html=True)
    with tp_cols[1]:
        st.markdown(f'<div class="level-card"><div class="level-price">TP3<br>${tp3:.2f}</div></div>', unsafe_allow_html=True)
    with tp_cols[2]:
        st.markdown(f'<div class="level-card"><div class="level-price">TP4<br>${tp4:.2f}</div></div>', unsafe_allow_html=True)
    with tp_cols[3]:
        risk_amount = 10000 * 0.01
        position_size = risk_amount / risk if risk > 0 else 0
        st.markdown(f'<div class="level-card"><div class="level-price">SIZE<br>{position_size:.4f}</div></div>', unsafe_allow_html=True)

with col3:
    st.markdown("### 📋 SIGNAL DETAILS")
    
    for key, value in details.items():
        if "BUY" in str(value) or "BULLISH" in str(value) or "OVERSOLD" in str(value) or "UP" in str(value):
            color = "#00ff88"
            arrow = "🔼"
        elif "SELL" in str(value) or "BEARISH" in str(value) or "OVERBOUGHT" in str(value) or "DOWN" in str(value):
            color = "#ff4444"
            arrow = "🔽"
        else:
            color = "#ffd700"
            arrow = "➡️"
        
        st.markdown(f"""
        <div class="indicator-card" style="border-left-color: {color};">
            <b>{key.upper()}</b><br>
            <span style="color: {color};">{arrow} {value}</span>
        </div>
        """, unsafe_allow_html=True)

# ============ CHART ============
st.markdown("---")
st.markdown("### 📈 CHART WITH ALL INDICATORS")

fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                    row_heights=[0.5, 0.25, 0.25],
                    subplot_titles=("Price & Ichimoku Cloud", "RSI & Stochastic RSI", "MACD"))

# Price chart with Ichimoku
chart_df = df.tail(100)
fig.add_trace(go.Candlestick(x=chart_df.index, open=chart_df['open'], high=chart_df['high'], 
                              low=chart_df['low'], close=chart_df['close'], name='XAUUSD'), row=1, col=1)

# Add Ichimoku Cloud
fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['senkou_span_a'], name='Senkou A', line=dict(color='#00ff88', width=1)), row=1, col=1)
fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['senkou_span_b'], name='Senkou B', line=dict(color='#ff4444', width=1)), row=1, col=1)
fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['kijun_sen'], name='Kijun', line=dict(color='#ffd700', width=1, dash='dash')), row=1, col=1)

# RSI
fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['rsi'], name='RSI', line=dict(color='#9b59b6')), row=2, col=1)
fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

# Stochastic RSI
fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['stoch_rsi_k'], name='Stoch RSI K', line=dict(color='#00ff88')), row=2, col=1)
fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['stoch_rsi_d'], name='Stoch RSI D', line=dict(color='#ffd700')), row=2, col=1)

# MACD
fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['macd'], name='MACD', line=dict(color='#00ff88')), row=3, col=1)
fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['macd_signal'], name='Signal', line=dict(color='#ff4444')), row=3, col=1)
fig.add_trace(go.Bar(x=chart_df.index, y=chart_df['macd_hist'], name='Histogram', marker_color='#ffd700'), row=3, col=1)

# Add levels if signal exists
if signal != "WAIT":
    fig.add_hline(y=entry, line_color="#ffd700", line_width=2, annotation_text="ENTRY", row=1, col=1)
    fig.add_hline(y=sl, line_color="#ff4444", line_dash="dash", annotation_text="SL", row=1, col=1)

fig.update_layout(template='plotly_dark', height=800, showlegend=True)
fig.update_xaxes(title_text="Date/Time", row=3, col=1)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption("✅ Using 10+ REAL indicators: RSI, StochRSI, Williams %R, CCI, MACD, Bollinger, ATR, Ichimoku, ADX, EMA/SMA")
st.caption("⚠️ EDUCATIONAL ONLY - Not financial advice")
