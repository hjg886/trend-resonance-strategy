# -*- coding: utf-8 -*-
"""P0d-core 固化：H1(禁S1+ETF) + BREADTH否决 + R10门槛75 默认开启。
回测证据：裸跑期望-1.062% → P0d-core +0.771%（H1+BREADTH是最核心改善项，门槛75保留成立）。"""
import io, os, shutil, sys

P = r"E:\fnOS\文档\证券\中线趋势共振策略\回测\scripts\run_backtest.py"
BAK = P + ".bak_20260821_p0dcore"
if not os.path.exists(BAK):
    shutil.copy2(P, BAK)
    print(f"[BAK] {BAK}")

pairs = [
    # ① R10 门槛默认开启（走 75/73/78，而非 else 的 70/75/72）
    ('R10_GATES_ON = os.environ.get("BT_R10GATES", "0") == "1"',
     'R10_GATES_ON = os.environ.get("BT_R10GATES", "1") == "1"  # P0d-core固化: 默认开，门槛75/73/78'),
    # ② H1 禁 S1+ETF 默认开启
    ('H1_S1NOETF_ON = os.environ.get("BT_H1_S1NOETF", "0") == "1"',
     'H1_S1NOETF_ON = os.environ.get("BT_H1_S1NOETF", "1") == "1"  # P0d-core固化: 默认开'),
    # ③ BREADTH 否决层默认开启
    ('BREADTH_VETO_ON = os.environ.get("BT_BREADTH_VETO", "0") == "1"',
     'BREADTH_VETO_ON = os.environ.get("BT_BREADTH_VETO", "1") == "1"  # P0d-core固化: 默认开'),
]

with io.open(P, "r", encoding="utf-8") as f:
    c = f.read()

ok = True
for old, new in pairs:
    n = c.count(old)
    if n != 1:
        print(f"[FAIL] count={n}: {old[:50]!r}")
        ok = False
    else:
        c = c.replace(old, new, 1)
        print(f"[OK] {old[:45]!r}")

if ok:
    with io.open(P, "w", encoding="utf-8", newline="") as f:
        f.write(c)
    print("\nP0d-core 固化完成：H1 + BREADTH + 门槛75 默认开启")
else:
    print("\nSOME FAILED (未写入)")
sys.exit(0 if ok else 1)
