from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "8369393711:AAGm8ydfJc3UQPyNCPR6uCEr1LQpFw-zV-4"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is working! Send /price to get gold price")

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import requests
    try:
        url = "https://api.twelvedata.com/price?symbol=XAU/USD&apikey=96871e27b094425f9ea104fa6eb2be64"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            price = r.json()['price']
            await update.message.reply_text(f"💰 XAUUSD: ${price}")
        else:
            await update.message.reply_text("❌ API error")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📈 BUY SIGNAL - Confidence: 65%")

print("Starting simple bot...")
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("price", price))
app.add_handler(CommandHandler("signal", signal))
print("Bot is running! Send /start to @BOACUTING")
app.run_polling()
