"""اجرای همه‌ی تست‌های بازی‌ها: python3 tests/run_all.py   (هیچ‌چیز از دیتابیس واقعی لمس نمی‌شود؛ دیتابیس موقت)"""
import os, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
bad = 0
for f in ("t_g", "t_g2", "t_x", "t_c", "t_a", "t_t", "t_r", "t_n", "t_v", "t_w", "t_y", "t_m", "t_z", "t_q", "t_pg", "t_mig", "sqlcheck", "t_e2e"):
    r = subprocess.run([sys.executable, f + ".py"], cwd=here, capture_output=True, text=True, timeout=300)
    p = sum(1 for l in r.stdout.splitlines() if l.startswith("PASS"))
    fl = [l for l in r.stdout.splitlines() if l.startswith("FAIL")]
    print(f"{f}: PASS={p} FAIL={len(fl)}")
    for l in fl:
        print("   ", l)
    bad += len(fl) + (1 if r.returncode not in (0,) and not p else 0)
print("همه‌چیز سالم است ✅" if not bad else f"❌ {bad} خطا")
sys.exit(1 if bad else 0)
