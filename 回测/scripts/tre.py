# -*- coding: utf-8 -*-
"""
TRE 趋势状态识别引擎 —— v4.7-R8 3.1/3.2/F-30/F-32/F-33 完整实现
包含:
  - 四态定义与判定矩阵 (S1/S2/S3/S4)
  - 状态转换表（含缓冲期: S1→S2当日 / S2→S3连2日 / S3→S4当日 / S4→S3连3日 / S4→S2连2日 / S3→S2连2日 / S2→S1连2日）
  - S4 加速恢复观察通道: 触发(≥2核心指数ADX≥20且站稳MA60,连续2日确认)、
    升级退出(F-33 五分区互斥穷尽)、失效退出(ADX<15或破MA60, 失效优先于升级)
  - R9落地C-1: 确认期不计入升级计数（升级计数自进入观察模式之日起算）
"""
from dataclasses import dataclass, field
from typing import Optional


# ---------------- 基础判定 ----------------

def raw_state(core_adx: list[float], cross20: int, vol20: float,
              n_core: int = 3, s2_major_on: bool = False,
              breadth: float | None = None, s2_breadth_gate: float = 15.0) -> str:
    """原始状态判定（无缓冲期）
    core_adx: 各核心指数当日 ADX 值列表
    cross20: 组合 MA60 有效穿越计数（近20日）
    vol20:   组合 20 日年化波动率(%)
    判定规则按 3.1 矩阵（S1 优先、S4 次之、S3 再次、S2 兜底）
    s2_major_on / breadth / s2_breadth_gate：Track B1（2026-08-26）S2 收紧开关。
      开启时 S2 兜底改为"多数核心指数 ADX≥20 且 BREADTH 宽度≥阈值"才判 S2，
      否则降级 S3（不建常规仓）——消除单指数 ADX 噪声假主升。
      默认关闭 → 行为与原基线 V1 完全一致。
    """
    n_strong = sum(1 for a in core_adx if a >= 20)
    n_weak = sum(1 for a in core_adx if a < 15)
    n_weak_majority = n_weak > n_core / 2  # 多数指数 ADX<15

    # S1: ≥2个核心指数ADX≥20 且 穿越≤3 且 波动率<18%
    if n_strong >= 2 and cross20 <= 3 and vol20 < 18:
        return "S1"
    # S4: 多数指数ADX<15 且 穿越≥5  或  波动率>25%
    if (n_weak_majority and cross20 >= 5) or vol20 > 25:
        return "S4"
    # S3: 多数指数ADX<15 且 穿越3-4 且 波动率15-25%
    if n_weak_majority and 3 <= cross20 <= 4 and 15 <= vol20 <= 25:
        return "S3"
    # S2: ADX 15-20 或 接近S1但未满足S1完整条件（波动率≥18% 或 穿越>3）【R7扩展定义】
    if s2_major_on:
        # Track B1: 仅当多数核心指数 ADX≥20 且 BREADTH 宽度确认时才判 S2（真主升），
        # 否则降级 S3（避免样本外单指数 ADX 噪声导致的假主升建仓）
        majority = n_core // 2 + 1
        if n_strong >= majority and (breadth is None or breadth >= s2_breadth_gate):
            return "S2"
        return "S3"
    return "S2"


@dataclass
class TreState:
    """TRE 状态机（含观察通道）"""
    state: str = "S2"                    # 名义状态 S1/S2/S3/S4
    buffer: dict = field(default_factory=lambda: {"S4toS3": 0, "S4toS2": 0, "S3toS2": 0, "S2toS1": 0, "S2toS3": 0})
    # 观察通道
    obs_active: bool = False             # 观察通道是否开启
    obs_confirm: int = 0                 # 通道触发确认连续天数（确认期，不计入升级计数）
    obs_since: int = 0                   # 自进入观察模式以来的交易日数（升级计数基准日）
    obs_up_s1: int = 0                   # 连续满足 S1 升级条件天数
    obs_up_s2: int = 0                   # 连续满足 S2 升级条件天数
    obs_fail: int = 0                    # 累计失效次数
    obs_s2_upgrades: int = 0             # 累计升级S2次数
    obs_s1_upgrades: int = 0             # 累计升级S1次数
    obs_channel_entries: int = 0         # 累计通道触发进入次数
    just_upgraded: bool = False          # 观察通道升级退出当日标记（豁免当日名义状态转换）
    log: list = field(default_factory=list)

    def log_event(self, t, msg):
        self.log.append((t, msg))


def _stand_ma60(below_streak: float, atr_ok: bool) -> bool:
    """站稳 MA60: 收盘高于MA60 且 (ATR带宽确认 或 连续2日收盘确认)"""
    return (below_streak == 0) and (atr_ok or True)


def step_tre(state: TreState, day_idx: int, core_adx: list[float], cross20: int,
             vol20: float, hs300_below_streak: float, hs300_close_gt_ma60: bool,
             atr_band_ok: bool = True, variant: str = "V0",
             obs_guard: bool = True, s2_major_on: bool = False,
             breadth: float | None = None, s2_breadth_gate: float = 15.0) -> TreState:
    """推进一天 TRE 状态机（用当日收盘数据判定，次日开盘生效——T-1铁律由引擎调度）
    hs300_below_streak: 沪深300收盘低于MA60的连续天数（0=在MA60上方）
    hs300_close_gt_ma60: 沪深300收盘是否高于MA60
    variant: V0=现行3.2转换表; V1=+S2→S4当日生效(P0-B重设计, 修复S4锁死)
    obs_guard: P0-E 观察通道升级退出当日豁免名义状态转换（防S2→S4吞没升级）
    """
    s = state
    raw = raw_state(core_adx, cross20, vol20, s2_major_on=s2_major_on,
                    breadth=breadth, s2_breadth_gate=s2_breadth_gate)

    # ============ 1. S4 观察通道逻辑（优先级最高，独立于名义状态） ============
    if s.state == "S4" and not s.obs_active:
        # 触发条件: 单日 ≥2个核心指数ADX≥20 且 收盘站稳MA60（连续2日确认）
        n_strong = sum(1 for a in core_adx if a >= 20)
        stand = hs300_close_gt_ma60 and atr_band_ok
        if n_strong >= 2 and stand:
            s.obs_confirm += 1
            if s.obs_confirm >= 2:
                # 连续2日确认 → 次日进入观察模式
                s.obs_active = True
                s.obs_confirm = 0
                s.obs_since = 0
                s.obs_up_s1 = 0
                s.obs_up_s2 = 0
                s.obs_channel_entries += 1
                s.log_event(day_idx, f"[OBS] 触发进入观察模式 (ADX强指数{n_strong}, 站稳MA60)")
        else:
            # 确认中断 → 计数清零（R10 P2-1 裁决方向: 确认期内任一日失效→中断重计）
            if s.obs_confirm > 0:
                s.log_event(day_idx, f"[OBS] 触发确认中断(第{s.obs_confirm}日), 计数清零")
            s.obs_confirm = 0

    elif s.obs_active:
        # 观察通道存续期: F-33 升级/失效判定（任一日失效优先于升级）
        n_strong = sum(1 for a in core_adx if a >= 20)
        # --- 失效条件（正交硬性条款，优先） ---
        adx_fail = n_strong == 0 and all(a < 15 for a in core_adx)  # ADX回落至<15(核心指数)
        adx_fail = adx_fail or (max(core_adx) < 15 if core_adx else True)
        ma_fail = not hs300_close_gt_ma60  # 收盘跌破MA60
        failed = adx_fail or ma_fail
        # --- 升级条件（F-33 五分区互斥穷尽） ---
        # ① 完整S1: ≥2核心ADX≥20 且 穿越≤3 且 波动率<18%
        up_s1_cond = (n_strong >= 2) and (cross20 <= 3) and (vol20 < 18)
        # ②③④ S2 方向: ADX∈[15,20) 或 (ADX≥20但波动率≥18% 或 穿越>3)
        if s2_major_on:
            # Track B1: 观察通道升级 S2 同样要求多数核心指数 ADX≥20 且 BREADTH 确认
            majority = len(core_adx) // 2 + 1
            up_s2_cond = (n_strong >= majority) and (vol20 < 22) and \
                         (breadth is None or breadth >= s2_breadth_gate)
        else:
            any_adx_15_20 = any(15 <= a < 20 for a in core_adx)
            up_s2_cond = any_adx_15_20 or ((n_strong >= 2) and ((vol20 >= 18) or (cross20 > 3)))

        if failed:
            # 失效优先: 升级计数清零, 通道终止
            s.obs_fail += 1
            s.log_event(day_idx, f"[OBS] 失效退出 (adx_fail={adx_fail}, ma_fail={ma_fail}) 恢复纯S4")
            s.obs_active = False
            s.obs_since = 0
            s.obs_up_s1 = 0
            s.obs_up_s2 = 0
            s.obs_confirm = 0
        else:
            s.obs_since += 1
            if up_s1_cond:
                s.obs_up_s1 += 1
                s.obs_up_s2 = 0
            elif up_s2_cond:
                s.obs_up_s2 += 1
                s.obs_up_s1 = 0
            else:
                s.obs_up_s1 = 0
                s.obs_up_s2 = 0
            # 升级退出判定
            if s.obs_up_s1 >= 2:
                s.obs_active = False
                s.obs_s1_upgrades += 1
                s.state = "S1"
                s.just_upgraded = True
                s.log_event(day_idx, f"[OBS] 连2日满足完整S1 → 升级退出为 S1 (观察期{s.obs_since}日)")
                s.obs_up_s1 = 0; s.obs_up_s2 = 0
            elif s.obs_up_s2 >= 2:
                s.obs_active = False
                s.obs_s2_upgrades += 1
                s.state = "S2"
                s.just_upgraded = True
                s.log_event(day_idx, f"[OBS] 连2日满足S2条件 → 升级退出为 S2 (观察期{s.obs_since}日)")
                s.obs_up_s1 = 0; s.obs_up_s2 = 0

    # ============ 2. 名义状态转换（观察通道期间仍按 3.1 转换表推进，F-32） ============
    cur = s.state
    if s.just_upgraded:
        s.just_upgraded = False
        if obs_guard:
            # 【P0-E】观察通道升级退出当日豁免名义状态转换：
            #   升级 S2 若当日再执行 S2→S4(V1) 会被立即吞没 → 升级建仓窗口为零（2020-09起7次0天存活）
            #   裁决: 升级优先, 当日跳过转换（次日恢复, 若仍满足S2→S4则正常触发）
            s.log_event(day_idx, f"[OBS] 升级当日豁免名义状态转换 (state={cur})")
            return s
        # obs_guard=False: 复位标记后继续执行正常转换（回归对照行为）
    if not (cur == "S4" and s.obs_active):
        # 观察通道开启期间名义状态保持 S4 不变（F-32），不执行转换
        if cur == "S1":
            if raw != "S1":
                s.state = "S2"   # S1→S2 当日立即生效
                s.log_event(day_idx, f"[TRE] S1→S2 当日生效 (raw={raw})")
        elif cur == "S2":
            if raw == "S4" and variant in ("V1", "V2"):
                # 【P0-B 重设计】S2→S4 当日生效: 修复风暴态被S2锁死（raw S4 19.2% 但名义S4仅1.0%）
                s.state = "S4"
                s.buffer["S2toS3"] = 0
                s.log_event(day_idx, f"[TRE] S2→S4 当日生效 (raw={raw}, variant={variant})")
            elif raw == "S3":
                s.buffer["S2toS3"] += 1
                if s.buffer["S2toS3"] >= 2:
                    s.state = "S3"; s.buffer["S2toS3"] = 0
                    s.log_event(day_idx, f"[TRE] S2→S3 连2日 (raw={raw})")
            else:
                s.buffer["S2toS3"] = 0
                if raw == "S1":
                    s.buffer["S2toS1"] += 1
                    if s.buffer["S2toS1"] >= 2:
                        s.state = "S1"; s.buffer["S2toS1"] = 0
                        s.log_event(day_idx, f"[TRE] S2→S1 连2日 (raw={raw})")
                else:
                    s.buffer["S2toS1"] = 0
        elif cur == "S3":
            if raw == "S4":
                s.state = "S4"   # S3→S4 当日立即生效
                s.log_event(day_idx, f"[TRE] S3→S4 当日生效 (raw={raw})")
            elif raw == "S2":
                s.buffer["S3toS2"] += 1
                if s.buffer["S3toS2"] >= 2:
                    s.state = "S2"; s.buffer["S3toS2"] = 0
                    s.log_event(day_idx, f"[TRE] S3→S2 连2日 (raw={raw})")
            else:
                s.buffer["S3toS2"] = 0
        elif cur == "S4":
            if raw == "S3":
                s.buffer["S4toS3"] += 1
                if s.buffer["S4toS3"] >= 3:
                    s.state = "S3"; s.buffer["S4toS3"] = 0
                    s.log_event(day_idx, f"[TRE] S4→S3 连3日 (raw={raw})")
            else:
                s.buffer["S4toS3"] = 0
                if raw == "S2":
                    s.buffer["S4toS2"] += 1
                    if s.buffer["S4toS2"] >= 2:
                        s.state = "S2"; s.buffer["S4toS2"] = 0
                        s.log_event(day_idx, f"[TRE] S4→S2 连2日 (raw={raw})")
                else:
                    s.buffer["S4toS2"] = 0

    return s
