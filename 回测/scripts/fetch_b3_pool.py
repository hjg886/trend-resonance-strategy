# -*- coding: utf-8 -*-
"""
B3 候选池个股 K线补数据脚本
============================
用途：拉取 cand_meta.json 候选池 72 只中「data 目录缺 K 线」的个股（当前缺 53 只）。
通道：westockdata skill（腾讯自选股接口，每请求硬上限250行），复权 qfq 前复权。
输出：data/stk_<code>.csv，格式与东财一致（date,open,close,high,low,volume,amount,amp,pct_chg,chg,turnover）

⚠️ 运行环境要求：需 Node.js + 网络 + 子进程捕获输出权限。
   当前 DSH 沙箱禁止程序通过管道捕获子进程 stdout（EPERM），本脚本无法在沙箱内运行，
   请在正常终端执行：  python fetch_b3_pool.py
"""
import os, re, subprocess, time, json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
META = os.path.join(BASE_DIR, "..", "tmp", "sectors", "cand_meta.json")

# 从 cand_meta.json 读候选池 72 只（带 sh/sz 前缀的代码 + 名称）
with open(META, "r", encoding="utf-8") as f:
    _meta = json.load(f)
NAMES = _meta["names"]
ALL_CODES = _meta["M"]  # ['sh688072', ...]

# 过滤：只保留 data 目录缺 stk_<code>.csv 的
def code6(c):
    return c.replace("sh", "").replace("sz", "")
CODES = [c for c in ALL_CODES if not os.path.exists(os.path.join(DATA_DIR, f"stk_{code6(c)}.csv"))]

RANGES = []
for y in range(2018, 2027):
    RANGES.append((f"{y}-01-01", f"{y}-06-30"))
    RANGES.append((f"{y}-07-01", f"{y}-12-31"))

NODE_DIR = r"C:\Users\hanji\.workbuddy\binaries\node\versions\22.22.2"
NPX = os.path.join(NODE_DIR, "npx.cmd")
ROW_RE = re.compile(
    r"^\|\s*(\w{2}\d{6})\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|"
)
# 单股格式兜底（无 symbol 列）：部分标的 qfq 批量接口返回空，但单股无 fq 接口有数据（如 sz000738 航发控制）
ROW_RE_SINGLE = re.compile(
    r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|"
)

def fetch_single_fallback(sym, start, end):
    """单股无fq兜底：qfq 批量返回空的标的（返回 {date: [o,last,h,l,v,amt,turn]}）"""
    cmd = [NPX, "-y", "westock-data-skillhub@1.0.5", "kline", sym,
           "--start", start, "--end", end, "--limit", "250"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    out = {}
    for line in r.stdout.splitlines():
        m = ROW_RE_SINGLE.match(line.strip())
        if m:
            out[m.group(1)] = [float(m.group(2)), float(m.group(3)), float(m.group(4)),
                               float(m.group(5)), float(m.group(6)), float(m.group(7)), float(m.group(8))]
    return out

def fetch_batch(start, end):
    cmd = [NPX, "-y", "westock-data-skillhub@1.0.5", "kline", ",".join(CODES),
           "--start", start, "--end", end, "--fq", "qfq", "--limit", "250"]
    print(f"  [run] {start}~{end} ({len(CODES)}只)", flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        print(f"    !! exit={r.returncode} stderr={r.stderr[:200]}", flush=True)
        return {}
    out = {}
    for line in r.stdout.splitlines():
        m = ROW_RE.match(line.strip())
        if m:
            sym, d = m.group(1), m.group(2)
            out.setdefault(sym, []).append([d, float(m.group(3)), float(m.group(4)),
                                            float(m.group(5)), float(m.group(6)), float(m.group(7)),
                                            float(m.group(8)), float(m.group(9))])
    for c in out:
        out[c].reverse()
    return out

def main():
    if not CODES:
        print("无缺数据个股，全部已就绪。")
        return
    print(f"待补 {len(CODES)} 只：{', '.join(NAMES.get(c, code6(c)) for c in CODES)}")
    all_data = {c: [] for c in CODES}
    for (s, e) in RANGES:
        batch = fetch_batch(s, e)
        for c in CODES:
            seen = {r[0] for r in all_data[c]}
            for row in batch.get(c, []):
                if row[0] not in seen:
                    seen.add(row[0])
                    all_data[c].append(row)
        time.sleep(0.8)
    summary = {}
    for c in CODES:
        rows = sorted(all_data[c], key=lambda r: r[0])
        label = NAMES.get(c, code6(c))
        if not rows:
            print(f"[fail] {label} ({c}) 空数据")
            summary[code6(c)] = {"label": label, "rows": 0, "note": "FAILED"}
            continue
        path = os.path.join(DATA_DIR, f"stk_{code6(c)}.csv")
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            fh.write("date,open,close,high,low,volume,amount,amp,pct_chg,chg,turnover\n")
            prev = None
            for row in rows:
                d, o, cc, h, lo, v, amt, turn = row
                if prev is None or prev == 0:
                    amp, pct, chg = 0.0, 0.0, 0.0
                else:
                    amp = round((h - lo) / prev * 100, 2)
                    pct = round((cc - prev) / prev * 100, 2)
                    chg = round(cc - prev, 3)
                fh.write(f"{d},{o},{cc},{h},{lo},{v},{amt},{amp},{pct},{chg},{turn}\n")
                prev = cc
        summary[code6(c)] = {"label": label, "rows": len(rows), "first": rows[0][0], "last": rows[-1][0]}
        print(f"[ok] {label}: {len(rows)} rows {rows[0][0]} ~ {rows[-1][0]}")
    with open(os.path.join(DATA_DIR, "_summary_b3_fetch.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
    print("\n===== SUMMARY =====")
    for k, v in summary.items():
        print(f"  stk_{k}: rows={v['rows']} {v.get('first','')}~{v.get('last','')}")

if __name__ == "__main__":
    main()
