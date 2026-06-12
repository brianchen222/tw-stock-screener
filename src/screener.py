# -*- coding: utf-8 -*-
"""
主流程:清單 -> 抓資料 -> 價格/量篩選 -> 形態與趨勢偵測 -> 評分 -> 輸出。
"""
import os
import csv

import numpy as np

import config
from . import universe as uni
from . import fetch
from . import patterns as pat
from . import trendlines as tl
from . import risk as rk
from . import momentum as mom


# 做多形態(本階段只負責「找出符合這些形態的標的」,不做選股策略/排序評分)
LONG_PATTERNS = {"雙重底/W底", "頭肩底", "複合頭肩底", "動能突破"}


def _investment_tier(trend):
    """
    依趨勢線型態把標的分成柏仁的『主要 / 次要』投資名單:
      主要(順勢)  : 上升支撐 或 雙軌道 -> 股價已在上升趨勢中,順勢做多
      次要(觸底反彈): 下降阻力突破 或 橫向/箱型 -> 由空翻多/箱型突破,剛要反轉、確認度較低
    主要優先於次要;兩者皆無趨勢訊號則歸『未分類』。
    """
    txt = " ".join(trend.get("signals", []))
    if "上升支撐" in txt or "雙軌道" in txt:
        return "主要"
    if "下降阻力突破" in txt or "橫向" in txt:
        return "次要"
    return "未分類"


def _make_plan(es):
    """把一組進場/停損(es)算成完整計畫:含口數與加碼。es 為 None 則回 None。"""
    if not es:
        return None
    sizing = rk.first_entry(es["entry"], es["stop"])
    add = None
    if sizing and sizing["lots"] >= 1:
        add = rk.pyramid_auto(es["entry"], es["stop"], sizing["lots"])
    return {"es": es, "sizing": sizing, "pyramid": add}


def _passes_price_volume(df):
    """價格落在預算區間、且流動性足夠。"""
    last_close = float(df["Close"].iloc[-1])
    if not (config.MIN_PRICE <= last_close <= config.MAX_PRICE):
        return False, last_close
    avg_vol = float(df["Volume"].tail(20).mean())
    if avg_vol < config.MIN_AVG_VOLUME:
        return False, last_close
    return True, last_close


def run(market=None, limit=None, use_cache=True, make_charts=True, progress=True,
        append=False):
    """
    單純『形態偵測清單』:過濾池 -> 偵測做多形態 -> 命中即列出。
    每檔以信心最高的『單一主形態』呈現,依形態信心(形狀有多標準)中性排序。
    不做選股策略、不做 R/R 排名(那部分待你確認形態後再研究)。
    """
    market = market or config.MARKET
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    universe = uni.get_universe(market)
    if limit:
        universe = universe[:limit]
    if progress:
        print(f"[1/4] 股票清單:{len(universe)} 檔({market})")

    if append:
        # 雲端模式:用官方端點補當日一筆到快取(不碰 Yahoo,避免雲端被限流)
        from . import fetch_daily
        fetch_daily.append_latest_day(universe, progress=progress)

    if progress:
        print(f"[2/4] 下載 K 線(回看 {config.LOOKBACK_DAYS} 天)...")
    data = fetch.fetch_many(universe, use_cache=use_cache, progress=progress)
    name_map = {r["code"]: r["name"] for r in universe}
    mk_map = {r["code"]: r["market"] for r in universe}

    if progress:
        print(f"[3/4] 偵測做多形態(有效資料 {len(data)} 檔)...")
    results = []
    for code, df in data.items():
        ok, last_close = _passes_price_volume(df)
        if not ok:
            continue
        found, _seq = pat.detect_all(df)
        mb = pat.momentum_breakout(df)
        if mb:
            found = found + [mb]
        # 只要命中任一做多形態就列入(跳空僅為輔助,不單獨成立)
        long_pats = [p for p in found if p["name"] in LONG_PATTERNS]
        if not long_pats:
            continue

        trend = tl.detect_trendlines(df)
        primary = max(long_pats, key=lambda p: p.get("confidence", 0))

        # 兩種進場方式各算一套(進場/停損/口數/加碼)
        plan_break = _make_plan(rk.pattern_entry_stop(df, primary))       # 突破買
        plan_pull = _make_plan(rk.trendline_pullback_entry(df, trend))    # 回測碰線買
        # 柏仁優先:有上升支撐/軌道下緣就用回測碰線買,否則用突破買
        active = plan_pull or plan_break
        entry_method = "回測碰線買" if plan_pull else "突破買"

        results.append({
            "code": code,
            "name": name_map.get(code, ""),
            "market": "上市" if mk_map.get(code) == "listed" else "上櫃",
            "close": round(last_close, 2),
            "lot_cost": int(round(last_close * config.SHARES_PER_LOT)),
            "score": round(primary.get("confidence", 0), 2),  # = 形態信心(中性排序用)
            "patterns": [primary],          # 單一主形態,乾淨呈現供驗證
            "all_pattern_names": [p["name"] for p in long_pats],
            "tier": _investment_tier(trend),   # 主要(順勢) / 次要(觸底反彈) / 未分類
            "timing": mom.entry_timing_signals(df),  # 帶量突破/回測均線/5MV翻揚
            "trend": trend,
            # 圖與 CSV 用「柏仁優先」的那套
            "entry_stop": active["es"] if active else None,
            "sizing": active["sizing"] if active else None,
            "pyramid": active["pyramid"] if active else None,
            "stage": active["es"]["stage"] if active else None,
            "dist_pct": active["es"]["dist_pct"] if active else None,
            "entry_method": entry_method,
            "plan_breakout": plan_break,       # 突破買
            "plan_pullback": plan_pull,        # 回測碰線買
            "df": df,
        })

    # 依形態信心(形狀標準度)中性排序;選股策略之後再談
    results.sort(key=lambda r: r["score"], reverse=True)
    if progress:
        print(f"[4/4] 命中 {len(results)} 檔符合形態,輸出結果...")

    _write_csv(results)
    if make_charts:
        _make_charts(results, progress)
    from . import report
    report.write_report(results)
    _sync_preview()
    return results


def _sync_preview():
    """把報告 + 圖同步到 /tmp 暫存目錄,供網頁預覽伺服器服務(OneDrive 目錄沙箱不可讀)。"""
    import shutil
    try:
        dst = config.PREVIEW_DIR
        os.makedirs(dst, exist_ok=True)
        rep = os.path.join(config.OUTPUT_DIR, "report.html")
        if os.path.exists(rep):
            shutil.copy(rep, os.path.join(dst, "report.html"))
            shutil.copy(rep, os.path.join(dst, "index.html"))   # 根目錄即顯示報告
        for fn in ("serve.py",):
            if os.path.exists(fn):
                shutil.copy(fn, os.path.join(dst, fn))
        cdst = os.path.join(dst, "charts")
        if os.path.isdir(config.CHART_DIR):
            shutil.rmtree(cdst, ignore_errors=True)
            shutil.copytree(config.CHART_DIR, cdst)
        print(f"  → 已同步預覽:{dst}(preview_start name=report)")
    except Exception as e:
        print(f"  預覽同步略過:{repr(e)[:100]}")


def _fmt_patterns(found):
    parts = []
    for p in found:
        tag = "✓突破" if p.get("breakout") else "形成中"
        tgt = f" 目標{p['target']}" if p.get("target") else ""
        parts.append(f"{p['name']}({tag},信心{p['confidence']:.2f}{tgt})")
    return " | ".join(parts)


def _write_csv(results):
    path = os.path.join(config.OUTPUT_DIR, "screener_results.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([
            "代號", "名稱", "市場", "收盤價", "形態信心", "做多形態",
            "進場價", "停損價", "進出依據", "每張停損(元)",
            "建議口數(張)", "投入金額", "觸損虧損", "實際風險%",
            "加碼進場", "加碼停損", "建議加碼(張)", "加碼後風險%", "無風險加碼",
            "趨勢訊號", "備註",
        ])
        for r in results:
            es, sz, ad = r.get("entry_stop"), r.get("sizing"), r.get("pyramid")
            trend_sig = " / ".join(r["trend"].get("signals", []))
            notes = " ".join(p.get("note", "") for p in r["patterns"]
                             if "人工" in p.get("note", ""))
            if sz and sz.get("note"):
                notes = (notes + " " + sz["note"]).strip()
            row = [r["code"], r["name"], r["market"], r["close"], r["score"],
                   _fmt_patterns(r["patterns"])]
            if es and sz:
                row += [es["entry"], es["stop"], es["source"],
                        f'{sz["stop_per_lot"]:,}', sz["lots"],
                        f'{sz["position_cost"]:,}', f'{sz["actual_loss"]:,}',
                        sz["actual_risk_pct"]]
            else:
                row += ["", "", "(停損過寬/無明確進場)", "", "", "", "", ""]
            if ad and ad.get("valid"):
                row += [ad["add_entry"], ad["add_stop"], ad["add_lots"],
                        ad["actual_risk_pct"], "是" if ad["risk_free"] else "否"]
            else:
                row += ["", "", "", "", ""]
            row += [trend_sig, notes]
            w.writerow(row)
    print(f"  → 清單已存:{path}")


def _make_charts(results, progress=True):
    from . import charting
    top = results[:config.MAX_CHARTS]
    for i, r in enumerate(top, 1):
        try:
            args = (r["code"], r["name"], r["df"], r["patterns"], r["trend"], r["score"])
            kw = dict(entry_stop=r.get("entry_stop"), sizing=r.get("sizing"))
            p = charting.plot_stock(*args, show_outline=True, suffix="", **kw)
            charting.plot_stock(*args, show_outline=False, suffix="_plain", **kw)
            if progress:
                print(f"  圖 {i}/{len(top)}: {os.path.basename(p)} (+無輪廓版)")
        except Exception as e:
            print(f"  圖 {i} 失敗 {r['code']}: {repr(e)[:120]}")
    print(f"  → K 線圖已存:{config.CHART_DIR}/")
