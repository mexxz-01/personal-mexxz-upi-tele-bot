import io
import logging
import re
import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())
from datetime import datetime
from collections import defaultdict
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask
from PIL import Image

# ============ CONFIG ============
BOT_TOKEN = "8824818245:AAGqUx-OglmiHwH4twoOrN0ILlqFS-DiIQU"
UPI_ID = "mexxz@slc"
PAYEE_NAME = "MEXXZ"
LOGO_PATH = "logo.png"
# ================================

qr_logs = []
current_upi = UPI_ID
banned_users = set()
user_history = defaultdict(list)
known_users = set()

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

def is_valid_upi(upi: str) -> bool:
    pattern = r'^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}$'
    return bool(re.match(pattern, upi))

def create_upi_link(amount, note=""):
    link = f"upi://pay?pa={current_upi}&pn={PAYEE_NAME}&am={amount:.2f}&cu=INR"
    if note:
        link += f"&tn={note}"
    return link

def make_qr(data):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=12,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=SolidFillColorMask(
            back_color=(255, 255, 255),
            front_color=(15, 23, 42)
        )
    ).convert("RGB")

    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        size = int(img.size[0] * 0.22)
        logo = logo.resize((size, size), Image.Resampling.LANCZOS)
        pos = ((img.size[0] - size) // 2, (img.size[1] - size) // 2)
        img.paste(logo, pos, logo)
    except:
        pass

    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in banned_users:
        await update.message.reply_text("You are banned.")
        return
    known_users.add(user_id)
    await update.message.reply_text("enter amount 😺🙏")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🔐 *Admin Panel*\n\n"
        f"UPI: `{current_upi}`\n"
        f"Total QRs: {len(qr_logs)}\n"
        f"Users: {len(known_users)}\n"
        f"Banned: {len(banned_users)}\n\n"
        "*Commands:*\n"
        "`/setupi upi@bank`\n"
        "`/ban userid`\n"
        "`/unban userid`\n"
        "`/broadcast message`\n"
        "`/logs`\n"
        "`/clearlogs`\n"
        "`/history`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def set_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_upi
    if not context.args:
        await update.message.reply_text("Usage: /setupi name@oksbi")
        return
    new_upi = context.args[0]
    if not is_valid_upi(new_upi):
        await update.message.reply_text("Invalid UPI format")
        return
    current_upi = new_upi
    await update.message.reply_text(f"✅ UPI set to `{current_upi}`", parse_mode="Markdown")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /ban 123456789")
        return
    try:
        uid = int(context.args[0])
        banned_users.add(uid)
        await update.message.reply_text(f"🚫 Banned {uid}")
    except:
        await update.message.reply_text("Invalid ID")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /unban 123456789")
        return
    try:
        uid = int(context.args[0])
        banned_users.discard(uid)
        await update.message.reply_text(f"✅ Unbanned {uid}")
    except:
        await update.message.reply_text("Invalid ID")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /broadcast Hello")
        return
    msg = " ".join(context.args)
    count = 0
    for uid in list(known_users):
        try:
            await context.bot.send_message(uid, f"📢 {msg}")
            count += 1
        except:
            pass
    await update.message.reply_text(f"✅ Sent to {count} users")

async def show_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not qr_logs:
        await update.message.reply_text("No logs yet")
        return
    text = "📜 Recent:\n\n"
    for log in qr_logs[-8:]:
        text += f"• ₹{log['amount']} | {log['time']}\n"
    await update.message.reply_text(text)

async def clear_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qr_logs.clear()
    await update.message.reply_text("✅ Logs cleared")

async def my_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    history = user_history.get(uid, [])
    if not history:
        await update.message.reply_text("No history yet")
        return
    text = "🧾 Your History:\n\n"
    for h in history[-10:]:
        text += f"• ₹{h['amount']} | {h['time']}\n"
    await update.message.reply_text(text)

async def auto_delete(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    try:
        await context.bot.delete_message(job.data["chat_id"], job.data["message_id"])
    except:
        pass

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in banned_users:
        await update.message.reply_text("You are banned.")
        return

    known_users.add(user_id)
    text = update.message.text.strip()

    if text.startswith("/"):
        return

    parts = text.split(maxsplit=1)
    try:
        amount = float(parts[0])
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("Please enter a valid amount")
        return

    note = parts[1] if len(parts) > 1 else ""
    upi_link = create_upi_link(amount, note)
    qr = make_qr(upi_link)

    entry = {
        "amount": amount,
        "note": note,
        "time": datetime.now().strftime("%d %b %I:%M %p"),
        "upi": current_upi
    }
    qr_logs.append(entry)
    user_history[user_id].append(entry)

    # Simple caption only
    caption = f"💰 ₹{amount:.2f}"
    if note:
        caption += f"\n📝 {note}"

    sent = await update.message.reply_photo(
        photo=InputFile(qr, filename="qr.png"),
        caption=caption
    )

    # Auto delete after 10 minutes
    context.job_queue.run_once(
        auto_delete, 600,
        data={"chat_id": sent.chat_id, "message_id": sent.message_id}
    )

    await update.message.reply_text("ur qr generated enter another amount")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin_mexxz", admin_panel))
    app.add_handler(CommandHandler("setupi", set_upi))
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(CommandHandler("unban", unban_user))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("logs", show_logs))
    app.add_handler(CommandHandler("clearlogs", clear_logs))
    app.add_handler(CommandHandler("history", my_history))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    print("Bot is running...")
    app.run_polling()
if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except RuntimeError:
        # Fallback for some environments
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
