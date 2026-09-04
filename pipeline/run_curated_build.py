#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
執行「精選版」管線：讀 data/raw/ 底下的原始 CSV（+ 可選的央行 CBC JSON），
套用 curated_build.py 的合併規則，輸出 web/data/*.js。

這支腳本把「哪些原始檔案 → 哪個最終資料集」的對應關係，跟每個最終資料集的
description／defaultDimFilters 這些策展決定，都寫死在這裡（STATIC_META /
DATASET_BUILDERS），之後如果使用者又要調整篩選範圍，直接改這支腳本就好，
不用再手動改 bundle JS 檔案。
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from curated_build import (
    melt_standard, melt_age_or_gender_ratewide, melt_wide_bucket_table,
    compute_overview_from_gender, summarize,
)

RATE_METRIC_RENAME = {
    "人數": None,  # 依 prefix 動態決定，見 build_mortgage_*
    "授信餘額": None,
    "平均利率": None,
}

CATEGORY_ORDER = ["個人貸款總覽", "房貸", "車貸", "信貸", "學貸", "卡債"]


def js_string_escape(obj):
    return json.dumps(obj, ensure_ascii=False)


def build_other_personal(raw_dir):
    p = raw_dir / "個人授信統計資訊"
    return {
        "1-1 個人總貸款狀況統計趨勢資料": melt_standard(p / "1-4 個人總貸款狀況統計趨勢資料.csv"),
        "1-2 新增個人總貸款狀況統計趨勢資料": melt_standard(p / "1-20 新增個人總貸款狀況統計趨勢資料.csv"),
    }


def build_student_loan(raw_dir):
    p = raw_dir / "個人授信統計資訊"
    return {
        "1-1 個人學生貸款狀況統計趨勢資料": melt_standard(p / "1-54 個人學生貸款狀況統計趨勢資料.csv"),
        "1-2 新增個人學生貸款狀況統計趨勢資料": melt_standard(p / "1-55 新增個人學生貸款狀況統計趨勢資料.csv"),
    }


def _overview_with_dims(records, view_label="總覽", cat_label="整體"):
    out = []
    for r in records:
        rec = dict(r)
        rec["類別"] = cat_label
        rec["檢視角度"] = view_label
        out.append(rec)
    return out


def build_mortgage(raw_dir):
    personal = raw_dir / "個人授信統計資訊"
    mortgage = raw_dir / "房貸類統計資訊"
    rename = {"人數": "個人房貸總人數", "授信餘額": "個人房貸總金額", "平均利率": "個人房貸平均利率"}
    rename_new = {"人數": "新增個人房貸總人數", "授信餘額": "新增個人房貸總金額", "平均利率": "新增個人房貸平均利率"}

    overview = _overview_with_dims(melt_standard(personal / "1-2 個人房屋貸款狀況統計趨勢資料.csv"))
    age = melt_age_or_gender_ratewide(mortgage / "1-23 房貸借款人各年齡層下的授信金額及利率統計表.csv",
                                       "借款人年齡區間", "年齡層", metric_rename=rename)
    gender = melt_age_or_gender_ratewide(mortgage / "1-24 房貸借款人不同性別下的授信金額及利率統計表.csv",
                                          "性別", "性別", metric_rename=rename)

    overview_new = _overview_with_dims(melt_standard(personal / "1-18 新增個人房屋貸款狀況統計趨勢資料.csv"))
    age_new = melt_age_or_gender_ratewide(mortgage / "1-27 房貸借款人各年齡層下的新增授信金額及利率統計表.csv",
                                           "借款人年齡區間", "年齡層", metric_rename=rename_new)
    gender_new = melt_age_or_gender_ratewide(mortgage / "1-28 房貸借款人不同性別下的新增授信金額及利率統計表.csv",
                                              "性別", "性別", metric_rename=rename_new)

    bundle = {
        "1-1 個人房屋貸款狀況統計趨勢資料": overview + age + gender,
        "1-2 新增個人房屋貸款狀況統計趨勢資料": overview_new + age_new + gender_new,
    }
    return bundle


def build_car_loan(raw_dir):
    personal = raw_dir / "個人授信統計資訊"
    car = raw_dir / "車貸類統計資訊"
    overview = _overview_with_dims(melt_standard(personal / "1-16 個人汽車貸款狀況統計趨勢資料.csv"))
    age = melt_age_or_gender_ratewide(car / "1-37 車貸借款人各年齡層下的授信金額及利率統計表.csv", "年齡", "年齡層")
    gender = melt_age_or_gender_ratewide(car / "1-38 車貸借款人不同性別下的授信金額及利率統計表.csv", "性別", "性別")

    overview_new = _overview_with_dims(melt_standard(personal / "1-21 新增個人汽車貸款狀況統計趨勢資料.csv"))
    age_new = melt_age_or_gender_ratewide(car / "1-39 車貸借款人各年齡層下的新增授信金額及利率統計表.csv", "年齡", "年齡層")
    gender_new = melt_age_or_gender_ratewide(car / "1-40 車貸借款人不同性別下的新增授信金額及利率統計表.csv", "性別", "性別")

    return {
        "1-1 個人汽車貸款狀況統計趨勢資料": overview + age + gender,
        "1-2 新增個人汽車貸款狀況統計趨勢資料": overview_new + age_new + gender_new,
    }


def build_credit_loan(raw_dir):
    personal = raw_dir / "個人授信統計資訊"
    credit = raw_dir / "信貸類統計資訊"
    overview = _overview_with_dims(melt_standard(personal / "1-3 個人信用貸款狀況統計趨勢資料.csv"))
    age = melt_age_or_gender_ratewide(credit / "1-31 信貸借款人各年齡層下的授信金額及利率統計表.csv", "年齡", "年齡層")
    gender = melt_age_or_gender_ratewide(credit / "1-32 信貸借款人不同性別下的授信金額及利率統計表.csv", "性別", "性別")

    overview_new = _overview_with_dims(melt_standard(personal / "1-19 新增個人信用貸款狀況統計趨勢資料.csv"))
    age_new = melt_age_or_gender_ratewide(credit / "1-33 信貸借款人各年齡層下的新增授信金額及利率統計表.csv", "年齡", "年齡層")
    gender_new = melt_age_or_gender_ratewide(credit / "1-34 信貸借款人不同性別下的新增授信金額及利率統計表.csv", "性別", "性別")

    return {
        "1-1 個人信用貸款狀況統計趨勢資料": overview + age + gender,
        "1-2 新增個人信用貸款狀況統計趨勢資料": overview_new + age_new + gender_new,
    }


def build_revolving_creditcard(raw_dir):
    rc = raw_dir / "循環信用及現金卡統計資訊"
    age1 = melt_wide_bucket_table(rc / "6-1 各年齡層信用卡循環信用金額統計表.csv", "循環信用金額", "年齡層")
    gender1 = melt_wide_bucket_table(rc / "6-2 不同性別信用卡循環信用金額統計表.csv", "循環信用金額", "性別")
    overview1 = compute_overview_from_gender(gender1)

    age3 = melt_wide_bucket_table(rc / "6-3 各年齡層未到期分期償還預借現金餘額統計表.csv",
                                   "未到期分期償還預借現金餘額", "年齡層")
    gender3 = melt_wide_bucket_table(rc / "6-6 不同性別未到期分期償還預借現金餘額統計表.csv",
                                      "未到期分期償還預借現金餘額", "性別")
    overview3 = compute_overview_from_gender(gender3)

    # 側邊選單/年齡標籤跟目前網站一致：性別用「男性/女性」，年齡沿用原始桶標籤，
    # 總覽用「全部」——都已經是 melt_wide_bucket_table / compute_overview_from_gender
    # 的預設輸出，不用再轉換。
    return {
        "6-1 信用卡循環信用金額統計表": overview1 + age1 + gender1,
        "6-3 未到期分期償還預借現金餘額統計表": overview3 + age3 + gender3,
    }


def build_cbc_mortgage_repair(cbc_json_path):
    """讀 fetch_cbc.py 抓回來的央行 EF99M01 原始 JSON，取出「房屋修繕貸款」
    （index 5：原始值，index 6：年增率）。JSON 格式見 fetch_cbc.py 的說明。

    這個來源不是 JCIC，抓取機制比較不穩定（見 claude/資料集篩選決定.md「跨機關
    資料來源」一節），所以這裡故意寫得保守：解析失敗就回傳 None、印警告，讓
    main() 改用「沿用舊資料」的備援，不要讓這個步驟出錯就讓整個房貸分類的
    房屋修繕貸款資料消失或整個管線失敗。"""
    if not cbc_json_path or not cbc_json_path.exists():
        return None
    try:
        with open(cbc_json_path, encoding="utf-8") as f:
            data = json.load(f)
        records = []
        for row in data["records"]:
            date_str = row["date"]
            val = row["values"][5]
            yoy = row["values"][6]
            if val is not None:
                records.append({"date": date_str, "metric": "房屋修繕貸款餘額", "value": val, "unit": "百萬元"})
            if yoy is not None:
                records.append({"date": date_str, "metric": "年增率", "value": yoy, "unit": "%"})
        if not records:
            raise ValueError("解析出 0 筆資料，可能是央行 API 回傳格式變了")
        return records
    except Exception as e:
        print(f"警告：解析央行 EF99M01 JSON 失敗（{e}），這次不更新房屋修繕貸款資料，"
              f"會沿用上一次的舊資料", file=sys.stderr)
        return None


def load_previous_cbc_records(out_dir: Path):
    """從「上一次已經產生、還沒被這次覆寫」的 mortgage.js 裡，把央行房屋修繕貸款
    那筆的 records 讀出來，當作 CBC 抓取失敗時的備援，避免那個資料集整個消失。"""
    prev_path = out_dir / "mortgage.js"
    if not prev_path.exists():
        return None
    try:
        text = prev_path.read_text(encoding="utf-8")
        m = re.search(r"window\.JCIC_DATASETS\[.mortgage.\]\s*=\s*(\{.*\});\s*$", text, re.S)
        if not m:
            return None
        bundle = json.loads(m.group(1))
        return bundle.get("房屋修繕貸款餘額統計表（中央銀行金融統計月報）")
    except Exception as e:
        print(f"警告：讀取舊的 mortgage.js 備援資料失敗（{e}）", file=sys.stderr)
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--out-dir", default="web/data")
    ap.add_argument("--cbc-json", default=None)
    ap.add_argument("--meta", default=str(Path(__file__).resolve().parent / "static_meta.json"),
                     help="靜態策展中繼資料（description/order/slug/defaultDimFilters）")
    args = ap.parse_args()

    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(args.meta, encoding="utf-8") as f:
        static_meta = json.load(f)

    bundles = {
        "other-personal": build_other_personal(raw_dir),
        "mortgage": build_mortgage(raw_dir),
        "car-loan": build_car_loan(raw_dir),
        "credit-loan": build_credit_loan(raw_dir),
        "student-loan": build_student_loan(raw_dir),
        "revolving-creditcard": build_revolving_creditcard(raw_dir),
    }

    cbc_records = build_cbc_mortgage_repair(Path(args.cbc_json)) if args.cbc_json else None
    if cbc_records is None:
        cbc_records = load_previous_cbc_records(out_dir)
        if cbc_records is not None:
            print("提示：這次改用上一次的房屋修繕貸款舊資料（央行來源這次沒有成功更新）",
                  file=sys.stderr)
    if cbc_records is not None:
        bundles["mortgage"]["房屋修繕貸款餘額統計表（中央銀行金融統計月報）"] = cbc_records
    else:
        print("警告：房屋修繕貸款資料這次完全沒有可用來源（新的抓不到、也沒有舊資料可沿用），"
              "這個資料集這次不會出現在網站上", file=sys.stderr)

    catalog = []
    for slug, bundle in bundles.items():
        for key, records in bundle.items():
            meta = static_meta.get(key)
            if meta is None:
                raise ValueError(f"static_meta.json 裡找不到 {key!r} 的策展中繼資料（description 等），"
                                  f"這是設定檔漏寫，不是資料問題，要先補上")
            info = summarize(records)
            entry = {
                "category": meta["category"],
                "file": key + ".csv",
                "dimensions": info["dimensions"],
                "metrics": info["metrics"],
                "row_count_raw": None,  # 精選合併後的資料集沒有單一「原始列數」概念，不再提供
                "record_count_long": info["record_count_long"],
                "year_min": info["year_min"],
                "year_max": info["year_max"],
                "slug": slug,
                "order": CATEGORY_ORDER.index(meta["category"]) if meta["category"] in CATEGORY_ORDER else 999,
                "description": meta["description"],
            }
            if "defaultDimFilters" in meta:
                entry["defaultDimFilters"] = meta["defaultDimFilters"]
            catalog.append(entry)

    catalog.sort(key=lambda it: (it["order"], it["file"]))

    with open(out_dir / "index.js", "w", encoding="utf-8") as f:
        f.write("// 自動產生，請勿手動編輯。來源：run_curated_build.py\n")
        f.write("window.JCIC_CATALOG = " + js_string_escape(catalog) + ";\n")
        f.write("window.JCIC_CATEGORY_ORDER = " + js_string_escape(CATEGORY_ORDER) + ";\n")

    for slug, bundle in bundles.items():
        out_path = out_dir / f"{slug}.js"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("// 自動產生，請勿手動編輯。來源：run_curated_build.py\n")
            f.write("window.JCIC_DATASETS = window.JCIC_DATASETS || {};\n")
            f.write(f"window.JCIC_DATASETS[{js_string_escape(slug)}] = " + js_string_escape(bundle) + ";\n")
        total_records = sum(len(v) for v in bundle.values())
        print(f"{slug}: {len(bundle)} 個資料集，共 {total_records} 筆長格式資料 -> {out_path.name}")

    print(f"\n共 {len(catalog)} 個側邊選單項目")


if __name__ == "__main__":
    main()
