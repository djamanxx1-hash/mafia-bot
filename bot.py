import os
import random
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


TOKEN = os.getenv("BOT_TOKEN")

games = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🕵️ Mafia botga xush kelibsiz!\n\n"
        "O'yinni boshlash uchun:\n"
        "/newgame — yangi o'yin\n"
        "/join — o'yinga qo'shilish\n"
        "/players — o'yinchilarni ko'rish\n"
        "/startgame — o'yinni boshlash"
    )


async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    games[chat_id] = {
        "players": {},
        "started": False
    }

    await update.message.reply_text(
        "🎭 Yangi Mafia o'yini yaratildi!\n\n"
        "Qo'shilish uchun /join ni bosing."
    )


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in games:
        await update.message.reply_text(
            "❌ Avval /newgame buyrug'i bilan o'yin yarating."
        )
        return

    if games[chat_id]["started"]:
        await update.message.reply_text(
            "❌ O'yin allaqachon boshlangan."
        )
        return

    games[chat_id]["players"][user.id] = user.first_name

    await update.message.reply_text(
        f"✅ {user.first_name} o'yinga qo'shildi!"
    )


async def players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id not in games:
        await update.message.reply_text(
            "❌ Hozircha o'yin yo'q."
        )
        return

    player_list = games[chat_id]["players"]

    if not player_list:
        await update.message.reply_text(
            "👥 Hozircha hech kim qo'shilmagan."
        )
        return

    text = "👥 O'yinchilar:\n\n"

    for number, name in enumerate(player_list.values(), 1):
        text += f"{number}. {name}\n"

    await update.message.reply_text(text)


async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id not in games:
        await update.message.reply_text(
            "❌ Avval /newgame buyrug'ini bosing."
        )
        return

    player_ids = list(games[chat_id]["players"].keys())

    if len(player_ids) < 4:
        await update.message.reply_text(
            "❌ O'yinni boshlash uchun kamida 4 ta o'yinchi kerak."
        )
        return

    roles = ["Mafia"]

    while len(roles) < len(player_ids):
        roles.append("Tinch aholi")

    random.shuffle(roles)

    games[chat_id]["started"] = True

    for user_id, role in zip(player_ids, roles):
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎭 Sizning rolingiz: {role}"
            )
        except Exception:
            pass

    await update.message.reply_text(
        "🎬 O'yin boshlandi!\n"
        "Rollar o'yinchilarga shaxsiy xabar orqali yuborildi."
    )


def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN topilmadi!")

    # Render uchun portni ochamiz
    threading.Thread(target=run_server, daemon=True).start()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newgame", newgame))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("players", players))
    app.add_handler(CommandHandler("startgame", startgame))

    print("🤖 Bot ishga tushdi!")

    app.run_polling()


if __name__ == "__main__":
    main()
