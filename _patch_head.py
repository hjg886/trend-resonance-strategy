# -*- coding: utf-8 -*-
"""简化开头元信息：版本定位/修改日期/版本状态 收敛为要点，细节指向第十六/十八章。"""
import io, os, shutil, sys

P = r"E:\fnOS\文档\证券\中线趋势共振策略\中线趋势共振策略 v4.7-R10 回测驱动重构版（1+2架构）完整补齐版.txt"
BAK = P + ".bak_20260821_head"
if not os.path.exists(BAK):
    shutil.copy2(P, BAK)
    print(f"[BAK] {BAK}")

with io.open(P, "r", encoding="utf-8") as f:
    lines = f.read().splitlines(keepends=True)

# 行索引（0-based）：第4行=3，第6行=5，第7行=6
lines[3] = ("版本定位：趋势共振 v4.5-R1 为主引擎（1）+ 安盈六策 v1.7.5-CRO 三大补丁（2）："
            "P53 ETF专用补丁、组合均衡风控、策略层自动降档，形成「个股+ETF双轨」中线量化体系。"
            "经六轮回测驱动重构，落地 10 项重构裁决（R-01~R-10），35 项融合裁决（F-01~F-35）全部保留（详见第十八章）。\n")

lines[5] = ("修改日期：2026-08-18 初始｜08-19 回测修正（F-35/BREADTH/附录D/C11）｜"
            "08-21 修正（去冗余阶段2/3、门槛75、P0d-core固化、战略修正、投资哲学修正、ETF止损口径警示）。\n")

lines[6] = ("版本状态：⚠️ 回测未达标，禁止实盘——主引擎 IS年化2.97%/OOS年化4.02% < 6%门槛，"
            "降为防守/观察定位；B3进攻线（OOS 13.15%）为唯一正期望收益源，09-01 起模拟盘验证"
            "（详见第十六章/附录D）。\n")

with io.open(P, "w", encoding="utf-8", newline="") as f:
    f.write("".join(lines))
print("[OK] 开头元信息已简化：版本定位/修改日期/版本状态")
print("DONE")
