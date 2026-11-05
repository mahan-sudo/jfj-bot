"""🌐 پنل مدیریت تحت وب — آدرس: /admin
ورود: آیدی عددی ادمین + رمز تصادفیِ مخصوص همان ادمین (از دکمه‌ی «🌐 پنل تحت وب» در پنل ربات ساخته می‌شود).
رمزها هش‌شده (PBKDF2) ذخیره می‌شوند؛ نشست با کوکی امضاشده (HttpOnly + SameSite=Strict).
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
import traceback
from urllib.parse import parse_qs

bot = None            # ماژول bot_test
HERE = os.path.dirname(os.path.abspath(__file__))
SESSION_TTL = 12 * 3600
COOKIE = "jfj_admin"
PBKDF_ROUNDS = 150_000
LOCK_FAILS = 5
LOCK_SECONDS = 600
_fails = {}           # (ip, id) -> [count, first_ts]
_flock = threading.Lock()
_ready = [False]


EXT = {}       # (method, name, act) -> fn(uid, arg, body, qs)


def api(method, name, act=None):
    def deco(fn):
        EXT[(method, name, act)] = fn
        return fn
    return deco


class WebErr(Exception):
    def __init__(self, msg, status=400):
        self.msg, self.status = msg, status


def init(bot_module):
    global bot
    bot = bot_module


def _tables():
    if _ready[0]:
        return
    with bot.get_db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS web_admins (
            user_id BIGINT PRIMARY KEY,
            salt TEXT NOT NULL,
            pw_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_login TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS web_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id BIGINT NOT NULL,
            action TEXT NOT NULL,
            detail TEXT,
            ts TEXT NOT NULL)""")
    _ready[0] = True


# ---------------- رمزها ----------------
_ALPHA = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def gen_password():
    parts = ["".join(secrets.choice(_ALPHA) for _ in range(4)) for _ in range(4)]
    return "-".join(parts)          # مثل  Xk7q-Pz93-mT2w-Hb8d  (۱۶ نویسه‌ی تصادفی ≈ ۹۰ بیت)


def _hash(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt.encode(), PBKDF_ROUNDS).hex()


def set_password(user_id, pw=None):
    """رمز جدید می‌سازد/جایگزین می‌کند و (برای نمایش به ادمین) برمی‌گرداند. نشست‌های قبلی خودبه‌خود باطل می‌شوند."""
    _tables()
    pw = pw or gen_password()
    salt = secrets.token_hex(8)
    with bot.get_db() as c:
        c.execute("INSERT INTO web_admins (user_id, salt, pw_hash, created_at) VALUES (?,?,?,?) "
                  "ON CONFLICT (user_id) DO UPDATE SET salt=excluded.salt, pw_hash=excluded.pw_hash, created_at=excluded.created_at",
                  (user_id, salt, _hash(pw, salt), bot.now_local().isoformat()))
    return pw


def _row(uid):
    _tables()
    with bot.get_db() as c:
        return c.execute("SELECT salt, pw_hash FROM web_admins WHERE user_id=?", (uid,)).fetchone()


def _secret():
    return hashlib.sha256(("webadmin|" + bot.BOT_TOKEN).encode()).digest()


def _sign(payload):
    return hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()[:40]


def make_session(uid, pw_hash):
    exp = int(time.time()) + SESSION_TTL
    p = "%d|%d|%s" % (uid, exp, pw_hash[:12])
    return base64.urlsafe_b64encode(p.encode()).decode() + "." + _sign(p)


def read_session(token):
    try:
        b64, sig = token.rsplit(".", 1)
        p = base64.urlsafe_b64decode(b64.encode()).decode()
        if not hmac.compare_digest(sig, _sign(p)):
            return None
        uid, exp, fp = p.split("|")
        uid, exp = int(uid), int(exp)
        if exp < time.time() or uid not in bot.ADMIN_IDS:
            return None
        row = _row(uid)
        if not row or row[1][:12] != fp:
            return None       # رمز عوض شده
        return uid
    except Exception:
        return None


def _ip(environ):
    xf = environ.get("HTTP_X_FORWARDED_FOR", "")
    return (xf.split(",")[0].strip() if xf else environ.get("REMOTE_ADDR", "")) or "?"


def login(environ, body):
    ip = _ip(environ)
    try:
        uid = int(str(body.get("id", "")).strip().translate(bot._ASCII_DIGITS))
    except ValueError:
        raise WebErr("آیدی عددی نامعتبر است.", 400)
    pw = str(body.get("password", "")).strip()
    key = (ip, uid)
    now = time.time()
    with _flock:
        f = _fails.get(key)
        if f and now - f[1] > LOCK_SECONDS:
            _fails.pop(key, None)
            f = None
        if f and f[0] >= LOCK_FAILS:
            raise WebErr("تعداد تلاش‌های ناموفق زیاد بود؛ %d دقیقه بعد دوباره تلاش کن." % (LOCK_SECONDS // 60 + 1), 429)
    row = _row(uid) if uid in bot.ADMIN_IDS else None
    good = False
    if row:
        good = hmac.compare_digest(_hash(pw, row[0]), row[1])
    else:
        _hash(pw, "00000000")      # زمان یکسان برای حدس نزدن وجود آیدی
    if not good:
        with _flock:
            f = _fails.setdefault(key, [0, now])
            f[0] += 1
        raise WebErr("آیدی یا رمز اشتباه است.", 401)
    with _flock:
        _fails.pop(key, None)
    with bot.get_db() as c:
        c.execute("UPDATE web_admins SET last_login=? WHERE user_id=?", (bot.now_local().isoformat(), uid))
    return uid, make_session(uid, row[1])


# ---------------- ابزار داده ----------------
def _q(sql, args=()):
    with bot.get_db() as c:
        return c.execute(sql, args).fetchall()


def _q1(sql, args=()):
    with bot.get_db() as c:
        r = c.execute(sql, args).fetchone()
    return r[0] if r else 0


def _num(v):
    try:
        f = float(v)
        return int(f) if f == int(f) else round(f, 2)
    except Exception:
        return v


def dashboard(uid):
    now = bot.now_local()
    today = bot._utc_str(now.replace(hour=0, minute=0, second=0, microsecond=0))
    return {
        "bot_on": bot.get_setting("bot_enabled", "1") != "0",
        "users": _q1("SELECT COUNT(*) FROM users"),
        "new_today": _q1("SELECT COUNT(*) FROM users WHERE created_at >= ?", (today,)),
        "banned": _q1("SELECT COUNT(*) FROM users WHERE banned=1"),
        "sales_today": _num(_q1("SELECT COALESCE(SUM(final_amount),0) FROM invoices WHERE status='paid' AND created_at >= ?", (today,))),
        "sales_all": _num(_q1("SELECT COALESCE(SUM(final_amount),0) FROM invoices WHERE status='paid'")),
        "pending_receipts": _q1("SELECT COUNT(*) FROM invoices WHERE status='review'"),
        "pending_orders": _q1("SELECT COUNT(*) FROM service_orders WHERE status='pending'"),
        "active_requests": _q1("SELECT COUNT(*) FROM requests WHERE status NOT IN ('completed','cancelled','removed','deleted','relinked')"),
        "tokens_total": _num(_q1("SELECT COALESCE(SUM(tokens),0) FROM users")),
        "betrayers": _q1("SELECT COUNT(*) FROM betrayers"),
        "overrides": (bot.TEXTS.overrides_count() if getattr(bot, "TEXTS", None) else 0),
        "admin_id": uid,
    }


def toggle_bot(uid, body):
    on = bool(body.get("on"))
    bot.set_setting("bot_enabled", "1" if on else "0")
    return {"ok": True, "bot_on": on}


def _user_dict(r):
    return {"id": r[0], "name": r[1] or "", "username": r[2] or "", "tokens": _num(r[3]), "banned": bool(r[4]),
            "created": str(r[5] or "")[:16], "phone": r[6] or ""}


_UCOLS = "id, first_name, username, tokens, banned, created_at, phone"


def users_list(uid, qs):
    q = (qs.get("q") or [""])[0].strip().lstrip("@")
    page = max(0, int((qs.get("page") or ["0"])[0] or 0))
    sort = (qs.get("sort") or ["new"])[0]
    order = {"new": "created_at DESC", "rich": "tokens DESC", "neg": "tokens ASC"}.get(sort, "created_at DESC")
    flt = {"neg": "tokens<0", "banned": "banned=1", "betray": "id IN (SELECT user_id FROM betrayers)",
           "phone": "COALESCE(phone,'')<>''"}.get(sort)
    conds, args = [], []
    if flt:
        conds.append(flt)
    if q:
        like = "%" + q.lower() + "%"
        conds.append("(CAST(id AS TEXT)=? OR LOWER(COALESCE(username,'')) LIKE ? OR LOWER(COALESCE(first_name,'')) LIKE ?)")
        args += [q, like, like]
    wh = ("WHERE " + " AND ".join(conds)) if conds else ""
    rows = _q(f"SELECT {_UCOLS} FROM users {wh} ORDER BY {order} LIMIT 31 OFFSET ?", tuple(args) + (page * 30,))
    total = _q1(f"SELECT COUNT(*) FROM users {wh}", tuple(args))
    return {"users": [_user_dict(r) for r in rows[:30]], "page": page, "more": len(rows) > 30, "total": total}


def user_detail(uid, target):
    rows = _q(f"SELECT {_UCOLS} FROM users WHERE id=?", (target,))
    if not rows:
        raise WebErr("کاربر پیدا نشد.", 404)
    u = _user_dict(rows[0])
    u["is_admin"] = target in bot.ADMIN_IDS
    u["requests"] = [{"code": r[0], "count": r[1], "status": r[2], "link": r[3] or "", "created": str(r[4])[:16]} for r in
                     _q("SELECT tracking_code, member_count, status, link, created_at FROM requests WHERE user_id=? ORDER BY created_at DESC LIMIT 10", (target,))]
    u["invoices"] = [{"code": r[0], "product": r[1], "amount": _num(r[2]), "status": r[3], "created": str(r[4])[:16]} for r in
                     _q("SELECT code, product_name, final_amount, status, created_at FROM invoices WHERE buyer_id=? ORDER BY created_at DESC LIMIT 10", (target,))]
    u["joins"] = _q1("SELECT COUNT(*) FROM joins WHERE user_id=?", (target,))
    u["left"] = _q1("SELECT COUNT(*) FROM joins WHERE user_id=? AND left_at IS NOT NULL", (target,))
    u["betrayer"] = bool(_q1("SELECT COUNT(*) FROM betrayers WHERE user_id=?", (target,)))
    return u


def user_tokens(uid, target, body):
    mode = body.get("mode")
    try:
        amount = float(str(body.get("amount")).translate(bot._ASCII_DIGITS))
    except ValueError:
        raise WebErr("مقدار نامعتبر است.")
    if amount < 0 or amount != amount:
        raise WebErr("مقدار نامعتبر است.")
    if not _q("SELECT 1 FROM users WHERE id=?", (target,)):
        raise WebErr("کاربر پیدا نشد.", 404)
    with bot.user_lock(target):
        cur = float(bot.get_balance(target))
        new = {"add": cur + amount, "sub": cur - amount, "set": amount}.get(mode)
        if new is None:
            raise WebErr("نوع عملیات نامعتبر است.")
        with bot.get_db() as c:
            c.execute("UPDATE users SET tokens=? WHERE id=?", (new, target))
    try:
        bot.send(target, f"🪙 *موجودی شما توسط مدیریت تغییر کرد.*\n💎 *موجودی فعلی: {bot.fmt_tokens(new)} شاهی*")
    except Exception:
        pass
    return {"ok": True, "tokens": _num(new)}


def user_ban(uid, target, body):
    if target in bot.ADMIN_IDS:
        raise WebErr("ادمین را نمی‌شود مسدود کرد.")
    with bot.get_db() as c:
        c.execute("UPDATE users SET banned = 1 - banned, updated_at=CURRENT_TIMESTAMP WHERE id=?", (target,))
    return {"ok": True, "banned": bool(_q1("SELECT banned FROM users WHERE id=?", (target,)))}


def user_dm(uid, target, body):
    text = str(body.get("text", "")).strip()
    if not text:
        raise WebErr("متن خالی است.")
    r = bot.tg("sendMessage", chat_id=target, text=text[:3900], parse_mode="HTML", disable_web_page_preview=True, _notx=True) \
        if body.get("html") else bot.tg("sendMessage", chat_id=target, text=text[:3900], _notx=True)
    if not r.get("ok"):
        raise WebErr("ارسال نشد: " + str(r.get("description", ""))[:120])
    return {"ok": True}


def invoices_list(uid, qs):
    st = (qs.get("status") or ["review"])[0]
    where, args = ("", ())
    if st != "all":
        where, args = "WHERE status=?", (st,)
    rows = _q(f"SELECT code, buyer_id, product_name, final_amount, status, kind, created_at FROM invoices {where} ORDER BY created_at DESC LIMIT 50", args)
    return {"invoices": [{"code": r[0], "buyer": r[1], "product": r[2], "amount": _num(r[3]), "status": r[4], "kind": r[5], "created": str(r[6])[:16]} for r in rows]}


def invoice_review(uid, code, body):
    ok = bool(body.get("ok"))
    inv = bot.get_invoice(code)
    if not inv:
        raise WebErr("فاکتور پیدا نشد.", 404)
    buyer_id = inv[0]
    if not bot.set_invoice_status(code, "paid" if ok else "rejected", expected_status="review"):
        raise WebErr("این رسید قبلاً بررسی شده است (یا در وضعیت بررسی نیست).")
    with bot.get_db() as c:
        meta = c.execute("SELECT meta FROM invoices WHERE code=?", (code,)).fetchone()[0]
    try:
        meta = json.loads(meta or "{}")
    except Exception:
        meta = {}
    who = "پنل وب (%d)" % uid
    if ok:
        bot.apply_paid_invoice(code)
    else:
        bot.send(buyer_id, f"❌ *رسید شما برای فاکتور {code} تأیید نشد.*\n{bot.stamp('زمان بررسی')}\n\n☎️ *در صورت اشتباه بودن، به پشتیبانی پیام دهید: {bot.SUPPORT_ID}*")
        bot.dc_release(meta.get("dc"))
    try:
        bot.rep_ev_receipt_result(code, ok, who)
    except Exception:
        traceback.print_exc()
    return {"ok": True}


_REQ_DONE = ("completed", "cancelled", "removed", "deleted", "relinked")


def requests_list(uid, qs):
    """in_progress = «در جریان» (هر وضعیتی جز پایانی‌ها، مثل ربات)، done = تکمیل‌شده، closed = حذف/لغو/تغییر لینک"""
    st = (qs.get("status") or ["in_progress"])[0]
    q = (qs.get("q") or [""])[0].strip().lstrip("@")
    ph = ",".join("?" * len(_REQ_DONE))
    where, args = {"in_progress": (f"WHERE r.status NOT IN ({ph})", _REQ_DONE), "done": ("WHERE r.status='completed'", ()),
                   "closed": ("WHERE r.status IN ('cancelled','removed','deleted','relinked')", ())}.get(st, ("", ()))
    if q:
        where += (" AND " if where else "WHERE ") + "(r.tracking_code=? OR CAST(r.user_id AS TEXT)=? OR LOWER(r.link) LIKE ?)"
        args = args + (q, q, "%" + q.lower() + "%")
    rows = _q("SELECT r.tracking_code, r.user_id, r.member_count, r.token_cost, r.link, r.status, r.created_at, u.first_name, u.username, "
              "(SELECT COUNT(*) FROM joins j WHERE j.tracking_code=r.tracking_code AND j.left_at IS NULL), "
              "(SELECT COUNT(*) FROM joins j WHERE j.tracking_code=r.tracking_code AND j.left_at IS NOT NULL) "
              f"FROM requests r LEFT JOIN users u ON u.id=r.user_id {where} ORDER BY r.created_at DESC LIMIT 60", args)
    out = []
    for r in rows:
        out.append({"code": r[0], "user": r[1], "count": r[2], "cost": _num(r[3]), "link": r[4] or "", "status": r[5], "created": str(r[6])[:16],
                    "name": r[7] or "", "username": r[8] or "", "done": r[9], "left": r[10]})
    return {"requests": out}


def request_remove(uid, code, body):
    with bot.get_db() as c:
        cur = c.execute("UPDATE requests SET status='removed' WHERE tracking_code=? AND status='in_progress'", (code,))
    if not cur.rowcount:
        raise WebErr("درخواست در حال انجام نیست.")
    try:
        bot.rep_ev_request_state(code, "removed")
    except Exception:
        traceback.print_exc()
    return {"ok": True}


def settings_get(uid):
    out = []
    for k, d in bot.SETTING_DEFS.items():
        out.append({"key": k, "label": d["label"], "unit": d["unit"], "kind": d["kind"], "min": d["min"], "value": _num(bot._cfg_value(k)), "icon": d["icon"]})
    texts = [{"key": k, "label": d["label"], "value": str(getattr(bot, d["g"], ""))} for k, d in bot.TEXT_DEFS.items()]
    return {"settings": out, "texts": texts, "bot_on": bot.get_setting("bot_enabled", "1") != "0"}


def settings_set(uid, body):
    key = body.get("key")
    val = body.get("value")
    if key in bot.SETTING_DEFS:
        d = bot.SETTING_DEFS[key]
        n = bot.parse_number(str(val))
        if n is None or n < d["min"] or (d["kind"] == "int" and n != int(n)):
            raise WebErr("مقدار نامعتبر است (حداقل %s)." % d["min"])
        bot.set_setting("cfg_" + key, n * d["mul"])
    elif key in bot.TEXT_DEFS:
        val = str(val).strip()
        if not 2 <= len(val) <= 100:
            raise WebErr("طول مقدار نامعتبر است.")
        if key == "card":
            digits = val.translate(bot._ASCII_DIGITS).replace("-", "").replace(" ", "")
            if not digits.isdigit() or len(digits) != 16:
                raise WebErr("شماره کارت باید ۱۶ رقم باشد.")
            val = "-".join(digits[i:i + 4] for i in range(0, 16, 4))
        bot.set_setting("cfg_" + key, val)
    else:
        raise WebErr("تنظیم ناشناخته.")
    bot.apply_settings()
    return {"ok": True}


# ---------------- متون ----------------
def _texts():
    T = getattr(bot, "TEXTS", None)
    if T is None:
        raise WebErr("ماژول متون فعال نیست.", 503)
    return T


def _tvars(it):
    """جاهای متغیر یک متن: [{n:'1', ex:'نمونه/عبارت'}]"""
    out, seen = [], set()
    for m in re.finditer(r"\{(\w+)\}", it["tpl"]):
        nm = m.group(1)
        if nm in seen:
            continue
        seen.add(nm)
        ex = it["ex"][int(nm) - 1][:50] if nm.isdigit() and int(nm) - 1 < len(it["ex"]) else ""
        out.append({"n": nm, "ex": ex})
    return out


def texts_list(uid, qs):
    T = _texts()
    cat = T.catalog()
    out = []
    for g, keys in T.groups().items():
        out.append({"group": g, "items": [{"key": k, "n": cat[k]["n"], "tpl": cat[k]["tpl"], "fns": cat[k]["fns"][:2], "ex": cat[k]["ex"],
                                            "edited": k in T._ov, "html": T._ov.get(k, ""), "vars": _tvars(cat[k]), "where": T._where(cat[k]), "prev": T._preview_html(cat[k]["tpl"])} for k in keys]})
    return {"groups": out, "edited": T.overrides_count()}


def text_set(uid, key, body):
    T = _texts()
    if key not in T.catalog():
        raise WebErr("متن پیدا نشد.", 404)
    html = str(body.get("html", "")).strip()
    if not html:
        raise WebErr("متن خالی است.")
    if len(html) > 3800:
        raise WebErr("متن خیلی بلند است.")
    r = bot.tg("sendMessage", chat_id=uid, text=html, parse_mode="HTML", disable_web_page_preview=True, _notx=True)
    if not r.get("ok"):
        raise WebErr("تلگرام این متن را نپذیرفت: " + str(r.get("description", ""))[:120])
    T.set_override(key, html)
    return {"ok": True}


def text_reset(uid, key, body):
    T = _texts()
    T.del_override(key)
    return {"ok": True}


# ---------------- اطلاعیه / خائن‌ها / بکاپ ----------------
def broadcast(uid, body):
    text = str(body.get("text", "")).strip()
    aud = body.get("aud")
    if aud not in ("all", "active", "new", "chan"):
        raise WebErr("مخاطب نامعتبر است.")
    if not text:
        raise WebErr("متن خالی است.")
    r = bot.tg("sendMessage", chat_id=uid, text=text[:3900], parse_mode="HTML", disable_web_page_preview=True, _notx=True)
    if not r.get("ok"):
        raise WebErr("متن پذیرفته نشد: " + str(r.get("description", ""))[:120])
    jid = bot.bc_create(uid, uid, uid, r["result"]["message_id"], aud, pin=1 if body.get("pin") else 0)
    return {"ok": True, "job": jid, "targets": len(bot.bc_targets(aud))}


def betrayers_list(uid, qs):
    rows = _q("SELECT b.user_id, u.first_name, u.username, b.flagged_at, b.last_run, b.runs, b.kicked, b.orders "
              "FROM betrayers b LEFT JOIN users u ON u.id=b.user_id ORDER BY b.flagged_at DESC LIMIT 100")
    return {"betrayers": [{"id": r[0], "name": r[1] or "", "username": r[2] or "", "flagged": str(r[3])[:16], "last": str(r[4] or "")[:16],
                           "runs": r[5], "kicked": r[6], "orders": r[7]} for r in rows],
            "min_joins": bot.BETRAY_MIN_JOINS}


def betrayer_rerun(uid, target, body):
    if not _q("SELECT 1 FROM betrayers WHERE user_id=?", (target,)):
        raise WebErr("این کاربر در فهرست نیست.", 404)
    threading.Thread(target=bot.betray_run, args=(target, False), daemon=True).start()
    return {"ok": True}


def betrayer_unflag(uid, target, body):
    with bot.get_db() as c:
        cur = c.execute("DELETE FROM betrayers WHERE user_id=?", (target,))
    if not cur.rowcount:
        raise WebErr("این کاربر در فهرست نیست.", 404)
    return {"ok": True}


def backup_bytes():
    data = bot.backup_dump()
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


_NOAUDIT = ("login", "logout", "upload")


def audit(uid, sub, body):
    """ثبت هر عملیات تغییردهنده‌ی ادمین‌های وب (بدون متن‌های بلند و رمزها)"""
    try:
        _tables()
        keep = {}
        for k, v in (body or {}).items():
            if k in ("password", "text", "html"):
                keep[k] = "…"
            elif isinstance(v, (int, float, bool)) or v is None:
                keep[k] = v
            else:
                keep[k] = str(v)[:40]
        with bot.get_db() as c:
            c.execute("INSERT INTO web_audit (admin_id, action, detail, ts) VALUES (?,?,?,?)",
                      (uid, sub[:80], json.dumps(keep, ensure_ascii=False)[:300], bot.now_local().isoformat()))
    except Exception:
        traceback.print_exc()


# ---------------- مسیریابی ----------------
def _json(start_response, status, obj, extra=None):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    h = [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body))), ("Cache-Control", "no-store")]
    h += extra or []
    start_response(status, h)
    return [body]


def _cookie(environ):
    for part in environ.get("HTTP_COOKIE", "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == COOKIE:
            return v
    return ""


def _secure(environ):
    return environ.get("HTTP_X_FORWARDED_PROTO", environ.get("wsgi.url_scheme", "")) == "https"


def _page(start_response):
    with open(os.path.join(HERE, "webadmin.html"), "rb") as f:
        body = f.read()
    start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(body))), ("Cache-Control", "no-store"),
                              ("X-Frame-Options", "DENY"), ("Referrer-Policy", "no-referrer"), ("X-Content-Type-Options", "nosniff"),
                              ("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; font-src 'self' https://cdn.jsdelivr.net; script-src 'self' 'unsafe-inline'; img-src 'self' data: https://cdn.jsdelivr.net")])
    return [body]


_ASSET_TYPES = {".webp": "image/webp", ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf", ".png": "image/png", ".svg": "image/svg+xml"}


def _asset(start_response, name):
    """لوگوی webp و فونت‌ها (Peyda/Estedad) از پوشه‌ی webadmin_assets؛ فایلِ ناموجود = ۴۰۴ و مرورگر فونت بعدی را استفاده می‌کند"""
    base = os.path.realpath(os.path.join(HERE, "webadmin_assets"))
    full = os.path.realpath(os.path.join(base, name))
    ext = os.path.splitext(full)[1].lower()
    if not full.startswith(base + os.sep) or ext not in _ASSET_TYPES or not os.path.isfile(full):
        return _json(start_response, "404 Not Found", {"error": "not found"})
    with open(full, "rb") as f:
        data = f.read()
    start_response("200 OK", [("Content-Type", _ASSET_TYPES[ext]), ("Content-Length", str(len(data))), ("Cache-Control", "public, max-age=2592000")])
    return [data]


def handle(environ, start_response):
    """True/لیست پاسخ برای مسیرهای /admin؛ None یعنی این درخواست مال پنل نیست"""
    path = environ.get("PATH_INFO", "")
    if not (path == "/admin" or path.startswith("/admin/")):
        return None
    method = environ.get("REQUEST_METHOD", "GET")
    try:
        if path in ("/admin", "/admin/") and method == "GET":
            return _page(start_response)
        if path.startswith("/admin/assets/") and method == "GET":
            return _asset(start_response, path[len("/admin/assets/"):])
        if not path.startswith("/admin/api/"):
            return _json(start_response, "404 Not Found", {"error": "not found"})
        sub = path[len("/admin/api/"):]
        qs = parse_qs(environ.get("QUERY_STRING", ""))
        body = {}
        if method == "POST" and sub == "upload":
            if environ.get("HTTP_X_REQUESTED_WITH") != "jfj":
                raise WebErr("درخواست نامعتبر.", 403)
            uid = read_session(_cookie(environ))
            if not uid:
                return _json(start_response, "401 Unauthorized", {"error": "auth", "login": True})
            R = webadmin_ext.upload(uid, environ, qs)
            audit(uid, "upload", {"kind": (qs.get("kind") or [""])[0]})
            return _json(start_response, "200 OK", R)
        if method == "POST":
            if environ.get("HTTP_X_REQUESTED_WITH") != "jfj":
                raise WebErr("درخواست نامعتبر.", 403)
            try:
                size = int(environ.get("CONTENT_LENGTH") or 0)
            except ValueError:
                size = 0
            raw = environ["wsgi.input"].read(min(size, 200000)) if size else b""
            body = json.loads(raw or b"{}")
        if sub == "login" and method == "POST":
            uid, tok = login(environ, body)
            ck = "%s=%s; Path=/admin; HttpOnly; SameSite=Strict; Max-Age=%d%s" % (COOKIE, tok, SESSION_TTL, "; Secure" if _secure(environ) else "")
            return _json(start_response, "200 OK", {"ok": True, "id": uid}, [("Set-Cookie", ck)])
        if sub == "logout" and method == "POST":
            return _json(start_response, "200 OK", {"ok": True}, [("Set-Cookie", "%s=; Path=/admin; Max-Age=0; HttpOnly; SameSite=Strict" % COOKIE)])
        uid = read_session(_cookie(environ))
        if not uid:
            return _json(start_response, "401 Unauthorized", {"error": "auth", "login": True})
        try:
            bot.apply_settings(force=False)
        except Exception:
            traceback.print_exc()
        m = re.match(r"^([a-z]+)(?:/([^/]+))?(?:/([a-z]+))?$", sub)
        if not m:
            raise WebErr("not found", 404)
        a, arg, act = m.groups()
        R = None
        if method == "GET":
            if a == "me":
                R = {"id": uid}
            elif a == "dashboard":
                R = dashboard(uid)
            elif a == "users" and not arg:
                R = users_list(uid, qs)
            elif a == "user" and arg:
                R = user_detail(uid, int(arg))
            elif a == "invoices":
                R = invoices_list(uid, qs)
            elif a == "requests":
                R = requests_list(uid, qs)
            elif a == "settings":
                R = settings_get(uid)
            elif a == "texts":
                R = texts_list(uid, qs)
            elif a == "betrayers":
                R = betrayers_list(uid, qs)
            elif a == "backup":
                data = backup_bytes()
                fn = "jfj-backup-%s.json" % bot.now_local().strftime("%Y%m%d-%H%M")
                start_response("200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(data))),
                                          ("Content-Disposition", 'attachment; filename="%s"' % fn), ("Cache-Control", "no-store")])
                return [data]
        elif method == "POST":
            if a == "bot":
                R = toggle_bot(uid, body)
            elif a == "user" and arg and act == "tokens":
                R = user_tokens(uid, int(arg), body)
            elif a == "user" and arg and act == "ban":
                R = user_ban(uid, int(arg), body)
            elif a == "user" and arg and act == "dm":
                R = user_dm(uid, int(arg), body)
            elif a == "invoice" and arg:
                R = invoice_review(uid, arg, body)
            elif a == "request" and arg and act == "remove":
                R = request_remove(uid, arg, body)
            elif a == "settings":
                R = settings_set(uid, body)
            elif a == "text" and arg and act == "set":
                R = text_set(uid, arg, body)
            elif a == "text" and arg and act == "reset":
                R = text_reset(uid, arg, body)
            elif a == "broadcast":
                R = broadcast(uid, body)
            elif a == "betrayer" and arg and act == "rerun":
                R = betrayer_rerun(uid, int(arg), body)
            elif a == "betrayer" and arg and act == "unflag":
                R = betrayer_unflag(uid, int(arg), body)
        if R is None:
            fn = EXT.get((method, a, act)) or EXT.get((method, a, None))
            if fn is None:
                raise WebErr("not found", 404)
            R = fn(uid, arg, body, qs)
        if method == "POST":
            audit(uid, sub, body)
        return _json(start_response, "200 OK", R)
    except WebErr as e:
        return _json(start_response, "%d Error" % e.status, {"ok": False, "error": e.msg})
    except Exception:
        traceback.print_exc()
        return _json(start_response, "500 Internal Server Error", {"ok": False, "error": "خطای سرور"})


import webadmin_ext  # noqa: E402,F401  (مسیرهای بیشتر: مالی، محصولات، بازی‌ها، …)
