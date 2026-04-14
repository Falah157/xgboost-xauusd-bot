import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="EXNESS AI TRADING", layout="wide", page_icon="💰")

st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: bold;
        background: linear-gradient(90deg, #00ff88, #ffd700);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 1rem;
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
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">💰 EXNESS AI TRADING SIGNALS (Mac Compatible)</div>', unsafe_allow_html=True)

API_KEY = "96871e27b094425f9ea104fa6eb2be64"

# Session state
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []

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

@st.cache_data(ttl=300)
def get_historical_data(period="3mo", interval="1h"):
    try:
        days_map = {"1w": 7, "1mo": 30, "3mo": 90, "6mo": 180}
        days = days_map.get(period, 90)
        total_candles = min(days * 24, 2000)
        
        url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval={interval}&outputsize={total_candles}&apikey={API_KEY}"
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
        st.error(f"Data error: {e}")
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
    if len(df_clean) < 100:
        return None, None, None
    
    df_clean['Target'] = (df_clean['Close'].shift(-prediction_bars) > df_clean['Close']).astype(int)
    df_clean = df_clean.dropna()
    
    X = df_clean[features].values
    y = df_clean['Target'].values
    
    split = int(len(X) * 0.8)
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    
    model = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42)
    model.fit(X_train_scaled, y_train)
    accuracy = model.score(X_val_scaled, y_val)
    
    return model, scaler, accuracy

def get_signal(model, scaler, features):
    if model is None:
        return None, 0
    features_scaled = scaler.transform(features)
    prob = model.predict_proba(features_scaled)[0]
    pred = 1 if prob[1] > 0.55 else 0
    confidence = max(prob)
    return pred, confidence

def calculate_levels(price, atr, direction):
    if direction == "LONG":
        sl = price - (atr * 1.0)
        tp1 = price + (atr * 1.5)
        tp2 = price + (atr * 2.0)
        tp3 = price + (atr * 3.0)
        tp4 = price + (atr * 4.0)
    else:
        sl = price + (atr * 1.0)
        tp1 = price - (atr * 1.5)
        tp2 = price - (atr * 2.0)
        tp3 = price - (atr * 3.0)
        tp4 = price - (atr * 4.0)
    
    risk = abs(price - sl)
    return sl, tp1, tp2, tp3, tp4, risk

# Sidebar
with st.sidebar:
    st.header("⚙️ SETTINGS")
    selected_timeframe = st.selectbox("Timeframe", ["1h", "4h"], index=0)
    account_balance = st.number_input("Account Balance ($)", value=10000, step=1000)
    risk_percent = st.slider("Risk per Trade (%)", 0.5, 2.0, 1.0)
    min_confidence = st.slider("Min Confidence (%)", 50, 80, 60) / 100
    
    st.markdown("---")
    st.info("""
    📝 **HOW TO TRADE MANUALLY:**
    1. Copy the Entry, SL, TP values below
    2. Open Exness WebTerminal
    3. Place trade manually
    4. Track in Trade History tab
    """)
    
    st.markdown("---")
    st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

# Main content
tab1, tab2, tab3 = st.tabs(["🎯 LIVE SIGNALS", "📊 BACKTEST", "📜 TRADE HISTORY"])

with tab1:
    st.header("🎯 LIVE AI SIGNALS")
    
    with st.spinner("Loading market data..."):
        df = get_historical_data(period="3mo", interval=selected_timeframe)
        if df is not None and len(df) > 50:
            df = calculate_indicators(df)
            model, scaler, accuracy = train_model(df, 4)
            current_price = get_realtime_price()
            if current_price is None:
                current_price = float(df['Close'].iloc[-1])
            atr = float(df['ATR'].iloc[-1])
            rsi = float(df['RSI'].iloc[-1])
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("XAUUSD", f"${current_price:.2f}")
            col2.metric("ATR", f"${atr:.2f}")
            col3.metric("RSI", f"{rsi:.1f}")
            col4.metric("AI Accuracy", f"{accuracy:.1%}")
            
            features = ['RSI', 'MACD_Hist', 'ATR', 'SMA_20', 'SMA_50']
            latest_features = df[features].iloc[-1:].values
            prediction, confidence = get_signal(model, scaler, latest_features)
            
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
                sl, tp1, tp2, tp3, tp4, risk = calculate_levels(current_price, atr, direction)
                position_size = (account_balance * (risk_percent / 100)) / risk
                
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
                
                # Copy to clipboard section
                st.markdown("---")
                st.subheader("📋 COPY TO EXNESS WEBTERMINAL")
                
                trade_details = f"""
                ===== MANUAL TRADE ORDER =====
                Symbol: XAUUSD
                Direction: {direction}
                Entry Price: ${current_price:.2f}
                Stop Loss: ${sl:.2f}
                Take Profit: ${tp2:.2f}
                Volume: {position_size:.4f} lots
                ===============================
                """
                
                st.code(trade_details, language="text")
                
                st.info("📌 1. Open https://terminal.exness.com\n📌 2. Login to your account\n📌 3. Place a new order with above values")
                
                # Record trade button
                if st.button("✅ RECORD THIS TRADE", type="primary"):
                    st.session_state.trade_history.append({
                        'time': datetime.now(),
                        'direction': direction,
                        'entry': current_price,
                        'sl': sl,
                        'tp': tp2,
                        'size': position_size,
                        'status': 'RECORDED'
                    })
                    st.success("Trade recorded in history!")
                    st.balloons()
                
                # Chart
                st.markdown("---")
                st.subheader("📈 CHART")
                recent_df = df.tail(100)
                fig = make_subplots(rows=2, cols=1, row_heights=[0.7, 0.3], shared_xaxes=True)
                
                fig.add_trace(go.Candlestick(
                    x=recent_df.index, open=recent_df['Open'], high=recent_df['High'],
                    low=recent_df['Low'], close=recent_df['Close'], name='XAUUSD'
                ), row=1, col=1)
                
                for name, price, color in [('Entry', current_price, '#ffd700'), ('SL', sl, '#ff4444'),
                    ('TP1', tp1, '#00ff88'), ('TP2', tp2, '#00cc66'), ('TP3', tp3, '#009944'), ('TP4', tp4, '#006622')]:
                    fig.add_hline(y=price, line_dash="dash" if name == 'SL' else "solid", line_color=color, annotation_text=name, row=1, col=1)
                
                fig.add_trace(go.Scatter(x=recent_df.index, y=recent_df['RSI'], name='RSI', line=dict(color='#9b59b6')), row=2, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
                
                fig.update_layout(template='plotly_dark', height=700, showlegend=True)
                st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header("📊 BACKTEST")
    
    col1, col2 = st.columns(2)
    with col1:
        backtest_period = st.selectbox("Period", ["1w", "1mo", "3mo", "6mo"], index=2)
    with col2:
        bt_risk = st.slider("Risk %", 0.5, 2.0, 1.0, key="bt_risk")
    
    if st.button("🚀 RUN BACKTEST", type="primary"):
        with st.spinner("Running backtest..."):
            bt_df = get_historical_data(period=backtest_period, interval=selected_timeframe)
            if bt_df is not None and len(bt_df) > 100:
                bt_df = calculate_indicators(bt_df)
                bt_model, bt_scaler, _ = train_model(bt_df, 4)
                
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
                        sl, tp1, tp2, tp3, tp4, risk = calculate_levels(price, atr_val, direction)
                        
                        risk_amount = balance * (bt_risk / 100)
                        pos_size = risk_amount / risk
                        future = bt_df['Close'].iloc[i+1:i+5].values
                        
                        hit_sl = any(future <= sl if direction == "LONG" else future >= sl)
                        hit_tp = any(future >= tp2 if direction == "LONG" else future <= tp2)
                        
                        if hit_tp and not hit_sl:
                            profit = pos_size * abs(tp2 - price)
                            balance += profit
                            trades.append({'result': 'WIN', 'pnl': profit})
                        elif hit_sl:
                            balance -= risk_amount
                            trades.append({'result': 'LOSS', 'pnl': -risk_amount})
                        balance_history.append(balance)
                    
                    if trades:
                        wins = len([t for t in trades if t['result'] == 'WIN'])
                        losses = len([t for t in trades if t['result'] == 'LOSS'])
                        win_rate = wins / len(trades) * 100
                        gross_profit = sum([t['pnl'] for t in trades if t['result'] == 'WIN'])
                        gross_loss = abs(sum([t['pnl'] for t in trades if t['result'] == 'LOSS']))
                        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
                        total_pnl = sum([t['pnl'] for t in trades])
                        
                        r1, r2, r3, r4 = st.columns(4)
                        r1.metric("Total Trades", len(trades))
                        r2.metric("Win Rate", f"{win_rate:.1f}%")
                        r3.metric("Profit Factor", f"{profit_factor:.2f}")
                        r4.metric("Total P&L", f"${total_pnl:,.2f}")
                        
                        fig_eq = go.Figure()
                        fig_eq.add_trace(go.Scatter(x=list(range(len(balance_history))), y=balance_history, mode='lines', line=dict(color='#00ff88', width=2)))
                        fig_eq.add_hline(y=10000, line_dash="dash", line_color="gray")
                        fig_eq.update_layout(title="Equity Curve", template='plotly_dark', height=400)
                        st.plotly_chart(fig_eq, use_container_width=True)

with tab3:
    st.header("📜 TRADE HISTORY")
    
    if st.session_state.trade_history:
        for trade in st.session_state.trade_history[-10:]:
            st.info(f"📌 {trade['time'].strftime('%Y-%m-%d %H:%M:%S')} | {trade['direction']} | Entry: ${trade['entry']:.2f} | SL: ${trade['sl']:.2f} | TP: ${trade['tp']:.2f} | Size: {trade['size']:.4f}")
    else:
        st.info("No trades recorded. Click 'RECORD THIS TRADE' when you get a signal.")

st.markdown("---")
st.caption("⚠️ EDUCATIONAL ONLY - Not financial advice. Always test on DEMO first!")
