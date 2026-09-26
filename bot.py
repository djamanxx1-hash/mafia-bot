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


# =========================================================
# 30 TA NOYOB ROL
# =========================================================

ROLES = [
    # 🔪 MAFIA
    {
        "name": "Don",
        "team": "Mafia",
        "description": "Mafiyaning boshlig'i. Mafia qarorlarini boshqaradi."
    },
    {
        "name": "Qotil",
        "team": "Mafia",
        "description": "Tunda bitta o'yinchini o'ldirishga urinadi."
    },
    {
        "name": "Zaharchi",
        "team": "Mafia",
        "description": "Tunda tanlagan o'yinchisini zaharlaydi. Zahar keyin ta'sir qiladi."
    },
    {
        "name": "Jimjit",
        "team": "Mafia",
        "description": "Tanlagan o'yinchisini keyingi kun jim bo'lishiga majbur qiladi."
    },
    {
        "name": "Soya",
        "team": "Mafia",
        "description": "Bir kecha Mafia a'zosini yashirib, uni tekshiruvlardan himoya qiladi."
    },
    {
        "name": "Bombachi",
        "team": "Mafia",
        "description": "Tanlagan o'yinchisiga yashirin bomba qo'yadi."
    },
    {
        "name": "Mafia Bankiri",
        "team": "Mafia",
        "description": "Mafia jamoasiga bir marta maxsus moliyaviy bonus beradi."
    },

    # 🏙️ SHAHAR
    {
        "name": "Detektiv",
        "team": "Shahar",
        "description": "Bir o'yinchining Mafia yoki boshqa tomon ekanini tekshiradi."
    },
    {
        "name": "Doktor",
        "team": "Shahar",
        "description": "Bir o'yinchini tunda o'limdan himoya qiladi."
    },
    {
        "name": "Qalqon",
        "team": "Shahar",
        "description": "Tanlagan odamiga hujumni o'ziga qabul qiladi."
    },
    {
        "name": "Kuzatuvchi",
        "team": "Shahar",
        "description": "Tanlagan o'yinchisiga kim tashrif buyurganini ko'radi."
    },
    {
        "name": "Qamoqchi",
        "team": "Shahar",
        "description": "Bir o'yinchining tungi qobiliyatini bloklaydi."
    },
    {
        "name": "Sudya",
        "team": "Shahar",
        "description": "Bir marta kunduzgi chiqarib yuborish qarorini bekor qiladi."
    },
    {
        "name": "Reanimator",
        "team": "Shahar",
        "description": "O'lgan bitta o'yinchini bir marta tiriltira oladi."
    },
    {
        "name": "Sovg'achi",
        "team": "Shahar",
        "description": "Har kecha tanlagan o'yinchisiga $10–100 va 1–5 almaz beradi."
    },
    {
        "name": "Muxbir",
        "team": "Shahar",
        "description": "Ikki o'yinchining bir tomonda yoki turli tomonda ekanini aniqlaydi."
    },
    {
        "name": "Sherif",
        "team": "Shahar",
        "description": "O'yin davomida bir marta o'z qurolidan foydalanib o'yinchini otishi mumkin."
    },

    # 🎭 MUSTAQIL
    {
        "name": "Joker",
        "team": "Mustaqil",
        "description": "Kunduzgi ovoz berishda chiqarib yuborilsa, o'zi g'olib bo'ladi."
    },
    {
        "name": "Ovchi",
        "team": "Mustaqil",
        "description": "Yashirin topshirig'idagi o'yinchini yo'q qilishga harakat qiladi."
    },
    {
        "name": "Yolg'iz Bo'ri",
        "team": "Mustaqil",
        "description": "Hamma tomonlarga qarshi kurashadi va oxirida yolg'iz qolishga harakat qiladi."
    },
    {
        "name": "Niqobchi",
        "team": "Mustaqil",
        "description": "Bir marta boshqa o'yinchining ko'rinishini oladi."
    },
    {
        "name": "O'g'ri",
        "team": "Mustaqil",
        "description": "Bir marta boshqa o'yinchining qobiliyatini o'g'irlashi mumkin."
    },
    {
        "name": "Arvoh",
        "team": "Mustaqil",
        "description": "O'lgandan keyin bir marta tirik o'yinchiga yashirin yordam beradi."
    },
    {
        "name": "Mukofotchi",
        "team": "Mustaqil",
        "description": "Bot unga yashirin nishon beradi. Nishon o'lsa, maxsus mukofot oladi."
    },

    # ⚡ MAXSUS
    {
        "name": "Aks-Sado",
        "team": "Maxsus",
        "description": "O'ziga ishlatilgan birinchi qobiliyatni uni ishlatgan odamga qaytaradi."
    },
    {
        "name": "Vaqtchi",
        "team": "Maxsus",
        "description": "Bir marta o'zini o'limdan saqlab qoladi."
    },
    {
        "name": "Shakl-Almashtiruvchi",
        "team": "Maxsus",
        "description": "Bir marta tirik o'yinchining rolini o'ziga oladi."
    },
    {
        "name": "Hacker",
        "team": "Maxsus",
        "description": "Bir o'yinchining keyingi tungi qobiliyatini o'chiradi."
    },
    {
        "name": "Folbin",
        "team": "Maxsus",
        "description": "O'yin davomida ikki marta o'yinchining tomonini aniqlaydi."
    },
    {
        "name": "Taqdirchi",
        "team": "Maxsus",
        "description": "Har kecha tasodifiy tirik o'yinchiga foydali yoki zararli ta'sir yuboradi."
    }
]


# =========================================================
# WEB SERVER
# =========================================================

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


# =========================================================
# PLAYER
# =========================================================

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


# =========================================================
# START
# =========================================================

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


# =========================================================
# ADMIN
# =========================================================

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


# =========================================================
# PROFILE
# =========================================================

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


# =========================================================
# BALANCE
# =========================================================

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):

    player = get_player(update.effective_user)

    await update.message.reply_text(

        f"💰 BALANS\n\n"
        f"💎 Almaz: {player['diamonds']}\n"
        f"💰 Money: {player['balance']}"
    )


# =========================================================
# MONEY
# =========================================================

async def money(update: Update, context: ContextTypes.DEFAULT_TYPE):

    player = get_player(update.effective_user)

    await update.message.reply_text(

        f"💰 MONEY\n\n"
        f"💰 Sizda: {player['balance']}"
    )


# =========================================================
# ADD DIAMONDS
# =========================================================

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


# =========================================================
# ADD BALANCE
# =========================================================

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
