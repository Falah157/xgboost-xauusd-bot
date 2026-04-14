#!/bin/bash
while true; do
    echo "🚀 Starting Trading Bot at $(date)"
    streamlit run auto_telegram_bot.py --server.port 8501
    echo "⚠️ Bot stopped at $(date). Restarting in 5 seconds..."
    sleep 5
done
