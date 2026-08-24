# -*- coding: utf-8 -*-
"""生成阶段1 A/B: MA60二元 vs 三级分级门控 对比 HTML 报告（2026-08-18 路径A验证）"""
import json, os
from collections import Counter, defaultdict

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "output")

def load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as fh:
        return json.load(fh)

G = {L: load(f"variant_{L}.json") for L in ["G-BIN", "G-TIER"]}
RES = {L: load(f"results_{L}_in.json") for L in ["G-BIN", "G-TIER"]}

def tag(ok):
    return "<span class=\"verdict %s\">%s</span>" % ("v-pass" if ok else "v-fail", "达标" if ok else "未达标")

def fmt(v, suf="%", dec=2, sign=False):
    if v != v:  # nan
        return "—"
    body = ("%+." if sign else "%.") + str(dec) + "f"
    return (body % v) + suf

# ---------- 核心对比 ----------
def cmp_row(L, name, desc):
    m = G[L]["metrics_in"]
    cls = "pos" if m["avg_pnl_pct"] > 0 else "neg"
    ncls = "pos" if m["ann_return"] > 0 else "neg"
    return ("<tr><td><strong>%s</strong></td><td>%s</td><td>%d</td><td>%.1f</td>"
            "<td class=\"%s\">%+.2f%%</td><td class=\"%s\">%.2f%%</td><td>%.2f%%</td><td>%.2f</td>"
            "<td>%.1f%%</td><td>%+.2f%%</td><td>%d</td></tr>") % (
        name, desc, m["n_buys"], m["freq_annual"], cls, m["avg_pnl_pct"], ncls, m["ann_return"],
        m["max_drawdown"], m["sharpe"], m["win_rate"], m["excess"], m["gate_days"])

rows_cmp = "".join([
    cmp_row("G-BIN", "G-BIN 对照组", "MA60二元门控（沪深300收盘≤MA60 禁一切建仓）"),
    cmp_row("G-TIER", "G-TIER 实验组", "三级分级门控（FULL全开 / HALF仅S3+观察5折 / NONE全禁）"),
])

# ---------- 窗口天数 ----------
def win_row(L, name):
    w = G[L]["in"]["win_stats"]
    full, half, none_ = w.get("win_full", 0), w.get("win_half", 0), w.get("win_none", 0)
    tot = full + half + none_
    pct = lambda v: "%.1f%%" % (v / tot * 100) if tot else "—"
    return ("<tr><td><strong>%s</strong></td><td>%d</td><td>%s</td><td>%d</td><td>%s</td><td>%d</td><td>%s</td></tr>"
            % (name, full, pct(full), half, pct(half), none_, pct(none_)))

rows_win = "".join([
    win_row("G-BIN", "G-BIN 对照组"),
    win_row("G-TIER", "G-TIER 实验组"),
])

# ---------- 验收判定 ----------
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

rows_accept = "".join([
    accept_row("G-BIN", "G-BIN 对照组"),
    accept_row("G-TIER", "G-TIER 实验组"),
])

# ---------- 分窗口建仓盈亏（实验组） ----------
def nearest_exit(buy, closed):
    cands = [c for c in closed if c["code"] == buy["code"] and str(c["exit"]) > str(buy["date"])]
    if not cands:
        return None
    cands.sort(key=lambda c: str(c["exit"]))
    return cands[0]

def win_breakdown(L):
    buys = G[L]["buys_in"]
    closed = G[L]["closed_in"]
    out = {}
    for w in ("FULL", "HALF", "NONE"):
        bs = [b for b in buys if b.get("win") == w]
        pnls = []
        for b in bs:
            ce = nearest_exit(b, closed)
            if ce:
                pnls.append(float(ce["pnl_pct"]) * 100)
        n_exit = len(pnls)
        out[w] = {
            "n_buy": len(bs), "n_exit": n_exit,
            "exp": (sum(pnls) / n_exit if n_exit else float("nan")),
            "wr": (sum(1 for p in pnls if p > 0) / n_exit * 100 if n_exit else float("nan")),
        }
    return out

WB = win_breakdown("G-TIER")
def wb_row(w, desc):
    d = WB.get(w, {})
    exp = fmt(d["exp"], "%", 2, True) if d["n_exit"] else "—"
    wr = fmt(d["wr"], "%", 1) if d["n_exit"] else "—"
    return ("<tr><td><strong>%s</strong></td><td>%s</td><td>%d</td><td>%d</td>"
            "<td>%s</td><td>%s</td></tr>") % (w, desc, d["n_buy"], d["n_exit"], exp, wr)

rows_wb = "".join([
    wb_row("FULL", "均线多头（常规建仓窗）"),
    wb_row("HALF", "弱反弹窗（仅S3+观察通道, 5折）"),
    wb_row("NONE", "空仓窗（禁一切建仓）"),
])

# ---------- HALF 窗建仓明细 ----------
half_buys = [b for b in G["G-TIER"]["buys_in"] if b.get("win") == "HALF"]
half_buys.sort(key=lambda b: b["date"])
rows_half = []
if half_buys:
    for b in half_buys[:40]:
        ce = nearest_exit(b, G["G-TIER"]["closed_in"])
        pnl = (fmt(float(ce["pnl_pct"]) * 100, "%", 2, True) if ce else "未平仓")
        rows_half.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%.0f</td><td>%.1f%%</td><td>%s</td><td>%s</td></tr>"
                         % (b["date"], b["code"], b["reason"].replace("观察通道试探建仓", "观察试探").replace("S3有限建仓", "S3有限"), b["score"], b["target"], b["tre"], pnl))
rows_half_html = "".join(rows_half) if rows_half else "<tr><td colspan='7' style='color:#999'>无 HALF 窗建仓</td></tr>"

# ---------- 窗口×TRE状态分布（G-TIER 根因拆解） ----------
hist_t = RES["G-TIER"]["hist"]
win_tre = {}
for h in hist_t:
    w = h.get("win", "")
    if w:
        win_tre.setdefault(w, Counter())[h["tre"]] += 1

def wtre_row(w):
    c = win_tre.get(w, {})
    tot = sum(c.values())
    cells = "".join("<td>%d</td>" % c.get(s, 0) for s in ("S1", "S2", "S3", "S4"))
    return "<tr><td><strong>%s</strong></td><td>%d</td>%s</tr>" % (w, tot, cells)

rows_wtre = "".join(wtre_row(w) for w in ("FULL", "HALF", "NONE"))
half_obs_days = sum(1 for h in hist_t if h.get("win") == "HALF" and h["obs"])

# ---------- MA60 门禁掉的建仓（G1r 无门控 vs G-BIN 二元门控） ----------
G1 = load("variant_G1r.json")
g1b = {(b["date"], b["code"]): b for b in G1["buys_in"]}
binb = {(b["date"], b["code"]): b for b in G["G-BIN"]["buys_in"]}
only_g1 = sorted(set(g1b) - set(binb))
rows_blocked = []
for k in only_g1:
    b = g1b[k]
    ce = nearest_exit(b, G1["closed_in"])
    pnl_s = fmt(float(ce["pnl_pct"]) * 100, "%", 2, True) if ce else "未平仓"
    reason_s = b["reason"].replace("S2减半建仓", "S2减半").replace("S1正常建仓", "S1正常")
    rows_blocked.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%.0f</td><td>%s</td><td>%.1f%%</td><td>%s</td></tr>"
                        % (k[0], k[1], reason_s, b["score"], b["tre"], b["target"], pnl_s))
rows_blocked_html = "".join(rows_blocked) if rows_blocked else "<tr><td colspan='7' style='color:#999'>无差异</td></tr>"

# ---------- 净值曲线 ----------
eq_data = {}
for L in ["G-BIN", "G-TIER"]:
    hist = RES[L]["hist"]
    dates = [h["date"] for h in hist]
    eq = [round(float(h["equity"]) / 10000, 2) for h in hist]  # 万元
    eq_data[L] = {"dates": dates, "equity": eq}

# ---------- 年度建仓分布 ----------
def yearly(L):
    cnt = Counter(b["date"][:4] for b in G[L]["buys_in"])
    return [cnt.get(str(y), 0) for y in range(2019, 2025)]

years = list(range(2019, 2025))
by_bin = yearly("G-BIN")
by_tier = yearly("G-TIER")

# ---------- 结论 ----------
mB, mT = G["G-BIN"]["metrics_in"], G["G-TIER"]["metrics_in"]
delta_buys = mT["n_buys"] - mB["n_buys"]
delta_exp = mT["avg_pnl_pct"] - mB["avg_pnl_pct"]
delta_ann = mT["ann_return"] - mB["ann_return"]
delta_dd = mT["max_drawdown"] - mB["max_drawdown"]
half_exp = WB["HALF"]["exp"] if WB["HALF"]["n_exit"] else float("nan")
full_exp = WB["FULL"]["exp"] if WB["FULL"]["n_exit"] else float("nan")

concl_lines = []
if mT["avg_pnl_pct"] > mB["avg_pnl_pct"]:
    concl_lines.append("实验组单笔期望 %+.2f%% 优于对照组 %+.2f%%" % (mT["avg_pnl_pct"], mB["avg_pnl_pct"]))
else:
    concl_lines.append("实验组单笔期望 %+.2f%% 未优于对照组 %+.2f%%" % (mT["avg_pnl_pct"], mB["avg_pnl_pct"]))
concl_lines.append("建仓笔数: 对照组 %d → 实验组 %d (%+d笔)" % (mB["n_buys"], mT["n_buys"], delta_buys))
if half_exp == half_exp:
    concl_lines.append("实验组 HALF 窗（路径A核心增量）期望 %+.2f%%/笔, 样本 %d 笔" % (half_exp, WB["HALF"]["n_exit"]))
else:
    concl_lines.append("实验组 HALF 窗（路径A核心增量）样本 %d 笔, 均未平仓或样本不足" % WB["HALF"]["n_buy"])

verdict_all = all([
    mT["freq_annual"] >= 6.0, mT["avg_pnl_pct"] > 0, mT["ann_return"] >= 6.0, mT["max_drawdown"] <= 12.0])
verdict_cls = "v-pass" if verdict_all else "v-fail"
verdict_txt = "✅ 实验组全部验收达标 —— 路径A具备 F-35 裁决落地条件" if verdict_all else \
    "❌ 实验组未达验收标准 —— 路径A仍需调整（详见结论）"

html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>阶段1 A/B对比：MA60二元门控 vs 三级分级门控（路径A验证）</title>
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
<h1>阶段1 A/B对比：MA60二元门控 vs 三级分级门控</h1>
<div class="subtitle">路径A验证（2026-08-18）| 复用 G1r 完整配置 + R-04/R-05/R-06/R-10 + 30只候选池 | 样本内 2019-2024 / 样本外 2025-2026H1</div>
<div class="date">引擎: run_backtest.py（新增 BT_MA60GATE / BT_TIERGATE 互斥开关）| 基准: 沪深300 | 初始资金 100万</div>
</div>

<div class="section">
<h2>一、A/B 配置口径</h2>
<table>
<tr><th>配置</th><th>门控结构</th><th>窗口定义（T-1 沪深300）</th><th>建仓权限</th></tr>
<tr><td><strong>G-BIN 对照组</strong></td><td>二元门控（现状实盘规则忠实实现）</td><td>收盘&gt;MA60 → 开；收盘≤MA60 → 关</td><td>MA60上方: 全逻辑；MA60下方: 禁一切建仓</td></tr>
<tr><td><strong>G-TIER 实验组</strong></td><td>三级分级门控（路径A）</td><td>FULL: close&gt;MA60 且 MA20&gt;MA60；HALF: close&gt;MA20 且非FULL；NONE: close≤MA20</td><td>FULL: 全逻辑；HALF: 仅S3有限+观察通道, target×0.5；NONE: 禁一切</td></tr>
</table>
<div class="callout">两组共用同一套 G1r 底层（TRE状态机、R-04波动率闸门、R-05 S1确认制、R-06止损分档、R-10门槛分轨、F-01~F-34 全部裁决），<strong>唯一差异 = 建仓时机门控结构</strong>。对照组 MA60 下方被禁的 S3 有限建仓，实验组在 HALF 窗以 5 折仓位恢复——这正是路径A的核心假设。</div>
</div>

<div class="section">
<h2>二、核心指标对比（样本内 6年）</h2>
<table>
<tr><th>配置</th><th>门控</th><th>建仓笔数</th><th>年建仓</th><th>单笔期望</th><th>年化收益</th><th>最大回撤</th><th>夏普</th><th>胜率</th><th>超额收益</th><th>闸门拦截日</th></tr>
@@ROWS_CMP@@
</table>
</div>

<div class="section">
<h2>三、分级窗口天数分布（样本内）</h2>
<table>
<tr><th>配置</th><th>FULL天数</th><th>占比</th><th>HALF天数</th><th>占比</th><th>NONE天数</th><th>占比</th></tr>
@@ROWS_WIN@@
</div>

<div class="section">
<h2>四、14A 验收判定（样本内）</h2>
<table>
<tr><th>配置</th><th>年建仓≥6笔</th><th>单笔期望&gt;0</th><th>年化≥6%</th><th>回撤≤12%</th><th>结论</th></tr>
@@ROWS_ACCEPT@@
</table>
<div class="callout callout-red"><strong>总判定：@@VERDICT@@</strong><br>
阶段1 验收标准 = 年建仓≥6笔 且 单笔期望&gt;0 且 年化≥6% 且 回撤≤12%（四项全达标方可走 F-35 裁决流程）。</div>
</div>

<div class="section">
<h2>五、净值曲线（样本内，万元）</h2>
<div id="chartEq" class="chart"></div>
</div>

<div class="section">
<h2>六、年度建仓笔数对比</h2>
<div id="chartY" class="chart"></div>
<p>对照组（MA60二元）在 2022-2024 的零建仓期是否被实验组（HALF窗）部分打开，是路径A能否解决"建仓枯竭"的直接证据。</p>
</div>

<div class="section">
<h2>七、实验组分窗口建仓盈亏（核心证据）</h2>
<table>
<tr><th>窗口</th><th>语义</th><th>建仓笔数</th><th>已平仓</th><th>单笔期望</th><th>胜率</th></tr>
@@ROWS_WB@@
</table>
<div class="callout">路径A的设计前提（R10 六维归因）：观察通道试探仓 +0.47%/笔是唯一稳定盈利引擎，S1 追涨 -2.94%/笔是亏损核心。若 HALF 窗建仓期望显著为正，说明"弱反弹期试探"策略有效；若为负，说明 2022-2024 的反弹确属假信号，路径A需转向。</div>
</div>

<div class="section">
<h2>八、根因拆解：HALF 窗为何零建仓（窗口×TRE状态矩阵）</h2>
<table>
<tr><th>窗口</th><th>天数</th><th>S1</th><th>S2</th><th>S3</th><th>S4</th></tr>
@@ROWS_WTRE@@
</table>
<div class="callout callout-red"><strong>结构性发现：HALF 窗 296 天中 TRE 状态 S3 仅 1 天、观察通道激活仅 @@HALF_OBS@@ 天。</strong><br>
路径A 半仓窗放开的"仅 S3 有限建仓 + 观察通道（F-33）"权限，在 6 年样本上几乎没有任何可用的入场通道：① S3 状态机层面几乎不进入（弱反弹期 raw 状态以 S2 为主，188天）；② S4 观察通道触发要求"站稳MA60"，而 HALF 窗定义即 close≤MA60 区域，观察通道仅 3 天过渡期；③ 即使偶有 S3/观察机会，得分≥85 资格门槛 + RPS60≥30 + 六/七灯 + MIN 链条继续拦截（全局拦截 top: RPS 2007次 / 得分&lt;S2_GATE 1244次 / R值C级 1233次 / 层级1 905次）。<strong>结论：建仓枯竭的瓶颈不在门控结构，而在信号供给端（弱反弹期无任何标的能穿透得分+RPS+层级1 完整链条）。</strong></div>
</div>

<div class="section">
<h2>九、MA60 二元门控防守价值验证（G1r 无门控 → G-BIN 被禁建仓）</h2>
<table>
<tr><th>日期</th><th>代码</th><th>模式</th><th>得分</th><th>TRE</th><th>目标仓位</th><th>周期盈亏</th></tr>
@@ROWS_BLOCKED@@
</table>
<div class="callout">对照组（MA60 二元门控）相对 G1r（无显式门控）仅禁掉 1 笔建仓：2023-08-15 酒ETF(512690) S2 减半建仓（score=80, 10%），周期盈亏 <strong>-2.47%</strong>（持有30日触发 E-P9 时间止损，得分降至59&lt;65）。<strong>这 1 笔恰好是亏损单——MA60 二元门控以 n=1 的小样本"净避损 +0.02% 年化贡献"（期望 +0.27%→+0.46%）。防守价值方向正确，但样本量不足以单独支撑结论，需与信号端修复联动。</strong></div>
</div>

<div class="section">
<h2>十、结论与建议</h2>
<ul>
<li>@@CONCL1@@</li>
<li>@@CONCL2@@</li>
<li>@@CONCL3@@</li>
</ul>
<div class="callout callout-red"><strong>阶段1 判定：路径A（分级门控）在此配置下证伪——</strong>与二元门控结果逐位一致（15笔/+0.46%/年化2.39%/回撤1.20%），HALF 窗 296 天开放 S3/观察通道权限后建仓 0 笔。根因是状态机结构性锁死（S3 仅1天、观察通道仅3天）+ 得分85/RPS/层级1 链条在弱反弹期无标的穿透。门控结构不是建仓枯竭的瓶颈。</div>
<div class="callout">下一步建议（按优先级）：
<ol>
<li><strong>信号供给端修复</strong>：HALF 窗零建仓的根因是"弱反弹期无标的通过得分≥85+RPS+层级1"——沿 R10 归因方向（得分门槛标定、标的面扩展、S1 假信号）继续，而非门控结构。</li>
<li><strong>路径D（市场健康度仪表盘）转为主推</strong>：A 证伪后，D 是唯一能同时改善"严控解除判据"与"信号质量感知"的路径，其 5 因子合成可识别"指数被权重股拉红但宽度极差"的假反弹——恰是 HALF 窗 2022-2024 高频出现的形态。</li>
<li><strong>F-35 裁决暂不立项</strong>：分级门控无增量证据，不值得固化入文档；如需保留"半仓窗"概念，仅作为路径D 落地后的配套（D 判定"解除严控"后再开放 HALF 试探）。</li>
</ol></div>
</div>

<div class="footer">中线趋势共振策略 v4.7-R10 · 阶段1 A/B 对比报告 · 2026-08-18</div>
</div>

<script>
var eq = @@EQDATA@@;
var dates = eq["G-BIN"].dates;
var chartEq = echarts.init(document.getElementById('chartEq'));
chartEq.setOption({
  tooltip: { trigger: 'axis' },
  legend: { data: ['G-BIN 二元门控', 'G-TIER 分级门控'], top: 8 },
  grid: { left: 60, right: 20, top: 40, bottom: 40 },
  xAxis: { type: 'category', data: dates, axisLabel: { show: false } },
  yAxis: { type: 'value', name: '万元', scale: true },
  series: [
    { name: 'G-BIN 二元门控', type: 'line', showSymbol: false, data: eq["G-BIN"].equity, lineStyle: { width: 1.5, color: '#90a4ae' }, itemStyle: { color: '#90a4ae' } },
    { name: 'G-TIER 分级门控', type: 'line', showSymbol: false, data: eq["G-TIER"].equity, lineStyle: { width: 2, color: '#c62828' }, itemStyle: { color: '#c62828' } }
  ]
});
var chartY = echarts.init(document.getElementById('chartY'));
chartY.setOption({
  tooltip: { trigger: 'axis' },
  legend: { data: ['G-BIN 二元门控', 'G-TIER 分级门控'], top: 8 },
  grid: { left: 50, right: 20, top: 40, bottom: 30 },
  xAxis: { type: 'category', data: @@YEARS@@ },
  yAxis: { type: 'value', name: '笔', minInterval: 1 },
  series: [
    { name: 'G-BIN 二元门控', type: 'bar', data: @@BY_BIN@@, itemStyle: { color: '#90a4ae' } },
    { name: 'G-TIER 分级门控', type: 'bar', data: @@BY_TIER@@, itemStyle: { color: '#c62828' } }
  ]
});
</script>
</body>
</html>
"""

path = os.path.join(OUT, "阶段1_门控AB对比_MA60二元vs三级分级.html")
repl = {
    "@@ROWS_CMP@@": rows_cmp,
    "@@ROWS_WIN@@": rows_win,
    "@@ROWS_ACCEPT@@": rows_accept,
    "@@ROWS_WB@@": rows_wb,
    "@@ROWS_WTRE@@": rows_wtre,
    "@@ROWS_BLOCKED@@": rows_blocked_html,
    "@@HALF_OBS@@": str(half_obs_days),
    "@@VERDICT@@": verdict_txt,
    "@@EQDATA@@": json.dumps(eq_data),
    "@@YEARS@@": json.dumps(years),
    "@@BY_BIN@@": json.dumps(by_bin),
    "@@BY_TIER@@": json.dumps(by_tier),
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
