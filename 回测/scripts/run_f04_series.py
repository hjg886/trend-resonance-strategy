# -*- coding: utf-8 -*-
"""
F-04 仓位引擎专项验证（2026-08-18 H系列证伪后的下一主攻方向）
基线 G1r : R10门槛全开 + VOLGATE/S1CONFIRM/EP1TENOR/R9UNIV 全开, 无MA60门控（复用既有 results_G1r_*）
命题     : G1r 六年交易净PnL 仅 +9,679 元, 总收益96%来自现金——"单笔金额贡献"能否通过仓位放大撑起年化6%?
变体     : F04_MULT=1.5/2.0/3.0（target 金额倍率） + KELLY_CAP=0.40（凯利封顶放宽, 总仓位叠加空间）
验收标准 : 14A 口径（年建仓≥6笔 且 单笔期望>0 且 年化≥6% 且 回撤≤12%）——预期无法独立达标,
          核心产出="倍率→年化/回撤"权衡曲线, 定位回撤≤12%的最大可用倍率（进攻线模拟盘参数）
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

# (label, f04_mult, kelly_cap)
CONFIGS = [
    ("F04a", "1.5", "0.25"),   # 单笔金额×1.5
    ("F04b", "2.0", "0.25"),   # 单笔金额×2.0
    ("F04c", "3.0", "0.25"),   # 单笔金额×3.0（激进, 看回撤爆点）
    ("F04d", "2.0", "0.40"),   # 金额×2.0 + 凯利封顶0.40（单笔+总仓同放）
]


def run_one(label, f04_mult, kelly_cap):
    env = dict(os.environ,
               BT_SCORE_GATE="80", BT_OBS_GATE="85",
               BT_TRE_VARIANT="V1", BT_FIXL5="1", BT_R1="1", BT_R2="1", BT_R3="1",
               BT_KELLYMIN="1", BT_EP1BLOCK="1", BT_OBSGUARD="1",
               BT_VOLFILTER="0", BT_S1DERATE="0",
               BT_VOLGATE="1", BT_S1CONFIRM="1", BT_EP1TENOR="1",
               BT_R10GATES="1", BT_R9UNIV="1",
               BT_MA60GATE="0", BT_TIERGATE="0",
               BT_H1_S1NOETF="0", BT_H2_MINHOLD="0",
               BT_F04_MULT=f04_mult, BT_KELLY_CAP=kelly_cap)
    print(f"=== 运行 {label}: F04_MULT={f04_mult} KELLY_CAP={kelly_cap} ===", flush=True)
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
    # 交易净PnL（closed_in pnl 求和）
    pnl_amt = sum(float(c.get("pnl", 0)) for c in res_in["closed"])
    summary = {
        "config": {"label": label, "f04_mult": f04_mult, "kelly_cap": kelly_cap},
        "in": {"final": res_in["final_equity"], "buys": len(res_in["buys"]),
               "closed": len(res_in["closed"]), "obs_stats": res_in["obs_stats"],
               "gate_stats": res_in["gate_stats"], "univ_size": res_in["universe_size"],
               "pnl_amt": pnl_amt,
               "avg_cost": (sum(float(c.get("cost_basis", 0)) for c in res_in["closed"]) /
                            len(res_in["closed"]) if res_in["closed"] else 0)},
        "oos": {"final": res_oos["final_equity"], "buys": len(res_oos["buys"]),
                "closed": len(res_oos["closed"]), "obs_stats": res_oos["obs_stats"],
                "pnl_amt": sum(float(c.get("pnl", 0)) for c in res_oos["closed"])},
        "metrics_in": mi, "metrics_oos": mo,
        "buys_in": res_in["buys"], "buys_oos": res_oos["buys"],
        "closed_in": res_in["closed"], "closed_oos": res_oos["closed"],
        "stats_in": res_in["stats"],
    }
    with open(os.path.join(OUT, f"variant_{label}.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1, default=str)
    print(f"[OK] {label}: in_final={res_in['final_equity']:.0f} buys={len(res_in['buys'])}+{len(res_oos['buys'])} "
          f"| 年建仓={mi['freq_annual']:.1f} 期望={mi['avg_pnl_pct']:.2f}% 年化={mi['ann_return']:.2f}% "
          f"回撤={mi['max_drawdown']:.2f}% 夏普={mi['sharpe']:.2f} 胜率={mi['win_rate']:.1f}% "
          f"交易PnL={pnl_amt:+,.0f}元", flush=True)
    return summary


if __name__ == "__main__":
    results = {}
    for cfg in CONFIGS:
        s = run_one(*cfg)
        if s:
            results[cfg[0]] = s
    # G1r 对照（复用既有）
    g1_res = M.load_res("results_G1r_in.json")
    g1 = {"metrics_in": M.compute_all(g1_res, bench_in, "G1r-样本内", 72),
          "metrics_oos": M.compute_all(M.load_res("results_G1r_oos.json"), bench_oos, "G1r-样本外", 18),
          "in": {"buys": len(g1_res["buys"]), "closed": len(g1_res["closed"]),
                 "pnl_amt": sum(float(c.get("pnl", 0)) for c in g1_res["closed"])},
          "oos": {"buys": len(M.load_res("results_G1r_oos.json")["buys"]),
                  "closed": len(M.load_res("results_G1r_oos.json")["closed"])}}
    print("\n===== F-04 汇总（样本内, 6年） =====")
    print(f"{'配置':<8}{'倍率':>5}{'凯利':>6}{'建仓':>5}{'年建仓':>7}{'期望%':>8}{'年化%':>8}{'回撤%':>8}{'夏普':>6}{'交易PnL':>12}{'平均投入':>10}")
    rows = [("G1r", "1.0", "0.25", g1)] + [(l, cfg[1], cfg[2], results[l]) for l, *cfg in CONFIGS if l in results]
    for label, mult, kc, d in rows:
        m = d["metrics_in"]
        avg_cost = (sum(float(c.get("cost_basis", 0)) for c in M.load_res(f"results_{label}_in.json")["closed"]) /
                    max(len(M.load_res(f"results_{label}_in.json")["closed"]), 1)) if label != "G1r" else 0
        print(f"{label:<8}{mult:>5}{kc:>6}{m['n_buys']:>5}{m['freq_annual']:>7.1f}"
              f"{m['avg_pnl_pct']:>8.2f}{m['ann_return']:>8.2f}{m['max_drawdown']:>8.2f}{m['sharpe']:>6.2f}"
              f"{d['in'].get('pnl_amt', 0):>12,.0f}{avg_cost:>10,.0f}")
    print("\n===== 验收判定（样本内, 14A口径） =====")
    for label, mult, kc, d in rows:
        m = d["metrics_in"]
        checks = {
            "年建仓≥6笔": m["freq_annual"] >= 6.0,
            "单笔期望>0": (m["avg_pnl_pct"] == m["avg_pnl_pct"]) and m["avg_pnl_pct"] > 0,
            "年化≥6%": m["ann_return"] >= 6.0,
            "回撤≤12%": m["max_drawdown"] <= 12.0,
        }
        ok = all(checks.values())
        print(f"{label}: {'✅ 全部达标' if ok else '❌ 未达标'} " + " | ".join(
            f"{k}={'✓' if v else '✗'}" for k, v in checks.items()))
