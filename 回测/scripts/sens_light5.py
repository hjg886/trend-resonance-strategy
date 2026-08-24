# -*- coding: utf-8 -*-
"""
第5灯敏感性 —— 放宽"近90日破位≤K"后, 新ETF可买日数变化 (样本内2019-01-02~2024-12-31)
口径: 与引擎建仓管线一致(层级1/RPS60≥30/TRE状态/得分门槛[分状态]/七灯其余灯/MIN/流动性)
    仅第5灯阈值 K 变化; 得分门槛用 S1=70 S2=75 OBS=72 (B7r参数)
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

# TRE 状态序列 (V1)
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

def buyable_days(code, K5):
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
        # 层级1
        ok1, _ = S.layer1_etf(row.to_dict(), product_ok=True, amount_min=3000e4)
        if not ok1:
            continue
        if rps < 30:
            continue
        # 得分门槛（分状态简化: S2占多数, 用S2_GATE=75; S1用70; obs/S3用72）
        if st == "S2":
            if sc < bt.S2_GATE: continue
        elif st == "S1":
            if sc < bt.SCORE_GATE: continue
        else:
            if sc < bt.OBS_GATE: continue
        # 七灯其余灯: 第1灯(非硬fail) 第4灯 dev>0 第5灯 ma60b90<=K5 第7灯 beta<1.2
        dev = float(row.get("DEV60", -999))
        if dev <= 0:
            continue
        m90 = row.get("ma60_break90", 99)
        if not np.isfinite(m90) or m90 > K5:
            continue
        beta = float(row.get("BETA60", 100)) / 100.0  # BETA60 百分比化
        if beta >= 1.2:
            continue
        # MIN>0 + 流动性
        mn_row = row.to_dict(); mn_row["R"] = 0.0
        min_pct, _ = S.min_nine(mn_row, st, False, st == "S3", None, 1.0)
        if min_pct <= 0:
            continue
        if float(row.get("amount20", 0)) < 3e7:
            continue
        cnt += 1
        if len(detail) < 3:
            detail.append(f"{t1} S{st} sc={sc:.0f} rps={rps:.0f} dev={dev:.0f} b90={m90}")
    return cnt, detail

print(f"{'代码':<8}{'名称':<12}" + "".join(f"{'K='+str(k):>9}" for k in [1, 2, 3, 5]) + "   示例(K=3)")
for code in NEW_ETFS:
    row_out = []
    det = []
    for k in [1, 2, 3, 5]:
        c, d = buyable_days(code, k)
        row_out.append(c)
        if k == 3:
            det = d
    print(f"{code:<8}{bt.UNIVERSE[code][1]:<12}" + "".join(f"{c:>9}" for c in row_out) + f"   {det[:2]}")
