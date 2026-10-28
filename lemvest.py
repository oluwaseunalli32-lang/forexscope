"""
Lemvest — a simple Telegram education bot for forex, gold, and bitcoin basics.
"""

import asyncio
import logging
import os
import sys

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.helpers import escape_markdown

# ---------------------------------------------------------------------------
# Defensive asyncio event loop guard
# ---------------------------------------------------------------------------
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
    print("ℹ️ Created a new asyncio event loop.", flush=True)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")

CHANNEL_URL = os.environ.get(
    "CHANNEL_URL",
    "https://t.me/+_uVZZCHw7U1lMGZk",
)

DISCLAIMER = (
    "⚠️ Educational content only, not financial advice. "
    "Forex trading carries a high risk of loss."
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("lemvest")

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

# ---------------------------------------------------------------------------
# Lesson content
# ---------------------------------------------------------------------------
LESSONS = {
    "pips": {
        "title": "📏 Pips",
        "body": (
            "A pip (percentage in point) is the smallest standard move in a "
            "currency pair. For most pairs it is the fourth decimal place "
            "(0.0001). For JPY pairs it is the second decimal place (0.01).\n\n"
            "Pips measure how far a price has moved and are used to "
            "calculate position size and risk."
        ),
    },
    "leverage": {
        "title": "⚖️ Leverage",
        "body": (
            "Leverage lets you control a larger position with a smaller "
            "amount of capital. It is expressed as a ratio, such as 1:100.\n\n"
            "Leverage magnifies both gains and losses. It does not improve "
            "your chances of winning a trade — it increases the size of the "
            "outcome. Many beginners lose their account quickly because of "
            "high leverage."
        ),
    },
    "risk": {
        "title": "🛡 Risk Management",
        "body": (
            "Risk management is about how much of your account you are "
            "willing to lose on a single trade.\n\n"
            "A common beginner rule is risking no more than 1 to 2 percent "
            "of the account per trade, with a stop-loss set in advance. "
            "This keeps one bad trade from wiping out your account."
        ),
    },
    "candlesticks": {
        "title": "🕯 Candlesticks",
        "body": (
            "Each candlestick shows price action over a fixed period. "
            "It has four parts: open, high, low, and close.\n\n"
            "Green or white candle = price closed higher than it opened.\n"
            "Red or black candle = price closed lower than it opened.\n\n"
            "Candlestick patterns show how buyers and sellers are behaving, "
            "but they do not predict the future on their own."
        ),
    },
    "sessions": {
        "title": "🌍 Trading Sessions",
        "body": (
            "Forex trades 24 hours a day on weekdays, across four main "
            "sessions:\n\n"
            "• Sydney\n"
            "• Tokyo\n"
            "• London\n"
            "• New York\n\n"
            "Volatility often increases during overlaps — especially "
            "London and New York. Many beginners start by observing these "
            "sessions rather than trading during all of them."
        ),
    },
}

# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------
def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎓 Start Learning", callback_data="back:lessons")],
        [InlineKeyboardButton("📢 Join Lemvest Channel", url=CHANNEL_URL)],
    ])

def learn_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📏 Pips", callback_data="lesson:pips"),
            InlineKeyboardButton("⚖️ Leverage", callback_data="lesson:leverage"),
        ],
        [
            InlineKeyboardButton("🛡 Risk Management", callback_data="lesson:risk"),
            InlineKeyboardButton("🕯 Candlesticks", callback_data="lesson:candlesticks"),
        ],
        [
            InlineKeyboardButton("🌍 Trading Sessions", callback_data="lesson:sessions"),
        ],
        [
            InlineKeyboardButton("📢 Join Lemvest Channel", url=CHANNEL_URL),
        ],
    ])

def lesson_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Lemvest Channel", url=CHANNEL_URL)],
        [InlineKeyboardButton("📚 More Lessons", callback_data="back:lessons")],
    ])

def channel_only_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Lemvest Channel", url=CHANNEL_URL)],
    ])

# ---------------------------------------------------------------------------
# Background Job (4h Reminder)
# ---------------------------------------------------------------------------
async def send_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    text = (
        "👋 Just a quick reminder! Have you joined the Lemvest channel yet?\n\n"
        "We share beginner-friendly insights there.\n\n"
        f"{DISCLAIMER}"
    )
    try:
        await context.bot.send_message(
            chat_id=job.chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=channel_only_keyboard(),
        )
        logger.info(f"Sent 4h reminder to chat {job.chat_id}")
    except Exception as e:
        logger.warning(f"Could not send reminder to {job.chat_id}: {e}")

# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    raw_name = (user.first_name if user and user.first_name else "there")
    safe_name = escape_markdown(raw_name, version=1)

    text = (
        f"Hi {safe_name}! 👋\n\n"
        "*Welcome to Lemvest* — a beginner-friendly place to learn the "
        "basics of forex, gold, and bitcoin.\n\n"
        "Use the buttons below to start learning or join the channel.\n\n"
        f"{DISCLAIMER}"
    )
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=start_keyboard(),
    )

    # Schedule the 4-hour reminder.
    job_name = f"reminder_{chat_id}"
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    
    if not current_jobs:
        context.job_queue.run_once(
            send_reminder,
            when=4 * 3600,  # 4 hours
            chat_id=chat_id,
            name=job_name,
        )
        logger.info(f"Scheduled 4h reminder for chat {chat_id}")

async def learn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "📚 *Lemvest — Lessons*\n\n"
        "Pick a topic below to start learning.\n\n"
        f"{DISCLAIMER}"
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=learn_keyboard(),
    )

async def channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Tap the button below to join the Lemvest channel for more "
        "beginner-friendly lessons.\n\n"
        f"{DISCLAIMER}"
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=channel_only_keyboard(),
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "*Lemvest — Commands*\n\n"
        "/start — Welcome message\n"
        "/learn — Browse beginner lessons\n"
        "/channel — Join the Lemvest channel\n"
        "/help — Show this message\n\n"
        f"{DISCLAIMER}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "I am here to teach — not to trade. 🙂\n\n"
        "Try /learn to browse lessons, or tap below to join the channel.\n\n"
        f"{DISCLAIMER}"
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=channel_only_keyboard(),
    )

# ---------------------------------------------------------------------------
# Callback query handler
# ---------------------------------------------------------------------------
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    if data == "back:lessons":
        text = (
            "📚 *Lemvest — Lessons*\n\n"
            "Pick a topic below to start learning.\n\n"
            f"{DISCLAIMER}"
        )
        try:
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=learn_keyboard(),
            )
        except Exception:
            await query.message.reply_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=learn_keyboard(),
            )
        return

    if data.startswith("lesson:"):
        key = data.split(":", 1)[1]
        lesson = LESSONS.get(key)
        if not lesson:
            await query.edit_message_text("Lesson not found.")
            return

        text = f"{lesson['title']}\n\n{lesson['body']}\n\n{DISCLAIMER}"
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=lesson_keyboard(),
        )
        return

    logger.warning("Unknown callback data: %r", data)

# ---------------------------------------------------------------------------
# Global error handler
# ---------------------------------------------------------------------------
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling update:", exc_info=context.error)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ Something went wrong. Please try /start again."
            )
    except Exception:
        logger.exception("Failed to send error reply.")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    if not BOT_TOKEN:
        print(
            "ERROR: BOT_TOKEN environment variable is not set. "
            "Set it in Render → Environment.",
            flush=True,
        )
        sys.exit(1)

    print("🚀 Starting Lemvest bot...", flush=True)

    application: Application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("learn", learn))
    application.add_handler(CommandHandler("channel", channel))
    application.add_handler(CommandHandler("help", help_cmd))

    # Inline button handler
    application.add_handler(CallbackQueryHandler(on_callback))

    # Any other text message
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, fallback)
    )

    # Global error handler
    application.add_error_handler(on_error)

    print("✅ Handlers registered.", flush=True)
    print("⏳ Polling for updates...", flush=True)

    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )

if __name__ == "__main__":
    main()
