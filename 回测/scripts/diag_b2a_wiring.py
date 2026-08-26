# -*- coding: utf-8 -*-
"""
diag_b2a_wiring.py —— 路径 A 复扫接线诊断（秒级，不跑完整回测）
目的:
  1) 验证 BT_B2_MOM_SCALE 是否真正驱动 etf_score (接线校验)
  2) 解释 sweep_b2a 4 组结果为何完全一致 (ETF 评分是否结构性低于建仓门槛)
方法:
  复用 run_backtest 真实数据管线 + compute_score(→etf_score)，在 4 个 mom 值下
  对 OOS 窗口全部 ETF 计算评分，统计 #>=70 / #>=75 与分布。
判定:
  - 若各 mom 的 mean/median/max 明显不同 → 接线 OK，mom 生效；
  - 若所有 mom 的 #>=门槛 皆为 0 → B2 结构把 ETF 压在门槛下，与 mom 无关 → 0 建仓 → 个股部分主导 → OOS 一致。
"""
import os, sys, time, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_backtest as RB

os.environ["BT_B2_ON"] = "1"
os.environ["BT_B2_EST_W"] = "25"
os.environ["BT_B2_VOL_W"] = "20"

t0 = time.time()
print("== 加载数据管线 ==", flush=True)
panels0, fins = RB.load_all()
panels = RB.build_panels(panels0)
panels = RB.add_pit_pb(panels, fins)
days = list(panels["idx_hs300"].index)
oos_days = [d for d in days if RB.PERIOD_OOS[0] <= d <= RB.PERIOD_OOS[1]]
print(f"   数据加载 {time.time()-t0:.0f}s；OOS 交易日数={len(oos_days)}", flush=True)

etfs = [(c, RB.UNIVERSE[c][0], RB.UNIVERSE[c][2]) for c in RB.UNIVERSE
        if RB.UNIVERSE[c][2] in ("etf", "etf_ind")]
print(f"   ETF 标的数={len(etfs)}", flush=True)

MOMS = [0.5, 0.7, 0.85, 1.0]
print(f"\n{'mom':>5} {'n':>7} {'mean':>6} {'median':>6} {'p90':>6} {'max':>6} "
      f"{'#>=70':>6} {'%>=70':>6} {'#>=75':>6}", flush=True)
summary = {}
for mom in MOMS:
    os.environ["BT_B2_MOM_SCALE"] = str(mom)
    arr = []
    ge70 = ge75 = 0
    for code, dn, ptype in etfs:
        p = panels[dn]
        for d in oos_days:
            if d not in p.index:
                continue
            row = p.loc[d]
            if row.get("amount", 0) < 3000e4:   # 层级1 成交额硬过滤(代理)
                continue
            sc = RB.compute_score(code, dn, ptype, row, fins, panels)
            arr.append(sc)
            if sc >= 70:
                ge70 += 1
            if sc >= 75:
                ge75 += 1
    a = np.array(arr)
    summary[mom] = dict(n=int(a.size), mean=float(a.mean()), median=float(np.median(a)),
                        p90=float(np.percentile(a, 90)), mx=float(a.max()),
                        ge70=ge70, ge70_pct=float(ge70 / a.size * 100) if a.size else 0.0,
                        ge75=ge75)
    print(f"{mom:>5} {a.size:>7} {a.mean():>6.1f} {np.median(a):>6.1f} "
          f"{np.percentile(a,90):>6.1f} {a.max():>6.1f} {ge70:>6} "
          f"{ge70/a.size*100:>5.1f}% {ge75:>6}", flush=True)

# 接线判定: 比较 mom=0.5 与 mom=1.0 的分布差异
d_mean = summary[1.0]["mean"] - summary[0.5]["mean"]
d_max = summary[1.0]["mx"] - summary[0.5]["mx"]
print("\n== 接线判定 ==", flush=True)
print(f"   mom 1.0 vs 0.5: mean 差={d_mean:+.2f}  max 差={d_max:+.2f}", flush=True)
if abs(d_mean) > 0.01 or abs(d_max) > 0.01:
    print("   => 接线正常: BT_B2_MOM_SCALE 确实驱动 etf_score（动量分量随 mom 变化）", flush=True)
else:
    print("   => 异常: mom 对评分零影响，疑似接线断裂（env 未达 etf_score）", flush=True)
all_zero = all(s["ge70"] == 0 for s in summary.values())
print(f"   所有 mom 的 #>=70 是否均为 0: {all_zero}", flush=True)
if all_zero:
    print("   => 解释: B2 结构(est_w=25/vol_w=20)把 ETF 评分系统性压在 70 门槛下，"
          "任何 mom 值都 0 建仓；结果由与 mom 无关的个股部分主导 → OOS 一致。", flush=True)
    print("   => 路径 A 假设('降动量过度')被证伪: 即便 mom=1.0(满动量)仍 0 建仓。", flush=True)

with open(os.path.join(RB.OUT, "diag_b2a_wiring.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=1)
print(f"\nDONE 总耗时 {time.time()-t0:.0f}s → diag_b2a_wiring.json", flush=True)
