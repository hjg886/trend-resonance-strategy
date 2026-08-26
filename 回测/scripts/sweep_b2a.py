# -*- coding: utf-8 -*-
"""
sweep_b2a.py —— Track B2 路径 A 复扫（2026-08-26）
验证假设: B2 失败主因是「动量缩放 0.5 砍半过度」，而非 B2 结构本身。
固定 B2 结构(est_w=25, vol_w=20), 扫描 MOM_SCALE ∈ {0.5, 0.7, 0.85, 1.0}:
  - 0.5 : 已知 fail (基线对照, B2 原设)
  - 0.7 : 轻度降动量
  - 0.85: 微降动量
  - 1.0 : 不降动量(仅新增估值/低波维度, 动量满)
验收(主引擎整体): OOS≥3.5% 且 OOS>IS 且 mdd≤12% 且 freq≥6
硬约束: 主引擎整体 OOS 不得较 B1 基线 3.86% 退化 >0.3%
"""
import os, sys, json, time, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PY = r"C:/Users/hanji/.workbuddy/binaries/python/envs/tre_backtest/Scripts/python.exe"
sys.path.insert(0, HERE)
import metrics as M

B1_OOS_BASE = 3.86
# 固定 B2 结构, 仅扫动量缩放
EST_W, VOL_W = 25, 20
MOMS = [0.5, 0.7, 0.85, 1.0]
CONFIGS = []
for mom in MOMS:
    fix = f"b2a_e{EST_W}_v{VOL_W}_m{mom}"
    env = {"BT_B2_ON": "1", "BT_B2_EST_W": str(EST_W),
           "BT_B2_VOL_W": str(VOL_W), "BT_B2_MOM_SCALE": str(mom)}
    CONFIGS.append((fix, env))


def have(fix):
    p_in = os.path.join(M.OUT, f"results_in_{fix}.json")
    p_oos = os.path.join(M.OUT, f"results_oos_{fix}.json")
    return os.path.exists(p_in) and os.path.exists(p_oos)


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
        "OOS_ann": round(r_oos["ann_return"], 3), "OOS_mdd": round(r_oos["max_drawdown"], 3),
        "OOS_trades": r_oos["n_buys"], "OOS_etf_ann": round(r_oos.get("etf_ann", float("nan")), 3),
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
    with open(os.path.join(M.OUT, "sweep_b2a.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print("\n===== Track B2 路径 A 汇总（MOM_SCALE 梯度, est_w=25/vol_w=20）=====", flush=True)
    print(f"{'fix':<22}{'OOS_ann':>9}{'OOS_etf':>9}{'IS_ann':>8}{'OOS_mdd':>8}{'trd':>5}"
          f"{'freq':>6}{'sharpe':>8}{'win%':>7}{'PASS':>6}", flush=True)
    best = None
    for r in results:
        ok = (r["OOS_ann"] >= 3.5 and r["OOS_ann"] > r["IS_ann"] and r["OOS_mdd"] <= 12
              and r["OOS_trades"] >= 6)
        hard = (r["OOS_ann"] >= B1_OOS_BASE - 0.3)
        tag = " <<<PASS" if (ok and hard) else (" <hardFAIL" if not hard else "")
        print(f"{r['fix']:<22}{r['OOS_ann']:>9}{r['OOS_etf_ann']:>9}{r['IS_ann']:>8}"
              f"{r['OOS_mdd']:>8}{r['OOS_trades']:>5}{r['OOS_freq']:>6}{r['OOS_sharpe']:>8}"
              f"{r['OOS_win']:>7}{tag}", flush=True)
        if ok and hard:
            if best is None or r["OOS_ann"] > best["OOS_ann"]:
                best = r
    print(f"\nDONE {len(results)}/{len(CONFIGS)} 配置；最佳 PASS 配置: "
          f"{best['fix'] if best else '无'} (OOS={best['OOS_ann'] if best else 'NA'})", flush=True)


if __name__ == "__main__":
    main()
