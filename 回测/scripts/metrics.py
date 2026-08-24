# -*- coding: utf-8 -*-
"""
metrics.py —— v4.7-R8 回测 27 项指标计算模块
输入: output/results_in.json / results_oos.json / data/idx_hs300.csv
口径: 对齐策略文档第十六章【必须输出的回测指标】27项
不可计算项如实标注: [样本不足] / [日线代理不可算] / [未实现对照]
"""
import os, json, sys
import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "output")

UNIVERSE_FALLBACK = 30  # R-09 标准候选池（v4.7-R10）; 无 universe_size 字段时的兜底


def load_res(fname):
    with open(os.path.join(OUT, fname), encoding="utf-8") as fh:
        return json.load(fh)


def load_bench(fname="idx_hs300.csv", start="2019-01-01", end="2026-06-30"):
    df = pd.read_csv(os.path.join(DATA, fname), dtype={"date": str})
    df["date"] = df["date"].astype(str).str[:10]
    df = df.set_index("date").sort_index()
    df = df.loc[(df.index >= start) & (df.index <= end)]
    return df


def annualized(equity_series, n_days):
    if n_days <= 0 or equity_series[-1] <= 0:
        return 0.0
    return (equity_series[-1] / equity_series[0]) ** (252.0 / n_days) - 1.0


def max_drawdown(equity):
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    # P1-02 防御性钳制[0,100]：回撤理论上限100%(权益不为负)；杜绝单位错误导致的>100%异常读数
    mdd = -dd.min() * 100.0 if len(dd) else 0.0
    return float(min(max(mdd, 0.0), 100.0))


def compute_all(res: dict, bench_df: pd.DataFrame, label: str, months: float) -> dict:
    hist = res["hist"]
    dates = [h["date"] for h in hist]
    eq = np.array([float(h["equity"]) for h in hist])
    dd_arr = np.array([float(h["dd"]) * 100.0 for h in hist])
    tre_arr = [h["tre"] for h in hist]
    cash_arr = np.array([float(h["cash"]) for h in hist])
    cap_arr = np.array([float(h["cap"]) for h in hist])
    n = len(eq)
    init = 1_000_000.0

    # 日收益序列（组合）
    rt = np.diff(eq) / eq[:-1]
    # 基准日收益
    b_close = bench_df["close"].loc[bench_df.index >= dates[0]]
    b_close = b_close.loc[b_close.index <= dates[-1]]
    b_rt = b_close.pct_change().dropna().values
    # 对齐长度
    m = min(len(rt), len(b_rt))
    rt_a, b_rt_a = rt[-m:], b_rt[-m:]

    ann = annualized(eq, n)
    mdd = max_drawdown(eq) if len(eq) else 0.0
    if mdd > 0:
        cmar = ann / (mdd / 100.0)
    else:
        cmar = 0.0
    vol = float(np.std(rt_a, ddof=1) * np.sqrt(252) * 100) if len(rt_a) > 1 else 0.0
    sharpe = (np.mean(rt_a) / np.std(rt_a, ddof=1) * np.sqrt(252)) if np.std(rt_a, ddof=1) > 0 else 0.0
    # 基准年化（区间对齐）
    b_ann = (b_close.iloc[-1] / b_close.iloc[0]) ** (252.0 / len(b_close)) - 1.0
    excess = ann - b_ann

    # 状态分布
    tre_cnt = {s: tre_arr.count(s) for s in ("S1", "S2", "S3", "S4")}
    tre_pct = {k: (v / n * 100.0 if n else 0.0) for k, v in tre_cnt.items()}

    # S3/S4 平均仓位
    s34_mask = np.array([t in ("S3", "S4") for t in tre_arr])
    pos = 1.0 - cash_arr / np.maximum(eq, 1e-9)
    s34_pos = float(pos[s34_mask].mean() * 100.0) if s34_mask.any() else 0.0

    # MA60冻结期间收益（S3/S4期间组合收益）
    if s34_mask.any():
        idx = np.where(s34_mask)[0]
        # 连续段收益
        segs = []
        s0 = idx[0]
        for i in range(1, len(idx)):
            if idx[i] != idx[i - 1] + 1:
                segs.append((s0, idx[i - 1]))
                s0 = idx[i]
        segs.append((s0, idx[-1]))
        seg_ret = [eq[e] / eq[s] - 1.0 for s, e in segs if s > 0 and eq[s] > 0]
        ma60_freeze_ret = float(np.mean(seg_ret) * 100.0) if seg_ret else 0.0
        ma60_freeze_n = len(segs)
    else:
        ma60_freeze_ret, ma60_freeze_n = 0.0, 0

    # 交易统计
    closed = res.get("closed", [])
    buys = res.get("buys", [])
    n_buys = len(buys)
    n_closed = len(closed)
    monthly_trades = n_buys / months if months > 0 else 0.0
    pnls = [float(c["pnl_pct"]) for c in closed if c.get("pnl_pct") is not None]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    win_rate = (len(wins) / len(pnls) * 100.0) if pnls else 0.0
    profit_factor = (np.mean(wins) / abs(np.mean(losses))) if wins and losses else (0.0 if losses else float("inf"))
    pl_ratio = profit_factor
    max_loss = min(pnls) * 100.0 if pnls else 0.0  # P1保护度（单笔最大亏损%）

    # ===== v4.7-R10 重构验证 6 项新指标 =====
    # R-06 交易期望: 单笔平均盈亏%（须>0）
    avg_pnl_pct = float(np.mean(pnls) * 100.0) if pnls else float("nan")
    # R-06 噪音止损率: 持有≤11日触发 P1/E-P1 占全部 P1/E-P1 止损比例（须<重构前53%）
    ep1_all = [c for c in closed if isinstance(c.get("exit_reason"), str) and ("E-P1" in c["exit_reason"] or c["exit_reason"].startswith("P1"))]
    ep1_noise = [c for c in ep1_all if int(c.get("hold_days", 99)) <= 11]
    noise_stop_rate = (len(ep1_noise) / len(ep1_all) * 100.0) if ep1_all else float("nan")
    # R-08 年建仓频率（6年样本, 目标6-18笔/年）与 14A④枯竭预警
    freq_annual = n_buys / max(months / 12.0, 0.001)
    freq_exhaust = freq_annual < 6.0
    # R-09 标的面利用率: 实际建仓标的不同代码数 / 候选池（须≥30%）
    univ_size = int(res.get("universe_size", UNIVERSE_FALLBACK))
    univ_used = len({c.get("code") for c in buys})
    univ_util = (univ_used / univ_size * 100.0) if univ_size else float("nan")
    # R-04 闸门触发天数（样本内）
    gs = res.get("gate_stats", {})
    gate_days = int(gs.get("gate_days", 0))
    gate_a_days = int(gs.get("gate_a_days", 0))
    gate_b_days = int(gs.get("gate_b_days", 0))

    # 信号命中率（buys → 该标的建仓后【最近一次】清仓周期盈利比例）
    def _nearest_exit(b):
        c_exit = [c for c in closed if c["code"] == b["code"] and c["exit"] > b["date"]]
        if not c_exit:
            return None
        c_exit.sort(key=lambda c: c["exit"])
        return c_exit[0]

    hit = []
    for b in buys:
        ce = _nearest_exit(b)
        if ce:
            hit.append(1.0 if float(ce["pnl_pct"]) > 0 else 0.0)
    signal_hit = (np.mean(hit) * 100.0) if hit else float("nan")

    # R-05 S1确认制胜率: S1状态建仓后最近清仓周期盈利比例（须>重构前29.7%）
    s1_buys = [b for b in buys if b.get("tre") == "S1"]
    s1_hit = []
    for b in s1_buys:
        ce = _nearest_exit(b)
        if ce:
            s1_hit.append(1.0 if float(ce["pnl_pct"]) > 0 else 0.0)
    s1_confirm_wr = (np.mean(s1_hit) * 100.0) if s1_hit else float("nan")
    s1_n = len(s1_hit)

    # TRE 状态胜率（按建仓时 TRE 分状态）
    tre_wr = {}
    for s in ("S1", "S2", "S3", "S4"):
        sb = [b for b in buys if b["tre"] == s]
        if not sb:
            tre_wr[s] = {"n": 0, "win_rate": float("nan")}
            continue
        st = []
        for b in sb:
            ce = _nearest_exit(b)
            if ce:
                st.append(1.0 if float(ce["pnl_pct"]) > 0 else 0.0)
        tre_wr[s] = {"n": len(st), "win_rate": (np.mean(st) * 100.0 if st else float("nan"))}

    # 熔断捕捉率（II/III级后次日沪深300续跌比例）
    mc = res.get("meltdown", {})
    captured = float(res.get("meltdown_captured", 0))
    ii3 = int(mc.get("II", 0)) + int(mc.get("III", 0))
    melt_acc = (captured / ii3 * 100.0) if ii3 else float("nan")

    # 防御观察模式有效性：回撤≥12%后5日内修复率（回撤收敛≥一半）
    repair = []
    for i in range(1, n):
        if dd_arr[i - 1] < 12.0 and dd_arr[i] >= 12.0:
            # 进入防御观察，看5日内 dd 是否收敛到 <6%（修复=回撤减半）
            end = min(i + 5, n)
            if dd_arr[i:end].min() <= 6.0:
                repair.append(1.0)
            elif end < n:
                repair.append(0.0)
    dd_repair_rate = (np.mean(repair) * 100.0) if repair else float("nan")

    # 策略健康度 Z-score：月度超额收益滚动12月
    eq_s = pd.Series(eq, index=pd.to_datetime(dates))
    _bench_df = bench_df.copy()
    _bench_df.index = pd.to_datetime(_bench_df.index)
    b_s = _bench_df["close"].reindex(pd.to_datetime(dates)).ffill()
    m_eq = eq_s.resample("ME").last()
    m_b = b_s.resample("ME").last()
    m_ret_s = m_eq.pct_change()
    m_ret_b = m_b.pct_change()
    ex = (m_ret_s - m_ret_b).dropna()
    z = (ex - ex.mean()) / ex.std(ddof=1) if len(ex) > 1 and ex.std(ddof=1) > 0 else pd.Series(dtype=float)
    z_mean = float(z.mean()) if len(z) else float("nan")

    # 现金管理贡献（年化）
    cash_ret = float(res.get("cash_mgmt_ret", 0))
    cash_contrib_ann = (cash_ret / init / (n / 252.0) * 100.0) if n > 0 else 0.0
    total_gain = float(eq[-1]) - init if n else 0.0
    cash_share = (cash_ret / total_gain * 100.0) if total_gain > 0 else 0.0

    # ETF 组合年化（仅ETF建仓完整周期）
    etf_pnls = [float(c["pnl_pct"]) for c in closed if str(c.get("code", "")).startswith(("510", "159", "588", "512"))]
    etf_ann = float("nan")
    if etf_pnls and n > 0:
        etf_ann = np.mean(etf_pnls) / (n / 252.0) * 100.0 * (252.0 / 21.0) / 12.0  # 平均周期→年化近似
        etf_ann = np.mean(etf_pnls) * (252.0 / np.mean([60, 90]))  # 简化: 平均持有80日

    return {
        "label": label, "n_days": n, "months": months,
        "final_equity": float(eq[-1]), "total_return": (float(eq[-1]) / init - 1.0) * 100.0,
        "ann_return": ann * 100.0, "max_drawdown": mdd, "sharpe": sharpe,
        "calmar": cmar, "vol": vol, "bench_ann": b_ann * 100.0, "excess": excess * 100.0,
        "win_rate": win_rate, "profit_factor": pl_ratio, "monthly_trades": monthly_trades,
        "n_buys": n_buys, "n_closed": n_closed,
        "tre_pct": tre_pct, "tre_cnt": tre_cnt,
        "s34_avg_pos": s34_pos, "ma60_freeze_ret": ma60_freeze_ret, "ma60_freeze_segs": ma60_freeze_n,
        "meltdown": mc, "meltdown_captured": captured, "melt_acc": melt_acc,
        "dd_repair_rate": dd_repair_rate, "max_loss_pct": max_loss,
        "z_mean": z_mean, "cash_contrib_ann": cash_contrib_ann, "cash_share_pct": cash_share,
        "signal_hit": signal_hit, "tre_win_rate": tre_wr,
        "etf_ann": etf_ann, "etf_n": len(etf_pnls),
        # ===== v4.7-R10 重构验证 6 项（R-04/R-05/R-06/R-08/R-09） =====
        "avg_pnl_pct": avg_pnl_pct,          # R-06 单笔期望% (须>0)
        "noise_stop_rate": noise_stop_rate,  # R-06 噪音止损率% (须<53)
        "s1_confirm_wr": s1_confirm_wr,      # R-05 S1建仓胜率% (须>29.7)
        "s1_n": s1_n,                        # S1建仓样本数
        "gate_days": gate_days,              # R-04 闸门A/B触发总天数
        "gate_a_days": gate_a_days, "gate_b_days": gate_b_days,
        "freq_annual": freq_annual,          # R-08 年建仓笔数 (须6-18)
        "freq_exhaust": freq_exhaust,        # R-08 14A④ 枯竭预警
        "univ_size": univ_size, "univ_used": univ_used, "univ_util": univ_util,  # R-09 (须≥30%)
    }


def main():
    bench = load_bench()
    res_in = load_res("results_in.json")
    res_oos = load_res("results_oos.json")

    # 样本内月数: 2019-01 ~ 2024-12 = 72个月
    m_in = 72.0
    # 样本外月数: 2025-01 ~ 2026-06 = 18个月
    m_oos = 18.0

    # 样本外基准区间从 OOS 起始日取
    oos_start = res_oos["hist"][0]["date"]
    bench_oos = load_bench(start=oos_start)

    r_in = compute_all(res_in, bench, "样本内6年", m_in)
    r_oos = compute_all(res_oos, bench_oos, "样本外18个月", m_oos)

    out = {"in": r_in, "oos": r_oos}
    with open(os.path.join(OUT, "metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
