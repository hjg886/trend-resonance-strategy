# -*- coding: utf-8 -*-
"""
B3 每日信号扫描（模拟盘工具，2026-08-21 新增）【已退休 · 归档副本】
========================================
用途: 每日盘后扫描观察池24只个股, 输出次日可执行的 B3 建仓信号清单

口径: 与 run_attack_b.py B3 变体逐行一致（阶段1锁定, 2026-08-18）
  - TRE状态: compute_tre_states（沪深300/SH/SZ 状态机, V1 + obs_guard）
  - 市场vol20: 沪深300近20日年化波动率（注意: 闸门A/B为"市场级"而非个股级）
  - 闸门A: vol20 >= 10（B3 回测: BT_VOL_GATE_A_THRESH=10）
  - 闸门B: 市场vol20 >= 20 且 TRE∈{S1,S2} → 禁建仓（B3 未覆盖阈值=默认20; TRE=S3 不受限, 正常建仓[非试探仓]）
  - TRE过滤: ∈{S1,S2,S3} 非 S4
  - 熔断: 沪深300 T-1跌幅>=2% → 当日禁建仓（meltdown_level >= 1）
  - 个股: 简化技术评分>=73（趋势50+动量30+流动性20，2026-09-07 优化落地 70→73）+ amount20>=5000万 + ATR20P<=10
  - 仓位: 5%/笔, 最多5笔并发, 总仓25%（台账记录时应用, 扫描不涉及）

用法:
  python scan_b3_daily.py [--date YYYY-MM-DD]
  --date: 指定判定基准日（默认 = 数据最后交易日）
输出:
  控制台: 市场状态面板 + 24只个股信号表 + PASS清单
  归档:   output/b3_daily_scan_<date>.json

[2026-09-07 退休说明] B3 日度扫描统一为 72 池（cand_meta.json），由 B3信号单.py 承担；
本 24 池扫描通道已废弃，仅保留此副本于 05_临时与废弃/ 供回溯。请勿在新流程中调用。
"""
import os, sys, json, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_attack_b import (load_all, build_panels, compute_tre_states,
                          OBS_POOL, CORE_IDX)
from engine import Portfolio


def simple_score_detail(row):
    """简化技术评分明细版: 返回 (总分, 趋势, 动量, 流动性)
    与 run_attack_b.simple_stock_score 逻辑逐行一致, 额外返回三部分分解
    """
    import numpy as np
    # 趋势 50
    tr = 0.0
    tr += 12.0 if row.get("MA60SLOPE") == 1 else (5.0 if row.get("MA60SLOPE") == 0 else 0.0)
    tr += 13.0 if row.get("DEV60", -999) > 0 else 0.0
    al = row.get("MAALIGN", 0)
    tr += 12.0 if al == 3 else (7.0 if al == 2 else 0.0)
    tr += 13.0 if row.get("ret60", -1) > 0 else 3.0
    tr = min(50, tr)
    # 动量 30
    mo = 0.0
    r5 = row.get("ret5", 0); r20 = row.get("ret20", 0); r60 = row.get("ret60", 0)
    mo += 10.0 * np.clip((r5 + 2) / 8, 0, 1) if r5 > -2 else 0.0
    mo += 10.0 * np.clip((r20 + 5) / 15, 0, 1) if r20 > -5 else 0.0
    mo += 10.0 * np.clip((r60 + 10) / 30, 0, 1) if r60 > -10 else 0.0
    mo = min(30, mo)
    # 流动性 20
    li = 0.0
    amt20 = row.get("amount20", 0)
    li += 10.0 * np.clip(np.log10(amt20 / 1e8 + 0.1) / 1.2, 0, 1) if amt20 > 0 else 0.0
    vol_ratio = row.get("VOLRATIO", 1.0)
    li += 10.0 * np.clip(vol_ratio / 2.5, 0, 1)
    li = min(20, li)
    return round(min(100, tr + mo + li), 1), round(tr, 1), round(mo, 1), round(li, 1)

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "output")
os.makedirs(OUT, exist_ok=True)

# B3 锁定参数（阶段1, 2026-08-18）→ 2026-09-07 优化落地 v2: SCORE 70→73
VOL_GATE_A = 10.0   # 闸门A: 市场vol20 >= 10
VOL_GATE_B = 20.0   # 闸门B: 市场vol20 >= 20 且 TRE∈{S1,S2} → 禁
SCORE_MIN = 73.0    # 2026-09-07 优化落地 70→73（对齐 run_attack_b.py B3 v2 / B3评分.py）
AMT_MIN = 5e7       # 日均成交额 >= 5000万
ATR_MAX = 10.0      # ATR20P <= 10%
MAX_POS = 5         # 最多5笔并发


def scan(date: str | None = None):
    panels0 = load_all()
    panels = build_panels(panels0)
    days = list(panels["idx_hs300"].index)
    tre_states = compute_tre_states(panels, days)

    T = date if date else days[-1]
    if T not in days:
        print(f"[ERROR] 判定日 {T} 不在数据范围内 (数据止于 {days[-1]})")
        return
    ti = days.index(T)
    t1 = days[ti - 1] if ti >= 1 else T

    # ---------- 市场状态（与回测口径一致: tre_states[T], t1数据评分） ----------
    hs300_ret = panels["idx_hs300"]["close"].pct_change()
    vol20 = float(hs300_ret.loc[:t1].tail(20).std(ddof=1) * np.sqrt(252) * 100)
    tre_state, obs_active, avg_adx = tre_states.get(T, ("S3", False, 20.0))

    pf = Portfolio()
    melt = pf.meltdown_level(float(panels["idx_hs300"].loc[t1, "pct_chg"]))
    melt_block = melt >= 1

    gate_a_block = vol20 < VOL_GATE_A
    gate_b_block = vol20 >= VOL_GATE_B and tre_state in ("S1", "S2")
    tre_block = tre_state == "S4"

    if melt_block:
        market_perm = f"禁建仓（熔断{melt}级: 沪深300 T-1跌幅{panels['idx_hs300'].loc[t1, 'pct_chg']:.2f}%≤-2%）"
    elif gate_a_block:
        market_perm = f"禁建仓（闸门A: 市场vol20={vol20:.1f}<{VOL_GATE_A:.0f}）"
    elif gate_b_block:
        market_perm = (f"禁建仓（闸门B: 市场vol20={vol20:.1f}≥{VOL_GATE_B:.0f} 且 TRE={tre_state}∈{{S1,S2}}, "
                       f"当日全禁, 与回测一致; TRE=S3 时不受闸门B限制, 可正常建仓）")
    elif tre_block:
        market_perm = f"禁建仓（TRE={tre_state}, 观察通道{'(开启)' if obs_active else '(关闭)'}）"
    else:
        market_perm = "开放"

    # ---------- 个股扫描（t1 评分, 与回测一致） ----------
    stocks = []
    for code, (dn, name, ind) in OBS_POOL.items():
        if dn not in panels or t1 not in panels[dn].index:
            stocks.append({"code": code, "name": name, "industry": ind,
                           "status": "无数据", "pass": False})
            continue
        row = panels[dn].loc[t1]
        score, tr, mo, li = simple_score_detail(row)
        amt20 = float(row.get("amount20", 0))
        atr20p = float(row.get("ATR20P", 0))
        close = float(row["close"])
        ret5 = float(row.get("ret5", 0))
        ret20 = float(row.get("ret20", 0))
        ret60 = float(row.get("ret60", 0))
        ma60 = float(row.get("MA60", 0))
        dev60 = float(row.get("DEV60", 0))
        vol_ratio = float(row.get("VOLRATIO", 1.0))

        fails = []
        if score < SCORE_MIN:
            fails.append(f"评分{score:.1f}<{SCORE_MIN:.0f}")
        if amt20 < AMT_MIN:
            fails.append(f"成交额{amt20/1e8:.2f}亿<5000万")
        if atr20p > ATR_MAX:
            fails.append(f"ATR{atr20p:.1f}%>{ATR_MAX:.0f}%")

        stocks.append({
            "code": code, "name": name, "industry": ind,
            "close": round(close, 2), "score": score,
            "trend": tr, "mom": mo, "liq": li,
            "ret5": round(ret5, 2), "ret20": round(ret20, 2), "ret60": round(ret60, 2),
            "ma60": round(ma60, 2), "dev60": round(dev60, 2),
            "amt20_yi": round(amt20 / 1e8, 2), "atr20p": round(atr20p, 2),
            "vol_ratio": round(vol_ratio, 2),
            "pass": not fails, "fails": fails,
        })

    pass_list = [s for s in stocks if s["pass"]]
    pass_list.sort(key=lambda s: s["score"], reverse=True)

    # ---------- 输出 ----------
    print("=" * 78)
    print(f"  B3 每日信号扫描 | 判定基准日 {T}（T-1={t1} 评分） | 数据至 {days[-1]}")
    print("=" * 78)
    print(f"  市场状态: TRE={tre_state} | 观察通道={'开启' if obs_active else '关闭'} | ADX={avg_adx:.1f}")
    print(f"  市场vol20(沪深300): {vol20:.2f}% | 闸门A({VOL_GATE_A:.0f})={'✅' if not gate_a_block else '❌'} "
          f"| 闸门B({VOL_GATE_B:.0f}禁S1/S2)={'✅' if not gate_b_block else '❌'} "
          f"| TRE非S4={'✅' if not tre_block else '❌'} | 熔断={'✅' if not melt_block else f'❌(级{melt})'}")
    print(f"  当日建仓权限: {market_perm}")
    print("-" * 78)
    print(f"  {'代码':<8s}{'名称':<8s}{'评分':>6s}{'收盘':>9s}{'成交额亿':>9s}{'ATR%':>7s}{'5日':>7s}"
          f"{'20日':>7s}{'60日':>8s}  判定")
    print("-" * 78)
    for s in stocks:
        mark = "✅PASS" if s["pass"] else "❌" + (s["fails"][0] if s["fails"] else "")
        if s.get("status") == "无数据":
            print(f"  {s['code']:<8s}{s['name']:<8s}  {'—':<6s}  无数据")
            continue
        print(f"  {s['code']:<8s}{s['name']:<8s}{s['score']:>6.1f}{s['close']:>9.2f}"
              f"{s['amt20_yi']:>9.2f}{s['atr20p']:>7.1f}{s['ret5']:>7.2f}"
              f"{s['ret20']:>7.2f}{s['ret60']:>8.2f}  {mark}")
    print("-" * 78)
    print(f"  PASS清单（{len(pass_list)}只, 按评分降序, 最多同时持{MAX_POS}笔）:")
    for i, s in enumerate(pass_list, 1):
        print(f"    {i}. {s['code']} {s['name']} 评分{s['score']:.1f} "
              f"(趋势{s['trend']:.0f}+动量{s['mom']:.0f}+流动{s['liq']:.0f}) "
              f"收盘{s['close']:.2f} 成交额{s['amt20_yi']:.2f}亿 ATR{s['atr20p']:.1f}%")
    if not pass_list:
        print("    （无）")

    # ---------- 归档 ----------
    rec = {
        "scan_date": T, "rating_date": t1, "data_through": days[-1],
        "market": {
            "tre": tre_state, "obs_active": obs_active, "avg_adx": round(avg_adx, 2),
            "vol20": round(vol20, 2), "gate_a_pass": not gate_a_block,
            "gate_b_pass": not gate_b_block, "tre_pass": not tre_block,
            "meltdown": melt, "meltdown_block": melt_block,
            "permission": market_perm,
        },
        "stocks": stocks,
        "pass_list": [s["code"] for s in pass_list],
        "n_pass": len(pass_list),
        "generated_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
    }
    out_file = os.path.join(OUT, f"b3_daily_scan_{T}.json")
    with open(out_file, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    print(f"\n  归档: {out_file}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="判定基准日 YYYY-MM-DD（默认=数据最后交易日）")
    args = ap.parse_args()
    scan(args.date)
