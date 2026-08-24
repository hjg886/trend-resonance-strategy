# -*- coding: utf-8 -*-
"""诊断：定位建仓链路各关卡通过率"""
import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import pandas as pd
from run_backtest import (load_all, build_panels, add_pit_pb, compute_score,
                          UNIVERSE, CORE_IDX, PERIOD_IN)
from tre import step_tre, TreState
from scoring import (layer1_stock, layer1_etf, six_lights, seven_lights,
                     min_nine, fin_at)

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
panels0, fins = load_all()
panels = build_panels(panels0)
panels = add_pit_pb(panels, fins)
days = list(panels["idx_hs300"].index)
days = [d for d in days if PERIOD_IN[0] <= d <= PERIOD_IN[1]]
print(f"样本内交易日: {len(days)}")

# 1) TRE 状态分布
tre = TreState()
state_cnt = {}
for i, date in enumerate(days):
    if i < 2: continue
    t1 = days[i-1]
    h = panels["idx_hs300"].loc[t1]
    core_adx = [panels[x].loc[t1, "ADX14"] for x in CORE_IDX]
    cross20 = h["CROSS20"]
    hs300_ret = panels["idx_hs300"]["close"].pct_change().loc[:t1]
    vol20 = float(hs300_ret.tail(20).std(ddof=1) * np.sqrt(252) * 100)
    step_tre(tre, i, core_adx, cross20, vol20, float(h["BELOW_STREAK"]), bool(h["close"] > h["MA60"]))
    state_cnt[tre.state] = state_cnt.get(tre.state, 0) + 1
print("TRE状态分布:", {k: state_cnt.get(k, 0) for k in ["S1", "S2", "S3", "S4"]},
      "obs_active:", state_cnt.get("obs", 0))

# 2) 评分/关卡统计
from collections import Counter
stat = Counter()
sc_ge80 = {c: 0 for c in UNIVERSE}
sc_ge85 = {c: 0 for c in UNIVERSE}
rps_ok = {c: 0 for c in UNIVERSE}
rA = {c: 0 for c in UNIVERSE}
light_ok = {c: 0 for c in UNIVERSE}
min_ok = {c: 0 for c in UNIVERSE}
total_eligible = {c: 0 for c in UNIVERSE}
for i, date in enumerate(days):
    if i < 2: continue
    t1 = days[i-1]
    for code, (dn, name, ptype, ind) in UNIVERSE.items():
        if t1 not in panels[dn].index: continue
        row = panels[dn].loc[t1].copy()
        sc = compute_score(code, dn, ptype, row, fins, panels)
        row["score"] = sc
        stat["scored"] += 1
        if sc >= 80: sc_ge80[code] += 1
        if sc >= 85: sc_ge85[code] += 1
        fin = None
        if ptype == "stock":
            f = fin_at(fins[code], t1)
            fin = dict(f) if f else None
            if fin: fin["price"] = row["close"]
        if ptype == "stock":
            ok1, r1 = layer1_stock(fin)
        else:
            ok1, r1 = layer1_etf(row, product_ok=True, amount_min=3000e4)
        if not ok1:
            stat["fail_layer1"] += 1; continue
        if row.get("RPS60", 50) >= 30:
            rps_ok[code] += 1
        else:
            stat["fail_rps"] += 1; continue
        if row.get("R", 99) <= 0.25:
            rA[code] += 1
        else:
            stat["fail_rlevel"] += 1; continue
        # 灯光校验（用宽松环境测通过率）
        open_pct = 0.0; n_hold = 0; n_same = 0; beta = 1.0; cap = 100.0; r_level = "A"
        if ptype == "stock":
            ok_l, _ = six_lights(row, tre.state, tre.obs_active, tre.state == "S3",
                                  n_hold, n_same, beta, cap, open_pct, r_level)
        else:
            ok_l, _ = seven_lights(row, tre.state, tre.obs_active, n_hold, n_same,
                                   beta, cap, open_pct, r_level, True, True,
                                   row.get("ma60_break90", 0))
        if not ok_l:
            stat["fail_lights"] += 1; continue
        light_ok[code] += 1
        min_pct, items = min_nine(row, tre.state, tre.obs_active, tre.state == "S3",
                                  fin, row.get("PB_EXPAND", 1.0))
        if min_pct <= 0:
            stat["fail_min"] += 1; continue
        min_ok[code] += 1
        total_eligible[code] += 1

print("\n关卡统计:", dict(stat))
print("得分>=80天数:", dict(sc_ge80))
print("得分>=85天数:", dict(sc_ge85))
print("RPS>=30天数:", dict(rps_ok))
print("R<=0.25(层级3.5A)天数:", dict(rA))
print("灯光通过天数:", dict(light_ok))
print("MIN9通过天数:", dict(min_ok))

# 3) 得分分布直方
import numpy as np
allscores = []
for code in UNIVERSE:
    dn = UNIVERSE[code][0]
    df = panels[dn].loc[days]
    for d in days:
        if d in df.index:
            row = df.loc[d]
            allscores.append(compute_score(code, dn, UNIVERSE[code][2], row, fins, panels))
allscores = [s for s in allscores if np.isfinite(s)]
print("\n得分分布: min=%.1f p25=%.1f med=%.1f p75=%.1f max=%.1f" % (
    np.min(allscores), np.percentile(allscores, 25), np.median(allscores),
    np.percentile(allscores, 75), np.max(allscores)))
print(">=80: %.1f%%  >=85: %.1f%%" % (
    100 * np.mean([s >= 80 for s in allscores]), 100 * np.mean([s >= 85 for s in allscores])))
