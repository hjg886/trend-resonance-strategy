# -*- coding: utf-8 -*-
"""
P12 移动止盈引擎扩大化回测（2026-08-18）

在 JOINT 基线（F04a×P0d = H1+BREADTH+7/4+x1.5）上，
测试 4 种 P12 门槛/回撤配置，寻找最优移动止盈参数。

变体设计:
  JOINT : 基线（P12 门槛15%, 回撤50/40/30%）
  P12v1 : 门槛10%（仅下移门槛, 回撤不变）
  P12v2 : 门槛8% + 新增低档（8-15%回撤55%, 其余不变）
  P12v3 : 门槛8% + 全档收紧（回撤50/45/35/25%）
  P12v4 : 门槛5% + 全档最紧（回撤50/45/35/25%）

BT_P12_TIERS 格式: JSON [[min_fp, retr], ...] 升序
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

# JOINT 基线环境（F04a×P0d）
JOINT_ENV = dict(
    BT_H1_S1NOETF="1",           # P0d: S1禁ETF (F-35)
    BT_BREADTH_VETO="1",          # P0d: BREADTH<15否决层 (F-36)
    BT_EP1_BAND_SHORT="7",       # P0d: E-P1宽带权 短端7%
    BT_EP1_BAND_LONG="4",        # P0d: E-P1宽带权 长端4%
    BT_F04_MULT="1.5",           # F04a: ATR仓位 x1.5
    BT_KELLY_CAP="0.25",         # 凯利封顶保持默认0.25
)

# P12 扩大化变体
VARIANTS = [
    ("P12v1", "门槛10%, 回撤50/40/30%",
     '{"BT_P12_TIERS": "[[0.10,0.50],[0.30,0.40],[0.50,0.30]]"}'),
    ("P12v2", "门槛8%, 新增低档55%, 回撤55/50/40/30%",
     '{"BT_P12_TIERS": "[[0.08,0.55],[0.15,0.50],[0.30,0.40],[0.50,0.30]]"}'),
    ("P12v3", "门槛8%, 全档收紧50/45/35/25%",
     '{"BT_P12_TIERS": "[[0.08,0.50],[0.15,0.45],[0.30,0.35],[0.50,0.25]]"}'),
    ("P12v4", "门槛5%, 全档最紧50/45/35/25%",
     '{"BT_P12_TIERS": "[[0.05,0.50],[0.15,0.45],[0.30,0.35],[0.50,0.25]]"}'),
]

# 已有结果（直接加载对比）
PRIOR = ["JOINT"]


def run_variant(label, desc, extra_json):
    extra = json.loads(extra_json)
    env = dict(os.environ, **BASE_ENV, **JOINT_ENV, **extra)
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
    pnl_amt_in = sum(float(c.get("pnl", 0)) for c in res_in["closed"])
    pnl_amt_oos = sum(float(c.get("pnl", 0)) for c in res_oos["closed"])

    # 统计 P12 出场笔数
    p12_in = [c for c in res_in["closed"] if "P12" in str(c.get("exit_reason", ""))]
    p12_oos = [c for c in res_oos["closed"] if "P12" in str(c.get("exit_reason", ""))]
    p12_pnl_in = sum(float(c.get("pnl", 0)) for c in p12_in)
    p12_pnl_oos = sum(float(c.get("pnl", 0)) for c in p12_oos)

    # 统计各出场机制
    exit_breakdown_in = {}
    for c in res_in["closed"]:
        reason = str(c.get("exit_reason", "unknown")).split("-")[0]
        exit_breakdown_in[reason] = exit_breakdown_in.get(reason, 0) + 1

    summary = {
        "config": {"label": label, "desc": desc, "extra_env": extra},
        "in": {"final": res_in["final_equity"], "buys": len(res_in["buys"]),
               "closed": len(res_in["closed"]), "obs_stats": res_in["obs_stats"],
               "gate_stats": res_in["gate_stats"], "univ_size": res_in["universe_size"],
               "pnl_amt": pnl_amt_in,
               "p12_count": len(p12_in), "p12_pnl": p12_pnl_in,
               "exit_breakdown": exit_breakdown_in},
        "oos": {"final": res_oos["final_equity"], "buys": len(res_oos["buys"]),
                "closed": len(res_oos["closed"]), "obs_stats": res_oos["obs_stats"],
                "pnl_amt": pnl_amt_oos,
                "p12_count": len(p12_oos), "p12_pnl": p12_pnl_oos},
        "metrics_in": mi, "metrics_oos": mo,
        "buys_in": res_in["buys"], "buys_oos": res_oos["buys"],
        "closed_in": res_in["closed"], "closed_oos": res_oos["closed"],
        "stats_in": res_in["stats"],
    }
    with open(os.path.join(OUT, f"variant_{label}.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1, default=str)
    print(f"[OK] {label}: in_final={res_in['final_equity']:.0f} "
          f"buys={len(res_in['buys'])}+{len(res_oos['buys'])} "
          f"P12={len(p12_in)}+{len(p12_oos)} "
          f"| 期望={mi['avg_pnl_pct']:.2f}% "
          f"年化={mi['ann_return']:.2f}% 回撤={mi['max_drawdown']:.2f}% "
          f"夏普={mi['sharpe']:.2f} 胜率={mi['win_rate']:.1f}% "
          f"交易PnL={pnl_amt_in:+,.0f}元 "
          f"P12PnL={p12_pnl_in:+,.0f}元", flush=True)
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

    # 运行 4 个 P12 变体
    for label, desc, extra_json in VARIANTS:
        s = run_variant(label, desc, extra_json)
        if s:
            results[label] = s

    # ===== 汇总对比表 =====
    order = ["JOINT", "P12v1", "P12v2", "P12v3", "P12v4"]
    descs = {
        "JOINT": "基线(门槛15%, 回撤50/40/30%)",
        "P12v1": "门槛10%, 回撤不变",
        "P12v2": "门槛8%, 新增低档55%",
        "P12v3": "门槛8%, 全档收紧",
        "P12v4": "门槛5%, 全档最紧",
    }

    print("\n" + "=" * 145)
    print("===== P12 移动止盈扩大化汇总（样本内 6 年 IS） =====")
    print("=" * 145)
    print(f"{'配置':<8}{'描述':<32}{'建仓':>5}{'期望%':>8}{'年化%':>8}{'回撤%':>8}"
          f"{'夏普':>6}{'胜率%':>7}{'P12笔':>6}{'P12PnL':>10}{'交易PnL':>12}{'噪音%':>7}")
    print("-" * 145)
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
        p12c = r.get("in", {}).get("p12_count", 0)
        if p12c == 0:
            # 可能是 JOINT 没有 p12_count 字段, 从 closed 手动统计
            closed_in = r.get("closed_in", [])
            p12c = sum(1 for c in closed_in if "P12" in str(c.get("exit_reason", "")))
        p12p = r.get("in", {}).get("p12_pnl", 0)
        if p12p == 0:
            closed_in = r.get("closed_in", [])
            p12p = sum(float(c.get("pnl", 0)) for c in closed_in if "P12" in str(c.get("exit_reason", "")))
        pnl = r.get("in", {}).get("pnl_amt", 0)
        if not pnl:
            closed_in = r.get("closed_in", [])
            if closed_in:
                pnl = sum(float(c.get("pnl", 0)) for c in closed_in)
        print(f"{label:<8}{descs.get(label, ''):<32}{mi['n_buys']:>5}"
              f"{mi['avg_pnl_pct']:>8.2f}{mi['ann_return']:>8.2f}{mi['max_drawdown']:>8.2f}"
              f"{mi['sharpe']:>6.2f}{mi['win_rate']:>7.1f}"
              f"{p12c:>6}{p12p:>10,.0f}{pnl:>12,.0f}"
              f"{nsr:>7.1f}")

    print("\n" + "=" * 100)
    print("===== P12 移动止盈扩大化汇总（样本外 18 月 OOS） =====")
    print("=" * 100)
    print(f"{'配置':<8}{'建仓':>5}{'期望%':>8}{'年化%':>8}{'回撤%':>8}"
          f"{'夏普':>6}{'胜率%':>7}{'P12笔':>6}{'P12PnL':>10}{'交易PnL':>12}")
    print("-" * 100)
    for label in order:
        if label not in results:
            continue
        r = results[label]
        mo = r.get("metrics_oos", {})
        if not mo:
            continue
        p12c = r.get("oos", {}).get("p12_count", 0)
        if p12c == 0:
            closed_oos = r.get("closed_oos", [])
            p12c = sum(1 for c in closed_oos if "P12" in str(c.get("exit_reason", "")))
        p12p = r.get("oos", {}).get("p12_pnl", 0)
        if p12p == 0:
            closed_oos = r.get("closed_oos", [])
            p12p = sum(float(c.get("pnl", 0)) for c in closed_oos if "P12" in str(c.get("exit_reason", "")))
        pnl = r.get("oos", {}).get("pnl_amt", 0)
        if not pnl:
            closed_oos = r.get("closed_oos", [])
            if closed_oos:
                pnl = sum(float(c.get("pnl", 0)) for c in closed_oos)
        print(f"{label:<8}{mo['n_buys']:>5}"
              f"{mo['avg_pnl_pct']:>8.2f}{mo['ann_return']:>8.2f}{mo['max_drawdown']:>8.2f}"
              f"{mo['sharpe']:>6.2f}{mo['win_rate']:>7.1f}"
              f"{p12c:>6}{p12p:>10,.0f}{pnl:>12,.0f}")

    # ===== 出场机制分布 =====
    print("\n" + "=" * 100)
    print("===== IS 出场机制分布 =====")
    print("=" * 100)
    for label in order:
        if label not in results:
            continue
        r = results[label]
        # 从 closed_in 统计出场机制
        closed_in = r.get("closed_in", [])
        if not closed_in:
            continue
        breakdown = {}
        for c in closed_in:
            reason = str(c.get("exit_reason", "unknown"))
            # 提取机制前缀 (如 "P12/E-P12-移动止盈..." -> "P12")
            parts = reason.split("-")
            prefix = parts[0].split("/")[0] if "/" in parts[0] else parts[0]
            breakdown[prefix] = breakdown.get(prefix, 0) + 1
        bd_str = ", ".join(f"{k}={v}" for k, v in sorted(breakdown.items()))
        print(f"  {label:<8}: {bd_str}")

    # ===== 14A 验收判定 =====
    print("\n" + "=" * 100)
    print("===== 14A 验收判定（样本内） =====")
    print("=" * 100)
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
