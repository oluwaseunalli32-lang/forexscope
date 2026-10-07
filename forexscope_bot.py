"""
ForexScope Bot — a simple Telegram bot for checking forex exchange rates.
Deployed as a Background Worker on Render.com.

Data source: Frankfurter API (https://api.frankfurter.dev/v2)
  - Free, no API key, no rate caps for normal use
  - 201 currencies, daily reference rates from 84 central banks
  - No signup required

Author: Senior Python Developer
"""

import asyncio
import logging
import os
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

# Read the token from the environment. Never hardcode secrets.
TELEGRAM_BOT_TOKEN: Optional[str] = os.environ.get("TELEGRAM_BOT_TOKEN")

# Frankfurter API base URL — public, no API key.
FRANKFURTER_BASE: str = "https://api.frankfurter.dev/v2"

# Timeout for external HTTP calls (seconds). Keeps the bot responsive
# even if the API is slow.
HTTP_TIMEOUT: float = 10.0

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defensive asyncio.get_event_loop() guard
# ---------------------------------------------------------------------------
# Python 3.14+ and some 3.12+ environments can raise DeprecationWarning
# or RuntimeError if get_event_loop() is called without a running loop.
# This guard ensures the bot starts cleanly on Render.com.

def _ensure_event_loop() -> None:
    """Create an event loop if none exists in the current thread.

    python-telegram-bot 21.9 uses asyncio internally. Calling
    asyncio.get_event_loop() when no loop exists triggers warnings
    or errors on newer Python versions. We explicitly create one.
    """
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        # No current event loop — create a new one.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger.info("Created a new asyncio event loop.", flush=True)


# ---------------------------------------------------------------------------
# External API helper (defensive)
# ---------------------------------------------------------------------------

async def fetch_rates(base: str) -> dict:
    """Fetch latest exchange rates for a base currency.

    Returns a dict like:
        {"base": "USD", "date": "2026-10-07", "rates": {...}}

    Raises httpx.HTTPError or ValueError on failure — the caller
    must handle it so the bot never crashes.
    """
    url = f"{FRANKFURTER_BASE}/rates?base={base.upper()}"
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

    # Frankfurter v2 returns {"base": ..., "date": ..., "rates": {...}}
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

    # v2 returns a list of dicts: [{"iso_code": "USD", ...}, ...]
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

    # Defensive: never let an API failure crash the bot.
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

    # Build a compact list of major currencies for readability.
    # Show all rates if the user used a less common base.
    major = ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "CAD", "CNY", "INR"]
    selected = {k: v for k, v in rates.items() if k in major and k != base}

    # If the base is not a major currency, show a broader set.
    if not selected:
        # Sort by currency code and take the first 15.
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

    # Validate amount.
    try:
        amount = float(amount_str)
    except ValueError:
        await update.message.reply_text(
            "Please provide a numeric amount, e.g. `100`.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Validate currency codes.
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

    # Defensive API call.
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

    # Extract ISO codes. Frankfurter v2 returns dicts with "iso_code".
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

    # Telegram messages have a 4096-character limit.
    # Build chunks of codes.
    chunks = []
    current = "`"
    for code in codes:
        if len(current) + len(code) + 3 > 4000:
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
    """Global error handler — logs any unhandled exception so the bot
    does not crash silently."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    # Try to inform the user gracefully.
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ Something went wrong. Please try again.",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            # If even the error reply fails, just log it.
            logger.exception("Failed to send error reply.")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Build and run the bot."""
    # Guard: ensure an event loop exists before python-telegram-bot
    # tries to call asyncio.get_event_loop() internally.
    _ensure_event_loop()

    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN environment variable is not set. "
            "Set it in Render.com → Environment."
        )

    # Build the application.
    application: Application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    # Register handlers.
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("rate", cmd_rate))
    application.add_handler(CommandHandler("convert", cmd_convert))
    application.add_handler(CommandHandler("currencies", cmd_currencies))

    # Global error handler.
    application.add_error_handler(cmd_error)

    # Startup line — flush=True so it appears immediately in Render logs.
    print(
        "🚀 ForexScope Bot is starting... "
        f"Python {os.sys.version.split()[0]}, "
        f"python-telegram-bot 21.9",
        flush=True,
    )
    print("✅ Handlers registered: /start /help /rate /convert /currencies", flush=True)
    print("⏳ Beginning polling...", flush=True)

    # Run the bot. run_polling() blocks until stopped.
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,  # Ignore messages sent while the bot was offline.
    )


if __name__ == "__main__":
    main()
