# -*- coding: utf-8 -*-
"""
v4.7-R10 重构后回测验证批次（G 系列）
  G0r: 回归对照 —— D6r 配置(12只池/70门槛/V1/全修复) + 重构开关全关（验证引擎改动零副作用）
  G1r: 完整 v4.7-R10 —— 30只池 + R-04双闸门 + R-05 S1确认制 + R-06止损分档 + R-10门槛(80/80/78/85)
  G2r: 门槛敏感性 —— G1 但门槛回退 P0-A(70/75/72)（隔离 R-10 门槛影响）
  G3r: R-05隔离 —— G1 关闭 S1确认制（隔离 R-05 效果）
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

# (label, sg, og, volgate, s1confirm, ep1tenor, r10gates, r9univ)
CONFIGS = [
    ("G0r", 70, 78, "0", "0", "0", "0", "0"),   # 回归对照 = D6r（重构开关全关, 12只池）
    ("G1r", 80, 85, "1", "1", "1", "1", "1"),   # 完整 v4.7-R10（30只池）
    ("G2r", 70, 72, "1", "1", "1", "0", "1"),   # G1 + 门槛回退P0-A（隔离R-10门槛）
    ("G3r", 80, 85, "1", "0", "1", "1", "1"),   # G1 关S1确认制（隔离R-05）
]


def run_one(label, sg, og, volgate, s1confirm, ep1tenor, r10gates, r9univ):
    env = dict(os.environ,
               BT_SCORE_GATE=str(sg), BT_OBS_GATE=str(og),
               BT_TRE_VARIANT="V1", BT_FIXL5="1", BT_R1="1", BT_R2="1", BT_R3="1",
               BT_KELLYMIN="1", BT_EP1BLOCK="1", BT_OBSGUARD="1",
               BT_VOLFILTER="0", BT_S1DERATE="0",
               BT_VOLGATE=volgate, BT_S1CONFIRM=s1confirm, BT_EP1TENOR=ep1tenor,
               BT_R10GATES=r10gates, BT_R9UNIV=r9univ)
    print(f"=== 运行 {label}: gate={sg}/{og} VG={volgate} S1C={s1confirm} "
          f"TEN={ep1tenor} R10G={r10gates} R9U={r9univ} ===", flush=True)
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
        "config": {"label": label, "score_gate": sg, "obs_gate": og,
                   "volgate": volgate, "s1confirm": s1confirm, "ep1tenor": ep1tenor,
                   "r10gates": r10gates, "r9univ": r9univ},
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
          f"回撤={mi['max_drawdown']:.2f}% 噪音止损={mi['noise_stop_rate'] if not isinstance(mi['noise_stop_rate'], float) or mi['noise_stop_rate']==mi['noise_stop_rate'] else 'nan'}% "
          f"S1胜率={mi['s1_confirm_wr']}% 利用率={mi['univ_util']}% 闸门={mi['gate_days']}日", flush=True)
    return summary


if __name__ == "__main__":
    results = {}
    for cfg in CONFIGS:
        s = run_one(*cfg)
        if s:
            results[cfg[0]] = s
    print("\n===== 汇总（样本内） =====")
    print(f"{'配置':<6}{'门槛':<8}{'建仓':>5}{'年建仓':>7}{'期望%':>8}{'年化%':>8}{'回撤%':>8}{'夏普':>6}{'胜率%':>7}"
          f"{'噪音止损%':>9}{'S1胜率%':>8}{'闸门日':>6}{'利用率%':>8}")
    for cfg in CONFIGS:
        label = cfg[0]
        if label not in results:
            continue
        m = results[label]["metrics_in"]
        print(f"{label:<6}{f'{cfg[1]}/{cfg[2]}':<8}{m['n_buys']:>5}{m['freq_annual']:>7.1f}"
              f"{m['avg_pnl_pct']:>8.2f}{m['ann_return']:>8.2f}{m['max_drawdown']:>8.2f}{m['sharpe']:>6.2f}"
              f"{m['win_rate']:>7.1f}{m['noise_stop_rate']:>9.1f}{m['s1_confirm_wr']:>8.1f}"
              f"{m['gate_days']:>6}{m['univ_util']:>8.1f}")
