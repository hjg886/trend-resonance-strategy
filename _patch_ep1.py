# -*- coding: utf-8 -*-
"""修正实盘辅助脚本的 ETF 止损公式口径。
策略 11.4：个股 P1 = 买入价 - MIN(2×ATR, 带宽%)；ETF E-P1 = 买入价 - 带宽%。
5 个实盘脚本误将 ETF 用个股 P1 公式（MIN(2×ATR,带宽)），导致止损线偏高、过早止损。
"""
import io, os, shutil, sys

ROOT = r"E:\fnOS\文档\证券\中线趋势共振策略"

# 每文件：(old, new) 列表
PATCHES = {
    "pre_market_calc_0820.py": [
        (
            "etf_p1 = etf_cost - min(2 * etf_atr, etf_cost * etf_r06_band) if etf_atr else etf_cost * (1 - etf_r06_band)",
            "# 【修正·ETF止损口径】ETF E-P1 = 买入价 - 带宽%（策略11.4，非个股 MIN(2×ATR,带宽)）\netf_p1 = etf_cost * (1 - etf_r06_band)"
        ),
    ],
    "pre_market_0820_calc.py": [
        (
            "    # P1止损位 = 买入价 - MIN(2×ATR, 买入价×带宽%)\n    bw_amount = cost * bandwidth / 100\n    min_stop = min(2 * atr, bw_amount) if atr else bw_amount\n    p1_stop = cost - min_stop",
            "    # 【修正·ETF止损口径】策略11.4：个股P1=买入价-MIN(2×ATR,带宽%)；ETF E-P1=买入价-带宽%\n    bw_amount = cost * bandwidth / 100\n    if 'ETF' in h['name']:\n        p1_stop = cost * (1 - bandwidth / 100)          # ETF E-P1\n    else:\n        min_stop = min(2 * atr, bw_amount) if atr else bw_amount\n        p1_stop = cost - min_stop                       # 个股 P1"
        ),
    ],
    "pre_market_0821_calc.py": [
        (
            "    # P1止损 = 买入价 - MIN(2×ATR, 止损带宽%)\n    sl_amount = min(2 * atr, h['cost'] * sl_band) if atr else h['cost'] * sl_band\n    p1 = h['cost'] - sl_amount",
            "    # 【修正·ETF止损口径】策略11.4：个股P1=买入价-MIN(2×ATR,带宽%)；ETF E-P1=买入价-带宽%\n    if 'ETF' in h['name']:\n        p1 = h['cost'] * (1 - sl_band)                   # ETF E-P1\n    else:\n        sl_amount = min(2 * atr, h['cost'] * sl_band) if atr else h['cost'] * sl_band\n        p1 = h['cost'] - sl_amount                      # 个股 P1"
        ),
    ],
    "close_summary_calc.py": [
        (
            "    # P1止损\n    bw_amount = cost * bandwidth / 100\n    p1_stop = cost - min(2 * atr, bw_amount) if atr else cost - bw_amount",
            "    # 【修正·ETF止损口径】策略11.4：个股P1=买入价-MIN(2×ATR,带宽%)；ETF E-P1=买入价-带宽%\n    bw_amount = cost * bandwidth / 100\n    if 'ETF' in pos['name']:\n        p1_stop = cost * (1 - bandwidth / 100)          # ETF E-P1\n    else:\n        p1_stop = cost - min(2 * atr, bw_amount) if atr else cost - bw_amount  # 个股 P1"
        ),
    ],
    "live_execution_calc.py": [
        (
            "    # P1止损\n    bw_amount = cost * bandwidth / 100\n    p1_stop = cost - min(2 * atr, bw_amount) if atr else cost - bw_amount",
            "    # 【修正·ETF止损口径】策略11.4：个股P1=买入价-MIN(2×ATR,带宽%)；ETF E-P1=买入价-带宽%\n    bw_amount = cost * bandwidth / 100\n    if 'ETF' in pos['name']:\n        p1_stop = cost * (1 - bandwidth / 100)          # ETF E-P1\n    else:\n        p1_stop = cost - min(2 * atr, bw_amount) if atr else cost - bw_amount  # 个股 P1"
        ),
    ],
}

all_ok = True
for fname, pairs in PATCHES.items():
    path = os.path.join(ROOT, fname)
    bak = path + ".bak_20260821"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
        print(f"[BAK] {bak}")
    with io.open(path, "r", encoding="utf-8") as f:
        c = f.read()
    for old, new in pairs:
        n = c.count(old)
        if n != 1:
            print(f"[FAIL] {fname}: count={n} for {old[:50]!r}")
            all_ok = False
        else:
            c = c.replace(old, new, 1)
            print(f"[OK]   {fname}: {old[:50]!r}")
    if all_ok:
        with io.open(path, "w", encoding="utf-8", newline="") as f:
            f.write(c)

print("\nALL DONE" if all_ok else "\nSOME FAILED")
sys.exit(0 if all_ok else 1)
