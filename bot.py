import os
import threading
import random
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))
OWNER_ID = os.getenv("OWNER_ID")

players = {}

# Hozirgi Mafia o'yini
game_players = {}
game_started = False


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
    get_player(update.effective_user)

    await update.message.reply_text(
        "🕵️ MAFIA BOT ISHLAYAPTI!\n\n"
        "🎭 O'YIN:\n"
        "/newgame - yangi o'yin\n"
        "/join - o'yinga qo'shilish\n"
        "/players - o'yinchilar\n"
        "/startgame - o'yinni boshlash\n\n"
        "👤 PROFIL:\n"
        "/profile - profil\n"
        "/balance - balans\n"
        "/money - money\n\n"
        "👑 OWNER:\n"
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
        "💎 /bankrot1 ID\n"
        "💰 /bankrot2 ID"
    )


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = get_player(user)

    await update.message.reply_text(
        f"👤 PROFIL\n\n"
        f"📝 Ism: {player['name']}\n"
        f"🆔 ID: {user.id}\n\n"
        f"💎 Almaz: {player['diamonds']}\n"
        f"💰 Money: {player['balance']}\n"
        f"🎮 O'yinlar: {player['games']}"
    )


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player = get_player(update.effective_user)

    await update.message.reply_text(
        f"💰 BALANS\n\n"
        f"💎 Almaz: {player['diamonds']}\n"
        f"💰 Money: {player['balance']}"
    )


async def money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player = get_player(update.effective_user)

    await update.message.reply_text(
        f"💰 MONEY\n\n"
        f"💰 Sizda: {player['balance']}"
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
        f"✅ Money berildi!\n\n"
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
        f"💰 Money: 0"
    )


# =========================
# MAFIA O'YINI
# =========================

async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_players, game_started

    if game_started:
        await update.message.reply_text(
            "⚠️ Hozir o'yin davom etmoqda."
        )
        return

    game_players = {}

    await update.message.reply_text(
        "🎭 YANGI MAFIA O'YINI OCHILDI!\n\n"
        "👥 O'yinga kirish uchun:\n"
        "/join\n\n"
        "📋 O'yinchilarni ko'rish:\n"
        "/players\n\n"
        "▶️ Yetarli o'yinchi bo'lgach:\n"
        "/startgame"
    )


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_started

    if game_started:
        await update.message.reply_text(
            "⚠️ O'yin allaqachon boshlangan."
        )
        return

    user = update.effective_user
    get_player(user)

    if user.id in game_players:
        await update.message.reply_text(
            "ℹ️ Siz allaqachon o'yindasiz."
        )
        return

    game_players[user.id] = {
        "name": user.full_name,
        "role": None
    }

    await update.message.reply_text(
        f"✅ {user.full_name}, siz Mafia o'yiniga qo'shildingiz!\n\n"
        f"👥 Hozirgi o'yinchilar: {len(game_players)}"
    )


async def players_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not game_players:
        await update.message.reply_text(
            "👥 Hozircha o'yinda hech kim yo'q.\n\n"
            "/join orqali qo'shiling."
        )
        return

    text = "👥 MAFIA O'YINCHILARI:\n\n"

    for number, player in enumerate(game_players.values(), start=1):
        text += f"{number}. {player['name']}\n"

    text += f"\n👥 Jami: {len(game_players)}"

    await update.message.reply_text(text)


async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_started

    if game_started:
        await update.message.reply_text(
            "⚠️ O'yin allaqachon boshlangan."
        )
        return

    if len(game_players) < 4:
        await update.message.reply_text(
            "⚠️ O'yinni boshlash uchun kamida 4 ta o'yinchi kerak.\n\n"
            f"👥 Hozir: {len(game_players)}\n"
            "👥 Kerak: 4"
        )
        return

    user_ids = list(game_players.keys())
    random.shuffle(user_ids)

    roles = []

    # 4-6 o'yinchi
    if len(user_ids) <= 6:
        roles = ["🔪 Mafia", "🕵️ Detektiv", "👨‍⚕️ Doktor"]
        roles += ["👤 Fuqaro"] * (len(user_ids) - 3)

    # 7-9 o'yinchi
    else:
        roles = [
            "🔪 Mafia",
            "🔪 Mafia",
            "🕵️ Detektiv",
            "👨‍⚕️ Doktor"
        ]
        roles += ["👤 Fuqaro"] * (len(user_ids) - 4)

    random.shuffle(roles)

    for user_id, role in zip(user_ids, roles):
        game_players[user_id]["role"] = role

    game_started = True

    await update.message.reply_text(
        "🎭 MAFIA O'YINI BOSHLANDI!\n\n"
        f"👥 O'yinchilar: {len(game_players)}\n\n"
        "📩 Har bir o'yinchiga o'z roli shaxsiy xabarda yuboriladi."
    )

    # Rollarni shaxsiy xabarda yuborish
    for user_id in user_ids:
        role = game_players[user_id]["role"]

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "🎭 MAFIA O'YINI\n\n"
                    f"🎴 Sizning rolingiz: {role}\n\n"
                    "⚠️ Bu rolni boshqa o'yinchilarga aytmang."
                )
            )
        except Exception:
            pass

    # O'yin hisoblagichi
    for user_id in user_ids:
        players[user_id]["games"] += 1


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
    app.add_handler(CommandHandler("money", money))

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
