# -*- coding: utf-8 -*-
"""
P0-B 转换表变体模拟（任务#87）
V0: 现行 3.2 转换表（无 S2→S4）
V1: + S2→S4 当日生效（raw=S4 且名义=S2 → 当日名义=S4）[重设计]
V2: V1 + S3 判定窗口放宽（穿越3-5, vol≤30）
统计: 名义状态分布 / S4 天数 / 观察通道触发机会 / S1可建仓天数 / S2减半天数 / S3有限建仓天数
"""
import sys, os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from indicators import indicator_panel
from tre import raw_state

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data")
CORE_IDX = ["idx_hs300", "idx_sh", "idx_sz"]


def load_csv(name):
    df = pd.read_csv(os.path.join(DATA, f"{name}.csv"), dtype={"date": str})
    df["date"] = df["date"].astype(str).str[:10]
    return df.set_index("date").sort_index()


def build_daily():
    P = {nm: indicator_panel(load_csv(nm)) for nm in CORE_IDX}
    hs = P["idx_hs300"]
    ret = hs["close"].pct_change()
    days = [d for d in hs.index if d >= "2018-06-01" and d <= "2024-12-31"]
    out = []
    for i, d in enumerate(days):
        if i < 65:
            continue
        adx = [float(P[x].loc[d, "ADX14"]) for x in CORE_IDX]
        cross = float(hs.loc[d, "CROSS20"])
        vol = float(ret.loc[:d].tail(20).std(ddof=1) * np.sqrt(252) * 100)
        below = (hs["close"] < hs["MA60"]).astype(int).loc[:d]
        streak = 0
        for v in below.iloc[::-1]:
            if v == 1:
                streak += 1
            else:
                break
        gt = bool(hs.loc[d, "close"] > hs.loc[d, "MA60"])
        out.append({"date": d, "adx": adx, "cross": cross, "vol": vol,
                    "streak": float(streak), "gt": gt})
    return out


def raw3(r, vol_hi=25, cross_hi=4, adx_weak=15):
    """S3 判定: 多数指数 ADX<adx_weak 且 穿越3-cross_hi 且 波动率15-vol_hi"""
    n_weak = sum(1 for a in r["adx"] if a < adx_weak)
    return n_weak > 1 and 3 <= r["cross"] <= cross_hi and 15 <= r["vol"] <= vol_hi


def raw4(r):
    n_weak = sum(1 for a in r["adx"] if a < 15)
    return (n_weak > 1 and r["cross"] >= 5) or r["vol"] > 25


def raw1(r):
    n_strong = sum(1 for a in r["adx"] if a >= 20)
    return n_strong >= 2 and r["cross"] <= 3 and r["vol"] < 18


def sim(rows, variant):
    """variant: 'V0' | 'V1' | 'V2'"""
    state = "S2"
    buf_s23, buf_s21, buf_s43, buf_s42, buf_s32 = 0, 0, 0, 0, 0
    hist = []
    obs_trigger_chances = 0   # S4 状态期间出现 ADX≥2强 + 站稳MA60 的连续日
    obs_trigger = 0           # 连续2日满足 → 观察通道
    obs_confirm = 0
    obs_active_days = 0
    s4_days = 0
    for r in rows:
        r1, r3, r4 = raw1(r), raw3(r, vol_hi=(30 if variant == "V2" else 25),
                                  cross_hi=(5 if variant == "V2" else 4)), raw4(r)
        raw = "S1" if r1 else ("S4" if r4 else ("S3" if r3 else "S2"))

        # ---- 转换（含变体） ----
        if state == "S1":
            if raw != "S1":
                state = "S2"
        elif state == "S2":
            if raw == "S3":
                buf_s23 += 1
                if buf_s23 >= 2:
                    state = "S3"; buf_s23 = 0
            elif raw == "S4" and variant in ("V1", "V2"):
                state = "S4"          # 【重设计】S2→S4 当日生效
                buf_s23 = 0; buf_s21 = 0
            else:
                buf_s23 = 0
                if raw == "S1":
                    buf_s21 += 1
                    if buf_s21 >= 2:
                        state = "S1"; buf_s21 = 0
                else:
                    buf_s21 = 0
        elif state == "S3":
            if raw == "S4":
                state = "S4"
            elif raw == "S2":
                buf_s32 += 1
                if buf_s32 >= 2:
                    state = "S2"; buf_s32 = 0
            else:
                buf_s32 = 0
        elif state == "S4":
            if raw == "S3":
                buf_s43 += 1
                if buf_s43 >= 3:
                    state = "S3"; buf_s43 = 0
            else:
                buf_s43 = 0
                if raw == "S2":
                    buf_s42 += 1
                    if buf_s42 >= 2:
                        state = "S2"; buf_s42 = 0
                else:
                    buf_s42 = 0

        # ---- 观察通道触发（S4 名义状态期间） ----
        if state == "S4":
            s4_days += 1
            n_strong = sum(1 for a in r["adx"] if a >= 20)
            stand = r["gt"]
            if n_strong >= 2 and stand:
                obs_confirm += 1
                if obs_confirm >= 2:
                    obs_trigger += 1
                    obs_confirm = 0
            else:
                obs_confirm = 0
        else:
            obs_confirm = 0

        hist.append(state)
    hs_ = pd.Series(hist)
    return {
        "dist": {s: float((hs_ == s).mean() * 100) for s in ["S1", "S2", "S3", "S4"]},
        "s4_days": s4_days,
        "obs_trigger": obs_trigger,
        "total_days": len(hist),
    }


def main():
    rows = build_daily()
    print(f"总交易日: {len(rows)}（2018-06预热 + 2019-2024样本内）\n")
    print(f"{'变体':<6}{'S1%':>7}{'S2%':>7}{'S3%':>7}{'S4%':>7}{'S4天':>6}{'观察通道触发':>12}")
    for v in ["V0", "V1", "V2"]:
        r = sim(rows, v)
        d = r["dist"]
        print(f"{v:<6}{d['S1']:>6.1f}%{d['S2']:>6.1f}%{d['S3']:>6.1f}%{d['S4']:>6.1f}%"
              f"{r['s4_days']:>6}{r['obs_trigger']:>10}次")
    print("\n注: V0=现行转换表; V1=+S2→S4当日生效; V2=V1+S3窗口放宽(穿越3-5/vol≤30)")
    print("观察通道触发=连续2日(≥2核心ADX≥20且站稳MA60) 次数")


if __name__ == "__main__":
    main()
