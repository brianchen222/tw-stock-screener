# -*- coding: utf-8 -*-
"""
量價進場時機偵測(帶量突破盤整的三個最佳時機)。

理念:盤整區會把沒信心的籌碼洗掉,帶量突破時留下的籌碼有共識,主力拉抬省力、漲幅大。
三個最佳進場時機:
  1. 盤整後帶量突破前高   → 假突破少、空間大
  2. 回測均線(MA20/MA60)不破 → 低風險補倉
  3. 量能潮剛啟動、5MV 剛翻揚 → 波段最早點
回傳布林訊號 + 細節,純資訊/可當篩選,不影響原本形態偵測。
"""
import numpy as np


def _sma(arr, n):
    """移動平均序列(長度 = len-n+1)。"""
    if len(arr) < n:
        return None
    return np.convolve(arr, np.ones(n) / n, mode="valid")


def entry_timing_signals(df):
    close = df["Close"].values.astype(float)
    high = df["High"].values.astype(float)
    vol = df["Volume"].values.astype(float)
    n = len(df)
    out = {
        "breakout_high": False,   # 帶量突破前高
        "pullback_ma": False,     # 回測均線不破
        "volume_surge": False,    # 5MV 剛翻揚
        "ma_label": None,         # 回測的是 MA20 還是 MA60
        "vol_ratio": None,        # 近量 / 20日均量
    }
    if n < 70:
        return out

    c = close[-1]
    vma20 = float(vol[-20:].mean())
    out["vol_ratio"] = round(float(vol[-3:].mean()) / vma20, 2) if vma20 > 0 else None

    # ---- 1. 盤整後帶量突破前高 ----
    # 前高 = 近 60 根(扣最近 3 根,避免用突破當根)最高;突破 + 近量放大 1.5 倍
    prior_high = float(high[n - 60:n - 3].max())
    recent_vol = float(vol[-3:].mean())
    if prior_high > 0 and c >= prior_high and vma20 > 0 and recent_vol >= 1.5 * vma20:
        out["breakout_high"] = True

    # ---- 2. 回測均線(MA20/MA60)不破 ----
    # 均線上彎 + 現價站在均線上、且貼近(回測,4% 內)
    ma20 = _sma(close, 20)
    ma60 = _sma(close, 60)

    def near_hold(ma):
        if ma is None or len(ma) < 7:
            return False
        now, prev = float(ma[-1]), float(ma[-6])
        rising = now > prev                       # 均線上彎
        near = now <= c <= now * 1.04             # 站上且回測在 4% 內
        return rising and near

    if near_hold(ma20):
        out["pullback_ma"] = True
        out["ma_label"] = "MA20"
    elif near_hold(ma60):
        out["pullback_ma"] = True
        out["ma_label"] = "MA60"

    # ---- 3. 量能潮剛啟動、5MV 剛翻揚 ----
    # 5日均量上彎(翻揚)+ 近期剛站上 20日均量(量能潮啟動)
    vol5 = _sma(vol, 5)
    vol20 = _sma(vol, 20)
    if vol5 is not None and vol20 is not None and len(vol5) >= 4 and len(vol20) >= 4:
        v5_now, v5_prev = float(vol5[-1]), float(vol5[-3])
        v20_now, v20_prev = float(vol20[-1]), float(vol20[-3])
        rising5 = v5_now > v5_prev                          # 5MV 翻揚
        crossed = v5_now > v20_now and v5_prev <= v20_prev  # 剛站上 20日均量
        if rising5 and crossed:
            out["volume_surge"] = True

    return out
