import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from pymongo import MongoClient
import asyncio

# Environment Variables
TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# MongoDB Connection
client = MongoClient(MONGO_URI)
db = client["smart_social_bot"]

print("✅ Bot Starting...")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Hello {user.first_name}!\n\n"
        "Welcome to **Chooll Bot** - Smart Social Intelligence Tool\n\n"
        "Send an Indian phone number (with country code) to start lookup."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text("🔍 Processing your request... (Feature coming soon)")

if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("BOT_TOKEN is missing!")
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & \~filters.COMMAND, handle_message))
    
    print("🚀 Bot is running...")
    app.run_polling()
