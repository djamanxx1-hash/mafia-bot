import os
import random
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# =========================================================
# SOZLAMALAR
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
PORT = int(os.getenv("PORT", "10000"))

MAX_PLAYERS = 30
MIN_PLAYERS = 4

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# =========================================================
# RENDER HEALTH SERVER
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def run_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logging.info("Health server PORT %s da ishga tushdi.", PORT)
    server.serve_forever()


# =========================================================
# MA'LUMOTLAR
# =========================================================

players = {}
admins = set()

game_players = {}
game_started = False
game_chat_id = None
game_phase = "lobby"

night_actions = {}
votes = {}

# =========================================================
# ROLLAR
# =========================================================

ROLES = [
    ("Mafia", "🔪"),
    ("Mafia", "🔪"),
    ("Mafia", "🔪"),
    ("Don", "👑"),
    ("Godfather", "🕴️"),
    ("Komissar", "🔍"),
    ("Sherif", "⭐"),
    ("Doktor", "💉"),
    ("Bodyguard", "🛡️"),
    ("Advokat", "⚖️"),
    ("Detektiv", "🕵️"),
    ("Snayper", "🎯"),
    ("Jurnalist", "📰"),
    ("Haker", "💻"),
    ("Psixolog", "🧠"),
    ("Sevishgan", "❤️"),
    ("Manyak", "🔪"),
    ("O'g'ri", "🥷"),
    ("Qasoskor", "⚔️"),
    ("Fuqaro", "👤"),
    ("Fuqaro", "👤"),
    ("Fuqaro", "👤"),
    ("Fuqaro", "👤"),
    ("Fuqaro", "👤"),
    ("Fuqaro", "👤"),
    ("Fuqaro", "👤"),
    ("Fuqaro", "👤"),
    ("Fuqaro", "👤"),
    ("Fuqaro", "👤"),
    ("Fuqaro", "👤"),
]


# =========================================================
# YORDAMCHI
# =========================================================

def is_owner(user_id):
    return user_id == OWNER_ID


def is_admin(user_id):
    return user_id == OWNER_ID or user_id in admins


def get_player(user):
    user_id = user.id

    if user_id not in players:
        players[user_id] = {
            "id": user_id,
            "name": user.first_name or "Noma'lum",
            "username": user.username or "",
            "diamonds": 0,
            "money": 0,
            "games": 0,
            "wins": 0,
            "banned": False,
        }
    else:
        players[user_id]["name"] = user.first_name or "Noma'lum"
        players[user_id]["username"] = user.username or ""

    return players[user_id]


def create_empty_player(user_id):
    return {
        "id": user_id,
        "name": "O'yinchi",
        "username": "",
        "diamonds": 0,
        "money": 0,
        "games": 0,
        "wins": 0,
        "banned": False,
    }


def player_text(p):
    username = f"@{p['username']}" if p["username"] else "username yo'q"

    return (
        f"👤 Ism: {p['name']}\n"
        f"🆔 ID: {p['id']}\n"
        f"📱 Username: {username}\n\n"
        f"💎 Olmos: {p['diamonds']}\n"
        f"💰 Pul: {p['money']}\n"
        f"🎮 O'yinlar: {p['games']}\n"
        f"🏆 G'alabalar: {p['wins']}"
    )


def alive_players():
    return {
        uid: data
        for uid, data in game_players.items()
        if data.get("alive", False)
    }


def get_role(user_id):
    if user_id in game_players:
        return game_players[user_id].get("role")
    return None


def find_player_by_number(number):
    alive = list(alive_players().values())

    if number < 1 or number > len(alive):
        return None

    return alive[number - 1]


def game_list_text(include_status=True):
    if not game_players:
        return "📭 O'yinchilar yo'q."

    text = "👥 O'YINCHILAR\n\n"

    for i, p in enumerate(game_players.values(), start=1):
        status = ""

        if include_status:
            status = " 🟢" if p.get("alive", False) else " 💀"

        text += f"{i}. {p['name']}{status}\n"

    text += f"\n👤 Jami: {len(game_players)}"

    return text


async def announce(context, text):
    if game_chat_id:
        try:
            await context.bot.send_message(
                chat_id=game_chat_id,
                text=text
            )
        except Exception as e:
            logging.error("Guruhga xabar yuborishda xato: %s", e)


# =========================================================
# MENU
# =========================================================

async def setup_menu(application):
    commands = [
        BotCommand("start", "Botni ishga tushirish"),
        BotCommand("profile", "Profilim"),
        BotCommand("money", "Balansim"),
        BotCommand("top", "Reyting"),
        BotCommand("exchange", "Olmosni pulga almashtirish"),
        BotCommand("newgame", "Yangi o'yin"),
        BotCommand("join", "O'yinga qo'shilish"),
        BotCommand("players", "O'yinchilar"),
        BotCommand("startgame", "O'yinni boshlash"),
        BotCommand("role", "Rolim"),
        BotCommand("night", "Tun harakatlari"),
        BotCommand("vote", "Ovoz berish"),
        BotCommand("help", "Yordam"),
    ]

    await application.bot.set_my_commands(commands)


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    p = get_player(user)

    if p["banned"]:
        await update.message.reply_text(
            "🚫 Siz botdan foydalanish huquqidan mahrum qilingansiz."
        )
        return

    await update.message.reply_text(
        "🎭 OVERLORD MAFIA\n\n"
        "👑 Sirlar • Intriga • G'alaba\n\n"
        "📋 Telegramdagi ☰ Menu orqali kerakli bo'limni tanlang.\n\n"
        "👤 /profile — Profil\n"
        "💰 /money — Balans\n"
        "🏆 /top — Reyting\n"
        "🎭 /newgame — Yangi o'yin\n"
        "📖 /help — Yordam"
    )


# =========================================================
# HELP
# =========================================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 OVERLORD MAFIA — YORDAM\n\n"
        "👤 /profile — profilingiz\n"
        "💰 /money — balans\n"
        "🏆 /top — reyting\n"
        "💎 /exchange 100 — olmosni pulga almashtirish\n\n"
        "🎭 /newgame — yangi o'yin\n"
        "➕ /join — o'yinga qo'shilish\n"
        "👥 /players — o'yinchilar\n"
        "🔥 /startgame — o'yinni boshlash\n"
        "🎭 /role — maxfiy rolingiz\n"
        "🌙 /night — tungi harakatlar\n"
        "🗳️ /vote — ovoz berish\n\n"
        "📌 O'yin admin tomonidan boshlanadi."
    )


# =========================================================
# PROFILE
# =========================================================

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and is_admin(update.effective_user.id):
        try:
            user_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ ID noto'g'ri.")
            return

        if user_id not in players:
            await update.message.reply_text("❌ O'yinchi topilmadi.")
            return

        await update.message.reply_text(
            "👤 O'YINCHI PROFILI\n\n" + player_text(players[user_id])
        )
        return

    p = get_player(update.effective_user)

    if p["banned"]:
        await update.message.reply_text("🚫 Siz ban qilingansiz.")
        return

    await update.message.reply_text(
        "👤 SIZNING PROFILINGIZ\n\n" + player_text(p)
    )


# =========================================================
# MONEY
# =========================================================

async def money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = get_player(update.effective_user)

    if p["banned"]:
        return

    await update.message.reply_text(
        f"💰 BALANS\n\n"
        f"💎 Olmos: {p['diamonds']}\n"
        f"💰 Pul: {p['money']}"
    )


# =========================================================
# TOP
# =========================================================

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not players:
        await update.message.reply_text("📭 Hali o'yinchilar yo'q.")
        return

    sorted_players = sorted(
        players.values(),
        key=lambda x: x["money"],
        reverse=True,
    )

    text = "🏆 TOP O'YINCHILAR\n\n"

    for i, p in enumerate(sorted_players[:10], start=1):
        text += f"{i}. {p['name']} — 💰 {p['money']}\n"

    await update.message.reply_text(text)


# =========================================================
# EXCHANGE
# =========================================================

async def exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = get_player(update.effective_user)

    if p["banned"]:
        return

    if not context.args:
        await update.message.reply_text(
            "💎 ALMASHISH\n\n"
            "/exchange 100\n\n"
            "100 💎 = 10 000 💰"
        )
        return

    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ Miqdor raqam bo'lishi kerak."
        )
        return

    if amount <= 0:
        await update.message.reply_text(
            "❌ Miqdor noto'g'ri."
        )
        return

    if p["diamonds"] < amount:
        await update.message.reply_text(
            "❌ Sizda yetarli 💎 yo'q."
        )
        return

    money_amount = amount * 100

    p["diamonds"] -= amount
    p["money"] += money_amount

    await update.message.reply_text(
        f"✅ ALMASHUV BAJARILDI!\n\n"
        f"💎 -{amount}\n"
        f"💰 +{money_amount}"
    )


# =========================================================
# ADMIN
# =========================================================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 Siz admin emassiz.")
        return

    await update.message.reply_text(
        "👑 ADMIN PANEL\n\n"
        "👤 /profile ID\n"
        "💎 /adddiamond ID AMOUNT\n"
        "💰 /addmoney ID AMOUNT\n"
        "💎 /removediamond ID AMOUNT\n"
        "💰 /removemoney ID AMOUNT\n"
        "💎 /bankrot1 ID\n"
        "💰 /bankrot2 ID\n"
        "🚫 /ban ID\n"
        "✅ /unban ID\n"
        "➕ /addadmin ID\n"
        "➖ /removeadmin ID"
    )


# =========================================================
# ADD DIAMOND
# =========================================================

async def adddiamond(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Format:\n/adddiamond ID AMOUNT"
        )
        return

    try:
        user_id = int(context.args[0])
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

    if user_id not in players:
        players[user_id] = create_empty_player(user_id)

    players[user_id]["diamonds"] += amount

    await update.message.reply_text(
        f"✅ {user_id} ga 💎 {amount} qo'shildi."
    )


# =========================================================
# ADD MONEY
# =========================================================

async def addmoney(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Format:\n/addmoney ID AMOUNT"
        )
        return

    try:
        user_id = int(context.args[0])
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

    if user_id not in players:
        players[user_id] = create_empty_player(user_id)

    players[user_id]["money"] += amount

    await update.message.reply_text(
        f"✅ {user_id} ga 💰 {amount} qo'shildi."
    )


# =========================================================
# REMOVE DIAMOND
# =========================================================

async def removediamond(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Format:\n/removediamond ID AMOUNT"
        )
        return

    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "❌ Raqam kiriting."
        )
        return

    if amount <= 0:
        await update.message.reply_text(
            "❌ Miqdor noto'g'ri."
        )
        return

    if user_id not in players:
        await update.message.reply_text(
            "❌ O'yinchi topilmadi."
        )
        return

    players[user_id]["diamonds"] = max(
        0,
        players[user_id]["diamonds"] - amount
    )

    await update.message.reply_text(
        "✅ Olmos kamaytirildi."
    )


# =========================================================
# REMOVE MONEY
# =========================================================

async def removemoney(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Format:\n/removemoney ID AMOUNT"
        )
        return

    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "❌ Raqam kiriting."
        )
        return

    if amount <= 0:
        await update.message.reply_text(
            "❌ Miqdor noto'g'ri."
        )
        return

    if user_id not in players:
        await update.message.reply_text(
            "❌ O'yinchi topilmadi."
        )
        return

    players[user_id]["money"] = max(
        0,
        players[user_id]["money"] - amount
    )

    await update.message.reply_text(
        "✅ Pul kamaytirildi."
    )


# =========================================================
# BANKROT
# =========================================================

async def bankrot1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "/bankrot1 ID"
        )
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ ID noto'g'ri."
        )
        return

    if user_id not in players:
        await update.message.reply_text(
            "❌ O'yinchi topilmadi."
        )
        return

    players[user_id]["diamonds"] = 0

    await update.message.reply_text(
        f"💎 {user_id} ning barcha olmoslari 0 qilindi."
    )


async def bankrot2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "/bankrot2 ID"
        )
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ ID noto'g'ri."
        )
        return

    if user_id not in players:
        await update.message.reply_text(
            "❌ O'yinchi topilmadi."
        )
        return

    players[user_id]["money"] = 0

    await update.message.reply_text(
        f"💰 {user_id} ning barcha pullari 0 qilindi."
    )


# =========================================================
# BAN
# =========================================================

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "/ban ID"
        )
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ ID noto'g'ri."
        )
        return

    if user_id not in players:
        await update.message.reply_text(
            "❌ O'yinchi topilmadi."
        )
        return

    if user_id == OWNER_ID:
        await update.message.reply_text(
            "❌ Owner'ni ban qilib bo'lmaydi."
        )
        return

    players[user_id]["banned"] = True

    await update.message.reply_text(
        f"🚫 {user_id} ban qilindi."
    )


# =========================================================
# UNBAN
# =========================================================

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "/unban ID"
        )
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ ID noto'g'ri."
        )
        return

    if user_id not in players:
        await update.message.reply_text(
            "❌ O'yinchi topilmadi."
        )
        return

    players[user_id]["banned"] = False

    await update.message.reply_text(
        f"✅ {user_id} unban qilindi."
    )


# =========================================================
# ADD ADMIN
# =========================================================

async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text(
            "🚫 Faqat Owner."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "/addadmin ID"
        )
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ ID noto'g'ri."
        )
        return

    if user_id == OWNER_ID:
        await update.message.reply_text(
            "ℹ️ Siz allaqachon Owner'siz."
        )
        return

    admins.add(user_id)

    await update.message.reply_text(
        f"👑 {user_id} admin qilindi."
    )


# =========================================================
# REMOVE ADMIN
# =========================================================

async def removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text(
            "🚫 Faqat Owner."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "/removeadmin ID"
        )
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ ID noto'g'ri."
        )
        return

    admins.discard(user_id)

    await update.message.reply_text(
        f"➖ {user_id} adminlikdan chiqarildi."
    )


# =========================================================
# NEW GAME
# =========================================================

async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_players
    global game_started
    global game_chat_id
    global game_phase
    global night_actions
    global votes

    if game_started:
        await update.message.reply_text(
            "⚠️ Hozir boshqa o'yin davom etmoqda."
        )
        return

    game_players = {}
    night_actions = {}
    votes = {}

    game_started = False
    game_phase = "lobby"
    game_chat_id = update.effective_chat.id

    await update.message.reply_text(
        "🎭 OVERLORD MAFIA\n\n"
        "🔥 YANGI O'YIN OCHILDI!\n\n"
        "➕ Qo'shilish: /join\n"
        "👥 O'yinchilar: /players\n"
        "🔥 Boshlash: /startgame\n\n"
        f"👤 Minimal: {MIN_PLAYERS}\n"
        f"👥 Maksimal: {MAX_PLAYERS}\n\n"
        "⚔️ Shaharda tun yana boshlandi..."
    )


# =========================================================
# JOIN
# =========================================================

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_chat_id

    user = update.effective_user
    p = get_player(user)

    if p["banned"]:
        await update.message.reply_text(
            "🚫 Siz ban qilingansiz."
        )
        return

    if game_started:
        await update.message.reply_text(
            "❌ O'yin allaqachon boshlangan."
        )
        return

    if game_chat_id is None:
        game_chat_id = update.effective_chat.id

    if user.id in game_players:
        await update.message.reply_text(
            "✅ Siz allaqachon o'yindasiz."
        )
        return

    if len(game_players) >= MAX_PLAYERS:
        await update.message.reply_text(
            "❌ O'yinchilar soni maksimal darajaga yetdi."
        )
        return

    game_players[user.id] = {
        "id": user.id,
        "name": user.first_name or "Noma'lum",
        "role": None,
        "emoji": "👤",
        "alive": False,
        "protected": False,
        "silenced": False,
    }

    await update.message.reply_text(
        f"✅ {user.first_name} o'yinga qo'shildi!\n\n"
        f"👥 O'yinchilar: {len(game_players)}/{MAX_PLAYERS}"
    )


# =========================================================
# PLAYERS
# =========================================================

async def players_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        game_list_text(include_status=game_started)
    )


# =========================================================
# START GAME
# =========================================================

async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_started
    global game_phase
    global night_actions
    global votes

    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "🚫 Faqat admin o'yinni boshlashi mumkin."
        )
        return

    if game_started:
        await update.message.reply_text(
            "⚠️ O'yin allaqachon boshlangan."
        )
        return

    if len(game_players) < MIN_PLAYERS:
        await update.message.reply_text(
            f"❌ O'yinni boshlash uchun kamida {MIN_PLAYERS} ta "
            f"o'yinchi kerak.\n\n"
            f"👥 Hozir: {len(game_players)}"
        )
        return

    game_started = True
    game_phase = "night"

    night_actions = {}
    votes = {}

    player_list = list(game_players.values())
    random.shuffle(player_list)

    roles = ROLES[:len(player_list)]
    random.shuffle(roles)

    for player, role_data in zip(player_list, roles):
        role_name, emoji = role_data

        player["role"] = role_name
        player["emoji"] = emoji
        player["alive"] = True
        player["protected"] = False
        player["silenced"] = False

        if player["id"] in players:
            players[player["id"]]["games"] += 1

        try:
            await context.bot.send_message(
                chat_id=player["id"],
                text=(
                    "🎭 SIZNING MAXFIY ROLINGIZ\n\n"
                    f"{emoji} {role_name}\n\n"
                    "🤫 Bu xabar faqat siz uchun.\n"
                    "⚠️ ROLINGIZNI hech kimga aytmang!\n\n"
                    "🌙 Tungi harakat kerak bo'lsa:\n"
                    "/night"
                ),
            )
        except Exception as e:
            logging.error(
                "Rolni yuborishda xato: %s",
                e,
            )

    await announce(
        context,
        "🔥 O'YIN BOSHLANDI!\n\n"
        f"👥 O'yinchilar: {len(player_list)}\n\n"
        "🎭 Rollar maxfiy yuborildi.\n"
        "🌙 HOZIR TUN!\n\n"
        "🤫 Mafia harakatga o'tadi..."
    )


# =========================================================
# ROLE
# =========================================================

async def role_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in game_players:
        await update.message.reply_text(
            "❌ Siz hozirgi o'yinda emassiz."
        )
        return

    p = game_players[user_id]

    if not game_started:
        await update.message.reply_text(
            "⏳ O'yin hali boshlanmadi."
        )
        return

    if not p["alive"]:
        await update.message.reply_text(
            "💀 Siz o'yinda vafot etgansiz."
        )
        return

    await update.message.reply_text(
        "🎭 SIZNING MAXFIY ROLINGIZ\n\n"
        f"{p['emoji']} {p['role']}\n\n"
        "🤫 Bu ma'lumotni sir saqlang."
    )


# =========================================================
# NIGHT
# =========================================================

async def night(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global night_actions

    user_id = update.effective_user.id

    if user_id not in game_players:
        await update.message.reply_text(
            "❌ Siz o'yinda emassiz."
        )
        return

    p = game_players[user_id]

    if not game_started:
        await update.message.reply_text(
            "⏳ O'yin hali boshlanmadi."
        )
        return

    if game_phase != "night":
        await update.message.reply_text(
            "☀️ Hozir tun emas."
        )
        return

    if not p["alive"]:
        await update.message.reply_text(
            "💀 Siz vafot etgansiz."
        )
        return

    role = p["role"]

    if role in ["Mafia", "Don", "Godfather"]:
        targets = []

        for target in alive_players().values():
            if target["id"] != user_id:
                targets.append(
                    f"{target['id']} — {target['name']}"
                )

        await update.message.reply_text(
            "🔪 MAFIA TUNGI HARAKATI\n\n"
            "Nishonni tanlang:\n\n"
            + "\n".join(targets)
            + "\n\n"
            "Misol:\n"
            "/kill ID"
        )
        return

    if role == "Doktor":
        await update.message.reply_text(
            "💉 DOKTOR\n\n"
            "Kimni davolaysiz?\n\n"
            "Misol:\n"
            "/heal ID"
        )
        return

    if role in ["Komissar", "Sherif", "Detektiv"]:
        await update.message.reply_text(
            "🔍 TEKSHIRUV\n\n"
            "Kimni tekshirasiz?\n\n"
            "Misol:\n"
            "/check ID"
        )
        return

    if role == "Bodyguard":
        await update.message.reply_text(
            "🛡️ BODYGUARD\n\n"
            "Kimni himoya qilasiz?\n\n"
            "Misol:\n"
            "/guard ID"
        )
        return

    if role == "Snayper":
        await update.message.reply_text(
            "🎯 SNAYPER\n\n"
            "Nishonni tanlang:\n\n"
            "Misol:\n"
            "/shoot ID"
        )
        return

    if role == "Manyak":
        await update.message.reply_text(
            "🔪 MANYAK\n\n"
            "Kimni yo'q qilasiz?\n\n"
            "Misol:\n"
            "/kill ID"
        )
        return

    if role == "Psixolog":
        await update.message.reply_text(
            "🧠 PSIXOLOG\n\n"
            "Kimni jim qilasiz?\n\n"
            "Misol:\n"
            "/silence ID"
        )
        return

    if role == "Jurnalist":
        await update.message.reply_text(
            "📰 JURNALIST\n\n"
            "Kim haqida ma'lumot yig'asiz?\n\n"
            "Misol:\n"
            "/check ID"
        )
        return

    if role == "Haker":
        await update.message.reply_text(
            "💻 HAKER\n\n"
            "Kimni buzib kirib tekshirasiz?\n\n"
            "Misol:\n"
            "/check ID"
        )
        return

    await update.message.reply_text(
        "🌙 Sizning rolingizda bu kecha maxsus harakat yo'q.\n\n"
        "🤫 Jim kuzating..."
    )


# =========================================================
# NIGHT TARGET VALIDATOR
# =========================================================

async def validate_target(update, target_id):
    user_id = update.effective_user.id

    if not game_started:
        await update.message.reply_text(
            "⏳ O'yin boshlanmagan."
        )
        return None

    if game_phase != "night":
        await update.message.reply_text(
            "☀️ Hozir tun emas."
        )
        return None

    if user_id not in game_players:
        await update.message.reply_text(
            "❌ Siz o'yinda emassiz."
        )
        return None

    if not game_players[user_id]["alive"]:
        await update.message.reply_text(
            "💀 Siz vafot etgansiz."
        )
        return None

    if target_id not in game_players:
        await update.message.reply_text(
            "❌ Bunday o'yinchi topilmadi."
        )
        return None

    if not game_players[target_id]["alive"]:
        await update.message.reply_text(
            "💀 Bu o'yinchi allaqachon vafot etgan."
        )
        return None

    if target_id == user_id:
        await update.message.reply_text(
            "❌ O'zingizni tanlay olmaysiz."
        )
        return None

    return game_players[target_id]


# =========================================================
# KILL
# =========================================================

async def kill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in game_players:
        return

    role = game_players[user_id]["role"]

    if role not in ["Mafia", "Don", "Godfather", "Manyak"]:
        await update.message.reply_text(
            "❌ Sizda bu harakat mavjud emas."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "/kill ID"
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ ID raqam bo'lishi kerak."
        )
        return

    target = await validate_target(update, target_id)

    if target is None:
        return

    night_actions[user_id] = {
        "action": "kill",
        "target": target_id
    }

    await update.message.reply_text(
        f"🔪 Nishon tanlandi: {target['name']}\n\n"
        "🤫 Harakat maxfiy saqlandi."
    )


# =========================================================
# HEAL
# =========================================================

async def heal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in game_players:
        return

    if game_players[user_id]["role"] != "Doktor":
        await update.message.reply_text(
            "❌ Siz Doktor emassiz."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "/heal ID"
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ ID raqam bo'lishi kerak."
        )
        return

    if target_id not in game_players:
        await update.message.reply_text(
            "❌ O'yinchi topilmadi."
        )
        return

    if not game_players[target_id]["alive"]:
        await update.message.reply_text(
            "💀 Bu o'yinchi vafot etgan."
        )
        return

    night_actions[user_id] = {
        "action": "heal",
        "target": target_id
    }

    await update.message.reply_text(
        f"💉 {game_players[target_id]['name']} davolanish uchun tanlandi."
    )


# =========================================================
# CHECK
# =========================================================

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in game_players:
        return

    role = game_players[user_id]["role"]

    if role not in ["Komissar", "Sherif", "Detektiv", "Jurnalist", "Haker"]:
        await update.message.reply_text(
            "❌ Sizda tekshiruv huquqi yo'q."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "/check ID"
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ ID raqam bo'lishi kerak."
        )
        return

    target = await validate_target(update, target_id)

    if target is None:
        return

    target_role = target["role"]

    mafia_roles = [
        "Mafia",
        "Don",
        "Godfather",
    ]

    if target_role in mafia_roles:
        result = "🔴 MAFIA TOMONI"
    else:
        result = "🟢 MAFIA EMAS"

    await update.message.reply_text(
        f"🔍 TEKSHIRUV NATIJASI\n\n"
        f"👤 {target['name']}\n"
        f"📋 Natija: {result}"
    )


# =========================================================
# GUARD
# =========================================================

async def guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in game_players:
        return

    if game_players[user_id]["role"] != "Bodyguard":
        await update.message.reply_text(
            "❌ Siz Bodyguard emassiz."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "/guard ID"
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ ID raqam bo'lishi kerak."
        )
        return

    target = await validate_target(update, target_id)

    if target is None:
        return

    night_actions[user_id] = {
        "action": "guard",
        "target": target_id
    }

    await update.message.reply_text(
        f"🛡️ {target['name']} himoyaga olindi."
    )


# =========================================================
# SHOOT
# =========================================================

async def shoot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in game_players:
        return

    if game_players[user_id]["role"] != "Snayper":
        await update.message.reply_text(
            "❌ Siz Snayper emassiz."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "/shoot ID"
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ ID raqam bo'lishi kerak."
        )
        return

    target = await validate_target(update, target_id)

    if target is None:
        return

    night_actions[user_id] = {
        "action": "shoot",
        "target": target_id
    }

    await update.message.reply_text(
        f"🎯 Nishon tanlandi: {target['name']}"
    )


# =========================================================
# SILENCE
# =========================================================

async def silence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in game_players:
        return

    if game_players[user_id]["role"] != "Psixolog":
        await update.message.reply_text(
            "❌ Siz Psixolog emassiz."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "/silence ID"
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ ID raqam bo'lishi kerak."
        )
        return

    target = await validate_target(update, target_id)

    if target is None:
        return

    night_actions[user_id] = {
        "action": "silence",
        "target": target_id
    }

    await update.message.reply_text(
        f"🧠 {target['name']} jim qilindi."
    )


# =========================================================
# END NIGHT
# =========================================================

async def endnight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_phase
    global night_actions

    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "🚫 Faqat admin."
        )
        return

    if not game_started:
        await update.message.reply_text(
            "❌ O'yin boshlanmagan."
        )
        return

    if game_phase != "night":
        await update.message.reply_text(
            "☀️ Hozir tun emas."
        )
        return

    mafia_target = None
    doctor_target = None
    guard_target = None
    sniper_target = None
    maniac_target = None
    silence_target = None

    for user_id, action in night_actions.items():

        if user_id not in game_players:
            continue

        if not game_players[user_id]["alive"]:
            continue

        action_type = action["action"]
        target = action["target"]

        if action_type == "kill":
            role = game_players[user_id]["role"]

            if role in ["Mafia", "Don", "Godfather"]:
                mafia_target = target

            elif role == "Manyak":
                maniac_target = target

            elif role == "Snayper":
                sniper_target = target

        elif action_type == "heal":
            doctor_target = target

        elif action_type == "guard":
            guard_target = target

        elif action_type == "shoot":
            sniper_target = target

        elif action_type == "silence":
            silence_target = target

    dead = []

    protected = set()

    if doctor_target:
        protected.add(doctor_target)

    if guard_target:
        protected.add(guard_target)

    if mafia_target and mafia_target not in protected:
        dead.append(mafia_target)

    if maniac_target and maniac_target not in protected:
        if maniac_target not in dead:
            dead.append(maniac_target)

    if sniper_target and sniper_target not in protected:
        if sniper_target not in dead:
            dead.append(sniper_target)

    for target_id in dead:
        if target_id in game_players:
            game_players[target_id]["alive"] = False

    if silence_target and silence_target in game_players:
        game_players[silence_target]["silenced"] = True

    text = "☀️ TONG OTDI!\n\n"

    if dead:
        text += "💀 Tungi voqealar:\n\n"

        for target_id in dead:
            target = game_players[target_id]

            text += (
                f"💀 {target['name']} o'ldirildi.\n"
                f"🎭 Roli: {target['emoji']} {target['role']}\n\n"
            )
    else:
        text += (
            "🌙 Bu kecha hech kim halok bo'lmadi.\n"
            "🛡️ Himoya muvaffaqiyatli ishladi.\n\n"
        )

    if silence_target and silence_target in game_players:
        if game_players[silence_target]["alive"]:
            text += (
                f"🧠 {game_players[silence_target]['name']} "
                "bugun jim turadi.\n\n"
            )

    game_phase = "day"
    night_actions = {}

    await announce(context, text)

    winner = check_winner()

    if winner:
        await finish_game(context, winner)
        return

    await announce(
        context,
        "🗳️ KUNDIZGI OVOZ BERISH\n\n"
        "Ovoz berish uchun:\n"
        "/vote ID\n\n"
        "👥 Tirik o'yinchilar:\n\n"
        + game_list_text()
    )


# =========================================================
# VOTE
# =========================================================

async def vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in game_players:
        await update.message.reply_text(
            "❌ Siz o'yinda emassiz."
        )
        return

    if not game_started:
        await update.message.reply_text(
            "⏳ O'yin boshlanmagan."
        )
        return

    if game_phase != "day":
        await update.message.reply_text(
            "🌙 Hozir ovoz berish vaqti emas."
        )
        return

    if not game_players[user_id]["alive"]:
        await update.message.reply_text(
            "💀 O'lgan o'yinchi ovoz bera olmaydi."
        )
        return

    if game_players[user_id].get("silenced", False):
        await update.message.reply_text(
            "🤐 Siz bugun Psixolog tomonidan jim qilingan."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "🗳️ Format:\n/vote ID"
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ ID raqam bo'lishi kerak."
        )
        return

    if target_id not in game_players:
        await update.message.reply_text(
            "❌ O'yinchi topilmadi."
        )
        return

    if not game_players[target_id]["alive"]:
        await update.message.reply_text(
            "💀 Bu o'yinchi allaqachon vafot etgan."
        )
        return

    if target_id == user_id:
        await update.message.reply_text(
            "❌ O'zingizga ovoz bera olmaysiz."
        )
        return

    votes[user_id] = target_id

    await update.message.reply_text(
        f"🗳️ Ovozingiz qabul qilindi.\n"
        f"🎯 Nishon: {game_players[target_id]['name']}"
    )

    alive_count = len(alive_players())

    if len(votes) >= alive_count:
        await process_votes(context)


# =========================================================
# PROCESS VOTES
# =========================================================

async def process_votes(context):
    global game_phase
    global votes

    if not votes:
        return

    counter = {}

    for target_id in votes.values():
        counter[target_id] = counter.get(target_id, 0) + 1

    max_votes = max(counter.values())

    candidates = [
        target_id
        for target_id, count in counter.items()
        if count == max_votes
    ]

    if len(candidates) > 1:
        await announce(
            context,
            "🤝 OVOZ NATIJASI\n\n"
            "⚖️ Ovozlar teng bo'ldi.\n"
            "Hech kim chiqarilmadi.\n\n"
            "🌙 Tun boshlanmoqda..."
        )

        votes = {}
        game_phase = "night"

        for p in game_players.values():
            p["silenced"] = False

        await announce(
            context,
            "🌙 TUN BOSHLANDI!\n\n"
            "🤫 Rollar o'z harakatlarini bajaradi."
        )
        return

    eliminated_id = candidates[0]

    if eliminated_id in game_players:
        eliminated = game_players[eliminated_id]
        eliminated["alive"] = False

        await announce(
            context,
            "⚖️ OVOZ BERISH YAKUNI\n\n"
            f"💀 {eliminated['name']} chiqarildi.\n"
            f"🎭 Uning roli: {eliminated['emoji']} {eliminated['role']}\n"
        )

    votes = {}

    winner = check_winner()

    if winner:
        await finish_game(context, winner)
        return

    game_phase = "night"

    for p in game_players.values():
        p["silenced"] = False

    await announce(
        context,
        "🌙 TUN BOSHLANDI!\n\n"
        "🔪 Mafia uyg'ondi...\n"
        "💉 Doktor navbatchilikda...\n"
        "🔍 Komissar iz qidirmoqda..."
    )


# =========================================================
# CHECK WINNER
# =========================================================

def check_winner():
    alive = list(alive_players().values())

    mafia_count = sum(
        1
        for p in alive
        if p["role"] in ["Mafia", "Don", "Godfather"]
    )

    maniac_count = sum(
        1
        for p in alive
        if p["role"] == "Manyak"
    )

    civilian_count = sum(
        1
        for p in alive
        if p["role"] not in [
            "Mafia",
            "Don",
            "Godfather",
            "Manyak",
        ]
    )

    if maniac_count > 0 and len(alive) == 1:
        return "Manyak"

    if mafia_count == 0 and maniac_count == 0:
        return "Fuqaro"

    if mafia_count >= civilian_count + maniac_count:
        return "Mafia"

    return None


# =========================================================
# FINISH GAME
# =========================================================

async def finish_game(context, winner):
    global game_started
    global game_phase
    global game_players
    global night_actions
    global votes

    game_started = False
    game_phase = "finished"

    if winner == "Mafia":
        winning_roles = ["Mafia", "Don", "Godfather"]

        for p in game_players.values():
            if p["role"] in winning_roles and p["alive"]:
                if p["id"] in players:
                    players[p["id"]]["wins"] += 1
                    players[p["id"]]["money"] += 5000

        result = (
            "🏆 MAFIA G'ALABA QILDI!\n\n"
            "🔪 Shahar Mafia qo'liga o'tdi.\n"
            "💰 G'oliblarga mukofot berildi."
        )

    elif winner == "Manyak":
        for p in game_players.values():
            if p["role"] == "Manyak":
                if p["id"] in players:
                    players[p["id"]]["wins"] += 1
                    players[p["id"]]["money"] += 10000

        result = (
            "🏆 MANYAK G'ALABA QILDI!\n\n"
            "🔪 Oxirgi tirik o'yinchi Manyak bo'ldi.\n"
            "💰 Maxsus mukofot berildi."
        )

    else:
        winning_roles = [
            "Komissar",
            "Sherif",
            "Doktor",
            "Bodyguard",
            "Advokat",
            "Detektiv",
            "Snayper",
            "Jurnalist",
            "Haker",
            "Psixolog",
            "Sevishgan",
            "Qasoskor",
            "O'g'ri",
            "Fuqaro",
        ]

        for p in game_players.values():
            if p["role"] in winning_roles and p["alive"]:
                if p["id"] in players:
                    players[p["id"]]["wins"] += 1
                    players[p["id"]]["money"] += 3000

        result = (
            "🏆 FUQAROLAR G'ALABA QILDI!\n\n"
            "🌆 Mafia mag'lub bo'ldi.\n"
            "💰 G'oliblarga mukofot berildi."
        )

    await announce(
        context,
        result
        + "\n\n"
        + "🎭 O'YIN YAKUNLANDI!\n\n"
        + "🔎 ROLLAR:\n"
        + "\n".join(
            f"• {p['name']} — {p['emoji']} {p['role']}"
            for p in game_players.values()
        )
        + "\n\n"
        + "🔥 Yangi o'yin uchun /newgame"
    )

    night_actions = {}
    votes = {}


# =========================================================
# ADMIN END NIGHT
# =========================================================

async def endnight_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await endnight(update, context)


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error(
        "Botda xato yuz berdi:",
        exc_info=context.error,
    )


# =========================================================
# MAIN
# =========================================================

def main():

    if not TOKEN:
        raise ValueError(
            "BOT_TOKEN topilmadi. "
            "Render Environment'da BOT_TOKEN yarating."
        )

    if OWNER_ID == 0:
        raise ValueError(
            "OWNER_ID topilmadi. "
            "Render Environment'da OWNER_ID yarating."
        )

    # Render health server
    health_thread = threading.Thread(
        target=run_health_server,
        daemon=True,
    )
    health_thread.start()

    application = (
        Application.builder()
        .token(TOKEN)
        .post_init(setup_menu)
        .build()
    )

    # =====================================================
    # ASOSIY BUYRUQLAR
    # =====================================================

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    application.add_handler(
        CommandHandler("profile", profile)
    )

    application.add_handler(
        CommandHandler("money", money)
    )

    application.add_handler(
        CommandHandler("top", top)
    )

    application.add_handler(
        CommandHandler("exchange", exchange)
    )

    # =====================================================
    # O'YIN
    # =====================================================

    application.add_handler(
        CommandHandler("newgame", newgame)
    )

    application.add_handler(
        CommandHandler("join", join)
    )

    application.add_handler(
        CommandHandler("players", players_command)
    )

    application.add_handler(
        CommandHandler("startgame", startgame)
    )

    application.add_handler(
        CommandHandler("role", role_command)
    )

    application.add_handler(
        CommandHandler("night", night)
    )

    application.add_handler(
        CommandHandler("vote", vote)
    )

    application.add_handler(
        CommandHandler("kill", kill)
    )

    application.add_handler(
        CommandHandler("heal", heal)
    )

    application.add_handler(
        CommandHandler("check", check)
    )

    application.add_handler(
        CommandHandler("guard", guard)
    )

    application.add_handler(
        CommandHandler("shoot", shoot)
    )

    application.add_handler(
        CommandHandler("silence", silence)
    )

    application.add_handler(
        CommandHandler("endnight", endnight_command)
    )

    # =====================================================
    # ADMIN
    # =====================================================

    application.add_handler(
        CommandHandler("admin", admin)
    )

    application.add_handler(
        CommandHandler("adddiamond", adddiamond)
    )

    application.add_handler(
        CommandHandler("addmoney", addmoney)
    )

    application.add_handler(
        CommandHandler("removediamond", removediamond)
    )

    application.add_handler(
        CommandHandler("removemoney", removemoney)
    )

    application.add_handler(
        CommandHandler("bankrot1", bankrot1)
    )

    application.add_handler(
        CommandHandler("bankrot2", bankrot2)
    )

    application.add_handler(
        CommandHandler("ban", ban)
    )

    application.add_handler(
        CommandHandler("unban", unban)
    )

    application.add_handler(
        CommandHandler("addadmin", addadmin)
    )

    application.add_handler(
        CommandHandler("removeadmin", removeadmin)
    )

    application.add_error_handler(error_handler)

    print("BOT IS RUNNING...")
    print(f"PORT: {PORT}")

    application.run_polling()


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
