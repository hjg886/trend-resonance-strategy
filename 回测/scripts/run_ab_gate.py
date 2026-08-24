# -*- coding: utf-8 -*-
"""
阶段1 A/B: 建仓时机门控对比 —— MA60二元 vs 三级分级（路径A，2026-08-18）
对照组 G-BIN : G1r完整配置 + BT_MA60GATE=1（沪深300收盘≤MA60 禁一切建仓）
实验组 G-TIER: G1r完整配置 + BT_TIERGATE=1（FULL/HALF/NONE 三窗；HALF=仅S3+观察通道5折）
基准配置对齐 G1r: score80/obs85, V1, 全部修复开关开, VOLGATE/S1CONFIRM/EP1TENOR/R10GATES/R9UNIV 全开
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

# (label, ma60gate, tiergate)
CONFIGS = [
    ("G-BIN",  "1", "0"),   # 对照组: MA60二元门控
    ("G-TIER", "0", "1"),   # 实验组: 三级分级门控
]


def run_one(label, ma60gate, tiergate):
    env = dict(os.environ,
               BT_SCORE_GATE="80", BT_OBS_GATE="85",
               BT_TRE_VARIANT="V1", BT_FIXL5="1", BT_R1="1", BT_R2="1", BT_R3="1",
               BT_KELLYMIN="1", BT_EP1BLOCK="1", BT_OBSGUARD="1",
               BT_VOLFILTER="0", BT_S1DERATE="0",
               BT_VOLGATE="1", BT_S1CONFIRM="1", BT_EP1TENOR="1",
               BT_R10GATES="1", BT_R9UNIV="1",
               BT_MA60GATE=ma60gate, BT_TIERGATE=tiergate)
    print(f"=== 运行 {label}: MA60GATE={ma60gate} TIERGATE={tiergate} ===", flush=True)
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
        "config": {"label": label, "ma60gate": ma60gate, "tiergate": tiergate},
        "in": {"final": res_in["final_equity"], "buys": len(res_in["buys"]),
               "closed": len(res_in["closed"]), "obs_stats": res_in["obs_stats"],
               "gate_stats": res_in["gate_stats"], "win_stats": res_in.get("win_stats", {}),
               "univ_size": res_in["universe_size"]},
        "oos": {"final": res_oos["final_equity"], "buys": len(res_oos["buys"]),
                "closed": len(res_oos["closed"]), "obs_stats": res_oos["obs_stats"],
                "win_stats": res_oos.get("win_stats", {})},
        "metrics_in": mi, "metrics_oos": mo,
        "buys_in": res_in["buys"], "buys_oos": res_oos["buys"],
        "closed_in": res_in["closed"], "closed_oos": res_oos["closed"],
        "stats_in": res_in["stats"],
    }
    with open(os.path.join(OUT, f"variant_{label}.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1, default=str)
    # HALF窗建仓明细（实验组关键证据）
    if tiergate == "1":
        half_buys = [b for b in res_in["buys"] if b.get("win") == "HALF"]
        print(f"  [HALF窗] 样本内 HALF 建仓 {len(half_buys)} 笔")
        for b in half_buys[:30]:
            print(f"    {b['date']} {b['code']} {b['reason']} score={b['score']:.0f} target={b['target']:.1f}% tre={b['tre']}")
    print(f"[OK] {label}: in_final={res_in['final_equity']:.0f} buys={len(res_in['buys'])}+{len(res_oos['buys'])} "
          f"| 年建仓={mi['freq_annual']:.1f} 期望={mi['avg_pnl_pct']:.2f}% 年化={mi['ann_return']:.2f}% "
          f"回撤={mi['max_drawdown']:.2f}% 夏普={mi['sharpe']:.2f} 胜率={mi['win_rate']:.1f}% "
          f"窗口={res_in.get('win_stats', {})}", flush=True)
    return summary


if __name__ == "__main__":
    results = {}
    for cfg in CONFIGS:
        s = run_one(*cfg)
        if s:
            results[cfg[0]] = s
    print("\n===== A/B 汇总（样本内） =====")
    print(f"{'配置':<8}{'建仓':>5}{'年建仓':>7}{'期望%':>8}{'年化%':>8}{'回撤%':>8}{'夏普':>6}{'胜率%':>7}"
          f"{'超额%':>8}{'FULL':>5}{'HALF':>5}{'NONE':>5}")
    for label, *_ in CONFIGS:
        if label not in results:
            continue
        s = results[label]
        m = s["metrics_in"]
        w = s["in"]["win_stats"]
        print(f"{label:<8}{m['n_buys']:>5}{m['freq_annual']:>7.1f}"
              f"{m['avg_pnl_pct']:>8.2f}{m['ann_return']:>8.2f}{m['max_drawdown']:>8.2f}{m['sharpe']:>6.2f}"
              f"{m['win_rate']:>7.1f}{m['excess']:>8.2f}"
              f"{w.get('win_full',0):>5}{w.get('win_half',0):>5}{w.get('win_none',0):>5}")
    print("\n===== 验收判定（样本内, 14A口径） =====")
    for label, *_ in CONFIGS:
        if label not in results:
            continue
        m = results[label]["metrics_in"]
        checks = {
            "年建仓≥6笔": m["freq_annual"] >= 6.0,
            "单笔期望>0": (m["avg_pnl_pct"] == m["avg_pnl_pct"]) and m["avg_pnl_pct"] > 0,
            "年化≥6%": m["ann_return"] >= 6.0,
            "回撤≤12%": m["max_drawdown"] <= 12.0,
        }
        ok = all(checks.values())
        print(f"{label}: {'✅ 全部达标' if ok else '❌ 未达标'} " + " | ".join(
            f"{k}={'✓' if v else '✗'}" for k, v in checks.items()))
