# -*- coding: utf-8 -*-
"""
لایه‌ی دیتابیس PostgreSQL ربات «جفج شاهنشاهی»  (جایگزین کامل SQLite)

رابط عمداً مثل قبل است تا کدهای ربات/بازی‌ها/مینی‌اپ کمترین تغییر را بخواهند:
    with get_db() as c:
        c.execute("SELECT ... WHERE id=?", (uid,)).fetchone()      # علامت ? همان‌طور که بود
    →  خروج موفق = commit ، خطا = rollback ، و در هر دو حالت اتصال به pool برمی‌گردد.

تنظیمات فقط از متغیرهای محیطی (هیچ رمزی در سورس نیست):
    DATABASE_URL          آدرس اتصال (Railway خودش می‌گذارد) — مثال: postgresql://user:pass@host:5432/dbname
    DB_SSLMODE            اختیاری: disable | require | verify-full ... (برای سرورهای خارجی/VPS)
    DB_POOL_MIN / DB_POOL_MAX   تعداد اتصال‌های pool (پیش‌فرض ۱ و ۲۰)
    DB_POOL_TIMEOUT       حداکثر انتظار برای گرفتن اتصال، ثانیه (۳۰)
    DB_LOCK_TIMEOUT_MS    حداکثر انتظار برای قفل ردیف‌ها (۱۰۰۰۰)  ≈ busy_timeout قبلی
    DB_STATEMENT_TIMEOUT_MS  سقف زمان هر دستور (۶۰۰۰۰)
    DB_SCHEMA             اختیاری: اسکیمای PostgreSQL (پیش‌فرض public) — برای تست‌ها
"""
import logging
import os
import re
import threading
import time
from collections import deque
from functools import lru_cache

import psycopg2
import psycopg2.extensions as _ext

Error = psycopg2.Error
IntegrityError = psycopg2.IntegrityError
OperationalError = psycopg2.OperationalError
ProgrammingError = psycopg2.ProgrammingError

_LOG = logging.getLogger("jfj.db")


# ----------------------------------------------------------------- پیکربندی
def _env_int(name, default):
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def database_url():
    for k in ("DATABASE_URL", "DATABASE_PRIVATE_URL", "POSTGRES_URL", "POSTGRESQL_URL"):
        v = (os.environ.get(k) or "").strip()
        if v:
            return v
    host = os.environ.get("PGHOST")
    if host:
        user = os.environ.get("PGUSER", "postgres")
        pw = os.environ.get("PGPASSWORD", "")
        from urllib.parse import quote
        auth = quote(user) + (":" + quote(pw) if pw else "")
        return f"postgresql://{auth}@{host}:{os.environ.get('PGPORT', '5432')}/{os.environ.get('PGDATABASE', user)}"
    return ""


_cfg = {"url": None, "schema": None}


def configure(url=None, schema=None):
    """(بیشتر برای تست) تنظیم دستیِ آدرس/اسکیما؛ pool قبلی بسته می‌شود"""
    _cfg["url"] = url
    _cfg["schema"] = schema
    _pool.reset()


def _safe(msg):
    """رمز/آدرس اتصال هرگز در لاگ و پیام خطا نمی‌آید"""
    s = str(msg)
    url = _cfg["url"] or database_url()
    if url:
        s = s.replace(url, "<DATABASE_URL>")
        m = re.match(r"^\w+://([^:@/]+):([^@]+)@", url)
        if m and m.group(2):
            s = s.replace(m.group(2), "***")
    return re.sub(r"(://[^:@/\s]+:)[^@\s]+@", r"\1***@", s)


# ----------------------------------------------------------------- نوع‌ها
def _num(v, cur=None):
    """NUMERIC (مثلاً خروجی SUM) → int یا float؛ مثل رفتار قبلی SQLite"""
    if v is None:
        return None
    return float(v) if "." in v or "e" in v.lower() else int(v)


try:
    _ext.register_type(_ext.new_type((1700,), "JFJ_NUM", _num))
except Exception:      # pragma: no cover
    _LOG.warning("numeric typecaster not registered")


class Row(tuple):
    """مثل sqlite3.Row: هم با اندیس هم با نام ستون؛ unpack و dict() هم کار می‌کند"""

    def __new__(cls, vals, names):
        o = tuple.__new__(cls, vals)
        o._names = names
        return o

    def __getitem__(self, i):
        if isinstance(i, str):
            return tuple.__getitem__(self, self._names[i])
        return tuple.__getitem__(self, i)

    def keys(self):
        return list(self._names)

    def get(self, k, d=None):
        return self[k] if k in self._names else d


class Cursor:
    """نتیجه‌ی بافرشده؛ بعد از بستن/برگشت اتصال هم قابل خواندن است (rowcount و fetch*)"""

    def __init__(self, rows, description, rowcount):
        self._rows = rows
        self.description = description
        self.rowcount = rowcount
        self._i = 0

    def fetchone(self):
        if self._i >= len(self._rows):
            return None
        r = self._rows[self._i]
        self._i += 1
        return r

    def fetchall(self):
        r = self._rows[self._i:]
        self._i = len(self._rows)
        return r

    def fetchmany(self, n=1):
        r = self._rows[self._i:self._i + n]
        self._i += len(r)
        return r

    def __iter__(self):
        while True:
            r = self.fetchone()
            if r is None:
                return
            yield r


# ----------------------------------------------------------------- تبدیل SQL
_TS_FMT = "'YYYY-MM-DD HH24:MI:SS'"
NOW_SQL = f"to_char(now() AT TIME ZONE 'UTC', {_TS_FMT})"
_RE_DT = re.compile(r"datetime\(\s*'now'\s*(?:,\s*'([+-]?\d+)\s*(second|minute|hour|day|month)s?'\s*)?\)", re.I)
_RE_DDL = re.compile(r"^\s*(CREATE\s+TABLE|ALTER\s+TABLE)\b", re.I)


def _dt_sub(m):
    if not m.group(1):
        return NOW_SQL
    n = int(m.group(1))
    return f"to_char((now() AT TIME ZONE 'UTC') + interval '{n} {m.group(2).lower()}', {_TS_FMT})"


def _ddl(sql):
    """CREATE/ALTER TABLE: نوع‌های SQLite → PostgreSQL (INTEGER=۳۲بیت در PG است؛ آیدی‌های تلگرام ۶۴بیتی‌اند)"""
    sql = re.sub(r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", "BIGSERIAL PRIMARY KEY", sql, flags=re.I)
    sql = re.sub(r"\btokens\s+INTEGER\b", "tokens DOUBLE PRECISION", sql, flags=re.I)     # شاهی کسری هم می‌شود (بازی‌ها)
    sql = re.sub(r"\bINTEGER\b", "BIGINT", sql, flags=re.I)
    sql = re.sub(r"\bREAL\b", "DOUBLE PRECISION", sql, flags=re.I)
    return sql


@lru_cache(maxsize=4096)
def translate(sql, with_params=True):
    """? → %s (بیرون از رشته‌های متنی) ، CURRENT_TIMESTAMP و datetime('now',...) → معادل UTC متنی PostgreSQL"""
    if _RE_DDL.match(sql):
        sql = _ddl(sql)
    sql = _RE_DT.sub(_dt_sub, sql)
    sql = re.sub(r"\bCURRENT_TIMESTAMP\b", "(" + NOW_SQL + ")", sql)
    out, i, n, q = [], 0, len(sql), False
    while i < n:
        ch = sql[i]
        if ch == "'":
            if q and i + 1 < n and sql[i + 1] == "'":      # '' داخل رشته
                out.append("''")
                i += 2
                continue
            q = not q
            out.append(ch)
        elif ch == "%" and with_params:
            out.append("%%")
        elif ch == "?" and not q:
            out.append("%s")
        else:
            out.append(ch)
        i += 1
    return "".join(out)


# ----------------------------------------------------------------- pool
class _Pool:
    def __init__(self):
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._idle = deque()          # (conn, last_used)
        self._out = 0
        self._gen = 0

    # --- پارامترها
    @staticmethod
    def _max():
        return max(2, _env_int("DB_POOL_MAX", 20))

    def reset(self):
        with self._lock:
            self._gen += 1
            idle, self._idle = list(self._idle), deque()
        for c, _ in idle:
            _quiet_close(c)

    def _connect(self):
        url = _cfg["url"] or database_url()
        if not url:
            raise RuntimeError("DATABASE_URL تنظیم نشده است (آدرس اتصال PostgreSQL را در متغیرهای محیطی بگذارید).")
        opts = [f"-c lock_timeout={_env_int('DB_LOCK_TIMEOUT_MS', 10000)}",
                f"-c statement_timeout={_env_int('DB_STATEMENT_TIMEOUT_MS', 60000)}",
                "-c idle_in_transaction_session_timeout=300000",
                "-c TimeZone=UTC"]
        schema = _cfg["schema"] or os.environ.get("DB_SCHEMA")
        if schema:
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema):
                raise RuntimeError("DB_SCHEMA نامعتبر است")
            opts.append(f"-c search_path={schema},public")
        kw = {"options": " ".join(opts), "connect_timeout": _env_int("DB_CONNECT_TIMEOUT", 10),
              "keepalives": 1, "keepalives_idle": 30, "keepalives_interval": 10, "keepalives_count": 3,
              "application_name": "jfj-bot"}
        ssl = os.environ.get("DB_SSLMODE")
        if ssl:
            kw["sslmode"] = ssl
        try:
            return psycopg2.connect(url, **kw)
        except psycopg2.Error as e:
            raise OperationalError("اتصال به PostgreSQL ناموفق بود: " + _safe(e)) from None

    def acquire(self):
        deadline = time.time() + _env_int("DB_POOL_TIMEOUT", 30)
        with self._cv:
            while True:
                gen = self._gen
                if self._idle:
                    conn, last = self._idle.pop()
                    self._out += 1
                    break
                if self._out < self._max():
                    conn, last = None, 0
                    self._out += 1
                    break
                left = deadline - time.time()
                if left <= 0:
                    raise OperationalError("pool دیتابیس پر است (DB_POOL_MAX را بیشتر کنید یا تراکنش‌های طولانی را بررسی کنید)")
                self._cv.wait(left)
        try:
            if conn is not None and (conn.closed or time.time() - last > 25):
                if conn.closed:
                    conn = None
                else:                                   # اتصال مدتی بیکار بوده (مثلاً قطع از سمت Railway)
                    try:
                        cur = conn.cursor()
                        cur.execute("SELECT 1")
                        conn.rollback()
                    except Exception:
                        _quiet_close(conn)
                        conn = None
            if conn is None:
                conn = self._connect()
                conn.autocommit = False
        except BaseException:
            with self._cv:
                self._out -= 1
                self._cv.notify()
            raise
        return conn, gen

    def release(self, conn, gen, broken=False):
        ok = not broken and not conn.closed and gen == self._gen
        if ok:
            try:
                conn.rollback()                           # هیچ تراکنش نیمه‌کاره‌ای به pool برنمی‌گردد
            except Exception:
                ok = False
        with self._cv:
            self._out -= 1
            if ok and len(self._idle) < self._max():
                self._idle.append((conn, time.time()))
                conn = None
            self._cv.notify()
        if conn is not None:
            _quiet_close(conn)


def _quiet_close(c):
    try:
        c.close()
    except Exception:
        pass


_pool = _Pool()


# ----------------------------------------------------------------- اتصال
class Conn:
    """هم‌رابط با sqlite3.Connection برای کدهای قبلی (execute/executemany/commit/rollback/close/with)"""

    def __init__(self):
        self._raw, self._gen = _pool.acquire()
        self._broken = False
        self._done = False
        self.row_factory = None

    # --- اجرا
    def _check(self):
        if self._done:
            raise ProgrammingError("اتصال دیتابیس قبلاً بسته/برگردانده شده است")

    def execute(self, sql, params=()):
        self._check()
        params = tuple(params) if params is not None else ()
        q = translate(sql, bool(params))
        cur = self._raw.cursor()
        try:
            cur.execute(q, params if params else None)
        except psycopg2.OperationalError:
            if self._raw.closed:
                self._broken = True
            raise
        except psycopg2.InterfaceError:
            self._broken = True
            raise
        desc = cur.description
        if desc is None:
            return Cursor([], None, cur.rowcount)
        raw = cur.fetchall()
        rf = self.row_factory
        if rf is None:
            names = {d[0]: i for i, d in reversed(list(enumerate(desc)))}
            rows = [Row(r, names) for r in raw]
        else:
            tmp = Cursor([], desc, len(raw))
            rows = [rf(tmp, r) for r in raw]
        return Cursor(rows, desc, len(raw))

    def executemany(self, sql, seq):
        self._check()
        q = translate(sql, True)
        cur = self._raw.cursor()
        n = 0
        for p in seq:
            cur.execute(q, tuple(p))
            n += max(cur.rowcount, 0)
        return Cursor([], None, n)

    def insert_many(self, table, cols, rows, chunk=500, conflict=""):
        """درج دسته‌ای (چند ردیف در هر دستور) برای مهاجرت/بازیابی؛ conflict مثلاً 'ON CONFLICT DO NOTHING'"""
        self._check()
        if not rows:
            return 0
        qc = ",".join('"%s"' % c for c in cols)
        one = "(" + ",".join("?" * len(cols)) + ")"
        n = 0
        for i in range(0, len(rows), chunk):
            part = rows[i:i + chunk]
            flat = [v for r in part for v in r]
            cur = self.execute(f'INSERT INTO "{table}" ({qc}) VALUES ' + ",".join([one] * len(part)) + (" " + conflict if conflict else ""), flat)
            n += max(cur.rowcount, 0)
        return n

    def lock(self, key):
        """قفل مشورتی در سطح تراکنش (معادل قفل نوشتنِ BEGIN IMMEDIATE) ؛ با commit/rollback آزاد می‌شود"""
        self.execute("SELECT pg_advisory_xact_lock(?)", (int(key),))

    # --- تراکنش
    def commit(self):
        self._check()
        try:
            self._raw.commit()
        except psycopg2.Error:
            if self._raw.closed:
                self._broken = True
            raise

    def rollback(self):
        if self._done:
            return
        try:
            self._raw.rollback()
        except psycopg2.Error:
            self._broken = True

    def close(self):
        if self._done:
            return
        self._done = True
        _pool.release(self._raw, self._gen, self._broken)

    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        if self._done:
            return False
        try:
            if et is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()
        return False

    def __del__(self):          # اگر کسی close نکرد، اتصال از pool گم نشود
        try:
            if not self._done:
                self.close()
        except Exception:
            pass


def get_db():
    return Conn()


# ----------------------------------------------------------------- ابزارهای اسکیما
def table_exists(c, name):
    return c.execute("SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() AND table_name=?",
                     (name,)).fetchone() is not None


def column_exists(c, table, col):
    return c.execute("SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() "
                     "AND table_name=? AND column_name=?", (table, col)).fetchone() is not None


def table_columns(c, table):
    return [r[0] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() "
                                    "AND table_name=? ORDER BY ordinal_position", (table,)).fetchall()]


def add_column(c, table, col, ddl):
    """ستون را فقط اگر نباشد می‌سازد؛ True = همین الان ساخته شد (برای backfill یک‌باره). بدون خطا در تراکنش."""
    if column_exists(c, table, col):
        return False
    c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
    return True


def all_tables(c):
    return [r[0] for r in c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() "
                                    "AND table_type='BASE TABLE' ORDER BY table_name").fetchall()]


def ensure_schema():
    """اگر DB_SCHEMA تنظیم شده باشد آن را می‌سازد (پیش‌فرض public نیازی ندارد)"""
    schema = _cfg["schema"] or os.environ.get("DB_SCHEMA")
    if not schema:
        return
    saved = _cfg["schema"], os.environ.pop("DB_SCHEMA", None)
    _cfg["schema"] = None
    _pool.reset()
    try:
        with get_db() as c:
            c.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    finally:
        _cfg["schema"] = saved[0]
        if saved[1]:
            os.environ["DB_SCHEMA"] = saved[1]
        _pool.reset()


def reset_sequence(c, table, col="id"):
    """بعد از درج رکورد با id دستی (مهاجرت/بازیابی) شمارنده را بعد از بیشینه می‌گذارد"""
    row = c.execute("SELECT pg_get_serial_sequence(?, ?)", (table, col)).fetchone()
    seq = row[0] if row else None
    if seq:
        c.execute(f"SELECT setval('{seq}', COALESCE((SELECT MAX({col}) FROM {table}), 0) + 1, false)")


def check_connection():
    """(برای شروع برنامه) اتصال را امتحان می‌کند و نسخه‌ی سرور را برمی‌گرداند"""
    with get_db() as c:
        return c.execute("SHOW server_version").fetchone()[0]


SCHEMA_LOCK_KEY = 7461000


class schema_lock:
    """قفل مشورتیِ سراسری هنگام ساخت/مهاجرت جدول‌ها: ربات، مینی‌اپ و رپلیکاهای هم‌زمان با هم DDL اجرا نمی‌کنند
    (CREATE TABLE IF NOT EXISTS هم‌زمان در PostgreSQL می‌تواند خطای تکراری بدهد). با اتصال جداگانه؛ تودرتو استفاده نشود."""

    def __enter__(self):
        self._c = get_db()
        self._c.execute("SELECT pg_advisory_lock(?)", (SCHEMA_LOCK_KEY,))
        return self

    def __exit__(self, *a):
        try:
            self._c.execute("SELECT pg_advisory_unlock(?)", (SCHEMA_LOCK_KEY,))
            self._c.commit()
        finally:
            self._c.close()
        return False
