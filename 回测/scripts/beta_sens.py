# -*- coding: utf-8 -*-
"""Beta 闸门敏感性 —— 量化放宽 Beta<1.2 对各 ETF 可买日的释放效果
对比原池(宽基+旧行业) vs 新池(5只新行业ETF)
在"过得分门槛+站稳MA60"前提下的 Beta 多档位通过天数
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_backtest as bt
import tre as T
import scoring as S

ALL_ETF = [c for c, v in bt.UNIVERSE.items() if v[2].startswith("etf")]
OLD_ETF = ["510300", "159915", "588000", "512010", "159928"]
NEW_ETF = ["512880", "512690", "515030", "512480", "512170"]

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

def analyze(codes, tag):
    print(f"\n========== {tag} ==========")
    for code in codes:
        dn, name, ptype, ind = bt.UNIVERSE[code]
        p = panels[dn]
        betas, scs = [], []
        # 前置: 过层级1+RPS+得分门槛+站稳MA60 的天数
        passed_pre = 0
        beta_pass = {"<1.2": 0, "<1.5": 0, "<1.8": 0, "任意": 0}
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
            scs.append(sc)
            beta_raw = float(row.get("BETA60", np.nan))
            if not np.isfinite(beta_raw):
                continue
            beta = beta_raw / 100.0  # BETA60 百分比化(100=1.0), 与 run_backtest 口径一致
            betas.append(beta)
            ok1, _ = S.layer1_etf(row.to_dict(), product_ok=True, amount_min=3000e4)
            rps = float(row.get("RPS60", 50))
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
            passed_pre += 1
            if beta < 1.2: beta_pass["<1.2"] += 1
            if beta < 1.5: beta_pass["<1.5"] += 1
            if beta < 1.8: beta_pass["<1.8"] += 1
            beta_pass["任意"] += 1
        b = np.array(betas)
        q = np.nanpercentile(b, [25, 50, 75, 90])
        print(f"{name} {code} [{ptype}] | 过前置闸门={passed_pre} | "
              f"Beta通过: <1.2:{beta_pass['<1.2']} <1.5:{beta_pass['<1.5']} "
              f"<1.8:{beta_pass['<1.8']} 任意:{beta_pass['任意']}")
        print(f"  BETA60分布 p25={q[0]:.2f} p50={q[1]:.2f} p75={q[2]:.2f} p90={q[3]:.2f} "
              f"min={np.nanmin(b):.2f} max={np.nanmax(b):.2f} 样本={len(b)}")

analyze(OLD_ETF, "原池 ETF（宽基+旧行业）")
analyze(NEW_ETF, "新池 ETF（5只行业）")
