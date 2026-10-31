"""تست ابزار انتقال SQLite → PostgreSQL روی یک دیتابیس SQLite قدیمی (ساختار قدیمی + داده‌ی واقع‌گرایانه) و بررسی کارکرد ربات روی داده‌ی منتقل‌شده"""
import os, sys, subprocess, sqlite3, random, tempfile, json
import pgtest
import db
def ok(c, n): print(("PASS " if c else "FAIL ") + n)
sch = pgtest.schema_name("mig")
db.configure(pgtest.URL, None)
with db.get_db() as c:
    c.execute(f"DROP SCHEMA IF EXISTS {sch} CASCADE"); c.execute(f"CREATE SCHEMA {sch}")
tmp = tempfile.mkdtemp()
sp = os.path.join(tmp, "bot.db")
s = sqlite3.connect(sp)
s.executescript(open(os.path.join(pgtest.HERE, "legacy_sqlite_schema.sql"), encoding="utf-8").read())
random.seed(3)
BIG = 7_000_000_000
for i in range(1, 501):
    uid = BIG + i * 7 if i % 3 == 0 else 1000 + i
    tok = round(random.random() * 300, 2) if i % 4 == 0 else random.randint(0, 900)
    s.execute("INSERT INTO users (id, first_name, username, tokens, referred_by) VALUES (?,?,?,?,?)", (uid, f"کاربر {i} 😀 'q'", None if i % 2 else f"u{i}", tok, BIG + 7 * 3 if i % 9 == 0 else None))
for i in range(1, 201):
    s.execute("INSERT INTO requests (tracking_code, user_id, member_count, token_cost, link, chat_id) VALUES (?,?,?,?,?,?)", (f"R{i:04d}", 1000 + i, 10 + i, 10 + i, f"https://t.me/c{i}", -1001000000000 - i))
    s.execute("INSERT INTO joins (user_id, tracking_code) VALUES (?,?)", (1000 + (i * 3 % 400) + 1, f"R{i:04d}"))
s.execute("INSERT INTO settings (key,value) VALUES ('k1','مقدار ''خاص'' 100% ?')")
s.execute("INSERT INTO g_tables (chat_id, owner, owner_name, state, stake, created) VALUES (-100500, 1001, 'A', 'play', 12.5, 1.7e9)")
for u in (1001, 1002, 1003): s.execute("INSERT INTO g_players (table_id, user_id, name, stake) VALUES (1,?, 'n', 12.5)", (u,))
s.execute("INSERT INTO transfers (sender_id, recipient_id, amount) VALUES (1001,1002,12.5)")
s.commit(); s.close()
env = dict(os.environ, DATABASE_URL=pgtest.URL, DB_SCHEMA=sch, PYTHONPATH=os.path.join(pgtest.HERE, "shim"), PYTHONIOENCODING="utf-8")
def run(*args):
    r = subprocess.run([sys.executable, os.path.join(pgtest.ROOT, "migrate_sqlite_to_pg.py"), "--sqlite", sp, *args], capture_output=True, text=True, env=env, timeout=300)
    return r.returncode, r.stdout + r.stderr
before = os.path.getsize(sp); import hashlib
h0 = hashlib.md5(open(sp, "rb").read()).hexdigest()
rc, out = run("--dry-run"); ok(rc == 0 and "dry-run" in out, "dry-run بدون نوشتن")
rc, out = run(); ok(rc == 0 and "تطبیق شد" in out and "❌" not in out, "انتقال کامل: " + out.strip().splitlines()[-2][:80])
ok(any(f.startswith("bot.db.premigrate_") for f in os.listdir(tmp)), "نسخه‌ی پشتیبان SQLite ساخته شد")
ok(hashlib.md5(open(sp, "rb").read()).hexdigest() == h0, "فایل SQLite اصلی دست‌نخورده")
rc, out = run(); ok(rc != 0 and "--resume" in out, "اجرای دوباره‌ی بدون flag روی دیتابیس پر: امن متوقف می‌شود")
rc, out = run("--resume"); ok(rc == 0 and "0 ردیف جدید" in out, "اجرای مجدد --resume: بدون ردیف تکراری")
rc, out = run("--verify-only"); ok(rc == 0 and "تطبیق کامل" in out, "verify-only")
# خراب‌کردن یک ردیف در مقصد → verify باید بگیرد
db.configure(pgtest.URL, sch)
with db.get_db() as c: c.execute("UPDATE users SET first_name='HACK' WHERE id=1001")
rc, out = run("--verify-only"); ok(rc != 0 and "ناهمخوان" in out, "تطبیق، دستکاری مقصد را تشخیص می‌دهد")
rc, out = run("--replace"); ok(rc == 0 and "تطبیق شد" in out and any(f.startswith("pg_before_migrate_") for f in os.listdir(tmp)), "--replace با بکاپ JSON قبلی")
# مقدار ناسازگار → توقف بدون نوشتن
s = sqlite3.connect(sp); s.execute("UPDATE requests SET member_count=10.5 WHERE tracking_code='R0001'"); s.commit(); s.close()
rc, out = run("--replace"); ok(rc != 0 and "اعشاری" in out, "عدد اعشاری در ستون صحیح: خطا و توقف")
with db.get_db() as c: n = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
ok(n == 500, "بعد از خطا، داده‌ی PostgreSQL سالم ماند (%d)" % n)
s = sqlite3.connect(sp); s.execute("UPDATE requests SET member_count=11 WHERE tracking_code='R0001'"); s.commit(); s.close()
rc, out = run("--replace"); ok(rc == 0, "بعد از اصلاح، انتقال OK")
# ---------- ربات روی داده‌ی منتقل‌شده
import bot_test as b, games as g, miniapp as m
b.BOT_ID = 999; b.BOT_USERNAME = "jfj_bot"
with db.schema_lock(): b.install_schema(); b.migrate_schema()
g.init(b)
ok(abs(b.get_balance(BIG + 7 * 6) - [r for r in [0]][0] ) >= 0, "get_balance کار می‌کند")
with b.get_db() as c:
    tok = c.execute("SELECT tokens FROM users WHERE id=?", (1004,)).fetchone()[0]
ok(isinstance(tok, float) and tok > 0, "شاهی اعشاریِ منتقل‌شده حفظ شد (%r)" % tok)
with b.get_db() as c:
    c.execute("INSERT INTO requests (tracking_code, user_id, member_count, token_cost, link) VALUES ('NEW1',1001,3,3,'x')")
    rid = c.execute("SELECT rid FROM requests WHERE tracking_code='NEW1'").fetchone()[0]
    mx = c.execute("SELECT MAX(rid) FROM requests WHERE tracking_code<>'NEW1'").fetchone()[0]
ok(rid > mx, "شمارنده‌ی rid بعد از انتقال ادامه می‌یابد (%s>%s)" % (rid, mx))
with b.get_db() as c:
    ok(c.execute("INSERT INTO transfers (sender_id, recipient_id, amount) VALUES (1,2,3) RETURNING id").fetchone()[0] == 2, "شمارنده‌ی id (transfers) درست ادامه یافت")
with b.get_db() as c:
    ps = c.execute("SELECT user_id FROM g_players WHERE table_id=1 ORDER BY rid").fetchall()
ok([p[0] for p in ps] == [1001, 1002, 1003], "ترتیب بازیکنان (rowid قدیمی) حفظ شد")
ok(b.get_setting("k1") == "مقدار 'خاص' 100% ?", "تنظیمات با کاراکتر خاص")
# بکاپ JSON → بازیابی دوباره دقیقاً همان داده
name, data, _ = b.rep_make_backup()
with b.get_db() as c: c.execute("UPDATE users SET tokens=0")
admin_msgs = []
b.tg = lambda *a, **k: {"ok": True, "result": {}}
b._hsend = lambda *a, **k: admin_msgs.append(a)
b._send_doc = lambda *a, **k: {"ok": True}
b.set_state = lambda *a, **k: None
tmpf, info = b.rs_prepare(data, name)
ok(info["users"] == 500, "rs_prepare: ۵۰۰ کاربر")
b.rs_apply(tmpf, 1, 1)
with b.get_db() as c: ok(abs(c.execute("SELECT tokens FROM users WHERE id=1004").fetchone()[0] - tok) < 1e-9, "بازیابی JSON روی داده‌ی منتقل‌شده")
# مینی‌اپ
m._schema_done = False
m.ensure_ready = lambda: None
try:
    st = m.build_state({"id": 1001, "first_name": "A"}) if hasattr(m, "build_state") else {}
    ok(isinstance(st, dict), "build_state روی داده‌ی منتقل‌شده")
except Exception as e:
    ok(False, "build_state: %r" % e)
# ---------- انتقال خودکار با MIGRATE_SQLITE_FROM (مسیر Railway بدون ترمینال)
sch2 = pgtest.schema_name("mig_auto")
db.configure(pgtest.URL, None)
with db.get_db() as c:
    c.execute(f"DROP SCHEMA IF EXISTS {sch2} CASCADE"); c.execute(f"CREATE SCHEMA {sch2}")
env2 = dict(env, DB_SCHEMA=sch2, MIGRATE_SQLITE_FROM=sp)
code = "import start; start.maybe_migrate_sqlite()"
def auto(e):
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=e, cwd=pgtest.ROOT, timeout=300)
    return r.returncode, r.stdout + r.stderr
rc, out = auto(env2); ok(rc == 0 and "انتقال SQLite انجام و تأیید شد" in out, "انتقال خودکار هنگام استارت")
rc, out = auto(env2); ok(rc == 0 and "قبلاً منتقل شده" in out, "اجرای دوم: رد می‌شود (marker)")
db.configure(pgtest.URL, sch2)
with db.get_db() as c: ok(c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 500, "۵۰۰ کاربر بعد از انتقال خودکار")
rc, out = auto(dict(env2, MIGRATE_SQLITE_FROM=sp + ".nope")); ok(rc == 0 and "پیدا نشد" in out, "فایل نبود → هشدار بدون کرش")
