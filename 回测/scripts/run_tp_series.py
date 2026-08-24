# -*- coding: utf-8 -*-
"""
冗余2 趋势位置合并回测（2026-08-24，提频路径①）
基线: P0dCore 等价环境（固化 R10GATES/H1/BREADTH 默认1 + 7/4 带宽；
      R-04/05/06=VOLGATE/S1CONFIRM/EP1TENOR 默认关——与 P0dCore 存档口径一致）
变体（BT_TP_VARIANT）:
  V0: 原逻辑（基线, 改造关, 等价验证已过）
  V1: 温和提频 —— ②④⑥ C→25（放行破位/高位无空间建仓）
  V2: 标准     —— ②⑥ C→25, ④ C→0（保留"高位且无空间"否决语义）
  V3: 严格     —— ②④⑥ C→0
  V4: 严格+第2灯仅A档（six_lights/seven_lights 只认 A）
通过标准: 频率↑ 且 期望≥+0.27% 且 OOS 不恶化（任一转负立即回滚）
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

# P0dCore 等价基线环境（与 _verify_tp_v0.py 完全一致）
BASE_ENV = dict(
    os.environ,
    BT_EP1_BAND_SHORT="7", BT_EP1_BAND_LONG="4",
)

CONFIGS = [
    ("TPV0", {"BT_TP_VARIANT": "0"}, "V0 原逻辑（基线, 改造关）"),
    ("TPV1", {"BT_TP_VARIANT": "1"}, "V1 温和提频: ②④⑥ C→25"),
    ("TPV2", {"BT_TP_VARIANT": "2"}, "V2 标准: ②⑥ C→25, ④ C→0"),
    ("TPV3", {"BT_TP_VARIANT": "3"}, "V3 严格: ②④⑥ C→0"),
    ("TPV4", {"BT_TP_VARIANT": "4"}, "V4 严格+第2灯仅A档"),
]


def run_one(label, extra_env, desc):
    env = {k: str(v) for k, v in dict(BASE_ENV, **extra_env).items()}
    print(f"\n=== 运行 {label}: {desc} ===", flush=True)
    r = subprocess.run([PY, "run_backtest.py"], cwd=SCRIPTS, env=env,
                       capture_output=True, text=True, timeout=1800)
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
                "closed": len(res_oos["closed"]), "obs_stats": res_oos["obs_stats"],
                "gate_stats": res_oos["gate_stats"]},
        "metrics_in": mi, "metrics_oos": mo,
        "buys_in": res_in["buys"], "buys_oos": res_oos["buys"],
        "closed_in": res_in["closed"], "closed_oos": res_oos["closed"],
    }
    with open(os.path.join(OUT, f"variant_{label}.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1, default=str)
    nsr = mi.get('noise_stop_rate', float('nan'))
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

    print("\n" + "=" * 130)
    print("===== 冗余2 趋势位置合并回测汇总（样本内 6 年） =====")
    print("=" * 130)
    print(f"{'配置':<6}{'描述':<30}{'建仓':>5}{'年建仓':>7}{'期望%':>8}{'年化%':>8}{'回撤%':>8}"
          f"{'夏普':>6}{'胜率%':>7}{'噪音%':>7}{'S1胜率%':>8}{'利用率%':>8}")
    print("-" * 130)
    for label in [c[0] for c in CONFIGS]:
        if label not in results:
            continue
        r = results[label]
        mi = r.get("metrics_in", {})
        if not mi:
            continue
        desc = r.get("config", {}).get("desc", "")
        nsr = mi.get('noise_stop_rate', float('nan'))
        print(f"{label:<6}{desc:<30}{mi['n_buys']:>5}{mi['freq_annual']:>7.1f}"
              f"{mi['avg_pnl_pct']:>8.2f}{mi['ann_return']:>8.2f}{mi['max_drawdown']:>8.2f}"
              f"{mi['sharpe']:>6.2f}{mi['win_rate']:>7.1f}"
              f"{nsr:>7.1f}{mi['s1_confirm_wr']:>8.1f}{mi['univ_util']:>8.1f}")

    print("\n" + "=" * 130)
    print("===== 冗余2 趋势位置合并回测汇总（样本外 18 月） =====")
    print("=" * 130)
    print(f"{'配置':<6}{'描述':<30}{'建仓':>5}{'年建仓':>7}{'期望%':>8}{'年化%':>8}{'回撤%':>8}"
          f"{'夏普':>6}{'胜率%':>7}{'噪音%':>7}{'S1胜率%':>8}")
    print("-" * 130)
    for label in [c[0] for c in CONFIGS]:
        if label not in results:
            continue
        r = results[label]
        mo = r.get("metrics_oos", {})
        if not mo:
            continue
        desc = r.get("config", {}).get("desc", "")
        nsr = mo.get('noise_stop_rate', float('nan'))
        print(f"{label:<6}{desc:<30}{mo['n_buys']:>5}{mo['freq_annual']:>7.1f}"
              f"{mo['avg_pnl_pct']:>8.2f}{mo['ann_return']:>8.2f}{mo['max_drawdown']:>8.2f}"
              f"{mo['sharpe']:>6.2f}{mo['win_rate']:>7.1f}"
              f"{nsr:>7.1f}{mo['s1_confirm_wr']:>8.1f}")

    print("\nDone.")
