# -*- coding: utf-8 -*-
"""
畫 K 線圖,並把偵測到的趨勢線、頸線、形態關鍵點標註上去。
輸出 PNG 到 config.CHART_DIR。
"""
import os
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import mplfinance as mpf

warnings.filterwarnings("ignore")
import config


# ---- 中文字型 ----
# macOS 的 CJK 字型多為 .ttc,matplotlib 預設不一定載入,且 mplfinance 會用自己的
# style 蓋掉 rcParams。因此這裡「明確註冊字型檔」取得字型名稱,後面再透過
# make_mpf_style(rc=...) 強制套用,確保中文標題正常顯示。
def _setup_cjk_font():
    font_files = [
        # macOS
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",  # 名稱 Arial Unicode MS,覆蓋全 CJK
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        # Linux(雲端 GitHub Actions 需先 apt install fonts-noto-cjk)
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ]
    for path in font_files:
        if os.path.exists(path):
            try:
                fm.fontManager.addfont(path)
                name = fm.FontProperties(fname=path).get_name()
                plt.rcParams["font.family"] = name
                plt.rcParams["axes.unicode_minus"] = False
                return name
            except Exception:
                continue
    # 退而求其次:用 matplotlib 已認得的繁中字型名(含 Linux Noto)
    for c in ["Heiti TC", "PingFang HK", "Songti SC", "STHeiti",
              "Noto Sans CJK TC", "Noto Sans CJK JP", "WenQuanYi Zen Hei"]:
        if c in {f.name for f in fm.fontManager.ttflist}:
            plt.rcParams["font.family"] = c
            plt.rcParams["axes.unicode_minus"] = False
            return c
    return None


_CJK = _setup_cjk_font()


def _idx_to_date(df, i):
    i = int(round(i))
    i = max(0, min(len(df) - 1, i))
    return df.index[i]


def plot_stock(code, name, df, patterns, trend, score, out_dir=None,
               entry_stop=None, sizing=None, show_outline=True, suffix=""):
    """
    code/name: 股票代號、名稱
    df: OHLCV(欄位 Open/High/Low/Close/Volume,index 為日期)
    patterns: patterns.detect_all 回傳的形態 list
    trend: trendlines.detect_trendlines 回傳 dict(signals/lines)
    score: 綜合分數
    回傳輸出檔路徑。
    """
    out_dir = out_dir or config.CHART_DIR
    os.makedirs(out_dir, exist_ok=True)

    # 紅漲綠跌(台股習慣)
    mc = mpf.make_marketcolors(up="#d62728", down="#2ca02c", inherit=True)
    rc = {"axes.unicode_minus": False}
    if _CJK:
        rc["font.family"] = _CJK
    style = mpf.make_mpf_style(marketcolors=mc, gridstyle=":",
                               facecolor="white", figcolor="white", rc=rc)

    # ---- 趨勢線 + 頸線 + 型態輪廓 -> alines ----
    # 趨勢線/頸線用「虛線」;型態輪廓(把 W底/頭肩底 的形狀連出來)用「橘色實線粗線」。
    seg_list, seg_colors, seg_lw, seg_ls = [], [], [], []

    def _add(seg, color, lw, ls):
        seg_list.append(seg)
        seg_colors.append(color)
        seg_lw.append(lw)
        seg_ls.append(ls)

    for ln in trend.get("lines", []):
        (x0, y0), (x1, y1) = ln["segment"]
        _add([(_idx_to_date(df, x0), y0), (_idx_to_date(df, x1), y1)],
             ln["color"], 1.2, "--")
    for p in patterns:
        if p.get("neckline"):
            (x0, y0), (x1, y1) = p["neckline"]
            _add([(_idx_to_date(df, x0), y0), (_idx_to_date(df, x1), y1)],
                 "#1f77b4", 1.3, "--")     # 頸線:藍色虛線(=突破/進場參考)
    # 型態輪廓:把結構轉折連起來畫出『完整』型態形狀。
    # W 底要補上左邊「跌入底1的前高」與右邊「由底2回升到現價」兩段,才會是 W(高低高低高);
    # 否則只連 底1→中峰→底2 會變成 ∧(看起來像 M 的左半)。
    high_arr = df["High"].values
    last_idx = len(df) - 1
    last_close = float(df["Close"].iloc[-1])
    for p in (patterns if show_outline else []):   # 無輪廓版:跳過橘色型態輪廓線
        nm = p["name"]
        if "跳空" in nm or nm == "動能突破":
            continue                        # 跳空為單點、動能突破改用方框,另處理
        mks = p.get("markers", [])
        if len(mks) < 2:
            continue
        pts = [(int(idx), float(price)) for (idx, price, _l) in mks]
        # 左端:第一個轉折之前的高點(型態的左上起點)
        half = max(10, min(45, pts[1][0] - pts[0][0]))
        lo = max(0, pts[0][0] - half)
        if lo < pts[0][0]:
            seg = high_arr[lo:pts[0][0]]
            pts = [(lo + int(seg.argmax()), float(seg.max()))] + pts
        # 右端:由最後一個底回升到現價(型態的右上終點 / 即將突破)
        pts = pts + [(last_idx, last_close)]
        poly = [(_idx_to_date(df, i), pr) for (i, pr) in pts]
        _add(poly, "#ff7f0e", 2.4, "-")  # 橘色實線=型態輪廓

    alines = dict(alines=seg_list, colors=seg_colors,
                  linewidths=seg_lw, linestyle=seg_ls) if seg_list else None

    # ---- 形態關鍵點 -> scatter addplot ----
    # 符號「依形態類型」固定對應(不再依順序輪流),且避開向下三角形以免被誤解為看跌。
    PAT_MARKER = {
        "雙重底/W底": "o",      # 圓
        "頭肩底": "^",          # 上三角
        "複合頭肩底": "s",      # 方
        "動能突破": "*",        # 星(整理上緣壓力/停損低)
    }
    addplots = []
    legend_items = []          # [(marker, label)] 供圖例使用
    seen = set()
    for p in patterns:
        pname = p["name"]
        if "跳空" in pname:
            mk, lab = "D", "跳空缺口"   # 菱形(不帶方向)
        else:
            mk, lab = PAT_MARKER.get(pname, "P"), pname
        ser = pd.Series(np.nan, index=df.index)
        for (idx, price, _lab) in p.get("markers", []):
            ser.iloc[int(idx)] = price
        if ser.notna().any():
            addplots.append(mpf.make_addplot(
                ser, type="scatter", markersize=90, marker=mk, color="#ff7f0e"))
            if lab not in seen:
                seen.add(lab)
                legend_items.append((mk, lab))

    # ---- 進場 / 停損 水平線 ----
    hlines_y, hlines_c = [], []
    if entry_stop:
        hlines_y += [entry_stop["entry"], entry_stop["stop"]]
        hlines_c += ["#1f77b4", "#d62728"]   # 進場藍、停損紅

    # ---- 標題 ----
    last_close = float(df["Close"].iloc[-1])
    lot_cost = last_close * config.SHARES_PER_LOT
    pat_names = "、".join(p["name"] for p in patterns) or "—"
    line2 = f"做多形態:{pat_names}"
    if entry_stop and entry_stop.get("stage"):
        line2 += f"　【{entry_stop['stage']}　距頸線{entry_stop['dist_pct']:+.1f}%】"
    if entry_stop and sizing:
        line2 += (f"\n進場{entry_stop['entry']} / 停損{entry_stop['stop']}"
                  f"({entry_stop['source']})　建議{sizing['lots']}張"
                  f"　投入{sizing['position_cost']:,}　實際風險{sizing['actual_risk_pct']}%")
    title = (f"{code} {name}　收{last_close:.2f}　一張約 NT${lot_cost:,.0f}　"
             f"形態信心{score:.2f}\n{line2}")

    out_path = os.path.join(out_dir, f"{code}_{name}{suffix}.png")
    kwargs = dict(
        type="candle", style=style, volume=True,
        figsize=(13, 7), title=title,
        datetime_format="%y/%m", xrotation=0,
        returnfig=True,
    )
    if alines:
        kwargs["alines"] = alines
    if addplots:
        kwargs["addplot"] = addplots
    if hlines_y:
        kwargs["hlines"] = dict(hlines=hlines_y, colors=hlines_c,
                                linestyle="-", linewidths=1.0, alpha=0.7)

    fig, axes = mpf.plot(df, **kwargs)

    # ---- 動能突破:整理區方框(輔助標示型態範圍)----
    for p in (patterns if show_outline else []):   # 無輪廓版:跳過橘色整理區方框
        if p["name"] == "動能突破" and p.get("neckline"):
            (x0, top), (x1, _t) = p["neckline"]
            bottom = min(pr for _i, pr, _l in p["markers"])
            axes[0].add_patch(Rectangle(
                (x0, bottom), x1 - x0, top - bottom,
                facecolor="#ff7f0e", alpha=0.10,
                edgecolor="#ff7f0e", linewidth=1.5, linestyle="-", zorder=1))

    # ---- 形態符號圖例 ----
    if legend_items:
        handles = [Line2D([0], [0], marker=mk, linestyle="none",
                          markerfacecolor="#ff7f0e", markeredgecolor="#ff7f0e",
                          markersize=10, label=lab)
                   for mk, lab in legend_items]
        axes[0].legend(handles=handles, loc="upper left", fontsize=10,
                       framealpha=0.92, facecolor="white", edgecolor="#bbbbbb",
                       title="形態關鍵點", title_fontsize=10).set_zorder(25)

    # ---- 進場 / 停損:放在「靠近指標、偏上的空白處」並用細線連回價位 ----
    if entry_stop:
        ax = axes[0]                              # 價格主圖
        box = dict(boxstyle="round,pad=0.4", edgecolor="white", linewidth=1.2)

        entry = entry_stop["entry"]
        stop = entry_stop["stop"]
        lots = sizing["lots"] if sizing else None
        entry_txt = f"進場 {entry}" + (f"（{lots}張）" if lots else "")
        stop_loss = sizing["actual_loss"] if (sizing and sizing.get("actual_loss")) else None
        stop_txt = f"停損 {stop}" + (f"（虧{stop_loss:,}）" if stop_loss else "")

        ymin, ymax = ax.get_ylim()
        yspan = (ymax - ymin) or 1.0
        highs = df["High"].values
        nb = len(df)

        # 找「上方頭頂空間最大」的橫向視窗當放置點;略偏向近期(右側,指標所在)。
        # 若左上角已被圖例占用,放置點避開左側 30%。
        win = max(6, nb // 14)
        x_start = int(nb * 0.30) if legend_items else 0
        best_score, best_c = None, x_start
        for c in range(x_start, max(x_start + 1, nb - win)):
            headroom = ymax - highs[c:c + win].max()
            recency = (c / nb) * 0.18 * yspan          # 近期加權
            score = headroom + recency
            if best_score is None or score > best_score:
                best_score, best_c = score, c + win // 2
        cx = min(max(best_c, nb * 0.12), nb * 0.88)

        # 兩個標籤疊在空白區上緣(進場在上、停損在下),用細線連回各自價位線。
        trans = ax.get_xaxis_transform()            # x=資料座標, y=軸比例
        for txt, price, yfrac, color in (
                (entry_txt, entry, 0.94, "#1f77b4"),
                (stop_txt, stop, 0.86, "#d62728")):
            ax.annotate(
                txt, xy=(cx, price), xycoords="data",
                xytext=(cx, yfrac), textcoords=trans,
                ha="center", va="center", fontsize=12, fontweight="bold",
                color="white", zorder=22,
                bbox={**box, "facecolor": color},
                arrowprops=dict(arrowstyle="-", color=color, lw=0.9,
                                alpha=0.55, linestyle=(0, (4, 2))))

    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return out_path
