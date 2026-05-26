import os
import logging
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

user_favorites = {}

def parse_time_input(time_str):
    time_str = time_str.lower().strip()
    try:
        if 'am' in time_str or 'pm' in time_str:
            if ':' in time_str:
                dt = datetime.strptime(time_str, '%I:%M%p')
            else:
                dt = datetime.strptime(time_str, '%I%p')
            return dt.time()
        else:
            if ':' in time_str:
                dt = datetime.strptime(time_str, '%H:%M')
            else:
                dt = datetime.strptime(time_str, '%H')
            return dt.time()
    except:
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌍 *Welcome to ZonaShift Bot!*\n\n"
        "I convert times between timezones instantly.\n\n"
        "▪️ /convert 3pm EST to IST\n"
        "▪️ /now Tokyo, London\n"
        "▪️ /addtz work\n\n"
        "Send /help for all commands",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*📚 Commands:*\n\n"
        "/start - Welcome message\n"
        "/help - This help menu\n"
        "/convert <time> <from> to <to> - Convert time\n"
        "/now <city1, city2...> - Current times\n"
        "/addtz <name> - Save favorite timezone\n"
        "/mytz - List favorites\n"
        "/removetz <name> - Remove favorite\n"
        "/list - Show timezones\n\n"
        "*Examples:*\n"
        "▪️ /convert 2pm London to Tokyo\n"
        "▪️ /now New York, Berlin, Dubai\n"
        "▪️ /addtz home",
        parse_mode='Markdown'
    )

async def convert_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ Usage: /convert 3pm EST to IST")
        return
    
    text = ' '.join(args)
    parts = text.lower().split(' to ')
    
    if len(parts) != 2:
        await update.message.reply_text("❌ Use: /convert <time> <from> to <to>")
        return
    
    from_part = parts[0].strip()
    to_zone = parts[1].strip()
    
    from_parts = from_part.rsplit(' ', 1)
    if len(from_parts) != 2:
        await update.message.reply_text("❌ Example: /convert 3pm EST to IST")
        return
    
    time_str, from_zone = from_parts
    parsed_time = parse_time_input(time_str)
    
    if not parsed_time:
        await update.message.reply_text("❌ Invalid time. Use: 9am, 2:30pm, 14:00")
        return
    
    try:
        from_tz = pytz.timezone(from_zone.upper())
        to_tz = pytz.timezone(to_zone.upper())
        now_from = datetime.now(from_tz)
        converted_dt = now_from.replace(hour=parsed_time.hour, minute=parsed_time.minute, second=0, microsecond=0)
        converted_dt = converted_dt.astimezone(to_tz)
        result = f"✅ *{time_str} {from_zone.upper()}* = *{converted_dt.strftime('%I:%M %p').lstrip('0')} {to_zone.upper()}*"
        await update.message.reply_text(result, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Timezone error. Use /list for valid zones.")

async def now_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        now_utc = datetime.now(pytz.UTC)
        await update.message.reply_text(f"🕐 *UTC Time:* {now_utc.strftime('%I:%M %p, %b %d')}", parse_mode='Markdown')
        return
    
    cities = ' '.join(args).split(',')
    result = "🌍 *Current Times:*\n\n"
    
    for city in cities:
        city = city.strip()
        try:
            tz = pytz.timezone(city)
            current = datetime.now(tz)
            result += f"📍 *{city}*: {current.strftime('%I:%M %p')}\n"
        except:
            result += f"❌ {city}: Not found\n"
    
    await update.message.reply_text(result, parse_mode='Markdown')

async def add_favorite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    args = context.args
    
    if not args:
        await update.message.reply_text("❌ Usage: /addtz work\nThen send me a timezone like Asia/Tokyo")
        return
    
    fav_name = args[0]
    if user_id not in user_favorites:
        user_favorites[user_id] = {}
    
    context.user_data['pending_fav'] = fav_name
    await update.message.reply_text(f"📝 Send me the timezone for *{fav_name}*\nExample: `America/New_York` or `Asia/Kolkata`", parse_mode='Markdown')

async def handle_favorite_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if 'pending_fav' not in context.user_data:
        return
    
    fav_name = context.user_data['pending_fav']
    tz_input = update.message.text.strip()
    
    try:
        pytz.timezone(tz_input)
        user_favorites[user_id][fav_name] = tz_input
        del context.user_data['pending_fav']
        await update.message.reply_text(f"✅ Saved! *{fav_name}* = `{tz_input}`", parse_mode='Markdown')
    except:
        await update.message.reply_text("❌ Invalid timezone. Send /list for valid zones.")

async def list_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    favs = user_favorites.get(user_id, {})
    
    if not favs:
        await update.message.reply_text("📭 No favorites. Use /addtz to add one.")
        return
    
    msg = "⭐ *Your Favorites:*\n\n"
    for name, tz in favs.items():
        try:
            current = datetime.now(pytz.timezone(tz))
            msg += f"• *{name}*: {tz} → {current.strftime('%I:%M %p')}\n"
        except:
            msg += f"• *{name}*: {tz}\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def remove_favorite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    args = context.args
    
    if not args:
        await update.message.reply_text("❌ Usage: /removetz work")
        return
    
    fav_name = args[0]
    if user_id in user_favorites and fav_name in user_favorites[user_id]:
        del user_favorites[user_id][fav_name]
        await update.message.reply_text(f"✅ Removed *{fav_name}*", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ '{fav_name}' not found")

async def list_timezones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    common_tz = [
        "America/New_York", "America/Los_Angeles", "America/Chicago",
        "Europe/London", "Europe/Paris", "Europe/Berlin",
        "Asia/Tokyo", "Asia/Dubai", "Asia/Kolkata", "Asia/Shanghai",
        "Australia/Sydney", "Pacific/Auckland", "Africa/Johannesburg"
    ]
    
    msg = "*📋 Common Timezones:*\n\n"
    for tz in common_tz:
        msg += f"• `{tz}`\n"
    
    msg += "\nUse these exactly as shown."
    await update.message.reply_text(msg, parse_mode='Markdown')

def main():
    """Start the bot using long polling (for Background Worker)"""
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("convert", convert_time))
    application.add_handler(CommandHandler("now", now_time))
    application.add_handler(CommandHandler("addtz", add_favorite))
    application.add_handler(CommandHandler("mytz", list_favorites))
    application.add_handler(CommandHandler("removetz", remove_favorite))
    application.add_handler(CommandHandler("list", list_timezones))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_favorite_timezone))
    
    # Use polling for background worker (no webhook needed)
    print("🤖 ZonaShift Bot is running with long polling...")
    application.run_polling()

if __name__ == '__main__':
    main()
