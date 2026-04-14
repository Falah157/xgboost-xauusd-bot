import streamlit as st
import pandas as pd
import numpy as np
import requests
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="IMPROVED AI XAUUSD Trader", layout="wide")
st.title("🏆 IMPROVED AI XAUUSD Trading System")

API_KEY = "96871e27b094425f9ea104fa6eb2be64"

# Initialize session state
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
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
                return df
    except:
        pass
    return None

def calculate_advanced_indicators(df):
    df = df.copy()
    
    # Moving Averages
    df['SMA_20'] = df['Close'].rolling(20).mean()
    df['SMA_50'] = df['Close'].rolling(50).mean()
    df['SMA_200'] = df['Close'].rolling(200).mean()
    df['EMA_9'] = df['Close'].ewm(span=9).mean()
    df['EMA_21'] = df['Close'].ewm(span=21).mean()
    
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
    
    # Bollinger Bands
    df['BB_Middle'] = df['Close'].rolling(20).mean()
    bb_std = df['Close'].rolling(20).std()
    df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
    df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
    df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Middle']
    
    # ATR
    df['H-L'] = df['High'] - df['Low']
    df['H-PC'] = abs(df['High'] - df['Close'].shift())
    df['L-PC'] = abs(df['Low'] - df['Close'].shift())
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    df['ATR'] = df['TR'].rolling(14).mean()
    
    # Volume indicators (simulated if not available)
    if 'Volume' not in df.columns:
        df['Volume'] = np.random.randint(1000, 10000, len(df))
    df['Volume_SMA'] = df['Volume'].rolling(20).mean()
    df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA']
    
    # Custom indicators
    df['Price_Position'] = (df['Close'] - df['SMA_20']) / df['SMA_20'] * 100
    df['Trend_Strength'] = abs(df['SMA_20'] - df['SMA_50']) / df['SMA_50'] * 100
    
    # Market regime detection
    df['Volatility_Regime'] = df['ATR'].rolling(50).mean() / df['ATR']
    
    return df

def detect_market_regime(df):
    """Detect if market is trending or ranging"""
    latest = df.iloc[-50:]
    adx = calculate_adx(latest)
    
    if adx > 25:
        return "TRENDING", "green"
    else:
        return "RANGING", "orange"

def calculate_adx(df, period=14):
    """Calculate ADX for trend strength"""
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    plus_dm = high.diff()
    minus_dm = low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    
    tr = df['TR']
    atr = tr.rolling(period).mean()
    
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = abs(100 * (minus_dm.rolling(period).mean() / atr))
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.rolling(period).mean()
    
    return adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 20

def train_improved_model(df):
    """Train ensemble model with better features"""
    features = [
        'RSI', 'MACD_Hist', 'BB_Width', 'ATR', 
        'Price_Position', 'Trend_Strength', 'Volume_Ratio'
    ]
    
    df_clean = df.dropna()
    if len(df_clean) < 200:
        return None, None, None
    
    # Create target: 4-hour forward return
    df_clean['Target'] = (df_clean['Close'].shift(-4) > df_clean['Close']).astype(int)
    df_clean = df_clean.dropna()
    
    X = df_clean[features].values
    y = df_clean['Target'].values[:-4]
    X = X[:-4]
    
    # Train/validation split
    split = int(len(X) * 0.8)
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    
    # Ensemble of models
    rf_model = RandomForestClassifier(n_estimators=150, max_depth=10, random_state=42)
    gb_model = GradientBoostingClassifier(n_estimators=100, learning_rate=0.1, random_state=42)
    
    rf_model.fit(X_train_scaled, y_train)
    gb_model.fit(X_train_scaled, y_train)
    
    # Validation accuracy
    rf_acc = rf_model.score(X_val_scaled, y_val)
    gb_acc = gb_model.score(X_val_scaled, y_val)
    
    return rf_model, gb_model, scaler, (rf_acc + gb_acc) / 2

def ensemble_predict(rf_model, gb_model, scaler, features):
    """Combine predictions from both models"""
    features_scaled = scaler.transform(features)
    rf_pred = rf_model.predict_proba(features_scaled)[0]
    gb_pred = gb_model.predict_proba(features_scaled)[0]
    
    # Weighted average (give more weight to better model)
    combined_prob = (rf_pred + gb_pred) / 2
    prediction = 1 if combined_prob[1] > 0.55 else 0  # Higher threshold for confidence
    confidence = max(combined_prob)
    
    return prediction, confidence

def calculate_dynamic_levels(price, atr, trend, regime):
    """Dynamic SL/TP based on market conditions"""
    if regime == "TRENDING":
        # Wider stops in trending markets
        sl_mult = 1.2
        tp_mult = [2.0, 3.0, 4.0, 5.0]
    else:
        # Tighter stops in ranging markets
        sl_mult = 0.8
        tp_mult = [1.5, 2.0, 2.5, 3.0]
    
    if trend == "BULLISH":
        sl = price - (atr * sl_mult)
        tps = {f"{int(r*10)}R": price + (atr * r) for r in tp_mult}
    else:
        sl = price + (atr * sl_mult)
        tps = {f"{int(r*10)}R": price - (atr * r) for r in tp_mult}
    
    return sl, tps

# Main App
st.sidebar.header("⚙️ Trading Settings")
risk_percent = st.sidebar.slider("Risk per trade (%)", 0.5, 3.0, 1.0)
min_confidence = st.sidebar.slider("Minimum AI Confidence (%)", 50, 80, 65) / 100
trade_direction = st.sidebar.selectbox("Trade Direction", ["Both", "Only LONG", "Only SHORT"])

# Load data
with st.spinner("Loading and training AI model..."):
    df = get_historical_data(180)
    if df is not None:
        df = calculate_advanced_indicators(df)
        rf_model, gb_model, scaler, val_acc = train_improved_model(df)
        
        if rf_model and gb_model:
            st.session_state.model_trained = True
            st.sidebar.success(f"✅ AI Trained | Validation Acc: {val_acc:.1%}")
        
        # Get current market regime
        regime, regime_color = detect_market_regime(df)
        st.sidebar.info(f"📊 Market Regime: **{regime}**")
        
        # Get current price
        current_price = get_realtime_price()
        if current_price is None:
            current_price = float(df['Close'].iloc[-1])
        
        # Get latest features
        features = ['RSI', 'MACD_Hist', 'BB_Width', 'ATR', 'Price_Position', 'Trend_Strength', 'Volume_Ratio']
        latest_features = df[features].iloc[-1:].values
        
        # Make prediction
        if st.session_state.model_trained:
            prediction, confidence = ensemble_predict(rf_model, gb_model, scaler, latest_features)
            
            # Apply direction filter
            if trade_direction == "Only LONG" and prediction == 0:
                prediction = None
                confidence = 0
                st.warning("⚠️ SHORT signal ignored (LONG only mode)")
            elif trade_direction == "Only SHORT" and prediction == 1:
                prediction = None
                confidence = 0
                st.warning("⚠️ LONG signal ignored (SHORT only mode)")
            
            # Display metrics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("XAUUSD", f"${current_price:.2f}")
            col2.metric("RSI", f"{df['RSI'].iloc[-1]:.1f}")
            col3.metric("ATR", f"${df['ATR'].iloc[-1]:.2f}")
            col4.metric("Market", regime)
            
            # AI Signal
            st.subheader("🤖 AI TRADING SIGNAL")
            
            if prediction is not None and confidence >= min_confidence:
                atr = df['ATR'].iloc[-1]
                trend = "BULLISH" if prediction == 1 else "BEARISH"
                sl, tps = calculate_dynamic_levels(current_price, atr, trend, regime)
                
                col1, col2 = st.columns(2)
                if prediction == 1:
                    col1.success(f"📈 **LONG SIGNAL**")
                else:
                    col1.error(f"📉 **SHORT SIGNAL**")
                col2.metric("Confidence", f"{confidence:.1%}")
                
                # Trading levels
                st.subheader("🎯 Dynamic Trading Levels")
                c1, c2 = st.columns(2)
                with c1:
                    st.metric("ENTRY", f"${current_price:.2f}")
                    st.metric("STOP LOSS", f"${sl:.2f}")
                with c2:
                    for label, tp in tps.items():
                        st.metric(f"TP {label}", f"${tp:.2f}")
                
                # Position sizing
                risk_amount = 10000 * (risk_percent / 100)
                position_size = risk_amount / abs(current_price - sl)
                st.metric("Position Size", f"{position_size:.4f} lots")
                
                # Entry button
                if st.button("✅ EXECUTE TRADE", type="primary"):
                    st.session_state.trade_history.append({
                        'date': datetime.now(),
                        'direction': 'LONG' if prediction == 1 else 'SHORT',
                        'entry': current_price,
                        'sl': sl,
                        'tp': list(tps.values())[0],
                        'confidence': confidence
                    })
                    st.success("Trade recorded!")
            elif confidence < min_confidence:
                st.warning(f"⏸️ Signal confidence {confidence:.1%} below threshold {min_confidence:.0%} - No trade")
            else:
                st.info("⚖️ No clear signal - Waiting for better setup")
            
            # Display recent trades
            if st.session_state.trade_history:
                st.subheader("📋 Active Trades")
                for trade in st.session_state.trade_history[-5:]:
                    st.text(f"{trade['date'].strftime('%H:%M')} | {trade['direction']} | Entry: ${trade['entry']:.2f} | SL: ${trade['sl']:.2f}")
        else:
            st.error("Insufficient data to train AI model. Need at least 200 candles.")
    else:
        st.error("Failed to load data. Check API key.")

st.sidebar.markdown("---")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.sidebar.warning("⚠️ Educational only - Not financial advice")

# Improvement tips
with st.expander("📈 How to Improve Win Rate"):
    st.markdown("""
    ### ✅ Key Improvements Added:
    
    | Improvement | Benefit |
    |-------------|---------|
    | **Higher confidence threshold** | Filters out low-quality signals |
    | **Market regime detection** | Adapts strategy to trending/ranging |
    | **Dynamic SL/TP** | Wider stops in trends, tighter in ranges |
    | **Ensemble model** | Combines RF + Gradient Boosting |
    | **Direction filter** | Trade only LONG or only SHORT |
    | **Validation accuracy** | Shows real model performance |
    
    ### 🎯 Recommended Settings:
    
    - **Risk per trade:** 0.5-1.0% (preserve capital)
    - **Min confidence:** 65-70% (quality over quantity)
    - **Trade direction:** Start with "Both", then specialize
    
    ### ⚠️ Remember:
    
    - 45-55% win rate with 2:1 R:R is profitable
    - Focus on **risk management**, not win rate
    - **Quality > Quantity** - fewer trades, better setups
    """)
