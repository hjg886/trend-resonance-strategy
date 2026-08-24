# -*- coding: utf-8 -*-
"""
sweep_runner.py —— P1-03 滑点冲击测试 + P3-02 参数敏感性分析 批量驱动
对 run_backtest.py 进行多配置子进程调用(每次独立读取 env), 结果写入 results_{in,oos}_{fix}.json,
再复用 metrics.compute_all 计算各配置 IS/OOS 指标, 汇总至 output/sweep_results.json。

配置说明:
  P1-03 滑点冲击: 固定冲击系数 SLIP_IMPACT=0.0006, 资金 100万(基准,=canonical)/500万/1000万
        有效成本 = 基础佣金(买0.1%/卖0.2%) + SLIP_IMPACT × √(AUM/100万)
  P3-02 敏感性: 对关键参数做 ±10% 扰动(EP1_BAND_SHORT=7→6.3/7.7; BREADTH_MIN=15→13.5/16.5;
        VOL_GATE_A=15→13.5/16.5), 其余沿用 v5.0 固化基线
"""
import os, sys, json, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PY = r"C:/Users/hanji/.workbuddy/binaries/python/envs/backtest/Scripts/python.exe"
sys.path.insert(0, HERE)
import metrics as M

CONFIGS = [
    # (fix后缀, env覆盖)
    # ---- P1-03 滑点冲击 ----
    ("slip500",  {"BT_CAPITAL": "5000000",   "BT_SLIP_IMPACT": "0.0006"}),
    ("slip1000", {"BT_CAPITAL": "10000000",  "BT_SLIP_IMPACT": "0.0006"}),
    # ---- P3-02 敏感性 ±10% ----
    ("sens_ep1s_dn",  {"BT_EP1_BAND_SHORT": "6.3"}),
    ("sens_ep1s_up",  {"BT_EP1_BAND_SHORT": "7.7"}),
    ("sens_breadth_dn", {"BT_BREADTH_MIN": "13.5"}),
    ("sens_breadth_up", {"BT_BREADTH_MIN": "16.5"}),
    ("sens_vola_dn",  {"BT_VOL_GATE_A_THRESH": "13.5"}),
    ("sens_vola_up",  {"BT_VOL_GATE_A_THRESH": "16.5"}),
]


def run_one(fix, env):
    e = dict(os.environ)
    e.update(env)
    e["BT_OUTFIX"] = fix
    print(f"=== [{fix}] env={env} 开始回测 ===", flush=True)
    subprocess.run([PY, "run_backtest.py"], env=e, cwd=HERE, check=True)
    suffix = f"_{fix}"
    rin = json.load(open(os.path.join(M.OUT, f"results_in{suffix}.json"), encoding="utf-8"))
    roos = json.load(open(os.path.join(M.OUT, f"results_oos{suffix}.json"), encoding="utf-8"))
    bench = M.load_bench()
    bench_oos = M.load_bench(start=roos["hist"][0]["date"])
    r_in = M.compute_all(rin, bench, "IS", 72.0)
    r_oos = M.compute_all(roos, bench_oos, "OOS", 18.0)
    rec = {
        "fix": fix, "env": env,
        "IS_ann": round(r_in["ann_return"], 3), "IS_mdd": round(r_in["max_drawdown"], 3),
        "IS_trades": r_in["n_buys"],
        "OOS_ann": round(r_oos["ann_return"], 3), "OOS_mdd": round(r_oos["max_drawdown"], 3),
        "OOS_total": round(r_oos["total_return"], 3), "OOS_trades": r_oos["n_buys"],
        "OOS_sharpe": round(r_oos["sharpe"], 3),
    }
    print(f"=== [{fix}] OOS_ann={rec['OOS_ann']}% OOS_mdd={rec['OOS_mdd']}% OOS_trades={rec['OOS_trades']} ===", flush=True)
    return rec


def main():
    results = []
    for fix, env in CONFIGS:
        results.append(run_one(fix, env))
    with open(os.path.join(M.OUT, "sweep_results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print("ALL_SWEEPS_DONE", flush=True)
    print(json.dumps(results, ensure_ascii=False, indent=1), flush=True)


if __name__ == "__main__":
    main()
