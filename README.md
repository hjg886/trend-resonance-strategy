# 中线趋势共振策略 v5.0

A股为主 · ETF为辐 · 开放式漏斗版 中线趋势共振策略（趋势状态识别 TRE + 24 因子评分 + 四级裁决金字塔）。

## 回测引擎
- `回测/scripts/engine.py` —— TRE 状态机 + 融合裁决 + 资金管理（含规模相关滑点模型）
- `回测/scripts/run_backtest.py` —— 回测主入口（环境变量驱动，详见脚本内 `BT_*` 开关与 `dump_run_manifest()` 防静默绕过）
- `回测/scripts/metrics.py` / `mhd_scorer.py` / `sweep_runner.py` —— 指标 / MHD 评分 / 敏感性扫描

## 依赖
```bash
pip install -r requirements.txt
```

## 可复现性
代码版本号 `engine_v4.7_R10_P2_20260822`。默认配置（`BT_UNIV_V5=1`）实测基线：
IS 2.70% / OOS 2.82% / OOS 最大回撤 1.42% / 夏普 1.61（资金 100 万、滑点 0）。

详见 `中线趋势共振策略_v5.0.txt` 与 `v5.0复核修复报告_2026-08-24.html`。

> 本仓库仅供研究参考，不构成任何投资建议。
