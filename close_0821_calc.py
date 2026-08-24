#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-08-21 收盘总结计算脚本（含TRE状态机/ADX/MA60穿越/vol20双闸门/ATR止损线）"""
import json, math

# ============ 读取K线数据 ============
with open(r'E:\fnOS\文档\证券\中线趋势共振策略\kline_close_0821.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

data_by_symbol = {}
for line in lines:
    parts = line.strip().split('|')
    if len(parts) < 8 or parts[1].strip() in ('', 'symbol', '---'):
        continue
    try:
        symbol = parts[1].strip()
        data_by_symbol.setdefault(symbol, []).append({
            'date': parts[2].strip(),
            'open': float(parts[3]), 'close': float(parts[4]),
            'high': float(parts[5]), 'low': float(parts[6]),
        })
    except (ValueError, IndexError):
        continue

for sym in data_by_symbol:
    data_by_symbol[sym].reverse()  # 旧→新

# ============ 计算函数 ============
def calc_vol20(data):
    if len(data) < 21: return None
    rets = [(data[-i]['close'] - data[-(i+1)]['close']) / data[-(i+1)]['close'] for i in range(1, 21)]
    mean_r = sum(rets) / len(rets)
    var_r = sum((r - mean_r) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var_r) * math.sqrt(252) * 100

def calc_ma(data, period):
    if len(data) < period: return None
    return sum(d['close'] for d in data[-period:]) / period

def calc_atr(data, period=14):
    if len(data) < period + 1: return None
    trs = []
    for i in range(1, len(data)):
        h, l, pc = data[i]['high'], data[i]['low'], data[i-1]['close']
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
    return atr

def calc_adx(data, period=14):
    if len(data) < period * 2: return None
    trs, pdms, mdms = [], [], []
    for i in range(1, len(data)):
        h, l, pc = data[i]['high'], data[i]['low'], data[i-1]['close']
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        up, dn = h - data[i-1]['high'], data[i-1]['low'] - l
        pdms.append(up if (up > dn and up > 0) else 0)
        mdms.append(dn if (dn > up and dn > 0) else 0)
    atr = sum(trs[:period]) / period
    pdi = sum(pdms[:period]) / period
    mdi = sum(mdms[:period]) / period
    dxs = []
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
        pdi = (pdi * (period - 1) + pdms[i]) / period
        mdi = (mdi * (period - 1) + mdms[i]) / period
        if atr > 0 and (pdi + mdi) > 0:
            dxs.append(abs(pdi - mdi) / (pdi + mdi) * 100)
    return sum(dxs[-period:]) / period if dxs else None

def count_ma60_cross(data, ma_period=60, window=20):
    """近20个交易日收盘价上/下穿MA60次数"""
    if len(data) < ma_period + window: return None
    crosses = 0
    prev_above = None
    for i in range(len(data) - window, len(data)):
        ma60 = sum(d['close'] for d in data[i - ma_period + 1:i + 1]) / ma_period
        above = data[i]['close'] > ma60
        if prev_above is not None and above != prev_above:
            crosses += 1
        prev_above = above
    return crosses

# ============ 指数TRE状态判定 ============
indices = {'sh000300': '沪深300', 'sh000905': '中证500', 'sz399006': '创业板指'}
idx_results = {}
for sym, name in indices.items():
    d = data_by_symbol[sym]
    today, prev = d[-1], d[-2]
    vol20 = calc_vol20(d)
    ma60 = calc_ma(d, 60)
    adx = calc_adx(d)
    crosses = count_ma60_cross(d)
    chg = (today['close'] - prev['close']) / prev['close'] * 100
    above_ma60 = today['close'] > ma60

    # TRE矩阵判定（单指数）
    if (adx or 0) >= 20 and (crosses or 0) <= 3 and vol20 < 18:
        state = 'S1'
    elif vol20 is not None and vol20 > 25:
        state = 'S4'
    elif (crosses or 0) >= 5:
        state = 'S4'
    elif (adx or 0) < 15 and 3 <= (crosses or 0) <= 4 and 15 <= (vol20 or 0) <= 25:
        state = 'S3'
    elif (adx or 0) < 15 and vol20 is not None and vol20 > 18:
        state = 'S4'  # ADX<15且波动率>18%（接近S1但不完整+穿越>3归S2，此处按多因子从严）
    else:
        state = 'S2'
    idx_results[sym] = {
        'name': name, 'close': today['close'], 'prev': prev['close'],
        'chg_pct': round(chg, 2), 'open': today['open'], 'high': today['high'], 'low': today['low'],
        'vol20': round(vol20, 2) if vol20 else None,
        'ma60': round(ma60, 2) if ma60 else None,
        'above_ma60': above_ma60,
        'ma60_bias': round((today['close'] - ma60) / ma60 * 100, 2),
        'adx14': round(adx, 1) if adx else None,
        'ma60_cross_20d': crosses, 'tre_state': state,
    }

# 全局TRE = 多数指数状态（从严）
states = [v['tre_state'] for v in idx_results.values()]
rank = {'S1': 0, 'S2': 1, 'S3': 2, 'S4': 3}
global_tre = max(states, key=lambda s: rank[s]) if states else None
# 多数判定：S4数量占多数或波动率>25占多数
s4_count = states.count('S4')
global_tre_final = 'S4' if s4_count >= 2 else global_tre

# ============ R-04波动率闸门（口径=沪深300 vol20） ============
vol300 = idx_results['sh000300']['vol20']
if vol300 < 15:
    gate = 'A（禁一切新建仓）'
elif vol300 >= 20:
    gate = 'B（禁S1/S2常规建仓）'
else:
    gate = '正常区（15-20%）'

# ============ 持仓计算 ============
holdings_cfg = {
    'sh510300': {'name': '沪深300ETF', 'code': '510300', 'shares': 20400, 'cost': 4.8224,
                 'buy_date': '2026-07-08', 'hold_days': 44, 'type': 'ETF', 'sold_today': 20300},
    'sz159650': {'name': '国开债ETF', 'code': '159650', 'shares': 1800, 'cost': 107.587,
                 'buy_date': '2026-06-04', 'hold_days': 78, 'type': 'ETF'},
}
hold_results = {}
for sym, h in holdings_cfg.items():
    d = data_by_symbol[sym]
    today, prev = d[-1], d[-2]
    chg = (today['close'] - prev['close']) / prev['close'] * 100
    atr = calc_atr(d)
    band = 0.04 if h['hold_days'] > 11 else 0.07  # R-06
    min_stop = min(2 * atr, h['cost'] * band)
    p1 = h['cost'] - min_stop
    ma60 = calc_ma(d, 60)
    info = dict(h)
    info.update({
        'close': today['close'], 'prev': prev['close'], 'chg_pct': round(chg, 2),
        'high': today['high'], 'low': today['low'],
        'market_value': round(today['close'] * h['shares'], 2),
        'floating_pnl': round((today['close'] - h['cost']) * h['shares'], 2),
        'floating_pnl_pct': round((today['close'] - h['cost']) / h['cost'] * 100, 2),
        'atr14': round(atr, 4), 'p1_band': f'{band*100:.0f}%',
        'p1_line': round(p1, 4), 'p1_gap': round(today['close'] - p1, 4),
        'p1_triggered': today['close'] < p1,
        'p1_intraday_high_above': today['high'] > p1,
        'ma60': round(ma60, 3), 'above_ma60': today['close'] > ma60,
        'ma60_bias': round((today['close'] - ma60) / ma60 * 100, 2),
        'vol20': round(calc_vol20(d), 2),
    })
    hold_results[sym] = info

# 今日已实现交易：510300部分卖出
sold = {'shares': 20300, 'price': 4.68, 'proceeds': round(20300 * 4.68, 2),
        'realized_pnl': round((4.68 - 4.8224) * 20300, 2),
        'realized_pct': round((4.68 - 4.8224) / 4.8224 * 100, 2)}

# 观察池：药明康德
d603 = data_by_symbol['sh603259']
t603, p603 = d603[-1], d603[-2]
yaoming = {
    'name': '药明康德', 'code': '603259', 'close': t603['close'],
    'prev': p603['close'], 'chg_pct': round((t603['close'] - p603['close']) / p603['close'] * 100, 2),
    'ma60': round(calc_ma(d603, 60), 2),
    'ma60_bias': round((t603['close'] - calc_ma(d603, 60)) / calc_ma(d603, 60) * 100, 2),
    'vol20': round(calc_vol20(d603), 2),
}

# ============ 账户总览（估算） ============
# 0820 F4: 总资产795,113.90 / 可用366,896.62（含T+1恒瑞~44,534今日到账）
cash_available = 366896.62 + 44534  # 今日可用（恒瑞T+1已入账）
cash_t1_pending = sold['proceeds']  # 今日卖出T+1下周一可用
cash_total = cash_available + cash_t1_pending
mv_510300 = hold_results['sh510300']['market_value']
mv_159650 = hold_results['sz159650']['market_value']
mv_total = mv_510300 + mv_159650
total_assets = cash_total + mv_total

# ============ 输出 ============
print("=" * 62)
print("2026-08-21 收盘总结计算结果")
print("=" * 62)

print("\n【三大指数与TRE】")
for sym in indices:
    r = idx_results[sym]
    print(f"  {r['name']}: {r['close']} ({r['chg_pct']:+.2f}%) | vol20={r['vol20']}% | ADX14={r['adx14']} | MA60={r['ma60']}({'上方' if r['above_ma60'] else '下方'}{r['ma60_bias']:+.2f}%) | 穿越20日={r['ma60_cross_20d']}次 → {r['tre_state']}")
print(f"  → 全局TRE: {global_tre_final}（S4数量={s4_count}/3）")

print(f"\n【R-04波动率闸门】vol20(沪深300)={vol300}% → 闸门{gate}")

print("\n【持仓】")
for sym in hold_results:
    r = hold_results[sym]
    print(f"\n  {r['name']}({r['code']}) 持有{r['hold_days']}日")
    print(f"    收盘: {r['close']} ({r['chg_pct']:+.2f}%) 高{r['high']} 低{r['low']}")
    print(f"    市值: ¥{r['market_value']:,.2f} | 浮动: ¥{r['floating_pnl']:+,.2f} ({r['floating_pnl_pct']:+.2f}%)")
    print(f"    P1={r['p1_line']} (2×ATR={2*r['atr14']:.4f} vs 带宽{r['p1_band']}={r['cost']*(0.04 if r['hold_days']>11 else 0.07):.4f}, 取小)")
    print(f"    收盘距P1: {r['p1_gap']:+.4f} → {'P1仍触发🔴' if r['p1_triggered'] else 'P1上方✅'} | 盘中高点{r['high']} {'曾收复P1⚠️' if r['p1_intraday_high_above'] else '未及P1'}")
    print(f"    MA60={r['ma60']}({'上方' if r['above_ma60'] else '下方'}) | vol20={r['vol20']}%")

print(f"\n【今日已实现交易】510300卖出{sold['shares']}股@{sold['price']}")
print(f"  回笼: ¥{sold['proceeds']:,.2f}（T+1下周一可用）| 实现盈亏: ¥{sold['realized_pnl']:+,.2f} ({sold['realized_pct']:+.2f}%)")

print(f"\n【观察池】药明康德: {yaoming['close']} ({yaoming['chg_pct']:+.2f}%) | MA60偏离{yaoming['ma60_bias']:+.2f}% | vol20={yaoming['vol20']}%")

print(f"\n【账户总览（估算）】")
print(f"  可用现金(含恒瑞T+1入账): ¥{cash_available:,.2f}")
print(f"  今日卖出T+1待入账: ¥{cash_t1_pending:,.2f}（下周一可用）")
print(f"  持仓市值: 510300 ¥{mv_510300:,.2f} + 159650 ¥{mv_159650:,.2f} = ¥{mv_total:,.2f}")
print(f"  总资产(估算): ¥{total_assets:,.2f}")
print(f"  外高B(100股,独立管理): 不计入策略体系")

# 保存JSON
output = {
    'date': '2026-08-21',
    'indices': idx_results,
    'global_tre': global_tre_final, 's4_count': s4_count,
    'vol20_hs300': vol300, 'gate': gate,
    'holdings': hold_results, 'sold_today': sold,
    'observation': yaoming,
    'account': {
        'cash_available': round(cash_available, 2),
        'cash_t1_pending': cash_t1_pending,
        'mv_510300': mv_510300, 'mv_159650': mv_159650,
        'total_assets': round(total_assets, 2),
    },
}
with open(r'E:\fnOS\文档\证券\中线趋势共振策略\close_0821_result.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print("\n[JSON已保存: close_0821_result.json]")
