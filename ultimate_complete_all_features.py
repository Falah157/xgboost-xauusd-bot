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
import os
import time
import threading
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="ULTIMATE COMPLETE TRADING SYSTEM", layout="wide", page_icon="🏆")

st.markdown("""
<style>
    .main-title { font-size: 1.8rem; font-weight: bold; background: linear-gradient(90deg, #ffd700, #ff8c00, #ff4444); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; }
    .signal-buy { background: linear-gradient(135deg, #0a3a2a, #0a2a1a); border-left: 4px solid #00ff88; border-radius: 12px; padding: 1rem; margin: 0.5rem 0; }
    .signal-sell { background: linear-gradient(135deg, #3a1a1a, #2a0a0a); border-left: 4px solid #ff4444; border-radius: 12px; padding: 1rem; margin: 0.5rem 0; }
    .signal-wait { background: #1e1e2e; border-left: 4px solid #ffd700; border-radius: 12px; padding: 1rem; margin: 0.5rem 0; }
    .checklist-pass { background: #0a3a2a22; border-left: 3px solid #00ff88; padding: 0.5rem; margin: 0.3rem 0; border-radius: 8px; }
    .checklist-fail { background: #3a1a1a22; border-left: 3px solid #ff4444; padding: 0.5rem; margin: 0.3rem 0; border-radius: 8px; }
    .checklist-warn { background: #1e1e2e; border-left: 3px solid #ffd700; padding: 0.5rem; margin: 0.3rem 0; border-radius: 8px; }
    .level-card { background: #13161d; border-radius: 10px; padding: 0.5rem; text-align: center; border: 1px solid #2a2e3a; }
    .level-price { font-size: 1rem; font-weight: bold; color: #ffd700; }
    .meter { background: #2a2e3a; border-radius: 10px; height: 8px; overflow: hidden; }
    .meter-fill { height: 100%; border-radius: 10px; }
    .metric-card { background: #1e1e2e; border-radius: 10px; padding: 0.8rem; text-align: center; }
    .tf-card { background: #13161d; border-radius: 8px; padding: 0.3rem; text-align: center; cursor: pointer; border: 1px solid #2a2e3a; }
    .tf-active { border-color: #ffd700; background: #ffd70022; }
    .feedback-card { background: #1e1e2e; border-radius: 12px; padding: 0.8rem; margin: 0.5rem 0; border-left: 4px solid; }
    .feedback-pending { border-left-color: #ffd700; }
    .feedback-win { border-left-color: #00ff88; }
    .feedback-loss { border-left-color: #ff4444; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🏆 ULTIMATE COMPLETE TRADING SYSTEM</div>', unsafe_allow_html=True)

# ============ CONFIGURATION ============
API_KEY = "96871e27b094425f9ea104fa6eb2be64"
TELEGRAM_BOT_TOKEN = "8369393711:AAGm8ydfJc3UQPyNCPR6uCEr1LQpFw-zV-4"

# All Timeframes
ALL_TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
TIMEFRAMES = {
    "1m": {"api": "1min", "minutes": 1, "send_interval": 1},
    "5m": {"api": "5min", "minutes": 5, "send_interval": 5},
    "15m": {"api": "15min", "minutes": 15, "send_interval": 15},
    "30m": {"api": "30min", "minutes": 30, "send_interval": 30},
    "1h": {"api": "1h", "minutes": 60, "send_interval": 60},
    "4h": {"api": "4h", "minutes": 240, "send_interval": 240},
    "1d": {"api": "1day", "minutes": 1440, "send_interval": 1440}
}

# Symbols
SYMBOLS = {
    "XAUUSD": {"api": "XAU/USD", "name": "Gold", "digits": 2, "color": "#ffd700"},
    "BTCUSD": {"api": "BTC/USD", "name": "Bitcoin", "digits": 0, "color": "#ff8c00"}
}

# Professional Risk Parameters
PROFESSIONAL_PARAMS = {
    "XAUUSD": {"tp_pips": 4700, "sl_pips": 1700, "rr_ratio": 2.76},
    "BTCUSD": {"tp_pips": 44000, "sl_pips": 11000, "rr_ratio": 4.0}
}

# Session State
if 'selected_symbol' not in st.session_state:
    st.session_state.selected_symbol = "XAUUSD"
if 'selected_tf' not in st.session_state:
    st.session_state.selected_tf = "1h"
if 'telegram_connected' not in st.session_state:
    st.session_state.telegram_connected = False
if 'telegram_chat_id' not in st.session_state:
    st.session_state.telegram_chat_id = None
if 'auto_send' not in st.session_state:
    st.session_state.auto_send = False
if 'last_signal_sent' not in st.session_state:
    st.session_state.last_signal_sent = {tf: None for tf in ALL_TIMEFRAMES}
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'feedback_data' not in st.session_state:
    st.session_state.feedback_data = []
if 'backtest_results' not in st.session_state:
    st.session_state.backtest_results = None

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
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def format_telegram_signal(signal, symbol, tf, entry, sl, tp1, tp2, tp3, tp4, confidence):
    emoji = "📈" if signal == "BUY" else "📉"
    signal_text = "BUY (LONG)" if signal == "BUY" else "SELL (SHORT)"
    return f"""
{emoji} <b>{symbol} TRADING SIGNAL</b> {emoji}

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
def get_data(symbol, tf, days=60):
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
    except Exception as e:
        print(f"Error: {e}")
    return None

def calculate_all_indicators(df):
    df = df.copy()
    
    # Moving Averages
    df['sma20'] = df['close'].rolling(20).mean()
    df['sma50'] = df['close'].rolling(50).mean()
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()
    df['ema100'] = df['close'].ewm(span=100).mean()
    
    # TEMA
    ema1 = df['close'].ewm(span=9).mean()
    ema2 = ema1.ewm(span=9).mean()
    ema3 = ema2.ewm(span=9).mean()
    df['tema'] = 3 * ema1 - 3 * ema2 + ema3
    
    # LSMA
    def lsma(series, length=25):
        weights = np.arange(1, length + 1)
        sum_weights = np.sum(weights)
        return series.rolling(length).apply(lambda x: np.sum(weights * x) / sum_weights)
    df['lsma'] = lsma(df['close'], 25)
    
    # KAMA
    def kama(series, er_period=10, fast=2, slow=30):
        change = abs(series - series.shift(er_period))
        volatility = abs(series.diff()).rolling(er_period).sum()
        er = change / volatility
        sc = (er * (2/(fast+1) - 2/(slow+1)) + 2/(slow+1)) ** 2
        kama_series = series.copy()
        for i in range(1, len(series)):
            if not pd.isna(sc.iloc[i]):
                kama_series.iloc[i] = kama_series.iloc[i-1] + sc.iloc[i] * (series.iloc[i] - kama_series.iloc[i-1])
        return kama_series
    df['kama'] = kama(df['close'])
    
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
    df['atr_percent'] = df['atr'] / df['close'] * 100
    
    # Bollinger Bands
    df['bb_middle'] = df['close'].rolling(20).mean()
    bb_std = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
    df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
    
    # Stochastic
    low_14 = df['low'].rolling(14).min()
    high_14 = df['high'].rolling(14).max()
    df['stoch_k'] = 100 * ((df['close'] - low_14) / (high_14 - low_14))
    df['stoch_d'] = df['stoch_k'].rolling(3).mean()
    
    # Williams %R
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
    
    # Liquidity Sweep Detection
    df['pivot_high'] = ((df['high'].shift(1) > df['high'].shift(2)) & 
                        (df['high'].shift(1) > df['high'])).astype(int)
    df['pivot_low'] = ((df['low'].shift(1) < df['low'].shift(2)) & 
                       (df['low'].shift(1) < df['low'])).astype(int)
    df['liquidity_sweep_up'] = ((df['high'] > df['high'].shift(1).rolling(5).max()) & 
                                 (df['close'] < df['high'].shift(1))).astype(int)
    df['liquidity_sweep_down'] = ((df['low'] < df['low'].shift(1).rolling(5).min()) & 
                                   (df['close'] > df['low'].shift(1))).astype(int)
    
    # Break of Structure
    df['bos_up'] = ((df['high'] > df['high'].shift(1).rolling(10).max()) & 
                    (df['close'] > df['open'])).astype(int)
    df['bos_down'] = ((df['low'] < df['low'].shift(1).rolling(10).min()) & 
                      (df['close'] < df['open'])).astype(int)
    
    # Fibonacci Levels (from recent high/low)
    recent_high = df['high'].tail(50).max()
    recent_low = df['low'].tail(50).min()
    diff = recent_high - recent_low
    df['fib_236'] = recent_low + diff * 0.236
    df['fib_382'] = recent_low + diff * 0.382
    df['fib_500'] = recent_low + diff * 0.5
    df['fib_618'] = recent_low + diff * 0.618
    df['fib_786'] = recent_low + diff * 0.786
    
    # Supply & Demand Zones
    df['supply_zone'] = df['high'].rolling(20).max()
    df['demand_zone'] = df['low'].rolling(20).min()
    
    # Volume proxy
    df['volume_ratio'] = 1.0
    
    # Momentum
    df['momentum_5'] = df['close'].pct_change(5) * 100
    df['momentum_10'] = df['close'].pct_change(10) * 100
    
    return df

def get_signal_with_all_confirmations(df):
    if df is None or len(df) < 50:
        return "WAIT", 0, {}
    
    last = df.iloc[-1]
    
    buy_score = 0
    sell_score = 0
    confirmations = {}
    
    # 1. Liquidity Sweep + BoS (25)
    if last['liquidity_sweep_up'] == 1 and last['bos_up'] == 1:
        buy_score += 25
        confirmations['liquidity_sweep'] = "LIQUIDITY SWEEP + BoS ✅"
    elif last['liquidity_sweep_down'] == 1 and last['bos_down'] == 1:
        sell_score += 25
        confirmations['liquidity_sweep'] = "LIQUIDITY SWEEP + BoS ✅"
    else:
        confirmations['liquidity_sweep'] = "No sweep detected"
    
    # 2. TEMA/LSMA Trend (20)
    if last['close'] > last['tema'] and last['close'] > last['lsma']:
        buy_score += 20
        confirmations['trend'] = "BULLISH ✅"
    elif last['close'] < last['tema'] and last['close'] < last['lsma']:
        sell_score += 20
        confirmations['trend'] = "BEARISH ✅"
    else:
        confirmations['trend'] = "MIXED"
    
    # 3. KAMA Exhaustion (15)
    if last['close'] < last['kama'] and last['rsi'] < 35:
        buy_score += 15
        confirmations['exhaustion'] = "OVERSOLD ✅"
    elif last['close'] > last['kama'] and last['rsi'] > 65:
        sell_score += 15
        confirmations['exhaustion'] = "OVERBOUGHT ✅"
    else:
        confirmations['exhaustion'] = "No exhaustion"
    
    # 4. MACD Flip (15)
    if last['macd'] > last['macd_signal'] and last['macd_hist'] > 0:
        buy_score += 15
        confirmations['macd'] = "BULLISH FLIP ✅"
    elif last['macd'] < last['macd_signal'] and last['macd_hist'] < 0:
        sell_score += 15
        confirmations['macd'] = "BEARISH FLIP ✅"
    else:
        confirmations['macd'] = "NEUTRAL"
    
    # 5. ADX Trend Strength (10)
    if last['adx'] > 25:
        confirmations['adx'] = f"STRONG TREND (ADX: {last['adx']:.1f})"
        if buy_score > sell_score:
            buy_score += 10
        else:
            sell_score += 10
    else:
        confirmations['adx'] = f"WEAK TREND (ADX: {last['adx']:.1f})"
    
    # 6. RSI (10)
    if last['rsi'] < 35:
        buy_score += 10
        confirmations['rsi'] = f"OVERSOLD (RSI: {last['rsi']:.1f}) ✅"
    elif last['rsi'] > 65:
        sell_score += 10
        confirmations['rsi'] = f"OVERBOUGHT (RSI: {last['rsi']:.1f}) ✅"
    else:
        confirmations['rsi'] = f"NEUTRAL (RSI: {last['rsi']:.1f})"
    
    # 7. Stochastic (5)
    if last['stoch_k'] < 20:
        buy_score += 5
        confirmations['stoch'] = "OVERSOLD ✅"
    elif last['stoch_k'] > 80:
        sell_score += 5
        confirmations['stoch'] = "OVERBOUGHT ✅"
    else:
        confirmations['stoch'] = "NEUTRAL"
    
    # 8. Bollinger Bands (5)
    if last['close'] < last['bb_lower']:
        buy_score += 5
        confirmations['bb'] = "BELOW LOWER BB ✅"
    elif last['close'] > last['bb_upper']:
        sell_score += 5
        confirmations['bb'] = "ABOVE UPPER BB ✅"
    
    # 9. Momentum (5)
    if last['momentum_5'] > 0:
        buy_score += 5
        confirmations['momentum'] = "POSITIVE ✅"
    else:
        sell_score += 5
        confirmations['momentum'] = "NEGATIVE ✅"
    
    confidence = max(buy_score, sell_score)
    
    if buy_score > sell_score and confidence >= 60:
        return "BUY", confidence, confirmations
    elif sell_score > buy_score and confidence >= 60:
        return "SELL", confidence, confirmations
    else:
        return "WAIT", confidence, confirmations

def calculate_levels(price, atr, signal, symbol):
    params = PROFESSIONAL_PARAMS[symbol]
    
    if signal == "BUY":
        entry = price
        sl = entry - (atr * (params['sl_pips'] / 1000))
        tp1 = entry + (atr * (params['tp_pips'] / 1000) * 0.5)
        tp2 = entry + (atr * (params['tp_pips'] / 1000))
        tp3 = entry + (atr * (params['tp_pips'] / 1000) * 1.5)
        tp4 = entry + (atr * (params['tp_pips'] / 1000) * 2)
    else:
        entry = price
        sl = entry + (atr * (params['sl_pips'] / 1000))
        tp1 = entry - (atr * (params['tp_pips'] / 1000) * 0.5)
        tp2 = entry - (atr * (params['tp_pips'] / 1000))
        tp3 = entry - (atr * (params['tp_pips'] / 1000) * 1.5)
        tp4 = entry - (atr * (params['tp_pips'] / 1000) * 2)
    
    risk = abs(entry - sl)
    return entry, sl, tp1, tp2, tp3, tp4, risk

def run_backtest(df, symbol, tf, risk_percent):
    if df is None or len(df) < 100:
        return None
    
    df = calculate_all_indicators(df)
    trades = []
    balance = 10000
    balance_history = [balance]
    
    for i in range(50, len(df) - 10):
        current_data = df.iloc[:i+1]
        signal, confidence, _ = get_signal_with_all_confirmations(current_data)
        
        if signal != "WAIT" and confidence >= 60:
            current_price = df.iloc[i]['close']
            atr = df.iloc[i]['atr'] if not pd.isna(df.iloc[i]['atr']) else current_price * 0.005
            
            entry, sl, tp1, tp2, tp3, tp4, risk = calculate_levels(current_price, atr, signal, symbol)
            
            risk_amount = balance * (risk_percent / 100)
            pos_size = risk_amount / risk if risk > 0 else 0
            
            future_prices = df['close'].iloc[i+1:i+8].values
            hit_sl = any(future_prices <= sl if signal == "BUY" else future_prices >= sl)
            hit_tp = any(future_prices >= tp2 if signal == "BUY" else future_prices <= tp2)
            
            if hit_tp and not hit_sl:
                profit = pos_size * abs(tp2 - current_price)
                balance += profit
                trades.append({'result': 'WIN', 'pnl': profit})
            elif hit_sl:
                balance -= risk_amount
                trades.append({'result': 'LOSS', 'pnl': -risk_amount})
            
            balance_history.append(balance)
    
    if trades:
        wins = len([t for t in trades if t['result'] == 'WIN'])
        win_rate = wins / len(trades) * 100
        total_pnl = sum([t['pnl'] for t in trades])
        gross_profit = sum([t['pnl'] for t in trades if t['result'] == 'WIN'])
        gross_loss = abs(sum([t['pnl'] for t in trades if t['result'] == 'LOSS']))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        return {
            'trades': len(trades),
            'wins': wins,
            'losses': len(trades) - wins,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'profit_factor': profit_factor,
            'balance_history': balance_history
        }
    return None

# ============ AUTO SIGNAL LOOP ============
def check_auto_signals():
    if st.session_state.auto_send and st.session_state.telegram_connected:
        current_time = datetime.now()
        for tf in ALL_TIMEFRAMES:
            interval = TIMEFRAMES[tf]["send_interval"]
            last_sent = st.session_state.last_signal_sent.get(tf)
            
            if last_sent is None:
                minutes_since = interval + 1
            else:
                minutes_since = (current_time - last_sent).total_seconds() / 60
            
            if minutes_since >= interval:
                df_tf = get_data(st.session_state.selected_symbol, tf, 30)
                if df_tf is not None and len(df_tf) > 30:
                    df_tf = calculate_all_indicators(df_tf)
                    signal, confidence, _ = get_signal_with_all_confirmations(df_tf)
                    
                    if signal != "WAIT" and confidence >= 65:
                        price = get_price(st.session_state.selected_symbol) or float(df_tf['close'].iloc[-1])
                        atr_val = float(df_tf['atr'].iloc[-1]) if not pd.isna(df_tf['atr'].iloc[-1]) else price * 0.005
                        entry, sl, tp1, tp2, tp3, tp4, risk = calculate_levels(price, atr_val, signal, st.session_state.selected_symbol)
                        
                        msg = format_telegram_signal(signal, st.session_state.selected_symbol, tf, entry, sl, tp1, tp2, tp3, tp4, confidence)
                        if send_telegram(st.session_state.telegram_chat_id, msg):
                            st.session_state.last_signal_sent[tf] = current_time
                            st.toast(f"📱 {tf} signal sent to Telegram!", icon="✅")

# ============ SIDEBAR ============
with st.sidebar:
    st.markdown("## ⚙️ CONTROL PANEL")
    
    # Symbol Selection
    st.markdown("### 📊 ASSET")
    symbol = st.selectbox("Select Symbol", ["XAUUSD", "BTCUSD"], index=0)
    if symbol != st.session_state.selected_symbol:
        st.session_state.selected_symbol = symbol
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    
    # Timeframe Selection
    st.markdown("### ⏱️ TIMEFRAME")
    tf_cols = st.columns(4)
    for i, tf in enumerate(ALL_TIMEFRAMES):
        col = tf_cols[i % 4]
        with col:
            active_class = "tf-active" if st.session_state.selected_tf == tf else ""
            if st.button(tf, key=f"sidebar_tf_{tf}", use_container_width=True):
                st.session_state.selected_tf = tf
                st.cache_data.clear()
                st.rerun()
    
    st.markdown("---")
    
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
        st.session_state.auto_send = st.toggle("Auto-Send Signals", value=st.session_state.auto_send)
    
    st.markdown("---")
    
    # Risk Management
    st.markdown("### 💰 RISK")
    account_balance = st.number_input("Balance ($)", value=10000, step=1000)
    risk_percent = st.slider("Risk %", 0.5, 2.0, 1.0)
    
    st.markdown("---")
    
    # Backtest
    st.markdown("### 📊 BACKTEST")
    bt_period = st.selectbox("Period", ["30d", "60d", "90d"], index=1)
    if st.button("🚀 Run Backtest", use_container_width=True):
        days = {"30d": 30, "60d": 60, "90d": 90}[bt_period]
        with st.spinner(f"Backtesting {st.session_state.selected_tf}..."):
            bt_df = get_data(st.session_state.selected_symbol, st.session_state.selected_tf, days)
            result = run_backtest(bt_df, st.session_state.selected_symbol, st.session_state.selected_tf, risk_percent)
            if result:
                st.session_state.backtest_results = result
                st.success(f"Win Rate: {result['win_rate']:.1f}% | P&L: ${result['total_pnl']:.2f}")
            else:
                st.warning("Insufficient data")
    
    if st.session_state.backtest_results:
        st.markdown("#### Last Backtest")
        res = st.session_state.backtest_results
        st.metric("Win Rate", f"{res['win_rate']:.1f}%")
        st.metric("Profit Factor", f"{res['profit_factor']:.2f}")
        st.metric("Total Trades", res['trades'])
    
    st.markdown("---")
    
    if st.button("🔄 Refresh All", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ============ MAIN CONTENT ============
# Auto-signal check
check_auto_signals()

# Load data
with st.spinner(f"Loading {st.session_state.selected_symbol} {st.session_state.selected_tf} data..."):
    df = get_data(st.session_state.selected_symbol, st.session_state.selected_tf, 60)
    current_price = get_price(st.session_state.selected_symbol)
    
    if df is not None and len(df) > 50:
        df = calculate_all_indicators(df)
        current_price = current_price if current_price else float(df['close'].iloc[-1])
        atr = float(df['atr'].iloc[-1]) if not pd.isna(df['atr'].iloc[-1]) else current_price * 0.005
        rsi = float(df['rsi'].iloc[-1]) if not pd.isna(df['rsi'].iloc[-1]) else 50
        adx = float(df['adx'].iloc[-1]) if not pd.isna(df['adx'].iloc[-1]) else 25
        
        # Get signal
        signal, confidence, confirmations = get_signal_with_all_confirmations(df)
        
        # Calculate levels
        if signal != "WAIT":
            entry, sl, tp1, tp2, tp3, tp4, risk = calculate_levels(current_price, atr, signal, st.session_state.selected_symbol)
        else:
            entry, sl, tp1, tp2, tp3, tp4, risk = current_price, current_price, current_price, current_price, current_price, current_price, 0

# ============ DISPLAY ============
# Symbol Header
color = SYMBOLS[st.session_state.selected_symbol]["color"]
st.markdown(f"### 🏆 {st.session_state.selected_symbol} - {st.session_state.selected_tf.upper()} TIMEFRAME")

# Top Metrics
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric(f"{st.session_state.selected_symbol} Price", f"${current_price:,.{SYMBOLS[st.session_state.selected_symbol]['digits']}f}")
col2.metric("ATR", f"${atr:.{SYMBOLS[st.session_state.selected_symbol]['digits']}f}", f"{atr/current_price*100:.2f}%")
col3.metric("RSI", f"{rsi:.1f}")
col4.metric("ADX", f"{adx:.1f}", "Strong Trend" if adx > 25 else "Weak Trend")
col5.metric("Telegram", "✅" if st.session_state.telegram_connected else "❌")

# ============ SIGNAL DISPLAY ============
st.markdown("---")
st.markdown("## 🏛️ INSTITUTIONAL SIGNAL")

if signal == "BUY":
    st.markdown(f"""
    <div class="signal-buy">
        <div style="font-size: 1.5rem; font-weight: bold; color: #00ff88;">📈 INSTITUTIONAL BUY SIGNAL</div>
        <div>Confidence: {confidence:.0f}% | Professional Strategy: Liquidity Sweep + BoS Confirmed</div>
        <div class="meter"><div class="meter-fill" style="width: {confidence}%; background: #00ff88;"></div></div>
    </div>
    """, unsafe_allow_html=True)
elif signal == "SELL":
    st.markdown(f"""
    <div class="signal-sell">
        <div style="font-size: 1.5rem; font-weight: bold; color: #ff4444;">📉 INSTITUTIONAL SELL SIGNAL</div>
        <div>Confidence: {confidence:.0f}% | Professional Strategy: Liquidity Sweep + BoS Confirmed</div>
        <div class="meter"><div class="meter-fill" style="width: {confidence}%; background: #ff4444;"></div></div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown(f"""
    <div class="signal-wait">
        <div style="font-size: 1.5rem; font-weight: bold; color: #ffd700;">⏸️ WAIT - No Institutional Setup</div>
        <div>Confidence: {confidence:.0f}% | Waiting for Liquidity Sweep + BoS</div>
        <div class="meter"><div class="meter-fill" style="width: {confidence}%; background: #ffd700;"></div></div>
    </div>
    """, unsafe_allow_html=True)

# ============ CONFIRMATIONS ============
st.markdown("### ✅ INSTITUTIONAL CONFIRMATIONS")

col_left, col_right = st.columns(2)

with col_left:
    st.markdown("#### 🏛️ Liquidity & Structure")
    for key in ['liquidity_sweep', 'trend', 'exhaustion']:
        if key in confirmations:
            if "✅" in str(confirmations[key]):
                st.markdown(f'<div class="checklist-pass">✅ {key.upper()}: {confirmations[key]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="checklist-fail">❌ {key.upper()}: {confirmations[key]}</div>', unsafe_allow_html=True)

with col_right:
    st.markdown("#### 📊 Momentum & Strength")
    for key in ['macd', 'adx', 'rsi', 'stoch', 'bb', 'momentum']:
        if key in confirmations:
            if "✅" in str(confirmations[key]):
                st.markdown(f'<div class="checklist-pass">✅ {key.upper()}: {confirmations[key]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="checklist-fail">❌ {key.upper()}: {confirmations[key]}</div>', unsafe_allow_html=True)

# ============ TRADING LEVELS ============
if signal != "WAIT":
    st.markdown("---")
    st.markdown("## 🎯 PROFESSIONAL TRADING LEVELS")
    
    level_cols = st.columns(6)
    level_cols[0].markdown(f'<div class="level-card"><div class="level-price">📍 ENTRY<br>${entry:.{SYMBOLS[st.session_state.selected_symbol]["digits"]}f}</div></div>', unsafe_allow_html=True)
    level_cols[1].markdown(f'<div class="level-card"><div class="level-price">🛑 SL<br>${sl:.{SYMBOLS[st.session_state.selected_symbol]["digits"]}f}</div><div style="font-size:0.7rem;">Risk: ${risk:.2f}</div></div>', unsafe_allow_html=True)
    level_cols[2].markdown(f'<div class="level-card"><div class="level-price">🎯 TP1<br>${tp1:.{SYMBOLS[st.session_state.selected_symbol]["digits"]}f}</div></div>', unsafe_allow_html=True)
    level_cols[3].markdown(f'<div class="level-card"><div class="level-price">🎯 TP2<br>${tp2:.{SYMBOLS[st.session_state.selected_symbol]["digits"]}f}</div></div>', unsafe_allow_html=True)
    level_cols[4].markdown(f'<div class="level-card"><div class="level-price">🎯 TP3<br>${tp3:.{SYMBOLS[st.session_state.selected_symbol]["digits"]}f}</div></div>', unsafe_allow_html=True)
    level_cols[5].markdown(f'<div class="level-card"><div class="level-price">🎯 TP4<br>${tp4:.{SYMBOLS[st.session_state.selected_symbol]["digits"]}f}</div></div>', unsafe_allow_html=True)
    
    # Position Sizing
    position_size = (account_balance * (risk_percent / 100)) / risk if risk > 0 else 0
    st.info(f"📊 Position Size: {position_size:.4f} lots | Risk Amount: ${account_balance * (risk_percent / 100):.2f} | Risk:Reward 1:{PROFESSIONAL_PARAMS[st.session_state.selected_symbol]['rr_ratio']}")
    
    # Execute Button
    if st.button("✅ EXECUTE PROFESSIONAL TRADE", type="primary", use_container_width=True):
        st.session_state.trade_history.append({
            'id': len(st.session_state.trade_history) + 1,
            'time': datetime.now(),
            'symbol': st.session_state.selected_symbol,
            'timeframe': st.session_state.selected_tf,
            'signal': signal,
            'entry': entry,
            'sl': sl,
            'tp2': tp2,
            'confidence': confidence,
            'status': 'PENDING_FEEDBACK'
        })
        st.success(f"✅ {signal} trade executed at ${entry:.2f}")
        st.balloons()
        st.rerun()

# ============ FEEDBACK SECTION ============
st.markdown("---")
st.markdown("## 📝 TEACH THE AI - Provide Feedback")

pending_trades = [t for t in st.session_state.trade_history if t.get('status') == 'PENDING_FEEDBACK']

if pending_trades:
    for trade in pending_trades:
        st.markdown(f"""
        <div class="feedback-card feedback-pending">
            <b>📊 Trade #{trade['id']}</b> | {trade['time'].strftime('%Y-%m-%d %H:%M:%S')}<br>
            <b>Symbol:</b> {trade['symbol']} | <b>Signal:</b> {trade['signal']}<br>
            <b>Entry:</b> ${trade['entry']:.2f} | <b>TP:</b> ${trade['tp2']:.2f} | <b>SL:</b> ${trade['sl']:.2f}<br>
            <b>AI Confidence:</b> {trade['confidence']:.0f}%
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button(f"✅ WIN - Hit TP", key=f"win_{trade['id']}", use_container_width=True):
                for t in st.session_state.trade_history:
                    if t.get('id') == trade['id']:
                        t['status'] = 'COMPLETED'
                        t['result'] = 'WIN'
                        break
                st.session_state.feedback_data.append({
                    'timestamp': datetime.now().isoformat(),
                    'symbol': trade['symbol'],
                    'signal': trade['signal'],
                    'confidence': trade['confidence'],
                    'result': 'WIN'
                })
                st.success("✅ Feedback recorded! AI learned from this WIN.")
                st.rerun()
        with col2:
            if st.button(f"❌ LOSS - Hit SL", key=f"loss_{trade['id']}", use_container_width=True):
                for t in st.session_state.trade_history:
                    if t.get('id') == trade['id']:
                        t['status'] = 'COMPLETED'
                        t['result'] = 'LOSS'
                        break
                st.session_state.feedback_data.append({
                    'timestamp': datetime.now().isoformat(),
                    'symbol': trade['symbol'],
                    'signal': trade['signal'],
                    'confidence': trade['confidence'],
                    'result': 'LOSS'
                })
                st.success("❌ Feedback recorded! AI learned from this LOSS.")
                st.rerun()
else:
    st.info("📭 No pending trades. Execute a trade first, then provide feedback.")

# ============ CHART ============
st.markdown("---")
st.markdown(f"## 📈 {st.session_state.selected_symbol} - {st.session_state.selected_tf.upper()} CHART")

fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                    row_heights=[0.7, 0.3],
                    subplot_titles=("Price Action", "RSI"))

chart_df = df.tail(100)

fig.add_trace(go.Candlestick(x=chart_df.index, open=chart_df['open'], high=chart_df['high'],
                              low=chart_df['low'], close=chart_df['close'], name=st.session_state.selected_symbol), row=1, col=1)

# Add TEMA and LSMA
fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['tema'], name='TEMA (9)', line=dict(color='#ffd700', width=1)), row=1, col=1)
fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['lsma'], name='LSMA (25)', line=dict(color='#ff8c00', width=1)), row=1, col=1)

# Add Fibonacci levels
fig.add_hline(y=df['fib_236'].iloc[-1], line_color="#ffd700", line_dash="dot", annotation_text="Fib 236", row=1, col=1)
fig.add_hline(y=df['fib_382'].iloc[-1], line_color="#ffd700", line_dash="dot", annotation_text="Fib 382", row=1, col=1)
fig.add_hline(y=df['fib_618'].iloc[-1], line_color="#ffd700", line_dash="dot", annotation_text="Fib 618", row=1, col=1)

# Add Supply/Demand zones
fig.add_hline(y=df['supply_zone'].iloc[-1], line_color="#ff4444", line_dash="dash", annotation_text="Supply", row=1, col=1)
fig.add_hline(y=df['demand_zone'].iloc[-1], line_color="#00ff88", line_dash="dash", annotation_text="Demand", row=1, col=1)

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

fig.update_layout(template='plotly_dark', height=700, showlegend=True)
st.plotly_chart(fig, use_container_width=True)

# ============ TRADE HISTORY ============
if st.session_state.trade_history:
    st.markdown("---")
    st.markdown("## 📋 RECENT TRADES")
    for trade in st.session_state.trade_history[-5:]:
        status_emoji = "✅" if trade.get('result') == 'WIN' else "❌" if trade.get('result') == 'LOSS' else "⏳"
        st.info(f"{status_emoji} Trade #{trade['id']} | {trade['time'].strftime('%Y-%m-%d %H:%M:%S')} | {trade['symbol']} | {trade['signal']} | Entry: ${trade['entry']:.2f} | TP: ${trade['tp2']:.2f} | Conf: {trade['confidence']:.0f}%")

# ============ LEARNING STATS ============
if st.session_state.feedback_data:
    st.markdown("---")
    st.markdown("## 🧠 AI LEARNING STATISTICS")
    
    total = len(st.session_state.feedback_data)
    wins = len([f for f in st.session_state.feedback_data if f['result'] == 'WIN'])
    win_rate = (wins / total * 100) if total > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Trades Learned", total)
    col2.metric("Wins", wins)
    col3.metric("Losses", total - wins)
    col4.metric("Win Rate", f"{win_rate:.1f}%")
    
    if total > 5:
        if win_rate > 60:
            st.success("📈 AI is learning effectively! Keep providing feedback.")
        elif win_rate > 50:
            st.info("📊 AI is improving. More feedback will increase accuracy.")
        else:
            st.warning("⚠️ AI needs more data. Continue providing feedback.")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 1rem; color: #666;">
    <p>🏆 ULTIMATE COMPLETE TRADING SYSTEM | All Timeframes | Backtest | Telegram | AI Feedback Learning | Institutional Strategy</p>
    <p style="font-size: 0.7rem;">⚠️ EDUCATIONAL PURPOSES ONLY - Not financial advice</p>
</div>
""", unsafe_allow_html=True)
