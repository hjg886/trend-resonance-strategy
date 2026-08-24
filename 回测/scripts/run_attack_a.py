# -*- coding: utf-8 -*-
"""
进攻线候选A：ETF 均值回归（超跌反弹）独立回测
===
阶段1历史定参回测 — 不依赖主引擎 TRE 趋势跟踪建仓逻辑

入场信号:
  A1: close <= MA20 * (1 - 3%)  且  TRE状态 in {S4, S3, S2(低ADX)}
  A2: RSI14 < 35                且  TRE状态 in {S4, S3, S2(低ADX)}
  A3: close <= MA20 * (1 - 5%)  且  TRE状态 in {S4, S3, S2(低ADX)}

出场信号:
  - 均值回归目标: close >= MA20 (回到均线即止盈)
  - 止损: 买入价 * (1 - stop_loss%)
  - 时间止损: 持有 N 日未回归
  - 可选 P12v6 叠加: 浮盈达门槛后回撤止盈

仓位: 5%/笔, 最多3笔并发
初始资金: 100万
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

# ---------------- 配置 ----------------
PERIOD_IN = ("2019-01-02", "2024-12-31")
PERIOD_OOS = ("2025-01-02", "2026-06-30")
CASH_ETF = "etf_159650"
CORE_IDX = ["idx_hs300", "idx_sh", "idx_sz"]

# 信号类型 (env: BT_ATK_SIGNAL = A1/A2/A3)
SIGNAL_TYPE = os.environ.get("BT_ATK_SIGNAL", "A1")
# 超跌阈值 (A1=3%, A3=5%)
DROPOUT_PCT = float(os.environ.get("BT_ATK_DROPOUT", "3.0")) / 100.0
# RSI 阈值 (A2)
RSI_THRESH = float(os.environ.get("BT_ATK_RSI_THRESH", "35"))
# 止损比例
STOP_LOSS = float(os.environ.get("BT_ATK_STOPLOSS", "8.0")) / 100.0
# 时间止损天数
TIME_STOP_DAYS = int(os.environ.get("BT_ATK_TIMESTOP", "20"))
# 单笔仓位 (%)
POS_SIZE = float(os.environ.get("BT_ATK_POSIZE", "5.0"))
# 最大并发持仓数
MAX_POSITIONS = int(os.environ.get("BT_ATK_MAXPOS", "3"))
# 低ADX阈值 (S2+低ADX 视为弱趋势)
LOW_ADX_THRESH = float(os.environ.get("BT_ATK_LOWADX", "20.0"))
# 是否叠加P12v6出场
P12_OVERLAY = os.environ.get("BT_ATK_P12", "0") == "1"
P12_TIERS = [(0.15, 0.45), (0.30, 0.35), (0.50, 0.25)]  # P12v6固化
# 输出文件名后缀
OUTPUT_TAG = os.environ.get("BT_ATK_TAG", SIGNAL_TYPE)
# 回测周期 (IS/OOS)
PERIOD_MODE = os.environ.get("BT_ATK_PERIOD", "IS")

# ETF 池 (22只, 不含国开债)
ETF_POOL = [
    "510050", "510300", "510500", "510880", "159915", "159920", "159928",
    "512010", "512400", "512660", "512880", "512980", "515000", "515050",
    "512170", "512480", "512690", "159995", "515030", "515790", "516160", "588000",
]

# ---------------- 数据加载 ----------------
def load_csv(name):
    df = pd.read_csv(os.path.join(DATA, f"{name}.csv"), dtype={"date": str})
    df["date"] = df["date"].astype(str).str[:10]
    return df.set_index("date").sort_index()


def compute_rsi(close, period=14):
    """RSI 指标"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period, min_periods=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def load_all():
    panels = {}
    # 核心指数
    for nm in CORE_IDX:
        panels[nm] = load_csv(nm)
    # ETF 数据
    for code in ETF_POOL:
        nm = f"etf_{code}"
        try:
            panels[nm] = load_csv(nm)
        except FileNotFoundError:
            print(f"[MISSING] {nm}")
    # 现金ETF
    try:
        panels[CASH_ETF] = load_csv(CASH_ETF)
    except FileNotFoundError:
        pass
    return panels


def build_panels(panels):
    """计算指标面板"""
    out = {}
    cal = panels["idx_hs300"].index
    for nm, df in panels.items():
        p = indicator_panel(df)
        p["MA20"] = p["close"].rolling(20).mean()
        p["VOL20A"] = p["close"].pct_change().rolling(20).std() * np.sqrt(252) * 100
        p["RSI14"] = compute_rsi(p["close"])
        out[nm] = p
    return out


def compute_tre_states(panels, days):
    """运行TRE状态机，返回每日状态序列"""
    tre = TreState()
    hs300 = panels["idx_hs300"]
    hs300_ret = hs300["close"].pct_change()
    states = {}
    core_adx_prev = [20.0] * 3  # 默认值

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


# ---------------- 回测主逻辑 ----------------
def run_attack_a(panels, days, period, label):
    """ETF均值回归回测"""
    tre_states = compute_tre_states(panels, days)
    pf = Portfolio()
    pf.kelly_cap = 0.25  # 不使用凯利, 仅用固定仓位

    period_start, period_end = period
    active = False
    hist = []
    buys = []
    stats = {"signal_triggers": 0, "max_pos_block": 0, "stop_loss": 0,
             "time_stop": 0, "mean_revert": 0, "p12_exit": 0, "vol_filter": 0}

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
            nm = f"etf_{code}"
            if nm not in panels or date not in panels[nm].index:
                continue
            p = pf.holdings[code]
            ct = float(panels[nm].loc[date, "close"])
            p.max_high = max(p.max_high, ct)
            p.time_cnt += 1

            # 1. 止损
            if ct <= p.cost * (1 - STOP_LOSS):
                open_px = float(panels[nm].loc[date, "open"]) if date in panels[nm].index else ct
                pf.sell(date, code, f"止损({STOP_LOSS*100:.0f}%)", 1.0, price=open_px)
                stats["stop_loss"] += 1
                continue

            # 2. 均值回归目标 (close >= MA20)
            ma20_t = float(panels[nm].loc[date, "MA20"])
            if pd.notna(ma20_t) and ct >= ma20_t:
                open_px = float(panels[nm].loc[date, "open"]) if date in panels[nm].index else ct
                pf.sell(date, code, "均值回归(MA20)", 1.0, price=open_px)
                stats["mean_revert"] += 1
                continue

            # 3. 时间止损
            if p.time_cnt >= TIME_STOP_DAYS:
                open_px = float(panels[nm].loc[date, "open"]) if date in panels[nm].index else ct
                pf.sell(date, code, f"时间止损({TIME_STOP_DAYS}日)", 1.0, price=open_px)
                stats["time_stop"] += 1
                continue

            # 4. P12v6 叠加 (可选)
            if P12_OVERLAY and P12_TIERS:
                max_fp = (p.max_high - p.cost) / p.cost
                if max_fp >= P12_TIERS[0][0]:
                    retr = P12_TIERS[-1][1]
                    for j in range(len(P12_TIERS) - 1):
                        if max_fp < P12_TIERS[j + 1][0]:
                            retr = P12_TIERS[j][1]
                            break
                    p12_price = p.cost * (1 + max_fp * (1 - retr))
                    open_px = float(panels[nm].loc[date, "open"]) if date in panels[nm].index else ct
                    if open_px <= p12_price:
                        pf.sell(date, code, f"P12止盈(浮盈{max_fp*100:.0f}%回撤{retr*100:.0f}%)", 1.0, price=open_px)
                        stats["p12_exit"] += 1
                        continue

        # ---------- 入场检查 ----------
        if melt_block:
            continue

        # 最多持仓数限制
        if len(pf.holdings) >= MAX_POSITIONS:
            stats["max_pos_block"] += 1
            continue

        # TRE 状态过滤: S4 / S3 / S2(低ADX)
        allow_entry = tre_state == "S4" or tre_state == "S3" or \
                      (tre_state == "S2" and avg_adx < LOW_ADX_THRESH)
        if not allow_entry:
            continue

        # 扫描ETF池, 寻找超跌信号
        candidates = []
        for code in ETF_POOL:
            if code in pf.holdings:
                continue
            nm = f"etf_{code}"
            if nm not in panels or t1 not in panels[nm].index:
                continue
            row = panels[nm].loc[t1]
            close_t1 = float(row["close"])
            ma20_t1 = float(row.get("MA20", np.nan))
            vol20a_t1 = float(row.get("VOL20A", np.nan))
            rsi_t1 = float(row.get("RSI14", np.nan))

            if pd.isna(ma20_t1) or ma20_t1 <= 0:
                continue

            # 波动率过滤: vol20a 15-40 区间 (避免极低和极高波动)
            if pd.isna(vol20a_t1) or vol20a_t1 < 10 or vol20a_t1 > 45:
                stats["vol_filter"] += 1
                continue

            # 信号判定
            signal = False
            signal_detail = ""
            if SIGNAL_TYPE == "A1":
                drop = (ma20_t1 - close_t1) / ma20_t1
                if drop >= DROPOUT_PCT:
                    signal = True
                    signal_detail = f"超跌{drop*100:.1f}%"
            elif SIGNAL_TYPE == "A2":
                if pd.isna(rsi_t1):
                    continue
                if rsi_t1 < RSI_THRESH:
                    signal = True
                    signal_detail = f"RSI{rsi_t1:.0f}<{RSI_THRESH:.0f}"
            elif SIGNAL_TYPE == "A3":
                drop = (ma20_t1 - close_t1) / ma20_t1
                if drop >= DROPOUT_PCT:
                    signal = True
                    signal_detail = f"超跌{drop*100:.1f}%"

            if signal:
                candidates.append((code, close_t1, signal_detail))

        if not candidates:
            continue

        # 按超跌深度排序 (越超跌越优先)
        candidates.sort(key=lambda x: float(x[1]) / float(panels[f"etf_{x[0]}"].loc[t1, "MA20"]))

        # 执行买入 (最多补满到 MAX_POSITIONS)
        slots = MAX_POSITIONS - len(pf.holdings)
        for code, close_t1, detail in candidates[:slots]:
            nm = f"etf_{code}"
            if date not in panels[nm].index:
                continue
            open_px = float(panels[nm].loc[date, "open"])
            if open_px <= 0:
                continue
            eq_now = pf.equity({c: float(panels[f"etf_{c}"].loc[date, "close"])
                                for c in pf.holdings if f"etf_{c}" in panels and date in panels[f"etf_{c}"].index})
            target = POS_SIZE
            # 总仓位检查
            pos_pct = 1.0 - pf.cash / max(eq_now, 1)
            if pos_pct + target / 100.0 > 0.25:  # 总仓位上限25%
                target = max(0, (0.25 - pos_pct) * 100)
                if target < 2.0:
                    continue
            pf.buy(date, code, f"ETF_{code}", "etf_wide", None, open_px, target, eq_now, i,
                   obs_probe=False, s3_pos=False, reason=f"均值回归-{detail}")
            stats["signal_triggers"] += 1
            buys.append({"date": date, "code": code, "reason": f"均值回归-{detail}",
                         "tre": tre_state, "signal": SIGNAL_TYPE, "target": target})

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
        for c in pf.holdings:
            nm = f"etf_{c}"
            prices_t[c] = float(panels[nm].loc[date, "close"]) if date in panels[nm].index else close_t1
        eq_t1 = pf.equity({c: float(panels[f"etf_{c}"].loc[t1, "close"])
                          for c in pf.holdings if f"etf_{c}" in panels and t1 in panels[f"etf_{c}"].index})
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
        nm = f"etf_{code}"
        if nm in panels and last_date in panels[nm].index:
            ct = float(panels[nm].loc[last_date, "close"])
            pf.sell(last_date, code, "期末清算", 1.0, price=ct)

    result = {
        "label": label, "signal_type": SIGNAL_TYPE, "period": period,
        "dropout_pct": DROPOUT_PCT * 100, "rsi_thresh": RSI_THRESH,
        "stop_loss": STOP_LOSS * 100, "time_stop": TIME_STOP_DAYS,
        "pos_size": POS_SIZE, "max_pos": MAX_POSITIONS,
        "p12_overlay": P12_OVERLAY, "period_mode": PERIOD_MODE,
        "hist": hist, "trades": pf.trades, "buys": buys, "stats": stats,
        "cash_mgmt_ret": pf.cash_mgmt_ret, "final_equity": eq_t if hist else 1e6,
        "final_cash": pf.cash, "closed": pf.closed_periods,
    }
    return result


def main():
    panels0 = load_all()
    panels = build_panels(panels0)
    days = list(panels["idx_hs300"].index)

    # 预热期
    warm = [d for d in days if d >= "2018-06-01" and d < PERIOD_IN[0]]

    if PERIOD_MODE == "IS":
        period = PERIOD_IN
        run_days = warm + [d for d in days if d >= PERIOD_IN[0] and d <= PERIOD_IN[1]]
    else:
        period = PERIOD_OOS
        run_days = [d for d in days if d >= PERIOD_OOS[0] and d <= PERIOD_OOS[1]]

    res = run_attack_a(panels, run_days, period, f"候选A-{SIGNAL_TYPE}-{PERIOD_MODE}")

    out_file = os.path.join(OUT, f"attack_a_{OUTPUT_TAG}.json")
    with open(out_file, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1, default=str)

    # 核心指标计算
    closed = res.get("closed", [])
    buys = res.get("buys", [])
    final_eq = res.get("final_equity", 1e6)
    total_ret = (final_eq / 1e6 - 1) * 100
    n_closed = len(closed)
    n_buys = len(buys)

    # 年化
    if PERIOD_MODE == "IS":
        years = 6.0
    else:
        years = 1.5
    ann_ret = ((final_eq / 1e6) ** (1 / years) - 1) * 100 if final_eq > 0 else -100

    # 交易PnL (from closed_periods)
    trade_pnl = sum(float(c.get("pnl", 0)) for c in closed)

    # 最大回撤
    max_dd = max((h.get("dd", 0) for h in res.get("hist", [])), default=0)

    print(f"\n{'='*60}")
    print(f"候选A-{SIGNAL_TYPE}-{PERIOD_MODE} 回测结果")
    print(f"{'='*60}")
    print(f"  信号类型: {SIGNAL_TYPE} (超跌={DROPOUT_PCT*100:.0f}% / RSI<{RSI_THRESH:.0f})")
    print(f"  止损: {STOP_LOSS*100:.0f}% / 时间止损: {TIME_STOP_DAYS}日")
    print(f"  P12叠加: {'是' if P12_OVERLAY else '否'}")
    print(f"  建仓次数: {n_buys}")
    print(f"  平仓笔数: {n_closed}")
    print(f"  总收益: {total_ret:.2f}%")
    print(f"  年化收益: {ann_ret:.2f}%")
    print(f"  交易PnL: {trade_pnl:,.0f}")
    print(f"  最大回撤: {max_dd:.2f}%")
    print(f"  现金管理收益: {res.get('cash_mgmt_ret', 0):,.0f}")
    print(f"  信号统计: {res['stats']}")
    print(f"  输出: {out_file}")


if __name__ == "__main__":
    main()
