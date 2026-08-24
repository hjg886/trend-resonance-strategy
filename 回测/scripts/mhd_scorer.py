#!/usr/bin/env python3
"""
MHD 评分引擎 (Market Health Dashboard Scorer) v0.1
路径D · 影子模式

读取 data/ 下全部指数+ETF+个股CSV，逐日计算5维子分+总分+假反弹信号。
输出: mhd_scores.csv + mhd_signals.csv

运行: python scripts/mhd_scorer.py
"""

import os, sys, csv, json, math, statistics
from collections import defaultdict, OrderedDict

# ── 配置 ──────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
OUT_DIR  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
os.makedirs(OUT_DIR, exist_ok=True)

# 样本宇宙定义
INDEX_FILE   = "idx_hs300"      # 权重基准
INDEX_FILES_AUX = ["idx_sh", "idx_sz"]  # 趋势一致性辅助

BROAD_ETF_MAP = {
    "etf_510050": "上证50ETF",
    "etf_510300": "沪深300ETF",
    "etf_510500": "中证500ETF",
    "etf_588000": "科创50ETF",
}

SECTOR_ETF_MAP = {
    "etf_512880": "证券ETF",
    "etf_512690": "酒ETF",
    "etf_512480": "半导体ETF",
    "etf_512170": "医疗ETF",
    "etf_512400": "有色金属ETF",
    "etf_512660": "军工ETF",
    "etf_512980": "传媒ETF",
    "etf_515000": "科技ETF",
    "etf_515030": "新能源车ETF",
    "etf_515050": "5G通信ETF",
    "etf_515790": "光伏ETF",
    "etf_516160": "新能源ETF",
}

STOCK_CODES = [
    "600276","603259","300357","605117","688120","002371","300750","600196",
    "002156","688082","300661","300693","600584","688239","603986","688008",
    "603005","002335","002472","002050","002111","000099","002518","688686",
    "600519","600036","601318","000858","000333",
]  # 29只 (24观察池 + 5大盘补充), 排除900912外高B

EXCLUDE = {"etf_159650", "stk_900912", "etf_159920", "x_gold", "x_hstech", "x_nasdaq100"}

MA_SHORT = 20
MA_LONG  = 60
VOL_WIN  = 20
RSI_WIN  = 14

# ── CSV 读取 ────────────────────────────────────────────

def load_csv(filepath):
    """读取CSV, 返回 list[dict] (date, open, close, high, low, volume, amount, amp, pct_chg, chg, turnover)"""
    rows = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                row = {
                    "date": r["date"],
                    "open": float(r["open"]),
                    "close": float(r["close"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "volume": float(r.get("volume", 0)),
                    "amount": float(r.get("amount", 0)),
                    "amp": float(r.get("amp", 0)),
                    "pct_chg": float(r.get("pct_chg", 0)),
                    "chg": float(r.get("chg", 0)),
                    "turnover": float(r.get("turnover", 0)),
                }
                rows.append(row)
            except (ValueError, KeyError):
                continue
    return rows

def compute_ma(closes, period):
    """计算移动平均, 返回 list[float] (NaN用0填充前period-1个)"""
    ma = []
    for i in range(len(closes)):
        if i < period - 1:
            ma.append(None)
        else:
            window = closes[i-period+1:i+1]
            ma.append(sum(window) / period)
    return ma

def compute_vol(pct_chgs, period):
    """20日年化波动率 = std(pct_chg, period) * sqrt(250)"""
    if len(pct_chgs) < period:
        return None
    window = pct_chgs[-period:]
    mean_val = sum(window) / period
    var = sum((x - mean_val) ** 2 for x in window) / (period - 1)
    return math.sqrt(var) * math.sqrt(250)

def compute_rsi(pct_chgs, period=14):
    """RSI(14)"""
    if len(pct_chgs) < period + 1:
        return None
    window = pct_chgs[-(period+1):]
    gains = []
    losses = []
    for i in range(1, len(window)):
        chg = window[i]  # pct_chg already is daily % change
        if chg > 0:
            gains.append(chg)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(chg))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

def compute_slope_r2(closes, period=20):
    """20日OLS回归斜率 × R²"""
    if len(closes) < period:
        return None, None
    y = closes[-period:]
    n = period
    x = list(range(n))
    x_mean = sum(x) / n
    y_mean = sum(y) / n
    ss_xx = sum((xi - x_mean) ** 2 for xi in x)
    ss_xy = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
    if ss_xx == 0:
        return 0, 0
    slope = ss_xy / ss_xx
    ss_yy = sum((yi - y_mean) ** 2 for yi in y)
    if ss_yy == 0:
        return slope, 0
    r2 = (ss_xy ** 2) / (ss_xx * ss_yy)
    return slope, r2

# ── 数据加载 ────────────────────────────────────────────

def load_all_data():
    """加载全部数据, 返回:
    - index_data: {filename: [{date, close, pct_chg, ...}]}
    - stock_data: {code: [{date, close, pct_chg, ...}]}
    - etf_data: {filename: [{date, close, pct_chg, ...}]}
    """
    all_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".csv")]
    
    index_data = {}
    stock_data = {}
    etf_data = {}
    
    # 加载指数
    for fn in [INDEX_FILE] + INDEX_FILES_AUX:
        path = os.path.join(DATA_DIR, fn + ".csv")
        if os.path.exists(path):
            index_data[fn] = load_csv(path)
            print(f"  [INDEX] {fn}: {len(index_data[fn])} rows")
    
    # 加载宽基ETF
    for fn in BROAD_ETF_MAP:
        path = os.path.join(DATA_DIR, fn + ".csv")
        if os.path.exists(path):
            etf_data[fn] = load_csv(path)
            print(f"  [BROAD]  {fn}: {len(etf_data[fn])} rows")
    
    # 加载行业ETF
    for fn in SECTOR_ETF_MAP:
        path = os.path.join(DATA_DIR, fn + ".csv")
        if os.path.exists(path):
            etf_data[fn] = load_csv(path)
            print(f"  [SECTOR] {fn}: {len(etf_data[fn])} rows")
    
    # 加载个股
    for code in STOCK_CODES:
        fn = f"stk_{code}"
        path = os.path.join(DATA_DIR, fn + ".csv")
        if os.path.exists(path):
            stock_data[fn] = load_csv(path)
        else:
            print(f"  [WARN] {fn}.csv not found, skipping")
    
    print(f"\n  Loaded: {len(index_data)} indices, {len(etf_data)} ETFs, {len(stock_data)} stocks")
    return index_data, stock_data, etf_data

# ── 技术指标预计算 ────────────────────────────────────────

def precompute_indicators(data_list, label):
    """给一个数据列表(list[dict])预计算MA/vol/RSI/slope, 原地添加到dict"""
    closes  = [r["close"] for r in data_list]
    pct_chgs = [r["pct_chg"] for r in data_list]
    
    ma20 = compute_ma(closes, MA_SHORT)
    ma60 = compute_ma(closes, MA_LONG)
    
    for i, r in enumerate(data_list):
        r["MA20"] = ma20[i]
        r["MA60"] = ma60[i]
        r["vol20"] = compute_vol(pct_chgs[:i+1], VOL_WIN)
        r["rsi14"] = compute_rsi(pct_chgs[:i+1], RSI_WIN)
        slope, r2 = compute_slope_r2(closes[:i+1], MA_SHORT)
        r["slope20"] = slope
        r["r2_20"] = r2
        # 20日高点
        if i >= MA_SHORT - 1:
            r["high20"] = max(closes[i-MA_SHORT+1:i+1])
        else:
            r["high20"] = max(closes[:i+1]) if closes else None
        # 5日涨幅
        if i >= 5:
            r["ret5d"] = (closes[i] / closes[i-5] - 1) * 100
        else:
            r["ret5d"] = None
        # 20日振幅均值
        if i >= VOL_WIN:
            r["amp_avg20"] = sum(data_list[j]["amp"] for j in range(i-VOL_WIN+1, i+1)) / VOL_WIN
        else:
            r["amp_avg20"] = None
        # 前20日振幅均值 (用于V3.3趋势)
        if i >= 2 * VOL_WIN:
            r["amp_avg_prev20"] = sum(data_list[j]["amp"] for j in range(i-2*VOL_WIN+1, i-VOL_WIN+1)) / VOL_WIN
        else:
            r["amp_avg_prev20"] = None
    
    return data_list

# ── 日期对齐 ────────────────────────────────────────────

def build_date_index(index_data):
    """用沪深300的日期作为主日历"""
    if INDEX_FILE in index_data:
        dates = [r["date"] for r in index_data[INDEX_FILE]]
    else:
        # fallback: 合并所有日期
        all_dates = set()
        for fn, rows in index_data.items():
            for r in rows:
                all_dates.add(r["date"])
        dates = sorted(all_dates)
    return dates

def build_date_map(data_list):
    """{date: row} 映射"""
    return {r["date"]: r for r in data_list}

# ── 评分函数 ────────────────────────────────────────────

def score_trend(hs300_row, aux_rows):
    """维度1: 趋势维度 (25分)"""
    score = 0
    detail = {}
    
    # T1.1 沪深300 vs MA20/MA60 (8分)
    close = hs300_row["close"]
    ma20 = hs300_row.get("MA20")
    ma60 = hs300_row.get("MA60")
    if ma20 is not None and ma60 is not None:
        above_ma20 = close > ma20
        above_ma60 = close > ma60
        if above_ma20 and above_ma60:
            t1 = 8
        elif above_ma20 and not above_ma60:
            t1 = 5
        elif not above_ma20 and above_ma60:
            t1 = 3
        else:
            t1 = 0
    else:
        t1 = 0
    score += t1
    detail["T1.1_pos"] = t1
    
    # T1.2 20日回归斜率 (5分)
    slope = hs300_row.get("slope20")
    r2 = hs300_row.get("r2_20")
    if slope is not None and r2 is not None:
        if slope > 0 and r2 > 0.3:
            t2 = 5
        elif slope > 0:
            t2 = 3
        else:
            t2 = 0
    else:
        t2 = 0
    score += t2
    detail["T1.2_slope"] = t2
    
    # T1.3 三大指数趋势一致性 (6分)
    positive_slopes = 0
    total_aux = 1  # hs300 counts
    if slope is not None and slope > 0:
        positive_slopes += 1
    for aux_row in aux_rows:
        aux_slope = aux_row.get("slope20") if aux_row else None
        if aux_slope is not None:
            total_aux += 1
            if aux_slope > 0:
                positive_slopes += 1
    if total_aux >= 2:
        ratio = positive_slopes / total_aux
        if ratio >= 2/3:
            t3 = 6
        elif ratio >= 1/2:
            t3 = 3
        else:
            t3 = 0
    else:
        t3 = 0
    score += t3
    detail["T1.3_consistency"] = t3
    
    # T1.4 距20日高点回撤 (6分)
    high20 = hs300_row.get("high20")
    if high20 is not None and high20 > 0:
        drawdown = (high20 - close) / high20 * 100
        if drawdown < 2:
            t4 = 6
        elif drawdown < 5:
            t4 = 4
        elif drawdown < 10:
            t4 = 2
        else:
            t4 = 0
    else:
        t4 = 0
        drawdown = None
    score += t4
    detail["T1.4_drawdown"] = t4
    detail["drawdown_pct"] = drawdown
    
    return score, detail

def score_breadth(hs300_row, stock_maps, date):
    """维度2: 宽度维度 (30分)"""
    score = 0
    detail = {}
    
    # 收集当日有数据的个股
    valid_stocks = []
    for fn, dmap in stock_maps.items():
        if date in dmap:
            r = dmap[date]
            if r.get("MA20") is not None and r.get("MA60") is not None:
                valid_stocks.append(r)
    
    n = len(valid_stocks)
    if n < 5:
        return 0, {"n_stocks": n, "note": "insufficient data"}
    
    detail["n_stocks"] = n
    
    # B2.1 当日上涨比例 (8分)
    up_count = sum(1 for s in valid_stocks if s["pct_chg"] > 0)
    up_ratio = up_count / n
    if up_ratio >= 0.70:
        b1 = 8
    elif up_ratio >= 0.50:
        b1 = 5
    elif up_ratio >= 0.30:
        b1 = 2
    else:
        b1 = 0
    score += b1
    detail["B2.1_up_ratio"] = round(up_ratio * 100, 1)
    detail["B2.1_score"] = b1
    
    # B2.2 站上MA20比例 (8分)
    above_ma20 = sum(1 for s in valid_stocks if s["close"] > s["MA20"])
    ratio_ma20 = above_ma20 / n
    if ratio_ma20 >= 0.70:
        b2 = 8
    elif ratio_ma20 >= 0.50:
        b2 = 5
    elif ratio_ma20 >= 0.30:
        b2 = 2
    else:
        b2 = 0
    score += b2
    detail["B2.2_above_ma20"] = round(ratio_ma20 * 100, 1)
    detail["B2.2_score"] = b2
    
    # B2.3 站上MA60比例 (6分)
    above_ma60 = sum(1 for s in valid_stocks if s["close"] > s["MA60"])
    ratio_ma60 = above_ma60 / n
    if ratio_ma60 >= 0.70:
        b3 = 6
    elif ratio_ma60 >= 0.50:
        b3 = 4
    elif ratio_ma60 >= 0.30:
        b3 = 2
    else:
        b3 = 0
    score += b3
    detail["B2.3_above_ma60"] = round(ratio_ma60 * 100, 1)
    detail["B2.3_score"] = b3
    
    # B2.4 指数-宽度背离度 (8分)
    stock_pcts = [s["pct_chg"] for s in valid_stocks]
    median_chg = statistics.median(stock_pcts)
    hs300_chg = hs300_row["pct_chg"]
    divergence = hs300_chg - median_chg
    
    if hs300_chg > 0 and median_chg < 0:
        b4 = 0  # 假反弹核心
    elif abs(divergence) <= 0.2:
        b4 = 8
    elif abs(divergence) <= 0.5:
        b4 = 5
    elif abs(divergence) <= 1.0:
        b4 = 2
    else:
        b4 = 0
    score += b4
    detail["B2.4_divergence"] = round(divergence, 3)
    detail["B2.4_median_chg"] = round(median_chg, 3)
    detail["B2.4_hs300_chg"] = hs300_chg
    detail["B2.4_score"] = b4
    
    return score, detail

def score_volatility(hs300_row, stock_maps, date):
    """维度3: 波动维度 (20分, 对齐R-04)"""
    score = 0
    detail = {}
    
    # V3.1 沪深300 vol20 (8分)
    vol_hs300 = hs300_row.get("vol20")
    if vol_hs300 is not None:
        vol_pct = vol_pct = vol_hs300 * 100
        if vol_pct < 15:
            v1 = 8
        elif vol_pct < 20:
            v1 = 6
        elif vol_pct < 25:
            v1 = 3
        else:
            v1 = 0
    else:
        v1 = 0
        vol_pct = None
    score += v1
    detail["V3.1_hs300_vol"] = round(vol_pct, 1) if vol_pct else None
    detail["V3.1_score"] = v1
    
    # V3.2 样本vol20中位 (6分)
    vols = []
    for fn, dmap in stock_maps.items():
        if date in dmap:
            v = dmap[date].get("vol20")
            if v is not None:
                vols.append(v * 100)
    if vols:
        vol_med = statistics.median(vols)
        if vol_med < 15:
            v2 = 6
        elif vol_med < 20:
            v2 = 4
        elif vol_med < 25:
            v2 = 2
        else:
            v2 = 0
    else:
        v2 = 0
        vol_med = None
    score += v2
    detail["V3.2_stock_vol_med"] = round(vol_med, 1) if vol_med else None
    detail["V3.2_score"] = v2
    
    # V3.3 振幅趋势 (6分)
    amp_cur = hs300_row.get("amp_avg20")
    amp_prev = hs300_row.get("amp_avg_prev20")
    if amp_cur is not None and amp_prev is not None and amp_prev > 0:
        change = (amp_cur - amp_prev) / amp_prev * 100
        if change < -5:
            v3 = 6  # 下降=收敛
        elif change < 5:
            v3 = 3  # 持平
        else:
            v3 = 0  # 上升=扩张
    else:
        v3 = 0
        change = None
    score += v3
    detail["V3.3_amp_trend"] = round(change, 1) if change is not None else None
    detail["V3.3_score"] = v3
    
    return score, detail

def score_momentum(hs300_row, stock_maps, date, prev_b2_2_ratio=None):
    """维度4: 动量维度 (15分)"""
    score = 0
    detail = {}
    
    # M4.1 沪深300 RSI(14) (5分)
    rsi_hs = hs300_row.get("rsi14")
    if rsi_hs is not None:
        if 50 <= rsi_hs <= 70:
            m1 = 5
        elif 30 <= rsi_hs < 50:
            m1 = 3
        elif rsi_hs > 70:
            m1 = 2
        else:
            m1 = 0
    else:
        m1 = 0
    score += m1
    detail["M4.1_hs300_rsi"] = round(rsi_hs, 1) if rsi_hs else None
    detail["M4.1_score"] = m1
    
    # M4.2 样本RSI中位 (5分)
    rsis = []
    for fn, dmap in stock_maps.items():
        if date in dmap:
            r = dmap[date].get("rsi14")
            if r is not None:
                rsis.append(r)
    if rsis:
        rsi_med = statistics.median(rsis)
        if 50 <= rsi_med <= 70:
            m2 = 5
        elif 30 <= rsi_med < 50:
            m2 = 3
        elif rsi_med > 70:
            m2 = 2
        else:
            m2 = 0
    else:
        m2 = 0
        rsi_med = None
    score += m2
    detail["M4.2_stock_rsi_med"] = round(rsi_med, 1) if rsi_med else None
    detail["M4.2_score"] = m2
    
    # M4.3 宽度动量 (5分) — 5日前B2.2 vs 当前
    # 用up_ratio_ma20的5日前值
    if prev_b2_2_ratio is not None:
        current_ratio = detail.get("M4.3_current_ratio")
        # current_ratio需要在调用前设好, 这里用传入的
        # 实际上我们在主循环中处理, 这里先返回0
        m3 = 0
    else:
        m3 = 0
    score += m3
    detail["M4.3_score"] = m3
    
    return score, detail

def score_structure(hs300_row, etf_maps, date):
    """维度5: 结构维度 (10分)"""
    score = 0
    detail = {}
    
    # S5.1 大小盘背离 (5分)
    hs300_ret5 = hs300_row.get("ret5d")
    csi500_row = etf_maps.get("etf_510500", {}).get(date)
    csi500_ret5 = csi500_row.get("ret5d") if csi500_row else None
    
    if hs300_ret5 is not None and csi500_ret5 is not None:
        diverge = abs(hs300_ret5 - csi500_ret5)
        if diverge <= 2:
            s1 = 5
        elif diverge <= 5:
            s1 = 2
        else:
            s1 = 0
    else:
        s1 = 0
        diverge = None
    score += s1
    detail["S5.1_large_small_diverge"] = round(diverge, 2) if diverge is not None else None
    detail["S5.1_score"] = s1
    
    # S5.2 行业分散度 (5分)
    sector_pcts = []
    for fn in SECTOR_ETF_MAP:
        dmap = etf_maps.get(fn, {})
        if date in dmap:
            sector_pcts.append(dmap[date]["pct_chg"])
    
    if len(sector_pcts) >= 6:
        std_val = statistics.stdev(sector_pcts)
        up_count = sum(1 for p in sector_pcts if p > 0)
        majority_same_dir = up_count >= len(sector_pcts) * 0.6 or up_count <= len(sector_pcts) * 0.4
        
        if 1.0 <= std_val <= 3.0 and majority_same_dir:
            s2 = 5  # 适度分散且有主线
        elif std_val < 1.0:
            s2 = 3  # 极度一致
        else:
            s2 = 1  # 极度分散无主线
    else:
        s2 = 0
        std_val = None
    score += s2
    detail["S5.2_sector_std"] = round(std_val, 2) if std_val is not None else None
    detail["S5.2_score"] = s2
    
    return score, detail

# ── 假反弹检测器 ────────────────────────────────────────

def detect_false_rebound(date, hs300_row, stock_maps, breadth_detail, breadth_score, etf_maps):
    """检测假反弹信号, 返回 list[dict]"""
    signals = []
    hs300_chg = hs300_row["pct_chg"]
    
    # 收集当日有效个股
    valid_stocks = []
    for fn, dmap in stock_maps.items():
        if date in dmap:
            r = dmap[date]
            if r.get("MA20") is not None:
                valid_stocks.append(r)
    
    n = len(valid_stocks)
    if n < 5:
        return signals
    
    up_count = sum(1 for s in valid_stocks if s["pct_chg"] > 0)
    up_ratio = up_count / n
    stock_pcts = [s["pct_chg"] for s in valid_stocks]
    median_chg = statistics.median(stock_pcts)
    divergence = hs300_chg - median_chg
    
    # FR-1 弱假反弹
    if hs300_chg > 0 and up_ratio < 0.40:
        signals.append({
            "signal_type": "FR-1_weak",
            "hs300_chg": round(hs300_chg, 3),
            "up_ratio": round(up_ratio * 100, 1),
            "median_chg": round(median_chg, 3),
            "divergence": round(divergence, 3),
            "breadth_score": breadth_score,
        })
    
    # FR-2 强假反弹
    if hs300_chg > 0.5 and median_chg < 0:
        signals.append({
            "signal_type": "FR-2_strong",
            "hs300_chg": round(hs300_chg, 3),
            "up_ratio": round(up_ratio * 100, 1),
            "median_chg": round(median_chg, 3),
            "divergence": round(divergence, 3),
            "breadth_score": breadth_score,
        })
    
    # FR-3 趋势假反弹
    hs300_ret5 = hs300_row.get("ret5d")
    if hs300_ret5 is not None and hs300_ret5 > 2 and breadth_score < 12:
        signals.append({
            "signal_type": "FR-3_trend",
            "hs300_chg": round(hs300_chg, 3),
            "hs300_ret5d": round(hs300_ret5, 2),
            "up_ratio": round(up_ratio * 100, 1),
            "median_chg": round(median_chg, 3),
            "divergence": round(divergence, 3),
            "breadth_score": breadth_score,
        })
    
    # FR-4 权重拉升
    csi500_row = etf_maps.get("etf_510500", {}).get(date)
    csi500_chg = csi500_row["pct_chg"] if csi500_row else None
    if csi500_chg is not None and hs300_chg > 0.3:
        large_small_diverge = abs(hs300_chg - csi500_chg)
        if large_small_diverge > 3:
            signals.append({
                "signal_type": "FR-4_weight_pull",
                "hs300_chg": round(hs300_chg, 3),
                "csi500_chg": round(csi500_chg, 3),
                "up_ratio": round(up_ratio * 100, 1),
                "median_chg": round(median_chg, 3),
                "divergence": round(divergence, 3),
                "breadth_score": breadth_score,
            })
    
    return signals

# ── 主循环 ──────────────────────────────────────────────

def main():
    print("=" * 60)
    print("MHD 评分引擎 v0.1 — 影子模式")
    print("=" * 60)
    
    # 1. 加载数据
    print("\n[1] 加载数据...")
    index_data, stock_data, etf_data = load_all_data()
    
    # 2. 预计算技术指标
    print("\n[2] 预计算技术指标...")
    for fn, rows in index_data.items():
        precompute_indicators(rows, fn)
    for fn, rows in stock_data.items():
        precompute_indicators(rows, fn)
    for fn, rows in etf_data.items():
        precompute_indicators(rows, fn)
    print("  指标计算完成")
    
    # 3. 构建日期映射
    print("\n[3] 构建日期映射...")
    index_maps = {fn: {r["date"]: r for r in rows} for fn, rows in index_data.items()}
    stock_maps = {fn: {r["date"]: r for r in rows} for fn, rows in stock_data.items()}
    etf_maps = {fn: {r["date"]: r for r in rows} for fn, rows in etf_data.items()}
    
    # 4. 主日历
    dates = build_date_index(index_data)
    print(f"  主日历: {dates[0]} ~ {dates[-1]} ({len(dates)} 交易日)")
    
    # 5. 逐日评分
    print("\n[4] 逐日评分...")
    all_scores = []
    all_signals = []
    
    # 用于M4.3宽度动量: 存储5日前的above_ma20_ratio
    ratio_ma20_history = []
    
    for i, date in enumerate(dates):
        hs300_row = index_maps.get(INDEX_FILE, {}).get(date)
        if not hs300_row:
            continue
        
        # 跳过技术指标不足的早期日 (需要至少MA60=60日)
        if hs300_row.get("MA60") is None:
            continue
        
        # 辅助指数行
        aux_rows = []
        for aux_fn in INDEX_FILES_AUX:
            aux_row = index_maps.get(aux_fn, {}).get(date)
            if aux_row:
                aux_rows.append(aux_row)
        
        # 维度1: 趋势
        trend_score, trend_detail = score_trend(hs300_row, aux_rows)
        
        # 维度2: 宽度
        breadth_score, breadth_detail = score_breadth(hs300_row, stock_maps, date)
        
        # 维度3: 波动
        vol_score, vol_detail = score_volatility(hs300_row, stock_maps, date)
        
        # 维度4: 动量 (需要5日前的ratio_ma20)
        prev_ratio_ma20 = None
        if len(ratio_ma20_history) >= 5:
            prev_ratio_ma20 = ratio_ma20_history[-5]
        
        mom_score, mom_detail = score_momentum(hs300_row, stock_maps, date, prev_ratio_ma20)
        
        # M4.3: 计算宽度动量
        current_ratio_ma20 = breadth_detail.get("B2.2_above_ma20")
        if current_ratio_ma20 is not None and prev_ratio_ma20 is not None:
            diff = current_ratio_ma20 - prev_ratio_ma20
            if diff >= 10:
                mom_score += 5
                mom_detail["M4.3_score"] = 5
            elif diff >= -10:
                mom_score += 3
                mom_detail["M4.3_score"] = 3
            else:
                mom_score += 0
                mom_detail["M4.3_score"] = 0
            mom_detail["M4.3_width_momentum"] = round(diff, 1)
        
        ratio_ma20_history.append(current_ratio_ma20)
        
        # 维度5: 结构
        struct_score, struct_detail = score_structure(hs300_row, etf_maps, date)
        
        # 总分
        mhs = trend_score + breadth_score + vol_score + mom_score + struct_score
        
        # 假反弹检测
        fr_signals = detect_false_rebound(date, hs300_row, stock_maps, breadth_detail, breadth_score, etf_maps)
        
        fr_flag = "|".join(s["signal_type"] for s in fr_signals) if fr_signals else ""
        
        row = {
            "date": date,
            "MHS": mhs,
            "TREND": trend_score,
            "BREADTH": breadth_score,
            "VOLATILITY": vol_score,
            "MOMENTUM": mom_score,
            "STRUCTURE": struct_score,
            "FR_flag": fr_flag,
            "hs300_close": round(hs300_row["close"], 2),
            "hs300_chg": hs300_row["pct_chg"],
            "hs300_vol20": trend_detail.get("V3.1_hs300_vol") or vol_detail.get("V3.1_hs300_vol"),
            "up_ratio": breadth_detail.get("B2.1_up_ratio", ""),
            "above_ma20_ratio": breadth_detail.get("B2.2_above_ma20", ""),
            "above_ma60_ratio": breadth_detail.get("B2.3_above_ma60", ""),
            "median_stock_chg": breadth_detail.get("B2.4_median_chg", ""),
            "divergence": breadth_detail.get("B2.4_divergence", ""),
            "n_stocks": breadth_detail.get("n_stocks", 0),
        }
        all_scores.append(row)
        
        for sig in fr_signals:
            sig["date"] = date
            all_signals.append(sig)
    
    print(f"  评分完成: {len(all_scores)} 交易日, {len(all_signals)} 个假反弹信号")
    
    # 6. 输出
    print("\n[5] 输出文件...")
    
    scores_path = os.path.join(OUT_DIR, "mhd_scores.csv")
    with open(scores_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "date", "MHS", "TREND", "BREADTH", "VOLATILITY", "MOMENTUM", "STRUCTURE",
            "FR_flag", "hs300_close", "hs300_chg", "hs300_vol20",
            "up_ratio", "above_ma20_ratio", "above_ma60_ratio",
            "median_stock_chg", "divergence", "n_stocks"
        ])
        writer.writeheader()
        writer.writerows(all_scores)
    print(f"  → {scores_path}")
    
    signals_path = os.path.join(OUT_DIR, "mhd_signals.csv")
    with open(signals_path, "w", encoding="utf-8-sig", newline="") as f:
        if all_signals:
            fieldnames = ["date", "signal_type", "hs300_chg", "up_ratio", "median_chg",
                         "divergence", "breadth_score"]
            # 补充可能出现的额外字段
            extra_keys = set()
            for s in all_signals:
                extra_keys.update(s.keys())
            extra_keys -= set(fieldnames)
            fieldnames += sorted(extra_keys)
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_signals)
        else:
            f.write("date,signal_type,hs300_chg,up_ratio,median_chg,divergence,breadth_score\n")
    print(f"  → {signals_path}")
    
    # 7. 统计摘要
    print("\n[6] 统计摘要...")
    mhs_values = [r["MHS"] for r in all_scores]
    if mhs_values:
        print(f"  MHS: min={min(mhs_values)}, max={max(mhs_values)}, "
              f"mean={statistics.mean(mhs_values):.1f}, median={statistics.median(mhs_values):.1f}")
        
        # 分年统计
        yearly = defaultdict(list)
        for r in all_scores:
            year = r["date"][:4]
            yearly[year].append(r["MHS"])
        
        print("\n  分年MHS统计:")
        for year in sorted(yearly.keys()):
            vals = yearly[year]
            fr_count = sum(1 for r in all_scores if r["date"][:4] == year and r["FR_flag"])
            print(f"    {year}: mean={statistics.mean(vals):.1f}, median={statistics.median(vals):.1f}, "
                  f"min={min(vals)}, max={max(vals)}, FR信号={fr_count}次")
    
    # 假反弹信号统计
    if all_signals:
        print(f"\n  假反弹信号: {len(all_signals)} 次")
        type_counts = defaultdict(int)
        for s in all_signals:
            type_counts[s["signal_type"]] += 1
        for t, c in sorted(type_counts.items()):
            print(f"    {t}: {c}次")
    
    # 8. 输出summary
    summary = {
        "total_days": len(all_scores),
        "date_range": f"{all_scores[0]['date']}~{all_scores[-1]['date']}" if all_scores else "",
        "MHS_mean": round(statistics.mean(mhs_values), 1) if mhs_values else 0,
        "MHS_median": round(statistics.median(mhs_values), 1) if mhs_values else 0,
        "MHS_min": min(mhs_values) if mhs_values else 0,
        "MHS_max": max(mhs_values) if mhs_values else 0,
        "total_FR_signals": len(all_signals),
        "FR_by_type": {k: v for k, v in sorted(type_counts.items())} if all_signals else {},
        "yearly_MHS_mean": {y: round(statistics.mean(v), 1) for y, v in sorted(yearly.items())},
    }
    summary_path = os.path.join(OUT_DIR, "mhd_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n  → {summary_path}")
    
    print("\n" + "=" * 60)
    print("MHD 评分完成 ✓")
    print("=" * 60)

if __name__ == "__main__":
    main()
