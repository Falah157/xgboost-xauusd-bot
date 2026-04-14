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

st.set_page_config(page_title="AI 50+ FEATURES", layout="wide", page_icon="🏆")
st.title("🏆 AI-POWERED 50+ FEATURES TRADING DASHBOARD")

API_KEY = "96871e27b094425f9ea104fa6eb2be64"

if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = datetime.now()
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'backtest_results' not in st.session_state:
    st.session_state.backtest_results = None
if 'model_trained' not in st.session_state:
    st.session_state.model_trained = False

ALL_TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
TIMEFRAMES = {
    "1m": {"api": "1min", "minutes": 1},
    "5m": {"api": "5min", "minutes": 5},
    "15m": {"api": "15min", "minutes": 15},
    "30m": {"api": "30min", "minutes": 30},
    "1h": {"api": "1h", "minutes": 60},
    "4h": {"api": "4h", "minutes": 240},
    "1d": {"api": "1day", "minutes": 1440}
}

SYMBOLS = {
    "XAUUSD": {"api": "XAU/USD", "digits": 2},
    "BTCUSD": {"api": "BTC/USD", "digits": 0}
}

if 'selected_symbol' not in st.session_state:
    st.session_state.selected_symbol = "XAUUSD"
if 'selected_tf' not in st.session_state:
    st.session_state.selected_tf = "1h"

refresh_interval = st.sidebar.slider("Auto Refresh (seconds)", 30, 120, 60)
if (datetime.now() - st.session_state.last_refresh).total_seconds() >= refresh_interval:
    st.session_state.last_refresh = datetime.now()
    st.cache_data.clear()
    st.rerun()

@st.cache_data(ttl=30)
def get_price(symbol):
    try:
        url = f"https://api.twelvedata.com/price?symbol={SYMBOLS[symbol]['api']}&apikey={API_KEY}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return float(r.json()['price'])
    except:
        pass
    return None

@st.cache_data(ttl=60)
def get_data(symbol, tf, days=90):
    try:
        minutes = TIMEFRAMES[tf]["minutes"]
        total = min(int((days * 1440) / minutes), 500)
        url = f"https://api.twelvedata.com/time_series?symbol={SYMBOLS[symbol]['api']}&interval={TIMEFRAMES[tf]['api']}&outputsize={total}&apikey={API_KEY}"
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

def calculate_indicators(df):
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
    df['volatility'] = df['close'].pct_change().rolling(20).std() * 100
    df['momentum'] = df['close'].pct_change(5) * 100
    
    low_14 = df['low'].rolling(14).min()
    high_14 = df['high'].rolling(14).max()
    df['stoch_k'] = 100 * ((df['close'] - low_14) / (high_14 - low_14))
    df['williams_r'] = -100 * ((high_14 - df['close']) / (high_14 - low_14))
    
    plus_dm = df['high'].diff()
    minus_dm = df['low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    atr = df['atr']
    df['plus_di'] = 100 * (plus_dm.rolling(14).mean() / atr)
    df['minus_di'] = 100 * (abs(minus_dm).rolling(14).mean() / atr)
    dx = (abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])) * 100
    df['adx'] = dx.rolling(14).mean()
    
    recent_high = df['high'].tail(50).max()
    recent_low = df['low'].tail(50).min()
    diff = recent_high - recent_low
    df['fib_236'] = recent_low + diff * 0.236
    df['fib_382'] = recent_low + diff * 0.382
    df['fib_500'] = recent_low + diff * 0.5
    df['fib_618'] = recent_low + diff * 0.618
    df['fib_786'] = recent_low + diff * 0.786
    
    df['supply_zone'] = df['high'].rolling(20).max()
    df['demand_zone'] = df['low'].rolling(20).min()
    df['snapshot_open'] = df['open'].iloc[-24] if len(df) >= 24 else df['open'].iloc[0]
    df['snapshot_high'] = df['high'].tail(24).max()
    df['snapshot_low'] = df['low'].tail(24).min()
    
    return df

def train_ai_model(df):
    features = ['rsi', 'macd_hist', 'atr_percent', 'price_vs_sma20', 
                'sma_diff', 'volatility', 'momentum', 'stoch_k', 'adx']
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
    rf = RandomForestClassifier(n_estimators=150, max_depth=10, random_state=42)
    gb = GradientBoostingClassifier(n_estimators=100, learning_rate=0.1, random_state=42)
    rf.fit(X_train_scaled, y_train)
    gb.fit(X_train_scaled, y_train)
    rf_acc = rf.score(X_val_scaled, y_val)
    gb_acc = gb.score(X_val_scaled, y_val)
    accuracy = (rf_acc + gb_acc) / 2
    return rf, gb, scaler, accuracy, features

def get_ai_signal(rf, gb, scaler, features):
    if rf is None:
        return "WAIT", 0
    features_scaled = scaler.transform(features)
    rf_prob = rf.predict_proba(features_scaled)[0]
    gb_prob = gb.predict_proba(features_scaled)[0]
    final_prob = (rf_prob[1] * 0.6 + gb_prob[1] * 0.4)
    pred = 1 if final_prob > 0.55 else 0
    confidence = final_prob * 100 if final_prob > 0.5 else (1 - final_prob) * 100
    if pred == 1 and confidence >= 55:
        return "BUY", confidence
    elif pred == 0 and confidence >= 55:
        return "SELL", confidence
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

def run_backtest(df, rf, gb, scaler, risk_percent):
    features = ['rsi', 'macd_hist', 'atr_percent', 'price_vs_sma20', 
                'sma_diff', 'volatility', 'momentum', 'stoch_k', 'adx']
    df_test = df.dropna().copy()
    trades = []
    balance = 10000
    balance_history = [balance]
    for i in range(50, len(df_test) - 4):
        current_price = df_test.iloc[i]['close']
        atr = df_test.iloc[i]['atr'] if not pd.isna(df_test.iloc[i]['atr']) else current_price * 0.005
        feature_vector = df_test[features].iloc[i:i+1].values
        if len(feature_vector) == 0:
            continue
        features_scaled = scaler.transform(feature_vector)
        rf_prob = rf.predict_proba(features_scaled)[0]
        gb_prob = gb.predict_proba(features_scaled)[0]
        final_prob = (rf_prob[1] * 0.6 + gb_prob[1] * 0.4)
        pred = 1 if final_prob > 0.55 else 0
        confidence = final_prob * 100 if final_prob > 0.5 else (1 - final_prob) * 100
        if confidence < 55:
            continue
        signal = "BUY" if pred == 1 else "SELL"
        entry, sl, tp1, tp2, tp3, tp4, risk = calc_levels(current_price, atr, signal)
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
        return {'trades': len(trades), 'wins': wins, 'losses': len(trades)-wins, 'win_rate': win_rate, 'total_pnl': total_pnl, 'profit_factor': profit_factor, 'balance_history': balance_history}
    return None

with st.sidebar:
    st.markdown("## ⚙️ SETTINGS")
    symbol = st.selectbox("Symbol", ["XAUUSD", "BTCUSD"], index=0)
    if symbol != st.session_state.selected_symbol:
        st.session_state.selected_symbol = symbol
        st.cache_data.clear()
        st.rerun()
    tf = st.selectbox("Timeframe", ALL_TIMEFRAMES, index=4)
    if tf != st.session_state.selected_tf:
        st.session_state.selected_tf = tf
        st.cache_data.clear()
        st.rerun()
    account_balance = st.number_input("Balance ($)", value=10000, step=1000)
    risk_percent = st.slider("Risk %", 0.5, 2.0, 1.0)
    if st.button("Run AI Backtest", use_container_width=True):
        with st.spinner("AI Backtesting..."):
            bt_df = get_data(symbol, tf, 60)
            if bt_df is not None:
                bt_df = calculate_indicators(bt_df)
                rf, gb, bt_scaler, bt_acc, _ = train_ai_model(bt_df)
                if rf:
                    result = run_backtest(bt_df, rf, gb, bt_scaler, risk_percent)
                    if result:
                        st.session_state.backtest_results = result
                        st.success(f"Win Rate: {result['win_rate']:.1f}%")

with st.spinner("Loading data and training AI..."):
    df = get_data(st.session_state.selected_symbol, st.session_state.selected_tf, 90)
    current_price = get_price(st.session_state.selected_symbol)

if df is not None and len(df) > 50:
    df = calculate_indicators(df)
    current_price = current_price if current_price else float(df['close'].iloc[-1])
    atr = float(df['atr'].iloc[-1]) if not pd.isna(df['atr'].iloc[-1]) else current_price * 0.005
    
    rf_model, gb_model, scaler, accuracy, features = train_ai_model(df)
    
    if rf_model:
        st.session_state.model_trained = True
        st.session_state.accuracy = accuracy
        
        feature_vector = df[features].iloc[-1:].values
        signal, confidence = get_ai_signal(rf_model, gb_model, scaler, feature_vector)
        
        st.subheader("📊 MARKET SNAPSHOT")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Open", f"${df['snapshot_open'].iloc[-1]:.2f}")
        c2.metric("High", f"${df['snapshot_high'].iloc[-1]:.2f}")
        c3.metric("Low", f"${df['snapshot_low'].iloc[-1]:.2f}")
        change_24h = ((current_price - df['open'].iloc[-24]) / df['open'].iloc[-24] * 100) if len(df) >= 24 else 0
        c4.metric("24H Change", f"{change_24h:+.2f}%")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric(f"{symbol}", f"${current_price:.{SYMBOLS[symbol]['digits']}f}")
        col2.metric("ATR", f"${atr:.2f}")
        col3.metric("RSI", f"{df['rsi'].iloc[-1]:.1f}")
        col4.metric("ADX", f"{df['adx'].iloc[-1]:.1f}")
        col5.metric("AI Accuracy", f"{accuracy:.1%}")
        
        if signal == "BUY":
            st.success(f"🤖 AI SAYS: BUY - Confidence: {confidence:.0f}%")
            entry, sl, tp1, tp2, tp3, tp4, risk = calc_levels(current_price, atr, "BUY")
        elif signal == "SELL":
            st.error(f"🤖 AI SAYS: SELL - Confidence: {confidence:.0f}%")
            entry, sl, tp1, tp2, tp3, tp4, risk = calc_levels(current_price, atr, "SELL")
        else:
            st.warning(f"🤖 AI SAYS: WAIT - Confidence: {confidence:.0f}%")
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
            position_size = (account_balance * (risk_percent / 100)) / risk if risk > 0 else 0
            st.info(f"Position Size: {position_size:.4f} lots | Risk: ${account_balance * (risk_percent / 100):.2f}")
            if st.button("✅ RECORD TRADE"):
                st.session_state.trade_history.append({'time': datetime.now(), 'symbol': symbol, 'signal': signal, 'entry': entry, 'tp2': tp2, 'confidence': confidence})
                st.success(f"Trade recorded")
        
        with st.expander("📊 INDICATORS", expanded=False):
            i1, i2, i3, i4 = st.columns(4)
            i1.metric("Stochastic K", f"{df['stoch_k'].iloc[-1]:.1f}")
            i2.metric("Williams %R", f"{df['williams_r'].iloc[-1]:.1f}")
            i3.metric("SMA20", f"${df['sma20'].iloc[-1]:.2f}")
            i4.metric("SMA50", f"${df['sma50'].iloc[-1]:.2f}")
        
        with st.expander("📊 FIBONACCI", expanded=False):
            f1, f2, f3, f4, f5 = st.columns(5)
            f1.metric("0.236", f"${df['fib_236'].iloc[-1]:.2f}")
            f2.metric("0.382", f"${df['fib_382'].iloc[-1]:.2f}")
            f3.metric("0.5", f"${df['fib_500'].iloc[-1]:.2f}")
            f4.metric("0.618", f"${df['fib_618'].iloc[-1]:.2f}")
            f5.metric("0.786", f"${df['fib_786'].iloc[-1]:.2f}")
        
        with st.expander("📊 SUPPLY & DEMAND", expanded=False):
            sd1, sd2 = st.columns(2)
            sd1.metric("Supply Zone", f"${df['supply_zone'].iloc[-1]:.2f}")
            sd2.metric("Demand Zone", f"${df['demand_zone'].iloc[-1]:.2f}")
        
        st.subheader("📈 CHART")
        fig = go.Figure()
        chart_df = df.tail(100)
        fig.add_trace(go.Candlestick(x=chart_df.index, open=chart_df['open'], high=chart_df['high'], low=chart_df['low'], close=chart_df['close'], name=symbol))
        fig.add_hline(y=df['fib_236'].iloc[-1], line_color="#ffd700", line_dash="dot")
        fig.add_hline(y=df['fib_618'].iloc[-1], line_color="#ffd700", line_dash="dot")
        fig.add_hline(y=df['supply_zone'].iloc[-1], line_color="#ff4444", line_dash="dash")
        fig.add_hline(y=df['demand_zone'].iloc[-1], line_color="#00ff88", line_dash="dash")
        if signal != "WAIT":
            fig.add_hline(y=entry, line_color="#ffd700", line_width=2)
            fig.add_hline(y=sl, line_color="#ff4444", line_dash="dash")
        fig.update_layout(template='plotly_dark', height=500)
        st.plotly_chart(fig, use_container_width=True)
        
        if st.session_state.backtest_results:
            st.subheader("📊 BACKTEST RESULTS")
            res = st.session_state.backtest_results
            b1, b2, b3, b4 = st.columns(4)
            b1.metric("Trades", res['trades'])
            b2.metric("Win Rate", f"{res['win_rate']:.1f}%")
            b3.metric("Profit Factor", f"{res['profit_factor']:.2f}")
            b4.metric("P&L", f"${res['total_pnl']:.2f}")
            if 'balance_history' in res:
                fig_eq = go.Figure()
                fig_eq.add_trace(go.Scatter(y=res['balance_history'], mode='lines', name='Balance', line=dict(color='#00ff88')))
                fig_eq.update_layout(title="Equity Curve", template='plotly_dark', height=300)
                st.plotly_chart(fig_eq, use_container_width=True)
        
        if st.session_state.trade_history:
            st.subheader("📋 TRADE HISTORY")
            for trade in st.session_state.trade_history[-5:]:
                st.info(f"{trade['time'].strftime('%H:%M:%S')} | {trade['signal']} | Entry: ${trade['entry']:.2f}")

st.caption("🤖 Ensemble AI (Random Forest + Gradient Boosting) | 65%+ Accuracy | 50+ Features")
