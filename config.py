# -*- coding: utf-8 -*-
"""
全域參數設定。
台股一張 = 1000 股，所以「每張投資金額」= 股價 x 1000。
使用者要的 2 萬 ~ 10 萬 / 張 => 股價約 NT$20 ~ NT$100。
"""

# ---- 投資金額 / 價格篩選 ----
SHARES_PER_LOT = 1000          # 台股一張股數
MIN_BUDGET = 20_000            # 每張最低投資金額(NT$)
MAX_BUDGET = 100_000           # 每張最高投資金額(NT$)
# 由預算換算出的股價區間(自動計算，不用手動改)
MIN_PRICE = MIN_BUDGET / SHARES_PER_LOT   # 20.0
MAX_PRICE = MAX_BUDGET / SHARES_PER_LOT   # 100.0

# ---- 流動性篩選 ----
MIN_AVG_VOLUME = 500_000       # 近 20 日平均成交股數下限(= 500 張),太冷門的剔除
MIN_BARS = 60                  # 至少幾根日 K 才納入(不足無法判讀形態)

# ---- 資料抓取 ----
LOOKBACK_DAYS = 365            # K 線回看天數(約一年)
MARKET = "both"               # listed(上市) / otc(上櫃) / both
CACHE_DIR = "data"
CACHE_HOURS = 12               # 快取多久內視為新鮮,避免重複抓

# ---- 轉折點(pivot)偵測 ----
PIVOT_WINDOW = 5               # 左右各 N 根 K 棒,決定 swing high/low 的靈敏度(越大越平滑)

# ---- 形態學門檻 ----
# 雙重底 / W 底
DB_BOTTOM_TOL = 0.05           # 兩底價差容許(<=5% 視為等高)
DB_MIN_REBOUND = 0.04          # 中間反彈(頸線)需高於底部 >=4%
DB_MIN_SEP = 8                 # 兩底間隔最少 K 棒
DB_MAX_SEP = 120               # 兩底間隔最多 K 棒

# 頭肩底
HS_SHOULDER_TOL = 0.06         # 左右肩高度容許 <=6%
HS_HEAD_DROP = 0.03            # 頭需比兩肩低 >=3%
HS_MIN_SEP = 5                 # 各轉折最少間隔

# 突破確認
BREAKOUT_CONFIRM = 0.0         # 收盤 >= 頸線 * (1+此值) 視為突破;0 = 剛站上
BREAKOUT_MAX_AGE = 20          # 突破發生在最近 N 根 K 棒內才算「當下機會」

# 趨勢線
TREND_PIVOTS = 4               # 用最近幾個轉折點擬合趨勢線
TREND_TOUCH_TOL = 0.03         # 轉折點離趨勢線 <=3% 算一次觸碰

# 跳空
GAP_MIN = 0.01                 # 跳空幅度 >=1% 才計入

# ---- 資金 / 風險控管 ----
TOTAL_CAPITAL = 300_000        # 總投資資金(NT$)
RISK_PCT = 0.01                # 單筆風險比例(投資資金 x 此值 = 風險金額)
# 加碼(金字塔)自動建議:以 R = (進場價 - 停損價) 為單位
ADD_AT_R = 2.0                 # 獲利達 +2R 時加碼
RAISE_STOP_TO_R = 1.0          # 加碼時把整體停損上移到 進場價 +1R(鎖住第一批 1R 獲利)
MIN_STOP_PCT = 0.02            # 最小停損距離(進場價的 2%);太近會被盤中雜訊掃到,也避免 R/R 失真
PULLBACK_STOP_BUFFER = 0.03    # 回測碰線買:停損設在趨勢線下方此比例(跌破線一點點就出)
# 進場時效性:現價離進場太遠(已追高)就視為「太晚」
ENTRABLE_PULLBACK_MAX = 0.12   # 回測碰線買:現價最多高於買線此比例,超過=漲太多、等不到回測
ENTRABLE_BREAKOUT_MAX = 0.04   # 突破買:現價最多高於頸線此比例,超過=已突破又追高
NEAR_ENTRY_BAND = 0.08         # 「貼近進場」:現價與進場價距離在此比例內(±8%)才算到買點

# ---- 輸出 ----
OUTPUT_DIR = "output"
CHART_DIR = "output/charts"
# 網頁預覽暫存目錄:OneDrive 目錄在預覽沙箱下不可讀,故每次產出後同步一份到 /tmp 供 preview 伺服器服務
PREVIEW_DIR = "/tmp/stock-screener-report"
MAX_CHARTS = 100000            # 畫全部命中標的的圖(避免有股票漏畫);量大時畫圖會較久
MIN_SCORE = 1                  # 至少命中幾個做多訊號才納入結果
