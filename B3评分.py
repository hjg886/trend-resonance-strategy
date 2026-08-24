# -*- coding: utf-8 -*-
"""
B3 进攻线 · 个股精选评分脚本（纯 Python，不依赖 pandas）
========================================================
口径：与回测引擎 run_attack_b.py 的 simple_stock_score 完全一致
  趋势50(MA60SLOPE 12/5/0 + DEV60>0 13/0 + MAALIGN 12/7/0 + ret60>0 13/3)
  动量30(ret5 + ret20 + ret60，各10分 clip)
  流动性20(amount20 + VOLRATIO，各10分 clip)
入场：评分≥70 + 当日建仓权限开放（熔断/闸门A vol20≥10/闸门B vol20≥20 且 S1S2禁/TRE≠S4，
      回测口径见 B3信号单.py；⚠️ B3 回测无 BREADTH 门槛，BREADTH 否决层是主引擎口径）
"""
import csv, io, json, math, os, datetime

ROOT = r"E:\fnOS\文档\证券\中线趋势共振策略"
DATA = os.path.join(ROOT, "回测", "data")
META = os.path.join(ROOT, "回测", "tmp", "sectors", "cand_meta.json")

def clip(x, lo, hi):
    return max(lo, min(hi, x))

def load_meta():
    with io.open(META, "r", encoding="utf-8") as f:
        obj = json.load(f)
    names = obj["names"]
    codes = obj["M"]
    return codes, names

def load_csv(path):
    rows = []
    with io.open(path, "r", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append({
                "date": row["date"],
                "close": float(row["close"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "volume": float(row["volume"]),
                "amount": float(row["amount"]),
            })
    return rows

def calc_indicators(rows):
    closes = [r["close"] for r in rows]
    volumes = [r["volume"] for r in rows]
    amounts = [r["amount"] for r in rows]
    n = len(closes)
    if n < 65:
        return None
    # MA60 / MA120
    ma60 = sum(closes[-60:]) / 60
    ma120 = sum(closes[-120:]) / 120 if n >= 120 else ma60
    # MA60SLOPE：ma60.diff(5) 符号（当前 vs 5日前）
    ma60_5ago = sum(closes[-65:-5]) / 60
    slope = 1 if ma60 > ma60_5ago else (-1 if ma60 < ma60_5ago else 0)
    # DEV60（价格偏离度 %）
    dev60 = (closes[-1] / ma60 - 1) * 100
    # MAALIGN（3多头=close>ma60>ma120；2偏多；1偏空；0空头）
    if closes[-1] > ma60 and ma60 > ma120:
        maalign = 3
    elif closes[-1] > ma60 and ma60 <= ma120:
        maalign = 2
    elif closes[-1] <= ma60 and ma60 > ma120:
        maalign = 1
    else:
        maalign = 0
    # 涨幅 %
    ret5 = (closes[-1] / closes[-6] - 1) * 100
    ret20 = (closes[-1] / closes[-21] - 1) * 100
    ret60 = (closes[-1] / closes[-61] - 1) * 100
    # 流动性
    amt20 = sum(amounts[-20:]) / 20
    volratio = volumes[-1] / (sum(volumes[-5:]) / 5) if sum(volumes[-5:]) > 0 else 1.0
    return {
        "date": rows[-1]["date"], "close": closes[-1],
        "ma60": ma60, "ma60slope": slope, "dev60": dev60, "maalign": maalign,
        "ret5": ret5, "ret20": ret20, "ret60": ret60,
        "amt20": amt20, "volratio": volratio,
    }

def score(ind):
    # 趋势 50
    tr = 0.0
    tr += 12.0 if ind["ma60slope"] == 1 else (5.0 if ind["ma60slope"] == 0 else 0.0)
    tr += 13.0 if ind["dev60"] > 0 else 0.0
    al = ind["maalign"]
    tr += 12.0 if al == 3 else (7.0 if al == 2 else 0.0)
    tr += 13.0 if ind["ret60"] > 0 else 3.0
    tr = min(50.0, tr)
    # 动量 30
    mo = 0.0
    r5, r20, r60 = ind["ret5"], ind["ret20"], ind["ret60"]
    mo += 10.0 * clip((r5 + 2) / 8, 0, 1) if r5 > -2 else 0.0
    mo += 10.0 * clip((r20 + 5) / 15, 0, 1) if r20 > -5 else 0.0
    mo += 10.0 * clip((r60 + 10) / 30, 0, 1) if r60 > -10 else 0.0
    mo = min(30.0, mo)
    # 流动性 20
    li = 0.0
    amt20 = ind["amt20"]
    li += 10.0 * clip(math.log10(amt20 / 1e8 + 0.1) / 1.2, 0, 1) if amt20 > 0 else 0.0
    li += 10.0 * clip(ind["volratio"] / 2.5, 0, 1)
    li = min(20.0, li)
    return tr, mo, li, min(100.0, tr + mo + li)

def main():
    codes, names = load_meta()
    print("=" * 72)
    print("B3 进攻线 · 个股精选评分（纯 Python，口径对齐 simple_stock_score）")
    print("=" * 72)
    results = []
    missing = []
    stale = []
    # 失效股过滤基准: 全部有数据个股的最新日期
    ref_date = None
    for code in codes:
        c6 = code.replace("sh", "").replace("sz", "")
        path = os.path.join(DATA, f"stk_{c6}.csv")
        if os.path.exists(path):
            try:
                with io.open(path, "r", encoding="utf-8-sig") as f:
                    for row in csv.DictReader(f):
                        ref_date = row["date"] if ref_date is None or row["date"] > ref_date else ref_date
            except Exception:
                pass
    for code in codes:
        # sh688072 -> 688072
        c6 = code.replace("sh", "").replace("sz", "")
        path = os.path.join(DATA, f"stk_{c6}.csv")
        if not os.path.exists(path):
            missing.append(f"{c6} {names.get(code, '')}")
            continue
        rows = load_csv(path)
        if not rows:
            missing.append(f"{c6} {names.get(code, '')}（空文件）")
            continue
        # 失效股过滤: 数据截止过旧（退市/长期停牌, 如 688287 观典防务 2026-06-10 摘牌）
        if ref_date and (datetime.date.fromisoformat(ref_date) - datetime.date.fromisoformat(rows[-1]["date"])).days > 90:
            stale.append(f"{c6} {names.get(code, '')}（数据止于{rows[-1]['date']}，疑似退市/长期停牌）")
            continue
        ind = calc_indicators(rows)
        if ind is None:
            missing.append(f"{c6} {names.get(code, '')}（数据不足65日）")
            continue
        tr, mo, li, total = score(ind)
        results.append({
            "code": c6, "name": names.get(code, ""),
            "date": ind["date"], "close": ind["close"],
            "trend": tr, "mo": mo, "li": li, "total": total,
        })
    results.sort(key=lambda x: -x["total"])
    print(f"\n数据截止：{results[0]['date'] if results else '无数据'}（个股CSV，注意更新到 T-1）")
    print(f"有数据个股：{len(results)} 只 | 缺数据：{len(missing)} 只 | 失效(退市/停牌)：{len(stale)} 只\n")
    print(f"{'代码':<7}{'名称':<9}{'收盘':>8}{'趋势':>6}{'动量':>6}{'流动':>6}{'总分':>7}  {'信号'}")
    print("-" * 72)
    for r in results:
        sig = "★≥70" if r["total"] >= 70 else ""
        print(f"{r['code']:<7}{r['name']:<9}{r['close']:>8.2f}{r['trend']:>6.1f}{r['mo']:>6.1f}{r['li']:>6.1f}{r['total']:>7.1f}  {sig}")
    print("-" * 72)
    sigs = [r for r in results if r["total"] >= 70]
    print(f"\n【≥70分信号】{len(sigs)} 只：")
    for r in sigs:
        print(f"  {r['code']} {r['name']} 总分{r['total']:.1f}（趋势{r['trend']:.1f}/动量{r['mo']:.1f}/流动{r['li']:.1f}）")
    if missing:
        print(f"\n【缺数据 {len(missing)} 只】（需 fetch 补 K 线）")
        print("  " + "、".join(missing))
    if stale:
        print(f"\n【失效 {len(stale)} 只】（退市/长期停牌，不参与评分）")
        print("  " + "、".join(stale))
    print("\n⚠️ 环境前置：评分≥70 仅是第一步，仍需当日建仓权限开放（熔断/闸门A/B/TRE 回测口径，"
          "\n   见 B3信号单.py；B3 回测无 BREADTH 门槛）")

if __name__ == "__main__":
    main()
