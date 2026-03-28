import logging
import os
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from pymongo import MongoClient

load_dotenv()

# ===================== CONFIG =====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing in environment variables!")

client = MongoClient(MONGO_URI)
db = client["smart_social_lookup"]
users = db["users"]

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# ===================== HELPERS =====================
def get_user(user_id: int):
    user = users.find_one({"user_id": user_id})
    if not user:
        users.insert_one({
            "user_id": user_id,
            "username": None,
            "first_name": None,
            "tos_accepted": False,
            "plan": "free",
            "subscription_expiry": None,
            "searches_today": 0,
            "last_reset_date": date.today(),
            "total_searches": 0
        })
        user = users.find_one({"user_id": user_id})
    return user

def reset_daily_if_needed(user):
    today = date.today()
    if user.get("last_reset_date") and user["last_reset_date"] < today:
        users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"searches_today": 0, "last_reset_date": today}}
        )
        user["searches_today"] = 0
        user["last_reset_date"] = today
    return user

async def check_quota(user_id: int) -> tuple[bool, str]:
    user = get_user(user_id)
    user = reset_daily_if_needed(user)
    
    if user.get("plan") == "weekly" and user.get("subscription_expiry") and datetime.now() < user["subscription_expiry"]:
        return True, "unlimited"
    
    if user.get("searches_today", 0) >= 5:
        return False, "limit_reached"
    
    return True, "ok"

def increment_search(user_id: int):
    users.update_one(
        {"user_id": user_id},
        {"$inc": {"searches_today": 1, "total_searches": 1}}
    )

def get_social_links(username: str):
    username = username.strip().lstrip("@")
    if not username:
        return {}
    
    links = {
        "Telegram": f"https://t.me/{username}",
        "Instagram": f"https://www.instagram.com/{username}/",
        "X / Twitter": f"https://x.com/{username}",
        "LinkedIn": f"https://www.linkedin.com/in/{username}/",
        "GitHub": f"https://github.com/{username}",
        "Facebook": f"https://www.facebook.com/{username}",
        "YouTube": f"https://youtube.com/@{username}",
    }
    return {k: v for k, v in links.items()}

# ===================== HANDLERS =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    user["username"] = update.effective_user.username
    user["first_name"] = update.effective_user.first_name
    users.update_one({"user_id": user["user_id"]}, {"$set": user})
    
    if not user.get("tos_accepted", False):
        tos_text = (
            "👋 Welcome to <b>Smart Social Lookup Bot</b>!\n\n"
            "🔒 We ONLY show publicly available profile links.\n"
            "✅ No private data is collected.\n"
            "✅ Fully compliant with all platform policies.\n\n"
            "By continuing, you accept our Terms of Service."
        )
        keyboard = [[InlineKeyboardButton("✅ I Accept TOS", callback_data="accept_tos")]]
        await update.message.reply_html(tos_text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    await main_menu(update, context)

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔍 Search Profile", callback_data="search")],
        [InlineKeyboardButton("📊 My Plan", callback_data="myplan")],
        [InlineKeyboardButton("💳 Subscribe", callback_data="subscribe")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    if update.effective_user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🔧 Admin", callback_data="admin")])
    
    text = "🏠 <b>Main Menu</b>\n\nWhat would you like to do?"
    if update.message:
        await update.message.reply_html(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "accept_tos":
        users.update_one({"user_id": user_id}, {"$set": {"tos_accepted": True}})
        await query.edit_message_text("✅ TOS accepted!")
        await main_menu(update, context)
        return

    elif data == "search":
        await query.edit_message_text("🔍 Send any username (e.g. elonmusk or @example)")
        context.user_data["waiting_for_search"] = True
        return

    elif data == "myplan":
        user = get_user(user_id)
        user = reset_daily_if_needed(user)
        status = "✅ Weekly (Unlimited)" if user.get("plan") == "weekly" and user.get("subscription_expiry") and datetime.now() < user["subscription_expiry"] else "Free (5/day)"
        text = f"📊 <b>Your Plan</b>\n\nPlan: {status}\nSearches today: {user.get('searches_today', 0)}/5"
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Back", callback_data="main")]]))

    elif data == "subscribe":
        text = "💳 Upgrade coming soon (Weekly / Pay-per-use)"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Back", callback_data="main")]]))

    elif data == "help":
        text = "Send any username after clicking Search Profile.\nFree: 5 searches/day"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Back", callback_data="main")]]))

    elif data == "main":
        await main_menu(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_for_search"):
        return
    context.user_data["waiting_for_search"] = False
    
    username = update.message.text.strip()
    user_id = update.effective_user.id
    
    can_search, reason = await check_quota(user_id)
    if not can_search:
        await update.message.reply_text("🚫 Daily limit reached. Upgrade for unlimited searches.")
        return
    
    links = get_social_links(username)
    if not links:
        await update.message.reply_text("❌ Invalid username.")
        return
    
    increment_search(user_id)
    
    result = f"🔍 Results for @{username}\n\n"
    for platform, link in links.items():
        result += f"• <b>{platform}</b>: <a href='{link}'>Open</a>\n"
    
    await update.message.reply_html(result)

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("Admin commands: /admin_users")

# ===================== MAIN =====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Smart Social Lookup Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
