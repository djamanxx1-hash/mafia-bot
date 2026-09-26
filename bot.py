import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))
OWNER_ID = os.getenv("OWNER_ID")


# O'yinchilar
players_list = []


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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🕵️ Mafia bot ishlayapti!\n\n"
        "/newgame - yangi oyin\n"
        "/join - oyinga qoshilish\n"
        "/players - oyinchilar\n"
        "/startgame - oyinni boshlash\n"
        "/admin - owner panel"
    )


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if user_id != OWNER_ID:
        await update.message.reply_text(
            "⛔ Sizda admin huquqi yo'q."
        )
        return

    await update.message.reply_text(
        "👑 OWNER PANEL\n\n"
        "Siz bot egasisiz.\n\n"
        "✅ Admin tizimi ishlayapti!"
    )


async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    players_list.clear()

    await update.message.reply_text(
        "🎭 Yangi oyin ochildi!\n\n"
        "Oyinga qoshilish uchun /join bosing."
    )


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    for player in players_list:
        if player["id"] == user.id:
            await update.message.reply_text(
                "⚠️ Siz allaqachon oyindasiz!"
            )
            return

    players_list.append({
        "id": user.id,
        "name": user.full_name
    })

    await update.message.reply_text(
        f"✅ {user.full_name}, siz oyinga qoshildingiz!"
    )


async def players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not players_list:
        await update.message.reply_text(
            "👥 Hozircha oyinchilar royxati bosh."
        )
        return

    text = "👥 O'yinchilar:\n\n"

    for number, player in enumerate(players_list, start=1):
        text += f"{number}. {player['name']}\n"

    await update.message.reply_text(text)


async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not players_list:
        await update.message.reply_text(
            "⚠️ Oyinda hech kim yo'q!"
        )
        return

    await update.message.reply_text(
        f"🎭 O'yin boshlanishga tayyor!\n\n"
        f"👥 O'yinchilar soni: {len(players_list)}"
    )


def main():
    print("MAIN BOSHLANDI", flush=True)

    if not TOKEN:
        print("XATO: BOT_TOKEN TOPILMADI!", flush=True)
        raise RuntimeError("BOT_TOKEN topilmadi!")

    if not OWNER_ID:
        print("XATO: OWNER_ID TOPILMADI!", flush=True)
        raise RuntimeError("OWNER_ID topilmadi!")

    print("TOKEN TOPILDI", flush=True)
    print("OWNER_ID TOPILDI", flush=True)

    threading.Thread(
        target=web_server,
        daemon=True
    ).start()

    print("WEB SERVER ISHLADI", flush=True)

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("newgame", newgame))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("players", players))
    app.add_handler(CommandHandler("startgame", startgame))

    print("BOT ISHLADI", flush=True)
    print("TELEGRAM POLLING BOSHLANDI", flush=True)

    app.run_polling()


if __name__ == "__main__":
    main()
