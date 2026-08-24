# -*- coding: utf-8 -*-
"""离场预案卡计算器：解析K线 → TRE判定 → 四只持仓离场线
输入: /tmp/kline_all.txt (westockdata kline 输出)
输出: 控制台结构化结果 + output/exit_plan.json
"""
import re, json, math, io, os, sys

SRC = r"E:/fnOS/文档/证券/中线趋势共振策略/回测/tmp/kline_all.txt"
OUT = r"E:/fnOS/文档/证券/中线趋势共振策略/回测/output/exit_plan.json"

# ---------- 1. 解析K线 ----------
data = {}  # symbol -> list of {date, open, last, high, low}
cur = None
for line in io.open(SRC, encoding="utf-8"):
    line = line.strip()
    if not line.startswith("|"):
        continue
    cells = [c.strip() for c in line.strip("|").split("|")]
    if len(cells) < 8:
        continue
    sym, date, o, last, hi, lo = cells[0], cells[1], cells[2], cells[3], cells[4], cells[5]
    if sym == "symbol":
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
    """20日ATR（TR简单平均）"""
    if len(recs) < 21:
        return None
    trs = []
    for i in range(len(recs) - 20, len(recs)):
        h, l, pc = recs[i]["high"], recs[i]["low"], recs[i - 1]["last"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs)

def vol20_ann(recs):
    """20日年化波动率 %：近20日日收益std × sqrt(252)"""
    if len(recs) < 21:
        return None
    closes = [r["last"] for r in recs[-21:]]
    rets = [closes[i + 1] / closes[i] - 1 for i in range(len(closes) - 1)]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252) * 100

def adx14(recs):
    """ADX(14) 简化计算"""
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
    # 取最近 n+1 段做平滑（简化：直接平均）
    tr_avg = sum(trs[-n:]) / n
    pdi = sum(pdm[-n:]) / n / tr_avg * 100 if tr_avg > 0 else 0
    ndi = sum(ndm[-n:]) / n / tr_avg * 100 if tr_avg > 0 else 0
    dx = abs(pdi - ndi) / (pdi + ndi) * 100 if (pdi + ndi) > 0 else 0
    # ADX = DX的简单平均（用最近n个DX近似）
    return dx

def ma60_cross_count(recs, window=20):
    """近window个交易日MA60有效穿越次数（收盘价由下穿上/下穿下）"""
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

def tre_judge(recs):
    """TRE四态判定（沪深300口径）"""
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
        elif adx >= 15 and adx < 20:
            state, reason = "S2", f"ADX{adx:.0f}∈[15,20) 连2日观察"
        elif v20 >= 18 or cross > 3:
            state, reason = "S3", f"vol20={v20:.1f}≥18 或穿越{cross}>3"
        else:
            state, reason = "S2", f"接近S1未满足完整条件(vol20={v20:.1f} 或穿越{cross})"
    return {
        "last": last, "ma20": ma20, "ma60": ma60, "ma20_dir": ma20_dir,
        "bull_align": bull, "vol20": v20, "adx": adx, "cross": cross,
        "state": state, "reason": reason,
    }

# ---------- 3. 计算 ----------
res = {}
idx = tre_judge(data["sh000300"])
res["bench"] = idx
print("=== 沪深300 TRE判定 ===")
print(f"  最新收盘: {idx['last']:.2f} | MA20: {idx['ma20']:.2f}({idx['ma20_dir']}) | MA60: {idx['ma60']:.2f} | 多头排列: {idx['bull_align']}")
print(f"  ADX: {idx['adx']:.1f} | 近20日MA60穿越: {idx['cross']} | vol20: {idx['vol20']:.2f}%")
print(f"  TRE状态: {idx['state']} | 动因: {idx['reason']}")
print(f"  R-04闸门: vol20={idx['vol20']:.1f}% → {'闸门A禁建仓' if idx['vol20']<15 else ('正常区' if idx['vol20']<20 else '闸门B仅S3/观察通道')}")
print()

# 持仓参数：代码 → (名称, 买入日列表(日期,份数), 余量, 类型, TRE档位)
POS = {
    "sh600276": dict(name="恒瑞医药600276", buys=[("2026-07-01", 900)], qty=900, typ="股票",
                     time_stop=(60, 30), label="个股P0-P12"),
    "sz159650": dict(name="国开债ETF159650", buys=[("2026-06-04", 3600)], qty=1800, typ="ETF",
                     time_stop=(60, 30), label="ETF E-P0.0~E-P12"),
    "sh510300": dict(name="沪深300ETF510300", buys=[("2026-07-08", 24100), ("2026-07-09", 1600)], qty=40700, typ="ETF",
                     time_stop=(60, 30), label="ETF E-P0.0~E-P12"),
}

def trading_days_between(recs, buy_date):
    """买入日到最新交易日之间的交易日数（含起算：自买入日起）"""
    dates = [r["date"] for r in recs]
    if buy_date not in dates:
        return None
    i = dates.index(buy_date)
    return len(dates) - i  # 自买入日（含）起算的交易日数

def est_cost(recs, buy_date):
    """估算成本=买入日收盘价（标注估算）"""
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
    state = idx["state"]  # 组合TRE状态（策略口径=沪深300）
    # 持有期与成本
    buy_days = [trading_days_between(recs, bd) for bd, _ in p["buys"]]
    hold_days = max(buy_days) if all(bd is not None for bd in buy_days) else None
    costs = [est_cost(recs, bd) for bd, _ in p["buys"]]
    wsum = sum(c * q for (_, q), c in zip(p["buys"], costs) if c) if all(costs) else None
    qsum = sum(q for _, q in p["buys"])
    cost = wsum / qsum if wsum else None
    # P1/E-P1带宽：持有≤11日5% / >11日3%（R-06）
    band = 5.0 if (hold_days is not None and hold_days <= 11) else 3.0
    # 止损线 = 成本 - MIN(2×ATR, 带宽%)
    atr_term = 2 * a20 if a20 else 0
    band_term = cost * band / 100 if cost else 0
    stop_dist = min(atr_term, band_term) if (atr_term and band_term) else (atr_term or band_term)
    stop_line = cost - stop_dist if cost else None
    # 动态回撤清仓线（S3/S4提前一档）
    dd_warn = cost * 0.95 if cost else None       # -5%
    dd_half = cost * 0.92 if cost else None       # -8%
    dd_clear = cost * (0.89 if state in ("S3", "S4") else 0.88) if cost else None  # S3/S4:-11% S1/S2:-12%
    # 移动止损P12/E-P12：最高浮盈≥15%启用
    peak = max(r["high"] for r in recs)
    profit_peak = (peak / cost - 1) * 100 if cost else 0
    if profit_peak >= 15:
        if profit_peak < 30:
            p12 = peak * 0.5 + cost * 0.5  # 回撤50%：peak-(peak-cost)*50%
        elif profit_peak < 50:
            p12 = peak - (peak - cost) * 0.4
        else:
            p12 = peak - (peak - cost) * 0.3
    else:
        p12 = None
    # 时间止损剩余
    ts_days = p["time_stop"][0] if state == "S1" else p["time_stop"][1]
    ts_left = max(ts_days - hold_days, 0) if hold_days is not None else None
    # E-P0/E-P0.5 单ETF亏损线
    ep0 = cost * 0.92 if cost else None
    ep05 = cost * (0.89 if state in ("S3", "S4") else 0.88) if cost else None
    # 现价盈亏
    pnl_pct = (last / cost - 1) * 100 if cost else None

    r = dict(name=p["name"], typ=p["typ"], last=last, ma60=ma60, atr20=a20,
             vol20=v20, cost_est=cost, hold_days=hold_days, band=band,
             stop_line=stop_line, dd_warn=dd_warn, dd_half=dd_half, dd_clear=dd_clear,
             profit_peak=profit_peak, p12=p12, ts_days=ts_days, ts_left=ts_left,
             ep0=ep0, ep05=ep05, pnl_pct=pnl_pct, state=state)
    res[sym] = r
    print(f"=== {p['name']}（{p['typ']}）===")
    print(f"  最新收盘: {last:.3f} | MA60: {ma60:.3f} | 20日ATR: {a20:.4f} | vol20: {v20:.2f}%")
    print(f"  估算成本: {cost:.3f}（买入日收盘，请核对）| 持有: {hold_days}交易日 | 盈亏: {pnl_pct:+.2f}%")
    print(f"  R-06带宽: {band:.0f}% | P1止损线: {stop_line:.3f}（距成本 {stop_dist:.3f}）")
    print(f"  动态回撤: 预警{dd_warn:.3f}(-5%) / 减半{dd_half:.3f}(-8%) / 清仓{dd_clear:.3f}（{state}档{'S3/S4:-11%' if state in ('S3','S4') else 'S1/S2:-12%'}）")
    if p12:
        print(f"  P12移动止损: 启用（峰值浮盈{profit_peak:.1f}%）线={p12:.3f} | 与P1取更高: {max(stop_line, p12):.3f}")
    else:
        print(f"  P12移动止损: 未启用（峰值浮盈{profit_peak:.1f}%<15%）")
    if p["typ"] == "ETF":
        print(f"  E-P0/E-P0.5: {ep0:.3f}(-8%减半) / {ep05:.3f}(-{11 if state in ('S3','S4') else 12}%清仓)")
    print(f"  时间止损: {ts_days}日({state})已用{hold_days} 剩余{ts_left}交易日 | 13因子/资格每日盘后监控")
    print()

# 外高B（数据源为空，按档案）
res["sh900912"] = dict(name="外高B900912", typ="B股", note="数据源无最新K线；按档案：成本$1.276、MA60=0.619、剩余100股、08-07已卖4400股@0.641", state="独立持仓")
print("=== 外高B 900912 ===")
print("  数据源无最新K线；按档案管理：成本$1.276 / MA60=0.619 / 剩余100股")
print("  08-07已卖出4400股@$0.641，已实现亏损 $2,794(-49.77%)；策略不干预")
print()

# R-04闸门结论
print("=== R-04 波动率闸门结论（今日）===")
if idx["vol20"] is not None:
    if idx["vol20"] < 15:
        print(f"  vol20={idx['vol20']:.1f}% < 15% → 闸门A：禁止一切新建仓（存量管理不受影响）")
    elif idx["vol20"] < 20:
        print(f"  vol20={idx['vol20']:.1f}% ∈ [15,20) → 正常区：建仓权限✅（但重构6项未达标仍禁止实盘建仓）")
    else:
        print(f"  vol20={idx['vol20']:.1f}% ≥ 20% → 闸门B：仅S3有限建仓+观察通道")
print()

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(res, fh, ensure_ascii=False, indent=1, default=str)
print("saved:", OUT)
