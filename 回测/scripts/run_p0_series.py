# -*- coding: utf-8 -*-
"""
P0 修正系列回测（2026-08-18）
基线: G1r 完整 v4.7-R10（30只池 + R-04/R-05/R-06/R-10 全开）
变体:
  P0a: H1 S1禁ETF（F-35 单项隔离）
  P0b: BREADTH<15 否决层（单项隔离）
  P0c: H1 + BREADTH 否决（两项组合）
  P0d: H1 + BREADTH + E-P1更宽带宽(7%/4%)（三项组合）
  P0e: H1 + BREADTH + ETF E-P1禁用（三项组合, 替代带宽方案）
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

# G1r 基线环境（所有 R10 开关全开）
BASE_ENV = dict(
    BT_SCORE_GATE="80", BT_OBS_GATE="85",
    BT_TRE_VARIANT="V1", BT_FIXL5="1", BT_R1="1", BT_R2="1", BT_R3="1",
    BT_KELLYMIN="1", BT_EP1BLOCK="1", BT_OBSGUARD="1",
    BT_VOLFILTER="0", BT_S1DERATE="0",
    BT_VOLGATE="1", BT_S1CONFIRM="1", BT_EP1TENOR="1",
    BT_R10GATES="1", BT_R9UNIV="1",
)

# (label, extra_env_dict, description)
CONFIGS = [
    ("P0a", {"BT_H1_S1NOETF": "1"},
     "H1: S1禁ETF（F-35单项）"),
    ("P0b", {"BT_BREADTH_VETO": "1"},
     "BREADTH<15否决层（单项）"),
    ("P0c", {"BT_H1_S1NOETF": "1", "BT_BREADTH_VETO": "1"},
     "H1+BREADTH（两项组合）"),
    ("P0d", {"BT_H1_S1NOETF": "1", "BT_BREADTH_VETO": "1",
              "BT_EP1_BAND_SHORT": "7", "BT_EP1_BAND_LONG": "4"},
     "H1+BREADTH+宽带宽7/4（三项）"),
    ("P0e", {"BT_H1_S1NOETF": "1", "BT_BREADTH_VETO": "1",
              "BT_EP1_ETF_OFF": "1"},
     "H1+BREADTH+ETF E-P1禁用（三项）"),
]


def run_one(label, extra_env, desc):
    env = dict(os.environ, **BASE_ENV, **extra_env)
    env = {k: str(v) for k, v in env.items()}
    print(f"\n=== 运行 {label}: {desc} ===", flush=True)
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
        "config": {"label": label, "desc": desc, "extra_env": extra_env},
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
    nsr = mi['noise_stop_rate'] if not (isinstance(mi['noise_stop_rate'], float) and mi['noise_stop_rate'] != mi['noise_stop_rate']) else 'nan'
    print(f"[OK] {label}: in_final={res_in['final_equity']:.0f} buys={len(res_in['buys'])}+{len(res_oos['buys'])} "
          f"| 年建仓={mi['freq_annual']:.1f} 期望={mi['avg_pnl_pct']:.2f}% 年化={mi['ann_return']:.2f}% "
          f"回撤={mi['max_drawdown']:.2f}% 胜率={mi['win_rate']:.1f}% 噪音止损={nsr}% "
          f"S1胜率={mi['s1_confirm_wr']}% 利用率={mi['univ_util']}%", flush=True)
    return summary


if __name__ == "__main__":
    results = {}
    for label, extra_env, desc in CONFIGS:
        s = run_one(label, extra_env, desc)
        if s:
            results[label] = s

    # 加载 G1r 基线对比
    g1r_path = os.path.join(OUT, "variant_G1r.json")
    if os.path.exists(g1r_path):
        with open(g1r_path, encoding="utf-8") as fh:
            results["G1r"] = json.load(fh)

    print("\n" + "=" * 120)
    print("===== P0 系列汇总（样本内 6 年） =====")
    print("=" * 120)
    print(f"{'配置':<6}{'描述':<36}{'建仓':>5}{'年建仓':>7}{'期望%':>8}{'年化%':>8}{'回撤%':>8}"
          f"{'夏普':>6}{'胜率%':>7}{'噪音%':>7}{'S1胜率%':>8}{'利用率%':>8}")
    print("-" * 120)
    for label in ["G1r"] + [c[0] for c in CONFIGS]:
        if label not in results:
            continue
        r = results[label]
        mi = r.get("metrics_in", r.get("metrics_in", {}))
        if not mi:
            continue
        desc = r.get("config", {}).get("desc", "G1r基线") if label != "G1r" else "G1r基线"
        nsr = mi.get('noise_stop_rate', float('nan'))
        if isinstance(nsr, float) and nsr != nsr:
            nsr = float('nan')
        print(f"{label:<6}{desc:<36}{mi['n_buys']:>5}{mi['freq_annual']:>7.1f}"
              f"{mi['avg_pnl_pct']:>8.2f}{mi['ann_return']:>8.2f}{mi['max_drawdown']:>8.2f}"
              f"{mi['sharpe']:>6.2f}{mi['win_rate']:>7.1f}"
              f"{nsr:>7.1f}{mi['s1_confirm_wr']:>8.1f}{mi['univ_util']:>8.1f}")

    print("\n" + "=" * 120)
    print("===== P0 系列汇总（样本外 18 月） =====")
    print("=" * 120)
    print(f"{'配置':<6}{'建仓':>5}{'年建仓':>7}{'期望%':>8}{'年化%':>8}{'回撤%':>8}"
          f"{'夏普':>6}{'胜率%':>7}{'噪音%':>7}{'S1胜率%':>8}")
    print("-" * 100)
    for label in ["G1r"] + [c[0] for c in CONFIGS]:
        if label not in results:
            continue
        r = results[label]
        mo = r.get("metrics_oos", {})
        if not mo:
            continue
        nsr = mo.get('noise_stop_rate', float('nan'))
        if isinstance(nsr, float) and nsr != nsr:
            nsr = float('nan')
        print(f"{label:<6}{mo['n_buys']:>5}{mo['freq_annual']:>7.1f}"
              f"{mo['avg_pnl_pct']:>8.2f}{mo['ann_return']:>8.2f}{mo['max_drawdown']:>8.2f}"
              f"{mo['sharpe']:>6.2f}{mo['win_rate']:>7.1f}"
              f"{nsr:>7.1f}{mo['s1_confirm_wr']:>8.1f}")

    print("\nDone.")
