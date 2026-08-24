#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-08-20 盘前分析计算脚本"""
import json, math, os

# ============ 数据加载 ============
data_file = r"E:\fnOS\文档\证券\中线趋势共振策略\kline_pre_0820.txt"
data_by_symbol = {}

with open(data_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

for line in lines:
    parts = line.strip().split('|')
    # 格式: | symbol | date | open | last | high | low | volume | amount | exchange |
    # parts[0]为空, parts[1]=symbol, parts[2]=date, parts[3]=open, parts[4]=last(close)
    if len(parts) < 8:
        continue
    sym = parts[1].strip()
    if sym in ('', 'symbol', '---') or sym.startswith('Batch') or sym.startswith('['):
        continue
    try:
        symbol = sym
        date = parts[2].strip()
        open_p = float(parts[3])
        close = float(parts[4])
        high = float(parts[5])
        low = float(parts[6])
        volume = float(parts[8]) if len(parts) > 8 and parts[8].strip() else 0
        if symbol not in data_by_symbol:
            data_by_symbol[symbol] = []
        data_by_symbol[symbol].append({
            'date': date, 'open': open_p, 'close': close,
            'high': high, 'low': low, 'volume': volume
        })
    except (ValueError, IndexError):
        continue

# 按日期排序
for sym in data_by_symbol:
    data_by_symbol[sym].sort(key=lambda x: x['date'])

# ============ 技术指标计算函数 ============
def calc_ma(data, period):
    if len(data) < period:
        return None
    return sum(d['close'] for d in data[-period:]) / period

def calc_vol20(data):
    if len(data) < 21:
        return None
    returns = []
    for i in range(-20, 0):
        if data[i-1]['close'] > 0:
            r = (data[i]['close'] - data[i-1]['close']) / data[i-1]['close']
            returns.append(r)
    if len(returns) < 2:
        return None
    avg = sum(returns) / len(returns)
    var = sum((r - avg)**2 for r in returns) / (len(returns) - 1)
    daily_vol = math.sqrt(var)
    annual_vol = daily_vol * math.sqrt(252)
    return annual_vol * 100

def calc_atr(data, period=14):
    if len(data) < period + 1:
        return None
    trs = []
    for i in range(-period, 0):
        tr = max(
            data[i]['high'] - data[i]['low'],
            abs(data[i]['high'] - data[i-1]['close']),
            abs(data[i]['low'] - data[i-1]['close'])
        )
        trs.append(tr)
    return sum(trs) / len(trs)

def calc_adx(data, period=14):
    if len(data) < period * 2 + 1:
        return 0
    # 简化ADX计算
    plus_dm = []
    minus_dm = []
    tr_list = []
    for i in range(-period*2, 0):
        if i == -period*2:
            continue
        up_move = data[i]['high'] - data[i-1]['high']
        down_move = data[i-1]['low'] - data[i]['low']
        pdm = up_move if (up_move > down_move and up_move > 0) else 0
        mdm = down_move if (down_move > up_move and down_move > 0) else 0
        tr = max(
            data[i]['high'] - data[i]['low'],
            abs(data[i]['high'] - data[i-1]['close']),
            abs(data[i]['low'] - data[i-1]['close'])
        )
        plus_dm.append(pdm)
        minus_dm.append(mdm)
        tr_list.append(tr)
    
    # Wilder smoothing
    atr = sum(tr_list[:period]) / period
    pdm_sum = sum(plus_dm[:period])
    mdm_sum = sum(minus_dm[:period])
    
    for i in range(period, len(tr_list)):
        atr = (atr * (period - 1) + tr_list[i]) / period
        pdm_sum = (pdm_sum * (period - 1) + plus_dm[i]) / period
        mdm_sum = (mdm_sum * (period - 1) + minus_dm[i]) / period
    
    if atr == 0:
        return 0
    pdi = (pdm_sum / atr) * 100
    mdi = (mdm_sum / atr) * 100
    dx_sum = pdi + mdi
    if dx_sum == 0:
        return 0
    dx = abs(pdi - mdi) / dx_sum * 100
    return dx

def calc_ma60_cross_count(data, ma60):
    """计算近60日MA60穿越次数"""
    if len(data) < 60 or ma60 is None:
        return 0
    count = 0
    ma60_list = []
    for i in range(len(data) - 60, len(data)):
        ma = sum(d['close'] for d in data[i-60:i]) / 60
        ma60_list.append(ma)
    
    crosses = 0
    for i in range(1, len(ma60_list)):
        prev_above = data[len(data)-60+i-1]['close'] > ma60_list[i-1]
        curr_above = data[len(data)-60+i]['close'] > ma60_list[i]
        if prev_above != curr_above:
            crosses += 1
    return crosses

# ============ 指数分析 ============
indices = {
    'sh000300': '沪深300',
    'sh000905': '中证500',
    'sz399006': '创业板指'
}

index_results = {}
for code, name in indices.items():
    data = data_by_symbol.get(code, [])
    if not data:
        continue
    latest = data[-1]
    prev_close = data[-2]['close'] if len(data) > 1 else latest['close']
    vol20 = calc_vol20(data)
    ma60 = calc_ma(data, 60)
    adx = calc_adx(data, 14)
    cross_count = calc_ma60_cross_count(data, ma60)
    above_ma60 = latest['close'] > ma60 if ma60 else False
    
    # TRE状态判定
    tre_status = ""
    if vol20 and vol20 > 25:
        tre_status = "S4(风暴市)"
    elif adx > 25 and above_ma60:
        tre_status = "S1(强趋势)"
    elif adx < 15 and cross_count >= 3:
        tre_status = "S3(震荡市)"
    elif not above_ma60 and adx < 20:
        tre_status = "S3近似(弱震荡)"
    elif adx > 20 and not above_ma60:
        tre_status = "S2(趋弱)"
    else:
        tre_status = "S2(趋弱)"
    
    # 连续跌破MA60天数
    below_days = 0
    for d in reversed(data):
        ma60_at = sum(dd['close'] for dd in data[data.index(d)-60:data.index(d)]) / 60 if data.index(d) >= 60 else ma60
        if d['close'] < ma60_at:
            below_days += 1
        else:
            break
    
    change_pct = (latest['close'] - prev_close) / prev_close * 100
    
    index_results[code] = {
        'name': name,
        'date': latest['date'],
        'open': latest['open'],
        'close': latest['close'],
        'high': latest['high'],
        'low': latest['low'],
        'prev_close': prev_close,
        'change_pct': change_pct,
        'vol20': vol20,
        'ma60': ma60,
        'adx': adx,
        'cross_count': cross_count,
        'above_ma60': above_ma60,
        'below_days': below_days,
        'tre': tre_status
    }

# ============ R-04 闸门判定 ============
hs300_vol20 = index_results['sh000300']['vol20']
if hs300_vol20 < 15:
    gate_status = "闸门A(禁一切新建仓)"
elif hs300_vol20 >= 20:
    gate_status = "闸门B(禁S1/S2常规建仓)"
else:
    gate_status = "正常区(15-20%)"

# ============ 持仓分析 ============
holdings = [
    {
        'code': 'sh600276', 'name': '恒瑞医药', 'shares': 4200,
        'cost_price': 51.2726, 'buy_date': '2026-07-01', 'buy_high': 58.00
    },
    {
        'code': 'sh510300', 'name': '沪深300ETF', 'shares': 40700,
        'cost_price': 4.8224, 'buy_date': '2026-07-08', 'buy_high': 5.09
    },
    {
        'code': 'sz159650', 'name': '国开债ETF', 'shares': 1900,
        'cost_price': 107.78, 'buy_date': '2026-06-04', 'buy_high': 107.95
    }
]

holding_results = []
for h in holdings:
    data = data_by_symbol.get(h['code'], [])
    if not data:
        continue
    latest = data[-1]
    prev_close = data[-2]['close'] if len(data) > 1 else latest['close']
    
    ma60 = calc_ma(data, 60)
    atr = calc_atr(data, 14)
    vol20 = calc_vol20(data)
    
    current = latest['close']
    cost = h['cost_price']
    
    # 盈亏
    pnl = (current - cost) * h['shares']
    pnl_pct = (current - cost) / cost * 100
    
    # 动态回撤
    high_since_buy = h['buy_high']
    drawdown = (current - high_since_buy) / high_since_buy * 100
    
    # R-06止损带宽
    hold_days = 0
    for d in data:
        if d['date'] >= h['buy_date']:
            hold_days += 1
    bandwidth = 7 if hold_days <= 11 else 4
    
    # 【修正·ETF止损口径】策略11.4：个股P1=买入价-MIN(2×ATR,带宽%)；ETF E-P1=买入价-带宽%
    bw_amount = cost * bandwidth / 100
    if 'ETF' in h['name']:
        p1_stop = cost * (1 - bandwidth / 100)          # ETF E-P1
    else:
        min_stop = min(2 * atr, bw_amount) if atr else bw_amount
        p1_stop = cost - min_stop                       # 个股 P1
    
    # S4提前一档 (-11% from high)
    s4_line = high_since_buy * (1 - 0.11)
    
    # MA60偏离
    ma60_dev = (current - ma60) / ma60 * 100 if ma60 else 0
    
    # 状态判定
    p0_triggered = drawdown <= -5
    p1_triggered = current <= p1_stop
    s4_triggered = current <= s4_line
    
    change_pct = (latest['close'] - prev_close) / prev_close * 100
    
    holding_results.append({
        **h,
        'date': latest['date'],
        'open': latest['open'],
        'close': current,
        'high': latest['high'],
        'low': latest['low'],
        'prev_close': prev_close,
        'change_pct': change_pct,
        'ma60': ma60,
        'ma60_dev': ma60_dev,
        'atr': atr,
        'vol20': vol20,
        'hold_days': hold_days,
        'bandwidth': bandwidth,
        'p1_stop': p1_stop,
        's4_line': s4_line,
        'drawdown': drawdown,
        'pnl': pnl,
        'pnl_pct': pnl_pct,
        'p0_triggered': p0_triggered,
        'p1_triggered': p1_triggered,
        's4_triggered': s4_triggered,
        'above_ma60': current > ma60 if ma60 else False
    })

# ============ 药明康德观察池 ============
ymkd_data = data_by_symbol.get('sh603259', [])
ymkd = {}
if ymkd_data:
    latest = ymkd_data[-1]
    prev_close = ymkd_data[-2]['close']
    ma60 = calc_ma(ymkd_data, 60)
    vol20 = calc_vol20(ymkd_data)
    adx = calc_adx(ymkd_data, 14)
    ymkd = {
        'close': latest['close'],
        'open': latest['open'],
        'prev_close': prev_close,
        'change_pct': (latest['close'] - prev_close) / prev_close * 100,
        'ma60': ma60,
        'ma60_dev': (latest['close'] - ma60) / ma60 * 100 if ma60 else 0,
        'vol20': vol20,
        'adx': adx,
        'high': latest['high'],
        'low': latest['low']
    }

# ============ 输出结果 ============
print("=" * 70)
print("2026-08-20 盘前分析计算结果")
print("=" * 70)

print("\n## R-04 波动率闸门")
print(f"沪深300 vol20 = {hs300_vol20:.2f}%")
print(f"闸门状态: {gate_status}")

print("\n## 三大指数TRE状态")
for code, r in index_results.items():
    print(f"{r['name']}: 收盘{r['close']:.2f} 涨跌{r['change_pct']:+.2f}% "
          f"vol20={r['vol20']:.2f}% MA60={r['ma60']:.2f} ADX={r['adx']:.1f} "
          f"穿越={r['cross_count']} MA60上方={r['above_ma60']} → {r['tre']}")

print("\n## 持仓监控")
for h in holding_results:
    print(f"\n{h['name']} ({h['code']})")
    print(f"  现价: {h['close']:.3f} (昨收{h['prev_close']:.3f}, 涨跌{h['change_pct']:+.2f}%)")
    print(f"  成本: {h['cost_price']:.4f} | 盈亏: ¥{h['pnl']:+,.0f} ({h['pnl_pct']:+.2f}%)")
    print(f"  MA60: {h['ma60']:.3f} (偏离{h['ma60_dev']:+.2f}%) | vol20: {h['vol20']:.2f}%")
    print(f"  ATR: {h['atr']:.4f} | 持有{h['hold_days']}天 | R-06带宽: {h['bandwidth']}%")
    print(f"  买入以来最高: {h['buy_high']:.2f} | 动态回撤: {h['drawdown']:.2f}%")
    print(f"  P1止损: {h['p1_stop']:.4f} | 距P1: {(h['close']-h['p1_stop'])/h['close']*100:.2f}%")
    print(f"  S4线(-11%): {h['s4_line']:.4f} | 距S4: {(h['close']-h['s4_line'])/h['close']*100:.2f}%")
    print(f"  P0触发: {'是' if h['p0_triggered'] else '否'} | P1触发: {'是!!!' if h['p1_triggered'] else '否'} | S4触发: {'是!!!' if h['s4_triggered'] else '否'}")

print("\n## 药明康德(观察池)")
if ymkd:
    print(f"  现价: {ymkd['close']:.2f} 涨跌{ymkd['change_pct']:+.2f}%")
    print(f"  MA60: {ymkd['ma60']:.2f} (偏离{ymkd['ma60_dev']:+.2f}%)")
    print(f"  vol20: {ymkd['vol20']:.2f}% ADX: {ymkd['adx']:.1f}")

# 保存JSON供HTML生成
output = {
    'date': '2026-08-20',
    'hs300_vol20': hs300_vol20,
    'gate_status': gate_status,
    'indices': index_results,
    'holdings': holding_results,
    'ymkd': ymkd
}

# 转换为可序列化格式
def to_serializable(obj):
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [to_serializable(i) for i in obj]
    elif isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    else:
        return str(obj)

with open(r"E:\fnOS\文档\证券\中线趋势共振策略\pre_0820_result.json", 'w', encoding='utf-8') as f:
    json.dump(to_serializable(output), f, ensure_ascii=False, indent=2)

print("\n\nJSON已保存到 pre_0820_result.json")
