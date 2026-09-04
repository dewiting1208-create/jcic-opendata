#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JCIC OpenData「精選版」自動更新管線（2026-09-04 新增）

背景：
  網站目前的 13 個側邊選單項目，是使用者這幾天一輪一輪手動篩選、合併、改名出來的
  成果（見 claude/資料集篩選決定.md），跟原本 Step 2/3/4 寫的機械式管線
  （download_jcic_data.py → clean_jcic_data.py → build_web_data.py，抓全部 135 筆、
  維持 JCIC 原始 9 大分類）完全不是同一回事。如果直接把舊管線排程重跑，會把使用者
  篩選過的成果洗掉、變回最原始的雜亂版本。

  這支腳本取代舊的 clean_jcic_data.py + build_web_data.py，只處理「目前網站真的
  有用到」的原始 CSV，並且把當初手動做過的合併/改名邏輯寫成固定規則，讓它可以在
  資料來源出新一季資料時重新跑一次，數字會更新、但分類/合併/命名方式不會跑掉。

用法：
    python3 curated_build.py
        --raw-dir data/raw          （download_jcic_data.py 下載出來的原始 CSV 所在）
        --out-dir web/data          （輸出 bundle 的資料夾）
        --cbc-json cbc_ef99m01.json （可選：央行 API 回傳的原始 JSON，見 fetch_cbc.py）

設計原則：
  - 「保留哪些資料集、怎麼合併、怎麼改名」寫死在 CURATION 設定裡，不會因為資料
    來源新增/減少檔案就跑掉——JCIC 就算之後又新增其他統計表，這支腳本也不會自動
    多收，維持使用者當初篩選過的範圍。
  - 「說明文字（description）、分類順序、defaultDimFilters」這些是使用者的策展
    決定，不是從原始資料算出來的，寫死在 STATIC_META 裡，每次重跑都不會變。
  - 每個資料集的 row_count_raw / record_count_long / year_min / year_max 這些
    「跟著資料變動」的欄位，每次重跑都會重新計算。
"""
import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

UNIT_RE = re.compile(r"^(.*?)[\[［]([^\]］]+)[\]］]\s*$")
LEGEND_RE = re.compile(r"(\d+)\s*為\s*([^\s0-9,，、；;]+)")
LOW_CARDINALITY_THRESHOLD = 6
KNOWN_CODE_LABELS = {"性別": {1: "男", 2: "女"}}
PERCENTILE_RE = re.compile(r"百分位數$")


def try_float(s):
    if s is None:
        return None, False
    s = s.strip().replace(",", "")
    if s == "":
        return None, False
    had_percent = s.endswith("%")
    if had_percent:
        s = s[:-1].strip()
    if s == "":
        return None, False
    try:
        return float(s), had_percent
    except ValueError:
        return None, False


def split_unit(colname: str):
    m = UNIT_RE.match(colname.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return colname.strip(), None


def parse_legend(unit_text):
    if not unit_text:
        return None
    pairs = LEGEND_RE.findall(unit_text)
    if not pairs:
        return None
    return {int(k): v for k, v in pairs}


def format_dim_value(raw_value, code_label_map):
    v = raw_value.strip() if raw_value else raw_value
    if not v:
        return v
    num, _ = try_float(v)
    if num is not None:
        if code_label_map is not None:
            key = int(num) if num == int(num) else num
            if key in code_label_map:
                return code_label_map[key]
        if num == int(num):
            return str(int(num))
    return v


def read_csv_rows(path: Path):
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return [], []
    header = [h.strip() for h in rows[0]]
    data_rows = [r for r in rows[1:] if any(cell.strip() for cell in r)]
    return header, data_rows


def classify_columns(header, data_rows):
    """跟 clean_jcic_data.py 完全一樣的欄位分類邏輯：其餘欄位裡，全部能轉數字
    且相異值夠多的當指標；不能轉數字、或雖然能轉數字但相異值很少（<=6，例如
    性別用 1/2 代碼存）的當維度。"""
    other_cols = list(range(2, len(header)))
    metric_cols, dim_cols, dim_code_labels = [], [], {}
    for ci in other_cols:
        all_numeric = True
        has_any_value = False
        distinct_vals = set()
        for r in data_rows:
            if ci >= len(r):
                continue
            v = r[ci].strip()
            if v == "":
                continue
            has_any_value = True
            val, _ = try_float(v)
            if val is None:
                all_numeric = False
                break
            distinct_vals.add(val)
        is_low_card = all_numeric and has_any_value and len(distinct_vals) <= LOW_CARDINALITY_THRESHOLD
        if has_any_value and all_numeric and not is_low_card:
            metric_cols.append(ci)
        else:
            dim_cols.append(ci)
            if is_low_card:
                colname, unit = split_unit(header[ci])
                label_map = KNOWN_CODE_LABELS.get(colname) or parse_legend(unit)
                if label_map:
                    dim_code_labels[ci] = label_map
    return metric_cols, dim_cols, dim_code_labels


def melt_standard(path: Path, drop_percentiles=True, extra_dims=None):
    """把「年,月,指標1,指標2,...」這種標準寬表轉成長格式 records。
    extra_dims: {固定欄位名: 固定值} 額外加到每筆記錄上（例如合併時要標記
    類別/檢視角度）。"""
    header, data_rows = read_csv_rows(path)
    if not header or header[0] != "年" or header[1] != "月":
        raise ValueError(f"{path}: 表頭不是「年,月」開頭，跟預期不符")
    metric_cols, dim_cols, dim_code_labels = classify_columns(header, data_rows)

    records = []
    for r in data_rows:
        maxcol = max(metric_cols + dim_cols, default=1)
        if len(r) <= maxcol:
            r = r + [""] * (maxcol + 1 - len(r))
        y, _ = try_float(r[0].strip())
        if y is None:
            continue
        y = int(y)
        try:
            m = int(r[1].strip())
        except ValueError:
            continue
        date_str = f"{y:04d}-{m:02d}"

        dims = {}
        for dc in dim_cols:
            colname, _unit = split_unit(header[dc])
            raw_val = r[dc].strip() if dc < len(r) else None
            dims[colname] = format_dim_value(raw_val, dim_code_labels.get(dc))
        if extra_dims:
            dims.update(extra_dims)

        for mc in metric_cols:
            metric_name, unit = split_unit(header[mc])
            if drop_percentiles and PERCENTILE_RE.search(metric_name):
                continue
            val, had_percent = try_float(r[mc]) if mc < len(r) else (None, False)
            if val is None:
                continue
            if unit is None and had_percent:
                unit = "%"
            rec = {"date": date_str, "metric": metric_name, "value": val}
            if unit:
                rec["unit"] = unit
            rec.update(dims)
            records.append(rec)
    return records


def melt_age_or_gender_ratewide(path: Path, category_dim_name, view_label,
                                 metric_rename=None):
    """處理「房貸/車貸/信貸借款人各年齡層／不同性別下的授信金額及利率統計表」這種
    格式：欄位是 年,月,(性別或年齡),人數,授信餘額,平均利率（或已經是加好前綴的
    XX總人數/XX總金額/XX平均利率）。輸出：每筆記錄的「類別」＝該年齡/性別的值，
    「檢視角度」＝ view_label（年齡層或性別）。
    metric_rename: 原始指標名稱 -> 最終指標名稱的對照表（房貸這幾筆的原始指標名
    是通用的「人數/授信餘額/平均利率」，要改成跟總覽版一致的「個人房貸總人數」等；
    車貸/信貸原始指標名本身就已經帶「個人車貸/個人信貸」前綴，不用改，傳 None）。"""
    header, data_rows = read_csv_rows(path)
    if not header or header[0] != "年" or header[1] != "月":
        raise ValueError(f"{path}: 表頭不是「年,月」開頭")
    metric_cols, dim_cols, dim_code_labels = classify_columns(header, data_rows)

    # 找出代表「年齡/性別」的維度欄位（通常是唯一一個 dim 欄）
    if len(dim_cols) != 1:
        raise ValueError(f"{path}: 預期剛好 1 個維度欄位（{category_dim_name}），"
                          f"實際找到 {len(dim_cols)} 個：{[split_unit(header[c])[0] for c in dim_cols]}")
    cat_col = dim_cols[0]

    records = []
    for r in data_rows:
        maxcol = max(metric_cols + [cat_col], default=1)
        if len(r) <= maxcol:
            r = r + [""] * (maxcol + 1 - len(r))
        y, _ = try_float(r[0].strip())
        if y is None:
            continue
        y = int(y)
        try:
            m = int(r[1].strip())
        except ValueError:
            continue
        date_str = f"{y:04d}-{m:02d}"

        colname, _unit = split_unit(header[cat_col])
        cat_val = format_dim_value(r[cat_col].strip() if cat_col < len(r) else None,
                                    dim_code_labels.get(cat_col))

        for mc in metric_cols:
            metric_name, unit = split_unit(header[mc])
            if metric_rename:
                metric_name = metric_rename.get(metric_name, metric_name)
            val, had_percent = try_float(r[mc]) if mc < len(r) else (None, False)
            if val is None:
                continue
            if unit is None and had_percent:
                unit = "%"
            rec = {"date": date_str, "metric": metric_name, "value": val,
                   "類別": cat_val, "檢視角度": view_label}
            if unit:
                rec["unit"] = unit
            records.append(rec)
    return records


def melt_wide_bucket_table(path: Path, metric_name, view_label, unit_hint=None):
    """處理 6-1/6-2/6-3/6-6 這種「年,月,年齡桶1[仟元],年齡桶2[仟元],...」或
    「年,月,男性[仟元],女性[仟元]」的寬表：每個欄位其實是一個類別（年齡層或性別），
    不是不同指標，要轉成「類別＝欄名, 指標＝metric_name（固定）」。"""
    header, data_rows = read_csv_rows(path)
    if not header[0].strip("﻿") == "年":
        header[0] = header[0].strip("﻿")
    if header[0] != "年" or header[1] != "月":
        raise ValueError(f"{path}: 表頭不是「年,月」開頭：{header[:2]}")
    bucket_cols = list(range(2, len(header)))

    records = []
    for r in data_rows:
        maxcol = max(bucket_cols, default=1)
        if len(r) <= maxcol:
            r = r + [""] * (maxcol + 1 - len(r))
        y, _ = try_float(r[0].strip())
        if y is None:
            continue
        y = int(y)
        try:
            m = int(r[1].strip())
        except ValueError:
            continue
        date_str = f"{y:04d}-{m:02d}"
        for bc in bucket_cols:
            label, unit = split_unit(header[bc])
            val, _ = try_float(r[bc]) if bc < len(r) else (None, False)
            if val is None:
                continue
            rec = {"date": date_str, "metric": metric_name, "value": val,
                   "類別": label, "檢視角度": view_label}
            if unit or unit_hint:
                rec["unit"] = unit or unit_hint
            records.append(rec)
    return records


def compute_overview_from_gender(gender_records, overview_label="全部"):
    """「總覽」＝男性+女性兩個類別加總（跟現有網站的既有規律一致：性別兩類加總
    永遠完全吻合總覽，用這個方式算「總覽」比用年齡層加總更準)。"""
    by_key = {}
    for rec in gender_records:
        key = (rec["date"], rec["metric"])
        by_key.setdefault(key, {"unit": rec.get("unit"), "total": 0.0, "n": 0})
        by_key[key]["total"] += rec["value"]
        by_key[key]["n"] += 1
    out = []
    for (date, metric), agg in by_key.items():
        if agg["n"] < 2:
            continue  # 該月只有其中一個性別有資料，加總沒有意義，跳過
        rec = {"date": date, "metric": metric, "value": agg["total"],
               "類別": overview_label, "檢視角度": "總覽"}
        if agg["unit"]:
            rec["unit"] = agg["unit"]
        out.append(rec)
    return out


def summarize(records):
    dims = sorted({k for r in records for k in r.keys()
                   if k not in ("date", "metric", "value", "unit")})
    metrics = sorted({r["metric"] for r in records})
    years = [int(r["date"][:4]) for r in records]
    return {
        "dimensions": dims,
        "metrics": metrics,
        "record_count_long": len(records),
        "year_min": min(years) if years else None,
        "year_max": max(years) if years else None,
    }
