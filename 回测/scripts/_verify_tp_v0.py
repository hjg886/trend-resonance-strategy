# -*- coding: utf-8 -*-
"""冗余2 改造 V0 等价性验证（当前数据口径）：
背景：P0dCore 存档(08-21 15:54)使用旧 stk 数据，53 只个股数据于 08-21 16:32 补充更新，
      逐笔复现历史存档已不可能。等价性验证目标改为：
      「当前数据下，TP 改造(V0) 相对无改造代码无副作用」。

方法：
  ref = bak_R9only 代码（08-21 固化前, 内容==bak_20260821_p0dcore）
        + 显式 R10GATES=1/H1=1/BREADTH=1（等价固化后）+ 带宽7/4 + 当前数据
  new = 当前 run_backtest.py + TP_VARIANT=0 + 同环境
  对比 ref/new 的 buys/closed/final_equity 逐笔一致 → 改造无副作用。
"""
import json, os, shutil, subprocess, sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCRIPTS = os.path.dirname(__file__)
OUT = os.path.join(ROOT, "output")
PY = r"C:/Users/hanji/.workbuddy/binaries/python/envs/backtest/Scripts/python.exe"
REF_PY = os.path.join(SCRIPTS, "run_backtest_v0ref.py")

BUY_KEYS = ["date", "code", "reason", "score", "target", "tre", "obs", "min", "lights_ok", "r_level"]
CLOSED_KEYS = ["code", "exit", "pnl", "pnl_pct", "hold_days", "exit_reason", "obs_probe", "s3_pos"]


def make_env(extra=None):
    env = dict(os.environ)
    env.update(BT_EP1_BAND_SHORT="7", BT_EP1_BAND_LONG="4")
    env.update(BT_R10GATES="1", BT_H1_S1NOETF="1", BT_BREADTH_VETO="1")
    if extra:
        env.update(extra)
    return {k: str(v) for k, v in env.items()}


def norm_buys(buys):
    return [{k: b.get(k) for k in BUY_KEYS} for b in buys]


def norm_closed(closed):
    out = []
    for c in closed:
        row = {k: c.get(k) for k in CLOSED_KEYS}
        row["pnl"] = round(row.get("pnl", 0), 4)
        row["pnl_pct"] = round(row.get("pnl_pct", 0), 10)
        out.append(row)
    return out


def compare_seg(seg, new, old):
    print(f"\n===== 样本{seg} 对比 =====")
    fails = []
    nv, ov = new.get("final_equity"), old.get("final_equity")
    if abs((nv or 0) - (ov or 0)) > 0.01:
        fails.append(f"[final_equity] new={nv} old={ov}")
    nb, ob = norm_buys(new.get("buys", [])), norm_buys(old.get("buys", []))
    if len(nb) != len(ob):
        fails.append(f"[buys数] new={len(nb)} old={len(ob)}")
    else:
        for i, (n, o) in enumerate(zip(nb, ob)):
            if n != o:
                fails.append(f"[buys#{i}] new={n} old={o}")
                break
    nc, oc = norm_closed(new.get("closed", [])), norm_closed(old.get("closed", []))
    if len(nc) != len(oc):
        fails.append(f"[closed数] new={len(nc)} old={len(oc)}")
    else:
        for i, (n, o) in enumerate(zip(nc, oc)):
            if n != o:
                fails.append(f"[closed#{i}] new={n} old={o}")
                break
    print(f"buys: new={len(nb)} old={len(ob)}" + (" 一致" if nb == ob else " 有差异!"))
    print(f"closed: new={len(nc)} old={len(oc)}" + (" 一致" if nc == oc else " 有差异!"))
    if fails:
        print("❌ 差异明细：")
        for f in fails[:10]:
            print(" ", f)
        return False
    print("✅ 一致")
    return True


if __name__ == "__main__":
    # 0) 准备参照代码（bak_R9only 内容 = bak_20260821_p0dcore）
    if not os.path.exists(REF_PY):
        shutil.copy2(os.path.join(SCRIPTS, "run_backtest.py.bak_R9only"), REF_PY)
        print("[REF] 已创建 run_backtest_v0ref.py（来自 bak_R9only）")

    # 1) 跑参照（无 TP 改造）
    print("=== 运行参照回测（bak 代码 + R10GATES/H1/BREADTH=1 + 带宽7/4）===", flush=True)
    r = subprocess.run([PY, "run_backtest_v0ref.py"], cwd=SCRIPTS, env=make_env(),
                       capture_output=True, text=True, timeout=1800)
    if r.returncode != 0:
        print(f"[FAIL] ref: {r.stderr[-3000:]}")
        sys.exit(1)
    for seg in ("in", "oos"):
        shutil.copy(os.path.join(OUT, f"results_{seg}.json"),
                    os.path.join(OUT, f"results_V0REF_{seg}.json"))

    # 2) 跑当前代码 V0
    print("=== 运行当前代码 V0（TP_VARIANT=0）===", flush=True)
    r = subprocess.run([PY, "run_backtest.py"], cwd=SCRIPTS, env=make_env({"BT_TP_VARIANT": "0"}),
                       capture_output=True, text=True, timeout=1800)
    if r.returncode != 0:
        print(f"[FAIL] new: {r.stderr[-3000:]}")
        sys.exit(1)
    for seg in ("in", "oos"):
        shutil.copy(os.path.join(OUT, f"results_{seg}.json"),
                    os.path.join(OUT, f"results_V0NEW_{seg}.json"))

    # 3) 对比
    all_ok = True
    for seg in ("in", "oos"):
        with open(os.path.join(OUT, f"results_V0NEW_{seg}.json"), encoding="utf-8") as fh:
            new = json.load(fh)
        with open(os.path.join(OUT, f"results_V0REF_{seg}.json"), encoding="utf-8") as fh:
            old = json.load(fh)
        all_ok = compare_seg(seg, new, old) and all_ok

    # 4) 结论 + 以当前数据 V0 为基线存档
    if all_ok:
        print("\n✅ V0 等价性验证通过（当前数据下 TP 改造无副作用）")
        print("   → V0 即当前数据下的 P0dCore 口径基线，作为 V1-V4 对比基准")
        # 用 V0NEW 覆盖 P0dCore 存档（当前数据口径）
        for seg in ("in", "oos"):
            shutil.copy(os.path.join(OUT, f"results_V0NEW_{seg}.json"),
                        os.path.join(OUT, f"results_{seg}_P0dCore.json"))
            print(f"   已更新 results_{seg}_P0dCore.json（当前数据口径）")
    else:
        print("\n❌ V0 等价性验证失败（需排查改造回归）")
    sys.exit(0 if all_ok else 2)
