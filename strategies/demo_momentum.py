"""
demo_momentum.py — 動量策略示例
==============================
這是一個示例策略，示範如何讓你自己的策略腳本整合到儀表板。

每個策略只需要實作一個 run() 函式，回傳以下格式的 dict：
    {
        "recommendation": str,   # 顯示在卡片上的建議文字，例如 "做多"、"做空"、"觀望"
        "signal": str,           # "LONG" / "SHORT" / "NEUTRAL"（控制顏色）
        "returns": pd.Series,    # 每日報酬率，DatetimeIndex，值為小數（0.01 = 1%）
        "details": str,          # （選填）顯示在圖表下方的說明文字
    }

把你真實的策略程式碼放到這個函式裡即可。
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta

try:
    import yfinance as yf
    _HAS_YF = True
except ImportError:
    _HAS_YF = False


def run() -> dict:
    """
    動量策略（示例）：
    - 追蹤標的過去 12 個月的報酬率
    - 若過去 1 個月報酬 > 0 → 做多訊號
    - 否則 → 觀望
    """

    # ── 1. 取得資料 ─────────────────────────────────────────────────────────
    ticker = "0050.TW"          # 台灣50 ETF
    end_date = date.today()
    start_date = end_date - timedelta(days=365 * 3)   # 取 3 年資料

    if _HAS_YF:
        try:
            raw = yf.download(
                ticker,
                start=start_date.isoformat(),
                end=end_date.isoformat(),
                progress=False,
                auto_adjust=True,
            )
            close = raw["Close"].squeeze().dropna()
        except Exception:
            close = _generate_synthetic(start_date, end_date, seed=42)
    else:
        close = _generate_synthetic(start_date, end_date, seed=42)

    # ── 2. 計算每日報酬 ──────────────────────────────────────────────────────
    returns = close.pct_change().dropna()

    # ── 3. 產生訊號 ──────────────────────────────────────────────────────────
    # 過去 20 個交易日的累積報酬
    recent_ret = (1 + returns.iloc[-20:]).prod() - 1 if len(returns) >= 20 else 0.0

    if recent_ret > 0.02:
        signal = "LONG"
        recommendation = "做多"
        detail_text = f"近 20 日累積報酬 {recent_ret*100:+.2f}%，動量偏多，維持做多部位。"
    elif recent_ret < -0.02:
        signal = "SHORT"
        recommendation = "做空"
        detail_text = f"近 20 日累積報酬 {recent_ret*100:+.2f}%，動量偏空，建議減碼或做空。"
    else:
        signal = "NEUTRAL"
        recommendation = "觀望"
        detail_text = f"近 20 日累積報酬 {recent_ret*100:+.2f}%，動能不明顯，暫時觀望。"

    return {
        "recommendation": recommendation,
        "signal": signal,
        "returns": returns,
        "details": detail_text,
    }


# ── 工具函式：生成合成資料（yfinance 不可用時的備案）──────────────────────────
def _generate_synthetic(start: date, end: date, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start=start, end=end)
    prices = 100.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, len(dates))))
    return pd.Series(prices, index=dates, name="Close")
