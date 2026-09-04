# 聯徵中心（JCIC）數據視覺化

把「財團法人金融聯合徵信中心（JCIC）」OpenData 專區的統計資料，加上中央銀行的
房屋修繕貸款資料，整理成可以瀏覽的圖表網站。純靜態 HTML/JS/CSS，沒有任何後端。

## 網站

部署在 GitHub Pages，網址在 repository 的 Settings → Pages 可以看到（第一次啟用
後，之後每次 `main` 分支有新的 commit 都會自動重新部署）。

## 資料夾結構

```
web/               網站本體，index.html 開起來就是整個網站
  data/            自動產生的資料檔案（*.js），不要手動編輯
pipeline/          自動更新用的程式
  fetch_raw.py     只下載網站實際會用到的 26 個 JCIC 原始 CSV
  fetch_cbc.py     抓中央銀行「房屋修繕貸款」資料
  curated_build.py / run_curated_build.py
                   把原始 CSV 轉成網站用的長格式資料，並套用篩選/合併/命名規則
  static_meta.json 每個資料集的說明文字、分類、預設檢視角度等策展設定
.github/workflows/update-data.yml
                   排程（每週一次）自動重新抓資料、重建、有變化才 commit、
                   然後部署到 GitHub Pages
```

## 為什麼不是直接用 JCIC 官方的下載清單

網站上顯示的 13 個資料集，是逐步篩選、合併、改名出來的成果（原始 JCIC 有 135
個 CSV、9 大分類），不是原始資料的機械式轉換。`pipeline/` 底下的腳本把這個篩選
結果寫成固定規則，重跑只會更新數字，不會把篩選結果洗掉。如果之後想調整篩選範圍
（多留/少留某個資料集），要同時改：

1. `pipeline/fetch_raw.py` 的 `FILES` 清單（要多抓/少抓的原始檔案）
2. `pipeline/run_curated_build.py` 對應的 `build_xxx()` 函式（合併/改名邏輯）
3. `pipeline/static_meta.json`（說明文字、分類）

## 手動更新一次

在 GitHub repository 頁面上方的「Actions」分頁，選「更新 JCIC 資料並部署網站」
這個 workflow，按「Run workflow」就會立刻抓一次最新資料、重新部署，不用等排程。

## 在本機測試

```
python3 pipeline/fetch_raw.py data/raw
python3 pipeline/fetch_cbc.py cbc_ef99m01_raw.json
python3 pipeline/run_curated_build.py --raw-dir data/raw --out-dir web/data --cbc-json cbc_ef99m01_raw.json --meta pipeline/static_meta.json
```

然後用瀏覽器打開 `web/index.html`（或 `python3 -m http.server` 起一個本機
伺服器）確認畫面正常，再 commit。
