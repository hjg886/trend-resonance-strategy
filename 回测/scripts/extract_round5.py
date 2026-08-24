# -*- coding: utf-8 -*-
"""E 系列结果提取与对比"""
import json, math, os
import sys
sys.path.insert(0, os.path.dirname(__file__))

def metrics(fn):
    d = json.load(open(fn, encoding='utf-8'))
    hist = d.get('hist', [])
    eq = [h['equity'] for h in hist]
    n = len(eq)
    if n < 2:
        return None
    ann = (eq[-1]/eq[0])**(252.0/n) - 1
    peak = eq[0]; mdd = 0.0
    for e in eq:
        peak = max(peak, e)
        mdd = max(mdd, 1 - e/peak)
    rets = [eq[i]/eq[i-1]-1 for i in range(1, n)]
    mr = sum(rets)/len(rets)
    var = sum((r-mr)**2 for r in rets)/len(rets)
    sd = math.sqrt(var)
    sharpe = (mr/sd*math.sqrt(252)) if sd > 0 else 0
    closed = d.get('closed', [])
    buys = d.get('buys', [])
    wins = [c for c in closed if isinstance(c, dict) and c.get('pnl_pct', 0) > 0]
    wr = len(wins)/len(closed)*100 if closed else 0
    cash_ret = d.get('cash_mgmt_ret', 0)
    total_ret = eq[-1] - eq[0]
    trade_ret = total_ret - cash_ret
    # 平仓 pnl
    pnls = [c['pnl_pct']*100 for c in closed if isinstance(c, dict)]
    exp = sum(pnls)/len(pnls) if pnls else 0
    win_pnls = [p for p in pnls if p > 0]
    loss_pnls = [p for p in pnls if p <= 0]
    avg_w = sum(win_pnls)/len(win_pnls) if win_pnls else 0
    avg_l = sum(loss_pnls)/len(loss_pnls) if loss_pnls else 0
    return {
        'final': eq[-1], 'ann': ann*100, 'mdd': mdd*100, 'sharpe': sharpe,
        'buys': len(buys), 'closed': len(closed), 'wr': wr,
        'cash_ret': cash_ret, 'total_ret': total_ret, 'trade_ret': trade_ret,
        'exp': exp, 'avg_w': avg_w, 'avg_l': avg_l,
    }

OUT = os.path.join(os.path.dirname(__file__), "..", "output")

print(f"{'配置':6s} {'终值':>12s} {'年化%':>7s} {'回撤%':>7s} {'夏普':>6s} {'建仓':>4s} {'平仓':>4s} {'胜率%':>6s} {'期望%':>7s} {'现金收益':>10s} {'交易净贡献':>10s}")
print("-" * 100)
for f in ['D6r', 'E1r', 'E2r', 'E3r']:
    mi = metrics(os.path.join(OUT, f'results_{f}_in.json'))
    if mi:
        print(f"{f:6s} {mi['final']:12,.0f} {mi['ann']:7.2f} {mi['mdd']:7.2f} {mi['sharpe']:6.2f} "
              f"{mi['buys']:4d} {mi['closed']:4d} {mi['wr']:6.1f} {mi['exp']:+7.2f} "
              f"{mi['cash_ret']:10,.0f} {mi['trade_ret']:10,.0f}")

print()
print("--- 样本外 ---")
for f in ['D6r', 'E1r', 'E2r', 'E3r']:
    mo = metrics(os.path.join(OUT, f'results_{f}_oos.json'))
    if mo:
        print(f"{f:6s} {mo['final']:12,.0f} {mo['ann']:7.2f} {mo['mdd']:7.2f} {mo['sharpe']:6.2f} "
              f"{mo['buys']:4d} {mo['closed']:4d} {mo['wr']:6.1f} {mo['exp']:+7.2f}")

print()
print("--- 决策门槛判定 ---")
mi = metrics(os.path.join(OUT, 'results_E1r_in.json'))
if mi:
    print(f"E1r 年化: {mi['ann']:.2f}%")
    if mi['ann'] >= 6:
        print("判定: >=6% → 达标，进入标的面扩展终局验证")
    elif mi['ann'] >= 3:
        print("判定: 3-6% → 有改善但不足，标的面扩展（重点加个股）→ 重跑")
    else:
        print("判定: <3% → 过滤器方案证伪，停止参数微调，进入战略复盘")
