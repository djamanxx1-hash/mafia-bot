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


# =========================
# SOZLAMALAR
# =========================

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = os.getenv("OWNER_ID")


# =========================
# O'YIN MA'LUMOTLARI
# =========================

players = {}
game_players = []
game_started = False


# =========================
# 30 TA ROL
# =========================

ROLES = [
    ("Don", "Mafia", "Mafia boshlig'i. Mafia jamoasini boshqaradi."),
    ("Qotil", "Mafia", "Har kecha bitta o'yinchini o'ldirishga harakat qiladi."),
    ("Zaharchi", "Mafia", "Tanlagan o'yinchisiga zahar beradi. Ta'siri kechikib ishlaydi."),
    ("Jimjit", "Mafia", "Tanlagan o'yinchisi keyingi kuni gapira olmaydi."),
    ("Soya", "Mafia", "Bir mafia a'zosini tekshiruvlardan yashiradi."),
    ("Bombachi", "Mafia", "Bir o'yinchiga yashirin bomba qo'yadi."),
    ("Mafia Bankiri", "Mafia", "Mafia jamoasiga maxsus pul mukofotlari beradi."),

    ("Detektiv", "Shahar", "Kecha bir o'yinchini tekshiradi va uning mafia ekanini biladi."),
    ("Doktor", "Shahar", "Har kecha bir o'yinchini o'limdan himoya qiladi."),
    ("Qalqon", "Shahar", "Tanlagan o'yinchisiga kelgan hujumni o'ziga olishi mumkin."),
    ("Kuzatuvchi", "Shahar", "Bir o'yinchiga kim tashrif buyurganini kuzatadi."),
    ("Qamoqchi", "Shahar", "Bir o'yinchining tungi qobiliyatini bloklaydi."),
    ("Sudya", "Shahar", "Bir marta kunduzgi chiqarib yuborishni bekor qiladi."),
    ("Reanimator", "Shahar", "Bir marta o'lgan o'yinchini tiriltirishi mumkin."),
    ("Sovg'achi", "Shahar", "Har kecha bir o'yinchiga tasodifiy 10-100 dollar va 1-5 olmos beradi."),
    ("Muxbir", "Shahar", "Ikki o'yinchining bir tomonda yoki turli tomonda ekanini tekshiradi."),
    ("Sherif", "Shahar", "Bir marta o'z quroli bilan o'yinchini otishi mumkin."),

    ("Joker", "Mustaqil", "Kunduzgi ovoz berishda chiqarilsa, o'zi g'alaba qiladi."),
    ("Ovchi", "Mustaqil", "Yashirin nishonini topib yo'q qilishi kerak."),
    ("Yolg'iz Bo'ri", "Mustaqil", "Mustaqil qotil. Oxirida yolg'iz qolishga harakat qiladi."),
    ("Niqobchi", "Mustaqil", "Bir marta boshqa rol ko'rinishini oladi."),
    ("O'g'ri", "Mustaqil", "Bir marta boshqa o'yinchining qobiliyatini o'g'irlaydi."),
    ("Arvoh", "Mustaqil", "O'lgandan keyin bir marta tirik o'yinchiga yordam beradi."),
    ("Mukofotchi", "Mustaqil", "Yashirin nishoni bor. Nishon yo'q qilinsa vazifasi bajariladi."),

    ("Aks-Sado", "Maxsus", "Unga ishlatilgan birinchi qobiliyat qobiliyat egasiga qaytadi."),
    ("Vaqtchi", "Maxsus", "Bir marta o'zini o'limdan saqlab qolishi mumkin."),
    ("Shakl-Almashtiruvchi", "Maxsus", "Bir marta boshqa tirik o'yinchining roliga aylanadi."),
    ("Hacker", "Maxsus", "Bir o'yinchining keyingi tungi qobiliyatini o'chiradi."),
    ("Folbin", "Maxsus", "Ikki marta o'yinchining tomonini bilishi mumkin."),
    ("Taqdirchi", "Maxsus", "Har kecha tasodifiy tirik o'yinchiga foydali yoki zararli ta'sir yuboradi."),
]


# =========================
# WEB SERVER
# RENDER PORT UCHUN
# =========================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def run_web_server():
    port = int(os.getenv("PORT", "10000"))

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    server.serve_forever()


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if user.id not in players:
        players[user.id] = {
            "id": user.id,
            "name": user.first_name or "Noma'lum",
            "diamonds": 0,
            "balance": 0,
            "games": 0,
            "role": None,
            "team": None,
            "alive": True,
        }

    await update.message.reply_text(
        "Mafia botiga xush kelibsiz!\n\n"
        "Buyruqlar:\n"
        "/newgame - yangi o'yin\n"
        "/join - o'yinga qo'shilish\n"
        "/players - o'yinchilar\n"
        "/startgame - o'yinni boshlash\n"
        "/profile - profil\n"
        "/balance - pul\n"
        "/money - pul miqdori\n"
        "/admin - admin panel"
    )


# =========================
# NEW GAME
# =========================

async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global game_players
    global game_started

    game_players = []
    game_started = False

    await update.message.reply_text(
        "Yangi Mafia o'yini yaratildi!\n\n"
        "O'yinga kirish uchun /join bosing."
    )


# =========================
# JOIN
# =========================

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global game_players

    user = update.effective_user

    if game_started:
        await update.message.reply_text(
            "O'yin allaqachon boshlangan."
        )
        return

    if user.id not in players:
        players[user.id] = {
            "id": user.id,
            "name": user.first_name or "Noma'lum",
            "diamonds": 0,
            "balance": 0,
            "games": 0,
            "role": None,
            "team": None,
            "alive": True,
        }

    if user.id in game_players:
        await update.message.reply_text(
            "Siz allaqachon o'yindasiz."
        )
        return

    game_players.append(user.id)

    await update.message.reply_text(
        f"{user.first_name} o'yinga qo'shildi.\n"
        f"O'yinchilar soni: {len(game_players)}"
    )


# =========================
# PLAYERS
# =========================

async def players_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not game_players:
        await update.message.reply_text(
            "Hozircha o'yinchilar yo'q."
        )
        return

    text = "O'yinchilar:\n\n"

    for number, user_id in enumerate(game_players, 1):

        if user_id in players:
            player = players[user_id]

            status = "Tirik" if player["alive"] else "O'lgan"

            text += (
                f"{number}. {player['name']} - {status}\n"
            )

    await update.message.reply_text(text)


# =========================
# PROFIL
# =========================

async def profile(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if user.id not in players:
        players[user.id] = {
            "id": user.id,
            "name": user.first_name or "Noma'lum",
            "diamonds": 0,
            "balance": 0,
            "games": 0,
            "role": None,
            "team": None,
            "alive": True,
        }

    player = players[user.id]

    role_text = player["role"] or "Hali rol berilmagan"

    await update.message.reply_text(
        "PROFIL\n\n"
        f"Ism: {player['name']}\n"
        f"ID: {player['id']}\n"
        f"Olmos: {player['diamonds']}\n"
        f"Pul: ${player['balance']}\n"
        f"O'yinlar: {player['games']}\n"
        f"Rol: {role_text}"
    )


# =========================
# BALANCE
# =========================

async def balance(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if user.id not in players:
        await update.message.reply_text(
            "Avval /start bosing."
        )
        return

    await update.message.reply_text(
        f"Sizning balansingiz: ${players[user.id]['balance']}"
    )


# =========================
# MONEY
# =========================

async def money(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if user.id not in players:
        await update.message.reply_text(
            "Avval /start bosing."
        )
        return

    await update.message.reply_text(
        f"Money: ${players[user.id]['balance']}"
    )


# =========================
# ADMIN TEKSHIRUVI
# =========================

def is_owner(user_id):

    if not OWNER_ID:
        return False

    return str(user_id) == str(OWNER_ID)


# =========================
# ADMIN
# =========================

async def admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_owner(update.effective_user.id):
        await update.message.reply_text(
            "Sizda admin huquqi yo'q."
        )
        return

    await update.message.reply_text(
        "OWNER PANEL\n\n"
        "/adddiamonds ID MIQDOR\n"
        "/addbalance ID MIQDOR\n"
        "/bankrot1 ID\n"
        "/bankrot2 ID"
    )


# =========================
# ADD DIAMONDS
# =========================

async def adddiamonds(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_owner(update.effective_user.id):
        await update.message.reply_text(
            "Sizda admin huquqi yo'q."
        )
        return

    if len(context.args) != 2:
        await update.message.reply_text(
            "Foydalanish:\n"
            "/adddiamonds ID MIQDOR"
        )
        return

    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "ID va miqdor raqam bo'lishi kerak."
        )
        return

    if amount <= 0:
        await update.message.reply_text(
            "Miqdor 0 dan katta bo'lishi kerak."
        )
        return

    if user_id not in players:
        players[user_id] = {
            "id": user_id,
            "name": "Noma'lum",
            "diamonds": 0,
            "balance": 0,
            "games": 0,
            "role": None,
            "team": None,
            "alive": True,
        }

    players[user_id]["diamonds"] += amount

    await update.message.reply_text(
        f"{user_id} ID ga {amount} ta olmos berildi."
    )


# =========================
# ADD BALANCE
# =========================

async def addbalance(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_owner(update.effective_user.id):
        await update.message.reply_text(
            "Sizda admin huquqi yo'q."
        )
        return

    if len(context.args) != 2:
        await update.message.reply_text(
            "Foydalanish:\n"
            "/addbalance ID MIQDOR"
        )
        return

    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "ID va miqdor raqam bo'lishi kerak."
        )
        return

    if amount <= 0:
        await update.message.reply_text(
            "Miqdor 0 dan katta bo'lishi kerak."
        )
        return

    if user_id not in players:
        players[user_id] = {
            "id": user_id,
            "name": "Noma'lum",
            "diamonds": 0,
            "balance": 0,
            "games": 0,
            "role": None,
            "team": None,
            "alive": True,
        }

    players[user_id]["balance"] += amount

    await update.message.reply_text(
        f"{user_id} ID ga ${amount} berildi."
    )


# =========================
# BANKROT 1
# OLmosni 0 qilish
# =========================

async def bankrot1(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_owner(update.effective_user.id):
        await update.message.reply_text(
            "Sizda admin huquqi yo'q."
        )
        return

    if len(context.args) != 1:
        await update.message.reply_text(
            "Foydalanish:\n"
            "/bankrot1 ID"
        )
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "ID raqam bo'lishi kerak."
        )
        return

    if user_id not in players:
        await update.message.reply_text(
            "Bu ID topilmadi."
        )
        return

    players[user_id]["diamonds"] = 0

    await update.message.reply_text(
        f"{user_id} ID ning olmoslari 0 qilindi."
    )


# =========================
# BANKROT 2
# PULNI 0 QILISH
# =========================

async def bankrot2(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_owner(update.effective_user.id):
        await update.message.reply_text(
            "Sizda admin huquqi yo'q."
        )
        return

    if len(context.args) != 1:
        await update.message.reply_text(
            "Foydalanish:\n"
            "/bankrot2 ID"
        )
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "ID raqam bo'lishi kerak."
        )
        return

    if user_id not in players:
        await update.message.reply_text(
            "Bu ID topilmadi."
        )
        return

    players[user_id]["balance"] = 0

    await update.message.reply_text(
        f"{user_id} ID ning puli 0 qilindi."
    )


# =========================
# ROLLAR YARATISH
# =========================

def create_roles(player_count):

    selected = []

    don = ROLES[0]
    selected.append(don)

    remaining_roles = ROLES[1:].copy()
    random.shuffle(remaining_roles)

    needed = player_count - 1

    if needed > 0:
        selected.extend(
            remaining_roles[:needed]
        )

    random.shuffle(selected)

    return selected


# =========================
# O'YINNI BOSHLASH
# =========================

async def startgame(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    global game_started

    if game_started:
        await update.message.reply_text(
            "O'yin allaqachon boshlangan."
        )
        return

    if len(game_players) < 3:
        await update.message.reply_text(
            "O'yinni boshlash uchun kamida 3 ta o'yinchi kerak."
        )
        return

    roles = create_roles(len(game_players))

    for index, user_id in enumerate(game_players):

        role_name, team, description = roles[index]

        players[user_id]["role"] = role_name
        players[user_id]["team"] = team
        players[user_id]["alive"] = True
        players[user_id]["games"] += 1

        try:

            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "MAFIA O'YINI BOSHLANDI\n\n"
                    f"Sizning rolingiz: {role_name}\n"
                    f"Tomoningiz: {team}\n\n"
                    f"Vazifangiz:\n{description}"
                )
            )

        except Exception:
            pass

    game_started = True

    await update.message.reply_text(
        "O'yin boshlandi.\n\n"
        "Barcha o'yinchilarga rollari shaxsiy xabarda yuborildi."
    )


# =========================
# MAIN
# =========================

def main():

    print("MAIN BOSHLANDI", flush=True)

    if not TOKEN:
        print(
            "XATO: BOT_TOKEN topilmadi.",
            flush=True
        )
        return

    if not OWNER_ID:
        print(
            "XATO: OWNER_ID topilmadi.",
            flush=True
        )
        return

    print("TOKEN TOPILDI", flush=True)
    print("OWNER_ID TOPILDI", flush=True)

    threading.Thread(
        target=run_web_server,
        daemon=True
    ).start()

    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

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
        CommandHandler("profile", profile)
    )

    application.add_handler(
        CommandHandler("balance", balance)
    )

    application.add_handler(
        CommandHandler("money", money)
    )

    application.add_handler(
        CommandHandler("admin", admin)
    )

    application.add_handler(
        CommandHandler("adddiamonds", adddiamonds)
    )

    application.add_handler(
        CommandHandler("addbalance", addbalance)
    )

    application.add_handler(
        CommandHandler("bankrot1", bankrot1)
    )

    application.add_handler(
        CommandHandler("bankrot2", bankrot2)
    )

    print("BOT ISHGA TUSHYAPTI", flush=True)

    application.run_polling()


# =========================
# ENG MUHIM QISM
# =========================

if __name__ == "__main__":
    main()
