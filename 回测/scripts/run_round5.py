# -*- coding: utf-8 -*-
"""
第五轮归因驱动修复验证批次:
  D6r 回归对照（确认新开关默认关闭=零副作用）
  E1r: D6r + vol20≥15 硬过滤（归因最优过滤器 +0.12%/笔）
  E2r: D6r + S1 建仓降档 50%（S1 期望-2.94%，降权比排除更保守）
  E3r: E1r + E2r 叠加（双过滤器验证）
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import run_variant as RV

# (label, sg, og, var, fixl5, r1, r2, r3, kellymin, ep1block, obsguard, volfilter, s1derate)
CONFIGS = [
    ("D6r", 70, 78, "V1", "1", "1", "1", "1", "1", "1", "1", "0", "0"),   # 回归对照（新开关全关）
    ("E1r", 70, 78, "V1", "1", "1", "1", "1", "1", "1", "1", "1", "0"),   # +vol20≥15 硬过滤
    ("E2r", 70, 78, "V1", "1", "1", "1", "1", "1", "1", "1", "0", "1"),   # +S1 降档50%
    ("E3r", 70, 78, "V1", "1", "1", "1", "1", "1", "1", "1", "1", "1"),   # vol过滤 + S1降档
]

if __name__ == "__main__":
    for cfg in CONFIGS:
        label = cfg[0]
        volf = cfg[11]; s1d = cfg[12]
        print(f"=== {label}: VOL={volf} S1D={s1d} ===", flush=True)
        RV.run_one(*cfg)
    print("ROUND5 DONE", flush=True)
