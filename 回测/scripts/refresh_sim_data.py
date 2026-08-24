# -*- coding: utf-8 -*-
"""
模拟盘数据增量刷新管线（2026-08-21 新增）
====================================
用途: 每日/每周增量刷新 B3 模拟盘所需数据, 供 scan_b3_daily.py 使用

刷新范围:
  1. 指数 idx_hs300 / idx_sh / idx_sz —— 批量拉取（现有数据止于 2026-06-30, 首次需补缺）
  2. 观察池 24 只个股 stk_* —— 批量拉取（现有数据止于 2026-08-18）
  3. 现金ETF etf_159650 —— 单股拉取（批量接口混入ETF报 KLINE_006, 须单独查询）

通道: westockdata skill（npx westock-data-skillhub@1.0.5 kline, 每请求硬上限250行）
输出: 合并去重后写回 ../data/*.csv（列格式与 fetch_data.py 一致, utf-8-sig）
      汇总: ../data/_summary_sim_refresh.json

复权说明: 增量使用 qfq 前复权追加; 若标的发生分红/拆股导致复权基准漂移,
          建议每月做一次全量重拉校准（fetch_stk_universe.py / fetch_data.py）
"""
import os, re, subprocess, time, json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")

NODE_DIR = r"C:\Users\hanji\.workbuddy\binaries\node\versions\22.22.2"
NPX = os.path.join(NODE_DIR, "npx.cmd")

# ---------------- 标的清单 ----------------
# (csv文件名, westock symbol, 中文名, 类型)
STOCKS = [
    ("stk_603259", "sh603259", "药明康德"), ("stk_300357", "sz300357", "我武生物"),
    ("stk_605117", "sh605117", "德业股份"), ("stk_688120", "sh688120", "华海清科"),
    ("stk_002371", "sz002371", "北方华创"), ("stk_300750", "sz300750", "宁德时代"),
    ("stk_600196", "sh600196", "复星医药"), ("stk_002156", "sz002156", "通富微电"),
    ("stk_688082", "sh688082", "盛美上海"), ("stk_300661", "sz300661", "圣邦股份"),
    ("stk_300693", "sz300693", "盛弘股份"), ("stk_600276", "sh600276", "恒瑞医药"),
    ("stk_600584", "sh600584", "长电科技"), ("stk_688239", "sh688239", "航宇科技"),
    ("stk_603986", "sh603986", "兆易创新"), ("stk_688008", "sh688008", "澜起科技"),
    ("stk_603005", "sh603005", "晶方科技"), ("stk_002335", "sz002335", "科华数据"),
    ("stk_002472", "sz002472", "双环传动"), ("stk_002050", "sz002050", "三花智控"),
    ("stk_002111", "sz002111", "威海广泰"), ("stk_000099", "sz000099", "中信海直"),
    ("stk_002518", "sz002518", "科士达"), ("stk_688686", "sh688686", "奥普特"),
]
INDICES = [
    ("idx_hs300", "sh000300", "沪深300指数"),
    ("idx_sh", "sh000001", "上证指数"),
    ("idx_sz", "sz399001", "深证成指"),
]
CASH_ETF = ("etf_159650", "sz159650", "国开债ETF")

# 批量返回行: | symbol | date | open | last | high | low | volume | amount | exchange |
ROW_RE_BATCH = re.compile(
    r"^\|\s*(\w{2}\d{6})\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|"
)
# 单股返回行: | date | open | last | high | low | volume | amount | exchange |
ROW_RE_SINGLE = re.compile(
    r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|"
)

CSV_HEADER = "date,open,close,high,low,volume,amount,amp,pct_chg,chg,turnover\n"


def run_kline(symbols, start, end):
    """调用 westockdata kline, 返回 {symbol: {date: [o,c,h,l,v,amt,turn]}} 或单股 dict"""
    if isinstance(symbols, str):
        symbols = [symbols]
    cmd = [NPX, "-y", "westock-data-skillhub@1.0.5", "kline", ",".join(symbols),
           "--start", start, "--end", end, "--fq", "qfq", "--limit", "250"]
    print(f"  [run] {symbols[0] if len(symbols)==1 else f'{len(symbols)}标的'} {start}~{end}", flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        print(f"    !! exit={r.returncode} stderr={r.stderr[:300]}", flush=True)
        return {}
    single = len(symbols) == 1
    out = {}
    for line in r.stdout.splitlines():
        if single:
            m = ROW_RE_SINGLE.match(line.strip())
            if m:
                d = m.group(1)
                out.setdefault(symbols[0], {})[d] = [float(m.group(2)), float(m.group(3)),
                                                     float(m.group(4)), float(m.group(5)),
                                                     float(m.group(6)), float(m.group(7)),
                                                     float(m.group(8))]
        else:
            m = ROW_RE_BATCH.match(line.strip())
            if m:
                sym, d = m.group(1), m.group(2)
                out.setdefault(sym, {})[d] = [float(m.group(3)), float(m.group(4)),
                                              float(m.group(5)), float(m.group(6)),
                                              float(m.group(7)), float(m.group(8)),
                                              float(m.group(9))]
    return out


def last_date_csv(name):
    """读取CSV最后一行日期, 无文件则 None"""
    path = os.path.join(DATA_DIR, f"{name}.csv")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8-sig") as fh:
        lines = [l for l in fh.read().splitlines() if l and not l.startswith("date")]
    return lines[-1].split(",")[0] if lines else None


def merge_append(name, new_rows):
    """把 {date: [o,c,h,l,v,amt,turn]} 按升序合并进CSV（按date去重）"""
    path = os.path.join(DATA_DIR, f"{name}.csv")
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig") as fh:
            lines = [l for l in fh.read().splitlines() if l and not l.startswith("date")]
        rows = [l.split(",") for l in lines]
    else:
        rows = []
    existing = {r[0] for r in rows}
    prev_close = float(rows[-1][2]) if rows else None
    added = 0
    for d in sorted(new_rows.keys()):
        if d in existing:
            continue
        o, c, h, lo, v, amt, turn = new_rows[d]
        if prev_close is None or prev_close == 0:
            amp, pct, chg = 0.0, 0.0, 0.0
        else:
            amp = round((h - lo) / prev_close * 100, 2)
            pct = round((c - prev_close) / prev_close * 100, 2)
            chg = round(c - prev_close, 3)
        rows.append([d, o, c, h, lo, v, amt, amp, pct, chg, turn])
        prev_close = c
        added += 1
    rows.sort(key=lambda r: r[0])
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        fh.write(CSV_HEADER)
        for r in rows:
            fh.write(",".join(str(x) for x in r) + "\n")
    return added, (rows[-1][0] if rows else None)


def refresh_group(items, group_name, batch=True):
    """按 group 批量刷新: items=[(name, symbol, label)]"""
    print(f"\n===== {group_name} =====", flush=True)
    summary = {}
    # 按现有最后日期分桶: 需要拉取的标的 → (start, symbols)
    need = []
    for name, sym, label in items:
        last = last_date_csv(name)
        start = last if last else "2018-01-01"  # 无文件则全量（理论不发生）
        need.append((name, sym, label, last, start))
    # 合并 start 相同的一批（简化: 用最早的 start 拉全组, 去重兜底）
    min_start = min((n[3] for n in need), default="2018-01-01")
    if min_start:
        # 增量: 从最早最后日期+1天开始
        from datetime import datetime, timedelta
        d0 = datetime.strptime(min_start, "%Y-%m-%d") + timedelta(days=1)
        min_start = d0.strftime("%Y-%m-%d")
    today = time.strftime("%Y-%m-%d")
    if min_start > today:
        print(f"  (全部已最新至 {today})", flush=True)
        return {n[0]: {"label": n[2], "added": 0, "note": "already fresh"} for n in need}

    if batch:
        syms = [n[1] for n in need]
        data = run_kline(syms, min_start, today)
    else:
        data = {}
        for name, sym, label, last, start in need:
            data.update(run_kline([sym], min_start, today))

    for name, sym, label, last, start in need:
        rows = data.get(sym, {})
        if not rows:
            summary[name] = {"label": label, "added": 0, "last": last, "note": "NO_NEW"}
            print(f"  [skip] {label}: 无新增数据", flush=True)
            continue
        added, new_last = merge_append(name, rows)
        summary[name] = {"label": label, "added": added, "last": last, "new_last": new_last,
                         "note": "src=westockdata(qfq) merged"}
        print(f"  [ok] {label}: +{added} 行  {last} → {new_last}", flush=True)
        time.sleep(0.6)
    return summary


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    all_sum = {}
    # 1. 指数（批量）
    all_sum.update(refresh_group(INDICES, "指数 idx_* (批量)", batch=True))
    # 2. 观察池个股（批量）
    all_sum.update(refresh_group(STOCKS, "观察池24只个股 (批量)", batch=True))
    # 3. 现金ETF（单股, 批量接口混入报KLINE_006）
    all_sum.update(refresh_group([CASH_ETF], "现金ETF etf_159650 (单股)", batch=False))

    with open(os.path.join(DATA_DIR, "_summary_sim_refresh.json"), "w", encoding="utf-8") as fh:
        json.dump(all_sum, fh, ensure_ascii=False, indent=1)
    print("\n===== 刷新汇总 =====")
    for k, v in all_sum.items():
        print(f"  {k}: +{v.get('added', 0)} 行  {v.get('last', '-')} → {v.get('new_last', v.get('last', '-'))}")


if __name__ == "__main__":
    main()
