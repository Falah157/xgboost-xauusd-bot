import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
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
    # Get values as simple numbers
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
    st.line_chart(df['Close'])

elif page == "Price Chart":
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index, 
        open=df['Open'], 
        high=df['High'], 
        low=df['Low'], 
        close=df['Close'], 
        name="Gold"
    ))
    fig.update_layout(height=600, title="Gold Price Chart")
    st.plotly_chart(fig, use_container_width=True)

else:
    st.subheader("Historical Data")
    st.dataframe(df.tail(100))
    csv = df.to_csv()
    st.download_button("Download CSV", csv, "gold_data.csv")

st.sidebar.success("Ready!")
