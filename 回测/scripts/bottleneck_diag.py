# -*- coding: utf-8 -*-
"""联合瓶颈分解 —— 逐级统计每个条件后的剩余天数 (样本内2019-2024, B7r参数, K5放宽到5)"""
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

STAGES = ["总天数", "过层级1", "+RPS60≥30", "+得分门槛", "+站稳MA60(dev>0)",
          "+Beta<1.2", "+MIN>0", "+流动性", "可买日"]
for code in NEW_ETFS:
    dn = bt.UNIVERSE[code][0]
    p = panels[dn]
    cnt = dict((s, 0) for s in STAGES)
    sc_hist = []
    for i, t1 in enumerate(dates):
        if t1 < "2019-01-02" or t1 > "2024-12-31":
            continue
        if t1 not in p.index:
            continue
        row = p.loc[t1]
        if not np.isfinite(row.get("MA60", np.nan)):
            continue
        cnt["总天数"] += 1
        st = states[t1]
        sc = S.etf_score(row.to_dict(), est_pct=0.6)
        sc_hist.append(sc)
        rps = float(row.get("RPS60", 50))
        ok1, _ = S.layer1_etf(row.to_dict(), product_ok=True, amount_min=3000e4)
        if not ok1:
            continue
        cnt["过层级1"] += 1
        if rps < 30:
            continue
        cnt["+RPS60≥30"] += 1
        if st == "S2":
            if sc < bt.S2_GATE: continue
        elif st == "S1":
            if sc < bt.SCORE_GATE: continue
        else:
            if sc < bt.OBS_GATE: continue
        cnt["+得分门槛"] += 1
        dev = float(row.get("DEV60", -999))
        if dev <= 0:
            continue
        cnt["+站稳MA60(dev>0)"] += 1
        beta = float(row.get("BETA60", 100)) / 100.0  # BETA60 百分比化, /100 得真实 Beta
        if beta >= 1.2:
            continue
        cnt["+Beta<1.2"] += 1
        mn_row = row.to_dict(); mn_row["R"] = 0.0
        min_pct, _ = S.min_nine(mn_row, st, False, st == "S3", None, 1.0)
        if min_pct <= 0:
            continue
        cnt["+MIN>0"] += 1
        if float(row.get("amount20", 0)) < 3e7:
            continue
        cnt["+流动性"] += 1
        cnt["可买日"] += 1
    sc_arr = np.array(sc_hist)
    print(f"\n【{bt.UNIVERSE[code][1]} {code}】 (得分: 均值{sc_arr.mean():.1f} p50={np.percentile(sc_arr,50):.1f} p75={np.percentile(sc_arr,75):.1f} p90={np.percentile(sc_arr,90):.1f})")
    print("  " + " → ".join(f"{s}:{cnt[s]}" for s in STAGES))
