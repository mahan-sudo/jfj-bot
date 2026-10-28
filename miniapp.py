"""
مینی‌اپ JFJ — لایه‌ی وب (WSGI، فقط کتابخانه‌ی استاندارد)
کنار bot_test.py بگذار. صفحه‌ی ظاهری در static/index.html است.
فایل WSGI در PythonAnywhere:
    import sys
    sys.path.insert(0, '/home/USERNAME/jfjtest')
    from miniapp import application
"""
import hashlib, hmac, json, mimetypes, os, sqlite3, sys, threading, time, traceback
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, parse_qsl
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import bot_test as bot  # noqa: E402

mimetypes.add_type("font/woff2", ".woff2")
HERE = os.path.dirname(os.path.abspath(__file__))

# مسیر دیتابیس مطلق شود (در WSGI مسیر کاری متفاوت است)
bot.DB_PATH = os.environ.get("JFJ_DB") or os.path.join(HERE, "bot.db")
try:  # اگر پوشه‌ی دیتابیس (مثل /data روی Volume) وجود ندارد بساز؛ نشد از کنار فایل‌ها استفاده کن
    os.makedirs(os.path.dirname(bot.DB_PATH) or ".", exist_ok=True)
    open(bot.DB_PATH, "a").close()
except OSError:
    print("WARNING: مسیر دیتابیس در دسترس نیست؛ از bot.db کنار فایل‌ها استفاده می‌شود", flush=True)
    bot.DB_PATH = os.path.join(HERE, "bot.db")
DEV_UID = os.environ.get("JFJ_DEV_UID")
DEV_PHOTO = os.environ.get("JFJ_DEV_PHOTO", "")
MINI_BUILD = "sec3-1028"   # شناسه‌ی نسخه؛ برای اطمینان از آپلود درست فایل‌ها
STATIC_DIR = os.path.join(HERE, "static")
if not os.path.exists(os.path.join(STATIC_DIR, "index.html")):
    STATIC_DIR = HERE  # اگر index.html کنار miniapp.py گذاشته شد (آپلود از موبایل)

_init_lock = __import__("threading").Lock()
_schema_done = False


def ensure_ready():
    """ساخت جدول‌ها (یک‌بار) + گرفتن یوزرنیم/آیدی ربات (تا موفق شود هر بار دوباره تلاش می‌کند)"""
    global _schema_done
    if not _schema_done:
        with _init_lock:
            if not _schema_done:
                bot.install_schema()
                bot.migrate_schema()
                bot.seed_products()
                with bot.get_db() as c:
                    c.execute("""CREATE TABLE IF NOT EXISTS mini_seen (
                        user_id INTEGER NOT NULL,
                        code TEXT NOT NULL,
                        verified INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY (user_id, code))""")
                    c.execute("CREATE TABLE IF NOT EXISTS mini_meta (k TEXT PRIMARY KEY, v TEXT)")
                    c.execute("""CREATE TABLE IF NOT EXISTS mini_notices (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        ukey TEXT NOT NULL,
                        kind TEXT NOT NULL DEFAULT 'info',
                        title TEXT NOT NULL,
                        body TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        UNIQUE (user_id, ukey))""")
                    c.execute("CREATE TABLE IF NOT EXISTS mini_notice_read (user_id INTEGER PRIMARY KEY, last_id INTEGER NOT NULL DEFAULT 0)")
                _schema_done = True
    if not bot.BOT_USERNAME or not bot.BOT_ID:
        with bot.get_db() as c:
            rows = dict(c.execute("SELECT k, v FROM mini_meta WHERE k IN ('bot_username','bot_id')").fetchall())
        if rows.get("bot_username") and rows.get("bot_id"):
            bot.BOT_USERNAME, bot.BOT_ID = rows["bot_username"], int(rows["bot_id"])
        else:
            try:
                me = bot.tg("getMe", _timeout=10)
            except Exception:
                me = {}
            if me.get("ok"):
                bot.BOT_USERNAME = me["result"].get("username")
                bot.BOT_ID = me["result"].get("id")
                with bot.get_db() as c:
                    c.execute("INSERT OR REPLACE INTO mini_meta (k, v) VALUES ('bot_username', ?)", (bot.BOT_USERNAME,))
                    c.execute("INSERT OR REPLACE INTO mini_meta (k, v) VALUES ('bot_id', ?)", (str(bot.BOT_ID),))


    try:  # آیدی ربات همیشه از خودِ توکن مشخص است؛ کش قدیمی دیتابیس نباید آن را خراب کند
        bot.BOT_ID = int(str(bot.BOT_TOKEN).split(":")[0])
    except (ValueError, AttributeError):
        pass


_ms_cache = {}  # (uid, ident) -> (زمان, وضعیت)


def member_status(uid, ident, tries=4, fresh=False):
    """وضعیت عضویت با تلاش مجدد. اگر تلگرام (یا تونل سرور) جواب نداد، آخرین وضعیت شناخته‌شده
    (حداکثر ۱۰ دقیقه قبل) استفاده می‌شود تا فهرست کانال‌ها بالا و پایین نشود.
    fresh=True: برای تأیید پاداش، فقط جواب زنده معتبر است."""
    key = (uid, ident)
    for i in range(tries):
        try:
            res = bot.tg("getChatMember", chat_id=ident, user_id=uid, _timeout=10)
            if res.get("ok"):
                st = res["result"].get("status")
                if len(_ms_cache) > 5000:
                    _ms_cache.clear()
                _ms_cache[key] = (time.time(), st)
                return st
            if res.get("error_code") in (400, 403):  # چت/کاربر نامعتبر؛ تلاش مجدد فایده ندارد
                return None
        except Exception:
            pass
        time.sleep(0.35 * (i + 1))
    hit = _ms_cache.get(key)
    if not fresh and hit and time.time() - hit[0] < 600:
        return hit[1]
    return None


# ---------------------------------------------------------------- احراز هویت
def verify_init_data(init_data, bot_token=None, max_age=604800):
    bot_token = bot_token or bot.BOT_TOKEN
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    got_hash = pairs.pop("hash", None)
    if not got_hash:
        return None
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    want = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(want, got_hash):
        return None
    try:
        if time.time() - int(pairs.get("auth_date", 0)) > max_age:
            return None
        return json.loads(pairs["user"])
    except (KeyError, ValueError):
        return None


class ApiError(Exception):
    def __init__(self, message, status=400, code=None):
        super().__init__(message)
        self.message, self.status, self.code = message, status, code


def auth_user(environ):
    auth = environ.get("HTTP_AUTHORIZATION", "")
    if auth.startswith("tma "):
        user = verify_init_data(auth[4:])
        if user:
            return user
    kb = environ.get("HTTP_X_KB", "")
    if kb and "." in kb:
        k_uid, k_sig = kb.split(".", 1)
        if k_uid.isdigit() and hmac.compare_digest(bot.kb_sig(k_uid), k_sig):
            fn, un = "", None
            try:
                with bot.get_db() as c:
                    r = c.execute("SELECT first_name, username FROM users WHERE id=?", (int(k_uid),)).fetchone()
                if r:
                    fn, un = r[0], r[1]
            except Exception:
                pass
            return {"id": int(k_uid), "first_name": fn, "username": un}
    if DEV_UID and not auth:
        return {"id": int(DEV_UID), "first_name": "Dev", "username": "dev_user", "photo_url": DEV_PHOTO}
    raise ApiError("unauthorized", 401)


# ---------------------------------------------------------------- کمکی‌ها
def tehran(dt):
    return dt.astimezone(ZoneInfo(bot.TIMEZONE))


def parse_ts(s):
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def when_text(dt):
    if not dt:
        return ""
    days = (tehran(datetime.now(timezone.utc)).date() - tehran(dt).date()).days
    if days <= 0:
        return "امروز"
    if days == 1:
        return "دیروز"
    return f"{days} روز پیش"


def clean_num(x):
    x = float(x)
    return int(x) if x == int(x) else round(x, 2)


def tme_url(link):
    ident = bot.extract_chat_identifier(link or "")
    if ident:
        return "https://t.me/" + ident[1:]
    link = (link or "").strip()
    return link if link.lower().startswith("http") else None


def display_name(link):
    return bot.extract_chat_identifier(link or "") or (link or "")


def products_info(uid=None):
    out = {}
    for key in ("views", "members", "reaction", "premium"):
        p = bot.get_product(key)
        out[key] = {
            "enabled": bool(p["enabled"] or (uid and bot.user_has_product(uid, key))), "min": p["min_qty"], "rate": p["rate_cost"], "per": p["rate_per"],
        }
    return out


# ---------------------------------------------------------------- برترین‌ها
LB_AGG = {
    "wealth": "SELECT id, tokens AS score FROM users WHERE tokens > 0",
    "joins": "SELECT user_id AS id, COUNT(*) AS score FROM joins WHERE left_at IS NULL GROUP BY user_id",
    "requests": "SELECT user_id AS id, COUNT(*) AS score FROM requests GROUP BY user_id",
    "invites": "SELECT referred_by AS id, COUNT(*) AS score FROM users WHERE referred_by IS NOT NULL GROUP BY referred_by",
}


def uphoto_sig(uid):
    key = hashlib.sha256(("uphoto:" + bot.BOT_TOKEN).encode()).digest()
    return hmac.new(key, str(uid).encode(), hashlib.sha256).hexdigest()[:16]


def lb_items(cat, off, limit):
    agg = LB_AGG[cat]
    with bot.get_db() as c:
        rows = c.execute(
            f"SELECT a.id, u.first_name, u.username, a.score FROM ({agg}) a JOIN users u ON u.id=a.id "
            "ORDER BY a.score DESC, a.id LIMIT ? OFFSET ?", (limit, off)).fetchall()
    return [{"rank": off + i + 1, "id": r[0], "name": (r[1] or "کاربر")[:40], "username": r[2] or "",
             "score": clean_num(r[3]), "photo": f"/api/uphoto/{r[0]}?s={uphoto_sig(r[0])}"}
            for i, r in enumerate(rows)]


def api_leaderboard(uid, query):
    cat = (query.get("cat") or ["wealth"])[0]
    if cat not in LB_AGG:
        raise ApiError("دسته نامعتبر است.")
    try:
        off = max(0, int((query.get("off") or ["0"])[0]))
    except ValueError:
        off = 0
    limit = 50
    items = lb_items(cat, off, limit + 1)
    more = len(items) > limit
    items = items[:limit]
    agg = LB_AGG[cat]
    with bot.get_db() as c:
        row = c.execute(f"SELECT score FROM ({agg}) WHERE id=?", (uid,)).fetchone()
        mine = row[0] if row else 0
        rank = None
        if mine and mine > 0:
            rank = c.execute(f"SELECT COUNT(*) FROM ({agg}) WHERE score > ? OR (score = ? AND id < ?)",
                             (mine, mine, uid)).fetchone()[0] + 1
        total = c.execute(f"SELECT COUNT(*) FROM ({agg})").fetchone()[0]
    return {"cat": cat, "items": items, "more": more, "total": total,
            "me": {"rank": rank, "score": clean_num(mine or 0)}}


_uphoto_cache = {}


def fetch_uphoto(uid):
    now = time.time()
    hit = _uphoto_cache.get(uid)
    if hit and hit[0] > now:
        return hit[1]
    result = None
    try:
        r = bot.tg("getUserProfilePhotos", user_id=uid, limit=1, _timeout=12)
        photos = r["result"]["photos"] if r.get("ok") else []
        if photos:
            f = bot.tg("getFile", file_id=photos[0][0]["file_id"], _timeout=12)
            if f.get("ok"):
                path = f["result"]["file_path"]
                with urllib.request.urlopen(f"https://api.telegram.org/file/bot{bot.BOT_TOKEN}/{path}", timeout=12) as resp:
                    result = (mimetypes.guess_type(path)[0] or "image/jpeg", resp.read(2_000_000))
    except Exception:
        result = None
    if len(_uphoto_cache) > 600:
        _uphoto_cache.clear()
    _uphoto_cache[uid] = (now + (6 * 3600 if result else 900), result)
    return result


def sponsor_subs(uid):
    out = []
    with bot.get_db() as c:
        rows = c.execute(
            "SELECT s.id, s.hours, s.status, s.ends_at, s.created_at, COALESCE(i.final_amount, 0) FROM sponsor_subs s "
            "LEFT JOIN invoices i ON i.code = s.invoice_code WHERE s.user_id=? ORDER BY s.id DESC LIMIT 20", (uid,)).fetchall()
    for sid, hours, status, ends, created, amount in rows:
        st = bot.sub_state(status, ends)
        out.append({"code": sid, "hours": clean_num(hours), "amount": amount,
                    "state": {"active": "active", "pending": "pending", "expired": "expired", "cancelled": "expired"}[st],
                    "when": when_text(parse_ts(created))})
    return out


# ---------------------------------------------------------------- اعلان‌ها (زنگ)
def add_notice(user_id, title, body="", kind="info", ukey=None, created_at=None):
    """user_id=None => اطلاعیه برای همه. از کنسول: python3 -c "import miniapp; miniapp.add_notice(None,'عنوان','متن')"""
    uid = 0 if user_id is None else int(user_id)
    ts = created_at or datetime.now(timezone.utc).isoformat()
    with bot.get_db() as c:
        c.execute("INSERT OR IGNORE INTO mini_notices (user_id, ukey, kind, title, body, created_at) VALUES (?,?,?,?,?,?)",
                  (uid, ukey or ("n%d" % time.time_ns()), kind, title, body, ts))


_FA = str.maketrans('0123456789.', '۰۱۲۳۴۵۶۷۸۹٫')


def fa_n(x):
    return str(x).translate(_FA)


def sync_notices(uid):
    """اعلان‌های شخصی را از رویدادهای واقعی می‌سازد (فقط یک‌بار برای هر رویداد)"""
    with bot.get_db() as c:
        first = c.execute("SELECT 1 FROM mini_notice_read WHERE user_id=?", (uid,)).fetchone() is None
        mine_left = c.execute(
            """SELECT j.tracking_code, r.link, j.left_at FROM joins j JOIN requests r ON r.tracking_code=j.tracking_code
               WHERE j.user_id=? AND j.left_at IS NOT NULL ORDER BY j.left_at DESC LIMIT 10""", (uid,)).fetchall()
        owner_left = c.execute(
            """SELECT j.tracking_code, j.user_id, r.link, j.left_at FROM joins j JOIN requests r ON r.tracking_code=j.tracking_code
               WHERE r.user_id=? AND j.left_at IS NOT NULL ORDER BY j.left_at DESC LIMIT 10""", (uid,)).fetchall()
        done = c.execute(
            "SELECT tracking_code, link, created_at FROM requests WHERE user_id=? AND status='completed' ORDER BY created_at DESC LIMIT 10",
            (uid,)).fetchall()
        refs = c.execute(
            "SELECT id, updated_at FROM users WHERE referred_by=? AND referral_rewarded=1 ORDER BY updated_at DESC LIMIT 10",
            (uid,)).fetchall()
        svc_done = c.execute(
            "SELECT tracking_code, service, status, created_at FROM service_orders WHERE user_id=? AND status IN ('completed','cancelled') "
            "ORDER BY created_at DESC LIMIT 10", (uid,)).fetchall()
    for code, name, st, at in svc_done:
        if st == "completed":
            add_notice(uid, "سفارش تکمیل شد", f"سفارش {name} با کد پیگیری {fa_n(code)} انجام شد.", "done", f"svc:{code}", at)
        else:
            add_notice(uid, "سفارش لغو شد", f"سفارش {name} با کد پیگیری {fa_n(code)} لغو و موجودی برگشت.", "info", f"svc:{code}", at)
    for code, link, at in mine_left:
        add_notice(uid, "ترک کانال", f"کانال {display_name(link)} را ترک کردی و {fa_n(clean_num(bot.JOIN_REWARD))} شاهی از تو کم شد.",
                   "leave", f"leave:{code}", at)
    for code, who, link, at in owner_left:
        add_notice(uid, "یک عضو لفت داد", f"یکی از اعضای {display_name(link)} لفت داد و {fa_n(clean_num(bot.LEAVE_REFUND_TO_OWNER))} شاهی به تو برگشت.",
                   "left", f"left:{code}:{who}", at)
    for code, link, at in done:
        add_notice(uid, "سفارش تکمیل شد", f"سفارش {display_name(link)} با کد پیگیری {fa_n(code)} کامل شد.", "done", f"done:{code}", at)
    for fid, at in refs:
        add_notice(uid, "پاداش دعوت", f"یکی از دوستان دعوت‌شده‌ات به حد نصاب رسید و {fa_n(clean_num(bot.REFERRAL_REWARD))} شاهی گرفتی.", "ref", f"ref:{fid}", at)
    if first:
        with bot.get_db() as c:
            last = c.execute("SELECT COALESCE(MAX(id),0) FROM mini_notices WHERE user_id IN (?,0)", (uid,)).fetchone()[0]
            c.execute("INSERT OR IGNORE INTO mini_notice_read (user_id, last_id) VALUES (?,?)", (uid, last))
        add_notice(uid, "خوش آمدی", "به جفج شاهنشاهی خوش آمدی! اعلان‌ها و پیام‌های تو اینجا نمایش داده می‌شود.", "welcome", "welcome")


def get_notices(uid):
    with bot.get_db() as c:
        last = (c.execute("SELECT last_id FROM mini_notice_read WHERE user_id=?", (uid,)).fetchone() or (0,))[0]
        rows = c.execute(
            "SELECT id, kind, title, body, created_at FROM mini_notices WHERE user_id IN (?,0) ORDER BY created_at DESC, id DESC LIMIT 30",
            (uid,)).fetchall()
    items = [{"id": r[0], "kind": r[1], "title": r[2], "body": r[3], "when": when_text(parse_ts(r[4])), "unread": r[0] > last}
             for r in rows]
    return items, sum(1 for i in items if i["unread"])


def api_notices_read(uid, body):
    with bot.get_db() as c:
        mx = c.execute("SELECT COALESCE(MAX(id),0) FROM mini_notices WHERE user_id IN (?,0)", (uid,)).fetchone()[0]
        c.execute("INSERT OR REPLACE INTO mini_notice_read (user_id, last_id) VALUES (?,?)", (uid, mx))
    return {"ok": True}


# ---------------------------------------------------------------- ثبت لفت (بررسی زنده‌ی عضویت)
_leave_check = {}  # uid -> زمان آخرین بررسی


def process_leave(uid, code, owner_id, link):
    """همان منطق handle_member_left ربات، برای یک سفارش مشخص؛ فقط یک‌بار اجرا می‌شود (left_at گیت است)"""
    with bot.get_db() as c:
        cur = c.execute(
            "UPDATE joins SET left_at=? WHERE user_id=? AND tracking_code=? AND left_at IS NULL",
            (bot.now_local().isoformat(), uid, code),
        )
        if cur.rowcount != 1:
            return False
    bot.add_tokens(owner_id, bot.LEAVE_REFUND_TO_OWNER)
    bot.send(owner_id, f"🔔 *یه ممبر لفت داده!*\n💎 *تعداد {bot.fmt_tokens(bot.LEAVE_REFUND_TO_OWNER)} شاهی به موجودی شما اضافه شد.*")
    with bot.get_db() as c:
        c.execute("UPDATE users SET tokens = tokens - ? WHERE id=?", (bot.JOIN_REWARD, uid))
    bot.send(uid, f"⛔️ *به دلیل لفت دادن شما*\n*از لینک ({link}) تعداد 💎{bot.JOIN_REWARD} شاهی از شما کم شد!*")
    bot.rep_ev_leave(uid, owner_id, code, link, bot.JOIN_REWARD, bot.LEAVE_REFUND_TO_OWNER)
    return True


def reconcile_leaves(uid, min_gap=12):
    """جوین‌های فعال کاربر را زنده چک می‌کند؛ اگر کانالی را ترک کرده باشد جریمه/بازگشت ثبت می‌شود.
    این‌طوری لفت حتی وقتی آپدیت chat_member به ربات نرسیده هم ثبت می‌شود."""
    now = time.time()
    if now - _leave_check.get(uid, 0) < min_gap:
        return []
    _leave_check[uid] = now
    with bot.get_db() as c:
        rows = c.execute(
            """SELECT j.tracking_code, r.link, r.chat_id, r.user_id
               FROM joins j JOIN requests r ON r.tracking_code=j.tracking_code
               WHERE j.user_id=? AND j.left_at IS NULL ORDER BY j.rowid DESC LIMIT 25""", (uid,)
        ).fetchall()
    if not rows:
        return []

    def check(row):
        ident = bot.resolve_chat_ident(row[2], row[1])
        if not ident:
            return None
        if member_status(uid, ident) in ("left", "kicked"):
            return row
        return None

    with ThreadPoolExecutor(4) as ex:
        gone = [r for r in ex.map(check, rows) if r]
    names = []
    for code, link, _cid, owner in gone:
        if process_leave(uid, code, owner, link):
            names.append(display_name(link))
    return names


_leave_res = {}
_leave_run = set()


def reconcile_bg(uid):
    """چک لفت را در پس‌زمینه انجام می‌دهد تا باز شدن مینی‌اپ منتظر تلگرام نماند؛
    نتیجه‌ی چک قبلی (در صورت وجود) همین‌جا برمی‌گردد."""
    res = _leave_res.pop(uid, [])
    if uid in _leave_run or time.time() - _leave_check.get(uid, 0) < 12:
        return res
    _leave_run.add(uid)

    def work():
        try:
            names = reconcile_leaves(uid)
            if names:
                _leave_res[uid] = names
        except Exception:
            traceback.print_exc()
        finally:
            _leave_run.discard(uid)
    threading.Thread(target=work, daemon=True).start()
    return res


# ---------------------------------------------------------------- state
def build_state(user):
    uid = user["id"]
    bot.upsert_user(user)
    left_now = []
    try:
        left_now = reconcile_bg(uid)
    except Exception:
        traceback.print_exc()
    with bot.get_db() as c:
        urow = c.execute("SELECT first_name, username, tokens FROM users WHERE id=?", (uid,)).fetchone()
        reqs = c.execute(
            """SELECT r.tracking_code, r.member_count, r.link, r.status, r.created_at,
                      (SELECT COUNT(*) FROM joins j WHERE j.tracking_code=r.tracking_code AND j.left_at IS NULL)
               FROM requests r WHERE r.user_id=? ORDER BY r.created_at DESC, r.rowid DESC LIMIT 100""",
            (uid,),
        ).fetchall()
        joins_n = c.execute("SELECT COUNT(*) FROM joins WHERE user_id=? AND left_at IS NULL", (uid,)).fetchone()[0]
        friends = c.execute(
            "SELECT id, activity_tokens, referral_rewarded, first_name FROM users WHERE referred_by=? ORDER BY created_at",
            (uid,),
        ).fetchall()

        tx = []
        for code, cnt, link, status, created_at, _ in reqs[:30]:
            tx.append((parse_ts(created_at), None, f"سفارش {display_name(link)}",
                       -float(c.execute("SELECT token_cost FROM requests WHERE tracking_code=?", (code,)).fetchone()[0])))
        for link, joined_at, left_at in c.execute(
            """SELECT r.link, j.joined_at, j.left_at FROM joins j JOIN requests r ON r.tracking_code=j.tracking_code
               WHERE j.user_id=? ORDER BY j.joined_at DESC LIMIT 30""", (uid,)
        ).fetchall():
            tx.append((parse_ts(joined_at), None, f"پاداش جوین {display_name(link)}", float(bot.JOIN_REWARD)))
            if left_at:
                tx.append((parse_ts(left_at), None, f"ترک کانال {display_name(link)}", -float(bot.JOIN_REWARD)))
        for link, left_at in c.execute(
            """SELECT r.link, j.left_at FROM joins j JOIN requests r ON r.tracking_code=j.tracking_code
               WHERE r.user_id=? AND j.left_at IS NOT NULL ORDER BY j.left_at DESC LIMIT 30""", (uid,)
        ).fetchall():
            tx.append((parse_ts(left_at), None, "بازگشت شاهی بابت ترک عضو", float(bot.LEAVE_REFUND_TO_OWNER)))
        for (upd,) in c.execute(
            "SELECT updated_at FROM users WHERE referred_by=? AND referral_rewarded=1", (uid,)
        ).fetchall():
            tx.append((parse_ts(upd), None, "پاداش دعوت دوست", float(bot.REFERRAL_REWARD)))
        for sid, rid, amount, created_at in c.execute(
            "SELECT sender_id, recipient_id, amount, created_at FROM transfers WHERE sender_id=? OR recipient_id=? "
            "ORDER BY id DESC LIMIT 20", (uid, uid)
        ).fetchall():
            tx.append((parse_ts(created_at), None, "انتقال توکن", -float(amount) if sid == uid else float(amount)))

    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    tx = [t for t in tx if t[0]]
    tx.sort(key=lambda t: t[0] or epoch, reverse=True)
    transactions = [{"title": t[2], "when": when_text(t[0]), "amount": clean_num(t[3])} for t in tx[:8]]

    with bot.get_db() as c:
        svc_rows = c.execute(
            "SELECT tracking_code, service, quantity, link, status, created_at FROM service_orders "
            "WHERE user_id=? ORDER BY created_at DESC, rowid DESC LIMIT 60", (uid,)).fetchall()
        inv_rows = c.execute(
            "SELECT code, product_name, status, created_at FROM invoices "
            "WHERE buyer_id=? AND status IN ('awaiting_receipt','review','paid','rejected') "
            "ORDER BY created_at DESC LIMIT 30", (uid,)).fetchall()
    epoch0 = datetime(1970, 1, 1, tzinfo=timezone.utc)
    allo = []
    for code, cnt, link, status, created, done in reqs:
        allo.append((parse_ts(created) or epoch0, {
            "kind": "jfj", "code": code, "channel": display_name(link), "total": cnt,
            "cur": min(done, cnt), "done": status == "completed", "removed": status in ("removed", "deleted", "relinked"),
            "rlabel": "حذف شد توسط مدیریت" if status == "deleted" else "لینک تغییر کرد" if status == "relinked" else "ربات عزل شد"}))
    for code, name, qty, link, status, created in svc_rows:
        allo.append((parse_ts(created) or epoch0, {
            "kind": "svc", "code": code, "title": name, "qty": qty, "channel": display_name(link),
            "done": status == "completed", "bad": status == "cancelled",
            "label": {"completed": "تکمیل شد", "cancelled": "لغو شد"}.get(status, "در حال انجام")}))
    for code, name, status, created in inv_rows:
        allo.append((parse_ts(created) or epoch0, {
            "kind": "inv", "code": code, "title": name, "done": status == "paid", "bad": status == "rejected",
            "label": {"paid": "تأیید شد", "rejected": "رد شد", "review": "در حال بررسی"}.get(status, "منتظر رسید")}))
    allo.sort(key=lambda t: t[0], reverse=True)
    orders = [o for _, o in allo[:120]]
    thr = bot.REFERRAL_ACTIVITY_THRESHOLD
    friend_list = [
        {"id": fid, "name": (fname or "").strip(), "cur": min(int(act), thr) if not rewarded else thr, "rewarded": bool(rewarded)}
        for fid, act, rewarded, fname in friends
    ]
    if not bot.BOT_USERNAME:
        ensure_ready()
    username = bot.BOT_USERNAME or ""
    try:
        sync_notices(uid)
        notices, unread = get_notices(uid)
    except Exception:
        traceback.print_exc()
        notices, unread = [], 0
    try:
        top3 = lb_items("wealth", 0, 3)
    except Exception:
        traceback.print_exc()
        top3 = []
    try:
        subs = sponsor_subs(uid)
    except Exception:
        traceback.print_exc()
        subs = []
    return {
        "top3": top3, "sponsorSubs": subs,
        "notices": notices, "unread": unread,
        "user": {"id": uid, "name": urow[0] or "کاربر", "username": urow[1] or "",
                 "photo": user.get("photo_url") or ""},
        "balance": clean_num(urow[2]),
        "stats": {"orders": len(orders), "joins": joins_n, "invited": len(friend_list)},
        "orders": orders,
        "friends": friend_list,
        "transactions": transactions,
        "leftNow": left_now,
        "refLink": f"https://t.me/{username}?start=ref{uid}" if username else "",
        "cfg": {
            "tokensPerMember": bot.TOKENS_PER_MEMBER,
            "minMembers": bot.MIN_MEMBER_COUNT,
            "joinReward": bot.JOIN_REWARD,
            "leavePenalty": bot.JOIN_REWARD,
            "minTransfer": bot.MIN_TRANSFER_AMOUNT,
            "cooldownMin": max(1, int(bot.RESUBMIT_COOLDOWN_SECONDS // 60)),
            "bonus": {k: v for k, v in bot.bonus_state().items() if k in ("active", "per", "amount", "ends")},
            "phoneVerify": bot.sbool("phone_verify"),
            "payMethods": [m for m in ("card", "zarin", "crypto") if bot.method_enabled(m)],
            "refReward": bot.REFERRAL_REWARD,
            "refThreshold": thr,
            "botUsername": username,
            "support": getattr(bot, "SUPPORT_ID", "") or "",
            "rules": (bot.get_setting("rules_text") or bot.RULES_TEXT).replace("*", ""),
        },
        "tokenPacks": bot.jt_packs_view(),
        "services": products_info(uid),
        "secOff": sec_off_list(uid, True),
        "isAdmin": bool(bot.is_admin(uid)),
        "build": MINI_BUILD,
        "sponsorPacks": bot.SPONSOR_PRODUCTS,
        "reactions": {"emojis": bot.REACTION_EMOJIS, "combos": ["ری‌اکشن ترکیبی مثبت🥳", "ری‌اکشن ترکیبی منفی🤮"]},
    }


# ---------------------------------------------------------------- بخش‌های غیرفعال ربات
def sec_off_list(uid, show_admin=False):
    """کلید بخش‌های خاموش. ادمین‌ها در API همیشه دسترسی دارند؛ ولی برای نمایش (show_admin) لیست واقعی را می‌بینند
    تا بتوانند ظاهر بخش خاموش را ببینند و با دکمه‌ی «ورود با دسترسی ادمین» رد شوند."""
    try:
        if bot.is_admin(uid) and not show_admin:
            return []
        return sorted(bot.sections_off())
    except Exception:
        traceback.print_exc()
        return []


def need_sec(uid, key, *more):
    off = sec_off_list(uid)
    if off and ("mi" in off or key in off or any(k in off for k in more)):
        raise ApiError("این بخش در حال حاضر غیرفعال است.")


# ---------------------------------------------------------------- JFJ: جوین
_title_cache = {}  # code -> (انقضا, عنوان)


def chat_title(code, ident):
    now = time.time()
    hit = _title_cache.get(code)
    if hit and hit[0] > now:
        return hit[1]
    title = ""
    try:
        r = bot.tg("getChat", chat_id=ident, _timeout=10)
        if r.get("ok"):
            title = (r["result"].get("title") or "").strip()
    except Exception:
        pass
    if len(_title_cache) > 500:
        _title_cache.clear()
    _title_cache[code] = (now + (6 * 3600 if title else 120), title)
    return title


def photo_sig(code):
    key = hashlib.sha256(("photo:" + bot.BOT_TOKEN).encode()).digest()
    return hmac.new(key, str(code).encode(), hashlib.sha256).hexdigest()[:16]


def _chan_blocked(link, chat_id_num):
    """کانال/گروه توسط مدیریت مسدود شده؟ (با یوزرنیم لینک، آیدی عددی و شناسه‌ی نهایی‌شده)"""
    try:
        if bot.is_chan_blocked(bot.extract_chat_identifier(link or ""), chat_id_num):
            return True
        ident = bot.resolve_chat_ident(chat_id_num, link)
        return bool(ident) and bot.is_chan_blocked(ident, chat_id_num)
    except Exception:
        traceback.print_exc()
        return False


def api_join_list(uid, body):
    need_sec(uid, "sj")
    """همه‌ی درخواست‌های درحال‌انجام که کاربر هنوز عضوشان نیست (چک زنده‌ی عضویت، مثل خود ربات)"""
    try:
        left_now = reconcile_leaves(uid, min_gap=5)
    except Exception:
        traceback.print_exc()
        left_now = []
    with bot.get_db() as c:
        rows = c.execute(
            """SELECT r.tracking_code, r.link, r.member_count, r.chat_id,
                      (SELECT COUNT(*) FROM joins j WHERE j.tracking_code=r.tracking_code AND j.left_at IS NULL)
               FROM requests r
               WHERE r.status='in_progress' AND r.user_id != ?
                 AND r.tracking_code NOT IN (SELECT tracking_code FROM joins WHERE user_id=? AND left_at IS NULL)
               ORDER BY r.created_at, r.rowid LIMIT 60""",
            (uid, uid),
        ).fetchall()

    def check(row):
        ident = bot.resolve_chat_ident(row[3], row[1])
        if not ident:
            return None
        st0 = member_status(uid, ident)
        if st0 is None and bot.bot_admin_state(ident) is False:
            bot.cancel_request_not_admin(row[0], "miniapp list")
            return None
        if st0 not in ("left", "kicked"):
            return None  # همین الان عضو است یا بررسی ممکن نیست
        return row + (chat_title(row[0], ident),)

    # هر کانال/گروه فقط یک بار (حتی با چند سفارش) و کانال‌هایی که قبلاً پاداششان گرفته شده نمایش داده نمی‌شوند
    done_keys = bot.user_channel_keys(uid)
    uniq, seen = [], set()
    for r in rows:
        k = bot.chan_key(r[3], r[1])
        if k in done_keys or k in seen:
            continue
        if _chan_blocked(r[1], r[3]):
            continue  # کانال/گروه توسط مدیریت مسدود شده
        seen.add(k)
        uniq.append(r)
    with ThreadPoolExecutor(4) as ex:
        ok = [r for r in ex.map(check, uniq) if r][:40]

    with bot.get_db() as c:
        keep = [r[0] for r in ok]
        if keep:
            c.execute("DELETE FROM mini_seen WHERE user_id=? AND code NOT IN (%s)" % ",".join("?" * len(keep)), [uid] + keep)
        else:
            c.execute("DELETE FROM mini_seen WHERE user_id=?", (uid,))
        c.executemany("INSERT OR REPLACE INTO mini_seen (user_id, code, verified) VALUES (?, ?, 1)",
                      [(uid, r[0]) for r in ok])
    return {"leftNow": left_now, "items": [
        {"code": r[0], "channel": display_name(r[1]), "title": r[5], "url": tme_url(r[1]),
         "photo": f"/api/photo/{r[0]}?s={photo_sig(r[0])}", "left": max(int(r[2]) - int(r[4]), 0)}
        for r in ok
    ]}


def api_join_confirm(uid, body):
    need_sec(uid, "sj")
    code = str(body.get("code") or "")
    with bot.get_db() as c:
        view = c.execute("SELECT verified FROM mini_seen WHERE user_id=? AND code=?", (uid, code)).fetchone()
        row = c.execute(
            "SELECT link, member_count, user_id, chat_id, status FROM requests WHERE tracking_code=?", (code,)
        ).fetchone()
    if not view or not row or row[4] != "in_progress":
        return {"ok": False, "gone": True, "error": "این درخواست دیگر معتبر نیست."}
    link, member_count, owner_id, chat_id_num, _status = row
    if _chan_blocked(link, chat_id_num):
        with bot.get_db() as c:
            c.execute("DELETE FROM mini_seen WHERE user_id=? AND code=?", (uid, code))
        return {"ok": False, "gone": True, "error": "این درخواست دیگر معتبر نیست."}

    if bot.chan_key(chat_id_num, link) in bot.user_channel_keys(uid, exclude_code=code):
        with bot.get_db() as c:
            c.execute("DELETE FROM mini_seen WHERE user_id=? AND code=?", (uid, code))
        return {"ok": False, "gone": True, "error": "برای این کانال قبلاً پاداش گرفتی."}
    ident = bot.resolve_chat_ident(chat_id_num, link)
    joined = False
    if ident:
        st = member_status(uid, ident, fresh=True)
        joined = st is not None and st not in ("left", "kicked")
    if ident and st is None:
        if bot.bot_admin_state(ident) is False:
            bot.cancel_request_not_admin(code, "miniapp confirm")
            with bot.get_db() as c:
                c.execute("DELETE FROM mini_seen WHERE user_id=? AND code=?", (uid, code))
            return {"ok": False, "gone": True, "error": "این درخواست دیگر معتبر نیست."}
        return {"ok": False, "error": "بررسی عضویت الان ممکن نشد؛ چند لحظه بعد دوباره امتحان کن."}
    if not joined:
        return {"ok": False, "error": "هنوز در کانال مورد نظر عضو نشدی!"}

    with bot.get_db() as c:
        c.execute("DELETE FROM mini_seen WHERE user_id=? AND code=?", (uid, code))
    if not bot.record_join(uid, code):
        return {"ok": False, "gone": True, "error": "برای این سفارش قبلاً پاداش گرفتی."}

    bot.add_tokens(uid, bot.JOIN_REWARD)
    bot.add_activity_tokens(uid, bot.JOIN_REWARD)
    bot.maybe_reward_referrer(uid)
    bot.refresh_request_status(code, member_count, "in_progress", owner_id=owner_id)
    return {"ok": True, "reward": bot.JOIN_REWARD, "balance": clean_num(bot.get_balance(uid))}


# ---------------------------------------------------------------- عکس کانال
_photo_cache = {}  # code -> (expires_ts, (ctype, bytes) | None)


def fetch_photo(code):
    now = time.time()
    hit = _photo_cache.get(code)
    if hit and hit[0] > now:
        return hit[1]
    with bot.get_db() as c:
        row = c.execute("SELECT link, chat_id FROM requests WHERE tracking_code=?", (code,)).fetchone()
    result = None
    if row:
        ident = bot.resolve_chat_ident(row[1], row[0])
        if ident:
            r = bot.tg("getChat", chat_id=ident, _timeout=12)
            ph = r["result"].get("photo") if r.get("ok") else None
            if ph:
                f = bot.tg("getFile", file_id=ph["small_file_id"], _timeout=12)
                if f.get("ok"):
                    path = f["result"]["file_path"]
                    try:
                        with urllib.request.urlopen(
                            f"https://api.telegram.org/file/bot{bot.BOT_TOKEN}/{path}", timeout=12
                        ) as resp:
                            data = resp.read(2_000_000)
                        result = (mimetypes.guess_type(path)[0] or "image/jpeg", data)
                    except Exception:
                        result = None
    if len(_photo_cache) > 300:
        _photo_cache.clear()
    _photo_cache[code] = (now + (6 * 3600 if result else 600), result)
    return result


# ---------------------------------------------------------------- JFJ: ثبت درخواست
def api_request(uid, body):
    need_sec(uid, "rj")
    link = str(body.get("link") or "").strip()
    try:
        count = int(body.get("count"))
    except (TypeError, ValueError):
        raise ApiError("تعداد نامعتبر است.")
    if count < bot.MIN_MEMBER_COUNT:
        raise ApiError(f"حداقل تعداد {bot.MIN_MEMBER_COUNT} است.")
    if count > 100000:
        raise ApiError("تعداد خیلی زیاد است.")
    link = bot.parse_jfj_link(link) or ""
    if not link:
        raise ApiError("آیدی کانال را حتماً با @ وارد کن؛ مثل @mychannel")
    ident = bot.extract_chat_identifier(link)
    if bot.is_chan_blocked(ident):
        raise ApiError("🛑 امکان درخواست برای این گروه-کانال وجود ندارد.")
    is_admin = False
    res = {}
    if ident and bot.BOT_ID:
        for attempt in range(3):
            res = bot.tg("getChatMember", chat_id=ident, user_id=bot.BOT_ID, _timeout=10)
            if res.get("ok"):
                is_admin = res["result"].get("status") in ("administrator", "creator")
                break
            d = str(res.get("description") or "").lower()
            if "chat not found" in d or "not a member" in d or "kicked" in d:
                break
            time.sleep(0.6)
    if not is_admin:
        d = str(res.get("description") or res.get("error_description") or res.get("error") or "")
        if res and not res.get("ok") and "chat not found" in d.lower():
            raise ApiError("کانال/گروه پیدا نشد؛ آیدی را درست وارد کن (کانال خصوصی را نمی‌شود با آیدی ثبت کرد).")
        if res and not res.get("ok") and not d.lower().startswith(("bad request", "forbidden")):
            raise ApiError("ارتباط با تلگرام برقرار نشد؛ چند ثانیه بعد دوباره امتحان کن.")
        raise ApiError(f"ربات (@{bot.BOT_USERNAME}) در کانال ادمین نیست!")
    chat_id_num = None
    res_chat = bot.tg("getChat", chat_id=ident)
    if res_chat.get("ok"):
        chat_id_num = res_chat["result"].get("id")
    if bot.is_chan_blocked(ident, chat_id_num):
        raise ApiError("🛑 امکان درخواست برای این گروه-کانال وجود ندارد.")

    left = bot.user_cooldown_left(uid)
    if left:
        raise ApiError(f"بین دو درخواست JFJ باید حداقل {fa_n(bot.RESUBMIT_COOLDOWN_SECONDS // 60)} دقیقه فاصله باشد؛ {bot.cooldown_text(left)} دیگر صبر کن.")
    existing = bot.get_active_request_for_chat(uid, chat_id_num)
    if existing and existing[2] not in ("completed", "cancelled", "removed", "deleted", "relinked"):
        elapsed = (bot.now_local() - datetime.fromisoformat(existing[3])).total_seconds()
        if elapsed < bot.RESUBMIT_COOLDOWN_SECONDS:
            raise ApiError("باید حداقل ۵ دقیقه از درخواست قبلی این کانال بگذرد یا سفارش قبلی تکمیل شود.")

    cost = count * bot.TOKENS_PER_MEMBER
    if not bot.deduct_tokens(uid, cost):
        raise ApiError("موجودی کافی نیست.", code="no_balance")
    code = bot.create_request(uid, count, cost, link, chat_id_num)
    date_str, time_str = bot.jalali_now_strings()
    bot.send(
        uid,
        "🚀 *درخواست JFJ شما #ثبت شد.*\n\n"
        f"🔍 *کد پیگیری: {code}*\n"
        f"⏰️ *زمان ثبت: {time_str} - {date_str}*",
    )
    return {"ok": True, "code": code, "balance": clean_num(bot.get_balance(uid))}


# ---------------------------------------------------------------- خرید شاهی
def api_invoice(uid, body):
    kind = "sponsor" if body.get("kind") == "sponsor" else "jtoken"
    need_sec(uid, "sp" if kind == "sponsor" else "bt")
    packs = bot.SPONSOR_PRODUCTS if kind == "sponsor" else bot.JTOKEN_PRODUCTS
    if not any(p["id"] == body.get("pack") for p in packs):
        raise ApiError("بسته نامعتبر است.")
    if kind == "sponsor":
        bot.sponsor_begin(uid, uid, body["pack"])
    else:
        bot.pay_start(uid, uid, "jtoken", body["pack"])
    return {"ok": True}


# ---------------------------------------------------------------- خرید خدمات با شاهی
def api_service(uid, body):
    need_sec(uid, "sv", {"seen": "sn", "views": "sn", "member": "mb", "members": "mb",
                         "reaction": "rc", "premium": "pm"}.get(body.get("service"), "sv"))
    key = {"seen": "views", "member": "members"}.get(body.get("service"), body.get("service"))
    if key not in ("views", "members", "reaction", "premium"):
        raise ApiError("سرویس نامعتبر است.")
    p = bot.get_product(key)
    if not bot.product_open(uid, key):
        raise ApiError("این محصول در حال حاضر ناموجود است.")
    try:
        qty = int(body.get("qty"))
    except (TypeError, ValueError):
        raise ApiError("تعداد نامعتبر است.")
    if qty < p["min_qty"]:
        raise ApiError(f"حداقل سفارش {p['min_qty']} عدد است.")
    link = str(body.get("link") or "").strip()
    if link.startswith("@"):
        link = "https://t.me/" + link[1:]
    elif link.lower().startswith("t.me/"):
        link = "https://" + link
    if not link.lower().startswith(("http://", "https://")):
        raise ApiError("لینک را درست وارد کن (https://t.me/...).")
    emoji = None
    combos = ("ری‌اکشن ترکیبی مثبت🥳", "ری‌اکشن ترکیبی منفی🤮")
    if key == "reaction":
        emoji = str(body.get("emoji") or "")
        if emoji not in bot.REACTION_EMOJIS and emoji not in combos:
            raise ApiError("ری‌اکشن را انتخاب کن.")
    elif key == "premium":
        emoji = str(body.get("emoji") or "") or None  # اختیاری؛ خالی = ترکیبی پرمیومی
        if emoji and emoji not in bot.REACTION_EMOJIS and emoji not in combos:
            raise ApiError("ری‌اکشن را درست انتخاب کن.")
    name = {"views": bot.SIMPLE_SERVICES["views"]["order_name"],
            "members": bot.SIMPLE_SERVICES["members"]["order_name"],
            "reaction": bot.REACTION_ORDER_NAME, "premium": bot.PREMIUM_ORDER_NAME}[key]
    cost = bot.calc_cost(p, qty)
    if not bot.deduct_tokens(uid, cost):
        raise ApiError("موجودی کافی نیست.", code="no_balance")
    code = bot.generate_service_order_code()
    bot.create_service_order(uid, name, qty, cost, link, code, extra=emoji)
    # همزمان (نه در thread): در PythonAnywhere بعد از پاسخ، thread ممکن است قبل از ارسال متوقف شود.
    # اگر ارسال نشد، ربات (invoice_watcher) تا ۳ روز دوباره تلاش می‌کند.
    try:
        bot.notify_admins_service_order(code)
    except Exception:
        traceback.print_exc()
    date_str, time_str = bot.jalali_now_strings()
    bot.send(
        uid,
        f"🚀 *سفارش {name} شما #ثبت شد.*\n\n"
        f"🔍 *کد پیگیری: {code}*\n"
        f"⏰️ *زمان ثبت: {time_str} - {date_str}*",
    )
    return {"ok": True, "code": code, "cost": clean_num(cost), "balance": clean_num(bot.get_balance(uid))}


# ---------------------------------------------------------------- WSGI
def api_transfer(uid, body):
    """انتقال موجودی (همان بانک انتقال ربات)"""
    need_sec(uid, "bk")
    try:
        amount = int(str(body.get("amount")).strip())
        to = int(str(body.get("to")).strip())
    except (TypeError, ValueError):
        raise ApiError("مقدار و آیدی عددی را درست وارد کن.")
    if amount < bot.MIN_TRANSFER_AMOUNT:
        raise ApiError(f"حداقل مقدار انتقال {bot.MIN_TRANSFER_AMOUNT} شاهی است.")
    if to == uid:
        raise ApiError("نمی‌توانی به خودت انتقال بدهی.")
    if not bot.user_exists(to):
        raise ApiError("این کاربر عضو ربات نیست؛ بهش بگو ربات را /start کند.")
    if not bot.transfer_tokens(uid, to, amount):
        raise ApiError("موجودی کافی نیست.", code="no_balance")
    date_str, time_str = bot.jalali_now_strings()
    bot.send(uid, f"✅️ *مقدار {amount} شاهی به کاربر {to} با موفقیت انتقال یافت.*\n"
                  f"⏰️ *زمان انتقال: {time_str} - {date_str}*")
    bot.send(to, f"✅️ *مقدار {amount} شاهی از کاربر {uid} دریافت شد.*\n"
                 f"⏰️ *زمان دریافت: {time_str} - {date_str}*")
    return {"ok": True, "balance": clean_num(bot.get_balance(uid))}


POST_ROUTES = {
    "/api/notices/read": api_notices_read,
    "/api/join/list": api_join_list,
    "/api/join/confirm": api_join_confirm,
    "/api/request": api_request,
    "/api/invoice": api_invoice,
    "/api/service": api_service,
    "/api/transfer": api_transfer,
}


def respond(start_response, status, body, ctype="application/json; charset=utf-8", cache="no-store"):
    if isinstance(body, (dict, list)):
        body = json.dumps(body, ensure_ascii=False)
    if isinstance(body, str):
        body = body.encode("utf-8")
    start_response(status, [("Content-Type", ctype), ("Content-Length", str(len(body))), ("Cache-Control", cache)])
    return [body]


def _index_path():
    """جدیدترین index.html بین static/ و کنار miniapp.py (تا نسخه‌ی قدیمی داخل static جلوی نسخه‌ی تازه را نگیرد)"""
    cands = [os.path.join(STATIC_DIR, "index.html"), os.path.join(HERE, "index.html")]
    cands = [c for c in cands if os.path.isfile(c)]
    return max(cands, key=os.path.getmtime) if cands else os.path.join(STATIC_DIR, "index.html")


def serve_file(start_response, path, cache="no-store"):
    if path == "index.html":
        with open(_index_path(), "rb") as f:
            return respond(start_response, "200 OK", f.read().decode("utf-8"), "text/html; charset=utf-8", cache)
    full = os.path.realpath(os.path.join(STATIC_DIR, path))
    if not full.startswith(os.path.realpath(STATIC_DIR) + os.sep) or not os.path.isfile(full):
        return respond(start_response, "404 Not Found", {"error": "not found"})
    ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
    if ctype.startswith("text/") or ctype in ("application/javascript",):
        ctype += "; charset=utf-8"
    if full.endswith((".woff2", ".woff")):
        cache = "public, max-age=2592000"
    with open(full, "rb") as f:
        return respond(start_response, "200 OK", f.read(), ctype, cache)


def application(environ, start_response):
    path = environ.get("PATH_INFO", "")
    method = environ.get("REQUEST_METHOD", "GET")
    try:
        if path in ("/", "/app") and method == "GET":
            return serve_file(start_response, "index.html")
        if path.startswith("/static/") and method == "GET":
            return serve_file(start_response, path[len("/static/"):], cache="public, max-age=86400")
        if path == "/zp/callback" and method == "GET":
            ensure_ready()
            ok, msg = bot.zp_callback_page(parse_qs(environ.get("QUERY_STRING", "")))
            color = "#16a34a" if ok else "#dc2626"
            page = ("<!doctype html><html lang='fa' dir='rtl'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                    "<title>نتیجه پرداخت</title></head><body style='font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#fff7ea'>"
                    f"<div style='text-align:center;padding:24px'><div style='font-size:56px'>{'✅' if ok else '❌'}</div>"
                    f"<h2 style='color:{color}'>{msg}</h2></div></body></html>")
            return respond(start_response, "200 OK", page, "text/html; charset=utf-8")
        if path.startswith("/api/photo/") and method == "GET":
            ensure_ready()
            code = path.rsplit("/", 1)[1]
            sig = (parse_qs(environ.get("QUERY_STRING", "")).get("s") or [""])[0]
            if not hmac.compare_digest(sig, photo_sig(code)):
                return respond(start_response, "403 Forbidden", {"error": "forbidden"})
            photo = fetch_photo(code)
            if not photo:
                return respond(start_response, "404 Not Found", {"error": "no photo"}, cache="public, max-age=300")
            return respond(start_response, "200 OK", photo[1], photo[0], cache="public, max-age=3600")
        if path.startswith("/api/uphoto/") and method == "GET":
            ensure_ready()
            who = path.rsplit("/", 1)[1]
            sig = (parse_qs(environ.get("QUERY_STRING", "")).get("s") or [""])[0]
            if not who.isdigit() or not hmac.compare_digest(sig, uphoto_sig(who)):
                return respond(start_response, "403 Forbidden", {"error": "forbidden"})
            photo = fetch_uphoto(int(who))
            if not photo:
                return respond(start_response, "404 Not Found", {"error": "no photo"}, cache="public, max-age=300")
            return respond(start_response, "200 OK", photo[1], photo[0], cache="public, max-age=3600")
        if path.startswith("/api/"):
            ensure_ready()
            user = auth_user(environ)
            uid = user["id"]
            try:
                bot.apply_settings(force=False)
            except Exception:
                traceback.print_exc()
            if bot.is_banned(uid):
                return respond(start_response, "403 Forbidden", {"error": "دسترسی شما به ربات مسدود شده است."})
            if uid not in bot.ADMIN_IDS and bot.get_setting("bot_enabled", "1") == "0":
                return respond(start_response, "503 Service Unavailable", {"error": "ربات موقتاً در حال بروزرسانی است؛ کمی بعد دوباره تلاش کن."})
            if path == "/api/fj":
                # بررسی تازه‌ی جوین اجباری (برای دکمه‌ی «عضو شدم» در صفحه‌ی لودینگ)
                bot.fj_forget(uid)
                try:
                    miss = [] if uid in bot.ADMIN_IDS else bot.fj_missing(uid)
                except Exception:
                    miss = []
                return respond(start_response, "200 OK", {"ok": not miss, "fj": [bot.fj_info(e) for e in miss]})
            if uid not in bot.ADMIN_IDS:
                try:
                    miss = bot.fj_missing(uid)
                except Exception:
                    miss = []
                if miss:
                    return respond(start_response, "403 Forbidden", {
                        "error": "برای استفاده از مینی‌اپ ابتدا در کانال‌های اجباری عضو شو.",
                        "code": "fj", "fj": [bot.fj_info(e) for e in miss]})
            if path == "/api/state" and method == "GET":
                return respond(start_response, "200 OK", build_state(user))
            if path == "/api/leaderboard" and method == "GET":
                bot.upsert_user(user)
                return respond(start_response, "200 OK", api_leaderboard(uid, parse_qs(environ.get("QUERY_STRING", ""))))
            handler = POST_ROUTES.get(path)
            if handler and method == "POST":
                try:
                    size = int(environ.get("CONTENT_LENGTH") or 0)
                except ValueError:
                    size = 0
                raw = environ["wsgi.input"].read(min(size, 20000)) if size else b""
                body = json.loads(raw or b"{}")
                bot.upsert_user(user)
                lock = bot.user_lock(uid)
                if not lock.acquire(timeout=10):
                    raise ApiError("درخواست قبلی در حال انجام است.", 429)
                try:
                    return respond(start_response, "200 OK", handler(uid, body))
                finally:
                    lock.release()
        return respond(start_response, "404 Not Found", {"error": "not found"})
    except ApiError as e:
        return respond(start_response, f"{e.status} Error", {"ok": False, "error": e.message, "code": e.code})
    except Exception:
        traceback.print_exc()
        return respond(start_response, "500 Internal Server Error", {"ok": False, "error": "خطای سرور"})

if __name__ == "__main__":
    from wsgiref.simple_server import make_server
    print("http://127.0.0.1:8000/app")
    make_server("127.0.0.1", 8000, application).serve_forever()
