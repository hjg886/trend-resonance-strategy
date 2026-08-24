# -*- coding: utf-8 -*-
"""简化第十七章：①策略已加载确认语(800字→150字)；②职责7/8去冗余长标注收敛。"""
import io, os, shutil, sys

P = r"E:\fnOS\文档\证券\中线趋势共振策略\中线趋势共振策略 v4.7-R10 回测驱动重构版（1+2架构）完整补齐版.txt"
BAK = P + ".bak_20260821_ch17"
if not os.path.exists(BAK):
    shutil.copy2(P, BAK)
    print(f"[BAK] {BAK}")

with io.open(P, "r", encoding="utf-8") as f:
    lines = f.read().splitlines(keepends=True)

# 校验锚点（避免行号漂移导致改错）
assert "执行六灯/七灯买入校验" in lines[1041], "行1042锚点不符"
assert "执行TRE趋势状态识别引擎" in lines[1042], "行1043锚点不符"
assert "策略已加载" in lines[1077], "行1078锚点不符"

lines[1041] = ("7. 执行六灯/七灯买入校验，强制先展示层级1/2/3/3.5裁决结果（F-02）；"
               "ETF七灯第2灯直接引用层级1产品硬过滤结果。\n")

lines[1042] = ("8. 执行TRE趋势状态识别引擎（S1/S2/S3/S4，状态包一次判定、六灯第1/6灯与MIN⑤统一引用），"
               "S3/S4冻结MA60破位清仓，S3有限建仓（Top3+85分，20%仓位）；"
               "S4观察通道（F-30/F-32/F-33：10%试探仓、升级/失效退出），观察通道为弱势期唯一进攻窗口（R-07）。\n")

lines[1077] = ("策略已加载（v4.7-R10 回测驱动重构版）。1+2架构（主引擎v4.5-R1 + P53 ETF/组合均衡/自动降档三补丁）"
               "+ 重构层R-01~R-10 + 融合裁决F-01~F-35 全部就绪；P0-P12/E-P0.0~E-P12离场、六灯/七灯、MIN9项、"
               "盘中熔断、健康度仪表盘就绪。⚠️ 回测未达标（IS年化2.97%/OOS年化4.02%<6%），禁止实盘；"
               "主引擎防守定位，B3进攻线（OOS 13.15%，09-01起模拟盘）为唯一收益源，以模拟盘对照运行。\n")

with io.open(P, "w", encoding="utf-8", newline="") as f:
    f.write("".join(lines))
print("[OK] 第十七章已简化：策略已加载确认语 + 职责7/8去冗余标注")
print("DONE")
