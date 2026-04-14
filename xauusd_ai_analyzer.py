import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="XAUUSD AI Analyzer", layout="wide")
st.title("🤖 XAUUSD Automated AI Analysis System")

@st.cache_data(ttl=300)
def get_live_data():
    gold = yf.download("GC=F", period="5d", interval="15m", progress=False)
    return gold

def calculate_indicators(df):
    df = df.copy()
    df['SMA_20'] = df['Close'].rolling(20).mean()
    df['SMA_50'] = df['Close'].rolling(50).mean()
    df['EMA_12'] = df['Close'].ewm(span=12).mean()
    df['EMA_26'] = df['Close'].ewm(span=26).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['Signal'] = df['MACD'].ewm(span=9).mean()
    df['Returns'] = df['Close'].pct_change()
    df['Volatility'] = df['Returns'].rolling(20).std()
    
    return df

with st.spinner("Fetching live XAUUSD data..."):
    df_raw = get_live_data()
    df = calculate_indicators(df_raw)

current = df['Close'].iloc[-1]
prev = df['Close'].iloc[-2]
change = current - prev

col1, col2, col3, col4 = st.columns(4)
col1.metric("XAUUSD", f"${current:.2f}", f"{change:+.2f}")
col2.metric("High", f"${df['High'].iloc[-1]:.2f}")
col3.metric("Low", f"${df['Low'].iloc[-1]:.2f}")
col4.metric("RSI", f"{df['RSI'].iloc[-1]:.1f}")

st.header("🤖 AI Prediction")
st.info("AI is analyzing XAUUSD patterns... (demo mode - add your API key for full AI)")

st.header("📊 Price Chart")
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df.index, df['Close'], color='gold', linewidth=2)
ax.set_title('XAUUSD Price')
ax.set_ylabel('USD')
ax.grid(True, alpha=0.3)
plt.xticks(rotation=45)
st.pyplot(fig)

st.caption("⚠️ Educational only - Not financial advice")
