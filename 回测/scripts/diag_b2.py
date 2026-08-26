# -*- coding: utf-8 -*-
"""diag_b2.py —— 诊断 B2 评分为何 0 建仓：对比 V1 与 B2 在 OOS 窗口 ETF 评分分布"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import run_backtest as R
import scoring as S

panels, fins = R.load_all()
panels = R.build_panels(panels)

# OOS 窗口: 2025-01-02 ~ 2026-06-30
oos_start = pd.Timestamp("2025-01-02")
oos_end = pd.Timestamp("2026-06-30")

etf_codes = [c for c, (dn, nm, pt, ind) in R.UNIVERSE.items() if pt.startswith("etf")]

def scan(b2_on):
    os.environ["BT_B2_ON"] = "1" if b2_on else "0"
    if b2_on:
        os.environ["BT_B2_EST_W"] = "25"; os.environ["BT_B2_VOL_W"] = "20"; os.environ["BT_B2_MOM_SCALE"] = "0.5"
    all_scores, ge70, ge75 = [], 0, 0
    for code in etf_codes:
        dn = R.UNIVERSE[code][0]
        p = panels[dn]
        seg = p[(pd.to_datetime(p.index) >= oos_start) & (pd.to_datetime(p.index) <= oos_end)]
        for d, row in seg.iterrows():
            sc = S.etf_score(row.to_dict(), est_pct=0.6, nav_pct=row.get("NAV_PCTL_120", 50.0))
            all_scores.append(sc)
            if sc >= 70: ge70 += 1
            if sc >= 75: ge75 += 1
    arr = np.array(all_scores)
    print(f"[BT_B2_ON={int(b2_on)}] n={len(arr)} score min={arr.min():.1f} p25={np.percentile(arr,25):.1f} "
          f"median={np.median(arr):.1f} p75={np.percentile(arr,75):.1f} max={arr.max():.1f} "
          f"#>=70={ge70}({ge70/len(arr)*100:.1f}%) #>=75={ge75}({ge75/len(arr)*100:.1f}%)")

scan(False)
scan(True)
