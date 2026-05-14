"""
strategy_template.py — 新增策略的模板
======================================
【使用說明】
1. 複製這個檔案，改成你的策略名稱，例如 my_rsi_strategy.py
2. 在 run() 裡面貼上你的策略程式碼
3. 確保 run() 回傳正確格式的 dict
4. 在 app.py 的 STRATEGY_REGISTRY 裡新增一行：
       {"id": "my_rsi", "name": "我的 RSI 策略", "module": "strategies.my_rsi_strategy"},
5. 推送到 GitHub，儀表板會自動更新！

【run() 回傳格式】
    {
        "recommendation": str,   # 顯示在卡片上，例如 "做多"、"做空"、"觀望"
        "signal": str,           # "LONG"（綠）/ "SHORT"（紅）/ "NEUTRAL"（黃）
        "returns": pd.Series,    # 每日報酬率（小數），index 為 DatetimeIndex
        "details": str,          # （選填）顯示在圖表下方的分析說明
    }

【returns 格式範例】
    2023-01-03    0.0123    # 1.23%
    2023-01-04   -0.0045    # -0.45%
    2023-01-05    0.0078    # 0.78%
    dtype: float64

    可以直接用 close.pct_change().dropna() 取得。
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta


def run() -> dict:
    """
    在這裡放你的策略程式碼。
    """

    # ── 範例：用合成資料模擬 ─────────────────────────────────────────────────
    # 實際使用時，把這段換成你的資料抓取 + 策略邏輯
    end_date = date.today()
    start_date = end_date - timedelta(days=365 * 2)
    dates = pd.bdate_range(start=start_date, end=end_date)
    rng = np.random.default_rng(seed=123)
    returns = pd.Series(rng.normal(0.0005, 0.015, len(dates)), index=dates)

    # ── 你的訊號判斷邏輯 ─────────────────────────────────────────────────────
    signal = "NEUTRAL"
    recommendation = "觀望"
    details = "這是模板策略，請替換成你自己的邏輯。"

    return {
        "recommendation": recommendation,
        "signal": signal,
        "returns": returns,
        "details": details,
    }
