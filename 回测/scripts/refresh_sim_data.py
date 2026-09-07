# -*- coding: utf-8 -*-
"""
模拟盘数据增量刷新管线（2026-08-21 新增）
====================================
用途: 每日/每周增量刷新 B3 模拟盘所需数据, 供 B3信号单.py（72池 cand_meta）使用

刷新范围:
  1. 指数 idx_hs300 / idx_sh / idx_sz —— 批量拉取
  2. B3 72 池个股 stk_*（cand_meta.json M 动态生成）—— 批量拉取, 分块(≤20/批)避免单次标的数超限
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

NODE_DIR = r"C:\Users\hanji\.workbuddy\binaries\node\versions\22.22.2-2"
NPX = os.path.join(NODE_DIR, "npx.cmd")

# ---------------- 标的清单（动态：B3 72 池 from cand_meta.json，2026-09-07 改造） ----------------
# 原 24 只观察池(scan_b3_daily / run_attack_b.OBS_POOL)已退休；B3 日度扫描统一使用
# cand_meta.json 的 72 池(M 列表)，refresh 与之同步，避免"池子不一致/数据陈旧"坑。
def load_b3_pool():
    meta_path = os.path.join(BASE_DIR, "..", "tmp", "sectors", "cand_meta.json")
    if not os.path.exists(meta_path):
        print("[WARN] cand_meta.json 缺失, STOCKS 为空（请先生成候选池）")
        return []
    obj = json.load(open(meta_path, encoding="utf-8"))
    names = obj.get("names", {})
    M = obj.get("M", [])
    out = []
    for code in M:
        c6 = code[2:] if code[:2] in ("sh", "sz") else code
        out.append((f"stk_{c6}", code, names.get(code, c6)))
    print(f"[INFO] B3 72 池加载 {len(out)} 只（cand_meta.json M）")
    return out
STOCKS = load_b3_pool()
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


def refresh_group(items, group_name, batch=True, chunk=20):
    """按 group 批量刷新: items=[(name, symbol, label)]。batch 时按 chunk 分块调 westockdata。"""
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
        data = {}
        chunks = [need[i:i + chunk] for i in range(0, len(need), chunk)]
        for ci, ch in enumerate(chunks, 1):
            syms = [n[1] for n in ch]
            print(f"  [batch {ci}/{len(chunks)}] {len(syms)} 标的", flush=True)
            data.update(run_kline(syms, min_start, today))
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
    # 2. B3 72 池个股（动态生成, 批量分块）
    all_sum.update(refresh_group(STOCKS, "B3 72池个股 (批量)", batch=True))
    # 3. 现金ETF（单股, 批量接口混入报KLINE_006）
    all_sum.update(refresh_group([CASH_ETF], "现金ETF etf_159650 (单股)", batch=False))

    with open(os.path.join(DATA_DIR, "_summary_sim_refresh.json"), "w", encoding="utf-8") as fh:
        json.dump(all_sum, fh, ensure_ascii=False, indent=1)
    print("\n===== 刷新汇总 =====")
    for k, v in all_sum.items():
        print(f"  {k}: +{v.get('added', 0)} 行  {v.get('last', '-')} → {v.get('new_last', v.get('last', '-'))}")


if __name__ == "__main__":
    main()
