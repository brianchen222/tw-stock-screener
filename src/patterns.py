# -*- coding: utf-8 -*-
"""
形態學偵測(全部聚焦「做多」訊號)。

實作的做多形態:
  1. 雙重底 / W 底        (double_bottom)      —— 偵測最可靠
  2. 頭肩底               (head_shoulders_bottom)
  3. 複合頭肩底           (complex_hs_bottom)   —— 較易誤判,標記「需人工確認」
  4. 跳空向上 / 雙跳空    (gap_up)              —— 強勢動能輔助訊號

每個形態回傳統一結構:
  {
    name, confidence(0~1), breakout(bool),
    neckline,        # ((x0,y0),(x1,y1)) 或 None,頸線,用於畫圖
    markers,         # [(idx, price, label)] 關鍵點,用於畫圖
    target,          # 突破後的量度目標價(可None)
    note,            # 補充說明
  }

設計原則:寧可少報、不要亂報。所有形態都要求「結構成立 + 近期相關」,
且明確區分「已突破確認」與「形成中」。最終仍需人眼看 K 線圖確認。
"""
import numpy as np

import config
from . import pivots as pv


# ---------- 共用工具 ----------
def _breakout_index(close, start_idx, level, confirm=0.0):
    """從 start_idx+1 起,找第一根收盤 >= level*(1+confirm) 的位置;沒有回 -1。"""
    thr = level * (1 + confirm)
    for j in range(start_idx + 1, len(close)):
        if close[j] >= thr:
            return j
    return -1


def _clip01(x):
    return float(max(0.0, min(1.0, x)))


# ---------- 1. 雙重底 / W 底 ----------
def double_bottom(df, seq):
    high = df["High"].values
    low = df["Low"].values
    close = df["Close"].values
    n = len(df)
    last = n - 1
    lows = pv.pivot_lows(seq)
    if len(lows) < 2:
        return None

    best = None
    # 由近往遠找,優先回傳最近一組
    for ci in range(len(lows) - 1, 0, -1):
        c = lows[ci]
        if last - c["idx"] > config.DB_MAX_SEP:      # 第二底太舊,後面更舊不用看
            break
        for ai in range(ci - 1, -1, -1):
            a = lows[ai]
            sep = c["idx"] - a["idx"]
            if sep < config.DB_MIN_SEP:
                continue
            if sep > config.DB_MAX_SEP:
                break
            # 兩底等高
            diff = abs(c["price"] - a["price"]) / a["price"]
            if diff > config.DB_BOTTOM_TOL:
                continue
            # 頸線 = 兩底之間最高點
            seg_hi = high[a["idx"]:c["idx"] + 1]
            neck = float(seg_hi.max())
            neck_idx = a["idx"] + int(seg_hi.argmax())
            rebound = neck / max(a["price"], c["price"]) - 1
            if rebound < config.DB_MIN_REBOUND:
                continue
            # 底部不可被跌破:底2 之後若出現低於雙底的更低低點,代表 W 已失效(非真底),排除。
            seg_post = low[c["idx"] + 1:]
            if len(seg_post) and float(seg_post.min()) < min(a["price"], c["price"]) * 0.98:
                continue

            # 突破確認
            bj = _breakout_index(close, c["idx"], neck, config.BREAKOUT_CONFIRM)
            confirmed = bj != -1 and (last - bj) <= config.BREAKOUT_MAX_AGE
            forming = (not confirmed) and (last - c["idx"] <= 15) and \
                      (close[-1] < neck) and (close[-1] > min(a["price"], c["price"]))
            if not (confirmed or forming):
                continue
            # 突破後別追太高(已漲過量度目標一半以上就略過)
            tgt = neck + (neck - min(a["price"], c["price"]))
            if confirmed and close[-1] > neck + (tgt - neck) * 0.9:
                continue

            conf = 0.50
            conf += (config.DB_BOTTOM_TOL - diff) / config.DB_BOTTOM_TOL * 0.20
            conf += min(rebound, 0.15) / 0.15 * 0.20
            conf += 0.10 if confirmed else 0.0
            best = {
                "name": "雙重底/W底",
                "confidence": _clip01(conf),
                "breakout": confirmed,
                "neckline": ((float(a["idx"]), neck), (float(last), neck)),
                "markers": [
                    (a["idx"], a["price"], "底1"),
                    (neck_idx, neck, "頸線"),
                    (c["idx"], c["price"], "底2"),
                ],
                "target": round(tgt, 2),
                "note": "已突破頸線" if confirmed else "形成中(尚未突破頸線)",
            }
            break
        if best:
            break
    return best


# ---------- 2. 頭肩底 ----------
def head_shoulders_bottom(df, seq):
    high = df["High"].values
    low = df["Low"].values
    close = df["Close"].values
    n = len(df)
    last = n - 1
    lows = pv.pivot_lows(seq)
    if len(lows) < 3:
        return None

    best = None
    # 取最近、相鄰的三個低點(左肩、頭、右肩)
    for k in range(len(lows) - 1, 1, -1):
        rs, head, ls = lows[k], lows[k - 1], lows[k - 2]
        if last - rs["idx"] > config.DB_MAX_SEP:
            break
        if rs["idx"] - ls["idx"] < 2 * config.HS_MIN_SEP:
            continue
        # 頭要比兩肩低
        if not (head["price"] < ls["price"] * (1 - config.HS_HEAD_DROP) and
                head["price"] < rs["price"] * (1 - config.HS_HEAD_DROP)):
            continue
        # 兩肩等高
        if abs(ls["price"] - rs["price"]) / ls["price"] > config.HS_SHOULDER_TOL:
            continue
        # 結構不可被跌破:右肩之後若跌破頭部最低點,頭肩底已失效,排除
        seg_post = low[rs["idx"] + 1:]
        if len(seg_post) and float(seg_post.min()) < head["price"] * 0.98:
            continue
        # 頸線 = 左右兩段間的高點連線(可傾斜)
        p1_hi = high[ls["idx"]:head["idx"] + 1]
        p2_hi = high[head["idx"]:rs["idx"] + 1]
        x1 = ls["idx"] + int(p1_hi.argmax()); y1 = float(p1_hi.max())
        x2 = head["idx"] + int(p2_hi.argmax()); y2 = float(p2_hi.max())
        if x2 == x1:
            continue
        slope = (y2 - y1) / (x2 - x1)
        neck_now = y2 + slope * (last - x2)        # 頸線外推到目前
        # 突破:收盤站上頸線外推值,且近期內發生
        bj = -1
        for j in range(rs["idx"] + 1, n):
            if close[j] >= y2 + slope * (j - x2):
                bj = j
                break
        confirmed = bj != -1 and (last - bj) <= config.BREAKOUT_MAX_AGE
        forming = (not confirmed) and (last - rs["idx"] <= 15) and (close[-1] < neck_now)
        if not (confirmed or forming):
            continue

        shoulder_sym = 1 - abs(ls["price"] - rs["price"]) / ls["price"] / config.HS_SHOULDER_TOL
        conf = 0.50 + 0.20 * max(0, shoulder_sym) + (0.15 if confirmed else 0.0)
        height = ((y1 + y2) / 2) - head["price"]
        best = {
            "name": "頭肩底",
            "confidence": _clip01(conf),
            "breakout": confirmed,
            "neckline": ((float(x1), y1), (float(last), neck_now)),
            "markers": [
                (ls["idx"], ls["price"], "左肩"),
                (head["idx"], head["price"], "頭"),
                (rs["idx"], rs["price"], "右肩"),
            ],
            "target": round(neck_now + height, 2),
            "note": "已突破頸線" if confirmed else "形成中(尚未突破頸線)",
        }
        break
    return best


# ---------- 3. 複合頭肩底(多重肩) ----------
def complex_hs_bottom(df, seq):
    """
    複合頭肩底:中央一個最低「頭」,左右各有 >=2 個較高且大致對稱的肩。
    此形態主觀成分高、較易誤判,confidence 上限壓低並標註需人工確認。
    """
    high = df["High"].values
    low = df["Low"].values
    close = df["Close"].values
    n = len(df)
    last = n - 1
    lows = pv.pivot_lows(seq)
    if len(lows) < 5:
        return None

    # 找最近 90 根內的最低轉折當「頭」
    recent = [p for p in lows if last - p["idx"] <= config.DB_MAX_SEP]
    if len(recent) < 5:
        return None
    head = min(recent, key=lambda p: p["price"])
    left = [p for p in recent if p["idx"] < head["idx"]]
    right = [p for p in recent if p["idx"] > head["idx"]]
    if len(left) < 2 or len(right) < 2:
        return None
    # 結構不可被跌破:最右肩之後若跌破頭部最低點,複合頭肩底已失效,排除
    seg_post = low[right[-1]["idx"] + 1:]
    if len(seg_post) and float(seg_post.min()) < head["price"] * 0.98:
        return None

    drop = config.HS_HEAD_DROP
    if not all(p["price"] > head["price"] * (1 + drop) for p in left[-2:] + right[:2]):
        return None
    # 左右最外肩大致對稱
    if abs(left[0]["price"] - right[-1]["price"]) / left[0]["price"] > config.HS_SHOULDER_TOL * 1.6:
        return None

    neck = float(max(high[left[-1]["idx"]:right[0]["idx"] + 1].max(),
                     high[head["idx"]:right[0]["idx"] + 1].max()))
    bj = _breakout_index(close, right[-1]["idx"], neck, config.BREAKOUT_CONFIRM)
    confirmed = bj != -1 and (last - bj) <= config.BREAKOUT_MAX_AGE
    forming = (not confirmed) and (last - right[-1]["idx"] <= 15) and (close[-1] < neck)
    if not (confirmed or forming):
        return None

    markers = [(left[0]["idx"], left[0]["price"], "肩"),
               (head["idx"], head["price"], "頭"),
               (right[-1]["idx"], right[-1]["price"], "肩")]
    height = neck - head["price"]
    return {
        "name": "複合頭肩底",
        "confidence": _clip01(0.40 + (0.10 if confirmed else 0.0)),
        "breakout": confirmed,
        "neckline": ((float(left[0]["idx"]), neck), (float(last), neck)),
        "markers": markers,
        "target": round(neck + height, 2),
        "note": "複合形態,主觀成分高,務必人工複核 K 線圖",
    }


# ---------- 4. 跳空向上 / 雙跳空 ----------
def gap_up(df):
    high = df["High"].values
    low = df["Low"].values
    n = len(df)
    look = min(30, n - 1)
    gaps = []
    for i in range(n - look, n):
        if i <= 0:
            continue
        if low[i] > high[i - 1] * (1 + config.GAP_MIN):     # 向上跳空
            gaps.append(i)
    if not gaps:
        return None
    name = "雙跳空向上(連續跳空,強勢)" if len(gaps) >= 2 else "跳空向上(突破缺口)"
    return {
        "name": name,
        "confidence": _clip01(0.35 + 0.15 * min(len(gaps), 3)),
        "breakout": True,
        "neckline": None,
        "markers": [(g, float(low[g]), "跳空") for g in gaps],
        "target": None,
        "note": f"近 {look} 根內出現 {len(gaps)} 個向上跳空",
    }


# ---------- 5. 動能突破(箱型/旗形整理後突破,接近創新高)----------
def momentum_breakout(df):
    """
    『飆股動能突破』:價格在一段『緊密整理』後、且接近 6 個月高點(上方無套牢壓力),
    正貼著或剛突破整理區上緣。這是『小賠大賺』的理想結構——停損緊(整理下沿)、上檔開闊。
      進場 = 整理區上緣(突破點)
      停損 = 近 10 根最低(緊停損 => 賠小)
    """
    high = df["High"].values
    low = df["Low"].values
    close = df["Close"].values
    vol = df["Volume"].values
    n = len(df)
    BASE = 25
    if n < BASE + 12:
        return None
    last = n - 1

    res_region = high[n - BASE:n - 3]            # 整理區上緣(扣掉最近3根,避免用突破當根定義)
    if len(res_region) == 0:
        return None
    resistance = float(res_region.max())
    res_idx = (n - BASE) + int(res_region.argmax())
    stop_idx = (n - 10) + int(low[n - 10:].argmin())
    stop = float(low[stop_idx])
    if resistance <= stop:
        return None

    base_low = float(low[n - BASE:].min())
    tightness = (resistance - base_low) / base_low          # 整理越緊越好
    hi6 = float(high[max(0, n - 130):].max())               # 6 個月高
    near_high = resistance >= 0.90 * hi6                     # 上方開闊
    c = float(close[-1])
    dist = (c - resistance) / resistance                    # 距突破點

    if tightness > 0.22 or not near_high:
        return None
    if not (-0.06 <= dist <= 0.05):                         # 貼著/剛突破突破點
        return None

    vol_ok = True
    if n - 5 > n - BASE:
        vol_ok = vol[-5:].mean() >= vol[n - BASE:n - 5].mean() * 1.05

    conf = 0.50 + max(0.0, (0.22 - tightness)) / 0.22 * 0.30
    conf += 0.10 if near_high else 0.0
    conf += 0.10 if vol_ok else 0.0
    stage = "即將突破" if dist <= 0.01 else "剛突破"
    target = resistance + (resistance - base_low)           # 箱型量度(保守參考,實際讓它跑)
    return {
        "name": "動能突破",
        "confidence": _clip01(conf),
        "breakout": dist > 0.01,
        "neckline": ((float(n - BASE), resistance), (float(last), resistance)),
        "markers": [(res_idx, resistance, "壓力"), (stop_idx, stop, "停損低")],
        "target": round(target, 2),
        "entry": round(resistance, 2), "stop": round(stop, 2),
        "stage": stage, "dist_pct": round(dist * 100, 2),
        "near_high_pct": round((c - hi6) / hi6 * 100, 2),    # 距6月高(越接近0或正=越開闊)
        "tightness_pct": round(tightness * 100, 1),
        "note": f"整理{tightness*100:.0f}%緊,距6月高{(c-hi6)/hi6*100:+.1f}%",
    }


# ---------- 對外:跑全部形態 ----------
def detect_all(df):
    """回傳該檔命中的所有做多形態 list[dict]。"""
    seq = pv.merged_pivots(df["High"].values, df["Low"].values, config.PIVOT_WINDOW)
    found = []
    for fn in (double_bottom, head_shoulders_bottom, complex_hs_bottom):
        try:
            r = fn(df, seq)
        except Exception:
            r = None
        if r:
            found.append(r)
    try:
        g = gap_up(df)
    except Exception:
        g = None
    if g:
        found.append(g)

    # 頭肩底與複合頭肩底若同時命中,保留信心較高者,避免重複
    names = {f["name"] for f in found}
    if "頭肩底" in names and "複合頭肩底" in names:
        hs = next(f for f in found if f["name"] == "頭肩底")
        cx = next(f for f in found if f["name"] == "複合頭肩底")
        drop = cx if cx["confidence"] <= hs["confidence"] else hs
        found = [f for f in found if f is not drop]
    return found, seq
