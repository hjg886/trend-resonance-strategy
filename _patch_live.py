# -*- coding: utf-8 -*-
"""同步实盘执行文本的三层资金架构战略定位（防守底盘收缩+现金管理为真防守）。"""
import io, os, shutil, sys

P = r"E:\fnOS\文档\证券\中线趋势共振策略\中线趋势共振策略 v5.0 实盘执行文本.txt"
BAK = P + ".bak_20260821"
if not os.path.exists(BAK):
    shutil.copy2(P, BAK)
    print(f"[BAK] {BAK}")

old = "战略定位（首席风控官裁决，2026-08-18）：三层资金架构=进攻线0-10%渐进（B3模拟盘候选）+防守底盘60-70%（JOINT+P12v6锁死）+现金国债ETF稳定器30-40%。"
new = ("战略定位（首席风控官裁决，2026-08-18；2026-08-21战略修正）：三层资金架构=进攻线0-10%渐进（B3模拟盘候选）+防守底盘60-70%（JOINT+P12v6锁死）+现金国债ETF稳定器30-40%。"
       "【2026-08-21修正·OOS全负证据】主引擎样本外OOS期望全负（-1.07%~-1.53%）、六年收益96.2%来自现金管理（独立配置）——「防守底盘60-70%锁死主引擎」不再成立，修正配比：进攻线(B3)0-10% + 主引擎风险资产10-20%(收缩) + 现金管理/国债ETF 70-90%(真防守主力)。")

with io.open(P, "r", encoding="utf-8") as f:
    c = f.read()
n = c.count(old)
if n != 1:
    print(f"[FAIL] count={n}")
    sys.exit(1)
c = c.replace(old, new, 1)
with io.open(P, "w", encoding="utf-8", newline="") as f:
    f.write(c)
print("[OK] 实盘执行文本战略定位已同步修正")
print("DONE")
