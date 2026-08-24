# -*- coding: utf-8 -*-
"""
观察池 24 只个股 K线数据完整性核验
检查项: 文件存在/非空/格式(11列)/行数/首末日期/日期升序/重复日期/除零异常值
输出: 核验报告 + 更新 _summary_attack.json 的核验状态
"""
import os, json, sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")

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

def check(code: str) -> dict:
    name = "stk_" + code[2:]
    path = os.path.join(DATA_DIR, f"{name}.csv")
    r = {"code": code, "label": NAMES[code], "file": f"{name}.csv"}
    if not os.path.exists(path):
        r.update(ok=False, err="文件不存在"); return r
    with open(path, encoding="utf-8-sig") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    if len(lines) < 2:
        r.update(ok=False, err="空文件"); return r
    header, body = lines[0], lines[1:]
    if header != "date,open,close,high,low,volume,amount,amp,pct_chg,chg,turnover":
        r.update(ok=False, err=f"表头异常: {header}"); return r
    dates, prev = [], None
    bad_cols = 0
    for ln in body:
        cells = ln.split(",")
        if len(cells) != 11:
            bad_cols += 1; continue
        d = cells[0]
        dates.append(d)
        if prev and d <= prev:
            r.setdefault("warn", []).append(f"日期乱序/重复: {d} after {prev}")
        prev = d
        # 数值合法性: close/high/low>0
        try:
            c_, h, lo = float(cells[2]), float(cells[3]), float(cells[4])
            if c_ <= 0 or h <= 0 or lo <= 0:
                r.setdefault("warn", []).append(f"非正价格: {d}")
        except ValueError:
            bad_cols += 1
    r["rows"] = len(body)
    r["first"] = dates[0] if dates else None
    r["last"] = dates[-1] if dates else None
    r["bad_cols"] = bad_cols
    r["ok"] = (len(body) > 200 and bad_cols == 0 and dates == sorted(dates))
    return r

def main():
    results = [check(c) for c in CODES]
    n_ok = sum(1 for x in results if x.get("ok"))
    print(f"===== 核验报告: {n_ok}/{len(CODES)} 通过 =====")
    for r in results:
        flag = "OK " if r.get("ok") else "FAIL"
        print(f"  [{flag}] {r['label']}({r['code']}): rows={r.get('rows','-')} "
              f"{r.get('first','-')}~{r.get('last','-')} bad_cols={r.get('bad_cols',0)}")
        for w in r.get("warn", [])[:3]:
            print(f"        warn: {w}")
        if not r.get("ok"):
            print(f"        err: {r.get('err','')}")
    # 更新 summary
    spath = os.path.join(DATA_DIR, "_summary_attack.json")
    if os.path.exists(spath):
        with open(spath, encoding="utf-8") as f:
            summ = json.load(f)
        for r in results:
            key = r["file"].replace(".csv", "")
            if key in summ:
                summ[key]["check"] = "OK" if r.get("ok") else "FAIL"
        with open(spath, "w", encoding="utf-8") as f:
            json.dump(summ, f, ensure_ascii=False, indent=1)
    return 0 if n_ok == len(CODES) else 1

if __name__ == "__main__":
    sys.exit(main())
