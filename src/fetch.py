# -*- coding: utf-8 -*-
"""
OHLCV 資料下載 + 本地快取。
主來源:yfinance(批次下載,快)。備援:FinMind 開放 API(逐檔)。
快取:data/{code}.csv,CACHE_HOURS 內視為新鮮,避免重複抓。
"""
import os
import time
import warnings
import datetime as dt

import pandas as pd

warnings.filterwarnings("ignore")

import config

OHLCV_COLS = ["Open", "High", "Low", "Close", "Volume"]


# ---------- 快取 ----------
def _cache_path(code):
    return os.path.join(config.CACHE_DIR, f"{code}.csv")


def _load_cache(code):
    p = _cache_path(code)
    if not os.path.exists(p):
        return None
    age_h = (time.time() - os.path.getmtime(p)) / 3600
    if age_h > config.CACHE_HOURS:
        return None
    try:
        df = pd.read_csv(p, index_col=0, parse_dates=True)
        if len(df) and set(OHLCV_COLS).issubset(df.columns):
            return df[OHLCV_COLS]
    except Exception:
        return None
    return None


def _save_cache(code, df):
    try:
        df[OHLCV_COLS].to_csv(_cache_path(code))
    except Exception:
        pass


def _clean(df):
    """整理單檔 OHLCV:去 NaN、排序、欄位齊全。"""
    if df is None or len(df) == 0:
        return None
    df = df.copy()
    df.columns = [str(c).capitalize() if str(c).lower() != "volume" else "Volume"
                  for c in df.columns]
    if not set(OHLCV_COLS).issubset(df.columns):
        return None
    df = df[OHLCV_COLS].dropna()
    df = df[df["Volume"] > 0]
    df = df.sort_index()
    return df if len(df) >= config.MIN_BARS else None  # 至少幾根才有意義(可調)


# ---------- yfinance 批次 ----------
def _fetch_yf_batch(symbols, period_days):
    """批次下載,回傳 {yf_symbol: df}。"""
    import yfinance as yf
    out = {}
    period = f"{period_days}d"
    try:
        data = yf.download(
            tickers=" ".join(symbols),
            period=period, interval="1d",
            group_by="ticker", auto_adjust=False,
            progress=False, threads=True,
        )
    except Exception:
        return out

    if data is None or len(data) == 0:
        return out

    # 單檔時 columns 不是 MultiIndex
    if not isinstance(data.columns, pd.MultiIndex):
        if len(symbols) == 1:
            out[symbols[0]] = _clean(data)
        return out

    for sym in symbols:
        if sym in data.columns.get_level_values(0):
            out[sym] = _clean(data[sym])
    return out


# ---------- FinMind 備援 ----------
def _fetch_finmind(code, start_date):
    import requests
    try:
        r = requests.get(
            "https://api.finmindtrade.com/api/v4/data",
            params={"dataset": "TaiwanStockPrice", "data_id": code,
                    "start_date": start_date},
            timeout=20,
        )
        j = r.json()
        if j.get("status") != 200 or not j.get("data"):
            return None
        df = pd.DataFrame(j["data"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").rename(columns={
            "open": "Open", "max": "High", "min": "Low",
            "close": "Close", "Trading_Volume": "Volume",
        })
        return _clean(df)
    except Exception:
        return None


# ---------- 對外主函式 ----------
def fetch_many(universe, period_days=None, batch_size=80, use_cache=True,
               progress=True):
    """
    universe: list[dict]，需含 code / yf_symbol。
    回傳 {code: df(OHLCV)}。
    """
    period_days = period_days or config.LOOKBACK_DAYS
    start_date = (dt.date.today() - dt.timedelta(days=period_days)).isoformat()
    result = {}
    todo = []  # 需要連網抓的 (code, yf_symbol)

    for r in universe:
        if use_cache:
            c = _load_cache(r["code"])
            if c is not None:
                result[r["code"]] = c
                continue
        todo.append(r)

    if progress:
        print(f"  快取命中 {len(result)} 檔,需下載 {len(todo)} 檔...")

    sym2code = {r["yf_symbol"]: r["code"] for r in todo}
    syms = list(sym2code.keys())

    for i in range(0, len(syms), batch_size):
        chunk = syms[i:i + batch_size]
        got = _fetch_yf_batch(chunk, period_days)
        for sym in chunk:
            code = sym2code[sym]
            df = got.get(sym)
            if df is None:                      # yfinance 失敗 -> FinMind 備援
                df = _fetch_finmind(code, start_date)
            if df is not None:
                result[code] = df
                _save_cache(code, df)
        if progress:
            done = min(i + batch_size, len(syms))
            print(f"  下載進度 {done}/{len(syms)}  (累計有效 {len(result)} 檔)")
        time.sleep(0.5)  # 禮貌性間隔,降低被限流機率

    return result
