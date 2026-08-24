# -*- coding: utf-8 -*-
"""从 results_in.json / results_oos.json 提取三个裁决数字：
1) 年建仓笔数 (R-08 目标 ≥6笔/年, 基线 2.5)
2) 单笔期望 % (基线 +0.27%, 转负=立即回滚)  —— 用 closed(完整平仓) 口径
3) 年化 % (IS/OOS, 6% 门槛)
"""
import json, os
from collections import Counter

OUT = os.path.join(os.path.dirname(__file__), "..", "output")

def load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as f:
        return json.load(f)

def cagr(equity, n_years):
    return ((equity / 1_000_000.0) ** (1.0 / n_years) - 1.0) * 100.0 if n_years > 0 else 0.0

def analyze(res, label, years):
    buys = res.get("buys", [])
    closed = res.get("closed", [])
    final_equity = res.get("final_equity", 1_000_000)
    n_years = years
    ann_buys = len(buys) / n_years
    rets = [c["pnl_pct"] * 100.0 for c in closed]
    exp = sum(rets) / len(rets) if rets else 0.0
    wins = sum(1 for r in rets if r > 0)
    ann = cagr(final_equity, n_years)
    # 现金管理贡献
    cm = res.get("cash_mgmt_ret", 0)
    print(f"===== {label} ({years:.1f}年) =====")
    print(f"  建仓笔数   : {len(buys)} 笔  |  年化 {ann_buys:.2f} 笔/年   [R-08目标≥6.0 | 基线2.5]")
    print(f"  单笔期望   : {exp:+.3f}%   ({len(rets)}笔平仓, 胜率 {wins/len(rets)*100:.1f}%)   [基线+0.27% | 转负即回滚]")
    print(f"  年化(复利) : {ann:+.2f}%   (期末{final_equity:,.0f})   [6%门槛]")
    print(f"  现金管理贡献: {cm}  |  obs_stats: {res.get('obs_stats')}")
    bc = Counter(b["date"][:4] for b in buys)
    print(f"  年度建仓分布: {dict(sorted(bc.items()))}")
    # 期望构成: 盈利笔/亏损笔贡献
    pos = sum(r for r in rets if r > 0); neg = sum(r for r in rets if r <= 0)
    print(f"  盈利笔合计{pos:+.1f}% / 亏损笔合计{neg:+.1f}%  (盈亏比 {abs(pos/neg) if neg else 0:.2f})")
    # 建仓原因分布
    rc = Counter(b["reason"] for b in buys)
    print(f"  建仓原因分布: {dict(rc)}")

if __name__ == "__main__":
    analyze(load("results_in.json"), "样本内 IS (2019-2024)", 6.0)
    print()
    analyze(load("results_oos.json"), "样本外 OOS (2025-2026H1)", 1.5)
