import streamlit as st
import pandas as pd
import numpy as np
import requests
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="VISUAL XAUUSD Trading System", layout="wide")
st.title("🏆 VISUAL XAUUSD TRADING SYSTEM - Chart with Entry, SL, TP1-TP4")

API_KEY = "96871e27b094425f9ea104fa6eb2be64"

if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []

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
def get_historical_data(days=30):
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

def calculate_indicators(df):
    df = df.copy()
    df['SMA_20'] = df['Close'].rolling(20).mean()
    df['SMA_50'] = df['Close'].rolling(50).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    df['EMA_12'] = df['Close'].ewm(span=12).mean()
    df['EMA_26'] = df['Close'].ewm(span=26).mean()
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    df['H-L'] = df['High'] - df['Low']
    df['H-PC'] = abs(df['High'] - df['Close'].shift())
    df['L-PC'] = abs(df['Low'] - df['Close'].shift())
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    df['ATR'] = df['TR'].rolling(14).mean()
    
    return df

def train_ai_model(df):
    features = ['RSI', 'MACD_Hist', 'ATR', 'SMA_20', 'SMA_50']
    df_clean = df.dropna()
    
    if len(df_clean) < 100:
        return None, None, None
    
    df_clean['Target'] = (df_clean['Close'].shift(-4) > df_clean['Close']).astype(int)
    df_clean = df_clean.dropna()
    
    X = df_clean[features].values
    y = df_clean['Target'].values
    
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
    if model is None or scaler is None:
        return None, 0
    features_scaled = scaler.transform(latest_features)
    proba = model.predict_proba(features_scaled)[0]
    prediction = model.predict(features_scaled)[0]
    confidence = max(proba)
    return prediction, confidence

def calculate_tp_levels(price, atr, direction):
    if direction == "LONG":
        tp1 = price + (atr * 1.5)
        tp2 = price + (atr * 2.0)
        tp3 = price + (atr * 3.0)
        tp4 = price + (atr * 4.0)
    else:
        tp1 = price - (atr * 1.5)
        tp2 = price - (atr * 2.0)
        tp3 = price - (atr * 3.0)
        tp4 = price - (atr * 4.0)
    return tp1, tp2, tp3, tp4

def create_visual_chart(df, current_price, entry, sl, tp1, tp2, tp3, tp4, direction):
    """Create a beautiful chart showing Entry, SL, and all TP levels"""
    
    fig, ax = plt.subplots(figsize=(14, 7))
    
    # Plot price data
    recent_df = df.tail(50)
    ax.plot(recent_df.index, recent_df['Close'], color='gold', linewidth=2, label='XAUUSD Price')
    
    # Color the background based on direction
    if direction == "LONG":
        bg_color = '#e8f5e9'  # Light green
        entry_color = 'green'
        tp_color = 'darkgreen'
    else:
        bg_color = '#ffebee'  # Light red
        entry_color = 'red'
        tp_color = 'darkred'
    
    ax.set_facecolor(bg_color)
    fig.patch.set_facecolor(bg_color)
    
    # Add horizontal lines for all levels
    # Entry line
    ax.axhline(y=entry, color=entry_color, linestyle='-', linewidth=2.5, 
               label=f'📍 ENTRY: ${entry:.2f}', alpha=0.9)
    
    # Stop Loss line
    ax.axhline(y=sl, color='red', linestyle='--', linewidth=2, 
               label=f'🛑 STOP LOSS: ${sl:.2f}', alpha=0.8)
    
    # TP lines with different styles
    ax.axhline(y=tp1, color=tp_color, linestyle=':', linewidth=1.5, 
               label=f'🎯 TP1 (1.5R): ${tp1:.2f}', alpha=0.7)
    ax.axhline(y=tp2, color=tp_color, linestyle=':', linewidth=1.5, 
               label=f'🎯 TP2 (2R): ${tp2:.2f}', alpha=0.7)
    ax.axhline(y=tp3, color=tp_color, linestyle=':', linewidth=1.5, 
               label=f'🎯 TP3 (3R): ${tp3:.2f}', alpha=0.7)
    ax.axhline(y=tp4, color=tp_color, linestyle=':', linewidth=1.5, 
               label=f'🎯 TP4 (4R): ${tp4:.2f}', alpha=0.7)
    
    # Add current price line
    ax.axhline(y=current_price, color='blue', linestyle='-', linewidth=1.5, 
               label=f'💰 CURRENT: ${current_price:.2f}', alpha=0.6)
    
    # Fill zones between levels
    if direction == "LONG":
        # Profit zone (above entry to TP4)
        ax.fill_between(recent_df.index, entry, tp4, alpha=0.1, color='green', label='Profit Zone')
        # Loss zone (below entry to SL)
        ax.fill_between(recent_df.index, sl, entry, alpha=0.1, color='red', label='Loss Zone')
    else:
        # Profit zone (below entry to TP4)
        ax.fill_between(recent_df.index, tp4, entry, alpha=0.1, color='green', label='Profit Zone')
        # Loss zone (above entry to SL)
        ax.fill_between(recent_df.index, entry, sl, alpha=0.1, color='red', label='Loss Zone')
    
    # Customize chart
    ax.set_title(f'{direction} TRADE SETUP - Entry, SL, and TP Levels', fontsize=14, fontweight='bold')
    ax.set_xlabel('Date/Time')
    ax.set_ylabel('Price (USD)')
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    
    # Add risk:reward text box
    risk = abs(entry - sl)
    reward1 = abs(tp1 - entry)
    reward2 = abs(tp2 - entry)
    reward3 = abs(tp3 - entry)
    reward4 = abs(tp4 - entry)
    
    textstr = f'Risk: ${risk:.2f}\nR:R Ratios:\nTP1: 1:{reward1/risk:.1f}\nTP2: 1:{reward2/risk:.1f}\nTP3: 1:{reward3/risk:.1f}\nTP4: 1:{reward4/risk:.1f}'
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.8)
    ax.text(0.02, 0.98, textstr, transform=ax.transAxes, fontsize=9,
            verticalalignment='top', bbox=props)
    
    plt.tight_layout()
    return fig

# Load data
with st.spinner("Loading XAUUSD data & training AI..."):
    df = get_historical_data(30)
    if df is not None:
        df = calculate_indicators(df)
        model, scaler, val_accuracy = train_ai_model(df)
        current_price = get_realtime_price()
        if current_price is None:
            current_price = float(df['Close'].iloc[-1])
        atr = float(df['ATR'].iloc[-1])
        rsi = float(df['RSI'].iloc[-1])

# Main display
col1, col2, col3, col4 = st.columns(4)
col1.metric("XAUUSD", f"${current_price:.2f}")
col2.metric("ATR", f"${atr:.2f}")
col3.metric("RSI", f"{rsi:.1f}")
col4.metric("AI Accuracy", f"{val_accuracy:.1%}" if val_accuracy else "N/A")

# Get AI signal
features = ['RSI', 'MACD_Hist', 'ATR', 'SMA_20', 'SMA_50']
latest_features = df[features].iloc[-1:].values
prediction, confidence = get_ai_signal(model, scaler, latest_features)

# Display signal
if prediction == 1:
    st.success(f"📈 **BULLISH SIGNAL** with {confidence:.1%} confidence")
    direction = "LONG"
else:
    st.error(f"📉 **BEARISH SIGNAL** with {confidence:.1%} confidence")
    direction = "SHORT"

# Calculate levels
sl_mult = 1.0
if direction == "LONG":
    entry = current_price
    stop_loss = entry - (atr * sl_mult)
    tp1, tp2, tp3, tp4 = calculate_tp_levels(entry, atr, "LONG")
else:
    entry = current_price
    stop_loss = entry + (atr * sl_mult)
    tp1, tp2, tp3, tp4 = calculate_tp_levels(entry, atr, "SHORT")

# Display levels in table format
st.subheader("📊 TRADING LEVELS")

level_cols = st.columns(6)
level_cols[0].metric("📍 ENTRY", f"${entry:.2f}")
level_cols[1].metric("🛑 STOP LOSS", f"${stop_loss:.2f}", f"Risk: ${abs(entry-stop_loss):.2f}")
level_cols[2].metric("🎯 TP1 (1.5R)", f"${tp1:.2f}", f"+${abs(tp1-entry):.2f}")
level_cols[3].metric("🎯 TP2 (2R)", f"${tp2:.2f}", f"+${abs(tp2-entry):.2f}")
level_cols[4].metric("🎯 TP3 (3R)", f"${tp3:.2f}", f"+${abs(tp3-entry):.2f}")
level_cols[5].metric("🎯 TP4 (4R)", f"${tp4:.2f}", f"+${abs(tp4-entry):.2f}")

# ============ VISUAL CHART ============
st.subheader("📈 VISUAL CHART - Entry, SL, TP1, TP2, TP3, TP4")

# Create and display the chart
fig = create_visual_chart(df, current_price, entry, stop_loss, tp1, tp2, tp3, tp4, direction)
st.pyplot(fig)

# Position sizing
st.subheader("⚙️ POSITION SIZING")
col1, col2 = st.columns(2)
account_size = col1.number_input("Account Balance ($)", value=10000, step=1000)
risk_pct = col2.slider("Risk per trade (%)", 0.5, 3.0, 1.0)

risk_amount = account_size * (risk_pct / 100)
position_size = risk_amount / abs(entry - stop_loss)

col1, col2 = st.columns(2)
col1.metric("Position Size", f"{position_size:.4f} lots")
col2.metric("Risk Amount", f"${risk_amount:.2f}")

# Execute button
if st.button("✅ EXECUTE THIS TRADE", type="primary"):
    st.session_state.trade_history.append({
        'date': datetime.now(),
        'direction': direction,
        'entry': entry,
        'sl': stop_loss,
        'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'tp4': tp4,
        'confidence': confidence,
        'price': current_price
    })
    st.success(f"✅ {direction} trade recorded at ${entry:.2f}")
    st.balloons()

# Show recent trades
if st.session_state.trade_history:
    st.subheader("📋 RECENT TRADES")
    for trade in st.session_state.trade_history[-5:]:
        st.text(f"{trade['date'].strftime('%H:%M:%S')} | {trade['direction']} | Entry: ${trade['entry']:.2f} | SL: ${trade['sl']:.2f} | TP1-4: ${trade['tp1']:.0f}/${trade['tp2']:.0f}/${trade['tp3']:.0f}/${trade['tp4']:.0f}")

st.sidebar.markdown("---")
st.sidebar.success("✅ VISUAL CHART ACTIVE")
st.sidebar.info("""
**Chart Features:**
- 📍 Green/Red line = Entry
- 🛑 Dashed red line = Stop Loss
- 🎯 Dotted lines = TP1, TP2, TP3, TP4
- 🟢 Green zone = Profit area
- 🔴 Red zone = Loss area
""")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.sidebar.warning("⚠️ Educational only - Not financial advice")

if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
