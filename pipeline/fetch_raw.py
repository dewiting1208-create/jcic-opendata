#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
只下載「精選版」網站真正會用到的原始 JCIC CSV（26 個檔案），存到 data/raw/<分類>/。

跟原本的 download_jcic_data.py 不同：那支會抓全部 135 個檔案（機械式、給第一版
探索用），這支只抓 run_curated_build.py 實際會讀的檔案，減少每次自動更新要下載
的量，也避免抓到已經被使用者篩選掉、網站用不到的資料。

下載機制沿用 step1 驗證過的做法：直接 GET，帶瀏覽器慣用 User-Agent + Referer，
不需要 cookie／登入（見 claude/step1-下載機制驗證結果.md）。
"""
import sys
import time
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

# (fid, 分類資料夾, 檔名) —— 只列「精選版」13 個側邊選單項目實際會用到的來源檔案。
# 之後如果使用者要求把哪個資料集換掉/加回來，記得同步更新這裡跟
# run_curated_build.py 的 CURATION 邏輯，兩邊要對得上。
FILES = [
    ("739", "個人授信統計資訊", "1-4 個人總貸款狀況統計趨勢資料.csv"),
    ("755", "個人授信統計資訊", "1-20 新增個人總貸款狀況統計趨勢資料.csv"),
    ("1004", "個人授信統計資訊", "1-54 個人學生貸款狀況統計趨勢資料.csv"),
    ("1006", "個人授信統計資訊", "1-55 新增個人學生貸款狀況統計趨勢資料.csv"),
    ("735", "個人授信統計資訊", "1-2 個人房屋貸款狀況統計趨勢資料.csv"),
    ("751", "個人授信統計資訊", "1-18 新增個人房屋貸款狀況統計趨勢資料.csv"),
    ("719", "房貸類統計資訊", "1-23 房貸借款人各年齡層下的授信金額及利率統計表.csv"),
    ("721", "房貸類統計資訊", "1-24 房貸借款人不同性別下的授信金額及利率統計表.csv"),
    ("727", "房貸類統計資訊", "1-27 房貸借款人各年齡層下的新增授信金額及利率統計表.csv"),
    ("729", "房貸類統計資訊", "1-28 房貸借款人不同性別下的新增授信金額及利率統計表.csv"),
    ("742", "個人授信統計資訊", "1-16 個人汽車貸款狀況統計趨勢資料.csv"),
    ("757", "個人授信統計資訊", "1-21 新增個人汽車貸款狀況統計趨勢資料.csv"),
    ("898", "車貸類統計資訊", "1-37 車貸借款人各年齡層下的授信金額及利率統計表.csv"),
    ("900", "車貸類統計資訊", "1-38 車貸借款人不同性別下的授信金額及利率統計表.csv"),
    ("902", "車貸類統計資訊", "1-39 車貸借款人各年齡層下的新增授信金額及利率統計表.csv"),
    ("904", "車貸類統計資訊", "1-40 車貸借款人不同性別下的新增授信金額及利率統計表.csv"),
    ("737", "個人授信統計資訊", "1-3 個人信用貸款狀況統計趨勢資料.csv"),
    ("753", "個人授信統計資訊", "1-19 新增個人信用貸款狀況統計趨勢資料.csv"),
    ("816", "信貸類統計資訊", "1-31 信貸借款人各年齡層下的授信金額及利率統計表.csv"),
    ("818", "信貸類統計資訊", "1-32 信貸借款人不同性別下的授信金額及利率統計表.csv"),
    ("820", "信貸類統計資訊", "1-33 信貸借款人各年齡層下的新增授信金額及利率統計表.csv"),
    ("822", "信貸類統計資訊", "1-34 信貸借款人不同性別下的新增授信金額及利率統計表.csv"),
    ("828", "循環信用及現金卡統計資訊", "6-1 各年齡層信用卡循環信用金額統計表.csv"),
    ("829", "循環信用及現金卡統計資訊", "6-2 不同性別信用卡循環信用金額統計表.csv"),
    ("832", "循環信用及現金卡統計資訊", "6-3 各年齡層未到期分期償還預借現金餘額統計表.csv"),
    ("838", "循環信用及現金卡統計資訊", "6-6 不同性別未到期分期償還預借現金餘額統計表.csv"),
]


def download_one(session, fid):
    url = DOWNLOAD_URL_TMPL.format(fid=fid)
    headers = {"User-Agent": UA, "Referer": PAGE_URL,
               "Accept": "text/csv,application/octet-stream,text/plain,*/*"}
    last_exc = None
    for attempt in range(1, 4):
        try:
            resp = session.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            last_exc = e
            if attempt < 3:
                time.sleep(2 * attempt)
    raise last_exc


def main():
    out_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw")
    session = requests.Session()
    ok, failed = 0, []
    for fid, category, filename in FILES:
        cat_dir = out_root / category
        cat_dir.mkdir(parents=True, exist_ok=True)
        out_path = cat_dir / filename
        print(f"{category} / {filename} (fid={fid}) ... ", end="", flush=True)
        try:
            content = download_one(session, fid)
        except Exception as e:
            print(f"失敗：{e}")
            failed.append((fid, filename, str(e)))
            continue
        if b"," not in content[:2000] or b"<html" in content[:500].lower():
            print("警告：內容不像 CSV，仍會存檔")
        with open(out_path, "wb") as f:
            f.write(content)
        print(f"OK（{len(content):,} bytes）")
        ok += 1
        time.sleep(0.4)

    print(f"\n完成：{ok}/{len(FILES)} 成功")
    if failed:
        print("失敗清單：")
        for fid, filename, err in failed:
            print(f"  - {filename} (fid={fid}): {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
