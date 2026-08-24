# -*- coding: utf-8 -*-
"""
观察池 24 只个股 K线全量拉取管线 —— 半年度分片 + 批量
通道: westockdata skill (腾讯自选股数据接口, 每请求硬上限250行)
输出: ../data/stk_<code>.csv —— 与东财格式一致
    date,open,close,high,low,volume,amount,amp,pct_chg,chg,turnover
    volume:手  amount:元  turnover:换手率%  amp/pct_chg:%
复权: qfq 前复权（全量重拉保证复权基准一致，覆盖旧文件）
依据: 选股报告观察池24只名单（v4.7-R10首轮，2026-08-18）
修正: data_gap.md 原"缺口16只"误算（已就绪8只中含5只非观察池标的），实际缺口21只+3只已有增量=全量24只
"""
import os, re, subprocess, time, json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")

# 观察池 24 只（选股报告权威名单，按评分降序）
CODES = [
    "sh603259", "sz300357", "sh605117", "sh688120", "sz002371",
    "sz300750", "sh600196", "sz002156", "sh688082", "sz300661",
    "sz300693", "sh600276", "sh600584", "sh688239", "sh603986",
    "sh688008", "sh603005", "sz002335", "sz002472", "sz002050",
    "sz002111", "sz000099", "sz002518", "sh688686",
]
NAMES = {
    "sh603259": "药明康德", "sz300357": "我武生物", "sh605117": "德业股份",
    "sh688120": "华海清科", "sz002371": "北方华创", "sz300750": "宁德时代",
    "sh600196": "复星医药", "sz002156": "通富微电", "sh688082": "盛美上海",
    "sz300661": "圣邦股份", "sz300693": "盛弘股份", "sh600276": "恒瑞医药",
    "sh600584": "长电科技", "sh688239": "航宇科技", "sh603986": "兆易创新",
    "sh688008": "澜起科技", "sh603005": "晶方科技", "sz002335": "科华数据",
    "sz002472": "双环传动", "sz002050": "三花智控", "sz002111": "威海广泰",
    "sz000099": "中信海直", "sz002518": "科士达", "sh688686": "奥普特",
}
# 半年度窗口 2018H1 ~ 2026H2（2026H2 接口自然返回至最新交易日）
RANGES = []
for y in range(2018, 2027):
    RANGES.append((f"{y}-01-01", f"{y}-06-30"))
    RANGES.append((f"{y}-07-01", f"{y}-12-31"))

NODE_DIR = r"C:\Users\hanji\.workbuddy\binaries\node\versions\22.22.2"
NPX = os.path.join(NODE_DIR, "npx.cmd")

# 批量输出行: | symbol | date | open | last | high | low | volume | amount | exchange |
ROW_RE = re.compile(
    r"^\|\s*(\w{2}\d{6})\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|"
)

def fetch_batch(start: str, end: str) -> dict[str, list]:
    """批量拉取一个半年度窗口, 返回 {code: [[date,o,c,h,lo,v,amt,turn],...](升序)}"""
    cmd = [NPX, "-y", "westock-data-skillhub@1.0.5", "kline", ",".join(CODES),
           "--start", start, "--end", end, "--fq", "qfq", "--limit", "250"]
    print(f"  [run] {start}~{end}", flush=True)
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
        out[c].reverse()  # 降序->升序
    # 覆盖率断言: 该窗口返回的标的数
    missing = [c for c in CODES if c not in out]
    if missing:
        print(f"    !! 窗口 {start}~{end} 缺失 {len(missing)} 只: {missing}", flush=True)
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
        time.sleep(0.8)

    summary = {}
    for c in CODES:
        rows = all_data[c]
        rows.sort(key=lambda r: r[0])
        name = "stk_" + c[2:]
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

    with open(os.path.join(DATA_DIR, "_summary_attack.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
    print("\n===== SUMMARY =====")
    for k, v in summary.items():
        print(f"  {k}: rows={v['rows']} {v['first']}~{v['last']}")

if __name__ == "__main__":
    main()
