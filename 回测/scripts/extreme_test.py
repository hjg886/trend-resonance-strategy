# -*- coding: utf-8 -*-
"""
extreme_test.py —— 极端行情测试（v4.7-R8 第十六章）
7 个极端行情区间切片: 组合收益 vs 沪深300 对照
数据: output/results_in.json (逐日equity/TRE/仓位) + data/idx_hs300.csv
"""
import os, json
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "output")

WINDOWS = [
    ("E1-2020年2月疫情暴跌", "2020-02-03", "2020-03-31"),
    ("E2-2020年7月快速反弹", "2020-07-01", "2020-07-31"),
    ("E3-2021年2月抱团崩塌", "2021-02-18", "2021-03-31"),
    ("E4-2022年4月探底", "2022-04-01", "2022-04-29"),
    ("E5-2022年10月探底", "2022-10-01", "2022-10-31"),
    ("E6-2023年AI行情", "2023-02-01", "2023-06-30"),
    ("E7-2024年1月流动性危机", "2024-01-02", "2024-02-08"),
    ("E8-2024年高股息行情", "2024-01-02", "2024-05-31"),
]


def main():
    res = json.load(open(os.path.join(OUT, "results_in.json"), encoding="utf-8"))
    hist = res["hist"]
    eq_by_date = {h["date"]: h for h in hist}
    dates = [h["date"] for h in hist]

    bench = pd.read_csv(os.path.join(DATA, "idx_hs300.csv"), dtype={"date": str})
    bench["date"] = bench["date"].astype(str).str[:10]
    bench = bench.set_index("date").sort_index()

    rows = []
    for name, s, e in WINDOWS:
        seg = [h for h in hist if s <= h["date"] <= e]
        if len(seg) < 2:
            rows.append({"window": name, "start": s, "end": e, "n_days": 0,
                         "port_ret": None, "hs300_ret": None, "avg_pos": None,
                         "tre_s1": None, "tre_s2": None, "max_dd": None})
            continue
        p0, p1 = seg[0]["equity"], seg[-1]["equity"]
        port_ret = (float(p1) / float(p0) - 1.0) * 100.0
        b0 = float(bench.loc[s, "close"]) if s in bench.index else float(bench.loc[seg[0]["date"], "close"])
        b1 = float(bench.loc[e, "close"]) if e in bench.index else float(bench.loc[seg[-1]["date"], "close"])
        hs300_ret = (b1 / b0 - 1.0) * 100.0
        # 区间内平均仓位
        pos = [1.0 - float(h["cash"]) / max(float(h["equity"]), 1e-9) for h in seg]
        avg_pos = sum(pos) / len(pos) * 100.0
        tre_s1 = sum(1 for h in seg if h["tre"] == "S1")
        tre_s2 = sum(1 for h in seg if h["tre"] == "S2")
        # 区间内组合最大回撤（用净值序列重算）
        eqs = [float(h["equity"]) for h in seg]
        peak = max(eqs)
        mdd = (eqs[-1] - peak) / peak * 100.0
        rows.append({"window": name, "start": s, "end": e, "n_days": len(seg),
                     "port_ret": round(port_ret, 2), "hs300_ret": round(hs300_ret, 2),
                     "excess": round(port_ret - hs300_ret, 2),
                     "avg_pos": round(avg_pos, 1), "tre_s1": tre_s1, "tre_s2": tre_s2,
                     "max_dd": round(mdd, 2)})

    out = {"windows": rows}
    with open(os.path.join(OUT, "extreme_test.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"{'区间':<26}{'天数':>5}{'组合%':>8}{'HS300%':>8}{'超额%':>8}{'均仓%':>7}{'S1':>5}{'S2':>5}")
    for r in rows:
        if r["n_days"] == 0:
            print(f"{r['window']:<26}  无数据")
            continue
        print(f"{r['window']:<26}{r['n_days']:>5}{r['port_ret']:>8}{r['hs300_ret']:>8}"
              f"{r['excess']:>8}{r['avg_pos']:>7}{r['tre_s1']:>5}{r['tre_s2']:>5}")


if __name__ == "__main__":
    main()
