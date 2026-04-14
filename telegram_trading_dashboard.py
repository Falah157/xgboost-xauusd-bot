import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import asyncio
import threading
import time
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="XAUUSD TELEGRAM TRADING", layout="wide", page_icon="🤖")

# Custom CSS
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
    .telegram-card {
        background: linear-gradient(135deg, #1e1e2e, #2a2a3a);
        border-radius: 15px;
        padding: 1rem;
        border: 1px solid #0088cc;
        margin: 0.5rem 0;
    }
    .level-box {
        background: #1e1e2e;
        border-radius: 10px;
        padding: 0.8rem;
        text-align: center;
        border: 1px solid #333;
    }
    .level-price {
        font-size: 1.2rem;
        font-weight: bold;
        color: #ffd700;
    }
    .timeframe-btn {
        background: linear-gradient(135deg, #1e1e2e, #2a2a3a);
        border-radius: 8px;
        padding: 0.5rem;
        text-align: center;
        border: 1px solid #ffd70033;
    }
    .timeframe-active {
        background: linear-gradient(135deg, #ffd70033, #ff8c0033);
        border: 1px solid #ffd700;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🤖 XAUUSD TELEGRAM TRADING BOT</div>', unsafe_allow_html=True)

# ============ CONFIGURATION ============
API_KEY = "96871e27b094425f9ea104fa6eb2be64"
TELEGRAM_BOT_TOKEN = "8369393711:AAGm8ydfJc3UQPyNCPR6uCEr1LQpFw-zV-4"

# All timeframes
TIMEFRAMES = {
    "1m": {"api": "1min", "hours": 1/60, "days": 1, "color": "#ff4444"},
    "5m": {"api": "5min", "hours": 5/60, "days": 3, "color": "#ff8844"},
    "15m": {"api": "15min", "hours": 15/60, "days": 7, "color": "#ffcc44"},
    "30m": {"api": "30min", "hours": 30/60, "days": 14, "color": "#ffff44"},
    "1h": {"api": "1h", "hours": 1, "days": 30, "color": "#88ff44"},
    "4h": {"api": "4h", "hours": 4, "days": 60, "color": "#44ff88"},
    "1d": {"api": "1day", "hours": 24, "days": 180, "color": "#44ffff"}
}

# Session state
if 'selected_timeframe' not in st.session_state:
    st.session_state.selected_timeframe = "1h"
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = datetime.now()
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False
if 'telegram_connected' not in st.session_state:
    st.session_state.telegram_connected = False
if 'telegram_chat_id' not in st.session_state:
    st.session_state.telegram_chat_id = None
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'last_signal_sent' not in st.session_state:
    st.session_state.last_signal_sent = None

# ============ TELEGRAM FUNCTIONS ============
def send_telegram_message(chat_id, message):
    """Send message via Telegram bot"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        st.error(f"Telegram error: {e}")
        return False

def get_telegram_updates(offset=None):
    """Get updates from Telegram to get chat_id"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        params = {"timeout": 5}
        if offset:
            params["offset"] = offset
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

def format_signal_message(direction, entry, sl, tp1, tp2, tp3, tp4, confidence, timeframe):
    """Format trading signal for Telegram"""
    if direction == "LONG":
        emoji = "📈"
        signal_text = "🟢 BUY (LONG)"
    else:
        emoji = "📉"
        signal_text = "🔴 SELL (SHORT)"
    
    message = f"""
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
📊 AI Powered Trading Bot</i>
"""
    return message

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
def get_historical_data(timeframe):
    try:
        tf_config = TIMEFRAMES[timeframe]
        days = tf_config["days"]
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
        st.error(f"Error: {e}")
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

# ============ SIDEBAR ============
with st.sidebar:
    st.header("⚙️ CONTROL PANEL")
    
    # Telegram Connection
    st.subheader("🤖 TELEGRAM BOT")
    
    if not st.session_state.telegram_connected:
        st.info("💡 Send any message to your bot to get your Chat ID")
        
        # Bot info display
        st.code(f"Bot: @{TELEGRAM_BOT_TOKEN.split(':')[0]}")
        
        # Check for new messages
        if st.button("📱 Get Chat ID", use_container_width=True):
            updates = get_telegram_updates()
            if updates and 'result' in updates and updates['result']:
                for update in updates['result']:
                    if 'message' in update and 'chat' in update['message']:
                        chat_id = update['message']['chat']['id']
                        st.session_state.telegram_chat_id = chat_id
                        st.session_state.telegram_connected = True
                        st.success(f"✅ Connected! Chat ID: {chat_id}")
                        send_telegram_message(chat_id, "✅ AI Trading Bot Connected!\n\nI will send you trading signals when the AI detects opportunities.")
                        break
            else:
                st.warning("No messages found. Send a message to your bot first!")
    else:
        st.success(f"✅ Connected to Telegram")
        st.caption(f"Chat ID: {st.session_state.telegram_chat_id}")
        
        if st.button("🔌 Disconnect", use_container_width=True):
            st.session_state.telegram_connected = False
            st.session_state.telegram_chat_id = None
            st.rerun()
    
    st.markdown("---")
    
    # Timeframe Selection
    st.subheader("📊 TIMEFRAME")
    tf_cols = st.columns(4)
    tf_list = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
    
    for i, tf in enumerate(tf_list):
        col = tf_cols[i % 4]
        with col:
            if st.button(tf, use_container_width=True,
                         type="primary" if st.session_state.selected_timeframe == tf else "secondary"):
                st.session_state.selected_timeframe = tf
                st.cache_data.clear()
                st.rerun()
    
    st.markdown(f"<div style='text-align: center;'>Current: <b>{st.session_state.selected_timeframe}</b></div>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Auto-Refresh
    st.subheader("🔄 AUTO REFRESH")
    refresh_interval = st.selectbox("Refresh every (min)", [5, 10, 15, 30, 60], index=2)
    st.session_state.auto_refresh = st.toggle("Enable Auto-Refresh", value=st.session_state.auto_refresh)
    
    if st.button("🔄 Refresh Now", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.session_state.last_refresh = datetime.now()
        st.rerun()
    
    st.markdown("---")
    
    # Trading Settings
    st.subheader("💰 TRADING SETTINGS")
    account_balance = st.number_input("Account Balance ($)", value=10000, step=1000)
    risk_percent = st.slider("Risk per Trade (%)", 0.5, 2.0, 1.0)
    min_confidence = st.slider("Min Confidence (%)", 50, 80, 60) / 100
    auto_send_signals = st.toggle("🤖 Auto-Send Signals to Telegram", value=True)
    
    st.markdown("---")
    st.caption(f"⏱️ Last refresh: {st.session_state.last_refresh.strftime('%H:%M:%S')}")

# ============ MAIN CONTENT ============
current_timeframe = st.session_state.selected_timeframe

with st.spinner(f"Loading {current_timeframe} data..."):
    df = get_historical_data(current_timeframe)
    
    if df is not None and len(df) > 20:
        df = calculate_indicators(df)
        
        pred_bars = {"1m": 12, "5m": 8, "15m": 4, "30m": 4, "1h": 4, "4h": 2, "1d": 1}
        model, scaler, accuracy = train_model(df, pred_bars.get(current_timeframe, 4))
        
        current_price = get_realtime_price()
        if current_price is None:
            current_price = float(df['Close'].iloc[-1])
        atr = float(df['ATR'].iloc[-1]) if not pd.isna(df['ATR'].iloc[-1]) else current_price * 0.005
        rsi = float(df['RSI'].iloc[-1]) if not pd.isna(df['RSI'].iloc[-1]) else 50
        
        # Top metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("XAUUSD", f"${current_price:.2f}")
        col2.metric("ATR", f"${atr:.2f}")
        col3.metric("RSI", f"{rsi:.1f}")
        col4.metric("AI Accuracy", f"{accuracy:.1%}" if accuracy else "N/A")
        col5.metric("Telegram", "✅" if st.session_state.telegram_connected else "❌")
        
        # Get AI Signal
        features = ['RSI', 'MACD_Hist', 'ATR', 'SMA_20', 'SMA_50']
        if model and scaler and len(df) > 30:
            latest_features = df[features].iloc[-1:].values
            prediction, confidence = get_signal(model, scaler, latest_features)
        else:
            prediction, confidence = None, 0
        
        # Display Signal
        st.markdown("---")
        st.subheader("🤖 AI SIGNAL")
        
        if prediction == 1 and confidence >= min_confidence:
            st.success(f"📈 BULLISH SIGNAL - Confidence: {confidence:.1%}")
            direction = "LONG"
        elif prediction == 0 and confidence >= min_confidence:
            st.error(f"📉 BEARISH SIGNAL - Confidence: {confidence:.1%}")
            direction = "SHORT"
        else:
            st.warning(f"⏸️ NO SIGNAL - Confidence: {confidence:.1%}")
            direction = None
        
        if direction:
            sl, tp1, tp2, tp3, tp4, risk = calculate_levels(current_price, atr, direction, current_timeframe)
            position_size = (account_balance * (risk_percent / 100)) / risk if risk > 0 else 0
            
            # Trading Levels
            st.markdown("---")
            st.subheader("🎯 TRADING LEVELS")
            
            level_cols = st.columns(6)
            level_cols[0].metric("📍 ENTRY", f"${current_price:.2f}")
            level_cols[1].metric("🛑 SL", f"${sl:.2f}", f"Risk: ${risk:.2f}")
            level_cols[2].metric("🎯 TP1", f"${tp1:.2f}")
            level_cols[3].metric("🎯 TP2", f"${tp2:.2f}")
            level_cols[4].metric("🎯 TP3", f"${tp3:.2f}")
            level_cols[5].metric("🎯 TP4", f"${tp4:.2f}")
            
            st.info(f"📊 Position Size: {position_size:.4f} lots | Risk: ${account_balance * (risk_percent / 100):.2f}")
            
            # Action Buttons
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("📝 RECORD TRADE", type="primary", use_container_width=True):
                    st.session_state.trade_history.append({
                        'time': datetime.now(),
                        'timeframe': current_timeframe,
                        'direction': direction,
                        'entry': current_price,
                        'sl': sl,
                        'tp2': tp2,
                        'confidence': confidence
                    })
                    st.success("Trade recorded!")
                    st.balloons()
            
            with col2:
                if st.session_state.telegram_connected and st.button("📱 SEND TO TELEGRAM", use_container_width=True):
                    message = format_signal_message(direction, current_price, sl, tp1, tp2, tp3, tp4, confidence, current_timeframe)
                    if send_telegram_message(st.session_state.telegram_chat_id, message):
                        st.success("Signal sent to Telegram!")
                        st.session_state.last_signal_sent = datetime.now()
                    else:
                        st.error("Failed to send")
            
            with col3:
                # Auto-send signal if enabled and new signal
                if auto_send_signals and st.session_state.telegram_connected:
                    signal_key = f"{direction}_{current_timeframe}_{int(current_price)}"
                    if st.session_state.last_signal_sent is None or (datetime.now() - st.session_state.last_signal_sent).seconds > 3600:
                        message = format_signal_message(direction, current_price, sl, tp1, tp2, tp3, tp4, confidence, current_timeframe)
                        send_telegram_message(st.session_state.telegram_chat_id, message)
                        st.session_state.last_signal_sent = datetime.now()
                        st.info("🤖 Auto-signal sent to Telegram")
            
            # Copy trade details
            trade_text = f"XAUUSD {direction} @ {current_price:.2f}\nSL: {sl:.2f}\nTP1: {tp1:.2f}\nTP2: {tp2:.2f}\nTP3: {tp3:.2f}\nTP4: {tp4:.2f}\nSize: {position_size:.4f}"
            st.code(trade_text, language="text")
        
        # Professional Chart
        st.markdown("---")
        st.subheader(f"📈 {current_timeframe.upper()} CHART")
        
        fig = make_subplots(rows=2, cols=1, row_heights=[0.7, 0.3], shared_xaxes=True)
        recent_df = df.tail(150)
        
        fig.add_trace(go.Candlestick(
            x=recent_df.index, open=recent_df['Open'], high=recent_df['High'],
            low=recent_df['Low'], close=recent_df['Close'], name='XAUUSD',
            increasing_line_color='#00ff88', decreasing_line_color='#ff4444'
        ), row=1, col=1)
        
        if direction:
            for name, price, color in [('Entry', current_price, '#ffd700'), ('SL', sl, '#ff4444'),
                ('TP1', tp1, '#00ff88'), ('TP2', tp2, '#00cc66'), ('TP3', tp3, '#009944'), ('TP4', tp4, '#006622')]:
                fig.add_hline(y=price, line_dash="dash" if name == 'SL' else "solid", 
                             line_color=color, annotation_text=name, row=1, col=1)
        
        fig.add_trace(go.Scatter(x=recent_df.index, y=recent_df['RSI'], name='RSI', 
                                 line=dict(color='#9b59b6', width=1.5)), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
        fig.update_yaxes(range=[0, 100], row=2, col=1)
        
        fig.update_layout(template='plotly_dark', height=600, showlegend=True, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # Trade History
        if st.session_state.trade_history:
            st.markdown("---")
            st.subheader("📋 RECENT TRADES")
            for trade in st.session_state.trade_history[-5:]:
                st.info(f"🎯 {trade['time'].strftime('%H:%M:%S')} | {trade['timeframe']} | {trade['direction']} | Entry: ${trade['entry']:.2f} | TP: ${trade['tp2']:.2f} | Conf: {trade['confidence']:.1%}")

# Auto-refresh logic
if st.session_state.auto_refresh:
    time_since = (datetime.now() - st.session_state.last_refresh).total_seconds() / 60
    if time_since >= refresh_interval:
        st.session_state.last_refresh = datetime.now()
        st.cache_data.clear()
        st.rerun()

# Footer
st.markdown("---")
st.caption("⚠️ EDUCATIONAL ONLY - Not financial advice. Always use proper risk management.")
