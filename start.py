"""اجرای هم‌زمان ربات + مینی‌اپ در یک سرویس (برای Railway و مشابه)"""
import os, sys, threading, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import miniapp  # noqa: E402  (مسیر دیتابیس را از JFJ_DB می‌گیرد)
import bot_test as bot  # noqa: E402


def run_bot():
    while True:
        try:
            bot.main()
        except BaseException:  # SystemExit هم (مثلاً قطعی لحظه‌ای تلگرام)
            traceback.print_exc()
        time.sleep(10)


if __name__ == "__main__":
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
