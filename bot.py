import os, sqlite3, logging, random, threading, html
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats, BotCommandScopeChat, InlineKeyboardButton, InlineKeyboardMarkup
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
    'universal': ('🛡️ Umumiy himoya', '100 pul', 100, 0),
    'vote': ('🗳️ Ovoz himoyasi', '💎 1', 0, 1),
    'fake_doc': ('📁 Soxta hujjat', '190 pul', 190, 0),
    'protect_other': ('🤝 Boshqani himoya qilish', '💎 5', 0, 5),
    'killer': ('🚨 Qotildan himoya', '💎 2', 0, 2),
    'silence': ('🔇 Sukut himoyasi', '💎 1', 0, 1),
    'poison': ('💊 Zahar himoyasi', '100 pul', 100, 0),
    'mask': ('🎭 Maska', '100 pul', 100, 0),
    'slip': ('🥊 Sirpanish himoyasi', '300 pul', 300, 0),
    'hero_protect': ('🦸 Qahramon himoyasi', '💎 5', 0, 5),
    'ricochet': ('🌀 Rikoshet', '💎 3', 0, 3),
    'profile_change': ('🔄 Profil almashtirish', '💎 5', 0, 5),
    'hero': ('🦸 Qahramon', '💎 90', 0, 90),
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
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA busy_timeout=20000')
    return con

def init_db():
    with db() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS players(
            user_id INTEGER PRIMARY KEY, name TEXT DEFAULT '', username TEXT DEFAULT '',
            diamonds INTEGER DEFAULT 0, money INTEGER DEFAULT 0, dollars INTEGER DEFAULT 0,
            games INTEGER DEFAULT 0, wins INTEGER DEFAULT 0, points INTEGER DEFAULT 0, banned INTEGER DEFAULT 0)''')
        con.execute('CREATE TABLE IF NOT EXISTS admins(user_id INTEGER PRIMARY KEY)')
        con.execute('CREATE TABLE IF NOT EXISTS group_members(chat_id INTEGER, user_id INTEGER, PRIMARY KEY(chat_id,user_id))')
        con.execute('CREATE TABLE IF NOT EXISTS protections(user_id INTEGER, item TEXT, amount INTEGER DEFAULT 0, PRIMARY KEY(user_id,item))')
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
        if update.effective_message: update.effective_message.reply_text('🚫 Siz botdan foydalanish huquqidan mahrum qilingansiz.')
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
    await update.effective_message.reply_text('🎭 <b>MAFIA BOT</b>\n\nProfilingizni ko‘rish: /profile\nGuruhda yangi o‘yin: /newgame\nRollar: /roles\nYordam: /help', parse_mode='HTML')

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    await update.effective_message.reply_text('📚 <b>BUYRUQLAR</b>\n\nShaxsiy: /start /profile /roles /help\nGuruh: /newgame /game /join /players /startgame /leave /role /night /vote /top /top1 /top7 /para\nPul yuborish: javob qilib /money 5000\nOlmos yuborish: javob qilib /give 2', parse_mode='HTML')

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    u = update.effective_user
    target = u
    # Reply orqali boshqa odamning profilini faqat admin ko‘ra oladi.
    if update.effective_chat and update.effective_chat.type in ('group','supergroup') and update.effective_message.reply_to_message:
        if not is_admin(u.id): return await update.effective_message.reply_text('🔒 Boshqa odam profilini faqat admin ko‘ra oladi.')
        target = update.effective_message.reply_to_message.from_user
    elif context.args and is_admin(u.id):
        try:
            uid = int(context.args[0]); p = get_player(uid)
            return await update.effective_message.reply_text('📋 <b>FOYDALANUVCHI PROFILI</b>\n\n'+money_text(p), parse_mode='HTML')
        except ValueError: return await update.effective_message.reply_text('ID рақам бўлиши керак.')
    p = get_player(target.id, target)
    await update.effective_message.reply_text('👤 <b>PROFIL</b>\n\n'+money_text(p), parse_mode='HTML', reply_markup=profile_keyboard() if target.id == u.id else None)

async def roles_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    lines = ['🎭 <b>MAFIA BOT — ROLLAR</b>', '']
    for role, icon in ROLES: lines.append(f'{icon} <b>{escape(role)}</b> — {escape(ROLE_HELP.get(role, "Maxsus rol."))}')
    # Telegram xabar chegarasidan oshmasligi uchun bo'lib yuboramiz.
    text = '\n'.join(lines)
    for i in range(0, len(text), 3500): await update.effective_message.reply_text(text[i:i+3500], parse_mode='HTML')

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not allowed(update): return
    uid = q.from_user.id
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
        name,price,mc,dc=PROTECTIONS[key]; p=get_player(uid,q.from_user)
        if p['money']<mc or p['diamonds']<dc: return await q.answer('Balans yetarli emas.',show_alert=True)
        save_player(uid,money=p['money']-mc,diamonds=p['diamonds']-dc); add_protection(uid,key,1)
        return await q.edit_message_text(f'✅ Xarid qilindi: {name}\nNarxi: {price}',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⬅️ Himoya markazi',callback_data='protections')],[InlineKeyboardButton('👤 Profil',callback_data='back_profile')]]))
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
    chat=update.effective_chat
    if chat.type not in ('group','supergroup'): return await update.effective_message.reply_text('/para guruhda ishlaydi.')
    with db() as con:
        rows=con.execute('SELECT p.user_id,p.name FROM players p JOIN group_members g ON p.user_id=g.user_id WHERE g.chat_id=? AND p.banned=0',(chat.id,)).fetchall()
    if len(rows)<2: return await update.effective_message.reply_text('Juftlik tanlash uchun kamida 2 foydalanuvchi bot bilan muloqot qilgan bo‘lishi kerak.')
    a,b=random.sample(rows,2)
    await update.effective_message.reply_text(f'❤️ <b>HAQIQIY JUFTLIK</b> ❤️\n\n<b>{escape(a["name"])} ❤️ {escape(b["name"])}</b>',parse_mode='HTML')

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
    g.update(players={},started=False,phase='lobby',votes={},actions={},silenced=set())
    await update.effective_message.reply_text('🎭 <b>YANGI MAFIYA O‘YINI</b>\n\nQo‘shilish uchun /join bosing.\n👥 Minimal: 4 | Maksimal: 30',parse_mode='HTML')

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    chat=update.effective_chat
    if chat.type not in ('group','supergroup'): return await update.effective_message.reply_text('O‘yinga guruhda qo‘shiling.')
    g=game_for(chat.id); u=update.effective_user
    if g['started']: return await update.effective_message.reply_text('O‘yin allaqachon boshlangan.')
    if len(g['players'])>=MAX_PLAYERS: return await update.effective_message.reply_text('O‘yinchilar soni 30 taga yetdi.')
    if u.id in g['players']: return await update.effective_message.reply_text('Siz allaqachon ro‘yxatdasiz.')
    get_player(u.id,u)
    g['players'][u.id]={'id':u.id,'name':u.full_name,'alive':True}
    with db() as con: con.execute('INSERT OR IGNORE INTO group_members(chat_id,user_id) VALUES(?,?)',(chat.id,u.id))
    await update.effective_message.reply_text(f'✅ {escape(u.full_name)} o‘yinga qo‘shildi. ({len(g["players"])}/{MAX_PLAYERS})',parse_mode='HTML')

async def players_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update): return
    g=game_for(update.effective_chat.id); ps=player_list(g)
    if not ps: return await update.effective_message.reply_text('Hozircha o‘yinchilar yo‘q. /newgame')
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
    if not allowed(update): return
    if not is_admin(update.effective_user.id): return await update.effective_message.reply_text('🔒 Bu buyruq faqat adminlar uchun.')
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
    general=[BotCommand('start','Botni boshlash'),BotCommand('profile','Profil'),BotCommand('roles','O‘yin rollari'),BotCommand('help','Yordam')]
    group=[BotCommand('game','Yangi o‘yin'),BotCommand('newgame','Yangi o‘yin ochish'),BotCommand('join','O‘yinga qo‘shilish'),BotCommand('players','O‘yinchilar'),BotCommand('startgame','O‘yinni boshlash'),BotCommand('leave','O‘yindan chiqish'),BotCommand('role','Mening rolim'),BotCommand('night','Tungi vazifa'),BotCommand('vote','Ovoz berish'),BotCommand('endnight','Tunni tugatish'),BotCommand('top','TOP'),BotCommand('top1','Bugungi TOP'),BotCommand('top7','7 kunlik TOP'),BotCommand('para','Juftlik'),BotCommand('kurs','Olmos kursi'),BotCommand('help','Yordam')]
    await app.bot.set_my_commands(general,scope=BotCommandScopeAllPrivateChats())
    await app.bot.set_my_commands(group,scope=BotCommandScopeAllGroupChats())
    if OWNER_ID:
        owner=[*general,BotCommand('admin','Admin panel'),BotCommand('addadmin','Admin qo‘shish'),BotCommand('removeadmin','Adminni olib tashlash'),BotCommand('adddiamond','Olmos qo‘shish'),BotCommand('removediamond','Olmos ayirish'),BotCommand('addmoney','Pul qo‘shish'),BotCommand('removemoney','Pul ayirish'),BotCommand('bankrot1','Pulni 0 qilish'),BotCommand('bankrot2','Olmos va dollarni 0 qilish'),BotCommand('ban','Ban'),BotCommand('unban','Unban')]
        await app.bot.set_my_commands(owner,scope=BotCommandScopeChat(chat_id=OWNER_ID))

def main():
    if not TOKEN: raise RuntimeError('BOT_TOKEN environment variable topilmadi.')
    if not OWNER_ID: logger.warning('OWNER_ID 0. Ega admin buyruqlari ishlamasligi mumkin.')
    init_db(); threading.Thread(target=health_server,daemon=True).start()
    app=Application.builder().token(TOKEN).post_init(post_init).build()
    handlers=[
        ('start',start),('help',help_cmd),('profile',profile),('roles',roles_cmd),('money',money_gift),('give',give_diamonds),
        ('top',top_cmd),('top1',top_cmd),('top7',top_cmd),('para',para_cmd),('game',newgame),('newgame',newgame),
        ('join',join),('players',players_cmd),('startgame',startgame),('role',role_cmd),('night',night_cmd),
        ('kill',kill_cmd),('heal',heal_cmd),('check',check_cmd),('endnight',endnight),('vote',vote_cmd),('leave',leave_cmd),
        ('admin',admin_cmd),('adddiamond',adddiamond),('adddiamonds',adddiamond),('removediamond',removediamond),
        ('addmoney',addmoney),('addbalance',addmoney),('removemoney',removemoney),('bankrot1',bankrot),('bankrot2',bankrot),
        ('ban',ban_cmd),('unban',unban_cmd),('addadmin',addadmin),('makeadmin',addadmin),('removeadmin',removeadmin),
        ('stop',stop_cmd),('lang',lang_cmd),('kurs',kurs_cmd),('sozlamalar',settings_cmd),('giveaway',giveaway_cmd)]
    for name,fn in handlers: app.add_handler(CommandHandler(name,fn))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.ALL,track_group),group=1)
    app.add_error_handler(error_handler)
    logger.info('MAFIA BOT ishga tushmoqda...')
    app.run_polling(drop_pending_updates=True)

if __name__=='__main__': main()
