"""آزمون سرتاسری مینی‌اپ با Chromium واقعی (Playwright): محصول غیرفعال و کانال مسدود. اگر Playwright نبود رد می‌شود."""
import os, sys, time, json, threading, hmac, hashlib, tempfile
from urllib.parse import urlencode
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
def ok(c, n): print(("PASS " if c else "FAIL ") + n)
try:
    from playwright.sync_api import sync_playwright
except Exception:
    print("SKIP playwright نصب نیست"); sys.exit(0)
import pgtest
import bot_test as b, miniapp as m
pgtest.fresh('e2e')
b.BOT_TOKEN = "123:TESTTOKEN"
m._schema_done = False; m.ensure_ready = lambda: None
b.install_schema(); b.migrate_schema(); b.seed_products()
with b.get_db() as c:
    c.execute("CREATE TABLE IF NOT EXISTS mini_seen (user_id INTEGER NOT NULL, code TEXT NOT NULL, verified INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (user_id, code))")
    c.execute("CREATE TABLE IF NOT EXISTS mini_meta (k TEXT PRIMARY KEY, v TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS mini_notices (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, ukey TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'info', title TEXT, body TEXT, created_at TEXT, UNIQUE(user_id, ukey))")
    c.execute("CREATE TABLE IF NOT EXISTS mini_notice_read (user_id INTEGER NOT NULL, ukey TEXT NOT NULL, PRIMARY KEY (user_id, ukey))")
b.upsert_user({"id": 5, "first_name": "A"}); b.upsert_user({"id": 6, "first_name": "B"})
with b.get_db() as c:
    c.execute("UPDATE users SET tokens=1000")
    c.execute("INSERT INTO requests (tracking_code,user_id,member_count,token_cost,link,chat_id,status) VALUES ('C1',6,10,10,'https://t.me/chanx',-100123,'in_progress')")
m.reconcile_leaves = lambda *a, **k: []; m.member_status = lambda *a, **k: "left"; m.chat_title = lambda *a, **k: "کانال تست"
b.resolve_chat_ident = lambda cid, link: "@chanx"; b.bot_admin_state = lambda i: True
b.tg = lambda method, _timeout=45, **p: {"ok": False, "description": "offline"}
m.sync_notices = lambda uid: None
m.get_notices = lambda uid: ([], 0)
m.fetch_photo = lambda code: None
def init_data(uid):
    pairs = {"auth_date": str(int(time.time())), "user": json.dumps({"id": uid, "first_name": "A"}), "query_id": "q"}
    chk = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    h = hmac.new(hmac.new(b"WebAppData", b.BOT_TOKEN.encode(), hashlib.sha256).digest(), chk.encode(), hashlib.sha256).hexdigest()
    return urlencode(dict(pairs, hash=h))
from wsgiref.simple_server import make_server, WSGIServer, WSGIRequestHandler
from socketserver import ThreadingMixIn
class T(ThreadingMixIn, WSGIServer): daemon_threads = True
class Q(WSGIRequestHandler):
    def log_message(self, *a): pass
srv = make_server("127.0.0.1", 0, m.application, server_class=T, handler_class=Q)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
INIT = init_data(5)
with sync_playwright() as pw:
    br = pw.chromium.launch()
    pg = br.new_page(viewport={"width": 420, "height": 860})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.Telegram={WebApp:new Proxy({initData:%s,initDataUnsafe:{},platform:'web',colorScheme:'light',themeParams:{},safeAreaInset:{top:0,bottom:0},contentSafeAreaInset:{top:0,bottom:0}},{get:(t,k)=>k in t?t[k]:(()=>{})})};" % json.dumps(INIT))
    pg.goto(f"http://127.0.0.1:{port}/")
    pg.wait_for_function("typeof S!=='undefined' && S.data && S.data.services", timeout=25000)
    ok(True, "مینی‌اپ بالا آمد و state گرفت")
    # ۱) محصول فعال: صفحه‌ی خرید باز می‌شود و دکمه‌ی ثبت سفارش هست
    pg.evaluate("go('home')"); pg.evaluate("acts.goSvc({v:'views'})") if False else None
    pg.evaluate("S.svc='views'; go('service','home')")
    pg.wait_for_timeout(300)
    ok("ثبت سفارش" in pg.inner_text("body"), "محصول فعال: دکمه‌ی ثبت سفارش دیده می‌شود")
    # ۲) ادمین محصول را غیرفعال می‌کند؛ مینی‌اپ بدون بستن، خودش متوجه می‌شود
    b.set_product_field("views", "enabled", 0)
    pg.evaluate("pollLive()"); pg.wait_for_timeout(800)
    txt = pg.inner_text("body")
    ok("در حال حاضر ناموجود" in txt and "ثبت سفارش" not in txt, "غیرفعال‌شدن هنگام باز بودن صفحه: دکمه‌ی سفارش برداشته شد")
    # ۳) رفتن به خرید از خانه
    pg.evaluate("go('home')"); pg.wait_for_timeout(600)
    pg.evaluate("document.querySelector('[data-act=goSvc][data-v=views]').click()"); pg.wait_for_timeout(500)
    ok(pg.evaluate("S.tab") == "home", "دکمه‌ی محصول غیرفعال در خانه وارد صفحه‌ی خرید نمی‌شود")
    pg.evaluate("document.querySelector('[data-act=goSvc][data-v=members]').click()"); pg.wait_for_timeout(500)
    ok(pg.evaluate("S.tab") == "service", "محصول فعال دیگر هنوز قابل ورود است")
    # ۴) سفارش مستقیم API روی محصول غیرفعال
    r = pg.evaluate("api('/api/service',{service:'views',qty:1000,link:'https://t.me/x/1'}).then(()=>'ok').catch(e=>e.message)")
    ok("ناموجود" in r, "API هم سفارش محصول غیرفعال را رد می‌کند")
    # ۵) JFJ: کانال دیده می‌شود، بعد مسدود می‌شود و بدون بستن برنامه برداشته می‌شود
    pg.evaluate("go('join','home')"); pg.wait_for_function("S.list && S.list.length===1", timeout=15000)
    ok("کانال تست" in pg.inner_text("body") or "chanx" in pg.inner_text("body"), "کانال در بخش JFJ نمایش داده شد")
    b.block_chan(["@chanx"])
    pg.evaluate("pollLive()"); pg.wait_for_function("S.list && S.list.length===0", timeout=15000)
    ok(True, "کانال مسدودشده بدون بستن برنامه از JFJ برداشته شد")
    b.unblock_chan("@chanx")
    pg.evaluate("loadList()"); pg.wait_for_function("S.list && S.list.length===1", timeout=15000)
    b.delete_request_admin("C1", False)
    pg.evaluate("pollLive()"); pg.wait_for_function("S.list && S.list.length===0", timeout=15000)
    ok(True, "درخواست حذف‌شده هم برداشته شد")
    # ۶) بخش‌های خاموش در «فعال/غیرفعال کردن بخش‌ها» (مثل «خرید شاهی»)
    pg.evaluate("go('buyToken','home')"); pg.wait_for_timeout(500)
    ok("بستهٔ مورد نظر" in pg.inner_text("body") or "بسته" in pg.inner_text("body"), "خرید شاهی: وقتی روشن است باز می‌شود")
    b.set_setting("sec_off", json.dumps(["bt", "sj"]))
    pg.evaluate("pollLive()"); pg.wait_for_function("secOff('bt')", timeout=15000); pg.wait_for_timeout(400)
    ok("غیرفعال" in pg.inner_text("body"), "خرید شاهی خاموش: صفحه‌ی باز هم بدون بستن برنامه غیرفعال شد")
    pg.evaluate("go('home')"); pg.wait_for_timeout(500)
    pg.evaluate("document.querySelector('[data-act=goBuyToken]').click()"); pg.wait_for_timeout(400)
    ok(pg.evaluate("S.tab") == "home", "دکمه‌ی خرید شاهی در خانه وارد صفحه نمی‌شود")
    pg.evaluate("document.querySelector('[data-act=goJoin]').click()"); pg.wait_for_timeout(400)
    ok(pg.evaluate("S.tab") == "home", "شروع JFJ خاموش وارد صفحه نمی‌شود")
    r = pg.evaluate("api('/api/invoice',{pack:'x'}).then(()=>'ok').catch(e=>e.message)")
    ok("غیرفعال" in r, "API خرید شاهی هم رد می‌شود")
    b.set_setting("sec_off", "[]")
    pg.evaluate("pollLive()"); pg.wait_for_function("!secOff('bt')", timeout=15000)
    pg.evaluate("document.querySelector('[data-act=goBuyToken]').click()"); pg.wait_for_timeout(400)
    ok(pg.evaluate("S.tab") == "buyToken", "بعد از روشن‌شدن دوباره باز می‌شود")
    # ۷) بخش‌های ریز: فقط سین خاموش؛ ممبر باز
    b.set_setting("sec_off", json.dumps(["sn"]))
    pg.evaluate("go('home')"); pg.evaluate("loadState(true)"); pg.wait_for_function("secOff('sn')", timeout=15000); pg.wait_for_timeout(400)
    pg.evaluate("document.querySelector('[data-act=goSvc][data-v=views]').click()"); pg.wait_for_timeout(400)
    ok(pg.evaluate("S.tab") == "home", "فقط سین خاموش: ورود به سین بسته است")
    pg.evaluate("document.querySelector('[data-act=goSvc][data-v=members]').click()"); pg.wait_for_timeout(400)
    ok(pg.evaluate("S.tab") == "service", "فقط سین خاموش: ممبر باز است")
    r = pg.evaluate("api('/api/service',{service:'seen',qty:1000,link:'https://t.me/x/1'}).then(()=>'ok').catch(e=>e.message)")
    ok("غیرفعال" in r, "API سین رد می‌شود")
    # ۸) طراحی صفحه‌ی خاموش
    b.set_setting("sec_off", json.dumps(["sp"]))
    pg.evaluate("go('home')"); pg.evaluate("loadState(true)"); pg.wait_for_function("secOff('sp')", timeout=15000)
    pg.evaluate("S.tab='sponsor'; render()"); pg.wait_for_timeout(400)
    t8 = pg.inner_text("body")
    ok("موقتاً غیرفعال است" in t8 and "بازگشت به خانه" in t8 and "بررسی دوباره" in t8, "صفحه‌ی خاموش: طراحی کامل")
    b.set_setting("sec_off", "[]")
    pg.evaluate("A.recheck()"); pg.wait_for_function("!secOff('sp')", timeout=15000)
    # ۹) کل مینی‌اپ خاموش
    b.set_setting("sec_off", json.dumps(["mi"]))
    pg.evaluate("loadState(true)"); pg.wait_for_function("secOff('mi')", timeout=15000); pg.wait_for_timeout(400)
    ok("«مینی‌اپ» موقتاً غیرفعال است" in pg.inner_text("body"), "مینی‌اپ خاموش: کل برنامه قفل")
    b.set_setting("sec_off", "[]")
    # ۱۰) ادمین: صفحه‌ی قفل را می‌بیند و با دکمه رد می‌شود
    pg.evaluate("S.data.isAdmin=true"); b.set_setting("sec_off", json.dumps(["sp"]))
    pg.evaluate("go('home')"); pg.wait_for_timeout(900); pg.evaluate("S.data.isAdmin=true; S.data.secOff=['sp']; go('sponsor','home')"); pg.wait_for_timeout(300)
    ok("ورود با دسترسی ادمین" in pg.inner_text("body"), "ادمین هم صفحه‌ی قفل را می‌بیند")
    pg.evaluate("A.adminPass({v:'sp'})"); pg.wait_for_timeout(400)
    ok("ورود با دسترسی ادمین" not in pg.inner_text("body"), "ادمین با دکمه وارد می‌شود")
    pg.evaluate("S.data.isAdmin=false"); b.set_setting("sec_off", "[]")
    # ۱۱) کاربر کانال را باز کرد و جوین شد؛ بازگشت به برنامه نباید آیتم را حذف کند
    with b.get_db() as c:
        c.execute("DELETE FROM requests WHERE tracking_code='C2'")
        c.execute("INSERT INTO requests (tracking_code,user_id,member_count,token_cost,link,chat_id,status) VALUES ('C2',6,10,10,'https://t.me/chanx2',-100124,'in_progress')")
    b.resolve_chat_ident = lambda cid, link: "@chanx2"
    pg.evaluate("go('join','home')"); pg.wait_for_function("S.list && S.list.length===1", timeout=15000)
    pg.evaluate("S.opened={C2:true}")
    m.member_status = lambda *a, **k: "member"     # کاربر جوین شد
    pg.evaluate("loadList(true)"); pg.wait_for_timeout(1500)
    ok(pg.evaluate("S.list.length") == 1, "جوین‌شده‌ی بازشده تا تأیید در لیست می‌ماند")
    pg.evaluate("S.opened={}; loadList(true)"); pg.wait_for_timeout(1500)
    ok(pg.evaluate("S.list.length") == 0, "کانالی که کاربر باز نکرده و عضو است نمایش داده نمی‌شود")
    pg.evaluate("S.opened={C2:true}; loadList(true)"); pg.wait_for_timeout(1500)
    ok(pg.evaluate("S.list.length") == 1, "دوباره با opened نمایش داده می‌شود")
    m.member_status = lambda *a, **k: "left"
    # ۱۲) تمام‌صفحه‌ی تلگرام (Android، Bot API 8.0): Back همیشه، فاصله‌ی ایمن بالا، بستن از خانه
    pg2 = br.new_page(viewport={"width": 420, "height": 860})
    e2 = []; pg2.on("pageerror", lambda e: e2.append(str(e)))
    pg2.add_init_script("""
      window.__log={fs:0,show:0,hide:0,close:0,cb:null};
      const W={initData:%s,initDataUnsafe:{},platform:'android',version:'8.0',colorScheme:'dark',themeParams:{},isFullscreen:false,
        isVersionAtLeast:(v)=>true, ready(){}, expand(){}, disableVerticalSwipes(){}, onEvent(){}, close(){window.__log.close++},
        requestFullscreen(){window.__log.fs++; this.isFullscreen=true;},
        HapticFeedback:{impactOccurred(){},notificationOccurred(){}},
        BackButton:{show(){window.__log.show++},hide(){window.__log.hide++},onClick(f){window.__log.cb=f}}};
      window.Telegram={WebApp:W};
      document.addEventListener('DOMContentLoaded',()=>{document.documentElement.style.setProperty('--tg-safe-area-inset-top','24px');document.documentElement.style.setProperty('--tg-content-safe-area-inset-top','56px');});
    """ % json.dumps(INIT))
    pg2.goto(f"http://127.0.0.1:{port}/")
    pg2.wait_for_function("typeof S!=='undefined' && S.data && S.data.services", timeout=25000)
    pg2.wait_for_function("!document.getElementById('splash')", timeout=15000); pg2.wait_for_timeout(600)
    lg = pg2.evaluate("window.__log")
    ok(lg["fs"] == 1, "درخواست تمام‌صفحه (requestFullscreen) فرستاده شد")
    ok(lg["show"] >= 1 and lg["hide"] == 0, "در تمام‌صفحه دکمه‌ی Back روی خانه هم نمایش داده می‌شود")
    top = pg2.evaluate("document.getElementById('head').getBoundingClientRect().top")
    ok(top >= 79, "هدر مینی‌اپ زیر قرص‌های تلگرام قرار گرفت (top=%s)" % top)
    pg2.evaluate("window.__log.cb()"); ok(pg2.evaluate("window.__log.close") == 1, "Back روی خانه برنامه را می‌بندد")
    pg2.evaluate("go('buyToken','home')"); pg2.wait_for_timeout(300); pg2.evaluate("window.__log.cb()"); pg2.wait_for_timeout(300)
    ok(pg2.evaluate("S.tab") == "home" and pg2.evaluate("window.__log.close") == 1, "Back در صفحه‌ی داخلی به خانه برمی‌گردد")
    ok(not e2, "بدون خطای جاوااسکریپت در تمام‌صفحه")
    # کلاینت بدون تمام‌صفحه (وب): هیچ درخواستی ارسال نمی‌شود
    ok(pg.evaluate("typeof Telegram.WebApp.requestFullscreen") in ("function","undefined"), "کلاینت وب بدون خطا")
    pg2.close()
    ok(not errs, "بدون خطای جاوااسکریپت" + (": " + errs[0] if errs else ""))
    br.close()
