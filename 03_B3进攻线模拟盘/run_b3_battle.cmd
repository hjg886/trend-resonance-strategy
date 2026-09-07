@echo off
chcp 65001 >nul
:: ============================================================
:: B3 进攻线 · 实战一键启动器（2026-09-07 改造：统一72池单通道）
:: 用途: 刷新数据 → 主引擎环境面板 → B3 72只信号单
:: 数据: 回测/data/*.csv（refresh 经 westockdata npx 联网增量刷新, 72池动态读 cand_meta）
:: 依赖: 受管 venv python + node(npx) 已在本机就绪
:: 说明: scan_b3_daily.py(24池) 已退休, B3信号单.py(72池 cand_meta) 为唯一日度扫描通道
:: ============================================================
cd /d "E:\fnOS\文档\证券\中线趋势共振策略"
set VENV=C:\Users\hanji\.workbuddy\binaries\python\envs\tre_backtest\Scripts\python.exe

echo.
echo ===== [1/3] 刷新 B3 模拟盘数据（指数 + B3 72池个股 + 现金ETF 159650）=====
%VENV% 回测\scripts\refresh_sim_data.py
echo [1/3] 完成 → 数据应更新至最近交易日

echo.
echo ===== [2/3] 主引擎环境面板（R-04双闸门/BREADTH/TRE/可建仓窗口）=====
%VENV% 回测\scripts\scan_env_daily.py
echo [2/3] 完成 → output/env_daily_scan_*.json

echo.
echo ===== [3/3] B3 72只信号单（cand_meta 池, SCORE_MIN=73, 含市场状态/闸门/TRE）=====
%VENV% 03_B3进攻线模拟盘\B3信号单.py
echo [3/3] 完成

echo.
echo ===== 实战信号已生成 =====
echo 下一步: 融合 [2]主引擎窗口 + [3]B3信号 → 若"B3信号≥73 且 主引擎窗口开放(或B3独立窗口开放)"
echo         → 按台账(7%%/笔,最多5笔,总仓≤25%%,止损10%%,时间止损30日,P12 run档)次日开盘模拟成交
echo 归档: 主引擎/信号 JSON 在 回测/output/ ; 复盘归档见 每日执行记录/
echo.
pause
