# -*- coding: utf-8 -*-
"""
sweep_trackA.py —— 主引擎优化研究 Track A 靶向网格（2026-08-26）
目标: 主引擎 OOS 年化 ≥3.5%（当前 v5.0 基线 2.70%/2.82%，根因=趋势交易组件 OOS 为负）

杠杆（全部 env 可控，不改 run_backtest.py 代码）:
  H1 BREADTH 校准:  BT_BREADTH_MIN ∈ {10,12,15(基线),18,20}
  H2 S1 抑制:       BT_S1DERATE=1 (S1建仓×0.5) / BT_VOL_GATE_B_THRESH=22 (扩闸门B多禁S1)
  H6 频率/波动闸门: BT_VOL_GATE_A_THRESH=12 / BT_VOL_MIN=12
  H3 个股通道:      BT_STOCK_GATE=65 (放宽个股独立门槛)
  H5 仓位放大器:    BT_F04_MULT=1.5 (仅当趋势组件翻正后有意义)

复用 sweep_runner.py 框架 + metrics.compute_all 统一口径。
"""
import os, sys, json, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PY = r"C:/Users/hanji/.workbuddy/binaries/python/envs/tre_backtest/Scripts/python.exe"
sys.path.insert(0, HERE)
import metrics as M

# (fix后缀, env覆盖) —— 基线在前，便于对照
CONFIGS = [
    ("base",        {}),
    # ---- H1 BREADTH 否决层校准 ----
    ("h1_b10",      {"BT_BREADTH_MIN": "10.0"}),
    ("h1_b12",      {"BT_BREADTH_MIN": "12.0"}),
    ("h1_b18",      {"BT_BREADTH_MIN": "18.0"}),
    ("h1_b20",      {"BT_BREADTH_MIN": "20.0"}),
    # ---- H2 S1 抑制 ----
    ("h2_s1d",      {"BT_S1DERATE": "1"}),
    ("h2_gb22",     {"BT_VOL_GATE_B_THRESH": "22.0"}),
    # ---- H6 频率/波动闸门 ----
    ("h6_ga12",     {"BT_VOL_GATE_A_THRESH": "12.0"}),
    ("h6_vm12",     {"BT_VOL_MIN": "12.0"}),
    ("h6_ga12_vm12",{"BT_VOL_GATE_A_THRESH": "12.0", "BT_VOL_MIN": "12.0"}),
    # ---- 组合 ----
    ("c1_b12_s1d",  {"BT_BREADTH_MIN": "12.0", "BT_S1DERATE": "1"}),
    ("c2_s1d_ga12", {"BT_S1DERATE": "1", "BT_VOL_GATE_A_THRESH": "12.0", "BT_VOL_MIN": "12.0"}),
    ("c3_full",     {"BT_BREADTH_MIN": "12.0", "BT_S1DERATE": "1", "BT_VOL_GATE_A_THRESH": "12.0", "BT_VOL_MIN": "12.0"}),
    ("c3_f05",      {"BT_BREADTH_MIN": "12.0", "BT_S1DERATE": "1", "BT_VOL_GATE_A_THRESH": "12.0", "BT_VOL_MIN": "12.0", "BT_F04_MULT": "1.5"}),
    # ---- H3 个股通道放宽 ----
    ("h3_stock65",  {"BT_STOCK_GATE": "65.0"}),
]


def run_one(fix, env):
    e = dict(os.environ)
    e.update(env)
    e["BT_OUTFIX"] = fix
    print(f"=== [{fix}] env={env} 开始回测 ===", flush=True)
    t0 = __import__("time").time()
    subprocess.run([PY, "run_backtest.py"], env=e, cwd=HERE, check=True)
    dt = __import__("time").time() - t0
    suffix = f"_{fix}"
    rin = json.load(open(os.path.join(M.OUT, f"results_in{suffix}.json"), encoding="utf-8"))
    roos = json.load(open(os.path.join(M.OUT, f"results_oos{suffix}.json"), encoding="utf-8"))
    bench = M.load_bench()
    bench_oos = M.load_bench(start=roos["hist"][0]["date"])
    r_in = M.compute_all(rin, bench, "IS", 72.0)
    r_oos = M.compute_all(roos, bench_oos, "OOS", 18.0)
    rec = {
        "fix": fix, "env": env,
        "IS_ann": round(r_in["ann_return"], 3), "IS_mdd": round(r_in["max_drawdown"], 3),
        "IS_trades": r_in["n_buys"], "IS_etf_ann": round(r_in.get("etf_ann", float("nan")), 3),
        "IS_cash_ann": round(r_in.get("cash_contrib_ann", float("nan")), 3),
        "OOS_ann": round(r_oos["ann_return"], 3), "OOS_mdd": round(r_oos["max_drawdown"], 3),
        "OOS_trades": r_oos["n_buys"], "OOS_etf_ann": round(r_oos.get("etf_ann", float("nan")), 3),
        "OOS_cash_ann": round(r_oos.get("cash_contrib_ann", float("nan")), 3),
        "OOS_avg_pnl": round(r_oos.get("avg_pnl_pct", float("nan")), 3),
        "OOS_freq": round(r_oos.get("freq_annual", float("nan")), 3),
        "OOS_sharpe": round(r_oos.get("sharpe", float("nan")), 3),
        "OOS_win": round(r_oos.get("win_rate", float("nan")), 3),
        "secs": round(dt, 1),
    }
    print(f"=== [{fix}] OOS_ann={rec['OOS_ann']}% OOS_etf_ann={rec['OOS_etf_ann']}% "
          f"OOS_mdd={rec['OOS_mdd']}% OOS_trades={rec['OOS_trades']} ({dt:.0f}s) ===", flush=True)
    return rec


def main():
    results = []
    for fix, env in CONFIGS:
        results.append(run_one(fix, env))
    with open(os.path.join(M.OUT, "sweep_trackA.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    # 汇总表
    print("\n===== Track A 汇总（验收: OOS_ann≥3.5 且 OOS>IS 且 mdd≤12 且 freq≥6）=====", flush=True)
    hdr = f"{'fix':<14}{'OOS_ann':>9}{'OOS_etf':>9}{'IS_ann':>8}{'OOS_mdd':>8}{'trd':>5}{'freq':>6}{'sharpe':>8}{'win%':>7}"
    print(hdr, flush=True)
    for r in results:
        ok = (r["OOS_ann"] >= 3.5 and r["OOS_ann"] > r["IS_ann"] and r["OOS_mdd"] <= 12
              and r["OOS_trades"] >= 6)
        tag = " <<<PASS" if ok else ""
        print(f"{r['fix']:<14}{r['OOS_ann']:>9}{r['OOS_etf_ann']:>9}{r['IS_ann']:>8}"
              f"{r['OOS_mdd']:>8}{r['OOS_trades']:>5}{r['OOS_freq']:>6}{r['OOS_sharpe']:>8}{r['OOS_win']:>7}{tag}", flush=True)
    print("ALL_TRACKA_DONE", flush=True)


if __name__ == "__main__":
    main()
