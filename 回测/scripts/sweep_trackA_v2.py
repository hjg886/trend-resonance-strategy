# -*- coding: utf-8 -*-
"""
sweep_trackA_v2.py —— Track A 稳健版（resume + 容错）
- 已有 results_in/out_{fix}.json 直接复用（不重跑）
- 任一配置失败不影响其他配置，最后强制写出已完成的 json
"""
import os, sys, json, subprocess, time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = r"C:/Users/hanji/.workbuddy/binaries/python/envs/tre_backtest/Scripts/python.exe"
sys.path.insert(0, HERE)
import metrics as M

CONFIGS = [
    ("base",        {}),
    ("h1_b10",      {"BT_BREADTH_MIN": "10.0"}),
    ("h1_b12",      {"BT_BREADTH_MIN": "12.0"}),
    ("h1_b18",      {"BT_BREADTH_MIN": "18.0"}),
    ("h1_b20",      {"BT_BREADTH_MIN": "20.0"}),
    ("h2_s1d",      {"BT_S1DERATE": "1"}),
    ("h2_gb22",     {"BT_VOL_GATE_B_THRESH": "22.0"}),
    ("h6_ga12",     {"BT_VOL_GATE_A_THRESH": "12.0"}),
    ("h6_vm12",     {"BT_VOL_MIN": "12.0"}),
    ("h6_ga12_vm12",{"BT_VOL_GATE_A_THRESH": "12.0", "BT_VOL_MIN": "12.0"}),
    ("c1_b12_s1d",  {"BT_BREADTH_MIN": "12.0", "BT_S1DERATE": "1"}),
    ("c2_s1d_ga12", {"BT_S1DERATE": "1", "BT_VOL_GATE_A_THRESH": "12.0", "BT_VOL_MIN": "12.0"}),
    ("c3_full",     {"BT_BREADTH_MIN": "12.0", "BT_S1DERATE": "1", "BT_VOL_GATE_A_THRESH": "12.0", "BT_VOL_MIN": "12.0"}),
    ("c3_f05",      {"BT_BREADTH_MIN": "12.0", "BT_S1DERATE": "1", "BT_VOL_GATE_A_THRESH": "12.0", "BT_VOL_MIN": "12.0", "BT_F04_MULT": "1.5"}),
    ("h3_stock65",  {"BT_STOCK_GATE": "65.0"}),
]


def have(fix):
    return (os.path.exists(os.path.join(M.OUT, f"results_in_{fix}.json")) and
            os.path.exists(os.path.join(M.OUT, f"results_oos_{fix}.json")))


def run_one(fix, env):
    if have(fix):
        print(f"=== [{fix}] 已有结果，resume 计算 ===", flush=True)
    else:
        e = dict(os.environ)
        e.update(env)
        e["BT_OUTFIX"] = fix
        print(f"=== [{fix}] env={env} 开始回测 ===", flush=True)
        t0 = time.time()
        subprocess.run([PY, "run_backtest.py"], env=e, cwd=HERE, check=True)
        print(f"  用时 {time.time()-t0:.0f}s", flush=True)
    rin = json.load(open(os.path.join(M.OUT, f"results_in_{fix}.json"), encoding="utf-8"))
    roos = json.load(open(os.path.join(M.OUT, f"results_oos_{fix}.json"), encoding="utf-8"))
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
    }
    print(f"=== [{fix}] OOS_ann={rec['OOS_ann']}% OOS_etf_ann={rec['OOS_etf_ann']}% "
          f"OOS_mdd={rec['OOS_mdd']}% OOS_trades={rec['OOS_trades']} ===", flush=True)
    return rec


def main():
    results = []
    for fix, env in CONFIGS:
        try:
            results.append(run_one(fix, env))
        except Exception as ex:
            import traceback
            print(f"!!! [{fix}] 失败: {ex}", flush=True)
            traceback.print_exc()
    with open(os.path.join(M.OUT, "sweep_trackA.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print("\n===== Track A 汇总（验收: OOS_ann≥3.5 且 OOS>IS 且 mdd≤12 且 freq≥6）=====", flush=True)
    print(f"{'fix':<14}{'OOS_ann':>9}{'OOS_etf':>9}{'IS_ann':>8}{'OOS_mdd':>8}{'trd':>5}{'freq':>6}{'sharpe':>8}{'win%':>7}", flush=True)
    for r in results:
        ok = (r["OOS_ann"] >= 3.5 and r["OOS_ann"] > r["IS_ann"] and r["OOS_mdd"] <= 12
              and r["OOS_trades"] >= 6)
        tag = " <<<PASS" if ok else ""
        print(f"{r['fix']:<14}{r['OOS_ann']:>9}{r['OOS_etf_ann']:>9}{r['IS_ann']:>8}"
              f"{r['OOS_mdd']:>8}{r['OOS_trades']:>5}{r['OOS_freq']:>6}{r['OOS_sharpe']:>8}{r['OOS_win']:>7}{tag}", flush=True)
    print(f"DONE {len(results)}/15 配置", flush=True)


if __name__ == "__main__":
    main()
