"""
ForexScope Bot — a simple Telegram bot for checking forex exchange rates.
Deployed as a Background Worker on Render.com.

Data source: Frankfurter API (https://api.frankfurter.dev/v2)
  - Free, no API key, no rate caps for normal use
  - 200+ currencies, daily reference rates from 84 central banks
"""

import asyncio
import logging
import os
import sys
from typing import Optional

import httpx
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TELEGRAM_BOT_TOKEN: Optional[str] = os.environ.get("TELEGRAM_BOT_TOKEN")
FRANKFURTER_BASE: str = "https://api.frankfurter.dev/v2"
HTTP_TIMEOUT: float = 10.0

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# NOTE: logging.Logger.info()/error()/etc. do NOT accept `flush=`.
# Only print() accepts flush. Do not mix them.

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Make stdout line-buffered so Render streams logs immediately.
try:
    sys.stdout.reconfigure(line_buffering=True)  # Python 3.7+
except Exception:
    pass

# ---------------------------------------------------------------------------
# Defensive asyncio.get_event_loop() guard
# ---------------------------------------------------------------------------
# Python 3.12+ no longer auto-creates an event loop for get_event_loop().
# On 3.14 it raises RuntimeError. We create one explicitly if needed.

def _ensure_event_loop() -> None:
    """Ensure an asyncio event loop exists in the current thread."""
    # If a loop is already running (shouldn't be at startup), nothing to do.
    try:
        asyncio.get_running_loop()
        return
    except RuntimeError:
        pass

    # Try to get the current loop. If none, create one.
    try:
        asyncio.get_event_loop_policy().get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # Use print() — logging does not accept flush=.
        print("ℹ️  Created a new asyncio event loop.", flush=True)


# ---------------------------------------------------------------------------
# External API helpers (defensive)
# ---------------------------------------------------------------------------

async def fetch_rates(base: str) -> dict:
    """Fetch latest exchange rates for a base currency.

    Returns dict: {"base": "USD", "date": "YYYY-MM-DD", "rates": {...}}
    Raises httpx.HTTPError or ValueError on failure.
    """
    url = f"{FRANKFURTER_BASE}/rates?base={base.upper()}"
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

    if "rates" not in data:
        raise ValueError("Unexpected response shape from Frankfurter API.")
    return data


async def fetch_currencies() -> list:
    """Fetch the list of supported currency codes."""
    url = f"{FRANKFURTER_BASE}/currencies"
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

    if not isinstance(data, list):
        raise ValueError("Unexpected currencies response from API.")
    return data


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — greet the user and show available commands."""
    text = (
        "*Welcome to ForexScope Bot!* 📊\n\n"
        "I help you check foreign exchange rates quickly.\n\n"
        "*Available commands:*\n"
        "• `/rate <base>` — latest rates for a base currency\n"
        "• `/convert <amount> <from> <to>` — convert an amount\n"
        "• `/currencies` — list supported currencies\n"
        "• `/help` — show this message again\n\n"
        "*Examples:*\n"
        "`/rate USD`\n"
        "`/convert 100 USD EUR`\n\n"
        "_⚠️ Disclaimer: Rates are indicative and sourced from public central "
        "bank data. Not financial advice._"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help — re-send the help text."""
    await cmd_start(update, context)


async def cmd_rate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /rate <base> — show latest rates for a base currency."""
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: `/rate <base>`\nExample: `/rate USD`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    base = args[0].upper()
    if len(base) != 3 or not base.isalpha():
        await update.message.reply_text(
            "Please provide a 3-letter currency code, e.g. `USD`.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        data = await fetch_rates(base)
    except httpx.TimeoutException:
        await update.message.reply_text(
            "⏳ The exchange rate service timed out. Please try again in a moment.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            await update.message.reply_text(
                f"❌ Unknown base currency `{base}`. "
                "Use `/currencies` to see supported codes.",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await update.message.reply_text(
                "⚠️ The exchange rate service returned an error. Please try again later.",
                parse_mode=ParseMode.MARKDOWN,
            )
        return
    except (httpx.RequestError, ValueError):
        await update.message.reply_text(
            "⚠️ Could not reach the exchange rate service. Please try again later.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    rates = data.get("rates", {})
    date = data.get("date", "latest")

    major = ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "CAD", "CNY", "INR"]
    selected = {k: v for k, v in rates.items() if k in major and k != base}

    if not selected:
        selected = dict(sorted(rates.items())[:15])

    lines = [f"*1 {base} =*"]
    for code, value in selected.items():
        lines.append(f"• `{value:.4f}` {code}")

    lines.append(f"\n_Reference date: {date}_")
    lines.append("_⚠️ Indicative rates — not financial advice._")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_convert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /convert <amount> <from> <to> — convert an amount."""
    args = context.args
    if len(args) != 3:
        await update.message.reply_text(
            "Usage: `/convert <amount> <from> <to>`\n"
            "Example: `/convert 100 USD EUR`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    amount_str, from_cur, to_cur = args[0], args[1].upper(), args[2].upper()

    try:
        amount = float(amount_str)
    except ValueError:
        await update.message.reply_text(
            "Please provide a numeric amount, e.g. `100`.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if len(from_cur) != 3 or len(to_cur) != 3:
        await update.message.reply_text(
            "Please use 3-letter currency codes, e.g. `USD` and `EUR`.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if from_cur == to_cur:
        await update.message.reply_text(
            f"{amount:.2f} {from_cur} = {amount:.2f} {to_cur} (no conversion needed).",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        data = await fetch_rates(from_cur)
    except httpx.TimeoutException:
        await update.message.reply_text(
            "⏳ The exchange rate service timed out. Please try again in a moment.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            await update.message.reply_text(
                f"❌ Unknown currency `{from_cur}`. "
                "Use `/currencies` to see supported codes.",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await update.message.reply_text(
                "⚠️ The exchange rate service returned an error. Please try again later.",
                parse_mode=ParseMode.MARKDOWN,
            )
        return
    except (httpx.RequestError, ValueError):
        await update.message.reply_text(
            "⚠️ Could not reach the exchange rate service. Please try again later.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    rates = data.get("rates", {})
    if to_cur not in rates:
        await update.message.reply_text(
            f"❌ Unknown target currency `{to_cur}`. "
            "Use `/currencies` to see supported codes.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    rate = rates[to_cur]
    converted = amount * rate
    date = data.get("date", "latest")

    text = (
        f"*{amount:.2f} {from_cur}* = *{converted:.2f} {to_cur}*\n\n"
        f"Rate: `1 {from_cur} = {rate:.6f} {to_cur}`\n"
        f"_Reference date: {date}_\n\n"
        "_⚠️ Indicative rates — not financial advice._"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_currencies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /currencies — list supported currency codes."""
    try:
        currencies = await fetch_currencies()
    except httpx.TimeoutException:
        await update.message.reply_text(
            "⏳ The currency list service timed out. Please try again in a moment.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError):
        await update.message.reply_text(
            "⚠️ Could not fetch the currency list. Please try again later.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    codes = []
    for item in currencies:
        if isinstance(item, dict):
            code = item.get("iso_code") or item.get("code")
            if code:
                codes.append(code)
        elif isinstance(item, str):
            codes.append(item)

    codes = sorted(set(codes))

    if not codes:
        await update.message.reply_text(
            "No currencies returned by the API. Please try again later.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Telegram limit is 4096 chars per message — chunk the list.
    chunks = []
    current = "`"
    for code in codes:
        if len(current) + len(code) + 4 > 4000:
            chunks.append(current + "`")
            current = "`"
        current += code + "` `"
    if current != "`":
        chunks.append(current + "`")

    header = f"*Supported currencies ({len(codes)}):*\n\n"
    for i, chunk in enumerate(chunks):
        prefix = header if i == 0 else ""
        await update.message.reply_text(
            prefix + chunk,
            parse_mode=ParseMode.MARKDOWN,
        )


async def cmd_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler — logs any unhandled exception gracefully."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ Something went wrong. Please try again.",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            logger.exception("Failed to send error reply.")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Build and run the bot."""
    # Guard: ensure an event loop exists before PTB touches asyncio.
    _ensure_event_loop()

    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN environment variable is not set. "
            "Set it in Render.com → Environment."
        )

    application: Application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("rate", cmd_rate))
    application.add_handler(CommandHandler("convert", cmd_convert))
    application.add_handler(CommandHandler("currencies", cmd_currencies))

    application.add_error_handler(cmd_error)

    # Startup lines — flush=True is only valid on print(), NOT logging.
    print(
        f"🚀 ForexScope Bot is starting... "
        f"Python {sys.version.split()[0]}, python-telegram-bot 21.9",
        flush=True,
    )
    print("✅ Handlers registered: /start /help /rate /convert /currencies", flush=True)
    print("⏳ Beginning polling...", flush=True)

    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
