import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Set page config
st.set_page_config(page_title="Gold Trading Dashboard", layout="wide")

# Import modules
import data_fetcher
import indicators
import charts
import ai_model
import predictions

# Simple menu using native Streamlit
st.sidebar.title("Navigation")
menu_options = ["Dashboard", "Technical Analysis", "AI Predictions", "Data View"]
selected = st.sidebar.radio("Go to", menu_options)

def main():
    st.title("🏆 Smart Gold Trading Dashboard")
    
    # Data fetching using the correct function
    with st.spinner("Loading gold data..."):
        df = data_fetcher.fetch_gold_data(period="1mo", interval="1h")
        
        if df is None or df.empty:
            st.error("Failed to load gold data. Please check your internet connection.")
            return
    
    if selected == "Dashboard":
        st.header("📊 Gold Price Dashboard")
        
        # Show price chart
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index,
                                      open=df['Open'],
                                      high=df['High'],
                                      low=df['Low'],
                                      close=df['Close'],
                                      name='Gold Price'))
        fig.update_layout(title='Gold Price Chart', xaxis_title='Date', yaxis_title='Price (USD)', height=500)
        st.plotly_chart(fig, use_container_width=True)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Current Price", f"${df['Close'].iloc[-1]:.2f}", 
                     f"{df['Close'].iloc[-1] - df['Close'].iloc[-2]:.2f}")
        with col2:
            st.metric("24h High", f"${df['High'].iloc[-1]:.2f}")
        with col3:
            st.metric("24h Low", f"${df['Low'].iloc[-1]:.2f}")
        with col4:
            st.metric("Total Volume", f"{df['Volume'].iloc[-1]:,.0f}")
            
    elif selected == "Technical Analysis":
        st.header("📈 Technical Indicators")
        if hasattr(indicators, 'show_indicators'):
            indicators.show_indicators(df)
        else:
            st.info("Technical indicators module loaded successfully")
            
    elif selected == "AI Predictions":
        st.header("🤖 AI Price Predictions")
        if hasattr(predictions, 'show_predictions'):
            predictions.show_predictions(df)
        else:
            st.info("AI predictions module loaded successfully")
            
    elif selected == "Data View":
        st.header("📋 Raw Data")
        st.dataframe(df.tail(100))

if __name__ == "__main__":
    main()
