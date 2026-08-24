# -*- coding: utf-8 -*-
"""
H系列: S1假信号定向修复组合回测（2026-08-18 阶段1归因落地）
基线 G1r : R10门槛全开 + VOLGATE/S1CONFIRM/EP1TENOR/R9UNIV 全开, 无MA60门控（复用既有 results_G1r_*）
H1      : G1r + S1常规建仓禁ETF（归因⑥: ETF亏/个股盈; S1追涨ETF被均值回归打穿）
H2      : G1r + S1常规建仓强制最短持有期11日（期间跳过P1/E-P1, E-P9/P4/P12/熔断仍生效）
H3      : H1+H2 组合
验收标准（14A）: 年建仓≥6笔 且 单笔期望>0 且 年化≥6% 且 回撤≤12%
"""
import os, sys, json, subprocess, shutil

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCRIPTS = os.path.dirname(__file__)
OUT = os.path.join(ROOT, "output")
PY = r"C:/Users/hanji/.workbuddy/binaries/python/envs/backtest/Scripts/python.exe"

sys.path.insert(0, SCRIPTS)
import metrics as M

bench_in = M.load_bench(start="2019-01-01", end="2024-12-31")
bench_oos = M.load_bench(start="2025-01-01", end="2026-06-30")

# (label, h1_s1noetf, h2_minhold)
CONFIGS = [
    ("H1", "1", "0"),   # S1 禁 ETF
    ("H2", "0", "1"),   # S1 强制持有期11日
    ("H3", "1", "1"),   # 组合
]


def run_one(label, h1, h2):
    env = dict(os.environ,
               BT_SCORE_GATE="80", BT_OBS_GATE="85",
               BT_TRE_VARIANT="V1", BT_FIXL5="1", BT_R1="1", BT_R2="1", BT_R3="1",
               BT_KELLYMIN="1", BT_EP1BLOCK="1", BT_OBSGUARD="1",
               BT_VOLFILTER="0", BT_S1DERATE="0",
               BT_VOLGATE="1", BT_S1CONFIRM="1", BT_EP1TENOR="1",
               BT_R10GATES="1", BT_R9UNIV="1",
               BT_MA60GATE="0", BT_TIERGATE="0",
               BT_H1_S1NOETF=h1, BT_H2_MINHOLD=h2)
    print(f"=== 运行 {label}: H1_S1NOETF={h1} H2_MINHOLD={h2} ===", flush=True)
    r = subprocess.run([PY, "run_backtest.py"], cwd=SCRIPTS, env=env,
                       capture_output=True, text=True, timeout=1200)
    if r.returncode != 0:
        print(f"[FAIL] {label}: {r.stderr[-3000:]}")
        print(r.stdout[-2000:])
        return None
    for seg in ("in", "oos"):
        src = os.path.join(OUT, f"results_{seg}.json")
        dst = os.path.join(OUT, f"results_{label}_{seg}.json")
        shutil.copy(src, dst)
    res_in = M.load_res(f"results_{label}_in.json")
    res_oos = M.load_res(f"results_{label}_oos.json")
    mi = M.compute_all(res_in, bench_in, f"{label}-样本内", 72)
    mo = M.compute_all(res_oos, bench_oos, f"{label}-样本外", 18)
    summary = {
        "config": {"label": label, "h1_s1noetf": h1, "h2_minhold": h2},
        "in": {"final": res_in["final_equity"], "buys": len(res_in["buys"]),
               "closed": len(res_in["closed"]), "obs_stats": res_in["obs_stats"],
               "gate_stats": res_in["gate_stats"], "univ_size": res_in["universe_size"]},
        "oos": {"final": res_oos["final_equity"], "buys": len(res_oos["buys"]),
                "closed": len(res_oos["closed"]), "obs_stats": res_oos["obs_stats"]},
        "metrics_in": mi, "metrics_oos": mo,
        "buys_in": res_in["buys"], "buys_oos": res_oos["buys"],
        "closed_in": res_in["closed"], "closed_oos": res_oos["closed"],
        "stats_in": res_in["stats"],
    }
    with open(os.path.join(OUT, f"variant_{label}.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1, default=str)
    print(f"[OK] {label}: in_final={res_in['final_equity']:.0f} buys={len(res_in['buys'])}+{len(res_oos['buys'])} "
          f"| 年建仓={mi['freq_annual']:.1f} 期望={mi['avg_pnl_pct']:.2f}% 年化={mi['ann_return']:.2f}% "
          f"回撤={mi['max_drawdown']:.2f}% 夏普={mi['sharpe']:.2f} 胜率={mi['win_rate']:.1f}%", flush=True)
    return summary


if __name__ == "__main__":
    results = {}
    for cfg in CONFIGS:
        s = run_one(*cfg)
        if s:
            results[cfg[0]] = s
    # G1r 对照（复用既有）
    g1 = {"metrics_in": M.compute_all(M.load_res("results_G1r_in.json"), bench_in, "G1r-样本内", 72),
          "metrics_oos": M.compute_all(M.load_res("results_G1r_oos.json"), bench_oos, "G1r-样本外", 18),
          "in": {"buys": len(M.load_res("results_G1r_in.json")["buys"]),
                 "closed": len(M.load_res("results_G1r_in.json")["closed"])},
          "oos": {"buys": len(M.load_res("results_G1r_oos.json")["buys"]),
                  "closed": len(M.load_res("results_G1r_oos.json")["closed"])}}
    print("\n===== H系列汇总（样本内） =====")
    print(f"{'配置':<8}{'建仓':>5}{'年建仓':>7}{'期望%':>8}{'年化%':>8}{'回撤%':>8}{'夏普':>6}{'胜率%':>7}{'超额%':>8}")
    for label, *_ in [("G1r",) * 2] + CONFIGS:
        if label == "G1r":
            m = g1["metrics_in"]
        elif label in results:
            m = results[label]["metrics_in"]
        else:
            continue
        print(f"{label:<8}{m['n_buys']:>5}{m['freq_annual']:>7.1f}"
              f"{m['avg_pnl_pct']:>8.2f}{m['ann_return']:>8.2f}{m['max_drawdown']:>8.2f}{m['sharpe']:>6.2f}"
              f"{m['win_rate']:>7.1f}{m['excess']:>8.2f}")
    print("\n===== 验收判定（样本内, 14A口径） =====")
    allc = [("G1r", g1["metrics_in"])] + [(l, results[l]["metrics_in"]) for l, *_ in CONFIGS if l in results]
    for label, m in allc:
        checks = {
            "年建仓≥6笔": m["freq_annual"] >= 6.0,
            "单笔期望>0": (m["avg_pnl_pct"] == m["avg_pnl_pct"]) and m["avg_pnl_pct"] > 0,
            "年化≥6%": m["ann_return"] >= 6.0,
            "回撤≤12%": m["max_drawdown"] <= 12.0,
        }
        ok = all(checks.values())
        print(f"{label}: {'✅ 全部达标' if ok else '❌ 未达标'} " + " | ".join(
            f"{k}={'✓' if v else '✗'}" for k, v in checks.items()))
