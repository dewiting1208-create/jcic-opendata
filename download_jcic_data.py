#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JCIC OpenData 批次下載腳本

用途：把「財團法人金融聯合徵信中心（JCIC）」OpenData 專區的所有 CSV 檔案
      下載到本機 data/raw/<分類>/<檔名> 資料夾底下。

使用方式：
    1. 安裝套件（只需一次）：
       pip install requests
    2. 執行：
       python3 download_jcic_data.py

    這支腳本會讀取同目錄下的 manifest.json（已預先解析好的 144 筆 CSV 清單，
    含分類、fid、檔名），逐一下載並存檔。

備註：
    - 這個下載連結已驗證過是一般的靜態 GET 請求，伺服器回傳
      Content-Type: text/csv, Content-Disposition: attachment，
      不需要登入、cookie 或特殊反爬蟲手法。
    - 腳本仍然帶上瀏覽器慣用的 User-Agent 與 Referer，純粹是禮貌性作法，
      避免被當成明顯的機器人流量。
    - 每次請求之間會 sleep 一小段時間，避免對 JCIC 伺服器造成負擔。
    - 之後如果要接 GitHub Actions 排程自動更新（專案第六步），
      這支腳本的下載邏輯可以直接複製過去用。
"""
import json
import os
import sys
import time
import hashlib
from pathlib import Path

try:
    import requests
except ImportError:
    print("缺少 requests 套件，請先執行：pip install requests")
    sys.exit(1)

BASE = "https://www.jcic.org.tw"
PAGE_URL = f"{BASE}/main_ch/download_page.aspx?uid=213&pid=213"
DOWNLOAD_URL_TMPL = f"{BASE}/main_ch/fileRename/fileRename.aspx?uid=213&fid={{fid}}&kid=4"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

SCRIPT_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = SCRIPT_DIR / "manifest.json"
OUTPUT_DIR = SCRIPT_DIR / "data" / "raw"

REQUEST_DELAY_SEC = 0.5
MAX_RETRIES = 3
RETRY_BACKOFF_SEC = 2


def sanitize_filename(name: str) -> str:
    """移除檔名中在檔案系統上有問題的字元（一般全形符號不受影響）。"""
    for ch in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
        name = name.replace(ch, '_')
    return name.strip()


def load_manifest():
    if not MANIFEST_PATH.exists():
        print(f"找不到 manifest.json（預期路徑：{MANIFEST_PATH}）")
        sys.exit(1)
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f)


def download_one(session: requests.Session, fid: str) -> tuple[bytes, dict]:
    url = DOWNLOAD_URL_TMPL.format(fid=fid)
    headers = {
        "User-Agent": UA,
        "Referer": PAGE_URL,
        "Accept": "text/csv,application/octet-stream,text/plain,*/*",
    }
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.content, dict(resp.headers)
        except Exception as e:
            last_exc = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * attempt)
    raise last_exc


def main():
    manifest = load_manifest()
    print(f"共 {len(manifest)} 個檔案待下載，輸出資料夾：{OUTPUT_DIR}\n")

    session = requests.Session()

    ok_count = 0
    failed = []
    skipped = []

    for i, item in enumerate(manifest, 1):
        category = item["category"]
        fid = item["fid"]
        filename = sanitize_filename(item["filename"])

        cat_dir = OUTPUT_DIR / sanitize_filename(category)
        cat_dir.mkdir(parents=True, exist_ok=True)
        out_path = cat_dir / filename

        print(f"[{i}/{len(manifest)}] {category} / {filename} (fid={fid}) ... ", end="", flush=True)

        try:
            content, headers = download_one(session, fid)
        except Exception as e:
            print(f"失敗：{e}")
            failed.append({"fid": fid, "filename": filename, "category": category, "error": str(e)})
            continue

        content_type = headers.get("Content-Type", "")
        looks_like_csv = (
            b"," in content[:2000] and
            b"<html" not in content[:500].lower() and
            b"<!doctype" not in content[:500].lower()
        )

        if not looks_like_csv:
            print(f"警告：內容看起來不像 CSV（Content-Type={content_type}），仍會存檔以便人工檢查")
            skipped.append({"fid": fid, "filename": filename, "category": category})

        with open(out_path, "wb") as f:
            f.write(content)

        print(f"OK（{len(content):,} bytes）")
        ok_count += 1
        time.sleep(REQUEST_DELAY_SEC)

    print("\n========== 下載完成 ==========")
    print(f"成功：{ok_count} / {len(manifest)}")
    if skipped:
        print(f"\n內容格式可疑（已存檔但建議人工檢查），共 {len(skipped)} 筆：")
        for s in skipped:
            print(f"  - [{s['category']}] {s['filename']} (fid={s['fid']})")
    if failed:
        print(f"\n下載失敗，共 {len(failed)} 筆：")
        for f_ in failed:
            print(f"  - [{f_['category']}] {f_['filename']} (fid={f_['fid']}): {f_['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
