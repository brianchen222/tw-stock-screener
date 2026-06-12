#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
台股做多選股器 —— 以趨勢線 + 形態學(雙重底/W底、頭肩底、複合頭肩底、跳空)
篩出「適合做多、且一張投資金額 2萬~10萬」的標的,並輸出 K 線圖。

用法範例:
  python run.py                      # 全上市+上櫃掃描(較久)
  python run.py --market listed      # 只掃上市
  python run.py --limit 100          # 只掃前 100 檔(測試用,快)
  python run.py --min-price 20 --max-price 100
  python run.py --no-charts          # 不畫圖,只出 CSV
  python run.py --max-charts 20      # 最多畫 20 張
"""
import argparse

import config
from src import screener


def main():
    ap = argparse.ArgumentParser(description="台股做多形態選股器")
    ap.add_argument("--market", choices=["listed", "otc", "both"],
                    default=config.MARKET, help="市場:上市/上櫃/兩者")
    ap.add_argument("--limit", type=int, default=None, help="只掃前 N 檔(測試用)")
    ap.add_argument("--min-price", type=float, default=None, help="最低股價")
    ap.add_argument("--max-price", type=float, default=None, help="最高股價")
    ap.add_argument("--min-volume", type=int, default=None, help="近20日均量下限(股)")
    ap.add_argument("--lookback", type=int, default=None, help="K線回看天數")
    ap.add_argument("--max-charts", type=int, default=None, help="最多畫幾張圖")
    ap.add_argument("--no-charts", action="store_true", help="不畫圖")
    ap.add_argument("--no-cache", action="store_true", help="不使用快取(強制重抓)")
    ap.add_argument("--append", action="store_true",
                    help="雲端模式:用官方端點(TWSE/TPEx)補當日一筆到快取再選股,不碰 Yahoo")
    args = ap.parse_args()

    # 覆寫設定
    if args.min_price is not None:
        config.MIN_PRICE = args.min_price
    if args.max_price is not None:
        config.MAX_PRICE = args.max_price
    if args.min_volume is not None:
        config.MIN_AVG_VOLUME = args.min_volume
    if args.lookback is not None:
        config.LOOKBACK_DAYS = args.lookback
    if args.max_charts is not None:
        config.MAX_CHARTS = args.max_charts

    print("=" * 64)
    print("台股做多選股器")
    print(f"  價格區間:NT${config.MIN_PRICE:.0f} ~ NT${config.MAX_PRICE:.0f} "
          f"(一張約 NT${config.MIN_PRICE*1000:,.0f} ~ {config.MAX_PRICE*1000:,.0f})")
    print(f"  流動性:近20日均量 >= {config.MIN_AVG_VOLUME:,} 股")
    print("=" * 64)

    print("  模式:形態偵測清單(只找出符合做多形態的標的,不做選股排序)")
    results = screener.run(
        market=args.market, limit=args.limit,
        use_cache=not args.no_cache, make_charts=not args.no_charts,
        append=args.append,
    )

    print("\n" + "=" * 64)
    print(f"完成!命中 {len(results)} 檔符合形態。前 15 名(依形態信心):")
    print("=" * 64)
    print(f'{"代號":<6}{"名稱":<10}{"收盤":>7}{"一張成本":>11}{"信心":>7}  做多形態')
    for r in results[:15]:
        pats = "、".join(p["name"] for p in r["patterns"])
        print(f'{r["code"]:<6}{r["name"]:<10}{r["close"]:>7.2f}'
              f'{r["lot_cost"]:>11,}{r["score"]:>7.2f}  {pats}')
    if not results:
        print("(無符合標的,可放寬 config.py 門檻或改用 --limit 測試)")


if __name__ == "__main__":
    main()
