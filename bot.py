import os
import random
import sqlite3
import logging
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import (
    Update,
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)


# =========================================================
# SOZLAMALAR
# =========================================================

TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
PORT = int(os.getenv("PORT", "10000"))
DB_PATH = os.getenv("DB_PATH", "mafia.db")

# Guruhdagi faza rasmlari
NIGHT_IMAGE_FILE_ID = os.getenv("NIGHT_IMAGE_FILE_ID", "").strip()
DAY_IMAGE_FILE_ID = os.getenv("DAY_IMAGE_FILE_ID", "").strip()
VOTE_IMAGE_FILE_ID = os.getenv("VOTE_IMAGE_FILE_ID", "").strip()
WIN_IMAGE_FILE_ID = os.getenv("WIN_IMAGE_FILE_ID", "").strip()

# Almaz animatsiyasi
DIAMOND_ANIMATION_FILE_ID = os.getenv(
    "DIAMOND_ANIMATION_FILE_ID", ""
).strip()

MAX_PLAYERS = 30
MIN_PLAYERS = 4
CHANGE_MAX = 50


# =========================================================
# LOG
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# DATABASE
# =========================================================

def db():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()

    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            username TEXT DEFAULT '',
            diamonds INTEGER DEFAULT 0,
            money INTEGER DEFAULT 0,
            dollars INTEGER DEFAULT 0,
            games INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            points INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS point_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            points INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            reason TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS group_members (
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY(chat_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS protections (
            user_id INTEGER PRIMARY KEY,
            universal INTEGER DEFAULT 0,
            vote INTEGER DEFAULT 0,
            fake_doc INTEGER DEFAULT 0,
            protect_other INTEGER DEFAULT 0,
            killer INTEGER DEFAULT 0,
            silence INTEGER DEFAULT 0,
            poison INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS changes (
            chat_id INTEGER PRIMARY KEY,
            creator_id INTEGER NOT NULL,
            prize INTEGER NOT NULL,
            message_id INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS change_participants (
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY(chat_id, user_id)
        );
        """
    )

    if OWNER_ID:
        con.execute(
            "INSERT OR IGNORE INTO admins(user_id) VALUES (?)",
            (OWNER_ID,),
        )

    con.commit()
    con.close()


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
    server = HTTPServer(
        ("0.0.0.0", PORT),
        HealthHandler,
    )

    logger.info(
        "Health server PORT %s da ishga tushdi",
        PORT,
    )

    server.serve_forever()


# =========================================================
# GLOBAL HOLATLAR
# =========================================================

admins = set()

games = {}

pending_inputs = {}

change_locks = set()


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
    ("Manyak", "☠️"),
    ("O'g'ri", "🥷"),
    ("Qasoskor", "⚔️"),
]

ROLES += [
    ("Fuqaro", "👤")
] * 12


ROLE_POINTS = {
    "Mafia": 100,
    "Don": 120,
    "Godfather": 120,
    "Komissar": 100,
    "Sherif": 100,
    "Doktor": 100,
    "Bodyguard": 100,
    "Advokat": 100,
    "Detektiv": 100,
    "Snayper": 120,
    "Jurnalist": 90,
    "Haker": 100,
    "Psixolog": 90,
    "Sevishgan": 80,
    "Manyak": 150,
    "O'g'ri": 100,
    "Qasoskor": 130,
    "Fuqaro": 50,
}


# =========================================================
# HIMOYALAR
# =========================================================

PROTECTIONS = {
    "universal": (
        "🛡️ Universal himoya",
        "$100",
        "Mafia va Manyak kabi odatiy hujumlardan "
        "himoya qiladi. Don va Komissar hujumlariga "
        "taalluqli emas.",
    ),

    "vote": (
        "🗳️ Ovoz himoyasi",
        "💎 1",
        "Ovoz orqali chiqarib yuborilishdan "
        "bir marta himoya qiladi.",
    ),

    "fake_doc": (
        "📄 Soxta hujjat",
        "$200",
        "Tekshiruv vaqtida haqiqiy rolingiz o‘rniga "
        "soxta ma'lumot ko‘rsatiladi.",
    ),

    "protect_other": (
        "🤝 Boshqa o‘yinchini himoyalash",
        "💎 5",
        "Bir kechada boshqa o‘yinchini himoya "
        "qilish imkonini beradi.",
    ),

    "killer": (
        "⚔️ Qotilga qarshi himoya",
        "💎 3",
        "Manyak/qotil hujumidan bir marta "
        "himoya qiladi.",
    ),

    "silence": (
        "🔇 Ovoz bloklash",
        "$100",
        "Tanlangan o‘yinchining ovoz berishini "
        "bir kechaga bloklaydi.",
    ),

    "poison": (
        "☠️ Zahar himoyasi",
        "💎 3",
        "Zahar ta'siridan bir marta himoya qiladi.",
    ),
}


# =========================================================
# O'YIN
# =========================================================

def new_game(chat_id):
    return {
        "chat_id": chat_id,
        "players": {},
        "started": False,
        "phase": "lobby",
        "night": 0,
        "actions": {},
        "votes": {},
        "protected": set(),
        "vote_protected": set(),
        "silenced": set(),
        "killer_protected": set(),
        "poison_protected": set(),
        "fake_doc": set(),
    }


def game_for(chat_id):
    if chat_id not in games:
        games[chat_id] = new_game(chat_id)

    return games[chat_id]


def alive_players(game):
    return {
        uid: p
        for uid, p in game["players"].items()
        if p["alive"]
    }


def role_of(game, user_id):
    player = game["players"].get(user_id)

    if player:
        return player["role"]

    return None


# =========================================================
# UMUMIY FUNKSIYALAR
# =========================================================

def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds")


def get_player(user):
    con = db()

    row = con.execute(
        "SELECT * FROM players WHERE user_id=?",
        (user.id,),
    ).fetchone()

    if row is None:
        con.execute(
            """
            INSERT INTO players(
                user_id,
                name,
                username
            )
            VALUES(?,?,?)
            """,
            (
                user.id,
                user.full_name[:100],
                user.username or "",
            ),
        )

    else:
        con.execute(
            """
            UPDATE players
            SET name=?, username=?
            WHERE user_id=?
            """,
            (
                user.full_name[:100],
                user.username or "",
                user.id,
            ),
        )

    con.commit()

    row = con.execute(
        "SELECT * FROM players WHERE user_id=?",
        (user.id,),
    ).fetchone()

    con.close()

    return row


def get_player_by_id(user_id):
    con = db()

    row = con.execute(
        "SELECT * FROM players WHERE user_id=?",
        (user_id,),
    ).fetchone()

    con.close()

    return row


def save_balances(
    user_id,
    diamonds=None,
    money=None,
    dollars=None,
):
    con = db()

    row = con.execute(
        "SELECT * FROM players WHERE user_id=?",
        (user_id,),
    ).fetchone()

    if not row:
        con.close()
        return False

    new_diamonds = (
        row["diamonds"]
        if diamonds is None
        else diamonds
    )

    new_money = (
        row["money"]
        if money is None
        else money
    )

    new_dollars = (
        row["dollars"]
        if dollars is None
        else dollars
    )

    if (
        new_diamonds < 0
        or new_money < 0
        or new_dollars < 0
    ):
        con.close()
        return False

    con.execute(
        """
        UPDATE players
        SET diamonds=?,
            money=?,
            dollars=?
        WHERE user_id=?
        """,
        (
            new_diamonds,
            new_money,
            new_dollars,
            user_id,
        ),
    )

    con.commit()
    con.close()

    return True


def add_points(user_id, amount, reason=""):
    if amount <= 0:
        return

    con = db()

    con.execute(
        """
        UPDATE players
        SET points=points+?
        WHERE user_id=?
        """,
        (
            amount,
            user_id,
        ),
    )

    con.execute(
        """
        INSERT INTO point_events(
            user_id,
            points,
            created_at,
            reason
        )
        VALUES(?,?,?,?)
        """,
        (
            user_id,
            amount,
            now_iso(),
            reason,
        ),
    )

    con.commit()
    con.close()


def add_stats(
    user_id,
    games_count=0,
    wins=0,
):
    con = db()

    con.execute(
        """
        UPDATE players
        SET games=games+?,
            wins=wins+?
        WHERE user_id=?
        """,
        (
            games_count,
            wins,
            user_id,
        ),
    )

    con.commit()
    con.close()


def parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def display_name(user_id):
    row = get_player_by_id(user_id)

    if not row:
        return str(user_id)

    return (
        row["name"]
        or row["username"]
        or str(user_id)
    )


def mention(user_id):
    row = get_player_by_id(user_id)

    if row:
        name = row["name"][:40]
    else:
        name = str(user_id)

    return (
        f'<a href="tg://user?id={user_id}">'
        f"{name}"
        f"</a>"
    )


# =========================================================
# ADMIN
# =========================================================

def is_owner(user_id):
    return (
        OWNER_ID != 0
        and user_id == OWNER_ID
    )


def is_admin(user_id):
    return (
        is_owner(user_id)
        or user_id in admins
    )


def load_admins():
    global admins

    con = db()

    rows = con.execute(
        "SELECT user_id FROM admins"
    ).fetchall()

    admins = {
        row[0]
        for row in rows
    }

    con.close()


def banned(user_id):
    row = get_player_by_id(user_id)

    return bool(
        row
        and row["banned"]
    )


# =========================================================
# GROUP TRACKING
# =========================================================

def track_group_user(update):
    if (
        not update.effective_chat
        or update.effective_chat.type == "private"
        or not update.effective_user
    ):
        return

    con = db()

    con.execute(
        """
        INSERT OR IGNORE INTO group_members(
            chat_id,
            user_id
        )
        VALUES(?,?)
        """,
        (
            update.effective_chat.id,
            update.effective_user.id,
        ),
    )

    con.commit()
    con.close()


# =========================================================
# PROTECTION DATABASE
# =========================================================

def ensure_protection_row(user_id):
    con = db()

    con.execute(
        """
        INSERT OR IGNORE INTO protections(user_id)
        VALUES(?)
        """,
        (user_id,),
    )

    con.commit()
    con.close()


def protection_count(user_id, key):
    ensure_protection_row(user_id)

    con = db()

    row = con.execute(
        f"SELECT {key} FROM protections WHERE user_id=?",
        (user_id,),
    ).fetchone()

    con.close()

    if not row:
        return 0

    return int(row[0])


def change_protection(
    user_id,
    key,
    delta,
):
    ensure_protection_row(user_id)

    con = db()

    row = con.execute(
        f"SELECT {key} FROM protections WHERE user_id=?",
        (user_id,),
    ).fetchone()

    current = int(row[0])

    new_value = current + delta

    if new_value < 0:
        con.close()
        return False

    con.execute(
        f"""
        UPDATE protections
        SET {key}=?
        WHERE user_id=?
        """,
        (
            new_value,
            user_id,
        ),
    )

    con.commit()
    con.close()

    return True


# =========================================================
# RASMLAR
# =========================================================

async def send_phase_image(
    context,
    chat_id,
    phase,
    caption,
):
    images = {
        "night": NIGHT_IMAGE_FILE_ID,
        "day": DAY_IMAGE_FILE_ID,
        "vote": VOTE_IMAGE_FILE_ID,
        "win": WIN_IMAGE_FILE_ID,
    }

    file_id = images.get(
        phase,
        "",
    )

    if file_id:
        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=file_id,
                caption=caption,
                parse_mode="HTML",
            )
            return

        except Exception:
            logger.exception(
                "Faza rasmi yuborilmadi"
            )

    await context.bot.send_message(
        chat_id=chat_id,
        text=caption,
        parse_mode="HTML",
    )


async def announce(
    context,
    chat_id,
    text,
):
    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="HTML",
    )


# =========================================================
# PROFIL
# =========================================================

def profile_text(row):
    return (
        "👤 <b>PROFIL</b>\n\n"
        f"🪪 Ism: <b>{row['name']}</b>\n"
        f"🆔 ID: <code>{row['user_id']}</code>\n\n"
        f"💎 Almaz: <b>{row['diamonds']}</b>\n"
        f"💰 Pul: <b>{row['money']}</b>\n"
        f"💵 Dollar: <b>${row['dollars']}</b>\n"
        f"⭐ Ball: <b>{row['points']}</b>\n\n"
        f"🎮 O‘yinlar: <b>{row['games']}</b>\n"
        f"🏆 G‘alabalar: <b>{row['wins']}</b>"
    )


def profile_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💎 Almaz sotib olish",
                    callback_data="shop_diamonds",
                )
            ],
            [
                InlineKeyboardButton(
                    "🎁 Almaz yuborish",
                    callback_data="gift_diamond",
                )
            ],
            [
                InlineKeyboardButton(
                    "🛡️ Himoya markazi",
                    callback_data="protection_menu",
                )
            ],
        ]
    )


# =========================================================
# ALMAZ DO'KONI
# =========================================================

def diamond_shop_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💎1 — 500 💰",
                    callback_data="buydia:1",
                )
            ],
            [
                InlineKeyboardButton(
                    "💎5 — 2 500 💰",
                    callback_data="buydia:5",
                )
            ],
            [
                InlineKeyboardButton(
                    "💎10 — 5 000 💰",
                    callback_data="buydia:10",
                )
            ],
            [
                InlineKeyboardButton(
                    "💎20 — 10 000 💰",
                    callback_data="buydia:20",
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Profil",
                    callback_data="back_profile",
                )
            ],
        ]
    )


# =========================================================
# HIMOYA MARKAZI
# =========================================================

def protection_keyboard():
    keys = list(PROTECTIONS.keys())

    rows = []

    for i in range(
        0,
        len(keys),
        2,
    ):
        row = []

        for key in keys[i:i + 2]:
            row.append(
                InlineKeyboardButton(
                    PROTECTIONS[key][0],
                    callback_data=f"prot:{key}",
                )
            )

        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(
                "⬅️ Profil",
                callback_data="back_profile",
            )
        ]
    )

    return InlineKeyboardMarkup(rows)


def protection_text(user_id):
    lines = [
        "🛡️ <b>HIMOYA MARKAZI</b>",
        "",
        "Har bir himoya sotib olingandan keyin "
        "inventarda saqlanadi.",
        "",
    ]

    for key, (
        name,
        price,
        desc,
    ) in PROTECTIONS.items():

        lines.append(
            f"{name} — <b>{price}</b> | "
            f"Mavjud: <b>{protection_count(user_id, key)}</b>"
        )

        lines.append(
            f"↳ {desc}"
        )

        lines.append("")

    return "\n".join(lines)


def protection_detail(
    user_id,
    key,
):
    name, price, desc = PROTECTIONS[key]

    count = protection_count(
        user_id,
        key,
    )

    return (
        f"{name}\n\n"
        f"💳 Narxi: <b>{price}</b>\n"
        f"📦 Sizda: <b>{count}</b>\n\n"
        f"ℹ️ {desc}"
    )


def protection_detail_keyboard(key):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🛒 Sotib olish",
                    callback_data=f"buyprot:{key}",
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Himoya markazi",
                    callback_data="protection_menu",
                )
            ],
        ]
    )


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user

    get_player(user)
    track_group_user(update)

    if banned(user.id):
        await update.effective_message.reply_text(
            "⛔ Siz botdan foydalanish huquqidan mahrumsiz."
        )
        return

    await update.effective_message.reply_text(
        "👑 <b>MAFIA BOT</b>\n\n"
        "🎭 Sirlar • Intriga • G‘alaba\n"
        "💎 Almaz • 💰 Pul • ⭐ Ball\n\n"
        "Profil va imkoniyatlarni pastdagi "
        "menyudan boshqaring.",
        parse_mode="HTML",
        reply_markup=profile_keyboard(),
    )


async def profile_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    row = get_player(
        update.effective_user
    )

    track_group_user(update)

    await update.effective_message.reply_text(
        profile_text(row),
        parse_mode="HTML",
        reply_markup=profile_keyboard(),
    )


# =========================================================
# MONEY
# =========================================================

async def money_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    if not update.message.reply_to_message:
        await update.effective_message.reply_text(
            "💰 Pul berish uchun boshqa "
            "o‘yinchining xabariga reply qilib:\n\n"
            "/money 5000"
        )
        return

    amount = (
        parse_int(context.args[0])
        if context.args
        else None
    )

    if amount is None or amount <= 0:
        await update.effective_message.reply_text(
            "❌ To‘g‘ri summa kiriting.\n"
            "Masalan: /money 5000"
        )
        return

    sender = get_player(
        update.effective_user
    )

    target_user = (
        update.message
        .reply_to_message
        .from_user
    )

    target = get_player(target_user)

    if sender["money"] < amount:
        await update.effective_message.reply_text(
            "❌ Pul yetarli emas."
        )
        return

    save_balances(
        sender["user_id"],
        money=sender["money"] - amount,
    )

    save_balances(
        target["user_id"],
        money=target["money"] + amount,
    )

    await update.effective_message.reply_text(
        "💸 <b>PUL O‘TKAZMASI</b>\n\n"
        f"{mention(sender['user_id'])} ➜ "
        f"{mention(target['user_id'])}\n"
        f"💰 <b>{amount:,}</b> pul yuborildi!",
        parse_mode="HTML",
    )


# =========================================================
# ALMAZ YUBORISH
# =========================================================

async def gift_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    target_id = None
    amount = None

    if update.message.reply_to_message:
        target_id = (
            update.message
            .reply_to_message
            .from_user
            .id
        )

        amount = (
            parse_int(context.args[0])
            if context.args
            else None
        )

    elif len(context.args) >= 2:
        target_id = parse_int(
            context.args[0]
        )

        amount = parse_int(
            context.args[1]
        )

    if (
        not target_id
        or not amount
        or amount <= 0
    ):
        await update.message.reply_text(
            "🎁 Reply qilib /give 1\n"
            "yoki\n"
            "/give TELEGRAM_ID 1"
        )
        return

    sender = get_player(
        update.effective_user
    )

    target = get_player_by_id(
        target_id
    )

    if not target:
        await update.message.reply_text(
            "❌ Bu o‘yinchi botni hali "
            "/start qilmagan."
        )
        return

    if target_id == sender["user_id"]:
        await update.message.reply_text(
            "❌ O‘zingizga yubora olmaysiz."
        )
        return

    if sender["diamonds"] < amount:
        await update.message.reply_text(
            "❌ Almaz yetarli emas."
        )
        return

    save_balances(
        sender["user_id"],
        diamonds=sender["diamonds"] - amount,
    )

    save_balances(
        target_id,
        diamonds=target["diamonds"] + amount,
    )

    if DIAMOND_ANIMATION_FILE_ID:
        try:
            await context.bot.send_animation(
                target_id,
                DIAMOND_ANIMATION_FILE_ID,
                caption=(
                    f"💎 Sizga {amount} ta "
                    "almaz yuborildi!"
                ),
            )
        except Exception:
            logger.exception(
                "Almaz animatsiyasi yuborilmadi"
            )

    await update.message.reply_text(
        "💎 <b>ALMAZ SOVG‘ASI</b>\n\n"
        f"{mention(sender['user_id'])} ➜ "
        f"{mention(target_id)}\n"
        f"🎁 <b>{amount}</b> ta almaz yuborildi!",
        parse_mode="HTML",
    )


# =========================================================
# EXCHANGE
# =========================================================

async def exchange_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "ℹ️ /exchange o‘chirildi.\n\n"
        "💎 Almazni Profil → "
        "💎 Almaz sotib olish orqali oling."
    )


# =========================================================
# CHANGE
# =========================================================

async def change_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_chat.type == "private":
        await update.effective_message.reply_text(
            "❌ /change faqat guruhda ishlaydi."
        )
        return

    if not context.args:
        await update.effective_message.reply_text(
            "🎁 Misol:\n"
            "/change 100\n\n"
            "Mukofot: 100 💎"
        )
        return

    prize = parse_int(
        context.args[0]
    )

    if prize is None or prize <= 0:
        await update.effective_message.reply_text(
            "❌ Mukofot son bo‘lishi kerak."
        )
        return

    creator = get_player(
        update.effective_user
    )

    if creator["diamonds"] < prize:
        await update.effective_message.reply_text(
            "❌ Sizda bu /change uchun "
            "yetarli 💎 yo‘q."
        )
        return

    chat_id = update.effective_chat.id

    con = db()

    old = con.execute(
        """
        SELECT *
        FROM changes
        WHERE chat_id=?
        AND active=1
        """,
        (chat_id,),
    ).fetchone()

    con.close()

    if old:
        await update.effective_message.reply_text(
            "❌ Bu guruhda allaqachon "
            "faol /change bor."
        )
        return

    save_balances(
        creator["user_id"],
        diamonds=creator["diamonds"] - prize,
    )

    con = db()

    con.execute(
        """
        INSERT OR REPLACE INTO changes(
            chat_id,
            creator_id,
            prize,
            message_id,
            active
        )
        VALUES(?,?,?,?,1)
        """,
        (
            chat_id,
            creator["user_id"],
            prize,
            0,
        ),
    )

    con.execute(
        """
        DELETE FROM change_participants
        WHERE chat_id=?
        """,
        (chat_id,),
    )

    con.commit()
    con.close()

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🎯 QATNASHISH",
                    callback_data="change_join",
                ),
                InlineKeyboardButton(
                    "🛑 YAKUNLASH",
                    callback_data="change_end",
                ),
            ]
        ]
    )

    msg = await update.effective_message.reply_text(
        "🎁 <b>CHANGE BOSHLANDI!</b>\n\n"
        f"💎 Mukofot: <b>{prize}</b>\n"
        f"👥 Maksimal: <b>{CHANGE_MAX}</b> ishtirokchi\n\n"
        "Qatnashish uchun tugmani bosing!",
        parse_mode="HTML",
        reply_markup=keyboard,
    )

    con = db()

    con.execute(
        """
        UPDATE changes
        SET message_id=?
        WHERE chat_id=?
        """,
        (
            msg.message_id,
            chat_id,
        ),
    )

    con.commit()
    con.close()


async def finish_change(
    context,
    chat_id,
):
    con = db()

    change = con.execute(
        """
        SELECT *
        FROM changes
        WHERE chat_id=?
        AND active=1
        """,
        (chat_id,),
    ).fetchone()

    participants = con.execute(
        """
        SELECT user_id
        FROM change_participants
        WHERE chat_id=?
        """,
        (chat_id,),
    ).fetchall()

    con.close()

    if not change:
        return False

    ids = [
        row[0]
        for row in participants
    ]

    if not ids:
        creator = get_player_by_id(
            change["creator_id"]
        )

        if creator:
            save_balances(
                creator["user_id"],
                diamonds=(
                    creator["diamonds"]
                    + change["prize"]
                ),
            )

        con = db()

        con.execute(
            """
            UPDATE changes
            SET active=0
            WHERE chat_id=?
            """,
            (chat_id,),
        )

        con.commit()
        con.close()

        await context.bot.send_message(
            chat_id,
            "🛑 <b>CHANGE YAKUNLANDI</b>\n\n"
            "Ishtirokchi bo‘lmagani uchun "
            "mukofot egasiga qaytarildi.",
            parse_mode="HTML",
        )

        return True

    winner = random.choice(ids)

    winner_row = get_player_by_id(
        winner
    )

    if winner_row:
        save_balances(
            winner,
            diamonds=(
                winner_row["diamonds"]
                + change["prize"]
            ),
        )

    con = db()

    con.execute(
        """
        UPDATE changes
        SET active=0
        WHERE chat_id=?
        """,
        (chat_id,),
    )

    con.commit()
    con.close()

    await context.bot.send_message(
        chat_id,
        "🏆 <b>CHANGE G‘OLIBI</b>\n\n"
        f"{mention(winner)}\n"
        f"💎 Mukofot: <b>{change['prize']}</b>",
        parse_mode="HTML",
    )

    return True


# =========================================================
# YANGI O'YIN
# =========================================================

async def newgame_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_chat.type == "private":
        await update.effective_message.reply_text(
            "❌ O‘yin guruhda boshlanadi."
        )
        return

    chat_id = update.effective_chat.id

    games[chat_id] = new_game(
        chat_id
    )

    await update.effective_message.reply_text(
        "🎭 <b>YANGI MAFIA O‘YINI</b>\n\n"
        f"👥 Ishtirokchilar: "
        f"{MIN_PLAYERS}–{MAX_PLAYERS}\n\n"
        "➕ Qo‘shilish: /join\n"
        "👥 Ro‘yxat: /players\n"
        "▶️ Boshlash: /startgame",
        parse_mode="HTML",
    )


async def join_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_chat.type == "private":
        await update.effective_message.reply_text(
            "❌ /join guruhda ishlaydi."
        )
        return

    track_group_user(update)

    user = update.effective_user

    get_player(user)

    game = game_for(
        update.effective_chat.id
    )

    if game["started"]:
        await update.effective_message.reply_text(
            "❌ O‘yin allaqachon boshlangan."
        )
        return

    if user.id in game["players"]:
        await update.effective_message.reply_text(
            "✅ Siz allaqachon o‘yindasiz."
        )
        return

    if len(game["players"]) >= MAX_PLAYERS:
        await update.effective_message.reply_text(
            "❌ O‘yinchilar soni limitga yetdi."
        )
        return

    game["players"][user.id] = {
        "user_id": user.id,
        "name": user.full_name[:40],
        "role": None,
        "emoji": "👤",
        "alive": True,
    }

    await update.effective_message.reply_text(
        f"✅ {user.full_name} o‘yinga qo‘shildi!\n"
        f"👥 {len(game['players'])}/{MAX_PLAYERS}"
    )


async def players_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    game = game_for(
        update.effective_chat.id
    )

    lines = []

    for i, p in enumerate(
        game["players"].values(),
        1,
    ):
        status = (
            "🟢"
            if p["alive"]
            else "💀"
        )

        lines.append(
            f"{i}. {status} {p['name']}"
        )

    text = (
        "👥 <b>O‘YINCHILAR</b>\n\n"
        + (
            "\n".join(lines)
            if lines
            else "Hozircha o‘yinchi yo‘q."
        )
    )

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
    )


# =========================================================
# ROL TAQSIMLASH
# =========================================================

def build_roles(player_count):
    """
    O'yin kichik bo'lsa ham rollar balansliroq
    bo'lishi uchun asosiy rollar beriladi.
    """

    if player_count == 4:
        base = [
            ("Mafia", "🔪"),
            ("Don", "👑"),
            ("Komissar", "🔍"),
            ("Fuqaro", "👤"),
        ]

    elif player_count == 5:
        base = [
            ("Mafia", "🔪"),
            ("Don", "👑"),
            ("Komissar", "🔍"),
            ("Doktor", "💉"),
            ("Fuqaro", "👤"),
        ]

    elif player_count == 6:
        base = [
            ("Mafia", "🔪"),
            ("Don", "👑"),
            ("Komissar", "🔍"),
            ("Doktor", "💉"),
            ("Manyak", "☠️"),
            ("Fuqaro", "👤"),
        ]

    else:
        base = [
            ("Mafia", "🔪"),
            ("Mafia", "🔪"),
            ("Don", "👑"),
            ("Komissar", "🔍"),
            ("Doktor", "💉"),
            ("Bodyguard", "🛡️"),
            ("Manyak", "☠️"),
            ("Snayper", "🎯"),
            ("Sherif", "⭐"),
            ("Advokat", "⚖️"),
            ("Detektiv", "🕵️"),
            ("Jurnalist", "📰"),
            ("Haker", "💻"),
            ("Psixolog", "🧠"),
            ("Sevishgan", "❤️"),
            ("O'g'ri", "🥷"),
            ("Qasoskor", "⚔️"),
        ]

    while len(base) < player_count:
        base.append(
            ("Fuqaro", "👤")
        )

    random.shuffle(base)

    return base[:player_count]


# =========================================================
# O'YINNI BOSHLASH
# =========================================================

async def startgame_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    chat_id = update.effective_chat.id

    game = game_for(chat_id)

    if game["started"]:
        await update.effective_message.reply_text(
            "❌ O‘yin allaqachon boshlangan."
        )
        return

    player_count = len(
        game["players"]
    )

    if player_count < MIN_PLAYERS:
        await update.effective_message.reply_text(
            f"❌ Kamida {MIN_PLAYERS} "
            "o‘yinchi kerak."
        )
        return

    game["started"] = True
    game["phase"] = "night"
    game["night"] = 1

    role_pool = build_roles(
        player_count
    )

    players = list(
        game["players"].values()
    )

    for i, player in enumerate(players):
        role, emoji = role_pool[i]

        player["role"] = role
        player["emoji"] = emoji

        add_stats(
            player["user_id"],
            games_count=1,
        )

        try:
            await context.bot.send_message(
                player["user_id"],
                "🎭 <b>SIZNING ROLINGIZ</b>\n\n"
                f"{emoji} <b>{role}</b>\n\n"
                "Rasmingizni va rolingizni "
                "boshqalarga oshkor qilmang.",
                parse_mode="HTML",
            )
        except Exception:
            pass

    await send_phase_image(
        context,
        chat_id,
        "night",
        "🌙 <b>TUN BOSHLANDI</b>\n\n"
        "Shahar jim... Sirlar uyg‘onmoqda.\n"
        "Tungi vazifalar boshlandi.",
    )

    await announce(
        context,
        chat_id,
        "🎭 <b>O‘YIN BOSHLANDI!</b>\n\n"
        "Rollar shaxsiy xabarda yuborildi.\n\n"
        "Tungi vazifalar boshlandi.",
    )


async def role_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    game = game_for(
        update.effective_chat.id
    )

    uid = update.effective_user.id

    if (
        not game["started"]
        or uid not in game["players"]
    ):
        await update.effective_message.reply_text(
            "❌ Siz faol o‘yinda emassiz."
        )
        return

    player = game["players"][uid]

    await update.effective_message.reply_text(
        "🎭 Sizning rolingiz:\n\n"
        f"{player['emoji']} "
        f"<b>{player['role']}</b>",
        parse_mode="HTML",
    )


# =========================================================
# FAZALAR
# =========================================================

async def night_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    game = game_for(
        update.effective_chat.id
    )

    if not game["started"]:
        await update.effective_message.reply_text(
            "❌ O‘yin boshlanmagan."
        )
        return

    game["phase"] = "night"

    await send_phase_image(
        context,
        update.effective_chat.id,
        "night",
        "🌙 <b>TUN</b>\n\n"
        "Tungi harakatlar boshlandi.",
    )


async def day_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    game = game_for(
        update.effective_chat.id
    )

    if not game["started"]:
        await update.effective_message.reply_text(
            "❌ O‘yin boshlanmagan."
        )
        return

    game["phase"] = "day"

    await send_phase_image(
        context,
        update.effective_chat.id,
        "day",
        "☀️ <b>KUN BOSHLANDI</b>\n\n"
        "Tungi voqealarni muhokama qiling.",
    )


# =========================================================
# O'YINCHI RAQAMINI TOPISH
# =========================================================

def find_player_by_number(
    game,
    value,
):
    number = parse_int(value)

    if number is None:
        return None

    players = list(
        game["players"].values()
    )

    if (
        number < 1
        or number > len(players)
    ):
        return None

    return players[
        number - 1
    ]["user_id"]


# =========================================================
# ACTION
# =========================================================

def action_allowed(
    game,
    user_id,
):
    return (
        game["started"]
        and game["phase"] == "night"
        and user_id in game["players"]
        and game["players"][user_id]["alive"]
    )


def record_action(
    game,
    user_id,
    action,
    target_id=None,
):
    game["actions"][user_id] = {
        "action": action,
        "target": target_id,
    }


async def target_action(
    update,
    context,
    allowed_roles,
    action_name,
    usage_text,
):
    game = game_for(
        update.effective_chat.id
    )

    uid = update.effective_user.id

    if not action_allowed(
        game,
        uid,
    ):
        await update.effective_message.reply_text(
            "❌ Bu harakat hozir mumkin emas."
        )
        return

    if role_of(
        game,
        uid,
    ) not in allowed_roles:
        await update.effective_message.reply_text(
            "❌ Sizning rolingizda "
            "bu harakat yo‘q."
        )
        return

    if not context.args:
        await update.effective_message.reply_text(
            usage_text
        )
        return

    target = find_player_by_number(
        game,
        context.args[0],
    )

    if (
        target is None
        or not game["players"][target]["alive"]
    ):
        await update.effective_message.reply_text(
            "❌ Noto‘g‘ri o‘yinchi raqami."
        )
        return

    record_action(
        game,
        uid,
        action_name,
        target,
    )

    await update.effective_message.reply_text(
        "✅ Harakat qabul qilindi:\n"
        f"{game['players'][target]['name']}"
    )


# =========================================================
# QOTIL / MAFIA
# =========================================================

async def kill_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    allowed = {
        "Mafia",
        "Don",
        "Godfather",
        "Manyak",
    }

    await target_action(
        update,
        context,
        allowed,
        "kill",
        "🔪 /kill O‘YINCHI_RAqAMI",
    )


# =========================================================
# DOKTOR
# =========================================================

async def heal_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await target_action(
        update,
        context,
        {"Doktor"},
        "heal",
        "💉 /heal O‘YINCHI_RAqAMI",
    )


# =========================================================
# TEKSHIRUV
# =========================================================

async def check_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await target_action(
        update,
        context,
        {
            "Komissar",
            "Sherif",
            "Detektiv",
            "Jurnalist",
            "Haker",
        },
        "check",
        "🔍 /check O‘YINCHI_RAqAMI",
    )


# =========================================================
# BODYGUARD
# =========================================================

async def guard_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await target_action(
        update,
        context,
        {"Bodyguard"},
        "guard",
        "🛡️ /guard O‘YINCHI_RAqAMI",
    )


# =========================================================
# SNAYPER
# =========================================================

async def shoot_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await target_action(
        update,
        context,
        {"Snayper"},
        "shoot",
        "🎯 /shoot O‘YINCHI_RAqAMI",
    )


# =========================================================
# OVOZ BLOKLASH
# =========================================================

async def silence_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    game = game_for(
        update.effective_chat.id
    )

    uid = update.effective_user.id

    if not action_allowed(
        game,
        uid,
    ):
        await update.effective_message.reply_text(
            "❌ Bu harakat hozir mumkin emas."
        )
        return

    role = role_of(
        game,
        uid,
    )

    has_role_power = role in {
        "Psixolog",
        "Mafia",
        "Don",
        "Godfather",
    }

    has_item = (
        protection_count(
            uid,
            "silence",
        ) > 0
    )

    if not has_role_power and not has_item:
        await update.effective_message.reply_text(
            "❌ Sizda ovoz bloklash "
            "imkoniyati yo‘q."
        )
        return

    if not context.args:
        await update.effective_message.reply_text(
            "🔇 /silence O‘YINCHI_RAqAMI"
        )
        return

    target = find_player_by_number(
        game,
        context.args[0],
    )

    if (
        target is None
        or not game["players"][target]["alive"]
    ):
        await update.effective_message.reply_text(
            "❌ Noto‘g‘ri o‘yinchi."
        )
        return

    if not has_role_power:
        change_protection(
            uid,
            "silence",
            -1,
        )

    game["silenced"].add(
        target
    )

    record_action(
        game,
        uid,
        "silence",
        target,
    )

    await update.effective_message.reply_text(
        f"🔇 {game['players'][target]['name']} "
        "ovoz berishdan bloklandi."
    )


# =========================================================
# BOSHQA O'YINCHINI HIMOYALASH
# =========================================================

async def protect_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    game = game_for(
        update.effective_chat.id
    )

    uid = update.effective_user.id

    if not action_allowed(
        game,
        uid,
    ):
        await update.effective_message.reply_text(
            "❌ Bu harakat hozir mumkin emas."
        )
        return

    if protection_count(
        uid,
        "protect_other",
    ) <= 0:
        await update.effective_message.reply_text(
            "❌ Sizda 🤝 himoyalash "
            "vositasi yo‘q."
        )
        return

    if not context.args:
        await update.effective_message.reply_text(
            "🤝 /protect O‘YINCHI_RAqAMI"
        )
        return

    target = find_player_by_number(
        game,
        context.args[0],
    )

    if (
        target is None
        or not game["players"][target]["alive"]
    ):
        await update.effective_message.reply_text(
            "❌ Noto‘g‘ri o‘yinchi."
        )
        return

    change_protection(
        uid,
        "protect_other",
        -1,
    )

    game["protected"].add(
        target
    )

    record_action(
        game,
        uid,
        "protect_other",
        target,
    )

    await update.effective_message.reply_text(
        f"🤝 {game['players'][target]['name']} "
        "himoyaga olindi."
    )


# =========================================================
# SHIELD
# =========================================================

async def shield_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    game = game_for(
        update.effective_chat.id
    )

    uid = update.effective_user.id

    if not action_allowed(
        game,
        uid,
    ):
        await update.effective_message.reply_text(
            "❌ Himoyani faqat tunda "
            "ishlatish mumkin."
        )
        return

    keys = [
        key
        for key in (
            "universal",
            "killer",
            "poison",
            "vote",
            "fake_doc",
        )
        if protection_count(
            uid,
            key,
        ) > 0
    ]

    if not keys:
        await update.effective_message.reply_text(
            "❌ Sizda ishlatishga "
            "tayyor himoya yo‘q."
        )
        return

    if not context.args:
        await update.effective_message.reply_text(
            "🛡️ Mavjud himoyalar:\n"
            + "\n".join(keys)
            + "\n\nMasalan:\n"
            "/shield universal"
        )
        return

    key = context.args[0].lower()

    if key not in keys:
        await update.effective_message.reply_text(
            "❌ Himoya topilmadi."
        )
        return

    change_protection(
        uid,
        key,
        -1,
    )

    if key == "universal":
        game["protected"].add(uid)

    elif key == "killer":
        game["killer_protected"].add(uid)

    elif key == "poison":
        game["poison_protected"].add(uid)

    elif key == "vote":
        game["vote_protected"].add(uid)

    elif key == "fake_doc":
        game["fake_doc"].add(uid)

    await update.effective_message.reply_text(
        f"✅ {PROTECTIONS[key][0]} "
        "ishlatildi."
    )


# =========================================================
# TUNNI YAKUNLASH
# =========================================================

async def endnight_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_chat.type == "private":
        return

    await resolve_night(
        context,
        update.effective_chat.id,
    )


async def resolve_night(
    context,
    chat_id,
):
    game = game_for(chat_id)

    if (
        not game["started"]
        or game["phase"] != "night"
    ):
        await context.bot.send_message(
            chat_id,
            "❌ Hozir tun emas.",
        )
        return

    actions = list(
        game["actions"].items()
    )

    healed = set(
    )

    guards = set(
        game["protected"]
    )

    killer_protected = set(
        game["killer_protected"]
    )

    dead = set()

    # Doctor / Bodyguard
    for uid, action in actions:
        if (
            action["action"] == "heal"
            and action["target"]
        ):
            healed.add(
                action["target"]
            )

        elif (
            action["action"] == "guard"
            and action["target"]
        ):
            guards.add(
                action["target"]
            )

    # Hujumlar
    for source_uid, action in actions:
        if action["action"] not in {
            "kill",
            "shoot",
        }:
            continue

        target = action["target"]

        if target is None:
            continue

        if target not in alive_players(game):
            continue

        source_role = role_of(
            game,
            source_uid,
        )

        # Doctor / Bodyguard
        if target in healed:
            continue

        if target in guards:
            continue

        # Qotilga qarshi himoya
        if (
            source_role == "Manyak"
            and target in killer_protected
        ):
            continue

        # Universal himoya:
        # Mafia / Godfather / Manyak hujumidan
        # himoya qiladi.
        #
        # Don hujumi universalni chetlab o'tadi.
        if (
            target in game["protected"]
            and source_role in {
                "Mafia",
                "Godfather",
                "Manyak",
            }
        ):
            continue

        dead.add(target)

    # O'lganlarni belgilash
    for uid in dead:
        game["players"][uid]["alive"] = False

    # Tekshiruvlar
    for source_uid, action in actions:
        if (
            action["action"] != "check"
            or not action["target"]
        ):
            continue

        target = action["target"]

        actual_role = role_of(
            game,
            target,
        )

        if target in game["fake_doc"]:
            shown_role = "Fuqaro"
            game["fake_doc"].discard(
                target
            )
        else:
            shown_role = actual_role

        try:
            await context.bot.send_message(
                source_uid,
                "🔍 <b>TEKSHIRUV NATIJASI</b>\n\n"
                f"{mention(target)} → "
                f"<b>{shown_role}</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass

    if dead:
        names = ", ".join(
            game["players"][uid]["name"]
            for uid in dead
        )

        await announce(
            context,
            chat_id,
            "💀 <b>TUN NATIJASI</b>\n\n"
            f"Halok bo‘lganlar:\n<b>{names}</b>",
        )

    else:
        await announce(
            context,
            chat_id,
            "🌅 <b>TUN NATIJASI</b>\n\n"
            "Bu kecha hech kim halok bo‘lmadi.",
        )

    game["actions"] = {}
    game["protected"] = set()
    game["killer_protected"] = set()
    game["poison_protected"] = set()
    game["silenced"] = set()
    game["phase"] = "day"
    game["night"] += 1

    if await check_winner(
        context,
        chat_id,
    ):
        return

    await send_phase_image(
        context,
        chat_id,
        "day",
        "☀️ <b>KUN BOSHLANDI</b>\n\n"
        "Tungi voqealar muhokama qilinadi.",
    )


# =========================================================
# OVOZ BERISH
# =========================================================

async def startvote_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    game = game_for(
        update.effective_chat.id
    )

    if not game["started"]:
        await update.effective_message.reply_text(
            "❌ O‘yin boshlanmagan."
        )
        return

    game["phase"] = "vote"
    game["votes"] = {}

    await send_phase_image(
        context,
        update.effective_chat.id,
        "vote",
        "🗳️ <b>OVOZ BERISH BOSHLANDI</b>\n\n"
        "Kim qoladi? Kim ketadi?\n\n"
        "Ovoz berish:\n"
        "/vote O‘YINCHI_RAqAMI\n\n"
        "Tugatish:\n"
        "/endvote",
    )


async def vote_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    game = game_for(
        update.effective_chat.id
    )

    uid = update.effective_user.id

    if (
        not game["started"]
        or game["phase"] != "vote"
    ):
        await update.effective_message.reply_text(
            "❌ Hozir ovoz berish vaqti emas."
        )
        return

    if (
        uid not in game["players"]
        or not game["players"][uid]["alive"]
    ):
        await update.effective_message.reply_text(
            "❌ Siz faol o‘yinda emassiz."
        )
        return

    if uid in game["silenced"]:
        await update.effective_message.reply_text(
            "🔇 Sizning ovozingiz bloklangan."
        )
        return

    if not context.args:
        await update.effective_message.reply_text(
            "🗳️ /vote O‘YINCHI_RAqAMI"
        )
        return

    target = find_player_by_number(
        game,
        context.args[0],
    )

    if (
        target is None
        or target == uid
        or not game["players"][target]["alive"]
    ):
        await update.effective_message.reply_text(
            "❌ Noto‘g‘ri nishon."
        )
        return

    game["votes"][uid] = target

    await update.effective_message.reply_text(
        f"🗳️ Ovoz qabul qilindi:\n"
        f"{game['players'][target]['name']}"
    )


async def endvote_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    chat_id = update.effective_chat.id

    game = game_for(chat_id)

    if (
        not game["started"]
        or game["phase"] != "vote"
    ):
        await update.effective_message.reply_text(
            "❌ Hozir ovoz berish bosqichi emas."
        )
        return

    votes = game["votes"]

    if not votes:
        await update.effective_message.reply_text(
            "❌ Hali hech kim ovoz bermadi."
        )
        return

    counts = {}

    for target in votes.values():
        counts[target] = (
            counts.get(target, 0) + 1
        )

    max_votes = max(
        counts.values()
    )

    candidates = [
        uid
        for uid, count in counts.items()
        if count == max_votes
    ]

    target = random.choice(
        candidates
    )

    if target in game["vote_protected"]:
        game["vote_protected"].discard(
            target
        )

        await announce(
            context,
            chat_id,
            "🛡️ <b>OVOZ HIMOYASI ISHLADI!</b>\n\n"
            f"{mention(target)} "
            "ovoz orqali chiqarilmadi.",
        )

    else:
        game["players"][target]["alive"] = False

        await announce(
            context,
            chat_id,
            "🗳️ <b>OVOZ NATIJASI</b>\n\n"
            f"{mention(target)} chiqarildi.\n"
            f"🔢 Ovozlar: <b>{max_votes}</b>",
        )

    game["votes"] = {}

    if await check_winner(
        context,
        chat_id,
    ):
        return

    game["phase"] = "night"
    game["night"] += 1

    await send_phase_image(
        context,
        chat_id,
        "night",
        "🌙 <b>TUN BOSHLANDI</b>\n\n"
        "Tungi vazifalar boshlandi.",
    )


# =========================================================
# G'ALABA TEKSHIRISH
# =========================================================

async def check_winner(
    context,
    chat_id,
):
    game = game_for(chat_id)

    if not game["started"]:
        return False

    alive = alive_players(
        game
    )

    if not alive:
        await finish_game(
            context,
            chat_id,
            "Hech kim",
        )
        return True

    mafia = sum(
        1
        for player in alive.values()
        if player["role"] in {
            "Mafia",
            "Don",
            "Godfather",
        }
    )

    maniac = sum(
        1
        for player in alive.values()
        if player["role"] == "Manyak"
    )

    others = (
        len(alive)
        - mafia
        - maniac
    )

    winner = None

    if (
        maniac > 0
        and len(alive) == 1
    ):
        winner = "Manyak"

    elif (
        mafia >= others + maniac
        and mafia > 0
    ):
        winner = "Mafia"

    elif (
        mafia == 0
        and maniac == 0
    ):
        winner = "Fuqarolar"

    if winner:
        await finish_game(
            context,
            chat_id,
            winner,
        )

        return True

    return False


async def finish_game(
    context,
    chat_id,
    winner_side,
):
    game = game_for(chat_id)

    if not game["started"]:
        return

    winners = []

    for uid, player in game["players"].items():

        role = player["role"]

        won = False

        if (
            winner_side == "Mafia"
            and role in {
                "Mafia",
                "Don",
                "Godfather",
            }
        ):
            won = True

        elif (
            winner_side == "Manyak"
            and role == "Manyak"
        ):
            won = True

        elif (
            winner_side == "Fuqarolar"
            and role not in {
                "Mafia",
                "Don",
                "Godfather",
                "Manyak",
            }
        ):
            won = True

        if won:
            winners.append(uid)

            row = get_player_by_id(
                uid
            )

            if row:
                save_balances(
                    uid,
                    dollars=row["dollars"] + 20,
                )

            points = ROLE_POINTS.get(
                role,
                50,
            )

            add_points(
                uid,
                points,
                f"G‘alaba: {role}",
            )

            add_stats(
                uid,
                wins=1,
            )

    game["started"] = False
    game["phase"] = "finished"

    winner_lines = []

    for uid in winners:
        role = game["players"][uid]["role"]
        points = ROLE_POINTS.get(
            role,
            50,
        )

        winner_lines.append(
            f"🏆 {game['players'][uid]['name']}"
            f" — +$20, +{points} ball"
        )

    if winner_lines:
        result = "\n".join(
            winner_lines
        )
    else:
        result = "G‘olib topilmadi."

    await send_phase_image(
        context,
        chat_id,
        "win",
        "🏆 <b>G‘ALABA!</b>\n\n"
        f"👑 G‘olib tomon: "
        f"<b>{winner_side}</b>\n\n"
        f"{result}",
    )


# =========================================================
# TOP
# =========================================================

def top_rows(start_dt):
    con = db()

    rows = con.execute(
        """
        SELECT
            p.user_id,
            p.name,
            COALESCE(
                SUM(e.points),
                0
            ) AS pts
        FROM point_events e
        JOIN players p
            ON p.user_id=e.user_id
        WHERE e.created_at>=?
        GROUP BY p.user_id
        ORDER BY pts DESC
        LIMIT 10
        """,
        (
            start_dt.isoformat(
                timespec="seconds"
            ),
        ),
    ).fetchall()

    con.close()

    return rows


async def send_top(
    update,
    rows,
    title,
):
    if not rows:
        await update.effective_message.reply_text(
            f"{title}\n\n"
            "Hozircha natijalar yo‘q."
        )
        return

    lines = [
        title,
        "",
    ]

    for i, row in enumerate(
        rows,
        1,
    ):
        lines.append(
            f"{i}. {row['name']} — "
            f"⭐ {row['pts']}"
        )

    await update.effective_message.reply_text(
        "\n".join(lines)
    )


async def top_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    now = datetime.utcnow()

    start = datetime(
        now.year,
        now.month,
        1,
    )

    await send_top(
        update,
        top_rows(start),
        "🏆 OYLIK TOP",
    )


async def top1_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    now = datetime.utcnow()

    start = datetime(
        now.year,
        now.month,
        now.day,
    )

    await send_top(
        update,
        top_rows(start),
        "🏆 BUGUNGI TOP",
    )


async def top7_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    start = (
        datetime.utcnow()
        - timedelta(days=7)
    )

    await send_top(
        update,
        top_rows(start),
        "🏆 7 KUNLIK TOP",
    )


# =========================================================
# ADMIN: ADD ADMIN
# =========================================================

async def addadmin_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_owner(
        update.effective_user.id
    ):
        await update.effective_message.reply_text(
            "⛔ Faqat owner."
        )
        return

    target_id = (
        parse_int(context.args[0])
        if context.args
        else None
    )

    if (
        target_id is None
        and update.message.reply_to_message
    ):
        target_id = (
            update.message
            .reply_to_message
            .from_user
            .id
        )

    if not target_id:
        await update.effective_message.reply_text(
            "/addadmin TELEGRAM_ID\n"
            "yoki reply qiling."
        )
        return

    con = db()

    con.execute(
        """
        INSERT OR IGNORE INTO admins(user_id)
        VALUES(?)
        """,
        (target_id,),
    )

    con.commit()
    con.close()

    admins.add(target_id)

    await update.effective_message.reply_text(
        "✅ Admin qo‘shildi:\n"
        f"<code>{target_id}</code>",
        parse_mode="HTML",
    )


# =========================================================
# ADMIN: DELETE ADMIN
# =========================================================

async def deladmin_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_owner(
        update.effective_user.id
    ):
        await update.effective_message.reply_text(
            "⛔ Faqat owner."
        )
        return

    target_id = (
        parse_int(context.args[0])
        if context.args
        else None
    )

    if (
        not target_id
        and update.message.reply_to_message
    ):
        target_id = (
            update.message
            .reply_to_message
            .from_user
            .id
        )

    if not target_id:
        await update.effective_message.reply_text(
            "/deladmin TELEGRAM_ID"
        )
        return

    con = db()

    con.execute(
        "DELETE FROM admins WHERE user_id=?",
        (target_id,),
    )

    con.commit()
    con.close()

    admins.discard(
        target_id
    )

    await update.effective_message.reply_text(
        "✅ Admin olib tashlandi."
    )


# =========================================================
# ADMIN: BAN
# =========================================================

async def ban_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_admin(
        update.effective_user.id
    ):
        await update.effective_message.reply_text(
            "⛔ Admin huquqi kerak."
        )
        return

    target_id = (
        parse_int(context.args[0])
        if context.args
        else None
    )

    if (
        not target_id
        and update.message.reply_to_message
    ):
        target_id = (
            update.message
            .reply_to_message
            .from_user
            .id
        )

    if not target_id:
        await update.effective_message.reply_text(
            "/ban TELEGRAM_ID"
        )
        return

    con = db()

    con.execute(
        """
        UPDATE players
        SET banned=1
        WHERE user_id=?
        """,
        (target_id,),
    )

    con.commit()
    con.close()

    await update.effective_message.reply_text(
        "⛔ Foydalanuvchi bloklandi."
    )


# =========================================================
# ADMIN: UNBAN
# =========================================================

async def unban_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_admin(
        update.effective_user.id
    ):
        await update.effective_message.reply_text(
            "⛔ Admin huquqi kerak."
        )
        return

    target_id = (
        parse_int(context.args[0])
        if context.args
        else None
    )

    if (
        not target_id
        and update.message.reply_to_message
    ):
        target_id = (
            update.message
            .reply_to_message
            .from_user
            .id
        )

    if not target_id:
        await update.effective_message.reply_text(
            "/unban TELEGRAM_ID"
        )
        return

    con = db()

    con.execute(
        """
        UPDATE players
        SET banned=0
        WHERE user_id=?
        """,
        (target_id,),
    )

    con.commit()
    con.close()

    await update.effective_message.reply_text(
        "✅ Foydalanuvchi blokdan chiqarildi."
    )


# =========================================================
# ADMIN: BANKROT
# =========================================================

async def bankrot_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_admin(
        update.effective_user.id
    ):
        await update.effective_message.reply_text(
            "⛔ Admin huquqi kerak."
        )
        return

    target_id = (
        parse_int(context.args[0])
        if context.args
        else None
    )

    if (
        not target_id
        and update.message.reply_to_message
    ):
        target_id = (
            update.message
            .reply_to_message
            .from_user
            .id
        )

    if not target_id:
        await update.effective_message.reply_text(
            "/bankrot TELEGRAM_ID"
        )
        return

    con = db()

    con.execute(
        """
        UPDATE players
        SET money=0,
            dollars=0,
            diamonds=0
        WHERE user_id=?
        """,
        (target_id,),
    )

    con.commit()
    con.close()

    await update.effective_message.reply_text(
        "💸 O‘yinchining barcha "
        "balanslari 0 qilindi."
    )


# =========================================================
# ADMIN: BALANS
# =========================================================

async def give_admin_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_admin(
        update.effective_user.id
    ):
        await update.effective_message.reply_text(
            "⛔ Admin huquqi kerak."
        )
        return

    if len(context.args) < 3:
        await update.effective_message.reply_text(
            "/giveadmin TELEGRAM_ID "
            "money|diamonds|dollars SUMMA"
        )
        return

    target_id = parse_int(
        context.args[0]
    )

    kind = (
        context.args[1]
        .lower()
    )

    amount = parse_int(
        context.args[2]
    )

    if (
        not target_id
        or amount is None
        or amount < 0
        or kind not in {
            "money",
            "diamonds",
            "dollars",
        }
    ):
        await update.effective_message.reply_text(
            "❌ Format xato."
        )
        return

    row = get_player_by_id(
        target_id
    )

    if not row:
        await update.effective_message.reply_text(
            "❌ O‘yinchi bazada topilmadi."
        )
        return

    save_balances(
        target_id,
        **{
            kind: amount
        },
    )

    await update.effective_message.reply_text(
        "✅ Balans o‘rnatildi."
    )


# =========================================================
# ADMIN: ROLLARNI KO'RISH
# =========================================================

async def who_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_admin(
        update.effective_user.id
    ):
        await update.effective_message.reply_text(
            "⛔ Admin huquqi kerak."
        )
        return

    game = game_for(
        update.effective_chat.id
    )

    if not game["players"]:
        await update.effective_message.reply_text(
            "O‘yinchilar yo‘q."
        )
        return

    lines = []

    for i, player in enumerate(
        game["players"].values(),
        1,
    ):
        lines.append(
            f"{i}. {player['name']} — "
            f"{player['emoji']} "
            f"{player['role']}"
        )

    await update.effective_message.reply_text(
        "🔐 <b>MAXFIY ROLLAR</b>\n\n"
        + "\n".join(lines),
        parse_mode="HTML",
    )


# =========================================================
# CALLBACKLAR
# =========================================================

async def callbacks(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    await query.answer()

    uid = query.from_user.id

    get_player(
        query.from_user
    )

    data = query.data or ""

    # PROFIL
    if data == "back_profile":
        row = get_player_by_id(
            uid
        )

        await query.edit_message_text(
            profile_text(row),
            parse_mode="HTML",
            reply_markup=profile_keyboard(),
        )

        return

    # ALMAZ SHOP
    if data == "shop_diamonds":
        row = get_player_by_id(
            uid
        )

        await query.edit_message_text(
            "💎 <b>ALMAZ DO‘KONI</b>\n\n"
            "1 💎 = 500 💰\n\n"
            f"Sizning pulingiz: "
            f"<b>{row['money']:,}</b> 💰",
            parse_mode="HTML",
            reply_markup=diamond_shop_keyboard(),
        )

        return

    # ALMAZ SOTIB OLISH
    if data.startswith("buydia:"):
        amount = parse_int(
            data.split(":", 1)[1]
        )

        prices = {
            1: 500,
            5: 2500,
            10: 5000,
            20: 10000,
        }

        if amount not in prices:
            return

        row = get_player_by_id(
            uid
        )

        price = prices[amount]

        if row["money"] < price:
            await query.answer(
                "Pul yetarli emas.",
                show_alert=True,
            )
            return

        save_balances(
            uid,
            money=row["money"] - price,
            diamonds=row["diamonds"] + amount,
        )

        row = get_player_by_id(
            uid
        )

        await query.edit_message_text(
            "✅ <b>XARID MUVAFFAQIYATLI</b>\n\n"
            f"💎 +{amount}\n"
            f"💰 -{price:,}\n\n"
            f"Yangi balans:\n"
            f"💎 {row['diamonds']}\n"
            f"💰 {row['money']:,}",
            parse_mode="HTML",
            reply_markup=diamond_shop_keyboard(),
        )

        return

    # ALMAZ YUBORISH
    if data == "gift_diamond":
        pending_inputs[uid] = {
            "type": "gift_target"
        }

        await query.edit_message_text(
            "🎁 Almaz yuboriladigan "
            "<b>Telegram ID</b>ni yuboring.",
            parse_mode="HTML",
        )

        return

    # HIMOYA MARKAZI
    if data == "protection_menu":
        await query.edit_message_text(
            protection_text(uid),
            parse_mode="HTML",
            reply_markup=protection_keyboard(),
        )

        return

    # HIMOYA DETALI
    if data.startswith("prot:"):
        key = data.split(
            ":",
            1,
        )[1]

        if key not in PROTECTIONS:
            return

        await query.edit_message_text(
            protection_detail(
                uid,
                key,
            ),
            parse_mode="HTML",
            reply_markup=protection_detail_keyboard(
                key
            ),
        )

        return

    # HIMOYA SOTIB OLISH
    if data.startswith("buyprot:"):
        key = data.split(
            ":",
            1,
        )[1]

        if key not in PROTECTIONS:
            return

        price_text = PROTECTIONS[key][1]

        row = get_player_by_id(
            uid
        )

        if "💎" in price_text:
            currency = "diamonds"
        else:
            currency = "money"

        amount = parse_int(
            price_text
            .replace("💎", "")
            .replace("$", "")
            .strip()
        )

        if amount is None:
            return

        if row[currency] < amount:
            await query.answer(
                "Balans yetarli emas.",
                show_alert=True,
            )
            return

        save_balances(
            uid,
            **{
                currency:
                    row[currency] - amount
            },
        )

        change_protection(
            uid,
            key,
            1,
        )

        await query.edit_message_text(
            "✅ <b>SOTIB OLINDI</b>\n\n"
            + protection_detail(
                uid,
                key,
            ),
            parse_mode="HTML",
            reply_markup=protection_detail_keyboard(
                key
            ),
        )

        return

    # CHANGE QATNASHISH
    if data == "change_join":
        chat_id = query.message.chat.id

        if chat_id in change_locks:
            return

        change_locks.add(chat_id)

        try:
            con = db()

            change = con.execute(
                """
                SELECT *
                FROM changes
                WHERE chat_id=?
                AND active=1
                """,
                (chat_id,),
            ).fetchone()

            if not change:
                con.close()

                await query.answer(
                    "Faol change yo‘q.",
                    show_alert=True,
                )

                return

            exists = con.execute(
                """
                SELECT 1
                FROM change_participants
                WHERE chat_id=?
                AND user_id=?
                """,
                (
                    chat_id,
                    uid,
                ),
            ).fetchone()

            count = con.execute(
                """
                SELECT COUNT(*)
                FROM change_participants
                WHERE chat_id=?
                """,
                (chat_id,),
            ).fetchone()[0]

            if exists:
                con.close()

                await query.answer(
                    "Siz allaqachon qatnashgansiz.",
                    show_alert=True,
                )

                return

            if count >= CHANGE_MAX:
                con.close()

                await query.answer(
                    "Limit to‘lgan.",
                    show_alert=True,
                )

                return

            get_player(
                query.from_user
            )

            con.execute(
                """
                INSERT INTO change_participants(
                    chat_id,
                    user_id
                )
                VALUES(?,?)
                """,
                (
                    chat_id,
                    uid,
                ),
            )

            con.commit()
            con.close()

            new_count = count + 1

            await query.answer(
                f"Qatnashdingiz! "
                f"{new_count}/{CHANGE_MAX}"
            )

            if new_count >= CHANGE_MAX:
                await finish_change(
                    context,
                    chat_id,
                )

        finally:
            change_locks.discard(
                chat_id
            )

        return

    # CHANGE YAKUNLASH
    if data == "change_end":
        chat_id = query.message.chat.id

        con = db()

        change = con.execute(
            """
            SELECT *
            FROM changes
            WHERE chat_id=?
            AND active=1
            """,
            (chat_id,),
        ).fetchone()

        con.close()

        if not change:
            await query.answer(
                "Faol change yo‘q.",
                show_alert=True,
            )
            return

        if (
            uid != change["creator_id"]
            and not is_admin(uid)
        ):
            await query.answer(
                "Faqat yaratgan odam "
                "yoki admin yakunlaydi.",
                show_alert=True,
            )
            return

        await finish_change(
            context,
            chat_id,
        )

        return


# =========================================================
# HELP
# =========================================================

async def help_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    text = (
        "📚 <b>MAFIA BOT BUYRUQLARI</b>\n\n"

        "👤 <b>PROFIL</b>\n"
        "/profil — profil\n"
        "/money 5000 — reply orqali pul\n"
        "/give 1 — reply orqali almaz\n"
        "/change 100 — sovrinli change\n\n"

        "🎭 <b>O‘YIN</b>\n"
        "/newgame — yangi o‘yin\n"
        "/join — qo‘shilish\n"
        "/players — o‘yinchilar\n"
        "/startgame — boshlash\n"
        "/role — o‘z rolingiz\n"
        "/night — tun\n"
        "/day — kun\n\n"

        "🌙 <b>TUNGI HARAKATLAR</b>\n"
        "/kill raqam\n"
        "/heal raqam\n"
        "/check raqam\n"
        "/guard raqam\n"
        "/shoot raqam\n"
        "/silence raqam\n"
        "/protect raqam\n"
        "/shield universal\n"
        "/endnight\n\n"

        "🗳️ <b>OVOZ</b>\n"
        "/startvote\n"
        "/vote raqam\n"
        "/endvote\n\n"

        "🏆 <b>REYTING</b>\n"
        "/top — oylik\n"
        "/top1 — bugungi\n"
        "/top7 — 7 kunlik\n\n"

        "🔐 <b>ADMIN</b>\n"
        "/addadmin\n"
        "/deladmin\n"
        "/ban\n"
        "/unban\n"
        "/bankrot\n"
        "/giveadmin\n"
        "/who"
    )

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
    )


# =========================================================
# MESSAGE TRACKER
# =========================================================

async def message_tracker(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_user:
        get_player(
            update.effective_user
        )

    track_group_user(
        update
    )

    if (
        update.effective_chat
        and update.effective_chat.type != "private"
        and update.effective_user
        and banned(update.effective_user.id)
    ):
        try:
            await update.effective_message.delete()
        except Exception:
            pass


# =========================================================
# BOT COMMANDS
# =========================================================

async def post_init(
    application: Application,
):
    commands = [
        BotCommand(
            "start",
            "Botni boshlash",
        ),
        BotCommand(
            "profil",
            "Profil",
        ),
        BotCommand(
            "help",
            "Yordam",
        ),
        BotCommand(
            "newgame",
            "Yangi o‘yin",
        ),
        BotCommand(
            "join",
            "O‘yinga qo‘shilish",
        ),
        BotCommand(
            "players",
            "O‘yinchilar",
        ),
        BotCommand(
            "startgame",
            "O‘yinni boshlash",
        ),
        BotCommand(
            "role",
            "Rolim",
        ),
        BotCommand(
            "night",
            "Tun",
        ),
        BotCommand(
            "day",
            "Kun",
        ),
        BotCommand(
            "startvote",
            "Ovoz berish",
        ),
        BotCommand(
            "vote",
            "Ovoz",
        ),
        BotCommand(
            "endvote",
            "Ovozni yakunlash",
        ),
        BotCommand(
            "endnight",
            "Tunni yakunlash",
        ),
        BotCommand(
            "money",
            "Pul yuborish",
        ),
        BotCommand(
            "give",
            "Almaz yuborish",
        ),
        BotCommand(
            "change",
            "Sovrinli change",
        ),
        BotCommand(
            "top",
            "Oylik top",
        ),
        BotCommand(
            "top1",
            "Bugungi top",
        ),
        BotCommand(
            "top7",
            "7 kunlik top",
        ),
    ]

    await application.bot.set_my_commands(
        commands
    )


# =========================================================
# APPLICATION
# =========================================================

def build_application():
    application = (
        Application
        .builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    # Asosiy
    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CommandHandler(
            "profil",
            profile_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "profile",
            profile_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_cmd,
        )
    )

    # O'yin
    application.add_handler(
        CommandHandler(
            "newgame",
            newgame_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "join",
            join_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "players",
            players_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "startgame",
            startgame_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "role",
            role_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "night",
            night_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "day",
            day_cmd,
        )
    )

    # Tungi harakatlar
    application.add_handler(
        CommandHandler(
            "kill",
            kill_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "heal",
            heal_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "check",
            check_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "guard",
            guard_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "shoot",
            shoot_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "silence",
            silence_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "protect",
            protect_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "shield",
            shield_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "endnight",
            endnight_cmd,
        )
    )

    # Ovoz
    application.add_handler(
        CommandHandler(
            "startvote",
            startvote_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "vote",
            vote_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "endvote",
            endvote_cmd,
        )
    )

    # Iqtisod
    application.add_handler(
        CommandHandler(
            "money",
            money_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "give",
            gift_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "change",
            change_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "exchange",
            exchange_cmd,
        )
    )

    # Top
    application.add_handler(
        CommandHandler(
            "top",
            top_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "top1",
            top1_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "top7",
            top7_cmd,
        )
    )

    # Admin
    application.add_handler(
        CommandHandler(
            "addadmin",
            addadmin_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "deladmin",
            deladmin_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "ban",
            ban_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "unban",
            unban_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "bankrot",
            bankrot_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "giveadmin",
            give_admin_cmd,
        )
    )

    application.add_handler(
        CommandHandler(
            "who",
            who_cmd,
        )
    )

    # Tugmalar
    application.add_handler(
        CallbackQueryHandler(
            callbacks
        )
    )

    # Oddiy xabarlar
    application.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            message_tracker,
        )
    )

    return application


# =========================================================
# MAIN
# =========================================================

def main():
    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable topilmadi."
        )

    init_db()

    load_admins()

    threading.Thread(
        target=run_health_server,
        daemon=True,
    ).start()

    application = build_application()

    logger.info(
        "Bot ishga tushmoqda..."
    )

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
