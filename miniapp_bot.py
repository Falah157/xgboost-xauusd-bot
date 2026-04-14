from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "8369393711:AAGm8ydfJc3UQPyNCPR6uCEr1LQpFw-zV-4"
# REPLACE WITH YOUR LOCALTUNNEL URL
WEBAPP_URL = "https://xxxx.loca.lt"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🏆 OPEN AI TRADING APP", web_app=WebAppInfo(url=WEBAPP_URL))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🚀 *XAUUSD AI TRADING MINI APP*\n\n"
        "Click the button below to open the full trading dashboard!\n\n"
        "✨ *Features:*\n"
        "• 🤖 AI Buy/Sell Signals\n"
        "• 📊 32+ Technical Indicators\n"
        "• 🎯 Entry, SL, TP1-TP4 Levels\n"
        "• 📈 Fibonacci & Pivot Points\n"
        "• 🔄 Backtest Engine\n"
        "• 💰 Position Sizing\n"
        "• 📋 Trade History\n\n"
        "⚡ *Gold & Black Theme | Matrix Effects*\n\n"
        "⚠️ Educational only - Not financial advice",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

def main():
    print("🤖 Starting Telegram Mini App Bot...")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("✅ Bot is running! Send /start to @BOACUTING")
    app.run_polling()

if __name__ == "__main__":
    main()
