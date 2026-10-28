"""
Lemvest — a simple Telegram education bot for forex, gold, and bitcoin basics.

Purpose: guide users through 5 short beginner lessons and redirect them
to the Lemvest Telegram channel.

Runs as a Render Background Worker using long polling (no web server).

python-telegram-bot==21.6
"""

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
# Configuration (all secrets come from environment variables)
# ---------------------------------------------------------------------------

BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Falls back to the provided channel link if the env var is not set.
CHANNEL_URL = os.environ.get(
    "CHANNEL_URL",
    "https://t.me/+_uVZZCHw7U1lMGZk",
)

# Required on the welcome message and every lesson.
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

# Make stdout line-buffered so Render streams logs immediately.
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

# ---------------------------------------------------------------------------
# Lesson content
# ---------------------------------------------------------------------------
# Written to be neutral and beginner-friendly. No profit promises, no hype.

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
    """Two-button keyboard shown on /start."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎓 Start Learning", callback_data="back:lessons")],
        [InlineKeyboardButton("📢 Join Lemvest Channel", url=CHANNEL_URL)],
    ])


def learn_keyboard() -> InlineKeyboardMarkup:
    """Five lesson buttons plus the channel button."""
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
    """Channel button + back button shown on every lesson page."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Lemvest Channel", url=CHANNEL_URL)],
        [InlineKeyboardButton("📚 More Lessons", callback_data="back:lessons")],
    ])


def channel_only_keyboard() -> InlineKeyboardMarkup:
    """Just the channel button (used on /channel and fallback replies)."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Lemvest Channel", url=CHANNEL_URL)],
    ])


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — welcome message with the user's first name."""
    user = update.effective_user
    raw_name = (user.first_name if user and user.first_name else "there")
    # Escape in case a user's first name contains Markdown characters.
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


async def learn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/learn — show the 5 lesson buttons."""
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
    """/channel — direct user to the Lemvest channel."""
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
    """/help — list available commands."""
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
    """Any other text message — short reply pointing to /learn and the channel."""
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
# Callback query handler (lesson buttons + back button)
# ---------------------------------------------------------------------------

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle taps on inline buttons."""
    query = update.callback_query
    await query.answer()  # acknowledge the tap so Telegram stops the spinner
    data = query.data or ""

    # "Start Learning" on /start, or "More Lessons" on a lesson page.
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
            # If the edit fails (e.g. identical content), send a fresh message.
            await query.message.reply_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=learn_keyboard(),
            )
        return

    # A specific lesson button.
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

    # Unknown callback — ignore politely.
    logger.warning("Unknown callback data: %r", data)


# ---------------------------------------------------------------------------
# Global error handler
# ---------------------------------------------------------------------------

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log any unhandled exception and notify the user without crashing."""
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

    print("🚀 Starting Lemvest bot (python-telegram-bot 21.6)...", flush=True)
    print(f"📢 Channel URL: {CHANNEL_URL}", flush=True)

    application: Application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("learn", learn))
    application.add_handler(CommandHandler("channel", channel))
    application.add_handler(CommandHandler("help", help_cmd))

    # Inline button handler
    application.add_handler(CallbackQueryHandler(on_callback))

    # Any other text message (not a command)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, fallback)
    )

    # Global error handler
    application.add_error_handler(on_error)

    print("✅ Handlers registered: /start /learn /channel /help", flush=True)
    print("⏳ Polling for updates...", flush=True)

    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
