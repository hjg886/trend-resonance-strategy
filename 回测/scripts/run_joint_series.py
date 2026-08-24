# -*- coding: utf-8 -*-
"""
F04a x P0d 联合回测（2026-08-18）
将仓位引擎 F04a(ATR x1.5) 与 P0d(H1+BREADTH+7%/4%) 合并为单一变体,
验证两个改善是否正交叠加或互相抵消。

已有结果（直接加载对比）:
  G1r  : 基线（无H1, 无BREADTH, x1.0, 5%/3%带宽）
  P0d  : H1+BREADTH+7%/4%（x1.0）
  F04a : x1.5（无H1, 无BREADTH, 5%/3%带宽）
  Joint: H1+BREADTH+7%/4% + x1.5（本次运行）
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

# G1r 基线环境
BASE_ENV = dict(
    BT_SCORE_GATE="80", BT_OBS_GATE="85",
    BT_TRE_VARIANT="V1", BT_FIXL5="1", BT_R1="1", BT_R2="1", BT_R3="1",
    BT_KELLYMIN="1", BT_EP1BLOCK="1", BT_OBSGUARD="1",
    BT_VOLFILTER="0", BT_S1DERATE="0",
    BT_VOLGATE="1", BT_S1CONFIRM="1", BT_EP1TENOR="1",
    BT_R10GATES="1", BT_R9UNIV="1",
)

# F04a x P0d 联合变体
JOINT_ENV = dict(
    BT_H1_S1NOETF="1",           # P0d: S1禁ETF (F-35)
    BT_BREADTH_VETO="1",          # P0d: BREADTH<15否决层 (F-36)
    BT_EP1_BAND_SHORT="7",       # P0d: E-P1宽带权 短端7%
    BT_EP1_BAND_LONG="4",        # P0d: E-P1宽带权 长端4%
    BT_F04_MULT="1.5",           # F04a: ATR仓位 x1.5
    BT_KELLY_CAP="0.25",         # 凯利封顶保持默认0.25
)

# 加载已有结果
PRIOR = ["G1r", "P0d", "F04a"]


def run_joint():
    label = "JOINT"
    env = dict(os.environ, **BASE_ENV, **JOINT_ENV)
    env = {k: str(v) for k, v in env.items()}
    print(f"\n=== 运行 {label}: F04a(x1.5) x P0d(H1+BREADTH+7/4) ===", flush=True)
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
    pnl_amt_in = sum(float(c.get("pnl", 0)) for c in res_in["closed"])
    pnl_amt_oos = sum(float(c.get("pnl", 0)) for c in res_oos["closed"])
    summary = {
        "config": {"label": label, "desc": "F04a(x1.5) x P0d(H1+BREADTH+7/4)",
                    "extra_env": JOINT_ENV},
        "in": {"final": res_in["final_equity"], "buys": len(res_in["buys"]),
               "closed": len(res_in["closed"]), "obs_stats": res_in["obs_stats"],
               "gate_stats": res_in["gate_stats"], "univ_size": res_in["universe_size"],
               "pnl_amt": pnl_amt_in},
        "oos": {"final": res_oos["final_equity"], "buys": len(res_oos["buys"]),
                "closed": len(res_oos["closed"]), "obs_stats": res_oos["obs_stats"],
                "pnl_amt": pnl_amt_oos},
        "metrics_in": mi, "metrics_oos": mo,
        "buys_in": res_in["buys"], "buys_oos": res_oos["buys"],
        "closed_in": res_in["closed"], "closed_oos": res_oos["closed"],
        "stats_in": res_in["stats"],
    }
    with open(os.path.join(OUT, f"variant_{label}.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1, default=str)
    nsr = mi.get('noise_stop_rate', float('nan'))
    if isinstance(nsr, float) and nsr != nsr:
        nsr = float('nan')
    print(f"[OK] {label}: in_final={res_in['final_equity']:.0f} "
          f"buys={len(res_in['buys'])}+{len(res_oos['buys'])} "
          f"| 年建仓={mi['freq_annual']:.1f} 期望={mi['avg_pnl_pct']:.2f}% "
          f"年化={mi['ann_return']:.2f}% 回撤={mi['max_drawdown']:.2f}% "
          f"夏普={mi['sharpe']:.2f} 胜率={mi['win_rate']:.1f}% "
          f"交易PnL={pnl_amt_in:+,.0f}元", flush=True)
    return summary


if __name__ == "__main__":
    results = {}

    # 加载已有结果
    for label in PRIOR:
        path = os.path.join(OUT, f"variant_{label}.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                results[label] = json.load(fh)
            print(f"[LOAD] {label} 已加载")

    # 运行联合变体
    s = run_joint()
    if s:
        results["JOINT"] = s

    # ===== 汇总对比表 =====
    print("\n" + "=" * 130)
    print("===== F04a x P0d 联合回测汇总（样本内 6 年） =====")
    print("=" * 130)
    print(f"{'配置':<8}{'描述':<42}{'建仓':>5}{'年建仓':>7}{'期望%':>8}{'年化%':>8}"
          f"{'回撤%':>8}{'夏普':>6}{'胜率%':>7}{'噪音%':>7}{'交易PnL':>12}")
    print("-" * 130)
    order = ["G1r", "P0d", "F04a", "JOINT"]
    descs = {
        "G1r": "基线（x1.0, 5%/3%, 无H1/BRD）",
        "P0d": "H1+BREADTH+7/4（x1.0）",
        "F04a": "ATR x1.5（无H1/BRD, 5%/3%）",
        "JOINT": "H1+BREADTH+7/4 + x1.5",
    }
    for label in order:
        if label not in results:
            continue
        r = results[label]
        mi = r.get("metrics_in", {})
        if not mi:
            continue
        nsr = mi.get('noise_stop_rate', float('nan'))
        if isinstance(nsr, float) and nsr != nsr:
            nsr = float('nan')
        pnl = r.get("in", {}).get("pnl_amt", 0)
        if not pnl:
            # G1r 可能没有 pnl_amt 字段，从 closed 手动计算
            closed_in = r.get("closed_in", [])
            if closed_in:
                pnl = sum(float(c.get("pnl", 0)) for c in closed_in)
        print(f"{label:<8}{descs.get(label, ''):<42}{mi['n_buys']:>5}{mi['freq_annual']:>7.1f}"
              f"{mi['avg_pnl_pct']:>8.2f}{mi['ann_return']:>8.2f}{mi['max_drawdown']:>8.2f}"
              f"{mi['sharpe']:>6.2f}{mi['win_rate']:>7.1f}"
              f"{nsr:>7.1f}{pnl:>12,.0f}")

    print("\n" + "=" * 130)
    print("===== F04a x P0d 联合回测汇总（样本外 18 月） =====")
    print("=" * 130)
    print(f"{'配置':<8}{'建仓':>5}{'年建仓':>7}{'期望%':>8}{'年化%':>8}{'回撤%':>8}"
          f"{'夏普':>6}{'胜率%':>7}{'交易PnL':>12}")
    print("-" * 90)
    for label in order:
        if label not in results:
            continue
        r = results[label]
        mo = r.get("metrics_oos", {})
        if not mo:
            continue
        pnl = r.get("oos", {}).get("pnl_amt", 0)
        if not pnl:
            closed_oos = r.get("closed_oos", [])
            if closed_oos:
                pnl = sum(float(c.get("pnl", 0)) for c in closed_oos)
        print(f"{label:<8}{mo['n_buys']:>5}{mo['freq_annual']:>7.1f}"
              f"{mo['avg_pnl_pct']:>8.2f}{mo['ann_return']:>8.2f}{mo['max_drawdown']:>8.2f}"
              f"{mo['sharpe']:>6.2f}{mo['win_rate']:>7.1f}{pnl:>12,.0f}")

    # ===== 正交性分析 =====
    print("\n" + "=" * 130)
    print("===== 正交性分析 =====")
    print("=" * 130)
    if all(k in results for k in ["G1r", "P0d", "F04a", "JOINT"]):
        g1r_mi = results["G1r"]["metrics_in"]
        p0d_mi = results["P0d"]["metrics_in"]
        f04a_mi = results["F04a"]["metrics_in"]
        joint_mi = results["JOINT"]["metrics_in"]

        # 改善量（相对于G1r基线）
        def delta(base, cur, key):
            return cur[key] - base[key]

        print(f"\n{'指标':<12}{'G1r基线':>10}{'P0d':>10}{'F04a':>10}{'JOINT':>10}"
              f"{'P0d增量':>10}{'F04a增量':>10}{'叠加预期':>10}{'实际JOINT':>10}{'交互效应':>10}")
        print("-" * 112)
        for key, label in [("ann_return", "年化%"), ("avg_pnl_pct", "期望%"),
                           ("max_drawdown", "回撤%"), ("sharpe", "夏普")]:
            g = g1r_mi[key]
            p = p0d_mi[key]
            f = f04a_mi[key]
            j = joint_mi[key]
            d_p = p - g  # P0d 单独改善
            d_f = f - g  # F04a 单独改善
            expected = g + d_p + d_f  # 线性叠加预期
            actual = j - g  # 实际联合改善
            interaction = actual - (d_p + d_f)  # 交互效应（>0=协同, <0=抵消）
            print(f"{label:<12}{g:>10.2f}{p:>10.2f}{f:>10.2f}{j:>10.2f}"
                  f"{d_p:>+10.2f}{d_f:>+10.2f}{expected:>10.2f}{actual:>+10.2f}{interaction:>+10.2f}")

        print("\n交互效应解读:")
        print("  >0 = 协同效应（1+1>2, 两个改善互相增强）")
        print("  ≈0 = 正交独立（1+1=2, 两个改善互不干扰）")
        print("  <0 = 抵消效应（1+1<2, 两个改善部分抵消）")

    # ===== 14A 验收判定 =====
    print("\n" + "=" * 130)
    print("===== 14A 验收判定（样本内） =====")
    print("=" * 130)
    for label in order:
        if label not in results:
            continue
        mi = results[label].get("metrics_in", {})
        if not mi:
            continue
        checks = {
            "年建仓≥6笔": mi["freq_annual"] >= 6.0,
            "单笔期望>0": (mi["avg_pnl_pct"] == mi["avg_pnl_pct"]) and mi["avg_pnl_pct"] > 0,
            "年化≥6%": mi["ann_return"] >= 6.0,
            "回撤≤12%": mi["max_drawdown"] <= 12.0,
        }
        ok = all(checks.values())
        print(f"  {label:<8}: {'✅ 全部达标' if ok else '❌ 未达标'} "
              + " | ".join(f"{k}={'✓' if v else '✗'}" for k, v in checks.items()))

    print("\nDone.")
