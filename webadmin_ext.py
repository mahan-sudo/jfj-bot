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
        where, args = "WHERE o.status=?", (st,)
    rows = W._q("SELECT o.tracking_code, o.user_id, o.service, o.quantity, o.extra, o.token_cost, o.status, o.created_at, o.link, u.first_name, u.username "
                f"FROM service_orders o LEFT JOIN users u ON u.id=o.user_id {where} ORDER BY o.created_at {'ASC' if st == 'pending' else 'DESC'} LIMIT 60", args)
    cnt = {r[0]: r[1] for r in W._q("SELECT status, COUNT(*) FROM service_orders GROUP BY status")}
    return {"counts": cnt,
            "orders": [{"code": r[0], "user": r[1], "service": r[2], "qty": W._num(r[3]), "extra": r[4] or "", "cost": W._num(r[5]), "status": r[6],
                        "created": str(r[7])[:16], "link": r[8] or "", "name": r[9] or "", "username": r[10] or ""} for r in rows]}


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
    note = str(body.get("note") or "").strip()[:500]
    if ok:
        b.send(user_id, f"✅ *سفارش {service} شما به کد پیگیری {code} تکمیل شد.*\n{b.stamp('زمان تکمیل')}")
    else:
        b.send(user_id, f"❌ *سفارش {service} شما به کد پیگیری {code} لغو شد.*\n{b.stamp('زمان لغو')}\n\n🪙 *{b.fmt_tokens(cost)} شاهی به حساب شما برگشت.*")
    if note:
        b.send(user_id, "📝 *توضیح پشتیبانی:*\n" + note, markdown=False)
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
    only = (qs.get("user") or [""])[0]
    where, args = ("WHERE user_id=?", (int(only),)) if only.isdigit() else ("", ())
    rows = W._q(f"SELECT id, user_id, invoice_code, hours, status, started_at, ends_at, chat_ref FROM sponsor_subs {where} ORDER BY id DESC LIMIT 60", args)
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


# ============ تکمیل‌ها: کاربر، زیرمجموعه، احراز شماره، هیولا، همگانی کانال‌ها ============
@api("GET", "userx")
def userx_get(uid, target, body, qs):
    b = _b()
    t = int(target)
    row = W._q("SELECT phone, phone_req, card_blocked, referred_by FROM users WHERE id=?", (t,))
    if not row:
        raise WebErr("کاربر پیدا نشد.", 404)
    phone, preq, cblk, ref = row[0]
    own = {r[0] for r in W._q("SELECT key FROM user_products WHERE user_id=?", (t,))}
    return {"phone": phone or "", "phone_req": bool(preq), "card_blocked": bool(cblk), "referred_by": ref,
            "subs_count": W._q1("SELECT COUNT(*) FROM users WHERE referred_by=?", (t,)),
            "products": [{"key": k, "title": d.get("title") or k, "on": k in own} for k, d in b.PRODUCT_DEFS.items()]}


@api("POST", "userx")
def userx_set(uid, target, body, qs):
    b = _b()
    t = int(target)
    if not W._q("SELECT 1 FROM users WHERE id=?", (t,)):
        raise WebErr("کاربر پیدا نشد.", 404)
    op = body.get("op")
    if op == "zero":
        with b.get_db() as c:
            c.execute("UPDATE users SET tokens=0 WHERE id=?", (t,))
    elif op == "phone":
        phone, req = b.user_phone(t)
        with b.get_db() as c:
            if req:
                c.execute("UPDATE users SET phone_req=0 WHERE id=?", (t,))
            else:
                c.execute("UPDATE users SET phone_req=1, phone=NULL WHERE id=?", (t,))
    elif op == "refreset":
        with b.get_db() as c:
            c.execute("UPDATE users SET referred_by=NULL WHERE referred_by=?", (t,))
    elif op == "product":
        key = body.get("key")
        if key not in b.PRODUCT_DEFS:
            raise WebErr("محصول ناشناخته.")
        with b.get_db() as c:
            if b.user_has_product(t, key):
                c.execute("DELETE FROM user_products WHERE user_id=? AND key=?", (t, key))
            else:
                c.execute("INSERT INTO user_products (user_id, key) VALUES (?,?) ON CONFLICT DO NOTHING", (t, key))
                b.send(t, f"🎁 *محصول «{b.PRODUCT_DEFS[key]['title']}» برای شما فعال شد.*")
    else:
        raise WebErr("عملیات ناشناخته.")
    return {"ok": True}


@api("GET", "referral")
def referral_get(uid, arg, body, qs):
    b = _b()
    rows = W._q("SELECT referred_by, COUNT(*), COALESCE(SUM(referral_rewarded),0) FROM users WHERE referred_by IS NOT NULL GROUP BY referred_by ORDER BY COUNT(*) DESC LIMIT 15")
    return {"act_on": b.ref_act_on(), "reward": W._num(b._cfg_value("rr")), "threshold": W._num(b._cfg_value("rt")),
            "top": [{"user": r[0], "n": r[1], "rewarded": W._num(r[2])} for r in rows]}


@api("POST", "referral")
def referral_set(uid, arg, body, qs):
    b = _b()
    if body.get("op") == "act_toggle":
        b.set_setting("ref_act_on", "0" if b.ref_act_on() else "1")
        return {"ok": True}
    raise WebErr("عملیات ناشناخته.")


@api("POST", "generalx")
def generalx_set(uid, arg, body, qs):
    b = _b()
    op = body.get("op")
    if op == "phone_verify":
        _tog("phone_verify")
    elif op == "rules_reset":
        with b.get_db() as c:
            c.execute("DELETE FROM settings WHERE key='rules_text'")
    elif op == "support_reset":
        with b.get_db() as c:
            c.execute("DELETE FROM settings WHERE key='support_text'")
    else:
        raise WebErr("عملیات ناشناخته.")
    return {"ok": True}


@api("GET", "generalx")
def generalx_get(uid, arg, body, qs):
    b = _b()
    return {"phone_verify": _flag("phone_verify"), "channels": len(b.admin_channels(force=True)),
            "invalid_minutes": W._num(b._cfg_value("inv"))}


@api("GET", "monster")
def monster_get(uid, arg, body, qs):
    g = _games()
    rows = []
    for name, label, unit, kind, lo, hi, ico in g._MCFG:
        rows.append({"name": name, "label": label, "unit": unit, "lo": lo, "hi": hi, "value": W._num(g.cv(name)), "default": W._num(float(getattr(g, g._CFGK[name][1])))})
    return {"auto_on": bool(g.mon_auto_on()), "cfg": rows}


@api("POST", "monster")
def monster_set(uid, arg, body, qs):
    g = _games()
    b = _b()
    op = body.get("op")
    if op == "toggle":
        now_on = not g.mon_auto_on()
        b.set_setting("g_m_on", "1" if now_on else "0")
        try:
            g._AG[0] = 0.0
        except Exception:
            pass
    elif op == "reset":
        for name in g._MCFG_BY:
            b.set_setting(g._CFGK[name][0], "")
    else:
        raise WebErr("عملیات ناشناخته.")
    return {"ok": True}


@api("GET", "betraycheck")
def betraycheck_get(uid, target, body, qs):
    return _b().betrayal_stats(int(target))


@api("POST", "betraycheck")
def betraycheck_post(uid, target, body, qs):
    b = _b()
    t = int(target)
    if not W._q("SELECT 1 FROM users WHERE id=?", (t,)):
        raise WebErr("کاربر پیدا نشد.", 404)
    if t in b.ADMIN_IDS:
        raise WebErr("ادمین قابل ثبت به‌عنوان خائن نیست.")
    new = b.betrayal_flag(t)
    return {"ok": True, "new": bool(new)}


# ============ اطلاعات کامل کاربر ============
def _lab(first, username):
    return (first or "").strip() or ("@" + username if username else "")


@api("GET", "userfull")
def userfull(uid, target, body, qs):
    b = _b()
    t = int(target)
    r = W._q("SELECT first_name, username, tokens, referred_by, created_at, banned, card_blocked, phone, phone_req, updated_at, "
             "referral_rewarded, activity_tokens, vip FROM users WHERE id=?", (t,))
    if not r:
        raise WebErr("کاربر پیدا نشد.", 404)
    f = r[0]
    q1 = W._q1
    act_ph = ",".join("?" * len(W._REQ_DONE))
    ref = None
    if f[3]:
        rr = W._q("SELECT first_name, username FROM users WHERE id=?", (f[3],))
        ref = {"id": f[3], "name": _lab(*rr[0]) if rr else ""}
    now = b._utcnow_str()
    return {
        "id": t, "name": f[0] or "", "username": f[1] or "", "tokens": W._num(f[2]), "referred_by": ref, "created": str(f[4] or "")[:16],
        "banned": bool(f[5]), "card_blocked": bool(f[6]), "phone": f[7] or "", "phone_req": bool(f[8]), "seen": str(f[9] or "")[:16],
        "ref_rewarded": W._num(f[10]), "activity": W._num(f[11]), "vip": bool(f[12]), "is_admin": t in b.ADMIN_IDS,
        "req_total": q1("SELECT COUNT(*) FROM requests WHERE user_id=?", (t,)),
        "req_active": q1(f"SELECT COUNT(*) FROM requests WHERE user_id=? AND status NOT IN ({act_ph})", (t, *W._REQ_DONE)),
        "joins_active": q1("SELECT COUNT(*) FROM joins WHERE user_id=? AND left_at IS NULL", (t,)),
        "joins_left": q1("SELECT COUNT(*) FROM joins WHERE user_id=? AND left_at IS NOT NULL", (t,)),
        "svc_total": q1("SELECT COUNT(*) FROM service_orders WHERE user_id=?", (t,)),
        "spent": W._num(q1("SELECT COALESCE(SUM(final_amount),0) FROM invoices WHERE buyer_id=? AND status='paid'", (t,))),
        "paid_n": q1("SELECT COUNT(*) FROM invoices WHERE buyer_id=? AND status='paid'", (t,)),
        "sponsor_active": q1("SELECT COUNT(*) FROM sponsor_subs WHERE user_id=? AND status='active' AND ends_at > ?", (t, now)),
        "subs_count": q1("SELECT COUNT(*) FROM users WHERE referred_by=?", (t,)),
        "subs": [{"id": x[0], "name": _lab(x[1], x[2]), "created": str(x[3])[:16], "rewarded": bool(x[4])} for x in
                 W._q("SELECT id, first_name, username, created_at, referral_rewarded FROM users WHERE referred_by=? ORDER BY created_at DESC LIMIT 15", (t,))],
        "requests": [{"code": x[0], "n": x[1], "status": x[2], "link": x[3] or "", "created": str(x[4])[:16], "done": x[5]} for x in
                     W._q("SELECT r.tracking_code, r.member_count, r.status, r.link, r.created_at, "
                          "(SELECT COUNT(*) FROM joins j WHERE j.tracking_code=r.tracking_code AND j.left_at IS NULL) "
                          "FROM requests r WHERE r.user_id=? ORDER BY r.created_at DESC LIMIT 15", (t,))],
        "joins": [{"code": x[0], "link": x[1] or "", "joined": str(x[2])[:16], "left": str(x[3] or "")[:16]} for x in
                  W._q("SELECT j.tracking_code, r.link, j.joined_at, j.left_at FROM joins j LEFT JOIN requests r ON r.tracking_code=j.tracking_code "
                       "WHERE j.user_id=? ORDER BY j.joined_at DESC LIMIT 15", (t,))],
        "orders": [{"code": x[0], "service": x[1], "qty": W._num(x[2]), "extra": x[3] or "", "cost": W._num(x[4]), "status": x[5], "link": x[6] or "", "created": str(x[7])[:16]} for x in
                   W._q("SELECT tracking_code, service, quantity, extra, token_cost, status, link, created_at FROM service_orders WHERE user_id=? ORDER BY created_at DESC LIMIT 15", (t,))],
        "invoices": [{"code": x[0], "product": x[1], "amount": W._num(x[2]), "status": x[3], "method": x[4] or "", "created": str(x[5])[:16]} for x in
                     W._q("SELECT code, product_name, final_amount, status, method, created_at FROM invoices WHERE buyer_id=? ORDER BY created_at DESC LIMIT 15", (t,))],
        "betray": b.betrayal_stats(t),
    }


# ============ جزئیات درخواست JFJ ============
@api("GET", "reqinfo")
def reqinfo(uid, code, body, qs):
    b = _b()
    r = W._q("SELECT r.tracking_code, r.user_id, r.member_count, r.initial_member_count, r.token_cost, r.link, r.chat_id, r.status, r.created_at, "
             "r.last_requested_at, u.first_name, u.username FROM requests r LEFT JOIN users u ON u.id=r.user_id WHERE r.tracking_code=?", (code,))
    if not r:
        raise WebErr("درخواست پیدا نشد.", 404)
    x = r[0]
    q1 = W._q1
    joiners = W._q("SELECT j.user_id, u.first_name, u.username, j.joined_at, j.left_at FROM joins j LEFT JOIN users u ON u.id=j.user_id "
                   "WHERE j.tracking_code=? ORDER BY j.joined_at DESC LIMIT 100", (code,))
    out = {"code": x[0], "user": x[1], "count": x[2], "initial": x[3], "cost": W._num(x[4]), "link": x[5] or "", "chat_id": x[6], "status": x[7],
           "created": str(x[8])[:16], "last": str(x[9] or "")[:16], "name": x[10] or "", "username": x[11] or "",
           "done": q1("SELECT COUNT(*) FROM joins WHERE tracking_code=? AND left_at IS NULL", (code,)),
           "left": q1("SELECT COUNT(*) FROM joins WHERE tracking_code=? AND left_at IS NOT NULL", (code,)),
           "owner_requests": q1("SELECT COUNT(*) FROM requests WHERE user_id=?", (x[1],)),
           "betrayer": bool(q1("SELECT COUNT(*) FROM betrayers WHERE user_id=?", (x[1],))),
           "blocked": (b.chan_key(x[6], x[5]) in b._block_keys()) if hasattr(b, "chan_key") else False,
           "joiners": [{"id": j[0], "name": _lab(j[1], j[2]), "username": j[2] or "", "joined": str(j[3])[:16], "left": str(j[4] or "")[:16]} for j in joiners],
           "live": None}
    if (qs.get("live") or [""])[0] == "1":
        try:
            ident = b.resolve_chat_ident(x[6], x[5])
            rs = b.tg("getChatMemberCount", chat_id=ident, _timeout=8) if ident else {}
            out["live"] = rs.get("result") if rs.get("ok") else None
        except Exception:
            out["live"] = None
    return out


@api("POST", "reqblock")
def reqblock(uid, code, body, qs):
    b = _b()
    r = W._q("SELECT chat_id, link FROM requests WHERE tracking_code=?", (code,))
    if not r:
        raise WebErr("درخواست پیدا نشد.", 404)
    key = b.chan_key(r[0][0], r[0][1])
    if body.get("block"):
        b.block_chan([key])
    else:
        b.unblock_chan(key)
    return {"ok": True}


# ============ بارگذاری رسانه برای پیام همگانی ============
_KIND_FIELD = {"photo": ("sendPhoto", "photo", 10), "video": ("sendVideo", "video", 48), "animation": ("sendAnimation", "animation", 48),
               "voice": ("sendVoice", "voice", 48), "audio": ("sendAudio", "audio", 48), "document": ("sendDocument", "document", 48),
               "sticker": ("sendSticker", "sticker", 5)}


def upload(uid, environ, qs):
    """فایل خام را می‌گیرد و برای خودِ ادمین در چت ربات می‌فرستد (پیش‌نمایش)؛ message_id برای ارسال همگانی برمی‌گردد."""
    import hashlib
    import os
    import urllib.error
    import urllib.request
    from urllib.parse import unquote
    b = _b()
    kind = (qs.get("kind") or [""])[0]
    if kind not in _KIND_FIELD:
        raise WebErr("نوع رسانه نامعتبر است.")
    method, field, mb = _KIND_FIELD[kind]
    try:
        size = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        size = 0
    if size <= 0:
        raise WebErr("فایلی دریافت نشد.")
    if size > mb * 1024 * 1024:
        raise WebErr(f"حجم فایل برای این نوع بیشتر از {mb} مگابایت است.")
    inp, chunks, got = environ["wsgi.input"], [], 0
    while got < size:
        part = inp.read(min(1 << 20, size - got))
        if not part:
            break
        chunks.append(part)
        got += len(part)
    data = b"".join(chunks)
    if len(data) != size:
        raise WebErr("دریافت فایل ناقص بود؛ دوباره امتحان کن.")
    name = re.sub(r"[^\w.\-]", "_", unquote((qs.get("name") or ["file"])[0]))[:60] or "file"
    caption = unquote((qs.get("caption") or [""])[0])[:1000]
    boundary = "----jfjweb" + hashlib.md5(os.urandom(8)).hexdigest()
    fields = {"chat_id": str(uid)}
    if caption and kind != "sticker":
        fields["caption"] = caption
        fields["parse_mode"] = "HTML"
    body = b""
    for k, v in fields.items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode("utf-8")
    body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{name}"\r\n'
             f'Content-Type: application/octet-stream\r\n\r\n').encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{b.BOT_TOKEN}/{method}", data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            res = json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            res = json.loads(e.read() or b"{}")
        except Exception:
            res = {"ok": False, "description": str(e)}
    except Exception as e:
        res = {"ok": False, "description": str(e)}
    if not res.get("ok"):
        raise WebErr("تلگرام فایل را نپذیرفت: " + str(res.get("description", ""))[:150])
    return {"ok": True, "mid": res["result"]["message_id"], "kind": kind}


@api("POST", "broadcastmedia")
def broadcast_media(uid, arg, body, qs):
    b = _b()
    aud = body.get("aud")
    if aud not in ("all", "active", "new", "chan"):
        raise WebErr("مخاطب نامعتبر است.")
    try:
        mid = int(body.get("mid"))
    except (TypeError, ValueError):
        raise WebErr("ابتدا فایل را بارگذاری کن.")
    jid = b.bc_create(uid, uid, uid, mid, aud, pin=1 if body.get("pin") else 0)
    return {"ok": True, "job": jid, "targets": len(b.bc_targets(aud))}


# ============ گزارش بازی‌ها (همان گزارش ربات) ============
@api("GET", "gamerep")
def gamerep_get(uid, arg, body, qs):
    g = _games()
    b = _b()
    from datetime import timedelta
    d = int((qs.get("days") or ["1"])[0])
    d = d if d in (1, 7, 30) else 1
    midnight = b.now_local().replace(hour=0, minute=0, second=0, microsecond=0)
    start = midnight.timestamp() if d == 1 else (midnight - timedelta(days=d - 1)).timestamp()
    rows = g._rows("SELECT game, kind, stake_total, payout_total, detail FROM g_log WHERE ts>=?", (start,))
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
    names = {"s": "گردونه شانس", "d": "تاس", "x": "دوز", "r": "سنگ کاغذ قیچی", "m": "هیولا"}
    games = [{"k": k, "name": names[k], "n": agg[k][0], "stake": W._num(agg[k][1]), "payout": W._num(agg[k][2]), "profit": W._num(round(agg[k][1] - agg[k][2], 2))}
             for k in names if k in agg]
    ts, tp = sum(x["stake"] for x in games), sum(x["payout"] for x in games)
    tables = g._rows("SELECT * FROM g_tables WHERE state IN ('join','send','play') ORDER BY id DESC LIMIT 20")
    st_fa = {"join": "جذب بازیکن", "send": "مرحله ارسال", "play": "در حال بازی"}
    act = []
    for t in tables:
        ps = g._players(t["id"])
        act.append({"id": t["id"], "game": names.get(t["game"], t["game"]), "state": st_fa.get(t["state"], t["state"]), "owner": t.get("owner_name") or "",
                    "owner_id": t["owner"], "stake": W._num(t["stake"]), "players": len(ps), "max": t["maxp"], "chat": t["chat_id"]})
    ms = g._rows("SELECT id, state FROM g_mon WHERE created>=?", (start,))
    cnt = {}
    for m_ in ms:
        cnt[m_["state"]] = cnt.get(m_["state"], 0) + 1
    hits = g._row("SELECT COUNT(*) n, COALESCE(SUM(hit),0) h, COALESCE(SUM(dmg),0) d, COUNT(DISTINCT user_id) u FROM g_mon_hits WHERE mon_id IN (SELECT id FROM g_mon WHERE created>=?)", (start,))
    fin = g._row("SELECT COALESCE(SUM(stake_total),0) s, COALESCE(SUM(payout_total),0) p FROM g_log WHERE game='m' AND ts>=?", (start,))
    top = g._rows("SELECT h.user_id, MAX(h.name) AS name, COUNT(*) n FROM g_mon m JOIN g_mon_hits h ON h.mon_id=m.id AND h.user_id=m.winner "
                  "WHERE m.state='done' AND m.created>=? GROUP BY h.user_id ORDER BY n DESC LIMIT 5", (start,))
    return {"days": d, "games": games, "total": {"n": sum(x["n"] for x in games), "stake": W._num(ts), "payout": W._num(tp), "profit": W._num(round(ts - tp, 2))},
            "players": len(players), "closed": closed, "active": act,
            "mon": {"sent": len(ms), "done": cnt.get("done", 0), "fail": cnt.get("fail", 0), "idle": cnt.get("idle", 0), "live": cnt.get("live", 0),
                    "hits": hits["n"], "hit_ok": W._num(hits["h"]), "dmg": W._num(hits["d"]), "players": hits["u"],
                    "stake": W._num(fin["s"]), "payout": W._num(fin["p"]), "top": [{"id": x["user_id"], "name": x["name"] or "", "n": x["n"]} for x in top]}}


@api("POST", "gametable")
def gametable(uid, arg, body, qs):
    g = _games()
    if body.get("all"):
        n = sum(1 for t in g._rows("SELECT id FROM g_tables WHERE state IN ('join','send','play')") if g.admin_close_table(t["id"]))
        return {"ok": True, "closed": n}
    return {"ok": bool(g.admin_close_table(int(body.get("id"))))}


# ============ لاگ عملیات، جستجوی سراسری، مدیریت ادمین‌ها ============
@api("GET", "audit")
def audit_get(uid, arg, body, qs):
    W._tables()
    who = (qs.get("admin") or [""])[0]
    where, args = ("WHERE admin_id=?", (int(who),)) if who.isdigit() else ("", ())
    rows = W._q(f"SELECT a.id, a.admin_id, a.action, a.detail, a.ts, u.first_name FROM web_audit a LEFT JOIN users u ON u.id=a.admin_id {where} ORDER BY a.id DESC LIMIT 100", args)
    return {"items": [{"id": r[0], "admin": r[1], "name": r[5] or "", "action": r[2], "detail": r[3] or "", "ts": str(r[4])[:16]} for r in rows]}


@api("GET", "search")
def search(uid, arg, body, qs):
    q = (qs.get("q") or [""])[0].strip().lstrip("@")
    if len(q) < 2:
        return {"users": [], "orders": [], "requests": [], "invoices": []}
    like = "%" + q.lower() + "%"
    num = int(q) if q.isdigit() and len(q) < 16 else None
    users = W._q("SELECT id, first_name, username, tokens FROM users WHERE CAST(id AS TEXT)=? OR LOWER(COALESCE(username,'')) LIKE ? OR LOWER(COALESCE(first_name,'')) LIKE ? "
                 "OR COALESCE(phone,'') LIKE ? ORDER BY created_at DESC LIMIT 8", (q, like, like, "%" + q + "%"))
    o_where, o_args = ("(LOWER(tracking_code) LIKE ? OR LOWER(link) LIKE ?" + (" OR user_id=?)" if num else ")")), (like, like) + ((num,) if num else ())
    orders = W._q(f"SELECT tracking_code, user_id, service, quantity, status FROM service_orders WHERE {o_where} ORDER BY created_at DESC LIMIT 8", o_args)
    r_where, r_args = ("(LOWER(tracking_code) LIKE ? OR LOWER(link) LIKE ?" + (" OR user_id=?)" if num else ")")), (like, like) + ((num,) if num else ())
    reqs = W._q(f"SELECT tracking_code, user_id, link, status FROM requests WHERE {r_where} ORDER BY created_at DESC LIMIT 8", r_args)
    i_where, i_args = ("(LOWER(code) LIKE ?" + (" OR buyer_id=?)" if num else ")")), (like,) + ((num,) if num else ())
    invs = W._q(f"SELECT code, buyer_id, product_name, status FROM invoices WHERE {i_where} ORDER BY created_at DESC LIMIT 8", i_args)
    return {"users": [{"id": r[0], "name": r[1] or "", "username": r[2] or "", "tokens": W._num(r[3])} for r in users],
            "orders": [{"code": r[0], "user": r[1], "service": r[2], "qty": W._num(r[3]), "status": r[4]} for r in orders],
            "requests": [{"code": r[0], "user": r[1], "link": r[2] or "", "status": r[3]} for r in reqs],
            "invoices": [{"code": r[0], "user": r[1], "product": r[2], "status": r[3]} for r in invs]}


@api("GET", "admins")
def admins_get(uid, arg, body, qs):
    b = _b()
    W._tables()
    have = {r[0]: str(r[1] or "")[:16] for r in W._q("SELECT user_id, last_login FROM web_admins")}
    out = []
    for a in b.ADMIN_IDS:
        r = W._q("SELECT first_name, username FROM users WHERE id=?", (a,))
        out.append({"id": a, "name": _lab(*r[0]) if r else "", "has_pw": a in have, "last": have.get(a, ""), "main": a == b.ADMIN_IDS[0], "me": a == uid})
    return {"admins": out, "can_manage": uid == b.ADMIN_IDS[0]}


@api("POST", "admins")
def admins_post(uid, arg, body, qs):
    b = _b()
    try:
        t = int(body.get("id"))
    except (TypeError, ValueError):
        raise WebErr("آیدی نامعتبر است.")
    if t not in b.ADMIN_IDS:
        raise WebErr("این آیدی ادمین ربات نیست.")
    if t != uid and uid != b.ADMIN_IDS[0]:
        raise WebErr("فقط ادمین اصلی می‌تواند رمز دیگران را تغییر دهد.", 403)
    pw = W.set_password(t)
    return {"ok": True, "password": pw}


# ============ اطلاعات تکمیلی داشبورد ============
@api("GET", "dashx")
def dashx(uid, arg, body, qs):
    from datetime import timedelta
    b = _b()
    q1, Q = W._q1, W._q
    mid = b.now_local().replace(hour=0, minute=0, second=0, microsecond=0)
    t0, t1 = b._utc_str(mid), b._utc_str(mid - timedelta(days=1))
    w0, w1 = b._utc_str(mid - timedelta(days=6)), b._utc_str(mid - timedelta(days=13))
    now = b._utcnow_str()
    sales = lambda a, z=None: W._num(q1("SELECT COALESCE(SUM(final_amount),0) FROM invoices WHERE status='paid' AND created_at >= ?" + (" AND created_at < ?" if z else ""), (a, z) if z else (a,)))
    gl = b.GAMES._rows("SELECT game, stake_total, payout_total FROM g_log WHERE ts>=? AND kind NOT IN ('cancel','admin')", (mid.timestamp(),)) if getattr(b, "GAMES", None) else []
    stake = sum(r["stake_total"] or 0 for r in gl)
    pay = sum(r["payout_total"] or 0 for r in gl)
    nm = lambda f, u: _lab(f, u)
    return {
        "today": {"requests": q1("SELECT COUNT(*) FROM requests WHERE created_at >= ?", (t0,)), "orders": q1("SELECT COUNT(*) FROM service_orders WHERE created_at >= ?", (t0,)),
                  "joins": q1("SELECT COUNT(*) FROM joins WHERE joined_at >= ?", (t0,)), "lefts": q1("SELECT COUNT(*) FROM joins WHERE left_at >= ?", (t0,)),
                  "paid": q1("SELECT COUNT(*) FROM invoices WHERE status='paid' AND created_at >= ?", (t0,)),
                  "hands": len(gl), "stake": W._num(stake), "house": W._num(round(stake - pay, 2))},
        "yesterday": {"sales": sales(t1, t0), "users": q1("SELECT COUNT(*) FROM users WHERE created_at >= ? AND created_at < ?", (t1, t0))},
        "week": {"sales": sales(w0), "prev_sales": sales(w1, w0), "users": q1("SELECT COUNT(*) FROM users WHERE created_at >= ?", (w0,)),
                 "prev_users": q1("SELECT COUNT(*) FROM users WHERE created_at >= ? AND created_at < ?", (w1, w0))},
        "totals": {"sponsors": q1("SELECT COUNT(*) FROM sponsor_subs WHERE status='active' AND ends_at > ?", (now,)), "banned": q1("SELECT COUNT(*) FROM users WHERE banned=1"),
                   "neg": q1("SELECT COUNT(*) FROM users WHERE tokens<0"), "joins_active": q1("SELECT COUNT(*) FROM joins WHERE left_at IS NULL"),
                   "orders_all": q1("SELECT COUNT(*) FROM service_orders"), "requests_all": q1("SELECT COUNT(*) FROM requests")},
        "new_users": [{"id": r[0], "name": nm(r[1], r[2]), "created": str(r[3])[:16]} for r in Q("SELECT id, first_name, username, created_at FROM users ORDER BY created_at DESC LIMIT 6")],
        "pend_orders": [{"code": r[0], "user": r[1], "service": r[2], "qty": W._num(r[3]), "extra": r[4] or "", "cost": W._num(r[5]), "status": "pending", "created": str(r[6])[:16], "link": r[7] or "", "name": nm(r[8], r[9]), "username": r[9] or ""}
                        for r in Q("SELECT o.tracking_code, o.user_id, o.service, o.quantity, o.extra, o.token_cost, o.created_at, o.link, u.first_name, u.username FROM service_orders o LEFT JOIN users u ON u.id=o.user_id WHERE o.status='pending' ORDER BY o.created_at LIMIT 5")],
        "review": [{"code": r[0], "user": r[1], "product": r[2], "amount": W._num(r[3]), "created": str(r[4])[:16]}
                   for r in Q("SELECT code, buyer_id, product_name, final_amount, created_at FROM invoices WHERE status='review' ORDER BY created_at LIMIT 5")],
        "requests": [{"code": r[0], "link": r[1] or "", "count": r[2], "done": r[3], "status": r[4]}
                     for r in Q("SELECT r.tracking_code, r.link, r.member_count, (SELECT COUNT(*) FROM joins j WHERE j.tracking_code=r.tracking_code AND j.left_at IS NULL), r.status FROM requests r "
                                "WHERE r.status NOT IN ('completed','cancelled','removed','deleted','relinked') ORDER BY r.created_at DESC LIMIT 5")],
        "rich": [{"id": r[0], "name": nm(r[1], r[2]), "v": W._num(r[3])} for r in Q("SELECT id, first_name, username, tokens FROM users ORDER BY tokens DESC LIMIT 5")],
        "refs": [{"id": r[0], "name": nm(r[1], r[2]), "v": r[3]} for r in Q("SELECT u.id, u.first_name, u.username, COUNT(s.id) c FROM users u JOIN users s ON s.referred_by=u.id GROUP BY u.id, u.first_name, u.username ORDER BY c DESC LIMIT 5")],
        "buyers": [{"id": r[0], "name": nm(r[1], r[2]), "v": W._num(r[3])} for r in Q("SELECT u.id, u.first_name, u.username, SUM(i.final_amount) s FROM invoices i JOIN users u ON u.id=i.buyer_id WHERE i.status='paid' GROUP BY u.id, u.first_name, u.username ORDER BY s DESC LIMIT 5")],
        "audit": [{"action": r[0], "ts": str(r[1])[:16], "name": r[2] or str(r[3])} for r in Q("SELECT a.action, a.ts, u.first_name, a.admin_id FROM web_audit a LEFT JOIN users u ON u.id=a.admin_id ORDER BY a.id DESC LIMIT 6")] if (W._tables() or True) else [],
    }


# ============ ایموجی پرمیوم متن پیام‌ها ============
def _pm():
    b = _b()
    if getattr(b, "MSGEMO", None) is None:
        raise WebErr("ماژول ایموجی پرمیوم پیام‌ها لود نشده است.", 503)
    return b, b.MSGEMO


@api("GET", "premsg")
def premsg_get(uid, arg, body, qs):
    import premium_msg as pmg
    b, pm = _pm()
    mode, rules = pm.settings()
    kind, ts = pm.state()
    raw = b.get_setting("premium_emoji_msg_map", "") or ""
    try:
        ov = json.loads(raw) if raw else {}
    except ValueError:
        ov = {}
    items = []
    for k in sorted(set(pmg.DEFAULT_RULES) | set(ov)):
        items.append({"key": k, "id": rules.get(k, ""), "default": pmg.DEFAULT_RULES.get(k, ""), "custom": k in ov,
                      "disabled": k in ov and ov[k] in ("", None)})
    return {"mode": mode, "state": kind, "state_ts": int(ts), "retry_hours": pmg.RETRY_AFTER // 3600, "items": items,
            "emoji": [{"e": e, "id": i} for e, i in pmg.GLOBAL_EMOJI.items()]}


@api("POST", "premsg")
def premsg_post(uid, act, body, qs):
    import premium_msg as pmg
    b, pm = _pm()
    if act == "mode":
        m = body.get("mode")
        if m not in ("auto", "on", "off"):
            raise WebErr("حالت نامعتبر است.")
        b.set_setting("premium_emoji_msg", m)
        if m != "off":
            b.set_setting("premium_emoji_msg_state", "")
        pm.refresh()
        return {"ok": True}
    if act == "map":
        key = str(body.get("key") or "").strip()
        eid = str(body.get("id") or "").strip()
        if not key or len(key) > 120:
            raise WebErr("اسکلت متن خط را بنویس (حداکثر ۱۲۰ نویسه).")
        if eid and not pmg.valid_id(eid):
            raise WebErr("آیدی ایموجی باید فقط عدد و بین ۱۵ تا ۲۰ رقم باشد.")
        raw = b.get_setting("premium_emoji_msg_map", "") or ""
        try:
            ov = json.loads(raw) if raw else {}
        except ValueError:
            ov = {}
        if body.get("reset"):
            ov.pop(key, None)
        elif eid or key in pmg.DEFAULT_RULES:
            ov[key] = eid
        else:
            raise WebErr("آیدی ایموجی را وارد کن.")
        if len(ov) > 400:
            raise WebErr("تعداد موارد سفارشی زیاد است.")
        b.set_setting("premium_emoji_msg_map", json.dumps(ov, ensure_ascii=False))
        pm.refresh()
        return {"ok": True}
    if act == "test":
        txt = ("💎 <b>شاهی چیه و چه کاربردی داره؟</b>\n"
               "⚠️ <b>نکته مهم:</b>\n"
               "1️⃣ <b>ممبر واقعی: تست</b>\n"
               "✅ <b>وضعیت: تکمیل شده</b>\n"
               "❌ <b>وضعیت: لغو شده</b>\n\n"
               "🧪 اگر به‌جای ایموجی‌های معمولی، ایموجی پرمیوم می‌بینی یعنی فعاله.")
        r = b.tg("sendMessage", chat_id=uid, text=txt, parse_mode="HTML", _notx=True)
        if not r.get("ok"):
            raise WebErr("ارسال پیام تست ناموفق بود: " + str(r.get("description", ""))[:120])
        kind, _ = pm.state()
        return {"ok": True, "state": kind, "active": pm.active()}
    raise WebErr("درخواست نامعتبر است.", 404)


# ============ ایموجی پرمیوم دکمه‌ها ============
def _pe():
    b = _b()
    if getattr(b, "PREMOJI", None) is None:
        raise WebErr("ماژول ایموجی پرمیوم لود نشده است.", 503)
    return b, b.PREMOJI


@api("GET", "premoji")
def premoji_get(uid, arg, body, qs):
    import premium_btn as pb
    b, pm = _pe()
    mode, mp = pm.settings()
    kind, ts = pm.state()
    raw = b.get_setting("premium_emoji_map", "") or ""
    try:
        ov = json.loads(raw) if raw else {}
    except ValueError:
        ov = {}
    keys = sorted(set(pb.DEFAULT_KEYS) | set(ov))
    items = []
    for k in keys:
        cur = mp.get(k)
        items.append({"key": k, "id": cur or "", "default": pb.DEFAULT_KEYS.get(k, ""), "custom": k in ov,
                      "disabled": k in ov and ov[k] in ("", None)})
    return {"mode": mode, "state": kind, "state_ts": int(ts), "retry_hours": pb.RETRY_AFTER // 3600, "items": items,
            "emoji": [{"e": e, "id": i} for e, i in pb.EMOJI_KEYS.items()]}


@api("POST", "premoji")
def premoji_post(uid, act, body, qs):
    import premium_btn as pb
    b, pm = _pe()
    if act == "mode":
        m = body.get("mode")
        if m not in ("auto", "on", "off"):
            raise WebErr("حالت نامعتبر است.")
        b.set_setting("premium_emoji", m)
        if m != "off":
            b.set_setting("premium_emoji_state", "")
        pm.refresh()
        return {"ok": True}
    if act == "map":
        key = str(body.get("key") or "").strip()
        eid = str(body.get("id") or "").strip()
        if not key or len(key) > 60:
            raise WebErr("متن دکمه را بنویس (حداکثر ۶۰ نویسه).")
        key = pb.core(key) or key
        if eid and not pb.valid_id(eid):
            raise WebErr("آیدی ایموجی باید فقط عدد و بین ۱۵ تا ۲۰ رقم باشد.")
        raw = b.get_setting("premium_emoji_map", "") or ""
        try:
            ov = json.loads(raw) if raw else {}
        except ValueError:
            ov = {}
        if body.get("reset"):
            ov.pop(key, None)
        elif eid or key in pb.DEFAULT_KEYS:
            ov[key] = eid          # id خالی روی کلید پیش‌فرض = غیرفعال کردن آن دکمه
        else:
            raise WebErr("آیدی ایموجی را وارد کن.")
        if len(ov) > 300:
            raise WebErr("تعداد موارد سفارشی زیاد است.")
        b.set_setting("premium_emoji_map", json.dumps(ov, ensure_ascii=False))
        pm.refresh()
        return {"ok": True}
    if act == "test":
        mode, mp = pm.settings()
        keys = [k for k in sorted(mp)][:90]
        rows, row = [], []
        for k in keys:
            row.append(b.btn_inline(k, "noop"))
            if len(row) == 3:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        r = b.tg("sendMessage", chat_id=uid, text="🧪 تست ایموجی پرمیوم دکمه‌ها\nاگر کنار دکمه‌ها ایموجی پرمیوم می‌بینی یعنی فعاله.",
                 reply_markup={"inline_keyboard": rows}, _notx=True)
        if not r.get("ok"):
            raise WebErr("ارسال پیام تست ناموفق بود: " + str(r.get("description", ""))[:120])
        kind, _ = pm.state()
        return {"ok": True, "state": kind, "active": pm.active()}
    raise WebErr("درخواست نامعتبر است.", 404)
