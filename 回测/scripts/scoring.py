# -*- coding: utf-8 -*-
"""
评分与裁决模块 —— v4.7-R8 回测引擎
实现: 个股24因子代理评分 / ETF 13因子代理评分 / 层级裁决(1/3/3.5) / 六灯七灯 / MIN 9项 / F-04
回测标注约定:
  [代理] = 用可得数据近似原规则（如 R 值定义、景气度、择时质量）
  [MISSING] = 原规则数据源回测期不可得（政策类、折溢价、ETF份额、北向等），按"不触发/中性分"处理
"""
import os
import numpy as np
import pandas as pd


# 【去冗余·冗余2】趋势位置合并变体开关（附录E，2026-08-24 提前回测）
# "0"=原逻辑（基线, 完全向后兼容, 诊断脚本默认）; "1"=温和(②④⑥ C→25); "2"=标准(②⑥ C→25, ④ C→0);
# "3"=严格(②④⑥ C→0); "4"=严格+第2灯仅A档
TP_VARIANT = os.environ.get("BT_TP_VARIANT", "0")


# ================= PIT 财报查询 =================

def build_financial_series(fin_json: dict, code: str) -> pd.DataFrame:
    """把财报JSON转为按 NOTICE_DATE(公告日) 生效的序列（PIT：公告后才可用）
    返回 df: index=NOTICE_DATE, 列: report_date, rev_yoy, np_yoy, np_ded_yoy,
            roe, bps, eps, ocf_ps, gm, debt, rev(营收), np(归母净利), np_ded(扣非)
    同比增速用累计值自行计算（本期/上年同期-1），避免接口预估值
    """
    recs = fin_json.get(code, [])
    if not recs:
        return pd.DataFrame()
    rows = []
    by_period = {}
    for r in recs:
        rd = str(r.get("REPORT_DATE") or "")[:10]
        if len(rd) < 10:
            continue
        by_period[rd] = r
    for rd, r in by_period.items():
        notice = str(r.get("NOTICE_DATE") or "")[:10]
        if len(notice) < 10:
            notice = rd
        rows.append({
            "notice": notice, "period": rd,
            "rev": r.get("TOTALOPERATEREVE") or 0,
            "np": r.get("PARENTNETPROFIT") or 0,
            "np_ded": r.get("KCFJCXSYJLR") or 0,
            "roe": r.get("ROEJQ"), "bps": r.get("BPS"),
            "eps": r.get("EPSJB"), "ocf_ps": r.get("MGJYXJJE"),
            "gm": r.get("XSMLL"), "debt": r.get("ZCFZL"),
        })
    df = pd.DataFrame(rows).sort_values("period")
    df = df.drop_duplicates("period", keep="last")
    # 计算同比（对上年同报告期）
    def _yoy(col):
        m = df["period"].str[5:7].map({"03": 1, "06": 2, "09": 3, "12": 4})
        # 上年同期记录
        prev = {}
        out = []
        for i, row in df.iterrows():
            p = row["period"]; y = int(p[:4]); mm = m.loc[i]
            key = f"{y-1}-{p[5:]}"
            if key in prev and prev[key] > 0:
                out.append(row[col] / prev[key] - 1 if row[col] is not None else None)
            else:
                out.append(None)
            prev[p] = row[col]
        return out
    df["rev_yoy"] = _yoy("rev")
    df["np_yoy"] = _yoy("np")
    df["np_ded_yoy"] = _yoy("np_ded")
    df["prev_np_yoy"] = df["np_yoy"].shift(1)  # 上一期净利同比（景气度减半判定用）
    df = df.set_index("notice").sort_index()
    return df


def fin_at(df_fin: pd.DataFrame, date) -> dict | None:
    """PIT: 返回 date 当日或之前最近已公告的财报指标（None=无公告）"""
    if df_fin is None or df_fin.empty:
        return None
    pos = df_fin.index.searchsorted(date, side="right")
    if pos == 0:
        return None
    row = df_fin.iloc[pos - 1]
    return row.to_dict()


# ================= 个股 24 因子代理评分 =================

def stock_score(row: dict, fin: dict | None, hist_pb: list[float],
                hist_pe: list[float]) -> float:
    """个股 24 因子综合得分（0-100），回测代理版
    row: T-1 日指标（MA60/ADX14/DEV60/MAALIGN/RPS20/ret60/VOLRATIO/turnover/amount...）
    fin: PIT 财报指标 dict
    hist_pb/hist_pe: 滚动历史PB/PE序列（用于分位）
    权重: 基本面35 / 趋势35 / 情绪10 / 微观10 / 风控10
    """
    # ---- 基本面 35 ----
    fb = 0.0
    if fin and fin.get("np_yoy") is not None:
        np_y = fin["np_yoy"]; rev_y = fin.get("rev_yoy"); roe = fin.get("roe")
        # ①营收增速TTM
        fb += 5.0 * min(1.0, max(0.0, (rev_y if rev_y is not None else 0) / 30))
        # ②净利润增速TTM
        fb += 6.0 * min(1.0, max(0.0, np_y / 30))
        # ④PE分位 (120日滚动) —— 容忍成长龙头高估值，仅极端高位扣分 [代理标定]
        if hist_pe and fin.get("pe") and np.isfinite(fin["pe"]):
            pe_pct = (np.asarray(hist_pe) > fin["pe"]).mean()
            fb += 6.0 * (1.0 if pe_pct <= 0.70 else max(0.0, (1.0 - pe_pct) / 0.30))
        else:
            fb += 4.0
        # ⑤PB分位 —— 同上容忍 [代理标定]
        if hist_pb and fin.get("pb") and np.isfinite(fin["pb"]):
            pb_pct = (np.asarray(hist_pb) > fin["pb"]).mean()
            fb += 6.0 * (1.0 if pb_pct <= 0.70 else max(0.0, (1.0 - pb_pct) / 0.30))
        else:
            fb += 4.0
        # ⑥PEG —— 平滑三档 [代理标定]
        if fin.get("pe") and np.isfinite(fin["pe"]) and np.isfinite(np_y):
            peg = fin["pe"] / (np_y * 100) if np_y > 0 else np.nan
            fb += 6.0 if (np.isfinite(peg) and peg <= 1.5) else (4.0 if (np.isfinite(peg) and peg <= 2.5) else (2.0 if np.isfinite(peg) else 4.0))
        # ③一致预期调整 → PIT不可得, 中性偏正 4.5 [代理]
        fb += 4.5
    else:
        # 财报缺失期: 基本面给中性 0.65 权重分 [代理]
        fb = 35 * 0.65
    fb = min(35, fb)

    # ---- 趋势 35 ----
    tr = 0.0
    tr += 7.0 if row.get("MA60SLOPE") == 1 else (3.0 if row.get("MA60SLOPE") == 0 else 0.0)   # ⑦MA60方向
    tr += 7.0 if row.get("DEV60", -999) > 0 else 0.0                                          # ⑧价格/MA60位置
    al = row.get("MAALIGN", 0); tr += 7.0 if al == 3 else (4.0 if al == 2 else 0.0)            # ⑨均线排列
    rps = np.clip(row.get("RPS20", 50) / 100, 0, 1); tr += 7.0 * rps                          # ⑩20日RPS
    tr += 7.0 if row.get("ret60", -1) > 0 else 2.0                                            # ⑪60日涨幅
    tr = min(35, tr)

    # ---- 情绪 10 [代理: 量能/换手] ----
    em = 0.0
    em += 5.0 * np.clip(row.get("VOLRATIO", 1.0) / 2, 0, 1)      # 量比
    em += 5.0 * np.clip(row.get("turnover", 0) / 2, 0, 1)        # 换手率(2%满分, A股中位~1%) [标定]
    em = min(10, em)

    # ---- 微观 10 ----
    mi = 0.0
    mi += 5.0 * np.clip(np.log10(row.get("amount", 1e6) / 1e8 + 0.1) / 1.2, 0, 1)  # 成交额(亿)对数归一 [标定]
    mi += 5.0 * np.clip(row.get("VOLRATIO", 1.0) / 2.5, 0, 1)                        # 突破量比
    mi = min(10, mi)

    # ---- 风控 10 [代理: 财报质量, 缺失给中性] ----
    rc = 0.0
    if fin and fin.get("roe") is not None:
        rc += 3.0 * np.clip(fin["roe"] / 15, 0, 1)                       # ROE
        rc += 3.0 if fin.get("ocf_ps") and fin.get("eps") and fin["eps"] > 0 and (fin["ocf_ps"] / fin["eps"]) > 0.5 else 1.0  # 现金流/净利
        rc += 2.0 * np.clip((fin.get("gm") or 0) / 40, 0, 1)              # 毛利率
        rc += 2.0 * np.clip(1 - (fin.get("debt") or 0) / 60, 0, 1)        # 负债率
    else:
        rc = 7.0
    rc = min(10, rc)

    return min(100, fb + tr + em + mi + rc)


# ================= ETF 13 因子代理评分 =================

def etf_score(row: dict, est_pct: float = 0.6, prod_ok: bool = True, nav_pct: float = None) -> float:
    """ETF 综合得分（0-100），回测代理版
    Track B2 改造（2026-08-26）：新增估值分位维度 + 低波维度，降动量暴露
    B2 开关（env，subprocess 级生效）:
      BT_B2_ON        ="1"(默认) 启用新权重；="0" 回退 V1 行为（与历史基线一致，A/B对照）
      BT_B2_EST_W    估值分位权重      默认 25
      BT_B2_VOL_W    低波权重          默认 20
      BT_B2_MOM_SCALE 动量(RPS20/ret20)缩放 默认 0.5（降约一半）
    V1 旧权重: 估值30/趋势35/微观20/情绪15（估值用固定 est_pct 占位、无真实分位、无低波）
    B2 新权重: 估值分位 EST_W / 趋势30 / 低波 VOL_W / 微观15 / 情绪10（满分直设100，去归一hack）
    """
    # Track B2 ETF 评分优化 —— 2026-08-26 正式结案（证伪）：
    #   诊断(diag_b2a_wiring.py)与路径A复扫(sweep_b2a.py)证实：即便 BT_B2_MOM_SCALE=1.0（满动量），
    #   B2 结构(est_w=25/vol_w=20)仍把 ETF 评分系统性压在 70 门槛下→0 建仓→OOS 退化至 1.21%（hardFAIL）；
    #   失败系结构性（估值/低波权重过重），非动量缩放。线程关闭，开关保留为实验位；默认回退 V1（已验证基线 OOS 3.86%）。
    b2_on = os.environ.get("BT_B2_ON", "0") == "1"

    # ---------- V1 回退（BT_B2_ON=0），与历史基线完全一致 ----------
    if not b2_on:
        va = 30 * est_pct
        tr = 0.0
        tr += 8.0 if row.get("MA60SLOPE") == 1 else (3.0 if row.get("MA60SLOPE") == 0 else 0.0)
        tr += 8.0 if row.get("DEV60", -999) > 0 else 0.0
        al = row.get("MAALIGN", 0); tr += 7.0 if al == 3 else (4.0 if al == 2 else 0.0)
        rps = np.clip(row.get("RPS20", 50) / 100, 0, 1); tr += 6.0 * rps
        tr += 6.0 if row.get("ret60", -1) > 0 else 2.0
        tr = min(35, tr)
        mi = 0.0
        mi += 10.0 * np.clip(np.log10(row.get("amount", 1e6) / 1e8 + 0.1) / 1.2, 0, 1)
        mi += 10.0 * np.clip(row.get("turnover", 0) / 2, 0, 1)
        mi = min(20, mi)
        em = 0.0
        em += 8.0 * np.clip(row.get("VOLRATIO", 1.0) / 2, 0, 1)
        em += 7.0 * np.clip(row.get("ret20", 0) / 8, 0, 1)
        em = min(15, em)
        raw = va + tr + mi + em
        return min(100.0, raw * 100.0 / 91.0)

    # ---------- B2 新结构 ----------
    est_w = float(os.environ.get("BT_B2_EST_W", "25"))
    vol_w = float(os.environ.get("BT_B2_VOL_W", "20"))
    mom = float(os.environ.get("BT_B2_MOM_SCALE", "0.5"))
    w_tr, w_mi, w_em = 30.0, 15.0, 10.0

    # 估值分位（ETF 无 PE/PB，用净值120日分位代理；lower=cheaper=better，对标 PE_PCTL 逻辑）
    if nav_pct is None:
        nav_pct = row.get("NAV_PCTL_120", 50.0)
    va = est_w * (1.0 if nav_pct <= 70 else max(0.0, (100.0 - nav_pct) / 30.0))

    # 趋势（RPS20 受动量缩放；ret60 中期趋势保留）
    tr = 0.0
    tr += 8.0 if row.get("MA60SLOPE") == 1 else (3.0 if row.get("MA60SLOPE") == 0 else 0.0)
    tr += 8.0 if row.get("DEV60", -999) > 0 else 0.0
    al = row.get("MAALIGN", 0); tr += 7.0 if al == 3 else (4.0 if al == 2 else 0.0)
    rps = np.clip(row.get("RPS20", 50) / 100, 0, 1); tr += 6.0 * rps * mom
    tr += 6.0 if row.get("ret60", -1) > 0 else 2.0
    tr = min(35, tr) * (w_tr / 35.0)

    # 低波（VOL20A 20日年化波动率%，lower=better；30%→0分, 0%→满分）
    vol = row.get("VOL20A", 20.0)
    vol_s = max(0.0, (30.0 - vol) / 30.0)
    vol_block = vol_w * vol_s

    # 微观
    mi = 0.0
    mi += 10.0 * np.clip(np.log10(row.get("amount", 1e6) / 1e8 + 0.1) / 1.2, 0, 1)
    mi += 10.0 * np.clip(row.get("turnover", 0) / 2, 0, 1)
    mi = min(20, mi) * (w_mi / 20.0)

    # 情绪（ret20 受动量缩放）
    em = 0.0
    em += 8.0 * np.clip(row.get("VOLRATIO", 1.0) / 2, 0, 1)
    em += 7.0 * np.clip(row.get("ret20", 0) / 8, 0, 1) * mom
    em = min(15, em) * (w_em / 15.0)

    raw = va + tr + mi + em + vol_block
    # 归一化到100分制（权重和随 EST_W/VOL_W 变化时保持门槛语义稳定）
    norm = est_w + w_tr + vol_w + w_mi + w_em
    return min(100.0, raw * 100.0 / norm)


# ================= 层级裁决 =================

def layer1_stock(fin: dict | None) -> tuple[bool, str]:
    """层级1 个股财报硬过滤（PIT）。返回 (通过?, 原因)
    归母净利同比≥-12% / 营收同比≥-15% / 扣非同比≥-15% / 经营现金流/净利>0.5 /
    ROE>5% / 静态PB≤4(通用)≤6(高景气) / PEG≤1.5 / 上市>120天 / 流通市值50-500亿 / 日均成交额>5000万
    回测中流通市值、成交额在引擎层检查；此处检查财报类
    """
    if fin is None:
        return True, "财报未公告[代理通过]"
    np_y = fin.get("np_yoy"); rev_y = fin.get("rev_yoy"); npd = fin.get("np_ded_yoy")
    roe = fin.get("roe"); bps = fin.get("bps"); price = fin.get("price")
    eps = fin.get("eps"); ocf = fin.get("ocf_ps")
    if np_y is not None and np_y < -12:
        return False, f"归母净利同比{np_y:.1f}%<-12%"
    if rev_y is not None and rev_y < -15:
        return False, f"营收同比{rev_y:.1f}%<-15%"
    if npd is not None and npd < -15:
        return False, f"扣非净利同比{npd:.1f}%<-15%"
    if eps and eps > 0 and ocf is not None and (ocf / eps) <= 0.5:
        return False, f"经营现金流/净利{ocf/eps:.2f}≤0.5"
    if roe is not None and roe <= 5:
        return False, f"ROE={roe:.1f}%≤5%"
    if bps and price:
        pb = price / bps
        if pb > 6:
            return False, f"静态PB={pb:.1f}≥6(高景气上限)"
        if pb > 4:
            return False, f"静态PB={pb:.1f}≥4(通用上限)"
    return True, "通过"


def layer1_etf(row: dict, product_ok: bool = True, amount_min: float = 3000e4) -> tuple[bool, str]:
    """层级1 ETF产品硬过滤（回测简化：规模/成立时间通过预设，成交额实时检查）"""
    if not product_ok:
        return False, "产品健康度不达标[MISSING代理]"
    if row.get("amount", 0) < amount_min:
        return False, f"近20日均成交额{row.get('amount',0)/1e4:.0f}万<3000万"
    return True, "通过"


def layer35(row: dict) -> tuple[str, float, float, bool]:
    """层级3.5: 信号时效(R值) / 位置性价比(L20,H60) / PB膨胀预警
    R = (close-low20)/(high60-close)  [代理定义: 下方空间/上方空间]
    返回 (R_level, L20, H60, pb_ok)
    """
    r = row.get("R", np.nan)
    r_level = "A" if r <= 0.15 else ("B" if r <= 0.25 else "C")
    l20 = row.get("L20", np.nan); h60 = row.get("H60", np.nan)
    return r_level, l20, h60, True


# ================= 六灯 / 七灯 =================

def six_lights(row: dict, tre_state: str, obs_active: bool, s3_limit_ok: bool,
               n_hold: int, n_same_ind: int, beta: float, cap_limit: float,
               open_pct: float, r_level: str, tp_grade: str | None = None) -> tuple[bool, list[str]]:
    """个股六灯。返回 (全绿?, 每灯结果)  T-1数据 + T日开盘竞价(open_pct)
    tp_grade: 可选。非None且BT_TP_VARIANT≠0 时, 第2灯引用SSOT趋势位置档位（冗余2）
    """
    lights = []
    # 【去冗余·阶段2·冗余5】TRE状态闸门单一判定（SSOT）
    # 第1灯"大盘环境"与第6灯"TRE适配"原为逐字重复的 if-elif，合并为一次判定、两灯引用
    if obs_active:
        tre_gate_kind = "obs"
    elif tre_state == "S4":
        tre_gate_kind = "s4"
    elif tre_state == "S3":
        tre_gate_kind = "s3_ok" if s3_limit_ok else "s3_no"
    else:
        tre_gate_kind = "s12"
    # 第1灯 大盘中长期环境
    lights.append({
        "obs": "第1灯✅(观察通道视为绿灯)",
        "s4": "第1灯❌(S4禁止)",
        "s3_ok": "第1灯✅(S3有限建仓视为绿灯)",
        "s3_no": "第1灯❌(S3非有限建仓)",
        "s12": "第1灯✅",
    }[tre_gate_kind])
    # 第2灯 标的中长期趋势 —— 【去冗余·冗余2】SSOT趋势位置档位（V1-V3 A/B绿灯, V4仅A; 原逻辑保留在else）
    if TP_VARIANT != "0" and tp_grade is not None:
        ok2 = tp_grade == "A" if TP_VARIANT == "4" else tp_grade in ("A", "B")
    elif tre_state in ("S1", "S2"):
        ok2 = row.get("DEV60", -999) > 0  # 前收站稳MA60
    else:
        ok2 = row.get("close", 0) > row.get("low20", 0)  # 近10日收盘>近20日最低
    lights.append(f"第2灯{'✅' if ok2 else '❌'}" + (f"(趋势{tp_grade}档)" if tp_grade else ""))
    # 第3灯 开盘竞价 ≤2%
    ok3 = open_pct <= 2.0
    lights.append(f"第3灯{'✅' if ok3 else '❌'}(竞价{open_pct:.2f}%)")
    # 第4灯 信号时效性 R≤25%  (v5.0 #167: 个股通道 R值C级经MIN③降权, 不再判灯❌=否决)
    ok4 = r_level in ("A", "B") or (r_level == "C" and os.environ.get("BT_STOCKCHANNEL_V5", "0") == "1")
    lights.append(f"第4灯{'✅' if ok4 else '❌'}(信号{r_level}级{'·v5降权' if r_level=='C' else ''})")
    # 第5灯 组合风控 —— 【去冗余·冗余1】SSOT combo_balance_ok（六灯第5灯≡七灯第7灯 同源, 行为零变化）
    _dup1 = os.environ.get("BT_DUP1_VARIANT", "1")   # 默认1=SSOT合并; "0"=原内联(等价验证用)
    ok5 = (n_hold < 5) and (n_same_ind < 2) and (beta < 1.2) if _dup1 == "0" else combo_balance_ok(n_hold, n_same_ind, beta)
    lights.append(f"第5灯{'✅' if ok5 else '❌'}(持仓{n_hold}/同业{n_same_ind}/Beta{beta:.2f})")
    # 第6灯 TRE状态适配（引用同一 tre_gate_kind，见上方冗余5合并）
    lights.append({
        "obs": "第6灯✅(观察通道按S3观察模式)",
        "s4": "第6灯❌(S4禁止)",
        "s3_ok": "第6灯✅(S3有限建仓开放)",
        "s3_no": "第6灯❌",
        "s12": "第6灯✅",
    }[tre_gate_kind])
    all_green = all("❌" not in x for x in lights)
    return all_green, lights


def seven_lights(row: dict, tre_state: str, obs_active: bool, n_hold: int,
                 n_same_ind: int, beta: float, cap_limit: float,
                 open_pct: float, r_level: str, layer1_ok: bool,
                 wide_ok: bool, ma60_break90: int,
                 ind_etf: bool = False, tp_grade: str | None = None) -> tuple[bool, list[str]]:
    """ETF七灯。返回 (全绿?, 每灯结果)
    r_level 对 ETF 恒为"A"（信号时效=首次入选观察池日，入池即有效，见3.5）
    ind_etf: 行业ETF标记（R1 第5灯分层: 宽基≤1 / 行业≤3 / 观察通道豁免）
    tp_grade: 可选。宽基ETF（ind_etf=False）且BT_TP_VARIANT≠0 时, 第4灯引用SSOT趋势位置档位（冗余2）;
              行业ETF保留原dev>0（R3 z-score 修正独立, 本轮不合并）
    """
    lights = []
    dev = row.get("DEV60", -999); adx = row.get("ADX14", 0); slope = row.get("MA60SLOPE", 0)
    if obs_active:
        lights.append("第1灯✅(观察通道⚠️档作准入绿灯)")
    elif dev > 0 and adx >= 25:
        lights.append("第1灯✅")
    elif dev < 0 and adx >= 25 and slope < 0:
        lights.append("第1灯❌(破MA60+ADX高+MA60向下)")
    else:
        lights.append("第1灯⚠️(建仓减半)" + ("→✅观察通道" if obs_active else ""))
    # 【去冗余·阶段2·冗余4】第2灯引用层级1产品硬过滤结果（原与 layer1_etf 的 product_ok 重复）
    lights.append(f"第2灯{'✅' if layer1_ok else '❌'}(层级1产品硬过滤)")
    lights.append(f"第3灯{'✅' if wide_ok else '❌'}(宽基默认通过)")
    # 【去冗余·冗余2】宽基ETF第4灯引用SSOT趋势位置档位（V1-V3 A/B绿灯, V4仅A; 行业ETF保留R3 z-score）
    if TP_VARIANT != "0" and tp_grade is not None and not ind_etf:
        ok4 = tp_grade == "A" if TP_VARIANT == "4" else tp_grade in ("A", "B")
    else:
        ok4 = dev > 0  # 前收站稳MA60
    lights.append(f"第4灯{'✅' if ok4 else '❌'}" + (f"(趋势{tp_grade}档)" if tp_grade else ""))
    # R1 第5灯分层(受ind_etf即R1开关控制): 观察通道豁免 / 宽基≤1 / 行业≤3
    #   注: ind_etf=False(即R1未启用)时无豁免、统一≤1 —— 保持旧口径回归
    if obs_active and ind_etf:
        ok5 = True
        lights.append(f"第5灯✅(观察通道豁免: 近90日破位{ma60_break90}次)")
    else:
        k5 = 3 if ind_etf else 1
        ok5 = ma60_break90 <= k5
        lights.append(f"第5灯{'✅' if ok5 else '❌'}(近90日破位{ma60_break90}次, {'行业≤3' if ind_etf else '≤1'})")
    ok6 = True  # ETF信号时效=入选观察池日已过, 恒A级 [文档3.5]
    lights.append(f"第6灯{'✅' if ok6 else '❌'}(信号A级=入池有效)")
    # 七灯第7灯 组合风控 —— 【去冗余·冗余1】SSOT combo_balance_ok（与六灯第5灯同源）
    _dup1 = os.environ.get("BT_DUP1_VARIANT", "1")   # 默认1=SSOT合并; "0"=原内联(等价验证用)
    ok7 = (n_hold < 5) and (n_same_ind < 2) and (beta < 1.2) if _dup1 == "0" else combo_balance_ok(n_hold, n_same_ind, beta)
    lights.append(f"第7灯{'✅' if ok7 else '❌'}(持仓{n_hold}/同业{n_same_ind}/Beta{beta:.2f})")
    all_green = all("❌" not in x for x in lights)
    return all_green, lights


# ================= MIN 9项 + F-04 =================

def min_nine(row: dict, tre_state: str, obs_active: bool, s3_limit_ok: bool,
             fin: dict | None, pb_expand: float, ind_etf: bool = False,
             tp_grade: str | None = None) -> tuple[float, list[float]]:
    """MIN 运算 9 项（第七章表）。返回 (MIN结果%, [9项各%])
    row 需含: H60, R, L20, DEV60, ret20/ret60, VOLRATIO, close, low20
    ind_etf: R3 行业ETF z-score化 —— ②H60与⑥DEV60 改用滚动250日z分档（NaN回退绝对阈值）
    tp_grade: 可选。非None且BT_TP_VARIANT≠0 且非行业ETF 时, ②④⑥ 引用SSOT趋势位置档位（冗余2）
    """
    items = []
    # ①信号分级: 回测中观察池入选=信号A级 [代理]
    items.append(100.0)
    # ②H60区间 —— 【去冗余·冗余2】个股/宽基ETF引用SSOT趋势位置档位; 行业ETF R3 z-score保留
    h60 = row.get("H60", np.nan)
    if TP_VARIANT != "0" and tp_grade is not None and not ind_etf:
        items.append(_tp_min_value(tp_grade, TP_VARIANT, 2))
    elif ind_etf:
        hz = row.get("H60_Z", np.nan)
        if np.isfinite(hz):
            if hz <= 0.5: items.append(100.0)
            elif hz <= 1.0: items.append(50.0)
            else: items.append(25.0)
        elif h60 >= 5: items.append(100.0)
        elif 3 <= h60 < 5: items.append(50.0)
        else: items.append(25.0)
    elif h60 >= 5: items.append(100.0)
    elif 3 <= h60 < 5: items.append(50.0)
    else: items.append(25.0)
    # ③性价比 R  (v5.0 #167: 个股通道 R值降权而非否决 —— 破除无意义高门槛卡死)
    #   旧逻辑 R>0.25→0% 经 min() 拉成零仓位=变相硬否决; v5 改为阶梯降权, 仍参与但权重递减
    r = row.get("R", np.nan)
    _v5stock = (not ind_etf) and os.environ.get("BT_STOCKCHANNEL_V5", "0") == "1"
    if r <= 0.15: items.append(100.0)
    elif r <= 0.25: items.append(50.0)
    elif _v5stock:
        items.append(25.0 if r <= 0.35 else 10.0)   # 0.25-0.35→25%; >0.35→10% 降权而非否决
    else:
        items.append(0.0)
    # ④位置 L20/H60 —— 【去冗余·冗余2】合并引用SSOT档位（变体2保留C→0否决语义）
    if TP_VARIANT != "0" and tp_grade is not None and not ind_etf:
        items.append(_tp_min_value(tp_grade, TP_VARIANT, 4))
    else:
        l20 = row.get("L20", np.nan)
        if l20 <= 60 and h60 >= 3: items.append(100.0)
        elif (l20 <= 60) or (h60 >= 3): items.append(50.0)
        else: items.append(0.0)
    # ⑤TRE状态
    if obs_active: items.append(10.0)
    elif tre_state == "S1": items.append(100.0)
    elif tre_state == "S2": items.append(50.0)
    elif tre_state == "S3": items.append(20.0 if s3_limit_ok else 0.0)
    else: items.append(0.0)
    # ⑥价格偏离度 —— 【去冗余·冗余2】个股/宽基ETF引用SSOT趋势位置档位; 行业ETF R3 z-score保留
    dev = row.get("DEV60", 0)
    if TP_VARIANT != "0" and tp_grade is not None and not ind_etf:
        items.append(_tp_min_value(tp_grade, TP_VARIANT, 6))
    elif ind_etf:
        dz = row.get("DEV60_Z", np.nan)
        if np.isfinite(dz):
            if dz <= 1.0: items.append(100.0)
            elif dz <= 1.5: items.append(50.0)
            else: items.append(25.0)
        elif dev <= 10: items.append(100.0)
        elif dev <= 15: items.append(50.0)
        else: items.append(25.0)
    elif dev <= 10: items.append(100.0)
    elif dev <= 15: items.append(50.0)
    else: items.append(25.0)
    # ⑦景气度减半 [代理: 标的自身财报环比恶化且增速下降]
    if fin and fin.get("np_yoy") is not None and fin.get("prev_np_yoy") is not None \
       and fin["np_yoy"] < fin["prev_np_yoy"] and fin["np_yoy"] < 0:
        items.append(50.0)
    else:
        items.append(100.0)
    # ⑧择时质量 [代理: 回踩MA60+缩量+红盘]
    pullback = abs(row.get("close", 0) - row.get("MA60", 0)) / max(row.get("MA60", 1), 1e-6) <= 0.02 \
        or row.get("near_ma60_5d", False)
    shrink = row.get("VOLRATIO", 1) < 1.0
    red = row.get("pct_chg", 0) > 0
    n_ok = int(pullback) + int(shrink) + int(red)
    if n_ok == 3: items.append(100.0)
    elif n_ok == 2: items.append(50.0)
    else: items.append(25.0)
    # ⑨PB膨胀预警
    if pb_expand <= 1.3: items.append(100.0)
    elif pb_expand <= 1.5: items.append(50.0)
    else: items.append(0.0)
    return min(items), items


def f04(min_pct: float, atr_scale: float, liq_cap: float) -> float:
    """F-04: 最终可执行仓位% = MIN(MIN结果×ATR缩放, 12%初次, 流动性分层, 15%总硬上限); <3%放弃"""
    v = min(min_pct * atr_scale, 12.0, liq_cap, 15.0)
    return v if v >= 3.0 else 0.0


def combo_balance_ok(n_hold: int, n_same_ind: int, beta: float) -> bool:
    """SSOT 组合风控（附录E 冗余1）：六灯第5灯 ≡ 七灯第7灯 同一组合约束，消除两灯内联重复公式。

    约束：持仓数 < 5 且 同业持仓 < 2 且 组合Beta < 1.2。
    设计：原 six_lights(第5灯) 与 seven_lights(第7灯) 各自内联同一公式；现统一引用此函数（行为零变化）。
    注：run_backtest 组合约束层(L763 持仓<5/同业<2) 与 组合均衡(补丁②: 总仓位压缩/行业>30%) 为组合级执行点；
        第5灯/第7灯 的 per-symbol 组合风控（含 Beta<1.2 = 冗余6 的 8.4 Beta分级）现经此 SSOT 收敛，
        冗余6「仓位引擎」的 Beta分级并入。动态回撤阶梯(P12v6) 属离场引擎，按设计独立保留。
    """
    return (n_hold < 5) and (n_same_ind < 2) and (beta < 1.2)


# ================= 去冗余·冗余2：SSOT 趋势位置校验（2026-08-24 提前回测） =================

def trend_position(row: dict, tre_state: str) -> str:
    """SSOT 趋势位置校验（附录E 冗余2）：一次计算输出 A/B/C 三档，六灯第2灯 + MIN②④⑥ 引用。
    设计（统一三处阈值口径）：
      A 优: 站稳趋势位 且 L20≤60（非高位）且 H60≥3（上方空间够）
      C 差: 未站稳趋势位 或 (L20>60 且 H60<3)（高位且无空间）
      B 中: 其余（已站稳但位置/空间一项不满足）
    趋势位: S1/S2=DEV60>0（前收站稳MA60, 层级3核心）; S3/S4=close>low20（MA60冻结代理）
    消费映射: six_lights 第2灯(能否建仓) / seven_lights 第4灯 / min_nine ②④⑥(仓位档)
    本轮合并范围=个股+宽基ETF；行业ETF保留R3 z-score原逻辑（合并会污染已验证结论, 延后至阶段4）
    """
    dev = row.get("DEV60", -999)
    h60 = row.get("H60", np.nan)
    l20 = row.get("L20", np.nan)
    close = row.get("close", 0)
    low20 = row.get("low20", 0)
    if tre_state in ("S1", "S2"):
        stand = dev > 0
    else:
        stand = close > low20
    pos_ok = l20 <= 60
    room_ok = h60 >= 3
    if stand and pos_ok and room_ok:
        return "A"
    if (not stand) or ((not pos_ok) and (not room_ok)):
        return "C"
    return "B"


def _tp_min_value(grade: str, variant: str, item: int) -> float:
    """MIN②④⑥ 引用趋势位置档位的映射（按变体）：
    V1 温和提频: ②④⑥ C→25（④C 从原0%提为25%, 放行"高位无空间/破位"建仓）
    V2 标准:     ②⑥ C→25, ④ C→0（保留④"高位且无空间"否决语义）
    V3 严格:     ②④⑥ C→0
    V4 严格+第2灯仅A: 同V3（第2灯只认A档, 由 six_lights/seven_lights 消费）
    """
    if variant in ("3", "4"):
        return {"A": 100.0, "B": 50.0, "C": 0.0}[grade]
    if variant == "2":
        return {"A": 100.0, "B": 50.0, "C": 0.0 if item == 4 else 25.0}[grade]
    return {"A": 100.0, "B": 50.0, "C": 25.0}[grade]  # V1
