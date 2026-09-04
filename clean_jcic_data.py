#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JCIC OpenData 資料清理腳本（Step 3）

讀取 data/raw/<分類>/*.csv，排除「其他公開資訊」分類（公告/FAQ/文件清單，非統計數字），
把剩下的統計類 CSV 轉成統一的長格式（long format）JSON，存到 data/processed/。

判斷邏輯：
- 每個檔案表頭固定以「年」「月」開頭
- 其餘欄位逐欄判斷：
    - 有任何值轉不成數字 → 視為「維度欄位（dimension）」，例如 產業別／性別／年齡
    - 都能轉成數字，但相異值很少（<=6，例如性別用 1/2 代碼存）→ 也視為維度欄位，
      並嘗試把數字代碼轉成文字標籤（見 KNOWN_CODE_LABELS / 表頭裡的圖例說明）
    - 都能轉成數字，且相異值夠多 → 視為「指標欄位（metric）」，會被 melt 成長格式的一列
- 欄位名稱結尾如果有形如 [仟元]、[%] 的單位標示，會拆出來存成 unit 欄位，
  metric 名稱本身則去掉單位標示，方便圖表標題使用

輸出：
- data/processed/<分類>/<原檔名去副檔名>.json：該檔案的長格式資料
- data/processed/files_index.json：每個檔案的摘要（分類、維度欄位、指標欄位、
  資料年月範圍、列數），給第四步做圖表分類邏輯用
"""
import csv
import glob
import io
import json
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
RAW_DIR = SCRIPT_DIR / "data" / "raw"
PROCESSED_DIR = SCRIPT_DIR / "data" / "processed"
EXCLUDED_CATEGORY = "其他公開資訊"

UNIT_RE = re.compile(r"^(.*?)[\[［]([^\]］]+)[\]］]\s*$")

# 有些維度欄位在原始 CSV 裡是用數字代碼存的（例如「性別」用 1/2，不是文字），
# 光看「是否能轉成數字」會被誤判成指標欄位。這裡設一個基數門檻：一個欄位就算
# 全部都是數字，只要相異值很少（<= LOW_CARDINALITY_THRESHOLD），也視為維度，
# 因為 135 個檔案裡的真指標（人數/金額/利率）每個都有幾十到上千種不同值。
LOW_CARDINALITY_THRESHOLD = 6

# 已知代碼欄位的中文標籤對照（JCIC 資料本身沒有在儲存格內附文字說明時，
# 依台灣官方統計常見慣例補上；如果之後發現對照有誤，這裡是唯一要改的地方）。
KNOWN_CODE_LABELS = {
    "性別": {1: "男", 2: "女"},
}

# 有些欄位的說明是直接寫在表頭的單位標示裡，例如「是否公開發行[1為是 0為否]」，
# 這種格式可以直接從欄名解析出代碼對照，不用猜。
LEGEND_RE = re.compile(r"(\d+)\s*為\s*([^\s0-9,，、；;]+)")


def parse_legend(unit_text):
    if not unit_text:
        return None
    pairs = LEGEND_RE.findall(unit_text)
    if not pairs:
        return None
    return {int(k): v for k, v in pairs}


def format_dim_value(raw_value, code_label_map):
    """把維度欄位的原始字串值轉成顯示用文字。如果值是數字代碼且有對照表，
    轉成文字標籤；如果是單純的整數浮點字串（例如 "1.0"），去掉多餘的 .0；
    否則原樣輸出。"""
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


def try_float(s):
    """回傳 (數值, 是否偵測到 % 符號)。有些欄位的百分比是直接把 % 寫在儲存格
    裡（例如 "5%"），不是只出現在表頭的 [%] 標示，這裡一併處理掉。"""
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
        name = m.group(1).strip()
        unit = m.group(2).strip()
        return name, unit
    return colname.strip(), None


def process_file(path: Path, category: str):
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return None
    header = [h.strip() for h in rows[0]]
    data_rows = [r for r in rows[1:] if any(cell.strip() for cell in r)]

    if len(header) < 3 or header[0] != "年" or header[1] != "月":
        return {"skipped": True, "reason": "header not starting with 年,月"}

    other_cols = list(range(2, len(header)))

    # classify columns: metric (all-numeric, many distinct values) vs
    # dimension (has non-numeric value, OR numeric but low-cardinality
    # code column like 性別=1/2)
    metric_cols = []
    dim_cols = []
    dim_code_labels = {}
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
        is_low_cardinality_code = all_numeric and has_any_value and len(distinct_vals) <= LOW_CARDINALITY_THRESHOLD
        if has_any_value and all_numeric and not is_low_cardinality_code:
            metric_cols.append(ci)
        else:
            dim_cols.append(ci)
            if is_low_cardinality_code:
                colname, unit = split_unit(header[ci])
                label_map = KNOWN_CODE_LABELS.get(colname) or parse_legend(unit)
                if label_map:
                    dim_code_labels[ci] = label_map

    records = []
    years = []
    for r in data_rows:
        if len(r) <= max(other_cols, default=1):
            # pad short rows
            r = r + [""] * (max(other_cols, default=1) + 1 - len(r))
        y_raw = r[0].strip()
        m_raw = r[1].strip()
        y, _ = try_float(y_raw)
        if y is None:
            continue
        y = int(y)
        try:
            m = int(m_raw)
        except ValueError:
            continue
        years.append(y)
        date_str = f"{y:04d}-{m:02d}"

        dims = {}
        for dc in dim_cols:
            colname, _unit = split_unit(header[dc])
            raw_val = r[dc].strip() if dc < len(r) else None
            dims[colname] = format_dim_value(raw_val, dim_code_labels.get(dc))

        for mc in metric_cols:
            metric_name, unit = split_unit(header[mc])
            val, had_percent = try_float(r[mc]) if mc < len(r) else (None, False)
            if unit is None and had_percent:
                unit = "%"
            rec = {"date": date_str, "metric": metric_name, "value": val}
            if unit:
                rec["unit"] = unit
            rec.update(dims)
            records.append(rec)

    summary = {
        "category": category,
        "file": path.name,
        "dimensions": sorted({split_unit(header[dc])[0] for dc in dim_cols}),
        "metrics": sorted({split_unit(header[mc])[0] for mc in metric_cols}),
        "row_count_raw": len(data_rows),
        "record_count_long": len(records),
        "year_min": min(years) if years else None,
        "year_max": max(years) if years else None,
    }
    return {"records": records, "summary": summary}


def main():
    files = sorted(RAW_DIR.glob("*/*.csv"))
    index = []
    processed_count = 0
    skipped_count = 0

    for f in files:
        category = f.parent.name
        if category == EXCLUDED_CATEGORY:
            continue

        result = process_file(f, category)
        if result is None:
            continue
        if result.get("skipped"):
            print(f"跳過（表頭不符預期）: {f}")
            skipped_count += 1
            continue

        out_dir = PROCESSED_DIR / category
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / (f.stem + ".json")
        with open(out_path, "w", encoding="utf-8") as out_f:
            json.dump(result["records"], out_f, ensure_ascii=False, indent=None)

        index.append(result["summary"])
        processed_count += 1
        print(f"[{processed_count}] {category} / {f.name} -> {len(result['records'])} 筆長格式資料")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROCESSED_DIR / "files_index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"\n========== 清理完成 ==========")
    print(f"處理成功：{processed_count}")
    print(f"跳過：{skipped_count}（不含已排除的「{EXCLUDED_CATEGORY}」分類，共 {len(list((RAW_DIR/EXCLUDED_CATEGORY).glob('*.csv'))) if (RAW_DIR/EXCLUDED_CATEGORY).exists() else 0} 個）")
    print(f"輸出位置：{PROCESSED_DIR}")


if __name__ == "__main__":
    main()
