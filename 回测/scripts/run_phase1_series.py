# -*- coding: utf-8 -*-
"""
阶段1 历史定参回测 — 14个进攻线变体（2026-08-18）
====================================
候选A: ETF均值回归 (run_attack_a.py)
  A1: 3%超跌  / A2: RSI<35 / A3: 5%宽松  × IS+OOS = 6

候选B: 个股精选 (run_backtest.py + 进攻线env)
  B1: vol20闸门B≥30禁 / B2: 得分≥85严格 / B3: vol20闸门A≥12高频  × IS+OOS = 6

候选C: P12v6叠加层
  C1: best A + P12v6  / C2: best B + P12v6确认  × IS+OOS = 2(+2)

执行顺序: A(6) → B(6) → 判定best A/B → C(4) = 16次回测
输出: 16个JSON → 14个变体（C1/C2各IS+OOS合并为1个变体）
"""
import os, sys, json, subprocess, time

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "output")
PY = r"C:/Users/hanji/.workbuddy/binaries/python/envs/backtest/Scripts/python.exe"

# 24只观察池个股代码
OBS_POOL_CODES = ",".join([
    "603259", "300357", "605117", "688120", "002371", "300750",
    "600196", "002156", "688082", "300661", "300693", "600276",
    "600584", "688239", "603986", "688008", "603005", "002335",
    "002472", "002050", "002111", "000099", "002518", "688686",
])

# G1r 基线环境（主引擎标准配置）
G1R_ENV = dict(
    BT_SCORE_GATE="80", BT_OBS_GATE="85",
    BT_TRE_VARIANT="V1", BT_FIXL5="1", BT_R1="1", BT_R2="1", BT_R3="1",
    BT_KELLYMIN="1", BT_EP1BLOCK="1", BT_OBSGUARD="1",
    BT_VOLFILTER="0", BT_S1DERATE="0",
    BT_VOLGATE="1", BT_S1CONFIRM="1", BT_EP1TENOR="1",
    BT_R10GATES="1", BT_R9UNIV="1",
    # JOINT基线固化的改善
    BT_H1_S1NOETF="1", BT_BREADTH_VETO="1",
    BT_EP1_BAND_SHORT="7", BT_EP1_BAND_LONG="4",
    BT_F04_MULT="1.5", BT_KELLY_CAP="0.25",
)


def run_backtest_variant(label, extra_env, period_mode, use_attack_a=False, attack_a_env=None, script_name=None):
    """运行单个回测变体"""
    if script_name:
        script = script_name
        env = dict(os.environ, **(attack_a_env or extra_env))
    elif use_attack_a:
        script = "run_attack_a.py"
        env = dict(os.environ, **(attack_a_env or {}))
    else:
        script = "run_backtest.py"
        env = dict(os.environ, **G1R_ENV, **extra_env)
        env["BT_ATK_PERIOD"] = period_mode

    env = {k: str(v) for k, v in env.items()}
    t0 = time.time()
    print(f"\n{'='*60}", flush=True)
    print(f"运行 {label} ...", flush=True)
    r = subprocess.run([PY, script], cwd=SCRIPTS, env=env,
                       capture_output=True, text=True, timeout=1800)
    elapsed = time.time() - t0
    if r.returncode != 0:
        print(f"[FAIL] {label} ({elapsed:.0f}s): {r.stderr[-2000:]}")
        print(r.stdout[-3000:])
        return None
    print(f"[OK] {label} ({elapsed:.0f}s)", flush=True)
    # 打印最后10行输出
    for line in r.stdout.strip().split("\n")[-10:]:
        print(f"  {line}")
    return True


def extract_metrics(json_path):
    """从结果JSON提取核心指标"""
    try:
        with open(json_path, encoding="utf-8") as fh:
            res = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

    hist = res.get("hist", [])
    if not hist:
        return None

    eq = [float(h["equity"]) for h in hist]
    init = 1_000_000.0
    final_eq = eq[-1]
    total_ret = (final_eq / init - 1) * 100

    # 年化 — 使用固定年数 (IS=6年, OOS=1.5年)
    res_label = str(res.get("label", "")) + str(res.get("period_mode", ""))
    is_oos = "OOS" in res_label or "oos" in res_label.lower()
    years = 1.5 if is_oos else 6.0
    ann_ret = ((final_eq / init) ** (1 / years) - 1) * 100 if final_eq > 0 else -100

    # 最大回撤 (正向遍历: 峰值到后续谷值)
    peak = eq[0] if eq else final_eq
    max_dd = 0.0
    for e in eq:
        if e > peak:
            peak = e
        dd = (peak - e) / peak * 100.0 if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    # 交易统计 — 使用 closed_periods (list of dicts, 已正确序列化) 而非 trades (Trade对象)
    closed = res.get("closed", [])
    buys = res.get("buys", [])
    n_buys = len(buys)

    # 交易PnL
    trade_pnl = sum(float(c.get("pnl", 0)) for c in closed)
    cash_mgmt = float(res.get("cash_mgmt_ret", 0))

    # 交易期望
    pnls = [float(c.get("pnl", 0)) for c in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    win_rate = len(wins) / len(pnls) * 100 if pnls else 0
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    expectancy = (sum(pnls) / len(pnls)) if pnls else 0

    # Sharpe (日收益)
    import numpy as np
    rt = np.diff(eq) / eq[:-1] if len(eq) > 1 else [0]
    sharpe = float(np.mean(rt) / np.std(rt, ddof=1) * np.sqrt(252)) if len(rt) > 1 and np.std(rt, ddof=1) > 0 else 0
    vol = float(np.std(rt, ddof=1) * np.sqrt(252) * 100) if len(rt) > 1 else 0

    return {
        "total_ret": round(total_ret, 2),
        "ann_ret": round(ann_ret, 2),
        "max_dd": round(max_dd, 2),
        "sharpe": round(sharpe, 2),
        "vol": round(vol, 2),
        "n_buys": n_buys,
        "trade_pnl": round(trade_pnl, 0),
        "cash_mgmt": round(cash_mgmt, 0),
        "win_rate": round(win_rate, 1),
        "avg_win": round(avg_win, 0),
        "avg_loss": round(avg_loss, 0),
        "expectancy": round(expectancy, 0),
        "final_equity": round(final_eq, 0),
    }


def main():
    results = {}

    # ====== 候选A: ETF均值回归 (6 runs) ======
    print("\n" + "=" * 70)
    print("  候选A: ETF均值回归 — 6个回测 (A1/A2/A3 × IS/OOS)")
    print("=" * 70)

    a_variants = [
        ("A1", {"BT_ATK_SIGNAL": "A1", "BT_ATK_DROPOUT": "3.0"}),
        ("A2", {"BT_ATK_SIGNAL": "A2", "BT_ATK_RSI_THRESH": "35"}),
        ("A3", {"BT_ATK_SIGNAL": "A3", "BT_ATK_DROPOUT": "5.0"}),
    ]

    for tag, env_a in a_variants:
        for period in ["IS", "OOS"]:
            label = f"{tag}_{period}"
            full_env = dict(env_a, BT_ATK_PERIOD=period, BT_ATK_TAG=f"{tag}_{period}")
            ok = run_backtest_variant(label, {}, period, use_attack_a=True, attack_a_env=full_env)
            if ok:
                m = extract_metrics(os.path.join(OUT, f"attack_a_{tag}_{period}.json"))
                if m:
                    results[label] = m
                    print(f"  → {label}: 年化={m['ann_ret']:.2f}% 回撤={m['max_dd']:.2f}% 建仓={m['n_buys']}笔")

    # ====== 候选B: 个股精选 (6 runs) ======
    print("\n" + "=" * 70)
    print("  候选B: 个股精选 — 6个回测 (B1/B2/B3 × IS/OOS)")
    print("=" * 70)

    b_variants = [
        ("B1", {"BT_VOL_GATE_B_THRESH": "30", "BT_ATK_SCORE": "70"}, "闸门B≥30禁+得分≥70(放宽S1/S2, 兼容无财报股)"),
        ("B2", {"BT_ATK_SCORE": "75"}, "得分≥75严格筛选(简化评分可达)"),
        ("B3", {"BT_VOL_GATE_A_THRESH": "10", "BT_ATK_SCORE": "70"}, "闸门A≥10+得分≥70(放宽低波动禁令, 高频)"),
    ]

    for tag, env_b, desc in b_variants:
        for period in ["IS", "OOS"]:
            label = f"{tag}_{period}"
            full_env = dict(env_b, BT_ATK_PERIOD=period, BT_ATK_TAG=f"{tag}_{period}",
                            BT_ATK_P12="1")  # B变体默认开启P12v6
            ok = run_backtest_variant(f"{label} ({desc})", {}, period,
                                      attack_a_env=full_env, script_name="run_attack_b.py")
            if ok:
                m = extract_metrics(os.path.join(OUT, f"attack_b_{tag}_{period}.json"))
                if m:
                    results[label] = m
                    print(f"  → {label}: 年化={m['ann_ret']:.2f}% 回撤={m['max_dd']:.2f}% 建仓={m['n_buys']}笔")

    # ====== 判定 best A / best B ======
    print("\n" + "=" * 70)
    print("  判定 best A / best B (基于IS年化收益)")
    print("=" * 70)

    a_is_results = {k: v for k, v in results.items() if k.startswith("A") and k.endswith("_IS")}
    b_is_results = {k: v for k, v in results.items() if k.startswith("B") and k.endswith("_IS")}

    best_a = max(a_is_results, key=lambda k: a_is_results[k]["ann_ret"]) if a_is_results else None
    best_b = max(b_is_results, key=lambda k: b_is_results[k]["ann_ret"]) if b_is_results else None

    print(f"  Best A: {best_a} (IS年化={a_is_results.get(best_a, {}).get('ann_ret', 'N/A')}%)")
    print(f"  Best B: {best_b} (IS年化={b_is_results.get(best_b, {}).get('ann_ret', 'N/A')}%)")

    # ====== 候选C: P12v6叠加 (4 runs = 2 variants × IS+OOS) ======
    print("\n" + "=" * 70)
    print("  候选C: P12v6叠加 — 4个回测 (C1/C2 × IS/OOS)")
    print("=" * 70)

    # C1: best A 信号 + P12v6 叠加
    if best_a:
        best_a_tag = best_a.split("_")[0]  # A1/A2/A3
        best_a_env = {"A1": {"BT_ATK_SIGNAL": "A1", "BT_ATK_DROPOUT": "3.0"},
                      "A2": {"BT_ATK_SIGNAL": "A2", "BT_ATK_RSI_THRESH": "35"},
                      "A3": {"BT_ATK_SIGNAL": "A3", "BT_ATK_DROPOUT": "5.0"}}[best_a_tag]
        for period in ["IS", "OOS"]:
            label = f"C1_{period}"
            full_env = dict(best_a_env, BT_ATK_PERIOD=period, BT_ATK_TAG=f"C1_{period}",
                            BT_ATK_P12="1")
            ok = run_backtest_variant(f"C1 (best A={best_a_tag} + P12v6)", {}, period,
                                      use_attack_a=True, attack_a_env=full_env)
            if ok:
                m = extract_metrics(os.path.join(OUT, f"attack_a_C1_{period}.json"))
                if m:
                    results[label] = m
                    print(f"  → {label}: 年化={m['ann_ret']:.2f}% 回撤={m['max_dd']:.2f}%")

    # C2: best B 配置 + P12v6确认（run_attack_b.py 默认开启P12）
    if best_b:
        best_b_tag = best_b.split("_")[0]  # B1/B2/B3
        best_b_env = {"B1": {"BT_VOL_GATE_B_THRESH": "30", "BT_ATK_SCORE": "70"},
                      "B2": {"BT_ATK_SCORE": "75"},
                      "B3": {"BT_VOL_GATE_A_THRESH": "10", "BT_ATK_SCORE": "70"}}[best_b_tag]
        for period in ["IS", "OOS"]:
            label = f"C2_{period}"
            full_env = dict(best_b_env, BT_ATK_PERIOD=period, BT_ATK_TAG=f"C2_{period}",
                            BT_ATK_P12="1")
            ok = run_backtest_variant(f"C2 (best B={best_b_tag} + P12v6确认)", {}, period,
                                      attack_a_env=full_env, script_name="run_attack_b.py")
            if ok:
                m = extract_metrics(os.path.join(OUT, f"attack_b_C2_{period}.json"))
                if m:
                    results[label] = m
                    print(f"  → {label}: 年化={m['ann_ret']:.2f}% 回撤={m['max_dd']:.2f}%")

    # ====== 汇总输出 ======
    print("\n" + "=" * 70)
    print("  全部14个变体回测结果汇总")
    print("=" * 70)

    summary = {
        "best_a": best_a, "best_b": best_b,
        "results": results,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(OUT, "phase1_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)

    # 打印汇总表
    print(f"\n{'变体':<12s} {'年化%':>8s} {'回撤%':>8s} {'Sharpe':>8s} {'建仓':>6s} {'交易PnL':>12s} {'现金管理':>12s} {'胜率%':>6s}")
    print("-" * 80)
    for label in sorted(results.keys()):
        m = results[label]
        print(f"{label:<12s} {m['ann_ret']:8.2f} {m['max_dd']:8.2f} {m['sharpe']:8.2f} {m['n_buys']:6d} {m['trade_pnl']:12,.0f} {m['cash_mgmt']:12,.0f} {m['win_rate']:6.1f}")

    print(f"\nBest A: {best_a} | Best B: {best_b}")
    print(f"汇总输出: {os.path.join(OUT, 'phase1_summary.json')}")


if __name__ == "__main__":
    main()
