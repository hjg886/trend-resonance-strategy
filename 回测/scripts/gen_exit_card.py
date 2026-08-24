# -*- coding: utf-8 -*-
"""生成四只持仓离场预案卡 HTML（基于 exit_plan.json + 触发检查结果）"""
import json, io, os

OUT = r"E:/fnOS/文档/证券/中线趋势共振策略/回测/output/离场预案卡_2026-08-18.html"
res = json.load(io.open(r"E:/fnOS/文档/证券/中线趋势共振策略/回测/output/exit_plan.json", encoding="utf-8"))

# 汇总今日触发状态（来自触发检查）
triggers = [
    dict(level="🔴 紧急", who="大盘 · 沪深300", cond="连续16个交易日收盘 < MA60（阈值=3日）",
         rule="P9（个股）/ E-P10（ETF）", action="总仓位压缩至 20% 以内（与E-P10同日取更严）", note="2026-08-18 收盘 4710.45 < MA60 4780.10"),
    dict(level="🔴 紧急", who="510300 沪深300ETF", cond="MA60走平(5日斜率-0.196%) 且 价格连续8日<MA60（阈值=2日）",
         rule="E-P3", action="无条件清仓（次日开盘执行）", note="现价 4.771 < MA60 4.823"),
    dict(level="🟠 预警", who="600276 恒瑞医药", cond="现价 52.42 距 P1 止损线 52.17 仅 +0.48%",
         rule="P1", action="收盘价跌破 52.17 → 次日开盘清仓", note="带宽3%（持有35日>11日）；跳空保护：开盘<52.17直接竞价清仓"),
    dict(level="🟡 观察", who="159650 国开债ETF", cond="现金管理定位，F-31 豁免闸门；时间止损剩余7交易日",
         rule="E-P9", action="13因子<65 时次日开盘清仓；现金管理不受闸门约束", note="现价 107.938 > MA60 107.790，安全"),
    dict(level="⚪ 独立", who="900912 外高B", cond="B股独立持仓，数据源无最新K线",
         rule="策略不干预", action="单独记录盈亏，不计入组合统计", note="剩余100股；08-07已卖4400股@$0.641"),
]

# 持仓明细
pos = []
for sym, p in res.items():
    if sym in ("bench",):
        continue
    if sym == "sh900912":
        pos.append((sym, "外高B 900912", "$1.276", "—", "—", "0.619", "策略不干预", "独立持仓"))
        continue
    nm = p["name"]
    cost = p.get("cost_est")
    stop = p.get("stop_line")
    p12v = max(stop, p.get("p12")) if (stop and p.get("p12")) else (p.get("p12") or stop)
    p12flag = "启用" if p.get("p12") else "未启用"
    pos.append((sym, nm, f"{cost:.3f}", f"{p['last']:.3f}", f"{p['pnl_pct']:+.2f}%",
                f"{p['ma60']:.3f}", f"{stop:.3f}", f"{p['hold_days']}日"))
    # 追加P12信息列
    pos[-1] = (sym, nm, f"{cost:.3f}", f"{p['last']:.3f}", f"{p['pnl_pct']:+.2f}%",
               f"{p['ma60']:.3f}", f"{stop:.3f}", f"P12{p12flag}·线{p12v:.3f}" if p12v else "P12未启用")

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>离场预案卡 · 2026-08-18</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:"Microsoft YaHei","PingFang SC",sans-serif; background:#f5f6f8; color:#222; padding:20px; }}
  .wrap {{ max-width:900px; margin:0 auto; }}
  h1 {{ font-size:22px; color:#1a2a4a; margin-bottom:4px; }}
  .sub {{ font-size:13px; color:#666; margin-bottom:16px; }}
  .card {{ background:#fff; border-radius:10px; padding:16px 20px; margin-bottom:14px; box-shadow:0 1px 4px rgba(0,0,0,.06); }}
  .card h2 {{ font-size:15px; color:#1a2a4a; margin-bottom:10px; border-left:4px solid #2b6cb0; padding-left:8px; }}
  .env {{ display:flex; flex-wrap:wrap; gap:8px; }}
  .env .item {{ background:#eef3fa; border-radius:6px; padding:6px 12px; font-size:13px; }}
  .env .item b {{ color:#1a2a4a; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th,td {{ border:1px solid #e2e6ec; padding:7px 9px; text-align:left; }}
  th {{ background:#f0f3f8; color:#1a2a4a; font-weight:600; }}
  tr:nth-child(even) td {{ background:#fafbfd; }}
  .lvl-red {{ color:#c0392b; font-weight:700; }}
  .lvl-orange {{ color:#e67e22; font-weight:700; }}
  .lvl-yellow {{ color:#b7950b; font-weight:700; }}
  .lvl-gray {{ color:#666; font-weight:700; }}
  .tag {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:12px; font-weight:600; }}
  .tag-r {{ background:#fdecea; color:#c0392b; }}
  .tag-o {{ background:#fef3e7; color:#e67e22; }}
  .tag-y {{ background:#fef9e7; color:#b7950b; }}
  .tag-g {{ background:#eafaf1; color:#1e8449; }}
  .tag-b {{ background:#e8f0fe; color:#2b6cb0; }}
  .todo {{ background:#fffbea; border:1px solid #f5d78e; border-radius:8px; padding:12px 16px; font-size:14px; line-height:1.9; }}
  .todo b {{ color:#c0392b; }}
  .foot {{ font-size:12px; color:#999; margin-top:18px; text-align:center; line-height:1.7; }}
  .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}
  @media (max-width:640px) {{ .grid2 {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<div class="wrap">
  <h1>🛡️ 存量持仓 · 离场预案卡</h1>
  <div class="sub">生成时间：2026-08-18（周二）盘后 · 策略版本：v4.7-R10 回测驱动重构版 · 数据源：westockdata（K线有延迟，以交易所为准）</div>

  <div class="card">
    <h2>一、今日环境快照</h2>
    <div class="env">
      <div class="item">沪深300收盘 <b>4710.45</b>（-0.65%）</div>
      <div class="item">MA60 <b>4780.10</b></div>
      <div class="item">TRE 名义状态 <b>S1</b>（ADX39/穿越0/vol20 17.9%）</div>
      <div class="item">vol20 <b>17.87%</b> → 正常区</div>
      <div class="item">⚠️ 但大盘已连续 <b>16日</b> 收盘 &lt; MA60</div>
    </div>
  </div>

  <div class="card">
    <h2>二、今日触发状态（按严重程度排序）</h2>
    <table>
      <tr><th>级别</th><th>对象</th><th>触发条件</th><th>适用条款</th><th>应执行动作</th><th>备注</th></tr>
"""
for t in triggers:
    cls = {"🔴 紧急":"lvl-red","🟠 预警":"lvl-orange","🟡 观察":"lvl-yellow","⚪ 独立":"lvl-gray"}[t["level"]]
    html += f"""      <tr>
        <td><span class="{cls}">{t['level']}</span></td>
        <td>{t['who']}</td>
        <td>{t['cond']}</td>
        <td>{t['rule']}</td>
        <td>{t['action']}</td>
        <td>{t['note']}</td>
      </tr>
"""

html += """    </table>
  </div>

  <div class="card">
    <h2>三、四只持仓离场线速查</h2>
    <table>
      <tr><th>标的</th><th>估算成本</th><th>现价</th><th>浮盈亏</th><th>MA60</th><th>P1/E-P1止损线</th><th>持有/时间止损</th></tr>
"""
for sym, nm, cost, last, pnl, ma60, stop, hold in pos:
    html += f"""      <tr><td><b>{nm}</b></td><td>{cost}</td><td>{last}</td><td>{pnl}</td><td>{ma60}</td><td><b>{stop}</b></td><td>{hold}</td></tr>
"""

# 时间止损明细
time_notes = {
    "sh600276": "已用35日/剩余25日（S1口径60日）；⚠️若TRE转S2-S4则30日已超期 → 立即触发时间止损核查",
    "sz159650": "已用53日/剩余7日（S1口径60日）；现金管理定位，13因子大概率通过；若转S2-S4则30日已超期，需13因子核查",
    "sh510300": "已用30日/剩余30日（S1口径60日）；但E-P3已触发清仓，时间止损不适用",
}
html += """    </table>
    <p style="font-size:12px;color:#888;margin-top:6px;">※ 成本为买入日收盘价估算（恒瑞07-01=53.78 / 国开债06-04=107.70 / 沪深300ETF 07-08与07-09加权=4.807），请以实际成交价核对，止损线随成本线性平移。</p>
  </div>

  <div class="grid2">
    <div class="card">
      <h2>四、恒瑞医药 600276 · 个股离场线</h2>
      <table>
        <tr><td>P1 止损（带宽3%）</td><td><b>52.17</b>（距现价 +0.48%）</td></tr>
        <tr><td>动态回撤 -5% 预警</td><td>51.09</td></tr>
        <tr><td>动态回撤 -8% 减半</td><td>49.48</td></tr>
        <tr><td>动态回撤 -12% 清仓</td><td>47.33</td></tr>
        <tr><td>P12 移动止损</td><td>未启用（峰值浮盈9.1%<15%）</td></tr>
        <tr><td>时间止损 11.5</td><td>S1=60日 已用35 剩25日；S2-S4=30日已超期</td></tr>
        <tr><td>MA60/MA120 破位 P6</td><td>现价 52.42 > MA60 51.93，未破位</td></tr>
      </table>
    </div>
    <div class="card">
      <h2>五、510300 沪深300ETF · ETF离场线</h2>
      <table>
        <tr><td>E-P3 MA60走平+破位</td><td><span class="tag tag-r">已触发 → 清仓</span></td></tr>
        <tr><td>E-P1 止损（带宽3%）</td><td>4.663（距现价 +2.3%）</td></tr>
        <tr><td>E-P0 单ETF亏损 -8%</td><td>4.423（减半）</td></tr>
        <tr><td>E-P0.5 亏损 -12% 清仓</td><td>4.231</td></tr>
        <tr><td>E-P12 移动止损</td><td>未启用（峰值浮盈6.1%<15%）</td></tr>
        <tr><td>时间止损 E-P9</td><td>已用30日/剩30日（S1）；E-P3优先</td></tr>
        <tr><td>E-P10 大盘减仓</td><td><span class="tag tag-r">已触发（大盘连续16日<MA60）</span></td></tr>
      </table>
    </div>
  </div>

  <div class="card">
    <h2>六、明日（08-19）执行清单</h2>
    <div class="todo">
      1. <b>开盘：清仓 510300</b>（E-P3 触发，无条件清仓，4.07万股）—— 集合竞价或开盘市价执行<br>
      2. <b>全天监控：恒瑞 600276 收盘价</b> —— 若收盘 &lt; <b>52.17</b>，次日开盘清仓；若开盘跳空直接 &lt; 52.17，竞价即清<br>
      3. <b>恒瑞时间止损警报</b>：TRE 若由 S1 转 S2-S4，30日时间止损已超期 → 立即核查是否清仓<br>
      4. <b>159650 继续持有</b>（现金管理，不受闸门约束）；若时间止损满60日且13因子&lt;65 → 次日清仓<br>
      5. <b>外高B 不动作</b>（独立持仓，剩余100股）<br>
      6. 收盘后向我报告："检查所有持仓" → 我逐项刷新触发状态
    </div>
  </div>

  <div class="card">
    <h2>七、纪律提醒</h2>
    <table>
      <tr><td>禁止动作</td><td>一切补仓 / 加仓 / 新开仓（重构6项未达标，买入通道锁死）</td></tr>
      <tr><td>允许动作</td><td>触发即卖、持有监控、现金管理（159650）</td></tr>
      <tr><td>优先级</td><td>F-11：层级1/E-P0.0 &gt; Ⅲ级熔断30% &gt; 动态回撤加速 &gt; 动态回撤 &gt; Ⅱ级熔断20% &gt; MA60破位（E-P3/E-P10）&gt; 风险贡献度</td></tr>
      <tr><td>批量减仓</td><td>当日总减仓≤20%（层级1/E-P0.0除外）；批量≥3只按F-11排序、间隔≥5分钟</td></tr>
    </table>
  </div>

  <div class="foot">
    免责声明：本预案卡仅供研究参考，不构成个人投资建议。数据可能有延迟，以交易所官方为准。<br>
    市场有风险，投资需谨慎。任何投资决策应结合个人风险承受能力独立判断，必要时咨询持牌专业机构。
  </div>
</div>
</body>
</html>
"""

with io.open(OUT, "w", encoding="utf-8") as fh:
    fh.write(html)
print("written:", OUT, len(html), "chars")
