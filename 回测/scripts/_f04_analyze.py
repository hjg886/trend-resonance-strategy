# -*- coding: utf-8 -*-
"""F-04 专项验证: G1r 建仓金额贡献分析（定位仓位引擎瓶颈）"""
import json, os

OUT = os.path.join(os.path.dirname(__file__), "..", "output")
v = json.load(open(os.path.join(OUT, "variant_G1r.json"), encoding="utf-8"))
buys = v["buys_in"]
closed = v["closed_in"]

print("=== 建仓 target 分布 ===")
print("总建仓:", len(buys))
tg = {}
for b in buys:
    tg[b["target"]] = tg.get(b["target"], 0) + 1
print("target 分布:", {round(k, 1): v for k, v in sorted(tg.items())})
print("target 均值: %.2f%%" % (sum(b["target"] for b in buys) / len(buys)))
print("打到12%%上限的笔数:", sum(1 for b in buys if b["target"] >= 11.9))
print()

print("=== 平仓单金额贡献 Top10 ===")
amts = [float(c["pnl"]) for c in closed]
print("净PnL合计: {:+,.0f} 元".format(sum(amts)))
for c in sorted(closed, key=lambda x: -abs(float(x["pnl"])))[:10]:
    print("  {} {:<8s} {:>+8.2f}%  {:>+,.0f}元  {}".format(
        c["exit"], c["code"], float(c["pnl_pct"]) * 100, float(c["pnl"]), c["exit_reason"]))
print()

print("=== 单笔投入金额 (cost_basis) ===")
pairs = [(c, float(c["cost_basis"])) for c in closed]
pairs.sort(key=lambda x: -x[1])
for c, i in pairs:
    print("  {} {:<8s} 投入≈{:>9,.0f}元".format(c["exit"], c["code"], i))
print("单笔投入均值: {:+,.0f} 元".format(sum(i for _, i in pairs) / len(pairs)))
print("单笔投入中位: {:+,.0f} 元".format(sorted(i for _, i in pairs)[len(pairs) // 2]))
print()

print("=== 按 reason 统计投入金额 ===")
from collections import defaultdict
byr = defaultdict(list)
for c in closed:
    byr[c["exit_reason"]].append(float(c["pnl"]))
for k, lst in sorted(byr.items(), key=lambda x: -sum(x[1])):
    print("  {:<28s} {:>2d}笔  {:>+,.0f}元".format(k, len(lst), sum(lst)))
