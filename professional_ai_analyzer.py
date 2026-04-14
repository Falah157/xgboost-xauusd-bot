import streamlit as st
import pandas as pd
import numpy as np
import requests
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import json
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="PROFESSIONAL AI XAUUSD Analyzer", layout="wide")
st.title("🏆 PROFESSIONAL AI XAUUSD Trading Analyzer")

# API Key
API_KEY = "96871e27b094425f9ea104fa6eb2be64"

# Initialize session state for trade history
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'backtest_results' not in st.session_state:
    st.session_state.backtest_results = None
if 'ai_model' not in st.session_state:
    st.session_state.ai_model = None

@st.cache_data(ttl=30)
def get_realtime_price():
    try:
        url = f"https://api.twelvedata.com/price?symbol=XAU/USD&apikey={API_KEY}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return float(data['price'])
    except:
        return None
    return None

@st.cache_data(ttl=3600)
def get_historical_data(days=90):
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
                df['Volume'] = df['volume'].astype(float) if 'volume' in df else 0
                return df
    except:
        pass
    return None

def calculate_all_indicators(df):
    df = df.copy()
    
    # Moving Averages
    df['SMA_20'] = df['Close'].rolling(20).mean()
    df['SMA_50'] = df['Close'].rolling(50).mean()
    df['EMA_12'] = df['Close'].ewm(span=12).mean()
    df['EMA_26'] = df['Close'].ewm(span=26).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
    df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
    
    # Bollinger Bands
    df['BB_Middle'] = df['Close'].rolling(20).mean()
    bb_std = df['Close'].rolling(20).std()
    df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
    df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
    
    # ATR
    df['High-Low'] = df['High'] - df['Low']
    df['High-Close'] = abs(df['High'] - df['Close'].shift())
    df['Low-Close'] = abs(df['Low'] - df['Close'].shift())
    df['TR'] = df[['High-Low', 'High-Close', 'Low-Close']].max(axis=1)
    df['ATR'] = df['TR'].rolling(14).mean()
    
    # Volume indicators
    df['Volume_SMA'] = df['Volume'].rolling(20).mean()
    
    return df

def train_ai_model(df):
    """Train Random Forest AI model for price direction prediction"""
    features = ['RSI', 'MACD', 'MACD_Signal', 'SMA_20', 'SMA_50', 'ATR']
    df_clean = df.dropna()
    
    if len(df_clean) < 100:
        return None, None
    
    X = df_clean[features].values
    y = (df_clean['Close'].shift(-4) > df_clean['Close']).astype(int)[:-4]
    X = X[:-4]
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_scaled, y)
    
    return model, scaler

def backtest_strategy(df, model, scaler, risk_percent=1.0):
    """Run backtest with AI predictions"""
    trades = []
    balance = 10000
    balance_history = [balance]
    
    features = ['RSI', 'MACD', 'MACD_Signal', 'SMA_20', 'SMA_50', 'ATR']
    df_clean = df.dropna().copy()
    
    for i in range(100, len(df_clean) - 24):
        current_price = df_clean['Close'].iloc[i]
        atr = df_clean['ATR'].iloc[i]
        
        # Get AI prediction
        feature_vector = df_clean[features].iloc[i:i+1].values
        feature_scaled = scaler.transform(feature_vector)
        prediction = model.predict(feature_scaled)[0]
        confidence = max(model.predict_proba(feature_scaled)[0])
        
        risk_amount = balance * (risk_percent / 100)
        position_size = risk_amount / atr
        
        if prediction == 1 and confidence > 0.6:  # Bullish with confidence
            entry = current_price
            sl = entry - atr
            tp2 = entry + (atr * 2)
            
            future_prices = df_clean['Close'].iloc[i+1:i+25]
            hit_sl = any(future_prices <= sl)
            hit_tp = any(future_prices >= tp2)
            
            if hit_tp and not hit_sl:
                profit = position_size * atr * 2
                balance += profit
                trades.append({
                    'date': df_clean.index[i], 'direction': 'LONG', 'result': 'WIN',
                    'pnl': profit, 'confidence': confidence
                })
            elif hit_sl:
                balance -= risk_amount
                trades.append({
                    'date': df_clean.index[i], 'direction': 'LONG', 'result': 'LOSS',
                    'pnl': -risk_amount, 'confidence': confidence
                })
                
        elif prediction == 0 and confidence > 0.6:  # Bearish with confidence
            entry = current_price
            sl = entry + atr
            tp2 = entry - (atr * 2)
            
            future_prices = df_clean['Close'].iloc[i+1:i+25]
            hit_sl = any(future_prices >= sl)
            hit_tp = any(future_prices <= tp2)
            
            if hit_tp and not hit_sl:
                profit = position_size * atr * 2
                balance += profit
                trades.append({
                    'date': df_clean.index[i], 'direction': 'SHORT', 'result': 'WIN',
                    'pnl': profit, 'confidence': confidence
                })
            elif hit_sl:
                balance -= risk_amount
                trades.append({
                    'date': df_clean.index[i], 'direction': 'SHORT', 'result': 'LOSS',
                    'pnl': -risk_amount, 'confidence': confidence
                })
        
        balance_history.append(balance)
    
    return trades, balance_history

# Main App Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📊 LIVE AI ANALYSIS", "📈 BACKTEST", "📋 TRADE HISTORY", "🤖 AI MODEL INFO"])

# Load data
with st.spinner("Loading XAUUSD data..."):
    current_price = get_realtime_price()
    df_hist = get_historical_data(90)
    
    if df_hist is not None:
        df_hist = calculate_all_indicators(df_hist)
        
        # Train AI model
        if st.session_state.ai_model is None:
            model, scaler = train_ai_model(df_hist)
            st.session_state.ai_model = (model, scaler)
        else:
            model, scaler = st.session_state.ai_model

with tab1:
    st.header("🎯 LIVE AI ANALYSIS")
    
    if current_price:
        st.metric("LIVE XAUUSD", f"${current_price:.2f}")
        
        # Get latest indicators
        if df_hist is not None and len(df_hist) > 0:
            latest = df_hist.iloc[-1]
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("RSI", f"{latest['RSI']:.1f}")
            col2.metric("MACD", f"{latest['MACD']:.2f}")
            col3.metric("ATR", f"${latest['ATR']:.2f}")
            col4.metric("Volume", f"{latest['Volume']:.0f}")
            
            # AI Prediction
            if model and scaler:
                features = ['RSI', 'MACD', 'MACD_Signal', 'SMA_20', 'SMA_50', 'ATR']
                feature_vector = df_hist[features].iloc[-1:].values
                feature_scaled = scaler.transform(feature_vector)
                prediction = model.predict(feature_scaled)[0]
                confidence = max(model.predict_proba(feature_scaled)[0])
                
                st.subheader("🤖 AI PREDICTION")
                if prediction == 1:
                    st.success(f"📈 BULLISH with {confidence:.1%} confidence")
                else:
                    st.error(f"📉 BEARISH with {confidence:.1%} confidence")
                
                # Trading levels
                atr = latest['ATR']
                if prediction == 1:
                    entry = current_price
                    sl = entry - atr
                    tps = {f"{r}R": entry + (atr * r) for r in [2, 3, 4, 5]}
                else:
                    entry = current_price
                    sl = entry + atr
                    tps = {f"{r}R": entry - (atr * r) for r in [2, 3, 4, 5]}
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("ENTRY", f"${entry:.2f}")
                    st.metric("STOP LOSS", f"${sl:.2f}")
                with col2:
                    for label, tp in tps.items():
                        st.metric(label, f"${tp:.2f}")
    
    # Live chart
    if df_hist is not None:
        st.subheader("📊 Price Chart with Indicators")
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(df_hist.index, df_hist['Close'], color='gold', linewidth=1.5, label='Price')
        ax.plot(df_hist.index, df_hist['SMA_20'], 'blue', linestyle='--', alpha=0.5, label='SMA 20')
        ax.plot(df_hist.index, df_hist['SMA_50'], 'red', linestyle='--', alpha=0.5, label='SMA 50')
        ax.fill_between(df_hist.index, df_hist['BB_Upper'], df_hist['BB_Lower'], alpha=0.1, color='gray')
        ax.set_ylabel('USD')
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        st.pyplot(fig)

with tab2:
    st.header("📈 BACKTEST RESULTS")
    
    col1, col2 = st.columns(2)
    backtest_days = col1.slider("Backtest Period (days)", 30, 180, 90)
    risk_backtest = col2.slider("Risk per trade (%)", 0.5, 3.0, 1.0)
    
    if st.button("🚀 RUN BACKTEST", type="primary"):
        with st.spinner("Running AI backtest..."):
            if model and scaler:
                df_backtest = get_historical_data(backtest_days)
                if df_backtest is not None:
                    df_backtest = calculate_all_indicators(df_backtest)
                    trades, balance_history = backtest_strategy(df_backtest, model, scaler, risk_backtest)
                    
                    st.session_state.backtest_results = (trades, balance_history)
                    
                    # Display results
                    actual_trades = [t for t in trades if t['result'] != 'NO_TRIGGER']
                    
                    if actual_trades:
                        wins = len([t for t in actual_trades if t['result'] == 'WIN'])
                        losses = len([t for t in actual_trades if t['result'] == 'LOSS'])
                        win_rate = wins / len(actual_trades) * 100
                        total_pnl = sum([t['pnl'] for t in actual_trades])
                        avg_win = sum([t['pnl'] for t in actual_trades if t['result'] == 'WIN']) / wins if wins > 0 else 0
                        avg_loss = abs(sum([t['pnl'] for t in actual_trades if t['result'] == 'LOSS']) / losses) if losses > 0 else 0
                        
                        st.subheader("📊 Performance Summary")
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Total Trades", len(actual_trades))
                        m2.metric("Win Rate", f"{win_rate:.1f}%")
                        m3.metric("Total P&L", f"${total_pnl:.2f}")
                        m4.metric("Profit Factor", f"{avg_win/avg_loss:.2f}" if avg_loss > 0 else "N/A")
                        
                        # Equity curve
                        st.subheader("📉 Equity Curve")
                        fig, ax = plt.subplots(figsize=(12, 4))
                        ax.plot(balance_history, color='green', linewidth=2)
                        ax.axhline(y=10000, color='gray', linestyle='--')
                        ax.set_ylabel('Balance ($)')
                        ax.set_xlabel('Trade Number')
                        ax.set_title('Account Balance Over Time')
                        ax.grid(True, alpha=0.3)
                        st.pyplot(fig)
                        
                        # Store in session state for trade history
                        for t in actual_trades:
                            st.session_state.trade_history.append(t)
                    else:
                        st.warning("No trades generated in backtest period")
                else:
                    st.error("Failed to load historical data")

with tab3:
    st.header("📋 TRADE HISTORY")
    
    if st.session_state.trade_history:
        # Create dataframe from trade history
        trades_df = pd.DataFrame(st.session_state.trade_history)
        trades_df['date'] = pd.to_datetime(trades_df['date'])
        
        # Summary stats
        col1, col2, col3, col4 = st.columns(4)
        total_trades = len(trades_df)
        wins = len(trades_df[trades_df['result'] == 'WIN'])
        win_rate = wins / total_trades * 100 if total_trades > 0 else 0
        total_pnl = trades_df['pnl'].sum()
        
        col1.metric("Total Trades", total_trades)
        col2.metric("Win Rate", f"{win_rate:.1f}%")
        col3.metric("Total P&L", f"${total_pnl:.2f}")
        col4.metric("Avg Confidence", f"{trades_df['confidence'].mean():.1%}")
        
        # Show recent trades
        st.subheader("Recent Trades")
        recent = trades_df.tail(20).sort_values('date', ascending=False)
        
        for _, trade in recent.iterrows():
            emoji = "✅" if trade['result'] == 'WIN' else "❌"
            st.text(f"{emoji} {trade['date'].strftime('%Y-%m-%d %H:%M')} | {trade['direction']} | {trade['result']} | P&L: ${trade['pnl']:.2f} | Confidence: {trade['confidence']:.1%}")
        
        # Export button
        csv = trades_df.to_csv()
        st.download_button("📥 Export Trade History (CSV)", csv, "trade_history.csv", "text/csv")
        
        if st.button("Clear Trade History"):
            st.session_state.trade_history = []
            st.rerun()
    else:
        st.info("No trades yet. Run a backtest to generate trade history.")

with tab4:
    st.header("🤖 AI MODEL INFORMATION")
    st.info("""
    ### 🧠 Model Architecture
    
    | Component | Details |
    |-----------|---------|
    | **Algorithm** | Random Forest Classifier |
    | **Features** | RSI, MACD, Signal, SMA20, SMA50, ATR |
    | **Training Data** | Last 90 days of XAUUSD |
    | **Prediction** | Price direction (Up/Down) in next 4 hours |
    | **Confidence Filter** | Only trades with >60% confidence |
    
    ### 📊 Feature Importance
    - **RSI** - Measures momentum and overbought/oversold conditions
    - **MACD** - Trend following momentum indicator
    - **Moving Averages** - Trend direction and support/resistance
    - **ATR** - Volatility measurement for stop loss placement
    
    ### ⚠️ Important Notes
    - AI is trained on historical data only
    - Past performance does not guarantee future results
    - Always use proper risk management
    - This is for educational purposes only
    """)

st.sidebar.markdown("---")
st.sidebar.success("🤖 AI-Powered XAUUSD Analyzer")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.sidebar.warning("⚠️ Educational only - Not financial advice")
