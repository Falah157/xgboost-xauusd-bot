import streamlit as st
import pandas as pd
import numpy as np
import requests
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="PRO XAUUSD Trading System", layout="wide")
st.title("🏆 PROFESSIONAL XAUUSD TRADING SYSTEM")

API_KEY = "96871e27b094425f9ea104fa6eb2be64"

# Initialize session state
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'backtest_results' not in st.session_state:
    st.session_state.backtest_results = None
if 'model_trained' not in st.session_state:
    st.session_state.model_trained = False

@st.cache_data(ttl=30)
def get_realtime_price():
    try:
        url = f"https://api.twelvedata.com/price?symbol=XAU/USD&apikey={API_KEY}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return float(data['price'])
    except:
        pass
    return None

@st.cache_data(ttl=3600)
def get_historical_data(days=180):
    try:
        url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=1h&outputsize={days*24}&apikey={API_KEY}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'values' in data:
                df = pd.DataFrame(data['values'])
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df.set_index('datetime')
                df['Close'] = df['close'].astype(float)
                df['High'] = df['high'].astype(float)
                df['Low'] = df['low'].astype(float)
                df['Volume'] = df['volume'].astype(float) if 'volume' in df else np.random.randint(1000, 10000, len(df))
                return df
    except:
        pass
    return None

def calculate_indicators(df):
    df = df.copy()
    
    # Moving Averages
    df['SMA_20'] = df['Close'].rolling(20).mean()
    df['SMA_50'] = df['Close'].rolling(50).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    df['EMA_12'] = df['Close'].ewm(span=12).mean()
    df['EMA_26'] = df['Close'].ewm(span=26).mean()
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    # ATR for SL/TP
    df['H-L'] = df['High'] - df['Low']
    df['H-PC'] = abs(df['High'] - df['Close'].shift())
    df['L-PC'] = abs(df['Low'] - df['Close'].shift())
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    df['ATR'] = df['TR'].rolling(14).mean()
    
    # Bollinger Bands
    df['BB_Middle'] = df['Close'].rolling(20).mean()
    bb_std = df['Close'].rolling(20).std()
    df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
    df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
    
    return df

def train_ai_model(df):
    """Train AI model for predictions"""
    features = ['RSI', 'MACD_Hist', 'ATR', 'SMA_20', 'SMA_50']
    df_clean = df.dropna()
    
    if len(df_clean) < 100:
        return None, None, None
    
    # Target: price direction in next 4 hours
    df_clean['Target'] = (df_clean['Close'].shift(-4) > df_clean['Close']).astype(int)
    df_clean = df_clean.dropna()
    
    X = df_clean[features].values
    y = df_clean['Target'].values
    
    # Use last 20% for validation
    split = int(len(X) * 0.8)
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    
    model = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42)
    model.fit(X_train_scaled, y_train)
    
    val_accuracy = model.score(X_val_scaled, y_val)
    
    return model, scaler, val_accuracy

def get_ai_signal(model, scaler, latest_features):
    """Get AI prediction with confidence"""
    if model is None or scaler is None:
        return None, 0
    
    features_scaled = scaler.transform(latest_features)
    proba = model.predict_proba(features_scaled)[0]
    prediction = model.predict(features_scaled)[0]
    confidence = max(proba)
    
    return prediction, confidence

def calculate_tp_levels(price, atr, direction):
    """Calculate TP1, TP2, TP3, TP4 levels"""
    if direction == "LONG":
        tp1 = price + (atr * 1.5)  # 1.5R
        tp2 = price + (atr * 2.0)  # 2R
        tp3 = price + (atr * 3.0)  # 3R
        tp4 = price + (atr * 4.0)  # 4R
    else:
        tp1 = price - (atr * 1.5)
        tp2 = price - (atr * 2.0)
        tp3 = price - (atr * 3.0)
        tp4 = price - (atr * 4.0)
    
    return tp1, tp2, tp3, tp4

def run_backtest(df, model, scaler, risk_percent=1.0):
    """Run backtest on historical data"""
    features = ['RSI', 'MACD_Hist', 'ATR', 'SMA_20', 'SMA_50']
    df_test = df.dropna().copy()
    
    trades = []
    balance = 10000
    balance_history = [balance]
    
    for i in range(50, len(df_test) - 24):
        current_price = df_test['Close'].iloc[i]
        atr = df_test['ATR'].iloc[i]
        
        # Get features for this point
        feature_vector = df_test[features].iloc[i:i+1].values
        if len(feature_vector) == 0:
            continue
            
        # Scale features
        feature_scaled = scaler.transform(feature_vector)
        prediction = model.predict(feature_scaled)[0]
        confidence = max(model.predict_proba(feature_scaled)[0])
        
        # Only trade with >60% confidence
        if confidence < 0.60:
            continue
            
        risk_amount = balance * (risk_percent / 100)
        position_size = risk_amount / atr
        
        if prediction == 1:  # LONG
            entry = current_price
            sl = entry - atr
            tp2 = entry + (atr * 2)
            
            future_prices = df_test['Close'].iloc[i+1:i+25]
            hit_sl = any(future_prices <= sl)
            hit_tp = any(future_prices >= tp2)
            
            if hit_tp and not hit_sl:
                profit = position_size * atr * 2
                balance += profit
                trades.append({
                    'date': df_test.index[i], 'direction': 'LONG', 'result': 'WIN',
                    'pnl': profit, 'confidence': confidence
                })
            elif hit_sl:
                balance -= risk_amount
                trades.append({
                    'date': df_test.index[i], 'direction': 'LONG', 'result': 'LOSS',
                    'pnl': -risk_amount, 'confidence': confidence
                })
                
        else:  # SHORT
            entry = current_price
            sl = entry + atr
            tp2 = entry - (atr * 2)
            
            future_prices = df_test['Close'].iloc[i+1:i+25]
            hit_sl = any(future_prices >= sl)
            hit_tp = any(future_prices <= tp2)
            
            if hit_tp and not hit_sl:
                profit = position_size * atr * 2
                balance += profit
                trades.append({
                    'date': df_test.index[i], 'direction': 'SHORT', 'result': 'WIN',
                    'pnl': profit, 'confidence': confidence
                })
            elif hit_sl:
                balance -= risk_amount
                trades.append({
                    'date': df_test.index[i], 'direction': 'SHORT', 'result': 'LOSS',
                    'pnl': -risk_amount, 'confidence': confidence
                })
        
        balance_history.append(balance)
    
    return trades, balance_history

# ============ MAIN APP ============
tabs = st.tabs(["🎯 LIVE SIGNALS", "📊 BACKTEST", "📋 TRADE HISTORY", "🤖 AI MODEL INFO"])

# Load data
with st.spinner("Loading XAUUSD data & training AI..."):
    df = get_historical_data(180)
    if df is not None:
        df = calculate_indicators(df)
        model, scaler, val_accuracy = train_ai_model(df)
        if model:
            st.session_state.model_trained = True
            current_price = get_realtime_price()
            if current_price is None:
                current_price = float(df['Close'].iloc[-1])
            atr = float(df['ATR'].iloc[-1])
            rsi = float(df['RSI'].iloc[-1])

# ============ TAB 1: LIVE SIGNALS ============
with tabs[0]:
    st.header("🎯 LIVE AI TRADING SIGNALS")
    
    if current_price and model:
        # Current market info
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("XAUUSD", f"${current_price:.2f}")
        col2.metric("ATR (14)", f"${atr:.2f}")
        col3.metric("RSI (14)", f"{rsi:.1f}")
        col4.metric("AI Accuracy", f"{val_accuracy:.1%}" if val_accuracy else "N/A")
        
        # Get AI signal
        features = ['RSI', 'MACD_Hist', 'ATR', 'SMA_20', 'SMA_50']
        latest_features = df[features].iloc[-1:].values
        prediction, confidence = get_ai_signal(model, scaler, latest_features)
        
        # Display signal
        st.subheader("🤖 AI PREDICTION")
        if prediction == 1:
            st.success(f"📈 **BULLISH SIGNAL** with {confidence:.1%} confidence")
            direction = "LONG"
        else:
            st.error(f"📉 **BEARISH SIGNAL** with {confidence:.1%} confidence")
            direction = "SHORT"
        
        # Calculate SL and TP levels
        sl_mult = 1.0
        if direction == "LONG":
            entry = current_price
            stop_loss = entry - (atr * sl_mult)
            tp1, tp2, tp3, tp4 = calculate_tp_levels(entry, atr, "LONG")
        else:
            entry = current_price
            stop_loss = entry + (atr * sl_mult)
            tp1, tp2, tp3, tp4 = calculate_tp_levels(entry, atr, "SHORT")
        
        # Display TRADING SETUP clearly
        st.subheader("📊 TRADING SETUP")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            ### 📍 ENTRY
            **${entry:.2f}**
            
            ### 🛑 STOP LOSS
            **${stop_loss:.2f}**
            Risk: **${abs(entry - stop_loss):.2f}** ({abs(entry - stop_loss)/entry*100:.2f}%)
            """)
        
        with col2:
            st.markdown(f"""
            ### 🎯 TAKE PROFIT TARGETS
            
            | Target | Price | Reward |
            |--------|-------|--------|
            | **TP1 (1.5R)** | **${tp1:.2f}** | ${abs(tp1 - entry):.2f} |
            | **TP2 (2R)** | **${tp2:.2f}** | ${abs(tp2 - entry):.2f} |
            | **TP3 (3R)** | **${tp3:.2f}** | ${abs(tp3 - entry):.2f} |
            | **TP4 (4R)** | **${tp4:.2f}** | ${abs(tp4 - entry):.2f} |
            """)
        
        # Position Sizing
        st.subheader("⚙️ POSITION SIZING")
        account_size = st.number_input("Account Balance ($)", value=10000, step=1000, key="account_live")
        risk_pct = st.slider("Risk per trade (%)", 0.5, 3.0, 1.0, key="risk_live")
        
        risk_amount = account_size * (risk_pct / 100)
        position_size = risk_amount / abs(entry - stop_loss)
        
        col1, col2 = st.columns(2)
        col1.metric("Position Size", f"{position_size:.4f} lots")
        col2.metric("Risk Amount", f"${risk_amount:.2f}")
        
        # Execute trade button
        if st.button("✅ EXECUTE TRADE", type="primary"):
            st.session_state.trade_history.append({
                'date': datetime.now(),
                'direction': direction,
                'entry': entry,
                'sl': stop_loss,
                'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'tp4': tp4,
                'confidence': confidence
            })
            st.success(f"✅ {direction} trade recorded at ${entry:.2f} with SL ${stop_loss:.2f}")
        
    else:
        st.warning("Waiting for data...")

# ============ TAB 2: BACKTEST ============
with tabs[1]:
    st.header("📊 BACKTEST RESULTS")
    
    col1, col2 = st.columns(2)
    backtest_days = col1.slider("Backtest Period (days)", 30, 180, 90, key="bt_days")
    risk_backtest = col2.slider("Risk per trade (%)", 0.5, 2.0, 1.0, key="bt_risk")
    
    if st.button("🚀 RUN BACKTEST", type="primary"):
        with st.spinner("Running backtest on historical data..."):
            if model and scaler:
                df_backtest = get_historical_data(backtest_days)
                if df_backtest is not None:
                    df_backtest = calculate_indicators(df_backtest)
                    trades, balance_history = run_backtest(df_backtest, model, scaler, risk_backtest)
                    
                    if trades:
                        wins = len([t for t in trades if t['result'] == 'WIN'])
                        losses = len([t for t in trades if t['result'] == 'LOSS'])
                        win_rate = wins / len(trades) * 100
                        total_pnl = sum([t['pnl'] for t in trades])
                        avg_win = sum([t['pnl'] for t in trades if t['result'] == 'WIN']) / wins if wins > 0 else 0
                        avg_loss = abs(sum([t['pnl'] for t in trades if t['result'] == 'LOSS']) / losses) if losses > 0 else 0
                        profit_factor = avg_win / avg_loss if avg_loss > 0 else 0
                        
                        st.subheader("📈 PERFORMANCE SUMMARY")
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Total Trades", len(trades))
                        m2.metric("Win Rate", f"{win_rate:.1f}%")
                        m3.metric("Total P&L", f"${total_pnl:.2f}")
                        m4.metric("Profit Factor", f"{profit_factor:.2f}")
                        
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Wins", wins)
                        c2.metric("Losses", losses)
                        c3.metric("Avg Confidence", f"{np.mean([t['confidence'] for t in trades]):.1%}")
                        
                        # Equity curve
                        st.subheader("📉 EQUITY CURVE")
                        fig, ax = plt.subplots(figsize=(12, 4))
                        ax.plot(balance_history, color='green', linewidth=2)
                        ax.axhline(y=10000, color='gray', linestyle='--')
                        ax.set_ylabel('Balance ($)')
                        ax.set_xlabel('Trade Number')
                        ax.set_title('Account Balance Over Time')
                        ax.grid(True, alpha=0.3)
                        st.pyplot(fig)
                        
                        # Trade list
                        with st.expander("📋 View All Backtest Trades"):
                            for t in trades[-30:]:
                                emoji = "✅" if t['result'] == 'WIN' else "❌"
                                st.text(f"{emoji} {t['date'].strftime('%Y-%m-%d %H:%M')} | {t['direction']} | {t['result']} | P&L: ${t['pnl']:.2f} | Conf: {t['confidence']:.1%}")
                        
                        # Store in session state
                        for t in trades:
                            st.session_state.trade_history.append(t)
                    else:
                        st.warning("No trades generated in backtest period")

# ============ TAB 3: TRADE HISTORY ============
with tabs[2]:
    st.header("📋 TRADE HISTORY")
    
    if st.session_state.trade_history:
        trades_df = pd.DataFrame(st.session_state.trade_history)
        
        # Summary stats
        total_trades = len(trades_df)
        if 'result' in trades_df.columns:
            wins = len(trades_df[trades_df['result'] == 'WIN'])
            win_rate = wins / total_trades * 100
        else:
            # For live trades without results yet
            win_rate = 0
            wins = 0
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Trades", total_trades)
        col2.metric("Wins", wins)
        col3.metric("Win Rate", f"{win_rate:.1f}%")
        
        # Display recent trades
        st.subheader("Recent Trades")
        for trade in trades_df.tail(20).to_dict('records'):
            if 'result' in trade:
                emoji = "✅" if trade['result'] == 'WIN' else "❌"
                st.text(f"{emoji} {trade['date']} | {trade['direction']} | Result: {trade.get('result', 'PENDING')} | P&L: ${trade.get('pnl', 0):.2f}")
            else:
                st.text(f"📌 {trade['date']} | {trade['direction']} | Entry: ${trade['entry']:.2f} | SL: ${trade['sl']:.2f}")
        
        # Export button
        csv = trades_df.to_csv()
        st.download_button("📥 Export Trade History (CSV)", csv, "trade_history.csv", "text/csv")
        
        if st.button("Clear History"):
            st.session_state.trade_history = []
            st.rerun()
    else:
        st.info("No trades yet. Execute a live trade or run a backtest.")

# ============ TAB 4: AI MODEL INFO ============
with tabs[3]:
    st.header("🤖 AI MODEL INFORMATION")
    st.markdown("""
    ### 🧠 Model Architecture
    
    | Component | Details |
    |-----------|---------|
    | **Algorithm** | Random Forest Classifier |
    | **Features** | RSI, MACD Histogram, ATR, SMA20, SMA50 |
    | **Training Data** | Last 180 days of XAUUSD (1H candles) |
    | **Prediction Target** | Price direction in next 4 hours |
    | **Confidence Filter** | Only trade when >60% confident |
    
    ### 📊 Feature Importance
    
    | Feature | What It Measures |
    |---------|------------------|
    | **RSI** | Momentum & overbought/oversold |
    | **MACD Hist** | Trend strength & momentum |
    | **ATR** | Volatility for SL placement |
    | **SMA20/SMA50** | Trend direction |
    
    ### 🎯 Trading Levels Explained
    
    | Level | Multiple | Description |
    |-------|----------|-------------|
    | **SL** | 1.0 x ATR | Stop loss based on volatility |
    | **TP1** | 1.5 x ATR | First profit target |
    | **TP2** | 2.0 x ATR | Second profit target |
    | **TP3** | 3.0 x ATR | Third profit target |
    | **TP4** | 4.0 x ATR | Final profit target |
    
    ### ⚠️ Important Notes
    - Backtest uses 2R target (realistic)
    - Actual results may vary due to spreads/slippage
    - Always use proper risk management
    - Educational purposes only
    """)

st.sidebar.markdown("---")
st.sidebar.success("✅ COMPLETE SYSTEM READY")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.sidebar.warning("⚠️ Educational only - Not financial advice")

if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
