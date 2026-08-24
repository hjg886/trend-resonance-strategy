# -*- coding: utf-8 -*-
"""修正「永久固化」：投资哲学与「只增不减」是同一思维残留，本次回测已证伪多条哲学，改为「相对稳定·证据驱动可修正」。"""
import io, os, shutil, sys

P = r"E:\fnOS\文档\证券\中线趋势共振策略\中线趋势共振策略 v4.7-R10 回测驱动重构版（1+2架构）完整补齐版.txt"
BAK = P + ".bak_20260821_philo2"
if not os.path.exists(BAK):
    shutil.copy2(P, BAK)
    print(f"[BAK] {BAK}")

pairs = [
    # ① 标题
    ("## 二、策略底层投资哲学（永久固化）",
     "## 二、策略底层投资哲学（相对稳定·证据驱动可修正）"),
    # ② 第7条里的「永久固化」
    ("本章投资哲学为价值观，永久固化；",
     "本章投资哲学为价值观，相对稳定（防朝令夕改）、但可基于回测证据修正（2026-08-21 已据此修正第1/5/6条，即「永久固化」本身不成立）；"),
]

with io.open(P, "r", encoding="utf-8") as f:
    c = f.read()

ok = True
for old, new in pairs:
    n = c.count(old)
    if n != 1:
        print(f"[FAIL] count={n}: {old[:40]!r}")
        ok = False
    else:
        c = c.replace(old, new, 1)
        print(f"[OK] {old[:40]!r}")

if ok:
    with io.open(P, "w", encoding="utf-8", newline="") as f:
        f.write(c)
    print("\n「永久固化」已修正为「相对稳定·证据驱动可修正」")
else:
    print("\nSOME FAILED (未写入)")
sys.exit(0 if ok else 1)
