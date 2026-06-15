# MultiSenseFormatter

自動化處理地質災害監測感測器數據的工具，支援 25 處 MT 潛勢區。

## 功能

- 將原始 Excel 數據按地點/儀器類型自動拆分歸檔
- 以指定日期為基準進行歸零處理，計算累積位移/變化量
- 支援多種感測器：水位觀測井、地表伸縮計、地表傾斜計、雨量計、GNSS
- GNSS 可選 LOS 投影（用於 InSAR 交叉驗證）

## 快速開始

### 1. 環境建置

```bash
# 使用 conda（建議）
conda env create -f environment.yml

# 或手動安裝
pip install pandas openpyxl
```

Windows 使用者也可以直接執行 `setup.bat`。

### 2. 設定

編輯 `vars.py` 設定區域：

```python
INSTRUMENT_FILE = r"data\20251031_25處MT潛勢區儀器編號.xlsx"  # 儀器編號對照表
INPUT_DIR = r"data\input"       # 原始資料輸入
SEPERATED_DIR = r"data\seperated"  # 拆分後資料
ZEROED_DIR = r"data\zeroed"     # 歸零後輸出

ZERO_DATE = "2023-12-01"       # 歸零基準日期
```

### 3. 準備資料

將原始 Excel 數據檔放入 `data/input/`，檔名格式為「縣市-鄉鎮區-站名.xlsx」。

### 4. 執行

```bash
# Step 1: 拆分原始資料（按地點/儀器類型分類）
python split_excel_by_location.py

# Step 2: 歸零處理（全部感測器）
python run_processor.py
```

Windows 使用者可直接點擊 `split_excel_by_location.bat` 和 `run_processor.bat`。

## 選擇性執行感測器

```bash
# 只執行 GNSS
python run_processor.py --sensor gnss

# 執行 GNSS 和雨量計
python run_processor.py --sensor gnss rain

# 強制覆蓋已存在的檔案
python run_processor.py --force --sensor water

# 列出所有可用的感測器
python run_processor.py --list
```

可用的感測器代號：

| 代號 | 感測器 | 處理方式 |
|------|--------|----------|
| `water` | 水位觀測井 | 單欄位歸零 |
| `extensometer` | 地表伸縮計 | 歸零 + 累計 |
| `inclinometer` | 地表傾斜計(雙軸) | 雙軸歸零 + 累計 |
| `rain` | 雨量計 | 乾濕季累積 |
| `gnss` | GNSS地表變位 | E/N/U 歸零、星曆計算、LOS 投影 |

## 資料流程

```
data/input/          原始 Excel（使用者放入）
     ↓ split_excel_by_location.py
data/seperated/      按「地名/儀器類型」拆分
     ↓ run_processor.py
data/zeroed/         歸零後 CSV 輸出
```

拆分後的目錄結構範例：

```
data/seperated/
└── 新竹縣-尖石鄉-D077_泰崗/
    ├── GNSS地表變位/
    │   ├── GP6(H1).xlsx
    │   └── JS077-G2(TG02).xlsx
    ├── 地表傾斜計(雙軸)/
    │   └── JS077-T1(TG01).xlsx
    └── 雨量計/
        └── JS077-R(TG02).xlsx
```

## 專案結構

```
vars.py                      感測器配置（路徑、表頭格式、處理參數）
processors.py                處理器類別（歸零、雨量、GNSS）
run_processor.py             歸零處理主程式
split_excel_by_location.py   資料拆分主程式
scripts/                     輔助腳本（InSAR 分析、繪圖等）
```

## GNSS 輸出欄位

| 欄位 | 說明 | 單位 |
|------|------|------|
| 星曆 | 小數點年份 (e.g. 2024.0027) | 年 |
| 系統時間 | 觀測時間 | YYYY/MM/DD HH:MM |
| 解算後E值 | 原始東向座標 | m |
| 解算後N值 | 原始北向座標 | m |
| 解算後U值 | 原始垂直座標 | m |
| 累積E位移(mm) | 歸零後東向位移 | mm |
| 累積N位移(mm) | 歸零後北向位移 | mm |
| 累積U位移(mm) | 歸零後垂直位移 | mm |
| 累積LOS位移(mm) | LOS 投影位移（啟用時） | mm |

## GNSS LOS 投影

LOS (Line-of-Sight) 投影將 GNSS 三維位移 (E, N, U) 投影至 SAR 衛星的雷達視線方向。

**投影公式：**

```
d_LOS = -sin(θ)cos(φ) × dE + sin(θ)sin(φ) × dN + cos(θ) × dU
```

θ = 入射角（從垂直方向量測），φ = 衛星飛行方向角（從北方順時針量測）。

**設定方式：** 在 `vars.py` 的 `GNSS_CONFIG` 中：

```python
"satellite_table": {
    "file": SATELLITE_TABLE_FILE,       # 衛星入射角表 Excel
    "heading_angles": {
        "ASC": 350,   # 升軌飛行方向角（度）
        "DES": 190,   # 降軌飛行方向角（度）
    },
    "los_output_name": "累積LOS位移(mm)",
},
```

## 新增感測器

1. 在 `vars.py` 新增 FORMAT 和 CONFIG（參考現有感測器格式）
2. 在 `run_processor.py` 的 `SENSOR_REGISTRY` 加入一筆註冊

## 注意事項

- 數據檔案必須是 `.xlsx` 格式，檔名需包含「縣市-鄉鎮區」
- 儀器編號檔案的每個分頁需有「儀器編號」和「儀器類型」欄位
- 表頭格式必須與 `vars.py` 中定義的 `expected_columns` 完全匹配
- 歸零計算只保留 `ZERO_DATE` 之後的數據

## 疑難排解

| 問題 | 解決方法 |
|------|----------|
| 分頁被歸類到「未分類」 | 檢查儀器編號檔案是否有對應資料 |
| 檔案讀取錯誤 | 確認檔案沒有被其他程式開啟 |
| ImportError | 執行 `pip install pandas openpyxl` |
| 處理器跳過檔案 | 確認 Excel 欄位是否與 `vars.py` 中的格式定義匹配 |
