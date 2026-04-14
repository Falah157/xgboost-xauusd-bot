import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import time
import threading
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="AUTO TELEGRAM TRADING BOT", layout="wide", page_icon="🤖")

st.markdown("""
<style>
    .main-header {
        font-size: 1.8rem;
        font-weight: bold;
        background: linear-gradient(90deg, #00ff88, #ffd700, #ff4444);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 0.5rem;
    }
    .timeframe-card {
        background: #1e1e2e;
        border-radius: 10px;
        padding: 0.5rem;
        margin: 0.2rem;
        text-align: center;
        border: 1px solid #333;
    }
    .signal-active {
        border-left: 4px solid #00ff88;
        background: #0a3a2a;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🤖 AUTO TELEGRAM TRADING BOT</div>', unsafe_allow_html=True)

# ============ CONFIGURATION ============
API_KEY = "96871e27b094425f9ea104fa6eb2be64"
TELEGRAM_BOT_TOKEN = "8369393711:AAGm8ydfJc3UQPyNCPR6uCEr1LQpFw-zV-4"

# Timeframe configurations with their send intervals (in minutes)
TIMEFRAMES_CONFIG = {
    "1m": {"api": "1min", "hours": 1/60, "days": 1, "send_interval": 1, "color": "#ff4444"},
    "5m": {"api": "5min", "hours": 5/60, "days": 3, "send_interval": 5, "color": "#ff8844"},
    "15m": {"api": "15min", "hours": 15/60, "days": 7, "send_interval": 15, "color": "#ffcc44"},
    "30m": {"api": "30min", "hours": 30/60, "days": 14, "send_interval": 30, "color": "#ffff44"},
    "1h": {"api": "1h", "hours": 1, "days": 30, "send_interval": 60, "color": "#88ff44"},
    "4h": {"api": "4h", "hours": 4, "days": 60, "send_interval": 240, "color": "#44ff88"},
    "1d": {"api": "1day", "hours": 24, "days": 180, "send_interval": 1440, "color": "#44ffff"}
}

# Session state
if 'telegram_connected' not in st.session_state:
    st.session_state.telegram_connected = False
if 'telegram_chat_id' not in st.session_state:
    st.session_state.telegram_chat_id = None
if 'last_signal_time' not in st.session_state:
    st.session_state.last_signal_time = {}
if 'auto_run' not in st.session_state:
    st.session_state.auto_run = False
if 'active_timeframes' not in st.session_state:
    st.session_state.active_timeframes = {tf: True for tf in TIMEFRAMES_CONFIG.keys()}

# ============ TELEGRAM FUNCTIONS ============
def send_telegram_message(chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except:
        return False

def get_telegram_updates():
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        response = requests.get(url, params={"timeout": 5}, timeout=10)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

def format_signal_message(direction, entry, sl, tp1, tp2, tp3, tp4, confidence, timeframe):
    emoji = "📈" if direction == "LONG" else "📉"
    signal_text = "🟢 BUY (LONG)" if direction == "LONG" else "🔴 SELL (SHORT)"
    return f"""
{emoji} <b>XAUUSD TRADING SIGNAL</b> {emoji}

<b>Signal:</b> {signal_text}
<b>Timeframe:</b> {timeframe}
<b>Confidence:</b> {confidence:.1%}

<b>━━━━━━━━━━━━━━</b>
<b>📍 ENTRY:</b> ${entry:.2f}
<b>🛑 STOP LOSS:</b> ${sl:.2f}

<b>🎯 TAKE PROFITS:</b>
• TP1: ${tp1:.2f}
• TP2: ${tp2:.2f}
• TP3: ${tp3:.2f}
• TP4: ${tp4:.2f}

<b>━━━━━━━━━━━━━━</b>
<i>⚠️ Risk management is essential!
🤖 Auto-Trading Bot</i>
"""

# ============ DATA FETCHING ============
@st.cache_data(ttl=30)
def get_realtime_price():
    try:
        url = f"https://api.twelvedata.com/price?symbol=XAU/USD&apikey={API_KEY}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return float(r.json()['price'])
    except:
        pass
    return None

@st.cache_data(ttl=60)
def get_historical_data(timeframe, period_days=None):
    try:
        tf_config = TIMEFRAMES_CONFIG[timeframe]
        days = period_days if period_days else tf_config["days"]
        api_interval = tf_config["api"]
        total_candles = min(int((days * 24) / tf_config["hours"]), 2000)
        url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval={api_interval}&outputsize={total_candles}&apikey={API_KEY}"
        r = requests.get(url, timeout=15)
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
        print(f"Error {timeframe}: {e}")
    return None

def calculate_indicators(df):
    df = df.copy()
    df['SMA_20'] = df['Close'].rolling(20).mean()
    df['SMA_50'] = df['Close'].rolling(50).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    df['EMA_12'] = df['Close'].ewm(span=12).mean()
    df['EMA_26'] = df['Close'].ewm(span=26).mean()
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    df['H-L'] = df['High'] - df['Low']
    df['H-PC'] = abs(df['High'] - df['Close'].shift())
    df['L-PC'] = abs(df['Low'] - df['Close'].shift())
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    df['ATR'] = df['TR'].rolling(14).mean()
    
    return df

def train_model(df, prediction_bars=4):
    features = ['RSI', 'MACD_Hist', 'ATR', 'SMA_20', 'SMA_50']
    df_clean = df.dropna()
    if len(df_clean) < 50:
        return None, None, None
    
    df_clean['Target'] = (df_clean['Close'].shift(-prediction_bars) > df_clean['Close']).astype(int)
    df_clean = df_clean.dropna()
    
    if len(df_clean) < 30:
        return None, None, None
    
    X = df_clean[features].values
    y = df_clean['Target'].values
    
    split = int(len(X) * 0.8)
    if split < 10:
        return None, None, None
    
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    
    model = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42)
    model.fit(X_train_scaled, y_train)
    accuracy = model.score(X_val_scaled, y_val) if len(X_val) > 0 else 0.5
    
    return model, scaler, accuracy

def get_signal(model, scaler, features):
    if model is None:
        return None, 0
    features_scaled = scaler.transform(features)
    prob = model.predict_proba(features_scaled)[0]
    pred = 1 if prob[1] > 0.55 else 0
    confidence = max(prob)
    return pred, confidence

def calculate_levels(price, atr, direction, timeframe):
    multipliers = {
        "1m": {"sl": 0.5, "tp": [0.8, 1.2, 1.8, 2.5]},
        "5m": {"sl": 0.6, "tp": [1.0, 1.5, 2.0, 3.0]},
        "15m": {"sl": 0.7, "tp": [1.2, 1.8, 2.5, 3.5]},
        "30m": {"sl": 0.8, "tp": [1.3, 2.0, 2.8, 4.0]},
        "1h": {"sl": 1.0, "tp": [1.5, 2.0, 3.0, 4.0]},
        "4h": {"sl": 1.2, "tp": [1.8, 2.5, 3.5, 5.0]},
        "1d": {"sl": 1.5, "tp": [2.0, 3.0, 4.0, 6.0]}
    }
    m = multipliers.get(timeframe, multipliers["1h"])
    
    if direction == "LONG":
        sl = price - (atr * m["sl"])
        tp1 = price + (atr * m["tp"][0])
        tp2 = price + (atr * m["tp"][1])
        tp3 = price + (atr * m["tp"][2])
        tp4 = price + (atr * m["tp"][3])
    else:
        sl = price + (atr * m["sl"])
        tp1 = price - (atr * m["tp"][0])
        tp2 = price - (atr * m["tp"][1])
        tp3 = price - (atr * m["tp"][2])
        tp4 = price - (atr * m["tp"][3])
    
    risk = abs(price - sl)
    return sl, tp1, tp2, tp3, tp4, risk

def analyze_timeframe(timeframe, min_confidence=0.60):
    """Analyze a single timeframe and return signal if any"""
    try:
        # Get data for this timeframe
        df = get_historical_data(timeframe)
        if df is None or len(df) < 30:
            return None
        
        df = calculate_indicators(df)
        
        pred_bars = {"1m": 12, "5m": 8, "15m": 4, "30m": 4, "1h": 4, "4h": 2, "1d": 1}
        model, scaler, accuracy = train_model(df, pred_bars.get(timeframe, 4))
        
        if model is None:
            return None
        
        current_price = get_realtime_price()
        if current_price is None:
            current_price = float(df['Close'].iloc[-1])
        
        atr = float(df['ATR'].iloc[-1]) if not pd.isna(df['ATR'].iloc[-1]) else current_price * 0.005
        
        features = ['RSI', 'MACD_Hist', 'ATR', 'SMA_20', 'SMA_50']
        latest_features = df[features].iloc[-1:].values
        prediction, confidence = get_signal(model, scaler, latest_features)
        
        if prediction is not None and confidence >= min_confidence:
            direction = "LONG" if prediction == 1 else "SHORT"
            sl, tp1, tp2, tp3, tp4, risk = calculate_levels(current_price, atr, direction, timeframe)
            
            return {
                'timeframe': timeframe,
                'direction': direction,
                'entry': current_price,
                'sl': sl,
                'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'tp4': tp4,
                'confidence': confidence,
                'timestamp': datetime.now()
            }
    except Exception as e:
        print(f"Error analyzing {timeframe}: {e}")
    
    return None

# ============ SIDEBAR ============
with st.sidebar:
    st.header("⚙️ CONTROL PANEL")
    
    # Telegram Connection
    st.subheader("🤖 TELEGRAM BOT")
    if not st.session_state.telegram_connected:
        st.info("💡 Send a message to @BOACUTING on Telegram")
        if st.button("📱 Connect Telegram", use_container_width=True):
            updates = get_telegram_updates()
            if updates and 'result' in updates and updates['result']:
                for update in updates['result']:
                    if 'message' in update and 'chat' in update['message']:
                        chat_id = update['message']['chat']['id']
                        st.session_state.telegram_chat_id = chat_id
                        st.session_state.telegram_connected = True
                        send_telegram_message(chat_id, "✅ AI Trading Bot Connected!\n\nI will send signals for all timeframes automatically!")
                        st.success(f"Connected! Chat ID: {chat_id}")
                        break
            else:
                st.warning("Send a message to @BOACUTING first!")
    else:
        st.success("✅ Connected to Telegram")
        if st.button("Disconnect", use_container_width=True):
            st.session_state.telegram_connected = False
            st.session_state.telegram_chat_id = None
            st.rerun()
    
    st.markdown("---")
    
    # Auto-Run Control
    st.subheader("🚀 AUTO SIGNALS")
    st.session_state.auto_run = st.toggle("Enable Auto-Signals", value=st.session_state.auto_run)
    
    min_conf = st.slider("Minimum Confidence (%)", 50, 80, 60) / 100
    
    st.markdown("---")
    st.subheader("📊 ACTIVE TIMEFRAMES")
    
    for tf in ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]:
        interval = TIMEFRAMES_CONFIG[tf]["send_interval"]
        st.session_state.active_timeframes[tf] = st.checkbox(f"{tf} (every {interval} min)", value=st.session_state.active_timeframes.get(tf, True))
    
    st.markdown("---")
    st.caption("Bot will automatically analyze each timeframe at its interval and send signals to Telegram!")

# ============ MAIN DISPLAY ============
# Show status of all timeframes
st.subheader("📊 TIMEFRAME STATUS")

cols = st.columns(7)
for i, tf in enumerate(["1m", "5m", "15m", "30m", "1h", "4h", "1d"]):
    with cols[i]:
        interval = TIMEFRAMES_CONFIG[tf]["send_interval"]
        active = st.session_state.active_timeframes.get(tf, True)
        last_time = st.session_state.last_signal_time.get(tf, None)
        
        status_color = "🟢" if active else "⚫"
        last_str = last_time.strftime("%H:%M") if last_time else "Never"
        
        st.markdown(f"""
        <div class="timeframe-card">
            <b>{tf}</b><br>
            {status_color} {interval}m<br>
            <small>Last: {last_str}</small>
        </div>
        """, unsafe_allow_html=True)

# Auto-send logic
if st.session_state.auto_run and st.session_state.telegram_connected:
    current_time = datetime.now()
    
    for tf in ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]:
        if not st.session_state.active_timeframes.get(tf, True):
            continue
        
        interval = TIMEFRAMES_CONFIG[tf]["send_interval"]
        last_time = st.session_state.last_signal_time.get(tf, datetime.min)
        minutes_since = (current_time - last_time).total_seconds() / 60
        
        if minutes_since >= interval:
            st.info(f"🔄 Analyzing {tf}...")
            
            # Analyze this timeframe
            signal = analyze_timeframe(tf, min_conf)
            
            if signal:
                # Send signal to Telegram
                message = format_signal_message(
                    signal['direction'], signal['entry'], signal['sl'],
                    signal['tp1'], signal['tp2'], signal['tp3'], signal['tp4'],
                    signal['confidence'], signal['timeframe']
                )
                
                if send_telegram_message(st.session_state.telegram_chat_id, message):
                    st.session_state.last_signal_time[tf] = current_time
                    st.success(f"✅ {tf} signal sent to Telegram!")
                    
                    # Also show in dashboard
                    with st.container():
                        st.markdown(f"""
                        <div class="signal-active" style="padding: 0.5rem; margin: 0.2rem 0; border-radius: 5px;">
                            <b>🎯 {tf.upper()} SIGNAL SENT</b><br>
                            {signal['direction']} @ ${signal['entry']:.2f} | Confidence: {signal['confidence']:.1%}
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info(f"📊 {tf}: No signal (confidence below {min_conf:.0%})")
                st.session_state.last_signal_time[tf] = current_time

# Manual test button for each timeframe
st.markdown("---")
st.subheader("🔧 MANUAL TEST")

test_cols = st.columns(7)
for i, tf in enumerate(["1m", "5m", "15m", "30m", "1h", "4h", "1d"]):
    with test_cols[i]:
        if st.button(f"Test {tf}", key=f"test_{tf}"):
            with st.spinner(f"Analyzing {tf}..."):
                signal = analyze_timeframe(tf, min_conf)
                if signal:
                    st.success(f"✅ {tf}: {signal['direction']} @ ${signal['entry']:.2f} ({signal['confidence']:.1%})")
                    if st.session_state.telegram_connected:
                        message = format_signal_message(
                            signal['direction'], signal['entry'], signal['sl'],
                            signal['tp1'], signal['tp2'], signal['tp3'], signal['tp4'],
                            signal['confidence'], signal['timeframe']
                        )
                        send_telegram_message(st.session_state.telegram_chat_id, message)
                        st.info(f"📱 Signal sent to Telegram!")
                else:
                    st.warning(f"❌ {tf}: No signal")

# Live status display
st.markdown("---")
st.subheader("📡 LIVE STATUS")

if st.session_state.auto_run:
    st.success("🚀 AUTO-SIGNALS ACTIVE - Bot is analyzing all timeframes!")
else:
    st.info("⏸️ AUTO-SIGNALS DISABLED - Enable in sidebar to start")

if st.session_state.telegram_connected:
    st.success(f"✅ Telegram Connected - Sending to Chat ID: {st.session_state.telegram_chat_id}")
else:
    st.warning("⚠️ Telegram NOT connected - Click 'Connect Telegram' in sidebar")

# Last signals summary
if st.session_state.last_signal_time:
    st.markdown("---")
    st.subheader("📜 LAST SIGNALS SENT")
    for tf, last_time in st.session_state.last_signal_time.items():
        if last_time and last_time > datetime.min:
            st.text(f"{tf}: {last_time.strftime('%Y-%m-%d %H:%M:%S')}")

# Footer
st.markdown("---")
st.caption("⚠️ EDUCATIONAL ONLY - Not financial advice. Bot auto-sends signals at each timeframe's interval!")
