# zonaShift_bot.py
import os
import logging
from datetime import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
PORT = int(os.getenv('PORT', 8443))

# Store user favorites (in production, use a database)
user_favorites = {}

def parse_time_input(time_str):
    """Parse various time formats"""
    time_str = time_str.lower().strip()
    try:
        # Try 12-hour format with am/pm
        if 'am' in time_str or 'pm' in time_str:
            dt = datetime.strptime(time_str, '%I:%M%p')
        elif 'am' in time_str or 'pm' in time_str:
            dt = datetime.strptime(time_str, '%I%p')
        else:
            # Try 24-hour format
            dt = datetime.strptime(time_str, '%H:%M')
        return dt.time()
    except:
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = """
🌍 **Welcome to ZonaShift Bot!**

I help you convert times between timezones instantly.

**Quick examples:**
• `/convert 3pm EST to IST`
• `/now Tokyo, London, New York`
• `/addtz` to save favorites

Use `/help` for all commands.
"""
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_msg = """
📚 **ZonaShift Commands**

/start - Start the bot
/help - Show this help

**Time Conversion:**
`/convert 3pm EST to IST`
`/convert 14:30 UTC to PST`
`/convert 9am London to Tokyo`

**Current Time:**
`/now New York, London, Tokyo`
`/now` (shows your timezone)

**Favorites:**
`/addtz work` → Then reply with timezone
`/mytz` - List saved timezones
`/removetz work` - Remove favorite

**Supported formats:** 9am, 2:30pm, 14:00, 11pm

Send `/list` for all available timezones
"""
    await update.message.reply_text(help_msg, parse_mode='Markdown')

async def convert_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ Usage: `/convert 3pm EST to IST`\nExample: `/convert 2:30pm PST to London`", parse_mode='Markdown')
        return
    
    text = ' '.join(args)
    
    # Parse the command: "3pm EST to IST"
    parts = text.lower().split(' to ')
    if len(parts) != 2:
        await update.message.reply_text("❌ Use format: `/convert <time> <from_zone> to <to_zone>`", parse_mode='Markdown')
        return
    
    from_part = parts[0].strip()
    to_zone = parts[1].strip()
    
    # Split time and from zone (e.g., "3pm est")
    from_parts = from_part.rsplit(' ', 1)
    if len(from_parts) != 2:
        await update.message.reply_text("❌ Example: `/convert 3pm EST to IST`", parse_mode='Markdown')
        return
    
    time_str, from_zone = from_parts
    
    # Parse time
    parsed_time = parse_time_input(time_str)
    if not parsed_time:
        await update.message.reply_text("❌ Invalid time format. Use: 9am, 2:30pm, 14:00, 11pm")
        return
    
    try:
        # Get timezones
        from_tz = pytz.timezone(pytz.timezone(from_zone.upper()).zone if from_zone.upper() in pytz.all_timezones_set else from_zone)
        to_tz = pytz.timezone(pytz.timezone(to_zone.upper()).zone if to_zone.upper() in pytz.all_timezones_set else to_zone)
    except:
        await update.message.reply_text(f"❌ Unknown timezone. Use `/list` to see supported zones.")
        return
    
    # Get current date in from_zone
    now_from = datetime.now(from_tz)
    converted_dt = now_from.replace(hour=parsed_time.hour, minute=parsed_time.minute, second=0, microsecond=0)
    converted_dt = converted_dt.astimezone(to_tz)
    
    result = f"🕒 **{time_str} {from_zone.upper()}** = **{converted_dt.strftime('%I:%M %p').lstrip('0')} {to_zone.upper()}**"
    await update.message.reply_text(result, parse_mode='Markdown')

async def now_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    user_id = str(update.effective_user.id)
    
    if not args:
        # Show user's local time if no args
        user_tz = user_favorites.get(user_id, {}).get('default', 'UTC')
        current = datetime.now(pytz.timezone(user_tz))
        await update.message.reply_text(f"🕐 Your current time: **{current.strftime('%I:%M %p, %B %d, %Y')}** ({user_tz})", parse_mode='Markdown')
        return
    
    cities = ' '.join(args).split(',')
    result = "🌍 **Current Times:**\n\n"
    
    for city in cities:
        city = city.strip()
        try:
            tz = pytz.timezone(city)
            current = datetime.now(tz)
            result += f"📍 **{city}**: {current.strftime('%I:%M %p')}\n"
        except:
            result += f"❌ {city}: Not found\n"
    
    await update.message.reply_text(result, parse_mode='Markdown')

async def add_favorite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in user_favorites:
        user_favorites[user_id] = {}
    
    args = context.args
    if not args:
        await update.message.reply_text("Usage: `/addtz <name>`\nExample: `/addtz work`\nThen send me a timezone like `Asia/Tokyo`", parse_mode='Markdown')
        return
    
    fav_name = args[0]
    user_favorites[user_id][fav_name] = None
    context.user_data['pending_fav'] = fav_name
    await update.message.reply_text(f"✅ Send me the timezone for **{fav_name}**\n(e.g., `America/New_York`, `Asia/Kolkata`, `Europe/London`)", parse_mode='Markdown')

async def handle_favorite_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if 'pending_fav' not in context.user_data:
        return
    
    fav_name = context.user_data['pending_fav']
    tz_input = update.message.text.strip()
    
    try:
        tz = pytz.timezone(tz_input)
        user_favorites[user_id][fav_name] = tz_input
        del context.user_data['pending_fav']
        await update.message.reply_text(f"✅ Saved! **{fav_name}** = {tz_input}\nUse `/mytz` to see all favorites.", parse_mode='Markdown')
    except:
        await update.message.reply_text(f"❌ Invalid timezone. Use `/list` to see valid zones.")

async def list_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    favs = user_favorites.get(user_id, {})
    
    if not favs:
        await update.message.reply_text("📭 No saved favorites. Use `/addtz <name>` to add one.")
        return
    
    msg = "⭐ **Your Favorites:**\n\n"
    for name, tz in favs.items():
        current = datetime.now(pytz.timezone(tz if tz else 'UTC'))
        msg += f"• **{name}**: {tz if tz else 'Not set'} → {current.strftime('%I:%M %p')}\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def remove_favorite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    args = context.args
    
    if not args:
        await update.message.reply_text("Usage: `/removetz <name>`\nExample: `/removetz work`", parse_mode='Markdown')
        return
    
    fav_name = args[0]
    if user_id in user_favorites and fav_name in user_favorites[user_id]:
        del user_favorites[user_id][fav_name]
        await update.message.reply_text(f"✅ Removed **{fav_name}** from favorites.", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ Favorite '{fav_name}' not found.")

async def list_timezones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    common_tz = [
        "America/New_York", "America/Los_Angeles", "America/Chicago",
        "Europe/London", "Europe/Paris", "Europe/Berlin",
        "Asia/Tokyo", "Asia/Dubai", "Asia/Kolkata", "Asia/Shanghai",
        "Australia/Sydney", "Pacific/Auckland", "Africa/Johannesburg"
    ]
    
    msg = "📋 **Common Timezones:**\n\n"
    for tz in common_tz:
        msg += f"• `{tz}`\n"
    
    msg += "\nUse exact names from https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
    await update.message.reply_text(msg, parse_mode='Markdown')

def main():
    """Start the bot"""
    application = Application.builder().token(TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("convert", convert_time))
    application.add_handler(CommandHandler("now", now_time))
    application.add_handler(CommandHandler("addtz", add_favorite))
    application.add_handler(CommandHandler("mytz", list_favorites))
    application.add_handler(CommandHandler("removetz", remove_favorite))
    application.add_handler(CommandHandler("list", list_timezones))
    
    # Message handler for favorite timezone input
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_favorite_timezone))
    
    # Start the Bot
    print("🤖 ZonaShift Bot is running...")
    application.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"https://your-app-name.onrender.com/{TOKEN}")

if __name__ == '__main__':
    main()
