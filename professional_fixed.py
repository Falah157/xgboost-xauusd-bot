import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="PRO XAUUSD TRADING PLATFORM", layout="wide")
st.title("🏆 PROFESSIONAL XAUUSD TRADING PLATFORM")

API_KEY = "96871e27b094425f9ea104fa6eb2be64"

# Timeframe mapping
TIMEFRAME_MAP = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "1h": "1h", "4h": "4h", "1d": "1day"}
TIMEFRAME_HOURS = {"1m": 1/60, "5m": 5/60, "15m": 15/60, "30m": 30/60, "1h": 1, "4h": 4, "1d": 24}

# Session state
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'active_positions' not in st.session_state:
    st.session_state.active_positions = []
if 'model_trained' not in st.session_state:
    st.session_state.model_trained = False

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
        days_map = {"1d": 1, "1w": 7, "1mo": 30, "3mo": 90, "6mo": 180}
        days = days_map.get(period, 90)
        hours_per_candle = TIMEFRAME_HOURS.get(interval, 1)
        total_candles = min(int((days * 24) / hours_per_candle), 5000)
        
        api_interval = TIMEFRAME_MAP.get(interval, "1h")
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
    df['Volatility'] = df['Close'].pct_change().rolling(20).std() * 100
    
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

def calculate_levels(price, atr, direction, timeframe):
    if timeframe in ["1m", "5m", "15m", "30m"]:
        sl_mult = 0.7
        tp_mult = [1.0, 1.5, 2.0, 2.5]
    else:
        sl_mult = 1.0
        tp_mult = [1.5, 2.0, 3.0, 4.0]
    
    if direction == "LONG":
        sl = price - (atr * sl_mult)
        tp1 = price + (atr * tp_mult[0])
        tp2 = price + (atr * tp_mult[1])
        tp3 = price + (atr * tp_mult[2])
        tp4 = price + (atr * tp_mult[3])
    else:
        sl = price + (atr * sl_mult)
        tp1 = price - (atr * tp_mult[0])
        tp2 = price - (atr * tp_mult[1])
        tp3 = price - (atr * tp_mult[2])
        tp4 = price - (atr * tp_mult[3])
    
    risk = abs(price - sl)
    rewards = [abs(tp - price) for tp in [tp1, tp2, tp3, tp4]]
    return sl, tp1, tp2, tp3, tp4, risk, rewards

def run_backtest(df, model, scaler, risk_percent, prediction_bars):
    features = ['RSI', 'MACD_Hist', 'ATR', 'SMA_20', 'SMA_50']
    df_test = df.dropna().copy()
    trades = []
    balance = 10000
    balance_history = [balance]
    
    for i in range(50, len(df_test) - prediction_bars):
        current_price = df_test['Close'].iloc[i]
        atr = df_test['ATR'].iloc[i]
        
        feature_vector = df_test[features].iloc[i:i+1].values
        if len(feature_vector) == 0:
            continue
        
        pred, conf = get_signal(model, scaler, feature_vector)
        if conf < 0.60:
            continue
        
        direction = "LONG" if pred == 1 else "SHORT"
        sl, tp1, tp2, tp3, tp4, risk, rewards = calculate_levels(current_price, atr, direction, "1h")
        
        risk_amount = balance * (risk_percent / 100)
        position_size = risk_amount / risk
        
        future_prices = df_test['Close'].iloc[i+1:i+prediction_bars+1].values
        
        hit_sl = any(future_prices <= sl if direction == "LONG" else future_prices >= sl)
        hit_tp2 = any(future_prices >= tp2 if direction == "LONG" else future_prices <= tp2)
        
        if hit_tp2 and not hit_sl:
            profit = position_size * abs(tp2 - current_price)
            balance += profit
            trades.append({
                'date': df_test.index[i], 'direction': direction, 'result': 'WIN',
                'pnl': profit, 'confidence': conf
            })
        elif hit_sl:
            balance -= risk_amount
            trades.append({
                'date': df_test.index[i], 'direction': direction, 'result': 'LOSS',
                'pnl': -risk_amount, 'confidence': conf
            })
        
        balance_history.append(balance)
    
    return trades, balance_history

# Sidebar
with st.sidebar:
    st.header("⚙️ SETTINGS")
    available_timeframes = ["15m", "30m", "1h", "4h"]
    selected_timeframe = st.selectbox("Timeframe", available_timeframes, index=2)
    
    prediction_options = {"15m": [4, 8, 12], "30m": [4, 8], "1h": [4, 8], "4h": [2, 4]}
    prediction_bars = st.selectbox("Prediction (candles ahead)", prediction_options.get(selected_timeframe, [4]))
    
    account_balance = st.number_input("Account Balance ($)", value=10000, step=1000)
    risk_percent = st.slider("Risk per Trade (%)", 0.5, 2.0, 1.0)
    min_confidence = st.slider("Min Confidence (%)", 50, 80, 60) / 100
    
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# Load data
with st.spinner(f"Loading {selected_timeframe} data..."):
    period_map = {"15m": "1mo", "30m": "1mo", "1h": "3mo", "4h": "3mo"}
    df = get_historical_data(period=period_map.get(selected_timeframe, "1mo"), interval=selected_timeframe)
    
    if df is not None and len(df) > 50:
        df = calculate_indicators(df)
        model, scaler, accuracy = train_model(df, prediction_bars)
        
        if model:
            st.session_state.model_trained = True
            current_price = get_realtime_price()
            if current_price is None:
                current_price = float(df['Close'].iloc[-1])
            atr = float(df['ATR'].iloc[-1]) if not pd.isna(df['ATR'].iloc[-1]) else current_price * 0.005
            rsi = float(df['RSI'].iloc[-1]) if not pd.isna(df['RSI'].iloc[-1]) else 50

# Main display
if st.session_state.model_trained and df is not None:
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("XAUUSD", f"${current_price:.2f}")
    col2.metric("ATR", f"${atr:.2f}")
    col3.metric("RSI", f"{rsi:.1f}")
    col4.metric("AI Accuracy", f"{accuracy:.1%}")
    col5.metric("Timeframe", selected_timeframe)
    
    # Get signal
    features = ['RSI', 'MACD_Hist', 'ATR', 'SMA_20', 'SMA_50']
    latest_features = df[features].iloc[-1:].values
    prediction, confidence = get_signal(model, scaler, latest_features)
    
    st.markdown("---")
    st.subheader("🤖 AI SIGNAL")
    
    if prediction == 1 and confidence >= min_confidence:
        st.success(f"📈 BULLISH - Confidence: {confidence:.1%}")
        direction = "LONG"
    elif prediction == 0 and confidence >= min_confidence:
        st.error(f"📉 BEARISH - Confidence: {confidence:.1%}")
        direction = "SHORT"
    else:
        st.warning(f"⏸️ NO SIGNAL - Confidence: {confidence:.1%} < {min_confidence:.0%}")
        direction = None
    
    if direction:
        sl, tp1, tp2, tp3, tp4, risk, rewards = calculate_levels(current_price, atr, direction, selected_timeframe)
        
        st.markdown("---")
        st.subheader("🎯 TRADING LEVELS")
        
        level_cols = st.columns(6)
        level_cols[0].metric("📍 ENTRY", f"${current_price:.2f}")
        level_cols[1].metric("🛑 SL", f"${sl:.2f}", f"Risk: ${risk:.2f}")
        level_cols[2].metric("🎯 TP1", f"${tp1:.2f}", f"+${rewards[0]:.2f}")
        level_cols[3].metric("🎯 TP2", f"${tp2:.2f}", f"+${rewards[1]:.2f}")
        level_cols[4].metric("🎯 TP3", f"${tp3:.2f}", f"+${rewards[2]:.2f}")
        level_cols[5].metric("🎯 TP4", f"${tp4:.2f}", f"+${rewards[3]:.2f}")
        
        # Position sizing
        st.markdown("---")
        st.subheader("⚙️ POSITION SIZING")
        pos_size = (account_balance * (risk_percent / 100)) / risk
        st.metric("Position Size", f"{pos_size:.4f} lots")
        st.metric("Risk Amount", f"${account_balance * (risk_percent / 100):.2f}")
        
        if st.button("✅ EXECUTE TRADE", type="primary"):
            st.session_state.active_positions.append({
                'date': datetime.now(), 'direction': direction, 'entry': current_price,
                'sl': sl, 'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'tp4': tp4,
                'confidence': confidence
            })
            st.success(f"Trade executed at ${current_price:.2f}")
            st.balloons()
        
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
        
        fig.update_layout(template='plotly_dark', height=700, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)
    
    # Backtest Section
    st.markdown("---")
    st.subheader("📊 BACKTEST")
    
    bt_col1, bt_col2 = st.columns(2)
    with bt_col1:
        backtest_period = st.selectbox("Backtest Period", ["1w", "1mo", "3mo"], index=1)
    with bt_col2:
        bt_risk = st.slider("Backtest Risk (%)", 0.5, 2.0, 1.0, key="bt_risk")
    
    if st.button("🚀 RUN BACKTEST", type="primary"):
        with st.spinner("Running backtest..."):
            bt_df = get_historical_data(period=backtest_period, interval=selected_timeframe)
            if bt_df is not None and len(bt_df) > 100:
                bt_df = calculate_indicators(bt_df)
                bt_model, bt_scaler, bt_acc = train_model(bt_df, prediction_bars)
                
                if bt_model:
                    trades, balance_history = run_backtest(bt_df, bt_model, bt_scaler, bt_risk, prediction_bars)
                    
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
                        
                        st.subheader("📈 RESULTS")
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
                        fig_eq.add_trace(go.Scatter(x=list(range(len(balance_history))), y=balance_history, mode='lines', name='Equity', line=dict(color='#00ff88', width=2)))
                        fig_eq.add_hline(y=10000, line_dash="dash", line_color="gray")
                        fig_eq.update_layout(title="Equity Curve", template='plotly_dark', height=400)
                        st.plotly_chart(fig_eq, use_container_width=True)
                        
                        with st.expander("View Recent Trades"):
                            for t in trades[-20:]:
                                emoji = "✅" if t['result'] == 'WIN' else "❌"
                                st.text(f"{emoji} {t['date'].strftime('%Y-%m-%d %H:%M')} | {t['direction']} | {t['result']} | P&L: ${t['pnl']:.2f}")
                    else:
                        st.warning("No trades generated")
    
    # Active positions
    if st.session_state.active_positions:
        st.markdown("---")
        st.subheader("📋 ACTIVE POSITIONS")
        for pos in st.session_state.active_positions[-5:]:
            st.text(f"{pos['date'].strftime('%H:%M')} | {pos['direction']} | Entry: ${pos['entry']:.2f} | SL: ${pos['sl']:.2f} | TP1-4: ${pos['tp1']:.0f}/{pos['tp2']:.0f}/{pos['tp3']:.0f}/{pos['tp4']:.0f}")

st.markdown("---")
st.caption("⚠️ Educational only - Not financial advice")
