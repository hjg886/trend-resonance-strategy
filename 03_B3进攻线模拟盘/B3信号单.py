# -*- coding: utf-8 -*-
"""
B3 进攻线 · 每日信号单（纯 Python 评分，市场状态复用回测口径）
================================================================
整合：TRE 状态判定（回测口径） + 市场闸门（B3 专用 A/B + 熔断） + 72 只候选池评分
入场门槛（须同时满足，对齐 run_attack_b.py B3 变体，阶段1锁定 2026-08-18）：
  ① 当日建仓权限开放（熔断 / 闸门A vol20≥10 / 闸门B vol20<20 或 TRE=S3 / TRE≠S4）
  ② 简化技术评分 ≥ 73（趋势50+动量30+流动性20）
  ③ 个股三条件（本脚本内联过滤）：评分≥73(趋势50+动量30+流动20) + 成交额≥5000万(amt20_yi≥0.5) + ATR20P≤10
  → 三者全过方为"可执行信号"；归档 回测/output/b3_daily_scan_YYYY-MM-DD.json（替代退休的 scan_b3_daily.py 产物）
说明：
  - TRE 状态 = run_attack_b.compute_tre_states（沪深300/SH/SZ 状态机 V1+obs_guard），
    与 B3 阶段1回测完全一致（⚠️ 勿用 pre_market_calc.py 的简化矩阵，两者判定不同，
    深证单日暴跌会经 any-vol20>25 误触发 S4）。
  - B3 回测无 BREADTH 门槛（BREADTH 否决层是主引擎口径），此处 BREADTH 仅供信息参考。
  - 扫描池 = cand_meta.json 72 只（B3 唯一信号池, 2026-09-07 起替代原 24 只 OBS_POOL 扫描）。
  - 评分口径: B3评分.py 简化技术评分(趋势50+动量30+流动性20), 与 run_attack_b.simple_stock_score
    同源; 本脚本为日度唯一扫描通道（scan_b3_daily.py 24 池已退休, 移入 05_临时与废弃/）。
"""
import csv, io, json, math, os, sys, datetime

ROOT = r"E:\fnOS\文档\证券\中线趋势共振策略"
DATA = os.path.join(ROOT, "回测", "data")
OUT = os.path.join(ROOT, "回测", "output")
META = os.path.join(ROOT, "回测", "tmp", "sectors", "cand_meta.json")
SCRIPTS = os.path.join(ROOT, "回测", "scripts")
sys.path.insert(0, SCRIPTS)

# ---------------- 市场状态（回测口径） ----------------
import numpy as np
from run_attack_b import load_all, build_panels, compute_tre_states
from engine import Portfolio

VOL_GATE_A = 10.0   # 闸门A: 市场vol20 >= 10（B3 回测 BT_VOL_GATE_A_THRESH）
VOL_GATE_B = 20.0   # 闸门B: 市场vol20 >= 20 且 TRE∈{S1,S2} → 禁（B3 默认值）
SCORE_MIN = 73.0  # 2026-09-07 优化落地 70→73

def market_state():
    """回测口径市场状态: 返回 dict（TRE/观察通道/vol20/闸门/熔断/当日权限）"""
    panels0 = load_all()
    panels = build_panels(panels0)
    days = list(panels["idx_hs300"].index)
    tre_states = compute_tre_states(panels, days)
    T = days[-1]
    ti = days.index(T)
    t1 = days[ti - 1] if ti >= 1 else T

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
        perm = f"禁建仓（熔断{melt}级: 沪深300 T-1跌幅{panels['idx_hs300'].loc[t1, 'pct_chg']:.2f}%≤-2%）"
    elif gate_a_block:
        perm = f"禁建仓（闸门A: 市场vol20={vol20:.1f}<{VOL_GATE_A:.0f}）"
    elif gate_b_block:
        perm = (f"禁建仓（闸门B: 市场vol20={vol20:.1f}≥{VOL_GATE_B:.0f} 且 TRE={tre_state}∈{{S1,S2}}, "
                f"当日全禁, 与回测一致; TRE=S3 时不受闸门B限制, 可正常建仓）")
    elif tre_block:
        perm = f"禁建仓（TRE={tre_state}, 观察通道{'开启' if obs_active else '关闭'}）"
    else:
        perm = "开放"

    return {
        "date": T, "rating_date": t1, "data_through": days[-1],
        "tre": tre_state, "obs_active": obs_active, "avg_adx": avg_adx,
        "vol20": vol20, "gate_a_block": gate_a_block, "gate_b_block": gate_b_block,
        "tre_block": tre_block, "meltdown": melt, "meltdown_block": melt_block,
        "permission": perm, "open": not (melt_block or gate_a_block or gate_b_block or tre_block),
    }


# ---------------- BREADTH 代理（信息参考，非门槛） ----------------
def breadth_proxy():
    rows = []
    with io.open(os.path.join(DATA, "idx_hs300.csv"), "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append(float(r["close"]))
    up = sum(1 for i in range(len(rows) - 5, len(rows)) if rows[i] > rows[i - 1])
    return round(up / 5 * 30, 1)


# ---------------- 评分（对齐 simple_stock_score / B3评分.py） ----------------
def clip(x, lo, hi):
    return max(lo, min(hi, x))

def score_stock(rows):
    """B3 简化技术评分（趋势50 + 动量30 + 流动性20），对齐 B3评分.py / run_attack_b.simple_stock_score。
    返回 dict: tr/mo/li/total + 风控字段 amt20_yi(20日均成交额,亿) / atrp(ATR20%) /
               dev60 / r5 / r20 / r60 / ma60 / close / vr(量比)。
    """
    closes = [r["close"] for r in rows]
    highs  = [r["high"] for r in rows]
    lows   = [r["low"] for r in rows]
    volumes = [r["volume"] for r in rows]
    amounts = [r["amount"] for r in rows]
    n = len(closes)
    if n < 65:
        return None
    ma60 = sum(closes[-60:]) / 60
    ma120 = sum(closes[-120:]) / 120 if n >= 120 else ma60
    ma60_5ago = sum(closes[-65:-5]) / 60
    slope = 1 if ma60 > ma60_5ago else (-1 if ma60 < ma60_5ago else 0)
    dev60 = (closes[-1] / ma60 - 1) * 100
    if closes[-1] > ma60 and ma60 > ma120: al = 3
    elif closes[-1] > ma60 and ma60 <= ma120: al = 2
    elif closes[-1] <= ma60 and ma60 > ma120: al = 1
    else: al = 0
    r5 = (closes[-1] / closes[-6] - 1) * 100
    r20 = (closes[-1] / closes[-21] - 1) * 100
    r60 = (closes[-1] / closes[-61] - 1) * 100
    amt20 = sum(amounts[-20:]) / 20
    amt20_yi = amt20 / 1e8
    vr = volumes[-1] / (sum(volumes[-5:]) / 5) if sum(volumes[-5:]) > 0 else 1.0
    # ATR20（真实波幅均值）
    trs = []
    for i in range(1, n):
        h, l, c0 = highs[i], lows[i], closes[i - 1]
        trs.append(max(h - l, abs(h - c0), abs(l - c0)))
    atr20 = sum(trs[-20:]) / 20 if len(trs) >= 20 else 0.0
    atrp = atr20 / closes[-1] * 100 if closes[-1] > 0 else 0.0
    tr = 0.0
    tr += 12.0 if slope == 1 else (5.0 if slope == 0 else 0.0)
    tr += 13.0 if dev60 > 0 else 0.0
    tr += 12.0 if al == 3 else (7.0 if al == 2 else 0.0)
    tr += 13.0 if r60 > 0 else 3.0
    tr = min(50.0, tr)
    mo = 0.0
    mo += 10.0 * clip((r5 + 2) / 8, 0, 1) if r5 > -2 else 0.0
    mo += 10.0 * clip((r20 + 5) / 15, 0, 1) if r20 > -5 else 0.0
    mo += 10.0 * clip((r60 + 10) / 30, 0, 1) if r60 > -10 else 0.0
    mo = min(30.0, mo)
    li = 0.0
    li += 10.0 * clip(math.log10(amt20 / 1e8 + 0.1) / 1.2, 0, 1) if amt20 > 0 else 0.0
    li += 10.0 * clip(vr / 2.5, 0, 1)
    li = min(20.0, li)
    return {
        "tr": tr, "mo": mo, "li": li, "total": min(100.0, tr + mo + li),
        "amt20_yi": amt20_yi, "atrp": atrp, "dev60": dev60,
        "r5": r5, "r20": r20, "r60": r60, "ma60": ma60,
        "close": closes[-1], "vr": vr,
    }


def main():
    with io.open(META, "r", encoding="utf-8") as f:
        meta = json.load(f)
    names, codes = meta["names"], meta["M"]

    ms = market_state()
    breadth = breadth_proxy()

    print("=" * 74)
    print("B3 进攻线 · 每日信号单（市场状态=回测口径 run_attack_b / B3评分.py 口径评分）")
    print("=" * 74)
    print(f"判定基准日: {ms['date']}（T-1={ms['rating_date']} 评分） | 数据至 {ms['data_through']}")
    print(f"TRE 状态: {ms['tre']}（回测状态机 V1+obs_guard）| 观察通道={'开启' if ms['obs_active'] else '关闭'} | ADX={ms['avg_adx']:.1f}")
    melt_txt = "✅" if not ms["meltdown_block"] else ("❌(级%d)" % ms["meltdown"])
    print(f"市场vol20(沪深300): {ms['vol20']:.2f}% | 闸门A({VOL_GATE_A:.0f})={'✅' if not ms['gate_a_block'] else '❌'} "
          f"| 闸门B({VOL_GATE_B:.0f}禁S1/S2)={'✅' if not ms['gate_b_block'] else '❌'} "
          f"| TRE非S4={'✅' if not ms['tre_block'] else '❌'} | 熔断={melt_txt}")
    print(f"当日建仓权限: {ms['permission']}")
    print(f"BREADTH[代理]: {breadth}/30（近5日上涨占比；仅供信息，B3 回测无此门槛）")
    print("-" * 74)
    rows_out = []
    missing = []
    stale = []
    for code in codes:
        c6 = code.replace("sh", "").replace("sz", "")
        path = os.path.join(DATA, f"stk_{c6}.csv")
        if not os.path.exists(path):
            missing.append(c6)
            continue
        with io.open(path, "r", encoding="utf-8-sig") as f:
            data = [{"date": r["date"], "close": float(r["close"]), "high": float(r["high"]),
                     "low": float(r["low"]), "volume": float(r["volume"]),
                     "amount": float(r["amount"])} for r in csv.DictReader(f)]
        if not data:
            missing.append(c6)
            continue
        # 失效股过滤: 数据截止过旧（退市/长期停牌, 如 688287 观典防务 2026-06-10 摘牌）
        if data[-1]["date"] < ms["data_through"] and \
           (datetime.date.fromisoformat(ms["data_through"]) - datetime.date.fromisoformat(data[-1]["date"])).days > 90:
            stale.append(f"{c6} {names.get(code, '')}（数据止于{data[-1]['date']}，疑似退市/长期停牌）")
            continue
        sc = score_stock(data)
        if sc is None:
            missing.append(c6)
            continue
        # 个股三条件（B3 台账口径）: 评分≥73 + 成交额≥5000万(amt20_yi≥0.5) + ATR20P≤10
        fails = []
        if sc["total"] < SCORE_MIN:
            fails.append(f"评分{sc['total']:.1f}<{SCORE_MIN:.0f}")
        if sc["amt20_yi"] < 0.5:
            fails.append(f"成交额{sc['amt20_yi']:.2f}亿<0.5亿")
        if sc["atrp"] > 10:
            fails.append(f"ATR20P{sc['atrp']:.2f}>10")
        passed = len(fails) == 0
        rows_out.append({
            "code": c6, "name": names.get(code, ""), "close": sc["close"],
            "score": sc["total"], "trend": sc["tr"], "mom": sc["mo"], "liq": sc["li"],
            "amt20_yi": round(sc["amt20_yi"], 2), "atr20p": round(sc["atrp"], 2),
            "vol_ratio": round(sc["vr"], 2), "dev60": round(sc["dev60"], 2),
            "ret5": round(sc["r5"], 2), "ret20": round(sc["r20"], 2), "ret60": round(sc["r60"], 2),
            "ma60": round(sc["ma60"], 2), "pass": passed, "fails": fails,
        })
    rows_out.sort(key=lambda x: -x["score"])
    print(f"{'代码':<7}{'名称':<9}{'总分':>7}{'成交额(亿)':>11}{'ATR20%':>9}  {'信号'}")
    for r in rows_out:
        if r["score"] >= SCORE_MIN:
            if r["pass"] and ms["open"]:
                mark = "★可执行"
            elif not r["pass"]:
                mark = "≥73(个股未过)"
            else:
                mark = "≥73(环境暂阻)"
        else:
            mark = ""
        print(f"{r['code']:<7}{r['name']:<9}{r['score']:>7.1f}{r['amt20_yi']:>11.2f}{r['atr20p']:>9.2f}  {mark}")
    print("-" * 74)
    sigs = [r for r in rows_out if r["score"] >= SCORE_MIN]
    passed_sigs = [r for r in sigs if r["pass"]]
    print(f"\n【评分≥73】{len(sigs)} 只 / 全池 {len(rows_out)} 只有效数据 / 缺数据 {len(missing)} 只 / 失效(退市/停牌) {len(stale)} 只")
    if stale:
        for s in stale:
            print(f"  ⚠️ {s}")
    if sigs:
        for r in sigs:
            if r["pass"]:
                flag = "✅可执行(三条件全过)"
            else:
                flag = "⛔个股未过(" + ",".join(r["fails"]) + ")"
            print(f"  {r['code']} {r['name']} 总分{r['score']:.1f}（趋势{r['trend']:.1f}/动量{r['mom']:.1f}/流动{r['liq']:.1f}）"
                  f"成交额{r['amt20_yi']:.2f}亿 ATR{r['atr20p']:.2f}% → {flag}")
    print(f"\n【结论】{'建仓权限开放(B3独立窗口): 评分≥73且个股三条件过 即触发信号' if ms['open'] else '当日禁建仓(B3窗口): ' + ms['permission']}")
    if ms["open"] and passed_sigs:
        print(f"  → 可执行信号 {len(passed_sigs)} 只（按台账流程：次日开盘模拟成交）")
    elif ms["open"] and sigs and not passed_sigs:
        print(f"  → 评分达标 {len(sigs)} 只，但个股三条件未过，无可执行信号")
    elif not ms["open"] and sigs:
        print(f"  → 信号冻结 {len(sigs)} 只，待权限开放后按信号日顺序执行")
    if missing:
        print(f"\n【缺数据 {len(missing)} 只】（需 fetch_b3_pool.py 补 K 线）")

    # ---- 归档 72 池信号单 JSON（替代退休的 scan_b3_daily.py 产物） ----
    os.makedirs(OUT, exist_ok=True)
    out = {
        "scan_date": ms["date"], "rating_date": ms["rating_date"], "data_through": ms["data_through"],
        "market": {
            "tre": ms["tre"], "obs_active": ms["obs_active"], "avg_adx": ms["avg_adx"],
            "vol20": ms["vol20"], "gate_a_pass": not ms["gate_a_block"],
            "gate_b_pass": not ms["gate_b_block"], "tre_pass": not ms["tre_block"],
            "meltdown": ms["meltdown"], "meltdown_block": ms["meltdown_block"],
            "permission": ms["permission"],
        },
        "breadth_proxy": breadth,
        "stocks": rows_out,
        "pass_list": [r["code"] for r in passed_sigs],
        "n_pass": len(passed_sigs),
        "n_score_ge73": len(sigs),
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    out_path = os.path.join(OUT, f"b3_daily_scan_{ms['date']}.json")
    with io.open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n[归档] {out_path}  (可执行 {len(passed_sigs)} 只 / 评分≥73 {len(sigs)} 只 / 全池 {len(rows_out)} 只)")


if __name__ == "__main__":
    main()
