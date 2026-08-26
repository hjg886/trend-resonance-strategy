# -*- coding: utf-8 -*-
"""
主引擎环境监控（提频路径②·环境恢复监控机制, 2026-08-24）
用途: 每日盘后输出主引擎口径的市场环境面板 + 可建仓窗口判定 + 环境恢复趋势，
      监控 R-04 双闸门 / TRE / BREADTH / 熔断，识别"可建仓窗口"何时恢复，
      为提频路径②（环境自然恢复 +0~2笔/年）提供量化监控。

口径（与回测 run_backtest.py 一致, 勿混入 B3 参数）:
  R-04 闸门A: 市场vol20 < 15 → 禁一切建仓
  R-04 闸门B: 市场vol20 >= 20 且 TRE∈{S1,S2} → 禁S1/S2常规（S3有限+观察通道不受限）
  正常区:     vol20 ∈ [15, 20)
  BREADTH:   < 15 → 否决层（禁建仓）; 缺失默认30=中性
  TRE:        S4 禁一切（观察通道开启期间可10%试探仓）; S3 有限建仓; S1/S2 常规
  熔断:       沪深300 T-1 跌幅 <= -2% 起
综合判定（可建仓窗口）: 非熔断 + 非闸门A + 非闸门B + TRE≠S4 + BREADTH>=15 → "开放"
                       任一不满足 → 给出具体阻塞项（支持多因并列）
输出:
  控制台: 环境面板 + 窗口状态 + 历史恢复统计
  归档:   output/env_daily_scan_<date>.json
"""
import os, sys, json, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_attack_b import load_all, build_panels, compute_tre_states
from engine import Portfolio

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "output")
os.makedirs(OUT, exist_ok=True)

# ---- 主引擎锁定参数（R-04 + BREADTH, 与回测一致） ----
VOL_GATE_A = 15.0   # 闸门A: vol20 < 15 禁一切
VOL_GATE_B = 20.0   # 闸门B: vol20 >= 20 且 TRE∈{S1,S2} 禁常规
BREADTH_MIN = 15.0  # BREADTH < 15 否决层
MHD_CSV = os.path.join(OUT, "mhd_scores.csv")
HIST_DAYS = [20, 60, 120, 250]  # 环境恢复趋势统计窗口

# ---- v5.0 动态观察池排除名单（2026-08-25 用户指令：药明康德 603259 移出观察池） ----
# 仅过滤"每日观察池扫描输出"，绝不修改 bt.UNIVERSE / #167 个股通道回测（保持可复现）。
# 代码格式：用裸6位代码（与 UNIVERSE 键一致），如 "603259"；为兼容亦接受带前缀形式（如 "sh603259"）。
# 扩展排除其他标的：在此集合追加代码即可，例如 {"603259", "300760"}。
OBS_POOL_EXCLUDE = {"603259"}

# ---- 观察池清空开关（2026-08-26 用户指令：清空当前观察池候选所有标的） ----
# True = 扫描强制返回空池（临时关闭观察池，不影响 bt.UNIVERSE / #167 回测可复现）；
# 恢复观察池时，将此开关改回 False 即可（OBS_POOL_EXCLUDE 名单保持不变）。
OBS_POOL_CLEAR_ALL = True


def load_breadth():
    import pandas as pd
    if not os.path.exists(MHD_CSV):
        print(f"[WARN] MHD scores not found at {MHD_CSV}, BREADTH=30 中性默认")
        return {}
    df = pd.read_csv(MHD_CSV, dtype={"date": str})
    df["date"] = df["date"].astype(str).str[:10]
    return dict(zip(df["date"], df["BREADTH"]))


def env_state(panels, tre_states, breadth_map, days, T):
    """计算 T 日（T-1 数据）的环境状态（与回测口径一致）"""
    ti = days.index(T)
    t1 = days[ti - 1] if ti >= 1 else T
    hs300_ret = panels["idx_hs300"]["close"].pct_change()
    vol20 = float(hs300_ret.loc[:t1].tail(20).std(ddof=1) * np.sqrt(252) * 100)
    tre_state, obs_active, avg_adx = tre_states.get(T, ("S3", False, 20.0))
    brd = float(breadth_map.get(t1, 30.0))
    pf = Portfolio()
    melt = pf.meltdown_level(float(panels["idx_hs300"].loc[t1, "pct_chg"]))
    pct = float(panels["idx_hs300"].loc[t1, "pct_chg"])

    gate_a = vol20 < VOL_GATE_A
    gate_b = vol20 >= VOL_GATE_B and tre_state in ("S1", "S2")
    tre_block = tre_state == "S4"
    brd_block = brd < BREADTH_MIN
    melt_block = melt >= 1

    blocks = []
    if melt_block:
        blocks.append(f"熔断{melt}级(T-1沪深300 {pct:.2f}%)")
    if gate_a:
        blocks.append(f"闸门A(vol20={vol20:.1f}<{VOL_GATE_A:.0f})")
    if gate_b:
        blocks.append(f"闸门B(vol20={vol20:.1f}≥{VOL_GATE_B:.0f}且TRE={tre_state})")
    if tre_block:
        blocks.append(f"TRE=S4(观察通道{'开启' if obs_active else '关闭'})")
    if brd_block:
        blocks.append(f"BREADTH={brd:.1f}<{BREADTH_MIN:.0f}")
    window = "开放" if not blocks else "受限/关闭"

    # 观察通道提示（路径③联动）
    obs_tip = ""
    if tre_state == "S4" and obs_active:
        obs_tip = "S4加速恢复观察通道开启→可10%试探仓（F-30, 个股+宽基, 禁行业ETF）"
    elif tre_state == "S3":
        obs_tip = "S3有限建仓开放（观察通道未开启, 常规S3条款）"

    return {
        "date": T, "t1": t1,
        "vol20": round(vol20, 2), "vol_zone": "A禁区(<15)" if gate_a else ("B禁区(≥20)" if vol20 >= VOL_GATE_B else "正常区[15,20)"),
        "tre": tre_state, "obs_active": obs_active, "adx": round(float(avg_adx), 1),
        "breadth": round(brd, 1), "breadth_block": brd_block,
        "melt": melt, "melt_block": melt_block,
        "gate_a_block": gate_a, "gate_b_block": gate_b, "tre_block": tre_block,
        "window": window, "blocks": blocks, "obs_tip": obs_tip,
        "pct_chg_t1": round(pct, 2),
    }


def hist_stats(panels, tre_states, breadth_map, days, T):
    """近 N 日窗口的开放天数占比（环境恢复趋势）"""
    ti = days.index(T)
    lo = max(0, ti - max(HIST_DAYS))
    win_days = days[lo:ti + 1]
    stats = {}
    for n in HIST_DAYS:
        seg = win_days[-n:]
        cnt = 0
        for d in seg:
            st = env_state(panels, tre_states, breadth_map, days, d)
            if st["window"] == "开放":
                cnt += 1
        stats[str(n)] = {"days": len(seg), "open_days": cnt,
                         "open_ratio": round(cnt / max(len(seg), 1), 3)}
    return stats


def scan_obs_pool(exclude, gate_stock=70.0, gate_etf=75.0):
    """v5.0 动态观察池：遍历主引擎 UNIVERSE，复用 run_backtest.compute_score（24因子同源），
    输出得分≥门槛的候选（个股≥70 / ETF≥75，#167 + P0dCore 口径），排除 EXCLUDE 集合。
    返回 (pool_list, excluded_list)。注意：本函数只读取 UNIVERSE，不修改它（#167 回测可复现）。"""
    import run_backtest as RB
    panels0, fins = RB.load_all()
    panels = RB.build_panels(panels0)
    if "idx_hs300" not in panels:
        return [], []
    days = list(panels["idx_hs300"].index)
    T = days[-1]
    if OBS_POOL_CLEAR_ALL:
        return [], []
    pool, excluded = [], []
    for code, (dn, name, ptype, ind) in RB.UNIVERSE.items():
        if code in exclude or dn in exclude:
            excluded.append({"code": code, "name": name, "reason": "OBS_POOL_EXCLUDE名单"})
            continue
        if dn not in panels:
            continue
        df = panels[dn]
        if T not in df.index:
            continue
        row = df.loc[T]
        try:
            sc = float(RB.compute_score(code, dn, ptype, row, fins, panels))
        except Exception as e:
            continue
        if not np.isfinite(sc):
            continue
        gate = gate_stock if ptype == "stock" else gate_etf
        close_v = float(row["close"]) if np.isfinite(float(row["close"])) else None
        if sc >= gate:
            pool.append({"code": code, "name": name, "ptype": ptype,
                         "score": round(sc, 1), "gate": gate,
                         "close": round(close_v, 3) if close_v is not None else None,
                         "date": T})
    pool.sort(key=lambda x: x["score"], reverse=True)
    return pool, excluded


def main(date: str | None = None):
    panels0 = load_all()
    panels = build_panels(panels0)
    days = list(panels["idx_hs300"].index)
    tre_states = compute_tre_states(panels, days)
    breadth_map = load_breadth()

    T = date if date else days[-1]
    if T not in days:
        print(f"[ERROR] 判定日 {T} 不在数据范围 (数据止于 {days[-1]})")
        return

    st = env_state(panels, tre_states, breadth_map, days, T)
    hs = hist_stats(panels, tre_states, breadth_map, days, T)

    print("=" * 64)
    print(f"  主引擎环境面板（T={T}, T-1数据）")
    print("=" * 64)
    print(f"  TRE状态: {st['tre']} | 观察通道={'开启' if st['obs_active'] else '关闭'} | ADX={st['adx']}")
    print(f"  市场vol20(沪深300): {st['vol20']}% [{st['vol_zone']}]")
    print(f"  闸门A(<{VOL_GATE_A:.0f}禁一切): {'✅' if not st['gate_a_block'] else '❌'}"
          f" | 闸门B(≥{VOL_GATE_B:.0f}禁S1S2): {'✅' if not st['gate_b_block'] else '❌'}")
    melt_txt = "✅" if not st["melt_block"] else "❌(级%d)" % st["melt"]
    print(f"  BREADTH: {st['breadth']} {'✅' if not st['breadth_block'] else f'❌(<{BREADTH_MIN:.0f}否决)'}"
          f" | 熔断: {melt_txt}")
    print(f"  >>> 可建仓窗口: 【{st['window']}】" + ("" if st["window"] == "开放" else f" 阻塞: {' + '.join(st['blocks'])}"))
    if st["obs_tip"]:
        print(f"  >>> {st['obs_tip']}")
    print("-" * 64)
    print("  环境恢复趋势（开放日占比, 窗口越大越接近历史常态）:")
    for n in HIST_DAYS:
        s = hs[str(n)]
        print(f"    近{n:>3}日: {s['open_days']}/{s['days']} = {s['open_ratio']*100:.0f}%")
    print("=" * 64)

    # ---- v5.0 动态观察池候选（得分≥门槛过滤 + EXCLUDE 排除） ----
    pool, excluded = scan_obs_pool(OBS_POOL_EXCLUDE)
    print(f"  📋 动态观察池候选: {len(pool)} 只（得分≥门槛, 已排除 {sorted(OBS_POOL_EXCLUDE)}）")
    for r in pool[:15]:
        print(f"    · {r['code']} {r['name']:<10} [{r['ptype']}] 得分{r['score']:.1f}/门槛{r['gate']:.0f} 收{r['close']}")
    if excluded:
        print(f"  🚫 排除名单生效: {', '.join(e['name'] + '(' + e['code'] + ')' for e in excluded)}")
    print("=" * 64)

    rec = {"env": st, "hist": hs, "window": st["window"], "blocks": st["blocks"],
           "obs_pool": pool, "obs_excluded": excluded, "obs_exclude_list": sorted(OBS_POOL_EXCLUDE)}
    out_file = os.path.join(OUT, f"env_daily_scan_{T}.json")
    with open(out_file, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    print(f"[归档] {out_file}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="判定日 YYYY-MM-DD（默认最后交易日）")
    args = ap.parse_args()
    main(args.date)
