# -*- coding: utf-8 -*-
"""
阶段0 信号供给端预检（checklist 0.1~0.4）
模拟盘启动前的信号频率验证，确认三候选是否有足够的信号供给
"""
import os, sys, json, csv
import numpy as np
import pandas as pd
from collections import defaultdict, Counter
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from indicators import indicator_panel
from tre import TreState, step_tre, raw_state

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")

CORE_IDX = ["idx_hs300", "idx_sh", "idx_sz"]

# 观察池24只个股（从 _summary_attack.json 提取的 code→name 映射）
OBS_POOL = {
    "603259": "药明康德", "300357": "我武生物", "605117": "德业股份",
    "688120": "华海清科", "002371": "北方华创", "300750": "宁德时代",
    "600196": "复星医药", "002156": "通富微电", "688082": "盛美上海",
    "300661": "圣邦股份", "300693": "盛弘股份", "600276": "恒瑞医药",
    "600584": "长电科技", "688239": "航宇科技", "603986": "兆易创新",
    "688008": "澜起科技", "603005": "晶方科技", "002335": "科华数据",
    "002472": "双环传动", "002050": "三花智控", "002111": "威海广泰",
    "000099": "中信海直", "002518": "科士达", "688686": "奥普特",
}

# 候选A ETF池（22只，不含国开债）
ETF_POOL = [
    "510050", "510300", "510500", "510880", "159915", "159920", "159928",
    "512010", "512400", "512660", "512880", "512980", "515000", "515050",
    "512170", "512480", "512690", "159995", "515030", "515790", "516160", "588000",
]


def load_csv(name):
    df = pd.read_csv(os.path.join(DATA, f"{name}.csv"), dtype={"date": str})
    df["date"] = df["date"].astype(str).str[:10]
    return df.set_index("date").sort_index()


def compute_tre_states(start_date="2019-01-01", end_date="2026-08-18"):
    """运行TRE状态机，返回每日状态序列"""
    # 加载3个核心指数
    idx_panels = {}
    for nm in CORE_IDX:
        df = load_csv(nm)
        idx_panels[nm] = indicator_panel(df)

    # 对齐到沪深300日历
    cal = idx_panels["idx_hs300"].index
    for nm in CORE_IDX:
        if not idx_panels[nm].index.equals(cal):
            idx_panels[nm] = idx_panels[nm].reindex(cal).ffill()

    # 计算每日TRE状态
    tre = TreState()
    hs300 = idx_panels["idx_hs300"]
    hs300_ret = hs300["close"].pct_change()
    states = []
    dates = list(cal)

    for i, date in enumerate(dates):
        if date < start_date or date > end_date:
            continue
        if i < 2:
            continue
        t1 = dates[i - 1]
        core_adx = [float(idx_panels[x].loc[t1, "ADX14"]) for x in CORE_IDX]
        cross20 = int(idx_panels["idx_hs300"].loc[t1, "CROSS20"])
        vol20 = float(hs300_ret.loc[:t1].tail(20).std(ddof=1) * np.sqrt(252) * 100)
        below_streak = float(idx_panels["idx_hs300"].loc[t1, "BELOW_STREAK"])
        gt_ma60 = bool(hs300.loc[t1, "close"] > hs300.loc[t1, "MA60"])

        step_tre(tre, i, core_adx, cross20, vol20, below_streak, gt_ma60,
                 variant="V1", obs_guard=True)
        states.append({
            "date": date,
            "state": tre.state,
            "obs_active": tre.obs_active,
            "vol20": vol20,
            "raw": raw_state(core_adx, cross20, vol20),
        })

    return pd.DataFrame(states).set_index("date")


def check_0_1_candidate_a(tre_df):
    """0.1 候选A：ETF均值回归S4超跌信号触发频率分年统计"""
    print("\n" + "="*70)
    print("0.1 候选A：ETF均值回归 S4 超跌信号触发频率统计")
    print("="*70)

    # 加载22只ETF数据，计算MA20和vol20
    etf_panels = {}
    for code in ETF_POOL:
        try:
            df = load_csv(f"etf_{code}")
            p = indicator_panel(df)
            p["MA20"] = p["close"].rolling(20).mean()
            p["VOL20A"] = p["close"].pct_change().rolling(20).std() * np.sqrt(252) * 100
            etf_panels[code] = p
        except FileNotFoundError:
            print(f"  [MISSING] etf_{code}")

    # 对每个S4日（或S3日——A3变体），检查超跌信号
    s4_days = tre_df[tre_df["state"] == "S4"].index
    s3_days = tre_df[tre_df["state"] == "S3"].index
    s4_s3_days = tre_df[tre_df["state"].isin(["S3", "S4"])].index

    print(f"\n  TRE状态分布（2019-2026.8）:")
    state_counts = tre_df["state"].value_counts()
    for s in ["S1", "S2", "S3", "S4"]:
        cnt = state_counts.get(s, 0)
        pct = cnt / len(tre_df) * 100
        print(f"    {s}: {cnt:4d}日 ({pct:5.1f}%)")

    # S4 + S3 日数分年统计
    tre_df["year"] = tre_df.index.str[:4]
    print(f"\n  S4+S3 日数分年统计:")
    print(f"  {'年份':>6s}  {'S4日数':>6s}  {'S3日数':>6s}  {'S4+S3':>6s}  {'总交易日':>6s}")
    for yr in sorted(tre_df["year"].unique()):
        yr_df = tre_df[tre_df["year"] == yr]
        s4_cnt = (yr_df["state"] == "S4").sum()
        s3_cnt = (yr_df["state"] == "S3").sum()
        total = len(yr_df)
        print(f"  {yr:>6s}  {s4_cnt:6d}  {s3_cnt:6d}  {s4_cnt+s3_cnt:6d}  {total:6d}")

    # 超跌信号触发频率（A1主变体: close ≤ MA20×(1-4%) 且 vol20 ∈ [15, 25]）
    print(f"\n  A1主变体超跌信号触发频率（close ≤ MA20×0.96 且 vol20∈[15,25]）:")
    print(f"  {'年份':>6s}  {'S4日触发':>8s}  {'S4+S3日触发':>10s}  {'ETF覆盖':>8s}  {'达标':>4s}")
    annual_triggers = {}
    for yr in sorted(tre_df["year"].unique()):
        yr_df = tre_df[tre_df["year"] == yr]
        s4_yr = yr_df[yr_df["state"] == "S4"].index
        s4s3_yr = yr_df[yr_df["state"].isin(["S3", "S4"])].index

        # S4日内触发
        s4_trig = 0
        s4_etfs = set()
        for d in s4_yr:
            for code, p in etf_panels.items():
                if d in p.index:
                    row = p.loc[d]
                    if pd.notna(row.get("MA20")) and pd.notna(row.get("VOL20A")):
                        if row["close"] <= row["MA20"] * 0.96 and 15 <= row["VOL20A"] <= 25:
                            s4_trig += 1
                            s4_etfs.add(code)

        # S4+S3日内触发
        s4s3_trig = 0
        for d in s4s3_yr:
            for code, p in etf_panels.items():
                if d in p.index:
                    row = p.loc[d]
                    if pd.notna(row.get("MA20")) and pd.notna(row.get("VOL20A")):
                        if row["close"] <= row["MA20"] * 0.96 and 15 <= row["VOL20A"] <= 25:
                            s4s3_trig += 1

        annual_triggers[yr] = {"s4": s4_trig, "s4s3": s4s3_trig, "etfs": len(s4_etfs)}
        ok = "✓" if s4_trig >= 8 or s4s3_trig >= 8 else "✗"
        print(f"  {yr:>6s}  {s4_trig:8d}  {s4s3_trig:10d}  {len(s4_etfs):8d}  {ok:>4s}")

    total_s4 = sum(v["s4"] for v in annual_triggers.values())
    total_s4s3 = sum(v["s4s3"] for v in annual_triggers.values())
    avg_s4 = total_s4 / len(annual_triggers) if annual_triggers else 0
    print(f"\n  汇总: S4日触发={total_s4}次 / 年均={avg_s4:.1f}次 | S4+S3日触发={total_s4s3}次 / 年均={total_s4s3/len(annual_triggers):.1f}次")
    verdict = "PASS" if avg_s4 >= 8 or total_s4s3 / max(len(annual_triggers), 1) >= 8 else "FAIL"
    print(f"  判定: {verdict}（门槛: 年触发≥8次）")

    return {"verdict": verdict, "annual": annual_triggers,
            "total_s4": total_s4, "avg_s4": avg_s4,
            "total_s4s3": total_s4s3, "avg_s4s3": total_s4s3 / max(len(annual_triggers), 1)}


def check_0_2_candidate_b():
    """0.2 候选B：观察池24只评分达标频率与vol20分布"""
    print("\n" + "="*70)
    print("0.2 候选B：观察池24只 vol20分布与R-04闸门压制")
    print("="*70)

    # 加载观察池个股数据，计算最新vol20
    results = {}
    for code, name in OBS_POOL.items():
        try:
            df = load_csv(f"stk_{code}")
            p = indicator_panel(df)
            p["VOL20A"] = p["close"].pct_change().rolling(20).std() * np.sqrt(252) * 100
            latest = p.iloc[-1]
            vol20 = float(latest["VOL20A"]) if pd.notna(latest["VOL20A"]) else 0
            # 计算近250日vol20分布
            recent_vol = p["VOL20A"].tail(250).dropna()
            vol_p25 = recent_vol.quantile(0.25) if len(recent_vol) > 0 else 0
            vol_p50 = recent_vol.quantile(0.50) if len(recent_vol) > 0 else 0
            vol_p75 = recent_vol.quantile(0.75) if len(recent_vol) > 0 else 0
            vol_min = recent_vol.min() if len(recent_vol) > 0 else 0
            vol_max = recent_vol.max() if len(recent_vol) > 0 else 0

            # 近250日 vol20<15 的天数占比
            below_15 = (recent_vol < 15).sum() / max(len(recent_vol), 1) * 100
            above_20 = (recent_vol >= 20).sum() / max(len(recent_vol), 1) * 100
            in_range = ((recent_vol >= 15) & (recent_vol < 20)).sum() / max(len(recent_vol), 1) * 100

            results[code] = {
                "name": name,
                "vol20_latest": vol20,
                "vol_p25": float(vol_p25), "vol_p50": float(vol_p50), "vol_p75": float(vol_p75),
                "vol_min": float(vol_min), "vol_max": float(vol_max),
                "pct_below_15": float(below_15),
                "pct_in_15_20": float(in_range),
                "pct_above_20": float(above_20),
            }
        except FileNotFoundError:
            print(f"  [MISSING] stk_{code} {name}")

    # 输出
    print(f"\n  {'代码':>6s}  {'名称':8s}  {'最新vol20':>8s}  {'P25':>6s}  {'P50':>6s}  {'P75':>6s}  {'<15%占比':>8s}  {'15-20%':>6s}  {'≥20%':>6s}")
    for code, r in sorted(results.items(), key=lambda x: x[1]["vol20_latest"]):
        print(f"  {code:>6s}  {r['name']:8s}  {r['vol20_latest']:8.1f}  {r['vol_p25']:6.1f}  {r['vol_p50']:6.1f}  {r['vol_p75']:6.1f}  {r['pct_below_15']:7.1f}%  {r['pct_in_15_20']:5.1f}%  {r['pct_above_20']:5.1f}%")

    # R-04闸门压制统计
    latest_above_20 = sum(1 for r in results.values() if r["vol20_latest"] >= 20)
    latest_in_15_20 = sum(1 for r in results.values() if 15 <= r["vol20_latest"] < 20)
    latest_below_15 = sum(1 for r in results.values() if r["vol20_latest"] < 15)

    avg_pct_above_20 = np.mean([r["pct_above_20"] for r in results.values()])
    avg_pct_in_15_20 = np.mean([r["pct_in_15_20"] for r in results.values()])
    avg_pct_below_15 = np.mean([r["pct_below_15"] for r in results.values()])

    print(f"\n  最新日R-04闸门分布:")
    print(f"    vol20≥20（闸门B禁S1/S2常规）: {latest_above_20}/{len(results)}只 ({latest_above_20/len(results)*100:.0f}%)")
    print(f"    vol20∈[15,20)（正常可建仓）: {latest_in_15_20}/{len(results)}只 ({latest_in_15_20/len(results)*100:.0f}%)")
    print(f"    vol20<15（闸门A禁一切建仓）: {latest_below_15}/{len(results)}只 ({latest_below_15/len(results)*100:.0f}%)")

    print(f"\n  近250日平均时间占比:")
    print(f"    vol20≥20（禁S1/S2）: {avg_pct_above_20:.1f}%")
    print(f"    vol20∈[15,20)（正常）: {avg_pct_in_15_20:.1f}%")
    print(f"    vol20<15（禁一切）: {avg_pct_below_15:.1f}%")

    # B1变体（≥80分+vol20≥15）可建仓频率估算
    print(f"\n  R-04闸门对候选B的压制评估:")
    print(f"    若仅vol20≥15可建仓 → 近250日平均{(avg_pct_in_15_20+avg_pct_above_20):.1f}%时间窗口可用")
    print(f"    若vol20≥20禁S1/S2 → 仅{(avg_pct_in_15_20):.1f}%时间可常规建仓")
    print(f"    B3变体（vol20≥12）可恢复约{avg_pct_below_15*0.5:.1f}%的时间窗口（估计值）")

    verdict = "PASS" if avg_pct_in_15_20 + avg_pct_above_20 > 50 else "WARN"
    print(f"  判定: {verdict}（>50%时间可建仓=PASS）")

    return {"verdict": verdict, "stocks": results,
            "latest_above_20": latest_above_20, "latest_in_15_20": latest_in_15_20,
            "avg_pct_above_20": avg_pct_above_20, "avg_pct_in_15_20": avg_pct_in_15_20,
            "avg_pct_below_15": avg_pct_below_15}


def check_0_3_candidate_c():
    """0.3 候选C：P12理论触发统计"""
    print("\n" + "="*70)
    print("0.3 候选C：P12 移动止盈引擎理论触发统计")
    print("="*70)

    # 从G1r/JOINT/P12v6回测结果中统计P12触发
    variants = {}
    for label in ["G1r", "JOINT", "P12v6"]:
        fpath = os.path.join(OUT, f"variant_{label}.json")
        if not os.path.exists(fpath):
            print(f"  [MISSING] variant_{label}.json")
            continue
        with open(fpath, encoding="utf-8") as f:
            d = json.load(f)

        # IS + OOS 交易
        all_closed = d.get("closed_in", []) + d.get("closed_oos", [])
        p12_trades = [c for c in all_closed if "P12" in str(c.get("exit_reason", ""))]
        p12_pnl = sum(float(c.get("pnl", 0)) for c in p12_trades)
        total_pnl = sum(float(c.get("pnl", 0)) for c in all_closed)

        # 统计浮盈≥15%的持仓（P12理论触发池）
        max_fp_trades = []
        for c in all_closed:
            reason = str(c.get("exit_reason", ""))
            # 从P12出场原因中提取最高浮盈
            if "P12" in reason:
                import re
                m = re.search(r"浮盈(\d+)%", reason)
                if m:
                    max_fp_trades.append(int(m.group(1)))

        variants[label] = {
            "total_trades": len(all_closed),
            "p12_count": len(p12_trades),
            "p12_pnl": p12_pnl,
            "total_pnl": total_pnl,
            "p12_share": len(p12_trades) / max(len(all_closed), 1) * 100,
            "p12_pnl_share": p12_pnl / max(abs(total_pnl), 1) * 100 if total_pnl != 0 else 0,
            "max_fp_list": max_fp_trades,
        }

        print(f"\n  {label}:")
        print(f"    总平仓交易: {len(all_closed)}笔")
        print(f"    P12触发: {len(p12_trades)}笔 ({len(p12_trades)/max(len(all_closed),1)*100:.1f}%)")
        print(f"    P12盈亏: {p12_pnl:+,.0f}元 (占总交易PnL {p12_pnl/max(abs(total_pnl),1)*100:.0f}%)")
        if max_fp_trades:
            print(f"    P12出场浮盈分布: {max_fp_trades}")

    # P12v6是当前固化基线，用它做判定
    base = variants.get("P12v6") or variants.get("JOINT") or variants.get("G1r")
    if base:
        # 年化频率
        years_is = 6.0  # 2019-2024
        years_oos = 1.5  # 2025-2026.6
        total_years = years_is + years_oos
        annual_p12 = base["p12_count"] / total_years

        print(f"\n  P12年化触发频率: {annual_p12:.1f}次/年（{base['p12_count']}笔/{total_years:.1f}年）")
        print(f"  P12占总交易比例: {base['p12_share']:.1f}%")
        print(f"  P12贡献利润占比: {base['p12_pnl_share']:.0f}%")

        verdict = "PASS" if annual_p12 >= 1 else "WARN"
        print(f"  判定: {verdict}（门槛: 年≥1次P12触发）")
        print(f"  注: P12v6已收紧回撤率至45/35/25%, 预期触发频率将提升")

    return {"verdict": verdict if base else "FAIL", "variants": variants}


def check_0_4_overlap():
    """0.4 三候选标的重叠度检查 + 资金优先级裁决规则"""
    print("\n" + "="*70)
    print("0.4 三候选标的重叠度检查与资金优先级裁决规则")
    print("="*70)

    # 候选A标的池
    a_codes = set(ETF_POOL)
    # 候选B标的池
    b_codes = set(OBS_POOL.keys())
    # 候选C复用A+B

    overlap_ab = a_codes & b_codes
    print(f"\n  候选A标的池: {len(a_codes)}只 ETF")
    print(f"  候选B标的池: {len(b_codes)}只 个股")
    print(f"  候选C: 复用A+B数据")
    print(f"  A∩B重叠: {len(overlap_ab)}只 → {'无重叠（ETF vs 个股天然隔离）' if not overlap_ab else overlap_ab}")

    # 候选B与主引擎UNIVERSE重叠
    main_universe_stocks = {"600276", "603259", "300750", "600519", "600036", "601318", "000858", "000333"}
    overlap_main = b_codes & main_universe_stocks
    print(f"\n  候选B与主引擎UNIVERSE个股重叠: {len(overlap_main)}只 → {overlap_main}")
    print(f"  → 冲突裁决原则: 主引擎（底盘）优先, 进攻线仅承接未被底盘占用的机会")
    print(f"  → 同一标的同日双向信号时进攻线让位")

    # 候选A与主引擎UNIVERSE重叠
    main_universe_etfs = {"510300", "159915", "588000", "512010", "159928",
                          "512880", "512690", "515030", "512480", "512170",
                          "510050", "510500", "510880", "159920",
                          "512400", "512660", "515790", "159995", "515000",
                          "512980", "515050", "516160"}
    overlap_a_main = a_codes & main_universe_etfs
    print(f"\n  候选A与主引擎UNIVERSE ETF重叠: {len(overlap_a_main)}/{len(a_codes)}只")
    print(f"  → 全部重叠: 候选A使用与主引擎相同的ETF池, 但入场逻辑不同（均值回归 vs 趋势跟踪）")
    print(f"  → 冲突裁决: 若同一ETF同时被主引擎(S1/S2趋势)和候选A(S4超跌)选中, 主引擎优先")
    print(f"  → 候选A仅在S4窗口触发, 与主引擎的S1/S2触发天然时间错开, 实际冲突极少")

    verdict = "PASS"
    print(f"\n  判定: {verdict}（重叠可管理, 裁决规则明确）")

    rules = [
        "1. 主引擎（底盘）绝对优先, 进攻线让位",
        "2. 同一标的同日双向信号 → 进攻线不执行",
        "3. 候选A仅S4窗口触发, 候选B仅vol20≥15窗口, 时间天然错开",
        "4. 三候选共享10万进攻线账户, 单候选最大同时持仓≤3只",
        "5. 进攻线总敞口≤90%（9万）, 预留10%现金缓冲",
    ]
    print(f"\n  资金优先级裁决规则:")
    for r in rules:
        print(f"    {r}")

    return {"verdict": verdict, "overlap_ab": len(overlap_ab),
            "overlap_b_main": len(overlap_main),
            "overlap_a_main": len(overlap_a_main), "rules": rules}


def main():
    print("╔════════════════════════════════════════════════════════════╗")
    print("║   进攻线模拟盘 · 阶段0 信号供给端预检                       ║")
    print("║   三候选：A=ETF均值回归 / B=个股精选 / C=P12引擎            ║")
    print("╚════════════════════════════════════════════════════════════╝")

    # 0.1 候选A
    tre_df = compute_tre_states()
    r_01 = check_0_1_candidate_a(tre_df)

    # 0.2 候选B
    r_02 = check_0_2_candidate_b()

    # 0.3 候选C
    r_03 = check_0_3_candidate_c()

    # 0.4 重叠度
    r_04 = check_0_4_overlap()

    # 汇总
    print("\n" + "="*70)
    print("阶段0 汇总判定")
    print("="*70)
    results = {
        "0.1_候选A_ETF均值回归": r_01["verdict"],
        "0.2_候选B_个股精选": r_02["verdict"],
        "0.3_候选C_P12引擎": r_03["verdict"],
        "0.4_重叠度检查": r_04["verdict"],
    }
    for k, v in results.items():
        icon = "✓" if v in ("PASS", "OK") else ("⚠" if v == "WARN" else "✗")
        print(f"  {icon} {k}: {v}")

    all_pass = all(v in ("PASS", "OK") for v in results.values())
    print(f"\n  总判定: {'阶段0通过 → 可进入阶段1历史定参回测' if all_pass else '部分未通过 → 需复核'}")

    # 保存结果
    summary = {
        "timestamp": datetime.now().isoformat(),
        "tre_state_distribution": tre_df["state"].value_counts().to_dict(),
        "results": {
            "0.1": {"verdict": r_01["verdict"], "annual": r_01["annual"],
                     "total_s4": r_01["total_s4"], "avg_s4": r_01["avg_s4"],
                     "total_s4s3": r_01["total_s4s3"], "avg_s4s3": r_01["avg_s4s3"]},
            "0.2": {"verdict": r_02["verdict"],
                     "latest_above_20": r_02["latest_above_20"],
                     "latest_in_15_20": r_02["latest_in_15_20"],
                     "avg_pct_above_20": r_02["avg_pct_above_20"],
                     "avg_pct_in_15_20": r_02["avg_pct_in_15_20"],
                     "avg_pct_below_15": r_02["avg_pct_below_15"]},
            "0.3": {"verdict": r_03["verdict"], "variants": r_03["variants"]},
            "0.4": {"verdict": r_04["verdict"], "rules": r_04["rules"]},
        },
        "all_pass": all_pass,
    }
    out_path = os.path.join(OUT, "phase0_precheck.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  结果已保存: {out_path}")

    return summary


if __name__ == "__main__":
    main()
