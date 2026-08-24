# -*- coding: utf-8 -*-
"""
进攻线候选B：个股精选（简化入场）独立回测
===
阶段1历史定参回测 — 绕过主引擎24因子复杂过滤, 使用简化技术评分

主引擎瓶颈诊断（B1 IS 拦截统计）:
  R值C级: 3848次 / RPS: 2494次 / 闸门A(vol20<15): 617天(42.5%)
  → 24因子体系为趋势跟踪设计, 对进攻线个股精选过于严格

入场信号（简化版）:
  1. TRE状态 in {S1, S2, S3} (非S4, 个股极端下跌期风险过高)
  2. vol20 闸门可配置 (B1: B≥30 / B2: 得分≥75 / B3: A≥10)
  3. 简化技术评分 ≥ 阈值 (趋势50 + 动量30 + 流动性20 = 100)
  4. 仓位: 5%/笔, 最多5笔并发

出场信号:
  - P12v6 移动止盈 (默认开启)
  - 止损: 买入价 × (1 - stop_loss%)
  - 时间止损: 持有 N 日
"""
import os, sys, json, math
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from indicators import indicator_panel, ma
from tre import TreState, step_tre, raw_state
from engine import Portfolio

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "output")
os.makedirs(OUT, exist_ok=True)

PERIOD_IN = ("2019-01-02", "2024-12-31")
PERIOD_OOS = ("2025-01-02", "2026-06-30")
CASH_ETF = "etf_159650"
CORE_IDX = ["idx_hs300", "idx_sh", "idx_sz"]

# 24只观察池个股
OBS_POOL = {
    "603259": ("stk_603259", "药明康德", "医药生物"),
    "300357": ("stk_300357", "我武生物", "医药生物"),
    "605117": ("stk_605117", "德业股份", "电力设备"),
    "688120": ("stk_688120", "华海清科", "电子"),
    "002371": ("stk_002371", "北方华创", "电子"),
    "300750": ("stk_300750", "宁德时代", "电力设备"),
    "600196": ("stk_600196", "复星医药", "医药生物"),
    "002156": ("stk_002156", "通富微电", "电子"),
    "688082": ("stk_688082", "盛美上海", "电子"),
    "300661": ("stk_300661", "圣邦股份", "电子"),
    "300693": ("stk_300693", "盛弘股份", "电力设备"),
    "600276": ("stk_600276", "恒瑞医药", "医药生物"),
    "600584": ("stk_600584", "长电科技", "电子"),
    "688239": ("stk_688239", "航宇科技", "国防军工"),
    "603986": ("stk_603986", "兆易创新", "电子"),
    "688008": ("stk_688008", "澜起科技", "电子"),
    "603005": ("stk_603005", "晶方科技", "电子"),
    "002335": ("stk_002335", "科华数据", "通信"),
    "002472": ("stk_002472", "双环传动", "汽车"),
    "002050": ("stk_002050", "三花智控", "汽车"),
    "002111": ("stk_002111", "威海广泰", "国防军工"),
    "000099": ("stk_000099", "中信海直", "国防军工"),
    "002518": ("stk_002518", "科士达", "电力设备"),
    "688686": ("stk_688686", "奥普特", "机械设备"),
}

# ---------------- 配置 ----------------
VOL_GATE_A_THRESH = float(os.environ.get("BT_VOL_GATE_A_THRESH", "15.0"))
VOL_GATE_B_THRESH = float(os.environ.get("BT_VOL_GATE_B_THRESH", "20.0"))
SCORE_THRESH = float(os.environ.get("BT_ATK_SCORE", "70.0"))
STOP_LOSS = float(os.environ.get("BT_ATK_STOPLOSS", "8.0")) / 100.0
TIME_STOP_DAYS = int(os.environ.get("BT_ATK_TIMESTOP", "30"))
POS_SIZE = float(os.environ.get("BT_ATK_POSIZE", "5.0"))
MAX_POSITIONS = int(os.environ.get("BT_ATK_MAXPOS", "5"))
P12_OVERLAY = os.environ.get("BT_ATK_P12", "1") == "1"  # 默认开启
P12_TIERS = [(0.15, 0.45), (0.30, 0.35), (0.50, 0.25)]
OUTPUT_TAG = os.environ.get("BT_ATK_TAG", "B1")
PERIOD_MODE = os.environ.get("BT_ATK_PERIOD", "IS")


# ---------------- 数据加载 ----------------
def load_csv(name):
    df = pd.read_csv(os.path.join(DATA, f"{name}.csv"), dtype={"date": str})
    df["date"] = df["date"].astype(str).str[:10]
    return df.set_index("date").sort_index()


def load_all():
    panels = {}
    for nm in CORE_IDX:
        panels[nm] = load_csv(nm)
    for code, (dn, _, _) in OBS_POOL.items():
        try:
            panels[dn] = load_csv(dn)
        except FileNotFoundError:
            print(f"[MISSING] {dn}")
    try:
        panels[CASH_ETF] = load_csv(CASH_ETF)
    except FileNotFoundError:
        pass
    return panels


def build_panels(panels):
    out = {}
    for nm, df in panels.items():
        p = indicator_panel(df)
        p["MA20"] = p["close"].rolling(20).mean()
        p["VOL20A"] = p["close"].pct_change().rolling(20).std() * np.sqrt(252) * 100
        p["ret5"] = p["close"].pct_change(5) * 100
        p["ret20"] = p["close"].pct_change(20) * 100
        p["ret60"] = p["close"].pct_change(60) * 100
        p["amount20"] = p["amount"].rolling(20).mean()
        out[nm] = p
    return out


def compute_tre_states(panels, days):
    tre = TreState()
    hs300 = panels["idx_hs300"]
    hs300_ret = hs300["close"].pct_change()
    states = {}
    for i, date in enumerate(days):
        if i < 2:
            states[date] = ("S3", False, 20.0)
            continue
        t1 = days[i - 1]
        core_adx = [float(panels[x].loc[t1, "ADX14"]) for x in CORE_IDX]
        cross20 = int(panels["idx_hs300"].loc[t1, "CROSS20"])
        vol20 = float(hs300_ret.loc[:t1].tail(20).std(ddof=1) * np.sqrt(252) * 100)
        below_streak = float(panels["idx_hs300"].loc[t1, "BELOW_STREAK"])
        gt_ma60 = bool(panels["idx_hs300"].loc[t1, "close"] > panels["idx_hs300"].loc[t1, "MA60"])
        step_tre(tre, i, core_adx, cross20, vol20, below_streak, gt_ma60,
                 variant="V1", obs_guard=True)
        avg_adx = float(np.mean(core_adx)) if core_adx else 20.0
        states[date] = (tre.state, tre.obs_active, avg_adx)
    return states


def simple_stock_score(row):
    """简化技术评分 (趋势50 + 动量30 + 流动性20 = 100)
    不依赖财报数据, 纯技术面评分
    """
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
    r5 = row.get("ret5", 0)
    r20 = row.get("ret20", 0)
    r60 = row.get("ret60", 0)
    # 5日动量 (超买警戒)
    mo += 10.0 * np.clip((r5 + 2) / 8, 0, 1) if r5 > -2 else 0.0
    # 20日动量
    mo += 10.0 * np.clip((r20 + 5) / 15, 0, 1) if r20 > -5 else 0.0
    # 60日动量 (主趋势)
    mo += 10.0 * np.clip((r60 + 10) / 30, 0, 1) if r60 > -10 else 0.0
    mo = min(30, mo)

    # 流动性 20
    li = 0.0
    amt20 = row.get("amount20", 0)
    li += 10.0 * np.clip(np.log10(amt20 / 1e8 + 0.1) / 1.2, 0, 1) if amt20 > 0 else 0.0
    vol_ratio = row.get("VOLRATIO", 1.0)
    li += 10.0 * np.clip(vol_ratio / 2.5, 0, 1)
    li = min(20, li)

    return min(100, tr + mo + li)


# ---------------- 回测主逻辑 ----------------
def run_attack_b(panels, days, period, label):
    tre_states = compute_tre_states(panels, days)
    pf = Portfolio()
    pf.kelly_cap = 0.25

    period_start, period_end = period
    active = False
    hist = []
    buys = []
    stats = {"signal_evaluated": 0, "signal_passed": 0, "max_pos_block": 0,
             "gate_a_block": 0, "gate_b_block": 0, "score_block": 0,
             "stop_loss": 0, "time_stop": 0, "p12_exit": 0, "tre_block": 0,
             "melt_block": 0, "dup_block": 0}

    for i, date in enumerate(days):
        if date >= period_start:
            active = True
        if date > period_end:
            break
        if not active or i < 2:
            continue

        t1 = days[i - 1]
        hs300_t1 = panels["idx_hs300"].loc[t1]
        hs300_ret = panels["idx_hs300"]["close"].pct_change()
        vol20 = float(hs300_ret.loc[:t1].tail(20).std(ddof=1) * np.sqrt(252) * 100)

        tre_state, obs_active, avg_adx = tre_states.get(date, ("S3", False, 20.0))

        # 熔断检查
        melt = pf.meltdown_level(float(hs300_t1["pct_chg"]))
        melt_block = melt >= 1

        # ---------- 离场检查 ----------
        for code in list(pf.holdings.keys()):
            dn = OBS_POOL[code][0]
            if dn not in panels or date not in panels[dn].index:
                continue
            p = pf.holdings[code]
            ct = float(panels[dn].loc[date, "close"])
            p.max_high = max(p.max_high, ct)
            p.time_cnt += 1

            open_px = float(panels[dn].loc[date, "open"]) if date in panels[dn].index else ct

            # 1. 止损
            if ct <= p.cost * (1 - STOP_LOSS):
                pf.sell(date, code, f"止损({STOP_LOSS*100:.0f}%)", 1.0, price=open_px)
                stats["stop_loss"] += 1
                continue

            # 2. P12v6 移动止盈
            if P12_OVERLAY and P12_TIERS:
                max_fp = (p.max_high - p.cost) / p.cost
                if max_fp >= P12_TIERS[0][0]:
                    retr = P12_TIERS[-1][1]
                    for j in range(len(P12_TIERS) - 1):
                        if max_fp < P12_TIERS[j + 1][0]:
                            retr = P12_TIERS[j][1]
                            break
                    p12_price = p.cost * (1 + max_fp * (1 - retr))
                    if open_px <= p12_price:
                        pf.sell(date, code, f"P12止盈(浮盈{max_fp*100:.0f}%回撤{retr*100:.0f}%)", 1.0, price=open_px)
                        stats["p12_exit"] += 1
                        continue

            # 3. 时间止损
            if p.time_cnt >= TIME_STOP_DAYS:
                pf.sell(date, code, f"时间止损({TIME_STOP_DAYS}日)", 1.0, price=open_px)
                stats["time_stop"] += 1
                continue

        # ---------- 入场检查 ----------
        if melt_block:
            stats["melt_block"] += 1
            continue

        # vol20 闸门
        if vol20 < VOL_GATE_A_THRESH:
            stats["gate_a_block"] += 1
            continue
        if vol20 >= VOL_GATE_B_THRESH and tre_state in ("S1", "S2"):
            stats["gate_b_block"] += 1
            continue

        # TRE 状态过滤: S1/S2/S3 (非S4)
        if tre_state == "S4":
            stats["tre_block"] += 1
            continue

        # 最多持仓数限制
        if len(pf.holdings) >= MAX_POSITIONS:
            stats["max_pos_block"] += 1
            continue

        # 扫描个股池
        candidates = []
        for code, (dn, name, ind) in OBS_POOL.items():
            if code in pf.holdings:
                stats["dup_block"] += 1
                continue
            if dn not in panels or t1 not in panels[dn].index:
                continue
            row = panels[dn].loc[t1]
            stats["signal_evaluated"] += 1

            # 简化评分
            score = simple_stock_score(row)
            if score < SCORE_THRESH:
                stats["score_block"] += 1
                continue

            # 流动性最低要求
            amt20 = float(row.get("amount20", 0))
            if amt20 < 5e7:  # 日均成交额≥5000万
                continue

            # ATR 过高过滤
            atr20p = float(row.get("ATR20P", 0))
            if atr20p > 10:
                continue

            close_t1 = float(row["close"])
            candidates.append((code, name, ind, close_t1, score))

        if not candidates:
            continue

        # 按评分排序
        candidates.sort(key=lambda x: x[4], reverse=True)
        stats["signal_passed"] += len(candidates)

        # 执行买入
        slots = MAX_POSITIONS - len(pf.holdings)
        for code, name, ind, close_t1, score in candidates[:slots]:
            dn = OBS_POOL[code][0]
            if date not in panels[dn].index:
                continue
            open_px = float(panels[dn].loc[date, "open"])
            if open_px <= 0:
                continue

            # 使用T-1收盘价作为fallback（防止停牌等数据缺失）
            eq_prices = {}
            for c in pf.holdings:
                dn_eq = OBS_POOL[c][0]
                if dn_eq in panels and date in panels[dn_eq].index:
                    eq_prices[c] = float(panels[dn_eq].loc[date, "close"])
                elif dn_eq in panels and t1 in panels[dn_eq].index:
                    eq_prices[c] = float(panels[dn_eq].loc[t1, "close"])
                else:
                    eq_prices[c] = float(pf.holdings[c].cost)
            eq_now = pf.equity(eq_prices)
            target = POS_SIZE
            pos_pct = 1.0 - pf.cash / max(eq_now, 1)
            if pos_pct + target / 100.0 > 0.25:
                target = max(0, (0.25 - pos_pct) * 100)
                if target < 2.0:
                    continue

            pf.buy(date, code, name, "stock", ind, open_px, target, eq_now, i,
                   obs_probe=False, s3_pos=False, reason=f"个股精选(评分{score:.0f})")
            buys.append({"date": date, "code": code, "reason": f"个股精选(评分{score:.0f})",
                         "tre": tre_state, "score": score, "target": target})

        # ---------- 现金管理 ----------
        cash_df = panels.get(CASH_ETF)
        cash_r = 0.0
        if cash_df is not None and t1 in cash_df.index:
            cash_r = float(cash_df.loc[t1, "pct_chg"]) / 100.0
        else:
            cash_r = 0.02 / 252.0
        pf.cash_mgmt_ret += pf.cash * cash_r
        pf.cash *= (1 + cash_r)

        # ---------- 盘后更新 ----------
        prices_t = {}
        prices_t1 = {}
        for c in pf.holdings:
            dn = OBS_POOL[c][0]
            # T日收盘价 (fallback: T-1收盘 → 成本价)
            if dn in panels and date in panels[dn].index:
                prices_t[c] = float(panels[dn].loc[date, "close"])
            elif dn in panels and t1 in panels[dn].index:
                prices_t[c] = float(panels[dn].loc[t1, "close"])
            else:
                prices_t[c] = float(pf.holdings[c].cost)
            # T-1收盘价
            if dn in panels and t1 in panels[dn].index:
                prices_t1[c] = float(panels[dn].loc[t1, "close"])
            else:
                prices_t1[c] = prices_t[c]
        eq_t1 = pf.equity(prices_t1)
        eq_t = pf.equity(prices_t)
        day_ret = eq_t / max(eq_t1, 1e-9) - 1 if eq_t1 > 0 else 0
        pf.ret_hist_20.append(day_ret)
        pf.ret_hist_20 = pf.ret_hist_20[-60:]
        pf.update_after_close(prices_t, day_ret, vol20)
        pf.prev_vol20 = vol20

        hist.append({
            "date": date, "tre": tre_state, "equity": eq_t, "cash": pf.cash,
            "dd": pf.drawdown, "vol20": vol20, "holdings": {c: round(p.shares * prices_t.get(c, 0), 0)
                                                              for c, p in pf.holdings.items()},
        })

    # 期末清算
    last_date = hist[-1]["date"] if hist else period_end
    for code in list(pf.holdings.keys()):
        dn = OBS_POOL[code][0]
        if dn in panels and last_date in panels[dn].index:
            ct = float(panels[dn].loc[last_date, "close"])
            pf.sell(last_date, code, "期末清算", 1.0, price=ct)

    result = {
        "label": label, "period": period, "period_mode": PERIOD_MODE,
        "score_thresh": SCORE_THRESH, "vol_gate_a": VOL_GATE_A_THRESH,
        "vol_gate_b": VOL_GATE_B_THRESH, "stop_loss": STOP_LOSS * 100,
        "time_stop": TIME_STOP_DAYS, "pos_size": POS_SIZE, "max_pos": MAX_POSITIONS,
        "p12_overlay": P12_OVERLAY,
        "hist": hist, "trades": pf.trades, "buys": buys, "stats": stats,
        "cash_mgmt_ret": pf.cash_mgmt_ret, "final_equity": eq_t if hist else 1e6,
        "final_cash": pf.cash, "closed": pf.closed_periods,
    }
    return result


def main():
    panels0 = load_all()
    panels = build_panels(panels0)
    days = list(panels["idx_hs300"].index)
    warm = [d for d in days if d >= "2018-06-01" and d < PERIOD_IN[0]]

    if PERIOD_MODE == "IS":
        period = PERIOD_IN
        run_days = warm + [d for d in days if d >= PERIOD_IN[0] and d <= PERIOD_IN[1]]
    else:
        period = PERIOD_OOS
        run_days = [d for d in days if d >= PERIOD_OOS[0] and d <= PERIOD_OOS[1]]

    res = run_attack_b(panels, run_days, period, f"候选B-{OUTPUT_TAG}-{PERIOD_MODE}")

    out_file = os.path.join(OUT, f"attack_b_{OUTPUT_TAG}.json")
    with open(out_file, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1, default=str)

    closed = res.get("closed", [])
    buys = res.get("buys", [])
    final_eq = res.get("final_equity", 1e6)
    total_ret = (final_eq / 1e6 - 1) * 100
    years = 6.0 if PERIOD_MODE == "IS" else 1.5
    ann_ret = ((final_eq / 1e6) ** (1 / years) - 1) * 100 if final_eq > 0 else -100
    trade_pnl = sum(float(c.get("pnl", 0)) for c in closed)
    max_dd = max((h.get("dd", 0) for h in res.get("hist", [])), default=0)

    pnls = [float(c.get("pnl", 0)) for c in closed]
    wins = [p for p in pnls if p > 0]
    win_rate = len(wins) / len(pnls) * 100 if pnls else 0

    print(f"\n{'='*60}")
    print(f"候选B-{OUTPUT_TAG}-{PERIOD_MODE} 回测结果")
    print(f"{'='*60}")
    print(f"  得分门槛: {SCORE_THRESH:.0f} / 闸门A: {VOL_GATE_A_THRESH:.0f} / 闸门B: {VOL_GATE_B_THRESH:.0f}")
    print(f"  止损: {STOP_LOSS*100:.0f}% / 时间止损: {TIME_STOP_DAYS}日 / P12: {'开' if P12_OVERLAY else '关'}")
    print(f"  建仓次数: {len(buys)} / 平仓笔数: {len(closed)}")
    print(f"  总收益: {total_ret:.2f}% / 年化: {ann_ret:.2f}%")
    print(f"  交易PnL: {trade_pnl:,.0f} / 最大回撤: {max_dd:.2f}%")
    print(f"  胜率: {win_rate:.1f}% / 现金管理: {res.get('cash_mgmt_ret', 0):,.0f}")
    print(f"  信号统计: {res['stats']}")
    print(f"  输出: {out_file}")


if __name__ == "__main__":
    main()
