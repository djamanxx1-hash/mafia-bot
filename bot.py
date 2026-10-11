Aimport os
import random
import sqlite3
import logging
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import (Update, BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats, InlineKeyboardButton, InlineKeyboardMarkup)
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler,
    MessageHandler, filters,
)

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
PORT = int(os.getenv("PORT", "10000"))
DB_PATH = os.getenv("DB_PATH", "mafia.db")
DIAMOND_ANIMATION_FILE_ID = os.getenv("DIAMOND_ANIMATION_FILE_ID", "").strip()

MAX_PLAYERS = 30
MIN_PLAYERS = 4
CHANGE_MAX = 50

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()
    con.executescript("""
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
        poison INTEGER DEFAULT 0,
        mask INTEGER DEFAULT 0,
        slip INTEGER DEFAULT 0,
        hero_protect INTEGER DEFAULT 0,
        ricochet INTEGER DEFAULT 0,
        profile_change INTEGER DEFAULT 0,
        hero INTEGER DEFAULT 0
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
    """)
    # Existing databases are upgraded safely with any new protection columns.
    existing = {row[1] for row in con.execute("PRAGMA table_info(protections)").fetchall()}
    for col in ("mask", "slip", "hero_protect", "ricochet", "profile_change", "hero"):
        if col not in existing:
            con.execute(f"ALTER TABLE protections ADD COLUMN {col} INTEGER DEFAULT 0")
    con.execute("INSERT OR IGNORE INTO admins(user_id) VALUES (?)", (OWNER_ID,))
    con.commit()
    con.close()


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
    logger.info("Health server PORT %s da ishga tushdi.", PORT)
    server.serve_forever()


players = {}
admins = set()
game_players = {}
game_started = False
game_chat_id = None
game_phase = "lobby"
night_actions = {}
votes = {}
silenced_users = set()
pending_inputs = {}
change_locks = set()

# Yangi rol to‘plami: 35 ta noyob rol. Eski rol nomlari olib tashlandi.
ROLES = [
    ("Tinch aholi", "👨🏼"), ("Komissar Kattani", "🕵🏼"), ("Serjant", "👮🏼"),
    ("Doktor", "👨🏼‍⚕️"), ("Tabib", "👨🏻‍⚕️"), ("Daydi", "🧙🏼"),
    ("Kezuvchi", "💃"), ("Afsungar", "💣"), ("Voris", "🧑🏻‍💼"),
    ("Janob", "🎖"), ("Ovchi", "🏹"), ("Donishmand", "👨🏼‍🏫"),
    ("Omadli", "🍀"), ("Suidsid", "🤦🏼"), ("Sotqin", "🤓"),
    ("Mafia", "🤵🏼"), ("Don", "🤵🏻"), ("Jurnalist", "👩🏼‍💻"),
    ("Yollanma qotil", "🕴"), ("Savdogar", "🧔🏻‍♂️"), ("Zaharchi", "🧑‍🎤"),
    ("Advokat", "👨🏼‍💼"), ("Qotil", "🔪"), ("G‘azabkor", "🧟"),
    ("Sehrgar", "🧙"), ("Vampir", "🧛🏻"), ("Haqiqiy Vampir", "🧛🏻‍♂️"),
    ("Qaroqchi", "🦹🏻‍♂️"), ("Konchi", "👷🏻‍♂️"), ("Banker", "👨🏻‍💻"),
    ("Bo‘ri", "🐺"), ("Gibrid", "🧛🏿‍♂️"), ("Reviver", "🧜🏻‍♂️"),
    ("Aferist", "🤹🏻"), ("Vampir ovchisi", "🧛‍♀️"),
]
ROLE_POINTS = {role: 100 for role, _ in ROLES}
ROLE_POINTS.update({"Don": 120, "Qotil": 150, "Haqiqiy Vampir": 150, "Gibrid": 150, "Vampir ovchisi": 130})

PROTECTIONS = {
    "universal": ("🛡️ Himoya", "100 pul", "Bir hujumdan himoya qiladi."),
    "fake_doc": ("📁 Hujjat", "190 pul", "Tekshiruvda rolingizni yashirishga yordam beradi."),
    "silence": ("🤫 Ovozdan himoya", "💎 1", "Ovoz bilan bog‘liq ta’sirdan himoya qiladi."),
    "protect_other": ("🔫 Miltiq", "💎 1", "O‘yinda maxsus hujum uchun ishlatiladi."),
    "poison": ("💊 Doridan himoya", "100 pul", "Zahar ta’siridan himoya qiladi."),
    "mask": ("🎭 Maska", "100 pul", "Tekshiruvda shaxsingizni yashirishga yordam beradi."),
    "killer": ("🚨 Qotildan himoya", "💎 2", "Qotil hujumidan bir marta saqlaydi."),
    "slip": ("🥊 Sirpanishdan himoya", "300 pul", "O‘yindan chiqarilish xavfidan saqlaydi."),
    "hero_protect": ("🛡️ Geroydan himoya", "💎 5", "Geroy hujumidan himoya qiladi."),
    "ricochet": ("🌀 Rikoshet himoyasi", "💎 3", "100+ darajada maxsus himoya beradi."),
    "profile_change": ("🔄 Profil almashtirish", "💎 5", "Profil ko‘rinishini almashtirish imkoniyati."),
    "hero": ("🦸 Geroy", "💎 90", "Maxsus geroy imkoniyatini ochadi."),
}


def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds")


def get_player(user):
    user_id = user.id
    name = user.first_name or "Noma'lum"
    username = user.username or ""
    con = db()
    row = con.execute("SELECT * FROM players WHERE user_id=?", (user_id,)).fetchone()
    if row is None:
        con.execute(
            "INSERT INTO players(user_id,name,username) VALUES(?,?,?)",
            (user_id, name, username),
        )
    else:
        con.execute("UPDATE players SET name=?, username=? WHERE user_id=?", (name, username, user_id))
    con.commit()
    con.close()
    players[user_id] = {
        "id": user_id, "name": name, "username": username,
        "diamonds": int(row["diamonds"]) if row else 0,
        "money": int(row["money"]) if row else 0,
        "dollars": int(row["dollars"]) if row else 0,
        "games": int(row["games"]) if row else 0,
        "wins": int(row["wins"]) if row else 0,
        "points": int(row["points"]) if row else 0,
        "banned": bool(row["banned"]) if row else False,
    }
    return players[user_id]


def get_player_by_id(user_id):
    con = db()
    row = con.execute("SELECT * FROM players WHERE user_id=?", (user_id,)).fetchone()
    con.close()
    if not row:
        return None
    return dict(row)


def save_balances(user_id, diamonds=None, money=None, dollars=None):
    fields, values = [], []
    if diamonds is not None:
        fields.append("diamonds=?"); values.append(int(diamonds))
    if money is not None:
        fields.append("money=?"); values.append(int(money))
    if dollars is not None:
        fields.append("dollars=?"); values.append(int(dollars))
    if not fields:
        return
    values.append(user_id)
    con = db()
    con.execute(f"UPDATE players SET {', '.join(fields)} WHERE user_id=?", values)
    con.commit(); con.close()
    if user_id in players:
        if diamonds is not None: players[user_id]["diamonds"] = int(diamonds)
        if money is not None: players[user_id]["money"] = int(money)
        if dollars is not None: players[user_id]["dollars"] = int(dollars)


def add_points(user_id, amount, reason):
    amount = int(amount)
    con = db()
    con.execute("UPDATE players SET points=points+? WHERE user_id=?", (amount, user_id))
    con.execute("INSERT INTO point_events(user_id,points,created_at,reason) VALUES(?,?,?,?)", (user_id, amount, now_iso(), reason))
    con.commit(); con.close()
    if user_id in players:
        players[user_id]["points"] += amount


def add_stats(user_id, games=0, wins=0):
    con = db()
    con.execute("UPDATE players SET games=games+?, wins=wins+? WHERE user_id=?", (games, wins, user_id))
    con.commit(); con.close()
    if user_id in players:
        players[user_id]["games"] += games
        players[user_id]["wins"] += wins


def ensure_protection_row(user_id):
    con = db(); con.execute("INSERT OR IGNORE INTO protections(user_id) VALUES(?)", (user_id,)); con.commit(); con.close()


def protection_count(user_id, key):
    ensure_protection_row(user_id)
    con = db(); row = con.execute(f"SELECT {key} FROM protections WHERE user_id=?", (user_id,)).fetchone(); con.close()
    return int(row[0]) if row else 0


def change_protection(user_id, key, delta):
    ensure_protection_row(user_id)
    con = db(); con.execute(f"UPDATE protections SET {key}=MAX(0,{key}+?) WHERE user_id=?", (delta, user_id)); con.commit(); con.close()


def is_owner(user_id):
    return user_id == OWNER_ID


def is_admin(user_id):
    if user_id == OWNER_ID:
        return True
    return user_id in admins


def load_admins():
    global admins
    con = db(); admins = {int(r[0]) for r in con.execute("SELECT user_id FROM admins")}; con.close()


def banned(user_id):
    p = get_player_by_id(user_id)
    return bool(p and p["banned"])


def require_allowed(update):
    if not update.effective_user:
        return False
    return not banned(update.effective_user.id)


def track_group_user(update):
    if update.effective_chat and update.effective_chat.type in ("group", "supergroup") and update.effective_user:
        get_player(update.effective_user)
        con = db(); con.execute("INSERT OR IGNORE INTO group_members(chat_id,user_id) VALUES(?,?)", (update.effective_chat.id, update.effective_user.id)); con.commit(); con.close()


def alive_players():
    return {uid: data for uid, data in game_players.items() if data.get("alive", False)}


def get_role(user_id):
    return game_players.get(user_id, {}).get("role")


def find_player_by_number(number):
    alive = list(alive_players().values())
    if number < 1 or number > len(alive):
        return None
    return alive[number - 1]


def game_list_text(include_status=True):
    if not game_players:
        return "📭 O‘yinchilar yo‘q."
    text = "👥 O‘YINCHILAR\n\n"
    for i, p in enumerate(game_players.values(), start=1):
        status = (" 🟢" if p.get("alive", False) else " 💀") if include_status else ""
        text += f"{i}. {p['name']}{status}\n"
    return text + f"\n👤 Jami: {len(game_players)}"


async def announce(context, text):
    if game_chat_id:
        try:
            await context.bot.send_message(chat_id=game_chat_id, text=text)
        except Exception as e:
            logger.error("Guruhga xabar yuborishda xato: %s", e)


def profile_text(p):
    profile_uid = p.get("user_id", p.get("id"))
    username = f"@{p['username']}" if p.get("username") else "username yo‘q"
    return (
        "👤 <b>PROFIL</b>\n\n"
        f"👤 Ism: <b>{p['name']}</b>\n"
        f"🆔 ID: <code>{p['user_id']}</code>\n"
        f"📱 Username: {username}\n\n"
        f"💰 Pul: <b>{p['money']}</b>\n"
        f"💎 Olmos: <b>{p['diamonds']}</b>\n"
        f"💵 Virtual $: <b>${p['dollars']}</b>\n"
        f"🛡️ Himoya: <b>{protection_count(profile_uid, 'universal')}</b>\n"
        f"📁 Hujjat: <b>{protection_count(profile_uid, 'fake_doc')}</b>\n"
        f"🤫 Ovozdan himoya: <b>{protection_count(profile_uid, 'silence')}</b>\n"
        f"🔫 Miltiq: <b>{protection_count(profile_uid, 'protect_other')}</b>\n"
        f"💊 Doridan himoya: <b>{protection_count(profile_uid, 'poison')}</b>\n"
        f"🎭 Maska: <b>{protection_count(profile_uid, 'mask')}</b>\n"
        f"🚨 Qotildan himoya: <b>{protection_count(profile_uid, 'killer')}</b>\n"
        f"🥊 Sirpanishdan himoya: <b>{protection_count(profile_uid, 'slip')}</b>\n"
        f"🛡️ Geroydan himoya: <b>{protection_count(profile_uid, 'hero_protect')}</b>\n"
        f"🌀 Rikoshet himoyasi: <b>{protection_count(profile_uid, 'ricochet')}</b>\n\n"
        f"🎯 G‘alaba: <b>{p['wins']}</b>\n"
        f"🎲 Barcha o‘yinlar: <b>{p['games']}</b>\n"
        f"🃏 Faol rollar: <b>{game_players.get(p['user_id'], {}).get('role', 'Yo‘q')}</b>\n"
        f"⭐ Ochko: <b>{p['points']}</b>"
    )


def profile_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 Almaz sotib olish", callback_data="shop_diamonds")],
        [InlineKeyboardButton("🎁 Almaz yuborish", callback_data="gift_diamond")],
        [InlineKeyboardButton("🛡️ Himoya markazi", callback_data="protection_menu")],
    ])


def protection_keyboard():
    keys = list(PROTECTIONS.keys())
    rows = []
    for i in range(0, len(keys), 2):
        row = []
        for key in keys[i:i+2]:
            row.append(InlineKeyboardButton(PROTECTIONS[key][0], callback_data=f"protect:{key}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Profil", callback_data="back_profile")])
    return InlineKeyboardMarkup(rows)


def protection_text():
    lines = [
        "🛡️ <b>HIMOYA MARKAZI</b>",
        "",
        "✨ O‘zingizni yoki ittifoqdoshingizni himoyalang.",
        "Har bir himoya maxsus vaziyatda bir martalik qo‘llanadi.",
        "",
    ]
    for key, (name, price, desc) in PROTECTIONS.items():
        lines += [f"{name} — <b>{price}</b>", desc, ""]
    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_allowed(update):
        return await update.message.reply_text("🚫 Sizning akkauntingiz botdan foydalanish uchun cheklangan.")
    p = get_player(update.effective_user)
    text = (
        "🎭 <b>MAFIA BOT</b>\n\n"
        "Xush kelibsiz!\n"
        "👤 Profilingizni ko‘rish uchun /profile bosing.\n"
        "🎭 O‘yin rollarini ko‘rish uchun /roles bosing.\n\n"
        f"💵 Dollar: <b>{p['dollars']}</b>\n💎 Olmos: <b>{p['diamonds']}</b>\n🪙 Oltin: <b>{p['money']}</b>"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_allowed(update): return
    await update.effective_message.reply_text(
        "📚 <b>BUYRUQLAR</b>\n\n"
        "/start — botni boshlash\n/profile — profil\n/roles — barcha o‘yin rollari\n/help — yordam\n"
        "/give 5 — reply orqali olmos yuborish\n/money 5000 — reply orqali pul yuborish\n/send 100 — admin olmos tarqatadi\n"
        "/change 100 — olmosli tanlov\n/newgame — yangi Mafia o‘yini\n/join — o‘yinga qo‘shilish\n"
        "/players — o‘yinchilar\n/startgame — o‘yinni boshlash\n/role — faol o‘yindagi o‘z rolingiz\n"
        "/night — tungi vazifa\n/vote 2 — ovoz berish\n/endnight — tunni tugatish\n\n"
        "🛡️ Himoya markazi profil ichida.", parse_mode="HTML")


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_allowed(update): return
    if context.args and is_admin(update.effective_user.id):
        try: target_id = int(context.args[0])
        except ValueError: return await update.message.reply_text("❌ ID noto‘g‘ri.")
        p = get_player_by_id(target_id)
        if not p: return await update.message.reply_text("❌ Bu ID bo‘yicha o‘yinchi topilmadi.")
        await update.message.reply_text(profile_text(p), parse_mode="HTML")
        return
    p = get_player(update.effective_user)
    await update.message.reply_text(profile_text(p), parse_mode="HTML", reply_markup=profile_keyboard())


async def money_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_allowed(update): return
    if not update.message.reply_to_message or not context.args:
        return await update.message.reply_text("🎁 Pul yuborish uchun o‘yinchining xabariga reply qilib:\n/money 5000")
    try: amount = int(context.args[0])
    except ValueError: return await update.message.reply_text("❌ Summani raqam bilan kiriting.")
    if amount <= 0: return await update.message.reply_text("❌ Summa 0 dan katta bo‘lishi kerak.")
    sender = get_player(update.effective_user)
    target_user = update.message.reply_to_message.from_user
    if target_user.id == sender["id"]: return await update.message.reply_text("❌ O‘zingizga pul yubora olmaysiz.")
    target = get_player(target_user)
    if sender["money"] < amount: return await update.message.reply_text("❌ Balansingizda yetarli pul yo‘q.")
    save_balances(sender["id"], money=sender["money"]-amount)
    save_balances(target["id"], money=target["money"]+amount)
    await update.message.reply_text(f"🎁✨ <b>HADYA YETKAZILDI!</b> ✨🎁\n\n💰 {amount} pul {target['name']}ga yuborildi.\n🤝 Yuboruvchi: {sender['name']}", parse_mode="HTML")


async def give_diamonds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_allowed(update): return
    target_user = None
    amount = None
    if update.message.reply_to_message and context.args:
        target_user = update.message.reply_to_message.from_user
        try: amount = int(context.args[0])
        except ValueError: pass
    elif len(context.args) >= 2:
        try: target_user = await context.bot.get_chat(int(context.args[0])); amount = int(context.args[1])
        except Exception: pass
    if not target_user or amount is None or amount <= 0:
        return await update.message.reply_text("💎 Olmos yuborish:\nReply → /give 5\nYoki: /give TELEGRAM_ID 5")
    sender = get_player(update.effective_user)
    if target_user.id == sender["id"]: return await update.message.reply_text("❌ O‘zingizga olmos yubora olmaysiz.")
    target = get_player(target_user)
    if sender["diamonds"] < amount: return await update.message.reply_text("❌ Balansingizda yetarli 💎 yo‘q.")
    save_balances(sender["id"], diamonds=sender["diamonds"]-amount)
    save_balances(target["id"], diamonds=target["diamonds"]+amount)
    msg = f"💎✨ <b>OLMOS HADYASI!</b> ✨💎\n\n🎁 Siz {target['name']}ga <b>{amount} 💎</b> yubordingiz."
    await update.message.reply_text(msg, parse_mode="HTML")
    try:
        if DIAMOND_ANIMATION_FILE_ID:
            await context.bot.send_animation(target["id"], DIAMOND_ANIMATION_FILE_ID)
        await context.bot.send_message(target["id"], f"💎✨ <b>SIZGA HADYA KELDI!</b> ✨💎\n\nSizga <b>{amount} 💎</b> olmos yuborildi!\n👤 Yuboruvchi: {sender['name']}", parse_mode="HTML")
    except Exception:
        pass


async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_allowed(update): return
    mode = update.message.text.split()[0].lower()
    if mode == "/top1":
        since = datetime.utcnow() - timedelta(days=1); label = "KUNLIK TOP"
    elif mode == "/top7":
        since = datetime.utcnow() - timedelta(days=7); label = "7 KUNLIK TOP"
    else:
        since = datetime(datetime.utcnow().year, datetime.utcnow().month, 1); label = "OYLIK TOP"
    con = db()
    rows = con.execute("""
        SELECT p.user_id,p.name,p.username,COALESCE(SUM(e.points),0) pts
        FROM players p LEFT JOIN point_events e ON p.user_id=e.user_id AND e.created_at>=?
        WHERE p.banned=0 GROUP BY p.user_id ORDER BY pts DESC, p.points DESC LIMIT 10
    """, (since.isoformat(timespec="seconds"),)).fetchall()
    con.close()
    text = f"🏆 <b>{label}</b>\n\n"
    for i, r in enumerate(rows, 1): text += f"{i}. {r['name']} — ⭐ {r['pts']}\n"
    await update.message.reply_text(text, parse_mode="HTML")


async def shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    if banned(uid): return await q.edit_message_text("🚫 Siz cheklangansiz.")
    if q.data == "shop_diamonds":
        await q.edit_message_text("💎 <b>ALMAZ DO‘KONI</b>\n\n💰 1 = 500\n💰 5 = 2 500\n💰 10 = 5 000\n💰 20 = 10 000\n\nTanlang:", parse_mode="HTML", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 1 — 500 💰", callback_data="buydia:1"), InlineKeyboardButton("💎 5 — 2500 💰", callback_data="buydia:5")],
            [InlineKeyboardButton("💎 10 — 5000 💰", callback_data="buydia:10"), InlineKeyboardButton("💎 20 — 10000 💰", callback_data="buydia:20")],
            [InlineKeyboardButton("⬅️ Profil", callback_data="back_profile")]
        ])); return
    if q.data.startswith("buydia:"):
        amount = int(q.data.split(":")[1]); price = amount * 500; p = get_player(q.from_user)
        if p["money"] < price: return await q.answer("❌ Pul yetarli emas.", show_alert=True)
        save_balances(uid, money=p["money"]-price, diamonds=p["diamonds"]+amount)
        await q.answer(f"✅ {amount} 💎 sotib olindi!", show_alert=True)
        await q.edit_message_text(profile_text(get_player(q.from_user)), parse_mode="HTML", reply_markup=profile_keyboard()); return
    if q.data == "back_profile":
        await q.edit_message_text(profile_text(get_player(q.from_user)), parse_mode="HTML", reply_markup=profile_keyboard()); return
    if q.data == "gift_diamond":
        pending_inputs[uid] = {"type":"gift", "step":"id"}
        await q.edit_message_text("🎁 <b>ALMAZ YUBORISH</b>\n\nQabul qiluvchining Telegram ID raqamini yuboring:", parse_mode="HTML"); return
    if q.data == "protection_menu":
        await q.edit_message_text(protection_text(), parse_mode="HTML", reply_markup=protection_keyboard()); return
    if q.data.startswith("protect:"):
        key = q.data.split(":",1)[1]
        name, price, desc = PROTECTIONS[key]
        await q.edit_message_text(f"{name}\n\n{desc}\n\n💳 Narxi: <b>{price}</b>\n\nSotib olishni tasdiqlaysizmi?", parse_mode="HTML", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Sotib olish", callback_data=f"buyprotect:{key}"), InlineKeyboardButton("⬅️ Orqaga", callback_data="protection_menu")]
        ])); return
    if q.data.startswith("buyprotect:"):
        key = q.data.split(":",1)[1]; name, price, _ = PROTECTIONS[key]; p = get_player(q.from_user)
        price = PROTECTIONS[key][1]
        if "pul" in price:
            cost = int(price.split()[0])
            if p["money"] < cost: return await q.answer("❌ Pul yetarli emas.", show_alert=True)
            save_balances(uid, money=p["money"]-cost)
        else:
            cost = int(price.replace("💎", "").strip())
            if p["diamonds"] < cost: return await q.answer("❌ 💎 yetarli emas.", show_alert=True)
            save_balances(uid, diamonds=p["diamonds"]-cost)
        change_protection(uid,key,1)
        await q.answer("✅ Himoya xarid qilindi!", show_alert=True)
        await q.edit_message_text(f"✅ <b>{name}</b> xarid qilindi.\n\n📦 Ombordagi soni: <b>{protection_count(uid,key)}</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛡️ Himoya markazi", callback_data="protection_menu")],[InlineKeyboardButton("⬅️ Profil", callback_data="back_profile")]])); return


async def handle_pending_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = pending_inputs.get(uid)
    if not state or update.message.chat.type != "private":
        return
    text = update.message.text.strip()
    if state["type"] == "gift":
        if state["step"] == "id":
            try: target_id = int(text)
            except ValueError: return await update.message.reply_text("❌ ID faqat raqam bo‘lishi kerak.")
            target = get_player_by_id(target_id)
            if not target: return await update.message.reply_text("❌ Bu foydalanuvchi botda ro‘yxatdan o‘tmagan.")
            if target_id == uid: return await update.message.reply_text("❌ O‘zingizga yubora olmaysiz.")
            state.update({"step":"amount","target_id":target_id})
            return await update.message.reply_text("💎 Qancha olmos yuborasiz? Masalan: 5")
        if state["step"] == "amount":
            try: amount = int(text)
            except ValueError: return await update.message.reply_text("❌ Miqdorni raqam bilan kiriting.")
            if amount <= 0: return await update.message.reply_text("❌ Miqdor 0 dan katta bo‘lsin.")
            target = get_player_by_id(state["target_id"]); sender = get_player(update.effective_user)
            if sender["diamonds"] < amount: return await update.message.reply_text("❌ Balansingizda yetarli 💎 yo‘q.")
            state.update({"step":"confirm","amount":amount})
            await update.message.reply_text(f"🎁 {target['name']}ga <b>{amount} 💎</b> yuborilsinmi?", parse_mode="HTML", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Tasdiqlash", callback_data="giftconfirm:yes"), InlineKeyboardButton("❌ Bekor qilish", callback_data="giftconfirm:no")]
            ]))


async def gift_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); uid=q.from_user.id; state=pending_inputs.get(uid)
    if not state or state.get("step") != "confirm": return await q.edit_message_text("⌛ Bu amal eskirgan.")
    if q.data == "giftconfirm:no": pending_inputs.pop(uid,None); return await q.edit_message_text("❌ Hadya bekor qilindi.")
    target=get_player_by_id(state["target_id"]); sender=get_player(q.from_user); amount=state["amount"]
    if not target or sender["diamonds"] < amount: pending_inputs.pop(uid,None); return await q.edit_message_text("❌ Amalni bajarib bo‘lmadi.")
    save_balances(uid, diamonds=sender["diamonds"]-amount); save_balances(target["user_id"], diamonds=target["diamonds"]+amount)
    pending_inputs.pop(uid,None)
    await q.edit_message_text(f"💎✨ <b>HADYA YUBORILDI!</b>\n\n{target['name']}ga <b>{amount} 💎</b> yuborildi.", parse_mode="HTML")
    try:
        if DIAMOND_ANIMATION_FILE_ID: await context.bot.send_animation(target["user_id"], DIAMOND_ANIMATION_FILE_ID)
        await context.bot.send_message(target["user_id"], f"💎✨ Sizga <b>{amount} 💎</b> olmos hadya qilindi!", parse_mode="HTML")
    except Exception: pass


async def send_diamonds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_allowed(update): return
    if not update.message.chat.type in ("group","supergroup") or not is_admin(update.effective_user.id):
        return await update.message.reply_text("🔒 Bu buyruq faqat guruh administratori uchun.")
    if not context.args or not context.args[0].isdigit(): return await update.message.reply_text("/send 100 — 100 ta olmosni 100 ta turli o‘yinchiga 1 tadan tarqatadi.")
    amount=int(context.args[0])
    if amount<=0: return await update.message.reply_text("❌ Miqdor 0 dan katta bo‘lsin.")
    con=db(); rows=con.execute("SELECT p.* FROM players p JOIN group_members g ON p.user_id=g.user_id WHERE g.chat_id=? AND p.banned=0",(update.effective_chat.id,)).fetchall(); con.close()
    eligible=[dict(r) for r in rows]
    if len(eligible)<amount: return await update.message.reply_text(f"❌ Yetarli ro‘yxatdan o‘tgan o‘yinchi yo‘q. Kerak: {amount}, mavjud: {len(eligible)}.")
    chosen=random.sample(eligible,amount)
    for p in chosen: save_balances(p["user_id"], diamonds=p["diamonds"]+1)
    await update.message.reply_text(f"🎁💎 <b>{amount} TA OLMOS TARQATILDI!</b>\n\nHar bir tanlangan o‘yinchiga 1 💎 dan berildi.", parse_mode="HTML")


async def change_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_allowed(update): return
    if not update.message.chat.type in ("group","supergroup"): return await update.message.reply_text("❌ Bu buyruq guruhda ishlaydi.")
    if not context.args or not context.args[0].isdigit(): return await update.message.reply_text("/change 100")
    prize=int(context.args[0]); uid=update.effective_user.id
    if prize<=0: return await update.message.reply_text("❌ Sovrin 0 dan katta bo‘lsin.")
    if update.effective_chat.id in change_locks: return await update.message.reply_text("⏳ Bu guruhda tanlov allaqachon davom etmoqda.")
    p=get_player(update.effective_user)
    if p["diamonds"]<prize: return await update.message.reply_text("❌ Sovrinni yaratish uchun sizda yetarli 💎 yo‘q.")
    save_balances(uid, diamonds=p["diamonds"]-prize)
    chat_id=update.effective_chat.id
    con=db(); con.execute("INSERT OR REPLACE INTO changes(chat_id,creator_id,prize,message_id,active) VALUES(?,?,?,?,1)",(chat_id,uid,prize,0)); con.execute("DELETE FROM change_participants WHERE chat_id=?",(chat_id,)); con.commit(); con.close(); change_locks.add(chat_id)
    msg=await update.message.reply_text(f"🎉 <b>OMADLI TANLOV!</b> 🎉\n\n💎 Sovrin: <b>{prize} 💎</b>\n👥 Maksimal qatnashuvchi: <b>50</b>\n\nQatnashish uchun tugmani bosing!",parse_mode="HTML",reply_markup=change_keyboard())
    con=db(); con.execute("UPDATE changes SET message_id=? WHERE chat_id=?",(msg.message_id,chat_id)); con.commit(); con.close()


def change_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🎯 QATNASHISH",callback_data="change:join")],[InlineKeyboardButton("🛑 YAKUNLASH",callback_data="change:end")]])


async def change_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); uid=q.from_user.id; chat_id=q.message.chat.id
    con=db(); ch=con.execute("SELECT * FROM changes WHERE chat_id=? AND active=1",(chat_id,)).fetchone()
    if not ch: con.close(); return await q.answer("Tanlov yakunlangan.",show_alert=True)
    if q.data=="change:join":
        exists=con.execute("SELECT 1 FROM change_participants WHERE chat_id=? AND user_id=?",(chat_id,uid)).fetchone()
        if exists: con.close(); return await q.answer("Siz allaqachon qatnashgansiz.",show_alert=True)
        count=con.execute("SELECT COUNT(*) FROM change_participants WHERE chat_id=?",(chat_id,)).fetchone()[0]
        if count>=CHANGE_MAX: con.close(); return await q.answer("Joy qolmagan.",show_alert=True)
        con.execute("INSERT INTO change_participants(chat_id,user_id) VALUES(?,?)",(chat_id,uid)); con.commit(); count+=1; con.close()
        await q.answer(f"✅ Qatnashdingiz! {count}/{CHANGE_MAX}",show_alert=True)
        if count>=CHANGE_MAX: await finish_change(context,chat_id,"50 ishtirokchiga yetdi")
        else:
            try: await q.edit_message_text(f"🎉 <b>OMADLI TANLOV!</b> 🎉\n\n💎 Sovrin: <b>{ch['prize']} 💎</b>\n👥 Qatnashuvchilar: <b>{count}/{CHANGE_MAX}</b>",parse_mode="HTML",reply_markup=change_keyboard())
            except Exception: pass
    else:
        if uid!=ch["creator_id"] and not is_admin(uid): con.close(); return await q.answer("❌ Faqat tanlov egasi yoki admin yakunlay oladi.",show_alert=True)
        con.close(); await finish_change(context,chat_id,"qo‘lda yakunlandi")


async def finish_change(context,chat_id,reason):
    con=db(); ch=con.execute("SELECT * FROM changes WHERE chat_id=? AND active=1",(chat_id,)).fetchone();
    if not ch: con.close(); change_locks.discard(chat_id); return
    parts=con.execute("SELECT user_id FROM change_participants WHERE chat_id=?",(chat_id,)).fetchall(); con.close()
    if not parts:
        p=get_player_by_id(ch["creator_id"]); save_balances(ch["creator_id"],diamonds=p["diamonds"]+ch["prize"])
        await context.bot.send_message(chat_id,f"🛑 Tanlov ishtirokchisiz yakunlandi. {ch['prize']} 💎 egasiga qaytarildi.");
    else:
        winner_id=random.choice([int(r[0]) for r in parts]); winner=get_player_by_id(winner_id); save_balances(winner_id,diamonds=winner["diamonds"]+ch["prize"])
        await context.bot.send_message(chat_id,f"🏆🎉 <b>G‘OLIB ANIQLANDI!</b> 🎉🏆\n\n👤 {winner['name']}\n💎 Sovrin: <b>{ch['prize']} 💎</b>\n✨ {reason}",parse_mode="HTML")
    con=db(); con.execute("UPDATE changes SET active=0 WHERE chat_id=?",(chat_id,)); con.commit(); con.close(); change_locks.discard(chat_id)


async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_players,game_started,game_chat_id,game_phase,night_actions,votes,silenced_users
    if not require_allowed(update): return
    if not update.message.chat.type in ("group","supergroup"): return await update.message.reply_text("❌ O‘yinni guruhda boshlang.")
    if not is_admin(update.effective_user.id): return await update.message.reply_text("🔒 Faqat admin yangi o‘yin boshlaydi.")
    game_players={}; game_started=False; game_chat_id=update.effective_chat.id; game_phase="lobby"; night_actions={}; votes={}; silenced_users=set()
    await update.message.reply_text("🎭 <b>YANGI MAFIA O‘YINI</b>\n\n👥 O‘yinga qo‘shilish uchun /join\n👤 Maksimal: 30\n🎯 Minimal: 4",parse_mode="HTML")


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_allowed(update): return
    global game_players
    if game_started: return await update.message.reply_text("❌ O‘yin allaqachon boshlangan.")
    if len(game_players)>=MAX_PLAYERS: return await update.message.reply_text("❌ O‘rinlar to‘ldi.")
    p=get_player(update.effective_user); game_players[p["id"]]={"id":p["id"],"name":p["name"],"username":p["username"],"alive":True}
    await update.message.reply_text(f"✅ {p['name']} o‘yinga qo‘shildi. Jami: {len(game_players)}/{MAX_PLAYERS}")


async def players_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_allowed(update): return
    await update.message.reply_text(game_list_text())


async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_started,game_phase,night_actions,votes
    if not require_allowed(update): return
    if not is_admin(update.effective_user.id): return await update.message.reply_text("🔒 Faqat admin.")
    if len(game_players)<MIN_PLAYERS: return await update.message.reply_text(f"❌ Kamida {MIN_PLAYERS} o‘yinchi kerak.")
    if game_started: return await update.message.reply_text("❌ O‘yin allaqachon boshlangan.")
    game_started=True; game_phase="night"; night_actions={}; votes={}
    role_pool=select_roles(len(game_players)); random.shuffle(role_pool)
    for i,(uid,p) in enumerate(game_players.items()):
        role,icon=role_pool[i]; p.update({"role":role,"icon":icon,"alive":True,"protected":False,"poisoned":False,"silenced":False}); add_stats(uid,games=1)
        try: await context.bot.send_message(uid,f"🎭 <b>SIZNING ROLINGIZ</b>\n\n{icon} <b>{role}</b>\n\n🔐 Bu ma’lumot maxfiy.",parse_mode="HTML")
        except Exception: pass
    await announce(context,"🌙 <b>TUN BOSHLANDI</b>\n\nHar bir rol o‘z vazifasini bajaradi. /night orqali ko‘rsatmani ko‘ring.")
    await check_winner(context)


async def role_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_allowed(update): return
    if not game_started or update.effective_user.id not in game_players: return await update.message.reply_text("❌ Siz faol o‘yinda emassiz.")
    p=game_players[update.effective_user.id]
    await update.message.reply_text(f"🎭 Sizning rolingiz: {p['icon']} <b>{p['role']}</b>",parse_mode="HTML")


async def roles_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_allowed(update):
        return
    unique_roles = []
    seen = set()
    for role, icon in ROLES:
        if role not in seen:
            seen.add(role)
            unique_roles.append((role, icon))
    lines = ["🎭 <b>MAFIA O‘YINI — ROLLAR</b>", ""]
    for role, icon in unique_roles:
        description = ROLE_HELP.get(role, "O‘yindagi maxsus rol.")
        lines.append(f"{icon} <b>{role}</b> — {description}")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")


ROLE_HELP = {
    "Tinch aholi": "Kunduzgi muhokama va ovoz berishda qatnashing.",
    "Komissar Kattani": "Tunda mafiyani aniqlash va yo‘q qilish.",
    "Serjant": "Komissar Kattani yordamchisi; u halok bo‘lsa o‘rnini egallaydi.",
    "Doktor": "Tunda bir o‘yinchini qutqarishga harakat qiladi.",
    "Tabib": "Zaharlangan o‘yinchini davolaydi.",
    "Daydi": "Tunda birovning uyiga borib, qotillikka guvoh bo‘lishi mumkin.",
    "Kezuvchi": "Mehmonga borgan o‘yinchini bir kechaga uxlatadi.",
    "Afsungar": "O‘ldirilsa, uni o‘ldirgan ham halok bo‘ladi.",
    "Voris": "Uni kim o‘ldirganiga qarab rolini o‘zgartiradi.",
    "Janob": "Kunduzgi ovozi ikkita hisoblanadi.",
    "Ovchi": "Tunda o‘yinchilarni tekshirishi yoki nishonga olishi mumkin.",
    "Donishmand": "Tungi ayrim maxfiy suhbatlarni eshitadi.",
    "Omadli": "Tungi hujumdan 50% ehtimol bilan omon qoladi.",
    "Suidsid": "Mafia uni o‘ldirsa, mafiani ham o‘zi bilan olib ketadi.",
    "Sotqin": "Mafia g‘alaba qilganida tirik bo‘lsa, u ham yutadi.",
    "Mafia": "Mafia jamoasi bilan tinch aholini yo‘q qiladi.",
    "Don": "Mafianing tungi nishonini belgilaydi.",
    "Jurnalist": "Tunda uyiga kelgan o‘yinchilarni kuzatadi.",
    "Yollanma qotil": "Mafia uchun alohida hujum qiladi.",
    "Savdogar": "Qora bozor orqali xavfli qutilarni taklif qiladi.",
    "Zaharchi": "Tunda o‘yinchini zaharlaydi; Tabib davolashi mumkin.",
    "Advokat": "Mafia sherigini tekshiruvdan yashiradi.",
    "Qotil": "Yakka o‘ynaydi va boshqalarning yo‘q qilinishini maqsad qiladi.",
    "G‘azabkor": "Uch qurbon tanlab, keyin o‘zini o‘ldirsa g‘alaba qiladi.",
    "Sehrgar": "Maxsus hujumlardan omon qolishi va la’nat qo‘yishi mumkin.",
    "Vampir": "Tunda nishonga hujum qiladi; ayrim rollar qarshi tura oladi.",
    "Haqiqiy Vampir": "Faqat kunduzgi osilish orqali yo‘q qilinadi.",
    "Qaroqchi": "Tunda pul, buyum yoki ovoz huquqini o‘g‘irlashi mumkin.",
    "Konchi": "Tunda dollar yoki olmos topadi; tirik qolsa yutadi.",
    "Banker": "Konchi yoki Savdogar daromadidan 10% oladi.",
    "Bo‘ri": "Tunda bir o‘yinchiga hujum qiladi; vampirlarga qarshi xavfi bor.",
    "Gibrid": "Maxsus kuchli rol; har kecha bir o‘yinchiga hujum qiladi.",
    "Reviver": "O‘yin davomida bir marta o‘lgan o‘yinchini tiriltiradi.",
    "Aferist": "Tunda tanlangan o‘yinchining harakatini o‘g‘irlaydi.",
    "Vampir ovchisi": "Vampirlarni aniqlash ва уларга қарши курашиш учун махсус rol.",
}


async def night_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_allowed(update): return
    if not game_started or game_phase!="night": return await update.message.reply_text("❌ Hozir tun bosqichi emas.")
    p=game_players.get(update.effective_user.id)
    if not p or not p.get("alive"): return await update.message.reply_text("💀 Siz o‘yinda faol emassiz.")
    await update.message.reply_text(f"🌙 <b>TUNGI VAZIFA</b>\n\n{ROLE_HELP.get(p['role'],'Maxsus vazifa.')}",parse_mode="HTML")


def action_target(update, context):
    if not game_started or game_phase!="night": return None,"❌ Hozir tun bosqichi emas."
    p=game_players.get(update.effective_user.id)
    if not p or not p.get("alive"): return None,"💀 Siz tirik o‘yinchi emassiz."
    if not context.args or not context.args[0].isdigit(): return None,"❌ Masalan: /kill 2"
    target=find_player_by_number(int(context.args[0]))
    if not target: return None,"❌ O‘yinchi raqami noto‘g‘ri."
    if target["id"]==update.effective_user.id and p["role"] not in ("Doktor","Bodyguard"): return None,"❌ O‘zingizni tanlay olmaysiz."
    return target,None


async def kill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_allowed(update): return
    p=game_players.get(update.effective_user.id)
    if not p or p.get("role") not in ("Mafia","Don","Godfather","Manyak"): return await update.message.reply_text("❌ Bu rol hujum qila olmaydi.")
    target,err=action_target(update,context)
    if err: return await update.message.reply_text(err)
    night_actions[update.effective_user.id]={"type":"kill","target":target["id"],"role":p["role"]}
    await update.message.reply_text(f"🔪 Nishon tanlandi: {target['name']}")


async def heal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_allowed(update): return
    p=game_players.get(update.effective_user.id)
    if not p or p.get("role")!="Doktor": return await update.message.reply_text("❌ Bu imkoniyat Doktorga tegishli.")
    target,err=action_target(update,context)
    if err:return await update.message.reply_text(err)
    night_actions[update.effective_user.id]={"type":"heal","target":target["id"]}; await update.message.reply_text(f"💉 {target['name']} davolanadi.")


async def guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_allowed(update): return
    p=game_players.get(update.effective_user.id)
    if not p or p.get("role") not in ("Bodyguard","Advokat"): return await update.message.reply_text("❌ Bu imkoniyat Bodyguard/Advokatga tegishli.")
    target,err=action_target(update,context)
    if err:return await update.message.reply_text(err)
    night_actions[update.effective_user.id]={"type":"guard","target":target["id"]}; await update.message.reply_text(f"🛡️ {target['name']} himoyalanadi.")


async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_allowed(update): return
    p=game_players.get(update.effective_user.id)
    if not p or p.get("role") not in ("Komissar","Sherif","Detektiv","Jurnalist","Haker"): return await update.message.reply_text("❌ Sizda tekshiruv imkoniyati yo‘q.")
    target,err=action_target(update,context)
    if err:return await update.message.reply_text(err)
    role=target["role"]
    if protection_count(target["id"],"fake_doc")>0:
        change_protection(target["id"],"fake_doc",-1); shown="👤 Fuqaro"
    else: shown=role
    await update.message.reply_text(f"🔍 Tekshiruv natijasi: {target['name']} → <b>{shown}</b>",parse_mode="HTML")


async def shoot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_allowed(update): return
    p=game_players.get(update.effective_user.id)
    if not p or p.get("role")!="Snayper": return await update.message.reply_text("❌ Bu imkoniyat Snayperga tegishli.")
    target,err=action_target(update,context)
    if err:return await update.message.reply_text(err)
    night_actions[update.effective_user.id]={"type":"shoot","target":target["id"]}; await update.message.reply_text(f"🎯 Nishon belgilandi: {target['name']}")


async def silence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_allowed(update): return
    p=game_players.get(update.effective_user.id)
    if not p or p.get("role")!="Psixolog": return await update.message.reply_text("❌ Bu imkoniyat Psixologga tegishli.")
    target,err=action_target(update,context)
    if err:return await update.message.reply_text(err)
    night_actions[update.effective_user.id]={"type":"silence","target":target["id"]}; await update.message.reply_text(f"🔇 {target['name']}ning ovozi cheklanadi.")


async def endnight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_phase,night_actions,silenced_users
    if not require_allowed(update): return
    if not is_admin(update.effective_user.id): return await update.message.reply_text("🔒 Faqat admin.")
    if game_phase!="night": return await update.message.reply_text("❌ Hozir tun emas.")
    killed=[]; healed=set(); guarded=set(); silenced=set(); shooters=[]
    for a in night_actions.values():
        if a["type"]=="heal": healed.add(a["target"])
        elif a["type"]=="guard": guarded.add(a["target"])
        elif a["type"]=="silence": silenced.add(a["target"])
        elif a["type"] in ("kill","shoot"): killed.append((a["target"],a["role"],a["type"]))
    silenced_users=silenced
    for target_id,role,atype in killed:
        target=game_players.get(target_id)
        if not target or not target.get("alive"): continue
        blocked=False
        if target_id in healed or target_id in guarded: blocked=True
        if atype=="kill" and role=="Manyak" and protection_count(target_id,"killer")>0:
            change_protection(target_id,"killer",-1); blocked=True
        elif atype=="shoot" and protection_count(target_id,"universal")>0:
            change_protection(target_id,"universal",-1); blocked=True
        if not blocked and target_id not in healed and target_id not in guarded:
            target["alive"]=False; killed.append((target_id,role,"resolved"))
    game_phase="day"; night_actions={}
    msg="☀️ <b>KUN BOSHLANDI</b>\n\n"
    dead_ids=[]
    for uid,p in game_players.items():
        if not p.get("alive"): dead_ids.append(uid)
    if dead_ids:
        msg += "💀 Kechasi qurbonlar: " + ", ".join(game_players[x]["name"] for x in dead_ids) + "\n"
    else: msg += "🌤️ Bu kecha hech kim halok bo‘lmadi.\n"
    if silenced:
        msg += "🔇 Bugun ovozi cheklanganlar bor.\n"
    await announce(context,msg)
    await check_winner(context)


async def vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_allowed(update): return
    if game_phase!="day": return await update.message.reply_text("❌ Hozir ovoz berish vaqti emas.")
    p=game_players.get(update.effective_user.id)
    if not p or not p.get("alive"): return await update.message.reply_text("💀 Siz ovoz bera olmaysiz.")
    if update.effective_user.id in silenced_users: return await update.message.reply_text("🔇 Bugun ovoz berishingiz cheklangan.")
    if not context.args or not context.args[0].isdigit(): return await update.message.reply_text("Masalan: /vote 3")
    target=find_player_by_number(int(context.args[0]))
    if not target:return await update.message.reply_text("❌ Raqam noto‘g‘ri.")
    if target["id"]==update.effective_user.id:return await update.message.reply_text("❌ O‘zingizga ovoz bera olmaysiz.")
    if protection_count(target["id"],"vote")>0:
        change_protection(target["id"],"vote",-1); return await update.message.reply_text(f"🛡️ {target['name']} ovoz himoyasidan foydalandi. Bu ovoz unga ta’sir qilmaydi.")
    votes[update.effective_user.id]=target["id"]
    await update.message.reply_text(f"🗳️ Ovozingiz qabul qilindi: {target['name']}")
    alive_count=len(alive_players())
    if len(votes)>=max(1,alive_count-len(silenced_users)): await process_votes(context)


async def process_votes(context):
    global game_phase,votes
    if not votes:return
    counts={}
    for target in votes.values(): counts[target]=counts.get(target,0)+1
    max_votes=max(counts.values()); top=[uid for uid,n in counts.items() if n==max_votes]
    if len(top)>1:
        await announce(context,"⚖️ Ovozlar teng chiqdi. Hech kim chiqarilmadi.")
    else:
        uid=top[0]; game_players[uid]["alive"]=False; await announce(context,f"🗳️ Ovoz berish natijasi: {game_players[uid]['name']} o‘yindan chiqarildi. 💀")
    votes={}; game_phase="night"; await check_winner(context)
    if game_started: await announce(context,"🌙 Yangi tun boshlandi. /night")


async def check_winner(context):
    global game_started,game_phase
    if not game_started:return
    alive=list(alive_players().values())
    mafia=sum(1 for p in alive if p["role"] in ("Mafia","Don","Godfather"))
    maniac=sum(1 for p in alive if p["role"]=="Manyak")
    civilians=len(alive)-mafia-maniac
    if maniac and len(alive)==1:
        await finish_game(context,"Manyak",[p for p in alive if p["role"]=="Manyak"]); return
    if mafia==0:
        await finish_game(context,"Fuqaro",[p for p in game_players.values() if p["alive"] and p["role"] not in ("Mafia","Don","Godfather","Manyak")]); return
    if mafia>=civilians+maniac:
        await finish_game(context,"Mafia",[p for p in game_players.values() if p["alive"] and p["role"] in ("Mafia","Don","Godfather")])


async def finish_game(context,side,winners):
    global game_started,game_phase,game_players,night_actions,votes,silenced_users
    if not game_started:return
    names=[]
    for p in winners:
        uid=p["id"]; role=p["role"]; reward=ROLE_POINTS.get(role,50)
        add_stats(uid,wins=1); add_points(uid,reward,f"G‘alaba: {role}")
        save_balances(uid,dollars=get_player(uid)["dollars"]+20)
        names.append(f"{p['name']} ({role}) +⭐{reward} +$20")
    await announce(context,f"🏆 <b>O‘YIN YAKUNLANDI</b>\n\n🎯 G‘olib tomon: <b>{side}</b>\n\n"+"\n".join(names),)
    game_started=False; game_phase="lobby"; night_actions={}; votes={}; silenced_users=set()
    for p in game_players.values(): p.pop("role",None)


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_allowed(update):return
    if not is_admin(update.effective_user.id):return await update.message.reply_text("🔒 Adminlar uchun.")
    await update.message.reply_text("👑 <b>ADMIN PANEL</b>\n\n/admin — panel\n/adddiamonds ID AMOUNT\n/addbalance ID AMOUNT\n/ban ID\n/unban ID\n/makeadmin ID\n/removeadmin ID\n/profile ID\n/bankrot1 ID — balansni 0 qilish\n/bankrot2 ID — 💎 va $ ni 0 qilish",parse_mode="HTML")


async def adddiamonds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):return
    if len(context.args)<2:return await update.message.reply_text("/adddiamonds ID 100")
    try: uid,amount=int(context.args[0]),int(context.args[1])
    except ValueError:return await update.message.reply_text("❌ Raqam noto‘g‘ri.")
    p=get_player_by_id(uid)
    if not p:return await update.message.reply_text("❌ O‘yinchi topilmadi.")
    save_balances(uid,diamonds=p["diamonds"]+amount); await update.message.reply_text("✅ Olmos qo‘shildi.")


async def addbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):return
    if len(context.args)<2:return await update.message.reply_text("/addbalance ID 10000")
    try: uid,amount=int(context.args[0]),int(context.args[1])
    except ValueError:return await update.message.reply_text("❌ Raqam noto‘g‘ri.")
    p=get_player_by_id(uid)
    if not p:return await update.message.reply_text("❌ O‘yinchi topilmadi.")
    save_balances(uid,money=p["money"]+amount); await update.message.reply_text("✅ Pul qo‘shildi.")


async def bankrot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):return
    if not context.args:return await update.message.reply_text("/bankrot1 ID yoki /bankrot2 ID")
    try:uid=int(context.args[0])
    except ValueError:return await update.message.reply_text("❌ ID noto‘g‘ri.")
    p=get_player_by_id(uid)
    if not p:return await update.message.reply_text("❌ Topilmadi.")
    if update.message.text.startswith("/bankrot1"): save_balances(uid,money=0)
    else: save_balances(uid,diamonds=0,dollars=0)
    await update.message.reply_text("⚠️ Balans yangilandi.")


async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):return
    if not context.args:return await update.message.reply_text("/ban ID")
    try:uid=int(context.args[0])
    except ValueError:return await update.message.reply_text("❌ ID noto‘g‘ri.")
    con=db();con.execute("UPDATE players SET banned=1 WHERE user_id=?",(uid,));con.commit();con.close();await update.message.reply_text("🚫 Foydalanuvchi cheklangan.")


async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):return
    if not context.args:return await update.message.reply_text("/unban ID")
    try:uid=int(context.args[0])
    except ValueError:return await update.message.reply_text("❌ ID noto‘g‘ri.")
    con=db();con.execute("UPDATE players SET banned=0 WHERE user_id=?",(uid,));con.commit();con.close();await update.message.reply_text("✅ Cheklov olib tashlandi.")


async def makeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):return
    if not context.args:return await update.message.reply_text("/makeadmin ID")
    try:uid=int(context.args[0])
    except ValueError:return await update.message.reply_text("❌ ID noto‘g‘ri.")
    con=db();con.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)",(uid,));con.commit();con.close();admins.add(uid);await update.message.reply_text("👑 Admin qo‘shildi.")


async def removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):return
    if not context.args:return await update.message.reply_text("/removeadmin ID")
    try:uid=int(context.args[0])
    except ValueError:return await update.message.reply_text("❌ ID noto‘g‘ri.")
    if uid==OWNER_ID:return await update.message.reply_text("❌ Ownerni olib bo‘lmaydi.")
    con=db();con.execute("DELETE FROM admins WHERE user_id=?",(uid,));con.commit();con.close();admins.discard(uid);await update.message.reply_text("✅ Admin olib tashlandi.")


async def lang_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("🌐 Hozircha bot tili: O‘zbekcha.")

async def game_alias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await newgame(update, context)

async def vsgame_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or update.effective_chat.type not in ("group", "supergroup"):
        return await update.effective_message.reply_text("Bu buyruq guruhda ishlaydi.")
    await update.effective_message.reply_text("⚔️ Jamoaviy o‘yin rejimi tanlandi. Yangi o‘yin uchun /newgame, qo‘shilish uchun /join.")

async def leave_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in game_players:
        return await update.effective_message.reply_text("Siz joriy o‘yinda emassiz.")
    if game_started:
        return await update.effective_message.reply_text("O‘yin boshlanganidan keyin chiqib bo‘lmaydi.")
    game_players.pop(uid, None)
    await update.effective_message.reply_text("✅ O‘yindan chiqдингиз.")

async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.effective_message.reply_text("🔒 Sozlamalarni faqat guruh admini o‘zgartiradi.")
    await update.effective_message.reply_text("⚙️ O‘yin sozlamalari: minimal 4 o‘yinchi, maksimal 30 o‘yinchi. Rollar /roles orqali ko‘riladi.")

async def giveaway_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.effective_message.reply_text("🔒 Giveaway sozlash faqat admin uchun.")
    await update.effective_message.reply_text("🎁 Giveaway funksiyasi uchun sovrin va muddatni keyingi sozlashda belgilash mumkin.")

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_players, game_started, game_phase, night_actions, votes
    if not is_admin(update.effective_user.id):
        return await update.effective_message.reply_text("🔒 Faqat admin o‘yinni to‘xtata oladi.")
    game_players = {}; game_started = False; game_phase = "lobby"; night_actions = {}; votes = {}
    await update.effective_message.reply_text("⛔ O‘yin to‘xtatildi.")

async def reload_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    load_admins()
    await update.effective_message.reply_text("🔄 Guruh ma’lumotlari yangilandi.")

async def kurs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("🪙 Hozirgi kurs: 1 olmos = 500 pul. 1 pul — bot ichidagi o‘yin valyutasi.")

async def para_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        return await msg.reply_text("💞 /para buyrug‘ini guruhda ishlating.")
    con = db()
    rows = con.execute(
        "SELECT p.user_id, p.name FROM players p JOIN group_members g ON p.user_id=g.user_id "
        "WHERE g.chat_id=? AND p.banned=0", (chat.id,)
    ).fetchall()
    con.close()
    candidates = [(int(r["user_id"]), r["name"] or "Noma’lum") for r in rows]
    if len(candidates) < 2:
        return await msg.reply_text("💞 Juftlik tanlash uchun guruhda kamida 2 o‘yinchi /buyruqlar orqali ro‘yxatga tushgan bo‘lishi kerak.")
    first, second = random.sample(candidates, 2)
    await msg.reply_text(
        f"💞 <b>HAQIQIY JUFTLIK</b> 💞\n\n<b>{first[1].upper()} ❤️ {second[1].upper()}</b>",
        parse_mode="HTML"
    )


async def track_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_group_user(update)


def select_roles(n):
    """Ishtirokchilar soniga qarab yangi rollarni takrorlamasdan tanlaydi."""
    pool = list(ROLES)
    mafia_roles = [("Don", "🤵🏻"), ("Mafia", "🤵🏼"), ("Yollanma qotil", "🕴"), ("Zaharchi", "🧑‍🎤"), ("Advokat", "👨🏼‍💼"), ("Jurnalist", "👩🏼‍💻"), ("Savdogar", "🧔🏻‍♂️")]
    selected = []
    mafia_count = max(1, n // 4)
    if n >= 8:
        selected.append(("Don", "🤵🏻"))
    for role in mafia_roles:
        if len([x for x in selected if x in mafia_roles]) >= mafia_count:
            break
        if role not in selected:
            selected.append(role)
    remaining = [r for r in pool if r not in selected]
    random.shuffle(remaining)
    selected.extend(remaining[:max(0, n-len(selected))])
    return selected[:n]


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable topilmadi.")
    init_db()
    load_admins()
    threading.Thread(target=run_health_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()

    # Private menu: faqat asosiy shaxsiy buyruqlar
    private_commands = [
        BotCommand("start", "Botni boshlash"),
        BotCommand("profile", "Profil"),
        BotCommand("roles", "O‘yin rollari"),
        BotCommand("help", "Yordam"),
    ]
    # Guruh menyusi: o‘yin buyruqlari va reytinglar
    group_commands = [
        BotCommand("start", "Botni boshlash"),
        BotCommand("profile", "Profil"),
        BotCommand("roles", "O‘yin rollari"),
        BotCommand("help", "Yordam"),
        BotCommand("lang", "Tilni o‘zgartirish"),
        BotCommand("game", "O‘yin yaratish"),
        BotCommand("vsgame", "Jamoaviy o‘yin"),
        BotCommand("leave", "O‘yindan chiqish"),
        BotCommand("sozlamalar", "O‘yin sozlamalari"),
        BotCommand("giveaway", "Giveaway sozlash"),
        BotCommand("stop", "O‘yinni to‘xtatish"),
        BotCommand("reload", "Guruh ma’lumotlarini yangilash"),
        BotCommand("kurs", "Olmos kursi"),
        BotCommand("para", "Juftlik"),
        BotCommand("newgame", "Yangi o‘yin"),
        BotCommand("join", "O‘yinga qo‘shilish"),
        BotCommand("players", "O‘yinchilar"),
        BotCommand("startgame", "O‘yinni boshlash"),
        BotCommand("night", "Tun vazifasi"),
        BotCommand("vote", "Ovoz berish"),
        BotCommand("endnight", "Tunni tugatish"),
        BotCommand("change", "Tanlov"),
        BotCommand("top", "Oylik TOP"),
        BotCommand("top1", "Bugungi TOP"),
        BotCommand("top7", "7 kunlik TOP"),
    ]

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("roles", roles_cmd))
    app.add_handler(CommandHandler("lang", lang_cmd))
    app.add_handler(CommandHandler("game", game_alias))
    app.add_handler(CommandHandler("vsgame", vsgame_cmd))
    app.add_handler(CommandHandler("leave", leave_cmd))
    app.add_handler(CommandHandler("sozlamalar", settings_cmd))
    app.add_handler(CommandHandler("giveaway", giveaway_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("reload", reload_cmd))
    app.add_handler(CommandHandler("kurs", kurs_cmd))
    app.add_handler(CommandHandler("para", para_cmd))
    # /money menu ichida yo‘q, ammo guruhda reply orqali pul yuborish funksiyasi saqlangan.
    app.add_handler(CommandHandler("money", money_gift))
    app.add_handler(CommandHandler("give", give_diamonds))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CommandHandler("top1", top_cmd))
    app.add_handler(CommandHandler("top7", top_cmd))
    app.add_handler(CommandHandler("send", send_diamonds))
    app.add_handler(CommandHandler("change", change_cmd))
    app.add_handler(CommandHandler("newgame", newgame))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("players", players_cmd))
    app.add_handler(CommandHandler("startgame", startgame))
    app.add_handler(CommandHandler("role", role_cmd))
    app.add_handler(CommandHandler("night", night_cmd))
    app.add_handler(CommandHandler("kill", kill))
    app.add_handler(CommandHandler("heal", heal))
    app.add_handler(CommandHandler("guard", guard))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CommandHandler("shoot", shoot))
    app.add_handler(CommandHandler("silence", silence))
    app.add_handler(CommandHandler("endnight", endnight))
    app.add_handler(CommandHandler("vote", vote))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("adddiamonds", adddiamonds))
    app.add_handler(CommandHandler("addbalance", addbalance))
    app.add_handler(CommandHandler("bankrot1", bankrot))
    app.add_handler(CommandHandler("bankrot2", bankrot))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("makeadmin", makeadmin))
    app.add_handler(CommandHandler("addadmin", makeadmin))
    app.add_handler(CommandHandler("removeadmin", removeadmin))
    app.add_handler(CallbackQueryHandler(
        shop_callback,
        pattern=r"^(shop_diamonds|buydia:\d+|back_profile|gift_diamond|protection_menu|protect:\w+|buyprotect:\w+)$"
    ))
    app.add_handler(CallbackQueryHandler(gift_confirm_callback, pattern=r"^giftconfirm:"))
    app.add_handler(CallbackQueryHandler(change_callback, pattern=r"^change:"))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.COMMAND, track_group_command), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pending_input), group=2)

    async def setup_commands(application):
        await application.bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())
        await application.bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())

    app.post_init = setup_commands
    logger.info("Bot ishga tushmoqda...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
