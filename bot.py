import logging
import os
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler
)
import pymongo

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")  # We'll set this later

# MongoDB setup (you can run without it first)
try:
    client = pymongo.MongoClient(MONGO_URI) if MONGO_URI else None
    db = client["chooll_bot"] if client else None
    users = db["users"] if db else None
except:
    client = db = users = None
    print("⚠️ Running without database (limits won't be saved)")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def get_user(user_id):
    if not users:
        return {"user_id": user_id, "plan": "free", "searches_today": 0, "last_reset": datetime.utcnow()}
    user = users.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "plan": "free",
            "searches_today": 0,
            "last_reset": datetime.utcnow(),
            "total_searches": 0
        }
        users.insert_one(user)
    return user

def can_search(user):
    if user.get("plan") == "free":
        if (datetime.utcnow() - user["last_reset"]).days >= 1:
            if users:
                users.update_one({"user_id": user["user_id"]}, {"$set": {"searches_today": 0, "last_reset": datetime.utcnow()}})
            user["searches_today"] = 0
        return user["searches_today"] < 5
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("✅ Accept & Start", callback_data="accept")],
        [InlineKeyboardButton("💰 View Plans", callback_data="plans")]
    ]
    await update.message.reply_text(
        "👋 Welcome to **Chooll - Smart Social Lookup Bot**!\n\n"
        "I help you find publicly available social media profiles using usernames.\n"
        "✅ Only public links • No private data • Compliant with policies\n\n"
        "Tap below to continue.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not can_search(user):
        await update.message.reply_text("❌ You have reached the daily limit (5 searches on Free plan).\nUse /plans to upgrade.")
        return
    await update.message.reply_text("🔍 Send me a username (example: elonmusk or @elonmusk)")

async def handle_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not can_search(user):
        await update.message.reply_text("Daily limit reached.")
        return

    username = update.message.text.strip().lstrip('@').lower()
    if len(username) < 2:
        await update.message.reply_text("❌ Please send a valid username.")
        return

    # Record usage
    if users:
        users.update_one({"user_id": user["user_id"]}, {"$inc": {"searches_today": 1, "total_searches": 1}})

    await update.message.reply_text(f"🔎 Looking up **@{username}**...", parse_mode='Markdown')

    results = [
        f"📱 **Telegram**: [t.me/{username}](https://t.me/{username})",
        f"🐦 **X / Twitter**: [x.com/{username}](https://x.com/{username})",
        f"📷 **Instagram**: [instagram.com/{username}](https://www.instagram.com/{username}/)",
        f"💼 **LinkedIn**: [linkedin.com/in/{username}](https://www.linkedin.com/in/{username}/)",
        f"🐙 **GitHub**: [github.com/{username}](https://github.com/{username})"
    ]

    response = f"✅ **Public Profile Links for @{username}**\n\n" + "\n\n".join(results)
    response += "\n\n⚠️ These are direct public links. Only information that is publicly visible on each platform will appear."

    await update.message.reply_text(response, parse_mode='Markdown', disable_web_page_preview=True)

async def plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Free Plan (5 searches/day)", callback_data="free")],
        [InlineKeyboardButton("Weekly Plan - ₹499/week (Unlimited)", callback_data="weekly")],
        [InlineKeyboardButton("Pay per Search - ₹49 each", callback_data="payper")]
    ]
    await update.message.reply_text("💰 **Choose a Plan**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "accept":
        await query.edit_message_text("✅ Great! Now use /search to start looking up usernames.")
    elif query.data == "plans":
        await plans(update, context)  # show plans again
    else:
        await query.edit_message_text(f"Selected: {query.data}\n\nPayment integration will be added soon.")

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("plans", plans))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_username))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("🚀 Chooll Bot is starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
