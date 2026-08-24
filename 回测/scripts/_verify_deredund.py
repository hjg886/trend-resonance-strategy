# -*- coding: utf-8 -*-
"""冗余5 逻辑等价性冒烟测试：修改前(第1/6灯独立if-elif) vs 修改后(tre_gate_kind)"""

def old_light1(obs, tre, s3):
    if obs: return "OK"
    elif tre == "S4": return "NO"
    elif tre == "S3": return "OK" if s3 else "NO"
    else: return "OK"

def old_light6(obs, tre, s3):
    if obs: return "OK"
    elif tre == "S4": return "NO"
    elif tre == "S3": return "OK" if s3 else "NO"
    else: return "OK"

def new_gate(obs, tre, s3):
    if obs: return "obs"
    elif tre == "S4": return "s4"
    elif tre == "S3": return "s3_ok" if s3 else "s3_no"
    else: return "s12"

L1 = {"obs": "OK", "s4": "NO", "s3_ok": "OK", "s3_no": "NO", "s12": "OK"}
L6 = {"obs": "OK", "s4": "NO", "s3_ok": "OK", "s3_no": "NO", "s12": "OK"}

combos = []
for obs in (True, False):
    for tre in ("S1", "S2", "S3", "S4"):
        for s3 in (True, False):
            combos.append((obs, tre, s3))

fails = 0
for obs, tre, s3 in combos:
    o1, o6 = old_light1(obs, tre, s3), old_light6(obs, tre, s3)
    g = new_gate(obs, tre, s3)
    n1, n6 = L1[g], L6[g]
    if o1 != n1 or o6 != n6:
        fails += 1
        print(f"MISMATCH: obs={obs} tre={tre} s3={s3} | old=({o1},{o6}) new=({n1},{n6})")

print(f"测试组合数={len(combos)} 不一致={fails}")
print("等价性验证：" + ("通过" if fails == 0 else "失败"))
