# -*- coding: utf-8 -*-
"""v4.7-R10 每日执行评估器
解析K线 → TRE判定 + R-04闸门 + P9/E-P10大盘条款 + 四只持仓离场线 + E-P3检查
输入: 回测/tmp/kline_all.txt (westockdata kline 输出, 带symbol列统一格式)
输出: 控制台结构化结果 + 回测/output/r10_daily_<date>.json
用法: python calc_r10_daily.py
"""
import re, json, math, io, os, sys
from datetime import datetime

BASE = r"E:/fnOS/文档/证券/中线趋势共振策略"
SRC = BASE + "/回测/tmp/kline_all.txt"
OUT_DIR = BASE + "/回测/output"

# ---------- 1. 解析K线 ----------
data = {}
for line in io.open(SRC, encoding="utf-8"):
    line = line.strip()
    if not line.startswith("|"):
        continue
    cells = [c.strip() for c in line.strip("|").split("|")]
    if len(cells) < 8:
        continue
    sym, date, o, last, hi, lo = cells[0], cells[1], cells[2], cells[3], cells[4], cells[5]
    if sym in ("symbol", "date"):
        continue
    try:
        rec = {"date": date, "open": float(o), "last": float(last),
               "high": float(hi), "low": float(lo)}
    except ValueError:
        continue
    data.setdefault(sym, []).append(rec)

for k in list(data.keys()):
    data[k].sort(key=lambda r: r["date"])

# ---------- 2. 工具函数 ----------
def sma(vals, n):
    if len(vals) < n:
        return None
    return sum(vals[-n:]) / n

def atr20(recs):
    if len(recs) < 21:
        return None
    trs = []
    for i in range(len(recs) - 20, len(recs)):
        h, l, pc = recs[i]["high"], recs[i]["low"], recs[i - 1]["last"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs)

def vol20_ann(recs):
    if len(recs) < 21:
        return None
    closes = [r["last"] for r in recs[-21:]]
    rets = [closes[i + 1] / closes[i] - 1 for i in range(len(closes) - 1)]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252) * 100

def adx14(recs):
    if len(recs) < 30:
        return None
    n = 14
    trs, pdm, ndm = [], [], []
    for i in range(1, len(recs)):
        h, l, ph, pl = recs[i]["high"], recs[i]["low"], recs[i - 1]["high"], recs[i - 1]["low"]
        tr = max(h - l, abs(h - ph), abs(l - pl))
        up, dn = h - ph, pl - l
        pdm.append(up if (up > dn and up > 0) else 0.0)
        ndm.append(dn if (dn > up and dn > 0) else 0.0)
        trs.append(tr)
    tr_avg = sum(trs[-n:]) / n
    pdi = sum(pdm[-n:]) / n / tr_avg * 100 if tr_avg > 0 else 0
    ndi = sum(ndm[-n:]) / n / tr_avg * 100 if tr_avg > 0 else 0
    dx = abs(pdi - ndi) / (pdi + ndi) * 100 if (pdi + ndi) > 0 else 0
    return dx

def ma60_cross_count(recs, window=20):
    if len(recs) < 62:
        return None
    ma60 = [sma([r["last"] for r in recs[:i + 1]], 60) for i in range(len(recs))]
    cnt = 0
    start = len(recs) - window
    for i in range(start + 1, len(recs)):
        a, b = ma60[i - 1], ma60[i]
        if a is None or b is None:
            continue
        p1, p2 = recs[i - 1]["last"] - a, recs[i]["last"] - b
        if (p1 <= 0 < p2) or (p1 >= 0 > p2):
            cnt += 1
    return cnt

def ma60_slope_pct(recs, days=5):
    """MA60 近days日斜率%：现MA60/前days日MA60 - 1"""
    if len(recs) < 60 + days:
        return None
    closes = [r["last"] for r in recs]
    ma_now = sum(closes[-60:]) / 60
    ma_prev = sum(closes[-60 - days:-days]) / 60
    return (ma_now / ma_prev - 1) * 100

def tre_judge(recs):
    closes = [r["last"] for r in recs]
    ma20 = sma(closes, 20)
    ma60 = sma(closes, 60)
    v20 = vol20_ann(recs)
    adx = adx14(recs)
    cross = ma60_cross_count(recs)
    last = closes[-1]
    ma20_dir = "↑" if ma20 and len(closes) >= 21 and ma20 > sma(closes[:-1], 20) else "↓"
    bull = (ma20 and ma60 and ma20 > ma60)
    state, reason = None, ""
    if adx is not None and v20 is not None and cross is not None:
        s1_full = adx >= 20 and cross <= 3 and v20 < 18
        if s1_full:
            state, reason = "S1", f"ADX{adx:.0f}≥20 穿越{cross}≤3 vol20={v20:.1f}<18"
        elif 15 <= adx < 20:
            state, reason = "S2", f"ADX{adx:.0f}∈[15,20)"
        # R7修复P1-1：ADX≥20但未满足S1完整条件（vol20≥18 或 穿越>3）→ S2（接近S1不完整），非S3
        elif adx >= 20 and (v20 >= 18 or cross > 3):
            state, reason = "S2", f"接近S1未满足完整条件(vol20={v20:.1f}≥18 或穿越{cross}>3)"
        elif v20 >= 25:
            state, reason = "S4", f"vol20={v20:.1f}≥25 风暴市"
        elif adx < 15 and 3 <= cross <= 4 and 15 <= v20 < 25:
            state, reason = "S3", f"ADX{adx:.0f}<15 穿越{cross} 3-4次 vol20={v20:.1f}"
        else:
            state, reason = "S2", f"接近S1未满足完整条件(vol20={v20:.1f} 或穿越{cross})"
    # P9/E-P10: 连续3日收盘<MA60
    below_ma60_days = 0
    if ma60:
        for r in reversed(recs):
            if r["last"] < ma60:
                below_ma60_days += 1
            else:
                break
    return {
        "last": last, "ma20": ma20, "ma60": ma60, "ma20_dir": ma20_dir,
        "bull_align": bull, "vol20": v20, "adx": adx, "cross": cross,
        "state": state, "reason": reason, "below_ma60_days": below_ma60_days,
    }

# ---------- 3. 计算 ----------
res = {}
idx = tre_judge(data["sh000300"])
res["bench"] = idx
res["meta"] = {"data_date": data["sh000300"][-1]["date"],
               "note": "数据为westockdata日K；当日数据可能为盘中时点，收盘后需复核"}
print("=" * 60)
print(f"=== 沪深300 TRE判定（数据日期 {idx['last'] and data['sh000300'][-1]['date']}）===")
print(f"  最新: {idx['last']:.2f} | MA20: {idx['ma20']:.2f}({idx['ma20_dir']}) | MA60: {idx['ma60']:.2f} | 多头: {idx['bull_align']}")
print(f"  ADX: {idx['adx']:.1f} | 近20日MA60穿越: {idx['cross']} | vol20: {idx['vol20']:.2f}%")
print(f"  TRE状态: {idx['state']} | 动因: {idx['reason']}")
# R-04 闸门
gate = "正常区" if (idx["vol20"] is not None and 15 <= idx["vol20"] < 20) else ("闸门A禁建仓" if idx["vol20"] is not None and idx["vol20"] < 15 else ("闸门B仅S3/观察通道" if idx["vol20"] is not None else "数据不足"))
print(f"  R-04闸门: vol20={idx['vol20']:.1f}% → {gate}")
# P9/E-P10 大盘条款
p9 = idx["below_ma60_days"] >= 3
print(f"  P9/E-P10: 沪深300连续{idx['below_ma60_days']}日收盘<MA60 → {'⚠️ 触发：总仓位压缩至20%以内(个股)/持仓减至30%以下(ETF)' if p9 else '未触发'}")
print()

POS = {
    "sh600276": dict(name="恒瑞医药600276", buys=[("2026-07-01", 900)], qty=900, typ="股票",
                     time_stop=(60, 30), label="个股P0-P12"),
    "sz159650": dict(name="国开债ETF159650", buys=[("2026-06-04", 3600)], qty=1800, typ="ETF",
                     time_stop=(60, 30), label="ETF E-P0.0~E-P12"),
    "sh510300": dict(name="沪深300ETF510300", buys=[("2026-07-08", 24100), ("2026-07-09", 1600)], qty=40700, typ="ETF",
                     time_stop=(60, 30), label="ETF E-P0.0~E-P12"),
}

def trading_days_between(recs, buy_date):
    dates = [r["date"] for r in recs]
    if buy_date not in dates:
        return None
    i = dates.index(buy_date)
    return len(dates) - i

def est_cost(recs, buy_date):
    for r in recs:
        if r["date"] == buy_date:
            return r["last"]
    return None

for sym, p in POS.items():
    recs = data[sym]
    closes = [r["last"] for r in recs]
    last = closes[-1]
    ma60 = sma(closes, 60)
    a20 = atr20(recs)
    v20 = vol20_ann(recs)
    state = idx["state"]
    buy_days = [trading_days_between(recs, bd) for bd, _ in p["buys"]]
    hold_days = max(buy_days) if all(bd is not None for bd in buy_days) else None
    costs = [est_cost(recs, bd) for bd, _ in p["buys"]]
    wsum = sum(c * q for (_, q), c in zip(p["buys"], costs) if c) if all(costs) else None
    qsum = sum(q for _, q in p["buys"])
    cost = wsum / qsum if wsum else None
    band = 5.0 if (hold_days is not None and hold_days <= 11) else 3.0
    atr_term = 2 * a20 if a20 else 0
    band_term = cost * band / 100 if cost else 0
    stop_dist = min(atr_term, band_term) if (atr_term and band_term) else (atr_term or band_term)
    stop_line = cost - stop_dist if cost else None
    dd_warn = cost * 0.95 if cost else None
    dd_half = cost * 0.92 if cost else None
    dd_clear = cost * (0.89 if state in ("S3", "S4") else 0.88) if cost else None
    peak = max(r["high"] for r in recs)
    profit_peak = (peak / cost - 1) * 100 if cost else 0
    p12 = None
    if profit_peak >= 15:
        if profit_peak < 30:
            p12 = peak * 0.5 + cost * 0.5
        elif profit_peak < 50:
            p12 = peak - (peak - cost) * 0.4
        else:
            p12 = peak - (peak - cost) * 0.3
    ts_days = p["time_stop"][0] if state == "S1" else p["time_stop"][1]
    ts_left = max(ts_days - hold_days, 0) if hold_days is not None else None
    ep0 = cost * 0.92 if cost else None
    ep05 = cost * (0.89 if state in ("S3", "S4") else 0.88) if cost else None
    pnl_pct = (last / cost - 1) * 100 if cost else None
    # E-P3: MA60走平(5日斜率<0.2%) 且 价格连续≥2日<MA60
    ep3_trigger = False
    ep3_detail = ""
    if p["typ"] == "ETF":
        slope = ma60_slope_pct(recs)
        below_days = 0
        for r in reversed(recs):
            if ma60 and r["last"] < ma60:
                below_days += 1
            else:
                break
        ep3_trigger = (slope is not None and abs(slope) < 0.2 and below_days >= 2)
        ep3_detail = f"MA60斜率{slope:+.3f}%/日 价格连续{below_days}日<MA60"

    r = dict(name=p["name"], typ=p["typ"], last=last, ma60=ma60, atr20=a20,
             vol20=v20, cost_est=cost, hold_days=hold_days, band=band,
             stop_line=stop_line, dd_warn=dd_warn, dd_half=dd_half, dd_clear=dd_clear,
             profit_peak=profit_peak, p12=p12, ts_days=ts_days, ts_left=ts_left,
             ep0=ep0, ep05=ep05, pnl_pct=pnl_pct, state=state,
             ep3_trigger=ep3_trigger, ep3_detail=ep3_detail)
    res[sym] = r
    print(f"=== {p['name']}（{p['typ']}）===")
    print(f"  最新: {last:.3f} | MA60: {ma60:.3f} | ATR20: {a20:.4f} | vol20: {v20:.2f}%")
    print(f"  估算成本: {cost:.3f}（买入日收盘，请核对）| 持有: {hold_days}交易日 | 盈亏: {pnl_pct:+.2f}%")
    print(f"  R-06带宽: {band:.0f}% | P1/E-P1止损线: {stop_line:.3f}")
    print(f"  动态回撤: 预警{dd_warn:.3f} / 减半{dd_half:.3f} / 清仓{dd_clear:.3f}（{state}档）")
    if p12:
        print(f"  P12移动止损: 启用(峰值{profit_peak:.1f}%) 线={p12:.3f} | 与P1取更高: {max(stop_line, p12):.3f}")
    else:
        print(f"  P12移动止损: 未启用(峰值{profit_peak:.1f}%<15%)")
    if p["typ"] == "ETF":
        print(f"  E-P0/E-P0.5: {ep0:.3f}(-8%) / {ep05:.3f}(清仓)")
        print(f"  E-P3检查: {'⚠️ 触发→清仓' if ep3_trigger else '未触发'}（{ep3_detail}）")
    print(f"  时间止损: {ts_days}日({state}) 已用{hold_days} 剩余{ts_left}交易日")
    print(f"  P1距离: {(last - stop_line) / cost * 100:+.2f}%（现价距止损线）" if stop_line else "")
    print()

res["sh900912"] = dict(name="外高B900912", typ="B股", note="数据源无最新K线；按档案：成本$1.276、MA60=0.619、剩余100股、08-07已卖4400股@0.641", state="独立持仓")
print("=== 外高B 900912 ===")
print("  数据源无最新K线；按档案管理：成本$1.276 / MA60=0.619 / 剩余100股；策略不干预")
print()

print("=== R-04 波动率闸门结论 ===")
if idx["vol20"] is not None:
    if idx["vol20"] < 15:
        print(f"  vol20={idx['vol20']:.1f}% < 15% → 闸门A：禁止一切新建仓")
    elif idx["vol20"] < 20:
        print(f"  vol20={idx['vol20']:.1f}% ∈ [15,20) → 正常区（但重构6项未达标：实盘趋势建仓仍禁止，仅模拟盘）")
    else:
        print(f"  vol20={idx['vol20']:.1f}% ≥ 20% → 闸门B：仅S3有限建仓+观察通道")
print(f"\n=== 版本执行状态：v4.7-R10（G系列未达标）===")
print("  新建仓：❌ 禁止实盘趋势建仓（阶段0模拟盘主导）；存量持仓：✅ 按原规则管理")
if p9:
    print("  ⚠️ P9/E-P10 触发：总仓位压缩至20%以内（个股口径）/持仓减至30%以下（ETF口径）")
print()

data_date = res["meta"]["data_date"]
out_path = f"{OUT_DIR}/r10_daily_{data_date}.json"
with open(out_path, "w", encoding="utf-8") as fh:
    json.dump(res, fh, ensure_ascii=False, indent=1, default=str)
print("saved:", out_path)
