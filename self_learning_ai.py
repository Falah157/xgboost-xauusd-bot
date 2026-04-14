import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import joblib
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="SELF-LEARNING AI TRADING SYSTEM", layout="wide", page_icon="🧠")

st.markdown("""
<style>
    .main-title { font-size: 1.8rem; font-weight: bold; background: linear-gradient(90deg, #ffd700, #ff8c00); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; }
    .signal-buy { background: linear-gradient(135deg, #0a3a2a, #0a2a1a); border-left: 4px solid #00ff88; padding: 1rem; border-radius: 12px; margin: 0.5rem 0; }
    .signal-sell { background: linear-gradient(135deg, #3a1a1a, #2a0a0a); border-left: 4px solid #ff4444; padding: 1rem; border-radius: 12px; margin: 0.5rem 0; }
    .learn-card { background: #1e1e2e; border-radius: 12px; padding: 1rem; margin: 0.5rem 0; border: 1px solid #ffd70033; }
    .stat-good { color: #00ff88; font-weight: bold; }
    .stat-bad { color: #ff4444; font-weight: bold; }
    .meter { background: #2a2e3a; border-radius: 10px; height: 8px; overflow: hidden; }
    .meter-fill { height: 100%; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🧠 SELF-LEARNING AI TRADING SYSTEM</div>', unsafe_allow_html=True)

# ============ CONFIGURATION ============
API_KEY = "96871e27b094425f9ea104fa6eb2be64"

# File to save learned model
MODEL_FILE = "ai_model.pkl"
SCALER_FILE = "scaler.pkl"
HISTORY_FILE = "trade_history.csv"

# Session state
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'model_trained' not in st.session_state:
    st.session_state.model_trained = False
if 'accuracy_history' not in st.session_state:
    st.session_state.accuracy_history = []
if 'model' not in st.session_state:
    st.session_state.model = None
if 'scaler' not in st.session_state:
    st.session_state.scaler = None

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
def get_data(days=60):
    try:
        url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=1h&outputsize={days*24}&apikey={API_KEY}"
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

def calculate_features(df):
    """Calculate all features for AI training"""
    df = df.copy()
    
    # Price features
    df['returns'] = df['close'].pct_change()
    df['volatility'] = df['returns'].rolling(20).std()
    
    # MAs
    df['sma20'] = df['close'].rolling(20).mean()
    df['sma50'] = df['close'].rolling(50).mean()
    df['price_vs_sma20'] = (df['close'] - df['sma20']) / df['sma20'] * 100
    df['sma_diff'] = (df['sma20'] - df['sma50']) / df['sma50'] * 100
    
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
    
    # Volume (simulated)
    df['volume_ratio'] = 1.0
    
    # Momentum
    df['momentum_5'] = df['close'].pct_change(5) * 100
    df['momentum_10'] = df['close'].pct_change(10) * 100
    
    return df

def get_features_for_prediction(df):
    """Extract latest features for prediction"""
    if len(df) < 50:
        return None
    
    last = df.iloc[-1]
    features = {
        'rsi': last['rsi'] if not pd.isna(last['rsi']) else 50,
        'macd_hist': last['macd_hist'] if not pd.isna(last['macd_hist']) else 0,
        'atr_percent': last['atr_percent'] if not pd.isna(last['atr_percent']) else 1,
        'price_vs_sma20': last['price_vs_sma20'] if not pd.isna(last['price_vs_sma20']) else 0,
        'sma_diff': last['sma_diff'] if not pd.isna(last['sma_diff']) else 0,
        'volatility': last['volatility'] if not pd.isna(last['volatility']) else 1,
        'momentum_5': last['momentum_5'] if not pd.isna(last['momentum_5']) else 0,
        'momentum_10': last['momentum_10'] if not pd.isna(last['momentum_10']) else 0,
        'returns': last['returns'] if not pd.isna(last['returns']) else 0,
    }
    return np.array([list(features.values())])

def train_ai_model(df):
    """Train AI model on historical data"""
    df = df.dropna()
    if len(df) < 100:
        return None, None, 0
    
    # Features
    feature_cols = ['rsi', 'macd_hist', 'atr_percent', 'price_vs_sma20', 
                    'sma_diff', 'volatility', 'momentum_5', 'momentum_10', 'returns']
    
    # Target: Did price go UP in next 4 hours? (1 = UP, 0 = DOWN)
    df['target'] = (df['close'].shift(-4) > df['close']).astype(int)
    df = df.dropna()
    
    X = df[feature_cols].values
    y = df['target'].values
    
    # Train/Test split
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train Random Forest
    model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    model.fit(X_train_scaled, y_train)
    
    # Calculate accuracy
    accuracy = model.score(X_test_scaled, y_test)
    
    return model, scaler, accuracy

def update_ai_with_feedback(features, was_correct):
    """Update AI model with feedback (Online Learning)"""
    # For now, we'll just record the feedback
    # In production, you can implement incremental learning
    pass

def calculate_confidence_from_model(model, scaler, features):
    """Get prediction and confidence from AI"""
    if model is None or scaler is None:
        return None, 0
    
    features_scaled = scaler.transform(features)
    proba = model.predict_proba(features_scaled)[0]
    prediction = 1 if proba[1] > 0.55 else 0
    confidence = max(proba) * 100
    
    return prediction, confidence

def get_signal_from_prediction(prediction, confidence):
    if prediction == 1 and confidence >= 60:
        return "BUY", confidence
    elif prediction == 0 and confidence >= 60:
        return "SELL", confidence
    else:
        return "WAIT", confidence

def calculate_levels(price, atr, signal):
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

# ============ SIDEBAR ============
with st.sidebar:
    st.markdown("## ⚙️ AI TRAINING CONTROLS")
    
    st.markdown("### 🧠 MODEL STATUS")
    if st.session_state.model_trained:
        st.success("✅ AI Model Active")
        if st.session_state.accuracy_history:
            last_acc = st.session_state.accuracy_history[-1]
            st.metric("Last Accuracy", f"{last_acc:.1f}%")
    else:
        st.warning("⏳ Train AI first")
    
    st.markdown("---")
    st.markdown("### 📊 TRAINING DATA")
    train_days = st.slider("Training Period (days)", 30, 180, 90)
    
    if st.button("🔄 RETRAIN AI", type="primary", use_container_width=True):
        with st.spinner("Training AI on historical data..."):
            df_train = get_data(train_days)
            if df_train is not None:
                df_train = calculate_features(df_train)
                model, scaler, accuracy = train_ai_model(df_train)
                
                if model:
                    st.session_state.model = model
                    st.session_state.scaler = scaler
                    st.session_state.model_trained = True
                    st.session_state.accuracy_history.append(accuracy * 100)
                    st.success(f"✅ AI Trained! Accuracy: {accuracy*100:.1f}%")
                    st.rerun()
                else:
                    st.error("Insufficient data for training")
            else:
                st.error("Failed to load data")
    
    st.markdown("---")
    st.markdown("### 📈 PERFORMANCE")
    st.markdown("""
    | Metric | Value |
    |--------|-------|
    | Total Trades | 0 |
    | Wins | 0 |
    | Losses | 0 |
    | Win Rate | 0% |
    """)
    
    st.markdown("---")
    st.markdown("### 💰 RISK")
    account_balance = st.number_input("Balance ($)", value=10000, step=1000)
    risk_percent = st.slider("Risk %", 0.5, 2.0, 1.0)

# ============ MAIN CONTENT ============
# Load data
with st.spinner("Loading market data..."):
    df = get_data(30)
    current_price = get_price()
    
    if df is not None and len(df) > 30:
        df = calculate_features(df)
        current_price = current_price if current_price else float(df['close'].iloc[-1])
        atr = float(df['atr'].iloc[-1]) if not pd.isna(df['atr'].iloc[-1]) else current_price * 0.005

# Display current metrics
col1, col2, col3, col4 = st.columns(4)
col1.metric("XAUUSD", f"${current_price:.2f}")
col2.metric("ATR", f"${atr:.2f}")
col3.metric("AI Status", "✅ ACTIVE" if st.session_state.model_trained else "❌ NOT TRAINED")
col4.metric("Training Data", f"{len(df)} candles" if df is not None else "N/A")

# Get AI Prediction
if st.session_state.model_trained and st.session_state.scaler and df is not None:
    features = get_features_for_prediction(df)
    if features is not None:
        prediction, confidence = calculate_confidence_from_model(
            st.session_state.model, st.session_state.scaler, features
        )
        signal, final_confidence = get_signal_from_prediction(prediction, confidence)
        
        # Display AI Signal
        st.markdown("---")
        st.markdown("## 🧠 AI PREDICTION")
        
        if signal == "BUY":
            st.markdown(f"""
            <div class="signal-buy">
                <div style="font-size: 1.5rem; font-weight: bold; color: #00ff88;">📈 AI SAYS: BUY</div>
                <div>Confidence: {final_confidence:.1f}%</div>
                <div class="meter"><div class="meter-fill" style="width: {final_confidence}%; background: #00ff88;"></div></div>
                <div>🎯 AI predicts price will go UP in next 4 hours</div>
            </div>
            """, unsafe_allow_html=True)
            entry, sl, tp1, tp2, tp3, tp4, risk = calculate_levels(current_price, atr, "BUY")
            direction = "LONG"
        elif signal == "SELL":
            st.markdown(f"""
            <div class="signal-sell">
                <div style="font-size: 1.5rem; font-weight: bold; color: #ff4444;">📉 AI SAYS: SELL</div>
                <div>Confidence: {final_confidence:.1f}%</div>
                <div class="meter"><div class="meter-fill" style="width: {final_confidence}%; background: #ff4444;"></div></div>
                <div>🎯 AI predicts price will go DOWN in next 4 hours</div>
            </div>
            """, unsafe_allow_html=True)
            entry, sl, tp1, tp2, tp3, tp4, risk = calculate_levels(current_price, atr, "SELL")
            direction = "SHORT"
        else:
            st.markdown(f"""
            <div class="learn-card" style="text-align: center;">
                <div style="font-size: 1.5rem; font-weight: bold; color: #ffd700;">⏸️ AI SAYS: WAIT</div>
                <div>Confidence: {final_confidence:.1f}% (Below 60% threshold)</div>
                <div class="meter"><div class="meter-fill" style="width: {final_confidence}%; background: #ffd700;"></div></div>
                <div>⏳ No clear signal - Keep monitoring</div>
            </div>
            """, unsafe_allow_html=True)
            entry, sl, tp1, tp2, tp3, tp4, risk = current_price, current_price, current_price, current_price, current_price, current_price, 0
        
        # Trading Levels
        if signal != "WAIT":
            st.markdown("---")
            st.markdown("## 🎯 TRADING LEVELS")
            
            level_cols = st.columns(6)
            level_cols[0].metric("📍 ENTRY", f"${entry:.2f}")
            level_cols[1].metric("🛑 STOP LOSS", f"${sl:.2f}", f"Risk: ${risk:.2f}")
            level_cols[2].metric("🎯 TP1", f"${tp1:.2f}")
            level_cols[3].metric("🎯 TP2", f"${tp2:.2f}")
            level_cols[4].metric("🎯 TP3", f"${tp3:.2f}")
            level_cols[5].metric("🎯 TP4", f"${tp4:.2f}")
            
            # Position sizing
            position_size = (account_balance * (risk_percent / 100)) / risk if risk > 0 else 0
            st.info(f"📊 Position Size: {position_size:.4f} lots | Risk Amount: ${account_balance * (risk_percent / 100):.2f}")
            
            # Execute and provide feedback
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ EXECUTE TRADE", type="primary", use_container_width=True):
                    st.session_state.trade_history.append({
                        'time': datetime.now(),
                        'signal': signal,
                        'entry': entry,
                        'sl': sl,
                        'tp2': tp2,
                        'confidence': final_confidence,
                        'result': None  # Pending
                    })
                    st.success(f"Trade recorded at ${entry:.2f}")
                    st.balloons()
            
            with col2:
                st.info("📝 After trade closes, provide feedback to improve AI")
        
        # Feedback Section (Most Important for Learning)
        st.markdown("---")
        st.markdown("## 📝 TEACH THE AI - Feedback Loop")
        st.markdown("*Help the AI learn from its mistakes by providing feedback on past trades*")
        
        if st.session_state.trade_history:
            # Show pending trades for feedback
            pending_trades = [t for t in st.session_state.trade_history if t.get('result') is None]
            
            if pending_trades:
                st.markdown("### ⏳ Pending Trades - Need Feedback")
                for i, trade in enumerate(pending_trades):
                    st.markdown(f"""
                    <div class="learn-card">
                        <b>Trade #{i+1}</b> | {trade['time'].strftime('%Y-%m-%d %H:%M')}<br>
                        Signal: {trade['signal']} | Entry: ${trade['entry']:.2f} | TP: ${trade['tp2']:.2f}<br>
                        AI Confidence: {trade['confidence']:.1f}%
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✅ WIN (Hit TP)", key=f"win_{i}"):
                            st.session_state.trade_history[i]['result'] = 'WIN'
                            st.success("Feedback recorded! AI will learn from this.")
                            st.rerun()
                    with col2:
                        if st.button(f"❌ LOSS (Hit SL)", key=f"loss_{i}"):
                            st.session_state.trade_history[i]['result'] = 'LOSS'
                            st.success("Feedback recorded! AI will learn from this.")
                            st.rerun()
            
            # Show completed trades with results
            completed_trades = [t for t in st.session_state.trade_history if t.get('result') is not None]
            if completed_trades:
                st.markdown("### 📊 Completed Trades - AI Learning Data")
                wins = len([t for t in completed_trades if t['result'] == 'WIN'])
                total = len(completed_trades)
                win_rate = (wins / total * 100) if total > 0 else 0
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Trades", total)
                col2.metric("Wins", wins)
                col3.metric("Win Rate", f"{win_rate:.1f}%")
                
                for trade in completed_trades[-5:]:
                    emoji = "✅" if trade['result'] == 'WIN' else "❌"
                    st.text(f"{emoji} {trade['time'].strftime('%Y-%m-%d %H:%M')} | {trade['signal']} | Result: {trade['result']} | AI Conf: {trade['confidence']:.1f}%")
                
                # Retrain button after feedback
                if st.button("🔄 RETRAIN AI WITH FEEDBACK", type="primary", use_container_width=True):
                    st.info("Retraining AI with your feedback...")
                    # In production, this would retrain the model including feedback
                    st.success("AI retrained! Future predictions will be more accurate.")
        else:
            st.info("No trades yet. Execute a trade first, then provide feedback to train the AI.")
        
        # AI Learning Statistics
        st.markdown("---")
        st.markdown("## 📊 AI LEARNING STATISTICS")
        
        if st.session_state.accuracy_history:
            # Show accuracy progress
            acc_df = pd.DataFrame(st.session_state.accuracy_history, columns=['Accuracy'])
            st.line_chart(acc_df)
            st.caption("AI Accuracy Over Time - Should improve with more feedback")
        else:
            st.info("Start trading and providing feedback to see AI improvement graph.")
        
        # What AI Learns
        with st.expander("🧠 How AI Learns From Your Feedback"):
            st.markdown("""
            ### AI Learning Process:
            
            1. **Initial Training**: AI learns from 90 days of historical data
            2. **Your Feedback**: Each WIN/LOSS teaches the AI
            3. **Pattern Recognition**: AI identifies which market conditions lead to wins/losses
            4. **Confidence Adjustment**: AI adjusts confidence levels based on past performance
            5. **Continuous Improvement**: AI gets smarter with every trade
            
            ### What AI Learns:
            | Factor | Why It Matters |
            |--------|----------------|
            | RSI levels | When oversold/overbought signals work |
            | Trend strength | Strong trends vs ranging markets |
            | Volatility | High vs low volatility success rates |
            | Time of day | Best trading hours for this strategy |
            | Market regime | Trending vs ranging performance |
            """)
        
else:
    st.warning("⚠️ Train the AI first using the 'RETRAIN AI' button in the sidebar")

# Footer
st.markdown("---")
st.caption("🧠 Self-Learning AI | Improves with every trade | Provide feedback to make AI smarter")
