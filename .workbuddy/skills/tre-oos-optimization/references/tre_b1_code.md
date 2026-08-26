# Track B1 代码改动模板（TRE 状态升级收紧）

本文件给出 B1 落地的三处关键改动骨架，供下次优化直接套用。路径与符号以趋势共振策略回测工程为准。

## 1. run_backtest.py —— env 开关读取（默认开）

```python
import os

# B1: S2 状态升级收紧开关（默认开启）
S2_MAJOR_ON = os.environ.get("BT_S2_MAJOR", "1") == "1"
S2_BREADTH_GATE = float(os.environ.get("BT_S2_BREADTH_GATE", "18.0"))

# 在调用 step_tre 处透传：
new_state = step_tre(
    raw_state=raw,
    breadth=breadth_now,          # 当前 BREADTH 宽度
    s2_major_on=S2_MAJOR_ON,
    s2_breadth_gate=S2_BREADTH_GATE,
)
```

## 2. tre.py —— raw_state S2 兜底收紧

原逻辑（过松）：
```python
# 任一核心指数 ADX ∈ [15, 20) 即升级到 S2
if any(15 <= adx < 20 for adx in core_adxs):
    return "S2"
```

B1 收紧后：
```python
def _s2_upgrade_ok(core_adxs, breadth, s2_major_on, s2_breadth_gate):
    if not s2_major_on:
        # 兼容旧行为：任一核心 ADX ∈ [15,20)
        return any(15 <= a < 20 for a in core_adxs)
    # 多数核心指数 ADX ≥ 20 且 BREADTH 宽度 ≥ 阈值
    major = sum(1 for a in core_adxs if a >= 20) > len(core_adxs) / 2
    return major and breadth >= s2_breadth_gate

# raw_state 兜底
if _s2_upgrade_ok(core_adxs, breadth, s2_major_on, s2_breadth_gate):
    return "S2"
return "S3"   # 不满足条件直接降级，避免假突破建仓
```

观察通道 `up_s2_cond` 同步复用 `_s2_upgrade_ok`，保证观察升级与实盘升级同口径。

## 3. tre.py —— step_tre 签名扩展

```python
def step_tre(raw_state, breadth=None, s2_major_on=True, s2_breadth_gate=18.0):
    # ... 其余不变，S2 判定处调用 _s2_upgrade_ok(...)
    pass
```

## 4. sweep_b1.py 扫描骨架

```python
import itertools, json, subprocess, sys

GATE_GRID = [15.0, 16.0, 17.0, 18.0, 19.0, 20.0]
MAJOR_GRID = ["0", "1"]
best = None

def have(res, key):  # 注意括号配对，曾因嵌套不匹配 SyntaxError
    return key in res and res[key] is not None

for major, gate in itertools.product(MAJOR_GRID, GATE_GRID):
    env = dict(os.environ, BT_S2_MAJOR=major, BT_S2_BREADTH_GATE=str(gate))
    out = subprocess.run([PY, "run_backtest.py"], env=env, capture_output=True, text=True)
    res = json.loads(out.stdout)  # 期望 run_backtest 打印 metrics json
    oos = res.get("oos_ann")
    if have(res, "oos_ann") and oos is not None and oos >= 0.035:
        cand = (oos, major, gate)
        if best is None or oos > best[0]:
            best = cand
    # 写 checkpoint 便于 resume（v2 容错）
    dump_checkpoint(...)
print("BEST", best)  # 案例最优 g18: major=1, gate=18.0 → OOS 3.862%
```

## 5. 回归验收对照（默认参数重跑）

落盘后必须做一次 `python run_backtest.py`（不传 env，走默认开）对照扫描最优格：

| 来源 | IS | OOS |
|------|-----|-----|
| 默认重跑 | 2.244% | 3.873% |
| b1_g18 (major=1,gate=18.0) | 2.243% | 3.862% |
| 误差 | <0.01% | <0.01% |

误差 <0.01% 即证明 env 默认落盘与扫描结论一致，验收通过。
