import streamlit as st
import pandas as pd
import numpy as np
import requests
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import json
import time
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="PRO XAUUSD TRADING PLATFORM", 
    layout="wide",
    page_icon="🏆",
    initial_sidebar_state="expanded"
)

# ============ CONFIGURATION ============
API_KEY = "96871e27b094425f9ea104fa6eb2be64"

# Custom CSS for professional look
st.markdown("""
<style>
    .stApp {
        background-color: #0e1117;
    }
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        background: linear-gradient(90deg, #ffd700, #ff8c00);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 1rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #1e1e2e, #2a2a3a);
        border-radius: 15px;
        padding: 1rem;
        border: 1px solid #ffd70033;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .signal-bullish {
        background: linear-gradient(135deg, #0a3a2a, #0a2a1a);
        border-left: 4px solid #00ff88;
        padding: 1rem;
        border-radius: 10px;
    }
    .signal-bearish {
        background: linear-gradient(135deg, #3a1a1a, #2a0a0a);
        border-left: 4px solid #ff4444;
        padding: 1rem;
        border-radius: 10px;
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
    .level-label {
        font-size: 0.8rem;
        color: #888;
    }
</style>
""", unsafe_allow_html=True)

# ============ SESSION STATE INITIALIZATION ============
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'backtest_results' not in st.session_state:
    st.session_state.backtest_results = None
if 'model_trained' not in st.session_state:
    st.session_state.model_trained = False
if 'active_positions' not in st.session_state:
    st.session_state.active_positions = []
if 'performance_metrics' not in st.session_state:
    st.session_state.performance_metrics = {}
if 'risk_settings' not in st.session_state:
    st.session_state.risk_settings = {
        'max_risk_per_trade': 1.0,
        'max_daily_loss': 3.0,
        'max_consecutive_losses': 3,
        'max_positions': 1
    }
if 'daily_pnl' not in st.session_state:
    st.session_state.daily_pnl = 0
if 'consecutive_losses' not in st.session_state:
    st.session_state.consecutive_losses = 0
if 'last_trade_date' not in st.session_state:
    st.session_state.last_trade_date = datetime.now().date()

# ============ DATA FETCHING ============
@st.cache_data(ttl=10)
def get_realtime_price():
    try:
        url = f"https://api.twelvedata.com/price?symbol=XAU/USD&apikey={API_KEY}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return float(data['price'])
    except:
        pass
    return None

@st.cache_data(ttl=300)
def get_historical_data(period="1mo", interval="1h"):
    try:
        hours = {"1d": 24, "1h": 1, "15min": 0.25}
        multiplier = {"1mo": 720, "1w": 168, "3mo": 2160, "6mo": 4320}
        total_hours = multiplier.get(period, 720) * hours.get(interval, 1)
        url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval={interval}&outputsize={int(total_hours)}&apikey={API_KEY}"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if 'values' in data:
                df = pd.DataFrame(data['values'])
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df.set_index('datetime')
                df['Close'] = df['close'].astype(float)
                df['High'] = df['high'].astype(float)
                df['Low'] = df['low'].astype(float)
                df['Open'] = df['open'].astype(float)
                df['Volume'] = df['volume'].astype(float) if 'volume' in df else np.random.randint(1000, 10000, len(df))
                return df
    except Exception as e:
        st.error(f"Data fetch error: {e}")
    return None

# ============ ADVANCED INDICATORS ============
def calculate_all_indicators(df):
    df = df.copy()
    
    # Moving Averages
    for period in [9, 20, 50, 100, 200]:
        df[f'SMA_{period}'] = df['Close'].rolling(period).mean()
        df[f'EMA_{period}'] = df['Close'].ewm(span=period).mean()
    
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
    df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
    
    # Bollinger Bands
    df['BB_Middle'] = df['Close'].rolling(20).mean()
    bb_std = df['Close'].rolling(20).std()
    df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
    df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
    df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Middle']
    df['BB_Position'] = (df['Close'] - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower'])
    
    # ATR
    df['H-L'] = df['High'] - df['Low']
    df['H-PC'] = abs(df['High'] - df['Close'].shift())
    df['L-PC'] = abs(df['Low'] - df['Close'].shift())
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    df['ATR'] = df['TR'].rolling(14).mean()
    df['ATR_Percent'] = df['ATR'] / df['Close'] * 100
    
    # Stochastic
    low_14 = df['Low'].rolling(14).min()
    high_14 = df['High'].rolling(14).max()
    df['Stoch_K'] = 100 * ((df['Close'] - low_14) / (high_14 - low_14))
    df['Stoch_D'] = df['Stoch_K'].rolling(3).mean()
    
    # ADX
    plus_dm = df['High'].diff()
    minus_dm = df['Low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    atr = df['ATR']
    df['Plus_DI'] = 100 * (plus_dm.rolling(14).mean() / atr)
    df['Minus_DI'] = 100 * (abs(minus_dm).rolling(14).mean() / atr)
    dx = (abs(df['Plus_DI'] - df['Minus_DI']) / (df['Plus_DI'] + df['Minus_DI'])) * 100
    df['ADX'] = dx.rolling(14).mean()
    
    # Volume indicators
    df['Volume_SMA'] = df['Volume'].rolling(20).mean()
    df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA']
    
    # Price action
    df['Price_Position'] = (df['Close'] - df['SMA_20']) / df['SMA_20'] * 100
    df['Trend_Strength'] = abs(df['SMA_20'] - df['SMA_50']) / df['SMA_50'] * 100
    df['Volatility'] = df['Close'].pct_change().rolling(20).std() * 100
    
    # Market regime
    df['Market_Regime'] = np.where(df['ADX'] > 25, 'TRENDING', 'RANGING')
    
    return df

# ============ AI MODEL TRAINING ============
def train_advanced_ai_model(df):
    features = ['RSI', 'MACD_Histogram', 'ATR', 'SMA_20', 'SMA_50', 
                'BB_Position', 'Stoch_K', 'ADX', 'Volume_Ratio', 'Volatility']
    
    df_clean = df.dropna()
    if len(df_clean) < 200:
        return None, None, None, None
    
    # Multiple targets for ensemble
    df_clean['Target_1h'] = (df_clean['Close'].shift(-1) > df_clean['Close']).astype(int)
    df_clean['Target_4h'] = (df_clean['Close'].shift(-4) > df_clean['Close']).astype(int)
    df_clean = df_clean.dropna()
    
    X = df_clean[features].values
    y_1h = df_clean['Target_1h'].values
    y_4h = df_clean['Target_4h'].values
    
    split = int(len(X) * 0.8)
    X_train, X_val = X[:split], X[split:]
    y1_train, y1_val = y_1h[:split], y_1h[split:]
    y4_train, y4_val = y_4h[:split], y_4h[split:]
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    
    # Ensemble of models
    rf_1h = RandomForestClassifier(n_estimators=150, max_depth=10, random_state=42)
    rf_4h = RandomForestClassifier(n_estimators=150, max_depth=10, random_state=42)
    gb_1h = GradientBoostingClassifier(n_estimators=100, learning_rate=0.1, random_state=42)
    gb_4h = GradientBoostingClassifier(n_estimators=100, learning_rate=0.1, random_state=42)
    
    rf_1h.fit(X_train_scaled, y1_train)
    rf_4h.fit(X_train_scaled, y4_train)
    gb_1h.fit(X_train_scaled, y1_train)
    gb_4h.fit(X_train_scaled, y4_train)
    
    # Validation accuracy
    rf1_acc = rf_1h.score(X_val_scaled, y1_val)
    rf4_acc = rf_4h.score(X_val_scaled, y4_val)
    gb1_acc = gb_1h.score(X_val_scaled, y1_val)
    gb4_acc = gb_4h.score(X_val_scaled, y4_val)
    
    models = {
        'rf_1h': rf_1h, 'rf_4h': rf_4h,
        'gb_1h': gb_1h, 'gb_4h': gb_4h
    }
    
    accuracies = {
        '1h': (rf1_acc + gb1_acc) / 2,
        '4h': (rf4_acc + gb4_acc) / 2
    }
    
    return models, scaler, accuracies, features

def ensemble_predict(models, scaler, features):
    features_scaled = scaler.transform(features)
    
    # Get all predictions
    rf1_prob = models['rf_1h'].predict_proba(features_scaled)[0]
    rf4_prob = models['rf_4h'].predict_proba(features_scaled)[0]
    gb1_prob = models['gb_1h'].predict_proba(features_scaled)[0]
    gb4_prob = models['gb_4h'].predict_proba(features_scaled)[0]
    
    # Weighted ensemble
    prob_1h = (rf1_prob[1] * 0.5 + gb1_prob[1] * 0.5)
    prob_4h = (rf4_prob[1] * 0.6 + gb4_prob[1] * 0.4)
    
    # Final prediction (weighted by timeframe)
    final_prob = (prob_1h * 0.3 + prob_4h * 0.7)
    prediction = 1 if final_prob > 0.55 else 0
    confidence = final_prob if final_prob > 0.5 else 1 - final_prob
    
    return prediction, confidence, prob_4h

# ============ RISK MANAGEMENT ============
def check_risk_limits():
    """Check if we can trade based on risk limits"""
    today = datetime.now().date()
    
    # Reset daily P&L if new day
    if today != st.session_state.last_trade_date:
        st.session_state.daily_pnl = 0
        st.session_state.last_trade_date = today
    
    # Check daily loss limit
    if st.session_state.daily_pnl <= -st.session_state.risk_settings['max_daily_loss']:
        return False, f"Daily loss limit reached (${abs(st.session_state.daily_pnl):.2f})"
    
    # Check consecutive losses
    if st.session_state.consecutive_losses >= st.session_state.risk_settings['max_consecutive_losses']:
        return False, f"{st.session_state.consecutive_losses} consecutive losses - cooling down"
    
    # Check max positions
    if len(st.session_state.active_positions) >= st.session_state.risk_settings['max_positions']:
        return False, "Max positions reached"
    
    return True, "OK"

def calculate_position_size(account_size, risk_percent, entry, sl):
    risk_amount = account_size * (risk_percent / 100)
    position_size = risk_amount / abs(entry - sl)
    return position_size, risk_amount

# ============ TRADING LEVELS ============
def calculate_pro_levels(price, atr, direction, volatility_regime="normal"):
    """Calculate professional trading levels with volatility adjustment"""
    
    # Adjust multipliers based on volatility regime
    if volatility_regime == "high":
        sl_mult = 1.5
        tp_mult = [1.2, 1.8, 2.5, 3.5]
    elif volatility_regime == "low":
        sl_mult = 0.8
        tp_mult = [1.8, 2.5, 3.5, 5.0]
    else:
        sl_mult = 1.0
        tp_mult = [1.5, 2.0, 3.0, 4.0]
    
    if direction == "LONG":
        entry = price
        stop_loss = entry - (atr * sl_mult)
        tp1 = entry + (atr * tp_mult[0])
        tp2 = entry + (atr * tp_mult[1])
        tp3 = entry + (atr * tp_mult[2])
        tp4 = entry + (atr * tp_mult[3])
    else:
        entry = price
        stop_loss = entry + (atr * sl_mult)
        tp1 = entry - (atr * tp_mult[0])
        tp2 = entry - (atr * tp_mult[1])
        tp3 = entry - (atr * tp_mult[2])
        tp4 = entry - (atr * tp_mult[3])
    
    risk = abs(entry - stop_loss)
    rewards = [abs(tp - entry) for tp in [tp1, tp2, tp3, tp4]]
    
    return entry, stop_loss, tp1, tp2, tp3, tp4, risk, rewards

# ============ VISUALIZATION ============
def create_pro_chart(df, current_price, entry, sl, tp1, tp2, tp3, tp4, direction):
    """Create professional-grade trading chart"""
    
    fig = make_subplots(
        rows=3, cols=1,
        row_heights=[0.6, 0.2, 0.2],
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=('Price Action', 'RSI (14)', 'Volume')
    )
    
    # Price chart with candlesticks
    recent_df = df.tail(100)
    
    fig.add_trace(
        go.Candlestick(
            x=recent_df.index,
            open=recent_df['Open'],
            high=recent_df['High'],
            low=recent_df['Low'],
            close=recent_df['Close'],
            name='XAUUSD',
            increasing_line_color='#00ff88',
            decreasing_line_color='#ff4444'
        ),
        row=1, col=1
    )
    
    # Add trading levels
    level_colors = {
        'Entry': '#ffd700',
        'SL': '#ff4444',
        'TP1': '#00ff88',
        'TP2': '#00cc66',
        'TP3': '#009944',
        'TP4': '#006622'
    }
    
    for level_name, level_price, color in [
        ('Entry', entry, level_colors['Entry']),
        ('SL', sl, level_colors['SL']),
        ('TP1', tp1, level_colors['TP1']),
        ('TP2', tp2, level_colors['TP2']),
        ('TP3', tp3, level_colors['TP3']),
        ('TP4', tp4, level_colors['TP4'])
    ]:
        fig.add_hline(
            y=level_price, 
            line_dash="dash" if level_name == 'SL' else "solid",
            line_width=2 if level_name == 'Entry' else 1.5,
            line_color=color,
            annotation_text=level_name,
            annotation_position="right",
            row=1, col=1
        )
    
    # RSI
    fig.add_trace(
        go.Scatter(
            x=recent_df.index,
            y=recent_df['RSI'],
            name='RSI',
            line=dict(color='#9b59b6', width=1.5)
        ),
        row=2, col=1
    )
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
    fig.update_yaxes(range=[0, 100], row=2, col=1)
    
    # Volume
    colors = ['#00ff88' if close >= open_ else '#ff4444' 
              for close, open_ in zip(recent_df['Close'], recent_df['Open'])]
    fig.add_trace(
        go.Bar(
            x=recent_df.index,
            y=recent_df['Volume'],
            name='Volume',
            marker_color=colors,
            opacity=0.5
        ),
        row=3, col=1
    )
    
    # Layout
    fig.update_layout(
        title=f'{direction} TRADING SETUP - Professional Chart',
        template='plotly_dark',
        height=800,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        plot_bgcolor='#0e1117',
        paper_bgcolor='#0e1117'
    )
    
    fig.update_xaxes(title_text="Date/Time", row=3, col=1)
    fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
    fig.update_yaxes(title_text="RSI", row=2, col=1)
    fig.update_yaxes(title_text="Volume", row=3, col=1)
    
    return fig

# ============ BACKTEST ENGINE ============
def run_pro_backtest(df, models, scaler, risk_percent=1.0, use_tp_levels=True):
    """Professional backtest with multiple TP levels"""
    features = ['RSI', 'MACD_Histogram', 'ATR', 'SMA_20', 'SMA_50', 
                'BB_Position', 'Stoch_K', 'ADX', 'Volume_Ratio', 'Volatility']
    
    df_test = df.dropna().copy()
    trades = []
    balance = 10000
    balance_history = [balance]
    equity_curve = []
    
    for i in range(100, len(df_test) - 24):
        current_price = df_test['Close'].iloc[i]
        atr = df_test['ATR'].iloc[i]
        volatility = df_test['Volatility'].iloc[i]
        
        # Get features
        feature_vector = df_test[features].iloc[i:i+1].values
        if len(feature_vector) == 0:
            continue
        
        # Get AI prediction
        prediction, confidence, _ = ensemble_predict(models, scaler, feature_vector)
        
        # Only trade with >60% confidence
        if confidence < 0.60:
            continue
        
        # Determine volatility regime
        if volatility > df_test['Volatility'].quantile(0.8):
            regime = "high"
        elif volatility < df_test['Volatility'].quantile(0.2):
            regime = "low"
        else:
            regime = "normal"
        
        # Calculate levels
        direction = "LONG" if prediction == 1 else "SHORT"
        entry, sl, tp1, tp2, tp3, tp4, risk, rewards = calculate_pro_levels(
            current_price, atr, direction, regime
        )
        
        risk_amount = balance * (risk_percent / 100)
        position_size = risk_amount / risk
        
        # Simulate trade
        future_prices = df_test['Close'].iloc[i+1:i+25]
        price_path = future_prices.values
        
        hit_sl = any(price_path <= sl if direction == "LONG" else price_path >= sl)
        
        if use_tp_levels:
            # Check which TP was hit
            tp_hit = None
            for tp, reward in zip([tp1, tp2, tp3, tp4], rewards):
                if direction == "LONG":
                    if any(price_path >= tp):
                        tp_hit = tp
                        break
                else:
                    if any(price_path <= tp):
                        tp_hit = tp
                        break
            
            if tp_hit and not hit_sl:
                reward = abs(tp_hit - entry)
                profit = position_size * reward
                balance += profit
                trades.append({
                    'date': df_test.index[i], 'direction': direction, 
                    'result': 'WIN', 'pnl': profit, 'confidence': confidence,
                    'tp_hit': f"${tp_hit:.2f}", 'rr': reward/risk
                })
            elif hit_sl:
                balance -= risk_amount
                trades.append({
                    'date': df_test.index[i], 'direction': direction, 
                    'result': 'LOSS', 'pnl': -risk_amount, 'confidence': confidence,
                    'tp_hit': 'SL', 'rr': -1
                })
        else:
            # Simple 2R target
            tp2_target = entry + (atr * 2) if direction == "LONG" else entry - (atr * 2)
            hit_tp = any(price_path >= tp2_target if direction == "LONG" else price_path <= tp2_target)
            
            if hit_tp and not hit_sl:
                profit = position_size * atr * 2
                balance += profit
                trades.append({
                    'date': df_test.index[i], 'direction': direction, 
                    'result': 'WIN', 'pnl': profit, 'confidence': confidence,
                    'tp_hit': 'TP2', 'rr': 2
                })
            elif hit_sl:
                balance -= risk_amount
                trades.append({
                    'date': df_test.index[i], 'direction': direction, 
                    'result': 'LOSS', 'pnl': -risk_amount, 'confidence': confidence,
                    'tp_hit': 'SL', 'rr': -1
                })
        
        balance_history.append(balance)
        equity_curve.append(balance)
    
    return trades, balance_history, equity_curve

# ============ MAIN APPLICATION ============
st.markdown('<div class="main-header">🏆 PROFESSIONAL XAUUSD TRADING PLATFORM</div>', unsafe_allow_html=True)

# Load data
with st.spinner("Initializing AI Engine & Loading Market Data..."):
    df = get_historical_data(period="3mo", interval="1h")
    if df is not None:
        df = calculate_all_indicators(df)
        models, scaler, accuracies, features = train_advanced_ai_model(df)
        
        if models:
            st.session_state.model_trained = True
            current_price = get_realtime_price()
            if current_price is None:
                current_price = float(df['Close'].iloc[-1])
            atr = float(df['ATR'].iloc[-1])
            rsi = float(df['RSI'].iloc[-1])
            adx = float(df['ADX'].iloc[-1]) if not pd.isna(df['ADX'].iloc[-1]) else 25
            volatility = float(df['Volatility'].iloc[-1])
            market_regime = df['Market_Regime'].iloc[-1]

# Sidebar - Professional Controls
with st.sidebar:
    st.markdown("## ⚙️ TRADING CONTROLS")
    
    # Account settings
    with st.expander("💰 ACCOUNT SETTINGS", expanded=True):
        account_balance = st.number_input("Account Balance ($)", value=10000, step=1000)
        base_currency = st.selectbox("Base Currency", ["USD", "EUR", "GBP"])
    
    # Risk management
    with st.expander("🛡️ RISK MANAGEMENT", expanded=True):
        st.session_state.risk_settings['max_risk_per_trade'] = st.slider("Max Risk per Trade (%)", 0.5, 3.0, 1.0)
        st.session_state.risk_settings['max_daily_loss'] = st.slider("Max Daily Loss (%)", 1.0, 5.0, 3.0)
        st.session_state.risk_settings['max_consecutive_losses'] = st.slider("Max Consecutive Losses", 2, 5, 3)
        st.session_state.risk_settings['max_positions'] = st.slider("Max Concurrent Positions", 1, 3, 1)
    
    # AI settings
    with st.expander("🤖 AI SETTINGS", expanded=True):
        min_confidence = st.slider("Minimum Confidence (%)", 50, 85, 60) / 100
        timeframe = st.selectbox("Prediction Timeframe", ["1 Hour", "4 Hours", "1 Day"])
    
    # Display status
    st.markdown("---")
    st.markdown("### 📊 SYSTEM STATUS")
    
    if st.session_state.model_trained:
        st.success(f"✅ AI Active\nAccuracy: {accuracies['4h']:.1%}")
    else:
        st.warning("⏳ Training AI...")
    
    st.metric("Market Regime", market_regime if 'market_regime' in dir() else "N/A")
    st.metric("Volatility", f"{volatility:.2f}%" if 'volatility' in dir() else "N/A")
    
    # Refresh button
    if st.button("🔄 Force Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# Main content area
if st.session_state.model_trained and df is not None:
    
    # Top metrics row
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("XAUUSD", f"${current_price:.2f}", delta=None)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("ATR (14)", f"${atr:.2f}", delta=f"{atr/current_price*100:.2f}%")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("RSI (14)", f"{rsi:.1f}", 
                  delta="Overbought" if rsi > 70 else "Oversold" if rsi < 30 else "Neutral")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("ADX", f"{adx:.1f}", delta="Trending" if adx > 25 else "Ranging")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col5:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("AI Accuracy", f"{accuracies['4h']:.1%}", delta=f"1h: {accuracies['1h']:.1%}")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col6:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        daily_pnl_pct = (st.session_state.daily_pnl / account_balance * 100) if account_balance > 0 else 0
        st.metric("Daily P&L", f"${st.session_state.daily_pnl:.2f}", delta=f"{daily_pnl_pct:+.1f}%")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Get AI Signal
    latest_features = df[features].iloc[-1:].values
    prediction, confidence, prob_4h = ensemble_predict(models, scaler, latest_features)
    
    # Display AI Signal
    st.markdown("---")
    st.markdown("## 🤖 AI TRADING SIGNAL")
    
    if prediction == 1 and confidence >= min_confidence:
        st.markdown(f"""
        <div class="signal-bullish">
            <h2 style="color: #00ff88; margin: 0;">📈 BULLISH SIGNAL</h2>
            <p style="font-size: 1.2rem;">Confidence: {confidence:.1%} | Probability: {prob_4h:.1%}</p>
            <p>AI predicts price INCREASE in the next {timeframe}</p>
        </div>
        """, unsafe_allow_html=True)
        direction = "LONG"
    elif prediction == 0 and confidence >= min_confidence:
        st.markdown(f"""
        <div class="signal-bearish">
            <h2 style="color: #ff4444; margin: 0;">📉 BEARISH SIGNAL</h2>
            <p style="font-size: 1.2rem;">Confidence: {confidence:.1%} | Probability: {1-prob_4h:.1%}</p>
            <p>AI predicts price DECREASE in the next {timeframe}</p>
        </div>
        """, unsafe_allow_html=True)
        direction = "SHORT"
    else:
        st.warning(f"⏸️ NO CLEAR SIGNAL - Confidence {confidence:.1%} below threshold {min_confidence:.0%}")
        direction = None
    
    # Calculate Professional Trading Levels
    if direction:
        volatility_regime = "high" if volatility > 1.5 else "low" if volatility < 0.5 else "normal"
        entry, sl, tp1, tp2, tp3, tp4, risk, rewards = calculate_pro_levels(
            current_price, atr, direction, volatility_regime
        )
        
        # Display Trading Levels
        st.markdown("---")
        st.markdown("## 🎯 PROFESSIONAL TRADING LEVELS")
        
        level_cols = st.columns(6)
        level_data = [
            ("📍 ENTRY", entry, "-"),
            ("🛑 STOP LOSS", sl, f"Risk: ${risk:.2f}"),
            ("🎯 TP1 (1.5R)", tp1, f"+${rewards[0]:.2f}"),
            ("🎯 TP2 (2R)", tp2, f"+${rewards[1]:.2f}"),
            ("🎯 TP3 (3R)", tp3, f"+${rewards[2]:.2f}"),
            ("🎯 TP4 (4R)", tp4, f"+${rewards[3]:.2f}")
        ]
        
        for col, (label, price, delta) in zip(level_cols, level_data):
            with col:
                st.markdown(f"""
                <div class="level-box">
                    <div class="level-label">{label}</div>
                    <div class="level-price">${price:.2f}</div>
                    <div class="level-label">{delta}</div>
                </div>
                """, unsafe_allow_html=True)
        
        # Risk/Reward Summary
        st.markdown("---")
        st.markdown("### 📊 RISK/REWARD ANALYSIS")
        
        rr_cols = st.columns(5)
        rr_cols[0].metric("Risk", f"${risk:.2f}", f"{risk/current_price*100:.2f}%")
        rr_cols[1].metric("R:R TP1", f"1:{rewards[0]/risk:.1f}", "Minimum target")
        rr_cols[2].metric("R:R TP2", f"1:{rewards[1]/risk:.1f}", "Primary target")
        rr_cols[3].metric("R:R TP3", f"1:{rewards[2]/risk:.1f}", "Extended target")
        rr_cols[4].metric("R:R TP4", f"1:{rewards[3]/risk:.1f}", "Max target")
        
        # Position Sizing
        st.markdown("---")
        st.markdown("### ⚙️ POSITION SIZING")
        
        pos_col1, pos_col2, pos_col3 = st.columns(3)
        with pos_col1:
            risk_percent_input = st.number_input("Risk per Trade (%)", min_value=0.5, max_value=3.0, value=1.0, step=0.1)
        with pos_col2:
            position_size, risk_amount = calculate_position_size(account_balance, risk_percent_input, entry, sl)
            st.metric("Position Size", f"{position_size:.4f} lots")
        with pos_col3:
            st.metric("Risk Amount", f"${risk_amount:.2f}", delta=f"{risk_percent_input}% of account")
        
        # Check risk limits
        can_trade, risk_message = check_risk_limits()
        
        if can_trade:
            if st.button("✅ EXECUTE TRADE", type="primary", use_container_width=True):
                st.session_state.active_positions.append({
                    'id': len(st.session_state.active_positions),
                    'date': datetime.now(),
                    'direction': direction,
                    'entry': entry,
                    'sl': sl,
                    'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'tp4': tp4,
                    'position_size': position_size,
                    'risk_amount': risk_amount,
                    'confidence': confidence
                })
                st.success(f"✅ {direction} trade executed at ${entry:.2f}")
                st.balloons()
        else:
            st.error(f"⚠️ TRADE BLOCKED: {risk_message}")
        
        # Professional Chart
        st.markdown("---")
        st.markdown("## 📈 PROFESSIONAL CHART")
        
        fig = create_pro_chart(df, current_price, entry, sl, tp1, tp2, tp3, tp4, direction)
        st.plotly_chart(fig, use_container_width=True)
        
        # Active Positions
        if st.session_state.active_positions:
            st.markdown("---")
            st.markdown("## 📋 ACTIVE POSITIONS")
            
            for pos in st.session_state.active_positions:
                st.markdown(f"""
                <div class="metric-card">
                    <b>{pos['direction']}</b> | Entry: ${pos['entry']:.2f} | SL: ${pos['sl']:.2f} | 
                    TP1-4: ${pos['tp1']:.0f}/${pos['tp2']:.0f}/${pos['tp3']:.0f}/${pos['tp4']:.0f} | 
                    Size: {pos['position_size']:.4f} lots | Risk: ${pos['risk_amount']:.2f}
                </div>
                """, unsafe_allow_html=True)
    
    # Backtest Section
    st.markdown("---")
    st.markdown("## 📊 BACKTEST ENGINE")
    
    bt_col1, bt_col2, bt_col3 = st.columns(3)
    with bt_col1:
        backtest_period = st.selectbox("Backtest Period", ["1mo", "3mo", "6mo"], index=1)
    with bt_col2:
        bt_risk = st.slider("Risk per Trade (%)", 0.5, 2.0, 1.0, key="bt_risk")
    with bt_col3:
        use_multi_tp = st.checkbox("Use Multi-TP Levels", value=True)
    
    if st.button("🚀 RUN PROFESSIONAL BACKTEST", type="primary", use_container_width=True):
        with st.spinner("Running advanced backtest on historical data..."):
            bt_df = get_historical_data(period=backtest_period, interval="1h")
            if bt_df is not None:
                bt_df = calculate_all_indicators(bt_df)
                bt_models, bt_scaler, bt_acc, _ = train_advanced_ai_model(bt_df)
                
                if bt_models:
                    trades, balance_history, equity_curve = run_pro_backtest(
                        bt_df, bt_models, bt_scaler, bt_risk, use_multi_tp
                    )
                    
                    if trades:
                        # Calculate metrics
                        wins = len([t for t in trades if t['result'] == 'WIN'])
                        losses = len([t for t in trades if t['result'] == 'LOSS'])
                        win_rate = wins / len(trades) * 100
                        total_pnl = sum([t['pnl'] for t in trades])
                        avg_win = sum([t['pnl'] for t in trades if t['result'] == 'WIN']) / wins if wins > 0 else 0
                        avg_loss = abs(sum([t['pnl'] for t in trades if t['result'] == 'LOSS']) / losses) if losses > 0 else 0
                        profit_factor = avg_win / avg_loss if avg_loss > 0 else 0
                        sharpe = np.mean(equity_curve) / np.std(equity_curve) if len(equity_curve) > 1 else 0
                        
                        # Display results
                        st.subheader("📈 BACKTEST RESULTS")
                        
                        res_col1, res_col2, res_col3, res_col4 = st.columns(4)
                        res_col1.metric("Total Trades", len(trades))
                        res_col2.metric("Win Rate", f"{win_rate:.1f}%")
                        res_col3.metric("Profit Factor", f"{profit_factor:.2f}")
                        res_col4.metric("Sharpe Ratio", f"{sharpe:.2f}")
                        
                        res_col5, res_col6, res_col7, res_col8 = st.columns(4)
                        res_col5.metric("Total P&L", f"${total_pnl:,.2f}")
                        res_col6.metric("Final Balance", f"${balance_history[-1]:,.2f}")
                        res_col7.metric("Wins", wins)
                        res_col8.metric("Losses", losses)
                        
                        # Equity curve chart
                        fig_eq = go.Figure()
                        fig_eq.add_trace(go.Scatter(
                            x=list(range(len(balance_history))),
                            y=balance_history,
                            mode='lines',
                            name='Equity Curve',
                            line=dict(color='#00ff88', width=2)
                        ))
                        fig_eq.add_hline(y=10000, line_dash="dash", line_color="gray")
                        fig_eq.update_layout(
                            title="Equity Curve",
                            template='plotly_dark',
                            height=400,
                            xaxis_title="Trade Number",
                            yaxis_title="Balance ($)"
                        )
                        st.plotly_chart(fig_eq, use_container_width=True)
                        
                        # Recent trades
                        with st.expander("📋 View Recent Backtest Trades"):
                            for t in trades[-20:]:
                                emoji = "✅" if t['result'] == 'WIN' else "❌"
                                st.text(f"{emoji} {t['date'].strftime('%Y-%m-%d %H:%M')} | {t['direction']} | {t['result']} | TP: {t['tp_hit']} | P&L: ${t['pnl']:.2f} | Conf: {t['confidence']:.1%}")
                    else:
                        st.warning("No trades generated in backtest period")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 1rem; color: #666;">
    <p>🏆 Professional XAUUSD Trading Platform | AI-Powered | Real-Time Data</p>
    <p style="font-size: 0.8rem;">⚠️ EDUCATIONAL PURPOSES ONLY - Not financial advice. Past performance does not guarantee future results.</p>
</div>
""", unsafe_allow_html=True)
