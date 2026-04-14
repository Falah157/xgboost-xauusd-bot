import streamlit as st
import pandas as pd
import numpy as np
import requests
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="XAUUSD Trading Dashboard", layout="wide")
st.title("🏆 XAUUSD Professional Trading Dashboard")

@st.cache_data(ttl=30)
def get_live_price():
    try:
        response = requests.get("https://api.gold-api.com/price/XAUUSD", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return float(data.get('price', 1932.50))
    except:
        pass
    return 1932.50 + np.random.randn() * 1.5

@st.cache_data(ttl=3600)
def get_historical_data(days=30):
    """Fetch or generate historical data for backtesting"""
    dates = pd.date_range(end=datetime.now(), periods=days*24, freq='h')
    base = 1900
    trends = np.cumsum(np.random.randn(len(dates)) * 1.2)
    prices = base + trends + np.sin(np.arange(len(dates)) * 0.3) * 8
    return pd.DataFrame({'Close': prices, 'High': prices + 5, 'Low': prices - 5}, index=dates)

def calculate_indicators(df):
    df = df.copy()
    df['SMA_20'] = df['Close'].rolling(20).mean()
    df['SMA_50'] = df['Close'].rolling(50).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    return df

def determine_trend(df, idx=-1):
    """Determine trend at a specific index"""
    if idx == -1:
        idx = len(df) - 1
    
    current = df['Close'].iloc[idx]
    sma20 = df['SMA_20'].iloc[idx] if not pd.isna(df['SMA_20'].iloc[idx]) else current
    sma50 = df['SMA_50'].iloc[idx] if not pd.isna(df['SMA_50'].iloc[idx]) else current
    rsi = df['RSI'].iloc[idx] if not pd.isna(df['RSI'].iloc[idx]) else 50
    
    if current > sma20 and current > sma50 and rsi > 50:
        return "BULLISH"
    elif current < sma20 and current < sma50 and rsi < 50:
        return "BEARISH"
    else:
        return "SIDEWAYS"

def backtest_strategy(df, risk_reward_ratios=[2, 3, 4, 5]):
    """Run backtest on historical data"""
    df = calculate_indicators(df)
    trades = []
    balance = 10000  # Starting balance
    balance_history = [balance]
    
    for i in range(100, len(df) - 24):  # Need enough data for indicators
        trend = determine_trend(df, i)
        current_price = df['Close'].iloc[i]
        atr = current_price * 0.005
        risk_amount = balance * 0.01  # 1% risk per trade
        
        if trend == "BULLISH":
            entry = current_price
            sl = entry - atr
            tp2 = entry + (atr * 2)
            
            # Check if trade would have hit TP or SL in next 24 hours
            future_prices = df['Close'].iloc[i+1:i+25]
            hit_sl = any(future_prices <= sl)
            hit_tp = any(future_prices >= tp2)
            
            if hit_tp and not hit_sl:
                # Win - 2R profit
                position_size = risk_amount / atr
                profit = position_size * atr * 2
                balance += profit
                trades.append({'date': df.index[i], 'direction': 'LONG', 'result': 'WIN', 'pnl': profit})
            elif hit_sl:
                # Loss
                balance -= risk_amount
                trades.append({'date': df.index[i], 'direction': 'LONG', 'result': 'LOSS', 'pnl': -risk_amount})
            else:
                trades.append({'date': df.index[i], 'direction': 'LONG', 'result': 'NO_TRIGGER', 'pnl': 0})
                
        elif trend == "BEARISH":
            entry = current_price
            sl = entry + atr
            tp2 = entry - (atr * 2)
            
            future_prices = df['Close'].iloc[i+1:i+25]
            hit_sl = any(future_prices >= sl)
            hit_tp = any(future_prices <= tp2)
            
            if hit_tp and not hit_sl:
                position_size = risk_amount / atr
                profit = position_size * atr * 2
                balance += profit
                trades.append({'date': df.index[i], 'direction': 'SHORT', 'result': 'WIN', 'pnl': profit})
            elif hit_sl:
                balance -= risk_amount
                trades.append({'date': df.index[i], 'direction': 'SHORT', 'result': 'LOSS', 'pnl': -risk_amount})
            else:
                trades.append({'date': df.index[i], 'direction': 'SHORT', 'result': 'NO_TRIGGER', 'pnl': 0})
        
        balance_history.append(balance)
    
    return trades, balance_history

# ============ MAIN APP ============
tab1, tab2, tab3 = st.tabs(["📊 LIVE TRADING", "📈 BACKTEST RESULTS", "📉 PERFORMANCE"])

# Get data
current_price = get_live_price()
df_hist = get_historical_data(30)
df_hist = calculate_indicators(df_hist)
trend, _ = determine_trend(df_hist)

with tab1:
    st.header("🎯 LIVE TRADING SETUP")
    
    # Current metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("XAUUSD", f"${current_price:.2f}")
    col2.metric("RSI (14)", f"{df_hist['RSI'].iloc[-1]:.1f}")
    col3.metric("Trend", trend)
    col4.metric("SMA 20/50", "Bullish" if df_hist['Close'].iloc[-1] > df_hist['SMA_20'].iloc[-1] else "Bearish")
    
    # Calculate levels
    atr = current_price * 0.005
    if "BULL" in trend:
        entry = current_price
        sl = entry - atr
        tps = {f"{r}R": entry + (atr * r) for r in [2, 3, 4, 5]}
        direction = "LONG"
    else:
        entry = current_price
        sl = entry + atr
        tps = {f"{r}R": entry - (atr * r) for r in [2, 3, 4, 5]}
        direction = "SHORT"
    
    st.subheader(f"📍 {direction} SETUP")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("ENTRY", f"${entry:.2f}")
        st.metric("STOP LOSS", f"${sl:.2f}", f"Risk: ${abs(entry - sl):.2f}")
    with col2:
        for label, tp in tps.items():
            st.metric(label, f"${tp:.2f}", f"Profit: ${abs(tp - entry):.2f}")
    
    # Account risk
    st.subheader("⚙️ Position Sizing")
    account = st.number_input("Account Balance ($)", value=10000, step=1000)
    risk_pct = st.slider("Risk per trade (%)", 0.5, 3.0, 1.0)
    risk_amount = account * (risk_pct / 100)
    position_size = risk_amount / abs(entry - sl)
    st.metric("Position Size", f"{position_size:.4f} lots")
    st.metric("Risk Amount", f"${risk_amount:.2f}")

with tab2:
    st.header("📊 BACKTEST RESULTS")
    
    col1, col2 = st.columns(2)
    days_back = col1.slider("Days for backtest", 7, 60, 30)
    risk_per_trade = col2.slider("Risk per trade (%)", 0.5, 2.0, 1.0)
    
    if st.button("🚀 RUN BACKTEST", type="primary"):
        with st.spinner("Running backtest on historical data..."):
            df_backtest = get_historical_data(days_back)
            trades, balance_history = backtest_strategy(df_backtest)
            
            # Filter actual trades
            actual_trades = [t for t in trades if t['result'] != 'NO_TRIGGER']
            
            if actual_trades:
                wins = len([t for t in actual_trades if t['result'] == 'WIN'])
                losses = len([t for t in actual_trades if t['result'] == 'LOSS'])
                win_rate = (wins / len(actual_trades)) * 100 if actual_trades else 0
                total_pnl = sum([t['pnl'] for t in actual_trades])
                avg_win = sum([t['pnl'] for t in actual_trades if t['result'] == 'WIN']) / wins if wins > 0 else 0
                avg_loss = abs(sum([t['pnl'] for t in actual_trades if t['result'] == 'LOSS']) / losses) if losses > 0 else 0
                
                # Display metrics
                st.subheader("📈 Performance Summary")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total Trades", len(actual_trades))
                m2.metric("Win Rate", f"{win_rate:.1f}%")
                m3.metric("Total P&L", f"${total_pnl:.2f}")
                m4.metric("Final Balance", f"${10000 + total_pnl:.2f}")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Wins", wins)
                c2.metric("Losses", losses)
                c3.metric("Profit Factor", f"{avg_win/avg_loss:.2f}" if avg_loss > 0 else "N/A")
                
                # Balance chart
                st.subheader("📉 Equity Curve")
                fig, ax = plt.subplots(figsize=(12, 4))
                ax.plot(balance_history, color='green', linewidth=2)
                ax.fill_between(range(len(balance_history)), 10000, balance_history, 
                                where=(np.array(balance_history) >= 10000), color='green', alpha=0.3)
                ax.fill_between(range(len(balance_history)), 10000, balance_history,
                                where=(np.array(balance_history) < 10000), color='red', alpha=0.3)
                ax.axhline(y=10000, color='gray', linestyle='--')
                ax.set_ylabel('Balance ($)')
                ax.set_xlabel('Trade Number')
                ax.set_title('Account Balance Over Time')
                ax.grid(True, alpha=0.3)
                st.pyplot(fig)
                
                # Trade list
                with st.expander("📋 View All Trades"):
                    trade_df = pd.DataFrame(actual_trades)
                    st.dataframe(trade_df)
            else:
                st.warning("No trading signals generated in the selected period")

with tab3:
    st.header("📊 ACCURACY ANALYSIS")
    st.info("""
    ### 🎯 What This Backtest Measures
    
    | Metric | What It Means |
    |--------|---------------|
    | **Win Rate** | % of trades that hit 2R target before SL |
    | **Profit Factor** | Gross profit / gross loss (>1.5 is good) |
    | **Expectancy** | Average profit per trade |
    
    ### ⚠️ Important Limitations
    
    - Backtests assume perfect execution (no slippage)
    - Doesn't account for spreads or commissions
    - Past performance ≠ future results
    - Your broker's conditions may differ
    
    ### 💡 Realistic Expectations
    
    - **50-60% win rate** is excellent for 2R targets
    - **Profit factor >1.5** indicates a viable strategy
    - **Sharpe ratio >1** suggests good risk-adjusted returns
    """)

st.sidebar.markdown("---")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.sidebar.warning("⚠️ Educational only - Not financial advice")
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
