# -*- coding: utf-8 -*-
"""深度诊断：建仓链路逐关卡拒绝原因统计（含组合态条件）"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from collections import Counter
from run_backtest import (load_all, build_panels, add_pit_pb, compute_score,
                          UNIVERSE, CORE_IDX, PERIOD_IN)
from tre import step_tre, TreState
from scoring import (layer1_stock, layer1_etf, six_lights, seven_lights,
                     min_nine, f04, fin_at)

panels0, fins = load_all()
panels = build_panels(panels0)
panels = add_pit_pb(panels, fins)
days = list(panels["idx_hs300"].index)
days = [d for d in days if PERIOD_IN[0] <= d <= PERIOD_IN[1]]

tre = TreState()
rej = Counter()          # 关卡拒绝计数
per_code = {c: Counter() for c in UNIVERSE}
sc_pass = {c: 0 for c in UNIVERSE}   # 得分达标但后续被挡
trade_candidates = []    # 全链路通过的天

for i, date in enumerate(days):
    if i < 2: continue
    t1 = days[i-1]
    h = panels["idx_hs300"].loc[t1]
    core_adx = [panels[x].loc[t1, "ADX14"] for x in CORE_IDX]
    cross20 = h["CROSS20"]
    hs300_ret = panels["idx_hs300"]["close"].pct_change().loc[:t1]
    vol20 = float(hs300_ret.tail(20).std(ddof=1) * np.sqrt(252) * 100)
    step_tre(tre, i, core_adx, cross20, vol20, float(h["BELOW_STREAK"]), bool(h["close"] > h["MA60"]))
    # 简化 cap（仅看量级）
    cap = 100.0
    if tre.state == "S1": cap = 60.0
    elif tre.state == "S2": cap = 40.0
    elif tre.state == "S3": cap = 20.0
    else: cap = 0.0

    for code, (dn, name, ptype, ind) in UNIVERSE.items():
        if t1 not in panels[dn].index: continue
        row = panels[dn].loc[t1].copy()
        sc = compute_score(code, dn, ptype, row, fins, panels)
        row["score"] = sc
        fin = None
        if ptype == "stock":
            f = fin_at(fins[code], t1); fin = dict(f) if f else None
            if fin: fin["price"] = row["close"]
        # 关卡链
        if ptype == "stock":
            ok1, r1 = layer1_stock(fin)
        else:
            ok1, r1 = layer1_etf(row, product_ok=True, amount_min=3000e4)
        if not ok1: rej["层级1"] += 1; per_code[code]["层级1"] += 1; continue
        if sc < 80:
            rej[f"得分<80({sc:.0f})"] += 1; per_code[code]["得分"] += 1; continue
        sc_pass[code] += 1
        if row.get("RPS60", 50) < 30:
            rej["RPS"] += 1; per_code[code]["RPS"] += 1; continue
        r_level = "A" if row.get("R", 99) <= 0.15 else ("B" if row.get("R", 99) <= 0.25 else "C")
        if r_level == "C":
            rej["层级3.5C"] += 1; per_code[code]["3.5"] += 1; continue
        open_pct = 0.0
        if ptype == "stock":
            ok_l, _ = six_lights(row, tre.state, tre.obs_active, tre.state == "S3",
                                 0, 0, 1.0, cap, open_pct, r_level)
        else:
            ok_l, _ = seven_lights(row, tre.state, tre.obs_active, 0, 0, 1.0,
                                   cap, open_pct, r_level, True, True, row.get("ma60_break90", 0))
        if not ok_l:
            rej["灯光"] += 1; per_code[code]["灯光"] += 1; continue
        min_pct, items = min_nine(row, tre.state, tre.obs_active, tre.state == "S3",
                                  fin, row.get("PB_EXPAND", 1.0))
        if min_pct <= 0:
            rej["MIN≤0"] += 1; per_code[code]["MIN"] += 1; continue
        base_atr = panels["idx_hs300"].loc[t1, "ATR20P"]
        atr_scale = min(base_atr / max(row.get("ATR20P", 2.0), 0.5), 1.5)
        amt20 = row.get("amount20", 0)
        liq_cap = 15.0 if amt20 >= 5e8 else (12.0 if amt20 >= 1e8 else (8.0 if amt20 >= 5e7 else 0.0))
        target = f04(min_pct, atr_scale, liq_cap)
        if target <= 0:
            rej[f"F04≤0(min={min_pct:.0f}%)"] += 1; per_code[code]["F04"] += 1; continue
        trade_candidates.append((date, code, round(sc,1), round(target,1), tre.state))

print("关卡拒绝:", dict(rej))
for c, cc in per_code.items():
    print(UNIVERSE[c][1], "得分达标但被后续挡:", dict(cc))
print("全链路通过:", len(trade_candidates))
for t in trade_candidates[:30]:
    print("  ", t)
