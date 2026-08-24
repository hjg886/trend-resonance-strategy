# -*- coding: utf-8 -*-
"""战略修正回写：基于 2026-08-21 P0d-core 四版回测的 OOS 全负证据，
修正「防守底盘60-70%锁死主引擎」→「现金管理为主 + 主引擎风险资产收缩」。"""
import io, os, shutil, sys

P = r"E:\fnOS\文档\证券\中线趋势共振策略\中线趋势共振策略 v4.7-R10 回测驱动重构版（1+2架构）完整补齐版.txt"
BAK = P + ".bak_20260821_strategy"
if not os.path.exists(BAK):
    shutil.copy2(P, BAK)
    print(f"[BAK] {BAK}")

FIX = ("**【2026-08-21 战略修正·OOS全负证据】**：门槛75+H1+BREADTH 四版回测显示主引擎样本外 OOS 期望全负"
       "（-1.07%~-1.53%）、六年总收益 96.2% 来自现金管理（独立配置）而非趋势交易——据此「防守底盘60-70%锁死主引擎」"
       "不再成立，修正为：**现金管理才是真防守（正期望），主引擎趋势交易为负期望慢性失血、其风险资产应收缩至最小、"
       "不作为防守底盘持仓主体**；主引擎降级为观察/过渡期工具，B3 进攻线是唯一正期望收益源。")

pairs = [
    # 第1012行（十六章内战略决策）
    ("仍需主引擎频率提升或B3配比提升。",
     "仍需主引擎频率提升或B3配比提升。" + FIX),
    # 第1382行（附录D-5战略决策）
    ("仍需主引擎频率提升或B3配比提升至15-20%。",
     "仍需主引擎频率提升或B3配比提升至15-20%。" + FIX),
]

with io.open(P, "r", encoding="utf-8") as f:
    c = f.read()

ok = True
for old, new in pairs:
    n = c.count(old)
    if n != 1:
        print(f"[FAIL] count={n}: {old[:45]!r}")
        ok = False
    else:
        c = c.replace(old, new, 1)
        print(f"[OK] {old[:45]!r}")

if ok:
    with io.open(P, "w", encoding="utf-8", newline="") as f:
        f.write(c)
    print("\n战略修正已回写两处战略决策")
else:
    print("\nSOME FAILED (未写入)")
sys.exit(0 if ok else 1)
