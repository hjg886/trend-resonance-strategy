# -*- coding: utf-8 -*-
"""
阶段1历史定参回测 — 对比分析HTML报告生成器
读取 phase1_summary.json，输出交互式HTML研报
"""
import json, os, datetime

SUMMARY = os.path.join(os.path.dirname(__file__), "..", "output", "phase1_summary.json")
OUT_HTML = os.path.join(os.path.dirname(__file__), "..", "output", "phase1_report.html")

with open(SUMMARY, "r", encoding="utf-8") as f:
    data = json.load(f)

R = data["results"]
TS = data.get("timestamp", "")

# ---------- helpers ----------
def fmt_money(v):
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:,.0f}"

def fmt_pct(v):
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"

def verdict(key):
    """Return PASS/FAIL based on annualized return >= 6% for IS"""
    is_key = key.replace("_OOS", "_IS")
    if is_key in R:
        return "PASS" if R[is_key]["ann_ret"] >= 6.0 else "FAIL"
    return "—"

# ---------- build table rows ----------
variants_a = ["A1", "A2", "A3"]
variants_b = ["B1", "B2", "B3"]
variants_c = ["C1", "C2"]

def row_html(key, label, desc):
    d = R[key]
    is_fail = d["ann_ret"] < 0
    cls = ' class="neg"' if is_fail else ' class="pos"'
    v = verdict(key)
    vcls = ' class="pass"' if v == "PASS" else ' class="fail"'
    return f"""<tr{cls}>
      <td class="td-label">{label}</td>
      <td class="td-desc">{desc}</td>
      <td>{'IS' if '_IS' in key else 'OOS'}</td>
      <td>{fmt_pct(d['ann_ret'])}</td>
      <td>{d['max_dd']:.2f}%</td>
      <td>{d['sharpe']:.2f}</td>
      <td>{d['n_buys']}</td>
      <td>{fmt_money(d['trade_pnl'])}</td>
      <td>{d['win_rate']:.1f}%</td>
      <td>{fmt_money(d['expectancy'])}</td>
      <td>{fmt_money(d['final_equity'])}</td>
      <td{vcls}>{v}</td>
    </tr>"""

table_rows_a = ""
for v in variants_a:
    for period in ["IS", "OOS"]:
        k = f"{v}_{period}"
        desc_map = {"A1": "3%超跌入场", "A2": "RSI<35入场", "A3": "5%宽松入场"}
        table_rows_a += row_html(k, v, desc_map[v])

table_rows_b = ""
for v in variants_b:
    for period in ["IS", "OOS"]:
        k = f"{v}_{period}"
        desc_map = {"B1": "vol20≥30禁建仓", "B2": "得分≥85严格", "B3": "vol20≥12高频"}
        table_rows_b += row_html(k, v, desc_map[v])

table_rows_c = ""
for v in variants_c:
    for period in ["IS", "OOS"]:
        k = f"{v}_{period}"
        desc_map = {"C1": "Best A(A3) + P12v6", "C2": "Best B(B3) + P12v6"}
        table_rows_c += row_html(k, v, desc_map[v])

# ---------- chart data ----------
# Bar chart: IS vs OOS annualized return by variant
bar_labels = []
bar_is = []
bar_oos = []
for v in variants_a + variants_b:
    bar_labels.append(v)
    bar_is.append(R[f"{v}_IS"]["ann_ret"])
    bar_oos.append(R[f"{v}_OOS"]["ann_ret"])

# B3 detail: trade_pnl breakdown
b3_pnl_is = R["B3_IS"]["trade_pnl"]
b3_pnl_oos = R["B3_OOS"]["trade_pnl"]
b3_cash_is = R["B3_IS"]["cash_mgmt"]
b3_cash_oos = R["B3_OOS"]["cash_mgmt"]

# Win rate comparison
win_labels = variants_a + variants_b
win_is = [R[f"{v}_IS"]["win_rate"] for v in win_labels]
win_oos = [R[f"{v}_OOS"]["win_rate"] for v in win_labels]

# Expectancy comparison
exp_labels = variants_a + variants_b
exp_is = [R[f"{v}_IS"]["expectancy"] for v in exp_labels]
exp_oos = [R[f"{v}_OOS"]["expectancy"] for v in exp_labels]

# Drawdown comparison
dd_labels = variants_a + variants_b
dd_is = [R[f"{v}_IS"]["max_dd"] for v in dd_labels]
dd_oos = [R[f"{v}_OOS"]["max_dd"] for v in dd_labels]

# ---------- HTML ----------
html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>阶段1历史定参回测对比分析报告</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<style>
  :root {{
    --bg: #f5f7fa;
    --card: #ffffff;
    --border: #e2e8f0;
    --text: #1a202c;
    --text2: #4a5568;
    --text3: #718096;
    --red: #e53e3e;
    --green: #38a169;
    --blue: #3182ce;
    --orange: #dd6b20;
    --purple: #805ad5;
    --teal: #319795;
    --pass: #38a169;
    --fail: #e53e3e;
    --neg: #e53e3e;
    --pos: #38a169;
    --shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06);
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    font-size: 14px;
  }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 24px 16px; }}

  /* Header */
  .report-header {{
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 40px 32px;
    border-radius: 12px;
    margin-bottom: 28px;
    box-shadow: 0 4px 14px rgba(102,126,234,0.35);
  }}
  .report-header h1 {{ font-size: 26px; font-weight: 700; margin-bottom: 8px; }}
  .report-header .subtitle {{ font-size: 15px; opacity: 0.9; }}
  .report-header .meta {{
    display: flex; gap: 24px; margin-top: 16px; font-size: 13px; opacity: 0.85;
  }}
  .report-header .meta span {{ display: flex; align-items: center; gap: 6px; }}

  /* Section */
  .section {{
    background: var(--card);
    border-radius: 10px;
    padding: 24px 28px;
    margin-bottom: 20px;
    box-shadow: var(--shadow);
    border: 1px solid var(--border);
  }}
  .section-title {{
    font-size: 18px;
    font-weight: 700;
    margin-bottom: 16px;
    padding-bottom: 10px;
    border-bottom: 2px solid var(--border);
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .section-title .icon {{
    width: 28px; height: 28px; border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px; color: white; flex-shrink: 0;
  }}

  /* Summary cards */
  .summary-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 16px;
    margin-bottom: 8px;
  }}
  .summary-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 18px 20px;
    box-shadow: var(--shadow);
  }}
  .summary-card .label {{ font-size: 12px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }}
  .summary-card .value {{ font-size: 24px; font-weight: 700; }}
  .summary-card .sub {{ font-size: 12px; color: var(--text3); margin-top: 4px; }}
  .summary-card .value.pos {{ color: var(--pos); }}
  .summary-card .value.neg {{ color: var(--neg); }}
  .summary-card.best {{ border-color: var(--green); border-width: 2px; }}
  .summary-card.best .label::after {{ content: " ★"; color: var(--orange); }}

  /* Table */
  .table-wrap {{ overflow-x: auto; margin-top: 8px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{
    background: #f7fafc;
    color: var(--text2);
    font-weight: 600;
    text-align: center;
    padding: 10px 8px;
    border-bottom: 2px solid var(--border);
    white-space: nowrap;
  }}
  td {{
    padding: 8px;
    text-align: center;
    border-bottom: 1px solid var(--border);
  }}
  td.td-label {{ font-weight: 700; text-align: left; padding-left: 12px; }}
  td.td-desc {{ color: var(--text3); text-align: left; font-size: 12px; }}
  tr.neg td {{ color: var(--neg); }}
  tr.pos td {{ color: var(--text); }}
  tr.pos td.td-label {{ color: var(--pos); font-weight: 700; }}
  td.pass {{ color: var(--pass); font-weight: 700; }}
  td.fail {{ color: var(--fail); font-weight: 700; }}
  .table-caption {{
    font-size: 12px; color: var(--text3); margin-top: 8px;
    padding: 8px 12px; background: #f7fafc; border-radius: 6px;
  }}

  /* Chart */
  .chart-box {{
    width: 100%; height: 380px; margin: 16px 0;
    border: 1px solid var(--border); border-radius: 8px; overflow: hidden;
  }}
  .chart-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  @media (max-width: 900px) {{ .chart-row {{ grid-template-columns: 1fr; }} }}

  /* Verdict box */
  .verdict-box {{
    border-radius: 8px;
    padding: 16px 20px;
    margin: 12px 0;
    display: flex;
    align-items: flex-start;
    gap: 12px;
  }}
  .verdict-box.reject {{ background: #fff5f5; border-left: 4px solid var(--red); }}
  .verdict-box.accept {{ background: #f0fff4; border-left: 4px solid var(--green); }}
  .verdict-box.warn {{ background: #fffaf0; border-left: 4px solid var(--orange); }}
  .verdict-box.info {{ background: #ebf8ff; border-left: 4px solid var(--blue); }}
  .verdict-box .v-title {{ font-weight: 700; margin-bottom: 4px; }}
  .verdict-box.reject .v-title {{ color: var(--red); }}
  .verdict-box.accept .v-title {{ color: var(--green); }}
  .verdict-box.warn .v-title {{ color: var(--orange); }}
  .verdict-box.info .v-title {{ color: var(--blue); }}
  .verdict-box .v-body {{ font-size: 13px; color: var(--text2); }}

  /* Gap analysis */
  .gap-table th, .gap-table td {{ text-align: center; }}
  .gap-table .gap-neg {{ color: var(--red); font-weight: 700; }}
  .gap-table .gap-pos {{ color: var(--green); font-weight: 700; }}

  /* Analysis text */
  .analysis-text {{ font-size: 14px; color: var(--text2); line-height: 1.8; }}
  .analysis-text strong {{ color: var(--text); }}
  .analysis-text ul {{ margin-left: 20px; margin-top: 8px; }}
  .analysis-text li {{ margin-bottom: 6px; }}

  /* Config card */
  .config-card {{
    background: linear-gradient(135deg, #f0fff4 0%, #e6fffa 100%);
    border: 2px solid var(--green);
    border-radius: 10px;
    padding: 20px 24px;
    margin: 12px 0;
  }}
  .config-card h4 {{ color: var(--green); margin-bottom: 10px; font-size: 16px; }}
  .config-card .params {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 13px; }}
  .config-card .params div {{ padding: 4px 0; border-bottom: 1px dashed #c6f6d5; }}
  .config-card .params strong {{ color: var(--text); }}

  /* Footer */
  .footer {{
    text-align: center; padding: 24px; color: var(--text3); font-size: 12px;
    border-top: 1px solid var(--border); margin-top: 20px;
  }}
  .footer .disclaimer {{
    background: #fffaf0; border: 1px solid #feebc8; border-radius: 8px;
    padding: 12px 20px; margin-bottom: 12px; text-align: left;
    font-size: 12px; color: #744210; line-height: 1.6;
  }}

  .tag {{
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 11px; font-weight: 600; margin-left: 6px;
  }}
  .tag-fail {{ background: #fed7d7; color: #9b2c2c; }}
  .tag-pass {{ background: #c6f6d5; color: #22543d; }}
</style>
</head>
<body>
<div class="container">

<!-- Header -->
<div class="report-header">
  <h1>阶段1历史定参回测 · 对比分析报告</h1>
  <div class="subtitle">三层资金架构进攻线模拟盘 · 14变体历史定参回测</div>
  <div class="meta">
    <span>回测引擎: v4.7-R10 + JOINT固化</span>
    <span>IS: 2019-01-02 ~ 2024-12-31 (6年)</span>
    <span>OOS: 2025-01-02 ~ 2026-06-30 (1.5年)</span>
    <span>初始资金: 1,000,000</span>
    <span>生成: {TS}</span>
  </div>
</div>

<!-- Executive Summary -->
<div class="section">
  <div class="section-title">
    <div class="icon" style="background:var(--blue)">01</div>
    执行摘要
  </div>
  <div class="summary-grid">
    <div class="summary-card best">
      <div class="label">最优变体</div>
      <div class="value pos">B3</div>
      <div class="sub">vol20≥12 + 得分≥70 + P12v6</div>
    </div>
    <div class="summary-card">
      <div class="label">B3 IS年化</div>
      <div class="value pos">+7.04%</div>
      <div class="sub">超额6%目标 +1.04pp</div>
    </div>
    <div class="summary-card">
      <div class="label">B3 OOS年化</div>
      <div class="value pos">+13.15%</div>
      <div class="sub">超额6%目标 +7.15pp</div>
    </div>
    <div class="summary-card">
      <div class="label">候选A(ETF均值回归)</div>
      <div class="value neg">全否决</div>
      <div class="sub">6变体均负收益</div>
    </div>
    <div class="summary-card">
      <div class="label">候选C(P12v6叠加)</div>
      <div class="value" style="color:var(--text3)">无增量</div>
      <div class="sub">C1=A3 / C2=B3 完全一致</div>
    </div>
    <div class="summary-card">
      <div class="label">B3 IS交易PnL</div>
      <div class="value pos">+505,801</div>
      <div class="sub">354笔建仓 · 胜率44.4%</div>
    </div>
  </div>
  <div class="verdict-box accept" style="margin-top:16px;">
    <div>
      <div class="v-title">裁决：B3为进攻线最优配置候选</div>
      <div class="v-body">
        B3（闸门A≥10 + 得分≥70 + P12v6默认开启）在IS期年化7.04%、OOS期年化13.15%，OOS显著优于IS表明非过拟合。
        P12v6移动止盈引擎为唯一核心盈利出场机制（IS触发104次）。建议进入模拟盘验证阶段，配比0-10%渐进实盘。
      </div>
    </div>
  </div>
</div>

<!-- Full Comparison Table -->
<div class="section">
  <div class="section-title">
    <div class="icon" style="background:var(--purple)">02</div>
    14变体核心指标对比
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>变体</th><th>配置说明</th><th>期间</th>
          <th>年化收益</th><th>最大回撤</th><th>Sharpe</th>
          <th>建仓数</th><th>交易PnL</th><th>胜率</th>
          <th>期望/笔</th><th>期末权益</th><th>6%目标</th>
        </tr>
      </thead>
      <tbody>
        <tr><td colspan="12" style="background:#fff5f5;font-weight:700;color:var(--red);text-align:left;padding-left:12px;">候选A — ETF均值回归</td></tr>
        {table_rows_a}
        <tr><td colspan="12" style="background:#f0fff4;font-weight:700;color:var(--green);text-align:left;padding-left:12px;">候选B — 个股精选</td></tr>
        {table_rows_b}
        <tr><td colspan="12" style="background:#ebf8ff;font-weight:700;color:var(--blue);text-align:left;padding-left:12px;">候选C — P12v6叠加验证</td></tr>
        {table_rows_c}
      </tbody>
    </table>
  </div>
  <div class="table-caption">
    注：IS=2019-2024样本内(6年固定年化)，OOS=2025-2026样本外(1.5年固定年化)；6%目标判定基于IS年化是否≥6%。
  </div>
</div>

<!-- Chart: IS vs OOS Annualized Return -->
<div class="section">
  <div class="section-title">
    <div class="icon" style="background:var(--teal)">03</div>
    年化收益对比：IS vs OOS
  </div>
  <div id="chart_annret" class="chart-box"></div>
  <div class="analysis-text">
    <strong>关键发现：</strong>
    <ul>
      <li><strong>候选A全部负收益</strong>：A1/A2/A3在IS期年化-1.10%~-1.55%，OOS期-0.66%~-1.21%，ETF均值回归策略在A股市场持续失效</li>
      <li><strong>B3 OOS > IS</strong>：B3的OOS年化(13.15%)几乎为IS(7.04%)的2倍，OOS胜率58.2%远超IS的44.4%，表明策略在近期市场环境下表现更优，非过拟合</li>
      <li><strong>B2与B1对比</strong>：B2(得分≥85)较B1(vol20≥30)在IS期年化更高(5.23% vs 4.36%)但OOS更低(6.32% vs 9.68%)，严格筛选在样本外边际递减</li>
    </ul>
  </div>
</div>

<!-- Candidate A Analysis -->
<div class="section">
  <div class="section-title">
    <div class="icon" style="background:var(--red)">04</div>
    候选A — ETF均值回归：策略否决
  </div>
  <div class="verdict-box reject">
    <div>
      <div class="v-title">否决裁决：ETF均值回归策略不适用于进攻线</div>
      <div class="v-body">
        所有6个变体（A1/A2/A3 × IS/OOS）均为负收益。IS期合计495笔建仓仅产生-232,809交易PnL，胜率38.8%~43.3%。
        核心问题：均值回归出场（close≥MA20）触发后盈利太小，无法覆盖止损亏损。
      </div>
    </div>
  </div>
  <div class="chart-row">
    <div id="chart_a_pnl" class="chart-box" style="height:320px;"></div>
    <div id="chart_a_winrate" class="chart-box" style="height:320px;"></div>
  </div>
  <div class="analysis-text">
    <strong>根因分析：</strong>
    <ul>
      <li><strong>胜率不足</strong>：A1-A3 IS期胜率38.8%~43.3%，均低于50%门槛，均值回归信号在趋势型A股市场频繁失效</li>
      <li><strong>盈亏比恶化</strong>：A3 IS期平均盈利2,025 vs 平均亏损-2,195，盈亏比仅0.92，无法以低胜率覆盖</li>
      <li><strong>出场过早</strong>：均值回归出场（close≥MA20）在反弹初期即触发，截断了潜在大盈利；而止损(8%)却完整承受了下跌</li>
      <li><strong>P12v6无效</strong>：C1=A3，ETF均值回归的持仓从未达到15%浮盈门槛，P12v6移动止盈零触发</li>
    </ul>
  </div>
</div>

<!-- Candidate B Analysis -->
<div class="section">
  <div class="section-title">
    <div class="icon" style="background:var(--green)">05</div>
    候选B — 个股精选：B3最优
  </div>

  <div class="config-card">
    <h4>B3 最优配置参数</h4>
    <div class="params">
      <div><strong>策略脚本：</strong>run_attack_b.py（独立回测）</div>
      <div><strong>标的池：</strong>OBS_POOL 24只观察池个股</div>
      <div><strong>入场评分：</strong>简化技术评分≥70（趋势50+动量30+流动性20）</div>
      <div><strong>TRE过滤：</strong>S1/S2/S3（非S4）</div>
      <div><strong>闸门A阈值：</strong>vol20 ≥ 10%（vs 主引擎15%）</div>
      <div><strong>流动性门槛：</strong>amount20 ≥ 5000万</div>
      <div><strong>ATR上限：</strong>≤10%</div>
      <div><strong>出场机制：</strong>P12v6移动止盈（默认开启）+ 止损8% + 时间止损30日</div>
      <div><strong>仓位管理：</strong>5%/笔，最多5笔并发</div>
      <div><strong>总仓上限：</strong>25%</div>
    </div>
  </div>

  <div class="chart-row">
    <div id="chart_b_pnl" class="chart-box" style="height:320px;"></div>
    <div id="chart_b_expectancy" class="chart-box" style="height:320px;"></div>
  </div>

  <div class="analysis-text">
    <strong>B1 → B2 → B3 递进分析：</strong>
    <ul>
      <li><strong>B1（vol20≥30禁建仓）</strong>：最保守配置，IS年化4.36%/OOS 9.68%，回撤5.67%最低，但287笔建仓仅290K PnL，闸门过紧压制频率</li>
      <li><strong>B2（得分≥85严格）</strong>：高得分筛选，IS年化5.23%/OOS 6.32%，221笔建仓PnL 356K，单笔期望1,610最高（IS），但OOS增速放缓</li>
      <li><strong>B3（vol20≥12高频）</strong>：放松闸门A至10%释放建仓窗口，IS年化7.04%/OOS 13.15%，354笔建仓PnL 506K，OOS胜率58.2% — <strong>综合最优</strong></li>
    </ul>
  </div>

  <div class="verdict-box accept">
    <div>
      <div class="v-title">B3 优势确认</div>
      <div class="v-body">
        ① IS年化7.04%超额6%目标+1.04pp；② OOS年化13.15%超额+7.15pp，OOS>IS排除过拟合；③ 交易PnL +505,801（IS最高）；
        ④ P12v6触发104次(IS)/42次(OOS)，是核心盈利引擎；⑤ 闸门A从15→10释放了558天建仓窗口(vs B1的613天被闸门A拦截)；
        ⑥ OOS期望2,146/笔（vs IS 1,429/笔），近期市场策略增益显著。
      </div>
    </div>
  </div>
</div>

<!-- Candidate C Analysis -->
<div class="section">
  <div class="section-title">
    <div class="icon" style="background:var(--blue)">06</div>
    候选C — P12v6叠加验证：无增量
  </div>
  <div class="verdict-box info">
    <div>
      <div class="v-title">结论：P12v6叠加不产生增量收益</div>
      <div class="v-body">
        C1 = A3（完全一致），C2 = B3（完全一致）。原因：
        ① 候选A的ETF均值回归持仓从未达到15%浮盈门槛，P12v6零触发；
        ② 候选B3的run_attack_b.py已默认开启P12v6，C2等同于B3自身。
        P12v6的价值已在B3单独回测中完整体现（IS触发104次），无需作为独立叠加层验证。
      </div>
    </div>
  </div>
</div>

<!-- Win Rate & Drawdown -->
<div class="section">
  <div class="section-title">
    <div class="icon" style="background:var(--orange)">07</div>
    胜率与回撤对比
  </div>
  <div class="chart-row">
    <div id="chart_winrate" class="chart-box" style="height:320px;"></div>
    <div id="chart_drawdown" class="chart-box" style="height:320px;"></div>
  </div>
  <div class="analysis-text">
    <strong>风控维度评估：</strong>
    <ul>
      <li><strong>B3 IS回撤8.37%</strong>：为所有B变体中最高，但仍远低于12%最大回撤目标线，风控可接受</li>
      <li><strong>B3 OOS回撤4.99%</strong>：较IS期下降40%，近期市场环境下风控表现更优</li>
      <li><strong>候选A回撤虚低</strong>：A1-A3 IS回撤7.41%~9.67%看似可控，但源于"亏损即出场"——负收益策略回撤天然偏低，不具参考价值</li>
      <li><strong>B3 OOS胜率58.2%</strong>：显著高于IS期44.4%，策略在2025-2026市场环境下胜率提升13.8pp</li>
    </ul>
  </div>
</div>

<!-- Orthogonality & Gap Analysis -->
<div class="section">
  <div class="section-title">
    <div class="icon" style="background:var(--purple)">08</div>
    正交性与6%目标差距分析
  </div>

  <div class="verdict-box info">
    <div>
      <div class="v-title">B3与主引擎的天然隔离</div>
      <div class="v-body">
        B3使用独立回测脚本(run_attack_b.py)，绕过主引擎24因子体系，采用简化技术评分(趋势50+动量30+流动性20)。
        标的池为OBS_POOL 24只观察池个股，与主引擎G1r回测的ETF+个股池存在交集但入场逻辑完全不同。
        A∩B=0：主引擎的S1+ETF亏损与B3的个股精选入场无信号重叠，两者天然正交。
      </div>
    </div>
  </div>

  <table class="gap-table" style="margin-top:16px;">
    <thead>
      <tr>
        <th>配置</th><th>IS年化</th><th>OOS年化</th><th>IS回撤</th>
        <th>IS缺口</th><th>OOS缺口</th><th>状态</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td style="text-align:left;font-weight:700;">主引擎 JOINT+P12v6</td>
        <td>+2.97%</td><td>+4.02%</td><td>1.85%</td>
        <td class="gap-neg">-3.03pp</td><td class="gap-neg">-1.98pp</td>
        <td><span class="tag tag-fail">未达标</span></td>
      </tr>
      <tr>
        <td style="text-align:left;font-weight:700;">进攻线B3（独立）</td>
        <td>+7.04%</td><td>+13.15%</td><td>8.37%</td>
        <td class="gap-pos">+1.04pp</td><td class="gap-pos">+7.15pp</td>
        <td><span class="tag tag-pass">已达标</span></td>
      </tr>
      <tr>
        <td style="text-align:left;font-weight:700;">组合(主90%+B3 10%)</td>
        <td>~3.37%</td><td>~4.82%</td><td>~2.5%</td>
        <td class="gap-neg">-2.63pp</td><td class="gap-neg">-1.18pp</td>
        <td><span class="tag tag-fail">未达标</span></td>
      </tr>
      <tr>
        <td style="text-align:left;font-weight:700;">组合(主80%+B3 20%)</td>
        <td>~3.78%</td><td>~5.62%</td><td>~3.2%</td>
        <td class="gap-neg">-2.22pp</td><td class="gap-neg">-0.38pp</td>
        <td><span class="tag tag-fail">接近</span></td>
      </tr>
      <tr style="background:#f0fff4;">
        <td style="text-align:left;font-weight:700;">目标</td>
        <td>6.00%</td><td>6.00%</td><td>≤12%</td>
        <td>0</td><td>0</td>
        <td>—</td>
      </tr>
    </tbody>
  </table>

  <div class="verdict-box warn" style="margin-top:16px;">
    <div>
      <div class="v-title">差距诊断</div>
      <div class="v-body">
        B3独立年化已超目标，但10%配比下对组合贡献约+0.4~+0.9pp，组合仍差2~3pp。
        瓶颈在于主引擎年化仅2.97%(IS)/4.02%(OOS)，交易频率过低(2.5笔/年 vs 14A下限6笔)。
        下一步需主引擎端提升（P12扩大化/信号期望质变）或提高B3配比（需模拟盘≥6月验证后逐步调整）。
      </div>
    </div>
  </div>
</div>

<!-- Next Steps -->
<div class="section">
  <div class="section-title">
    <div class="icon" style="background:var(--teal)">09</div>
    结论与下一步
  </div>
  <div class="analysis-text">
    <strong>阶段1回测结论：</strong>
    <ul>
      <li><strong>候选A（ETF均值回归）</strong>：全否决。6变体均负收益，A股趋势型市场不适合均值回归策略，入场信号在反弹初期即被截断</li>
      <li><strong>候选B（个股精选）</strong>：B3为最优。闸门A≥10+得分≥70+P12v6，IS/OOS均超额6%目标，OOS>IS排除过拟合</li>
      <li><strong>候选C（P12v6叠加）</strong>：无增量。P12v6已在B3中默认开启，作为独立叠加层不产生额外价值</li>
      <li><strong>正交性</strong>：B3与主引擎信号无重叠(A∩B=0)，可安全并行运行</li>
    </ul>
    <br>
    <strong>推荐行动项：</strong>
    <ul>
      <li><strong>立即执行</strong>：B3进入模拟盘验证阶段，配比0→5%→10%渐进，模拟盘运行≥6个月</li>
      <li><strong>模拟盘达标条件</strong>：OOS年化≥6% + 最大回撤≤12% + 夏普≥1.5 + 交易频率≥4笔/年</li>
      <li><strong>同步推进</strong>：主引擎P12扩大化（当前唯一盈利出场，IS仅2笔触发），提升交易频率至14A下限6笔/年</li>
      <li><strong>配比调整</strong>：模拟盘达标后，B3配比可从10%逐步提升至15-20%，缩小组合年化缺口</li>
      <li><strong>风险监控</strong>：B3 IS回撤8.37%为所有变体最高，实盘需监控是否突破12%红线</li>
    </ul>
  </div>
</div>

<!-- Footer -->
<div class="footer">
  <div class="disclaimer">
    <strong>免责声明：</strong>本报告仅供研究参考，不构成个人投资建议。历史回测结果不代表未来收益。
    量化策略存在模型风险、市场风险和数据风险，投资者应根据自身风险承受能力审慎决策。
    所有回测基于历史数据，实际交易可能因滑点、冲击成本和市场环境变化而产生偏差。
  </div>
  <p>三层资金架构进攻线模拟盘 · 阶段1历史定参回测对比分析报告</p>
  <p>v4.7-R10 + JOINT固化 | 生成时间: {TS}</p>
</div>

</div>

<script>
// ========== Chart 1: IS vs OOS Annualized Return ==========
(function(){{
  var chart = echarts.init(document.getElementById('chart_annret'));
  var option = {{
    tooltip: {{ trigger: 'axis', axisPointer: {{ type: 'shadow' }} }},
    legend: {{ data: ['IS年化(6年)', 'OOS年化(1.5年)'], top: 8 }},
    grid: {{ left: 50, right: 30, top: 50, bottom: 40 }},
    xAxis: {{ type: 'category', data: {json.dumps(bar_labels)} }},
    yAxis: {{ type: 'value', name: '年化%', axisLine: {{lineStyle:{{color:'#cbd5e0'}}}} }},
    series: [
      {{
        name: 'IS年化(6年)', type: 'bar',
        data: {json.dumps(bar_is)},
        itemStyle: {{
          color: function(p) {{ return p.value < 0 ? '#e53e3e' : '#38a169'; }},
          borderRadius: [4, 4, 0, 0]
        }},
        barWidth: 28,
        label: {{ show: true, position: 'top', formatter: '{{c}}%', fontSize: 10 }}
      }},
      {{
        name: 'OOS年化(1.5年)', type: 'bar',
        data: {json.dumps(bar_oos)},
        itemStyle: {{
          color: function(p) {{ return p.value < 0 ? '#fc8181' : '#68d391'; }},
          borderRadius: [4, 4, 0, 0]
        }},
        barWidth: 28,
        label: {{ show: true, position: 'top', formatter: '{{c}}%', fontSize: 10 }}
      }}
    ]
  }};
  // Add 6% target line
  option.series[0].markLine = {{
    silent: true, symbol: 'none',
    lineStyle: {{ color: '#dd6b20', type: 'dashed', width: 1.5 }},
    data: [{{ yAxis: 6, label: {{ formatter: '6%目标', fontSize: 10, color: '#dd6b20' }} }}]
  }};
  chart.setOption(option);
  window.addEventListener('resize', function(){{ chart.resize(); }});
}})();

// ========== Chart 2: Candidate A Trade PnL ==========
(function(){{
  var chart = echarts.init(document.getElementById('chart_a_pnl'));
  chart.setOption({{
    title: {{ text: '候选A — 交易PnL对比', left: 'center', textStyle: {{ fontSize: 14 }} }},
    tooltip: {{ trigger: 'axis', formatter: function(p) {{ return p[0].name + '<br/>交易PnL: ' + (p[0].value>=0?'+':'') + p[0].value.toLocaleString(); }} }},
    grid: {{ left: 60, right: 20, top: 50, bottom: 30 }},
    xAxis: {{ type: 'category', data: ['A1_IS','A1_OOS','A2_IS','A2_OOS','A3_IS','A3_OOS'] }},
    yAxis: {{ type: 'value', name: 'PnL', axisLabel: {{ formatter: function(v){{ return (v/1000)+'K'; }} }} }},
    series: [{{
      type: 'bar',
      data: {[R['A1_IS']['trade_pnl'], R['A1_OOS']['trade_pnl'], R['A2_IS']['trade_pnl'], R['A2_OOS']['trade_pnl'], R['A3_IS']['trade_pnl'], R['A3_OOS']['trade_pnl']]},
      itemStyle: {{ color: '#e53e3e', borderRadius: [4,4,0,0] }},
      barWidth: 30
    }}]
  }});
  window.addEventListener('resize', function(){{ chart.resize(); }});
}})();

// ========== Chart 3: Candidate A Win Rate ==========
(function(){{
  var chart = echarts.init(document.getElementById('chart_a_winrate'));
  chart.setOption({{
    title: {{ text: '候选A — 胜率对比', left: 'center', textStyle: {{ fontSize: 14 }} }},
    tooltip: {{ trigger: 'axis', formatter: '{{b}}<br/>胜率: {{c}}%' }},
    grid: {{ left: 50, right: 20, top: 50, bottom: 30 }},
    xAxis: {{ type: 'category', data: ['A1_IS','A1_OOS','A2_IS','A2_OOS','A3_IS','A3_OOS'] }},
    yAxis: {{ type: 'value', name: '%', min: 30, max: 60 }},
    series: [{{
      type: 'bar',
      data: {[R['A1_IS']['win_rate'], R['A1_OOS']['win_rate'], R['A2_IS']['win_rate'], R['A2_OOS']['win_rate'], R['A3_IS']['win_rate'], R['A3_OOS']['win_rate']]},
      itemStyle: {{ color: '#fc8181', borderRadius: [4,4,0,0] }},
      barWidth: 30,
      markLine: {{ silent: true, symbol: 'none', lineStyle: {{color:'#dd6b20',type:'dashed'}}, data: [{{ yAxis: 50, label:{{ formatter:'50%',fontSize:10 }} }}] }}
    }}]
  }});
  window.addEventListener('resize', function(){{ chart.resize(); }});
}})();

// ========== Chart 4: Candidate B Trade PnL ==========
(function(){{
  var chart = echarts.init(document.getElementById('chart_b_pnl'));
  chart.setOption({{
    title: {{ text: '候选B — 交易PnL对比', left: 'center', textStyle: {{ fontSize: 14 }} }},
    tooltip: {{ trigger: 'axis', formatter: function(p) {{ return p[0].name + '<br/>交易PnL: ' + (p[0].value>=0?'+':'') + p[0].value.toLocaleString(); }} }},
    grid: {{ left: 60, right: 20, top: 50, bottom: 30 }},
    xAxis: {{ type: 'category', data: ['B1_IS','B1_OOS','B2_IS','B2_OOS','B3_IS','B3_OOS'] }},
    yAxis: {{ type: 'value', name: 'PnL', axisLabel: {{ formatter: function(v){{ return (v/1000)+'K'; }} }} }},
    series: [{{
      type: 'bar',
      data: {[R['B1_IS']['trade_pnl'], R['B1_OOS']['trade_pnl'], R['B2_IS']['trade_pnl'], R['B2_OOS']['trade_pnl'], R['B3_IS']['trade_pnl'], R['B3_OOS']['trade_pnl']]},
      itemStyle: {{
        color: function(p) {{ var labels=['B1_IS','B1_OOS','B2_IS','B2_OOS','B3_IS','B3_OOS']; return labels[p.dataIndex] === 'B3_IS' || labels[p.dataIndex] === 'B3_OOS' ? '#38a169' : '#9ae6b4'; }},
        borderRadius: [4,4,0,0]
      }},
      barWidth: 30,
      label: {{ show: true, position: 'top', formatter: function(p){{ return (p.value/1000).toFixed(0)+'K'; }}, fontSize: 10 }}
    }}]
  }});
  window.addEventListener('resize', function(){{ chart.resize(); }});
}})();

// ========== Chart 5: Candidate B Expectancy ==========
(function(){{
  var chart = echarts.init(document.getElementById('chart_b_expectancy'));
  chart.setOption({{
    title: {{ text: '候选B — 单笔期望对比', left: 'center', textStyle: {{ fontSize: 14 }} }},
    tooltip: {{ trigger: 'axis', formatter: function(p) {{ return p[0].name + '<br/>期望/笔: ' + (p[0].value>=0?'+':'') + p[0].value.toFixed(0); }} }},
    grid: {{ left: 60, right: 20, top: 50, bottom: 30 }},
    xAxis: {{ type: 'category', data: ['B1_IS','B1_OOS','B2_IS','B2_OOS','B3_IS','B3_OOS'] }},
    yAxis: {{ type: 'value', name: '期望/笔' }},
    series: [{{
      type: 'bar',
      data: {[R['B1_IS']['expectancy'], R['B1_OOS']['expectancy'], R['B2_IS']['expectancy'], R['B2_OOS']['expectancy'], R['B3_IS']['expectancy'], R['B3_OOS']['expectancy']]},
      itemStyle: {{
        color: function(p) {{ var labels=['B1_IS','B1_OOS','B2_IS','B2_OOS','B3_IS','B3_OOS']; return labels[p.dataIndex] === 'B3_IS' || labels[p.dataIndex] === 'B3_OOS' ? '#38a169' : '#9ae6b4'; }},
        borderRadius: [4,4,0,0]
      }},
      barWidth: 30,
      label: {{ show: true, position: 'top', formatter: '{{c}}', fontSize: 10 }}
    }}]
  }});
  window.addEventListener('resize', function(){{ chart.resize(); }});
}})();

// ========== Chart 6: Win Rate Comparison ==========
(function(){{
  var chart = echarts.init(document.getElementById('chart_winrate'));
  chart.setOption({{
    title: {{ text: '胜率对比：IS vs OOS', left: 'center', textStyle: {{ fontSize: 14 }} }},
    tooltip: {{ trigger: 'axis' }},
    legend: {{ data: ['IS', 'OOS'], top: 30 }},
    grid: {{ left: 50, right: 20, top: 60, bottom: 30 }},
    xAxis: {{ type: 'category', data: {json.dumps(win_labels)} }},
    yAxis: {{ type: 'value', name: '%', min: 30, max: 65 }},
    series: [
      {{ name: 'IS', type: 'bar', data: {json.dumps(win_is)}, itemStyle: {{ color: '#63b3ed', borderRadius:[4,4,0,0] }}, barWidth: 24 }},
      {{ name: 'OOS', type: 'bar', data: {json.dumps(win_oos)}, itemStyle: {{ color: '#f6ad55', borderRadius:[4,4,0,0] }}, barWidth: 24 }}
    ]
  }});
  window.addEventListener('resize', function(){{ chart.resize(); }});
}})();

// ========== Chart 7: Drawdown Comparison ==========
(function(){{
  var chart = echarts.init(document.getElementById('chart_drawdown'));
  chart.setOption({{
    title: {{ text: '最大回撤对比：IS vs OOS', left: 'center', textStyle: {{ fontSize: 14 }} }},
    tooltip: {{ trigger: 'axis', formatter: '{{b}}<br/>IS: {{c0}}%<br/>OOS: {{c1}}%' }},
    legend: {{ data: ['IS', 'OOS'], top: 30 }},
    grid: {{ left: 50, right: 20, top: 60, bottom: 30 }},
    xAxis: {{ type: 'category', data: {json.dumps(dd_labels)} }},
    yAxis: {{ type: 'value', name: '%', max: 12 }},
    series: [
      {{ name: 'IS', type: 'bar', data: {json.dumps(dd_is)}, itemStyle: {{ color: '#fc8181', borderRadius:[4,4,0,0] }}, barWidth: 24 }},
      {{ name: 'OOS', type: 'bar', data: {json.dumps(dd_oos)}, itemStyle: {{ color: '#fbd38d', borderRadius:[4,4,0,0] }}, barWidth: 24 }}
    ]
  }});
  window.addEventListener('resize', function(){{ chart.resize(); }});
}})();
</script>

</body>
</html>
"""

with open(OUT_HTML, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Report generated: {OUT_HTML}")
print(f"File size: {os.path.getsize(OUT_HTML):,} bytes")
