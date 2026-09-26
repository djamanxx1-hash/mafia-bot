import os
import random
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

games = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def run_web_server():
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()


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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Mafia botga xush kelibsiz!\n\n"
        "/newgame - yangi oyin\n"
        "/join - oyinga qoshilish\n"
        "/players - oyinchilar\n"
        "/startgame - oyinni boshlash\n"
        "/status - oyin holati"
    )


async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    games[chat_id] = {
        "players": [],
        "roles": {},
        "alive": [],
        "started": False,
        "phase": "waiting"
    }

    await update.message.reply_text(
        "Yangi Mafia oyini ochildi!\n\n"
        "/join - oyinga qoshilish\n"
        "/players - oyinchilarni korish"
    )


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = get_game(chat_id)
    user = update.effective_user

    if game["started"]:
        await update.message.reply_text(
            "Oyin allaqachon boshlangan!"
        )
        return

    for player in game["players"]:
        if player["id"] == user.id:
            await update.message.reply_text(
                "Siz allaqachon oyindasiz!"
            )
            return

    game["players"].append({
        "id": user.id,
        "name": user.first_name
    })

    await update.message.reply_text(
        f"{user.first_name} oyinga qoshildi!\n"
        f"Jami oyinchilar: {len(game['players'])}"
    )


async def players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = get_game(chat_id)

    if not game["players"]:
        await update.message.reply_text(
            "Hozircha oyinchilar yoq."
        )
        return

    text = "Oyinchilar:\n\n"

    for number, player in enumerate(game["players"], 1):
        text += f"{number}. {player['name']}\n"

    await update.message.reply_text(text)


def make_roles(player_count):
    roles = []

    mafia_count = max(1, player_count // 4)

    roles.extend(["Mafia"] * mafia_count)

    if player_count >= 5:
        roles.append("Doktor")

    if player_count >= 6:
        roles.append("Komissar")

    while len(roles) < player_count:
        roles.append("Fuqaro")

    return roles[:player_count]


async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = get_game(chat_id)

    if game["started"]:
        await update.message.reply_text(
            "Oyin allaqachon boshlangan!"
        )
        return

    player_count = len(game["players"])

    if player_count < 4:
        await update.message.reply_text(
            "Oyin uchun kamida 4 ta oyinchi kerak."
        )
        return

    roles = make_roles(player_count)
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
        "MAFIA OYINI BOSHLANDI!\n\n"
        "Kecha boshlandi.\n"
        "Har bir oyinchiga roli shaxsiy xabarda yuborildi."
    )

    for player in game["players"]:
        try:
            await context.bot.send_message(
                chat_id=player["id"],
                text=(
                    "SIZNING ROLINGIZ\n\n"
                    f"{game['roles'][player['id']]}\n\n"
                    "Rolingizni boshqalarga aytmang."
                )
            )
        except Exception:
            pass


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = get_game(chat_id)

    if not game["started"]:
       
