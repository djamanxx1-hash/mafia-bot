
import os
import random
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

TOKEN = os.getenv("BOT_TOKEN")

games = {}


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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🕵️ Mafia botga xush kelibsiz!\n\n"
        "🎭 O'yinni boshlash uchun:\n"
        "/newgame — yangi o'yin\n"
        "/join — o'yinga qo'shilish\n"
        "/players — o'yinchilarni ko'rish\n"
        "/startgame — o'yinni boshlash"
    )


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
        "O'yinga kirish uchun /join bosing.\n"
        "👥 O'yinchilar: /players"
    )


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = get_game(chat_id)

    if game["started"]:
        await update.message.reply_text("❌ O'yin allaqachon boshlangan!")
        return

    user = update.effective_user

    if any(p["id"] == user.id for p in game["players"]):
        await update.message.reply_text("⚠️ Siz allaqachon o'yindasiz!")
        return

    game["players"].append({
        "id": user.id,
        "name": user.first_name,
    })

    await update.message.reply_text(
        f"✅ {user.first_name} o'yinga qo'shildi!\n"
        f"👥 Jami o'yinchilar: {len(game['players'])}"
    )


async def players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = get_game(chat_id)

    if not game["players"]:
        await update.message.reply_text("👥 Hozircha o'yinchilar yo'q.")
        return

    text = "👥 O'yinchilar:\n\n"

    for i, player in enumerate(game["players"], 1):
        text += f"{i}. {player['name']}\n"

    await update.message.reply_text(text)


async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = get_game(chat_id)

    if game["started"]:
        await update.message.reply_text("❌ O'yin allaqachon boshlangan!")
        return

    count = len(game["players"])

    if count < 4:
        await update.message.reply_text(
            "❌ O'yinni boshlash uchun kamida 4 ta o'yinchi kerak!"
        )
        return

    # Rollar
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

    game["alive"] = [player["id"] for player in game["players"]]
    game["started"] = True
    game["phase"] = "night"

    await update.message.reply_text(
        "🎭 MAFIA O'YINI BOSHLANDI!\n\n"
        "🌙 Kecha boshlandi.\n"
        "📩 Har bir o'yinchiga o'z roli shaxsiy xabarda yuboriladi."
    )

    # Rollarni shaxsiy xabarda yuborish
    for player in game["players"]:
        try:
            await context.bot.send_message(
                chat_id=player["id"],
                text=(
                    "🎭 SIZNING ROLINGIZ\n\n"
                    f"{game['roles'][player['id']]}\n\n"
                    "🤫 Rolingizni hech kimga aytmang!"
                ),
            )
        except Exception:
            pass


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = get_game(chat_id)

    if not game["started"]:
        await update.message.reply_text("⏳ Hozircha o'yin boshlanmagan.")
        return

    alive_names = []

    for player in game["players"]:
        if player["id"] in game["alive"]:
            alive_names.append(player["name"])

    await update.message.reply_text(
        f"🎭 O'yin holati\n\n"
        f"🌙/☀️ Bosqich: {game['phase']}\n"
        f"❤️ Tiriklar: {len(alive_names)}\n\n"
        + "\n".join(f"• {name}" for name in alive_names)
    )


def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN topilmadi!")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newgame", newgame))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("players", players))
    app.add_handler(CommandHandler("startgame", startgame))
    app.add_handler(CommandHandler("status", status))

    print("🤖 Mafia bot ishga tushdi!")

    app.run_polling()


if __name__ == "__main__":
    main()
