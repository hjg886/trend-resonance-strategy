# -*- coding: utf-8 -*-
"""
sens_backtest.py —— 敏感性对照实验（[代理]标注）
主策略 B0 之外的三档对照，仅放宽层级1 个股财报硬过滤的 PB/ROE 阈值：
  B1: PB≤8(通用)/≤12(高景气), ROE>5%   —— 仅放宽PB
  B2: PB≤8/≤12, ROE>3%                 —— 放宽PB+ROE
  B3: 去除静态PB上限, ROE>3%            —— 最宽松（PB由MIN⑨膨胀预警独立约束）
其余规则（得分门槛/3.5/六灯七灯/MIN/熔断/组合约束）与 B0 完全一致。
输出: output/sens_B1.json / sens_B2.json / sens_B3.json
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
import run_backtest as rb


def make_layer1_sens(pb_ub, pb_ub_hi, roe_thr, drop_pb=False):
    """生成 sens 版 layer1_stock（签名与 scoring.layer1_stock 一致）"""
    def layer1_sens(fin):
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
        if roe is not None and roe <= roe_thr:
            return False, f"ROE={roe:.1f}%≤{roe_thr}%"
        if not drop_pb and bps and price:
            pb = price / bps
            if pb > pb_ub_hi:
                return False, f"静态PB={pb:.1f}≥{pb_ub_hi}(高景气上限)"
            if pb > pb_ub:
                return False, f"静态PB={pb:.1f}≥{pb_ub}(通用上限)"
        return True, "通过"
    return layer1_sens


def run_sens(label: str, layer1_sens):
    rb.layer1_stock = layer1_sens   # 替换 run_backtest 模块内的引用
    panels0, fins = rb.load_all()
    panels = rb.build_panels(panels0)
    panels = rb.add_pit_pb(panels, fins)
    days = list(panels["idx_hs300"].index)
    warm = [d for d in days if d >= "2018-06-01" and d < rb.PERIOD_IN[0]]
    res_in = rb.run_backtest(panels, fins, warm + [d for d in days if d >= rb.PERIOD_IN[0] and d <= rb.PERIOD_IN[1]], rb.PERIOD_IN, f"{label}样本内")
    res_oos = rb.run_backtest(panels, fins, [d for d in days if d >= rb.PERIOD_OOS[0] and d <= rb.PERIOD_OOS[1]], rb.PERIOD_OOS, f"{label}样本外")
    fn = f"output/sens_{label}.json"
    with open(os.path.join(rb.ROOT, fn), "w", encoding="utf-8") as fh:
        json.dump({"in": res_in, "oos": res_oos}, fh, ensure_ascii=False, indent=1, default=str)
    print(f"[{label}] in: final={res_in['final_equity']:.0f} buys={len(res_in['buys'])} closed={len(res_in['closed'])} "
          f"| oos: final={res_oos['final_equity']:.0f} buys={len(res_oos['buys'])} closed={len(res_oos['closed'])}")
    for b in res_in["buys"][:30]:
        print(f"   IN  BUY {b['date']} {b['code']} {b['reason']} score={b['score']:.0f} target={b['target']:.0f}% {b['tre']}")
    for b in res_oos["buys"][:30]:
        print(f"   OOS BUY {b['date']} {b['code']} {b['reason']} score={b['score']:.0f} target={b['target']:.0f}% {b['tre']}")


if __name__ == "__main__":
    print("=" * 70)
    print("B1: PB≤8/12, ROE>5%")
    run_sens("B1", make_layer1_sens(8.0, 12.0, 5.0))
    print("=" * 70)
    print("B2: PB≤8/12, ROE>3%")
    run_sens("B2", make_layer1_sens(8.0, 12.0, 3.0))
    print("=" * 70)
    print("B3: 去静态PB, ROE>3%")
    run_sens("B3", make_layer1_sens(999.0, 999.0, 3.0, drop_pb=True))
