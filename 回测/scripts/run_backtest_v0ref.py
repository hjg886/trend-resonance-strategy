# -*- coding: utf-8 -*-
"""
中线趋势共振策略 v4.7-R8 —— 六年回测主程序
区间: 样本内 2019-01-02~2024-12-31(6年) / 样本外 2025-01-02~2026-06-30
基准: 沪深300 | 初始资金: 100万 | 成本: 买0.1% 卖0.2%
铁律: T-1判定/T日开盘执行 | PIT财报(NOTICE_DATE对齐) | 历史时点存在性检查 | 跨资产有效性检验
"""
import os, json, math, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from indicators import indicator_panel, ma, ma60_effective_break
from tre import TreState, step_tre
from scoring import (build_financial_series, fin_at, stock_score, etf_score,
                     layer1_stock, layer1_etf, six_lights, seven_lights, min_nine, f04)
from engine import Portfolio

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "output")
os.makedirs(OUT, exist_ok=True)

# ---------------- 标的配置 ----------------
# code -> (data_name, name, ptype, industry)   ptype: stock / etf_wide / etf_ind
# R-09 标的面扩展（v4.7-R10）: 总候选池 12→30 只（个股 2→8 / ETF 10→22），解决六年"标的面不足→建仓枯竭"
# 开关必须在本节前定义（UNIVERSE 组装依赖）
R9_UNIV_ON = os.environ.get("BT_R9UNIV", "1") == "1"
UNIVERSE = {
    "600276": ("stk_600276", "恒瑞医药", "stock", "医药生物"),
    "603259": ("stk_603259", "药明康德", "stock", "医药生物"),
    "510300": ("etf_510300", "沪深300ETF", "etf_wide", None),
    "159915": ("etf_159915", "创业板ETF", "etf_wide", None),
    "588000": ("etf_588000", "科创50ETF", "etf_wide", None),
    "512010": ("etf_512010", "医药ETF", "etf_ind", "医药生物"),
    "159928": ("etf_159928", "消费ETF", "etf_ind", "食品饮料"),
    # P0 观察池扩展（2026-08-17）: 新增5只主流行业ETF, 提高建仓机会面
    "512880": ("etf_512880", "证券ETF", "etf_ind", "非银金融"),
    "512690": ("etf_512690", "酒ETF", "etf_ind", "食品饮料"),
    "515030": ("etf_515030", "新能源车ETF", "etf_ind", "电力设备"),
    "512480": ("etf_512480", "半导体ETF", "etf_ind", "电子"),
    "512170": ("etf_512170", "医疗ETF", "etf_ind", "医药生物"),
}
# R-09 扩展池（2026-08-18, 重构 R-09 落地）: +18 只（宽基4 + 行业8 + 个股6）→ 总候选 30
UNIVERSE_R9 = {
    # --- 宽基/风格 ETF 4只 ---
    "510050": ("etf_510050", "上证50ETF", "etf_wide", None),
    "510500": ("etf_510500", "中证500ETF", "etf_wide", None),
    "510880": ("etf_510880", "红利ETF", "etf_wide", None),
    "159920": ("etf_159920", "恒生ETF", "etf_wide", None),
    # --- 行业 ETF 8只 ---
    "512400": ("etf_512400", "有色金属ETF", "etf_ind", "有色金属"),
    "512660": ("etf_512660", "军工ETF", "etf_ind", "国防军工"),
    "515790": ("etf_515790", "光伏ETF", "etf_ind", "电力设备"),
    "159995": ("etf_159995", "芯片ETF", "etf_ind", "电子"),
    "515000": ("etf_515000", "科技ETF", "etf_ind", "电子"),
    "512980": ("etf_512980", "传媒ETF", "etf_ind", "传媒"),
    "515050": ("etf_515050", "5G通信ETF", "etf_ind", "通信"),
    "516160": ("etf_516160", "新能源ETF", "etf_ind", "电力设备"),
    # --- 个股 6只（财报PIT缺失[代理: 未公告期中性分], 观察通道85分门槛自动拦截） ---
    "600519": ("stk_600519", "贵州茅台", "stock", "食品饮料"),
    "600036": ("stk_600036", "招商银行", "stock", "银行"),
    "601318": ("stk_601318", "中国平安", "stock", "非银金融"),
    "000858": ("stk_000858", "五粮液", "stock", "食品饮料"),
    "300750": ("stk_300750", "宁德时代", "stock", "电力设备"),
    "000333": ("stk_000333", "美的集团", "stock", "家用电器"),
}
if R9_UNIV_ON:
    UNIVERSE.update(UNIVERSE_R9)
# 进攻线专用: 自定义标的池（逗号分隔代码列表, 设置后替换UNIVERSE为指定子集）
_ATTACK_UNIVERSE = os.environ.get("BT_ATTACK_UNIVERSE", "")
if _ATTACK_UNIVERSE:
    _attack_codes = [c.strip() for c in _ATTACK_UNIVERSE.split(",") if c.strip()]
    UNIVERSE = {c: v for c, v in UNIVERSE.items() if c in _attack_codes}
    # 为不在当前UNIVERSE但存在数据文件的标的追加配置
    _ATTACK_EXTRA = {
        "300357": ("stk_300357", "我武生物", "stock", "医药生物"),
        "605117": ("stk_605117", "德业股份", "stock", "电力设备"),
        "688120": ("stk_688120", "华海清科", "stock", "电子"),
        "002371": ("stk_002371", "北方华创", "stock", "电子"),
        "600196": ("stk_600196", "复星医药", "stock", "医药生物"),
        "002156": ("stk_002156", "通富微电", "stock", "电子"),
        "688082": ("stk_688082", "盛美上海", "stock", "电子"),
        "300661": ("stk_300661", "圣邦股份", "stock", "电子"),
        "300693": ("stk_300693", "盛弘股份", "stock", "电力设备"),
        "600584": ("stk_600584", "长电科技", "stock", "电子"),
        "688239": ("stk_688239", "航宇科技", "stock", "国防军工"),
        "603986": ("stk_603986", "兆易创新", "stock", "电子"),
        "688008": ("stk_688008", "澜起科技", "stock", "电子"),
        "603005": ("stk_603005", "晶方科技", "stock", "电子"),
        "002335": ("stk_002335", "科华数据", "stock", "通信"),
        "002472": ("stk_002472", "双环传动", "stock", "汽车"),
        "002050": ("stk_002050", "三花智控", "stock", "汽车"),
        "002111": ("stk_002111", "威海广泰", "stock", "国防军工"),
        "000099": ("stk_000099", "中信海直", "stock", "国防军工"),
        "002518": ("stk_002518", "科士达", "stock", "电力设备"),
        "688686": ("stk_688686", "奥普特", "stock", "机械设备"),
    }
    for c in _attack_codes:
        if c not in UNIVERSE and c in _ATTACK_EXTRA:
            UNIVERSE[c] = _ATTACK_EXTRA[c]
CASH_ETF = "etf_159650"          # 现金管理（国开债ETF，2022-10-28上市）
CROSS_ASSETS = ["x_hstech", "x_nasdaq100", "x_gold"]   # 美债US10Y [MISSING]
CORE_IDX = ["idx_hs300", "idx_sh", "idx_sz"]

PERIOD_IN = ("2019-01-02", "2024-12-31")
PERIOD_OOS = ("2025-01-02", "2026-06-30")

# 建仓得分门槛（默认对齐文档: 常规80 / S3有限建仓与观察通道85）——可参数化做敏感性对照[B4]
# P0-A 重设计: 基于6年得分分布（>=80仅1.46%, p75≈65.5）重标定
#   SCORE_GATE=70 常规(S1);  S2_GATE=75 S2减半(更严, 因S2建仓6年胜率差);
#   OBS_GATE=72 观察通道试探仓(>常规70保持相对更严, 资格维持仍85)
SCORE_GATE = float(os.environ.get("BT_SCORE_GATE", "70.0"))
S2_GATE = float(os.environ.get("BT_S2_GATE", "75.0"))
OBS_GATE = float(os.environ.get("BT_OBS_GATE", "72.0"))
# 进攻线专用: 统一得分门槛（>0时覆盖所有状态门槛为该值, 用于候选B严格筛选）
ATTACK_SCORE = float(os.environ.get("BT_ATTACK_SCORE", "0.0"))
# P0-B 重设计: 转换表变体 V0=现行 / V1=+S2→S4当日生效
TRE_VARIANT = os.environ.get("BT_TRE_VARIANT", "V1")
# v4.7-R9 第三轮修复开关（默认全开; 用于C/D系列变体隔离效果）
#   P0-D: 第5灯事件计数修复 —— ma60_break 旧口径(>=3天数计数) vs 事件计数(==3首次日)
#   R1: 七灯第5灯分层(宽基≤1/行业≤3/观察通道豁免)
#   R2: 行业ETF得分门槛分轨(S1=65/S2=72/观察=68)
#   R3: MIN运算行业ETF z-score化(②H60与⑥DEV60)
FIXL5_ON = os.environ.get("BT_FIXL5", "1") == "1"
R1_ON = os.environ.get("BT_R1", "1") == "1"
R2_ON = os.environ.get("BT_R2", "1") == "1"
R3_ON = os.environ.get("BT_R3", "1") == "1"
# R2 行业ETF分轨门槛
ETFI_GATE_S1 = 65.0
ETFI_GATE_S2 = 72.0
ETFI_GATE_OBS = 68.0
# v4.7-R9 第四轮修复开关（默认全开; B系列全0回归对照, D系列逐步叠加）
#   P0-E: 观察通道升级退出当日豁免名义状态转换（防 S2→S4(V1) 吞没升级）
#   P0-F: 凯利下限保护10%（防连续亏损→f*=0→cap=0→半年+无法建仓死锁）
#   P0-G: E-P1/P1 技术止损后30日洗仓封堵（需得分≥85方可重购, 与资格类清仓一致）
OBSGUARD_ON = os.environ.get("BT_OBSGUARD", "1") == "1"
KELLY_MIN_ON = os.environ.get("BT_KELLYMIN", "1") == "1"
EP1BLOCK_ON = os.environ.get("BT_EP1BLOCK", "1") == "1"
# 第五轮敏感性参数（默认对齐策略文档: E-P1带宽3% / 资格维持85）
EP1_PCT = float(os.environ.get("BT_EP1PCT", "3.0"))
QUAL_GATE = float(os.environ.get("BT_QUALGATE", "85.0"))
# 第六轮归因驱动修复（基于 D6r 交易特征归因分析）
#   E1: vol20≥15 硬过滤 —— 归因显示 vol20<15 期望-2.51%、S1+低波动为死亡陷阱(-4.68%)
#   E2: S1 建仓降档 50% —— 归因显示 S1 期望-2.94%是亏损核心，但降权比排除更符合策略哲学
VOLFILTER_ON = os.environ.get("BT_VOLFILTER", "0") == "1"
VOL_MIN = float(os.environ.get("BT_VOL_MIN", "15.0"))
S1DERATE_ON = os.environ.get("BT_S1DERATE", "0") == "1"
# ============ v4.7-R10 重构开关（R-04/R-05/R-06/R-10, 默认全关=回归对照） ============
# R-04 波动率环境双闸门: vol20<15 禁一切建仓(闸门A) / ≥20 禁S1/S2常规(闸门B, 仅S3有限+观察通道) / 15-20正常
VOLGATE_ON = os.environ.get("BT_VOLGATE", "0") == "1"
# 进攻线专用: 闸门阈值可配置（默认对齐R-04标准, 候选B可放宽）
VOL_GATE_A_THRESH = float(os.environ.get("BT_VOL_GATE_A_THRESH", "15.0"))
VOL_GATE_B_THRESH = float(os.environ.get("BT_VOL_GATE_B_THRESH", "20.0"))
# R-05 S1突破确认制: 连续2日S1完整条件 + 标的连续2日站稳MA60 + 开盘涨幅≤1%
S1CONFIRM_ON = os.environ.get("BT_S1CONFIRM", "0") == "1"
# R-06 止损带宽时间分档: 持有≤11日5% / >11日3%（engine.py tenor_on）
EP1TENOR_ON = os.environ.get("BT_EP1TENOR", "0") == "1"
# R-10 得分门槛分轨: 个股/宽基常规80 / 行业ETF 78 / S3与观察通道85
#   （覆盖 P0-A 重标定 70/75/72 与 R2 行业分轨 65/72/68 —— 重构后标的面扩大, 无需靠降门槛凑建仓）
R10_GATES_ON = os.environ.get("BT_R10GATES", "0") == "1"
# ============ 阶段1 A/B: 建仓时机门控（2026-08-18 路径A裁决对比, 两开关互斥） ============
# 对照组 BIN: BT_MA60GATE=1 → "沪深300站稳MA60才可建仓"忠实实现（收盘≤MA60 禁一切建仓）
# 实验组 TIER: BT_TIERGATE=1 → 三级分级门控（路径A）
#   FULL: close>MA60 且 MA20>MA60  均线多头 → 常规全开（同对照组FULL）
#   HALF: close>MA20 且 非FULL     弱反弹窗 → 禁S1/S2常规, 仅S3有限建仓+观察通道, target×0.5
#   NONE: close≤MA20               空仓窗 → 禁一切建仓
MA60GATE_ON = os.environ.get("BT_MA60GATE", "0") == "1"
TIERGATE_ON = os.environ.get("BT_TIERGATE", "0") == "1"
# ============ H系列: S1假信号定向修复（2026-08-18 阶段1归因, 三变体可组合, 默认全关=G1r回归） ============
# H1: S1 常规建仓禁 ETF（归因⑥: ETF亏/个股盈; S1追涨ETF被均值回归打穿; 个股S1不受影响）
H1_S1NOETF_ON = os.environ.get("BT_H1_S1NOETF", "0") == "1"
# H2: S1 常规建仓强制最短持有期 N 日（期间跳过 P1/E-P1 噪音止损, E-P9时间止损/回撤P4/P12/熔断仍生效;
#     打破 E-P1 快速打穿循环, 给 P12 移动止盈引擎激活时间; 归因: ≤5日-2.83% vs >30日+5.90%）
H2_MINHOLD_ON = os.environ.get("BT_H2_MINHOLD", "0") == "1"
H2_MINHOLD_DAYS = int(os.environ.get("BT_H2_MINHOLD_DAYS", "11"))
# R-09 标的面扩展开关: 1=30只扩展池(v4.7-R10标准) / 0=原12只对照
# （实际定义见标的配置节, 此处仅保留开关读取, 供 run_r10 等模块引用一致性）
# ============ F-04 仓位引擎专项验证（2026-08-18, 默认全关=G1r回归） ============
# 命题: 交易净PnL 仅 +9,679元/6年, 总收益96%来自现金——"单笔金额贡献"能否通过仓位放大撑起年化6%缺口?
# F04_MULT: 最终target倍率（≥1时在全部建仓约束判定后放大执行金额; 上限12/15同比例放大,
#           但 凯利总仓位cap/行业30%/组合约束 仍按原始target判定=纯粹的金额贡献实验）
# KELLY_CAP: 凯利封顶（总仓位上限 cap 的乘数之一, 0.25→0.40 验证高信号期多单叠加空间）
F04_MULT = float(os.environ.get("BT_F04_MULT", "1.0"))
KELLY_CAP = float(os.environ.get("BT_KELLY_CAP", "0.25"))
# ============ P0 修正系列（2026-08-18, 默认全关=G1r回归） ============
# P0-1a: E-P1 止损带宽自定义（覆盖 R-06 默认 5%/3%）
EP1_BAND_SHORT = float(os.environ.get("BT_EP1_BAND_SHORT", "5.0"))
EP1_BAND_LONG = float(os.environ.get("BT_EP1_BAND_LONG", "3.0"))
# P0-1b: 禁用 ETF 的 E-P1 止损（仅靠 P4/E-P0.5/P12/E-P9 兜底）
EP1_ETF_OFF = os.environ.get("BT_EP1_ETF_OFF", "0") == "1"
# P0-3: BREADTH 否决层（MHD 宽度<阈值时拒绝建仓, 附加否决非许可）
BREADTH_VETO_ON = os.environ.get("BT_BREADTH_VETO", "0") == "1"
BREADTH_MIN = float(os.environ.get("BT_BREADTH_MIN", "15.0"))
# MHD 评分数据路径
MHD_CSV = os.path.join(OUT, "mhd_scores.csv")
# ============ P12 移动止盈引擎（P12v6固化, 2026-08-18） ============
# BT_P12_TIERS: JSON字符串 [[min_fp, retr], ...] 升序
# P12v6回测验证固化: 回撤率45/35/25%（从50/40/30%收紧, IS年化+0.36pp/Sharpe+0.21/OOS零恶化）
P12_TIERS = os.environ.get("BT_P12_TIERS", "")


# ---------------- 数据加载 ----------------
def load_csv(name):
    df = pd.read_csv(os.path.join(DATA, f"{name}.csv"), dtype={"date": str})
    df["date"] = df["date"].astype(str).str[:10]
    return df.set_index("date").sort_index()


def load_all():
    panels = {}
    for nm in ["idx_hs300", "idx_sh", "idx_sz"] + [v[0] for v in UNIVERSE.values()] + \
              [CASH_ETF] + CROSS_ASSETS:
        try:
            panels[nm] = load_csv(nm)
        except FileNotFoundError:
            print(f"[MISSING] {nm}"); continue
    with open(os.path.join(DATA, "financials.json"), encoding="utf-8") as fh:
        fins_json = json.load(fh)
    fins = {c: build_financial_series(fins_json, c) for c in ("600276", "603259")}
    return panels, fins


# ---------------- 指标与辅助列 ----------------
def build_panels(panels: dict) -> dict:
    """计算全部指标面板（含离场辅助列、PIT PB序列）"""
    out = {}
    # 跨资产（海外市场）交易日与A股不一致：先统一重索引到沪深300日历并前值填充
    if "idx_hs300" in panels:
        cal = panels["idx_hs300"].index
        for xa in CROSS_ASSETS:
            if xa in panels and not panels[xa].index.equals(cal):
                panels[xa] = panels[xa].reindex(cal).ffill()
    for nm, df in panels.items():
        p = indicator_panel(df)
        c = p["close"]
        p["ret20"] = c.pct_change(20) * 100
        p["ret60"] = c.pct_change(60) * 100
        p["low20"] = c.rolling(20).min()
        hi60 = c.rolling(60).max()
        p["R"] = ((c - p["low20"]) / (hi60 - c)).clip(upper=10)  # 创新高时→0（突破型买点）; 上限防除零
        p["near_ma60_5d"] = ((p["low"].rolling(5).min() >= p["MA60"] * 0.98) &
                             (p["low"].rolling(5).min() <= p["MA60"] * 1.02)).astype(int)
        p["amount20"] = p["amount"].rolling(20).mean()
        # 阶段1 A/B: MA20（分级门控窗口判定需要, 仅沪深300实际使用, 统一计算无副作用）
        p["MA20"] = p["close"].rolling(20).mean()
        # MA60/MA120 有效破位（连续3日收盘确认[代理]）
        below60 = (c < p["MA60"]).astype(int)
        p["below60_streak"] = below60.groupby((below60 != below60.shift()).cumsum()).cumsum()
        # P0-D 修复: 破位事件计数(首次达到连续3日当天=1) 替代 天数计数(持续期每天=1)
        #   旧口径(>=3)把"破位持续天数"当"破位次数", 90日窗口内恒偏高→第5灯结构性否决假象
        if FIXL5_ON:
            p["ma60_break"] = (p["below60_streak"] == 3).astype(int)
        else:
            p["ma60_break"] = (p["below60_streak"] >= 3).astype(int)
        below120 = (c < p["MA120"]).astype(int)
        p["below120_streak"] = below120.groupby((below120 != below120.shift()).cumsum()).cumsum()
        p["ma120_break"] = (p["below120_streak"] >= 3).astype(int)
        # MA60走平且破位连2日（E-P3）
        slope60 = p["MA60"].diff(5).abs()
        p["ma60_flat_break2"] = ((slope60 / p["MA60"] < 0.001) & (p["below60_streak"] >= 2)).astype(int)
        # 近90日破位次数
        p["ma60_break90"] = p["ma60_break"].rolling(90).sum()
        # R3: 行业ETF z-score化数据基础 —— DEV60/H60 滚动250日z-score（NaN保留供回退）
        dev60 = p["DEV60"]
        p["DEV60_Z"] = (dev60 - dev60.rolling(250).mean()) / dev60.rolling(250).std()
        h60s = p["H60"]
        p["H60_Z"] = (h60s - h60s.rolling(250).mean()) / h60s.rolling(250).std()
        # 个股 Beta（60日滚动 vs 沪深300）
        if nm.startswith(("stk_", "etf_")) and nm != CASH_ETF:
            hs = out.get("idx_hs300") if "idx_hs300" in out else None
            if hs is None:
                hs = indicator_panel(panels["idx_hs300"])
                out["idx_hs300"] = hs
            ret_a = c.pct_change()
            ret_h = hs["close"].pct_change()
            cov = ret_a.rolling(60).cov(ret_h)
            var = ret_h.rolling(60).var()
            p["BETA60"] = (cov / var) * 100.0  # 百分比化避免除零
        out[nm] = p
    return out


def add_pit_pb(panels: dict, fins: dict):
    """PIT PB/PE 序列: pb=close/bps, pe=close/eps(累计值年化代理[代理])；滚动分位用于评分"""
    for code, (dn, _, ptype, _) in UNIVERSE.items():
        if ptype != "stock":
            continue
        p = panels[dn]
        fin_df = fins.get(code)  # R-09: 扩展个股财报PIT缺失 → None（评分走"财报未公告"中性分）
        dates = p.index
        bps_list, eps_list = [], []
        for d in dates:
            f = fin_at(fin_df, d)
            bps_list.append(f["bps"] if f and f.get("bps") else np.nan)
            eps_list.append(f["eps"] if f and f.get("eps") else np.nan)
        bps_s = pd.Series(bps_list, index=dates)
        eps_s = pd.Series(eps_list, index=dates)
        p["PB"] = p["close"] / bps_s
        p["PE"] = p["close"] / eps_s
        p["PB_PCTL"] = p["PB"].rolling(120).apply(lambda x: (x[-1] > x).mean() * 100 if len(x) == 120 else 50, raw=True)
        p["PE_PCTL"] = p["PE"].rolling(120).apply(lambda x: (x[-1] > x).mean() * 100 if len(x) == 120 else 50, raw=True)
        p["PB_EXPAND"] = p["PB"] / p["PB"].rolling(250).median()
    return panels


# ---------------- 评分 ----------------
def compute_score(code: str, dn: str, ptype: str, row: dict, fins: dict, panels: dict) -> float:
    if ptype == "stock":
        fin_df = fins.get(code)  # R-09: 财报缺失 → fin_at(None)=None → layer1 代理通过/评分中性
        f = fin_at(fin_df, row.name)
        fin = dict(f) if f else None
        if fin is not None:
            fin["price"] = row["close"]
            if fin.get("eps") and np.isfinite(fin["eps"]) and fin["eps"] > 0:
                fin["pe"] = row["close"] / fin["eps"]
            if fin.get("bps") and np.isfinite(fin["bps"]) and fin["bps"] > 0:
                fin["pb"] = row["close"] / fin["bps"]
        hist_pb, hist_pe = [], []
        for col, hlist in (("PB", hist_pb), ("PE", hist_pe)):
            if col in panels[dn]:
                s = panels[dn][col].dropna()
                v = row.get(col)
                if np.isfinite(v):
                    hlist.extend(s[s.index < row.name].tail(120).tolist())
        return stock_score(row, fin, hist_pb, hist_pe)
    else:
        return etf_score(row, est_pct=0.6)


# ---------------- 主回测 ----------------
def run_backtest(panels: dict, fins: dict, days: list, period: tuple, label: str) -> dict:
    tre = TreState()
    pf = Portfolio()
    # P0-F 凯利下限保护（开关: BT_KELLY_MIN=1 → 下限10%）
    if KELLY_MIN_ON:
        pf.kelly_min = 0.10
    # F-04 专项: 凯利封顶放宽（默认0.25=G1r回归）
    pf.kelly_cap = KELLY_CAP
    pf.ep1_pct = EP1_PCT
    pf.qual_gate = QUAL_GATE
    # R-06 止损带宽时间分档（≤11日5% / >11日3%）—— P0-1a 可自定义带宽
    pf.tenor_on = EP1TENOR_ON
    pf.ep1_band_short = EP1_BAND_SHORT
    pf.ep1_band_long = EP1_BAND_LONG
    # H2: S1 强制最短持有期（engine.check_exits 跳过 P1/E-P1 用）
    pf.h2_minhold_on = H2_MINHOLD_ON
    pf.h2_minhold_days = H2_MINHOLD_DAYS
    # P0-1b: 禁用 ETF 的 E-P1 止损（engine 标志）
    pf.ep1_ETF_off = EP1_ETF_OFF
    # P12 移动止盈引擎 tiers（可配置, 用于扩大化回测）
    if P12_TIERS:
        import json as _json
        pf.p12_tiers = [tuple(t) for t in _json.loads(P12_TIERS)]
    # P0-3: BREADTH 否决层数据加载
    breadth_map = {}
    if BREADTH_VETO_ON:
        try:
            mhd_df = pd.read_csv(MHD_CSV, dtype={"date": str})
            mhd_df["date"] = mhd_df["date"].astype(str).str[:10]
            breadth_map = dict(zip(mhd_df["date"], mhd_df["BREADTH"]))
        except FileNotFoundError:
            print(f"[WARN] MHD scores not found at {MHD_CSV}, BREADTH veto disabled")
    # 现金ETF收益序列
    cash_df = panels.get(CASH_ETF)

    hist = []   # 逐日记录
    obs_snapshots = []
    buys = []
    tre_hist = []   # R-05 S1确认制: 名义状态连续2日S1核查
    gate_hist = []  # R-04 闸门触发记录
    win_hist = []   # 阶段1 A/B: 分级门控窗口 FULL/HALF/NONE 逐日记录
    stats = {"intercept": {k: 0 for k in
        ["持仓冲突", "洗仓封堵", "层级1", "RPS", "R值C级", "TRE不可建仓",
         "得分<SCORE_GATE", "得分<S2_GATE", "得分<OBS_GATE", "组合约束", "六/七灯",
         "MIN≤0", "ATR>8%", "流动性不足", "F04<3%", "风险预算", "总仓位上限", "行业>30%",
         "R04闸门", "S1确认制", "分级HALF禁S1/S2", "分级HALF<3%", "H1禁S1+ETF", "BREADTH否决"]}}

    period_start, period_end = period
    active = False

    for i, date in enumerate(days):
        if date >= period_start:
            active = True
        if date > period_end:
            break
        if not active:
            continue
        if i < 2:
            continue

        t1 = days[i - 1]
        # ---------- T-1 汇总 ----------
        h = panels["idx_hs300"].loc[t1]
        core_adx = [panels[x].loc[t1, "ADX14"] for x in CORE_IDX]
        cross20 = h["CROSS20"]
        # 市场20日年化波动率（沪深300）——P0-C 口径修复: TRE是市场状态识别, vol20与持仓无关
        # （原实现用持仓加权波动率, 空仓时≈0 → vol>25%风暴条件永不触发, S4被锁死）
        hs300_ret = panels["idx_hs300"]["close"].pct_change().loc[:t1]
        vol20 = float(hs300_ret.tail(20).std(ddof=1) * np.sqrt(252) * 100)
        # 组合持仓波动率（仅输出/风控用, 不影响TRE判定）
        pf_vol20 = float(np.std(pf.ret_hist_20, ddof=1) * np.sqrt(252) * 100) if pf.ret_hist_20 else vol20
        hs300_below_streak = float(h["BELOW_STREAK"])
        hs300_gt = bool(h["close"] > h["MA60"])
        step_tre(tre, i, core_adx, cross20, vol20, hs300_below_streak, hs300_gt,
                 variant=TRE_VARIANT, obs_guard=OBSGUARD_ON)
        tre_hist.append(tre.state)

        # ---------- R-04 波动率环境双闸门（v4.7-R10 重构，建仓第一前置条件） ----------
        gate = ""
        if VOLGATE_ON:
            if vol20 < VOL_GATE_A_THRESH:
                gate = f"A-vol20={vol20:.1f}<{VOL_GATE_A_THRESH:.0f}禁一切建仓"
            elif vol20 >= VOL_GATE_B_THRESH and tre.state in ("S1", "S2") and not tre.obs_active:
                gate = f"B-vol20={vol20:.1f}≥{VOL_GATE_B_THRESH:.0f}禁S1/S2常规"
        # 兼容 E1r 旧开关（对照实验）
        if not gate and VOLFILTER_ON and vol20 < VOL_MIN:
            gate = f"vol20={vol20:.1f}<{VOL_MIN:.0f}禁建仓"
        gate_hist.append(gate)

        # ---------- 阶段1 A/B: 建仓时机门控（MA60二元 vs 三级分级, 两开关互斥） ----------
        # 判定基于 T-1 沪深300收盘/MA20/MA60；FULL 常规全开 / HALF 仅S3+观察通道5折 / NONE 全禁
        win = ""
        if TIERGATE_ON or MA60GATE_ON:
            h_c = float(h["close"])
            h_m60 = float(h["MA60"])
            h_m20 = float(h["MA20"])
            if TIERGATE_ON:
                if h_c > h_m60 and h_m20 > h_m60:
                    win = "FULL"
                elif h_c > h_m20:
                    win = "HALF"
                else:
                    win = "NONE"
                if win == "NONE" and not gate:
                    gate = f"分级NONE-空仓窗(close≤MA20)禁建仓"
            elif MA60GATE_ON and not gate and h_c <= h_m60:
                gate = f"MA60二元-沪深300收盘≤MA60禁建仓"
        win_hist.append(win)

        # 跨资产破位数（MA60下）
        xbrk = 0
        for xa in CROSS_ASSETS:
            if xa in panels:
                xr = panels[xa].loc[t1]
                if xr["close"] < xr["MA60"]:
                    xbrk += 1

        # 熔断级别（T-1沪深300跌幅代理）
        melt = pf.meltdown_level(float(h["pct_chg"]))
        if melt >= 1:
            pf.meltdown_count[["I", "II", "III"][melt - 1]] += 1
            if melt >= 2:
                # 捕捉率代理: 次日沪深300是否续跌
                if i + 1 < len(days) and panels["idx_hs300"].loc[days[i + 1], "close"] < h["close"]:
                    pf.meltdown_captured += 1

        # 三层封顶
        cap, cap_reason = pf.cap_limit(tre.state, xbrk, vol20, pf.day_ret)

        # ---------- T-1 各标的 row + score ----------
        rows, scores = {}, {}
        for code, (dn, name, ptype, ind) in UNIVERSE.items():
            if t1 in panels[dn].index:
                row = panels[dn].loc[t1].copy()
                row["score"] = compute_score(code, dn, ptype, row, fins, panels)
                rows[code] = row
                scores[code] = row["score"]

        open_px = {}
        for code, (dn, *_ ) in UNIVERSE.items():
            if date in panels[dn].index:
                open_px[code] = panels[dn].loc[date, "open"]
            else:
                open_px[code] = rows.get(code, {}).get("close", 0)

        # 组合Beta（T-1权重 × 60日Beta）
        beta = 0.0
        eq_t1 = pf.equity({c: rows.get(c, {}).get("close", 0) for c in pf.holdings}) if pf.holdings else pf.cash
        for c, p in pf.holdings.items():
            dn = UNIVERSE[c][0]
            if c in rows and np.isfinite(rows[c].get("BETA60", np.nan)):
                w = p.shares * rows[c]["close"] / max(eq_t1, 1)
                beta += w * rows[c]["BETA60"] / 100.0

        # ---------- 资格监控失守（T-1盘后判定 → T日开盘清仓） ----------
        for c in list(pf.holdings.keys()):
            p = pf.holdings[c]
            if p.qual_break and open_px.get(c, 0) > 0:
                pf.sell(date, c, p.qual_break_reason, 1.0, price=open_px[c])
                # 洗仓封堵: 30日内重购须85分（记录到 code_qual 表）
                pf.qual_block[c] = {"until": i + 30, "threshold": 85}

        # ---------- 离场检查与执行 ----------
        # 大盘连3日破MA60 (P9/E-P10)
        hs300_below3 = hs300_below_streak >= 3
        month_ret = (pf.equity({c: rows.get(c, {}).get("close", 0) for c in pf.holdings}) - pf.month_start_equity) / pf.month_start_equity if pf.month_start_equity > 0 else 0
        exit_rows = {c: {**rows.get(c, {}), "score": scores.get(c, 100)} for c in pf.holdings}
        orders = pf.check_exits(exit_rows, tre.state, tre.obs_active, hs300_below3, beta, month_ret)

        # 账户级压缩标志
        comp_p9 = comp_p10 = comp_p8 = False
        exec_amt = 0.0
        def _ep1_block(code, reason):
            # P0-G: E-P1/P1 技术止损清仓后 30 日洗仓封堵（重购须得分≥85, 与资格类清仓一致）
            if EP1BLOCK_ON and (reason.startswith("P1-") or reason.startswith("E-P1-")) \
               and code not in pf.holdings:
                pf.qual_block[code] = {"until": i + 30, "threshold": 85}
        for code, reason, ratio in orders:
            if code.startswith("__"):
                if "P9" in reason: comp_p9 = True
                if "P10" in reason: comp_p10 = True
                if "P8" in reason: comp_p8 = True
                continue
            p = pf.holdings.get(code)
            if not p:
                continue
            amt = p.shares * open_px.get(code, 0)
            forced = reason.startswith(("P0", "E-P0.0"))
            if not forced and exec_amt + amt * ratio > eq_t1 * 0.20:
                pf.pending_sells.append((date, code, reason, ratio))
                continue
            pf.sell(date, code, reason, ratio, price=open_px.get(code, 0), forced=forced)
            exec_amt += amt * ratio
            _ep1_block(code, reason)

        # pending 次日执行
        still = []
        for (pd_, c, reason, ratio) in pf.pending_sells:
            if pd_ == date:
                continue  # 本日排队，次日再处理
            p = pf.holdings.get(c)
            if p:
                pf.sell(date, c, reason, ratio, price=open_px.get(c, 0), forced=False)
                _ep1_block(c, reason)
            else:
                still.append((pd_, c, reason, ratio))
        pf.pending_sells = still

        # 总仓位压缩
        def reduce_to(target_pct):
            for _ in range(3):
                eq_now = pf.equity({c: rows.get(c, {}).get("close", 0) for c in pf.holdings})
                pos_pct = 1.0 - pf.cash / max(eq_now, 1)
                if pos_pct <= target_pct:
                    break
                # 按持仓占比从大到小减仓
                wl = sorted(pf.holdings.items(), key=lambda kv: kv[1].shares * rows.get(kv[0], {}).get("close", 0), reverse=True)
                for c, p in wl[:1]:
                    pf.sell(date, c, "总仓位压缩", 0.5, price=open_px.get(c, 0), forced=True)
        if comp_p9:
            reduce_to(0.20)
        elif comp_p10:
            reduce_to(0.60)
        if comp_p8:
            reduce_to(0.40)

        # ---------- 建仓 ----------
        melt_block = melt >= 1   # 熔断Ⅰ级起当日暂停新建仓
        vol_block = bool(gate)   # R-04 双闸门 + E1r 兼容（闸门为建仓第一前置条件）
        if not melt_block and not comp_p9 and not vol_block:
            # 候选池排序（观察池Top3, 窄池降级为全部候选）
            cands = [c for c in UNIVERSE if c in rows]
            cands.sort(key=lambda c: scores.get(c, 0), reverse=True)
            for code in cands:
                # 禁忌25条: 已持仓/未清仓禁止重复建仓（持仓冲突检查）
                if code in pf.holdings:
                    stats["intercept"]["持仓冲突"] += 1; continue
                # 洗仓封堵检查
                if hasattr(pf, "qual_block") and code in pf.qual_block and i < pf.qual_block[code]["until"]:
                    if scores.get(code, 0) < pf.qual_block[code]["threshold"]:
                        stats["intercept"]["洗仓封堵"] += 1; continue
                row = rows[code]
                dn, name, ptype, ind = UNIVERSE[code]
                fin = None
                if ptype == "stock":
                    f = fin_at(fins.get(code), t1)  # R-09: 财报缺失 → None
                    fin = dict(f) if f else None
                    if fin:
                        fin["price"] = row["close"]
                # ---- R-05 S1突破确认制（前置2, 先于层级1; 仅S1常规建仓适用, 观察通道/S3不适用） ----
                if S1CONFIRM_ON and tre.state == "S1" and not tre.obs_active:
                    s1_2d = len(tre_hist) >= 2 and tre_hist[-1] == "S1" and tre_hist[-2] == "S1"
                    pnl_dn = panels[dn]
                    t2 = days[i - 2] if i >= 2 else None
                    if t2 is not None and t1 in pnl_dn.index and t2 in pnl_dn.index:
                        stand2 = (pnl_dn.loc[t1, "close"] > pnl_dn.loc[t1, "MA60"]) and \
                                 (pnl_dn.loc[t2, "close"] > pnl_dn.loc[t2, "MA60"])
                    else:
                        stand2 = False
                    open_ok = (open_px[code] / row["close"] - 1) * 100 <= 1.0 if row["close"] > 0 else False
                    if not (s1_2d and stand2 and open_ok):
                        stats["intercept"]["S1确认制"] += 1
                        continue
                # 层级1
                if ptype == "stock":
                    ok1, r1 = layer1_stock(fin)
                else:
                    ok1, r1 = layer1_etf(row, product_ok=True, amount_min=3000e4)
                if not ok1:
                    stats["intercept"]["层级1"] += 1; continue
                # 行业近5日涨幅前10% / RPS前20% (窄池代理: 用RPS60)
                rps_ok = row.get("RPS60", 50) >= 30
                if not rps_ok:
                    stats["intercept"]["RPS"] += 1; continue
                # 层级3.5
                # ETF: 信号时效=首次入选观察池日（得分≥80即在池内=信号有效）[文档:ETF以首次入选观察池日为信号生成日]
                # 个股: R值实时判断（回调/突破买点）
                if ptype != "stock":
                    r_level, l20, h60, pb_ok = ("A", row.get("L20"), row.get("H60"), True)
                else:
                    # 【去冗余·阶段3·冗余3】R值等级统一A/B/C三级（对齐scoring.layer35与第七章MIN③：≤0.15=A,≤0.25=B,>0.25=C）
                    _r = row.get("R", 99)
                    r_level = "A" if _r <= 0.15 else ("B" if _r <= 0.25 else "C")
                    l20, h60, pb_ok = row.get("L20"), row.get("H60"), True
                if r_level == "C":
                    stats["intercept"]["R值C级"] += 1; continue
                # TRE 建仓模式
                obs_mode = tre.obs_active
                s3_mode = tre.state == "S3" and not obs_mode
                s12_mode = tre.state in ("S1", "S2") and not obs_mode
                if not (obs_mode or s3_mode or s12_mode):
                    stats["intercept"]["TRE不可建仓"] += 1; continue
                # H1: S1 常规建仓禁 ETF（归因⑥: ETF亏/个股盈; S1追涨ETF被均值回归打穿;
                #     仅限 S1 常规, 观察通道/S3 试探仓不受影响）
                if H1_S1NOETF_ON and tre.state == "S1" and not obs_mode and not s3_mode and ptype != "stock":
                    stats["intercept"]["H1禁S1+ETF"] += 1; continue
                # 分级门控 HALF 窗: 弱反弹期不追 S1/S2 常规（归因: S1追涨是亏损核心），
                #   仅保留 S3 有限建仓 + 观察通道试探仓（盈利引擎），仓位×0.5（半仓）
                if TIERGATE_ON and win == "HALF" and s12_mode:
                    stats["intercept"]["分级HALF禁S1/S2"] += 1; continue
                # 得分门槛（分状态: S1常规 / S2减半更严 / 观察通道与S3有限）
                # R2: 行业ETF分轨 S1=65 / S2=72 / 观察=68（行业ETF得分天然偏低, 与宽基同一门槛结构性否决）
                # R-10 重构分轨（v4.7-R10）: 个股/宽基常规80 / 行业ETF 78 / S3与观察通道85
                #   （标的面扩大后无需靠降门槛凑建仓; 归因①证明高得分差在追涨时点而非分数, 门槛不降, 时点问题由R-05解决）
                ind_etf_flag = (ptype == "etf_ind") and R2_ON
                if R10_GATES_ON:
                    # 【提频·门槛放宽 2026-08-21】R10门槛80/85过高→建仓枯竭(16笔/6年, D-5主因)
                    #   回测证据：降门槛期望更高(+0.77%)，报告推测最优75-78中间值；行业ETF得分天然偏低保持-2分
                    g_s1 = 73.0 if ptype == "etf_ind" else 75.0
                    g_s2 = 73.0 if ptype == "etf_ind" else 75.0
                    g_obs = 78.0
                else:
                    g_s1 = ETFI_GATE_S1 if ind_etf_flag else SCORE_GATE
                    g_s2 = ETFI_GATE_S2 if ind_etf_flag else S2_GATE
                    g_obs = ETFI_GATE_OBS if ind_etf_flag else OBS_GATE
                # 进攻线专用: ATTACK_SCORE > 0 时统一覆盖所有状态门槛
                if ATTACK_SCORE > 0:
                    g_s1 = g_s2 = g_obs = ATTACK_SCORE
                if obs_mode or s3_mode:
                    if scores.get(code, 0) < g_obs or not rps_ok:
                        stats["intercept"]["得分<OBS_GATE"] += 1; continue
                elif tre.state == "S2":
                    if scores.get(code, 0) < g_s2:
                        stats["intercept"]["得分<S2_GATE"] += 1; continue
                else:
                    if scores.get(code, 0) < g_s1:
                        stats["intercept"]["得分<SCORE_GATE"] += 1; continue
                # 组合约束
                n_hold = len(pf.holdings)
                n_same = sum(1 for c2 in pf.holdings if UNIVERSE[c2][3] == ind and ind)
                if n_hold >= 5 or (ind and n_same >= 2):
                    stats["intercept"]["组合约束"] += 1; continue
                # 六灯/七灯
                open_pct = (open_px[code] / row["close"] - 1) * 100 if row["close"] > 0 else 99
                if ptype == "stock":
                    ok_l, lights = six_lights(row, tre.state, tre.obs_active, tre.state == "S3",
                                              n_hold, n_same, beta, cap, open_pct, r_level)
                else:
                    # 【去冗余·阶段2·冗余4】第2灯引用层级1结果(ok1)，不再硬编码 True
                    ok_l, lights = seven_lights(row, tre.state, tre.obs_active, n_hold, n_same,
                                                beta, cap, open_pct, r_level, ok1, True,
                                                row.get("ma60_break90", 0),
                                                ind_etf=(ptype == "etf_ind") and R1_ON)
                if not ok_l:
                    stats["intercept"]["六/七灯"] += 1; continue
                # MIN 9项 (ETF: ③性价比按入池有效=100%处理 [文档3.5信号时效])
                mn_row = row
                if ptype != "stock":
                    mn_row = row.copy(); mn_row["R"] = 0.0
                min_pct, items = min_nine(mn_row, tre.state, tre.obs_active, tre.state == "S3",
                                          fin, row.get("PB_EXPAND", 1.0),
                                          ind_etf=(ptype == "etf_ind") and R3_ON)
                if min_pct <= 0:
                    stats["intercept"]["MIN≤0"] += 1; continue
                # ATR缩放 / 流动性分层
                base_atr = panels["idx_hs300"].loc[t1, "ATR20P"]
                atr_scale = min(base_atr / max(row.get("ATR20P", 2.0), 0.5), 1.5)
                if row.get("ATR20P", 0) > 8:
                    stats["intercept"]["ATR>8%"] += 1; continue
                amt20 = row.get("amount20", 0)
                if ptype == "stock":
                    liq_cap = 15.0 if amt20 >= 5e8 else (12.0 if amt20 >= 1e8 else (8.0 if amt20 >= 5e7 else 0.0))
                else:
                    liq_cap = 15.0 if amt20 >= 5e8 else (12.0 if amt20 >= 1e8 else (8.0 if amt20 >= 3e7 else 0.0))
                if liq_cap <= 0:
                    stats["intercept"]["流动性不足"] += 1; continue
                target = f04(min_pct, atr_scale, liq_cap)
                if target <= 0:
                    stats["intercept"]["F04<3%"] += 1; continue
                # 分级门控 HALF 窗: 半仓窗目标仓位×0.5（路径A"仓位上限打5折"）
                if TIERGATE_ON and win == "HALF":
                    target *= 0.5
                    if target < 3.0:
                        stats["intercept"]["分级HALF<3%"] += 1; continue
                # 单笔风险预算≤1%总资产
                risk_budget = target * row.get("ATR20P", 3.0) / 100.0
                if risk_budget > 1.0:
                    target = 1.0 / max(row.get("ATR20P", 3.0) / 100.0, 0.01)
                    if target < 3.0:
                        stats["intercept"]["风险预算"] += 1; continue
                # 总仓位上限
                eq_now = pf.equity({c: rows.get(c, {}).get("close", 0) for c in pf.holdings})
                pos_pct = 1.0 - pf.cash / max(eq_now, 1)
                if pos_pct + target / 100.0 > cap / 100.0:
                    target = max(0.0, (cap / 100.0 - pos_pct) * 100.0)
                    if target < 3.0:
                        stats["intercept"]["总仓位上限"] += 1; continue
                # 行业≤30%
                if ind:
                    ind_w = sum(pf.holdings[c2].shares * rows[c2]["close"] for c2 in pf.holdings if UNIVERSE[c2][3] == ind) / max(eq_now, 1)
                    if (ind_w + target / 100.0) > 0.30:
                        target = max(0.0, (0.30 - ind_w) * 100.0)
                        if target < 3.0:
                            stats["intercept"]["行业>30%"] += 1; continue
                # E2r: S1 建仓降档 50%（归因显示 S1 期望-2.94%是亏损核心，降权比排除更保守）
                if S1DERATE_ON and tre.state == "S1" and not obs_mode:
                    target *= 0.5
                # F-04 专项: 金额贡献倍率（在全部约束判定后放大执行金额; 凯利总仓位cap仍约束叠加）
                if F04_MULT != 1.0:
                    target *= F04_MULT
                # P0-3: BREADTH 否决层（MHD 宽度<阈值 → 拒绝建仓, 附加否决非许可）
                if BREADTH_VETO_ON:
                    brd = breadth_map.get(t1, 30.0)  # T-1 日 BREADTH 分（缺失默认30=中性）
                    if brd < BREADTH_MIN:
                        stats["intercept"]["BREADTH否决"] = stats["intercept"].get("BREADTH否决", 0) + 1
                        continue
                # 执行买入
                obs_probe = obs_mode
                s3_pos = s3_mode
                reason = "观察通道试探建仓" if obs_mode else ("S3有限建仓" if s3_mode else ("S2减半建仓" if tre.state == "S2" else "S1正常建仓"))
                pf.buy(date, code, name, ptype, ind, open_px[code], target, eq_now, i,
                       obs_probe=obs_probe, s3_pos=s3_pos, reason=reason)
                p = pf.holdings.get(code)
                if p:
                    p.target_w = target
                    # H2: S1 常规建仓标记（观察通道/S3 试探仓不适用最短持有期豁免）
                    p.s1_min_hold = (tre.state == "S1" and not obs_mode and not s3_mode)
                    if obs_probe or s3_pos:
                        p.qual_cnt = 0; p.qual_expired = False
                    buys.append({"date": date, "code": code, "reason": reason,
                                 "score": scores.get(code, 0), "target": target,
                                 "tre": tre.state, "obs": obs_mode, "min": min_pct,
                                 "lights_ok": True, "r_level": r_level,
                                 "win": win})

        # ---------- 双周再平衡（每10交易日, 以月首为锚） ----------
        if active and (i - anchor_idx(i, days)) % 10 == 0:
            eq_now = pf.equity({c: rows.get(c, {}).get("close", 0) for c in pf.holdings})
            for c, p in list(pf.holdings.items()):
                if p.target_w <= 0:
                    continue
                w_now = p.shares * rows.get(c, {}).get("close", 0) / max(eq_now, 1) * 100
                if w_now > p.target_w + 5.0 and open_px.get(c, 0) > 0:
                    ratio = (w_now - p.target_w) / w_now
                    pf.sell(date, c, "双周再平衡(权重超限减仓)", ratio, price=open_px[c])

        # ---------- 盘后 ----------
        qual_flags = {}
        for c, p in pf.holdings.items():
            dn = UNIVERSE[c][0]
            if date not in panels[dn].index:
                continue
            ct = panels[dn].loc[date, "close"]
            p.max_high = max(p.max_high, ct)
            p.time_cnt += 1
            # 11.5a/E-P9.5 每日盘后监控（T收盘评分）
            if (p.obs_probe or p.s3_pos) and not p.qual_expired:
                row_t = panels[dn].loc[date].copy()
                sc_t = compute_score(c, dn, UNIVERSE[c][2], row_t, fins, panels)
                if sc_t < 85:
                    p.qual_break = True
                    p.qual_break_reason = f"{'E-P9.5' if UNIVERSE[c][2]!='stock' else '11.5a'}-资格失守(盘后得分{sc_t:.0f}<85)"
                    p.qual_cnt = 0
                else:
                    p.qual_cnt += 1
                    if p.qual_cnt >= 30:
                        p.qual_expired = True  # 30日存续上限, 过期转常规

        # 风险贡献度/行业>45%强制减仓（T+1开盘执行）
        eq_now = pf.equity({c: rows.get(c, {}).get("close", 0) for c in pf.holdings})
        wl = {c: (p.shares * rows.get(c, {}).get("close", 0) / max(eq_now, 1), p) for c, p in pf.holdings.items()}
        if len(wl) >= 2:
            total_beta_w = sum(w * rows[c].get("BETA60", 100) / 100 for c, (w, _) in wl.items() if np.isfinite(rows[c].get("BETA60", np.nan)))
            for c, (w, p) in wl.items():
                if np.isfinite(rows[c].get("BETA60", np.nan)) and total_beta_w > 0:
                    contrib = w * rows[c]["BETA60"] / 100.0 / total_beta_w
                    if contrib > 0.25:
                        pf.pending_sells.append((date, c, "风险贡献度>25%减仓", 0.3))
        ind_w_all = {}
        for c, (w, p) in wl.items():
            ind = UNIVERSE[c][3]
            if ind:
                ind_w_all[ind] = ind_w_all.get(ind, 0) + w
        for ind, iw in ind_w_all.items():
            if iw > 0.45:
                for c, (w, p) in wl.items():
                    if UNIVERSE[c][3] == ind and open_px.get(c, 0) > 0:
                        pf.sell(date, c, "行业集中度>45%强制减仓", 0.4, price=open_px[c])

        # 现金管理收益（159650实际收益 或 货基2%年化[代理]）
        cash_r = 0.0
        if cash_df is not None and t1 in cash_df.index:
            cash_r = float(cash_df.loc[t1, "pct_chg"]) / 100.0
        else:
            cash_r = 0.02 / 252.0
        pf.cash_mgmt_ret += pf.cash * cash_r
        pf.cash *= (1 + cash_r)

        # 组合收益与价值更新
        prices_t = {}
        for c in pf.holdings:
            dn = UNIVERSE[c][0]
            prices_t[c] = panels[dn].loc[date, "close"] if date in panels[dn].index else rows[c].get("close", 0)
        eq_t = pf.equity(prices_t)
        day_ret_t = eq_t / max(eq_t1, 1e-9) - 1 if eq_t1 > 0 else 0
        pf.ret_hist_20.append(day_ret_t)
        pf.ret_hist_20 = pf.ret_hist_20[-60:]
        pf.update_after_close(prices_t, day_ret_t, vol20)
        pf.prev_vol20 = vol20

        # 月度收益
        if date[5:7] != pf.cur_month:
            pf.month_start_equity = eq_t
            pf.cur_month = date[5:7]

        hist.append({
            "date": date, "tre": tre.state, "obs": tre.obs_active,
            "equity": eq_t, "cash": pf.cash, "dd": pf.drawdown,
            "cap": cap, "vol20": vol20, "pf_vol": pf_vol20, "melt": melt,
            "gate": gate,   # R-04 波动率闸门（空=未触发）
            "win": win,     # 阶段1 A/B: 分级门控窗口 FULL/HALF/NONE（空=未启用）
            "holdings": {c: round(p.shares * prices_t.get(c, 0), 0) for c, p in pf.holdings.items()},
            "beta": beta,
        })
        if tre.obs_active:
            obs_snapshots.append({"date": date, "state": tre.state, "obs_since": tre.obs_since})

    result = {
        "label": label, "period": period, "hist": hist, "trades": pf.trades,
        "closed": pf.closed_periods, "tre_log": tre.log, "obs_stats": {
            "entries": tre.obs_channel_entries, "fail": tre.obs_fail,
            "up_s2": tre.obs_s2_upgrades, "up_s1": tre.obs_s1_upgrades,
            "confirm_breaks": tre.obs_confirm,
        },
        "meltdown": pf.meltdown_count, "meltdown_captured": pf.meltdown_captured,
        "cash_mgmt_ret": pf.cash_mgmt_ret, "buys": buys, "stats": stats,
        "gate_stats": {  # R-04 闸门统计
            "gate_days": sum(1 for g in gate_hist if g),
            "gate_a_days": sum(1 for g in gate_hist if g.startswith("A-")),
            "gate_b_days": sum(1 for g in gate_hist if g.startswith("B-")),
        },
        "win_stats": {  # 阶段1 A/B: 分级门控窗口天数统计（空=未启用）
            "win_full": win_hist.count("FULL"),
            "win_half": win_hist.count("HALF"),
            "win_none": win_hist.count("NONE"),
        },
        "universe_size": len(UNIVERSE),  # R-09 标的面利用率
        "final_equity": eq_t, "final_cash": pf.cash,
    }
    return result


def anchor_idx(i: int, days: list) -> int:
    """每月第1个交易日为锚点"""
    d = days[i]
    j = i
    while j > 0 and days[j][5:7] == d[5:7]:
        j -= 1
    return j + 1


# ---------------- 主入口 ----------------
def main():
    panels0, fins = load_all()
    panels = build_panels(panels0)
    panels = add_pit_pb(panels, fins)
    days = list(panels["idx_hs300"].index)

    # 预热期（2018-06-01起推进状态机但2019-01-02前不交易）
    warm = [d for d in days if d >= "2018-06-01" and d < PERIOD_IN[0]]
    res_in = run_backtest(panels, fins, warm + [d for d in days if d >= PERIOD_IN[0] and d <= PERIOD_IN[1]], PERIOD_IN, "样本内6年")
    res_oos = run_backtest(panels, fins, [d for d in days if d >= PERIOD_OOS[0] and d <= PERIOD_OOS[1]], PERIOD_OOS, "样本外18个月")

    with open(os.path.join(OUT, "results_in.json"), "w", encoding="utf-8") as fh:
        json.dump(res_in, fh, ensure_ascii=False, indent=1, default=str)
    with open(os.path.join(OUT, "results_oos.json"), "w", encoding="utf-8") as fh:
        json.dump(res_oos, fh, ensure_ascii=False, indent=1, default=str)
    print("DONE in:", res_in["final_equity"], "oos:", res_oos["final_equity"])
    print("obs_stats:", res_in["obs_stats"])
    print("closed periods:", len(res_in["closed"]))
    print("in trades:", len(res_in["trades"]), " buys:", len(res_in["buys"]))
    print("oos trades:", len(res_oos["trades"]), " buys:", len(res_oos["buys"]))
    for b in res_in["buys"][:40]:
        print("  BUY", b["date"], b["code"], b["reason"], "score=%.0f" % b["score"], "target=%.0f%%" % b["target"], b["tre"])


if __name__ == "__main__":
    main()
