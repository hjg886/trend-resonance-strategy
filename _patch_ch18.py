# -*- coding: utf-8 -*-
"""简化第十八章版本记录 v4.7-R10 行（650字→约200字），收敛为要点、细节指向附录D/E。"""
import io, os, shutil, sys

P = r"E:\fnOS\文档\证券\中线趋势共振策略\中线趋势共振策略 v4.7-R10 回测驱动重构版（1+2架构）完整补齐版.txt"
BAK = P + ".bak_20260821_ch18"
if not os.path.exists(BAK):
    shutil.copy2(P, BAK)
    print(f"[BAK] {BAK}")

with io.open(P, "r", encoding="utf-8") as f:
    lines = f.read().splitlines(keepends=True)

# 校验锚点
assert lines[1098].startswith("| **v4.7-R10** |"), "行1099锚点不符"

lines[1098] = ("| **v4.7-R10** | **2026-08-18（修正至08-21）** | "
               "**回测驱动重构版：R-01~R-10 十项重构 + F-01~F-35 继承（新增F-34/F-35）+ "
               "四轮回测改善（P0→F04a→JOINT→P12v6）+ BREADTH否决层 + 去冗余阶段2/3（冗余4/5/3）+ "
               "门槛75 + 战略/哲学/ETF止损口径修正（详见附录D/E）** | "
               "**当前版本（IS 2.97%/OOS 4.02%<6%禁止实盘；B3进攻线进入模拟盘）** |\n")

with io.open(P, "w", encoding="utf-8", newline="") as f:
    f.write("".join(lines))
print("[OK] 版本记录 v4.7-R10 行已简化")
print("DONE")
