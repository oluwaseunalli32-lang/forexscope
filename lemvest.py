"""
Lemvest — Forex Funnel Bot (Portuguese Version)
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
# Image Proof Content (Translated to Portuguese)
# ---------------------------------------------------------------------------
PROOFS = [
    {
        "img": "images/forexa1.jpg",
        "caption": "Muito obrigado, Secret! 🙏 Estou realmente gostando dos resultados. Você é incrível, cara! Seu EA tem me ajudado muito ❤️"
    },
    {
        "img": "images/forexa2.jpg",
        "caption": "Lucro após 2 dias. Esta era uma conta padrão com 50 euros e 50 de bônus da corretora. 🚀🔥"
    },
    {
        "img": "images/forexa3.jpg",
        "caption": "Irmão, hoje foi um daqueles dias que é ótimo de ver 😮‍💨 Configurei ontem à noite, e os resultados vieram naturalmente hoje. Estou realmente gostando deste EA, obrigado pela parceria! 💪"
    },
    {
        "img": "images/forexa4.jpg",
        "caption": "Mais de 2.000 de lucro, eu honestamente fiquei sem palavras. Sinceramente, eu não esperava um resultado desses. Estou muito impressionado com o EA 🤯"
    },
    {
        "img": "images/forexa5.jpg",
        "caption": "Hoje, eu não fiquei realmente de olho nisso, haha. Verifiquei a conta depois de um tempo e já tenho $2.525. Obrigado, Secret, você é abençoado 🙏🙏🙏"
    }
]

# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------
def join_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👉 ENTRAR AGORA", url=CHANNEL_URL)]
    ])

# ---------------------------------------------------------------------------
# Background Job (3-hour proof sender)
# ---------------------------------------------------------------------------
async def send_proof(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    chat_id = job.chat_id
    
    proof = random.choice(PROOFS)
    text = f"{proof['caption']}\n\nComece sua jornada hoje 👇"
    
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
        "Você está a um passo de pagar todas as suas dívidas e deixar de ser um "
        "iniciante para se tornar um trader profissional de Forex. Dessa forma, "
        "você pode largar seu emprego e operar em tempo integral."
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
        "Entre agora antes que os links expirem em 5 segundos e você perca a chance!!!!! ⏳ 5",
        reply_markup=join_keyboard()
    )
    
    # Run the 5-second countdown by editing the message every second
    for i in range(4, 0, -1):
        await asyncio.sleep(1)
        await msg2.edit_text(
            f"Entre agora antes que os links expirem em {i} segundos e você perca a chance!!!!! ⏳ {i}",
            reply_markup=join_keyboard()
        )
        
    await asyncio.sleep(1)
    
    # Final countdown message
    await msg2.edit_text(
        "⚠️ O TEMPO ESTÁ ACABANDO!\n\n"
        "Pare de perder tempo. Entre na comunidade Secret EA agora e comece a ver resultados.",
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
        "Não perca os lucros mais fáceis da sua vida. Entre no canal abaixo agora! 👇",
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
