#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
資金管理 / 加碼計算器(手動)。
先有停損價才有進場價;用「投資資金 x 風險%」回推第一批口數,
再依加碼公式算可加碼口數與加碼後風險。

用法:
  # 只算第一批(自動建議加碼)
  python calc.py --entry 35.45 --stop 33.20

  # 自訂加碼價/停損(現場決定時用)
  python calc.py --entry 35.45 --stop 33.20 --add-entry 39.0 --add-stop 37.5

  # 自訂總資金 / 風險%
  python calc.py --entry 35.45 --stop 33.20 --capital 500000 --risk 0.01
"""
import argparse

import config
from src import risk as rk


def main():
    ap = argparse.ArgumentParser(description="資金管理 / 加碼計算器")
    ap.add_argument("--entry", type=float, required=True, help="進場價")
    ap.add_argument("--stop", type=float, required=True, help="停損價(需 < 進場價)")
    ap.add_argument("--capital", type=float, default=config.TOTAL_CAPITAL, help="總投資資金")
    ap.add_argument("--risk", type=float, default=config.RISK_PCT, help="風險比例(0.01=1%)")
    ap.add_argument("--add-entry", type=float, default=None, help="加碼進場價(可省=自動建議)")
    ap.add_argument("--add-stop", type=float, default=None, help="加碼停損價(可省=自動建議)")
    args = ap.parse_args()

    if args.stop >= args.entry:
        print("錯誤:停損價必須低於進場價(先有停損才有進場)。")
        return

    sz = rk.first_entry(args.entry, args.stop, args.capital, args.risk)
    R = args.entry - args.stop
    print("=" * 60)
    print("【第一批進場】")
    print(f"  總資金           NT${args.capital:,.0f}　風險比例 {args.risk*100:g}%")
    print(f"  風險金額(資金x%) NT${sz['risk_amt']:,}")
    print(f"  進場價 {args.entry}　停損價 {args.stop}　(R = {R:.2f} 元/股)")
    print(f"  每張停損金額     NT${sz['stop_per_lot']:,}  ((進場-停損)x1000)")
    print(f"  風險允許口數     {sz['n_risk']} 張   (風險金額 / 每張停損金額)")
    print(f"  資金允許口數     {sz['n_cap']} 張   (總資金 / 每張成本)")
    print(f"  → 建議買進       {sz['lots']} 張(取較小,受限於{sz['limited_by']})")
    print(f"  投入金額         NT${sz['position_cost']:,}")
    print(f"  觸停損實際虧損   NT${sz['actual_loss']:,}")
    print(f"  實際風險比例     {sz['actual_risk_pct']}%")
    if sz["note"]:
        print(f"  ⚠ {sz['note']}")

    if sz["lots"] < 1:
        print("\n第一批口數為 0,無法加碼。請放寬停損或提高資金/風險%。")
        return

    # 加碼
    if args.add_entry is not None and args.add_stop is not None:
        ad = rk.pyramid(args.entry, args.stop, sz["lots"],
                        args.add_entry, args.add_stop, args.capital, args.risk)
        scen = "自訂加碼"
    else:
        ad = rk.pyramid_auto(args.entry, args.stop, sz["lots"], args.capital, args.risk)
        scen = ad.get("scenario", "自動建議")

    print("=" * 60)
    print(f"【加碼(金字塔)】{scen}")
    if not ad.get("valid"):
        print(f"  無法加碼:{ad.get('reason')}")
        return
    print(f"  加碼進場價       {ad['add_entry']}　加碼停損 {ad['add_stop']}")
    print(f"  第一批已鎖獲利   NT${ad['first_profit']:,}  ((加碼停損-進場)x第一批口數x1000)")
    print(f"  加碼每張停損金額 NT${ad['add_stop_per_lot']:,}")
    print(f"  加碼風險允許口數 {ad['n2_risk']} 張   ((風險金額+第一批獲利)/加碼每張停損)")
    print(f"  加碼資金允許口數 {ad['n2_cap']} 張   (剩餘資金 / 加碼每張成本)")
    print(f"  → 建議加碼       {ad['add_lots']} 張")
    print(f"  加碼投入金額     NT${ad['add_cost']:,}")
    print(f"  加碼後整體淨風險 NT${ad['actual_risk_amt']:,}  ({ad['actual_risk_pct']}%)")
    print(f"  無風險加碼       {'✓ 是(第一批獲利已覆蓋加碼風險)' if ad['risk_free'] else '否'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
