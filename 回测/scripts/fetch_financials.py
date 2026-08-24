# -*- coding: utf-8 -*-
"""
PIT 财报数据拉取 —— 东财 F10 主要财务指标（含 NOTICE_DATE 公告日，用于 Point-in-Time 对齐）
层级1财报硬过滤 + 24因子基本面部分 的回测数据源
"""
import requests, json, time, os, sys

HDRS = {"User-Agent": "Mozilla/5.0", "Referer": "https://emweb.securities.eastmoney.com/"}
URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
PARAMS = {
    "reportName": "RPT_F10_FINANCE_MAINFINADATA",
    "columns": "ALL",
    "quoteColumns": "",
    "pageNumber": "1",
    "pageSize": "200",
    "sortTypes": "-1",
    "sortColumns": "REPORT_DATE",
    "source": "HSF10",
    "client": "PC",
}
STOCKS = {"600276": "600276.SH", "603259": "603259.SH"}

# 需要保留的字段（先全量获取，脚本内选择）
KEEP = [
    "SECUCODE", "REPORT_DATE", "NOTICE_DATE",
    "TOTALOPERATEREVETZ",      # 营业总收入同比增长率
    "PARENTNETPROFITTZ",       # 归母净利润同比增长率
    "SJLTZ",                   # 实际利润(扣非?)增长率
    "ROEJQ",                   # 净资产收益率(加权)
    "BPS",                     # 每股净资产
    "EPSJB",                   # 基本每股收益
    "MGJYXJJE",                # 每股经营现金流量
    "XSMLL",                   # 销售毛利率
    "ZCFZL",                   # 资产负债率
    "KCFJCXSYJLR",             # 扣非净利润(可能字段)
    "PARENTNETPROFIT",         # 归母净利润(可能字段)
    "TOTALOPERATEREVE",        # 营业总收入(可能字段)
]

def fetch(secucode: str) -> list:
    p = dict(PARAMS); p["filter"] = f'(SECUCODE="{secucode}")'
    for attempt in range(3):
        try:
            j = requests.get(URL, params=p, headers=HDRS, timeout=25).json()
            d = j.get("result")
            if d and d.get("data"):
                return d["data"]
            print(f"[warn] {secucode} empty: {str(j)[:150]}", flush=True)
        except Exception as e:
            print(f"[retry] {secucode} err={e}", flush=True)
        time.sleep(1.5)
    return []

def main():
    out = {}
    for code, secu in STOCKS.items():
        rows = fetch(secu)
        print(f"[fetch] {code} rows={len(rows)}", flush=True)
        recs = []
        for r in rows:
            rec = {k: r.get(k) for k in KEEP}
            # 时间归一化
            for k in ("REPORT_DATE", "NOTICE_DATE"):
                if rec.get(k):
                    rec[k] = str(rec[k])[:10]
            recs.append(rec)
        out[code] = recs
        time.sleep(0.8)
    out_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    with open(os.path.join(out_dir, "financials.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    # 打印样例确认扣非字段名
    for code in out:
        print(f"\n--- {code} 样例(最近2期) ---")
        for r in out[code][:2]:
            print({k: r[k] for k in KEEP if k not in ("SECUCODE",) and r.get(k) is not None})

if __name__ == "__main__":
    main()
