# -*- coding: utf-8 -*-
"""
資金管理 / 風險控管模組(實作使用者的進場-停損-口數-加碼公式)。

核心原則:先有停損價,才有進場價;用「風險金額 = 投資資金 x 風險%」回推口數,
讓單筆最大虧損不超過設定比例。獲利後依「無風險加碼」公式計算可加碼口數。

單位:台股一張 = SHARES_PER_LOT(1000)股。下面的「口數」即「張數」。
所有金額單位為 NT$。
"""
import math

import config

LOT = config.SHARES_PER_LOT


# ---------- 1. 決定進場價 / 停損價 ----------
def determine_entry_stop(df, patterns):
    """
    依規則決定進場價、停損價:
      - 有向上跳空缺口 -> 進場 = 缺口上緣(跳空當根 Low)、停損 = 缺口下緣(前一根 High)
      - 否則用形態     -> 進場 = 頸線突破價、停損 = 形態支撐(最後一個結構低點:
                          W底第二底 / 頭肩底右肩 / 複合頭肩底右肩)
    回傳 dict{entry, stop, source, basis} 或 None。
    """
    high = df["High"].values
    low = df["Low"].values
    last_close = float(df["Close"].iloc[-1])

    # (a) 跳空缺口優先 —— 但缺口必須仍是「支撐」:上緣需在現價之下(價格站在缺口之上)。
    #     若缺口已被跌破(上緣高於現價),它變成上方壓力,不可當做多進場價,跳過。
    gap_p = next((p for p in patterns if "跳空" in p["name"]), None)
    if gap_p and gap_p.get("markers"):
        for (g, _p, _lab) in reversed(gap_p["markers"]):   # 由近往遠找仍具支撐的缺口
            g = int(g)
            if g < 1:
                continue
            entry = float(low[g])                # 上緣
            stop = float(high[g - 1])            # 下緣
            if entry > stop and entry <= last_close:   # 缺口在現價之下=有效支撐
                return {"entry": round(entry, 2), "stop": round(stop, 2),
                        "source": "跳空缺口",
                        "basis": f"缺口上緣{entry:.2f}/下緣{stop:.2f}(支撐)"}

    # (b) 形態支撐
    bottoms = [p for p in patterns
               if p["name"] in ("雙重底/W底", "頭肩底", "複合頭肩底") and p.get("neckline")]
    if bottoms:
        # 取可靠度最高的一個
        best = max(bottoms, key=lambda p: p.get("confidence", 0))
        entry = float(best["neckline"][1][1])         # 頸線在當前的位置 = 突破價
        # 最後一個 marker = 最右側結構低點(底2 / 右肩)
        stop = float(best["markers"][-1][1])
        if entry > stop:
            return {"entry": round(entry, 2), "stop": round(stop, 2),
                    "source": "形態支撐",
                    "basis": f"{best['name']}頸線{entry:.2f}/支撐{stop:.2f}"}
    return None


BOTTOM_WEIGHT = {"雙重底/W底": 1.0, "頭肩底": 0.9, "複合頭肩底": 0.6}


def floor_stop(entry, stop):
    """確保停損離進場至少 MIN_STOP_PCT,太近會被雜訊掃到、也會讓 R/R 失真。"""
    min_dist = entry * config.MIN_STOP_PCT
    if entry - stop < min_dist:
        return round(entry - min_dist, 2)
    return stop


def rr_ratio(entry, stop, target):
    """風險報酬比 = (目標 - 進場) / (進場 - 停損);停損距離即『賠』,目標距離即『賺』。"""
    if not target or entry <= stop:
        return None
    risk = entry - stop
    return round((target - entry) / risk, 2) if risk > 0 else None


def trendline_pullback_entry(df, trend):
    """
    『回測碰線買』(柏仁優先):等價格回測到『上升支撐線 / 雙軌道下緣』才進場。
      進場 = 該綠色上升支撐線在當前的位置(回測買點)
      停損 = 線下方一點(PULLBACK_STOP_BUFFER,跌破線即出),並套最小停損
    只有『主要名單(順勢)』才有這條線;沒有則回 None(那類改用突破買)。
    """
    line = None
    for ln in trend.get("lines", []):
        lab = ln.get("label", "")
        if lab.startswith("上升支撐") or "軌道下緣" in lab:
            line = ln
            break
    if not line:
        return None
    entry = float(line["segment"][1][1])      # 趨勢線在最後一根的位置
    if entry <= 0:
        return None
    stop = floor_stop(entry, entry * (1 - config.PULLBACK_STOP_BUFFER))
    close = float(df["Close"].iloc[-1])
    dist = (close - entry) / entry            # 現價在線上方多少(要回測下來才進場)
    return {"entry": round(entry, 2), "stop": round(stop, 2),
            "source": "回測上升支撐/軌道下緣", "method": "回測碰線買",
            "stage": "等回測碰線", "dist_pct": round(dist * 100, 2),
            "basis": f"回測支撐線{entry:.2f}/停損{stop:.2f}(現價在線上方{dist*100:.1f}%)"}


def pattern_entry_stop(df, p):
    """
    單純依『單一形態』取進場 / 停損(供驗證形態用,不做任何排序評分):
      進場 = 形態頸線 / 整理區上緣(突破價)
      停損 = 形態支撐(W底第二底 / 頭肩底右肩 / 整理下沿),最小距離 MIN_STOP_PCT
    並附 stage(已突破 / 即將突破 / 整理中)當參考標籤,純資訊、不參與篩選。
    """
    close = float(df["Close"].iloc[-1])
    if p["name"] == "動能突破":
        entry = float(p["entry"])
        stop = floor_stop(entry, float(p["stop"]))
    else:
        if not p.get("neckline"):
            return None
        entry = float(p["neckline"][1][1])
        stop = float(p["markers"][-1][1])
        if entry <= stop:
            return None
        stop = floor_stop(entry, stop)
    dist = (close - entry) / entry
    stage = "已突破" if dist > 0.01 else ("即將突破" if dist >= -0.08 else "整理中")
    return {"entry": round(entry, 2), "stop": round(stop, 2), "source": p["name"],
            "method": "突破買", "stage": stage, "dist_pct": round(dist * 100, 2),
            "basis": f"{p['name']}進場{entry:.2f}/停損{stop:.2f}"}


def primary_bottom(patterns):
    """取信心x可靠度最高的『單一主形態』(底部型),沒有回 None。"""
    bottoms = [p for p in patterns
               if p["name"] in BOTTOM_WEIGHT and p.get("neckline")]
    if not bottoms:
        return None
    return max(bottoms, key=lambda p: BOTTOM_WEIGHT[p["name"]] * p.get("confidence", 0))


def imminent_setup(df, patterns):
    """
    『即將突破(蓄勢待發)』設定:以單一主形態為準,
    只接受『價格貼著頸線下方、尚未突破(或剛觸頸線)』的標的——這是停損最近、
    風險報酬比最佳的做多進場點。已大漲延伸/離頸線太遠者一律排除。
      進場 = 主形態頸線(突破價)、停損 = 形態支撐(底2/右肩)
      dist = (現價 - 頸線)/頸線
        -8% ~ +1%  → 即將突破(蓄勢待發)  ← 你要的
        +1% ~ +4%  → 剛突破(仍可接受,次選)
        其餘        → 排除(未到位 或 已延伸追高)
    """
    close = float(df["Close"].iloc[-1])
    p = primary_bottom(patterns)
    if not p:
        return None
    entry = float(p["neckline"][1][1])
    stop = float(p["markers"][-1][1])
    if entry <= stop:
        return None
    stop = floor_stop(entry, stop)
    dist = (close - entry) / entry
    if -0.08 <= dist <= 0.01:
        stage = "即將突破"
    elif 0.01 < dist <= 0.04:
        stage = "剛突破"
    else:
        return None
    return {"entry": round(entry, 2), "stop": round(stop, 2),
            "source": p["name"], "primary": p["name"],
            "confidence": round(p.get("confidence", 0), 2),
            "stage": stage, "dist_pct": round(dist * 100, 2),
            "basis": f"{p['name']}頸線{entry:.2f}/支撐{stop:.2f}({stage})"}


# ---------- 2. 第一批進場部位計算 ----------
def first_entry(entry, stop, capital=None, risk_pct=None):
    """
    回傳第一批進場的部位計算。
      風險金額   = 投資資金 x 風險%
      每張停損金額 = (進場價 - 停損價) x 每張股數
      風險口數   = floor(風險金額 / 每張停損金額)
      資金口數   = floor(投資資金 / (進場價 x 每張股數))
      實際口數   = min(風險口數, 資金口數)
      實際風險比例 = 實際口數 x 每張停損金額 / 投資資金
    """
    capital = capital or config.TOTAL_CAPITAL
    risk_pct = risk_pct if risk_pct is not None else config.RISK_PCT

    risk_amt = capital * risk_pct
    stop_per_lot = (entry - stop) * LOT          # 每張的潛在虧損(元)
    cost_per_lot = entry * LOT                   # 每張的成本(元)

    if stop_per_lot <= 0:
        return None

    n_risk = math.floor(risk_amt / stop_per_lot)
    n_cap = math.floor(capital / cost_per_lot)
    n = max(0, min(n_risk, n_cap))

    actual_loss = n * stop_per_lot
    return {
        "capital": capital,
        "risk_pct": risk_pct,
        "risk_amt": round(risk_amt),
        "entry": entry,
        "stop": stop,
        "stop_per_lot": round(stop_per_lot),       # 每張停損金額
        "cost_per_lot": round(cost_per_lot),       # 每張成本
        "n_risk": n_risk,                          # 風險允許口數
        "n_cap": n_cap,                            # 資金允許口數
        "lots": n,                                 # 實際建議口數
        "position_cost": round(n * cost_per_lot),  # 投入金額
        "actual_loss": round(actual_loss),         # 觸停損實際虧損
        "actual_risk_pct": round(actual_loss / capital * 100, 3),  # 實際風險比例(%)
        "limited_by": ("資金" if n_cap < n_risk else "風險") if n > 0 else "停損過寬",
        "note": ("" if n >= 1 else
                 f"停損距離過寬,買 1 張就虧 {round(stop_per_lot)} 元 "
                 f"(={round(stop_per_lot/capital*100,2)}% > 設定風險)"),
    }


# ---------- 3. 加碼(金字塔)計算 ----------
def pyramid(entry, stop, n1, add_entry, add_stop, capital=None, risk_pct=None):
    """
    依使用者公式計算加碼:
      第1次獲利       = (加碼停損點 - 進場價) x 第1次口數 x 每張股數
      加碼停損金額/張 = (加碼進場價 - 加碼停損價) x 每張股數
      加碼風險口數    = floor((風險金額 + 第1次獲利) / 加碼停損金額/張)
      加碼資金口數    = floor(剩餘資金 / (加碼進場價 x 每張股數))   <- 依總資金比對
      加碼實際口數    = min(風險口數, 資金口數)
      加碼後實際風險% = (加碼口數 x 加碼停損金額/張 - 第1次獲利) / 投資資金
                       (<=0 代表「無風險加碼」:第一批已鎖獲利覆蓋加碼風險)
    add_stop 同時是「加碼停損點」與「加碼停損價」(整體部位的新停損)。
    """
    capital = capital or config.TOTAL_CAPITAL
    risk_pct = risk_pct if risk_pct is not None else config.RISK_PCT
    risk_amt = capital * risk_pct

    if add_entry <= add_stop:
        return {"valid": False, "reason": "加碼進場價需高於加碼停損價"}

    first_profit = (add_stop - entry) * n1 * LOT        # 第一批鎖住的獲利(元)
    add_stop_per_lot = (add_entry - add_stop) * LOT     # 加碼每張停損金額(元)

    n2_risk = math.floor((risk_amt + first_profit) / add_stop_per_lot)
    used = n1 * entry * LOT
    remaining = capital - used
    n2_cap = math.floor(remaining / (add_entry * LOT)) if add_entry > 0 else 0
    n2 = max(0, min(n2_risk, n2_cap))

    actual_risk_amt = n2 * add_stop_per_lot - first_profit   # 加碼後整體淨風險
    return {
        "valid": True,
        "add_entry": round(add_entry, 2),
        "add_stop": round(add_stop, 2),
        "first_profit": round(first_profit),
        "add_stop_per_lot": round(add_stop_per_lot),
        "n2_risk": n2_risk,
        "n2_cap": n2_cap,
        "add_lots": n2,
        "add_cost": round(n2 * add_entry * LOT),
        "remaining_capital": round(remaining),
        "actual_risk_amt": round(actual_risk_amt),
        "actual_risk_pct": round(actual_risk_amt / capital * 100, 3),
        "risk_free": actual_risk_amt <= 0,
    }


def pyramid_auto(entry, stop, n1, capital=None, risk_pct=None,
                 add_at_r=None, raise_to_r=None):
    """
    自動建議加碼情境:以 R = 進場價 - 停損價 為單位。
      加碼進場價 = 進場價 + add_at_r x R   (預設 +2R 才加碼)
      加碼停損   = 進場價 + raise_to_r x R (預設停損上移到 +1R,鎖第一批 1R 獲利)
    """
    add_at_r = add_at_r if add_at_r is not None else config.ADD_AT_R
    raise_to_r = raise_to_r if raise_to_r is not None else config.RAISE_STOP_TO_R
    R = entry - stop
    add_entry = entry + add_at_r * R
    add_stop = entry + raise_to_r * R
    res = pyramid(entry, stop, n1, add_entry, add_stop, capital, risk_pct)
    res["R"] = round(R, 2)
    res["scenario"] = f"+{add_at_r:g}R 加碼、停損移到 +{raise_to_r:g}R"
    return res
