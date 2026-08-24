# -*- coding: utf-8 -*-
"""
v4.7-R10 首轮选股报告生成器
生成 HTML 格式的观察池选股报告
"""
import json, io, os

BASE = r'E:/fnOS/文档/证券/中线趋势共振策略/回测/tmp/sectors'
OUT = r'E:/fnOS/文档/证券/中线趋势共振策略/选股'

with io.open(BASE + '/screen_result.json', encoding='utf-8') as f:
    data = json.load(f)

passed = data['passed']
failed = data['failed']

# Sector and policy line mapping
sector_map = {
    'sz300357': '生物医药', 'sz300693': '储能/逆变器', 'sh688239': '航空航天',
    'sh603005': '半导体封测', 'sz002335': '储能/数据中心', 'sz002472': '机器人',
    'sz002111': '低空经济', 'sz000099': '低空经济', 'sz002518': '储能/逆变器',
    'sh688686': '机器人视觉',
    # H档龙头（市值上限取消后纳入）
    'sh603259': '生物医药', 'sh605117': '储能/逆变器', 'sh688120': '半导体设备',
    'sz002371': '半导体设备', 'sz300750': '储能', 'sh600196': '生物医药',
    'sz002156': '半导体封测', 'sh688082': '半导体设备', 'sz300661': '半导体设计',
    'sh600276': '生物医药', 'sh600584': '半导体封测', 'sh603986': '半导体设计',
    'sh688008': '半导体设计', 'sz002050': '机器人零部件',
}
policy_map = {
    '生物医药': '主线2', '储能/逆变器': '主线1', '航空航天': '主线1',
    '半导体封测': '主线1', '储能/数据中心': '主线1', '机器人': '主线1',
    '低空经济': '主线1', '机器人视觉': '主线1', '半导体设备': '主线1',
    '储能': '主线1', '半导体设计': '主线1', '机器人零部件': '主线1',
}

# Sort by score
passed.sort(key=lambda x: -x['total'])

# 动态等级统计（避免硬编码漂移）
b_cnt = sum(1 for r in passed if r['grade'] == 'B')
c_cnt = sum(1 for r in passed if r['grade'] == 'C')

# H-grade stocks still failing (backup list)
h_list = [
    ('sh688981', '中芯国际', '半导体制造', '主线1', 'ROE 2.0% < 5%'),
    ('sh603501', '韦尔股份', '半导体设计', '主线1', '净利YoY -41.9% < -12%'),
    ('sh600760', '中航沈飞', '航空航天', '主线1', '净利-61.7%/营收-55.2%'),
    ('sz000768', '中航西飞', '航空航天', '主线1', '净利-14.7%/营收-17.0%/ROE 4.9%'),
    ('sh600893', '航发动力', '航空航天', '主线1', '净利-65.9%/ROE 1.3%'),
    ('sh000738', '航发控制', '航空航天', '主线1', '数据缺失'),
    ('sz300124', '汇川技术', '机器人', '主线1', '净利YoY -23.4% < -12%'),
    ('sz300760', '迈瑞医疗', '生物医药', '主线2', 'OCF/净利 < 0.5'),
    ('sh688287', '观典防务', '低空经济', '主线1', '数据缺失'),
]

# Count failures by filter
from collections import Counter
filter_counts = Counter()
real_failed = [r for r in failed if 'filters' in r]
for r in real_failed:
    for k, v in r['filters'].items():
        if not v:
            filter_counts[k] += 1

# Build HTML
html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>v4.7-R10 首轮选股报告 | 观察池筛选结果</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/echarts/5.4.3/echarts.min.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, "Microsoft YaHei", sans-serif; background: #f5f5f0; color: #2c2c2a; line-height: 1.6; font-size: 14px; }
.container { max-width: 960px; margin: 0 auto; padding: 24px 20px 60px; }
h1 { font-size: 22px; font-weight: 600; color: #1a1a1a; margin-bottom: 4px; }
h2 { font-size: 17px; font-weight: 600; color: #1a1a1a; margin: 28px 0 12px; padding-bottom: 8px; border-bottom: 2px solid #d4d0c4; }
h3 { font-size: 15px; font-weight: 500; color: #444; margin: 18px 0 8px; }
.subtitle { color: #888; font-size: 13px; margin-bottom: 20px; }
.card { background: #fff; border: 1px solid #e0ddd5; border-radius: 8px; padding: 16px 20px; margin-bottom: 16px; }
.summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.metric { background: #fff; border: 1px solid #e0ddd5; border-radius: 8px; padding: 14px 16px; text-align: center; }
.metric .num { font-size: 24px; font-weight: 600; color: #1a1a1a; }
.metric .num.red { color: #c0392b; }
.metric .num.green { color: #27ae60; }
.metric .num.amber { color: #e67e22; }
.metric .label { font-size: 12px; color: #888; margin-top: 4px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { background: #f8f7f4; padding: 10px 8px; text-align: left; font-weight: 600; color: #444; border-bottom: 2px solid #d4d0c4; font-size: 12px; }
td { padding: 8px; border-bottom: 1px solid #eee; }
tr:hover td { background: #fafaf7; }
.grade-B { color: #2980b9; font-weight: 600; }
.grade-C { color: #e67e22; font-weight: 600; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
.tag-m1 { background: #e8f0fe; color: #1a5276; }
.tag-m2 { background: #fef3e8; color: #935116; }
.tag-exempt { background: #eafaf1; color: #1e8449; }
.tag-vol-ok { background: #eafaf1; color: #1e8449; }
.tag-vol-warn { background: #fef3e8; color: #935116; }
.tag-vol-block { background: #fdedec; color: #922b21; }
.chart-box { background: #fff; border: 1px solid #e0ddd5; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
.chart { width: 100%; height: 280px; }
.note { background: #fef9e7; border: 1px solid #f9e79f; border-radius: 6px; padding: 12px 16px; font-size: 13px; color: #7d6608; margin-bottom: 12px; }
.warn { background: #fdedec; border: 1px solid #f5b7b1; border-radius: 6px; padding: 12px 16px; font-size: 13px; color: #922b21; margin-bottom: 12px; }
.disclaimer { margin-top: 32px; padding: 16px; background: #f8f7f4; border-radius: 8px; font-size: 12px; color: #888; text-align: center; }
.scroll-x { overflow-x: auto; }
</style>
</head>
<body>
<div class="container">

<h1>v4.7-R10 首轮选股报告</h1>
<p class="subtitle">观察池筛选 | 2026-08-18 | 中线趋势共振策略 v4.7-R10 回测驱动重构版</p>

<div class="note">
<b>两项关键裁决（2026-08-18）：</b><br>
① <b>OCF 高增长豁免</b>——对"营收+净利双正（双增）"的标的，OCF/净利>0.5 门槛降至 OCF>0（仅排除负现金流）。研发驱动成长股在扩产备货期 OCF 天然偏弱，不等于账面利润造假。<br>
② <b>流通市值上限取消</b>——原层级1硬过滤"50-500亿"系统性排除六大赛道龙头（中芯国际/北方华创/恒瑞/宁德时代等均>500亿）。与8.2市值均衡"大盘股>200亿"定义矛盾，取消上限仅保留下限≥50亿。补拉H档12只龙头数据后，通过数从10只增至24只，B级从1只增至9只。
</div>

<h2>一、筛选总览</h2>
<div class="summary-grid">
<div class="metric"><div class="num">84</div><div class="label">六赛道候选总数</div></div>
<div class="metric"><div class="num green">24</div><div class="label">通过硬过滤（观察池）</div></div>
<div class="metric"><div class="num red">58</div><div class="label">硬过滤淘汰</div></div>
<div class="metric"><div class="num amber">2</div><div class="label">数据缺失</div></div>
</div>

<div class="card">
<h3>失败过滤器命中统计（58只）</h3>
<div id="chart_filter" class="chart"></div>
</div>

<h2>二、观察池（24只，Top 12 优先建仓候选）</h2>
<p style="font-size:13px; color:#888; margin-bottom:12px;">按总评分降序排列。评级口径：A+≥90 / A≥80 / B≥70 / C&lt;70。B级可排序入池，C级仅监控不建仓。24只超过R-09观察池8-12只上限，取Top 12为优先监控/建仓候选，其余12只为扩展池。</p>

<div class="scroll-x">
<table>
<thead>
<tr>
<th>#</th><th>代码</th><th>名称</th><th>赛道</th><th>主线</th><th>市值(亿)</th>
<th>总评</th><th>级</th><th>基本面</th><th>趋势</th><th>情绪</th><th>微观</th><th>风控</th>
<th>vol20</th><th>OCF豁免</th>
</tr>
</thead>
<tbody>
'''

for i, r in enumerate(passed):
    sec = sector_map.get(r['code'], '?')
    pol = policy_map.get(sec, '?')
    exempt = r.get('high_growth_exempt', False)
    vol20 = r.get('vol20', 0)
    
    # R-04 vol20 gate
    if vol20 < 15:
        vol_tag = '<span class="tag tag-vol-block">R-04禁建</span>'
    elif vol20 >= 20:
        vol_tag = '<span class="tag tag-vol-warn">R-04仅S3/观察</span>'
    else:
        vol_tag = '<span class="tag tag-vol-ok">正常</span>'
    
    grade_class = f'grade-{r["grade"]}'
    pol_tag = f'<span class="tag tag-{"m1" if pol=="主线1" else "m2"}">{pol}</span>'
    exempt_tag = '<span class="tag tag-exempt">是</span>' if exempt else '<span style="color:#888">否</span>'
    
    html += f'''<tr>
<td>{i+1}</td><td>{r["code"]}</td><td>{r["name"]}</td><td>{sec}</td><td>{pol_tag}</td>
<td>{r["mkt_cap"]:.0f}</td><td class="{grade_class}">{r["total"]:.1f}</td><td class="{grade_class}">{r["grade"]}</td>
<td>{r["f"]["fundamental"]:.1f}</td><td>{r["f"]["trend"]:.1f}</td><td>{r["f"]["emotion"]:.1f}</td>
<td>{r["f"]["micro"]:.1f}</td><td>{r["f"]["risk"]:.1f}</td>
<td>{vol20:.1f}% {vol_tag}</td><td>{exempt_tag}</td>
</tr>'''

html += '''
</tbody>
</table>
</div>

<div class="card" style="margin-top:12px;">
<h3>观察池关键指标明细</h3>
<div class="scroll-x">
<table>
<thead>
<tr>
<th>代码</th><th>名称</th><th>净利YoY</th><th>营收YoY</th><th>ROE</th><th>毛利率</th>
<th>OCF/净利</th><th>PE(2026E)</th><th>PB(2026E)</th><th>一致预期机构数</th>
<th>MA60趋势</th><th>价/MA60</th><th>20日涨幅</th><th>60日涨幅</th>
</tr>
</thead>
<tbody>
'''

for r in passed:
    ma60_up = r.get('ma60_up', False)
    ma60_tag = '上升' if ma60_up else '下降'
    ma60_color = '#27ae60' if ma60_up else '#e74c3c'
    ocf = r.get('ocf_ratio')
    ocf_str = f'{ocf:.2f}' if ocf is not None else '—'
    
    html += f'''<tr>
<td>{r["code"]}</td><td>{r["name"]}</td>
<td>{r["np_yoy"]:.1f}%</td><td>{r["rev_yoy"]:.1f}%</td><td>{r["roe"]:.2f}%</td>
<td>{r.get("gross_m", 0):.1f}%</td><td>{ocf_str}</td>
<td>{r.get("cs_pe", "—") or "—"}</td><td>{r.get("cs_pb", "—") or "—"}</td>
<td>{r.get("cs_inst", 0)}</td>
<td style="color:{ma60_color}">{ma60_tag}</td>
<td>{r.get("pos_ma60", 0):.3f}</td>
<td>{r.get("rps20", 0):.1f}%</td><td>{r.get("ret60", 0):.1f}%</td>
</tr>'''

html += '''
</tbody>
</table>
</div>
</div>

<h2>三、赛道与主线分布</h2>
<div class="card">
<div id="chart_sector" class="chart"></div>
</div>

<div class="warn">
<b>R-04 波动率双闸门预警：</b>24只观察池标的中，23只 vol20≥20%（触发"禁S1S2常规建仓，仅S3有限建仓+观察通道"），仅威海广泰 vol20=18.2% 处于正常区间（15-20%）。当前市场波动率环境下，绝大多数标的只能通过观察通道试探仓或S3有限建仓介入，无法执行常规S1/S2建仓。
</div>

<h2>四、未通过龙头备选（9只）</h2>
<p style="font-size:13px; color:#888; margin-bottom:12px;">市值上限取消后仍因财报硬过滤未通过的赛道龙头。这些标的在盈利修复或现金流改善后可快速纳入观察池。</p>

<div class="scroll-x">
<table>
<thead>
<tr><th>代码</th><th>名称</th><th>赛道</th><th>主线</th><th>备注</th></tr>
</thead>
<tbody>
'''

for code, name, sec, pol, fail_reason in h_list:
    note_text = fail_reason
    
    pol_tag = f'<span class="tag tag-{"m1" if pol=="主线1" else "m2"}">{pol}</span>'
    html += f'<tr><td>{code}</td><td>{name}</td><td>{sec}</td><td>{pol_tag}</td><td style="color:#888;font-size:12px">{note_text}</td></tr>'

html += '''
</tbody>
</table>
</div>

<h2>五、筛选漏斗</h2>
<div class="card">
<div id="chart_funnel" class="chart" style="height:320px;"></div>
</div>

<h2>六、配置规则校验</h2>
<div class="card">
<table style="font-size:13px;">
<tr><th>规则</th><th>要求</th><th>当前</th><th>状态</th></tr>
<tr><td>观察池数量</td><td>8-12只</td><td>24只（Top12优先+12扩展）</td><td style="color:#27ae60;font-weight:600">达标（超过上限取Top12）</td></tr>
<tr><td>B级及以上</td><td>可排序建仓</td><td>9只B级</td><td style="color:#27ae60;font-weight:600">优于上轮(1只B级)</td></tr>
<tr><td>主线1(硬科技)上限</td><td>≤3只建仓</td><td>20只在池</td><td style="color:#e67e22;">池中偏多，实际建仓≤3</td></tr>
<tr><td>主线2(内需)上限</td><td>≤3只建仓</td><td>4只在池（药明/我武/复星/恒瑞）</td><td style="color:#27ae60;">达标</td></tr>
<tr><td>单一行业≤30%</td><td>预警线</td><td>半导体10只/储能5只/生物医药4只</td><td style="color:#e67e22;">半导体集中度偏高</td></tr>
<tr><td>单票≤15%</td><td>硬上限</td><td>建仓时由F-04控制</td><td style="color:#27ae60;">建仓阶段执行</td></tr>
<tr><td>总仓≤80%</td><td>硬上限</td><td>建仓阶段执行</td><td style="color:#27ae60;">建仓阶段执行</td></tr>
<tr><td>现金≥20%</td><td>硬下限</td><td>建仓阶段执行</td><td style="color:#27ae60;">建仓阶段执行</td></tr>
<tr><td>vol20≥15(R-04)</td><td>建仓前置条件</td><td>24只中23只vol20≥20</td><td style="color:#e74c3c;font-weight:600">23只仅S3/观察通道</td></tr>
</table>
</div>

<h2>七、下一步行动</h2>
<div class="card">
<ol style="font-size:13px; line-height:2;">
<li><b>日常监控</b>：对24只观察池标的执行每日盘后 TRE 状态判定，重点监控 vol20 变化与 MA60 趋势。Top 12 优先监控</li>
<li><b>观察通道</b>：对 vol20≥20 的23只标的，仅可通过观察通道试探仓介入（F-30/F-32/F-33 全套流程）</li>
<li><b>正常建仓窗口</b>：仅威海广泰(vol20=18.2%)可执行常规建仓，但需满足 24因子≥80分(A级)且通过六灯校验</li>
<li><b>建仓频率校准</b>：R-08 要求月建仓2-6次（年6-18笔），当前观察池规模充分支持此频率</li>
<li><b>未通过龙头跟踪</b>：9只因财报硬过滤未通过的龙头（中芯国际ROE/韦尔净利下滑/沈飞双降等），在盈利修复后可快速纳入</li>
<li><b>策略文档更新</b>：需将层级1硬过滤"流通市值50-500亿"修订为"流通市值≥50亿(无上限)"，并记录OCF高增长豁免裁决</li>
</ol>
</div>

<div class="disclaimer">
<p>本报告仅供研究参考，不构成个人投资建议。市场有风险，投资需谨慎。所有数据来源于公开市场数据，可能存在延迟或误差。策略回测结果不代表未来表现。</p>
<p style="margin-top:8px;">中线趋势共振策略 v4.7-R10 | 2026-08-18 | AI辅助人工模式</p>
</div>

</div>

<script>
// Filter failure chart
var chartFilter = echarts.init(document.getElementById('chart_filter'));
chartFilter.setOption({
    title: { text: '硬过滤失败原因统计', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '15%', right: '8%', top: 40, bottom: 30 },
    xAxis: { type: 'value', name: '命中次数' },
    yAxis: { type: 'category', data: ''' + str([k for k, _ in filter_counts.most_common()]).replace("'", '"') + ''', axisLabel: { fontSize: 12 } },
    series: [{
        type: 'bar',
        data: ''' + str([v for _, v in filter_counts.most_common()]) + ''',
        itemStyle: { color: function(p) { var colors = ['#c0392b','#e67e22','#f39c12','#3498db','#95a5a6','#bdc3c7']; return colors[p.dataIndex % colors.length]; } },
        label: { show: true, position: 'right', fontSize: 12 }
    }]
});

// Sector distribution chart
var chartSector = echarts.init(document.getElementById('chart_sector'));
var sectorData = [
'''

# Count sectors
from collections import Counter
sec_count = Counter()
for r in passed:
    sec = sector_map.get(r['code'], '?')
    sec_count[sec] += 1

for sec, cnt in sec_count.most_common():
    html += f'    {{value: {cnt}, name: "{sec}"}},\n'

html += '''];
chartSector.setOption({
    title: { text: '观察池赛道分布', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'item', formatter: '{b}: {c}只 ({d}%)' },
    legend: { orient: 'vertical', left: 'left', top: 'middle', textStyle: { fontSize: 12 } },
    series: [{
        type: 'pie',
        radius: ['35%', '65%'],
        center: ['60%', '50%'],
        data: sectorData,
        label: { fontSize: 12, formatter: '{b}\\n{c}只' }
    }]
});

// Funnel chart
var chartFunnel = echarts.init(document.getElementById('chart_funnel'));
chartFunnel.setOption({
    title: { text: '筛选漏斗', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'item', formatter: '{b}: {c}只' },
    series: [{
        type: 'funnel',
        left: '15%',
        right: '15%',
        top: 50,
        bottom: 30,
        width: '70%',
        gap: 4,
        label: { show: true, position: 'inside', fontSize: 13 },
        data: [
            { value: 84, name: '六赛道候选总数', itemStyle: { color: '#378ADD' } },
            { value: 82, name: '有效数据', itemStyle: { color: '#85B7EB' } },
            { value: 58, name: '硬过滤淘汰', itemStyle: { color: '#D85A30' } },
            { value: 24, name: '通过硬过滤', itemStyle: { color: '#1D9E75' } },
            { value: 9, name: 'B级(可排序建仓)', itemStyle: { color: '#BA7517' } }
        ]
    }]
});

window.addEventListener('resize', function() {
    chartFilter.resize();
    chartSector.resize();
    chartFunnel.resize();
});
</script>
</body>
</html>
'''

os.makedirs(OUT, exist_ok=True)

# 动态统计替换（B级数量随数据自动同步，消除硬编码漂移）
html = html.replace('B级从1只增至9只', f'B级从1只增至{b_cnt}只')
html = html.replace('<td>9只B级</td>', f'<td>{b_cnt}只B级</td>')
html = html.replace("{ value: 9, name: 'B级(可排序建仓)'", f"{{ value: {b_cnt}, name: 'B级(可排序建仓)'")

out_path = OUT + '/v4.7-R10_首轮选股报告.html'
with io.open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'报告已生成: {out_path}')
print(f'文件大小: {os.path.getsize(out_path) / 1024:.1f} KB')
