# -*- coding: utf-8 -*-
"""2026-08-20 盘前分析计算脚本"""
import math, json

# ========== 读取K线数据 ==========
with open(r'E:\fnOS\文档\证券\中线趋势共振策略\kline_pre_0820.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

data_by_symbol = {}
for line in lines:
    parts = [p.strip() for p in line.split('|')]
    if len(parts) >= 9 and parts[1].startswith(('sh', 'sz')) and parts[2].startswith('2026'):
        symbol = parts[1]
        date = parts[2]
        try:
            o, c, h, l = float(parts[3]), float(parts[4]), float(parts[5]), float(parts[6])
            v = float(parts[7]) if parts[7] else 0
            if symbol not in data_by_symbol:
                data_by_symbol[symbol] = []
            data_by_symbol[symbol].append({'date': date, 'open': o, 'close': c, 'high': h, 'low': l, 'volume': v})
        except:
            pass

# 按日期排序
for sym in data_by_symbol:
    data_by_symbol[sym].sort(key=lambda x: x['date'])

# ========== 技术指标计算 ==========
def calc_ma(data, period):
    if len(data) < period:
        return None
    return sum(d['close'] for d in data[-period:]) / period

def calc_vol20(data):
    if len(data) < 21:
        return None
    returns = []
    for i in range(1, len(data)):
        r = (data[i]['close'] - data[i-1]['close']) / data[i-1]['close']
        returns.append(r)
    recent = returns[-20:]
    mean_r = sum(recent) / len(recent)
    var_r = sum((r - mean_r)**2 for r in recent) / (len(recent) - 1)
    daily_vol = math.sqrt(var_r)
    return daily_vol * math.sqrt(252) * 100

def calc_atr(data, period=14):
    if len(data) < period + 1:
        return None
    trs = []
    for i in range(1, len(data)):
        tr = max(
            data[i]['high'] - data[i]['low'],
            abs(data[i]['high'] - data[i-1]['close']),
            abs(data[i]['low'] - data[i-1]['close'])
        )
        trs.append(tr)
    recent = trs[-period:]
    return sum(recent) / len(recent)

def calc_adx(data, period=14):
    if len(data) < period * 2 + 1:
        return None
    dm_plus = []
    dm_minus = []
    trs = []
    for i in range(1, len(data)):
        up_move = data[i]['high'] - data[i-1]['high']
        down_move = data[i-1]['low'] - data[i]['low']
        dm_p = up_move if (up_move > down_move and up_move > 0) else 0
        dm_m = down_move if (down_move > up_move and down_move > 0) else 0
        tr = max(
            data[i]['high'] - data[i]['low'],
            abs(data[i]['high'] - data[i-1]['close']),
            abs(data[i]['low'] - data[i-1]['close'])
        )
        dm_plus.append(dm_p)
        dm_minus.append(dm_m)
        trs.append(tr)

    def smooth(arr, n):
        if len(arr) < n:
            return 0
        s = sum(arr[:n])
        for i in range(n, len(arr)):
            s = (s - s/n) + arr[i]
        return s

    adx_values = []
    for i in range(period, len(trs) - period + 1):
        s_tr = smooth(trs[i-period+1:i+1], period) if i >= period else sum(trs[:i+1])
        s_dm_p = smooth(dm_plus[i-period+1:i+1], period) if i >= period else sum(dm_plus[:i+1])
        s_dm_m = smooth(dm_minus[i-period+1:i+1], period) if i >= period else sum(dm_minus[:i+1])
        if s_tr > 0:
            di_p = 100 * s_dm_p / s_tr
            di_m = 100 * s_dm_m / s_tr
            dx = 100 * abs(di_p - di_m) / (di_p + di_m) if (di_p + di_m) > 0 else 0
        else:
            dx = 0
        adx_values.append(dx)
    if len(adx_values) >= period:
        return sum(adx_values[-period:]) / period
    return sum(adx_values) / len(adx_values) if adx_values else 0

def calc_breadth(data_idx, threshold=0):
    """简化BREADTH：用指数成分股涨跌比代理（此处用指数自身涨跌方向代理）"""
    if len(data_idx) < 2:
        return 0
    # 使用近5日上涨日占比 * 100 作为代理
    recent5 = data_idx[-6:-1]
    up_days = sum(1 for d in recent5 if d['close'] > d['open'])
    return up_days * 20  # 0-100

def ma60_crossovers(data):
    """计算近60日内MA60穿越次数"""
    if len(data) < 61:
        return 0
    crossovers = 0
    for i in range(60, len(data)):
        ma60_prev = sum(d['close'] for d in data[i-60:i]) / 60
        ma60_curr = sum(d['close'] for d in data[i-59:i+1]) / 60
        if data[i-1]['close'] <= ma60_prev and data[i]['close'] > ma60_curr:
            crossovers += 1
        elif data[i-1]['close'] >= ma60_prev and data[i]['close'] < ma60_curr:
            crossovers += 1
    return crossovers

# ========== 指数指标计算 ==========
hs300 = data_by_symbol.get('sh000300', [])
zz500 = data_by_symbol.get('sh000905', [])
cyb = data_by_symbol.get('sz399006', [])

# 竞价价 = 08-20数据
hs300_auction = hs300[0] if hs300 else {}
zz500_auction = zz500[0] if zz500 else {}
cyb_auction = cyb[0] if cyb else {}

# 用到08-19为止的数据计算指标（排除08-20竞价）
hs300_hist = [d for d in hs300 if d['date'] < '2026-08-20']
zz500_hist = [d for d in zz500 if d['date'] < '2026-08-20']
cyb_hist = [d for d in cyb if d['date'] < '2026-08-20']

hs300_vol20 = calc_vol20(hs300_hist)
hs300_ma60 = calc_ma(hs300_hist, 60)
hs300_adx = calc_adx(hs300_hist, 14)
hs300_cross = ma60_crossovers(hs300_hist)
hs300_breadth = calc_breadth(hs300_hist)

zz500_vol20 = calc_vol20(zz500_hist)
zz500_ma60 = calc_ma(zz500_hist, 60)
zz500_adx = calc_adx(zz500_hist, 14)
zz500_cross = ma60_crossovers(zz500_hist)

cyb_vol20 = calc_vol20(cyb_hist)
cyb_ma60 = calc_ma(cyb_hist, 60)
cyb_adx = calc_adx(cyb_hist, 14)
cyb_cross = ma60_crossovers(cyb_hist)

# ========== R-04 闸门判定 ==========
r04_vol = hs300_vol20
if r04_vol < 15:
    r04_status = "闸门A（禁一切新建仓）"
    r04_code = "A"
elif r04_vol >= 20:
    r04_status = "闸门B（禁S1/S2常规建仓）"
    r04_code = "B"
else:
    r04_status = "正常区（15-20%）"
    r04_code = "NORMAL"

# ========== TRE状态判定 ==========
def tre_status(data, vol20, adx, ma60, cross):
    last = data[-1]
    above_ma60 = last['close'] > ma60 if ma60 else False
    if vol20 > 25:
        return "S4", "风暴市"
    if above_ma60 and adx > 25 and cross <= 2:
        return "S1", "强趋势市"
    if above_ma60 and 15 <= adx <= 25:
        return "S2", "趋弱市"
    if not above_ma60 and cross >= 3 and adx < 20:
        return "S3", "震荡市"
    if not above_ma60 and adx < 15 and cross <= 2:
        return "S3近似", "弱震荡（近似）"
    return "S3", "震荡市"

hs300_tre, hs300_tre_name = tre_status(hs300_hist, hs300_vol20, hs300_adx, hs300_ma60, hs300_cross)
zz500_tre, zz500_tre_name = tre_status(zz500_hist, zz500_vol20, zz500_adx, zz500_ma60, zz500_cross)
cyb_tre, cyb_tre_name = tre_status(cyb_hist, cyb_vol20, cyb_adx, cyb_ma60, cyb_cross)

# 综合TRE（取最严）
tre_list = [(hs300_tre, "沪深300"), (zz500_tre, "中证500"), (cyb_tre, "创业板指")]
tre_priority = {"S4": 4, "S3": 3, "S3近似": 3, "S2": 2, "S1": 1}
overall_tre = max(tre_list, key=lambda x: tre_priority.get(x[0], 0))

# ========== 持仓指标计算 ==========
# 恒瑞医药
hr_data = data_by_symbol.get('sh600276', [])
hr_hist = [d for d in hr_data if d['date'] < '2026-08-20']
hr_auction = hr_data[0] if hr_data else {}
hr_cost = 51.2726
hr_shares = 900
hr_peak = max(d['high'] for d in hr_data if d['date'] >= '2026-07-01')
hr_close = hr_hist[-1]['close'] if hr_hist else 0
hr_auction_price = hr_auction.get('close', 0)
hr_ma60 = calc_ma(hr_hist, 60)
hr_atr = calc_atr(hr_hist, 14)
hr_vol20 = calc_vol20(hr_hist)
hr_adx = calc_adx(hr_hist, 14)
hr_buy_date = '2026-07-01'
hr_hold_days = 50  # 07-01 to 08-20

# 止损位计算
hr_r06_band = 0.04 if hr_hold_days > 11 else 0.07  # >11日=4%
hr_p1 = hr_cost - min(2 * hr_atr, hr_cost * hr_r06_band) if hr_atr else hr_cost * (1 - hr_r06_band)

# 动态回撤
hr_dd_close = (hr_close - hr_peak) / hr_peak * 100
hr_dd_auction = (hr_auction_price - hr_peak) / hr_peak * 100

# S4提前一档
hr_s4_line = hr_peak * (1 - 0.11)
# P0(-5%), P2(-8%), P3(-10%), P4(-15%) -> S4下提前一档: P4->-11%, P3->-8%, P2->-5%
hr_p0_line = hr_peak * (1 - 0.05)
hr_p2_line = hr_peak * (1 - 0.08)
hr_p3_line = hr_peak * (1 - 0.10)
hr_p4_normal = hr_peak * (1 - 0.15)

# 沪深300ETF
etf_data = data_by_symbol.get('sh510300', [])
etf_hist = [d for d in etf_data if d['date'] < '2026-08-20']
etf_auction = etf_data[0] if etf_data else {}
etf_cost = 4.8224
etf_shares = 40700
etf_peak = max(d['high'] for d in etf_data if d['date'] >= '2026-07-08')
etf_close = etf_hist[-1]['close'] if etf_hist else 0
etf_auction_price = etf_auction.get('close', 0)
etf_ma60 = calc_ma(etf_hist, 60)
etf_atr = calc_atr(etf_hist, 14)
etf_vol20 = calc_vol20(etf_hist)
etf_buy_date = '2026-07-08'
etf_hold_days = 43

etf_r06_band = 0.04 if etf_hold_days > 11 else 0.07
# 【修正·ETF止损口径】ETF E-P1 = 买入价 - 带宽%（策略11.4，非个股 MIN(2×ATR,带宽)）
etf_p1 = etf_cost * (1 - etf_r06_band)

etf_dd_close = (etf_close - etf_peak) / etf_peak * 100
etf_dd_auction = (etf_auction_price - etf_peak) / etf_peak * 100

# 国开债ETF
bond_data = data_by_symbol.get('sz159650', [])
bond_hist = [d for d in bond_data if d['date'] < '2026-08-20']
bond_auction = bond_data[0] if bond_data else {}
bond_cost = 107.587
bond_shares = 1800
bond_close = bond_hist[-1]['close'] if bond_hist else 0
bond_auction_price = bond_auction.get('close', 0)
bond_vol20 = calc_vol20(bond_hist)

# 药明康德（观察池）
yw_data = data_by_symbol.get('sh603259', [])
yw_hist = [d for d in yw_data if d['date'] < '2026-08-20']
yw_auction = yw_data[0] if yw_data else {}
yw_close = yw_hist[-1]['close'] if yw_hist else 0
yw_auction_price = yw_auction.get('close', 0)
yw_ma60 = calc_ma(yw_hist, 60)
yw_vol20 = calc_vol20(yw_hist)
yw_atr = calc_atr(yw_hist, 14)
yw_adx = calc_adx(yw_hist, 14)

# ========== BREADTH判定（F-35） ==========
# BREADTH代理：近5日上涨日占比
breadth_val = hs300_breadth
breadth_pass = breadth_val >= 15

# ========== 资产配置 ==========
cash = 366708.97
hr_value = hr_shares * hr_auction_price
etf_value = etf_shares * etf_auction_price
bond_value = bond_shares * bond_auction_price
total_assets = cash + hr_value + etf_value + bond_value

# 三层配置
defense_pct = (hr_value + etf_value) / total_assets * 100  # 防守底盘
stable_pct = bond_value / total_assets * 100  # 稳定器
cash_pct = cash / total_assets * 100  # 现金
attack_pct = 0  # 进攻线

# P&L
hr_pnl = (hr_auction_price - hr_cost) * hr_shares
hr_pnl_pct = (hr_auction_price / hr_cost - 1) * 100
etf_pnl = (etf_auction_price - etf_cost) * etf_shares
etf_pnl_pct = (etf_auction_price / etf_cost - 1) * 100
bond_pnl = (bond_auction_price - bond_cost) * bond_shares
bond_pnl_pct = (bond_auction_price / bond_cost - 1) * 100

# ========== 输出结果 ==========
results = {
    'date': '2026-08-20',
    'time': '09:25 集合竞价',
    # 指数
    'hs300': {'close': hs300_hist[-1]['close'], 'auction': hs300_auction.get('close',0), 'vol20': round(hs300_vol20,2), 'ma60': round(hs300_ma60,2) if hs300_ma60 else None, 'adx': round(hs300_adx,1), 'cross': hs300_cross, 'tre': hs300_tre, 'tre_name': hs300_tre_name},
    'zz500': {'close': zz500_hist[-1]['close'], 'auction': zz500_auction.get('close',0), 'vol20': round(zz500_vol20,2), 'ma60': round(zz500_ma60,2) if zz500_ma60 else None, 'adx': round(zz500_adx,1), 'cross': zz500_cross, 'tre': zz500_tre, 'tre_name': zz500_tre_name},
    'cyb': {'close': cyb_hist[-1]['close'], 'auction': cyb_auction.get('close',0), 'vol20': round(cyb_vol20,2), 'ma60': round(cyb_ma60,2) if cyb_ma60 else None, 'adx': round(cyb_adx,1), 'cross': cyb_cross, 'tre': cyb_tre, 'tre_name': cyb_tre_name},
    'overall_tre': overall_tre[0], 'overall_tre_name': overall_tre[1],
    # R-04
    'r04_vol': round(r04_vol,2), 'r04_status': r04_status, 'r04_code': r04_code,
    # BREADTH
    'breadth': breadth_val, 'breadth_pass': breadth_pass,
    # 恒瑞
    'hr': {'cost': hr_cost, 'shares': hr_shares, 'peak': hr_peak, 'close': hr_close, 'auction': hr_auction_price, 'ma60': round(hr_ma60,2) if hr_ma60 else None, 'atr': round(hr_atr,3) if hr_atr else None, 'vol20': round(hr_vol20,2), 'adx': round(hr_adx,1), 'hold_days': hr_hold_days, 'r06_band': hr_r06_band, 'p1': round(hr_p1,2), 'dd_close': round(hr_dd_close,2), 'dd_auction': round(hr_dd_auction,2), 's4_line': round(hr_s4_line,2), 'p0_line': round(hr_p0_line,2), 'pnl': round(hr_pnl,0), 'pnl_pct': round(hr_pnl_pct,2), 'value': round(hr_value,0)},
    # ETF
    'etf': {'cost': etf_cost, 'shares': etf_shares, 'peak': etf_peak, 'close': etf_close, 'auction': etf_auction_price, 'ma60': round(etf_ma60,2) if etf_ma60 else None, 'atr': round(etf_atr,4) if etf_atr else None, 'vol20': round(etf_vol20,2), 'hold_days': etf_hold_days, 'r06_band': etf_r06_band, 'p1': round(etf_p1,4), 'dd_close': round(etf_dd_close,2), 'dd_auction': round(etf_dd_auction,2), 'pnl': round(etf_pnl,0), 'pnl_pct': round(etf_pnl_pct,2), 'value': round(etf_value,0)},
    # 国开债
    'bond': {'cost': bond_cost, 'shares': bond_shares, 'close': bond_close, 'auction': bond_auction_price, 'vol20': round(bond_vol20,2), 'pnl': round(bond_pnl,0), 'pnl_pct': round(bond_pnl_pct,2), 'value': round(bond_value,0)},
    # 药明康德
    'yw': {'close': yw_close, 'auction': yw_auction_price, 'ma60': round(yw_ma60,2) if yw_ma60 else None, 'vol20': round(yw_vol20,2), 'adx': round(yw_adx,1), 'atr': round(yw_atr,2) if yw_atr else None},
    # 资产配置
    'total_assets': round(total_assets,0), 'cash': round(cash,0), 'cash_pct': round(cash_pct,1), 'defense_pct': round(defense_pct,1), 'stable_pct': round(stable_pct,1),
}

print(json.dumps(results, ensure_ascii=False, indent=2))

# 保存JSON
with open(r'E:\fnOS\文档\证券\中线趋势共振策略\pre_market_0820.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\n===== 关键判定 =====")
print(f"R-04: vol20={r04_vol:.2f}% → {r04_status}")
print(f"TRE: {overall_tre[0]} {overall_tre[1]}")
print(f"BREADTH: {breadth_val} → {'PASS' if breadth_pass else 'FAIL'}")
print(f"\n恒瑞医药:")
print(f"  竞价: {hr_auction_price}, 成本: {hr_cost}, 峰值: {hr_peak}")
print(f"  动态回撤(竞价): {hr_dd_auction:.2f}%")
print(f"  S4即刻清仓线(-11%): {hr_s4_line:.2f}")
print(f"  P1止损: {hr_p1:.2f}")
print(f"  竞价 vs S4线: {'跌破！即刻清仓' if hr_auction_price < hr_s4_line else '未跌破'}")
print(f"\n沪深300ETF:")
print(f"  竞价: {etf_auction_price}, 成本: {etf_cost}")
print(f"  P1止损: {etf_p1}")
print(f"  竞价 vs P1: {'跌破！执行止损' if etf_auction_price < etf_p1 else '未跌破'}")
print(f"  昨收 vs P1: {'已触发（昨日收盘跌破）' if etf_close < etf_p1 else '未触发'}")
