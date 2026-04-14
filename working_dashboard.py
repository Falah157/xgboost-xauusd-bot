import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import yfinance as yf
from datetime import datetime

st.set_page_config(page_title="Gold Dashboard", layout="wide")
st.title("🏆 Smart Gold Trading Dashboard")

st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Dashboard", "Price Chart", "Data View"])

@st.cache_data
def load_data():
    data = yf.download("GC=F", period="2mo", interval="1d", progress=False)
    return data

with st.spinner("Loading gold data..."):
    df = load_data()

if df.empty:
    st.error("Failed to load data")
    st.stop()

if page == "Dashboard":
    current_price = round(float(df['Close'].values[-1]), 2)
    prev_price = round(float(df['Close'].values[-2]), 2) if len(df) > 1 else current_price
    high_price = round(float(df['High'].values[-1]), 2)
    low_price = round(float(df['Low'].values[-1]), 2)
    volume_val = int(df['Volume'].values[-1])
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Gold Price", f"${current_price}", f"{current_price - prev_price}")
    col2.metric("Daily High", f"${high_price}")
    col3.metric("Daily Low", f"${low_price}")
    col4.metric("Volume", f"{volume_val:,}")
    
    st.subheader("Price History")
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(df.index, df['Close'], color='gold', linewidth=2)
    ax.set_title('Gold Price History')
    ax.set_xlabel('Date')
    ax.set_ylabel('Price (USD)')
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    st.pyplot(fig)

elif page == "Price Chart":
    fig, ax = plt.subplots(figsize=(12, 6))
    
    dates = df.index.tolist()
    opens = df['Open'].values
    closes = df['Close'].values
    highs = df['High'].values
    lows = df['Low'].values
    
    for i in range(len(dates)):
        open_val = float(opens[i])
        close_val = float(closes[i])
        high_val = float(highs[i])
        low_val = float(lows[i])
        date_val = dates[i]
        
        color = 'green' if close_val >= open_val else 'red'
        ax.plot([date_val, date_val], [low_val, high_val], color=color, linewidth=1)
        ax.plot([date_val, date_val], [open_val, close_val], color=color, linewidth=4)
    
    ax.set_title('Gold Price - Candlestick Chart')
    ax.set_xlabel('Date')
    ax.set_ylabel('Price (USD)')
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    st.pyplot(fig)

else:
    st.subheader("Historical Data - Last 10 Days")
    
    # Convert to simple Python types
    last_10_data = []
    for i in range(min(10, len(df))):
        idx = len(df) - 10 + i if len(df) >= 10 else i
        row = df.iloc[idx]
        last_10_data.append({
            'Date': df.index[idx].strftime('%Y-%m-%d'),
            'Open': f"${float(row['Open']):.2f}",
            'High': f"${float(row['High']):.2f}",
            'Low': f"${float(row['Low']):.2f}",
            'Close': f"${float(row['Close']):.2f}",
            'Volume': f"{int(row['Volume']):,}"
        })
    
    # Display as simple text
    for item in last_10_data:
        st.text(f"{item['Date']} | Open: {item['Open']} | High: {item['High']} | Low: {item['Low']} | Close: {item['Close']} | Volume: {item['Volume']}")
    
    # CSV download
    csv = df.to_csv()
    st.download_button("Download Full CSV", csv, "gold_data.csv", "text/csv")

st.sidebar.success("Dashboard Ready!")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
