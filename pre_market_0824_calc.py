#!/usr/bin/env python3
"""2026-08-24 盘前分析计算脚本"""
import json, math

# === 读取K线数据 ===
with open(r'E:\fnOS\文档\证券\中线趋势共振策略\kline_pre_0824.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

data_by_symbol = {}
for line in lines:
    parts = line.strip().split('|')
    if len(parts) < 8 or parts[1].strip() in ('', 'symbol', '---', ''):
        continue
    try:
        symbol = parts[1].strip()
        date = parts[2].strip()
        open_p = float(parts[3])
        close = float(parts[4])
        high = float(parts[5])
        low = float(parts[6])
        volume = float(parts[7]) if parts[7] else 0
        if symbol not in data_by_symbol:
            data_by_symbol[symbol] = []
        data_by_symbol[symbol].append({
            'date': date, 'open': open_p, 'close': close,
            'high': high, 'low': low, 'volume': volume
        })
    except (ValueError, IndexError):
        continue

for sym in data_by_symbol:
    data_by_symbol[sym].reverse()

# === 计算函数 ===
def calc_vol20(data):
    if len(data) < 21:
        return None
    returns = []
    for i in range(1, 21):
        prev_close = data[-(i+1)]['close']
        curr_close = data[-i]['close']
        returns.append((curr_close - prev_close) / prev_close)
    mean_r = sum(returns) / len(returns)
    var_r = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(var_r) * math.sqrt(252) * 100

def calc_ma(data, period):
    if len(data) < period:
        return None
    return sum(d['close'] for d in data[-period:]) / period

def calc_adx(data, period=14):
    if len(data) < period * 2:
        return None
    tr_list, plus_dm, minus_dm = [], [], []
    for i in range(1, len(data)):
        high, low, prev_close = data[i]['high'], data[i]['low'], data[i-1]['close']
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        up_move = high - data[i-1]['high']
        down_move = data[i-1]['low'] - low
        pdm = up_move if (up_move > down_move and up_move > 0) else 0
        mdm = down_move if (down_move > up_move and down_move > 0) else 0
        tr_list.append(tr)
        plus_dm.append(pdm)
        minus_dm.append(mdm)
    atr = sum(tr_list[:period]) / period
    pdi_sum = sum(plus_dm[:period]) / period
    mdi_sum = sum(minus_dm[:period]) / period
    dx_list = []
    for i in range(period, len(tr_list)):
        atr = (atr * (period - 1) + tr_list[i]) / period
        pdi_sum = (pdi_sum * (period - 1) + plus_dm[i]) / period
        mdi_sum = (mdi_sum * (period - 1) + minus_dm[i]) / period
        pdi = (pdi_sum / atr) * 100 if atr > 0 else 0
        mdi = (mdi_sum / atr) * 100 if atr > 0 else 0
        dx = abs(pdi - mdi) / (pdi + mdi) * 100 if (pdi + mdi) > 0 else 0
        dx_list.append(dx)
    if len(dx_list) < period:
        return None
    adx = sum(dx_list[-period:]) / period
    return adx

def calc_atr(data, period=14):
    if len(data) < period + 1:
        return None
    tr_list = []
    for i in range(1, len(data)):
        high, low, prev_close = data[i]['high'], data[i]['low'], data[i-1]['close']
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)
    return sum(tr_list[-period:]) / period

def count_ma60_crossings(data, ma60_values):
    crossings = 0
    for i in range(-min(20, len(data)-1), 0):
        if ma60_values[i-1] is not None and ma60_values[i] is not None:
            prev_above = data[i-1]['close'] > ma60_values[i-1]
            curr_above = data[i]['close'] > ma60_values[i]
            if prev_above != curr_above:
                crossings += 1
    return crossings

# === 指数指标 ===
results = {}
for sym, name in [('sh000300', '沪深300'), ('sh000905', '中证500'), ('sz399006', '创业板指')]:
    data = data_by_symbol.get(sym, [])
    if not data:
        continue
    vol20 = calc_vol20(data)
    ma60 = calc_ma(data, 60)
    adx = calc_adx(data, 14)
    last = data[-1]
    prev = data[-2] if len(data) > 1 else None
    ma60_vals = [calc_ma(data[:i+1], 60) if i >= 59 else None for i in range(len(data))]
    crossings = count_ma60_crossings(data, ma60_vals)
    above_ma60 = last['close'] > ma60 if ma60 else False
    deviation = (last['close'] - ma60) / ma60 * 100 if ma60 else 0

    tre = 'Unknown'
    if vol20 and vol20 > 25:
        tre = 'S4(风暴市)'
    elif adx and adx > 25 and above_ma60:
        tre = 'S1(强趋势)'
    elif adx and adx < 15 and crossings >= 3:
        tre = 'S3(震荡)'
    elif adx and adx < 20 and not above_ma60:
        tre = 'S2(趋弱)'
    elif adx and adx < 15:
        tre = 'S3近似(弱震荡)'

    results[sym] = {
        'name': name, 'date': last['date'], 'close': last['close'],
        'open': last['open'], 'high': last['high'], 'low': last['low'],
        'prev_close': prev['close'] if prev else None,
        'vol20': vol20, 'ma60': ma60, 'adx': adx,
        'above_ma60': above_ma60, 'deviation': deviation,
        'crossings': crossings, 'tre': tre
    }
    print(f"{name}({sym}): date={last['date']} close={last['close']} prev={prev['close'] if prev else 'N/A'} "
          f"vol20={vol20:.2f}% MA60={ma60:.2f}(dev={deviation:+.2f}%) ADX={adx:.1f} TRE={tre}")

# === R-04 闸门判定 ===
hs300_vol20 = results.get('sh000300', {}).get('vol20', 0)
if hs300_vol20:
    if hs300_vol20 < 15:
        gate = 'A(禁一切新建仓)'
    elif hs300_vol20 >= 20:
        gate = 'B(禁S1/S2常规建仓)'
    else:
        gate = '正常区(15-20%)'
    print(f"\nR-04闸门: vol20={hs300_vol20:.2f}% → {gate}")

# === 全局TRE ===
s4_count = sum(1 for k in ['sh000300','sh000905','sz399006'] if results.get(k,{}).get('tre','').startswith('S4'))
global_tre = 'S4(风暴市)' if s4_count >= 2 else '非S4'
print(f"全局TRE: {global_tre} (S4指数数: {s4_count}/3)")

# === 持仓监控 ===
print("\n=== 持仓监控 ===")
# 510300: 剩余20,400股, 原买入07-08/07-09, 成本4.8224
# 今日裁决: 09:25集合竞价清仓
holdings = [
    {'sym': 'sh510300', 'name': '沪深300ETF', 'cost': 4.8224, 'shares': 20400, 'buy_date': '2026-07-08'},
    {'sym': 'sz159650', 'name': '国开债ETF', 'cost': 107.587, 'shares': 1800, 'buy_date': '2026-06-04'},
]

for h in holdings:
    data = data_by_symbol.get(h['sym'], [])
    if not data:
        continue
    last = data[-1]
    atr = calc_atr(data, 14)
    ma60 = calc_ma(data, 60)
    above_ma60 = last['close'] > ma60 if ma60 else False
    vol20_h = calc_vol20(data)

    # 持有天数
    from datetime import date
    buy_d = date(2026, int(h['buy_date'][5:7]), int(h['buy_date'][8:10]))
    today_d = date(2026, 8, 24)
    hold_days = (today_d - buy_d).days

    # R-06止损带宽
    sl_band = 0.07 if hold_days <= 11 else 0.04

    # ETF E-P1 = cost × (1 - bandwidth)
    if 'ETF' in h['name']:
        p1 = h['cost'] * (1 - sl_band)
    else:
        sl_amount = min(2 * atr, h['cost'] * sl_band) if atr else h['cost'] * sl_band
        p1 = h['cost'] - sl_amount

    # 买入以来最高
    buy_idx = None
    for i, d in enumerate(data):
        if d['date'] >= h['buy_date']:
            buy_idx = i
            break
    peak_since_buy = max(d['high'] for d in data[buy_idx:]) if buy_idx is not None else last['high']
    drawdown = (last['close'] - peak_since_buy) / peak_since_buy * 100

    # P0触发(-5%)
    p0_triggered = drawdown <= -5
    # S4提前一档(-11%)
    s4_line = peak_since_buy * 0.89
    s4_triggered = last['close'] < s4_line
    # P1触发
    p1_triggered = last['close'] < p1

    # 市值与盈亏
    market_value = last['close'] * h['shares']
    pnl = (last['close'] - h['cost']) * h['shares']
    pnl_pct = (last['close'] - h['cost']) / h['cost'] * 100

    # P12移动止盈
    p12_trigger = peak_since_buy * 1.15
    p12_active = last['close'] >= p12_trigger

    print(f"\n{h['name']}({h['sym']}):")
    print(f"  日期={last['date']} 收盘={last['close']} 开盘={last['open']} 前收={data[-2]['close'] if len(data)>1 else 'N/A'}")
    print(f"  成本={h['cost']} 持股={h['shares']} 持有天数={hold_days}日")
    print(f"  市值=¥{market_value:,.0f} 浮动盈亏=¥{pnl:+,.0f}({pnl_pct:+.2f}%)")
    print(f"  ATR(14)={atr:.4f} vol20={vol20_h:.2f}% 止损带宽={sl_band*100:.0f}%")
    print(f"  E-P1止损={p1:.4f} → {'触发!' if p1_triggered else '未触发'}")
    print(f"  买入以来最高={peak_since_buy} 动态回撤={drawdown:.2f}%")
    print(f"  P0(-5%)={'触发' if p0_triggered else '未触发'} S4(-11%)={'触发' if s4_triggered else '未触发'}")
    print(f"  MA60={ma60:.4f} 上方={above_ma60} P12={'激活' if p12_active else '未激活'}")

    h.update({
        'date': last['date'], 'close': last['close'], 'open': last['open'],
        'high': last['high'], 'low': last['low'], 'prev_close': data[-2]['close'] if len(data)>1 else None,
        'atr': atr, 'ma60': ma60, 'vol20': vol20_h, 'above_ma60': above_ma60,
        'p1': p1, 'p1_triggered': p1_triggered,
        'peak_since_buy': peak_since_buy, 'drawdown': drawdown,
        'p0_triggered': p0_triggered, 's4_line': s4_line, 's4_triggered': s4_triggered,
        'market_value': market_value, 'pnl': pnl, 'pnl_pct': pnl_pct,
        'p12_active': p12_active, 'p12_trigger': p12_trigger,
        'sl_band': sl_band, 'hold_days': hold_days
    })
    results[h['sym']] = h

# === 药明康德(观察池) ===
ymkd = data_by_symbol.get('sh603259', [])
if ymkd:
    last_ym = ymkd[-1]
    ma60_ym = calc_ma(ymkd, 60)
    atr_ym = calc_atr(ymkd, 14)
    vol20_ym = calc_vol20(ymkd)
    adx_ym = calc_adx(ymkd, 14)
    above_ma60_ym = last_ym['close'] > ma60_ym if ma60_ym else False
    deviation = (last_ym['close'] - ma60_ym) / ma60_ym * 100 if ma60_ym else 0
    print(f"\n药明康德(603259)观察池:")
    print(f"  日期={last_ym['date']} 收盘={last_ym['close']} MA60={ma60_ym:.2f}(偏离={deviation:+.2f}%)")
    print(f"  ATR={atr_ym:.2f} vol20={vol20_ym:.2f}% ADX={adx_ym:.1f} 上方MA60={above_ma60_ym}")
    results['sh603259'] = {
        'name': '药明康德(观察)', 'date': last_ym['date'], 'close': last_ym['close'],
        'ma60': ma60_ym, 'deviation': deviation, 'vol20': vol20_ym, 'above_ma60': above_ma60_ym,
        'adx': adx_ym, 'atr': atr_ym
    }

# === 三层资金架构 ===
print("\n=== 三层资金架构 ===")
# 0820 F4基准: 总资产795,113.90 / 可用366,896.62
# 恒瑞0820卖出T+1(0821到账): +¥44,534 (49.52*900-费用)
# 510300 0821卖出20,300股T+1(0824到账): +¥95,004
cash = 366896.62 + 44534 + 95004  # 恒瑞T+1 + 510300部分T+1
v510300 = results.get('sh510300', {}).get('market_value', 95472)
v159650 = results.get('sz159650', {}).get('market_value', 194314)
total = cash + v510300 + v159650

print(f"现金(含两笔T+1): ¥{cash:,.0f}")
print(f"  - 0820 F4可用: ¥366,896.62")
print(f"  - 恒瑞T+1(0821到账): ¥44,534")
print(f"  - 510300部分T+1(0824到账): ¥95,004")
print(f"510300市值(剩余20,400股): ¥{v510300:,.0f}")
print(f"159650市值: ¥{v159650:,.0f}")
print(f"总资产估算: ¥{total:,.0f}")

# 今日竞价清仓510300后
cash_after_sell = cash + v510300  # T+1(0825)到账
print(f"\n【今日竞价清仓后预估】")
print(f"  竞价卖出510300 20,400股@~4.68 → 回笼~¥{v510300:,.0f}(T+1 0825到账)")
print(f"  现金(含T+1): ¥{cash_after_sell:,.0f} ({cash_after_sell/total*100:.1f}%)")
print(f"  159650: ¥{v159650:,.0f} ({v159650/total*100:.1f}%)")
print(f"  防守底盘: 0% (清仓)")
print(f"  稳定器(159650): {v159650/total*100:.1f}%")
print(f"  进攻线: 0% (B3模拟盘阶段)")

# 510300全程亏损
total_510300_cost = 40700 * 4.8224
total_510300_proceeds = 20300 * 4.68 + 20400 * 4.68  # 假设竞价@4.68
total_510300_pnl = total_510300_proceeds - total_510300_cost
print(f"\n510300全程盈亏(预估):")
print(f"  总成本: 40,700 × 4.8224 = ¥{total_510300_cost:,.2f}")
print(f"  已回收: 20,300 × 4.68 = ¥{20300*4.68:,.2f}")
print(f"  剩余预估: 20,400 × 4.68 = ¥{20400*4.68:,.2f}")
print(f"  总回收: ¥{20300*4.68 + 20400*4.68:,.2f}")
print(f"  全程实现亏损: ¥{total_510300_pnl:,.2f} ({total_510300_pnl/total_510300_cost*100:.2f}%)")

# === 保存结果 ===
output = {
    'indices': {k: v for k, v in results.items() if k.startswith('sh0') or k.startswith('sz399')},
    'holdings': {k: v for k, v in results.items() if k in ('sh510300', 'sz159650')},
    'observation': results.get('sh603259', {}),
    'r04_gate': gate if hs300_vol20 else 'Unknown',
    'global_tre': global_tre,
    'hs300_vol20': hs300_vol20,
    'cash': cash,
    'cash_after_sell': cash_after_sell,
    'total_assets': total,
    'total_510300_pnl': total_510300_pnl,
}

with open(r'E:\fnOS\文档\证券\中线趋势共振策略\pre_0824_result.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2, default=str)

print(f"\n结果已保存: pre_0824_result.json")
