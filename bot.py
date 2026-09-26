import os
import random
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))

games = {}


# =========================
# RENDER PORT SERVER
# =========================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def run_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    server.serve_forever()


# =========================
# GAME
# =========================

def get_game(chat_id):
    if chat_id not in games:
        games[chat_id] = {
            "players": [],
            "roles": {},
            "alive": [],
            "started": False,
            "phase": "waiting",
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
        "/players — o'yinchilarni ko'rish\n"
        "/startgame — o'yinni boshlash\n"
        "/status — o'yin holati"
    )


# =========================
# NEW GAME
# =========================

async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    games[chat_id] = {
        "players": [],
        "roles": {},
        "alive": [],
        "started": False,
        "phase": "waiting",
    }

    await update.message.reply_text(
        "🎭 Yangi Mafia o'yini ochildi!\n\n"
        "O'yinga qo'shilish uchun:\n"
        "👉 /join\n\n"
        "👥 O'yinchilarni ko'rish:\n"
        "👉 /players"
    )


# =========================
# JOIN
# =========================

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id
    game = get_game(chat_id)

    if game["started"]:
        await update.message.reply_text(
            "❌ O'yin allaqachon boshlangan!"
        )
        return

    user = update.effective_user

    for player in game["players"]:
        if player["id"] == user.id:
            await update.message.reply_text(
                "⚠️ Siz allaqachon o'yindasiz!"
            )
            return

    game["players"].append({
        "id": user.id,
        "name": user.first_name,
    })

    await update.message.reply_text(
        f"✅ {user.first_name} o'yinga qo'shildi!\n\n"
        f"👥 O'yinchilar soni: {len(game['players'])}"
    )


# =========================
# PLAYERS
# =========================

async def players(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id
    game = get_game(chat_id)

    if not game["players"]:
        await update.message.reply_text(
            "👥 Hozircha o'yinchilar yo'q."
        )
        return

    text = "👥 O'yinchilar:\n\n"

    for i, player in enumerate(game["players"], 1):
        text += f"{i}. {player['name']}\n"

    await update.message.reply_text(text)


# =========================
# START GAME
# =========================

async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id
    game = get_game(chat_id)

    if game["started"]:
        await update.message.reply_text(
            "❌ O'yin allaqachon boshlangan!"
        )
        return

    count = len(game["players"])

    if count < 4:
        await update.message.reply_text(
            "❌ O'yinni boshlash uchun kamida 4 ta o'yinchi kerak!"
        )
        return

    roles = []

    mafia_count = max(1, count // 4)

    roles += ["🔪 Mafia"] * mafia_count
    roles += ["👨‍⚕️ Doktor"]
    roles += ["🕵️ Komissar"]

    while len(roles) < count:
        roles.append("👨‍🌾 Fuqaro")

    random.shuffle(roles)

    game["roles"] = {}

    for player, role in zip(game["players"], roles):
        game["roles"][player["id"]] = role

    game["alive"] = [
        player["id"]
        for player in game["players"]
    ]

    game["started"] = True
    game["phase"] = "night"

    await update.message.reply_text(
        "🎭 MAFIA O'YINI BOSHLANDI!\n\n"
        "🌙 KECHA BOSHLANDI.\n\n"
        "📩 Har bir o'yinchiga uning roli "
        "shaxsiy xabarda yuborildi."
    )

    for player in game["players"]:

        try:

            await context.bot.send_message(
                chat_id=player["id"],
                text=(
                    "🎭 SIZNING ROLINGIZ\n\n"
                    f"{game['roles'][player['id']]}\n\n"
                    "🤫 Rolingizni hech kimga aytmang!"
                )
            )

        except Exception:
            pass


# =========================
# STATUS
# =========================

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id
    game = get_game(chat_id)

    if not game["started"]:
        await update.message.reply_text(
            "⏳ Hozircha o'yin boshlanmagan."
        )
        return

    alive_names = []

    for player in game["players"]:

        if player["id"] in game["alive"]:
            alive_names.append(player["name"])

    await update.message.reply_text(
        "🎭 O'YIN HOLATI\n\n"
        f"🌙 Bosqich: {game['phase']}\n"
        f"❤️ Tirik o'yinchilar: {len(alive_names)}\n\n"
        + "\n".join(
            f"• {name}"
            for name in alive_names
       
