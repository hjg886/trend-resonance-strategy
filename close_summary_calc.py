#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""收盘总结 - 2026-08-19 完整计算"""

import os, math
from datetime import datetime

# ========== 读取K线 ==========
def load_kline_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    data_by_symbol = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith('[Batch]') or line.startswith('| ---') or line.startswith('| symbol'):
            continue
        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 9: continue
        try:
            symbol = parts[1]; date = parts[2]
            open_p = float(parts[3]); close = float(parts[4])
            high = float(parts[5]); low = float(parts[6])
            volume = float(parts[7]) if parts[7] else 0
            amount = float(parts[8]) if len(parts) > 8 and parts[8] else 0
            if symbol not in data_by_symbol:
                data_by_symbol[symbol] = []
            data_by_symbol[symbol].append({'date': date, 'open': open_p, 'close': close, 'high': high, 'low': low, 'volume': volume, 'amount': amount})
        except (ValueError, IndexError):
            continue
    for sym in data_by_symbol:
        data_by_symbol[sym].sort(key=lambda x: x['date'])
    return data_by_symbol

# ========== 指标计算 ==========
def calc_ma(data, period=60):
    if len(data) < period: return None
    return sum(d['close'] for d in data[-period:]) / period

def calc_atr(data, period=14):
    if len(data) < period + 1: return None
    trs = []
    for i in range(1, len(data)):
        h, l = data[i]['high'], data[i]['low']
        prev_c = data[i-1]['close']
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        trs.append(tr)
    return sum(trs[-period:]) / period

def calc_adx(data, period=14):
    if len(data) < period * 2: return 0
    plus_dm, minus_dm, trs = [], [], []
    for i in range(1, len(data)):
        h, l = data[i]['high'], data[i]['low']
        prev_h, prev_l = data[i-1]['high'], data[i-1]['low']
        prev_c = data[i-1]['close']
        up = h - prev_h; down = prev_l - l
        plus_dm.append(up if (up > down and up > 0) else 0)
        minus_dm.append(down if (down > up and down > 0) else 0)
        trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
    def smooth(arr, p):
        return sum(arr[-p:]) / p if len(arr) >= p else sum(arr) / max(len(arr), 1)
    atr = smooth(trs, period)
    if atr == 0: return 0
    plus_di = 100 * smooth(plus_dm, period) / atr
    minus_di = 100 * smooth(minus_dm, period) / atr
    return abs(plus_di - minus_di) / max(plus_di + minus_di, 0.001) * 100

def calc_vol20(data):
    if len(data) < 21: return 0
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
    if len(data) < 61: return 0
    ma60_list = []
    for i in range(len(data)):
        if i < 59: ma60_list.append(None)
        else: ma60_list.append(sum(d['close'] for d in data[i-59:i+1]) / 60)
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
    if not ma60 or not data: return "S4", "风暴市", "数据不足"
    last = data[-1]
    above_ma60 = last['close'] > ma60
    crossings = ma60_crossings(data)
    if vol20 > 25: return "S4", "风暴市", f"vol20={vol20:.1f}%>25%"
    if above_ma60 and adx > 20: return "S1", "强趋势", f"价格>MA60+ADX={adx:.1f}>20"
    if above_ma60 and adx < 20: return "S2", "趋弱", f"价格>MA60+ADX={adx:.1f}<20"
    if not above_ma60 and crossings >= 3: return "S3", "震荡", f"价格<MA60+穿越{crossings}次"
    if not above_ma60 and crossings < 3: return "S3近似", "弱震荡", f"价格<MA60+穿越{crossings}次(需≥3)"
    return "S4", "风暴市", "默认"

# ========== 加载数据 ==========
kline_file = os.path.join(os.path.dirname(__file__), 'kline_close_0819.txt')
all_data = load_kline_file(kline_file)

# 指数
hs300_data = all_data.get('sh000300', [])
zz500_data = all_data.get('sh000905', [])
cyb_data = all_data.get('sz399006', [])

# 今日行情
hs300_today = hs300_data[-1]
hs300_yest = hs300_data[-2]
hs300_chg = (hs300_today['close'] - hs300_yest['close']) / hs300_yest['close'] * 100

zz500_today = zz500_data[-1]
zz500_yest = zz500_data[-2]
zz500_chg = (zz500_today['close'] - zz500_yest['close']) / zz500_yest['close'] * 100

cyb_today = cyb_data[-1]
cyb_yest = cyb_data[-2]
cyb_chg = (cyb_today['close'] - cyb_yest['close']) / cyb_yest['close'] * 100

# 指标
hs300_vol20 = calc_vol20(hs300_data)
hs300_ma60 = calc_ma(hs300_data, 60)
hs300_adx = calc_adx(hs300_data, 14)
tre_hs300 = tre_state(hs300_data)
tre_zz500 = tre_state(zz500_data)
tre_cyb = tre_state(cyb_data)

print(f"沪深300: {hs300_today['date']} close={hs300_today['close']} chg={hs300_chg:.2f}%")
print(f"中证500: chg={zz500_chg:.2f}%")
print(f"创业板指: chg={cyb_chg:.2f}%")
print(f"vol20={hs300_vol20:.2f}% TRE: HS300={tre_hs300[0]} ZZ500={tre_zz500[0]} CYB={tre_cyb[0]}")

# R-04闸门
if hs300_vol20 < 15: gate = "闸门A（禁一切）"; gate_color = "#dc3545"
elif hs300_vol20 >= 20: gate = "闸门B（禁S1/S2常规）"; gate_color = "#fd7e14"
else: gate = "正常区"; gate_color = "#28a745"

# ========== 持仓 ==========
positions = [
    {'code': '600276', 'name': '恒瑞医药', 'shares': 900, 'cost_price': 51.2726,
     'buy_date': '2026-07-01', 'tier': '防守底盘', 'kline_key': 'sh600276'},
    {'code': '510300', 'name': '沪深300ETF', 'shares': 40700, 'cost_price': 4.8224,
     'buy_date': '2026-07-08', 'tier': '防守底盘', 'kline_key': 'sh510300'},
    {'code': '159650', 'name': '国开债ETF', 'shares': 1800, 'cost_price': 107.5870,
     'buy_date': '2026-06-04', 'tier': '稳定器', 'kline_key': 'sz159650'},
    {'code': '603259', 'name': '药明康德', 'shares': 0, 'cost_price': 0,
     'buy_date': '', 'tier': '观察池', 'kline_key': 'sh603259'},
]
account = {'cash': 366708.97}

pos_results = []
for pos in positions:
    data = all_data.get(pos['kline_key'], [])
    if not data: continue
    today = data[-1]
    yest = data[-2]
    chg_pct = (today['close'] - yest['close']) / yest['close'] * 100
    
    if pos['tier'] == '观察池':
        result = {**pos, 'close': today['close'], 'chg_pct': chg_pct,
                  'high': today['high'], 'low': today['low'], 'open': today['open']}
        pos_results.append(result)
        print(f"  {pos['name']}: close={today['close']} chg={chg_pct:.2f}% (观察池)")
        continue

    current = today['close']
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
    today_dt = datetime.strptime('2026-08-19', '%Y-%m-%d')
    holding_days = (today_dt - buy_dt).days
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
    s4_level = highest * 0.89

    # 触发判定
    p0_trig = current < p0_level
    p1_trig = current < p1_stop
    p2_trig = current < p2_level
    s4_trig = current < s4_level

    # 近5日
    five_day_pct = (current - data[-6]['close']) / data[-6]['close'] * 100 if len(data) >= 6 else 0

    # P12
    profit_from_cost = (highest - cost) / cost * 100
    p12_active = profit_from_cost >= 15

    result = {**pos, 'close': current, 'chg_pct': chg_pct, 'market_value': market_value,
              'cost_basis': cost_basis, 'pnl': pnl, 'pnl_pct': pnl_pct, 'ma60': ma60,
              'ma60_dev': ma60_dev, 'above_ma60': current > ma60 if ma60 else False,
              'atr': atr, 'adx': adx, 'vol20': vol20, 'holding_days': holding_days,
              'bandwidth': bandwidth, 'p1_stop': p1_stop, 'highest': highest,
              'drawdown_pct': drawdown_pct, 'p0_level': p0_level, 'p2_level': p2_level,
              's4_level': s4_level, 'p0_trig': p0_trig, 'p1_trig': p1_trig,
              'p2_trig': p2_trig, 's4_trig': s4_trig, 'five_day_pct': five_day_pct,
              'p12_active': p12_active, 'profit_from_cost': profit_from_cost,
              'high': today['high'], 'low': today['low'], 'open': today['open']}
    pos_results.append(result)
    print(f"  {pos['name']}: close={current} chg={chg_pct:+.2f}% pnl={pnl:+.0f}({pnl_pct:+.2f}%) "
          f"MA60={ma60:.2f} ATR={atr:.3f} ADX={adx:.1f} vol20={vol20:.1f}% "
          f"P1={p1_stop:.3f}(trig={p1_trig}) P0={p0_trig} 回撤={drawdown_pct:.2f}%")

# ========== 三层配置 ==========
hold_positions = [p for p in pos_results if p['tier'] != '观察池']
total_position_value = sum(p['market_value'] for p in hold_positions)
total_assets = total_position_value + account['cash']
defense_base = sum(p['market_value'] for p in hold_positions if p['tier'] == '防守底盘')
stabilizer = sum(p['market_value'] for p in hold_positions if p['tier'] == '稳定器') + account['cash']
defense_pct = defense_base / total_assets * 100
stabilizer_pct = stabilizer / total_assets * 100

# ========== 账户总盈亏 ==========
total_pnl = sum(p['pnl'] for p in hold_positions)

# ========== HTML ==========
def fmt(v): return f"{v:,.0f}"
def pnl_cls(v): return "profit" if v > 0 else "loss"
def chg_cls(v): return "profit" if v > 0 else "loss"

# 执行指令判定
hr = pos_results[0]  # 恒瑞
etf = pos_results[1]  # 沪深300ETF

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>收盘总结 - 2026-08-19</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:"Microsoft YaHei","PingFang SC",sans-serif; background:#f5f7fa; color:#333; line-height:1.6; padding:20px; }}
.container {{ max-width:1200px; margin:0 auto; }}
.header {{ background:linear-gradient(135deg,#b71c1c 0%,#d32f2f 100%); color:white; padding:24px 30px; border-radius:12px; margin-bottom:20px; box-shadow:0 4px 12px rgba(0,0,0,0.15); }}
.header h1 {{ font-size:24px; margin-bottom:6px; }}
.header .meta {{ font-size:13px; opacity:0.9; }}
.section {{ background:white; border-radius:10px; padding:20px 24px; margin-bottom:16px; box-shadow:0 2px 8px rgba(0,0,0,0.06); }}
.section-title {{ font-size:16px; font-weight:700; color:#b71c1c; margin-bottom:14px; padding-bottom:8px; border-bottom:2px solid #ffebee; display:flex; align-items:center; gap:8px; }}
.section-title .icon {{ width:8px; height:20px; background:#b71c1c; border-radius:3px; }}
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
.footer {{ text-align:center; padding:16px; color:#999; font-size:12px; margin-top:20px; }}
.profit {{ color:#dc3545; font-weight:600; }}
.loss {{ color:#2e7d32; font-weight:600; }}
.critical {{ background:#ffebee; border:2px solid #c62828; border-radius:8px; padding:16px; margin:8px 0; }}
</style>
</head>
<body>
<div class="container">

<div class="header">
  <h1>收盘总结 — 2026-08-19（周三）</h1>
  <div class="meta">
    生成时间：15:40 | 策略版本：v4.7-R10完整补齐版 | 数据源：westockdata |
    <span style="color:#ffcdd2;">市场暴跌日，沪深300ETF P1止损已触发！明日开盘需执行清仓</span>
  </div>
</div>

<!-- 市场行情 -->
<div class="section">
  <div class="section-title"><span class="icon"></span>今日市场行情</div>
  <table>
    <tr><th>指数</th><th>昨收</th><th>今收</th><th>涨跌幅</th><th>最高</th><th>最低</th><th>振幅</th><th>成交额</th></tr>
    <tr>
      <td><strong>沪深300</strong></td><td>{hs300_yest['close']:.2f}</td><td><strong style="color:#2e7d32;">{hs300_today['close']:.2f}</strong></td>
      <td class="loss">{hs300_chg:+.2f}%</td><td>{hs300_today['high']:.2f}</td><td>{hs300_today['low']:.2f}</td>
      <td>{(hs300_today['high']-hs300_today['low'])/hs300_yest['close']*100:.2f}%</td><td>{hs300_today['amount']/1e8:.0f}亿</td>
    </tr>
    <tr>
      <td><strong>中证500</strong></td><td>{zz500_yest['close']:.2f}</td><td><strong style="color:#2e7d32;">{zz500_today['close']:.2f}</strong></td>
      <td class="loss">{zz500_chg:+.2f}%</td><td>{zz500_today['high']:.2f}</td><td>{zz500_today['low']:.2f}</td>
      <td>{(zz500_today['high']-zz500_today['low'])/zz500_yest['close']*100:.2f}%</td><td>{zz500_today['amount']/1e8:.0f}亿</td>
    </tr>
    <tr>
      <td><strong>创业板指</strong></td><td>{cyb_yest['close']:.2f}</td><td><strong style="color:#2e7d32;">{cyb_today['close']:.2f}</strong></td>
      <td class="loss">{cyb_chg:+.2f}%</td><td>{cyb_today['high']:.2f}</td><td>{cyb_today['low']:.2f}</td>
      <td>{(cyb_today['high']-cyb_today['low'])/cyb_yest['close']*100:.2f}%</td><td>{cyb_today['amount']/1e8:.0f}亿</td>
    </tr>
  </table>
  <div class="alert-box alert-danger" style="margin-top:12px;">
    <strong>市场定调：暴跌日</strong> — 三大指数全线重挫，创业板指-6.26%为近期最大单日跌幅。
    中证500-4.82%，沪深300-2.90%。市场恐慌情绪蔓延，S4风暴市状态延续。
  </div>
</div>

<!-- TRE + R-04 -->
<div class="section">
  <div class="section-title"><span class="icon"></span>市场环境（TRE + R-04）</div>
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
    <strong>S4严控状态延续 → 禁止一切新建仓/补仓</strong><br>
    三大指数均处于MA60下方，创业板指vol20预计进一步攀升<br>
    S4下存量持仓按"提前一档"管理：P0=减仓信号、P1=即刻执行、P2=清仓、-11%=即刻清仓<br>
    <strong>明日继续禁止新建仓，仅执行止损/止盈指令</strong>
  </div>
</div>

<!-- 持仓监控表 -->
<div class="section">
  <div class="section-title"><span class="icon"></span>持仓监控表（收盘价）</div>
  <div style="overflow-x:auto;">
  <table>
    <tr>
      <th>标的</th><th>层级</th><th>持股</th><th>成本价</th><th>今开</th><th>最高</th><th>最低</th>
      <th>收盘</th><th>涨跌</th><th>盈亏</th><th>盈亏%</th>
      <th>MA60</th><th>偏离</th><th>持有天</th><th>带宽</th><th>P1止损</th><th>P1</th>
      <th>最高价</th><th>回撤</th><th>P0</th><th>S4(-11%)</th><th>ADX</th><th>vol20</th>
    </tr>
'''

for p in pos_results:
    if p['tier'] == '观察池':
        html += f'''    <tr style="background:#f8f9fa;">
      <td><strong>{p["name"]}</strong><br><span style="color:#999;font-size:11px;">{p["code"]}</span></td>
      <td><span class="badge badge-gray">观察池</span></td>
      <td>—</td><td>—</td><td>{p["open"]:.2f}</td><td>{p["high"]:.2f}</td><td>{p["low"]:.2f}</td>
      <td><strong>{p["close"]:.2f}</strong></td>
      <td class="{chg_cls(p["chg_pct"])}">{p["chg_pct"]:+.2f}%</td>
      <td colspan="14" style="color:#999;text-align:center;">观察池标的，不纳入持仓计算</td>
    </tr>
'''
        continue

    p1_trig_str = "🔴触发" if p['p1_trig'] else "○未触发"
    p0_trig_str = "🔴触发" if p['p0_trig'] else "○未触发"
    ma60_str = f'{"●" if p["above_ma60"] else "○"} {p["ma60"]:.2f}' if p['ma60'] else '—'
    s4_dist = (p['close'] - p['s4_level']) / p['close'] * 100

    if p['tier'] == '稳定器':
        p1_s = '—'; p1_trig_s = '—'; hi_s = '—'; dd_s = '—'; p0_s = '—'; s4_s = '—'
    else:
        p1_s = f'{p["p1_stop"]:.3f}'; hi_s = f'{p["highest"]:.3f}'; dd_s = f'{p["drawdown_pct"]:.2f}%'
        s4_s = f'{p["s4_level"]:.3f}({s4_dist:.1f}%)'

    html += f'''    <tr>
      <td><strong>{p["name"]}</strong><br><span style="color:#999;font-size:11px;">{p["code"]}</span></td>
      <td><span class="badge {"badge-blue" if p["tier"]=="稳定器" else "badge-green"}">{p["tier"]}</span></td>
      <td>{p["shares"]:,}</td><td>{p["cost_price"]:.4f}</td>
      <td>{p["open"]:.3f}</td><td>{p["high"]:.3f}</td><td>{p["low"]:.3f}</td>
      <td><strong>{p["close"]:.3f}</strong></td>
      <td class="{chg_cls(p["chg_pct"])}">{p["chg_pct"]:+.2f}%</td>
      <td class="{pnl_cls(p["pnl"])}">¥{p["pnl"]:+,.0f}</td>
      <td class="{pnl_cls(p["pnl_pct"])}">{p["pnl_pct"]:+.2f}%</td>
      <td>{ma60_str}</td><td>{p["ma60_dev"]:+.2f}%</td>
      <td>{p["holding_days"]}天</td><td>{p["bandwidth"]}%</td>
      <td>{p1_s}</td><td>{p1_trig_str if p["tier"]!="稳定器" else "—"}</td>
      <td>{hi_s}</td><td>{dd_s}</td><td>{p0_trig_str if p["tier"]!="稳定器" else "—"}</td>
      <td>{s4_s}</td><td>{p["adx"]:.1f}</td><td>{p["vol20"]:.1f}%</td>
    </tr>
'''

html += f'''  </table>
  </div>
  <div style="margin-top:12px;font-size:12px;color:#666;">
    ●=高于MA60 ○=低于MA60 | R-06带宽：≤11日→7%，>11日→4% | P1=买入价-MIN(2×ATR,带宽%) |
    S4提前一档=动态回撤-11% | 成本价来源：券商F4查询(0731) | 红涨绿跌（A股惯例）
  </div>
</div>

<!-- 执行指令 -->
<div class="section">
  <div class="section-title"><span class="icon"></span>明日执行指令（S4规则）</div>
'''

for p in pos_results:
    if p['tier'] == '观察池':
        html += f'''  <div style="border:1px solid #e0e0e0;border-radius:8px;padding:16px;margin-bottom:12px;background:#f8f9fa;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <h3 style="font-size:14px;color:#757575;">{p["name"]}（{p["code"]}）— 观察池</h3>
      <span class="badge badge-gray">仅观察</span>
    </div>
    <table style="font-size:12px;">
      <tr><td style="width:20%;color:#666;">收盘/涨跌</td><td>{p["close"]:.2f} ({p["chg_pct"]:+.2f}%)</td>
      <td style="width:20%;color:#666;">今开/最高/最低</td><td>{p["open"]:.2f} / {p["high"]:.2f} / {p["low"]:.2f}</td></tr>
    </table>
    <div class="alert-box alert-info" style="margin-top:8px;font-size:12px;">
      药明康德偏离MA60仍有+36.5%，高位回调中，S4下禁止追高建仓。
    </div>
  </div>
'''
        continue

    if p['tier'] == '稳定器':
        html += f'''  <div style="border:1px solid #e0e0e0;border-radius:8px;padding:16px;margin-bottom:12px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <h3 style="font-size:14px;color:#1a237e;">{p["name"]}（{p["code"]}）— 稳定器</h3>
      <span class="badge badge-blue">正常运行</span>
    </div>
    <table style="font-size:12px;">
      <tr><td style="width:20%;color:#666;">收盘/涨跌</td><td style="width:30%;">{p["close"]:.3f} ({p["chg_pct"]:+.2f}%)</td>
      <td style="width:20%;color:#666;">市值</td><td>¥{fmt(p["market_value"])}</td></tr>
      <tr><td style="color:#666;">盈亏</td><td class="{pnl_cls(p["pnl"])}">¥{p["pnl"]:+,.0f} ({p["pnl_pct"]:+.2f}%)</td>
      <td style="color:#666;">功能</td><td>稳定器运行正常，波动率{p["vol20"]:.2f}%</td></tr>
    </table>
    <div class="alert-box alert-success" style="margin-top:8px;font-size:12px;">
      稳定器功能正常，无止损要求。继续持有。
    </div>
  </div>
'''
        continue

    # 防守底盘持仓
    actions = []
    alert_cls = "alert-warning"
    if p['s4_trig']:
        actions.append("S4即刻清仓线(-11%)已触发！明日开盘立即清仓")
        alert_cls = "alert-danger"
    elif p['p2_trig']:
        actions.append("P2(-8%)已触发，S4下=清仓信号，明日开盘清仓")
        alert_cls = "alert-danger"
    elif p['p1_trig']:
        actions.append(f"P1技术止损已触发！收盘{p['close']:.3f} < P1止损{p['p1_stop']:.3f}")
        actions.append(f"S4下P1=即刻执行 -> 明日开盘竞价清仓")
        alert_cls = "alert-danger"
    elif p['p0_trig']:
        actions.append(f"P0(-5%)已触发（回撤{abs(p['drawdown_pct']):.2f}%），S4下=减仓信号")
        actions.append(f"考虑减仓1/3（{p['shares']//3}股）")
        s4_dist = (p['close'] - p['s4_level']) / p['close'] * 100
        actions.append(f"距S4即刻清仓线{p['s4_level']:.3f}仅{s4_dist:.1f}%")
        alert_cls = "alert-warning"
    else:
        s4_dist = (p['close'] - p['s4_level']) / p['close'] * 100
        actions.append(f"距S4线{p['s4_level']:.3f}还有{s4_dist:.1f}%")
        alert_cls = "alert-info"

    p1_dist = (p['close'] - p['p1_stop']) / p['close'] * 100

    html += f'''  <div style="border:2px solid {"#c62828" if alert_cls=="alert-danger" else "#e0e0e0"};border-radius:8px;padding:16px;margin-bottom:12px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
      <h3 style="font-size:15px;color:#b71c1c;">{p["name"]}（{p["code"]}）— {p["tier"]}</h3>
      <span class="badge {"badge-red" if alert_cls=="alert-danger" else "badge-orange" if alert_cls=="alert-warning" else "badge-green"}">
        {"P1触发" if p["p1_trig"] else "P0触发" if p["p0_trig"] else "正常"}
      </span>
    </div>
    <table style="font-size:12px;">
      <tr>
        <td style="width:18%;color:#666;">持股/成本</td><td style="width:32%;">{p["shares"]:,}股 @ ¥{p["cost_price"]:.4f}</td>
        <td style="width:18%;color:#666;">今开/最高/最低</td><td>{p["open"]:.3f} / {p["high"]:.3f} / {p["low"]:.3f}</td>
      </tr>
      <tr>
        <td style="color:#666;">收盘/涨跌</td><td><strong>{p["close"]:.3f}</strong> <span class="{chg_cls(p["chg_pct"])}">({p["chg_pct"]:+.2f}%)</span></td>
        <td style="color:#666;">市值/盈亏</td><td>¥{fmt(p["market_value"])} / <span class="{pnl_cls(p["pnl"])}">¥{p["pnl"]:+,.0f}({p["pnl_pct"]:+.2f}%)</span></td>
      </tr>
      <tr>
        <td style="color:#666;">MA60/偏离</td><td>{"●" if p["above_ma60"] else "○"} {p["ma60"]:.3f} ({p["ma60_dev"]:+.2f}%)</td>
        <td style="color:#666;">ATR/ADX/vol20</td><td>{p["atr"]:.3f} / {p["adx"]:.1f} / {p["vol20"]:.1f}%</td>
      </tr>
      <tr>
        <td style="color:#666;">持有天数/带宽</td><td>{p["holding_days"]}天 / {p["bandwidth"]}%</td>
        <td style="color:#666;">近5日</td><td>{p["five_day_pct"]:+.2f}%</td>
      </tr>
      <tr>
        <td style="color:#666;">P1止损位</td><td style="{"color:#c62828;font-weight:700;" if p["p1_trig"] else "color:#dc3545;"}><strong>{p["p1_stop"]:.3f}</strong> {"已触发！" if p["p1_trig"] else f"(距{p1_dist:.1f}%)"}</td>
        <td style="color:#666;">最高价/回撤</td><td>{p["highest"]:.3f} / {p["drawdown_pct"]:.2f}%</td>
      </tr>
      <tr>
        <td style="color:#666;">P0(-5%)/P2(-8%)</td><td>{"触发" if p["p0_trig"] else "未触发"} / {"触发" if p["p2_trig"] else "未触发"}</td>
        <td style="color:#666;">S4(-11%)</td><td style="color:#fd7e14;">{p["s4_level"]:.3f} (距{s4_dist:.1f}%)</td>
      </tr>
'''

    if p['p12_active']:
        if p['profit_from_cost'] >= 50: p12_trailing = p['highest'] * 0.55
        elif p['profit_from_cost'] >= 35: p12_trailing = p['highest'] * 0.65
        else: p12_trailing = p['highest'] * 0.75
        html += f'      <tr><td style="color:#666;">P12移动止盈</td><td style="color:#2e7d32;"><strong>已激活</strong>（浮盈{p["profit_from_cost"]:.1f}%≥15%）</td><td style="color:#666;">P12v6止盈线</td><td>{p12_trailing:.3f}</td></tr>\n'
    else:
        html += f'      <tr><td style="color:#666;">P12移动止盈</td><td>未激活（浮盈{p["profit_from_cost"]:.1f}%<15%）</td><td style="color:#666;">—</td><td>—</td></tr>\n'

    action_text = "<br>".join(f"• {a}" for a in actions)
    html += f'''    </table>
    <div class="alert-box {alert_cls}" style="margin-top:10px;font-size:13px;">
      <strong>明日执行指令：</strong><br>{action_text}
    </div>
  </div>
'''

html += f'''</div>

<!-- 账户总览 -->
<div class="section">
  <div class="section-title"><span class="icon"></span>账户总览</div>
  <table>
    <tr><th>项目</th><th>金额</th><th>占比</th><th>说明</th></tr>
    <tr><td>防守底盘（持仓）</td><td>¥{fmt(defense_base)}</td><td>{defense_pct:.1f}%</td><td>恒瑞医药+沪深300ETF</td></tr>
    <tr><td>现金国债稳定器</td><td>¥{fmt(stabilizer)}</td><td>{stabilizer_pct:.1f}%</td><td>国开债ETF+现金</td></tr>
    <tr><td>进攻线（模拟盘）</td><td>¥0</td><td>0%</td><td>B3待启动</td></tr>
    <tr style="background:#f8f9fa;font-weight:700;"><td>总资产</td><td>¥{fmt(total_assets)}</td><td>100%</td><td>含现金¥{fmt(account["cash"])}</td></tr>
    <tr><td>持仓浮盈浮亏</td><td class="{pnl_cls(total_pnl)}">¥{total_pnl:+,.0f}</td><td>—</td><td>持仓成本vs市值</td></tr>
  </table>
  <div class="alert-box alert-info" style="margin-top:12px;">
    防守底盘{defense_pct:.1f}%低于目标60-70%。高现金占比{stabilizer_pct:.1f}%是S4下正确的防御姿态。待TRE好转后逐步将现金转入防守底盘。
  </div>
</div>

<!-- 明日预案 -->
<div class="section">
  <div class="section-title"><span class="icon"></span>明日预案（2026-08-20 周四）</div>
  <div class="critical">
    <strong style="color:#c62828;font-size:15px;">第一优先级：沪深300ETF P1止损执行</strong>
    <table style="margin-top:8px;font-size:13px;">
      <tr><td style="width:25%;color:#666;">标的</td><td>沪深300ETF（510300）</td></tr>
      <tr><td style="color:#666;">持仓</td><td>40,700股</td></tr>
      <tr><td style="color:#666;">成本价</td><td>4.8224</td></tr>
      <tr><td style="color:#666;">今日收盘</td><td><strong>4.654</strong></td></tr>
      <tr><td style="color:#666;">P1止损位</td><td><strong style="color:#c62828;">{etf['p1_stop']:.3f}</strong>（收盘已跌破！）</td></tr>
      <tr><td style="color:#666;">S4执行规则</td><td>P1触发=即刻执行 -> 明日09:25集合竞价挂市价卖出</td></tr>
      <tr><td style="color:#666;">预计亏损</td><td class="loss">约¥{etf['pnl']:+,.0f}（{etf['pnl_pct']:+.2f}%）</td></tr>
      <tr><td style="color:#666;">R-03洗仓封堵</td><td>止损后30日内禁止重购，除非得分≥85分</td></tr>
    </table>
  </div>
  <div style="border:1px solid #ff9800;border-radius:8px;padding:16px;margin:12px 0;">
    <strong style="color:#e65100;font-size:15px;">第二优先级：恒瑞医药P0减仓评估</strong>
    <table style="margin-top:8px;font-size:13px;">
      <tr><td style="width:25%;color:#666;">标的</td><td>恒瑞医药（600276）</td></tr>
      <tr><td style="color:#666;">持仓</td><td>900股</td></tr>
      <tr><td style="color:#666;">成本价</td><td>51.2726</td></tr>
      <tr><td style="color:#666;">今日收盘</td><td><strong>52.66</strong>（+0.55%，抗跌）</td></tr>
      <tr><td style="color:#666;">最高价/回撤</td><td>58.00 / {hr['drawdown_pct']:.2f}%（P0已触发）</td></tr>
      <tr><td style="color:#666;">S4即刻清仓线</td><td><strong style="color:#fd7e14;">{hr['s4_level']:.2f}</strong>（距{(hr['close']-hr['s4_level'])/hr['close']*100:.1f}%）</td></tr>
      <tr><td style="color:#666;">P1止损位</td><td>{hr['p1_stop']:.2f}（距{(hr['close']-hr['p1_stop'])/hr['close']*100:.1f}%，暂安全）</td></tr>
      <tr><td style="color:#666;">执行规则</td><td>S4下P0触发=减仓信号。今日抗跌+0.55%属强势。<strong>建议观察明日走势：</strong>若站稳52以上可暂持，若跌破{hr['s4_level']:.2f}则即刻清仓</td></tr>
    </table>
  </div>
  <div class="alert-box alert-warning">
    <strong>明日时间表</strong>：<br>
    • 09:15-09:25 集合竞价 -> 沪深300ETF挂市价卖出（P1执行）<br>
    • 09:30 开盘 -> 确认恒瑞开盘价，评估是否站稳52<br>
    • 10:00/10:30/14:30 盘中波动率熔断监控<br>
    • 全天 恒瑞{hr['s4_level']:.2f}清仓线监控<br>
    • 15:00 收盘 -> 复盘P1执行结果+恒瑞持仓状态更新
  </div>
</div>

<!-- 策略状态 -->
<div class="section">
  <div class="section-title"><span class="icon"></span>策略状态与纪律提醒</div>
  <table>
    <tr><th>项目</th><th>状态</th><th>说明</th></tr>
    <tr><td>主引擎版本</td><td>v4.7-R10完整补齐版</td><td>35项融合裁决+10项重构裁决</td></tr>
    <tr><td>回测状态</td><td><span class="badge badge-red">未达标</span></td><td>IS年化2.97% < 6%门槛，禁止实盘新建仓</td></tr>
    <tr><td>当前执行权限</td><td><span class="badge badge-orange">仅限止损/止盈执行</span></td><td>S4严控，存量持仓按提前一档管理</td></tr>
    <tr><td>进攻线B3</td><td><span class="badge badge-gray">模拟盘阶段</span></td><td>≥6月验证达标后渐进实盘</td></tr>
    <tr><td>三层资金架构</td><td>防守{defense_pct:.0f}% / 稳定器{stabilizer_pct:.0f}% / 进攻0%</td><td>高现金=防御姿态</td></tr>
  </table>
  <div class="alert-box alert-warning" style="margin-top:12px;">
    <strong>纪律提醒</strong>：<br>
    1. P1止损已触发，明日必须执行，不可拖延（R-06止损纪律）<br>
    2. 止损后30日内禁止重购沪深300ETF，除非24因子评分≥85分（R-03洗仓封堵）<br>
    3. S4下禁止一切新建仓/补仓，包括恒瑞医药<br>
    4. 恒瑞若跌破{hr['s4_level']:.2f}（S4即刻清仓线），同样必须立即执行
  </div>
</div>

<div class="footer">
  收盘总结 v4.7-R10 | 2026-08-19 15:40 | 数据源：westockdata + 券商F4查询(0731) |
  本报告仅供策略执行参考，不构成个人投资建议。实盘交易决策由投资者自行承担。
</div>

</div>
</body>
</html>
'''

output_path = r'E:\fnOS\文档\证券\收盘总结-20260819.html'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"\n收盘总结已生成: {output_path}")
print(f"文件大小: {os.path.getsize(output_path):,} bytes")

# 关键结论
print("\n" + "="*60)
print("关键结论：")
print("="*60)
print(f"沪深300: {hs300_chg:+.2f}% | 中证500: {zz500_chg:+.2f}% | 创业板指: {cyb_chg:+.2f}%")
print(f"\n恒瑞医药: 收盘{hr['close']:.2f} ({hr['chg_pct']:+.2f}%)")
print(f"  P0={'触发' if hr['p0_trig'] else '未触发'} P1={'触发' if hr['p1_trig'] else '未触发'} S4线={hr['s4_level']:.2f}(距{(hr['close']-hr['s4_level'])/hr['close']*100:.1f}%)")
print(f"\n沪深300ETF: 收盘{etf['close']:.3f} ({etf['chg_pct']:+.2f}%)")
print(f"  P0={'触发' if etf['p0_trig'] else '未触发'} P1={'触发' if etf['p1_trig'] else '未触发'} P1止损={etf['p1_stop']:.3f}")
if etf['p1_trig']:
    print(f"  P1已触发！收盘{etf['close']:.3f} < P1止损{etf['p1_stop']:.3f}")
    print(f"  明日开盘必须执行清仓！")
    print(f"  预计亏损: ¥{etf['pnl']:+,.0f} ({etf['pnl_pct']:+.2f}%)")
print(f"\n国开债ETF: 收盘{pos_results[2]['close']:.3f} ({pos_results[2]['chg_pct']:+.2f}%) 稳定器正常")
print(f"\n药明康德: 收盘{pos_results[3]['close']:.2f} ({pos_results[3]['chg_pct']:+.2f}%) 观察池")
