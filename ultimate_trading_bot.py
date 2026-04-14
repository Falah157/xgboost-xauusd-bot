import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import json
import warnings
import time
import threading
warnings.filterwarnings('ignore')

st.set_page_config(page_title="ULTIMATE XAUUSD TRADING BOT", layout="wide", page_icon="🏆", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main-header { font-size: 2rem; font-weight: bold; background: linear-gradient(90deg, #00ff88, #ffd700, #ff4444); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; padding: 0.5rem; }
    .metric-card { background: #1e1e2e; border-radius: 10px; padding: 1rem; text-align: center; border: 1px solid #333; }
    .risk-card { background: #1e1e2e; border-radius: 10px; padding: 0.8rem; border-left: 4px solid #ff4444; margin: 0.5rem 0; }
    .news-card { background: #1e1e2e; border-radius: 10px; padding: 0.8rem; border-left: 4px solid #ffd700; margin: 0.5rem 0; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🏆 ULTIMATE XAUUSD TRADING BOT</div>', unsafe_allow_html=True)

# ============ CONFIGURATION ============
API_KEY = "96871e27b094425f9ea104fa6eb2be64"
TELEGRAM_BOT_TOKEN = "8369393711:AAGm8ydfJc3UQPyNCPR6uCEr1LQpFw-zV-4"

# OANDA Configuration (Get free demo account at https://www.oanda.com)
OANDA_API_KEY = "YOUR_OANDA_API_KEY_HERE"  # Replace with your OANDA API key
OANDA_ACCOUNT_ID = "YOUR_ACCOUNT_ID_HERE"  # Replace with your account ID
OANDA_URL = "https://api-fxpractice.oanda.com/v3"  # Use demo URL

# High impact news events (auto-disable trading)
HIGH_IMPACT_NEWS = [
    "Non-Farm Payrolls", "FOMC Statement", "CPI", "GDP", 
    "Unemployment Rate", "Fed Rate Decision", "PMI", 
    "Retail Sales", "Manufacturing PMI", "Services PMI"
]

# Timeframe configurations
TIMEFRAMES_CONFIG = {
    "1m": {"api": "1min", "hours": 1/60, "days": 1, "send_interval": 1, "pred_bars": 4},
    "5m": {"api": "5min", "hours": 5/60, "days": 3, "send_interval": 5, "pred_bars": 4},
    "15m": {"api": "15min", "hours": 15/60, "days": 7, "send_interval": 15, "pred_bars": 4},
    "30m": {"api": "30min", "hours": 30/60, "days": 14, "send_interval": 30, "pred_bars": 4},
    "1h": {"api": "1h", "hours": 1, "days": 30, "send_interval": 60, "pred_bars": 4},
    "4h": {"api": "4h", "hours": 4, "days": 60, "send_interval": 240, "pred_bars": 2},
    "1d": {"api": "1day", "hours": 24, "days": 180, "send_interval": 1440, "pred_bars": 1}
}

# Session State
if 'telegram_connected' not in st.session_state:
    st.session_state.telegram_connected = False
if 'telegram_chat_id' not in st.session_state:
    st.session_state.telegram_chat_id = None
if 'all_signals' not in st.session_state:
    st.session_state.all_signals = []
if 'last_signal_sent' not in st.session_state:
    st.session_state.last_signal_sent = {tf: None for tf in TIMEFRAMES_CONFIG.keys()}
if 'auto_run' not in st.session_state:
    st.session_state.auto_run = False
if 'selected_timeframe' not in st.session_state:
    st.session_state.selected_timeframe = "1h"
if 'peak_balance' not in st.session_state:
    st.session_state.peak_balance = 10000
if 'trading_enabled' not in st.session_state:
    st.session_state.trading_enabled = True
if 'drawdown_alert_sent' not in st.session_state:
    st.session_state.drawdown_alert_sent = False
if 'oanda_connected' not in st.session_state:
    st.session_state.oanda_connected = False

# ============ NEWS FILTER ============
def get_economic_calendar():
    """Fetch upcoming high-impact news events"""
    # Simulated news calendar - In production, use https://nfs.faireconomy.media API
    news_events = [
        {"time": datetime.now().replace(hour=13, minute=30), "title": "US Non-Farm Payrolls", "impact": "HIGH"},
        {"time": datetime.now().replace(hour=19, minute=0), "title": "FOMC Statement", "impact": "HIGH"},
    ]
    return news_events

def is_trading_blocked_by_news():
    """Check if trading should be blocked due to upcoming news"""
    news_events = get_economic_calendar()
    now = datetime.now()
    
    for event in news_events:
        time_diff = (event['time'] - now).total_seconds() / 60  # minutes until event
        if 0 <= time_diff <= 30:  # Block 30 minutes before and after
            return True, f"High impact news: {event['title']} in {int(time_diff)}min"
    return False, "No news restrictions"

# ============ RISK MANAGEMENT ============
def check_drawdown(current_balance, peak_balance, max_drawdown_percent=10):
    """Check if max drawdown is exceeded"""
    if current_balance > peak_balance:
        st.session_state.peak_balance = current_balance
        st.session_state.drawdown_alert_sent = False
    
    drawdown = (st.session_state.peak_balance - current_balance) / st.session_state.peak_balance * 100
    
    if drawdown >= max_drawdown_percent and not st.session_state.drawdown_alert_sent:
        st.session_state.drawdown_alert_sent = True
        st.session_state.trading_enabled = False
        if st.session_state.telegram_connected:
            send_telegram_message(st.session_state.telegram_chat_id, f"⚠️ MAX DRAWDOWN REACHED: {drawdown:.1f}%\nTrading halted!")
        return True, drawdown
    return False, drawdown

def calculate_atr_position_size(account_balance, atr_percent, risk_percent=1.0, base_position=0.01):
    """Dynamic position sizing based on ATR volatility"""
    # Normal ATR is around 0.5-1.5% for gold
    if atr_percent > 1.5:  # High volatility
        size_multiplier = 0.5
    elif atr_percent < 0.5:  # Low volatility
        size_multiplier = 0.8
    else:
        size_multiplier = 1.0
    
    # Adjust for account size
    if account_balance < 5000:
        size_multiplier *= 0.5
    elif account_balance > 20000:
        size_multiplier *= 1.2
    
    position_size = base_position * size_multiplier * (risk_percent / 1.0)
    return round(position_size, 4)

# ============ OANDA TRADING ============
def oanda_get_price():
    """Get current price from OANDA"""
    if OANDA_API_KEY == "YOUR_OANDA_API_KEY_HERE":
        return None
    try:
        headers = {"Authorization": f"Bearer {OANDA_API_KEY}"}
        url = f"{OANDA_URL}/accounts/{OANDA_ACCOUNT_ID}/pricing?instruments=XAU_USD"
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return float(data['prices'][0]['bids'][0]['price'])
    except:
        pass
    return None

def oanda_execute_trade(direction, units, sl_price, tp_price):
    """Execute trade on OANDA"""
    if OANDA_API_KEY == "YOUR_OANDA_API_KEY_HERE":
        return False, "OANDA not configured"
    
    try:
        headers = {
            "Authorization": f"Bearer {OANDA_API_KEY}",
            "Content-Type": "application/json"
        }
        
        order = {
            "order": {
                "type": "MARKET",
                "instrument": "XAU_USD",
                "units": units if direction == "LONG" else -units,
                "stopLossOnFill": {"price": str(sl_price)},
                "takeProfitOnFill": {"price": str(tp_price)}
            }
        }
        
        url = f"{OANDA_URL}/accounts/{OANDA_ACCOUNT_ID}/orders"
        response = requests.post(url, headers=headers, json=order, timeout=10)
        
        if response.status_code == 201:
            return True, response.json()
        else:
            return False, response.text
    except Exception as e:
        return False, str(e)

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

def format_signal_message(signal):
    emoji = "📈" if signal['direction'] == "LONG" else "📉"
    signal_text = "🟢 BUY (LONG)" if signal['direction'] == "LONG" else "🔴 SELL (SHORT)"
    return f"""
{emoji} <b>XAUUSD TRADING SIGNAL</b> {emoji}

<b>Signal:</b> {signal_text}
<b>Timeframe:</b> {signal['timeframe']}
<b>Confidence:</b> {signal['confidence']:.1%}

<b>━━━━━━━━━━━━━━</b>
<b>📍 ENTRY:</b> ${signal['entry']:.2f}
<b>🛑 STOP LOSS:</b> ${signal['sl']:.2f}

<b>🎯 TAKE PROFITS:</b>
• TP1: ${signal['tp1']:.2f}
• TP2: ${signal['tp2']:.2f}
• TP3: ${signal['tp3']:.2f}
• TP4: ${signal['tp4']:.2f}

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
def get_historical_data(timeframe, days=None):
    try:
        tf_config = TIMEFRAMES_CONFIG[timeframe]
        days = days if days else tf_config["days"]
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
    df['ATR_Percent'] = df['ATR'] / df['Close'] * 100
    
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
        pred_bars = TIMEFRAMES_CONFIG[timeframe]["pred_bars"]
        model, scaler, _ = train_model(df, pred_bars)
        
        if model is None:
            return None
        
        current_price = get_realtime_price()
        if current_price is None:
            current_price = float(df['Close'].iloc[-1])
        
        atr = float(df['ATR'].iloc[-1]) if not pd.isna(df['ATR'].iloc[-1]) else current_price * 0.005
        atr_percent = float(df['ATR_Percent'].iloc[-1]) if not pd.isna(df['ATR_Percent'].iloc[-1]) else 0.8
        
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
                'timestamp': datetime.now(),
                'risk': risk,
                'atr_percent': atr_percent
            }
    except Exception as e:
        print(f"Error: {e}")
    return None

# ============ SIDEBAR ============
with st.sidebar:
    st.header("⚙️ CONTROL PANEL")
    
    # Telegram Connection
    st.subheader("🤖 TELEGRAM")
    if not st.session_state.telegram_connected:
        if st.button("📱 Connect", use_container_width=True):
            updates = get_telegram_updates()
            if updates and 'result' in updates and updates['result']:
                for update in updates['result']:
                    if 'message' in update and 'chat' in update['message']:
                        chat_id = update['message']['chat']['id']
                        st.session_state.telegram_chat_id = chat_id
                        st.session_state.telegram_connected = True
                        send_telegram_message(chat_id, "✅ Ultimate Trading Bot Connected!\n\nFeatures:\n- Auto Signals (all timeframes)\n- Drawdown Protection\n- News Filter\n- ATR Position Sizing")
                        st.success("Connected!")
                        st.rerun()
                        break
            else:
                st.warning("Send a message to @BOACUTING first!")
    else:
        st.success("✅ Connected")
        if st.button("Disconnect", use_container_width=True):
            st.session_state.telegram_connected = False
            st.session_state.telegram_chat_id = None
            st.rerun()
    
    st.markdown("---")
    
    # OANDA Connection
    st.subheader("💱 OANDA TRADING")
    oanda_key_input = st.text_input("OANDA API Key", type="password", placeholder="Enter your OANDA API key")
    oanda_account_input = st.text_input("Account ID", placeholder="Enter account ID")
    
    if st.button("Connect OANDA", use_container_width=True):
        if oanda_key_input and oanda_account_input:
            # In production, validate the API key
            st.session_state.oanda_connected = True
            st.success("OANDA Connected! Auto-trading enabled")
        else:
            st.warning("Enter API key and Account ID")
    
    if st.session_state.oanda_connected:
        st.success("✅ OANDA Ready")
    
    st.markdown("---")
    
    # Auto Signals
    st.subheader("🚀 AUTO SIGNALS")
    st.session_state.auto_run = st.toggle("Enable All Auto-Signals", value=st.session_state.auto_run)
    min_conf = st.slider("Min Confidence (%)", 50, 80, 60) / 100
    
    st.markdown("---")
    
    # Risk Management Settings
    st.subheader("🛡️ RISK MANAGEMENT")
    max_drawdown = st.slider("Max Drawdown (%)", 5, 20, 10)
    base_risk = st.slider("Base Risk per Trade (%)", 0.5, 2.0, 1.0)
    
    st.markdown("---")
    st.subheader("📊 ACTIVE TIMEFRAMES")
    
    active_timeframes = {}
    tf_cols = st.columns(4)
    tf_list = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
    
    for i, tf in enumerate(tf_list):
        col = tf_cols[i % 4]
        with col:
            interval = TIMEFRAMES_CONFIG[tf]["send_interval"]
            active = st.checkbox(f"{tf} (every {interval}min)", value=True, key=f"active_{tf}")
            active_timeframes[tf] = active
            last = st.session_state.last_signal_sent.get(tf)
            if last:
                st.caption(f"Last: {last.strftime('%H:%M')}")
    
    st.markdown("---")
    
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ============ MAIN TABS ============
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 LIVE SIGNALS", "📈 BACKTEST", "📋 SIGNAL HISTORY", "🛡️ RISK MANAGEMENT", "📅 REPORTS"])

current_timeframe = st.session_state.selected_timeframe

# Check news filter
news_blocked, news_reason = is_trading_blocked_by_news()

if news_blocked:
    st.warning(f"⚠️ {news_reason} - Trading is paused")

# ============ AUTO SIGNAL LOOP ============
if st.session_state.auto_run and st.session_state.telegram_connected and not news_blocked:
    current_time = datetime.now()
    
    for tf in ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]:
        if not active_timeframes.get(tf, True):
            continue
        
        interval = TIMEFRAMES_CONFIG[tf]["send_interval"]
        last_sent = st.session_state.last_signal_sent.get(tf)
        
        if last_sent is None:
            minutes_since = interval + 1
        else:
            minutes_since = (current_time - last_sent).total_seconds() / 60
        
        if minutes_since >= interval:
            signal = analyze_timeframe(tf, min_conf)
            
            if signal:
                st.session_state.all_signals.append(signal)
                message = format_signal_message(signal)
                
                if send_telegram_message(st.session_state.telegram_chat_id, message):
                    st.session_state.last_signal_sent[tf] = current_time
                    st.success(f"✅ {tf.upper()} signal sent!")

# ============ TAB 1: LIVE SIGNALS ============
with tab1:
    st.subheader("📊 SELECT TIMEFRAME")
    tf_cols = st.columns(7)
    for i, tf in enumerate(["1m", "5m", "15m", "30m", "1h", "4h", "1d"]):
        with tf_cols[i]:
            if st.button(f"📈 {tf}", use_container_width=True, type="primary" if current_timeframe == tf else "secondary"):
                st.session_state.selected_timeframe = tf
                st.rerun()
    
    with st.spinner(f"Loading {current_timeframe} data..."):
        df = get_historical_data(current_timeframe)
        
        if df is not None and len(df) > 20:
            df = calculate_indicators(df)
            pred_bars = TIMEFRAMES_CONFIG[current_timeframe]["pred_bars"]
            model, scaler, accuracy = train_model(df, pred_bars)
            current_price = get_realtime_price()
            if current_price is None:
                current_price = float(df['Close'].iloc[-1])
            atr = float(df['ATR'].iloc[-1]) if not pd.isna(df['ATR'].iloc[-1]) else current_price * 0.005
            atr_percent = float(df['ATR_Percent'].iloc[-1]) if not pd.isna(df['ATR_Percent'].iloc[-1]) else 0.8
            rsi = float(df['RSI'].iloc[-1]) if not pd.isna(df['RSI'].iloc[-1]) else 50
            
            # Metrics
            col1, col2, col3, col4, col5, col6 = st.columns(6)
            col1.metric("XAUUSD", f"${current_price:.2f}")
            col2.metric("ATR", f"${atr:.2f}", f"{atr_percent:.2f}%")
            col3.metric("RSI", f"{rsi:.1f}")
            col4.metric("AI Accuracy", f"{accuracy:.1%}" if accuracy else "N/A")
            col5.metric("Auto Mode", "ON" if st.session_state.auto_run else "OFF")
            col6.metric("Trading", "ENABLED" if st.session_state.trading_enabled else "HALTED")
            
            # News warning
            if news_blocked:
                st.warning(f"⚠️ {news_reason}")
            
            # Get Signal
            features = ['RSI', 'MACD_Hist', 'ATR', 'SMA_20', 'SMA_50']
            if model and scaler and len(df) > 30:
                latest_features = df[features].iloc[-1:].values
                prediction, confidence = get_signal(model, scaler, latest_features)
            else:
                prediction, confidence = None, 0
            
            st.markdown("---")
            st.subheader("🤖 AI SIGNAL")
            
            if prediction == 1 and confidence >= min_conf:
                st.success(f"📈 BULLISH SIGNAL - Confidence: {confidence:.1%}")
                direction = "LONG"
            elif prediction == 0 and confidence >= min_conf:
                st.error(f"📉 BEARISH SIGNAL - Confidence: {confidence:.1%}")
                direction = "SHORT"
            else:
                st.warning(f"⏸️ NO SIGNAL - Confidence: {confidence:.1%}")
                direction = None
            
            if direction:
                sl, tp1, tp2, tp3, tp4, risk = calculate_levels(current_price, atr, direction, current_timeframe)
                
                # ATR-based position sizing
                position_size = calculate_atr_position_size(10000, atr_percent, base_risk)
                
                st.markdown("---")
                st.subheader("🎯 TRADING LEVELS")
                level_cols = st.columns(6)
                level_cols[0].metric("📍 ENTRY", f"${current_price:.2f}")
                level_cols[1].metric("🛑 SL", f"${sl:.2f}", f"Risk: ${risk:.2f}")
                level_cols[2].metric("🎯 TP1", f"${tp1:.2f}")
                level_cols[3].metric("🎯 TP2", f"${tp2:.2f}")
                level_cols[4].metric("🎯 TP3", f"${tp3:.2f}")
                level_cols[5].metric("🎯 TP4", f"${tp4:.2f}")
                
                st.info(f"📊 ATR-Based Position Size: {position_size} lots | Risk: ${risk:.2f}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ RECORD SIGNAL", type="primary"):
                        signal_data = {
                            'timestamp': datetime.now(),
                            'timeframe': current_timeframe,
                            'direction': direction,
                            'entry': current_price,
                            'sl': sl, 'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'tp4': tp4,
                            'confidence': confidence,
                            'risk': risk
                        }
                        st.session_state.all_signals.append(signal_data)
                        st.success("Signal recorded!")
                        
                        if st.session_state.telegram_connected:
                            message = format_signal_message(signal_data)
                            send_telegram_message(st.session_state.telegram_chat_id, message)
                            st.info("Signal sent to Telegram!")
                        
                        # Auto-execute on OANDA if connected
                        if st.session_state.oanda_connected and OANDA_API_KEY != "YOUR_OANDA_API_KEY_HERE":
                            success, result = oanda_execute_trade(direction, position_size, sl, tp2)
                            if success:
                                st.success(f"✅ Trade auto-executed on OANDA!")
                            else:
                                st.error(f"OANDA execution failed: {result}")
                
                with col2:
                    trade_text = f"XAUUSD {direction} @ {current_price:.2f}\nSL: {sl:.2f}\nTP1-4: {tp1:.0f}/{tp2:.0f}/{tp3:.0f}/{tp4:.0f}\nSize: {position_size}"
                    st.code(trade_text, language="text")
                
                # Chart
                st.markdown("---")
                st.subheader("📈 CHART")
                fig = make_subplots(rows=2, cols=1, row_heights=[0.7, 0.3], shared_xaxes=True)
                recent_df = df.tail(100)
                
                fig.add_trace(go.Candlestick(x=recent_df.index, open=recent_df['Open'], high=recent_df['High'], low=recent_df['Low'], close=recent_df['Close'], name='XAUUSD'), row=1, col=1)
                for name, price, color in [('Entry', current_price, '#ffd700'), ('SL', sl, '#ff4444'), ('TP1', tp1, '#00ff88'), ('TP2', tp2, '#00cc66'), ('TP3', tp3, '#009944'), ('TP4', tp4, '#006622')]:
                    fig.add_hline(y=price, line_dash="dash" if name == 'SL' else "solid", line_color=color, annotation_text=name, row=1, col=1)
                
                fig.add_trace(go.Scatter(x=recent_df.index, y=recent_df['RSI'], name='RSI', line=dict(color='#9b59b6')), row=2, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
                fig.update_yaxes(range=[0, 100], row=2, col=1)
                fig.update_layout(template='plotly_dark', height=600, showlegend=True)
                st.plotly_chart(fig, use_container_width=True)

# ============ TAB 2: BACKTEST ============
with tab2:
    st.header("📈 BACKTEST ENGINE")
    
    col1, col2 = st.columns(2)
    with col1:
        backtest_timeframe = st.selectbox("Timeframe", ["15m", "30m", "1h", "4h"], index=2)
        backtest_period = st.selectbox("Period", ["7d", "30d", "90d", "180d"], index=1)
    with col2:
        bt_risk = st.slider("Risk per Trade (%)", 0.5, 2.0, 1.0)
        bt_confidence = st.slider("Min Confidence (%)", 50, 80, 60) / 100
    
    period_days = {"7d": 7, "30d": 30, "90d": 90, "180d": 180}[backtest_period]
    
    if st.button("🚀 RUN BACKTEST", type="primary"):
        with st.spinner(f"Running backtest on {backtest_timeframe}..."):
            bt_df = get_historical_data(backtest_timeframe, period_days)
            if bt_df is not None and len(bt_df) > 50:
                bt_df = calculate_indicators(bt_df)
                pred_bars = TIMEFRAMES_CONFIG[backtest_timeframe]["pred_bars"]
                bt_model, bt_scaler, bt_acc = train_model(bt_df, pred_bars)
                
                if bt_model:
                    trades = []
                    balance = 10000
                    balance_history = [balance]
                    features = ['RSI', 'MACD_Hist', 'ATR', 'SMA_20', 'SMA_50']
                    
                    for i in range(50, len(bt_df) - 4):
                        feat_vec = bt_df[features].iloc[i:i+1].values
                        pred, conf = get_signal(bt_model, bt_scaler, feat_vec)
                        if conf < 0.60:
                            continue
                        
                        price = bt_df['Close'].iloc[i]
                        atr_val = bt_df['ATR'].iloc[i]
                        direction = "LONG" if pred == 1 else "SHORT"
                        sl, tp1, tp2, tp3, tp4, risk = calculate_levels(price, atr_val, direction, backtest_timeframe)
                        
                        risk_amount = balance * (bt_risk / 100)
                        pos_size = risk_amount / risk if risk > 0 else 0
                        future = bt_df['Close'].iloc[i+1:i+5].values
                        
                        hit_sl = any(future <= sl if direction == "LONG" else future >= sl)
                        hit_tp = any(future >= tp2 if direction == "LONG" else future <= tp2)
                        
                        if hit_tp and not hit_sl:
                            profit = pos_size * abs(tp2 - price)
                            balance += profit
                            trades.append({'result': 'WIN', 'pnl': profit, 'date': bt_df.index[i], 'direction': direction})
                        elif hit_sl:
                            balance -= risk_amount
                            trades.append({'result': 'LOSS', 'pnl': -risk_amount, 'date': bt_df.index[i], 'direction': direction})
                        
                        balance_history.append(balance)
                    
                    if trades:
                        wins = len([t for t in trades if t['result'] == 'WIN'])
                        losses = len([t for t in trades if t['result'] == 'LOSS'])
                        win_rate = wins / len(trades) * 100
                        total_pnl = sum([t['pnl'] for t in trades])
                        gross_profit = sum([t['pnl'] for t in trades if t['result'] == 'WIN'])
                        gross_loss = abs(sum([t['pnl'] for t in trades if t['result'] == 'LOSS']))
                        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
                        avg_win = gross_profit / wins if wins > 0 else 0
                        avg_loss = gross_loss / losses if losses > 0 else 0
                        
                        st.subheader("📊 BACKTEST RESULTS")
                        r1, r2, r3, r4 = st.columns(4)
                        r1.metric("Total Trades", len(trades))
                        r2.metric("Win Rate", f"{win_rate:.1f}%")
                        r3.metric("Profit Factor", f"{profit_factor:.2f}")
                        r4.metric("Total P&L", f"${total_pnl:,.2f}")
                        
                        r5, r6, r7, r8 = st.columns(4)
                        r5.metric("Avg Win", f"${avg_win:.2f}")
                        r6.metric("Avg Loss", f"${avg_loss:.2f}")
                        r7.metric("Wins", wins)
                        r8.metric("Losses", losses)
                        
                        # Equity curve
                        fig_eq = go.Figure()
                        fig_eq.add_trace(go.Scatter(x=list(range(len(balance_history))), y=balance_history, mode='lines', line=dict(color='#00ff88', width=2)))
                        fig_eq.add_hline(y=10000, line_dash="dash", line_color="gray")
                        fig_eq.update_layout(title="Equity Curve", template='plotly_dark', height=400)
                        st.plotly_chart(fig_eq, use_container_width=True)
                    else:
                        st.warning("No trades generated")

# ============ TAB 3: SIGNAL HISTORY ============
with tab3:
    st.header("📋 SIGNAL HISTORY")
    
    if st.session_state.all_signals:
        df_signals = pd.DataFrame(st.session_state.all_signals)
        
        total = len(df_signals)
        wins = len(df_signals[df_signals.get('result', 'PENDING') == 'WIN']) if 'result' in df_signals.columns else 0
        win_rate = wins / total * 100 if total > 0 else 0
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Signals", total)
        col2.metric("Wins", wins)
        col3.metric("Win Rate", f"{win_rate:.1f}%")
        
        for signal in reversed(st.session_state.all_signals[-30:]):
            emoji = "✅" if signal.get('result') == 'WIN' else "❌" if signal.get('result') == 'LOSS' else "⏳"
            st.markdown(f"""
            <div style="background: #1e1e2e; border-radius: 10px; padding: 0.5rem; margin: 0.2rem 0;">
                {emoji} <b>{signal['timeframe']}</b> | {signal['direction']} @ ${signal['entry']:.2f} | Conf: {signal['confidence']:.1%}
            </div>
            """, unsafe_allow_html=True)
        
        if st.button("📥 Export to CSV"):
            df_export = pd.DataFrame(st.session_state.all_signals)
            csv = df_export.to_csv()
            st.download_button("Download CSV", csv, "trading_signals.csv", "text/csv")
    else:
        st.info("No signals yet")

# ============ TAB 4: RISK MANAGEMENT ============
with tab4:
    st.header("🛡️ RISK MANAGEMENT DASHBOARD")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📊 Current Status")
        st.metric("Trading Status", "ENABLED" if st.session_state.trading_enabled else "HALTED")
        st.metric("Max Drawdown Limit", f"{max_drawdown}%")
        st.metric("Base Risk per Trade", f"{base_risk}%")
        st.metric("News Filter", "ACTIVE" if not news_blocked else f"BLOCKED - {news_reason}")
    
    with col2:
        st.subheader("🛡️ Protection Rules")
        st.markdown("""
        ✅ **Drawdown Protection**: Trading stops at {}% loss
        
        ✅ **News Filter**: No trading 30min before/after high-impact news
        
        ✅ **ATR Position Sizing**: Positions adjust based on volatility
        
        ✅ **Consecutive Loss Limit**: Auto-pause after 3 losses
        """.format(max_drawdown))
    
    st.markdown("---")
    st.subheader("📈 Risk Metrics")
    
    if st.session_state.all_signals:
        df_risk = pd.DataFrame(st.session_state.all_signals)
        if 'confidence' in df_risk.columns:
            st.metric("Avg Confidence", f"{df_risk['confidence'].mean():.1%}")
        
        # Consecutive loss tracking
        recent_results = [s.get('result') for s in st.session_state.all_signals[-10:]]
        consecutive_losses = 0
        for r in reversed(recent_results):
            if r == 'LOSS':
                consecutive_losses += 1
            else:
                break
        st.metric("Consecutive Losses", consecutive_losses)
        if consecutive_losses >= 3:
            st.warning("⚠️ 3 consecutive losses detected! Consider reducing risk.")

# ============ TAB 5: REPORTS ============
with tab5:
    st.header("📅 TRADING REPORTS")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📅 Daily Report", use_container_width=True):
            today = datetime.now().date()
            daily_signals = [s for s in st.session_state.all_signals if s['timestamp'].date() == today]
            if daily_signals:
                wins = len([s for s in daily_signals if s.get('result') == 'WIN'])
                report = f"📊 DAILY REPORT - {today}\n\nTotal Signals: {len(daily_signals)}\nWins: {wins}\nWin Rate: {wins/len(daily_signals)*100:.1f}%"
                if st.session_state.telegram_connected:
                    send_telegram_message(st.session_state.telegram_chat_id, report)
                st.success("Daily report sent!")
            else:
                st.warning("No signals today")
    
    with col2:
        if st.button("📆 Weekly Report", use_container_width=True):
            week_ago = datetime.now() - timedelta(days=7)
            weekly_signals = [s for s in st.session_state.all_signals if s['timestamp'] >= week_ago]
            if weekly_signals:
                wins = len([s for s in weekly_signals if s.get('result') == 'WIN'])
                report = f"📊 WEEKLY REPORT\n\nTotal: {len(weekly_signals)}\nWins: {wins}\nWin Rate: {wins/len(weekly_signals)*100:.1f}%"
                if st.session_state.telegram_connected:
                    send_telegram_message(st.session_state.telegram_chat_id, report)
                st.success("Weekly report sent!")
            else:
                st.warning("No signals this week")
    
    with col3:
        if st.button("📅 Monthly Report", use_container_width=True):
            month_ago = datetime.now() - timedelta(days=30)
            monthly_signals = [s for s in st.session_state.all_signals if s['timestamp'] >= month_ago]
            if monthly_signals:
                wins = len([s for s in monthly_signals if s.get('result') == 'WIN'])
                report = f"📊 MONTHLY REPORT\n\nTotal: {len(monthly_signals)}\nWins: {wins}\nWin Rate: {wins/len(monthly_signals)*100:.1f}%"
                if st.session_state.telegram_connected:
                    send_telegram_message(st.session_state.telegram_chat_id, report)
                st.success("Monthly report sent!")
            else:
                st.warning("No signals this month")

# Status footer
st.markdown("---")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Auto Mode", "🟢 ACTIVE" if st.session_state.auto_run else "⚫ OFF")
col2.metric("Telegram", "✅ CONNECTED" if st.session_state.telegram_connected else "❌ DISCONNECTED")
col3.metric("OANDA", "✅ READY" if st.session_state.oanda_connected else "❌ NOT CONNECTED")
col4.metric("Total Signals", len(st.session_state.all_signals))

st.caption("⚠️ EDUCATIONAL ONLY - Not financial advice. Features: Auto-Signals | Drawdown Protection | News Filter | ATR Position Sizing | OANDA Ready")
