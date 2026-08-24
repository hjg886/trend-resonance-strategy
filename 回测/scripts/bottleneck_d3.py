# -*- coding: utf-8 -*-
"""D3口径联合瓶颈分解 —— P0-D修复+FIXL5 + R1分层 + R2分轨 + R3 z-score (样本内2019-2024)
对比 B7r 口径(旧计数/无分层/统一门槛) 与 D3 口径的逐级剩余天数
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# 强制 D3 开关
os.environ.setdefault("BT_FIXL5", "1")
os.environ.setdefault("BT_R1", "1")
os.environ.setdefault("BT_R2", "1")
os.environ.setdefault("BT_R3", "1")
os.environ.setdefault("BT_TRE_VARIANT", "V1")
import run_backtest as bt
import tre as T
import scoring as S

ALL = ["600276", "603259", "510300", "159915", "588000", "512010", "159928",
       "512880", "512690", "515030", "512480", "512170"]

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

STAGES = ["总天数", "过层级1", "+RPS≥30", "+得分门槛", "+站稳MA60",
          "+七灯(Beta/破位)", "+MIN>0", "+流动性", "可买日"]
tot = {s: 0 for s in STAGES}
per = {}
for code in ALL:
    dn = bt.UNIVERSE[code][0]
    p = panels[dn]
    cnt = dict((s, 0) for s in STAGES)
    for i, t1 in enumerate(dates):
        if t1 < "2019-01-02" or t1 > "2024-12-31":
            continue
        if t1 not in p.index:
            continue
        row = p.loc[t1]
        if not np.isfinite(row.get("MA60", np.nan)):
            continue
        cnt["总天数"] += 1
        dn2, name, ptype, ind = bt.UNIVERSE[code]
        ok1, _ = S.layer1_etf(row.to_dict(), product_ok=True, amount_min=3000e4) if ptype != "stock" \
            else S.layer1_stock(fins[code].iloc[-1].to_dict() if False else None)
        # 个股层级1用PIT财报; 简化: 个股无财报时通过
        if not ok1:
            continue
        cnt["过层级1"] += 1
        if float(row.get("RPS60", 50)) < 30:
            continue
        cnt["+RPS≥30"] += 1
        st = states[t1]
        sc = S.stock_score(row.to_dict(), None, [], []) if ptype == "stock" \
            else S.etf_score(row.to_dict(), est_pct=0.6)
        # R2 分轨门槛
        etfi = (ptype == "etf_ind")
        g_s1 = bt.ETFI_GATE_S1 if etfi else bt.SCORE_GATE
        g_s2 = bt.ETFI_GATE_S2 if etfi else bt.S2_GATE
        g_obs = bt.ETFI_GATE_OBS if etfi else bt.OBS_GATE
        if st == "S2":
            if sc < g_s2: continue
        elif st == "S1":
            if sc < g_s1: continue
        else:
            if sc < g_obs: continue
        cnt["+得分门槛"] += 1
        if float(row.get("DEV60", -999)) <= 0:
            continue
        cnt["+站稳MA60"] += 1
        # 七灯关键闸门: 第4灯(dev>0已过) + 第5灯(R1分层) + 第7灯(Beta<1.2 组合Beta, 此处用标的Beta近似)
        beta = float(row.get("BETA60", 100)) / 100.0
        m90r = row.get("ma60_break90", 0)
        m90 = int(m90r) if np.isfinite(m90r) else 0
        k5 = 3 if (ptype == "etf_ind") else 1
        if beta >= 1.2 or m90 > k5:
            continue
        cnt["+七灯(Beta/破位)"] += 1
        mn_row = row.to_dict()
        if ptype != "stock":
            mn_row["R"] = 0.0
        min_pct, _ = S.min_nine(mn_row, st, False, st == "S3", None, 1.0,
                                ind_etf=(ptype == "etf_ind"))
        if min_pct <= 0:
            continue
        cnt["+MIN>0"] += 1
        if float(row.get("amount20", 0)) < 3e7:
            continue
        cnt["+流动性"] += 1
        cnt["可买日"] += 1
    per[code] = cnt
    for s in STAGES:
        tot[s] += cnt[s]

print(f"\n{'标的':<10}{'类型':<8}" + "".join(f"{s:>10}" for s in STAGES[1:]))
for code in ALL:
    dn2, name, ptype, ind = bt.UNIVERSE[code]
    c = per[code]
    print(f"{code:<10}{ptype:<8}" + "".join(f"{c[s]:>10}" for s in STAGES[1:]))
print(f"\n{'合计':<10}{'':<8}" + "".join(f"{tot[s]:>10}" for s in STAGES[1:]))
print(f"\n可买日合计={tot['可买日']}  (目标: 6年≥48日 ≈ 月2次)")
