# -*- coding: utf-8 -*-
"""纠正1+2落地：①510300清仓依据明确为E-P9非P1；②主引擎脚本标注TRE双轨口径。"""
import io, os, shutil, sys

HTML = r"E:\fnOS\文档\证券\收盘总结-20260821.html"
PY = r"E:\fnOS\文档\证券\中线趋势共振策略\pre_market_calc.py"

ok = True

# ---- 纠正1：收盘总结 HTML 补明确依据 ----
old1 = "剩余20,400股周一竞价清仓为最后期限；"
new1 = "剩余20,400股周一竞价清仓（依据=E-P9时间止损·13因子&lt;65，非P1技术止损；E-P1线4.6295未触发）；"
with io.open(HTML, "r", encoding="utf-8") as f:
    c = f.read()
n = c.count(old1)
if n != 1:
    print(f"[FAIL] HTML count={n}")
    ok = False
else:
    c = c.replace(old1, new1, 1)
    with io.open(HTML, "w", encoding="utf-8", newline="") as f:
        f.write(c)
    print("[OK] 纠正1：收盘总结HTML清仓依据已明确 E-P9 非 P1")

# ---- 纠正2：pre_market_calc.py 标注主引擎口径 ----
old2 = '# ============== 任务1: TRE状态判定 ==============\nprint("【任务1】TRE趋势状态判定")'
new2 = ('# ============== 任务1: TRE状态判定（主引擎口径·三指数简化矩阵） ==============\n'
        '# ⚠️ 口径说明：本脚本 TRE 用「三指数各自判定 + any vol20>25→S4」的简化矩阵，\n'
        '#    与 B3 回测口径（run_attack_b.compute_tre_states，只看沪深300 vol20）不同——\n'
        '#    主引擎持仓用本脚本口径（当前 S4），B3 信号单用回测口径（当前 S2），勿混用。\n'
        'print("【任务1】TRE趋势状态判定（主引擎口径·三指数简化矩阵）")')
with io.open(PY, "r", encoding="utf-8") as f:
    c = f.read()
n = c.count(old2)
if n != 1:
    print(f"[FAIL] PY count={n}")
    ok = False
else:
    c = c.replace(old2, new2, 1)
    with io.open(PY, "w", encoding="utf-8", newline="") as f:
        f.write(c)
    print("[OK] 纠正2：pre_market_calc.py 已标注主引擎口径（勿与B3回测口径混淆）")

print("\nALL DONE" if ok else "\nSOME FAILED")
sys.exit(0 if ok else 1)
