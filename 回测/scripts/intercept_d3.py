# -*- coding: utf-8 -*-
"""D3口径拦截统计 —— 逐日回放建仓管线(完整模拟组合状态), 统计各闸门拦截数 (样本内2019-2024)
对比 B7r(旧口径) 与 D3r(修复口径) 的拦截分布, 定位样本内行业ETF建仓为何仍稀疏
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MODE = sys.argv[1] if len(sys.argv) > 1 else "D3"  # B7r / D3
STOCKCHANNEL_V5 = os.environ.get("BT_STOCKCHANNEL_V5", "0") == "1"
STOCK_QUOTA = int(os.environ.get("BT_STOCK_QUOTA", "3"))  # v5.0 修正：个股上限=3，A股为组合大占比核心（3只 vs ETF补位约2只）
if MODE == "B7r":
    os.environ["BT_FIXL5"] = "0"; os.environ["BT_R1"] = "0"
    os.environ["BT_R2"] = "0"; os.environ["BT_R3"] = "0"
else:
    os.environ["BT_FIXL5"] = "1"; os.environ["BT_R1"] = "1"
    os.environ["BT_R2"] = "1"; os.environ["BT_R3"] = "1"
os.environ["BT_TRE_VARIANT"] = "V1"
os.environ["BT_SCORE_GATE"] = "70"; os.environ["BT_OBS_GATE"] = "78"

import run_backtest as bt
from engine import Portfolio

# v5.0 #167 验证：动态扩展 UNIVERSE 至全部可用个股数据（突破硬编码8只瓶颈）
if os.environ.get("BT_UNIV_V5", "0") == "1":
    import glob as _glob
    _dd = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    for _f in _glob.glob(os.path.join(_dd, "stk_*.csv")):
        _code = os.path.basename(_f)[4:-4]
        if _code not in bt.UNIVERSE:
            bt.UNIVERSE[_code] = ("stk_" + _code, _code, "stock", None)

panels0, fins = bt.load_all()
panels = bt.build_panels(panels0)
hs = panels["idx_hs300"]
dates = hs.index

# 复用主程序状态循环 (简化: 只跑建仓管线统计, 离场用基础版本)
class SimPF:
    def __init__(self):
        self.holdings = {}; self.cash = 1e6; self.qual_block = {}
    def equity(self, px):
        v = self.cash
        for c, p in self.holdings.items():
            pxv = px.get(c)
            price = float(pxv) if pxv is not None else p["px"]
            v += p["shares"] * price
        return v
    def buy(self, code, price, target_w, eq):
        amt = eq * target_w / 100.0
        sh = int(amt / price / 100) * 100
        if sh <= 0: return None
        cost = sh * price * 1.001
        if cost > self.cash: return None
        self.cash -= cost
        self.holdings[code] = {"shares": sh, "px": price, "cost": cost}
        return self.holdings[code]
    def sell(self, code, ratio=1.0, price=0):
        if code not in self.holdings: return
        p = self.holdings[code]
        amt = p["shares"] * price * ratio * 0.998
        self.cash += amt
        if ratio >= 0.999:
            del self.holdings[code]

STATS = ["层级1", "RPS", "R值C级", "TRE不可建仓", "得分门槛", "组合约束",
         "七灯", "MIN≤0", "ATR/流动性", "F04<3%", "风险预算", "总仓位上限", "行业>30%"]
tot = {k: 0 for k in STATS}
n_buy = 0
stock_buy = 0
obs_entries = 0
pf = SimPF()
tre = bt.TreState()
cap = 100.0
prev_obs = False

for i, t1 in enumerate(dates):
    if t1 < "2019-01-02" or t1 > "2024-12-31":
        continue
    h = hs.loc[t1]
    core_adx = [panels[x].loc[t1, "ADX14"] for x in bt.CORE_IDX]
    hs300_ret = panels["idx_hs300"]["close"].pct_change().loc[:t1]
    vol20 = float(hs300_ret.tail(20).std(ddof=1) * np.sqrt(252) * 100)
    bt.step_tre(tre, i, core_adx, int(h["CROSS20"]), vol20,
                float(h["BELOW_STREAK"]), bool(h["close"] > h["MA60"]), variant="V1")
    if tre.obs_active and not prev_obs:
        obs_entries += 1
    prev_obs = tre.obs_active

    rows = {}
    for code, (dn, name, ptype, ind) in bt.UNIVERSE.items():
        if t1 in panels[dn].index:
            rows[code] = panels[dn].loc[t1]
    if not rows:
        continue
    scores = {}
    for code, (dn, name, ptype, ind) in bt.UNIVERSE.items():
        if code not in rows: continue
        row = rows[code]
        scores[code] = bt.compute_score(code, dn, ptype, row, fins, panels)
    open_px = {c: r["open"] for c, r in rows.items()}

    # 组合Beta (同主程序: BETA60/100 加权)
    close_px = {c: float(r["close"]) for c, r in rows.items()}
    beta = 0.0
    for c, p in pf.holdings.items():
        if c in rows:
            beta += (rows[c].get("BETA60", 100) / 100.0) * (p["shares"] * p["px"]) / max(pf.equity(close_px), 1)
    eq_t1 = pf.equity(close_px)

    melt = 0  # 熔断简化: 不模拟
    melt_block = False
    if not melt_block:
        cands = [c for c in bt.UNIVERSE if c in rows]
        cands.sort(key=lambda c: scores.get(c, 0), reverse=True)
        # v5.0 #167 个股专属配额：个股优先占用前 STOCK_QUOTA 名额（与 run_backtest.py 一致）
        if STOCKCHANNEL_V5 and STOCK_QUOTA > 0:
            _stk = [c for c in cands if bt.UNIVERSE[c][2] == "stock"]
            _etf = [c for c in cands if bt.UNIVERSE[c][2] != "stock"]
            cands = _stk[:STOCK_QUOTA] + _etf + _stk[STOCK_QUOTA:]
        for code in cands:
            if code in pf.holdings:
                continue
            if code in pf.qual_block and i < pf.qual_block[code]["until"]:
                continue
            row = rows[code]
            dn, name, ptype, ind = bt.UNIVERSE[code]
            fin = None
            if ptype == "stock":
                f = bt.fin_at(fins[code], t1) if code in fins else None; fin = dict(f) if f else None
                if fin: fin["price"] = row["close"]
            if ptype == "stock":
                ok1, r1 = bt.layer1_stock(fin)
            else:
                ok1, r1 = bt.layer1_etf(row, product_ok=True, amount_min=3000e4)
            if not ok1:
                tot["层级1"] += 1; continue
            if ptype == "stock" and STOCKCHANNEL_V5:
                rps_floor = 20  # v5.0 #167：个股 RPS 硬门槛≥30→≥20
            else:
                rps_floor = 30
            if row.get("RPS60", 50) < rps_floor:
                tot["RPS"] += 1; continue
            if ptype != "stock":
                r_level = "A"
            else:
                _r = row.get("R", 99)
                if STOCKCHANNEL_V5:
                    # v5.0 #167：R值去硬否决，仅 R>0.35 否决；0.25-0.35 交MIN③降权
                    r_level = "A" if _r <= 0.15 else ("B" if _r <= 0.35 else "C")
                    if _r > 0.35:
                        tot["R值C级"] += 1; continue
                else:
                    r_level = "A" if _r <= 0.25 else "C"
                    if r_level == "C":
                        tot["R值C级"] += 1; continue
            obs_mode = tre.obs_active
            s3_mode = tre.state == "S3" and not obs_mode
            s12_mode = tre.state in ("S1", "S2") and not obs_mode
            if not (obs_mode or s3_mode or s12_mode):
                tot["TRE不可建仓"] += 1; continue
            etfi = (ptype == "etf_ind") and bt.R2_ON
            g_s1 = bt.ETFI_GATE_S1 if etfi else bt.SCORE_GATE
            g_s2 = bt.ETFI_GATE_S2 if etfi else bt.S2_GATE
            g_obs = bt.ETFI_GATE_OBS if etfi else bt.OBS_GATE
            if STOCKCHANNEL_V5 and ptype == "stock":
                # v5.0 #167：个股通道独立门槛=70（原SCORE_GATE基线；统一75结构性饿死个股通道）
                g_s1 = g_s2 = g_obs = 70.0
            if obs_mode or s3_mode:
                if scores.get(code, 0) < g_obs:
                    tot["得分门槛"] += 1; continue
            elif tre.state == "S2":
                if scores.get(code, 0) < g_s2:
                    tot["得分门槛"] += 1; continue
            else:
                if scores.get(code, 0) < g_s1:
                    tot["得分门槛"] += 1; continue
            n_hold = len(pf.holdings)
            n_same = sum(1 for c2 in pf.holdings if bt.UNIVERSE[c2][3] == ind and ind)
            if n_hold >= 5 or (ind and n_same >= 2):
                tot["组合约束"] += 1; continue
            open_pct = (open_px[code] / row["close"] - 1) * 100 if row["close"] > 0 else 99
            if ptype == "stock":
                ok_l, lights = bt.six_lights(row.to_dict(), tre.state, tre.obs_active, tre.state == "S3",
                                             n_hold, n_same, beta, cap, open_pct, r_level)
            else:
                ok_l, lights = bt.seven_lights(row.to_dict(), tre.state, tre.obs_active, n_hold, n_same,
                                               beta, cap, open_pct, r_level, True, True,
                                               row.get("ma60_break90", 0),
                                               ind_etf=(ptype == "etf_ind") and bt.R1_ON)
            if not ok_l:
                tot["七灯"] += 1; continue
            mn_row = row.to_dict()
            if ptype != "stock":
                mn_row["R"] = 0.0
            min_pct, items = bt.min_nine(mn_row, tre.state, tre.obs_active, tre.state == "S3",
                                         fin, row.get("PB_EXPAND", 1.0),
                                         ind_etf=(ptype == "etf_ind") and bt.R3_ON)
            if min_pct <= 0:
                tot["MIN≤0"] += 1; continue
            base_atr = panels["idx_hs300"].loc[t1, "ATR20P"]
            atr_scale = min(base_atr / max(row.get("ATR20P", 2.0), 0.5), 1.5)
            if row.get("ATR20P", 0) > 8:
                tot["ATR/流动性"] += 1; continue
            amt20 = row.get("amount20", 0)
            if ptype == "stock":
                liq_cap = 15.0 if amt20 >= 5e8 else (12.0 if amt20 >= 1e8 else (8.0 if amt20 >= 5e7 else 0.0))
            else:
                liq_cap = 15.0 if amt20 >= 5e8 else (12.0 if amt20 >= 1e8 else (8.0 if amt20 >= 3e7 else 0.0))
            if liq_cap <= 0:
                tot["ATR/流动性"] += 1; continue
            target = bt.f04(min_pct, atr_scale, liq_cap)
            if target <= 0:
                tot["F04<3%"] += 1; continue
            risk_budget = target * row.get("ATR20P", 3.0) / 100.0
            if risk_budget > 1.0:
                target = 1.0 / max(row.get("ATR20P", 3.0) / 100.0, 0.01)
                if target < 3.0:
                    tot["风险预算"] += 1; continue
            eq_now = pf.equity(close_px)
            pos_pct = 1.0 - pf.cash / max(eq_now, 1)
            if pos_pct + target / 100.0 > cap / 100.0:
                target = max(0.0, (cap / 100.0 - pos_pct) * 100.0)
                if target < 3.0:
                    tot["总仓位上限"] += 1; continue
            if ind:
                ind_w = sum(pf.holdings[c2]["shares"] * rows[c2]["close"] for c2 in pf.holdings if bt.UNIVERSE[c2][3] == ind) / max(eq_now, 1)
                if (ind_w + target / 100.0) > 0.30:
                    target = max(0.0, (0.30 - ind_w) * 100.0)
                    if target < 3.0:
                        tot["行业>30%"] += 1; continue
            p = pf.buy(code, open_px[code], target, eq_now)
            if p:
                n_buy += 1
                if ptype == "stock":
                    stock_buy += 1
                reason = "观察通道试探建仓" if obs_mode else ("S3有限建仓" if s3_mode else ("S2减半建仓" if tre.state == "S2" else "S1正常建仓"))
                if n_buy <= 30:
                    print(f"  [{MODE}] {t1} {code} {reason} score={scores[code]:.0f} tre={tre.state} obs={obs_mode}")

print(f"\n=== {MODE} 拦截统计 (样本内2019-2024, 简化无离场) ===")
for k in STATS:
    print(f"  {k:<10}: {tot[k]:>6}")
print(f"  建仓数   : {n_buy}  (其中个股: {stock_buy})")
print(f"  观察通道 : {obs_entries}次")
