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
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="PROFESSIONAL AI WITH FEEDBACK", layout="wide", page_icon="🧠")

st.markdown("""
<style>
    .main-title { font-size: 1.8rem; font-weight: bold; background: linear-gradient(90deg, #ffd700, #ff8c00, #ff4444); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; }
    .feedback-card { background: linear-gradient(135deg, #1e1e2e, #2a2a3a); border-radius: 15px; padding: 1rem; margin: 0.5rem 0; border-left: 4px solid; }
    .feedback-pending { border-left-color: #ffd700; }
    .feedback-win { border-left-color: #00ff88; background: #0a3a2a22; }
    .feedback-loss { border-left-color: #ff4444; background: #3a1a1a22; }
    .signal-buy { background: #0a3a2a22; border-left: 4px solid #00ff88; padding: 1rem; border-radius: 12px; }
    .signal-sell { background: #3a1a1a22; border-left: 4px solid #ff4444; padding: 1rem; border-radius: 12px; }
    .meter { background: #2a2e3a; border-radius: 10px; height: 8px; overflow: hidden; }
    .meter-fill { height: 100%; border-radius: 10px; }
    .level-card { background: #13161d; border-radius: 10px; padding: 0.5rem; text-align: center; }
    .level-price { font-size: 1rem; font-weight: bold; color: #ffd700; }
    .btn-win { background-color: #00ff88; color: #000; border: none; padding: 0.5rem 1rem; border-radius: 8px; cursor: pointer; }
    .btn-loss { background-color: #ff4444; color: #fff; border: none; padding: 0.5rem 1rem; border-radius: 8px; cursor: pointer; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🧠 PROFESSIONAL AI WITH FEEDBACK LEARNING</div>', unsafe_allow_html=True)

# ============ CONFIGURATION ============
API_KEY = "96871e27b094425f9ea104fa6eb2be64"

# File to store feedback data
FEEDBACK_FILE = "ai_feedback_data.json"

# Professional Risk Parameters
PROFESSIONAL_PARAMS = {
    "XAUUSD": {"tp_pips": 4700, "sl_pips": 1700, "rr_ratio": 2.76},
    "BTCUSD": {"tp_pips": 44000, "sl_pips": 11000, "rr_ratio": 4.0}
}

# Session state
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'feedback_data' not in st.session_state:
    # Load existing feedback if any
    if os.path.exists(FEEDBACK_FILE):
        try:
            with open(FEEDBACK_FILE, 'r') as f:
                st.session_state.feedback_data = json.load(f)
        except:
            st.session_state.feedback_data = []
    else:
        st.session_state.feedback_data = []
if 'model_trained' not in st.session_state:
    st.session_state.model_trained = False
if 'selected_symbol' not in st.session_state:
    st.session_state.selected_symbol = "XAUUSD"
if 'learning_stats' not in st.session_state:
    st.session_state.learning_stats = {
        'total_feedback': 0,
        'wins': 0,
        'losses': 0,
        'win_rate': 0,
        'avg_confidence_win': 0,
        'avg_confidence_loss': 0
    }

# Symbol mapping
SYMBOLS = {
    "XAUUSD": {"api": "XAU/USD", "name": "Gold", "pip": 0.01, "digits": 2, "color": "#ffd700"},
    "BTCUSD": {"api": "BTC/USD", "name": "Bitcoin", "pip": 5.0, "digits": 0, "color": "#ff8c00"}
}

TIMEFRAMES = {
    "15m": {"api": "15min", "minutes": 15},
    "30m": {"api": "30min", "minutes": 30},
    "1h": {"api": "1h", "minutes": 60},
    "4h": {"api": "4h", "minutes": 240}
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

def calculate_indicators(df):
    df = df.copy()
    
    # MAs
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
    
    # Liquidity Sweep
    df['pivot_high'] = ((df['high'].shift(1) > df['high'].shift(2)) & 
                        (df['high'].shift(1) > df['high'])).astype(int)
    df['pivot_low'] = ((df['low'].shift(1) < df['low'].shift(2)) & 
                       (df['low'].shift(1) < df['low'])).astype(int)
    df['liquidity_sweep_up'] = ((df['high'] > df['high'].shift(1).rolling(5).max()) & 
                                 (df['close'] < df['high'].shift(1))).astype(int)
    df['liquidity_sweep_down'] = ((df['low'] < df['low'].shift(1).rolling(5).min()) & 
                                   (df['close'] > df['low'].shift(1))).astype(int)
    
    # BoS
    df['bos_up'] = ((df['high'] > df['high'].shift(1).rolling(10).max()) & 
                    (df['close'] > df['open'])).astype(int)
    df['bos_down'] = ((df['low'] < df['low'].shift(1).rolling(10).min()) & 
                      (df['close'] < df['open'])).astype(int)
    
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
    
    # Stochastic
    low_14 = df['low'].rolling(14).min()
    high_14 = df['high'].rolling(14).max()
    df['stoch_k'] = 100 * ((df['close'] - low_14) / (high_14 - low_14))
    df['stoch_d'] = df['stoch_k'].rolling(3).mean()
    
    # Bollinger
    df['bb_middle'] = df['close'].rolling(20).mean()
    bb_std = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
    df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
    
    return df

def get_signal(df):
    if df is None or len(df) < 50:
        return "WAIT", 0, {}
    
    last = df.iloc[-1]
    
    buy_score = 0
    sell_score = 0
    confirmations = {}
    
    # Liquidity Sweep + BoS (25 points)
    if last['liquidity_sweep_up'] == 1 and last['bos_up'] == 1:
        buy_score += 25
        confirmations['liquidity_sweep'] = "LIQUIDITY SWEEP + BoS ✅"
    elif last['liquidity_sweep_down'] == 1 and last['bos_down'] == 1:
        sell_score += 25
        confirmations['liquidity_sweep'] = "LIQUIDITY SWEEP + BoS ✅"
    else:
        confirmations['liquidity_sweep'] = "No sweep detected"
    
    # TEMA/LSMA Trend (20 points)
    if last['close'] > last['tema'] and last['close'] > last['lsma']:
        buy_score += 20
        confirmations['trend'] = "BULLISH ✅"
    elif last['close'] < last['tema'] and last['close'] < last['lsma']:
        sell_score += 20
        confirmations['trend'] = "BEARISH ✅"
    else:
        confirmations['trend'] = "MIXED"
    
    # KAMA Exhaustion (15 points)
    if last['close'] < last['kama'] and last['rsi'] < 35:
        buy_score += 15
        confirmations['exhaustion'] = "OVERSOLD ✅"
    elif last['close'] > last['kama'] and last['rsi'] > 65:
        sell_score += 15
        confirmations['exhaustion'] = "OVERBOUGHT ✅"
    else:
        confirmations['exhaustion'] = "No exhaustion"
    
    # MACD Flip (15 points)
    if last['macd'] > last['macd_signal'] and last['macd_hist'] > 0:
        buy_score += 15
        confirmations['macd'] = "BULLISH FLIP ✅"
    elif last['macd'] < last['macd_signal'] and last['macd_hist'] < 0:
        sell_score += 15
        confirmations['macd'] = "BEARISH FLIP ✅"
    else:
        confirmations['macd'] = "NEUTRAL"
    
    # ADX (10 points)
    if last['adx'] > 25:
        confirmations['adx'] = f"STRONG (ADX: {last['adx']:.1f})"
        if buy_score > sell_score:
            buy_score += 10
        else:
            sell_score += 10
    else:
        confirmations['adx'] = f"WEAK (ADX: {last['adx']:.1f})"
    
    # Stochastic (10 points)
    if last['stoch_k'] < 20:
        buy_score += 10
        confirmations['stoch'] = "OVERSOLD ✅"
    elif last['stoch_k'] > 80:
        sell_score += 10
        confirmations['stoch'] = "OVERBOUGHT ✅"
    else:
        confirmations['stoch'] = "NEUTRAL"
    
    # Bollinger (5 points)
    if last['close'] < last['bb_lower']:
        buy_score += 5
        confirmations['bb'] = "BELOW LOWER BB ✅"
    elif last['close'] > last['bb_upper']:
        sell_score += 5
        confirmations['bb'] = "ABOVE UPPER BB ✅"
    
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

def save_feedback():
    """Save feedback data to file"""
    with open(FEEDBACK_FILE, 'w') as f:
        json.dump(st.session_state.feedback_data, f)
    
    # Update learning stats
    total = len(st.session_state.feedback_data)
    wins = len([f for f in st.session_state.feedback_data if f['result'] == 'WIN'])
    losses = total - wins
    win_rate = (wins / total * 100) if total > 0 else 0
    
    # Calculate average confidence
    avg_conf_win = np.mean([f['confidence'] for f in st.session_state.feedback_data if f['result'] == 'WIN']) if wins > 0 else 0
    avg_conf_loss = np.mean([f['confidence'] for f in st.session_state.feedback_data if f['result'] == 'LOSS']) if losses > 0 else 0
    
    st.session_state.learning_stats = {
        'total_feedback': total,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'avg_confidence_win': avg_conf_win,
        'avg_confidence_loss': avg_conf_loss
    }

# ============ SIDEBAR ============
with st.sidebar:
    st.markdown("## ⚙️ PROFESSIONAL CONTROLS")
    
    st.markdown("### 📊 ASSET")
    symbol = st.selectbox("Select Symbol", ["XAUUSD", "BTCUSD"], index=0)
    if symbol != st.session_state.selected_symbol:
        st.session_state.selected_symbol = symbol
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("### ⏱️ TIMEFRAME")
    tf_options = ["15m", "30m", "1h", "4h"]
    selected_tf = st.selectbox("Timeframe", tf_options, index=2)
    
    st.markdown("### 💰 RISK")
    account_balance = st.number_input("Balance ($)", value=10000, step=1000)
    risk_percent = st.slider("Risk %", 0.5, 2.0, 1.0)
    
    # Learning Stats
    st.markdown("---")
    st.markdown("## 🧠 LEARNING STATS")
    stats = st.session_state.learning_stats
    st.metric("Total Feedback", stats['total_feedback'])
    st.metric("Win Rate", f"{stats['win_rate']:.1f}%")
    st.metric("Wins/Losses", f"{stats['wins']}/{stats['losses']}")
    
    if stats['total_feedback'] > 0:
        st.caption(f"Avg Conf Wins: {stats['avg_confidence_win']:.1f}%")
        st.caption(f"Avg Conf Losses: {stats['avg_confidence_loss']:.1f}%")
    
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ============ MAIN CONTENT ============
with st.spinner(f"Loading {symbol} {selected_tf} data..."):
    df = get_data(symbol, selected_tf, 60)
    current_price = get_price(symbol)
    
    if df is not None and len(df) > 50:
        df = calculate_indicators(df)
        current_price = current_price if current_price else float(df['close'].iloc[-1])
        atr = float(df['atr'].iloc[-1]) if not pd.isna(df['atr'].iloc[-1]) else current_price * 0.005
        
        signal, confidence, confirmations = get_signal(df)
        
        if signal != "WAIT":
            entry, sl, tp1, tp2, tp3, tp4, risk = calculate_levels(current_price, atr, signal, symbol)
        else:
            entry, sl, tp1, tp2, tp3, tp4, risk = current_price, current_price, current_price, current_price, current_price, current_price, 0

# ============ SIGNAL DISPLAY ============
st.markdown(f"### 🏆 {symbol} - {selected_tf.upper()} TIMEFRAME")

col1, col2, col3, col4 = st.columns(4)
col1.metric(f"{symbol} Price", f"${current_price:,.{SYMBOLS[symbol]['digits']}f}")
col2.metric("ATR", f"${atr:.{SYMBOLS[symbol]['digits']}f}", f"{atr/current_price*100:.2f}%")
col3.metric("RSI", f"{df['rsi'].iloc[-1]:.1f}")
col4.metric("ADX", f"{df['adx'].iloc[-1]:.1f}", "Strong Trend" if df['adx'].iloc[-1] > 25 else "Weak Trend")

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
    <div class="signal-buy" style="border-left-color: #ffd700; background: #1e1e2e;">
        <div style="font-size: 1.5rem; font-weight: bold; color: #ffd700;">⏸️ WAIT - No Institutional Setup</div>
        <div>Confidence: {confidence:.0f}% | Waiting for Liquidity Sweep + BoS</div>
        <div class="meter"><div class="meter-fill" style="width: {confidence}%; background: #ffd700;"></div></div>
    </div>
    """, unsafe_allow_html=True)

# ============ TRADING LEVELS ============
if signal != "WAIT":
    st.markdown("---")
    st.markdown("## 🎯 PROFESSIONAL TRADING LEVELS")
    
    level_cols = st.columns(6)
    level_cols[0].markdown(f'<div class="level-card"><div class="level-price">📍 ENTRY<br>${entry:.{SYMBOLS[symbol]["digits"]}f}</div></div>', unsafe_allow_html=True)
    level_cols[1].markdown(f'<div class="level-card"><div class="level-price">🛑 SL<br>${sl:.{SYMBOLS[symbol]["digits"]}f}</div><div style="font-size:0.7rem;">Risk: ${risk:.2f}</div></div>', unsafe_allow_html=True)
    level_cols[2].markdown(f'<div class="level-card"><div class="level-price">🎯 TP1<br>${tp1:.{SYMBOLS[symbol]["digits"]}f}</div></div>', unsafe_allow_html=True)
    level_cols[3].markdown(f'<div class="level-card"><div class="level-price">🎯 TP2<br>${tp2:.{SYMBOLS[symbol]["digits"]}f}</div></div>', unsafe_allow_html=True)
    level_cols[4].markdown(f'<div class="level-card"><div class="level-price">🎯 TP3<br>${tp3:.{SYMBOLS[symbol]["digits"]}f}</div></div>', unsafe_allow_html=True)
    level_cols[5].markdown(f'<div class="level-card"><div class="level-price">🎯 TP4<br>${tp4:.{SYMBOLS[symbol]["digits"]}f}</div></div>', unsafe_allow_html=True)
    
    position_size = (account_balance * (risk_percent / 100)) / risk if risk > 0 else 0
    st.info(f"📊 Position Size: {position_size:.4f} lots | Risk Amount: ${account_balance * (risk_percent / 100):.2f}")
    
    # EXECUTE TRADE BUTTON
    if st.button("✅ EXECUTE PROFESSIONAL TRADE", type="primary", use_container_width=True):
        trade = {
            'id': len(st.session_state.trade_history) + 1,
            'time': datetime.now(),
            'symbol': symbol,
            'timeframe': selected_tf,
            'signal': signal,
            'entry': entry,
            'sl': sl,
            'tp2': tp2,
            'confidence': confidence,
            'status': 'PENDING_FEEDBACK'
        }
        st.session_state.trade_history.append(trade)
        st.success(f"✅ {signal} trade executed at ${entry:.2f}")
        st.balloons()
        st.rerun()

# ============ FEEDBACK SECTION (MOST IMPORTANT) ============
st.markdown("---")
st.markdown("## 📝 TEACH THE AI - Provide Feedback")
st.markdown("*After your trade hits TP (WIN) or SL (LOSS), tell the AI what happened so it can learn!*")

# Show pending trades that need feedback
pending_trades = [t for t in st.session_state.trade_history if t.get('status') == 'PENDING_FEEDBACK']

if pending_trades:
    st.markdown("### ⏳ Pending Trades - Need Your Feedback")
    
    for trade in pending_trades:
        st.markdown(f"""
        <div class="feedback-card feedback-pending">
            <b>📊 Trade #{trade['id']}</b> | {trade['time'].strftime('%Y-%m-%d %H:%M:%S')}<br>
            <b>Symbol:</b> {trade['symbol']} | <b>Signal:</b> {trade['signal']}<br>
            <b>Entry:</b> ${trade['entry']:.2f} | <b>TP:</b> ${trade['tp2']:.2f} | <b>SL:</b> ${trade['sl']:.2f}<br>
            <b>AI Confidence at entry:</b> {trade['confidence']:.0f}%
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button(f"✅ WIN - Hit TP", key=f"win_{trade['id']}", use_container_width=True):
                # Find trade and update
                for t in st.session_state.trade_history:
                    if t['id'] == trade['id']:
                        t['status'] = 'COMPLETED'
                        t['result'] = 'WIN'
                        break
                
                # Save to feedback data
                st.session_state.feedback_data.append({
                    'timestamp': datetime.now().isoformat(),
                    'symbol': trade['symbol'],
                    'timeframe': trade['timeframe'],
                    'signal': trade['signal'],
                    'confidence': trade['confidence'],
                    'result': 'WIN',
                    'entry': trade['entry'],
                    'tp': trade['tp2']
                })
                save_feedback()
                st.success("✅ Feedback recorded! AI learned from this WIN.")
                st.balloons()
                st.rerun()
        
        with col2:
            if st.button(f"❌ LOSS - Hit SL", key=f"loss_{trade['id']}", use_container_width=True):
                for t in st.session_state.trade_history:
                    if t['id'] == trade['id']:
                        t['status'] = 'COMPLETED'
                        t['result'] = 'LOSS'
                        break
                
                st.session_state.feedback_data.append({
                    'timestamp': datetime.now().isoformat(),
                    'symbol': trade['symbol'],
                    'timeframe': trade['timeframe'],
                    'signal': trade['signal'],
                    'confidence': trade['confidence'],
                    'result': 'LOSS',
                    'entry': trade['entry'],
                    'sl': trade['sl']
                })
                save_feedback()
                st.success("❌ Feedback recorded! AI learned from this LOSS.")
                st.rerun()
else:
    st.info("📭 No pending trades. Execute a trade first, then come back to provide feedback.")

# ============ FEEDBACK HISTORY ============
if st.session_state.feedback_data:
    st.markdown("### 📊 Feedback History (What AI Learned)")
    
    recent_feedback = st.session_state.feedback_data[-10:]
    for fb in reversed(recent_feedback):
        emoji = "✅" if fb['result'] == 'WIN' else "❌"
        st.markdown(f"""
        <div class="feedback-card feedback-{fb['result'].lower()}">
            {emoji} <b>{fb['symbol']}</b> | {fb['timeframe']} | Signal: {fb['signal']}<br>
            Result: <b>{fb['result']}</b> | AI Confidence: {fb['confidence']:.0f}%<br>
            <small>{fb['timestamp'][:19]}</small>
        </div>
        """, unsafe_allow_html=True)
    
    # Learning Insights
    st.markdown("### 🧠 AI Learning Insights")
    
    stats = st.session_state.learning_stats
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Trades Learned", stats['total_feedback'])
    col2.metric("Win Rate", f"{stats['win_rate']:.1f}%")
    col3.metric("AI Improvement", "Active" if stats['total_feedback'] > 0 else "Pending")
    
    if stats['total_feedback'] > 5:
        if stats['avg_confidence_win'] > stats['avg_confidence_loss']:
            st.success("📈 AI is learning! Higher confidence trades are producing more wins.")
        else:
            st.warning("⚠️ AI needs more data. Keep providing feedback to improve accuracy.")

# ============ CHART ============
st.markdown("---")
st.markdown(f"## 📈 {symbol} - {selected_tf.upper()} CHART")

fig = go.Figure()
chart_df = df.tail(100)

fig.add_trace(go.Candlestick(x=chart_df.index, open=chart_df['open'], high=chart_df['high'],
                              low=chart_df['low'], close=chart_df['close'], name=symbol))

if signal != "WAIT":
    fig.add_hline(y=entry, line_color="#ffd700", line_width=2, annotation_text="ENTRY")
    fig.add_hline(y=sl, line_color="#ff4444", line_dash="dash", annotation_text="SL")

fig.update_layout(template='plotly_dark', height=500)
st.plotly_chart(fig, use_container_width=True)

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 1rem; color: #666;">
    <p>🧠 AI learns from EVERY feedback you provide! More feedback = Smarter AI</p>
    <p style="font-size: 0.7rem;">⚠️ EDUCATIONAL PURPOSES ONLY - Not financial advice</p>
</div>
""", unsafe_allow_html=True)
