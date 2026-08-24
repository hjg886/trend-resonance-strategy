# -*- coding: utf-8 -*-
"""战略修正补充具体配比数字：防守底盘60-70% → 主引擎风险资产10-20%收缩 + 现金管理70-90%真防守。"""
import io, os, shutil, sys

P = r"E:\fnOS\文档\证券\中线趋势共振策略\中线趋势共振策略 v4.7-R10 回测驱动重构版（1+2架构）完整补齐版.txt"

old = "主引擎降级为观察/过渡期工具，B3 进攻线是唯一正期望收益源。"
new = ("主引擎降级为观察/过渡期工具，B3 进攻线是唯一正期望收益源。"
       "**修正后配比：进攻线(B3)0-10% + 主引擎风险资产10-20%(收缩，原60-70%) + 现金管理/国债ETF 70-90%(真防守主力，原30-40%)**。")

with io.open(P, "r", encoding="utf-8") as f:
    c = f.read()
n = c.count(old)
if n == 0:
    print("[FAIL] 未找到")
    sys.exit(1)
c = c.replace(old, new)
with io.open(P, "w", encoding="utf-8", newline="") as f:
    f.write(c)
print(f"[OK] 配比数字已补充，替换 {n} 处")
print("DONE")
