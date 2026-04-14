from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import requests
import pandas as pd
import numpy as np
from datetime import datetime

app = Flask(__name__)
CORS(app)

API_KEY = "96871e27b094425f9ea104fa6eb2be64"

def get_price():
    try:
        url = f"https://api.twelvedata.com/price?symbol=XAU/USD&apikey={API_KEY}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return float(r.json()['price'])
    except:
        pass
    return None

def get_historical():
    try:
        url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=1h&outputsize=100&apikey={API_KEY}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if 'values' in data:
                prices = [float(v['close']) for v in data['values']]
                return prices[::-1]
    except:
        pass
    return None

def get_indicators():
    try:
        url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=1h&outputsize=50&apikey={API_KEY}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if 'values' in data:
                df = pd.DataFrame(data['values'])
                df['close'] = df['close'].astype(float)
                df['high'] = df['high'].astype(float)
                df['low'] = df['low'].astype(float)
                
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                
                df['hl'] = df['high'] - df['low']
                atr = df['hl'].rolling(14).mean()
                
                sma20 = df['close'].rolling(20).mean()
                sma50 = df['close'].rolling(50).mean()
                
                return {
                    'price': float(df['close'].iloc[-1]),
                    'rsi': float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50,
                    'atr': float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0,
                    'sma20': float(sma20.iloc[-1]) if not pd.isna(sma20.iloc[-1]) else 0,
                    'sma50': float(sma50.iloc[-1]) if not pd.isna(sma50.iloc[-1]) else 0
                }
    except Exception as e:
        print(f"Error: {e}")
    return None

def get_signal(data):
    if not data:
        return "WAIT", 0
    
    price = data['price']
    sma20 = data['sma20']
    sma50 = data['sma50']
    rsi = data['rsi']
    
    bull = 0
    bear = 0
    
    if price > sma20:
        bull += 1
    else:
        bear += 1
    
    if sma20 > sma50:
        bull += 1
    else:
        bear += 1
    
    if rsi < 40:
        bull += 1
    elif rsi > 60:
        bear += 1
    
    confidence = max(bull, bear) * 33
    
    if bull >= 2:
        return "BUY", confidence
    elif bear >= 2:
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
    return entry, sl, tp1, tp2, tp3, tp4

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/api/data')
def get_data():
    data = get_indicators()
    if not data:
        return jsonify({'error': 'No data'})
    
    signal, confidence = get_signal(data)
    entry, sl, tp1, tp2, tp3, tp4 = calc_levels(data['price'], data['atr'], signal)
    
    prices = get_historical()
    
    return jsonify({
        'price': data['price'],
        'rsi': data['rsi'],
        'atr': data['atr'],
        'sma20': data['sma20'],
        'sma50': data['sma50'],
        'signal': signal,
        'confidence': confidence,
        'entry': entry,
        'sl': sl,
        'tp1': tp1,
        'tp2': tp2,
        'tp3': tp3,
        'tp4': tp4,
        'prices': prices if prices else [],
        'change': data['price'] - (prices[-2] if prices and len(prices) > 1 else data['price'])
    })

if __name__ == '__main__':
    print("🚀 Mini App Server Starting...")
    print("📍 Open http://localhost:5000 to test")
    app.run(host='0.0.0.0', port=5000, debug=False)
