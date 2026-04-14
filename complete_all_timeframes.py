import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="COMPLETE XAUUSD TRADER", layout="wide", page_icon="🏆")

# Custom CSS
st.markdown("""
<style>
    .main-title { font-size: 2rem; font-weight: bold; background: linear-gradient(90deg, #ffd700, #ff8c00); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; }
    .tf-card { background: #1e1e2e; border-radius: 12px; padding: 0.8rem; text-align: center; margin: 0.2rem; cursor: pointer; border: 1px solid #333; }
    .tf-active { border: 2px solid #ffd700; background: #2a2a3a; }
    .signal-buy { background: linear-gradient(135deg, #0a3a2a, #0a2a1a); border-left: 4px solid #00ff88; }
    .signal-sell { background: linear-gradient(135deg, #3a1a1a, #2a0a0a); border-left: 4px solid #ff4444; }
    .signal-wait { background: #1e1e2e; border-left: 4px solid #ffd700; }
    .meter { background: #333; border-radius: 10px; height: 8px; overflow: hidden; margin: 5px 0; }
    .meter-fill { height: 100%; border-radius: 10px; transition: width 0.5s; }
    .level-card { background: #1e1e2e; border-radius: 10px; padding: 0.5rem; text-align: center; }
    .level-price { font-size: 1.1rem; font-weight: bold; color: #ffd700; }
    .big-price { font-size: 2.5rem; font-weight: bold; color: #ffd700; text-align: center; }
    .metric-card { background: #1e1e2e; border-radius: 10px; padding: 0.5rem; text-align: center; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🏆 COMPLETE XAUUSD TRADING DASHBOARD</div>', unsafe_allow_html=True)

# ============ CONFIGURATION ============
API_KEY = "96871e27b094425f9ea104fa6eb2be64"

# All Timeframes
TIMEFRAMES = {
    "1m": {"api": "1min", "hours": 1/60, "days": 1, "color": "#ff4444", "pred": 4},
    "5m": {"api": "5min", "hours": 5/60, "days": 3, "color": "#ff8844", "pred": 4},
    "15m": {"api": "15min", "hours": 15/60, "days": 7, "color": "#ffcc44", "pred": 4},
    "30m": {"api": "30min", "hours": 30/60, "days": 14, "color": "#ffff44", "pred": 4},
    "1h": {"api": "1h", "hours": 1, "days": 30, "color": "#88ff44", "pred": 4},
    "4h": {"api": "4h", "hours": 4, "days": 60, "color": "#44ff88", "pred": 2},
    "1d": {"api": "1day", "hours": 24, "days": 180, "color": "#44ffff", "pred": 1}
}

# Session State
if 'selected_tf' not in st.session_state:
    st.session_state.selected_tf = "1h"
if 'backtest_results' not in st.session_state:
    st.session_state.backtest_results = None
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []

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
def get_data(tf, days=None):
    try:
        tf_config = TIMEFRAMES[tf]
        days = days if days else tf_config["days"]
        total = min(int((days * 24) / tf_config["hours"]), 500)
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
        st.error(f"Error: {e}")
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

def get_signal_with_power(df):
    """Get signal with power meter (0-100%)"""
    if df is None or len(df) < 30:
        return "WAIT", 0, 0, 0
    
    last = df.iloc[-1]
    
    # Calculate buy power and sell power
    buy_power = 0
    sell_power = 0
    
    # Trend (30% weight)
    if last['close'] > last['sma20']:
        buy_power += 30
    else:
        sell_power += 30
    
    # SMA alignment (20% weight)
    if last['sma20'] > last['sma50']:
        buy_power += 20
    else:
        sell_power += 20
    
    # RSI (25% weight)
    if last['rsi'] < 35:
        buy_power += 25
    elif last['rsi'] > 65:
        sell_power += 25
    elif last['rsi'] < 45:
        buy_power += 10
    elif last['rsi'] > 55:
        sell_power += 10
    
    # Momentum (25% weight)
    if len(df) > 2:
        if last['close'] > df.iloc[-2]['close']:
            buy_power += 25
        else:
            sell_power += 25
    
    # Determine signal
    if buy_power > sell_power and buy_power >= 50:
        return "BUY", buy_power, buy_power, sell_power
    elif sell_power > buy_power and sell_power >= 50:
        return "SELL", sell_power, buy_power, sell_power
    else:
        return "WAIT", max(buy_power, sell_power), buy_power, sell_power

def calc_levels(price, atr, signal):
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
    return entry, sl, tp1, tp2, tp3, tp4, risk

def run_backtest(df, tf, risk_percent=1.0):
    """Simple backtest for timeframe"""
    if df is None or len(df) < 100:
        return None
    
    df = calc_indicators(df)
    trades = []
    balance = 10000
    balance_history = [balance]
    
    for i in range(50, len(df) - 10):
        current_data = df.iloc[:i+1]
        signal, power, bp, sp = get_signal_with_power(current_data)
        
        if signal != "WAIT" and power >= 60:
            current_price = df.iloc[i]['close']
            atr = df.iloc[i]['atr'] if not pd.isna(df.iloc[i]['atr']) else current_price * 0.005
            
            entry, sl, tp1, tp2, tp3, tp4, risk = calc_levels(current_price, atr, signal)
            
            risk_amount = balance * (risk_percent / 100)
            pos_size = risk_amount / risk if risk > 0 else 0
            
            # Check future prices (next 4-8 candles depending on timeframe)
            lookahead = 8 if tf in ["1m", "5m"] else 4
            future_prices = df['close'].iloc[i+1:i+lookahead+1].values
            
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
        return {'trades': len(trades), 'wins': wins, 'win_rate': win_rate, 'total_pnl': total_pnl, 'balance_history': balance_history}
    return None

# ============ SIDEBAR ============
with st.sidebar:
    st.markdown("## ⚙️ CONTROL PANEL")
    
    st.markdown("### 📊 TIMEFRAMES")
    tf_cols = st.columns(4)
    tf_list = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
    for i, tf in enumerate(tf_list):
        col = tf_cols[i % 4]
        with col:
            if st.button(tf, use_container_width=True, type="primary" if st.session_state.selected_tf == tf else "secondary"):
                st.session_state.selected_tf = tf
                st.cache_data.clear()
                st.rerun()
    
    st.markdown("---")
    st.markdown("### 💰 RISK")
    account_balance = st.number_input("Balance ($)", value=10000, step=1000)
    risk_percent = st.slider("Risk %", 0.5, 2.0, 1.0)
    
    st.markdown("---")
    st.markdown("### 📈 BACKTEST")
    backtest_tf = st.selectbox("Backtest Timeframe", ["1h", "4h", "1d"], index=0)
    bt_days = st.selectbox("Period", ["30d", "60d", "90d"], index=1)
    
    if st.button("🚀 RUN BACKTEST", use_container_width=True):
        days = {"30d": 30, "60d": 60, "90d": 90}[bt_days]
        with st.spinner(f"Backtesting {backtest_tf}..."):
            bt_df = get_data(backtest_tf, days)
            result = run_backtest(bt_df, backtest_tf, risk_percent)
            if result:
                st.session_state.backtest_results = result
                st.success(f"Win Rate: {result['win_rate']:.1f}% | P&L: ${result['total_pnl']:.2f}")
            else:
                st.warning("Insufficient data")

# ============ MAIN CONTENT ============
current_tf = st.session_state.selected_tf

with st.spinner(f"Loading {current_tf} data..."):
    df = get_data(current_tf)
    current_price = get_price()
    
    if df is not None and len(df) > 20:
        df = calc_indicators(df)
        current_price = current_price if current_price else float(df['close'].iloc[-1])
        atr = float(df['atr'].iloc[-1]) if not pd.isna(df['atr'].iloc[-1]) else current_price * 0.005
        rsi = float(df['rsi'].iloc[-1]) if not pd.isna(df['rsi'].iloc[-1]) else 50
        
        # Get signal with power meter
        signal, power, buy_power, sell_power = get_signal_with_power(df)
        
        # === BIG PRICE ===
        st.markdown(f'<div class="big-price">XAUUSD: ${current_price:,.2f}</div>', unsafe_allow_html=True)
        
        # === POWER METERS ===
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div style="color: #00ff88;">📈 BUY POWER</div>
                <div style="font-size: 2rem; font-weight: bold;">{buy_power:.0f}%</div>
                <div class="meter"><div class="meter-fill" style="width: {buy_power}%; background: #00ff88;"></div></div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div style="color: #ff4444;">📉 SELL POWER</div>
                <div style="font-size: 2rem; font-weight: bold;">{sell_power:.0f}%</div>
                <div class="meter"><div class="meter-fill" style="width: {sell_power}%; background: #ff4444;"></div></div>
            </div>
            """, unsafe_allow_html=True)
        
        # === SIGNAL BOX ===
        if signal == "BUY":
            st.markdown(f"""
            <div class="signal-buy" style="padding: 1rem; border-radius: 15px; margin: 1rem 0;">
                <div style="font-size: 2rem; font-weight: bold; color: #00ff88;">📈 BUY SIGNAL</div>
                <div>Confidence: {power:.0f}% | Buy Power: {buy_power:.0f}% | Sell Power: {sell_power:.0f}%</div>
                <div class="meter"><div class="meter-fill" style="width: {power}%; background: #00ff88;"></div></div>
                <div>🎯 Price expected to GO UP</div>
            </div>
            """, unsafe_allow_html=True)
            entry, sl, tp1, tp2, tp3, tp4, risk = calc_levels(current_price, atr, "BUY")
            direction = "LONG"
            
        elif signal == "SELL":
            st.markdown(f"""
            <div class="signal-sell" style="padding: 1rem; border-radius: 15px; margin: 1rem 0;">
                <div style="font-size: 2rem; font-weight: bold; color: #ff4444;">📉 SELL SIGNAL</div>
                <div>Confidence: {power:.0f}% | Buy Power: {buy_power:.0f}% | Sell Power: {sell_power:.0f}%</div>
                <div class="meter"><div class="meter-fill" style="width: {power}%; background: #ff4444;"></div></div>
                <div>🎯 Price expected to GO DOWN</div>
            </div>
            """, unsafe_allow_html=True)
            entry, sl, tp1, tp2, tp3, tp4, risk = calc_levels(current_price, atr, "SELL")
            direction = "SHORT"
        else:
            st.markdown(f"""
            <div class="signal-wait" style="padding: 1rem; border-radius: 15px; margin: 1rem 0;">
                <div style="font-size: 2rem; font-weight: bold; color: #ffd700;">⏸️ WAIT</div>
                <div>Buy Power: {buy_power:.0f}% | Sell Power: {sell_power:.0f}%</div>
                <div class="meter"><div class="meter-fill" style="width: {max(buy_power, sell_power)}%; background: #ffd700;"></div></div>
                <div>⏳ No clear signal - Keep watching</div>
            </div>
            """, unsafe_allow_html=True)
            entry, sl, tp1, tp2, tp3, tp4, risk = calc_levels(current_price, atr, "WAIT")
            direction = "NONE"
        
        # === METRICS ROW ===
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div style="color: #888;">TIMEFRAME</div>
                <div style="font-size: 1.5rem; font-weight: bold; color: #ffd700;">{current_tf}</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div style="color: #888;">RSI (14)</div>
                <div style="font-size: 1.5rem; font-weight: bold; color: {'#00ff88' if rsi < 35 else '#ff4444' if rsi > 65 else '#ffd700'}">{rsi:.1f}</div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div style="color: #888;">ATR</div>
                <div style="font-size: 1.5rem; font-weight: bold; color: #ffd700;">${atr:.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        with col4:
            pos_size = (account_balance * (risk_percent / 100)) / risk if risk > 0 else 0
            st.markdown(f"""
            <div class="metric-card">
                <div style="color: #888;">POSITION SIZE</div>
                <div style="font-size: 1.5rem; font-weight: bold; color: #ffd700;">{pos_size:.4f}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # === TRADING LEVELS ===
        st.markdown("---")
        st.markdown("## 🎯 TRADING LEVELS")
        
        level_cols = st.columns(6)
        with level_cols[0]:
            st.markdown(f'<div class="level-card"><div class="level-label">📍 ENTRY</div><div class="level-price">${entry:.2f}</div></div>', unsafe_allow_html=True)
        with level_cols[1]:
            st.markdown(f'<div class="level-card"><div class="level-label">🛑 SL</div><div class="level-price">${sl:.2f}</div></div>', unsafe_allow_html=True)
        with level_cols[2]:
            st.markdown(f'<div class="level-card"><div class="level-label">🎯 TP1</div><div class="level-price">${tp1:.2f}</div></div>', unsafe_allow_html=True)
        with level_cols[3]:
            st.markdown(f'<div class="level-card"><div class="level-label">🎯 TP2</div><div class="level-price">${tp2:.2f}</div></div>', unsafe_allow_html=True)
        with level_cols[4]:
            st.markdown(f'<div class="level-card"><div class="level-label">🎯 TP3</div><div class="level-price">${tp3:.2f}</div></div>', unsafe_allow_html=True)
        with level_cols[5]:
            st.markdown(f'<div class="level-card"><div class="level-label">🎯 TP4</div><div class="level-price">${tp4:.2f}</div></div>', unsafe_allow_html=True)
        
        st.info(f"📊 Risk: ${risk:.2f} | Reward TP2: ${abs(tp2-entry):.2f} | R:R 1:{abs(tp2-entry)/risk:.1f}")
        
        # === ACTION BUTTON ===
        if st.button("✅ RECORD TRADE", type="primary", use_container_width=True):
            st.session_state.trade_history.append({
                'time': datetime.now(),
                'timeframe': current_tf,
                'signal': signal,
                'entry': entry,
                'sl': sl,
                'tp2': tp2,
                'confidence': power
            })
            st.success(f"Trade recorded at ${entry:.2f}")
            st.balloons()
        
        # === CHART ===
        st.markdown("---")
        st.markdown(f"## 📈 {current_tf.upper()} CHART")
        
        # Fix the index.tail error
        chart_df = df.tail(100)
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=chart_df.index,
            open=chart_df['open'],
            high=chart_df['high'],
            low=chart_df['low'],
            close=chart_df['close'],
            name='XAUUSD',
            increasing_line_color='#00ff88',
            decreasing_line_color='#ff4444'
        ))
        
        # Add levels
        fig.add_hline(y=entry, line_color="#ffd700", line_width=2, annotation_text="ENTRY")
        fig.add_hline(y=sl, line_color="#ff4444", line_dash="dash", annotation_text="SL")
        fig.add_hline(y=tp1, line_color="#00ff88", line_dash="dot", annotation_text="TP1")
        fig.add_hline(y=tp2, line_color="#00cc66", line_dash="dot", annotation_text="TP2")
        
        fig.update_layout(template='plotly_dark', height=500, title=f"XAUUSD - {current_tf} Chart")
        st.plotly_chart(fig, use_container_width=True)
        
        # === BACKTEST RESULTS ===
        if st.session_state.backtest_results:
            st.markdown("---")
            st.markdown("## 📊 BACKTEST RESULTS")
            res = st.session_state.backtest_results
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Trades", res['trades'])
            col2.metric("Win Rate", f"{res['win_rate']:.1f}%")
            col3.metric("Wins", res['wins'])
            col4.metric("Total P&L", f"${res['total_pnl']:.2f}")
        
        # === TRADE HISTORY ===
        if st.session_state.trade_history:
            st.markdown("---")
            st.markdown("## 📋 RECENT TRADES")
            for trade in st.session_state.trade_history[-5:]:
                st.info(f"🎯 {trade['time'].strftime('%H:%M:%S')} | {trade['timeframe']} | {trade['signal']} | Entry: ${trade['entry']:.2f} | TP: ${trade['tp2']:.2f} | Conf: {trade['confidence']:.0f}%")

# Footer
st.markdown("---")
st.caption("⚠️ EDUCATIONAL ONLY - Not financial advice")
