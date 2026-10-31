"""راه‌اندازی تست‌ها روی PostgreSQL واقعی. هر تست اسکیمای جداگانه‌ی خودش را دارد (t_<نام فایل>).
متغیر TEST_DATABASE_URL (پیش‌فرض: postgresql://postgres@127.0.0.1:5432/jfj_test).
اگر psycopg2 واقعی نصب باشد همان استفاده می‌شود؛ وگرنه درایور آزمایشی tests/shim (فقط برای سندباکس بدون pip)."""
import os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
try:
    import psycopg2  # noqa
    DRIVER = "psycopg2 " + getattr(psycopg2, "__version__", "")
except ImportError:
    sys.path.insert(0, os.path.join(HERE, "shim"))
    import psycopg2  # noqa
    DRIVER = "shim"
URL = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres@127.0.0.1:5432/jfj_test")


def schema_name(name=None):
    name = name or os.path.splitext(os.path.basename(sys.argv[0] or "t"))[0]
    return "t_" + re.sub(r"[^A-Za-z0-9_]", "_", name).lower()


def fresh(name=None):
    """اسکیمای تمیز می‌سازد و db را روی آن تنظیم می‌کند"""
    import db
    sch = schema_name(name)
    db.configure(URL, None)
    with db.get_db() as c:
        c.execute(f"DROP SCHEMA IF EXISTS {sch} CASCADE")
        c.execute(f"CREATE SCHEMA {sch}")
    db.configure(URL, sch)
    return sch
