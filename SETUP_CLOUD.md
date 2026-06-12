# 雲端自動更新 + 網路發布(GitHub Actions + Pages)

目標:**不用開電腦、不用開 Claude**,每週一~五 **14:00(台北)** 自動更新,
報告發布在公開網址,用瀏覽器(含手機)就能看。

資料來源已改用**台灣交易所官方端點**(TWSE / TPEx)整批抓當日收盤,雲端 IP 不會被擋。

---

## 一次性設定(約 5 分鐘)

### 1. 建一個 GitHub repo
到 GitHub → New repository → 取名(例如 `tw-stock-screener`)→ **Private 或 Public 皆可** → Create。
(先不要勾 README,建空的。)

### 2. 把專案推上去
在本機這個資料夾(已幫你 `git init` 並完成首次 commit)執行:
```bash
cd "/Users/brianchen/Library/CloudStorage/OneDrive-自家股份有限公司/(BCC-Agent)/stock-screener"
git remote add origin https://github.com/<你的帳號>/<repo名>.git
git branch -M main
git push -u origin main
```
> 需登入 GitHub。若沒裝 `gh`,push 時會跳出帳密/Token 視窗;或先 `gh auth login`。

### 3. 開啟「讀寫」權限(讓它能把每天補好的資料存回)
repo → **Settings → Actions → General → Workflow permissions** → 選 **Read and write permissions** → Save。

### 4. 開啟 GitHub Pages
repo → **Settings → Pages → Build and deployment → Source** → 選 **GitHub Actions**。

### 5. 先手動跑一次測試
repo → **Actions** 分頁 → 左側「每日選股更新」→ **Run workflow** → 等約 10 分鐘跑完(綠勾)。

完成後你的網址是:
```
https://<你的帳號>.github.io/<repo名>/
```
首頁是功能總覽,點「開啟選股報告」進報告;或直接 `.../report.html`。

---

## 之後

- **全自動**:每週一~五 14:00 台北自動跑(GitHub 排程偶爾延遲幾分鐘,正常)。
- 想臨時更新:Actions 頁「Run workflow」手動觸發即可。
- 想改時間:編輯 `.github/workflows/daily.yml` 的 `cron`(用 UTC,台北=UTC+8;例 `0 6 * * 1-5` = 台北 14:00)。

## 費用 / 限制
- GitHub Actions 免費額度每月 2000 分鐘;本工作每次約 8~10 分鐘 × 每月約 22 個交易日 ≈ 200 分鐘,**免費額度內**。
- Pages 免費。

## 疑難排解
- **圖是空白方框**:workflow 已 `apt install fonts-noto-cjk`;若仍異常,確認該步驟成功。
- **資料沒更新**:當天若非交易日(假日/颱風假)官方端點無資料,屬正常;Actions log 會顯示「沒有取得當日資料」。
- **push 失敗**:多半是第 3 步「Read and write permissions」沒開。
- **OneDrive 與 .git**:OneDrive 同步 `.git` 偶爾會卡。若 git 操作異常,可把整個 `stock-screener` 複製到非 OneDrive 路徑(例如 `~/tw-stock-screener`)再做 git。

## 本機仍可用
本機照舊:`python run.py`(用 Yahoo,資料最完整)→ `preview_start`。雲端與本機互不影響。
