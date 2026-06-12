# -*- coding: utf-8 -*-
"""
轉折點(swing high / swing low)偵測。
這是趨勢線與形態學的共同基礎:先把「波峰、波谷」找出來,
後面所有形態都是在這些轉折點的「序列」上做圖形比對。

定義:第 i 根 K 棒是 swing high,若其 High 是 [i-w, i+w] 區間內的最大值(且唯一在中心)。
swing low 同理用 Low 取最小。w = PIVOT_WINDOW。
"""
import numpy as np


def find_pivots(high, low, window=5):
    """
    high, low: 1D numpy array
    回傳 (highs, lows):各為轉折點索引的 list(由左到右)。
    註:最右側 window 根 K 棒無法成為轉折(右邊資料不足),
        當下的「突破」另外用收盤價判斷,不靠轉折點。
    """
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    n = len(high)
    highs, lows = [], []
    for i in range(window, n - window):
        h_seg = high[i - window:i + window + 1]
        l_seg = low[i - window:i + window + 1]
        if high[i] == h_seg.max() and h_seg.argmax() == window:
            highs.append(i)
        if low[i] == l_seg.min() and l_seg.argmin() == window:
            lows.append(i)
    return highs, lows


def merged_pivots(high, low, window=5):
    """
    把波峰、波谷合併成一條依時間排序的轉折序列。
    回傳 list[dict]:{idx, price, kind}  kind in {'H','L'}
    """
    highs, lows = find_pivots(high, low, window)
    seq = [{"idx": i, "price": float(high[i]), "kind": "H"} for i in highs]
    seq += [{"idx": i, "price": float(low[i]), "kind": "L"} for i in lows]
    seq.sort(key=lambda d: d["idx"])
    return seq


def pivot_lows(seq):
    return [p for p in seq if p["kind"] == "L"]


def pivot_highs(seq):
    return [p for p in seq if p["kind"] == "H"]
