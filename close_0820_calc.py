#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-08-20 收盘总结计算脚本"""

import json

# ============ 收盘数据（0820） ============
# 昨日(0819)收盘
prev_close = {
    'sh000300': 4588.70, 'sh000905': 7783.46, 'sz399006': 3473.49,
    'sh600276': 52.66, 'sh510300': 4.654, 'sz159650': 107.949, 'sh603259': 167.14
}

# 今日(0820)收盘
today_data = {
    'sh000300': {'open': 4613.3, 'close': 4592.75, 'high': 4631.13, 'low': 4569.23},
    'sh000905': {'open': 7864.68, 'close': 7850.4, 'high': 7923.91, 'low': 7796.28},
    'sz399006': {'open': 3517.65, 'close': 3495.59, 'high': 3531.92, 'low': 3459.57},
    'sh600276': {'open': 51.0, 'close': 49.5, 'high': 51.53, 'low': 48.16},
    'sh510300': {'open': 4.67, 'close': 4.653, 'high': 4.689, 'low': 4.632},
    'sz159650': {'open': 107.944, 'close': 107.948, 'high': 107.951, 'low': 107.943},
    'sh603259': {'open': 171.0, 'close': 167.9, 'high': 173.6, 'low': 165.97},
}

# ============ 持仓参数 ============
holdings = {
    'sh600276': {
        'name': '恒瑞医药', 'code': '600276', 'shares': 900, 'cost': 51.2726,
        'buy_date': '2026-07-01', 'hold_days': 50, 'peak': 58.00,
        'status': '已清仓', 'sold_price': 49.52, 'sold_time': '14:46盘中'
    },
    'sh510300': {
        'name': '沪深300ETF', 'code': '510300', 'shares': 40700, 'cost': 4.8224,
        'buy_date': '2026-07-08', 'hold_days': 43, 'peak': None,
        'status': '持仓中'
    },
    'sz159650': {
        'name': '国开债ETF', 'code': '159650', 'shares': 1800, 'cost': 107.587,
        'buy_date': '2026-06-04', 'hold_days': 77, 'peak': None,
        'status': '持仓中'
    },
    'sh603259': {
        'name': '药明康德(观察池)', 'code': '603259', 'shares': None, 'cost': None,
        'buy_date': None, 'hold_days': None, 'peak': None,
        'status': '观察池'
    },
}

# ============ 计算指标 ============
results = {}

# 1. 指数涨跌
for code in ['sh000300', 'sh000905', 'sz399006']:
    d = today_data[code]
    chg = (d['close'] - prev_close[code]) / prev_close[code] * 100
    results[code] = {
        'close': d['close'], 'prev': prev_close[code],
        'chg_pct': round(chg, 2), 'open': d['open'], 'high': d['high'], 'low': d['low']
    }

# 2. 持仓计算
total_market_value = 0
total_floating_pnl = 0

for code in ['sh600276', 'sh510300', 'sz159650', 'sh603259']:
    h = holdings[code]
    d = today_data[code]
    chg = (d['close'] - prev_close[code]) / prev_close[code] * 100
    
    info = {
        'name': h['name'], 'code': h['code'], 'status': h['status'],
        'close': d['close'], 'prev': prev_close[code], 'chg_pct': round(chg, 2),
        'open': d['open'], 'high': d['high'], 'low': d['low'],
    }
    
    if h['shares'] and h['cost']:
        info['shares'] = h['shares']
        info['cost'] = h['cost']
        info['market_value'] = round(d['close'] * h['shares'], 2)
        info['cost_total'] = round(h['cost'] * h['shares'], 2)
        info['floating_pnl'] = round((d['close'] - h['cost']) * h['shares'], 2)
        info['floating_pnl_pct'] = round((d['close'] - h['cost']) / h['cost'] * 100, 2)
        
        if h['status'] == '持仓中':
            total_market_value += info['market_value']
            total_floating_pnl += info['floating_pnl']
        
        # P1止损 (R-06: >11日 → 4%带宽)
        hold_days = h['hold_days']
        if hold_days > 11:
            p1_bandwidth = 0.04
        else:
            p1_bandwidth = 0.07
        info['p1_stop'] = round(h['cost'] * (1 - p1_bandwidth), 4)
        info['p1_triggered'] = d['close'] < info['p1_stop']
        info['p1_intraday_breach'] = d['low'] < info['p1_stop']
        info['hold_days'] = hold_days
        
        # S4即刻清仓线 (买入以来最高 × 0.89)
        if h['peak']:
            info['peak'] = h['peak']
            info['s4_line'] = round(h['peak'] * 0.89, 2)
            info['drawdown'] = round((d['close'] - h['peak']) / h['peak'] * 100, 2)
            info['s4_triggered'] = d['close'] < info['s4_line']
        
        # P0触发 (-5%)
        info['p0_line'] = round(h['cost'] * 0.95, 4)
        info['p0_triggered'] = d['close'] < info['p0_line']
    
    if h['status'] == '已清仓':
        info['sold_price'] = h['sold_price']
        info['realized_pnl'] = round((h['sold_price'] - h['cost']) * h['shares'], 2)
        info['realized_pnl_pct'] = round((h['sold_price'] - h['cost']) / h['cost'] * 100, 2)
        info['proceeds'] = round(h['sold_price'] * h['shares'], 2)
    
    results[code] = info

# 3. 波动率 (vol20 - 沪深300)
# 从数据文件读取计算
vol20_raw = [
    4725.81, 4588.70, 4734.07, 4672.28, 4665.88, 4663.95, 4690.92, 4663.79,
    4702.02, 4694.44, 4651.31, 4658.15, 4600.93, 4543.18, 4588.20, 4549.72,
    4600.26, 4569.52, 4702.43, 4649.19, 4728.00, 4717.24, 4739.23, 4598.32,
    4529.10, 4598.32
]
# 20日收益率标准差 × sqrt(250)
import math
returns = []
for i in range(1, len(vol20_raw)):
    r = (vol20_raw[i] - vol20_raw[i-1]) / vol20_raw[i-1]
    returns.append(r)
# 最近20日
recent = returns[-20:]
mean_r = sum(recent) / len(recent)
var_r = sum((r - mean_r)**2 for r in recent) / (len(recent) - 1)
std_r = math.sqrt(var_r)
vol20 = std_r * math.sqrt(250) * 100

# 4. 恒瑞医药已实现盈亏
hengrui_realized = results['sh600276']['realized_pnl']

# 5. 外高B
waigaob = {'shares': 100, 'cost_usd': 1.276, 'realized_usd': -2794, 'note': '2026-08-07卖出4400股@$0.641'}

# 6. 账户总览
# 0803基准: 总资产795,768 / 可用366,735 / 市值429,033
# 变化: 恒瑞卖出回笼44,568, 510300浮亏, 159650浮盈
cash_approx = 366735 + 44568  # 0803可用 + 恒瑞回笼
market_value_now = total_market_value
total_assets_approx = cash_approx + market_value_now

# 输出结果
print("=" * 60)
print("2026-08-20 收盘总结计算结果")
print("=" * 60)

print("\n【三大指数】")
for code, name in [('sh000300', '沪深300'), ('sh000905', '中证500'), ('sz399006', '创业板指')]:
    r = results[code]
    print(f"  {name}: {r['close']} ({r['chg_pct']:+.2f}%) 开{r['open']} 高{r['high']} 低{r['low']}")

print(f"\n【R-04波动率】vol20 = {vol20:.2f}%")
if vol20 >= 20:
    print(f"  → 闸门B触发（≥20%禁S1/S2常规建仓）")
elif vol20 < 15:
    print(f"  → 闸门A触发（<15%禁一切新建仓）")
else:
    print(f"  → 正常区（15-20%）")

print("\n【持仓】")
for code in ['sh600276', 'sh510300', 'sz159650']:
    r = results[code]
    print(f"\n  {r['name']}({r['code']}) — {r['status']}")
    print(f"    收盘: {r['close']} ({r['chg_pct']:+.2f}%) 开{r['open']} 高{r['high']} 低{r['low']}")
    if r['status'] == '已清仓':
        print(f"    卖出价: {r['sold_price']} / 回笼: ¥{r['proceeds']:,.2f}")
        print(f"    实现盈亏: ¥{r['realized_pnl']:+,.2f} ({r['realized_pnl_pct']:+.2f}%)")
        print(f"    R-03洗仓封堵: 30日至2026-09-19")
    elif r['status'] == '持仓中':
        print(f"    持仓: {r['shares']}股 / 成本: {r['cost']}")
        print(f"    市值: ¥{r['market_value']:,.2f} / 浮动盈亏: ¥{r['floating_pnl']:+,.2f} ({r['floating_pnl_pct']:+.2f}%)")
        print(f"    P1止损: {r['p1_stop']} (带宽{('4%' if r['hold_days']>11 else '7%')}, 持有{r['hold_days']}日)")
        print(f"    P1触发: {'是🔴' if r['p1_triggered'] else '否'} / 盘中击穿: {'是⚠️' if r.get('p1_intraday_breach') else '否'}")
        if 's4_line' in r:
            print(f"    动态回撤: {r['drawdown']:.2f}% (峰值{r['peak']}→现{r['close']})")
            print(f"    S4清仓线: {r['s4_line']} → {'已跌破🔴' if r['s4_triggered'] else '上方'}")

r603 = results['sh603259']
print(f"\n  {r603['name']} — {r603['status']}")
print(f"    收盘: {r603['close']} ({r603['chg_pct']:+.2f}%) 开{r603['open']} 高{r603['high']} 低{r603['low']}")

print(f"\n【账户总览（估算）】")
print(f"  现金(估算): ¥{cash_approx:,.0f}")
print(f"  持仓市值: ¥{market_value_now:,.2f}")
print(f"  总资产(估算): ¥{total_assets_approx:,.0f}")
print(f"  今日实现亏损(恒瑞): ¥{hengrui_realized:+,.2f}")
print(f"  浮动盈亏(510300+159650): ¥{total_floating_pnl:+,.2f}")
print(f"  外高B已实现亏损: $-2,794.00")

# 保存JSON
output = {
    'date': '2026-08-20',
    'indices': {k: v for k, v in results.items() if k in ['sh000300', 'sh000905', 'sz399006']},
    'holdings': {k: v for k, v in results.items() if k in ['sh600276', 'sh510300', 'sz159650', 'sh603259']},
    'vol20': round(vol20, 2),
    'vol20_gate': 'B' if vol20 >= 20 else ('A' if vol20 < 15 else 'normal'),
    'total_market_value': round(market_value_now, 2),
    'total_floating_pnl': round(total_floating_pnl, 2),
    'today_realized_pnl': hengrui_realized,
    'cash_approx': cash_approx,
    'total_assets_approx': round(total_assets_approx, 0),
}
with open('E:/fnOS/文档/证券/中线趋势共振策略/close_0820_result.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print("\n[JSON已保存]")
