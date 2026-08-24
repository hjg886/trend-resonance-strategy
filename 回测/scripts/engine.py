# -*- coding: utf-8 -*-
"""
组合模拟器 —— v4.7-R8 回测引擎核心
实现: 持仓管理(P0-P12/E-P0.0~E-P12离场) / 三层封顶资金管理(四层MIN×降档) / 凯利(贝叶斯收缩) /
      降档机制 / 动态回撤阶梯 / 移动止损(A.5) / 时间止损(11.5/E-P9) / 建仓条件时效(11.5a/E-P9.5) /
      组合风控(行业≤30%/Beta分级/风险贡献度) / 熔断代理 / 现金管理 / 双周再平衡
T-1铁律: 所有判定用 T-1 收盘数据, T日开盘价成交（由主循环调度保证）
"""
import numpy as np
from dataclasses import dataclass, field


@dataclass
class Position:
    code: str
    name: str
    ptype: str            # stock / etf_wide / etf_bond
    industry: str | None  # 东财一级行业
    shares: float = 0.0
    cost: float = 0.0              # 加权平均成本价
    lots: list = field(default_factory=list)   # [(date, shares, cost, entry_idx)]
    entry_idx: int = 0             # 建仓日 index（主循环交易日序号）
    max_high: float = 0.0          # 持仓期最高收盘价
    time_cnt: int = 0              # 持有交易日数
    qual_cnt: int = 0              # 11.5a/E-P9.5 30日资格窗口计数（每日盘后监控）
    qual_expired: bool = False     # 30日窗口已满（过期转常规）
    eval_reset: dict = field(default_factory=dict)  # E-P9/11.5 到期评估重置
    obs_probe: bool = False        # 是否观察通道试探仓
    s3_pos: bool = False           # 是否S3有限建仓
    s1_min_hold: bool = False      # H2: 是否S1常规建仓（强制最短持有期豁免E-P1）
    ep4_counter: int = 0           # E-P4 T+10 评估计数
    ep4_flag: bool = False
    open_pct: float = 0.0          # 当日开盘涨幅（用于竞价灯）
    target_w: float = 0.0          # 建仓目标仓位%（F-04输出）
    qual_break: bool = False       # 11.5a/E-P9.5 盘后失守标志（次日开盘清仓）
    qual_break_reason: str = ""


@dataclass
class Trade:
    date: str
    code: str
    name: str
    side: str            # buy / sell
    reason: str
    price: float
    shares: float
    amount: float        # 含成本
    pnl: float = 0.0     # 卖出时结算


class Portfolio:
    def __init__(self, init_cash: float = 1_000_000.0, cost_buy: float = 0.001, cost_sell: float = 0.002):
        self.cash = init_cash
        self.init_cash = init_cash
        self.cost_buy = cost_buy
        self.cost_sell = cost_sell
        self.capital_scale = init_cash / 1_000_000.0   # 规模冲击缩放基准(100万=AUM 1.0)
        self.slip_impact = 0.0                          # 规模冲击成本系数(由主程序按 BT_SLIP_IMPACT 设置)
        self.holdings: dict[str, Position] = {}
        self.trades: list[Trade] = []
        self.equity_hist: list[float] = []
        self.date_hist: list[str] = []
        self.peak = init_cash
        self.drawdown = 0.0
        self.closed_periods: list[dict] = []   # 完整建仓-清仓周期盈亏（降档/凯利用）
        self.pending_sells: list = []          # 因20%上限推迟的卖出
        self.obs_trades: list = []
        self.meltdown_count = {"I": 0, "II": 0, "III": 0}
        self.meltdown_captured = 0
        self.month_start_equity = init_cash
        self.month_ret = 0.0
        self.cash_mgmt_ret = 0.0   # 现金管理累计收益
        self.day_ret = 1.0
        self.vol20_hist = []
        self.prev_vol20 = 0.0
        self.ret_hist_20 = []        # 20日组合收益历史（风险贡献度/波动率用）
        self.qual_block: dict = {}   # 洗仓封堵：code -> {"until": 指数日期idx, "threshold": 85}
        self.cur_month = "00"        # 当前月份（YYYY-MM），双周再平衡锚定
        self.kelly_min = 0.0         # 凯利下限保护（P0-F, 由主程序按开关设置; 默认0=不启用）
        self.kelly_cap = 0.25        # 凯利封顶（F-04专项: 主程序可按 BT_KELLY_CAP 放宽）
        self.ep1_pct = 3.0           # P1/E-P1 技术止损带宽%（默认3; 敏感性测试用）
        self.qual_gate = 85.0        # 11.5a/E-P9.5 资格维持门槛（默认85; 敏感性测试用）
        # R-06 止损带宽时间分档（v4.7-R10）: 持有≤11日噪音保护期5% / >11日趋势确认后3%
        self.tenor_on = False        # R-06 开关（由主程序按 BT_EP1TENOR 设置）
        self.ep1_band_short = 7.0    # 持有≤11个交易日（v5.0 固化基线：对齐主文档R-06 P0d/JOINT回测最优）
        self.ep1_band_long = 4.0     # 持有>11个交易日（v5.0 固化基线：对齐主文档R-06 P0d/JOINT回测最优）
        # H2: S1 强制最短持有期（跳过 P1/E-P1 噪音止损; 由主程序按 BT_H2_MINHOLD 设置）
        self.h2_minhold_on = False
        self.h2_minhold_days = 11
        # P0-1b: 禁用 ETF 的 E-P1 止损（仅靠 P4/E-P0.5/P12/E-P9 兜底）
        self.ep1_ETF_off = False
        # P12 移动止盈引擎参数（可配置, 用于扩大化回测）
        #   tiers = [(min_fp, retr), ...]  升序排列
        #   P12v6回测固化（2026-08-18）: 回撤率从50/40/30%收紧至45/35/25%
        #     IS年化+0.36pp/Sharpe+0.21/P12PnL+19%/OOS零恶化
        #     门槛维持15%不变（8%/5%门槛IS无效OOS有害）
        self.p12_tiers = [(0.15, 0.45), (0.30, 0.35), (0.50, 0.25)]

    # ---------- 基础 ----------
    def equity(self, prices: dict[str, float]) -> float:
        v = self.cash
        for c, p in self.holdings.items():
            v += p.shares * prices[c]
        return v

    def update_after_close(self, prices: dict[str, float], day_ret: float, vol20: float):
        self.equity_hist.append(self.equity(prices))
        self.date_hist.append(self.date_hist[-1] if self.date_hist else "")
        if self.equity_hist[-1] > self.peak:
            self.peak = self.equity_hist[-1]
        # P1-02 防御性钳制：回撤=(峰值-当前)/峰值，理论上限100%；
        # 钳制[0,1]杜绝任何数值/单位错误导致的>100%异常(如复核报告中的113.97%读数)
        self.drawdown = min(max((self.peak - self.equity_hist[-1]) / max(self.peak, 1e-9), 0.0), 1.0)
        self.day_ret = day_ret
        self.vol20_hist.append(vol20)

    # ---------- 交易执行 ----------
    def buy(self, date: str, code: str, name: str, ptype: str, industry: str | None,
            price: float, target_pct: float, equity_now: float, idx: int,
            obs_probe: bool = False, s3_pos: bool = False,
            reason: str = "正常建仓") -> bool:
        """按目标仓位%买入（T日开盘价），返回是否成交"""
        amount = equity_now * target_pct / 100.0
        if amount < 1000:
            return False
        # P1-03 规模冲击成本：有效买入成本 = 基础佣金 + 冲击系数×√(AUM/100万)
        # 大资金在同一流动性池交易，冲击成本随规模平方根递增(市场冲击 sqrt 法则)
        eff_buy = self.cost_buy + self.slip_impact * (self.capital_scale ** 0.5)
        shares = amount * (1 - eff_buy) / price
        if code in self.holdings:
            p = self.holdings[code]
            old_cost = p.cost * p.shares
            p.cost = (old_cost + price * shares) / (p.shares + shares)
            p.shares += shares
            p.lots.append((date, shares, price, idx))
            if p.ptype == "stock":
                p.obs_probe = p.obs_probe or obs_probe
                p.s3_pos = p.s3_pos or s3_pos
        else:
            p = Position(code, name, ptype, industry, shares=shares, cost=price,
                         lots=[(date, shares, price, idx)], entry_idx=idx,
                         max_high=price, obs_probe=obs_probe, s3_pos=s3_pos)
            self.holdings[code] = p
        self.cash -= amount
        self.trades.append(Trade(date, code, name, "buy", reason, price, shares, amount))
        return True

    def sell(self, date: str, code: str, reason: str, ratio: float = 1.0,
             price: float = 0.0, forced: bool = False) -> float:
        """卖出持仓比例(0-1)，返回卖出金额（含成本扣除后）。forced=True 不受20%上限约束（P0/E-P0.0等）"""
        p = self.holdings.get(code)
        if not p or p.shares <= 0:
            return 0.0
        sell_shares = p.shares * ratio
        if sell_shares <= 0:
            return 0.0
        # P1-03 规模冲击成本：有效卖出成本 = 基础佣金 + 冲击系数×√(AUM/100万)
        eff_sell = self.cost_sell + self.slip_impact * (self.capital_scale ** 0.5)
        proceeds = sell_shares * price * (1 - eff_sell)
        pnl = (price - p.cost) * sell_shares - sell_shares * price * eff_sell - sell_shares * p.cost * 0  # 含买卖成本近似
        p.shares -= sell_shares
        self.cash += proceeds
        self.trades.append(Trade(date, code, p.name, "sell", reason, price, sell_shares, proceeds, pnl))
        if p.shares < 1e-6:
            # 完整周期结算
            if p.ptype in ("stock", "etf_wide", "etf_ind"):
                self.closed_periods.append({
                    "code": code, "name": p.name, "exit": date,
                    "entry_idx": p.entry_idx, "pnl": pnl,
                    "cost_basis": (p.cost * (p.shares + sell_shares)) if p.shares > 0 else pnl,
                    "pnl_pct": (price - p.cost) / p.cost,
                    "hold_days": p.time_cnt,       # R-06 噪音止损率指标（≤11日E-P1占比）
                    "exit_reason": reason,          # 离场原因（E-P1/P1 过滤用）
                    "obs_probe": p.obs_probe, "s3_pos": p.s3_pos,
                    "tre_at_exit": reason,
                })
            del self.holdings[code]
        return proceeds

    # ---------- 资金管理 ----------
    def tre_cap(self, tre_state: str, cross_assets_break: int) -> float:
        cap = {"S1": 80.0, "S2": 60.0, "S3": 40.0, "S4": 20.0}[tre_state]
        cap -= 10 if cross_assets_break >= 2 else 0
        cap -= 20 if cross_assets_break >= 3 else 0
        return max(0.0, cap)

    def vol_cap(self, vol20: float) -> float:
        return min(80.0, 80.0 * 15.0 / max(vol20, 1.0)) if vol20 > 0 else 80.0

    def dd_cap(self) -> tuple[float, str]:
        dd = self.drawdown * 100
        if dd < 5: return 1.0, f"回撤{dd:.1f}%<5%"
        if dd < 8: return 0.75, f"回撤{dd:.1f}%∈[5,8)"
        if dd < 10: return 0.5, f"回撤{dd:.1f}%∈[8,10)"
        if dd < 12: return 0.25, f"回撤{dd:.1f}%∈[10,12)"
        return 0.10, f"回撤{dd:.1f}%≥12%(防御观察)"

    def kelly(self) -> float:
        """f* = (b*p - q)/b, 贝叶斯收缩, 封顶0.25; 样本<30强制收缩"""
        periods = [x for x in self.closed_periods if x["pnl_pct"] is not None]
        n = len(periods)
        if n == 0:
            return 0.25  # 无样本: 保守上限
        wins = [x for x in periods if x["pnl_pct"] > 0]
        p_raw = len(wins) / n
        avg_win = np.mean([x["pnl_pct"] for x in wins]) if wins else 0.0
        losses = [x for x in periods if x["pnl_pct"] <= 0]
        avg_loss = abs(np.mean([x["pnl_pct"] for x in losses])) if losses else 0.0
        b_raw = avg_win / avg_loss if avg_loss > 0 else 1.0
        # 贝叶斯收缩（先验 p0=0.45, b0=1.8, λ=12）
        lam = 12.0
        p = (n * p_raw + lam * 0.45) / (n + lam)
        b = (n * b_raw + lam * 1.8) / (n + lam)
        q = 1 - p
        f = (b * p - q) / b if b > 0 else 0.0
        # P0-F 下限保护: 连续亏损→f*≤0→cap=0→无法建仓→永远无法产生盈利周期修复凯利→永久死锁
        #   （2019-04 两笔E-P1止损后 cap=0 长达7个月实证）。降档机制已承担亏损惩罚, 凯利不再双重归零。
        f = max(f, self.kelly_min)
        return float(min(self.kelly_cap, f))

    def degrade_level(self, day_ret_t1: float, vol20: float) -> tuple[float, str]:
        """降档: 连续3个完整周期亏损 / 单日浮亏≥-5% / 波动率较前20日升>30%"""
        triggers = 0
        reasons = []
        recent = self.closed_periods[-3:] if self.closed_periods else []
        if len(recent) == 3 and all(x["pnl_pct"] is not None and x["pnl_pct"] < 0 for x in recent):
            triggers += 1; reasons.append("连续3周期亏损")
        if day_ret_t1 <= -0.05:
            triggers += 1; reasons.append(f"单日浮亏{day_ret_t1*100:.1f}%≤-5%")
        if self.prev_vol20 > 0 and vol20 > self.prev_vol20 * 1.3:
            triggers += 1; reasons.append(f"波动率{vol20:.1f}%较前{self.prev_vol20:.1f}%升>30%")
        if triggers >= 2:
            return 0.25, "停机档(" + "+".join(reasons) + ")"
        if triggers == 1:
            return 0.5, "降档(" + reasons[0] + ")"
        return 1.0, "正常档"

    def cap_limit(self, tre_state: str, cross_assets_break: int, vol20: float,
                  day_ret_t1: float) -> tuple[float, str]:
        """三层封顶总仓位上限 = MIN(TRE, 波动率目标, 回撤, 凯利) × 降档系数"""
        t = self.tre_cap(tre_state, cross_assets_break)
        v = self.vol_cap(vol20)
        d, d_reason = self.dd_cap()
        k = self.kelly() * 100.0
        deg, deg_reason = self.degrade_level(day_ret_t1, vol20)
        cap = min(t, v, d * 100.0, k) * deg
        return cap, f"TRE{t:.0f}%/VOL{v:.0f}%/DD{d:.2f}×100%/Kelly{k:.0f}%×降档{deg}"

    # ---------- 离场检查（T-1 数据） ----------
    def check_exits(self, row: dict, tre_state: str, obs_active: bool,
                    hs300_below3: bool, beta: float, month_ret: float) -> list[tuple[str, str, float]]:
        """返回 [(code, reason, ratio)]，按 F-11/11.6 优先级排序
        row: {code: {指标..., price: T-1收盘, open: T日开盘, pct_chg: T-1涨跌幅}}
        """
        orders = []
        codes = list(self.holdings.keys())
        for code in codes:
            p = self.holdings[code]
            r = row.get(code)
            if not r:
                continue
            t1_close = r["close"]
            open_t = r.get("open", t1_close)
            atr20p = r.get("ATR20P", 2.0)
            atr_abs = atr20p / 100.0 * t1_close
            loss_pct = (t1_close - p.cost) / p.cost * 100   # 相对成本浮盈亏
            # ---- 个股 P0 / ETF E-P0.0（无条件，forced） ----
            if p.ptype == "stock":
                fin = r.get("fin")
                if fin and (fin.get("np_yoy") is not None and fin["np_yoy"] < -12) \
                   or (fin and fin.get("rev_yoy") is not None and fin["rev_yoy"] < -15):
                    orders.append((code, "P0-财报硬过滤击穿", 1.0))
                    continue
            # ---- P1 / E-P1 技术止损（R-06 时间分档: ≤11日5% / >11日3%） ----
            if self.tenor_on:
                band = self.ep1_band_short if p.time_cnt <= 11 else self.ep1_band_long
            else:
                band = self.ep1_pct
            p1 = p.cost - min(2 * atr_abs, band / 100.0 * p.cost)
            # H2: S1 常规建仓强制最短持有期——期间跳过 P1/E-P1 噪音止损
            #   （打破 E-P1 快速打穿循环; E-P9时间止损/P4回撤/P12移动止损/熔断仍生效兜底）
            skip_ep1 = self.h2_minhold_on and p.s1_min_hold and p.time_cnt <= self.h2_minhold_days
            # P0-1b: 禁用 ETF E-P1 止损（仅 ETF 跳过, 个股 P1 仍生效）
            skip_ep1_etf = self.ep1_ETF_off and p.ptype != "stock"
            if not skip_ep1 and not skip_ep1_etf:
                if p.ptype == "stock" and t1_close <= p1:
                    orders.append((code, "P1-技术止损", 1.0))
                    continue
                ep1 = p.cost * (1 - band / 100.0)
                if p.ptype != "stock" and t1_close <= ep1:
                    orders.append((code, "E-P1-技术止损", 1.0))
                    continue
            # ---- 动态回撤（P4 / E-P0/E-P0.5） ----
            dd_thr_clear = -12 if tre_state in ("S1", "S2") else -11
            if p.ptype == "stock":
                if loss_pct <= dd_thr_clear:
                    orders.append((code, f"P4-动态回撤{dd_thr_clear}%", 1.0)); continue
                if loss_pct <= -8:
                    orders.append((code, "P4-动态回撤-8%减半", 0.5)); continue
                if r.get("pct_chg", 0) <= -9:
                    orders.append((code, "P5-单日跌>9%减半", 0.5)); continue
            else:
                ep05 = -11 if tre_state in ("S3", "S4") else -12
                if loss_pct <= ep05:
                    orders.append((code, f"E-P0.5-回撤{ep05}%", 1.0)); continue
                if loss_pct <= -8:
                    orders.append((code, "E-P0-回撤-8%减半", 0.5)); continue
            # ---- P6 MA60破位（仅S1/S2） ----
            if p.ptype == "stock" and tre_state in ("S1", "S2"):
                if r.get("ma120_break", False):
                    orders.append((code, "P6-MA120破位清仓", 1.0)); continue
                if r.get("ma60_break", False):
                    orders.append((code, "P6-MA60破位减半", 0.5)); continue
            # ---- E-P3 MA60走平破位连2日（ETF） ----
            if p.ptype != "stock" and r.get("ma60_flat_break2", False):
                orders.append((code, "E-P3-MA60走平破位", 1.0)); continue
            # ---- E-P4 13因子<60（ETF过程监控） ----
            if p.ptype != "stock" and r.get("score", 100) < 60:
                if p.ep4_flag:
                    p.ep4_counter += 1
                    if p.ep4_counter >= 10:
                        orders.append((code, "E-P4-因子退化T+10未修复", 1.0)); continue
                else:
                    p.ep4_flag = True; p.ep4_counter = 0
                    orders.append((code, "E-P4-因子退化减仓30%", 0.3)); continue
            # ---- P12 / E-P12 移动止盈（可配置 tiers） ----
            max_fp = (p.max_high - p.cost) / p.cost
            if self.p12_tiers and max_fp >= self.p12_tiers[0][0]:
                retr = self.p12_tiers[-1][1]  # default: 最高档
                for i in range(len(self.p12_tiers) - 1):
                    if max_fp < self.p12_tiers[i + 1][0]:
                        retr = self.p12_tiers[i][1]
                        break
                p12 = p.cost * (1 + max_fp * (1 - retr))
                if t1_close <= p12:
                    orders.append((code, f"P12/E-P12-移动止盈(浮盈{max_fp*100:.0f}%回撤{retr*100:.0f}%)", 1.0)); continue
            # ---- 时间止损 11.5 / E-P9（到期评估） ----
            time_thr = 60 if tre_state == "S1" else 30
            if p.time_cnt >= time_thr:
                score = r.get("score", 100)
                if p.ptype == "stock" and score < 70:
                    orders.append((code, f"11.5-时间止损到期(得分{score:.0f}<70)", 1.0)); continue
                if p.ptype != "stock" and score < 65:
                    orders.append((code, f"E-P9-时间止损到期(得分{score:.0f}<65)", 1.0)); continue
                # 评估通过 → 重置
                p.time_cnt = 0
                p.eval_reset["ext"] = 15 if tre_state != "S1" else 30
            # ---- 11.5a / E-P9.5 建仓条件时效（每日盘后监控，30日存续上限） ----
            if (p.obs_probe or p.s3_pos) and not p.qual_expired:
                score = r.get("score", 100)
                if score < self.qual_gate:
                    orders.append((code, f"{'E-P9.5' if p.ptype!='stock' else '11.5a'}-建仓资格失守(得分{score:.0f}<{self.qual_gate:.0f})", 1.0)); continue
        # ---- 组合类（账户级） ----
        if hs300_below3:
            orders.append(("__P9__", "P9/E-P10-大盘连3日破MA60(总仓≤20%)", 1.0))
        if beta > 1.5:
            orders.append(("__P10__", "P10/E-P11-组合Beta>1.5(总仓≤60%)", 1.0))
        if month_ret <= -0.12:
            orders.append(("__P8__", "P8-账户月度浮亏12%(总仓≤40%)", 1.0))
        # ---- 排序（F-11 跨品种优先级） ----
        pri = {"P0": 0, "E-P0.0": 1, "P2": 2, "P3": 3, "E-P0": 4, "E-P0.5": 5,
               "P4": 6, "P5": 7, "P6": 8, "P7": 9, "E-P1": 10, "E-P2": 11,
               "E-P3": 12, "E-P4": 13, "E-P5": 14, "E-P6": 15, "E-P7": 16,
               "E-P8": 17, "E-P9": 18, "E-P10": 19, "P8": 20, "P9": 21, "P10": 22, "E-P11": 23,
               "P11": 24, "P12": 25, "E-P12": 26, "11.5a": 27, "E-P9.5": 28, "11.5": 29, "E-P9": 30}
        def _pri(t):
            for k, v in pri.items():
                if t.startswith(k):
                    return v
            return 99
        orders.sort(key=lambda x: _pri(x[1]))
        return orders

    def meltdown_level(self, hs300_pct: float) -> int:
        """盘中熔断级别（日线代理: 用T-1日沪深300涨跌幅判定T日限制）
        跌幅≥2%→Ⅰ级 / ≥3.5%→Ⅱ级 / ≥5%→Ⅲ级
        """
        if hs300_pct <= -5.0: return 3
        if hs300_pct <= -3.5: return 2
        if hs300_pct <= -2.0: return 1
        return 0
