"""مسیرهای تکمیلی پنل وب: نمودارها، سفارش خدمات، محصولات، بسته‌ها، مالی، جوین اجباری، بخش‌ها، اسپانسری،
بازی‌ها، گزارشات، کدهای تخفیف، مسدودها و …  (همان کارهایی که پنل داخل ربات می‌کند، با همان کلیدهای تنظیمات)"""
import json
import re
import time
import traceback
from datetime import datetime, timedelta, timezone

import webadmin as W
from webadmin import WebErr, api

bot = None


def _b():
    return W.bot


def _num(v, lo=None, hi=None, integer=False, name="مقدار"):
    b = _b()
    n = b.parse_number(str(v)) if v is not None else None
    if n is None or n != n:
        raise WebErr(f"{name} نامعتبر است.")
    if lo is not None and n < lo:
        raise WebErr(f"{name} باید حداقل {lo} باشد.")
    if hi is not None and n > hi:
        raise WebErr(f"{name} باید حداکثر {hi} باشد.")
    if integer and n != int(n):
        raise WebErr(f"{name} باید عدد صحیح باشد.")
    return int(n) if integer else n


def _flag(key, default="0"):
    return _b().sbool(key, default)


def _tog(key, default="0"):
    new = "0" if _flag(key, default) else "1"
    _b().set_setting(key, new)
    return new == "1"


# ============ نمودارها ============
def _daily(sql, days):
    start = (datetime.now(timezone.utc) - timedelta(days=days - 1)).date()
    rows = W._q(sql, (start.isoformat(),))
    got = {str(r[0]): float(r[1] or 0) for r in rows}
    out = []
    for i in range(days):
        d = (start + timedelta(days=i)).isoformat()
        out.append({"d": d, "v": got.get(d, 0)})
    return out


@api("GET", "charts")
def charts(uid, arg, body, qs):
    days = int((qs.get("days") or ["14"])[0])
    days = days if days in (7, 14, 30, 90) else 14
    sales = _daily("SELECT substr(created_at,1,10) d, SUM(final_amount) FROM invoices WHERE status='paid' AND substr(created_at,1,10) >= ? GROUP BY 1", days)
    users = _daily("SELECT substr(created_at,1,10) d, COUNT(*) FROM users WHERE substr(created_at,1,10) >= ? GROUP BY 1", days)
    reqs = _daily("SELECT substr(created_at,1,10) d, COUNT(*) FROM requests WHERE substr(created_at,1,10) >= ? GROUP BY 1", days)
    kinds = W._q("SELECT kind, COALESCE(SUM(final_amount),0), COUNT(*) FROM invoices WHERE status='paid' GROUP BY kind ORDER BY 2 DESC")
    st = W._q("SELECT status, COUNT(*) FROM requests GROUP BY status ORDER BY 2 DESC")
    return {"days": days, "sales": sales, "users": users, "requests": reqs,
            "kinds": [{"k": r[0], "v": W._num(r[1]), "n": r[2]} for r in kinds],
            "req_status": [{"k": r[0], "n": r[1]} for r in st]}


# ============ سفارش خدمات ============
@api("GET", "orders")
def orders_list(uid, arg, body, qs):
    st = (qs.get("status") or ["pending"])[0]
    where, args = ("", ())
    if st != "all":
        where, args = "WHERE status=?", (st,)
    rows = W._q(f"SELECT tracking_code, user_id, service, quantity, token_cost, status, created_at, link FROM service_orders {where} ORDER BY created_at DESC LIMIT 60", args)
    return {"orders": [{"code": r[0], "user": r[1], "service": r[2], "qty": W._num(r[3]), "cost": W._num(r[4]), "status": r[5], "created": str(r[6])[:16], "link": r[7] or ""} for r in rows]}


@api("POST", "order")
def order_review(uid, code, body, qs):
    b = _b()
    ok = bool(body.get("ok"))
    new_status = "completed" if ok else "cancelled"
    with b.get_db() as c:
        row = c.execute("SELECT user_id, service, token_cost FROM service_orders WHERE tracking_code=?", (code,)).fetchone()
        if not row:
            raise WebErr("سفارش پیدا نشد.", 404)
        cur = c.execute("UPDATE service_orders SET status=? WHERE tracking_code=? AND status='pending'", (new_status, code))
        if cur.rowcount != 1:
            raise WebErr("این سفارش قبلاً بررسی شده است.")
        if not ok:
            c.execute("UPDATE users SET tokens = tokens + ? WHERE id=?", (row[2], row[0]))
    who = f"پنل وب ({uid})"
    try:
        b.rep_ev_service_result(code, ok, who)
    except Exception:
        traceback.print_exc()
    user_id, service, cost = row
    if ok:
        b.send(user_id, f"✅ *سفارش {service} شما به کد پیگیری {code} تکمیل شد.*\n{b.stamp('زمان تکمیل')}")
    else:
        b.send(user_id, f"❌ *سفارش {service} شما به کد پیگیری {code} لغو شد.*\n{b.stamp('زمان لغو')}\n\n🪙 *{b.fmt_tokens(cost)} شاهی به حساب شما برگشت.*")
    return {"ok": True}


# ============ محصولات ============
@api("GET", "products")
def products_list(uid, arg, body, qs):
    b = _b()
    out = []
    for k, d in b.PRODUCT_DEFS.items():
        p = b.get_product(k)
        out.append({"key": k, "title": d.get("title") or d.get("label") or k, "enabled": p["enabled"], "min": p["min_qty"], "rate": W._num(p["rate_cost"])})
    return {"products": out}


@api("POST", "product")
def product_set(uid, key, body, qs):
    b = _b()
    if key not in b.PRODUCT_DEFS:
        raise WebErr("محصول ناشناخته.", 404)
    f = body.get("field")
    if f == "enabled":
        b.set_product_field(key, "enabled", 1 if body.get("value") else 0)
    elif f == "min_qty":
        b.set_product_field(key, "min_qty", _num(body.get("value"), 1, integer=True, name="حداقل خرید"))
    elif f == "rate_cost":
        b.set_product_field(key, "rate_cost", _num(body.get("value"), 0.0001, name="قیمت"))
    else:
        raise WebErr("فیلد نامعتبر.")
    return {"ok": True}


# ============ بسته‌های شاهی / اسپانسری ============
@api("GET", "packs")
def packs_get(uid, arg, body, qs):
    b = _b()
    return {"j": [dict(p, final=W._num(b.jt_price_info(p)[0]), pct=W._num(b.jt_price_info(p)[2])) for p in b.JTOKEN_PRODUCTS],
            "p": list(b.SPONSOR_PRODUCTS), "unit_price": W._num(b.unit_price())}


@api("POST", "packs")
def packs_set(uid, arg, body, qs):
    b = _b()
    kind = body.get("kind")
    if kind not in ("j", "p"):
        raise WebErr("نوع بسته نامعتبر است.")
    packs = [dict(p) for p in b._packs(kind)]
    qf = "tokens" if kind == "j" else "hours"
    op = body.get("op")
    if op == "del":
        if len(packs) <= 1:
            raise WebErr("حداقل یک بسته باید بماند.")
        packs = [p for p in packs if p["id"] != body.get("id")]
    else:
        amount = _num(body.get("amount"), 1, integer=(kind == "j"), name="مقدار بسته")
        price = _num(body.get("price"), 1, integer=True, name="قیمت")
        if op == "add":
            pid = ("jt" if kind == "j" else "sp") + re.sub(r"\W", "", str(amount)) + "_" + str(int(time.time()) % 100000)
            packs.append({"id": pid, qf: amount, "price": price})
        elif op == "edit":
            for p in packs:
                if p["id"] == body.get("id"):
                    p[qf], p["price"] = amount, price
        else:
            raise WebErr("عملیات نامعتبر.")
    packs.sort(key=lambda p: p[qf])
    b._save_packs(kind, packs)
    return {"ok": True}


# ============ مالی ============
@api("GET", "finance")
def finance_get(uid, arg, body, qs):
    b = _b()
    bs = b.bonus_state()
    mer = b.get_setting("zarin_merchant") or ""
    tiers = b.sjson("disc_tiers", [])
    now = time.time()
    return {
        "pay": {m: {"label": b.METHOD_LABELS[m], "on": _flag("pay_" + m, "1" if m == "card" else "0")} for m in b.METHOD_LABELS},
        "card": b.CARD_NUMBER, "holder": b.CARD_HOLDER,
        "zarin": {"merchant": (mer[:6] + "…") if mer else "", "site": b.site_url() or "", "sandbox": _flag("zarin_sandbox")},
        "crypto": {"wallet": b.get_setting("crypto_wallet") or "", "net": b.get_setting("crypto_net", "USDT"), "rate": W._num(b.crypto_rate())},
        "unit_price": W._num(b.unit_price()),
        "bonus": {"on": bs["on"], "active": bs["active"], "per": W._num(bs["per"]), "amount": W._num(bs["amount"]), "hours": W._num(bs["hours"])},
        "tiers": [{"min": t["min"], "pct": t["pct"], "until": t.get("until") or 0, "left": max(int(t["until"] - now), 0) if t.get("until") else 0} for t in tiers],
        "codes": [{"code": r[0], "user": r[1], "kind": r[2], "value": W._num(r[3]), "used": bool(r[4]), "exp": str(r[5] or "")[:16]} for r in
                  W._q("SELECT code, user_id, kind, value, used, expires_at FROM discount_codes ORDER BY created_at DESC LIMIT 30")]
    }


@api("POST", "finance")
def finance_set(uid, arg, body, qs):
    b = _b()
    op = body.get("op")
    val = body.get("value")
    sv = str(val if val is not None else "").strip().translate(b._ASCII_DIGITS)
    if op == "paytoggle":
        m = body.get("method")
        if m not in b.METHOD_LABELS:
            raise WebErr("روش نامعتبر.")
        k = "pay_" + m
        if not _flag(k, "1" if m == "card" else "0"):
            if m == "zarin" and (not b.get_setting("zarin_merchant") or not b.site_url()):
                raise WebErr("ابتدا «مرچنت زرین‌پال» و «آدرس سایت» را وارد کن.")
            if m == "crypto" and (not b.get_setting("crypto_wallet") or b.crypto_rate() <= 0):
                raise WebErr("ابتدا «آدرس کیف پول» و «نرخ هر واحد» را وارد کن.")
        _tog(k, "1" if m == "card" else "0")
    elif op == "sandbox":
        _tog("zarin_sandbox")
    elif op == "card":
        d = sv.replace("-", "").replace(" ", "")
        if not d.isdigit() or len(d) != 16:
            raise WebErr("شماره کارت باید ۱۶ رقم باشد.")
        b.set_setting("cfg_card", "-".join(d[i:i + 4] for i in range(0, 16, 4)))
        b.apply_settings()
    elif op == "holder":
        if not 2 <= len(str(val).strip()) <= 60:
            raise WebErr("نام باید ۲ تا ۶۰ نویسه باشد.")
        b.set_setting("cfg_holder", str(val).strip())
        b.apply_settings()
    elif op == "zp_merchant":
        if not re.fullmatch(r"[0-9a-fA-F-]{30,40}", sv):
            raise WebErr("مرچنت‌کد زرین‌پال ۳۶ نویسه است.")
        b.set_setting("zarin_merchant", sv)
    elif op == "site_url":
        if not re.match(r"^https://[^\s/]+\S*$", sv):
            raise WebErr("آدرس باید با https:// شروع شود.")
        b.set_setting("site_url", sv.rstrip("/"))
    elif op == "crypto_wallet":
        if not 10 <= len(sv) <= 120 or " " in sv:
            raise WebErr("آدرس کیف پول نامعتبر است.")
        b.set_setting("crypto_wallet", sv)
    elif op == "crypto_net":
        if not 2 <= len(str(val).strip()) <= 30:
            raise WebErr("نام ارز/شبکه باید ۲ تا ۳۰ نویسه باشد.")
        b.set_setting("crypto_net", str(val).strip())
    elif op == "crypto_rate":
        b.set_setting("crypto_rate", _num(sv, 1, name="نرخ"))
    elif op == "unit_price":
        b.set_setting("unit_price", _num(sv, 0, name="قیمت هر شاهی"))
    elif op == "bonus_toggle":
        new = _tog("bonus_on")
        if new:
            b.set_setting("bonus_start", time.time())
    elif op in ("bonus_per", "bonus_amount", "bonus_hours"):
        n = _num(sv, 0 if op == "bonus_hours" else 0.01, name="مقدار")
        b.set_setting(op, n)
        if op == "bonus_hours" and _flag("bonus_on"):
            b.set_setting("bonus_start", time.time())
    elif op == "disc_add":
        mn = _num(body.get("min"), 1, integer=True, name="حداقل خرید")
        pct = _num(body.get("pct"), 1, 99, name="درصد")
        hrs = _num(body.get("hours") or 0, 0, name="ساعت")
        tiers = b.sjson("disc_tiers", [])
        tiers.append({"min": mn, "pct": pct, "until": (time.time() + hrs * 3600) if hrs > 0 else 0})
        b.set_setting("disc_tiers", json.dumps(tiers))
    elif op == "disc_del":
        tiers = b.sjson("disc_tiers", [])
        i = int(body.get("index", -1))
        if 0 <= i < len(tiers):
            tiers.pop(i)
            b.set_setting("disc_tiers", json.dumps(tiers))
    else:
        raise WebErr("عملیات ناشناخته.")
    return {"ok": True}


@api("POST", "dcode")
def dcode_create(uid, arg, body, qs):
    b = _b()
    target = int(str(body.get("user")).translate(b._ASCII_DIGITS))
    if not W._q("SELECT 1 FROM users WHERE id=?", (target,)):
        raise WebErr("کاربر پیدا نشد.", 404)
    kind = body.get("kind")
    if kind not in ("pct", "amount"):
        raise WebErr("نوع کد نامعتبر است.")
    val = _num(body.get("value"), 1, 99 if kind == "pct" else None, name="مقدار")
    hrs = _num(body.get("hours") or 0, 0, name="ساعت")
    code = b.dc_new_code()
    exp = b._utcnow_str(datetime.now(timezone.utc) + timedelta(hours=hrs)) if hrs > 0 else None
    with b.get_db() as c:
        c.execute("INSERT INTO discount_codes (code, user_id, kind, value, expires_at) VALUES (?,?,?,?,?)", (code, target, kind, val, exp))
    desc = f"{b._n(val)}٪" if kind == "pct" else f"{b._n(val)} تومان"
    b.send(target, f"🎁 *یک کد تخفیف اختصاصی برای شما ساخته شد!*\n\n🏷 *کد: `{code}`*\n💸 *مقدار: {b.fa_digits(desc.replace('٪', ' درصد'))}*\n\n"
                   "ℹ️ *هنگام خرید شاهی یا اسپانسری روی «دارم کد تخفیف» بزنید و این کد را بفرستید.*")
    return {"ok": True, "code": code}


@api("POST", "masscharge")
def mass_charge(uid, arg, body, qs):
    b = _b()
    mode = body.get("mode")
    amt = _num(body.get("amount"), 0.01, name="مقدار")
    if mode not in ("add", "sub") or not body.get("confirm"):
        raise WebErr("تأیید لازم است.")
    with b.get_db() as c:
        cur = c.execute("UPDATE users SET tokens = tokens + ?" if mode == "add" else "UPDATE users SET tokens = tokens - ?", (amt,))
    try:
        b.rep_ev_mass(uid, mode, amt, cur.rowcount)
    except Exception:
        traceback.print_exc()
    return {"ok": True, "users": cur.rowcount}


# ============ تنظیمات عمومی: بخش‌ها، جوین اجباری، پشتیبانی، کرون، صدا ============
@api("GET", "general")
def general_get(uid, arg, body, qs):
    b = _b()
    off = b.sections_off()
    fj = b.sjson("fj_list", [])
    return {
        "bot_on": b.get_setting("bot_enabled", "1") != "0",
        "sections": [{"k": k, "name": n, "on": k not in off} for k, n, _ in b.SECTIONS],
        "fj": {"on": _flag("fj_enabled"), "list": [{"i": i, "ref": e["ref"], "title": e.get("title") or e["ref"], "link": e.get("link", "")} for i, e in enumerate(fj)],
               "auto": [{"ref": e["ref"], "title": b.fj_info(e)["title"]} for e in b.fj_entries() if e.get("sponsor")]},
        "support_id": b.SUPPORT_ID, "support_text": b.get_setting("cfg_support_text") or "", "rules": b.get_setting("cfg_rules") or "",
        "cron": W._num(b.cron_sec()),
        "voice": {"on": _flag("vc_on", "1"), "mode": b.get_setting("vc_mode", "hide"), "fb": _flag("vc_fb", "1")},
        "phone_gate": _flag("phone_gate"),
    }


@api("POST", "general")
def general_set(uid, arg, body, qs):
    b = _b()
    op = body.get("op")
    val = body.get("value")
    sv = str(val if val is not None else "").strip()
    if op == "section":
        off = b.sections_off()
        off.symmetric_difference_update({body.get("key")})
        b.set_setting("sec_off", json.dumps(sorted(off)))
    elif op == "fj_toggle":
        _tog("fj_enabled")
    elif op == "fj_add":
        t = sv.translate(b._ASCII_DIGITS)
        ref = t if re.fullmatch(r"-?\d{6,}", t) else None
        if not ref:
            m = re.fullmatch(r"(?:https?://)?(?:t\.me/)?@?([A-Za-z][A-Za-z0-9_]{3,31})", t)
            ref = "@" + m.group(1) if m else None
        if not ref:
            raise WebErr("آیدی نامعتبر است؛ مثل @mychannel یا آیدی عددی (-100…).")
        if not ref.startswith("@") and not ref.startswith("-"):
            ref = "-100" + ref
        info = b.tg("getChat", chat_id=ref, _timeout=10)
        if not info.get("ok"):
            raise WebErr("ربات به این کانال/گروه دسترسی ندارد؛ ابتدا ربات را ادمین کن.")
        title = (info.get("result") or {}).get("title") or ref
        link = str(body.get("link") or "").strip()
        if ref.startswith("@"):
            link = f"https://t.me/{ref[1:]}"
        elif not re.match(r"^https://t\.me/\S+$", link):
            raise WebErr("برای کانال/گروه خصوصی لینک دعوت (https://t.me/+…) لازم است.")
        lst = b.sjson("fj_list", [])
        lst.append({"ref": ref, "title": title, "link": link})
        b.set_setting("fj_list", json.dumps(lst, ensure_ascii=False))
    elif op == "fj_del":
        lst = b.sjson("fj_list", [])
        i = int(body.get("index", -1))
        if 0 <= i < len(lst):
            lst.pop(i)
            b.set_setting("fj_list", json.dumps(lst, ensure_ascii=False))
    elif op == "support_id":
        if not re.fullmatch(r"@[A-Za-z][A-Za-z0-9_]{3,31}", sv):
            raise WebErr("آیدی پشتیبانی مثل @support باشد.")
        b.set_setting("cfg_support", sv)
        b.apply_settings()
    elif op == "support_text":
        if not 3 <= len(sv) <= 3500:
            raise WebErr("متن باید ۳ تا ۳۵۰۰ نویسه باشد.")
        b.set_setting("cfg_support_text", sv)
    elif op == "rules":
        if not 3 <= len(sv) <= 3500:
            raise WebErr("متن باید ۳ تا ۳۵۰۰ نویسه باشد.")
        b.set_setting("cfg_rules", sv)
    elif op == "cron":
        v = float(_num(sv, 0.05, 86400, name="فاصله (ثانیه)"))
        b.set_setting("cron_sec", v)
    elif op == "vc_toggle":
        _tog("vc_on", "1")
    elif op == "vc_fb":
        _tog("vc_fb", "1")
    elif op == "vc_mode":
        b.set_setting("vc_mode", "public" if sv == "public" else "hide")
    elif op == "vc_reset":
        try:
            b.VOICE.reset_levels()
        except Exception:
            pass
    else:
        raise WebErr("عملیات ناشناخته.")
    return {"ok": True}


# ============ کانال‌های مسدود از درخواست JFJ ============
@api("GET", "blocked")
def blocked_list(uid, arg, body, qs):
    return {"keys": sorted(_b()._block_keys())}


@api("POST", "blocked")
def blocked_set(uid, arg, body, qs):
    b = _b()
    if body.get("op") == "del":
        b.unblock_chan(body.get("key"))
        return {"ok": True}
    t = str(body.get("value", "")).strip().translate(b._ASCII_DIGITS)
    if re.fullmatch(r"-?\d{6,}", t):
        keys = [f"id:{t}"]
    else:
        m = re.fullmatch(r"(?:https?://)?(?:t\.me/)?@?([A-Za-z][A-Za-z0-9_]{3,31})", t)
        if not m:
            raise WebErr("آیدی نامعتبر است؛ مثل @mychannel یا آیدی عددی.")
        keys = ["@" + m.group(1)]
        g = b.tg("getChat", chat_id="@" + m.group(1), _timeout=10)
        if g.get("ok"):
            keys.append(f"id:{g['result']['id']}")
    b.block_chan(keys)
    return {"ok": True}


# ============ حذف درخواست با/بدون بازگشت هزینه ============
@api("POST", "reqdel")
def req_delete(uid, code, body, qs):
    ok = _b().delete_request_admin(code, bool(body.get("refund")), uid)
    if not ok:
        raise WebErr("درخواست قابل حذف نیست.")
    return {"ok": True}


# ============ اسپانسری ============
@api("GET", "sponsors")
def sponsors_list(uid, arg, body, qs):
    b = _b()
    rows = W._q("SELECT id, user_id, invoice_code, hours, status, started_at, ends_at, chat_ref FROM sponsor_subs ORDER BY id DESC LIMIT 60")
    return {"subs": [{"id": r[0], "user": r[1], "inv": r[2] or "", "hours": W._num(r[3]), "status": b.sub_state(r[4], r[6]), "start": str(r[5] or "")[:16], "end": str(r[6] or "")[:16], "ref": r[7] or ""} for r in rows]}


@api("POST", "sponsor")
def sponsor_op(uid, arg, body, qs):
    b = _b()
    op = body.get("op")
    if op == "new":
        target = int(str(body.get("user")).translate(b._ASCII_DIGITS))
        if not W._q("SELECT 1 FROM users WHERE id=?", (target,)):
            raise WebErr("کاربر پیدا نشد.", 404)
        hours = _num(body.get("hours"), 0.01, name="ساعت")
        ref = str(body.get("ref") or "").strip().translate(b._ASCII_DIGITS)
        if ref in ("", "-"):
            ref = None
        else:
            m = re.fullmatch(r"(?:https?://)?(?:t\.me/)?@?([A-Za-z][A-Za-z0-9_]{3,31})", ref)
            ref = ("@" + m.group(1)) if m else (ref if re.fullmatch(r"-\d{6,}", ref) else None)
            if not ref:
                raise WebErr("آیدی کانال نامعتبر است.")
        with b.get_db() as c:
            c.execute("INSERT INTO sponsor_subs (user_id, hours, status, chat_kind, chat_ref) VALUES (?,?,?,?,?)",
                      (target, hours, "pending", "public" if (ref or "").startswith("@") else "private", ref))
            sid = c.execute("SELECT MAX(id) FROM sponsor_subs").fetchone()[0]
        b.sponsor_activate(sid)
        return {"ok": True, "id": sid}
    sid = int(body.get("id"))
    if op in ("add", "sub"):
        h = _num(body.get("hours"), 0.01, name="ساعت")
        b.sponsor_shift(sid, h if op == "add" else -h)
    elif op == "cancel":
        with b.get_db() as c:
            c.execute("UPDATE sponsor_subs SET status='cancelled' WHERE id=?", (sid,))
    elif op == "activate":
        b.sponsor_activate(sid)
    else:
        raise WebErr("عملیات ناشناخته.")
    return {"ok": True}


# ============ بازی‌های گروهی ============
def _games():
    g = getattr(_b(), "GAMES", None)
    if g is None:
        raise WebErr("بخش بازی‌ها فعال نیست.", 503)
    return g


@api("GET", "games")
def games_get(uid, arg, body, qs):
    g = _games()
    b = _b()
    cfg = []
    for name, label, unit, kind, lo, hi, ico in g._ACFG_BY.values():
        cur = g.cv(name)
        dflt = float(getattr(g, g._CFGK[name][1]))
        cfg.append({"name": name, "label": label, "unit": unit, "kind": kind, "lo": lo, "hi": hi, "value": W._num(cur), "default": W._num(dflt), "mon": name in getattr(g, "_MCFG_BY", {})})
    return {"games": [{"k": k, "name": n, "on": b.game_setting_on(k)} for k, n in b.GAME_KEYS], "cfg": cfg}


@api("POST", "games")
def games_set(uid, arg, body, qs):
    g = _games()
    b = _b()
    op = body.get("op")
    if op == "toggle":
        k = body.get("key")
        if k not in dict(b.GAME_KEYS):
            raise WebErr("بازی ناشناخته.")
        b.set_setting(f"g_{k}_on", "0" if b.game_setting_on(k) else "1")
    elif op == "cfg":
        name = body.get("name")
        row = g._ACFG_BY.get(name)
        if not row:
            raise WebErr("تنظیم ناشناخته.")
        _n, _l, _u, kind, lo, hi, _i = row
        v = _num(body.get("value"), lo, hi, integer=(kind == "int"), name=_l)
        b.set_setting(g._CFGK[name][0], str(int(v) if kind == "int" else v))
    elif op == "reset":
        for name in g._CFGK:
            b.set_setting(g._CFGK[name][0], "")
    else:
        raise WebErr("عملیات ناشناخته.")
    return {"ok": True}


# ============ گزارشات ============
@api("GET", "reports")
def reports_get(uid, arg, body, qs):
    b = _b()
    cid, topics = b.rep_conf()
    off = b.rep_off()
    return {"chat": cid, "ready": bool(b.rep_ready()),
            "topics": [{"k": k, "name": n, "desc": d, "on": k not in off, "has_topic": str(k) in topics or k in topics} for k, n, d in b.REPORT_TOPICS]}


@api("POST", "reports")
def reports_set(uid, arg, body, qs):
    b = _b()
    k = body.get("key")
    if k not in {t[0] for t in b.REPORT_TOPICS}:
        raise WebErr("تاپیک ناشناخته.")
    b.rep_set_off(k, off=bool(body.get("off")))
    return {"ok": True}


# ============ کاربر: کارت‌به‌کارت و آمار بیشتر ============
@api("POST", "usercard")
def user_cardblock(uid, target, body, qs):
    b = _b()
    t = int(target)
    with b.get_db() as c:
        c.execute("UPDATE users SET card_blocked = 1 - card_blocked WHERE id=?", (t,))
    return {"ok": True, "card_blocked": bool(W._q1("SELECT card_blocked FROM users WHERE id=?", (t,)))}


@api("GET", "userorders")
def user_orders(uid, target, body, qs):
    t = int(target)
    rq = W._q("SELECT tracking_code, member_count, status, link, created_at FROM requests WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (t,))
    so = W._q("SELECT tracking_code, service, quantity, status, created_at FROM service_orders WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (t,))
    return {"requests": [{"code": r[0], "n": r[1], "status": r[2], "link": r[3] or "", "created": str(r[4])[:16]} for r in rq],
            "orders": [{"code": r[0], "service": r[1], "qty": W._num(r[2]), "status": r[3], "created": str(r[4])[:16]} for r in so]}
