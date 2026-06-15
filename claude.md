# MultiSenseFormatter 開發指南

## 專案概述

地質災害監測感測器數據處理工具，用於台灣 25 處 MT 潛勢區的監測數據標準化與歸零處理。

## 架構

```
vars.py          → 所有感測器配置（路徑、表頭格式、處理參數）
processors.py    → BaseProcessor 基類 + 各種專用處理器
run_processor.py → 主程式入口，初始化並執行處理器
```

## 處理器類型

| 處理器 | 用途 | 特點 |
|--------|------|------|
| `ZeroingProcessor` | 通用歸零處理 | 支援多欄位、可選累計計算 |
| `SeasonalRainfallProcessor` | 雨量計 | 乾濕季累積（5/1-11/30 濕季，12/1-4/30 乾季） |
| `GNSSProcessor` | GNSS 地表變位 | 單位轉換(m→mm)、星曆計算、欄位重命名 |

## 感測器配置結構

```python
# 1. 定義表頭格式（可多個版本）
SENSOR_FORMAT_V1 = {
    "id": "格式識別名稱",
    "expected_columns": ['欄位1', '欄位2', ...],  # 必須完全匹配
    "time_column": "系統時間",
    "value_columns": [
        {"name": "原始欄位名", "output_name": "輸出欄位名"}
    ]
}

# 2. 定義處理器配置
SENSOR_CONFIG = {
    "sensor_name": "顯示名稱",
    "target_subdir": "資料夾名稱",
    "input_path": SEPERATED_DIR,
    "output_path": ZEROED_DIR,
    "formats": [SENSOR_FORMAT_V1],
    "enable_cumulative": False,  # 可選，啟用累計計算
}
```

## 新增感測器步驟

1. 在 `vars.py` 新增 FORMAT 和 CONFIG
2. 在 `run_processor.py` 的 `SENSOR_REGISTRY` 加入一筆註冊
3. 選擇適合的處理器類型（或繼承 BaseProcessor 寫新的）

## 資料流程

```
data/input/          原始 Excel
     ↓ split_excel_by_location.py
data/seperated/      按地點/儀器類型拆分
     ↓ run_processor.py
data/zeroed/         歸零後 CSV 輸出
```

## 處理邏輯摘要

1. **每日採樣** - 每日取最後一筆數據
2. **日期篩選** - 只保留歸零日期之後的數據
3. **歸零計算** - `輸出值 = 原始值 - 歸零日基準值`
4. **累計計算**（可選）- `cumsum()` 累積加總

## 關鍵變數

- `ZERO_DATE`: 歸零基準日期（目前 2023-12-01）
- `SEPERATED_DIR`: 拆分後資料路徑
- `ZEROED_DIR`: 輸出路徑

## 目前啟用的感測器

查看 `run_processor.py` 中的 `SENSOR_REGISTRY` 確認已註冊的處理器。

## 測試

```bash
pytest tests/
```

## 注意事項

- 表頭格式必須**完全匹配**（包括欄位順序）
- 新表頭格式需新增 FORMAT 定義
- 累計欄位名稱自動將「歸零值」替換成「累計」
- GNSS 的星曆計算會自動判斷閏年
