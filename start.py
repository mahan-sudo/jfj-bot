"""اجرای هم‌زمان ربات + مینی‌اپ در یک سرویس (برای Railway و مشابه)"""
import os, sys, threading, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import miniapp  # noqa: E402
import bot_test as bot  # noqa: E402


def maybe_migrate_sqlite():
    """انتقال خودکار و یک‌باره‌ی دیتابیس قدیمی SQLite به PostgreSQL (مخصوص وقتی دسترسی به ترمینال نیست).
    فقط اگر متغیر MIGRATE_SQLITE_FROM=/data/bot.db تنظیم باشد. اجرا idempotent است (--resume) و با تطبیق شمارش/checksum؛
    اگر ناموفق باشد ربات روشن نمی‌شود تا با دیتابیس خالی کار نکند. فایل SQLite هرگز حذف/تغییر نمی‌کند."""
    src = os.environ.get("MIGRATE_SQLITE_FROM", "").strip()
    if not src:
        return
    if not os.path.isfile(src):
        print(f"WARNING: MIGRATE_SQLITE_FROM={src} پیدا نشد؛ انتقال انجام نشد", flush=True)
        return
    import subprocess
    marker = "sqlite_migrated:" + os.path.basename(src)
    try:
        with bot.get_db() as c:
            if bot._db.table_exists(c, "settings"):
                r = c.execute("SELECT value FROM settings WHERE key=?", (marker,)).fetchone()
                if r and not os.environ.get("MIGRATE_SQLITE_FORCE"):
                    print(f"SQLite قبلاً منتقل شده ({r[0]}); برای تکرار MIGRATE_SQLITE_FORCE=1 بگذارید", flush=True)
                    return
    except Exception as e:
        raise SystemExit("اتصال به PostgreSQL برقرار نشد: " + bot._db._safe(e))
    print("🚚 شروع انتقال SQLite → PostgreSQL ...", flush=True)
    rc = subprocess.call([sys.executable, os.path.join(HERE, "migrate_sqlite_to_pg.py"), "--sqlite", src, "--resume"])
    if rc != 0:
        raise SystemExit(f"انتقال SQLite ناموفق بود (کد {rc}); ربات روشن نشد. لاگ بالا را ببینید؛ فایل SQLite دست‌نخورده است.")
    with bot.get_db() as c:
        c.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
                  (marker, time.strftime("%Y-%m-%d %H:%M:%S")))
    print("✅ انتقال SQLite انجام و تأیید شد", flush=True)


def run_bot():
    while True:
        try:
            bot.main()
        except BaseException:  # SystemExit هم (مثلاً قطعی لحظه‌ای تلگرام)
            traceback.print_exc()
        time.sleep(10)


if __name__ == "__main__":
    maybe_migrate_sqlite()
    miniapp.ensure_ready()
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", "8000"))
    print(f"mini app on :{port}", flush=True)
    try:
        from waitress import serve
        serve(miniapp.application, host="0.0.0.0", port=port, threads=8)
    except ImportError:
        from socketserver import ThreadingMixIn
        from wsgiref.simple_server import make_server, WSGIServer

        class T(ThreadingMixIn, WSGIServer):
            daemon_threads = True
        make_server("0.0.0.0", port, miniapp.application, server_class=T).serve_forever()
