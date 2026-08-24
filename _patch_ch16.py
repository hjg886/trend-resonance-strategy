# -*- coding: utf-8 -*-
"""十六章回测指标表：年化目标 >15% → ≥6%（对齐6%实盘门槛，原15%被证伪）。"""
import io, os, shutil, sys

P = r"E:\fnOS\文档\证券\中线趋势共振策略\中线趋势共振策略 v4.7-R10 回测驱动重构版（1+2架构）完整补齐版.txt"

old = "| 年化收益率 | >15% | 复合年化 |"
new = "| 年化收益率 | ≥6%（2026-08-21修正：原「>15%」脱离现实，改对齐6%实盘门槛；B3进攻线单独按OOS 13.15%基准考核） | 复合年化 |"

with io.open(P, "r", encoding="utf-8") as f:
    c = f.read()
n = c.count(old)
if n != 1:
    print(f"[FAIL] count={n}")
    sys.exit(1)
c = c.replace(old, new, 1)
with io.open(P, "w", encoding="utf-8", newline="") as f:
    f.write(c)
print("[OK] 十六章回测指标表：年化目标 >15% → ≥6%")
print("DONE")
