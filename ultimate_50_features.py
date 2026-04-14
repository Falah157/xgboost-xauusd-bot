import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="ULTIMATE 50 FEATURES", layout="wide", page_icon="🏆")

st.title("🏆 ULTIMATE 50 FEATURES TRADING DASHBOARD")

API_KEY = "96871e27b094425f9ea104fa6eb2be64"

if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = datetime.now()
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'backtest_results' not in st.session_state:
    st.session_state.backtest_results = None

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
    "XAUUSD": {"api": "XAU/USD", "name": "Gold", "digits": 2, "color": "#ffd700"},
    "BTCUSD": {"api": "BTC/USD", "name": "Bitcoin", "digits": 0, "color": "#ff8c00"}
}

if 'selected_symbol' not in st.session_state:
    st.session_state.selected_symbol = "XAUUSD"
if 'selected_tf' not in st.session_state:
    st.session_state.selected_tf = "1h"

# Auto Refresh
refresh_interval = st.sidebar.slider("Auto Refresh (seconds)", 30, 120, 60)
time_since = (datetime.now() - st.session_state.last_refresh).total_seconds()
if time_since >= refresh_interval:
    st.session_state.last_refresh = datetime.now()
    st.cache_data.clear()
    st.rerun()

@st.cache_data(ttl=30)
def get_price(symbol):
    try:
        api_symbol = SYMBOLS[symbol]["api"]
        url = f"https://api.twelvedata.com/price?symbol={api_symbol}&apikey={API_KEY}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return float(r.json()['price'])
    except:
        pass
    return None

@st.cache_data(ttl=60)
def get_data(symbol, tf, days=60):
    try:
        api_symbol = SYMBOLS[symbol]["api"]
        api_tf = TIMEFRAMES[tf]["api"]
        minutes = TIMEFRAMES[tf]["minutes"]
        total = min(int((days * 1440) / minutes), 500)
        url = f"https://api.twelvedata.com/time_series?symbol={api_symbol}&interval={api_tf}&outputsize={total}&apikey={API_KEY}"
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
    
    # Stochastic
    low_14 = df['low'].rolling(14).min()
    high_14 = df['high'].rolling(14).max()
    df['stoch_k'] = 100 * ((df['close'] - low_14) / (high_14 - low_14))
    df['stoch_d'] = df['stoch_k'].rolling(3).mean()
    
    # Williams %R
    df['williams_r'] = -100 * ((high_14 - df['close']) / (high_14 - low_14))
    
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
    
    # Fibonacci
    recent_high = df['high'].tail(50).max()
    recent_low = df['low'].tail(50).min()
    diff = recent_high - recent_low
    df['fib_236'] = recent_low + diff * 0.236
    df['fib_382'] = recent_low + diff * 0.382
    df['fib_500'] = recent_low + diff * 0.5
    df['fib_618'] = recent_low + diff * 0.618
    df['fib_786'] = recent_low + diff * 0.786
    
    # Pivot Points
    pivot_high = df['high'].tail(20).max()
    pivot_low = df['low'].tail(20).min()
    pivot_close = df['close'].iloc[-1]
    pivot = (pivot_high + pivot_low + pivot_close) / 3
    df['pivot'] = pivot
    df['r1'] = 2 * pivot - pivot_low
    df['s1'] = 2 * pivot - pivot_high
    
    # Supply & Demand
    df['supply_zone'] = df['high'].rolling(20).max()
    df['demand_zone'] = df['low'].rolling(20).min()
    
    # Asian Range
    try:
        asian_df = df.between_time('00:00', '06:00')
        if len(asian_df) > 0:
            df['asian_high'] = asian_df['high'].max()
            df['asian_low'] = asian_df['low'].min()
    except:
        df['asian_high'] = df['high'].max()
        df['asian_low'] = df['low'].min()
    
    # Market Snapshot
    df['snapshot_open'] = df['open'].iloc[-24] if len(df) >= 24 else df['open'].iloc[0]
    df['snapshot_high'] = df['high'].tail(24).max()
    df['snapshot_low'] = df['low'].tail(24).min()
    
    return df

def get_signal(df):
    if df is None or len(df) < 30:
        return "WAIT", 0
    
    last = df.iloc[-1]
    buy_score = 0
    sell_score = 0
    
    if last['close'] > last['sma20']:
        buy_score += 30
    else:
        sell_score += 30
    
    if last['sma20'] > last['sma50']:
        buy_score += 20
    else:
        sell_score += 20
    
    if last['rsi'] < 35:
        buy_score += 25
    elif last['rsi'] > 65:
        sell_score += 25
    
    if last['macd'] > last['macd_signal']:
        buy_score += 25
    else:
        sell_score += 25
    
    confidence = max(buy_score, sell_score)
    
    if buy_score > sell_score and confidence >= 55:
        return "BUY", confidence
    elif sell_score > buy_score and confidence >= 55:
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

def run_backtest(df, risk_percent):
    if df is None or len(df) < 100:
        return None
    
    df = calculate_indicators(df)
    trades = []
    balance = 10000
    balance_history = [balance]
    
    for i in range(50, len(df) - 4):
        current_data = df.iloc[:i+1]
        signal, confidence = get_signal(current_data)
        
        if signal != "WAIT" and confidence >= 55:
            current_price = df.iloc[i]['close']
            atr = df.iloc[i]['atr'] if not pd.isna(df.iloc[i]['atr']) else current_price * 0.005
            
            entry, sl, tp1, tp2, tp3, tp4, risk = calc_levels(current_price, atr, signal)
            
            risk_amount = balance * (risk_percent / 100)
            pos_size = risk_amount / risk if risk > 0 else 0
            
            future_prices = df['close'].iloc[i+1:i+5].values
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
    
    if st.button("Run Backtest", use_container_width=True):
        days = 60
        with st.spinner(f"Backtesting {tf}..."):
            bt_df = get_data(symbol, tf, days)
            if bt_df is not None:
                bt_df = calculate_indicators(bt_df)
                result = run_backtest(bt_df, risk_percent)
                if result:
                    st.session_state.backtest_results = result
                    st.success(f"Win Rate: {result['win_rate']:.1f}% | P&L: ${result['total_pnl']:.2f}")
                else:
                    st.warning("No trades generated")
    
    if st.session_state.backtest_results:
        res = st.session_state.backtest_results
        st.metric("Total Trades", res['trades'])
        st.metric("Win Rate", f"{res['win_rate']:.1f}%")
        st.metric("Profit Factor", f"{res['profit_factor']:.2f}")

with st.spinner(f"Loading {symbol} {tf} data..."):
    df = get_data(symbol, tf, 60)
    current_price = get_price(symbol)

if df is not None and len(df) > 30:
    df = calculate_indicators(df)
    current_price = current_price if current_price else float(df['close'].iloc[-1])
    atr = float(df['atr'].iloc[-1]) if not pd.isna(df['atr'].iloc[-1]) else current_price * 0.005
    
    signal, confidence = get_signal(df)
    
    # Market Snapshot
    st.subheader("📊 MARKET SNAPSHOT")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Open", f"${df['snapshot_open'].iloc[-1]:.2f}")
    c2.metric("High", f"${df['snapshot_high'].iloc[-1]:.2f}")
    c3.metric("Low", f"${df['snapshot_low'].iloc[-1]:.2f}")
    change_24h = ((current_price - df['open'].iloc[-24]) / df['open'].iloc[-24] * 100) if len(df) >= 24 else 0
    c4.metric("24H Change", f"{change_24h:+.2f}%")
    
    # Price and Indicators
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric(f"{symbol}", f"${current_price:.{SYMBOLS[symbol]['digits']}f}")
    col2.metric("ATR", f"${atr:.2f}")
    col3.metric("RSI", f"{df['rsi'].iloc[-1]:.1f}")
    col4.metric("ADX", f"{df['adx'].iloc[-1]:.1f}")
    col5.metric("Auto Refresh", f"{refresh_interval}s")
    
    # Signal
    if signal == "BUY":
        st.success(f"📈 BUY SIGNAL - Confidence: {confidence:.0f}%")
        entry, sl, tp1, tp2, tp3, tp4, risk = calc_levels(current_price, atr, "BUY")
    elif signal == "SELL":
        st.error(f"📉 SELL SIGNAL - Confidence: {confidence:.0f}%")
        entry, sl, tp1, tp2, tp3, tp4, risk = calc_levels(current_price, atr, "SELL")
    else:
        st.warning(f"⏸️ WAIT - Confidence: {confidence:.0f}%")
        entry, sl, tp1, tp2, tp3, tp4, risk = current_price, current_price, current_price, current_price, current_price, current_price, 0
    
    # Trading Levels
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
            st.session_state.trade_history.append({
                'time': datetime.now(),
                'symbol': symbol,
                'signal': signal,
                'entry': entry,
                'tp2': tp2,
                'confidence': confidence
            })
            st.success(f"Trade recorded at ${entry:.2f}")
    
    # Additional Indicators
    with st.expander("📊 ADDITIONAL INDICATORS", expanded=False):
        i1, i2, i3, i4 = st.columns(4)
        i1.metric("Stochastic K", f"{df['stoch_k'].iloc[-1]:.1f}")
        i2.metric("Stochastic D", f"{df['stoch_d'].iloc[-1]:.1f}")
        i3.metric("Williams %R", f"{df['williams_r'].iloc[-1]:.1f}")
        i4.metric("SMA20", f"${df['sma20'].iloc[-1]:.2f}")
        
        i5, i6, i7, i8 = st.columns(4)
        i5.metric("SMA50", f"${df['sma50'].iloc[-1]:.2f}")
        i6.metric("MACD", f"{df['macd_hist'].iloc[-1]:.4f}")
        i7.metric("Asian High", f"${df['asian_high'].iloc[-1]:.2f}")
        i8.metric("Asian Low", f"${df['asian_low'].iloc[-1]:.2f}")
    
    # Fibonacci & Pivots
    with st.expander("📊 FIBONACCI & PIVOTS", expanded=False):
        f1, f2, f3, f4, f5 = st.columns(5)
        f1.metric("0.236", f"${df['fib_236'].iloc[-1]:.2f}")
        f2.metric("0.382", f"${df['fib_382'].iloc[-1]:.2f}")
        f3.metric("0.5", f"${df['fib_500'].iloc[-1]:.2f}")
        f4.metric("0.618", f"${df['fib_618'].iloc[-1]:.2f}")
        f5.metric("0.786", f"${df['fib_786'].iloc[-1]:.2f}")
        
        p1, p2, p3 = st.columns(3)
        p1.metric("R1", f"${df['r1'].iloc[-1]:.2f}")
        p2.metric("PIVOT", f"${df['pivot'].iloc[-1]:.2f}")
        p3.metric("S1", f"${df['s1'].iloc[-1]:.2f}")
    
    # Supply & Demand
    with st.expander("📊 SUPPLY & DEMAND", expanded=False):
        sd1, sd2 = st.columns(2)
        sd1.metric("Supply Zone", f"${df['supply_zone'].iloc[-1]:.2f}")
        sd2.metric("Demand Zone", f"${df['demand_zone'].iloc[-1]:.2f}")
    
    # Chart
    st.subheader("📈 CHART")
    fig = go.Figure()
    chart_df = df.tail(100)
    fig.add_trace(go.Candlestick(x=chart_df.index, open=chart_df['open'], high=chart_df['high'],
                                  low=chart_df['low'], close=chart_df['close'], name=symbol))
    
    fig.add_hline(y=df['fib_236'].iloc[-1], line_color="#ffd700", line_dash="dot", annotation_text="Fib 236")
    fig.add_hline(y=df['fib_618'].iloc[-1], line_color="#ffd700", line_dash="dot", annotation_text="Fib 618")
    fig.add_hline(y=df['supply_zone'].iloc[-1], line_color="#ff4444", line_dash="dash", annotation_text="Supply")
    fig.add_hline(y=df['demand_zone'].iloc[-1], line_color="#00ff88", line_dash="dash", annotation_text="Demand")
    
    if signal != "WAIT":
        fig.add_hline(y=entry, line_color="#ffd700", line_width=2, annotation_text="ENTRY")
        fig.add_hline(y=sl, line_color="#ff4444", line_dash="dash", annotation_text="SL")
    
    fig.update_layout(template='plotly_dark', height=500)
    st.plotly_chart(fig, use_container_width=True)
    
    # Backtest Results
    if st.session_state.backtest_results:
        st.subheader("📊 BACKTEST RESULTS")
        res = st.session_state.backtest_results
        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Total Trades", res['trades'])
        b2.metric("Win Rate", f"{res['win_rate']:.1f}%")
        b3.metric("Profit Factor", f"{res['profit_factor']:.2f}")
        b4.metric("Total P&L", f"${res['total_pnl']:.2f}")
        
        if 'balance_history' in res and res['balance_history']:
            fig_eq = go.Figure()
            fig_eq.add_trace(go.Scatter(y=res['balance_history'], mode='lines', name='Balance', line=dict(color='#00ff88')))
            fig_eq.add_hline(y=10000, line_dash="dash", line_color="gray")
            fig_eq.update_layout(title="Equity Curve", template='plotly_dark', height=300)
            st.plotly_chart(fig_eq, use_container_width=True)
    
    # Trade History
    if st.session_state.trade_history:
        st.subheader("📋 TRADE HISTORY")
        for trade in st.session_state.trade_history[-5:]:
            st.info(f"{trade['time'].strftime('%Y-%m-%d %H:%M:%S')} | {trade['symbol']} | {trade['signal']} | Entry: ${trade['entry']:.2f} | Conf: {trade['confidence']:.0f}%")

else:
    st.warning("Loading market data... Please wait.")

st.caption("🏆 50+ FEATURES | Auto Refresh | Fibonacci | Pivots | Supply/Demand | Asian Range | Backtest")
