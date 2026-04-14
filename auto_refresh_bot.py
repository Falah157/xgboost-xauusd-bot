import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import time
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="AUTO REFRESH TRADING BOT", layout="wide", page_icon="🤖", initial_sidebar_state="expanded")

# ============ CONFIGURATION ============
API_KEY = "96871e27b094425f9ea104fa6eb2be64"
TELEGRAM_BOT_TOKEN = "8369393711:AAGm8ydfJc3UQPyNCPR6uCEr1LQpFw-zV-4"

TIMEFRAMES_CONFIG = {
    "1m": {"api": "1min", "send_interval": 1, "color": "#ff4444"},
    "5m": {"api": "5min", "send_interval": 5, "color": "#ff8844"},
    "15m": {"api": "15min", "send_interval": 15, "color": "#ffcc44"},
    "30m": {"api": "30min", "send_interval": 30, "color": "#ffff44"},
    "1h": {"api": "1h", "send_interval": 60, "color": "#88ff44"},
    "4h": {"api": "4h", "send_interval": 240, "color": "#44ff88"},
    "1d": {"api": "1day", "send_interval": 1440, "color": "#44ffff"}
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
if 'page_refresh_counter' not in st.session_state:
    st.session_state.page_refresh_counter = 0

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
<i>⚠️ Risk management is essential!</i>
"""

# ============ DATA FUNCTIONS ============
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
def get_historical_data(timeframe):
    try:
        tf_config = TIMEFRAMES_CONFIG[timeframe]
        api_interval = tf_config["api"]
        url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval={api_interval}&outputsize=500&apikey={API_KEY}"
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
        print(f"Error: {e}")
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
    try:
        df = get_historical_data(timeframe)
        if df is None or len(df) < 30:
            return None
        
        df = calculate_indicators(df)
        pred_bars = {"1m": 12, "5m": 8, "15m": 4, "30m": 4, "1h": 4, "4h": 2, "1d": 1}
        model, scaler, _ = train_model(df, pred_bars.get(timeframe, 4))
        
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
                'sl': sl, 'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'tp4': tp4,
                'confidence': confidence,
                'timestamp': datetime.now()
            }
    except Exception as e:
        print(f"Error: {e}")
    return None

# ============ SIDEBAR ============
with st.sidebar:
    st.header("⚙️ CONTROL PANEL")
    
    # Telegram Connection
    st.subheader("🤖 TELEGRAM BOT")
    if not st.session_state.telegram_connected:
        if st.button("📱 Connect Telegram", use_container_width=True):
            updates = get_telegram_updates()
            if updates and 'result' in updates and updates['result']:
                for update in updates['result']:
                    if 'message' in update and 'chat' in update['message']:
                        chat_id = update['message']['chat']['id']
                        st.session_state.telegram_chat_id = chat_id
                        st.session_state.telegram_connected = True
                        send_telegram_message(chat_id, "✅ AI Trading Bot Connected!")
                        st.success(f"Connected!")
                        st.rerun()
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
    
    # Auto-Run Settings
    st.subheader("🚀 AUTO SIGNALS")
    
    # Data refresh interval
    refresh_interval = st.selectbox("Data Refresh (seconds)", [30, 60, 120, 300], index=1)
    
    # Auto-send toggle
    st.session_state.auto_run = st.toggle("Enable Auto-Signals", value=st.session_state.auto_run)
    
    min_conf = st.slider("Min Confidence (%)", 50, 80, 60) / 100
    
    st.markdown("---")
    st.subheader("📊 ACTIVE TIMEFRAMES")
    
    active_tfs = {}
    for tf in ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]:
        interval = TIMEFRAMES_CONFIG[tf]["send_interval"]
        active_tfs[tf] = st.checkbox(f"{tf} (every {interval} min)", value=True)
    
    st.markdown("---")
    
    # Auto-refresh countdown
    if 'last_check' not in st.session_state:
        st.session_state.last_check = datetime.now()
    
    time_since = (datetime.now() - st.session_state.last_check).total_seconds()
    next_refresh = max(0, refresh_interval - time_since)
    
    st.progress(1 - (next_refresh / refresh_interval) if refresh_interval > 0 else 0)
    st.caption(f"Next auto-check in: {int(next_refresh)} seconds")
    
    if st.button("🔄 Force Refresh Now", use_container_width=True):
        st.cache_data.clear()
        st.session_state.last_check = datetime.now()
        st.rerun()

# ============ MAIN ============
st.subheader("📊 LIVE SIGNAL STATUS")

# Auto-refresh logic
current_time = datetime.now()
time_since = (current_time - st.session_state.last_check).total_seconds()

if time_since >= refresh_interval:
    st.session_state.last_check = current_time
    st.cache_data.clear()
    
    # Check all timeframes
    if st.session_state.auto_run and st.session_state.telegram_connected:
        st.info("🔄 Running auto-analysis...")
        
        for tf in ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]:
            if not active_tfs.get(tf, True):
                continue
            
            interval = TIMEFRAMES_CONFIG[tf]["send_interval"]
            last_time = st.session_state.last_signal_time.get(tf, datetime.min)
            minutes_since = (current_time - last_time).total_seconds() / 60
            
            if minutes_since >= interval:
                signal = analyze_timeframe(tf, min_conf)
                if signal:
                    message = format_signal_message(
                        signal['direction'], signal['entry'], signal['sl'],
                        signal['tp1'], signal['tp2'], signal['tp3'], signal['tp4'],
                        signal['confidence'], signal['timeframe']
                    )
                    if send_telegram_message(st.session_state.telegram_chat_id, message):
                        st.session_state.last_signal_time[tf] = current_time
                        st.success(f"✅ {tf} signal sent!")
        
        st.rerun()

# Display current signals for each timeframe
cols = st.columns(7)
for i, tf in enumerate(["1m", "5m", "15m", "30m", "1h", "4h", "1d"]):
    with cols[i]:
        with st.spinner(f"Loading {tf}..."):
            signal = analyze_timeframe(tf, min_conf)
            if signal:
                color = "#00ff88" if signal['direction'] == "LONG" else "#ff4444"
                st.markdown(f"""
                <div style="background: #1e1e2e; border-radius: 10px; padding: 0.5rem; text-align: center; border-left: 4px solid {color};">
                    <b>{tf}</b><br>
                    <span style="color: {color}">{signal['direction']}</span><br>
                    <small>{signal['confidence']:.0%}</small>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background: #1e1e2e; border-radius: 10px; padding: 0.5rem; text-align: center;">
                    <b>{tf}</b><br>
                    <span style="color: #666">NO SIGNAL</span>
                </div>
                """, unsafe_allow_html=True)

# Status
st.markdown("---")
if st.session_state.auto_run and st.session_state.telegram_connected:
    st.success("🚀 BOT ACTIVE - Auto-refreshing every {} seconds!".format(refresh_interval))
elif not st.session_state.telegram_connected:
    st.warning("⚠️ Connect Telegram to start receiving signals")
else:
    st.info("⏸️ Auto-signals disabled - Enable in sidebar")

st.caption("⚠️ EDUCATIONAL ONLY - Not financial advice")
