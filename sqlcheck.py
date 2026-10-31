"""بررسی ایستای همه‌ی SQLهای پروژه روی PostgreSQL واقعی: هر دستور DML با PREPARE (تبدیل‌شده توسط db.translate) اعتبارسنجی می‌شود
(سینتکس، نام جدول/ستون، نوع‌ها، GROUP BY). دستورهای پویا (f-string) جدا گزارش می‌شوند تا دستی بررسی شوند."""
import ast, os, re, sys
import pgtest
import bot_test as b, games as g, miniapp as m
import db
pgtest.fresh("sqlcheck")
b.BOT_ID = 1
m._schema_done = False
with db._pool.__class__ and db.schema_lock():
    b.install_schema(); b.migrate_schema(); m._mini_tables()
g.init(b)
b.seed_products()
ROOT = pgtest.ROOT
NAMES = {"execute", "executemany", "_row", "_rows", "_x", "_q1", "_q"}
bad = good = skipped = dyn = 0
dyn_list = []
seen = set()
SQLRE = re.compile(r"\s*(SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM|WITH)\b[\s\S]*\b(FROM|SET|VALUES|INTO)\b", re.I)
for fn in ("bot_test.py", "games.py", "miniapp.py"):
    tree = ast.parse(open(os.path.join(ROOT, fn), encoding="utf-8").read())
    frag = {id(c) for j in ast.walk(tree) if isinstance(j, ast.JoinedStr) for c in ast.walk(j) if isinstance(c, ast.Constant)}
    for n in ast.walk(tree):
        if id(n) in frag:
            continue          # تکه‌ی f-string (پویا) — با تست‌های اجرایی پوشش داده می‌شود
        if isinstance(n, ast.Call) and isinstance(n.func, (ast.Attribute, ast.Name)):
            nm = n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id
            if nm in NAMES and n.args and not isinstance(n.args[0], (ast.Constant, ast.Name, ast.Subscript)) :
                dyn += 1; dyn_list.append((fn, n.lineno, ast.unparse(n.args[0])[:90]))
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and SQLRE.match(n.value) and len(n.value) > 15:
            sql = n.value
            if (fn, sql) in seen:
                continue
            seen.add((fn, sql))
            q = db.translate(sql, "?" in sql)
            k = [0]
            def ph(_):
                k[0] += 1; return f"${k[0]}"
            q = re.sub(r"%s", ph, q).replace("%%", "%")
            with db.get_db() as c:
                cur = c._raw.cursor()
                try:
                    cur.execute("PREPARE chk AS " + q)
                    good += 1
                except Exception as e:
                    msg = str(e).split("\n")[0]
                    if "could not determine data type of parameter" in msg:
                        skipped += 1
                    else:
                        bad += 1; print("FAIL BAD", fn, n.lineno, msg, "\n   ", sql[:140].replace("\n", " "))
                finally:
                    c._raw.rollback(); c._raw.cursor().execute("DEALLOCATE ALL"); c._raw.rollback()
print(f"INFO checked ok={good} bad={bad} skipped(DDL/untyped)={skipped} dynamic={dyn}")
for d in dyn_list: print("INFO DYN", *d)
print(("PASS" if not bad else "FAIL") + f" همه‌ی SQLهای ایستا روی PostgreSQL اعتبارسنجی شد ({good} دستور، {bad} خطا)")
sys.exit(1 if bad else 0)
