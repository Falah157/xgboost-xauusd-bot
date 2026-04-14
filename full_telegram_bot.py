from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import requests
import pandas as pd
import numpy as np
from datetime import datetime

# ============ CONFIGURATION ============
TOKEN = "8369393711:AAGm8ydfJc3UQPyNCPR6uCEr1LQpFw-zV-4"
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
                
                # RSI
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                
                # ATR
                df['hl'] = df['high'] - df['low']
                atr = df['hl'].rolling(14).mean()
                
                # SMA
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
        return "NO_DATA", 0
    
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

# ============ TELEGRAM HANDLERS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📈 SIGNAL", callback_data="signal"),
         InlineKeyboardButton("📊 ANALYSIS", callback_data="analysis")],
        [InlineKeyboardButton("💰 PRICE", callback_data="price"),
         InlineKeyboardButton("📋 LEVELS", callback_data="levels")],
        [InlineKeyboardButton("🔄 REFRESH", callback_data="refresh"),
         InlineKeyboardButton("❓ HELP", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🚀 *XAUUSD TRADING BOT*\n\n"
        "Welcome! Use the buttons below:\n\n"
        "📈 SIGNAL - Current trading signal\n"
        "📊 ANALYSIS - RSI, SMA, Trend\n"
        "💰 PRICE - Live XAUUSD price\n"
        "📋 LEVELS - Entry, SL, TP1-TP4\n\n"
        "⚡ Real-time data from live market!",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    
    data = get_indicators()
    if not data:
        msg = "❌ Failed to fetch data. Try again."
    else:
        signal, confidence = get_signal(data)
        
        if signal == "BUY":
            msg = f"📈 *BULLISH SIGNAL* 📈\n\n✅ *BUY (LONG)*\nConfidence: {confidence:.0f}%\n\n📍 Price: ${data['price']:.2f}\n📊 RSI: {data['rsi']:.1f}"
        elif signal == "SELL":
            msg = f"📉 *BEARISH SIGNAL* 📉\n\n❌ *SELL (SHORT)*\nConfidence: {confidence:.0f}%\n\n📍 Price: ${data['price']:.2f}\n📊 RSI: {data['rsi']:.1f}"
        else:
            msg = f"⏸️ *NO CLEAR SIGNAL*\n\n📍 Price: ${data['price']:.2f}\n📊 RSI: {data['rsi']:.1f}\nConfidence: {confidence:.0f}%"
    
    keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="refresh"),
                 InlineKeyboardButton("📋 Levels", callback_data="levels")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

async def analysis_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    
    data = get_indicators()
    if not data:
        msg = "❌ Failed to fetch data"
    else:
        signal, confidence = get_signal(data)
        
        if data['price'] > data['sma20']:
            trend = "🟢 BULLISH"
        else:
            trend = "🔴 BEARISH"
        
        if data['rsi'] < 30:
            rsi_status = "OVERSOLD 📈"
        elif data['rsi'] > 70:
            rsi_status = "OVERBOUGHT 📉"
        else:
            rsi_status = "NEUTRAL"
        
        msg = f"📊 *TECHNICAL ANALYSIS*\n\n"
        msg += f"📍 Price: ${data['price']:.2f}\n"
        msg += f"📈 Trend: {trend}\n"
        msg += f"📊 RSI: {data['rsi']:.1f} ({rsi_status})\n"
        msg += f"📉 ATR: ${data['atr']:.2f}\n"
        msg += f"📊 SMA20: ${data['sma20']:.2f}\n"
        msg += f"📊 SMA50: ${data['sma50']:.2f}\n\n"
        msg += f"🎯 Signal: {signal} ({confidence:.0f}%)"
    
    keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="refresh")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

async def price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    
    price = get_price()
    if price:
        msg = f"💰 *XAUUSD LIVE PRICE*\n\n📍 ${price:.2f}"
    else:
        msg = "❌ Failed to fetch price"
    
    keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="price_refresh"),
                 InlineKeyboardButton("🔙 Menu", callback_data="menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

async def levels_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    
    data = get_indicators()
    if not data:
        msg = "❌ Failed to fetch data"
    else:
        signal, confidence = get_signal(data)
        
        if signal == "BUY" or signal == "SELL":
            entry, sl, tp1, tp2, tp3, tp4 = calc_levels(data['price'], data['atr'], signal)
            risk = abs(entry - sl)
            reward = abs(tp2 - entry)
            rr = reward / risk if risk > 0 else 0
            
            msg = f"🎯 *TRADING LEVELS*\n\n"
            msg += f"Signal: {signal} ({confidence:.0f}%)\n\n"
            msg += f"📍 ENTRY: ${entry:.2f}\n"
            msg += f"🛑 STOP LOSS: ${sl:.2f}\n"
            msg += f"Risk: ${risk:.2f}\n\n"
            msg += f"🎯 TAKE PROFITS:\n"
            msg += f"• TP1: ${tp1:.2f}\n"
            msg += f"• TP2: ${tp2:.2f} (R:R 1:{rr:.1f})\n"
            msg += f"• TP3: ${tp3:.2f}\n"
            msg += f"• TP4: ${tp4:.2f}"
        else:
            msg = f"⏸️ *NO TRADE SETUP*\n\nWait for BUY/SELL signal first.\nCurrent: {signal} ({confidence:.0f}%)"
    
    keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="levels_refresh"),
                 InlineKeyboardButton("🔙 Menu", callback_data="menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

async def refresh_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer("Refreshing...")
    
    data = get_indicators()
    if data:
        msg = f"🔄 *Data Refreshed*\n\n📍 Price: ${data['price']:.2f}\n📊 RSI: {data['rsi']:.1f}"
    else:
        msg = "❌ Failed to refresh"
    
    keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data="menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    
    msg = "ℹ️ *HELP*\n\n"
    msg += "Commands:\n"
    msg += "/start - Main menu\n"
    msg += "/signal - Trading signal\n"
    msg += "/analysis - Technical analysis\n"
    msg += "/price - Live price\n"
    msg += "/levels - SL/TP levels\n\n"
    msg += "⚠️ Risk warning: Never risk more than 1-2% per trade!"
    
    keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data="menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📈 SIGNAL", callback_data="signal"),
         InlineKeyboardButton("📊 ANALYSIS", callback_data="analysis")],
        [InlineKeyboardButton("💰 PRICE", callback_data="price"),
         InlineKeyboardButton("📋 LEVELS", callback_data="levels")],
        [InlineKeyboardButton("🔄 REFRESH", callback_data="refresh"),
         InlineKeyboardButton("❓ HELP", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    msg = "🚀 *XAUUSD TRADING BOT*\n\nSelect an option:"
    
    if query:
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

async def price_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await price_cmd(update, context)

async def levels_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await levels_cmd(update, context)

# ============ MAIN ============
def main():
    print("🤖 Starting XAUUSD Trading Bot...")
    app = Application.builder().token(TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("signal", signal_cmd))
    app.add_handler(CommandHandler("analysis", analysis_cmd))
    app.add_handler(CommandHandler("price", price_cmd))
    app.add_handler(CommandHandler("levels", levels_cmd))
    app.add_handler(CommandHandler("refresh", refresh_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("menu", menu_cmd))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(signal_cmd, pattern="^signal$"))
    app.add_handler(CallbackQueryHandler(analysis_cmd, pattern="^analysis$"))
    app.add_handler(CallbackQueryHandler(price_cmd, pattern="^price$"))
    app.add_handler(CallbackQueryHandler(levels_cmd, pattern="^levels$"))
    app.add_handler(CallbackQueryHandler(refresh_cmd, pattern="^refresh$"))
    app.add_handler(CallbackQueryHandler(help_cmd, pattern="^help$"))
    app.add_handler(CallbackQueryHandler(menu_cmd, pattern="^menu$"))
    app.add_handler(CallbackQueryHandler(price_refresh, pattern="^price_refresh$"))
    app.add_handler(CallbackQueryHandler(levels_refresh, pattern="^levels_refresh$"))
    
    print("✅ Bot is running! Send /start to @BOACUTING")
    app.run_polling()

if __name__ == "__main__":
    main()
