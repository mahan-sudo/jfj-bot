"""تست‌های اختصاصی PostgreSQL: CRUD، تراکنش، هم‌زمانی، نوع‌های داده، pool، داده‌ی منتقل‌شده از SQLite، مسیرهای پویا"""
import os, sys, time, threading, json, subprocess
import pgtest
import bot_test as b, games as g, miniapp as m
import db
def ok(c, n): print(("PASS " if c else "FAIL ") + n)
sch = pgtest.fresh("pg")
b.BOT_ID = 999; b.BOT_USERNAME = "jfj_bot"
with db.schema_lock():
    b.install_schema(); b.migrate_schema(); m._mini_tables()
g.init(b); b.GAMES = g; b.seed_products()
# ---------- نوع‌ها
with b.get_db() as c:
    cols = dict(c.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='users'").fetchall())
ok(cols["id"] == "bigint" and cols["referred_by"] == "bigint" and cols["tokens"] == "double precision", "نوع ستون‌ها: id/referred_by=bigint, tokens=double")
with b.get_db() as c:
    bad = c.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema=current_schema() AND data_type='integer'").fetchall()
ok(not bad, "هیچ ستون ۳۲بیتی integer نیست " + str(bad[:3]))
big = 7_000_000_123; neg = -1_001_234_567_890
b.upsert_user({"id": big, "first_name": "Big"}); ok(b.user_exists(big), "آیدی ۶۴بیتی کاربر")
with b.get_db() as c:
    c.execute("INSERT INTO requests (tracking_code, user_id, member_count, token_cost, link, chat_id) VALUES ('K1',?,5,5,'l',?)", (big, neg))
    r = c.execute("SELECT chat_id FROM requests WHERE tracking_code='K1'").fetchone()
ok(r[0] == neg, "chat_id منفی بزرگ")
# شاهی اعشاری و گرد کردن
with b.get_db() as c:
    c.execute("UPDATE users SET tokens=? WHERE id=?", (10.55, big))
ok(abs(b.get_balance(big) - 10.55) < 1e-9, "شاهی اعشاری ذخیره می‌شود")
with g._Tx() as c: g._pay_in(c, big, 0.1); g._pay_in(c, big, 0.2)
ok(b.get_balance(big) == 10.85, "پرداخت اعشاری با ROUND ۲رقم: %r" % b.get_balance(big))
with g._Tx() as c: okc = g._charge_in(c, big, 10.85)
ok(okc and b.get_balance(big) == 0, "کسر کامل بدون خطای اعشار")
with g._Tx() as c: okc = g._charge_in(c, big, 0.01)
ok(not okc and b.get_balance(big) == 0, "کسر بیش از موجودی رد می‌شود")
# SUM/AVG → عدد پایتون (نه Decimal)
with b.get_db() as c:
    s1 = c.execute("SELECT SUM(member_count) FROM requests").fetchone()[0]
    s2 = c.execute("SELECT COALESCE(SUM(tokens),0) FROM users").fetchone()[0]
ok(isinstance(s1, int) and isinstance(s2, (int, float)), "SUM → int/float (%s,%s)" % (type(s1).__name__, type(s2).__name__))
# رشته‌ی دارای % و ? و '
b.set_setting("t_special", "100% ? 'x' \"y\" \\ سلام")
ok(b.get_setting("t_special") == "100% ? 'x' \"y\" \\ سلام", "رشته‌ی خاص (%, ?, ', \\) سالم ذخیره می‌شود")
with b.get_db() as c:
    r = c.execute("SELECT value FROM settings WHERE key=? AND value LIKE '%?%'", ("t_special",)).fetchone()
ok(r is not None, "LIKE با % در SQL و پارامتر")
# Row: اندیس + نام
with b.get_db() as c:
    r = c.execute("SELECT id, first_name FROM users WHERE id=?", (big,)).fetchone()
    ok(r[0] == big and r["id"] == big and r["first_name"] == "Big" and tuple(r) == (big, "Big") and dict(r)["id"] == big, "Row: اندیس/نام/dict/tuple")
    a_, n_ = r; ok(a_ == big, "unpack")
# زمان‌ها: قالب متنی UTC مثل SQLite
with b.get_db() as c:
    ts = c.execute("SELECT created_at FROM users WHERE id=?", (big,)).fetchone()[0]
ok(isinstance(ts, str) and len(ts) == 19 and ts[4] == "-" and ts[10] == " ", "created_at متنی YYYY-MM-DD HH:MM:SS: " + ts)
import datetime as dt
ok(abs((dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - dt.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")).total_seconds()) < 5, "created_at برحسب UTC")
with b.get_db() as c:
    n = c.execute("SELECT COUNT(*) FROM users WHERE created_at >= datetime('now','-1 day')").fetchone()[0]
    n2 = c.execute("SELECT COUNT(*) FROM users WHERE created_at >= datetime('now','+1 day')").fetchone()[0]
ok(n == 1 and n2 == 0, "datetime('now','-1 day') معادل")
# ---------- تراکنش
b.upsert_user({"id": 501, "first_name": "T"})
try:
    with b.get_db() as c:
        c.execute("UPDATE users SET tokens=999 WHERE id=501")
        raise RuntimeError("boom")
except RuntimeError: pass
ok(b.get_balance(501) != 999, "خطا داخل with → rollback")
with b.get_db() as c: c.execute("UPDATE users SET tokens=77 WHERE id=501")
ok(b.get_balance(501) == 77, "خروج موفق → commit")
try:
    with b.get_db() as c:
        c.execute("INSERT INTO users (id) VALUES (501)")
except db.IntegrityError: ok(True, "نقض یکتایی → IntegrityError")
else: ok(False, "نقض یکتایی")
# بعد از خطا، اتصال pool سالم است
ok(b.get_balance(501) == 77, "اتصال بعد از خطا سالم به pool برمی‌گردد")
# ---------- ON CONFLICT / RETURNING / rid
with b.get_db() as c:
    j1 = c.execute("INSERT INTO joins (user_id, tracking_code) VALUES (1,'K1') ON CONFLICT DO NOTHING").rowcount
    j2 = c.execute("INSERT INTO joins (user_id, tracking_code) VALUES (1,'K1') ON CONFLICT DO NOTHING").rowcount
ok((j1, j2) == (1, 0), "INSERT OR IGNORE معادل: rowcount 1/0")
jid = b.bc_create(501, 501, 501, 1, "all") if False else None
with b.get_db() as c:
    i1 = c.execute("INSERT INTO sponsor_subs (user_id, hours, status) VALUES (1,1,'pending') RETURNING id").fetchone()[0]
    i2 = c.execute("INSERT INTO sponsor_subs (user_id, hours, status) VALUES (1,1,'pending') RETURNING id").fetchone()[0]
ok(i2 == i1 + 1, "RETURNING id (جای lastrowid)")
with b.get_db() as c:
    for i in range(5): c.execute("INSERT INTO requests (tracking_code, user_id, member_count, token_cost, link) VALUES (?,1,3,3,'x')", (f"Z{i}",))
    rows = c.execute("SELECT tracking_code FROM requests WHERE user_id=1 ORDER BY created_at, rid").fetchall()
ok([r[0] for r in rows] == [f"Z{i}" for i in range(5)], "ترتیب درج با rid (جای rowid)")
# ---------- هم‌زمانی: کسر هم‌زمان شاهی (بدون منفی شدن / بدون کسر مضاعف)
b.upsert_user({"id": 600, "first_name": "C"})
with b.get_db() as c: c.execute("UPDATE users SET tokens=100 WHERE id=600")
res = []
def w():
    try: res.append(b.deduct_tokens(600, 10))
    except Exception as e: res.append(repr(e))
fn = [n for n in dir(b) if "spend" in n.lower() or "deduct" in n.lower() or "charge" in n.lower()]
print("INFO کسر:", fn)
ths = [threading.Thread(target=w) for _ in range(30)]
[t.start() for t in ths]; [t.join() for t in ths]
okn = sum(1 for r in res if r is True)
ok(okn == 10 and b.get_balance(600) == 0, "۳۰ کسر هم‌زمان ۱۰تایی از ۱۰۰ → دقیقاً ۱۰ موفق، موجودی ۰ (موفق=%d، موجودی=%s)" % (okn, b.get_balance(600)))
# ثبت تکراری update_id هم‌زمان
cl = []
def cu(): cl.append(b.claim_update(424242))
ths = [threading.Thread(target=cu) for _ in range(20)]
[t.start() for t in ths]; [t.join() for t in ths]
ok(sum(1 for x in cl if x) == 1, "claim_update هم‌زمان: فقط یک برنده")
# upsert هم‌زمان کاربر
ths = [threading.Thread(target=b.upsert_user, args=({"id": 700, "first_name": "Z"},)) for _ in range(20)]
[t.start() for t in ths]; [t.join() for t in ths]
with b.get_db() as c: ok(c.execute("SELECT COUNT(*) FROM users WHERE id=700").fetchone()[0] == 1, "upsert_user هم‌زمان: یک ردیف")
# تراکنش بازی‌ها: قفل سراسری (۲ ترد، افزایش ثبت‌شده بدون گم‌شدن)
b.upsert_user({"id": 800, "first_name": "L"})
with b.get_db() as c: c.execute("UPDATE users SET tokens=0 WHERE id=800")
def inc():
    for _ in range(25):
        with g._Tx() as c:
            v = c.execute("SELECT tokens FROM users WHERE id=800").fetchone()["tokens"]
            c.execute("UPDATE users SET tokens=? WHERE id=800", (v + 1,))
ths = [threading.Thread(target=inc) for _ in range(6)]
[t.start() for t in ths]; [t.join() for t in ths]
ok(b.get_balance(800) == 150, "خواندن-تغییر-نوشتن داخل _Tx هم‌زمان: ۱۵۰ بدون گم‌شدن (%s)" % b.get_balance(800))
# pool: تعداد زیاد درخواست هم‌زمان
os.environ["DB_POOL_MAX"] = "5"
errs = []
def q():
    try:
        for _ in range(20):
            with b.get_db() as c: c.execute("SELECT pg_sleep(0.001)"); c.execute("SELECT COUNT(*) FROM users").fetchone()
    except Exception as e: errs.append(repr(e))
ths = [threading.Thread(target=q) for _ in range(25)]
[t.start() for t in ths]; [t.join() for t in ths]
ok(not errs, "۲۵ ترد روی pool با سقف ۵ اتصال بدون خطا " + str(errs[:1]))
with b.get_db() as c:
    n_conn = c.execute("SELECT COUNT(*) FROM pg_stat_activity WHERE application_name='jfj-bot'").fetchone()[0]
ok(1 <= n_conn <= 5 + 6, "تعداد اتصال‌های باز محدود می‌ماند (%d)" % n_conn)
os.environ["DB_POOL_MAX"] = "20"
# اتصال قطع‌شده: pool خودش دوباره وصل می‌شود
with b.get_db() as c: pid = c.execute("SELECT pg_backend_pid()").fetchone()[0]
with b.get_db() as c1, b.get_db() as c2: c2.execute("SELECT pg_terminate_backend(?)", (pid,)) if c1._raw.get_transaction_status() is not None else None
time.sleep(0.2)
try:
    with b.get_db() as c: v = c.execute("SELECT 1").fetchone()[0]
    ok(v == 1, "بعد از قطع اتصال از سمت سرور، درخواست بعدی جواب می‌دهد")
except Exception as e:
    # اولین درخواست روی اتصال مرده ممکن است خطا بدهد؛ بعدی باید سالم باشد
    with b.get_db() as c: v = c.execute("SELECT 1").fetchone()[0]
    ok(v == 1, "اتصال مرده دور ریخته شد و بعدی سالم است (%s)" % type(e).__name__)
# ---------- امنیت پیام خطا
db.configure("postgresql://u:SECRETPW@127.0.0.1:1/x", None)
try: db.check_connection()
except Exception as e: ok("SECRETPW" not in str(e), "پیام خطای اتصال رمز را فاش نمی‌کند")
db.configure(pgtest.URL, sch)
# ---------- مسیرهای پویا
with b.get_db() as c: c.execute("INSERT INTO requests (tracking_code, user_id, member_count, token_cost, link) VALUES ('Q1',1,3,3,'x')")
for cat in m.LB_AGG:
    try:
        items = m.lb_items(cat, 0, 5); ok(isinstance(items, (list, tuple, dict)), "لیدربرد مینی‌اپ " + cat)
    except Exception as e: ok(False, "لیدربرد %s: %r" % (cat, e))
for kind in g._LB_SQL:
    try:
        for q_ in g._LB_SQL[kind][:2]: pass
        g._row(g._LB_SQL[kind][1], (big,)) if kind in ("t","r") else None
        g._rows(g._LB_SQL[kind][0], (5,)); g._row(g._LB_SQL[kind][2], (1, 1, 1))
        ok(True, "لیدربرد بازی‌ها " + kind)
    except Exception as e: ok(False, "لیدربرد بازی‌ها %s: %r" % (kind, e))
print("DONE")
# انتقال هم‌زمان A→B و B→A (deadlock نباید رخ دهد)
for i in (901, 902):
    b.upsert_user({"id": i, "first_name": "X%d" % i})
    with b.get_db() as c: c.execute("UPDATE users SET tokens=1000 WHERE id=?", (i,))
errs = []
def tr(a, bb):
    try:
        for _ in range(40): b.transfer_tokens(a, bb, 1)
    except Exception as e: errs.append(repr(e))
b.rep_ev_transfer = lambda *a, **k: None
ths = [threading.Thread(target=tr, args=(901, 902)) for _ in range(4)] + [threading.Thread(target=tr, args=(902, 901)) for _ in range(4)]
[t.start() for t in ths]; [t.join() for t in ths]
ok(not errs and b.get_balance(901) + b.get_balance(902) == 2000, "انتقال‌های دوطرفه‌ی هم‌زمان: بدون deadlock و جمع ثابت %s" % errs[:1])
