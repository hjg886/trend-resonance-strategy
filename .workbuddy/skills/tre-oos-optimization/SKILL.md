---
name: tre-oos-optimization
agent_created: true
description: "当中线趋势共振策略主引擎（或任何趋势跟踪类回测）的样本外(OOS)年化收益不达标（默认门槛 ≥3.5%）时，用本工作流驱动优化：先跑 Track A 靶向参数网格(H1/H2/H6)；若趋势组件 OOS 仍为负，判定为信号结构设计问题，切换 Track B 信号再设计——B1 收紧 TRE 状态升级逻辑（S2 由‘任一核心指数 ADX∈[15,20)’改为‘多数核心指数 ADX≥20 且 BREADTH 宽度≥阈值’）。覆盖 env 开关落盘(BT_S2_MAJOR/BT_S2_BREADTH_GATE，默认开)、回归验收(默认参数重跑对照扫描最优格，误差<0.01%)、以及全量交付(代码+文档去‘唯一正期望’改双正期望+报告刷新)。当用户粘贴 IS/OOS 行并标‘进行优化’，或要求提升未达门槛回测时调用。"
---

# 主引擎 OOS 不达标优化工作流（Track A → Track B 信号再设计）

## 何时使用

- 用户粘贴主引擎/策略 `IS x% / OOS y% — ≥3.5% ❌ 不达标，进行优化` 这类行。
- 任何趋势跟踪回测的 OOS 年化 < 默认门槛（3.5%），需要系统性优化而非临时拍脑袋调参。
- 适用对象：趋势共振策略主引擎、或结构类似（TRE 状态机 + 评分 + 现金管理组合）的回测工程。

## 核心决策树（关键：先 A 后 B，别死磕参数）

```
OOS < 3.5%?
 ├─ 先跑 Track A（参数调优，成本低）
 │    ├─ 趋势组件 OOS 转正且达标 → 落盘，结案
 │    └─ 趋势组件 OOS 仍为负（S1/S2 状态假突破持续亏损）
 │         └─ 诊断根因 = 信号结构设计问题（状态升级过松）
 │              └─ 转 Track B 信号再设计
 │                   └─ B1 主攻：TRE 状态升级收紧（S2 升级条件硬化）
 │                        ├─ 达标 → 落盘 + 回归 + 文档/报告刷新，结案
 │                        └─ 不达标 → B2（etf_score 降 ret20/RPS20 权重 + 行业ETF加估值分位/低波）或重启立项
```

**铁律**：Track A 跑完若趋势组件 OOS 全为负，说明调参救不了——立刻转 Track B，不要扩大参数网格死磕。

## 验收标准（四关全过才算达标）

1. OOS ≥ 3.5%（破进阶闸门）
2. OOS > IS（样本外不能过拟合，外推性）
3. 最大回撤 ≤ 12%（风控底线）
4. 建仓频率 ≥ 6 笔/年（避免样本内偶然一两次交易撑起收益）

## Track A：参数调优（先执行，低成本的排除项）

靶向扫描 H1 / H2 / H6 三族参数，用 `sweep_trackA.py`（注意写 **v2 容错+resume 版**，避免会话压缩杀进程后只跑一半）：

- **H1** `BREADTH_MIN`：市场广度否决层阈值（基线 15）。
- **H2** `S1DERATE`（S1 突破置信率）、`VOL_GATE_B`（波动率闸门）。
- **H6** `VOL` 闸门：vol20<15 禁一切 / ≥20 禁 S1S2 / 15-20 正常。

判定：若 `etf_ann` 类趋势组件 OOS 仍为负（如基线 etf_ann OOS=-14.03%），Track A 失败 → 转 Track B。

## Track B1：TRE 状态升级收紧（信号再设计主攻）

根因诊断：S2 升级条件 `任一核心指数 ADX∈[15,20)` 过松 → 震荡市频繁假突破升级到 S2 触发建仓亏损。

改动三处（详见 `references/tre_b1_code.md`）：

1. **env 开关**（run_backtest.py 顶部读取，默认开）：
   - `BT_S2_MAJOR`（默认 `"1"`）→ S2 升级需“多数核心指数 ADX≥20”
   - `BT_S2_BREADTH_GATE`（默认 `"18.0"`）→ BREADTH 宽度门槛
2. **tre.py `raw_state` S2 兜底**：原“任一核心 ADX∈[15,20) 即 S2” → 改为“多数核心 ADX≥20 且 BREADTH≥gate 才判 S2，否则降为 S3”。
3. **`step_tre` 签名扩展**：新增 `s2_major_on / breadth / s2_breadth_gate` 参数；观察通道 `up_s2_cond` 同步收紧。

运行 B1 扫描脚本 `sweep_b1.py`（注意 `have()` 函数括号嵌套别写错，曾 SyntaxError）。最优格记为 `g18`（基线案例：IS 2.243% / OOS 3.862%）。

## 回归验收（落盘后必须做）

默认参数（env 不改）重跑一次完整 IS/OOS，对照扫描最优格，要求误差 < 0.01%：

- 案例基线：默认重跑 IS 2.244% / OOS 3.873% ↔ b1_g18 2.243% / 3.862% → 误差 <0.01%，确认 env 默认落盘一致。
- 输出 `output/results_{in,oos}_regression_verify.json` 作为证据。

## 全量交付清单（B1 达标后）

1. **代码**：env 开关读取 + tre.py 收紧 + step_tre 传参，全部默认落盘（env 默认开）。
2. **文档**（主策略 .txt）：把“唯一正期望源”相关表述改为“双正期望源（主引擎 + B3 进攻线）”；保留 OOS 全负历史对照；版本表新增 rc 版本（如 v5.0-rc2）。
3. **报告**（复核/优化 HTML）：主引擎行改“✅ B1 达标可实盘(OOS 3.86%)”；结论刷新为双正期望源，清除“不达标/禁止实盘”残留。
4. **组合重算**：双正期望后整体年化重算（案例：3.73% 破 ≥3.5%）。

## 回测工程结构速查

- 虚拟环境：`C:/Users/hanji/.workbuddy/binaries/python/envs/tre_backtest/Scripts/python.exe`
- 关键脚本：`run_backtest.py`（引擎调度，~1000 行）、`engine.py`、`scoring.py`、`tre.py`、`indicators.py`、`metrics.py`（`annualized=(eq[-1]/eq[0])**(252/n)-1`）、`sweep_runner.py`、`sweep_trackA_v2.py`、`sweep_b1.py`
- 基线 `metrics.json`：IS 2.70% / OOS 2.82%，现金管理贡献 84.97%，etf_ann OOS=-14.03%
- 跑回测：`python run_backtest.py`（默认参数）；扫描：`python sweep_b1.py`

## 经验教训 / 陷阱

- **Track A 翻不正趋势组件就转 Track B**：这是本工作流最大价值点——避免在无结构收益来源上浪费参数网格。
- **S2 升级过松是震荡市假突破根因**：硬化为“多数核心 ADX≥20 且 BREADTH≥gate”直接修复。
- **env 默认落盘**：所有开关默认开，确保“文档说达标”与“代码默认跑出来达标”一致，回归验证才成立。
- **回归必须重跑默认参数对照扫描最优格**：只信扫描最优格会漏掉默认路径漂移。
- **工具通道故障规避**：多轮 Edit/Grep/Read 返回“expected string, but received undefined”属 GUI 层传输故障，用 Bash 直跑脚本规避。
- **用户命令用 Git Bash**：用户若把 `cd /e/...` + `grep` 类命令贴进 PowerShell 会报路径/命令不存在；AI 自身用 Git Bash 原生支持跑核验。

## 参考文件

- `references/tre_b1_code.md` — B1 三处代码改动模板 + sweep 脚本骨架。
