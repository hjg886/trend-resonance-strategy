# -*- coding: utf-8 -*-
"""去冗余阶段3·冗余3：R值等级统一 A/B/C 三级（run_backtest.py 内联原为 A/C 两级，与 scoring.layer35 及第七章MIN③不一致）"""
import io, os, shutil, sys

PATH = r"E:\fnOS\文档\证券\中线趋势共振策略\回测\scripts\run_backtest.py"
BAK = PATH + ".bak_20260821_s3"
if not os.path.exists(BAK):
    shutil.copy2(PATH, BAK)
    print(f"[BAK] {BAK}")

old = '                    r_level, l20, h60, pb_ok = ("A", row.get("L20"), row.get("H60"), True) if row.get("R", 99) <= 0.25 else ("C", row.get("L20"), row.get("H60"), True)'
new = ('                    # 【去冗余·阶段3·冗余3】R值等级统一A/B/C三级（对齐scoring.layer35与第七章MIN③：≤0.15=A,≤0.25=B,>0.25=C）\n'
       '                    _r = row.get("R", 99)\n'
       '                    r_level = "A" if _r <= 0.15 else ("B" if _r <= 0.25 else "C")\n'
       '                    l20, h60, pb_ok = row.get("L20"), row.get("H60"), True')

with io.open(PATH, "r", encoding="utf-8") as f:
    c = f.read()
n = c.count(old)
if n != 1:
    print(f"[FAIL] count={n}")
    sys.exit(1)
c = c.replace(old, new, 1)
with io.open(PATH, "w", encoding="utf-8", newline="") as f:
    f.write(c)
print("[OK] run_backtest.py R值等级已统一为A/B/C三级")
print("DONE")
