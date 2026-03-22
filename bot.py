import os
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from database import init_db, add_expense, get_summary
from voice_handler import transcribe_voice, extract_amount, detect_category
from excel_export import export_to_excel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")

WAIT_AMOUNT, WAIT_CATEGORY, WAIT_CONFIRM = range(3)

CATEGORIES = [
    ["🍔 Oziq-ovqat", "🚗 Transport"],
    ["👕 Kiyim", "💊 Sog'liq"],
    ["🏠 Kommunal", "🎮 Ko'ngilochar"],
    ["📦 Boshqa"]
]

main_keyboard = ReplyKeyboardMarkup(
    [
        ["➕ Harajat qo'shish", "🎙 Ovozli kiritish"],
        ["📊 Oylik hisobot", "📅 Haftalik hisobot"],
        ["📥 Excel eksport", "❓ Yordam"]
    ],
    resize_keyboard=True
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Salom! Men sizning harajatlaringizni hisoblab beraman.\n\n"
        "Ovozli xabar yuboring yoki quyidagi tugmalardan foydalaning:",
        reply_markup=main_keyboard
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Foydalanish yo'riqnomasi:*\n\n"
        "🎙 *Ovozli kiritish:* Ovozli xabar yuboring\n"
        "Masalan: _'Taksi uchun 15 ming to'ladim'_\n\n"
        "➕ *Qo'lda kiritish:* Tugma orqali\n\n"
        "📊 *Hisobotlar:* Oylik yoki haftalik\n\n"
        "📥 *Excel:* Barcha harajatlarni yuklab oling",
        parse_mode="Markdown",
        reply_markup=main_keyboard
    )

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎙 Ovoz qabul qilindi, tahlil qilinmoqda...")
    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    file_path = f"voice_{update.effective_user.id}.ogg"
    await file.download_to_drive(file_path)
    text = transcribe_voice(file_path)

    if not text:
        await update.message.reply_text(
            "❌ Ovozni tushunib bo'lmadi. Aniqroq gapiring.\n"
            "Masalan: _'Oziq-ovqatga 50 ming so'm sarfladim'_",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    amount = extract_amount(text)
    category = detect_category(text)

    if not amount:
        await update.message.reply_text(
            f"🔍 Eshitildi: _{text}_\n\n"
            "❌ Miqdorni aniqlab bo'lmadi.\n"
            "Masalan: _'Taksi uchun 20 ming to'ladim'_",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    context.user_data["pending"] = {
        "amount": amount,
        "category": category,
        "description": text
    }

    confirm_keyboard = ReplyKeyboardMarkup(
        [["✅ Ha, to'g'ri", "✏️ Tahrirlash"], ["❌ Bekor qilish"]],
        resize_keyboard=True
    )

    await update.message.reply_text(
        f"🔍 Eshitildi: _{text}_\n\n"
        f"💰 Miqdor: *{amount:,.0f} so'm*\n"
        f"📂 Kategoriya: *{category}*\n\n"
        "To'g'rimi?",
        parse_mode="Markdown",
        reply_markup=confirm_keyboard
    )
    return WAIT_CONFIRM

async def confirm_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "✅ Ha, to'g'ri":
        pending = context.user_data.get("pending")
        if pending:
            add_expense(
                update.effective_user.id,
                pending["amount"],
                pending["category"],
                pending["description"]
            )
            await update.message.reply_text(
                f"✅ Saqlandi!\n💰 {pending['amount']:,.0f} so'm → {pending['category']}",
                reply_markup=main_keyboard
            )
    elif text == "❌ Bekor qilish":
        await update.message.reply_text("❌ Bekor qilindi.", reply_markup=main_keyboard)
    else:
        await update.message.reply_text("✅ yoki ❌ tugmasini bosing.", reply_markup=main_keyboard)
        return WAIT_CONFIRM

    context.user_data.pop("pending", None)
    return ConversationHandler.END

async def manual_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💰 Harajat miqdorini kiriting (so'mda):\nMasalan: *50000*",
        parse_mode="Markdown"
    )
    return WAIT_AMOUNT

async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.replace(" ", "").replace(",", ""))
        context.user_data["amount"] = amount
        cat_keyboard = ReplyKeyboardMarkup(CATEGORIES, resize_keyboard=True)
        await update.message.reply_text("📂 Kategoriyani tanlang:", reply_markup=cat_keyboard)
        return WAIT_CATEGORY
    except ValueError:
        await update.message.reply_text("❌ Faqat raqam kiriting. Masalan: *50000*", parse_mode="Markdown")
        return WAIT_AMOUNT

async def get_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = update.message.text
    amount = context.user_data.get("amount", 0)
    add_expense(update.effective_user.id, amount, category)
    await update.message.reply_text(
        f"✅ Saqlandi!\n💰 {amount:,.0f} so'm → {category}",
        reply_markup=main_keyboard
    )
    return ConversationHandler.END

async def monthly_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    summary, total = get_summary(update.effective_user.id, "month")
    if not summary:
        await update.message.reply_text("📊 Bu oy hali harajat yo'q.", reply_markup=main_keyboard)
        return
    text = "📊 *Bu oylik hisobot:*\n\n"
    for cat, amount in sorted(summary.items(), key=lambda x: -x[1]):
        percent = (amount / total) * 100
        text += f"{cat}: *{amount:,.0f} so'm* ({percent:.1f}%)\n"
    text += f"\n💰 *Jami: {total:,.0f} so'm*"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard)

async def weekly_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    summary, total = get_summary(update.effective_user.id, "week")
    if not summary:
        await update.message.reply_text("📅 Bu hafta hali harajat yo'q.", reply_markup=main_keyboard)
        return
    text = "📅 *Bu haftalik hisobot:*\n\n"
    for cat, amount in sorted(summary.items(), key=lambda x: -x[1]):
        percent = (amount / total) * 100
        text += f"{cat}: *{amount:,.0f} so'm* ({percent:.1f}%)\n"
    text += f"\n💰 *Jami: {total:,.0f} so'm*"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard)

async def excel_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📥 Excel fayl tayyorlanmoqda...")
    filename = export_to_excel(update.effective_user.id, "month")
    with open(filename, "rb") as f:
        await update.message.reply_document(
            document=f,
            filename=filename,
            caption="📊 Bu oylik harajatlaringiz"
        )
    os.remove(filename)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📊 Oylik hisobot":
        await monthly_report(update, context)
    elif text == "📅 Haftalik hisobot":
        await weekly_report(update, context)
    elif text == "📥 Excel eksport":
        await excel_export(update, context)
    elif text == "❓ Yordam":
        await help_command(update, context)
    elif text == "🎙 Ovozli kiritish":
        await update.message.reply_text("🎙 Ovozli xabar yuboring!")

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    voice_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.VOICE, handle_voice)],
        states={WAIT_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_expense)]},
        fallbacks=[]
    )

    manual_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Harajat qo'shish$"), manual_add)],
        states={
            WAIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
            WAIT_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_category)],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(voice_conv)
    app.add_handler(manual_conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
    PORT = int(os.environ.get("PORT", 10000))

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()
