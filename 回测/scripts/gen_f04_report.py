# -*- coding: utf-8 -*-
"""生成 F-04 仓位引擎专项验证 HTML 报告（2026-08-18 下一主攻方向）"""
import json, os, sys
from collections import Counter

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "output")
SCRIPTS = os.path.dirname(__file__)
sys.path.insert(0, SCRIPTS)
import run_backtest as RB  # 复用 UNIVERSE 映射

UNIV = RB.UNIVERSE if RB.R9_UNIV_ON else {}

LABELS = ["G1r", "F04a", "F04b", "F04c", "F04d"]
G = {L: json.load(open(os.path.join(OUT, f"variant_{L}.json"), encoding="utf-8")) for L in LABELS}
RES = {L: json.load(open(os.path.join(OUT, f"results_{L}_in.json"), encoding="utf-8")) for L in LABELS}

MULT = {"G1r": "1.0", "F04a": "1.5", "F04b": "2.0", "F04c": "3.0", "F04d": "2.0"}


def fmt(v, suf="%", dec=2, sign=False):
    if v != v:
        return "—"
    body = ("%+." if sign else "%.") + str(dec) + "f"
    return (body % v) + suf


def tag(ok):
    return f'<span class="verdict {"v-pass" if ok else "v-fail"}">{"达标" if ok else "未达标"}</span>'


def chk(b):
    return f'<span class="verdict {"v-pass" if b else "v-fail"}">{"✓" if b else "✗"}</span>'


# ---------- 一、核心对比 ----------
def cmp_row(L):
    m = G[L]["metrics_in"]
    cfg = G[L]["config"]
    pnl = sum(float(c.get("pnl", 0)) for c in G[L]["closed_in"])
    cls = "pos" if m["avg_pnl_pct"] > 0 else "neg"
    ncls = "pos" if m["ann_return"] > 0 else "neg"
    mult = cfg.get("f04_mult", "1.0")
    kc = cfg.get("kelly_cap", "0.25")
    row = ("<tr><td><strong>%s</strong></td><td>%s×</td><td>%s</td><td>%d</td><td>%.1f</td>"
           "<td class=\"%s\">%+.2f%%</td><td class=\"%s\">%.2f%%</td><td>%.2f%%</td><td>%.2f</td>"
           "<td>%.1f%%</td><td>%s</td></tr>") % (
        L, mult, kc, m["n_buys"], m["freq_annual"], cls, m["avg_pnl_pct"], ncls, m["ann_return"],
        m["max_drawdown"], m["sharpe"], m["win_rate"], "{:+,.0f}".format(pnl))
    return row


rows_cmp = "".join(cmp_row(L) for L in LABELS)

# ---------- 二、验收判定 ----------
def accept_row(L):
    m = G[L]["metrics_in"]
    c1 = m["freq_annual"] >= 6.0
    c2 = (m["avg_pnl_pct"] == m["avg_pnl_pct"]) and m["avg_pnl_pct"] > 0
    c3 = m["ann_return"] >= 6.0
    c4 = m["max_drawdown"] <= 12.0
    allok = all([c1, c2, c3, c4])
    return ("<tr><td><strong>%s</strong></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>") % (
        L, chk(c1), chk(c2), chk(c3), chk(c4), tag(allok))


rows_accept = "".join(accept_row(L) for L in LABELS)

# ---------- 三、金额贡献分解（E-P1 vs P12） ----------
def reason_stats(L):
    closed = G[L]["closed_in"]
    ep1 = [c for c in closed if c.get("exit_reason", "").startswith("E-P1")]
    p12 = [c for c in closed if "P12" in c.get("exit_reason", "")]
    other = [c for c in closed if c not in ep1 and c not in p12]
    def agg(lst):
        return (len(lst), sum(float(c.get("pnl", 0)) for c in lst))
    return agg(ep1), agg(p12), agg(other)


def contrib_row(L):
    ep1, p12, oth = reason_stats(L)
    tot = sum(float(c.get("pnl", 0)) for c in G[L]["closed_in"])
    def cell(a):
        return f"<td>{a[0]}笔</td><td>{'{:+,.0f}'.format(a[1])}</td>"
    row = ("<tr><td><strong>%s</strong></td>%s%s%s"
           "<td class=\"%s\">{:+,.0f}</td></tr>").format(tot) % (
        L, cell(ep1), cell(p12), cell(oth), "pos" if tot > 0 else "neg")
    return row


rows_contrib = "".join(contrib_row(L) for L in LABELS)

# ---------- 四、建仓笔数变化（资金占用效应） ----------
def buys_by_reason(L):
    return Counter(b.get("reason", "?") for b in G[L]["buys_in"])


reason_names = ["S1正常建仓", "S2减半建仓", "观察通道试探建仓", "S3有限建仓"]
byr = {L: buys_by_reason(L) for L in LABELS}
n_buys_all = {L: len(G[L]["buys_in"]) for L in LABELS}

# ---------- 五、净值曲线 ----------
eq_data = {}
for L in LABELS:
    hist = RES[L]["hist"]
    eq_data[L] = {
        "dates": [h["date"] for h in hist],
        "equity": [round(float(h["equity"]) / 10000, 2) for h in hist],
    }

# ---------- 六、样本外 ----------
def oos_row(L):
    m = G[L]["metrics_oos"]
    cls = "pos" if m["avg_pnl_pct"] > 0 else "neg"
    pnl = sum(float(c.get("pnl", 0)) for c in G[L]["closed_oos"])
    return ("<tr><td><strong>%s</strong></td><td>%d</td><td>%.1f</td><td class=\"%s\">%+.2f%%</td>"
            "<td>%.2f%%</td><td>%.2f%%</td><td>%.1f%%</td><td>%s</td></tr>") % (
        L, m["n_buys"], m["freq_annual"], cls, m["avg_pnl_pct"],
        m["ann_return"], m["max_drawdown"], m["win_rate"], "{:+,.0f}".format(pnl))


rows_oos = "".join(oos_row(L) for L in LABELS)

# ---------- 七、结论 ----------
m0 = G["G1r"]["metrics_in"]
ma = G["F04a"]["metrics_in"]
pnl0 = sum(float(c.get("pnl", 0)) for c in G["G1r"]["closed_in"])
pnla = sum(float(c.get("pnl", 0)) for c in G["F04a"]["closed_in"])
pnlc = sum(float(c.get("pnl", 0)) for c in G["F04c"]["closed_in"])
GAP = 274602  # 年化6%缺口（G1r基线: 终值141.85万 - 终值114.39万）

best_mult = "F04a(×1.5)"
verdict_txt = "❌ 全部变体年化未达 6% —— F-04 仓位引擎存在有效放大空间(×1.5最优)但无法独立撑起年化缺口"
verdict_detail = (
    f"最优变体 = {best_mult}：交易PnL {'{:+,.0f}'.format(pnla)}元（G1r {'{:+,.0f}'.format(pnl0)}元 → ×{pnla/pnl0:.1f}），"
    f"年化 {ma['ann_return']:.2f}%（G1r {m0['ann_return']:.2f}%），回撤 {ma['max_drawdown']:.2f}%（≤12%可控）"
    f"｜但年化6%缺口 {'{:+,.0f}'.format(GAP)}元仍差 {GAP/pnla:.1f} 倍（仓位引擎数学边界）"
)

concl_lines = [
    f"① 最优倍率拐点 = ×1.5（F04a）：交易PnL +9,679→+23,303元（×2.4），期望 +0.27%→+0.43%，回撤 1.20%→1.81% 仍远低于12%；样本外同步改善（期望 -2.56%→-1.24%、年化 0.92%→3.70%）→ F04a 是稳健的进攻线参数",
    f"② 倍率超调反噬：×2.0/×3.0 时建仓笔数 16→12→10（大仓位占用资金→叠加能力下降），×3.0 期望转负(-0.07%)——金额放大同时放大亏损单(E-P1×8笔)，拐点后每+1%仓位以更多笔数牺牲为代价",
    f"③ 凯利封顶 0.40 零效果（F04d=F04b 逐位一致）：总仓位从未触顶25%——瓶颈在单笔金额而非总仓位上限，放宽凯利无意义",
    f"④ 数学现实坐实：F-04 最优(×1.5)交易贡献 23,303元 vs 年化6%缺口 274,602元 仍差 11.8 倍——仓位引擎是'放大器'不是'发动机'，年化6%最后一棒仍需信号期望(频率)质变或三层资金架构进攻线(模拟盘≥6月)承接",
    f"⑤ 落地建议：F-04 ×1.5 可作三层资金架构进攻线的起始仓位参数（与 ETF均值回归S4观察仓/个股精选/P12引擎组合，模拟盘验证）；防守底盘保持 v4.7-R10 锁死参数不变",
]

# ---------- 组装 ----------
colors = {"G1r": "#90a4ae", "F04a": "#1565c0", "F04b": "#c62828", "F04c": "#2e7d32", "F04d": "#f57f17"}
legend = list(LABELS)
eq_series = [{
    "name": L, "type": "line", "showSymbol": False, "data": eq_data[L]["equity"],
    "lineStyle": {"width": 2.2 if L == "F04a" else 1.5, "color": colors[L]},
    "itemStyle": {"color": colors[L]},
} for L in LABELS]

# 倍率权衡曲线（核心）
mult_axis = [1.0, 1.5, 2.0, 3.0]
curve = {"ann": [], "dd": [], "pnl": []}
for k in mult_axis:
    lab = "G1r" if k == 1.0 else {1.5: "F04a", 2.0: "F04b", 3.0: "F04c"}[k]
    m = G[lab]["metrics_in"]
    pnl = sum(float(c.get("pnl", 0)) for c in G[lab]["closed_in"])
    curve["ann"].append(round(m["ann_return"], 2))
    curve["dd"].append(round(m["max_drawdown"], 2))
    curve["pnl"].append(round(pnl, 0))

# 建仓笔数条形（按 reason 堆叠）
reason_series = []
rcolors = {"S1正常建仓": "#c62828", "S2减半建仓": "#f57f17", "观察通道试探建仓": "#1565c0", "S3有限建仓": "#2e7d32"}
for rn in reason_names:
    reason_series.append({"name": rn, "type": "bar", "stack": "t",
                          "data": [byr[L].get(rn, 0) for L in LABELS], "itemStyle": {"color": rcolors[rn]}})

html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>F-04仓位引擎专项验证：单笔金额贡献边界（2026-08-18）</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, "Microsoft YaHei", "PingFang SC", sans-serif; background: #f5f5f5; color: #1a1a1a; line-height: 1.7; }
.container { max-width: 1100px; margin: 0 auto; padding: 20px; }
.header { background: linear-gradient(135deg, #0d3b66, #1a237e); color: white; padding: 30px 40px; border-radius: 12px; margin-bottom: 24px; }
.header h1 { font-size: 23px; margin-bottom: 8px; }
.header .subtitle { font-size: 14px; opacity: 0.85; }
.header .date { font-size: 12px; opacity: 0.7; margin-top: 6px; }
.section { background: white; border-radius: 10px; padding: 24px 30px; margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.section h2 { font-size: 18px; color: #1a237e; border-left: 4px solid #1a237e; padding-left: 12px; margin-bottom: 16px; }
.section h3 { font-size: 15px; color: #333; margin: 16px 0 10px; }
.section p { margin-bottom: 12px; font-size: 14px; }
.section li { margin-left: 20px; margin-bottom: 6px; font-size: 14px; }
table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 13px; }
th { background: #e8eaf6; color: #1a237e; padding: 8px 10px; text-align: center; font-weight: 600; }
td { padding: 7px 10px; text-align: center; border-bottom: 1px solid #eee; }
tr:hover { background: #f5f5f5; }
.pos { color: #c62828; font-weight: 600; }
.neg { color: #2e7d32; font-weight: 600; }
.chart { width: 100%; height: 380px; margin: 16px 0; }
.callout { background: #fff3e0; border-left: 4px solid #ff9800; padding: 14px 18px; border-radius: 6px; margin: 14px 0; font-size: 14px; }
.callout-red { background: #ffebee; border-left: 4px solid #c62828; }
.callout-green { background: #e8f5e9; border-left: 4px solid #2e7d32; }
.callout-blue { background: #e3f2fd; border-left: 4px solid #1565c0; }
.verdict { display: inline-block; padding: 2px 10px; border-radius: 4px; font-size: 12px; font-weight: 600; }
.v-fail { background: #ffcdd2; color: #b71c1c; }
.v-pass { background: #c8e6c9; color: #1b5e20; }
.footer { text-align: center; padding: 20px; color: #999; font-size: 12px; }
</style>
</head>
<body>
<div class="container">

<div class="header">
<h1>F-04 仓位引擎专项验证：单笔金额贡献的边界</h1>
<div class="subtitle">H系列证伪后的下一主攻方向（2026-08-18）| G1r 基线 + F04a/b/c/d 仓位倍率扫描 | 样本内 2019-2024 / 样本外 2025-2026H1</div>
<div class="date">引擎: run_backtest.py（BT_F04_MULT 金额倍率 + BT_KELLY_CAP 凯利封顶开关）+ engine.py（kelly_cap 参数化）| 基准: 沪深300 | 初始资金 100万</div>
</div>

<div class="section">
<h2>一、验证命题与配置口径</h2>
<table>
<tr><th>配置</th><th>target 金额倍率</th><th>凯利封顶</th><th>设计意图</th></tr>
<tr><td><strong>G1r</strong></td><td>×1.0（基线）</td><td>0.25</td><td>R10完整配置对照（16笔/+0.27%/交易PnL +9,679元）</td></tr>
<tr><td><strong>F04a</strong></td><td>×1.5</td><td>0.25</td><td>单笔金额放大1.5倍（上限12/15%同步放大, 凯利总仓位仍约束叠加）</td></tr>
<tr><td><strong>F04b</strong></td><td>×2.0</td><td>0.25</td><td>单笔金额放大2倍</td></tr>
<tr><td><strong>F04c</strong></td><td>×3.0</td><td>0.25</td><td>激进放大3倍（探测回撤爆点与超调拐点）</td></tr>
<tr><td><strong>F04d</strong></td><td>×2.0</td><td>0.40</td><td>金额+总仓位双放宽（验证凯利封顶是否构成约束）</td></tr>
</table>
<div class="callout"><strong>命题（H系列结论转译）</strong>：G1r 六年交易净PnL 仅 +9,679 元（总收益14.39万中占6.7%），现金管理贡献 93.3%。要年化6%（终值141.85万），缺口 +274,602 元 = 当前交易PnL 的 <strong>28.4 倍</strong>。F-04 验证：<strong>单笔金额放大能否让交易贡献撑起这个缺口？回撤代价多大？</strong>——定位"倍率→年化/回撤"权衡曲线与回撤≤12%的最大可用倍率。</div>
<div class="callout callout-blue"><strong>瓶颈分解（G1r 建仓金额审计）</strong>：16笔中 12笔的 min(9项)=25 分，但 target 均值仅 8.14%——主压制器是 <strong>ATR缩放（标的波动高于沪深300 → atr_scale 0.13~0.48）</strong>，其次 12% 初次上限（仅3笔触顶）、15% 总硬上限（从未生效）。凯利 0.25 总仓位cap 在16笔全程未触顶（单笔target太小叠加不满）。</div>
</div>

<div class="section">
<h2>二、核心指标对比（样本内 6年）</h2>
<table>
<tr><th>配置</th><th>倍率</th><th>凯利</th><th>建仓</th><th>年建仓</th><th>单笔期望</th><th>年化</th><th>最大回撤</th><th>夏普</th><th>胜率</th><th>交易净PnL(元)</th></tr>
@@ROWS_CMP@@
</table>
</div>

<div class="section">
<h2>三、倍率权衡曲线（核心产出）</h2>
<div id="chartCurve" class="chart"></div>
<div class="callout">横轴 = target 金额倍率。左轴 = 年化%/回撤%，右轴 = 交易PnL(元)。<strong>拐点读法</strong>：×1.5 时 PnL 冲到 +23,303（×2.4）且回撤仅 1.81%——最优；×2.0 起建仓笔数骤降（资金占用反噬），PnL 回落；×3.0 期望转负（亏损单放大压过盈利单），回撤 6.77% 但仍 <12%。</div>
</div>

<div class="section">
<h2>四、14A 验收判定（样本内）</h2>
<table>
<tr><th>配置</th><th>年建仓≥6笔</th><th>单笔期望&gt;0</th><th>年化≥6%</th><th>回撤≤12%</th><th>结论</th></tr>
@@ROWS_ACCEPT@@
</table>
<div class="callout callout-red"><strong>总判定：@@VERDICT@@</strong><br>@@VERDICT_DETAIL@@</div>
</div>

<div class="section">
<h2>五、金额贡献分解：E-P1 亏损引擎 vs P12 盈利引擎</h2>
<table>
<tr><th>配置</th><th colspan="2">E-P1噪音止损</th><th colspan="2">P12移动止盈</th><th colspan="2">其它退出</th><th>净PnL</th></tr>
<tr><th></th><th>笔数</th><th>金额</th><th>笔数</th><th>金额</th><th>笔数</th><th>金额</th><th></th></tr>
@@ROWS_CONTRIB@@
</table>
<div class="callout">倍率放大的本质是<strong>同时放大两个引擎</strong>：E-P1 亏损（负引擎）与 P12 盈利（正引擎）。×1.5 时正引擎净增益 > 负引擎放大（净PnL ×2.4）；×3.0 时负引擎放大反超（期望转负）。这解释了最优拐点的存在。</div>
</div>

<div class="section">
<h2>六、建仓笔数结构（资金占用反噬效应）</h2>
<div id="chartBuys" class="chart"></div>
<div class="callout">倍率 1.0→3.0 时总建仓 16→10 笔：大仓位单笔占用资金 → 可叠加建仓能力下降 → 交易机会被"资金挤占"而非信号过滤。这是×2.0+ 后 PnL 不升反降的结构性原因。</div>
</div>

<div class="section">
<h2>七、净值曲线（样本内, 万元）</h2>
<div id="chartEq" class="chart"></div>
</div>

<div class="section">
<h2>八、样本外（2025-2026H1, 18个月）</h2>
<table>
<tr><th>配置</th><th>建仓</th><th>年建仓</th><th>单笔期望</th><th>年化</th><th>最大回撤</th><th>胜率</th><th>交易PnL</th></tr>
@@ROWS_OOS@@
</table>
<div class="callout">F04a 样本外同步改善（期望 -2.56%→-1.24%、年化 0.92%→3.70%）——金额放大方向<strong>样本外稳健</strong>（与H1/H3禁ETF方向一致）。F04c(×3.0) 样本外恶化（-4.87%/-3.00%）——激进倍率在样本外确认不可行。</div>
</div>

<div class="section">
<h2>九、结论与建议</h2>
<ul>
<li>@@CONCL1@@</li>
<li>@@CONCL2@@</li>
<li>@@CONCL3@@</li>
<li>@@CONCL4@@</li>
<li>@@CONCL5@@</li>
</ul>
<div class="callout callout-green"><strong>F-04 落地裁决建议</strong>：F04a(×1.5) 固化为进攻线起始仓位参数（与三层资金架构的模拟盘组合验证）；不执行 ×2.0+（建仓反噬）与凯利放宽（零效果）。仓位引擎定位 = <strong>"放大器"而非"发动机"</strong>——年化6%缺口的剩余 11.8 倍必须由信号期望质变或进攻线新策略贡献。</div>
</div>

<div class="footer">中线趋势共振策略 v4.7-R10 · F-04 仓位引擎专项验证报告 · 2026-08-18</div>
</div>

<script>
var curve = @@CURVE@@;
var chartCurve = echarts.init(document.getElementById('chartCurve'));
chartCurve.setOption({
  tooltip: { trigger: 'axis' },
  legend: { data: ['年化%', '回撤%', '交易PnL(元)'], top: 8 },
  grid: { left: 70, right: 70, top: 40, bottom: 40 },
  xAxis: { type: 'category', data: curve.labels },
  yAxis: [
    { type: 'value', name: '%', scale: true },
    { type: 'value', name: '元', scale: true }
  ],
  series: [
    { name: '年化%', type: 'line', data: curve.ann, smooth: true, lineStyle: { width: 3, color: '#1565c0' }, itemStyle: { color: '#1565c0' } },
    { name: '回撤%', type: 'line', data: curve.dd, smooth: true, lineStyle: { width: 3, color: '#c62828', type: 'dashed' }, itemStyle: { color: '#c62828' } },
    { name: '交易PnL(元)', type: 'bar', yAxisIndex: 1, data: curve.pnl, itemStyle: { color: 'rgba(46,125,50,0.55)' } }
  ]
});
var eq = @@EQDATA@@;
var chartEq = echarts.init(document.getElementById('chartEq'));
chartEq.setOption({
  tooltip: { trigger: 'axis' },
  legend: { data: @@LEGEND@@, top: 8 },
  grid: { left: 60, right: 20, top: 40, bottom: 40 },
  xAxis: { type: 'category', data: eq["G1r"].dates, axisLabel: { show: false } },
  yAxis: { type: 'value', name: '万元', scale: true },
  series: @@EQSERIES@@
});
var chartBuys = echarts.init(document.getElementById('chartBuys'));
chartBuys.setOption({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  legend: { data: @@BUYLEGEND@@, top: 8 },
  grid: { left: 50, right: 20, top: 40, bottom: 30 },
  xAxis: { type: 'category', data: @@BUYLABELS@@ },
  yAxis: { type: 'value', name: '笔', minInterval: 1 },
  series: @@BUYSERIES@@
});
</script>
</body>
</html>
"""

path = os.path.join(OUT, "F04_仓位引擎专项验证_金额贡献边界.html")
repl = {
    "@@ROWS_CMP@@": rows_cmp,
    "@@ROWS_ACCEPT@@": rows_accept,
    "@@ROWS_CONTRIB@@": rows_contrib,
    "@@ROWS_OOS@@": rows_oos,
    "@@VERDICT@@": verdict_txt,
    "@@VERDICT_DETAIL@@": verdict_detail,
    "@@CURVE@@": json.dumps({"labels": [f"×{k}" for k in mult_axis], "ann": curve["ann"], "dd": curve["dd"], "pnl": curve["pnl"]}),
    "@@EQDATA@@": json.dumps(eq_data),
    "@@LEGEND@@": json.dumps(legend),
    "@@EQSERIES@@": json.dumps(eq_series),
    "@@BUYLABELS@@": json.dumps(LABELS),
    "@@BUYLEGEND@@": json.dumps(reason_names),
    "@@BUYSERIES@@": json.dumps(reason_series),
    "@@CONCL1@@": concl_lines[0],
    "@@CONCL2@@": concl_lines[1],
    "@@CONCL3@@": concl_lines[2],
    "@@CONCL4@@": concl_lines[3],
    "@@CONCL5@@": concl_lines[4],
}
for k, v in repl.items():
    assert k in html, "missing token " + k
    html = html.replace(k, v)
with open(path, "w", encoding="utf-8") as fh:
    fh.write(html)
print("written:", path, len(html), "chars")
