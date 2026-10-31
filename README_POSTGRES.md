# مهاجرت دیتابیس ربات «جفج شاهنشاهی» از SQLite به PostgreSQL

از این نسخه به بعد **تمام داده‌های ربات و مینی‌اپ فقط در PostgreSQL** ذخیره می‌شود. SQLite در مسیر اجرای ربات استفاده نمی‌شود
(فقط ابزار انتقال `migrate_sqlite_to_pg.py` برای خواندن فایل قدیمی از آن استفاده می‌کند).

## فایل‌ها
| فایل | کار |
|---|---|
| `db.py` | لایه‌ی اتصال: pool، تبدیل `?` به پارامتر PostgreSQL، commit/rollback خودکار، قفل‌ها، ابزار اسکیما |
| `bot_test.py` / `games.py` / `miniapp.py` | همان منطق قبلی؛ فقط SQL و مدیریت اتصال سازگار شد |
| `migrate_sqlite_to_pg.py` | انتقال امن و قابل‌تکرار داده از SQLite به PostgreSQL + تطبیق |
| `start.py` | اجرای ربات + مینی‌اپ؛ انتقال خودکار با `MIGRATE_SQLITE_FROM` |
| `.env.example` | نمونه‌ی متغیرهای محیطی |
| `tests/` | تست‌ها (`python3 tests/run_all.py`) |

## متغیرهای محیطی
| متغیر | توضیح |
|---|---|
| `DATABASE_URL` | **الزامی.** `postgresql://USER:PASS@HOST:5432/DB` (رمز هرگز در سورس نیست و در لاگ/خطاها چاپ نمی‌شود) |
| `DB_SSLMODE` | اختیاری: `require` برای سرورهای خارجی که SSL می‌خواهند |
| `DB_POOL_MAX` | حداکثر اتصال هم‌زمان (پیش‌فرض ۲۰؛ کمتر از `max_connections` سرور) |
| `DB_POOL_TIMEOUT` | حداکثر انتظار برای گرفتن اتصال، ثانیه (۳۰) |
| `DB_LOCK_TIMEOUT_MS` | انتظار برای قفل ردیف‌ها (۱۰۰۰۰) |
| `DB_STATEMENT_TIMEOUT_MS` | سقف زمان هر دستور (۶۰۰۰۰) |
| `DB_SCHEMA` | اسکیمای دلخواه (پیش‌فرض `public`) |
| `BACKUP_DIR` | پوشه‌ی فایل‌های موقت بازیابی و `restore.json` |
| `MIGRATE_SQLITE_FROM` | مسیر فایل قدیمی (مثلاً `/data/bot.db`) برای انتقال خودکارِ یک‌باره موقع روشن شدن |
| `MIGRATE_SQLITE_FORCE` | `1` = انتقال خودکار دوباره اجرا شود |

## راه‌اندازی روی Railway (بدون نیاز به کامپیوتر)
1. در پروژه‌ی Railway: **New → Database → Add PostgreSQL**.
2. روی سرویس **ربات** → Variables → یک متغیر جدید:
   `DATABASE_URL` = `${{Postgres.DATABASE_URL}}` (اگر سرویس‌ها در یک پروژه‌اند؛ آدرس خصوصی `DATABASE_PRIVATE_URL` سریع‌تر و بدون هزینه‌ی ترافیک است).
3. **اگر داده‌ی قبلی (SQLite) دارید:** همان Volume قبلی را روی سرویس نگه دارید و متغیر
   `MIGRATE_SQLITE_FROM` = `/data/bot.db` را اضافه کنید (مسیر همان `DB_PATH` قبلی).
   موقع روشن شدن، ربات خودش انتقال را انجام می‌دهد، شمارش و checksum همه‌ی جدول‌ها را تطبیق می‌دهد و
   فقط در صورت موفقیت روشن می‌شود. فایل SQLite و یک نسخه‌ی `.premigrate_*.bak` کنارش **باقی می‌مانند**.
4. Deploy. در لاگ باید ببینید: `🚚 شروع انتقال…` سپس جدول تطبیق (همه ✅) و `✅ انتقال SQLite انجام و تأیید شد`.
5. بعد از چند روز کارکرد درست می‌توانید `MIGRATE_SQLITE_FROM` و Volume قدیمی را بردارید (حذف فایل `bot.db` را دستی و فقط بعد از اطمینان انجام دهید).

> برای اجرای دستی روی سرور/VPS:
> ```bash
> pip install -r requirements.txt
> export DATABASE_URL='postgresql://user:pass@host:5432/dbname'
> python3 migrate_sqlite_to_pg.py --sqlite /path/to/bot.db --dry-run   # بررسی
> python3 migrate_sqlite_to_pg.py --sqlite /path/to/bot.db             # انتقال
> python3 migrate_sqlite_to_pg.py --sqlite /path/to/bot.db --verify-only
> ```
> حالت‌ها: `--resume` (اجرای مجدد بی‌خطر؛ ردیف‌های موجود تکرار نمی‌شوند) ، `--replace` (جایگزینی کامل؛ قبلش بکاپ JSON از PostgreSQL گرفته می‌شود) ، `--allow-round` (گرد کردن عدد اعشاری در ستون صحیح؛ پیش‌فرض خطا).

## راه‌اندازی روی هاست / VPS
1. PostgreSQL نصب کنید و دیتابیس/کاربر بسازید:
   ```sql
   CREATE USER jfj WITH PASSWORD '...';
   CREATE DATABASE jfj OWNER jfj ENCODING 'UTF8';
   ```
2. `DATABASE_URL=postgresql://jfj:...@127.0.0.1:5432/jfj` (و در صورت سرور خارجی `DB_SSLMODE=require`).
3. `pip install -r requirements.txt` و `python3 start.py`. جدول‌ها در اولین اجرا خودکار ساخته می‌شوند.
4. نیازی به `max_connections` بالا نیست؛ `DB_POOL_MAX` را متناسب با سرور بگذارید (اگر چند نسخه‌ی ربات هم‌زمان اجرا می‌شود، مجموع‌شان از `max_connections` کمتر باشد).

## هر چیزی که عوض شد
* **نوع داده‌ها:** `INTEGER` در PostgreSQL فقط ۳۲ بیت است ولی آیدی تلگرام و چت‌ها (مثل `-1001234567890`) بزرگ‌ترند؛ همه‌ی ستون‌های صحیح `BIGINT` و ستون‌های اعشاری `DOUBLE PRECISION` ساخته می‌شوند. **`users.tokens` اعشاری (DOUBLE) است** چون بازی‌ها شاهی کسری می‌دهند.
* **زمان‌ها** مثل قبل رشته‌ی UTC با قالب `YYYY-MM-DD HH:MM:SS` هستند (`CURRENT_TIMESTAMP` و `datetime('now','-3 day')` در `db.py` به معادل UTC تبدیل می‌شوند) تا داده‌ی قدیمی و مقایسه‌های متنی بدون تغییر کار کنند.
* `INSERT OR IGNORE` → `ON CONFLICT DO NOTHING` ؛ `INSERT OR REPLACE` → `ON CONFLICT (...) DO UPDATE` ؛ `lastrowid` → `INSERT ... RETURNING id` ؛ `AUTOINCREMENT` → `BIGSERIAL`.
* **`rowid`:** PostgreSQL ندارد؛ جدول‌های `requests`, `joins`, `service_orders`, `g_players` ستون `rid` (ترتیب درج) گرفتند و مهاجرت مقدار قدیمی rowid را در آن می‌گذارد.
* **هم‌زمانی:** `BEGIN IMMEDIATE` بازی‌ها → قفل مشورتی PostgreSQL (`pg_advisory_xact_lock`) با همان معنا (در چند پردازه هم امن). کسر/افزایش شاهی با `UPDATE ... WHERE tokens >= ?` اتمیک است؛ انتقال بین کاربران با `FOR UPDATE` به ترتیب ثابت id (بدون deadlock). ساخت/مهاجرت جدول‌ها با قفل مشورتی جداگانه (ربات و مینی‌اپ و چند رپلیکا هم‌زمان DDL اجرا نمی‌کنند).
* **pool اتصال:** سقف `DB_POOL_MAX` ، بررسی سلامت اتصال‌های بیکار، دور انداختن اتصال قطع‌شده، `lock_timeout` ، `statement_timeout` و `idle_in_transaction_session_timeout`.
* **بکاپ و بازیابی ادمین:** حالا فایل **JSON** (`jfj_backup_*.json[.gz]`) است (همه‌ی جدول‌ها از یک تصویر یکپارچه). بازیابی در **یک تراکنش** انجام می‌شود (یا کامل یا هیچ) و قبلش بکاپ ایمنی ارسال می‌شود. بکاپ‌های قدیمی `.db/.sql` با `migrate_sqlite_to_pg.py` منتقل می‌شوند، نه با دکمه‌ی بازیابی.
* جدول‌هایی که قبلاً هنگام اولین استفاده ساخته می‌شدند (`pay_ctx`, `rep_msgs`, `rep_daily`) حالا یک‌بار در شروع ساخته می‌شوند.

## تست
```bash
# PostgreSQL تست (هر تست اسکیمای جداگانه‌ی خودش را می‌سازد)
export TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5432/jfj_test
pip install psycopg2-binary
python3 tests/run_all.py
```
* `tests/sqlcheck.py` همه‌ی SQLهای سورس را با `PREPARE` روی PostgreSQL واقعی اعتبارسنجی می‌کند.
* `tests/t_pg.py` نوع‌ها، تراکنش، هم‌زمانی، pool و قطع اتصال؛ `tests/t_mig.py` ابزار انتقال و ربات روی داده‌ی منتقل‌شده.
* اگر `psycopg2` نصب نباشد، تست‌ها خودکار از درایور آزمایشی `tests/shim` استفاده می‌کنند (فقط برای تست؛ در اجرای واقعی استفاده نمی‌شود).

## نکته‌ها / محدودیت‌ها
* دستورهای پویای (f-string) را نمی‌شود ایستا اعتبارسنجی کرد؛ همه‌ی آن‌ها با تست‌های اجرایی پوشش داده شده‌اند.
* PostgreSQL نسخه‌ی ۱۳ به بالا پیشنهاد می‌شود (روی ۱۶ تست شده).
