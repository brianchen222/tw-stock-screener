# -*- coding: utf-8 -*-
"""
取得台股清單(代號、名稱、市場別)。
資料來源:twstock 內建的 codes 表(離線,不需連網)。
yfinance 代號規則:上市 -> 代號.TW,上櫃 -> 代號.TWO
"""
import twstock


def get_universe(market="both"):
    """
    回傳 list[dict]:{code, name, market, yf_symbol}
    market: 'listed'(上市) / 'otc'(上櫃) / 'both'
    只取 type == '股票'(排除 ETF、權證、特別股等)。
    """
    rows = []
    for code, info in twstock.codes.items():
        if info.type != "股票":
            continue
        if info.market == "上市":
            mk, suffix = "listed", ".TW"
        elif info.market == "上櫃":
            mk, suffix = "otc", ".TWO"
        else:
            continue  # 興櫃、其他略過

        if market != "both" and mk != market:
            continue

        # 代號需為 4 碼純數字(排除如 0050 以外的特殊代號可放行,這裡只擋非 4 碼)
        if not (code.isdigit() and len(code) == 4):
            continue

        rows.append({
            "code": code,
            "name": info.name,
            "market": mk,
            "yf_symbol": code + suffix,
        })
    return rows


if __name__ == "__main__":
    u = get_universe("both")
    print(f"共 {len(u)} 檔(上市+上櫃)")
    for r in u[:5]:
        print(r)
