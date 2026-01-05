# ==============================================================================
# 路徑設定
# ==============================================================================

INSTRUMENT_FILE = r"data\20251031_25處MT潛勢區儀器編號.xlsx"  # 儀器編號對照表
INPUT_DIR = r"data\input"                                      # 原始資料輸入
SEPERATED_DIR = r"data\seperated"                              # 拆分後資料
ZEROED_DIR = r"data\zeroed"                                    # 歸零後輸出

# ==============================================================================
# 處理器通用設定
# ==============================================================================

ZERO_DATE = "2023-12-01"  # 歸零基準日期 (格式: YYYY-MM-DD)

# ==============================================================================
# 感測器設定
# ==============================================================================
#
# 每個感測器需要定義：
#   1. FORMAT: 表頭格式定義（可有多個版本）
#      - id: 格式識別名稱（用於日誌顯示）
#      - expected_columns: 預期的欄位列表（必須完全匹配）
#      - time_column: 時間欄位名稱
#      - value_columns: 要處理的數值欄位
#        - name: 原始欄位名
#        - output_name: 歸零後欄位名
#
#   2. CONFIG: 感測器處理設定
#      - sensor_name: 感測器名稱（用於顯示）
#      - target_subdir: 資料所在子目錄名稱
#      - input_path: 輸入路徑
#      - output_path: 輸出路徑
#      - formats: 支援的表頭格式列表
#      - enable_cumulative: 是否啟用累計計算（可選，預設 False）
#
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. 水位觀測井
# ------------------------------------------------------------------------------

WATER_LEVEL_FORMAT_V1 = {
    "id": "Standard",
    "expected_columns": ['儀器名稱', '系統時間', '水位高', '相對水位高'],
    "time_column": "系統時間",
    "value_columns": [
        {"name": "水位高", "output_name": "水位高歸零值"}
    ]
}

WATER_LEVEL_FORMAT_V2 = {
    "id": "Standard (含額外欄位)",
    "expected_columns": ['儀器名稱', '系統時間', '水位高', '相對水位高', 'Unnamed: 4'],
    "time_column": "系統時間",
    "value_columns": [
        {"name": "水位高", "output_name": "水位高歸零值"}
    ]
}

WATER_LEVEL_CONFIG = {
    "sensor_name": "Water Level",
    "target_subdir": "水位觀測井",
    "input_path": SEPERATED_DIR,
    "output_path": ZEROED_DIR,
    "formats": [WATER_LEVEL_FORMAT_V1, WATER_LEVEL_FORMAT_V2],
}

# ------------------------------------------------------------------------------
# 2. 地表伸縮計
# ------------------------------------------------------------------------------

EXTENSOMETER_FORMAT_V1 = {
    "id": "Standard",
    "expected_columns": ['儀器名稱', '系統時間', '伸張量', '累積變位量', '1日變位量'],
    "time_column": "系統時間",
    "value_columns": [
        {"name": "伸張量", "output_name": "伸張量歸零值"}
    ]
}

EXTENSOMETER_CONFIG = {
    "sensor_name": "Surface Extensometer",
    "target_subdir": "地表伸縮計",
    "input_path": SEPERATED_DIR,
    "output_path": ZEROED_DIR,
    "formats": [EXTENSOMETER_FORMAT_V1],
    "enable_cumulative": True,  # 啟用累計計算
}

# ------------------------------------------------------------------------------
# 3. 地表傾斜計（雙軸）
# ------------------------------------------------------------------------------

INCLINOMETER_FORMAT_V1 = {
    "id": "Standard",
    "expected_columns": [
        '儀器名稱', '系統時間',
        '方位一觀測值', '方位二觀測值',
        '方位一累積變位量', '方位二累積變位量',
        '方位一1日變位量', '方位二1日變位量'
    ],
    "time_column": "系統時間",
    "value_columns": [
        {"name": "方位一觀測值", "output_name": "方位一歸零值"},
        {"name": "方位二觀測值", "output_name": "方位二歸零值"}
    ]
}

INCLINOMETER_CONFIG = {
    "sensor_name": "Inclinometer",
    "target_subdir": "地表傾斜計(雙軸)",
    "input_path": SEPERATED_DIR,
    "output_path": ZEROED_DIR,
    "formats": [INCLINOMETER_FORMAT_V1],
    "enable_cumulative": True,  # 啟用累計計算
}

# ------------------------------------------------------------------------------
# 4. 雨量計
# ------------------------------------------------------------------------------
#
# 雨量計使用季節性累積：
#   - 乾季：12/1 至 4/30
#   - 濕季：5/1 至 11/30
# 每個季節開始時累積歸零
#
# ------------------------------------------------------------------------------

RAIN_GAUGE_FORMAT_V1 = {
    "id": "Standard",
    "expected_columns": [
        '儀器名稱', '系統時間',
        '10分鐘累積雨量', '1小時累積雨量', '3小時累積雨量',
        '6小時累積雨量', '12小時累積雨量', '24小時累積雨量',
        '48小時累積雨量', '72小時累積雨量', '7日累積雨量', '30日累積雨量'
    ],
    "time_column": "系統時間",
    "value_column": "24小時累積雨量",
    "output_column": "季節累積雨量",
}

RAIN_GAUGE_CONFIG = {
    "sensor_name": "Rain Gauge",
    "target_subdir": "雨量計",
    "input_path": SEPERATED_DIR,
    "output_path": ZEROED_DIR,
    "formats": [RAIN_GAUGE_FORMAT_V1],
    # 季節設定
    "seasons": {
        "wet": {"start_month": 5, "start_day": 1, "end_month": 11, "end_day": 30},    # 濕季
        "dry": {"start_month": 12, "start_day": 1, "end_month": 4, "end_day": 30},    # 乾季
    },
}

# ------------------------------------------------------------------------------
# 5. GNSS
# ------------------------------------------------------------------------------

GNSS_FORMAT_V1 = {
    "id": "Standard",
    "expected_columns": [
        '儀器名稱', '系統時間', '解算後E值', '解算後N值', '解算後H值', '方位角',
        '三軸變位速率', '平面變位速率', '累積變位量', '每日解算後E值',
        '每日解算後N值', '每日解算後H值'
    ],
    "time_column": "系統時間",
    "value_columns": [
        {"name": "解算後E值", "output_name": "累積E位移(mm)"},
        {"name": "解算後N值", "output_name": "累積N位移(mm)"},
        {"name": "解算後H值", "output_name": "累積U位移(mm)"}
    ],
    # For the final output file
    "final_columns": [
        '星曆', '系統時間', '解算後E值', '解算後N值', '解算後U值',
        '累積E位移(mm)', '累積N位移(mm)', '累積U位移(mm)'
    ],
    "rename_map": {
        "解算後H值": "解算後U值"
    }
}

GNSS_CONFIG = {
    "sensor_name": "GNSS",
    "target_subdir": "GNSS地表變位",
    "input_path": SEPERATED_DIR,
    "output_path": ZEROED_DIR,
    "formats": [GNSS_FORMAT_V1],
}
