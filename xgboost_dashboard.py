import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from datetime import datetime
import xgboost as xgb
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="XGBOOST XAUUSD TRADER", layout="wide")

st.title("🚀 XGBOOST AI TRADING DASHBOARD")

API_KEY = "96871e27b094425f9ea104fa6eb2be64"

if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []

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
    df = df.copy()
    df['sma20'] = df['close'].rolling(20).mean()
    df['sma50'] = df['close'].rolling(50).mean()
    df['price_vs_sma20'] = (df['close'] - df['sma20']) / df['sma20'] * 100
    df['sma_diff'] = (df['sma20'] - df['sma50']) / df['sma50'] * 100
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    df['ema12'] = df['close'].ewm(span=12).mean()
    df['ema26'] = df['close'].ewm(span=26).mean()
    df['macd'] = df['ema12'] - df['ema26']
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    df['hl'] = df['high'] - df['low']
    df['atr'] = df['hl'].rolling(14).mean()
    df['atr_percent'] = df['atr'] / df['close'] * 100
    
    df['returns'] = df['close'].pct_change()
    df['volatility'] = df['returns'].rolling(20).std() * 100
    df['momentum_5'] = df['close'].pct_change(5) * 100
    df['momentum_10'] = df['close'].pct_change(10) * 100
    
    low_14 = df['low'].rolling(14).min()
    high_14 = df['high'].rolling(14).max()
    df['stoch_k'] = 100 * ((df['close'] - low_14) / (high_14 - low_14))
    
    plus_dm = df['high'].diff()
    minus_dm = df['low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    atr = df['atr']
    df['plus_di'] = 100 * (plus_dm.rolling(14).mean() / atr)
    df['minus_di'] = 100 * (abs(minus_dm).rolling(14).mean() / atr)
    dx = (abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])) * 100
    df['adx'] = dx.rolling(14).mean()
    
    return df

def train_model(df):
    features = ['rsi', 'macd_hist', 'atr_percent', 'price_vs_sma20', 
                'sma_diff', 'volatility', 'momentum_5', 'momentum_10', 'stoch_k', 'adx']
    
    df_clean = df.dropna()
    if len(df_clean) < 100:
        return None, None, 0
    
    df_clean['target'] = (df_clean['close'].shift(-4) > df_clean['close']).astype(int)
    df_clean = df_clean.dropna()
    
    X = df_clean[features].values
    y = df_clean['target'].values
    
    split = int(len(X) * 0.8)
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    
    model = xgb.XGBClassifier(n_estimators=150, max_depth=6, learning_rate=0.05, random_state=42, eval_metric='logloss')
    model.fit(X_train_scaled, y_train)
    accuracy = model.score(X_val_scaled, y_val)
    
    return model, scaler, accuracy

def get_signal(model, scaler, features):
    if model is None:
        return "WAIT", 0
    features_scaled = scaler.transform(features)
    prob = model.predict_proba(features_scaled)[0]
    pred = 1 if prob[1] > 0.55 else 0
    confidence = max(prob) * 100
    if pred == 1 and confidence >= 55:
        return "BUY", confidence
    elif pred == 0 and confidence >= 55:
        return "SELL", confidence
    else:
        return "WAIT", confidence

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

with st.sidebar:
    st.header("⚙️ SETTINGS")
    account_balance = st.number_input("Balance ($)", value=10000, step=1000)
    risk_percent = st.slider("Risk %", 0.5, 2.0, 1.0)

with st.spinner("Loading data and training XGBoost..."):
    df = get_data(90)
    current_price = get_price()

if df is not None and len(df) > 50:
    df = calculate_features(df)
    current_price = current_price if current_price else float(df['close'].iloc[-1])
    atr = float(df['atr'].iloc[-1]) if not pd.isna(df['atr'].iloc[-1]) else current_price * 0.005
    rsi = float(df['rsi'].iloc[-1]) if not pd.isna(df['rsi'].iloc[-1]) else 50
    
    model, scaler, accuracy = train_model(df)
    
    if model:
        st.success(f"✅ XGBoost Trained! Accuracy: {accuracy:.1%}")
        
        features = ['rsi', 'macd_hist', 'atr_percent', 'price_vs_sma20', 
                    'sma_diff', 'volatility', 'momentum_5', 'momentum_10', 'stoch_k', 'adx']
        latest = df[features].iloc[-1:].values
        signal, confidence = get_signal(model, scaler, latest)
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("XAUUSD", f"${current_price:.2f}")
        col2.metric("ATR", f"${atr:.2f}")
        col3.metric("RSI", f"{rsi:.1f}")
        col4.metric("XGBoost Acc", f"{accuracy:.1%}")
        
        if signal == "BUY":
            st.success(f"📈 XGBoost: BUY with {confidence:.0f}% confidence")
            entry, sl, tp1, tp2, tp3, tp4, risk = calc_levels(current_price, atr, "BUY")
        elif signal == "SELL":
            st.error(f"📉 XGBoost: SELL with {confidence:.0f}% confidence")
            entry, sl, tp1, tp2, tp3, tp4, risk = calc_levels(current_price, atr, "SELL")
        else:
            st.warning(f"⏸️ XGBoost: WAIT (Confidence: {confidence:.0f}%)")
            entry, sl, tp1, tp2, tp3, tp4, risk = current_price, current_price, current_price, current_price, current_price, current_price, 0
        
        if signal != "WAIT":
            st.subheader("🎯 TRADING LEVELS")
            cols = st.columns(6)
            cols[0].metric("ENTRY", f"${entry:.2f}")
            cols[1].metric("SL", f"${sl:.2f}", f"Risk: ${risk:.2f}")
            cols[2].metric("TP1", f"${tp1:.2f}")
            cols[3].metric("TP2", f"${tp2:.2f}")
            cols[4].metric("TP3", f"${tp3:.2f}")
            cols[5].metric("TP4", f"${tp4:.2f}")
            
            pos_size = (account_balance * (risk_percent / 100)) / risk if risk > 0 else 0
            st.info(f"Position Size: {pos_size:.4f} lots | Risk: ${account_balance * (risk_percent / 100):.2f}")
            
            if st.button("✅ RECORD TRADE"):
                st.session_state.trade_history.append({
                    'time': datetime.now(),
                    'signal': signal,
                    'entry': entry,
                    'tp2': tp2,
                    'confidence': confidence
                })
                st.success(f"Trade recorded at ${entry:.2f}")
        
        st.subheader("📈 CHART")
        fig = go.Figure()
        chart_df = df.tail(100)
        fig.add_trace(go.Candlestick(x=chart_df.index, open=chart_df['open'], high=chart_df['high'], low=chart_df['low'], close=chart_df['close'], name='XAUUSD'))
        if signal != "WAIT":
            fig.add_hline(y=entry, line_color="#ffd700", line_width=2, annotation_text="ENTRY")
            fig.add_hline(y=sl, line_color="#ff4444", line_dash="dash", annotation_text="SL")
        fig.update_layout(template='plotly_dark', height=500)
        st.plotly_chart(fig, use_container_width=True)
        
        if st.session_state.trade_history:
            st.subheader("📋 RECENT TRADES")
            for trade in st.session_state.trade_history[-5:]:
                st.info(f"{trade['time'].strftime('%Y-%m-%d %H:%M:%S')} | {trade['signal']} | Entry: ${trade['entry']:.2f} | TP: ${trade['tp2']:.2f} | Conf: {trade['confidence']:.0f}%")
else:
    st.error("Failed to load market data. Please check your internet connection and refresh.")

st.caption("🚀 XGBoost AI Trading System | Better accuracy than Random Forest")
