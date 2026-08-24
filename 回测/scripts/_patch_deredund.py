# -*- coding: utf-8 -*-
"""去冗余阶段2落地：对 scoring.py 与 run_backtest.py 做等价字符串替换。"""
import io, sys

SCORING = r"E:\fnOS\文档\证券\中线趋势共振策略\回测\scripts\scoring.py"
RUNBT = r"E:\fnOS\文档\证券\中线趋势共振策略\回测\scripts\run_backtest.py"

def patch(path, pairs):
    with io.open(path, "r", encoding="utf-8") as f:
        c = f.read()
    ok = True
    for old, new in pairs:
        n = c.count(old)
        if n != 1:
            print(f"[FAIL] count={n} in {path}: {old[:50]!r}")
            ok = False
        else:
            c = c.replace(old, new, 1)
            print(f"[OK]   {path}: {old[:50]!r}")
    if ok:
        with io.open(path, "w", encoding="utf-8", newline="") as f:
            f.write(c)
        print(f"[WROTE] {path}")
    return ok

# ---- scoring.py 冗余5：第1灯 / 第6灯 TRE 判定合并 ----
old1 = '''    lights = []
    # 第1灯 大盘中长期环境
    if obs_active:
        lights.append("第1灯✅(观察通道视为绿灯)")
    elif tre_state == "S4":
        lights.append("第1灯❌(S4禁止)")
    elif tre_state == "S3":
        lights.append("第1灯✅(S3有限建仓视为绿灯)" if s3_limit_ok else "第1灯❌(S3非有限建仓)")
    else:
        lights.append("第1灯✅")'''

new1 = '''    lights = []
    # 【去冗余·阶段2·冗余5】TRE状态闸门单一判定（SSOT）
    # 第1灯"大盘环境"与第6灯"TRE适配"原为逐字重复的 if-elif，合并为一次判定、两灯引用
    if obs_active:
        tre_gate_kind = "obs"
    elif tre_state == "S4":
        tre_gate_kind = "s4"
    elif tre_state == "S3":
        tre_gate_kind = "s3_ok" if s3_limit_ok else "s3_no"
    else:
        tre_gate_kind = "s12"
    # 第1灯 大盘中长期环境
    lights.append({
        "obs": "第1灯✅(观察通道视为绿灯)",
        "s4": "第1灯❌(S4禁止)",
        "s3_ok": "第1灯✅(S3有限建仓视为绿灯)",
        "s3_no": "第1灯❌(S3非有限建仓)",
        "s12": "第1灯✅",
    }[tre_gate_kind])'''

old2 = '''    # 第6灯 TRE适配
    if obs_active:
        lights.append("第6灯✅(观察通道按S3观察模式)")
    elif tre_state == "S4":
        lights.append("第6灯❌(S4禁止)")
    elif tre_state == "S3":
        lights.append("第6灯✅(S3有限建仓开放)" if s3_limit_ok else "第6灯❌")
    else:
        lights.append("第6灯✅")'''

new2 = '''    # 第6灯 TRE状态适配（引用同一 tre_gate_kind，见上方冗余5合并）
    lights.append({
        "obs": "第6灯✅(观察通道按S3观察模式)",
        "s4": "第6灯❌(S4禁止)",
        "s3_ok": "第6灯✅(S3有限建仓开放)",
        "s3_no": "第6灯❌",
        "s12": "第6灯✅",
    }[tre_gate_kind])'''

# ---- scoring.py 冗余4：第2灯引用层级1 ----
old3 = '''                 open_pct: float, r_level: str, product_ok: bool,
                 wide_ok: bool, ma60_break90: int,'''

new3 = '''                 open_pct: float, r_level: str, layer1_ok: bool,
                 wide_ok: bool, ma60_break90: int,'''

old4 = '''    lights.append(f"第2灯{'✅' if product_ok else '❌'}(产品健康度)")'''

new4 = '''    # 【去冗余·阶段2·冗余4】第2灯引用层级1产品硬过滤结果（原与 layer1_etf 的 product_ok 重复）
    lights.append(f"第2灯{'✅' if layer1_ok else '❌'}(层级1产品硬过滤)")'''

ok1 = patch(SCORING, [(old1, new1), (old2, new2), (old3, new3), (old4, new4)])

# ---- run_backtest.py 冗余4：第2灯传 ok1（层级1结果）而非硬编码 True ----
old5 = '''                    ok_l, lights = seven_lights(row, tre.state, tre.obs_active, n_hold, n_same,
                                                beta, cap, open_pct, r_level, True, True,
                                                row.get("ma60_break90", 0),
                                                ind_etf=(ptype == "etf_ind") and R1_ON)'''

new5 = '''                    # 【去冗余·阶段2·冗余4】第2灯引用层级1结果(ok1)，不再硬编码 True
                    ok_l, lights = seven_lights(row, tre.state, tre.obs_active, n_hold, n_same,
                                                beta, cap, open_pct, r_level, ok1, True,
                                                row.get("ma60_break90", 0),
                                                ind_etf=(ptype == "etf_ind") and R1_ON)'''

ok2 = patch(RUNBT, [(old5, new5)])

print("\nALL DONE" if (ok1 and ok2) else "\nSOME FAILED")
sys.exit(0 if (ok1 and ok2) else 1)
