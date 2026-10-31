#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
انتقال امنِ دیتابیس SQLite قدیمیِ ربات «جفج شاهنشاهی» به PostgreSQL

  python3 migrate_sqlite_to_pg.py --sqlite /data/bot.db                 # انتقال (فقط اگر PostgreSQL خالی باشد)
  python3 migrate_sqlite_to_pg.py --sqlite /data/bot.db --dry-run       # فقط بررسی؛ هیچ‌چیز نوشته نمی‌شود
  python3 migrate_sqlite_to_pg.py --sqlite /data/bot.db --resume        # اجرای مجدد/ادامه: ردیف‌های موجود دوباره درج نمی‌شوند
  python3 migrate_sqlite_to_pg.py --sqlite /data/bot.db --replace       # جایگزینی کامل داده‌های PostgreSQL (قبلش بکاپ JSON)
  python3 migrate_sqlite_to_pg.py --sqlite /data/bot.db --verify-only   # فقط تطبیق شمارش و checksum

ضمانت‌ها:
  • فایل SQLite فقط خوانده می‌شود (mode=ro) و هرگز حذف/تغییر نمی‌کند؛ قبل از شروع یک نسخه‌ی پشتیبان کنارش ساخته می‌شود.
  • کل انتقال در «یک تراکنش» PostgreSQL است: خطا = rollback کامل و هیچ داده‌ای نیمه‌کاره نمی‌ماند.
  • بعد از انتقال، تعداد ردیف‌ها و checksum همه‌ی ستون‌های هر جدول بین دو دیتابیس تطبیق داده می‌شود.
  • آدرس اتصال فقط از DATABASE_URL (یا --database-url) خوانده می‌شود و در خروجی چاپ نمی‌شود.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# جدول‌هایی که ترتیب درج (rowid در SQLite) در PostgreSQL به ستون rid منتقل می‌شود
ROWID_TABLES = {"requests", "joins", "service_orders", "g_players"}
INT_TYPES = {"bigint", "integer", "smallint"}
FLOAT_TYPES = {"double precision", "real", "numeric"}


def log(*a):
    print(*a, flush=True)


def die(msg, code=2):
    print("❌ " + msg, file=sys.stderr, flush=True)
    sys.exit(code)


def parse_args():
    ap = argparse.ArgumentParser(description="SQLite → PostgreSQL migration for JFJ bot")
    ap.add_argument("--sqlite", required=True, help="مسیر فایل bot.db قدیمی")
    ap.add_argument("--database-url", help="پیش‌فرض: متغیر محیطی DATABASE_URL")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="فقط بررسی و گزارش؛ بدون نوشتن")
    g.add_argument("--resume", action="store_true", help="ردیف‌های موجود را رد کن (اجرای مجدد بی‌خطر)")
    g.add_argument("--replace", action="store_true", help="داده‌های فعلیِ PostgreSQL را پاک و جایگزین کن (بکاپ JSON ساخته می‌شود)")
    g.add_argument("--verify-only", action="store_true", help="فقط تطبیق شمارش و checksum")
    ap.add_argument("--backup-dir", help="پوشه‌ی بکاپ‌ها (پیش‌فرض: کنار فایل SQLite)")
    ap.add_argument("--allow-round", action="store_true",
                    help="اگر عددِ اعشاری در ستون صحیح بود گرد شود (پیش‌فرض: خطا و توقف)")
    return ap.parse_args()


# ------------------------------------------------------------------ تبدیل مقدار
class Coerce:
    def __init__(self, allow_round):
        self.allow_round = allow_round
        self.rounded = {}
        self.warns = []

    def conv(self, tbl, col, typ, v):
        if v is None:
            return None
        if typ in INT_TYPES:
            if isinstance(v, bool):
                return int(v)
            if isinstance(v, int):
                return v
            if isinstance(v, float):
                if v == int(v):
                    return int(v)
                if self.allow_round:
                    self.rounded[(tbl, col)] = self.rounded.get((tbl, col), 0) + 1
                    return int(round(v))
                raise ValueError(f"{tbl}.{col}: مقدار اعشاری {v!r} در ستون صحیح")
            if isinstance(v, str):
                try:
                    return int(v.strip())
                except ValueError:
                    raise ValueError(f"{tbl}.{col}: متن {v!r} در ستون صحیح")
            raise ValueError(f"{tbl}.{col}: نوع {type(v).__name__} در ستون صحیح")
        if typ in FLOAT_TYPES:
            if isinstance(v, (int, float)):
                return float(v)
            try:
                return float(v)
            except (TypeError, ValueError):
                raise ValueError(f"{tbl}.{col}: مقدار {v!r} در ستون عددی")
        # text
        if isinstance(v, bytes):
            return v.decode("utf-8", "replace")
        if isinstance(v, str):
            return v.replace("\x00", "") if "\x00" in v else v
        return str(v)


def norm(v):
    """نمایش یکتا برای checksum (هر دو طرف با همین تابع)"""
    if v is None:
        return "\x00N"
    if isinstance(v, bool):
        return str(int(v))
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(float(v))
    return str(v)


def fingerprint(rows):
    """checksum مستقل از ترتیب: مجموع md5 هر ردیف (mod 2^128)"""
    acc = 0
    for r in rows:
        h = hashlib.md5("\x1f".join(norm(x) for x in r).encode("utf-8", "replace")).digest()
        acc = (acc + int.from_bytes(h, "big")) % (1 << 128)
    return "%032x" % acc


# ------------------------------------------------------------------ اصلی
def main():
    a = parse_args()
    if a.database_url:
        os.environ["DATABASE_URL"] = a.database_url
    if not os.path.isfile(a.sqlite):
        die(f"فایل SQLite پیدا نشد: {a.sqlite}")
    import db as _db
    if not _db.database_url():
        die("DATABASE_URL تنظیم نشده است (آدرس PostgreSQL را در متغیر محیطی DATABASE_URL بگذارید).")
    try:
        ver = _db.check_connection()
    except Exception as e:
        die("اتصال به PostgreSQL ناموفق بود: " + _db._safe(e))
    log(f"🐘 PostgreSQL {ver} — اتصال برقرار است")

    backup_dir = a.backup_dir or os.path.dirname(os.path.abspath(a.sqlite))
    os.makedirs(backup_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")

    # --- ۱) خواندن SQLite (فقط‌خواندنی) + نسخه‌ی پشتیبان
    src = sqlite3.connect(f"file:{os.path.abspath(a.sqlite)}?mode=ro", uri=True)
    chk = src.execute("PRAGMA quick_check").fetchone()
    if not chk or chk[0] != "ok":
        die("فایل SQLite آسیب دیده است (quick_check ناموفق)؛ ابتدا آن را تعمیر/بازیابی کنید.")
    if not (a.dry_run or a.verify_only):
        bak = os.path.join(backup_dir, f"{os.path.basename(a.sqlite)}.premigrate_{stamp}.bak")
        dst = sqlite3.connect(bak)
        src.backup(dst)
        dst.close()
        log(f"💾 نسخه‌ی پشتیبان SQLite: {bak}")
    s_tables = [r[0] for r in src.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    log(f"🗂 جدول‌های SQLite: {len(s_tables)}")

    # --- ۲) ساخت ساختار در PostgreSQL با همان کدِ خودِ ربات (ساختار دقیقاً یکی است)
    if not a.dry_run and not a.verify_only:
        import bot_test as bot
        import games
        import miniapp
        with _db.schema_lock():
            bot.install_schema()
            bot.migrate_schema()
            miniapp._mini_tables()
        games.init(bot)
        log("🏗 ساختار جدول‌ها در PostgreSQL آماده است")
    elif a.dry_run:
        log("ℹ️ dry-run: ساختار ساخته نمی‌شود؛ فقط داده‌ی SQLite بررسی می‌شود")

    co = Coerce(a.allow_round)
    report, problems = [], []

    with _db.get_db() as pg:
        pg_tables = set(_db.all_tables(pg)) if not a.dry_run or True else set()
        types = {}
        for t in pg_tables:
            types[t] = {r[0]: r[1] for r in pg.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema=current_schema() AND table_name=?", (t,)).fetchall()}

        # --- حالت فقط تطبیق/dry-run ریشه
        plan = []
        for t in s_tables:
            scols = [r[1] for r in src.execute(f'PRAGMA table_info("{t}")')]
            if t not in pg_tables:
                if a.dry_run:
                    # ساختار هنوز ساخته نشده: نوع‌ها را از اعلان SQLite حدس می‌زنیم تا ناسازگاری‌ها همین حالا پیدا شوند
                    types[t] = {}
                    for _cid, cname, ctype, *_r in src.execute(f'PRAGMA table_info("{t}")'):
                        ct = (ctype or "").upper()
                        types[t][cname] = ("double precision" if (ct == "REAL" or (t == "users" and cname == "tokens"))
                                           else "bigint" if "INT" in ct else "text")
                    plan.append((t, scols, scols, False))
                    continue
                problems.append(f"جدول {t} در PostgreSQL وجود ندارد (ساختار نسخه‌ی جدید ربات آن را ندارد) — رد شد")
                continue
            tcols = [c for c in scols if c in types[t]]
            dropped = [c for c in scols if c not in types[t]]
            if dropped:
                problems.append(f"{t}: ستون‌های نادیده‌گرفته‌شده: {', '.join(dropped)}")
            plan.append((t, scols, tcols, False))

        if a.replace and not a.dry_run and not a.verify_only:
            # بکاپ JSON از وضعیت فعلی PostgreSQL قبل از هر عملیات مخرب
            dump = {}
            for t in sorted(pg_tables):
                cur = pg.execute(f'SELECT * FROM "{t}"')
                dump[t] = {"columns": [d[0] for d in cur.description], "rows": [list(r) for r in cur.fetchall()]}
            if any(v["rows"] for v in dump.values()):
                bp = os.path.join(backup_dir, f"pg_before_migrate_{stamp}.json")
                with open(bp, "w", encoding="utf-8") as f:
                    json.dump({"format": "jfj-pg-backup", "version": 1, "created": stamp, "tables": dump}, f,
                              ensure_ascii=False, separators=(",", ":"))
                log(f"💾 بکاپ JSON از داده‌ی فعلی PostgreSQL: {bp}")
            pg.execute("TRUNCATE TABLE " + ", ".join(f'"{t}"' for t in sorted(pg_tables)) + " RESTART IDENTITY")
            log("🧹 جدول‌های PostgreSQL خالی شدند (--replace)")
        elif not (a.resume or a.dry_run or a.verify_only):
            busy = []
            for t, _, tcols, _ in plan:
                if t in pg_tables and pg.execute(f'SELECT 1 FROM "{t}" LIMIT 1').fetchone():
                    busy.append(t)
            # جدول‌های seed شده توسط خود ربات (products/settings) خالی فرض نمی‌شوند
            busy = [t for t in busy if t not in ("products", "settings")]
            if busy:
                die("PostgreSQL خالی نیست (" + ", ".join(busy[:6]) + "). برای ادامه‌ی انتقال قبلی --resume و برای جایگزینی کامل --replace بزنید.")

        total_src = total_ins = 0
        for t, scols, tcols, missing in plan:
            has_rowid = t in ROWID_TABLES and "rid" in types.get(t, {})
            sel_cols = ", ".join(f'"{c}"' for c in tcols)
            q = f'SELECT rowid AS __rid, {sel_cols} FROM "{t}" ORDER BY rowid' if has_rowid else f'SELECT {sel_cols} FROM "{t}"'
            if missing:
                n = src.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                report.append((t, n, None, "جدول در مقصد نیست"))
                total_src += n
                continue
            rows_src = src.execute(q).fetchall()
            out_cols = list(tcols)
            if has_rowid:
                if "rid" in out_cols:
                    out_cols.remove("rid")
                out_cols = ["rid"] + out_cols
            conv_rows = []
            try:
                for r in rows_src:
                    vals = r[1:] if has_rowid else r
                    cv = [co.conv(t, c, types[t][c], v) for c, v in zip(tcols, vals)]
                    if has_rowid:
                        d = dict(zip(tcols, cv))
                        conv_rows.append([r[0]] + [d[c] for c in out_cols[1:]])
                    else:
                        conv_rows.append(cv)
            except ValueError as e:
                pg.rollback()
                die(f"مقدار ناسازگار — انتقال متوقف شد و چیزی نوشته نشد:\n   {e}\n"
                    "   اگر گرد شدن مجاز است --allow-round بزنید، وگرنه ابتدا داده‌ی SQLite را اصلاح کنید.")
            total_src += len(conv_rows)
            ins = 0
            if not (a.dry_run or a.verify_only):
                ins = pg.insert_many(t, out_cols, conv_rows, conflict="ON CONFLICT DO NOTHING")
                total_ins += ins
            report.append((t, len(conv_rows), ins, out_cols, conv_rows))

        # --- شمارنده‌های خودکار
        if not (a.dry_run or a.verify_only):
            for t, *_ in report:
                if t in pg_tables:
                    for col in ("id", "rid"):
                        if col in types.get(t, {}):
                            _db.reset_sequence(pg, t, col)

        # --- ۳) تطبیق: شمارش + checksum
        log("\n" + "جدول".ljust(22) + "SQLite".rjust(9) + "PostgreSQL".rjust(12) + "   checksum")
        bad = False
        if a.dry_run:
            for rep in report:
                log(rep[0].ljust(22) + str(rep[1]).rjust(9) + "—".rjust(12) + "   (dry-run)")
        else:
            for rep in report:
                t = rep[0]
                if len(rep) == 4:
                    log(t.ljust(22) + str(rep[1]).rjust(9) + "—".rjust(12) + "   ⚠️ " + rep[3])
                    bad = True
                    continue
                _, n_src, ins, out_cols, conv_rows = rep
                pcols = ", ".join(f'"{c}"' for c in out_cols)
                n_pg = pg.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                fp_pg = fingerprint(pg.execute(f'SELECT {pcols} FROM "{t}"').fetchall()) if n_pg == n_src else "-"
                fp_src = fingerprint(conv_rows)
                if a.resume or a.verify_only:
                    # در حالت ادامه ممکن است ردیف‌های تازه‌تری در PostgreSQL باشد؛ فقط وجود همه‌ی ردیف‌های SQLite لازم است
                    ok = n_pg >= n_src and (n_pg != n_src or fp_pg == fp_src)
                    if n_pg > n_src:
                        have = {fingerprint([r]) for r in pg.execute(f'SELECT {pcols} FROM "{t}"').fetchall()}
                        ok = all(fingerprint([r]) in have for r in conv_rows)
                else:
                    ok = (n_pg == n_src and fp_pg == fp_src)
                bad |= not ok
                log(t.ljust(22) + str(n_src).rjust(9) + str(n_pg).rjust(12) + "   " + ("✅" if ok else "❌ ناهمخوان"))
            if bad:
                pg.rollback()
                die("تطبیق ناموفق بود؛ تراکنش برگشت داده شد و PostgreSQL تغییری نکرد.", 3)
        if a.dry_run or a.verify_only:
            pg.rollback()
        else:
            pg.commit()

    for k, n in co.rounded.items():
        problems.append(f"{k[0]}.{k[1]}: {n} مقدار اعشاری گرد شد")
    if problems:
        log("\n⚠️ نکته‌ها:")
        for p in problems:
            log("  - " + p)
    src.close()
    log("\n" + ("✅ بررسی (dry-run) تمام شد؛ چیزی نوشته نشد." if a.dry_run else
                "✅ تطبیق کامل است." if a.verify_only else
                f"✅ انتقال کامل شد و تطبیق شد: {total_src} ردیف خوانده، {total_ins} ردیف جدید درج شد."))
    if not (a.dry_run or a.verify_only):
        log("ℹ️ فایل SQLite دست‌نخورده است؛ تا مطمئن نشدید حذفش نکنید.")


if __name__ == "__main__":
    main()
