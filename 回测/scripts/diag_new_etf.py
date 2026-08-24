# -*- coding: utf-8 -*-
"""
新ETF建仓管线诊断 —— 定位5只新标的被哪道闸门拦截
复用 run_backtest 的 panels/评分/七灯/MIN, 逐日回放候选评估, 记录每个symbol的首次拦截分布
"""
import os, sys, json
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import run_backtest as bt
import tre as T
import scoring as S
from indicators import indicator_panel

NEW_ETFS = ["512880", "512690", "515030", "512480", "512170"]

panels0, fins = bt.load_all()
panels = bt.build_panels(panels0)

# 沪深300 指标 + TRE 状态机
hs = panels["idx_hs300"]
dates = hs.index
tre = T.TreState()
tre_log = []

# 预测状态序列（与 run_backtest 相同口径）
states = {}
for i, t1 in enumerate(dates):
    h = hs.loc[t1]
    core_adx = [panels[x].loc[t1, "ADX14"] for x in bt.CORE_IDX]
    cross20 = int(h["CROSS20"])
    hs300_ret = panels["idx_hs300"]["close"].pct_change().loc[:t1]
    vol20 = float(hs300_ret.tail(20).std(ddof=1) * np.sqrt(252) * 100)
    hs_below_streak = float(h["BELOW_STREAK"])
    hs_gt = bool(h["close"] > h["MA60"])
    T.step_tre(tre, i, core_adx, cross20, vol20, hs_below_streak, hs_gt,
               variant="V1")
    states[t1] = tre.state

# 逐日逐symbol评估
GATES = ["层级1", "RPS60<30", "R值C级", "TRE不可建仓", "得分门槛",
         "组合约束", "七灯", "MIN≤0", "ATR>8%", "流动性", "F04<3%", "风险预算", "总仓位", "行业>30%"]
per_sym = {c: {g: 0 for g in GATES} for c in NEW_ETFS}
per_sym_extra = {c: {"n_days": 0, "n_valid": 0, "score_ge75": 0, "score_ge72": 0,
                     "rps_ok": 0, "dev_ok": 0, "light4_fail": 0, "light5_fail": 0,
                     "light7_beta_fail": 0, "max_score": 0.0, "score_mean": 0.0,
                     "buyable": 0, "buyable_detail": []} for c in NEW_ETFS}

# 候选日期 = 引擎主循环同样日历（2019-01-02 起）
for i, t1 in enumerate(dates):
    if t1 < "2019-01-02":
        continue
    st = states[t1]
    obs_mode = tre.obs_active  # 简化: 用当日obs_active
    for code in NEW_ETFS:
        dn = bt.UNIVERSE[code][0]
        p = panels[dn]
        if t1 not in p.index:
            continue
        row = p.loc[t1]
        per_sym_extra[code]["n_days"] += 1
        # 指标可用性
        if not (np.isfinite(row.get("MA60", np.nan)) and np.isfinite(row.get("score_", np.nan) or 0) is False):
            pass
        # 评分
        sc = S.etf_score(row.to_dict(), est_pct=0.6)
        per_sym_extra[code]["n_valid"] += 1
        per_sym_extra[code]["score_mean"] += sc
        per_sym_extra[code]["max_score"] = max(per_sym_extra[code]["max_score"], sc)
        if sc >= 75: per_sym_extra[code]["score_ge75"] += 1
        if sc >= 72: per_sym_extra[code]["score_ge72"] += 1
        rps = float(row.get("RPS60", 50))
        if rps >= 30: per_sym_extra[code]["rps_ok"] += 1
        dev = float(row.get("DEV60", -999))
        if dev > 0: per_sym_extra[code]["dev_ok"] += 1
        if dev <= 0: per_sym_extra[code]["light4_fail"] += 1
        if np.isfinite(row.get("ma60_break90", 0)) and int(row.get("ma60_break90", 0)) > 1: per_sym_extra[code]["light5_fail"] += 1

        # ---- 管线回放（首个拦截）----
        gate = None
        # 层级1
        ok1, _ = S.layer1_etf(row.to_dict(), product_ok=True, amount_min=3000e4)
        if not ok1:
            gate = "层级1"
        # RPS
        if gate is None and rps < 30:
            gate = "RPS60<30"
        # TRE 建仓模式
        if gate is None:
            s3_mode = st == "S3" and not obs_mode
            s12_mode = st in ("S1", "S2") and not obs_mode
            if not (obs_mode or s3_mode or s12_mode):
                gate = "TRE不可建仓"
        # 得分门槛
        if gate is None:
            if obs_mode or s3_mode:
                if sc < bt.OBS_GATE:
                    gate = "得分门槛"
            elif st == "S2":
                if sc < bt.S2_GATE:
                    gate = "得分门槛"
            else:
                if sc < bt.SCORE_GATE:
                    gate = "得分门槛"
        # 组合约束
        if gate is None:
            n_hold = 0  # 简化: 忽略持仓约束（单独统计）
        # 七灯
        if gate is None:
            beta = float(row.get("BETA60", 100))
            ok7 = beta < 1.2
            if not ok7:
                per_sym_extra[code]["light7_beta_fail"] += 1
            ok_l = (dev > 0) and (np.isfinite(row.get("ma60_break90", 0)) and int(row.get("ma60_break90", 0)) <= 1) and ok7
            if not ok_l:
                gate = "七灯"
        # MIN
        if gate is None:
            mn_row = row.to_dict(); mn_row["R"] = 0.0
            min_pct, _ = S.min_nine(mn_row, st, obs_mode, st == "S3", None, 1.0)
            if min_pct <= 0:
                gate = "MIN≤0"
        # 流动性 / F04 等（简化: 用amount20）
        if gate is None:
            amt20 = float(row.get("amount20", 0))
            if amt20 < 3e7:
                gate = "流动性"
            else:
                per_sym_extra[code]["buyable"] += 1
                if len(per_sym_extra[code]["buyable_detail"]) < 5:
                    per_sym_extra[code]["buyable_detail"].append(
                        f"{t1} S{st} score={sc:.0f} rps={rps:.0f} dev={dev:.0f} ma60b90={int(row.get('ma60_break90',0))}")
        if gate:
            per_sym[code][gate] += 1

print(f"\n=== 新ETF建仓管线诊断 (样本内 2019-01-02~2024-12-31, variant=V1, gates 70/75/72) ===")
for c in NEW_ETFS:
    d = per_sym[c]; e = per_sym_extra[c]
    mean_sc = e["score_mean"] / max(e["n_valid"], 1)
    print(f"\n【{bt.UNIVERSE[c][1]} {c}】 有效评估日={e['n_valid']} "
          f"得分均值={mean_sc:.1f} 最高={e['max_score']:.1f} "
          f"≥75:{e['score_ge75']} ≥72:{e['score_ge72']}")
    print(f"  RPS60≥30:{e['rps_ok']} 站稳MA60(dev>0):{e['dev_ok']} "
          f"第4灯FAIL:{e['light4_fail']} 第5灯FAIL:{e['light5_fail']} Beta≥1.2:{e['light7_beta_fail']}")
    print(f"  理论可买日:{e['buyable']}  示例: {e['buyable_detail'][:3]}")
    print(f"  首次拦截分布: " + ", ".join(f"{g}={d[g]}" for g in GATES if d[g] > 0))
