# -*- coding: utf-8 -*-
"""第四轮修复验证批次: B7r(回归对照) + D4r/D5r/D6r(P0-F/G/E 叠加)"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import run_variant as RV

CONFIGS = [
    ("B7r", 70, 78, "V1", "0", "0", "0", "0", "0", "0", "0"),   # 回归对照（开关全0, 应复现历史）
    ("D4r", 70, 78, "V1", "1", "1", "1", "1", "1", "0", "0"),   # D3 + P0-F 凯利下限
    ("D5r", 70, 78, "V1", "1", "1", "1", "1", "1", "1", "0"),   # D4 + P0-G E-P1洗仓封堵
    ("D6r", 70, 78, "V1", "1", "1", "1", "1", "1", "1", "1"),   # D5 + P0-E 观察升级豁免
]

if __name__ == "__main__":
    for cfg in CONFIGS:
        label, sg, og, var, fixl5, r1, r2, r3, kellymin, ep1block, obsguard = cfg
        print(f"=== {label}: K={kellymin} E={ep1block} O={obsguard} ===", flush=True)
        RV.run_one(label, sg, og, var, fixl5, r1, r2, r3, kellymin, ep1block, obsguard)
    print("ROUND4 DONE", flush=True)
