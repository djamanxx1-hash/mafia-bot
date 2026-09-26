import os
import random
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# =========================
# SOZLAMALAR
# =========================

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

MAX_PLAYERS = 30
MIN_PLAYERS = 4

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# =========================
# MA'LUMOTLAR
# =========================

players = {}
admins = set()

game_players = {}
game_started = False

# =========================
# ROLLAR
# =========================

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
    ("Fuqarо", "👤"),
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

# =========================
# YORDAMCHI
# =========================

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

    return players[user_id]


def player_text(p):
    username = f"@{p['username']}" if p["username"] else "username yo'q"

    return (
        f"👤 Ism: {p['name']}\n"
        f"🆔 ID: `{p['id']}`\n"
        f"📱 Username: {username}\n\n"
        f"💎 Olmos: {p['diamonds']}\n"
        f"💰 Pul: {p['money']}\n"
        f"🎮 O'yinlar: {p['games']}\n"
        f"🏆 G'alabalar: {p['wins']}"
    )


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    p = get_player(user)

    if p["banned"]:
        await update.message.reply_text(
            "🚫 Siz botdan foydalanish huquqidan mahrum qilingansiz."
        )
        return

    await update.message.reply_text(
        "👑 OVERLORD MAFIA\n\n"
        "🎭 Sirlar • Intriga • G'alaba\n"
        "💎 Olmos • 💰 Pul • 🎁 Mukofotlar\n\n"
        "📌 Asosiy buyruqlar:\n"
        "/profile — profilingiz\n"
        "/money — balansingiz\n"
        "/players — o'yinchilar\n"
        "/newgame — yangi o'yin\n"
        "/join — o'yinga qo'shilish\n"
        "/startgame — o'yinni boshlash\n"
        "/top — reyting\n\n"
        "🔥 Har o'yin — yangi hikoya!"
    )


# =========================
# PROFILE
# =========================

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = get_player(update.effective_user)

    if p["banned"]:
        return

    await update.message.reply_text(
        "👤 SIZNING PROFILINGIZ\n\n" + player_text(p),
        parse_mode="Markdown",
    )


# =========================
# MONEY
# =========================

async def money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = get_player(update.effective_user)

    await update.message.reply_text(
        f"💰 BALANS\n\n"
        f"💎 Olmos: {p['diamonds']}\n"
        f"💰 Pul: {p['money']}"
    )


# =========================
# TOP
# =========================

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not players:
        await update.message.reply_text("📭 Hali o'yinchilar yo'q.")
        return

    sorted_players = sorted(
        players.values(),
        key=lambda x: x["money"],
        reverse=True,
    )

    text = "🏆 OVERLORD MAFIA — TOP\n\n"

    for i, p in enumerate(sorted_players[:10], start=1):
        text += f"{i}. {p['name']} — 💰 {p['money']}\n"

    await update.message.reply_text(text)


# =========================
# EXCHANGE
# =========================

async def exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = get_player(update.effective_user)

    if not context.args:
        await update.message.reply_text(
            "💎 Almashish:\n\n"
            "/exchange 100\n\n"
            "100 💎 = 10 000 💰"
        )
        return

    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Raqam kiriting.")
        return

    if amount <= 0:
        await update.message.reply_text("❌ Miqdor noto'g'ri.")
        return

    if p["diamonds"] < amount:
        await update.message.reply_text("❌ Sizda yetarli 💎 yo'q.")
        return

    money_amount = amount * 100

    p["diamonds"] -= amount
    p["money"] += money_amount

    await update.message.reply_text(
        f"✅ Almashuv amalga oshdi!\n\n"
        f"💎 -{amount}\n"
        f"💰 +{money_amount}"
    )


# =========================
# ADMIN PANEL
# =========================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 Siz admin emassiz.")
        return

    await update.message.reply_text(
        "👑 OVERLORD ADMIN PANEL\n\n"
        "👤 /profile ID\n"
        "💎 /adddiamond ID AMOUNT\n"
        "💰 /addmoney ID AMOUNT\n"
        "💎 /removediamond ID AMOUNT\n"
        "💰 /removemoney ID AMOUNT\n"
        "💎 /bankrot1 ID — olmosni 0 qiladi\n"
        "💰 /bankrot2 ID — pulni 0 qiladi\n"
        "🚫 /ban ID\n"
        "✅ /unban ID\n"
        "➕ /addadmin ID\n"
        "➖ /removeadmin ID"
    )


# =========================
# ADMIN: ADD DIAMOND
# =========================

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
        await update.message.reply_text("❌ ID va miqdor raqam bo'lishi kerak.")
        return

    if user_id not in players:
        players[user_id] = {
            "id": user_id,
            "name": "O'yinchi",
            "username": "",
            "diamonds": 0,
            "money": 0,
            "games": 0,
            "wins": 0,
            "banned": False,
        }

    players[user_id]["diamonds"] += amount

    await update.message.reply_text(
        f"✅ {user_id} ga 💎 {amount} qo'shildi."
    )


# =========================
# ADMIN: ADD MONEY
# =========================

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
        await update.message.reply_text("❌ ID va miqdor raqam bo'lishi kerak.")
        return

    if user_id not in players:
        players[user_id] = {
            "id": user_id,
            "name": "O'yinchi",
            "username": "",
            "diamonds": 0,
            "money": 0,
            "games": 0,
            "wins": 0,
            "banned": False,
        }

    players[user_id]["money"] += amount

    await update.message.reply_text(
        f"✅ {user_id} ga 💰 {amount} qo'shildi."
    )


# =========================
# REMOVE DIAMOND
# =========================

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
        await update.message.reply_text("❌ Raqam kiriting.")
        return

    if user_id not in players:
        await update.message.reply_text("❌ O'yinchi topilmadi.")
        return

    players[user_id]["diamonds"] = max(
        0,
        players[user_id]["diamonds"] - amount
    )

    await update.message.reply_text("✅ Olmos kamaytirildi.")


# =========================
# REMOVE MONEY
# =========================

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
        await update.message.reply_text("❌ Raqam kiriting.")
        return

    if user_id not in players:
        await update.message.reply_text("❌ O'yinchi topilmadi.")
        return

    players[user_id]["money"] = max(
        0,
        players[user_id]["money"] - amount
    )

    await update.message.reply_text("✅ Pul kamaytirildi.")


# =========================
# BANKROT
# =========================

async def bankrot1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("/bankrot1 ID")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID noto'g'ri.")
        return

    if user_id not in players:
        await update.message.reply_text("❌ O'yinchi topilmadi.")
        return

    players[user_id]["diamonds"] = 0

    await update.message.reply_text(
        f"💎 {user_id} ning barcha olmoslari 0 qilindi."
    )


async def bankrot2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("/bankrot2 ID")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID noto'g'ri.")
        return

    if user_id not in players:
        await update.message.reply_text("❌ O'yinchi topilmadi.")
        return

    players[user_id]["money"] = 0

    await update.message.reply_text(
        f"💰 {user_id} ning barcha pullari 0 qilindi."
    )


# =========================
# BAN / UNBAN
# =========================

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("/ban ID")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID noto'g'ri.")
        return

    if user_id not in players:
        await update.message.reply_text("❌ O'yinchi topilmadi.")
        return

    players[user_id]["banned"] = True

    await update.message.reply_text(f"🚫 {user_id} ban qilindi.")


async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("/unban ID")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID noto'g'ri.")
        return

    if user_id not in players:
        await update.message.reply_text("❌ O'yinchi topilmadi.")
        return

    players[user_id]["banned"] = False

    await update.message.reply_text(f"✅ {user_id} unban qilindi.")


# =========================
# ADD ADMIN
# =========================

async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("/addadmin ID")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID noto'g'ri.")
        return

    admins.add(user_id)

    await update.message.reply_text(
        f"👑 {user_id} admin qilindi."
    )


# =========================
# REMOVE ADMIN
# =========================

async def removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("/removeadmin ID")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID noto'g'ri.")
        return

    admins.discard(user_id)

    await update.message.reply_text(
        f"➖ {user_id} adminlikdan chiqarildi."
    )


# =========================
# NEW GAME
# =========================

async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_players
    global game_started

    if game_started:
        await update.message.reply_text(
            "⚠️ Hozir boshqa o'yin davom etmoqda."
        )
        return

    game_players = {}
    game_started = False

    await update.message.reply_text(
        "🎭 YANGI MAFIA O'YINI OCHILDI!\n\n"
        "👥 O'yinga qo'shilish uchun:\n"
        "/join\n\n"
        f"👤 Minimal: {MIN_PLAYERS} o'yinchi\n"
        f"👥 Maksimal: {MAX_PLAYERS} o'yinchi\n\n"
        "🔥 O'yin boshlanishini kuting..."
    )


# =========================
# JOIN
# =========================

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_players

    user = update.effective_user
    p = get_player(user)

    if p["banned"]:
        await update.message.reply_text("🚫 Siz ban qilingansiz.")
        return

    if game_started:
        await update.message.reply_text(
            "❌ O'yin allaqachon boshlangan."
        )
        return

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
    }

    await update.message.reply_text(
        f"✅ {user.first_name} o'yinga qo'shildi!\n\n"
        f"👥 O'yinchilar: {len(game_players)}/{MAX_PLAYERS}"
    )


# =========================
# PLAYERS
# =========================

async def players_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not game_players:
        await update.message.reply_text(
            "📭 Hozircha o'yinchilar yo'q."
        )
        return

    text = "👥 O'YINCHILAR\n\n"

    for i, p in enumerate(game_players.values(), start=1):
        text += f"{i}. {p['name']}\n"

    text += f"\n👤 Jami: {len(game_players)}"

    await update.message.reply_text(text)


# =========================
# START GAME
# =========================

async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_started

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
            f"❌ O'yinni boshlash uchun kamida "
            f"{MIN_PLAYERS} ta o'yinchi kerak.\n\n"
            f"👥 Hozir: {len(game_players)}"
        )
        return

    game_started = True

    player_list = list(game_players.values())
    random.shuffle(player_list)

    roles = ROLES[:len(player_list)]
    random.shuffle(roles)

    for player, role_data in zip(player_list, roles):
        role_name, emoji = role_data
        player["role"] = role_name

        if player["id"] in players:
            players[player["id"]]["games"] += 1

        try:
            await context.bot.send_message(
                chat_id=player["id"],
                text=(
                    "🎭 SIZNING MAXFIY ROLINGIZ\n\n"
                    f"{emoji} {role_name}\n\n"
                    "🤫 Bu xabar faqat siz uchun.\n"
                    "⚠️ ROLINGIZNI boshqa o'yinchilarga aytmang!"
                ),
            )
        except Exception:
            pass

    await update.message.reply_text(
        "🔥 MAFIA O'YINI BOSHLANDI!\n\n"
        f"👥 O'yinchilar: {len(player_list)}\n\n"
        "🎭 Rollar barcha o'yinchilarga maxfiy yuborildi.\n"
        "🌙 Tun boshlandi...\n\n"
        "🤫 O'yin davomida hushyor bo'ling!"
    )


# =========================
# MAIN
# =========================

def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN topilmadi.")

    if OWNER_ID == 0:
        raise ValueError("OWNER_ID topilmadi.")

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CommandHandler("money", money))
    application.add_handler(CommandHandler("top", top))
    application.add_handler(CommandHandler("exchange", exchange))

    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CommandHandler("adddiamond", adddiamond))
    application.add_handler(CommandHandler("addmoney", addmoney))
    application.add_handler(CommandHandler("removediamond", removediamond))
    application.add_handler(CommandHandler("removemoney", removemoney))
    application.add_handler(CommandHandler("bankrot1", bankrot1))
    application.add_handler(CommandHandler("bankrot2", bankrot2))
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(CommandHandler("unban", unban))
    application.add_handler(CommandHandler("addadmin", addadmin))
    application.add_handler(CommandHandler("removeadmin", removeadmin))

    application.add_handler(CommandHandler("newgame", newgame))
    application.add_handler(CommandHandler("join", join))
    application.add_handler(CommandHandler("players", players_command))
    application.add_handler(CommandHandler("startgame", startgame))

    print("🤖 OVERLORD MAFIA BOT IS RUNNING...")

    application.run_polling()


if __name__ == "__main__":
    main()
