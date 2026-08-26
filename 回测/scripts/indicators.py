# -*- coding: utf-8 -*-
"""
指标计算模块 —— 中线趋势共振策略 v4.7-R8 回测引擎
实现: MA60/MA120、ADX(14) Wilder、ATR(20)、20日年化波动率、MA60有效穿越计数、
      RPS、均线排列、价格偏离度、L20/H60 等回测所需技术指标
铁律: 全部指标仅使用 T-1 及以前数据（T-1铁律由引擎循环结构保证，此处只做纯函数计算）
"""
import numpy as np
import pandas as pd


def ma(close: pd.Series, n: int) -> pd.Series:
    return close.rolling(n).mean()


def _wilder_smooth(values: np.ndarray, n: int) -> np.ndarray:
    """Wilder 平滑（RMA）—— 前导 NaN 用 nanmean 初始，递推遇 NaN 保持前值"""
    out = np.full(len(values), np.nan)
    if len(values) < n:
        return out
    head = values[:n]
    out[n - 1] = float(np.nanmean(head)) if np.isfinite(head).any() else 0.0
    for i in range(n, len(values)):
        vi = values[i]
        if not np.isfinite(vi):
            out[i] = out[i - 1]
        else:
            out[i] = (out[i - 1] * (n - 1) + vi) / n
    return out


def adx(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    """ADX(14) —— Wilder 标准算法"""
    h, l, c = high.values, low.values, close.values
    length = len(h)
    up = np.full(length, np.nan); dn = np.full(length, np.nan)
    for i in range(1, length):
        up_move = h[i] - h[i - 1]
        dn_move = l[i - 1] - l[i]
        up[i] = up_move if (up_move > dn_move and up_move > 0) else 0.0
        dn[i] = dn_move if (dn_move > up_move and dn_move > 0) else 0.0
    # 真实波幅 TR
    tr = np.full(length, np.nan)
    for i in range(1, length):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    atr_w = _wilder_smooth(tr, n)
    up_w = _wilder_smooth(up, n)
    dn_w = _wilder_smooth(dn, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi = 100 * up_w / atr_w
        mdi = 100 * dn_w / atr_w
        dx = 100 * np.abs(pdi - mdi) / (pdi + mdi)
    dx = np.where(np.isnan(dx), 0.0, dx)
    adx_arr = _wilder_smooth(dx, n)
    return pd.Series(adx_arr, index=close.index)


def atr_pct(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 20) -> pd.Series:
    """ATR(20) 百分比 = ATR / 收盘价"""
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(n).mean()
    return atr / close * 100


def ann_vol_20(close: pd.Series, n: int = 20) -> pd.Series:
    """20日年化波动率(%) = 20日对数收益率标准差 × √252 × 100"""
    ret = np.log(close / close.shift(1))
    return ret.rolling(n).std(ddof=1) * np.sqrt(252) * 100


def ma60_cross_count(close: pd.Series, ma60: pd.Series, lookback: int = 20) -> pd.Series:
    """近 lookback 日 MA60 有效穿越次数
    有效穿越定义（v4.7-R8 3.1）: 收盘价上穿/下穿 MA60，且以 ATR 带宽或连续3日确认
    简化代理: 收盘价与 MA60 的相对方向变化即记 1 次穿越（报告中标注[代理]）
    """
    above = (close > ma60).astype(int)
    sign = above.diff()
    # diff: +1=由下穿上, -1=由上穿下, 0=方向未变
    cnt = pd.Series(0, index=close.index)
    # 滚动统计最近 lookback 日内的穿越次数
    roll = sign.rolling(lookback).apply(
        lambda w: np.nansum(np.abs(w)), raw=True)
    return roll.fillna(0)


def ma60_effective_break(close: pd.Series, ma60: pd.Series, atr_p: pd.Series,
                         n_days: int = 3, atr_band: float = 1.0) -> pd.Series:
    """MA60 有效破位（严控/站稳确认）
    严控定义（3.1）: 连续3个交易日有效跌破MA60（经ATR带宽或连续3日收盘价确认）
    返回 bool Series: 当日收盘有效破位（跌）为 True
    """
    below = close < ma60 - atr_p / 100 * close * atr_band  # ATR带宽确认
    consec = below.rolling(n_days).sum() >= n_days
    return consec


def ma60_below_streak(close: pd.Series, ma60: pd.Series) -> pd.Series:
    """收盘价位于 MA60 下方的连续天数（用于站稳/破位判定）"""
    below = (close < ma60).astype(int)
    streak = pd.Series(0, index=close.index)
    s = 0
    for i, b in enumerate(below.values):
        s = s + 1 if b else 0
        streak.iloc[i] = s
    return streak


def rps(close: pd.Series, n: int = 20, rank_window: int = 120) -> pd.Series:
    """相对价格强度 RPS: 近n日涨幅在近 rank_window 日滚动样本中的百分位排名(0-100)
    简化代理: 以标的自身上一段区间涨幅分布为参照（无全市场截面数据时）
    真实实现见引擎层(用候选池截面排名)，此处为单标的滚动自分布
    """
    ret_n = close.pct_change(n)
    # 滚动百分位
    def _pct_rank(x):
        x = x[~np.isnan(x)]
        if len(x) < 20 or np.std(x) == 0:
            return 50.0
        return (x[-1] > x).mean() * 100
    return ret_n.rolling(rank_window).apply(_pct_rank, raw=True)


def price_deviation(close: pd.Series, ma60: pd.Series) -> pd.Series:
    """价格偏离度(%) = (收盘/MA60 - 1) × 100"""
    return (close / ma60 - 1) * 100


def l20_h60(close: pd.Series, lookback20: int = 20, lookback60: int = 60) -> pd.DataFrame:
    """L20: 当前价位于近20日区间的位置(0-100%)；H60: 当前价距近60日最高价的回撤(%)
    L20 = (close - min20) / (max20 - min20) × 100
    H60 = (close / max60 - 1) × 100  （正值=在最高点下方距离，负值不可能，越高越接近最高点）
    """
    min20 = close.rolling(lookback20).min()
    max20 = close.rolling(lookback20).max()
    max60 = close.rolling(lookback60).max()
    l20 = (close - min20) / (max20 - min20).replace(0, np.nan) * 100
    h60 = (close / max60 - 1) * 100
    return pd.DataFrame({"L20": l20, "H60": h60})


def ma_align(close: pd.Series, ma60: pd.Series, ma120: pd.Series) -> pd.Series:
    """均线排列: 多头=3(close>ma60>ma120) 偏多=2 偏空=1 空头=0"""
    cond = pd.Series(0, index=close.index)
    cond = cond.mask((close > ma60) & (ma60 > ma120), 3)
    cond = cond.mask((close > ma60) & (ma60 <= ma120), 2)
    cond = cond.mask((close <= ma60) & (ma60 > ma120), 1)
    return cond


def ma60_slope(ma60: pd.Series, n: int = 5) -> pd.Series:
    """MA60 方向: 近n日斜率（用差分符号，向上=1 平=0 向下=-1）"""
    slope = ma60.diff(n)
    return slope.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))


def volume_ratio(volume: pd.Series, n: int = 5) -> pd.Series:
    """量比: 当日成交量 / 近n日均量"""
    return volume / volume.rolling(n).mean().replace(0, np.nan)


def nav_pctl(close: pd.Series, n: int = 120) -> pd.Series:
    """净值/价格 n 日历史分位(%)：当前价在滚动 n 日样本中的百分位排名（lower=cheaper）
    ETF 无 PE/PB 成分数据，用净值(价格)120日分位作估值代理，对标个股 PE_PCTL/PB_PCTL 逻辑
    (估值分位越低=越便宜=评分越高)；样本不足 n 日给中性 50
    """
    def _f(x):
        x = x[~np.isnan(x)]
        if len(x) < 20:
            return 50.0
        return (x[-1] > x).mean() * 100
    return close.rolling(n).apply(_f, raw=True)


def indicator_panel(df: pd.DataFrame) -> pd.DataFrame:
    """对单标的日线DataFrame计算全部指标，返回追加列
    df 需含列: date(index), open, close, high, low, volume, amount
    """
    out = df.copy()
    c = out["close"]
    out["MA60"] = ma(c, 60)
    out["MA120"] = ma(c, 120)
    out["ADX14"] = adx(out["high"], out["low"], c, 14)
    out["ATR20P"] = atr_pct(out["high"], out["low"], c, 20)
    out["VOL20A"] = ann_vol_20(c, 20)
    out["CROSS20"] = ma60_cross_count(c, out["MA60"], 20)
    out["DEV60"] = price_deviation(c, out["MA60"])
    out["RPS20"] = rps(c, 20, 120)
    out["RPS60"] = rps(c, 60, 250)
    pos = l20_h60(c, 20, 60)
    out["L20"] = pos["L20"]
    out["H60"] = pos["H60"]
    out["MAALIGN"] = ma_align(c, out["MA60"], out["MA120"])
    out["MA60SLOPE"] = ma60_slope(out["MA60"], 5)
    out["VOLRATIO"] = volume_ratio(out["volume"], 5)
    out["BELOW_STREAK"] = ma60_below_streak(c, out["MA60"])
    return out
