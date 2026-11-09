"""
Lemvest — Forex Funnel Bot
"""

import asyncio
import logging
import os
import sys
import random

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

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
    "https://t.me/+RxOYpIb69gs1MWUx",
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
# Image Proof Content
# ---------------------------------------------------------------------------
PROOFS = [
    {
        "img": "images/forexa1.jpg",
        "caption": "Thank you so much, Secret! 🙏 I'm really enjoying the results. You're amazing, man! Your EA has been helping me a lot ❤️"
    },
    {
        "img": "images/forexa2.jpg",
        "caption": "Profit after 2 days. This was a standard account with 50 euro and 50 broker bonus. 🚀🔥"
    },
    {
        "img": "images/forexa3.jpg",
        "caption": "Brother, today was one of those days that's great to see 😮‍💨 I set it up last night, and the results came naturally today. I'm really enjoying this EA, thanks for the partnership! 💪"
    },
    {
        "img": "images/forexa4.jpg",
        "caption": "More than 2,000 in profit, I was honestly speechless. Honestly, I wasn't expecting a result like this. I'm really impressed with the EA 🤯"
    },
    {
        "img": "images/forexa5.jpg",
        "caption": "Today, I didn't really keep a close eye on it, haha. I checked the account after a while and I already have $2,525. Thank you, Secret, you are blessed 🙏🙏🙏"
    }
]

# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------
def join_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👉 JOIN NOW", url=CHANNEL_URL)]
    ])

# ---------------------------------------------------------------------------
# Background Job (3-hour proof sender)
# ---------------------------------------------------------------------------
async def send_proof(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    chat_id = job.chat_id
    
    proof = random.choice(PROOFS)
    text = f"{proof['caption']}\n\nStart your journey today 👇"
    
    try:
        with open(proof["img"], "rb") as photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=text,
                reply_markup=join_keyboard()
            )
        logger.info(f"Sent 3h proof image {proof['img']} to chat {chat_id}")
    except FileNotFoundError:
        logger.error(f"Missing image file: {proof['img']}. Check your GitHub repo.")
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=join_keyboard()
        )
    except Exception as e:
        logger.warning(f"Could not send proof to {chat_id}: {e}")

# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    
    # 1. Send the initial hook message (NO BUTTON)
    msg1 = await update.message.reply_text(
        "You're one step away from paying off all your debt and going from a "
        "newbie to a professional Forex trader, this way you can quit your day "
        "job and trade full time."
    )
    
    # 2. Wait 10 seconds for them to read it
    await asyncio.sleep(10)
    
    # 3. Delete the first message
    try:
        await msg1.delete()
    except Exception:
        pass # Ignore if already deleted
        
    # 4. Send the countdown message (WITH BUTTON)
    msg2 = await update.message.reply_text(
        "Join Now before the links expire in 5 seconds and you will miss out!!!!! ⏳ 5",
        reply_markup=join_keyboard()
    )
    
    # Run the 5-second countdown by editing the message every second
    for i in range(4, 0, -1):
        await asyncio.sleep(1)
        await msg2.edit_text(
            f"Join Now before the links expire in {i} seconds and you will miss out!!!!! ⏳ {i}",
            reply_markup=join_keyboard()
        )
        
    await asyncio.sleep(1)
    
    # Final countdown message
    await msg2.edit_text(
        "⚠️ TIME IS RUNNING OUT!\n\n"
        "Stop wasting time. Join the Secret EA community now and start seeing results.",
        reply_markup=join_keyboard()
    )

    # 5. Schedule the 3-hour background timer
    job_name = f"proof_{chat_id}"
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    
    if not current_jobs:
        context.job_queue.run_repeating(
            send_proof,
            interval=3 * 3600, # 3 hours
            first=3 * 3600,    # First send in 3 hours
            chat_id=chat_id,
            name=job_name,
        )
        logger.info(f"Scheduled 3h proof loop for chat {chat_id}")

async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Don't miss out on the easiest profits of your life. Join the channel below now! 👇",
        reply_markup=join_keyboard(),
    )

# ---------------------------------------------------------------------------
# Global error handler
# ---------------------------------------------------------------------------
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling update:", exc_info=context.error)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN environment variable is not set.", flush=True)
        sys.exit(1)

    print("🚀 Starting Forex Funnel bot...", flush=True)

    application: Application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback))
    application.add_error_handler(on_error)

    print("✅ Handlers registered.", flush=True)
    print("⏳ Polling for updates...", flush=True)

    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )

if __name__ == "__main__":
    main()
