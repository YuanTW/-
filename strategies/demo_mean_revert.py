"""
demo_mean_revert.py — 均值回歸策略示例
=======================================
示例策略 2：使用布林通道 (Bollinger Bands) 偵測超買/超賣。

同樣只需實作 run() → dict，格式與 demo_momentum.py 相同。
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
    均值回歸策略（示例）：
    - 布林通道 (20 日 MA ± 2σ)
    - 價格低於下軌 → 做多（期待反彈）
    - 價格高於上軌 → 做空（期待回落）
    - 其他 → 觀望
    """

    # ── 1. 取得資料 ─────────────────────────────────────────────────────────
    ticker = "SPY"              # S&P 500 ETF
    end_date = date.today()
    start_date = end_date - timedelta(days=365 * 3)

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
            close = _generate_synthetic(start_date, end_date, seed=99)
    else:
        close = _generate_synthetic(start_date, end_date, seed=99)

    # ── 2. 計算每日報酬 ──────────────────────────────────────────────────────
    returns = close.pct_change().dropna()

    # ── 3. 布林通道訊號 ──────────────────────────────────────────────────────
    window = 20
    if len(close) >= window:
        ma  = close.rolling(window).mean()
        std = close.rolling(window).std()
        upper = ma + 2 * std
        lower = ma - 2 * std

        last_close = close.iloc[-1]
        last_upper = upper.iloc[-1]
        last_lower = lower.iloc[-1]
        last_ma    = ma.iloc[-1]

        pct_from_ma = (last_close - last_ma) / last_ma * 100

        if last_close < last_lower:
            signal = "LONG"
            recommendation = "做多"
            detail_text = (
                f"價格 {last_close:.2f} 跌破布林下軌 {last_lower:.2f}，"
                f"偏離均線 {pct_from_ma:+.1f}%，超賣訊號，布局多單。"
            )
        elif last_close > last_upper:
            signal = "SHORT"
            recommendation = "做空"
            detail_text = (
                f"價格 {last_close:.2f} 突破布林上軌 {last_upper:.2f}，"
                f"偏離均線 {pct_from_ma:+.1f}%，超買訊號，考慮減碼。"
            )
        else:
            signal = "NEUTRAL"
            recommendation = "觀望"
            detail_text = (
                f"價格 {last_close:.2f} 在布林通道內（{last_lower:.2f}–{last_upper:.2f}），"
                f"偏離均線 {pct_from_ma:+.1f}%，尚無明確訊號。"
            )
    else:
        signal = "NEUTRAL"
        recommendation = "觀望"
        detail_text = "資料不足，無法計算布林通道。"

    return {
        "recommendation": recommendation,
        "signal": signal,
        "returns": returns,
        "details": detail_text,
    }


def _generate_synthetic(start: date, end: date, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start=start, end=end)
    # 加入均值回歸特性（OU process）
    x = np.zeros(len(dates))
    for i in range(1, len(dates)):
        x[i] = x[i-1] * 0.97 + rng.normal(0, 0.015)
    prices = 450.0 * np.exp(np.cumsum(rng.normal(0.0004, 0.008, len(dates))) + x * 0.1)
    return pd.Series(prices, index=dates, name="Close")
