# -*- coding: utf-8 -*-
"""
趨勢線偵測:上升支撐、下降阻力、雙軌道(channel)、橫向。
做法:用最近數個同向轉折點做最小平方擬合,計算斜率與「觸碰次數」,
再依斜率方向與目前收盤位置,轉成「做多相關」的訊號。

回傳的每條線都附帶兩個端點 (idx, price),方便在 K 線圖上畫線。
"""
import numpy as np

import config
from . import pivots as pv


def _fit_line(points, last_idx, tol):
    """
    points: list[dict] (轉折點,需 idx/price),用最近 TREND_PIVOTS 個。
    回傳 dict: slope, intercept, touches, segment=((x0,y0),(x1,y1)) 或 None。
    """
    pts = points[-config.TREND_PIVOTS:]
    if len(pts) < 2:
        return None
    xs = np.array([p["idx"] for p in pts], dtype=float)
    ys = np.array([p["price"] for p in pts], dtype=float)
    slope, intercept = np.polyfit(xs, ys, 1)

    # 觸碰次數:所有(不只擬合用的)同類轉折點離線 <= tol 的個數
    touches = 0
    for p in points:
        line_y = slope * p["idx"] + intercept
        if line_y > 0 and abs(p["price"] - line_y) / line_y <= tol:
            touches += 1

    x0 = xs[0]
    seg = ((float(x0), float(slope * x0 + intercept)),
           (float(last_idx), float(slope * last_idx + intercept)))
    return {"slope": float(slope), "intercept": float(intercept),
            "touches": int(touches), "segment": seg}


def _slope_pct_per_bar(line, ref_price):
    """斜率換算成每根 K 棒的百分比變化,用來判斷方向(避免受股價絕對值影響)。"""
    if ref_price <= 0:
        return 0.0
    return line["slope"] / ref_price


def detect_trendlines(df, seq=None):
    """
    df: OHLCV DataFrame。seq: merged_pivots 結果(可省,會自行計算)。
    回傳 dict:
      signals: list[str]  做多相關趨勢訊號(中文)
      lines:   list[dict] 要畫的線 {label, segment, color}
    """
    high = df["High"].values
    low = df["Low"].values
    close = df["Close"].values
    last_idx = len(df) - 1
    last_close = float(close[-1])
    ref = float(np.mean(close[-60:]))

    if seq is None:
        seq = pv.merged_pivots(high, low, config.PIVOT_WINDOW)
    lows = pv.pivot_lows(seq)
    highs = pv.pivot_highs(seq)

    signals, lines = [], []
    FLAT = 0.0015  # 每根 < 0.15% 視為橫向

    # ---- 支撐線(用低點) ----
    sup = _fit_line(lows, last_idx, config.TREND_TOUCH_TOL) if len(lows) >= 2 else None
    if sup and sup["touches"] >= 2:
        sp = _slope_pct_per_bar(sup, ref)
        sup_y_now = sup["slope"] * last_idx + sup["intercept"]
        above = last_close >= sup_y_now * 0.98  # 收盤仍在支撐附近或之上
        if sp > FLAT and above:
            signals.append(f"上升支撐(觸碰{sup['touches']}次,趨勢向上)")
            lines.append({"label": "上升支撐", "segment": sup["segment"], "color": "#2ca02c"})
        elif abs(sp) <= FLAT and above:
            signals.append(f"橫向支撐(箱型底,觸碰{sup['touches']}次)")
            lines.append({"label": "橫向支撐", "segment": sup["segment"], "color": "#2ca02c"})

    # ---- 阻力線(用高點) ----
    res = _fit_line(highs, last_idx, config.TREND_TOUCH_TOL) if len(highs) >= 2 else None
    if res and res["touches"] >= 2:
        rp = _slope_pct_per_bar(res, ref)
        res_y_now = res["slope"] * last_idx + res["intercept"]
        broke = last_close > res_y_now  # 收盤突破阻力
        if rp < -FLAT:
            lines.append({"label": "下降阻力", "segment": res["segment"], "color": "#d62728"})
            if broke:
                signals.append("下降阻力突破(由空翻多)")
        elif abs(rp) <= FLAT:
            lines.append({"label": "橫向阻力", "segment": res["segment"], "color": "#d62728"})
            if broke:
                signals.append("橫向壓力突破(箱型突破)")

    # ---- 雙軌道(channel):上下軌斜率同向且接近平行 ----
    if sup and res and sup["touches"] >= 2 and res["touches"] >= 2:
        sp = _slope_pct_per_bar(sup, ref)
        rp = _slope_pct_per_bar(res, ref)
        if sp > FLAT and rp > FLAT and abs(sp - rp) < 0.002:
            signals.append("上升雙軌道(平行通道,順勢做多)")
            # 把上下兩條平行軌都畫出來(上緣阻力為上升,原阻力分支不會畫到)
            if not any(l["label"].startswith("上升支撐") or "下緣" in l["label"]
                       for l in lines):
                lines.append({"label": "軌道下緣(上升支撐)",
                              "segment": sup["segment"], "color": "#2ca02c"})
            lines.append({"label": "軌道上緣(上升阻力)",
                          "segment": res["segment"], "color": "#d62728"})

    return {"signals": signals, "lines": lines}
