import asyncio
import json
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import pandas as pd
import numpy as np
from datetime import datetime

# ============ CONFIGURATION ============
TELEGRAM_BOT_TOKEN = "8369393711:AAGm8ydfJc3UQPyNCPR6uCEr1LQpFw-zV-4"
API_KEY = "96871e27b094425f9ea104fa6eb2be64"

# Store user sessions
user_sessions = {}

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
        [InlineKeyboardButton("📈 Live Signal", callback_data="signal"),
         InlineKeyboardButton("📊 Analysis", callback_data="analysis")],
        [InlineKeyboardButton("💰 Price", callback_data="price"),
         InlineKeyboardButton("📋 Levels", callback_data="levels")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh"),
         InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🚀 *XAUUSD TRADING BOT*\n\n"
        "Welcome to your personal trading assistant!\n\n"
        "📱 *Use the buttons below:*\n"
        "• 📈 Live Signal - Get current trading signal\n"
        "• 📊 Analysis - Technical analysis summary\n"
        "• 💰 Price - Current XAUUSD price\n"
        "• 📋 Levels - Entry, SL, TP levels\n\n"
        "⚡ All data is real-time from live market!",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    
    data = get_indicators()
    if not data:
        msg = "❌ Failed to fetch data. Please try again."
    else:
        signal, confidence = get_signal(data)
        
        if signal == "BUY":
            msg = f"📈 *BULLISH SIGNAL* 📈\n\n"
            msg += f"🟢 *BUY (LONG)*\n"
            msg += f"Confidence: {confidence:.0f}%\n\n"
            msg += f"📍 Price: ${data['price']:.2f}\n"
            msg += f"📊 RSI: {data['rsi']:.1f}\n"
            msg += f"📈 ATR: ${data['atr']:.2f}"
        elif signal == "SELL":
            msg = f"📉 *BEARISH SIGNAL* 📉\n\n"
            msg += f"🔴 *SELL (SHORT)*\n"
            msg += f"Confidence: {confidence:.0f}%\n\n"
            msg += f"📍 Price: ${data['price']:.2f}\n"
            msg += f"📊 RSI: {data['rsi']:.1f}\n"
            msg += f"📈 ATR: ${data['atr']:.2f}"
        else:
            msg = f"⏸️ *NO CLEAR SIGNAL*\n\n"
            msg += f"📍 Price: ${data['price']:.2f}\n"
            msg += f"📊 RSI: {data['rsi']:.1f}\n"
            msg += f"Confidence: {confidence:.0f}%"
    
    keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="refresh"),
                 InlineKeyboardButton("📊 Levels", callback_data="levels")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

async def analysis_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    
    data = get_indicators()
    if not data:
        msg = "❌ Failed to fetch data"
    else:
        signal, confidence = get_signal(data)
        
        if data['price'] > data['sma20']:
            trend = "🟢 BULLISH (above SMA20)"
        else:
            trend = "🔴 BEARISH (below SMA20)"
        
        if data['rsi'] < 30:
            rsi_status = "🟢 OVERSOLD (may bounce up)"
        elif data['rsi'] > 70:
            rsi_status = "🔴 OVERBOUGHT (may drop down)"
        else:
            rsi_status = "⚪ NEUTRAL"
        
        msg = f"📊 *TECHNICAL ANALYSIS*\n\n"
        msg += f"📍 *Price:* ${data['price']:.2f}\n"
        msg += f"📈 *Trend:* {trend}\n"
        msg += f"📊 *RSI:* {data['rsi']:.1f} - {rsi_status}\n"
        msg += f"📉 *ATR:* ${data['atr']:.2f}\n"
        msg += f"📊 *SMA20:* ${data['sma20']:.2f}\n"
        msg += f"📊 *SMA50:* ${data['sma50']:.2f}\n\n"
        msg += f"🎯 *Signal:* {signal} ({confidence:.0f}%)"
    
    keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="refresh")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    
    price = get_price()
    
    if price:
        msg = f"💰 *XAUUSD LIVE PRICE*\n\n"
        msg += f"📍 ${price:.2f}"
    else:
        msg = "❌ Failed to fetch price"
    
    keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="price_refresh"),
                 InlineKeyboardButton("🔙 Menu", callback_data="menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

async def levels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            msg += f"📊 *Signal:* {signal} ({confidence:.0f}%)\n\n"
            msg += f"📍 *ENTRY:* ${entry:.2f}\n"
            msg += f"🛑 *STOP LOSS:* ${sl:.2f}\n"
            msg += f"Risk: ${risk:.2f}\n\n"
            msg += f"🎯 *TAKE PROFITS:*\n"
            msg += f"• TP1: ${tp1:.2f}\n"
            msg += f"• TP2: ${tp2:.2f} (R:R 1:{rr:.1f})\n"
            msg += f"• TP3: ${tp3:.2f}\n"
            msg += f"• TP4: ${tp4:.2f}"
        else:
            msg = f"⏸️ *NO TRADE SETUP*\n\n"
            msg += f"Wait for a clear BUY/SELL signal first.\n"
            msg += f"Current signal: {signal} ({confidence:.0f}%)"
    
    keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="levels_refresh"),
                 InlineKeyboardButton("🔙 Menu", callback_data="menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

async def refresh_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer("Refreshing...")
    
    data = get_indicators()
    
    if data:
        msg = f"🔄 *Data Refreshed*\n\n"
        msg += f"📍 Price: ${data['price']:.2f}\n"
        msg += f"📊 RSI: {data['rsi']:.1f}\n"
        msg += f"📈 ATR: ${data['atr']:.2f}\n\n"
        msg += "Use /signal for trading signal"
    else:
        msg = "❌ Failed to refresh"
    
    keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data="menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    
    msg = "ℹ️ *XAUUSD TRADING BOT HELP*\n\n"
    msg += "*Commands:*\n"
    msg += "📈 /signal - Get current trading signal\n"
    msg += "📊 /analysis - Full technical analysis\n"
    msg += "💰 /price - Current XAUUSD price\n"
    msg += "📋 /levels - Entry, SL, TP levels\n"
    msg += "🔄 /refresh - Refresh all data\n"
    msg += "ℹ️ /help - Show this message\n\n"
    msg += "*How to use:*\n"
    msg += "1. Check /signal for trade direction\n"
    msg += "2. Use /levels for exact prices\n"
    msg += "3. Place trade on your broker\n\n"
    msg += "⚠️ *Risk Warning:*\n"
    msg += "Trading involves risk. Never risk more than 1-2% per trade."
    
    keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data="menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📈 Live Signal", callback_data="signal"),
         InlineKeyboardButton("📊 Analysis", callback_data="analysis")],
        [InlineKeyboardButton("💰 Price", callback_data="price"),
         InlineKeyboardButton("📋 Levels", callback_data="levels")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh"),
         InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    msg = "🚀 *XAUUSD TRADING BOT*\n\nSelect an option:"
    
    if query:
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

async def price_refresh_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await price_command(update, context)

async def levels_refresh_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await levels_command(update, context)

# ============ MAIN ============
def main():
    print("🤖 Starting XAUUSD Trading Bot...")
    print("Bot Token:", TELEGRAM_BOT_TOKEN[:10] + "...")
    
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("signal", signal_command))
    app.add_handler(CommandHandler("analysis", analysis_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("levels", levels_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("refresh", refresh_command))
    app.add_handler(CommandHandler("menu", menu_command))
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(signal_command, pattern="^signal$"))
    app.add_handler(CallbackQueryHandler(analysis_command, pattern="^analysis$"))
    app.add_handler(CallbackQueryHandler(price_command, pattern="^price$"))
    app.add_handler(CallbackQueryHandler(levels_command, pattern="^levels$"))
    app.add_handler(CallbackQueryHandler(refresh_command, pattern="^refresh$"))
    app.add_handler(CallbackQueryHandler(help_command, pattern="^help$"))
    app.add_handler(CallbackQueryHandler(menu_command, pattern="^menu$"))
    app.add_handler(CallbackQueryHandler(price_refresh_command, pattern="^price_refresh$"))
    app.add_handler(CallbackQueryHandler(levels_refresh_command, pattern="^levels_refresh$"))
    
    print("✅ Bot is running! Send /start to @BOACUTING on Telegram")
    print("Press Ctrl+C to stop")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
