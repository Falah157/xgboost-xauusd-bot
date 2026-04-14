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
warnings.filterwarnings('ignore')

st.set_page_config(page_title="PROFESSIONAL XAUUSD TRADING BOT", layout="wide", page_icon="🏆", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main-header { font-size: 2rem; font-weight: bold; background: linear-gradient(90deg, #00ff88, #ffd700, #ff4444); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; padding: 0.5rem; }
    .metric-card { background: #1e1e2e; border-radius: 10px; padding: 1rem; text-align: center; border: 1px solid #333; }
    .signal-bullish { background: #0a3a2a; border-left: 4px solid #00ff88; padding: 1rem; border-radius: 10px; }
    .signal-bearish { background: #3a1a1a; border-left: 4px solid #ff4444; padding: 1rem; border-radius: 10px; }
    .level-box { background: #1e1e2e; border-radius: 10px; padding: 0.8rem; text-align: center; border: 1px solid #333; }
    .level-price { font-size: 1.2rem; font-weight: bold; color: #ffd700; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🏆 PROFESSIONAL XAUUSD TRADING BOT</div>', unsafe_allow_html=True)

# ============ CONFIGURATION ============
API_KEY = "96871e27b094425f9ea104fa6eb2be64"
TELEGRAM_BOT_TOKEN = "8369393711:AAGm8ydfJc3UQPyNCPR6uCEr1LQpFw-zV-4"

TIMEFRAMES = {
    "1m": {"api": "1min", "hours": 1/60, "days": 1, "send_interval": 1},
    "5m": {"api": "5min", "hours": 5/60, "days": 3, "send_interval": 5},
    "15m": {"api": "15min", "hours": 15/60, "days": 7, "send_interval": 15},
    "30m": {"api": "30min", "hours": 30/60, "days": 14, "send_interval": 30},
    "1h": {"api": "1h", "hours": 1, "days": 30, "send_interval": 60},
    "4h": {"api": "4h", "hours": 4, "days": 60, "send_interval": 240},
    "1d": {"api": "1day", "hours": 24, "days": 180, "send_interval": 1440}
}

# Session State Initialization
if 'telegram_connected' not in st.session_state:
    st.session_state.telegram_connected = False
if 'telegram_chat_id' not in st.session_state:
    st.session_state.telegram_chat_id = None
if 'all_signals' not in st.session_state:
    st.session_state.all_signals = []
if 'backtest_results' not in st.session_state:
    st.session_state.backtest_results = None
if 'auto_run' not in st.session_state:
    st.session_state.auto_run = False
if 'selected_timeframe' not in st.session_state:
    st.session_state.selected_timeframe = "1h"
if 'daily_report_last' not in st.session_state:
    st.session_state.daily_report_last = None
if 'weekly_report_last' not in st.session_state:
    st.session_state.weekly_report_last = None
if 'monthly_report_last' not in st.session_state:
    st.session_state.monthly_report_last = None

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
        tf_config = TIMEFRAMES[timeframe]
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
        st.error(f"Error: {e}")
    return None

def calculate_indicators(df):
    df = df.copy()
    df['SMA_20'] = df['Close'].rolling(20).mean()
    df['SMA_50'] = df['Close'].rolling(50).mean()
    df['EMA_9'] = df['Close'].ewm(span=9).mean()
    df['EMA_21'] = df['Close'].ewm(span=21).mean()
    
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
    
    df['BB_Middle'] = df['Close'].rolling(20).mean()
    bb_std = df['Close'].rolling(20).std()
    df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
    df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
    
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
                'timestamp': datetime.now(),
                'risk': risk
            }
    except Exception as e:
        print(f"Error: {e}")
    return None

def run_backtest(df, model, scaler, risk_percent, timeframe):
    features = ['RSI', 'MACD_Hist', 'ATR', 'SMA_20', 'SMA_50']
    df_test = df.dropna().copy()
    trades = []
    balance = 10000
    balance_history = [balance]
    
    for i in range(50, len(df_test) - 4):
        current_price = df_test['Close'].iloc[i]
        atr = df_test['ATR'].iloc[i]
        
        feature_vector = df_test[features].iloc[i:i+1].values
        if len(feature_vector) == 0:
            continue
        
        pred, conf = get_signal(model, scaler, feature_vector)
        if conf < 0.60:
            continue
        
        direction = "LONG" if pred == 1 else "SHORT"
        sl, tp1, tp2, tp3, tp4, risk = calculate_levels(current_price, atr, direction, timeframe)
        
        risk_amount = balance * (risk_percent / 100)
        pos_size = risk_amount / risk if risk > 0 else 0
        
        future_prices = df_test['Close'].iloc[i+1:i+5].values
        hit_sl = any(future_prices <= sl if direction == "LONG" else future_prices >= sl)
        hit_tp = any(future_prices >= tp2 if direction == "LONG" else future_prices <= tp2)
        
        if hit_tp and not hit_sl:
            profit = pos_size * abs(tp2 - current_price)
            balance += profit
            trades.append({'result': 'WIN', 'pnl': profit, 'date': df_test.index[i], 'direction': direction, 'entry': current_price})
        elif hit_sl:
            balance -= risk_amount
            trades.append({'result': 'LOSS', 'pnl': -risk_amount, 'date': df_test.index[i], 'direction': direction, 'entry': current_price})
        
        balance_history.append(balance)
    
    return trades, balance_history

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
                        send_telegram_message(chat_id, "✅ Professional Trading Bot Connected!")
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
    
    # Auto Signals
    st.subheader("🚀 AUTO SIGNALS")
    st.session_state.auto_run = st.toggle("Enable Auto-Signals", value=st.session_state.auto_run)
    min_conf = st.slider("Min Confidence (%)", 50, 80, 60) / 100
    
    st.markdown("---")
    st.subheader("📊 REPORTS")
    
    if st.button("📅 Send Daily Report", use_container_width=True):
        # Generate daily report
        today = datetime.now().date()
        daily_signals = [s for s in st.session_state.all_signals if s['timestamp'].date() == today]
        if daily_signals and st.session_state.telegram_connected:
            wins = len([s for s in daily_signals if s.get('result') == 'WIN'])
            report = f"📊 DAILY REPORT - {today}\n\nTotal Signals: {len(daily_signals)}\nWins: {wins}\nWin Rate: {wins/len(daily_signals)*100:.1f}%"
            send_telegram_message(st.session_state.telegram_chat_id, report)
            st.success("Daily report sent!")
    
    if st.button("📆 Send Weekly Report", use_container_width=True):
        week_ago = datetime.now() - timedelta(days=7)
        weekly_signals = [s for s in st.session_state.all_signals if s['timestamp'] >= week_ago]
        if weekly_signals and st.session_state.telegram_connected:
            wins = len([s for s in weekly_signals if s.get('result') == 'WIN'])
            report = f"📊 WEEKLY REPORT\n\nPeriod: {week_ago.strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}\nTotal Signals: {len(weekly_signals)}\nWins: {wins}\nWin Rate: {wins/len(weekly_signals)*100:.1f}%"
            send_telegram_message(st.session_state.telegram_chat_id, report)
            st.success("Weekly report sent!")
    
    if st.button("📅 Send Monthly Report", use_container_width=True):
        month_ago = datetime.now() - timedelta(days=30)
        monthly_signals = [s for s in st.session_state.all_signals if s['timestamp'] >= month_ago]
        if monthly_signals and st.session_state.telegram_connected:
            wins = len([s for s in monthly_signals if s.get('result') == 'WIN'])
            report = f"📊 MONTHLY REPORT\n\nPeriod: {month_ago.strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}\nTotal Signals: {len(monthly_signals)}\nWins: {wins}\nWin Rate: {wins/len(monthly_signals)*100:.1f}%"
            send_telegram_message(st.session_state.telegram_chat_id, report)
            st.success("Monthly report sent!")

# ============ MAIN TABS ============
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 LIVE SIGNALS", "📈 BACKTEST", "📋 SIGNAL HISTORY", "📅 REPORTS", "📊 STATISTICS"])

current_timeframe = st.session_state.selected_timeframe

# ============ TAB 1: LIVE SIGNALS ============
with tab1:
    # Timeframe selector
    tf_cols = st.columns(7)
    for i, tf in enumerate(["1m", "5m", "15m", "30m", "1h", "4h", "1d"]):
        with tf_cols[i]:
            if st.button(tf, use_container_width=True, type="primary" if current_timeframe == tf else "secondary"):
                st.session_state.selected_timeframe = tf
                st.rerun()
    
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
            
            # Metrics
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("XAUUSD", f"${current_price:.2f}")
            col2.metric("ATR", f"${atr:.2f}")
            col3.metric("RSI", f"{rsi:.1f}")
            col4.metric("AI Accuracy", f"{accuracy:.1%}" if accuracy else "N/A")
            col5.metric("Telegram", "✅" if st.session_state.telegram_connected else "❌")
            
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
                st.markdown('<div class="signal-bullish"><h2 style="color: #00ff88;">📈 BULLISH SIGNAL</h2>', unsafe_allow_html=True)
                st.write(f"Confidence: {confidence:.1%}")
                direction = "LONG"
            elif prediction == 0 and confidence >= min_conf:
                st.markdown('<div class="signal-bearish"><h2 style="color: #ff4444;">📉 BEARISH SIGNAL</h2>', unsafe_allow_html=True)
                st.write(f"Confidence: {confidence:.1%}")
                direction = "SHORT"
            else:
                st.warning(f"⏸️ NO SIGNAL - Confidence: {confidence:.1%}")
                direction = None
            
            if direction:
                sl, tp1, tp2, tp3, tp4, risk = calculate_levels(current_price, atr, direction, current_timeframe)
                
                st.markdown("---")
                st.subheader("🎯 TRADING LEVELS")
                level_cols = st.columns(6)
                level_cols[0].metric("📍 ENTRY", f"${current_price:.2f}")
                level_cols[1].metric("🛑 SL", f"${sl:.2f}", f"Risk: ${risk:.2f}")
                level_cols[2].metric("🎯 TP1", f"${tp1:.2f}")
                level_cols[3].metric("🎯 TP2", f"${tp2:.2f}")
                level_cols[4].metric("🎯 TP3", f"${tp3:.2f}")
                level_cols[5].metric("🎯 TP4", f"${tp4:.2f}")
                
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
                
                with col2:
                    trade_text = f"XAUUSD {direction} @ {current_price:.2f}\nSL: {sl:.2f}\nTP1-4: {tp1:.0f}/{tp2:.0f}/{tp3:.0f}/{tp4:.0f}"
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
                pred_bars = {"15m": 4, "30m": 4, "1h": 4, "4h": 2}
                bt_model, bt_scaler, bt_acc = train_model(bt_df, pred_bars.get(backtest_timeframe, 4))
                
                if bt_model:
                    trades, balance_history = run_backtest(bt_df, bt_model, bt_scaler, bt_risk, backtest_timeframe)
                    
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
                        
                        with st.expander("📋 View All Trades"):
                            for t in trades[-30:]:
                                emoji = "✅" if t['result'] == 'WIN' else "❌"
                                st.text(f"{emoji} {t['date'].strftime('%Y-%m-%d %H:%M')} | {t['direction']} | {t['result']} | P&L: ${t['pnl']:.2f}")
                    else:
                        st.warning("No trades generated")

# ============ TAB 3: SIGNAL HISTORY ============
with tab3:
    st.header("📋 SIGNAL HISTORY")
    
    if st.session_state.all_signals:
        # Filters
        col1, col2 = st.columns(2)
        with col1:
            filter_tf = st.selectbox("Filter by Timeframe", ["All"] + list(TIMEFRAMES.keys()))
        with col2:
            filter_result = st.selectbox("Filter by Result", ["All", "WIN", "LOSS", "PENDING"])
        
        filtered = st.session_state.all_signals
        if filter_tf != "All":
            filtered = [s for s in filtered if s['timeframe'] == filter_tf]
        
        # Statistics
        total = len(filtered)
        wins = len([s for s in filtered if s.get('result') == 'WIN'])
        win_rate = wins / total * 100 if total > 0 else 0
        
        st.subheader("📊 Summary")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Signals", total)
        c2.metric("Wins", wins)
        c3.metric("Win Rate", f"{win_rate:.1f}%")
        
        # Display signals
        for signal in reversed(filtered[-50:]):
            emoji = "✅" if signal.get('result') == 'WIN' else "❌" if signal.get('result') == 'LOSS' else "⏳"
            st.markdown(f"""
            <div style="background: #1e1e2e; border-radius: 10px; padding: 0.5rem; margin: 0.2rem 0;">
                {emoji} <b>{signal['timeframe']}</b> | {signal['direction']} @ ${signal['entry']:.2f} | Conf: {signal['confidence']:.1%} | {signal['timestamp'].strftime('%Y-%m-%d %H:%M')}
            </div>
            """, unsafe_allow_html=True)
        
        # Export
        if st.button("📥 Export to CSV"):
            df_export = pd.DataFrame(st.session_state.all_signals)
            csv = df_export.to_csv()
            st.download_button("Download CSV", csv, "trading_signals.csv", "text/csv")
    else:
        st.info("No signals recorded yet. Record a signal from the LIVE SIGNALS tab.")

# ============ TAB 4: REPORTS ============
with tab4:
    st.header("📅 TRADING REPORTS")
    
    # Auto-report settings
    st.subheader("⚙️ Auto-Report Settings")
    auto_daily = st.checkbox("Auto Daily Report", value=True)
    auto_weekly = st.checkbox("Auto Weekly Report", value=True)
    auto_monthly = st.checkbox("Auto Monthly Report", value=True)
    
    # Check for auto-reports
    now = datetime.now()
    
    if auto_daily and st.session_state.telegram_connected:
        if st.session_state.daily_report_last is None or (now - st.session_state.daily_report_last).days >= 1:
            today = now.date()
            daily_signals = [s for s in st.session_state.all_signals if s['timestamp'].date() == today]
            if daily_signals:
                wins = len([s for s in daily_signals if s.get('result') == 'WIN'])
                report = f"📊 DAILY REPORT - {today}\n\nTotal Signals: {len(daily_signals)}\nWins: {wins}\nWin Rate: {wins/len(daily_signals)*100:.1f}%"
                send_telegram_message(st.session_state.telegram_chat_id, report)
                st.session_state.daily_report_last = now
                st.info("Daily report sent automatically!")
    
    if auto_weekly and st.session_state.telegram_connected:
        if st.session_state.weekly_report_last is None or (now - st.session_state.weekly_report_last).days >= 7:
            week_ago = now - timedelta(days=7)
            weekly_signals = [s for s in st.session_state.all_signals if s['timestamp'] >= week_ago]
            if weekly_signals:
                wins = len([s for s in weekly_signals if s.get('result') == 'WIN'])
                report = f"📊 WEEKLY REPORT\n\nPeriod: {week_ago.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}\nTotal Signals: {len(weekly_signals)}\nWins: {wins}\nWin Rate: {wins/len(weekly_signals)*100:.1f}%"
                send_telegram_message(st.session_state.telegram_chat_id, report)
                st.session_state.weekly_report_last = now
                st.info("Weekly report sent automatically!")
    
    if auto_monthly and st.session_state.telegram_connected:
        if st.session_state.monthly_report_last is None or (now - st.session_state.monthly_report_last).days >= 30:
            month_ago = now - timedelta(days=30)
            monthly_signals = [s for s in st.session_state.all_signals if s['timestamp'] >= month_ago]
            if monthly_signals:
                wins = len([s for s in monthly_signals if s.get('result') == 'WIN'])
                report = f"📊 MONTHLY REPORT\n\nPeriod: {month_ago.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}\nTotal Signals: {len(monthly_signals)}\nWins: {wins}\nWin Rate: {wins/len(monthly_signals)*100:.1f}%"
                send_telegram_message(st.session_state.telegram_chat_id, report)
                st.session_state.monthly_report_last = now
                st.info("Monthly report sent automatically!")
    
    # Manual reports
    st.subheader("📤 Manual Reports")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📅 Send Daily Report Now", use_container_width=True):
            today = now.date()
            daily_signals = [s for s in st.session_state.all_signals if s['timestamp'].date() == today]
            if daily_signals and st.session_state.telegram_connected:
                wins = len([s for s in daily_signals if s.get('result') == 'WIN'])
                report = f"📊 DAILY REPORT - {today}\n\nTotal Signals: {len(daily_signals)}\nWins: {wins}\nWin Rate: {wins/len(daily_signals)*100:.1f}%"
                send_telegram_message(st.session_state.telegram_chat_id, report)
                st.success("Daily report sent!")
            else:
                st.warning("No signals today")
    
    with col2:
        if st.button("📆 Send Weekly Report Now", use_container_width=True):
            week_ago = now - timedelta(days=7)
            weekly_signals = [s for s in st.session_state.all_signals if s['timestamp'] >= week_ago]
            if weekly_signals and st.session_state.telegram_connected:
                wins = len([s for s in weekly_signals if s.get('result') == 'WIN'])
                report = f"📊 WEEKLY REPORT\n\nPeriod: {week_ago.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}\nTotal Signals: {len(weekly_signals)}\nWins: {wins}\nWin Rate: {wins/len(weekly_signals)*100:.1f}%"
                send_telegram_message(st.session_state.telegram_chat_id, report)
                st.success("Weekly report sent!")
            else:
                st.warning("No signals this week")
    
    with col3:
        if st.button("📅 Send Monthly Report Now", use_container_width=True):
            month_ago = now - timedelta(days=30)
            monthly_signals = [s for s in st.session_state.all_signals if s['timestamp'] >= month_ago]
            if monthly_signals and st.session_state.telegram_connected:
                wins = len([s for s in monthly_signals if s.get('result') == 'WIN'])
                report = f"📊 MONTHLY REPORT\n\nPeriod: {month_ago.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}\nTotal Signals: {len(monthly_signals)}\nWins: {wins}\nWin Rate: {wins/len(monthly_signals)*100:.1f}%"
                send_telegram_message(st.session_state.telegram_chat_id, report)
                st.success("Monthly report sent!")
            else:
                st.warning("No signals this month")

# ============ TAB 5: STATISTICS ============
with tab5:
    st.header("📊 TRADING STATISTICS")
    
    if st.session_state.all_signals:
        df_signals = pd.DataFrame(st.session_state.all_signals)
        
        # Overall stats
        total = len(df_signals)
        wins = len(df_signals[df_signals.get('result', 'PENDING') == 'WIN']) if 'result' in df_signals.columns else 0
        win_rate = wins / total * 100 if total > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Signals", total)
        col2.metric("Wins", wins)
        col3.metric("Win Rate", f"{win_rate:.1f}%")
        col4.metric("Active Signals", len([s for s in st.session_state.all_signals if s.get('result') == 'PENDING']))
        
        # By timeframe
        st.subheader("📊 Signals by Timeframe")
        tf_stats = df_signals['timeframe'].value_counts()
        st.bar_chart(tf_stats)
        
        # By direction
        st.subheader("📈 Signals by Direction")
        dir_stats = df_signals['direction'].value_counts()
        col1, col2 = st.columns(2)
        col1.write("LONG vs SHORT")
        col1.bar_chart(dir_stats)
        
        # Confidence distribution
        st.subheader("🎯 Confidence Distribution")
        st.bar_chart(df_signals['confidence'].value_counts().sort_index())
        
        # Daily activity
        st.subheader("📅 Daily Activity")
        df_signals['date'] = pd.to_datetime(df_signals['timestamp']).dt.date
        daily_counts = df_signals['date'].value_counts().sort_index().tail(30)
        st.line_chart(daily_counts)
    else:
        st.info("No data yet. Record some signals to see statistics.")

# Auto-signal loop (runs in background when enabled)
if st.session_state.auto_run and st.session_state.telegram_connected:
    current_time = datetime.now()
    
    for tf in TIMEFRAMES.keys():
        interval = TIMEFRAMES[tf]["send_interval"]
        last_signal = max([s['timestamp'] for s in st.session_state.all_signals if s['timeframe'] == tf], default=datetime.min)
        minutes_since = (current_time - last_signal).total_seconds() / 60
        
        if minutes_since >= interval:
            signal = analyze_timeframe(tf, min_conf)
            if signal:
                st.session_state.all_signals.append(signal)
                message = format_signal_message(signal)
                send_telegram_message(st.session_state.telegram_chat_id, message)
                st.success(f"Auto-signal sent for {tf}!")

st.markdown("---")
st.caption("⚠️ EDUCATIONAL ONLY - Not financial advice. Past performance does not guarantee future results.")
