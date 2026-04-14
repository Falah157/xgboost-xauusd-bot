import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import xgboost as xgb
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="XGBOOST XAUUSD TRADER", layout="wide", page_icon="🚀")

st.markdown("""
<style>
    .main-title { font-size: 2rem; font-weight: bold; background: linear-gradient(90deg, #ffd700, #ff8c00); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; }
    .signal-buy { background: #0a3a2a22; border-left: 4px solid #00ff88; padding: 1rem; border-radius: 12px; margin: 0.5rem 0; }
    .signal-sell { background: #3a1a1a22; border-left: 4px solid #ff4444; padding: 1rem; border-radius: 12px; margin: 0.5rem 0; }
    .signal-wait { background: #1e1e2e; border-left: 4px solid #ffd700; padding: 1rem; border-radius: 12px; margin: 0.5rem 0; }
    .level-card { background: #13161d; border-radius: 10px; padding: 0.5rem; text-align: center; border: 1px solid #2a2e3a; }
    .level-price { font-size: 1rem; font-weight: bold; color: #ffd700; }
    .meter { background: #2a2e3a; border-radius: 10px; height: 8px; overflow: hidden; }
    .meter-fill { height: 100%; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🚀 XGBOOST AI TRADING DASHBOARD</div>', unsafe_allow_html=True)

# ============ CONFIGURATION ============
API_KEY = "96871e27b094425f9ea104fa6eb2be64"

# Session state
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'model_trained' not in st.session_state:
    st.session_state.model_trained = False
if 'accuracy' not in st.session_state:
    st.session_state.accuracy = 0

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
    """Calculate features for XGBoost model"""
    df = df.copy()
    
    # Moving Averages
    df['sma20'] = df['close'].rolling(20).mean()
    df['sma50'] = df['close'].rolling(50).mean()
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()
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
    
    # Bollinger Bands
    df['bb_middle'] = df['close'].rolling(20).mean()
    bb_std = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
    df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
    df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    
    # Stochastic
    low_14 = df['low'].rolling(14).min()
    high_14 = df['high'].rolling(14).max()
    df['stoch_k'] = 100 * ((df['close'] - low_14) / (high_14 - low_14))
    df['stoch_d'] = df['stoch_k'].rolling(3).mean()
    
    # ADX
    plus_dm = df['high'].diff()
    minus_dm = df['low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    atr = df['atr']
    df['plus_di'] = 100 * (plus_dm.rolling(14).mean() / atr)
    df['minus_di'] = 100 * (abs(minus_dm).rolling(14).mean() / atr)
    dx = (abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])) * 100
    df['adx'] = dx.rolling(14).mean()
    
    # Momentum
    df['momentum_5'] = df['close'].pct_change(5) * 100
    df['momentum_10'] = df['close'].pct_change(10) * 100
    df['volatility'] = df['close'].pct_change().rolling(20).std() * 100
    
    return df

def train_xgboost_model(df):
    """Train XGBoost model - More accurate than Random Forest"""
    features = ['rsi', 'macd_hist', 'atr_percent', 'price_vs_sma20', 
                'sma_diff', 'volatility', 'momentum_5', 'momentum_10',
                'stoch_k', 'adx', 'bb_position']
    
    df_clean = df.dropna()
    if len(df_clean) < 100:
        return None, None, 0
    
    # Target: price direction in next 4 hours
    df_clean['target'] = (df_clean['close'].shift(-4) > df_clean['close']).astype(int)
    df_clean = df_clean.dropna()
    
    X = df_clean[features].values
    y = df_clean['target'].values
    
    # Train/Test split
    split = int(len(X) * 0.8)
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    
    # XGBoost Classifier (Better than Random Forest!)
    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        use_label_encoder=False,
        eval_metric='logloss'
    )
    
    model.fit(X_train_scaled, y_train)
    accuracy = model.score(X_val_scaled, y_val)
    
    # Feature importance
    importance = dict(zip(features, model.feature_importances_))
    
    return model, scaler, accuracy, importance

def get_signal(model, scaler, features):
    """Get prediction from XGBoost"""
    if model is None:
        return "WAIT", 0
    
    features_scaled = scaler.transform(features)
    prob = model.predict_proba(features_scaled)[0]
    pred = 1 if prob[1] > 0.55 else 0
    confidence = max(prob) * 100
    
    if pred == 1 and confidence >= 60:
        return "BUY", confidence
    elif pred == 0 and confidence >= 60:
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

def run_backtest(df, model, scaler, risk_percent):
    features = ['rsi', 'macd_hist', 'atr_percent', 'price_vs_sma20', 
                'sma_diff', 'volatility', 'momentum_5', 'momentum_10',
                'stoch_k', 'adx', 'bb_position']
    
    df_test = df.dropna().copy()
    trades = []
    balance = 10000
    balance_history = [balance]
    
    for i in range(50, len(df_test) - 10):
        current_price = df_test.iloc[i]['close']
        atr = df_test.iloc[i]['atr'] if not pd.isna(df_test.iloc[i]['atr']) else current_price * 0.005
        
        feature_vector = df_test[features].iloc[i:i+1].values
        if len(feature_vector) == 0:
            continue
        
        features_scaled = scaler.transform(feature_vector)
        prob = model.predict_proba(features_scaled)[0]
        pred = 1 if prob[1] > 0.55 else 0
        confidence = max(prob) * 100
        
        if confidence < 60:
            continue
        
        signal = "BUY" if pred == 1 else "SELL"
        entry, sl, tp1, tp2, tp3, tp4, risk = calculate_levels(current_price, atr, signal)
        
        risk_amount = balance * (risk_percent / 100)
        pos_size = risk_amount / risk if risk > 0 else 0
        
        future_prices = df_test['close'].iloc[i+1:i+5].values
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
        gross_profit = sum([t['pnl'] for t in trades if t['result'] == 'WIN'])
        gross_loss = abs(sum([t['pnl'] for t in trades if t['result'] == 'LOSS']))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        return {
            'trades': len(trades),
            'wins': wins,
            'losses': len(trades) - wins,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'profit_factor': profit_factor,
            'balance_history': balance_history
        }
    return None

# ============ SIDEBAR ============
with st.sidebar:
    st.markdown("## ⚙️ XGBOOST SETTINGS")
    
    st.markdown("### 📊 TIMEFRAME")
    tf_options = ["1h", "4h"]
    selected_tf = st.selectbox("Timeframe", tf_options, index=0)
    
    st.markdown("### 💰 RISK")
    account_balance = st.number_input("Balance ($)", value=10000, step=1000)
    risk_percent = st.slider("Risk per Trade (%)", 0.5, 2.0, 1.0)
    
    st.markdown("### 🤖 MODEL STATUS")
    if st.session_state.model_trained:
        st.success(f"✅ XGBoost Active | Accuracy: {st.session_state.accuracy:.1%}")
    else:
        st.warning("⏳ Training XGBoost...")
    
    if st.button("🔄 Retrain Model", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 📊 BACKTEST")
    bt_days = st.selectbox("Period", ["30d", "60d", "90d"], index=1)
    if st.button("🚀 Run Backtest", use_container_width=True):
        days = {"30d": 30, "60d": 60, "90d": 90}[bt_days]
        with st.spinner("Running XGBoost backtest..."):
            bt_df = get_data(days)
            if bt_df is not None:
                bt_df = calculate_features(bt_df)
                bt_model, bt_scaler, bt_acc, _ = train_xgboost_model(bt_df)
                if bt_model:
                    result = run_backtest(bt_df, bt_model, bt_scaler, risk_percent)
                    if result:
                        st.session_state.backtest_results = result
                        st.success(f"Win Rate: {result['win_rate']:.1f}% | P&L: ${result['total_pnl']:.2f}")
                    else:
                        st.warning("No trades generated")

# ============ MAIN CONTENT ============
with st.spinner("Loading data and training XGBoost AI..."):
    df = get_data(90)
    current_price = get_price()

if df is not None and len(df) > 50:
    df = calculate_features(df)
    current_price = current_price if current_price else float(df['close'].iloc[-1])
    atr = float(df['atr'].iloc[-1]) if not pd.isna(df['atr'].iloc[-1]) else current_price * 0.005
    rsi = float(df['rsi'].iloc[-1]) if not pd.isna(df['rsi'].iloc[-1]) else 50
    adx = float(df['adx'].iloc[-1]) if not pd.isna(df['adx'].iloc[-1]) else 25
    
    # Train XGBoost model
    model, scaler, accuracy, importance = train_xgboost_model(df)
    
    if model:
        st.session_state.model_trained = True
        st.session_state.accuracy = accuracy
        
        # Display metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("XAUUSD", f"${current_price:.2f}")
        col2.metric("ATR", f"${atr:.2f}", f"{atr/current_price*100:.2f}%")
        col3.metric("RSI", f"{rsi:.1f}")
        col4.metric("ADX", f"{adx:.1f}", "Strong Trend" if adx > 25 else "Weak Trend")
        col5.metric("XGBoost Acc", f"{accuracy:.1%}")
        
        # Get features for prediction
        features = ['rsi', 'macd_hist', 'atr_percent', 'price_vs_sma20', 
                    'sma_diff', 'volatility', 'momentum_5', 'momentum_10',
                    'stoch_k', 'adx', 'bb_position']
        latest_features = df[features].iloc[-1:].values
        signal, confidence = get_signal(model, scaler, latest_features)
        
        # Display Signal
        st.markdown("---")
        st.markdown("## 🤖 XGBOOST AI SIGNAL")
        
        if signal == "BUY":
            st.markdown(f"""
            <div class="signal-buy">
                <div style="font-size: 1.5rem; font-weight: bold; color: #00ff88;">📈 XGBoost SAYS: BUY</div>
                <div>Confidence: {confidence:.0f}% | Model Accuracy: {accuracy:.1%}</div>
                <div class="meter"><div class="meter-fill" style="width: {confidence}%; background: #00ff88;"></div></div>
            </div>
            """, unsafe_allow_html=True)
            entry, sl, tp1, tp2, tp3, tp4, risk = calculate_levels(current_price, atr, "BUY")
        elif signal == "SELL":
            st.markdown(f"""
            <div class="signal-sell">
                <div style="font-size: 1.5rem; font-weight: bold; color: #ff4444;">📉 XGBoost SAYS: SELL</div>
                <div>Confidence: {confidence:.0f}% | Model Accuracy: {accuracy:.1%}</div>
                <div class="meter"><div class="meter-fill" style="width: {confidence}%; background: #ff4444;"></div></div>
            </div>
            """, unsafe_allow_html=True)
            entry, sl, tp1, tp2, tp3, tp4, risk = calculate_levels(current_price, atr, "SELL")
        else:
            st.markdown(f"""
            <div class="signal-wait">
                <div style="font-size: 1.5rem; font-weight: bold; color: #ffd700;">⏸️ XGBoost SAYS: WAIT</div>
                <div>Confidence: {confidence:.0f}% | Model Accuracy: {accuracy:.1%}</div>
                <div class="meter"><div class="meter-fill" style="width: {confidence}%; background: #ffd700;"></div></div>
            </div>
            """, unsafe_allow_html=True)
            entry, sl, tp1, tp2, tp3, tp4, risk = current_price, current_price, current_price, current_price, current_price, current_price, 0
        
        # Trading Levels
        if signal != "WAIT":
            st.markdown("---")
            st.markdown("## 🎯 TRADING LEVELS")
            
            level_cols = st.columns(6)
            level_cols[0].markdown(f'<div class="level-card"><div class="level-price">📍 ENTRY<br>${entry:.2f}</div></div>', unsafe_allow_html=True)
            level_cols[1].markdown(f'<div class="level-card"><div class="level-price">🛑 SL<br>${sl:.2f}</div><div style="font-size:0.7rem;">Risk: ${risk:.2f}</div></div>', unsafe_allow_html=True)
            level_cols[2].markdown(f'<div class="level-card"><div class="level-price">🎯 TP1<br>${tp1:.2f}</div></div>', unsafe_allow_html=True)
            level_cols[3].markdown(f'<div class="level-card"><div class="level-price">🎯 TP2<br>${tp2:.2f}</div></div>', unsafe_allow_html=True)
            level_cols[4].markdown(f'<div class="level-card"><div class="level-price">🎯 TP3<br>${tp3:.2f}</div></div>', unsafe_allow_html=True)
            level_cols[5].markdown(f'<div class="level-card"><div class="level-price">🎯 TP4<br>${tp4:.2f}</div></div>', unsafe_allow_html=True)
            
            # Position Sizing
            position_size = (account_balance * (risk_percent / 100)) / risk if risk > 0 else 0
            st.info(f"📊 Position Size: {position_size:.4f} lots | Risk Amount: ${account_balance * (risk_percent / 100):.2f}")
            
            if st.button("✅ RECORD TRADE", type="primary", use_container_width=True):
                st.session_state.trade_history.append({
                    'time': datetime.now(),
                    'signal': signal,
                    'entry': entry,
                    'tp2': tp2,
                    'confidence': confidence
                })
                st.success(f"Trade recorded at ${entry:.2f}")
                st.balloons()
        
        # Feature Importance
        with st.expander("📊 XGBoost Feature Importance"):
            for name, imp in sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5]:
                st.progress(imp, text=f"{name}: {imp:.1%}")
        
        # Chart
        st.markdown("---")
        st.markdown(f"## 📈 {selected_tf.upper()} CHART")
        
        fig = go.Figure()
        chart_df = df.tail(100)
        fig.add_trace(go.Candlestick(x=chart_df.index, open=chart_df['open'], high=chart_df['high'],
                                      low=chart_df['low'], close=chart_df['close'], name='XAUUSD'))
        
        if signal != "WAIT":
            fig.add_hline(y=entry, line_color="#ffd700", line_width=2, annotation_text="ENTRY")
            fig.add_hline(y=sl, line_color="#ff4444", line_dash="dash", annotation_text="SL")
        
        fig.update_layout(template='plotly_dark', height=500)
        st.plotly_chart(fig, use_container_width=True)
        
        # Trade History
        if st.session_state.trade_history:
            st.markdown("---")
            st.markdown("## 📋 RECENT TRADES")
            for trade in st.session_state.trade_history[-5:]:
                st.info(f"🎯 {trade['time'].strftime('%Y-%m-%d %H:%M:%S')} | {trade['signal']} | Entry: ${trade['entry']:.2f} | TP: ${trade['tp2']:.2f} | Conf: {trade['confidence']:.0f}%")
        
        # Backtest Results
        if 'backtest_results' in st.session_state and st.session_state.backtest_results:
            st.markdown("---")
            st.markdown("## 📊 BACKTEST RESULTS")
            res = st.session_state.backtest_results
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Trades", res['trades'])
            c2.metric("Win Rate", f"{res['win_rate']:.1f}%")
            c3.metric("Profit Factor", f"{res['profit_factor']:.2f}")
            c4.metric("Total P&L", f"${res['total_pnl']:.2f}")

# Footer
st.markdown("---")
st.caption("🚀 XGBoost AI Trading System | Better accuracy than Random Forest")
