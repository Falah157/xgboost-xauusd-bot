import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time
import threading
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="ULTIMATE XAUUSD TRADING SYSTEM", layout="wide", page_icon="🏆")

# Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    * { font-family: 'Inter', sans-serif; }
    
    .main-title { font-size: 1.8rem; font-weight: bold; background: linear-gradient(135deg, #ffd700, #ff8c00, #ff4444); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; }
    .signal-buy { background: linear-gradient(135deg, #0a3a2a, #0a2a1a); border-left: 4px solid #00ff88; border-radius: 12px; padding: 1rem; margin: 0.5rem 0; }
    .signal-sell { background: linear-gradient(135deg, #3a1a1a, #2a0a0a); border-left: 4px solid #ff4444; border-radius: 12px; padding: 1rem; margin: 0.5rem 0; }
    .signal-neutral { background: #1e1e2e; border-left: 4px solid #ffd700; border-radius: 12px; padding: 1rem; margin: 0.5rem 0; }
    .checklist-pass { background: #0a3a2a22; border-left: 3px solid #00ff88; padding: 0.5rem; margin: 0.3rem 0; border-radius: 8px; }
    .checklist-fail { background: #3a1a1a22; border-left: 3px solid #ff4444; padding: 0.5rem; margin: 0.3rem 0; border-radius: 8px; }
    .checklist-warn { background: #1e1e2e; border-left: 3px solid #ffd700; padding: 0.5rem; margin: 0.3rem 0; border-radius: 8px; }
    .level-card { background: #13161d; border-radius: 10px; padding: 0.5rem; text-align: center; border: 1px solid #2a2e3a; }
    .level-price { font-size: 1rem; font-weight: bold; color: #ffd700; }
    .meter { background: #2a2e3a; border-radius: 10px; height: 6px; overflow: hidden; }
    .meter-fill { height: 100%; border-radius: 10px; }
    .tf-card { background: #13161d; border-radius: 8px; padding: 0.3rem; text-align: center; cursor: pointer; border: 1px solid #2a2e3a; }
    .tf-active { border-color: #ffd700; background: #ffd70022; }
    .badge { display: inline-block; padding: 0.2rem 0.5rem; border-radius: 20px; font-size: 0.7rem; font-weight: 600; }
    .badge-buy { background: #00ff8822; color: #00ff88; }
    .badge-sell { background: #ff444422; color: #ff4444; }
    .badge-neutral { background: #ffd70022; color: #ffd700; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🏆 ULTIMATE XAUUSD TRADING SYSTEM</div>', unsafe_allow_html=True)

# ============ CONFIGURATION ============
API_KEY = "96871e27b094425f9ea104fa6eb2be64"
TELEGRAM_BOT_TOKEN = "8369393711:AAGm8ydfJc3UQPyNCPR6uCEr1LQpFw-zV-4"

# All Timeframes
TIMEFRAMES = {
    "1m": {"api": "1min", "minutes": 1, "send_interval": 1, "color": "#ff4444"},
    "5m": {"api": "5min", "minutes": 5, "send_interval": 5, "color": "#ff8844"},
    "15m": {"api": "15min", "minutes": 15, "send_interval": 15, "color": "#ffcc44"},
    "30m": {"api": "30min", "minutes": 30, "send_interval": 30, "color": "#ffff44"},
    "1h": {"api": "1h", "minutes": 60, "send_interval": 60, "color": "#88ff44"},
    "4h": {"api": "4h", "minutes": 240, "send_interval": 240, "color": "#44ff88"},
    "1d": {"api": "1day", "minutes": 1440, "send_interval": 1440, "color": "#44ffff"}
}

# Session State
if 'selected_tf' not in st.session_state:
    st.session_state.selected_tf = "1h"
if 'telegram_connected' not in st.session_state:
    st.session_state.telegram_connected = False
if 'telegram_chat_id' not in st.session_state:
    st.session_state.telegram_chat_id = None
if 'auto_send' not in st.session_state:
    st.session_state.auto_send = False
if 'last_signal_sent' not in st.session_state:
    st.session_state.last_signal_sent = {tf: None for tf in TIMEFRAMES.keys()}
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'all_signals' not in st.session_state:
    st.session_state.all_signals = []

# ============ TELEGRAM FUNCTIONS ============
def send_telegram(chat_id, msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}
        r = requests.post(url, json=payload, timeout=5)
        return r.status_code == 200
    except:
        return False

def get_telegram_updates():
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        r = requests.get(url, params={"timeout": 5}, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

# ============ DATA FUNCTIONS ============
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
def get_data(tf, days=30):
    try:
        tf_config = TIMEFRAMES[tf]
        minutes = tf_config["minutes"]
        total = min(int((days * 1440) / minutes), 500)
        url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval={tf_config['api']}&outputsize={total}&apikey={API_KEY}"
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
    except Exception as e:
        print(f"Error: {e}")
    return None

def calculate_indicators(df):
    df = df.copy()
    
    # MAs
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
    
    # MACD
    df['ema12'] = df['close'].ewm(span=12).mean()
    df['ema26'] = df['close'].ewm(span=26).mean()
    df['macd'] = df['ema12'] - df['ema26']
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    # ATR
    df['hl'] = df['high'] - df['low']
    df['atr'] = df['hl'].rolling(14).mean()
    
    # Bollinger
    df['bb_middle'] = df['close'].rolling(20).mean()
    bb_std = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
    df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
    
    # Stochastic RSI
    rsi_min = df['rsi'].rolling(14).min()
    rsi_max = df['rsi'].rolling(14).max()
    df['stoch_rsi'] = 100 * ((df['rsi'] - rsi_min) / (rsi_max - rsi_min))
    
    # Williams %R
    high_14 = df['high'].rolling(14).max()
    low_14 = df['low'].rolling(14).min()
    df['williams_r'] = -100 * ((high_14 - df['close']) / (high_14 - low_14))
    
    # ADX
    plus_dm = df['high'].diff()
    minus_dm = df['low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    atr = df['atr']
    df['plus_di'] = 100 * (plus_dm.rolling(14).mean() / atr)
    df['minus_di'] = 100 * (abs(minus_dm).rolling(14).mean() / atr)
    dx = (abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])) * 100
    df['adx'] = dx.rolling(14).mean()
    
    # Ichimoku
    df['tenkan'] = (df['high'].rolling(9).max() + df['low'].rolling(9).min()) / 2
    df['kijun'] = (df['high'].rolling(26).max() + df['low'].rolling(26).min()) / 2
    df['senkou_a'] = ((df['tenkan'] + df['kijun']) / 2).shift(26)
    df['senkou_b'] = ((df['high'].rolling(52).max() + df['low'].rolling(52).min()) / 2).shift(26)
    
    return df

# ============ SUPPLY & DEMAND ZONES ============
def find_supply_demand(df):
    """Find supply (resistance) and demand (support) zones"""
    highs = df['high'].values
    lows = df['low'].values
    length = len(highs)
    
    supply_zones = []
    demand_zones = []
    
    for i in range(5, length - 5):
        # Supply zone (resistance) - price rejected from high
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            supply_zones.append(highs[i])
        
        # Demand zone (support) - price rejected from low
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            demand_zones.append(lows[i])
    
    # Get most recent zones
    recent_supply = supply_zones[-3:] if supply_zones else []
    recent_demand = demand_zones[-3:] if demand_zones else []
    
    return recent_supply, recent_demand

# ============ BREAKOUT & FAKEOUT DETECTION ============
def detect_breakout_fakeout(df):
    """Detect breakout and fakeout patterns"""
    if len(df) < 20:
        return "NO_PATTERN", 0
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    range_high = df['high'].tail(20).max()
    range_low = df['low'].tail(20).min()
    
    # Breakout above resistance
    if last['close'] > range_high and prev['close'] <= range_high:
        # Check if it's fakeout (reversal within 2 candles)
        if len(df) > 1 and df['close'].iloc[-2] < range_high:
            return "BREAKOUT_UP", 70
    elif last['close'] < range_low and prev['close'] >= range_low:
        return "BREAKOUT_DOWN", 70
    
    # Fakeout detection (price broke then reversed)
    if len(df) > 3:
        if df['high'].iloc[-2] > range_high and last['close'] < range_high:
            return "FAKEOUT_UP", 80
        elif df['low'].iloc[-2] < range_low and last['close'] > range_low:
            return "FAKEOUT_DOWN", 80
    
    return "NO_PATTERN", 0

# ============ FIBONACCI LEVELS ============
def calculate_fibonacci(df):
    """Calculate Fibonacci levels from recent swing high/low"""
    recent_high = df['high'].tail(50).max()
    recent_low = df['low'].tail(50).min()
    diff = recent_high - recent_low
    
    return {
        '0.236': recent_low + diff * 0.236,
        '0.382': recent_low + diff * 0.382,
        '0.5': recent_low + diff * 0.5,
        '0.618': recent_low + diff * 0.618,
        '0.786': recent_low + diff * 0.786,
        '1.272': recent_high + diff * 0.272,
        '1.618': recent_high + diff * 0.618
    }

# ============ TRENDLINES ============
def find_trendlines(df):
    """Find basic trendlines"""
    if len(df) < 10:
        return None, None
    
    highs = df['high'].tail(20).values
    lows = df['low'].tail(20).values
    
    # Uptrend: higher lows
    uptrend = all(lows[i] < lows[i+1] for i in range(len(lows)-1))
    # Downtrend: lower highs
    downtrend = all(highs[i] > highs[i+1] for i in range(len(highs)-1))
    
    if uptrend:
        return "UPTREND", lows[-1]
    elif downtrend:
        return "DOWNTREND", highs[-1]
    else:
        return "SIDEWAYS", None

# ============ ORDER FLOW SIMULATION ============
def calculate_order_flow(df):
    """Simulate order flow based on price action"""
    if len(df) < 5:
        return {"buying": 50, "selling": 50, "imbalance": 0}
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Calculate buying/selling pressure
    buying_pressure = 0
    selling_pressure = 0
    
    # Up close = buying pressure
    if last['close'] > last['open']:
        buying_pressure = (last['close'] - last['open']) / last['open'] * 100
    else:
        selling_pressure = (last['open'] - last['close']) / last['open'] * 100
    
    # Volume confirmation (simulated)
    buying_pressure += 25 if last['close'] > prev['close'] else 0
    selling_pressure += 25 if last['close'] < prev['close'] else 0
    
    total = buying_pressure + selling_pressure
    if total > 0:
        buying_pct = (buying_pressure / total) * 100
        selling_pct = (selling_pressure / total) * 100
    else:
        buying_pct = 50
        selling_pct = 50
    
    return {
        "buying": buying_pct,
        "selling": selling_pct,
        "imbalance": buying_pct - selling_pct
    }

# ============ SIGNAL WITH CONFIRMATIONS ============
def get_signal_with_all_confirmations(df):
    """Generate signal with all confirmation checks"""
    if df is None or len(df) < 50:
        return "WAIT", 0, {}
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    buy_score = 0
    sell_score = 0
    confirmations = {}
    
    # 1. Trend (SMA/EMA) - 15 points
    if last['close'] > last['sma20'] and last['sma20'] > last['sma50']:
        buy_score += 15
        confirmations['trend'] = "BULLISH ✅"
    elif last['close'] < last['sma20'] and last['sma20'] < last['sma50']:
        sell_score += 15
        confirmations['trend'] = "BEARISH ✅"
    else:
        confirmations['trend'] = "NEUTRAL ⚠️"
    
    # 2. RSI - 15 points
    if last['rsi'] < 35:
        buy_score += 15
        confirmations['rsi'] = f"OVERSOLD ✅ ({last['rsi']:.1f})"
    elif last['rsi'] > 65:
        sell_score += 15
        confirmations['rsi'] = f"OVERBOUGHT ✅ ({last['rsi']:.1f})"
    else:
        confirmations['rsi'] = f"NEUTRAL ({last['rsi']:.1f})"
    
    # 3. MACD - 15 points
    if last['macd'] > last['macd_signal'] and last['macd_hist'] > 0:
        buy_score += 15
        confirmations['macd'] = "BULLISH ✅"
    elif last['macd'] < last['macd_signal'] and last['macd_hist'] < 0:
        sell_score += 15
        confirmations['macd'] = "BEARISH ✅"
    else:
        confirmations['macd'] = "NEUTRAL"
    
    # 4. Stochastic RSI - 10 points
    if last['stoch_rsi'] < 20:
        buy_score += 10
        confirmations['stoch_rsi'] = "OVERSOLD ✅"
    elif last['stoch_rsi'] > 80:
        sell_score += 10
        confirmations['stoch_rsi'] = "OVERBOUGHT ✅"
    else:
        confirmations['stoch_rsi'] = "NEUTRAL"
    
    # 5. Williams %R - 10 points
    if last['williams_r'] < -80:
        buy_score += 10
        confirmations['williams'] = "OVERSOLD ✅"
    elif last['williams_r'] > -20:
        sell_score += 10
        confirmations['williams'] = "OVERBOUGHT ✅"
    else:
        confirmations['williams'] = "NEUTRAL"
    
    # 6. ADX (Trend Strength) - 10 points
    if last['adx'] > 25:
        confirmations['adx'] = f"STRONG TREND ✅ ({last['adx']:.1f})"
        if buy_score > sell_score:
            buy_score += 10
        else:
            sell_score += 10
    else:
        confirmations['adx'] = f"WEAK TREND ({last['adx']:.1f})"
    
    # 7. Bollinger Bands - 10 points
    if last['close'] < last['bb_lower']:
        buy_score += 10
        confirmations['bb'] = "BELOW LOWER ✅"
    elif last['close'] > last['bb_upper']:
        sell_score += 10
        confirmations['bb'] = "ABOVE UPPER ✅"
    else:
        confirmations['bb'] = "INSIDE BANDS"
    
    # 8. Ichimoku - 10 points
    if last['close'] > last['senkou_a'] and last['close'] > last['senkou_b']:
        buy_score += 10
        confirmations['ichimoku'] = "ABOVE CLOUD ✅"
    elif last['close'] < last['senkou_a'] and last['close'] < last['senkou_b']:
        sell_score += 10
        confirmations['ichimoku'] = "BELOW CLOUD ✅"
    else:
        confirmations['ichimoku'] = "INSIDE CLOUD"
    
    # 9. Momentum - 10 points
    if last['close'] > prev['close']:
        buy_score += 10
        confirmations['momentum'] = "UP ✅"
    else:
        sell_score += 10
        confirmations['momentum'] = "DOWN ✅"
    
    total = buy_score + sell_score
    confidence = max(buy_score, sell_score)
    
    if buy_score > sell_score and confidence >= 60:
        return "BUY", confidence, confirmations
    elif sell_score > buy_score and confidence >= 60:
        return "SELL", confidence, confirmations
    else:
        return "WAIT", confidence, confirmations

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

def format_signal_for_telegram(signal, tf, entry, sl, tp1, tp2, tp3, tp4, confidence, confirmations):
    emoji = "📈" if signal == "BUY" else "📉"
    signal_text = "🟢 BUY (LONG)" if signal == "BUY" else "🔴 SELL (SHORT)"
    
    msg = f"""
{emoji} <b>XAUUSD TRADING SIGNAL</b> {emoji}

<b>Signal:</b> {signal_text}
<b>Timeframe:</b> {tf}
<b>Confidence:</b> {confidence:.0f}%

<b>━━━━━━━━━━━━━━</b>
<b>📍 ENTRY:</b> ${entry:.2f}
<b>🛑 STOP LOSS:</b> ${sl:.2f}

<b>🎯 TAKE PROFITS:</b>
• TP1: ${tp1:.2f}
• TP2: ${tp2:.2f}
• TP3: ${tp3:.2f}
• TP4: ${tp4:.2f}

<b>━━━━━━━━━━━━━━</b>
<i>⚠️ Risk management is essential!</i>
"""
    return msg

# ============ SIDEBAR ============
with st.sidebar:
    st.markdown("## ⚙️ CONTROL PANEL")
    
    # Telegram Connection
    st.markdown("### 🤖 TELEGRAM")
    if not st.session_state.telegram_connected:
        if st.button("📱 Connect", use_container_width=True):
            updates = get_telegram_updates()
            if updates and 'result' in updates and updates['result']:
                for upd in updates['result']:
                    if 'message' in upd and 'chat' in upd['message']:
                        chat_id = upd['message']['chat']['id']
                        st.session_state.telegram_chat_id = chat_id
                        st.session_state.telegram_connected = True
                        send_telegram(chat_id, "✅ Ultimate Trading Bot Connected!")
                        st.success("Connected!")
                        st.rerun()
                        break
            else:
                st.warning("Send a message to @BOACUTING first!")
    else:
        st.success("✅ Connected")
    
    st.markdown("---")
    
    # Auto Send Settings
    st.markdown("### 🚀 AUTO SIGNALS")
    st.session_state.auto_send = st.toggle("Auto-Send Signals to Telegram", value=st.session_state.auto_send)
    
    st.markdown("### 📊 ACTIVE TIMEFRAMES")
    active_tfs = {}
    tf_cols = st.columns(3)
    tf_list = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
    for i, tf in enumerate(tf_list):
        col = tf_cols[i % 3]
        with col:
            interval = TIMEFRAMES[tf]["send_interval"]
            active_tfs[tf] = st.checkbox(f"{tf} (every {interval}min)", value=True)
    
    st.markdown("---")
    st.markdown("### 💰 RISK")
    account_balance = st.number_input("Balance ($)", value=10000, step=1000)
    risk_percent = st.slider("Risk %", 0.5, 2.0, 1.0)
    
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ============ MAIN CONTENT ============
# Auto-signal loop
if st.session_state.auto_send and st.session_state.telegram_connected:
    current_time = datetime.now()
    for tf in tf_list:
        if not active_tfs.get(tf, True):
            continue
        
        interval = TIMEFRAMES[tf]["send_interval"]
        last_sent = st.session_state.last_signal_sent.get(tf)
        
        if last_sent is None:
            minutes_since = interval + 1
        else:
            minutes_since = (current_time - last_sent).total_seconds() / 60
        
        if minutes_since >= interval:
            df_tf = get_data(tf, 14)
            if df_tf is not None and len(df_tf) > 30:
                df_tf = calculate_indicators(df_tf)
                signal, confidence, confs = get_signal_with_all_confirmations(df_tf)
                
                if signal != "WAIT" and confidence >= 65:
                    price = get_price() or float(df_tf['close'].iloc[-1])
                    atr_val = float(df_tf['atr'].iloc[-1]) if not pd.isna(df_tf['atr'].iloc[-1]) else price * 0.005
                    entry, sl, tp1, tp2, tp3, tp4, risk, rr = calculate_levels(price, atr_val, signal)
                    
                    msg = format_signal_for_telegram(signal, tf, entry, sl, tp1, tp2, tp3, tp4, confidence, confs)
                    if send_telegram(st.session_state.telegram_chat_id, msg):
                        st.session_state.last_signal_sent[tf] = current_time
                        st.success(f"✅ {tf} signal sent to Telegram!")

# Display timeframe selector
st.markdown("### 📊 TIMEFRAME SELECTOR")
tf_cols = st.columns(7)
for i, tf in enumerate(["1m", "5m", "15m", "30m", "1h", "4h", "1d"]):
    with tf_cols[i]:
        active_class = "tf-active" if st.session_state.selected_tf == tf else ""
        if st.button(tf, key=f"main_tf_{tf}", use_container_width=True):
            st.session_state.selected_tf = tf
            st.cache_data.clear()
            st.rerun()

# Load data for selected timeframe
with st.spinner(f"Loading {st.session_state.selected_tf} data & analyzing..."):
    df = get_data(st.session_state.selected_tf, 60)
    current_price = get_price()
    
    if df is not None and len(df) > 50:
        df = calculate_indicators(df)
        current_price = current_price if current_price else float(df['close'].iloc[-1])
        atr = float(df['atr'].iloc[-1]) if not pd.isna(df['atr'].iloc[-1]) else current_price * 0.005
        
        # Get all analysis
        signal, confidence, confirmations = get_signal_with_all_confirmations(df)
        supply_zones, demand_zones = find_supply_demand(df)
        breakout_pattern, breakout_conf = detect_breakout_fakeout(df)
        fib_levels = calculate_fibonacci(df)
        trendline_type, trendline_price = find_trendlines(df)
        order_flow = calculate_order_flow(df)
        
        # Calculate levels
        if signal != "WAIT":
            entry, sl, tp1, tp2, tp3, tp4, risk, rr = calculate_levels(current_price, atr, signal)
        else:
            entry, sl, tp1, tp2, tp3, tp4, risk, rr = current_price, current_price, current_price, current_price, current_price, current_price, 0, 0

# ============ DISPLAY ============
# Top row - Price
col1, col2, col3, col4 = st.columns(4)
with col1:
    if current_price:
    st.metric("XAUUSD", f"${current_price:.2f}")
else:
    st.metric("XAUUSD", "Loading...")
with col2:
    st.metric("ATR (14)", f"${atr:.2f}", f"{atr/current_price*100:.2f}%")
with col3:
    st.metric("RSI (14)", f"{df['rsi'].iloc[-1]:.1f}")
with col4:
    st.metric("ADX", f"{df['adx'].iloc[-1]:.1f}", "Trending" if df['adx'].iloc[-1] > 25 else "Ranging")

# ============ SIGNAL DISPLAY ============
if signal == "BUY":
    st.markdown(f"""
    <div class="signal-buy">
        <span class="badge badge-buy">STRONG BUY</span>
        <div style="font-size: 1.5rem; font-weight: bold; margin-top: 0.5rem;">📈 BUY SIGNAL</div>
        <div>Confidence: {confidence:.0f}%</div>
        <div class="meter" style="margin-top: 0.5rem;"><div class="meter-fill" style="width: {confidence}%; background: #00ff88;"></div></div>
    </div>
    """, unsafe_allow_html=True)
elif signal == "SELL":
    st.markdown(f"""
    <div class="signal-sell">
        <span class="badge badge-sell">STRONG SELL</span>
        <div style="font-size: 1.5rem; font-weight: bold; margin-top: 0.5rem;">📉 SELL SIGNAL</div>
        <div>Confidence: {confidence:.0f}%</div>
        <div class="meter" style="margin-top: 0.5rem;"><div class="meter-fill" style="width: {confidence}%; background: #ff4444;"></div></div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown(f"""
    <div class="signal-neutral">
        <span class="badge badge-neutral">NEUTRAL</span>
        <div style="font-size: 1.5rem; font-weight: bold; margin-top: 0.5rem;">⏸️ WAIT</div>
        <div>Confidence: {confidence:.0f}%</div>
        <div class="meter" style="margin-top: 0.5rem;"><div class="meter-fill" style="width: {confidence}%; background: #ffd700;"></div></div>
    </div>
    """, unsafe_allow_html=True)

# ============ TRADING LEVELS ============
st.markdown("### 🎯 TRADING LEVELS")
level_cols = st.columns(6)
level_cols[0].markdown(f'<div class="level-card"><div class="level-price">📍 ENTRY<br>${entry:.2f}</div></div>', unsafe_allow_html=True)
level_cols[1].markdown(f'<div class="level-card"><div class="level-price">🛑 SL<br>${sl:.2f}</div></div>', unsafe_allow_html=True)
level_cols[2].markdown(f'<div class="level-card"><div class="level-price">🎯 TP1<br>${tp1:.2f}</div></div>', unsafe_allow_html=True)
level_cols[3].markdown(f'<div class="level-card"><div class="level-price">🎯 TP2<br>${tp2:.2f}</div></div>', unsafe_allow_html=True)
level_cols[4].markdown(f'<div class="level-card"><div class="level-price">🎯 TP3<br>${tp3:.2f}</div></div>', unsafe_allow_html=True)
level_cols[5].markdown(f'<div class="level-card"><div class="level-price">🎯 TP4<br>${tp4:.2f}</div></div>', unsafe_allow_html=True)

# Position sizing
position_size = (account_balance * (risk_percent / 100)) / risk if risk > 0 else 0
st.info(f"📊 Position Size: {position_size:.4f} lots | Risk Amount: ${account_balance * (risk_percent / 100):.2f} | R:R 1:{rr:.1f}")

# ============ CONFIRMATION CHECKLIST ============
st.markdown("### ✅ CONFIRMATION CHECKLIST")

col_left, col_right = st.columns(2)

with col_left:
    st.markdown("#### 📊 TECHNICAL CONFIRMATIONS")
    for key, value in confirmations.items():
        if "✅" in str(value):
            st.markdown(f'<div class="checklist-pass">✅ {key.upper()}: {value}</div>', unsafe_allow_html=True)
        elif "⚠️" in str(value):
            st.markdown(f'<div class="checklist-warn">⚠️ {key.upper()}: {value}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="checklist-fail">❌ {key.upper()}: {value}</div>', unsafe_allow_html=True)

with col_right:
    st.markdown("#### 📈 ORDER FLOW & PATTERNS")
    
    # Order Flow
    st.markdown(f"""
    <div class="checklist-pass" style="border-left-color: {'#00ff88' if order_flow['buying'] > order_flow['selling'] else '#ff4444'};">
        📊 ORDER FLOW: Buying {order_flow['buying']:.0f}% | Selling {order_flow['selling']:.0f}%<br>
        Imbalance: {'🟢 BUYING' if order_flow['imbalance'] > 0 else '🔴 SELLING'} ({abs(order_flow['imbalance']):.0f}%)
    </div>
    """, unsafe_allow_html=True)
    
    # Breakout/Fakeout
    if "BREAKOUT" in breakout_pattern:
        st.markdown(f'<div class="checklist-pass">🚀 BREAKOUT: {breakout_pattern} (Conf: {breakout_conf}%)</div>', unsafe_allow_html=True)
    elif "FAKEOUT" in breakout_pattern:
        st.markdown(f'<div class="checklist-warn">⚠️ FAKEOUT DETECTED: {breakout_pattern}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="checklist-fail">📉 NO BREAKOUT PATTERN</div>', unsafe_allow_html=True)
    
    # Trendline
    if trendline_type == "UPTREND":
        st.markdown(f'<div class="checklist-pass">📈 TRENDLINE: UPTREND (Support at ${trendline_price:.2f})</div>', unsafe_allow_html=True)
    elif trendline_type == "DOWNTREND":
        st.markdown(f'<div class="checklist-pass">📉 TRENDLINE: DOWNTREND (Resistance at ${trendline_price:.2f})</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="checklist-warn">➡️ TRENDLINE: SIDEWAYS</div>', unsafe_allow_html=True)
    
    # Supply/Demand
    if demand_zones:
        st.markdown(f'<div class="checklist-pass">🟢 DEMAND ZONES: ${", $".join([f"{z:.2f}" for z in demand_zones[-2:]])}</div>', unsafe_allow_html=True)
    if supply_zones:
        st.markdown(f'<div class="checklist-fail">🔴 SUPPLY ZONES: ${", $".join([f"{z:.2f}" for z in supply_zones[-2:]])}</div>', unsafe_allow_html=True)

# ============ FIBONACCI LEVELS ============
st.markdown("### 📊 FIBONACCI LEVELS")
fib_cols = st.columns(7)
for i, (level, price) in enumerate(fib_levels.items()):
    with fib_cols[i % 7]:
        st.markdown(f'<div class="level-card"><div class="level-price">{level}<br>${price:.2f}</div></div>', unsafe_allow_html=True)

# ============ CHART ============
st.markdown("### 📈 PROFESSIONAL CHART")

fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                    row_heights=[0.65, 0.35],
                    subplot_titles=("Price Action with Supply/Demand & Fibonacci", "RSI & Stochastic"))

chart_df = df.tail(100)

# Candlestick chart
fig.add_trace(go.Candlestick(x=chart_df.index, open=chart_df['open'], high=chart_df['high'],
                              low=chart_df['low'], close=chart_df['close'], name='XAUUSD'), row=1, col=1)

# Add Fibonacci levels
for level, price in fib_levels.items():
    fig.add_hline(y=price, line_color="#ffd700", line_dash="dot", line_width=0.8, 
                  annotation_text=level, annotation_position="right", row=1, col=1)

# Add Supply/Demand zones
for zone in supply_zones[-2:]:
    fig.add_hline(y=zone, line_color="#ff4444", line_dash="dash", line_width=1.5, 
                  annotation_text="SUPPLY", annotation_position="right", row=1, col=1)
for zone in demand_zones[-2:]:
    fig.add_hline(y=zone, line_color="#00ff88", line_dash="dash", line_width=1.5, 
                  annotation_text="DEMAND", annotation_position="right", row=1, col=1)

# Add trading levels if signal exists
if signal != "WAIT":
    fig.add_hline(y=entry, line_color="#ffd700", line_width=2, annotation_text="ENTRY", row=1, col=1)
    fig.add_hline(y=sl, line_color="#ff4444", line_dash="dash", annotation_text="SL", row=1, col=1)
    fig.add_hline(y=tp1, line_color="#00ff88", line_dash="dot", annotation_text="TP1", row=1, col=1)
    fig.add_hline(y=tp2, line_color="#00cc66", line_dash="dot", annotation_text="TP2", row=1, col=1)

# RSI
fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['rsi'], name='RSI', line=dict(color='#9b59b6')), row=2, col=1)
fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

# Stochastic RSI
fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['stoch_rsi'], name='Stoch RSI', line=dict(color='#ffd700')), row=2, col=1)
fig.add_hline(y=80, line_dash="dash", line_color="orange", row=2, col=1)
fig.add_hline(y=20, line_dash="dash", line_color="orange", row=2, col=1)

fig.update_layout(template='plotly_dark', height=700, showlegend=True)
fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
fig.update_yaxes(title_text="RSI", row=2, col=1)
st.plotly_chart(fig, use_container_width=True)

# ============ EXECUTE BUTTON ============
if signal != "WAIT":
    if st.button("✅ EXECUTE TRADE", type="primary", use_container_width=True):
        st.session_state.trade_history.append({
            'time': datetime.now(),
            'timeframe': st.session_state.selected_tf,
            'signal': signal,
            'entry': entry,
            'sl': sl,
            'tp2': tp2,
            'confidence': confidence
        })
        st.success(f"Trade recorded at ${entry:.2f}")
        st.balloons()

# ============ TRADE HISTORY ============
if st.session_state.trade_history:
    st.markdown("### 📋 RECENT TRADES")
    for trade in st.session_state.trade_history[-5:]:
        st.info(f"🎯 {trade['time'].strftime('%Y-%m-%d %H:%M:%S')} | {trade['timeframe']} | {trade['signal']} | Entry: ${trade['entry']:.2f} | TP: ${trade['tp2']:.2f} | Conf: {trade['confidence']:.0f}%")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 1rem; color: #666;">
    <p>🏆 ULTIMATE TRADING SYSTEM | All Timeframes | Auto Telegram Signals | Supply/Demand | Fibonacci | Order Flow | Breakout Detection</p>
    <p style="font-size: 0.7rem;">⚠️ EDUCATIONAL PURPOSES ONLY - Not financial advice</p>
</div>
""", unsafe_allow_html=True)
