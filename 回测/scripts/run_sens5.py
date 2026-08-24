# -*- coding: utf-8 -*-
"""第五轮敏感性批次: E-P1 带宽 × E-P9.5 资格门槛（基于 D6r 完整修复）"""
import os, sys, json, subprocess, shutil
sys.path.insert(0, os.path.dirname(__file__))
import run_variant as RV

OUT = RV.OUT
PY = RV.PY
SCRIPTS = RV.SCRIPTS

# (label, ep1_pct, qual_gate)
SENS = [
    ("D6r",       "3.0", "85"),   # 基准复验（参数化无副作用验证）
    ("S5a",       "5.0", "85"),   # E-P1 3%→5%
    ("S5b",       "5.0", "80"),   # + E-P9.5 85→80
    ("S5c",       "7.0", "80"),   # 更宽止损 + 更低资格门槛
]

def run_sens(label, ep1_pct, qual_gate):
    env = dict(os.environ, BT_SCORE_GATE="70", BT_OBS_GATE="78", BT_TRE_VARIANT="V1",
               BT_FIXL5="1", BT_R1="1", BT_R2="1", BT_R3="1",
               BT_KELLYMIN="1", BT_EP1BLOCK="1", BT_OBSGUARD="1",
               BT_EP1PCT=ep1_pct, BT_QUALGATE=qual_gate)
    r = subprocess.run([PY, "run_backtest.py"], cwd=SCRIPTS, env=env,
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        print(f"[FAIL] {label}: {r.stderr[-1500:]}")
        return None
    for seg in ("in", "oos"):
        shutil.copy(os.path.join(OUT, f"results_{seg}.json"),
                    os.path.join(OUT, f"results_{label}_{seg}.json"))
    res_in = RV.M.load_res(f"results_{label}_in.json")
    res_oos = RV.M.load_res(f"results_{label}_oos.json")
    mi = RV.M.compute_all(res_in, RV.bench_in, f"{label}-样本内", 72)
    mo = RV.M.compute_all(res_oos, RV.bench_oos, f"{label}-样本外", 18)
    summary = {"config": {"label": label, "ep1_pct": ep1_pct, "qual_gate": qual_gate},
               "in": {"final": res_in["final_equity"], "buys": len(res_in["buys"]),
                      "closed": len(res_in["closed"]), "obs_stats": res_in["obs_stats"],
                      "intercept": res_in["stats"]["intercept"]},
               "oos": {"final": res_oos["final_equity"], "buys": len(res_oos["buys"]),
                       "closed": len(res_oos["closed"]), "obs_stats": res_oos["obs_stats"]},
               "metrics_in": mi, "metrics_oos": mo,
               "buys_in": res_in["buys"], "buys_oos": res_oos["buys"],
               "closed_in": res_in["closed"], "closed_oos": res_oos["closed"]}
    with open(os.path.join(OUT, f"variant_{label}.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1, default=str)
    print(f"[OK] {label} (EP1={ep1_pct}%, QUAL={qual_gate}): "
          f"in={res_in['final_equity']:.0f} buys={len(res_in['buys'])} "
          f"| oos={res_oos['final_equity']:.0f} buys={len(res_oos['buys'])}", flush=True)
    return summary

if __name__ == "__main__":
    for cfg in SENS:
        run_sens(*cfg)
    print("SENS DONE", flush=True)
