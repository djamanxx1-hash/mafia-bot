import os, sqlite3, logging, random, threading, html
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats, BotCommandScopeChat, BotCommandScopeDefault, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

# ==================== SOZLAMALAR ====================
TOKEN = os.getenv('BOT_TOKEN', '').strip()
OWNER_ID = int(os.getenv('OWNER_ID', '0'))
PORT = int(os.getenv('PORT', '10000'))
DB_PATH = os.getenv('DB_PATH', 'mafia.db')
MAX_PLAYERS, MIN_PLAYERS = 30, 4
logging.basicConfig(format='%(asctime)s | %(levelname)s | %(name)s | %(message)s', level=logging.INFO)
logger = logging.getLogger('mafia-bot')

# Bitta jarayondagi o'yin holatlari. Har bir guruh alohida saqlanadi.
games = {}
pending = {}
user_game = {}  # foydalanuvchi ID -> o‘yin ketayotgan guruh ID

ROLES = [
    ('Fuqaro','👤'), ('Komissar','🕵️'), ('Doktor','💉'), ('Mafia','🔪'), ('Don','🤵'),
    ('Yollanma qotil','🎯'), ('Advokat','⚖️'), ('Jurnalist','📰'), ('Zaharchi','🧪'),
    ('Ovchi','🏹'), ('Omadli','🍀'), ('Sotqin','🦹'), ('Qaroqchi','🥷'), ('Vampir','🧛'),
    ('Vampir ovchisi','🗡️'), ('Reviver','✨'), ('Konchi','⛏️'), ('Banker','🏦'),
    ('Sehrgar','🪄'), ('Aferist','🎭'), ('Bo‘ri','🐺'), ('Gibrid','🧬'),
    ('Tinch aholi','👨‍🌾'), ('Serjant','🎖️'), ('Tabib','🌿'), ('Daydi','🚶'),
    ('Kezuvchi','🧳'), ('Afsungar','🔮'), ('Voris','👑'), ('Janob','🎩'),
    ('Donishmand','🧠'), ('Suidsid','💣'), ('G‘azabkor','😡'), ('Haqiqiy Vampir','🩸'),
    ('Savdogar','🛍️')]
ROLE_HELP = {
    'Fuqaro':'Kunduz muhokamada qatnashing va ovoz bering.', 'Tinch aholi':'Kunduz muhokamada qatnashing va ovoz bering.',
    'Mafia':'Tunda nishon tanlaydi.', 'Don':'Mafia jamoasining yetakchisi.', 'Komissar':'Tunda o‘yinchini tekshiradi.',
    'Doktor':'Tunda bir o‘yinchini himoya qiladi.', 'Tabib':'Tunda bir o‘yinchini davolashga harakat qiladi.',
    'Yollanma qotil':'Tunda alohida hujum qiladi.', 'Advokat':'O‘yinchini tekshiruvdan yashirishi mumkin.',
    'Jurnalist':'Maxsus ma’lumot to‘plashga mo‘ljallangan rol.', 'Zaharchi':'Tunda nishonga ta’sir qiladi.',
    'Omadli':'Hujumdan omon qolish ehtimoli bor.', 'Sotqin':'Mafia g‘alabasida yutishi mumkin.',
    'Qaroqchi':'O‘yinda maxsus harakat qiladi.', 'Vampir':'Tunda hujum qiladi.', 'Vampir ovchisi':'Vampirlarga qarshi kurashadi.',
    'Reviver':'Bir marta o‘yinchini qaytarish imkoniyati bor.', 'Konchi':'O‘yinda qo‘shimcha mukofot izlaydi.',
    'Banker':'Valyuta bilan bog‘liq bonus rol.', 'Sehrgar':'Maxsus qobiliyatga ega.', 'Aferist':'Raqib harakatiga xalaqit beradi.',
    'Bo‘ri':'Tunda hujum qilishi mumkin.', 'Gibrid':'Maxsus kuchli rol.', 'Serjant':'Komissarga yordam beradi.',
    'Daydi':'Tunda harakatlarni kuzatishi mumkin.', 'Kezuvchi':'Raqib harakatiga xalaqit berishi mumkin.',
    'Afsungar':'O‘ziga xos qarshi ta’sirga ega.', 'Voris':'O‘yinda rol o‘zgarishi mumkin.', 'Janob':'Ovoz berishda maxsus ta’sirga ega.',
    'Donishmand':'Maxfiy ma’lumot to‘plashi mumkin.', 'Suidsid':'Maxsus g‘alaba shartiga ega.', 'G‘azabkor':'Maxsus g‘alaba shartiga ega.',
    'Haqiqiy Vampir':'Vampirlar jamoasining maxsus roli.', 'Savdogar':'O‘yin ichidagi savdo bonuslari.'}

PROTECTIONS = {
    'universal': ('🛡️ Umumiy himoya', '💵 100', 100, 0),
    'vote': ('🗳️ Ovoz himoyasi', '💎 1', 0, 1),
    'fake_doc': ('📁 Soxta hujjat', '💵 190', 190, 0),
    'protect_other': ('🤝 Boshqani himoya qilish', '💎 5', 0, 5),
    'killer': ('🚨 Qotildan himoya', '💎 2', 0, 2),
    'silence': ('🔇 Sukut himoyasi', '💎 1', 0, 1),
    'poison': ('💊 Zahar himoyasi', '💵 100', 100, 0),
    'mask': ('🎭 Maska', '💵 100', 100, 0),
    'slip': ('🥊 Sirpanish himoyasi', '💵 300', 300, 0),
    'hero_protect': ('🦸 Qahramon himoyasi', '💎 5', 0, 5),
    'ricochet': ('🌀 Rikoshet', '💎 3', 0, 3),
    'profile_change': ('🔄 Profil almashtirish', '💎 5', 0, 5),
    'hero': ('🦸 Qahramon', '💎 90', 0, 90),
}

PROTECTION_HELP = {
    'universal': 'Bu himoya egasini bir marta xavfli hujumdan yoki ovoz berish orqali o‘yindan chiqarilishdan saqlash uchun mo‘ljallangan. Himoya mavjud bo‘lsa, undan foydalanish mumkin; ishlatilgach, zaxiradagi soni bittaga kamayadi.',
    'vote': 'Bu himoya kunduzgi ovoz berish natijasida o‘yindan chiqarilish xavfidan saqlash uchun mo‘ljallangan. Ovozlar hisoblanganda himoya bir marta yordam beradi va ishlatilgach zaxiradan kamayadi.',
    'fake_doc': 'Soxta hujjat tekshiruv paytida haqiqiy rolingizni yashirishga yordam beradigan maxsus buyum. U tekshiruvda siz haqingizdagi ma’lumotni chalg‘itish uchun mo‘ljallangan.',
    'protect_other': 'Bu himoya o‘zingizdan boshqa bir o‘yinchini himoya qilish uchun mo‘ljallangan. Kerakli vaziyatda sherigingizni xavfdan asrash imkonini beradi.',
    'killer': 'Qotildan himoya sizni qotilning hujumidan bir marta saqlash uchun mo‘ljallangan. Himoya ishlatilgach, zaxiradagi soni bittaga kamayadi.',
    'silence': 'Sukut himoyasi sizni sukut holatining salbiy ta’siridan asrash uchun mo‘ljallangan. U ovoz berish yoki gapirish imkoniyatiga ta’sir qiladigan sukutdan himoyalanish uchun ishlatiladi.',
    'poison': 'Zahar himoyasi zahar ta’siridan bir marta saqlanish uchun mo‘ljallangan. Zaharli hujumga qarshi kerakli vaziyatda foydalaniladi.',
    'mask': 'Maska sizning shaxsingiz yoki rolingizni boshqalardan yashirishga yordam beradigan buyum. U siz haqingizdagi ma’lumotni aniqlashni qiyinlashtirish uchun mo‘ljallangan.',
    'slip': 'Sirpanish himoyasi xavfli hujumdan qochib qolish imkoniyati uchun mo‘ljallangan. U sizni nishonga olgan hujumdan saqlanishga yordam berishi mumkin.',
    'hero_protect': 'Qahramon himoyasi qahramon rolidagi o‘yinchini hujumdan asrash uchun mo‘ljallangan. Uni qahramonni xavfdan himoya qilish kerak bo‘lgan vaziyatda ishlatish mumkin.',
    'ricochet': 'Rikoshet himoyasi sizga qaratilgan hujumni qaytarish uchun mo‘ljallangan. Himoya hujumga qarshi javob berish imkonini ifodalaydi.',
    'profile_change': 'Profil almashtirish maxsus profilni almashtirish funksiyasidan foydalanish uchun mo‘ljallangan. Xarid qilishdan oldin uning o‘yin ichidagi mavjud imkoniyatlari bilan tanishib chiqing.',
    'hero': 'Qahramon buyumi qahramon bilan bog‘liq maxsus imkoniyatni ochish uchun mo‘ljallangan. U himoya buyumlaridan alohida hisoblanadi.',
}
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b'OK')
    def do_HEAD(self):
        self.send_response(200); self.end_headers()
    def log_message(self, *_): pass

def health_server():
    HTTPServer(('0.0.0.0', PORT), HealthHandler).serve_forever()

def db():
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA busy_timeout=20000')
    return con

def init_db():
    with db() as con:
        con.execute('PRAGMA journal_mode=WAL')
        con.execute('''CREATE TABLE IF NOT EXISTS players(
            user_id INTEGER PRIMARY KEY, name TEXT DEFAULT '', username TEXT DEFAULT '',
            diamonds INTEGER DEFAULT 0, money INTEGER DEFAULT 0, dollars INTEGER DEFAULT 0,
            games INTEGER DEFAULT 0, wins INTEGER DEFAULT 0, points INTEGER DEFAULT 0, banned INTEGER DEFAULT 0)''')
        con.execute('CREATE TABLE IF NOT EXISTS admins(user_id INTEGER PRIMARY KEY)')
        con.execute('CREATE TABLE IF NOT EXISTS group_members(chat_id INTEGER, user_id INTEGER, PRIMARY KEY(chat_id,user_id))')
        con.execute('CREATE TABLE IF NOT EXISTS protections(user_id INTEGER, item TEXT, amount INTEGER DEFAULT 0, PRIMARY KEY(user_id,item))')
        con.execute('CREATE TABLE IF NOT EXISTS pairs(user_id INTEGER PRIMARY KEY, partner_id INTEGER NOT NULL)')
        con.execute('''CREATE TABLE IF NOT EXISTS pair_requests(
            requester_id INTEGER NOT NULL, target_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
            created_at INTEGER NOT NULL, PRIMARY KEY(requester_id,target_id))''')
        # PRO muddati: Unix timestamp. 0 bo‘lsa faol PRO yo‘q.
        try:
            con.execute('ALTER TABLE players ADD COLUMN pro_until INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        if OWNER_ID:
            con.execute('INSERT OR IGNORE INTO admins(user_id) VALUES(?)', (OWNER_ID,))

def get_player(uid, user=None):
    with db() as con:
        row = con.execute('SELECT * FROM players WHERE user_id=?', (uid,)).fetchone()
        if not row:
            name = (getattr(user, 'full_name', '') if user else '') or 'Noma’lum'
            username = (getattr(user, 'username', '') if user else '') or ''
            con.execute('INSERT OR IGNORE INTO players(user_id,name,username) VALUES(?,?,?)', (uid, name, username))
            row = con.execute('SELECT * FROM players WHERE user_id=?', (uid,)).fetchone()
        elif user:
            con.execute('UPDATE players SET name=?,username=? WHERE user_id=?', (user.full_name or 'Noma’lum', user.username or '', uid))
            row = con.execute('SELECT * FROM players WHERE user_id=?', (uid,)).fetchone()
        return dict(row)

def save_player(uid, **fields):
    allowed = {'diamonds','money','dollars','games','wins','points','banned','name','username'}
    fields = {k:v for k,v in fields.items() if k in allowed}
    if not fields: return
    sql = ','.join(f'{k}=?' for k in fields)
    with db() as con: con.execute(f'UPDATE players SET {sql} WHERE user_id=?', (*fields.values(), uid))

def add_protection(uid, key, amount=1):
    with db() as con:
        con.execute('INSERT INTO protections(user_id,item,amount) VALUES(?,?,?) ON CONFLICT(user_id,item) DO UPDATE SET amount=MAX(0,amount+excluded.amount)', (uid,key,amount))

def protection_count(uid, key):
    with db() as con:
        row = con.execute('SELECT amount FROM protections WHERE user_id=? AND item=?', (uid,key)).fetchone()
        return int(row['amount']) if row else 0

def is_pro(uid):
    # PRO ustuni eski bazaga ham init_db() orqali qo‘shiladi.
    with db() as con:
        row = con.execute('SELECT pro_until FROM players WHERE user_id=?', (uid,)).fetchone()
        return bool(row and int(row['pro_until'] or 0) > int(datetime.now().timestamp()))

def lobby_text(g):
    # Niklar bitta matn qatorida beriladi; Telegram ekran kengligiga qarab o‘zi o‘raydi.
    names = []
    for player in g['players'].values():
        nick = escape(player.get('name', 'O‘yinchi'))
        if is_pro(player['id']):
            names.append(f'<b>{nick}</b> <b>PRO</b>')
        else:
            names.append(f'<b>{nick}</b>')
    roster = '  ·  '.join(names) if names else 'Hali hech kim qo‘shilmadi.'
    return ('🎭 <b>YANGI MAFIYA O‘YINI</b>\n\n'
            f'👥 {roster}\n\n'
            'O‘yinga kirish uchun quyidagi tugmani bosing.')

def is_owner(uid): return uid == OWNER_ID and OWNER_ID != 0
def is_admin(uid):
    if is_owner(uid): return True
    with db() as con: return con.execute('SELECT 1 FROM admins WHERE user_id=?', (uid,)).fetchone() is not None

def track(update):
    u = update.effective_user; c = update.effective_chat
    if not u: return
    get_player(u.id, u)
    if c and c.type in ('group','supergroup'):
        with db() as con: con.execute('INSERT OR IGNORE INTO group_members(chat_id,user_id) VALUES(?,?)', (c.id,u.id))

def allowed(update):
    u = update.effective_user
    if not u: return False
    p = get_player(u.id,u)
    if p['banned']:
        return False
    return True

def escape(s): return html.escape(str(s or ''))
def money_text(p):
    return (f"👤 Ism: <b>{escape(p['name'])}</b>\n🆔 ID: <code>{p['user_id']}</code>\n"
            f"🔗 Username: @{escape(p['username']) if p['username'] else 'yo‘q'}\n\n"
            f"💰 Pul: <b>{p['money']:,}</b>\n💎 Olmos: <b>{p['diamonds']:,}</b>\n"
            f"💵 Dollar: <b>{p['dollars']:,}</b>\n⭐ Ball: <b>{p['points']:,}</b>\n"
            f"🎮 O‘yinlar: <b>{p['games']}</b>\n🏆 G‘alabalar: <b>{p['wins']}</b>")

def profile_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('💎 Olmos sotib olish', callback_data='shop')],
        [InlineKeyboardButton('🎁 Olmos yuborish', callback_data='gift'), InlineKeyboardButton('🛡️ Himoya markazi', callback_data='protections')],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    welcome = (
        '👋 <b>𝐒𝐚𝐥𝐨𝐦! 𝐌𝐚𝐟𝐢𝐲𝐚 𝐨𝐥𝐚𝐦𝐢𝐠𝐚 𝐇𝐮𝐬𝐡 𝐤𝐞𝐥𝐢𝐛𝐬𝐚𝐧!</b>\n\n'
        '𝐁𝐮 𝐨𝐝𝐝𝐢𝐲 𝐨ʻ𝐲𝐢𝐧 𝐞𝐦𝐚𝐬 — 𝐬𝐢𝐫𝐥𝐢 𝐣𝐚𝐦𝐨𝐚, 𝐢𝐬𝐡𝐨𝐧𝐜𝐡 𝐯𝐚 𝐡𝐚𝐦𝐦𝐚𝐧𝐢 𝐬𝐢𝐧𝐨𝐯𝐝𝐚𝐧 𝐨ʻ𝐭𝐤𝐚𝐳𝐚𝐝𝐢𝐠𝐚𝐧 𝐨ʻ𝐲𝐢𝐧! 🕵️‍♂️\n'
        '𝐎ʻ𝐲𝐢𝐧𝐠𝐚 𝐤𝐢𝐫, 𝐫𝐨𝐥𝐢𝐧𝐠𝐧𝐢 𝐨𝐥, 𝐨ʻ𝐳𝐢𝐧𝐠𝐧𝐢 𝐤𝐨ʻ𝐫𝐬𝐚𝐭! 🎯\n\n'
        '🎭 <b>𝐒𝐞𝐧𝐢𝐧𝐠 𝐫𝐨𝐥𝐢𝐧𝐠 𝐤𝐮𝐭𝐦𝐨𝐪𝐝𝐚...</b>\n'
        '🔪 Mafia orasida yashirinib qolasanmi yoki 🕵️‍♂️ shaharni qutqarasanmi? Buni faqat o‘yin ko‘rsatadi!\n\n'
        '🤝 Do‘stlaringni guruhga yig‘, yangi o‘yin och va kimning kimligini topishga harakat qil.\n'
        '⚡ Har bir ovoz muhim. Har bir tun xavfli. Ishonch esa eng katta qurol!\n\n'
        '🎮 <b>BOSHLASH UCHUN:</b> botni guruhga qo‘shing va guruhda /game yuboring.\n'
        '👤 Profil: /profile  |  🎭 Rollar: /roles  |  📚 Yordam: /help\n\n'
        '🩸 <i>Shubha qil. Kuzat. Ovoz ber. G‘alaba qozon!</i>'
    )
    await update.effective_message.reply_text(welcome, parse_mode='HTML')

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    await update.effective_message.reply_text('📚 <b>BUYRUQLAR</b>\n\nShaxsiy: /start /profile /roles /help\nGuruh: /game /players /startgame /leave /roles /role /night /kill /heal /check /vote /endnight /top /top1 /top7\nPul yuborish: javob qilib /money 5000\nOlmos yuborish: javob qilib /give 2', parse_mode='HTML')

async def delete_command_message(msg):
    """Guruhdagi buyruq xabarini o'chirish; botga admin huquqi kerak bo'lishi mumkin."""
    try:
        if msg and msg.chat and msg.chat.type in ("group", "supergroup"):
            await msg.delete()
            return True
    except Exception as exc:
        logger.info("Buyruq xabarini o'chirib bo'lmadi: %s", exc)
    return False

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    u = update.effective_user
    msg = update.effective_message
    chat = update.effective_chat
    in_group = bool(chat and chat.type in ('group', 'supergroup'))

    # Guruhda oddiy o'yinchining profili ommaga chiqarilmaydi: o'z bot chatiga yuboriladi.
    if in_group and not is_admin(u.id):
        await delete_command_message(msg)
        p = get_player(u.id, u)
        try:
            await context.bot.send_message(u.id, '👤 <b>PROFIL</b>\n\n' + money_text(p),
                                           parse_mode='HTML', reply_markup=profile_keyboard())
        except Exception:
            await context.bot.send_message(chat_id=chat.id, text='👤 Profilni ko‘rish uchun avval botning shaxsiy chatida /start bosing.')
        return

    target = u
    if in_group:
        if msg.reply_to_message and msg.reply_to_message.from_user:
            target = msg.reply_to_message.from_user
        elif context.args and context.args[0].isdigit():
            target = None
            p = get_player(int(context.args[0]))
            await msg.reply_text('📋 <b>FOYDALANUVCHI PROFILI</b>\n\n' + money_text(p), parse_mode='HTML')
            return
        else:
            await delete_command_message(msg)
            return await context.bot.send_message(chat_id=chat.id, text='Admin uchun: o‘yinchi xabariga reply qilib /profile yozing yoki /profile ID.')
    elif context.args and is_admin(u.id) and context.args[0].isdigit():
        p = get_player(int(context.args[0]))
        return await msg.reply_text('📋 <b>FOYDALANUVCHI PROFILI</b>\n\n' + money_text(p), parse_mode='HTML')

    p = get_player(target.id, target)
    await msg.reply_text('👤 <b>PROFIL</b>\n\n' + money_text(p), parse_mode='HTML',
                         reply_markup=profile_keyboard() if target.id == u.id else None)

async def roles_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    lines = ['🎭 <b>MAFIA BOT — ROLLAR</b>', '']
    for role, icon in ROLES: lines.append(f'{icon} <b>{escape(role)}</b> — {escape(ROLE_HELP.get(role, "Maxsus rol."))}')
    # Telegram xabar chegarasidan oshmasligi uchun bo'lib yuboramiz.
    text = '\n'.join(lines)
    for i in range(0, len(text), 3500): await update.effective_message.reply_text(text[i:i+3500], parse_mode='HTML')

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    # Juftlik so‘rovlarini umumiy callbackdan oldin boshqaramiz.
    if q.data.startswith(('pair_accept:', 'pair_decline:', 'pair_profile:')):
        return await pair_callback(update, context)
    if not q.data.startswith('join_game:'):
        await q.answer()
    if not allowed(update): return
    uid = q.from_user.id
    if q.data.startswith('join_game:'):
        try: chat_id = int(q.data.split(':', 1)[1])
        except (ValueError, IndexError): return await q.answer('Tugma noto‘g‘ri.', show_alert=True)
        if q.message is None or q.message.chat.id != chat_id:
            return await q.answer('Bu tugma boshqa guruh uchun.', show_alert=True)
        g = game_for(chat_id)
        if g.get('lobby_message_id') != q.message.message_id:
            return await q.answer('Bu o‘yin e’loni eskirgan. Yangi o‘yin oching.', show_alert=True)
        if g['started'] or g.get('phase') != 'lobby':
            return await q.answer('O‘yin boshlangan, qo‘shilish yopiq.', show_alert=True)
        u = q.from_user
        if u.id in g['players']:
            return await q.answer('Siz allaqachon ro‘yxatdasiz.', show_alert=True)
        if len(g['players']) >= MAX_PLAYERS:
            return await q.answer('O‘yinchilar soni 30 taga yetdi.', show_alert=True)
        get_player(u.id, u)
        g['players'][u.id] = {'id': u.id, 'name': u.full_name, 'alive': True}
        with db() as con:
            con.execute('INSERT OR IGNORE INTO group_members(chat_id,user_id) VALUES(?,?)', (chat_id, u.id))
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton('➕ Qo‘shilish', callback_data=f'join_game:{chat_id}')]])
        try:
            await q.edit_message_text(lobby_text(g), parse_mode='HTML', reply_markup=keyboard)
        except Exception as e:
            logger.warning('Lobby xabarini yangilab bo‘lmadi: %s', e)
        return await q.answer('✅ O‘yinga qo‘shildingiz!')
    if q.data == 'back_profile':
        p=get_player(uid,q.from_user); return await q.edit_message_text('👤 <b>PROFIL</b>\n\n'+money_text(p),parse_mode='HTML',reply_markup=profile_keyboard())
    if q.data == 'shop':
        return await q.edit_message_text('💎 <b>OLMOS DO‘KONI</b>\n\n1 olmos = 500 pul\n5 olmos = 2500 pul\n10 olmos = 5000 pul\n20 olmos = 10000 pul',parse_mode='HTML',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('💎 1',callback_data='buydia:1'),InlineKeyboardButton('💎 5',callback_data='buydia:5')],[InlineKeyboardButton('💎 10',callback_data='buydia:10'),InlineKeyboardButton('💎 20',callback_data='buydia:20')],[InlineKeyboardButton('⬅️ Profil',callback_data='back_profile')]]))
    if q.data.startswith('buydia:'):
        amount=int(q.data.split(':')[1]); p=get_player(uid,q.from_user); cost=amount*500
        if p['money']<cost: return await q.edit_message_text('❌ Pul yetarli emas.',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⬅️ Profil',callback_data='back_profile')]]))
        save_player(uid,money=p['money']-cost,diamonds=p['diamonds']+amount); p=get_player(uid,q.from_user)
        return await q.edit_message_text(f'✅ {amount} olmos xarid qilindi.\n\n'+money_text(p),parse_mode='HTML',reply_markup=profile_keyboard())
    if q.data == 'protections':
        rows=[]
        for key,(name,price,money_cost,diamond_cost) in PROTECTIONS.items(): rows.append([InlineKeyboardButton(f'{name} — {price}',callback_data='protect:'+key)])
        rows.append([InlineKeyboardButton('⬅️ Profil',callback_data='back_profile')])
        return await q.edit_message_text('🛡️ <b>HIMOYA MARKAZI</b>\nKerakli himoyani tanlang:',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(rows))
    if q.data.startswith('protect:'):
        key=q.data.split(':',1)[1]
        if key not in PROTECTIONS: return
        name,price,mc,dc=PROTECTIONS[key]
        description=PROTECTION_HELP.get(key, 'Ushbu himoya o‘yin davomida maxsus imkoniyat beradi.')
        text=f'{name}\n\n📖 <b>Vazifasi:</b> {description}\n\n💰 <b>Narxi:</b> {price}'
        return await q.edit_message_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f'{name} — {price}',callback_data='buyprotect:'+key)],
            [InlineKeyboardButton('⬅️ Boshqa himoyalar',callback_data='protections')],
            [InlineKeyboardButton('👤 Profil',callback_data='back_profile')]
        ]))
    if q.data.startswith('buyprotect:'):
        key=q.data.split(':',1)[1]
        if key not in PROTECTIONS: return
        name,price,mc,dc=PROTECTIONS[key]
        p=get_player(uid,q.from_user)
        if p['money']<mc or p['diamonds']<dc:
            return await q.answer('Balans yetarli emas.',show_alert=True)
        save_player(uid,money=p['money']-mc,diamonds=p['diamonds']-dc)
        add_protection(uid,key,1)
        return await q.edit_message_text(f'✅ Xarid qilindi: {name}\nNarxi: {price}',parse_mode='HTML',reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton('⬅️ Himoya markazi',callback_data='protections')],
            [InlineKeyboardButton('👤 Profil',callback_data='back_profile')]
        ]))
    if q.data == 'gift':
        pending[uid]={'type':'gift'}
        return await q.edit_message_text('🎁 Olmos yuborish uchun guruhda qabul qiluvchining xabariga reply qilib /give MIQDOR yozing.\nMasalan: /give 2',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⬅️ Profil',callback_data='back_profile')]]))

async def money_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    msg=update.effective_message
    if not msg.reply_to_message: return await msg.reply_text('Pul yuborish uchun odamning xabariga reply qiling: /money 5000')
    if not context.args or not context.args[0].isdigit(): return await msg.reply_text('Misol: /money 5000')
    amount=int(context.args[0]); sender=update.effective_user; target=msg.reply_to_message.from_user
    if amount<=0: return await msg.reply_text('Miqdor 0 dan katta bo‘lsin.')
    a=get_player(sender.id,sender); b=get_player(target.id,target)
    if a['money']<amount: return await msg.reply_text('❌ Pulingiz yetarli emas.')
    save_player(sender.id,money=a['money']-amount); save_player(target.id,money=b['money']+amount)
    await msg.reply_text(f'✅ {escape(sender.full_name)} → {escape(target.full_name)}\n💰 Yuborildi: {amount:,} pul',parse_mode='HTML')

async def give_diamonds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    msg=update.effective_message
    if not msg.reply_to_message: return await msg.reply_text('Olmos yuborish uchun odamning xabariga reply qiling: /give 2')
    if not context.args or not context.args[0].isdigit(): return await msg.reply_text('Misol: /give 2')
    amount=int(context.args[0]); a=get_player(update.effective_user.id,update.effective_user); target=msg.reply_to_message.from_user; b=get_player(target.id,target)
    if amount<=0: return await msg.reply_text('Miqdor 0 dan katta bo‘lsin.')
    if a['diamonds']<amount: return await msg.reply_text('❌ Olmos yetarli emas.')
    save_player(update.effective_user.id,diamonds=a['diamonds']-amount); save_player(target.id,diamonds=b['diamonds']+amount)
    await msg.reply_text(f'✅ {escape(update.effective_user.full_name)} → {escape(target.full_name)}\n💎 Yuborildi: {amount}',parse_mode='HTML')

async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    if update.effective_chat.type not in ('group','supergroup'): return await update.effective_message.reply_text('TOP buyruqlari guruhda ishlaydi.')
    cmd=update.effective_message.text.split()[0].split('@')[0]
    days=1 if cmd=='/top1' else 7 if cmd=='/top7' else 30
    with db() as con:
        rows=con.execute('SELECT user_id,name,points,wins FROM players ORDER BY points DESC,wins DESC LIMIT 10').fetchall()
    lines=[f'🏆 <b>TOP — {"bugun" if days==1 else "7 kun" if days==7 else "umumiy reyting"}</b>','']
    for i,r in enumerate(rows,1): lines.append(f'{i}. {escape(r["name"])} — ⭐ {r["points"]} | 🏆 {r["wins"]}')
    await update.effective_message.reply_text('\n'.join(lines),parse_mode='HTML')

async def para_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    msg = update.effective_message
    chat = update.effective_chat
    if not chat or chat.type not in ('group', 'supergroup'):
        return await msg.reply_text('❤️ Juftlik so‘rovini guruhda, odamning xabariga reply qilib yuboring: /para')
    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        await delete_command_message(msg)
        return await context.bot.send_message(chat_id=chat.id, text='💌 Juftlik so‘rovi yuborish uchun o‘yinchining xabariga reply qilib /para yozing.')

    sender = update.effective_user
    target = msg.reply_to_message.from_user
    await delete_command_message(msg)
    if target.is_bot:
        return await context.bot.send_message(chat_id=chat.id, text='🤖 Bot bilan juft bo‘lib bo‘lmaydi.')
    if sender.id == target.id:
        return await context.bot.send_message(chat_id=chat.id, text='😊 O‘zingizga juftlik so‘rovi yubora olmaysiz.')

    get_player(sender.id, sender)
    get_player(target.id, target)
    with db() as con:
        a = con.execute('SELECT partner_id FROM pairs WHERE user_id=?', (sender.id,)).fetchone()
        b = con.execute('SELECT partner_id FROM pairs WHERE user_id=?', (target.id,)).fetchone()
        if a:
            return await context.bot.send_message(chat_id=chat.id, text='❤️ Sizning juftingiz allaqachon bor. Avvalgi juftlikni o‘zgartirish uchun admin yordamiga murojaat qiling.')
        if b:
            return await context.bot.send_message(chat_id=chat.id, text='💔 Bu o‘yinchining allaqachon jufti bor.')
        existing = con.execute('SELECT 1 FROM pair_requests WHERE requester_id=? AND target_id=?', (sender.id, target.id)).fetchone()
        if existing:
            return await context.bot.send_message(chat_id=chat.id, text='💌 Bu o‘yinchiga so‘rov allaqachon yuborilgan.')
        con.execute('INSERT INTO pair_requests(requester_id,target_id,chat_id,created_at) VALUES(?,?,?,?)',
                    (sender.id, target.id, chat.id, int(datetime.now().timestamp())))

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton('💚 Qabul qilish', callback_data=f'pair_accept:{sender.id}:{target.id}'),
        InlineKeyboardButton('❌ Rad etish', callback_data=f'pair_decline:{sender.id}:{target.id}')
    ]])
    sender_link = f'<a href="tg://user?id={sender.id}">{escape(sender.full_name)}</a>'
    target_link = f'<a href="tg://user?id={target.id}">{escape(target.full_name)}</a>'
    request_text = (
        f'💌 <b>JUFTLIK SO‘ROVI</b>\n\n{sender_link} siz bilan juft bo‘lishni xohlaydi! ❤️\n\n'
        'Birgalikda Mafia olamida o‘z hikoyangizni boshlaysizmi?\n'
        'Qaroringizni quyidagi tugmalardan biri orqali bildiring. ✨'
    )
    try:
        await context.bot.send_message(target.id, request_text, parse_mode='HTML', reply_markup=keyboard)
    except Exception:
        with db() as con:
            con.execute('DELETE FROM pair_requests WHERE requester_id=? AND target_id=?', (sender.id, target.id))
        return await context.bot.send_message(chat_id=chat.id, text=
            f'💌 <a href="tg://user?id={sender.id}">{escape(sender.full_name)}</a> juftlik so‘rovini yubormoqchi, '
            f'lekin <a href="tg://user?id={target.id}">{escape(target.full_name)}</a> avval botga shaxsiy chatda /start yuborishi kerak.',
            parse_mode='HTML')

    # So‘rov shaxsiy chatga yuboriladi; guruhda 'so‘rov yubordi' degan xabar chiqmaydi.
    return

async def mypara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    msg = update.effective_message
    if update.effective_chat and update.effective_chat.type in ('group', 'supergroup'):
        await delete_command_message(msg)
    u = update.effective_user
    with db() as con:
        row = con.execute('SELECT partner_id FROM pairs WHERE user_id=?', (u.id,)).fetchone()
    if not row:
        text = '💔 Sizda hozircha juft yo‘q. Guruhda o‘yinchining xabariga reply qilib /para yozib, so‘rov yuborishingiz mumkin.'
        if update.effective_chat and update.effective_chat.type in ('group', 'supergroup'):
            return await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        return await msg.reply_text(text)
    partner = get_player(int(row['partner_id']))
    own = get_player(u.id, u)
    own_name = escape(own.get('name') or u.full_name or 'Siz')
    partner_name = escape(partner.get('name') or 'Juftingiz')
    own_link = f'<a href="tg://user?id={u.id}">{own_name}</a>'
    partner_link = f'<a href="tg://user?id={partner["user_id"]}">{partner_name}</a>'
    # Matn saqlanadi; faqat ikkala juftning niki metka qilinadi. Profil tugmasi olib tashlandi.
    text = (f'❤️ <b>SENING JUFTING</b> ❤️\n\n💞 Juftingiz: {own_link} | {partner_link}\n\n'
            'Bir-biringizni asrang va Mafia olamida birga porlang! ✨')
    if update.effective_chat and update.effective_chat.type in ('group', 'supergroup'):
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode='HTML')
    else:
        await msg.reply_text(text, parse_mode='HTML')

async def dpara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    msg = update.effective_message
    uid = update.effective_user.id
    chat = update.effective_chat
    if chat and chat.type in ('group', 'supergroup'):
        await delete_command_message(msg)
    with db() as con:
        pair = con.execute('SELECT partner_id FROM pairs WHERE user_id=?', (uid,)).fetchone()
        if pair:
            partner_id = int(pair['partner_id'])
            con.execute('DELETE FROM pairs WHERE user_id=? OR partner_id=?', (uid, uid))
        else:
            partner_id = None
        # Ajralish bilan birga kutilayotgan juftlik so‘rovlari ham bekor bo‘ladi.
        con.execute('DELETE FROM pair_requests WHERE requester_id=? OR target_id=?', (uid, uid))
    if not partner_id:
        text = '💔 Siz hozir hech kim bilan juft emassiz. Ba’zan aytilmagan hislar ham og‘riydi… 🥀'
    else:
        partner = get_player(partner_id)
        partner_name = escape(partner.get('name') or 'juftingiz')
        text = (f'💔 <b>JUFTLIK YAKUNLANDI</b>\n\n'
                f'❤️‍🩹 Siz va <a href="tg://user?id={partner_id}">{partner_name}</a> endi juft emassiz.\n\n'
                '“Ba’zi insonlar qalbimizda qoladi, ammo yonimizda qololmaydi…” 🥀\n\n'
                'Har kim o‘z yo‘lidan davom etadi. O‘zingizni asrang. 🕊️')
        try:
            await context.bot.send_message(chat_id=partner_id,
                text='💔 Juftingiz siz bilan juftlikni yakunladi.\n\n'
                     '“Ba’zi insonlar qalbimizda qoladi, ammo yonimizda qololmaydi…” 🥀')
        except Exception:
            pass
    if chat and chat.type in ('group', 'supergroup'):
        await context.bot.send_message(chat_id=chat.id, text=text, parse_mode='HTML')
    else:
        await msg.reply_text(text, parse_mode='HTML')

async def pair_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data or ''
    uid = q.from_user.id
    if not allowed(update):
        return await q.answer('Sizda bu amalni bajarish huquqi yo‘q.', show_alert=True)
    if data.startswith('pair_profile:'):
        try: partner_id = int(data.split(':', 1)[1])
        except (ValueError, IndexError): return await q.answer('Profil topilmadi.', show_alert=True)
        with db() as con:
            pair = con.execute('SELECT partner_id FROM pairs WHERE user_id=?', (uid,)).fetchone()
        if not pair or int(pair['partner_id']) != partner_id:
            return await q.answer('Bu profil faqat juftingiz uchun mavjud.', show_alert=True)
        p = get_player(partner_id)
        await q.answer()
        return await q.message.reply_text('👤 <b>JUFTINGIZ PROFILI</b>\n\n' + money_text(p), parse_mode='HTML')
    try:
        action, requester_id, target_id = data.split(':')
        requester_id, target_id = int(requester_id), int(target_id)
    except (ValueError, IndexError):
        return await q.answer('So‘rov noto‘g‘ri.', show_alert=True)
    if uid != target_id:
        return await q.answer('Bu so‘rov boshqa o‘yinchiga yuborilgan.', show_alert=True)
    with db() as con:
        request = con.execute('SELECT chat_id FROM pair_requests WHERE requester_id=? AND target_id=?',
                              (requester_id, target_id)).fetchone()
        if not request:
            return await q.answer('Bu so‘rov bekor qilingan yoki avval javob berilgan.', show_alert=True)
        if action == 'pair_decline':
            con.execute('DELETE FROM pair_requests WHERE requester_id=? AND target_id=?', (requester_id, target_id))
        elif action == 'pair_accept':
            a = con.execute('SELECT partner_id FROM pairs WHERE user_id=?', (requester_id,)).fetchone()
            b = con.execute('SELECT partner_id FROM pairs WHERE user_id=?', (target_id,)).fetchone()
            if a or b:
                con.execute('DELETE FROM pair_requests WHERE requester_id=? AND target_id=?', (requester_id, target_id))
                return await q.answer('Sizlardan biringizning allaqachon jufti bor.', show_alert=True)
            con.execute('INSERT INTO pairs(user_id,partner_id) VALUES(?,?)', (requester_id, target_id))
            con.execute('INSERT INTO pairs(user_id,partner_id) VALUES(?,?)', (target_id, requester_id))
            con.execute('DELETE FROM pair_requests WHERE requester_id=? AND target_id=?', (requester_id, target_id))
    await q.answer('❤️ Juftlik so‘rovi qabul qilindi!' if action == 'pair_accept' else 'So‘rov rad etildi.')
    if action == 'pair_accept':
        requester = get_player(requester_id)
        target = get_player(target_id, q.from_user)
        text = (f'💞 <b>YANGI JUFTLIK!</b> ❤️\n\n'
                f'<a href="tg://user?id={requester_id}">{escape(requester["name"])}</a> '
                f'❤️ <a href="tg://user?id={target_id}">{escape(target["name"])}</a>\n\n'
                'Tabriklaymiz! Mafia olamida bir-biringizga omad tilaymiz! ✨')
        try:
            await q.edit_message_text(text, parse_mode='HTML')
        except Exception:
            await q.message.reply_text(text, parse_mode='HTML')
    else:
        try:
            await q.edit_message_text('💔 <b>Juftlik so‘rovi rad etildi.</b>\nYaxshi niyat uchun rahmat. ❤️', parse_mode='HTML')
        except Exception:
            pass

# ==================== O'YIN ====================
def game_for(chat_id):
    return games.setdefault(chat_id, {'players':{},'started':False,'phase':'lobby','votes':{},'actions':{},'silenced':set()})

def active_game(update):
    chat = update.effective_chat
    if chat and chat.type in ('group','supergroup'):
        return chat.id, game_for(chat.id)
    gid = user_game.get(update.effective_user.id)
    return (gid, game_for(gid)) if gid is not None else (None, None)
def player_number(g, n):
    alive_or_all=list(g['players'].values())
    return alive_or_all[n-1] if 1<=n<=len(alive_or_all) else None

def player_list(g):
    return list(g['players'].values())

async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    chat=update.effective_chat
    if chat.type not in ('group','supergroup'): return await update.effective_message.reply_text('Yangi o‘yinni guruhda oching.')
    g=game_for(chat.id)
    if g['started']: return await update.effective_message.reply_text('❌ Hozir o‘yin davom etmoqda.')
    g.update(players={},started=False,phase='lobby',votes={},actions={},silenced=set(),lobby_message_id=None)
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton('➕ Qo‘shilish', callback_data=f'join_game:{chat.id}')]])
    sent = await update.effective_message.reply_text(
        lobby_text(g), parse_mode='HTML', reply_markup=keyboard)
    g['lobby_message_id'] = sent.message_id

async def players_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    g=game_for(update.effective_chat.id); ps=player_list(g)
    if not ps: return await update.effective_message.reply_text('Hozircha o‘yinchilar yo‘q. /game')
    lines=['👥 <b>O‘YINCHILAR</b>','']
    for i,p in enumerate(ps,1): lines.append(f'{i}. {"🟢" if p.get("alive",True) else "💀"} {escape(p["name"])}')
    await update.effective_message.reply_text('\n'.join(lines),parse_mode='HTML')

async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    chat=update.effective_chat; g=game_for(chat.id)
    if not is_admin(update.effective_user.id): return await update.effective_message.reply_text('🔒 O‘yinni faqat bot admini boshlashi mumkin.')
    if g['started']: return await update.effective_message.reply_text('O‘yin boshlangan.')
    ps=player_list(g)
    if len(ps)<MIN_PLAYERS: return await update.effective_message.reply_text('Kamida 4 o‘yinchi kerak.')
    random.shuffle(ps); mafia_count=max(1,len(ps)//4)
    roles=['Don']+['Mafia']*(mafia_count-1)+['Komissar','Doktor']
    roles=(roles+['Fuqaro']*len(ps))[:len(ps)]; random.shuffle(roles)
    for p,role in zip(ps,roles):
        p.update(role=role,alive=True)
        user_game[p['id']] = chat.id
    g.update(started=True,phase='night',votes={},actions={},silenced=set())
    for p in ps:
        try: await context.bot.send_message(p['id'],f'🎭 Sizning rolingiz: <b>{escape(p["role"])}</b>\n{escape(ROLE_HELP.get(p["role"],"Maxsus rol."))}',parse_mode='HTML')
        except Exception: pass
    for p in ps:
        pp=get_player(p['id']); save_player(p['id'],games=pp['games']+1)
    await update.effective_message.reply_text('🌙 <b>O‘YIN BOSHLANDI!</b> Rollar shaxsiy xabarda yuborildi. Tungi vazifa uchun botga /night yozing.',parse_mode='HTML')

async def role_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    gid,g=active_game(update)
    p=g['players'].get(update.effective_user.id) if g else None
    if not g or not g['started'] or not p: return await update.effective_message.reply_text('Siz faol o‘yinda emassiz.')
    await update.effective_message.reply_text(f'🎭 Sizning rolingiz: <b>{escape(p.get("role",""))}</b>',parse_mode='HTML')

async def night_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    gid,g=active_game(update); p=g['players'].get(update.effective_user.id) if g else None
    if not g or not g['started'] or g['phase']!='night': return await update.effective_message.reply_text('Hozir tun bosqichi emas.')
    if not p or not p['alive']: return await update.effective_message.reply_text('Siz faol tirik o‘yinchi emassiz.')
    await update.effective_message.reply_text(f'🌙 <b>TUNGI VAZIFA</b>\n{escape(ROLE_HELP.get(p.get("role"),"Maxsus vazifa."))}\n\nNishon tanlash: /kill RAQAM (Mafia/Don), /heal RAQAM (Doktor), /check RAQAM (Komissar).',parse_mode='HTML')

def target_from(g, args):
    if not args or not args[0].isdigit(): return None
    return player_number(g,int(args[0]))

async def night_action(update, context, kind, allowed_roles):
    if not allowed(update): return
    chat=update.effective_chat; gid,g=active_game(update); uid=update.effective_user.id; p=g['players'].get(uid) if g else None
    if not g or not g['started'] or g['phase']!='night': return await update.effective_message.reply_text('Hozir tun bosqichi emas.')
    if not p or not p['alive'] or p.get('role') not in allowed_roles: return await update.effective_message.reply_text('Bu harakat sizning rolingizga tegishli emas.')
    t=target_from(g,context.args)
    if not t or not t.get('alive'): return await update.effective_message.reply_text('Nishon raqami noto‘g‘ri. /players orqali ko‘ring.')
    if t['id']==uid and kind not in ('heal',): return await update.effective_message.reply_text('O‘zingizni tanlay olmaysiz.')
    if kind=='check': return await update.effective_message.reply_text(f'🔍 {escape(t["name"])} roli: <b>{escape(t.get("role","Noma’lum"))}</b>',parse_mode='HTML')
    g['actions'][uid]={'type':kind,'target':t['id'],'role':p.get('role')}
    await update.effective_message.reply_text(f'✅ Nishon tanlandi: {escape(t["name"])}',parse_mode='HTML')

async def kill_cmd(u,c): await night_action(u,c,'kill',('Mafia','Don','Yollanma qotil','Bo‘ri','Vampir'))
async def heal_cmd(u,c): await night_action(u,c,'heal',('Doktor','Tabib'))
async def check_cmd(u,c): await night_action(u,c,'check',('Komissar','Serjant','Jurnalist','Ovchi'))

async def endnight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    chat=update.effective_chat; g=game_for(chat.id)
    if not is_admin(update.effective_user.id): return await update.effective_message.reply_text('🔒 Faqat admin.')
    if not g['started'] or g['phase']!='night': return await update.effective_message.reply_text('Hozir tun emas.')
    heals={a['target'] for a in g['actions'].values() if a['type']=='heal'}
    kills=[a['target'] for a in g['actions'].values() if a['type']=='kill']
    dead=[]
    for uid in kills:
        p=g['players'].get(uid)
        if p and p['alive'] and uid not in heals:
            p['alive']=False; dead.append(p['name'])
    g['actions']={}; g['phase']='day'
    msg='☀️ <b>KUN BOSHLANDI</b>\n'
    msg += ('💀 Halok bo‘lganlar: '+', '.join(map(escape,dead))) if dead else '🌤️ Bu kecha hech kim halok bo‘lmadi.'
    await update.effective_message.reply_text(msg,parse_mode='HTML')
    await check_winner(context,chat.id)

async def vote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    chat=update.effective_chat; g=game_for(chat.id); uid=update.effective_user.id; p=g['players'].get(uid)
    if not g['started'] or g['phase']!='day': return await update.effective_message.reply_text('Hozir ovoz berish vaqti emas.')
    if not p or not p['alive']: return await update.effective_message.reply_text('Siz ovoz bera olmaysiz.')
    t=target_from(g,context.args)
    if not t or not t.get('alive') or t['id']==uid: return await update.effective_message.reply_text('To‘g‘ri o‘yinchi raqamini kiriting: /vote 2')
    g['votes'][uid]=t['id']; await update.effective_message.reply_text(f'🗳️ Ovoz qabul qilindi: {escape(t["name"])}',parse_mode='HTML')
    alive=[x for x in g['players'].values() if x['alive']]
    if len(g['votes'])>=len(alive):
        counts={}
        for x in g['votes'].values(): counts[x]=counts.get(x,0)+1
        high=max(counts.values()); winners=[x for x,n in counts.items() if n==high]
        if len(winners)==1: g['players'][winners[0]]['alive']=False; await update.effective_message.reply_text(f'💀 Ovoz bilan chiqarildi: {escape(g["players"][winners[0]]["name"])}',parse_mode='HTML')
        else: await update.effective_message.reply_text('⚖️ Ovozlar teng. Hech kim chiqarilmadi.')
        g['votes']={}; g['phase']='night'; await check_winner(context,chat.id)
        if g['started']: await update.effective_message.reply_text('🌙 Yangi tun boshlandi. /night')

async def check_winner(context, chat_id):
    g=game_for(chat_id)
    if not g['started']: return
    alive=[p for p in g['players'].values() if p['alive']]
    mafia=sum(p.get('role') in ('Mafia','Don','Yollanma qotil') for p in alive)
    citizens=len(alive)-mafia
    if mafia and mafia>=citizens: side='Mafia'; winners=[p for p in alive if p.get('role') in ('Mafia','Don','Yollanma qotil')]
    elif mafia==0: side='Fuqaro'; winners=[p for p in alive if p.get('role') not in ('Mafia','Don','Yollanma qotil')]
    else: return
    lines=[f'🏆 <b>O‘YIN TUGADI — {side}</b>','']
    for p in winners:
        pp=get_player(p['id']); reward=100
        save_player(p['id'],wins=pp['wins']+1,points=pp['points']+reward,dollars=pp['dollars']+20)
        lines.append(f'👑 {escape(p["name"])} — +{reward} ⭐, +20 💵')
    await context.bot.send_message(chat_id,'\n'.join(lines),parse_mode='HTML')
    for p in g['players'].values(): user_game.pop(p['id'], None)
    g.update(players={},started=False,phase='lobby',votes={},actions={},silenced=set())

async def leave_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    g=game_for(update.effective_chat.id); uid=update.effective_user.id
    if g['started']: return await update.effective_message.reply_text('O‘yin boshlanganidan keyin chiqib bo‘lmaydi.')
    if uid not in g['players']: return await update.effective_message.reply_text('Siz o‘yinda emassiz.')
    del g['players'][uid]; await update.effective_message.reply_text('O‘yindan chiqdingiz.')

# ==================== ADMIN ====================
def admin_target(update):
    msg=update.effective_message
    if msg.reply_to_message and msg.reply_to_message.from_user: return msg.reply_to_message.from_user.id
    if update.effective_message and update.effective_message.text:
        parts=update.effective_message.text.split()
        if len(parts)>1 and parts[1].lstrip('-').isdigit(): return int(parts[1])
    return None

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return await update.effective_message.reply_text('🔒 /admin buyrug‘i faqat bot egasiga shaxsiy chatda ochiq.')
    if update.effective_chat.type != 'private':
        return await update.effective_message.reply_text('🔒 Admin panelni bot bilan shaxsiy chatda oching.')
    text=('👑 <b>ADMIN PANEL</b>\n\n'
          'Reply orqali: /profile, /bankrot1, /bankrot2, /ban, /unban\n'
          'ID bilan: /profile ID\n'
          '/adddiamond ID MIQDOR\n/addmoney ID MIQDOR\n/removediamond ID MIQDOR\n/removemoney ID MIQDOR\n'
          '/bankrot1 ID — pulni 0 qilish\n/bankrot2 ID — olmos va dollarni 0 qilish\n'
          '/ban ID · /unban ID · /addadmin ID · /removeadmin ID')
    await update.effective_message.reply_text(text,parse_mode='HTML')

async def admin_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    if not is_admin(update.effective_user.id): return await update.effective_message.reply_text('🔒 Faqat admin.')
    uid=admin_target(update)
    if not uid: return await update.effective_message.reply_text('O‘yinchi xabariga reply qilib /profile yozing yoki /profile ID.')
    p=get_player(uid)
    await update.effective_message.reply_text('📋 <b>FOYDALANUVCHI HAQIDA MA’LUMOT</b>\n\n'+money_text(p),parse_mode='HTML')

async def admin_change(update: Update, context: ContextTypes.DEFAULT_TYPE, field, sign):
    if not allowed(update): return
    if not is_admin(update.effective_user.id): return await update.effective_message.reply_text('🔒 Faqat admin.')
    msg=update.effective_message; uid=None; amount=None
    # Reply: /addmoney 5000; ID usuli: /addmoney ID 5000
    if msg.reply_to_message:
        uid=msg.reply_to_message.from_user.id
        if context.args and context.args[0].isdigit(): amount=int(context.args[0])
    elif len(context.args)>=2 and context.args[0].isdigit() and context.args[1].isdigit():
        uid=int(context.args[0]); amount=int(context.args[1])
    if uid is None or amount is None or amount<=0: return await msg.reply_text(f'Foydalanish: reply qilib /{msg.text.split()[0][1:]} MIQDOR yoki /{msg.text.split()[0][1:]} ID MIQDOR')
    p=get_player(uid); value=max(0,p[field]+sign*amount); save_player(uid,**{field:value})
    newp=get_player(uid)
    label={'money':'pul','diamonds':'olmos'}[field]
    await msg.reply_text(f'✅ {escape(newp["name"])} balansiga {label}: {newp[field]:,}\n🆔 ID: {uid}',parse_mode='HTML')

async def adddiamond(u,c): await admin_change(u,c,'diamonds',1)
async def removediamond(u,c): await admin_change(u,c,'diamonds',-1)
async def addmoney(u,c): await admin_change(u,c,'money',1)
async def removemoney(u,c): await admin_change(u,c,'money',-1)

async def bankrot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    if not is_admin(update.effective_user.id): return await update.effective_message.reply_text('🔒 Faqat admin.')
    msg=update.effective_message; cmd=msg.text.split()[0].split('@')[0]
    uid=admin_target(update)
    if not uid: return await msg.reply_text(f'O‘yinchi xabariga reply qilib {cmd} yozing yoki {cmd} ID.')
    p=get_player(uid)
    if cmd=='/bankrot1': save_player(uid,money=0); desc='pul 0 qilindi'
    else: save_player(uid,diamonds=0,dollars=0); desc='olmos va dollar 0 qilindi'
    p=get_player(uid)
    await msg.reply_text(f'⚠️ <b>BANKROT</b>\n👤 {escape(p["name"])}\n🆔 ID: <code>{uid}</code>\n✅ {desc}',parse_mode='HTML')

async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    if not is_admin(update.effective_user.id): return await update.effective_message.reply_text('🔒 Faqat admin.')
    uid=admin_target(update)
    if not uid: return await update.effective_message.reply_text('Reply qilib /ban yozing yoki /ban ID.')
    save_player(uid,banned=1); await update.effective_message.reply_text(f'🚫 {uid} cheklab qo‘yildi.')
async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    if not is_admin(update.effective_user.id): return await update.effective_message.reply_text('🔒 Faqat admin.')
    uid=admin_target(update)
    if not uid: return await update.effective_message.reply_text('Reply qilib /unban yozing yoki /unban ID.')
    save_player(uid,banned=0); await update.effective_message.reply_text(f'✅ {uid} cheklovi olib tashlandi.')
async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return await update.effective_message.reply_text('🔒 Faqat bot egasi.')
    uid=admin_target(update)
    if not uid: return await update.effective_message.reply_text('Reply qilib /addadmin yozing yoki /addadmin ID.')
    with db() as con: con.execute('INSERT OR IGNORE INTO admins(user_id) VALUES(?)',(uid,))
    await update.effective_message.reply_text('👑 Admin qo‘shildi.')
async def removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return await update.effective_message.reply_text('🔒 Faqat bot egasi.')
    uid=admin_target(update)
    if not uid: return await update.effective_message.reply_text('Reply qilib /removeadmin yozing yoki /removeadmin ID.')
    if uid==OWNER_ID: return await update.effective_message.reply_text('Bot egasini olib tashlab bo‘lmaydi.')
    with db() as con: con.execute('DELETE FROM admins WHERE user_id=?',(uid,))
    await update.effective_message.reply_text('✅ Admin olib tashlandi.')

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    if not is_admin(update.effective_user.id): return await update.effective_message.reply_text('🔒 Faqat admin.')
    g=game_for(update.effective_chat.id)
    for p in g['players'].values(): user_game.pop(p['id'], None)
    g.update(players={},started=False,phase='lobby',votes={},actions={},silenced=set())
    await update.effective_message.reply_text('⛔ O‘yin to‘xtatildi.')

async def lang_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.effective_message.reply_text('🌐 Bot tili: O‘zbekcha.')
async def kurs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.effective_message.reply_text('🪙 Kurs: 1 olmos = 500 pul.')
async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return await update.effective_message.reply_text('🔒 Faqat admin.')
    await update.effective_message.reply_text('⚙️ Minimal 4, maksimal 30 o‘yinchi.')
async def giveaway_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return await update.effective_message.reply_text('🔒 Faqat admin.')
    await update.effective_message.reply_text('🎁 Giveaway funksiyasi keyingi bosqichda sozlanadi.')

async def track_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track(update)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception('Handler xatosi:', exc_info=context.error)

async def post_init(app: Application):
    # Shaxsiy menyu. Admin buyruqlari oddiy foydalanuvchiga ko‘rsatilmaydi.
    general = [
        BotCommand('start', 'Botni boshlash'),
        BotCommand('profile', 'Profilni ko‘rish'),
        BotCommand('roles', 'O‘yin rollari'),
        BotCommand('help', 'Yordam'),
    ]
    # Guruh menyusi: /start birinchi, /game yagona yangi o‘yin buyrug‘i.
    # Juftlik buyruqlari menyuda ataylab ko‘rsatilmaydi.
    group = [
        BotCommand('start', 'Botni boshlash'),
        BotCommand('game', 'Yangi o‘yin ochish'),
        BotCommand('profile', 'O‘yinchi profilini ko‘rish (admin)'),
        BotCommand('players', 'O‘yinchilar ro‘yxati'),
        BotCommand('startgame', 'O‘yinni boshlash'),
        BotCommand('leave', 'O‘yindan chiqish'),
        BotCommand('roles', 'Barcha rollar'),
        BotCommand('role', 'O‘z rolingni ko‘rish'),
        BotCommand('night', 'Tungi vazifani ko‘rish'),
        BotCommand('kill', 'Tunda nishonga hujum'),
        BotCommand('heal', 'O‘yinchini davolash'),
        BotCommand('check', 'O‘yinchini tekshirish'),
        BotCommand('vote', 'Ovoz berish'),
        BotCommand('endnight', 'Tunni yakunlash'),
        BotCommand('top', 'Umumiy reyting'),
        BotCommand('top1', 'Bugungi reyting'),
        BotCommand('top7', '7 kunlik reyting'),
        BotCommand('money', 'Reply orqali pul yuborish'),
        BotCommand('give', 'Reply orqali olmos yuborish'),
        BotCommand('kurs', 'Olmos kursi'),
        BotCommand('lang', 'Bot tilini ko‘rish'),
        BotCommand('sozlamalar', 'O‘yin sozlamalari (admin)'),
        BotCommand('giveaway', 'Sovrinli tanlov (admin)'),
        BotCommand('stop', 'O‘yinni to‘xtatish (admin)'),
        BotCommand('help', 'Buyruqlar bo‘yicha yordam'),
    ]
    await app.bot.set_my_commands([], scope=BotCommandScopeDefault())
    await app.bot.set_my_commands(general, scope=BotCommandScopeAllPrivateChats())
    await app.bot.set_my_commands(group, scope=BotCommandScopeAllGroupChats())
    if OWNER_ID:
        owner = general + [
            BotCommand('admin', 'Admin panel'),
            BotCommand('addadmin', 'Admin tayinlash'),
            BotCommand('removeadmin', 'Adminlikdan olish'),
            BotCommand('adddiamond', 'Olmos qo‘shish'),
            BotCommand('removediamond', 'Olmos ayirish'),
            BotCommand('addmoney', 'Pul qo‘shish'),
            BotCommand('removemoney', 'Pul ayirish'),
            BotCommand('bankrot1', 'Pulni nol qilish'),
            BotCommand('bankrot2', 'Olmos va dollarni nol qilish'),
            BotCommand('ban', 'O‘yinchini cheklash'),
            BotCommand('unban', 'Cheklovni olib tashlash'),
        ]
        await app.bot.set_my_commands(owner, scope=BotCommandScopeChat(chat_id=OWNER_ID))

async def run_command_and_delete(update: Update, context: ContextTypes.DEFAULT_TYPE, handler):
    # Guruhda buyruq bajarilgach, buyruq xabarini o‘chiramiz; bot javobi qoladi.
    try:
        return await handler(update, context)
    finally:
        await delete_command_message(update.effective_message)

def wrapped(handler):
    async def _wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await run_command_and_delete(update, context, handler)
    return _wrapped

def main():
    if not TOKEN:
        raise RuntimeError('BOT_TOKEN environment variable topilmadi.')
    if not OWNER_ID:
        logger.warning('OWNER_ID 0. Ega admin buyruqlari ishlamasligi mumkin.')
    init_db()
    threading.Thread(target=health_server, daemon=True).start()
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    handlers = [
        ('start', start), ('help', help_cmd), ('profile', profile), ('roles', roles_cmd),
        ('money', money_gift), ('give', give_diamonds),
        ('top', top_cmd), ('top1', top_cmd), ('top7', top_cmd),
        ('para', para_cmd), ('mypara', mypara_cmd), ('dpara', dpara_cmd),
        ('game', newgame),
        ('players', players_cmd), ('startgame', startgame), ('role', role_cmd), ('night', night_cmd),
        ('kill', kill_cmd), ('heal', heal_cmd), ('check', check_cmd), ('endnight', endnight),
        ('vote', vote_cmd), ('leave', leave_cmd),
        ('admin', admin_cmd), ('adddiamond', adddiamond), ('adddiamonds', adddiamond),
        ('removediamond', removediamond), ('addmoney', addmoney), ('addbalance', addmoney),
        ('removemoney', removemoney), ('bankrot1', bankrot), ('bankrot2', bankrot),
        ('ban', ban_cmd), ('unban', unban_cmd), ('addadmin', addadmin),
        ('makeadmin', addadmin), ('removeadmin', removeadmin), ('stop', stop_cmd),
        ('lang', lang_cmd), ('kurs', kurs_cmd), ('sozlamalar', settings_cmd), ('giveaway', giveaway_cmd),
    ]
    for name, fn in handlers:
        app.add_handler(CommandHandler(name, wrapped(fn)))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.ALL, track_group), group=1)
    app.add_error_handler(error_handler)
    logger.info('MAFIA BOT ishga tushmoqda...')
    app.run_polling(drop_pending_updates=True)

if __name__=='__main__': main()
