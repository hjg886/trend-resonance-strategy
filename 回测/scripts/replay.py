# -*- coding: utf-8 -*-
"""单日回放：模拟主引擎 2021-02-25 建仓链路，打印每步结果"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from run_backtest import (load_all, build_panels, add_pit_pb, compute_score,
                          UNIVERSE, CORE_IDX)
from tre import step_tre, TreState
from scoring import (layer1_stock, layer1_etf, six_lights, seven_lights,
                     min_nine, f04, fin_at)
from engine import Portfolio

panels0, fins = load_all()
panels = build_panels(panels0)
panels = add_pit_pb(panels, fins)
days = list(panels["idx_hs300"].index)
days = [d for d in days if "2019-01-01" <= d <= "2024-12-31"]

# 推进到 2021-02-25
tre = TreState()
pf = Portfolio()
i_target = days.index("2021-02-25")
for i, date in enumerate(days):
    if i < 2: continue
    t1 = days[i-1]
    h = panels["idx_hs300"].loc[t1]
    core_adx = [panels[x].loc[t1, "ADX14"] for x in CORE_IDX]
    cross20 = h["CROSS20"]
    hs300_ret = panels["idx_hs300"]["close"].pct_change().loc[:t1]
    vol20 = float(hs300_ret.tail(20).std(ddof=1) * np.sqrt(252) * 100)
    step_tre(tre, i, core_adx, cross20, vol20, float(h["BELOW_STREAK"]), bool(h["close"] > h["MA60"]))
    if i == i_target:
        date, i, t1 = date, i, t1
        break

print("T日:", date, "T-1:", t1, "TRE:", tre.state, "obs:", tre.obs_active)
h = panels["idx_hs300"].loc[t1]
print("沪深300 T-1: pct_chg=%.2f%% ADX=%.1f CROSS=%d vol20=%.1f%%" % (h['pct_chg'], h['ADX14'], h['CROSS20'], vol20))
melt = pf.meltdown_level(float(h["pct_chg"]))
print("熔断级别:", melt, "→ melt_block:", melt >= 1)

# 跨资产
xbrk = 0
for xa in ["x_hstech", "x_nasdaq100", "x_gold"]:
    xr = panels[xa].loc[t1]
    if xr["close"] < xr["MA60"]: xbrk += 1
print("跨资产破位:", xbrk)
cap, cap_reason = pf.cap_limit(tre.state, xbrk, vol20, pf.day_ret)
print("三层封顶 cap:", round(cap,1), cap_reason)

for code, (dn, name, ptype, ind) in UNIVERSE.items():
    if t1 not in panels[dn].index: continue
    row = panels[dn].loc[t1].copy()
    sc = compute_score(code, dn, ptype, row, fins, panels)
    row["score"] = sc
    print(f"\n=== {name} 得分={sc:.1f} ===")
    fin = None
    if ptype == "stock":
        f = fin_at(fins[code], t1); fin = dict(f) if f else None
        if fin: fin["price"] = row["close"]
        ok1, r1 = layer1_stock(fin)
    else:
        ok1, r1 = layer1_etf(row, product_ok=True, amount_min=3000e4)
    print("层级1:", ok1, r1 if not ok1 else "")
    if not ok1: continue
    if sc < 80:
        print("得分<80 门槛挡"); continue
    rps_ok = row.get("RPS60", 50) >= 30
    print("RPS60=%.0f ≥30: %s" % (row.get("RPS60",50), rps_ok))
    if not rps_ok: continue
    if ptype == "etf":
        r_level = "A"
    else:
        r_level = "A" if row.get("R", 99) <= 0.25 else "C"
    print("层级3.5 R=%.2f → %s级" % (row.get("R",99), r_level))
    if r_level == "C": continue
    open_px = panels[dn].loc[date, "open"]
    open_pct = (open_px / row["close"] - 1) * 100
    print("T日开盘跳空: %.2f%% (open=%.2f close=%.2f)" % (open_pct, open_px, row["close"]))
    if ptype == "stock":
        ok_l, lights = six_lights(row, tre.state, tre.obs_active, tre.state == "S3", 0, 0, 1.0, cap, open_pct, r_level)
    else:
        ok_l, lights = seven_lights(row, tre.state, tre.obs_active, 0, 0, 1.0, cap, open_pct, r_level, True, True, row.get("ma60_break90", 0))
    print("灯光:", "全绿" if ok_l else "❌", lights)
    if not ok_l: continue
    mn_row = row.copy(); mn_row["R"] = 0.0 if ptype == "etf" else mn_row["R"]
    min_pct, items = min_nine(mn_row, tre.state, tre.obs_active, tre.state == "S3", fin, row.get("PB_EXPAND", 1.0))
    print("MIN9: %.0f%% items=%s" % (min_pct, [int(x) for x in items]))
    if min_pct <= 0: continue
    base_atr = panels["idx_hs300"].loc[t1, "ATR20P"]
    atr_scale = min(base_atr / max(row.get("ATR20P", 2.0), 0.5), 1.5)
    print("ATR缩放: base=%.2f%% 标的=%.2f%% → %.2f" % (base_atr, row.get("ATR20P",2), atr_scale))
    amt20 = row.get("amount20", 0)
    liq_cap = 15.0 if amt20 >= 5e8 else (12.0 if amt20 >= 1e8 else (8.0 if amt20 >= 5e7 else 0.0))
    target = f04(min_pct, atr_scale, liq_cap)
    print("F04: min=%.0f%% liq=%.0f%% target=%.1f%%" % (min_pct, liq_cap, target))
    if target <= 0: continue
    risk_budget = target * row.get("ATR20P", 3.0) / 100.0
    print("风险预算: %.2f%% ≤1%%? %s" % (risk_budget, risk_budget <= 1.0))
    if risk_budget > 1.0:
        target = 1.0 / max(row.get("ATR20P", 3.0)/100.0, 0.01)
        print("  → target 压缩至 %.1f%%" % target)
        if target < 3.0: continue
    eq_now = pf.equity({c: 0 for c in pf.holdings}) if pf.holdings else pf.cash
    pos_pct = 1.0 - pf.cash / max(eq_now, 1)
    print("总仓位: 当前=%.1f%% cap=%.1f%% → 可加=%.1f%%" % (pos_pct*100, cap, cap-pos_pct*100))
    if pos_pct + target/100.0 > cap/100.0:
        target = max(0.0, (cap/100.0 - pos_pct)*100.0)
        print("  → target 压缩至 %.1f%%" % target)
        if target < 3.0:
            print("  target<3% 放弃"); continue
    print(">>> 最终建仓 target=%.1f%% 执行!" % target)
