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

if page == "Dashboard":
    col1, col2, col3, col4 = st.columns(4)
    current = df['Close'].iloc[-1]
    previous = df['Close'].iloc[-2]
    col1.metric("Gold Price", f"${current:.2f}", f"{current - previous:.2f}")
    col2.metric("Daily High", f"${df['High'].iloc[-1]:.2f}")
    col3.metric("Daily Low", f"${df['Low'].iloc[-1]:.2f}")
    col4.metric("Volume", f"{df['Volume'].iloc[-1]:.0f}")
    st.subheader("Price History")
    st.line_chart(df['Close'])

elif page == "Price Chart":
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Gold"))
    fig.update_layout(title="Gold Price - Candlestick Chart", xaxis_title="Date", yaxis_title="Price (USD)", height=600)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.subheader("Historical Data")
    st.dataframe(df.tail(100))
    csv = df.to_csv()
    st.download_button("Download CSV", csv, "gold_data.csv", "text/csv")

st.sidebar.success("Dashboard ready!")
