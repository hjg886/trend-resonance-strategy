# -*- coding: utf-8 -*-
"""
v4.7-R10 重构 R-09 标的面扩展数据拉取 —— 18 只新标的（12 ETF + 6 个股）
通道: westockdata skill (腾讯自选股数据接口, 每请求硬上限250行)
半年度分片 2018H1 ~ 2026H1, qfq 前复权
输出: ../data/{name}.csv  列: date,open,close,high,low,volume,amount,amp,pct_chg,chg,turnover
"""
import os, re, subprocess, time, json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")

CODES = [
    # --- 宽基/风格 ETF 4只 ---
    "sh510050", "sh510500", "sh510880", "sz159920",
    # --- 行业 ETF 8只 ---
    "sh512400", "sh512660", "sh515790", "sz159995",
    "sh515000", "sh512980", "sh515050", "sh516160",
    # --- 个股 6只 ---
    "sh600519", "sh600036", "sh601318", "sz000858", "sz300750", "sz000333",
]
NAMES = {
    "sh510050": "上证50ETF", "sh510500": "中证500ETF", "sh510880": "红利ETF", "sz159920": "恒生ETF",
    "sh512400": "有色金属ETF", "sh512660": "军工ETF", "sh515790": "光伏ETF", "sz159995": "芯片ETF",
    "sh515000": "科技ETF", "sh512980": "传媒ETF", "sh515050": "5G通信ETF", "sh516160": "新能源ETF",
    "sh600519": "贵州茅台", "sh600036": "招商银行", "sh601318": "中国平安",
    "sz000858": "五粮液", "sz300750": "宁德时代", "sz000333": "美的集团",
}
# 半年度窗口 2018H1 ~ 2026H1
RANGES = []
for y in range(2018, 2027):
    RANGES.append((f"{y}-01-01", f"{y}-06-30"))
    RANGES.append((f"{y}-07-01", f"{y}-12-31"))
RANGES = [r for r in RANGES if r[0] <= "2026-07-01"]

NODE_DIR = r"C:\Users\hanji\.workbuddy\binaries\node\versions\22.22.2"
NPX = os.path.join(NODE_DIR, "npx.cmd")

ROW_RE = re.compile(
    r"^\|\s*(\w{2}\d{6})\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|"
)

def fetch_batch(start: str, end: str) -> dict[str, list]:
    cmd = [NPX, "-y", "westock-data-skillhub@1.0.5", "kline", ",".join(CODES),
           "--start", start, "--end", end, "--fq", "qfq", "--limit", "250"]
    print(f"  [run] {start}~{end}", flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        print(f"    !! exit={r.returncode} stderr={r.stderr[:300]}", flush=True)
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
    os.makedirs(DATA_DIR, exist_ok=True)
    all_data = {c: [] for c in CODES}
    for (s, e) in RANGES:
        batch = fetch_batch(s, e)
        for c in CODES:
            rows = batch.get(c, [])
            seen_dates = {row[0] for row in all_data[c]}
            for row in rows:
                if row[0] not in seen_dates:
                    seen_dates.add(row[0])
                    all_data[c].append(row)
        time.sleep(0.6)

    summary = {}
    for c in CODES:
        rows = all_data[c]
        rows.sort(key=lambda r: r[0])
        name = ("etf_" if c[:2] in ("sh", "sz") and c[2:5] in ("510", "159", "512", "515", "516") else "stk_") + c[2:]
        label = NAMES[c]
        if not rows:
            print(f"[fail] {label} ({c}) 空数据", flush=True)
            summary[name] = {"label": label, "rows": 0, "note": "FAILED"}
            continue
        path = os.path.join(DATA_DIR, f"{name}.csv")
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            fh.write("date,open,close,high,low,volume,amount,amp,pct_chg,chg,turnover\n")
            prev_close = None
            for row in rows:
                d, o, c_, h, lo, v, amt, turn = row
                if prev_close is None or prev_close == 0:
                    amp, pct, chg = 0.0, 0.0, 0.0
                else:
                    amp = round((h - lo) / prev_close * 100, 2)
                    pct = round((c_ - prev_close) / prev_close * 100, 2)
                    chg = round(c_ - prev_close, 3)
                fh.write(f"{d},{o},{c_},{h},{lo},{v},{amt},{amp},{pct},{chg},{turn}\n")
                prev_close = c_
        summary[name] = {"label": label, "rows": len(rows),
                         "first": rows[0][0], "last": rows[-1][0], "note": "src=westockdata(tx) fq=qfq"}
        print(f"[ok] {label}: {len(rows)} rows  {rows[0][0]} ~ {rows[-1][0]}", flush=True)

    with open(os.path.join(DATA_DIR, "_summary_r10.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
    print("\n===== SUMMARY =====")
    for k, v in summary.items():
        print(f"  {k}: rows={v['rows']} {v['first']}~{v['last']}")

if __name__ == "__main__":
    main()
