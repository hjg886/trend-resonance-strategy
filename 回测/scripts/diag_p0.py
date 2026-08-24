# -*- coding: utf-8 -*-
"""
P0 重新设计诊断（任务#85）
1. TRE 状态机锁死诊断: 6年 raw_state 分布 / 名义状态分布 / S3判定参数敏感性
2. 得分分布诊断: 观察池 7 标的每日得分分位数 → 门槛标定依据
3. 转换表敏感性: S2→S3 确认天数 / S3 窗口参数 → 名义 S3 占比
"""
import os, sys, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from indicators import indicator_panel
from tre import raw_state, TreState, step_tre
from scoring import (build_financial_series, fin_at, stock_score, etf_score,
                     layer1_stock)

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data")
CORE_IDX = ["idx_hs300", "idx_sh", "idx_sz"]

UNIVERSE = {
    "600276": ("stk_600276", "恒瑞医药", "stock"),
    "603259": ("stk_603259", "药明康德", "stock"),
    "510300": ("etf_510300", "沪深300ETF", "etf_wide"),
    "159915": ("etf_159915", "创业板ETF", "etf_wide"),
    "588000": ("etf_588000", "科创50ETF", "etf_wide"),
    "512010": ("etf_512010", "医药ETF", "etf_ind"),
    "159928": ("etf_159928", "消费ETF", "etf_ind"),
}
CROSS_ASSETS = ["x_hstech", "x_nasdaq100", "x_gold"]
CASH_ETF = "etf_159650"


def load_csv(name):
    df = pd.read_csv(os.path.join(DATA, f"{name}.csv"), dtype={"date": str})
    df["date"] = df["date"].astype(str).str[:10]
    return df.set_index("date").sort_index()


def main():
    # ---------- 1. 状态机诊断 ----------
    panels = {nm: load_csv(nm) for nm in CORE_IDX + ["etf_159650"]}
    for nm in CROSS_ASSETS:
        try:
            panels[nm] = load_csv(nm)
        except FileNotFoundError:
            pass
    cal = panels["idx_hs300"].index
    for xa in CROSS_ASSETS:
        if xa in panels and not panels[xa].index.equals(cal):
            panels[xa] = panels[xa].reindex(cal).ffill()
    P = {nm: indicator_panel(df) for nm, df in panels.items()}

    days = list(cal)
    # 预热 + 样本内
    scan_days = [d for d in days if d >= "2018-06-01" and d <= "2024-12-31"]

    hs300 = P["idx_hs300"]
    ret_h = hs300["close"].pct_change()
    rows = []
    for i, d in enumerate(scan_days):
        if i < 65:
            continue
        core_adx = [P[x].loc[d, "ADX14"] for x in CORE_IDX]
        cross20 = float(hs300.loc[d, "CROSS20"])
        vol20 = float(ret_h.loc[:d].tail(20).std(ddof=1) * np.sqrt(252) * 100)
        rows.append({"date": d, "adx": core_adx, "cross": cross20, "vol": vol20,
                     "raw": raw_state(core_adx, cross20, vol20)})
    df = pd.DataFrame(rows).set_index("date")

    print("=" * 72)
    print("【诊断1】6年 raw_state 分布（2018-06 预热 + 2019-2024）")
    vc = df["raw"].value_counts()
    for s in ["S1", "S2", "S3", "S4"]:
        n = int(vc.get(s, 0))
        print(f"  raw {s}: {n:5d} 天  {n/len(df)*100:5.1f}%")
    # raw S3 连续段
    segs, cur = [], 0
    prev = None
    for v in df["raw"]:
        if v == "S3":
            cur += 1
        else:
            if cur > 0:
                segs.append(cur)
            cur = 0
    if cur > 0:
        segs.append(cur)
    print(f"  raw S3 连续段: {len(segs)} 段, 最长 {max(segs) if segs else 0} 天, 段长分布:",
          sorted(segs, reverse=True)[:15] if segs else [])

    # ---------- 2. 名义状态（现行转换表） ----------
    tre = TreState()
    state_hist = []
    for i, d in enumerate(scan_days):
        if i < 65:
            continue
        r = df.loc[d]
        below_streak = float((hs300["close"] < hs300["MA60"]).loc[d] * 1.0)  # 简化
        # 实际连续天数
        below = (hs300["close"] < hs300["MA60"]).astype(int).loc[:d]
        streak = 0
        for v in below.iloc[::-1]:
            if v == 1:
                streak += 1
            else:
                break
        gt = bool(hs300.loc[d, "close"] > hs300.loc[d, "MA60"])
        step_tre(tre, i, r["adx"], r["cross"], r["vol"], float(streak), gt)
        state_hist.append(tre.state)
    sh = pd.Series(state_hist, index=df.index)
    print("\n【诊断2】现行转换表 名义状态分布")
    vc2 = sh.value_counts()
    for s in ["S1", "S2", "S3", "S4"]:
        n = int(vc2.get(s, 0))
        print(f"  名义 {s}: {n:5d} 天  {n/len(sh)*100:5.1f}%")

    # ---------- 3. S3 窗口参数敏感性（raw 层面） ----------
    print("\n【诊断3】S3 判定窗口参数敏感性 → raw S3 频率")
    def raw_sens(vol_lo, vol_hi, cross_lo, cross_hi, adx_weak):
        n = 0
        for r in rows:
            na = sum(1 for a in r["adx"] if a < adx_weak)
            if na > 1 and cross_lo <= r["cross"] <= cross_hi and vol_lo <= r["vol"] <= vol_hi:
                n += 1
        return n / len(rows) * 100
    cfg = [
        ("基准 15-25/3-4/adx15",     15, 25, 3, 4, 15),
        ("波动率上界30",              15, 30, 3, 4, 15),
        ("穿越上界5",                 15, 25, 3, 5, 15),
        ("穿越3-5+波动率上界30",      15, 30, 3, 5, 15),
        ("穿越3-5+波动率15-35",       15, 35, 3, 5, 15),
        ("穿越2-5+波动率15-30",       15, 30, 2, 5, 15),
        ("穿越2-5+波动率15-35",       15, 35, 2, 5, 15),
        ("ADX弱阈值18",               15, 25, 3, 4, 18),
        ("ADX弱阈值18+穿越3-5+vol≤30", 15, 30, 3, 5, 18),
    ]
    for name, a, b, c, d_, e in cfg:
        print(f"  {name:<28} raw S3 = {raw_sens(a,b,c,d_,e):5.1f}%")

    # ---------- 4. 转换表敏感性：S2→S3 确认天数 1 日 vs 2 日 ----------
    print("\n【诊断4】S2→S3 确认天数敏感性（名义 S3 占比）")
    def sim_nominal(confirm_days, vol_hi=25, cross_hi=4, adx_weak=15):
        state = "S2"
        buf = 0
        hist = []
        for i, d in enumerate(scan_days):
            if i < 65:
                continue
            r = df.loc[d]
            na = sum(1 for a in r["adx"] if a < adx_weak)
            raw = raw_state(r["adx"], r["cross"], r["vol"])
            # 仅改 S2→S3 确认规则，其余照旧
            if state == "S1":
                if raw != "S1":
                    state = "S2"
            elif state == "S2":
                if raw == "S3":
                    buf += 1
                    if buf >= confirm_days:
                        state = "S3"; buf = 0
                else:
                    buf = 0
                    if raw == "S1":
                        if state == "S2":
                            state = "S1"  # 简化: S2→S1 连2日(此处简化为当日,仅观察S3)
            elif state == "S3":
                if raw == "S4":
                    state = "S4"
                elif raw == "S2":
                    state = "S2"
            elif state == "S4":
                if raw == "S3":
                    state = "S3"
                elif raw == "S2":
                    state = "S2"
            hist.append(state)
        hs = pd.Series(hist)
        return {s: float((hs == s).mean() * 100) for s in ["S1", "S2", "S3", "S4"]}

    for cd in [2, 1]:
        r_ = sim_nominal(cd)
        print(f"  S2→S3 确认 {cd} 日: 名义 S1={r_['S1']:4.1f}% S2={r_['S2']:4.1f}% "
              f"S3={r_['S3']:4.1f}% S4={r_['S4']:4.1f}%")

    # ---------- 5. 得分分布诊断 ----------
    print("\n【诊断5】观察池 7 标的得分分布（2019-2024, T-1收盘）")
    fins = {}
    with open(os.path.join(DATA, "financials.json"), encoding="utf-8") as fh:
        fins_json = json.load(fh)
    fins = {c: build_financial_series(fins_json, c) for c in ("600276", "603259")}

    # 构建全部面板（复用 run_backtest 的 build_panels 逻辑, 但独立实现简化）
    all_panels = {}
    for nm in CORE_IDX + [v[0] for v in UNIVERSE.values()] + [CASH_ETF]:
        try:
            all_panels[nm] = indicator_panel(load_csv(nm))
        except FileNotFoundError:
            continue
    # 简单 PB/PE 用财报
    for code, (dn, _, ptype) in UNIVERSE.items():
        if ptype != "stock":
            continue
        p = all_panels[dn]
        fin_df = fins[code]
        bps_l, eps_l = [], []
        for d in p.index:
            f = fin_at(fin_df, d)
            bps_l.append(f["bps"] if f and f.get("bps") else np.nan)
            eps_l.append(f["eps"] if f and f.get("eps") else np.nan)
        p["PB"] = p["close"] / pd.Series(bps_l, index=p.index)
        p["PE"] = p["close"] / pd.Series(eps_l, index=p.index)

    score_data = {code: [] for code in UNIVERSE}
    for d in scan_days:
        for code, (dn, _, ptype) in UNIVERSE.items():
            if d not in all_panels[dn].index:
                continue
            row = all_panels[dn].loc[d].copy()
            if ptype == "stock":
                f = fin_at(fins[code], d)
                fin = dict(f) if f else None
                if fin is not None:
                    fin["price"] = row["close"]
                    if fin.get("eps") and np.isfinite(fin["eps"]) and fin["eps"] > 0:
                        fin["pe"] = row["close"] / fin["eps"]
                    if fin.get("bps") and np.isfinite(fin["bps"]) and fin["bps"] > 0:
                        fin["pb"] = row["close"] / fin["bps"]
                hist_pb = all_panels[dn]["PB"].dropna()
                hist_pe = all_panels[dn]["PE"].dropna()
                hpb = [x for x in hist_pb[hist_pb.index < d].tail(120).tolist() if np.isfinite(x)]
                hpe = [x for x in hist_pe[hist_pe.index < d].tail(120).tolist() if np.isfinite(x)]
                sc = stock_score(row, fin, hpb, hpe)
            else:
                sc = etf_score(row, est_pct=0.6)
            score_data[code].append(sc)

    all_scores = []
    for code, (dn, name, ptype) in UNIVERSE.items():
        s = np.array(score_data[code])
        if len(s) == 0:
            continue
        q = np.percentile(s, [5, 25, 50, 75, 90, 95])
        print(f"  {code} {name:<6} n={len(s):5d}  p5={q[0]:5.1f} p25={q[1]:5.1f} "
              f"med={q[2]:5.1f} p75={q[3]:5.1f} p90={q[4]:5.1f} p95={q[5]:5.1f}")
        all_scores.extend(s.tolist())
    as_ = np.array(all_scores)
    q = np.percentile(as_, [25, 50, 75, 90, 95])
    print(f"  全部合并 n={len(as_)}  p25={q[0]:.1f} med={q[1]:.1f} p75={q[2]:.1f} "
          f"p90={q[3]:.1f} p95={q[4]:.1f}  >=80分占比={(as_>=80).mean()*100:.2f}%")
    # 得分 ≥ 各门槛的标的-日数
    for g in [70, 75, 80, 85]:
        n_g = int((as_ >= g).sum())
        print(f"  score>={g}: {n_g} 标的天 ({n_g/len(as_)*100:.2f}%)")


if __name__ == "__main__":
    main()
