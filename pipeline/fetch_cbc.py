#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抓中央銀行統計資料庫 EF99M01（消費者貸款及建築貸款餘額）的原始 JSON，存成
cbc_ef99m01_raw.json，給 run_curated_build.py 解析出「房屋修繕貸款」那一項。

這個 API 過去驗證可行（見 claude/資料集篩選決定.md「跨機關資料來源」一節），
不需要金鑰。GitHub Actions runner 是一般網路環境，直接 requests.get 就能連到，
不像本專案某些雲端沙盒環境會被組織的 egress allowlist 擋掉。

失敗時這支腳本會直接印錯誤、以非 0 結束，讓 GitHub Actions 那個 step 顯示失敗，
但不影響 workflow 其他 step 繼續跑（workflow 裡這步設定 continue-on-error），
run_curated_build.py 那邊沒收到 --cbc-json 時會自動改用「沿用上次資料」的備援。
"""
import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("缺少 requests 套件，請先執行：pip install requests")
    sys.exit(1)

API_URL = "https://cpx.cbc.gov.tw/API/DataAPI/Get?FileName=EF99M01"


def main():
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("cbc_ef99m01_raw.json")
    try:
        resp = requests.get(API_URL, timeout=30, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "application/json,text/plain,*/*",
        })
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"抓取央行 EF99M01 失敗：{e}", file=sys.stderr)
        sys.exit(1)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"已存到 {out_path}（{out_path.stat().st_size:,} bytes）")

    # 這支腳本只負責把「原始回應」存下來，欄位格式的實際解析在
    # run_curated_build.py 的 build_cbc_mortgage_repair() 裡處理。如果央行那邊
    # 改了回應格式，之後只要調整那個函式，不用動這支下載腳本。
    if isinstance(data, dict) and "records" not in data:
        print("提示：抓到的 JSON 頂層沒有 records 欄位，格式可能跟預期不同，"
              "run_curated_build.py 解析時如果失敗，需要人工檢查這份原始 JSON",
              file=sys.stderr)


if __name__ == "__main__":
    main()
