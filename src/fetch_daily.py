# -*- coding: utf-8 -*-
"""
每日整批補資料(雲端用):用官方端點一次抓「全市場當日收盤」,append 到歷史快取。

為什麼:雲端(GitHub Actions)IP 會被 Yahoo/FinMind 擋。改用台灣交易所官方 API——
  上市:TWSE STOCK_DAY_ALL(一次回傳全部上市當日 OHLCV)
  上櫃:TPEx openapi tpex_mainboard_daily_close_quotes(一次回傳全部上櫃當日 OHLCV)
兩者單位皆與歷史快取一致(成交股數),日期需處理(TPEx 為民國年)。
"""
import os
import datetime as dt

import requests
import pandas as pd

import config

_H = {"User-Agent": "Mozilla/5.0"}
_TWSE = "https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL"
_TPEX = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"


def _num(s):
    """把 '2,325.00' / '12435' / '--' 轉 float;無效回 None。"""
    if s is None:
        return None
    s = str(s).replace(",", "").strip()
    if s in ("", "--", "---", "N/A"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _is_stock(code):
    return code.isdigit() and len(code) == 4


def fetch_latest_day():
    """
    回傳 (rows, date_str):
      rows = {code: {"Open","High","Low","Close","Volume"}}
      date_str = 'YYYY-MM-DD'(交易日)
    """
    rows = {}
    date_str = None

    # ---- 上市 TWSE ----
    try:
        j = requests.get(_TWSE, params={"response": "json"}, headers=_H, timeout=30).json()
        if j.get("stat") == "OK" and j.get("data"):
            d = str(j.get("date", ""))                 # 20260612
            if len(d) == 8:
                date_str = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
            for r in j["data"]:
                code = str(r[0]).strip()
                if not _is_stock(code):
                    continue
                o, h, l, c, v = _num(r[4]), _num(r[5]), _num(r[6]), _num(r[7]), _num(r[2])
                if None in (o, h, l, c) or not v:
                    continue
                rows[code] = {"Open": o, "High": h, "Low": l, "Close": c, "Volume": v}
    except Exception as e:
        print("  TWSE 抓取失敗:", repr(e)[:120])

    # ---- 上櫃 TPEx ----
    try:
        arr = requests.get(_TPEX, headers=_H, timeout=30).json()
        for r in arr:
            code = str(r.get("SecuritiesCompanyCode", "")).strip()
            if not _is_stock(code):
                continue
            o, h, l, c = _num(r.get("Open")), _num(r.get("High")), _num(r.get("Low")), _num(r.get("Close"))
            v = _num(r.get("TradingShares"))
            if None in (o, h, l, c) or not v:
                continue
            rows[code] = {"Open": o, "High": h, "Low": l, "Close": c, "Volume": v}
            if date_str is None:
                md = str(r.get("Date", ""))            # 1150612(民國)
                if len(md) == 7:
                    date_str = f"{int(md[:3]) + 1911}-{md[3:5]}-{md[5:7]}"
    except Exception as e:
        print("  TPEx 抓取失敗:", repr(e)[:120])

    return rows, date_str


def append_latest_day(universe, progress=True):
    """
    把『最新交易日』append 到 data/{code}.csv(僅當該日比快取最後一筆新)。
    回傳 (appended, skipped, date_str)。
    """
    rows, date_str = fetch_latest_day()
    if not rows or not date_str:
        print("  整批補資料:沒有取得當日資料(可能非交易日或端點異常)")
        return 0, 0, None
    new_date = pd.Timestamp(date_str)
    cols = ["Open", "High", "Low", "Close", "Volume"]
    appended = skipped = 0

    for r in universe:
        code = r["code"]
        p = os.path.join(config.CACHE_DIR, f"{code}.csv")
        if code not in rows or not os.path.exists(p):
            continue
        try:
            df = pd.read_csv(p, index_col=0, parse_dates=True)
        except Exception:
            continue
        if len(df) and df.index[-1] >= new_date:
            skipped += 1                                # 已有當日,跳過
            continue
        df.loc[new_date, cols] = [rows[code][k] for k in cols]
        df = df[cols]
        df.to_csv(p)
        appended += 1

    if progress:
        print(f"  整批補資料({date_str}):新增 {appended} 檔、已最新 {skipped} 檔")
    return appended, skipped, date_str
