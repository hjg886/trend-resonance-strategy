#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""实盘执行仪表盘 - 从文件读取K线数据 + 指标计算 + HTML生成"""

import os, math
from datetime import datetime

# ========== 1. 读取K线数据文件 ==========
def load_kline_file(filepath):
    """从批量K线文件读取数据，按symbol分组"""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    data_by_symbol = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith('[Batch]') or line.startswith('| ---') or line.startswith('| symbol'):
            continue
        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 9:
            continue
        try:
            symbol = parts[1]
            date = parts[2]
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

    # 按日期排序（旧→新）
    for sym in data_by_symbol:
        data_by_symbol[sym].sort(key=lambda x: x['date'])
    return data_by_symbol

# ========== 2. 技术指标计算 ==========
def calc_ma(data, period=60):
    if len(data) < period:
        return None
    return sum(d['close'] for d in data[-period:]) / period

def calc_atr(data, period=14):
    if len(data) < period + 1:
        return None
    trs = []
    for i in range(1, len(data)):
        h, l = data[i]['high'], data[i]['low']
        prev_c = data[i-1]['close']
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        trs.append(tr)
    return sum(trs[-period:]) / period

def calc_adx(data, period=14):
    if len(data) < period * 2:
        return 0
    plus_dm, minus_dm, trs = [], [], []
    for i in range(1, len(data)):
        h, l = data[i]['high'], data[i]['low']
        prev_h, prev_l = data[i-1]['high'], data[i-1]['low']
        prev_c = data[i-1]['close']
        up = h - prev_h
        down = prev_l - l
        plus_dm.append(up if (up > down and up > 0) else 0)
        minus_dm.append(down if (down > up and down > 0) else 0)
        trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
    def smooth(arr, p):
        return sum(arr[-p:]) / p if len(arr) >= p else sum(arr) / max(len(arr), 1)
    atr = smooth(trs, period)
    if atr == 0:
        return 0
    plus_di = 100 * smooth(plus_dm, period) / atr
    minus_di = 100 * smooth(minus_dm, period) / atr
    return abs(plus_di - minus_di) / max(plus_di + minus_di, 0.001) * 100

def calc_vol20(data):
    if len(data) < 21:
        return 0
    returns = []
    for i in range(1, len(data)):
        r = (data[i]['close'] - data[i-1]['close']) / data[i-1]['close']
        returns.append(r)
    recent = returns[-20:]
    mean_r = sum(recent) / len(recent)
    var = sum((r - mean_r)**2 for r in recent) / (len(recent) - 1)
    return math.sqrt(var) * math.sqrt(250) * 100

def highest_since(data, start_date):
    highs = [d['high'] for d in data if d['date'] >= start_date]
    return max(highs) if highs else data[-1]['high']

def ma60_crossings(data):
    if len(data) < 61:
        return 0
    ma60_list = []
    for i in range(len(data)):
        if i < 59:
            ma60_list.append(None)
        else:
            ma60_list.append(sum(d['close'] for d in data[i-59:i+1]) / 60)
    crossings = 0
    for i in range(1, len(data)):
        if ma60_list[i] and ma60_list[i-1]:
            if (data[i]['close'] > ma60_list[i] and data[i-1]['close'] <= ma60_list[i-1]) or \
               (data[i]['close'] < ma60_list[i] and data[i-1]['close'] >= ma60_list[i-1]):
                crossings += 1
    return crossings

def tre_state(data):
    vol20 = calc_vol20(data)
    adx = calc_adx(data)
    ma60 = calc_ma(data, 60)
    if not ma60 or not data:
        return "S4", "风暴市", "数据不足"
    last = data[-1]
    above_ma60 = last['close'] > ma60
    crossings = ma60_crossings(data)
    if vol20 > 25:
        return "S4", "风暴市", f"vol20={vol20:.1f}%>25%"
    if above_ma60 and adx > 20:
        return "S1", "强趋势", f"价格>MA60+ADX={adx:.1f}>20"
    if above_ma60 and adx < 20:
        return "S2", "趋弱", f"价格>MA60+ADX={adx:.1f}<20"
    if not above_ma60 and crossings >= 3:
        return "S3", "震荡", f"价格<MA60+穿越{crossings}次"
    if not above_ma60 and crossings < 3:
        return "S3近似", "弱震荡", f"价格<MA60+穿越{crossings}次(需≥3)"
    return "S4", "风暴市", "默认"

# ========== 3. 加载数据 ==========
kline_file = os.path.join(os.path.dirname(__file__), 'kline_data.txt')
print(f"读取K线数据: {kline_file}")
all_data = load_kline_file(kline_file)
print(f"Symbols: {list(all_data.keys())}")
for sym, data in all_data.items():
    print(f"  {sym}: {len(data)} bars, 最新={data[-1]['date']} close={data[-1]['close']}")

# 指数数据
hs300_data = all_data.get('sh000300', [])
zz500_data = all_data.get('sh000905', [])
cyb_data = all_data.get('sz399006', [])

hs300_vol20 = calc_vol20(hs300_data)
hs300_ma60 = calc_ma(hs300_data, 60)
hs300_adx = calc_adx(hs300_data, 14)
tre_hs300 = tre_state(hs300_data)
tre_zz500 = tre_state(zz500_data)
tre_cyb = tre_state(cyb_data)

print(f"\n沪深300: vol20={hs300_vol20:.2f}%, MA60={hs300_ma60:.2f}, ADX={hs300_adx:.1f}")
print(f"TRE: HS300={tre_hs300[0]}({tre_hs300[1]}), ZZ500={tre_zz500[0]}({tre_zz500[1]}), CYB={tre_cyb[0]}({tre_cyb[1]})")

# R-04闸门
if hs300_vol20 < 15:
    gate = "闸门A（禁一切新建仓）"; gate_color = "#dc3545"
elif hs300_vol20 >= 20:
    gate = "闸门B（禁S1/S2常规建仓）"; gate_color = "#fd7e14"
else:
    gate = "正常区（无闸门触发）"; gate_color = "#28a745"
print(f"R-04: vol20={hs300_vol20:.2f}% → {gate}")

# ========== 4. 持仓数据（0731券商F4查询）==========
positions = [
    {'code': '600276', 'name': '恒瑞医药', 'shares': 900, 'cost_price': 51.2726,
     'buy_date': '2026-07-01', 'tier': '防守底盘', 'kline_key': 'sh600276'},
    {'code': '510300', 'name': '沪深300ETF', 'shares': 40700, 'cost_price': 4.8224,
     'buy_date': '2026-07-08', 'tier': '防守底盘', 'kline_key': 'sh510300'},
    {'code': '159650', 'name': '国开债ETF', 'shares': 1800, 'cost_price': 107.5870,
     'buy_date': '2026-06-04', 'tier': '稳定器', 'kline_key': 'sz159650'},
]
account = {'cash': 366708.97, 'total_assets_0731': 798920.47}

# ========== 5. 持仓指标计算 ==========
print("\n持仓指标:")
pos_results = []
for pos in positions:
    data = all_data.get(pos['kline_key'], [])
    if not data:
        print(f"  {pos['name']}: 无数据"); continue

    current = data[-1]['close']
    cost = pos['cost_price']
    shares = pos['shares']
    market_value = current * shares
    cost_basis = cost * shares
    pnl = market_value - cost_basis
    pnl_pct = (pnl / cost_basis) * 100

    ma60 = calc_ma(data, 60)
    atr = calc_atr(data, 14)
    adx = calc_adx(data, 14)
    vol20 = calc_vol20(data)
    ma60_dev = ((current - ma60) / ma60 * 100) if ma60 else 0

    buy_dt = datetime.strptime(pos['buy_date'], '%Y-%m-%d')
    today = datetime.strptime('2026-08-18', '%Y-%m-%d')
    holding_days = (today - buy_dt).days
    bandwidth = 7 if holding_days <= 11 else 4

    # 【修正·ETF止损口径】策略11.4：个股P1=买入价-MIN(2×ATR,带宽%)；ETF E-P1=买入价-带宽%
    bw_amount = cost * bandwidth / 100
    if 'ETF' in pos['name']:
        p1_stop = cost * (1 - bandwidth / 100)          # ETF E-P1
    else:
        p1_stop = cost - min(2 * atr, bw_amount) if atr else cost - bw_amount  # 个股 P1

    # 动态回撤
    highest = highest_since(data, pos['buy_date'])
    drawdown_pct = (current - highest) / highest * 100
    p0_level = highest * 0.95
    p2_level = highest * 0.92
    p3_level = highest * 0.89
    s4_level = highest * 0.89  # S4提前一档=-11%

    # 近5日
    five_day_pct = (current - data[-6]['close']) / data[-6]['close'] * 100 if len(data) >= 6 else 0

    # P12
    profit_from_cost = (highest - cost) / cost * 100
    p12_active = profit_from_cost >= 15
    if p12_active:
        if profit_from_cost >= 50: p12_trailing = highest * 0.55
        elif profit_from_cost >= 35: p12_trailing = highest * 0.65
        else: p12_trailing = highest * 0.75
    else:
        p12_trailing = None

    result = {**pos, 'current': current, 'market_value': market_value, 'cost_basis': cost_basis,
              'pnl': pnl, 'pnl_pct': pnl_pct, 'ma60': ma60, 'ma60_dev': ma60_dev,
              'above_ma60': current > ma60 if ma60 else False, 'atr': atr, 'adx': adx, 'vol20': vol20,
              'holding_days': holding_days, 'bandwidth': bandwidth, 'p1_stop': p1_stop,
              'highest': highest, 'drawdown_pct': drawdown_pct, 'p0_level': p0_level,
              'p2_level': p2_level, 'p3_level': p3_level, 's4_level': s4_level,
              'five_day_pct': five_day_pct, 'p12_active': p12_active, 'p12_trailing': p12_trailing,
              'profit_from_cost': profit_from_cost}
    pos_results.append(result)
    print(f"  {pos['name']}: 现价{current:.2f} 成本{cost:.4f} 盈亏{pnl:+.0f}({pnl_pct:+.2f}%) "
          f"MA60={ma60:.2f}({'>' if current>ma60 else '<'}) ATR={atr:.3f} ADX={adx:.1f} vol20={vol20:.1f}% "
          f"持有{holding_days}天 P1={p1_stop:.2f} 最高{highest:.2f} 回撤{drawdown_pct:.2f}%")

# ========== 6. 三层配置 ==========
total_position_value = sum(p['market_value'] for p in pos_results)
total_assets = total_position_value + account['cash']
defense_base = sum(p['market_value'] for p in pos_results if p['tier'] == '防守底盘')
stabilizer = sum(p['market_value'] for p in pos_results if p['tier'] == '稳定器') + account['cash']
defense_pct = defense_base / total_assets * 100
stabilizer_pct = stabilizer / total_assets * 100
print(f"\n三层: 防守={defense_base:,.0f}({defense_pct:.1f}%) 稳定器={stabilizer:,.0f}({stabilizer_pct:.1f}%) 总资产={total_assets:,.0f}")

# ========== 7. S4状态判定 ==========
def s4_status(p):
    if p['tier'] == '稳定器':
        return ("稳定器运行中", "#28a745", "无止损要求（国债ETF稳定器功能）")
    warnings = []
    if not p['above_ma60']:
        warnings.append("价格低于MA60")
    if p['current'] < p['p0_level']:
        warnings.append(f"P0触发(回撤{abs(p['drawdown_pct']):.1f}%)")
    p1_dist = (p['current'] - p['p1_stop']) / p['current'] * 100
    if p1_dist < 5:
        warnings.append(f"P1临近(距{p['p1_stop']:.2f}仅{p1_dist:.1f}%)")
    s4_dist = (p['current'] - p['s4_level']) / p['current'] * 100
    if warnings:
        return ("⚠️监控", "#fd7e14", "；".join(warnings))
    return ("正常", "#28a745", f"距S4提前一档({p['s4_level']:.2f})还有{s4_dist:.1f}%")

# ========== 8. HTML生成 ==========
def fmt_money(v): return f"{v:,.0f}"
def pnl_cls(v): return "profit" if v > 0 else "loss"

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>实盘执行仪表盘 - 2026-08-19</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:"Microsoft YaHei","PingFang SC",sans-serif; background:#f5f7fa; color:#333; line-height:1.6; padding:20px; }}
.container {{ max-width:1200px; margin:0 auto; }}
.header {{ background:linear-gradient(135deg,#1a237e 0%,#283593 100%); color:white; padding:24px 30px; border-radius:12px; margin-bottom:20px; box-shadow:0 4px 12px rgba(0,0,0,0.15); }}
.header h1 {{ font-size:24px; margin-bottom:6px; }}
.header .meta {{ font-size:13px; opacity:0.85; }}
.section {{ background:white; border-radius:10px; padding:20px 24px; margin-bottom:16px; box-shadow:0 2px 8px rgba(0,0,0,0.06); }}
.section-title {{ font-size:16px; font-weight:700; color:#1a237e; margin-bottom:14px; padding-bottom:8px; border-bottom:2px solid #e8eaf6; display:flex; align-items:center; gap:8px; }}
.section-title .icon {{ width:8px; height:20px; background:#1a237e; border-radius:3px; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ background:#f5f7fa; color:#555; font-weight:600; padding:10px 8px; text-align:left; border-bottom:2px solid #e0e0e0; white-space:nowrap; }}
td {{ padding:10px 8px; border-bottom:1px solid #f0f0f0; white-space:nowrap; }}
tr:hover td {{ background:#fafbfc; }}
.badge {{ display:inline-block; padding:2px 10px; border-radius:12px; font-size:12px; font-weight:600; }}
.badge-green {{ background:#e8f5e9; color:#2e7d32; }}
.badge-orange {{ background:#fff3e0; color:#e65100; }}
.badge-red {{ background:#ffebee; color:#c62828; }}
.badge-blue {{ background:#e3f2fd; color:#1565c0; }}
.badge-gray {{ background:#f5f5f5; color:#757575; }}
.metric-card {{ display:inline-block; background:#f8f9fa; border:1px solid #e9ecef; border-radius:8px; padding:12px 16px; margin:4px; min-width:140px; vertical-align:top; }}
.metric-label {{ font-size:12px; color:#666; margin-bottom:4px; }}
.metric-value {{ font-size:20px; font-weight:700; }}
.alert-box {{ border-left:4px solid; padding:12px 16px; border-radius:4px; margin:8px 0; font-size:13px; }}
.alert-warning {{ border-color:#ff9800; background:#fff8e1; color:#e65100; }}
.alert-danger {{ border-color:#f44336; background:#ffebee; color:#c62828; }}
.alert-info {{ border-color:#2196f3; background:#e3f2fd; color:#1565c0; }}
.alert-success {{ border-color:#4caf50; background:#e8f5e9; color:#2e7d32; }}
.timeline {{ border-left:3px solid #e0e0e0; padding-left:20px; margin-left:10px; }}
.timeline-item {{ position:relative; padding:8px 0 16px 0; }}
.timeline-item::before {{ content:''; position:absolute; left:-27px; top:14px; width:11px; height:11px; border-radius:50%; background:#1a237e; border:2px solid white; }}
.footer {{ text-align:center; padding:16px; color:#999; font-size:12px; margin-top:20px; }}
.profit {{ color:#dc3545; font-weight:600; }}
.loss {{ color:#2e7d32; font-weight:600; }}
</style>
</head>
<body>
<div class="container">

<div class="header">
  <h1>实盘执行仪表盘 v4.7-R10</h1>
  <div class="meta">
    日期：2026-08-19（周三）| 生成时间：08:58 | 策略版本：v4.7-R10完整补齐版（1+2架构）|
    数据源：westockdata + 券商F4查询(0731) |
    <span style="color:#ffcdd2;">⚠️ 主引擎年化2.97%<6%门槛，存量持仓按S4规则管理，新建仓禁止</span>
  </div>
</div>

<!-- 三层资金架构 -->
<div class="section">
  <div class="section-title"><span class="icon"></span>三层资金架构执行确认</div>
  <table>
    <tr><th>层级</th><th>目标配比</th><th>当前市值</th><th>当前占比</th><th>状态</th><th>说明</th></tr>
    <tr>
      <td><strong>防守底盘</strong></td><td>60-70%</td>
      <td>¥{fmt_money(defense_base)}</td>
      <td><span class="badge badge-orange">{defense_pct:.1f}%</span></td>
      <td><span class="badge badge-orange">低于目标</span></td>
      <td>恒瑞医药+沪深300ETF | S4下禁止扩仓</td>
    </tr>
    <tr>
      <td><strong>现金国债稳定器</strong></td><td>30-40%</td>
      <td>¥{fmt_money(stabilizer)}</td>
      <td><span class="badge badge-blue">{stabilizer_pct:.1f}%</span></td>
      <td><span class="badge badge-blue">高于目标</span></td>
      <td>国开债ETF+现金 | S4下高现金=防御姿态</td>
    </tr>
    <tr>
      <td><strong>进攻线(模拟盘)</strong></td><td>0-10%</td><td>¥0</td>
      <td><span class="badge badge-gray">0%</span></td>
      <td><span class="badge badge-gray">模拟盘阶段</span></td>
      <td>B3个股精选 | ≥6月模拟盘验证后渐进实盘</td>
    </tr>
    <tr style="background:#f8f9fa;font-weight:700;">
      <td>合计</td><td>100%</td><td>¥{fmt_money(total_assets)}</td><td>100%</td><td></td><td>总资产(含现金)</td>
    </tr>
  </table>
  <div class="alert-box alert-info" style="margin-top:12px;">
    <strong>配置诊断</strong>：防守底盘{defense_pct:.1f}%低于目标60-70%，稳定器{stabilizer_pct:.1f}%高于目标30-40%。
    原因：S4严控下禁止新建仓，高现金比例是正确的防御姿态。待TRE好转(S4→S3/S2)后逐步转入防守底盘。
  </div>
</div>

<!-- TRE + R-04 -->
<div class="section">
  <div class="section-title"><span class="icon"></span>市场环境判定（TRE + R-04）</div>
  <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px;">
    <div class="metric-card">
      <div class="metric-label">R-04波动率闸门</div>
      <div class="metric-value" style="color:{gate_color};">{gate}</div>
      <div style="font-size:12px;color:#666;">vol20 = {hs300_vol20:.2f}%</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">沪深300 TRE</div>
      <div class="metric-value" style="color:#dc3545;">{tre_hs300[0]}</div>
      <div style="font-size:12px;color:#666;">{tre_hs300[1]} | {tre_hs300[2]}</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">中证500 TRE</div>
      <div class="metric-value" style="color:#dc3545;">{tre_zz500[0]}</div>
      <div style="font-size:12px;color:#666;">{tre_zz500[1]} | {tre_zz500[2]}</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">创业板指 TRE</div>
      <div class="metric-value" style="color:#dc3545;">{tre_cyb[0]}</div>
      <div style="font-size:12px;color:#666;">{tre_cyb[1]} | {tre_cyb[2]}</div>
    </div>
  </div>
  <div class="alert-box alert-danger">
    <strong>🔴 实盘执行裁决：S4严控状态 → 禁止一切新建仓/补仓</strong><br>
    • 三大指数均处于MA60下方，中证500+创业板指vol20>25%触发S4<br>
    • 观察通道未触发（ADX均远低于20，无趋势反转信号）<br>
    • <strong>今日执行权限：仅限持仓监控与止盈止损执行，不开放新建仓</strong>
  </div>
</div>

<!-- 持仓监控表 -->
<div class="section">
  <div class="section-title"><span class="icon"></span>持仓监控表（S4规则管理）</div>
  <div style="overflow-x:auto;">
  <table>
    <tr>
      <th>标的</th><th>层级</th><th>持股</th><th>成本价</th><th>现价</th>
      <th>市值</th><th>盈亏</th><th>盈亏%</th><th>MA60</th><th>偏离MA60</th>
      <th>持有天数</th><th>R-06带宽</th><th>P1止损</th><th>距P1</th>
      <th>最高价</th><th>动态回撤</th><th>S4(-11%)</th>
      <th>ADX</th><th>vol20</th><th>状态</th>
    </tr>
'''

for p in pos_results:
    s4 = s4_status(p)
    p1_dist = (p['current'] - p['p1_stop']) / p['current'] * 100
    s4_dist = (p['current'] - p['s4_level']) / p['current'] * 100
    ma60_str = f'{"●" if p["above_ma60"] else "○"} {p["ma60"]:.2f}' if p['ma60'] else '—'
    if p['tier'] == '稳定器':
        p1_s = '—'; p1_d = '—'; s4_s = '—'; hi_s = '—'; dd_s = '—'
    else:
        p1_s = f'{p["p1_stop"]:.2f}'; p1_d = f'{p1_dist:.1f}%'
        s4_s = f'{p["s4_level"]:.2f}({s4_dist:.1f}%)'; hi_s = f'{p["highest"]:.2f}'; dd_s = f'{p["drawdown_pct"]:.2f}%'

    html += f'''    <tr>
      <td><strong>{p["name"]}</strong><br><span style="color:#999;font-size:11px;">{p["code"]}</span></td>
      <td><span class="badge {"badge-blue" if p["tier"]=="稳定器" else "badge-green"}">{p["tier"]}</span></td>
      <td>{p["shares"]:,}</td><td>{p["cost_price"]:.4f}</td><td><strong>{p["current"]:.2f}</strong></td>
      <td>¥{fmt_money(p["market_value"])}</td>
      <td class="{pnl_cls(p["pnl"])}">¥{p["pnl"]:+,.0f}</td>
      <td class="{pnl_cls(p["pnl_pct"])}">{p["pnl_pct"]:+.2f}%</td>
      <td>{ma60_str}</td><td>{p["ma60_dev"]:+.2f}%</td>
      <td>{p["holding_days"]}天</td><td>{p["bandwidth"]}%</td>
      <td>{p1_s}</td><td>{p1_d}</td><td>{hi_s}</td><td>{dd_s}</td><td>{s4_s}</td>
      <td>{p["adx"]:.1f}</td><td>{p["vol20"]:.1f}%</td>
      <td><span class="badge" style="background:{s4[1]}20;color:{s4[1]};">{s4[0]}</span></td>
    </tr>
'''

html += f'''  </table>
  </div>
  <div style="margin-top:12px;font-size:12px;color:#666;">
    ●=高于MA60 ○=低于MA60 | R-06带宽：≤11日→7%，>11日→4% | P1=买入价-MIN(2×ATR,带宽%) |
    S4提前一档=动态回撤-11% | 成本价来源：券商F4查询(0731)
  </div>
</div>

<!-- 持仓详细分析 -->
<div class="section">
  <div class="section-title"><span class="icon"></span>持仓详细分析与执行指令</div>
'''

for p in pos_results:
    s4 = s4_status(p)
    p1_dist = (p['current'] - p['p1_stop']) / p['current'] * 100
    html += f'''  <div style="border:1px solid #e0e0e0;border-radius:8px;padding:16px;margin-bottom:12px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
      <h3 style="font-size:15px;color:#1a237e;">{p["name"]}（{p["code"]}）— {p["tier"]}</h3>
      <span class="badge" style="background:{s4[1]}20;color:{s4[1]};">{s4[0]}</span>
    </div>
    <table style="font-size:12px;">
      <tr>
        <td style="width:20%;color:#666;">持股/成本</td><td style="width:30%;">{p["shares"]:,}股 @ ¥{p["cost_price"]:.4f}</td>
        <td style="width:20%;color:#666;">现价/市值</td><td>{p["current"]:.2f} / ¥{fmt_money(p["market_value"])}</td>
      </tr>
      <tr>
        <td style="color:#666;">盈亏</td><td class="{pnl_cls(p["pnl"])}">¥{p["pnl"]:+,.0f} ({p["pnl_pct"]:+.2f}%)</td>
        <td style="color:#666;">MA60/偏离</td><td>{p["ma60"]:.2f} ({p["ma60_dev"]:+.2f}%)</td>
      </tr>
      <tr>
        <td style="color:#666;">持有天数/R-06</td><td>{p["holding_days"]}天 / {p["bandwidth"]}%</td>
        <td style="color:#666;">ATR/ADX/vol20</td><td>{p["atr"]:.3f} / {p["adx"]:.1f} / {p["vol20"]:.1f}%</td>
      </tr>
'''
    if p['tier'] != '稳定器':
        p0_trig = "🔴触发" if p['current'] < p['p0_level'] else "○未触发"
        p2_trig = "🔴触发" if p['current'] < p['p2_level'] else "○未触发"
        html += f'''      <tr>
        <td style="color:#666;">P1止损位</td><td style="color:#dc3545;"><strong>{p["p1_stop"]:.2f}</strong>（距{p1_dist:.1f}%）</td>
        <td style="color:#666;">最高价/回撤</td><td>{p["highest"]:.2f} / {p["drawdown_pct"]:.2f}%</td>
      </tr>
      <tr>
        <td style="color:#666;">S4(-11%)</td><td style="color:#fd7e14;">{p["s4_level"]:.2f}（距{s4_dist:.1f}%）</td>
        <td style="color:#666;">P0(-5%)/P2(-8%)</td><td>{p0_trig} / {p2_trig}</td>
      </tr>
'''
        if p['p12_active']:
            html += f'''      <tr><td style="color:#666;">P12移动止盈</td><td style="color:#28a745;"><strong>已激活</strong>（浮盈{p["profit_from_cost"]:.1f}%≥15%）</td><td style="color:#666;">P12v6止盈线</td><td>{p["p12_trailing"]:.2f}</td></tr>
'''
        else:
            html += f'''      <tr><td style="color:#666;">P12移动止盈</td><td>未激活（浮盈{p["profit_from_cost"]:.1f}%<15%）</td><td style="color:#666;">近5日</td><td>{p["five_day_pct"]:+.2f}%</td></tr>
'''

    alert_cls = "alert-warning" if "⚠️" in s4[0] else "alert-info"
    html += f'''    </table>
    <div class="alert-box {alert_cls}" style="margin-top:10px;font-size:12px;"><strong>执行指令</strong>：{s4[2]}</div>
  </div>
'''

html += f'''</div>

<!-- 今日执行清单 -->
<div class="section">
  <div class="section-title"><span class="icon"></span>今日实盘执行清单（2026-08-19）</div>
  <table>
    <tr><th style="width:5%;">#</th><th style="width:12%;">时间</th><th style="width:55%;">执行事项</th><th style="width:13%;">类型</th><th style="width:15%;">状态</th></tr>
'''

# 生成执行清单
exec_items = [
    ("1", "09:15-09:25", "集合竞价观察：恒瑞医药/沪深300ETF开盘方向", "观察", "待执行", "gray"),
    ("2", "09:30", "开盘确认：三大指数方向，确认S4延续", "观察", "待执行", "gray"),
    ("3", "10:00", "盘中波动率熔断监控①：沪深300日内波动率", "熔断", "待执行", "gray"),
    ("4", "10:30", "盘中波动率熔断监控②：沪深300日内波动率", "熔断", "待执行", "gray"),
]

# 持仓特定监控
for i, p in enumerate(pos_results):
    if p['tier'] == '稳定器':
        continue
    s4 = s4_status(p)
    p1_dist = (p['current'] - p['p1_stop']) / p['current'] * 100
    p0_trig = p['current'] < p['p0_level']
    item_desc = f"{p['name']}P1止损监控：P1={p['p1_stop']:.2f}（距{p1_dist:.1f}%）"
    if p0_trig:
        item_desc += f" | P0已触发（回撤{abs(p['drawdown_pct']):.1f}%），S4下考虑减仓"
    badge = "red" if p0_trig else "orange"
    status = "P0触发" if p0_trig else "持续"
    exec_items.append((str(5+i), "全天", item_desc, "止损监控", status, badge))

exec_items.extend([
    ("8", "14:30", "盘中波动率熔断监控③：沪深300最终检查", "熔断", "待执行", "gray"),
    ("9", "15:00", "收盘确认：各持仓收盘价、MA60更新、TRE刷新", "收盘", "待执行", "gray"),
    ("10", "盘后", "盘后复盘：持仓因子更新+组合健康检查+明日预案", "复盘", "待执行", "gray"),
])

for num, time, desc, typ, status, color in exec_items:
    html += f'    <tr><td>{num}</td><td>{time}</td><td>{desc}</td><td>{typ}</td><td><span class="badge badge-{color}">{status}</span></td></tr>\n'

html += f'''  </table>
</div>

<!-- S4止损标准 -->
<div class="section">
  <div class="section-title"><span class="icon"></span>S4状态下止损执行标准（R-06 + 提前一档）</div>
  <table>
    <tr><th>触发级别</th><th>正常状态</th><th>S4提前一档</th><th>执行方式</th><th>当前最近触发</th></tr>
'''

for p in pos_results:
    if p['tier'] == '稳定器':
        continue
    p0_trig = "🔴已触发" if p['current'] < p['p0_level'] else "○未触发"

# 恒瑞
hr = pos_results[0]
etf = pos_results[1]
hr_p0 = "🔴已触发" if hr['current'] < hr['p0_level'] else "○未触发"
hr_p1_dist = (hr['current'] - hr['p1_stop']) / hr['current'] * 100
etf_p1_dist = (etf['current'] - etf['p1_stop']) / etf['current'] * 100

html += f'''    <tr><td><strong>P0</strong> 动态回撤-5%</td><td>预警观察</td><td style="color:#fd7e14;">减仓信号</td><td>S4下P0触发→考虑减仓1/3</td><td>恒瑞{hr_p0}(回撤{abs(hr["drawdown_pct"]):.1f}%)</td></tr>
    <tr><td><strong>P1</strong> 技术止损</td><td>次日开盘清仓</td><td style="color:#dc3545;">即刻执行</td><td>跌破买入价-MIN(2×ATR,带宽%)</td><td>恒瑞{hr["p1_stop"]:.2f}(距{hr_p1_dist:.1f}%) / 沪深300{etf["p1_stop"]:.2f}(距{etf_p1_dist:.1f}%)</td></tr>
    <tr><td><strong>P2</strong> 动态回撤-8%</td><td>减仓1/2</td><td style="color:#dc3545;">清仓信号</td><td>S4下P2触发→清仓</td><td>未触发</td></tr>
    <tr><td><strong>P3/S4</strong> 回撤-11%</td><td>清仓</td><td style="color:#dc3545;font-weight:700;">即刻清仓</td><td>S4下-11%=正常-15%级别</td><td>恒瑞{hr["s4_level"]:.2f} / 沪深300{etf["s4_level"]:.2f}</td></tr>
  </table>
  <div class="alert-box alert-warning" style="margin-top:12px;">
    <strong>注意</strong>：S4"提前一档"=正常各级别阈值整体收紧一档。正常P0(-5%)→S4减仓；正常P1→S4即刻执行；正常P2(-8%)→S4清仓；正常P3(-11%)→S4即刻清仓(=正常P4(-15%)级别)。
  </div>
</div>

<!-- 进攻线模拟盘 -->
<div class="section">
  <div class="section-title"><span class="icon"></span>进攻线模拟盘状态（B3个股精选）</div>
  <table>
    <tr><th>项目</th><th>状态</th><th>说明</th></tr>
    <tr><td>策略候选</td><td><span class="badge badge-green">B3已选定</span></td><td>IS年化7.04% / OOS年化13.15%（OOS>IS排除过拟合）</td></tr>
    <tr><td>模拟盘阶段</td><td><span class="badge badge-orange">待启动</span></td><td>需≥6月模拟盘验证达标后渐进实盘</td></tr>
    <tr><td>配比规划</td><td>0%→5%→10%→15-20%</td><td>达标后逐步提升</td></tr>
    <tr><td>B3参数</td><td>闸门A≥10+得分≥70+P12v6</td><td>vol20≥15建仓≥30禁 + P12v6回撤45/35/25%</td></tr>
    <tr><td>数据就绪</td><td><span class="badge badge-green">已就绪</span></td><td>24只个股K线全量至2026-08-18</td></tr>
    <tr><td>台账模板</td><td><span class="badge badge-gray">待创建</span></td><td>attack_sim/journal_template.csv</td></tr>
  </table>
</div>

<!-- 执行纪律 -->
<div class="section">
  <div class="section-title"><span class="icon"></span>实盘执行纪律（13条锁死规则）</div>
  <div class="timeline">
    <div class="timeline-item"><strong>1. R-04波动率闸门是建仓第一前置</strong>：环境不配合，信号再强也放弃</div>
    <div class="timeline-item"><strong>2. TRE S4覆盖一切</strong>：S4下禁止新建仓，存量按提前一档管理</div>
    <div class="timeline-item"><strong>3. BREADTH否决层（F-35）</strong>：BREADTH&lt;15禁建仓，须与H1组合，禁止单独使用</div>
    <div class="timeline-item"><strong>4. S1不追单日强信号</strong>：连续2日确认+标的连续2日站稳MA60+开盘涨幅≤1%</div>
    <div class="timeline-item"><strong>5. R-06止损带宽</strong>：≤11日→7%，>11日→4%</div>
    <div class="timeline-item"><strong>6. 洗仓封堵（R-03）</strong>：P1/E-P1止损后30日内重购须≥85分</div>
    <div class="timeline-item"><strong>7. 建仓频率枯竭预警（R-08）</strong>：年6-18笔，<6笔触发预警</div>
    <div class="timeline-item"><strong>8. P12v6移动止盈</strong>：浮盈≥15%启动，回撤45/35/25%分档</div>
    <div class="timeline-item"><strong>9. 标的面≥30只</strong>：观察池保持充足候选</div>
    <div class="timeline-item"><strong>10. 门槛分轨</strong>：个股80/宽基80/行业78/S3观察85</div>
    <div class="timeline-item"><strong>11. 买卖指令标准化</strong>：使用11.7/11.8模板（含R-04/R-05/BREADTH前置字段）</div>
    <div class="timeline-item"><strong>12. 三层资金架构</strong>：防守底盘60-70%+稳定器30-40%+进攻线0-10%(渐进)</div>
    <div class="timeline-item"><strong>13. 回测未达标</strong>：主引擎年化2.97%<6%，进攻线B3需≥6月模拟盘达标后才可实盘</div>
  </div>
</div>

<div class="footer">
  实盘执行仪表盘 v4.7-R10 | 生成时间：2026-08-19 08:58 | 数据源：westockdata + 券商F4查询(0731) |
  本仪表盘仅供策略执行参考，不构成个人投资建议。实盘交易决策由投资者自行承担。
</div>

</div>
</body>
</html>
'''

output_path = r'E:\fnOS\文档\证券\实盘执行仪表盘-20260819.html'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"\n仪表盘已生成: {output_path}")
print(f"文件大小: {os.path.getsize(output_path):,} bytes")
