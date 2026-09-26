import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))


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
        "/startgame - oyinni boshlash"
    )


async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎭 Yangi oyin ochildi!")


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Siz oyinga qoshildingiz!")


async def players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👥 Hozircha oyinchilar royxati bosh.")


async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎭 Oyinni boshlash uchun tayyor!")


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN topilmadi!")

    threading.Thread(
        target=web_server,
        daemon=True
    ).start()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newgame", newgame))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("players", players))
    app.add_handler(CommandHandler("startgame", startgame))

    print("BOT ISHLADI")
    print("PORT:", PORT)

    app.run_polling()


if __name__ == "__main__":
    main()
