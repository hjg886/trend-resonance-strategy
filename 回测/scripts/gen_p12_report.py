# -*- coding: utf-8 -*-
"""P12 移动止盈引擎扩大化 HTML 报告生成器"""
import json, os, sys, math

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "output")
SCRIPTS = os.path.dirname(__file__)
sys.path.insert(0, SCRIPTS)
import run_backtest as RB

UNIV = RB.UNIVERSE if RB.R9_UNIV_ON else {}

LABELS = ["JOINT", "P12v1", "P12v2", "P12v3", "P12v4", "P12v5", "P12v6"]
DESCS = {
    "JOINT": "基线: 15%门槛, 回撤50/40/30%",
    "P12v1": "门槛10%, 回撤不变50/40/30%",
    "P12v2": "门槛8%, 新增低档55%, 回撤55/50/40/30%",
    "P12v3": "门槛8%, 全档收紧50/45/35/25%",
    "P12v4": "门槛5%, 全档最紧50/45/35/25%",
    "P12v5": "15%门槛, 仅高档收紧50/45/35/25%",
    "P12v6": "15%门槛, 核心档收紧45/35/25%",
}
THRESH = {
    "JOINT": "15%", "P12v1": "10%", "P12v2": "8%", "P12v3": "8%",
    "P12v4": "5%", "P12v5": "15%", "P12v6": "15%",
}
RETR = {
    "JOINT": "50/40/30%", "P12v1": "50/40/30%", "P12v2": "55/50/40/30%",
    "P12v3": "50/45/35/25%", "P12v4": "50/45/35/25%",
    "P12v5": "50/45/35/25%", "P12v6": "45/35/25%",
}

G = {}
for L in LABELS:
    path = os.path.join(OUT, f"variant_{L}.json")
    if os.path.exists(path):
        G[L] = json.load(open(path, encoding="utf-8"))

def fmt(v, suf="%", dec=2, sign=False):
    if v != v: return "--"
    body = ("%+." if sign else "%.") + str(dec) + "f"
    return (body % v) + suf

def chk(b):
    return f'<span class="{"v-pass" if b else "v-fail"}">{"Y" if b else "N"}</span>'

# ========== IS comparison rows ==========
def is_row(L):
    if L not in G: return ""
    d = G[L]; m = d.get("metrics_in", {})
    if not m: return ""
    pnl = d.get("in", {}).get("pnl_amt", 0)
    p12c = d.get("in", {}).get("p12_count", 0)
    p12p = d.get("in", {}).get("p12_pnl", 0)
    if p12c == 0:
        cl = d.get("closed_in", [])
        p12c = sum(1 for c in cl if "P12" in str(c.get("exit_reason", "")))
        p12p = sum(float(c.get("pnl", 0)) for c in cl if "P12" in str(c.get("exit_reason", "")))
    ec = "best" if L == "P12v6" else ""
    return f"""<tr class="{ec}">
<td><strong>{L}</strong></td><td>{THRESH.get(L,'')}</td><td>{RETR.get(L,'')}</td>
<td>{m.get('n_buys',0)}</td><td>{m.get('freq_annual',0):.1f}</td>
<td class="{'pos' if m.get('avg_pnl_pct',0)>0 else 'neg'}">{fmt(m.get('avg_pnl_pct',0),sign=True)}</td>
<td>{fmt(m.get('ann_return',0))}</td><td>{fmt(m.get('max_drawdown',0))}</td>
<td>{m.get('sharpe',0):.2f}</td><td>{m.get('win_rate',0):.1f}%</td>
<td>{p12c}</td><td>{p12p:+,.0f}</td><td>{pnl:+,.0f}</td></tr>"""

def oos_row(L):
    if L not in G: return ""
    d = G[L]; m = d.get("metrics_oos", {})
    if not m: return ""
    pnl = d.get("oos", {}).get("pnl_amt", 0)
    p12c = d.get("oos", {}).get("p12_count", 0)
    p12p = d.get("oos", {}).get("p12_pnl", 0)
    if p12c == 0:
        cl = d.get("closed_oos", [])
        p12c = sum(1 for c in cl if "P12" in str(c.get("exit_reason", "")))
        p12p = sum(float(c.get("pnl", 0)) for c in cl if "P12" in str(c.get("exit_reason", "")))
    ec = "best" if L == "P12v6" else ""
    return f"""<tr class="{ec}">
<td><strong>{L}</strong></td>
<td>{m.get('n_buys',0)}</td>
<td class="{'pos' if m.get('avg_pnl_pct',0)>0 else 'neg'}">{fmt(m.get('avg_pnl_pct',0),sign=True)}</td>
<td>{fmt(m.get('ann_return',0))}</td><td>{fmt(m.get('max_drawdown',0))}</td>
<td>{m.get('sharpe',0):.2f}</td><td>{m.get('win_rate',0):.1f}%</td>
<td>{p12c}</td><td>{p12p:+,.0f}</td><td>{pnl:+,.0f}</td></tr>"""

is_rows = "".join(is_row(L) for L in LABELS)
oos_rows = "".join(oos_row(L) for L in LABELS)

# ========== 14A verdict ==========
def verdict_row(L):
    if L not in G: return ""
    m = G[L].get("metrics_in", {})
    if not m: return ""
    c1 = m.get("freq_annual", 0) >= 6.0
    c2 = (m.get("avg_pnl_pct", 0) == m.get("avg_pnl_pct", 0)) and m.get("avg_pnl_pct", 0) > 0
    c3 = m.get("ann_return", 0) >= 6.0
    c4 = m.get("max_drawdown", 0) <= 12.0
    ok = all([c1, c2, c3, c4])
    return f"""<tr>
<td><strong>{L}</strong></td><td>{THRESH.get(L,'')}</td><td>{RETR.get(L,'')}</td>
<td>{chk(c1)}</td><td>{chk(c2)}</td><td>{chk(c3)}</td><td>{chk(c4)}</td>
<td class="{'v-pass' if ok else 'v-fail'}">{'PASS' if ok else 'FAIL'}</td></tr>"""

verdict_rows = "".join(verdict_row(L) for L in LABELS)

# ========== P12 trade details ==========
def p12_detail_rows(L):
    if L not in G: return ""
    d = G[L]
    rows = ""
    for seg, cl_key in [("IS", "closed_in"), ("OOS", "closed_oos")]:
        cl = d.get(cl_key, [])
        for c in cl:
            reason = str(c.get("exit_reason", ""))
            if "P12" in reason:
                code = c.get("code", "")
                name = UNIV.get(code, (None, code))[1] if isinstance(UNIV.get(code), tuple) else code
                pnl = c.get("pnl", 0)
                hold = c.get("hold_days", 0)
                # extract profit% and retr% from reason
                import re
                pm = re.search(r'\u6d6e\u76c8(\d+)%', reason)
                profit_str = pm.group(1) + "%" if pm else "--"
                rm = re.search(r'\u56de\u64a4(\d+)%', reason)
                retr_str = rm.group(1) + "%" if rm else "--"
                cls = "pos" if pnl > 0 else "neg"
                rows += f"""<tr><td>{L}</td><td>{seg}</td><td>{code}</td><td>{name}</td>
<td>{profit_str}</td><td>{hold}</td><td class="{cls}">{pnl:+,.0f}</td>
<td>{reason}</td></tr>"""
    return rows

p12_rows = "".join(p12_detail_rows(L) for L in LABELS)

# ========== IS exit breakdown ==========
def exit_breakdown_row(L):
    if L not in G: return ""
    d = G[L]
    cl = d.get("closed_in", [])
    if not cl: return ""
    bd = {}
    for c in cl:
        reason = str(c.get("exit_reason", "unknown"))
        parts = reason.split("-")
        prefix = parts[0].split("/")[0] if "/" in parts[0] else parts[0]
        bd[prefix] = bd.get(prefix, 0) + 1
    bd_str = ", ".join(f"{k}={v}" for k, v in sorted(bd.items()))
    pnl_by = {}
    for c in cl:
        reason = str(c.get("exit_reason", "unknown"))
        parts = reason.split("-")
        prefix = parts[0].split("/")[0] if "/" in parts[0] else parts[0]
        pnl_by.setdefault(prefix, 0)
        pnl_by[prefix] += float(c.get("pnl", 0))
    pnl_str = ", ".join(f"{k}={v:+,.0f}" for k, v in sorted(pnl_by.items()))
    ec = "best" if L == "P12v6" else ""
    return f'<tr class="{ec}"><td><strong>{L}</strong></td><td>{THRESH.get(L,"")}</td><td>{RETR.get(L,"")}</td><td>{bd_str}</td><td>{pnl_str}</td></tr>'

exit_rows = "".join(exit_breakdown_row(L) for L in LABELS)

# ========== Delta analysis ==========
def delta_row(L):
    if L not in G or "JOINT" not in G: return ""
    d = G[L]; j = G["JOINT"]
    mi = d.get("metrics_in", {}); ji = j.get("metrics_in", {})
    if not mi or not ji: return ""
    dp = d.get("in", {}).get("pnl_amt", 0) - j.get("in", {}).get("pnl_amt", 0)
    dp12 = d.get("in", {}).get("p12_pnl", 0) - j.get("in", {}).get("p12_pnl", 0)
    de = mi.get("avg_pnl_pct", 0) - ji.get("avg_pnl_pct", 0)
    da = mi.get("ann_return", 0) - ji.get("ann_return", 0)
    ds = mi.get("sharpe", 0) - ji.get("sharpe", 0)
    db = mi.get("n_buys", 0) - ji.get("n_buys", 0)
    def sign_fmt(v, suf=""):
        return f"{v:+.2f}{suf}" if suf == "" else f"{v:+.0f}{suf}"
    ec = "best" if L == "P12v6" else ""
    return f"""<tr class="{ec}">
<td><strong>{L}</strong></td><td>{THRESH.get(L,'')}</td><td>{RETR.get(L,'')}</td>
<td>{db:+d}</td><td>{de:+.2f}pp</td><td>{da:+.2f}pp</td>
<td>{ds:+.2f}</td><td>{dp12:+,.0f}</td><td>{dp:+,.0f}</td></tr>"""

delta_rows = "".join(delta_row(L) for L in LABELS if L != "JOINT")

# ========== Chart data ==========
chart_labels = json.dumps([L for L in LABELS if L in G], ensure_ascii=False)
chart_ann_is = [G[L]["metrics_in"].get("ann_return", 0) for L in LABELS if L in G]
chart_ann_oos = [G[L]["metrics_oos"].get("ann_return", 0) for L in LABELS if L in G]
chart_sharpe_is = [G[L]["metrics_in"].get("sharpe", 0) for L in LABELS if L in G]
chart_pnl_is = [G[L].get("in", {}).get("pnl_amt", 0) for L in LABELS if L in G]
chart_p12_pnl = [G[L].get("in", {}).get("p12_pnl", 0) for L in LABELS if L in G]
chart_buys = [G[L]["metrics_in"].get("n_buys", 0) for L in LABELS if L in G]

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>P12 移动止盈引擎扩大化 - 回测验证报告</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif; background:#f5f5f5; color:#333; line-height:1.7; padding:20px; max-width:1400px; margin:0 auto; }}
h1 {{ font-size:24px; color:#1a1a2e; margin:20px 0 5px; border-bottom:3px solid #e94560; padding-bottom:8px; }}
h2 {{ font-size:18px; color:#16213e; margin:25px 0 10px; border-left:4px solid #e94560; padding-left:10px; }}
h3 {{ font-size:15px; color:#0f3460; margin:15px 0 8px; }}
.subtitle {{ color:#666; font-size:13px; margin-bottom:15px; }}
table {{ width:100%; border-collapse:collapse; margin:10px 0; font-size:13px; background:#fff; box-shadow:0 1px 3px rgba(0,0,0,0.1); }}
th {{ background:#1a1a2e; color:#fff; padding:8px 6px; text-align:center; font-weight:600; white-space:nowrap; }}
td {{ padding:7px 6px; border-bottom:1px solid #eee; text-align:center; white-space:nowrap; }}
tr.best {{ background:#fff8e1; }}
tr.best td:first-child {{ border-left:3px solid #e94560; }}
tr:hover {{ background:#f0f0ff; }}
.pos {{ color:#c62828; font-weight:600; }}
.neg {{ color:#2e7d32; font-weight:600; }}
.v-pass {{ color:#2e7d32; font-weight:bold; }}
.v-fail {{ color:#c62828; font-weight:bold; }}
.box {{ background:#fff; padding:15px 20px; margin:10px 0; border-radius:8px; box-shadow:0 2px 6px rgba(0,0,0,0.08); }}
.box h3 {{ margin-top:0; }}
.finding {{ background:#fff; border-left:4px solid #e94560; padding:12px 16px; margin:8px 0; border-radius:0 8px 8px 0; font-size:14px; }}
.finding strong {{ color:#e94560; }}
.note {{ background:#e8f5e9; padding:10px 15px; border-radius:6px; margin:8px 0; font-size:13px; }}
.warn {{ background:#fff3cd; padding:10px 15px; border-radius:6px; margin:8px 0; font-size:13px; }}
.chart-box {{ background:#fff; padding:15px; border-radius:8px; margin:15px 0; box-shadow:0 2px 6px rgba(0,0,0,0.08); }}
.chart {{ height:350px; }}
.grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:15px; }}
.disclaimer {{ margin-top:30px; padding:15px; background:#f8f9fa; border-top:2px solid #dee2e6; font-size:12px; color:#6c757d; }}
.tag {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600; }}
.tag-best {{ background:#e94560; color:#fff; }}
.tag-same {{ background:#e0e0e0; color:#666; }}
.tag-worse {{ background:#ffebee; color:#c62828; }}
</style>
</head>
<body>

<h1>P12 移动止盈引擎扩大化 - 回测验证报告</h1>
<div class="subtitle">v4.7-R10 | 基于 JOINT 基线(F04a x P0d) | 7 变体扫描 | 2026-08-18</div>

<div class="box">
<h3>背景与命题</h3>
<p style="font-size:14px;">
<b>P12 移动止盈</b>是策略中唯一的盈利出场引擎。在 JOINT 基线回测中：
IS 12 笔平仓中 P12 仅 2 笔但贡献 +33,014 元（占总交易 PnL 的 124%）；
OOS 5 笔平仓中 P12 仅 1 笔贡献 +7,415 元。
P12 触发频率极低（6 年仅 2 笔）是制约年化收益的核心瓶颈之一。
</p>
<p style="font-size:14px; margin-top:8px;">
<b>扩大化方向</b>：① 降低激活门槛（15%→10%/8%/5%，让更多浮盈仓位进入 P12 保护）；
② 收紧回撤率（50/40/30%→50/45/35/25%，在触发后保护更多利润）。
<b>基线</b>：JOINT = H1(S1 禁 ETF) + BREADTH 否决 + 7/4 宽带宽 + F04a(x1.5) + P12 默认(15% 门槛, 回撤 50/40/30%)
</p>
</div>

<h2>一、样本内核心对比（6 年 IS 2019-2024）</h2>
<table>
<tr><th>配置</th><th>门槛</th><th>回撤率</th><th>建仓</th><th>年建仓</th><th>期望%/笔</th><th>年化%</th><th>回撤%</th><th>夏普</th><th>胜率%</th><th>P12笔</th><th>P12盈亏</th><th>交易PnL</th></tr>
{is_rows}
</table>
<div class="note">
<span class="tag tag-best">P12v6</span> = 最优配置（15% 门槛 + 回撤 45/35/25%）：
IS 年化 2.97%（+0.36pp）、Sharpe 1.83（+0.21）、交易 PnL +32,368（+21%）、P12 PnL +39,267（+19%），且 OOS 完全保持。
</div>

<h2>二、样本外核心对比（18 月 OOS 2025.01-2026.06）</h2>
<table>
<tr><th>配置</th><th>建仓</th><th>期望%/笔</th><th>年化%</th><th>回撤%</th><th>夏普</th><th>胜率%</th><th>P12笔</th><th>P12盈亏</th><th>交易PnL</th></tr>
{oos_rows}
</table>
<div class="warn">
<b>OOS 关键发现</b>：降低门槛（8%/5%）的变体（v2/v3/v4）OOS 全面恶化——
期望 -1.93%→-2.28%、交易 PnL -1,911→-10,754。
根因：8% 门槛在 OOS 触发 512480 提前止盈（+8% 浮盈仅回撤 50%→-210 元亏损出场），
释放资金后重新建仓同一标的遭遇 E-P1 止损（-14,656 元），"早出再进"反而放大亏损。
<b>P12v6（15% 门槛）OOS 与 JOINT 完全一致，零恶化</b>。
</div>

<div class="grid2">
<div class="chart-box">
<div id="chart_ann" class="chart"></div>
</div>
<div class="chart-box">
<div id="chart_sharpe" class="chart"></div>
</div>
</div>

<div class="grid2">
<div class="chart-box">
<div id="chart_pnl" class="chart"></div>
</div>
<div class="chart-box">
<div id="chart_buys" class="chart"></div>
</div>
</div>

<h2>三、增量分析（vs JOINT 基线）</h2>
<table>
<tr><th>配置</th><th>门槛</th><th>回撤率</th><th>建仓Δ</th><th>期望Δ</th><th>年化Δ</th><th>夏普Δ</th><th>P12PnLΔ</th><th>交易PnLΔ</th></tr>
{delta_rows}
</table>

<div class="finding">
<strong>发现 1：降低门槛 IS 无效</strong>
P12v1(10%) 和 P12v2(8%) 在 IS 中与 JOINT 逐位一致。
原因：6 年内无任何持仓的最高浮盈落入 8-15% 区间——
要么不到 8%（P12 未激活），要么直接冲过 15%（进入现有 P12 保护）。
门槛下移在 IS 中是<b>死参数</b>，不产生任何行为变化。
</div>

<div class="finding">
<strong>发现 2：降低门槛 OOS 有害</strong>
P12v2/v3/v4（门槛 8%/5%）在 OOS 中触发了一次 512480 的 8% 浮盈 P12 止盈，
但回撤率 50-55% 导致实际出场价低于成本（-210 元亏损），
随后重新建仓同一标的遭遇 -14,656 元 E-P1 止损。
"低门槛→早止盈→再进场→大亏损"的链条使 OOS 交易 PnL 从 -1,911 恶化至 -10,754。
</div>

<div class="finding">
<strong>发现 3：收紧回撤率是有效杠杆</strong>
P12v3/v6 通过将 15-30% 浮盈档的回撤率从 50% 收紧至 45%，
使 512480 的 P12 出场从 +12,229 提升至 +18,481（+51%），
并提前 1 日释放资金，使 IS 建仓从 13 笔增至 17 笔（+31%）。
P12 总盈亏从 +33,014 提升至 +39,267（+19%），
交易 PnL 从 +26,641 提升至 +32,368（+21%），
Sharpe 从 1.62 提升至 1.83（+0.21）。
</div>

<div class="finding">
<strong>发现 4：P12v6 是最优清洁变体</strong>
P12v6（15% 门槛 + 回撤 45/35/25%）= P12v3 的 IS 改善 + JOINT 的 OOS 稳定性。
与 P12v3 的唯一区别是门槛保持 15%（而非 8%），
消除了 OOS 中低门槛触发的"早出再进"灾难。
IS 指标与 P12v3 完全一致，OOS 指标与 JOINT 完全一致。
</div>

<h2>四、P12 逐笔明细</h2>
<table>
<tr><th>配置</th><th>区间</th><th>代码</th><th>名称</th><th>浮盈</th><th>持有日</th><th>盈亏</th><th>出场原因</th></tr>
{p12_rows}
</table>
<div class="note">
6 年 IS 中仅 2 笔 P12 出场（510300 浮盈 21%、512480 浮盈 25%），
P12v4 额外触发 2 笔微利 P12（512400/510880 浮盈 6%，分别仅 +40/+6 元），
说明门槛降至 5-8% 虽然增加 P12 笔数，但新增的都是微利/噪音出场。
</div>

<h2>五、IS 出场机制分布</h2>
<table>
<tr><th>配置</th><th>门槛</th><th>回撤率</th><th>出场笔数分布</th><th>出场盈亏分布</th></tr>
{exit_rows}
</table>

<h2>六、14A 验收判定</h2>
<table>
<tr><th>配置</th><th>门槛</th><th>回撤率</th><th>年建仓>=6</th><th>期望>0</th><th>年化>=6%</th><th>回撤<=12%</th><th>判定</th></tr>
{verdict_rows}
</table>
<div class="warn">
<b>全部未达标</b>：最高 IS 年化 2.97%（P12v3/v6），最高 OOS 年化 4.02%（JOINT/v1/v5/v6），
均未达 6% 目标。P12 引擎扩大化将 IS 交易 PnL 从 +26,641 提升至 +32,368（+21%），
但缺口仍达 24.2 万元（= 274,602 - (32,368-9,679) / 9,679 * 274,602 的线性外推）。
<b>瓶颈未变</b>：交易频率 2.8 笔/年（IS）远低于 14A 下限 6 笔；P12 仍仅 2 笔触发（6 年）。
</div>

<h2>七、结论与固化裁决</h2>
<div class="box">
<h3>7.1 最优配置：P12v6</h3>
<table>
<tr><th>参数</th><th>JOINT 基线</th><th>P12v6 最优</th><th>变化</th></tr>
<tr><td>激活门槛</td><td>15%</td><td>15%</td><td>不变</td></tr>
<tr><td>15-30% 回撤率</td><td>50%</td><td><b>45%</b></td><td><span class="v-pass">收紧 5pp</span></td></tr>
<tr><td>30-50% 回撤率</td><td>40%</td><td><b>35%</b></td><td><span class="v-pass">收紧 5pp</span></td></tr>
<tr><td>>=50% 回撤率</td><td>30%</td><td><b>25%</b></td><td><span class="v-pass">收紧 5pp</span></td></tr>
</table>

<h3>7.2 核心数据对比</h3>
<table>
<tr><th>指标</th><th>JOINT</th><th>P12v6</th><th>增量</th><th>评价</th></tr>
<tr><td>IS 建仓笔数</td><td>13</td><td>17</td><td>+4</td><td><span class="v-pass">+31% 频率</span></td></tr>
<tr><td>IS 期望/笔</td><td>+1.31%</td><td>+1.13%</td><td>-0.18pp</td><td>略降(更多小亏单)</td></tr>
<tr><td>IS 年化</td><td>2.61%</td><td>2.97%</td><td>+0.36pp</td><td><span class="v-pass">改善</span></td></tr>
<tr><td>IS 回撤</td><td>1.85%</td><td>1.81%</td><td>-0.04pp</td><td><span class="v-pass">改善</span></td></tr>
<tr><td>IS 夏普</td><td>1.62</td><td>1.83</td><td>+0.21</td><td><span class="v-pass">显著改善</span></td></tr>
<tr><td>IS P12 盈亏</td><td>+33,014</td><td>+39,267</td><td>+6,253</td><td><span class="v-pass">+19%</span></td></tr>
<tr><td>IS 交易 PnL</td><td>+26,641</td><td>+32,368</td><td>+5,727</td><td><span class="v-pass">+21%</span></td></tr>
<tr><td>OOS 年化</td><td>4.02%</td><td>4.02%</td><td>0</td><td><span class="v-pass">零恶化</span></td></tr>
<tr><td>OOS 回撤</td><td>1.60%</td><td>1.60%</td><td>0</td><td><span class="v-pass">零恶化</span></td></tr>
<tr><td>OOS 交易 PnL</td><td>-1,911</td><td>-1,911</td><td>0</td><td><span class="v-pass">零恶化</span></td></tr>
</table>

<h3>7.3 固化裁决</h3>
<div class="finding">
<strong>P12 回撤率收紧固化为新基线</strong>：P12v6 参数（15% 门槛 + 回撤 45/35/25%）
替换 JOINT 的 P12 默认参数（15% 门槛 + 回撤 50/40/30%），
作为 F04a x P0d 联合基线的 P12 正式参数。
</div>
<div class="finding">
<strong>门槛下移否决</strong>：激活门槛维持 15% 不变。
8%/5% 门槛在 IS 中无效（无持仓浮盈落入 8-15% 区间），
在 OOS 中有害（低门槛触发"早出再进"灾难链：-210→-14,656）。
</div>
<div class="finding">
<strong>机制洞察</strong>：P12 引擎扩大化的有效路径不是"降低门槛让更多仓位进入保护"，
而是"收紧回撤率在已触发的仓位上保护更多利润"。
6 年仅 2 笔 P12 触发（浮盈 21%/25%）说明瓶颈不在门槛，
而在"有多少仓位能达到 15%+ 浮盈"——这是信号质量问题，非 P12 参数可修。
</div>
<div class="finding">
<strong>瓶颈未变</strong>：P12v6 将 IS 交易 PnL 从 +26,641 提升至 +32,368（+21%），
但距 6% 年化缺口（约 27.5 万元）仍差 24.2 万元。
交易频率 2.8 笔/年仍远低于 14A 下限 6 笔。
下一主攻方向不变：三层资金架构进攻线模拟盘（候选=ETF 均值回归/个股精选）。
</div>
</div>

<h2>八、7 变体参数速查</h2>
<table>
<tr><th>配置</th><th>门槛</th><th>回撤率档位</th><th>设计意图</th><th>IS 结果</th><th>OOS 结果</th></tr>
<tr><td><b>JOINT</b></td><td>15%</td><td>50/40/30%</td><td>基线</td><td>13 笔 / +1.31% / 2.61%</td><td>6 笔 / -1.93% / 4.02%</td></tr>
<tr><td>P12v1</td><td>10%</td><td>50/40/30%</td><td>仅降门槛</td><td><span class="tag tag-same">= JOINT</span></td><td><span class="tag tag-same">= JOINT</span></td></tr>
<tr><td>P12v2</td><td>8%</td><td>55/50/40/30%</td><td>降门槛+新增低档</td><td><span class="tag tag-same">= JOINT</span></td><td><span class="tag tag-worse">恶化</span></td></tr>
<tr><td>P12v3</td><td>8%</td><td>50/45/35/25%</td><td>降门槛+全档收紧</td><td>17 笔 / +1.13% / 2.97%</td><td><span class="tag tag-worse">恶化</span></td></tr>
<tr><td>P12v4</td><td>5%</td><td>50/45/35/25%</td><td>最低门槛+最紧</td><td>17 笔 / +1.62% / 2.97%</td><td><span class="tag tag-worse">恶化</span></td></tr>
<tr><td>P12v5</td><td>15%</td><td>50/45/35/25%</td><td>不降门槛+高档收紧</td><td><span class="tag tag-same">= JOINT</span></td><td><span class="tag tag-same">= JOINT</span></td></tr>
<tr class="best"><td><b>P12v6</b></td><td>15%</td><td><b>45/35/25%</b></td><td><b>不降门槛+核心档收紧</b></td><td><b>17 笔 / +1.13% / 2.97%</b></td><td><b>6 笔 / -1.93% / 4.02%</b></td></tr>
</table>
<div class="note">
<b>P12v5 vs P12v6 的区别</b>：P12v5 回撤率 50/45/35/25%（第一档仍 50%），P12v6 回撤率 45/35/25%（第一档收紧至 45%）。
P12v5 = JOINT 逐位一致（说明 30%+ 高档收紧无效果，因无持仓达到 30%+ 浮盈）；
P12v6 = P12v3 IS 逐位一致 + JOINT OOS 逐位一致（说明 15-30% 档收紧是唯一有效杠杆）。
</div>

<div class="disclaimer">
本报告仅供研究参考，不构成个人投资建议。回测结果基于历史数据，不代表未来表现。
策略 v4.7-R10 当前状态：G 系列四配置全部未达标，禁止实盘新建仓。存量持仓按原规则管理。
</div>

<script>
var chartLabels = {chart_labels};
var chartAnnIS = {json.dumps(chart_ann_is)};
var chartAnnOOS = {json.dumps(chart_ann_oos)};
var chartSharpeIS = {json.dumps(chart_sharpe_is)};
var chartPnlIS = {json.dumps(chart_pnl_is)};
var chartP12Pnl = {json.dumps(chart_p12_pnl)};
var chartBuys = {json.dumps(chart_buys)};

var baseColor = '#5470c6';
var oosColor = '#fac858';
var p12Color = '#ee6666';
var bestColor = '#e94560';

// Chart 1: Annual Return IS vs OOS
var c1 = echarts.init(document.getElementById('chart_ann'));
c1.setOption({{
    title:{{text:'IS vs OOS Annual Return', left:'center', textStyle:{{fontSize:14}}}},
    tooltip:{{trigger:'axis'}},
    legend:{{data:['IS','OOS'], bottom:0}},
    xAxis:{{type:'category', data:chartLabels, axisLabel:{{fontSize:10, rotate:30}}}},
    yAxis:{{type:'value', name:'%', axisLabel:{{formatter:'{{value}}%'}}}},
    series:[
        {{name:'IS', type:'bar', data:chartAnnIS, itemStyle:{{color:function(p){{return p.dataIndex===6?bestColor:baseColor;}}}}}},
        {{name:'OOS', type:'bar', data:chartAnnOOS, itemStyle:{{color:oosColor}}}}
    ],
    markLine:{{data:[{{yAxis:6, name:'6% target'}}], lineStyle:{{color:'#c62828', type:'dashed'}}}}
}});

// Chart 2: Sharpe
var c2 = echarts.init(document.getElementById('chart_sharpe'));
c2.setOption({{
    title:{{text:'IS Sharpe Ratio', left:'center', textStyle:{{fontSize:14}}}},
    tooltip:{{trigger:'axis'}},
    xAxis:{{type:'category', data:chartLabels, axisLabel:{{fontSize:10, rotate:30}}}},
    yAxis:{{type:'value', name:'Sharpe'}},
    series:[{{type:'bar', data:chartSharpeIS, itemStyle:{{color:function(p){{return p.dataIndex===6?bestColor:baseColor;}}}}}}]
}});

// Chart 3: Trade PnL & P12 PnL
var c3 = echarts.init(document.getElementById('chart_pnl'));
c3.setOption({{
    title:{{text:'IS Trade PnL vs P12 PnL', left:'center', textStyle:{{fontSize:14}}}},
    tooltip:{{trigger:'axis'}},
    legend:{{data:['Trade PnL','P12 PnL'], bottom:0}},
    xAxis:{{type:'category', data:chartLabels, axisLabel:{{fontSize:10, rotate:30}}}},
    yAxis:{{type:'value', name:'CNY', axisLabel:{{formatter:function(v){{return (v/1000)+'K';}}}}}},
    series:[
        {{name:'Trade PnL', type:'bar', data:chartPnlIS, itemStyle:{{color:baseColor}}}},
        {{name:'P12 PnL', type:'bar', data:chartP12Pnl, itemStyle:{{color:p12Color}}}}
    ]
}});

// Chart 4: Buy count
var c4 = echarts.init(document.getElementById('chart_buys'));
c4.setOption({{
    title:{{text:'IS Buy Count', left:'center', textStyle:{{fontSize:14}}}},
    tooltip:{{trigger:'axis'}},
    xAxis:{{type:'category', data:chartLabels, axisLabel:{{fontSize:10, rotate:30}}}},
    yAxis:{{type:'value', name:'trades'}},
    series:[{{type:'bar', data:chartBuys, itemStyle:{{color:function(p){{return p.dataIndex===6?bestColor:baseColor;}}}}}}],
    markLine:{{data:[{{yAxis:6, name:'14A min'}}], lineStyle:{{color:'#c62828', type:'dashed'}}}}
}});

window.addEventListener('resize', function(){{c1.resize();c2.resize();c3.resize();c4.resize();}});
</script>
</body>
</html>"""

out_path = os.path.join(OUT, "P12_移动止盈引擎扩大化_回测验证.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"Generated: {out_path}")
