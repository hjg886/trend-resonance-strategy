# -*- coding: utf-8 -*-
"""提频：R10 得分门槛放宽 80/85 → 75/73/78（对齐回测证据 D-5「降门槛期望更高+0.77%、最优75-78中间值」）"""
import io, os, shutil, sys

P = r"E:\fnOS\文档\证券\中线趋势共振策略\回测\scripts\run_backtest.py"
BAK = P + ".bak_20260821_gate"
if not os.path.exists(BAK):
    shutil.copy2(P, BAK)
    print(f"[BAK] {BAK}")

old = """                if R10_GATES_ON:
                    g_s1 = 78.0 if ptype == "etf_ind" else 80.0
                    g_s2 = 78.0 if ptype == "etf_ind" else 80.0
                    g_obs = 85.0"""

new = """                if R10_GATES_ON:
                    # 【提频·门槛放宽 2026-08-21】R10门槛80/85过高→建仓枯竭(16笔/6年, D-5主因)
                    #   回测证据：降门槛期望更高(+0.77%)，报告推测最优75-78中间值；行业ETF得分天然偏低保持-2分
                    g_s1 = 73.0 if ptype == "etf_ind" else 75.0
                    g_s2 = 73.0 if ptype == "etf_ind" else 75.0
                    g_obs = 78.0"""

with io.open(P, "r", encoding="utf-8") as f:
    c = f.read()
n = c.count(old)
if n != 1:
    print(f"[FAIL] count={n}")
    sys.exit(1)
c = c.replace(old, new, 1)
with io.open(P, "w", encoding="utf-8", newline="") as f:
    f.write(c)
print("[OK] R10 门槛已放宽：个股宽基 80→75 / 行业ETF 78→73 / 观察通道 85→78")
print("DONE")
