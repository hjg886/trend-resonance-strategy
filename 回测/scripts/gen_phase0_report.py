# -*- coding: utf-8 -*-
"""生成阶段0信号供给端预检 HTML 报告"""
import os, json
from datetime import datetime

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")

# 加载预检结果
with open(os.path.join(OUT, "phase0_precheck.json"), encoding="utf-8") as f:
    data = json.load(f)

r01 = data["results"]["0.1"]
r02 = data["results"]["0.2"]
r03 = data["results"]["0.3"]
r04 = data["results"]["0.4"]
tre_dist = data["tre_state_distribution"]

# 年度触发数据
annual = r01["annual"]

# 个股vol20数据
stocks = r02.get("stocks", {})

# 判定图标
def icon(v):
    if v in ("PASS", "OK"): return "✅"
    if v == "WARN": return "⚠️"
    return "❌"

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>进攻线模拟盘 · 阶段0信号供给端预检报告</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, "Microsoft YaHei", "PingFang SC", sans-serif; background: #f5f5f5; color: #1a1a1a; line-height: 1.7; }}
.container {{ max-width: 1100px; margin: 0 auto; padding: 20px; }}
.header {{ background: linear-gradient(135deg, #0d3b66, #1a237e); color: white; padding: 30px 40px; border-radius: 12px; margin-bottom: 24px; }}
.header h1 {{ font-size: 23px; margin-bottom: 8px; }}
.header .subtitle {{ font-size: 14px; opacity: 0.85; }}
.header .date {{ font-size: 12px; opacity: 0.7; margin-top: 6px; }}
.header .tag {{ display: inline-block; background: rgba(255,255,255,0.15); padding: 3px 12px; border-radius: 20px; font-size: 12px; margin-right: 8px; margin-top: 10px; }}
.section {{ background: white; border-radius: 10px; padding: 24px 30px; margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }}
.section h2 {{ font-size: 18px; color: #1a237e; border-left: 4px solid #1a237e; padding-left: 12px; margin-bottom: 16px; }}
.section h3 {{ font-size: 15px; color: #333; margin: 18px 0 10px; }}
.section p {{ margin-bottom: 12px; font-size: 14px; }}
.section li {{ margin-left: 20px; margin-bottom: 6px; font-size: 14px; }}
table {{ width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 13px; }}
th {{ background: #e8eaf6; color: #1a237e; padding: 8px 10px; text-align: left; border: 1px solid #c5cae9; }}
td {{ padding: 8px 10px; border: 1px solid #e0e0e0; vertical-align: top; }}
tr:nth-child(even) td {{ background: #fafafa; }}
.hl {{ color: #c62828; font-weight: 600; }}
.ok {{ color: #2e7d32; font-weight: 600; }}
.warn {{ color: #e65100; font-weight: 600; }}
.chart {{ width: 100%; height: 340px; margin: 10px 0; }}
.callout {{ background: #fff8e1; border-left: 4px solid #f9a825; padding: 12px 16px; border-radius: 6px; margin: 14px 0; font-size: 13.5px; }}
.callout-blue {{ background: #e3f2fd; border-left-color: #1e88e5; }}
.callout-red {{ background: #fce4ec; border-left-color: #c62828; }}
.callout-green {{ background: #e8f5e9; border-left-color: #2e7d32; }}
.verdict-box {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 16px 0; }}
.verdict-card {{ flex: 1; min-width: 200px; border-radius: 8px; padding: 16px; border: 2px solid; }}
.verdict-card.pass {{ background: #e8f5e9; border-color: #2e7d32; }}
.verdict-card.fail {{ background: #fce4ec; border-color: #c62828; }}
.verdict-card.warn {{ background: #fff8e1; border-color: #f9a825; }}
.verdict-card .vc-title {{ font-size: 14px; font-weight: 700; margin-bottom: 6px; }}
.verdict-card .vc-verdict {{ font-size: 18px; font-weight: 800; }}
.footer {{ text-align: center; color: #888; font-size: 12px; padding: 20px 0 30px; }}
.footer .disclaimer {{ background: #eceff1; padding: 12px; border-radius: 8px; color: #555; margin-bottom: 10px; }}
.mono {{ font-family: Consolas, Monaco, monospace; font-size: 12.5px; background: #f5f5f5; padding: 1px 5px; border-radius: 3px; }}
</style>
</head>
<body>
<div class="container">

<div class="header">
  <h1>进攻线模拟盘 · 阶段0 信号供给端预检报告</h1>
  <div class="subtitle">三候选信号频率验证 · TRE状态分布 · R-04闸门压制 · P12触发统计 · 标的重叠度</div>
  <div class="date">{datetime.now().strftime('%Y-%m-%d %H:%M')} · 依据：TRE状态机 2019-2026.8 全样本回算 + 22只ETF/24只个股日K数据 + G1r/JOINT/P12v6 回测结果</div>
  <div><span class="tag">checklist 0.1~0.4</span><span class="tag">模拟盘启动前置</span><span class="tag">14A频率口径</span></div>
</div>

<!-- ================= 汇总判定 ================= -->
<div class="section">
  <h2>一、汇总判定</h2>
  <div class="verdict-box">
    <div class="verdict-card {'pass' if r01['verdict']=='PASS' else 'fail'}">
      <div class="vc-title">0.1 候选A · ETF均值回归</div>
      <div class="vc-verdict">{icon(r01['verdict'])} {r01['verdict']}</div>
      <div style="font-size:13px;margin-top:4px">年均触发 {r01['avg_s4']:.1f}次 / S4+S3 {r01['avg_s4s3']:.1f}次（门槛≥8）</div>
    </div>
    <div class="verdict-card {'pass' if r02['verdict']=='PASS' else 'fail'}">
      <div class="vc-title">0.2 候选B · 个股精选</div>
      <div class="vc-verdict">{icon(r02['verdict'])} {r02['verdict']}</div>
      <div style="font-size:13px;margin-top:4px">vol20≥15占比{r02['avg_pct_in_15_20']+r02['avg_pct_above_20']:.1f}% / 15-20正常区{r02['avg_pct_in_15_20']:.1f}%</div>
    </div>
    <div class="verdict-card warn">
      <div class="vc-title">0.3 候选C · P12引擎</div>
      <div class="vc-verdict">{icon(r03['verdict'])} {r03['verdict']}</div>
      <div style="font-size:13px;margin-top:4px">年触发0.4次（门槛≥1） / 利润贡献153%</div>
    </div>
    <div class="verdict-card pass">
      <div class="vc-title">0.4 重叠度检查</div>
      <div class="vc-verdict">{icon(r04['verdict'])} {r04['verdict']}</div>
      <div style="font-size:13px;margin-top:4px">A∩B=0 / B∩主引擎=3只 / 裁决规则明确</div>
    </div>
  </div>
  <div class="callout {'callout-red' if not data['all_pass'] else 'callout-green'}">
    <b>总判定：{'阶段0通过 → 可进入阶段1' if data['all_pass'] else '部分未通过 → 需复核调整后进入阶段1'}</b><br>
    {'三候选信号供给充足，可启动历史定参回测。' if data['all_pass'] else '候选A频率不足（S4窗口集中在2019-2022，2023-2024零触发）→ 需调整参数；候选B vol20≥20占比96%但vol20≥15仍可建仓（99.6%时间窗口）；候选C年触发0.4次偏低但利润贡献153%→保留为叠加层而非独立策略。'}
  </div>
</div>

<!-- ================= 0.1 候选A ================= -->
<div class="section">
  <h2>二、0.1 候选A：ETF均值回归 S4 超跌信号触发频率</h2>
  <h3>TRE 状态分布（2019-2026.8，共{sum(tre_dist.values())}交易日）</h3>
  <table>
    <tr><th>状态</th><th>日数</th><th>占比</th><th>说明</th></tr>
    <tr><td><b>S1 强趋势</b></td><td>{tre_dist.get('S1',0)}</td><td>{tre_dist.get('S1',0)/sum(tre_dist.values())*100:.1f}%</td><td>≥2核心指数ADX≥20 + 穿越≤3 + 波动率<18%</td></tr>
    <tr><td><b>S2 震荡</b></td><td>{tre_dist.get('S2',0)}</td><td>{tre_dist.get('S2',0)/sum(tre_dist.values())*100:.1f}%</td><td>ADX 15-20 或接近S1但未满足完整条件</td></tr>
    <tr><td><b>S3 弱平衡</b></td><td>{tre_dist.get('S3',0)}</td><td>{tre_dist.get('S3',0)/sum(tre_dist.values())*100:.1f}%</td><td>多数指数ADX<15 + 穿越3-4 + 波动率15-25%</td></tr>
    <tr><td><b>S4 风暴</b></td><td>{tre_dist.get('S4',0)}</td><td>{tre_dist.get('S4',0)/sum(tre_dist.values())*100:.1f}%</td><td>多数指数ADX<15 + 穿越≥5 或 波动率>25%</td></tr>
  </table>
  <div id="chart_tre" class="chart"></div>
  <h3>S4+S3 日数分年统计</h3>
  <table>
    <tr><th>年份</th><th>S4日数</th><th>S3日数</th><th>S4+S3</th><th>总交易日</th><th>A1触发(S4)</th><th>A3触发(S4+S3)</th><th>达标≥8</th></tr>
"""
for yr in sorted(annual.keys()):
    a = annual[yr]
    ok = "✅" if a["s4"] >= 8 or a["s4s3"] >= 8 else "❌"
    html += f"""    <tr><td>{yr}</td><td>{a.get('s4_days', a.get('s4',0))}</td><td>{a.get('s3_days', '-')}</td><td>{a.get('s4s3_days', '-')}</td><td>{a.get('total_days', '-')}</td><td>{a['s4']}</td><td>{a['s4s3']}</td><td>{ok}</td></tr>
"""

html += f"""  </table>
  <div class="callout callout-red">
    <b>核心发现</b>：S4窗口高度集中在2019-2022年（52+84+48+66=250日，占S4总日数的81%），2023-2024年S4日数为<span class="hl">零</span>。<br>
    A1主变体年均触发<b> {r01['avg_s4']:.1f}次</b>（门槛8次），2023/2024年零触发。A3变体（S4+S3）年均<b> {r01['avg_s4s3']:.1f}次</b>，仍不达标。<br>
    <b>根因</b>：2023-2024年市场处于S2震荡期（占比约60%），既非强趋势（S1）也非风暴（S4），均值回归信号无触发环境。<br>
    <b>调整方案</b>：① 将入场环境从仅S4扩展至S2+低ADX（ADX<18的S2日）；② 降低超跌门槛从4%到3%（A2变体）；③ 增加RSI<35辅助条件（A2变体已有）
  </div>
</div>

<!-- ================= 0.2 候选B ================= -->
<div class="section">
  <h2>三、0.2 候选B：观察池24只 vol20分布与R-04闸门压制</h2>
  <div id="chart_vol20" class="chart" style="height:420px"></div>
  <h3>R-04 闸门对建仓频率的压制</h3>
  <table>
    <tr><th>闸门条件</th><th>占比</th><th>含义</th><th>影响</th></tr>
    <tr><td>vol20 < 15%</td><td>{r02['avg_pct_below_15']:.1f}%</td><td>闸门A：禁一切建仓</td><td>极低，几乎不影响</td></tr>
    <tr><td>vol20 ∈ [15, 20)</td><td>{r02['avg_pct_in_15_20']:.1f}%</td><td>正常区间：S1/S2常规建仓可用</td><td class="hl">极低！仅3%时间可常规建仓</td></tr>
    <tr><td>vol20 ≥ 20%</td><td>{r02['avg_pct_above_20']:.1f}%</td><td>闸门B：禁S1/S2常规建仓</td><td class="hl">极高！96.5%时间被压制</td></tr>
  </table>
  <div class="callout callout-red">
    <b>核心发现</b>：观察池24只个股<b>23只（96%）</b>最新vol20≥20%，被R-04闸门B压制。近250日平均仅<b>3.1%</b>时间落入15-20%正常区间。<br>
    唯一例外：<b>威海广泰(002111)</b> vol20=17.7%，是当前唯一可常规建仓的标的。<br>
    <b>根因</b>：观察池选股偏向高Beta成长股（半导体/新能源/医药），天然高波动。R-04闸门设计初衷是保护主引擎（60-70%仓位），但对进攻线（10%仓位）过于保守。<br>
    <b>调整方案</b>：① B3变体（vol20≥12）几乎无改善（仅0.4%时间<15）；② 需新增B4变体：进攻线专用闸门，vol20≥25或30才禁（因进攻线仅10%资金，风险承受更高）；③ 或完全放弃vol20闸门，改用绝对止损（-5%）控制风险
  </div>
</div>

<!-- ================= 0.3 候选C ================= -->
<div class="section">
  <h2>四、0.3 候选C：P12 移动止盈引擎理论触发统计</h2>
  <table>
    <tr><th>配置</th><th>总平仓</th><th>P12触发</th><th>P12占比</th><th>P12盈亏</th><th>总交易PnL</th><th>P12利润占比</th></tr>
"""
for label, v in r03["variants"].items():
    html += f"""    <tr><td><b>{label}</b></td><td>{v['total_trades']}</td><td>{v['p12_count']}</td><td>{v['p12_share']:.1f}%</td><td class="ok">{v['p12_pnl']:+,.0f}</td><td>{v['total_pnl']:+,.0f}</td><td class="ok">{v['p12_pnl_share']:.0f}%</td></tr>
"""

html += f"""  </table>
  <div class="callout">
    <b>核心发现</b>：P12年触发仅<b>0.4次/年</b>（3笔/7.5年），远低于1次/年门槛。但P12是<b>唯一盈利出场引擎</b>，3笔贡献了总交易PnL的<b>153%</b>（即其他出场合计为负53%）。<br>
    P12出场浮盈分布：21%/25%/28%——均远超15%门槛，说明<b>瓶颈不在门槛而在浮盈≥15%的持仓数量</b>（P12v6扩大化回测已证实：降低门槛无效，收紧回撤有效）。<br>
    <b>裁决</b>：候选C不应作为独立策略（频率太低），应作为<b>叠加层</b>——在候选A/B入场后自动应用P12v6退出管理，替代E-P1噪音止损。
  </div>
</div>

<!-- ================= 0.4 重叠度 ================= -->
<div class="section">
  <h2>五、0.4 三候选标的重叠度与裁决规则</h2>
  <table>
    <tr><th>检查项</th><th>结果</th><th>影响</th></tr>
    <tr><td>A∩B（ETF vs 个股）</td><td class="ok">0只重叠</td><td>天然隔离，无冲突</td></tr>
    <tr><td>B∩主引擎个股</td><td>3只（600276/603259/300750）</td><td>底盘优先，进攻线让位</td></tr>
    <tr><td>A∩主引擎ETF</td><td>22/22全部重叠</td><td>入场逻辑不同（S4超跌 vs S1趋势），时间天然错开</td></tr>
  </table>
  <h3>资金优先级裁决规则（5条）</h3>
  <ol>
"""
for rule in r04["rules"]:
    html += f"    <li>{rule}</li>\n"
html += f"""  </ol>
</div>

<!-- ================= 阶段1参数定稿建议 ================= -->
<div class="section">
  <h2>六、阶段1 历史定参回测参数定稿建议</h2>
  <p>基于阶段0预检结果，对三候选的阶段1回测参数做如下调整：</p>
  <h3>候选A · ETF均值回归（参数修正）</h3>
  <table>
    <tr><th>参数</th><th>A1原版</th><th>A1-修正版（推荐）</th><th>A3宽松版</th><th>修正理由</th></tr>
    <tr><td>触发环境</td><td>S4仅</td><td><b>S4 + S3 + 低ADX S2</b></td><td>S4+S3</td><td>2023-2024 S4为零，需扩展窗口</td></tr>
    <tr><td>超跌门槛</td><td>close≤MA20×0.96</td><td><b>close≤MA20×0.97</b></td><td>close≤MA20×0.95</td><td>4%太严→3%增加触发</td></tr>
    <tr><td>vol20范围</td><td>[15,25]</td><td>[15,30]</td><td>[12,35]</td><td>放宽上限适配高波动</td></tr>
    <tr><td>其余</td><td colspan="3">保持不变：5%仓位 / 最多3只 / -5%止损 / 20日上限 / 回归MA20或+3%止盈</td><td></td></tr>
  </table>
  <h3>候选B · 个股精选（参数修正）</h3>
  <table>
    <tr><th>参数</th><th>B1原版</th><th>B1-修正版（推荐）</th><th>B3高频版</th><th>修正理由</th></tr>
    <tr><td>评分门槛</td><td>≥80</td><td>≥80</td><td>≥75</td><td>保持（不改评分改闸门）</td></tr>
    <tr><td>vol20闸门</td><td>≥15（R-04A）</td><td><b>≥15建仓 / ≥30禁</b></td><td>≥12</td><td>进攻线10%资金可承受更高波动</td></tr>
    <tr><td>单笔仓位</td><td>10%进攻线</td><td>10%</td><td>8%</td><td>不变</td></tr>
    <tr><td>止损</td><td>P1分档5%/3%</td><td>P1分档5%/3%</td><td>同左</td><td>不变</td></tr>
    <tr><td>止盈</td><td>P12移动止盈</td><td><b>P12v6（45/35/25%）</b></td><td>P12v6</td><td>用最新固化版本</td></tr>
  </table>
  <h3>候选C · P12引擎（定位调整）</h3>
  <table>
    <tr><th>参数</th><th>C1原版</th><th>C-修正版（推荐）</th><th>修正理由</th></tr>
    <tr><td>定位</td><td>独立策略</td><td><b>叠加层（非独立）</b></td><td>年触发0.4次无法独立成立</td></tr>
    <tr><td>入场</td><td>复用B1</td><td><b>复用A/B入场</b></td><td>作为A/B的退出管理器</td></tr>
    <tr><td>P12 tiers</td><td>50/40/30%</td><td><b>45/35/25%（P12v6固化）</b></td><td>已验证最优</td></tr>
    <tr><td>兜底止损</td><td>E-P1 -5%</td><td><b>-5%（保留）</b></td><td>不可去除，但P12优先</td></tr>
  </table>
  <div class="callout callout-blue">
    <b>阶段1回测矩阵（9+3=12个变体）</b>：<br>
    A1-修正 / A2 / A3 × IS+OOS = 6个<br>
    B1-修正 / B2(严格) / B3(高频) × IS+OOS = 6个<br>
    C作为叠加层在A/B最优变体上验证 = 2个<br>
    合计14个回测，预计30分钟内完成
  </div>
</div>

<div class="footer">
  <div class="disclaimer">⚠️ 本报告仅供研究参考，不构成个人投资建议。回测结果基于历史数据与假设，不代表未来表现；模拟盘验证不保证实盘盈利。投资有风险，决策需谨慎。</div>
  <div>进攻线模拟盘 · 阶段0信号供给端预检 · {datetime.now().strftime('%Y-%m-%d')} · 依据 TRE全样本回算 + 22ETF/24个股日K + G1r/JOINT/P12v6回测</div>
</div>

</div>
<script>
// TRE状态分布饼图
var tre = echarts.init(document.getElementById('chart_tre'));
tre.setOption({{
  tooltip: {{ trigger: 'item' }},
  legend: {{ bottom: 0, textStyle: {{ fontSize: 13 }} }},
  series: [{{
    type: 'pie', radius: ['30%', '60%'], center: ['50%', '45%'],
    itemStyle: {{ borderRadius: 6, borderColor: '#fff', borderWidth: 2 }},
    label: {{ fontSize: 13, formatter: '{{b}}\\n{{c}}日 ({{d}}%)' }},
    data: [
      {{ value: {tre_dist.get('S1',0)}, name: 'S1 强趋势', itemStyle: {{ color: '#2e7d32' }} }},
      {{ value: {tre_dist.get('S2',0)}, name: 'S2 震荡', itemStyle: {{ color: '#1a237e' }} }},
      {{ value: {tre_dist.get('S3',0)}, name: 'S3 弱平衡', itemStyle: {{ color: '#f9a825' }} }},
      {{ value: {tre_dist.get('S4',0)}, name: 'S4 风暴', itemStyle: {{ color: '#c62828' }} }}
    ]
  }}]
}});

// vol20分布柱状图
var vol = echarts.init(document.getElementById('chart_vol20'));
var stkCodes = {json.dumps([s['name'] for s in stocks.values()], ensure_ascii=False)};
var stkVol = {json.dumps([s['vol20_latest'] for s in stocks.values()], ensure_ascii=False)};
var stkP50 = {json.dumps([s['vol_p50'] for s in stocks.values()], ensure_ascii=False)};
// 按最新vol20排序
var combined = stkCodes.map((name, i) => ({{ name, vol: stkVol[i], p50: stkP50[i] }}));
combined.sort((a, b) => a.vol - b.vol);
vol.setOption({{
  tooltip: {{ trigger: 'axis', axisPointer: {{ type: 'shadow' }} }},
  legend: {{ bottom: 0, textStyle: {{ fontSize: 12 }} }},
  grid: {{ left: 100, right: 30, top: 20, bottom: 60 }},
  xAxis: {{ type: 'value', name: 'vol20(%)', axisLabel: {{ fontSize: 12 }} }},
  yAxis: {{ type: 'category', inverse: true, data: combined.map(d => d.name), axisLabel: {{ fontSize: 11 }} }},
  series: [
    {{ name: '最新vol20', type: 'bar', barWidth: 12, data: combined.map(d => d.vol.toFixed(1)),
       itemStyle: {{ color: function(v) {{ return v >= 20 ? '#c62828' : (v >= 15 ? '#f9a825' : '#2e7d32'); }} }} }},
    {{ name: 'P50(250日中位)', type: 'bar', barWidth: 12, data: combined.map(d => d.p50.toFixed(1)),
       itemStyle: {{ color: '#90caf9' }} }}
  ]
}});
</script>
</body>
</html>
"""

out_path = os.path.join(OUT, "阶段0_信号供给端预检报告.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"报告已生成: {out_path}")
