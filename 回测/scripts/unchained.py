# -*- coding: utf-8 -*-
"""解锁版上界分析 —— 分离各闸门独立影响 (样本内2019-2024)
逐级解锁: 基线(全闸门) → 解锁第5灯 → +解锁Beta → +解锁MIN → 仅剩得分/RPS/组合等
确认扩展池"理论上限"到底有多少可买日, 定位最终瓶颈
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_backtest as bt
import tre as T
import scoring as S

NEW_ETFS = ["512880", "512690", "515030", "512480", "512170"]

panels0, fins = bt.load_all()
panels = bt.build_panels(panels0)
hs = panels["idx_hs300"]
dates = hs.index

tre = T.TreState()
states = {}
for i, t1 in enumerate(dates):
    h = hs.loc[t1]
    core_adx = [panels[x].loc[t1, "ADX14"] for x in bt.CORE_IDX]
    hs300_ret = panels["idx_hs300"]["close"].pct_change().loc[:t1]
    vol20 = float(hs300_ret.tail(20).std(ddof=1) * np.sqrt(252) * 100)
    T.step_tre(tre, i, core_adx, int(h["CROSS20"]), vol20,
               float(h["BELOW_STREAK"]), bool(h["close"] > h["MA60"]), variant="V1")
    states[t1] = tre.state

# 状态占比
from collections import Counter
sc_cnt = Counter(states.values())
tot = sum(sc_cnt.values())
print("TRE状态占比(样本内): " + ", ".join(f"S{k}={v}({v/tot*100:.0f}%)" for k, v in sorted(sc_cnt.items())))

# 闸门组合: (解锁第5灯, 解锁Beta, 解锁MIN, 解锁流动性)
MODES = [
    ("基线(全闸门)",              False, False, False, False),
    ("解锁第5灯(K=∞)",            True,  False, False, False),
    ("解锁第5灯+Beta",            True,  True,  False, False),
    ("解锁第5灯+Beta+MIN",        True,  True,  True,  False),
    ("解锁第5灯+Beta+MIN+流动性", True,  True,  True,  True),
]

def buyable(code, unlock_l5, unlock_beta, unlock_min, unlock_liq):
    dn = bt.UNIVERSE[code][0]
    p = panels[dn]
    cnt = 0
    detail = []
    for i, t1 in enumerate(dates):
        if t1 < "2019-01-02" or t1 > "2024-12-31":
            continue
        if t1 not in p.index:
            continue
        row = p.loc[t1]
        if not np.isfinite(row.get("MA60", np.nan)):
            continue
        st = states[t1]
        sc = S.etf_score(row.to_dict(), est_pct=0.6)
        rps = float(row.get("RPS60", 50))
        ok1, _ = S.layer1_etf(row.to_dict(), product_ok=True, amount_min=3000e4)
        if not ok1 or rps < 30:
            continue
        if st == "S2":
            if sc < bt.S2_GATE: continue
        elif st == "S1":
            if sc < bt.SCORE_GATE: continue
        else:
            if sc < bt.OBS_GATE: continue
        dev = float(row.get("DEV60", -999))
        if dev <= 0:
            continue
        if not unlock_l5:
            m90 = row.get("ma60_break90", 99)
            if not np.isfinite(m90) or m90 > 1:
                continue
        if not unlock_beta:
            beta = float(row.get("BETA60", 100)) / 100.0
            if beta >= 1.2:
                continue
        if not unlock_min:
            mn_row = row.to_dict(); mn_row["R"] = 0.0
            min_pct, _ = S.min_nine(mn_row, st, False, st == "S3", None, 1.0)
            if min_pct <= 0:
                continue
        if not unlock_liq:
            if float(row.get("amount20", 0)) < 3e7:
                continue
        cnt += 1
        if len(detail) < 2:
            detail.append(f"{t1} S{st} sc={sc:.0f} b90={row.get('ma60_break90', -1)}")
    return cnt, detail

print(f"\n{'模式':<24}" + "".join(f"{bt.UNIVERSE[c][1][:4]:>9}" for c in NEW_ETFS))
for label, u1, u2, u3, u4 in MODES:
    row_vals = []
    for code in NEW_ETFS:
        c, _ = buyable(code, u1, u2, u3, u4)
        row_vals.append(c)
    print(f"{label:<24}" + "".join(f"{v:>9}" for v in row_vals))
