# -*- coding: utf-8 -*-
"""
P0 重设计批量实验（任务#86）
B5: P0-A 评分门槛重标定(70/78) + V0 现行转换表      —— 隔离评分效果
B6: P0-B 转换表修复(S2→S4当日, V1) + 现行门槛(80/85) —— 隔离转换表效果
B7: P0-A + P0-B 组合(70/78 + V1)                    —— 完整 v4.7-R9
B8: 中间档(75/82 + V1)                              —— 门槛灵敏度
B9: 宽松档(65/75 + V1)                              —— 过度交易检验

D 系列（v4.7-R9 第三轮修复, 门槛与B7r一致 70/78 + V1, 基准=B7r）:
D0: P0-D 第5灯事件计数修复(唯一改动)
D1: D0 + R1 第5灯分层(宽基≤1/行业≤3/观察通道豁免)
D2: D1 + R2 行业ETF门槛分轨(65/72/68)
D3: D2 + R3 MIN行业ETF z-score化                    —— 完整 v4.7-R9 候选

D4-D6（v4.7-R9 第四轮修复, 基于D3 叠加 P0-E/F/G）:
D4: D3 + P0-F 凯利下限保护10%                       —— 修复连续亏损→cap=0死锁
D5: D4 + P0-G E-P1止损后30日洗仓封堵                —— 修复同日卖买回洗仓
D6: D5 + P0-E 观察升级当日豁免名义状态转换           —— 修复升级S2被S2→S4吞没
"""
import os, sys, json, subprocess, shutil

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCRIPTS = os.path.dirname(__file__)
OUT = os.path.join(ROOT, "output")
PY = r"C:/Users/hanji/.workbuddy/binaries/python/envs/backtest/Scripts/python.exe"

sys.path.insert(0, SCRIPTS)
import metrics as M

# (label, sg, og, var, fixl5, r1, r2, r3, kellymin, ep1block, obsguard)
CONFIGS = [
    ("B0r", 80, 85, "V0", "0", "0", "0", "0", "0", "0", "0"),   # 仅P0-C: vol20口径修复（对照）
    ("B5r", 70, 78, "V0", "0", "0", "0", "0", "0", "0", "0"),   # P0-A+P0-C
    ("B6r", 80, 85, "V1", "0", "0", "0", "0", "0", "0", "0"),   # P0-B+P0-C
    ("B7r", 70, 78, "V1", "0", "0", "0", "0", "0", "0", "0"),   # 完整: P0-A+P0-B+P0-C（D系列基准）
    ("B8r", 75, 82, "V1", "0", "0", "0", "0", "0", "0", "0"),   # 门槛灵敏度
    ("B9r", 65, 75, "V1", "0", "0", "0", "0", "0", "0", "0"),   # 宽松档
    # ---- D 系列（P0-D 计数修复 + R1/R2/R3 叠加） ----
    ("D0r", 70, 78, "V1", "1", "0", "0", "0", "0", "0", "0"),   # P0-D 事件计数修复
    ("D1r", 70, 78, "V1", "1", "1", "0", "0", "0", "0", "0"),   # +R1 第5灯分层
    ("D2r", 70, 78, "V1", "1", "1", "1", "0", "0", "0", "0"),   # +R2 行业门槛分轨
    ("D3r", 70, 78, "V1", "1", "1", "1", "1", "0", "0", "0"),   # +R3 MIN z-score 完整候选
    # ---- D4-D6 系列（第四轮: P0-F/G/E 叠加） ----
    ("D4r", 70, 78, "V1", "1", "1", "1", "1", "1", "0", "0"),   # +P0-F 凯利下限10%
    ("D5r", 70, 78, "V1", "1", "1", "1", "1", "1", "1", "0"),   # +P0-G E-P1洗仓封堵
    ("D6r", 70, 78, "V1", "1", "1", "1", "1", "1", "1", "1"),   # +P0-E 观察升级豁免 完整修复
]

bench_in = M.load_bench(start="2019-01-01", end="2024-12-31")
bench_oos = M.load_bench(start="2025-01-01", end="2026-06-30")


def run_one(label, sg, og, var, fixl5, r1, r2, r3, kellymin, ep1block, obsguard,
            volfilter="0", s1derate="0"):
    env = dict(os.environ, BT_SCORE_GATE=str(sg), BT_OBS_GATE=str(og),
               BT_TRE_VARIANT=var, BT_FIXL5=fixl5, BT_R1=r1, BT_R2=r2, BT_R3=r3,
               BT_KELLYMIN=kellymin, BT_EP1BLOCK=ep1block, BT_OBSGUARD=obsguard,
               BT_VOLFILTER=volfilter, BT_S1DERATE=s1derate)
    r = subprocess.run([PY, "run_backtest.py"], cwd=SCRIPTS, env=env,
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        print(f"[FAIL] {label}: {r.stderr[-2000:]}")
        return None
    # 复制输出
    for seg in ("in", "oos"):
        src = os.path.join(OUT, f"results_{seg}.json")
        dst = os.path.join(OUT, f"results_{label}_{seg}.json")
        shutil.copy(src, dst)
    res_in = M.load_res(f"results_{label}_in.json")
    res_oos = M.load_res(f"results_{label}_oos.json")
    mi = M.compute_all(res_in, bench_in, f"{label}-样本内", 72)
    mo = M.compute_all(res_oos, bench_oos, f"{label}-样本外", 18)
    summary = {
        "config": {"label": label, "score_gate": sg, "obs_gate": og, "variant": var,
                   "fixl5": fixl5, "r1": r1, "r2": r2, "r3": r3,
                   "kellymin": kellymin, "ep1block": ep1block, "obsguard": obsguard,
                   "volfilter": volfilter, "s1derate": s1derate},
        "in": {"final": res_in["final_equity"], "buys": len(res_in["buys"]),
               "closed": len(res_in["closed"]), "obs_stats": res_in["obs_stats"]},
        "oos": {"final": res_oos["final_equity"], "buys": len(res_oos["buys"]),
                "closed": len(res_oos["closed"]), "obs_stats": res_oos["obs_stats"]},
        "metrics_in": mi, "metrics_oos": mo,
        "buys_in": res_in["buys"], "buys_oos": res_oos["buys"],
        "closed_in": res_in["closed"], "closed_oos": res_oos["closed"],
    }
    with open(os.path.join(OUT, f"variant_{label}.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1, default=str)
    print(f"[OK] {label}: in_final={res_in['final_equity']:.0f} "
          f"buys={len(res_in['buys'])}+{len(res_oos['buys'])} "
          f"obs_entries={res_in['obs_stats']['entries']} "
          f"| oos_final={res_oos['final_equity']:.0f}")
    return summary


if __name__ == "__main__":
    results = {}
    for cfg in CONFIGS:
        label, sg, og, var, fixl5, r1, r2, r3, kellymin, ep1block, obsguard = cfg
        print(f"=== 运行 {label} (gate={sg}/{og}, {var}, F={fixl5}R1={r1}R2={r2}R3={r3} K={kellymin} E={ep1block} O={obsguard}) ===")
        s = run_one(label, sg, og, var, fixl5, r1, r2, r3, kellymin, ep1block, obsguard)
        if s:
            results[label] = s
    print("\n===== 汇总 =====")
    print(f"{'配置':<6}{'门槛':<9}{'开关F/R1R2R3/K/E/O':<22}{'内终值':>10}{'内建仓':>6}{'内观察':>6}"
          f"{'外终值':>10}{'外建仓':>6}{'外观察':>6}")
    for cfg in CONFIGS:
        label, sg, og, var, fixl5, r1, r2, r3, kellymin, ep1block, obsguard = cfg
        if label not in results:
            continue
        s = results[label]
        sw = f"{fixl5}{r1}{r2}{r3}/{kellymin}/{ep1block}/{obsguard}"
        print(f"{label:<6}{f'{sg}/{og}':<9}{sw:<22}"
              f"{s['in']['final']:>10.0f}{s['in']['buys']:>6}{s['in']['obs_stats']['entries']:>6}"
              f"{s['oos']['final']:>10.0f}{s['oos']['buys']:>6}{s['oos']['obs_stats']['entries']:>6}")

