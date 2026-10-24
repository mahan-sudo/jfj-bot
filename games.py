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
import threading
import time

B = None            # ماژول bot_test
_LK = threading.RLock()   # علاوه بر قفل دیتابیس؛ تراکنش‌های هم‌پردازشی را صف می‌کند

# ---------------- تنظیمات ----------------
TRIGGER = "کازینو شاهی"          # فقط خودِ همین متن (نه «حاوی» آن)
TRIGGER_XO = "دوز شاهی"
XO_MIN_STAKE = 2
XFER_SEC = 60                 # فرصت تأیید انتقال
XFER_WORD = "انتقال"
XO_SEC = 150                  # کل زمان بازی دوز؛ بعد از آن بازیکنِ نوبت‌دار بازنده است
MIN_STAKE = 5
MAX_STAKE_DEFAULT = 1000      # سقف مبلغ ورودی؛ کلید تنظیمات casino_max (0 = بدون سقف)
JOIN_SEC = 60
SEND_SEC = 60
COOLDOWN_SEC = 120
REVEAL_DELAY = 3.6            # صبر برای تمام شدن انیمیشن قبل از نمایش نتیجه
STALE_SEC = 600
PLAYER_EMOJIS = "🍟🍿🍱🍩🍭"
PRE = ("menu", "setup", "stake_wait", "pick", "mode")      # مراحل قبل از ساخت میز (بدون پول)
DICE_MULT_PAIR = 1.9          # تاس تک‌نفره: زوج/فرد
DICE_MULT_NUM = 5.5           # تاس تک‌نفره: حدس عدد دقیق

# گردونه: 0=BAR 1=انگور 2=لیمو 3=هفت
SYM = {0: "ʙᴀʀ", 1: "🍇", 2: "🍋", 3: "7️⃣"}
MULT = {0: 0.0, 1: 1.0, 2: 1.5, 3: 2.0}
NUM_EMO = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣"}

GAMES = {
    "s": {"emoji": "🎰", "title": "🃏 کازینو گردونه شانس 🎰", "short": "🃏 گردونه شانس 🎰", "maxp": 3, "word": "گردونه"},
    "d": {"emoji": "🎲", "title": "🃏 کازینو تاس 🎲", "short": "🃏 کازینو تاس 🎲", "maxp": 2, "word": "تاس"},
    "x": {"emoji": "", "title": "🕹 دوز شاهنشاهی XO", "short": "🕹 دوز شاهنشاهی XO", "maxp": 2, "word": "دوز",
          "min": XO_MIN_STAKE, "trigger": TRIGGER_XO},
}
XO_SYM = {"X": "❌️", "O": "⭕️", "-": "◻️"}
XO_LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6))


def _min_stake(game):
    return GAMES.get(game, {}).get("min", MIN_STAKE)


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
        return DICE_MULT_PAIR if value % 2 == 0 else 0.0
    if pick == "o":
        return DICE_MULT_PAIR if value % 2 == 1 else 0.0
    try:
        return DICE_MULT_NUM if int(pick) == value else 0.0
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


def enabled():
    return B.get_setting("casino_on", "1") != "0"


def game_on(key):
    """کلید بازی: 's' گردونه، 'd' تاس، 'x' دوز. خاموش = ربات برای ساخت میز جدید اصلاً پاسخ نمی‌دهد"""
    return enabled() and B.get_setting(f"g_{key}_on", "1") != "0"


def casino_games():
    return [k for k in ("s", "d") if game_on(k)]


def _max_stake():
    try:
        return float(B.get_setting("casino_max", MAX_STAKE_DEFAULT))
    except Exception:
        return MAX_STAKE_DEFAULT


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
        c.execute("CREATE INDEX IF NOT EXISTS g_tables_state ON g_tables(state)")
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
    """بازیِ تمام‌شده (برد/باخت/مساوی/لغو/منقضی) کاملاً از دیتابیس ربات پاک می‌شود؛ فقط پیام داخل گروه می‌ماند"""
    try:
        with _Tx() as c:
            c.execute("DELETE FROM g_players WHERE table_id=?", (tid,))
            c.execute("DELETE FROM g_tables WHERE id=? AND state IN ('done','cancelled','expired')", (tid,))
    except Exception:
        logging.exception("games purge")


def _table(tid):
    return _row("SELECT * FROM g_tables WHERE id=?", (tid,))


def _players(tid):
    return _rows("SELECT * FROM g_players WHERE table_id=? ORDER BY rowid", (tid,))


def _active_in(c, uid):
    return c.execute("SELECT t.id FROM g_tables t JOIN g_players p ON p.table_id=t.id "
                     "WHERE p.user_id=? AND t.state IN ('join','send','play')", (uid,)).fetchone()


def _cool_left_c(c, uid):
    r = c.execute("SELECT ts FROM g_cool WHERE user_id=?", (uid,)).fetchone()
    return max(0, COOLDOWN_SEC - (time.time() - r["ts"])) if r else 0


def _cool_left(uid):
    r = _row("SELECT ts FROM g_cool WHERE user_id=?", (uid,))
    return max(0, COOLDOWN_SEC - (time.time() - r["ts"])) if r else 0


def _active_table_of(uid):
    return _row("SELECT t.* FROM g_tables t JOIN g_players p ON p.table_id=t.id "
                "WHERE p.user_id=? AND t.state IN ('join','send','play')", (uid,))


def _pay_in(c, uid, amount):
    c.execute("UPDATE users SET tokens = tokens + ? WHERE id=?", (amount, uid))


def _charge_in(c, uid, amount):
    cur = c.execute("UPDATE users SET tokens = tokens - ? WHERE id=? AND tokens >= ?", (amount, uid, amount))
    return cur.rowcount == 1


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


def _edit(t, text, kb=None):
    if not t.get("msg_id"):
        return
    p = {"chat_id": t["chat_id"], "message_id": t["msg_id"], "text": text,
         "reply_markup": kb or {"inline_keyboard": []}}
    r = _tgh("editMessageText", **p)
    if not r.get("ok") and "not modified" not in str(r.get("description", "")):
        logging.warning("games edit failed: %s", r)


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
                    f"حداقل مبلغ › {_n(XO_MIN_STAKE)} شاهی",
                    _kb([_btn("بازگشت ◁", f"g:bk:{tid}", B.DANGER)]))
        if not t["stake"]:
            return (head, _kb([_btn("تعیین مبلغ ورودی 💰", f"g:stk:{tid}")],
                              [_btn("بازگشت ◁", f"g:cx:{tid}", B.DANGER)]))
        return (head, _kb([_btn("ساخت بازی دوز XO", f"g:mk:{tid}", B.SUCCESS)],
                          [_btn("تغییر مبلغ ورودی 💰", f"g:stk:{tid}", B.SUCCESS)]))
    if t["state"] == "stake_wait":
        return (head + f"\n\n‼️ شما درحال تعیین مبلغ ورودی {g['word']} میباشید.\n\n"
                "🔻 لطفا مبلغ ورودی را در جواب همین پنل وارد کنید.\n"
                f"حداقل مبلغ › {_n(MIN_STAKE)} شاهی",
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
               f"⏰️ فقط {_n(JOIN_SEC)} ثانیه فرصت پیوستن دارید…")
        return txt, _kb([_btn("پیوستن به میز 🃏", f"g:jn:{t['id']}", B.SUCCESS)])
    lines = "\n".join(f"👑 {_plabel(i, len(ps))} ›› {_pname(p)}" for i, p in enumerate(ps))
    extra = f"🎯 حالت برد › {_mode_label(t['mode'])}\n" if t["game"] == "d" and t.get("mode") else ""
    txt = (f"{g['short']}\n\n"
           f"🏦 مبلغ ورودی › {_t(t['stake'])} شاهی 💎\n{extra}"
           f"👥️ ظرفیت میز › {_n(len(ps))} از {_n(t['maxp'])}\n\n{lines}\n\n"
           "🔻 برای پیوستن به میز دکمه‌ی زیر را بزنید.\n\n"
           f"⏰️ فقط {_n(JOIN_SEC)} ثانیه فرصت پیوستن دارید…")
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
                   f"⏰️ فقط {_n(SEND_SEC)} ثانیه فرصت دارید…")
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
               f"⏰️ فقط {_n(SEND_SEC)} ثانیه فرصت دارید…")
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
           f"⏰️ فقط {_n(SEND_SEC)} ثانیه فرصت دارید…")
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
           f"⏰️ فقط {_n(XO_SEC)} ثانیه فرصت دارید…")
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
    if m.get("dice"):
        return True
    t = _norm(m.get("text") or "")
    if not t:
        return False
    if t in (TRIGGER, TRIGGER_XO) or t.startswith(XFER_WORD):
        return True
    rp = m.get("reply_to_message")
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
    if nt == XFER_WORD or nt.startswith(XFER_WORD + " "):
        return _on_transfer(m, u, nt)
    if nt == TRIGGER:
        if not casino_games():
            return          # خاموش: بی‌صدا
        return _on_trigger(m, u, "c")
    if nt == TRIGGER_XO:
        if not game_on("x"):
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
        if o.get("msg_id"):
            B.tg("deleteMessage", _timeout=NET_TIMEOUT, chat_id=chat_id, message_id=o["msg_id"])
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
    val = _parse_num(text)
    if val is None or val < _min_stake(t0["game"]):
        return
    err = None
    with _Tx() as c:
        t = c.execute("SELECT * FROM g_tables WHERE id=? AND state='stake_wait'", (t0["id"],)).fetchone()
        if not t:
            return
        bal = (c.execute("SELECT tokens FROM users WHERE id=?", (uid,)).fetchone() or {"tokens": 0})["tokens"]
        if _max_stake() and val > _max_stake():
            err = f"❌ حداکثر مبلغ ورودی {_t(_max_stake())} شاهی است."
        elif bal < val:
            err = f"❌ موجودی شما کافی نیست! موجودی فعلی: {_t(bal)} شاهی"
        if not err:
            c.execute("UPDATE g_tables SET stake=?, state='setup', touched=? WHERE id=?", (val, time.time(), t["id"]))
    if err:
        _say(t["chat_id"], err, t.get("thread_id"), m["message_id"])
        return
    t = _table(t["id"])
    txt, kb = _setup_view(t)
    _edit(t, txt, kb)
    B.tg("deleteMessage", _timeout=NET_TIMEOUT, chat_id=t["chat_id"], message_id=m["message_id"])


def _is_forward(m):
    return any(k in m for k in ("forward_origin", "forward_date", "forward_from", "forward_from_chat", "via_bot"))


def _on_dice(m, u):
    d = m["dice"]
    emo = d.get("emoji")
    if emo not in ("🎰", "🎲") or _is_forward(m):
        return
    uid = u["id"]
    reply = None
    pre = _row("SELECT t.id FROM g_tables t JOIN g_players p ON p.table_id=t.id "
               "WHERE p.user_id=? AND t.state='send' AND t.chat_id=?", (uid, m["chat"]["id"]))
    if not pre:
        return          # بیشتر 🎰/🎲‌های گروه به بازی ربطی ندارند؛ بدون قفل نوشتن رد می‌شوند
    with _Tx() as c:
        r = c.execute("SELECT t.* FROM g_tables t JOIN g_players p ON p.table_id=t.id "
                      "WHERE p.user_id=? AND t.state='send'", (uid,)).fetchone()
        if not r or r["chat_id"] != m["chat"]["id"] or GAMES[r["game"]]["emoji"] != emo:
            return
        p = c.execute("SELECT * FROM g_players WHERE table_id=? AND user_id=?", (r["id"], uid)).fetchone()
        mid = m.get("message_id") or 0
        if r.get("msg_id") and mid < r["msg_id"]:
            return      # قبل از ساخت پنل فرستاده شده؛ حساب نمی‌شود
        if p["sent"]:
            # فقط «اولین» 🎰 حساب می‌شود. اگر به‌خاطر هم‌زمانی، پیام اول دیرتر از دومی پردازش شد
            # (message_id کوچک‌تر = زودتر فرستاده شده) و هنوز نتیجه نمایش داده نشده، همان اولی جایگزین می‌شود.
            if (not p["shown"]) and p["mid"] and mid and mid < p["mid"]:
                c.execute("UPDATE g_players SET value=?, mid=? WHERE table_id=? AND user_id=? AND shown=0",
                          (int(d["value"]), mid, r["id"], uid))
            return
        if r["game"] == "d" and r["maxp"] == 1 and not p["pick"]:
            reply = "❌ ابتدا از دکمه‌های پنل انتخاب خود را بزنید، سپس تاس بیندازید."
        else:
            c.execute("UPDATE g_players SET sent=1, sent_at=?, value=?, mid=? WHERE table_id=? AND user_id=? AND sent=0",
                      (time.time(), int(d["value"]), mid, r["id"], uid))
    if reply:
        _say(m["chat"]["id"], reply, r.get("thread_id"), m["message_id"])


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
    if not xfer_on():
        return              # خاموش: بی‌صدا
    uid = u["id"]
    chat_id = m["chat"]["id"]
    th = _thread(m)
    mid = m["message_id"]
    nt = _fa2en(nt)
    toks = nt.split()
    if len(toks) >= 2 and toks[1] != "شاهی":
        return              # «انتقال دادم…» و مانند آن یعنی گفتگوی عادی
    rest = toks[2:]
    amount = _parse_num(rest[0]) if rest else None
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
                        (chat_id, th, uid, _name(u), e1, to_id, to_name, e2, amount, now + XFER_SEC))
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
        return (f"💎 رسید انتقال شاهی 👑\n\n🏦 مبلغ انتقال یافته : {_t(x['amount'])} شاهی\n{_xfer_people(x)}\n\n"
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
                c.execute("UPDATE users SET tokens = tokens + ? WHERE id=?", (x["amount"], uid))
                return ans("🛑 کاربر عضو ربات نیست, بهش بگو /start کنه!", True)
            _pay_in(c, x["recipient"], x["amount"])
            c.execute("INSERT INTO transfers (sender_id, recipient_id, amount) VALUES (?,?,?)",
                      (uid, x["recipient"], x["amount"]))
            # رسید انتقال‌یافته هرگز پاک نمی‌شود: ردیف با وضعیت done برای همیشه می‌ماند
            c.execute("UPDATE g_xfer SET state='done', deadline=? WHERE id=?", (time.time(), xid))
            result = "ok"
    ans()
    if result == "cancel":
        _xfer_edit(x, "انتقال شاهی لغو شد. ❌")
    else:
        _xfer_edit(x, _xfer_text(x, True))
        try:
            B.rep_ev_transfer(x["sender"], x["recipient"], x["amount"])
        except Exception:
            logging.exception("rep_ev_transfer")


def _tick_xfer(now):
    for x in _rows("SELECT * FROM g_xfer WHERE state='pending' AND deadline<=?", (now,)):
        cur = _x("DELETE FROM g_xfer WHERE id=? AND state='pending'", (x["id"],))
        if cur.rowcount == 1:
            _xfer_edit(x, "انتقال شاهی خودکار لغو شد. ❌")


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
            U("UPDATE g_tables SET game=?, state='setup', maxp=CASE WHEN maxp>? THEN NULL ELSE maxp END, touched=? WHERE id=?",
              (arg, mp, now, tid))
        elif act == "menu":
            U("UPDATE g_tables SET state='menu', touched=? WHERE id=?", (now, tid))
        elif act == "stk":
            U("UPDATE g_tables SET state='stake_wait', touched=? WHERE id=?", (now, tid))
        elif act == "np":
            U("UPDATE g_tables SET state='pick', touched=? WHERE id=?", (now, tid))
        elif act == "bk":
            U("UPDATE g_tables SET state='setup', touched=? WHERE id=?", (now, tid))
        elif act == "n":
            if arg not in [str(i) for i in range(1, GAMES[t["game"]]["maxp"] + 1)]:
                return ans()
            U("UPDATE g_tables SET maxp=?, state='setup', touched=? WHERE id=?", (int(arg), now, tid))
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
    if t["state"] == "menu":
        _edit(t, _menu_text(), _menu_kb(tid))
    else:
        txt, kb = _setup_view(t)
        _edit(t, txt, kb)


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
        c.execute("UPDATE g_tables SET state='send', send_dl=?, touched=? WHERE id=?", (now + SEND_SEC, now, t["id"]))
    else:
        c.execute("UPDATE g_tables SET state='join', join_dl=?, touched=? WHERE id=?", (now + JOIN_SEC, now, t["id"]))
    return None


def _after_make(tid):
    t = _table(tid)
    ps = _players(tid)
    if t["state"] == "play":
        txt, kb = _xo_view(t, ps)
        _edit(t, txt, kb)
    elif t["state"] == "send":
        txt, kb = _send_view(t, ps)
        _edit(t, txt, kb)
    else:
        txt, kb = _join_view(t, ps)
        _edit(t, txt, kb)


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
        left = _cool_left_c(c, uid) if t["game"] != "x" else 0
        if left > 0:
            return ans(_cool_msg(left), True)
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
                          (now + SEND_SEC, now, tid))
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
    t = _table(tid)
    txt, kb = _send_view(t, _players(tid))
    _edit(t, txt, kb)


# ---------------- دوز (نوبتی، اتمیک) ----------------
def _start_xo_in(c, t, joiner, now):
    """داخل تراکنش: نقش‌ها رندوم، سازنده اول شروع می‌کند"""
    roles = ["X", "O"]
    random.shuffle(roles)
    c.execute("UPDATE g_players SET pick=? WHERE table_id=? AND user_id=?", (roles[0], t["id"], t["owner"]))
    c.execute("UPDATE g_players SET pick=? WHERE table_id=? AND user_id=?", (roles[1], t["id"], joiner))
    c.execute("UPDATE g_tables SET state='play', board='---------', turn=?, send_dl=?, touched=? "
              "WHERE id=? AND state='join'", (t["owner"], now + XO_SEC, now, t["id"]))


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
        txt, kb = _xo_view(t, ps)
        _edit(t, txt, kb)


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
            c.execute("INSERT INTO g_cool (user_id, ts) VALUES (?, ?) "
                      "ON CONFLICT(user_id) DO UPDATE SET ts=excluded.ts", (p["user_id"], now))
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


def _cancel_join(tid):
    with _Tx() as c:
        cur = c.execute("UPDATE g_tables SET state='cancelled' WHERE id=? AND state='join'", (tid,))
        if cur.rowcount != 1:
            return
        t = c.execute("SELECT * FROM g_tables WHERE id=?", (tid,)).fetchone()
        for p in c.execute("SELECT * FROM g_players WHERE table_id=?", (tid,)).fetchall():
            _pay_in(c, p["user_id"], p["stake"])
    g = GAMES[t["game"]]
    _edit(t, f"{g['short']}\n\n❌ میز بسته شد چون بازیکنی نپیوست.\n"
             f"💎 {_t(t['stake'])} شاهی به موجودی شما برگشت.")
    _purge(tid)


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
        _edit(t, "⌛ این پنل منقضی شد. برای شروع دوباره بنویسید: «"
              + (TRIGGER_XO if t["game"] == "x" else TRIGGER) + "»")
        _purge(t["id"])


def _tick_join(t, now):
    with _Tx() as c:
        n = c.execute("SELECT COUNT(*) AS n FROM g_players WHERE table_id=?", (t["id"],)).fetchone()["n"]
        moved = False
        if n >= 2:
            cur = c.execute("UPDATE g_tables SET state='send', send_dl=?, touched=? WHERE id=? AND state='join'",
                            (now + SEND_SEC, now, t["id"]))
            moved = cur.rowcount == 1
    if n >= 2:
        if moved:
            _after_make(t["id"])
    else:
        _cancel_join(t["id"])


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
        txt, kb = _send_view(t, ps)
        _edit(t, txt, kb)


def _tick():
    now = time.time()
    ph = ",".join("?" * len(PRE))
    for t in _rows(f"SELECT * FROM g_tables WHERE state IN ({ph}) AND touched<?", (*PRE, now - STALE_SEC)):
        _guard(_tick_pre, t, ph, now)
    for t in _rows("SELECT * FROM g_tables WHERE state='play' AND send_dl<=?", (now,)):
        _guard(_xo_timeout, t["id"])
    for t in _rows("SELECT * FROM g_tables WHERE state='join' AND join_dl<=?", (now,)):
        _guard(_tick_join, t, now)
    for t in _rows("SELECT * FROM g_tables WHERE state='send'"):
        _guard(_tick_send, t, now)
    # نظافت: بازی‌های تمام‌شده‌ی جامانده (مثلاً بعد از کرش) و کول‌داون‌های گذشته
    for t in _rows("SELECT id FROM g_tables WHERE state IN ('done','cancelled','expired')"):
        _guard(_purge, t["id"])
    _x("DELETE FROM g_cool WHERE ts<?", (now - COOLDOWN_SEC - 5,))
    _guard(_tick_xfer, now)


def worker():
    while True:
        try:
            _tick()
        except Exception:
            logging.exception("games worker")
        time.sleep(1)


def start():
    threading.Thread(target=worker, daemon=True, name="games").start()
