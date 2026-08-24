# -*- coding: utf-8 -*-
"""
回测数据拉取脚本 —— 东方财富历史K线接口（与用户 Choice 数据源同源）
拉取 2018-01-01 至 2026-06-30 日线（前复权），2018年为指标预热期（MA60/ADX/ATR/波动率）
输出: ../data/{name}.csv  列: date,open,close,high,low,volume,amount,amp,pct_chg,chg,turnover
"""
import json, time, sys, os
import requests

BASE = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
PARAMS = {
    "fields1": "f1,f2,f3,f4,f5,f6",
    "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
    "klt": "101",       # 日线
    "fqt": "1",         # 前复权
    "beg": "20180101",
    "end": "20260630",
}

# secid: 1=沪市 0=深市 100=美股指数 124=港指 101=期货
TARGETS = {
    # --- TRE 核心指数 ---
    "idx_hs300":   ("1.000300",  "沪深300指数"),
    "idx_sh":      ("1.000001",  "上证指数"),
    "idx_sz":      ("0.399001",  "深证成指"),
    # --- 个股观察池 ---
    "stk_600276":  ("1.600276",  "恒瑞医药"),
    "stk_603259":  ("1.603259",  "药明康德"),
    # --- ETF ---
    "etf_510300":  ("1.510300",  "沪深300ETF"),
    "etf_159915":  ("0.159915",  "创业板ETF"),
    "etf_588000":  ("1.588000",  "科创50ETF"),
    "etf_512010":  ("1.512010",  "医药ETF"),
    "etf_159928":  ("0.159928",  "消费ETF"),
    "etf_512880":  ("1.512880",  "证券ETF"),
    "etf_512690":  ("1.512690",  "酒ETF"),
    "etf_515030":  ("1.515030",  "新能源车ETF"),
    "etf_512480":  ("1.512480",  "半导体ETF"),
    "etf_512170":  ("1.512170",  "医疗ETF"),
    "etf_159650":  ("0.159650",  "国开债ETF"),
    # --- B股（独立持仓，不进入策略，仅记录） ---
    "stk_900912":  ("1.900912",  "外高B"),
    # --- 跨资产验证（回测纪律第4条） ---
    "x_hstech":    ("124.HSTECH","恒生科技指数"),
    "x_nasdaq100": ("100.NDX",   "纳斯达克100"),
    "x_gold":      ("101.GC00Y", "COMEX黄金主力"),
    "x_us10y":     ("100.US10Y", "美国10年期国债收益率"),
}

HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
}

def fetch(secid: str, retry: int = 3) -> dict | None:
    p = dict(PARAMS); p["secid"] = secid
    for i in range(retry):
        try:
            r = requests.get(BASE, params=p, headers=HDRS, timeout=20)
            j = r.json()
            if j and j.get("data") and j["data"].get("klines"):
                return j["data"]
            print(f"    [warn] secid={secid} 空数据: {str(j)[:120]}", flush=True)
            return None
        except Exception as e:
            print(f"    [retry {i+1}] secid={secid} err={e}", flush=True)
            time.sleep(1.5)
    return None

def main():
    out_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(out_dir, exist_ok=True)
    summary = {}
    for name, (secid, label) in TARGETS.items():
        print(f"[fetch] {label} ({secid})", flush=True)
        data = fetch(secid)
        if not data or "klines" not in data:
            print(f"  -> FAILED {name}", flush=True)
            summary[name] = {"label": label, "rows": 0, "note": "FAILED"}
            continue
        rows = []
        for line in data["klines"]:
            f = line.split(",")
            # f51日期 f52开 f53收 f54高 f55低 f56量 f57额 f58振幅 f59涨跌幅 f60涨跌额 f61换手
            rows.append({
                "date": f[0], "open": float(f[1]), "close": float(f[2]),
                "high": float(f[3]), "low": float(f[4]), "volume": float(f[5]),
                "amount": float(f[6]), "amp": float(f[7]),
                "pct_chg": float(f[8]), "chg": float(f[9]), "turnover": float(f[10]),
            })
        path = os.path.join(out_dir, f"{name}.csv")
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            fh.write("date,open,close,high,low,volume,amount,amp,pct_chg,chg,turnover\n")
            for r in rows:
                fh.write(f"{r['date']},{r['open']},{r['close']},{r['high']},{r['low']},"
                         f"{r['volume']},{r['amount']},{r['amp']},{r['pct_chg']},{r['chg']},{r['turnover']}\n")
        summary[name] = {
            "label": label, "rows": len(rows),
            "first": rows[0]["date"] if rows else None,
            "last": rows[-1]["date"] if rows else None,
            "note": data.get("name", ""),
        }
        print(f"  -> {len(rows)} rows  {rows[0]['date']} ~ {rows[-1]['date']}", flush=True)
        time.sleep(0.6)

    print("\n===== SUMMARY =====")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    with open(os.path.join(out_dir, "_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
