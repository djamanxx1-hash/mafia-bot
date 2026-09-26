import os
import random
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

games = {}


# =========================
# RENDER WEB SERVER
# =========================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        return


def run_web_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    server.serve_forever()


# =========================
# GAME DATA
# =========================

def get_game(chat_id):

    if chat_id not in games:
        games[chat_id] = {
            "players": [],
            "roles": {},
            "alive": [],
            "started": False,
            "phase": "waiting"
        }

    return games[chat_id]


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🕵️ Mafia botga xush kelibsiz!\n\n"
        "🎭 O'yinni boshlash uchun:\n"
        "/newgame — yangi o'yin\n"
        "/join — o'yinga qo'shilish\n"
        "/players — o'yinchilarni ko'r
