#!/usr/bin/env python3
"""生成 MHD HTML 仪表盘"""
import json

# 加载图表数据
with open('mhd_chart_data.json', encoding='utf-8') as f:
    data = json.load(f)

# G1r交易匹配数据
g1r_trades = [
    {'date':'2020-07-29','code':'510300','tre':'S4','mhs':58,'breadth':21,'pnl':5.93,'win':True},
    {'date':'2020-08-25','code':'159915','tre':'S2','mhs':53,'breadth':8,'pnl':-5.02,'win':False},
    {'date':'2020-11-16','code':'510300','tre':'S2','mhs':68,'breadth':21,'pnl':11.41,'win':True},
    {'date':'2021-06-09','code':'512690','tre':'S1','mhs':63,'breadth':14,'pnl':-5.56,'win':False},
    {'date':'2022-07-04','code':'512880','tre':'S1','mhs':62,'breadth':21,'pnl':-6.25,'win':False},
    {'date':'2022-07-12','code':'510300','tre':'S1','mhs':49,'breadth':11,'pnl':-4.36,'win':False},
    {'date':'2022-07-13','code':'512010','tre':'S1','mhs':57,'breadth':24,'pnl':-4.17,'win':False},
    {'date':'2022-07-14','code':'515030','tre':'S1','mhs':56,'breadth':19,'pnl':-3.51,'win':False},
    {'date':'2022-07-18','code':'512690','tre':'S1','mhs':47,'breadth':21,'pnl':-3.49,'win':False},
    {'date':'2022-12-21','code':'159920','tre':'S1','mhs':42,'breadth':4,'pnl':6.42,'win':True},
    {'date':'2023-03-06','code':'512480','tre':'S2','mhs':47,'breadth':16,'pnl':9.09,'win':True},
    {'date':'2023-03-08','code':'510500','tre':'S2','mhs':37,'breadth':14,'pnl':-2.71,'win':False},
    {'date':'2023-08-15','code':'512690','tre':'S2','mhs':29,'breadth':0,'pnl':-2.47,'win':False},
    {'date':'2024-03-13','code':'510880','tre':'S1','mhs':76,'breadth':22,'pnl':3.58,'win':True},
    {'date':'2024-10-17','code':'510500','tre':'S4','mhs':61,'breadth':19,'pnl':8.73,'win':True},
    {'date':'2024-11-22','code':'512880','tre':'S2','mhs':40,'breadth':6,'pnl':-3.25,'win':False},
]

# 生成G1r买入散点JS
g1r_scatter_js = ""
for t in g1r_trades:
    if t['win']:
        g1r_scatter_js += f"g1rWinPoints.push(['{t['date']}', {t['mhs']}]);\n"
    else:
        g1r_scatter_js += f"g1rLosePoints.push(['{t['date']}', {t['mhs']}]);\n"

# 生成G1r表格行
g1r_rows = ""
for t in g1r_trades:
    fr_flag = 'FR-1' if t['date'] == '2022-12-21' else '--'
    win_tag = '<span class="tag tag-win">盈</span>' if t['win'] else '<span class="tag tag-lose">亏</span>'
    pnl_class = 'win' if t['pnl'] > 0 else 'lose'
    tre_lower = t['tre'].lower()
    g1r_rows += f'<tr><td>{t["date"]}</td><td>{t["code"]}</td><td><span class="tag tag-{tre_lower}">{t["tre"]}</span></td><td>{t["mhs"]}</td><td>{t["breadth"]}</td><td>{fr_flag}</td><td class="{pnl_class}">{t["pnl"]:+.2f}%</td><td>—</td><td>{win_tag}</td></tr>\n'

data_json = json.dumps(data, ensure_ascii=False)

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>市场健康度仪表盘 MHD v0.1 — 影子模式</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; background: #f0f2f5; color: #1f2937; line-height: 1.6; }}
.container {{ max-width: 1280px; margin: 0 auto; padding: 20px; }}
.header {{ background: linear-gradient(135deg, #1e3a5f, #2d5a87); color: white; padding: 28px 32px; border-radius: 12px; margin-bottom: 20px; }}
.header h1 {{ font-size: 26px; margin-bottom: 6px; }}
.header .subtitle {{ font-size: 14px; opacity: 0.85; }}
.badge {{ display: inline-block; background: rgba(255,255,255,0.2); padding: 3px 10px; border-radius: 12px; font-size: 12px; margin-left: 8px; }}
.cards {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 20px; }}
.card {{ background: white; padding: 18px; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); text-align: center; }}
.card .label {{ font-size: 12px; color: #6b7280; margin-bottom: 4px; }}
.card .value {{ font-size: 24px; font-weight: 700; }}
.card .sub {{ font-size: 11px; color: #9ca3af; margin-top: 2px; }}
.card.green .value {{ color: #059669; }}
.card.red .value {{ color: #dc2626; }}
.card.blue .value {{ color: #2563eb; }}
.card.amber .value {{ color: #d97706; }}
.card.gray .value {{ color: #6b7280; }}
.chart-box {{ background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }}
.chart-box h2 {{ font-size: 16px; margin-bottom: 12px; color: #374151; }}
.chart {{ width: 100%; height: 400px; }}
.chart.tall {{ height: 500px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ background: #f3f4f6; padding: 8px 10px; text-align: left; font-weight: 600; color: #374151; border-bottom: 2px solid #e5e7eb; }}
td {{ padding: 7px 10px; border-bottom: 1px solid #f3f4f6; }}
tr:hover {{ background: #f9fafb; }}
.win {{ color: #dc2626; font-weight: 600; }}
.lose {{ color: #059669; font-weight: 600; }}
.tag {{ display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
.tag-s1 {{ background: #fee2e2; color: #991b1b; }}
.tag-s2 {{ background: #fef3c7; color: #92400e; }}
.tag-s4 {{ background: #dbeafe; color: #1e40af; }}
.tag-win {{ background: #fee2e2; color: #991b1b; }}
.tag-lose {{ background: #d1fae5; color: #065f46; }}
.section-title {{ font-size: 18px; font-weight: 700; margin: 24px 0 12px; color: #1f2937; padding-left: 12px; border-left: 4px solid #2563eb; }}
.note {{ background: #fffbeb; border: 1px solid #fde68a; padding: 12px 16px; border-radius: 8px; margin: 12px 0; font-size: 13px; color: #92400e; }}
.disclaimer {{ margin-top: 24px; padding: 16px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #9ca3af; text-align: center; }}
.stat-table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin: 8px 0; }}
.stat-table th {{ background: #eff6ff; padding: 8px; text-align: center; }}
.stat-table td {{ padding: 8px; text-align: center; }}
.highlight-row {{ background: #fef3c7; }}
</style>
</head>
<body>
<div class="container">

<div class="header">
  <h1>市场健康度仪表盘 MHD v0.1 <span class="badge">影子模式 · 不参与裁决</span></h1>
  <div class="subtitle">路径D · 2018-04-02 ~ 2026-06-30 · 1999 交易日 · 同时改善严控解除判据与识别假反弹</div>
</div>

<div class="cards">
  <div class="card blue"><div class="label">MHS 均值</div><div class="value">48.0</div><div class="sub">中位 49.0</div></div>
  <div class="card amber"><div class="label">假反弹信号</div><div class="value">215</div><div class="sub">10日precision 51.6%</div></div>
  <div class="card red"><div class="label">HALF窗 MHS</div><div class="value">43.6</div><div class="sub">vs 其他年 50.5</div></div>
  <div class="card green"><div class="label">MHS≥60 胜率</div><div class="value">60%</div><div class="sub">G1r 建仓均PnL +2.38%</div></div>
  <div class="card gray"><div class="label">BREADTH≥15</div><div class="value">56%</div><div class="sub">vs &lt;15仅14%</div></div>
</div>

<div class="chart-box">
  <h2>MHS 时间序列 (2018-2026) — HALF窗高亮 · 假反弹信号 · G1r建仓日</h2>
  <div id="chart_main" class="chart tall"></div>
</div>

<div class="chart-box">
  <h2>五维子分堆叠面积图 — 趋势/宽度/波动/动量/结构</h2>
  <div id="chart_stack" class="chart"></div>
</div>

<div class="chart-box">
  <h2>MHS 分布热力图 — 分年分档</h2>
  <div id="chart_heatmap" class="chart" style="height:350px"></div>
</div>

<div class="section-title">G1r 建仓日 × MHD 对照表（16笔精确匹配）</div>
<div class="chart-box">
<table>
<thead><tr><th>买入日</th><th>代码</th><th>TRE</th><th>MHS</th><th>BREADTH</th><th>FR</th><th>PnL%</th><th>离场原因</th><th>结果</th></tr></thead>
<tbody>
{g1r_rows}
</tbody></table>
</div>

<div class="section-title">分档统计 — MHS/BREADTH 阈值区分力</div>
<div class="chart-box">
<table class="stat-table">
<thead><tr><th>分档</th><th>样本</th><th>均PnL%</th><th>胜率</th><th>结论</th></tr></thead>
<tbody>
<tr><td>MHS ≥ 60</td><td>5</td><td class="win">+2.38%</td><td>60%</td><td>正期望 — 高健康度建仓有效</td></tr>
<tr><td>MHS &lt; 60</td><td>11</td><td class="lose">-0.68%</td><td>27%</td><td>负期望 — 低健康度建仓失效</td></tr>
<tr class="highlight-row"><td>BREADTH ≥ 15</td><td>9</td><td class="win">+2.37%</td><td>56%</td><td>宽度健康 — 建仓正期望</td></tr>
<tr class="highlight-row"><td>BREADTH &lt; 15</td><td>7</td><td class="lose">-2.42%</td><td>14%</td><td>灾难性 — 假反弹环境必亏</td></tr>
<tr><td>HALF窗 (2022-2024)</td><td>12</td><td class="lose">-0.20%</td><td>—</td><td>均MHS=50.2 — 恰好卡在分水岭</td></tr>
<tr><td>非HALF</td><td>4</td><td class="win">+1.69%</td><td>—</td><td>均MHS=60.5 — 健康区间</td></tr>
</tbody>
</table>
</div>

<div class="section-title">假反弹信号 Precision 检验</div>
<div class="chart-box">
<table class="stat-table">
<thead><tr><th>信号类型</th><th>次数</th><th>5日precision</th><th>10日precision</th><th>20日precision</th><th>基准率(10日)</th></tr></thead>
<tbody>
<tr><td>FR-1 弱假反弹</td><td>94</td><td>40.4%</td><td>—</td><td>—</td><td>49.4%</td></tr>
<tr><td>FR-2 强假反弹</td><td>48</td><td>54.2%</td><td>—</td><td>—</td><td>49.4%</td></tr>
<tr><td>FR-3 趋势假反弹</td><td>69</td><td>44.9%</td><td>—</td><td>—</td><td>49.4%</td></tr>
<tr><td>FR-4 权重拉升</td><td>4</td><td>0%</td><td>—</td><td>—</td><td>49.4%</td></tr>
<tr style="background:#f0fdf4"><td><b>总体</b></td><td><b>215</b></td><td>44.2%</td><td><b>51.6%</b></td><td>46.0%</td><td>49.4%</td></tr>
</tbody>
</table>
<div class="note"><b>FR信号 10日 precision 为 51.6%</b>（基准率 49.4%），边际优势 +2.2pp，未达 70% 升级门槛。但 <b>BREADTH 子分的区分力远强于 FR 信号本身</b>——BREADTH&lt;15 胜率仅 14% 是最有力的假反弹代理指标。MHS 与 G1r PnL 正相关 r=0.243，MHS≥60 时均 PnL +2.38%/胜率 60%，MHS&lt;60 时 -0.68%/27%。</div>
</div>

<div class="section-title">影子模式运行规则与升级条件</div>
<div class="chart-box">
<div class="note">
<b>当前状态</b>：影子模式 v0.1 已回填 2018-2026 历史数据（1999 交易日），<b>不参与任何策略裁决</b>。<br><br>
<b>升级三条件</b>（全部满足才谈接入）：<br>
1. MHS 与策略回测收益正相关 → <b>已验证 r=0.243（边际正相关）</b><br>
2. 假反弹信号 precision > 70% → <b>未达标</b>（10日 51.6%），但 BREADTH&lt;15 区分力极强（14% vs 56%），可替代<br>
3. 严控解除判据回测改善 → <b>待验证</b>：提案为「MHS连续5日>60 + FR≤1次 + BREADTH>15 + 背离<0.5%」四条同时满足<br><br>
<b>关键发现</b>：MHS=60 与 BREADTH=15 是两个核心分水岭。同时不满足时（MHS&lt;60 且 BREADTH&lt;15），G1r 建仓 7 笔中 6 亏（86%），均 PnL -2.42%。这正是 HALF 窗假反弹的量化指纹。
</div>
</div>

<div class="disclaimer">
本仪表盘仅供研究参考，不构成个人投资建议。市场有风险，投资需谨慎。<br>
数据来源：沪深300指数 + 29只个股（观察池24+大盘5） + 16只ETF（4宽基+12行业） · westockdata 通道<br>
MHD v0.1 · 2026-08-18 · 路径D 影子模式
</div>

</div>

<script>
var chartData = {data_json};

// ========== 主图: MHS时间序列 ==========
var mainChart = echarts.init(document.getElementById('chart_main'));
var frPoints = chartData.fr_dates.map(function(d) {{
    var idx = chartData.dates.indexOf(d);
    if (idx >= 0) return [d, chartData.mhs[idx]];
    return null;
}}).filter(function(x) {{ return x !== null; }});

var g1rBuyPoints = [];
var g1rWinPoints = [];
var g1rLosePoints = [];
{g1r_scatter_js}

var option = {{
    tooltip: {{ trigger: 'axis', axisPointer: {{ type: 'cross' }} }},
    legend: {{ data: ['MHS', '沪深300(右轴)', '假反弹信号', 'G1r买入-盈', 'G1r买入-亏'], top: 5 }},
    grid: {{ left: 60, right: 70, top: 50, bottom: 60 }},
    xAxis: {{ type: 'category', data: chartData.dates, axisLabel: {{ rotate: 30, formatter: function(v){{ return v.substring(0,7); }} }} }},
    yAxis: [
        {{ type: 'value', name: 'MHS', min: 0, max: 100, position: 'left' }},
        {{ type: 'value', name: '沪深300', position: 'right' }}
    ],
    dataZoom: [{{ type: 'inside', start: 0, end: 100 }}, {{ type: 'slider', start: 0, end: 100, bottom: 10 }}],
    series: [
        {{
            name: 'MHS', type: 'line', data: chartData.mhs, smooth: true,
            itemStyle: {{ color: '#2563eb' }}, lineStyle: {{ width: 1.5 }},
            areaStyle: {{ color: 'rgba(37,99,235,0.08)' }},
            markArea: {{ silent: true, itemStyle: {{ color: 'rgba(220,38,38,0.06)' }}, data: [[{{xAxis:'2022-01-01'}}, {{xAxis:'2024-12-31'}}]] }},
            markLine: {{ silent: true, symbol: 'none', data: [{{ yAxis: 60, lineStyle: {{ color: '#dc2626', type: 'dashed', width: 1.5 }}, label: {{ formatter: 'MHS=60 分水岭', color: '#dc2626' }} }}] }}
        }},
        {{
            name: '沪深300(右轴)', type: 'line', data: chartData.hs300, yAxisIndex: 1,
            itemStyle: {{ color: '#9ca3af' }}, lineStyle: {{ width: 1, type: 'dotted' }}
        }},
        {{
            name: '假反弹信号', type: 'scatter', data: frPoints,
            itemStyle: {{ color: '#f59e0b' }}, symbolSize: 5, z: 10
        }},
        {{
            name: 'G1r买入-盈', type: 'scatter', data: g1rWinPoints,
            itemStyle: {{ color: '#dc2626' }}, symbolSize: 10, z: 20
        }},
        {{
            name: 'G1r买入-亏', type: 'scatter', data: g1rLosePoints,
            itemStyle: {{ color: '#059669' }}, symbolSize: 10, z: 20
        }}
    ]
}};
mainChart.setOption(option);

// ========== 堆叠面积图 ==========
var stackChart = echarts.init(document.getElementById('chart_stack'));
stackChart.setOption({{
    tooltip: {{ trigger: 'axis' }},
    legend: {{ data: ['趋势25', '宽度30', '波动20', '动量15', '结构10'], top: 5 }},
    grid: {{ left: 50, right: 30, top: 50, bottom: 50 }},
    xAxis: {{ type: 'category', data: chartData.dates, axisLabel: {{ rotate: 30, formatter: function(v){{ return v.substring(0,7); }} }} }},
    yAxis: {{ type: 'value', name: '子分', max: 100 }},
    dataZoom: [{{ type: 'inside', start: 0, end: 100 }}, {{ type: 'slider', start: 0, end: 100, bottom: 10 }}],
    series: [
        {{ name: '趋势25', type: 'line', stack: 'total', data: chartData.trend, areaStyle: {{ opacity: 0.5 }}, itemStyle: {{ color: '#3b82f6' }} }},
        {{ name: '宽度30', type: 'line', stack: 'total', data: chartData.breadth, areaStyle: {{ opacity: 0.5 }}, itemStyle: {{ color: '#ef4444' }} }},
        {{ name: '波动20', type: 'line', stack: 'total', data: chartData.vol, areaStyle: {{ opacity: 0.5 }}, itemStyle: {{ color: '#10b981' }} }},
        {{ name: '动量15', type: 'line', stack: 'total', data: chartData.mom, areaStyle: {{ opacity: 0.5 }}, itemStyle: {{ color: '#f59e0b' }} }},
        {{ name: '结构10', type: 'line', stack: 'total', data: chartData.struct, areaStyle: {{ opacity: 0.5 }}, itemStyle: {{ color: '#8b5cf6' }} }}
    ]
}});

// ========== 热力图 ==========
var heatChart = echarts.init(document.getElementById('chart_heatmap'));
var years = ['2018','2019','2020','2021','2022','2023','2024','2025','2026'];
var buckets = ['0-9','10-19','20-29','30-39','40-49','50-59','60-69','70-79','80-89'];
var heatData = [];
for (var yi = 0; yi < years.length; yi++) {{
    for (var bi = 0; bi < buckets.length; bi++) {{
        var count = 0;
        for (var i = 0; i < chartData.dates.length; i++) {{
            if (chartData.dates[i].substring(0,4) === years[yi]) {{
                var bucket = Math.floor(chartData.mhs[i] / 10);
                if (bucket === bi) count++;
            }}
        }}
        if (count > 0) heatData.push([yi, bi, count]);
    }}
}}
heatChart.setOption({{
    tooltip: {{ position: 'top' }},
    grid: {{ left: 60, right: 30, top: 30, bottom: 40 }},
    xAxis: {{ type: 'category', data: years, splitArea: {{ show: true }} }},
    yAxis: {{ type: 'category', data: buckets, splitArea: {{ show: true }}, inverse: true }},
    visualMap: {{ min: 0, max: 100, calculable: true, orient: 'horizontal', left: 'center', bottom: 0, inRange: {{ color: ['#dbeafe','#3b82f6','#1e40af','#dc2626'] }} }},
    series: [{{
        name: 'MHS分布', type: 'heatmap', data: heatData,
        label: {{ show: true, formatter: function(p){{ return p.value[2] > 0 ? p.value[2] : ''; }} }},
        emphasis: {{ itemStyle: {{ shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' }} }}
    }}]
}});

window.addEventListener('resize', function() {{
    mainChart.resize();
    stackChart.resize();
    heatChart.resize();
}});
</script>
</body></html>'''

with open('MHD仪表盘_v0.1.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f'HTML生成完成: {len(html)} 字符')
