import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="PRO XAUUSD TRADER", layout="wide", page_icon="🏆")

# Custom CSS for professional look
st.markdown("""
<style>
    .main-title {
        font-size: 2.5rem;
        font-weight: bold;
        background: linear-gradient(90deg, #ffd700, #ff8c00, #ff4444);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 0.5rem;
        margin-bottom: 1rem;
    }
    .signal-box {
        border-radius: 20px;
        padding: 1.5rem;
        text-align: center;
        margin: 1rem 0;
    }
    .signal-buy {
        background: linear-gradient(135deg, #0a3a2a, #0a2a1a);
        border: 2px solid #00ff88;
        box-shadow: 0 0 20px rgba(0,255,136,0.3);
    }
    .signal-sell {
        background: linear-gradient(135deg, #3a1a1a, #2a0a0a);
        border: 2px solid #ff4444;
        box-shadow: 0 0 20px rgba(255,68,68,0.3);
    }
    .signal-wait {
        background: linear-gradient(135deg, #1e1e2e, #2a2a3a);
        border: 2px solid #ffd700;
    }
    .signal-text {
        font-size: 3rem;
        font-weight: bold;
    }
    .confidence-bar {
        background: #333;
        border-radius: 10px;
        height: 10px;
        margin: 10px 0;
        overflow: hidden;
    }
    .confidence-fill {
        background: linear-gradient(90deg, #00ff88, #ffd700);
        height: 100%;
        border-radius: 10px;
        transition: width 0.5s;
    }
    .level-card {
        background: #1e1e2e;
        border-radius: 15px;
        padding: 1rem;
        text-align: center;
        border: 1px solid #333;
        transition: all 0.3s;
    }
    .level-card:hover {
        border-color: #ffd700;
        transform: translateY(-5px);
    }
    .level-label {
        font-size: 0.8rem;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .level-price {
        font-size: 1.4rem;
        font-weight: bold;
        color: #ffd700;
    }
    .level-pnl {
        font-size: 0.8rem;
        margin-top: 5px;
    }
    .metric-card {
        background: linear-gradient(135deg, #1e1e2e, #2a2a3a);
        border-radius: 15px;
        padding: 1rem;
        text-align: center;
        border: 1px solid #ffd70033;
    }
    .big-price {
        font-size: 3rem;
        font-weight: bold;
        color: #ffd700;
    }
    .instruction-box {
        background: #0e1117;
        border-radius: 15px;
        padding: 1rem;
        margin-top: 1rem;
        border-left: 4px solid #ffd700;
    }
    .green-text { color: #00ff88; }
    .red-text { color: #ff4444; }
    .gold-text { color: #ffd700; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🏆 PROFESSIONAL XAUUSD TRADING DASHBOARD</div>', unsafe_allow_html=True)

# ============ CONFIGURATION ============
API_KEY = "96871e27b094425f9ea104fa6eb2be64"
TELEGRAM_BOT_TOKEN = "8369393711:AAGm8ydfJc3UQPyNCPR6uCEr1LQpFw-zV-4"

# Session State
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'telegram_connected' not in st.session_state:
    st.session_state.telegram_connected = False
if 'telegram_chat_id' not in st.session_state:
    st.session_state.telegram_chat_id = None

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
def get_data():
    try:
        url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=1h&outputsize=100&apikey={API_KEY}"
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
    df['sma20'] = df['close'].rolling(20).mean()
    df['sma50'] = df['close'].rolling(50).mean()
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    df['hl'] = df['high'] - df['low']
    df['atr'] = df['hl'].rolling(14).mean()
    
    return df

def get_signal_simple(df):
    """Simple signal logic anyone can understand"""
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last
    
    # Trend direction
    trend_bullish = last['close'] > last['sma20'] and last['sma20'] > last['sma50']
    trend_bearish = last['close'] < last['sma20'] and last['sma20'] < last['sma50']
    
    # RSI condition
    rsi_oversold = last['rsi'] < 35
    rsi_overbought = last['rsi'] > 65
    
    # Price momentum
    momentum_up = last['close'] > prev['close']
    momentum_down = last['close'] < prev['close']
    
    # Calculate score
    buy_score = 0
    sell_score = 0
    
    if trend_bullish:
        buy_score += 2
    if rsi_oversold:
        buy_score += 2
    if momentum_up:
        buy_score += 1
        
    if trend_bearish:
        sell_score += 2
    if rsi_overbought:
        sell_score += 2
    if momentum_down:
        sell_score += 1
    
    # Determine signal
    if buy_score >= 3:
        return "BUY", min(buy_score * 20, 95)
    elif sell_score >= 3:
        return "SELL", min(sell_score * 20, 95)
    else:
        return "WAIT", max(buy_score, sell_score) * 20

def calc_levels(price, atr, signal):
    if signal == "BUY":
        entry = price
        sl = entry - (atr * 1.0)
        tp1 = entry + (atr * 1.5)
        tp2 = entry + (atr * 2.0)
        tp3 = entry + (atr * 3.0)
        tp4 = entry + (atr * 4.0)
        direction = "LONG"
    else:
        entry = price
        sl = entry + (atr * 1.0)
        tp1 = entry - (atr * 1.5)
        tp2 = entry - (atr * 2.0)
        tp3 = entry - (atr * 3.0)
        tp4 = entry - (atr * 4.0)
        direction = "SHORT"
    
    risk = abs(entry - sl)
    rr1 = abs(tp1 - entry) / risk
    rr2 = abs(tp2 - entry) / risk
    rr3 = abs(tp3 - entry) / risk
    rr4 = abs(tp4 - entry) / risk
    
    return entry, sl, tp1, tp2, tp3, tp4, risk, direction, rr1, rr2, rr3, rr4

def send_telegram(msg):
    if st.session_state.telegram_connected and st.session_state.telegram_chat_id:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": st.session_state.telegram_chat_id, "text": msg, "parse_mode": "HTML"}
            requests.post(url, json=payload, timeout=5)
        except:
            pass

# ============ SIDEBAR ============
with st.sidebar:
    st.markdown("## ⚙️ SETTINGS")
    
    # Telegram
    st.markdown("### 🤖 TELEGRAM")
    if not st.session_state.telegram_connected:
        if st.button("📱 Connect Telegram", use_container_width=True):
            try:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    if data['result']:
                        chat_id = data['result'][0]['message']['chat']['id']
                        st.session_state.telegram_chat_id = chat_id
                        st.session_state.telegram_connected = True
                        send_telegram("✅ Dashboard Connected!")
                        st.success("Connected!")
                        st.rerun()
                    else:
                        st.warning("Send any message to @BOACUTING first!")
                else:
                    st.error("Connection failed")
            except:
                st.error("Error connecting")
    else:
        st.success("✅ Telegram Connected")
        if st.button("Disconnect", use_container_width=True):
            st.session_state.telegram_connected = False
            st.session_state.telegram_chat_id = None
            st.rerun()
    
    st.markdown("---")
    
    # Trading Settings
    st.markdown("### 💰 RISK MANAGEMENT")
    account_balance = st.number_input("Account Balance ($)", value=10000, step=1000)
    risk_percent = st.slider("Risk per Trade (%)", 0.5, 3.0, 1.0)
    
    st.markdown("---")
    st.markdown("### 📊 STATUS")
    st.info("✅ Live Data Active\n✅ AI Ready\n✅ Auto Signals ON")

# ============ MAIN CONTENT ============
with st.spinner("Loading market data..."):
    df = get_data()
    current_price = get_price()
    
    if df is not None and len(df) > 30:
        df = calc_indicators(df)
        current_price = current_price if current_price else float(df['close'].iloc[-1])
        atr = float(df['atr'].iloc[-1]) if not pd.isna(df['atr'].iloc[-1]) else current_price * 0.005
        rsi = float(df['rsi'].iloc[-1]) if not pd.isna(df['rsi'].iloc[-1]) else 50
        
        # Get Signal
        signal, confidence = get_signal_simple(df)
        
        # === BIG PRICE DISPLAY ===
        st.markdown(f'<div style="text-align: center;"><span class="big-price">${current_price:,.2f}</span></div>', unsafe_allow_html=True)
        
        # === SIGNAL BOX ===
        if signal == "BUY":
            st.markdown(f"""
            <div class="signal-box signal-buy">
                <div class="signal-text green-text">📈 BUY (LONG)</div>
                <div style="font-size: 1.2rem; margin-top: 10px;">Confidence: {confidence}%</div>
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width: {confidence}%;"></div>
                </div>
                <div style="margin-top: 10px;">🎯 Price expected to GO UP</div>
            </div>
            """, unsafe_allow_html=True)
            entry, sl, tp1, tp2, tp3, tp4, risk, direction, rr1, rr2, rr3, rr4 = calc_levels(current_price, atr, "BUY")
            
        elif signal == "SELL":
            st.markdown(f"""
            <div class="signal-box signal-sell">
                <div class="signal-text red-text">📉 SELL (SHORT)</div>
                <div style="font-size: 1.2rem; margin-top: 10px;">Confidence: {confidence}%</div>
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width: {confidence}%;"></div>
                </div>
                <div style="margin-top: 10px;">🎯 Price expected to GO DOWN</div>
            </div>
            """, unsafe_allow_html=True)
            entry, sl, tp1, tp2, tp3, tp4, risk, direction, rr1, rr2, rr3, rr4 = calc_levels(current_price, atr, "SELL")
        else:
            st.markdown(f"""
            <div class="signal-box signal-wait">
                <div class="signal-text gold-text">⏸️ WAIT</div>
                <div style="font-size: 1.2rem; margin-top: 10px;">Confidence: {confidence}%</div>
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width: {confidence}%;"></div>
                </div>
                <div style="margin-top: 10px;">⏳ No clear signal - Keep watching</div>
            </div>
            """, unsafe_allow_html=True)
            entry, sl, tp1, tp2, tp3, tp4, risk, direction, rr1, rr2, rr3, rr4 = calc_levels(current_price, atr, "WAIT")
        
        # === METRICS ROW ===
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div style="font-size: 0.8rem; color: #888;">RSI (14)</div>
                <div style="font-size: 1.8rem; font-weight: bold; color: {'#00ff88' if rsi < 35 else '#ff4444' if rsi > 65 else '#ffd700'}">{rsi:.1f}</div>
                <div style="font-size: 0.7rem;">{'🟢 Oversold' if rsi < 35 else '🔴 Overbought' if rsi > 65 else '⚪ Neutral'}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div style="font-size: 0.8rem; color: #888;">ATR (Volatility)</div>
                <div style="font-size: 1.8rem; font-weight: bold; color: #ffd700;">${atr:.2f}</div>
                <div style="font-size: 0.7rem;">Risk per trade: ${risk:.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            position_size = (account_balance * (risk_percent / 100)) / risk if risk > 0 else 0
            st.markdown(f"""
            <div class="metric-card">
                <div style="font-size: 0.8rem; color: #888;">Position Size</div>
                <div style="font-size: 1.8rem; font-weight: bold; color: #ffd700;">{position_size:.4f}</div>
                <div style="font-size: 0.7rem;">Risk: ${account_balance * (risk_percent / 100):.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div class="metric-card">
                <div style="font-size: 0.8rem; color: #888;">Trend</div>
                <div style="font-size: 1.8rem; font-weight: bold; color: {'#00ff88' if df['close'].iloc[-1] > df['sma20'].iloc[-1] else '#ff4444'}">
                    {'📈 BULLISH' if df['close'].iloc[-1] > df['sma20'].iloc[-1] else '📉 BEARISH'}
                </div>
                <div style="font-size: 0.7rem;">SMA20: ${df['sma20'].iloc[-1]:.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # === TRADING LEVELS (CLEAR & SIMPLE) ===
        st.markdown("---")
        st.markdown("## 🎯 TRADING LEVELS")
        st.markdown("*Copy these numbers to your broker*")
        
        level_cols = st.columns(6)
        
        with level_cols[0]:
            st.markdown(f"""
            <div class="level-card">
                <div class="level-label">📍 ENTRY</div>
                <div class="level-price">${entry:.2f}</div>
                <div class="level-pnl green-text">Place order here</div>
            </div>
            """, unsafe_allow_html=True)
        
        with level_cols[1]:
            st.markdown(f"""
            <div class="level-card">
                <div class="level-label">🛑 STOP LOSS</div>
                <div class="level-price">${sl:.2f}</div>
                <div class="level-pnl red-text">Risk: ${risk:.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with level_cols[2]:
            st.markdown(f"""
            <div class="level-card">
                <div class="level-label">🎯 TP1 (1.5R)</div>
                <div class="level-price">${tp1:.2f}</div>
                <div class="level-pnl green-text">+${abs(tp1-entry):.2f} (1:{rr1:.0f})</div>
            </div>
            """, unsafe_allow_html=True)
        
        with level_cols[3]:
            st.markdown(f"""
            <div class="level-card">
                <div class="level-label">🎯 TP2 (2R)</div>
                <div class="level-price">${tp2:.2f}</div>
                <div class="level-pnl green-text">+${abs(tp2-entry):.2f} (1:{rr2:.0f})</div>
            </div>
            """, unsafe_allow_html=True)
        
        with level_cols[4]:
            st.markdown(f"""
            <div class="level-card">
                <div class="level-label">🎯 TP3 (3R)</div>
                <div class="level-price">${tp3:.2f}</div>
                <div class="level-pnl green-text">+${abs(tp3-entry):.2f} (1:{rr3:.0f})</div>
            </div>
            """, unsafe_allow_html=True)
        
        with level_cols[5]:
            st.markdown(f"""
            <div class="level-card">
                <div class="level-label">🎯 TP4 (4R)</div>
                <div class="level-price">${tp4:.2f}</div>
                <div class="level-pnl green-text">+${abs(tp4-entry):.2f} (1:{rr4:.0f})</div>
            </div>
            """, unsafe_allow_html=True)
        
        # === SIMPLE INSTRUCTIONS ===
        st.markdown("---")
        st.markdown("## 📋 HOW TO TRADE (Simple Steps)")
        
        if signal == "BUY":
            st.markdown(f"""
            <div class="instruction-box">
                <b>✅ STEP 1:</b> OPEN a <span class="green-text">BUY (LONG)</span> position at <b>${entry:.2f}</b><br>
                <b>✅ STEP 2:</b> Set STOP LOSS at <b>${sl:.2f}</b><br>
                <b>✅ STEP 3:</b> Take profit at TP1: <b>${tp1:.2f}</b>, TP2: <b>${tp2:.2f}</b>, TP3: <b>${tp3:.2f}</b>, TP4: <b>${tp4:.2f}</b><br>
                <b>✅ STEP 4:</b> Risk ${risk:.2f} to make ${abs(tp2-entry):.2f} (1:2 Risk/Reward)<br>
                <b>🎯 TARGET:</b> Price expected to go <span class="green-text">UP</span>
            </div>
            """, unsafe_allow_html=True)
        elif signal == "SELL":
            st.markdown(f"""
            <div class="instruction-box">
                <b>✅ STEP 1:</b> OPEN a <span class="red-text">SELL (SHORT)</span> position at <b>${entry:.2f}</b><br>
                <b>✅ STEP 2:</b> Set STOP LOSS at <b>${sl:.2f}</b><br>
                <b>✅ STEP 3:</b> Take profit at TP1: <b>${tp1:.2f}</b>, TP2: <b>${tp2:.2f}</b>, TP3: <b>${tp3:.2f}</b>, TP4: <b>${tp4:.2f}</b><br>
                <b>✅ STEP 4:</b> Risk ${risk:.2f} to make ${abs(tp2-entry):.2f} (1:2 Risk/Reward)<br>
                <b>🎯 TARGET:</b> Price expected to go <span class="red-text">DOWN</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="instruction-box">
                <b>⏸️ NO CLEAR SIGNAL</b><br>
                Current price: <b>${current_price:.2f}</b><br>
                RSI: <b>{rsi:.1f}</b> | ATR: <b>${atr:.2f}</b><br><br>
                <i>Wait for a BUY or SELL signal before trading.</i>
            </div>
            """, unsafe_allow_html=True)
        
        # === CHART ===
        st.markdown("---")
        st.markdown("## 📈 LIVE CHART")
        
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df.index.tail(100),
            open=df['open'].tail(100),
            high=df['high'].tail(100),
            low=df['low'].tail(100),
            close=df['close'].tail(100),
            name='XAUUSD',
            increasing_line_color='#00ff88',
            decreasing_line_color='#ff4444'
        ))
        
        # Add levels to chart
        fig.add_hline(y=entry, line_color="#ffd700", line_width=2, annotation_text="ENTRY", annotation_position="right")
        fig.add_hline(y=sl, line_color="#ff4444", line_dash="dash", annotation_text="SL", annotation_position="right")
        fig.add_hline(y=tp1, line_color="#00ff88", line_dash="dot", annotation_text="TP1", annotation_position="right")
        fig.add_hline(y=tp2, line_color="#00cc66", line_dash="dot", annotation_text="TP2", annotation_position="right")
        fig.add_hline(y=tp3, line_color="#009944", line_dash="dot", annotation_text="TP3", annotation_position="right")
        fig.add_hline(y=tp4, line_color="#006622", line_dash="dot", annotation_text="TP4", annotation_position="right")
        
        fig.update_layout(
            template='plotly_dark',
            height=500,
            title="XAUUSD - 1 Hour Chart",
            yaxis_title="Price (USD)",
            xaxis_title="Time"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # === ACTION BUTTONS ===
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("✅ RECORD THIS TRADE", type="primary", use_container_width=True):
                st.session_state.trade_history.append({
                    'time': datetime.now(),
                    'signal': signal,
                    'entry': entry,
                    'sl': sl,
                    'tp2': tp2,
                    'confidence': confidence
                })
                st.success(f"Trade recorded at ${entry:.2f}")
                st.balloons()
                
                if st.session_state.telegram_connected:
                    msg = f"""
🏆 *TRADE SIGNAL*

Signal: {signal}
Entry: ${entry:.2f}
SL: ${sl:.2f}
TP1: ${tp1:.2f}
TP2: ${tp2:.2f}
TP3: ${tp3:.2f}
TP4: ${tp4:.2f}
Confidence: {confidence}%

Risk: ${risk:.2f}
Reward: ${abs(tp2-entry):.2f}
R:R: 1:{abs(tp2-entry)/risk:.0f}
"""
                    send_telegram(msg)
                    st.info("Signal sent to Telegram!")
        
        with col2:
            if st.button("📋 COPY TRADE DETAILS", use_container_width=True):
                trade_text = f"""XAUUSD {signal}
Entry: ${entry:.2f}
SL: ${sl:.2f}
TP1: ${tp1:.2f}
TP2: ${tp2:.2f}
TP3: ${tp3:.2f}
TP4: ${tp4:.2f}
Risk: ${risk:.2f}
Size: {position_size:.4f} lots"""
                st.code(trade_text, language="text")
                st.success("Copied! Paste in your broker")
        
        with col3:
            if st.session_state.telegram_connected:
                st.success("✅ Telegram Ready")
            else:
                if st.button("🔗 Connect Telegram First", use_container_width=True):
                    st.info("Click Connect in sidebar")
        
        # === TRADE HISTORY ===
        if st.session_state.trade_history:
            st.markdown("---")
            st.markdown("## 📋 RECENT TRADES")
            for trade in st.session_state.trade_history[-5:]:
                st.info(f"🎯 {trade['time'].strftime('%Y-%m-%d %H:%M:%S')} | {trade['signal']} | Entry: ${trade['entry']:.2f} | TP: ${trade['tp2']:.2f} | Conf: {trade['confidence']}%")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 1rem; color: #666;">
    <p>🏆 Professional XAUUSD Trading Dashboard | Real-Time Data</p>
    <p style="font-size: 0.8rem;">⚠️ EDUCATIONAL PURPOSES ONLY - Not financial advice</p>
</div>
""", unsafe_allow_html=True)
