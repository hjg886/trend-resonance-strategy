# -*- coding: utf-8 -*-
"""v5.0 #167 诊断：仅保留个股池运行真实回测管线(含R-04 vol_block/六灯/MIN/出口风控/离场),
定位个股究竟死在哪个闸门 —— 复用了 run_backtest 全部真实逻辑, 仅裁剪 UNIVERSE 为个股。
"""
import os, glob, json
os.environ["BT_UNIV_V5"] = "1"
os.environ["BT_STOCKCHANNEL_V5"] = "1"
os.environ["BT_STOCK_QUOTA"] = "0"   # 个股only, 配额无意义
import run_backtest as bt

# 动态扩池至全部可用个股
_dd = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
for _f in glob.glob(os.path.join(_dd, "stk_*.csv")):
    _code = os.path.basename(_f)[4:-4]
    if _code not in bt.UNIVERSE:
        bt.UNIVERSE[_code] = ("stk_" + _code, _code, "stock", None)
# 仅保留个股
bt.UNIVERSE = {c: v for c, v in bt.UNIVERSE.items() if v[2] == "stock"}
print("个股池规模:", len(bt.UNIVERSE))

panels0, fins = bt.load_all()
panels = bt.build_panels(panels0)
panels = bt.add_pit_pb(panels, fins)
days = list(panels["idx_hs300"].index)
warm = [d for d in days if d >= "2018-06-01" and d < bt.PERIOD_IN[0]]
res = bt.run_backtest(panels, fins,
                      warm + [d for d in days if d >= bt.PERIOD_IN[0] and d <= bt.PERIOD_IN[1]],
                      bt.PERIOD_IN, "个股only")
print("个股建仓数:", len(res["buys"]))
for b in res["buys"]:
    print("  ", b["date"], b["code"], b["reason"], "score=%.0f" % b["score"], b["tre"], "r=", b.get("r_level"))
print("=== 拦截分布(个股) ===")
for k, v in res["stats"]["intercept"].items():
    if v:
        print("  %-16s: %d" % (k, v))
