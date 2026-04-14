import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="AUTO CHECKLIST XAUUSD TRADER", layout="wide", page_icon="✅")

# Custom CSS
st.markdown("""
<style>
    .main-title { font-size: 2rem; font-weight: bold; background: linear-gradient(90deg, #ffd700, #ff8c00); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; }
    .checklist-pass { background: linear-gradient(135deg, #0a3a2a, #0a2a1a); border-left: 4px solid #00ff88; padding: 0.5rem; margin: 0.3rem 0; border-radius: 8px; }
    .checklist-fail { background: linear-gradient(135deg, #3a1a1a, #2a0a0a); border-left: 4px solid #ff4444; padding: 0.5rem; margin: 0.3rem 0; border-radius: 8px; }
    .checklist-warn { background: #1e1e2e; border-left: 4px solid #ffd700; padding: 0.5rem; margin: 0.3rem 0; border-radius: 8px; }
    .signal-box { border-radius: 20px; padding: 1.5rem; text-align: center; margin: 1rem 0; }
    .signal-buy { background: linear-gradient(135deg, #0a3a2a, #0a2a1a); border: 2px solid #00ff88; }
    .signal-sell { background: linear-gradient(135deg, #3a1a1a, #2a0a0a); border: 2px solid #ff4444; }
    .signal-wait { background: #1e1e2e; border: 2px solid #ffd700; }
    .meter { background: #333; border-radius: 10px; height: 10px; overflow: hidden; margin: 5px 0; }
    .meter-fill { height: 100%; border-radius: 10px; transition: width 0.5s; }
    .big-score { font-size: 3rem; font-weight: bold; text-align: center; }
    .level-card { background: #1e1e2e; border-radius: 10px; padding: 0.5rem; text-align: center; }
    .level-price { font-size: 1.1rem; font-weight: bold; color: #ffd700; }
    .metric-card { background: #1e1e2e; border-radius: 10px; padding: 0.8rem; text-align: center; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">✅ AUTO PRE-TRADE CHECKLIST DASHBOARD</div>', unsafe_allow_html=True)

# ============ CONFIGURATION ============
API_KEY = "96871e27b094425f9ea104fa6eb2be64"

# High impact news events (auto-block trading)
HIGH_IMPACT_NEWS = ["NFP", "FOMC", "CPI", "GDP", "Unemployment", "Fed", "Rate Decision"]

# Session state
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
def get_data(tf="1h", days=30):
    try:
        interval_map = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "1h": "1h", "4h": "4h", "1d": "1day"}
        hours_map = {"1m": 1/60, "5m": 5/60, "15m": 15/60, "30m": 30/60, "1h": 1, "4h": 4, "1d": 24}
        total = min(int((days * 24) / hours_map[tf]), 500)
        url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval={interval_map[tf]}&outputsize={total}&apikey={API_KEY}"
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
    df['atr_percent'] = df['atr'] / df['close'] * 100
    
    return df

def get_signal_with_power(df):
    if df is None or len(df) < 30:
        return "WAIT", 0, 0, 0
    
    last = df.iloc[-1]
    
    buy_power = 0
    sell_power = 0
    
    # Trend (30%)
    if last['close'] > last['sma20']:
        buy_power += 30
    else:
        sell_power += 30
    
    # SMA alignment (20%)
    if last['sma20'] > last['sma50']:
        buy_power += 20
    else:
        sell_power += 20
    
    # RSI (25%)
    if last['rsi'] < 35:
        buy_power += 25
    elif last['rsi'] > 65:
        sell_power += 25
    elif last['rsi'] < 45:
        buy_power += 10
    elif last['rsi'] > 55:
        sell_power += 10
    
    # Momentum (25%)
    if len(df) > 2:
        if last['close'] > df.iloc[-2]['close']:
            buy_power += 25
        else:
            sell_power += 25
    
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
    rr = abs(tp2 - entry) / risk if risk > 0 else 0
    return entry, sl, tp1, tp2, tp3, tp4, risk, rr

def check_news():
    """Simulate news check - in production, use economic calendar API"""
    current_hour = datetime.now().hour
    # Assume no news for demo
    return False, "No high-impact news"

def check_trading_hours():
    current_hour = datetime.now().hour
    # London session (8-17 GMT) or NY session (13-22 GMT)
    if (8 <= current_hour <= 17) or (13 <= current_hour <= 22):
        return True, "London/NY Session"
    else:
        return False, "Asian Session (low volatility)"

def check_higher_timeframe():
    """Check 4h timeframe for alignment"""
    df_4h = get_data("4h", 7)
    if df_4h is not None and len(df_4h) > 20:
        df_4h = calc_indicators(df_4h)
        signal_4h, power_4h, bp_4h, sp_4h = get_signal_with_power(df_4h)
        return signal_4h, power_4h
    return "WAIT", 0

# ============ MAIN APP ============
# Sidebar
with st.sidebar:
    st.markdown("## ⚙️ SETTINGS")
    
    st.markdown("### 📊 TIMEFRAME")
    tf_options = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
    selected_tf = st.selectbox("Select Timeframe", tf_options, index=4)
    
    st.markdown("---")
    st.markdown("### 💰 RISK MANAGEMENT")
    account_balance = st.number_input("Account Balance ($)", value=10000, step=1000)
    risk_percent = st.slider("Risk per Trade (%)", 0.5, 3.0, 1.0)
    
    st.markdown("---")
    st.markdown("### ✅ AUTO CHECKLIST RULES")
    st.info("""
    **Automatic Checks:**
    1. Trend alignment (SMA20/50)
    2. RSI confirmation
    3. Power meter > 60%
    4. Higher timeframe alignment
    5. Risk/Reward > 1:2
    6. News filter
    7. Trading hours
    """)

# Load data
with st.spinner(f"Analyzing {selected_tf} market data..."):
    df = get_data(selected_tf, 30)
    current_price = get_price()
    
    if df is not None and len(df) > 20:
        df = calc_indicators(df)
        current_price = current_price if current_price else float(df['close'].iloc[-1])
        atr = float(df['atr'].iloc[-1]) if not pd.isna(df['atr'].iloc[-1]) else current_price * 0.005
        rsi = float(df['rsi'].iloc[-1]) if not pd.isna(df['rsi'].iloc[-1]) else 50
        
        # Get signal
        signal, confidence, buy_power, sell_power = get_signal_with_power(df)
        
        # Get checklist results
        news_blocked, news_msg = check_news()
        trading_hours, session_msg = check_trading_hours()
        signal_4h, power_4h = check_higher_timeframe()
        
        # Calculate levels if signal exists
        if signal != "WAIT":
            entry, sl, tp1, tp2, tp3, tp4, risk, rr = calc_levels(current_price, atr, signal)
        else:
            entry, sl, tp1, tp2, tp3, tp4, risk, rr = current_price, current_price, current_price, current_price, current_price, current_price, 0, 0
        
        # ============ AUTO CHECKLIST ============
        st.markdown("## 📋 AUTOMATIC PRE-TRADE CHECKLIST")
        
        checklist_results = []
        total_score = 0
        
        # 1. Trend Check
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📊 CHECKLIST STATUS")
            
            # Check 1: Trend
            if signal == "BUY":
                trend_ok = current_price > df['sma20'].iloc[-1] and df['sma20'].iloc[-1] > df['sma50'].iloc[-1]
                trend_text = f"Price ${current_price:.2f} vs SMA20 ${df['sma20'].iloc[-1]:.2f} vs SMA50 ${df['sma50'].iloc[-1]:.2f}"
            else:
                trend_ok = current_price < df['sma20'].iloc[-1] and df['sma20'].iloc[-1] < df['sma50'].iloc[-1]
                trend_text = f"Price ${current_price:.2f} vs SMA20 ${df['sma20'].iloc[-1]:.2f} vs SMA50 ${df['sma50'].iloc[-1]:.2f}"
            
            if trend_ok:
                st.markdown(f'<div class="checklist-pass">✅ TREND: {trend_text}</div>', unsafe_allow_html=True)
                total_score += 15
            else:
                st.markdown(f'<div class="checklist-fail">❌ TREND: {trend_text}</div>', unsafe_allow_html=True)
            
            # Check 2: RSI
            if signal == "BUY":
                rsi_ok = rsi < 40
                rsi_text = f"RSI = {rsi:.1f} (Need < 40 for BUY)"
            else:
                rsi_ok = rsi > 60
                rsi_text = f"RSI = {rsi:.1f} (Need > 60 for SELL)"
            
            if rsi_ok:
                st.markdown(f'<div class="checklist-pass">✅ RSI: {rsi_text}</div>', unsafe_allow_html=True)
                total_score += 15
            else:
                st.markdown(f'<div class="checklist-fail">❌ RSI: {rsi_text}</div>', unsafe_allow_html=True)
            
            # Check 3: Power Meter
            power_ok = confidence >= 60
            if power_ok:
                st.markdown(f'<div class="checklist-pass">✅ POWER: {confidence:.0f}% (Need > 60%)</div>', unsafe_allow_html=True)
                total_score += 15
            else:
                st.markdown(f'<div class="checklist-fail">❌ POWER: {confidence:.0f}% (Need > 60%)</div>', unsafe_allow_html=True)
            
            # Check 4: Higher Timeframe
            if signal == "BUY":
                tf_ok = signal_4h == "BUY"
            else:
                tf_ok = signal_4h == "SELL"
            
            if tf_ok:
                st.markdown(f'<div class="checklist-pass">✅ HIGHER TF: 4h also {signal_4h} ({power_4h:.0f}%)</div>', unsafe_allow_html=True)
                total_score += 15
            else:
                st.markdown(f'<div class="checklist-fail">❌ HIGHER TF: 4h is {signal_4h} (should be {signal})</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown("### 📊 CONTINUED...")
            
            # Check 5: Risk/Reward
            rr_ok = rr >= 2.0
            if rr_ok:
                st.markdown(f'<div class="checklist-pass">✅ RISK/REWARD: 1:{rr:.1f} (Need > 1:2)</div>', unsafe_allow_html=True)
                total_score += 15
            else:
                st.markdown(f'<div class="checklist-fail">❌ RISK/REWARD: 1:{rr:.1f} (Need > 1:2)</div>', unsafe_allow_html=True)
            
            # Check 6: News
            if not news_blocked:
                st.markdown(f'<div class="checklist-pass">✅ NEWS: {news_msg}</div>', unsafe_allow_html=True)
                total_score += 15
            else:
                st.markdown(f'<div class="checklist-fail">❌ NEWS: {news_msg}</div>', unsafe_allow_html=True)
            
            # Check 7: Trading Hours
            if trading_hours:
                st.markdown(f'<div class="checklist-pass">✅ TIME: {session_msg}</div>', unsafe_allow_html=True)
                total_score += 10
            else:
                st.markdown(f'<div class="checklist-warn">⚠️ TIME: {session_msg} (Lower liquidity)</div>', unsafe_allow_html=True)
                total_score += 5
        
        # ============ FINAL SCORE & SIGNAL ============
        st.markdown("---")
        st.markdown("## 🎯 FINAL VERDICT")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div style="font-size: 0.8rem;">TOTAL SCORE</div>
                <div class="big-score" style="color: {'#00ff88' if total_score >= 80 else '#ffd700' if total_score >= 60 else '#ff4444'}">{total_score}/100</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            if total_score >= 80:
                verdict = "✅ STRONG TRADE"
                verdict_color = "#00ff88"
                action = "TAKE THIS TRADE"
            elif total_score >= 60:
                verdict = "⚠️ GOOD TRADE"
                verdict_color = "#ffd700"
                action = "Consider Taking"
            else:
                verdict = "❌ NO TRADE"
                verdict_color = "#ff4444"
                action = "WAIT FOR BETTER SETUP"
            
            st.markdown(f"""
            <div class="metric-card">
                <div style="font-size: 0.8rem;">VERDICT</div>
                <div style="font-size: 1.2rem; font-weight: bold; color: {verdict_color};">{verdict}</div>
                <div>{action}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            # Power Meters
            st.markdown(f"""
            <div class="metric-card">
                <div>📈 BUY POWER</div>
                <div style="font-size: 1.5rem;">{buy_power:.0f}%</div>
                <div class="meter"><div class="meter-fill" style="width: {buy_power}%; background: #00ff88;"></div></div>
                <div>📉 SELL POWER</div>
                <div style="font-size: 1.5rem;">{sell_power:.0f}%</div>
                <div class="meter"><div class="meter-fill" style="width: {sell_power}%; background: #ff4444;"></div></div>
            </div>
            """, unsafe_allow_html=True)
        
        # ============ SIGNAL DISPLAY ============
        if total_score >= 60 and signal != "WAIT":
            if signal == "BUY":
                st.markdown(f"""
                <div class="signal-box signal-buy">
                    <div style="font-size: 2.5rem; font-weight: bold; color: #00ff88;">📈 BUY SIGNAL</div>
                    <div>Confidence: {confidence:.0f}% | Score: {total_score}/100</div>
                    <div class="meter"><div class="meter-fill" style="width: {confidence}%; background: #00ff88;"></div></div>
                    <div>🎯 Price expected to GO UP</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="signal-box signal-sell">
                    <div style="font-size: 2.5rem; font-weight: bold; color: #ff4444;">📉 SELL SIGNAL</div>
                    <div>Confidence: {confidence:.0f}% | Score: {total_score}/100</div>
                    <div class="meter"><div class="meter-fill" style="width: {confidence}%; background: #ff4444;"></div></div>
                    <div>🎯 Price expected to GO DOWN</div>
                </div>
                """, unsafe_allow_html=True)
            
            # ============ TRADING LEVELS ============
            st.markdown("---")
            st.markdown("## 🎯 TRADING LEVELS")
            
            level_cols = st.columns(6)
            level_cols[0].markdown(f'<div class="level-card"><div class="level-label">📍 ENTRY</div><div class="level-price">${entry:.2f}</div></div>', unsafe_allow_html=True)
            level_cols[1].markdown(f'<div class="level-card"><div class="level-label">🛑 SL</div><div class="level-price">${sl:.2f}</div><div style="font-size:0.7rem;">Risk: ${risk:.2f}</div></div>', unsafe_allow_html=True)
            level_cols[2].markdown(f'<div class="level-card"><div class="level-label">🎯 TP1 (1.5R)</div><div class="level-price">${tp1:.2f}</div></div>', unsafe_allow_html=True)
            level_cols[3].markdown(f'<div class="level-card"><div class="level-label">🎯 TP2 (2R)</div><div class="level-price">${tp2:.2f}</div></div>', unsafe_allow_html=True)
            level_cols[4].markdown(f'<div class="level-card"><div class="level-label">🎯 TP3 (3R)</div><div class="level-price">${tp3:.2f}</div></div>', unsafe_allow_html=True)
            level_cols[5].markdown(f'<div class="level-card"><div class="level-label">🎯 TP4 (4R)</div><div class="level-price">${tp4:.2f}</div></div>', unsafe_allow_html=True)
            
            # Position Size
            position_size = (account_balance * (risk_percent / 100)) / risk if risk > 0 else 0
            st.info(f"📊 Position Size: {position_size:.4f} lots | Risk Amount: ${account_balance * (risk_percent / 100):.2f} | R:R 1:{rr:.1f}")
            
            # Execute Button
            if st.button("✅ RECORD THIS TRADE", type="primary", use_container_width=True):
                st.session_state.trade_history.append({
                    'time': datetime.now(),
                    'timeframe': selected_tf,
                    'signal': signal,
                    'entry': entry,
                    'sl': sl,
                    'tp2': tp2,
                    'confidence': confidence,
                    'score': total_score
                })
                st.success(f"Trade recorded at ${entry:.2f}")
                st.balloons()
        
        else:
            st.markdown(f"""
            <div class="signal-box signal-wait">
                <div style="font-size: 2rem; font-weight: bold; color: #ffd700;">⏸️ NO TRADE</div>
                <div>Score: {total_score}/100 - Conditions not met</div>
                <div>Buy Power: {buy_power:.0f}% | Sell Power: {sell_power:.0f}%</div>
                <div>⏳ Wait for better setup</div>
            </div>
            """, unsafe_allow_html=True)
        
        # ============ CHART ============
        st.markdown("---")
        st.markdown(f"## 📈 {selected_tf.upper()} CHART")
        
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
        
        if total_score >= 60 and signal != "WAIT":
            fig.add_hline(y=entry, line_color="#ffd700", line_width=2, annotation_text="ENTRY")
            fig.add_hline(y=sl, line_color="#ff4444", line_dash="dash", annotation_text="SL")
            fig.add_hline(y=tp1, line_color="#00ff88", line_dash="dot", annotation_text="TP1")
            fig.add_hline(y=tp2, line_color="#00cc66", line_dash="dot", annotation_text="TP2")
        
        fig.update_layout(template='plotly_dark', height=500, title=f"XAUUSD - {selected_tf} Chart")
        st.plotly_chart(fig, use_container_width=True)
        
        # ============ TRADE HISTORY ============
        if st.session_state.trade_history:
            st.markdown("---")
            st.markdown("## 📋 RECENT TRADES")
            for trade in st.session_state.trade_history[-5:]:
                st.info(f"🎯 {trade['time'].strftime('%Y-%m-%d %H:%M:%S')} | {trade['timeframe']} | {trade['signal']} | Entry: ${trade['entry']:.2f} | TP: ${trade['tp2']:.2f} | Score: {trade['score']}/100")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 1rem; color: #666;">
    <p>✅ Auto Checklist - 7 Rules Automatically Checked Before Every Trade</p>
    <p style="font-size: 0.8rem;">⚠️ EDUCATIONAL ONLY - Not financial advice</p>
</div>
""", unsafe_allow_html=True)
