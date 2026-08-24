# -*- coding: utf-8 -*-
"""生成 H系列: S1假信号定向修复 对比 HTML 报告（2026-08-18 阶段1归因落地验证）"""
import json, os, sys
from collections import Counter

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "output")
SCRIPTS = os.path.dirname(__file__)
sys.path.insert(0, SCRIPTS)
import run_backtest as RB  # 复用 UNIVERSE 映射（R9UNIV 默认开 = 30只）

UNIV = RB.UNIVERSE if RB.R9_UNIV_ON else {}

def ptype_of(code):
    v = UNIV.get(code)
    return v[2] if v else ("etf_" if str(code).startswith(("5", "1")) else "stock")

def load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as fh:
        return json.load(fh)

LABELS = ["G1r", "H1", "H2", "H3"]
G = {L: load(f"variant_{L}.json") for L in LABELS}
RES = {L: load(f"results_{L}_in.json") for L in LABELS}

def tag(ok):
    return "<span class=\"verdict %s\">%s</span>" % ("v-pass" if ok else "v-fail", "达标" if ok else "未达标")

def fmt(v, suf="%", dec=2, sign=False):
    if v != v:
        return "—"
    body = ("%+." if sign else "%.") + str(dec) + "f"
    return (body % v) + suf

# ---------- 一、核心对比 ----------
def cmp_row(L, name, desc):
    m = G[L]["metrics_in"]
    cls = "pos" if m["avg_pnl_pct"] > 0 else "neg"
    ncls = "pos" if m["ann_return"] > 0 else "neg"
    pnl_amt = sum(float(c.get("pnl", 0)) for c in G[L]["closed_in"])
    row = ("<tr><td><strong>%s</strong></td><td>%s</td><td>%d</td><td>%.1f</td>"
           "<td class=\"%s\">%+.2f%%</td><td class=\"%s\">%.2f%%</td><td>%.2f%%</td><td>%.2f</td>"
           "<td>%.1f%%</td><td>%+.2f%%</td>") % (
        name, desc, m["n_buys"], m["freq_annual"], cls, m["avg_pnl_pct"], ncls, m["ann_return"],
        m["max_drawdown"], m["sharpe"], m["win_rate"], m["excess"])
    return row + "<td>{:+,.0f}</td></tr>".format(pnl_amt)

rows_cmp = "".join([
    cmp_row("G1r", "G1r 基线", "R10完整配置（无S1修复）"),
    cmp_row("H1", "H1", "S1 常规建仓禁 ETF"),
    cmp_row("H2", "H2", "S1 常规建仓强制持有期11日"),
    cmp_row("H3", "H3", "H1+H2 组合"),
])

# ---------- 二、验收判定 ----------
def accept_row(L, name):
    m = G[L]["metrics_in"]
    ok4 = lambda b: "<span class=\"verdict %s\">%s</span>" % ("v-pass" if b else "v-fail", "✓" if b else "✗")
    c1 = m["freq_annual"] >= 6.0
    c2 = (m["avg_pnl_pct"] == m["avg_pnl_pct"]) and m["avg_pnl_pct"] > 0
    c3 = m["ann_return"] >= 6.0
    c4 = m["max_drawdown"] <= 12.0
    allok = all([c1, c2, c3, c4])
    return ("<tr><td><strong>%s</strong></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
            "<td>%s</td></tr>") % (name, ok4(c1), ok4(c2), ok4(c3), ok4(c4),
            "<span class=\"verdict %s\">%s</span>" % ("v-pass" if allok else "v-fail", "全部达标" if allok else "未达标"))

rows_accept = "".join(accept_row(L, L) for L in LABELS)

# ---------- 工具: 匹配平仓 ----------
def nearest_exit(buy, closed):
    cands = [c for c in closed if c["code"] == buy["code"] and str(c["exit"]) > str(buy["date"])]
    if not cands:
        return None
    cands.sort(key=lambda c: str(c["exit"]))
    return cands[0]

def s1_buys(L):
    return [b for b in G[L]["buys_in"] if b.get("reason") == "S1正常建仓"]

def stats_of(buys, closed):
    pnls, amts, holds, reasons = [], [], [], []
    n_exit = 0
    for b in buys:
        ce = nearest_exit(b, closed)
        if ce:
            n_exit += 1
            pnls.append(float(ce["pnl_pct"]) * 100)
            amts.append(float(ce.get("pnl", 0)))
            holds.append(int(ce.get("hold_days", 0)))
            reasons.append(ce.get("exit_reason", ""))
    return {
        "n_buy": len(buys), "n_exit": n_exit,
        "exp": (sum(pnls) / n_exit if n_exit else float("nan")),
        "amt": sum(amts),
        "wr": (sum(1 for p in pnls if p > 0) / n_exit * 100 if n_exit else float("nan")),
        "avg_hold": (sum(holds) / n_exit if n_exit else float("nan")),
        "reasons": Counter(reasons),
    }

def s1_row(L, name):
    d = stats_of(s1_buys(L), G[L]["closed_in"])
    cls = "pos" if d["exp"] > 0 else "neg"
    row = ("<tr><td><strong>%s</strong></td><td>%d</td><td>%d</td><td class=\"%s\">%s</td>"
           "<td>%s</td><td>%.1f%%</td><td>%.1f日</td><td>%s</td></tr>") % (
        name, d["n_buy"], d["n_exit"], cls, fmt(d["exp"], "%", 2, True),
        "{:+,.0f}".format(d["amt"]), d["wr"], d["avg_hold"],
        "、".join("%s×%d" % (k.replace("-技术止损", ""), v) for k, v in d["reasons"].most_common(3)))
    return row

rows_s1 = "".join(s1_row(L, L) for L in LABELS)

# ---------- 三、H1 拦截明细（G1r 中被禁的 S1+ETF 单） ----------
h1_blocked = [b for b in s1_buys("G1r") if ptype_of(b["code"]) != "stock"]
rows_h1 = []
for b in sorted(h1_blocked, key=lambda x: x["date"]):
    ce = nearest_exit(b, G["G1r"]["closed_in"])
    pnl_s = fmt(float(ce["pnl_pct"]) * 100, "%", 2, True) if ce else "未平仓"
    hold_s = ("%d日" % ce["hold_days"]) if ce else "—"
    rows_h1.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%.0f</td><td>%.1f%%</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                   % (b["date"], b["code"], UNIV.get(b["code"], (None, b["code"], None, None))[1], b["score"],
                      b["target"], pnl_s, hold_s, ce["exit_reason"] if ce else "—"))
rows_h1_html = "".join(rows_h1) if rows_h1 else "<tr><td colspan='8' style='color:#999'>G1r 中无 S1+ETF 建仓</td></tr>"
h1_stat = stats_of(h1_blocked, G["G1r"]["closed_in"])

# ---------- 四、H2 持有期效果（同一批 S1 单: G1r vs H2 的持有期/盈亏变化） ----------
g1_s1 = {b["date"] + b["code"]: b for b in s1_buys("G1r")}
h2_s1 = {b["date"] + b["code"]: b for b in s1_buys("H2")}
common = sorted(set(g1_s1) & set(h2_s1))
rows_h2 = []
for k in common:
    b1, b2 = g1_s1[k], h2_s1[k]
    c1 = nearest_exit(b1, G["G1r"]["closed_in"])
    c2 = nearest_exit(b2, G["H2"]["closed_in"])
    if not c1 or not c2:
        continue
    p1 = float(c1["pnl_pct"]) * 100
    p2 = float(c2["pnl_pct"]) * 100
    cls = "pos" if p2 > p1 else "neg"
    delta = p2 - p1
    d_hold = c2["hold_days"] - c1["hold_days"]
    rows_h2.append("<tr><td>%s</td><td>%s</td><td>%d日→%d日</td><td class=\"%s\">%+d日</td>"
                   "<td>%s→%s</td><td>%+.2f%%→%+.2f%%</td><td class=\"%s\">%+.2f%%</td></tr>"
                   % (b1["date"], b1["code"], c1["hold_days"], c2["hold_days"],
                      "pos" if d_hold >= 0 else "neg", d_hold,
                      c1["exit_reason"].replace("-技术止损", ""), c2["exit_reason"].replace("-技术止损", ""),
                      p1, p2, cls, delta))
rows_h2_html = "".join(rows_h2) if rows_h2 else "<tr><td colspan='7' style='color:#999'>G1r 与 H2 无共同 S1 单</td></tr>"
h2_improve = sum(1 for k in common if (lambda c1, c2: c1 and c2 and float(c2["pnl_pct"]) > float(c1["pnl_pct"]))(
    nearest_exit(g1_s1[k], G["G1r"]["closed_in"]), nearest_exit(h2_s1[k], G["H2"]["closed_in"])))

# ---------- 五、净值曲线 ----------
eq_data = {}
for L in LABELS:
    hist = RES[L]["hist"]
    eq_data[L] = {
        "dates": [h["date"] for h in hist],
        "equity": [round(float(h["equity"]) / 10000, 2) for h in hist],
    }

# ---------- 六、年度建仓 ----------
def yearly(L):
    cnt = Counter(b["date"][:4] for b in G[L]["buys_in"])
    return [cnt.get(str(y), 0) for y in range(2019, 2025)]

years = list(range(2019, 2025))
by_y = {L: yearly(L) for L in LABELS}

# ---------- 七、样本外 ----------
def oos_row(L, name):
    m = G[L]["metrics_oos"]
    cls = "pos" if m["avg_pnl_pct"] > 0 else "neg"
    return ("<tr><td><strong>%s</strong></td><td>%d</td><td>%.1f</td><td class=\"%s\">%+.2f%%</td>"
            "<td>%.2f%%</td><td>%.2f%%</td><td>%.1f%%</td></tr>") % (
        name, m["n_buys"], m["freq_annual"], cls, m["avg_pnl_pct"],
        m["ann_return"], m["max_drawdown"], m["win_rate"])

rows_oos = "".join(oos_row(L, L) for L in LABELS)

# ---------- 八、拦截统计 ----------
def intc_top(L, n=5):
    st = G[L]["stats_in"]["intercept"]
    return "、".join("%s=%d" % (k, v) for k, v in sorted(st.items(), key=lambda x: -x[1])[:n])

# ---------- 结论 ----------
m0, m1, m2, m3 = (G[L]["metrics_in"] for L in LABELS)
s1_g1 = stats_of(s1_buys("G1r"), G["G1r"]["closed_in"])
s1_h1 = stats_of(s1_buys("H1"), G["H1"]["closed_in"])
s1_h2 = stats_of(s1_buys("H2"), G["H2"]["closed_in"])
s1_h3 = stats_of(s1_buys("H3"), G["H3"]["closed_in"])

verdict_best = max(LABELS, key=lambda L: G[L]["metrics_in"]["avg_pnl_pct"])
verdict = (
    f"最佳变体 = {verdict_best}（期望 {G[verdict_best]['metrics_in']['avg_pnl_pct']:+.2f}%）"
    f"｜S1单期望: G1r {s1_g1['exp']:+.2f}% → H3 {s1_h3['exp']:+.2f}%"
)
all_pass = all(G[L]["metrics_in"]["ann_return"] >= 6.0 for L in LABELS)
verdict_txt = ("❌ 全部变体年化未达 6%（信号端修复改善单笔质量, 但交易贡献仍不足以独立达标）"
               if not all_pass else "✅ 存在达标变体")

html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>H系列对比：S1假信号定向修复（阶段1归因落地）</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, "Microsoft YaHei", "PingFang SC", sans-serif; background: #f5f5f5; color: #1a1a1a; line-height: 1.7; }
.container { max-width: 1100px; margin: 0 auto; padding: 20px; }
.header { background: linear-gradient(135deg, #1a237e, #283593); color: white; padding: 30px 40px; border-radius: 12px; margin-bottom: 24px; }
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
.verdict { display: inline-block; padding: 2px 10px; border-radius: 4px; font-size: 12px; font-weight: 600; }
.v-fail { background: #ffcdd2; color: #b71c1c; }
.v-warn { background: #fff9c4; color: #f57f17; }
.v-pass { background: #c8e6c9; color: #1b5e20; }
.footer { text-align: center; padding: 20px; color: #999; font-size: 12px; }
</style>
</head>
<body>
<div class="container">

<div class="header">
<h1>H系列对比：S1假信号定向修复</h1>
<div class="subtitle">阶段1归因落地（2026-08-18）| G1r 基线 + H1/H2/H3 | 样本内 2019-2024 / 样本外 2025-2026H1</div>
<div class="date">引擎: run_backtest.py（新增 BT_H1_S1NOETF / BT_H2_MINHOLD 开关）+ engine.py（H2 最短持有期豁免E-P1）| 基准: 沪深300 | 初始资金 100万</div>
</div>

<div class="section">
<h2>一、H系列配置口径</h2>
<table>
<tr><th>变体</th><th>改动（相对 G1r 基线）</th><th>设计依据</th></tr>
<tr><td><strong>G1r</strong></td><td>R10完整配置（VOLGATE/S1CONFIRM/EP1TENOR/R10GATES/R9UNIV 全开），无S1修复</td><td>阶段1对照基准（16笔/+0.27%）</td></tr>
<tr><td><strong>H1</strong></td><td>S1 常规建仓禁 ETF（观察通道/S3 试探仓不受影响）</td><td>归因⑥: ETF亏/个股盈；S1追涨ETF被均值回归打穿</td></tr>
<tr><td><strong>H2</strong></td><td>S1 常规建仓强制最短持有期11日（期间跳过 P1/E-P1；E-P9时间止损/P4回撤/P12移动止损/熔断仍生效）</td><td>归因③: ≤5日-2.83% vs >30日+5.90%；打破E-P1快速打穿循环, 激活P12盈利引擎</td></tr>
<tr><td><strong>H3</strong></td><td>H1+H2 组合</td><td>双引擎效应最大化（压亏损引擎 + 放大盈利引擎）</td></tr>
</table>
<div class="callout"><strong>设计红线（吸取 E2r 降档证伪教训）</strong>：H系列是"定向限制"而非"放松"——H1 禁掉一类建仓、H2 拉长持有期（用 E-P9 时间止损兜底），均不新增任何建仓权限；S4 风暴期/R-04 闸门照常全禁。目标不是提高频率，而是<strong>提升 S1 单（亏损核心）的期望质量</strong>。</div>
</div>

<div class="section">
<h2>二、核心指标对比（样本内 6年）</h2>
<table>
<tr><th>配置</th><th>修复</th><th>建仓笔数</th><th>年建仓</th><th>单笔期望</th><th>年化收益</th><th>最大回撤</th><th>夏普</th><th>胜率</th><th>超额收益</th><th>交易净PnL(元)</th></tr>
@@ROWS_CMP@@
</table>
</div>

<div class="section">
<h2>三、14A 验收判定（样本内）</h2>
<table>
<tr><th>配置</th><th>年建仓≥6笔</th><th>单笔期望&gt;0</th><th>年化≥6%</th><th>回撤≤12%</th><th>结论</th></tr>
@@ROWS_ACCEPT@@
</table>
<div class="callout callout-red"><strong>总判定：@@VERDICT@@</strong><br>
@@VERDICT_DETAIL@@</div>
</div>

<div class="section">
<h2>四、S1 单专项对比（核心证据）</h2>
<table>
<tr><th>配置</th><th>S1建仓笔数</th><th>已平仓</th><th>S1单期望</th><th>S1净PnL(元)</th><th>胜率</th><th>平均持有</th><th>主要退出原因</th></tr>
@@ROWS_S1@@
</table>
<div class="callout">R10 六维归因：S1 强趋势追涨是亏损核心（9笔期望-2.94%，亏损占全部108%）。H系列的目标正是把 S1 单的期望从负转正或显著抬升。<strong>S1 单期望变化 = H系列有效性的第一判据。</strong></div>
</div>

<div class="section">
<h2>五、H1 拦截明细（G1r 中被禁的 S1+ETF 建仓）</h2>
<table>
<tr><th>日期</th><th>代码</th><th>名称</th><th>得分</th><th>目标仓位</th><th>G1r周期盈亏</th><th>持有天数</th><th>退出原因</th></tr>
@@ROWS_H1@@
</table>
<div class="callout">以上 @@H1_N@@ 笔为 G1r 中 S1 状态下的 ETF 建仓，H1 将其全部拦截。若其 G1r 实际盈亏期望为负，说明 H1 恰好"禁掉了亏损单"——定向限制有效性的直接证据。</div>
</div>

<div class="section">
<h2>六、H2 持有期效果（同一批 S1 单逐笔对比: G1r → H2）</h2>
<table>
<tr><th>日期</th><th>代码</th><th>持有天数(G1r→H2)</th><th>持有期变化</th><th>退出原因(G1r→H2)</th><th>周期盈亏(G1r→H2)</th><th>Δ盈亏</th></tr>
@@ROWS_H2@@
</table>
<div class="callout">G1r 与 H2 共 @@H2_N@@ 笔相同 S1 建仓，其中 @@H2_IMP@@ 笔在 H2 中盈亏改善。逐笔对比可直接观察"强制持有期"是否让 E-P1 噪音止损的亏损单延后/转为 P12 止盈。</div>
</div>

<div class="section">
<h2>七、净值曲线（样本内，万元）</h2>
<div id="chartEq" class="chart"></div>
</div>

<div class="section">
<h2>八、年度建仓笔数</h2>
<div id="chartY" class="chart"></div>
</div>

<div class="section">
<h2>九、样本外（2025-2026H1, 18个月）</h2>
<table>
<tr><th>配置</th><th>建仓笔数</th><th>年建仓</th><th>单笔期望</th><th>年化</th><th>最大回撤</th><th>胜率</th></tr>
@@ROWS_OOS@@
</table>
<div class="callout">样本外是过拟合检验的关键：G 系列样本外全面恶化（期望-0.58%~-4.93%）已警示过拟合风险。H 变体若样本外未同步恶化，说明修复方向稳健而非拟合历史。</div>
</div>

<div class="section">
<h2>十、结论与建议</h2>
<ul>
<li>@@CONCL1@@</li>
<li>@@CONCL2@@</li>
<li>@@CONCL3@@</li>
</ul>
<div class="callout callout-red"><strong>H系列判定：@@VERDICT@@</strong><br>
信号端修复的价值边界 = 单笔期望/净PnL 质量提升 vs 年化缺口（交易贡献占比仍低）。若 H3 使 S1 单期望显著转正且交易净PnL改善，具备 F-35 裁决（S1定向限制固化）立项条件；年化 6% 的最后一棒仍需仓位引擎（F-04 单笔金额贡献）重构承接。</div>
</div>

<div class="footer">中线趋势共振策略 v4.7-R10 · H系列 S1假信号定向修复对比报告 · 2026-08-18</div>
</div>

<script>
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
var chartY = echarts.init(document.getElementById('chartY'));
chartY.setOption({
  tooltip: { trigger: 'axis' },
  legend: { data: @@LEGEND@@, top: 8 },
  grid: { left: 50, right: 20, top: 40, bottom: 30 },
  xAxis: { type: 'category', data: @@YEARS@@ },
  yAxis: { type: 'value', name: '笔', minInterval: 1 },
  series: @@YSERIES@@
});
</script>
</body>
</html>
"""

# ---------- 组装 ----------
s1_exps = {L: stats_of(s1_buys(L), G[L]["closed_in"])["exp"] for L in LABELS}
m_best = max(LABELS, key=lambda L: G[L]["metrics_in"]["avg_pnl_pct"])
m_worst = min(LABELS, key=lambda L: G[L]["metrics_in"]["avg_pnl_pct"])
concl_lines = [
    f"最佳变体 = {m_best}（单笔期望 {G[m_best]['metrics_in']['avg_pnl_pct']:+.2f}%, 交易净PnL {sum(float(c.get('pnl',0)) for c in G[m_best]['closed_in']):+,.0f} 元）vs 基线 G1r（{G['G1r']['metrics_in']['avg_pnl_pct']:+.2f}%, {sum(float(c.get('pnl',0)) for c in G['G1r']['closed_in']):+,.0f} 元）",
    f"S1 单期望变化: G1r {s1_exps['G1r']:+.2f}% → H1 {s1_exps['H1']:+.2f}% / H2 {s1_exps['H2']:+.2f}% / H3 {s1_exps['H3']:+.2f}%（H1 禁掉 S1+ETF 共 {len(h1_blocked)} 笔）",
    f"样本外: 各变体期望 {', '.join(f'{L}={G[L]['metrics_oos']['avg_pnl_pct']:+.2f}%' for L in LABELS)}（过拟合检验）",
]
if h1_stat["n_exit"] > 0:
    concl_lines[1] += f"；被禁单 G1r 实际期望 {h1_stat['exp']:+.2f}%"

colors = {"G1r": "#90a4ae", "H1": "#1565c0", "H2": "#c62828", "H3": "#2e7d32"}
legend = list(LABELS)
eq_series = [{
    "name": L, "type": "line", "showSymbol": False, "data": eq_data[L]["equity"],
    "lineStyle": {"width": 2 if L in ("H3",) else 1.5, "color": colors[L]},
    "itemStyle": {"color": colors[L]},
} for L in LABELS]
y_series = [{
    "name": L, "type": "bar", "data": by_y[L], "itemStyle": {"color": colors[L]},
} for L in LABELS]

path = os.path.join(OUT, "H系列_对比_S1假信号定向修复.html")
repl = {
    "@@ROWS_CMP@@": rows_cmp,
    "@@ROWS_ACCEPT@@": rows_accept,
    "@@ROWS_S1@@": rows_s1,
    "@@ROWS_H1@@": rows_h1_html,
    "@@ROWS_H2@@": rows_h2_html,
    "@@ROWS_OOS@@": rows_oos,
    "@@H1_N@@": str(len(h1_blocked)),
    "@@H2_N@@": str(len(common)),
    "@@H2_IMP@@": str(h2_improve),
    "@@VERDICT@@": verdict_txt,
    "@@VERDICT_DETAIL@@": verdict,
    "@@EQDATA@@": json.dumps(eq_data),
    "@@LEGEND@@": json.dumps(legend),
    "@@EQSERIES@@": json.dumps(eq_series),
    "@@YSERIES@@": json.dumps(y_series),
    "@@YEARS@@": json.dumps(years),
    "@@CONCL1@@": concl_lines[0] if len(concl_lines) > 0 else "",
    "@@CONCL2@@": concl_lines[1] if len(concl_lines) > 1 else "",
    "@@CONCL3@@": concl_lines[2] if len(concl_lines) > 2 else "",
}
for k, v in repl.items():
    assert k in html, "missing token " + k
    html = html.replace(k, v)
with open(path, "w", encoding="utf-8") as fh:
    fh.write(html)
print("written:", path, len(html), "chars")
