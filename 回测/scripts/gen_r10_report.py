# -*- coding: utf-8 -*-
"""生成 v4.7-R10 重构后回测验证 HTML 报告（G 系列）"""
import json, os

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "output")

def load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as fh:
        return json.load(fh)

G = {L: load(f"variant_{L}.json") for L in ["G0r", "G1r", "G2r", "G3r"]}
EQ = load("tmp_equity.json")


def row(L):
    m = G[L]["metrics_in"]
    c = G[L]["config"]
    cls = "pos" if m["avg_pnl_pct"] > 0 else "neg"
    ncls = "pos" if m["noise_stop_rate"] < 53 else "neg"
    return ("<tr><td><strong>%s</strong></td><td>%s/%s</td><td>%d</td><td>%.1f</td>"
            "<td class=\"%s\">%+.2f</td><td>%.2f</td><td>%.2f</td><td>%.2f</td><td>%.1f</td>"
            "<td>%.2f</td><td class=\"%s\">%.1f</td><td>%.1f</td><td>%d</td><td>%.1f</td></tr>") % (
        L, c["score_gate"], c["obs_gate"], m["n_buys"], m["freq_annual"], cls,
        m["avg_pnl_pct"], m["ann_return"], m["max_drawdown"], m["sharpe"], m["win_rate"],
        m["profit_factor"], ncls, m["noise_stop_rate"], m["s1_confirm_wr"],
        m["gate_days"], m["univ_util"])


m = G["G1r"]["metrics_in"]

def tag(ok):
    return "<span class=\"verdict %s\">%s</span>" % ("v-pass" if ok else "v-fail", "达标" if ok else "未达标")

rows33 = []
rows33.append("<tr><td>年化收益率</td><td>&gt;15%%</td><td>%.2f%%</td><td>%s</td></tr>" % (m["ann_return"], tag(False)))
rows33.append("<tr><td>最大回撤</td><td>&lt;12%%</td><td>%.2f%%</td><td>%s</td></tr>" % (m["max_drawdown"], tag(True)))
rows33.append("<tr><td>夏普比率</td><td>&gt;1.0</td><td>%.2f</td><td>%s</td></tr>" % (m["sharpe"], tag(True)))
rows33.append("<tr><td>卡玛比率</td><td>&gt;1.0</td><td>%.2f</td><td>%s</td></tr>" % (m["calmar"], tag(True)))
rows33.append("<tr><td>胜率</td><td>&gt;40%%</td><td>%.1f%%</td><td>%s</td></tr>" % (m["win_rate"], tag(False)))
rows33.append("<tr><td>盈亏比</td><td>&gt;1.5</td><td>%.2f</td><td>%s</td></tr>" % (m["profit_factor"], tag(True)))
rows33.append("<tr><td>年化波动率</td><td>&lt;20%%</td><td>%.2f%%</td><td>%s</td></tr>" % (m["vol"], tag(True)))
rows33.append("<tr><td>月均交易次数(重构口径年6-18)</td><td>6-18笔/年</td><td>%.1f笔/年</td><td>%s</td></tr>" % (m["freq_annual"], tag(False)))
rows33.append("<tr><td>基准超额收益</td><td>&gt;5%%</td><td>%+.2f%%</td><td>%s</td></tr>" % (m["excess"], tag(False)))
rows33.append("<tr><td>第一梯队贡献度</td><td>&gt;50%%</td><td colspan=\"2\">[未计算]</td></tr>")
rows33.append("<tr><td>第二梯队贡献度</td><td>&gt;30%%</td><td colspan=\"2\">[未计算]</td></tr>")
tp = m["tre_pct"]
rows33.append("<tr><td>S1/S2/S3/S4状态占比</td><td>30-50/20-40/15-30/&lt;15%%</td><td>%.1f/%.1f/%.1f/%.1f%%</td><td><span class=\"verdict v-warn\">S2/S3/S4偏离</span></td></tr>" % (tp["S1"], tp["S2"], tp["S3"], tp["S4"]))
rows33.append("<tr><td>S3有限建仓胜率</td><td>&gt;35%%</td><td>样本0笔</td><td><span class=\"verdict v-warn\">[样本不足]</span></td></tr>")
rows33.append("<tr><td>S3/S4平均仓位</td><td>&lt;30%%</td><td>%.2f%%</td><td>%s</td></tr>" % (m["s34_avg_pos"], tag(True)))
rows33.append("<tr><td>MA60冻结期间收益</td><td>&gt;-5%%</td><td>%+.2f%%</td><td>%s</td></tr>" % (m["ma60_freeze_ret"], tag(True)))
rows33.append("<tr><td>熔断触发准确率</td><td>≥70%%</td><td>%.1f%%</td><td>%s</td></tr>" % (m["melt_acc"], tag(False)))
rows33.append("<tr><td>ETF组合年化收益</td><td>&gt;12%%</td><td>%.2f%%</td><td>%s</td></tr>" % (m["etf_ann"] * 100, tag(False)))
rows33.append("<tr><td>ETF产品硬过滤拦截率</td><td>≥90%%</td><td colspan=\"2\">[未单独计算;层级1代理拦截954次]</td></tr>")
rows33.append("<tr><td>降档机制损失规避率</td><td>≥15%%</td><td colspan=\"2\">[未单独计算]</td></tr>")
rows33.append("<tr><td>组合均衡风控回撤</td><td>&lt;10%%</td><td>%.2f%%</td><td>%s</td></tr>" % (m["max_drawdown"], tag(True)))
rows33.append("<tr><td>≥12%%防御观察有效性</td><td>5日修复率≥50%%</td><td>样本无触发</td><td><span class=\"verdict v-warn\">[未触发]</span></td></tr>")
rows33.append("<tr><td>P1止损保护度</td><td>单笔最大亏≤8%%</td><td>%.2f%%</td><td>%s</td></tr>" % (abs(m["max_loss_pct"]), tag(True)))
rows33.append("<tr><td>策略健康度Z-score</td><td>&gt;-2</td><td>%.2f</td><td>%s</td></tr>" % (m["z_mean"], tag(True)))
rows33.append("<tr><td>现金管理收益贡献</td><td>0.5-1%%年化</td><td>%.2f%%年化</td><td><span class=\"verdict v-warn\">超上限2.4%%</span></td></tr>" % m["cash_contrib_ann"])
rows33.append("<tr><td>信号命中率</td><td>参考≥40%%</td><td>%.1f%%</td><td>%s</td></tr>" % (m["signal_hit"], tag(False)))
tw = m["tre_win_rate"]
rows33.append("<tr><td>TRE状态胜率基准</td><td>分状态输出</td><td>S1 %.0f%%(n=%d) / S2 %.0f%%(n=%d) / S3 样本0 / S4 %.0f%%(n=%d)</td><td><span class=\"verdict v-warn\">S1/S2样本&lt;12</span></td></tr>" % (
    tw["S1"]["win_rate"], tw["S1"]["n"], tw["S2"]["win_rate"], tw["S2"]["n"], tw["S4"]["win_rate"], tw["S4"]["n"]))
rows33.append("<tr><td>14:30尾盘熔断捕捉率</td><td>≥80%%</td><td>%.1f%%</td><td>%s</td></tr>" % (m["melt_acc"], tag(False)))
rows33.append("<tr><td><strong>R-04 闸门拦截率</strong></td><td>拦截信号虚拟期望&lt;0</td><td>766日(52.6%%), A门617/B门149</td><td><span class=\"verdict v-pass\">有效</span></td></tr>")
rows33.append("<tr><td><strong>R-05 S1确认制胜率</strong></td><td>&gt;29.7%%</td><td>%.1f%%(n=%d)</td><td>%s</td></tr>" % (m["s1_confirm_wr"], m["s1_n"], tag(False)))
rows33.append("<tr><td><strong>R-06 噪音止损率</strong></td><td>&lt;53%%</td><td>%.1f%%</td><td>%s</td></tr>" % (m["noise_stop_rate"], tag(True)))
rows33.append("<tr><td><strong>R-06 交易期望</strong></td><td>&gt;0%%/笔</td><td>%+.2f%%</td><td>%s</td></tr>" % (m["avg_pnl_pct"], tag(True)))
rows33.append("<tr><td><strong>R-08 建仓频率</strong></td><td>年6-18笔</td><td>%.1f笔/年</td><td>%s</td></tr>" % (m["freq_annual"], tag(False)))
rows33.append("<tr><td><strong>R-09 标的面利用率</strong></td><td>≥30%%</td><td>%.1f%%(%d/%d)</td><td>%s</td></tr>" % (m["univ_util"], m["univ_used"], m["univ_size"], tag(True)))

labels = EQ["G1r"]["labels"]
def eqj(k):
    return json.dumps(EQ[k]["equity"])

pnl = {"G0r": -37820, "G1r": 9679, "G2r": -17863, "G3r": 9679}
cash = {"G0r": 135755, "G1r": 138420, "G2r": 137119, "G3r": 138420}

rows_mat = "".join([row(L) for L in ["G0r", "G1r", "G2r", "G3r"]])
rows33_html = "".join(rows33)

html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>中线趋势共振策略 v4.7-R10 重构后回测验证报告</title>
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
  <h1>中线趋势共振策略 v4.7-R10 重构后回测验证报告</h1>
  <div class="subtitle">R-01~R-10 十项重构裁决引擎落地 · G 系列验证批次（G0r回归对照 / G1r完整重构 / G2r门槛敏感性 / G3r R-05隔离）</div>
  <div class="date">2026-08-18 · 样本内2019-01~2024-12（6年）/ 样本外2025-01~2026-06 · 基准沪深300 · 初始100万</div>
</div>

<div class="section">
  <h2>一、执行摘要</h2>
  <p>本轮在回测引擎中完整落地 v4.7-R10 十项重构裁决（R-01~R-10），建立 G 系列四配置验证批次重跑六年样本，输出 33 项回测指标。核心结论：</p>
  <ul>
    <li><strong>引擎重构成功</strong>：交易期望首次转正（G0r -0.66% → G1r +0.27%）；金额口径交易净贡献首次转正（-3.78万 → <span class="pos">+0.97万</span>）；噪音止损率 83.3% → <span class="pos">30%</span>；盈亏比 1.75 → 1.85；夏普 1.56 → 2.07</li>
    <li><strong>但核心门槛未达标</strong>：G1r 年建仓 2.7笔/年（&lt;6）✗ / 期望 +0.27% ✓ / 年化 2.35%（&lt;6%）✗；G2r 年建仓 6.5 ✓ / 期望 +0.77% ✓ / 年化 1.80% ✗ —— <strong>年化 6% 是全部配置的共同障碍</strong></li>
    <li><strong>收益引擎错位</strong>：G1r 六年总收益 14.39 万中现金管理贡献 13.84 万（96.2%），交易仅贡献 0.97 万（6.7%）——策略实质仍是"现金增强 + 防御"而非"趋势 alpha"</li>
  </ul>
  <div class="callout callout-red">
    <strong>判定：重构版未通过核心门槛，禁止实盘。</strong>按第十六章标准（原27项≥80%达标 + 重构6项全达标 + 年建仓≥6 且 单笔期望&gt;0 且 年化≥6%），G1r 原27项达标率约 53%（可算项）&lt;80%，核心门槛年化 2.35% 距 6% 差 2.5 倍——触发"重新设计"判定，达标前不得宣称可实盘执行。
  </div>
  <p style="font-size:13px;color:#666;">两项积极信号：① R-04 闸门拦截 766 个交易日（52.6%），其拦截信号的虚拟期望为负 → 闸门有效；② R-06 止损分档将噪音止损率从 83.3% 压至 30%（G1r），"给交易时间"假设成立。两项证伪信号：① R-10 的 80 分门槛造成建仓枯竭（16笔/6年）且降门槛后期望更高（+0.77%）——延续归因①"高得分反而最差"；② R-05 确认制在 80 分门槛下隔离效果为零（G1r 与 G3r 逐笔完全一致）。</p>
</div>

<div class="section">
  <h2>二、重构落地核对表（R-01~R-10 → 引擎实现 → 验证证据）</h2>
  <table>
    <tr><th>裁决</th><th>内容</th><th>引擎落地</th><th>验证证据</th></tr>
    <tr><td>R-01</td><td>观察升级豁免固化（P0-E）</td><td>BT_OBSGUARD=1</td><td>继承 D 系列验证</td></tr>
    <tr><td>R-02</td><td>凯利下限 0.10（P0-F）</td><td>BT_KELLYMIN=1</td><td>无 cap=0 死锁</td></tr>
    <tr><td>R-03</td><td>E-P1 止损后 30 日洗仓封堵（P0-G）</td><td>BT_EP1BLOCK=1</td><td>洗仓封堵拦截 51 次(G1r)</td></tr>
    <tr><td><strong>R-04</strong></td><td>波动率环境双闸门（vol20&lt;15禁一切/≥20禁S1S2）</td><td>BT_VOLGATE=1</td><td><strong>766日拦截(52.6%)</strong>；A门617日(42.4%)、B门149日</td></tr>
    <tr><td><strong>R-05</strong></td><td>S1 突破确认制（连2日S1+站稳MA60+开盘≤1%）</td><td>BT_S1CONFIRM=1</td><td><strong>隔离效果=0</strong>（G1r==G3r）；783次拦截全部被前置关卡吸收</td></tr>
    <tr><td><strong>R-06</strong></td><td>止损带宽时间分档（≤11日5% / &gt;11日3%）</td><td>BT_EP1TENOR=1</td><td><strong>噪音止损率 83.3%→30%</strong>；盈亏比 1.75→1.85</td></tr>
    <tr><td>R-07</td><td>观察通道 = 弱势期唯一进攻窗口</td><td>F-30/32/33 全套</td><td>G2r S4建仓10笔胜率40%、S3 2笔胜率50%</td></tr>
    <tr><td><strong>R-08</strong></td><td>建仓频率校准（年6-18笔 + 枯竭预警）</td><td>freq_annual/freq_exhaust</td><td>G1r 2.7 ✗(枯竭) / G2r 6.5 ✓</td></tr>
    <tr><td><strong>R-09</strong></td><td>标的面扩展（12→30只）</td><td>BT_R9UNIV=1（+18只）</td><td><strong>利用率 33.3%✓</strong>（10/30只）; 中证500盈利+7.3K(2024-11)</td></tr>
    <tr><td><strong>R-10</strong></td><td>得分门槛分轨（80/80/78/85）</td><td>BT_R10GATES=1</td><td><strong>建仓枯竭主因</strong>：16笔 vs G2r 39笔；且降门槛后期望更高</td></tr>
  </table>
</div>

<div class="section">
  <h2>三、G 系列验证矩阵（样本内6年）</h2>
  <table>
    <tr><th>配置</th><th>门槛</th><th>建仓</th><th>年建仓</th><th>期望%/笔</th><th>年化%</th><th>回撤%</th><th>夏普</th><th>胜率%</th><th>盈亏比</th><th>噪音止损%</th><th>S1胜率%</th><th>闸门日</th><th>利用率%</th></tr>
    @@ROWS_MAT@@
  </table>
  <div class="callout callout-green">
    <strong>G1r（完整重构）三项突破</strong>：交易期望 -0.66%→+0.27%（六轮迭代首次转正）；金额口径交易净贡献 -3.78万→+0.97万（首次为正）；噪音止损率 83.3%→30%（"给交易时间"生效）。代价是建仓频率 2.7笔/年（门槛 80 分 + 闸门 52.6% 拦截双重压缩）。
  </div>
  <div id="chart_equity" class="chart"></div>
</div>

<div class="section">
  <h2>四、核心门槛判定</h2>
  <table>
    <tr><th>配置</th><th>年建仓≥6笔</th><th>单笔期望&gt;0</th><th>年化≥6%</th><th>判定</th></tr>
    <tr><td>G0r 回归对照</td><td>7.0 ✓</td><td class="neg">-0.66% ✗</td><td class="neg">1.74% ✗</td><td><span class="verdict v-fail">未达标</span></td></tr>
    <tr><td><strong>G1r 完整重构</strong></td><td class="neg">2.7 ✗</td><td class="pos">+0.27% ✓</td><td class="neg">2.35% ✗</td><td><span class="verdict v-fail">未达标</span></td></tr>
    <tr><td><strong>G2r 门槛回退</strong></td><td class="pos">6.5 ✓</td><td class="pos">+0.77% ✓</td><td class="neg">1.80% ✗</td><td><span class="verdict v-fail">未达标</span></td></tr>
    <tr><td>G3r 关S1确认制</td><td class="neg">2.7 ✗</td><td class="pos">+0.27% ✓</td><td class="neg">2.35% ✗</td><td><span class="verdict v-fail">未达标</span></td></tr>
  </table>
  <div class="callout callout-red">
    <strong>年化 6% 是共同障碍</strong>：全部配置年化 1.7-2.4%，且主要来自现金管理（2.4%/年）。交易贡献占 G1r 总收益仅 6.7%。G2r 虽然频率与期望双达标，但金额口径交易净贡献仍为负（-1.79万）——低门槛引入了更多噪音止损，稀释了赢家仓位。
  </div>
  <p><strong>年化 6% 的算术鸿沟</strong>：目标 6 年总收益 ≈ 41.9 万（复利），现金贡献 ≈ 13.8 万，交易需贡献 ≈ 28 万。G1r 当前交易贡献 0.97 万、每笔金额贡献 +605 元——需要 <strong>463 笔同质量交易</strong>（≈77笔/年，远超 6-18 目标）或每笔金额贡献提高 29 倍。这不是参数微调能跨越的差距。</p>
</div>

<div class="section">
  <h2>五、33 项回测指标逐项评估（G1r 完整重构配置）</h2>
  <table>
    <tr><th>指标</th><th>目标值</th><th>G1r 实测</th><th>判定</th></tr>
    @@ROWS33@@
  </table>
  <p style="font-size:13px;color:#666;">可计算项达标率约 13/24 ≈ 54%（[未计算] 与 [样本不足] 不计入分母），低于 80% 触发重新设计判定。达标的均为风控/防御类（回撤/夏普/卡玛/盈亏比/波动率/P1保护/组合均衡回撤/Z-score/MA60冻结），未达标的均为收益/进攻类（年化/超额/胜率/频率/ETF年化/熔断捕捉）。</p>
</div>

<div class="section">
  <h2>六、隔离分析：R-10 门槛 / R-05 确认制 / R-04 闸门</h2>
  <h3>6.1 R-10 门槛（G1r 80/85 vs G2r 70/72）—— 建仓枯竭主因，且降门槛不损期望</h3>
  <table>
    <tr><th>维度</th><th>G1r (80/85)</th><th>G2r (70/72)</th><th>结论</th></tr>
    <tr><td>建仓笔数</td><td>16</td><td>39</td><td>门槛下降 → 建仓 +144%</td></tr>
    <tr><td>年建仓</td><td class="neg">2.7 ✗</td><td class="pos">6.5 ✓</td><td>G2r 达标，G1r 枯竭</td></tr>
    <tr><td>单笔期望</td><td>+0.27%</td><td class="pos">+0.77%</td><td><strong>降门槛期望反而更高</strong></td></tr>
    <tr><td>金额交易贡献</td><td class="pos">+9,679元</td><td class="neg">-17,863元</td><td>高门槛"少而精"、低门槛"多而杂"</td></tr>
    <tr><td>噪音止损率</td><td class="pos">30.0%</td><td>50.0%</td><td>高门槛噪音更少</td></tr>
    <tr><td>盈亏比</td><td>1.85</td><td class="pos">2.50</td><td>G2r 盈利笔质量更高</td></tr>
  </table>
  <p>G2r 的期望优势（+0.77% vs +0.27%）来自更多中低分交易（70-79分）的平均表现——延续归因①"高得分反而最差"（80 分以上追涨信号在 ETF 上被均值回归打穿）。但 G2r 的金额贡献为负，因为低门槛同时放进了更多噪音止损（E-P1 14笔 vs G1r 8笔）并稀释了赢家仓位（2024-11 中证500 同笔盈利 G1r +7,318元 vs G2r +590元，仓位差 12 倍）。<strong>频率与质量存在权衡，最优门槛可能在 75-78 之间的中间值</strong>（本批次未覆盖，列入下一步）。</p>

  <h3>6.2 R-05 S1 确认制（G1r vs G3r）—— 隔离效果 = 零</h3>
  <div class="callout callout-red">
    <strong>G1r 与 G3r 样本内/样本外建仓逐笔完全一致（16+14 笔）。</strong>S1 确认制 783 次拦截的信号，全部被更前置的关卡（RPS 2206 / 得分&lt;S2门槛 1721 / R值C级 1283 / 层级1 954）吸收——即被拦截的信号本就不满足建仓条件。在 80 分高门槛下 R-05 完全冗余，其真实效果需在低门槛（G2r 类）下重新隔离验证。
  </div>
  <p>G1r 的 8 笔 S1 建仓集中在 2022-07（4笔：510300/512010/515030/512690，score 81.6-85.3）——这是 2022 年 7 月反弹顶部区域的密集追涨，S1 胜率仅 25%。R-05 确认制虽拦截了 783 次，但 2022-07 这批"确认后"信号仍被放行——<strong>确认制过滤的是"单日假突破"，不是"顶部区域追涨"</strong>，后者需要 R-04 闸门 B 或更高阶信号把关。</p>

  <h3>6.3 R-04 闸门（766日/52.6%拦截）—— 有效但代价高昂</h3>
  <div id="chart_gate" class="chart"></div>
  <p>六年 1,456 个交易日中 766 日（52.6%）被闸门拦截：<strong>A 门（vol20&lt;15 禁一切建仓）617 日占 42.4%</strong>，B 门（≥20 禁 S1/S2 常规）149 日占 10.2%。vol20 环境分布：黄金区间（15-20）仅 462 日（31.7%）、低波动（&lt;15）617 日（42.4%）、高波动（≥20）377 日（25.9%）。2023 年 193/242 日（80%）被 A 门锁死——A 股长期低波动期与策略的"波动率环境第一过滤器"存在结构性冲突：<strong>策略 6 年中仅 1/3 时间处于正常建仓窗口</strong>。</p>
</div>

<div class="section">
  <h2>七、交易结构：盈亏引擎（G1r vs G2r）</h2>
  <table>
    <tr><th>离场原因</th><th>G0r笔数</th><th>G0r合计%</th><th>G1r笔数</th><th>G1r合计%</th><th>G2r笔数</th><th>G2r合计%</th></tr>
    <tr><td>E-P1 技术止损</td><td>19</td><td class="neg">-0.8</td><td>8</td><td class="neg">-0.4</td><td>14</td><td class="neg">-0.7</td></tr>
    <tr><td>E-P9.5 资格失守</td><td>8</td><td>+0.0</td><td>2</td><td>+0.1</td><td>12</td><td>+0.1</td></tr>
    <tr><td>P12/E-P12 移动止盈</td><td>5</td><td class="pos">+0.4</td><td>2</td><td class="pos">+0.2</td><td>4</td><td class="pos">+0.7</td></tr>
    <tr><td>E-P3 MA60破位</td><td>3</td><td>+0.0</td><td>1</td><td>-0.0</td><td>3</td><td>-0.0</td></tr>
    <tr><td>E-P9 时间止损</td><td>1</td><td>+0.1</td><td>2</td><td>+0.0</td><td>3</td><td>+0.1</td></tr>
    <tr><td>E-P4 因子退化</td><td>1</td><td>+0.0</td><td>1</td><td>+0.0</td><td>1</td><td>+0.0</td></tr>
  </table>
  <div class="callout callout-green">
    <strong>G1r 盈利引擎</strong>：P12 移动止盈 2021-03-01 沪深300ETF <span class="pos">+13,870元（+11.41%）</span> + 2024-11-05 中证500ETF <span class="pos">+7,318元（+8.73%）</span>（R-09 扩展池新标的首次贡献大额盈利）+ 2020-08-04 沪深300ETF +4,883元 = 三笔大赢 +26K 覆盖五笔大亏 -20K。<strong>"让利润奔跑"是唯一盈利引擎，与 E 系列归因结论一致</strong>。
  </div>
  <div class="callout">
    <strong>G2r 的稀释效应</strong>：同样三笔大赢（+11.5K/+4.9K/+0.6K = +17K）但中证500仓位被压缩至 1/12（组合更满 → cap 收缩），叠加军工 -5.2K、沪深300 -4.6K、酒 -4.0K、芯片 -3.0K、科创 -2.5K 五笔大亏 -19.3K → 净 -17.9K。<strong>建仓越多 ≠ 贡献越大；组合拥挤度稀释了单笔"值钱"的交易</strong>。
  </div>
  <div id="chart_breakdown" class="chart"></div>
</div>

<div class="section">
  <h2>八、样本外验证（2025-01 ~ 2026-06）</h2>
  <table>
    <tr><th>配置</th><th>建仓</th><th>年化%</th><th>期望%/笔</th><th>胜率%</th><th>判定</th></tr>
    <tr><td>G0r</td><td>18</td><td>0.71%</td><td class="neg">-0.58%</td><td>11.1%</td><td><span class="verdict v-fail">大幅差于样本内</span></td></tr>
    <tr><td>G1r</td><td>14</td><td>0.92%</td><td class="neg">-2.56%</td><td>9.1%</td><td><span class="verdict v-fail">过拟合警示</span></td></tr>
    <tr><td>G2r</td><td>11</td><td>1.47%</td><td class="neg">-4.93%</td><td>0.0%</td><td><span class="verdict v-fail">过拟合警示</span></td></tr>
    <tr><td>G3r</td><td>14</td><td>0.92%</td><td class="neg">-2.56%</td><td>9.1%</td><td><span class="verdict v-fail">=G1r</span></td></tr>
  </table>
  <div class="callout callout-red">
    <strong>样本外全面恶化</strong>：所有配置期望为负（-0.58% ~ -4.93%）、胜率 0-11%。2025-2026 的上涨市中，策略的 S1/S2 追涨信号被市场打穿——与样本内"低波动防御"的有效性形成反差。<strong>按第十六章标准（大幅差于回测 → 过拟合，简化因子），G 系列配置均存在过拟合警示</strong>，进一步支持"禁止实盘"。
  </div>
</div>

<div class="section">
  <h2>九、结论与战略建议</h2>
  <div class="callout callout-red">
    <strong>最终判定：v4.7-R10 重构版未通过核心门槛，禁止实盘。</strong>引擎重构是成功的（期望转正、噪音止损减半、夏普提升），但收益引擎错位（现金管理 96% 主导）与建仓频率/质量权衡两大结构问题未解决。按第十六章标准触发"重新设计"判定，模拟盘对照运行（《实盘执行文本》过渡期安排）不受影响。
  </div>
  <h3>9.1 证据链总结（G 系列 vs 六轮迭代）</h3>
  <table>
    <tr><th>阶段</th><th>核心修复</th><th>建仓</th><th>期望%</th><th>年化%</th><th>结论</th></tr>
    <tr><td>R1-R3</td><td>门槛重标定/转换表V1/第5灯分层</td><td>2</td><td>-</td><td>2.29</td><td>建仓频率瓶颈</td></tr>
    <tr><td>R4 (P0-E/F/G)</td><td>观察升级豁免/凯利下限/洗仓封堵</td><td>42</td><td>-0.66</td><td>1.74</td><td>建仓达标但负期望</td></tr>
    <tr><td>R6 (E系列)</td><td>vol过滤/S1降档</td><td>33/62/42</td><td>+0.03/-1.16/-0.60</td><td>2.12/1.97/2.16</td><td>过滤器证伪</td></tr>
    <tr><td><strong>R10 (G系列)</strong></td><td><strong>双闸门/S1确认制/止损分档/30只池</strong></td><td><strong>16/39</strong></td><td class="pos"><strong>+0.27/+0.77</strong></td><td><strong>2.35/1.80</strong></td><td><strong>期望转正但年化受阻</strong></td></tr>
  </table>
  <p>七轮迭代共修复 17 个引擎级缺陷，交易期望从 -0.66% 修复至 +0.27~+0.77%，但年化始终在 1.7-2.4% 徘徊。<strong>每轮修复解决前一瓶颈，暴露更深结构问题：收益引擎是持币吃息而非交易 alpha</strong>。</p>
  <h3>9.2 下一步路径（按优先级）</h3>
  <table>
    <tr><th>路径</th><th>核心动作</th><th>预期</th><th>风险</th></tr>
    <tr>
      <td><strong>① 门槛细分扫描</strong></td>
      <td>在 75-78 之间扫描行业ETF/常规门槛（G1r 80 vs G2r 70 的中间带），验证"频率×质量"最优平衡点</td>
      <td>可能找到 年建仓≥6 且 金额贡献为正 的配置</td>
      <td>低；工作量小，基于现有引擎</td>
    </tr>
    <tr>
      <td><strong>② 仓位引擎重构</strong></td>
      <td>解决"期望正但金额贡献小"：放宽 F04 目标仓位（3-15%→5-20%）与 cap 约束，验证风险预算≤1% 是否过度保守</td>
      <td>单笔金额贡献提高 2-3 倍，交易贡献占收益比提升</td>
      <td>中；回撤可能上升，须重验风控</td>
    </tr>
    <tr>
      <td><strong>③ 接受定位 + 另起进攻线</strong></td>
      <td>明确"低波动现金增强+防御"定位（年化≈2.6%），6% 目标转由新策略线承担</td>
      <td>定位清晰，避免反复重构</td>
      <td>放弃 15% 目标，需重建组合结构</td>
    </tr>
  </table>
  <p style="font-size:13px;color:#666;">无论选择哪条路径，实盘资格门槛不变：样本内年建仓≥6 且 单笔期望&gt;0 且 年化≥6%。现有持仓（恒瑞医药/国开债ETF/沪深300ETF/外高B）继续按原有计划管理，不受策略迭代影响；外高B独立不计入组合统计。</p>
</div>

<div class="footer">
  <p>本报告仅供研究参考，不构成个人投资建议。市场有风险，投资需谨慎。</p>
  <p>中线趋势共振策略 v4.7-R10 · 重构后回测验证（G系列）· 2026-08-18</p>
</div>

</div>

<script>
var c1 = echarts.init(document.getElementById('chart_equity'));
c1.setOption({
  title: { text: '净值曲线对比（样本内6年，月度）', left: 'center', textStyle: { fontSize: 14 } },
  tooltip: { trigger: 'axis' },
  legend: { data: ['G0r 回归对照','G1r 完整重构','G2r 门槛回退','沪深300基准'], bottom: 0 },
  grid: { left: 60, right: 30, top: 40, bottom: 50 },
  xAxis: { type: 'category', data: @@LABELS@@, axisLabel: { fontSize: 10, interval: 5 } },
  yAxis: { type: 'value', name: '净值(万)', axisLabel: { formatter: function(v){ return (v/10000).toFixed(1); } } },
  series: [
    { name: 'G0r 回归对照', type: 'line', data: @@EQ_G0R@@, lineStyle: { width: 1.5 }, color: '#9e9e9e' },
    { name: 'G1r 完整重构', type: 'line', data: @@EQ_G1R@@, lineStyle: { width: 2.5 }, color: '#1976d2' },
    { name: 'G2r 门槛回退', type: 'line', data: @@EQ_G2R@@, lineStyle: { width: 2 }, color: '#e65100' },
    { name: '沪深300基准', type: 'line', data: @@EQ_BENCH@@, lineStyle: { width: 1.5, type: 'dashed' }, color: '#8e24aa' }
  ]
});

var c2 = echarts.init(document.getElementById('chart_breakdown'));
c2.setOption({
  title: { text: '收益结构（6年，元）：现金管理 vs 已实现交易', left: 'center', textStyle: { fontSize: 14 } },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  legend: { data: ['现金管理收益','已实现交易PnL'], bottom: 0 },
  grid: { left: 70, right: 30, top: 40, bottom: 50 },
  xAxis: { type: 'category', data: ['G0r','G1r','G2r','G3r'] },
  yAxis: { type: 'value', name: '元', axisLabel: { formatter: function(v){ return (v/10000).toFixed(1)+'万'; } } },
  series: [
    { name: '现金管理收益', type: 'bar', data: [@@CASH0@@,@@CASH1@@,@@CASH2@@,@@CASH3@@], color: '#43a047', barWidth: 30 },
    { name: '已实现交易PnL', type: 'bar', data: [@@PNL0@@,@@PNL1@@,@@PNL2@@,@@PNL3@@], color: '#e53935', barWidth: 30,
      label: { show: true, position: 'top', formatter: function(p){ return (p.value/10000).toFixed(2)+'万'; }, fontSize: 10, color: '#333' } }
  ]
});

var c3 = echarts.init(document.getElementById('chart_gate'));
c3.setOption({
  title: { text: 'R-04 闸门年度分布（样本内）', left: 'center', textStyle: { fontSize: 14 } },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  legend: { data: ['A门 vol20<15','B门 vol20≥20','正常交易日'], bottom: 0 },
  grid: { left: 60, right: 30, top: 40, bottom: 50 },
  xAxis: { type: 'category', data: ['2019','2020','2021','2022','2023','2024'] },
  yAxis: { type: 'value', name: '交易日', max: 250 },
  series: [
    { name: 'A门 vol20<15', type: 'bar', stack: 't', data: [94,68,72,53,193,137], color: '#ef5350', barWidth: 40 },
    { name: 'B门 vol20≥20', type: 'bar', stack: 't', data: [28,29,38,17,0,37], color: '#ffa726' },
    { name: '正常交易日', type: 'bar', stack: 't', data: [122,146,133,172,49,68], color: '#c8e6c9' }
  ]
});

window.addEventListener('resize', function() { c1.resize(); c2.resize(); c3.resize(); });
</script>
</body>
</html>
"""

path = os.path.join(OUT, "中线趋势共振策略 v4.7-R10 重构后回测验证.html")
toks = {
    "@@ROWS_MAT@@": rows_mat,
    "@@ROWS33@@": rows33_html,
    "@@LABELS@@": json.dumps(labels),
    "@@EQ_G0R@@": eqj("G0r"),
    "@@EQ_G1R@@": eqj("G1r"),
    "@@EQ_G2R@@": eqj("G2r"),
    "@@EQ_BENCH@@": eqj("bench"),
    "@@CASH0@@": str(cash["G0r"]), "@@CASH1@@": str(cash["G1r"]),
    "@@CASH2@@": str(cash["G2r"]), "@@CASH3@@": str(cash["G3r"]),
    "@@PNL0@@": str(pnl["G0r"]), "@@PNL1@@": str(pnl["G1r"]),
    "@@PNL2@@": str(pnl["G2r"]), "@@PNL3@@": str(pnl["G3r"]),
}
for k, v in toks.items():
    assert k in html, "missing token " + k
    html = html.replace(k, v)
with open(path, "w", encoding="utf-8") as fh:
    fh.write(html)
print("written:", path, len(html), "chars")
