import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))
OWNER_ID = os.getenv("OWNER_ID")

players = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def web_server():
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()


def get_player(user):
    if user.id not in players:
        players[user.id] = {
            "name": user.full_name,
            "diamonds": 0,
            "balance": 0,
            "games": 0
        }

    players[user.id]["name"] = user.full_name
    return players[user.id]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🕵️ Mafia bot ishlayapti!\n\n"
        "/newgame - yangi oyin\n"
        "/join - oyinga qoshilish\n"
        "/players - oyinchilar\n"
        "/startgame - oyinni boshlash\n"
        "/profile - profil\n"
        "/balance - balans\n"
        "/admin - owner panel"
    )


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != OWNER_ID:
        await update.message.reply_text(
            "⛔ Sizda admin huquqi yo'q."
        )
        return

    await update.message.reply_text(
        "👑 OWNER PANEL\n\n"
        "💎 /adddiamonds ID MIQDOR\n"
        "💰 /addbalance ID MIQDOR\n"
        "💎 /bankrot1 ID - almazni 0 qilish\n"
        "💰 /bankrot2 ID - money'ni 0 qilish"
    )


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = get_player(user)

    await update.message.reply_text(
        f"👤 PROFIL\n\n"
        f"📝 Ism: {player['name']}\n"
        f"🆔 ID: {user.id}\n\n"
        f"💎 Almaz: {player['diamonds']}\n"
        f"💰 Balans: {player['balance']}\n"
        f"🎮 O'yinlar: {player['games']}"
    )


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = get_player(user)

    await update.message.reply_text(
        f"💰 BALANS\n\n"
        f"💎 Almaz: {player['diamonds']}\n"
        f"💰 Balans: {player['balance']}"
    )


async def adddiamonds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != OWNER_ID:
        await update.message.reply_text(
            "⛔ Bu buyruq faqat OWNER uchun."
        )
        return

    if len(context.args) != 2:
        await update.message.reply_text(
            "❌ Format:\n/adddiamonds ID MIQDOR"
        )
        return

    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "❌ ID va miqdor raqam bo'lishi kerak."
        )
        return

    if amount <= 0:
        await update.message.reply_text(
            "❌ Miqdor 0 dan katta bo'lishi kerak."
        )
        return

    if target_id not in players:
        players[target_id] = {
            "name": f"ID {target_id}",
            "diamonds": 0,
            "balance": 0,
            "games": 0
        }

    players[target_id]["diamonds"] += amount

    await update.message.reply_text(
        f"✅ Almaz berildi!\n\n"
        f"👤 ID: {target_id}\n"
        f"💎 Qo'shildi: {amount}\n"
        f"💎 Jami: {players[target_id]['diamonds']}"
    )


async def addbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != OWNER_ID:
        await update.message.reply_text(
            "⛔ Bu buyruq faqat OWNER uchun."
        )
        return

    if len(context.args) != 2:
        await update.message.reply_text(
            "❌ Format:\n/addbalance ID MIQDOR"
        )
        return

    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "❌ ID va miqdor raqam bo'lishi kerak."
        )
        return

    if amount <= 0:
        await update.message.reply_text(
            "❌ Miqdor 0 dan katta bo'lishi kerak."
        )
        return

    if target_id not in players:
        players[target_id] = {
            "name": f"ID {target_id}",
            "diamonds": 0,
            "balance": 0,
            "games": 0
        }

    players[target_id]["balance"] += amount

    await update.message.reply_text(
        f"✅ Balans to'ldirildi!\n\n"
        f"👤 ID: {target_id}\n"
        f"💰 Qo'shildi: {amount}\n"
        f"💰 Jami: {players[target_id]['balance']}"
    )


async def bankrupt1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != OWNER_ID:
        await update.message.reply_text(
            "⛔ Bu buyruq faqat OWNER uchun."
        )
        return

    if len(context.args) != 1:
        await update.message.reply_text(
            "❌ Format:\n/bankrot1 ID"
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ ID raqam bo'lishi kerak."
        )
        return

    if target_id not in players:
        await update.message.reply_text(
            "❌ Bu ID bilan o'yinchi topilmadi."
        )
        return

    players[target_id]["diamonds"] = 0

    await update.message.reply_text(
        f"💎 BANKROT 1\n\n"
        f"👤 ID: {target_id}\n"
        f"💎 Almaz: 0"
    )


async def bankrupt2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != OWNER_ID:
        await update.message.reply_text(
            "⛔ Bu buyruq faqat OWNER uchun."
        )
        return

    if len(context.args) != 1:
        await update.message.reply_text(
            "❌ Format:\n/bankrot2 ID"
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ ID raqam bo'lishi kerak."
        )
        return

    if target_id not in players:
        await update.message.reply_text(
            "❌ Bu ID bilan o'yinchi topilmadi."
        )
        return

    players[target_id]["balance"] = 0

    await update.message.reply_text(
        f"💰 BANKROT 2\n\n"
        f"👤 ID: {target_id}\n"
        f"💰 Balans: 0"
    )


async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎭 Yangi oyin ochildi!\n\n"
        "Oyinga qoshilish uchun /join bosing."
    )


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_player(user)

    await update.message.reply_text(
        f"✅ {user.full_name}, siz oyinga qoshildingiz!"
    )


async def players_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not players:
        await update.message.reply_text(
            "👥 Hozircha oyinchilar royxati bosh."
        )
        return

    text = "👥 O'YINCHILAR:\n\n"

    for number, player in enumerate(players.values(), start=1):
        text += f"{number}. {player['name']}\n"

    await update.message.reply_text(text)


async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not players:
        await update.message.reply_text(
            "⚠️ Oyinda hech kim yo'q!"
        )
        return

    for player in players.values():
        player["games"] += 1

    await update.message.reply_text(
        f"🎭 O'yin boshlanishga tayyor!\n\n"
        f"👥 O'yinchilar soni: {len(players)}"
    )


def main():
    print("MAIN BOSHLANDI", flush=True)

    if not TOKEN:
        raise RuntimeError("BOT_TOKEN topilmadi!")

    if not OWNER_ID:
        raise RuntimeError("OWNER_ID topilmadi!")

    print("TOKEN TOPILDI", flush=True)
    print("OWNER_ID TOPILDI", flush=True)

    threading.Thread(
        target=web_server,
        daemon=True
    ).start()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("adddiamonds", adddiamonds))
    app.add_handler(CommandHandler("addbalance", addbalance))
    app.add_handler(CommandHandler("bankrot1", bankrupt1))
    app.add_handler(CommandHandler("bankrot2", bankrupt2))
    app.add_handler(CommandHandler("newgame", newgame))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("players", players_command))
    app.add_handler(CommandHandler("startgame", startgame))

    print("BOT ISHLADI", flush=True)

    app.run_polling()


if __name__ == "__main__":
    main()
