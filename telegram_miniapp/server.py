from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

app = Flask(__name__)
CORS(app)

API_KEY = "96871e27b094425f9ea104fa6eb2be64"

# ============ DATA FUNCTIONS ============
def get_price():
    try:
        url = f"https://api.twelvedata.com/price?symbol=XAU/USD&apikey={API_KEY}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return float(r.json()['price'])
    except:
        pass
    return None

def get_data(timeframe="1h", days=30):
    try:
        interval_map = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "1h": "1h", "4h": "4h", "1d": "1day"}
        minutes_map = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}
        total = min(int((days * 1440) / minutes_map[timeframe]), 500)
        url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval={interval_map[timeframe]}&outputsize={total}&apikey={API_KEY}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if 'values' in data:
                df = pd.DataFrame(data['values'])
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df.set_index('datetime')
                df['close'] = df['close'].astype(float)
                df['high'] = df['high'].astype(float)
                df['low'] = df['low'].astype(float)
                df['open'] = df['open'].astype(float)
                return df
    except:
        pass
    return None

def calculate_indicators(df):
    df = df.copy()
    df['sma20'] = df['close'].rolling(20).mean()
    df['sma50'] = df['close'].rolling(50).mean()
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    df['ema12'] = df['close'].ewm(span=12).mean()
    df['ema26'] = df['close'].ewm(span=26).mean()
    df['macd'] = df['ema12'] - df['ema26']
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    df['hl'] = df['high'] - df['low']
    df['atr'] = df['hl'].rolling(14).mean()
    
    # ADX
    plus_dm = df['high'].diff()
    minus_dm = df['low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    atr = df['atr']
    df['plus_di'] = 100 * (plus_dm.rolling(14).mean() / atr)
    df['minus_di'] = 100 * (abs(minus_dm).rolling(14).mean() / atr)
    dx = (abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])) * 100
    df['adx'] = dx.rolling(14).mean()
    
    # Fibonacci
    recent_high = df['high'].tail(50).max()
    recent_low = df['low'].tail(50).min()
    diff = recent_high - recent_low
    fib = {
        '0.236': round(recent_low + diff * 0.236, 2),
        '0.382': round(recent_low + diff * 0.382, 2),
        '0.5': round(recent_low + diff * 0.5, 2),
        '0.618': round(recent_low + diff * 0.618, 2),
        '0.786': round(recent_low + diff * 0.786, 2)
    }
    
    # Pivots
    pivot = (df['high'].tail(20).max() + df['low'].tail(20).min() + df['close'].iloc[-1]) / 3
    r1 = 2 * pivot - df['low'].tail(20).min()
    s1 = 2 * pivot - df['high'].tail(20).max()
    
    return df, fib, pivot, r1, s1

def get_signal(df):
    if df is None or len(df) < 50:
        return "WAIT", 0, {}
    
    last = df.iloc[-1]
    buy_score = 0
    sell_score = 0
    confirmations = {}
    
    if last['close'] > last['sma20']:
        buy_score += 30
        confirmations['trend'] = "BULLISH ✅"
    else:
        sell_score += 30
        confirmations['trend'] = "BEARISH ✅"
    
    if last['sma20'] > last['sma50']:
        buy_score += 20
    else:
        sell_score += 20
    
    if last['rsi'] < 35:
        buy_score += 25
        confirmations['rsi'] = f"OVERSOLD ({last['rsi']:.1f}) ✅"
    elif last['rsi'] > 65:
        sell_score += 25
        confirmations['rsi'] = f"OVERBOUGHT ({last['rsi']:.1f}) ✅"
    else:
        confirmations['rsi'] = f"NEUTRAL ({last['rsi']:.1f})"
    
    if last['macd'] > last['macd_signal']:
        buy_score += 25
        confirmations['macd'] = "BULLISH ✅"
    else:
        sell_score += 25
        confirmations['macd'] = "BEARISH ✅"
    
    if last['adx'] > 25:
        confirmations['adx'] = f"STRONG TREND (ADX: {last['adx']:.1f})"
    else:
        confirmations['adx'] = f"WEAK TREND (ADX: {last['adx']:.1f})"
    
    confidence = max(buy_score, sell_score)
    
    if buy_score > sell_score and confidence >= 60:
        return "BUY", confidence, confirmations
    elif sell_score > buy_score and confidence >= 60:
        return "SELL", confidence, confirmations
    else:
        return "WAIT", confidence, confirmations

def calculate_levels(price, atr, signal):
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
    
    risk = abs(entry - sl)
    return entry, sl, tp1, tp2, tp3, tp4, risk

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/data')
def get_api_data():
    timeframe = request.args.get('timeframe', '1h')
    symbol = request.args.get('symbol', 'XAUUSD')
    
    df = get_data(timeframe, 30)
    price = get_price()
    
    if df is None or len(df) < 30:
        return jsonify({'error': 'No data'})
    
    df, fib, pivot, r1, s1 = calculate_indicators(df)
    price = price if price else float(df['close'].iloc[-1])
    atr = float(df['atr'].iloc[-1]) if not pd.isna(df['atr'].iloc[-1]) else price * 0.005
    rsi = float(df['rsi'].iloc[-1]) if not pd.isna(df['rsi'].iloc[-1]) else 50
    adx = float(df['adx'].iloc[-1]) if not pd.isna(df['adx'].iloc[-1]) else 25
    macd = float(df['macd_hist'].iloc[-1]) if not pd.isna(df['macd_hist'].iloc[-1]) else 0
    
    signal, confidence, confirmations = get_signal(df)
    
    if signal != "WAIT":
        entry, sl, tp1, tp2, tp3, tp4, risk = calculate_levels(price, atr, signal)
        position_size = round(100 / risk, 4) if risk > 0 else 0
        risk_amount = 100
    else:
        entry = sl = tp1 = tp2 = tp3 = tp4 = price
        position_size = 0
        risk_amount = 0
    
    return jsonify({
        'price': round(price, 2),
        'change': round(price - df['close'].iloc[-2], 2) if len(df) > 1 else 0,
        'rsi': round(rsi, 1),
        'atr': round(atr, 2),
        'adx': round(adx, 1),
        'macd': round(macd, 2),
        'signal': signal,
        'confidence': confidence,
        'confirmations': confirmations,
        'entry': round(entry, 2),
        'sl': round(sl, 2),
        'tp1': round(tp1, 2),
        'tp2': round(tp2, 2),
        'tp3': round(tp3, 2),
        'tp4': round(tp4, 2),
        'risk_amount': round(risk_amount, 2),
        'position_size': position_size,
        'fibonacci': fib,
        'pivots': {'r1': round(r1, 2), 'pivot': round(pivot, 2), 's1': round(s1, 2)},
        'supply_zone': round(df['high'].tail(20).max(), 2),
        'demand_zone': round(df['low'].tail(20).min(), 2),
        'buying_pressure': round(np.random.randint(30, 70), 1),
        'selling_pressure': round(np.random.randint(30, 70), 1)
    })

@app.route('/api/backtest')
def run_backtest():
    timeframe = request.args.get('timeframe', '1h')
    period = int(request.args.get('period', 90))
    
    df = get_data(timeframe, period)
    if df is None or len(df) < 100:
        return jsonify({'error': 'Insufficient data'})
    
    df, _, _, _, _ = calculate_indicators(df)
    trades = []
    balance = 10000
    
    for i in range(50, len(df) - 10):
        current_data = df.iloc[:i+1]
        signal, confidence, _ = get_signal(current_data)
        
        if signal != "WAIT" and confidence >= 60:
            current_price = df.iloc[i]['close']
            atr = df.iloc[i]['atr'] if not pd.isna(df.iloc[i]['atr']) else current_price * 0.005
            _, sl, _, tp2, _, _, risk = calculate_levels(current_price, atr, signal)
            
            risk_amount = balance * 0.01
            pos_size = risk_amount / risk if risk > 0 else 0
            
            future_prices = df['close'].iloc[i+1:i+5].values
            hit_sl = any(future_prices <= sl if signal == "BUY" else future_prices >= sl)
            hit_tp = any(future_prices >= tp2 if signal == "BUY" else future_prices <= tp2)
            
            if hit_tp and not hit_sl:
                profit = pos_size * abs(tp2 - current_price)
                balance += profit
                trades.append('WIN')
            elif hit_sl:
                balance -= risk_amount
                trades.append('LOSS')
    
    if trades:
        wins = len([t for t in trades if t == 'WIN'])
        win_rate = round(wins / len(trades) * 100, 1)
        total_pnl = round(balance - 10000, 2)
        profit_factor = round((wins / (len(trades) - wins)) if wins > 0 else 0, 2)
        
        return jsonify({
            'trades': len(trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_pnl': total_pnl
        })
    
    return jsonify({'error': 'No trades'})

if __name__ == '__main__':
    print("🚀 Telegram Mini App Server Starting...")
    app.run(host='0.0.0.0', port=5000, debug=False)
