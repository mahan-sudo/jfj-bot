"""🃏 کازینو شاهنشاهی — بخش بازی‌های گروهی ربات (فایل جدا؛ اگر خراب شود بقیه‌ی ربات کار می‌کند)

بازی ۱: 🎰 گردونه شانس (۱ تا ۳ بازیکن)
بازی ۲: 🎲 تاس (۱ یا ۲ بازیکن)
بازی ۳: ❌⭕ دوز شاهنشاهی (۲ بازیکن، نوبتی)
+ 💎 انتقال شاهی در گروه (ریپلای + «انتقال شاهی مقدار»)

امنیت پول: هر کسر/پرداخت/تغییر وضعیت در «یک تراکنش» sqlite با BEGIN IMMEDIATE انجام می‌شود
(یا کامل انجام می‌شود یا هیچ؛ حتی با کرش یا دو نمونه‌ی هم‌زمان ربات روی یک دیتابیس).
tg() ربات تمام متن‌ها را خودکار Bold می‌کند.
"""
import html as _html
import logging
import random
import re
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

B = None            # ماژول bot_test
_LK = threading.RLock()   # علاوه بر قفل دیتابیس؛ تراکنش‌های هم‌پردازشی را صف می‌کند

# ---------------- تنظیمات ----------------
TRIGGER = "کازینو"               # فقط خودِ همین متن (نه «حاوی» آن)
TRIGGERS_XO = ("دوز", "xo")        # هر دو؛ فقط متن دقیق (xo بدون حساسیت به بزرگی حروف)
TRIGGER_XO = "دوز"
XO_MIN_STAKE = 2
XFER_SEC = 60                 # فرصت تأیید انتقال
XFER_WORD = "انتقال"
LB_WORD = "لیدربرد"
PROF_SELF = ("پروفایل", "شاهیام", "شاهی ام")          # پروفایل خودم
PROF_OTHER = ("پروفایلش", "شاهیاش", "شاهی اش")        # فقط با ریپلای روی کاربر
XO_SEC = 150                  # کل زمان بازی دوز؛ بعد از آن بازیکنِ نوبت‌دار بازنده است
MIN_STAKE = 5
MAX_STAKE_DEFAULT = 100       # سقف مبلغ ورودی؛ کلید تنظیمات casino_max (0 = بدون سقف)
JOIN_SEC = 60
SEND_SEC = 60
COOLDOWN_SEC = 120
REVEAL_DELAY = 3.6            # صبر برای تمام شدن انیمیشن قبل از نمایش نتیجه
STALE_SEC = 600
PLAYER_EMOJIS = "🍟🍿🍱🍩🍭"
PRE = ("menu", "setup", "stake_wait", "pick", "mode")      # مراحل قبل از ساخت میز (بدون پول)
DICE_MULT_PAIR = 1.5          # تاس تک‌نفره: زوج/فرد
DICE_MULT_NUM = 1.5           # تاس تک‌نفره: حدس عدد دقیق ۱ تا ۵
DICE_MULT_SIX = 2.0           # تاس تک‌نفره: حدس عدد ۶ و آمدن ۶

# گردونه: 0=BAR 1=انگور 2=لیمو 3=هفت
SYM = {0: "ʙᴀʀ", 1: "🍇", 2: "🍋", 3: "7️⃣"}
MULT = {0: 0.0, 1: 1.0, 2: 1.5, 3: 2.0}
NUM_EMO = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣"}

GAMES = {
    "s": {"emoji": "🎰", "title": "🃏 کازینو گردونه شانس 🎰", "short": "🃏 گردونه شانس 🎰", "maxp": 3, "word": "گردونه"},
    "d": {"emoji": "🎲", "title": "🃏 کازینو تاس 🎲", "short": "🃏 کازینو تاس 🎲", "maxp": 2, "word": "تاس"},
    "x": {"emoji": "", "title": "🕹 دوز شاهنشاهی XO", "short": "🕹 دوز شاهنشاهی XO", "maxp": 2, "word": "دوز",
          "trigger": TRIGGER_XO},
}
XO_SYM = {"X": "❌️", "O": "⭕️", "-": "◻️"}
XO_LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6))


# تنظیمات قابل‌تغییر از پنل ادمین: نام → (کلید ذخیره در settings، نام ثابت پیش‌فرض)
_CFGK = {
    "max": ("casino_max", "MAX_STAKE_DEFAULT"), "min": ("g_min", "MIN_STAKE"), "xmin": ("g_xmin", "XO_MIN_STAKE"),
    "join": ("g_join", "JOIN_SEC"), "send": ("g_send", "SEND_SEC"), "xo": ("g_xo", "XO_SEC"),
    "cool": ("g_cool", "COOLDOWN_SEC"), "xfer": ("g_xfer", "XFER_SEC"), "stale": ("g_stale", "STALE_SEC"),
    "dp": ("g_dp", "DICE_MULT_PAIR"), "dn": ("g_dn", "DICE_MULT_NUM"), "d6": ("g_d6", "DICE_MULT_SIX"),
}


def cv(name):
    """مقدار فعلی یک تنظیم: اگر ادمین تنظیم کرده همان، وگرنه پیش‌فرض داخل کد"""
    key, const = _CFGK[name]
    try:
        raw = B.get_setting(key, "")
        if raw not in (None, ""):
            return float(raw)
    except Exception:
        pass
    return float(globals()[const])


def _min_stake(game):
    return cv("xmin") if game == "x" else cv("min")


def xo_winner(board):
    for a, b, c in XO_LINES:
        if board[a] != "-" and board[a] == board[b] == board[c]:
            return board[a]
    return None


# ---------------- منطق بازی ----------------
def decode_dice(value):
    v = int(value) - 1
    return [v % 4, (v // 4) % 4, v // 16]


def evaluate(reels, rnd=random):
    """گردونه: (ضریب، امتیاز)"""
    cnt = {}
    for s in reels:
        cnt[s] = cnt.get(s, 0) + 1
    if len(cnt) == 1:
        m = MULT[reels[0]]
        return m, int(round(m * 100)) + 25
    if len(cnt) == 2:
        pair = [s for s, n in cnt.items() if n == 2][0]
        single = [s for s, n in cnt.items() if n == 1][0]
        m = 1.0 if (pair == 3 and single == 0) else MULT[pair]
        return m, int(round(m * 100))
    s = set(reels)
    if 0 in s and 3 in s:
        m = rnd.choice([1.0, 1.5])
    elif 0 in s:
        m = 0.0
    else:
        m = (1.0 + 1.5 + 2.0) / 3
    return m, int(round(m * 100))


def dice_solo_mult(pick, value):
    """تاس تک‌نفره: pick = 'e' زوج، 'o' فرد، یا '1'..'6'"""
    if pick == "e":
        return cv("dp") if value % 2 == 0 else 0.0
    if pick == "o":
        return cv("dp") if value % 2 == 1 else 0.0
    try:
        if int(pick) != value:
            return 0.0
        return cv("d6") if value == 6 else cv("dn")
    except Exception:
        return 0.0


def _pick_label(pick):
    if pick is None:
        return "تعیین نشده ❌️"
    if pick == "e":
        return "زوج"
    if pick == "o":
        return "فرد"
    return NUM_EMO.get(int(pick), pick)


def _mode_label(mode):
    return "بیشترین عدد 🔺️" if mode == "max" else "کمترین عدد 🔻"


def _fm(m):
    return f"{m:.1f}"


# ---------------- ابزار ----------------
def _t(v):
    return B.fa_digits(B.fmt_tokens(v))


def _n(v):
    return B.fa_digits(str(int(v)))


def _norm(s):
    t = (s or "").replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ").replace("\u200f", "")
    return " ".join(t.split())


def _name(u):
    n = (u.get("first_name") or u.get("username") or "کاربر").strip()
    return n[:18] or "کاربر"


def _kb(*rows):
    return B._kb(*rows)


def _btn(text, cb, style=None):
    return B._ab(text, cb, style)


def _parse_num(text):
    t = (text or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٬٫", "01234567890123456789,."))
    t = t.replace(",", "").strip()
    if not re.fullmatch(r"\d+(\.\d{1,2})?", t):
        return None
    return float(t)


def _parse_int(text):
    """مبلغ بازی/انتقال فقط عدد صحیح؛ اعشاری = None (نامعتبر)"""
    v = _parse_num(text)
    if v is None or v != int(v):
        return None
    return float(int(v))


def enabled():
    return B.get_setting("casino_on", "1") != "0"


def game_on(key):
    """کلید بازی: 's' گردونه، 'd' تاس، 'x' دوز. خاموش = ربات برای ساخت میز جدید اصلاً پاسخ نمی‌دهد"""
    return enabled() and B.get_setting(f"g_{key}_on", "1") != "0"


def casino_games():
    return [k for k in ("s", "d") if game_on(k)]


def _max_stake():
    return cv("max")


def _fmt_wait(sec):
    sec = max(1, int(sec + 0.999))
    m, s = divmod(sec, 60)
    if m and s:
        return f"{_n(m)} دقیقه و {_n(s)} ثانیه"
    if m:
        return f"{_n(m)} دقیقه"
    return f"{_n(s)} ثانیه"


def _cool_msg(left):
    return f"👑 برو استراحت کن بعدا دوباره بیا سَرورَم.\n⏰️ باید {_fmt_wait(left)} صبر کنی."


# ---------------- دیتابیس و تراکنش ----------------
def _RF(cur, row):
    return {d[0]: row[i] for i, d in enumerate(cur.description)}


_TL = threading.local()
NET_TIMEOUT = 12        # ثانیه؛ تماس کند تلگرام نباید ترد را دقیقه‌ها قفل کند


class _Tx:
    """تراکنش اتمیک: BEGIN IMMEDIATE (قفل نوشتن دیتابیس از اول) ؛ خطا = rollback کامل.
    هیچ تماس شبکه‌ای وسط تراکنش انجام نمی‌شود: پاسخ‌های callback تا بعد از commit نگه داشته می‌شوند
    (وگرنه یک تلگرامِ کند، قفل نوشتن را نگه می‌داشت و کل ربات قفل می‌شد)."""

    def __enter__(self):
        _LK.acquire()
        try:
            self.c = B.get_db()
            self.c.row_factory = _RF
            self.c.execute("BEGIN IMMEDIATE")
        except BaseException:
            _LK.release()
            raise
        _TL.pending = []
        _TL.active = True
        return self.c

    def __exit__(self, et, ev, tb):
        pend = getattr(_TL, "pending", [])
        _TL.active = False
        _TL.pending = []
        try:
            if et is None:
                self.c.commit()
            else:
                self.c.rollback()
        finally:
            self.c.close()
            _LK.release()
        if et is None:
            for fn, a in pend:      # حالا بیرون از قفل
                try:
                    fn(*a)
                except Exception:
                    logging.exception("games deferred")
        return False


def _later(fn, *a):
    """داخل تراکنش: به تعویق می‌اندازد؛ بیرون تراکنش: همان لحظه اجرا می‌کند"""
    if getattr(_TL, "active", False):
        _TL.pending.append((fn, a))
    else:
        fn(*a)


def init(bot):
    global B
    B = bot
    with B.get_db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS g_tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL, thread_id INTEGER, owner INTEGER NOT NULL, owner_name TEXT,
            msg_id INTEGER, state TEXT NOT NULL, stake REAL, maxp INTEGER,
            join_dl REAL, send_dl REAL, touched REAL, created REAL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS g_players (
            table_id INTEGER NOT NULL, user_id INTEGER NOT NULL, name TEXT, emo TEXT, stake REAL,
            sent INTEGER NOT NULL DEFAULT 0, sent_at REAL, value INTEGER, shown INTEGER NOT NULL DEFAULT 0,
            mult REAL, score INTEGER, payout REAL,
            PRIMARY KEY (table_id, user_id))""")
        c.execute("""CREATE TABLE IF NOT EXISTS g_xfer (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL, thread_id INTEGER, msg_id INTEGER,
            sender INTEGER NOT NULL, sname TEXT, semo TEXT, recipient INTEGER NOT NULL, rname TEXT, remo TEXT,
            amount REAL NOT NULL, state TEXT NOT NULL, deadline REAL NOT NULL)""")
        c.execute("CREATE TABLE IF NOT EXISTS g_cool (user_id INTEGER PRIMARY KEY, ts REAL NOT NULL)")
        c.execute("""CREATE TABLE IF NOT EXISTS g_mon (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL, thread_id INTEGER, msg_id INTEGER,
            state TEXT NOT NULL, hp INTEGER NOT NULL, maxhp INTEGER NOT NULL, seed INTEGER NOT NULL DEFAULT 0,
            chances INTEGER NOT NULL, created REAL NOT NULL, expires REAL NOT NULL, winner INTEGER, reward REAL,
            has_photo INTEGER NOT NULL DEFAULT 0)""")
        c.execute("""CREATE TABLE IF NOT EXISTS g_mon_hits (
            id INTEGER PRIMARY KEY AUTOINCREMENT, mon_id INTEGER NOT NULL, user_id INTEGER NOT NULL, name TEXT,
            emo TEXT, hit INTEGER NOT NULL, dmg INTEGER NOT NULL, line TEXT, ts REAL NOT NULL)""")
        c.execute("CREATE INDEX IF NOT EXISTS g_mon_hits_m ON g_mon_hits(mon_id)")
        c.execute("CREATE INDEX IF NOT EXISTS g_mon_state ON g_mon(state, chat_id)")
        c.execute("""CREATE TABLE IF NOT EXISTS g_chats (
            chat_id INTEGER PRIMARY KEY, title TEXT, type TEXT, seen REAL)""")
        c.execute("CREATE INDEX IF NOT EXISTS g_tables_state ON g_tables(state)")
        c.execute("CREATE INDEX IF NOT EXISTS g_xfer_st ON g_xfer(state, deadline)")
        c.execute("CREATE INDEX IF NOT EXISTS g_xfer_snd ON g_xfer(sender, state)")
        c.execute("""CREATE TABLE IF NOT EXISTS g_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, game TEXT, chat_id INTEGER, tid INTEGER,
            kind TEXT, stake_total REAL, payout_total REAL, detail TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS g_log_ts ON g_log(ts)")
        c.execute("""CREATE TABLE IF NOT EXISTS g_stats (
            user_id INTEGER NOT NULL, game TEXT NOT NULL, wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (user_id, game))""")
        for tbl, col, ddl in (("g_tables", "game", "TEXT NOT NULL DEFAULT 's'"), ("g_tables", "mode", "TEXT"),
                              ("g_players", "pick", "TEXT"), ("g_tables", "board", "TEXT"),
                              ("g_tables", "turn", "INTEGER"), ("g_tables", "oemo", "TEXT"), ("g_players", "mid", "INTEGER")):
            cols = [r[1] for r in c.execute(f"PRAGMA table_info({tbl})")]
            if col not in cols:
                c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {ddl}")


def _row(q, args=()):
    c = B.get_db()
    try:
        c.row_factory = _RF
        return c.execute(q, args).fetchone()
    finally:
        c.close()


def _rows(q, args=()):
    c = B.get_db()
    try:
        c.row_factory = _RF
        return c.execute(q, args).fetchall()
    finally:
        c.close()


def _x(q, args=()):
    """یک دستور تکی (اتمیک خودش)"""
    c = B.get_db()
    try:
        cur = c.execute(q, args)
        c.commit()
        return cur
    finally:
        c.close()


def _purge(tid):
    """بازیِ تمام‌شده کاملاً از دیتابیس ربات پاک می‌شود؛ فقط پیام داخل گروه می‌ماند.
    محافظ: بازیکنانِ یک میزِ «فعال» هرگز پاک نمی‌شوند (پول بازیکن‌ها فقط با پایان بازی حذف می‌شود)."""
    try:
        with _Tx() as c:
            cur = c.execute("DELETE FROM g_tables WHERE id=? AND state IN ('done','cancelled','expired')", (tid,))
            if cur.rowcount == 1 or not c.execute("SELECT 1 FROM g_tables WHERE id=?", (tid,)).fetchone():
                c.execute("DELETE FROM g_players WHERE table_id=?", (tid,))
    except Exception:
        logging.exception("games purge")
    with _ELK_G:
        _ELK.pop(tid, None)


# ---- قفل ویرایش هر میز: ویرایش‌ها پشت‌سرهم و همیشه با «آخرین وضعیت» انجام می‌شوند ----
_ELK = {}
_ELK_G = threading.Lock()


def _elock(tid):
    with _ELK_G:
        lk = _ELK.get(tid)
        if lk is None:
            lk = _ELK[tid] = threading.RLock()
        return lk


def _table(tid):
    return _row("SELECT * FROM g_tables WHERE id=?", (tid,))


def _players(tid):
    return _rows("SELECT * FROM g_players WHERE table_id=? ORDER BY rowid", (tid,))


def _active_in(c, uid):
    return c.execute("SELECT t.id FROM g_tables t JOIN g_players p ON p.table_id=t.id "
                     "WHERE p.user_id=? AND t.state IN ('join','send','play')", (uid,)).fetchone()


def _cool_left_c(c, uid):
    r = c.execute("SELECT ts FROM g_cool WHERE user_id=?", (uid,)).fetchone()
    return max(0, cv('cool') - (time.time() - r["ts"])) if r else 0


def _cool_left(uid):
    r = _row("SELECT ts FROM g_cool WHERE user_id=?", (uid,))
    return max(0, cv('cool') - (time.time() - r["ts"])) if r else 0


def _active_table_of(uid):
    return _row("SELECT t.* FROM g_tables t JOIN g_players p ON p.table_id=t.id "
                "WHERE p.user_id=? AND t.state IN ('join','send','play')", (uid,))


def _pay_in(c, uid, amount):
    cur = c.execute("UPDATE users SET tokens = ROUND(tokens + ?, 2) WHERE id=?", (amount, uid))
    if cur.rowcount != 1:
        logging.error("games: payout to missing user %s amount %s", uid, amount)
    return cur.rowcount == 1


def _charge_in(c, uid, amount):
    cur = c.execute("UPDATE users SET tokens = ROUND(tokens - ?, 2) WHERE id=? AND ROUND(tokens, 2) >= ROUND(?, 2)",
                    (amount, uid, amount))
    return cur.rowcount == 1


def _log_in(c, t, ps, kind):
    """دفتر مالی فشرده (۳۰ روز نگهداری) برای رسیدگی به اعتراض‌ها و گزارش شبانه"""
    det = [[p["user_id"], p.get("name"), p.get("stake"), p.get("payout") or 0.0, int(bool(p.get("sent")))] for p in ps]
    c.execute("INSERT INTO g_log (ts, game, chat_id, tid, kind, stake_total, payout_total, detail) VALUES (?,?,?,?,?,?,?,?)",
              (time.time(), t["game"], t["chat_id"], t["id"], kind, round(sum(p["stake"] or 0 for p in ps), 2),
               round(sum(p.get("payout") or 0 for p in ps), 2), json.dumps(det, ensure_ascii=False)))
    for p in ps:        # آمار دائمی برد/باخت برای پروفایل: سود خالص > 0 = برد ، < 0 = باخت ، صفر = هیچ‌کدام
        net = round((p.get("payout") or 0) - (p.get("stake") or 0), 2)
        if net:
            c.execute("INSERT INTO g_stats (user_id, game, wins, losses) VALUES (?,?,?,?) "
                      "ON CONFLICT(user_id, game) DO UPDATE SET wins=wins+excluded.wins, losses=losses+excluded.losses",
                      (p["user_id"], t["game"], 1 if net > 0 else 0, 1 if net < 0 else 0))


# ---------------- ارسال/ویرایش ----------------
def _plain(text):
    return _html.unescape(re.sub(r"<[^>]+>", "", text))


def _tgh(method, **p):
    """متن‌ها HTML هستند (منشن کاربر). اگر تلگرام نپذیرفت (مثلاً منشن ممکن نبود) همان متن بدون منشن ارسال می‌شود"""
    r = B.tg(method, _timeout=NET_TIMEOUT, parse_mode="HTML", **p)
    if r.get("ok") or "not modified" in str(r.get("description", "")):
        return r
    if p.get("text") and "<a " in p["text"] or "parse" in str(r.get("description", "")):
        q = dict(p)
        q["text"] = _plain(p["text"])
        return B.tg(method, _timeout=NET_TIMEOUT, **q)
    return r


def _send(t, text, kb=None, reply_to=None):
    p = {"chat_id": t["chat_id"], "text": text}
    if t.get("thread_id"):
        p["message_thread_id"] = t["thread_id"]
    if reply_to:
        p["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
    if kb:
        p["reply_markup"] = kb
    return _tgh("sendMessage", **p)


def _retry_after(r):
    ra = (r.get("parameters") or {}).get("retry_after")
    if ra:
        return float(ra)
    m_ = re.search(r"retry after (\d+)", str(r.get("description", "")), re.I)
    return float(m_.group(1)) if m_ else None


def _edit(t, text, kb=None):
    """ویرایش همان پیام (بدون ارسال پیام جدید). خطای شبکه/فشار تلگرام → چند بار تلاش مجدد.
    ویرایش‌های یک میز پشت‌سرهم (با قفل) انجام می‌شوند."""
    if not t.get("msg_id"):
        return
    p = {"chat_id": t["chat_id"], "message_id": t["msg_id"], "text": text,
         "reply_markup": kb or {"inline_keyboard": []}}
    with _elock(t["id"]):
        for attempt in range(4):
            r = _tgh("editMessageText", **p)
            d = str(r.get("description", ""))
            if r.get("ok") or "not modified" in d:
                return
            flood = "Too Many Requests" in d or _retry_after(r) is not None
            if d.startswith("Bad Request") and not flood:
                logging.warning("games edit failed: %s", r)       # خطای دائمی (پیام حذف شده و…)؛ تلاش مجدد بی‌فایده است
                return
            if attempt < 3:
                time.sleep(min(_retry_after(r) or 1.5 * (attempt + 1), 10) + 0.3)
        logging.warning("games edit failed after retries: %s", r)


def _render(tid):
    """وضعیت «فعلی» میز را از دیتابیس می‌خواند و همان‌جا (زیر قفل) در همان پیام ویرایش می‌کند"""
    with _elock(tid):
        t = _table(tid)
        if not t:
            return
        st = t["state"]
        if st == "play":
            txt, kb = _xo_view(t, _players(tid))
        elif st == "send":
            txt, kb = _send_view(t, _players(tid))
        elif st == "join":
            txt, kb = _join_view(t, _players(tid))
        elif st == "menu":
            txt, kb = _menu_text(), _menu_kb(tid)
        elif st in PRE:
            txt, kb = _setup_view(t)
        else:
            return
        _edit(t, txt, kb)


EXPIRE_NOTE = {"menu": "گردونه", "s": "گردونه", "d": "میز تاس", "x": "میز دوز"}


def _expire_note(t):
    """پنل قبل از شروع بازی منقضی شد: متن میز سر جایش می‌ماند، دکمه‌ها برداشته می‌شود و یک خط انتهای همان پیام اضافه می‌شود"""
    try:
        if t["state"] == "menu" or not t.get("game"):
            body, noun = _menu_text(), EXPIRE_NOTE["menu"]
        else:
            body, noun = _setup_view(t)[0], EXPIRE_NOTE.get(t["game"], "میز")
        _edit(t, f"{body}\n\n🛑 این {noun} دیگر اعتبار ندارد...")
    except Exception:
        logging.exception("expire note")


def _say(chat_id, text, thread_id=None, reply_to=None):
    p = {"chat_id": chat_id, "text": text}
    if thread_id:
        p["message_thread_id"] = thread_id
    if reply_to:
        p["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
    return B.tg("sendMessage", _timeout=NET_TIMEOUT, **p)


# ---------------- متن پنل‌ها ----------------
_MENU_PARTS = {
    "s": "🎰 گردونه شانس\nمحدودیت بازیکن › 1 - 3 بازیکن",
    "d": "🎲 تاس\nمحدودیت بازیکن › 1 - 2 بازیکن",
}


def _menu_text():
    keys = casino_games()
    return ("🃏 کازینو شاهنشاهی 👑\n\n" + "\n\n".join(_MENU_PARTS[k] for k in keys)
            + "\n\n⤵ لطفا قمار مورد نظر را انتخاب کنید.")


def _menu_kb(tid):
    return _kb([_btn(GAMES[k]["emoji"], f"g:sel:{tid}:{k}") for k in casino_games()])


def _owner_line(t):
    return f"👑 سازنده میز ›› {_mention(t['owner'], t['owner_name'])} {t['oemo'] or ''}".rstrip()


def _setup_head(t):
    g = GAMES[t["game"]]
    if t["game"] == "x":
        stake = f"{_t(t['stake'])} شاهی 💎" if t["stake"] else "تعیین نشده ❌"
        return (f"{g['title']}\n\n🛎 لطفا میز دوز XO را بچینید!\n\n{_owner_line(t)}\n🏦 مبلغ ورودی › {stake}")
    stake = f"{_t(t['stake'])} شاهی 💎" if t["stake"] else "تعیین نشده ❌"
    maxp = f"{_n(t['maxp'])} بازیکن" if t["maxp"] else "تعیین نشده ❌"
    return (f"{g['title']}\n\n🛎 لطفا میز قمار را بچینید!\n\n"
            f"🏦 مبلغ ورودی › {stake}\n👑 تعداد بازیکن › {maxp}")


def _setup_view(t):
    tid = t["id"]
    g = GAMES[t["game"]]
    head = _setup_head(t)
    if t["game"] == "x":
        if t["state"] == "stake_wait":
            return (head + f"\n\n‼️ شما درحال تعیین مبلغ ورودی {g['word']} میباشید.\n\n"
                    "🔻 لطفا مبلغ ورودی را در جواب همین پنل وارد کنید.\n"
                    f"حداقل مبلغ › {_n(cv('xmin'))} شاهی",
                    _kb([_btn("بازگشت ◁", f"g:bk:{tid}", B.DANGER)]))
        if not t["stake"]:
            return (head, _kb([_btn("تعیین مبلغ ورودی 💰", f"g:stk:{tid}")],
                              [_btn("بازگشت ◁", f"g:cx:{tid}", B.DANGER)]))
        return (head, _kb([_btn("ساخت بازی دوز XO", f"g:mk:{tid}", B.SUCCESS)],
                          [_btn("تغییر مبلغ ورودی 💰", f"g:stk:{tid}", B.SUCCESS)]))
    if t["state"] == "stake_wait":
        return (head + f"\n\n‼️ شما درحال تعیین مبلغ ورودی {g['word']} میباشید.\n\n"
                "🔻 لطفا مبلغ ورودی را در جواب همین پنل وارد کنید.\n"
                f"حداقل مبلغ › {_n(cv('min'))} شاهی",
                _kb([_btn("بازگشت ◁", f"g:bk:{tid}", B.DANGER)]))
    if t["state"] == "pick":
        nums = [_btn(NUM_EMO[i], f"g:n:{tid}:{i}") for i in range(1, g["maxp"] + 1)]
        return head, _kb(nums, [_btn("بازگشت ◁", f"g:bk:{tid}", B.DANGER)])
    if t["state"] == "mode":
        return (head + "\n\n🎯 لطفا حالت برنده شدن میز را انتخاب کنید:\n"
                "برنده کسی است که تاسش بیشتر / کمتر بیاید.",
                _kb([_btn("بیشترین عدد 🔺️", f"g:md:{tid}:max"), _btn("کمترین عدد 🔻", f"g:md:{tid}:min")],
                    [_btn("بازگشت ◁", f"g:bk:{tid}", B.DANGER)]))
    if not t["stake"]:
        return (head, _kb([_btn("تعیین مبلغ ورودی 💰", f"g:stk:{tid}")],
                          [_btn("بازگشت ◁", f"g:menu:{tid}", B.DANGER)]))
    if not t["maxp"]:
        return (head, _kb([_btn("تعیین تعداد بازیکن 👥️", f"g:np:{tid}")],
                          [_btn("تغییر مبلغ ورودی 💰", f"g:stk:{tid}", B.SUCCESS)]))
    return (head, _kb([_btn("ساخت میز قمار 🃏", f"g:mk:{tid}", B.SUCCESS)],
                      [_btn("تغییر مبلغ ورودی 💰", f"g:stk:{tid}", B.SUCCESS), _btn("تغییر تعداد بازیکن 👑", f"g:np:{tid}", B.SUCCESS)]))


def _mention(uid, name):
    """نام قابل‌کلیک (منشن) — اگر تلگرام نپذیرفت، خودکار بدون منشن ارسال می‌شود"""
    return f'<a href="tg://user?id={int(uid)}">{_html.escape(name or "کاربر", quote=False)}</a>'


def _free_emo(c, tid):
    """ایموجی رندومی که هنوز دست هیچ بازیکنِ این میز نیست"""
    used = {r["emo"] for r in c.execute("SELECT emo FROM g_players WHERE table_id=?", (tid,)).fetchall()}
    free = [e for e in PLAYER_EMOJIS if e not in used]
    return random.choice(free or list(PLAYER_EMOJIS))


def _pname(p):
    return f"{_mention(p['user_id'], p['name'])} {p['emo']}"


ORD = {1: "اول", 2: "دوم", 3: "سوم"}


def _plabel(i, n):
    return f"بازیکن {ORD[i + 1]}" if n > 1 else "بازیکن"


def _reels_text(p, hide=False):
    if hide or p["value"] is None:
        return "⬜ ⬜ ⬜"
    return " ".join(SYM[s] for s in decode_dice(p["value"]))


def _join_view(t, ps):
    g = GAMES[t["game"]]
    if t["game"] == "x":
        txt = (f"{g['short']}\n\n{_owner_line(t)}\n🏦 مبلغ ورودی › {_t(t['stake'])} شاهی 💎\n\n"
               f"⏰️ فقط {_n(cv('join'))} ثانیه فرصت پیوستن دارید…")
        return txt, _kb([_btn("پیوستن به میز 🃏", f"g:jn:{t['id']}", B.SUCCESS)])
    lines = "\n".join(f"👑 {_plabel(i, len(ps))} ›› {_pname(p)}" for i, p in enumerate(ps))
    extra = f"🎯 حالت برد › {_mode_label(t['mode'])}\n" if t["game"] == "d" and t.get("mode") else ""
    txt = (f"{g['short']}\n\n"
           f"🏦 مبلغ ورودی › {_t(t['stake'])} شاهی 💎\n{extra}"
           f"👥️ ظرفیت میز › {_n(len(ps))} از {_n(t['maxp'])}\n\n{lines}\n\n"
           "🔻 برای پیوستن به میز دکمه‌ی زیر را بزنید.\n\n"
           f"⏰️ فقط {_n(cv('join'))} ثانیه فرصت پیوستن دارید…")
    return txt, _kb([_btn("پیوستن به میز 🃏", f"g:jn:{t['id']}", B.SUCCESS)])


def _dice_pick_kb(tid):
    return _kb([_btn("زوج", f"g:pk:{tid}:e"), _btn("فرد", f"g:pk:{tid}:o")],
               [_btn(NUM_EMO[3], f"g:pk:{tid}:3"), _btn(NUM_EMO[2], f"g:pk:{tid}:2"), _btn(NUM_EMO[1], f"g:pk:{tid}:1")],
               [_btn(NUM_EMO[6], f"g:pk:{tid}:6"), _btn(NUM_EMO[5], f"g:pk:{tid}:5"), _btn(NUM_EMO[4], f"g:pk:{tid}:4")])


def _send_view(t, ps):
    """(متن، کیبورد) پنل فاز ارسال"""
    if t["game"] == "s":
        if len(ps) == 1:
            p = ps[0]
            sc = "🎰 در حال چرخش…" if (p["sent"] and not p["shown"]) else _reels_text(p, hide=not (p["sent"] and p["shown"]))
            txt = ("🃏 گردونه شانس 🎰\n\n"
                   f"🏦 مبلغ ورودی › {_t(t['stake'])} شاهی 💎\n"
                   f"👑 بازیکن ›› {_pname(p)}\n🎉 امتیاز ››› {sc}"
                   "\n\n⚠️ لطفا ایموجی '🎰' را در جواب همین پنل ارسال کنید!\n\n"
                   f"⏰️ فقط {_n(cv('send'))} ثانیه فرصت دارید…")
            return txt, None
        blocks = []
        for p in ps:
            if not p["sent"]:
                reels, sc = "⬜️ ⬜️ ⬜️ ...", "هنوز خالیه"
            elif not p["shown"]:
                reels, sc = "🎰 در حال چرخش…", "…"
            else:
                reels, sc = _reels_text(p), _n(p["score"] or 0)
            blocks.append(f"👑 بازیکن ›› {_pname(p)}\n🎰 گردونه ›› {reels}\n🎉 امتیاز ››› {sc}")
        txt = ("🎰 کازینو گردونه شانس 🃏\n\n"
               f"🏦 مبلغ ورودی › {_t(t['stake'])} شاهی 💎\n\n"
               + "\n\n".join(blocks) +
               "\n\n⚠️ لطفا ایموجی '🎰' را در جواب همین پنل ارسال کنید!\n\n"
               f"⏰️ فقط {_n(cv('send'))} ثانیه فرصت دارید…")
        return txt, None
    # تاس
    def num(p):
        if not p["sent"]:
            return "..."
        return NUM_EMO[p["value"]] if p["shown"] else "🎲 در حال چرخش…"
    if len(ps) == 1:
        p = ps[0]
        body = (f"👑 بازیکن › {_pname(p)}\n🎉 انتخاب ›› {_pick_label(p['pick'])}\n🎲 عدد تاس ››› {num(p)}")
        kb = _dice_pick_kb(t["id"]) if (p["pick"] is None and not p["sent"]) else None
        warn = "⚠️ لطفا ایموجی '🎲' را در جواب همین پنل ارسال کنید." if p["pick"] else \
            "⚠️ ابتدا انتخاب کنید، سپس ایموجی '🎲' را در جواب همین پنل ارسال کنید."
    else:
        body = "\n\n".join(f"👑 {_plabel(i, len(ps))} › {_pname(p)}\n🎲 عدد تاس ››› {num(p)}" for i, p in enumerate(ps))
        body = f"🎯 حالت برد ›› {_mode_label(t['mode'])}\n\n" + body
        kb = None
        warn = "⚠️ لطفا ایموجی '🎲' را در جواب همین پنل ارسال کنید."
    txt = ("🃏 کازینو تاس 🎲\n\n"
           f"🏦 مبلغ ورودی ›› {_t(t['stake'])} شاهی 💎\n\n{body}\n\n{warn}\n\n"
           f"⏰️ فقط {_n(cv('send'))} ثانیه فرصت دارید…")
    return txt, kb


def _xo_board_kb(t):
    b = t["board"]
    rows = [[_btn(XO_SYM[b[r * 3 + c]], f"g:xo:{t['id']}:{r * 3 + c}") for c in range(3)] for r in range(3)]
    return _kb(*rows)


def _xo_view(t, ps):
    cur = next((p for p in ps if p["user_id"] == t["turn"]), ps[0])
    lines = "\n".join(f"👑 {_plabel(i, 2)} ›› {_pname(p)}\n🎭 نقش › {XO_SYM[p['pick']]}" for i, p in enumerate(ps))
    txt = (f"{GAMES['x']['short']}\n\n🏦 مبلغ ورودی › {_t(t['stake'])} شاهی 💎\n\n{lines}\n\n"
           f"🎯 نوبت ›› {_pname(cur)}\n\n"
           "‼️ لطفا با کلیک روی خانه های خالی دوز بازی کنید.\n\n"
           f"⏰️ فقط {_n(cv('xo'))} ثانیه فرصت دارید…")
    return txt, _xo_board_kb(t)


def _xo_result(t, ps, winner_uid, timeout):
    b = t["board"]
    rows = "\n".join("".join(XO_SYM[b[r * 3 + c]] for c in range(3)) for r in range(3))
    stake = _t(t["stake"])
    head = f"{GAMES['x']['short']}\n\n🏦 مبلغ ورودی › {stake} شاهی 💎\n\n"
    if winner_uid is None:
        pl = "\n".join(f"👑 بازیکن ›› {_pname(p)}\n🎭 نقش › {XO_SYM[p['pick']]}" for p in ps)
        return (head + pl + f"\n\n🔍 نتیجه میز:\n{rows}\n\n"
                "🃏 بازی مساوی شد ، مبلغ به کیف پول بازمیگردد.")
    pl = "\n".join(f"👑 بازیکن ›› {_pname(p)}\n🎭 نقش › {XO_SYM[p['pick']]}\n"
                    f"📊 وضعیت ››› {'برنده 🏆' if p['user_id'] == winner_uid else 'بازنده ⛔️'}" for p in ps)
    w = next(p for p in ps if p["user_id"] == winner_uid)
    extra = "⏰️ زمان بازی تمام شد؛ بازیکنِ نوبت‌دار بازنده شد.\n\n" if timeout else ""
    return (head + pl + f"\n\n🔍 نتیجه میز:\n{rows}\n\n{extra}"
            f"🏆 برنده نهایی ››› {_pname(w)} 🎉\n🏆 مبلغ دریافتی برنده ››› {_t(w['payout'])} شاهی 💎")


def _slot_block(p, i=0, n=1):
    """بلوک نتیجه‌ی یک بازیکن در گردونه"""
    if p["sent"] and p["value"] is not None:
        reels, mtxt = _reels_text(p), f"({_fm(p['mult'] or 0.0)}X)"
    else:
        reels, mtxt = " ".join([SYM[0]] * 3), "(0.0x)"
    if n == 1:
        return (f"👑 بازیکن ›› {_pname(p)}\n"
                f"🏆 مبلغ دریافتی ››› {_t(p['payout'] or 0)} شاهی 💎 {mtxt}\n\n"
                f"🎉 | {reels}\n✨️ امتیاز: {_n(p['score'] or 0)}")
    return (f"👑 {_plabel(i, n)} ›› {_pname(p)}\n"
            f"🎰 گردونه ›› {reels} {mtxt}\n"
            f"🎉 امتیاز ››› {_n(p['score'] or 0)}")


def _dice_block(t, p, i=0, n=1):
    """(بلوک نتیجه‌ی یک بازیکن در تاس، ضریب)"""
    mtxt = f"({_fm(p['mult'] or 0.0)}X)"
    num = NUM_EMO[p["value"]] if p["sent"] else "تاس ننداخت"
    if n == 1:
        return (f"👑 بازیکن ›› {_pname(p)}\n🎉 انتخاب ›› {_pick_label(p['pick'])}\n🎲 عدد تاس ››› {num}"), mtxt
    return (f"👑 {_plabel(i, n)} ›› {_pname(p)}\n🎲 تاس ››› {num}"), mtxt


# ---------------- ورودی‌ها ----------------
def _gate(uid):
    if B.is_admin(uid):
        return True
    if B.get_setting("bot_enabled", "1") == "0" or B.is_banned(uid):
        return False
    return True


def relevant(m):
    """فیلتر سبک پیش از هر قفل/دیتابیس: فقط پیام‌هایی که به بازی‌ها مربوط‌اند"""
    rp = m.get("reply_to_message")
    if m.get("dice"):
        return bool(rp and (rp.get("from") or {}).get("id") == B.BOT_ID)    # فقط ایموجیِ ریپلای‌شده روی ربات
    t = _norm(m.get("text") or "")
    if not t:
        return False
    if t == TRIGGER or t.lower() in TRIGGERS_XO or t.startswith(XFER_WORD) or t in PROF_SELF or t in PROF_OTHER or t == LB_WORD:
        return True
    return bool(rp and (rp.get("from") or {}).get("id") == B.BOT_ID)


def on_group_message(m):
    u = m.get("from") or {}
    if not u.get("id") or u.get("is_bot"):
        return
    if not _gate(u["id"]):
        return
    if m.get("dice"):
        return _on_dice(m, u)
    text = (m.get("text") or "").strip()
    if not text:
        return
    nt = _norm(text)
    if nt == LB_WORD:
        return _on_lb(m, u)
    if nt in PROF_SELF or nt in PROF_OTHER:
        return _on_profile(m, u, nt in PROF_OTHER)
    if nt == XFER_WORD or nt.startswith(XFER_WORD + " "):
        return _on_transfer(m, u, nt)
    if nt == TRIGGER:
        if not casino_games() or gbanned(u["id"]):
            return          # خاموش یا محروم: بی‌صدا
        return _on_trigger(m, u, "c")
    if nt.lower() in TRIGGERS_XO:
        if not game_on("x") or gbanned(u["id"]):
            return
        return _on_trigger(m, u, "x")
    rp = m.get("reply_to_message")
    if rp and (rp.get("from") or {}).get("id") == B.BOT_ID:
        return _on_reply_text(m, u, rp, text)


def _thread(m):
    return m.get("message_thread_id") if m.get("is_topic_message") else None


def _on_trigger(m, u, kind="c"):
    uid = u["id"]
    chat_id = m["chat"]["id"]
    th = _thread(m)
    left = _cool_left(uid) if kind == "c" else 0     # دوز محدودیت ۲ دقیقه‌ای کازینو را ندارد
    if left > 0:
        _say(chat_id, _cool_msg(left), th, m["message_id"])
        return
    if not B.user_exists(uid):
        _say(chat_id, "👑 سَرورَم ابتدا باید ربات را استارت کنی تا کیف پولت ساخته شود.\n"
                      f"🔻 @{B.BOT_USERNAME}", th, m["message_id"])
        return
    if _active_table_of(uid):
        _say(chat_id, "🃏 شما همین الان پشت یک میز بازی نشسته‌اید سَرورَم!", th, m["message_id"])
        return
    now = time.time()
    ph = ",".join("?" * len(PRE))
    with _Tx() as c:
        olds = c.execute(f"SELECT * FROM g_tables WHERE owner=? AND chat_id=? AND state IN ({ph})",
                         (uid, chat_id, *PRE)).fetchall()
        for o in olds:
            c.execute("UPDATE g_tables SET state='expired' WHERE id=?", (o["id"],))
        if kind == "x":
            cur = c.execute("INSERT INTO g_tables (chat_id, thread_id, owner, owner_name, state, touched, created, "
                            "game, maxp, oemo) VALUES (?,?,?,?, 'setup', ?, ?, 'x', 2, ?)",
                            (chat_id, th, uid, _name(u), now, now, random.choice(PLAYER_EMOJIS)))
        else:
            cur = c.execute("INSERT INTO g_tables (chat_id, thread_id, owner, owner_name, state, touched, created) "
                            "VALUES (?,?,?,?, 'menu', ?, ?)", (chat_id, th, uid, _name(u), now, now))
        tid = cur.lastrowid
    for o in olds:
        _expire_note(o)
        _purge(o["id"])
    t = _table(tid)
    if kind == "x":
        txt, kb = _setup_view(t)
        r = _send(t, txt, kb, reply_to=m["message_id"])
    else:
        r = _send(t, _menu_text(), _menu_kb(tid), reply_to=m["message_id"])
    if r.get("ok"):
        _x("UPDATE g_tables SET msg_id=? WHERE id=?", (r["result"]["message_id"], tid))
    else:
        _x("UPDATE g_tables SET state='expired' WHERE id=?", (tid,))


def _on_reply_text(m, u, rp, text):
    uid = u["id"]
    # پیش‌بررسی سبک (بدون تراکنش نوشتن): ورودی نامعتبر/زیر حداقل = بی‌صدا نادیده گرفته می‌شود
    t0 = _row("SELECT id, owner, game FROM g_tables WHERE chat_id=? AND msg_id=? AND state='stake_wait'",
              (m["chat"]["id"], rp.get("message_id")))
    if not t0 or t0["owner"] != uid:
        return
    if not game_on(t0["game"]):
        return
    val = _parse_int(text)
    if val is None or val < _min_stake(t0["game"]):
        return
    err = None
    with _Tx() as c:
        t = c.execute("SELECT * FROM g_tables WHERE id=? AND state='stake_wait'", (t0["id"],)).fetchone()
        if not t:
            return
        bal = (c.execute("SELECT tokens FROM users WHERE id=?", (uid,)).fetchone() or {"tokens": 0})["tokens"]
        if _max_stake() and val > _max_stake():
            err = f"🛑 حداکثر مبلغ ورودی {_t(_max_stake())} شاهی است."
        elif bal < val:
            err = f"🛑 موجودی شما کافی نیست!\nموجودی فعلی ››› {_t(bal)} شاهی"
        if not err:
            c.execute("UPDATE g_tables SET stake=?, state='setup', touched=? WHERE id=?", (val, time.time(), t["id"]))
    if err:
        _say(t["chat_id"], err, t.get("thread_id"), m["message_id"])
        return
    _render(t["id"])
    B.tg("deleteMessage", _timeout=NET_TIMEOUT, chat_id=t["chat_id"], message_id=m["message_id"])


def _is_forward(m):
    return any(k in m for k in ("forward_origin", "forward_date", "forward_from", "forward_from_chat", "via_bot"))


def _on_dice(m, u):
    """فقط 🎰/🎲 که «در جواب (ریپلای) پنل همین بازی» فرستاده شود و بازی در مرحله‌ی ارسال باشد پذیرفته می‌شود؛
    هر چیز دیگر بی‌صدا نادیده گرفته می‌شود."""
    d = m["dice"]
    emo = d.get("emoji")
    if emo not in ("🎰", "🎲") or _is_forward(m):
        return
    rp = m.get("reply_to_message") or {}
    if (rp.get("from") or {}).get("id") != B.BOT_ID or not rp.get("message_id"):
        return
    uid = u["id"]
    if gbanned(uid):
        return
    pre = _row("SELECT t.id FROM g_tables t JOIN g_players p ON p.table_id=t.id "
               "WHERE p.user_id=? AND t.state='send' AND t.chat_id=? AND t.msg_id=?",
               (uid, m["chat"]["id"], rp["message_id"]))
    if not pre:
        return          # بدون قفل نوشتن رد می‌شود
    with _Tx() as c:
        r = c.execute("SELECT t.* FROM g_tables t JOIN g_players p ON p.table_id=t.id "
                      "WHERE p.user_id=? AND t.state='send' AND t.id=?", (uid, pre["id"])).fetchone()
        if not r or r["chat_id"] != m["chat"]["id"] or r["msg_id"] != rp["message_id"] \
                or GAMES[r["game"]]["emoji"] != emo:
            return
        p = c.execute("SELECT * FROM g_players WHERE table_id=? AND user_id=?", (r["id"], uid)).fetchone()
        mid = m.get("message_id") or 0
        if r.get("msg_id") and mid < r["msg_id"]:
            return      # قبل از ساخت پنل فرستاده شده؛ حساب نمی‌شود
        if p["sent"]:
            # فقط «اولین» ایموجی حساب می‌شود. اگر به‌خاطر هم‌زمانی، پیام اول دیرتر از دومی پردازش شد
            # (message_id کوچک‌تر = زودتر فرستاده شده) و هنوز نتیجه نمایش داده نشده، همان اولی جایگزین می‌شود.
            if (not p["shown"]) and p["mid"] and mid and mid < p["mid"]:
                c.execute("UPDATE g_players SET value=?, mid=? WHERE table_id=? AND user_id=? AND shown=0",
                          (int(d["value"]), mid, r["id"], uid))
            return
        if r["game"] == "d" and r["maxp"] == 1 and not p["pick"]:
            return      # تاس تک‌نفره: تا انتخاب با دکمه‌ها ثبت نشده ورودی پذیرفته نمی‌شود (بدون هشدار)
        c.execute("UPDATE g_players SET sent=1, sent_at=?, value=?, mid=? WHERE table_id=? AND user_id=? AND sent=0",
                  (time.time(), int(d["value"]), mid, r["id"], uid))


# ---------------- 💎 انتقال شاهی در گروه ----------------
XFER_HELP = ("🚥 آموزش استفاده درست از دستور انتقال! 🏦\n"
             "۱. انتقال شاهی {مقدار} {کاربر}\n"
             "۲. کاربر میتونه \"یوزرنیم\" یا \"آیدی عددی\" مقصد باشه یا همچنین میتونید با ریپلای کردن "
             "روی پیام کاربر مقصد را انتخاب کنید.")


def xfer_on():
    return B.get_setting("g_t_on", "1") != "0"


def _fa2en(t):
    return (t or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def _xfer_target(m, rest_tokens):
    """(uid, name) مقصد یا None. اولویت با ریپلای؛ بعد @یوزرنیم یا آیدی عددی."""
    rp = m.get("reply_to_message")
    if rp and "forum_topic_created" not in rp and rp.get("from"):
        f = rp["from"]
        if f.get("is_bot"):
            return "bot"
        return f["id"], _name(f)
    if rest_tokens:
        tok = rest_tokens[0]
        if tok.startswith("@") and len(tok) > 1:
            r = _row("SELECT id, first_name FROM users WHERE lower(username)=lower(?)", (tok[1:],))
            return (r["id"], _name({"first_name": r["first_name"]})) if r else "missing"
        if tok.isdigit():
            r = _row("SELECT id, first_name FROM users WHERE id=?", (int(tok),))
            return (r["id"], _name({"first_name": r["first_name"]})) if r else "missing"
    return None


def _on_transfer(m, u, nt):
    if not xfer_on() or "bk" in B.sections_off():
        return              # خاموش (کلید انتقال گروهی یا بخش «بانک انتقال»): بی‌صدا
    uid = u["id"]
    chat_id = m["chat"]["id"]
    th = _thread(m)
    mid = m["message_id"]
    nt = _fa2en(nt)
    toks = nt.split()
    if len(toks) >= 2 and toks[1] != "شاهی":
        return              # «انتقال دادم…» و مانند آن یعنی گفتگوی عادی
    rest = toks[2:]
    amount = _parse_int(rest[0]) if rest else None      # فقط عدد صحیح (مثل بانک انتقال)
    target = _xfer_target(m, rest[1:]) if amount is not None else None
    if amount is None or target is None:
        _say(chat_id, XFER_HELP, th, mid)
        return
    if target == "bot":
        return
    if target == "missing":
        _say(chat_id, "🛑 کاربر عضو ربات نیست, بهش بگو /start کنه!", th, mid)
        return
    to_id, to_name = target
    if not B.user_exists(uid):
        _say(chat_id, f"👑 ابتدا ربات را استارت کنید: @{B.BOT_USERNAME}", th, mid)
        return
    if not B.user_exists(to_id):
        _say(chat_id, "🛑 کاربر عضو ربات نیست, بهش بگو /start کنه!", th, mid)
        return
    if to_id == uid:
        _say(chat_id, "🛑 نمی‌توانید به خودتان انتقال دهید!", th, mid)
        return
    if B.is_banned(to_id):
        _say(chat_id, "🛑 این کاربر قابل دریافت شاهی نیست.", th, mid)
        return
    mn = float(getattr(B, "MIN_TRANSFER_AMOUNT", 5))
    if amount < mn:
        _say(chat_id, f"🛑 حداقل مبلغ انتقال {_t(mn)} شاهی است.", th, mid)
        return
    if B.get_balance(uid) < amount:
        _say(chat_id, "🛑 موجودی شما کافی نیست!", th, mid)
        return
    e1, e2 = random.sample(PLAYER_EMOJIS, 2)
    now = time.time()
    with _Tx() as c:
        olds = c.execute("SELECT id, chat_id, msg_id FROM g_xfer WHERE sender=? AND state='pending'", (uid,)).fetchall()
        for o in olds:
            c.execute("DELETE FROM g_xfer WHERE id=?", (o["id"],))
        cur = c.execute("INSERT INTO g_xfer (chat_id, thread_id, sender, sname, semo, recipient, rname, remo, amount, "
                        "state, deadline) VALUES (?,?,?,?,?,?,?,?,?, 'pending', ?)",
                        (chat_id, th, uid, _name(u), e1, to_id, to_name, e2, amount, now + cv('xfer')))
        xid = cur.lastrowid
    for o in olds:
        if o.get("msg_id"):
            B.tg("deleteMessage", _timeout=NET_TIMEOUT, chat_id=o["chat_id"], message_id=o["msg_id"])
    x = _row("SELECT * FROM g_xfer WHERE id=?", (xid,))
    r = _send({"chat_id": chat_id, "thread_id": th}, _xfer_text(x, False), _xfer_kb(xid), reply_to=mid)
    if r.get("ok"):
        _x("UPDATE g_xfer SET msg_id=? WHERE id=?", (r["result"]["message_id"], xid))
    else:
        _x("DELETE FROM g_xfer WHERE id=?", (xid,))


def _xfer_people(x):
    return (f"✨️ از {_mention(x['sender'], x['sname'])} {x['semo']} "
            f"به {_mention(x['recipient'], x['rname'])} {x['remo']}")


def _xfer_text(x, done):
    if done:
        return (f"💎 رسید انتقال شاهی 👑\n\n🏦 مبلغ انتقال یافته ››› {_t(x['amount'])} شاهی\n{_xfer_people(x)}\n\n"
                "🎉 با موفقیت انتقال یافت. ✅")
    return (f"💎 انتقال شاهی 👑\n\n🏦 مبلغ درحال انتقال ›› {_t(x['amount'])} شاهی\n{_xfer_people(x)}\n\n"
            "⁉️ آیا از انتقال شاهی هاتون اطمینان دارید؟")


def _xfer_kb(xid):
    return _kb([_btn("❌️", f"g:tx:{xid}:n", B.DANGER), _btn("✅️", f"g:tx:{xid}:y", B.SUCCESS)])


def _xfer_edit(x, text):
    if x.get("msg_id"):
        _tgh("editMessageText", chat_id=x["chat_id"], message_id=x["msg_id"], text=text,
             reply_markup={"inline_keyboard": []})


def _cb_xfer(cq, xid, arg, ans):
    uid = cq["from"]["id"]
    if arg not in ("y", "n"):
        return ans()
    result = None
    with _Tx() as c:
        x = c.execute("SELECT * FROM g_xfer WHERE id=?", (xid,)).fetchone()
        if not x or x["state"] != "pending":
            return ans("⌛ این انتقال دیگر معتبر نیست.", True)
        if x["sender"] != uid:
            return ans("🛑 فقط انتقال‌دهنده می‌تواند تأیید یا لغو کند.", True)
        if time.time() >= x["deadline"]:
            return ans("⌛ این انتقال دیگر معتبر نیست.", True)
        if arg == "n":
            c.execute("DELETE FROM g_xfer WHERE id=?", (xid,))
            result = "cancel"
        else:
            if not _charge_in(c, uid, x["amount"]):
                return ans("🛑 موجودی شما کافی نیست!", True)
            if not c.execute("SELECT 1 FROM users WHERE id=?", (x["recipient"],)).fetchone():
                _pay_in(c, uid, x["amount"])
                return ans("🛑 کاربر عضو ربات نیست, بهش بگو /start کنه!", True)
            _pay_in(c, x["recipient"], x["amount"])
            c.execute("INSERT INTO transfers (sender_id, recipient_id, amount) VALUES (?,?,?)",
                      (uid, x["recipient"], x["amount"]))
            # رسید انتقال‌یافته هرگز پاک نمی‌شود: ردیف با وضعیت done برای همیشه می‌ماند
            c.execute("UPDATE g_xfer SET state='done', deadline=? WHERE id=?", (time.time(), xid))
            result = "ok"
    ans()
    if result == "cancel":
        _xfer_edit(x, "🛑 انتقال شاهی لغو شد.")
    else:
        _xfer_edit(x, _xfer_text(x, True))
        try:        # مثل بانک انتقال: به گیرنده در پیوی اطلاع داده می‌شود
            date_str, time_str = B.jalali_now_strings()
            _tgh("sendMessage", chat_id=x["recipient"],
                 text=f"✅️ مقدار {int(x['amount'])} شاهی از کاربر <code>{int(x['sender'])}</code> دریافت شد.\n"
                      f"⏰️ زمان دریافت: {time_str} - {date_str}")
        except Exception:
            logging.exception("xfer notify")
        try:
            B.rep_ev_transfer(x["sender"], x["recipient"], x["amount"])
        except Exception:
            logging.exception("rep_ev_transfer")


def _tick_xfer(now):
    for x in _rows("SELECT * FROM g_xfer WHERE state='pending' AND deadline<=?", (now,)):
        cur = _x("DELETE FROM g_xfer WHERE id=? AND state='pending'", (x["id"],))
        if cur.rowcount == 1:
            _xfer_edit(x, "🛑 انتقال شاهی خودکار لغو شد.")


# ---------------- 👑 پروفایل شاهنشاهی ----------------
_PROF_LAST = {}


def _rank_of(tokens):
    r = _row("SELECT COUNT(*) AS n FROM users WHERE tokens > ?", (tokens,))
    return (r["n"] if r else 0) + 1


def _profile_text(uid, name, tokens):
    st = {r["game"]: r for r in _rows("SELECT game, wins, losses FROM g_stats WHERE user_id=?", (uid,))}

    def line(k):
        r = st.get(k)
        return f"برد ›› {_n(r['wins'] if r else 0)} باخت ›› {_n(r['losses'] if r else 0)}"
    return ("👑 پروفایل شاهنشاهی\n\n"
            f"👤 کاربر › {_mention(uid, name)} {random.choice(PLAYER_EMOJIS)}\n"
            f"\u200f🪪 آیدی عددی ›› <code>{int(uid)}</code>\n\n"
            f"🏦 موجودی ››› {_t(tokens)} شاهی 💎\n"
            f"🎖️ رتبه › {_n(_lb_rank('t', uid))}ام لیدربرد\n\n"
            "📊 آمار بازی ها\n🃏 کازینو\n"
            f"⤫ 🎲 تاس › {line('d')}\n"
            f"⤫ 🎰 اسلات › {line('s')}\n\n"
            f"⤫🕹 دوز › {line('x')}")


def _on_profile(m, u, other):
    if not feat_on("p"):
        return                      # خاموش از پنل ادمین: بی‌صدا
    now = time.time()
    if now - _PROF_LAST.get(u["id"], 0) < 3:
        return                      # ضد اسپم: بی‌صدا
    chat_id = m["chat"]["id"]
    th = _thread(m)
    mid = m["message_id"]
    if other:
        rp = m.get("reply_to_message")
        if not rp or "forum_topic_created" in rp or not rp.get("from") or rp["from"].get("is_bot"):
            return                  # «پروفایلش» فقط با ریپلای روی یک کاربر
        tu = rp["from"]
    else:
        tu = u
    _PROF_LAST[u["id"]] = now
    row = _row("SELECT tokens FROM users WHERE id=?", (tu["id"],))
    if not row:
        if other:
            _say(chat_id, "🛑 کاربر عضو ربات نیست, بهش بگو /start کنه!", th, mid)
        else:
            _say(chat_id, f"👑 ابتدا ربات را استارت کنید: @{B.BOT_USERNAME}", th, mid)
        return
    text = _profile_text(tu["id"], _name(tu), row["tokens"])
    file_id = None
    try:
        r = B.tg("getUserProfilePhotos", _timeout=NET_TIMEOUT, user_id=tu["id"], limit=1)
        photos = (r.get("result") or {}).get("photos") or []
        if r.get("ok") and photos:
            file_id = photos[0][-1]["file_id"]
    except Exception:
        logging.exception("profile photo")
    base = {"chat_id": chat_id, "reply_parameters": {"message_id": mid, "allow_sending_without_reply": True}}
    if th:
        base["message_thread_id"] = th
    if file_id:
        r = B.tg("sendPhoto", _timeout=NET_TIMEOUT, photo=file_id, caption=text, parse_mode="HTML", **base)
        if r.get("ok"):
            return
        r = B.tg("sendPhoto", _timeout=NET_TIMEOUT, photo=file_id, caption=_plain(text), **base)
        if r.get("ok"):
            return
    _tgh("sendMessage", text=text, **base)


# ---------------- 🏆 لیدربرد جهانی ----------------
LB_FIRST = 5          # صفحه‌ی اول فقط ۵ نفر
LB_PER_PAGE = 10      # صفحه‌های بعدی ۱۰ نفر
LB_MAX = 100          # حداکثر نفرات لیست
LB_TITLES = ["پادشاه شاهنشاهی", "قهرمان شاهنشاهی", "وزیراعظم شاهنشاهی", "وزیر شاهنشاهی", "ارشد شاهنشاهی"]
LB_MEDALS = ["🥇", "🥈", "🥉", "🏅", "🎖"]
LB_EMOJIS = ["🍟", "🍿", "🍱", "🍩", "🍭", "🌽", "🥨", "🥐", "🍔", "🍺", "🍷", "🧸", "🔥", "☃️", "⛄️"]
LB_KINDS = {
    "t": {"btn": "شاهی 💎", "desc": "💎 لیدربرد شاهی ها › ثروتمند ترین های شاهنشاهی با بیشترین شاهی"},
    "r": {"btn": "زیرمجموعه‌گیری 👥️", "desc": "👥️ لیدربرد زیرمجموعه‌گیری › پر سر و صدا ترین های شاهنشاهی با بیشترین دعوت"},
    "q": {"btn": "درخواست JFJ 👑", "desc": "📋 لیدربرد درخواست JFJ › بهترین های شاهنشاهی با بیشترین درخواست"},
    "j": {"btn": "شروع JFJ 🏆", "desc": "🏁 لیدربرد شروع JFJ › فعالترین های شاهنشاهی با بیشترین جفج"},
}
# هر نوع: (کوئری لیست، کوئری ارزش یک کاربر، کوئری تعداد افراد با ارزش بیشتر) ؛ کاربران مسدود در لیست نمی‌آیند
_LB_SQL = {
    "t": ("SELECT id AS uid, first_name, tokens AS v FROM users WHERE COALESCE(banned,0)=0 "
          "ORDER BY tokens DESC, id LIMIT ?",
          "SELECT tokens AS v FROM users WHERE id=?",
          "SELECT COUNT(*) AS n FROM users WHERE COALESCE(banned,0)=0 AND (tokens > ? OR (tokens = ? AND id < ?))"),
    "r": ("SELECT u.id AS uid, u.first_name, COUNT(*) AS v FROM users u JOIN users r ON r.referred_by=u.id "
          "WHERE COALESCE(u.banned,0)=0 GROUP BY u.id ORDER BY v DESC, u.id LIMIT ?",
          "SELECT COUNT(*) AS v FROM users WHERE referred_by=?",
          "SELECT COUNT(*) AS n FROM (SELECT u.id AS uid, COUNT(*) AS c FROM users u JOIN users r ON r.referred_by=u.id "
          "WHERE COALESCE(u.banned,0)=0 GROUP BY u.id) WHERE c > ? OR (c = ? AND uid < ?)"),
    "q": ("SELECT u.id AS uid, u.first_name, COUNT(*) AS v FROM users u JOIN requests q ON q.user_id=u.id "
          "WHERE COALESCE(u.banned,0)=0 GROUP BY u.id ORDER BY v DESC, u.id LIMIT ?",
          "SELECT COUNT(*) AS v FROM requests WHERE user_id=?",
          "SELECT COUNT(*) AS n FROM (SELECT u.id AS uid, COUNT(*) AS c FROM users u JOIN requests q ON q.user_id=u.id "
          "WHERE COALESCE(u.banned,0)=0 GROUP BY u.id) WHERE c > ? OR (c = ? AND uid < ?)"),
    "j": ("SELECT u.id AS uid, u.first_name, COUNT(*) AS v FROM users u JOIN joins j ON j.user_id=u.id "
          "WHERE COALESCE(u.banned,0)=0 GROUP BY u.id ORDER BY v DESC, u.id LIMIT ?",
          "SELECT COUNT(*) AS v FROM joins WHERE user_id=?",
          "SELECT COUNT(*) AS n FROM (SELECT u.id AS uid, COUNT(*) AS c FROM users u JOIN joins j ON j.user_id=u.id "
          "WHERE COALESCE(u.banned,0)=0 GROUP BY u.id) WHERE c > ? OR (c = ? AND uid < ?)"),
}
_LB_LAST = {}


def _lb_rank(kind, uid):
    """رتبه‌ی دقیق = جایگاه واقعی در همان لیستی که نمایش داده می‌شود (ترتیب: ارزش نزولی، سپس آیدی)؛
    پروفایل و لیدربرد هر دو از همین تابع می‌خوانند. برای لیدربردهای شمارشی، ارزش صفر = بدون رتبه (None)"""
    me = _row(_LB_SQL[kind][1], (uid,))
    v = (me["v"] if me else 0) or 0
    if kind != "t" and v <= 0:
        return None
    cnt = _row(_LB_SQL[kind][2], (v, v, uid))
    return (cnt["n"] if cnt else 0) + 1


def _lb_menu_text():
    return ("🏆 لیدربرد جهانی شاهنشاهی 👑\n\n🔻 لطفا نوع لیدربرد را انتخاب کنید 🔍\n\n"
            + "\n".join(LB_KINDS[k]["desc"] for k in ("t", "r", "q", "j")))


def _lb_menu_kb(owner):
    b = lambda k: _btn(LB_KINDS[k]["btn"], f"g:lb:{owner}:{k}:0", B.SUCCESS)
    return _kb([b("t")], [b("q"), b("j")], [b("r")])


def _lb_pages(n):
    return 1 + (max(n - LB_FIRST, 0) + LB_PER_PAGE - 1) // LB_PER_PAGE


def _lb_value_line(kind, v):
    if kind == "t":
        return f"💎 موجودی ›› {_t(v)} شاهی"
    if kind == "r":
        return f"👥️ زیرمجموعه ها ›› {_n(v)} دعوت"
    if kind == "q":
        return f"📋 درخواست ها ›› {_n(v)} درخواست"
    return f"🏁 جفج ›› {_n(v)} جفج رفته"


def _lb_view(kind, page, viewer):
    rows = _rows(_LB_SQL[kind][0], (LB_MAX,))
    pages = _lb_pages(len(rows))
    page = max(0, min(page, pages - 1))
    lo = 0 if page == 0 else LB_FIRST + (page - 1) * LB_PER_PAGE
    hi = LB_FIRST if page == 0 else lo + LB_PER_PAGE
    blocks = []
    cnt = max(0, min(hi, len(rows)) - lo)
    emos = random.sample(LB_EMOJIS, min(cnt, len(LB_EMOJIS)))      # در هر صفحه بدون تکرار؛ فقط اگر مجبور بود تکرار می‌شود
    while len(emos) < cnt:
        emos.append(random.choice(LB_EMOJIS))
    for i in range(lo, min(hi, len(rows))):
        r = rows[i]
        who = f"{_mention(r['uid'], _name({'first_name': r['first_name']}))} {emos[i - lo]}"
        head = (f"{LB_MEDALS[i]} {LB_TITLES[i]} › {who}" if i < len(LB_TITLES)
                else f"🔻 رتبه {_n(i + 1)} › {who}")
        blocks.append(f"{head}\n{_lb_value_line(kind, r['v'])}")
    txt = f"🏆 لیدربرد جهانی شاهنشاهی 👑\n\n{LB_KINDS[kind]['desc']}\n\n"
    txt += "\n\n".join(blocks) if blocks else "🔻 هنوز کاربری در این لیدربرد ثبت نشده است."
    if B.user_exists(viewer):
        rk = _lb_rank(kind, viewer)
        txt += ("\n\n🎖️ رتبه شما › " + (f"{_n(rk)}ام لیدربرد" if rk else "هنوز رتبه‌ای ندارید"))
    nav = []
    if page > 0:
        nav.append(_btn("قبلی ◁", f"g:lb:{viewer}:{kind}:{page - 1}"))
    if page < pages - 1:
        nav.append(_btn("▷ بعدی", f"g:lb:{viewer}:{kind}:{page + 1}"))
    kb = _kb(nav, [_btn("بازگشت ◁", f"g:lb:{viewer}:m:0", B.DANGER)])
    return txt, kb


def _on_lb(m, u):
    if not feat_on("l"):
        return                      # خاموش از پنل ادمین: بی‌صدا
    now = time.time()
    if now - _LB_LAST.get(u["id"], 0) < 3:
        return                      # ضد اسپم: بی‌صدا
    _LB_LAST[u["id"]] = now
    base = {"chat_id": m["chat"]["id"], "thread_id": _thread(m)}
    _send(base, _lb_menu_text(), _lb_menu_kb(u["id"]), reply_to=m["message_id"])


def _cb_lb(cq, owner, parts, ans):
    uid = cq["from"]["id"]
    if not feat_on("l"):
        return ans()
    if uid != owner:
        r = _row("SELECT first_name FROM users WHERE id=?", (owner,))
        return ans(f"🃏 این پنل مخصوص {_name({'first_name': r['first_name'] if r else None})} است. خودتان بنویسید «{LB_WORD}».", True)
    kind = parts[3] if len(parts) > 3 else "m"
    try:
        page = int(parts[4]) if len(parts) > 4 else 0
    except ValueError:
        page = 0
    msg = cq.get("message") or {}
    if not msg.get("message_id"):
        return ans()
    ans()
    if kind == "m":
        txt, kb = _lb_menu_text(), _lb_menu_kb(owner)
    elif kind in LB_KINDS:
        txt, kb = _lb_view(kind, page, uid)
    else:
        return
    _tgh("editMessageText", chat_id=msg["chat"]["id"], message_id=msg["message_id"], text=txt, reply_markup=kb)


# ---------------- کال‌بک‌ها ----------------
def on_callback(cq):
    data = cq.get("data", "")
    cid = cq["id"]
    uid = cq["from"]["id"]

    def ans(text=None, alert=False):
        _later(B.answer_callback, cid, text, alert)

    if not _gate(uid):
        return ans("🚫 دسترسی شما محدود است.", True)
    parts = data.split(":")
    if len(parts) < 3:
        return ans()
    act = parts[1]
    try:
        tid = int(parts[2])
    except ValueError:
        return ans()
    arg = parts[3] if len(parts) > 3 else None

    if act == "lb":
        return _cb_lb(cq, tid, parts, ans)
    if act != "tx" and gbanned(uid):
        return ans()                # محروم از بازی‌ها: بی‌صدا
    if act == "mat":
        return _cb_mon(cq, tid, ans)
    if act == "jn":
        return _cb_join(cq, tid, ans)
    if act == "pk":
        return _cb_pick(cq, tid, arg, ans)
    if act == "xo":
        return _cb_xo(cq, tid, arg, ans)
    if act == "tx":
        return _cb_xfer(cq, tid, arg, ans)

    now = time.time()
    make = False
    cancelled = False
    with _Tx() as c:
        t = c.execute("SELECT * FROM g_tables WHERE id=?", (tid,)).fetchone()
        if not t or t["state"] not in PRE:
            return ans("⌛ این پنل منقضی شده است.", True)
        if t["owner"] != uid:
            return ans(f"🃏 این پنل مخصوص {t['owner_name']} است. خودتان بنویسید «{TRIGGER}».", True)
        if act in ("sel", "mk", "md", "stk", "np", "n") and not game_on(arg if (act == "sel" and arg in GAMES) else t["game"]):
            return ans()        # بازی خاموش شده: بی‌صدا
        U = lambda sql, a: c.execute(sql, a)
        if act == "cx":
            U("UPDATE g_tables SET state='expired' WHERE id=?", (tid,))
            cancelled = True
        elif act == "sel":
            if arg not in ("s", "d") or t["game"] == "x":
                return ans()
            mp = GAMES[arg]["maxp"]
            U("UPDATE g_tables SET game=?, state='setup', mode=NULL, maxp=CASE WHEN maxp>? THEN NULL ELSE maxp END, touched=? WHERE id=?",
              (arg, mp, now, tid))
        elif act == "menu":
            U("UPDATE g_tables SET state='menu', touched=? WHERE id=?", (now, tid))
        elif act == "stk":
            U("UPDATE g_tables SET state='stake_wait', touched=? WHERE id=?", (now, tid))
        elif act == "np":
            U("UPDATE g_tables SET state='pick', mode=NULL, touched=? WHERE id=?", (now, tid))
        elif act == "bk":
            U("UPDATE g_tables SET state='setup', touched=? WHERE id=?", (now, tid))
        elif act == "n":
            if arg not in [str(i) for i in range(1, GAMES[t["game"]]["maxp"] + 1)]:
                return ans()
            U("UPDATE g_tables SET maxp=?, state='setup', mode=NULL, touched=? WHERE id=?", (int(arg), now, tid))
        elif act == "md":
            if arg not in ("max", "min") or t["game"] != "d":
                return ans()
            U("UPDATE g_tables SET mode=?, touched=? WHERE id=?", (arg, now, tid))
            make = True
        elif act == "mk":
            if t["game"] == "d" and t["maxp"] == 2 and not t["mode"] and t["state"] == "setup":
                U("UPDATE g_tables SET state='mode', touched=? WHERE id=?", (now, tid))
            else:
                make = True
        else:
            return ans()
        if make:
            t = c.execute("SELECT * FROM g_tables WHERE id=?", (tid,)).fetchone()
            err = _make_table_in(c, t, uid)
            if err:
                return ans(err, True)
    ans()
    if make:
        return _after_make(tid)
    t = _table(tid)
    if cancelled:
        _edit(t, "❌ میز لغو شد.")
        return _purge(tid)
    _render(tid)


def _make_table_in(c, t, uid):
    """داخل تراکنش: متن خطا یا None. در خطا هیچ تغییری ثبت نمی‌شود (قبل از هر نوشتن چک می‌کنیم)"""
    if t["state"] not in ("setup", "mode") or not t["stake"] or not t["maxp"]:
        return "❌ ابتدا مبلغ ورودی و تعداد بازیکن را تعیین کنید."
    left = _cool_left_c(c, uid) if t["game"] != "x" else 0
    if left > 0:
        return _cool_msg(left)
    if _active_in(c, uid):
        return "🃏 شما همین الان پشت یک میز بازی نشسته‌اید!"
    if not _charge_in(c, uid, t["stake"]):
        return "❌ موجودی شما برای این مبلغ کافی نیست!"
    now = time.time()
    c.execute("INSERT INTO g_players (table_id, user_id, name, emo, stake) VALUES (?,?,?,?,?)",
              (t["id"], uid, _name({"first_name": t["owner_name"]}), t["oemo"] or _free_emo(c, t["id"]), t["stake"]))
    if t["maxp"] == 1:
        c.execute("UPDATE g_tables SET state='send', send_dl=?, touched=? WHERE id=?", (now + cv('send'), now, t["id"]))
    else:
        c.execute("UPDATE g_tables SET state='join', join_dl=?, touched=? WHERE id=?", (now + cv('join'), now, t["id"]))
    return None


def _after_make(tid):
    _render(tid)


def _cb_join(cq, tid, ans):
    uid = cq["from"]["id"]
    with _Tx() as c:
        t = c.execute("SELECT * FROM g_tables WHERE id=?", (tid,)).fetchone()
        if not t or t["state"] != "join":
            return ans("⌛ این میز دیگر باز نیست.", True)
        ps = c.execute("SELECT * FROM g_players WHERE table_id=?", (tid,)).fetchall()
        if any(p["user_id"] == uid for p in ps):
            return ans("🃏 شما همین الان پشت این میز هستید!", True)
        if len(ps) >= t["maxp"]:
            return ans("❌ ظرفیت میز تکمیل است.", True)
        if not c.execute("SELECT 1 FROM users WHERE id=?", (uid,)).fetchone():
            return ans(f"👑 ابتدا ربات را استارت کنید: @{B.BOT_USERNAME}", True)
        # محدودیت ۲ دقیقه‌ای فقط برای «سازنده‌ی میز» است؛ پیوستن به میز دیگران محدودیتی ندارد
        if _active_in(c, uid):
            return ans("🃏 شما همین الان پشت یک میز دیگر نشسته‌اید!", True)
        if not _charge_in(c, uid, t["stake"]):
            return ans(f"❌ موجودی شما برای ورود ({_t(t['stake'])} شاهی) کافی نیست!", True)
        c.execute("INSERT INTO g_players (table_id, user_id, name, emo, stake) VALUES (?,?,?,?,?)",
                  (tid, uid, _name(cq["from"]), _free_emo(c, tid), t["stake"]))
        if len(ps) + 1 >= t["maxp"]:
            now = time.time()
            if t["game"] == "x":
                _start_xo_in(c, t, uid, now)
            else:
                c.execute("UPDATE g_tables SET state='send', send_dl=?, touched=? WHERE id=? AND state='join'",
                          (now + cv('send'), now, tid))
    ans("✅ به میز پیوستید!")
    _after_make(tid)


def _cb_pick(cq, tid, arg, ans):
    uid = cq["from"]["id"]
    if arg not in ("e", "o", "1", "2", "3", "4", "5", "6"):
        return ans()
    with _Tx() as c:
        t = c.execute("SELECT * FROM g_tables WHERE id=?", (tid,)).fetchone()
        if not t or t["state"] != "send" or t["game"] != "d" or t["maxp"] != 1:
            return ans("⌛ این پنل منقضی شده است.", True)
        p = c.execute("SELECT * FROM g_players WHERE table_id=? AND user_id=?", (tid, uid)).fetchone()
        if not p:
            return ans("🃏 این میز مخصوص بازیکن دیگری است.", True)
        if p["pick"] or p["sent"]:
            return ans("✅ انتخاب شما قبلاً ثبت شده است.", True)
        c.execute("UPDATE g_players SET pick=? WHERE table_id=? AND user_id=? AND pick IS NULL", (arg, tid, uid))
    ans("✅ ثبت شد! حالا 🎲 را بفرستید.")
    _render(tid)


# ---------------- دوز (نوبتی، اتمیک) ----------------
def _start_xo_in(c, t, joiner, now):
    """داخل تراکنش: نقش‌ها رندوم، سازنده اول شروع می‌کند"""
    roles = ["X", "O"]
    random.shuffle(roles)
    c.execute("UPDATE g_players SET pick=? WHERE table_id=? AND user_id=?", (roles[0], t["id"], t["owner"]))
    c.execute("UPDATE g_players SET pick=? WHERE table_id=? AND user_id=?", (roles[1], t["id"], joiner))
    c.execute("UPDATE g_tables SET state='play', board='---------', turn=?, send_dl=?, touched=? "
              "WHERE id=? AND state='join'", (t["owner"], now + cv('xo'), now, t["id"]))


def _xo_finish_in(c, t, ps, board, winner_uid):
    """داخل تراکنش: پایان بازی. برنده کل جایزه؛ مساوی = برگشت ورودی هر دو"""
    cur = c.execute("UPDATE g_tables SET state='done', board=? WHERE id=? AND state='play'", (board, t["id"]))
    if cur.rowcount != 1:
        return False
    pot = round(sum(p["stake"] for p in ps), 2)
    for p in ps:
        if winner_uid is None:
            p["payout"] = p["stake"]
        else:
            p["payout"] = pot if p["user_id"] == winner_uid else 0.0
        if p["payout"]:
            _pay_in(c, p["user_id"], p["payout"])
        c.execute("UPDATE g_players SET payout=? WHERE table_id=? AND user_id=?", (p["payout"], t["id"], p["user_id"]))
    _log_in(c, t, ps, "draw" if winner_uid is None else "win")
    return True


def _cb_xo(cq, tid, arg, ans):
    uid = cq["from"]["id"]
    try:
        cell = int(arg)
        assert 0 <= cell <= 8
    except Exception:
        return ans()
    finished = False
    with _Tx() as c:
        t = c.execute("SELECT * FROM g_tables WHERE id=?", (tid,)).fetchone()
        if not t or t["state"] != "play" or t["game"] != "x":
            return ans("⌛ این بازی تمام شده است.", True)
        ps = c.execute("SELECT * FROM g_players WHERE table_id=? ORDER BY rowid", (tid,)).fetchall()
        me = next((p for p in ps if p["user_id"] == uid), None)
        if not me:
            return ans("🃏 شما بازیکن این میز نیستید!", True)
        if t["turn"] != uid:
            return ans("⏳ نوبت شما نیست!", True)
        if time.time() >= t["send_dl"]:
            return ans("⏰️ زمان بازی تمام شد!", True)
        board = t["board"]
        if board[cell] != "-":
            return ans("❌ این خانه پر است!", True)
        board = board[:cell] + me["pick"] + board[cell + 1:]
        t["board"] = board
        w = xo_winner(board)
        if w:
            finished = _xo_finish_in(c, t, ps, board, uid)
            win = uid
        elif "-" not in board:
            finished = _xo_finish_in(c, t, ps, board, None)
            win = None
        else:
            other = next(p for p in ps if p["user_id"] != uid)
            c.execute("UPDATE g_tables SET board=?, turn=?, touched=? WHERE id=? AND state='play' AND turn=?",
                      (board, other["user_id"], time.time(), tid, uid))
    ans()
    t = _table(tid)
    ps = _players(tid)
    if finished:
        _edit(t, _xo_result(t, ps, win, False))
        _purge(tid)
    else:
        _render(tid)


def _xo_timeout(tid):
    """زمان تمام شد: بازیکنِ نوبت‌دار بازنده است"""
    with _Tx() as c:
        t = c.execute("SELECT * FROM g_tables WHERE id=? AND state='play' AND send_dl<=?", (tid, time.time())).fetchone()
        if not t:
            return
        ps = c.execute("SELECT * FROM g_players WHERE table_id=? ORDER BY rowid", (tid,)).fetchall()
        winner = next(p["user_id"] for p in ps if p["user_id"] != t["turn"])
        if not _xo_finish_in(c, t, ps, t["board"], winner):
            return
    t = _table(tid)
    _edit(t, _xo_result(t, _players(tid), winner, True))
    _purge(tid)


# ---------------- تسویه (اتمیک) ----------------
def _settle(tid):
    """پایان بازی: محاسبه، پرداخت، سوزاندن و کول‌داون در «یک تراکنش»؛ فقط یک‌بار اجرا می‌شود."""
    with _Tx() as c:
        cur = c.execute("UPDATE g_tables SET state='done' WHERE id=? AND state='send'", (tid,))
        if cur.rowcount != 1:
            return
        t = c.execute("SELECT * FROM g_tables WHERE id=?", (tid,)).fetchone()
        ps = c.execute("SELECT * FROM g_players WHERE table_id=? ORDER BY rowid", (tid,)).fetchall()
        game = t["game"]
        senders = [p for p in ps if p["sent"]]
        for p in ps:
            p["payout"] = 0.0
            if not p["sent"]:
                p["mult"], p["score"], p["value"] = 0.0, 0, None
            elif game == "s":
                if p["shown"] and p["mult"] is not None and p["score"] is not None:
                    pass                    # همان ضریب/امتیازی که به بازیکنان نمایش داده شد
                else:
                    p["mult"], p["score"] = evaluate(decode_dice(p["value"]))
            else:
                p["mult"] = 0.0
                p["score"] = p["value"] if (len(ps) == 1 or t["mode"] == "max") else -p["value"]
        winners, note = [], ""
        if len(ps) == 1:
            p = ps[0]
            if p["sent"]:
                if game == "d":
                    p["mult"] = dice_solo_mult(p["pick"], p["value"])
                p["payout"] = round(p["stake"] * p["mult"], 2)
        elif len(senders) >= 2:
            best = max(p["score"] for p in senders)
            top = [p for p in senders if p["score"] == best]
            if len(top) > 1:                # مساوی: ورودی همه‌ی ارسال‌کنندگان برمی‌گردد
                note = "draw"
                for p in senders:
                    p["payout"] = p["stake"]
            else:
                winners = top
                pot = round(sum(p["stake"] for p in senders), 2)
                winners[0]["payout"] = pot
                if game == "d":
                    winners[0]["mult"] = round(pot / winners[0]["stake"], 2)
        elif len(senders) == 1:
            senders[0]["payout"] = senders[0]["stake"]
            note = "refund"
        now = time.time()
        for p in ps:
            if p["payout"]:
                _pay_in(c, p["user_id"], p["payout"])
            c.execute("UPDATE g_players SET mult=?, score=?, payout=?, value=? WHERE table_id=? AND user_id=?",
                      (p["mult"], p["score"], p["payout"], p["value"], tid, p["user_id"]))
            if p["user_id"] == t["owner"]:      # فقط سازنده‌ی میز محدود می‌شود
                c.execute("INSERT INTO g_cool (user_id, ts) VALUES (?, ?) "
                          "ON CONFLICT(user_id) DO UPDATE SET ts=excluded.ts", (p["user_id"], now))
        _log_in(c, t, ps, "solo" if len(ps) == 1 else ("win" if winners else (note or "burn")))
    txt = _result_text(t, ps, winners, note)
    _edit(t, txt)
    _purge(tid)


def _result_text(t, ps, winners, note):
    stake = _t(t["stake"])
    n = len(ps)
    if n == 1:
        if t["game"] == "s":
            return (f"🃏 کازینو گردونه شانس 🎰\n\n🏦 مبلغ ورودی › {stake} شاهی 💎\n" + _slot_block(ps[0])).strip()
        body, mtxt = _dice_block(t, ps[0])
        return (f"🃏 کازینو تاس 🎲\n\n🏦 مبلغ ورودی › {stake} شاهی 💎\n"
                f"🏆 مبلغ دریافتی ››› {_t(ps[0]['payout'])} شاهی 💎 {mtxt if ps[0]['sent'] else '(0.0X)'}\n\n{body}")
    # چندنفره
    if t["game"] == "s":
        head = f"🎰 کازینو گردونه شانس 🃏\n\n🏦 مبلغ ورودی › {stake} شاهی 💎\n\n"
        blocks = [_slot_block(p, i, n) for i, p in enumerate(ps)]
    else:
        head = (f"🎲 کازینو تاس 🃏\n\n🏦 مبلغ ورودی › {stake} شاهی 💎\n"
                f"🎯 حالت برد › {_mode_label(t['mode'])}\n\n")
        blocks = [_dice_block(t, p, i, n)[0] for i, p in enumerate(ps)]
    txt = head + "\n\n".join(blocks) + "\n\n"
    if winners:
        txt += (f"🏆 برنده نهایی ››› {_pname(winners[0])} 🎉\n"
                f"🏆 مبلغ دریافتی برنده ››› {_t(winners[0]['payout'])} شاهی 💎")
    elif note == "draw":
        txt += "🃏 بازی مساوی شد ، مبلغ به کیف پول بازمیگردد."
    elif note == "refund":
        txt += "⚠️ بازیکن دیگری ارسال نکرد؛ ورودی شما برگشت داده شد."
    else:
        txt += "🔥 هیچ‌کس ارسال نکرد؛ تمام ورودی‌ها سوخت!"
    return txt.strip()


def _cancel_join(tid, n=1):
    with _Tx() as c:
        cur = c.execute("UPDATE g_tables SET state='cancelled' WHERE id=? AND state='join'", (tid,))
        if cur.rowcount != 1:
            return
        t = c.execute("SELECT * FROM g_tables WHERE id=?", (tid,)).fetchone()
        cps = c.execute("SELECT * FROM g_players WHERE table_id=?", (tid,)).fetchall()
        for p in cps:
            _pay_in(c, p["user_id"], p["stake"])
            p["payout"] = p["stake"]
        _log_in(c, t, cps, "cancel")
    g = GAMES[t["game"]]
    why = "بازیکنی نپیوست" if n <= 1 else "تعداد بازیکنان تکمیل نشد"
    _edit(t, f"{g['short']}\n\n❌ میز بسته شد چون {why}.\n"
             f"💎 {_t(t['stake'])} شاهی به موجودی همه‌ی بازیکنان برگشت.")
    _purge(tid)



# =====================================================================
#  🛠 پنل مدیریت بازی‌ها (فقط ادمین؛ از «تنظیمات عمومی ← 🃏 بازی‌های گروهی»)
# =====================================================================
def feat_on(k):
    """کلیدهای ویژگی‌ها: l لیدربرد ، p پروفایل"""
    return B.get_setting(f"g_{k}_on", "1") != "0"


def _gbanned_list():
    try:
        return {int(x) for x in json.loads(B.get_setting("g_banned", "[]") or "[]")}
    except Exception:
        return set()


def gbanned(uid):
    """محروم‌شده از بازی‌ها (فقط بازی‌ها؛ پروفایل/لیدربرد/انتقال را شامل نمی‌شود)"""
    return uid in _gbanned_list()


# نام، برچسب، واحد، نوع، حداقل، حداکثر، ایموجی
_ACFG = [
    ("max", "حداکثر مبلغ ورودی", "شاهی", "int", 0, 10_000_000, "🔝"),
    ("min", "حداقل ورودی گردونه/تاس", "شاهی", "int", 1, 100_000, "🔻"),
    ("xmin", "حداقل ورودی دوز", "شاهی", "int", 1, 100_000, "❌"),
    ("join", "مهلت پیوستن به میز", "ثانیه", "int", 10, 600, "⏰️"),
    ("send", "مهلت ارسال گردونه/تاس", "ثانیه", "int", 15, 600, "🎰"),
    ("xo", "کل زمان بازی دوز", "ثانیه", "int", 30, 1800, "🕹"),
    ("cool", "کول‌داون سازنده‌ی میز", "ثانیه", "int", 0, 3600, "⏳"),
    ("xfer", "مهلت تأیید انتقال", "ثانیه", "int", 15, 600, "💸"),
    ("stale", "انقضای پنل بی‌فعالیت", "ثانیه", "int", 60, 3600, "⌛"),
    ("dp", "ضریب تاس: زوج/فرد", "X", "float", 0, 20, "🎲"),
    ("dn", "ضریب تاس: عدد ۱ تا ۵", "X", "float", 0, 50, "🔢"),
    ("d6", "ضریب تاس: عدد ۶", "X", "float", 0, 50, "6️⃣"),
]
_ACFG_BY = {r[0]: r for r in _ACFG}


def _fv(v, kind):
    return _n(v) if kind == "int" else B.fa_digits(f"{v:g}")


def _fts(ts):
    dt = __import__("datetime").datetime.fromtimestamp(ts, B.now_local().tzinfo)
    jy, jm, jd = B.gregorian_to_jalali(dt.year, dt.month, dt.day)
    return B.fa_digits(f"{jy:04d}/{jm:02d}/{jd:02d} {dt.strftime('%H:%M')}")


def _back_gm():
    return [_btn("🔙 بازی‌های گروهی", "adm_p:x:gm", B.DANGER)]


def _cfg_page():
    lines = ["⚙️ <b>تنظیمات بازی‌ها</b>", B.LINE]
    for name, label, unit, kind, lo, hi, ico in _ACFG:
        cur = cv(name)
        dflt = float(globals()[_CFGK[name][1]])
        mark = "" if cur == dflt else " ✏️"
        extra = " (0 = بدون سقف)" if name == "max" else ""
        lines.append(f"{ico} {label}: <b>{_fv(cur, kind)}</b> {unit}{mark}{extra}")
    lines.append("\n✏️ = تغییر داده‌شده نسبت به پیش‌فرض.\n👇 <i>برای تغییر هر مورد روی آن بزنید.</i>")
    rows, cur_row = [], []
    for name, label, *_r in _ACFG:
        cur_row.append(_btn(f"{_ACFG_BY[name][6]} {label}", f"adm_p:x:gx_set:{name}", B.SUCCESS))
        if len(cur_row) == 2:
            rows.append(cur_row)
            cur_row = []
    if cur_row:
        rows.append(cur_row)
    rows.append([_btn("♻️ بازگشت همه به پیش‌فرض", "adm_p:x:gx_rst", B.SUCCESS)])
    rows.append(_back_gm())
    return "\n".join(lines), _kb(*rows)


def _rep_page(days):
    dt = B.now_local()
    midnight = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    start = midnight.timestamp() if days == 1 else (midnight - __import__("datetime").timedelta(days=days - 1)).timestamp()
    rows = _rows("SELECT game, kind, stake_total, payout_total, detail FROM g_log WHERE ts>=?", (start,))
    agg, players, closed = {}, set(), 0
    for r in rows:
        if r["kind"] in ("cancel", "admin"):
            closed += 1
            continue
        a = agg.setdefault(r["game"], [0, 0.0, 0.0])
        a[0] += 1
        a[1] += r["stake_total"] or 0
        a[2] += r["payout_total"] or 0
        try:
            for e in json.loads(r["detail"] or "[]"):
                players.add(e[0])
        except Exception:
            pass
    names = {"s": "🎰 گردونه", "d": "🎲 تاس", "x": "❌⭕ دوز", "m": "🎃 هیولا"}
    title = {1: "امروز", 7: "۷ روز اخیر", 30: "۳۰ روز اخیر"}[days]
    lines = [f"📊 <b>گزارش بازی‌های گروهی — {title}</b>", B.LINE]
    ts = tp = tn = 0
    for k in ("s", "d", "x", "m"):
        if k in agg:
            n, st, pa = agg[k]
            ts, tp, tn = ts + st, tp + pa, tn + n
            pr = round(st - pa, 2)
            lines.append(f"{names[k]}: <b>{_n(n)}</b> بازی • ورودی {_t(st)} • پرداختی {_t(pa)} • "
                         f"{'سود' if pr >= 0 else 'ضرر'} ربات {_t(abs(pr))}")
        else:
            lines.append(f"{names[k]}: بدون بازی")
    pr = round(ts - tp, 2)
    lines.append(B.LINE)
    lines.append(f"🧮 جمع: <b>{_n(tn)}</b> بازی • ورودی {_t(ts)} • پرداختی {_t(tp)} شاهی")
    lines.append(f"{'📈 سود' if pr >= 0 else '📉 ضرر'} ربات: <b>{_t(abs(pr))}</b> شاهی")
    lines.append(f"👥 بازیکنان یکتا: {_n(len(players))}")
    lines.append(f"🛑 میزهای لغو/بسته‌شده: {_n(closed)}")
    act = _row("SELECT COUNT(*) AS n FROM g_tables WHERE state IN ('join','send','play')")
    lines.append(f"🎲 میزهای فعال همین الان: {_n(act['n'] if act else 0)}")
    lines.append("\nℹ️ <i>گزارش‌ها از دفتر مالیِ ۳۰ روز اخیر ساخته می‌شود؛ سود/ضرر = ورودی‌ها − پرداخت‌ها.</i>")
    pb = lambda d, tx: _btn(("• " if d == days else "") + tx, f"adm_p:x:gx_rep:{d}")
    return "\n".join(lines), _kb([pb(1, "امروز"), pb(7, "۷ روز"), pb(30, "۳۰ روز")], _back_gm())


_STATE_FA = {"join": "جذب بازیکن", "send": "مرحله ارسال", "play": "در حال بازی"}


def _act_page():
    ts = _rows("SELECT * FROM g_tables WHERE state IN ('join','send','play') ORDER BY id DESC LIMIT 10")
    pre = _row("SELECT COUNT(*) AS n FROM g_tables WHERE state IN ('menu','setup','stake_wait','pick','mode')")
    lines = ["🎲 <b>میزهای فعال</b>", B.LINE]
    rows = []
    if not ts:
        lines.append("هیچ میز فعالی وجود ندارد.")
    for t in ts:
        ps = _players(t["id"])
        em = GAMES[t["game"]]["emoji"] or "❌⭕"
        who = _html.escape(t.get("owner_name") or "—", quote=False)
        lines.append(f"#{t['id']} {em} {_STATE_FA.get(t['state'], t['state'])} • سازنده: {who} (<code>{t['owner']}</code>)\n"
                     f"   ورودی {_t(t['stake'])} شاهی • بازیکن {_n(len(ps))}/{_n(t['maxp'])} • گروه <code>{t['chat_id']}</code>")
    for i in range(0, len(ts), 2):
        rows.append([_btn(f"🛑 بستن #{t['id']}", f"adm_p:x:gx_close:{t['id']}", B.DANGER) for t in ts[i:i + 2]])
    lines.append(f"\n🕓 پنل‌های در حال تنظیم (بدون پول): {_n(pre['n'] if pre else 0)}")
    lines.append("ℹ️ <i>بستن میز، ورودی همه‌ی بازیکنان را کامل برمی‌گرداند و پیام میز را به‌روز می‌کند.</i>")
    if ts:
        rows.append([_btn("🛑 بستن همه‌ی میزها (با بازگشت پول)", "adm_p:x:gx_closeall", B.DANGER)])
    rows.append([_btn("🔄 تازه‌سازی", "adm_p:x:gx_act")])
    rows.append(_back_gm())
    return "\n".join(lines), _kb(*rows)


def admin_close_table(tid, who="مدیریت"):
    """بستن اجباری یک میز فعال با برگشت کامل ورودی همه‌ی بازیکنان؛ True اگر بسته شد"""
    with _Tx() as c:
        cur = c.execute("UPDATE g_tables SET state='cancelled' WHERE id=? AND state IN ('join','send','play')", (tid,))
        if cur.rowcount != 1:
            return False
        t = c.execute("SELECT * FROM g_tables WHERE id=?", (tid,)).fetchone()
        ps = c.execute("SELECT * FROM g_players WHERE table_id=?", (tid,)).fetchall()
        for p in ps:
            _pay_in(c, p["user_id"], p["stake"])
            p["payout"] = p["stake"]
        _log_in(c, t, ps, "admin")
    _edit(t, f"{GAMES[t['game']]['short']}\n\n🛑 این میز توسط مدیریت بسته شد؛ ورودی همه‌ی بازیکنان برگشت داده شد.")
    _purge(tid)
    return True


def _user_page(uid):
    u = _row("SELECT first_name, username, tokens FROM users WHERE id=?", (uid,))
    if not u:
        return "❌ کاربر پیدا نشد.", _kb(_back_gm())
    st = {r["game"]: r for r in _rows("SELECT game, wins, losses FROM g_stats WHERE user_id=?", (uid,))}
    ln = lambda k: f"برد {_n(st[k]['wins'] if k in st else 0)} • باخت {_n(st[k]['losses'] if k in st else 0)}"
    cool = _cool_left(uid)
    banned = gbanned(uid)
    lines = [f"🔎 <b>بازیکن</b>: {_mention(uid, _name({'first_name': u['first_name']}))}",
             f"🆔 آیدی عددی: <code>{uid}</code>" + (f" • @{_html.escape(u['username'])}" if u["username"] else ""),
             f"🏦 موجودی: {_t(u['tokens'])} شاهی",
             f"⏳ کول‌داون: {_fmt_wait(cool) if cool > 0 else 'ندارد'}",
             f"⛔ وضعیت بازی‌ها: {'محروم' if banned else 'آزاد'}", B.LINE,
             f"🎲 تاس: {ln('d')}", f"🎰 گردونه: {ln('s')}", f"🕹 دوز: {ln('x')}", B.LINE, "🧾 <b>آخرین بازی‌ها</b>"]
    shown = 0
    for r in _rows("SELECT ts, game, kind, detail FROM g_log WHERE detail LIKE ? ORDER BY ts DESC LIMIT 60", (f"%[{int(uid)}, %",)):
        try:
            e = next(x for x in json.loads(r["detail"]) if x[0] == uid)
        except Exception:
            continue
        net = round((e[3] or 0) - (e[2] or 0), 2)
        em = {"s": "🎰", "d": "🎲", "x": "🕹"}.get(r["game"], "🃏")
        res = "✅" if net > 0 else ("❌" if net < 0 else "➖")
        lines.append(f"{res} {em} {_fts(r['ts'])} • ورودی {_t(e[2] or 0)} ← دریافتی {_t(e[3] or 0)}")
        shown += 1
        if shown >= 10:
            break
    if not shown:
        lines.append("هنوز بازی‌ای ثبت نشده است.")
    kb = _kb([_btn("⏱ ریست کول‌داون", f"adm_p:x:gx_cdr:{uid}", B.SUCCESS),
              _btn("✅ رفع محرومیت از بازی‌ها" if banned else "⛔ محروم از بازی‌ها", f"adm_p:x:gx_ban:{uid}",
                   B.SUCCESS if banned else B.DANGER)],
             [_btn("🔎 بازیکن دیگر", "adm_p:x:gx_find", B.SUCCESS)], _back_gm())
    return "\n".join(lines), kb


def admin_cb(act, args, admin_id, chat_id):
    """(متن، کیبورد، پیام کوتاه) یا None وقتی خودش پیام ورودی فرستاده است"""
    if act == "gx_set" and args and args[0] in _ACFG_BY:
        name, label, unit, kind, lo, hi, ico = _ACFG_BY[args[0]]
        B.set_state(admin_id, "adm_in", {"name": "gx_set", "key": name, "back": "x"})
        B._hsend(chat_id, f"{ico} <b>{label}</b>\n\nمقدار فعلی: <b>{_fv(cv(name), kind)}</b> {unit}\n"
                          f"بازه‌ی مجاز: {_fv(lo, kind)} تا {_fv(hi, kind)}\n"
                          f"مقدار جدید را به صورت {'عدد صحیح' if kind == 'int' else 'عدد (اعشار مجاز است)'} بفرستید:",
                 _kb([_btn("❌ انصراف", "adm_p:x:gx_cfg", B.DANGER)]))
        return None
    if act in ("gx_mon", "gx_mon_r", "gx_mon_s", "gx_mon_a", "gx_mon_i"):
        B.set_state(admin_id, "admin_panel")
        toast = None
        if act == "gx_mon_i":
            threading.Thread(target=_art_bootstrap, daemon=True, name="art-install").start()
            toast = "⏳ نصب Pillow شروع شد؛ چند دقیقه بعد لیست را به‌روز کنید."
        elif act == "gx_mon_r":
            mon_chats(True)
            toast = "🔄 لیست به‌روز شد."
        elif act in ("gx_mon_s", "gx_mon_a") and args and re.fullmatch(r"-?\d+", args[0]):
            cid = int(args[0])
            if cid not in {c_[0] for c_ in mon_chats()}:
                toast = "ربات در این گروه ادمین نیست."
            elif act == "gx_mon_s":
                toast = mon_send(cid)[1]
            else:
                cur = _mon_auto()
                cur.symmetric_difference_update({cid})
                B.set_setting("g_mon_auto", json.dumps(sorted(cur)))
                toast = "🔁 ارسال خودکار روشن شد." if cid in cur else "⛔ ارسال خودکار خاموش شد."
        return (*_mon_page(), toast)
    if act == "gx_find":
        B.set_state(admin_id, "adm_in", {"name": "gx_find", "back": "x"})
        B._hsend(chat_id, "🔎 <b>جستجوی بازیکن</b>\n\nآیدی عددی یا @یوزرنیم بازیکن را بفرستید:",
                 _kb([_btn("❌ انصراف", "adm_p:x:gm", B.DANGER)]))
        return None
    B.set_state(admin_id, "admin_panel")
    toast = None
    if act == "gx_cfg":
        return (*_cfg_page(), None)
    if act == "gx_rst":
        for name in _CFGK:
            B.set_setting(_CFGK[name][0], "")
        return (*_cfg_page(), "♻️ همه به پیش‌فرض برگشت.")
    if act == "gx_rep":
        d = int(args[0]) if args and args[0] in ("1", "7", "30") else 1
        return (*_rep_page(d), None)
    if act == "gx_act":
        return (*_act_page(), None)
    if act == "gx_close" and args:
        ok_ = admin_close_table(int(args[0]))
        return (*_act_page(), "🛑 میز بسته شد و پول‌ها برگشت." if ok_ else "این میز دیگر فعال نیست.")
    if act == "gx_closeall":
        n = sum(1 for t in _rows("SELECT id FROM g_tables WHERE state IN ('join','send','play')") if admin_close_table(t["id"]))
        return (*_act_page(), f"🛑 {n} میز بسته شد.")
    if act in ("gx_cdr", "gx_ban") and args and args[0].isdigit():
        uid = int(args[0])
        if act == "gx_cdr":
            _x("DELETE FROM g_cool WHERE user_id=?", (uid,))
            toast = "⏱ کول‌داون ریست شد."
        else:
            cur = _gbanned_list()
            cur.symmetric_difference_update({uid})
            B.set_setting("g_banned", json.dumps(sorted(cur)))
            toast = "⛔ محروم شد." if uid in cur else "✅ رفع محرومیت شد."
        return (*_user_page(uid), toast)
    return (*_cfg_page(), None)


def admin_input(chat_id, user, text, data):
    admin_id = user["id"]
    name = data.get("name")
    text = (text or "").strip()
    if name == "gx_find":
        uid = B._find_user(text)
        if not uid:
            B._hsend(chat_id, "❗️ کاربری با این مشخصات پیدا نشد.")
            return
        B.set_state(admin_id, "admin_panel")
        t, k = _user_page(uid)
        B._hsend(chat_id, t, k)
        return
    if name == "gx_set":
        key = data.get("key")
        if key not in _ACFG_BY:
            return
        _n_, label, unit, kind, lo, hi, ico = _ACFG_BY[key]
        v = B.parse_number(text)
        if v is None or v < lo or v > hi or (kind == "int" and v != int(v)):
            B._hsend(chat_id, f"❗️ یک {'عدد صحیح' if kind == 'int' else 'عدد'} بین {_fv(lo, kind)} و {_fv(hi, kind)} بفرستید.")
            return
        mx = v if key == "max" else cv("max")
        mn = v if key == "min" else cv("min")
        xm = v if key == "xmin" else cv("xmin")
        if mx > 0 and (mn > mx or xm > mx):
            B._hsend(chat_id, "❗️ حداقل ورودی نمی‌تواند از حداکثر ورودی بیشتر باشد.")
            return
        B.set_setting(_CFGK[key][0], str(int(v) if kind == "int" else v))
        B.set_state(admin_id, "admin_panel")
        B._hsend(chat_id, f"✅ {label} روی {_fv(v, kind)} {unit} تنظیم شد.")
        t, k = _cfg_page()
        B._hsend(chat_id, t, k)


# ---------------- پردازشگر پس‌زمینه ----------------
def _guard(fn, *a):
    """خطای یک میز نباید پردازش بقیه‌ی میزها را متوقف کند"""
    try:
        fn(*a)
    except Exception:
        logging.exception("games tick item")


def _tick_pre(t, ph, now):
    cur = _x(f"UPDATE g_tables SET state='expired' WHERE id=? AND state IN ({ph})", (t["id"], *PRE))
    if cur.rowcount == 1:
        _expire_note(t)
        _purge(t["id"])


def _tick_join(t, now):
    with _Tx() as c:
        n = c.execute("SELECT COUNT(*) AS n FROM g_players WHERE table_id=?", (t["id"],)).fetchone()["n"]
        moved = False
        full = n >= t["maxp"]       # بازی فقط با «همان تعداد انتخاب‌شده» شروع می‌شود، نه کمتر
        if full:
            cur = c.execute("UPDATE g_tables SET state='send', send_dl=?, touched=? WHERE id=? AND state='join'",
                            (now + cv('send'), now, t["id"]))
            moved = cur.rowcount == 1
    if full:
        if moved:
            _after_make(t["id"])
    else:
        _cancel_join(t["id"], n)


def _tick_send(t, now):
    ps = _players(t["id"])
    changed = False
    for p in ps:
        if p["sent"] and not p["shown"] and now >= (p["sent_at"] or 0) + REVEAL_DELAY:
            if t["game"] == "s":
                mm, sc = evaluate(decode_dice(p["value"]))
                _x("UPDATE g_players SET shown=1, mult=?, score=? WHERE table_id=? AND user_id=?",
                   (mm, sc, t["id"], p["user_id"]))
            else:
                _x("UPDATE g_players SET shown=1 WHERE table_id=? AND user_id=?", (t["id"], p["user_id"]))
            changed = True
    ps = _players(t["id"])
    if not ps:
        return
    if all(p["sent"] and p["shown"] for p in ps) or now >= t["send_dl"]:
        _settle(t["id"])
    elif changed:
        _render(t["id"])


_POOL = ThreadPoolExecutor(6, thread_name_prefix="gtick")
_INFL = set()
_INFL_L = threading.Lock()


def _submit(key, fn, *a):
    """هر میز هم‌زمان فقط یک کار در حال اجرا دارد؛ میزهای مختلف موازی پردازش می‌شوند (تماس کند تلگرام بقیه را معطل نمی‌کند)"""
    with _INFL_L:
        if key in _INFL:
            return None
        _INFL.add(key)

    def run():
        try:
            _guard(fn, *a)
        finally:
            with _INFL_L:
                _INFL.discard(key)
    return _POOL.submit(run)


_LAST_LOGCLEAN = [0.0]
LOG_KEEP_SEC = 30 * 86400


def _tick(wait=True):
    now = time.time()
    ph = ",".join("?" * len(PRE))
    futs = []
    for t in _rows(f"SELECT * FROM g_tables WHERE state IN ({ph}) AND touched<?", (*PRE, now - cv('stale'))):
        futs.append(_submit(("t", t["id"]), _tick_pre, t, ph, now))
    for t in _rows("SELECT * FROM g_tables WHERE state='play' AND send_dl<=?", (now,)):
        futs.append(_submit(("t", t["id"]), _xo_timeout, t["id"]))
    for t in _rows("SELECT * FROM g_tables WHERE state='join' AND join_dl<=?", (now,)):
        futs.append(_submit(("t", t["id"]), _tick_join, t, now))
    for t in _rows("SELECT * FROM g_tables WHERE state='send'"):
        futs.append(_submit(("t", t["id"]), _tick_send, t, now))
    # نظافت: بازی‌های تمام‌شده‌ی جامانده (مثلاً بعد از کرش) و کول‌داون‌های گذشته
    for t in _rows("SELECT id FROM g_tables WHERE state IN ('done','cancelled','expired')"):
        futs.append(_submit(("t", t["id"]), _purge, t["id"]))
    _x("DELETE FROM g_cool WHERE ts<?", (now - cv('cool') - 5,))
    futs.append(_submit(("x",), _tick_xfer, now))
    futs.append(_submit(("m",), _tick_mon, now))
    if now - _LAST_LOGCLEAN[0] > 3600:
        _LAST_LOGCLEAN[0] = now
        _x("DELETE FROM g_log WHERE ts<?", (now - LOG_KEEP_SEC,))
    if wait:
        for f in futs:
            if f is not None:
                f.result()


def worker():
    while True:
        try:
            _tick(wait=False)
        except Exception:
            logging.exception("games worker")
        time.sleep(1)


# ---------------- 🎃 هیولا (باس‌فایت گروهی هالووین) ----------------
_ART_SRC = r'''
"""تصویر هیولای هالووین (باس‌فایت) برای بازی گروهی — با Pillow ساخته می‌شود.
اگر Pillow نصب نباشد، render() مقدار None برمی‌گرداند و ربات فقط متن می‌فرستد."""
import io
import math
import os
import random

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops
    OK = True
except Exception:       # pragma: no cover
    OK = False

W, H = 1024, 576
S = 2                   # ابر-نمونه‌برداری برای لبه‌های نرم
_BASE = {}
_FONT_CANDS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", "/Library/Fonts/Arial Bold.ttf", "C:/Windows/Fonts/arialbd.ttf",
]


def _font(size):
    here = os.path.dirname(os.path.abspath(__file__))
    for p in [os.path.join(here, "static", "monster_font.ttf")] + _FONT_CANDS:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size)
    except Exception:
        return ImageFont.load_default()


PALETTES = [  # (آسمان بالا، آسمان پایین، کدو روشن، کدو تیره، درخشش چشم، هاله)
    ((12, 6, 34), (58, 18, 70), (255, 140, 25), (150, 50, 8), (255, 235, 90), (255, 60, 20)),
    ((6, 12, 38), (24, 38, 84), (255, 120, 20), (140, 40, 6), (140, 255, 90), (90, 255, 120)),
    ((26, 6, 24), (80, 14, 44), (240, 100, 20), (120, 28, 8), (255, 70, 50), (255, 30, 60)),
    ((8, 8, 30), (40, 20, 90), (255, 160, 40), (160, 70, 10), (120, 220, 255), (120, 120, 255)),
]


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _glow(img, xy_draw_fn, blur, strength=1.0):
    """یک لایه‌ی درخشان (بلور) روی تصویر می‌اندازد"""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    xy_draw_fn(d)
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    if strength != 1.0:
        a = layer.getchannel("A").point(lambda v: min(255, int(v * strength)))
        layer.putalpha(a)
    img.alpha_composite(layer)


def _poly_jitter(rng, pts, j):
    return [(x + rng.uniform(-j, j), y + rng.uniform(-j, j)) for x, y in pts]


def _build_base(seed):
    rng = random.Random(seed)
    pal = PALETTES[seed % len(PALETTES)]
    sky_t, sky_b, pk_l, pk_d, eye, aura = pal
    w, h = W * S, H * S
    img = Image.new("RGBA", (w, h))
    px = ImageDraw.Draw(img)
    for y in range(h):                                          # آسمان شب
        px.line([(0, y), (w, y)], fill=_lerp(sky_t, sky_b, (y / h) ** 1.4) + (255,))
    for _ in range(170):                                        # ستاره‌ها
        x, y = rng.randrange(w), rng.randrange(int(h * 0.55))
        r = rng.choice((1, 1, 2, 3))
        c = rng.randrange(140, 255)
        px.ellipse([x - r, y - r, x + r, y + r], fill=(c, c, 255, rng.randrange(120, 255)))
    # ماه بزرگ
    mx, my, mr = int(w * 0.80), int(h * 0.22), int(h * 0.14)
    _glow(img, lambda d: d.ellipse([mx - mr * 2, my - mr * 2, mx + mr * 2, my + mr * 2], fill=(255, 220, 140, 70)), 70)
    px.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=(255, 238, 190, 255))
    for cx, cy, cr in ((-0.35, -0.2, 0.22), (0.25, 0.3, 0.28), (-0.1, 0.45, 0.15), (0.4, -0.3, 0.12)):
        px.ellipse([mx + cx * mr - cr * mr, my + cy * mr - cr * mr, mx + cx * mr + cr * mr, my + cy * mr + cr * mr],
                   fill=(235, 215, 165, 255))
    # ابرهای تیره
    for _ in range(7):
        cx, cy = rng.randrange(w), rng.randrange(int(h * 0.05), int(h * 0.45))
        for k in range(6):
            rr = rng.randrange(50, 120)
            ox = cx + rng.randrange(-180, 180)
            oy = cy + rng.randrange(-20, 20)
            px.ellipse([ox - rr * 1.6, oy - rr * 0.5, ox + rr * 1.6, oy + rr * 0.5], fill=(20, 8, 34, 70))
    # قلعه‌ی شاهنشاهی (چپ)
    cx0 = int(w * 0.06)
    base_y = int(h * 0.78)
    castle = (14, 8, 26, 255)
    px.rectangle([cx0, base_y - 230, cx0 + 330, base_y], fill=castle)
    for tx, th in ((cx0 - 20, 330), (cx0 + 120, 400), (cx0 + 270, 300)):
        px.rectangle([tx, base_y - th, tx + 90, base_y], fill=castle)
        px.polygon([(tx - 14, base_y - th), (tx + 45, base_y - th - 110), (tx + 104, base_y - th)], fill=castle)
    for tx, th in ((cx0 - 20, 330), (cx0 + 120, 400), (cx0 + 270, 300)):
        for wy in (th - 70, th - 150):
            px.rectangle([tx + 34, base_y - wy, tx + 56, base_y - wy + 38], fill=(255, 200, 80, 255))
    # تپه و قبرستان
    px.polygon([(0, h)] + [(x, base_y + 20 + 24 * math.sin(x / 190.0)) for x in range(0, w + 40, 40)] + [(w, h)],
               fill=(10, 6, 18, 255))
    for _ in range(11):
        x = rng.randrange(int(w * 0.40), w)
        y = base_y + 60 + rng.randrange(0, int(h * 0.12))
        tw, th = rng.randrange(34, 56), rng.randrange(52, 86)
        px.rounded_rectangle([x, y - th, x + tw, y], radius=tw // 2, fill=(26, 18, 40, 255))
        px.line([(x + tw // 2, y - th + 14), (x + tw // 2, y - th + 34)], fill=(60, 48, 80, 255), width=3)
    # درخت‌های خشک
    def tree(x, y, ln, ang, dep):
        if dep == 0 or ln < 10:
            return
        ex, ey = x + ln * math.cos(ang), y - ln * math.sin(ang)
        px.line([(x, y), (ex, ey)], fill=(8, 4, 14, 255), width=max(2, dep * 3))
        tree(ex, ey, ln * 0.72, ang + rng.uniform(0.25, 0.6), dep - 1)
        tree(ex, ey, ln * 0.70, ang - rng.uniform(0.25, 0.6), dep - 1)
    tree(int(w * 0.93), base_y + 70, 150, math.pi / 2 + 0.15, 6)
    tree(int(w * 0.42), base_y + 60, 110, math.pi / 2 - 0.1, 5)
    # هاله‌ی پشت هیولا
    bx, by = int(w * 0.52), int(h * 0.56)
    br = int(h * 0.34)
    _glow(img, lambda d: d.ellipse([bx - br * 1.9, by - br * 1.5, bx + br * 1.9, by + br * 1.5], fill=aura + (120,)), 90)
    # پیچک‌ها/بازوهای هیولا با چنگال
    for sgn in (-1, 1):
        pts = []
        for i in range(0, 41):
            t = i / 40
            x = bx + sgn * (br * 0.95 + t * br * 1.35)
            y = by + br * 0.35 - math.sin(t * 2.6) * br * 0.7 + t * br * 0.55
            pts.append((x, y))
        for i in range(len(pts) - 1):
            wd = int((1 - i / 40) * 70 + 18)
            px.line([pts[i], pts[i + 1]], fill=(32, 70, 26, 255), width=wd)
            px.line([pts[i], pts[i + 1]], fill=(60, 120, 40, 255), width=max(2, wd // 3))
        ex, ey = pts[-1]
        for k in (-1, 0, 1):
            ang = math.radians(-70 + k * 35 + (0 if sgn == 1 else 40))
            px.polygon([(ex, ey), (ex + sgn * 70 * math.cos(ang) - 14, ey - 70 * math.sin(ang) - 40),
                        (ex + sgn * 20, ey + 10)], fill=(235, 225, 190, 255))
    # بدنه‌ی کدو
    body = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(body)
    lobes = [(-0.62, 0.78), (-0.31, 0.92), (0.0, 1.0), (0.31, 0.92), (0.62, 0.78)]
    for ox, sc in sorted(lobes, key=lambda z: -abs(z[0])):
        rw, rh = br * 0.62, br * 0.98 * sc
        bd.ellipse([bx + ox * br * 1.5 - rw, by - rh * 0.5 - br * 0.05 - rh * 0.5 + rh * 0.5 - rh * 0.5,
                    bx + ox * br * 1.5 + rw, by + rh * 0.5 + br * 0.05 + rh * 0.5 - rh * 0.5], fill=pk_d + (255,))
    # گرادیان شعاعی روی بدنه
    mask = body.getchannel("A")
    grad = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for k in range(40, 0, -1):
        t = k / 40
        col = _lerp(pk_l, pk_d, t ** 1.3)
        gd.ellipse([bx - br * 1.55 * t - br * 0.1, by - br * 0.95 * t - br * 0.15, bx + br * 1.55 * t - br * 0.1,
                    by + br * 0.95 * t - br * 0.15], fill=col + (255,))
    clipped = Image.new("RGBA", img.size, (0, 0, 0, 0))
    clipped.paste(grad, (0, 0), mask)
    body = clipped
    groove = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gdr = ImageDraw.Draw(groove)
    for ox in (-0.9, -0.45, 0.0, 0.45, 0.9):                     # شیارهای کدو (فقط داخل بدنه)
        cxg = bx + ox * br * 1.45
        gdr.ellipse([cxg - br * 0.30, by - br * 1.05, cxg + br * 0.30, by + br * 0.95], outline=pk_d + (200,), width=14)
    gdr.ellipse([bx - br * 1.62, by - br * 0.88, bx + br * 1.48, by + br * 0.88], outline=(0, 0, 0, 60), width=26)
    ga = ImageChops.multiply(groove.getchannel("A"), body.getchannel("A"))
    groove.putalpha(ga)
    body.alpha_composite(groove)
    img.alpha_composite(body)
    # دمبرگ
    px = ImageDraw.Draw(img)
    stem = [(bx - 30, by - br * 0.92), (bx + 10, by - br * 1.32), (bx + 90, by - br * 1.42), (bx + 70, by - br * 1.24),
            (bx + 40, by - br * 1.2), (bx + 40, by - br * 0.92)]
    px.polygon(stem, fill=(54, 84, 30, 255), outline=(20, 36, 12, 255))
    # چشم‌ها و دهان درخشان
    def facial(d):
        for sgn in (-1, 1):
            ex = bx + sgn * br * 0.52
            ey = by - br * 0.28
            d.polygon([(ex - sgn * br * 0.34, ey + br * 0.10), (ex + sgn * br * 0.30, ey - br * 0.30),
                       (ex + sgn * br * 0.24, ey + br * 0.20)], fill=eye + (255,))
        pts = [(bx - br * 0.95, by + br * 0.18)]
        n = 11
        for i in range(n):
            x0 = bx - br * 0.95 + i * (br * 1.9 / n)
            x1 = bx - br * 0.95 + (i + 0.5) * (br * 1.9 / n)
            pts.append((x0, by + br * (0.18 if i % 2 == 0 else 0.34) + 0))
            pts.append((x1, by + br * 0.52 + (br * 0.10 if i % 2 else 0)))
        pts.append((bx + br * 0.95, by + br * 0.18))
        pts.append((bx + br * 0.5, by + br * 0.78))
        pts.append((bx - br * 0.5, by + br * 0.78))
        d.polygon(pts, fill=eye + (255,))
    _glow(img, lambda d: facial(d), 30, 1.6)
    facial(px)
    dark = (30, 8, 6, 255)                                       # دندان‌ها
    for i in range(10):
        x = bx - br * 0.85 + i * (br * 1.7 / 9)
        up = i % 2 == 0
        y0 = by + br * (0.20 if up else 0.74)
        y1 = y0 + br * (0.22 if up else -0.22)
        px.polygon([(x - br * 0.07, y0), (x + br * 0.07, y0), (x, y1)], fill=dark)
    for sgn in (-1, 1):                                          # مردمک‌های تیره‌ی چشم
        ex = bx + sgn * br * 0.50
        ey = by - br * 0.20
        px.ellipse([ex - 18, ey - 26, ex + 18, ey + 26], fill=dark)
    # خفاش‌ها
    for _ in range(6):
        x, y, sz = rng.randrange(w), rng.randrange(int(h * 0.06), int(h * 0.4)), rng.randrange(26, 60)
        px.polygon([(x, y), (x - sz, y - sz * 0.5), (x - sz * 0.5, y + sz * 0.1), (x, y + sz * 0.35),
                    (x + sz * 0.5, y + sz * 0.1), (x + sz, y - sz * 0.5)], fill=(6, 2, 12, 255))
    # مه پایین
    fog = Image.new("RGBA", img.size, (0, 0, 0, 0))
    fd = ImageDraw.Draw(fog)
    for _ in range(22):
        x, y = rng.randrange(-100, w), int(h * rng.uniform(0.80, 0.98))
        rr = rng.randrange(120, 260)
        fd.ellipse([x - rr, y - rr * 0.25, x + rr, y + rr * 0.25], fill=(190, 180, 220, 26))
    img.alpha_composite(fog.filter(ImageFilter.GaussianBlur(22)))
    vig = Image.new("L", img.size, 0)                            # تاریکی گوشه‌ها
    vd = ImageDraw.Draw(vig)
    vd.ellipse([-w * 0.25, -h * 0.35, w * 1.25, h * 1.35], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(120))
    dark_l = Image.new("RGBA", img.size, (0, 0, 0, 170))
    dark_l.putalpha(ImageChops.invert(vig).point(lambda v: int(v * 0.67)))
    img.alpha_composite(dark_l)
    out = img.resize((W, H), Image.LANCZOS)
    geo = {"bx": bx / S, "by": by / S, "br": br / S}
    return out, geo


def _base(seed):
    k = seed % len(PALETTES)
    if k not in _BASE:
        _BASE[k] = _build_base(k)
    img, geo = _BASE[k]
    return img.copy(), geo


def _text_c(d, xy, text, font, fill, stroke=4, stroke_fill=(0, 0, 0, 255), anchor="mm"):
    d.text(xy, text, font=font, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=stroke_fill)


def render(hp, maxhp, seed=0, hits=(), state="live"):
    """PNG بایت‌ها. hits: فهرست دمیج‌ها (عدد) یا None برای خطا. state: live | dead | safe(هیچ‌کس نجنگید)"""
    if not OK:
        return None
    try:
        img, geo = _base(int(seed))
        d = ImageDraw.Draw(img)
        bx, by, br = geo["bx"], geo["by"], geo["br"]
        if state == "dead":
            gray = img.convert("L").convert("RGBA")
            img = Image.blend(img, gray, 0.78)
            img = Image.blend(img, Image.new("RGBA", img.size, (0, 0, 0, 255)), 0.28)
            d = ImageDraw.Draw(img)
            for _ in range(3):                                   # ترک
                x = bx + random.Random(seed).uniform(-br, br)
                d.line([(x, by - br * 0.6), (x + 40, by), (x - 30, by + br * 0.5)], fill=(255, 255, 255, 200), width=5)
        # نوار جان بالای هیولا
        bw, bh = 520, 38
        x0, y0 = bx - bw / 2, 34
        d.rounded_rectangle([x0 - 6, y0 - 6, x0 + bw + 6, y0 + bh + 6], radius=14, fill=(0, 0, 0, 190))
        frac = max(0.0, min(1.0, hp / float(maxhp or 1)))
        col = (80, 220, 90) if frac > 0.55 else ((250, 190, 40) if frac > 0.25 else (235, 50, 40))
        if frac > 0:
            d.rounded_rectangle([x0, y0, x0 + bw * frac, y0 + bh], radius=10, fill=col + (255,))
        d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=10, outline=(255, 255, 255, 220), width=2)
        f1 = _font(34)
        label = f"HP  {int(max(hp, 0))} / {int(maxhp)}"
        _text_c(d, (bx, y0 + bh / 2 + 1), label, f1, (255, 255, 255, 255), stroke=3)
        # آیکون کدوی کوچک کنار نوار
        ix, iy = x0 - 44, y0 + bh / 2
        d.ellipse([ix - 22, iy - 20, ix + 22, iy + 20], fill=(255, 130, 20, 255), outline=(120, 40, 5, 255), width=3)
        d.polygon([(ix - 10, iy - 8), (ix - 3, iy + 2), (ix - 14, iy + 2)], fill=(30, 10, 0, 255))
        d.polygon([(ix + 10, iy - 8), (ix + 3, iy + 2), (ix + 14, iy + 2)], fill=(30, 10, 0, 255))
        d.rectangle([ix - 3, iy - 30, ix + 5, iy - 18], fill=(60, 100, 30, 255))
        # دمیج‌های پرنده روی هیولا
        f2 = _font(70)
        for i, h_ in enumerate(hits[:3]):
            px_ = bx + (i - 1) * br * 1.0
            py_ = by - br * (0.78 if i % 2 == 0 else 0.55)
            if h_:
                _text_c(d, (px_, py_), f"-{int(h_)}", f2, (255, 60, 50, 255), stroke=8, stroke_fill=(255, 255, 255, 255))
            else:
                _text_c(d, (px_, py_), "MISS", _font(54), (215, 220, 230, 255), stroke=7, stroke_fill=(25, 25, 40, 255))
        if state == "dead":
            _text_c(d, (bx, H * 0.55), "DEFEATED", _font(96), (255, 235, 150, 255), stroke=9, stroke_fill=(70, 20, 0, 255))
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=88, optimize=True)
        return buf.getvalue()
    except Exception:
        import logging
        logging.exception("monster_art.render")
        return None

'''


def _load_art():
    """سازنده‌ی تصویر هیولا (Pillow) — داخل همین فایل است؛ بدون Pillow ربات فقط متن می‌فرستد (دلیل در لاگ)"""
    try:
        import types
        mod = types.ModuleType("monster_art")
        mod.__file__ = __file__
        exec(compile(_ART_SRC, "monster_art(inline)", "exec"), mod.__dict__)
        if not getattr(mod, "OK", False):
            logging.warning("Pillow نصب نیست؛ هیولا بدون تصویر ارسال می‌شود (pip install Pillow)")
            return None
        return mod
    except Exception:
        logging.exception("monster art load failed — هیولا بدون تصویر ارسال می‌شود")
        return None


_art = _load_art()
_ART_ST = {"busy": False, "err": ""}


def _install_pillow():
    """نصب خودکار Pillow (روی Railway/PythonAnywhere/cPanel/aaPanel/سرور؛ چند روش پشت‌سرهم). True اگر import شد"""
    import subprocess
    import sys
    import importlib
    import site
    base = [sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "Pillow"]
    tries = [base, base[:5] + ["--user"] + base[5:], base[:5] + ["--user", "--break-system-packages"] + base[5:],
             base[:5] + ["--break-system-packages"] + base[5:]]
    err = ""
    for cmd in tries:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=420)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            continue
        if r.returncode == 0:
            err = ""
            break
        _ln = (r.stderr or r.stdout or "").strip().splitlines()
        err = _ln[-1] if _ln else "pip failed"
    importlib.invalidate_caches()
    try:
        us = site.getusersitepackages()
        if us and us not in sys.path:
            sys.path.append(us)
    except Exception:
        pass
    try:
        importlib.import_module("PIL")
        return True
    except Exception as e:
        _ART_ST["err"] = (err or str(e))[:200]
        return False


def _art_bootstrap():
    """اگر Pillow نیست، در پس‌زمینه خودش را نصب می‌کند و بعد تصویر هیولا فعال می‌شود (ربات متوقف نمی‌شود)"""
    global _art
    if _art is not None or _ART_ST["busy"]:
        return
    _ART_ST["busy"] = True
    try:
        logging.info("Pillow پیدا نشد؛ نصب خودکار شروع شد…")
        if _install_pillow():
            _art = _load_art()
            logging.info("Pillow نصب شد؛ تصویر هیولا فعال است." if _art else "Pillow نصب شد ولی تصویر فعال نشد.")
        else:
            logging.warning("نصب خودکار Pillow ناموفق بود: %s", _ART_ST["err"])
    except Exception:
        logging.exception("art bootstrap")
    finally:
        _ART_ST["busy"] = False

MON_TTL = 900                 # عمر هر هیولا (ثانیه) — همزمان با فاصله‌ی ارسال خودکار
MON_GAP = 900                 # فاصله‌ی ارسال خودکار (۱۵ دقیقه)
MON_CHANCES = 3               # کل شانس اتک‌های یک هیولا (مشترک بین همه‌ی بازیکن‌ها، نه برای هر نفر)
MON_COST = 1                  # هزینه‌ی هر اتک
MON_HP = (300, 450)
MON_DMG = (110, 150)
MON_HIT = 0.8
MON_REWARD = (4, 7)
MON_LK = 2_000_000_000        # جدا کردن کلید قفل ویرایش از میزها
_CHAT_SEEN = {}
_CL = [None]                  # کش لیست گروه‌های ادمین
_LAST_MONCLEAN = [0.0]

MON_HEAD = "🎃 هیولا درحال حمله به شاهنشاهی است…\n🏆 با کمک مردم شاهنشاهی هیولا رو شکست بدید!\n\n"
MON_COST_LINE = "🏦 هزینه هر اتک به هیولا ››› ۱ شاهی 💎"
MON_HIT_LINES = [
    "با یک گلوله‌ی آتشین درست به پیشانی هیولا زد و {d} از جانش کم کرد! 💥",
    "از لای دود و آتش نشانه گرفت و {d} جان از هیولا گرفت! 🔥",
    "ضربه‌ای سهمگین به شکم هیولا فرود آورد و {d} از نیرویش کاست! ⚡",
    "هیولا را غافلگیر کرد و با تیری نقره‌ای {d} جانش را گرفت! 🌙",
    "جلو دوید، به دندان‌های هیولا شلیک کرد و {d} آسیب زد! 🦷",
    "با نعره‌ای بلند شلیک کرد؛ پوست کدویی هیولا ترک خورد و {d} جان کم شد! 🎯",
    "از پشت دیوار قلعه نشانه رفت و {d} از جان هیولا را سوزاند! 🏰",
]
MON_MISS_LINES = [
    "شلیک کرد اما تیرش در مه شب گم شد و هیولا فقط خندید! 🌫",
    "دستش لرزید و گلوله از کنار گوش هیولا رد شد! 💨",
    "هیولا در آخرین لحظه جاخالی داد و ضربه به تاریکی خورد! 👻",
    "تیرش به دیوار قبرستان خورد و خفاش‌ها پراکنده شدند! 🦇",
    "گلوله‌اش به دمبرگ سبز هیولا خورد اما خراشی هم برنداشت! 🌿",
]


def _tg_files(method, fields, fname, data, timeout=60):
    """ارسال multipart (تصویر) به Bot API؛ همیشه dict برمی‌گرداند و exception پرتاب نمی‌کند"""
    import urllib.request
    import urllib.error
    import hashlib
    import os
    boundary = "----jfjmon" + hashlib.md5(os.urandom(8)).hexdigest()
    body = b""
    for k, v in fields.items():
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n').encode("utf-8")
    body += (f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="{fname}"\r\n'
             f'Content-Type: image/jpeg\r\n\r\n').encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{B.BOT_TOKEN}/{method}", data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8", "replace"))
        except Exception:
            return {"ok": False, "description": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "description": str(e)}


def _bold_cap(cap):
    q = B._boldify("sendPhoto", {"caption": cap, "parse_mode": "HTML"})
    return (q or {"caption": cap})["caption"]


def note_chat(chat):
    """هر گروهی که ربات در آن پیام می‌بیند را (کم‌هزینه) ثبت می‌کند تا ادمین بتواند هیولا بفرستد"""
    try:
        if chat.get("type") not in ("group", "supergroup"):
            return
        cid, now = chat["id"], time.time()
        if now - _CHAT_SEEN.get(cid, 0) < 600:
            return
        _CHAT_SEEN[cid] = now
        _x("INSERT INTO g_chats (chat_id, title, type, seen) VALUES (?,?,?,?) ON CONFLICT(chat_id) DO UPDATE SET "
           "title=excluded.title, type=excluded.type, seen=excluded.seen",
           (cid, (chat.get("title") or "")[:60], chat["type"], now))
    except Exception:
        logging.exception("note_chat")


def on_my_chat_member(u):
    try:
        chat = u.get("chat") or {}
        st = (u.get("new_chat_member") or {}).get("status")
        if chat.get("type") not in ("group", "supergroup"):
            return
        if st in ("administrator", "creator", "member"):
            _CHAT_SEEN.pop(chat["id"], None)
            note_chat(chat)
        elif st in ("left", "kicked"):
            _x("DELETE FROM g_chats WHERE chat_id=?", (chat["id"],))
        _CL[0] = None
    except Exception:
        logging.exception("on_my_chat_member")


def mon_chats(force=False):
    """[(chat_id, عنوان)] گروه‌هایی که ربات در آن‌ها ادمین است (با بررسی زنده؛ ۲ دقیقه کش)"""
    if not force and _CL[0] and time.time() - _CL[0][0] < 120:
        return _CL[0][1]
    known = {r["chat_id"]: r["title"] for r in _rows("SELECT chat_id, title FROM g_chats")}
    ids = dict(known)
    for r in _rows("SELECT DISTINCT chat_id FROM g_tables"):
        ids.setdefault(r["chat_id"], None)
    out = []
    for cid, title in list(ids.items())[:60]:
        r = B.tg("getChatMember", _timeout=8, chat_id=cid, user_id=B.BOT_ID)
        st = (r.get("result") or {}).get("status") if r.get("ok") else None
        if st not in ("administrator", "creator"):
            if not r.get("ok") and re.search(r"not found|kicked|forbidden|deactivated", str(r.get("description", "")), re.I):
                _x("DELETE FROM g_chats WHERE chat_id=?", (cid,))
            continue
        if cid not in known:
            g = B.tg("getChat", _timeout=8, chat_id=cid)
            ch = g.get("result") or {}
            if not g.get("ok") or ch.get("type") not in ("group", "supergroup"):
                continue
            title = ch.get("title")
            _CHAT_SEEN.pop(cid, None)
            note_chat(ch)
        out.append((cid, (title or str(cid))))
    out.sort(key=lambda z: z[1])
    _CL[0] = (time.time(), out)
    return out


def _mon_auto():
    try:
        return {int(x) for x in json.loads(B.get_setting("g_mon_auto", "[]") or "[]")}
    except Exception:
        return set()


def _mon(mid):
    return _row("SELECT * FROM g_mon WHERE id=?", (mid,))


def _mon_hits(mid):
    return _rows("SELECT * FROM g_mon_hits WHERE mon_id=? ORDER BY id", (mid,))


def _mon_view(m):
    """(متن، کیبورد، تصویر) از وضعیت فعلی هیولا"""
    hits = _mon_hits(m["id"])
    chn = _n(max(m["chances"], 0))
    lines = [f"بازیکن {_mention(h['user_id'], h['name'])} {h['emo']} {h['line']}" for h in hits]
    kb = None
    state = "live"
    if m["state"] == "live":
        text = MON_HEAD + f"🔫 شانس های باقی مانده ›› {chn} شانس\n" + ("\n".join(lines) + "\n" if lines else "") + "\n" + MON_COST_LINE
        kb = _kb([_btn("اتک به هیولا  🔫🎃", f"g:mat:{m['id']}", B.DANGER)])
    elif m["state"] == "done":
        w = next((h for h in reversed(hits) if h["user_id"] == m["winner"]), None)
        text = (f"🎃 هیولا پس از {_n(len(hits))} تلاش با موفقیت شکست خورد و به ملکوت بازگشت! 🔥\n\n"
                f"🏆 بازیکن {_mention(m['winner'], (w or {}).get('name'))} {(w or {}).get('emo', '🍟')} شجاعانه در مقابل هیولا ایستاد و اورا شکست داد.\n\n"
                f"🎁 پاداش ››› {_t(m['reward'])} شاهی 💎")
        state = "dead"
    elif hits:
        text = MON_HEAD + f"🔫 شانس های باقی مانده ›› {chn} شانس\n" + "\n".join(lines)
    else:
        text = MON_HEAD + f"🔫 شانس های باقی مانده ›› {chn} شانس\nکسی در مقابل هیولا از شاهنشاهی دفاع نکرد! 🏰\n\n" + MON_COST_LINE
    png = None
    if _art is not None:
        try:
            png = _art.render(max(m["hp"], 0), m["maxhp"], m["seed"], [h["dmg"] if h["hit"] else None for h in hits], state)
        except Exception:
            logging.exception("monster render")
    return text, kb, png


def _mon_post(m, text, kb, png):
    """ارسال اولیه؛ عکس‌دار اگر ممکن بود، وگرنه متن. (ok, message_id, has_photo, توضیح خطا)"""
    p = {"chat_id": m["chat_id"], "reply_markup": json.dumps(kb or {"inline_keyboard": []})}
    if m.get("thread_id"):
        p["message_thread_id"] = m["thread_id"]
    if png:
        f = dict(p, caption=_bold_cap(text), parse_mode="HTML")
        r = _tg_files("sendPhoto", f, "monster.jpg", png)
        if not r.get("ok") and re.search(r"parse|entities", str(r.get("description", "")), re.I):
            r = _tg_files("sendPhoto", dict(p, caption=_plain(text)), "monster.jpg", png)
        if r.get("ok"):
            return True, r["result"]["message_id"], 1, ""
        logging.warning("monster sendPhoto failed: %s", r)
    q = {"chat_id": m["chat_id"], "text": text}
    if m.get("thread_id"):
        q["message_thread_id"] = m["thread_id"]
    if kb:
        q["reply_markup"] = kb
    r = _tgh("sendMessage", **q)
    if r.get("ok"):
        return True, r["result"]["message_id"], 0, ""
    return False, None, 0, str(r.get("description", "نامشخص"))


def mon_send(chat_id, thread_id=None):
    """هیولای تازه در گروه. (ok, پیام)"""
    now = time.time()
    with _Tx() as c:
        if c.execute("SELECT 1 FROM g_mon WHERE chat_id=? AND state='live'", (chat_id,)).fetchone():
            return False, "در این گروه همین الان یک هیولای فعال هست."
        hp = random.randint(*MON_HP)
        cur = c.execute("INSERT INTO g_mon (chat_id, thread_id, state, hp, maxhp, seed, chances, created, expires) "
                        "VALUES (?,?,?,?,?,?,?,?,?)",
                        (chat_id, thread_id, "live", hp, hp, random.randrange(1000), MON_CHANCES, now, now + MON_TTL))
        mid = cur.lastrowid
    m = _mon(mid)
    text, kb, png = _mon_view(m)
    ok_, msg_id, has_photo, err = _mon_post(m, text, kb, png)
    if not ok_:
        _x("DELETE FROM g_mon WHERE id=?", (mid,))
        return False, f"ارسال نشد: {err}"
    _x("UPDATE g_mon SET msg_id=?, has_photo=? WHERE id=?", (msg_id, has_photo, mid))
    return True, "🎃 هیولا فرستاده شد." + ("" if has_photo else " (بدون تصویر؛ Pillow نصب نیست)")


def _mon_render(mid):
    """وضعیت فعلی هیولا را (زیر قفل) روی همان پیام می‌نشاند: ویرایش تصویر + متن"""
    with _elock(MON_LK + mid):
        m = _mon(mid)
        if not m or not m.get("msg_id"):
            return
        text, kb, png = _mon_view(m)
        rm = json.dumps(kb or {"inline_keyboard": []})
        r = {}
        for attempt in range(4):
            if m["has_photo"] and png:
                media = json.dumps({"type": "photo", "media": "attach://photo", "caption": _bold_cap(text), "parse_mode": "HTML"})
                r = _tg_files("editMessageMedia", {"chat_id": m["chat_id"], "message_id": m["msg_id"], "media": media,
                                                   "reply_markup": rm}, "monster.jpg", png)
            elif m["has_photo"]:
                r = _tgh("editMessageCaption", chat_id=m["chat_id"], message_id=m["msg_id"], caption=text,
                         reply_markup=kb or {"inline_keyboard": []})
            else:
                r = _tgh("editMessageText", chat_id=m["chat_id"], message_id=m["msg_id"], text=text,
                         reply_markup=kb or {"inline_keyboard": []})
            d = str(r.get("description", ""))
            if r.get("ok") or "not modified" in d:
                return
            flood = "Too Many Requests" in d or _retry_after(r) is not None
            if d.startswith("Bad Request") and not flood:
                logging.warning("monster edit failed: %s", r)
                if m["has_photo"] and png:      # تصویر ویرایش نشد؛ حداقل متن به‌روز شود
                    r2 = _tgh("editMessageCaption", chat_id=m["chat_id"], message_id=m["msg_id"], caption=text,
                              reply_markup=kb or {"inline_keyboard": []})
                    if not r2.get("ok") and "not modified" not in str(r2.get("description", "")):
                        logging.warning("monster caption fallback failed: %s", r2)
                return
            if attempt < 3:
                time.sleep(min(_retry_after(r) or 1.5 * (attempt + 1), 10) + 0.3)
        logging.warning("monster edit failed after retries: %s", r)


def _cb_mon(cq, mid, ans):
    uid = cq["from"]["id"]
    name = _name(cq["from"])
    now = time.time()
    with _Tx() as c:
        m = c.execute("SELECT * FROM g_mon WHERE id=?", (mid,)).fetchone()
        if not m or m["state"] != "live" or now >= m["expires"] or m["chances"] <= 0:
            return ans("🎃 این هیولا دیگر فعال نیست.", True)
        if not _charge_in(c, uid, MON_COST):
            r = c.execute("SELECT tokens FROM users WHERE id=?", (uid,)).fetchone()
            return ans(f"🛑 موجودی شما کافی نیست!\nموجودی فعلی ››› {_t(r['tokens'] if r else 0)} شاهی", True)
        prev = c.execute("SELECT emo FROM g_mon_hits WHERE mon_id=? AND user_id=? LIMIT 1", (mid, uid)).fetchone()
        used = {r["emo"] for r in c.execute("SELECT emo FROM g_mon_hits WHERE mon_id=?", (mid,)).fetchall()}
        emo = prev["emo"] if prev else random.choice([e for e in PLAYER_EMOJIS if e not in used] or list(PLAYER_EMOJIS))
        hit = random.random() < MON_HIT
        dmg = random.randint(*MON_DMG) if hit else 0
        hp = m["hp"] - dmg
        line = random.choice(MON_HIT_LINES).format(d=_n(dmg)) if hit else random.choice(MON_MISS_LINES)
        chances = m["chances"] - 1
        c.execute("INSERT INTO g_mon_hits (mon_id, user_id, name, emo, hit, dmg, line, ts) VALUES (?,?,?,?,?,?,?,?)",
                  (mid, uid, name, emo, int(hit), dmg, line, now))
        state, reward = "live", 0
        if hp <= 0:
            state, reward = "done", float(random.randint(*MON_REWARD))
            _pay_in(c, uid, reward)
        elif chances <= 0:
            state = "fail"
        c.execute("UPDATE g_mon SET hp=?, chances=?, state=?, winner=?, reward=? WHERE id=?",
                  (hp, chances, state, uid if state == "done" else None, reward, mid))
        if state != "live":
            _mon_log_in(c, m, state, reward)
        ans("💥 ضربه خورد!" if hit else "💨 خطا رفت!")
        _later(_mon_render, mid)


def _mon_log_in(c, m, state, reward):
    """دفتر مالی: ورودی = تعداد اتک‌ها، پرداختی = جایزه‌ی برنده"""
    hs = c.execute("SELECT user_id, name, COUNT(*) n FROM g_mon_hits WHERE mon_id=? GROUP BY user_id", (m["id"],)).fetchall()
    win = c.execute("SELECT winner FROM g_mon WHERE id=?", (m["id"],)).fetchone()
    wid = win["winner"] if win else None
    det = [[h["user_id"], h["name"], float(h["n"] * MON_COST), float(reward) if h["user_id"] == wid else 0.0, 1] for h in hs]
    c.execute("INSERT INTO g_log (ts, game, chat_id, tid, kind, stake_total, payout_total, detail) VALUES (?,?,?,?,?,?,?,?)",
              (time.time(), "m", m["chat_id"], m["id"], state, round(sum(e[2] for e in det), 2), round(float(reward), 2),
               json.dumps(det, ensure_ascii=False)))


def _mon_expire(mid):
    with _Tx() as c:
        m = c.execute("SELECT * FROM g_mon WHERE id=? AND state='live'", (mid,)).fetchone()
        if not m:
            return
        n = c.execute("SELECT COUNT(*) n FROM g_mon_hits WHERE mon_id=?", (mid,)).fetchone()["n"]
        st = "fail" if n else "idle"
        c.execute("UPDATE g_mon SET state=? WHERE id=?", (st, mid))
        if n:
            _mon_log_in(c, m, st, 0.0)
        _later(_mon_render, mid)


def _mon_auto_send(cid):
    ok_, msg = mon_send(cid)
    if not ok_:
        logging.warning("auto monster %s: %s", cid, msg)


def _tick_mon(now):
    for m in _rows("SELECT id FROM g_mon WHERE state='live' AND expires<=?", (now,)):
        _mon_expire(m["id"])
    auto = _mon_auto()
    if auto:
        try:
            last = json.loads(B.get_setting("g_mon_last", "{}") or "{}")
        except Exception:
            last = {}
        changed = False
        for cid in auto:
            if now - float(last.get(str(cid), 0)) >= MON_GAP:
                last[str(cid)] = now
                changed = True
                if not _row("SELECT 1 x FROM g_mon WHERE chat_id=? AND state='live'", (cid,)):
                    _mon_auto_send(cid)
        if changed:
            B.set_setting("g_mon_last", json.dumps(last))
    if now - _LAST_MONCLEAN[0] > 3600:
        _LAST_MONCLEAN[0] = now
        cut = now - 7 * 86400
        _x("DELETE FROM g_mon_hits WHERE mon_id IN (SELECT id FROM g_mon WHERE state!='live' AND created<?)", (cut,))
        _x("DELETE FROM g_mon WHERE state!='live' AND created<?", (cut,))


def _mon_page():
    auto = _mon_auto()
    chats = mon_chats()[:20]
    live = _rows("SELECT id, chat_id, hp, maxhp, chances FROM g_mon WHERE state='live'")
    lines = ["🎃 <b>هیولا (باس‌فایت هالووین)</b>", B.LINE,
             f"هر هیولا {B._rp_n(MON_CHANCES)} شانس مشترک دارد • هزینه‌ی هر اتک {B._rp_n(MON_COST)} شاهی • "
             f"احتمال برخورد {B._rp_n(int(MON_HIT * 100))}٪ • جایزه‌ی کشنده {B._rp_n(MON_REWARD[0])} تا {B._rp_n(MON_REWARD[1])} شاهی • "
             f"عمر هیولا {B._rp_n(MON_TTL // 60)} دقیقه.",
             f"🟢 هیولای فعال الان: <b>{B._rp_n(len(live))}</b>",
             "🔁 «خودکار» یعنی هر ۱۵ دقیقه یک هیولا برای آن گروه فرستاده شود.",
             "ℹ️ فقط گروه‌هایی که ربات در آن‌ها ادمین است نمایش داده می‌شوند.",
             ("🖼 تصویر هیولا: ✅ فعال" if _art is not None else
              ("🖼 تصویر هیولا: ⏳ در حال نصب خودکار Pillow… چند دقیقه بعد «به‌روزرسانی» را بزنید." if _ART_ST["busy"] else
               "🖼 تصویر هیولا: ⚠️ غیرفعال (Pillow نصب نیست)" + (f"\nخطا: <code>{_html.escape(_ART_ST['err'], quote=False)}</code>" if _ART_ST["err"] else "")))]
    if not chats:
        lines.append("\n❗️ گروهی پیدا نشد. ربات را در گروه ادمین کنید و یک پیام در گروه بفرستید، بعد «به‌روزرسانی» را بزنید.")
    rows = []
    for cid, title in chats:
        on = cid in auto
        rows.append([_btn("🎃 " + _html.unescape(title)[:22], f"adm_p:x:gx_mon_s:{cid}", B.SUCCESS),
                     _btn("🔁 خودکار " + ("✅" if on else "⛔"), f"adm_p:x:gx_mon_a:{cid}", B.SUCCESS if on else B.DANGER)])
    if _art is None and not _ART_ST["busy"]:
        rows.append([_btn("🖼 نصب خودکار Pillow", "adm_p:x:gx_mon_i", B.SUCCESS)])
    rows.append([_btn("🔄 به‌روزرسانی لیست", "adm_p:x:gx_mon_r", B.SUCCESS)])
    rows.append(_back_gm())
    return "\n".join(lines), _kb(*rows)


# ---------------- گزارش شبانه‌ی کازینو ----------------
def casino_day_block(day):
    """بخش کازینو برای گزارش شبانه (HTML)؛ رشته‌ی خالی اگر آن روز بازی‌ای نبوده"""
    from datetime import datetime
    d0 = datetime.fromisoformat(day).replace(tzinfo=B.ZoneInfo(B.TIMEZONE)).timestamp()
    rows = _rows("SELECT * FROM g_log WHERE ts>=? AND ts<?", (d0, d0 + 86400))
    rows = [r for r in rows if r["kind"] != "cancel"]
    if not rows:
        return ""
    names = {"s": "🎰 گردونه", "d": "🎲 تاس", "x": "❌⭕ دوز", "m": "🎃 هیولا"}
    agg, big = {}, None
    for r in rows:
        a = agg.setdefault(r["game"], [0, 0.0, 0.0])
        a[0] += 1
        a[1] += r["stake_total"] or 0
        a[2] += r["payout_total"] or 0
        try:
            for uid, nm, stk, pay, _sent in json.loads(r["detail"] or "[]"):
                gain = (pay or 0) - (stk or 0)
                if big is None or gain > big[0]:
                    big = (gain, nm, r["game"])
        except Exception:
            pass
    lines = []
    tot_s = tot_p = 0.0
    for k in ("s", "d", "x", "m"):
        if k in agg:
            n, st, pa = agg[k]
            tot_s += st
            tot_p += pa
            lines.append(f"• {names[k]}: {B._rp_n(n)} بازی • ورودی {B._rp_t(st)} • پرداختی {B._rp_t(pa)}")
    prof = round(tot_s - tot_p, 2)
    sign = "سود ربات" if prof >= 0 else "ضرر ربات"
    txt = "🃏 <b>کازینو</b>\n" + "\n".join(lines) + f"\n• {sign}: {B._rp_t(abs(prof))} شاهی"
    if big and big[0] > 0:
        txt += f"\n• بزرگ‌ترین برد: {_html.escape(big[1] or 'کاربر', quote=False)} ({B._rp_t(big[0])} شاهی) در {names.get(big[2], '')}"
    return txt + "\n\n"


def start():
    threading.Thread(target=worker, daemon=True, name="games").start()
    if _art is None:
        threading.Thread(target=_art_bootstrap, daemon=True, name="art-install").start()
