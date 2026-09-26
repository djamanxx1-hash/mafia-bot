import os
import random
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))
OWNER_ID = os.getenv("OWNER_ID")

players = {}

game_players = {}
game_started = False


# ==================================================
# 30 TA ROL
# ==================================================

ROLES = [
    ("Don", "Mafia", "Mafiyaning boshlig'i."),
    ("Qotil", "Mafia", "Tunda bitta o'yinchini o'ldirishga urinadi."),
    ("Zaharchi", "Mafia", "Tanlagan o'yinchisini zaharlaydi."),
    ("Jimjit", "Mafia", "Tanlagan o'yinchisini keyingi kun jim qiladi."),
    ("Soya", "Mafia", "Mafia a'zosini tekshiruvdan yashiradi."),
    ("Bombachi", "Mafia", "Tanlagan o'yinchisiga yashirin bomba qo'yadi."),
    ("Mafia Bankiri", "Mafia", "Mafia uchun maxsus moliyaviy bonus beradi."),

    ("Detektiv", "Shahar", "Bir o'yinchining tomonini tekshiradi."),
    ("Doktor", "Shahar", "Bir o'yinchini tunda himoya qiladi."),
    ("Qalqon", "Shahar", "Hujumni o'ziga qabul qiladi."),
    ("Kuzatuvchi", "Shahar", "Tanlangan o'yinchiga kim borganini ko'radi."),
    ("Qamoqchi", "Shahar", "Bir o'yinchining tungi qobiliyatini bloklaydi."),
    ("Sudya", "Shahar", "Bir marta kunduzgi chiqarishni bekor qiladi."),
    ("Reanimator", "Shahar", "Bir o'lgan o'yinchini tiriltiradi."),
    ("Sovg'achi", "Shahar", "Har kecha $10-100 va 1-5 almaz beradi."),
    ("Muxbir", "Shahar", "Ikki o'yinchining tomonini taqqoslaydi."),
    ("Sherif", "Shahar", "Bir marta o'yinchini otishi mumkin."),

    ("Joker", "Mustaqil", "Kunduzgi ovoz bilan chiqarilsa g'olib bo'ladi."),
    ("Ovchi", "Mustaqil", "Yashirin nishonini yo'q qilishga harakat qiladi."),
    ("Yolg'iz Bo'ri", "Mustaqil", "Barcha tomonlarga qarshi o'ynaydi."),
    ("Niqobchi", "Mustaqil", "Bir marta boshqa rol ko'rinishini oladi."),
    ("O'g'ri", "Mustaqil", "Bir marta boshqa o'yinchining qobiliyatini oladi."),
    ("Arvoh", "Mustaqil", "O'lgandan keyin bir marta yordam beradi."),
    ("Mukofotchi", "Mustaqil", "Yashirin nishoni o'lsa mukofot oladi."),

    ("Aks-Sado", "Maxsus", "O'ziga ishlatilgan birinchi qobiliyatni qaytaradi."),
    ("Vaqtchi", "Maxsus", "Bir marta o'zini o'limdan saqlaydi."),
    ("Shakl-Almashtiruvchi", "Maxsus", "Bir marta boshqa tirik o'yinchining rolini oladi."),
    ("Hacker", "Maxsus", "Bir o'yinchining keyingi qobiliyatini o'chiradi."),
    ("Folbin", "Maxsus", "Ikki marta o'yinchining tomonini biladi."),
    ("Taqdirchi", "Maxsus", "Tasodifiy o'yinchiga foydali yoki zararli ta'sir beradi.")
]


# ==================================================
# WEB SERVER
# ==================================================

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


# ==================================================
# PLAYER
# ==================================================

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


# ==================================================
# START
# ==================================================

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


# ==================================================
# ADMIN
# ==================================================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if str(update.effective_user.id) != OWNER_ID:
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
