import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Set page config
st.set_page_config(page_title="Gold Trading Dashboard", layout="wide")

# Simple menu using native Streamlit
st.sidebar.title("Navigation")
menu_options = ["Dashboard", "Technical Analysis", "AI Predictions", "Data View"]
selected = st.sidebar.radio("Go to", menu_options)

# Import other modules
import data_fetcher
import indicators
import charts
import ai_model
import predictions

def main():
    st.title("🏆 Smart Gold Trading Dashboard")
    
    # Data fetching
    with st.spinner("Loading gold data..."):
        df = data_fetcher.get_gold_data()
        if df is None or df.empty:
            st.error("Failed to load gold data. Please check your internet connection.")
            return
    
    if selected == "Dashboard":
        st.header("📊 Gold Price Dashboard")
        charts.show_price_chart(df)
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Current Price", f"${df['Close'].iloc[-1]:.2f}", 
                     f"{df['Close'].iloc[-1] - df['Close'].iloc[-2]:.2f}")
        with col2:
            st.metric("Daily High", f"${df['High'].iloc[-1]:.2f}")
        with col3:
            st.metric("Daily Low", f"${df['Low'].iloc[-1]:.2f}")
        with col4:
            st.metric("Volume", f"{df['Volume'].iloc[-1]:,.0f}")
            
    elif selected == "Technical Analysis":
        st.header("📈 Technical Indicators")
        indicators.show_indicators(df)
        
    elif selected == "AI Predictions":
        st.header("🤖 AI Price Predictions")
        predictions.show_predictions(df)
        
    elif selected == "Data View":
        st.header("📋 Raw Data")
        st.dataframe(df.tail(100))

if __name__ == "__main__":
    main()
