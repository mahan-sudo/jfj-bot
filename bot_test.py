"""
نسخه‌ی تست تک‌فایلی - بدون نیاز به نصب هیچ پکیجی (فقط کتابخانه‌ی استاندارد پایتون)
- دیتابیس: SQLite
- ریس کاندیشن: جلوگیری از پردازش دوباره‌ی آپدیت + قفل هر کاربر + کسر/افزایش اتمیک توکن
- فلوها: درخواست JFJ | حساب من (زیرمجموعه‌گیری و چالش امروز) | بانک انتقال
- تاریخ/ساعت شمسی بدون کتابخانه‌ی جانبی محاسبه می‌شود
اجرا:  python3 bot_test.py
"""
import hashlib
import hmac
import html as _hmod
import mimetypes
import os
import sys
import traceback
from urllib.parse import parse_qs, parse_qsl
import json
import logging
import random
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# ===================== تنظیمات =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN") or "PUT_YOUR_NEW_TOKEN_HERE"  # روی Railway در Variables با نام BOT_TOKEN بگذارید
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "8322577437").replace(" ", "").split(",") if x]  # آیدی عددی ادمین (می‌توانید چند آیدی بگذارید: [111, 222])
# مسیر دیتابیس: اگر متغیر محیطی DB_PATH (مثلاً /data/bot.db روی Railway با Volume) تنظیم شود همان استفاده می‌شود
DB_PATH = os.environ.get("DB_PATH") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.db")
TIMEZONE = "Asia/Tehran"

TOKENS_PER_MEMBER = 1       # هزینه‌ی هر ممبر در درخواست JFJ
MIN_MEMBER_COUNT = 3         # حداقل تعداد ممبر قابل درخواست
RESUBMIT_COOLDOWN_SECONDS = 5 * 60  # فاصله‌ی لازم بین دو درخواست JFJ برای یک کانال/گروه یکسان
MIN_TRANSFER_AMOUNT = 5      # حداقل مقدار قابل انتقال در بانک انتقال
STARTING_TOKENS = 2          # موجودی اولیه‌ی کاربر جدید
REFERRAL_REWARD = 5          # پاداش معرف وقتی زیرمجموعه‌اش فعال شود
REFERRAL_ACTIVITY_THRESHOLD = 3  # زیرمجموعه باید این‌قدر از فعالیت (جوین در JFJ) کسب کند تا معرف پاداش بگیرد
JOIN_REWARD = 1              # پاداش هر جوین موفق در بخش شروع JFJ
LEAVE_REFUND_TO_OWNER = 1    # وقتی ممبر لفت می‌دهد، این‌قدر به صاحب سفارش برمی‌گردد (و ۱ شاهی از لفت‌دهنده کم می‌شود)

# ---------- تنظیمات فاکتور/پرداخت (مشترک بین شاهی و اسپانسری) ----------
CARD_NUMBER = "0000-0000-0000-0000"   # شماره کارت خودتان را جایگزین کنید
CARD_HOLDER = "نام صاحب کارت"          # نام صاحب کارت را جایگزین کنید
INVOICE_VALIDITY_MINUTES = 30
INVOICE_OFFSET_MIN = 1000    # مبلغ نهایی فاکتور = قیمت پایه + عددی رندوم بین این دو
INVOICE_OFFSET_MAX = 1950    # (برای تشخیص خودکار واریزی‌ها روی صورت‌حساب بانکی)

# قیمت‌ها فعلاً نمونه/جای‌گذاری هستند — خودتان اصلاح کنید
JTOKEN_PRODUCTS = [
    {"id": "jt100", "tokens": 100, "price": 15000},
    {"id": "jt200", "tokens": 200, "price": 28000},
    {"id": "jt400", "tokens": 400, "price": 54000},
    {"id": "jt1000", "tokens": 1000, "price": 130000},
    {"id": "jt2000", "tokens": 2000, "price": 250000},
]

SPONSOR_PRODUCTS = [
    {"id": "sp24", "hours": 24, "price": 50000},
    {"id": "sp48", "hours": 48, "price": 90000},
    {"id": "sp72", "hours": 72, "price": 130000},
]

SUPPORT_ID = os.environ.get("SUPPORT_ID") or "@your_support_username"  # آیدی پشتیبانی را جایگزین کنید

# افکت‌های انیمیشنی پیام (فقط در چت خصوصی کار می‌کنند)
EFFECT_PARTY = "5046509860389126442"  # 🎉

BOT_USERNAME = None  # در startup پر می‌شود
BOT_ID = None        # در startup پر می‌شود

# ===================== متن‌های منوی اصلی =====================
BTN_REQUEST_JFJ = "📋 درخواست JFJ"
BTN_START_JFJ = "🏁 شروع JFJ"
BTN_MY_ACCOUNT = "🆔️ حساب من"
BTN_TRANSFER_BANK = "🏦 بانک انتقال"
BTN_BUY_JTOKEN = "🛍 خرید شاهی"
BTN_BUY_SERVICES = "⭐️ خرید ممبر و سین ..."
BTN_SUPPORT = "☎️ پشتیبانی"
BTN_MY_ORDERS = "🔍 سفارش من"
BTN_RULES = "📛 قوانین"
BTN_MINIAPP = "💻 Mini app"
BACK_BTN = "بازگشت ◁"
BTN_ADMIN_PANEL = "🖌 پنل مدیریت"
BTN_ADMIN_STATS = "📊 آمار ربات"
BTN_ADMIN_PRODUCTS = "🏬 تنظیمات محصولات"
BTN_PROD_STATUS = "📊 وضعیت قابلیت‌های محصولات"
BTN_PROD_LAYOUT = "🔁 چیدمان دکمه محصولات"

MAIN_MENU_TEXT = ("🌸 به جفج شاهنشاهی خوش آمدی!\n\n/help راهنما\n\n🎯 همین الان شروع کن.\n"
                  "درخواست JFJ بده و ممبر واقعی دریافت کن.")
BACK_MENU_TEXT = "👇 لطفا از منوی زیر انتخاب کنید."

SUCCESS = "success"  # سبز
DANGER = "danger"    # قرمز
PRIMARY = "primary"  # آبی


def btn(text, style=None):
    b = {"text": text}
    if style:
        b["style"] = style
    return b


def is_admin(user_id):
    return user_id in ADMIN_IDS


def miniapp_url():
    """آدرس مینی‌اپ: از MINIAPP_URL یا (روی Railway) از آدرس عمومی خودِ سرویس"""
    u = (os.environ.get("MINIAPP_URL") or "").strip()
    if not u:
        d = (os.environ.get("RAILWAY_PUBLIC_DOMAIN") or "").strip()
        if d:
            u = f"https://{d}/app"
    return u if u.startswith("https://") else ""


def kb_sig(uid):
    return hmac.new(BOT_TOKEN.encode(), f"jfj-kb:{int(uid)}".encode(), hashlib.sha256).hexdigest()[:32]


def main_menu(user_id):
    mu = miniapp_url()
    buy_row = [btn(BTN_BUY_JTOKEN, SUCCESS), btn(BTN_BUY_SERVICES, SUCCESS)]
    if mu and "mi" in sections_off() and not is_admin(user_id):
        mu = None
    if mu:  # دکمه‌ی مینی‌اپ دقیقاً بین «خرید شاهی» و «خرید ممبر و سین»
        buy_row.insert(1, {"text": BTN_MINIAPP, "web_app": {"url": mu + ("&" if "?" in mu else "?") + f"kb={int(user_id)}.{kb_sig(user_id)}"}, "style": SUCCESS})
    rows = [
        [btn(BTN_REQUEST_JFJ, SUCCESS), btn(BTN_START_JFJ, SUCCESS)],
        [btn(BTN_MY_ACCOUNT, SUCCESS), btn(BTN_TRANSFER_BANK, SUCCESS)],
        buy_row,
        [btn(BTN_SUPPORT, DANGER), btn(BTN_MY_ORDERS, DANGER), btn(BTN_RULES, DANGER)],
    ]
    if is_admin(user_id):
        rows.append([btn(BTN_ADMIN_PANEL)])
    return {
        "keyboard": rows,
        "resize_keyboard": True,
        "is_persistent": False,
    }


def admin_panel_menu():
    """کیبوردی که ادمین بعد از زدن «🖌 پنل مدیریت» می‌بیند"""
    return {
        "keyboard": [
            [btn(BTN_ADMIN_STATS)],
            [btn(BTN_ADMIN_PRODUCTS), btn("⚙️ تنظیمات عمومی")],
            [btn("☎️ بخش پشتیبانی")],
            [btn("🏦 مالی"), btn("👤 مدیریت کاربر")],
            [btn("🎗 تنظیمات اسپانسر"), btn("👥️ تنظیمات زیرمجموعه")],
            [btn("🛍 تنظیمات خرید شاهی"), btn("🧰 تنظیمات درخواست JFJ")],
            [btn("🧾 سفارشات تکمیل نشده")],
        ],
        "resize_keyboard": True,
        "is_persistent": False,
    }


def back_menu():
    """کیبورد پایین صفحه در تمام مراحل فلوهای چندمرحله‌ای (JFJ / بانک انتقال)"""
    return {
        "keyboard": [[btn(BACK_BTN, DANGER)]],
        "resize_keyboard": True,
        "is_persistent": False,
    }


# ===================== تاریخ و ساعت شمسی (بدون کتابخانه‌ی جانبی) =====================
def gregorian_to_jalali(gy, gm, gd):
    g_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    j_days = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]
    gy2 = gy - 1600
    gm2 = gm - 1
    gd2 = gd - 1
    g_day_no = 365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
    for i in range(gm2):
        g_day_no += g_days[i]
    if gm2 > 1 and ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0):
        g_day_no += 1
    g_day_no += gd2
    j_day_no = g_day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053
    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461
    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365
    jm, jd = 12, j_day_no + 1
    for i in range(11):
        if j_day_no < j_days[i]:
            jm, jd = i + 1, j_day_no + 1
            break
        j_day_no -= j_days[i]
    return jy, jm, jd


_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa_digits(s):
    return s.translate(_FA_DIGITS)


def fmt_tokens(value):
    """موجودی/هزینه می‌تواند اعشاری شود (بازگشت نیم‌توکن هنگام لفت، یا هزینه‌ی
    خدمات تلگرام که متناسب با تعداد حساب می‌شود). عدد صحیح بدون اعشار و بقیه
    حداکثر با دو رقم اعشار (بدون صفرهای اضافی) نمایش داده می‌شود: 10 یا 11.5 یا 1.67"""
    value = round(float(value), 2)
    if value == int(value):
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def fmt_num(value):
    """عدد با جداکننده‌ی هزارگان؛ اعشار (حداکثر ۲ رقم) فقط در صورت نیاز: 1,250 یا 1,250.5"""
    value = round(float(value), 2)
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def jalali_now_strings():
    dt = datetime.now(ZoneInfo(TIMEZONE))
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    date_str = fa_digits(f"{jy:04d}/{jm:02d}/{jd:02d}")
    time_str = fa_digits(dt.strftime("%H:%M"))
    return date_str, time_str


def stamp(label="زمان ثبت", md=True):
    """خط زمان (جلالی) برای همه‌ی پیام‌های ثبت/تأیید؛ برای اعتماد و امنیت کاربر"""
    d, t = jalali_now_strings()
    return f"⏰️ *{label}: {t} - {d}*" if md else f"⏰ {label}: {t} - {d}"


# ===================== دیتابیس =====================
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def install_schema():
    with get_db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            tokens INTEGER NOT NULL DEFAULT 0,
            activity_tokens INTEGER NOT NULL DEFAULT 0,
            referral_rewarded INTEGER NOT NULL DEFAULT 0,
            vip INTEGER NOT NULL DEFAULT 0,
            referred_by INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS processed_updates (
            update_id INTEGER PRIMARY KEY,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS states (
            user_id INTEGER PRIMARY KEY,
            state TEXT NOT NULL,
            data TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS requests (
            tracking_code TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            member_count INTEGER NOT NULL,
            token_cost INTEGER NOT NULL,
            link TEXT NOT NULL,
            chat_id INTEGER,
            initial_member_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'in_progress',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_requested_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS joins (
            user_id INTEGER NOT NULL,
            tracking_code TEXT NOT NULL,
            joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            left_at TEXT,
            PRIMARY KEY (user_id, tracking_code))""")
        c.execute("""CREATE TABLE IF NOT EXISTS invoices (
            code TEXT PRIMARY KEY,
            buyer_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            kind TEXT NOT NULL DEFAULT 'vip',
            product_name TEXT NOT NULL,
            base_price INTEGER NOT NULL,
            final_amount INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            meta TEXT,
            chat_id INTEGER,
            message_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS products (
            key TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 1,
            min_qty INTEGER NOT NULL,
            rate_cost REAL NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            recipient_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS service_orders (
            tracking_code TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            service TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            extra TEXT,
            token_cost REAL NOT NULL,
            link TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")


def migrate_schema():
    """برای دیتابیس‌های قدیمی‌تر که ستون‌های جدید را ندارند"""
    alters = [
        "ALTER TABLE users ADD COLUMN activity_tokens INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN referral_rewarded INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE requests ADD COLUMN initial_member_count INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE requests ADD COLUMN chat_id INTEGER",
        "ALTER TABLE requests ADD COLUMN last_requested_at TEXT",
        "ALTER TABLE joins ADD COLUMN left_at TEXT",
        "ALTER TABLE invoices ADD COLUMN kind TEXT NOT NULL DEFAULT 'vip'",
        "ALTER TABLE invoices ADD COLUMN meta TEXT",
        "ALTER TABLE users ADD COLUMN banned INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE bc_jobs ADD COLUMN pin INTEGER NOT NULL DEFAULT 0",
    ]
    with get_db() as c:
        for stmt in alters:
            try:
                c.execute(stmt)
            except sqlite3.OperationalError:
                pass  # ستون از قبل وجود دارد
        try:
            c.execute("ALTER TABLE service_orders ADD COLUMN admin_notified INTEGER NOT NULL DEFAULT 0")
            c.execute("UPDATE service_orders SET admin_notified=1")  # سفارش‌های قدیمی دوباره ارسال نشوند
        except sqlite3.OperationalError:
            pass
    v2_migrate()


def user_exists(user_id):
    with get_db() as c:
        return c.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone() is not None


def upsert_user(user, referred_by=None):
    """ثبت کاربر به‌صورت اتمیک؛ به کاربر تازه موجودی اولیه‌ی تستی داده می‌شود"""
    with get_db() as c:
        c.execute(
            """INSERT INTO users (id, first_name, username, tokens, referred_by) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   first_name = excluded.first_name,
                   username = excluded.username,
                   updated_at = CURRENT_TIMESTAMP""",
            (user["id"], user.get("first_name"), user.get("username"), STARTING_TOKENS, referred_by),
        )


def get_balance(user_id):
    with get_db() as c:
        row = c.execute("SELECT tokens FROM users WHERE id=?", (user_id,)).fetchone()
        return row[0] if row else 0


REFERRAL_SIGNUP_TEXT = (
    "✅️ *زیرمجموعه جدید گرفتی!*\n\n"
    f"💎 *با جمع‌آوری {REFERRAL_ACTIVITY_THRESHOLD} شاهی توسط زیرمجموعه، {REFERRAL_REWARD} شاهی دریافت میکنید!*"
)
REFERRAL_CONFIRMED_TEXT = (
    "✅ *زیرمجموعه شما تایید شد!*\n\n"
    f"🎉 *به کیف پول شما ‌{REFERRAL_REWARD} شاهی افزوده شد.*"
)


def notify_new_referral(referrer_id, new_user=None):
    """همان لحظه‌ای که کاربر جدید از لینک زیرمجموعه‌گیری وارد شد (هنوز پاداشی داده نمی‌شود)"""
    rep_ev_ref_new(referrer_id, new_user)
    for attempt in range(3):
        r = send(referrer_id, REFERRAL_SIGNUP_TEXT)
        if r.get("ok"):
            return True
        logging.warning("referral signup notify to %s failed (try %s): %s", referrer_id, attempt + 1, r)
        if r.get("error_code") in (400, 403):
            break  # بلاک/چت نامعتبر؛ تکرار فایده ندارد
        time.sleep(1 + attempt)
    return False


def register_start_referral(message):
    """اگر کاربر تازه با لینک دعوت /start کرد، همان لحظه (قبل از هر قفل جوین اجباری و ...) ثبت و به معرف خبر می‌دهد"""
    user = message.get("from") or {}
    text = (message.get("text") or "").strip()
    m = re.match(r"^/start(?:@\w+)?\s+ref(\d+)", text)
    if not m or not user.get("id") or user_exists(user["id"]):
        return
    candidate = int(m.group(1))
    if candidate == user["id"] or not user_exists(candidate):
        return
    upsert_user(user, referred_by=candidate)
    notify_new_referral(candidate, user)


def get_referral_count(user_id):
    with get_db() as c:
        row = c.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (user_id,)).fetchone()
        return row[0] if row else 0


def add_activity_tokens(user_id, amount):
    with get_db() as c:
        c.execute("UPDATE users SET activity_tokens = activity_tokens + ? WHERE id=?", (amount, user_id))


def maybe_reward_referrer(user_id):
    """وقتی زیرمجموعه به‌اندازه‌ی کافی از فعالیت (جوین در JFJ) کسب کرد، معرف پاداش می‌گیرد.
    کسر/افزایش و ست‌کردن پرچم reward در یک تراکنش واحد انجام می‌شود تا دوبار پرداخت نشود."""
    with get_db() as c:
        row = c.execute(
            "SELECT referred_by, activity_tokens, referral_rewarded FROM users WHERE id=?", (user_id,)
        ).fetchone()
        if not row:
            return
        referred_by, activity_tokens, rewarded = row
        if not referred_by or rewarded or activity_tokens < REFERRAL_ACTIVITY_THRESHOLD:
            return
        c.execute("UPDATE users SET tokens = tokens + ? WHERE id=?", (REFERRAL_REWARD, referred_by))
        c.execute("UPDATE users SET referral_rewarded=1 WHERE id=?", (user_id,))
    rep_ev_ref_ok(referred_by, user_id)
    r = send(referred_by, REFERRAL_CONFIRMED_TEXT)
    if not r.get("ok"):
        logging.warning("referral confirmed notify to %s failed: %s", referred_by, r)



def deduct_tokens(user_id, amount):
    """کسر اتمیک: فقط اگر موجودی کافی باشد کسر انجام می‌شود"""
    with get_db() as c:
        cur = c.execute("UPDATE users SET tokens = tokens - ? WHERE id=? AND tokens >= ?", (amount, user_id, amount))
        return cur.rowcount == 1


def add_tokens(user_id, amount):
    with get_db() as c:
        c.execute("UPDATE users SET tokens = tokens + ? WHERE id=?", (amount, user_id))


def transfer_tokens(sender_id, recipient_id, amount):
    """انتقال اتمیک: کسر از فرستنده و افزایش گیرنده در یک تراکنش واحد"""
    with get_db() as c:
        cur = c.execute("UPDATE users SET tokens = tokens - ? WHERE id=? AND tokens >= ?", (amount, sender_id, amount))
        if cur.rowcount != 1:
            return False
        c.execute("UPDATE users SET tokens = tokens + ? WHERE id=?", (amount, recipient_id))
        c.execute(
            "INSERT INTO transfers (sender_id, recipient_id, amount) VALUES (?, ?, ?)",
            (sender_id, recipient_id, amount),
        )
    rep_ev_transfer(sender_id, recipient_id, amount)
    return True


def get_state(user_id):
    with get_db() as c:
        row = c.execute("SELECT state, data FROM states WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            return None, {}
        return row[0], (json.loads(row[1]) if row[1] else {})


def set_state(user_id, state, data=None):
    with get_db() as c:
        c.execute(
            """INSERT INTO states (user_id, state, data) VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET state=excluded.state, data=excluded.data""",
            (user_id, state, json.dumps(data or {})),
        )


def clear_state(user_id):
    with get_db() as c:
        c.execute("DELETE FROM states WHERE user_id=?", (user_id,))


def generate_tracking_code():
    """کد ۵ رقمی رندوم و بدون تکرار"""
    with get_db() as c:
        for _ in range(50):
            code = f"{random.randint(0, 99999):05d}"
            if not c.execute("SELECT 1 FROM requests WHERE tracking_code=?", (code,)).fetchone():
                return code
    raise RuntimeError("کد پیگیری آزاد پیدا نشد")


def generate_service_order_code():
    """کد ۵ رقمی رندوم و بدون تکرار، مخصوص سفارش‌های خدمات تلگرام (ویو/ممبر/استارز/ری‌اکشن)"""
    with get_db() as c:
        for _ in range(50):
            code = f"{random.randint(0, 99999):05d}"
            if not c.execute("SELECT 1 FROM service_orders WHERE tracking_code=?", (code,)).fetchone():
                return code
    raise RuntimeError("کد پیگیری آزاد پیدا نشد")


def create_service_order(user_id, service_name, quantity, cost, link, code, extra=None):
    with get_db() as c:
        c.execute(
            """INSERT INTO service_orders (tracking_code, user_id, service, quantity, extra, token_cost, link)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (code, user_id, service_name, quantity, extra, cost, link),
        )
    rep_ev_service(code)


def create_request(user_id, member_count, token_cost, link, chat_id=None):
    """هر سفارش کاملاً مستقل است: کد پیگیری خودش، هدف خودش، تکمیل‌شدن خودش —
    هیچ ربطی به سفارش‌های دیگرِ همان کانال ندارد."""
    code = generate_tracking_code()
    now_iso = now_local().isoformat()
    with get_db() as c:
        c.execute(
            """INSERT INTO requests (tracking_code, user_id, member_count, token_cost, link, chat_id, last_requested_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (code, user_id, member_count, token_cost, link, chat_id, now_iso),
        )
    rep_ev_request(code)
    return code


def get_active_request_for_chat(user_id, chat_id_num):
    """آخرین درخواست این کاربر برای همین چت (اگر باشد) — فقط برای محدودیت ۵ دقیقه‌ای"""
    if not chat_id_num:
        return None
    with get_db() as c:
        return c.execute(
            """SELECT tracking_code, member_count, status, last_requested_at FROM requests
               WHERE user_id=? AND chat_id=? ORDER BY created_at DESC LIMIT 1""",
            (user_id, chat_id_num),
        ).fetchone()


def user_cooldown_left(user_id):
    """ثانیه‌ی باقی‌مانده تا کاربر بتواند درخواست JFJ تازه بدهد (۰ = آزاد)"""
    with get_db() as c:
        row = c.execute(
            "SELECT COALESCE(last_requested_at, created_at) FROM requests WHERE user_id=? "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1", (user_id,)).fetchone()
    if not row or not row[0]:
        return 0
    try:
        dt = datetime.fromisoformat(row[0])
    except ValueError:
        return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    left = RESUBMIT_COOLDOWN_SECONDS - (datetime.now(timezone.utc) - dt).total_seconds()
    return int(left) + 1 if left > 0 else 0


def cooldown_text(left):
    m, sec = divmod(left, 60)
    return f"{m} دقیقه و {sec} ثانیه" if m else f"{sec} ثانیه"


def get_recent_requests(user_id, limit=5):
    with get_db() as c:
        return c.execute(
            """SELECT tracking_code, member_count, link, status
               FROM requests WHERE user_id=? ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()


def get_join_count(tracking_code):
    """فقط جوین‌های فعال (کسی که لفت نداده) شمارش می‌شوند — مخصوص همین سفارش"""
    with get_db() as c:
        return c.execute(
            "SELECT COUNT(*) FROM joins WHERE tracking_code=? AND left_at IS NULL", (tracking_code,)
        ).fetchone()[0]


def refresh_request_status(tracking_code, member_count, status, owner_id=None):
    """وقتی تعداد جوین‌های همین سفارش (فقط همین یکی) به تعداد درخواستی‌اش برسد،
    وضعیت تکمیل‌شده ثبت و پیام تکمیل‌شدن برای صاحب همین سفارش ارسال می‌شود"""
    if status in ("completed", "removed", "deleted", "relinked"):
        return status
    if get_join_count(tracking_code) >= member_count:
        with get_db() as c:
            c.execute("UPDATE requests SET status='completed' WHERE tracking_code=?", (tracking_code,))
        rep_ev_request_state(tracking_code, "completed")
        if owner_id:
            date_str, time_str = jalali_now_strings()
            send(
                owner_id,
                "✅ *درخواست JFJ شما با موفقیت #تکمیل شد.*\n\n"
                f"🔍 *کد پیگیری: {tracking_code}*\n"
                f"⏰️ *زمان تکمیل: {time_str} - {date_str}*",
            )
        return "completed"
    return status


def handle_member_left(chat_numeric_id, user_id):
    """وقتی یک عضو از کانال/گروهی که برایش JFJ ثبت شده لفت می‌دهد:
    - بخشی از توکن آن جوین (نه کامل) به صاحب همان سفارش مشخص برمی‌گردد (وضعیت سفارش دست‌نخورده می‌ماند)
    - کل توکنی که خودِ کاربر برای جوین گرفته بود از او کسر می‌شود
    - جوین‌اش برای همان سفارش 'left' علامت می‌خورد تا آن سفارش مشخص دیگر برایش
      نمایش داده نشود، مگر اینکه صاحبش دوباره همان کانال را با سفارش تازه‌ای ثبت کند"""
    with get_db() as c:
        rows = c.execute(
            "SELECT tracking_code, user_id, link FROM requests WHERE chat_id=?", (chat_numeric_id,)
        ).fetchall()

    for tracking_code, owner_id, link in rows:
        with get_db() as c:
            cur = c.execute(
                "UPDATE joins SET left_at=? WHERE user_id=? AND tracking_code=? AND left_at IS NULL",
                (now_local().isoformat(), user_id, tracking_code),
            )
            refunded = cur.rowcount == 1
        if not refunded:
            continue  # این کاربر از طریق ربات برای همین سفارش جوین نگرفته بود (یا قبلاً پردازش شده)

        add_tokens(owner_id, LEAVE_REFUND_TO_OWNER)
        send(
            owner_id,
            f"🔔 *یه ممبر لفت داده!*\n💎 *تعداد {fmt_tokens(LEAVE_REFUND_TO_OWNER)} شاهی به موجودی شما اضافه شد.*",
        )

        with get_db() as c:
            c.execute("UPDATE users SET tokens = tokens - ? WHERE id=?", (JOIN_REWARD, user_id))  # می‌تواند منفی شود
        send(
            user_id,
            f"⛔️ *به دلیل لفت دادن شما*\n*از لینک ({link}) تعداد 💎{JOIN_REWARD} شاهی از شما کم شد!*",
        )
        rep_ev_leave(user_id, owner_id, tracking_code, link, JOIN_REWARD, LEAVE_REFUND_TO_OWNER)


# ===================== فاکتورها (مشترک: شاهی و اسپانسری) =====================
def now_local():
    return datetime.now(ZoneInfo(TIMEZONE))


def generate_invoice_code():
    """کد ۳ رقمی رندوم و بدون تکرار"""
    with get_db() as c:
        for _ in range(200):
            code = f"{random.randint(0, 999):03d}"
            if not c.execute("SELECT 1 FROM invoices WHERE code=?", (code,)).fetchone():
                return code
    raise RuntimeError("کد فاکتور آزاد پیدا نشد")


def generate_unique_amount(base_price):
    """مبلغ نهایی = قیمت پایه + عددی رندوم، طوری که بین فاکتورهای فعال تکراری نباشد"""
    now_iso = now_local().isoformat()
    with get_db() as c:
        for _ in range(200):
            amount = base_price + random.randint(INVOICE_OFFSET_MIN, INVOICE_OFFSET_MAX)
            clash = c.execute(
                "SELECT 1 FROM invoices WHERE final_amount=? AND status='pending' AND expires_at > ?",
                (amount, now_iso),
            ).fetchone()
            if not clash:
                return amount
    raise RuntimeError("مبلغ آزاد پیدا نشد")


def create_invoice(buyer_id, target_id, product_name, base_price, chat_id, message_id, kind, meta=None, exact_amount=None):
    code = generate_invoice_code()
    amount = exact_amount if exact_amount else generate_unique_amount(base_price)
    expires_at = (now_local() + timedelta(minutes=INVOICE_VALIDITY_MINUTES)).isoformat()
    with get_db() as c:
        c.execute(
            """INSERT INTO invoices
               (code, buyer_id, target_id, kind, product_name, base_price, final_amount, meta, chat_id, message_id, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (code, buyer_id, target_id, kind, product_name, base_price, amount,
             json.dumps(meta or {}), chat_id, message_id, expires_at),
        )
    return code, amount, expires_at


def get_invoice(code):
    with get_db() as c:
        return c.execute(
            "SELECT buyer_id, target_id, product_name, final_amount, status, chat_id, message_id, expires_at "
            "FROM invoices WHERE code=?",
            (code,),
        ).fetchone()


def set_invoice_status(code, new_status, expected_status=None):
    with get_db() as c:
        if expected_status:
            cur = c.execute(
                "UPDATE invoices SET status=? WHERE code=? AND status=?", (new_status, code, expected_status)
            )
        else:
            cur = c.execute("UPDATE invoices SET status=? WHERE code=?", (new_status, code))
        return cur.rowcount == 1


def invoice_watcher():
    """هر چند ثانیه فاکتورهای منقضی‌شده را پیدا و پیامشان را ویرایش می‌کند"""
    while True:
        try:
            now_iso = now_local().isoformat()
            with get_db() as c:
                rows = c.execute(
                    "SELECT code, chat_id, message_id FROM invoices WHERE status='pending' AND expires_at <= ?",
                    (now_iso,),
                ).fetchall()
            for code, chat_id, message_id in rows:
                if not set_invoice_status(code, "expired", expected_status="pending"):
                    continue
                try:
                    with get_db() as c:
                        m = c.execute("SELECT meta FROM invoices WHERE code=?", (code,)).fetchone()
                    dc_release((json.loads(m[0] or "{}") or {}).get("dc"))
                except Exception:
                    pass
                if chat_id and message_id:
                    edit(
                        chat_id, message_id,
                        "🔔 *زمان اعتبار این تراکنش به پایان رسید!*",
                        {"inline_keyboard": []},
                    )
        except Exception:
            logging.exception("invoice_watcher error")
        try:
            retry_unnotified_orders()
        except Exception:
            logging.exception("retry_unnotified_orders")
        time.sleep(20)


# قفل هر کاربر: پیام‌های همزمان یک کاربر پشت سر هم اجرا می‌شوند
_user_locks = {}
_guard = threading.Lock()


def user_lock(user_id):
    with _guard:
        return _user_locks.setdefault(user_id, threading.Lock())


# ===================== تلگرام =====================
_MD_TOK = re.compile(r"(```.*?```|`[^`\n]+`|\[[^\]\n]+\]\([^)\s]+\)|\*[^*\n]+\*|_[^_\n]+_)", re.S)


def _md_to_html(t):
    """Markdown قدیمی تلگرام -> HTML (برای اینکه کل متن بتواند bold شود)"""
    out = []
    pos = 0
    for m in _MD_TOK.finditer(t):
        out.append(_hmod.escape(t[pos:m.start()], quote=False))
        g = m.group(0)
        if g.startswith("```"):
            out.append("<pre>" + _hmod.escape(g.strip("`").strip("\n"), quote=False) + "</pre>")
        elif g[0] == "`":
            out.append("<code>" + _hmod.escape(g[1:-1], quote=False) + "</code>")
        elif g[0] == "[":
            lt, lu = g[1:].split("](", 1)
            out.append('<a href="%s">%s</a>' % (_hmod.escape(lu[:-1]), _hmod.escape(lt, quote=False)))
        elif g[0] == "*":
            out.append("<b>" + _hmod.escape(g[1:-1], quote=False) + "</b>")
        else:
            out.append("<i>" + _hmod.escape(g[1:-1], quote=False) + "</i>")
        pos = m.end()
    out.append(_hmod.escape(t[pos:], quote=False))
    return "".join(out)


# آیدی عددی کاربران در همه‌ی متن‌های ربات به‌صورت Mono (قابل کپی با یک لمس) نمایش داده می‌شود
_UID_RE = re.compile(r"((?:آیدی|ایدی|آی\u200cدی)\s*عددی\s*[:›：]*\s*|کاربر\s*[:›：]?\s*)(\d{6,15})(?!\d)")


def _mono_ids(h):
    return _UID_RE.sub(lambda m: m.group(1) + "<code>" + m.group(2) + "</code>", h)


def _boldify(method, params):
    """همه‌ی متن‌های ربات bold می‌شوند. اگر تلگرام HTML را نپذیرفت، نسخه‌ی اصلی ارسال می‌شود."""
    key = "caption" if method in ("sendPhoto", "sendDocument", "editMessageCaption", "sendVideo") else (
        "text" if method in ("sendMessage", "editMessageText") else None)
    if not key or not isinstance(params.get(key), str) or not params[key].strip():
        return None
    t = params[key]
    if not any(ch.isalnum() for ch in t):
        return None  # فقط ایموجی/نماد: bold نشود (ایموجی تکی کوچک می‌شود)
    pm = params.get("parse_mode")
    if pm == "HTML":
        h = t
    elif pm == "Markdown":
        h = _md_to_html(t)
    elif pm is None:
        h = _hmod.escape(t, quote=False)
    else:
        return None
    q = dict(params)
    q[key] = "<b>" + _mono_ids(h) + "</b>"
    q["parse_mode"] = "HTML"
    return q


_tg_warn = {}


def tg(method, _timeout=45, **params):
    q = _boldify(method, params)
    if q is not None:
        r = _tg_raw(method, _timeout, **q)
        if r.get("ok") or "parse entities" not in str(r.get("description", r.get("error_description", ""))):
            return r
    return _tg_raw(method, _timeout, **params)


def _tg_raw(method, _timeout=45, **params):
    """urllib خودش پروکسی محیط (http_proxy/https_proxy) را استفاده می‌کند.
    هیچ‌وقت exception پرتاب نمی‌کند؛ در صورت هر خطایی dict با ok=False برمی‌گرداند
    تا یک قطعی شبکه هرگز وسط یک فلو (مثل شروع JFJ) آن را نصفه‌کاره نگذارد."""
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        data=json.dumps(params).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read() or b"{}")
        except Exception:
            return {"ok": False, "error_description": str(e)}
    except Exception as e:
        _now = time.time()
        if _now - _tg_warn.get(method, 0) > 20:
            _tg_warn[method] = _now
            logging.warning("tg(%s) failed: %s", method, e)
        return {"ok": False, "error_description": str(e)}


def send(chat_id, text, reply_markup=None, markdown=True, effect_id=None):
    params = {"chat_id": chat_id, "text": text}
    if markdown:
        params["parse_mode"] = "Markdown"
    if reply_markup:
        params["reply_markup"] = reply_markup
    if effect_id:
        params["message_effect_id"] = effect_id  # فقط در چت خصوصی کار می‌کند
    return tg("sendMessage", **params)


def edit(chat_id, message_id, text, reply_markup=None, markdown=True):
    params = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if markdown:
        params["parse_mode"] = "Markdown"
    if reply_markup:
        params["reply_markup"] = reply_markup
    return tg("editMessageText", **params)


def answer_callback(callback_id, text=None, show_alert=False):
    params = {"callback_query_id": callback_id}
    if text:
        params["text"] = text
    if show_alert:
        params["show_alert"] = True
    tg("answerCallbackQuery", **params)


def send_main_menu(chat_id, user_id, back=False):
    st, _ = get_state(user_id)
    if st and st.startswith("admin_"):
        clear_state(user_id)
    if back:
        send(chat_id, BACK_MENU_TEXT, main_menu(user_id), markdown=False)
    else:
        send(chat_id, MAIN_MENU_TEXT, main_menu(user_id), markdown=False, effect_id=EFFECT_PARTY)


# ===================== فلوی درخواست JFJ =====================
def jfj_count_prompt_text():
    return "🧮 *تعداد ممبر مورد نیاز خودتون رو ارسال کنید:*\n\n👤 *1 member = 💎 1 شاهی*"


def send_jfj_count_prompt(chat_id, user_id):
    bal = fmt_tokens(get_balance(user_id))
    send(chat_id, jfj_count_prompt_text() + f"\n\n💎 *موجودی شما: {bal} شاهی*", back_menu())


def start_jfj_request(chat_id, user_id):
    set_state(user_id, "jfj_wait_count")
    send_jfj_count_prompt(chat_id, user_id)


def handle_jfj_wait_count(chat_id, user_id, text):
    if not text.isdigit():
        send(chat_id, "❗️ *فقط عدد ارسال کنید.*")
        return

    count = int(text)
    if count < MIN_MEMBER_COUNT:
        send(chat_id, f"🛑 *عدد ارسالی باید حداقل {MIN_MEMBER_COUNT} باشه.*")
        return

    cost = count * TOKENS_PER_MEMBER
    if get_balance(user_id) < cost:
        send(chat_id, "🛑 *موجودی کافی نیست!*", main_menu(user_id))
        clear_state(user_id)
        return

    set_state(user_id, "jfj_wait_link", {"count": count, "cost": cost})
    send(
        chat_id,
        "🔗 *لینک کانال یا گروه مورد نظرتونو بفرستید:*\n"
        f"⚠️ *حتما قبل از ارسال لینکتون, ربات (@{BOT_USERNAME}) رو توی کانالتون-گروهتون ادمین کنید!*",
        back_menu(),
    )


_LINK_MARKERS = ("http://", "https://", "t.me/", "@")
BLOCKED_MSG = "🛑 *امکان درخواست برای این گروه-کانال وجود ندارد.*"


def parse_jfj_link(text):
    """فقط آیدی با @ پذیرفته می‌شود (مثل @mychannel)؛ لینک http/https/t.me قبول نیست"""
    t = (text or "").strip()
    return t if re.fullmatch(r"@[A-Za-z][A-Za-z0-9_]{3,31}", t) else None


def _block_keys():
    return {str(k).lower() for k in sjson("jfj_block", [])}


def is_chan_blocked(ident=None, num=None):
    keys = _block_keys()
    if not keys:
        return False
    if ident and str(ident).lower() in keys:
        return True
    return bool(num) and f"id:{num}" in keys


def block_chan(keys):
    cur = sorted(_block_keys() | {str(k).lower() for k in keys if k})
    set_setting("jfj_block", json.dumps(cur, ensure_ascii=False))


def unblock_chan(key):
    cur = sorted(_block_keys() - {str(key).lower()})
    set_setting("jfj_block", json.dumps(cur, ensure_ascii=False))


def extract_chat_identifier(text):
    """از روی لینک/یوزرنیم ارسالی، شناسه‌ی قابل استفاده برای getChatMember را برمی‌گرداند"""
    m = re.search(r"@([A-Za-z0-9_]{4,})", text)
    if m:
        return "@" + m.group(1)
    m = re.search(r"t\.me/([A-Za-z0-9_]{4,})", text, re.IGNORECASE)
    if m and not m.group(1).lower().startswith(("joinchat", "+")):
        return "@" + m.group(1)
    return None


def handle_jfj_wait_link(chat_id, user_id, text, data):
    text = parse_jfj_link(text)
    if not text:
        send(chat_id, "🛑 *لطفا آیدی را صحیح وارد کنید! (حتما با @ شروع شود؛ مثل @mychannel)*")
        return

    chat_ident = extract_chat_identifier(text)
    if is_chan_blocked(chat_ident):
        send(chat_id, BLOCKED_MSG)
        return
    is_admin = False
    if chat_ident:
        res = tg("getChatMember", chat_id=chat_ident, user_id=BOT_ID)
        if res.get("ok"):
            is_admin = res["result"].get("status") in ("administrator", "creator")

    if not is_admin:
        send(chat_id, "🛑 *ربات توی چنلت ادمین نیست!*")
        return

    chat_id_num = None
    res_chat = tg("getChat", chat_id=chat_ident)
    if res_chat.get("ok"):
        chat_id_num = res_chat["result"].get("id")
    if is_chan_blocked(chat_ident, chat_id_num):
        send(chat_id, BLOCKED_MSG)
        return

    count, cost = data["count"], data["cost"]

    left = user_cooldown_left(user_id)
    if left:
        send(chat_id, f"🔔 *صبور باشید! بین دو درخواست JFJ باید حداقل {RESUBMIT_COOLDOWN_SECONDS // 60} دقیقه فاصله باشد.*\n"
                      f"⏳ *{cooldown_text(left)} دیگر صبر کنید.*")
        return

    existing = get_active_request_for_chat(user_id, chat_id_num)
    if existing:
        _, _, ex_status, ex_last_requested_at = existing
        if ex_status not in ("completed", "cancelled", "removed", "deleted", "relinked"):
            try:
                elapsed = (now_local() - datetime.fromisoformat(ex_last_requested_at)).total_seconds()
            except (TypeError, ValueError):
                elapsed = RESUBMIT_COOLDOWN_SECONDS  # ردیف قدیمی بدون زمان ثبت: محدودیت اعمال نمی‌شود
            if elapsed < RESUBMIT_COOLDOWN_SECONDS:
                send(
                    chat_id,
                    "🔔 *صبور باشید تا از درخواست قبلی برای این لینک حداقل 5 دقیقه بگذرد یا سفارش "
                    "قبلی تکمیل شود سپس سفارش جدید ثبت کنید!*",
                )
                return

    if not deduct_tokens(user_id, cost):
        send(chat_id, "🛑 *موجودی کافی نیست!*", main_menu(user_id))
        clear_state(user_id)
        return

    code = create_request(user_id, count, cost, text, chat_id_num)
    clear_state(user_id)

    date_str, time_str = jalali_now_strings()
    send(
        chat_id,
        "🚀 *درخواست JFJ شما #ثبت شد.*\n\n"
        f"🔍 *کد پیگیری: {code}*\n"
        f"⏰️ *زمان ثبت: {time_str} - {date_str}*",
        main_menu(user_id),
    )
    send(chat_id, "🔔 کانال شما اکنون در « 🏁 شروع JFJ » نمایش داده می‌شود.", None, markdown=False)


# ===================== بخش حساب من =====================
def account_text(user_id, first_name):
    balance = get_balance(user_id)
    ref_count = get_referral_count(user_id)
    date_str, time_str = jalali_now_strings()
    return (
        f"👤 *نام کاربر : {first_name or 'کاربر'}*\n"
        f"🆔️ *ایدی عددی : {user_id}*\n"
        f"🏦 *موجودی : {fmt_tokens(balance)} شاهی*\n"
        f"👥️ *زیرمجموعه‌گیری: {ref_count}*\n\n"
        f"⏰️ *زمان: {time_str} - {date_str}*"
    )


def btn_inline(text, callback_data, style=None):
    b = {"text": text, "callback_data": callback_data}
    if style:
        b["style"] = style
    return b


def account_keyboard():
    return {
        "inline_keyboard": [[
            btn_inline("👥️ زیرمجموعه‌گیری", "acc_ref", SUCCESS),
        ]]
    }


def send_account(chat_id, user_id, first_name):
    kb = account_keyboard() if ("rf" not in sections_off() or is_admin(user_id)) else None
    send(chat_id, account_text(user_id, first_name), kb)


def referral_link(user_id):
    return f"https://t.me/{BOT_USERNAME}?start=ref{user_id}"


def referral_text(user_id):
    link = referral_link(user_id)
    return (
        "🔗 *لینک زیرمجموعه‌گیری اختصاصی شما:*\n"
        f"`{link}`\n\n"
        f"🎁 *با ارسال لینک بالا برای بقیه به ازای هر فردی که وارد ربات بشه بهتون {REFERRAL_REWARD} تا شاهی تعلق میگیره!*"
    )


def referral_keyboard(user_id):
    return {
        "inline_keyboard": [[
            {
                "text": "کپی لینک زیرمجموعه‌گیری 🔗",
                "copy_text": {"text": referral_link(user_id)},
                "style": SUCCESS,
            }
        ]]
    }


def handle_callback(cq):
    data = cq.get("data", "")

    if data == "noop":
        answer_callback(cq["id"])
        return
    if data == "jfj_back":
        answer_callback(cq["id"])
        uid = cq["from"]["id"]
        clear_state(uid)
        send_main_menu(cq["message"]["chat"]["id"], uid, back=True)
        return
    _cbblk = callback_section_blocked(cq["from"]["id"], data)
    if _cbblk:
        answer_callback(cq["id"], f"🛑 بخش ({_cbblk}) فعلا غیرفعال میباشد!", show_alert=True)
        return
    if data.startswith("adm_"):
        handle_admin_callback(cq)
        return
    if data.startswith("pm:") or data.startswith("pm_dc") or data.startswith("pm_x"):
        handle_pay_callback(cq)
        return
    if data.startswith("sps:"):
        handle_sps_callback(cq)
        return
    if data.startswith("zp_chk:"):
        handle_zp_check(cq)
        return
    if data == "fj_check":
        handle_fj_check(cq)
        return
    svc_key = SVC_CALLBACK_KEYS.get(data)
    if svc_key and not product_open(cq["from"]["id"], svc_key):
        answer_callback(cq["id"], "🛑 این محصول در حال حاضر ناموجود است.", show_alert=True)
        return

    if data == "jfj_join":
        handle_jfj_join(cq)
        return
    if data == "jfj_next":
        handle_jfj_next(cq)
        return
    if data == "admin_stats_refresh":
        handle_admin_stats_refresh(cq)
        return
    if data.startswith("jt_pick:"):
        handle_jt_pick(cq)
        return
    if data.startswith("sp_pick:"):
        handle_sp_pick(cq)
        return
    if data.startswith(("jt_paid:", "sp_paid:")):
        handle_invoice_paid(cq)
        return
    if data == "svc_reaction":
        handle_svc_reaction_entry(cq)
        return
    if data == "svc_premium_reaction":
        handle_svc_premium_entry(cq)
        return
    if data in ("svc_views", "svc_members", "svc_stars"):
        handle_svc_simple_start(cq)
        return
    if data == "svc_buy_jtoken":
        handle_svc_buy_jtoken(cq)
        return
    if data.startswith("react_page:"):
        handle_react_page(cq)
        return
    if data.startswith("react_pick:"):
        handle_react_pick(cq)
        return
    if data.startswith("react_combo:"):
        handle_react_combo(cq)
        return
    if data == "react_cancel":
        handle_react_cancel(cq)
        return

    user = cq["from"]
    chat_id = cq["message"]["chat"]["id"]
    message_id = cq["message"]["message_id"]

    if data == "acc_ref":
        edit(chat_id, message_id, referral_text(user["id"]), referral_keyboard(user["id"]))

    answer_callback(cq["id"])


# ===================== شروع JFJ (جوین‌شدن و کسب توکن) =====================
JFJ_WELCOME_TEXT = (
    "🎗 *به بخش JFJ خوش آمدید.*\n\n"
    "💎 *در این بخش با جوین شدن در کانال دیگران و JFJ رفتن شاهی جمع آوری کنید!*"
)
JFJ_SEARCHING_TEXT = "🔍 *دارم برات درخواست JFJ پیدا میکنم, منتظر بمون!*"


def jfj_found_text(link):
    return f"🔍 *درخواست JFJ پیدا شد!*\n\n💎لینک: {link}"


def jfj_browse_keyboard():
    return {
        "inline_keyboard": [[
            btn_inline("✅️ جوین شدم", "jfj_join", SUCCESS),
            btn_inline("▷ بعدی", "jfj_next"),  # بدون رنگ
        ]]
    }


def resolve_chat_ident(chat_id_num, link):
    """اگر آیدی عددی چت ذخیره شده باشد همان استفاده می‌شود (مطمئن‌تر)، وگرنه از روی لینک حدس زده می‌شود"""
    return chat_id_num if chat_id_num else extract_chat_identifier(link)


def bot_admin_state(ident):
    """True = ربات ادمین است، False = قطعاً ادمین نیست (حذف شده/کانال پاک شده)، None = نامشخص (خطای شبکه و ...)"""
    if not ident or not BOT_ID:
        return None
    r = tg("getChatMember", chat_id=ident, user_id=BOT_ID, _timeout=10)
    if r.get("ok"):
        return r["result"].get("status") in ("administrator", "creator")
    d = str(r.get("description") or r.get("error_description") or "").lower()
    if r.get("error_code") in (400, 403) and any(x in d for x in (
            "chat not found", "kicked", "not a member", "forbidden", "channel_private", "chat_admin_required")):
        return False
    return None


def cancel_request_not_admin(code, why=""):
    """سفارش را بی‌صدا لغو می‌کند تا دیگر در شروع JFJ نمایش داده نشود (موجودی برنمی‌گردد)"""
    with get_db() as c:
        cur = c.execute("UPDATE requests SET status='removed' WHERE tracking_code=? AND status='in_progress'", (code,))
        c.execute("DELETE FROM mini_seen WHERE code=?", (code,)) if _table_exists(c, "mini_seen") else None
    if cur.rowcount:
        logging.warning("request %s cancelled: bot is not admin (%s)", code, why)
        rep_ev_request_state(code, "removed")
    return bool(cur.rowcount)


def _table_exists(c, name):
    return bool(c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


def request_sweeper():
    """هر ۳۰ دقیقه: سفارش‌هایی که ربات دیگر در کانال/گروهشان ادمین نیست بی‌صدا لغو می‌شوند"""
    time.sleep(60)
    while True:
        try:
            with get_db() as c:
                rows = c.execute("SELECT tracking_code, link, chat_id FROM requests WHERE status='in_progress'").fetchall()
            checked = {}
            for code, link, chat_id_num in rows:
                key = chan_key(chat_id_num, link)
                if key not in checked:
                    checked[key] = bot_admin_state(resolve_chat_ident(chat_id_num, link))
                    time.sleep(0.2)
                if checked[key] is False:
                    cancel_request_not_admin(code, "sweep")
                    continue
                ck = ("chg", chat_id_num, extract_chat_identifier(link or ""))
                if ck not in checked:
                    checked[ck] = link_changed_check(chat_id_num, link)
                    time.sleep(0.2)
                if checked[ck][0] is True:
                    relink_cancel_request(code, checked[ck][1])
        except Exception:
            logging.exception("request_sweeper")
        time.sleep(900)


def relink_cancel_request(code, new_note=""):
    """لینک کانال/گروه عوض شده: سفارش حذف می‌شود و هزینه‌ی باقی‌مانده (به نسبت ممبرهای نیامده) برمی‌گردد.
    True یعنی همین الان کنسل شد (فقط یک‌بار اجرا می‌شود)"""
    with get_db() as c:
        r = c.execute("SELECT user_id, member_count, token_cost, link, status FROM requests WHERE tracking_code=?", (code,)).fetchone()
        if not r or r[4] != "in_progress":
            return False
        cur = c.execute("UPDATE requests SET status='relinked' WHERE tracking_code=? AND status='in_progress'", (code,))
        if cur.rowcount != 1:
            return False
        if _table_exists(c, "mini_seen"):
            c.execute("DELETE FROM mini_seen WHERE code=?", (code,))
    uid, cnt, cost, link, _ = r
    done = get_join_count(code)
    rest = max(cnt - done, 0)
    amt = round(float(cost) * rest / max(cnt, 1), 2)
    if amt > 0:
        add_tokens(uid, amt)
    send(uid, "🔔 شما لینک کانال-گروه خود را تغییر دادید.\n\n"
              f"📊 لینک ({link}) تغییر یافت ، سفارش شما کنسل خواهد شد و مبلغ باقی مانده به کیف پول شما بازمیگردد.\n"
              f"💎 تعداد {fmt_tokens(amt)} شاهی به موجودی شما برگشت.", markdown=False)
    rep_ev_request_state(code, "relinked", new_note)
    if amt > 0:
        rep_ev_refund(None, uid, code, amt, "بازگشت هزینه‌ی باقی‌مانده (تغییر لینک کانال/گروه)")
    return True


def link_changed_check(chat_id_num, link):
    """True = لینک عمومی (@username) دیگر متعلق به این چت نیست؛ False = سالم؛ None = نامشخص/قابل‌بررسی‌نبودن"""
    ident = extract_chat_identifier(link or "")
    if not ident or not chat_id_num:
        return None, ""
    r = tg("getChat", chat_id=chat_id_num, _timeout=10)
    if not r.get("ok"):
        return None, ""
    res = r["result"]
    names = {str(res.get("username") or "").lower()} | {str(x).lower() for x in (res.get("active_usernames") or [])}
    names.discard("")
    if ident[1:].lower() in names:
        return False, ""
    cur = ("@" + res["username"]) if res.get("username") else "بدون یوزرنیم عمومی"
    return True, f"لینک قبلی: {ident} ← لینک فعلی: {cur}"


def chan_key(chat_id_num, link):
    """کلید یکتای کانال/گروه (مستقل از اینکه چند سفارش جدا برایش ثبت شده باشد)"""
    ident = extract_chat_identifier(link or "")
    if ident:
        return ident.lower()
    if chat_id_num:
        return f"id:{chat_id_num}"
    return re.sub(r"^https?://", "", (link or "").strip().lower()).rstrip("/")


def record_join(user_id, code):
    """ثبت جوین؛ اگر قبلاً لفت داده بود دوباره فعال می‌شود. True یعنی جوین تازه ثبت/فعال شد"""
    with get_db() as c:
        cur = c.execute("INSERT OR IGNORE INTO joins (user_id, tracking_code) VALUES (?, ?)", (user_id, code))
        if cur.rowcount == 1:
            new = True
        else:
            cur = c.execute("UPDATE joins SET left_at=NULL, joined_at=CURRENT_TIMESTAMP "
                            "WHERE user_id=? AND tracking_code=? AND left_at IS NOT NULL", (user_id, code))
            new = cur.rowcount == 1
    if new:
        rep_count("joins")
    return new


def user_channel_keys(user_id, exclude_code=None):
    """کانال‌هایی که کاربر از طریق ربات در آن‌ها جوین فعال دارد (کسی که لفت داده دوباره می‌تواند جوین بدهد)"""
    with get_db() as c:
        rows = c.execute("SELECT r.chat_id, r.link, j.tracking_code FROM joins j JOIN requests r ON r.tracking_code=j.tracking_code "
                         "WHERE j.user_id=? AND j.left_at IS NULL", (user_id,)).fetchall()
    return {chan_key(cid, lk) for cid, lk, code in rows if code != exclude_code}


def pick_jfj_candidate(user_id, exclude_code=None):
    """یک درخواست JFJ درحال‌انجام برمی‌گرداند که:
    - مال خود کاربر نباشد
    - قبلاً از طریق ربات در آن جوین نشده باشد (یا لفت داده و هنوز همان سفارش تازه ثبت نشده)
    - کاربر از قبل واقعاً عضوش نباشد (چک زنده با getChatMember)
    هر سفارش کاملاً مستقل دیده می‌شود؛ اگر یک کانال چند سفارش JFJ داشته باشد،
    از قبل‌عضو‌بودنِ واقعیِ کاربر (چک زنده) طبیعتاً جلوی دیدنِ دوباره‌ی همان کانال
    را می‌گیرد، بدون نیاز به منطق خاصی بین سفارش‌ها.
    خروجی: (code, link, member_count, verified) که verified یعنی «همین الان با
    موفقیت تأیید شد که کاربر عضو نیست»."""
    query = """
        SELECT tracking_code, link, member_count, chat_id FROM requests
        WHERE status = 'in_progress' AND user_id != ?
          AND tracking_code NOT IN (SELECT tracking_code FROM joins WHERE user_id = ? AND left_at IS NULL)
    """
    params = [user_id, user_id]
    if exclude_code:
        query += " AND tracking_code != ?"
        params.append(exclude_code)
    query += " ORDER BY RANDOM()"
    with get_db() as c:
        rows = c.execute(query, params).fetchall()

    done_keys = user_channel_keys(user_id)  # کانالی که قبلاً پاداشش را گرفته، دیگر نمایش داده نمی‌شود
    seen_keys = set()
    for code, link, member_count, chat_id_num in rows:
        key = chan_key(chat_id_num, link)
        if key in done_keys or key in seen_keys:
            continue  # یک کانال فقط یک بار (حتی اگر چند سفارش داشته باشد)
        seen_keys.add(key)
        chat_ident = resolve_chat_ident(chat_id_num, link)
        verified = False
        if chat_ident:
            res = tg("getChatMember", chat_id=chat_ident, user_id=user_id)
            if res.get("ok"):
                if res["result"].get("status") not in ("left", "kicked"):
                    continue  # کاربر همین الان هم عضو این کانال است؛ نشانش نده
                verified = True  # همین الان تأیید شد که عضو نیست
            elif bot_admin_state(chat_ident) is False:
                cancel_request_not_admin(code, "pick")
                continue  # ربات دیگر ادمین نیست: سفارش بی‌صدا لغو و از لیست برداشته شد
        return (code, link, member_count, verified)
    return None


def start_jfj_browsing(chat_id, user_id):
    """این تابع باید همیشه هر دو پیام را کامل بفرستد؛ هر خطای احتمالی در جست‌وجو
    قورت داده می‌شود تا پیام دوم (نتیجه/جست‌وجو) هیچ‌وقت جا نیفتد."""
    send(chat_id, JFJ_WELCOME_TEXT)
    try:
        candidate = pick_jfj_candidate(user_id)
    except Exception:
        logging.exception("pick_jfj_candidate failed for user %s", user_id)
        candidate = None
    if not candidate:
        clear_state(user_id)
        send(chat_id, JFJ_SEARCHING_TEXT)
        return
    code, link, _, verified = candidate
    set_state(user_id, "jfj_browsing", {"code": code, "verified": verified})
    send(chat_id, jfj_found_text(link), jfj_browse_keyboard())


def advance_jfj(user_id, chat_id, message_id, exclude_code=None):
    try:
        candidate = pick_jfj_candidate(user_id, exclude_code)
    except Exception:
        logging.exception("pick_jfj_candidate failed for user %s", user_id)
        candidate = None
    if not candidate:
        clear_state(user_id)
        edit(chat_id, message_id, JFJ_SEARCHING_TEXT, {"inline_keyboard": []})
        return
    code, link, _, verified = candidate
    set_state(user_id, "jfj_browsing", {"code": code, "verified": verified})
    edit(chat_id, message_id, jfj_found_text(link), jfj_browse_keyboard())


def handle_jfj_join(cq):
    user = cq["from"]
    chat_id = cq["message"]["chat"]["id"]
    message_id = cq["message"]["message_id"]

    state, data = get_state(user["id"])
    code = data.get("code") if state == "jfj_browsing" else None
    if not code:
        answer_callback(cq["id"])
        return
    verified_not_member = data.get("verified", False)

    with get_db() as c:
        row = c.execute(
            "SELECT link, member_count, user_id, chat_id FROM requests WHERE tracking_code=?", (code,)
        ).fetchone()
    if not row:
        clear_state(user["id"])
        answer_callback(cq["id"])
        return
    link, member_count, owner_id, chat_id_num = row

    chat_ident = resolve_chat_ident(chat_id_num, link)
    joined = False
    check_failed = None
    if chat_ident:
        res = {}
        for _try in range(3):
            res = tg("getChatMember", chat_id=chat_ident, user_id=user["id"], _timeout=15)
            if res.get("ok"):
                break
            time.sleep(1.0 + _try)
        if res.get("ok"):
            joined = res["result"].get("status") not in ("left", "kicked")
            if not joined:
                logging.info("jfj join: user %s status=%s in %s", user["id"], res["result"].get("status"), chat_ident)
        else:
            check_failed = res.get("description") or res.get("error_description") or res.get("error") or "no response"
            logging.warning("jfj join check failed for %s: %s", chat_ident, check_failed)
    else:
        check_failed = "آیدی/لینک کانال قابل استفاده نیست (کانال خصوصی؟)"

    if check_failed:
        _cf = str(check_failed).lower()
        _rm = any(x in _cf for x in ("member list is inaccessible", "not enough rights", "chat_admin_required",
                                      "need administrator", "chat not found", "kicked", "forbidden"))
        if _rm or bot_admin_state(chat_ident) is False or not chat_ident:
            cancel_request_not_admin(code, "join")  # بی‌صدا؛ بدون هشدار به کاربر، مستقیم سراغ بعدی
            answer_callback(cq["id"])
            advance_jfj(user["id"], chat_id, message_id, exclude_code=code)
            return
        msg = "⚠️ بررسی عضویت الان ممکن نشد؛ چند لحظه بعد دوباره امتحان کن."
        if user["id"] in ADMIN_IDS:
            msg += f"\n\n[ادمین] علت: {str(check_failed)[:150]}"
        answer_callback(cq["id"], msg, show_alert=True)
        return

    if not joined:
        answer_callback(cq["id"], "🛑 هنوز در کانال مورد نظر عضو نشدید!", show_alert=True)
        return

    with get_db() as c:
        already = c.execute(
            "SELECT 1 FROM joins WHERE user_id=? AND tracking_code=? AND left_at IS NULL", (user["id"], code)
        ).fetchone()

    # اگر قبلاً برای همین سفارش پاداش گرفته (کلیک دوباره)، یا هیچ‌وقت تأیید نشده بود که
    # واقعاً «تازه» عضو شده (یعنی احتمالاً از قبل عضو بوده)، پاداشی داده نمی‌شود.
    if not already and chan_key(chat_id_num, link) in user_channel_keys(user["id"], exclude_code=code):
        already = True  # برای همین کانال (در سفارش دیگر) قبلاً پاداش گرفته
    if already or not verified_not_member:
        answer_callback(cq["id"], "⚠️ شما از قبل عضو بودید!", show_alert=True)
        advance_jfj(user["id"], chat_id, message_id, exclude_code=code)
        return

    if not record_join(user["id"], code):
        answer_callback(cq["id"], "⚠️ شما از قبل عضو بودید!", show_alert=True)
        advance_jfj(user["id"], chat_id, message_id, exclude_code=code)
        return

    add_tokens(user["id"], JOIN_REWARD)
    add_activity_tokens(user["id"], JOIN_REWARD)
    maybe_reward_referrer(user["id"])
    refresh_request_status(code, member_count, "in_progress", owner_id=owner_id)
    answer_callback(cq["id"], f"✅️ عضویت شما تایید شد.\n💎 شما {JOIN_REWARD} شاهی دریافت کردید!", show_alert=False)

    advance_jfj(user["id"], chat_id, message_id, exclude_code=code)


def handle_jfj_next(cq):
    user = cq["from"]
    chat_id = cq["message"]["chat"]["id"]
    message_id = cq["message"]["message_id"]

    state, data = get_state(user["id"])
    current_code = data.get("code") if state == "jfj_browsing" else None
    answer_callback(cq["id"])
    advance_jfj(user["id"], chat_id, message_id, exclude_code=current_code)


def invoice_text(product_name, amount, code, expire_dt=None):
    """expire_dt=None یعنی خط اعتبار تراکنش نمایش داده نمی‌شود (مثل خرید شاهی و
    اسپانسری)؛ اگر جایی خواستید این خط را نشان بدهید، expire_dt را پاس بدهید."""
    expiry_line = f"⏰️ *اعتبار تراکنش: تا {fa_digits(expire_dt.strftime('%H:%M'))}*\n\n" if expire_dt else ""
    return (
        f"🧾 *فاکتور خرید • {product_name}*\n\n"
        f"💰 *مبلغ قابل پرداخت: {amount} تومان*\n"
        f"🔍 *کد پیگیری فاکتور: {code}*\n"
        f"{stamp('زمان صدور فاکتور')}\n\n"
        "💳 *شماره کارت:*\n"
        f"`{CARD_NUMBER}`\n"
        f"👤 *به نام: {CARD_HOLDER}*\n\n"
        "⚠️ *نکته مهم:*\n"
        "۱. این مبلغ مخصوص خودِ شماست، پس مبلغ واریزی باید دقیقاً مطابق همین عدد باشد. "
        "حتی ۱ تومان کمتر یا بیشتر، باعث رد شدن خودکار پرداخت خواهد شد.\n"
        "۲. این تراکنش به مدت ۳۰ دقیقه (نیم ساعت) اعتبار دارد و پس از آن امکان پرداخت این تراکنش وجود نخواهد داشت.\n\n"
        f"{expiry_line}"
        "🛑 *لطفا پس از واریزتون روی پرداخت کردم کلیک کنین!*"
    )


def invoice_keyboard(code, amount, paid_callback):
    return {
        "inline_keyboard": [
            [
                {"text": "کپی شماره کارت 💳", "copy_text": {"text": CARD_NUMBER}},
                {"text": "کپی مبلغ💰", "copy_text": {"text": str(amount)}},
            ],
            [btn_inline("پرداخت کردم ✅️", paid_callback, SUCCESS)],
        ]
    }



def handle_invoice_paid(cq):
    """مشترک بین همه‌ی نوع فاکتورها (شاهی / اسپانسری)"""
    code = cq["data"].split(":", 1)[1]
    invoice = get_invoice(code)
    if not invoice or invoice[4] != "pending":
        answer_callback(cq["id"], "🔔 این تراکنش دیگر معتبر نیست.", show_alert=True)
        return
    set_invoice_status(code, "awaiting_receipt", expected_status="pending")
    answer_callback(cq["id"])
    chat_id = cq["message"]["chat"]["id"]
    with get_db() as c:
        meth = c.execute("SELECT method FROM invoices WHERE code=?", (code,)).fetchone()
    if (meth[0] if meth else None) in (None, "", "card"):
        # برای امنیت: پیام فاکتور که شماره کارت دارد پاک می‌شود و فقط خلاصه‌ی بدون شماره کارت می‌ماند
        tg("deleteMessage", chat_id=chat_id, message_id=cq["message"]["message_id"])
        send(chat_id, f"🧾 *فاکتور {code}*\n💰 *مبلغ: {invoice[3]} تومان*\n{stamp('زمان ثبت پرداخت')}\n\n"
                      "🔒 *برای امنیت شما، پیام حاوی شماره کارت پاک شد.*\n\n"
                      "🧾 *رسید واریزی را ارسال کنید!*")
        return
    send(chat_id, f"{stamp('زمان ثبت پرداخت')}\n\n🧾 *رسید واریزی را ارسال کنید!*")


# ===================== خرید شاهی =====================
def _jt_btn_label(p):
    final, base, pct = jt_price_info(p)
    bonus = bonus_for(p["tokens"])
    s = f"💎 {fmt_tokens(p['tokens'])} شاهی • {final} تومان"
    if pct:
        s += f" ({pct}٪ تخفیف)"
    if bonus:
        s += f" 🎁+{fmt_tokens(bonus)}"
    return s


def jtoken_keyboard():
    return {
        "inline_keyboard": [
            [btn_inline(_jt_btn_label(p), f"jt_pick:{p['id']}")]
            for p in JTOKEN_PRODUCTS
        ]
    }


def start_jtoken_purchase(chat_id, user_id):
    send(chat_id, "💎 *خرید شاهی*\n\n👇 *چه مقدار می‌خواهید خریداری کنید؟*", jtoken_keyboard())


def handle_jt_pick(cq):
    product_id = cq["data"].split(":", 1)[1]
    product = next((p for p in JTOKEN_PRODUCTS if p["id"] == product_id), None)
    answer_callback(cq["id"])
    if not product:
        return
    pay_start(cq["message"]["chat"]["id"], cq["from"]["id"], "jtoken", product_id, cq["message"]["message_id"])


# ===================== اسپانسری (فعلاً فقط خرید) =====================
SPONSOR_TEXT = (
    "🎗 *تایم اسپانسری خود را انتخاب کنید:*\n\n"
    "🚥 *راهنمایی:*\n"
    "• شما با خریدن اشتراک اسپانسری میتوانید جوین اجباری این ربات را تهیه کنید, میتوانید کانال-گروه‌تون رو "
    "در جوین اجباری ربات ما فعال کنید تا به روند افزایش دنبال کنندگان کانال-گروه شما مفید باشد.\n\n"
    "💟 *نمونه جذب مشتریان:*"
)


def sponsor_keyboard():
    return {
        "inline_keyboard": [
            [btn_inline(f"{p['hours']} ساعت • {p['price']} تومان", f"sp_pick:{p['id']}")]
            for p in SPONSOR_PRODUCTS
        ]
    }


def send_sponsor_menu(chat_id):
    send(chat_id, SPONSOR_TEXT, sponsor_keyboard())


def handle_sp_pick(cq):
    product_id = cq["data"].split(":", 1)[1]
    product = next((p for p in SPONSOR_PRODUCTS if p["id"] == product_id), None)
    answer_callback(cq["id"])
    if not product:
        return
    sponsor_begin(cq["message"]["chat"]["id"], cq["from"]["id"], product_id, cq["message"]["message_id"])


# ===================== خدمات تلگرام (ویو/ممبر/استارز/ری‌اکشن) =====================
REACTION_ORDER_NAME = "ری‌اکشن پست"
PREMIUM_ORDER_NAME = "ری‌اکشن پرمیومی-بوستی پست"

SIMPLE_SERVICES = {
    "views": {
        "item_word": "ویو",
        "order_name": "ویو پست",
        "ask_text": "👁️‍🗨️ *خرید ویو پست*\n\n🔢 *تعداد ویو مورد نظر را وارد کنید.*\n*حداقل سفارش: {min} عدد*",
        "count_line": "👁 *تعداد: {qty} ویو*",
    },
    "members": {
        "item_word": "ممبر",
        "order_name": "ممبر فیک چنل",
        "ask_text": "👥️ *خرید ممبر فیک چنل*\n\n🔢 *تعداد ممبر مورد نظر را وارد کنید.*\n*حداقل سفارش: {min} عدد*",
        "count_line": "👥 *تعداد: {qty} ممبر*",
    },
    "stars": {
        "item_word": "استارز",
        "order_name": "استارز پست",
        "ask_text": "⭐️ *خرید استارز پست*\n\n🔢 *تعداد استارز مورد نظر را وارد کنید.*\n*حداقل سفارش: {min} عدد*",
        "count_line": "⭐ *تعداد: {qty} استارز*",
    },
}

# مشخصات ثابت و مقدارهای «پیش‌فرض» محصولات. حداقل خرید، قیمت، موجود/ناموجود بودن و چیدمان را
# ادمین از پنل مدیریت عوض می‌کند و در دیتابیس ذخیره می‌شود (قیمت = شاهی به ازای هر rate_per عدد).
PRODUCT_DEFS = {
    "views": {"callback": "svc_views", "menu_label": "👁️‍🗨️ ویو پست", "title": "👁️‍🗨️ ویو پست",
              "admin_btn": "👁️‍🗨️ تنظیمات ویو پست", "style": SUCCESS,
              "default_min": 100, "rate_per": 1000, "default_rate": 5},   # ۰٫۰۰۵ شاهی برای هر ویو
    "reaction": {"callback": "svc_reaction", "menu_label": "🎄 ری‌اکشن پست", "title": "🎄 ری‌اکشن پست",
                 "admin_btn": "🎄 تنظیمات ری‌اکشن پست", "style": SUCCESS,
                 "default_min": 10, "rate_per": 10, "default_rate": 0.5},   # ۰٫۰۵ شاهی برای هر ری‌اکشن
    "stars": {"callback": "svc_stars", "menu_label": "⭐️ استارز پست", "title": "⭐️ استارز پست",
              "admin_btn": "⭐️ تنظیمات استارز پست", "style": SUCCESS,
              "default_min": 1, "rate_per": 1, "default_rate": 15},
    "members": {"callback": "svc_members", "menu_label": "👥️ ممبر فیک چنل", "title": "👥️ ممبر فیک چنل",
                "admin_btn": "👥️ تنظیمات ممبر فیک چنل", "style": SUCCESS,
                "default_min": 500, "rate_per": 1000, "default_rate": 80},
    "premium": {"callback": "svc_premium_reaction", "menu_label": "💎 ری‌اکشن پرمیومی-بوستی پست",
                "title": "💎 ری‌اکشن پرمیومی", "admin_btn": "💎 تنظیمات ری‌اکشن پرمیومی-بوستی پست",
                "style": PRIMARY, "default_min": 10, "rate_per": 10, "default_rate": 3},   # ۰٫۳ شاهی برای هر ری‌اکشن پرمیومی
}
PRODUCT_ORDER = ["views", "reaction", "stars", "members", "premium"]  # ترتیب ثابت در صفحه‌های ادمین
DEFAULT_LAYOUT = [["reaction", "views"], ["stars", "members"], ["premium"]]
SVC_CALLBACK_KEYS = {d["callback"]: k for k, d in PRODUCT_DEFS.items()}


_OLD_DEFAULT_RATES = {"reaction": 1, "premium": 5}  # پیش‌فرض‌های نسخه‌ی قبل


def seed_products():
    with get_db() as c:
        for key, d in PRODUCT_DEFS.items():
            c.execute(
                "INSERT OR IGNORE INTO products (key, enabled, min_qty, rate_cost) VALUES (?, 1, ?, ?)",
                (key, d["default_min"], d["default_rate"]),
            )
        # یک‌بار: قیمت‌هایی که هنوز روی پیش‌فرض قدیمی‌اند به پیش‌فرض جدید می‌روند (قیمت‌های دست‌کاری‌شده‌ی ادمین دست نمی‌خورند)
        done = c.execute("SELECT 1 FROM settings WHERE key='pricedef_v3'").fetchone()
        if not done:
            for key, old in _OLD_DEFAULT_RATES.items():
                c.execute("UPDATE products SET rate_cost=? WHERE key=? AND rate_cost=?",
                          (PRODUCT_DEFS[key]["default_rate"], key, old))
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('pricedef_v3','1')")


def get_product(key):
    d = PRODUCT_DEFS[key]
    with get_db() as c:
        row = c.execute("SELECT enabled, min_qty, rate_cost FROM products WHERE key=?", (key,)).fetchone()
    enabled, min_qty, rate_cost = row if row else (1, d["default_min"], d["default_rate"])
    return {**d, "key": key, "enabled": bool(enabled), "min_qty": int(min_qty), "rate_cost": float(rate_cost)}


def set_product_field(key, field, value):
    assert field in ("enabled", "min_qty", "rate_cost")
    d = PRODUCT_DEFS[key]
    with get_db() as c:
        c.execute(
            "INSERT OR IGNORE INTO products (key, enabled, min_qty, rate_cost) VALUES (?, 1, ?, ?)",
            (key, d["default_min"], d["default_rate"]),
        )
        c.execute(f"UPDATE products SET {field}=? WHERE key=?", (value, key))


def calc_cost(product, qty):
    return round(qty * product["rate_cost"] / product["rate_per"], 2)


def normalize_layout(layout):
    """چیدمان ذخیره‌شده را اعتبارسنجی می‌کند: هر محصول دقیقاً یک‌بار، بدون ردیف خالی"""
    seen, out = set(), []
    try:
        source = layout if layout else DEFAULT_LAYOUT
        for row in source:
            r = [k for k in row if k in PRODUCT_DEFS and k not in seen]
            seen.update(r)
            if r:
                out.append(r)
    except Exception:
        return [list(r) for r in DEFAULT_LAYOUT]
    missing = [k for k in PRODUCT_ORDER if k not in seen]
    if missing:
        out.append(missing)
    return out


def get_layout():
    with get_db() as c:
        row = c.execute("SELECT value FROM settings WHERE key='product_layout'").fetchone()
    data = None
    if row:
        try:
            data = json.loads(row[0])
        except Exception:
            data = None
    return normalize_layout(data)


def set_layout(layout):
    with get_db() as c:
        c.execute(
            """INSERT INTO settings (key, value) VALUES ('product_layout', ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
            (json.dumps(layout),),
        )


def move_in_layout(layout, key, direction):
    """direction: l/r (چپ/راست در همان ردیف)، u/d (ردیف بالا/پایین). اگر حرکتی ممکن نبود None."""
    layout = [list(r) for r in layout]
    r = next(i for i, row in enumerate(layout) if key in row)
    row = layout[r]
    c = row.index(key)
    if direction == "l":
        if c == 0:
            return None
        row[c - 1], row[c] = row[c], row[c - 1]
    elif direction == "r":
        if c == len(row) - 1:
            return None
        row[c + 1], row[c] = row[c], row[c + 1]
    elif direction == "u":
        if r == 0:
            if len(row) == 1:
                return None
            row.pop(c)
            layout.insert(0, [key])
        else:
            row.pop(c)
            dest = layout[r - 1]
            dest.insert(min(c, len(dest)), key)
            if not row:
                layout.pop(r)
    elif direction == "d":
        if r == len(layout) - 1:
            if len(row) == 1:
                return None
            row.pop(c)
            layout.append([key])
        else:
            row.pop(c)
            dest = layout[r + 1]
            dest.insert(min(c, len(dest)), key)
            if not row:
                layout.pop(r)
    else:
        return None
    return layout


_ASCII_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫", "01234567890123456789.")


def parse_number(text):
    """عدد (حتی با ارقام فارسی/عربی و اعشار) یا None"""
    t = text.strip().translate(_ASCII_DIGITS)
    if re.fullmatch(r"\d+(\.\d+)?", t):
        return float(t)
    return None


REACTION_EMOJIS = [
    "👍", "👎", "❤️", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱", "🤬", "😢", "🎉", "🤩", "🤮",
    "💩", "🙏", "👌", "🕊️", "🤡", "🥱", "🥴", "😍", "🐳", "❤️‍🔥", "🌚", "🌭", "💯", "🤣", "⚡",
    "🍌", "🏆", "💔", "🤨", "😐", "🍓", "🍾", "💋", "🖕", "😈", "😴", "😭", "🤓", "👻", "👨‍💻",
    "👀", "🎃", "🙈", "😇", "😨", "🤝", "✍️", "🤗", "🫡", "🎅", "🎄", "☃️", "💅", "🤪", "🗿",
    "🆒", "💘", "🙉", "🦄", "😘", "💊", "🙊", "😎", "👾", "🤷‍♂️", "🤷", "🤷‍♀️", "😡",
]
REACTION_PAGE_SIZE = 35
REACTION_PICK_TEXT = "🎄 *انتخاب نوع ری‌اکشن پست*\n\n👇 *لطفاً ری‌اکشن مورد نظر را انتخاب کنید:*"


def services_menu_keyboard(uid=None):
    rows = []
    for row in get_layout():
        btns = []
        for key in row:
            p = get_product(key)
            if p["enabled"] or (uid and user_has_product(uid, key)):
                btns.append(btn_inline(p["menu_label"], p["callback"], p["style"]))
        if btns:
            rows.append(btns)
    return {"inline_keyboard": rows}


def start_services_menu(chat_id, user_id):
    kb = services_menu_keyboard(user_id)
    if not kb["inline_keyboard"]:
        send(chat_id, "🛑 *در حال حاضر هیچ خدمتی موجود نیست.*")
        return
    send(chat_id, "📱 *خدمات تلگرام*\n\n👇 *لطفاً یکی از خدمات زیر را انتخاب کنید:*", kb)


# ---------- انتخاب ری‌اکشن (صفحه‌بندی‌شده) ----------
def reaction_keyboard(page):
    start = page * REACTION_PAGE_SIZE
    chunk = REACTION_EMOJIS[start:start + REACTION_PAGE_SIZE]
    total_pages = (len(REACTION_EMOJIS) + REACTION_PAGE_SIZE - 1) // REACTION_PAGE_SIZE

    rows = []
    if page == 0:
        rows.append([
            btn_inline("ری‌اکشن ترکیبی مثبت🥳", "react_combo:pos"),
            btn_inline("ری‌اکشن ترکیبی منفی🤮", "react_combo:neg"),
        ])
    for i in range(0, len(chunk), 5):
        rows.append([btn_inline(e, f"react_pick:{e}") for e in chunk[i:i + 5]])

    nav = [btn_inline("قبلی ◁", f"react_page:{page - 1}", SUCCESS)] if page > 0 \
        else [btn_inline("بازگشت ◁", "react_cancel", DANGER)]
    if page < total_pages - 1:
        nav.append(btn_inline("▷ بعدی", f"react_page:{page + 1}", SUCCESS))
    rows.append(nav)
    return {"inline_keyboard": rows}


def handle_svc_reaction_entry(cq):
    chat_id = cq["message"]["chat"]["id"]
    answer_callback(cq["id"])
    send(chat_id, REACTION_PICK_TEXT, reaction_keyboard(0))


def handle_react_page(cq):
    page = int(cq["data"].split(":", 1)[1])
    chat_id = cq["message"]["chat"]["id"]
    message_id = cq["message"]["message_id"]
    answer_callback(cq["id"])
    edit(chat_id, message_id, REACTION_PICK_TEXT, reaction_keyboard(page))


def handle_react_cancel(cq):
    chat_id = cq["message"]["chat"]["id"]
    message_id = cq["message"]["message_id"]
    answer_callback(cq["id"])
    edit(chat_id, message_id, "📱 *خدمات تلگرام*\n\n👇 *لطفاً یکی از خدمات زیر را انتخاب کنید:*", services_menu_keyboard(cq["from"]["id"]))


def handle_react_select(cq, chosen_label):
    user = cq["from"]
    chat_id = cq["message"]["chat"]["id"]
    set_state(user["id"], "react_wait_qty", {"emoji": chosen_label})
    answer_callback(cq["id"])
    send(
        chat_id,
        "🎄 *خرید ری‌اکشن پست*\n\n🔢 *تعداد ری‌اکشن مورد نظر را وارد کنید.*\n"
        f"*حداقل سفارش: {get_product('reaction')['min_qty']} عدد*",
        back_menu(),
    )


def handle_react_pick(cq):
    handle_react_select(cq, cq["data"].split(":", 1)[1])


def handle_react_combo(cq):
    kind = cq["data"].split(":", 1)[1]
    label = "ری‌اکشن ترکیبی مثبت🥳" if kind == "pos" else "ری‌اکشن ترکیبی منفی🤮"
    handle_react_select(cq, label)


def handle_react_wait_qty(chat_id, user_id, text, data):
    if not text.isdigit():
        send(chat_id, "❗️ *فقط عدد ارسال کنید.*")
        return
    qty = int(text)
    p = get_product("reaction")
    if qty < p["min_qty"]:
        send(chat_id, f"🛑 *حداقل سفارش {p['min_qty']} عدد است.*")
        return
    cost = calc_cost(p, qty)
    emoji = data["emoji"]
    set_state(user_id, "svc_wait_link", {"order_name": REACTION_ORDER_NAME, "qty": qty, "cost": cost, "emoji": emoji})
    send(
        chat_id,
        f"🎄 *ری‌اکشن انتخاب شد:* {emoji}\n\n"
        f"🔢 *تعداد: {qty} ری‌اکشن*\n"
        f"🪙 *هزینه: {fmt_tokens(cost)} شاهی*\n\n"
        "🔗 *حالا لینک پست مورد نظر رو ارسال کنید.*",
    )


# ---------- ری‌اکشن پرمیومی-بوستی (بدون انتخاب ایموجی) ----------
def handle_svc_premium_entry(cq):
    user = cq["from"]
    chat_id = cq["message"]["chat"]["id"]
    answer_callback(cq["id"])
    set_state(user["id"], "premium_wait_qty")
    send(
        chat_id,
        "💎 *خرید ری‌اکشن پرمیومی-بوستی پست*\n\n🔢 *تعداد ری‌اکشن پرمیومی مورد نظر را وارد کنید.*\n"
        f"*حداقل سفارش: {get_product('premium')['min_qty']} عدد*",
        back_menu(),
    )


def handle_premium_wait_qty(chat_id, user_id, text):
    if not text.isdigit():
        send(chat_id, "❗️ *فقط عدد ارسال کنید.*")
        return
    qty = int(text)
    p = get_product("premium")
    if qty < p["min_qty"]:
        send(chat_id, f"🛑 *حداقل سفارش {p['min_qty']} عدد است.*")
        return
    cost = calc_cost(p, qty)
    set_state(user_id, "svc_wait_link", {"order_name": PREMIUM_ORDER_NAME, "qty": qty, "cost": cost})
    send(
        chat_id,
        f"💎 *تعداد: {qty} ری‌اکشن پرمیومی*\n"
        f"🪙 *هزینه: {fmt_tokens(cost)} شاهی*\n\n"
        "🔗 *حالا لینک پست موردنظر رو ارسال کنید.*",
    )


# ---------- ویو/ممبر/استارز (یکسان، فقط نرخ و حداقل فرق دارد) ----------
def start_simple_service(chat_id, user_id, service_key):
    svc = SIMPLE_SERVICES[service_key]
    set_state(user_id, "svc_wait_qty", {"service": service_key})
    send(chat_id, svc["ask_text"].format(min=get_product(service_key)["min_qty"]), back_menu())


def handle_svc_simple_start(cq):
    key = cq["data"][len("svc_"):]
    user = cq["from"]
    chat_id = cq["message"]["chat"]["id"]
    answer_callback(cq["id"])
    start_simple_service(chat_id, user["id"], key)


def handle_svc_wait_qty(chat_id, user_id, text, data):
    svc = SIMPLE_SERVICES[data["service"]]
    p = get_product(data["service"])
    if not text.isdigit():
        send(chat_id, "❗️ *فقط عدد ارسال کنید.*")
        return
    qty = int(text)
    if qty < p["min_qty"]:
        send(chat_id, f"🛑 *حداقل سفارش {p['min_qty']} عدد است.*")
        return
    cost = calc_cost(p, qty)
    set_state(user_id, "svc_wait_link", {"order_name": svc["order_name"], "qty": qty, "cost": cost})
    send(
        chat_id,
        f"✅ *تعداد {svc['item_word']} دریافت شد.*\n\n"
        f"{svc['count_line'].format(qty=qty)}\n"
        f"🪙 *هزینه: {fmt_tokens(cost)} شاهی*\n\n"
        "🔗 *حالا لینک پست مورد نظر رو ارسال کنید.*",
    )


# ---------- قدم مشترک نهایی: دریافت لینک و ثبت سفارش (ویو/ممبر/استارز/ری‌اکشن/پرمیومی) ----------
def handle_svc_wait_link(chat_id, user_id, text, data):
    low = text.lower()
    if not (low.startswith("http://") or low.startswith("https://")):
        send(chat_id, "🛑 *لطفا لینک پست را به‌صورت صحیح (با http یا https) ارسال کنید.*")
        return

    order_name, qty, cost = data["order_name"], data["qty"], data["cost"]
    emoji = data.get("emoji")

    if get_balance(user_id) < cost or not deduct_tokens(user_id, cost):
        send(
            chat_id,
            f"🛑 *سکه کافی ندارید.*\n\n🪙 *هزینه سفارش: {fmt_tokens(cost)}*\n🏦 *موجودی شما: {fmt_tokens(get_balance(user_id))}*",
            {"inline_keyboard": [[btn_inline("🛍 خرید شاهی", "svc_buy_jtoken", SUCCESS)]]},
        )
        return

    code = generate_service_order_code()
    create_service_order(user_id, order_name, qty, cost, text, code, extra=emoji)
    notify_admins_service_order(code)
    clear_state(user_id)
    date_str, time_str = jalali_now_strings()
    send(
        chat_id,
        f"🚀 *سفارش {order_name} شما #ثبت شد.*\n\n"
        f"🔍 *کد پیگیری: {code}*\n"
        f"⏰️ *زمان ثبت: {time_str} - {date_str}*",
        main_menu(user_id),
    )



# ===================== سفارش خدمات و فاکتورها: اطلاع‌رسانی و تأیید ادمین =====================
def _user_label(user_id):
    with get_db() as c:
        r = c.execute("SELECT first_name, username FROM users WHERE id=?", (user_id,)).fetchone()
    name = ((r[0] if r else "") or "کاربر").strip()
    un = f"@{r[1]}" if r and r[1] else "بدون یوزرنیم"
    return f"{name} ({un}) • آیدی عددی: {user_id}"


def _admin_buttons(ok_cb, no_cb, ok_text="✅ تکمیل", no_text="❌ لغو"):
    return {"inline_keyboard": [[btn_inline(ok_text, ok_cb, SUCCESS), btn_inline(no_text, no_cb, DANGER)]]}


def _user_brief(user_id):
    """خلاصه‌ی کامل کاربر برای ادمین: نام، یوزرنیم، آیدی، شماره، موجودی، سابقه"""
    with get_db() as c:
        u = c.execute("SELECT first_name, username, tokens, created_at, phone FROM users WHERE id=?", (user_id,)).fetchone()
        n_all = c.execute("SELECT COUNT(*) FROM service_orders WHERE user_id=?", (user_id,)).fetchone()[0]
        spent = c.execute("SELECT COALESCE(SUM(final_amount),0) FROM invoices WHERE buyer_id=? AND status='paid'", (user_id,)).fetchone()[0]
    if not u:
        return [f"👤 کاربر: {user_id}"]
    name = (u[0] or "کاربر").strip()
    lines = [f"👤 نام: {name}",
             f"🆔 یوزرنیم: {'@' + u[1] if u[1] else 'ندارد'}",
             f"🔢 آیدی عددی: {user_id}"]
    if u[4]:
        lines.append(f"📱 شماره: {u[4]}")
    lines += [f"🪙 موجودی فعلی: {fmt_tokens(u[2])} شاهی",
              f"📅 عضویت: {_fa_dt(u[3])}",
              f"🛒 تعداد سفارش‌های خدمات: {n_all} • مجموع خرید: {fmt_num(spent)} تومان"]
    return lines


def _invoice_detail_lines(code):
    """جزئیات فاکتور برای ادمین: قیمت پایه، تخفیف، کد تخفیف، بونوس، مشخصات اسپانسری"""
    try:
        with get_db() as c:
            r = c.execute("SELECT kind, base_price, final_amount, meta, created_at FROM invoices WHERE code=?", (code,)).fetchone()
        if not r:
            return []
        kind, base, final, meta, created = r
        meta = json.loads(meta or "{}") if meta else {}
        out = []
        if kind == "jtoken":
            out.append(f"🪙 شاهی خریداری‌شده: {fmt_tokens(meta.get('tokens', 0))}")
            if meta.get("bonus"):
                out.append(f"🎁 بونوس: +{fmt_tokens(meta['bonus'])} شاهی (جمعاً {fmt_tokens(meta.get('tokens', 0) + meta['bonus'])})")
        elif kind == "sponsor":
            out.append(f"🎗 مدت اسپانسری: {meta.get('hours', '—')} ساعت")
            out.append(_sponsor_info_text(meta.get("si") or {}))
        if base and base != final:
            out.append(f"🏷 قیمت پایه: {fmt_num(base)} تومان ← پرداختی: {fmt_num(final)} تومان")
        if meta.get("dc"):
            out.append(f"🏷 کد تخفیف: {meta['dc']}")
        if created:
            out.append(f"⏰ ساخت فاکتور: {_fa_dt(created)}")
        return out
    except Exception:
        return []


def notify_admins_service_order(code):
    """سفارش جدید خدمات (سین/ممبر/ری‌اکشن/پرمیومی) را کامل و با دکمه‌های تکمیل/لغو برای ادمین‌ها می‌فرستد.
    اگر هیچ ادمینی پیام را دریافت نکند، ستون admin_notified صفر می‌ماند و invoice_watcher دوباره تلاش می‌کند."""
    try:
        with get_db() as c:
            row = c.execute(
                "SELECT user_id, service, quantity, extra, token_cost, link, created_at, status FROM service_orders WHERE tracking_code=?",
                (code,),
            ).fetchone()
        if not row:
            return False
        user_id, service, qty, extra, cost, link, created, status = row
        date_str, time_str = jalali_now_strings()
        unit = (cost / qty) if qty else 0
        lines = [
            "🛒 سفارش جدید خدمات — منتظر تحویل",
            "━━━━━━━━━━━━━━",
            f"🔍 کد پیگیری: {code}",
            f"📦 سرویس: {service}",
            f"🔢 تعداد: {qty}",
        ]
        if extra:
            lines.append(f"😀 ری‌اکشن انتخابی: {extra}")
        lines += [
            f"🔗 لینک:\n{link}",
            f"🪙 هزینه‌ی سفارش: {fmt_tokens(cost)} شاهی (قیمت هر واحد: {fmt_tokens(round(unit, 4))})",
            "ℹ️ هزینه از موجودی کاربر کسر شده است.",
            f"⏰ زمان ثبت: {_fa_dt(created) if created else time_str + ' - ' + date_str}",
            "━━━━━━━━━━━━━━",
        ] + _user_brief(user_id) + [
            "━━━━━━━━━━━━━━",
            "بعد از انجام سفارش «تکمیل» را بزن (کاربر خبردار می‌شود). با «لغو» سفارش کنسل و موجودی به کاربر برگردانده می‌شود.",
        ]
        kb = {"inline_keyboard": [
            [btn_inline("✅ تکمیل سفارش", f"adm_so_ok:{code}", SUCCESS), btn_inline("❌ لغو و بازگشت موجودی", f"adm_so_no:{code}", DANGER)],
            [btn_inline("👤 کارت کاربر", f"adm_p:u:card:{user_id}", PRIMARY), btn_inline("✉️ پیام به کاربر", f"adm_p:u:dm:{user_id}", PRIMARY)],
        ]}
        ok_any = False
        for admin_id in ADMIN_IDS:
            r = send(admin_id, "\n".join(lines), kb, markdown=False)
            ok_any = ok_any or bool(isinstance(r, dict) and r.get("ok"))
        if ok_any:
            with get_db() as c:
                c.execute("UPDATE service_orders SET admin_notified=1 WHERE tracking_code=?", (code,))
        else:
            logging.warning("service order %s was not delivered to any admin (will retry)", code)
        return ok_any
    except Exception:
        logging.exception("notify_admins_service_order failed")
        return False


def retry_unnotified_orders():
    with get_db() as c:
        codes = [r[0] for r in c.execute(
            "SELECT tracking_code FROM service_orders WHERE admin_notified=0 AND status='pending' "
            "AND created_at >= datetime('now','-3 day') ORDER BY created_at LIMIT 20").fetchall()]
    for code in codes:
        notify_admins_service_order(code)


def handle_admin_service_order(cq, code, ok):
    admin = cq["from"]
    chat_id = cq["message"]["chat"]["id"]
    message_id = cq["message"]["message_id"]
    new_status = "completed" if ok else "cancelled"
    with get_db() as c:
        row = c.execute(
            "SELECT user_id, service, token_cost FROM service_orders WHERE tracking_code=?", (code,)
        ).fetchone()
        cur = c.execute(
            "UPDATE service_orders SET status=? WHERE tracking_code=? AND status='pending'", (new_status, code)
        ) if row else None
        changed = bool(cur and cur.rowcount == 1)
        if changed and not ok:
            c.execute("UPDATE users SET tokens = tokens + ? WHERE id=?", (row[2], row[0]))
    if not row:
        answer_callback(cq["id"], "سفارش پیدا نشد.", show_alert=True)
        return
    if not changed:
        answer_callback(cq["id"], "این سفارش قبلاً بررسی شده است.", show_alert=True)
        edit(chat_id, message_id, (cq["message"].get("text") or "") + "\n\n(قبلاً بررسی شده)", {"inline_keyboard": []}, markdown=False)
        return
    user_id, service, cost = row
    who = admin.get("first_name") or "ادمین"
    verdict = "✅ تکمیل شد" if ok else f"❌ لغو شد • {fmt_tokens(cost)} شاهی به کاربر برگشت"
    edit(chat_id, message_id, (cq["message"].get("text") or "") + f"\n\n{verdict}\nتوسط: {who}",
         {"inline_keyboard": []}, markdown=False)
    answer_callback(cq["id"], "انجام شد.")
    rep_ev_service_result(code, ok, who)
    if ok:
        send(user_id, f"✅ *سفارش {service} شما به کد پیگیری {code} تکمیل شد.*\n{stamp('زمان تکمیل')}")
    else:
        send(user_id, f"❌ *سفارش {service} شما به کد پیگیری {code} لغو شد.*\n{stamp('زمان لغو')}\n\n"
                      f"🪙 *{fmt_tokens(cost)} شاهی به حساب شما برگشت.*")


def handle_receipt(message):
    """رسید واریزی (عکس/فایل) بعد از «پرداخت کردم»: برای ادمین‌ها با دکمه‌های تأیید/رد فوروارد می‌شود"""
    user = message["from"]
    chat_id = message["chat"]["id"]
    with get_db() as c:
        inv = c.execute(
            "SELECT code, product_name, final_amount, method FROM invoices WHERE buyer_id=? AND status='awaiting_receipt' "
            "ORDER BY created_at DESC LIMIT 1", (user["id"],)).fetchone()
    if not inv:
        return False
    code, product, amount, method = inv
    txt = (message.get("text") or "").strip()
    if not (message.get("photo") or message.get("document")) and not (method == "crypto" and len(txt) >= 20 and " " not in txt):
        return False  # متن فقط برای رسید ارزی (هش تراکنش) پذیرفته می‌شود
    if not set_invoice_status(code, "review", expected_status="awaiting_receipt"):
        return False
    with get_db() as c:
        c.execute("UPDATE invoices SET receipt_chat=?, receipt_mid=? WHERE code=?", (chat_id, message["message_id"], code))
    caption = (
        "🧾 رسید جدید برای بررسی\n"
        "━━━━━━━━━━━━━━\n"
        f"🔍 کد فاکتور: {code}\n"
        f"📦 محصول: {product}\n"
        f"💰 مبلغ فاکتور: {amount} تومان\n"
        f"💳 روش پرداخت: {METHOD_LABELS.get(method, 'کارت به کارت')}\n"
        + stamp("زمان دریافت رسید", md=False) + "\n"
        + "\n".join(_invoice_detail_lines(code)) + "\n"
        "━━━━━━━━━━━━━━\n"
        + "\n".join(_user_brief(user["id"])[:6]) + "\n\n"
        "مبلغ واریزی را با فاکتور مقایسه کن و سپس تأیید یا رد کن."
    )[:1020]
    kb = {"inline_keyboard": [
        [btn_inline("✅ تأیید و اعمال", f"adm_inv_ok:{code}", SUCCESS), btn_inline("❌ رد رسید", f"adm_inv_no:{code}", DANGER)],
        [btn_inline("👤 کارت کاربر", f"adm_p:u:card:{user['id']}", PRIMARY), btn_inline("✉️ پیام به کاربر", f"adm_p:u:dm:{user['id']}", PRIMARY)]]}
    sent = False
    for admin_id in ADMIN_IDS:
        r = tg("copyMessage", chat_id=admin_id, from_chat_id=chat_id, message_id=message["message_id"],
               caption=caption, reply_markup=kb)
        sent = sent or bool(r.get("ok"))
    if not sent:
        set_invoice_status(code, "awaiting_receipt", expected_status="review")
        send(chat_id, "⚠️ *ارسال رسید به پشتیبانی انجام نشد؛ لطفاً چند لحظه بعد دوباره رسید را بفرستید.*")
        return True
    rep_ev_receipt(code, user["id"], chat_id, message["message_id"],
                   media=bool(message.get("photo") or message.get("document")), txt=txt)
    send(chat_id, f"✅ *رسید شما دریافت شد.*\n🔍 *کد فاکتور: {code}*\n{stamp('زمان دریافت رسید')}\n\n⏳ *بعد از بررسی ادمین، نتیجه همین‌جا اطلاع داده می‌شود.*")
    return True


def handle_admin_invoice(cq, code, ok):
    admin = cq["from"]
    chat_id = cq["message"]["chat"]["id"]
    message_id = cq["message"]["message_id"]
    inv = get_invoice(code)
    if not inv:
        answer_callback(cq["id"], "فاکتور پیدا نشد.", show_alert=True)
        return
    buyer_id, product = inv[0], inv[2]
    if not set_invoice_status(code, "paid" if ok else "rejected", expected_status="review"):
        answer_callback(cq["id"], "این رسید قبلاً بررسی شده است.", show_alert=True)
        tg("editMessageReplyMarkup", chat_id=chat_id, message_id=message_id, reply_markup={"inline_keyboard": []})
        return
    with get_db() as c:
        kind, meta = c.execute("SELECT kind, meta FROM invoices WHERE code=?", (code,)).fetchone()
    try:
        meta = json.loads(meta or "{}")
    except Exception:
        meta = {}
    who = admin.get("first_name") or "ادمین"
    old = cq["message"].get("caption") or cq["message"].get("text") or ""
    if ok:
        apply_paid_invoice(code)
        verdict = "✅ تأیید شد" + (" • شاهی به حساب کاربر اضافه شد" if kind == "jtoken" else " • اشتراک ساخته شد، منتظر فعال‌سازی" if kind == "sponsor" else "")
    else:
        send(buyer_id, f"❌ *رسید شما برای فاکتور {code} تأیید نشد.*\n{stamp('زمان بررسی')}\n\n☎️ *در صورت اشتباه بودن، به پشتیبانی پیام دهید: {SUPPORT_ID}*")
        verdict = "❌ رد شد"
        dc_release(meta.get("dc"))
    rep_ev_receipt_result(code, ok, who)
    _edit_any(chat_id, message_id, old + f"\n\n{verdict}\nتوسط: {who}")
    answer_callback(cq["id"], "انجام شد.")


def handle_sponsor_channel(chat_id, user, text, data):
    """بعد از تأیید فاکتور اسپانسری، کاربر کانالش را می‌فرستد و برای ادمین‌ها ارسال می‌شود"""
    clear_state(user["id"])
    msg = (
        "🎗 درخواست فعال‌سازی اسپانسری\n\n"
        f"🔍 کد فاکتور: {data.get('code', '')}\n"
        f"📦 محصول: {data.get('product', '')}\n"
        f"🔗 کانال/گروه: {text}\n"
        f"👤 کاربر: {_user_label(user['id'])}"
    )
    for admin_id in ADMIN_IDS:
        send(admin_id, msg, markdown=False)
    send(chat_id, "✅ *اطلاعات کانال شما برای ادمین ارسال شد؛ اسپانسری شما به‌زودی فعال می‌شود.*", main_menu(user["id"]))


# ===================== پنل مدیریت (نسخه‌ی کامل) =====================
import html as _html


def _h(x):
    return _html.escape(str(x), quote=False)


def _n(v):
    """عدد با جداکننده‌ی هزارگان و ارقام فارسی"""
    return fa_digits(fmt_num(v))


def _t(v):
    return fa_digits(fmt_tokens(v))


# ---------- ذخیره‌ی تنظیمات ----------
def get_setting(key, default=None):
    with get_db() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def set_setting(key, value):
    with get_db() as c:
        c.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))


# name: متغیر سراسری، عنوان، نوع، حداقل، ضریب (مقدار ذخیره‌شده = ورودی × ضریب)، واحد
SETTING_DEFS = {
    "tpm":   {"g": "TOKENS_PER_MEMBER", "label": "هزینه‌ی هر ممبر در درخواست JFJ", "kind": "num", "min": 0.01, "mul": 1, "unit": "شاهی", "icon": "💎"},
    "minm":  {"g": "MIN_MEMBER_COUNT", "label": "حداقل تعداد ممبر در هر درخواست", "kind": "int", "min": 1, "mul": 1, "unit": "ممبر", "icon": "🔢"},
    "jr":    {"g": "JOIN_REWARD", "label": "پاداش هر جوین موفق (جریمه‌ی لفت هم همین‌قدر است)", "kind": "num", "min": 0.01, "mul": 1, "unit": "شاهی", "icon": "🎁"},
    "lrf":   {"g": "LEAVE_REFUND_TO_OWNER", "label": "بازگشت به صاحب سفارش وقتی ممبر لفت می‌دهد", "kind": "num", "min": 0, "mul": 1, "unit": "شاهی", "icon": "↩️"},
    "cool":  {"g": "RESUBMIT_COOLDOWN_SECONDS", "label": "فاصله‌ی دو درخواست برای یک کانال", "kind": "int", "min": 0, "mul": 60, "unit": "دقیقه", "icon": "⏱"},
    "start": {"g": "STARTING_TOKENS", "label": "موجودی اولیه‌ی کاربر جدید", "kind": "num", "min": 0, "mul": 1, "unit": "شاهی", "icon": "🪙"},
    "rr":    {"g": "REFERRAL_REWARD", "label": "پاداش معرف", "kind": "num", "min": 0, "mul": 1, "unit": "شاهی", "icon": "🎁"},
    "rt":    {"g": "REFERRAL_ACTIVITY_THRESHOLD", "label": "فعالیت لازم زیرمجموعه تا معرف پاداش بگیرد", "kind": "int", "min": 1, "mul": 1, "unit": "شاهی", "icon": "🎯"},
    "mt":    {"g": "MIN_TRANSFER_AMOUNT", "label": "حداقل انتقال در بانک انتقال", "kind": "int", "min": 1, "mul": 1, "unit": "شاهی", "icon": "🔁"},
    "inv":   {"g": "INVOICE_VALIDITY_MINUTES", "label": "مدت اعتبار فاکتور", "kind": "int", "min": 5, "mul": 1, "unit": "دقیقه", "icon": "⏱"},
}
TEXT_DEFS = {
    "card":   {"g": "CARD_NUMBER", "label": "شماره کارت"},
    "holder": {"g": "CARD_HOLDER", "label": "نام صاحب کارت"},
    "support": {"g": "SUPPORT_ID", "label": "آیدی پشتیبانی"},
}
_settings_ts = [0.0]


def apply_settings(force=True):
    """تنظیمات ذخیره‌شده‌ی ادمین را روی متغیرهای سراسری ربات اعمال می‌کند (در مینی‌اپ هم صدا زده می‌شود)"""
    if not force and time.time() - _settings_ts[0] < 5:
        return
    _settings_ts[0] = time.time()
    g = globals()
    for name, d in SETTING_DEFS.items():
        raw = get_setting("cfg_" + name)
        if raw is None:
            continue
        try:
            v = float(raw)
            g[d["g"]] = int(v) if (d["kind"] == "int" or v == int(v)) else v
        except ValueError:
            pass
    for name, d in TEXT_DEFS.items():
        raw = get_setting("cfg_" + name)
        if raw:
            g[d["g"]] = raw
    for key, gname in (("jtoken_products", "JTOKEN_PRODUCTS"), ("sponsor_products", "SPONSOR_PRODUCTS")):
        raw = get_setting(key)
        if raw:
            try:
                lst = json.loads(raw)
                if isinstance(lst, list) and lst:
                    g[gname] = lst
            except ValueError:
                pass


def _cfg_value(name):
    d = SETTING_DEFS[name]
    return globals()[d["g"]] / d["mul"]


def is_banned(user_id):
    try:
        with get_db() as c:
            r = c.execute("SELECT banned FROM users WHERE id=?", (user_id,)).fetchone()
        return bool(r and r[0])
    except sqlite3.OperationalError:
        return False


def gate_blocked(user_id, chat_id, callback_id=None):
    """ربات خاموش یا کاربر مسدود: به غیر از ادمین‌ها همه را متوقف می‌کند"""
    if is_admin(user_id):
        return False
    if get_setting("bot_enabled", "1") == "0":
        msg = "🛠 ربات موقتاً در حال بروزرسانی است. کمی بعد دوباره تلاش کنید."
    elif is_banned(user_id):
        msg = "🚫 دسترسی شما به ربات مسدود شده است."
    else:
        return False
    if callback_id:
        answer_callback(callback_id, msg, show_alert=True)
    elif chat_id:
        send(chat_id, msg, markdown=False)
    return True


# ---------- ابزار پیام‌ها ----------
def _ab(text, cb, style=None):
    return btn_inline(text, cb, style)


def _kb(*rows):
    return {"inline_keyboard": [r for r in rows if r]}


def _hsend(chat_id, text, kb=None):
    p = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if kb:
        p["reply_markup"] = kb
    return tg("sendMessage", **p)


def _hedit(chat_id, message_id, text, kb=None):
    p = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML",
         "disable_web_page_preview": True, "reply_markup": kb or {"inline_keyboard": []}}
    return tg("editMessageText", **p)


def _edit_any(chat_id, message_id, text):
    """پیام ادمین یا عکس/فایل است (کپشن) یا متن؛ هر کدام را ویرایش می‌کند و دکمه‌ها را برمی‌دارد"""
    empty = {"inline_keyboard": []}
    r = tg("editMessageCaption", chat_id=chat_id, message_id=message_id, caption=text[:1000], reply_markup=empty)
    if not r.get("ok"):
        tg("editMessageText", chat_id=chat_id, message_id=message_id, text=text[:4000], reply_markup=empty)


def _fa_dt(utc_str):
    try:
        dt = datetime.strptime(utc_str[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).astimezone(ZoneInfo(TIMEZONE))
    except Exception:
        return "—"
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    return fa_digits(f"{jy:04d}/{jm:02d}/{jd:02d} {dt.strftime('%H:%M')}")


def _label(user_id):
    with get_db() as c:
        r = c.execute("SELECT first_name, username FROM users WHERE id=?", (user_id,)).fetchone()
    name = ((r[0] if r else "") or "کاربر").strip()
    un = f"@{r[1]}" if r and r[1] else "بدون یوزرنیم"
    return f"{_h(name)} ({_h(un)}) • <code>{user_id}</code>"


def _q1(sql, args=()):
    with get_db() as c:
        r = c.execute(sql, args).fetchone()
    return r[0] if r and r[0] is not None else 0


LINE = "━━━━━━━━━━━━━━"


# ---------- منوی پایین پنل ----------
ADMIN_SECTION_BTNS = {
    "⚙️ تنظیمات عمومی": "g",
    "☎️ بخش پشتیبانی": "s",
    "🏦 مالی": "f",
    "👤 مدیریت کاربر": "u",
    "🎗 تنظیمات اسپانسر": "p",
    "👥️ تنظیمات زیرمجموعه": "r",
    "🛍 تنظیمات خرید شاهی": "j",
    "🧰 تنظیمات درخواست JFJ": "q",
    "🧾 سفارشات تکمیل نشده": "o",
}
_SEC_BY_KEY = {v: k for k, v in ADMIN_SECTION_BTNS.items()}


def admin_panel_menu():
    b = list(ADMIN_SECTION_BTNS)
    return {
        "keyboard": [
            [btn(BTN_ADMIN_STATS)],
            [btn(BTN_ADMIN_PRODUCTS), btn(b[0])],
            [btn(b[1])],
            [btn(b[2]), btn(b[3])],
            [btn(b[4]), btn(b[5])],
            [btn(b[6]), btn(b[7])],
            [btn(b[8])],
            [btn(BACK_BTN)],
        ],
        "resize_keyboard": True,
        "is_persistent": False,
    }


ADMIN_SECTION_BTNS_ALL = set(ADMIN_SECTION_BTNS)


def admin_dashboard(chat_id):
    now = now_local()
    today = _utc_str(now.replace(hour=0, minute=0, second=0, microsecond=0))
    users = _q1("SELECT COUNT(*) FROM users")
    new_today = _q1("SELECT COUNT(*) FROM users WHERE created_at >= ?", (today,))
    sales = _q1("SELECT COALESCE(SUM(final_amount),0) FROM invoices WHERE status='paid' AND created_at >= ?", (today,))
    pend_so = _q1("SELECT COUNT(*) FROM service_orders WHERE status='pending'")
    pend_inv = _q1("SELECT COUNT(*) FROM invoices WHERE status='review'")
    active_req = _q1("SELECT COUNT(*) FROM requests WHERE status NOT IN ('completed','cancelled','removed','deleted','relinked')")
    on = get_setting("bot_enabled", "1") != "0"
    text = (
        "🖌 <b>پنل مدیریت</b>\n"
        f"{LINE}\n"
        f"🤖 وضعیت ربات: {'🟢 فعال' if on else '🔴 خاموش'}\n"
        f"👥 کاربران: <b>{_n(users)}</b> (امروز <b>{_n(new_today)}</b> نفر جدید)\n"
        f"💰 فروش امروز: <b>{_n(sales)}</b> تومان\n"
        f"{LINE}\n"
        f"🛒 سفارش خدمات در انتظار: <b>{_n(pend_so)}</b>\n"
        f"🧾 رسید در انتظار بررسی: <b>{_n(pend_inv)}</b>\n"
        f"📋 درخواست JFJ در حال انجام: <b>{_n(active_req)}</b>\n\n"
        "👇 <i>یکی از بخش‌های پایین را انتخاب کنید.</i>"
    )
    p = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "reply_markup": admin_panel_menu()}
    tg("sendMessage", **p)


# ---------- صفحه‌ی هر بخش ----------
def _back(sec, text="🔙 بازگشت به منو"):
    return [_ab(text, f"adm_p:{sec}:home")]


def render_general():
    on = get_setting("bot_enabled", "1") != "0"
    fj = len(fj_entries())
    text = (
        "⚙️ <b>تنظیمات عمومی</b>\n"
        f"{LINE}\n"
        f"🤖 وضعیت ربات: {'🟢 فعال' if on else '🔴 خاموش (فقط ادمین‌ها کار می‌کنند)'}\n"
        f"☎️ آیدی پشتیبانی: <code>{_h(SUPPORT_ID)}</code>\n"
        f"🔁 حداقل انتقال در بانک: <b>{_t(MIN_TRANSFER_AMOUNT)}</b> شاهی\n"
        f"🪙 موجودی اولیه‌ی کاربر جدید: <b>{_t(STARTING_TOKENS)}</b> شاهی\n"
        f"📢 جوین اجباری: <b>{_onoff(sbool('fj_enabled'))}</b> ({_n(fj)} کانال/گروه فعال)\n"
        f"📱 احراز شماره‌ی تلفن (برای کارت به کارت): <b>{_onoff(sbool('phone_verify'))}</b>\n"
        f"⏱ کرون ارسال اطلاعیه: <b>{_fmt_dur(cron_sec())}</b> بین هر دو نفر\n"
        f"📛 متن قوانین: {'✏️ سفارشی' if get_setting('rules_text') else '📄 پیش‌فرض'}\n"
        f"📣 گزارشات ربات: {'🟢 فعال' if rep_ready() else '🔴 تنظیم نشده'}\n"
        f"🃏 بازی‌های گروهی: {'🟢 فعال' if get_setting('casino_on', '1') != '0' else '🔴 خاموش'}\n\n"
        "👇 <i>برای تغییر هر مورد، دکمه‌اش را بزنید.</i>"
    )
    kb = _kb(
        [_ab("🔴 خاموش کردن ربات" if on else "🟢 روشن کردن ربات", "adm_p:g:tg", DANGER if on else SUCCESS)],
        [_ab("☎️ آیدی پشتیبانی", "adm_p:g:in:support", PRIMARY), _ab("🔁 حداقل انتقال", "adm_p:g:in:mt", PRIMARY)],
        [_ab("🪙 موجودی اولیه کاربر جدید", "adm_p:g:in:start", PRIMARY)],
        [_ab("📢 جوین اجباری", "adm_p:x:fj", PRIMARY), _ab("📣 ارسال اطلاعیه", "adm_p:x:bc", SUCCESS)],
        [_ab("📱 احراز شماره: " + ("روشن" if sbool("phone_verify") else "خاموش"), "adm_p:x:ph",
             DANGER if sbool("phone_verify") else SUCCESS), _ab("⏱ تنظیم کرون", "adm_p:x:cron", PRIMARY)],
        [_ab("📡 همگانی درخواست JFJ", "adm_p:x:cb", SUCCESS), _ab("🛑 فعال/غیرفعال کردن بخش‌ها", "adm_p:x:sec", PRIMARY)],
        [_ab("📛 ویرایش قوانین", "adm_p:g:in:rules", SUCCESS), _ab("♻️ قوانین پیش‌فرض", "adm_p:g:rr", DANGER)],
        [_ab("👁 پیش‌نمایش قوانین", "adm_p:g:rv")],
        [_ab("📣 گزارشات ربات", "adm_p:x:rep", SUCCESS if rep_ready() else DANGER)],
        [_ab("🃏 بازی‌های گروهی", "adm_p:x:gm", SUCCESS if get_setting("casino_on", "1") != "0" else DANGER)],
        [_ab("♻️ بازیابی بکاپ", "adm_p:x:rs", SUCCESS)],
    )
    return text, kb


def render_support():
    st = get_setting("support_text")
    text = (
        "☎️ <b>بخش پشتیبانی</b>\n"
        f"{LINE}\n"
        f"🆔 آیدی پشتیبانی: <code>{_h(SUPPORT_ID)}</code>\n"
        f"📝 متن بخش پشتیبانی: {'✏️ سفارشی' if st else '📄 پیش‌فرض'}\n"
        f"👥 کاربران ربات: <b>{_n(_q1('SELECT COUNT(*) FROM users'))}</b>\n\n"
        "✉️ <b>پیام به کاربر</b>: با آیدی عددی پیام می‌فرستید.\n"
        "📣 <b>پیام همگانی</b>: برای همه‌ی کاربران (قبل از ارسال پیش‌نمایش می‌بینید)."
    )
    kb = _kb(
        [_ab("☎️ آیدی پشتیبانی", "adm_p:s:in:support", PRIMARY), _ab("📝 متن بخش پشتیبانی", "adm_p:s:in:support_text", PRIMARY)],
        [_ab("✉️ پیام به کاربر", "adm_p:s:dm", SUCCESS), _ab("📣 پیام همگانی", "adm_p:s:bc", SUCCESS)],
        [_ab("👁 پیش‌نمایش بخش پشتیبانی", "adm_p:s:pv"), _ab("♻️ متن پیش‌فرض", "adm_p:s:rst", DANGER)],
    )
    return text, kb


def _sales(since=None):
    if since:
        return (_q1("SELECT COALESCE(SUM(final_amount),0) FROM invoices WHERE status='paid' AND created_at >= ?", (since,)),
                _q1("SELECT COUNT(*) FROM invoices WHERE status='paid' AND created_at >= ?", (since,)))
    return (_q1("SELECT COALESCE(SUM(final_amount),0) FROM invoices WHERE status='paid'"),
            _q1("SELECT COUNT(*) FROM invoices WHERE status='paid'"))


def render_finance():
    now = now_local()
    d0 = _utc_str(now.replace(hour=0, minute=0, second=0, microsecond=0))
    d7 = _utc_str(now - timedelta(days=7))
    d30 = _utc_str(now - timedelta(days=30))
    (a0, c0), (a7, c7), (a30, c30), (aa, ca) = _sales(d0), _sales(d7), _sales(d30), _sales()
    circ = _q1("SELECT COALESCE(SUM(tokens),0) FROM users")
    review = _q1("SELECT COUNT(*) FROM invoices WHERE status='review'")
    methods = " • ".join(METHOD_LABELS[m] for m in ("card", "zarin", "crypto")
                         if sbool("pay_" + m, "1" if m == "card" else "0")) or "—"
    text = (
        "🏦 <b>مالی</b>\n"
        f"{LINE}\n"
        f"💰 فروش امروز: <b>{_n(a0)}</b> تومان ({_n(c0)} فاکتور)\n"
        f"📅 ۷ روز اخیر: <b>{_n(a7)}</b> تومان ({_n(c7)})\n"
        f"🗓 ۳۰ روز اخیر: <b>{_n(a30)}</b> تومان ({_n(c30)})\n"
        f"📈 کل فروش: <b>{_n(aa)}</b> تومان ({_n(ca)})\n"
        f"{LINE}\n"
        f"🪙 شاهی در گردش: <b>{_t(circ)}</b>\n"
        f"🧾 رسید در انتظار بررسی: <b>{_n(review)}</b>\n"
        f"{LINE}\n"
        f"💳 روش‌های پرداخت فعال: <b>{methods}</b>\n"
        f"⏱ اعتبار فاکتور: <b>{_n(INVOICE_VALIDITY_MINUTES)}</b> دقیقه"
    )
    kb = _kb(
        [_ab("💳 روش‌های پرداخت", "adm_p:x:pay", SUCCESS)],
        [_ab("⏱ اعتبار فاکتور", "adm_p:f:in:inv", PRIMARY)],
        [_ab("📜 آخرین فروش‌ها", "adm_p:f:last", SUCCESS), _ab(f"🧾 رسیدهای در انتظار ({_n(review)})", "adm_p:o:inv:0", SUCCESS)],
        [_ab("🔄 بروزرسانی", "adm_p:f:home")],
    )
    return text, kb


def render_users():
    total = _q1("SELECT COUNT(*) FROM users")
    banned = _q1("SELECT COUNT(*) FROM users WHERE banned=1")
    text = (
        "👤 <b>مدیریت کاربر</b>\n"
        f"{LINE}\n"
        f"👥 کل کاربران: <b>{_n(total)}</b>\n"
        f"🚫 مسدود شده: <b>{_n(banned)}</b>\n\n"
        "🔎 با «جستجوی کاربر» آیدی عددی یا @یوزرنیم را بفرستید تا پروفایل او باز شود؛ "
        "از آنجا می‌توانید موجودی را تغییر دهید، کاربر را مسدود کنید یا پیام بفرستید."
    )
    kb = _kb(
        [_ab("🔎 جستجوی کاربر", "adm_p:u:in:ufind", SUCCESS)],
        [_ab("🏆 ثروتمندترین‌ها", "adm_p:u:rich", PRIMARY), _ab("🆕 جدیدترین‌ها", "adm_p:u:new", PRIMARY)],
        [_ab(f"🚫 مسدودشده‌ها ({_n(banned)})", "adm_p:u:bl", DANGER)],
        [_ab("💸 شارژ همگانی", "adm_p:x:mc", SUCCESS)],
    )
    return text, kb


def _packs(kind):
    return JTOKEN_PRODUCTS if kind == "j" else SPONSOR_PRODUCTS


def _pack_label(kind, p):
    if kind == "j":
        final, base, pct = jt_price_info(p)
        extra = f" ({_n(pct)}٪ تخفیف)" if pct else ""
        return f"{_n(p['tokens'])} شاهی • {_n(final)} تومان{extra}"
    return f"{_n(p['hours'])} ساعت • {_n(p['price'])} تومان"


def _save_packs(kind, packs):
    set_setting("jtoken_products" if kind == "j" else "sponsor_products", json.dumps(packs))
    apply_settings()


def render_packs(kind):
    packs = _packs(kind)
    if kind == "j":
        title, unit = "🛍 <b>تنظیمات خرید شاهی</b>", "j"
        sold = _q1("SELECT COUNT(*) FROM invoices WHERE status='paid' AND kind='jtoken'")
        amount = _q1("SELECT COALESCE(SUM(final_amount),0) FROM invoices WHERE status='paid' AND kind='jtoken'")
    else:
        title, unit = "🎗 <b>تنظیمات اسپانسر</b>", "p"
        sold = _q1("SELECT COUNT(*) FROM invoices WHERE status='paid' AND kind='sponsor'")
        amount = _q1("SELECT COALESCE(SUM(final_amount),0) FROM invoices WHERE status='paid' AND kind='sponsor'")
    lines = [f"{i + 1}️⃣ {_pack_label(kind, p)}" for i, p in enumerate(packs)]
    text = (
        f"{title}\n{LINE}\n"
        "📦 <b>بسته‌های فعلی:</b>\n" + "\n".join(lines) + "\n"
        f"{LINE}\n"
        f"✅ فروش موفق: <b>{_n(sold)}</b> عدد • <b>{_n(amount)}</b> تومان\n\n"
        "👇 <i>برای ویرایش یا حذف، روی هر بسته بزنید.</i>"
    )
    rows = [[_ab(f"✏️ {_pack_label(kind, p)}", f"adm_p:{unit}:pk:{p['id']}", PRIMARY)] for p in packs]
    rows.append([_ab("➕ افزودن بسته‌ی جدید", f"adm_p:{unit}:pa", SUCCESS)])
    if kind == "j":
        b = bonus_state()
        up = unit_price()
        rows.append([_ab("💵 قیمت هر شاهی و تخفیف", "adm_p:x:disc", PRIMARY),
                     _ab("🎁 بونوس خرید شاهی", "adm_p:x:bon", SUCCESS)])
        text = text.replace("👇 <i>برای ویرایش", (
            f"💵 قیمت هر ۱ شاهی: <b>{(_n(up) + ' تومان') if up > 0 else 'تنظیم نشده (قیمت ثابت بسته‌ها)'}</b>\n"
            f"🏷 تخفیف‌های فعال: <b>{_n(len(disc_tiers()))}</b>\n"
            f"🎁 بونوس خرید: <b>{'🟢 فعال' if b['active'] else '🔴 غیرفعال'}</b>\n\n"
            "👇 <i>برای ویرایش"), 1)
    if kind == "p":
        rows.append([_ab("📋 آخرین اسپانسرها", "adm_p:p:last", PRIMARY)])
    return text, _kb(*rows)


def render_referral():
    refs = _q1("SELECT COUNT(DISTINCT referred_by) FROM users WHERE referred_by IS NOT NULL")
    invited = _q1("SELECT COUNT(*) FROM users WHERE referred_by IS NOT NULL")
    rewarded = _q1("SELECT COUNT(*) FROM users WHERE referred_by IS NOT NULL AND referral_rewarded=1")
    text = (
        "👥 <b>تنظیمات زیرمجموعه</b>\n"
        f"{LINE}\n"
        f"🎁 پاداش معرف: <b>{_t(REFERRAL_REWARD)}</b> شاهی\n"
        f"🎯 فعالیت لازم زیرمجموعه: <b>{_t(REFERRAL_ACTIVITY_THRESHOLD)}</b> شاهی از جوین‌ها\n"
        f"{LINE}\n"
        f"🧑‍🤝‍🧑 معرف‌ها: <b>{_n(refs)}</b> نفر\n"
        f"📥 زیرمجموعه‌های دعوت‌شده: <b>{_n(invited)}</b> نفر\n"
        f"✅ پاداش پرداخت‌شده: <b>{_n(rewarded)}</b> مورد\n"
        f"💸 مجموع پاداش پرداختی: <b>{_t(rewarded * REFERRAL_REWARD)}</b> شاهی"
    )
    kb = _kb(
        [_ab("🎁 تغییر پاداش معرف", "adm_p:r:in:rr", PRIMARY)],
        [_ab("🎯 تغییر فعالیت لازم", "adm_p:r:in:rt", PRIMARY)],
        [_ab("🏆 برترین معرف‌ها", "adm_p:r:top", SUCCESS)],
    )
    return text, kb


def render_requests():
    tot = _q1("SELECT COUNT(*) FROM requests")
    act = _q1("SELECT COUNT(*) FROM requests WHERE status NOT IN ('completed','cancelled','removed','deleted','relinked')")
    joins = _q1("SELECT COUNT(*) FROM joins")
    left = _q1("SELECT COUNT(*) FROM joins WHERE left_at IS NOT NULL")
    text = (
        "🧰 <b>تنظیمات درخواست JFJ</b>\n"
        f"{LINE}\n"
        f"💎 هزینه‌ی هر ممبر: <b>{_t(TOKENS_PER_MEMBER)}</b> شاهی\n"
        f"🔢 حداقل ممبر هر درخواست: <b>{_n(MIN_MEMBER_COUNT)}</b>\n"
        f"🎁 پاداش هر جوین: <b>{_t(JOIN_REWARD)}</b> شاهی (جریمه‌ی لفت: همین‌قدر)\n"
        f"↩️ بازگشت به صاحب سفارش هنگام لفت: <b>{_t(LEAVE_REFUND_TO_OWNER)}</b> شاهی\n"
        f"⏱ فاصله‌ی دو درخواست برای یک کانال: <b>{_n(RESUBMIT_COOLDOWN_SECONDS // 60)}</b> دقیقه\n"
        f"{LINE}\n"
        f"📋 کل درخواست‌ها: <b>{_n(tot)}</b> • در حال انجام: <b>{_n(act)}</b>\n"
        f"✅ جوین‌ها: <b>{_n(joins)}</b> • لفت‌ها: <b>{_n(left)}</b>"
    )
    kb = _kb(
        [_ab("💎 هزینه‌ی هر ممبر", "adm_p:q:in:tpm", PRIMARY), _ab("🔢 حداقل ممبر", "adm_p:q:in:minm", PRIMARY)],
        [_ab("🎁 پاداش جوین", "adm_p:q:in:jr", PRIMARY), _ab("↩️ بازگشت لفت", "adm_p:q:in:lrf", PRIMARY)],
        [_ab("⏱ فاصله‌ی دو درخواست", "adm_p:q:in:cool", PRIMARY)],
        [_ab("📋 درخواست‌های در حال انجام", "adm_p:o:req:0", SUCCESS)],
        [_ab("🗑 حذف درخواست‌ها", "adm_p:x:rm:0", DANGER), _ab(f"🚫 کانال‌های مسدود ({_n(len(_block_keys()))})", "adm_p:x:bk", DANGER)],
    )
    return text, kb


def render_orders():
    so = _q1("SELECT COUNT(*) FROM service_orders WHERE status='pending'")
    rv = _q1("SELECT COUNT(*) FROM invoices WHERE status='review'")
    aw = _q1("SELECT COUNT(*) FROM invoices WHERE status='awaiting_receipt'")
    rq = _q1("SELECT COUNT(*) FROM requests WHERE status NOT IN ('completed','cancelled','removed','deleted','relinked')")
    text = (
        "🧾 <b>سفارشات تکمیل نشده</b>\n"
        f"{LINE}\n"
        f"🛒 سفارش خدمات منتظر انجام: <b>{_n(so)}</b>\n"
        f"🧾 رسید منتظر تأیید: <b>{_n(rv)}</b>\n"
        f"⏳ فاکتور منتظر ارسال رسید: <b>{_n(aw)}</b>\n"
        f"📋 درخواست JFJ در حال انجام: <b>{_n(rq)}</b>\n\n"
        "👇 <i>هر بخش را باز کنید؛ هر مورد دکمه‌ی تکمیل/لغو یا تأیید/رد خودش را دارد.</i>"
    )
    kb = _kb(
        [_ab(f"🛒 سفارش‌های خدمات ({_n(so)})", "adm_p:o:svc:0", SUCCESS)],
        [_ab(f"🧾 رسیدهای منتظر تأیید ({_n(rv)})", "adm_p:o:inv:0", SUCCESS)],
        [_ab(f"📋 درخواست‌های JFJ ({_n(rq)})", "adm_p:o:req:0", PRIMARY)],
        [_ab("🔄 بروزرسانی", "adm_p:o:home")],
    )
    return text, kb


SECTION_RENDER = {
    "g": render_general, "s": render_support, "f": render_finance, "u": render_users,
    "p": lambda: render_packs("p"), "j": lambda: render_packs("j"),
    "r": render_referral, "q": render_requests, "o": render_orders,
}


def _send_section(chat_id, sec):
    text, kb = SECTION_RENDER[sec]()
    _hsend(chat_id, text, kb)


def admin_open_section(chat_id, admin_id, sec):
    set_state(admin_id, "admin_panel")
    _send_section(chat_id, sec)


# ---------- کارت کاربر ----------
def _find_user(text):
    t = text.strip().translate(_ASCII_DIGITS).lstrip("@")
    with get_db() as c:
        if t.isdigit():
            r = c.execute("SELECT id FROM users WHERE id=?", (int(t),)).fetchone()
        else:
            r = c.execute("SELECT id FROM users WHERE LOWER(username)=LOWER(?)", (t,)).fetchone()
    return r[0] if r else None


def _user_card(uid):
    with get_db() as c:
        u = c.execute("SELECT first_name, username, tokens, referred_by, created_at, banned, card_blocked, phone, phone_req "
                      "FROM users WHERE id=?", (uid,)).fetchone()
    if not u:
        return "❌ کاربر پیدا نشد.", _kb(_back("u"))
    reqs = _q1("SELECT COUNT(*) FROM requests WHERE user_id=?", (uid,))
    act = _q1("SELECT COUNT(*) FROM requests WHERE user_id=? AND status NOT IN ('completed','cancelled','removed','deleted','relinked')", (uid,))
    joins = _q1("SELECT COUNT(*) FROM joins WHERE user_id=? AND left_at IS NULL", (uid,))
    lefts = _q1("SELECT COUNT(*) FROM joins WHERE user_id=? AND left_at IS NOT NULL", (uid,))
    svc = _q1("SELECT COUNT(*) FROM service_orders WHERE user_id=?", (uid,))
    subs = _q1("SELECT COUNT(*) FROM users WHERE referred_by=?", (uid,))
    spent = _q1("SELECT COALESCE(SUM(final_amount),0) FROM invoices WHERE buyer_id=? AND status='paid'", (uid,))
    spons = _q1("SELECT COUNT(*) FROM sponsor_subs WHERE user_id=? AND status='active' AND ends_at > ?", (uid, _utcnow_str()))
    banned, cblk, phone, preq = bool(u[5]), bool(u[6]), u[7], bool(u[8])
    un = f"@{u[1]}" if u[1] else "بدون یوزرنیم"
    text = (
        f"👤 <b>{_h((u[0] or 'کاربر').strip())}</b>  {_h(un)}\n"
        f"{LINE}\n"
        f"🆔 آیدی عددی: <code>{uid}</code>\n"
        f"🪙 دارایی: <b>{_t(u[2])}</b> شاهی\n"
        f"📅 عضویت: {_fa_dt(u[4])}\n"
        f"📱 شماره: {('<code>%s</code>' % _h(phone)) if phone else ('⏳ منتظر ارسال کاربر' if preq else '—')}\n"
        f"{LINE}\n"
        f"📋 درخواست JFJ: <b>{_n(reqs)}</b> (در حال انجام: {_n(act)})\n"
        f"✅ جوین فعال: <b>{_n(joins)}</b> • ❌ لفت: <b>{_n(lefts)}</b>\n"
        f"🛒 سفارش خدمات: <b>{_n(svc)}</b>\n"
        f"💳 مجموع خرید: <b>{_n(spent)}</b> تومان\n"
        f"🎗 اسپانسری فعال: <b>{_n(spons)}</b>\n"
        f"👥 زیرمجموعه: <b>{_n(subs)}</b> • معرف: {('<code>%s</code>' % u[3]) if u[3] else '—'}\n"
        f"{LINE}\n"
        f"وضعیت: {'🚫 <b>مسدود</b>' if banned else '🟢 فعال'} • کارت به کارت: {'🔴 غیرفعال' if cblk else '🟢 فعال'}"
    )
    kb = _kb(
        [_ab("➕ افزودن شاهی", f"adm_p:u:add:{uid}", SUCCESS), _ab("➖ کسر شاهی", f"adm_p:u:sub:{uid}", DANGER)],
        [_ab("🎯 تنظیم موجودی", f"adm_p:u:set:{uid}", PRIMARY), _ab("0️⃣ صفر کردن موجودی", f"adm_p:u:zero:{uid}", DANGER)],
        [_ab("✅ رفع مسدودی" if banned else "🚫 مسدود کردن", f"adm_p:u:ban:{uid}", SUCCESS if banned else DANGER),
         _ab("✉️ پیام به کاربر", f"adm_p:u:dm:{uid}", PRIMARY)],
        [_ab("🎁 افزودن محصول", f"adm_p:u:prod:{uid}", SUCCESS), _ab("🏷 کد تخفیف", f"adm_p:u:dcn:{uid}", SUCCESS)],
        [_ab("💳 فعال‌سازی کارت" if cblk else "💳 غیرفعال‌سازی کارت", f"adm_p:u:cbt:{uid}", SUCCESS if cblk else DANGER),
         _ab("📱 لغو الزام شماره" if preq else "📱 تأیید دستی شماره", f"adm_p:u:phr:{uid}", PRIMARY)],
        [_ab("🎗 اشتراک اسپانسری", f"adm_p:sp:ls:{uid}", PRIMARY), _ab("♻️ ریست زیرمجموعه‌ها", f"adm_p:u:rrf:{uid}", DANGER)],
        [_ab("📦 سفارش‌های کاربر", f"adm_p:u:ords:{uid}"), _ab("🔄 بروزرسانی", f"adm_p:u:card:{uid}")],
        _back("u", "🔙 بازگشت به مدیریت کاربر"),
    )
    return text, kb


# ---------- ورودی‌های متنی ----------
def _ask(chat_id, admin_id, name, back, prompt, **extra):
    set_state(admin_id, "adm_in", dict(name=name, back=back, **extra))
    _hsend(chat_id, prompt + "\n\n<i>برای انصراف، دکمه‌ی زیر را بزنید.</i>",
           _kb([_ab("❌ انصراف", f"adm_p:{back}:home", DANGER)]))


def _prompt_for(name):
    if name in SETTING_DEFS:
        d = SETTING_DEFS[name]
        cur = _cfg_value(name)
        kind = "عدد صحیح" if d["kind"] == "int" else "عدد (اعشار مجاز است)"
        return (f"{d['icon']} <b>{_h(d['label'])}</b>\n\nمقدار فعلی: <b>{_t(cur)}</b> {d['unit']}\n"
                f"مقدار جدید را به صورت {kind} بفرستید:")
    return {
        "card": f"💳 <b>شماره کارت</b>\n\nمقدار فعلی: <code>{_h(CARD_NUMBER)}</code>\nشماره‌ی کارت جدید را بفرستید:",
        "holder": f"👤 <b>نام صاحب کارت</b>\n\nمقدار فعلی: <b>{_h(CARD_HOLDER)}</b>\nنام جدید را بفرستید:",
        "support": f"☎️ <b>آیدی پشتیبانی</b>\n\nمقدار فعلی: <code>{_h(SUPPORT_ID)}</code>\nآیدی جدید را بفرستید (مثل @support):",
        "support_text": "📝 <b>متن بخش پشتیبانی</b>\n\nمتن جدید را بفرستید. برای جای‌گذاری خودکار آیدی پشتیبانی، "
                        "عبارت <code>{support}</code> را در متن بنویسید.",
        "rules": "📛 <b>متن قوانین</b>\n\nمتن جدید قوانین را بفرستید (چند خطی و ایموجی مجاز است).",
        "ufind": "🔎 <b>جستجوی کاربر</b>\n\nآیدی عددی یا @یوزرنیم کاربر را بفرستید:",
    }[name]


def admin_begin_input(chat_id, admin_id, name, back, **extra):
    _ask(chat_id, admin_id, name, back, _prompt_for(name), **extra)


def _done(chat_id, admin_id, data, msg):
    set_state(admin_id, "admin_panel")
    _hsend(chat_id, "✅ " + msg)
    then = data.get("then")
    if then and then[0] == "card":
        t, k = _user_card(then[1])
        _hsend(chat_id, t, k)
    else:
        _send_section(chat_id, data["back"])


def _err(chat_id, msg):
    _hsend(chat_id, "❗️ " + msg)


def admin_handle_input(chat_id, user, text, data):
    if str(data.get("name", "")).startswith("gx_") and GAMES:
        return GAMES.admin_input(chat_id, user, text, data)
    if data.get("name") in ("rs_wait", "rs_confirm"):
        _hsend(chat_id, "❗️ فایل بکاپ را به‌صورت «فایل (Document)» بفرستید، یا برای ادامه/لغو از دکمه‌های پیام قبلی استفاده کنید.")
        return
    if v2_handle_input(chat_id, user, text, data):
        return
    admin_id = user["id"]
    name = data.get("name")
    text = text.strip()
    t = text.translate(_ASCII_DIGITS)
    if name in SETTING_DEFS:
        d = SETTING_DEFS[name]
        n = parse_number(text)
        if n is None or n < d["min"] or (d["kind"] == "int" and n != int(n)):
            _err(chat_id, f"یک {'عدد صحیح' if d['kind'] == 'int' else 'عدد'} معتبر (حداقل {fa_digits(str(d['min']))}) بفرستید.")
            return
        set_setting("cfg_" + name, n * d["mul"])
        apply_settings()
        _done(chat_id, admin_id, data, f"{d['label']} روی {_t(n)} {d['unit']} تنظیم شد.")
    elif name == "card":
        digits = text.translate(_ASCII_DIGITS).replace("-", "").replace(" ", "")
        if not digits.isdigit() or len(digits) != 16:
            _err(chat_id, "شماره کارت باید ۱۶ رقم باشد.")
            return
        set_setting("cfg_card", "-".join(digits[i:i + 4] for i in range(0, 16, 4)))
        apply_settings()
        _done(chat_id, admin_id, data, "شماره کارت ذخیره شد.")
    elif name == "holder":
        if not 2 <= len(text) <= 60:
            _err(chat_id, "نام باید بین ۲ تا ۶۰ حرف باشد.")
            return
        set_setting("cfg_holder", text)
        apply_settings()
        _done(chat_id, admin_id, data, "نام صاحب کارت ذخیره شد.")
    elif name == "support":
        v = text if text.startswith("@") else "@" + text.lstrip("@")
        if not re.fullmatch(r"@[A-Za-z0-9_]{4,32}", v):
            _err(chat_id, "آیدی نامعتبر است؛ مثل @support بفرستید.")
            return
        set_setting("cfg_support", v)
        apply_settings()
        _done(chat_id, admin_id, data, f"آیدی پشتیبانی روی {_h(v)} تنظیم شد.")
    elif name in ("support_text", "rules"):
        if len(text) < 5 or len(text) > 3500:
            _err(chat_id, "متن باید بین ۵ تا ۳۵۰۰ نویسه باشد.")
            return
        set_setting("support_text" if name == "support_text" else "rules_text", text)
        _done(chat_id, admin_id, data, "متن ذخیره شد.")
    elif name == "ufind":
        uid = _find_user(text)
        if not uid:
            _err(chat_id, "کاربری با این مشخصات پیدا نشد؛ دوباره بفرستید.")
            return
        set_state(admin_id, "admin_panel")
        t, k = _user_card(uid)
        _hsend(chat_id, t, k)
    elif name in ("uadd", "usub", "uset"):
        n = parse_number(text)
        if n is None or (name != "uset" and n <= 0):
            _err(chat_id, "یک عدد معتبر بفرستید.")
            return
        uid = data["uid"]
        old_bal = get_balance(uid)
        with get_db() as c:
            if name == "uadd":
                c.execute("UPDATE users SET tokens = tokens + ? WHERE id=?", (n, uid))
            elif name == "usub":
                c.execute("UPDATE users SET tokens = tokens - ? WHERE id=?", (n, uid))
            else:
                c.execute("UPDATE users SET tokens = ? WHERE id=?", (n, uid))
        bal = get_balance(uid)
        rep_ev_admin_balance(admin_id, uid, name, n, old_bal)
        note = {"uadd": f"🎁 مدیر {_t(n)} شاهی به حساب شما اضافه کرد.\n🪙 دارایی فعلی: {_t(bal)} شاهی",
                "usub": f"➖ مدیر {_t(n)} شاهی از حساب شما کم کرد.\n🪙 دارایی فعلی: {_t(bal)} شاهی",
                "uset": f"🪙 دارایی شما توسط مدیر روی {_t(n)} شاهی تنظیم شد."}[name]
        # فقط افزایش به کاربر اطلاع داده می‌شود؛ کسر و کاهش بی‌صدا انجام می‌شود
        if bal > old_bal:
            send(uid, note if name != "uset" else f"🎁 دارایی شما به {_t(bal)} شاهی افزایش یافت.", markdown=False)
        _done(chat_id, admin_id, data, f"انجام شد. دارایی جدید: {_t(bal)} شاهی." + ("" if bal > old_bal else " (به کاربر خبر داده نشد)"))
    elif name == "udm":
        uid = data["uid"]
        r = send(uid, "📩 پیام از مدیریت:\n\n" + text, markdown=False)
        if r.get("ok"):
            _done(chat_id, admin_id, data, "پیام ارسال شد.")
        else:
            _err(chat_id, "ارسال نشد؛ احتمالاً کاربر ربات را بلاک کرده است.")
            set_state(admin_id, "admin_panel")
    elif name in ("mc_add", "mc_sub"):
        n = _num_ok(t, 0.01)
        if n is None:
            _err(chat_id, "یک عدد معتبر بزرگ‌تر از صفر بفرستید.")
            return True
        mode = name[3:]
        total = _q1("SELECT COUNT(*) FROM users")
        set_state(admin_id, "admin_panel")
        _hsend(chat_id, f"{'➕ شارژ' if mode == 'add' else '➖ کسر'} همگانی\n{LINE}\n"
                        f"🪙 مقدار: <b>{_t(n)}</b> شاهی برای هر کاربر\n👥 تعداد کاربران: <b>{_n(total)}</b>\n"
                        "🔕 بدون اطلاع‌رسانی به کاربران.\n\nمطمئنید؟",
               _kb([_ab("✅ تأیید و اجرا", f"adm_p:x:mcg:{mode}:{fmt_tokens(n)}", SUCCESS if mode == "add" else DANGER)],
                   [_ab("❌ انصراف", "adm_p:x:mc", PRIMARY)]))
    elif name == "bk_add":
        ref = t if re.fullmatch(r"-?\d{6,}", t) else None
        if ref:
            keys = [f"id:{ref}"]
        else:
            m = re.fullmatch(r"(?:https?://)?(?:t\.me/)?@?([A-Za-z][A-Za-z0-9_]{3,31})", t)
            if not m:
                _err(chat_id, "آیدی نامعتبر است؛ مثل @mychannel یا آیدی عددی (-100…) بفرستید.")
                return True
            keys = ["@" + m.group(1)]
            g = tg("getChat", chat_id="@" + m.group(1), _timeout=10)
            if g.get("ok"):
                keys.append(f"id:{g['result']['id']}")
        block_chan(keys)
        _fin(chat_id, admin_id, data, "کانال/گروه مسدود شد.")
    elif name == "sdm_id":
        uid = _find_user(text)
        if not uid:
            _err(chat_id, "کاربری با این مشخصات پیدا نشد؛ دوباره بفرستید.")
            return
        _ask(chat_id, admin_id, "udm", "s", f"✉️ پیام برای {_label(uid)}\n\nمتن پیام را بفرستید:", uid=uid)
    elif name == "bc_text":
        if len(text) > 3500:
            _err(chat_id, "متن خیلی طولانی است (حداکثر ۳۵۰۰ نویسه).")
            return
        total = _q1("SELECT COUNT(*) FROM users WHERE banned=0")
        set_state(admin_id, "admin_panel", {"bc": text})
        _hsend(chat_id,
               f"📣 <b>پیش‌نمایش پیام همگانی</b>\n{LINE}\n{_h(text)}\n{LINE}\n"
               f"این پیام برای <b>{_n(total)}</b> کاربر ارسال می‌شود. مطمئنید؟",
               _kb([_ab("✅ ارسال برای همه", "adm_p:s:bcgo", SUCCESS), _ab("❌ انصراف", "adm_p:s:home", DANGER)]))
    elif name in ("pk_add_q", "pk_add_p", "pk_edit_q", "pk_edit_p"):
        n = parse_number(text)
        if n is None or n != int(n) or n < 1:
            _err(chat_id, "یک عدد صحیح و بزرگ‌تر از صفر بفرستید.")
            return
        _pack_input(chat_id, admin_id, name, int(n), data)
    else:
        set_state(admin_id, "admin_panel")


def _pack_input(chat_id, admin_id, name, n, data):
    kind = data["kind"]
    qf = "tokens" if kind == "j" else "hours"
    unit = "شاهی" if kind == "j" else "ساعت"
    if name == "pk_add_q":
        _ask(chat_id, admin_id, "pk_add_p", kind, f"💰 قیمت این بسته را به <b>تومان</b> بفرستید:", kind=kind, q=n)
    elif name == "pk_add_p":
        packs = [dict(p) for p in _packs(kind)]
        pid = f"{'jt' if kind == 'j' else 'sp'}{data['q']}"
        if any(p["id"] == pid for p in packs):
            pid += str(random.randint(10, 99))
        packs.append({"id": pid, qf: data["q"], "price": n})
        packs.sort(key=lambda p: p[qf])
        _save_packs(kind, packs)
        _done(chat_id, admin_id, data, f"بسته‌ی {_n(data['q'])} {unit} با قیمت {_n(n)} تومان اضافه شد.")
    else:
        packs = [dict(p) for p in _packs(kind)]
        for p in packs:
            if p["id"] == data["pid"]:
                p[qf if name == "pk_edit_q" else "price"] = n
        _save_packs(kind, packs)
        _done(chat_id, admin_id, data, "بسته ذخیره شد.")


# ---------- لیست‌ها ----------
def _so_card(code):
    with get_db() as c:
        row = c.execute("SELECT user_id, service, quantity, extra, token_cost, link, created_at FROM service_orders WHERE tracking_code=?", (code,)).fetchone()
    if not row:
        return None, None
    uid, service, qty, extra, cost, link, created = row
    lines = ["🛒 <b>سفارش خدمات</b>", f"🔍 کد: <code>{code}</code>", f"📦 {_h(service)} • تعداد {_n(qty)}"]
    if extra:
        lines.append(f"😀 ری‌اکشن: {_h(extra)}")
    lines += [f"🔗 {_h(link)}", f"🪙 {_t(cost)} شاهی", f"👤 {_label(uid)}", f"⏰ {_fa_dt(created)}"]
    kb = _kb([_ab("✅ تکمیل سفارش", f"adm_so_ok:{code}", SUCCESS), _ab("❌ لغو و بازگشت موجودی", f"adm_so_no:{code}", DANGER)])
    return "\n".join(lines), kb


def _inv_card(code):
    with get_db() as c:
        row = c.execute("SELECT buyer_id, product_name, final_amount, created_at FROM invoices WHERE code=?", (code,)).fetchone()
    if not row:
        return None, None
    text = (f"🧾 <b>رسید منتظر تأیید</b>\n🔍 فاکتور: <code>{code}</code>\n📦 {_h(row[1])}\n"
            f"💰 {_n(row[2])} تومان\n👤 {_label(row[0])}\n⏰ {_fa_dt(row[3])}")
    kb = _kb([_ab("✅ تأیید و اعمال", f"adm_inv_ok:{code}", SUCCESS), _ab("❌ رد رسید", f"adm_inv_no:{code}", DANGER)])
    return text, kb


PAGE = 5


def _send_list(ctx_chat, sec_key, offset):
    """سفارش خدمات / رسیدها: هر مورد پیام جدا با دکمه‌های خودش"""
    if sec_key == "svc":
        total = _q1("SELECT COUNT(*) FROM service_orders WHERE status='pending'")
        with get_db() as c:
            codes = [r[0] for r in c.execute("SELECT tracking_code FROM service_orders WHERE status='pending' ORDER BY created_at LIMIT ? OFFSET ?", (PAGE, offset)).fetchall()]
        card, empty = _so_card, "🎉 هیچ سفارش خدماتی در انتظار نیست."
    else:
        total = _q1("SELECT COUNT(*) FROM invoices WHERE status='review'")
        with get_db() as c:
            codes = [r[0] for r in c.execute("SELECT code FROM invoices WHERE status='review' ORDER BY created_at LIMIT ? OFFSET ?", (PAGE, offset)).fetchall()]
        card, empty = _inv_card, "🎉 هیچ رسیدی در انتظار بررسی نیست."
    if not codes:
        _hsend(ctx_chat, empty, _kb(_back("o")))
        return
    for code in codes:
        t, k = card(code)
        if t:
            _hsend(ctx_chat, t, k)
    left = total - offset - len(codes)
    if left > 0:
        _hsend(ctx_chat, f"📄 {_n(left)} مورد دیگر هم هست.",
               _kb([_ab("⬇️ نمایش بعدی‌ها", f"adm_p:o:{sec_key}:{offset + PAGE}", PRIMARY)], _back("o")))
    else:
        _hsend(ctx_chat, "✅ پایان لیست.", _kb(_back("o")))


def _send_requests(chat_id, offset):
    total = _q1("SELECT COUNT(*) FROM requests WHERE status NOT IN ('completed','cancelled','removed','deleted','relinked')")
    with get_db() as c:
        rows = c.execute(
            "SELECT r.tracking_code, r.user_id, r.member_count, r.link, r.created_at, "
            "(SELECT COUNT(*) FROM joins j WHERE j.tracking_code=r.tracking_code AND j.left_at IS NULL) "
            "FROM requests r WHERE r.status NOT IN ('completed','cancelled','removed','deleted','relinked') ORDER BY r.created_at LIMIT 8 OFFSET ?", (offset,)).fetchall()
    if not rows:
        _hsend(chat_id, "🎉 درخواست JFJ در حال انجامی وجود ندارد.", _kb(_back("o")))
        return
    lines = ["📋 <b>درخواست‌های JFJ در حال انجام</b>", LINE]
    for code, uid, cnt, link, created, done in rows:
        lines.append(f"🔍 <code>{code}</code> • {_n(done)} از {_n(cnt)}\n🔗 {_h(link)}\n👤 {_label(uid)}\n⏰ {_fa_dt(created)}\n")
    kb = []
    left = total - offset - len(rows)
    if left > 0:
        kb.append([_ab(f"⬇️ {_n(left)} مورد بعدی", f"adm_p:o:req:{offset + 8}", PRIMARY)])
    kb.append(_back("o"))
    _hsend(chat_id, "\n".join(lines), _kb(*kb))


# ---------- مسیریاب دکمه‌های شیشه‌ای پنل ----------
def admin_panel_callback(cq):
    if v2_admin_callback(cq):
        return
    parts = cq["data"].split(":")  # adm_p : بخش : عملیات : آرگومان‌ها
    sec = parts[1] if len(parts) > 1 else "g"
    act = parts[2] if len(parts) > 2 else "home"
    args = parts[3:]
    admin_id = cq["from"]["id"]
    chat_id = cq["message"]["chat"]["id"]
    mid = cq["message"]["message_id"]
    answered = [False]

    def ack(text=None, alert=False):
        if not answered[0]:
            answered[0] = True
            answer_callback(cq["id"], text, show_alert=alert)

    def show(text, kb):
        _hedit(chat_id, mid, text, kb)

    def home(sec_key=None):
        t, k = SECTION_RENDER[sec_key or sec]()
        show(t, k)

    try:
        # --- مشترک ---
        if act == "home":
            ack()
            set_state(admin_id, "admin_panel")
            return home()
        if act == "in":
            ack()
            return admin_begin_input(chat_id, admin_id, args[0], sec)

        # --- تنظیمات عمومی ---
        if sec == "g":
            if act == "tg":
                set_setting("bot_enabled", "1" if get_setting("bot_enabled", "1") == "0" else "0")
                ack("وضعیت ربات تغییر کرد.")
                return home()
            if act == "cas":
                set_setting("casino_on", "1" if get_setting("casino_on", "1") == "0" else "0")
                ack("وضعیت کازینو تغییر کرد.")
                return home()
            if act == "rr":
                with get_db() as c:
                    c.execute("DELETE FROM settings WHERE key='rules_text'")
                ack("قوانین به حالت پیش‌فرض برگشت.")
                return home()
            if act == "rv":
                ack()
                return send_rules(chat_id)

        # --- پشتیبانی ---
        if sec == "s":
            if act == "dm":
                ack()
                return _ask(chat_id, admin_id, "sdm_id", "s", "✉️ <b>پیام به کاربر</b>\n\nآیدی عددی یا @یوزرنیم کاربر را بفرستید:")
            if act == "bc":
                ack()
                return _ask(chat_id, admin_id, "bc_text", "s", "📣 <b>پیام همگانی</b>\n\nمتن پیام را بفرستید (متن ساده):")
            if act == "pv":
                ack()
                return send_support(chat_id)
            if act == "rst":
                with get_db() as c:
                    c.execute("DELETE FROM settings WHERE key='support_text'")
                ack("متن پیش‌فرض برگشت.")
                return home()
            if act == "bcgo":
                _, data = get_state(admin_id)
                text = data.get("bc")
                if not text:
                    return ack("پیامی برای ارسال نیست.", True)
                set_state(admin_id, "admin_panel")
                ack("ارسال شروع شد…")
                show("📣 <b>ارسال پیام همگانی شروع شد…</b>\nنتیجه بعد از پایان همین‌جا اعلام می‌شود.", None)
                threading.Thread(target=_broadcast, args=(chat_id, mid, text), daemon=True).start()
                return

        # --- مالی ---
        if sec == "f" and act == "last":
            ack()
            with get_db() as c:
                rows = c.execute("SELECT product_name, final_amount, buyer_id, created_at FROM invoices WHERE status='paid' ORDER BY created_at DESC LIMIT 10").fetchall()
            if not rows:
                return _hsend(chat_id, "هنوز فروشی ثبت نشده است.", _kb(_back("f")))
            lines = ["📜 <b>آخرین فروش‌ها</b>", LINE]
            for pn, amt, buyer, created in rows:
                lines.append(f"✅ {_h(pn)} • <b>{_n(amt)}</b> تومان\n👤 {_label(buyer)}\n⏰ {_fa_dt(created)}\n")
            return _hsend(chat_id, "\n".join(lines), _kb(_back("f")))

        # --- مدیریت کاربر ---
        if sec == "u":
            if act in ("rich", "new", "bl"):
                ack()
                q = {"rich": ("🏆 ثروتمندترین کاربران", "ORDER BY tokens DESC LIMIT 10", ""),
                     "new": ("🆕 جدیدترین کاربران", "ORDER BY created_at DESC LIMIT 10", ""),
                     "bl": ("🚫 کاربران مسدود", "ORDER BY updated_at DESC LIMIT 20", "WHERE banned=1")}[act]
                with get_db() as c:
                    rows = c.execute(f"SELECT id, first_name, username, tokens FROM users {q[2]} {q[1]}").fetchall()
                if not rows:
                    return _hsend(chat_id, "موردی پیدا نشد.", _kb(_back("u")))
                lines = [f"<b>{q[0]}</b>", LINE]
                kb = []
                for i, (uid, fn, un, tk) in enumerate(rows, 1):
                    lines.append(f"{fa_digits(str(i))}. {_h((fn or 'کاربر').strip())} {_h('@' + un) if un else ''} • <code>{uid}</code> • {_t(tk)} شاهی")
                    kb.append([_ab(f"👤 {(fn or 'کاربر').strip()[:20]} ({uid})", f"adm_p:u:card:{uid}")])
                kb.append(_back("u"))
                return _hsend(chat_id, "\n".join(lines), _kb(*kb))
            if args and act in ("card", "add", "sub", "set", "ban", "dm", "ords"):
                uid = int(args[0])
                if act == "card":
                    ack()
                    t, k = _user_card(uid)
                    return show(t, k)
                if act in ("add", "sub", "set"):
                    ack()
                    name = {"add": "uadd", "sub": "usub", "set": "uset"}[act]
                    ttl = {"add": "➕ <b>افزودن شاهی</b>", "sub": "➖ <b>کسر شاهی</b>", "set": "🎯 <b>تنظیم موجودی</b>"}[act]
                    return _ask(chat_id, admin_id, name, "u", f"{ttl}\nکاربر: {_label(uid)}\n🪙 دارایی فعلی: <b>{_t(get_balance(uid))}</b> شاهی\n\nمقدار را بفرستید:",
                                uid=uid, then=["card", uid])
                if act == "ban":
                    if uid in ADMIN_IDS:
                        return ack("ادمین را نمی‌شود مسدود کرد.", True)
                    with get_db() as c:
                        c.execute("UPDATE users SET banned = 1 - banned, updated_at=CURRENT_TIMESTAMP WHERE id=?", (uid,))
                    ack("وضعیت کاربر تغییر کرد.")
                    t, k = _user_card(uid)
                    return show(t, k)
                if act == "dm":
                    ack()
                    return _ask(chat_id, admin_id, "udm", "u", f"✉️ پیام برای {_label(uid)}\n\nمتن پیام را بفرستید:", uid=uid, then=["card", uid])
                if act == "ords":
                    ack()
                    with get_db() as c:
                        rq = c.execute("SELECT tracking_code, member_count, status FROM requests WHERE user_id=? ORDER BY created_at DESC LIMIT 5", (uid,)).fetchall()
                        so = c.execute("SELECT tracking_code, service, quantity, status FROM service_orders WHERE user_id=? ORDER BY created_at DESC LIMIT 5", (uid,)).fetchall()
                    st = {"completed": "✅ تکمیل", "pending": "⏳ در انتظار", "cancelled": "❌ لغو", "removed": "🚫 ربات عزل شد", "relinked": "🔗 لینک تغییر کرد", "deleted": "🗑 حذف شد", "in_progress": "⏳ در حال انجام"}
                    lines = [f"📦 <b>سفارش‌های کاربر</b> <code>{uid}</code>", LINE, "<b>درخواست‌های JFJ:</b>"]
                    lines += [f"• <code>{c0}</code> • {_n(m)} ممبر • {st.get(s0, s0)}" for c0, m, s0 in rq] or ["—"]
                    lines += ["", "<b>سفارش‌های خدمات:</b>"]
                    lines += [f"• <code>{c0}</code> • {_h(sv)} × {_n(q)} • {st.get(s0, s0)}" for c0, sv, q, s0 in so] or ["—"]
                    return _hsend(chat_id, "\n".join(lines), _kb([_ab("🔙 کارت کاربر", f"adm_p:u:card:{uid}")]))

        # --- بسته‌ها (شاهی / اسپانسر) ---
        if sec in ("j", "p"):
            kind = sec
            qf = "tokens" if kind == "j" else "hours"
            unit = "شاهی" if kind == "j" else "ساعت"
            if sec == "p" and act == "last":
                ack()
                with get_db() as c:
                    rows = c.execute("SELECT product_name, buyer_id, created_at FROM invoices WHERE kind='sponsor' AND status='paid' ORDER BY created_at DESC LIMIT 10").fetchall()
                if not rows:
                    return _hsend(chat_id, "هنوز اسپانسری فروخته نشده است.", _kb(_back("p")))
                lines = ["📋 <b>آخرین اسپانسرها</b>", LINE]
                lines += [f"🎗 {_h(pn)}\n👤 {_label(b)}\n⏰ {_fa_dt(cr)}\n" for pn, b, cr in rows]
                return _hsend(chat_id, "\n".join(lines), _kb(_back("p")))
            if act == "pa":
                ack()
                return _ask(chat_id, admin_id, "pk_add_q", sec, f"➕ <b>بسته‌ی جدید</b>\n\nمقدار بسته را به <b>{unit}</b> بفرستید:", kind=kind)
            pid = args[0] if args else None
            pack = next((p for p in _packs(kind) if p["id"] == pid), None) if pid else None
            if act in ("pk", "pe", "pd", "pdc") and not pack:
                ack("این بسته دیگر وجود ندارد.", True)
                return home()
            if act == "pk":
                ack()
                return show(f"✏️ <b>ویرایش بسته</b>\n{LINE}\n📦 {_pack_label(kind, pack)}\n\nچه چیزی را تغییر می‌دهید؟",
                            _kb([_ab(f"🔢 مقدار ({unit})", f"adm_p:{sec}:pe:{pid}:q", PRIMARY), _ab("💰 قیمت", f"adm_p:{sec}:pe:{pid}:p", PRIMARY)],
                                [_ab("🗑 حذف بسته", f"adm_p:{sec}:pd:{pid}", DANGER)], _back(sec)))
            if act == "pe":
                ack()
                what = args[1]
                label = f"مقدار جدید را به {unit}" if what == "q" else "قیمت جدید را به تومان"
                return _ask(chat_id, admin_id, f"pk_edit_{what}", sec, f"✏️ بسته‌ی فعلی: {_pack_label(kind, pack)}\n\n{label} بفرستید:", kind=kind, pid=pid)
            if act == "pd":
                ack()
                if len(_packs(kind)) <= 1:
                    return _hsend(chat_id, "❗️ حداقل یک بسته باید باقی بماند.")
                return show(f"🗑 <b>حذف بسته</b>\n\n{_pack_label(kind, pack)}\n\nمطمئنید؟",
                            _kb([_ab("✅ بله، حذف شود", f"adm_p:{sec}:pdc:{pid}", DANGER), _ab("❌ انصراف", f"adm_p:{sec}:pk:{pid}", SUCCESS)]))
            if act == "pdc":
                if len(_packs(kind)) <= 1:
                    return ack("حداقل یک بسته باید باقی بماند.", True)
                _save_packs(kind, [p for p in _packs(kind) if p["id"] != pid])
                ack("بسته حذف شد.")
                return home()

        # --- زیرمجموعه ---
        if sec == "r" and act == "top":
            ack()
            with get_db() as c:
                rows = c.execute("SELECT referred_by, COUNT(*), SUM(referral_rewarded) FROM users WHERE referred_by IS NOT NULL GROUP BY referred_by ORDER BY COUNT(*) DESC LIMIT 10").fetchall()
            if not rows:
                return _hsend(chat_id, "هنوز کسی زیرمجموعه‌ای نیاورده است.", _kb(_back("r")))
            lines = ["🏆 <b>برترین معرف‌ها</b>", LINE]
            for i, (rid, cnt, rw) in enumerate(rows, 1):
                lines.append(f"{fa_digits(str(i))}. {_label(rid)}\n   👥 {_n(cnt)} زیرمجموعه • ✅ {_n(rw or 0)} پاداش")
            return _hsend(chat_id, "\n".join(lines), _kb(_back("r")))

        # --- سفارشات تکمیل نشده ---
        if sec == "o":
            off = int(args[0]) if args else 0
            if act in ("svc", "inv"):
                ack()
                return _send_list(chat_id, act, off)
            if act == "req":
                ack()
                return _send_requests(chat_id, off)
    except Exception:
        logging.exception("admin_panel_callback failed: %s", cq.get("data"))
    ack()


def _broadcast(chat_id, mid, text):
    with get_db() as c:
        ids = [r[0] for r in c.execute("SELECT id FROM users WHERE banned=0").fetchall()]
    ok = fail = 0
    for uid in ids:
        r = send(uid, text, markdown=False)
        if r.get("ok"):
            ok += 1
        else:
            fail += 1
        time.sleep(0.05)
    _hedit(chat_id, mid, f"📣 <b>پیام همگانی تمام شد</b>\n{LINE}\n✅ موفق: <b>{_n(ok)}</b>\n❌ ناموفق: <b>{_n(fail)}</b> (بلاک‌کرده‌ها)",
           _kb(_back("s")))


def handle_svc_buy_jtoken(cq):
    user = cq["from"]
    chat_id = cq["message"]["chat"]["id"]
    answer_callback(cq["id"])
    start_jtoken_purchase(chat_id, user["id"])


# ===================== پنل مدیریت: تنظیمات محصولات =====================
ADMIN_PRODUCTS_PROMPT = "👇 *یک گزینه را انتخاب کنید.*"
PRODUCT_STATUS_TEXT = "در این بخش میتوانید محصولات رو موجود یا ناموجود کنید."
ADMIN_PRODUCT_BUTTONS = {BTN_PROD_STATUS, BTN_PROD_LAYOUT} | {d["admin_btn"] for d in PRODUCT_DEFS.values()}
_ADMIN_BTN_TO_KEY = {d["admin_btn"]: k for k, d in PRODUCT_DEFS.items()}


def admin_products_menu():
    d = PRODUCT_DEFS
    return {
        "keyboard": [
            [btn(BTN_PROD_STATUS)],
            [btn(d["views"]["admin_btn"]), btn(d["reaction"]["admin_btn"])],
            [btn(d["stars"]["admin_btn"]), btn(d["members"]["admin_btn"])],
            [btn(d["premium"]["admin_btn"])],
            [btn(BTN_PROD_LAYOUT)],
            [btn(BACK_BTN, DANGER)],
        ],
        "resize_keyboard": True,
        "is_persistent": False,
    }


def start_admin_panel(chat_id, user_id):
    set_state(user_id, "admin_panel")
    admin_dashboard(chat_id)


def start_admin_products(chat_id, user_id):
    set_state(user_id, "admin_products")
    send(chat_id, ADMIN_PRODUCTS_PROMPT, admin_products_menu())


# ---------- وضعیت موجود/ناموجود ----------
def product_status_keyboard():
    rows = [[btn_inline("وضعیت", "noop"), btn_inline("عنوان", "noop")]]
    for key in PRODUCT_ORDER:
        p = get_product(key)
        rows.append([
            btn_inline("🟢 موجود" if p["enabled"] else "🔴 ناموجود", f"adm_toggle:{key}"),
            btn_inline(p["title"], "noop"),
        ])
    return {"inline_keyboard": rows}


# ---------- چیدمان دکمه‌ها ----------
def layout_text():
    lines = [" ، ".join(PRODUCT_DEFS[k]["menu_label"] for k in reversed(row)) for row in get_layout()]
    return "اینجا میتونی جایگاه دکمه هاتو عوض کنی.\n\nچیدمان فعلی:\n" + "\n".join(lines)


def layout_keyboard():
    rows = [[btn_inline("جایگاه", "noop"), btn_inline("طبقه", "noop"), btn_inline("عنوان", "noop")]]
    for key in PRODUCT_ORDER:
        rows.append([
            btn_inline("⬅️", f"adm_mv:l:{key}"),
            btn_inline("➡️", f"adm_mv:r:{key}"),
            btn_inline("⬆️", f"adm_mv:u:{key}"),
            btn_inline("⬇️", f"adm_mv:d:{key}"),
            btn_inline(PRODUCT_DEFS[key]["title"], "noop"),
        ])
    return {"inline_keyboard": rows}


# ---------- تنظیمات هر محصول (حداقل خرید و قیمت) ----------
def product_settings_text(key):
    p = get_product(key)
    return (
        f"*{p['admin_btn']}*\n\n"
        f"🔢 *حداقل خرید: {fmt_num(p['min_qty'])} عدد*\n"
        f"🪙 *قیمت: {fmt_tokens(p['rate_cost'])} شاهی به ازای هر {fmt_num(p['rate_per'])} عدد*"
    )


def product_settings_keyboard(key):
    return {"inline_keyboard": [[
        btn_inline("✏️ تغییر حداقل خرید", f"adm_min:{key}"),
        btn_inline("💰 تغییر قیمت", f"adm_price:{key}"),
    ]]}


def handle_admin_products_button(chat_id, user_id, text):
    set_state(user_id, "admin_products")  # اگر وسط ویرایش عدد بود، از آن خارج می‌شود
    if text == BTN_PROD_STATUS:
        send(chat_id, PRODUCT_STATUS_TEXT, product_status_keyboard(), markdown=False)
    elif text == BTN_PROD_LAYOUT:
        send(chat_id, layout_text(), layout_keyboard(), markdown=False)
    else:
        key = _ADMIN_BTN_TO_KEY[text]
        send(chat_id, product_settings_text(key), product_settings_keyboard(key))


def handle_admin_edit_min(chat_id, user_id, text, data):
    key = data["product"]
    n = parse_number(text)
    if n is None or n != int(n) or n < 1:
        send(chat_id, "❗️ *یک عدد صحیح و بزرگ‌تر از صفر ارسال کنید.*")
        return
    set_product_field(key, "min_qty", int(n))
    set_state(user_id, "admin_products")
    send(chat_id, "✅ *حداقل خرید ذخیره شد.*\n\n" + product_settings_text(key), product_settings_keyboard(key))


def handle_admin_edit_price(chat_id, user_id, text, data):
    key = data["product"]
    n = parse_number(text)
    if n is None or round(n, 2) <= 0:
        send(chat_id, "❗️ *یک عدد بزرگ‌تر از صفر ارسال کنید (اعشار مجاز است).*")
        return
    set_product_field(key, "rate_cost", round(n, 2))
    set_state(user_id, "admin_products")
    send(chat_id, "✅ *قیمت ذخیره شد.*\n\n" + product_settings_text(key), product_settings_keyboard(key))


def handle_admin_callback(cq):
    user_id = cq["from"]["id"]
    if not is_admin(user_id):
        answer_callback(cq["id"])
        return
    if cq.get("data", "").startswith("adm_p:"):
        admin_panel_callback(cq)
        return
    chat_id = cq["message"]["chat"]["id"]
    message_id = cq["message"]["message_id"]
    parts = cq["data"].split(":")
    action = parts[0]

    if action in ("adm_so_ok", "adm_so_no") and len(parts) == 2:
        handle_admin_service_order(cq, parts[1], action == "adm_so_ok")
        return
    if action in ("adm_inv_ok", "adm_inv_no") and len(parts) == 2:
        handle_admin_invoice(cq, parts[1], action == "adm_inv_ok")
        return

    if action == "adm_toggle" and len(parts) == 2 and parts[1] in PRODUCT_DEFS:
        key = parts[1]
        set_product_field(key, "enabled", 0 if get_product(key)["enabled"] else 1)
        edit(chat_id, message_id, PRODUCT_STATUS_TEXT, product_status_keyboard(), markdown=False)
        answer_callback(cq["id"])
    elif action == "adm_mv" and len(parts) == 3 and parts[2] in PRODUCT_DEFS:
        new_layout = move_in_layout(get_layout(), parts[2], parts[1])
        if new_layout is None:
            answer_callback(cq["id"], "⚠️ این دکمه بیشتر از این در این جهت جابه‌جا نمی‌شود.")
            return
        set_layout(new_layout)
        edit(chat_id, message_id, layout_text(), layout_keyboard(), markdown=False)
        answer_callback(cq["id"])
    elif action in ("adm_min", "adm_price") and len(parts) == 2 and parts[1] in PRODUCT_DEFS:
        key = parts[1]
        p = get_product(key)
        answer_callback(cq["id"])
        if action == "adm_min":
            set_state(user_id, "admin_edit_min", {"product": key})
            send(chat_id, f"🔢 *حداقل خرید جدید را ارسال کنید.*\n*(فعلی: {fmt_num(p['min_qty'])} عدد)*")
        else:
            set_state(user_id, "admin_edit_price", {"product": key})
            send(
                chat_id,
                f"💰 *قیمت جدید را ارسال کنید (شاهی به ازای هر {fmt_num(p['rate_per'])} عدد).*\n"
                f"*(فعلی: {fmt_tokens(p['rate_cost'])} شاهی)*",
            )
    else:
        answer_callback(cq["id"])


# ===================== پنل مدیریت: آمار ربات =====================
def _utc_str(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def collect_stats():
    now = now_local()
    today_start = _utc_str(now.replace(hour=0, minute=0, second=0, microsecond=0))
    active_cutoff = _utc_str(now - timedelta(hours=24))
    st = {}
    with get_db() as c:
        def one(sql, params=()):
            return c.execute(sql, params).fetchone()[0] or 0

        st["users"] = one("SELECT COUNT(*) FROM users")
        st["new_today"] = one("SELECT COUNT(*) FROM users WHERE created_at >= ?", (today_start,))
        st["active"] = one("SELECT COUNT(*) FROM users WHERE updated_at >= ?", (active_cutoff,))
        st["referred"] = one("SELECT COUNT(*) FROM users WHERE referred_by IS NOT NULL")

        st["jfj_requests"] = one("SELECT COUNT(*) FROM requests")
        st["joins"] = one("SELECT COUNT(*) FROM joins")
        st["leaves"] = one("SELECT COUNT(*) FROM joins WHERE left_at IS NOT NULL")
        st["members_requested"] = one("SELECT COALESCE(SUM(member_count), 0) FROM requests")
        st["jfj_tokens"] = one("SELECT COALESCE(SUM(token_cost), 0) FROM requests")

        st["balance_total"] = one("SELECT COALESCE(SUM(tokens), 0) FROM users")
        st["rewarded_referrals"] = one("SELECT COUNT(*) FROM users WHERE referral_rewarded = 1")
        st["transfer_tokens"] = one("SELECT COALESCE(SUM(amount), 0) FROM transfers")
        st["transfer_count"] = one("SELECT COUNT(*) FROM transfers")

        st["svc_total"] = one("SELECT COUNT(*) FROM service_orders")
        st["svc_tokens"] = one("SELECT COALESCE(SUM(token_cost), 0) FROM service_orders")
        by_service = dict(c.execute("SELECT service, COUNT(*) FROM service_orders GROUP BY service").fetchall())

        st["referrers"] = one("SELECT COUNT(DISTINCT referred_by) FROM users WHERE referred_by IS NOT NULL")
        st["top_referrer"] = one(
            "SELECT COALESCE(MAX(cnt), 0) FROM "
            "(SELECT COUNT(*) AS cnt FROM users WHERE referred_by IS NOT NULL GROUP BY referred_by)"
        )

        paid = c.execute("SELECT kind, final_amount, meta FROM invoices WHERE status = 'paid'").fetchall()

    # فاکتورهای موفق (status='paid')؛ فعلاً هیچ‌جای ربات این وضعیت را ثبت نمی‌کند
    bought_tokens = jt_sales = sp_sales = total_sales = 0
    for kind, amount, meta in paid:
        total_sales += amount
        if kind == "jtoken":
            jt_sales += amount
            try:
                bought_tokens += json.loads(meta or "{}").get("tokens", 0)
            except Exception:
                pass
        elif kind == "sponsor":
            sp_sales += amount

    st["paid_invoices"] = len(paid)
    st["bought_tokens"] = bought_tokens
    st["jt_sales"] = jt_sales
    st["sp_sales"] = sp_sales
    st["total_sales"] = total_sales
    st["product_sales"] = len(paid) + st["svc_total"]
    st["spent_tokens"] = st["jfj_tokens"] + st["svc_tokens"]
    st["referral_tokens"] = st["rewarded_referrals"] * REFERRAL_REWARD
    st["svc_views"] = by_service.get(SIMPLE_SERVICES["views"]["order_name"], 0)
    st["svc_members"] = by_service.get(SIMPLE_SERVICES["members"]["order_name"], 0)
    st["svc_stars"] = by_service.get(SIMPLE_SERVICES["stars"]["order_name"], 0)
    st["svc_reaction"] = by_service.get(REACTION_ORDER_NAME, 0)
    st["svc_premium"] = by_service.get(PREMIUM_ORDER_NAME, 0)
    return st


def stats_text():
    s = collect_stats()

    t0 = time.perf_counter()
    res = tg("getMe", _timeout=10)
    ping = f"{int((time.perf_counter() - t0) * 1000)} میلی‌ثانیه" if res.get("ok") else "نامشخص"

    N = fmt_num
    lines = [
        "📊 آمار ربات",
        "",
        f"👤 تعداد کل کاربران: {N(s['users'])} نفر",
        f"🆕 کاربران جدید امروز: {N(s['new_today'])} نفر",
        f"🟢 کاربران فعال: {N(s['active'])} نفر",
        f"👥 تعداد کل زیرمجموعه‌ها: {N(s['referred'])} نفر",
        "",
        f"📋 تعداد کل درخواست JFJ: {N(s['jfj_requests'])} عدد",
        f"🛰 تعداد کل Join کاربران: {N(s['joins'])} عدد",
        f"🚪 تعداد کل Leave کاربران: {N(s['leaves'])} عدد",
        f"👥 تعداد کل اعضای درخواست‌شده: {N(s['members_requested'])} نفر",
        f"💎 تعداد شاهی مصرف‌شده در JFJ: {N(s['jfj_tokens'])} شاهی",
        "",
        f"🏦 موجودی کل کاربران: {N(s['balance_total'])} شاهی",
        f"🛍 تعداد کل شاهی خریداری‌شده: {N(s['bought_tokens'])} شاهی",
        f"🪙 تعداد شاهی دریافت‌شده از زیرمجموعه: {N(s['referral_tokens'])} شاهی",
        f"🎰 تعداد شاهی انتقال‌یافته: {N(s['transfer_tokens'])} شاهی",
        f"📩 تعداد شاهی مصرف‌شده: {N(s['spent_tokens'])} شاهی",
        "",
        f"⭐️ تعداد کل فروش محصولات: {N(s['product_sales'])} سفارش",
        f"👛 تعداد کل فاکتورهای موفق: {N(s['paid_invoices'])} عدد",
        f"💎 جمع فروش شاهی: {N(s['jt_sales'])} تومان",
        f"💰 جمع فروش اسپانسری: {N(s['sp_sales'])} تومان",
        f"👝 جمع کل فروش: {N(s['total_sales'])} تومان",
        "",
        f"📦 تعداد کل سفارشات: {N(s['svc_total'])} سفارش",
        f"👁️‍🗨️ تعداد سفارشات ویو: {N(s['svc_views'])} سفارش",
        f"👥 تعداد سفارشات ممبر: {N(s['svc_members'])} سفارش",
        f"⭐️ تعداد سفارشات استارز: {N(s['svc_stars'])} سفارش",
        f"🎄 تعداد سفارشات ری‌اکشن: {N(s['svc_reaction'])} سفارش",
        f"💎 تعداد سفارشات ری‌اکشن پرمیومی: {N(s['svc_premium'])} سفارش",
        f"📤 تعداد شاهی مصرف‌شده خدمات: {N(s['svc_tokens'])} شاهی",
        f"📥 تعداد کل انتقالات شاهی: {N(s['transfer_count'])} تراکنش",
        "",
        f"🏆 تعداد معرف‌ها: {N(s['referrers'])} نفر",
        f"🎁 مجموع پاداش زیرمجموعه‌ها: {N(s['referral_tokens'])} شاهی",
        f"👑 بیشترین زیرمجموعه یک کاربر: {N(s['top_referrer'])} نفر",
        "",
        f"📡 پینگ ربات: {ping}",
    ]
    return "\n".join(f"*{ln}*" if ln else "" for ln in lines)


def stats_keyboard():
    return {"inline_keyboard": [[btn_inline("🔄 بروزرسانی", "admin_stats_refresh")]]}


def send_admin_stats(chat_id):
    send(chat_id, stats_text(), stats_keyboard())


def handle_admin_stats_refresh(cq):
    if not is_admin(cq["from"]["id"]):
        answer_callback(cq["id"])
        return
    chat_id = cq["message"]["chat"]["id"]
    message_id = cq["message"]["message_id"]
    edit(chat_id, message_id, stats_text(), stats_keyboard())
    answer_callback(cq["id"], "✅ بروزرسانی شد")


# ===================== پشتیبانی =====================
def send_support(chat_id):
    _t = get_setting("support_text")
    if _t:
        send(chat_id, _t.replace("{support}", SUPPORT_ID), markdown=False)
        return
    send(
        chat_id,
        "☎️ *پشتیبانی*\n\n"
        "🔭 *لطفا موضوع و توضیحات خود را در یک قالب مسیج ارسال کرده تا برای پاسخگویی زمان کمتری منظتر بمانید!*\n\n"
        f"{SUPPORT_ID}",
    )


# ===================== راهنما (/help) =====================
HELP_TEXT = (
    "💡 *راهنما*\n\n"
    "👈🏻 *تو این ربات شما یه محیط ساده و فضای رایگان و عالی رو در اختیار دارین تا رایگان ممبر های کانالتون یا "
    "گروهتون رو با JFJ رفتن بالا ببرید.*\n\n"
    "🤖 *کار ربات JFJ هم همینه که فضای مناسب JFJ رفتن رو براتون فراهم کنه تا با کمترین دردسر و سرعت بالا بتونید "
    "JFJ برید.*\n\n"
    "🚥 *اما JFJ چیه عمو؟*\n"
    "این کلمه مخفف Join for Join هست به معنی جفج یا همون عضو شو کانالم تا عضو شم کانالت.\n\n"
    "👈🏻 *به این معناست که شما عضو میشید تو کانال یا گروه بقیه و اوناهم عضو کانال یا گروه شما میشن و هر دو طرف "
    "ممبر کاملا واقعی جذب میکنید.*\n\n"
    "⚠️ *نکته:*\n"
    "• اگر فردی از کانال-گروه شما لفت بدهد, مقدار شاهی به کیف پول شما بازمیگردد."
)


# ===================== فلوی بانک انتقال =====================
def bank_amount_prompt_text(user_id):
    balance = get_balance(user_id)
    return f"💰 *میخوای چند شاهی انتقال بدی؟*\n🏦 *موجودی: {fmt_tokens(balance)} شاهی*"


def start_bank_transfer(chat_id, user_id):
    set_state(user_id, "bank_wait_amount")
    send(chat_id, bank_amount_prompt_text(user_id), back_menu())


def handle_bank_wait_amount(chat_id, user_id, text):
    if not text.isdigit():
        send(chat_id, "❗️ *فقط عدد ارسال کنید.*")
        return

    amount = int(text)
    if amount < MIN_TRANSFER_AMOUNT:
        send(chat_id, f"🛑 *عدد ارسالی باید حداقل {MIN_TRANSFER_AMOUNT} باشه.*")
        return

    if get_balance(user_id) < amount:
        send(chat_id, "🛑 *موجودی کافی نیست!*", main_menu(user_id))
        clear_state(user_id)
        return

    set_state(user_id, "bank_wait_recipient", {"amount": amount})
    send(
        chat_id,
        f"🆔️ *ایدی عددی فردی که میخواهید {amount} شاهی به او انتقال دهید را ارسال کنید.*",
        back_menu(),
    )


def handle_bank_wait_recipient(chat_id, user_id, text, data):
    if not text.isdigit():
        send(chat_id, "❗️ *فقط عدد ارسال کنید.*")
        return

    recipient_id = int(text)
    amount = data["amount"]

    if recipient_id == user_id:
        send(chat_id, "🛑 *نمیتونید به خودتون انتقال بدید!*")
        return

    if not user_exists(recipient_id):
        send(chat_id, "🛑 *کاربر عضو ربات نیست, بهش بگو /start کنه!*")
        return

    if not transfer_tokens(user_id, recipient_id, amount):
        send(chat_id, "🛑 *موجودی کافی نیست!*", main_menu(user_id))
        clear_state(user_id)
        return

    clear_state(user_id)
    date_str, time_str = jalali_now_strings()
    send(
        chat_id,
        f"✅️ *مقدار {amount} شاهی به کاربر {recipient_id} با موفقیت انتقال یافت.*\n"
        f"⏰️ *زمان انتقال: {time_str} - {date_str}*",
        main_menu(user_id),
    )
    send(
        recipient_id,
        f"✅️ *مقدار {amount} شاهی از کاربر {user_id} دریافت شد.*\n"
        f"⏰️ *زمان دریافت: {time_str} - {date_str}*",
    )


# ===================== قوانین =====================
RULES_TEXT = (
    "📌 *قوانین استفاده از ربات*\n\n"
    "👈🏻 *کاربران می‌توانند خارج از ربات با یکدیگر اقدام به خرید و فروش شاهی کنند، اما مسئولیت "
    "تمامی معاملات بر عهده طرفین معامله است. در صورت بروز کلاهبرداری، اسکم، عدم تحویل یا هرگونه اختلاف، "
    "ربات و مدیریت هیچ مسئولیتی نخواهند داشت.*\n\n"
    "👈🏻 *تا زمان تکمیل شدن سفارش، ربات را از ادمینی کانال یا گروه خارج نکنید؛ در غیر این صورت ممکن است "
    "سفارش شما با مشکل مواجه شود و مراحل پیگیری این مورد ممکن است چند ساعت یا روز طول بکشد.*\n\n"
    "👈🏻 *پس از خرید اشتراک و یا موجودی ربات و فعال‌سازی آن، امکان لغو یا بازگشت وجه تحت هیچ شرایطی "
    "وجود ندارد.*"
)


def send_rules(chat_id):
    _r = get_setting("rules_text")
    if _r:
        send(chat_id, _r, markdown=False)
        return
    send(chat_id, RULES_TEXT)


# ===================== سفارش من =====================
def send_orders(chat_id, user_id):
    rows = get_recent_requests(user_id, 5)
    with get_db() as c:
        svc = c.execute(
            "SELECT tracking_code, service, quantity, link, status, token_cost FROM service_orders "
            "WHERE user_id=? ORDER BY created_at DESC, rowid DESC LIMIT 5", (user_id,)).fetchall()
        inv = c.execute(
            "SELECT code, product_name, final_amount, status FROM invoices "
            "WHERE buyer_id=? AND status IN ('awaiting_receipt','review','paid','rejected') "
            "ORDER BY created_at DESC LIMIT 5", (user_id,)).fetchall()
    if not rows and not svc and not inv:
        send(chat_id, "🛑 *شما هنوز هیچ سفارشی ثبت نکردید!*")
        return

    send(chat_id, "🔭", markdown=False)

    if rows:
        lines = ["🔍 *وضعیت درخواست های JFJ اخیر شما:*", ""]
        for code, member_count, link, status in rows:
            status = refresh_request_status(code, member_count, status, owner_id=user_id)
            status_emoji = "✅️" if status == "completed" else ("🚫" if status in ("removed", "deleted", "relinked") else "⏳️")
            status_text = "تکمیل شده" if status == "completed" else ("ربات عزل شد" if status == "removed" else "لینک تغییر کرد (کنسل شد)" if status == "relinked" else "حذف شد توسط مدیریت" if status == "deleted" else "درحال انجام")
            lines += [
                f"🔐 *کد پیگیری: {code}*",
                f"{status_emoji} *وضعیت: {status_text}*",
                f"👤 *تعداد ممبر درخواستی: {member_count}*",
                f"🔗 *لینک: {link}*",
                "",
                " ◽️◽️◽️◽️◽️◽️◽️",
                "",
            ]
        send(chat_id, "\n".join(lines).rstrip())

    if svc:
        st = {"completed": ("✅️", "تکمیل شده"), "cancelled": ("❌", "لغو شده (موجودی برگشت)"),
              "pending": ("⏳️", "در حال انجام")}
        lines = ["🛍 *سفارش‌های خرید محصولات شما:*", ""]
        for code, name, qty, link, status, cost in svc:
            e, t = st.get(status, ("⏳️", "در حال انجام"))
            lines += [
                f"🔐 *کد پیگیری: {code}*",
                f"📦 *محصول: {name}*",
                f"🔢 *تعداد: {qty}*",
                f"{e} *وضعیت: {t}*",
                f"🔗 *لینک: {link}*",
                "",
                " ◽️◽️◽️◽️◽️◽️◽️",
                "",
            ]
        send(chat_id, "\n".join(lines).rstrip())

    if inv:
        st = {"paid": ("✅️", "پرداخت تأیید شد"), "rejected": ("❌", "رد شد"),
              "review": ("⏳️", "در حال بررسی توسط ادمین"), "awaiting_receipt": ("⏳️", "منتظر ارسال رسید")}
        lines = ["🧾 *فاکتورهای اخیر شما:*", ""]
        for code, name, amount, status in inv:
            e, t = st.get(status, ("⏳️", status))
            lines += [
                f"🔐 *کد فاکتور: {code}*",
                f"📦 *محصول: {name}*",
                f"{e} *وضعیت: {t}*",
                "",
                " ◽️◽️◽️◽️◽️◽️◽️",
                "",
            ]
        send(chat_id, "\n".join(lines).rstrip())


# ===================== دکمه‌ی بازگشت (مشترک بین فلوها) =====================
def handle_back(chat_id, user_id, state):
    if state == "jfj_wait_link":
        set_state(user_id, "jfj_wait_count")
        send_jfj_count_prompt(chat_id, user_id)
    elif state == "bank_wait_recipient":
        set_state(user_id, "bank_wait_amount")
        send(chat_id, bank_amount_prompt_text(user_id), back_menu())
    elif state == "adm_in":
        start_admin_panel(chat_id, user_id)
    elif state in ("admin_edit_min", "admin_edit_price"):
        start_admin_products(chat_id, user_id)
    elif state == "admin_products":
        start_admin_panel(chat_id, user_id)
    else:  # jfj_wait_count, bank_wait_amount -> اولین قدم فلو، برگشت به منوی اصلی
        clear_state(user_id)
        send_main_menu(chat_id, user_id, back=True)


# ===================== پردازش پیام‌ها =====================
def handle_message(message):
    user = message["from"]
    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()

    is_new = not user_exists(user["id"])
    referrer_id = None
    m = re.match(r"^/start(?:@\w+)?\s+ref(\d+)", text)
    if is_new and m:
        candidate = int(m.group(1))
        if candidate != user["id"] and user_exists(candidate):
            referrer_id = candidate

    upsert_user(user, referred_by=referrer_id)

    if is_new and referrer_id:
        notify_new_referral(referrer_id, user)

    state, data = get_state(user["id"])
    if is_admin(user["id"]) and message["chat"].get("type") == "private":
        try:
            rep_nag_admin(chat_id, user["id"], state, data)
        except Exception:
            logging.exception("rep_nag_admin")

    if message.get("contact"):
        handle_contact(message)
        return
    if phone_gate(message):
        return
    _blk = section_blocked(user["id"], text)
    if _blk:
        send(chat_id, f"🛑 بخش ({_blk}) فعلا غیرفعال میباشد!", markdown=False)
        return

    if is_admin(user["id"]) and state == "adm_in" and data.get("name") == "rs_wait" and message.get("document") \
            and message["chat"].get("type") == "private":
        rs_receive(message)
        return

    if is_admin(user["id"]) and state == "adm_in" and data.get("name") == "rich" and data.get("kind") \
            and text not in ADMIN_SECTION_BTNS and text != BACK_BTN:
        rich_receive(message, data)
        return

    if (message.get("photo") or message.get("document") or (text and not text.startswith("/"))) \
            and state not in ("sps", "dc_wait", "adm_in") and handle_receipt(message):
        return

    if state == "sps" and text and text != BACK_BTN:
        handle_sps_text(chat_id, user["id"], text, data)
    elif state == "dc_wait" and text and text != BACK_BTN:
        handle_dc_text(chat_id, user["id"], text, data)
    elif state == "sponsor_wait_link" and text and text != BACK_BTN:
        handle_sponsor_channel(chat_id, user, text, data)
    elif text == BACK_BTN and state:
        handle_back(chat_id, user["id"], state)
    elif is_admin(user["id"]) and text in ADMIN_SECTION_BTNS:
        admin_open_section(chat_id, user["id"], ADMIN_SECTION_BTNS[text])
    elif is_admin(user["id"]) and state == "adm_in" and text:
        admin_handle_input(chat_id, user, text, data)
    elif is_admin(user["id"]) and text in ADMIN_PRODUCT_BUTTONS:
        handle_admin_products_button(chat_id, user["id"], text)
    elif state == "admin_edit_min":
        handle_admin_edit_min(chat_id, user["id"], text, data)
    elif state == "admin_edit_price":
        handle_admin_edit_price(chat_id, user["id"], text, data)
    elif state == "jfj_wait_count":
        handle_jfj_wait_count(chat_id, user["id"], text)
    elif state == "jfj_wait_link":
        handle_jfj_wait_link(chat_id, user["id"], text, data)
    elif state == "bank_wait_amount":
        handle_bank_wait_amount(chat_id, user["id"], text)
    elif state == "bank_wait_recipient":
        handle_bank_wait_recipient(chat_id, user["id"], text, data)
    elif state == "svc_wait_qty":
        handle_svc_wait_qty(chat_id, user["id"], text, data)
    elif state == "svc_wait_link":
        handle_svc_wait_link(chat_id, user["id"], text, data)
    elif state == "react_wait_qty":
        handle_react_wait_qty(chat_id, user["id"], text, data)
    elif state == "premium_wait_qty":
        handle_premium_wait_qty(chat_id, user["id"], text)
    elif text == BTN_MINIAPP:
        mu = miniapp_url()
        if mu:
            send(chat_id, "👇 برای ورود به مینی‌اپ روی دکمه‌ی زیر بزنید.",
                 {"inline_keyboard": [[{"text": BTN_MINIAPP, "web_app": {"url": mu}}]]}, markdown=False)
        else:
            send_main_menu(chat_id, user["id"], back=True)
    elif text == BTN_REQUEST_JFJ:
        start_jfj_request(chat_id, user["id"])
    elif text == BTN_START_JFJ:
        start_jfj_browsing(chat_id, user["id"])
    elif text == BTN_TRANSFER_BANK:
        start_bank_transfer(chat_id, user["id"])
    elif text == BTN_BUY_JTOKEN:
        start_jtoken_purchase(chat_id, user["id"])
    elif text == BTN_BUY_SERVICES:
        start_services_menu(chat_id, user["id"])
    elif text == BTN_SUPPORT:
        send_support(chat_id)
    elif text == BTN_MY_ACCOUNT:
        send_account(chat_id, user["id"], user.get("first_name"))
    elif text == BTN_RULES:
        send_rules(chat_id)
    elif text == BTN_MY_ORDERS:
        send_orders(chat_id, user["id"])
    elif text == BTN_ADMIN_PANEL and is_admin(user["id"]):
        start_admin_panel(chat_id, user["id"])
    elif text == BTN_ADMIN_PRODUCTS and is_admin(user["id"]):
        start_admin_products(chat_id, user["id"])
    elif text == BTN_ADMIN_STATS and is_admin(user["id"]):
        send_admin_stats(chat_id)
    elif text == "/help":
        send(chat_id, HELP_TEXT)
    elif text == "/sponser":
        send_sponsor_menu(chat_id)
    else:
        send_main_menu(chat_id, user["id"], back=not text.startswith("/start"))


# =====================================================================
#  نسخه‌ی ۲ — امکانات تازه‌ی ربات
#  (پیام‌رسانی با فرمت اصلی، همگانی با کرون، جوین اجباری، احراز شماره، محصول اختصاصی)
# =====================================================================
def _utcnow_str(dt=None):
    return (dt or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M:%S")


def v2_migrate():
    alters = [
        "ALTER TABLE users ADD COLUMN card_blocked INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN phone TEXT",
        "ALTER TABLE users ADD COLUMN phone_req INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE invoices ADD COLUMN method TEXT",
        "ALTER TABLE invoices ADD COLUMN ref TEXT",
        "ALTER TABLE invoices ADD COLUMN receipt_chat INTEGER",
        "ALTER TABLE invoices ADD COLUMN receipt_mid INTEGER",
    ]
    with get_db() as c:
        for stmt in alters:
            try:
                c.execute(stmt)
            except sqlite3.OperationalError:
                pass
        c.execute("""CREATE TABLE IF NOT EXISTS user_products (
            user_id INTEGER NOT NULL, key TEXT NOT NULL, PRIMARY KEY (user_id, key))""")
        c.execute("""CREATE TABLE IF NOT EXISTS discount_codes (
            code TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL DEFAULT 0,
            kind TEXT NOT NULL,
            value REAL NOT NULL,
            expires_at TEXT,
            used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS sponsor_subs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            invoice_code TEXT,
            hours REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            started_at TEXT,
            ends_at TEXT,
            chat_kind TEXT,
            link_kind TEXT,
            chat_ref TEXT,
            invite_link TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS bc_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER, src_chat INTEGER, src_mid INTEGER,
            audience TEXT, targets TEXT, idx INTEGER NOT NULL DEFAULT 0,
            ok INTEGER NOT NULL DEFAULT 0, fail INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'running',
            prog_chat INTEGER, prog_mid INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        for _col in ("pin", "fwd"):
            try:
                c.execute(f"ALTER TABLE bc_jobs ADD COLUMN {_col} INTEGER NOT NULL DEFAULT 0")
            except sqlite3.OperationalError:
                pass
        # اشتراک‌های قدیمیِ پرداخت‌شده که هنوز ردیف ندارند
        old = c.execute(
            "SELECT i.code, i.buyer_id, i.meta, i.created_at FROM invoices i WHERE i.kind='sponsor' AND i.status='paid' "
            "AND NOT EXISTS (SELECT 1 FROM sponsor_subs s WHERE s.invoice_code=i.code)").fetchall()
        for code, buyer, meta, created in old:
            try:
                hours = float(json.loads(meta or "{}").get("hours", 0))
            except Exception:
                hours = 0
            try:
                st = datetime.strptime(created[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except Exception:
                st = datetime.now(timezone.utc)
            c.execute(
                "INSERT INTO sponsor_subs (user_id, invoice_code, hours, status, started_at, ends_at) VALUES (?,?,?,?,?,?)",
                (buyer, code, hours, "active", _utcnow_str(st), _utcnow_str(st + timedelta(hours=hours))))


def sbool(key, default="0"):
    return get_setting(key, default) == "1"


def sjson(key, default):
    raw = get_setting(key)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except ValueError:
        return default


def _fmt_dur(seconds):
    seconds = float(seconds)
    if seconds >= 3600 and seconds % 3600 == 0:
        return f"{_n(int(seconds // 3600))} ساعت"
    if seconds >= 60 and seconds % 60 == 0:
        return f"{_n(int(seconds // 60))} دقیقه"
    return f"{_t(seconds)} ثانیه"


# ---------- دسترسی محصول (عمومی یا اختصاصی کاربر) ----------
def user_has_product(uid, key):
    with get_db() as c:
        return c.execute("SELECT 1 FROM user_products WHERE user_id=? AND key=?", (uid, key)).fetchone() is not None


def product_open(uid, key):
    return get_product(key)["enabled"] or user_has_product(uid, key)


# ---------- ارسال/کپی دقیق پیام (فرمت، پریمیوم‌ایموجی، مدیا همان‌طور که هست) ----------
def copy_msg(to_chat, from_chat, mid):
    r = tg("copyMessage", chat_id=to_chat, from_chat_id=from_chat, message_id=mid)
    return r


def forward_msg(to_chat, from_chat, mid):
    return tg("forwardMessage", chat_id=to_chat, from_chat_id=from_chat, message_id=mid)


def send_rich(to_chat, from_chat, mid, fwd=False):
    return forward_msg(to_chat, from_chat, mid) if fwd else copy_msg(to_chat, from_chat, mid)


RICH_KINDS = {
    "photo": "🖼 دارای عکس",
    "voice": "🎙 دارای ویس",
    "sticker": "🎭 دارای استیکر",
    "gif": "🎞 دارای گیف",
    "text": "📝 متن خالی (بدون مدیا)",
    "forward": "↪️ فوروارد",
}


def msg_kind(m):
    if m.get("sticker"):
        return "sticker"
    if m.get("animation"):
        return "gif"
    if m.get("photo"):
        return "photo"
    if m.get("voice"):
        return "voice"
    if m.get("text"):
        return "text"
    return None


def rich_start(chat_id, admin_id, purpose, back, **extra):
    set_state(admin_id, "adm_in", dict(name="rich", purpose=purpose, back=back, kind=None, **extra))
    rows = [[_ab(RICH_KINDS["photo"], "adm_p:x:rk:photo", PRIMARY), _ab(RICH_KINDS["voice"], "adm_p:x:rk:voice", PRIMARY)],
            [_ab(RICH_KINDS["sticker"], "adm_p:x:rk:sticker", PRIMARY), _ab(RICH_KINDS["gif"], "adm_p:x:rk:gif", PRIMARY)],
            [_ab(RICH_KINDS["text"], "adm_p:x:rk:text", SUCCESS), _ab(RICH_KINDS["forward"], "adm_p:x:rk:forward", SUCCESS)],
            [_ab("❌ انصراف", "adm_p:x:rx", DANGER)]]
    ttl = {"dm": "✉️ <b>پیام به کاربر</b>", "bc": "📣 <b>ارسال اطلاعیه</b>"}[purpose]
    if extra.get("aud") == "chan":
        ttl = "📡 <b>همگانی درخواست JFJ</b>"
    _hsend(chat_id, f"{ttl}\n{LINE}\nپیام شما چه نوعی است؟ 👇\n\n"
                    "<i>ربات دقیقاً همان پیامی را که می‌فرستید ارسال می‌کند: bold، کج‌نویس، خط‌خورده، اسپویلر، "
                    "لینک، کد و ایموجی‌ها (حتی پریمیوم) همه حفظ می‌شوند.</i>", _kb(*rows))


def rich_receive(message, data):
    chat_id = message["chat"]["id"]
    admin_id = message["from"]["id"]
    kind = "forward" if data.get("kind") == "forward" else msg_kind(message)
    if kind != data.get("kind"):
        _hsend(chat_id, f"❗️ نوع پیام با گزینه‌ی انتخابی (<b>{RICH_KINDS[data['kind']]}</b>) نمی‌خواند؛ دوباره بفرستید یا نوع را عوض کنید.",
               _kb([_ab("🔁 تغییر نوع پیام", "adm_p:x:rch", PRIMARY), _ab("❌ انصراف", "adm_p:x:rx", DANGER)]))
        return
    data = dict(data, src_chat=chat_id, src_mid=message["message_id"])
    set_state(admin_id, "adm_in", data)
    pr = send_rich(chat_id, chat_id, message["message_id"], data.get("kind") == "forward")
    if not pr.get("ok"):
        _hsend(chat_id, "❗️ پیش‌نمایش پیام ممکن نشد؛ دوباره بفرستید.")
        return
    if data["purpose"] == "dm":
        q = f"✉️ بالا پیش‌نمایش پیام است. برای {_label(data['uid'])} ارسال شود؟"
    else:
        aud = data["aud"]
        q = (f"📣 بالا پیش‌نمایش اطلاعیه است.\nگیرندگان: <b>{AUD_LABELS[aud]}</b> — <b>{_n(len(bc_targets(aud)))}</b> "
             f"{'کانال/گروه' if aud == 'chan' else 'نفر'}\n"
             f"⏱ فاصله‌ی ارسال بین هر دو نفر: <b>{_fmt_dur(cron_sec())}</b>\n\nمطمئنید؟")
    if data["purpose"] == "dm":
        _hsend(chat_id, q, _kb([_ab("✅ ارسال", "adm_p:x:rgo", SUCCESS), _ab("❌ انصراف", "adm_p:x:rx", DANGER)]))
    else:
        _hsend(chat_id, q + "\n\n📌 پیام بعد از ارسال برای گیرندگان <b>پین</b> بشود؟",
               _kb([_ab("📌 ارسال و پین", "adm_p:x:rgop", SUCCESS)],
                   [_ab("✅ ارسال بدون پین", "adm_p:x:rgo", PRIMARY)],
                   [_ab("❌ انصراف", "adm_p:x:rx", DANGER)]))


# ---------- مخاطبان و ارسال همگانی با فاصله‌ی زمانی (کرون) ----------
AUD_LABELS = {"all": "همه‌ی کاربران", "active": "کاربران فعال (۷ روز اخیر)", "new": "کاربران جدید (۷ روز اخیر)",
              "chan": "تمام کانال‌ها و گروه‌ها"}


_adm_chan_cache = [0, []]


def admin_channels(force=False):
    """کانال/گروه‌هایی که ربات در آن‌ها ادمین است (از درخواست‌ها، اسپانسرها و جوین اجباری) — ۵ دقیقه کش"""
    if not force and time.time() - _adm_chan_cache[0] < 300:
        return _adm_chan_cache[1]
    refs = []
    with get_db() as c:
        refs += [r[0] for r in c.execute("SELECT DISTINCT chat_id FROM requests WHERE chat_id IS NOT NULL").fetchall()]
        refs += [r[0] for r in c.execute("SELECT DISTINCT chat_ref FROM sponsor_subs WHERE chat_ref IS NOT NULL AND chat_ref!=''").fetchall()]
    refs += [e["ref"] for e in sjson("fj_list", []) if e.get("ref")]
    uniq = []
    for r in refs:
        if r not in uniq:
            uniq.append(r)

    def chk(ref):
        try:
            ch = tg("getChat", chat_id=ref, _timeout=10)
            if not ch.get("ok") or ch["result"].get("type") not in ("channel", "group", "supergroup"):
                return None
            m = tg("getChatMember", chat_id=ref, user_id=BOT_ID or 0, _timeout=10)
            if m.get("ok") and m["result"].get("status") in ("administrator", "creator"):
                return {"id": ch["result"]["id"], "title": ch["result"].get("title") or str(ref)}
        except Exception:
            pass
        return None
    out, seen = [], set()
    if uniq:
        with ThreadPoolExecutor(max_workers=min(8, len(uniq))) as ex:
            for r in ex.map(chk, uniq):
                if r and r["id"] not in seen:
                    seen.add(r["id"])
                    out.append(r)
    _adm_chan_cache[0] = time.time()
    _adm_chan_cache[1] = out
    return out


def bc_targets(aud):
    if aud == "chan":
        return [c["id"] for c in admin_channels()]
    q = {"all": "SELECT id FROM users WHERE banned=0",
         "active": "SELECT id FROM users WHERE banned=0 AND updated_at >= datetime('now','-7 days')",
         "new": "SELECT id FROM users WHERE banned=0 AND created_at >= datetime('now','-7 days')"}[aud]
    with get_db() as c:
        return [r[0] for r in c.execute(q).fetchall()]


def cron_sec():
    try:
        return max(0.05, float(get_setting("cron_sec", "1")))
    except ValueError:
        return 1.0


def bc_create(admin_id, chat_id, src_chat, src_mid, aud, pin=0, fwd=0):
    targets = bc_targets(aud)
    with get_db() as c:
        cur = c.execute(
            "INSERT INTO bc_jobs (admin_id, src_chat, src_mid, audience, targets, prog_chat, pin, fwd) VALUES (?,?,?,?,?,?,?,?)",
            (admin_id, src_chat, src_mid, aud, json.dumps(targets), chat_id, 1 if pin else 0, 1 if fwd else 0))
        jid = cur.lastrowid
    r = _hsend(chat_id, _bc_progress_text(jid), _kb([_ab("⛔ توقف ارسال", f"adm_p:x:bcc:{jid}", DANGER)]))
    if r.get("ok"):
        with get_db() as c:
            c.execute("UPDATE bc_jobs SET prog_mid=? WHERE id=?", (r["result"]["message_id"], jid))
    return jid


def _bc_progress_text(jid):
    with get_db() as c:
        row = c.execute("SELECT audience, targets, idx, ok, fail, status, pin FROM bc_jobs WHERE id=?", (jid,)).fetchone()
    if not row:
        return "—"
    aud, targets, idx, ok, fail, status, pin = row
    total = len(json.loads(targets))
    left = max(total - idx, 0)
    eta = _fmt_dur(left * cron_sec()) if left and status == "running" else "—"
    st = {"running": "🟢 در حال ارسال…", "done": "✅ تمام شد", "cancelled": "⛔ متوقف شد"}.get(status, status)
    return (f"{'📡 <b>همگانی درخواست JFJ</b>' if aud == 'chan' else '📣 <b>ارسال اطلاعیه</b>'} — {AUD_LABELS.get(aud, aud)}\n{LINE}\n{st}\n"
            f"📤 ارسال‌شده: <b>{_n(idx)}</b> از <b>{_n(total)}</b>\n"
            f"✅ موفق: <b>{_n(ok)}</b> • ❌ ناموفق: <b>{_n(fail)}</b>\n"
            f"📌 پین: <b>{'بله' if pin else 'خیر'}</b>\n"
            f"⏱ فاصله‌ی ارسال: <b>{_fmt_dur(cron_sec())}</b>\n"
            f"⌛ زمان باقی‌مانده: <b>{eta}</b>")


def bc_step():
    """یک پیام از صف همگانی را می‌فرستد. True یعنی کاری انجام شد."""
    with get_db() as c:
        job = c.execute("SELECT id, src_chat, src_mid, targets, idx, ok, fail, prog_chat, prog_mid, pin, fwd FROM bc_jobs "
                        "WHERE status='running' ORDER BY id LIMIT 1").fetchone()
    if not job:
        return False
    jid, src_chat, src_mid, targets, idx, ok, fail, prog_chat, prog_mid, pin, fwd = job
    targets = json.loads(targets)
    finished = idx >= len(targets)
    if not finished:
        r = send_rich(targets[idx], src_chat, src_mid, fwd)
        if not r.get("ok") and r.get("error_code") == 429:
            time.sleep(float((r.get("parameters") or {}).get("retry_after", 3)) + 0.5)
            return True
        good = bool(r.get("ok"))
        if good and pin:
            try:
                tg("pinChatMessage", chat_id=targets[idx], message_id=r["result"]["message_id"], disable_notification=True)
            except Exception:
                pass
        with get_db() as c:
            c.execute("UPDATE bc_jobs SET idx=idx+1, ok=ok+?, fail=fail+? WHERE id=? AND status='running'",
                      (1 if good else 0, 0 if good else 1, jid))
        idx += 1
        finished = idx >= len(targets)
    if finished:
        with get_db() as c:
            c.execute("UPDATE bc_jobs SET status='done' WHERE id=? AND status='running'", (jid,))
    if prog_chat and prog_mid and (finished or idx % 5 == 0 or idx == 1):
        _hedit(prog_chat, prog_mid, _bc_progress_text(jid),
               None if finished else _kb([_ab("⛔ توقف ارسال", f"adm_p:x:bcc:{jid}", DANGER)]))
    return True


def bc_worker():
    while True:
        try:
            if bc_step():
                time.sleep(cron_sec())
            else:
                time.sleep(2)
        except Exception:
            logging.exception("bc_worker error")
            time.sleep(3)


# ---------- جوین اجباری ----------
_fj_cache = {}


def fj_entries():
    out = []
    if sbool("fj_enabled"):
        out += [e for e in sjson("fj_list", []) if e.get("ref")]
    with get_db() as c:
        rows = c.execute("SELECT chat_ref, invite_link FROM sponsor_subs WHERE status='active' AND ends_at > ? "
                         "AND chat_ref IS NOT NULL AND chat_ref != ''", (_utcnow_str(),)).fetchall()
    seen = {e["ref"] for e in out}
    for ref, link in rows:
        if ref in seen:
            continue
        seen.add(ref)
        out.append({"ref": ref, "title": ref, "sponsor": 1,
                    "link": link or (f"https://t.me/{ref[1:]}" if ref.startswith("@") else "")})
    return out


_fj_warned = {}


def _fj_warn_admins(ref, desc):
    """اگر ربات نتواند عضویت را بررسی کند (مثلاً ادمین کانال نیست) هر ۶ ساعت یک‌بار به ادمین‌ها خبر می‌دهد"""
    now = time.time()
    if now - _fj_warned.get(ref, 0) < 6 * 3600:
        return
    _fj_warned[ref] = now
    if str(ref).startswith("jfj:"):
        text = (f"⚠️ <b>بررسی عضویت در شروع JFJ ناموفق بود</b>\n"
                f"سفارش: <code>{_h(str(ref)[4:])}</code>\n"
                f"جزئیات: <code>{_h(str(desc))[:300]}</code>\n\n"
                f"✅ بررسی کن ربات هنوز در آن کانال/گروه <b>ادمین</b> است و لینک سفارش درست است.")
        for aid in ADMIN_IDS:
            tg("sendMessage", chat_id=aid, text=text, parse_mode="HTML")
        return
    text = (f"⚠️ <b>جوین اجباری کار نمی‌کند</b>\n"
            f"ربات نمی‌تواند عضویت در <code>{_h(str(ref))}</code> را بررسی کند، پس این کانال فعلاً چک نمی‌شود.\n"
            f"دلیل: <code>{_h(str(desc))[:200]}</code>\n\n"
            f"✅ راه‌حل: ربات را در همین کانال/گروه <b>ادمین</b> کن و آیدی را درست وارد کن.")
    for aid in ADMIN_IDS:
        tg("sendMessage", chat_id=aid, text=text, parse_mode="HTML")


_fj_info_cache = {}


def fj_info(e):
    """عنوان و لینک عضویت کانال/گروه (از getChat؛ ۱ ساعت کش می‌شود)"""
    ref = e["ref"]
    hit = _fj_info_cache.get(ref)
    if hit and time.time() - hit[0] < (3600 if hit[1].get("title") else 60):
        base = hit[1]
    else:
        base = {}
        try:
            r = tg("getChat", chat_id=ref, _timeout=10)
            if r.get("ok"):
                ch = r["result"]
                base["title"] = ch.get("title")
                if ch.get("username"):
                    base["link"] = "https://t.me/" + ch["username"]
                elif ch.get("invite_link"):
                    base["link"] = ch["invite_link"]
        except Exception:
            pass
        _fj_info_cache[ref] = (time.time(), base)
    title = e.get("title") if (e.get("title") and e.get("title") != ref) else None
    link = e.get("link") or base.get("link") or (f"https://t.me/{ref[1:]}" if str(ref).startswith("@") else "")
    return {"title": title or base.get("title") or str(ref), "link": link, "sponsor": bool(e.get("sponsor"))}


def _fj_status(uid, ref):
    # هر بار مستقیم از تلگرام پرسیده می‌شود (کش فقط ۳ ثانیه، برای درخواست‌های هم‌زمان یک کاربر)
    hit = _fj_cache.get((uid, ref))
    if hit and time.time() - hit[0] < 3:
        return hit[1]
    r = {}
    for attempt in range(3):
        r = tg("getChatMember", chat_id=ref, user_id=uid, _timeout=10)
        if r.get("ok"):
            break
        d = str(r.get("description") or r.get("error_description") or r.get("error") or "").lower()
        if any(x in d for x in ("chat not found", "not enough rights", "member list is inaccessible",
                                "bot is not a member", "chat_admin_required", "user not found", "peer_id_invalid")):
            break  # خطای دائمی تنظیمات؛ تکرار فایده ندارد
        time.sleep(0.5 * (attempt + 1))
    if not r.get("ok"):
        _fj_warn_admins(ref, r.get("description") or r.get("error_description") or r.get("error") or "no response")
        return "unknown"  # کاربر را به‌خاطر خطای ربات/شبکه قفل نمی‌کنیم
    st = r["result"].get("status")
    if st == "restricted" and not r["result"].get("is_member", True):
        st = "left"
    if len(_fj_cache) > 5000:
        _fj_cache.clear()
    _fj_cache[(uid, ref)] = (time.time(), st)
    return st


def fj_forget(uid):
    for k in [k for k in _fj_cache if k[0] == uid]:
        _fj_cache.pop(k, None)


def fj_missing(uid):
    ents = fj_entries()
    if not ents:
        return []
    if len(ents) == 1:
        return [e for e in ents if _fj_status(uid, e["ref"]) in ("left", "kicked")]
    with ThreadPoolExecutor(max_workers=min(6, len(ents))) as ex:
        sts = list(ex.map(lambda e: _fj_status(uid, e["ref"]), ents))
    return [e for e, st in zip(ents, sts) if st in ("left", "kicked")]


def fj_gate(uid, chat_id, callback_id=None, data=""):
    """True یعنی کاربر باید اول در کانال‌ها عضو شود و کار متوقف شد"""
    if is_admin(uid) or data == "fj_check":
        return False
    try:
        missing = fj_missing(uid)
    except Exception:
        logging.exception("fj_gate")
        return False
    if not missing:
        return False
    items = []
    for e in missing:
        i = fj_info(e)
        if i.get("link"):
            items.append({"text": i["title"], "url": i["link"]})
    rows = [items[k:k + 2] for k in range(0, len(items), 2)]
    rows.append([btn_inline("عضو شدم | بررسی ✅️", "fj_check", SUCCESS)])
    if callback_id:
        answer_callback(callback_id, "برای استفاده از ربات ابتدا در کانال‌های اجباری عضو شوید.", show_alert=True)
    if chat_id:
        send(chat_id, "🎇🎆 *خوش اومدی گلم ...*\n\nبرای استفاده از ربات، باید توی کانال زیر جوین شی!",
             {"inline_keyboard": rows})
    return True


def handle_fj_check(cq):
    uid = cq["from"]["id"]
    for k in [k for k in _fj_cache if k[0] == uid]:
        _fj_cache.pop(k, None)
    missing = fj_missing(uid)
    if missing:
        answer_callback(cq["id"], "هنوز در همه‌ی کانال‌ها عضو نشده‌اید.", show_alert=True)
        return
    answer_callback(cq["id"], "✅ عضویت شما تأیید شد.")
    cid = cq["message"]["chat"]["id"]
    tg("deleteMessage", chat_id=cid, message_id=cq["message"]["message_id"])
    send_main_menu(cid, uid)


# ---------- احراز شماره تلفن ----------
def user_phone(uid):
    with get_db() as c:
        r = c.execute("SELECT phone, phone_req FROM users WHERE id=?", (uid,)).fetchone()
    return (r[0], bool(r[1])) if r else (None, False)


def phone_keyboard():
    return {"keyboard": [[{"text": "📱 ارسال شماره‌ی من", "request_contact": True}]],
            "resize_keyboard": True, "one_time_keyboard": True}


def ask_phone(chat_id, why=""):
    send(chat_id, "📱 *برای ادامه باید شماره‌ی تلفن حساب تلگرام خودتان را تأیید کنید.*\n\n"
                  "👇 *روی دکمه‌ی «ارسال شماره‌ی من» بزنید.*" + (f"\n\n{why}" if why else ""), phone_keyboard())


def phone_gate(message):
    """اگر ادمین شماره‌ی کاربر را الزامی کرده، تا شماره نفرستد کار دیگری انجام نمی‌شود"""
    uid = message["from"]["id"]
    if is_admin(uid):
        return False
    phone, req = user_phone(uid)
    if not req or phone:
        return False
    ask_phone(message["chat"]["id"])
    return True


def handle_contact(message):
    uid = message["from"]["id"]
    chat_id = message["chat"]["id"]
    ct = message.get("contact") or {}
    if ct.get("user_id") != uid:
        send(chat_id, "❗️ *فقط شماره‌ی خودتان را (با دکمه‌ی ارسال شماره) بفرستید.*", phone_keyboard())
        return
    st, ctx = get_state(uid)
    with get_db() as c:
        c.execute("UPDATE users SET phone=?, phone_req=0 WHERE id=?", (str(ct.get("phone_number")), uid))
    send(chat_id, "✅ *شماره‌ی شما تأیید شد.*", main_menu(uid))
    if st == "pay_phone" and ctx:
        pay_make_invoice(chat_id, uid, ctx, ctx.get("method", "card"))
    else:
        clear_state(uid)


# =====================================================================
#  قیمت هر شاهی، تخفیف خرید، بونوس، کد تخفیف و روش‌های پرداخت
# =====================================================================
def unit_price():
    try:
        return float(get_setting("unit_price", "1000") or 0)  # پیش‌فرض: هر شاهی ۱٬۰۰۰ تومان؛ ۰ یعنی قیمت ثابت بسته‌ها
    except ValueError:
        return 0.0


def disc_tiers():
    now = time.time()
    return [t for t in sjson("disc_tiers", []) if not t.get("until") or t["until"] > now]


def jt_price_info(p):
    """(قیمت نهایی، قیمت پایه، درصد تخفیف) برای یک بسته‌ی شاهی"""
    tokens = p["tokens"]
    up = unit_price()
    base = int(round(tokens * up)) if up > 0 else int(p["price"])
    pct = 0
    for t in disc_tiers():
        if tokens >= t["min"] and t["pct"] > pct:
            pct = t["pct"]
    return int(round(base * (100 - pct) / 100)), base, pct


def bonus_state():
    def f(k, d="0"):
        try:
            return float(get_setting(k, d) or 0)
        except ValueError:
            return 0.0
    on = sbool("bonus_on")
    per, amount, hours, start = f("bonus_per"), f("bonus_amount"), f("bonus_hours"), f("bonus_start")
    ends = start + hours * 3600 if hours > 0 else 0
    active = on and per > 0 and amount > 0 and (hours <= 0 or time.time() < ends)
    return {"on": on, "active": active, "per": per, "amount": amount, "hours": hours, "ends": ends}


def bonus_for(tokens):
    b = bonus_state()
    if not b["active"]:
        return 0
    return round(int(tokens // b["per"]) * b["amount"], 2)


def jt_packs_view():
    out = []
    for p in JTOKEN_PRODUCTS:
        final, base, pct = jt_price_info(p)
        out.append({"id": p["id"], "tokens": p["tokens"], "price": final, "base": base, "pct": pct,
                    "bonus": bonus_for(p["tokens"])})
    return out


# ---------- کد تخفیف ----------
def dc_new_code():
    alpha = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    with get_db() as c:
        for _ in range(50):
            code = "OFF" + "".join(random.choice(alpha) for _ in range(6))
            if not c.execute("SELECT 1 FROM discount_codes WHERE code=?", (code,)).fetchone():
                return code
    raise RuntimeError("no code")


def dc_validate(code, uid):
    code = code.strip().upper().translate(_ASCII_DIGITS)
    with get_db() as c:
        r = c.execute("SELECT user_id, kind, value, expires_at, used FROM discount_codes WHERE code=?", (code,)).fetchone()
    if not r:
        return None, "❌ این کد تخفیف وجود ندارد."
    owner, kind, value, exp, used = r
    if owner and owner != uid:
        return None, "❌ این کد تخفیف برای شما نیست."
    if used:
        return None, "❌ این کد قبلاً استفاده شده است."
    if exp and exp < _utcnow_str():
        return None, "❌ مهلت این کد تخفیف تمام شده است."
    return {"code": code, "kind": kind, "value": value}, None


def dc_apply(price, d):
    if not d:
        return price
    if d["kind"] == "pct":
        out = price * (100 - d["value"]) / 100
    else:
        out = price - d["value"]
    return max(int(round(out)), 1000)


def dc_use(code):
    with get_db() as c:
        cur = c.execute("UPDATE discount_codes SET used=1 WHERE code=? AND used=0", (code,))
        return cur.rowcount == 1


def dc_release(code):
    if code:
        with get_db() as c:
            c.execute("UPDATE discount_codes SET used=0 WHERE code=?", (code,))


# ---------- روش‌های پرداخت ----------
METHOD_LABELS = {"card": "💳 کارت به کارت", "zarin": "🌐 درگاه زرین‌پال", "crypto": "🪙 ارزی آفلاین"}


def card_blocked(uid):
    with get_db() as c:
        r = c.execute("SELECT card_blocked FROM users WHERE id=?", (uid,)).fetchone()
    return bool(r and r[0])


def method_enabled(m):
    if m == "card":
        return sbool("pay_card", "1")
    if m == "zarin":
        return sbool("pay_zarin") and bool(get_setting("zarin_merchant"))
    if m == "crypto":
        return sbool("pay_crypto") and bool(get_setting("crypto_wallet")) and crypto_rate() > 0
    return False


def crypto_rate():
    try:
        return float(get_setting("crypto_rate", "0") or 0)
    except ValueError:
        return 0.0


def pay_methods_for(uid):
    out = []
    for m in ("card", "zarin", "crypto"):
        if method_enabled(m) and not (m == "card" and card_blocked(uid)):
            out.append(m)
    return out


def pay_item(kind, pack_id, dcode=None):
    """اطلاعات کالا و قیمت نهایی (بعد از تخفیف خرید و کد تخفیف)"""
    if kind == "sponsor":
        p = next((x for x in SPONSOR_PRODUCTS if x["id"] == pack_id), None)
        if not p:
            return None
        base = int(p["price"])
        name = f"اسپانسری {p['hours']} ساعته"
        meta = {"hours": p["hours"]}
    else:
        p = next((x for x in JTOKEN_PRODUCTS if x["id"] == pack_id), None)
        if not p:
            return None
        base, _, _ = jt_price_info(p)
        name = f"{p['tokens']} شاهی"
        meta = {"tokens": p["tokens"], "bonus": bonus_for(p["tokens"])}
    final = dc_apply(base, dcode)
    return {"name": name, "base": base, "final": final, "meta": meta}


def _price_lines(item, ctx):
    lines = [f"📦 *محصول: {item['name']}*"]
    if item["final"] != item["base"]:
        lines.append(f"🏷 *قیمت با کد تخفیف: {item['final']} تومان* (قبل از کد: {item['base']})")
    else:
        lines.append(f"💰 *قیمت: {item['final']} تومان*")
    b = item["meta"].get("bonus")
    if b:
        lines.append(f"🎁 *بونوس خرید: +{fmt_tokens(b)} شاهی*")
    return lines


def _ctx_conn():
    c = get_db()
    c.execute("CREATE TABLE IF NOT EXISTS pay_ctx (tok TEXT PRIMARY KEY, uid INTEGER NOT NULL, data TEXT NOT NULL, "
              "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    return c


def ctx_save(uid, ctx):
    """زمینه‌ی خرید در دیتابیس با یک شناسه‌ی کوتاه ذخیره می‌شود و داخل دکمه‌ها می‌آید؛
    پس دکمه‌ها مستقل از «وضعیت» کاربر کار می‌کنند (حتی اگر بین مراحل جای دیگری رفته باشد)"""
    import uuid
    ctx = dict(ctx)
    ctx["tok"] = ctx.get("tok") or uuid.uuid4().hex[:10]
    with _ctx_conn() as c:
        c.execute("INSERT INTO pay_ctx (tok, uid, data) VALUES (?,?,?) ON CONFLICT(tok) DO UPDATE SET data=excluded.data",
                  (ctx["tok"], uid, json.dumps(ctx)))
        c.execute("DELETE FROM pay_ctx WHERE created_at < datetime('now','-3 day')")
    return ctx


def ctx_load(tok, uid):
    with _ctx_conn() as c:
        r = c.execute("SELECT data FROM pay_ctx WHERE tok=? AND uid=?", (tok, uid)).fetchone()
    return json.loads(r[0]) if r else None


def ctx_drop(tok):
    if tok:
        with _ctx_conn() as c:
            c.execute("DELETE FROM pay_ctx WHERE tok=?", (tok,))


def pay_chooser(chat_id, uid, ctx, message_id=None, note=None):
    item = pay_item(ctx["kind"], ctx["pack"], ctx.get("dc"))
    methods = pay_methods_for(uid)
    if not item:
        send(chat_id, "🛑 *این بسته دیگر وجود ندارد.*")
        return
    if not methods:
        txt = "🛑 *در حال حاضر هیچ روش پرداختی برای شما فعال نیست.*\n\n☎️ *با پشتیبانی تماس بگیرید: " + SUPPORT_ID + "*"
        if message_id:
            edit(chat_id, message_id, txt, {"inline_keyboard": []})
        else:
            send(chat_id, txt)
        return
    ctx = ctx_save(uid, ctx)
    set_state(uid, "pay_ctx", ctx)
    tok = ctx["tok"]
    lines = ["🧾 *تأیید خرید*", ""] + _price_lines(item, ctx)
    if ctx.get("dc"):
        lines.append(f"🏷 *کد تخفیف اعمال‌شده: {ctx['dc']['code']}*")
    if note:
        lines += ["", note]
    lines += ["", "👇 *روش پرداخت را انتخاب کنید:*"]
    rows = [[btn_inline(METHOD_LABELS[m], f"pm:{m}:{tok}", SUCCESS)] for m in methods]
    rows.append([btn_inline("🏷 دارم کد تخفیف", f"pm_dc:{tok}", PRIMARY), btn_inline("❌ انصراف", f"pm_x:{tok}", DANGER)])
    text, kb = "\n".join(lines), {"inline_keyboard": rows}
    if message_id:
        r = edit(chat_id, message_id, text, kb)
        err = str((r or {}).get("description") or (r or {}).get("error_description") or "")
        if not (r or {}).get("ok") and "not modified" not in err.lower():
            send(chat_id, text, kb)  # ویرایش ممکن نبود (مثلاً پیام متنی نیست): پیام تازه می‌فرستیم
    else:
        send(chat_id, text, kb)


def pay_start(chat_id, uid, kind, pack_id, message_id=None, si=None):
    ctx = {"kind": kind, "pack": pack_id, "dc": None, "mid": message_id}
    if si:
        ctx["si"] = si
    pay_chooser(chat_id, uid, ctx, message_id)


def _ctx_of(uid):
    st, ctx = get_state(uid)
    return ctx if st in ("pay_ctx", "pay_phone") and ctx else None


def handle_pay_callback(cq):
    data = cq["data"]
    uid = cq["from"]["id"]
    chat_id = cq["message"]["chat"]["id"]
    mid = cq["message"]["message_id"]
    parts = data.split(":")
    cmd = parts[0]
    tok = parts[2] if cmd == "pm" and len(parts) > 2 else (parts[1] if cmd in ("pm_dc", "pm_x") and len(parts) > 1 else None)
    ctx = (ctx_load(tok, uid) if tok else None) or _ctx_of(uid)
    if cmd == "pm_x":
        answer_callback(cq["id"])
        ctx_drop(tok)
        if (get_state(uid)[0] or "") in ("pay_ctx", "dc_wait", "pay_phone"):
            clear_state(uid)
        edit(chat_id, mid, "❌ *خرید لغو شد.*", {"inline_keyboard": []})
        return
    if not ctx:
        answer_callback(cq["id"], "این مرحله تمام شده است. اگر فاکتور ساخته شده در همین گفتگو است؛ وگرنه دوباره از «خرید» شروع کنید.", show_alert=True)
        return
    ctx["mid"] = mid
    if cmd == "pm_dc":
        answer_callback(cq["id"])
        set_state(uid, "dc_wait", ctx)
        send(chat_id, "🏷 *کد تخفیف خود را ارسال کنید:*", back_menu())
        return
    method = parts[1] if len(parts) > 1 else ""
    if method not in pay_methods_for(uid):
        answer_callback(cq["id"], "این روش پرداخت فعال نیست.", show_alert=True)
        return
    answer_callback(cq["id"])
    if method == "card" and sbool("phone_verify") and not user_phone(uid)[0] and not is_admin(uid):
        set_state(uid, "pay_phone", dict(ctx, method="card"))
        ask_phone(chat_id, "ℹ️ *برای پرداخت کارت به کارت، تأیید شماره الزامی است.*")
        return
    pay_make_invoice(chat_id, uid, ctx, method)


def handle_dc_text(chat_id, uid, text, ctx):
    d, err = dc_validate(text, uid)
    if err:
        send(chat_id, err + "\n\n🏷 *کد دیگری بفرستید یا «بازگشت» را بزنید.*")
        return
    ctx = dict(ctx, dc=d)
    send(chat_id, "✅ *کد تخفیف ثبت شد.*", main_menu(uid))
    pay_chooser(chat_id, uid, ctx)


def pay_make_invoice(chat_id, uid, ctx, method):
    item = pay_item(ctx["kind"], ctx["pack"], ctx.get("dc"))
    if not item:
        send(chat_id, "🛑 *این بسته دیگر وجود ندارد.*")
        return
    if method not in pay_methods_for(uid):
        send(chat_id, "🛑 *این روش پرداخت فعال نیست.*")
        return
    dc = ctx.get("dc")
    if dc and not dc_use(dc["code"]):
        send(chat_id, "❌ *این کد تخفیف دیگر معتبر نیست.*")
        return
    meta = dict(item["meta"])
    if dc:
        meta["dc"] = dc["code"]
    if ctx.get("si"):
        meta["si"] = ctx["si"]
    usdt = None
    exact = None
    if method in ("zarin", "crypto"):
        exact = item["final"]
    if method == "crypto":
        usdt = round(item["final"] / crypto_rate(), 2)
        meta["usdt"] = usdt
    code, amount, _ = create_invoice(uid, uid, item["name"], item["final"], chat_id, None,
                                     kind=ctx["kind"], meta=meta, exact_amount=exact)
    paid_cb = ("sp_paid:" if ctx["kind"] == "sponsor" else "jt_paid:") + code
    clear_state(uid)
    ctx_drop(ctx.get("tok"))
    extra = "\n".join(_price_lines(item, ctx)[1:]) if (dc or meta.get("bonus")) else ""
    if method == "card":
        text = invoice_text(item["name"], amount, code)
        if extra:
            text = text.replace("💰 *مبلغ قابل پرداخت", extra + "\n💰 *مبلغ قابل پرداخت", 1)
        r = send(chat_id, text, invoice_keyboard(code, amount, paid_cb))
    elif method == "crypto":
        wallet, net = get_setting("crypto_wallet"), get_setting("crypto_net", "USDT")
        text = (f"🧾 *فاکتور خرید • {item['name']}*\n\n"
                + (extra + "\n" if extra else "")
                + f"🪙 *مبلغ قابل پرداخت: {usdt} {net}*\n"
                f"💵 *معادل: {item['final']} تومان*\n"
                f"🔍 *کد پیگیری فاکتور: {code}*\n"
                f"{stamp('زمان صدور فاکتور')}\n\n"
                f"👛 *آدرس کیف پول ({net}):*\n`{wallet}`\n\n"
                "⚠️ *نکته مهم:*\n"
                "۱. حتماً از همین شبکه واریز کنید و مبلغ را دقیق بفرستید.\n"
                "۲. پس از واریز روی «پرداخت کردم» بزنید و سپس *اسکرین‌شات یا هش تراکنش (TXID)* را ارسال کنید.")
        kb = {"inline_keyboard": [
            [{"text": "کپی آدرس کیف پول 👛", "copy_text": {"text": wallet}},
             {"text": "کپی مبلغ 💰", "copy_text": {"text": str(usdt)}}],
            [btn_inline("پرداخت کردم ✅️", paid_cb, SUCCESS)]]}
        r = send(chat_id, text, kb)
    else:  # zarin
        res = zp_request(item["final"], f"خرید {item['name']} (فاکتور {code})", code)
        if not res.get("ok"):
            set_invoice_status(code, "expired", expected_status="pending")
            dc_release(meta.get("dc"))
            send(chat_id, "🛑 *اتصال به درگاه پرداخت انجام نشد؛ چند دقیقه بعد دوباره تلاش کنید یا روش دیگری را انتخاب کنید.*")
            return
        with get_db() as c:
            c.execute("UPDATE invoices SET ref=? WHERE code=?", (res["authority"], code))
        text = (f"🧾 *فاکتور خرید • {item['name']}*\n\n"
                + (extra + "\n" if extra else "")
                + f"💰 *مبلغ قابل پرداخت: {item['final']} تومان*\n"
                f"🔍 *کد پیگیری فاکتور: {code}*\n"
                f"{stamp('زمان صدور فاکتور')}\n\n"
                "👇 *برای پرداخت آنلاین روی دکمه‌ی زیر بزنید. بعد از پرداخت، نتیجه خودکار اعلام می‌شود.*")
        kb = {"inline_keyboard": [[{"text": "💳 پرداخت آنلاین", "url": res["url"]}],
                                  [btn_inline("🔄 بررسی پرداخت", f"zp_chk:{code}", PRIMARY)]]}
        r = send(chat_id, text, kb)
    with get_db() as c:
        c.execute("UPDATE invoices SET method=?, message_id=? WHERE code=?",
                  (method, (r.get("result") or {}).get("message_id"), code))
    old = ctx.get("mid")
    if old:
        tg("deleteMessage", chat_id=chat_id, message_id=old)


# ---------- درگاه زرین‌پال ----------
def _zp_base():
    return "https://sandbox.zarinpal.com" if sbool("zarin_sandbox") else "https://api.zarinpal.com"


def _zp_call(path, payload):
    req = urllib.request.Request(_zp_base() + path, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read() or b"{}")
        except Exception:
            return {}
    except Exception as e:
        logging.warning("zarinpal failed: %s", e)
        return {}


def site_url():
    return (get_setting("site_url") or "").rstrip("/")


def zp_request(amount_toman, desc, code):
    base = site_url()
    if not base:
        return {"ok": False}
    res = _zp_call("/pg/v4/payment/request.json", {
        "merchant_id": get_setting("zarin_merchant"), "amount": int(amount_toman) * 10,
        "callback_url": f"{base}/zp/callback", "description": desc})
    data = res.get("data") or {}
    if data.get("code") == 100 and data.get("authority"):
        host = "https://sandbox.zarinpal.com" if sbool("zarin_sandbox") else "https://www.zarinpal.com"
        return {"ok": True, "authority": data["authority"], "url": f"{host}/pg/StartPay/{data['authority']}"}
    return {"ok": False}


def zp_verify_invoice(code):
    """True اگر پرداخت واقعاً انجام شده و فاکتور تازه به paid تبدیل شد؛ 'already' اگر قبلاً بوده"""
    with get_db() as c:
        row = c.execute("SELECT status, final_amount, ref, method FROM invoices WHERE code=?", (code,)).fetchone()
    if not row or row[3] != "zarin" or not row[2]:
        return False
    status, amount, authority, _ = row
    if status == "paid":
        return "already"
    if status not in ("pending", "expired"):
        return False
    res = _zp_call("/pg/v4/payment/verify.json", {
        "merchant_id": get_setting("zarin_merchant"), "amount": int(amount) * 10, "authority": authority})
    if (res.get("data") or {}).get("code") not in (100, 101):
        return False
    if set_invoice_status(code, "paid", expected_status=status):
        apply_paid_invoice(code)
        rep_ev_gateway(code)
        return True
    return "already"


def zp_callback_page(query):
    authority = (query.get("Authority") or [""])[0]
    ok_flag = (query.get("Status") or [""])[0] == "OK"
    with get_db() as c:
        row = c.execute("SELECT code FROM invoices WHERE ref=?", (authority,)).fetchone() if authority else None
    if not row:
        return False, "تراکنش پیدا نشد."
    if not ok_flag:
        return False, "پرداخت انجام نشد یا لغو شد."
    r = zp_verify_invoice(row[0])
    return (bool(r), "پرداخت با موفقیت انجام شد؛ به ربات برگردید." if r else "پرداخت تأیید نشد؛ اگر مبلغ کم شده در ربات «بررسی پرداخت» را بزنید.")


def handle_zp_check(cq):
    code = cq["data"].split(":", 1)[1]
    r = zp_verify_invoice(code)
    if r is True:
        answer_callback(cq["id"], "✅ پرداخت تأیید شد.")
        tg("editMessageReplyMarkup", chat_id=cq["message"]["chat"]["id"], message_id=cq["message"]["message_id"],
           reply_markup={"inline_keyboard": []})
    elif r == "already":
        answer_callback(cq["id"], "این فاکتور قبلاً پرداخت شده است.", show_alert=True)
    else:
        answer_callback(cq["id"], "هنوز پرداختی برای این فاکتور ثبت نشده است.", show_alert=True)


# ---------- اعمال فاکتور پرداخت‌شده (مشترک: تأیید ادمین و درگاه) ----------
def apply_paid_invoice(code):
    with get_db() as c:
        row = c.execute("SELECT buyer_id, kind, meta, product_name FROM invoices WHERE code=?", (code,)).fetchone()
    if not row:
        return
    buyer, kind, meta, product = row
    try:
        meta = json.loads(meta or "{}")
    except Exception:
        meta = {}
    if kind == "jtoken":
        tokens = meta.get("tokens", 0)
        bonus = meta.get("bonus", 0) or 0
        add_tokens(buyer, tokens + bonus)
        msg = f"✅ *پرداخت شما تأیید شد.*\n🔍 *کد فاکتور: {code}*\n{stamp('زمان تأیید')}\n\n🪙 *{fmt_tokens(tokens)} شاهی به حساب شما اضافه شد.*"
        if bonus:
            msg += f"\n🎁 *بونوس خرید: {fmt_tokens(bonus)} شاهی هم هدیه گرفتید!*"
        send(buyer, msg)
    elif kind == "sponsor":
        si = meta.get("si") or {}
        with get_db() as c:
            cur = c.execute(
                "INSERT INTO sponsor_subs (user_id, invoice_code, hours, status, chat_kind, link_kind, chat_ref, invite_link) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (buyer, code, meta.get("hours", 0), "pending", si.get("kind"), si.get("lk"), si.get("ref"), si.get("link")))
            sid = cur.lastrowid
        rep_ev_sponsor_new(sid, code)
        send(buyer, f"✅ *پرداخت شما تأیید شد.*\n🔍 *کد فاکتور: {code}*\n{stamp('زمان تأیید')}\n\n🎗 *اسپانسری شما بعد از بررسی ادمین فعال می‌شود و همین‌جا اطلاع می‌دهیم.*")
        txt = (f"🎗 اشتراک اسپانسری جدید (منتظر فعال‌سازی)\n{stamp('زمان تأیید پرداخت', md=False)}\n\n🔍 فاکتور: {code}\n📦 {product}\n"
               f"👤 {_user_label(buyer)}\n{_sponsor_info_text(si)}")
        kb = _kb([_ab("✅ فعال‌سازی", f"adm_p:sp:act:{sid}", SUCCESS), _ab("📄 جزئیات", f"adm_p:sp:sub:{sid}", PRIMARY)])
        for admin_id in ADMIN_IDS:
            tg("sendMessage", chat_id=admin_id, text=txt, reply_markup=kb)
    else:
        send(buyer, f"✅ *پرداخت شما تأیید شد.*\n🔍 *کد فاکتور: {code}*\n{stamp('زمان تأیید')}")
    rep_ev_invoice_paid(code)


def _sponsor_info_text(si):
    if not si:
        return "ℹ️ اطلاعات کانال ثبت نشده است."
    kind = "عمومی" if si.get("kind") == "public" else "خصوصی"
    lines = [f"📢 نوع: {kind}"]
    if si.get("kind") == "private":
        lines.append("🔗 نوع لینک: " + ("درخواستی (با تأیید ادمین)" if si.get("lk") == "request" else "عادی"))
        lines.append(f"🔗 لینک: {si.get('link', '—')}")
    lines.append(f"🆔 آیدی: {si.get('ref', '—')}")
    return "\n".join(lines)


# =====================================================================
#  خرید اسپانسری: گرفتن مشخصات کانال/گروه از کاربر
# =====================================================================
def _sps_cancel_kb():
    return {"inline_keyboard": [[btn_inline("❌ انصراف", "sps:x", DANGER)]]}


def sponsor_begin(chat_id, uid, pack_id, message_id=None):
    set_state(uid, "sps", {"pack": pack_id, "step": "type", "si": {}})
    text = ("🎗 *کانال/گروهی که می‌خواهید اسپانسر شود از چه نوعی است؟*\n\n"
            "🌐 *عمومی:* آیدی با @ دارد (مثل @mychannel)\n"
            "🔒 *خصوصی:* فقط با لینک دعوت عضو می‌شوند")
    kb = {"inline_keyboard": [[btn_inline("🌐 عمومی", "sps:t:public", SUCCESS), btn_inline("🔒 خصوصی", "sps:t:private", PRIMARY)],
                              [btn_inline("❌ انصراف", "sps:x", DANGER)]]}
    if message_id:
        edit(chat_id, message_id, text, kb)
    else:
        send(chat_id, text, kb)


def handle_sps_callback(cq):
    uid = cq["from"]["id"]
    chat_id = cq["message"]["chat"]["id"]
    mid = cq["message"]["message_id"]
    st, data = get_state(uid)
    parts = cq["data"].split(":")
    if parts[1] == "x":
        answer_callback(cq["id"])
        clear_state(uid)
        edit(chat_id, mid, "❌ *خرید اسپانسری لغو شد.*", {"inline_keyboard": []})
        return
    if st != "sps":
        answer_callback(cq["id"], "این مرحله منقضی شده؛ دوباره از اول شروع کنید.", show_alert=True)
        return
    answer_callback(cq["id"])
    si = data.get("si", {})
    if parts[1] == "t":
        si["kind"] = parts[2]
        if parts[2] == "public":
            data.update(step="ref", si=si)
            set_state(uid, "sps", data)
            edit(chat_id, mid, "🆔 *آیدی کانال/گروه را با @ ارسال کنید (مثل @mychannel):*", _sps_cancel_kb())
        else:
            data.update(step="lk", si=si)
            set_state(uid, "sps", data)
            edit(chat_id, mid, "🔗 *لینک دعوت کانال/گروه خصوصی شما از چه نوعی است؟*\n\n"
                               "🔗 *درخواستی:* کاربر باید درخواست عضویت بدهد و ادمین تأیید کند\n"
                               "🔓 *عادی:* کاربر مستقیم عضو می‌شود",
                 {"inline_keyboard": [[btn_inline("🔗 لینک درخواستی", "sps:l:request", PRIMARY),
                                       btn_inline("🔓 لینک عادی", "sps:l:plain", SUCCESS)],
                                      [btn_inline("❌ انصراف", "sps:x", DANGER)]]})
    elif parts[1] == "l":
        si["lk"] = parts[2]
        data.update(step="link", si=si)
        set_state(uid, "sps", data)
        edit(chat_id, mid, "🔗 *لینک دعوت کانال/گروه را ارسال کنید (مثل https://t.me/+AbCdEf):*", _sps_cancel_kb())


def handle_sps_text(chat_id, uid, text, data):
    t = text.strip().translate(_ASCII_DIGITS)
    step, si = data.get("step"), data.get("si", {})
    if step == "ref":
        m = re.fullmatch(r"(?:https?://)?(?:t\.me/)?@?([A-Za-z][A-Za-z0-9_]{3,31})", t)
        if not m:
            send(chat_id, "❗️ *آیدی نامعتبر است؛ مثل @mychannel بفرستید.*", _sps_cancel_kb())
            return
        si["ref"] = "@" + m.group(1)
        return sponsor_info_done(chat_id, uid, data, si)
    if step == "link":
        if not re.match(r"^https?://t\.me/\S+$", t):
            send(chat_id, "❗️ *لینک نامعتبر است؛ باید مثل https://t.me/+AbCdEf باشد.*", _sps_cancel_kb())
            return
        si["link"] = t
        data.update(step="id", si=si)
        set_state(uid, "sps", data)
        send(chat_id, "🆔 *آیدی عددی کانال/گروه را ارسال کنید (مثل -1001234567890):*\n\n"
                      "ℹ️ *می‌توانید آن را از ربات‌هایی مثل @userinfobot یا @getidsbot بگیرید.*", _sps_cancel_kb())
        return
    if step == "id":
        if not re.fullmatch(r"-?\d{6,}", t):
            send(chat_id, "❗️ *آیدی عددی نامعتبر است؛ مثل -1001234567890 بفرستید.*", _sps_cancel_kb())
            return
        si["ref"] = t if t.startswith("-") else "-100" + t
        return sponsor_info_done(chat_id, uid, data, si)
    send(chat_id, "👇 *از دکمه‌های بالا استفاده کنید.*", _sps_cancel_kb())


def sponsor_info_done(chat_id, uid, data, si):
    r = tg("getChatMember", chat_id=si["ref"], user_id=BOT_ID or 0, _timeout=10) if BOT_ID else {}
    warn = None
    if r.get("ok") and r["result"].get("status") not in ("administrator", "creator"):
        warn = "⚠️ *ربات هنوز در این کانال/گروه ادمین نیست؛ برای فعال‌سازی اسپانسری حتماً ربات را ادمین کنید.*"
    elif not r.get("ok"):
        warn = "⚠️ *ربات به این کانال/گروه دسترسی ندارد؛ آن را ادمین کنید تا اسپانسری فعال شود.*"
    send(chat_id, "✅ *مشخصات کانال/گروه ثبت شد.*" + (f"\n\n{warn}" if warn else ""), main_menu(uid))
    pay_start(chat_id, uid, "sponsor", data["pack"], None, si=si)


# =====================================================================
#  اشتراک‌های اسپانسری (مدیریت ادمین)
# =====================================================================
def sub_row(sid):
    with get_db() as c:
        return c.execute("SELECT id, user_id, invoice_code, hours, status, started_at, ends_at, chat_kind, link_kind, "
                         "chat_ref, invite_link FROM sponsor_subs WHERE id=?", (sid,)).fetchone()


def sub_state(status, ends_at):
    if status == "active" and ends_at and ends_at <= _utcnow_str():
        return "expired"
    return status


_SUB_ST = {"active": "🟢 فعال", "pending": "🟡 منتظر فعال‌سازی", "expired": "⚪ تمام‌شده", "cancelled": "🔴 لغوشده"}


def _remaining_text(ends_at):
    try:
        e = datetime.strptime(ends_at[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception:
        return "—"
    left = (e - datetime.now(timezone.utc)).total_seconds()
    if left <= 0:
        return "تمام شده"
    return f"{_n(int(left // 3600))} ساعت و {_n(int(left % 3600 // 60))} دقیقه"


def render_sub(sid):
    r = sub_row(sid)
    if not r:
        return "❌ این اشتراک پیدا نشد.", _kb([_ab("🔙 بازگشت", "adm_p:u:home")])
    _, uid, inv, hours, status, st_at, ends, ck, lk, ref, link = r
    stt = sub_state(status, ends)
    si = {"kind": ck, "lk": lk, "ref": ref or "—", "link": link or "—"}
    lines = ["🎗 <b>اشتراک اسپانسری</b>", LINE, f"👤 {_label(uid)}", f"🔖 شناسه‌ی اشتراک: <code>{sid}</code>",
             f"وضعیت: <b>{_SUB_ST[stt]}</b>", f"⏳ مدت: <b>{_t(hours)}</b> ساعت"]
    if status in ("active",) or ends:
        lines += [f"▶️ شروع: {_fa_dt(st_at)}", f"⏹ پایان: {_fa_dt(ends)}", f"⌛ باقی‌مانده: <b>{_remaining_text(ends)}</b>"]
    lines += [LINE, _h(_sponsor_info_text(si if ck or ref else {}))]
    if inv:
        lines.append(f"🧾 فاکتور: <code>{inv}</code>")
    rows = []
    if stt in ("pending", "expired", "cancelled"):
        rows.append([_ab("✅ فعال‌سازی (از همین الان)", f"adm_p:sp:act:{sid}", SUCCESS)])
    if stt == "active":
        rows.append([_ab("⛔ لغو اشتراک", f"adm_p:sp:can:{sid}", DANGER)])
    rows.append([_ab("➕ افزودن ساعت", f"adm_p:sp:ah:{sid}", SUCCESS), _ab("➖ کسر ساعت", f"adm_p:sp:sh:{sid}", DANGER)])
    rows.append([_ab("📄 مدارک ارسالی کاربر", f"adm_p:sp:doc:{sid}", PRIMARY), _ab("🗑 حذف", f"adm_p:sp:del:{sid}", DANGER)])
    rows.append([_ab("🔙 اشتراک‌های کاربر", f"adm_p:sp:ls:{uid}")])
    return "\n".join(lines), _kb(*rows)


def render_sub_list(uid):
    with get_db() as c:
        rows = c.execute("SELECT id, hours, status, ends_at FROM sponsor_subs WHERE user_id=? ORDER BY id DESC LIMIT 15", (uid,)).fetchall()
    lines = ["🎗 <b>اشتراک‌های اسپانسری کاربر</b>", LINE, f"👤 {_label(uid)}", ""]
    kb = []
    for sid, hours, status, ends in rows:
        stt = sub_state(status, ends)
        lines.append(f"• #{sid} — {_SUB_ST[stt]} — {_t(hours)} ساعت")
        kb.append([_ab(f"#{sid} • {_SUB_ST[stt]} • {_t(hours)} ساعت", f"adm_p:sp:sub:{sid}", PRIMARY)])
    if not rows:
        lines.append("هنوز اشتراکی ندارد.")
    kb.append([_ab("➕ ساخت اشتراک دستی", f"adm_p:sp:new:{uid}", SUCCESS)])
    kb.append([_ab("🔙 کارت کاربر", f"adm_p:u:card:{uid}")])
    return "\n".join(lines), _kb(*kb)


def sponsor_activate(sid):
    r = sub_row(sid)
    if not r:
        return False
    hours = r[3]
    now = datetime.now(timezone.utc)
    with get_db() as c:
        c.execute("UPDATE sponsor_subs SET status='active', started_at=?, ends_at=? WHERE id=?",
                  (_utcnow_str(now), _utcnow_str(now + timedelta(hours=hours)), sid))
    rep_ev_sponsor("act", sid)
    send(r[1], f"🎗 *اسپانسری شما فعال شد!*\n{stamp('زمان فعال‌سازی')}\n\n⏳ *مدت: {fmt_tokens(hours)} ساعت*\n"
               "📢 *کانال/گروه شما در جوین اجباری ربات قرار گرفت.*")
    return True


def sponsor_shift(sid, hours):
    """hours مثبت = افزودن (به کاربر اطلاع داده می‌شود)، منفی = کسر (بی‌صدا)"""
    r = sub_row(sid)
    if not r:
        return False
    status, ends = r[4], r[6]
    with get_db() as c:
        if status == "active" and ends:
            e = datetime.strptime(ends[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) + timedelta(hours=hours)
            c.execute("UPDATE sponsor_subs SET ends_at=?, hours=MAX(hours+?,0) WHERE id=?", (_utcnow_str(e), hours, sid))
        else:
            c.execute("UPDATE sponsor_subs SET hours=MAX(hours+?,0) WHERE id=?", (hours, sid))
    rep_ev_sponsor("ah" if hours > 0 else "sh", sid, f"{fmt_tokens(abs(hours))} ساعت")
    if hours > 0:
        send(r[1], f"🎁 *{fmt_tokens(hours)} ساعت به اشتراک اسپانسری شما اضافه شد.*\n{stamp('زمان ثبت')}")
    return True


def sponsor_docs(chat_id, sid):
    r = sub_row(sid)
    if not r:
        return
    si = {"kind": r[7], "lk": r[8], "ref": r[9] or "—", "link": r[10] or "—"}
    _hsend(chat_id, f"📄 <b>مدارک اشتراک #{sid}</b>\n{LINE}\n{_h(_sponsor_info_text(si if r[7] or r[9] else {}))}\n"
                    f"🧾 فاکتور: <code>{r[2] or '—'}</code>", _kb([_ab("🔙 اشتراک", f"adm_p:sp:sub:{sid}")]))
    if r[2]:
        with get_db() as c:
            rc = c.execute("SELECT receipt_chat, receipt_mid FROM invoices WHERE code=?", (r[2],)).fetchone()
        if rc and rc[0] and rc[1]:
            cp = tg("copyMessage", chat_id=chat_id, from_chat_id=rc[0], message_id=rc[1], caption="🧾 رسید ارسالی کاربر")
            if not cp.get("ok"):
                _hsend(chat_id, "ℹ️ رسید ذخیره‌شده دیگر قابل نمایش نیست.")
        else:
            _hsend(chat_id, "ℹ️ رسیدی ثبت نشده است (پرداخت از درگاه یا اشتراک دستی).")


# =====================================================================
#  صفحه‌های پنل ادمین (نسخه‌ی ۲)
# =====================================================================
def _onoff(b):
    return "🟢 روشن" if b else "🔴 خاموش"


def render_cron():
    cur = cron_sec()
    text = ("⏱ <b>تنظیم کرون (فاصله‌ی ارسال اطلاعیه)</b>\n" + LINE + "\n"
            f"فاصله‌ی فعلی بین ارسال پیام به هر دو نفر: <b>{_fmt_dur(cur)}</b>\n\n"
            "مثلاً اگر روی ۱۰ ثانیه باشد، ربات بعد از ارسال برای نفر اول، ۱۰ ثانیه صبر می‌کند و بعد برای نفر بعدی می‌فرستد.\n"
            "👇 <i>یک گزینه را بزنید یا مقدار دلخواه بفرستید.</i>")

    def pre(sec, label):
        return _ab(("✅ " if abs(cur - sec) < 1e-9 else "") + label, f"adm_p:x:cron_set:{sec}", PRIMARY)
    kb = _kb([pre(1, "۱ ثانیه"), pre(3, "۳ ثانیه"), pre(5, "۵ ثانیه")],
             [pre(10, "۱۰ ثانیه"), pre(30, "۳۰ ثانیه"), pre(60, "۱ دقیقه")],
             [pre(300, "۵ دقیقه"), pre(600, "۱۰ دقیقه")],
             [_ab("✏️ مقدار دلخواه", "adm_p:x:cron_in", SUCCESS)],
             [_ab("🔙 تنظیمات عمومی", "adm_p:g:home")])
    return text, kb


def render_fj():
    on = sbool("fj_enabled")
    lst = sjson("fj_list", [])
    lines = ["📢 <b>جوین اجباری</b>", LINE,
             f"وضعیت: <b>{_onoff(on)}</b>",
             "کاربر تا وقتی در همه‌ی کانال/گروه‌های زیر عضو نباشد نمی‌تواند از ربات (و مینی‌اپ) استفاده کند.",
             "ℹ️ ربات باید در هر کانال/گروه <b>ادمین</b> باشد؛ کانال‌های اسپانسرِ فعال هم خودکار به این فهرست اضافه می‌شوند.", ""]
    kb = [[_ab("🔴 خاموش کردن" if on else "🟢 روشن کردن", "adm_p:x:fj_tg", DANGER if on else SUCCESS)]]
    for i, e in enumerate(lst):
        lines.append(f"{fa_digits(str(i + 1))}. {_h(e.get('title') or e['ref'])} — <code>{_h(e['ref'])}</code>")
        kb.append([_ab(f"🗑 حذف {e.get('title') or e['ref']}", f"adm_p:x:fj_del:{i}", DANGER)])
    if not lst:
        lines.append("هنوز کانالی اضافه نشده است.")
    auto = [e for e in fj_entries() if e.get("sponsor")]
    if auto:
        lines += ["", "🎗 <b>اسپانسرهای فعال (خودکار؛ با پایان یا حذف اشتراک برداشته می‌شوند):</b>"]
        for e in auto:
            lines.append(f"• {_h(fj_info(e)['title'])} — <code>{_h(e['ref'])}</code>")
    kb.append([_ab("➕ افزودن کانال/گروه", "adm_p:x:fj_add", SUCCESS)])
    kb.append([_ab("🔙 تنظیمات عمومی", "adm_p:g:home")])
    return "\n".join(lines), _kb(*kb)


def render_pay():
    def line(m, extra):
        return f"{METHOD_LABELS[m]}: <b>{_onoff(sbool('pay_' + m, '1' if m == 'card' else '0'))}</b>\n{extra}"
    mer = get_setting("zarin_merchant")
    text = ("💳 <b>روش‌های پرداخت</b>\n" + LINE + "\n"
            + line("card", f"   🔢 <code>{_h(CARD_NUMBER)}</code> • {_h(CARD_HOLDER)}") + "\n\n"
            + line("zarin", f"   🔑 مرچنت: <code>{_h(mer[:6] + '…') if mer else '—'}</code> • حالت تست: {_onoff(sbool('zarin_sandbox'))}\n"
                            f"   🌐 آدرس سایت: <code>{_h(site_url() or '—')}</code>") + "\n\n"
            + line("crypto", f"   👛 <code>{_h(get_setting('crypto_wallet') or '—')}</code>\n"
                             f"   🪙 ارز/شبکه: <b>{_h(get_setting('crypto_net', 'USDT'))}</b> • نرخ هر واحد: <b>{_n(crypto_rate())}</b> تومان") + "\n\n"
            "ℹ️ اگر بیش از یک روش روشن باشد، کاربر هنگام خرید یکی را انتخاب می‌کند.")

    def tg_btn(m):
        on = sbool("pay_" + m, "1" if m == "card" else "0")
        return _ab(("🟢 " if on else "🔴 ") + METHOD_LABELS[m], f"adm_p:x:pay_tg:{m}", SUCCESS if on else DANGER)
    kb = _kb([tg_btn("card"), tg_btn("zarin")], [tg_btn("crypto")],
             [_ab("💳 شماره کارت", "adm_p:f:in:card", PRIMARY), _ab("👤 نام صاحب کارت", "adm_p:f:in:holder", PRIMARY)],
             [_ab("🔑 مرچنت زرین‌پال", "adm_p:x:pay_in:zp_merchant", PRIMARY), _ab("🌐 آدرس سایت", "adm_p:x:pay_in:site_url", PRIMARY)],
             [_ab("🧪 حالت تست زرین‌پال: " + ("روشن" if sbool("zarin_sandbox") else "خاموش"), "adm_p:x:pay_sb")],
             [_ab("👛 آدرس کیف پول", "adm_p:x:pay_in:crypto_wallet", PRIMARY), _ab("🪙 نام ارز/شبکه", "adm_p:x:pay_in:crypto_net", PRIMARY)],
             [_ab("💵 نرخ هر واحد ارز (تومان)", "adm_p:x:pay_in:crypto_rate", PRIMARY)],
             [_ab("🔙 مالی", "adm_p:f:home")])
    return text, kb


def render_bonus():
    b = bonus_state()
    if b["active"]:
        st = "🟢 فعال" + (f" — باقی‌مانده: {_fmt_dur(max(b['ends'] - time.time(), 0))}" if b["hours"] > 0 else " — بدون محدودیت زمان")
    elif b["on"] and b["hours"] > 0 and time.time() >= b["ends"]:
        st = "⚪ زمانش تمام شده"
    elif b["on"]:
        st = "🟡 روشن (تنظیمات ناقص: مقدار «به ازای» و «بونوس» را وارد کنید)"
    else:
        st = "🔴 خاموش"
    text = ("🎁 <b>بونوس خرید شاهی</b>\n" + LINE + "\n"
            f"وضعیت: <b>{st}</b>\n"
            f"📐 قانون: به ازای هر <b>{_t(b['per'])}</b> شاهی خرید، <b>{_t(b['amount'])}</b> شاهی هدیه\n"
            f"⏳ مدت: <b>{('بدون محدودیت' if b['hours'] <= 0 else _fmt_dur(b['hours'] * 3600))}</b>\n\n"
            "مثال: «به ازای ۵ شاهی، ۱ شاهی هدیه» یعنی کسی که ۱۰۰ شاهی بخرد، ۲۰ شاهی بونوس می‌گیرد.\n"
            "بونوس در فاکتور و صفحه‌ی خرید به کاربر نشان داده می‌شود و بعد از تأیید پرداخت اضافه می‌شود.\n"
            "⏳ با «روشن کردن»، شمارش زمان از همان لحظه شروع می‌شود (مدت ۰ = بی‌نهایت).")
    kb = _kb([_ab("🔴 خاموش کردن" if b["on"] else "🟢 روشن کردن", "adm_p:x:bon_tg", DANGER if b["on"] else SUCCESS)],
             [_ab("📐 به ازای هر … شاهی", "adm_p:x:bon_in:bonus_per", PRIMARY), _ab("🎁 مقدار بونوس", "adm_p:x:bon_in:bonus_amount", PRIMARY)],
             [_ab("⏳ مدت (ساعت)", "adm_p:x:bon_in:bonus_hours", PRIMARY)],
             [_ab("🔙 تنظیمات خرید شاهی", "adm_p:j:home")])
    return text, kb


def render_disc():
    up = unit_price()
    tiers = sjson("disc_tiers", [])
    now = time.time()
    lines = ["💵 <b>قیمت هر شاهی و تخفیف خرید</b>", LINE,
             "💰 قیمت هر ۱ شاهی: " + (f"<b>{_n(up)}</b> تومان (قیمت بسته‌ها = تعداد × این عدد)" if up > 0
                                      else "<b>تنظیم نشده</b> (از قیمت ثابت هر بسته استفاده می‌شود)"), "",
             "🏷 <b>تخفیف‌ها:</b>"]
    kb = []
    for i, t in enumerate(tiers):
        until = "دائمی" if not t.get("until") else (f"{_fmt_dur(t['until'] - now)} مانده" if t["until"] > now else "⚪ تمام شده")
        lines.append(f"{fa_digits(str(i + 1))}. خرید از <b>{_n(t['min'])}</b> شاهی به بالا → <b>{_n(t['pct'])}٪</b> تخفیف • {until}")
        kb.append([_ab(f"🗑 حذف تخفیف {fa_digits(str(i + 1))}", f"adm_p:x:disc_del:{i}", DANGER)])
    if not tiers:
        lines.append("هنوز تخفیفی تعریف نشده است.")
    lines += ["", "اگر چند تخفیف هم‌زمان شامل خریدی شود، بیشترین درصد اعمال می‌شود."]
    kb = [[_ab("💵 تعیین قیمت هر شاهی", "adm_p:x:up", PRIMARY), _ab("🧹 حذف قیمت (برگشت به قیمت بسته)", "adm_p:x:up_clear", DANGER)]] + kb
    kb.append([_ab("➕ افزودن تخفیف", "adm_p:x:disc_add", SUCCESS)])
    kb.append([_ab("🔙 تنظیمات خرید شاهی", "adm_p:j:home")])
    return "\n".join(lines), _kb(*kb)


def render_chan_bc():
    n = len(admin_channels(force=True))
    text = ("📡 <b>همگانی درخواست JFJ</b>\n" + LINE + "\n"
            "پیامی که بفرستید دقیقاً (با همه‌ی فرمت‌ها و ایموجی‌ها) داخل تمام کانال‌ها و گروه‌هایی که ربات در آن‌ها "
            "<b>ادمین</b> است ارسال می‌شود؛ مناسب تبلیغ و خبر.\n"
            f"⏱ فاصله‌ی ارسال بین هر دو کانال: <b>{_fmt_dur(cron_sec())}</b>\n\n👇 <i>گیرندگان را انتخاب کنید.</i>")
    kb = _kb([_ab(f"تمام کانال ها ({_n(n)})", "adm_p:x:bca:chan", SUCCESS)],
             [_ab("🔙 تنظیمات عمومی", "adm_p:g:home")])
    return text, kb


SECTIONS = [("rj", "درخواست JFJ", BTN_REQUEST_JFJ), ("sj", "شروع JFJ", BTN_START_JFJ),
            ("ac", "حساب من", BTN_MY_ACCOUNT), ("bk", "بانک انتقال", BTN_TRANSFER_BANK),
            ("bt", "خرید شاهی", BTN_BUY_JTOKEN), ("su", "پشتیبانی", BTN_SUPPORT),
            ("od", "سفارش من", BTN_MY_ORDERS), ("ru", "قوانین", BTN_RULES), ("hp", "راهنما", "/help"),
            ("sv", "خرید ممبر و سین", BTN_BUY_SERVICES), ("mi", "مینی‌اپ", BTN_MINIAPP),
            ("sp", "اسپانسری", "/sponser"), ("rf", "زیرمجموعه‌گیری", "__rf__")]
_SEC_BY_BTN = {b: (k, n) for k, n, b in SECTIONS}


def sections_off():
    return set(sjson("sec_off", []))


# دکمه‌های شیشه‌ای (callback) هر بخش؛ پیشوند → کلید بخش (پرداخت فاکتورهای موجود عمداً مسدود نمی‌شود)
_CB_SEC = (("sp_pick:", "sp"), ("sps:", "sp"), ("acc_ref", "rf"), ("jt_pick:", "bt"),
           ("svc_", "sv"), ("react_", "sv"), ("premium", "sv"), ("jfj_join", "sj"), ("jfj_next", "sj"))
_SEC_NAME = {k: n for k, n, _b in SECTIONS}


def callback_section_blocked(uid, data):
    if is_admin(uid):
        return None
    off = sections_off()
    if not off:
        return None
    for pre, k in _CB_SEC:
        if data.startswith(pre) and k in off:
            return _SEC_NAME.get(k)
    return None


def render_sections():
    off = sections_off()
    text = ("🛑 <b>فعال/غیرفعال کردن بخش‌های ربات</b>\n" + LINE + "\n"
            "بخش غیرفعال برای کاربران پیام «فعلاً غیرفعال است» می‌دهد (ادمین‌ها همیشه دسترسی دارند).\n"
            "محصولات از «🏬 تنظیمات محصولات» مدیریت می‌شوند.\n\n👇 <i>برای تغییر، روی هر بخش بزنید.</i>")
    rows, cur = [], []
    for k, n, _b in SECTIONS:
        cur.append(_ab(("🔴 " if k in off else "🟢 ") + n, f"adm_p:x:sect:{k}", DANGER if k in off else SUCCESS))
        if len(cur) == 2:
            rows.append(cur)
            cur = []
    if cur:
        rows.append(cur)
    rows.append([_ab("🔙 تنظیمات عمومی", "adm_p:g:home")])
    return text, _kb(*rows)


def section_blocked(uid, text):
    """اگر دکمه/دستور مربوط به یک بخش غیرفعال باشد پیام می‌دهد و True برمی‌گرداند"""
    hit = _SEC_BY_BTN.get(text)
    if not hit or is_admin(uid):
        return None
    return hit[1] if hit[0] in sections_off() else None



def render_mass_charge():
    total = _q1("SELECT COUNT(*) FROM users")
    s = _q1("SELECT COALESCE(SUM(tokens),0) FROM users")
    text = ("💸 <b>شارژ همگانی</b>\n" + LINE + "\n"
            f"👥 تعداد کاربران: <b>{_n(total)}</b>\n"
            f"🪙 مجموع موجودی همه: <b>{_t(s)}</b> شاهی\n\n"
            "با «شارژ» مقدار دلخواه به موجودی <b>همه‌ی کاربران</b> اضافه می‌شود و با «کسر» از همه کم می‌شود "
            "(موجودی می‌تواند منفی شود).\n"
            "🔕 به کاربران هیچ پیامی ارسال نمی‌شود.")
    kb = _kb([_ab("➕ شارژ همه", "adm_p:x:mc_in:add", SUCCESS), _ab("➖ کسر از همه", "adm_p:x:mc_in:sub", DANGER)],
             [_ab("🔙 مدیریت کاربر", "adm_p:u:home")])
    return text, kb


def _req_short(code, link):
    return f"{code} • {link}"[:40]


def render_req_manage(offset=0):
    PG = 8
    total = _q1("SELECT COUNT(*) FROM requests WHERE status NOT IN ('completed','cancelled','removed','deleted','relinked')")
    with get_db() as c:
        rows = c.execute(
            "SELECT tracking_code, link, member_count, (SELECT COUNT(*) FROM joins j WHERE j.tracking_code=r.tracking_code AND j.left_at IS NULL) "
            "FROM requests r WHERE status NOT IN ('completed','cancelled','removed','deleted','relinked') ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (PG, offset)).fetchall()
    text = ("🗑 <b>حذف درخواست JFJ</b>\n" + LINE + "\n"
            f"درخواست‌های در حال انجام: <b>{_n(total)}</b>\n\n"
            "روی هر درخواست بزنید تا گزینه‌های حذف (با یا بدون بازگرداندن شاهی) و مسدودسازی کانال را ببینید.")
    kb = [[_ab(f"🗑 {_req_short(code, link)} ({_n(done)}/{_n(cnt)})", f"adm_p:x:rmc:{code}", PRIMARY)] for code, link, cnt, done in rows]
    nav = []
    if offset > 0:
        nav.append(_ab("⬆️ قبلی", f"adm_p:x:rm:{max(offset - PG, 0)}", PRIMARY))
    if offset + PG < total:
        nav.append(_ab("⬇️ بعدی", f"adm_p:x:rm:{offset + PG}", PRIMARY))
    if nav:
        kb.append(nav)
    kb.append([_ab("🔙 تنظیمات درخواست JFJ", "adm_p:q:home")])
    return text, _kb(*kb)


def render_req_card(code):
    with get_db() as c:
        r = c.execute("SELECT user_id, member_count, token_cost, link, chat_id, status, created_at, "
                      "(SELECT COUNT(*) FROM joins j WHERE j.tracking_code=requests.tracking_code AND j.left_at IS NULL) "
                      "FROM requests WHERE tracking_code=?", (code,)).fetchone()
    if not r:
        return "❌ درخواست پیدا نشد.", _kb([_ab("🔙 لیست", "adm_p:x:rm:0")])
    uid, cnt, cost, link, cid, status, created, done = r
    blocked = is_chan_blocked(extract_chat_identifier(link or ""), cid)
    text = ("🗑 <b>درخواست JFJ</b>\n" + LINE + "\n"
            f"🔍 کد: <code>{code}</code>\n👤 {_label(uid)}\n🔗 {_h(link)}\n"
            f"👥 {_n(done)} از {_n(cnt)} ممبر\n💎 هزینه‌ی پرداختی: <b>{_t(cost)}</b> شاهی\n"
            f"📌 وضعیت: <b>{status}</b>\n⏰ {_fa_dt(created)}"
            + ("\n🚫 این کانال مسدود است." if blocked else ""))
    kb = []
    if status not in ("completed", "cancelled", "removed", "deleted", "relinked"):
        kb.append([_ab("🗑 حذف + بازگرداندن شاهی", f"adm_p:x:rmd:{code}:1", DANGER)])
        kb.append([_ab("🗑 حذف بدون بازگرداندن", f"adm_p:x:rmd:{code}:0", DANGER)])
        if not blocked:
            kb.append([_ab("🚫 حذف همه‌ی درخواست‌های این کانال + مسدود", f"adm_p:x:rmb:{code}", DANGER)])
    kb.append([_ab("🔙 لیست", "adm_p:x:rm:0")])
    return text, _kb(*kb)


def render_block_list():
    keys = sorted(_block_keys())
    text = ("🚫 <b>کانال‌های مسدود از درخواست JFJ</b>\n" + LINE + "\n"
            + (f"تعداد: <b>{_n(len(keys))}</b>\nبا زدن روی هر مورد، مسدودی آن برداشته می‌شود."
               if keys else "هنوز کانالی مسدود نشده است.")
            + "\n\nکاربر هنگام ثبت درخواست برای این کانال‌ها پیام «امکان درخواست وجود ندارد» می‌گیرد.")
    kb = [[_ab(f"♻️ {k}", f"adm_p:x:bku:{i}", PRIMARY)] for i, k in enumerate(keys[:30])]
    kb.append([_ab("➕ مسدود کردن کانال/گروه", "adm_p:x:bk_in", DANGER)])
    kb.append([_ab("🔙 تنظیمات درخواست JFJ", "adm_p:q:home")])
    return text, _kb(*kb)


def delete_request_admin(code, refund, admin_id=None):
    """True اگر حذف شد. refund=True: هزینه‌ی باقی‌مانده (به نسبت ممبرهای نیامده) به صاحب برمی‌گردد"""
    with get_db() as c:
        r = c.execute("SELECT user_id, member_count, token_cost, status FROM requests WHERE tracking_code=?", (code,)).fetchone()
        if not r or r[3] in ("completed", "cancelled", "removed", "deleted", "relinked"):
            return False
        c.execute("UPDATE requests SET status='deleted' WHERE tracking_code=?", (code,))
        if _table_exists(c, "mini_seen"):
            c.execute("DELETE FROM mini_seen WHERE code=?", (code,))
    rep_ev_request_state(code, "deleted", _admin_name(admin_id))
    if refund:
        uid, cnt, cost, _ = r
        done = get_join_count(code)
        rest = max(cnt - done, 0)
        amt = round(float(cost) * rest / max(cnt, 1), 2)
        if amt > 0:
            add_tokens(uid, amt)
            rep_ev_refund(admin_id, uid, code, amt)
    return True


GAME_KEYS = (("s", "🎰 گردونه شانس"), ("d", "🎲 تاس"), ("x", "❌⭕ دوز شاهی"))


def game_setting_on(key):
    return get_setting(f"g_{key}_on", "1") != "0"


def render_games():
    master = get_setting("casino_on", "1") != "0"
    text = ("🃏 <b>بازی‌های گروهی</b>\n" + LINE + "\n"
            f"🕹 همه‌ی بازی‌ها: {'🟢 روشن' if master else '🔴 خاموش'}\n"
            + "\n".join(f"{n}: {'🟢 روشن' if game_setting_on(k) else '🔴 خاموش'}" for k, n in GAME_KEYS) +
            f"\n💸 انتقال شاهی در گروه: {'🟢 روشن' if game_setting_on('t') else '🔴 خاموش'}"
            f"\n🏆 لیدربرد: {'🟢 روشن' if game_setting_on('l') else '🔴 خاموش'}"
            f"\n👑 پروفایل: {'🟢 روشن' if game_setting_on('p') else '🔴 خاموش'}"
            "\n\nℹ️ بازی خاموش اصلاً در گروه پاسخ نمی‌دهد و هیچ پیامی نمی‌فرستد "
            "(خاموش‌شدن تاس فقط دکمه‌اش را از منوی کازینو برمی‌دارد). "
            "میزهایی که هم‌اکنون در جریان‌اند تا پایان بازی می‌شوند تا شاهیِ کسی نسوزد."
            "\n\n👇 <i>برای تغییر، روی هر مورد بزنید.</i>")
    rows = [[_ab(("🔴 خاموش کردن همه‌ی بازی‌ها" if master else "🟢 روشن کردن همه‌ی بازی‌ها"), "adm_p:x:gmt:all",
                 DANGER if master else SUCCESS)]]
    for k, n in GAME_KEYS:
        on = game_setting_on(k)
        rows.append([_ab(("🟢 " if on else "🔴 ") + n, f"adm_p:x:gmt:{k}", SUCCESS if on else DANGER)])
    _t_on = game_setting_on("t")
    rows.append([_ab(("🟢 " if _t_on else "🔴 ") + "💸 انتقال شاهی در گروه", "adm_p:x:gmt:t", SUCCESS if _t_on else DANGER)])
    for k_, n_ in (("l", "🏆 لیدربرد"), ("p", "👑 پروفایل")):
        on_ = game_setting_on(k_)
        rows.append([_ab(("🟢 " if on_ else "🔴 ") + n_, f"adm_p:x:gmt:{k_}", SUCCESS if on_ else DANGER)])
    rows.append([_ab("⚙️ تنظیمات بازی‌ها", "adm_p:x:gx_cfg", SUCCESS), _ab("📊 گزارش بازی‌ها", "adm_p:x:gx_rep:1", PRIMARY)])
    rows.append([_ab("🎲 میزهای فعال", "adm_p:x:gx_act", PRIMARY), _ab("🔎 جستجوی بازیکن", "adm_p:x:gx_find", PRIMARY)])
    rows.append([_ab("🔙 تنظیمات عمومی", "adm_p:g:home", DANGER)])
    return text, _kb(*rows)


XPAGES = {"gm": render_games, "mc": render_mass_charge, "bk": render_block_list, "us": render_users, "cb": render_chan_bc, "sec": render_sections, "cron": render_cron, "fj": render_fj, "pay": render_pay, "bon": render_bonus, "disc": render_disc}


# =====================================================================
#  مسیریاب و ورودی‌های پنل ادمین (نسخه‌ی ۲)
# =====================================================================
def show_then(chat_id, then):
    then = then or ""
    try:
        if then.startswith("card:"):
            t, k = _user_card(int(then[5:]))
        elif then.startswith("sub:"):
            t, k = render_sub(int(then[4:]))
        elif then.startswith("spl:"):
            t, k = render_sub_list(int(then[4:]))
        elif then.startswith("prod:"):
            t, k = render_user_products(int(then[5:]))
        elif then in XPAGES:
            t, k = XPAGES[then]()
        else:
            t, k = SECTION_RENDER["g"]()
    except Exception:
        logging.exception("show_then")
        return
    _hsend(chat_id, t, k)


def _ask2(chat_id, admin_id, name, then, prompt, **extra):
    set_state(admin_id, "adm_in", dict(name=name, then=then, back="g", **extra))
    _hsend(chat_id, prompt + "\n\n<i>برای انصراف، دکمه‌ی زیر را بزنید.</i>",
           _kb([_ab("❌ انصراف", "adm_p:x:rt", DANGER)]))


def _fin(chat_id, admin_id, data, msg):
    set_state(admin_id, "admin_panel")
    _hsend(chat_id, "✅ " + msg)
    show_then(chat_id, data.get("then"))


def _num_ok(text, minv=0.0, integer=False, maxv=None):
    n = parse_number(text)
    if n is None or n < minv or (maxv is not None and n > maxv) or (integer and n != int(n)):
        return None
    return n


def render_user_products(uid):
    names = {k: PRODUCT_DEFS[k]["title"] for k in ("views", "reaction", "members", "premium")}
    lines = ["🎁 <b>محصول اختصاصی کاربر</b>", LINE, f"👤 {_label(uid)}", "",
             "اگر محصولی برای همه ناموجود باشد، با فعال کردنش اینجا فقط همین کاربر می‌تواند آن را بخرد.", ""]
    kb = []
    for k, title in names.items():
        glob = get_product(k)["enabled"]
        mine = user_has_product(uid, k)
        lines.append(f"{'✅' if mine else '⬜'} {title} — " + ("برای همه موجود است" if glob else "برای همه ناموجود"))
        kb.append([_ab(("✅ " if mine else "⬜ ") + title, f"adm_p:u:prodt:{uid}:{k}", SUCCESS if mine else PRIMARY)])
    kb.append([_ab("🔙 کارت کاربر", f"adm_p:u:card:{uid}")])
    return "\n".join(lines), _kb(*kb)


def v2_handle_input(chat_id, user, text, data):
    """True یعنی این ورودی متعلق به امکانات نسخه‌ی ۲ بود"""
    admin_id = user["id"]
    name = data.get("name")
    text = text.strip()
    t = text.translate(_ASCII_DIGITS)
    if name == "rep_chat":
        return rep_handle_chat_input(chat_id, admin_id, text, data)
    if name == "cron":
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(ثانیه|ث|s|sec|دقیقه|د|m|min)?", t, re.I)
        if not m:
            _err(chat_id, "مثل «۱۰» (ثانیه) یا «۲ دقیقه» بفرستید.")
            return True
        v = float(m.group(1)) * (60 if (m.group(2) or "").lower() in ("دقیقه", "د", "m", "min") else 1)
        if v < 0.05 or v > 86400:
            _err(chat_id, "مقدار باید بین ۰٫۰۵ ثانیه تا ۲۴ ساعت باشد.")
            return True
        set_setting("cron_sec", v)
        _fin(chat_id, admin_id, data, f"فاصله‌ی ارسال روی {_fmt_dur(v)} تنظیم شد.")
    elif name == "sdm_id":
        uid = _find_user(text)
        if not uid:
            _err(chat_id, "کاربری با این مشخصات پیدا نشد؛ دوباره بفرستید.")
            return True
        rich_start(chat_id, admin_id, "dm", "s", uid=uid, then=f"card:{uid}")
    elif name == "fj_add":
        ref = t if re.fullmatch(r"-?\d{6,}", t) else None
        if not ref:
            m = re.fullmatch(r"(?:https?://)?(?:t\.me/)?@?([A-Za-z][A-Za-z0-9_]{3,31})", t)
            ref = "@" + m.group(1) if m else None
        if not ref:
            _err(chat_id, "آیدی نامعتبر است؛ مثل @mychannel یا آیدی عددی (-100…) بفرستید.")
            return True
        if not ref.startswith("@") and not ref.startswith("-"):
            ref = "-100" + ref
        info = tg("getChat", chat_id=ref, _timeout=10)
        title = (info.get("result") or {}).get("title") or ref
        if not info.get("ok"):
            _err(chat_id, "ربات به این کانال/گروه دسترسی ندارد؛ ابتدا ربات را در آن ادمین کنید و دوباره بفرستید.")
            return True
        if ref.startswith("@"):
            lst = sjson("fj_list", [])
            lst.append({"ref": ref, "title": title, "link": f"https://t.me/{ref[1:]}"})
            set_setting("fj_list", json.dumps(lst, ensure_ascii=False))
            _fin(chat_id, admin_id, data, f"«{_h(title)}» به جوین اجباری اضافه شد.")
        else:
            _ask2(chat_id, admin_id, "fj_link", "fj", f"🔗 لینک دعوت «{_h(title)}» را بفرستید (برای دکمه‌ی عضویت کاربران):",
                  ref=ref, title=title)
    elif name == "fj_link":
        if not re.match(r"^https?://t\.me/\S+$", t):
            _err(chat_id, "لینک نامعتبر است؛ مثل https://t.me/+AbCdEf بفرستید.")
            return True
        lst = sjson("fj_list", [])
        lst.append({"ref": data["ref"], "title": data["title"], "link": t})
        set_setting("fj_list", json.dumps(lst, ensure_ascii=False))
        _fin(chat_id, admin_id, data, f"«{_h(data['title'])}» به جوین اجباری اضافه شد.")
    elif name == "zp_merchant":
        if not re.fullmatch(r"[0-9a-fA-F-]{30,40}", t):
            _err(chat_id, "مرچنت‌کد زرین‌پال ۳۶ نویسه (مثل xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx) است.")
            return True
        set_setting("zarin_merchant", t)
        _fin(chat_id, admin_id, data, "مرچنت‌کد ذخیره شد.")
    elif name == "site_url":
        if not re.match(r"^https://[^\s/]+\S*$", t):
            _err(chat_id, "آدرس باید با https:// شروع شود (مثل https://yourdomain.com).")
            return True
        set_setting("site_url", t.rstrip("/"))
        _fin(chat_id, admin_id, data, "آدرس سایت ذخیره شد.")
    elif name == "crypto_wallet":
        if not 10 <= len(t) <= 120 or " " in t:
            _err(chat_id, "آدرس کیف پول نامعتبر است.")
            return True
        set_setting("crypto_wallet", t)
        _fin(chat_id, admin_id, data, "آدرس کیف پول ذخیره شد.")
    elif name == "crypto_net":
        if not 2 <= len(text) <= 30:
            _err(chat_id, "نام ارز/شبکه باید بین ۲ تا ۳۰ نویسه باشد (مثل USDT TRC20).")
            return True
        set_setting("crypto_net", text)
        _fin(chat_id, admin_id, data, "نام ارز/شبکه ذخیره شد.")
    elif name == "crypto_rate":
        n = _num_ok(t, 1)
        if n is None:
            _err(chat_id, "یک عدد معتبر (تومان به ازای هر واحد ارز) بفرستید.")
            return True
        set_setting("crypto_rate", n)
        _fin(chat_id, admin_id, data, f"نرخ هر واحد ارز روی {_n(n)} تومان تنظیم شد.")
    elif name in ("bonus_per", "bonus_amount", "bonus_hours"):
        n = _num_ok(t, 0 if name == "bonus_hours" else 0.01)
        if n is None:
            _err(chat_id, "یک عدد معتبر بفرستید" + (" (۰ یعنی بدون محدودیت زمان)." if name == "bonus_hours" else "."))
            return True
        set_setting(name, n)
        if name == "bonus_hours" and sbool("bonus_on"):
            set_setting("bonus_start", time.time())
        _fin(chat_id, admin_id, data, "ذخیره شد.")
    elif name == "unit_price":
        n = _num_ok(t, 1)
        if n is None:
            _err(chat_id, "یک عدد معتبر (تومان) بفرستید.")
            return True
        set_setting("unit_price", n)
        _fin(chat_id, admin_id, data, f"قیمت هر ۱ شاهی روی {_n(n)} تومان تنظیم شد.")
    elif name == "disc_min":
        n = _num_ok(t, 1, integer=True)
        if n is None:
            _err(chat_id, "یک عدد صحیح بزرگ‌تر از صفر بفرستید.")
            return True
        _ask2(chat_id, admin_id, "disc_pct", "disc", "🏷 چند <b>درصد</b> تخفیف؟ (عدد ۱ تا ۹۹)", min=int(n))
    elif name == "disc_pct":
        n = _num_ok(t, 1, maxv=99)
        if n is None:
            _err(chat_id, "عددی بین ۱ تا ۹۹ بفرستید.")
            return True
        _ask2(chat_id, admin_id, "disc_hours", "disc", "⏳ این تخفیف چند <b>ساعت</b> فعال باشد؟\n(۰ یعنی دائمی)",
              min=data["min"], pct=n)
    elif name == "disc_hours":
        n = _num_ok(t, 0)
        if n is None:
            _err(chat_id, "یک عدد معتبر بفرستید (۰ = دائمی).")
            return True
        tiers = sjson("disc_tiers", [])
        tiers.append({"min": data["min"], "pct": data["pct"], "until": (time.time() + n * 3600) if n > 0 else 0})
        set_setting("disc_tiers", json.dumps(tiers))
        _fin(chat_id, admin_id, data, "تخفیف اضافه شد.")
    elif name == "dc_val":
        kind = data["kind"]
        n = _num_ok(t, 1, maxv=99 if kind == "pct" else None)
        if n is None:
            _err(chat_id, "عددی بین ۱ تا ۹۹ بفرستید." if kind == "pct" else "مبلغ را به تومان (عدد) بفرستید.")
            return True
        _ask2(chat_id, admin_id, "dc_exp", data["then"], "⏳ کد تا چند <b>ساعت</b> معتبر باشد؟\n(۰ یعنی بدون انقضا)",
              uid=data["uid"], kind=kind, value=n)
    elif name == "dc_exp":
        n = _num_ok(t, 0)
        if n is None:
            _err(chat_id, "یک عدد معتبر بفرستید (۰ = بدون انقضا).")
            return True
        code = dc_new_code()
        exp = _utcnow_str(datetime.now(timezone.utc) + timedelta(hours=n)) if n > 0 else None
        with get_db() as c:
            c.execute("INSERT INTO discount_codes (code, user_id, kind, value, expires_at) VALUES (?,?,?,?,?)",
                      (code, data["uid"], data["kind"], data["value"], exp))
        desc = f"{_n(data['value'])}٪" if data["kind"] == "pct" else f"{_n(data['value'])} تومان"
        send(data["uid"], f"🎁 *یک کد تخفیف اختصاصی برای شما ساخته شد!*\n\n🏷 *کد: `{code}`*\n💸 *مقدار: {fa_digits(desc.replace('٪', ' درصد'))}*\n"
                          "ℹ️ *هنگام خرید شاهی یا اسپانسری روی «دارم کد تخفیف» بزنید و این کد را بفرستید.*")
        _fin(chat_id, admin_id, data, f"کد تخفیف <code>{code}</code> ({desc}) ساخته و برای کاربر ارسال شد.")
    elif name in ("sp_ah", "sp_sh"):
        n = _num_ok(t, 0.01)
        if n is None:
            _err(chat_id, "ساعت را به صورت عدد بفرستید.")
            return True
        sponsor_shift(data["sid"], n if name == "sp_ah" else -n)
        _fin(chat_id, admin_id, data, "انجام شد.")
    elif name == "sp_new":
        n = _num_ok(t, 0.01)
        if n is None:
            _err(chat_id, "ساعت را به صورت عدد بفرستید.")
            return True
        _ask2(chat_id, admin_id, "sp_new_ref", data["then"],
              "🆔 آیدی کانال/گروه را بفرستید (@ یا عددی)؛ اگر نمی‌خواهید ثبت شود، <code>-</code> بفرستید:", uid=data["uid"], hours=n)
    elif name == "sp_new_ref":
        ref = None
        if t != "-":
            m = re.fullmatch(r"(?:https?://)?(?:t\.me/)?@?([A-Za-z][A-Za-z0-9_]{3,31})", t)
            ref = ("@" + m.group(1)) if m else (t if re.fullmatch(r"-\d{6,}", t) else None)
            if not ref:
                _err(chat_id, "آیدی نامعتبر است؛ @آیدی یا عدد منفی بفرستید یا - برای رد کردن.")
                return True
        with get_db() as c:
            cur = c.execute("INSERT INTO sponsor_subs (user_id, hours, status, chat_kind, chat_ref) VALUES (?,?,?,?,?)",
                            (data["uid"], data["hours"], "pending", "public" if (ref or "").startswith("@") else "private", ref))
            sid = cur.lastrowid
        sponsor_activate(sid)
        _fin(chat_id, admin_id, data, f"اشتراک #{sid} ساخته و فعال شد.")
    else:
        return False
    return True


def v2_admin_callback(cq):
    """True یعنی این دکمه‌ی شیشه‌ای توسط نسخه‌ی ۲ مدیریت شد"""
    parts = cq["data"].split(":")
    sec = parts[1] if len(parts) > 1 else ""
    act = parts[2] if len(parts) > 2 else ""
    args = parts[3:]
    admin_id = cq["from"]["id"]
    chat_id = cq["message"]["chat"]["id"]
    mid = cq["message"]["message_id"]
    mine = (sec in ("x", "sp")
            or (sec == "u" and act in ("zero", "zeroc", "prod", "prodt", "cbt", "phr", "dcn", "dck", "rrf", "rrc", "dm"))
            or (sec == "s" and act in ("bc", "dm"))
            or (sec == "f" and act == "pay"))
    if not mine:
        return False
    answered = [False]

    def ack(text=None, alert=False):
        if not answered[0]:
            answered[0] = True
            answer_callback(cq["id"], text, show_alert=alert)

    def show(text, kb):
        _hedit(chat_id, mid, text, kb)

    def page(key):
        t, k = XPAGES[key]()
        show(t, k)

    try:
        if sec == "x":
            if act in XPAGES:
                ack()
                set_state(admin_id, "admin_panel")
                return page(act) or True
            if act.startswith("rs_"):
                return rs_callback(act, args, admin_id, chat_id, mid, ack, show)
            if act.startswith("gx_") and GAMES:
                r = GAMES.admin_cb(act, args, admin_id, chat_id)
                if r is None:
                    ack()
                    return True
                t_, k_, toast = r
                ack(toast)
                show(t_, k_)
                return True
            if act == "gmt":
                key = "casino_on" if args[0] == "all" else f"g_{args[0]}_on"
                if args[0] == "all" or args[0] in ("s", "d", "x", "t", "l", "p"):
                    set_setting(key, "1" if get_setting(key, "1") == "0" else "0")
                ack("انجام شد.")
                return page("gm") or True
            if act == "sect":
                off = sections_off()
                off.symmetric_difference_update({args[0]})
                set_setting("sec_off", json.dumps(sorted(off)))
                ack("انجام شد.")
                return page("sec") or True
            if act == "rx":
                ack("لغو شد.")
                set_state(admin_id, "admin_panel")
                return show("❌ لغو شد.", None) or True
            if act == "rt":
                ack()
                _, d = get_state(admin_id)
                set_state(admin_id, "admin_panel")
                show_then(chat_id, (d or {}).get("then"))
                return True
            if act == "rch":
                ack()
                _, d = get_state(admin_id)
                d = d or {}
                rich_start(chat_id, admin_id, d.get("purpose", "dm"), d.get("back", "s"),
                           **{k: v for k, v in d.items() if k in ("uid", "aud", "then")})
                return True
            if act == "rk":
                _, d = get_state(admin_id)
                if not d or d.get("name") != "rich" or args[0] not in RICH_KINDS:
                    ack("این مرحله منقضی شده.", True)
                    return True
                d["kind"] = args[0]
                set_state(admin_id, "adm_in", d)
                ack()
                hint = {"photo": "🖼 عکس (با کپشن اگر می‌خواهید)", "voice": "🎙 ویس", "sticker": "🎭 استیکر",
                        "gif": "🎞 گیف", "text": "📝 متن", "forward": "↪️ فوروارد"}[args[0]]
                show(f"✉️ <b>{hint}</b>\n\n" + (
                     "هر پیامی (از هر نوعی) بفرستید یا از یک کانال/چت <b>فوروارد</b> کنید؛ ربات همان را به‌صورت "
                     "<b>فوروارد</b> (با نام مبدأ) برای گیرندگان می‌فرستد."
                     if args[0] == "forward" else
                     "حالا پیام را <b>همان‌طور که می‌خواهید کاربر ببیند</b> بفرستید. "
                     "فرمت‌ها (bold، کج، خط‌خورده، اسپویلر، لینک و…) دقیقاً حفظ می‌شود."),
                     _kb([_ab("🔁 تغییر نوع", "adm_p:x:rch", PRIMARY), _ab("❌ انصراف", "adm_p:x:rx", DANGER)]))
                return True
            if act in ("rgo", "rgop"):
                _, d = get_state(admin_id)
                if not d or d.get("name") != "rich" or not d.get("src_mid"):
                    ack("پیامی برای ارسال نیست.", True)
                    return True
                ack("در حال ارسال…")
                set_state(admin_id, "admin_panel")
                if d["purpose"] == "dm":
                    r = send_rich(d["uid"], d["src_chat"], d["src_mid"], d.get("kind") == "forward")
                    _hsend(chat_id, "✅ پیام ارسال شد." if r.get("ok") else "❗️ ارسال نشد؛ احتمالاً کاربر ربات را بلاک کرده است.")
                    show_then(chat_id, d.get("then"))
                else:
                    bc_create(admin_id, chat_id, d["src_chat"], d["src_mid"], d["aud"], pin=(act == "rgop"), fwd=(d.get("kind") == "forward"))
                return True
            if act == "bc":
                ack()
                rows = [[_ab(f"{AUD_LABELS[a]} ({_n(len(bc_targets(a)))})", f"adm_p:x:bca:{a}", PRIMARY)] for a in AUD_LABELS]
                rows.append([_ab("🔙 بازگشت", "adm_p:g:home")])
                show("📣 <b>ارسال اطلاعیه</b>\n" + LINE + "\nاطلاعیه برای چه کسانی ارسال شود؟\n\n"
                     f"⏱ فاصله‌ی ارسال بین هر دو نفر: <b>{_fmt_dur(cron_sec())}</b> (از «تنظیم کرون» قابل تغییر)", _kb(*rows))
                return True
            if act == "bca":
                ack()
                return rich_start(chat_id, admin_id, "bc", "g", aud=args[0], then="gen") or True
            if act == "bcc":
                with get_db() as c:
                    c.execute("UPDATE bc_jobs SET status='cancelled' WHERE id=? AND status='running'", (int(args[0]),))
                ack("ارسال متوقف شد.")
                show(_bc_progress_text(int(args[0])), None)
                return True
            if act == "cron_set":
                set_setting("cron_sec", float(args[0]))
                ack("ذخیره شد.")
                return page("cron") or True
            if act == "cron_in":
                ack()
                return _ask2(chat_id, admin_id, "cron", "cron",
                             "⏱ <b>فاصله‌ی ارسال</b>\n\nمقدار را بفرستید؛ مثل <code>10</code> (ثانیه) یا <code>2 دقیقه</code>.") or True
            if act == "fj_tg":
                set_setting("fj_enabled", "0" if sbool("fj_enabled") else "1")
                ack("تغییر کرد.")
                return page("fj") or True
            if act == "fj_add":
                ack()
                return _ask2(chat_id, admin_id, "fj_add", "fj",
                             "📢 <b>افزودن کانال/گروه</b>\n\nآیدی را بفرستید: <code>@mychannel</code> یا آیدی عددی (مثل -1001234567890).\n"
                             "ربات باید در آن ادمین باشد.") or True
            if act == "fj_del":
                lst = sjson("fj_list", [])
                i = int(args[0])
                if 0 <= i < len(lst):
                    lst.pop(i)
                    set_setting("fj_list", json.dumps(lst, ensure_ascii=False))
                ack("حذف شد.")
                return page("fj") or True
            if act == "ph":
                set_setting("phone_verify", "0" if sbool("phone_verify") else "1")
                ack("تغییر کرد.")
                t, k = SECTION_RENDER["g"]()
                return show(t, k) or True
            if act == "pay_tg":
                m = args[0]
                if m not in METHOD_LABELS:
                    return ack() or True
                k = "pay_" + m
                new = "0" if sbool(k, "1" if m == "card" else "0") else "1"
                if new == "1":
                    need = {"zarin": (not get_setting("zarin_merchant") or not site_url(), "ابتدا «مرچنت زرین‌پال» و «آدرس سایت» را وارد کنید."),
                            "crypto": (not get_setting("crypto_wallet") or crypto_rate() <= 0, "ابتدا «آدرس کیف پول» و «نرخ هر واحد» را وارد کنید.")}.get(m)
                    if need and need[0]:
                        return ack(need[1], True) or True
                set_setting(k, new)
                ack("تغییر کرد.")
                return page("pay") or True
            if act == "pay_sb":
                set_setting("zarin_sandbox", "0" if sbool("zarin_sandbox") else "1")
                ack("تغییر کرد.")
                return page("pay") or True
            if act == "pay_in":
                ack()
                f = args[0]
                prompt = {"zp_merchant": "🔑 <b>مرچنت‌کد زرین‌پال</b> را بفرستید:",
                          "site_url": "🌐 <b>آدرس سایت</b> را بفرستید (برای بازگشت کاربر از درگاه؛ مثل https://yourdomain.com):",
                          "crypto_wallet": "👛 <b>آدرس کیف پول</b> را بفرستید:",
                          "crypto_net": "🪙 <b>نام ارز/شبکه</b> را بفرستید (مثل USDT TRC20):",
                          "crypto_rate": "💵 <b>نرخ هر ۱ واحد ارز به تومان</b> را بفرستید:"}[f]
                return _ask2(chat_id, admin_id, f, "pay", prompt) or True
            if act == "bon_tg":
                new = "0" if sbool("bonus_on") else "1"
                set_setting("bonus_on", new)
                if new == "1":
                    set_setting("bonus_start", time.time())
                ack("تغییر کرد.")
                return page("bon") or True
            if act == "bon_in":
                ack()
                f = args[0]
                prompt = {"bonus_per": "📐 به ازای هر <b>چند شاهی خرید</b> بونوس بدهیم؟ (مثلاً ۵)",
                          "bonus_amount": "🎁 <b>چند شاهی</b> بونوس بدهیم؟",
                          "bonus_hours": "⏳ بونوس چند <b>ساعت</b> فعال باشد؟ (۰ = بدون محدودیت)"}[f]
                return _ask2(chat_id, admin_id, f, "bon", prompt) or True
            if act == "mc_in":
                ack()
                mode = args[0]
                return _ask2(chat_id, admin_id, "mc_" + mode, "mc",
                             ("➕ <b>شارژ همگانی</b>\n\nچند شاهی به <b>همه‌ی کاربران</b> اضافه شود؟" if mode == "add"
                              else "➖ <b>کسر همگانی</b>\n\nچند شاهی از <b>همه‌ی کاربران</b> کم شود؟")) or True
            if act == "mcg":
                mode, amt = args[0], float(args[1])
                if mode not in ("add", "sub") or amt <= 0:
                    return ack() or True
                with get_db() as c:
                    if mode == "add":
                        cur = c.execute("UPDATE users SET tokens = tokens + ?", (amt,))
                    else:
                        cur = c.execute("UPDATE users SET tokens = tokens - ?", (amt,))
                ack("انجام شد.")
                rep_ev_mass(admin_id, mode, amt, cur.rowcount)
                set_state(admin_id, "admin_panel")
                show(f"✅ <b>{'شارژ' if mode == 'add' else 'کسر'} همگانی انجام شد</b>\n{LINE}\n"
                     f"🪙 مقدار: <b>{_t(amt)}</b> شاهی\n👥 کاربران: <b>{_n(cur.rowcount)}</b>\n🔕 به کاربران خبری داده نشد.",
                     _kb([_ab("🔙 مدیریت کاربر", "adm_p:u:home")]))
                return True
            if act == "rm":
                ack()
                t, k = render_req_manage(int(args[0]) if args else 0)
                return show(t, k) or True
            if act == "rmc":
                ack()
                t, k = render_req_card(args[0])
                return show(t, k) or True
            if act == "rmd":
                ok = delete_request_admin(args[0], args[1] == "1", admin_id)
                ack("درخواست حذف شد." if ok else "این درخواست دیگر فعال نیست.", not ok)
                t, k = render_req_manage(0)
                return show(t, k) or True
            if act == "rmb":
                with get_db() as c:
                    r = c.execute("SELECT link, chat_id FROM requests WHERE tracking_code=?", (args[0],)).fetchone()
                if not r:
                    return ack("پیدا نشد.", True) or True
                link, cid = r
                keys = [extract_chat_identifier(link or ""), f"id:{cid}" if cid else None]
                block_chan(keys)
                n = 0
                with get_db() as c:
                    rows = c.execute("SELECT tracking_code, link, chat_id FROM requests WHERE status NOT IN ('completed','cancelled','removed','deleted','relinked')").fetchall()
                for code, l2, c2 in rows:
                    if is_chan_blocked(extract_chat_identifier(l2 or ""), c2):
                        n += 1 if delete_request_admin(code, False, admin_id) else 0
                ack(f"کانال مسدود شد؛ {n} درخواست حذف شد.", True)
                t, k = render_req_manage(0)
                return show(t, k) or True
            if act == "bku":
                keys = sorted(_block_keys())
                i = int(args[0])
                if 0 <= i < len(keys):
                    unblock_chan(keys[i])
                ack("مسدودی برداشته شد.")
                return page("bk") or True
            if act == "rep_in":
                ack()
                return _ask2(chat_id, admin_id, "rep_chat", "rep", rep_ask_text()) or True
            if act == "rep_ic":
                cid, _tp = rep_conf()
                if not cid:
                    return ack("ابتدا گروه را ثبت کنید.", True) or True
                ack("در حال تنظیم آیکن‌ها…")
                n_ic = rep_apply_icons(cid)
                _hsend(chat_id, f"🎨 آیکن <b>{_rp_n(n_ic)}</b> تاپیک از {_rp_n(len(REPORT_TOPICS))} تنظیم شد.\n"
                                "ℹ️ تلگرام فقط تعداد محدودی ایموجی را برای آیکن تاپیک مجاز می‌داند؛ تاپیکی که ایموجی نامش در آن لیست نباشد بدون آیکن می‌ماند.")
                return True
            if act == "rep_dl":
                ack()
                t, k = render_report_delete_list()
                return show(t, k) or True
            if act == "rep_dc":
                key = args[0] if args else ""
                if key not in _REP_ICON:
                    return ack("پیدا نشد.", True) or True
                ack()
                return show(f"🗑 <b>حذف {_REP_ICON[key]}</b>\n\nمطمئنید؟ این تاپیک با همه‌ی پیام‌هایش از گروه پاک می‌شود و تا وقتی دوباره نسازید، گزارش آن ارسال نمی‌شود.",
                            _kb([_ab("✅ بله، حذف شود", f"adm_p:x:rep_dd:{key}", DANGER), _ab("❌ انصراف", "adm_p:x:rep_dl", SUCCESS)])) or True
            if act == "rep_dd":
                key = args[0] if args else ""
                cid, _tp = rep_conf()
                if key not in _REP_ICON or not cid:
                    return ack("پیدا نشد.", True) or True
                ok_d = rep_delete_topic(cid, key)
                ack("تاپیک حذف شد." if ok_d else "حذف انجام نشد؛ دسترسی ربات را بررسی کنید.", not ok_d)
                return page("rep") or True
            if act == "rep_mk1":
                key = args[0] if args else ""
                cid, _tp = rep_conf()
                if key not in _REP_ICON or not cid:
                    return ack("پیدا نشد.", True) or True
                rep_set_off(key, False)
                ack("در حال ساخت…")
                tid_new = rep_make_topic(cid, key)
                if not tid_new:
                    _hsend(chat_id, f"❌ ساخت تاپیک نشد: {_h(_rep_err.get(key, 'نامشخص'))}")
                return page("rep") or True
            if act == "rep_test":
                cid, _tp = rep_conf()
                if not cid:
                    return ack("ابتدا گروه را ثبت کنید.", True) or True
                ack("در حال تست…")
                ok_n = rep_connection_test(cid)
                _hsend(chat_id, f"📡 تست اتصال: <b>{_rp_n(ok_n)} از ۳</b> پیام ارسال شد " + ("✅ اتصال برقرار است." if ok_n == 3 else "⚠️ اتصال کامل نیست."))
                return True
            if act == "rep_mk":
                cid, _tp = rep_conf()
                if not cid:
                    return ack("ابتدا گروه را ثبت کنید.", True) or True
                ack("در حال بررسی…")
                made, failed = rep_ensure_topics(cid)
                _hsend(chat_id, f"♻️ تاپیک‌های تازه ساخته‌شده: <b>{_rp_n(made)}</b>" + (f" • ❌ ناموفق: {_rp_n(failed)}" if failed else " • همه‌ی تاپیک‌ها سالم‌اند ✅"))
                return page("rep") or True
            if act == "rep_bk":
                if not rep_ready():
                    return ack("ابتدا گروه را ثبت کنید.", True) or True
                ack("بکاپ در حال ارسال…")
                threading.Thread(target=rep_send_backup, args=(chat_id,), daemon=True).start()
                return True
            if act == "rep_day":
                if not rep_ready():
                    return ack("ابتدا گروه را ثبت کنید.", True) or True
                ack("گزارش در حال ارسال…")
                rep_send_day(now_local().date().isoformat(), partial=True)
                return True
            if act == "bk_in":
                ack()
                return _ask2(chat_id, admin_id, "bk_add", "bk",
                             "🚫 <b>مسدود کردن کانال/گروه</b>\n\nآیدی را بفرستید: <code>@mychannel</code> یا آیدی عددی (مثل -1001234567890).") or True
            if act == "up":
                ack()
                return _ask2(chat_id, admin_id, "unit_price", "disc", "💵 قیمت هر <b>۱ شاهی</b> را به تومان بفرستید:") or True
            if act == "up_clear":
                set_setting("unit_price", "0")
                ack("حذف شد.")
                return page("disc") or True
            if act == "disc_add":
                ack()
                return _ask2(chat_id, admin_id, "disc_min", "disc",
                             "🏷 <b>تخفیف جدید</b>\n\nاز چند شاهی خرید به بالا؟ (حداقل تعداد خرید)") or True
            if act == "disc_del":
                tiers = sjson("disc_tiers", [])
                i = int(args[0])
                if 0 <= i < len(tiers):
                    tiers.pop(i)
                    set_setting("disc_tiers", json.dumps(tiers))
                ack("حذف شد.")
                return page("disc") or True
            return ack() or True

        if sec == "f" and act == "pay":
            ack()
            return page("pay") or True

        if sec == "s":
            if act == "bc":
                ack()
                return admin_panel_callback_fake(cq, "x", "bc")
            if act == "dm":
                ack()
                return _ask2(chat_id, admin_id, "sdm_id", "gen",
                             "✉️ <b>پیام به کاربر</b>\n\nآیدی عددی یا @یوزرنیم کاربر را بفرستید:") or True

        if sec == "u":
            uid = int(args[0]) if args else 0
            if act == "dm":
                ack()
                return rich_start(chat_id, admin_id, "dm", "u", uid=uid, then=f"card:{uid}") or True
            if act == "zero":
                ack()
                return show(f"0️⃣ <b>صفر کردن موجودی</b>\n\n{_label(uid)}\n🪙 دارایی فعلی: <b>{_t(get_balance(uid))}</b> شاهی\n\n"
                            "موجودی صفر شود؟ (به کاربر خبر داده نمی‌شود)",
                            _kb([_ab("✅ بله، صفر شود", f"adm_p:u:zeroc:{uid}", DANGER), _ab("❌ انصراف", f"adm_p:u:card:{uid}", SUCCESS)])) or True
            if act == "zeroc":
                with get_db() as c:
                    c.execute("UPDATE users SET tokens=0 WHERE id=?", (uid,))
                ack("موجودی صفر شد.")
                t, k = _user_card(uid)
                return show(t, k) or True
            if act == "prod":
                ack()
                t, k = render_user_products(uid)
                return show(t, k) or True
            if act == "prodt":
                key = args[1]
                if key not in PRODUCT_DEFS:
                    return ack() or True
                with get_db() as c:
                    if user_has_product(uid, key):
                        c.execute("DELETE FROM user_products WHERE user_id=? AND key=?", (uid, key))
                        added = False
                    else:
                        c.execute("INSERT OR IGNORE INTO user_products (user_id, key) VALUES (?,?)", (uid, key))
                        added = True
                if added:
                    send(uid, f"🎁 *محصول «{PRODUCT_DEFS[key]['title']}» برای شما فعال شد.*\n\n🛍 *از بخش «خرید محصولات» می‌توانید آن را سفارش دهید.*")
                ack("فعال شد." if added else "برداشته شد.")
                t, k = render_user_products(uid)
                return show(t, k) or True
            if act == "cbt":
                with get_db() as c:
                    c.execute("UPDATE users SET card_blocked = 1 - card_blocked WHERE id=?", (uid,))
                if not card_blocked(uid):
                    send(uid, "✅ *پرداخت کارت به کارت برای شما فعال شد.*")
                ack("وضعیت کارت تغییر کرد.")
                t, k = _user_card(uid)
                return show(t, k) or True
            if act == "phr":
                phone, req = user_phone(uid)
                with get_db() as c:
                    if req:
                        c.execute("UPDATE users SET phone_req=0 WHERE id=?", (uid,))
                    else:
                        c.execute("UPDATE users SET phone_req=1, phone=NULL WHERE id=?", (uid,))
                ack("تغییر کرد؛ دفعه‌ی بعد که کاربر از ربات استفاده کند شماره‌اش را می‌خواهد." if not req else "الزام شماره برداشته شد.", True)
                t, k = _user_card(uid)
                return show(t, k) or True
            if act == "dcn":
                ack()
                return show(f"🏷 <b>کد تخفیف اختصاصی</b>\n\n{_label(uid)}\n\nنوع تخفیف را انتخاب کنید:",
                            _kb([_ab("٪ درصدی", f"adm_p:u:dck:{uid}:pct", PRIMARY), _ab("💰 مبلغ ثابت (تومان)", f"adm_p:u:dck:{uid}:amt", PRIMARY)],
                                [_ab("🔙 کارت کاربر", f"adm_p:u:card:{uid}")])) or True
            if act == "dck":
                ack()
                kind = args[1]
                return _ask2(chat_id, admin_id, "dc_val", f"card:{uid}",
                             "🏷 <b>مقدار تخفیف</b>\n\n" + ("چند درصد؟ (۱ تا ۹۹)" if kind == "pct" else "چند تومان؟"),
                             uid=uid, kind=kind) or True
            if act == "rrf":
                ack()
                n = _q1("SELECT COUNT(*) FROM users WHERE referred_by=?", (uid,))
                return show(f"♻️ <b>ریست زیرمجموعه‌ها</b>\n\n{_label(uid)}\n👥 زیرمجموعه‌ی فعلی: <b>{_n(n)}</b> نفر\n\n"
                            "همه‌ی زیرمجموعه‌های این کاربر از او جدا می‌شوند (به کاربر خبر داده نمی‌شود). مطمئنید؟",
                            _kb([_ab("✅ بله، ریست شود", f"adm_p:u:rrc:{uid}", DANGER), _ab("❌ انصراف", f"adm_p:u:card:{uid}", SUCCESS)])) or True
            if act == "rrc":
                with get_db() as c:
                    c.execute("UPDATE users SET referred_by=NULL WHERE referred_by=?", (uid,))
                ack("زیرمجموعه‌ها ریست شدند.")
                t, k = _user_card(uid)
                return show(t, k) or True

        if sec == "sp":
            key = int(args[0]) if args else 0
            if act == "ls":
                ack()
                t, k = render_sub_list(key)
                return show(t, k) or True
            if act == "sub":
                ack()
                t, k = render_sub(key)
                return show(t, k) or True
            r = sub_row(key) if act != "new" else None
            if act != "new" and not r:
                return ack("این اشتراک پیدا نشد.", True) or True
            if act == "act":
                sponsor_activate(key)
                ack("فعال شد.")
                t, k = render_sub(key)
                return show(t, k) or True
            if act == "can":
                with get_db() as c:
                    c.execute("UPDATE sponsor_subs SET status='cancelled' WHERE id=?", (key,))
                rep_ev_sponsor("can", key, admin_id=admin_id)
                ack("لغو شد (به کاربر خبر داده نشد).")
                t, k = render_sub(key)
                return show(t, k) or True
            if act == "del":
                ack()
                return show(f"🗑 <b>حذف اشتراک #{key}</b>\n\nمطمئنید؟ (به کاربر خبر داده نمی‌شود)",
                            _kb([_ab("✅ بله، حذف شود", f"adm_p:sp:delc:{key}", DANGER), _ab("❌ انصراف", f"adm_p:sp:sub:{key}", SUCCESS)])) or True
            if act == "delc":
                rep_ev_sponsor("del", key, admin_id=admin_id)
                with get_db() as c:
                    c.execute("DELETE FROM sponsor_subs WHERE id=?", (key,))
                ack("حذف شد.")
                t, k = render_sub_list(r[1])
                return show(t, k) or True
            if act in ("ah", "sh"):
                ack()
                return _ask2(chat_id, admin_id, "sp_" + act, f"sub:{key}",
                             ("➕ <b>افزودن ساعت</b>" if act == "ah" else "➖ <b>کسر ساعت</b>") + "\n\nتعداد ساعت را بفرستید:", sid=key) or True
            if act == "doc":
                ack()
                return sponsor_docs(chat_id, key) or True
            if act == "new":
                ack()
                return _ask2(chat_id, admin_id, "sp_new", f"spl:{key}",
                             "➕ <b>ساخت اشتراک دستی</b>\n\nمدت اشتراک را به <b>ساعت</b> بفرستید:", uid=key) or True
    except Exception:
        logging.exception("v2_admin_callback failed: %s", cq.get("data"))
    ack()
    return True


def admin_panel_callback_fake(cq, sec, act, *args):
    c2 = dict(cq, data=":".join(["adm_p", sec, act, *args]))
    return v2_admin_callback(c2)


# ===================== دیسپچ آپدیت =====================
def claim_update(update_id):
    with get_db() as c:
        cur = c.execute("INSERT OR IGNORE INTO processed_updates (update_id) VALUES (?)", (update_id,))
        return cur.rowcount == 1


def release_update(update_id):
    with get_db() as c:
        c.execute("DELETE FROM processed_updates WHERE update_id = ?", (update_id,))


class _GlobalsProxy:
    """دسترسی games.py به توابع/متغیرهای همین فایل؛ مستقل از اینکه فایل چطور اجرا شده باشد
    (python bot_test.py، import، یا اجرا از طریق runpy/لانچر) و همیشه آخرین مقدار را می‌خواند"""

    def __getattr__(self, name):
        try:
            return globals()[name]
        except KeyError:
            raise AttributeError(name)


GAMES = None  # ماژول games (اگر لود شود)


def _games_dispatch(update_id, message=None, callback=None):
    """پیام/کال‌بک گروه را به games.py می‌دهد؛ هر خطایی اینجا مهار می‌شود تا بقیه‌ی ربات سالم بماند"""
    if GAMES is None:
        return
    try:
        if callback is not None:
            if not str(callback.get("data", "")).startswith("g:"):
                return
            uid = callback["from"]["id"]
        else:
            uid = message["from"]["id"]
            if not GAMES.relevant(message):
                return      # پیام عادی گروه: بدون قفل و بدون دیتابیس رد می‌شود
        lock = user_lock(uid)
        if not lock.acquire(timeout=10):
            return
        try:
            if not claim_update(update_id):
                return
            if callback is not None:
                GAMES.on_callback(callback)
            else:
                GAMES.on_group_message(message)
        finally:
            lock.release()
    except Exception:
        logging.exception("games dispatch")


def handle_update(update):
    update_id = update["update_id"]
    message = update.get("message")
    callback = update.get("callback_query")
    chat_member = update.get("chat_member")

    if message and "from" in message:
        user_id = message["from"]["id"]
    elif callback and "from" in callback:
        user_id = callback["from"]["id"]
    elif chat_member:
        user_id = chat_member["new_chat_member"]["user"]["id"]
    else:
        return

    # گروه/سوپرگروه/کانال: فقط بخش بازی‌ها (کازینو شاهنشاهی)؛ بقیه‌ی پیام‌های گروه نادیده گرفته می‌شود
    if message and message["chat"].get("type") != "private":
        _games_dispatch(update_id, message=message)
        return
    if callback and (callback.get("message") or {}).get("chat", {}).get("type", "private") != "private":
        _games_dispatch(update_id, callback=callback)
        return

    lock = user_lock(user_id)
    if not lock.acquire(timeout=10):
        return
    try:
        if not claim_update(update_id):
            return  # قبلاً پردازش شده
        try:
            if message and message["chat"].get("type") == "private":
                try:
                    register_start_referral(message)
                except Exception:
                    logging.exception("register_start_referral")
            if message and gate_blocked(user_id, message["chat"]["id"]):
                return
            if callback and gate_blocked(user_id, (callback.get("message") or {}).get("chat", {}).get("id"), callback["id"]):
                return
            if message and message["chat"].get("type") == "private" and fj_gate(user_id, message["chat"]["id"]):
                return
            if callback and fj_gate(user_id, (callback.get("message") or {}).get("chat", {}).get("id"), callback["id"],
                                    callback.get("data", "")):
                return
            if message:
                handle_message(message)
            elif callback:
                upsert_user(callback["from"])
                handle_callback(callback)
            elif chat_member:
                handle_chat_member_update(chat_member)
        except Exception:
            release_update(update_id)  # اجازه‌ی ریتری
            raise
    except Exception:
        logging.exception("update %s failed", update_id)
    finally:
        lock.release()


def handle_chat_member_update(cm):
    """وقتی وضعیت عضویت کسی در کانال/گروهی که ربات ادمینشه تغییر کند (join/leave/kick)"""
    new_status = cm["new_chat_member"]["status"]
    old_status = cm["old_chat_member"]["status"]
    if new_status in ("left", "kicked") and old_status not in ("left", "kicked"):
        chat_numeric_id = cm["chat"]["id"]
        user_id = cm["new_chat_member"]["user"]["id"]
        handle_member_left(chat_numeric_id, user_id)


# ===================== 📣 گزارشات ربات (گروه تاپیک‌دار مدیریت) =====================
import queue as _queue
import gzip as _gzip

REPORT_NAG_SEC = 600  # حداقل فاصله‌ی یادآوری برای هر ادمین تا زمانی که گزارشات تنظیم نشده
REPORT_BACKUP_SEC = 6 * 3600
REPORT_SEND_GAP = 3.2  # تلگرام: حداکثر ۲۰ پیام در دقیقه برای هر گروه
REPORT_TOPICS = [
    ("buy", "🛍 گزارش خرید", "گزارش خرید خدمات، خرید شاهی، اسپانسری و نتیجه‌ی سفارش‌ها."),
    ("fin", "💰 گزارش مالی", "گزارش افزایش/کاهش موجودی کاربران (خرید شاهی، شارژ و کسر مدیر، شارژ همگانی، بازگشت هزینه)."),
    ("bak", "🗃 بکاپ ربات", "هر ۶ ساعت یک‌بار فایل بکاپ دیتابیس (با فرمت .sql) اینجا ارسال می‌شود."),
    ("ref", "👥️ گزارش زیرمجموعه", "گزارش زیرمجموعه‌گیری کاربران و قبولی‌ها (پاداش معرف)."),
    ("rcp", "🧾 گزارش رسید", "گزارش رسیدهای واریزی، تأیید/رد رسید و پرداخت‌های آنلاین کاربران."),
    ("jfj", "🎗 گزارش درخواست JFJ", "گزارش ثبت، تکمیل، عزل ربات و حذف درخواست‌های JFJ کاربران."),
    ("spn", "🌟 گزارش اسپانسری", "گزارش خرید، ثبت مشخصات کانال، فعال‌سازی، افزودن/کسر ساعت و لغو اشتراک‌های اسپانسری."),
    ("lft", "📖 گزارش لفت", "گزارش لفت دادن کاربران با اطلاعات دقیق (کانال، جریمه، بازگشت به صاحب سفارش)."),
    ("xfr", "💸 گزارش بانک انتقال", "گزارش انتقال شاهی از کاربری به کاربر دیگر با اطلاعات دقیق."),
    ("day", "📊 گزارش شبانه", "گزارش آمار روزانه‌ی ربات (فقط همان روز، نه آمار کل). هر شب بعد از نیمه‌شب ارسال می‌شود."),
]
_REP_ICON = {k: n for k, n, _ in REPORT_TOPICS}
_rep_q = _queue.Queue(maxsize=5000)
_rep_nag = {}
_rep_db_ready = [False]
_rep_lock = threading.Lock()
_rep_err = {}          # آخرین خطای ساخت هر تاپیک (برای نمایش به ادمین)
_rep_icons = {}        # کش ایموجی -> custom_emoji_id
_rep_lock_topic = threading.RLock()
_rep_recreate = set()


def rep_conf():
    """(chat_id یا None، دیکشنری تاپیک‌ها)"""
    cid = get_setting("rep_chat")
    try:
        cid = int(cid) if cid else None
    except Exception:
        cid = None
    try:
        topics = json.loads(get_setting("rep_topics", "{}") or "{}")
    except Exception:
        topics = {}
    return cid, topics


def rep_off():
    try:
        return set(json.loads(get_setting("rep_off", "[]") or "[]"))
    except Exception:
        return set()


def rep_set_off(key, off=True):
    cur = rep_off()
    (cur.add if off else cur.discard)(key)
    set_setting("rep_off", json.dumps(sorted(cur)))


def rep_msg_set(key, mid):
    if not key or not mid:
        return
    with _rep_lock:
        with get_db() as c:
            c.execute("CREATE TABLE IF NOT EXISTS rep_msgs (k TEXT PRIMARY KEY, mid INTEGER NOT NULL)")
            c.execute("INSERT INTO rep_msgs (k, mid) VALUES (?,?) ON CONFLICT(k) DO UPDATE SET mid=excluded.mid", (key, int(mid)))


def rep_msg_get(key):
    if not key:
        return None
    try:
        with get_db() as c:
            if not _table_exists(c, "rep_msgs"):
                return None
            r = c.execute("SELECT mid FROM rep_msgs WHERE k=?", (key,)).fetchone()
        return r[0] if r else None
    except Exception:
        return None


def rep_ready():
    cid, _ = rep_conf()
    return bool(cid) and get_setting("rep_enabled", "0") == "1"


def rep_count(key, n=1):
    """شمارنده‌ی روزانه برای گزارش شبانه (حتی وقتی گزارشات خاموش است ثبت می‌شود)"""
    try:
        day = now_local().date().isoformat()
        with _rep_lock:
            with get_db() as c:
                if not _rep_db_ready[0]:
                    c.execute("CREATE TABLE IF NOT EXISTS rep_daily (day TEXT NOT NULL, k TEXT NOT NULL, n REAL NOT NULL DEFAULT 0, PRIMARY KEY (day, k))")
                    _rep_db_ready[0] = True
                c.execute("INSERT INTO rep_daily (day, k, n) VALUES (?,?,?) ON CONFLICT(day,k) DO UPDATE SET n = n + excluded.n",
                          (day, key, float(n)))
    except Exception:
        logging.exception("rep_count")


def report(topic, builder, key=None, reply=None):
    """builder: متن یا تابعی که متن را می‌سازد (کمی بعد اجرا می‌شود تا موجودی‌ها به‌روز باشند).
    key: شناسه‌ی این پیام (برای ریپلای‌های بعدی)؛ reply: شناسه‌ی پیام ثبتی که این پیام باید روی آن ریپلای شود.
    هیچ‌وقت exception پرتاب نمی‌کند و جریان اصلی را کند نمی‌کند."""
    try:
        if not rep_ready() or topic in rep_off():
            return

        def _go():
            try:
                txt = builder() if callable(builder) else builder
                if txt:
                    _rep_q.put_nowait({"kind": "text", "topic": topic, "b": txt, "key": key, "reply": reply, "n": 0})
            except Exception:
                logging.exception("report build failed")
        tm = threading.Timer(1.0, _go)
        tm.daemon = True
        tm.start()
    except Exception:
        logging.warning("report failed")


def report_copy(topic, from_chat, message_id, caption=None, key=None):
    """رسید (عکس/فایل) همراه با متن در یک پیام"""
    try:
        if not rep_ready() or topic in rep_off():
            return

        def _go():
            try:
                cap = caption() if callable(caption) else caption
                _rep_q.put_nowait({"kind": "copy", "topic": topic, "from": from_chat, "mid": message_id,
                                   "cap": (cap or "")[:1024], "key": key, "n": 0})
            except Exception:
                logging.exception("report_copy build failed")
        tm = threading.Timer(1.0, _go)
        tm.daemon = True
        tm.start()
    except Exception:
        pass


def _admin_name(admin_id):
    if not admin_id:
        return "مدیر"
    try:
        with get_db() as c:
            r = c.execute("SELECT first_name FROM users WHERE id=?", (admin_id,)).fetchone()
        return (r[0] if r and r[0] else "مدیر")
    except Exception:
        return "مدیر"


def _rp_user(uid, label="👤 کاربر"):
    with get_db() as c:
        r = c.execute("SELECT first_name, username FROM users WHERE id=?", (uid,)).fetchone()
    name = ((r[0] if r else "") or "کاربر").strip()
    un = ("@" + r[1]) if r and r[1] else "بدون یوزرنیم"
    return f'{label}: <a href="tg://user?id={uid}">{_h(name)}</a> • {_h(un)} • <code>{uid}</code>'


def _rp_bal(uid):
    try:
        return fa_digits(fmt_tokens(get_balance(uid)))
    except Exception:
        return "؟"


def _rp_t(v):
    return fa_digits(fmt_tokens(v))


def _rp_n(v):
    return fa_digits(fmt_num(v))


def _rp_head(topic, title):
    n = _REP_ICON.get(topic, "").split(" ", 1)[0]
    return f"{n} <b>{title}</b>\n━━━━━━━━━━━━━━\n"


def _rp_time(label="زمان"):
    return "\n" + stamp(label, md=False)


# ---------- ارسال به تاپیک‌ها ----------
def _rep_post(method, topic, **params):
    """هیچ‌وقت در تاپیک General ارسال نمی‌کند؛ اگر تاپیک نبود می‌سازد و اگر نشد، خطای no_topic می‌دهد"""
    cid, topics = rep_conf()
    if not cid:
        return {"ok": False, "description": "no chat"}
    if topic in rep_off():
        return {"ok": False, "description": "off", "off": True}
    tid = topics.get(topic) or rep_make_topic(cid, topic)
    if not tid:
        return {"ok": False, "description": "no_topic"}
    p = dict(params)
    p["chat_id"] = cid
    p["message_thread_id"] = tid
    r = tg(method, **p)
    desc = str(r.get("description", r.get("error_description", ""))).lower()
    if not r.get("ok") and ("thread not found" in desc or "topic_deleted" in desc or "topic_id_invalid" in desc
                            or ("topic" in desc and "not" in desc)):
        new_tid = rep_make_topic(cid, topic)
        if not new_tid:
            return {"ok": False, "description": "no_topic"}
        p["message_thread_id"] = new_tid
        p.pop("reply_to_message_id", None)
        r = tg(method, **p)
    return r


def _send_doc(chat_id, thread_id, filename, data, caption, timeout=180):
    """ارسال فایل با multipart (بدون وابستگی). همیشه dict برمی‌گرداند و exception پرتاب نمی‌کند."""
    boundary = "----jfjrep" + hashlib.md5(os.urandom(8)).hexdigest()
    fields = {"chat_id": str(chat_id), "caption": caption[:1000], "parse_mode": "HTML"}
    if thread_id:
        fields["message_thread_id"] = str(thread_id)
    body = b""
    for k, v in fields.items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode("utf-8")
    body += (f'--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="{filename}"\r\n'
             f'Content-Type: application/octet-stream\r\n\r\n').encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument", data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read() or b"{}")
        except Exception:
            return {"ok": False, "description": str(e)}
    except Exception as e:
        return {"ok": False, "description": str(e)}


def _rep_upload_doc(topic, filename, data, caption):
    cid, topics = rep_conf()
    if not cid or topic in rep_off():
        return {"ok": False, "description": "off"}
    tid = topics.get(topic) or rep_make_topic(cid, topic)
    if not tid:
        return {"ok": False, "description": "no_topic"}
    return _send_doc(cid, tid, filename, data, caption)


def _plain_emoji(s):
    return (s or "").replace("\ufe0f", "").replace("\ufe0e", "").strip()


def rep_icon_for(key):
    """custom_emoji_id ایموجی داخل نام تاپیک (اگر در لیست مجاز تلگرام باشد)"""
    if not _rep_icons:
        r = tg("getForumTopicIconStickers", _timeout=20)
        for st in (r.get("result") or []):
            if st.get("emoji") and st.get("custom_emoji_id"):
                _rep_icons.setdefault(_plain_emoji(st["emoji"]), st["custom_emoji_id"])
        if not _rep_icons:
            _rep_icons["_"] = ""
    name = _REP_ICON.get(key, "")
    return _rep_icons.get(_plain_emoji(name.split(" ", 1)[0]))


def rep_make_topic(cid, key):
    """ساخت تاپیک با ایموجی پروفایل؛ در صورت محدودیت تلگرام (429) صبر و تکرار می‌کند. None = ناموفق (خطا در _rep_err)"""
    with _rep_lock_topic:
        _, topics = rep_conf()
        if topics.get(key) and key not in _rep_recreate:
            return topics[key]
        name = _REP_ICON[key]
        icon = None
        try:
            icon = rep_icon_for(key)
        except Exception:
            icon = None
        r = None
        for attempt in range(4):
            params = {"chat_id": cid, "name": name}
            if icon:
                params["icon_custom_emoji_id"] = icon
            r = tg("createForumTopic", **params)
            if r.get("ok"):
                break
            desc = str(r.get("description", r.get("error_description", "")))
            ra = (r.get("parameters") or {}).get("retry_after")
            if ra:
                time.sleep(min(int(ra) + 1, 90))
                continue
            if icon and ("icon" in desc.lower() or "emoji" in desc.lower()):
                icon = None  # ایموجی مجاز نبود؛ بدون آیکن
                continue
            break
        if not r or not r.get("ok"):
            _rep_err[key] = str((r or {}).get("description", (r or {}).get("error_description", "نامشخص")))
            logging.warning("createForumTopic %s failed: %s", key, r)
            return None
        _rep_err.pop(key, None)
        _rep_recreate.discard(key)
        tid = r["result"]["message_thread_id"]
        _, topics = rep_conf()
        topics[key] = tid
        set_setting("rep_topics", json.dumps(topics))
    desc = next((d for k, n, d in REPORT_TOPICS if k == key), "")
    tg("sendMessage", chat_id=cid, message_thread_id=tid, text=f"✅ این تاپیک فعال شد.\n\n📌 {desc}")
    return tid


def rep_ensure_topics(cid):
    """فقط تاپیک‌های ساخته‌نشده (و حذف‌نشده توسط ادمین) را می‌سازد. (ساخته‌شده، ناموفق)"""
    made = failed = 0
    off = rep_off()
    for key, _, _ in REPORT_TOPICS:
        _, topics = rep_conf()
        if topics.get(key) or key in off:
            continue
        if rep_make_topic(cid, key):
            made += 1
        else:
            failed += 1
        time.sleep(3)
    return made, failed


def rep_apply_icons(cid):
    """ایموجی پروفایل همه‌ی تاپیک‌ها را بر اساس ایموجی داخل نامشان تنظیم می‌کند. تعداد موفق را برمی‌گرداند"""
    _, topics = rep_conf()
    done = 0
    for key, tid in topics.items():
        try:
            icon = rep_icon_for(key)
        except Exception:
            icon = None
        if not icon:
            continue
        r = tg("editForumTopic", chat_id=cid, message_thread_id=tid, name=_REP_ICON.get(key, ""), icon_custom_emoji_id=icon)
        if r.get("ok") or "not modified" in str(r.get("description", "")).lower():
            done += 1
        time.sleep(1.2)
    return done


def rep_delete_topic(cid, key):
    """حذف تاپیک از گروه (با همه‌ی پیام‌هایش) و خاموش‌کردن آن؛ دیگر خودکار ساخته نمی‌شود تا ادمین دوباره بسازد"""
    _, topics = rep_conf()
    tid = topics.get(key)
    ok = True
    if tid:
        r = tg("deleteForumTopic", chat_id=cid, message_thread_id=tid)
        desc = str(r.get("description", "")).lower()
        ok = bool(r.get("ok")) or "not found" in desc or "topic_id_invalid" in desc
    if ok:
        topics.pop(key, None)
        set_setting("rep_topics", json.dumps(topics))
        rep_set_off(key, True)
    return ok


def rep_connection_test(cid):
    ok = 0
    for _ in range(3):
        r = tg("sendMessage", chat_id=cid, text="تست اتصال ربات")
        ok += 1 if r.get("ok") else 0
        time.sleep(1.2)
    return ok


def rep_check_group(cid):
    """(True, None) یا (False, پیام خطای فارسی)"""
    g = tg("getChat", chat_id=cid, _timeout=15)
    if not g.get("ok"):
        return False, "گروهی با این آیدی پیدا نشد یا ربات عضو آن نیست. مطمئن شوید ربات را داخل گروه اضافه و ادمین کرده‌اید."
    ch = g["result"]
    if ch.get("type") != "supergroup":
        return False, "این چت «سوپرگروه» نیست. یک گروه بسازید و حالت Topics (انجمن) را از تنظیمات گروه روشن کنید."
    if not ch.get("is_forum"):
        return False, "حالت Topics (انجمن) در این گروه روشن نیست. از تنظیمات گروه آن را فعال کنید و دوباره آیدی را بفرستید."
    m = tg("getChatMember", chat_id=cid, user_id=BOT_ID, _timeout=15)
    st = (m.get("result") or {}).get("status")
    if not m.get("ok") or st != "administrator":
        return False, "ربات در این گروه ادمین نیست. آن را ادمین گروه کنید و دوباره بفرستید."
    res = m["result"]
    if res.get("can_manage_topics") is False:
        return False, "ربات اجازه‌ی «مدیریت تاپیک‌ها» (Manage Topics) را ندارد. هنگام ادمین‌کردن این دسترسی را روشن کنید."
    return True, None


def rep_setup_run(cid, admin_chat, admin_id):
    """در پس‌زمینه: ساخت تاپیک‌ها، تست اتصال، گزارش نتیجه به ادمین"""
    try:
        made, failed = rep_ensure_topics(cid)
        ok = rep_connection_test(cid)
        icons = 0
        try:
            icons = rep_apply_icons(cid)
        except Exception:
            logging.exception("rep_apply_icons")
        txt = ("📣 <b>نتیجه‌ی راه‌اندازی گزارشات</b>\n━━━━━━━━━━━━━━\n"
               f"📂 تاپیک‌های ساخته‌شده: <b>{_rp_n(made)}</b>" + (f" • ❌ ناموفق: <b>{_rp_n(failed)}</b>" if failed else "") + "\n"
               f"🎨 آیکن تاپیک‌ها: <b>{_rp_n(icons)}</b> از {_rp_n(len(REPORT_TOPICS))}\n"
               f"📡 تست اتصال: <b>{_rp_n(ok)} از ۳</b> پیام با موفقیت ارسال شد "
               + ("✅ اتصال برقرار است." if ok == 3 else "⚠️ اتصال کامل نیست؛ دسترسی‌های ربات در گروه را بررسی کنید."))
        if failed:
            errs = "\n".join(f"• {_REP_ICON[k]}: {_h(v)[:120]}" for k, v in _rep_err.items() if k in _REP_ICON)
            txt += ("\n\n⚠️ <b>ساخت این تاپیک‌ها نشد:</b>\n" + errs +
                    "\n\n♻️ ربات هر چند دقیقه خودکار دوباره تلاش می‌کند؛ یا از «📣 گزارشات ربات» دکمه‌ی «بررسی/ساخت تاپیک‌ها» را بزنید."
                    "\nتا ساخته‌شدن تاپیک، گزارش آن در General ارسال <b>نمی‌شود</b> و در صف می‌ماند.")
        _hsend(admin_chat, txt, _kb([_ab("📣 مدیریت گزارشات", "adm_p:x:rep", PRIMARY)]))
        set_setting("rep_last_backup", "0")
        set_setting("rep_last_day", (now_local().date() - timedelta(days=1)).isoformat())
        set_setting("rep_icons_v", "2")
    except Exception:
        logging.exception("rep_setup_run")


def rep_nag_admin(chat_id, user_id, state, data):
    """ادمین هر فعالیتی کند و گزارشات تنظیم نشده باشد: درخواست اجباری فعال‌سازی"""
    if rep_ready():
        return
    if state == "adm_in" and (data or {}).get("name") == "rep_chat":
        return
    now = time.time()
    if now - _rep_nag.get(user_id, 0) < REPORT_NAG_SEC:
        return
    _rep_nag[user_id] = now
    _hsend(chat_id, "سلام من روشن شدم.\nحالا برای شروع گزارشات منو تنظیم کن! 📖",
           _kb([_ab("📣 گزارشات ربات", "adm_p:x:rep_in", PRIMARY)]))


def rep_ask_text():
    cid, _ = rep_conf()
    cur = f"<code>{cid}</code>" if cid else "❌ هنوز ثبت نشده"
    return (
        "📣 در این بخش می‌توانید آیدی عددی گروه را برای ارسال اعلان ارسال نمایید.\n\n"
        "🚥 <b>آموزش تنظیم گروه:</b>\n"
        "۱. ابتدا یک گروه تلگرامی بسازید.\n"
        "۲. ربات ( @myidbot ) را عضو و ادمین گروه کنید.\n"
        "۳. حالت Topics یا انجمن گروه را از تنظیمات گروه روشن کنید.\n"
        "۴. ربات خودتان را ادمین گروه کنید.\n"
        "۵. حالا دستور زیر را در گروه ارسال کنید:\n"
        "<code>/getgroupid@myidbot</code>\n"
        "۶. آیدی عددی که ربات ارسال کرده را در همینجا ارسال کنید.\n\n"
        f"🆔 آیدی عددی فعلی شما: {cur}")


def rep_handle_chat_input(chat_id, admin_id, text, data):
    t = text.strip().translate(_ASCII_DIGITS)
    if not re.fullmatch(r"-?\d{6,20}", t):
        _err(chat_id, "آیدی عددی گروه را بفرستید؛ مثل -1001234567890")
        return True
    if t.startswith("-"):
        cid = int(t)
    elif t.startswith("100") and len(t) >= 13:
        cid = -int(t)
    else:
        cid = int("-100" + t)
    ok, why = rep_check_group(cid)
    if not ok:
        _err(chat_id, why)
        return True
    old, _ = rep_conf()
    if old != cid:
        set_setting("rep_topics", "{}")
        set_setting("rep_off", "[]")
    set_setting("rep_chat", cid)
    set_setting("rep_enabled", "1")
    set_state(admin_id, "admin_panel")
    _hsend(chat_id, "🔰 کانال با موفقیت تنظیم گردید. 🎉\n\n"
                    "⏰️ لطفاً چند لحظه صبر کنید تا تاپیک‌ ها به‌صورت خودکار ساخته شوند.\n\n"
                    "🚥 در صورتی که هنوز کامل ساخته نشده‌ صبر کنید!\nسیستم به‌طور خودکار آن‌ها را ایجاد میکند.")
    threading.Thread(target=rep_setup_run, args=(cid, chat_id, admin_id), daemon=True).start()
    return True


def render_report():
    cid, topics = rep_conf()
    on = rep_ready()
    off = rep_off()
    lines = []
    for key, name, _ in REPORT_TOPICS:
        mark = "⏸" if key in off else ("✅" if topics.get(key) else "❌")
        lines.append(f"{mark} {name}" + (" (حذف‌شده)" if key in off else ""))
    text = ("📣 <b>گزارشات ربات</b>\n" + LINE + "\n"
            f"📡 وضعیت: {'🟢 فعال' if on else '🔴 تنظیم نشده'}\n"
            f"🆔 گروه: {('<code>' + str(cid) + '</code>') if cid else '—'}\n\n"
            + "\n".join(lines)
            + f"\n\n📬 صف ارسال: <b>{_rp_n(_rep_q.qsize())}</b> گزارش")
    rows = [
        [_ab("📌 ثبت / تغییر گروه", "adm_p:x:rep_in", SUCCESS)],
        [_ab("🧪 تست اتصال", "adm_p:x:rep_test", PRIMARY), _ab("♻️ بررسی/ساخت تاپیک‌ها", "adm_p:x:rep_mk", PRIMARY)],
        [_ab("💾 بکاپ همین الان", "adm_p:x:rep_bk", PRIMARY), _ab("📊 گزارش امروز", "adm_p:x:rep_day", PRIMARY)],
        [_ab("🎨 تنظیم آیکن تاپیک‌ها", "adm_p:x:rep_ic", PRIMARY), _ab("🗑 حذف تاپیک", "adm_p:x:rep_dl", DANGER)],
    ]
    for key in [k for k, _, _ in REPORT_TOPICS if k in off]:
        rows.append([_ab(f"➕ ساخت مجدد: {_REP_ICON[key]}", f"adm_p:x:rep_mk1:{key}", SUCCESS)])
    rows.append([_ab("🔙 تنظیمات عمومی", "adm_p:g:home")])
    return text, _kb(*rows)


def render_report_delete_list():
    _, topics = rep_conf()
    rows = [[_ab(f"🗑 {n}", f"adm_p:x:rep_dc:{k}", DANGER)] for k, n, _ in REPORT_TOPICS if topics.get(k)]
    rows.append([_ab("🔙 گزارشات ربات", "adm_p:x:rep")])
    return ("🗑 <b>حذف تاپیک</b>\n" + LINE + "\nکدام تاپیک حذف شود؟\n⚠️ تاپیک با <b>همه‌ی پیام‌هایش</b> از گروه پاک می‌شود و گزارش آن دیگر ارسال نمی‌شود "
            "(هر وقت خواستید از همین صفحه دوباره ساخته می‌شود)."), _kb(*rows)


# ---------- بکاپ SQL ----------
def rep_make_backup():
    """(نام فایل، بایت‌ها، تعداد خط) — خروجی .sql؛ اگر بزرگ‌تر از حد تلگرام بود gzip می‌شود"""
    src = get_db()
    try:
        try:
            dump = "\n".join(src.iterdump()).encode("utf-8", "replace")
        except Exception:
            logging.exception("iterdump failed; per-table fallback")
            parts = ["BEGIN TRANSACTION;"]
            for (nm, ddl) in src.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL"):
                if nm.startswith("sqlite_"):
                    continue
                parts.append(ddl + ";")
                try:
                    for row in src.execute(f'SELECT * FROM "{nm}"'):
                        vals = []
                        for v in row:
                            if v is None:
                                vals.append("NULL")
                            elif isinstance(v, (int, float)):
                                vals.append(repr(v))
                            elif isinstance(v, bytes):
                                vals.append("X'" + v.hex() + "'")
                            else:
                                vals.append("'" + str(v).replace("'", "''") + "'")
                        parts.append(f'INSERT INTO "{nm}" VALUES(' + ",".join(vals) + ");")
                except Exception:
                    logging.exception("backup table %s", nm)
                    parts.append(f"-- table {nm} could not be dumped")
            parts.append("COMMIT;")
            dump = "\n".join(parts).encode("utf-8", "replace")
    finally:
        src.close()
    stamp_s = now_local().strftime("%Y%m%d_%H%M")
    name = f"jfj_backup_{stamp_s}.sql"
    if len(dump) > 48 * 1024 * 1024:
        return name + ".gz", _gzip.compress(dump), dump.count(b"\n")
    return name, dump, dump.count(b"\n")


_bak_warn = [0.0]


def _bak_notify(requester, text, name=None, data=None, cap=None):
    """نتیجه‌ی بکاپ را به ادمین می‌گوید؛ در صورت شکست، فایل را مستقیم در پیوی ادمین می‌فرستد"""
    targets = [requester] if requester else list(ADMIN_IDS)
    for aid in targets:
        if not requester and time.time() - _bak_warn[0] < 3600:
            return
        if name and data:
            _send_doc(aid, None, name, data, (cap or "") + "\n\n" + text, timeout=120)
        else:
            tg("sendMessage", chat_id=aid, text=text)
    if not requester:
        _bak_warn[0] = time.time()


def rep_send_backup(requester=None):
    """requester = آیدی ادمینی که دکمه را زده (نتیجه را همان‌جا می‌گیرد)؛ None = بکاپ خودکار.
    اگر ارسال به تاپیک ممکن نباشد، دلیل دقیق + خودِ فایل بکاپ به پیوی ادمین می‌آید (بی‌صدا شکست نمی‌خورد)."""
    name = data = cap = None
    try:
        off = "bak" in rep_off()
        if off and not requester:
            return False                       # تاپیک بکاپ عمداً خاموش/حذف شده؛ بکاپ خودکار نمی‌رود
        name, data, lines = rep_make_backup()
        users = 0
        try:
            users = _q1("SELECT COUNT(*) FROM users")
        except Exception:
            pass
        cap = (f"🗃 <b>بکاپ ربات</b>\n━━━━━━━━━━━━━━\n📄 {name}\n💽 حجم: {_rp_n(round(len(data) / 1024, 1))} کیلوبایت\n"
               f"👥 کاربران: {_rp_n(users)}" + _rp_time("زمان بکاپ"))
        if off:
            _bak_notify(requester, "ℹ️ تاپیک بکاپ حذف/غیرفعال است، برای همین فایل اینجا ارسال شد. "
                                   "(از «📣 گزارشات ربات» ← بررسی/ساخت تاپیک‌ها دوباره بسازید.)", name, data, cap)
            return True
        r = _rep_upload_doc("bak", name, data, cap)
        if not r.get("ok"):
            desc = str(r.get("description", ""))
            if "thread" in desc.lower():
                cid, _ = rep_conf()
                if cid and rep_make_topic(cid, "bak"):
                    r = _rep_upload_doc("bak", name, data, cap)
        if r.get("ok"):
            set_setting("rep_last_backup", str(time.time()))
            if requester:
                tg("sendMessage", chat_id=requester, text="✅ بکاپ در تاپیک ارسال شد.")
            return True
        why = str(r.get("description", r))
        logging.warning("backup send failed: %s", r)
        _bak_notify(requester, f"❌ ارسال بکاپ به تاپیک ناموفق بود: {why}\n📎 فایل بکاپ همین‌جا فرستاده شد.", name, data, cap)
        return False
    except Exception as e:
        logging.exception("rep_send_backup")
        try:
            _bak_notify(requester, f"❌ خطا در بکاپ: {type(e).__name__}: {e}", name, data, cap)
        except Exception:
            pass
        return False


# ---------- گزارش شبانه ----------
def _rep_casino(day):
    try:
        return GAMES.casino_day_block(day) if GAMES else ""
    except Exception:
        logging.exception("casino report")
        return ""


def rep_day_text(day, partial=False):
    d0 = datetime.fromisoformat(day)
    s = d0.replace(tzinfo=ZoneInfo(TIMEZONE)).astimezone(timezone.utc)
    e = s + timedelta(days=1)
    a, b = s.strftime("%Y-%m-%d %H:%M:%S"), e.strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as c:
        cnt = dict(c.execute("SELECT k, n FROM rep_daily WHERE day=?", (day,)).fetchall()) if _rep_db_ready[0] or _table_exists(c, "rep_daily") else {}
        new_users = c.execute("SELECT COUNT(*) FROM users WHERE created_at>=? AND created_at<?", (a, b)).fetchone()[0]
        via_ref = c.execute("SELECT COUNT(*) FROM users WHERE created_at>=? AND created_at<? AND referred_by IS NOT NULL", (a, b)).fetchone()[0]
        total_users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    g = lambda k: cnt.get(k, 0)
    jy, jm, jd = gregorian_to_jalali(d0.year, d0.month, d0.day)
    jdate = fa_digits(f"{jy:04d}/{jm:02d}/{jd:02d}")
    title = "گزارش امروز تا این لحظه" if partial else "گزارش شبانه"
    return (
        f"📊 <b>{title}</b> — {jdate}\n━━━━━━━━━━━━━━\n"
        f"👥 <b>کاربران</b>\n• کاربر جدید: {_rp_n(new_users)} (از زیرمجموعه‌گیری: {_rp_n(via_ref)})\n"
        f"• پاداش معرف پرداخت‌شده: {_rp_n(g('ref_ok'))} مورد\n\n"
        f"🎗 <b>درخواست‌های JFJ</b>\n• ثبت‌شده: {_rp_n(g('req_new'))} (جمع ممبر: {_rp_n(g('req_members'))} • هزینه: {_rp_t(g('req_cost'))} شاهی)\n"
        f"• تکمیل‌شده: {_rp_n(g('req_done'))} • عزل ربات: {_rp_n(g('req_removed'))} • تغییر لینک: {_rp_n(g('req_relinked'))} • حذف مدیر: {_rp_n(g('req_deleted'))}\n"
        f"• جوین موفق: {_rp_n(g('joins'))} • لفت: {_rp_n(g('leaves'))}\n\n"
        f"🛍 <b>خرید</b>\n• سفارش خدمات: {_rp_n(g('svc_new'))} (هزینه: {_rp_t(g('svc_cost'))} شاهی)\n"
        f"• تکمیل: {_rp_n(g('svc_done'))} • لغو: {_rp_n(g('svc_cancel'))}\n"
        f"• خرید شاهی/اسپانسری تأییدشده: {_rp_n(g('inv_paid'))} (مبلغ: {_rp_n(g('inv_toman'))} تومان • شاهی فروخته‌شده: {_rp_t(g('tok_sold'))})\n\n"
        f"🧾 <b>رسیدها</b>\n• دریافت‌شده: {_rp_n(g('rcp_new'))} • تأیید: {_rp_n(g('rcp_ok'))} • رد: {_rp_n(g('rcp_no'))}\n\n"
        f"💸 <b>بانک انتقال</b>\n• تعداد انتقال: {_rp_n(g('xfr_n'))} • مجموع: {_rp_t(g('xfr_sum'))} شاهی\n\n"
        f"💰 <b>مدیریت موجودی</b>\n• افزایش دستی/همگانی: {_rp_t(g('adm_add'))} شاهی • کاهش: {_rp_t(g('adm_sub'))} شاهی\n\n"
        + _rep_casino(day)
        + f"👤 کل کاربران ربات (لحظه‌ی گزارش): {_rp_n(total_users)}"
        + _rp_time("زمان تهیه گزارش"))


def rep_send_day(day, partial=False):
    try:
        txt = rep_day_text(day, partial)
    except Exception:
        logging.exception("rep_day_text")
        return
    report("day", txt)


def rep_scheduler():
    """بکاپ هر ۶ ساعت + گزارش شبانه بعد از نیمه‌شب + ترمیم خودکار تاپیک‌های ناقص"""
    time.sleep(20)
    last_heal = 0.0
    while True:
        try:
            if rep_ready():
                cid, topics = rep_conf()
                if time.time() - last_heal > 300:
                    last_heal = time.time()
                    off = rep_off()
                    if any(not topics.get(k) and k not in off for k, _, _ in REPORT_TOPICS):
                        rep_ensure_topics(cid)
                        rep_apply_icons(cid)
                    elif get_setting("rep_icons_v", "") != "2":
                        rep_apply_icons(cid)
                        set_setting("rep_icons_v", "2")
                try:
                    last = float(get_setting("rep_last_backup", "0") or 0)
                except Exception:
                    last = 0
                if "bak" not in rep_off() and time.time() - last >= REPORT_BACKUP_SEC:
                    set_setting("rep_last_backup", str(time.time() - REPORT_BACKUP_SEC + 300))
                    rep_send_backup()
                yday = (now_local().date() - timedelta(days=1)).isoformat()
                if get_setting("rep_last_day", "") != yday:
                    set_setting("rep_last_day", yday)
                    rep_send_day(yday)
        except Exception:
            logging.exception("rep_scheduler")
        time.sleep(45)


def rep_worker():
    while True:
        item = _rep_q.get()
        try:
            if not rep_ready() or item["topic"] in rep_off():
                continue
            reply_to = rep_msg_get(item.get("reply")) if item.get("reply") else None
            if item["kind"] == "text":
                kw = dict(text=item["b"][:4000], parse_mode="HTML", disable_web_page_preview=True)
                if reply_to:
                    kw.update(reply_to_message_id=reply_to, allow_sending_without_reply=True)
                r = None
                for attempt in range(3):
                    r = _rep_post("sendMessage", item["topic"], **kw)
                    if r.get("ok"):
                        rep_msg_set(item.get("key"), (r.get("result") or {}).get("message_id"))
                        break
                    ra = (r.get("parameters") or {}).get("retry_after")
                    if ra:
                        time.sleep(min(int(ra) + 1, 60))
                        continue
                    break
            else:
                kw = dict(from_chat_id=item["from"], message_id=item["mid"], caption=item.get("cap") or None, parse_mode="HTML")
                r = _rep_post("copyMessage", item["topic"], **kw)
                if r.get("ok"):
                    rep_msg_set(item.get("key"), (r.get("result") or {}).get("message_id"))
                elif "parse" in str(r.get("description", "")).lower():
                    kw.pop("parse_mode")
                    r = _rep_post("copyMessage", item["topic"], **kw)
            if r and not r.get("ok") and not r.get("off"):
                logging.warning("report send failed: %s", r)
                if r.get("description") == "no_topic" and item.get("n", 0) < 6:
                    item["n"] = item.get("n", 0) + 1
                    tm = threading.Timer(90, lambda it=item: _rep_q.put_nowait(it))  # بعد از ساخته‌شدن تاپیک دوباره تلاش می‌شود
                    tm.daemon = True
                    tm.start()
        except Exception:
            logging.exception("rep_worker")
        time.sleep(REPORT_SEND_GAP)


# ---------- سازنده‌ی گزارش هر رویداد ----------
def rep_ev_service(code):
    def b():
        with get_db() as c:
            r = c.execute("SELECT user_id, service, quantity, extra, token_cost, link FROM service_orders WHERE tracking_code=?", (code,)).fetchone()
        if not r:
            return None
        uid, svc, qty, extra, cost, link = r
        return (_rp_head("buy", "سفارش جدید خدمات") + f"🔍 کد پیگیری: <code>{code}</code>\n🛒 خدمت: {_h(svc)}\n🔢 تعداد: {_rp_n(qty)}\n"
                + (f"😀 ری‌اکشن: {_h(extra)}\n" if extra else "") + f"🔗 لینک: {_h(link)}\n💎 هزینه: {_rp_t(cost)} شاهی\n"
                + _rp_user(uid) + f"\n🪙 موجودی فعلی کاربر: {_rp_bal(uid)} شاهی" + _rp_time("زمان ثبت"))
    rep_count("svc_new")
    try:
        with get_db() as c:
            r = c.execute("SELECT token_cost FROM service_orders WHERE tracking_code=?", (code,)).fetchone()
        rep_count("svc_cost", r[0] if r else 0)
    except Exception:
        pass
    report("buy", b, key=f"svc:{code}")


def rep_ev_service_result(code, ok, admin_name):
    def b():
        with get_db() as c:
            r = c.execute("SELECT user_id, service, quantity, token_cost, link FROM service_orders WHERE tracking_code=?", (code,)).fetchone()
        if not r:
            return None
        uid, svc, qty, cost, link = r
        return (_rp_head("buy", "سفارش خدمات تکمیل شد ✅" if ok else "سفارش خدمات لغو شد ❌")
                + f"🔍 کد پیگیری: <code>{code}</code>\n🛒 {_h(svc)} • {_rp_n(qty)}\n🔗 {_h(link)}\n"
                + _rp_user(uid) + f"\n👮 توسط: {_h(admin_name)}"
                + ("" if ok else f"\n💰 بازگشت هزینه: {_rp_t(cost)} شاهی (موجودی فعلی: {_rp_bal(uid)})") + _rp_time())
    rep_count("svc_done" if ok else "svc_cancel")
    report("buy", b, reply=f"svc:{code}")
    if not ok:
        def f():
            with get_db() as c:
                r = c.execute("SELECT user_id, token_cost, service FROM service_orders WHERE tracking_code=?", (code,)).fetchone()
            if not r:
                return None
            return (_rp_head("fin", "افزایش موجودی (بازگشت هزینه‌ی سفارش لغوشده)") + f"🔍 سفارش: <code>{code}</code> • {_h(r[2])}\n"
                    f"➕ مقدار: {_rp_t(r[1])} شاهی\n" + _rp_user(r[0]) + f"\n🪙 موجودی فعلی: {_rp_bal(r[0])} شاهی" + _rp_time())
        report("fin", f)


def rep_ev_invoice_paid(code):
    try:
        with get_db() as c:
            _k = c.execute("SELECT kind FROM invoices WHERE code=?", (code,)).fetchone()
        topic = "spn" if _k and _k[0] == "sponsor" else "buy"
    except Exception:
        topic = "buy"

    def b():
        with get_db() as c:
            r = c.execute("SELECT buyer_id, kind, product_name, final_amount, method, meta FROM invoices WHERE code=?", (code,)).fetchone()
        if not r:
            return None
        uid, kind, product, amount, method, meta = r
        try:
            meta = json.loads(meta or "{}")
        except Exception:
            meta = {}
        what = {"jtoken": "خرید شاهی", "sponsor": "خرید اسپانسری"}.get(kind, "خرید")
        extra = ""
        if kind == "jtoken":
            extra = f"🪙 شاهی: {_rp_t(meta.get('tokens', 0))}" + (f" + بونوس {_rp_t(meta.get('bonus'))}" if meta.get("bonus") else "") + "\n"
        elif kind == "sponsor":
            extra = f"⏳ مدت: {_rp_n(meta.get('hours', 0))} ساعت\n"
        return (_rp_head(topic, f"{what} (پرداخت تأیید شد)") + f"🔍 کد فاکتور: <code>{code}</code>\n📦 محصول: {_h(product)}\n"
                + extra + f"💵 مبلغ: {_rp_n(amount)} تومان\n💳 روش: {_h(METHOD_LABELS.get(method, method or '—'))}\n"
                + _rp_user(uid) + f"\n🪙 موجودی فعلی: {_rp_bal(uid)} شاهی" + _rp_time("زمان تأیید"))
    report(topic, b, key=f"spi:{code}" if topic == "spn" else None)
    try:
        with get_db() as c:
            r = c.execute("SELECT buyer_id, kind, final_amount, meta, product_name FROM invoices WHERE code=?", (code,)).fetchone()
        if not r:
            return
        meta = json.loads(r[3] or "{}")
        rep_count("inv_paid")
        rep_count("inv_toman", r[2])
        if r[1] == "jtoken":
            tk = (meta.get("tokens", 0) or 0) + (meta.get("bonus", 0) or 0)
            rep_count("tok_sold", tk)

            def f():
                return (_rp_head("fin", "افزایش موجودی (خرید شاهی)") + f"🔍 فاکتور: <code>{code}</code> • {_h(r[4])}\n"
                        f"➕ مقدار: {_rp_t(tk)} شاهی\n💵 مبلغ پرداختی: {_rp_n(r[2])} تومان\n" + _rp_user(r[0])
                        + f"\n🪙 موجودی فعلی: {_rp_bal(r[0])} شاهی" + _rp_time())
            report("fin", f)
    except Exception:
        logging.exception("rep_ev_invoice_paid")


def rep_ev_receipt(code, uid, from_chat, mid, media=True, txt=""):
    """رسید + اطلاعات در یک پیام (عکس/فایل با کپشن)؛ برای رسید متنی (هش ارزی) متن گزارش شامل هش است"""
    rep_count("rcp_new")

    def info():
        with get_db() as c:
            r = c.execute("SELECT product_name, final_amount, method FROM invoices WHERE code=?", (code,)).fetchone()
        if not r:
            return None
        return (_rp_head("rcp", "رسید جدید دریافت شد") + f"🔍 کد فاکتور: <code>{code}</code>\n📦 محصول: {_h(r[0])}\n💵 مبلغ فاکتور: {_rp_n(r[1])} تومان\n"
                f"💳 روش: {_h(METHOD_LABELS.get(r[2], r[2] or '—'))}\n" + _rp_user(uid)
                + ("" if media else f"\n🔗 هش/متن رسید: <code>{_h(txt)[:300]}</code>")
                + "\n⏳ وضعیت: در انتظار بررسی ادمین" + _rp_time("زمان دریافت"))
    if media:
        report_copy("rcp", from_chat, mid, info, key=f"rcp:{code}")
    else:
        report("rcp", info, key=f"rcp:{code}")


def rep_ev_receipt_result(code, ok, admin_name):
    rep_count("rcp_ok" if ok else "rcp_no")

    def b():
        with get_db() as c:
            r = c.execute("SELECT buyer_id, product_name, final_amount FROM invoices WHERE code=?", (code,)).fetchone()
        if not r:
            return None
        return (_rp_head("rcp", "رسید تأیید شد ✅" if ok else "رسید رد شد ❌") + f"🔍 کد فاکتور: <code>{code}</code>\n📦 {_h(r[1])}\n💵 {_rp_n(r[2])} تومان\n"
                + _rp_user(r[0]) + f"\n👮 توسط: {_h(admin_name)}" + _rp_time("زمان بررسی"))
    report("rcp", b, reply=f"rcp:{code}")


def rep_ev_gateway(code):
    def b():
        with get_db() as c:
            r = c.execute("SELECT buyer_id, product_name, final_amount, ref FROM invoices WHERE code=?", (code,)).fetchone()
        if not r:
            return None
        return (_rp_head("rcp", "پرداخت آنلاین موفق ✅") + f"🔍 کد فاکتور: <code>{code}</code>\n📦 {_h(r[1])}\n💵 {_rp_n(r[2])} تومان\n"
                f"🔖 شناسه تراکنش: <code>{_h(r[3] or '—')}</code>\n" + _rp_user(r[0]) + _rp_time("زمان پرداخت"))
    report("rcp", b)


def rep_ev_admin_balance(admin_id, uid, kind, n, old_bal):
    rep_count("adm_add" if kind == "uadd" else "adm_sub", n if kind != "uset" else 0)

    def b():
        title = {"uadd": "افزایش موجودی توسط مدیر", "usub": "کاهش موجودی توسط مدیر", "uset": "تنظیم موجودی توسط مدیر"}[kind]
        sign = {"uadd": "➕", "usub": "➖", "uset": "🟰"}[kind]
        return (_rp_head("fin", title) + f"{sign} مقدار: {_rp_t(n)} شاهی\n" + _rp_user(uid)
                + f"\n🪙 موجودی قبل: {_rp_t(old_bal)} ← بعد: {_rp_bal(uid)} شاهی\n" + _rp_user(admin_id, "👮 مدیر") + _rp_time())
    report("fin", b)


def rep_ev_mass(admin_id, mode, amt, n_users):
    rep_count("adm_add" if mode == "add" else "adm_sub", amt * n_users)
    report("fin", lambda: (_rp_head("fin", "شارژ همگانی" if mode == "add" else "کسر همگانی")
                           + f"{'➕' if mode == 'add' else '➖'} مقدار برای هر کاربر: {_rp_t(amt)} شاهی\n👥 تعداد کاربران: {_rp_n(n_users)}\n"
                           + f"💎 مجموع: {_rp_t(amt * n_users)} شاهی\n" + _rp_user(admin_id, "👮 مدیر") + _rp_time()))


def rep_ev_refund(admin_id, uid, code, amt, note=None):
    rep_count("adm_add", amt)
    report("fin", lambda: (_rp_head("fin", "افزایش موجودی (" + (note or "بازگشت هزینه‌ی درخواست JFJ حذف‌شده") + ")") + f"🔍 درخواست: <code>{code}</code>\n"
                           f"➕ مقدار: {_rp_t(amt)} شاهی\n" + _rp_user(uid) + f"\n🪙 موجودی فعلی: {_rp_bal(uid)} شاهی"
                           + ("\n" + _rp_user(admin_id, "👮 مدیر") if admin_id else "") + _rp_time()))


def rep_ev_ref_new(referrer_id, new_user):
    rep_count("ref_new")
    nid = (new_user or {}).get("id")

    def b():
        total = get_referral_count(referrer_id)
        return (_rp_head("ref", "زیرمجموعه جدید") + _rp_user(referrer_id, "🧲 معرف") + "\n"
                + (_rp_user(nid, "🆕 کاربر جدید") + "\n" if nid else "") + f"👥 مجموع زیرمجموعه‌های معرف: {_rp_n(total)}"
                + f"\n⏳ پاداش بعد از کسب {_rp_t(REFERRAL_ACTIVITY_THRESHOLD)} شاهی توسط زیرمجموعه پرداخت می‌شود." + _rp_time())
    report("ref", b, key=f"ref:{nid}" if nid else None)


def rep_ev_ref_ok(referrer_id, user_id):
    rep_count("ref_ok")
    report("ref", lambda: (_rp_head("ref", "قبولی زیرمجموعه ✅ (پاداش معرف پرداخت شد)") + _rp_user(referrer_id, "🧲 معرف") + "\n"
                           + _rp_user(user_id, "✅ زیرمجموعه") + f"\n🎁 پاداش: {_rp_t(REFERRAL_REWARD)} شاهی\n🪙 موجودی فعلی معرف: {_rp_bal(referrer_id)} شاهی" + _rp_time()),
           reply=f"ref:{user_id}")


def rep_ev_request(code):
    rep_count("req_new")
    try:
        with get_db() as c:
            r0 = c.execute("SELECT member_count, token_cost FROM requests WHERE tracking_code=?", (code,)).fetchone()
        if r0:
            rep_count("req_members", r0[0])
            rep_count("req_cost", r0[1])
    except Exception:
        pass

    def b():
        with get_db() as c:
            r = c.execute("SELECT user_id, member_count, token_cost, link, chat_id FROM requests WHERE tracking_code=?", (code,)).fetchone()
        if not r:
            return None
        return (_rp_head("jfj", "درخواست JFJ جدید") + f"🔍 کد پیگیری: <code>{code}</code>\n🔗 لینک: {_h(r[3])}\n"
                f"🆔 آیدی چت: <code>{r[4] if r[4] else '—'}</code>\n🔢 تعداد ممبر: {_rp_n(r[1])}\n💎 هزینه: {_rp_t(r[2])} شاهی\n"
                + _rp_user(r[0]) + f"\n🪙 موجودی فعلی: {_rp_bal(r[0])} شاهی" + _rp_time("زمان ثبت"))
    report("jfj", b, key=f"req:{code}")


def rep_ev_request_state(code, state, admin_name=None):
    rep_count({"completed": "req_done", "removed": "req_removed", "deleted": "req_deleted", "relinked": "req_relinked"}.get(state, "req_x"))

    def b():
        with get_db() as c:
            r = c.execute("SELECT user_id, member_count, token_cost, link FROM requests WHERE tracking_code=?", (code,)).fetchone()
        if not r:
            return None
        done = get_join_count(code)
        title, extra = {
            "completed": ("درخواست JFJ تکمیل شد ✅", ""),
            "removed": ("ربات از کانال/گروه عزل شد ⛔", "\n📌 وضعیت: «ربات عزل شد» (هزینه برگشت داده نشد)"),
            "deleted": ("درخواست توسط مدیریت حذف شد 🗑", f"\n👮 توسط: {_h(admin_name or 'مدیر')}"),
            "relinked": ("لینک کانال/گروه تغییر کرد؛ درخواست کنسل شد 🔗", f"\n📌 {_h(admin_name or '')}"),
        }[state]
        return (_rp_head("jfj", title) + f"🔍 کد پیگیری: <code>{code}</code>\n🔗 {_h(r[3])}\n👥 پیشرفت: {_rp_n(done)} از {_rp_n(r[1])}\n"
                + _rp_user(r[0]) + extra + _rp_time())
    report("jfj", b, reply=f"req:{code}")


def _rp_sub_lines(sid):
    r = sub_row(sid)
    if not r:
        return None, ""
    _, uid, inv, hours, status, started, ends, ckind, lkind, cref, invite = r
    st = _SUB_ST.get(sub_state(status, ends), status)
    lines = (f"🆔 اشتراک: <code>{sid}</code> • فاکتور: <code>{_h(inv or '—')}</code>\n⏳ مدت: {_rp_t(hours)} ساعت\n📌 وضعیت: {st}\n"
             f"📢 نوع: {'عمومی' if ckind == 'public' else 'خصوصی'} • آیدی: {_h(cref or '—')}\n")
    if invite:
        lines += f"🔗 لینک: {_h(invite)}\n"
    if ends:
        lines += f"⏰ پایان: {_h(_fa_dt(ends))}\n"
    return uid, lines


def rep_ev_sponsor_new(sid, code):
    def b():
        uid, lines = _rp_sub_lines(sid)
        if not uid:
            return None
        return (_rp_head("spn", "اشتراک اسپانسری جدید (منتظر فعال‌سازی)") + lines + _rp_user(uid) + _rp_time("زمان ثبت"))
    report("spn", b, key=f"sub:{sid}", reply=f"spi:{code}")


def rep_ev_sponsor(kind, sid, detail="", admin_id=None):
    """kind: act / ah / sh / can / del"""
    title = {"act": "اسپانسری فعال شد ✅", "ah": "افزودن ساعت به اسپانسری ➕", "sh": "کسر ساعت از اسپانسری ➖",
             "can": "اشتراک اسپانسری لغو شد ⛔", "del": "اشتراک اسپانسری حذف شد 🗑"}[kind]
    snap = {}
    try:
        uid, lines = _rp_sub_lines(sid)
        snap = {"uid": uid, "lines": lines}
    except Exception:
        pass

    def b():
        if not snap.get("uid"):
            return None
        if kind in ("del",):
            lines = snap["lines"]
        else:
            uid2, lines = _rp_sub_lines(sid)
            lines = lines or snap["lines"]
        return (_rp_head("spn", title) + lines + (f"📝 {_h(detail)}\n" if detail else "") + _rp_user(snap["uid"])
                + ("\n" + _rp_user(admin_id, "👮 مدیر") if admin_id else "") + _rp_time())
    report("spn", b, reply=f"sub:{sid}")


def rep_ev_leave(user_id, owner_id, code, link, penalty, refund):
    rep_count("leaves")

    def b():
        return (_rp_head("lft", "لفت کاربر") + f"🔍 سفارش: <code>{code}</code>\n🔗 کانال/گروه: {_h(link)}\n"
                + _rp_user(user_id, "🚪 لفت‌دهنده") + f"\n⛔ جریمه: {_rp_t(penalty)} شاهی • موجودی فعلی: {_rp_bal(user_id)}\n"
                + _rp_user(owner_id, "👑 صاحب سفارش") + f"\n🔔 بازگشت به صاحب: {_rp_t(refund)} شاهی • موجودی فعلی: {_rp_bal(owner_id)}" + _rp_time("زمان لفت"))
    report("lft", b)


def rep_ev_transfer(sender_id, recipient_id, amount):
    rep_count("xfr_n")
    rep_count("xfr_sum", amount)
    report("xfr", lambda: (_rp_head("xfr", "انتقال شاهی") + f"💎 مقدار: {_rp_t(amount)} شاهی\n" + _rp_user(sender_id, "📤 فرستنده")
                           + f"\n🪙 موجودی فعلی فرستنده: {_rp_bal(sender_id)}\n" + _rp_user(recipient_id, "📥 گیرنده")
                           + f"\n🪙 موجودی فعلی گیرنده: {_rp_bal(recipient_id)}" + _rp_time("زمان انتقال")))



XPAGES["rep"] = render_report


# =====================================================================
#  ♻️ بازیابی بکاپ از پنل مدیریت (فایل را همان‌جا بفرستید؛ ربات خودش دیتابیس را جایگزین می‌کند)
#  سازگار با: .sql ، .sql.gz ، .db/.sqlite ، .zip ، و فایل روی سرور (restore.*) برای فایل‌های بزرگ‌تر از ۲۰ مگابایت
#  روی PythonAnywhere / Railway / cPanel / aaPanel / هر هاست دیگر یکسان کار می‌کند (بدون جایگزینی فایل؛ با backup-API خود SQLite)
# =====================================================================
RS_MAX_DL = 20 * 1024 * 1024            # سقف دانلود فایل از طریق Bot API
RS_MAX_RAW = 600 * 1024 * 1024          # سقف حجم بعد از باز کردن gzip/zip
RS_NAMES = ("restore",)                 # فایل‌های روی سرور باید با این نام شروع شوند
_RS_EXT = (".sql", ".sql.gz", ".gz", ".db", ".sqlite", ".sqlite3", ".zip")
_RS_PRAGMAS = {"foreign_keys", "user_version", "journal_mode", "synchronous", "page_size", "encoding",
               "application_id", "defer_foreign_keys", "legacy_alter_table", "cache_size", "busy_timeout"}


def _rs_auth(action, a1, a2, dbname, trigger):
    """امنیت: اسکریپت SQL بکاپ اجازه‌ی ATTACH/DETACH ندارد و PRAGMAهای غیرمجاز نادیده گرفته می‌شوند"""
    if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_PRAGMA and (a1 or "").lower() not in _RS_PRAGMAS:
        return sqlite3.SQLITE_IGNORE
    return sqlite3.SQLITE_OK


def _rs_unwrap(raw, fname, depth=0):
    """gzip/zip را تا رسیدن به SQL یا فایل SQLite باز می‌کند → (bytes, نام)"""
    import gzip, zipfile, io
    if depth > 3:
        raise ValueError("فایل چندلایه است؛ فقط یک‌بار فشرده‌سازی پشتیبانی می‌شود.")
    if raw[:2] == b"\x1f\x8b":
        out = bytearray()
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as gz:
            while True:
                chunk = gz.read(1 << 20)
                if not chunk:
                    break
                out += chunk
                if len(out) > RS_MAX_RAW:
                    raise ValueError("حجم فایل بعد از باز شدن بیش از حد بزرگ است.")
        return _rs_unwrap(bytes(out), re.sub(r"\.gz$", "", fname, flags=re.I), depth + 1)
    if raw[:4] == b"PK\x03\x04":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = [n for n in z.namelist() if not n.endswith("/")]
            if not names:
                raise ValueError("فایل zip خالی است.")
            pick = next((n for n in names if n.lower().endswith((".sql", ".db", ".sqlite", ".sqlite3", ".gz"))), names[0])
            info = z.getinfo(pick)
            if info.file_size > RS_MAX_RAW:
                raise ValueError("حجم فایل داخل zip بیش از حد بزرگ است.")
            return _rs_unwrap(z.read(pick), pick, depth + 1)
    return raw, fname


def rs_prepare(raw, fname):
    """فایل بکاپ (هر قالبی) → یک دیتابیس موقت سالم و بررسی‌شده کنار دیتابیس اصلی. (مسیر، اطلاعات) برمی‌گرداند؛ خطا = ValueError"""
    raw, fname = _rs_unwrap(raw, fname)
    d = os.path.dirname(os.path.abspath(DB_PATH)) or "."
    stamp = str(int(time.time() * 1000))
    tmp = os.path.join(d, f"restore_tmp_{stamp}.db")
    script = None
    if raw[:16] == b"SQLite format 3\x00":
        srcp = os.path.join(d, f"restore_src_{stamp}.db")
        with open(srcp, "wb") as f:
            f.write(raw)
        try:
            sc = sqlite3.connect(f"file:{srcp}?mode=ro", uri=True)
            try:
                ok_ = sc.execute("PRAGMA quick_check").fetchone()
                if not ok_ or ok_[0] != "ok":
                    raise ValueError("فایل دیتابیس آسیب دیده است (quick_check ناموفق).")
                script = "\n".join(sc.iterdump())
            finally:
                sc.close()
        except sqlite3.DatabaseError as e:
            raise ValueError(f"فایل دیتابیس قابل خواندن نیست: {e}")
        finally:
            try:
                os.remove(srcp)
            except OSError:
                pass
    else:
        try:
            script = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            script = raw.decode("utf-8", "replace")
        if not re.search(r"create\s+table", script, re.I):
            raise ValueError("این فایل بکاپ ربات (SQL یا دیتابیس SQLite) به نظر نمی‌رسد.")
    try:
        conn = sqlite3.connect(tmp)
        try:
            conn.set_authorizer(_rs_auth)
            conn.executescript(script)
            conn.set_authorizer(None)
            conn.commit()
            chk = conn.execute("PRAGMA integrity_check").fetchone()
            if not chk or chk[0] != "ok":
                raise ValueError("بررسی سلامت دیتابیس بازیابی‌شده ناموفق بود.")
            tabs = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"users", "settings"} <= tabs:
                raise ValueError("جدول‌های اصلی ربات (users/settings) در این بکاپ نیست؛ بکاپ ربات دیگری است.")
            n_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            tokens = conn.execute("SELECT COALESCE(SUM(tokens),0) FROM users").fetchone()[0]
            try:
                last = conn.execute("SELECT MAX(created_at) FROM users").fetchone()[0]
            except sqlite3.DatabaseError:
                last = None
        finally:
            conn.close()
    except sqlite3.DatabaseError as e:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise ValueError(f"خطا در اجرای SQL بکاپ: {e}")
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return tmp, {"fname": fname, "tables": len(tabs), "users": n_users, "tokens": tokens, "last": last,
                 "size": os.path.getsize(tmp)}


def rs_server_files():
    """فایل‌های restore.* که کنار دیتابیس/ربات/پوشه‌ی جاری گذاشته شده‌اند (برای فایل‌های بزرگ‌تر از ۲۰ مگابایت)"""
    seen, out = set(), []
    dirs = [os.path.dirname(os.path.abspath(DB_PATH)), os.path.dirname(os.path.abspath(__file__)), os.getcwd()]
    for d in dirs:
        if d in seen or not os.path.isdir(d):
            continue
        seen.add(d)
        try:
            for n in sorted(os.listdir(d)):
                low = n.lower()
                if low.startswith(RS_NAMES) and low.endswith(_RS_EXT) and os.path.isfile(os.path.join(d, n)):
                    out.append(os.path.join(d, n))
        except OSError:
            pass
    return out[:4]


def rs_host_note():
    path = os.path.abspath(DB_PATH)
    if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID") or os.environ.get("RAILWAY_SERVICE_ID"):
        vol = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
        if vol and path.startswith(vol.rstrip("/") + "/"):
            return "🚆 Railway — ✅ دیتابیس روی Volume است و بعد از هر دیپلوی می‌ماند."
        return ("🚆 Railway — ⚠️ دیتابیس روی Volume نیست؛ با هر دیپلوی جدید پاک می‌شود! یک Volume (مثلاً در /data) بسازید و "
                "متغیر <code>DB_PATH=/data/bot.db</code> را تنظیم کنید.")
    if os.environ.get("PYTHONANYWHERE_DOMAIN") or "pythonanywhere" in path.lower() or path.startswith("/home/"):
        return "🐍 PythonAnywhere/هاست اشتراکی — ✅ فایل‌ها دائمی‌اند."
    if "/www/wwwroot" in path:
        return "🧩 aaPanel — ✅ فایل‌ها دائمی‌اند."
    if "public_html" in path or os.path.isdir(os.path.expanduser("~/.cpanel")):
        return "🗂 cPanel — ✅ فایل‌ها دائمی‌اند."
    return "🖥 سرور/هاست — ✅ فایل‌ها دائمی‌اند (اگر داکر دارید، دیتابیس را روی Volume بگذارید)."


def render_restore():
    for f in os.listdir(os.path.dirname(os.path.abspath(DB_PATH)) or "."):      # نظافت فایل‌های موقتِ جامانده
        if f.startswith(("restore_tmp_", "restore_src_")):
            fp = os.path.join(os.path.dirname(os.path.abspath(DB_PATH)) or ".", f)
            try:
                if time.time() - os.path.getmtime(fp) > 3600:
                    os.remove(fp)
            except OSError:
                pass
    try:
        size = os.path.getsize(DB_PATH)
    except OSError:
        size = 0
    files = rs_server_files()
    text = ("♻️ <b>بازیابی بکاپ</b>\n" + LINE + "\n"
            f"{rs_host_note()}\n"
            f"📍 مسیر دیتابیس: <code>{_h(os.path.abspath(DB_PATH))}</code>\n"
            f"💽 حجم فعلی: {_rp_n(round(size / 1024, 1))} کیلوبایت • 👥 کاربران: {_rp_n(_q1('SELECT COUNT(*) FROM users'))}\n\n"
            "📤 <b>روش اول:</b> دکمه‌ی «ارسال فایل بکاپ» را بزنید و فایل بکاپ را (همان فایلی که ربات در تاپیک بکاپ می‌فرستد؛ "
            "<code>.sql</code> یا <code>.sql.gz</code> یا <code>.db</code> یا <code>.zip</code>) همین‌جا بفرستید.\n"
            "📂 <b>روش دوم (فایل بزرگ‌تر از ۲۰ مگابایت):</b> فایل را با نام <code>restore.sql</code> (یا restore.sql.gz / restore.db) "
            "کنار فایل‌های ربات یا کنار دیتابیس آپلود کنید؛ بعد دکمه‌اش اینجا ظاهر می‌شود.\n\n"
            "🛡 قبل از هر بازیابی، از وضعیت فعلی یک بکاپ گرفته و برای شما ارسال می‌شود تا هر لحظه برگردید. "
            "بعد از بازیابی نیازی به ری‌استارت نیست؛ ساختار جدول‌ها هم خودکار با نسخه‌ی فعلی ربات هماهنگ می‌شود.")
    rows = [[_ab("📤 ارسال فایل بکاپ", "adm_p:x:rs_arm", SUCCESS)]]
    for i, fp in enumerate(files):
        rows.append([_ab(f"📂 {os.path.basename(fp)} ({_rp_n(round(os.path.getsize(fp) / 1024))} KB)", f"adm_p:x:rs_f:{i}", SUCCESS)])
    rows.append([_ab("💾 بکاپ همین الان", "adm_p:x:rs_bk", PRIMARY)])
    rows.append([_ab("🔙 تنظیمات عمومی", "adm_p:g:home", DANGER)])
    return text, _kb(*rows)


def _rs_summary(info, now_users, now_tokens):
    last = info["last"]
    return ("♻️ <b>تأیید بازیابی بکاپ</b>\n" + LINE + "\n"
            f"📄 فایل: <code>{_h(info['fname'])}</code> • {_rp_n(round(info['size'] / 1024, 1))} کیلوبایت\n"
            f"🗂 جدول‌ها: {_rp_n(info['tables'])}\n"
            f"👥 کاربران: <b>{_rp_n(info['users'])}</b> در بکاپ • {_rp_n(now_users)} فعلی\n"
            f"🪙 مجموع شاهی: <b>{_t(info['tokens'])}</b> در بکاپ • {_t(now_tokens)} فعلی\n"
            + (f"🕒 آخرین ثبت‌نام در بکاپ: {_h(str(last))}\n" if last else "") +
            "\n⚠️ <b>با تأیید، تمام داده‌های فعلی ربات با این بکاپ جایگزین می‌شود.</b>\n"
            "قبل از آن یک بکاپ از وضعیت فعلی گرفته و برایتان ارسال می‌شود.")


def _rs_download(message):
    doc = message["document"]
    if (doc.get("file_size") or 0) > RS_MAX_DL:
        raise ValueError("حجم فایل بیش از ۲۰ مگابایت است (محدودیت تلگرام). فایل را با نام restore.sql (یا restore.sql.gz) روی سرور "
                         "کنار ربات آپلود کنید و از «روش دوم» استفاده کنید.")
    r = tg("getFile", file_id=doc["file_id"])
    path = (r.get("result") or {}).get("file_path")
    if not r.get("ok") or not path:
        raise ValueError(f"دریافت فایل از تلگرام ناموفق بود: {r.get('description', r.get('error_description', ''))}")
    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}"
    try:
        with urllib.request.urlopen(url, timeout=120) as resp:
            data = resp.read(RS_MAX_DL + 1)
    except Exception as e:
        raise ValueError(f"دانلود فایل ناموفق بود: {e}")
    return data, doc.get("file_name") or os.path.basename(path)


def _rs_offer(chat_id, admin_id, raw, fname, source):
    try:
        tmp, info = rs_prepare(raw, fname)
    except ValueError as e:
        _hsend(chat_id, f"❌ {_h(str(e))}")
        return
    except Exception as e:
        logging.exception("rs_prepare")
        _hsend(chat_id, f"❌ خطای غیرمنتظره در خواندن بکاپ: {_h(type(e).__name__)}: {_h(str(e))}")
        return
    set_state(admin_id, "adm_in", {"name": "rs_confirm", "tmp": tmp, "src": source, "back": "x"})
    _hsend(chat_id, _rs_summary(info, _q1("SELECT COUNT(*) FROM users"), _q1("SELECT COALESCE(SUM(tokens),0) FROM users")),
           _kb([_ab("✅ تأیید و بازیابی", "adm_p:x:rs_ok", SUCCESS)], [_ab("❌ انصراف", "adm_p:x:rs_no", DANGER)]))


def rs_receive(message):
    """ادمین فایل بکاپ را فرستاده (در حالت rs_wait)"""
    chat_id = message["chat"]["id"]
    admin_id = message["from"]["id"]
    _hsend(chat_id, "⏳ در حال دریافت و بررسی فایل بکاپ…")
    try:
        raw, fname = _rs_download(message)
    except ValueError as e:
        _hsend(chat_id, f"❌ {_h(str(e))}")
        return
    _rs_offer(chat_id, admin_id, raw, fname, "tg")


def _rs_safety_backup(admin_id):
    """بکاپ از وضعیت فعلی: روی دیسک (کنار دیتابیس) + ارسال برای ادمین. (نام فایل یا None) """
    try:
        name, data, _lines = rep_make_backup()
    except Exception:
        logging.exception("rs safety backup")
        return None
    pre = "pre_restore_" + name.replace("jfj_backup_", "")
    d = os.path.dirname(os.path.abspath(DB_PATH)) or "."
    saved = None
    try:
        with open(os.path.join(d, pre), "wb") as f:
            f.write(data)
        saved = pre
        olds = sorted(x for x in os.listdir(d) if x.startswith("pre_restore_"))
        for x in olds[:-3]:
            try:
                os.remove(os.path.join(d, x))
            except OSError:
                pass
    except OSError:
        logging.warning("pre-restore backup could not be written to disk")
    try:
        _send_doc(admin_id, None, pre, data, "🛡 بکاپ وضعیت قبل از بازیابی (برای برگشت)")
    except Exception:
        logging.exception("rs safety send")
    return saved or pre


def rs_apply(tmp, admin_id, chat_id, src="tg"):
    """جایگزینی کل دیتابیس با بکاپ بررسی‌شده، با backup-API خود SQLite (امن در حضور اتصال‌های باز و WAL)"""
    if not os.path.isfile(tmp):
        _hsend(chat_id, "❌ فایل موقت بکاپ پیدا نشد؛ دوباره فایل را بفرستید.")
        return False
    _hsend(chat_id, "⏳ در حال گرفتن بکاپ ایمنی و بازیابی… (چند ثانیه)")
    safe = _rs_safety_backup(admin_id)
    lock = getattr(GAMES, "_LK", None) if GAMES else None
    if lock:
        lock.acquire()
    try:
        s_ = sqlite3.connect(tmp)
        d_ = sqlite3.connect(DB_PATH, timeout=60)
        try:
            d_.execute("PRAGMA busy_timeout=60000")
            s_.backup(d_)
            d_.commit()
        finally:
            s_.close()
            d_.close()
    except Exception as e:
        logging.exception("rs_apply")
        _hsend(chat_id, f"❌ بازیابی ناموفق بود: {_h(type(e).__name__)}: {_h(str(e))}\n"
                        "دیتابیس قبلی دست‌نخورده است یا با بکاپ ایمنی قابل برگشت است.")
        return False
    finally:
        if lock:
            lock.release()
        try:
            os.remove(tmp)
        except OSError:
            pass
    problems = []
    for fn in (install_schema, migrate_schema, seed_products):
        try:
            fn()
        except Exception as e:
            logging.exception("rs post %s", fn.__name__)
            problems.append(fn.__name__)
    try:
        if GAMES:
            GAMES.init(GAMES.B)
        with get_db() as c:        # پنل‌های نیمه‌تمامِ بکاپ (بدون پول) بی‌معنی‌اند
            c.execute("DELETE FROM g_tables WHERE state IN ('menu','setup','stake_wait','pick','mode')")
    except Exception:
        logging.exception("rs games post")
    try:
        apply_settings()
    except Exception:
        logging.exception("rs apply_settings")
    set_state(admin_id, "admin_panel")
    users = _q1("SELECT COUNT(*) FROM users")
    toks = _q1("SELECT COALESCE(SUM(tokens),0) FROM users")
    if src not in ("tg", "") and os.path.isfile(src):
        try:
            os.replace(src, src + f".done_{int(time.time())}")       # فایل روی سرور دوباره به‌اشتباه استفاده نشود
        except OSError:
            pass
    _hsend(chat_id, "✅ <b>بازیابی کامل شد.</b>\n" + LINE + "\n"
                    f"👥 کاربران: <b>{_rp_n(users)}</b> • 🪙 مجموع شاهی: <b>{_t(toks)}</b>\n"
                    + (f"🛡 بکاپ قبل از بازیابی: <code>{_h(safe)}</code>\n" if safe else "⚠️ بکاپ ایمنی ساخته نشد.\n")
                    + ("⚠️ مرحله‌های: " + _h(", ".join(problems)) + " خطا داشت؛ لاگ را ببینید.\n" if problems else "")
                    + "نیازی به ری‌استارت ربات نیست.")
    return True


def rs_callback(act, args, admin_id, chat_id, mid, ack, show):
    if act == "rs_arm":
        set_state(admin_id, "adm_in", {"name": "rs_wait", "back": "x"})
        ack()
        _hsend(chat_id, "📤 <b>فایل بکاپ را بفرستید</b>\n\nفایل را به‌صورت <b>فایل (Document)</b> ارسال کنید "
                        "(.sql / .sql.gz / .db / .zip).",
               _kb([_ab("❌ انصراف", "adm_p:x:rs_no", DANGER)]))
        return True
    if act == "rs_no":
        _, d = get_state(admin_id)
        tmp = (d or {}).get("tmp")
        if tmp and os.path.isfile(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        set_state(admin_id, "admin_panel")
        ack("لغو شد.")
        t, k = render_restore()
        show(t, k)
        return True
    if act == "rs_ok":
        state, d = get_state(admin_id)
        if state != "adm_in" or (d or {}).get("name") != "rs_confirm":
            ack("این مرحله منقضی شده؛ دوباره فایل را بفرستید.", True)
            return True
        ack("در حال بازیابی…")
        set_state(admin_id, "admin_panel")
        show("♻️ در حال بازیابی…", None)
        rs_apply(d["tmp"], admin_id, chat_id, d.get("src", "tg"))
        return True
    if act == "rs_f":
        files = rs_server_files()
        try:
            fp = files[int(args[0])]
        except (IndexError, ValueError):
            ack("فایل پیدا نشد.", True)
            return True
        ack("در حال خواندن فایل…")
        try:
            with open(fp, "rb") as f:
                raw = f.read(RS_MAX_RAW + 1)
            if len(raw) > RS_MAX_RAW:
                raise ValueError("حجم فایل بیش از حد بزرگ است.")
        except (OSError, ValueError) as e:
            _hsend(chat_id, f"❌ {_h(str(e))}")
            return True
        _rs_offer(chat_id, admin_id, raw, os.path.basename(fp), fp)
        return True
    if act == "rs_bk":
        ack("بکاپ در حال ارسال…")
        threading.Thread(target=rep_send_backup, args=(chat_id,), daemon=True).start()
        return True
    return False


XPAGES["rs"] = render_restore


# ===================== اجرا =====================
def main():
    global BOT_USERNAME, BOT_ID
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    install_schema()
    migrate_schema()
    apply_settings()
    seed_products()

    try:
        me = tg("getMe", _timeout=20)
    except Exception as e:
        raise SystemExit(f"اتصال به تلگرام برقرار نشد: {e}")
    if not me.get("ok"):
        raise SystemExit(f"توکن اشتباه است یا خطای تلگرام: {me}")
    BOT_USERNAME = me["result"].get("username")
    BOT_ID = me["result"].get("id")
    logging.info("ربات روشن شد: @%s", BOT_USERNAME)

    tg("deleteWebhook")
    threading.Thread(target=invoice_watcher, daemon=True).start()
    threading.Thread(target=bc_worker, daemon=True).start()
    threading.Thread(target=request_sweeper, daemon=True).start()
    threading.Thread(target=rep_worker, daemon=True).start()
    threading.Thread(target=rep_scheduler, daemon=True).start()
    global GAMES
    try:
        import games as _games
        _games.init(_GlobalsProxy())
        _games.start()
        GAMES = _games
        logging.info("🃏 بخش بازی‌ها (games.py) فعال شد")
    except Exception:
        logging.exception("games.py لود نشد؛ ربات بدون بخش بازی ادامه می‌دهد")
    offset = 0
    pool = ThreadPoolExecutor(max_workers=8)
    fails = 0
    while True:
        try:
            res = tg(
                "getUpdates", offset=offset, timeout=30,
                allowed_updates=["message", "callback_query", "chat_member"],
            )
            if not res.get("ok"):
                # tg() استثنا پرتاب نمی‌کند؛ بدون این تأخیر، حلقه در خطای پروکسی
                # صدها بار در ثانیه تکرار می‌شد (سیل لاگ ۵۰۳)
                fails += 1
                if "Conflict" in str(res.get("error_description", "")):
                    logging.error("نمونه‌ی دیگری از ربات هم‌زمان در حال اجراست (409).")
                time.sleep(min(60, 2 * fails))
                continue
            fails = 0
            for upd in res.get("result", []):
                offset = upd["update_id"] + 1
                pool.submit(handle_update, upd)
        except Exception as e:
            logging.warning("خطای شبکه: %s | تلاش دوباره...", e)
            time.sleep(3)


if __name__ == "__main__":
    main()
